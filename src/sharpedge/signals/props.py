"""Signals specific to player props.

The single most valuable idea here is **usage redistribution**. When a team
loses a starter, the game's side moves within seconds because everyone is
watching it. The teammates' props move slowly, incompletely, or not at all --
and their true values have changed a lot. A point guard's absence does not
reduce his team's assists to zero; it hands them to whoever brings the ball up
next, and that player's assist prop is still priced for a world where he
doesn't.

The effect is large and mechanical rather than speculative. Basketball has
fixed minutes and a fixed number of shots; when a 30%-usage player sits, that
usage goes somewhere, and it goes disproportionately to the one or two players
who share his role.

The other signals here exploit structural facts books price crudely:

* **Blowout risk.** Starters sit in the fourth quarter of a 20-point game.
  Counting-stat overs are systematically hurt by large spreads, and books
  price props off season averages that include close games.
* **Pace.** Possessions are the denominator of every counting stat. A game
  projected 8 possessions above average lifts every prop in it.
* **Umpire and park.** Strike-zone size measurably moves strikeout props, and
  park factors move baseball counting stats. Both are known days in advance.
* **Pitch and workload limits.** A pitcher on an innings limit cannot reach
  the tail of his strikeout distribution no matter how well he pitches, which
  makes his alternate overs worthless and his unders undervalued.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import InjuryStatus, MarketType, SignalContribution
from ..oddsmath import expit, logit
from .base import SignalContext, clamp, recency_credit

# ---------------------------------------------------------------------------
# Usage redistribution
# ---------------------------------------------------------------------------

# When a player is out, the share of his usage that flows to a teammate in
# the same role. Position-mates absorb far more than the roster at large.
USAGE_TRANSFER: dict[str, dict[str, float]] = {
    "nba": {
        "same_position": 0.42,
        "same_unit": 0.22,
        "team_wide": 0.11,
    },
    "wnba": {
        # 12-player rosters against the NBA's 15 mean a star's absence has
        # fewer bodies to redistribute to, so what remains concentrates
        # harder on the players who share her role.
        "same_position": 0.48,
        "same_unit": 0.24,
        "team_wide": 0.12,
    },
    "nfl": {
        "same_position": 0.55,   # a WR2 absorbing WR1 targets
        "same_unit": 0.18,
        "team_wide": 0.06,
    },
    "nhl": {
        "same_position": 0.30,
        "same_unit": 0.16,
        "team_wide": 0.05,
    },
    "mlb": {
        # Baseball lineups are fixed, so absences move counting stats far less.
        "same_position": 0.10,
        "same_unit": 0.05,
        "team_wide": 0.02,
    },
}

# How responsive each stat is to a teammate's absence. Assists move most
# because playmaking concentrates; blocks and steals barely move at all.
STAT_USAGE_SENSITIVITY: dict[str, float] = {
    "assists": 1.30,
    "points": 1.00,
    "pra": 1.05,
    "threes_made": 0.95,
    "rebounds": 0.70,
    "turnovers": 0.85,
    "steals": 0.35,
    "blocks": 0.30,
    "receptions": 1.25,
    "receiving_yards": 1.20,
    "rush_attempts": 1.15,
    "rushing_yards": 1.10,
    "pass_attempts": 0.45,
    "passing_yards": 0.40,
    "shots_on_goal": 0.85,
    "player_points": 1.00,
    "total_bases": 0.20,
    "hits": 0.15,
    "strikeouts": 0.05,
}


class UsageRedistributionSignal:
    """Reprice a prop when a teammate is out and his usage moves.

    Reads ``ctx.event.metadata['depth_chart']``, a mapping of team to
    ``{player: {"position": str, "usage": float}}``. Without a depth chart the
    signal correctly does nothing rather than guessing.
    """

    name = "usage_redistribution"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        if not ctx.market.market_type.is_prop or not ctx.market.subject:
            return []
        stat = ctx.market.stat
        if not stat:
            return []

        player = ctx.market.subject
        depth = (ctx.event.metadata or {}).get("depth_chart", {})
        team = _team_of_player(depth, player)
        if team is None:
            return []

        roster = depth.get(team, {})
        me = roster.get(player, {})
        my_position = me.get("position")

        out_players = [
            inj
            for inj in ctx.injuries
            if inj.team == team
            and inj.player != player
            and inj.status in (InjuryStatus.OUT, InjuryStatus.DOUBTFUL)
        ]
        if not out_players:
            return []

        transfer = USAGE_TRANSFER.get(ctx.sport.lower(), USAGE_TRANSFER["nba"])
        sensitivity = STAT_USAGE_SENSITIVITY.get(stat, 0.6)

        gained_usage = 0.0
        reasons: list[str] = []
        for inj in out_players:
            info = roster.get(inj.player, {})
            usage = info.get("usage", 0.0)
            if usage <= 0:
                continue
            position = info.get("position")
            if my_position and position == my_position:
                rate = transfer["same_position"]
                how = "same position"
            elif position:
                rate = transfer["same_unit"]
                how = "same unit"
            else:
                rate = transfer["team_wide"]
                how = "team-wide"
            share = usage * rate * (1.0 - inj.play_probability)
            if share < 0.005:
                continue
            gained_usage += share
            reasons.append(
                f"{inj.player} ({inj.status.value}, {usage:.0%} usage) -- "
                f"{how}, about {share:.1%} flows here"
            )

        if gained_usage < 0.01:
            return []

        # Usage translates to production close to proportionally, damped
        # because efficiency falls as a player's role expands.
        production_lift = gained_usage * sensitivity * 0.82

        # The over becomes more likely; the under less.
        is_over = ctx.outcome.lower().startswith("over")
        direction = 1.0 if is_over else -1.0
        adjustment = direction * production_lift * 2.2

        # If the prop's own line already moved, part of this is priced.
        already_moved = 0.0
        if ctx.opening_line is not None and ctx.current_line is not None:
            already_moved = ctx.current_line - ctx.opening_line
        credit = 1.0
        if abs(already_moved) > 0.4:
            credit = 0.35
            reasons.append(
                f"the prop line has already moved {already_moved:+.1f}, so most of "
                "this is priced"
            )

        newest = max((i.reported_at for i in out_players), default=ctx.now)
        weight = clamp(0.85 * credit * recency_credit(newest, ctx.now, 240.0), 0.0, 0.85)

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=weight,
                rationale=(
                    f"{player} gains roughly {gained_usage:.1%} usage: "
                    + "; ".join(reasons[:2])
                ),
                source="depth chart + injury report",
                observed_at=newest,
            )
        ]


def _team_of_player(depth: dict, player: str) -> str | None:
    for team, roster in depth.items():
        if player in roster:
            return team
    return None


# ---------------------------------------------------------------------------
# Blowout risk
# ---------------------------------------------------------------------------


class BlowoutRiskSignal:
    """Large spreads suppress counting-stat overs.

    Starters sit late in decided games, and books price props off season
    averages that include close ones. The effect runs both ways and is not
    symmetric: a heavy favorite's stars get pulled, while a heavy underdog's
    pass-catchers often see *more* volume because the team throws to catch up.
    """

    name = "blowout_risk"

    # Stats hurt by garbage time (playing time), versus helped by trailing.
    MINUTES_DEPENDENT = {
        "points", "rebounds", "assists", "pra", "threes_made", "steals",
        "blocks", "turnovers", "shots_on_goal",
    }
    TRAILING_BOOSTED = {"pass_attempts", "passing_yards", "receptions", "receiving_yards"}
    LEADING_BOOSTED = {"rush_attempts", "rushing_yards"}

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        if not ctx.market.market_type.is_prop or not ctx.market.subject:
            return []
        stat = ctx.market.stat
        if not stat:
            return []

        spread = (ctx.event.metadata or {}).get("player_team_spread", {}).get(
            ctx.market.subject
        )
        if spread is None:
            return []

        magnitude = abs(spread)
        if magnitude < 9.0:
            return []

        favored = spread < 0
        severity = min((magnitude - 9.0) / 12.0, 1.0)
        effect = 0.0
        why = ""

        if stat in self.MINUTES_DEPENDENT and favored:
            effect = -0.16 * severity
            why = f"favored by {magnitude:.0f}; starters often sit late in a decided game"
        elif stat in self.TRAILING_BOOSTED and not favored:
            effect = 0.14 * severity
            why = f"{magnitude:.0f}-point underdog; trailing teams throw more"
        elif stat in self.TRAILING_BOOSTED and favored:
            effect = -0.12 * severity
            why = f"favored by {magnitude:.0f}; leading teams stop throwing"
        elif stat in self.LEADING_BOOSTED and favored:
            effect = 0.13 * severity
            why = f"favored by {magnitude:.0f}; leading teams run out the clock"
        elif stat in self.LEADING_BOOSTED and not favored:
            effect = -0.14 * severity
            why = f"{magnitude:.0f}-point underdog; trailing teams abandon the run"

        if effect == 0.0:
            return []

        is_over = ctx.outcome.lower().startswith("over")
        adjustment = effect if is_over else -effect

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=0.55,
                rationale=why,
                source="game script",
            )
        ]


# ---------------------------------------------------------------------------
# Pace
# ---------------------------------------------------------------------------


class PaceSignal:
    """Possessions are the denominator of every counting stat.

    Reads ``metadata['projected_pace']`` (possessions per game) against
    ``metadata['league_pace']``. A fast game lifts every counting prop in it,
    and books price the game total for pace far more carefully than they
    price the individual props.
    """

    name = "pace"

    PACE_SENSITIVE = {
        "points", "rebounds", "assists", "pra", "threes_made", "steals",
        "blocks", "turnovers", "shots_on_goal", "saves",
    }

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        if not ctx.market.market_type.is_prop:
            return []
        stat = ctx.market.stat
        if stat not in self.PACE_SENSITIVE:
            return []

        meta = ctx.event.metadata or {}
        projected = meta.get("projected_pace")
        baseline = meta.get("league_pace")
        if projected is None or baseline is None or baseline <= 0:
            return []

        ratio = projected / baseline
        if abs(ratio - 1.0) < 0.02:
            return []

        # Production scales close to linearly with possessions.
        lift = (ratio - 1.0) * 0.9
        is_over = ctx.outcome.lower().startswith("over")
        adjustment = (lift if is_over else -lift) * 2.0

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=0.50,
                rationale=(
                    f"projected pace {projected:.1f} vs league {baseline:.1f} "
                    f"({ratio - 1:+.1%} possessions)"
                ),
                source="pace projection",
            )
        ]


# ---------------------------------------------------------------------------
# Baseball specifics
# ---------------------------------------------------------------------------

# Umpires vary measurably in strike-zone size, and it moves strikeout props.
# Values are the multiplier on a pitcher's expected strikeouts.
UMPIRE_K_FACTOR_DEFAULT = 1.0


class UmpireSignal:
    """Home plate umpire strike-zone size, which moves strikeout props.

    Reads ``metadata['umpire_k_factor']``. The spread between the most
    pitcher-friendly and most hitter-friendly umpires is worth roughly half a
    strikeout on a starter, which is a meaningful fraction of a 6.5 line. It
    is known the morning of the game and many books never adjust for it.
    """

    name = "umpire"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        if ctx.market.stat not in ("strikeouts", "walks_allowed"):
            return []
        factor = (ctx.event.metadata or {}).get("umpire_k_factor")
        if factor is None or abs(factor - 1.0) < 0.02:
            return []

        lift = (factor - 1.0) * 0.85
        is_over = ctx.outcome.lower().startswith("over")
        adjustment = (lift if is_over else -lift) * 2.4

        direction = "expands" if factor > 1 else "shrinks"
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=0.45,
                rationale=(
                    f"home plate umpire {direction} the zone "
                    f"({factor:.2f}x strikeout rate)"
                ),
                source="umpire assignment",
            )
        ]


class ParkFactorSignal:
    """Ballpark run environment, for baseball counting props."""

    name = "park_factor"

    HITTER_STATS = {"total_bases", "hits", "home_runs", "rbis", "runs_scored"}
    PITCHER_STATS = {"earned_runs", "hits_allowed"}

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        stat = ctx.market.stat
        if stat not in (self.HITTER_STATS | self.PITCHER_STATS):
            return []
        factor = (ctx.event.metadata or {}).get("park_factor")
        if factor is None or abs(factor - 1.0) < 0.03:
            return []

        lift = (factor - 1.0) * 0.7
        is_over = ctx.outcome.lower().startswith("over")
        adjustment = (lift if is_over else -lift) * 2.0

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=0.40,
                rationale=(
                    f"park plays {'hitter' if factor > 1 else 'pitcher'}-friendly "
                    f"({factor:.2f}x run environment)"
                ),
                source="park factors",
            )
        ]


class WorkloadLimitSignal:
    """A pitcher on a leash cannot reach the tail of his distribution.

    Reads ``metadata['expected_pitch_limit']`` and
    ``metadata['expected_innings']``. This is the clearest case in the package
    of a hard physical cap the market prices lazily: a pitcher who will not
    throw past the fifth inning has essentially no path to nine strikeouts,
    yet his alternate overs are priced off an unconstrained distribution.
    """

    name = "workload_limit"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        if ctx.market.stat not in ("strikeouts", "outs_recorded", "hits_allowed"):
            return []
        meta = ctx.event.metadata or {}
        innings = meta.get("expected_innings")
        if innings is None:
            return []

        # A normal start is around 5.7 innings.
        if innings >= 5.4:
            return []

        shortfall = 5.7 - innings
        lift = -0.13 * shortfall
        is_over = ctx.outcome.lower().startswith("over")
        adjustment = (lift if is_over else -lift) * 2.0

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=0.70,
                rationale=(
                    f"expected only {innings:.1f} innings -- a short leash caps the "
                    "upside on counting stats"
                ),
                source="workload report",
            )
        ]


# ---------------------------------------------------------------------------
# Public shading on props
# ---------------------------------------------------------------------------


class PropPublicBiasSignal:
    """Price in the public's structural preference for prop overs.

    The largest and most consistent public-money effect available, because
    prop markets receive almost no sharp correction. Roughly 88% of anytime-
    touchdown tickets are on the over; books know it and price it, and the
    resulting premium is still there at settlement.
    """

    name = "prop_public_bias"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        if not ctx.market.market_type.is_prop:
            return []
        stat = ctx.market.stat
        if not stat:
            return []

        from ..market.public import _over_share
        from ..market.props import over_shading

        magnitude = over_shading(stat)
        if magnitude < 0.01:
            return []

        is_over = ctx.outcome.lower().startswith("over")
        # The shaded side is worse to bet; the other side is where the honest
        # price is.
        adjustment = -magnitude if is_over else magnitude * 0.55

        share = _over_share(stat)
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=0.60,
                rationale=(
                    f"about {share:.0%} of tickets on {stat.replace('_', ' ')} take the "
                    f"over; the {'over carries a public premium' if is_over else 'under is the unshaded side'}"
                ),
                source="prop ticket splits",
            )
        ]


class LadderConsistencySignal:
    """Flag an alternate line that disagrees with its own anchor.

    Carries no directional adjustment itself -- the ladder analysis in
    ``market.props`` computes the actual price. This surfaces the reasoning in
    the report and marks the bet as one whose premise is verifiable rather
    than predictive.
    """

    name = "ladder_consistency"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        mispricing = (ctx.event.metadata or {}).get("ladder_mispricing", {}).get(
            (ctx.market.subject, ctx.outcome, ctx.bet_line)
        )
        if not mispricing:
            return []
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=0.0,
                weight=0.0,
                rationale=mispricing,
                source="ladder fit",
            )
        ]
