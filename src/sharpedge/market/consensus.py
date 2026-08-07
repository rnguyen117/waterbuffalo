"""Sharp consensus pricing: reconstructing what the market actually believes.

This module is the answer to "take Vegas into account and how they think".

The premise, which is the most heavily replicated result in sports betting
research: the closing line at a high-limit book is a better forecast than
essentially any public model. Books do not set numbers by predicting games in
isolation -- they open near their own model, then let informed money move
them, and the number that survives that process aggregates more information
than any single estimate. Beating it consistently from a laptop is not
realistic.

So the strategy is not to out-predict Vegas. It is to:

  1. Reconstruct the sharp number precisely, stripping vig correctly and
     weighting books by how much their opinion is worth.
  2. Measure how much books disagree, because that dispersion is the honest
     error bar on the consensus and it should shrink your stakes.
  3. Separate the sharp number from the retail number. Retail books shade
     prices toward the popular side to balance action against a public that
     reliably prefers favorites, overs, and famous teams. That gap is not
     noise -- it is a measurable, directional bias, and it points at where
     value sits.
  4. Find prices that have not caught up to the sharp number yet.

The output is a :class:`~sharpedge.models.FairPrice` per outcome carrying the
probability, its uncertainty, and the sharp/retail split.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime

from ..models import FairPrice, Market, MarketType, Price, utcnow
from ..oddsmath import devig, devig_worst_case, expit, hold, logit
from .books import consensus_weight, get_book


# ---------------------------------------------------------------------------
# Per-book devigging
# ---------------------------------------------------------------------------


def devigged_book_probs(
    market: Market, book: str, method: str = "shin"
) -> dict[str, float] | None:
    """Vig-free probabilities implied by one book's prices for one market.

    Returns ``None`` if the book has not posted every outcome, because a
    partial market carries no information about the book's true opinion --
    you cannot tell a shaded price from a fair one without its counterpart.
    """
    if not market.complete_at(book):
        return None
    prices = {}
    for outcome in market.outcomes:
        matching = [p for p in market.by_book(book) if p.outcome == outcome]
        if not matching:
            return None
        # If a book posts several lines (alternates), the one nearest the
        # market's main line is the one that reflects its true opinion.
        prices[outcome] = max(matching, key=lambda p: p.timestamp)
    raw = [prices[o].implied for o in market.outcomes]
    if sum(raw) <= 1.0:
        # Sub-100% book: either an exchange after commission or a data error.
        # Either way it is a genuine (possibly arbitrage) price, so keep the
        # shape but normalize rather than "removing" negative vig.
        total = sum(raw)
        if total <= 0:
            return None
        fair = [r / total for r in raw]
    else:
        fair = devig(raw, method=method)
    return dict(zip(market.outcomes, fair))


def _book_line(market: Market, book: str, outcome: str) -> float | None:
    """The line a book most recently posted for one outcome.

    Mirrors the price selection in :func:`devigged_book_probs` (latest by
    timestamp) so the line and the probability always describe the same
    quote.
    """
    matching = [p for p in market.by_book(book) if p.outcome == outcome]
    if not matching:
        return None
    return max(matching, key=lambda p: p.timestamp).line


def book_hold(market: Market, book: str) -> float | None:
    """Theoretical hold on one book's version of a market."""
    if not market.complete_at(book):
        return None
    raw = []
    for outcome in market.outcomes:
        matching = [p for p in market.by_book(book) if p.outcome == outcome]
        if not matching:
            return None
        raw.append(max(matching, key=lambda p: p.timestamp).implied)
    return hold(raw)


# ---------------------------------------------------------------------------
# Time weighting
# ---------------------------------------------------------------------------


def recency_weight(price_time: datetime, now: datetime | None = None, half_life_min: float = 45.0) -> float:
    """Exponential decay on stale quotes.

    A price from six hours ago is a statement about a different information
    set. Decaying it stops a book that stopped updating from anchoring the
    consensus -- while still letting the stale price itself be flagged as an
    opportunity elsewhere.
    """
    now = now or utcnow()
    age_min = max((now - price_time).total_seconds() / 60.0, 0.0)
    return 0.5 ** (age_min / half_life_min)


