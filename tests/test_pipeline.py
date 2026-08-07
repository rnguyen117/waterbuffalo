"""End-to-end tests: ledger, calibration, simulation, and a full daily run."""

from datetime import datetime, timedelta, timezone

import pytest

from sharpedge import pipeline, report
from sharpedge.backtest.simulate import (
    risk_of_drawdown,
    simulate_season,
    simulate_slate,
)
from sharpedge.config import Config
from sharpedge.market.movement import LineHistory
from sharpedge.models import BetStatus, Confidence, MarketType
from sharpedge.risk.bankroll import BankrollState, StakingRules, days_to_double
from sharpedge.sources.demo import DemoSource
from sharpedge.track import calibration, clv
from sharpedge.track.ledger import Ledger


class TestDemoSource:
    def test_generates_a_slate(self):
        events = DemoSource(seed=1, n_events=6).fetch_events(["nfl", "nba"])
        assert len(events) == 6
        assert all(e.markets for e in events)

    def test_every_event_has_the_three_core_markets(self):
        events = DemoSource(seed=1, n_events=3).fetch_events(["nfl"])
        for e in events:
            types = {m.market_type for m in e.markets}
            assert types == {MarketType.MONEYLINE, MarketType.SPREAD, MarketType.TOTAL}

    def test_markets_are_priced_by_many_books(self):
        events = DemoSource(seed=1, n_events=1).fetch_events(["nfl"])
        market = events[0].markets[0]
        assert len(market.books()) >= 10

    def test_reproducible_with_a_seed(self):
        a = DemoSource(seed=42, n_events=3).fetch_events(["nfl"])
        b = DemoSource(seed=42, n_events=3).fetch_events(["nfl"])
        assert [e.home_team for e in a] == [e.home_team for e in b]

    def test_sharp_books_charge_less_vig(self):
        from sharpedge.market.consensus import book_hold

        events = DemoSource(seed=3, n_events=1).fetch_events(["nfl"])
        market = events[0].markets[0]
        sharp = book_hold(market, "pinnacle")
        soft = book_hold(market, "bovada")
        assert sharp < soft

    def test_ancillary_feeds_produce_data(self):
        source = DemoSource(seed=5, n_events=6)
        events = source.fetch_events(["nfl", "nba"])
        assert source.fetch_news(events)
        assert source.fetch_public(events)
        assert isinstance(source.fetch_weather(events), dict)

    def test_wnba_gets_its_own_teams_and_scoring_level(self):
        # Before the fix, any sport other than "nfl" fell through to the
        # NBA's team list -- adding WNBA without a real per-sport lookup
        # would have quietly generated WNBA-tagged games played between NBA
        # franchises at NBA scoring levels.
        from sharpedge.sources.demo import NBA_TEAMS, WNBA_TEAMS

        events = DemoSource(seed=9, n_events=6).fetch_events(["wnba"])
        assert len(events) == 6
        for e in events:
            assert e.sport == "wnba"
            assert e.home_team in WNBA_TEAMS
            assert e.away_team in WNBA_TEAMS
            assert e.home_team not in NBA_TEAMS

    def test_wnba_totals_are_lower_than_nba(self):
        # WNBA quarters run 10 minutes to the NBA's 12; the combined score
        # should land well below the NBA's, not share its scoring level.
        nba_events = DemoSource(seed=11, n_events=10).fetch_events(["nba"])
        wnba_events = DemoSource(seed=11, n_events=10).fetch_events(["wnba"])

        def total_line(events):
            for e in events:
                for p in e.market(MarketType.TOTAL).prices_for("Over"):
                    if p.line is not None:
                        return p.line
            return None

        assert total_line(wnba_events) < total_line(nba_events)


