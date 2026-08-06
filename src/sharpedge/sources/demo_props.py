"""Synthetic player props and derivative markets.

Generates the rest of the betting menu for the demo slate, with the same
philosophy as the core demo source: the mispricings are *structural* rather
than random, so a screen that finds them has demonstrated something.

Three errors are planted deliberately, and they are the three that occur in
real books:

1. **Ladder inconsistency.** Alternate lines are generated from the anchor
   with a crude linear multiplier instead of the correct distribution. Because
   real counting stats are overdispersed, this misprices the tails in a
   predictable direction -- exactly the error a Poisson-based alt generator
   makes.
2. **Over shading.** Prop overs are priced above their fair value by an amount
   proportional to how lopsidedly the public bets that stat.
3. **Stale props after news.** When a player is ruled out, some books have
   repriced his teammates' props and some have not.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from ..market.props import DEFAULT_OVER_SHARE, PROP_OVER_TICKET_SHARE
from ..market.taxonomy import props_for
from ..models import Event, Market, MarketType, Price
from ..oddsmath import prob_to_american
from ..pricing.distributions import PoissonDist, build, model_for
from .demo import NBA_TEAMS, NFL_TEAMS

# Plausible rosters so props attach to a real depth chart.
ROSTERS: dict[str, list[tuple[str, str, float]]] = {
    # (player, position, usage share)
    "nba": [
        ("A. Brennan", "PG", 0.29),
        ("D. Okafor", "SG", 0.23),
        ("M. Vasquez", "SF", 0.19),
        ("T. Kowalski", "PF", 0.16),
        ("J. Ferreira", "C", 0.13),
    ],
    "nfl": [
        ("R. Delgado", "QB", 0.35),
        ("K. Boateng", "RB", 0.22),
        ("S. Lindqvist", "WR", 0.20),
        ("N. Abadi", "WR", 0.14),
        ("P. Cavanaugh", "TE", 0.09),
    ],
    "mlb": [
        ("H. Tanaka", "SP", 0.40),
        ("L. Moreau", "OF", 0.16),
        ("C. Whitfield", "IF", 0.15),
        ("E. Rosales", "C", 0.15),
        ("B. Ashworth", "IF", 0.14),
    ],
}

# Typical projections by stat, used as the hidden truth the market prices near.
BASE_PROJECTION: dict[str, tuple[float, float]] = {
    "strikeouts": (5.8, 1.6),
    "hits_allowed": (5.2, 1.2),
    "earned_runs": (2.7, 0.8),
    "total_bases": (1.35, 0.35),
    "hits": (0.95, 0.22),
    "points": (18.5, 6.5),
    "rebounds": (6.8, 2.6),
    "assists": (4.6, 2.2),
    "threes_made": (2.1, 0.8),
    "pra": (29.0, 8.0),
    "passing_yards": (245.0, 45.0),
    "passing_tds": (1.7, 0.5),
    "completions": (22.0, 4.0),
    "rushing_yards": (68.0, 22.0),
    "receptions": (4.6, 1.5),
    "receiving_yards": (58.0, 20.0),
    "anytime_td": (0.55, 0.18),
    "shots_on_goal": (2.6, 0.8),
    "saves": (26.0, 5.0),
}

# Which positions plausibly carry which stat.
STAT_POSITIONS: dict[str, set[str]] = {
    "strikeouts": {"SP"}, "hits_allowed": {"SP"}, "earned_runs": {"SP"},
    "total_bases": {"OF", "IF", "C"}, "hits": {"OF", "IF", "C"},
    "points": {"PG", "SG", "SF", "PF", "C"},
    "rebounds": {"SF", "PF", "C"}, "assists": {"PG", "SG", "SF"},
    "threes_made": {"PG", "SG", "SF"}, "pra": {"PG", "SG", "SF", "PF", "C"},
    "passing_yards": {"QB"}, "passing_tds": {"QB"}, "completions": {"QB"},
    "rushing_yards": {"RB", "QB"}, "receptions": {"WR", "TE", "RB"},
    "receiving_yards": {"WR", "TE"}, "anytime_td": {"RB", "WR", "TE"},
}


class DemoPropSource:
    """Adds props and derivative markets to demo events."""

    name = "demo-props"

    def __init__(self, seed: int = 19, stale_rate: float = 0.28, books: list[str] | None = None):
        self.rng = random.Random(seed)
        self.stale_rate = stale_rate
        # Props are posted by fewer books than sides, which is the point.
        self.books = books or [
            "pinnacle", "draftkings", "fanduel", "betmgm", "caesars",
            "espnbet", "betrivers", "hardrock", "fanatics",
        ]

    def augment(self, events: list[Event]) -> list[Event]:
        """Attach props and derivatives to each event, in place."""
        now = datetime.now(timezone.utc)
        for event in events:
            self._attach_depth_chart(event)
            event.markets.extend(self._derivatives(event, now))
            event.markets.extend(self._props(event, now))
        return events

    # -- depth chart -------------------------------------------------------

    def _attach_depth_chart(self, event: Event) -> None:
        roster = ROSTERS.get(event.sport, ROSTERS["nba"])
        depth: dict[str, dict] = {}
        for team in (event.home_team, event.away_team):
            suffix = team.split()[-1][:3].upper()
            depth[team] = {
                f"{name} ({suffix})": {"position": position, "usage": usage}
                for name, position, usage in roster
            }
        event.metadata["depth_chart"] = depth

        # Context the prop signals read.
        if event.sport == "nba":
            event.metadata["projected_pace"] = round(self.rng.uniform(96, 104), 1)
            event.metadata["league_pace"] = 99.5
        if event.sport == "mlb":
            event.metadata["umpire_k_factor"] = round(self.rng.uniform(0.92, 1.09), 3)
            event.metadata["park_factor"] = round(self.rng.uniform(0.88, 1.14), 3)
            event.metadata["expected_innings"] = round(self.rng.uniform(4.4, 6.3), 1)

    # -- derivatives -------------------------------------------------------

    def _derivatives(self, event: Event, now: datetime) -> list[Market]:
        """First-half and first-quarter markets, priced off the full game."""
        spread_market = event.market(MarketType.SPREAD)
        total_market = event.market(MarketType.TOTAL)
        if spread_market is None or total_market is None:
            return []

        home_line = next(
            (p.line for p in spread_market.prices_for(event.home_team) if p.line is not None),
            None,
        )
        game_total = next(
            (p.line for p in total_market.prices_for("Over") if p.line is not None), None
        )
        if home_line is None or game_total is None:
            return []

        out: list[Market] = []

        # First halves carry a bit more than half the game: teams score more
        # before adjustments and fatigue.
        for market_type, spread_share, total_share in (
            (MarketType.FIRST_HALF_SPREAD, 0.55, None),
            (MarketType.FIRST_HALF_TOTAL, None, 0.52),
            (MarketType.FIRST_QUARTER, 0.28, None),
        ):
            if market_type == MarketType.FIRST_QUARTER and event.sport not in ("nba", "nfl"):
                continue
            if spread_share is not None:
                line = round(home_line * spread_share * 2) / 2
                out.append(
                    self._two_way(
                        event, market_type,
                        event.home_team, event.away_team,
                        0.5, line, -line, now,
                        hold=0.05, books=self.books,
                    )
                )
            else:
                line = round(game_total * total_share * 2) / 2
                out.append(
                    self._two_way(
                        event, market_type, "Over", "Under",
                        0.5, line, line, now, hold=0.052, books=self.books,
                    )
                )

        # Team totals, derived from the side and total. Books compute these
        # mechanically, and the arithmetic often does not reconcile.
        for team, sign in ((event.home_team, -1.0), (event.away_team, 1.0)):
            implied = game_total / 2.0 + sign * home_line / 2.0
            line = round(implied * 2) / 2
            market = self._two_way(
                event, MarketType.TEAM_TOTAL, "Over", "Under",
                0.5, line, line, now, hold=0.055, books=self.books[:7],
            )
            market.subject = team
            out.append(market)

        return out

    # -- props -------------------------------------------------------------

    def _props(self, event: Event, now: datetime) -> list[Market]:
        profiles = props_for(event.sport)
        if not profiles:
            return []

        roster = ROSTERS.get(event.sport, [])
        out: list[Market] = []

        for team in (event.home_team, event.away_team):
            suffix = team.split()[-1][:3].upper()
            for name, position, _usage in roster:
                player = f"{name} ({suffix})"
                for profile in profiles:
                    allowed = STAT_POSITIONS.get(profile.stat)
                    if allowed and position not in allowed:
                        continue
                    if self.rng.random() > 0.55:
                        continue
                    market = self._prop_market(event, player, profile.stat, now)
                    if market is not None:
                        out.append(market)
        return out

    def _prop_market(
        self, event: Event, player: str, stat: str, now: datetime
    ) -> Market | None:
        base = BASE_PROJECTION.get(stat)
        if base is None:
            return None
        mean, spread = base
        true_mean = max(0.15, self.rng.gauss(mean, spread))

        model = model_for(stat)
        dist = build(stat, true_mean)

        # Anchor line: the half-number nearest the projection, as books post.
        anchor = (
            round(true_mean - 0.5) + 0.5
            if model.integer
            else round(true_mean / 5.0) * 5.0 - 0.5
        )
        anchor = max(anchor, 0.5)

        over_share = PROP_OVER_TICKET_SHARE.get(stat, DEFAULT_OVER_SHARE)
        shade = (over_share - 0.5) * 0.055     # over priced above fair
        hold = 0.070 + self.rng.uniform(0, 0.030)

        # Books post the anchor plus a few alternates.
        step = 1.0 if model.integer else (10.0 if anchor >= 60 else 5.0)
        lines = [anchor] + [
            anchor + i * step for i in (-2, -1, 1, 2) if anchor + i * step > 0
        ]

        prices: list[Price] = []
        posting = [b for b in self.books if self.rng.random() < 0.78]
        if len(posting) < 3:
            posting = self.books[:4]

        for book in posting:
            stale = self.rng.random() < self.stale_rate
            # Only some books generate alternates badly; the rest price the
            # whole ladder coherently and should yield no findings at all.
            sloppy_alts = self.rng.random() < 0.45
            book_mean = true_mean * (1.0 + self.rng.gauss(0, 0.035))
            if stale:
                # A book that has not repriced after news.
                book_mean *= self.rng.choice([0.90, 0.93, 1.07, 1.10])
            book_dist = build(stat, book_mean)

            for line in lines:
                is_anchor = abs(line - anchor) < 1e-9
                # Only some books post the full alternate ladder.
                if not is_anchor and self.rng.random() > 0.5:
                    continue

                if is_anchor:
                    p_over = book_dist.sf(line)
                elif sloppy_alts and model.integer:
                    # THE PLANTED ERROR for counting stats, and it is the
                    # realistic one: the book generates alternates from a
                    # Poisson with the same mean. Poisson assumes variance
                    # equals the mean, but real counting stats are
                    # overdispersed, so this understates both tails. Subtle
                    # near the anchor and material several rungs out, which is
                    # exactly how it shows up in real books.
                    # Blended rather than fully Poisson: real books are
                    # partly wrong, not completely wrong, and a demo that
                    # advertises 40% edges teaches the wrong expectations.
                    correct = book_dist.sf(line)
                    p_over = 0.5 * PoissonDist(mean=book_mean).sf(line) + 0.5 * correct
                elif sloppy_alts:
                    # For continuous stats a Poisson is meaningless, so the
                    # realistic error is a too-narrow spread: the book prices
                    # alternates off a tighter distribution than reality,
                    # which makes both tails too expensive.
                    narrow = build(stat, book_mean)
                    if hasattr(narrow, "cv"):
                        narrow = type(narrow)(mean=book_mean, cv=narrow.cv * 0.88)
                    p_over = 0.5 * narrow.sf(line) + 0.5 * book_dist.sf(line)
                else:
                    p_over = book_dist.sf(line)

                p_over = min(max(p_over + shade, 0.02), 0.98)
                raw_over = p_over * (1.0 + hold)
                raw_under = (1.0 - p_over) * (1.0 + hold)

                age = timedelta(minutes=self.rng.uniform(0, 20) + (55 if stale else 0))
                for outcome, raw in (("Over", raw_over), ("Under", raw_under)):
                    prices.append(
                        Price(
                            book=book,
                            outcome=outcome,
                            american=round(
                                prob_to_american(min(max(raw, 0.02), 0.975)) / 5
                            ) * 5,
                            line=line,
                            timestamp=now - age,
                        )
                    )

        if len({p.book for p in prices}) < 3:
            return None

        return Market(
            event_id=event.event_id,
            market_type=MarketType.PLAYER_PROP,
            outcomes=["Over", "Under"],
            prices=prices,
            subject=player,
            metadata={"stat": stat, "true_mean": round(true_mean, 3)},
        )

    # -- shared ------------------------------------------------------------

    def _two_way(
        self, event: Event, market_type: MarketType,
        outcome_a: str, outcome_b: str, p_a: float,
        line_a: float | None, line_b: float | None,
        now: datetime, hold: float, books: list[str],
    ) -> Market:
        prices: list[Price] = []
        for book in books:
            noise = self.rng.gauss(0, 0.012)
            pa = min(max(p_a + noise, 0.05), 0.95)
            raw_a = pa * (1.0 + hold)
            raw_b = (1.0 - pa) * (1.0 + hold)
            age = timedelta(minutes=self.rng.uniform(0, 25))
            for outcome, raw, line in (
                (outcome_a, raw_a, line_a),
                (outcome_b, raw_b, line_b),
            ):
                prices.append(
                    Price(
                        book=book,
                        outcome=outcome,
                        american=round(prob_to_american(min(max(raw, 0.03), 0.97)) / 5) * 5,
                        line=line,
                        timestamp=now - age,
                    )
                )
        return Market(
            event_id=event.event_id,
            market_type=market_type,
            outcomes=[outcome_a, outcome_b],
            prices=prices,
        )
