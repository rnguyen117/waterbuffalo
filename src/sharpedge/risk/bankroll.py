"""Bankroll management.

The part everyone skips and the part that decides whether an edge ever turns
into money. A bettor with a 2% edge and bad bankroll discipline goes broke
more reliably than a bettor with no edge and good discipline, because ruin is
absorbing and edges are slow.

Three rules encoded here:

* Stake as a fraction of the *current* bankroll, never a fixed dollar amount.
  Fixed staking means you bet the same after losing 40%, which is how a
  drawdown becomes a wipeout.
* Cap single-bet exposure regardless of what Kelly says. Kelly's advice on a
  mispriced longshot is unhinged.
* Treat a deep drawdown as evidence about the model, not just bad luck, and
  reduce size while you find out which it is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime

from ..models import utcnow


@dataclass
class BankrollState:
    """Current bankroll and the history needed to size the next bet."""

    starting: float
    current: float
    peak: float
    bets_placed: int = 0
    total_staked: float = 0.0
    total_profit: float = 0.0
    history: list[tuple[datetime, float]] = field(default_factory=list)

    @classmethod
    def new(cls, starting: float) -> "BankrollState":
        return cls(starting=starting, current=starting, peak=starting)

    @property
    def roi(self) -> float:
        return self.total_profit / self.total_staked if self.total_staked > 0 else 0.0

    @property
    def growth(self) -> float:
        return (self.current / self.starting) - 1.0 if self.starting > 0 else 0.0

    @property
    def drawdown(self) -> float:
        """Current distance below the high-water mark."""
        return 1.0 - (self.current / self.peak) if self.peak > 0 else 0.0

    @property
    def max_drawdown(self) -> float:
        if not self.history:
            return self.drawdown
        peak = self.starting
        worst = 0.0
        for _, value in self.history:
            peak = max(peak, value)
            worst = max(worst, 1.0 - value / peak if peak > 0 else 0.0)
        return worst

    def record(self, profit: float, stake: float, when: datetime | None = None) -> None:
        """Apply a settled bet."""
        self.current += profit
        self.peak = max(self.peak, self.current)
        self.bets_placed += 1
        self.total_staked += stake
        self.total_profit += profit
        self.history.append((when or utcnow(), self.current))


@dataclass
class StakingRules:
    """Limits applied on top of whatever the model recommends."""

    kelly_multiplier: float = 0.25
    max_bet_fraction: float = 0.03
    max_daily_exposure: float = 0.12
    min_stake: float = 5.0
    round_to: float = 1.0
    # Halt trading if the bankroll falls this far below the peak. A hard stop
    # is worth more than any model refinement, because it bounds the damage
    # from a bug or a bad assumption you have not found yet.
    stop_loss_drawdown: float = 0.35
    # Scale down as drawdown deepens.
    drawdown_scaling: bool = True

    def effective_multiplier(self, state: BankrollState) -> float:
        if not self.drawdown_scaling:
            return self.kelly_multiplier
        from ..pricing.kelly import drawdown_adjusted_multiplier

        return drawdown_adjusted_multiplier(
            state.current, state.peak, self.kelly_multiplier
        )

    def should_halt(self, state: BankrollState) -> tuple[bool, str]:
        if state.drawdown >= self.stop_loss_drawdown:
            return True, (
                f"drawdown of {state.drawdown:.1%} has hit the {self.stop_loss_drawdown:.0%} "
                "stop loss -- stop betting and audit the model before continuing"
            )
        return False, ""

    def size(self, state: BankrollState, kelly_fraction: float, book_limit: float | None = None) -> float:
        """Dollar stake for a bet with the given raw Kelly fraction."""
        halt, _ = self.should_halt(state)
        if halt:
            return 0.0
        fraction = min(
            kelly_fraction * self.effective_multiplier(state) / max(self.kelly_multiplier, 1e-9)
            * self.kelly_multiplier,
            self.max_bet_fraction,
        )
        stake = state.current * fraction
        if book_limit is not None:
            stake = min(stake, book_limit)
        if stake < self.min_stake:
            return 0.0
        return math.floor(stake / self.round_to) * self.round_to if self.round_to > 0 else stake


def unit_size(bankroll: float, units_per_bankroll: float = 100.0) -> float:
    """Classic unit sizing, for comparison against Kelly.

    A "unit" is conventionally 1% of the bankroll. Flat unit betting is worse
    than Kelly when edges vary and better than Kelly when your probabilities
    are badly calibrated, which is a real argument for it if you have not
    verified your calibration yet.
    """
    return bankroll / units_per_bankroll


def expected_growth(edge: float, variance: float, fraction: float) -> float:
    """Approximate expected log-growth per bet."""
    return fraction * edge - 0.5 * (fraction**2) * variance


def kelly_criterion_summary(bankroll: float, multiplier: float = 0.25) -> str:
    """A plain-language description of what the staking plan implies."""
    max_bet = bankroll * 0.03
    typical = bankroll * 0.01
    return (
        f"On a ${bankroll:,.0f} bankroll at {multiplier:g} Kelly: a typical bet is "
        f"about ${typical:,.0f}, the hard cap is ${max_bet:,.0f}, and a bad day "
        f"should cost no more than ${bankroll * 0.12:,.0f}."
    )


def days_to_double(edge: float, bets_per_day: float, fraction: float) -> float:
    """Rough time to double the bankroll at a sustained edge.

    Sobering by design. A 2% edge betting 1% of bankroll ten times a day takes
    the better part of a year to double, and that is with no variance and no
    limits. Anyone promising faster is describing gambling, not investing.
    """
    if edge <= 0 or fraction <= 0 or bets_per_day <= 0:
        return float("inf")
    growth_per_bet = fraction * edge
    if growth_per_bet <= 0:
        return float("inf")
    return math.log(2.0) / (growth_per_bet * bets_per_day)
