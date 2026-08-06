"""Tests for line movement, CLV, and line shopping."""

from datetime import datetime, timedelta, timezone

import pytest

from sharpedge.market.movement import (
    LineHistory,
    beat_close_rate,
    clv_significance,
    closing_line_value,
    detect_reverse_line_movement,
    detect_steam,
    expected_roi_from_clv,
    find_stale_lines,
    no_vig_clv,
    sharp_money_indicator,
)
from sharpedge.market.shopping import (
    arbitrage_stakes,
    best_available,
    boost_value,
    compare,
    correlated_parlay_probability,
    find_arbitrage,
    find_low_hold,
    find_middles,
    lookup_correlation,
    parlay_edge,
    parlay_price,
    synthetic_hold,
)
from sharpedge.models import Event, LineSnapshot, Market, MarketType, Price, PublicBetting

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def event():
    return Event(
        event_id="e1",
        sport="nfl",
        league="NFL",
        home_team="Home",
        away_team="Away",
        start_time=NOW + timedelta(hours=4),
    )


def market(prices, market_type=MarketType.SPREAD, outcomes=("Home", "Away")):
    return Market(event_id="e1", market_type=market_type, outcomes=list(outcomes), prices=prices)


def price(book, outcome, american, line=None, minutes_old=0):
    return Price(book=book, outcome=outcome, american=american, line=line,
                 timestamp=NOW - timedelta(minutes=minutes_old))


def snapshot(book, american, line, minutes_old, outcome="Home"):
    return LineSnapshot("e1", MarketType.SPREAD, outcome, book, american, line,
                        NOW - timedelta(minutes=minutes_old))


class TestSteam:
    def test_coordinated_move_is_steam(self):
        history = []
        for book in ("pinnacle", "circa", "draftkings", "fanduel"):
            history.append(snapshot(book, -110, -3.0, 60))
            history.append(snapshot(book, -110, -4.0, 5))
        steam, direction = detect_steam(history)
        assert steam
        assert direction == -1

    def test_books_drifting_both_ways_is_not_steam(self):
        history = [
            snapshot("pinnacle", -110, -3.0, 60), snapshot("pinnacle", -110, -4.0, 5),
            snapshot("circa", -110, -3.0, 60), snapshot("circa", -110, -2.0, 5),
            snapshot("draftkings", -110, -3.0, 60), snapshot("draftkings", -110, -4.0, 5),
        ]
        steam, _ = detect_steam(history)
        assert not steam

    def test_soft_books_alone_do_not_make_steam(self):
        # Soft books following late is the echo, not the move.
        history = []
        for book in ("espnbet", "bovada", "fanatics"):
            history.append(snapshot(book, -110, -3.0, 60))
            history.append(snapshot(book, -110, -4.0, 5))
        steam, _ = detect_steam(history)
        assert not steam

    def test_too_few_books_is_not_steam(self):
        history = [snapshot("pinnacle", -110, -3.0, 60), snapshot("pinnacle", -110, -4.0, 5)]
        assert detect_steam(history) == (False, 0)

    def test_empty_history_is_safe(self):
        assert detect_steam([]) == (False, 0)


class TestReverseLineMovement:
    def test_line_moving_against_tickets_is_rlm(self):
        public = PublicBetting("e1", MarketType.SPREAD, "Home", ticket_pct=0.75, handle_pct=0.40)
        rlm, why = detect_reverse_line_movement("Home", -3.0, -2.0, public)
        assert rlm
        assert "moved" in why

    def test_line_moving_with_tickets_is_not_rlm(self):
        public = PublicBetting("e1", MarketType.SPREAD, "Home", 0.75, 0.80)
        rlm, _ = detect_reverse_line_movement("Home", -3.0, -4.0, public)
        assert not rlm

    def test_no_public_data_means_no_signal(self):
        assert detect_reverse_line_movement("Home", -3.0, -2.0, None) == (False, "")

    def test_balanced_tickets_do_not_trigger(self):
        public = PublicBetting("e1", MarketType.SPREAD, "Home", 0.52, 0.50)
        rlm, _ = detect_reverse_line_movement("Home", -3.0, -2.0, public)
        assert not rlm

    def test_handle_divergence_scoring(self):
        big = PublicBetting("e1", MarketType.SPREAD, "Home", 0.30, 0.60)
        score, note = sharp_money_indicator(big)
        assert score > 0
        assert "larger wagers" in note

        small = PublicBetting("e1", MarketType.SPREAD, "Home", 0.70, 0.45)
        score, note = sharp_money_indicator(small)
        assert score < 0


