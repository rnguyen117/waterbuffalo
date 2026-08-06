"""Prop pricing: every bet inside every bet.

Three distinct edges live in prop markets, and they are worth separating
because they have different reliability.

**1. Ladder inconsistency (strongest).** A book posts one anchor line and a
stack of alternates. Fit a distribution to the anchor, derive what every
alternate should cost, and compare. Books generate alternates with a simple
multiplier rather than from the model that produced the anchor, so the tails
are routinely wrong. This edge does not require out-projecting anyone -- it
uses the book's own number as truth and only checks its internal consistency.
When it fires, you are betting that a book disagrees with itself.

**2. Cross-book anchor disagreement (standard).** The same prop priced at 6.5
somewhere and 7.5 elsewhere. Ordinary line shopping, but props disagree far
more than sides because fewer books post them and none of them are being
corrected by sharp money.

**3. Stale props after news (highest value, shortest window).** A side moves
within seconds of an injury; the related props move in minutes, and sometimes
not until someone manually pulls them. When a starting point guard is ruled
out, his backup's assist prop is wrong right now.

The public-money angle matters here more than anywhere else in betting. Prop
handle is overwhelmingly recreational, and recreational bettors bet overs --
they are betting on a player to do something, not to fail to. Books know this
and shade prop overs accordingly. The systematic consequence is that prop
unders carry structural value, which is measured explicitly below rather than
assumed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..models import Market, MarketType, Price
from ..oddsmath import american_to_prob, devig, expit, logit, prob_to_american
from ..pricing.distributions import (
    Distribution,
    build,
    fit_to_market,
    model_for,
    push_probability,
    standard_ladder,
)
from .books import get_book
from .taxonomy import PROPS_BY_STAT, profile_for


# The share of prop tickets that land on the over. This is one of the most
# consistent facts in sportsbook data, and it is why prop overs are shaded.
PROP_OVER_TICKET_SHARE: dict[str, float] = {
    "anytime_td": 0.88,
    "home_runs": 0.86,
    "passing_tds": 0.78,
    "threes_made": 0.76,
    "points": 0.74,
    "total_bases": 0.74,
    "strikeouts": 0.72,
    "receptions": 0.71,
    "receiving_yards": 0.70,
    "passing_yards": 0.69,
    "rushing_yards": 0.69,
    "assists": 0.68,
    "rebounds": 0.68,
    "shots_on_goal": 0.67,
    "saves": 0.58,   # the exception: unders are the popular side on saves
}

DEFAULT_OVER_SHARE = 0.70

# Rungs implying a probability outside this band are not priced. Below roughly
# 3% the fit is pure extrapolation and the model error dwarfs any edge.
TAIL_FLOOR = 0.03


@dataclass
class PropQuote:
    """One book's version of a prop at one line."""

    book: str
    line: float
    over_american: float | None = None
    under_american: float | None = None

    @property
    def complete(self) -> bool:
        return self.over_american is not None and self.under_american is not None

    def fair_over(self, method: str = "shin") -> float | None:
        """Vig-free over probability at this book's line."""
        if not self.complete:
            return None
        raw = [american_to_prob(self.over_american), american_to_prob(self.under_american)]
        if sum(raw) <= 1.0:
            total = sum(raw)
            return raw[0] / total if total > 0 else None
        return devig(raw, method=method)[0]

    def hold(self) -> float | None:
        if not self.complete:
            return None
        raw = [american_to_prob(self.over_american), american_to_prob(self.under_american)]
        return 1.0 - 1.0 / sum(raw)


