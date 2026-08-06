"""Tests for the signal framework and individual signals."""

from datetime import datetime, timedelta, timezone

import pytest

from sharpedge.models import (
    Event,
    InjuryReport,
    InjuryStatus,
    Market,
    MarketType,
    NewsItem,
    Price,
    PublicBetting,
    SignalContribution,
    WeatherReport,
)
from sharpedge.signals.base import (
    SignalContext,
    SignalEngine,
    book_lag_credit,
    points_to_logit,
    recency_credit,
    residual_after_market_move,
)
from sharpedge.signals.injuries import (
    InjurySignal,
    position_value,
    team_injury_points,
)
from sharpedge.signals.market_signals import (
    HandleDivergenceSignal,
    RetailShadingSignal,
    StaleLineSignal,
)
from sharpedge.signals.news import (
    BreakingNewsSignal,
    classify,
    extract_players,
    match_teams,
    to_injury_reports,
)
from sharpedge.signals.situational import RestSignal, haversine_miles
from sharpedge.signals.weather import WeatherSignal, wind_total_impact

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def make_event(sport="nfl", metadata=None):
    return Event(
        event_id="e1",
        sport=sport,
        league=sport.upper(),
        home_team="Denver Broncos" if sport == "nfl" else "Denver Nuggets",
        away_team="Kansas City Chiefs" if sport == "nfl" else "Boston Celtics",
        start_time=NOW + timedelta(hours=6),
        metadata=metadata or {},
    )


def make_market(market_type=MarketType.SPREAD, line=-3.0):
    return Market(
        event_id="e1",
        market_type=market_type,
        outcomes=["Denver Broncos", "Kansas City Chiefs"],
        prices=[
            Price(book="pinnacle", outcome="Denver Broncos", american=-110, line=line, timestamp=NOW),
            Price(book="pinnacle", outcome="Kansas City Chiefs", american=-110, line=-line, timestamp=NOW),
        ],
    )


def make_ctx(**overrides):
    defaults = dict(
        event=make_event(),
        market=make_market(),
        outcome="Denver Broncos",
        market_probability=0.5,
        now=NOW,
    )
    defaults.update(overrides)
    return SignalContext(**defaults)


class TestHelpers:
    def test_points_move_probability_in_the_right_direction(self):
        assert points_to_logit(3.0, 0.5, "nfl") > 0
        assert points_to_logit(-3.0, 0.5, "nfl") < 0
        assert points_to_logit(0.0, 0.5, "nfl") == 0.0

    def test_points_matter_less_to_heavy_favorites(self):
        # Three points is worth far more *in probability* to a coin flip than
        # to a team already winning 90% of the time. Losing a star from a
        # heavy favorite moves the spread a lot and the win probability
        # barely at all, which is the whole reason the conversion goes
        # through the margin distribution instead of a fixed rate.
        from sharpedge.oddsmath import expit, logit

        def gain(p):
            return expit(logit(p) + points_to_logit(3.0, p, "nfl")) - p

        assert gain(0.50) > gain(0.90) * 2

    def test_residual_is_zero_when_market_already_moved(self):
        residual, credit = residual_after_market_move(3.0, 3.0)
        assert residual == 0.0
        assert credit == 0.0

    def test_residual_survives_a_partial_move(self):
        residual, credit = residual_after_market_move(3.0, 1.0)
        assert residual == pytest.approx(2.0)
        assert credit > 0

    def test_news_decays_with_age(self):
        fresh = recency_credit(NOW, NOW, half_life_min=90)
        old = recency_credit(NOW - timedelta(minutes=90), NOW, half_life_min=90)
        assert fresh == pytest.approx(1.0)
        assert old == pytest.approx(0.5, abs=1e-9)

    def test_no_timestamp_gets_low_credit(self):
        assert recency_credit(None, NOW) < 0.5

    def test_book_lag_credit_collapses_at_kickoff(self):
        assert book_lag_credit(0.1) < book_lag_credit(6.0)


