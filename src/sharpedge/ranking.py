"""Ranking the day's candidates down to a fixed-size card.

There is a real tension in "give me the 10 most probable bets" that is worth
stating plainly rather than quietly resolving.

**Ranking purely by win probability selects the worst bets on the board.** The
highest-probability wager available on any given day is a -3000 favorite at
96.8%. It is also close to the worst price in the building: you risk $30 to
win $1, and one loss erases thirty wins. Sort a slate by probability and you
get a card of heavy chalk that loses money slowly and reliably, which is
exactly the product every parlay-of-favorites tout sells.

**Ranking purely by expected value selects longshots.** The largest EV numbers
come from the thinnest, highest-variance markets, where the estimate is least
trustworthy and a 12% edge is usually a modeling error.

So the default ranking is a composite of five things, all of which matter:

1. **Edge quality** -- EV at its lower confidence bound, not the point estimate.
2. **Hit probability** -- how often the bet actually wins, which is what makes
   a card feel and behave the way a bettor expects.
3. **Evidence strength** -- how many books priced it, whether a market maker
   is among them, and how tightly they agree.
4. **Verifiability** -- a stale line or a ladder inconsistency is checkable
   before the game starts; a situational read is not. Verifiable premises rank
   higher at equal EV.
5. **Realizable size** -- an 11% edge on a market that takes $250 is worth less
   than a 3% edge on one that takes $5,000.

Every mode is selectable, including the literal highest-probability one, so
the trade-off is yours to make with the numbers in front of you.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from .market.taxonomy import profile_for
from .models import BetCandidate, Confidence


class RankMode(str, Enum):
    """How to order the day's candidates."""

    VALUE = "value"              # composite (default)
    PROBABILITY = "probability"  # literal highest win probability
    EDGE = "edge"                # raw expected value
    CONFIDENCE = "confidence"    # strength of evidence
    KELLY = "kelly"              # expected bankroll growth


@dataclass
class ScoredBet:
    """A candidate with its ranking components exposed."""

    bet: BetCandidate
    score: float
    hit_probability: float
    edge_quality: float
    evidence: float
    verifiability: float
    realizable: float
    components: dict[str, float] = field(default_factory=dict)

    @property
    def why_ranked(self) -> str:
        parts = sorted(self.components.items(), key=lambda kv: -kv[1])[:3]
        return ", ".join(f"{k} {v:.2f}" for k, v in parts)


# Signals whose premise can be checked before the game is played. A bet
# resting on one of these is not a forecast, so it earns a ranking bonus.
VERIFIABLE_SIGNALS = {
    "stale_line": 1.00,
    "ladder_consistency": 0.95,
    "retail_shading": 0.70,
    "prop_public_bias": 0.65,
    "handle_divergence": 0.45,
    "workload_limit": 0.55,
    "usage_redistribution": 0.60,
    "steam": 0.40,
}


def score(bet: BetCandidate, ev_lower: float | None = None) -> ScoredBet:
    """Compute a bet's composite ranking score and its components."""
    hit = bet.model_probability

    # 1. Edge quality: lower-bound EV, compressed so a 15% outlier does not
    # dominate a card of honest 3% edges.
    lower = ev_lower if ev_lower is not None else bet.conservative_ev
    edge_quality = math.tanh(max(lower, 0.0) / 0.04)

    # 2. Hit probability, shaped rather than raw. Bets in the 45-70% band get
    # full credit; heavy chalk is penalized because its price is unforgiving
    # and its variance is deceptive, and sub-30% shots are penalized because
    # a card of them will not resemble its expectation for a long time.
    if hit >= 0.85:
        prob_score = 0.35
    elif hit >= 0.72:
        prob_score = 0.72
    elif hit >= 0.42:
        prob_score = 1.00
    elif hit >= 0.28:
        prob_score = 0.70
    else:
        prob_score = 0.40

    # 3. Evidence: book count, sharp participation, and agreement.
    n_books = bet.fair.n_books
    breadth = min(n_books / 8.0, 1.0)
    sharp_bonus = 0.20 if bet.fair.n_sharp_books > 0 else 0.0
    agreement = 1.0 / (1.0 + bet.fair.sigma_logit * 6.0)
    evidence = min(1.0, 0.55 * breadth + sharp_bonus + 0.35 * agreement)

    # 4. Verifiability: does this rest on something checkable now?
    verifiability = 0.0
    for contribution in bet.signals:
        weight = VERIFIABLE_SIGNALS.get(contribution.name)
        if weight and abs(contribution.effective) > 1e-4:
            verifiability = max(verifiability, weight)
        elif weight and contribution.name in ("ladder_consistency",):
            verifiability = max(verifiability, weight)

    # 5. Realizable size: an edge you can only get $250 down on is worth less
    # than a smaller one on a market that takes $5,000. The stat matters here
    # -- a strikeout prop and a tackles prop have very different limits.
    profile = profile_for(bet.market_type, bet.stat)
    limit = profile.typical_limit
    realizable = min(1.0, math.log10(max(limit, 100.0)) / 4.0)

    components = {
        "edge": 0.34 * edge_quality,
        "hit_rate": 0.22 * prob_score,
        "evidence": 0.22 * evidence,
        "verifiable": 0.14 * verifiability,
        "size": 0.08 * realizable,
    }
    total = sum(components.values())

    return ScoredBet(
        bet=bet,
        score=total,
        hit_probability=hit,
        edge_quality=edge_quality,
        evidence=evidence,
        verifiability=verifiability,
        realizable=realizable,
        components=components,
    )


