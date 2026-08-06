"""Expected value, and why most published EV numbers are wrong.

The formula is trivial. Applying it honestly is not, and the gap between the
two is where most bettors lose money while believing they have an edge.

Three corrections separate this module from a naive EV screen:

**The probability is an estimate, not a fact.** A 3% edge computed from a
probability with a 4% standard error is not a 3% edge, it is a coin flip on
whether an edge exists. The fix is to evaluate EV at a lower confidence bound
rather than at the point estimate, which is the single highest-impact change
available to a betting model.

**Selection bias is real and large.** Screening thousands of prices and
keeping the best ones guarantees the survivors are the ones whose errors ran
in your favor. The more markets scanned, the larger the correction needs to
be. This is the winner's curse, and it is why a screen that shows fifty +EV
bets a day has found approximately zero.

**The best available price is itself evidence.** If one book is 30 cents off
every other book, the likeliest explanation is not that the book is generous
but that it knows something -- a late scratch, a lineup change -- or that the
feed is stale in the other direction. An outlier price should lower your
confidence, not raise it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..oddsmath import american_to_decimal, decimal_to_prob, expit, logit


@dataclass
class EVResult:
    """Full expected-value assessment of a single price."""

    probability: float
    decimal_odds: float
    ev: float                  # expected profit per unit staked
    ev_lower: float            # EV at the lower confidence bound
    edge: float                # probability minus break-even
    break_even: float
    sigma_prob: float
    z_score: float             # how many standard errors the edge is from zero

    @property
    def ev_pct(self) -> float:
        return self.ev * 100.0

    @property
    def is_actionable(self) -> bool:
        """Whether the edge survives its own uncertainty."""
        return self.ev_lower > 0.0


def expected_value(probability: float, american: float) -> float:
    """Expected profit per unit staked. The textbook formula."""
    d = american_to_decimal(american)
    return probability * (d - 1.0) - (1.0 - probability)


def edge(probability: float, american: float) -> float:
    """Probability advantage over the price's break-even point."""
    return probability - decimal_to_prob(american_to_decimal(american))


def break_even_probability(american: float) -> float:
    """Win rate required to break even at this price.

    At -110 it is 52.38%, which is why the standard "you only need to win
    52.4%" framing is correct and also why the margin for error is so thin:
    a 55% bettor is doing very well and is only 2.6 points from breaking even.
    """
    return decimal_to_prob(american_to_decimal(american))


def ev_with_uncertainty(
    probability: float,
    american: float,
    sigma_logit: float,
    confidence: float = 0.75,
    selection_penalty: float = 0.0,
) -> EVResult:
    """EV evaluated at a pessimistic bound on the probability estimate.

    ``sigma_logit`` is the standard error of the probability in log-odds,
    which is what the consensus estimator produces from book disagreement.
    ``confidence`` sets how pessimistic to be: 0.75 uses roughly a 0.67
    standard-error haircut, 0.90 uses about 1.28.

    ``selection_penalty`` is an extra log-odds haircut for the winner's
    curse. Scale it with how many prices were screened to produce this one.
    """
    d = american_to_decimal(american)
    z = _z_for(confidence)
    center = logit(probability) - selection_penalty
    lower_logit = center - z * sigma_logit

    p_point = expit(center)
    p_lower = expit(lower_logit)

    ev = p_point * (d - 1.0) - (1.0 - p_point)
    ev_lower = p_lower * (d - 1.0) - (1.0 - p_lower)
    be = decimal_to_prob(d)

    # Standard error of the probability itself, via the logistic derivative.
    sigma_p = sigma_logit * p_point * (1.0 - p_point)
    z_score = (p_point - be) / sigma_p if sigma_p > 0 else 0.0

    return EVResult(
        probability=p_point,
        decimal_odds=d,
        ev=ev,
        ev_lower=ev_lower,
        edge=p_point - be,
        break_even=be,
        sigma_prob=sigma_p,
        z_score=z_score,
    )


def _z_for(confidence: float) -> float:
    """One-sided normal quantile for a few common confidence levels."""
    table = {0.50: 0.0, 0.60: 0.253, 0.67: 0.44, 0.75: 0.674, 0.80: 0.842,
             0.90: 1.282, 0.95: 1.645, 0.975: 1.960, 0.99: 2.326}
    if confidence in table:
        return table[confidence]
    keys = sorted(table)
    lo = max((k for k in keys if k <= confidence), default=keys[0])
    hi = min((k for k in keys if k >= confidence), default=keys[-1])
    if hi == lo:
        return table[lo]
    frac = (confidence - lo) / (hi - lo)
    return table[lo] + frac * (table[hi] - table[lo])


def selection_penalty(n_prices_screened: int, per_market_sigma: float = 0.06) -> float:
    """Log-odds haircut for having picked the best of many prices.

    The expected maximum of n independent draws grows roughly with
    sqrt(2 ln n). Scanning 500 prices and keeping the best one means the
    survivor carries about 2.5 standard errors of favorable noise, and
    subtracting that is the difference between a screen that finds edges and
    one that finds outliers.
    """
    if n_prices_screened <= 1:
        return 0.0
    return per_market_sigma * math.sqrt(2.0 * math.log(n_prices_screened)) * 0.5


