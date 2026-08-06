"""Calibration: are the model's probabilities honest?

A model that says 60% should win 60% of the time. If its 60% bets win 52% of
the time, the model is not unlucky, it is miscalibrated, and every stake it
recommends is too large.

This is the diagnostic that separates "I had a bad month" from "my numbers
are wrong", and it converges much faster than profit does because it uses
every bet's probability rather than just the win/loss outcome.

The output feeds back into staking: a measured overconfidence factor becomes
a shrinkage parameter, so the system corrects itself instead of requiring the
operator to notice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class CalibrationBin:
    low: float
    high: float
    count: int
    predicted: float   # mean predicted probability in the bin
    actual: float      # observed win rate

    @property
    def error(self) -> float:
        return self.predicted - self.actual

    @property
    def label(self) -> str:
        return f"{self.low:.0%}-{self.high:.0%}"


@dataclass
class CalibrationReport:
    bins: list[CalibrationBin]
    brier: float
    log_loss: float
    expected_calibration_error: float
    overconfidence: float   # >1 means the model claims more edge than it has
    n: int

    @property
    def verdict(self) -> str:
        if self.n < 100:
            return "too few settled bets to judge calibration yet"
        if self.expected_calibration_error < 0.02:
            return "well calibrated"
        if self.expected_calibration_error < 0.05:
            return "acceptable, with some drift at the extremes"
        if self.overconfidence > 1.15:
            return (
                "overconfident -- the model claims more edge than it delivers; "
                "raise market_trust and cut the Kelly multiplier"
            )
        return "poorly calibrated -- do not size off these probabilities"


def brier_score(predictions: list[float], outcomes: list[int]) -> float:
    """Mean squared error of probability forecasts. Lower is better.

    A model that always says 50% scores 0.25. Anything worse than that on
    binary sports outcomes means the probabilities are actively harmful.
    """
    if not predictions:
        return 0.0
    return sum((p - o) ** 2 for p, o in zip(predictions, outcomes)) / len(predictions)


def log_loss(predictions: list[float], outcomes: list[int], eps: float = 1e-9) -> float:
    """Log loss, which punishes confident mistakes far harder than Brier does.

    The right metric when overconfidence is the failure you fear, which for a
    Kelly-staked bettor it is.
    """
    if not predictions:
        return 0.0
    total = 0.0
    for p, o in zip(predictions, outcomes):
        p = min(max(p, eps), 1.0 - eps)
        total -= math.log(p) if o else math.log(1.0 - p)
    return total / len(predictions)


def calibration_bins(
    predictions: list[float], outcomes: list[int], n_bins: int = 10
) -> list[CalibrationBin]:
    """Group forecasts into probability bands and compare predicted to actual."""
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, o in zip(predictions, outcomes):
        idx = min(int(p * n_bins), n_bins - 1)
        buckets[idx].append((p, o))

    bins: list[CalibrationBin] = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        bins.append(
            CalibrationBin(
                low=i / n_bins,
                high=(i + 1) / n_bins,
                count=len(bucket),
                predicted=sum(p for p, _ in bucket) / len(bucket),
                actual=sum(o for _, o in bucket) / len(bucket),
            )
        )
    return bins


def expected_calibration_error(bins: list[CalibrationBin]) -> float:
    """Weighted average gap between predicted and actual across bins."""
    total = sum(b.count for b in bins)
    if total == 0:
        return 0.0
    return sum(b.count * abs(b.error) for b in bins) / total


def overconfidence_factor(predictions: list[float], outcomes: list[int]) -> float:
    """How much the model exaggerates its distance from the coin flip.

    Fits a single scaling factor on the log-odds: predicted log-odds times
    1/factor best matches reality. A factor of 1.3 means every edge the model
    claims should be cut by roughly a quarter, which is directly actionable
    as a shrinkage parameter.
    """
    pairs = [
        (p, o) for p, o in zip(predictions, outcomes) if 1e-6 < p < 1 - 1e-6
    ]
    if len(pairs) < 30:
        return 1.0

    def loss(scale: float) -> float:
        total = 0.0
        for p, o in pairs:
            z = math.log(p / (1 - p)) / max(scale, 1e-6)
            q = 1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
            q = min(max(q, 1e-9), 1 - 1e-9)
            total -= math.log(q) if o else math.log(1 - q)
        return total

    # Golden-section search over a sensible range of scaling factors.
    lo, hi = 0.4, 3.0
    phi = (math.sqrt(5) - 1) / 2
    a, b = hi - phi * (hi - lo), lo + phi * (hi - lo)
    fa, fb = loss(a), loss(b)
    for _ in range(60):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - phi * (hi - lo)
            fa = loss(a)
        else:
            lo, a, fa = a, b, fb
            b = lo + phi * (hi - lo)
            fb = loss(b)
    return (lo + hi) / 2


def analyze(predictions: list[float], outcomes: list[int], n_bins: int = 10) -> CalibrationReport:
    """Full calibration assessment."""
    bins = calibration_bins(predictions, outcomes, n_bins)
    return CalibrationReport(
        bins=bins,
        brier=brier_score(predictions, outcomes),
        log_loss=log_loss(predictions, outcomes),
        expected_calibration_error=expected_calibration_error(bins),
        overconfidence=overconfidence_factor(predictions, outcomes),
        n=len(predictions),
    )


def suggested_market_trust(report: CalibrationReport, current: float) -> float:
    """Recommend a new market_trust setting from measured calibration.

    Closes the loop: if the model has been overconfident, defer more to the
    market. Bounded so a small sample cannot swing the configuration wildly.
    """
    if report.n < 150:
        return current
    if report.overconfidence <= 1.0:
        adjustment = -0.05
    else:
        adjustment = min((report.overconfidence - 1.0) * 0.4, 0.15)
    return min(max(current + adjustment, 0.30), 0.85)
