"""Core data types shared across the pipeline.

These are plain dataclasses with no I/O so that every stage -- ingestion,
pricing, signals, staking, reporting -- agrees on the same vocabulary and can
be tested in isolation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .oddsmath import american_to_decimal, decimal_to_american, decimal_to_prob


def utcnow() -> datetime:
    """Timezone-aware current time. Never use naive datetimes here."""
    return datetime.now(timezone.utc)


class MarketType(str, Enum):
    """Every market the engine knows how to price.

    Ordered roughly by how efficiently the market prices them. The game
    markets at the top are the most heavily bet and hardest to beat; the
    props and derivatives further down are priced by smaller teams, defended
    with smaller limits, and corrected by far fewer sharp bettors -- which is
    where the exploitable pricing errors concentrate.
    """

    # -- Core game markets: efficient, high limits, hard to beat -----------
    MONEYLINE = "moneyline"
    SPREAD = "spread"
    TOTAL = "total"
    TEAM_TOTAL = "team_total"
    ALTERNATE_SPREAD = "alternate_spread"
    ALTERNATE_TOTAL = "alternate_total"

    # -- Derivatives: priced off the full game, often mechanically --------
    FIRST_HALF = "first_half"
    SECOND_HALF = "second_half"
    FIRST_QUARTER = "first_quarter"
    QUARTER = "quarter"
    FIRST_PERIOD = "first_period"
    FIRST_FIVE = "first_five"          # MLB, first five innings
    FIRST_HALF_SPREAD = "first_half_spread"
    FIRST_HALF_TOTAL = "first_half_total"

    # -- Player props: the softest markets in the book --------------------
    PLAYER_PROP = "player_prop"
    ALTERNATE_PLAYER_PROP = "alternate_player_prop"

    # -- Game props and exotics -------------------------------------------
    GAME_PROP = "game_prop"
    RACE_TO = "race_to"
    BOTH_TEAMS_SCORE = "both_teams_score"
    MARGIN_BUCKET = "margin_bucket"
    FIRST_SCORE = "first_score"

    @property
    def is_prop(self) -> bool:
        return self in (
            MarketType.PLAYER_PROP,
            MarketType.ALTERNATE_PLAYER_PROP,
            MarketType.GAME_PROP,
        )

    @property
    def is_derivative(self) -> bool:
        return self in (
            MarketType.FIRST_HALF,
            MarketType.SECOND_HALF,
            MarketType.FIRST_QUARTER,
            MarketType.QUARTER,
            MarketType.FIRST_PERIOD,
            MarketType.FIRST_FIVE,
            MarketType.FIRST_HALF_SPREAD,
            MarketType.FIRST_HALF_TOTAL,
        )

    @property
    def is_core(self) -> bool:
        return self in (
            MarketType.MONEYLINE,
            MarketType.SPREAD,
            MarketType.TOTAL,
        )

    @property
    def has_line(self) -> bool:
        """Whether prices in this market are attached to a number."""
        return self not in (
            MarketType.MONEYLINE,
            MarketType.BOTH_TEAMS_SCORE,
            MarketType.FIRST_SCORE,
        )

    @property
    def is_spread_like(self) -> bool:
        """Whether the line is a margin (positive means getting points)."""
        return self in (
            MarketType.SPREAD,
            MarketType.ALTERNATE_SPREAD,
            MarketType.FIRST_HALF_SPREAD,
        )

    @property
    def is_total_like(self) -> bool:
        """Whether the line is a scoring threshold with Over/Under outcomes."""
        return self in (
            MarketType.TOTAL,
            MarketType.ALTERNATE_TOTAL,
            MarketType.TEAM_TOTAL,
            MarketType.FIRST_HALF_TOTAL,
        )


class BookTier(str, Enum):
    """How much a book's price tells you about the true probability.

    The distinction drives everything: you learn the number from sharp books
    and you place the bet at soft ones. A price that looks like an edge but
    only exists at a market maker is usually not an edge, it is your model
    being wrong.
    """

    MARKET_MAKER = "market_maker"   # Pinnacle, Circa: low margin, high limits
    EXCHANGE = "exchange"           # Betfair, Prophet X: real two-sided liquidity
    RETAIL_SHARP = "retail_sharp"   # DraftKings, FanDuel: fast, big, still shaded
    RETAIL = "retail"               # BetMGM, Caesars: slower to move
    SOFT = "soft"                   # ESPN Bet, Fanatics: slowest, where edges live


class BetStatus(str, Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    PUSHED = "pushed"
    VOIDED = "voided"
    CASHED_OUT = "cashed_out"


class Confidence(str, Enum):
    """Tier assigned to a recommendation. Drives stake multipliers."""

    A = "A"  # large, well-supported edge; full fractional Kelly
    B = "B"  # solid edge, some uncertainty; reduced stake
    C = "C"  # marginal or thin; minimum stake or watchlist only
    PASS = "PASS"


@dataclass(frozen=True)
class Book:
    """A sportsbook and how much its opinion is worth."""

    key: str
    name: str
    tier: BookTier
    # How informative this book's no-vig price is about the truth, 0..1.
    sharpness: float
    # Typical accepted stake in dollars. High limits mean the number has been
    # defended with real money, which is the whole reason to trust it.
    max_limit: float
    # Whether we can actually place bets here.
    bettable: bool = True
    # Books that copy a market maker rather than pricing independently should
    # not be counted as extra evidence for consensus.
    follows: str | None = None

    @property
    def is_sharp(self) -> bool:
        return self.tier in (BookTier.MARKET_MAKER, BookTier.EXCHANGE)


@dataclass
class Price:
    """A single posted price at a single book at a point in time."""

    book: str
    outcome: str
    american: float
    line: float | None = None          # spread or total; None for moneylines
    timestamp: datetime = field(default_factory=utcnow)
    limit: float | None = None         # accepted stake if the book publishes it
    deep_link: str | None = None

    @property
    def decimal(self) -> float:
        return american_to_decimal(self.american)

    @property
    def implied(self) -> float:
        """Implied probability including vig."""
        return decimal_to_prob(self.decimal)

    def __repr__(self) -> str:  # pragma: no cover - display only
        line = "" if self.line is None else f" {self.line:+g}"
        return f"<Price {self.book} {self.outcome}{line} {self.american:+.0f}>"


@dataclass
class Market:
    """One market for one event: all books' prices for the same set of outcomes."""

    event_id: str
    market_type: MarketType
    outcomes: list[str]
    prices: list[Price] = field(default_factory=list)
    # Player prop markets carry the subject so signals can match on them.
    subject: str | None = None
    # Free-form market detail. Props use ``stat`` (e.g. "strikeouts") and
    # ``position``; derivatives use ``period``.
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def stat(self) -> str | None:
        return self.metadata.get("stat")

    def prices_for(self, outcome: str) -> list[Price]:
        return [p for p in self.prices if p.outcome == outcome]

    def by_book(self, book: str) -> list[Price]:
        return [p for p in self.prices if p.book == book]

    def books(self) -> list[str]:
        seen: list[str] = []
        for p in self.prices:
            if p.book not in seen:
                seen.append(p.book)
        return seen

    def complete_at(self, book: str) -> bool:
        """True if this book has posted a price for every outcome.

        Vig can only be removed from a complete market -- half a market tells
        you nothing about the book's true probability.
        """
        posted = {p.outcome for p in self.by_book(book)}
        return all(o in posted for o in self.outcomes)

    def best_price(self, outcome: str, bettable_books: set[str] | None = None) -> Price | None:
        """Highest payout available for an outcome, which is where you bet it."""
        candidates = [
            p
            for p in self.prices_for(outcome)
            if bettable_books is None or p.book in bettable_books
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.decimal)


