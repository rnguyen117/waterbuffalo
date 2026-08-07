"""Tests for the goal-based risk-reduction recurrence in risk/goals.py."""

from __future__ import annotations

import pytest

from sharpedge.risk.goals import (
    GoalState,
    TargetSeekResult,
    next_goal_state,
    solve_exposure_scale_for_target,
    state_from_history,
)


class TestNextGoalState:
    def test_missing_the_goal_banks_nothing(self):
        # A losing (or merely short) day contributes a negative term to the
        # surplus, which must floor at zero rather than carry forward as
        # "debt" that would justify betting bigger tomorrow.
        state = next_goal_state(
            prior_banked_surplus=0.0, prior_period_profit_units=-2.0, goal_units=3.0
        )
        assert state.banked_surplus == 0.0
        assert state.risk_multiplier == pytest.approx(1.0)

    def test_exactly_hitting_the_goal_banks_nothing_extra(self):
        state = next_goal_state(
            prior_banked_surplus=0.0, prior_period_profit_units=3.0, goal_units=3.0
        )
        assert state.banked_surplus == pytest.approx(0.0)
        assert state.risk_multiplier == pytest.approx(1.0)

    def test_exceeding_the_goal_banks_the_surplus(self):
        state = next_goal_state(
            prior_banked_surplus=0.0, prior_period_profit_units=5.0, goal_units=3.0
        )
        assert state.banked_surplus == pytest.approx(2.0)
        assert state.effective_goal == pytest.approx(1.0)
        assert state.progress_fraction == pytest.approx(2 / 3)

    def test_fully_banking_the_goal_hits_the_multiplier_floor(self):
        state = next_goal_state(
            prior_banked_surplus=0.0,
            prior_period_profit_units=10.0,
            goal_units=3.0,
            min_risk_multiplier=0.4,
        )
        assert state.effective_goal == 0.0
        assert state.is_fully_banked
        assert state.progress_fraction == pytest.approx(1.0)
        assert state.risk_multiplier == pytest.approx(0.4)

    def test_risk_multiplier_never_exceeds_one(self):
        # A day that missed badly must not push size *above* baseline --
        # the recurrence is one-directional (down only).
        state = next_goal_state(
            prior_banked_surplus=0.0, prior_period_profit_units=-50.0, goal_units=3.0
        )
        assert state.risk_multiplier == pytest.approx(1.0)

    def test_risk_multiplier_never_drops_below_the_floor(self):
        state = next_goal_state(
            prior_banked_surplus=0.0,
            prior_period_profit_units=1000.0,
            goal_units=3.0,
            min_risk_multiplier=0.4,
        )
        assert state.risk_multiplier >= 0.4

    def test_partial_progress_interpolates_linearly(self):
        # Half the goal already banked, and this period nets to zero
        # relative to the goal -> stays at half, halfway between 1.0 and
        # the floor.
        state = next_goal_state(
            prior_banked_surplus=1.5,
            prior_period_profit_units=3.0,
            goal_units=3.0,
            min_risk_multiplier=0.4,
        )
        assert state.progress_fraction == pytest.approx(0.5)
        assert state.risk_multiplier == pytest.approx(1.0 - 0.5 * 0.6)

    def test_prior_surplus_carries_forward(self):
        # A prior banked surplus, with this period netting to exactly the
        # goal (contributing nothing either way), should pass through
        # unchanged -- the recurrence must compose correctly across periods.
        state = next_goal_state(
            prior_banked_surplus=4.0, prior_period_profit_units=3.0, goal_units=3.0
        )
        assert state.banked_surplus == pytest.approx(4.0)
        assert state.is_fully_banked

    def test_rejects_nonpositive_goal(self):
        with pytest.raises(ValueError):
            next_goal_state(0.0, 1.0, goal_units=0.0)

    def test_rejects_out_of_range_min_multiplier(self):
        with pytest.raises(ValueError):
            next_goal_state(0.0, 1.0, goal_units=3.0, min_risk_multiplier=1.5)
        with pytest.raises(ValueError):
            next_goal_state(0.0, 1.0, goal_units=3.0, min_risk_multiplier=-0.1)


