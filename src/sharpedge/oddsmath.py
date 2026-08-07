"""Odds conversion, vig removal, and line/probability modeling.

Everything downstream depends on this module being right, so it is pure
stdlib and heavily tested. Three groups of functions live here:

1. Conversions between American odds, decimal odds, and implied probability.
2. Vig ("juice") removal, which turns a book's prices into the probabilities
   the book actually believes. Four methods are provided because they
   disagree meaningfully on longshots, and which one you use changes whether
   a +450 bet looks like +EV.
3. Line/probability models, which convert a point spread or total into a
   win probability and back. This is what lets a news event measured in
   points ("their starting quarterback is out, that's worth 6.5") become a
   probability shift that can be compared against a price.
"""

from __future__ import annotations

import math
from typing import Sequence

__all__ = [
    "american_to_decimal",
    "decimal_to_american",
    "decimal_to_prob",
    "prob_to_decimal",
    "prob_to_american",
    "american_to_prob",
    "overround",
    "hold",
    "devig",
    "devig_multiplicative",
    "devig_additive",
    "devig_power",
    "devig_shin",
    "devig_worst_case",
    "shin_z",
    "logit",
    "expit",
    "SPORT_SIGMA",
    "spread_to_prob",
    "prob_to_spread",
    "total_over_prob",
    "margin_pmf",
    "push_prob",
    "half_point_value",
    "spread_to_moneyline",
    "moneyline_to_spread",
    "poisson_diff_pmf",
    "skellam_win_prob",
]

# --------------------------------------------------------------------------
# Conversions
# --------------------------------------------------------------------------


def american_to_decimal(american: float) -> float:
    """Convert American odds (-110, +150) to decimal odds (1.909, 2.50)."""
    a = float(american)
    if -100.0 < a < 100.0:
        raise ValueError(f"American odds must be <= -100 or >= +100, got {american}")
    if a > 0:
        return 1.0 + a / 100.0
    return 1.0 + 100.0 / abs(a)


def decimal_to_american(dec: float) -> float:
    """Convert decimal odds to American odds."""
    d = float(dec)
    if d <= 1.0:
        raise ValueError(f"Decimal odds must be > 1.0, got {dec}")
    if d >= 2.0:
        return (d - 1.0) * 100.0
    return -100.0 / (d - 1.0)


def decimal_to_prob(dec: float) -> float:
    """Raw implied probability of a decimal price, vig included."""
    d = float(dec)
    if d <= 1.0:
        raise ValueError(f"Decimal odds must be > 1.0, got {dec}")
    return 1.0 / d


def prob_to_decimal(p: float) -> float:
    """Fair decimal odds for a probability."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"Probability must be in (0, 1), got {p}")
    return 1.0 / p


def prob_to_american(p: float) -> float:
    """Fair American odds for a probability."""
    return decimal_to_american(prob_to_decimal(p))


def american_to_prob(american: float) -> float:
    """Raw implied probability of an American price, vig included."""
    return decimal_to_prob(american_to_decimal(american))


def overround(probs: Sequence[float]) -> float:
    """How much the raw implied probabilities exceed 1.0.

    A standard -110/-110 market is 1.0476, i.e. 4.76% overround.
    """
    return sum(probs) - 1.0


def hold(probs: Sequence[float]) -> float:
    """The book's theoretical hold: the share of handle it keeps.

    Distinct from overround. A 4.76% overround is a 4.55% hold. Hold is the
    number to compare across markets because it is what the bettor pays.
    """
    total = sum(probs)
    if total <= 0:
        raise ValueError("probabilities must sum to a positive number")
    return 1.0 - 1.0 / total


def logit(p: float) -> float:
    """Log-odds. Probabilities are averaged and adjusted in this space."""
    p = min(max(float(p), 1e-12), 1.0 - 1e-12)
    return math.log(p / (1.0 - p))


def expit(x: float) -> float:
    """Inverse of :func:`logit`."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