class TestSignalEngine:
    def test_no_signals_leaves_the_market_price(self):
        engine = SignalEngine(signals=[])
        p, contributions = engine.evaluate(make_ctx())
        assert p == pytest.approx(0.5)
        assert contributions == []

    def test_market_trust_shrinks_adjustments(self):
        class Big:
            name = "big"

            def evaluate(self, ctx):
                return [SignalContribution("big", 1.0, 1.0, "test")]

        trusting = SignalEngine([Big()], market_trust=0.0)
        deferring = SignalEngine([Big()], market_trust=0.9)
        p_trust, _ = trusting.evaluate(make_ctx())
        p_defer, _ = deferring.evaluate(make_ctx())
        assert p_trust > p_defer > 0.5

    def test_adjustment_is_capped(self):
        class Absurd:
            name = "absurd"

            def evaluate(self, ctx):
                return [SignalContribution("absurd", 50.0, 1.0, "test")]

        engine = SignalEngine([Absurd()], max_total_logit=0.5, market_trust=0.0)
        p, _ = engine.evaluate(make_ctx())
        # Capped rather than pinned to certainty.
        assert p < 0.65

    def test_zero_weight_signal_has_no_effect(self):
        class Inert:
            name = "inert"

            def evaluate(self, ctx):
                return [SignalContribution("inert", 5.0, 0.0, "flagged only")]

        engine = SignalEngine([Inert()], market_trust=0.0)
        p, contributions = engine.evaluate(make_ctx())
        assert p == pytest.approx(0.5)
        assert len(contributions) == 1  # still reported

    def test_a_broken_signal_does_not_kill_the_run(self):
        class Broken:
            name = "broken"

            def evaluate(self, ctx):
                raise RuntimeError("boom")

        engine = SignalEngine([Broken()])
        p, contributions = engine.evaluate(make_ctx())
        assert p == pytest.approx(0.5)
        assert "failed" in contributions[0].rationale


class TestInjurySignals:
    def test_positional_values_are_sane(self):
        # A quarterback dwarfs everything else in football.
        assert position_value("nfl", "QB") > 5.0
        assert position_value("nfl", "QB") > position_value("nfl", "RB") * 4
        assert position_value("mlb", "SP") > position_value("mlb", "OF")

    def test_out_player_counts_fully(self):
        reports = [
            InjuryReport("Star QB", "Denver Broncos", InjuryStatus.OUT, "QB", 6.5, NOW)
        ]
        points, matched = team_injury_points(reports, "Denver Broncos", "nfl")
        assert points == pytest.approx(6.5)
        assert len(matched) == 1

    def test_questionable_counts_partially(self):
        reports = [
            InjuryReport("Star QB", "Denver Broncos", InjuryStatus.QUESTIONABLE, "QB", 6.5, NOW)
        ]
        points, _ = team_injury_points(reports, "Denver Broncos", "nfl")
        assert 0 < points < 6.5

    def test_multiple_injuries_have_diminishing_returns(self):
        reports = [
            InjuryReport(f"P{i}", "Denver Broncos", InjuryStatus.OUT, "WR", 2.0, NOW)
            for i in range(3)
        ]
        points, _ = team_injury_points(reports, "Denver Broncos", "nfl")
        assert points < 6.0  # not simply 3 x 2.0

    def test_injury_signal_claims_only_the_residual(self):
        # The line has already moved the full amount, so there is nothing left.
        injuries = [
            InjuryReport("Star QB", "Denver Broncos", InjuryStatus.OUT, "QB", 6.5, NOW)
        ]
        ctx = make_ctx(injuries=injuries, opening_line=-3.0, current_line=3.5)
        contributions = InjurySignal().evaluate(ctx)
        assert contributions
        assert contributions[0].weight == 0.0
        assert "fully priced" in contributions[0].rationale

    def test_injury_signal_fires_when_line_has_not_moved(self):
        injuries = [
            InjuryReport("Star QB", "Denver Broncos", InjuryStatus.OUT, "QB", 6.5, NOW)
        ]
        ctx = make_ctx(injuries=injuries, opening_line=-3.0, current_line=-3.0)
        contributions = InjurySignal().evaluate(ctx)
        assert contributions
        assert contributions[0].weight > 0
        # Our team lost its quarterback, so our probability should fall.
        assert contributions[0].logit_adjustment < 0

    def test_opponent_injury_helps_us(self):
        injuries = [
            InjuryReport("Star QB", "Kansas City Chiefs", InjuryStatus.OUT, "QB", 6.5, NOW)
        ]
        ctx = make_ctx(injuries=injuries, opening_line=-3.0, current_line=-3.0)
        contributions = InjurySignal().evaluate(ctx)
        assert contributions[0].logit_adjustment > 0


