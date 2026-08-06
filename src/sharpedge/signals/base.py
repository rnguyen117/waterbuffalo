"""Signal framework: turning information into a defensible probability shift.

Every signal answers the same question -- *given what the market already
knows, how much should this outcome's probability move?* -- and returns the
answer in log-odds along with a weight for how much of it survives.

Two design rules make this work rather than devolve into a pile of fudge
factors:

**Signals must be net of what the market already prices.** The market has
seen the injury report too. A signal that reports the full effect of a known
absence is double-counting: the line already moved. Each signal therefore
compares its expected effect to the movement already observed and only claims
the residual. This is the difference between a system that finds real edges
and one that reliably bets on old news.

**Adjustments are in log-odds and bounded.** Log-odds compose additively, can
never push a probability outside (0, 1), and correctly make a five-point shift
matter more to a coin flip than to a heavy favorite. The total adjustment is
capped, because no realistic combination of situational factors justifies
moving a number more than the market moves in a week.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from ..models import (
    Event,
    InjuryReport,
    Market,
    MarketType,
    NewsItem,
    PublicBetting,
    SignalContribution,
    WeatherReport,
    utcnow,
)
from ..oddsmath import logit, spread_to_prob, sport_sigma


@dataclass
class SignalContext:
    """Everything a signal is allowed to look at."""

    event: Event
    market: Market
    outcome: str
    market_probability: float
    # The full consensus estimate for this outcome. Signals that reason about
    # book disagreement or the sharp/retail split read it from here.
    fair_price: object | None = None  # models.FairPrice
    # The book and number this bet would actually be placed at. Signals that
    # reason about a specific book's staleness need to know which one we chose,
    # otherwise they credit an edge to a book we are not betting.
    book: str | None = None
    bet_line: float | None = None
    consensus_line: float | None = None
    opening_line: float | None = None
    current_line: float | None = None
    news: list[NewsItem] = field(default_factory=list)
    injuries: list[InjuryReport] = field(default_factory=list)
    weather: WeatherReport | None = None
    public: PublicBetting | None = None
    movement: object | None = None  # market.movement.MovementRead
    now: datetime = field(default_factory=utcnow)

    @property
    def sport(self) -> str:
        return self.event.sport

    @property
    def hours_to_start(self) -> float:
        return self.event.hours_to_start(self.now)

    @property
    def line_move(self) -> float:
        if self.opening_line is None or self.current_line is None:
            return 0.0
        return self.current_line - self.opening_line

    def team_for_outcome(self) -> str | None:
        """Which team this outcome refers to, if any."""
        for team in (self.event.home_team, self.event.away_team):
            if team.lower() in self.outcome.lower() or self.outcome.lower() in team.lower():
                return team
        return None

    def is_home_outcome(self) -> bool:
        return self.team_for_outcome() == self.event.home_team


class Signal(Protocol):
    """A named source of disagreement with the market."""

    name: str

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        """Return contributions, or an empty list when the signal does not apply."""
        ...


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def points_to_logit(points: float, market_probability: float, sport: str) -> float:
    """Convert an effect measured in points into a log-odds shift.

    Done through the sport's margin distribution rather than a fixed
    conversion, because a point is worth much more to a pick'em than to a
    two-touchdown favorite. Losing a star from a team favored by 14 barely
    changes their win probability even though it moves the spread a lot.
    """
    if points == 0.0:
        return 0.0
    sigma = sport_sigma(sport)
    p = min(max(market_probability, 1e-6), 1.0 - 1e-6)
    # Recover the spread the market probability corresponds to, shift it,
    # and measure the change in log-odds.
    from ..oddsmath import prob_to_spread

    current_spread = prob_to_spread(p, sport, sigma)
    new_p = spread_to_prob(current_spread - points, sport, sigma)
    return logit(new_p) - logit(p)


def residual_after_market_move(
    expected_points: float, observed_move: float, tolerance: float = 0.25
) -> tuple[float, float]:
    """Split an expected effect into the part the market has already taken.

    Returns ``(residual_points, credit)`` where credit is 0..1 describing how
    much of the effect is still unpriced. If the line already moved the full
    expected amount there is nothing left; if it moved further than expected,
    the market has overreacted and the residual flips sign, which is itself a
    tradeable observation.
    """
    if abs(expected_points) < 1e-9:
        return 0.0, 0.0
    residual = expected_points - observed_move
    if abs(residual) < tolerance:
        return 0.0, 0.0
    credit = min(abs(residual) / abs(expected_points), 1.5)
    return residual, credit


def recency_credit(observed_at: datetime | None, now: datetime, half_life_min: float = 90.0) -> float:
    """How much a piece of news is still worth, by age.

    News decays fast. An injury report from three days ago is fully in the
    price at every book. One from four minutes ago is in the price at maybe
    two of them, and that gap is the entire opportunity.
    """
    if observed_at is None:
        return 0.3
    age_min = max((now - observed_at).total_seconds() / 60.0, 0.0)
    return 0.5 ** (age_min / half_life_min)


def book_lag_credit(hours_to_start: float) -> float:
    """Extra credit when there is still time for slow books to be wrong.

    Right before kickoff every book has repriced, so the informational edge
    is gone even if the analysis is correct.
    """
    if hours_to_start <= 0.25:
        return 0.35
    if hours_to_start <= 2:
        return 0.75
    if hours_to_start <= 24:
        return 1.0
    return 0.85


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class SignalEngine:
    """Runs signals and combines them into a final model probability.

    ``max_total_logit`` caps how far the model may stray from the market.
    Set generously it turns the package into a random number generator; set
    at the default it permits a shift of roughly three to four points on a
    typical NFL spread, which is already a very strong claim to make against
    a market that has seen everything you have.

    ``market_trust`` shrinks the combined adjustment toward zero. At 0.6, the
    model keeps 40% of its disagreement with the market. That looks timid and
    it is the correct posture: the closing line is very hard to beat, and
    every point of overconfidence here is paid for in real money.
    """

    signals: list[Signal] = field(default_factory=list)
    max_total_logit: float = 0.55
    market_trust: float = 0.60

    def register(self, signal: Signal) -> None:
        self.signals.append(signal)

    def evaluate(self, ctx: SignalContext) -> tuple[float, list[SignalContribution]]:
        """Return ``(model_probability, contributions)``."""
        contributions: list[SignalContribution] = []
        for signal in self.signals:
            try:
                contributions.extend(signal.evaluate(ctx))
            except Exception as exc:  # a broken signal must not kill the run
                contributions.append(
                    SignalContribution(
                        name=getattr(signal, "name", type(signal).__name__),
                        logit_adjustment=0.0,
                        weight=0.0,
                        rationale=f"signal failed: {exc}",
                    )
                )

        raw = sum(c.effective for c in contributions)
        shrunk = raw * (1.0 - self.market_trust)
        bounded = clamp(shrunk, -self.max_total_logit, self.max_total_logit)

        p = ctx.market_probability
        z = logit(p) + bounded
        model_p = 1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1.0 + math.exp(z))
        return clamp(model_p, 1e-4, 1.0 - 1e-4), contributions

    def explain(self, contributions: list[SignalContribution]) -> list[str]:
        """Readable reasons, strongest first, skipping inert signals."""
        active = [c for c in contributions if abs(c.effective) > 1e-4]
        active.sort(key=lambda c: -abs(c.effective))
        return [f"{c.name}: {c.rationale}" for c in active]