# --------------------------------------------------------------------------
# Vig removal
# --------------------------------------------------------------------------
#
# A book posting -110/-110 is quoting 52.38%/52.38%, which sums to 104.76%.
# The extra 4.76% is the vig, and removing it recovers what the book thinks.
# The methods differ in *where* they take the vig from, which matters most on
# lopsided markets: on a -2000/+1000 market, multiplicative and Shin devigging
# differ by enough to flip the sign of the edge.


def devig_multiplicative(probs: Sequence[float]) -> list[float]:
    """Scale every probability by the same factor so they sum to 1.

    Fast, standard, and the usual default. It implicitly assumes the book
    charges vig proportionally, which overstates longshot probabilities
    relative to what closing lines actually settle at.
    """
    total = sum(probs)
    if total <= 0:
        raise ValueError("probabilities must sum to a positive number")
    return [p / total for p in probs]


def devig_additive(probs: Sequence[float]) -> list[float]:
    """Subtract the overround equally from each outcome.

    Assumes the book charges a flat probability-point tax regardless of
    price. Tends to be too harsh on longshots -- it can drive small
    probabilities negative, so results are clamped.
    """
    n = len(probs)
    if n == 0:
        raise ValueError("need at least one outcome")
    excess = (sum(probs) - 1.0) / n
    adjusted = [max(p - excess, 1e-9) for p in probs]
    total = sum(adjusted)
    return [p / total for p in adjusted]


def devig_power(probs: Sequence[float], tol: float = 1e-12) -> list[float]:
    """Raise each probability to a common power k so that they sum to 1.

    Because every input is below 1, raising to k > 1 shrinks small
    probabilities proportionally more than large ones. That matches the
    empirical favorite-longshot bias: longshots are overpriced, so more of
    the vig belongs to them.
    """
    total = sum(probs)
    if total <= 0:
        raise ValueError("probabilities must sum to a positive number")
    if abs(total - 1.0) < tol:
        return list(probs)

    def summed(k: float) -> float:
        return sum(p**k for p in probs)

    lo, hi = 0.05, 1.0
    # sum is decreasing in k for p < 1, so search upward for a bracket.
    while summed(hi) > 1.0 and hi < 64.0:
        lo, hi = hi, hi * 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if summed(mid) > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    k = 0.5 * (lo + hi)
    out = [p**k for p in probs]
    s = sum(out)
    return [p / s for p in out]


def shin_z(probs: Sequence[float], tol: float = 1e-12) -> float:
    """Estimate Shin's z: the implied share of insider money in the market.

    Shin (1993) models the book as setting prices to protect itself against
    a proportion z of bettors who know the outcome. z is interesting on its
    own -- it rises for markets with injury uncertainty or thin liquidity,
    and it is a usable proxy for "how confident is this book in its number".
    """
    total = sum(probs)
    if total <= 1.0 + tol:
        return 0.0

    def prob_sum(z: float) -> float:
        return sum(_shin_prob(p, z, total) for p in probs)

    lo, hi = 0.0, 0.9999
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if prob_sum(mid) > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def _shin_prob(q: float, z: float, total: float) -> float:
    if z <= 0:
        return q / math.sqrt(total) if total > 0 else q
    inner = z * z + 4.0 * (1.0 - z) * (q * q) / total
    return (math.sqrt(max(inner, 0.0)) - z) / (2.0 * (1.0 - z))


def devig_shin(probs: Sequence[float]) -> list[float]:
    """Remove vig using Shin's insider-trading model.

    This is the default. Across published backtests it tracks closing-line
    settled results better than multiplicative devigging, especially on
    two-way markets priced away from even money, which is exactly where
    naive devigging manufactures phantom edges.
    """
    total = sum(probs)
    if total <= 0:
        raise ValueError("probabilities must sum to a positive number")
    z = shin_z(probs)
    out = [_shin_prob(p, z, total) for p in probs]
    s = sum(out)
    if s <= 0:
        return devig_multiplicative(probs)
    return [p / s for p in out]


