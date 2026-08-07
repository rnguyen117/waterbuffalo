"""Live injury reports from ESPN's public site API.

There is no official, documented, free injury-data API for any of these
leagues -- real-time injury feeds are normally a paid product (SportsDataIO,
Sportradar, and similar). ESPN's site API (site.api.espn.com) is what its
own website and apps run on; it is not published as a public product, is
not versioned, and could change or disappear without notice. That is a real
operational risk, stated plainly rather than glossed over: this is the best
free option available, not a guaranteed-stable one. If it starts returning
errors or empty data, that is this endpoint changing shape, not a bug in
the parsing below to chase blindly.

Point values are the same kind of estimate the rest of this package is
built on -- positional defaults, not per-player fitted values (see
signals/injuries.py and models.py's own note that this is not a fitted
parameter). A generic "starting QB out" is worth far more than a generic
"starting cornerback out," and the position tables below encode that
ordering without pretending to know a specific player's individual value.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import InjuryReport, InjuryStatus
from .base import SourceError

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"

# ESPN's sport/league path per internal sport key.
ESPN_LEAGUE_PATHS: dict[str, str] = {
    "nfl": "football/nfl",
    "nba": "basketball/nba",
    "wnba": "basketball/wnba",
    "mlb": "baseball/mlb",
    "nhl": "hockey/nhl",
}

# ESPN's status strings, mapped onto this package's InjuryStatus. Statuses
# seen in practice vary by sport and are not documented anywhere, so this
# defaults anything unrecognized to QUESTIONABLE (see _status_for) rather
# than silently treating an unknown status as "fine to start."
ESPN_STATUS_MAP: dict[str, InjuryStatus] = {
    "out": InjuryStatus.OUT,
    "injured reserve": InjuryStatus.OUT,
    "ir": InjuryStatus.OUT,
    "doubtful": InjuryStatus.DOUBTFUL,
    "questionable": InjuryStatus.QUESTIONABLE,
    "day-to-day": InjuryStatus.QUESTIONABLE,
    "probable": InjuryStatus.PROBABLE,
    "game-time decision": InjuryStatus.GAME_TIME_DECISION,
    "active": InjuryStatus.ACTIVE,
    "suspension": InjuryStatus.OUT,
}

# Rough positional point value: how many points a team's line moves without
# a starter at that position, same spirit as demo.py's simplified categories
# but with real position abbreviations instead of "STAR"/"STARTER" stand-ins.
# Consensus estimates, not fitted parameters -- see models.py's own caveat
# on InjuryReport.point_value.
POSITION_POINT_VALUE: dict[str, dict[str, float]] = {
    "nfl": {
        "QB": 6.0, "RB": 1.0, "WR": 1.3, "TE": 0.7,
        "T": 1.0, "G": 0.8, "C": 0.8, "OL": 1.0,
        "DE": 1.2, "DT": 0.9, "EDGE": 1.2, "LB": 0.8,
        "CB": 1.0, "S": 0.8, "SS": 0.8, "FS": 0.8,
        "K": 0.3, "P": 0.2,
    },
    "nba": {
        "PG": 2.0, "SG": 1.6, "SF": 1.6, "PF": 1.4, "C": 1.4,
    },
    "wnba": {
        "PG": 1.6, "SG": 1.3, "SF": 1.3, "PF": 1.1, "C": 1.1,
    },
    "mlb": {
        "SP": 1.0, "RP": 0.3, "P": 0.6,
        "C": 0.3, "1B": 0.3, "2B": 0.3, "3B": 0.3, "SS": 0.3,
        "OF": 0.3, "LF": 0.3, "CF": 0.3, "RF": 0.3, "DH": 0.25,
    },
    "nhl": {
        "G": 1.5, "D": 0.4, "C": 0.5, "LW": 0.5, "RW": 0.5, "F": 0.5,
    },
}


class ESPNInjurySource:
    """Injury reports for a sport's whole league, from ESPN's site API."""

    name = "espn"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def fetch_injuries(self, sports: list[str]) -> list[InjuryReport]:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise SourceError(
                "live injuries need `requests` installed: pip install requests"
            ) from exc

        out: list[InjuryReport] = []
        for sport in sports:
            path = ESPN_LEAGUE_PATHS.get(sport.lower())
            if path is None:
                continue
            try:
                response = requests.get(
                    f"{BASE_URL}/{path}/injuries", timeout=self.timeout
                )
                response.raise_for_status()
                data = response.json()
            except Exception:
                # One sport's feed being down must not take the others with
                # it -- this call runs once per sport, independently.
                continue
            out.extend(_parse_injuries(data, sport.lower()))
        return out


def _parse_injuries(data: dict, sport: str) -> list[InjuryReport]:
    positions = POSITION_POINT_VALUE.get(sport, {})
    out: list[InjuryReport] = []
    for team in data.get("injuries", []) or []:
        team_name = team.get("displayName", "")
        for entry in team.get("injuries", []) or []:
            athlete = entry.get("athlete") or {}
            player = athlete.get("displayName")
            if not player:
                continue
            status = _status_for(entry.get("status", ""))
            position_abbr = (athlete.get("position") or {}).get("abbreviation", "")
            point_value = positions.get(position_abbr, _default_point_value(sport))
            out.append(
                InjuryReport(
                    player=player,
                    team=team_name,
                    status=status,
                    position=position_abbr or None,
                    point_value=point_value,
                    reported_at=_parse_date(entry.get("date")),
                    note=entry.get("shortComment", "") or "",
                )
            )
    return out


def _status_for(raw: str) -> InjuryStatus:
    return ESPN_STATUS_MAP.get(raw.strip().lower(), InjuryStatus.QUESTIONABLE)


def _default_point_value(sport: str) -> float:
    # A position ESPN reports that is not in the table above -- conservative
    # rather than zero, since "unlisted" usually means a bench/depth player
    # whose absence still moves the number a little.
    return {"nfl": 0.5, "nba": 0.8, "wnba": 0.6, "mlb": 0.2, "nhl": 0.3}.get(sport, 0.3)


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)
