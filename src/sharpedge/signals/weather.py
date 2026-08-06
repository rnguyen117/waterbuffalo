"""Weather effects, which live almost entirely in totals.

One weather variable matters a lot and the rest barely register. Wind
suppresses scoring by degrading the passing and kicking games; below roughly
10 mph it does essentially nothing, and above 15 mph the effect grows fast.
Cold weather is mostly a myth as an independent factor once wind is
controlled for, and rain matters less than people expect because both offense
and defense are slowed.

The betting-relevant asymmetry: wind affects the *total* strongly and the
*side* only slightly. High wind compresses variance, which very mildly helps
the better team cover a small spread and hurts a large favorite covering a
big number, but the total is where the money is.
"""

from __future__ import annotations

from ..models import MarketType, SignalContribution
from .base import SignalContext, clamp


def wind_total_impact(wind_mph: float, sport: str = "nfl") -> float:
    """Points to subtract from a game total for wind.

    Piecewise because the relationship is genuinely nonlinear: nothing until
    about 10 mph, then accelerating. A 25 mph game is a different sport.
    """
    if sport.lower() not in ("nfl", "ncaaf"):
        return 0.0
    w = max(wind_mph, 0.0)
    if w < 10:
        return 0.0
    if w < 15:
        return 0.5 * (w - 10) / 5.0
    if w < 20:
        return 0.5 + 1.7 * (w - 15) / 5.0
    if w < 25:
        return 2.2 + 2.3 * (w - 20) / 5.0
    return min(4.5 + 0.35 * (w - 25), 9.0)


def temperature_impact(temp_f: float, sport: str = "nfl") -> float:
    """Points off a total for extreme cold, which is a small real effect."""
    if sport.lower() not in ("nfl", "ncaaf"):
        return 0.0
    if temp_f >= 32:
        return 0.0
    if temp_f >= 20:
        return 0.4
    if temp_f >= 10:
        return 0.9
    return 1.4


def precipitation_impact(chance: float, sport: str = "nfl") -> float:
    """Points off a total for rain or snow. Modest and often overbet."""
    if sport.lower() not in ("nfl", "ncaaf"):
        return 0.0
    return 0.9 * clamp(chance, 0.0, 1.0)


def mlb_wind_impact(wind_mph: float, blowing_out: bool) -> float:
    """Runs added or removed by wind at a baseball park.

    Direction is everything here. Wind blowing out at Wrigley is the single
    largest weather effect in baseball; the same speed blowing in suppresses
    scoring by a comparable amount.
    """
    if wind_mph < 8:
        return 0.0
    magnitude = min(0.09 * (wind_mph - 8), 1.1)
    return magnitude if blowing_out else -magnitude


class WeatherSignal:
    """Adjust totals for conditions the market may not have fully priced.

    Weather is priced well close to kickoff and poorly days out, when the
    forecast is uncertain and books post a number based on climate rather
    than conditions. The weight therefore rises as the forecast firms up but
    the *opportunity* falls, because books reprice too -- so the sweet spot is
    a confident forecast at a book that has not updated.
    """

    name = "weather"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        report = ctx.weather
        if report is None or report.dome:
            return []
        if ctx.market.market_type not in (MarketType.TOTAL, MarketType.ALTERNATE_TOTAL, MarketType.TEAM_TOTAL):
            return self._side_effect(ctx, report)

        sport = ctx.sport.lower()
        points = (
            wind_total_impact(report.wind_mph, sport)
            + temperature_impact(report.temperature_f, sport)
            + precipitation_impact(report.precipitation_chance, sport)
        )
        if points < 0.4:
            return []

        # Lower total favors the under. Convert a points effect on the total
        # into a probability shift using the total's own sigma.
        from ..oddsmath import sport_sigma

        sigma = sport_sigma(sport) * 1.15
        is_under = ctx.outcome.lower().startswith("under")
        direction = 1.0 if is_under else -1.0
        # Density-based conversion: near the line, each point of movement is
        # worth roughly pdf(0)/sigma of probability.
        per_point = 0.3989 / sigma
        delta_p = direction * points * per_point
        p = clamp(ctx.market_probability + delta_p, 1e-4, 1 - 1e-4)
        from ..oddsmath import logit

        adjustment = logit(p) - logit(ctx.market_probability)

        detail = []
        if report.wind_mph >= 10:
            detail.append(f"{report.wind_mph:.0f} mph wind")
        if report.temperature_f < 32:
            detail.append(f"{report.temperature_f:.0f}F")
        if report.precipitation_chance > 0.3:
            detail.append(f"{report.precipitation_chance:.0%} precip")

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=adjustment,
                weight=0.65,
                rationale=(
                    f"{', '.join(detail) or report.description}: "
                    f"worth about {points:.1f} points off the total"
                ),
                points=-points,
                source="weather forecast",
            )
        ]

    def _side_effect(
        self, ctx: SignalContext, report
    ) -> list[SignalContribution]:
        """High wind compresses scoring variance, which nudges sides slightly."""
        if report.wind_mph < 18 or ctx.sport.lower() not in ("nfl", "ncaaf"):
            return []
        if ctx.market.market_type != MarketType.SPREAD:
            return []
        line = ctx.current_line
        if line is None:
            return []
        # Fewer possessions means fewer chances for the better team to pull
        # away: big favorites cover large numbers less often in heavy wind.
        favorite = line < 0
        magnitude = min((report.wind_mph - 18) * 0.04, 0.35)
        if abs(line) < 3.5:
            return []
        direction = -1.0 if favorite else 1.0
        from ..oddsmath import logit

        p = clamp(ctx.market_probability + direction * magnitude * 0.04, 1e-4, 1 - 1e-4)
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=logit(p) - logit(ctx.market_probability),
                weight=0.35,
                rationale=(
                    f"{report.wind_mph:.0f} mph wind compresses scoring; large "
                    "spreads are harder to cover in these conditions"
                ),
                source="weather forecast",
            )
        ]