_DEVIG_METHODS = {
    "multiplicative": devig_multiplicative,
    "additive": devig_additive,
    "power": devig_power,
    "shin": devig_shin,
}


def devig(probs: Sequence[float], method: str = "shin") -> list[float]:
    """Remove vig with the named method.

    Valid methods: ``shin`` (default), ``power``, ``multiplicative``,
    ``additive``, ``worst_case``.
    """
    if method == "worst_case":
        return devig_worst_case(probs)
    try:
        fn = _DEVIG_METHODS[method]
    except KeyError:
        raise ValueError(
            f"unknown devig method {method!r}; "
            f"expected one of {sorted(_DEVIG_METHODS)} or 'worst_case'"
        ) from None
    return fn(probs)


def devig_worst_case(probs: Sequence[float]) -> list[float]:
    """Take the lowest probability each outcome receives across all methods.

    The result does not sum to 1 and is not meant to -- it is a deliberately
    pessimistic estimate. Requiring a bet to clear an EV threshold under the
    worst-case devig removes most edges that exist only because of the devig
    method chosen, which is the single most common way a screen fools itself.
    """
    estimates = [fn(probs) for fn in _DEVIG_METHODS.values()]
    return [min(est[i] for est in estimates) for i in range(len(probs))]


# --------------------------------------------------------------------------
# Margin models: points <-> probability
# --------------------------------------------------------------------------

# Standard deviation of final margin around the spread, by sport. These are
# stable across seasons and are what turn "worth 6.5 points" into a number of
# percentage points.
SPORT_SIGMA: dict[str, float] = {
    "nfl": 13.2,
    "ncaaf": 16.5,
    "nba": 11.5,
    "ncaab": 10.4,
    "wnba": 10.8,
    "nhl": 1.9,  # goals; prefer the Skellam path for hockey
    "mlb": 3.1,  # runs; prefer the Skellam path for baseball
    "soccer": 1.4,
    # Games margin, best-of-3 (the large majority of tour-level matches,
    # every WTA match, most ATP matches). Best-of-5 is wider --
    # pricing.tennis.games_margin_sigma() gives the format-aware version;
    # this generic entry is the fallback for callers that only know the
    # sport, not the match format.
    "tennis": 4.1,
}

# Approximate NFL frequency of each absolute final margin. Football margins
# are famously spiky -- 3 and 7 are the most common results by a wide margin
# because of how scoring works -- and a normal curve badly misprices the half
# point around those numbers. Values are relative weights and get normalized.
_NFL_ABS_MARGIN_WEIGHTS: dict[int, float] = {
    0: 0.4, 1: 5.0, 2: 3.6, 3: 14.7, 4: 5.7, 5: 3.4, 6: 6.0, 7: 9.2,
    8: 3.5, 9: 2.4, 10: 5.6, 11: 3.1, 12: 2.0, 13: 3.2, 14: 4.8, 15: 1.6,
    16: 2.6, 17: 3.1, 18: 1.5, 19: 1.2, 20: 2.0, 21: 1.9, 22: 0.9, 23: 1.1,
    24: 1.5, 25: 0.9, 26: 0.6, 27: 0.9, 28: 0.9, 29: 0.4, 30: 0.6, 31: 0.5,
    32: 0.3, 33: 0.3, 34: 0.4, 35: 0.3, 36: 0.2, 37: 0.2, 38: 0.2, 39: 0.1,
    40: 0.2, 41: 0.1, 42: 0.1, 43: 0.1, 44: 0.1, 45: 0.1,
}

