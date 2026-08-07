"""Situational and scheduling spots.

These are the small, durable effects that come from the calendar rather than
from the teams: rest, travel, altitude, short weeks, and the emotional
hangover spots. Individually they are worth a fraction of a point. Their
value is that they are *measurable in advance*, they occasionally stack, and
retail books price several of them lazily.

Two honest caveats are built into the numbers below.

First, the effect sizes are small. Anyone quoting three points for a
"letdown spot" is selling something. The largest genuine situational effect
in this file is the NBA back-to-back with travel, and it is worth about a
point and a half.

Second, the market prices most of this already. That is what the weights are
for -- a factor the market has priced for twenty years gets a low weight even
when the effect itself is real.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..models import SignalContribution
from .base import SignalContext, clamp, points_to_logit


# ---------------------------------------------------------------------------
# Venue reference data
# ---------------------------------------------------------------------------

# Latitude/longitude by team, for travel distance and time-zone shifts.
# Populated for the venues where the effect is large enough to matter.
VENUE_COORDS: dict[str, tuple[float, float]] = {
    "Denver Nuggets": (39.749, -105.008),
    "Denver Broncos": (39.744, -105.020),
    "Utah Jazz": (40.768, -111.901),
    "Golden State Warriors": (37.768, -122.388),
    "Los Angeles Lakers": (34.043, -118.267),
    "Los Angeles Clippers": (34.043, -118.267),
    "Boston Celtics": (42.366, -71.062),
    "New York Knicks": (40.751, -73.994),
    "Miami Heat": (25.781, -80.187),
    "Seattle Seahawks": (47.595, -122.332),
    "Green Bay Packers": (44.501, -88.062),
    "Buffalo Bills": (42.774, -78.787),
    "Kansas City Chiefs": (39.049, -94.484),
    "Phoenix Suns": (33.446, -112.071),
    "Portland Trail Blazers": (45.532, -122.667),
}

# Venues with a real altitude effect. Visiting teams tire measurably, and the
# effect on totals is larger than the effect on sides.
ALTITUDE_VENUES: dict[str, float] = {
    "Denver Nuggets": 1.5,
    "Denver Broncos": 1.2,
    "Utah Jazz": 0.8,
    "Mexico City": 1.4,
}


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two coordinates, in miles."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 3958.8 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


class RestSignal:
    """Rest differential, back-to-backs, and short weeks.

    The NBA back-to-back is the strongest scheduling effect in American
    sports and it compounds with travel. The NFL short week (Thursday games)
    hurts the team that played a physical Sunday game and travels.

    Metadata read: ``rest_days`` mapping team to days off, ``back_to_back``
    mapping team to bool, ``third_in_four`` likewise.
    """

    name = "rest"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        team = ctx.team_for_outcome()
        if team is None:
            return []
        opponent = ctx.event.opponent_of(team)
        meta = ctx.event.metadata or {}
        rest = meta.get("rest_days", {})
        b2b = meta.get("back_to_back", {})
        third = meta.get("third_in_four", {})

        sport = ctx.sport.lower()
        points = 0.0
        reasons: list[str] = []

        own_rest = rest.get(team)
        opp_rest = rest.get(opponent) if opponent else None
        if own_rest is not None and opp_rest is not None:
            diff = own_rest - opp_rest
            per_day = {"nba": 0.35, "wnba": 0.30, "nhl": 0.25, "nfl": 0.55, "ncaab": 0.30}.get(sport, 0.25)
            capped = clamp(diff, -3, 3)
            if abs(capped) >= 1:
                points += capped * per_day
                reasons.append(f"{capped:+.0f} days rest vs opponent")

        if sport in ("nba", "wnba", "nhl"):
            b2b_value = {"nba": 1.1, "wnba": 0.9, "nhl": 0.35}.get(sport, 0.5)
            if b2b.get(team):
                points -= b2b_value
                reasons.append("on the second night of a back-to-back")
            if opponent and b2b.get(opponent):
                points += b2b_value
                reasons.append("opponent on a back-to-back")
            if third.get(team):
                points -= 0.6
                reasons.append("third game in four nights")
            if opponent and third.get(opponent):
                points += 0.6
                reasons.append("opponent playing third in four")

        if sport == "nfl":
            if meta.get("short_week", {}).get(team):
                points -= 0.8
                reasons.append("on a short week")
            if meta.get("off_bye", {}).get(team):
                points += 0.9
                reasons.append("coming off a bye")

        if abs(points) < 0.15:
            return []

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=points_to_logit(points, ctx.market_probability, ctx.sport),
                weight=0.55,  # heavily priced already; claim only part of it
                rationale="; ".join(reasons) + f" ({points:+.1f} pts)",
                points=points,
                source="schedule",
            )
        ]


class TravelSignal:
    """Distance, time-zone crossings, and altitude.

    The reliable pieces are west-to-east body-clock disadvantage for early
    kickoffs and altitude for visiting teams. Raw mileage on its own is
    nearly worthless once rest is controlled for, so it is weighted low here.
    """

    name = "travel"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        team = ctx.team_for_outcome()
        if team is None or ctx.event.neutral_site:
            return []

        is_home = ctx.is_home_outcome()
        points = 0.0
        reasons: list[str] = []
        home_team = ctx.event.home_team

        altitude = ALTITUDE_VENUES.get(home_team, 0.0)
        if altitude:
            if is_home:
                points += altitude * 0.5
                reasons.append(f"altitude advantage at {home_team}")
            else:
                points -= altitude * 0.5
                reasons.append(f"visiting {home_team} at altitude")

        away_team = ctx.event.away_team
        if away_team in VENUE_COORDS and home_team in VENUE_COORDS:
            miles = haversine_miles(VENUE_COORDS[away_team], VENUE_COORDS[home_team])
            if miles > 1800:
                penalty = 0.35 if miles > 2400 else 0.2
                points += penalty if is_home else -penalty
                reasons.append(f"{miles:.0f} mile road trip for {away_team}")

        meta = ctx.event.metadata or {}
        if meta.get("early_kickoff_west_coast") and not is_home:
            points += 0.6
            reasons.append("west coast team in an early eastern kickoff")

        if abs(points) < 0.15:
            return []

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=points_to_logit(points, ctx.market_probability, ctx.sport),
                weight=0.45,
                rationale="; ".join(reasons) + f" ({points:+.1f} pts)",
                points=points,
                source="schedule",
            )
        ]


class ScheduleSpotSignal:
    """Lookahead, letdown, and revenge spots.

    The weakest category in this file and the one most abused by touts.
    Lookahead spots -- a good team facing a weak opponent immediately before
    a marquee game -- have the most support in the data. Revenge narratives
    have close to none, so the signal reports them at near-zero weight rather
    than pretending otherwise.
    """

    name = "schedule_spot"

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        team = ctx.team_for_outcome()
        if team is None:
            return []
        meta = (ctx.event.metadata or {}).get("spots", {})
        own = meta.get(team, [])
        opp = meta.get(ctx.event.opponent_of(team) or "", [])
        if not own and not opp:
            return []

        # (points, weight) per spot type.
        table = {
            "lookahead": (-0.9, 0.5),
            "letdown": (-0.7, 0.4),
            "sandwich": (-0.8, 0.45),
            "revenge": (0.3, 0.10),
            "division_rematch": (0.0, 0.0),
            "emotional_win_prior": (-0.5, 0.3),
        }

        points = 0.0
        weight_num = 0.0
        weight_den = 0.0
        reasons: list[str] = []
        for spot in own:
            pts, w = table.get(spot, (0.0, 0.0))
            points += pts
            weight_num += w
            weight_den += 1
            if w > 0:
                reasons.append(f"{team} in a {spot.replace('_', ' ')} spot")
        for spot in opp:
            pts, w = table.get(spot, (0.0, 0.0))
            points -= pts
            weight_num += w
            weight_den += 1
            if w > 0:
                reasons.append(f"opponent in a {spot.replace('_', ' ')} spot")

        if abs(points) < 0.1 or weight_den == 0:
            return []

        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=points_to_logit(points, ctx.market_probability, ctx.sport),
                weight=clamp(weight_num / weight_den, 0.0, 0.6),
                rationale="; ".join(reasons) + f" ({points:+.1f} pts)",
                points=points,
                source="schedule",
            )
        ]


class HomeFieldSignal:
    """Sanity check on home advantage rather than an independent edge.

    Home field is the most thoroughly priced factor in existence, so this
    never contributes weight. It exists to catch a data error -- if the
    consensus implies a home edge wildly outside the sport's normal range,
    something is wrong with the feed and the run should say so rather than
    bet on it.
    """

    name = "home_field"

    NORMAL_RANGE: dict[str, tuple[float, float]] = {
        "nfl": (1.0, 3.0),
        "nba": (1.5, 3.5),
        "ncaaf": (1.5, 4.0),
        "ncaab": (2.5, 5.0),
        "nhl": (0.1, 0.35),
        "mlb": (0.1, 0.35),
        "npb": (0.1, 0.35),
    }

    def evaluate(self, ctx: SignalContext) -> list[SignalContribution]:
        if ctx.consensus_line is None or ctx.event.neutral_site:
            return []
        lo, hi = self.NORMAL_RANGE.get(ctx.sport.lower(), (0.0, 5.0))
        implied = (ctx.event.metadata or {}).get("implied_home_edge")
        if implied is None:
            return []
        if lo <= implied <= hi:
            return []
        return [
            SignalContribution(
                name=self.name,
                logit_adjustment=0.0,
                weight=0.0,
                rationale=(
                    f"implied home edge of {implied:.1f} pts is outside the normal "
                    f"{lo:.1f}-{hi:.1f} range for {ctx.sport.upper()} -- verify the feed"
                ),
                source="data check",
            )
        ]