class TestStaleLines:
    def test_finds_a_book_behind_the_market(self):
        m = market([
            price("pinnacle", "Home", -110, line=-3.0),
            price("espnbet", "Home", -110, line=-2.0),
        ])
        stale = find_stale_lines(m, sharp_consensus_line=-3.0)
        assert len(stale) == 1
        assert stale[0][0] == "espnbet"
        assert stale[0][2] == pytest.approx(1.0)

    def test_sharp_books_are_not_flagged(self):
        m = market([price("pinnacle", "Home", -110, line=-2.0)])
        assert find_stale_lines(m, sharp_consensus_line=-3.0) == []

    def test_worse_numbers_are_not_opportunities(self):
        m = market([price("espnbet", "Home", -110, line=-4.0)])
        assert find_stale_lines(m, sharp_consensus_line=-3.0) == []

    def test_no_reference_line_returns_nothing(self):
        m = market([price("espnbet", "Home", -110, line=-2.0)])
        assert find_stale_lines(m, None) == []


class TestCLV:
    def test_beating_the_close_is_positive(self):
        # Took +110, closed at -110: a clear win against the number.
        assert closing_line_value(110, -110) > 0

    def test_losing_to_the_close_is_negative(self):
        assert closing_line_value(-130, -110) < 0

    def test_matching_the_close_is_neutral(self):
        assert closing_line_value(-110, -110) == pytest.approx(0.0)

    def test_no_vig_clv_strips_the_juice(self):
        # Beating a -110 close by five cents is less impressive once the vig
        # is removed from the closing number.
        raw = closing_line_value(-105, -110)
        fair = no_vig_clv(-105, [-110, -110])
        assert fair < raw

    def test_beat_close_rate(self):
        assert beat_close_rate([0.01, -0.01, 0.02, 0.03]) == pytest.approx(0.75)
        assert beat_close_rate([]) == 0.0

    def test_significance_needs_a_sample(self):
        t, verdict = clv_significance([0.02])
        assert t == 0.0
        assert "not enough" in verdict

    def test_strong_consistent_clv_is_significant(self):
        t, verdict = clv_significance([0.02] * 50 + [0.018] * 50)
        assert t > 2.5
        assert "strong evidence" in verdict

    def test_negative_clv_is_called_out(self):
        t, verdict = clv_significance([-0.02] * 100)
        assert t < -2.0
        assert "negative edge" in verdict

    def test_roi_projection_is_conservative(self):
        # Nobody turns 2% CLV into 15% ROI.
        assert expected_roi_from_clv(0.02) < 0.02


class TestLineHistory:
    def test_records_and_reads_back(self, tmp_path):
        history = LineHistory(tmp_path / "lines.db")
        m = market([price("pinnacle", "Home", -110, line=-3.0)])
        assert history.record_market(m, NOW) == 1
        series = history.series("e1", MarketType.SPREAD, "Home")
        assert len(series) == 1
        assert series[0].line == -3.0
        history.close()

    def test_opener_prefers_a_sharp_book(self, tmp_path):
        history = LineHistory(tmp_path / "lines.db")
        history.record_market(
            market([price("espnbet", "Home", -110, line=-2.0, minutes_old=120)]), NOW
        )
        history.record_market(
            market([price("pinnacle", "Home", -110, line=-3.0, minutes_old=100)]), NOW
        )
        opener = history.opener("e1", MarketType.SPREAD, "Home")
        assert opener.book == "pinnacle"
        history.close()

    def test_closing_ignores_prices_after_kickoff(self, tmp_path):
        history = LineHistory(tmp_path / "lines.db")
        history.record_market(
            market([price("pinnacle", "Home", -110, line=-3.0, minutes_old=60)]), NOW
        )
        kickoff = NOW - timedelta(minutes=30)
        assert history.closing("e1", MarketType.SPREAD, "Home", kickoff) is not None
        early = NOW - timedelta(minutes=120)
        assert history.closing("e1", MarketType.SPREAD, "Home", early) is None
        history.close()