# College football is flatter than the NFL but keeps the same key numbers.
_NCAAF_ABS_MARGIN_WEIGHTS: dict[int, float] = {
    0: 0.2, 1: 3.3, 2: 2.6, 3: 9.4, 4: 3.8, 5: 2.5, 6: 3.9, 7: 7.2,
    8: 2.7, 9: 2.1, 10: 4.6, 11: 2.6, 12: 2.0, 13: 2.6, 14: 4.5, 15: 1.9,
    16: 2.3, 17: 3.2, 18: 1.8, 19: 1.6, 20: 2.3, 21: 2.6, 22: 1.4, 23: 1.4,
    24: 2.0, 25: 1.3, 26: 1.1, 27: 1.3, 28: 1.7, 29: 0.9, 30: 1.1, 31: 1.0,
    32: 0.7, 33: 0.7, 34: 1.0, 35: 0.8, 36: 0.6, 37: 0.5, 38: 0.6, 39: 0.4,
    40: 0.5, 41: 0.3, 42: 0.4, 43: 0.3, 44: 0.3, 45: 0.3,
}

_KEY_NUMBER_TABLES = {
    "nfl": _NFL_ABS_MARGIN_WEIGHTS,
    "ncaaf": _NCAAF_ABS_MARGIN_WEIGHTS,
}


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _normal_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def sport_sigma(sport: str) -> float:
    """Margin standard deviation for a sport, defaulting to NFL-like."""
    return SPORT_SIGMA.get(sport.lower(), 13.0)


def spread_to_prob(spread: float, sport: str = "nfl", sigma: float | None = None) -> float:
    """Win probability for a team laying ``spread`` points.

    ``spread`` follows betting convention: -7.0 means the team is favored by
    seven. A team favored by 7 in the NFL wins roughly 70% of the time.
    """
    s = sigma if sigma is not None else sport_sigma(sport)
    if s <= 0:
        raise ValueError("sigma must be positive")
    return _normal_cdf(-spread / s)


def prob_to_spread(prob: float, sport: str = "nfl", sigma: float | None = None) -> float:
    """Point spread implied by a win probability. Inverse of :func:`spread_to_prob`."""
    if not 0.0 < prob < 1.0:
        raise ValueError(f"probability must be in (0, 1), got {prob}")
    s = sigma if sigma is not None else sport_sigma(sport)
    return -_normal_ppf(prob) * s