class TestStateFromHistory:
    def test_empty_history_is_full_risk(self):
        state = state_from_history({}, goal_units=3.0)
        assert state.risk_multiplier == pytest.approx(1.0)
        assert state.banked_surplus == 0.0

    def test_replays_days_in_chronological_order(self):
        # Two days that individually miss the goal but together exceed it
        # should bank the combined surplus, regardless of dict insertion
        # order -- the function must sort by date, not trust caller order.
        history = {"2026-01-02": 4.0, "2026-01-01": 1.0}
        state = state_from_history(history, goal_units=3.0)
        # Day 1: profit 1.0 vs goal 3.0 -> banked 0. Day 2: profit 4.0 vs
        # effective goal (still 3.0, since day 1 banked nothing) -> surplus 1.0.
        assert state.banked_surplus == pytest.approx(1.0)

    def test_consecutive_good_days_compound_the_surplus(self):
        history = {"2026-01-01": 6.0, "2026-01-02": 6.0}
        state = state_from_history(history, goal_units=3.0)
        # Day 1: surplus 3.0. Day 2: 3.0 + (6.0 - 3.0) = 6.0.
        assert state.banked_surplus == pytest.approx(6.0)
        assert state.is_fully_banked

    def test_a_losing_day_after_banking_does_not_go_negative(self):
        history = {"2026-01-01": 6.0, "2026-01-02": -10.0}
        state = state_from_history(history, goal_units=3.0)
        # Day 1 banks 3.0. Day 2: 3.0 + (-10.0 - 3.0) = -10.0 -> floored to 0.
        assert state.banked_surplus == 0.0
        assert state.risk_multiplier == pytest.approx(1.0)

    def test_matches_hand_rolled_recurrence(self):
        history = {"2026-01-01": 5.0, "2026-01-02": -1.0, "2026-01-03": 2.0}
        goal = 3.0
        banked = 0.0
        for day in sorted(history):
            banked = max(banked + (history[day] - goal), 0.0)
        state = state_from_history(history, goal_units=goal)
        assert state.banked_surplus == pytest.approx(banked)


class TestSolveExposureScaleForTarget:
    """Uses synthetic, deterministic profit curves rather than the real
    pipeline -- the solver only assumes monotonicity, and testing it against
    hand-built curves pins down its own logic independent of whatever the
    portfolio optimizer happens to produce on a given day. The real curve is
    exercised separately in tests/test_pipeline.py against pipeline.stake.
    """

    def _linear(self, slope=2.0):
        return lambda scale: slope * scale

    def _capped_linear(self, slope=2.0, cap_scale=1.3):
        # Rises linearly, then plateaus past cap_scale -- mimics a portfolio
        # optimizer hitting its per-bet/per-game caps before total exposure.
        return lambda scale: slope * min(scale, cap_scale)

    def test_baseline_already_clears_goal_needs_no_scale_up(self):
        result = solve_exposure_scale_for_target(self._linear(slope=5.0), target_profit_units=3.0)
        assert result.scale == 1.0
        assert result.achieved
        assert result.expected_profit_units == pytest.approx(5.0)

    def test_finds_the_minimal_sufficient_scale(self):
        # slope=2 means profit(scale) = 2*scale; target=3 -> scale=1.5 exactly.
        result = solve_exposure_scale_for_target(
            self._linear(slope=2.0), target_profit_units=3.0, max_scale=2.0, tol=1e-4
        )
        assert result.achieved
        assert result.scale == pytest.approx(1.5, abs=1e-3)
        assert result.expected_profit_units == pytest.approx(3.0, abs=1e-2)

    def test_never_scales_below_one(self):
        # Even a target barely above baseline should not return scale < 1.0.
        result = solve_exposure_scale_for_target(self._linear(slope=1.0), target_profit_units=1.0001)
        assert result.scale >= 1.0

    def test_unreachable_target_reports_shortfall_honestly(self):
        result = solve_exposure_scale_for_target(
            self._capped_linear(slope=1.0, cap_scale=1.2), target_profit_units=10.0, max_scale=1.5
        )
        assert not result.achieved
        assert result.scale == 1.5
        assert result.expected_profit_units == pytest.approx(1.2, abs=1e-6)
        assert "short of" in result.note

    def test_respects_the_max_scale_ceiling(self):
        result = solve_exposure_scale_for_target(
            self._linear(slope=2.0), target_profit_units=100.0, max_scale=1.5
        )
        assert result.scale <= 1.5
        assert not result.achieved

    def test_rejects_nonpositive_target(self):
        with pytest.raises(ValueError):
            solve_exposure_scale_for_target(self._linear(), target_profit_units=0.0)
        with pytest.raises(ValueError):
            solve_exposure_scale_for_target(self._linear(), target_profit_units=-1.0)

    def test_rejects_max_scale_below_one(self):
        with pytest.raises(ValueError):
            solve_exposure_scale_for_target(self._linear(), target_profit_units=1.0, max_scale=0.9)

    def test_result_is_a_frozen_dataclass(self):
        result = solve_exposure_scale_for_target(self._linear(slope=5.0), target_profit_units=3.0)
        assert isinstance(result, TargetSeekResult)
        with pytest.raises(Exception):
            result.scale = 99.0