def market_maturity(hours_to_start: float) -> float:
    """How much the market has converged, 0 (just opened) to 1 (at the bell).

    Lines sharpen monotonically toward kickoff as limits rise and informed
    money arrives. Early numbers offer more edge but are far noisier, and
    treating a Tuesday number with the same confidence as a Sunday-morning
    number is a good way to mistake noise for signal.
    """
    if hours_to_start <= 0:
        return 1.0
    if hours_to_start >= 168:
        return 0.25
    # Roughly logarithmic convergence over the week before kickoff.
    return max(0.25, min(1.0, 1.0 - math.log10(1.0 + hours_to_start) / 2.6))


# ---------------------------------------------------------------------------
# Consensus
# ---------------------------------------------------------------------------


def fair_prices(
    market: Market,
    now: datetime | None = None,
    method: str = "shin",
    hours_to_start: float = 24.0,
    half_life_min: float = 45.0,
    min_books: int = 2,
    sport: str = "nfl",
) -> dict[str, FairPrice]:
    """Estimate the true probability of every outcome in a market.

    Books are devigged individually, converted to log-odds, and averaged with
    weights combining sharpness, limit size, and recency. Log-odds rather
    than raw probabilities because averaging probabilities directly biases
    the result toward 50% and compresses exactly the longshot region where
    the disagreements matter.

    For markets with a line, every book's cover probability is first
    translated onto a common reference line before it is averaged. This
    matters more than it looks. On a near-even game, different books can
    disagree about which side is the technical favorite -- one book has the
    home team -1.5, another has it +1.5 -- purely because their internal
    models sit on opposite sides of a coin flip. Averaging "P(cover -1.5)"
    directly against "P(cover +1.5)" treats those as samples of the same
    claim, which they are not, and the blended result is close to a
    meaningless 50% no matter what either book actually believes. Once both
    are converted to what they imply about a shared reference number, the
    real (and usually much smaller) disagreement is what gets averaged.
    Skipping this step is how a genuinely small 5-point difference of opinion
    on a near-pick'em game turns into a fabricated 50%-EV bet.
    """
    now = now or utcnow()
    per_book: dict[str, dict[str, float]] = {}
    weights: dict[str, float] = {}
    holds: list[float] = []

    for book_key in market.books():
        probs = devigged_book_probs(market, book_key, method=method)
        if probs is None:
            continue
        book = get_book(book_key)
        latest = max(
            (p.timestamp for p in market.by_book(book_key)), default=now
        )
        weight = consensus_weight(book) * recency_weight(latest, now, half_life_min)
        if weight <= 1e-6:
            continue
        per_book[book_key] = probs
        weights[book_key] = weight
        h = book_hold(market, book_key)
        if h is not None:
            holds.append(h)

    if len(per_book) < min_books:
        return {}

    sharp_keys = [k for k in per_book if get_book(k).is_sharp]
    retail_keys = [k for k in per_book if not get_book(k).is_sharp]

    # A market maker in the pool dominates by design: when Pinnacle or Circa
    # has posted, their number is the number, and twenty retail books echoing
    # each other should not outvote it.
    if sharp_keys:
        sharp_mass = sum(weights[k] for k in sharp_keys)
        total_mass = sum(weights.values())
        floor = 0.55 * total_mass
        if sharp_mass < floor and sharp_mass > 0:
            boost = floor / sharp_mass
            for k in sharp_keys:
                weights[k] *= boost

    maturity = market_maturity(hours_to_start)
    results: dict[str, FairPrice] = {}
    normalize_lines = market.market_type.is_spread_like or market.market_type.is_total_like
    is_total = market.market_type.is_total_like

    for outcome in market.outcomes:
        # Pick the reference line first, before translating anyone onto it.
        # A weighted average of the raw posted lines is a fine target -- it
        # does not need to be a real market number, only a fixed point every
        # book's quote gets converted onto so the averaging step is comparing
        # like with like.
        reference_line = consensus_line(market, outcome, weights) if normalize_lines else None
        is_over = outcome.lower().startswith("over")

        # Translate every book onto the reference line once, then reuse the
        # result both for the overall average and for the sharp/retail split
        # below. Computing this twice with two different code paths is how a
        # fix like this quietly stays half-applied.
        translated: dict[str, float] = {}
        for book_key, probs in per_book.items():
            p = probs.get(outcome)
            if p is None or not 0.0 < p < 1.0:
                continue
            if reference_line is not None:
                book_line = _book_line(market, book_key, outcome)
                if book_line is not None and abs(book_line - reference_line) > 1e-9:
                    p = probability_at_line(
                        consensus_probability=p,
                        consensus_line=book_line,
                        target_line=reference_line,
                        sport=sport,
                        is_total=is_total,
                        is_over=is_over,
                    )
                    p = min(max(p, 1e-6), 1.0 - 1e-6)
            translated[book_key] = p

        if not translated:
            continue

        logits = [logit(p) for p in translated.values()]
        wts = [weights[k] for k in translated]

        total_w = sum(wts)
        mean_logit = sum(l * w for l, w in zip(logits, wts)) / total_w

        # Dispersion across books, weighted. This is the error bar.
        if len(logits) > 1:
            var = sum(w * (l - mean_logit) ** 2 for l, w in zip(logits, wts)) / total_w
            dispersion = math.sqrt(max(var, 0.0))
        else:
            dispersion = 0.35  # single-source markets get a wide default

        # Immature markets deserve a wider error bar even when books happen
        # to agree, because they agree by copying rather than by converging.
        sigma = dispersion / max(maturity, 0.25) ** 0.5
        sigma = max(sigma, 0.02)

        sharp_p = _weighted_prob(translated, weights, sharp_keys)
        retail_p = _weighted_prob(translated, weights, retail_keys)
        bias = 0.0
        if sharp_p is not None and retail_p is not None:
            bias = logit(retail_p) - logit(sharp_p)

        results[outcome] = FairPrice(
            outcome=outcome,
            probability=expit(mean_logit),
            sigma_logit=sigma,
            n_books=len(logits),
            n_sharp_books=len(sharp_keys),
            sharp_probability=sharp_p,
            retail_probability=retail_p,
            consensus_line=reference_line if normalize_lines else consensus_line(market, outcome, weights),
            market_hold=statistics.median(holds) if holds else None,
            retail_bias=bias,
        )

    return _renormalize(results, market.outcomes)


