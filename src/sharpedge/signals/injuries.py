"""Injury and availability signals.

Injuries are the most valuable live information in sports betting, and also
the easiest to get wrong, because the tempting mistake is to bet the news
instead of the residual. By the time an injury is on a national feed, the
market makers have moved. The money is in two narrower places:

  1. **Speed.** The window between a beat reporter's post and a soft book
     repricing is measured in minutes. During it, the stale book is offering
     a number that is provably wrong.
  2. **Magnitude.** The market moves on a headline immediately but often
     misjudges *how much*. Backup quality is systematically underrated when
     the backup is competent and overrated when the injury is to a role
     player the public knows by name.

So this module estimates the point impact of an absence, subtracts the
movement that already happened, and claims only what is left.
"""

from __future__ import annotations

from ..models import InjuryReport, InjuryStatus, SignalContribution
from .base import (
    SignalContext,
    book_lag_credit,
    clamp,
    points_to_logit,
    recency_credit,
    residual_after_market_move,
)

# ---------------------------------------------------------------------------
# Positional value
# ---------------------------------------------------------------------------
#
# Points the spread moves when a starter at this position is replaced by a
# typical backup. These are the spread-market consensus values, not a claim
# about individual talent -- a specific player's value is set by
# ``point_value`` on the report and these are the fallback.

POSITION_VALUE: dict[str, dict[str, float]] = {
    "nfl": {
        "QB": 6.5,   # by far the largest single-player effect in any sport
        "RB": 1.2,
        "WR": 1.4,
        "TE": 0.9,
        "OL": 0.8,
        "LT": 1.3,
        "EDGE": 1.3,
        "DL": 1.0,
        "LB": 0.7,
        "CB": 1.1,
        "S": 0.8,
        "K": 0.6,
    },
    "nba": {
        # Basketball has the highest per-player leverage of the major sports:
        # five players, forty minutes, no substitution limits.
        "SUPERSTAR": 7.5,
        "STAR": 4.5,
        "STARTER": 2.0,
        "ROTATION": 0.8,
        "BENCH": 0.3,
    },
    "nhl": {
        "G": 0.7,    # goalies matter, skaters mostly do not
        "C": 0.2,
        "W": 0.15,
        "D": 0.2,
    },
    "mlb": {
        "SP": 0.6,   # starting pitcher dominates; position players barely move a line
        "RP": 0.1,
        "C": 0.15,
        "IF": 0.12,
        "OF": 0.12,
        "DH": 0.1,
    },
    "npb": {
        "SP": 0.6,   # same roster shape as MLB; no NPB-specific injury feed exists to fit this against
        "RP": 0.1,
        "C": 0.15,
        "IF": 0.12,
        "OF": 0.12,
        "DH": 0.1,
    },
}


def position_value(sport: str, position: str | None) -> float:
    """Default point value for a position, 0 when unknown."""
    if not position:
        return 0.0
    table = POSITION_VALUE.get(sport.lower(), {})
    return table.get(position.upper(), 0.0)


def team_injury_points(
    injuries: list[InjuryReport], team: str, sport: str
) -> tuple[float, list[InjuryReport]]:
    """Total expected point impact of a team's absences.

    Impacts are summed with diminishing returns: losing three starters hurts
    less than three times as much as losing one, because replacement level
    rises as usage redistributes and because the market prices multi-injury
    situations more conservatively than additive math implies.
    """
    relevant = [
        inj
        for inj in injuries
        if inj.team.lower() == team.lower() and inj.status != InjuryStatus.ACTIVE
    ]
    if not relevant:
        return 0.0, []

    impacts = []
    for inj in relevant:
        value = inj.point_value or position_value(sport, inj.position)
        impacts.append(value * (1.0 - inj.play_probability))

    impacts.sort(reverse=True)
    total = 0.0
    for i, impact in enumerate(impacts):
        total += impact * (0.82**i)
    return total, relevant


