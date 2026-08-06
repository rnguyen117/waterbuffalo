"""The daily run: from raw prices to a staked card.

Order of operations, and why each step is where it is:

1. **Ingest** odds, news, injuries, weather, and ticket counts.
2. **Record** every price to the line history, because closing line value
   cannot be computed retroactively from data you did not save.
3. **Price** each market: devig every book, weight by sharpness and recency,
   and produce a consensus probability with an honest error bar.
4. **Adjust** with signals, each claiming only the part of its effect the
   market has not already priced.
5. **Shop** for the best available price at a book you can actually bet.
6. **Screen** on expected value evaluated pessimistically -- at a lower
   confidence bound, after a winner's-curse haircut, and only if every devig
   method agrees.
7. **Size** the whole card jointly under exposure and correlation limits.

Steps 6 and 7 reject most of what step 5 produces, and that is the system
working. A screen that passes everything through has no opinion; the value is
in what it throws away.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from .config import Config
from .market import consensus, movement, shopping
from .market.books import bettable_books, get_book
from .market.movement import LineHistory
from .models import (
    BetCandidate,
    Confidence,
    Event,
    InjuryReport,
    Market,
    MarketType,
    NewsItem,
    Opportunity,
    PublicBetting,
    SlateResult,
    WeatherReport,
    utcnow,
)
from .oddsmath import american_to_prob, decimal_to_prob
from .pricing import portfolio
from .pricing.ev import (
    devig_logit_deltas,
    ev_with_uncertainty,
    outlier_discount,
    robust_under_devig,
    selection_penalty,
)
from .pricing.portfolio import PortfolioConstraints, assign_confidence
from .signals.base import SignalContext, SignalEngine
from .signals.injuries import InjurySignal, QuestionableTagSignal
from .signals.market_signals import (
    HandleDivergenceSignal,
    MarketDisagreementSignal,
    OpenerDriftSignal,
    ReverseLineMovementSignal,
    RetailShadingSignal,
    SteamSignal,
    StaleLineSignal,
)
from .signals.news import BreakingNewsSignal, MotivationSignal
from .signals.situational import (
    HomeFieldSignal,
    RestSignal,
    ScheduleSpotSignal,
    TravelSignal,
)
from .signals.weather import WeatherSignal


def default_engine(config: Config) -> SignalEngine:
    """The standard signal stack.

    Ordering does not matter -- contributions are additive -- but the mix
    does. Market-derived signals dominate by design, because they are the
    ones with verifiable premises.
    """
    return SignalEngine(
        signals=[
            StaleLineSignal(),
            RetailShadingSignal(),
            SteamSignal(),
            ReverseLineMovementSignal(),
            HandleDivergenceSignal(),
            OpenerDriftSignal(),
            MarketDisagreementSignal(),
            InjurySignal(),
            QuestionableTagSignal(),
            BreakingNewsSignal(),
            MotivationSignal(),
            WeatherSignal(),
            RestSignal(),
            TravelSignal(),
            ScheduleSpotSignal(),
            HomeFieldSignal(),
        ],
        max_total_logit=config.model.max_total_logit,
        market_trust=config.model.market_trust,
    )


@dataclass
class Inputs:
    """Everything a run needs, already fetched."""

    events: list[Event]
    news: list[NewsItem]
    injuries: list[InjuryReport]
    weather: dict[str, WeatherReport]
    public: list[PublicBetting]


def run(
    inputs: Inputs,
    config: Config,
    history: LineHistory | None = None,
    engine: SignalEngine | None = None,
    now: datetime | None = None,
) -> SlateResult:
    """Produce a staked card from fetched inputs."""
    now = now or utcnow()
    engine = engine or default_engine(config)
    books = bettable_books(config.available_books)

    candidates: list[BetCandidate] = []
    opportunities: list[Opportunity] = []
    skipped: list[tuple[str, str]] = []
    considered = 0

    public_index = {
        (p.event_id, p.market_type, p.outcome): p for p in inputs.public
    }

    for event in inputs.events:
        hours = event.hours_to_start(now)
        if hours > config.filters.max_hours_to_start:
            skipped.append((event.name, f"starts in {hours:.0f}h, beyond the window"))
            continue
        if hours < config.filters.min_hours_to_start:
            skipped.append((event.name, "too close to start time"))
            continue
        if event.league in config.filters.exclude_leagues:
            continue

        event_injuries = [
            i for i in inputs.injuries if event.involves(i.team)
        ]
        event_news = [
            n for n in inputs.news if any(event.involves(t) for t in n.teams)
        ]
        weather = inputs.weather.get(event.event_id)

        for market in event.markets:
            if market.market_type.value in config.filters.exclude_markets:
                continue

            if history is not None:
                history.record_market(market, now)

            considered += len(market.prices)

            fair = consensus.fair_prices(
                market,
                now=now,
                method=config.model.devig_method,
                hours_to_start=hours,
                half_life_min=config.model.consensus_half_life_min,
                min_books=config.model.min_books_for_consensus,
            )
            if not fair:
                skipped.append(
                    (f"{event.name} {market.market_type.value}", "not enough books to price")
                )
                continue

            first = next(iter(fair.values()))
            if first.market_hold is not None and first.market_hold > config.filters.max_hold:
                skipped.append(
                    (
                        f"{event.name} {market.market_type.value}",
                        f"market hold of {first.market_hold:.1%} is too rich",
                    )
                )
                continue

            opportunities.extend(_structural(event, market, books, config))

            conservative = consensus.conservative_probs(market)

            for outcome in market.outcomes:
                fp = fair.get(outcome)
                if fp is None or fp.n_books < config.filters.min_books:
                    continue

                comparison = shopping.compare(market, outcome, config.available_books)
                if comparison is None:
                    continue
                # The best bet is the best combination of number and price,
                # not the longest price. A book at +2.5 (-105) beats one at
                # +1.5 (+100), and ranking on odds alone would pick the wrong
                # one and then credit the edge to the wrong book.
                best = _best_by_value(comparison.all_prices, fp, market, event)

                sharp_now = consensus.sharp_line(market, outcome)
                read = movement.analyze(
                    market,
                    history,
                    outcome,
                    public=public_index.get((event.event_id, market.market_type, outcome)),
                    sharp_line_now=sharp_now,
                )

                ctx = SignalContext(
                    event=event,
                    market=market,
                    outcome=outcome,
                    market_probability=fp.probability,
                    fair_price=fp,
                    book=best.book,
                    bet_line=best.line,
                    consensus_line=fp.consensus_line,
                    opening_line=read.opening_line,
                    current_line=read.current_line,
                    news=event_news,
                    injuries=event_injuries,
                    weather=weather,
                    public=public_index.get((event.event_id, market.market_type, outcome)),
                    movement=read,
                    now=now,
                )
                model_p, contributions = engine.evaluate(ctx)

                candidate = _build_candidate(
                    event=event,
                    market=market,
                    outcome=outcome,
                    best=best,
                    fair=fp,
                    model_probability=model_p,
                    contributions=contributions,
                    comparison=comparison,
                    conservative=conservative.get(outcome),
                    config=config,
                    considered=considered,
                    movement_notes=read.notes,
                )
                if candidate is not None:
                    candidates.append(candidate)

    candidates = portfolio.dedupe_same_bet(candidates)
    candidates = portfolio.drop_conflicting_sides(candidates)

    constraints = config.portfolio
    result = portfolio.optimize(candidates, config.bankroll.starting, constraints)

    return SlateResult(
        generated_at=now,
        bets=result.bets,
        opportunities=sorted(opportunities, key=lambda o: -o.profit_pct)[:25],
        considered=considered,
        bankroll=config.bankroll.starting,
        skipped=skipped,
    )


def _build_candidate(
    event: Event,
    market: Market,
    outcome: str,
    best,
    fair,
    model_probability: float,
    contributions: list,
    comparison,
    conservative: float | None,
    config: Config,
    considered: int,
    movement_notes: list[str],
) -> BetCandidate | None:
    """Price, screen, and provisionally size one bet."""
    book = get_book(best.book)

    # A price at a different number is a different bet. Re-price the model's
    # probability at the line this specific book is offering before comparing
    # it against that book's price, otherwise a stale line's extra half point
    # gets counted twice -- once as a better number and again as a better price.
    at_line = _line_adjusted_probability(fair, market, event, outcome, best.line)
    if abs(at_line - fair.probability) < 1e-12:
        effective_probability = model_probability
    else:
        # Carry the model's disagreement with the market across to the new
        # number rather than discarding it.
        from .oddsmath import expit, logit

        effective_probability = expit(
            logit(at_line) + (logit(model_probability) - logit(fair.probability))
        )

    penalty = 0.0
    if config.model.apply_selection_penalty:
        penalty += selection_penalty(max(considered, 2))

    # An outlier price is more often informed than generous.
    median_decimal = sorted(p.decimal for p in comparison.all_prices)[
        len(comparison.all_prices) // 2
    ]
    penalty += outlier_discount(best.decimal, median_decimal)

    assessment = ev_with_uncertainty(
        probability=effective_probability,
        american=best.american,
        sigma_logit=fair.sigma_logit,
        confidence=config.model.ev_confidence,
        selection_penalty=penalty,
    )

    if assessment.ev < config.filters.min_ev:
        return None
    if assessment.ev_lower < config.filters.min_ev_lower:
        return None

    # Every devig method must agree the bet clears zero, otherwise the edge
    # is an artifact of the arithmetic rather than a property of the market.
    # The check runs against the probability at *this book's line*, since a
    # stale number and a generous price are different things.
    devig_evs: dict[str, float] = {}
    if config.model.require_robust_devig:
        raw = _raw_probs_at_sharpest_book(market)
        if raw is not None:
            probs, index_map = raw
            idx = index_map.get(outcome)
            if idx is not None:
                deltas = devig_logit_deltas(probs, idx)
                robust, devig_evs = robust_under_devig(
                    assessment.probability, best.american, deltas, min_ev=0.0
                )
                if not robust:
                    return None

    candidate = BetCandidate(
        event=event,
        market_type=market.market_type,
        outcome=outcome,
        book=best.book,
        american=best.american,
        line=best.line,
        fair=fair,
        model_probability=assessment.probability,
        signals=contributions,
        conservative_probability=conservative,
        deep_link=best.deep_link,
    )

    candidate.confidence = assign_confidence(
        candidate, assessment.ev_lower, fair.n_books
    )
    if candidate.confidence == Confidence.PASS:
        return None

    # Provisional Kelly fraction; the portfolio optimizer resizes it jointly.
    from .pricing.kelly import uncertainty_adjusted_kelly

    fraction, _, constraint = uncertainty_adjusted_kelly(
        model_probability=assessment.probability,
        market_probability=fair.probability,
        american=best.american,
        sigma_logit=fair.sigma_logit,
        kelly_multiplier=config.bankroll.kelly_multiplier,
        max_fraction=config.bankroll.max_bet_fraction,
    )
    if fraction <= 0:
        return None
    candidate.kelly_fraction = fraction

    notes = list(movement_notes)
    notes.append(f"best of {len(comparison.all_prices)} books, {comparison.spread_cents:.0f} cents of spread")
    notes.append(f"EV {assessment.ev:.2%}, lower bound {assessment.ev_lower:.2%}")
    if fair.market_hold is not None:
        notes.append(f"market hold {fair.market_hold:.2%}")
    notes.append(f"provisional sizing limited by {constraint}; final stake set by the slate optimizer")
    if book.max_limit < 2000:
        notes.append(f"{book.name} limits are around ${book.max_limit:,.0f}")
    candidate.notes = notes

    return candidate


def _line_adjusted_probability(
    fair, market: Market, event: Event, outcome: str, line: float | None
) -> float:
    """Fair probability of an outcome at a specific book's number."""
    if (
        line is None
        or fair.consensus_line is None
        or abs(line - fair.consensus_line) < 1e-9
        or market.market_type
        not in (
            MarketType.SPREAD,
            MarketType.TOTAL,
            MarketType.ALTERNATE_SPREAD,
            MarketType.ALTERNATE_TOTAL,
        )
    ):
        return fair.probability

    return consensus.probability_at_line(
        consensus_probability=fair.probability,
        consensus_line=fair.consensus_line,
        target_line=line,
        sport=event.sport,
        is_total=market.market_type
        in (MarketType.TOTAL, MarketType.ALTERNATE_TOTAL),
        is_over=outcome.lower().startswith("over"),
    )