@dataclass
class Event:
    """A game, with every market we have prices for."""

    event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    start_time: datetime
    markets: list[Market] = field(default_factory=list)
    venue: str | None = None
    neutral_site: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"{self.away_team} @ {self.home_team}"

    def market(self, market_type: MarketType) -> Market | None:
        for m in self.markets:
            if m.market_type == market_type:
                return m
        return None

    def hours_to_start(self, now: datetime | None = None) -> float:
        now = now or utcnow()
        return (self.start_time - now).total_seconds() / 3600.0

    def involves(self, team: str) -> bool:
        needle = team.lower()
        return needle in self.home_team.lower() or needle in self.away_team.lower()

    def opponent_of(self, team: str) -> str | None:
        if team == self.home_team:
            return self.away_team
        if team == self.away_team:
            return self.home_team
        return None


@dataclass
class FairPrice:
    """What the market, taken as a whole, believes about one outcome.

    ``probability`` is the sharp-weighted consensus after vig removal.
    ``sigma_logit`` is the disagreement between books measured in log-odds,
    and it is the honest uncertainty estimate: when books disagree, the
    consensus deserves less trust and stakes should shrink.
    """

    outcome: str
    probability: float
    sigma_logit: float
    n_books: int
    n_sharp_books: int
    sharp_probability: float | None = None
    retail_probability: float | None = None
    consensus_line: float | None = None
    market_hold: float | None = None
    # Positive means retail books price this outcome higher than sharp books
    # do, i.e. it is the popular side and is being shaded.
    retail_bias: float = 0.0

    @property
    def fair_american(self) -> float:
        return decimal_to_american(1.0 / self.probability)


