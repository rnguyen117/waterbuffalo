"""Tests for the `sharp-edge card` CLI's goal tracking and target-seeking.

Exercises _cmd_card directly (an argparse.Namespace stands in for parsed
CLI args) rather than shelling out to the entry point, so these run as fast
in-process unit tests.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

import pytest

from sharpedge.cli import _cmd_card, _scale_exposure
from sharpedge.config import Config
from sharpedge.models import BetStatus
from sharpedge.track.ledger import Ledger


def _card_args(tmp_path, target_profit=None, json_out=None):
    return argparse.Namespace(
        bankroll=None, unit_size=None, kelly_multiplier=None, top=None, rank=None,
        min_probability=None, no_props=False, props_only=False, verbose=False,
        log=False, json=str(json_out) if json_out else None, markdown=None,
        target_profit=target_profit,
    )


def _run_card(tmp_path, target_profit=None):
    out = tmp_path / "card.json"
    cfg = Config()
    cfg.data_dir = str(tmp_path)
    args = _card_args(tmp_path, target_profit=target_profit, json_out=out)
    rc = _cmd_card(args, cfg)
    assert rc == 0
    return json.loads(out.read_text())


class TestScaleExposure:
    def test_scales_every_exposure_lever(self):
        cfg = Config()
        before = (
            cfg.portfolio.max_total_exposure,
            cfg.portfolio.max_per_bet,
            cfg.portfolio.max_per_game,
            cfg.portfolio.max_per_book,
            cfg.bankroll.max_bet_fraction,
        )
        _scale_exposure(cfg, 0.5)
        after = (
            cfg.portfolio.max_total_exposure,
            cfg.portfolio.max_per_bet,
            cfg.portfolio.max_per_game,
            cfg.portfolio.max_per_book,
            cfg.bankroll.max_bet_fraction,
        )
        for b, a in zip(before, after):
            assert a == pytest.approx(b * 0.5)

    def test_does_not_touch_kelly_multiplier(self):
        # The whole point of the fix: kelly_multiplier is not the lever
        # that controls final stake size, so scaling exposure must not
        # touch it.
        cfg = Config()
        before = cfg.bankroll.kelly_multiplier
        _scale_exposure(cfg, 0.5)
        assert cfg.bankroll.kelly_multiplier == before


class TestTargetProfitFlag:
    def test_enables_auto_target_and_sets_goal(self, tmp_path):
        payload = _run_card(tmp_path, target_profit=3.0)
        assert payload["card_stats"]["goal"]["daily_goal_units"] == 3.0
        assert "target_seek" in payload["card_stats"]["goal"]

    def test_achievable_target_scales_exposure_up(self, tmp_path):
        baseline = _run_card(tmp_path / "baseline")
        targeted = _run_card(tmp_path / "targeted", target_profit=3.0)

        ts = targeted["card_stats"]["goal"]["target_seek"]
        assert ts["achieved"]
        assert ts["scale"] >= 1.0
        # A higher exposure scale should produce at least as much total
        # stake as the untargeted baseline (same screened slate, same seed).
        assert targeted["total_stake"] >= baseline["total_stake"] - 1e-6

    def test_target_already_met_leaves_baseline_scale_alone(self, tmp_path):
        baseline = _run_card(tmp_path / "baseline")
        # 0.5u is trivially below what the default demo card projects.
        low_target = _run_card(tmp_path / "low", target_profit=0.5)
        ts = low_target["card_stats"]["goal"]["target_seek"]
        assert ts["achieved"]
        assert ts["scale"] == pytest.approx(1.0)
        assert low_target["total_stake"] == pytest.approx(baseline["total_stake"])

    def test_unreachable_target_reports_shortfall_and_caps_scale(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        cfg.goals.max_target_scale = 1.5
        out = tmp_path / "card.json"
        args = _card_args(tmp_path, target_profit=1000.0, json_out=out)
        _cmd_card(args, cfg)
        payload = json.loads(out.read_text())
        ts = payload["card_stats"]["goal"]["target_seek"]
        assert not ts["achieved"]
        assert ts["scale"] == pytest.approx(1.5)
        assert "short of" in ts["note"]

    def test_auto_target_off_by_default_ignores_daily_goal_units_alone(self, tmp_path):
        # Setting daily_goal_units in config without --target-profit (i.e.
        # without auto_target) must not change sizing -- auto-scaling is
        # opt-in.
        baseline = _run_card(tmp_path / "baseline")

        cfg = Config()
        cfg.data_dir = str(tmp_path / "notarget")
        cfg.goals.daily_goal_units = 50.0
        out = tmp_path / "notarget_card.json"
        args = _card_args(tmp_path, json_out=out)
        _cmd_card(args, cfg)
        payload = json.loads(out.read_text())

        assert "target_seek" not in payload["card_stats"]["goal"]
        assert payload["total_stake"] == pytest.approx(baseline["total_stake"])


class TestGoalRiskReduction:
    def _seed_big_winning_day(self, data_dir):
        """A day that blows well past a 3u goal, settled yesterday."""
        ledger = Ledger(data_dir / "bets.db")
        now = datetime.now(timezone.utc)

        class FakeEvent:
            event_id = "hist-1"
            name = "Historical Game"
            league = "NFL"
            start_time = now - timedelta(days=2)

        class FakeFair:
            probability = 0.54

        class FakeBet:
            event = FakeEvent()
            market_type = type("M", (), {"value": "spread"})()
            outcome = "Home"
            line = -3.5
            book = "draftkings"
            american = 150
            stake = 300.0
            fair = FakeFair()
            model_probability = 0.55
            confidence = type("C", (), {"value": "B"})()
            ev = 0.10
            signals = []

        bet_id = ledger.record(FakeBet(), placed_at=now - timedelta(days=1, hours=6))
        ledger.settle(bet_id, BetStatus.WON)
        settled_at = now - timedelta(days=1, hours=1)
        ledger.conn.execute(
            "UPDATE bets SET settled_at=? WHERE id=?", (settled_at.isoformat(), bet_id)
        )
        ledger.conn.commit()
        ledger.close()

    def test_being_ahead_of_goal_actually_shrinks_the_card(self, tmp_path):
        # Regression test for the bug this session found: risk reduction
        # used to scale bankroll.kelly_multiplier, which the portfolio
        # optimizer largely ignores once a bet clears the eligibility
        # floor, so being "ahead of goal" did not actually reduce stakes.
        # It must now shrink real exposure.
        baseline_dir = tmp_path / "baseline"
        baseline_dir.mkdir()
        baseline = _run_card(baseline_dir)

        ahead_dir = tmp_path / "ahead"
        ahead_dir.mkdir()
        self._seed_big_winning_day(ahead_dir)
        cfg = Config()
        cfg.data_dir = str(ahead_dir)
        out = ahead_dir / "card.json"
        args = _card_args(ahead_dir, json_out=out)
        _cmd_card(args, cfg)
        ahead = json.loads(out.read_text())

        assert ahead["card_stats"]["goal"]["risk_multiplier"] < 0.999
        assert ahead["total_stake"] < baseline["total_stake"]
