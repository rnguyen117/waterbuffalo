"""Tests for configuration, including unit-size reporting."""

import json

import pytest

from sharpedge.config import BankrollConfig, Config
from sharpedge import pipeline, report


class TestUnitSize:
    def test_default_unit_is_one_percent_of_bankroll(self):
        cfg = BankrollConfig(starting=10_000.0)
        assert cfg.effective_unit_size == pytest.approx(100.0)

    def test_explicit_unit_size_overrides_the_default(self):
        cfg = BankrollConfig(starting=10_000.0, unit_size=50.0)
        assert cfg.effective_unit_size == pytest.approx(50.0)

    def test_unit_size_rebases_with_bankroll_when_unset(self):
        small = BankrollConfig(starting=1_000.0)
        large = BankrollConfig(starting=100_000.0)
        assert small.effective_unit_size == pytest.approx(10.0)
        assert large.effective_unit_size == pytest.approx(1_000.0)

    def test_to_units_converts_correctly(self):
        cfg = BankrollConfig(starting=10_000.0, unit_size=50.0)
        assert cfg.to_units(150.0) == pytest.approx(3.0)

    def test_to_units_handles_zero_unit_safely(self):
        cfg = BankrollConfig(starting=0.0, unit_size=0.0)
        assert cfg.to_units(100.0) == 0.0


class TestUnitSizeInReports:
    def test_console_shows_units_at_the_configured_size(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        cfg.bankroll.unit_size = 25.0
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        text = report.console(result, unit_size=cfg.bankroll.effective_unit_size)
        assert "1 unit = $25.00" in text

    def test_console_defaults_to_one_percent_when_unset(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        text = report.console(result)
        assert f"1 unit = ${cfg.bankroll.starting / 100:,.2f}" in text

    def test_json_carries_unit_size_and_per_bet_units(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        cfg.bankroll.unit_size = 40.0
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        payload = json.loads(report.to_json(result, unit_size=40.0))
        assert payload["unit_size"] == 40.0
        for bet in payload["bets"]:
            expected = bet["stake"] / 40.0
            assert bet["stake_units"] == pytest.approx(expected, abs=0.01)

    def test_json_carries_kelly_fraction_per_bet(self, tmp_path):
        # Needed by the web dashboard to recompute stakes at a different
        # bankroll/unit size without re-running the Python pipeline.
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        payload = json.loads(report.to_json(result))
        for bet in payload["bets"]:
            assert "kelly_fraction" in bet
            assert "sigma_logit" in bet
            assert "model_probability" in bet

    def test_markdown_shows_units_column(self, tmp_path):
        cfg = Config()
        cfg.data_dir = str(tmp_path)
        result = pipeline.run(pipeline.fetch_inputs(cfg), cfg)
        text = report.markdown(result, unit_size=50.0)
        assert "Units" in text
