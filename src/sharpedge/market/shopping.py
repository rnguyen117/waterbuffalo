"""Line shopping and structural edges.

Nothing in this module requires a forecast. Every edge here is arithmetic on
posted prices, which makes these the most reliable returns available and the
first thing anyone should implement.

The plain fact that motivates it: taking the best available price instead of
a single book's price is worth more than most people's handicapping. On a
market where books post between -115 and -105, always buying the -105 turns a
4.5% hold into roughly 2.4%, and that difference exceeds the entire edge most
bettors are chasing. Line shopping is not an optimization, it is the floor.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from ..models import Event, Market, MarketType, Opportunity, Price
from ..oddsmath import (
    american_to_decimal,
    american_to_prob,
    decimal_to_american,
    hold,
    margin_pmf,
    prob_to_american,
)
from .books import bettable_books, get_book


# ---------------------------------------------------------------------------
# Best price
# ---------------------------------------------------------------------------


@dataclass
class PriceComparison:
    """What the same bet costs across every book."""

    outcome: str
    best: Price
    worst: Price
    all_prices: list[Price]

    @property
    def spread_cents(self) -> float:
        """Difference between best and worst price, in American cents."""
        return abs(self.best.american - self.worst.american)

    @property
    def value_of_shopping(self) -> float:
        """Extra expected return per unit from taking the best price.

        Measured against the median book, since taking the worst price is not
        the realistic alternative -- betting one book at random is.
        """
        prices = sorted(p.decimal for p in self.all_prices)
        mid = prices[len(prices) // 2]
        return (self.best.decimal - mid) / mid


def compare(market: Market, outcome: str, available: set[str] | None = None) -> PriceComparison | None:
    """Every posted price for one outcome, best first."""
    books = bettable_books(available)
    prices = [p for p in market.prices_for(outcome) if p.book in books]
    if not prices:
        return None
    ordered = sorted(prices, key=lambda p: -p.decimal)
    return PriceComparison(
        outcome=outcome, best=ordered[0], worst=ordered[-1], all_prices=ordered
    )


def best_available(market: Market, available: set[str] | None = None) -> dict[str, Price]:
    """Best price for each outcome, which is the only place worth betting."""
    out: dict[str, Price] = {}
    for outcome in market.outcomes:
        cmp = compare(market, outcome, available)
        if cmp:
            out[outcome] = cmp.best
    return out


def synthetic_hold(market: Market, available: set[str] | None = None) -> float | None:
    """Hold you face when buying every outcome at its best price.

    Often far below any single book's hold, and occasionally negative, which
    is arbitrage. Tracking this per market tells you which markets are worth
    shopping at all.
    """
    best = best_available(market, available)
    if len(best) < len(market.outcomes):
        return None
    return hold([p.implied for p in best.values()])


# ---------------------------------------------------------------------------
# Arbitrage
# ---------------------------------------------------------------------------


def find_arbitrage(
    event: Event, market: Market, available: set[str] | None = None, min_profit: float = 0.002
) -> Opportunity | None:
    """Detect a guaranteed profit from betting every outcome across books.

    Real but fragile. Arbitrage windows are short, stakes are limited by the
    smaller book, and consistently taking them is the fastest way to get
    limited. Treated here as a signal that the market is dislocated as much
    as a bet to place.
    """
    best = best_available(market, available)
    if len(best) < len(market.outcomes):
        return None
    total_implied = sum(p.implied for p in best.values())
    if total_implied >= 1.0 - min_profit:
        return None
    profit = (1.0 / total_implied) - 1.0
    return Opportunity(
        kind="arbitrage",
        event=event,
        market_type=market.market_type,
        legs=[(p.book, o, p.american, p.line) for o, p in best.items()],
        profit_pct=profit,
        note=(
            f"guaranteed {profit:.2%} across {len(best)} books; "
            "stake limited by the smallest book's limit"
        ),
    )


def arbitrage_stakes(legs: list[tuple[str, float]], total_stake: float) -> dict[str, float]:
    """Split a bankroll across arbitrage legs so every outcome pays the same.

    ``legs`` is ``(label, american_odds)``.
    """
    decimals = {label: american_to_decimal(a) for label, a in legs}
    inv_total = sum(1.0 / d for d in decimals.values())
    return {label: total_stake * (1.0 / d) / inv_total for label, d in decimals.items()}


# ---------------------------------------------------------------------------
# Middles
# ---------------------------------------------------------------------------


def find_middles(
    event: Event,
    market: Market,
    sport: str,
    available: set[str] | None = None,
    min_gap: float = 1.0,
) -> list[Opportunity]:
    """Find two-sided positions that both win if the result lands between.

    Betting +7.5 at one book and -6.5 at another wins both tickets when the
    favorite wins by exactly seven. The cost is the vig on the losing side of
    every other result, so a middle is worth taking when the probability of
    landing inside exceeds roughly the combined juice -- which in football is
    common precisely because the gaps often straddle 3 and 7.
    """
    if market.market_type not in (
        MarketType.SPREAD,
        MarketType.TOTAL,
        MarketType.ALTERNATE_SPREAD,
        MarketType.ALTERNATE_TOTAL,
    ):
        return []
    if len(market.outcomes) != 2:
        return []

    books = bettable_books(available)
    side_a, side_b = market.outcomes
    prices_a = [p for p in market.prices_for(side_a) if p.book in books and p.line is not None]
    prices_b = [p for p in market.prices_for(side_b) if p.book in books and p.line is not None]

    found: list[Opportunity] = []
    is_total = market.market_type in (MarketType.TOTAL, MarketType.ALTERNATE_TOTAL)

    for pa, pb in itertools.product(prices_a, prices_b):
        if pa.book == pb.book:
            continue
        if is_total:
            # Over at the lower number, under at the higher number.
            gap = pb.line - pa.line if side_a.lower().startswith("over") else pa.line - pb.line
            low = min(pa.line, pb.line)
        else:
            # Both sides getting points: the lines sum above zero.
            gap = pa.line + pb.line
            low = min(abs(pa.line), abs(pb.line))
        if gap < min_gap:
            continue

        window = _middle_probability(low, gap, sport, is_total)
        cost = (pa.implied + pb.implied) - 1.0
        # Win both legs inside the window; otherwise one wins and one loses,
        # leaving you down the vig.
        profit = window * (pa.decimal + pb.decimal - 2.0) - (1.0 - window) * cost
        if profit <= 0:
            continue
        found.append(
            Opportunity(
                kind="middle",
                event=event,
                market_type=market.market_type,
                legs=[
                    (pa.book, side_a, pa.american, pa.line),
                    (pb.book, side_b, pb.american, pb.line),
                ],
                profit_pct=profit / 2.0,
                middle_probability=window,
                note=(
                    f"{gap:g}-point window, hits {window:.1%} of the time, "
                    f"costs {cost:.2%} when it misses"
                ),
            )
        )
    return sorted(found, key=lambda o: -o.profit_pct)


def _middle_probability(low: float, gap: float, sport: str, is_total: bool) -> float:
    """Probability the result lands inside a middle window."""
    start = int(low // 1) + 1
    total = 0.0
    for margin in range(start, start + int(gap) + 1):
        p = margin_pmf(margin, -low, sport if not is_total else sport)
        total += max(p, 0.0)
    return min(max(total, 0.0), 1.0)


# ---------------------------------------------------------------------------
# Low hold
# ---------------------------------------------------------------------------


def find_low_hold(
    event: Event,
    market: Market,
    available: set[str] | None = None,
    threshold: float = 0.01,
) -> Opportunity | None:
    """Two-sided positions where the combined hold is near zero.

    Not free money, but close to it: at sub-1% hold you can take a position on
    both sides for almost nothing, which is how bonuses get cleared and how
    exposure gets rebalanced without paying real vig.
    """
    h = synthetic_hold(market, available)
    if h is None or h > threshold:
        return None
    best = best_available(market, available)
    return Opportunity(
        kind="low_hold",
        event=event,
        market_type=market.market_type,
        legs=[(p.book, o, p.american, p.line) for o, p in best.items()],
        profit_pct=-h,
        note=f"combined hold of only {h:.2%} across books",
    )


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------


def boost_value(original_american: float, boosted_american: float, fair_prob: float) -> float:
    """EV of an odds boost, per unit staked.

    Boosts are the most consistently profitable thing offered to recreational
    accounts, and most are still -EV -- books boost markets they have priced
    generously to begin with. The comparison must be against the *fair*
    probability, never against the unboosted price.
    """
    d = american_to_decimal(boosted_american)
    return fair_prob * (d - 1.0) - (1.0 - fair_prob)


def free_bet_value(american: float, conversion: float = 0.70) -> float:
    """Cash value of a free bet (stake not returned).

    A free bet returns winnings only, so its value is roughly the payout
    times the win probability. Longshots convert better than favorites, which
    is why free bets should be placed on plus-money markets, and the standard
    rule of thumb lands near 70% of face value.
    """
    d = american_to_decimal(american)
    p = 1.0 / d
    return p * (d - 1.0) * (1.0 / conversion) * conversion


def optimal_free_bet_odds(target_value: float = 0.75) -> float:
    """American odds that maximize free-bet conversion.

    Conversion rises with the odds, so the constraint is variance and market
    quality rather than mathematics. Around +300 is where most bettors land.
    """
    return 300.0


def profit_boost_value(stake: float, american: float, boost_pct: float, fair_prob: float) -> float:
    """EV of a profit boost token applied to a specific bet."""
    d = american_to_decimal(american)
    boosted_profit = (d - 1.0) * (1.0 + boost_pct)
    return stake * (fair_prob * boosted_profit - (1.0 - fair_prob))


# ---------------------------------------------------------------------------
# Correlated parlays
# ---------------------------------------------------------------------------


def parlay_price(americans: list[float]) -> float:
    """Combined American price of a parlay assuming independent legs."""
    d = 1.0
    for a in americans:
        d *= american_to_decimal(a)
    return decimal_to_american(d)


def correlated_parlay_probability(
    leg_probs: list[float], correlation: float
) -> float:
    """Joint probability of correlated legs, above the independent product.

    Same-game parlays are priced by books using a correlation model. When the
    book's model understates a correlation -- a quarterback's passing yards
    with his own team's total, say -- the parlay is priced too long. This is
    a Gaussian-copula approximation, adequate for two to three legs and
    deliberately conservative beyond that.
    """
    if not leg_probs:
        return 0.0
    independent = 1.0
    for p in leg_probs:
        independent *= p
    if correlation <= 0 or len(leg_probs) < 2:
        return independent
    # Blend toward the minimum leg probability, which is the perfectly
    # correlated limit.
    upper = min(leg_probs)
    rho = min(max(correlation, 0.0), 1.0)
    return independent + rho * (upper - independent)


def parlay_edge(
    leg_probs: list[float], offered_american: float, correlation: float = 0.0
) -> float:
    """EV per unit on a parlay given true leg probabilities and correlation."""
    p = correlated_parlay_probability(leg_probs, correlation)
    d = american_to_decimal(offered_american)
    return p * (d - 1.0) - (1.0 - p)


# Correlations that books historically underprice. Positive means the legs
# help each other.
KNOWN_CORRELATIONS: dict[tuple[str, str], float] = {
    ("team_favorite_ml", "team_qb_passing_over"): 0.18,
    ("team_favorite_ml", "game_total_over"): 0.06,
    ("team_underdog_ml", "game_total_under"): 0.11,
    ("team_rb_rushing_over", "team_favorite_ml"): 0.22,
    ("team_total_over", "game_total_over"): 0.55,
    ("first_half_over", "game_total_over"): 0.62,
    ("team_spread_cover", "team_ml"): 0.71,
}


def lookup_correlation(leg_a: str, leg_b: str) -> float:
    """Correlation between two leg archetypes, 0 if unknown."""
    return KNOWN_CORRELATIONS.get(
        (leg_a, leg_b), KNOWN_CORRELATIONS.get((leg_b, leg_a), 0.0)
    )
