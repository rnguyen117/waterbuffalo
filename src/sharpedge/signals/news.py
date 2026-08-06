"""News ingestion and headline classification.

The value of a news feed to a bettor is almost entirely about latency. A
headline that is an hour old has been priced by every book that matters. A
headline that is four minutes old has been priced by two of them.

This module classifies headlines into categories that carry known betting
consequences, extracts the teams and players involved, and emits either a
structured :class:`~sharpedge.models.InjuryReport` (so the injury signal can
price it properly in points) or a direct sentiment nudge for the categories
that do not reduce cleanly to points.

Deliberately keyword-based rather than model-based. Betting news is a small,
formulaic vocabulary -- "ruled out", "will not travel", "expected to play",
"placed on IR" -- and matching it exactly is more reliable and far faster
than a language model, which matters when the entire edge is measured in
minutes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from ..models import InjuryReport, InjuryStatus, NewsItem, SignalContribution, utcnow
from .base import SignalContext, clamp, points_to_logit, recency_credit


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


@dataclass
class Classification:
    category: str
    status: InjuryStatus | None
    confidence: float
    matched: str


# Ordered most specific first: "will not play" must beat "play".
STATUS_PATTERNS: list[tuple[str, InjuryStatus, float]] = [
    (r"\bruled out\b", InjuryStatus.OUT, 0.97),
    (r"\bwill (?:not|n't) (?:play|suit up|dress)\b", InjuryStatus.OUT, 0.96),
    (r"\bwon'?t play\b", InjuryStatus.OUT, 0.96),
    (r"\bout for the (?:season|year)\b", InjuryStatus.OUT, 0.99),
    (r"\bplaced on (?:the )?(?:ir|injured reserve|\d+-day il|il)\b", InjuryStatus.OUT, 0.97),
    (r"\bwill (?:miss|sit out)\b", InjuryStatus.OUT, 0.94),
    (r"\binactive\b", InjuryStatus.OUT, 0.95),
    (r"\bscratched\b", InjuryStatus.OUT, 0.93),
    (r"\bsuspended\b", InjuryStatus.OUT, 0.92),
    (r"\bwill not travel\b", InjuryStatus.OUT, 0.94),
    (r"\bdoubtful\b", InjuryStatus.DOUBTFUL, 0.90),
    (r"\bgame[- ]time decision\b", InjuryStatus.GAME_TIME_DECISION, 0.88),
    (r"\bquestionable\b", InjuryStatus.QUESTIONABLE, 0.88),
    (r"\bprobable\b", InjuryStatus.PROBABLE, 0.85),
    (r"\bexpected to play\b", InjuryStatus.PROBABLE, 0.86),
    (r"\b(?:cleared|activated|will play|returns?)\b", InjuryStatus.ACTIVE, 0.82),
    (r"\bupgraded to (?:active|available)\b", InjuryStatus.ACTIVE, 0.90),
]

CATEGORY_PATTERNS: list[tuple[str, str, float]] = [
    ("injury", r"\b(?:injur|strain|sprain|tear|acl|hamstring|concussion|ankle|knee|groin|illness|sick)\w*\b", 0.8),
    ("lineup", r"\b(?:starting lineup|will start|gets the start|named starter|scratched)\b", 0.75),
    ("goalie", r"\b(?:starting goalie|between the pipes|gets the nod in net)\b", 0.85),
    ("pitcher", r"\b(?:starting pitcher|takes the mound|scratched from (?:his|the) start)\b", 0.85),
    ("trade", r"\b(?:traded|acquired|waived|released|signed)\b", 0.6),
    ("coaching", r"\b(?:fired|interim head coach|stepping down|relieved of duties)\b", 0.65),
    ("weather", r"\b(?:wind|rain|snow|storm|blizzard|gust|downpour)\w*\b", 0.7),
    ("motivation", r"\b(?:resting starters|clinched|eliminated|nothing to play for|tanking)\b", 0.7),
    ("discipline", r"\b(?:suspended|ejected|arrested|violation of team rules)\b", 0.75),
]


def classify(headline: str) -> Classification:
    """Categorize a headline and extract an availability status if present."""
    text = headline.lower()

    status: InjuryStatus | None = None
    status_conf = 0.0
    matched = ""
    for pattern, st, conf in STATUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            status, status_conf, matched = st, conf, pattern
            break

    category = "general"
    cat_conf = 0.3
    for name, pattern, conf in CATEGORY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            category, cat_conf = name, conf
            break

    if status is not None and category == "general":
        category = "injury"

    return Classification(
        category=category,
        status=status,
        confidence=max(status_conf, cat_conf),
        matched=matched or category,
    )


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

# Capitalized two-or-three word sequences are almost always player names in
# sports headlines. Common false positives are filtered explicitly.
_NAME_RE = re.compile(r"\b([A-Z][a-z'.-]+(?:\s+[A-Z][a-z'.-]+){1,2})\b")

_NAME_STOPWORDS = {
    "Monday Night", "Sunday Night", "Thursday Night", "Super Bowl", "World Series",
    "Stanley Cup", "New York", "Los Angeles", "San Francisco", "Las Vegas",
    "Injury Report", "Head Coach", "Wild Card", "Free Agency", "Trade Deadline",
}


def extract_players(headline: str) -> list[str]:
    """Pull likely player names out of a headline."""
    found = []
    for match in _NAME_RE.finditer(headline):
        name = match.group(1)
        if name in _NAME_STOPWORDS:
            continue
        if len(name.split()) > 3:
            continue
        found.append(name)
    return found


def match_teams(headline: str, teams: list[str]) -> list[str]:
    """Which of the known teams a headline mentions.

    Matches on the last word of the team name as well as the full name,
    because headlines say "Chiefs" far more often than "Kansas City Chiefs".
    """
    text = headline.lower()
    hits = []
    for team in teams:
        full = team.lower()
        nickname = full.split()[-1] if full.split() else full
        if full in text or (len(nickname) > 3 and re.search(rf"\b{re.escape(nickname)}\b", text)):
            hits.append(team)
    return hits


def to_injury_reports(
    items: list[NewsItem],
    known_teams: list[str],
    sport: str,
    player_values: dict[str, float] | None = None,
) -> list[InjuryReport]:
    """Convert classified headlines into structured injury reports.

    ``player_values`` maps a player name to the points his absence is worth.
    Without it the report carries zero point value and the injury signal will
    fall back to positional defaults, which is why maintaining that table for
    the players who actually move lines is the highest-leverage manual work
    in this whole package.
    """
    player_values = player_values or {}
    reports: list[InjuryReport] = []

    for item in items:
        cls = classify(item.headline)
        if cls.status is None:
            continue
        teams = item.teams or match_teams(item.headline, known_teams)
        if not teams:
            continue
        players = item.players or extract_players(item.headline)
        if not players:
            continue
        for player in players[:1]:  # the headline subject is the first name
            reports.append(
                InjuryReport(
                    player=player,
                    team=teams[0],
                    status=cls.status,
                    point_value=player_values.get(player, 0.0),
                    reported_at=item.published,
                    note=item.headline,
                )
            )
    return reports


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


class BreakingNewsSignal:
    """Flag very recent, market-moving headlines that books may not have priced.

    The output is intentionally modest in magnitude and large in urgency: the
    point is not that the model knows better, it is that a specific book's
    number is about to be wrong and there is a short window to take it.
    """

    name = "breaking_news"

    def __init__(self, urgent_minutes: float = 20.0):
        self.urgent_minutes = urgent_minutes

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        team = ctx.team_for_outcome()
        if team is None or not ctx.news:
            return []

        out: list[SignalContribution] = []
        for item in ctx.news:
            age = item.age_minutes(ctx.now)
            if age > self.urgent_minutes:
                continue
            teams = item.teams or match_teams(
                item.headline, [ctx.event.home_team, ctx.event.away_team]
            )
            if not teams:
                continue
            cls = classify(item.headline)
            if cls.category in ("general",):
                continue

            affects_us = team in teams
            # Bad news for the opponent is good news for this outcome.
            direction = -1.0 if affects_us else 1.0
            severity = _category_severity(cls.category, cls.status)
            if severity == 0.0:
                continue

            adjustment = points_to_logit(
                direction * severity, ctx.market_probability, ctx.sport
            )
            weight = clamp(cls.confidence * recency_credit(item.published, ctx.now, 25.0), 0.0, 1.0)
            out.append(
                SignalContribution(
                    name=self.name,
                    logit_adjustment=adjustment,
                    weight=weight,
                    rationale=(
                        f"{int(age)} min ago: {item.headline.strip()[:110]} "
                        f"[{cls.category}] -- slow books may not have repriced"
                    ),
                    points=direction * severity,
                    source=item.source,
                    observed_at=item.published,
                )
            )
        return out


def _category_severity(category: str, status: InjuryStatus | None) -> float:
    """Rough point impact by headline category, before player-specific detail."""
    if category == "injury" and status == InjuryStatus.OUT:
        return 1.5
    if category == "injury":
        return 0.4
    if category in ("goalie", "pitcher"):
        return 0.8
    if category == "lineup":
        return 0.5
    if category == "discipline":
        return 0.9
    if category == "coaching":
        return 0.6
    if category == "motivation":
        return 1.2
    return 0.0


class MotivationSignal:
    """Teams with nothing to play for.

    Late-season spots where a team has clinched or been eliminated are the
    clearest motivation edge, because the effect is real, the market is slow
    to price it, and coaches announce it publicly. Resting starters in a
    meaningless final week is worth multiple points and the number frequently
    does not reflect it until the inactives post.
    """

    name = "motivation"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        team = ctx.team_for_outcome()
        if team is None:
            return []
        meta = ctx.event.metadata or {}
        flags = meta.get("motivation", {})
        own = flags.get(team)
        opp = flags.get(ctx.event.opponent_of(team) or "")
        if not own and not opp:
            return []

        severity = {"resting_starters": 3.5, "eliminated": 1.2, "clinched": 1.0}
        points = 0.0
        reasons = []
        if own:
            points -= severity.get(own, 0.0)
            reasons.append(f"{team}: {own.replace('_', ' ')}")
        if opp:
            points += severity.get(opp, 0.0)
            reasons.append(f"opponent: {opp.replace('_', ' ')}")
        if abs(points) < 0.2:
            return []

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=points_to_logit(points, ctx.market_probability, ctx.sport),
                weight=0.7,
                rationale="; ".join(reasons),
                points=points,
                source="schedule context",
            )
        ]