def _normal_ppf(p: float) -> float:
    """Inverse normal CDF (Acklam's rational approximation, refined by Halley)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    elif p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    else:
        q = p - 0.5
        r = q * q
        x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    # One Halley step to clean up the approximation.
    e = _normal_cdf(x) - p
    u = e * math.sqrt(2.0 * math.pi) * math.exp(x * x / 2.0)
    return x - u / (1.0 + x * u / 2.0)


def total_over_prob(
    line: float, projected_total: float, sport: str = "nfl", sigma: float | None = None
) -> float:
    """Probability the game goes over ``line`` given a projected total.

    Totals are noisier than margins because both teams' scoring adds rather
    than cancels, so sigma is scaled up.
    """
    s = sigma if sigma is not None else sport_sigma(sport) * 1.15
    return 1.0 - _normal_cdf((line - projected_total) / s)


def margin_pmf(margin: int, spread: float, sport: str = "nfl") -> float:
    """Probability the favorite wins by exactly ``margin`` points.

    Football uses an empirical table shifted to the spread so that the key
    numbers stay where they belong; other sports fall back to a discretized
    normal. This is what makes half points around 3 and 7 cost what they
    should.
    """
    table = _KEY_NUMBER_TABLES.get(sport.lower())
    sigma = sport_sigma(sport)
    if table is None:
        return _normal_cdf((margin + 0.5 + spread) / sigma) - _normal_cdf(
            (margin - 0.5 + spread) / sigma
        )

    # Blend the empirical shape (which carries the key numbers) with a normal
    # centered on the spread (which carries the game-specific expectation).
    total_weight = sum(table.values()) * 2.0 - table.get(0, 0.0)
    shape = table.get(abs(margin), 0.0) / total_weight
    center = -spread
    normal_weight = _normal_pdf((margin - center) / sigma) / sigma
    flat = _normal_pdf(0.0) / sigma
    return shape * (normal_weight / flat if flat > 0 else 1.0)


def push_prob(line: float, sport: str = "nfl") -> float:
    """Probability a spread lands exactly on ``line`` (a push).

    Zero for half-point lines. For whole numbers in football this is large
    enough to matter: a game landing on 3 happens often enough that -3 and
    -3.5 are genuinely different bets.
    """
    if abs(line - round(line)) > 1e-9:
        return 0.0
    key = abs(int(round(line)))
    table = _KEY_NUMBER_TABLES.get(sport.lower())
    if table is None:
        sigma = sport_sigma(sport)
        return _normal_pdf(0.0) / sigma
    total_weight = sum(table.values()) * 2.0 - table.get(0, 0.0)
    return table.get(key, 0.0) / total_weight


def half_point_value(line: float, sport: str = "nfl") -> float:
    """Win-probability gained by moving a spread half a point in your favor.

    Moving from -3 to -2.5 buys the pushes at 3 plus half the outright
    threes; the function returns the probability mass crossed. Compare it
    against what the book charges to buy the half point -- most books
    overcharge everywhere except the key numbers, where they undercharge.
    """
    lo = math.floor(min(line, line + 0.5) * 2) / 2
    crossed = 0.0
    for candidate in (math.floor(line), math.ceil(line)):
        if min(line, line + 0.5) <= candidate <= max(line, line + 0.5):
            crossed += push_prob(float(candidate), sport)
    if crossed == 0.0:
        sigma = sport_sigma(sport)
        crossed = 0.5 * _normal_pdf((lo + spread_epsilon()) / sigma) / sigma
    return crossed


def spread_epsilon() -> float:
    """Small offset used when a half-point move crosses no whole number."""
    return 0.0


def spread_to_moneyline(spread: float, sport: str = "nfl") -> float:
    """Fair moneyline (American) implied by a point spread.

    Useful as a cross-market consistency check: when a book's moneyline and
    its own spread disagree by more than the vig, one of them is stale.
    """
    return prob_to_american(spread_to_prob(spread, sport))


def moneyline_to_spread(american: float, sport: str = "nfl") -> float:
    """Fair point spread implied by a moneyline price (vig not removed)."""
    return prob_to_spread(american_to_prob(american), sport)


# --------------------------------------------------------------------------
# Low-scoring sports: Skellam (difference of two Poissons)
# --------------------------------------------------------------------------
#
# Hockey, baseball, and soccer margins are small integers, and a normal curve
# both misses the discreteness and gets the tails wrong. The difference of two
# Poisson variables is the right shape, and the sum converges fast enough to
# evaluate directly.


def poisson_diff_pmf(lam_a: float, lam_b: float, k: int, terms: int = 60) -> float:
    """P(A - B == k) where A ~ Poisson(lam_a), B ~ Poisson(lam_b)."""
    if lam_a <= 0 or lam_b <= 0:
        raise ValueError("rates must be positive")
    total = 0.0
    for j in range(0, terms):
        i = k + j
        if i < 0:
            continue
        log_p = (
            -lam_a - lam_b
            + i * math.log(lam_a)
            + j * math.log(lam_b)
            - math.lgamma(i + 1)
            - math.lgamma(j + 1)
        )
        total += math.exp(log_p)
    return total


def skellam_win_prob(lam_a: float, lam_b: float, terms: int = 60) -> tuple[float, float, float]:
    """Return (P(A wins), P(draw), P(B wins)) for two Poisson scoring rates.

    For hockey and baseball the draw mass is what regulation ties become, and
    it has to be redistributed by the overtime rules rather than ignored.
    """
    p_draw = poisson_diff_pmf(lam_a, lam_b, 0, terms)
    p_a = sum(poisson_diff_pmf(lam_a, lam_b, k, terms) for k in range(1, terms))
    p_b = sum(poisson_diff_pmf(lam_a, lam_b, -k, terms) for k in range(1, terms))
    total = p_a + p_b + p_draw
    if total <= 0:
        raise ValueError("degenerate scoring rates")
    return p_a / total, p_draw / total, p_b / total
