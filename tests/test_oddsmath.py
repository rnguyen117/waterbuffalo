"""Tests for odds conversion, vig removal, and the margin models."""

import math

import pytest

from sharpedge.oddsmath import (
    american_to_decimal,
    american_to_prob,
    decimal_to_american,
    devig,
    devig_additive,
    devig_multiplicative,
    devig_power,
    devig_shin,
    devig_worst_case,
    expit,
    half_point_value,
    hold,
    logit,
    margin_pmf,
    overround,
    poisson_diff_pmf,
    prob_to_american,
    prob_to_spread,
    push_prob,
    shin_z,
    skellam_win_prob,
    spread_to_prob,
    total_over_prob,
)


class TestConversions:
    def test_known_american_to_decimal(self):
        assert american_to_decimal(100) == pytest.approx(2.0)
        assert american_to_decimal(-110) == pytest.approx(1.9090909, abs=1e-6)
        assert american_to_decimal(150) == pytest.approx(2.5)
        assert american_to_decimal(-200) == pytest.approx(1.5)

    def test_round_trip(self):
        for american in (-500, -250, -110, -105, 100, 120, 250, 900):
            assert decimal_to_american(american_to_decimal(american)) == pytest.approx(
                american, abs=1e-6
            )

    def test_minus_110_break_even(self):
        # The number every bettor knows: -110 needs 52.38%.
        assert american_to_prob(-110) == pytest.approx(0.5238, abs=1e-4)

    def test_prob_to_american_round_trip(self):
        for p in (0.05, 0.25, 0.5, 0.5238, 0.75, 0.95):
            assert american_to_prob(prob_to_american(p)) == pytest.approx(p, abs=1e-9)

    def test_invalid_odds_rejected(self):
        with pytest.raises(ValueError):
            american_to_decimal(50)
        with pytest.raises(ValueError):
            decimal_to_american(0.5)

    def test_logit_expit_inverse(self):
        for p in (0.01, 0.3, 0.5, 0.87, 0.999):
            assert expit(logit(p)) == pytest.approx(p, abs=1e-9)


class TestOverroundAndHold:
    def test_standard_market(self):
        probs = [american_to_prob(-110), american_to_prob(-110)]
        assert overround(probs) == pytest.approx(0.0476, abs=1e-4)
        # Overround and hold are different numbers and both get quoted.
        assert hold(probs) == pytest.approx(0.0455, abs=1e-4)

    def test_fair_market_has_no_hold(self):
        assert hold([0.5, 0.5]) == pytest.approx(0.0)

    def test_three_way_market(self):
        probs = [0.40, 0.32, 0.33]
        assert overround(probs) == pytest.approx(0.05)


class TestDevig:
    RAW = [american_to_prob(-110), american_to_prob(-110)]

    @pytest.mark.parametrize(
        "method", ["multiplicative", "additive", "power", "shin"]
    )
    def test_all_methods_sum_to_one(self, method):
        result = devig(self.RAW, method=method)
        assert sum(result) == pytest.approx(1.0, abs=1e-9)

    @pytest.mark.parametrize(
        "method", ["multiplicative", "additive", "power", "shin"]
    )
    def test_symmetric_market_devigs_to_even(self, method):
        result = devig(self.RAW, method=method)
        assert result[0] == pytest.approx(0.5, abs=1e-6)

    def test_methods_disagree_on_lopsided_markets(self):
        # This is the whole reason multiple methods exist. On a heavy
        # favorite the choice of method meaningfully changes the longshot's
        # probability, which is where phantom edges come from.
        raw = [american_to_prob(-2000), american_to_prob(+1000)]
        mult = devig_multiplicative(raw)
        shin = devig_shin(raw)
        assert mult[1] != pytest.approx(shin[1], abs=1e-3)
        # Shin assigns the longshot a lower probability than multiplicative.
        assert shin[1] < mult[1]

    def test_power_devig_solves_correctly(self):
        raw = [0.60, 0.48]
        result = devig_power(raw)
        assert sum(result) == pytest.approx(1.0, abs=1e-9)
        assert result[0] > result[1]

    def test_additive_never_goes_negative(self):
        raw = [0.95, 0.12]
        result = devig_additive(raw)
        assert all(p > 0 for p in result)
        assert sum(result) == pytest.approx(1.0, abs=1e-9)

    def test_shin_z_zero_for_fair_market(self):
        assert shin_z([0.5, 0.5]) == pytest.approx(0.0, abs=1e-6)

    def test_shin_z_positive_for_vigged_market(self):
        assert shin_z(self.RAW) > 0.0

    def test_shin_z_rises_with_vig(self):
        light = shin_z([american_to_prob(-104), american_to_prob(-104)])
        heavy = shin_z([american_to_prob(-130), american_to_prob(-130)])
        assert heavy > light

    def test_worst_case_is_never_above_any_method(self):
        raw = [american_to_prob(-300), american_to_prob(+240)]
        worst = devig_worst_case(raw)
        for method in ("multiplicative", "additive", "power", "shin"):
            for w, m in zip(worst, devig(raw, method=method)):
                assert w <= m + 1e-12

    def test_worst_case_sums_below_one(self):
        # Deliberately incoherent -- it is a pessimistic bound, not a
        # distribution.
        raw = [american_to_prob(-300), american_to_prob(+240)]
        assert sum(devig_worst_case(raw)) <= 1.0 + 1e-9

    def test_three_way_devig(self):
        raw = [0.42, 0.31, 0.33]
        for method in ("multiplicative", "additive", "power", "shin"):
            result = devig(raw, method=method)
            assert len(result) == 3
            assert sum(result) == pytest.approx(1.0, abs=1e-9)

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="unknown devig method"):
            devig(self.RAW, method="magic")

    def test_sub_hundred_market_handled(self):
        # An arbitrage market sums below 1; devigging must not explode.
        raw = [0.48, 0.49]
        result = devig_multiplicative(raw)
        assert sum(result) == pytest.approx(1.0)


