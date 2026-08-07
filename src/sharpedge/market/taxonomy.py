"""The full market tree, and how hard each market is to beat.

The central claim of this module, and the reason it exists: **market
efficiency varies enormously across bet types, and the variation is
structural rather than random.**

A book's NFL side is priced by its best people, moved by seven-figure daily
handle, defended with $50,000 limits, and attacked continuously by every
syndicate in the world. It is close to unbeatable.

That same book's "Nikola Jokic assists over 8.5" is priced by an automated
model off a projection feed, carries a 9% hold, accepts $250, and is attacked
by almost nobody. When Jamal Murray is ruled out an hour before tip, the side
moves within seconds and the assist prop moves in minutes -- if at all.

So this table drives real behavior in the pipeline:

* ``efficiency`` sets how much the model is allowed to disagree with the
  market. On core markets it defers almost completely; on props it is
  permitted a real opinion.
* ``typical_hold`` sets the juice threshold above which a market is not worth
  playing at all.
* ``typical_limit`` is the honest ceiling on what a bet is worth finding. An
  8% edge on a $250 prop is $20.

The trade-off is stated plainly rather than hidden: props are softer *and*
lower-limit. The edges are bigger and the dollars per edge are smaller.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import MarketType


@dataclass(frozen=True)
class MarketProfile:
    """How a market behaves, and how much to trust its price."""

    market_type: MarketType
    label: str
    # 0..1. How close to unbeatable this market is. Feeds directly into how
    # much the signal engine is allowed to move the number.
    efficiency: float
    typical_hold: float
    typical_limit: float
    # How many books typically post it. Thin coverage means a weaker
    # consensus and a wider error bar.
    typical_books: int
    stat: str | None = None
    note: str = ""

    @property
    def market_trust(self) -> float:
        """How far the model must defer to the market here.

        Core markets get near-total deference. Props get room to disagree,
        because the price is often a machine's guess rather than a number
        that survived being attacked.
        """
        return min(0.90, max(0.25, self.efficiency))

    @property
    def min_edge_required(self) -> float:
        """EV floor for this market.

        Scales with hold and thin coverage. A 2% edge on a market with a 9%
        hold priced by three books is far more likely to be estimation error
        than a 2% edge on a six-book, 4.5%-hold side.
        """
        base = 0.01 + max(0.0, self.typical_hold - 0.045) * 0.9
        if self.typical_books < 5:
            base += 0.012
        return round(base, 4)


# ---------------------------------------------------------------------------
# Core and derivative markets
# ---------------------------------------------------------------------------

CORE_PROFILES: dict[MarketType, MarketProfile] = {
    MarketType.SPREAD: MarketProfile(
        MarketType.SPREAD, "Point spread", 0.90, 0.045, 25_000, 14,
        note="the most efficiently priced market in sports",
    ),
    MarketType.MONEYLINE: MarketProfile(
        MarketType.MONEYLINE, "Moneyline", 0.88, 0.042, 25_000, 14,
    ),
    MarketType.TOTAL: MarketProfile(
        MarketType.TOTAL, "Game total", 0.87, 0.045, 20_000, 14,
    ),
    MarketType.ALTERNATE_SPREAD: MarketProfile(
        MarketType.ALTERNATE_SPREAD, "Alternate spread", 0.72, 0.060, 3_000, 7,
        note="generated off the main line, often with a lazy multiplier",
    ),
    MarketType.ALTERNATE_TOTAL: MarketProfile(
        MarketType.ALTERNATE_TOTAL, "Alternate total", 0.72, 0.060, 3_000, 7,
    ),
    MarketType.TEAM_TOTAL: MarketProfile(
        MarketType.TEAM_TOTAL, "Team total", 0.68, 0.055, 2_500, 8,
        note="derived from side and total; inconsistencies between the three are common",
    ),
    MarketType.FIRST_HALF: MarketProfile(
        MarketType.FIRST_HALF, "First half", 0.74, 0.050, 5_000, 9,
    ),
    MarketType.FIRST_HALF_SPREAD: MarketProfile(
        MarketType.FIRST_HALF_SPREAD, "First half spread", 0.74, 0.050, 5_000, 9,
    ),
    MarketType.FIRST_HALF_TOTAL: MarketProfile(
        MarketType.FIRST_HALF_TOTAL, "First half total", 0.72, 0.052, 4_000, 9,
    ),
    MarketType.SECOND_HALF: MarketProfile(
        MarketType.SECOND_HALF, "Second half", 0.70, 0.055, 3_000, 6,
    ),
    MarketType.FIRST_QUARTER: MarketProfile(
        MarketType.FIRST_QUARTER, "First quarter", 0.62, 0.060, 1_500, 6,
        note="small samples make these genuinely hard to price",
    ),
    MarketType.QUARTER: MarketProfile(
        MarketType.QUARTER, "Quarter", 0.58, 0.065, 1_000, 4,
    ),
    MarketType.FIRST_PERIOD: MarketProfile(
        MarketType.FIRST_PERIOD, "First period", 0.60, 0.062, 1_500, 5,
    ),
    MarketType.FIRST_FIVE: MarketProfile(
        MarketType.FIRST_FIVE, "First five innings", 0.78, 0.048, 5_000, 8,
        note="removes bullpen variance, so it is a cleaner bet on the starters",
    ),
    MarketType.RACE_TO: MarketProfile(
        MarketType.RACE_TO, "Race to X points", 0.55, 0.070, 500, 3,
    ),
    MarketType.BOTH_TEAMS_SCORE: MarketProfile(
        MarketType.BOTH_TEAMS_SCORE, "Both teams to score", 0.62, 0.065, 1_000, 5,
    ),
    MarketType.MARGIN_BUCKET: MarketProfile(
        MarketType.MARGIN_BUCKET, "Winning margin", 0.50, 0.110, 500, 3,
        note="very high hold; rarely worth playing without a large edge",
    ),
    MarketType.FIRST_SCORE: MarketProfile(
        MarketType.FIRST_SCORE, "First to score", 0.55, 0.075, 500, 3,
    ),
}


# ---------------------------------------------------------------------------
# Player props by sport
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PropProfile:
    """A specific player prop market."""

    key: str
    label: str
    stat: str
    sport: str
    efficiency: float
    typical_hold: float
    typical_limit: float
    typical_books: int
    note: str = ""

    def as_market_profile(self) -> MarketProfile:
        return MarketProfile(
            MarketType.PLAYER_PROP,
            self.label,
            self.efficiency,
            self.typical_hold,
            self.typical_limit,
            self.typical_books,
            stat=self.stat,
            note=self.note,
        )


# Efficiency ratings reflect how much attention each prop actually receives.
# Strikeouts and passing yards are the most heavily bet props and are priced
# accordingly; obscure counting stats are not.
PROP_PROFILES: list[PropProfile] = [
    # -- MLB ---------------------------------------------------------------
    PropProfile("mlb_strikeouts", "Pitcher strikeouts", "strikeouts", "mlb",
                0.66, 0.075, 2_500, 9,
                "the most-bet prop in baseball, so the anchor line is decent -- "
                "but the alternates hanging off it usually are not"),
    PropProfile("mlb_hits_allowed", "Hits allowed", "hits_allowed", "mlb",
                0.52, 0.085, 1_000, 5),
    PropProfile("mlb_earned_runs", "Earned runs allowed", "earned_runs", "mlb",
                0.50, 0.090, 750, 4,
                "extremely heavy tail; books routinely misprice the alternates"),
    PropProfile("mlb_outs", "Outs recorded", "outs_recorded", "mlb",
                0.55, 0.080, 1_000, 5),
    PropProfile("mlb_total_bases", "Total bases", "total_bases", "mlb",
                0.54, 0.088, 1_000, 7),
    PropProfile("mlb_hits", "Batter hits", "hits", "mlb", 0.56, 0.085, 1_000, 7),
    PropProfile("mlb_home_runs", "Home run", "home_runs", "mlb",
                0.48, 0.130, 500, 8,
                "enormous hold; the public loves it, which is exactly why"),
    PropProfile("mlb_rbis", "RBIs", "rbis", "mlb", 0.50, 0.095, 750, 6),
    PropProfile("mlb_runs", "Runs scored", "runs_scored", "mlb", 0.50, 0.095, 750, 6),
    # -- NFL ---------------------------------------------------------------
    PropProfile("nfl_pass_yards", "Passing yards", "passing_yards", "nfl",
                0.68, 0.070, 3_000, 10),
    PropProfile("nfl_pass_tds", "Passing TDs", "passing_tds", "nfl",
                0.56, 0.090, 1_000, 8),
    PropProfile("nfl_completions", "Completions", "completions", "nfl",
                0.58, 0.080, 1_500, 7),
    PropProfile("nfl_rush_yards", "Rushing yards", "rushing_yards", "nfl",
                0.62, 0.075, 2_000, 9),
    PropProfile("nfl_receptions", "Receptions", "receptions", "nfl",
                0.60, 0.078, 2_000, 9,
                "moves hard on target-share news and is slow to reprice"),
    PropProfile("nfl_rec_yards", "Receiving yards", "receiving_yards", "nfl",
                0.58, 0.080, 2_000, 9),
    PropProfile("nfl_longest_rec", "Longest reception", "longest_reception", "nfl",
                0.44, 0.105, 500, 4,
                "priced badly because the distribution is an extreme-value problem"),
    PropProfile("nfl_anytime_td", "Anytime touchdown", "anytime_td", "nfl",
                0.54, 0.115, 1_000, 10,
                "the most popular prop in football and among the juiciest"),
    PropProfile("nfl_tackles", "Tackles + assists", "tackles_assists", "nfl",
                0.46, 0.095, 500, 4,
                "thin coverage, weak models, real edges"),
    # -- NBA ---------------------------------------------------------------
    PropProfile("nba_points", "Points", "points", "nba", 0.66, 0.072, 2_500, 10),
    PropProfile("nba_rebounds", "Rebounds", "rebounds", "nba", 0.58, 0.080, 1_500, 9),
    PropProfile("nba_assists", "Assists", "assists", "nba", 0.56, 0.082, 1_500, 9,
                "most sensitive stat to a teammate's absence"),
    PropProfile("nba_threes", "Three-pointers made", "threes_made", "nba",
                0.52, 0.090, 1_000, 8),
    PropProfile("nba_pra", "Points + rebounds + assists", "pra", "nba",
                0.54, 0.085, 1_000, 7),
    PropProfile("nba_steals", "Steals", "steals", "nba", 0.42, 0.110, 250, 4,
                "tiny samples, weak pricing, but limits make it barely worth it"),
    PropProfile("nba_blocks", "Blocks", "blocks", "nba", 0.42, 0.110, 250, 4),
    # -- NHL ---------------------------------------------------------------
    PropProfile("nhl_shots", "Shots on goal", "shots_on_goal", "nhl",
                0.54, 0.085, 1_000, 7),
    PropProfile("nhl_saves", "Goalie saves", "saves", "nhl", 0.58, 0.080, 1_500, 7,
                "correlated with the game total in a way books underprice"),
    PropProfile("nhl_points", "Player points", "player_points", "nhl",
                0.50, 0.095, 750, 6),
    # -- WNBA ----------------------------------------------------------------
    # Same stats as the NBA, priced far worse: fewer books post it, fewer
    # sharp bettors correct it, and limits run a fraction of the NBA's.
    PropProfile("wnba_points", "Points", "points", "wnba", 0.52, 0.090, 750, 6),
    PropProfile("wnba_rebounds", "Rebounds", "rebounds", "wnba", 0.46, 0.095, 500, 5),
    PropProfile("wnba_assists", "Assists", "assists", "wnba", 0.44, 0.098, 500, 5,
                "thin coverage; a starter's absence moves this hard and slowly"),
    PropProfile("wnba_threes", "Three-pointers made", "threes_made", "wnba",
                0.42, 0.105, 400, 5),
    PropProfile("wnba_pra", "Points + rebounds + assists", "pra", "wnba",
                0.44, 0.100, 400, 4),
    PropProfile("wnba_steals", "Steals", "steals", "wnba", 0.34, 0.130, 200, 3,
                "barely covered; real edges, tiny stakes"),
    PropProfile("wnba_blocks", "Blocks", "blocks", "wnba", 0.34, 0.130, 200, 3),
    # -- Tennis --------------------------------------------------------------
    # Posted mainly for tour-level (ATP/WTA) main-draw matches, by a handful
    # of books, off models thinner than the ones pricing the moneyline.
    PropProfile("tennis_aces", "Total aces", "aces", "tennis",
                0.48, 0.100, 400, 5,
                "swings hard on surface and a player's own serve-speed news"),
    PropProfile("tennis_double_faults", "Total double faults", "double_faults", "tennis",
                0.40, 0.115, 250, 4,
                "thin coverage, high variance -- a player's off day means nothing structural"),
]

PROPS_BY_SPORT: dict[str, list[PropProfile]] = {}
for _p in PROP_PROFILES:
    PROPS_BY_SPORT.setdefault(_p.sport, []).append(_p)

PROPS_BY_KEY: dict[str, PropProfile] = {p.key: p for p in PROP_PROFILES}

# Keyed by (sport, stat), not stat alone. Several sports share stat names --
# "points", "rebounds", "assists" mean one thing for the NBA and a
# structurally softer, thinner-covered thing for the WNBA. A stat-only key
# would let whichever sport's entry loads last silently overwrite the other's
# efficiency and limit numbers for every sport that shares the name.
PROPS_BY_SPORT_STAT: dict[tuple[str, str], PropProfile] = {
    (p.sport, p.stat): p for p in PROP_PROFILES
}

# Stat-only fallback for callers that genuinely have no sport context. Kept
# deliberately last-write-wins so behavior stays obvious, but every real call
# site in this codebase passes a sport and should use PROPS_BY_SPORT_STAT.
PROPS_BY_STAT: dict[str, PropProfile] = {p.stat: p for p in PROP_PROFILES}


# ---------------------------------------------------------------------------
# Which markets exist per sport
# ---------------------------------------------------------------------------

SPORT_MARKETS: dict[str, list[MarketType]] = {
    "nfl": [
        MarketType.SPREAD, MarketType.MONEYLINE, MarketType.TOTAL,
        MarketType.TEAM_TOTAL, MarketType.ALTERNATE_SPREAD,
        MarketType.ALTERNATE_TOTAL, MarketType.FIRST_HALF_SPREAD,
        MarketType.FIRST_HALF_TOTAL, MarketType.FIRST_QUARTER,
        MarketType.PLAYER_PROP,
    ],
    "ncaaf": [
        MarketType.SPREAD, MarketType.MONEYLINE, MarketType.TOTAL,
        MarketType.TEAM_TOTAL, MarketType.FIRST_HALF_SPREAD,
        MarketType.FIRST_HALF_TOTAL,
    ],
    "nba": [
        MarketType.SPREAD, MarketType.MONEYLINE, MarketType.TOTAL,
        MarketType.TEAM_TOTAL, MarketType.ALTERNATE_SPREAD,
        MarketType.ALTERNATE_TOTAL, MarketType.FIRST_HALF_SPREAD,
        MarketType.FIRST_HALF_TOTAL, MarketType.FIRST_QUARTER,
        MarketType.PLAYER_PROP,
    ],
    "ncaab": [
        MarketType.SPREAD, MarketType.MONEYLINE, MarketType.TOTAL,
        MarketType.FIRST_HALF_SPREAD, MarketType.FIRST_HALF_TOTAL,
    ],
    "mlb": [
        MarketType.MONEYLINE, MarketType.SPREAD, MarketType.TOTAL,
        MarketType.TEAM_TOTAL, MarketType.FIRST_FIVE, MarketType.PLAYER_PROP,
    ],
    "npb": [
        # No team total, first-five, or player props: The Odds API only
        # lists core h2h/spreads/totals for baseball_npb.
        MarketType.MONEYLINE, MarketType.SPREAD, MarketType.TOTAL,
    ],
    "nhl": [
        MarketType.MONEYLINE, MarketType.SPREAD, MarketType.TOTAL,
        MarketType.TEAM_TOTAL, MarketType.FIRST_PERIOD, MarketType.PLAYER_PROP,
    ],
    "wnba": [
        # No alternate lines or quarters listed: real books cover the WNBA
        # far thinner than the NBA, and claiming markets that mostly are not
        # actually posted would just generate skips.
        MarketType.SPREAD, MarketType.MONEYLINE, MarketType.TOTAL,
        MarketType.TEAM_TOTAL, MarketType.FIRST_HALF_SPREAD,
        MarketType.FIRST_HALF_TOTAL, MarketType.PLAYER_PROP,
    ],
    "tennis": [
        # No team total, no halves -- tennis has no such thing as a "team,"
        # let alone a game/set split priced the way a football half is.
        # SPREAD here means the games-handicap line (e.g. -3.5 games); TOTAL
        # means total games in the match.
        MarketType.MONEYLINE, MarketType.SPREAD, MarketType.TOTAL,
        MarketType.PLAYER_PROP,
    ],
}


def profile_for(
    market_type: MarketType, stat: str | None = None, sport: str | None = None
) -> MarketProfile:
    """Look up how a market behaves, defaulting conservatively.

    Pass ``sport`` whenever it is available. Several sports share stat names
    -- "points" means something structurally different for the NBA (0.66
    efficiency, $2,500 limit) than for the WNBA (0.52, $750). Without a sport,
    the lookup falls back to whichever sport's profile happens to be
    registered last, which is a real bug waiting to misprice one of the two.
    """
    if market_type.is_prop and stat:
        key = stat.lower().replace(" ", "_")
        prop = None
        if sport:
            prop = PROPS_BY_SPORT_STAT.get((sport.lower(), key))
        if prop is None:
            prop = PROPS_BY_STAT.get(key)
        if prop:
            return prop.as_market_profile()
    profile = CORE_PROFILES.get(market_type)
    if profile:
        return profile
    return MarketProfile(
        market_type, market_type.value.replace("_", " ").title(),
        efficiency=0.60, typical_hold=0.080, typical_limit=500,
        typical_books=4, stat=stat,
        note="unprofiled market, treated conservatively",
    )


def props_for(sport: str) -> list[PropProfile]:
    """Every player prop the engine knows for a sport."""
    return PROPS_BY_SPORT.get(sport.lower(), [])


def markets_for(sport: str) -> list[MarketType]:
    """Every market type worth scanning for a sport."""
    return SPORT_MARKETS.get(
        sport.lower(),
        [MarketType.SPREAD, MarketType.MONEYLINE, MarketType.TOTAL],
    )


def softest_markets(limit: int = 10) -> list[MarketProfile]:
    """Markets ranked by how poorly they tend to be priced.

    Useful for deciding where to point limited data budget. Note that the
    softest markets are also the lowest-limit ones, so this list is where the
    *percentage* edges are, not where the money is.
    """
    everything = list(CORE_PROFILES.values()) + [
        p.as_market_profile() for p in PROP_PROFILES
    ]
    return sorted(everything, key=lambda p: p.efficiency)[:limit]


def expected_value_ceiling(profile: MarketProfile, edge: float) -> float:
    """Dollar ceiling on an edge, given the market's realistic limit.

    The number that keeps prop hunting honest. A 10% edge sounds enormous
    until you notice the book takes $250 on it.
    """
    return profile.typical_limit * edge