@dataclass
class SignalContribution:
    """One reason the model disagrees with the market.

    Adjustments are expressed in log-odds so they compose additively and
    cannot push a probability outside (0, 1). ``weight`` is how much of the
    raw adjustment survives -- a signal the market has already priced in
    should report a large adjustment and a near-zero weight, which keeps the
    reasoning visible in the report while correctly having no effect.
    """

    name: str
    logit_adjustment: float
    weight: float
    rationale: str
    points: float | None = None       # effect in points, when meaningful
    source: str | None = None
    observed_at: datetime | None = None

    @property
    def effective(self) -> float:
        return self.logit_adjustment * self.weight


@dataclass
class BetCandidate:
    """A specific bet at a specific book, priced and staked."""

    event: Event
    market_type: MarketType
    outcome: str
    book: str
    american: float
    line: float | None
    fair: FairPrice
    model_probability: float
    signals: list[SignalContribution] = field(default_factory=list)
    stake: float = 0.0
    kelly_fraction: float = 0.0
    confidence: Confidence = Confidence.PASS
    notes: list[str] = field(default_factory=list)
    deep_link: str | None = None
    # Worst-case devig probability, used as the pessimistic screen.
    conservative_probability: float | None = None
    # Player props need the subject and stat to be identified at all: two
    # players' "Over" on the same game are entirely different bets, and
    # without these they collide in dedup, conflict detection, and
    # correlation.
    subject: str | None = None
    stat: str | None = None

    @property
    def decimal(self) -> float:
        return american_to_decimal(self.american)

    @property
    def implied(self) -> float:
        return decimal_to_prob(self.decimal)

    @property
    def ev(self) -> float:
        """Expected profit per unit staked."""
        return self.model_probability * (self.decimal - 1.0) - (1.0 - self.model_probability)

    @property
    def ev_pct(self) -> float:
        return self.ev * 100.0

    @property
    def conservative_ev(self) -> float:
        """EV computed against the worst-case probability estimate."""
        p = self.conservative_probability
        if p is None:
            return self.ev
        return p * (self.decimal - 1.0) - (1.0 - p)

    @property
    def edge_vs_market(self) -> float:
        """Model probability minus the price's break-even probability."""
        return self.model_probability - self.implied

    @property
    def expected_profit(self) -> float:
        return self.stake * self.ev

    @property
    def description(self) -> str:
        if self.subject and self.stat:
            return (
                f"{self.subject} {self.stat.replace('_', ' ')} {self.outcome} "
                f"{self.line:g} ({self.american:+.0f}) @ {self.book}"
            )
        line = ""
        if self.line is not None:
            if self.market_type in (
                MarketType.TOTAL,
                MarketType.ALTERNATE_TOTAL,
                MarketType.TEAM_TOTAL,
                MarketType.FIRST_HALF_TOTAL,
            ):
                line = f" {self.line:g}"
            else:
                line = f" {self.line:+g}"
        subject = f"{self.subject} " if self.subject else ""
        return f"{subject}{self.outcome}{line} ({self.american:+.0f}) @ {self.book}"

    def key(self) -> tuple:
        """Identity of the logical bet, independent of which book offers it."""
        return (
            self.event.event_id,
            self.market_type,
            self.subject,
            self.stat,
            self.outcome,
            self.line,
        )

    def market_key(self) -> tuple:
        """Identity of the market this bet sits in, for conflict detection.

        Carries the subject and line so that two players' props -- and two
        rungs of the same ladder -- are never mistaken for opposite sides of
        a single market.
        """
        return (
            self.event.event_id,
            self.market_type,
            self.subject,
            self.stat,
            self.line,
        )


@dataclass
class NewsItem:
    """A headline, already matched to the teams and players it affects."""

    headline: str
    published: datetime
    source: str
    teams: list[str] = field(default_factory=list)
    players: list[str] = field(default_factory=list)
    url: str | None = None
    body: str = ""

    def age_minutes(self, now: datetime | None = None) -> float:
        now = now or utcnow()
        return max((now - self.published).total_seconds() / 60.0, 0.0)


class InjuryStatus(str, Enum):
    OUT = "out"
    DOUBTFUL = "doubtful"
    QUESTIONABLE = "questionable"
    PROBABLE = "probable"
    ACTIVE = "active"
    GAME_TIME_DECISION = "gtd"


# Probability a player actually suits up, by reported status. Questionable is
# close to a coin flip in most leagues, which is why questionable tags move
# lines so little until they resolve.
PLAY_PROBABILITY: dict[InjuryStatus, float] = {
    InjuryStatus.OUT: 0.0,
    InjuryStatus.DOUBTFUL: 0.08,
    InjuryStatus.GAME_TIME_DECISION: 0.45,
    InjuryStatus.QUESTIONABLE: 0.55,
    InjuryStatus.PROBABLE: 0.92,
    InjuryStatus.ACTIVE: 1.0,
}