def rank(
    candidates: list[BetCandidate],
    mode: RankMode = RankMode.VALUE,
    top_n: int = 10,
    min_probability: float = 0.0,
    max_per_game: int = 2,
    max_per_market_type: int = 6,
    diversify: bool = True,
) -> list[ScoredBet]:
    """Order candidates and cut to the top ``top_n``.

    Two diversification limits, for two different risks.

    ``max_per_game`` addresses *outcome* correlation. Four bets on one game is
    one opinion expressed four times, and a card built that way is far more
    correlated than its length suggests.

    ``max_per_market_type`` addresses *model* correlation, which is subtler
    and more dangerous. Every player prop on a card is priced through the same
    distribution assumptions -- the same negative-binomial dispersion, the
    same ladder-fitting method. If that machinery is wrong, it is wrong on all
    of them simultaneously, and the card's true variance is far higher than
    its correlation matrix suggests because the errors share a common cause.
    Spreading across market types hedges the modeling itself, not just the
    games.
    """
    scored = [score(c) for c in candidates]

    if mode == RankMode.PROBABILITY:
        scored.sort(key=lambda s: (-s.hit_probability, -s.bet.ev))
    elif mode == RankMode.EDGE:
        scored.sort(key=lambda s: -s.bet.ev)
    elif mode == RankMode.CONFIDENCE:
        scored.sort(key=lambda s: (-s.evidence, -s.bet.ev))
    elif mode == RankMode.KELLY:
        scored.sort(key=lambda s: -s.bet.kelly_fraction)
    else:
        scored.sort(key=lambda s: -s.score)

    if min_probability > 0:
        scored = [s for s in scored if s.hit_probability >= min_probability]

    if not diversify:
        return scored[:top_n]

    selected: list[ScoredBet] = []
    per_game: dict[str, int] = {}
    per_market: dict[str, int] = {}
    overflow: list[ScoredBet] = []

    for item in scored:
        event_id = item.bet.event.event_id
        market = item.bet.market_type.value
        if per_game.get(event_id, 0) >= max_per_game:
            overflow.append(item)
            continue
        if per_market.get(market, 0) >= max_per_market_type:
            overflow.append(item)
            continue
        selected.append(item)
        per_game[event_id] = per_game.get(event_id, 0) + 1
        per_market[market] = per_market.get(market, 0) + 1
        if len(selected) >= top_n:
            break

    # If diversification left the card short, backfill from what it excluded
    # rather than returning fewer bets than asked for. This is a real
    # trade-off: filling to a fixed card size means relaxing the caps that
    # limit correlation and model risk. It is flagged on the returned items so
    # the report can say so out loud rather than quietly padding the card.
    if len(selected) < top_n and overflow:
        backfilled = overflow[: top_n - len(selected)]
        for item in backfilled:
            item.components["backfilled"] = 0.0
        selected.extend(backfilled)

    return selected[:top_n]


def summarize_card(scored: list[ScoredBet]) -> dict:
    """Headline statistics for a ranked card."""
    if not scored:
        return {
            "count": 0,
            "mean_probability": 0.0,
            "mean_ev": 0.0,
            "markets": {},
            "verifiable_share": 0.0,
        }

    markets: dict[str, int] = {}
    for item in scored:
        key = item.bet.market_type.value
        markets[key] = markets.get(key, 0) + 1

    backfilled = sum(1 for s in scored if "backfilled" in s.components)

    return {
        "count": len(scored),
        "backfilled": backfilled,
        "mean_probability": sum(s.hit_probability for s in scored) / len(scored),
        "mean_ev": sum(s.bet.ev for s in scored) / len(scored),
        "markets": markets,
        "verifiable_share": sum(1 for s in scored if s.verifiability > 0.5) / len(scored),
        "expected_hits": sum(s.hit_probability for s in scored),
    }


def expected_record(scored: list[ScoredBet]) -> tuple[float, float]:
    """Expected wins and losses for the card, from its own probabilities.

    Worth printing next to any card. A ten-bet card of 55% shots is expected
    to go 5.5-4.5, and seeing that in advance is what stops a 4-6 night from
    looking like evidence that anything is broken.
    """
    wins = sum(s.hit_probability for s in scored)
    return wins, len(scored) - wins


def probability_of_winning_at_least(scored: list[ScoredBet], k: int) -> float:
    """P(at least k of the card's bets win), treating them as independent.

    Independence overstates certainty when the card contains correlated legs,
    so the portfolio's correlation matrix is the honest tool for sizing. This
    is for setting expectations about the shape of a night.
    """
    probs = [s.hit_probability for s in scored]
    n = len(probs)
    if n == 0:
        return 0.0
    # Poisson-binomial via dynamic programming.
    dp = [1.0] + [0.0] * n
    for p in probs:
        for i in range(n, 0, -1):
            dp[i] = dp[i] * (1 - p) + dp[i - 1] * p
        dp[0] *= 1 - p
    return sum(dp[k:])