class InjurySignal:
    """Convert availability news into a residual probability shift."""

    name = "injuries"

    def __init__(self, expected_move_fraction: float = 0.85):
        # Fraction of a genuine injury effect the market typically absorbs
        # before we see it. High by design -- assuming the market is slow is
        # how bettors lose to old news.
        self.expected_move_fraction = expected_move_fraction

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        team = ctx.team_for_outcome()
        if team is None or not ctx.injuries:
            return []

        opponent = ctx.event.opponent_of(team)
        own_points, own_reports = team_injury_points(ctx.injuries, team, ctx.sport)
        opp_points, opp_reports = (
            team_injury_points(ctx.injuries, opponent, ctx.sport)
            if opponent
            else (0.0, [])
        )

        # Net effect on this team's spread. Their injuries hurt, the
        # opponent's injuries help.
        net_points = opp_points - own_points
        if abs(net_points) < 0.15:
            return []

        # How much of this the line has already absorbed. Spread moves are
        # signed toward the team; convert the observed move into the same
        # frame as net_points.
        observed = -ctx.line_move if ctx.line_move else 0.0
        residual, credit = residual_after_market_move(net_points, observed)
        if credit <= 0.0:
            return [
                SignalContribution(
                    name=self.name,
                    logit_adjustment=0.0,
                    weight=0.0,
                    rationale=(
                        f"net {net_points:+.1f} pts of availability news, but the line "
                        f"already moved {observed:+.1f} -- fully priced"
                    ),
                    points=net_points,
                )
            ]

        newest = max(
            (r.reported_at for r in own_reports + opp_reports), default=ctx.now
        )
        freshness = recency_credit(newest, ctx.now, half_life_min=180.0)
        lag = book_lag_credit(ctx.hours_to_start)

        # The market absorbs most of a real injury effect; we claim the rest.
        claimable = residual * (1.0 - self.expected_move_fraction * (1.0 - freshness))
        adjustment = points_to_logit(claimable, ctx.market_probability, ctx.sport)
        weight = clamp(freshness * lag, 0.0, 1.0)

        detail = ", ".join(
            f"{r.player} ({r.status.value}{', ' + r.position if r.position else ''})"
            for r in sorted(
                own_reports + opp_reports,
                key=lambda r: -(r.point_value or position_value(ctx.sport, r.position)),
            )[:3]
        )

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=weight,
                rationale=(
                    f"{detail}; net {net_points:+.1f} pts, line has moved "
                    f"{observed:+.1f}, {residual:+.1f} pts still unpriced"
                ),
                points=claimable,
                source="injury report",
                observed_at=newest,
            )
        ]


class QuestionableTagSignal:
    """Value in game-time decisions that the market prices as coin flips.

    When a star is questionable the line sits between the two worlds. If you
    have better information than the market about whether he plays -- a beat
    writer's report, warmup video, a team's historical pattern with the tag
    -- the correct bet is often on the *other* market entirely: the line will
    jump when the news breaks, so the value is in taking the number now.
    """

    name = "questionable_tag"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        team = ctx.team_for_outcome()
        if team is None:
            return []
        gtd = [
            inj
            for inj in ctx.injuries
            if inj.team.lower() == team.lower()
            and inj.status in (InjuryStatus.QUESTIONABLE, InjuryStatus.GAME_TIME_DECISION)
            and (inj.point_value or position_value(ctx.sport, inj.position)) >= 3.0
        ]
        if not gtd:
            return []

        biggest = max(
            gtd, key=lambda r: r.point_value or position_value(ctx.sport, r.position)
        )
        value = biggest.point_value or position_value(ctx.sport, biggest.position)

        # No directional claim -- this flags that the number carries binary
        # risk that Kelly staking should treat as extra variance.
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=0.0,
                weight=0.0,
                rationale=(
                    f"{biggest.player} is {biggest.status.value} and worth ~{value:.1f} pts; "
                    "the price embeds a coin flip, so size down or wait for the news"
                ),
                points=value,
                source="injury report",
                observed_at=biggest.reported_at,
            )
        ]


def rest_adjusted_availability(
    report: InjuryReport, back_to_back: bool, sport: str
) -> float:
    """Adjust play probability for load management.

    NBA teams rest healthy stars on the second night of back-to-backs, and
    the announcement often comes after lines are posted. A star listed as
    questionable on a back-to-back plays materially less often than the tag
    alone suggests.
    """
    base = report.play_probability
    if sport.lower() == "nba" and back_to_back and report.status in (
        InjuryStatus.QUESTIONABLE,
        InjuryStatus.GAME_TIME_DECISION,
    ):
        return base * 0.62
    return base
