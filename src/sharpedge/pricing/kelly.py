"""Kelly staking, and the adjustments that make it survivable.

Full Kelly maximizes long-run growth *given that your probabilities are
correct*. They are not correct. That single fact is why full Kelly is a
disaster in practice and why every serious bettor uses a fraction of it.

The failure mode is asymmetric and worth stating plainly: overestimating your
edge by a factor of two makes Kelly stake four times too much, and the growth
penalty for overbetting is far steeper than for underbetting. Betting half
Kelly gives up about a quarter of theoretical growth while cutting variance
roughly in half. Quarter Kelly gives up more growth and makes ruin a
practical impossibility. The default here is a quarter, and moving it up is a
decision that should be made deliberately.

Three refinements beyond fractional Kelly:

* **Uncertainty shrinkage.** Shrink the probability estimate toward the
  market before computing the stake. A model that disagrees with the market
  by 4 points is usually wrong by 3 of them.
* **Simultaneous bets.** Games on the same day resolve together, so total
  exposure has to be controlled jointly rather than bet by bet.
* **Correlation.** Two bets on the same game are one bet with extra steps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..oddsmath import american_to_decimal, expit, logit


@dataclass
class StakeDecision:
    """A recommended stake and the reasoning that produced it."""

    fraction: float          # fraction of bankroll
    stake: float             # dollars
    full_kelly: float        # unconstrained Kelly fraction, for reference
    shrunk_probability: float
    binding_constraint: str  # what limited the stake
    notes: list[str] = field(default_factory=list)


def kelly_fraction(probability: float, american: float) -> float:
    """Unconstrained Kelly fraction for a single binary bet.

    f* = (bp - q) / b, where b is the profit per unit staked. Negative means
    the bet is -EV and the correct stake is zero (or the other side).
    """
    d = american_to_decimal(american)
    b = d - 1.0
    if b <= 0:
        return 0.0
    p = min(max(probability, 0.0), 1.0)
    q = 1.0 - p
    return (b * p - q) / b


def kelly_growth_rate(probability: float, american: float, fraction: float) -> float:
    """Expected log-growth per bet at a given stake fraction.

    Plotting this against fraction shows why overbetting is so punishing: the
    curve is roughly parabolic near the optimum but falls off a cliff past
    twice the Kelly fraction, and goes negative well before the stake reaches
    the whole bankroll.
    """
    d = american_to_decimal(american)
    b = d - 1.0
    p = min(max(probability, 0.0), 1.0)
    if fraction <= 0:
        return 0.0
    if fraction >= 1.0 / 1.0 and fraction * 1.0 >= 1.0:
        return float("-inf")
    win_term = p * math.log(1.0 + fraction * b) if 1.0 + fraction * b > 0 else float("-inf")
    lose_term = (1.0 - p) * math.log(1.0 - fraction) if 1.0 - fraction > 0 else float("-inf")
    return win_term + lose_term


def shrink_toward_market(
    model_probability: float, market_probability: float, confidence: float
) -> float:
    """Pull the model estimate toward the market in log-odds space.

    ``confidence`` is 0..1: at 0 the model is ignored entirely, at 1 it is
    taken at face value. Shrinking is not timidity, it is the correct
    Bayesian response to having a noisy estimate and a strong prior -- and
    the market is a very strong prior.
    """
    c = min(max(confidence, 0.0), 1.0)
    return expit(c * logit(model_probability) + (1.0 - c) * logit(market_probability))


def confidence_from_sigma(sigma_logit: float, floor: float = 0.15) -> float:
    """Turn a consensus dispersion into a model-confidence weight.

    Tight agreement between books means the market is confident and a
    disagreeing model should mostly defer. Wide dispersion means the market
    itself does not know, which is where an independent estimate is worth
    the most.
    """
    if sigma_logit <= 0:
        return floor
    return max(floor, min(1.0, sigma_logit / (sigma_logit + 0.12)))


def uncertainty_adjusted_kelly(
    model_probability: float,
    market_probability: float,
    american: float,
    sigma_logit: float,
    kelly_multiplier: float = 0.25,
    max_fraction: float = 0.03,
    min_fraction: float = 0.0025,
) -> tuple[float, float, str]:
    """Kelly fraction after shrinkage, fractional scaling, and capping.

    Returns ``(fraction, shrunk_probability, binding_constraint)``.
    """
    confidence = confidence_from_sigma(sigma_logit)
    shrunk = shrink_toward_market(model_probability, market_probability, confidence)

    full = kelly_fraction(shrunk, american)
    if full <= 0:
        return 0.0, shrunk, "no edge after shrinkage"

    fraction = full * kelly_multiplier
    constraint = f"{kelly_multiplier:g} Kelly"

    if fraction > max_fraction:
        fraction = max_fraction
        constraint = f"max bet cap ({max_fraction:.1%} of bankroll)"

    if fraction < min_fraction:
        return 0.0, shrunk, "below minimum bet size"

    return fraction, shrunk, constraint


def stake_for(
    bankroll: float,
    model_probability: float,
    market_probability: float,
    american: float,
    sigma_logit: float,
    kelly_multiplier: float = 0.25,
    max_fraction: float = 0.03,
    min_stake: float = 5.0,
    book_limit: float | None = None,
    round_to: float = 1.0,
) -> StakeDecision:
    """Full staking decision for one bet, in dollars."""
    fraction, shrunk, constraint = uncertainty_adjusted_kelly(
        model_probability,
        market_probability,
        american,
        sigma_logit,
        kelly_multiplier,
        max_fraction,
    )
    full = kelly_fraction(shrunk, american)
    notes: list[str] = []

    stake = bankroll * fraction

    if book_limit is not None and stake > book_limit:
        stake = book_limit
        constraint = "book limit"
        notes.append(f"capped by the book's ${book_limit:,.0f} limit")

    if stake < min_stake:
        return StakeDecision(0.0, 0.0, full, shrunk, "below minimum stake", notes)

    if round_to > 0:
        stake = math.floor(stake / round_to) * round_to

    return StakeDecision(
        fraction=stake / bankroll if bankroll > 0 else 0.0,
        stake=stake,
        full_kelly=full,
        shrunk_probability=shrunk,
        binding_constraint=constraint,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Simultaneous bets
# ---------------------------------------------------------------------------


def simultaneous_kelly(
    edges: list[tuple[float, float]], max_total: float = 0.15
) -> list[float]:
    """Scale a set of independent Kelly fractions to respect total exposure.

    ``edges`` is ``(probability, american)`` per bet. Independent bets placed
    at the same time should not simply be summed at their individual Kelly
    fractions -- the correct joint solution is smaller, because each bet's
    risk reduces the capital available to the others.

    Scaling proportionally is an approximation of the true joint optimum,
    accurate enough for the small fractions fractional Kelly produces and far
    more robust than solving the exact system with noisy inputs.
    """
    fractions = [max(kelly_fraction(p, a), 0.0) for p, a in edges]
    total = sum(fractions)
    if total <= max_total or total == 0:
        return fractions
    scale = max_total / total
    return [f * scale for f in fractions]


def correlation_haircut(fraction: float, correlations: list[float]) -> float:
    """Reduce a stake for correlation with bets already in the portfolio.

    Two bets correlated at 0.7 are close to a single bet at 1.7x the size.
    The haircut divides by the effective multiplier so the *combined*
    position lands near where a single Kelly bet would.
    """
    if not correlations:
        return fraction
    effective = 1.0 + sum(max(min(c, 1.0), 0.0) for c in correlations)
    return fraction / effective


def drawdown_adjusted_multiplier(
    current_bankroll: float, peak_bankroll: float, base: float = 0.25
) -> float:
    """Reduce Kelly during a drawdown.

    Kelly already scales stakes with bankroll, so this is not mathematically
    required -- it is behavioral and practical. Drawdowns are when models are
    most likely to be broken rather than unlucky, and betting smaller while
    you find out is cheap insurance.
    """
    if peak_bankroll <= 0:
        return base
    drawdown = 1.0 - (current_bankroll / peak_bankroll)
    if drawdown < 0.10:
        return base
    if drawdown < 0.20:
        return base * 0.75
    if drawdown < 0.35:
        return base * 0.5
    return base * 0.35


def risk_of_ruin(
    win_probability: float, fraction: float, ruin_threshold: float = 0.5, bets: int = 1000
) -> float:
    """Approximate probability of losing down to ``ruin_threshold``.

    Uses a random-walk approximation on log bankroll. With quarter Kelly and
    a genuine edge, the answer is very close to zero, which is the entire
    argument for fractional staking.
    """
    if fraction <= 0:
        return 0.0
    p = min(max(win_probability, 1e-6), 1 - 1e-6)
    mu = p * math.log(1 + fraction) + (1 - p) * math.log(1 - fraction)
    var = (
        p * (math.log(1 + fraction) - mu) ** 2
        + (1 - p) * (math.log(1 - fraction) - mu) ** 2
    )
    if var <= 0:
        return 0.0 if mu > 0 else 1.0
    barrier = -math.log(ruin_threshold)
    if mu <= 0:
        return 1.0
    # Probability a positive-drift walk ever reaches -barrier.
    return math.exp(-2.0 * mu * barrier / var)


def optimal_multiplier_for_ruin(
    win_probability: float, american: float, max_ruin: float = 0.01
) -> float:
    """Largest Kelly multiplier keeping risk of ruin under a threshold."""
    full = kelly_fraction(win_probability, american)
    if full <= 0:
        return 0.0
    for multiplier in [1.0, 0.75, 0.5, 0.33, 0.25, 0.2, 0.15, 0.1, 0.05]:
        if risk_of_ruin(win_probability, full * multiplier) <= max_ruin:
            return multiplier
    return 0.05