class TestNewsClassification:
    @pytest.mark.parametrize(
        "headline,expected",
        [
            ("Star QB ruled out for Sunday", InjuryStatus.OUT),
            ("Smith listed as questionable", InjuryStatus.QUESTIONABLE),
            ("Jones is doubtful with an ankle injury", InjuryStatus.DOUBTFUL),
            ("Brown expected to play after clearing protocol", InjuryStatus.PROBABLE),
            ("Davis placed on IR", InjuryStatus.OUT),
            ("Wilson will not play tonight", InjuryStatus.OUT),
        ],
    )
    def test_status_extraction(self, headline, expected):
        assert classify(headline).status == expected

    def test_specific_patterns_beat_general_ones(self):
        # "will not play" must not be read as "will play".
        assert classify("Miller will not play Sunday").status == InjuryStatus.OUT

    def test_category_detection(self):
        assert classify("High winds expected at kickoff").category == "weather"
        assert classify("Coach fired after loss").category == "coaching"
        assert classify("Team resting starters, has clinched").category == "motivation"

    def test_no_status_in_a_plain_headline(self):
        assert classify("Preview: a look at Sunday's matchup").status is None

    def test_player_extraction(self):
        players = extract_players("Patrick Mahomes ruled out for Sunday")
        assert "Patrick Mahomes" in players

    def test_stopwords_are_not_players(self):
        assert "Monday Night" not in extract_players("Monday Night preview")

    def test_team_matching_on_nickname(self):
        teams = match_teams("Chiefs ruled out three starters", ["Kansas City Chiefs"])
        assert teams == ["Kansas City Chiefs"]

    def test_headlines_become_injury_reports(self):
        items = [
            NewsItem(
                headline="Patrick Mahomes ruled out for Sunday",
                published=NOW,
                source="test",
                teams=["Kansas City Chiefs"],
                players=["Patrick Mahomes"],
            )
        ]
        reports = to_injury_reports(items, ["Kansas City Chiefs"], "nfl", {"Patrick Mahomes": 7.0})
        assert len(reports) == 1
        assert reports[0].status == InjuryStatus.OUT
        assert reports[0].point_value == 7.0

    def test_breaking_news_only_fires_when_fresh(self):
        stale = NewsItem("Star ruled out", NOW - timedelta(hours=5), "t", ["Denver Broncos"])
        fresh = NewsItem("Star ruled out", NOW - timedelta(minutes=3), "t", ["Denver Broncos"])
        signal = BreakingNewsSignal()
        assert signal.evaluate(make_ctx(news=[stale])) == []
        assert signal.evaluate(make_ctx(news=[fresh]))


