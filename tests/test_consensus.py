"""Tests for sharp consensus pricing."""

from datetime import datetime, timedelta, timezone

import pytest

from sharpedge.market.books import consensus_weight, get_book
from sharpedge.market.consensus import (
    book_hold,
    conservative_probs,
    consensus_line,
    devigged_book_probs,
    fair_prices,
    implied_expected_margin,
    market_maturity,
    probability_at_line,
    recency_weight,
    retail_shading,
    sharp_line,
)
from sharpedge.models import Market, MarketType, Price

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def market(prices, market_type=MarketType.MONEYLINE, outcomes=("Home", "Away")):
    return Market(
        event_id="e1",
        market_type=market_type,
        outcomes=list(outcomes),
        prices=prices,
    )


def price(book, outcome, american, line=None, minutes_old=0):
    return Price(
        book=book,
        outcome=outcome,
        american=american,
        line=line,
        timestamp=NOW - timedelta(minutes=minutes_old),
    )


class TestDevigPerBook:
    def test_complete_market_devigs(self):
        m = market([price("pinnacle", "Home", -110), price("pinnacle", "Away", -110)])
        probs = devigged_book_probs(m, "pinnacle")
        assert probs["Home"] == pytest.approx(0.5, abs=1e-6)

    def test_incomplete_market_returns_none(self):
        # Half a market says nothing about what the book believes.
        m = market([price("pinnacle", "Home", -110)])
        assert devigged_book_probs(m, "pinnacle") is None

    def test_book_hold_computed(self):
        # -120 both ways is a fat market: 8.3% hold against the 4.5% a
        # standard -110/-110 costs.
        m = market([price("espnbet", "Home", -120), price("espnbet", "Away", -120)])
        assert book_hold(m, "espnbet") == pytest.approx(0.0833, abs=1e-3)
        fair = market([price("pinnacle", "Home", -110), price("pinnacle", "Away", -110)])
        assert book_hold(fair, "pinnacle") == pytest.approx(0.0455, abs=1e-3)


class TestWeighting:
    def test_recency_decays(self):
        fresh = recency_weight(NOW, NOW, half_life_min=45)
        stale = recency_weight(NOW - timedelta(minutes=45), NOW, half_life_min=45)
        assert fresh == pytest.approx(1.0)
        assert stale == pytest.approx(0.5, abs=1e-9)

    def test_sharp_books_outweigh_soft_ones(self):
        assert consensus_weight(get_book("pinnacle")) > consensus_weight(get_book("bovada"))

    def test_maturity_rises_toward_kickoff(self):
        assert market_maturity(0.0) == 1.0
        assert market_maturity(1.0) > market_maturity(72.0)
        assert market_maturity(200.0) == pytest.approx(0.25)


class TestFairPrices:
    def test_consensus_probabilities_sum_to_one(self):
        m = market(
            [
                price("pinnacle", "Home", -115),
                price("pinnacle", "Away", +105),
                price("draftkings", "Home", -120),
                price("draftkings", "Away", +100),
                price("espnbet", "Home", -118),
                price("espnbet", "Away", +102),
            ]
        )
        fair = fair_prices(m, now=NOW)
        assert sum(f.probability for f in fair.values()) == pytest.approx(1.0, abs=1e-9)

    def test_returns_nothing_without_enough_books(self):
        m = market([price("pinnacle", "Home", -110), price("pinnacle", "Away", -110)])
        assert fair_prices(m, now=NOW, min_books=3) == {}

    def test_sharp_book_dominates_a_crowd_of_soft_ones(self):
        # Five soft books agreeing should not outvote Pinnacle. They are
        # copying each other, not pricing independently.
        prices = [
            price("pinnacle", "Home", -110),
            price("pinnacle", "Away", -110),
        ]
        for book in ("espnbet", "fanatics", "bovada", "hardrock", "betrivers"):
            prices.append(price(book, "Home", -150))
            prices.append(price(book, "Away", +130))
        fair = fair_prices(market(prices), now=NOW)
        # Soft books say ~58%; Pinnacle says 50%. The answer should sit
        # much closer to Pinnacle than to the crowd.
        assert fair["Home"].probability < 0.55

    def test_dispersion_recorded_as_uncertainty(self):
        agree = market(
            [
                price("pinnacle", "Home", -110), price("pinnacle", "Away", -110),
                price("circa", "Home", -110), price("circa", "Away", -110),
                price("draftkings", "Home", -110), price("draftkings", "Away", -110),
            ]
        )
        disagree = market(
            [
                price("pinnacle", "Home", -110), price("pinnacle", "Away", -110),
                price("circa", "Home", -180), price("circa", "Away", +160),
                price("draftkings", "Home", +140), price("draftkings", "Away", -160),
            ]
        )
        tight = fair_prices(agree, now=NOW)["Home"].sigma_logit
        wide = fair_prices(disagree, now=NOW)["Home"].sigma_logit
        assert wide > tight

    def test_retail_bias_detects_shading(self):
        # Retail prices the home team well above the sharp number: the
        # public side.
        prices = [
            price("pinnacle", "Home", -110), price("pinnacle", "Away", -110),
            price("circa", "Home", -110), price("circa", "Away", -110),
            price("draftkings", "Home", -140), price("draftkings", "Away", +120),
            price("espnbet", "Home", -145), price("espnbet", "Away", +125),
        ]
        fair = fair_prices(market(prices), now=NOW)
        assert fair["Home"].retail_bias > 0
        assert fair["Away"].retail_bias < 0
        assert "public side" in retail_shading(fair["Home"])

    def test_counts_books(self):
        prices = []
        for book in ("pinnacle", "draftkings", "espnbet", "betmgm"):
            prices.append(price(book, "Home", -110))
            prices.append(price(book, "Away", -110))
        fair = fair_prices(market(prices), now=NOW)
        assert fair["Home"].n_books == 4
        assert fair["Home"].n_sharp_books == 1

    def test_stale_prices_lose_influence(self):
        prices = [
            price("draftkings", "Home", -110, minutes_old=0),
            price("draftkings", "Away", -110, minutes_old=0),
            price("fanduel", "Home", -110, minutes_old=0),
            price("fanduel", "Away", -110, minutes_old=0),
            price("betmgm", "Home", -300, minutes_old=600),
            price("betmgm", "Away", +260, minutes_old=600),
        ]
        fair = fair_prices(market(prices), now=NOW)
        # The six-hour-old outlier should barely move the consensus.
        assert fair["Home"].probability < 0.56