class TestSameDayFilter:
    """filters.same_day_only: one slate, one calendar date, not a blend of
    tonight's MLB and next Sunday's NFL."""

    def _inputs(self, events):
        return pipeline.Inputs(events=events, news=[], injuries=[], weather={}, public=[])

    def _event(self, event_id, start_time, sport="nfl"):
        from sharpedge.models import Event

        # Distinct team names per event_id -- Event.name is derived from
        # them, and two events sharing the same names would collide in any
        # assertion keyed on result.skipped's (name, reason) pairs.
        return Event(
            event_id=event_id, sport=sport, league=sport.upper(),
            home_team=f"Home {event_id}", away_team=f"Away {event_id}", start_time=start_time,
        )

    def test_same_schedule_day_unit(self):
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        now = datetime(2026, 1, 15, 20, 0, tzinfo=et)  # 8pm ET
        same_day_later = datetime(2026, 1, 15, 23, 30, tzinfo=et)
        next_day = datetime(2026, 1, 16, 0, 30, tzinfo=et)
        assert pipeline._same_schedule_day(same_day_later, now, et)
        assert not pipeline._same_schedule_day(next_day, now, et)

    def test_same_schedule_day_handles_utc_midnight_seam(self):
        # A 1pm ET game and a 9pm ET game on the *same* Eastern calendar
        # day land on two different UTC dates (18:00 UTC vs. 02:00 UTC the
        # next day) -- comparing raw UTC dates would incorrectly read these
        # as two different slates. Anchoring to ET must call them the same.
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        afternoon_game = datetime(2026, 1, 15, 13, 0, tzinfo=et)
        primetime_game = datetime(2026, 1, 15, 21, 0, tzinfo=et)
        assert afternoon_game.astimezone(timezone.utc).date() != primetime_game.astimezone(
            timezone.utc
        ).date(), "test setup should actually cross a UTC date boundary"
        assert pipeline._same_schedule_day(primetime_game, afternoon_game, et)

    def test_events_on_other_days_are_excluded_by_default(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        now = pipeline.utcnow()
        today = self._event("today", now + timedelta(hours=3))
        next_week = self._event("next-week", now + timedelta(days=6))
        result = pipeline.run(self._inputs([today, next_week]), cfg, now=now)
        skipped_names = {name for name, _ in result.skipped}
        assert next_week.name in skipped_names
        assert today.name not in skipped_names

    def test_skip_reason_mentions_the_slate(self, tmp_path):
        # +30h is comfortably inside the default 96h max_hours_to_start
        # window but always lands on a different Eastern calendar date --
        # the max_hours_to_start check must not be what fires first here,
        # or this is just re-testing that filter instead of same_day_only.
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        now = pipeline.utcnow()
        tomorrow = self._event("tomorrow", now + timedelta(hours=30))
        result = pipeline.run(self._inputs([tomorrow]), cfg, now=now)
        reasons = dict(result.skipped)
        assert "slate" in reasons[tomorrow.name]

    def test_disabling_same_day_only_falls_back_to_rolling_window(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        cfg.filters.same_day_only = False
        cfg.filters.max_hours_to_start = 24 * 10  # 10 days, wide enough
        now = pipeline.utcnow()
        next_week = self._event("next-week", now + timedelta(days=6))
        result = pipeline.run(self._inputs([next_week]), cfg, now=now)
        skipped_names = {name for name, _ in result.skipped}
        assert next_week.name not in skipped_names

    def test_respects_a_configured_schedule_timezone(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        cfg.filters.schedule_timezone = "America/Los_Angeles"
        now = pipeline.utcnow()
        # An event 20 hours out is very likely still "today" Pacific but
        # could cross an Eastern midnight -- exercising a non-default zone
        # end-to-end, not just that *some* zone is used.
        soon = self._event("soon", now + timedelta(hours=2))
        result = pipeline.run(self._inputs([soon]), cfg, now=now)
        skipped_names = {name for name, _ in result.skipped}
        assert soon.name not in skipped_names


class TestFullPipeline:
    def test_runs_without_error(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        inputs = pipeline.fetch_inputs(cfg)
        history = LineHistory(tmp_path / "lines.db")
        result = pipeline.run(inputs, cfg, history=history)
        history.close()
        assert result.considered > 0
        assert isinstance(result.bets, list)

    def test_screen_then_stake_matches_run(self, tmp_path):
        # run() is documented as screen() followed by stake(); if that ever
        # drifts, everything built on re-staking a screened slate (the
        # target-profit solver) would silently produce a different card
        # than a plain `sharp-edge card` run.
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        inputs = pipeline.fetch_inputs(cfg)
        now = pipeline.utcnow()
        via_run = pipeline.run(inputs, cfg, now=now)
        screened = pipeline.screen(inputs, cfg, now=now)
        via_split = pipeline.stake(screened, cfg, now=now)
        assert len(via_run.bets) == len(via_split.bets)
        assert via_run.total_stake == pytest.approx(via_split.total_stake)
        assert via_run.expected_profit == pytest.approx(via_split.expected_profit)

    def test_stake_is_reusable_across_different_exposure_caps(self, tmp_path):
        # The whole point of the split: re-staking the same screened slate
        # at a different exposure scale should change the stakes without
        # needing to re-screen the market.
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        inputs = pipeline.fetch_inputs(cfg)
        screened = pipeline.screen(inputs, cfg)

        baseline = pipeline.stake(screened, cfg)

        cfg_bigger = Config()
        cfg_bigger.data_dir = str(tmp_path)
        cfg_bigger.portfolio.max_total_exposure *= 2
        cfg_bigger.portfolio.max_per_bet *= 2
        cfg_bigger.portfolio.max_per_game *= 2
        cfg_bigger.portfolio.max_per_book *= 2
        scaled = pipeline.stake(screened, cfg_bigger)

        assert scaled.total_stake > baseline.total_stake
        assert scaled.expected_profit > baseline.expected_profit

    def test_finds_the_planted_stale_lines(self, tmp_path):
        # The demo generator deliberately leaves some soft books behind the
        # market. With props disabled the card is core markets only, so the
        # stale lines are what should surface. If nothing does, the screen is
        # broken rather than disciplined.
        #
        # Sports are pinned explicitly rather than left at the config
        # default: this test is about stale-line detection, not about how
        # many sports happen to be active out of the box, and it should not
        # flake if that default list changes size.
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        cfg.sources.sports = ["nfl", "nba"]
        cfg.filters.include_props = False
        cfg.filters.include_derivatives = False
        inputs = pipeline.fetch_inputs(cfg)
        result = pipeline.run(inputs, cfg)
        assert result.bets, "pipeline found no bets on a slate with planted edges"
        reasons = " ".join(
            c.rationale for bet in result.bets for c in bet.signals
        )
        assert "off the sharp consensus" in reasons

    def test_never_recommends_a_negative_ev_bet(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        assert all(bet.ev > 0 for bet in result.bets)

    def test_respects_exposure_limits(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        cap = cfg.bankroll.starting * cfg.portfolio.max_total_exposure
        assert result.total_stake <= cap + 1e-6

    def test_no_bet_exceeds_the_per_bet_cap(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        cap = cfg.bankroll.starting * cfg.portfolio.max_per_bet
        assert all(bet.stake <= cap + 1e-6 for bet in result.bets)

    def test_never_bets_both_sides_of_a_market(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        seen = set()
        for bet in result.bets:
            # market_key carries the prop subject and line, so two players'
            # props are not mistaken for two sides of one market.
            key = bet.market_key()
            assert key not in seen, "recommended both sides of the same market"
            seen.add(key)

    def test_only_recommends_bettable_books(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        cfg.accounts.books = ["draftkings", "fanduel"]
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        assert all(bet.book in {"draftkings", "fanduel"} for bet in result.bets)

    def test_a_strict_filter_produces_an_empty_card(self, tmp_path):
        # An impossible EV floor must yield nothing rather than the least-bad
        # option, because "bet something" is not a valid answer.
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        cfg.filters.min_ev = 0.99
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        assert result.bets == []

    def test_higher_market_trust_produces_fewer_bets(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        inputs = pipeline.fetch_inputs(cfg)

        cfg.model.market_trust = 0.2
        bold = pipeline.run(inputs, cfg)
        cfg.model.market_trust = 0.95
        humble = pipeline.run(inputs, cfg)
        assert len(humble.bets) <= len(bold.bets)

    def test_every_bet_carries_its_reasoning(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        for bet in result.bets:
            assert bet.notes
            assert bet.confidence != Confidence.PASS


class TestReporting:
    def test_console_renders(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        text = report.console(result, verbose=True)
        assert "DAILY CARD" in text

    def test_empty_card_says_so_plainly(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        cfg.filters.min_ev = 0.99
        text = report.console(pipeline.run(pipeline.fetch_inputs(cfg), cfg))
        assert "No bets today" in text

    def test_json_is_valid(self, tmp_path):
        import json

        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        payload = json.loads(report.to_json(result))
        assert payload["prices_screened"] > 0
        assert len(payload["bets"]) == len(result.bets)

    def test_markdown_renders(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        assert "Daily Card" in report.markdown(result)


class TestLedger:
    def _bet(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        assert result.bets
        return result.bets[0]

    def test_records_and_settles(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        bet_id = ledger.record(self._bet(tmp_path))
        assert len(ledger.pending()) == 1

        profit = ledger.settle(bet_id, BetStatus.WON, closing_american=-130)
        assert profit > 0
        assert len(ledger.pending()) == 0
        ledger.close()

    def test_loss_returns_the_stake(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        bet = self._bet(tmp_path)
        bet_id = ledger.record(bet)
        assert ledger.settle(bet_id, BetStatus.LOST) == pytest.approx(-bet.stake)
        ledger.close()

    def test_push_is_flat(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        bet_id = ledger.record(self._bet(tmp_path))
        assert ledger.settle(bet_id, BetStatus.PUSHED) == 0.0
        ledger.close()

    def test_clv_computed_from_the_closing_price(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        bet = self._bet(tmp_path)
        bet_id = ledger.record(bet)
        # Closing much shorter than we took means we beat the number.
        ledger.settle(bet_id, BetStatus.LOST, closing_american=-200)
        entry = ledger.settled()[0]
        assert entry.clv is not None
        assert entry.clv > 0
        ledger.close()

    def test_summary_on_an_empty_ledger(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        assert ledger.summary()["bets"] == 0
        ledger.close()

    def test_breakdown_by_book(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        bet_id = ledger.record(self._bet(tmp_path))
        ledger.settle(bet_id, BetStatus.WON)
        assert ledger.by_dimension("book")
        ledger.close()

    def test_rejects_an_unknown_dimension(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        with pytest.raises(ValueError):
            ledger.by_dimension("nonsense")
        ledger.close()

    def test_settling_a_missing_bet_raises(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        with pytest.raises(KeyError):
            ledger.settle(999, BetStatus.WON)
        ledger.close()

    def test_scorecard_counts_wins_and_losses_not_pushes(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        for status in (BetStatus.WON, BetStatus.WON, BetStatus.LOST, BetStatus.PUSHED):
            bet_id = ledger.record(self._bet(tmp_path))
            ledger.settle(bet_id, status)
        card = ledger.scorecard()
        assert card == {"wins": 2, "losses": 1, "graded": 3, "win_rate": pytest.approx(2 / 3)}
        ledger.close()

    def test_scorecard_on_empty_ledger(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        assert ledger.scorecard() == {"wins": 0, "losses": 0, "graded": 0, "win_rate": 0.0}
        ledger.close()

    def test_daily_pnl_units_groups_by_settlement_day(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        bet = self._bet(tmp_path)
        bet_id = ledger.record(bet)
        profit = ledger.settle(bet_id, BetStatus.WON)
        daily = ledger.daily_pnl_units(unit_size=bet.stake)
        assert len(daily) == 1
        (day, units), = daily.items()
        assert units == pytest.approx(profit / bet.stake)
        ledger.close()

    def test_daily_pnl_units_rejects_nonpositive_unit_size(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        with pytest.raises(ValueError):
            ledger.daily_pnl_units(unit_size=0.0)
        ledger.close()


class TestCalibration:
    def test_perfectly_calibrated_model_scores_well(self):
        import random

        rng = random.Random(3)
        predictions, outcomes = [], []
        for _ in range(4000):
            p = rng.uniform(0.35, 0.75)
            predictions.append(p)
            outcomes.append(1 if rng.random() < p else 0)
        rep = calibration.analyze(predictions, outcomes)
        assert rep.expected_calibration_error < 0.05
        assert 0.85 < rep.overconfidence < 1.2

    def test_overconfident_model_is_detected(self):
        import random

        rng = random.Random(4)
        predictions, outcomes = [], []
        for _ in range(4000):
            true_p = rng.uniform(0.45, 0.55)
            # Claims far more edge than exists.
            claimed = 0.5 + (true_p - 0.5) * 4
            predictions.append(min(max(claimed, 0.02), 0.98))
            outcomes.append(1 if rng.random() < true_p else 0)
        rep = calibration.analyze(predictions, outcomes)
        assert rep.overconfidence > 1.2

    def test_brier_of_a_coin_flip(self):
        assert calibration.brier_score([0.5] * 100, [1, 0] * 50) == pytest.approx(0.25)

    def test_log_loss_punishes_confident_errors(self):
        mild = calibration.log_loss([0.6], [0])
        severe = calibration.log_loss([0.99], [0])
        assert severe > mild * 4

    def test_small_sample_is_not_judged(self):
        rep = calibration.analyze([0.5] * 10, [1, 0] * 5)
        assert "too few" in rep.verdict

    def test_suggested_trust_rises_with_overconfidence(self):
        rep = calibration.CalibrationReport([], 0.25, 0.7, 0.08, 1.5, 500)
        assert calibration.suggested_market_trust(rep, 0.60) > 0.60

    def test_small_samples_do_not_move_the_config(self):
        rep = calibration.CalibrationReport([], 0.25, 0.7, 0.08, 1.5, 20)
        assert calibration.suggested_market_trust(rep, 0.60) == 0.60


class TestBankroll:
    def test_tracks_growth_and_drawdown(self):
        state = BankrollState.new(10_000)
        state.record(1_000, 500)
        assert state.current == 11_000
        assert state.peak == 11_000
        state.record(-2_000, 2_000)
        assert state.drawdown == pytest.approx(2_000 / 11_000)

    def test_stop_loss_halts_betting(self):
        state = BankrollState.new(10_000)
        state.record(-4_000, 4_000)
        rules = StakingRules(stop_loss_drawdown=0.35)
        halt, why = rules.should_halt(state)
        assert halt
        assert "stop loss" in why
        assert rules.size(state, kelly_fraction=0.05) == 0.0

    def test_stake_scales_with_bankroll(self):
        rules = StakingRules()
        big = BankrollState.new(100_000)
        small = BankrollState.new(1_000)
        assert rules.size(big, 0.04) > rules.size(small, 0.04)

    def test_days_to_double_is_realistic(self):
        # A 2% edge at 1% of bankroll is a long grind, not a get-rich scheme.
        days = days_to_double(0.02, bets_per_day=10, fraction=0.01)
        assert days > 300


class TestSimulation:
    def test_slate_simulation_summarizes(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        if not result.bets:
            pytest.skip("no bets to simulate")
        sim = simulate_slate(result.bets, trials=2000)
        assert sim.p05 < sim.median_profit < sim.p95
        assert 0.0 <= sim.prob_profit <= 1.0

    def test_empty_slate_is_safe(self):
        assert simulate_slate([], trials=100).trials == 0

    def test_a_real_edge_usually_wins_over_a_season(self):
        sim = simulate_season(edge=0.04, bets_per_day=5, days=180,
                              bankroll=10_000, kelly_fraction=0.01, trials=600)
        assert sim.prob_profit > 0.7

    def test_a_genuine_edge_still_loses_sometimes(self):
        # The honest reality check: a real but small edge is not a guarantee.
        sim = simulate_season(edge=0.01, bets_per_day=1, days=100,
                              bankroll=10_000, kelly_fraction=0.01, trials=800)
        assert sim.prob_profit < 0.95

    def test_no_edge_loses_money_on_average(self):
        sim = simulate_season(edge=-0.045, bets_per_day=3, days=100,
                              bankroll=10_000, kelly_fraction=0.01, trials=600)
        assert sim.mean_profit < 0

    def test_drawdowns_are_common_even_when_winning(self):
        risk = risk_of_drawdown(edge=0.03, bets=1000, kelly_fraction=0.02, threshold=0.20)
        assert risk > 0.05


class TestCLVReporting:
    def test_empty_ledger_reports_nothing(self, tmp_path):
        ledger = Ledger(tmp_path / "bets.db")
        rep = clv.analyze(ledger)
        assert rep.n == 0
        ledger.close()

    def test_four_quadrant_diagnosis(self):
        good = clv.CLVReport(200, 0.02, 0.02, 0.6, 3.0, "strong", 0.018, {}, {})
        assert "real edge" in clv.diagnose(good, roi=0.05)
        assert "variance" in clv.diagnose(good, roi=-0.03)

        bad = clv.CLVReport(200, -0.02, -0.02, 0.35, -3.0, "negative", -0.018, {}, {})
        assert "dangerous" in clv.diagnose(bad, roi=0.05)
        assert "not identifying value" in clv.diagnose(bad, roi=-0.05)

    def test_small_samples_are_not_diagnosed(self):
        tiny = clv.CLVReport(10, 0.02, 0.02, 0.6, 1.0, "x", 0.018, {}, {})
        assert "Not enough" in clv.diagnose(tiny, roi=0.05)
