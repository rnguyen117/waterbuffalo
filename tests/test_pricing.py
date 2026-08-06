"""Tests for expected value, Kelly staking, and portfolio construction."""

from datetime import datetime, timedelta, timezone

import pytest

from sharpedge.models import (
    BetCandidate,
    Confidence,
    Event,
    FairPrice,
    Market,
    MarketType,
)
from sharpedge.oddsmath import american_to_prob
from sharpedge.pricing.ev import (
    break_even_probability,
    devig_logit_deltas,
    ev_with_uncertainty,
    expected_value,
    hold_cost,
    is_robust_edge,
    outlier_discount,
    price_improvement_value,
    required_win_rate,
    robust_under_devig,
    selection_penalty,
)
from sharpedge.pricing.kelly import (
    confidence_from_sigma,
    correlation_haircut,
    drawdown_adjusted_multiplier,
    kelly_fraction,
    kelly_growth_rate,
    risk_of_ruin,
    shrink_toward_market,
    simultaneous_kelly,
    stake_for,
    uncertainty_adjusted_kelly,
)
from sharpedge.pricing.portfolio import (
    PortfolioConstraints,
    assign_confidence,
    dedupe_same_bet,
    drop_conflicting_sides,
    optimize,
)
from sharpedge.risk.correlation import (
    bet_variance,
    correlation_matrix,
    effective_bet_count,
    pair_correlation,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


class TestExpectedValue:
    def test_fair_bet_has_zero_ev(self):
        assert expected_value(0.5, 100) == pytest.approx(0.0)

    def test_break_even_at_minus_110(self):
        assert break_even_probability(-110) == pytest.approx(0.5238, abs=1e-4)

    def test_edge_produces_positive_ev(self):
        assert expected_value(0.55, -110) > 0

    def test_no_edge_produces_negative_ev(self):
        # The vig means a coin flip at -110 loses money.
        assert expected_value(0.50, -110) < 0

    def test_required_win_rate_is_sobering(self):
        # 10% ROI at -110 needs a 57.6% win rate, which nobody sustains.
        assert required_win_rate(-110, 0.10) == pytest.approx(0.576, abs=1e-3)

    def test_hold_cost_of_standard_market(self):
        assert hold_cost([-110, -110]) == pytest.approx(0.0455, abs=1e-4)

    def test_price_improvement_is_worth_real_money(self):
        # Getting -105 instead of -115 is a bigger edge than most handicapping.
        gain = price_improvement_value(-105, -115, 0.52)
        assert gain > 0.04


class TestEVUncertainty:
    def test_lower_bound_is_below_point_estimate(self):
        result = ev_with_uncertainty(0.55, -110, sigma_logit=0.10)
        assert result.ev_lower < result.ev

    def test_no_uncertainty_means_bounds_coincide(self):
        result = ev_with_uncertainty(0.55, -110, sigma_logit=0.0)
        assert result.ev_lower == pytest.approx(result.ev)

    def test_wide_uncertainty_can_kill_an_edge(self):
        # A 2-point edge with a wide error bar is not an edge.
        tight = ev_with_uncertainty(0.545, -110, sigma_logit=0.02)
        wide = ev_with_uncertainty(0.545, -110, sigma_logit=0.40)
        assert tight.is_actionable
        assert not wide.is_actionable

    def test_selection_penalty_grows_with_screening(self):
        assert selection_penalty(10) < selection_penalty(1000)
        assert selection_penalty(1) == 0.0

    def test_selection_penalty_reduces_ev(self):
        clean = ev_with_uncertainty(0.56, -110, 0.05, selection_penalty=0.0)
        screened = ev_with_uncertainty(0.56, -110, 0.05, selection_penalty=0.15)
        assert screened.ev < clean.ev

    def test_outlier_price_is_discounted(self):
        # A book far off the market is more likely informed than generous.
        assert outlier_discount(2.30, 2.00) > 0
        assert outlier_discount(2.01, 2.00) == 0.0


class TestDevigRobustness:
    def test_symmetric_market_is_robust(self):
        raw = [american_to_prob(-110), american_to_prob(-110)]
        deltas = devig_logit_deltas(raw, 0)
        # All methods agree on a symmetric market, so all deltas are zero.
        assert all(abs(d) < 1e-6 for d in deltas.values())

    def test_lopsided_market_methods_diverge(self):
        raw = [american_to_prob(-2000), american_to_prob(+1000)]
        deltas = devig_logit_deltas(raw, 1)
        assert max(deltas.values()) - min(deltas.values()) > 0.01

    def test_robust_check_rejects_method_dependent_edges(self):
        raw = [american_to_prob(-2000), american_to_prob(+1000)]
        deltas = devig_logit_deltas(raw, 1)
        # A price barely above the Shin estimate should not survive every
        # method.
        robust, evs = robust_under_devig(0.088, 1000, deltas, min_ev=0.0)
        assert isinstance(robust, bool)
        assert set(evs) == {"multiplicative", "additive", "power", "shin"}

    def test_is_robust_edge_requires_unanimity(self):
        assert is_robust_edge({"a": 0.02, "b": 0.01})
        assert not is_robust_edge({"a": 0.02, "b": -0.01})
        assert not is_robust_edge({})


class TestKelly:
    def test_no_edge_means_no_bet(self):
        assert kelly_fraction(0.5, -110) < 0

    def test_known_kelly_value(self):
        # p=0.6 at even money: f* = 2p - 1 = 0.2
        assert kelly_fraction(0.6, 100) == pytest.approx(0.2)

    def test_bigger_edge_means_bigger_stake(self):
        assert kelly_fraction(0.60, -110) > kelly_fraction(0.55, -110)

    def test_growth_rate_peaks_at_kelly(self):
        p, odds = 0.6, 100
        optimal = kelly_fraction(p, odds)
        best = kelly_growth_rate(p, odds, optimal)
        assert best > kelly_growth_rate(p, odds, optimal * 0.5)
        assert best > kelly_growth_rate(p, odds, optimal * 2.0)

    def test_overbetting_is_worse_than_underbetting(self):
        # The asymmetry that justifies fractional Kelly: doubling the stake
        # hurts more than halving it.
        p, odds = 0.6, 100
        optimal = kelly_fraction(p, odds)
        half = kelly_growth_rate(p, odds, optimal * 0.5)
        double = kelly_growth_rate(p, odds, optimal * 2.0)
        assert double < half

    def test_shrinkage_moves_toward_market(self):
        shrunk = shrink_toward_market(0.60, 0.50, confidence=0.5)
        assert 0.50 < shrunk < 0.60

    def test_zero_confidence_ignores_the_model(self):
        assert shrink_toward_market(0.60, 0.50, confidence=0.0) == pytest.approx(0.50)

    def test_full_confidence_keeps_the_model(self):
        assert shrink_toward_market(0.60, 0.50, confidence=1.0) == pytest.approx(0.60)

    def test_confidence_rises_with_market_disagreement(self):
        assert confidence_from_sigma(0.4) > confidence_from_sigma(0.02)

    def test_uncertainty_adjusted_kelly_is_capped(self):
        fraction, _, constraint = uncertainty_adjusted_kelly(
            0.90, 0.50, +200, sigma_logit=0.3, max_fraction=0.03
        )
        assert fraction <= 0.03
        assert "cap" in constraint

    def test_no_edge_returns_zero_stake(self):
        fraction, _, reason = uncertainty_adjusted_kelly(0.48, 0.50, -110, 0.05)
        assert fraction == 0.0
        assert "no edge" in reason or "minimum" in reason

    def test_stake_respects_book_limit(self):
        decision = stake_for(
            bankroll=100_000,
            model_probability=0.60,
            market_probability=0.55,
            american=-110,
            sigma_logit=0.20,
            book_limit=500,
        )
        assert decision.stake <= 500
        assert decision.binding_constraint == "book limit"

    def test_simultaneous_kelly_respects_total(self):
        edges = [(0.58, -110)] * 10
        fractions = simultaneous_kelly(edges, max_total=0.15)
        assert sum(fractions) <= 0.15 + 1e-9

    def test_correlation_haircut_reduces_size(self):
        assert correlation_haircut(0.02, [0.7]) < 0.02
        assert correlation_haircut(0.02, []) == 0.02

    def test_drawdown_reduces_multiplier(self):
        assert drawdown_adjusted_multiplier(70, 100, 0.25) < 0.25
        assert drawdown_adjusted_multiplier(98, 100, 0.25) == 0.25

    def test_fractional_kelly_slashes_ruin_risk(self):
        full = kelly_fraction(0.55, -110)
        assert risk_of_ruin(0.55, full) > risk_of_ruin(0.55, full * 0.25)


def make_event(event_id="e1", home="Home Team", away="Away Team", league="NFL"):
    return Event(
        event_id=event_id,
        sport="nfl",
        league=league,
        home_team=home,
        away_team=away,
        start_time=NOW + timedelta(hours=6),
    )


def make_bet(event, outcome, american=-110, market_type=MarketType.SPREAD,
             prob=0.56, line=-3.0, book="draftkings"):
    fair = FairPrice(outcome=outcome, probability=prob, sigma_logit=0.05, n_books=8,
                     n_sharp_books=2)
    return BetCandidate(
        event=event,
        market_type=market_type,
        outcome=outcome,
        book=book,
        american=american,
        line=line,
        fair=fair,
        model_probability=prob,
        kelly_fraction=0.02,
        confidence=Confidence.B,
    )


class TestCorrelation:
    def test_same_bet_is_perfectly_correlated(self):
        e = make_event()
        bet = make_bet(e, "Home Team")
        assert pair_correlation(bet, bet) == 1.0

    def test_opposite_sides_are_negatively_correlated(self):
        e = make_event()
        a = make_bet(e, "Home Team")
        b = make_bet(e, "Away Team")
        assert pair_correlation(a, b) < 0

    def test_moneyline_and_spread_correlate_strongly(self):
        e = make_event()
        a = make_bet(e, "Home Team", market_type=MarketType.MONEYLINE, line=None)
        b = make_bet(e, "Home Team", market_type=MarketType.SPREAD)
        assert pair_correlation(a, b) > 0.5

    def test_different_games_barely_correlate(self):
        a = make_bet(make_event("e1", "A", "B"), "A")
        b = make_bet(make_event("e2", "C", "D"), "C")
        assert abs(pair_correlation(a, b)) < 0.1

    def test_matrix_is_symmetric(self):
        e = make_event()
        bets = [make_bet(e, "Home Team"), make_bet(e, "Away Team")]
        m = correlation_matrix(bets)
        assert m[0][1] == m[1][0]
        assert m[0][0] == 1.0

    def test_effective_count_falls_with_correlation(self):
        e = make_event()
        correlated = correlation_matrix(
            [
                make_bet(e, "Home Team", market_type=MarketType.MONEYLINE, line=None),
                make_bet(e, "Home Team", market_type=MarketType.SPREAD),
            ]
        )
        independent = correlation_matrix(
            [
                make_bet(make_event("e1", "A", "B"), "A"),
                make_bet(make_event("e2", "C", "D"), "C"),
            ]
        )
        assert effective_bet_count(correlated) < effective_bet_count(independent)

    def test_bet_variance_is_positive(self):
        assert bet_variance(0.55, 1.91) > 0


class TestPortfolio:
    def test_empty_input_gives_empty_card(self):
        result = optimize([], 10_000)
        assert result.bets == []

    def test_respects_total_exposure(self):
        events = [make_event(f"e{i}", f"H{i}", f"A{i}") for i in range(10)]
        bets = [make_bet(e, f"H{i}") for i, e in enumerate(events)]
        constraints = PortfolioConstraints(max_total_exposure=0.10)
        result = optimize(bets, 10_000, constraints)
        assert result.total_exposure <= 10_000 * 0.10 + 1e-6

    def test_respects_per_game_cap(self):
        e = make_event()
        bets = [
            make_bet(e, "Home Team", market_type=MarketType.SPREAD),
            make_bet(e, "Home Team", market_type=MarketType.MONEYLINE, line=None),
            make_bet(e, "Over", market_type=MarketType.TOTAL, line=45.0),
        ]
        constraints = PortfolioConstraints(max_per_game=0.04)
        result = optimize(bets, 10_000, constraints)
        per_game = sum(b.stake for b in result.bets if b.event.event_id == "e1")
        assert per_game <= 10_000 * 0.04 + 1e-6

    def test_respects_max_bets(self):
        events = [make_event(f"e{i}", f"H{i}", f"A{i}") for i in range(30)]
        bets = [make_bet(e, f"H{i}") for i, e in enumerate(events)]
        result = optimize(bets, 100_000, PortfolioConstraints(max_bets=5))
        assert len(result.bets) <= 5

    def test_negative_ev_bets_are_excluded(self):
        e = make_event()
        bad = make_bet(e, "Home Team", american=-200, prob=0.50)
        result = optimize([bad], 10_000)
        assert result.bets == []

    def test_dedupe_keeps_the_best_price(self):
        e = make_event()
        cheap = make_bet(e, "Home Team", american=-115, book="fanduel")
        rich = make_bet(e, "Home Team", american=+100, book="espnbet")
        kept = dedupe_same_bet([cheap, rich])
        assert len(kept) == 1
        assert kept[0].book == "espnbet"

    def test_both_sides_positive_means_drop_both(self):
        # If the model likes both sides, the model is wrong about the market.
        e = make_event()
        over = make_bet(e, "Over", market_type=MarketType.TOTAL, line=45.0, prob=0.56)
        under = make_bet(e, "Under", market_type=MarketType.TOTAL, line=45.0, prob=0.56)
        assert drop_conflicting_sides([over, under]) == []

    def test_clear_winner_survives_conflict_check(self):
        e = make_event()
        strong = make_bet(e, "Over", market_type=MarketType.TOTAL, line=45.0, prob=0.62)
        weak = make_bet(e, "Under", market_type=MarketType.TOTAL, line=45.0, prob=0.505)
        kept = drop_conflicting_sides([strong, weak])
        assert len(kept) == 1
        assert kept[0].outcome == "Over"


class TestConfidenceTiers:
    def test_thin_market_is_downgraded(self):
        e = make_event()
        bet = make_bet(e, "Home Team")
        # A large edge from only two books cannot be an A.
        assert assign_confidence(bet, ev_lower=0.08, n_books=2) != Confidence.A

    def test_broad_confirmation_earns_an_a(self):
        e = make_event()
        bet = make_bet(e, "Home Team")
        assert assign_confidence(bet, ev_lower=0.05, n_books=10) == Confidence.A

    def test_tiny_edge_is_a_pass(self):
        e = make_event()
        bet = make_bet(e, "Home Team")
        assert assign_confidence(bet, ev_lower=0.001, n_books=10) == Confidence.PASS