class TestShopping:
    def test_best_price_wins(self):
        m = market([
            price("draftkings", "Home", -115),
            price("espnbet", "Home", -105),
            price("betmgm", "Home", -110),
        ], market_type=MarketType.MONEYLINE)
        result = compare(m, "Home")
        assert result.best.book == "espnbet"
        assert result.spread_cents == pytest.approx(10.0)

    def test_shopping_has_measurable_value(self):
        m = market([
            price("draftkings", "Home", -115),
            price("espnbet", "Home", -105),
            price("betmgm", "Home", -112),
        ], market_type=MarketType.MONEYLINE)
        assert compare(m, "Home").value_of_shopping > 0

    def test_synthetic_hold_beats_any_single_book(self):
        m = market([
            price("draftkings", "Home", -120), price("draftkings", "Away", +100),
            price("espnbet", "Home", -100), price("espnbet", "Away", -120),
        ], market_type=MarketType.MONEYLINE)
        combined = synthetic_hold(m)
        assert combined is not None
        assert combined < 0.045

    def test_arbitrage_detected(self):
        m = market([
            price("draftkings", "Home", +110),
            price("espnbet", "Away", +110),
        ], market_type=MarketType.MONEYLINE)
        arb = find_arbitrage(event(), m)
        assert arb is not None
        assert arb.profit_pct > 0

    def test_no_arbitrage_in_a_normal_market(self):
        m = market([
            price("draftkings", "Home", -110),
            price("espnbet", "Away", -110),
        ], market_type=MarketType.MONEYLINE)
        assert find_arbitrage(event(), m) is None

    def test_arbitrage_stakes_equalize_payouts(self):
        stakes = arbitrage_stakes([("a", +110), ("b", +110)], 1000)
        assert sum(stakes.values()) == pytest.approx(1000)
        payout_a = stakes["a"] * 2.10
        payout_b = stakes["b"] * 2.10
        assert payout_a == pytest.approx(payout_b)

    def test_low_hold_detected(self):
        m = market([
            price("draftkings", "Home", +102),
            price("espnbet", "Away", -104),
        ], market_type=MarketType.MONEYLINE)
        assert find_low_hold(event(), m, threshold=0.02) is not None

    def test_middle_found_across_books(self):
        m = market([
            price("draftkings", "Home", -110, line=3.5),
            price("espnbet", "Away", -110, line=3.5),
        ])
        middles = find_middles(event(), m, "nfl", min_gap=1.0)
        # Lines sum to 7, a wide window straddling the key numbers.
        assert middles
        assert middles[0].middle_probability > 0

    def test_no_middle_without_a_gap(self):
        m = market([
            price("draftkings", "Home", -110, line=-3.0),
            price("espnbet", "Away", -110, line=3.0),
        ])
        assert find_middles(event(), m, "nfl", min_gap=1.0) == []


class TestPromotionsAndParlays:
    def test_boost_is_measured_against_fair_value(self):
        # A boost on an already-bad price can still be -EV.
        assert boost_value(-110, +100, fair_prob=0.45) < 0
        assert boost_value(-110, +100, fair_prob=0.55) > 0

    def test_parlay_price_compounds(self):
        assert parlay_price([100, 100]) == pytest.approx(300.0)

    def test_independent_parlay_probability(self):
        assert correlated_parlay_probability([0.5, 0.5], 0.0) == pytest.approx(0.25)

    def test_correlation_raises_joint_probability(self):
        independent = correlated_parlay_probability([0.5, 0.5], 0.0)
        correlated = correlated_parlay_probability([0.5, 0.5], 0.5)
        assert correlated > independent

    def test_perfect_correlation_reaches_the_minimum_leg(self):
        assert correlated_parlay_probability([0.5, 0.7], 1.0) == pytest.approx(0.5)

    def test_correlated_parlay_can_be_positive_ev(self):
        # A book pricing correlated legs as independent leaves value.
        independent_price = parlay_price([-110, -110])
        assert parlay_edge([0.52, 0.52], independent_price, correlation=0.35) > 0

    def test_known_correlations_are_symmetric(self):
        a = lookup_correlation("team_spread_cover", "team_ml")
        b = lookup_correlation("team_ml", "team_spread_cover")
        assert a == b > 0

    def test_unknown_correlation_is_zero(self):
        assert lookup_correlation("nonsense", "gibberish") == 0.0