def outlier_discount(best_decimal: float, median_decimal: float) -> float:
    """Extra haircut when the best price is far off the rest of the market.

    A book alone by a wide margin is more often informed or stale than
    generous. Returns a log-odds penalty to apply to the probability.
    """
    if median_decimal <= 0 or best_decimal <= median_decimal:
        return 0.0
    ratio = best_decimal / median_decimal
    if ratio < 1.03:
        return 0.0
    # Roughly: a 10% better price than the market median costs about 0.1
    # log-odds of confidence.
    return min((ratio - 1.03) * 1.4, 0.45)


def implausible_edge(
    fair_probability: float, american: float, max_logit_gap: float = 1.30
) -> tuple[bool, str]:
    """Reject edges too large to be real.

    A price implying 10% when the fair value is 45% is not a gift, it is one
    of three things: a stale quote that will be voided, a feed error, or a
    market you have misidentified (a different line, a different player, a
    first-half number filed as a full-game one). All three lose money or waste
    time, and none of them is a bet.

    Real edges at a live, correctly-parsed market run from a fraction of a
    percent to a few percent. Anything implying a 4:1 disagreement with the
    market is a data-quality alert, and treating it as an opportunity is how
    an automated bettor ends up firing at prices that do not exist.

    ``max_logit_gap`` of 1.30 is roughly a 3.7x odds discrepancy.
    """
    implied = decimal_to_prob(american_to_decimal(american))
    gap = logit(fair_probability) - logit(implied)
    if gap > max_logit_gap:
        return True, (
            f"price implies {implied:.1%} against a fair estimate of "
            f"{fair_probability:.1%} -- too large to be a real edge, treating "
            "it as a stale quote or a parsing error"
        )
    return False, ""


def required_win_rate(american: float, target_roi: float) -> float:
    """Win rate needed to achieve a target ROI at a given price.

    Useful as a reality check. Hitting 10% ROI at -110 requires winning
    57.6% of bets, which essentially nobody sustains over a large sample.
    """
    d = american_to_decimal(american)
    return (1.0 + target_roi) / d


def hold_cost(prices: list[float]) -> float:
    """What the vig costs per unit staked at these prices.

    Every bet starts this far behind. At -110 both ways the number is 4.55%,
    and a 3% edge is really a 3% edge *after* paying it -- which is why the
    price you get matters as much as the side you pick.
    """
    from ..oddsmath import hold

    return hold([decimal_to_prob(american_to_decimal(a)) for a in prices])


def price_improvement_value(taken: float, alternative: float, probability: float) -> float:
    """EV gained by taking one price over another.

    Quantifies line shopping. Getting -105 instead of -115 on a 52% shot is
    worth roughly 4.5 percentage points of EV, which is larger than almost
    any handicapping edge.
    """
    return expected_value(probability, taken) - expected_value(probability, alternative)


def devig_sensitivity(raw_probs: list[float], index: int, american: float) -> dict[str, float]:
    """EV of a bet under every devig method.

    If the sign of the EV changes depending on the method, the edge is an
    artifact of the arithmetic rather than a property of the market. This is
    the check that kills the majority of apparent longshot edges.
    """
    from ..oddsmath import devig

    out: dict[str, float] = {}
    for method in ("multiplicative", "additive", "power", "shin"):
        fair = devig(raw_probs, method=method)
        out[method] = expected_value(fair[index], american)
    return out


def is_robust_edge(sensitivities: dict[str, float], min_ev: float = 0.0) -> bool:
    """True when every devig method agrees the bet clears the threshold."""
    return bool(sensitivities) and all(v > min_ev for v in sensitivities.values())


def devig_logit_deltas(raw_probs: list[float], index: int, baseline: str = "shin") -> dict[str, float]:
    """How much each devig method moves an outcome, relative to the baseline.

    Returned in log-odds so the deltas can be transplanted onto a probability
    estimated somewhere else -- specifically onto a probability that has been
    re-priced at a different line. Comparing a price at one book's number
    against another book's devigged probability is not a robustness check, it
    is a units error; this keeps the question honest, which is only ever
    "would a different vig assumption flip the sign of this edge?"
    """
    from ..oddsmath import devig

    base = devig(raw_probs, method=baseline)[index]
    if not 0.0 < base < 1.0:
        return {}
    base_logit = logit(base)

    deltas: dict[str, float] = {}
    for method in ("multiplicative", "additive", "power", "shin"):
        p = devig(raw_probs, method=method)[index]
        if 0.0 < p < 1.0:
            deltas[method] = logit(p) - base_logit
    return deltas


def robust_under_devig(
    probability: float, american: float, deltas: dict[str, float], min_ev: float = 0.0
) -> tuple[bool, dict[str, float]]:
    """Check an edge survives every vig assumption, at this bet's own line.

    Applies each method's log-odds shift to the probability actually being
    bet, then recomputes EV. Returns whether all methods clear the floor,
    plus the EV under each for reporting.
    """
    if not deltas:
        return True, {}
    d = american_to_decimal(american)
    out: dict[str, float] = {}
    for method, delta in deltas.items():
        p = expit(logit(probability) + delta)
        out[method] = p * (d - 1.0) - (1.0 - p)
    return all(v > min_ev for v in out.values()), out