def _weighted_prob(
    probs: dict[str, float],
    weights: dict[str, float],
    keys: list[str],
) -> float | None:
    """Weighted log-odds average of a (book -> probability) map, restricted to keys."""
    logits, wts = [], []
    for k in keys:
        p = probs.get(k)
        if p is None or not 0.0 < p < 1.0:
            continue
        logits.append(logit(p))
        wts.append(weights[k])
    if not logits:
        return None
    return expit(sum(l * w for l, w in zip(logits, wts)) / sum(wts))


def _renormalize(
    results: dict[str, FairPrice], outcomes: list[str]
) -> dict[str, FairPrice]:
    """Force the consensus probabilities to sum to 1.

    Averaging each outcome independently in log-odds does not guarantee
    coherence. Small corrections here keep EV calculations honest; without
    it a two-way market can quietly sum to 1.01 and hand every outcome a
    free percentage point of fake edge.
    """
    present = [o for o in outcomes if o in results]
    if len(present) < 2:
        return results
    total = sum(results[o].probability for o in present)
    if total <= 0 or abs(total - 1.0) < 1e-9:
        return results
    for o in present:
        fp = results[o]
        fp.probability = fp.probability / total
    return results


def consensus_line(
    market: Market, outcome: str, weights: dict[str, float]
) -> float | None:
    """The weighted-average line (spread or total) across books.

    This is "the number" -- what a sharp shop has the game at. Comparing an
    individual book's posted line against it is how stale lines surface.
    """
    values, wts = [], []
    for price in market.prices_for(outcome):
        if price.line is None:
            continue
        w = weights.get(price.book)
        if w is None:
            continue
        values.append(price.line)
        wts.append(w)
    if not values:
        return None
    return sum(v * w for v, w in zip(values, wts)) / sum(wts)


