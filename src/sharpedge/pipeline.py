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
from .market import consensus, movement, props as props_module, public as public_module, shopping
from .market.taxonomy import profile_for
from .market.books import bettable_books, get_book
from .market.movement import LineHistory
from .models import (
    BetCandidate,
    Confidence,
    FairPrice,
    Event,
    InjuryReport,
    Market,
    MarketType,
    NewsItem,
    Opportunity,
    PublicBetting,
    SignalContribution,
    SlateResult,
    WeatherReport,
    utcnow,
)
from .oddsmath import american_to_prob, decimal_to_prob
from .pricing import portfolio
from .pricing.distributions import fit_to_market, model_for
from .pricing.ev import (
    devig_logit_deltas,
    implausible_edge,
    ev_with_uncertainty,
    outlier_discount,
    robust_under_devig,
    selection_penalty,
)
from .pricing.portfolio import PortfolioConstraints, assign_confidence
from .ranking import RankMode, expected_record, rank, summarize_card
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
from .signals.props import (
    BlowoutRiskSignal,
    LadderConsistencySignal,
    PaceSignal,
    ParkFactorSignal,
    PropPublicBiasSignal,
    UmpireSignal,
    UsageRedistributionSignal,
    WorkloadLimitSignal,
)
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
            # Prop-specific. Inert on game markets, so they cost nothing there.
            UsageRedistributionSignal(),
            PropPublicBiasSignal(),
            BlowoutRiskSignal(),
            PaceSignal(),
            UmpireSignal(),
            ParkFactorSignal(),
            WorkloadLimitSignal(),
            LadderConsistencySignal(),
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

            # Props take a dedicated path: their ladders must be priced rung
            # by rung from a fitted distribution, never pooled into one
            # consensus.
            if market.market_type.is_prop:
                prop_bets, prop_skips = _prop_candidates(
                    event, market, config, engine, now,
                    event_injuries, event_news, weather, considered,
                )
                candidates.extend(prop_bets)
                skipped.extend(prop_skips)
                continue

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

            # Each market type carries its own efficiency, juice tolerance,
            # and EV floor. A 2% edge on a spread and a 2% edge on a tackles
            # prop are not the same claim, and treating them alike either
            # floods the card with prop noise or ignores props entirely.
            profile = profile_for(market.market_type, market.stat)
            max_hold = max(config.filters.max_hold, profile.typical_hold * 1.35)
            min_ev = max(config.filters.min_ev, profile.min_edge_required)

            first = next(iter(fair.values()))
            if first.market_hold is not None and first.market_hold > max_hold:
                skipped.append(
                    (
                        f"{event.name} {profile.label}",
                        f"hold of {first.market_hold:.1%} exceeds the "
                        f"{max_hold:.1%} ceiling for this market",
                    )
                )
                continue

            ladder_notes = _ladder_notes(event, market, config) if market.market_type.is_prop else {}
            if ladder_notes:
                event.metadata.setdefault("ladder_mispricing", {}).update(ladder_notes)

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
                model_p, contributions = engine.evaluate(
                    ctx, market_trust=profile.market_trust
                )

                # Where the public's money is, folded in as an explicit
                # adjustment rather than buried inside another signal.
                pub = public_module.read(
                    outcome=outcome,
                    market_type=market.market_type,
                    public=ctx.public,
                    stat=market.stat,
                    is_home=(outcome == event.home_team),
                )
                if abs(pub.shading_logit) > 0.005:
                    from .oddsmath import expit as _expit, logit as _logit

                    model_p = _expit(
                        _logit(model_p)
                        + public_module.contrarian_value(pub) * (1.0 - profile.market_trust)
                    )
                    verdict = public_module.fade_recommendation(pub)
                    if verdict:
                        contributions.append(
                            SignalContribution(
                                name="public_money",
                                logit_adjustment=public_module.contrarian_value(pub),
                                weight=1.0 - profile.market_trust,
                                rationale=verdict + (
                                    f" ({pub.verdict})" if pub.ticket_pct is not None else ""
                                ),
                                source="public money",
                            )
                        )

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
                    min_ev=min_ev,
                    profile=profile,
                )
                if candidate is not None:
                    candidates.append(candidate)

    candidates = portfolio.dedupe_same_bet(candidates)
    candidates = portfolio.drop_conflicting_sides(candidates)

    # Rank everything that survived the screen and cut to the target card
    # size *before* staking, so the optimizer allocates the bankroll across
    # the bets that actually made the card rather than spreading it thin over
    # everything that merely cleared the floor.
    ranked = rank(
        candidates,
        mode=RankMode(config.filters.rank_mode),
        top_n=config.filters.card_size,
        min_probability=config.filters.min_probability,
        max_per_game=config.filters.max_per_game,
        max_per_market_type=config.filters.max_per_market_type,
    )
    shortlist = [item.bet for item in ranked]

    constraints = config.portfolio
    result = portfolio.optimize(shortlist, config.bankroll.starting, constraints)

    staked = {id(bet) for bet in result.bets}
    ordered = [bet for bet in shortlist if id(bet) in staked]

    stats = summarize_card([item for item in ranked if id(item.bet) in staked])
    wins, losses = expected_record([i for i in ranked if id(i.bet) in staked])
    stats["expected_record"] = (wins, losses)

    return SlateResult(
        generated_at=now,
        bets=ordered,
        opportunities=sorted(opportunities, key=lambda o: -o.profit_pct)[:25],
        considered=considered,
        bankroll=config.bankroll.starting,
        skipped=skipped,
        ranked=ranked,
        card_stats=stats,
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
    min_ev: float = 0.01,
    profile=None,
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

    if assessment.ev < min_ev:
        return None
    if assessment.ev_lower < config.filters.min_ev_lower:
        return None

    # An edge this large is a data-quality alert, not an opportunity.
    if assessment.ev > config.filters.max_ev:
        return None
    bad, _ = implausible_edge(assessment.probability, best.american)
    if bad:
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
    if profile is not None:
        notes.append(
            f"{profile.label}: efficiency {profile.efficiency:.2f}, "
            f"typical limit ${profile.typical_limit:,.0f}"
        )
        if profile.note:
            notes.append(profile.note)
    if book.max_limit < 2000:
        notes.append(f"{book.name} limits are around ${book.max_limit:,.0f}")
    candidate.notes = notes

    return candidate


def _prop_candidates(
    event: Event,
    market: Market,
    config: Config,
    engine: SignalEngine,
    now: datetime,
    injuries: list,
    news: list,
    weather,
    considered: int,
) -> tuple[list[BetCandidate], list[tuple[str, str]]]:
    """Price a player prop market rung by rung.

    Props cannot go through the generic consensus path, and the reason is
    worth stating precisely: a prop market is not one market. "Over 6.5
    strikeouts" and "Over 9.5 strikeouts" are different bets with different
    probabilities, and pooling every rung of a ladder into a single "Over"
    outcome produces a blended fair price belonging to no actual bet. Doing
    that manufactures spectacular fake edges on deep alternates -- it compares
    the fair price of the 6.5 against the payout of the 9.5.

    So: fit one distribution to the anchor, then price every rung from it.
    Each rung gets its own probability and a confidence penalty growing with
    distance from the anchor, because the extrapolated tail is the least
    trustworthy part of the fit.
    """
    prop = props_module.market_to_prop(market, event.sport)
    if prop is None:
        return [], []

    profile = profile_for(market.market_type, market.stat)
    playable, reason = props_module.is_playable(
        prop,
        max_hold=profile.typical_hold * 1.35,
        min_books=max(3, config.filters.min_books),
    )
    if not playable:
        return [], [(f"{prop.player} {prop.stat}", reason)]

    # Fit across every book and every rung, not to one anchor. A single-point
    # fit is fragile: a small error in recovering that one probability
    # compounds into a large error several rungs away and invents edges.
    #
    # The fit describes what the market believes, shading and all. Correcting
    # for the public's over-bias happens once, in the signal layer -- doing it
    # here too would double-count it and produce a card of nothing but unders.
    consensus_fit = props_module.consensus_distribution(
        prop, method=config.model.devig_method
    )
    anchor_line = prop.anchor_line
    if consensus_fit is None or anchor_line is None:
        return [], [(f"{prop.player} {prop.stat}", "not enough quotes to fit a ladder")]

    dist, sigma, n_books = consensus_fit
    integer = model_for(prop.stat).integer
    books = bettable_books(config.available_books)
    min_ev = max(config.filters.min_ev, profile.min_edge_required)
    hold = props_module.prop_hold(prop)
    skips: list[tuple[str, str]] = []
    n_sharp = sum(
        1 for q in prop.quotes_at(anchor_line) if get_book(q.book).is_sharp
    )

    candidates: list[BetCandidate] = []

    for quote in prop.quotes:
        if quote.book not in books:
            continue

        distance = abs(quote.line - anchor_line)
        # Confidence decays away from the anchor: the fit is pinned there and
        # extrapolated everywhere else.
        rung_sigma = sigma * (1.0 + 0.22 * distance)

        fair_over = dist.sf(quote.line)
        push = (
            props_module.push_probability(dist, quote.line, prop.stat)
            if integer
            else 0.0
        )

        for side, offered in (
            ("Over", quote.over_american),
            ("Under", quote.under_american),
        ):
            if offered is None:
                continue
            fair_p = fair_over if side == "Over" else max(1.0 - fair_over - push, 1e-6)
            # Deep-tail rungs are extrapolation, not estimation.
            if not props_module.TAIL_FLOOR <= fair_p <= 1.0 - props_module.TAIL_FLOOR:
                continue

            fp = FairPrice(
                outcome=side,
                probability=fair_p,
                sigma_logit=rung_sigma,
                n_books=n_books,
                n_sharp_books=n_sharp,
                consensus_line=anchor_line,
                market_hold=hold,
            )

            ctx = SignalContext(
                event=event,
                market=market,
                outcome=side,
                market_probability=fair_p,
                fair_price=fp,
                book=quote.book,
                bet_line=quote.line,
                consensus_line=anchor_line,
                news=news,
                injuries=injuries,
                weather=weather,
                now=now,
            )
            model_p, contributions = engine.evaluate(
                ctx, market_trust=profile.market_trust
            )

            assessment = ev_with_uncertainty(
                probability=model_p,
                american=offered,
                sigma_logit=rung_sigma,
                confidence=config.model.ev_confidence,
                selection_penalty=(
                    selection_penalty(max(considered, 2))
                    if config.model.apply_selection_penalty
                    else 0.0
                ),
            )
            if assessment.ev < min_ev:
                continue
            if assessment.ev_lower < config.filters.min_ev_lower:
                continue

            if assessment.ev > config.filters.max_ev:
                skips.append((
                    f"{prop.player} {prop.stat} {side} {quote.line:g}",
                    f"EV of {assessment.ev:.0%} is beyond the {config.filters.max_ev:.0%} "
                    "sanity bound -- treating it as bad data, not an edge",
                ))
                continue

            bad, why = implausible_edge(assessment.probability, offered)
            if bad:
                skips.append((f"{prop.player} {prop.stat} {side} {quote.line:g}", why))
                continue

            candidate = BetCandidate(
                event=event,
                market_type=market.market_type,
                outcome=side,
                book=quote.book,
                american=offered,
                line=quote.line,
                fair=fp,
                model_probability=assessment.probability,
                signals=contributions,
                subject=prop.player,
                stat=prop.stat,
            )
            candidate.confidence = assign_confidence(
                candidate, assessment.ev_lower, n_books
            )
            if candidate.confidence == Confidence.PASS:
                continue

            from .pricing.kelly import uncertainty_adjusted_kelly

            fraction, _, constraint = uncertainty_adjusted_kelly(
                model_probability=assessment.probability,
                market_probability=fair_p,
                american=offered,
                sigma_logit=rung_sigma,
                kelly_multiplier=config.bankroll.kelly_multiplier,
                max_fraction=config.bankroll.max_bet_fraction,
            )
            if fraction <= 0:
                continue
            candidate.kelly_fraction = fraction

            notes = [
                f"the market's own {anchor_line:g} anchor implies a projection of "
                f"{dist.mean:.1f} {prop.stat.replace('_', ' ')}",
                f"EV {assessment.ev:.2%}, lower bound {assessment.ev_lower:.2%}",
                f"{n_books} books priced the anchor"
                + (f", median hold {hold:.1%}" if hold is not None else ""),
                f"{profile.label}: typical limit ${profile.typical_limit:,.0f}",
            ]
            if distance > 0:
                notes.append(
                    f"alternate {distance:g} away from the anchor -- the fair price "
                    "is extrapolated, so confidence and stake are reduced"
                )
            if push > 0:
                notes.append(f"whole-number line, pushes {push:.1%} of the time")
            if profile.note:
                notes.append(profile.note)
            candidate.notes = notes
            candidates.append(candidate)

    return candidates, skips


def _ladder_notes(event: Event, market: Market, config: Config) -> dict:
    """Run the alternate-line consistency check on a prop market.

    Returns a map of ``(player, side, line) -> explanation`` for alternates
    the book has priced inconsistently with its own anchor. The explanation
    is attached to the candidate so the report can say *why* the bet exists,
    which for a ladder mispricing is a genuinely checkable claim rather than
    a forecast.
    """
    prop = props_module.market_to_prop(market, event.sport)
    if prop is None:
        return {}

    playable, reason = props_module.is_playable(prop)
    if not playable:
        return {}

    notes: dict = {}
    for mis in props_module.analyze_ladder(prop, method=config.model.devig_method):
        notes[(prop.player, mis.side, mis.line)] = (
            f"{mis.book} prices {mis.side} {mis.line:g} at {mis.offered_american:+.0f} "
            f"but its own {mis.anchor_line:g} anchor implies {mis.fair_american:+.0f} "
            f"(projection {mis.implied_projection:.1f}) -- the book disagrees with itself"
        )
    return notes


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

        # Props and derivatives are where the soft pricing is, so the demo
        # slate includes the full menu rather than just sides and totals.
        if config.filters.include_props or config.filters.include_derivatives:
            from .sources.demo_props import DemoPropSource

            DemoPropSource().augment(events)
            if not config.filters.include_props:
                for e in events:
                    e.markets = [m for m in e.markets if not m.market_type.is_prop]
            if not config.filters.include_derivatives:
                for e in events:
                    e.markets = [m for m in e.markets if not m.market_type.is_derivative]
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