class TestSpreadProbability:
    def test_pick_em_is_a_coin_flip(self):
        assert spread_to_prob(0.0, "nfl") == pytest.approx(0.5)

    def test_favorite_wins_more_often(self):
        assert spread_to_prob(-7.0, "nfl") > 0.5
        assert spread_to_prob(7.0, "nfl") < 0.5

    def test_nfl_seven_point_favorite_is_plausible(self):
        # A 7-point NFL favorite wins about 70% of the time.
        p = spread_to_prob(-7.0, "nfl")
        assert 0.66 < p < 0.75

    def test_nba_spreads_move_probability_faster(self):
        # Lower margin variance means each point is worth more.
        assert spread_to_prob(-7.0, "nba") > spread_to_prob(-7.0, "nfl")

    def test_round_trip_with_prob_to_spread(self):
        for spread in (-14.0, -7.0, -3.0, 0.0, 3.5, 10.0):
            p = spread_to_prob(spread, "nfl")
            assert prob_to_spread(p, "nfl") == pytest.approx(spread, abs=1e-6)

    def test_totals_over_under_symmetry(self):
        assert total_over_prob(45.0, 45.0, "nfl") == pytest.approx(0.5, abs=1e-9)
        assert total_over_prob(41.0, 45.0, "nfl") > 0.5


class TestKeyNumbers:
    def test_three_is_the_most_common_nfl_margin(self):
        three = push_prob(3.0, "nfl")
        for other in (1, 2, 4, 5, 6, 8, 9, 10):
            assert three > push_prob(float(other), "nfl")

    def test_seven_is_second(self):
        seven = push_prob(7.0, "nfl")
        assert seven > push_prob(6.0, "nfl")
        assert seven > push_prob(8.0, "nfl")
        assert seven < push_prob(3.0, "nfl")

    def test_half_point_lines_never_push(self):
        assert push_prob(3.5, "nfl") == 0.0
        assert push_prob(-6.5, "nfl") == 0.0

    def test_half_point_off_three_costs_the_most(self):
        # Buying from -3 to -2.5 crosses the biggest chunk of probability
        # mass in football, which is why books charge extra for it.
        at_three = half_point_value(3.0, "nfl")
        at_five = half_point_value(5.0, "nfl")
        assert at_three > at_five

    def test_margin_pmf_is_a_probability(self):
        for margin in range(0, 21):
            p = margin_pmf(margin, -3.0, "nfl")
            assert 0.0 <= p <= 1.0

    def test_sport_without_a_table_falls_back(self):
        p = margin_pmf(5, -3.0, "nba")
        assert 0.0 < p < 1.0


class TestSkellam:
    def test_pmf_sums_to_about_one(self):
        total = sum(poisson_diff_pmf(2.8, 2.6, k) for k in range(-25, 26))
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_probabilities_sum_to_one(self):
        home, draw, away = skellam_win_prob(3.1, 2.7)
        assert home + draw + away == pytest.approx(1.0, abs=1e-9)

    def test_better_team_wins_more(self):
        home, _, away = skellam_win_prob(3.4, 2.4)
        assert home > away

    def test_equal_rates_are_symmetric(self):
        home, _, away = skellam_win_prob(3.0, 3.0)
        assert home == pytest.approx(away, abs=1e-9)

    def test_rejects_nonpositive_rates(self):
        with pytest.raises(ValueError):
            poisson_diff_pmf(0.0, 2.0, 1)