class TestLines:
    def test_consensus_line_weights_by_book(self):
        m = market(
            [
                price("pinnacle", "Home", -110, line=-3.0),
                price("pinnacle", "Away", +100, line=3.0),
                price("espnbet", "Home", -110, line=-4.0),
                price("espnbet", "Away", +100, line=4.0),
            ],
            market_type=MarketType.SPREAD,
        )
        weights = {"pinnacle": 1.0, "espnbet": 0.2}
        line = consensus_line(m, "Home", weights)
        # Weighted toward Pinnacle's -3.
        assert -3.3 < line < -3.0

    def test_sharp_line_ignores_retail(self):
        m = market(
            [
                price("pinnacle", "Home", -110, line=-3.0),
                price("pinnacle", "Away", +100, line=3.0),
                price("espnbet", "Home", -110, line=-6.0),
                price("espnbet", "Away", +100, line=6.0),
            ],
            market_type=MarketType.SPREAD,
        )
        assert sharp_line(m, "Home") == pytest.approx(-3.0)


class TestLineReprice:
    def test_same_line_is_unchanged(self):
        assert probability_at_line(0.55, -3.0, -3.0, "nfl") == pytest.approx(0.55)

    def test_better_number_is_worth_more(self):
        # Getting +7 instead of +6 must raise the cover probability.
        base = probability_at_line(0.5, 6.0, 6.0, "nfl")
        better = probability_at_line(0.5, 6.0, 7.0, "nfl")
        assert better > base

    def test_worse_number_is_worth_less(self):
        assert probability_at_line(0.5, 6.0, 5.0, "nfl") < 0.5

    def test_totals_direction_is_respected(self):
        # A higher total is worse for the over and better for the under.
        over = probability_at_line(0.5, 45.0, 47.0, "nfl", is_total=True, is_over=True)
        under = probability_at_line(0.5, 45.0, 47.0, "nfl", is_total=True, is_over=False)
        assert over < 0.5 < under
        assert over + under == pytest.approx(1.0, abs=1e-9)

    def test_expected_margin_recovers_the_line(self):
        # A pick'em at 50% implies an expected margin of zero.
        assert implied_expected_margin(0.5, 0.0, "nfl") == pytest.approx(0.0, abs=1e-6)
        # A -7 favorite priced at its own number implies a 7-point margin.
        assert implied_expected_margin(0.5, -7.0, "nfl") == pytest.approx(7.0, abs=1e-6)

    def test_a_full_point_is_worth_more_in_nba_than_nfl(self):
        nfl = probability_at_line(0.5, 3.0, 4.0, "nfl") - 0.5
        nba = probability_at_line(0.5, 3.0, 4.0, "nba") - 0.5
        assert nba > nfl


class TestConservative:
    def test_conservative_is_below_consensus(self):
        prices = [
            price("pinnacle", "Home", -250),
            price("pinnacle", "Away", +210),
            price("draftkings", "Home", -260),
            price("draftkings", "Away", +215),
        ]
        m = market(prices)
        fair = fair_prices(m, now=NOW, min_books=2)
        worst = conservative_probs(m)
        assert worst["Away"] <= fair["Away"].probability + 1e-9
