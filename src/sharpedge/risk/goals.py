"""Goal-based risk reduction.

A different kind of discipline than the stop-loss in ``bankroll.py``. That
one answers "how bad is too bad" on the downside. This one answers a
question that most staking plans ignore entirely: what happens the day
*after* a good day?

The naive answers are both wrong. Betting the same size regardless of
yesterday ignores real information -- a day that cleared the goal was either
skill or variance, and either way there is no reason to keep pressing at full
size once the target for the period is already banked. Betting *bigger*
after a good day is worse: that is revenge-betting's twin, chasing a
streak instead of a loss, and it is how a good month turns into a bad
quarter. The only sound adjustment is downward, and only in proportion to
how much of the goal is already sitting in the bank.

So: pick a daily (or per-period) profit goal, denominated in units so it
means the same thing regardless of bankroll size. Once a day's profit clears
that goal, the surplus is "banked" and carries forward, reducing how much of
tomorrow's goal is still outstanding. The more of the goal that is already
banked, the smaller the size on the next day's bets -- continuously, not as
a step function, and floored so the model never stops betting outright (that
is what the stop-loss is for). A losing day banks nothing negative: the
surplus floors at zero, so a bad day never becomes license to bet bigger to
catch up. That asymmetry is the whole point.

This is deliberately scoped to the entire bankroll, not per sport -- one
goal, one risk dial, regardless of what mix of NFL, MLB, WNBA, or tennis
bets produced yesterday's number.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class GoalState:
    """Where the goal recurrence stands going into the next period."""

    banked_surplus: float      # units carried forward, floored at 0
    effective_goal: float      # units still needed this period
    progress_fraction: float   # 0 = nothing banked, 1 = goal fully covered
    risk_multiplier: float     # multiplies kelly_multiplier for this period

    @property
    def is_fully_banked(self) -> bool:
        return self.effective_goal <= 1e-9


def next_goal_state(
    prior_banked_surplus: float,
    prior_period_profit_units: float,
    goal_units: float,
    min_risk_multiplier: float = 0.4,
) -> GoalState:
    """Advance the recurrence by one period (typically one day).

    banked_surplus_t  = max(banked_surplus_{t-1} + (profit_{t-1} - goal), 0)
    effective_goal_t  = max(goal - banked_surplus_t, 0)
    progress_fraction = 1 - effective_goal_t / goal
    risk_multiplier   = 1 - progress_fraction * (1 - min_risk_multiplier)

    The floor at 0 on ``banked_surplus`` is the load-bearing line: a period
    that misses the goal contributes a negative term that gets clamped away
    rather than carried forward as debt. Debt that justified betting bigger
    to "catch up" is exactly the martingale pattern this is built to avoid.
    """
    if goal_units <= 0:
        raise ValueError("goal_units must be positive")
    if not 0.0 <= min_risk_multiplier <= 1.0:
        raise ValueError("min_risk_multiplier must be in [0, 1]")

    banked_surplus = max(prior_banked_surplus + (prior_period_profit_units - goal_units), 0.0)
    effective_goal = max(goal_units - banked_surplus, 0.0)
    progress_fraction = 1.0 - (effective_goal / goal_units)
    risk_multiplier = 1.0 - progress_fraction * (1.0 - min_risk_multiplier)

    return GoalState(
        banked_surplus=banked_surplus,
        effective_goal=effective_goal,
        progress_fraction=progress_fraction,
        risk_multiplier=risk_multiplier,
    )


def state_from_history(
    daily_profit_units: dict, goal_units: float, min_risk_multiplier: float = 0.4
) -> GoalState:
    """Replay the recurrence across a history of completed days.

    Deliberately stateless rather than reading a saved "yesterday's banked
    surplus" from disk: folding over the full settled history on every run
    means the number in front of a bettor is always reproducible from the
    ledger alone, with no separate state file that could drift out of sync
    with it. ``daily_profit_units`` need only cover *settled* days --
    today's still-pending bets should not be in it, since the state
    returned here is what governs sizing for the day that has not
    settled yet.
    """
    banked_surplus = 0.0
    for day in sorted(daily_profit_units):
        state = next_goal_state(
            banked_surplus, daily_profit_units[day], goal_units, min_risk_multiplier
        )
        banked_surplus = state.banked_surplus

    effective_goal = max(goal_units - banked_surplus, 0.0)
    progress_fraction = 1.0 - (effective_goal / goal_units)
    risk_multiplier = 1.0 - progress_fraction * (1.0 - min_risk_multiplier)
    return GoalState(
        banked_surplus=banked_surplus,
        effective_goal=effective_goal,
        progress_fraction=progress_fraction,
        risk_multiplier=risk_multiplier,
    )


# ---------------------------------------------------------------------------
# Target-seeking: the other direction
# ---------------------------------------------------------------------------
#
# next_goal_state / state_from_history answer "how much should sizing shrink
# after a day that beat the goal." This answers the complementary question a
# bettor asks on an ordinary day: "what sizing would it take to actually be
# on pace for the goal today?"
#
# The two compose rather than compete. Risk reduction only ever pulls
# effective_goal down (never below zero) or shrinks a risk_multiplier toward
# min_risk_multiplier -- it never raises exposure above what was configured.
# Target-seeking is the mirror image and is bounded the same way in reverse:
# it only ever scales exposure *up* from the configured baseline (1.0x),
# never down, and only up to an explicit ceiling (max_scale) the caller
# controls. A day already on pace to clear the goal at baseline sizing is
# left alone -- there is no reason to shrink stakes just to land exactly on
# a round number once the model has already found more edge than that.


@dataclass(frozen=True)
class TargetSeekResult:
    """Result of searching for the exposure scale that targets a daily profit."""

    scale: float                   # multiplier on the configured exposure caps, >= 1.0
    achieved: bool                 # whether target_profit_units was reachable within max_scale
    expected_profit_units: float   # what the found scale actually projects today
    target_profit_units: float
    note: str


def solve_exposure_scale_for_target(
    expected_profit_at_scale: Callable[[float], float],
    target_profit_units: float,
    max_scale: float = 1.5,
    tol: float = 0.01,
    max_iterations: int = 25,
) -> TargetSeekResult:
    """Binary-search the smallest exposure scale (>= 1.0) that hits a target.

    ``expected_profit_at_scale(scale)`` re-stakes the same already-screened
    slate with every exposure cap (total, per-bet, per-game, per-book)
    multiplied by ``scale`` and returns the resulting expected profit in
    units -- in practice, ``pipeline.stake`` re-run against a scaled
    ``config.portfolio``. This function knows nothing about bets, bankrolls,
    or dollars; it only assumes the callback is monotonically
    non-decreasing in ``scale``, which holds here because relaxing an
    exposure cap only ever enlarges the feasible set the portfolio
    optimizer searches, and nothing that clears the EV screen is ever -EV,
    so more room to size a slate never lowers its expected profit.

    ``max_scale`` is the actual safety rail here, not an implementation
    detail: it is the most the configured exposure caps are ever allowed to
    be multiplied by in pursuit of the goal, however far short that leaves
    the target. This function has no opinion on what it should be --
    doubling every exposure cap roughly quadruples the depth of a bad run
    (see risk/bankroll.py), so the default is deliberately closer to 1 than
    to 2. A caller that never wants to bet more than its own configured
    caps, full stop, should pass ``max_scale=1.0`` and treat ``achieved``
    as informational only.
    """
    if target_profit_units <= 0:
        raise ValueError("target_profit_units must be positive")
    if max_scale < 1.0:
        raise ValueError("max_scale must be at least 1.0 -- this only ever scales up")

    profit_at_baseline = expected_profit_at_scale(1.0)
    if profit_at_baseline >= target_profit_units:
        return TargetSeekResult(
            scale=1.0,
            achieved=True,
            expected_profit_units=profit_at_baseline,
            target_profit_units=target_profit_units,
            note="today's configured sizing already clears the goal -- no scale-up needed",
        )

    lo, hi = 1.0, max_scale
    profit_at_hi = expected_profit_at_scale(hi)
    if profit_at_hi < target_profit_units:
        return TargetSeekResult(
            scale=hi,
            achieved=False,
            expected_profit_units=profit_at_hi,
            target_profit_units=target_profit_units,
            note=(
                f"today's screened edges support at most {profit_at_hi:.2f}u of "
                f"expected profit even at {hi:g}x the configured exposure caps -- "
                f"short of the {target_profit_units:.2f}u goal. There are not enough "
                "(or strong enough) +EV bets today; this is not a sizing problem, "
                "and pushing exposure further would not fix it."
            ),
        )

    for _ in range(max_iterations):
        mid = 0.5 * (lo + hi)
        profit = expected_profit_at_scale(mid)
        if profit < target_profit_units:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break

    achieved_profit = expected_profit_at_scale(hi)
    return TargetSeekResult(
        scale=hi,
        achieved=True,
        expected_profit_units=achieved_profit,
        target_profit_units=target_profit_units,
        note=f"scaled exposure to {hi:.2f}x the configured caps to target {target_profit_units:.2f}u/day",
    )
