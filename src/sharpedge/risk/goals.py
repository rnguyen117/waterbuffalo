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