def implied_expected_margin(
    consensus_probability: float, consensus_line: float, sport: str, is_total: bool = False
) -> float:
    """Recover the market's expected margin (or total) from its price and line.

    The market tells us two things -- the number it posted and the price it
    charges on each side of that number -- and together they pin down the
    distribution's center. For a spread, covering line L means the margin
    plus L exceeds zero, so the expected margin follows directly from
    inverting the normal at the consensus probability.
    """
    from ..oddsmath import _normal_ppf, sport_sigma

    sigma = sport_sigma(sport) * (1.15 if is_total else 1.0)
    if is_total:
        # P(total > L) = consensus_probability  =>  mu = L + sigma * z
        return consensus_line + sigma * _normal_ppf(consensus_probability)
    # P(margin + L > 0) = consensus_probability  =>  m = sigma * z - L
    return sigma * _normal_ppf(consensus_probability) - consensus_line


def probability_at_line(
    consensus_probability: float,
    consensus_line: float,
    target_line: float,
    sport: str,
    is_total: bool = False,
    is_over: bool = True,
) -> float:
    """Re-price an outcome at a different number.

    Essential for line shopping. A book offering +2.5 and one offering +1.5
    are not selling the same bet, and comparing their prices directly
    manufactures an edge equal to the point of difference. This converts both
    to a common footing by asking what each specific number is actually
    worth against the market's implied expectation.
    """
    from ..oddsmath import _normal_cdf, sport_sigma

    if abs(target_line - consensus_line) < 1e-9:
        return consensus_probability

    sigma = sport_sigma(sport) * (1.15 if is_total else 1.0)
    center = implied_expected_margin(
        consensus_probability, consensus_line, sport, is_total
    )

    if is_total:
        over = 1.0 - _normal_cdf((target_line - center) / sigma)
        return over if is_over else 1.0 - over

    return _normal_cdf((center + target_line) / sigma)


def sharp_line(market: Market, outcome: str) -> float | None:
    """The line at market-making books only, ignoring retail entirely."""
    values, wts = [], []
    for price in market.prices_for(outcome):
        book = get_book(price.book)
        if not book.is_sharp or price.line is None:
            continue
        values.append(price.line)
        wts.append(consensus_weight(book))
    if not values:
        return None
    return sum(v * w for v, w in zip(values, wts)) / sum(wts)


def conservative_probs(market: Market) -> dict[str, float]:
    """Worst-case probability per outcome across every devig method and book.

    Used as the pessimistic screen. A bet that is still +EV when every book
    is devigged the least generous way, and the least generous book is the
    one believed, is a bet whose edge does not depend on a methodology
    choice. Most apparent edges do not survive this, which is the point.
    """
    out: dict[str, float] = {}
    for book_key in market.books():
        if not market.complete_at(book_key):
            continue
        raw = []
        ok = True
        for outcome in market.outcomes:
            matching = [p for p in market.by_book(book_key) if p.outcome == outcome]
            if not matching:
                ok = False
                break
            raw.append(max(matching, key=lambda p: p.timestamp).implied)
        if not ok or sum(raw) <= 0:
            continue
        worst = devig_worst_case(raw)
        for outcome, p in zip(market.outcomes, worst):
            book = get_book(book_key)
            # Only sharp books get to define the pessimistic bound; a soft
            # book's bad price should not lower our estimate of the truth.
            if not book.is_sharp and book.tier.value != "retail_sharp":
                continue
            if outcome not in out or p < out[outcome]:
                out[outcome] = p
    return out


def retail_shading(fair: FairPrice) -> str:
    """Human-readable read on the sharp/retail gap for one outcome.

    Retail books shade toward whatever the public wants, because they profit
    from hold rather than from being right. When retail prices an outcome
    materially above the sharp number, the public is on it and the other
    side is where the price is soft.
    """
    b = fair.retail_bias
    if abs(b) < 0.02:
        return "retail and sharp agree"
    direction = "above" if b > 0 else "below"
    magnitude = "sharply" if abs(b) > 0.08 else "slightly"
    side = "public side, price inflated" if b > 0 else "unpopular side, price soft"
    return f"retail prices this {magnitude} {direction} the sharp number ({side})"


def implied_market_line(
    market_type: MarketType, fair: dict[str, FairPrice], sport: str
) -> float | None:
    """Back out the spread the consensus probability corresponds to.

    Lets a moneyline consensus be compared against a posted spread, which is
    how cross-market inconsistencies at a single book get caught.
    """
    from ..oddsmath import prob_to_spread

    if market_type != MarketType.MONEYLINE or len(fair) != 2:
        return None
    first = next(iter(fair.values()))
    return prob_to_spread(first.probability, sport)