def _best_by_value(prices, fair, market: Market, event: Event):
    """Pick the price with the highest EV once its own line is priced in."""
    best = None
    best_ev = float("-inf")
    for price in prices:
        p = _line_adjusted_probability(fair, market, event, price.outcome, price.line)
        ev = p * (price.decimal - 1.0) - (1.0 - p)
        if ev > best_ev:
            best, best_ev = price, ev
    return best


def _raw_probs_at_sharpest_book(
    market: Market,
) -> tuple[list[float], dict[str, int]] | None:
    """Raw implied probabilities from the sharpest book with a full market."""
    best_book = None
    best_sharpness = -1.0
    for book_key in market.books():
        if not market.complete_at(book_key):
            continue
        sharpness = get_book(book_key).sharpness
        if sharpness > best_sharpness:
            best_sharpness, best_book = sharpness, book_key
    if best_book is None:
        return None

    probs: list[float] = []
    index_map: dict[str, int] = {}
    for i, outcome in enumerate(market.outcomes):
        matching = [p for p in market.by_book(best_book) if p.outcome == outcome]
        if not matching:
            return None
        probs.append(max(matching, key=lambda p: p.timestamp).implied)
        index_map[outcome] = i
    return probs, index_map


def _structural(
    event: Event, market: Market, books: set[str], config: Config
) -> list[Opportunity]:
    """Arbitrage, middles, and low-hold pairs, which need no model at all."""
    found: list[Opportunity] = []

    arb = shopping.find_arbitrage(event, market, config.available_books)
    if arb:
        found.append(arb)

    low = shopping.find_low_hold(event, market, config.available_books)
    if low:
        found.append(low)

    if market.market_type in (MarketType.SPREAD, MarketType.TOTAL):
        found.extend(
            shopping.find_middles(event, market, event.sport, config.available_books)[:3]
        )

    return found


def fetch_inputs(config: Config) -> Inputs:
    """Pull everything from the configured providers."""
    provider = config.sources.provider.lower()

    if provider == "demo":
        from .sources.demo import DemoSource

        source = DemoSource()
        events = source.fetch_events(config.sources.sports)
        return Inputs(
            events=events,
            news=source.fetch_news(events),
            injuries=source.fetch_injuries(events),
            weather=source.fetch_weather(events),
            public=source.fetch_public(events),
        )

    if provider == "theoddsapi":
        from .sources.theoddsapi import TheOddsAPISource

        source = TheOddsAPISource(
            api_key=config.sources.api_key,
            regions=config.sources.regions,
            markets=config.sources.markets,
            cache_dir=f"{config.data_dir}/cache",
            cache_ttl=config.sources.cache_ttl_seconds,
        )
        events = source.fetch_events(config.sources.sports)

        news: list[NewsItem] = []
        if config.sources.news_feeds:
            from .sources.news_feed import RSSNewsSource

            news = RSSNewsSource(config.sources.news_feeds).fetch_news()

        return Inputs(events=events, news=news, injuries=[], weather={}, public=[])

    raise ValueError(
        f"unknown provider {config.sources.provider!r}; expected 'demo' or 'theoddsapi'"
    )