@dataclass
class PropMarket:
    """Every quote for one player-stat combination, across books and lines."""

    player: str
    stat: str
    sport: str
    event_id: str
    quotes: list[PropQuote] = field(default_factory=list)

    @property
    def anchor_line(self) -> float | None:
        """The most commonly posted line, which is the book's real opinion.

        Alternates hang off this number, so it is the one to fit against.
        """
        counts: dict[float, int] = {}
        for q in self.quotes:
            if q.complete:
                counts[q.line] = counts.get(q.line, 0) + 1
        if not counts:
            return None
        best = max(counts.values())
        # Break ties toward the median line rather than an arbitrary one.
        candidates = sorted(l for l, c in counts.items() if c == best)
        return candidates[len(candidates) // 2]

    def quotes_at(self, line: float) -> list[PropQuote]:
        return [q for q in self.quotes if abs(q.line - line) < 1e-9 and q.complete]

    def lines(self) -> list[float]:
        return sorted({q.line for q in self.quotes})


# ---------------------------------------------------------------------------
# Anchor pricing
# ---------------------------------------------------------------------------


def anchor_probability(
    prop: PropMarket, method: str = "shin", correct_over_bias: bool = True
) -> tuple[float, float, int] | None:
    """Consensus fair over-probability at the anchor line.

    Returns ``(probability, sigma_logit, n_books)``.

    Books are weighted by sharpness as elsewhere, but prop coverage is thin
    enough that the dispersion term usually dominates -- which is correct.
    Three books disagreeing about a strikeout line is a genuinely uncertain
    number and the error bar should say so.

    ``correct_over_bias`` removes the structural shading toward the over
    before returning the estimate. Without it, every prop under looks like
    value and every prop over looks like a trap, which is an artifact of the
    shading rather than a real edge.
    """
    line = prop.anchor_line
    if line is None:
        return None

    quotes = prop.quotes_at(line)
    if not quotes:
        return None

    logits: list[float] = []
    weights: list[float] = []
    for q in quotes:
        p = q.fair_over(method)
        if p is None or not 0.0 < p < 1.0:
            continue
        book = get_book(q.book)
        logits.append(logit(p))
        weights.append(book.sharpness)

    if not logits:
        return None

    total_w = sum(weights)
    mean_logit = sum(l * w for l, w in zip(logits, weights)) / total_w

    if len(logits) > 1:
        var = sum(w * (l - mean_logit) ** 2 for l, w in zip(logits, weights)) / total_w
        sigma = math.sqrt(max(var, 0.0))
    else:
        sigma = 0.30

    # Thin coverage means a weak consensus regardless of apparent agreement,
    # because agreement between two books that use the same projection feed
    # is not independent confirmation.
    sigma = max(sigma, 0.26 / math.sqrt(len(logits)))

    if correct_over_bias:
        mean_logit -= over_shading(prop.stat)

    return expit(mean_logit), sigma, len(logits)


def over_shading(stat: str) -> float:
    """Log-odds by which books shade a prop's over, from public flow.

    Derived from how lopsided the ticket split is on that stat. This is the
    "where is the public's money" question answered at the level where it has
    the largest effect: books do not need to shade a spread much because
    sharp money will correct it, but nobody corrects a prop, so the shading
    survives all the way to settlement.
    """
    share = PROP_OVER_TICKET_SHARE.get(stat.lower().replace(" ", "_"), DEFAULT_OVER_SHARE)
    excess = max(0.0, share - 0.5)
    # Calibrated so an 88%-over prop carries roughly 0.10 log-odds of shading,
    # which is about 2.5 points of probability near even money.
    return excess * 0.27


# ---------------------------------------------------------------------------
# Ladder analysis -- the main event
# ---------------------------------------------------------------------------


@dataclass
class LadderMispricing:
    """An alternate line priced inconsistently with the book's own anchor."""

    player: str
    stat: str
    book: str
    line: float
    side: str                # "Over" | "Under"
    offered_american: float
    fair_american: float
    fair_probability: float
    ev: float
    anchor_line: float
    implied_projection: float
    push_probability: float = 0.0

    @property
    def description(self) -> str:
        return f"{self.player} {self.stat.replace('_', ' ')} {self.side} {self.line:g}"


def fit_ladder(
    quotes: list[PropQuote], stat: str, method: str = "shin"
) -> Distribution | None:
    """Fit one distribution to an entire set of quotes at once.

    Fitting to a single anchor and extrapolating is tempting and fragile: any
    bias in recovering that one probability compounds as you move away from
    it, and a rung three steps out can be off by enough to invent a 10% edge
    out of nothing. That failure is silent, and it produces phantom bets on
    exactly the deep alternates where the money is worst.

    Fitting jointly fixes it. Every rung is devigged the same way and the mean
    is chosen to minimize squared error in log-odds across all of them, so a
    systematic devig bias shifts every rung in the same direction and largely
    cancels out of the residuals. What survives is genuine internal
    disagreement -- the thing actually worth betting.
    """
    observations: list[tuple[float, float]] = []
    for q in quotes:
        p = q.fair_over(method)
        if p is None or not 1e-4 < p < 1 - 1e-4:
            continue
        observations.append((q.line, p))

    if len(observations) < 2:
        return None

    def loss(mean: float) -> float:
        dist = build(stat, mean)
        total = 0.0
        for line, p in observations:
            predicted = min(max(dist.sf(line), 1e-6), 1 - 1e-6)
            total += (logit(predicted) - logit(p)) ** 2
        return total

    lines = [line for line, _ in observations]
    lo, hi = 1e-3, max(max(lines) * 2.5, 5.0)
    phi = (math.sqrt(5) - 1) / 2
    a, b = hi - phi * (hi - lo), lo + phi * (hi - lo)
    fa, fb = loss(a), loss(b)
    for _ in range(120):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - phi * (hi - lo)
            fa = loss(a)
        else:
            lo, a, fa = a, b, fb
            b = lo + phi * (hi - lo)
            fb = loss(b)
        if hi - lo < 1e-7:
            break
    return build(stat, 0.5 * (lo + hi))


def consensus_distribution(
    prop: PropMarket, method: str = "shin", min_quotes: int = 4
) -> tuple[Distribution, float, int] | None:
    """Fit one distribution to the whole market, across books and rungs.

    Returns ``(distribution, sigma_logit, n_books)``.

    This is the prop equivalent of the sharp consensus on a side, and it is
    what individual prices get judged against. Fitting across every book's
    every rung rather than to one book's anchor means a single sloppy
    alternate ladder cannot drag the reference with it -- instead it stands
    out against the others, which is exactly the behavior wanted.

    The returned distribution describes what the market *believes*, shading
    included. Correcting for the public's over-bias is a separate step and
    belongs to the signal layer; doing it here as well would double-count it
    and produce a card of nothing but unders.
    """
    usable = [q for q in prop.quotes if q.complete]
    if len(usable) < min_quotes:
        return None

    # Sharper books get more say, exactly as on a side.
    weighted: list[PropQuote] = []
    for q in usable:
        weight = max(1, int(round(get_book(q.book).sharpness * 4)))
        weighted.extend([q] * weight)

    dist = fit_ladder(weighted, prop.stat, method)
    if dist is None:
        return None

    # Dispersion: how much the books disagree at the anchor, in log-odds.
    anchor = prop.anchor_line
    logits: list[float] = []
    if anchor is not None:
        for q in prop.quotes_at(anchor):
            p = q.fair_over(method)
            if p is not None and 0.0 < p < 1.0:
                logits.append(logit(p))

    n_books = len({q.book for q in usable})
    if len(logits) > 1:
        mean = sum(logits) / len(logits)
        sigma = math.sqrt(sum((l - mean) ** 2 for l in logits) / len(logits))
    else:
        sigma = 0.30
    # Thin prop coverage is never as confident as it looks: books share
    # projection feeds, so agreement is not independent confirmation.
    sigma = max(sigma, 0.26 / math.sqrt(max(n_books, 1)))

    return dist, sigma, n_books


def analyze_ladder(
    prop: PropMarket,
    method: str = "shin",
    min_ev: float = 0.02,
    correct_over_bias: bool = True,
    min_rungs: int = 3,
) -> list[LadderMispricing]:
    """Find alternate lines a book has priced inconsistently with its own ladder.

    Per book: fit one distribution across every rung that book posts, then
    flag the rungs that deviate from it. A book pricing its whole ladder from
    a single coherent model produces no findings here, which is the correct
    and most common answer.

    Two deliberate conservatisms. Rungs far from the ladder's center get a
    haircut that always makes the bet look *worse*, never better -- the
    penalty is one-directional so it cannot manufacture an edge. And
    whole-number lines credit the push, since a push refunds the stake rather
    than losing it.
    """
    integer = model_for(prop.stat).integer
    shading = over_shading(prop.stat) if correct_over_bias else 0.0
    found: list[LadderMispricing] = []

    by_book: dict[str, list[PropQuote]] = {}
    for q in prop.quotes:
        if q.complete:
            by_book.setdefault(q.book, []).append(q)

    for book, quotes in by_book.items():
        # A book posting one or two rungs cannot contradict itself in a way
        # we can measure.
        if len(quotes) < min_rungs:
            continue

        dist = fit_ladder(quotes, prop.stat, method)
        if dist is None:
            continue

        center = sum(q.line for q in quotes) / len(quotes)

        for quote in quotes:
            distance = abs(quote.line - center)
            # One-directional: always reduces the apparent edge.
            tail_penalty = min(0.40, 0.07 * distance)

            fair_over = dist.sf(quote.line)
            # Extreme-tail rungs cannot be priced reliably by anyone, us
            # included. A fitted 0.3% probability carries more model error
            # than signal, and the EV computed from it is meaningless -- so
            # the honest answer is to decline rather than to bet a number we
            # cannot stand behind.
            if not TAIL_FLOOR <= fair_over <= 1.0 - TAIL_FLOOR:
                continue
            push = push_probability(dist, quote.line, prop.stat) if integer else 0.0

            # Remove the structural over-shading from the fitted curve so the
            # comparison is against an honest price rather than a shaded one.
            fair_over = expit(logit(fair_over) - shading)
            fair_under = max(1.0 - fair_over - push, 1e-6)

            for side, offered, fair_p in (
                ("Over", quote.over_american, fair_over),
                ("Under", quote.under_american, fair_under),
            ):
                if offered is None:
                    continue
                shrunk = expit(logit(fair_p) - tail_penalty)
                decimal = 1.0 + (
                    offered / 100.0 if offered > 0 else 100.0 / abs(offered)
                )
                # A push returns the stake, so it is not part of the loss.
                ev = shrunk * (decimal - 1.0) - (1.0 - shrunk - push)
                if ev < min_ev:
                    continue
                found.append(
                    LadderMispricing(
                        player=prop.player,
                        stat=prop.stat,
                        book=book,
                        line=quote.line,
                        side=side,
                        offered_american=offered,
                        fair_american=prob_to_american(
                            min(max(shrunk, 1e-4), 1 - 1e-4)
                        ),
                        fair_probability=shrunk,
                        ev=ev,
                        anchor_line=round(center, 1),
                        implied_projection=dist.mean,
                        push_probability=push,
                    )
                )

    return sorted(found, key=lambda m: -m.ev)


def derived_ladder(prop: PropMarket, method: str = "shin") -> dict[float, tuple[float, float]]:
    """Fair over/under American prices at every plausible line.

    Returns ``{line: (over_american, under_american)}``. Useful on its own:
    it tells you what to ask for when a book will negotiate an alternate, and
    what a same-game parlay leg is actually worth.
    """
    anchor = anchor_probability(prop, method)
    if anchor is None:
        return {}
    anchor_p, _, _ = anchor
    line = prop.anchor_line
    if line is None:
        return {}

    dist = fit_to_market(prop.stat, line, anchor_p)
    out: dict[float, tuple[float, float]] = {}
    for candidate in standard_ladder(line, prop.stat):
        p_over = min(max(dist.sf(candidate), 1e-4), 1 - 1e-4)
        out[candidate] = (
            prob_to_american(p_over),
            prob_to_american(1.0 - p_over),
        )
    return out


def implied_projection(prop: PropMarket, method: str = "shin") -> float | None:
    """The player projection the market's price implies.

    Worth surfacing on its own. If the market implies 6.9 strikeouts and your
    own read is 5.5, that disagreement is the actual bet -- and seeing it in
    the same units as a projection makes it much easier to sanity-check than
    comparing prices.
    """
    anchor = anchor_probability(prop, method)
    line = prop.anchor_line
    if anchor is None or line is None:
        return None
    return fit_to_market(prop.stat, line, anchor[0]).mean


# ---------------------------------------------------------------------------
# Cross-book comparison
# ---------------------------------------------------------------------------


@dataclass
class LineDisagreement:
    """Books posting materially different numbers on the same prop."""

    player: str
    stat: str
    low_book: str
    low_line: float
    high_book: str
    high_line: float

    @property
    def gap(self) -> float:
        return self.high_line - self.low_line

    @property
    def description(self) -> str:
        return (
            f"{self.player} {self.stat.replace('_', ' ')}: "
            f"{self.low_line:g} at {self.low_book} vs {self.high_line:g} at {self.high_book}"
        )


def find_line_disagreement(prop: PropMarket, min_gap: float = 1.0) -> LineDisagreement | None:
    """Detect books that disagree on the number itself, not just the price.

    A full-point gap on a strikeout prop is a large disagreement -- someone is
    working from a different projection, a different expected pitch count, or
    stale lineup information. Taking the under at the high book and the over
    at the low book is often a genuine middle.
    """
    complete = [q for q in prop.quotes if q.complete]
    if len(complete) < 2:
        return None
    low = min(complete, key=lambda q: q.line)
    high = max(complete, key=lambda q: q.line)
    if high.line - low.line < min_gap:
        return None
    return LineDisagreement(
        player=prop.player,
        stat=prop.stat,
        low_book=low.book,
        low_line=low.line,
        high_book=high.book,
        high_line=high.line,
    )


def prop_hold(prop: PropMarket) -> float | None:
    """Median hold across books, for deciding whether a prop is playable."""
    holds = [q.hold() for q in prop.quotes if q.hold() is not None]
    if not holds:
        return None
    holds.sort()
    return holds[len(holds) // 2]


def is_playable(prop: PropMarket, max_hold: float = 0.10, min_books: int = 3) -> tuple[bool, str]:
    """Whether a prop is worth analyzing at all.

    Most are not. A two-book prop with a 13% hold cannot be beaten by any
    realistic edge, and screening it only produces false positives.
    """
    complete = [q for q in prop.quotes if q.complete]
    if len(complete) < min_books:
        return False, f"only {len(complete)} books posting a complete market"
    hold = prop_hold(prop)
    if hold is not None and hold > max_hold:
        return False, f"hold of {hold:.1%} is too rich to overcome"
    return True, "playable"


def market_to_prop(market: Market, sport: str) -> PropMarket | None:
    """Convert a generic Market carrying prop prices into a PropMarket."""
    if not market.market_type.is_prop or not market.subject:
        return None

    stat = (market.metadata or {}).get("stat") if hasattr(market, "metadata") else None
    stat = stat or _infer_stat(market)
    if stat is None:
        return None

    by_key: dict[tuple[str, float], PropQuote] = {}
    for price in market.prices:
        if price.line is None:
            continue
        key = (price.book, price.line)
        quote = by_key.get(key)
        if quote is None:
            quote = PropQuote(book=price.book, line=price.line)
            by_key[key] = quote
        if price.outcome.lower().startswith("over"):
            quote.over_american = price.american
        elif price.outcome.lower().startswith("under"):
            quote.under_american = price.american

    return PropMarket(
        player=market.subject,
        stat=stat,
        sport=sport,
        event_id=market.event_id,
        quotes=list(by_key.values()),
    )


def _infer_stat(market: Market) -> str | None:
    """Recover the stat from the outcome labels when it is not carried."""
    for outcome in market.outcomes:
        lowered = outcome.lower()
        for stat in PROPS_BY_STAT:
            if stat.replace("_", " ") in lowered or stat in lowered:
                return stat
    return None
