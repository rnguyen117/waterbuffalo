"""Monte Carlo simulation of a card and of a season.

Two questions this answers that a point estimate cannot:

**What does a bad day look like?** A card with 12% exposure and a positive
expectation still loses eight percent of the bankroll fairly often. Seeing
the distribution before placing the bets is what keeps a normal losing day
from feeling like evidence that the model broke.

**How long until I know if this works?** Usually much longer than people
think. Simulating a season at a realistic edge shows how often a genuinely
profitable approach finishes in the red, and it is the most useful reality
check in this package.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ..models import BetCandidate
from ..risk.correlation import correlation_matrix


@dataclass
class SimulationResult:
    trials: int
    mean_profit: float
    median_profit: float
    std_profit: float
    p05: float
    p25: float
    p75: float
    p95: float
    prob_profit: float
    worst: float
    best: float

    def summary(self, bankroll: float | None = None) -> str:
        def fmt(v: float) -> str:
            if bankroll:
                return f"${v:,.0f} ({v / bankroll:+.1%})"
            return f"${v:,.0f}"

        return (
            f"Across {self.trials:,} simulations: median {fmt(self.median_profit)}, "
            f"profitable {self.prob_profit:.0%} of the time. "
            f"A bad day (5th percentile) is {fmt(self.p05)}; "
            f"a good one (95th) is {fmt(self.p95)}."
        )


def simulate_slate(
    bets: list[BetCandidate],
    trials: int = 20_000,
    seed: int = 11,
    use_correlation: bool = True,
) -> SimulationResult:
    """Simulate a day's card, respecting correlation between bets.

    Correlated outcomes are drawn with a one-factor Gaussian copula: each bet
    gets a shared component and an idiosyncratic one, calibrated so the
    average pairwise correlation matches the structural matrix. Cruder than a
    full copula and sufficient for the question, which is the shape of the
    tail rather than a precise joint distribution.
    """
    if not bets:
        return SimulationResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    rng = random.Random(seed)
    n = len(bets)
    probs = [b.model_probability for b in bets]
    payouts = [b.stake * (b.decimal - 1.0) for b in bets]
    losses = [-b.stake for b in bets]

    loading = 0.0
    if use_correlation and n > 1:
        matrix = correlation_matrix(bets)
        off_diagonal = [
            matrix[i][j] for i in range(n) for j in range(n) if i != j
        ]
        avg = sum(off_diagonal) / len(off_diagonal) if off_diagonal else 0.0
        loading = math.sqrt(max(avg, 0.0))

    results: list[float] = []
    for _ in range(trials):
        shared = rng.gauss(0, 1)
        total = 0.0
        for i in range(n):
            z = loading * shared + math.sqrt(max(1.0 - loading**2, 0.0)) * rng.gauss(0, 1)
            # Convert the latent normal into a win/loss at the right rate.
            threshold = _inv_norm(1.0 - probs[i])
            total += payouts[i] if z > threshold else losses[i]
        results.append(total)

    return _summarize(results, trials)


def simulate_season(
    edge: float,
    bets_per_day: int,
    days: int,
    bankroll: float,
    kelly_fraction: float = 0.01,
    average_decimal: float = 1.91,
    trials: int = 5_000,
    seed: int = 13,
) -> SimulationResult:
    """Simulate a season of betting at a constant edge.

    Run this before believing any projection. At a 2% edge, one bet per day,
    quarter Kelly, a full season still finishes negative a meaningful share of
    the time -- which is the honest answer to "how much will this make me".
    """
    rng = random.Random(seed)
    win_prob = (1.0 + edge) / average_decimal
    profit_multiple = average_decimal - 1.0

    finals: list[float] = []
    for _ in range(trials):
        roll = bankroll
        for _ in range(days):
            for _ in range(bets_per_day):
                stake = roll * kelly_fraction
                if stake <= 0:
                    break
                if rng.random() < win_prob:
                    roll += stake * profit_multiple
                else:
                    roll -= stake
                if roll <= bankroll * 0.05:
                    break
        finals.append(roll - bankroll)

    return _summarize(finals, trials)


def risk_of_drawdown(
    edge: float,
    bets: int,
    kelly_fraction: float,
    threshold: float = 0.20,
    average_decimal: float = 1.91,
    trials: int = 5_000,
    seed: int = 17,
) -> float:
    """Probability of ever being down by ``threshold`` during a run.

    Almost always higher than intuition suggests. A profitable bettor at
    quarter Kelly should expect to see a 20% drawdown at some point, and
    knowing that in advance is what stops them from abandoning a working
    process at the bottom.
    """
    rng = random.Random(seed)
    win_prob = (1.0 + edge) / average_decimal
    profit_multiple = average_decimal - 1.0

    hits = 0
    for _ in range(trials):
        roll = 1.0
        peak = 1.0
        for _ in range(bets):
            stake = roll * kelly_fraction
            roll += stake * profit_multiple if rng.random() < win_prob else -stake
            peak = max(peak, roll)
            if 1.0 - roll / peak >= threshold:
                hits += 1
                break
    return hits / trials


def _summarize(results: list[float], trials: int) -> SimulationResult:
    ordered = sorted(results)
    n = len(ordered)

    def pct(q: float) -> float:
        if n == 0:
            return 0.0
        idx = min(int(q * n), n - 1)
        return ordered[idx]

    mean = sum(ordered) / n if n else 0.0
    var = sum((r - mean) ** 2 for r in ordered) / n if n else 0.0

    return SimulationResult(
        trials=trials,
        mean_profit=mean,
        median_profit=pct(0.5),
        std_profit=math.sqrt(var),
        p05=pct(0.05),
        p25=pct(0.25),
        p75=pct(0.75),
        p95=pct(0.95),
        prob_profit=sum(1 for r in ordered if r > 0) / n if n else 0.0,
        worst=ordered[0] if n else 0.0,
        best=ordered[-1] if n else 0.0,
    )


def _inv_norm(p: float) -> float:
    """Inverse normal CDF, reused from the odds math module."""
    from ..oddsmath import _normal_ppf

    return _normal_ppf(min(max(p, 1e-9), 1 - 1e-9))