@dataclass
class InjuryReport:
    """A player's availability and what his absence is worth in points."""

    player: str
    team: str
    status: InjuryStatus
    position: str | None = None
    # Points the team's spread moves if this player does not play. Positive
    # means the team gets worse without him.
    point_value: float = 0.0
    reported_at: datetime = field(default_factory=utcnow)
    note: str = ""

    @property
    def play_probability(self) -> float:
        return PLAY_PROBABILITY.get(self.status, 1.0)

    @property
    def expected_point_impact(self) -> float:
        """Point impact weighted by the chance he sits."""
        return self.point_value * (1.0 - self.play_probability)


@dataclass
class WeatherReport:
    """Conditions at kickoff for outdoor games."""

    event_id: str
    wind_mph: float = 0.0
    temperature_f: float = 60.0
    precipitation_chance: float = 0.0
    dome: bool = False
    description: str = ""


@dataclass
class LineSnapshot:
    """One observation of a line, for movement analysis."""

    event_id: str
    market_type: MarketType
    outcome: str
    book: str
    american: float
    line: float | None
    timestamp: datetime


@dataclass
class PublicBetting:
    """Where the public money is, split by tickets and by dollars.

    The gap between the two is the useful part. Sixty percent of tickets on a
    side but forty percent of the handle means small bettors are on it and
    large bettors are not.
    """

    event_id: str
    market_type: MarketType
    outcome: str
    ticket_pct: float
    handle_pct: float

    @property
    def divergence(self) -> float:
        """Handle share minus ticket share. Positive means big money agrees."""
        return self.handle_pct - self.ticket_pct


@dataclass
class Opportunity:
    """A structural edge that does not depend on any probability estimate.

    Arbitrage, middles, and low-hold pairs are true regardless of who wins,
    so they are surfaced separately from model-driven bets.
    """

    kind: str  # "arbitrage" | "middle" | "low_hold" | "boost" | "stale_line"
    event: Event
    market_type: MarketType
    legs: list[tuple[str, str, float, float | None]]  # (book, outcome, american, line)
    profit_pct: float
    note: str = ""
    middle_probability: float = 0.0

    @property
    def description(self) -> str:
        parts = [f"{o} {a:+.0f} @ {b}" for b, o, a, _ in self.legs]
        return " / ".join(parts)


@dataclass
class NearMiss:
    """A priced outcome that fell just short of the EV floor.

    Not a recommendation -- it never passed the bar that turns a priced
    outcome into a bet, and it is never staked. It exists because "no bets
    today" and "the closest thing missed the floor by 0.3 points" are
    different situations for a bettor deciding whether to keep checking
    back, and the screen otherwise throws this distinction away: a
    candidate that misses ``min_ev`` by a hair and one that misses it by
    ten points both just vanish as an uncounted rejection.
    """

    event: str
    league: str
    sport: str
    market: str
    subject: str | None
    stat: str | None
    outcome: str
    line: float | None
    book: str
    american: float
    ev: float
    min_ev: float
    model_probability: float
    market_probability: float
    books_priced: int

    @property
    def shortfall(self) -> float:
        """How far below the floor this fell, in EV points. Always > 0."""
        return self.min_ev - self.ev


@dataclass
class SlateResult:
    """Everything the daily run produced."""

    generated_at: datetime
    bets: list[BetCandidate]
    opportunities: list[Opportunity] = field(default_factory=list)
    considered: int = 0
    bankroll: float = 0.0
    skipped: list[tuple[str, str]] = field(default_factory=list)
    # Ranked view of the card, carrying each bet's scoring components.
    ranked: list[Any] = field(default_factory=list)   # ranking.ScoredBet
    card_stats: dict[str, Any] = field(default_factory=dict)
    # Priced outcomes that missed the EV floor but were close -- see
    # NearMiss's docstring for why these are worth keeping separately from
    # an ordinary uncounted rejection.
    near_misses: list[NearMiss] = field(default_factory=list)

    @property
    def total_stake(self) -> float:
        return sum(b.stake for b in self.bets)

    @property
    def expected_profit(self) -> float:
        return sum(b.expected_profit for b in self.bets)

    @property
    def expected_roi(self) -> float:
        total = self.total_stake
        return self.expected_profit / total if total > 0 else 0.0

    def by_confidence(self, tier: Confidence) -> list[BetCandidate]:
        return [b for b in self.bets if b.confidence == tier]


def blend_logit(probability: float, adjustment: float) -> float:
    """Apply a log-odds adjustment to a probability, staying inside (0, 1)."""
    p = min(max(probability, 1e-9), 1.0 - 1e-9)
    z = math.log(p / (1.0 - p)) + adjustment
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)
