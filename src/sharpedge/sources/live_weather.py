"""Live weather from the National Weather Service.

NWS (api.weather.gov) is free, keyless, and official -- a real government
forecast rather than a scraped or rate-limited third party. Its coverage is
US-only, which is a fine trade for this package: weather only matters for
outdoor NFL games, and the NFL is entirely US venues. NHL, being indoor,
never needed this in the first place.

The lookup is two calls: coordinates -> grid point (which forecast office
and grid cell covers that location), then grid point -> hourly forecast.
The grid point rarely changes for a fixed venue, but is not cached across
runs here for simplicity -- it is a cheap call and NWS asks only for a
descriptive User-Agent, no key, no quota to manage.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import WeatherReport
from .base import SourceError

BASE_URL = "https://api.weather.gov"

# A descriptive User-Agent is NWS's only access requirement -- no key.
_USER_AGENT = "sharp-edge (https://github.com/rnguyen117/waterbuffalo)"

# All 32 NFL stadiums: (latitude, longitude, is_dome). "Dome" here means
# fully enclosed or a fixed/usually-closed retractable roof -- the outcome
# that matters is "the model should not price weather into this game,"
# not architectural precision about which roofs technically open.
NFL_VENUES: dict[str, tuple[float, float, bool]] = {
    "Buffalo Bills": (42.7738, -78.7870, False),
    "Miami Dolphins": (25.9580, -80.2389, False),
    "New England Patriots": (42.0909, -71.2643, False),
    "New York Jets": (40.8135, -74.0745, False),
    "New York Giants": (40.8135, -74.0745, False),
    "Baltimore Ravens": (39.2780, -76.6227, False),
    "Cincinnati Bengals": (39.0955, -84.5160, False),
    "Cleveland Browns": (41.5061, -81.6995, False),
    "Pittsburgh Steelers": (40.4468, -80.0158, False),
    "Houston Texans": (29.6847, -95.4107, True),
    "Indianapolis Colts": (39.7601, -86.1639, True),
    "Jacksonville Jaguars": (30.3239, -81.6373, False),
    "Tennessee Titans": (36.1665, -86.7713, False),
    "Denver Broncos": (39.7439, -105.0201, False),
    "Kansas City Chiefs": (39.0489, -94.4839, False),
    "Las Vegas Raiders": (36.0909, -115.1833, True),
    "Los Angeles Chargers": (33.9535, -118.3392, True),
    "Los Angeles Rams": (33.9535, -118.3392, True),
    "Dallas Cowboys": (32.7473, -97.0945, True),
    "Philadelphia Eagles": (39.9008, -75.1675, False),
    "Washington Commanders": (38.9078, -76.8645, False),
    "Chicago Bears": (41.8623, -87.6167, False),
    "Detroit Lions": (42.3400, -83.0456, True),
    "Green Bay Packers": (44.5013, -88.0622, False),
    "Minnesota Vikings": (44.9737, -93.2577, True),
    "Atlanta Falcons": (33.7554, -84.4009, True),
    "Carolina Panthers": (35.2258, -80.8528, False),
    "New Orleans Saints": (29.9511, -90.0812, True),
    "Tampa Bay Buccaneers": (27.9759, -82.5033, False),
    "Arizona Cardinals": (33.5276, -112.2626, True),
    "San Francisco 49ers": (37.4030, -121.9700, False),
    "Seattle Seahawks": (47.5952, -122.3316, False),
}


class NWSWeatherSource:
    """Forecast conditions for outdoor NFL games, from api.weather.gov."""

    name = "nws"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def fetch_weather(self, events: list) -> dict[str, WeatherReport]:
        """One WeatherReport per NFL event with a known venue, keyed by event_id.

        Events for sports other than NFL, or NFL venues not in
        ``NFL_VENUES`` (there should not be any -- all 32 are listed), are
        silently skipped, matching how the demo source only ever reports
        weather for NFL to begin with.
        """
        out: dict[str, WeatherReport] = {}
        for event in events:
            if getattr(event, "sport", "").lower() != "nfl":
                continue
            venue = NFL_VENUES.get(event.home_team)
            if venue is None:
                continue
            lat, lon, dome = venue
            if dome:
                out[event.event_id] = WeatherReport(
                    event_id=event.event_id,
                    wind_mph=0.0,
                    temperature_f=70.0,
                    precipitation_chance=0.0,
                    dome=True,
                    description="dome",
                )
                continue
            try:
                report = self._forecast_at(lat, lon, event.event_id, event.start_time)
            except SourceError:
                continue
            if report is not None:
                out[event.event_id] = report
        return out

    def _forecast_at(
        self, lat: float, lon: float, event_id: str, when: datetime
    ) -> WeatherReport | None:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise SourceError(
                "live weather needs `requests` installed: pip install requests"
            ) from exc

        headers = {"User-Agent": _USER_AGENT}
        try:
            point = requests.get(
                f"{BASE_URL}/points/{lat:.4f},{lon:.4f}", headers=headers, timeout=self.timeout
            )
        except Exception as exc:
            raise SourceError(f"NWS point lookup failed: {exc}") from exc
        if point.status_code >= 400:
            raise SourceError(f"NWS point lookup returned {point.status_code}")

        forecast_url = point.json().get("properties", {}).get("forecastHourly")
        if not forecast_url:
            return None

        try:
            fc = requests.get(forecast_url, headers=headers, timeout=self.timeout)
        except Exception as exc:
            raise SourceError(f"NWS forecast fetch failed: {exc}") from exc
        if fc.status_code >= 400:
            raise SourceError(f"NWS forecast fetch returned {fc.status_code}")

        periods = fc.json().get("properties", {}).get("periods", [])
        period = _closest_period(periods, when)
        if period is None:
            # Beyond NWS's ~7-day hourly horizon -- nothing to report yet,
            # not an error. The caller re-fetches closer to kickoff.
            return None

        precip = period.get("probabilityOfPrecipitation", {}) or {}
        wind = _parse_wind_mph(period.get("windSpeed", ""))
        return WeatherReport(
            event_id=event_id,
            wind_mph=wind,
            temperature_f=float(period.get("temperature", 60.0)),
            precipitation_chance=(precip.get("value") or 0) / 100.0,
            dome=False,
            description=period.get("shortForecast", ""),
        )


# NWS's hourly endpoint only covers about a week out. A "closest available"
# match with no ceiling would silently hand back today's weather mislabeled
# as a forecast for a game a month away -- worse than reporting nothing.
_MAX_FORECAST_GAP_SECONDS = 8 * 24 * 3600


def _closest_period(periods: list[dict], when: datetime) -> dict | None:
    """The hourly period whose start time is nearest kickoff, within the forecast horizon."""
    if not periods:
        return None
    target = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    best, best_gap = None, None
    for period in periods:
        start = period.get("startTime")
        if not start:
            continue
        try:
            period_time = datetime.fromisoformat(start)
        except ValueError:
            continue
        gap = abs((period_time - target).total_seconds())
        if best_gap is None or gap < best_gap:
            best, best_gap = period, gap
    if best_gap is None or best_gap > _MAX_FORECAST_GAP_SECONDS:
        return None
    return best


def _parse_wind_mph(text: str) -> float:
    """NWS reports wind as e.g. "10 mph" or "10 to 15 mph" -- take the high end."""
    digits = [int(tok) for tok in text.replace("mph", "").split() if tok.isdigit()]
    return float(max(digits)) if digits else 0.0
