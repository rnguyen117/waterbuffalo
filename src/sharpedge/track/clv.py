"""Closing line value reporting.

CLV is the scoreboard that matters. Results over a season are dominated by
variance -- a genuine 3% edge over 500 bets still loses money about a quarter
of the time -- while CLV is measurable on every single bet the moment the
game starts.

The practical reading:

* Consistently positive CLV and negative results: you are fine, keep going.
* Consistently negative CLV and positive results: you got lucky, and the
  approach is losing. This is the dangerous case, because the profit hides it.
* Negative CLV and negative results: the model is not finding edges.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..market.movement import beat_close_rate, clv_significance, expected_roi_from_clv
from .ledger import Ledger, LedgerEntry


@dataclass
class CLVReport:
    n: int
    mean_clv: float
    median_clv: float
    beat_close: float
    t_stat: float
    verdict: str
    projected_roi: float
    by_book: dict[str, float]
    by_market: dict[str, float]

    @property
    def summary(self) -> str:
        return (
            f"{self.n} bets with a closing price recorded. Average CLV "
            f"{self.mean_clv:+.2%}, beating the close on {self.beat_close:.0%} of bets "
            f"(t = {self.t_stat:.2f}). {self.verdict}."
        )


def analyze(ledger: Ledger) -> CLVReport:
    """Compute CLV across every bet that has a closing price attached."""
    entries = [e for e in ledger.all() if e.clv is not None]
    return analyze_entries(entries)


def analyze_entries(entries: list[LedgerEntry]) -> CLVReport:
    values = [e.clv for e in entries if e.clv is not None]
    if not values:
        return CLVReport(0, 0.0, 0.0, 0.0, 0.0, "no closing prices recorded yet",
                         0.0, {}, {})

    ordered = sorted(values)
    mid = len(ordered) // 2
    median = (
        ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    )
    mean = sum(values) / len(values)
    t, verdict = clv_significance(values)

    return CLVReport(
        n=len(values),
        mean_clv=mean,
        median_clv=median,
        beat_close=beat_close_rate(values),
        t_stat=t,
        verdict=verdict,
        projected_roi=expected_roi_from_clv(mean),
        by_book=_group(entries, lambda e: e.book),
        by_market=_group(entries, lambda e: e.market_type),
    )


def _group(entries: list[LedgerEntry], key) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for entry in entries:
        if entry.clv is None:
            continue
        buckets.setdefault(key(entry), []).append(entry.clv)
    return {k: sum(v) / len(v) for k, v in sorted(buckets.items())}


def diagnose(report: CLVReport, roi: float) -> str:
    """Interpret CLV against realized results.

    The four-quadrant read is the single most useful thing a bettor can do
    with their own history, and almost nobody does it.
    """
    if report.n < 50:
        return (
            "Not enough graded bets to draw conclusions. CLV stabilizes far faster "
            "than profit, but it still needs a few hundred bets."
        )

    positive_clv = report.mean_clv > 0.005
    positive_roi = roi > 0

    if positive_clv and positive_roi:
        return (
            "Beating the close and making money. The results are consistent with a "
            "real edge; keep the process unchanged and let sample size accumulate."
        )
    if positive_clv and not positive_roi:
        return (
            "Beating the close but losing money. This is what a real edge inside a "
            "bad run looks like. Nothing here calls for a change -- variance over a "
            "few hundred bets is larger than most people expect."
        )
    if not positive_clv and positive_roi:
        return (
            "Making money while losing to the close. This is the dangerous quadrant: "
            "the profit is most likely luck, and the process is not finding edges. "
            "Cut stake sizes and audit where the model disagrees with the market."
        )
    return (
        "Losing to the close and losing money. The model is not identifying value. "
        "Stop sizing off it and go back to the structural edges -- line shopping, "
        "stale lines, and promotions -- which do not depend on prediction."
    )
