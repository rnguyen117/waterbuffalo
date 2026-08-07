"""Slate construction: turning a list of +EV prices into a day's card.

Sizing bets one at a time is where good analysis becomes a bad bankroll.
A screen that finds fifteen edges will happily recommend staking 40% of a
bankroll across correlated positions on eight games that all kick off within
three hours of each other.

This module solves for the whole card at once, maximizing expected log growth
minus a variance penalty -- the mean-variance approximation to joint Kelly --
subject to the constraints that actually matter:

* total exposure across the slate
* exposure per game, so one bad number cannot appear four times
* exposure per bet
* a cap on how many bets a card may contain

The optimizer is projected gradient ascent in pure Python. The objective is
concave and the feasible set is convex, so it converges reliably and there is
no dependency to install.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..models import BetCandidate, Confidence
from ..risk.correlation import bet_variance, correlation_matrix, effective_bet_count


@dataclass
class PortfolioConstraints:
    """Limits applied to a day's card.

    The defaults are conservative on purpose. Total daily exposure of 12% of
    bankroll with a 3% per-bet cap means a catastrophic day costs a tenth of
    the roll, which is survivable. Doubling these numbers roughly quadruples
    the depth of a bad run.
    """

    max_total_exposure: float = 0.12   # fraction of bankroll at risk per day
    max_per_game: float = 0.05
    max_per_bet: float = 0.03
    max_bets: int = 15
    min_stake: float = 5.0
    risk_aversion: float = 1.0         # weight on the variance penalty
    max_per_book: float = 0.08         # concentration limit per sportsbook


@dataclass
class PortfolioResult:
    bets: list[BetCandidate]
    total_exposure: float
    expected_profit: float
    variance: float
    effective_bets: float
    binding: list[str] = field(default_factory=list)

    @property
    def sharpe(self) -> float:
        """Expected profit per unit of standard deviation for the day."""
        sd = math.sqrt(self.variance) if self.variance > 0 else 0.0
        return self.expected_profit / sd if sd > 0 else 0.0


def optimize(
    candidates: list[BetCandidate],
    bankroll: float,
    constraints: PortfolioConstraints | None = None,
    iterations: int = 400,
    step: float = 0.35,
) -> PortfolioResult:
    """Solve for stakes across a slate.

    Objective: maximize ``sum(f_i * mu_i) - 0.5 * risk_aversion * f' S f``
    where mu is EV per unit staked and S is the covariance of returns. This
    is the quadratic approximation of expected log growth, and at the small
    fractions fractional Kelly produces the approximation is tight.
    """
    constraints = constraints or PortfolioConstraints()
    if not candidates or bankroll <= 0:
        return PortfolioResult([], 0.0, 0.0, 0.0, 0.0)

    # Only bets that survive their own uncertainty are eligible.
    eligible = [c for c in candidates if c.ev > 0 and c.confidence != Confidence.PASS]
    if not eligible:
        return PortfolioResult([], 0.0, 0.0, 0.0, 0.0)

    eligible.sort(key=lambda c: -c.ev)
    eligible = eligible[: max(constraints.max_bets * 3, constraints.max_bets)]

    n = len(eligible)
    mu = [c.ev for c in eligible]
    var = [bet_variance(c.model_probability, c.decimal) for c in eligible]
    rho = correlation_matrix(eligible)

    # Covariance of per-unit returns.
    cov = [
        [rho[i][j] * math.sqrt(var[i]) * math.sqrt(var[j]) for j in range(n)]
        for i in range(n)
    ]

    # Start from the individually-sized fractions, scaled to fit the budget.
    f = [min(c.kelly_fraction, constraints.max_per_bet) for c in eligible]
    total = sum(f)
    if total > constraints.max_total_exposure and total > 0:
        f = [x * constraints.max_total_exposure / total for x in f]

    binding: list[str] = []

    for _ in range(iterations):
        grad = []
        for i in range(n):
            g = mu[i] - constraints.risk_aversion * sum(cov[i][j] * f[j] for j in range(n))
            grad.append(g)
        f = [max(0.0, f[i] + step * grad[i]) for i in range(n)]
        f, hit = _project(f, eligible, constraints)
        binding = hit

    # Materialize stakes and drop anything that rounds away to nothing.
    # Floored to the cent rather than rounded to nearest: the projection
    # above guarantees sum(f) * bankroll clears every cap, but round-to-
    # nearest can push individual stakes up by half a cent each, and
    # summed across a full card that is enough to breach a cap the
    # optimizer itself just satisfied. Flooring can only ever reduce the
    # total, never re-cross a cap it was already under.
    chosen: list[BetCandidate] = []
    for candidate, fraction in zip(eligible, f):
        stake = fraction * bankroll
        if stake < constraints.min_stake:
            continue
        candidate.stake = math.floor(stake * 100) / 100
        candidate.kelly_fraction = fraction
        chosen.append(candidate)

    chosen.sort(key=lambda c: -c.expected_profit)
    if len(chosen) > constraints.max_bets:
        binding.append(f"card capped at {constraints.max_bets} bets")
        chosen = chosen[: constraints.max_bets]

    total_stake = sum(c.stake for c in chosen)
    expected = sum(c.expected_profit for c in chosen)
    idx = {id(c): i for i, c in enumerate(eligible)}
    variance = 0.0
    for a in chosen:
        for b in chosen:
            i, j = idx[id(a)], idx[id(b)]
            variance += a.stake * b.stake * cov[i][j]

    return PortfolioResult(
        bets=chosen,
        total_exposure=total_stake,
        expected_profit=expected,
        variance=variance,
        effective_bets=effective_bet_count(correlation_matrix(chosen)) if chosen else 0.0,
        binding=sorted(set(binding)),
    )


def _project(
    f: list[float], bets: list[BetCandidate], c: PortfolioConstraints
) -> tuple[list[float], list[str]]:
    """Project a stake vector back into the feasible set."""
    binding: list[str] = []

    # Per-bet cap.
    for i, value in enumerate(f):
        if value > c.max_per_bet:
            f[i] = c.max_per_bet
            binding.append("per-bet cap")

    # Per-game cap: scale every bet on an over-exposed game.
    by_game: dict[str, list[int]] = {}
    for i, bet in enumerate(bets):
        by_game.setdefault(bet.event.event_id, []).append(i)
    for indices in by_game.values():
        total = sum(f[i] for i in indices)
        if total > c.max_per_game and total > 0:
            scale = c.max_per_game / total
            for i in indices:
                f[i] *= scale
            binding.append("per-game cap")

    # Per-book cap: keeps a single account from carrying the whole card,
    # which matters both for limits and for counterparty risk.
    by_book: dict[str, list[int]] = {}
    for i, bet in enumerate(bets):
        by_book.setdefault(bet.book, []).append(i)
    for indices in by_book.values():
        total = sum(f[i] for i in indices)
        if total > c.max_per_book and total > 0:
            scale = c.max_per_book / total
            for i in indices:
                f[i] *= scale
            binding.append("per-book cap")

    # Total exposure.
    total = sum(f)
    if total > c.max_total_exposure and total > 0:
        scale = c.max_total_exposure / total
        f = [x * scale for x in f]
        binding.append("total exposure cap")

    return f, binding


def assign_confidence(
    candidate: BetCandidate,
    ev_lower: float,
    n_books: int,
    tier_thresholds: tuple[float, float, float] = (0.03, 0.015, 0.005),
) -> Confidence:
    """Grade a bet on the strength of the evidence behind it.

    Tiers are driven by the *lower bound* on EV rather than the point
    estimate, plus how many books priced the market. A large edge derived
    from two books is a C, and a modest edge confirmed by a dozen books
    including a market maker is an A. That ordering is deliberate: breadth of
    confirmation matters more than the size of the apparent edge.
    """
    a, b, c = tier_thresholds

    if n_books < 3:
        # Too thin to trust the consensus at all.
        return Confidence.C if ev_lower > b else Confidence.PASS

    if ev_lower >= a and n_books >= 5:
        return Confidence.A
    if ev_lower >= b:
        return Confidence.B
    if ev_lower >= c:
        return Confidence.C
    return Confidence.PASS


def dedupe_same_bet(candidates: list[BetCandidate]) -> list[BetCandidate]:
    """Keep only the best-priced version of each logical bet.

    The same side at four books is one bet. Without this the optimizer sees
    four independent opportunities and quadruples the position.
    """
    best: dict[tuple, BetCandidate] = {}
    for candidate in candidates:
        key = candidate.key()
        current = best.get(key)
        if current is None or candidate.decimal > current.decimal:
            best[key] = candidate
    return list(best.values())


def drop_conflicting_sides(candidates: list[BetCandidate]) -> list[BetCandidate]:
    """Remove both sides of the same market when both screen as +EV.

    If a model likes both the over and the under, the model is wrong about
    that market, not doubly right. Keeping the stronger side and discarding
    the other is generous; discarding both is more honest, and that is what
    happens here when the two are close.
    """
    by_market: dict[tuple, list[BetCandidate]] = {}
    for candidate in candidates:
        by_market.setdefault(candidate.market_key(), []).append(candidate)

    kept: list[BetCandidate] = []
    for group in by_market.values():
        sides = {c.outcome for c in group}
        if len(sides) <= 1:
            kept.extend(group)
            continue
        ordered = sorted(group, key=lambda c: -c.ev)
        best, second = ordered[0], ordered[1]
        if best.outcome == second.outcome:
            kept.extend(group)
            continue
        if best.ev - second.ev < 0.01:
            # Both sides look good by a similar margin: the fair price is
            # wrong, not the market.
            continue
        kept.append(best)
    return kept