class TestMarketSignals:
    class FakeMovement:
        def __init__(self, stale_books=None, steam=False, direction=0, rlm=False):
            self.stale_books = stale_books or []
            self.steam = steam
            self.steam_direction = direction
            self.reverse_line_movement = rlm

    def test_stale_line_fires_for_the_book_we_bet(self):
        ctx = make_ctx(
            book="espnbet",
            movement=self.FakeMovement(stale_books=[("espnbet", 1.5)]),
        )
        contributions = StaleLineSignal().evaluate(ctx)
        assert contributions
        assert "espnbet" in contributions[0].rationale
        assert contributions[0].weight > 0.5

    def test_stale_line_ignores_other_books(self):
        # Another book being stale is not our edge if we are not betting it.
        ctx = make_ctx(
            book="draftkings",
            movement=self.FakeMovement(stale_books=[("espnbet", 1.5)]),
        )
        assert StaleLineSignal().evaluate(ctx) == []

    def test_no_movement_data_means_no_signal(self):
        assert StaleLineSignal().evaluate(make_ctx()) == []

    def test_retail_shading_favors_the_unpopular_side(self):
        class Fair:
            retail_bias = -0.10  # retail prices this below the sharp number

        contributions = RetailShadingSignal().evaluate(make_ctx(fair_price=Fair()))
        assert contributions
        assert contributions[0].logit_adjustment > 0
        assert "unpopular" in contributions[0].rationale

    def test_retail_shading_penalizes_the_public_side(self):
        class Fair:
            retail_bias = 0.10

        contributions = RetailShadingSignal().evaluate(make_ctx(fair_price=Fair()))
        assert contributions[0].logit_adjustment < 0

    def test_small_shading_is_ignored(self):
        class Fair:
            retail_bias = 0.001

        assert RetailShadingSignal().evaluate(make_ctx(fair_price=Fair())) == []

    def test_handle_divergence_reads_bet_size(self):
        public = PublicBetting("e1", MarketType.SPREAD, "Denver Broncos", 0.35, 0.62)
        contributions = HandleDivergenceSignal().evaluate(
            make_ctx(public=public, outcome="Denver Broncos")
        )
        assert contributions
        assert contributions[0].logit_adjustment > 0

    def test_aligned_ticket_and_handle_says_nothing(self):
        public = PublicBetting("e1", MarketType.SPREAD, "Denver Broncos", 0.55, 0.56)
        assert HandleDivergenceSignal().evaluate(make_ctx(public=public)) == []


class TestSituational:
    def test_back_to_back_hurts(self):
        event = make_event(
            "nba",
            metadata={
                "back_to_back": {"Denver Nuggets": True, "Boston Celtics": False},
                "rest_days": {"Denver Nuggets": 0, "Boston Celtics": 2},
            },
        )
        ctx = make_ctx(event=event, outcome="Denver Nuggets")
        contributions = RestSignal().evaluate(ctx)
        assert contributions
        assert contributions[0].points < 0

    def test_no_metadata_means_no_signal(self):
        assert RestSignal().evaluate(make_ctx(event=make_event("nba"))) == []

    def test_situational_effects_stay_small(self):
        # Guards against the classic tout error of pricing a scheduling spot
        # at three points.
        event = make_event(
            "nba",
            metadata={
                "back_to_back": {"Denver Nuggets": True},
                "third_in_four": {"Denver Nuggets": True},
                "rest_days": {"Denver Nuggets": 0, "Boston Celtics": 3},
            },
        )
        contributions = RestSignal().evaluate(make_ctx(event=event, outcome="Denver Nuggets"))
        assert abs(contributions[0].points) < 3.5

    def test_distance_calculation(self):
        denver = (39.749, -105.008)
        boston = (42.366, -71.062)
        assert 1600 < haversine_miles(denver, boston) < 2000


class TestWeather:
    def test_light_wind_does_nothing(self):
        assert wind_total_impact(5, "nfl") == 0.0
        assert wind_total_impact(9, "nfl") == 0.0

    def test_wind_effect_accelerates(self):
        low = wind_total_impact(12, "nfl")
        mid = wind_total_impact(18, "nfl")
        high = wind_total_impact(25, "nfl")
        assert 0 < low < mid < high
        assert (high - mid) > (mid - low)

    def test_indoor_sports_are_unaffected(self):
        assert wind_total_impact(30, "nba") == 0.0

    def test_dome_games_produce_no_signal(self):
        report = WeatherReport("e1", wind_mph=25, dome=True)
        ctx = make_ctx(market=make_market(MarketType.TOTAL), outcome="Under", weather=report)
        assert WeatherSignal().evaluate(ctx) == []

    def test_high_wind_favors_the_under(self):
        report = WeatherReport("e1", wind_mph=24, temperature_f=40)
        market = Market(
            event_id="e1",
            market_type=MarketType.TOTAL,
            outcomes=["Over", "Under"],
            prices=[],
        )
        under = WeatherSignal().evaluate(
            make_ctx(market=market, outcome="Under", weather=report)
        )
        over = WeatherSignal().evaluate(
            make_ctx(market=market, outcome="Over", weather=report)
        )
        assert under[0].logit_adjustment > 0
        assert over[0].logit_adjustment < 0
