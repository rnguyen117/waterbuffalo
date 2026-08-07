"""Tests for the live data sources added to answer 'is this real data'.

No network calls: requests.get is mocked with realistic response shapes
captured from real API responses during development, so these exercise the
actual parsing logic without depending on network access or live quota.
Skipped entirely if `requests` isn't installed, since it's an optional
"live" dependency (pyproject.toml's [live] extra), not a core one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

requests = pytest.importorskip("requests")

from sharpedge.market.taxonomy import PROPS_BY_STAT
from sharpedge.models import InjuryStatus
from sharpedge.sources.live_injuries import (
    ESPN_STATUS_MAP,
    ESPNInjurySource,
    POSITION_POINT_VALUE,
    _parse_injuries,
    _status_for,
)
from sharpedge.sources.live_weather import (
    NFL_VENUES,
    NWSWeatherSource,
    _closest_period,
    _parse_wind_mph,
)
from sharpedge.sources.base import SourceError
from sharpedge.sources.theoddsapi import PROP_MARKET_KEYS, TheOddsAPISource, _attach_prop_markets
from sharpedge.models import Event


class TestPropMarketKeys:
    def test_every_mapped_stat_has_a_taxonomy_profile(self):
        # A prop market key mapped to a stat name with no PropProfile would
        # silently fall back to unprofiled/conservative pricing -- this
        # catches that mismatch (a typo, a stat renamed in taxonomy.py and
        # not here) at test time instead of at 2am against a real card.
        for sport, keymap in PROP_MARKET_KEYS.items():
            for market_key, stat in keymap.items():
                assert stat in PROPS_BY_STAT, (
                    f"{sport}/{market_key} maps to stat {stat!r}, which has "
                    "no PropProfile in market/taxonomy.py"
                )


class TestAttachPropMarkets:
    def _event(self):
        return Event(
            event_id="evt-1",
            sport="mlb",
            league="MLB",
            home_team="Pittsburgh Pirates",
            away_team="New York Mets",
            start_time=datetime.now(timezone.utc) + timedelta(hours=6),
        )

    def _raw_response(self):
        # Shape captured from a real pitcher_strikeouts response.
        return {
            "bookmakers": [
                {
                    "key": "fanduel",
                    "last_update": "2026-08-07T06:18:34Z",
                    "markets": [
                        {
                            "key": "pitcher_strikeouts",
                            "outcomes": [
                                {"name": "Over", "description": "Zach Thornton", "price": 110, "point": 4.5},
                                {"name": "Under", "description": "Zach Thornton", "price": -140, "point": 4.5},
                                {"name": "Over", "description": "Carmen Mlodzinski", "price": 128, "point": 3.5},
                                {"name": "Under", "description": "Carmen Mlodzinski", "price": -164, "point": 3.5},
                            ],
                        }
                    ],
                },
                {
                    "key": "draftkings",
                    "last_update": "2026-08-07T06:18:15Z",
                    "markets": [
                        {
                            "key": "pitcher_strikeouts",
                            "outcomes": [
                                {"name": "Over", "description": "Zach Thornton", "price": 101, "point": 4.5},
                                {"name": "Under", "description": "Zach Thornton", "price": -129, "point": 4.5},
                            ],
                        }
                    ],
                },
            ]
        }

    def test_creates_one_market_per_stat_per_player(self):
        event = self._event()
        keymap = PROP_MARKET_KEYS["mlb"]
        _attach_prop_markets(event, self._raw_response(), keymap)
        subjects = {(m.subject, m.stat) for m in event.markets}
        assert subjects == {("Zach Thornton", "strikeouts"), ("Carmen Mlodzinski", "strikeouts")}

    def test_pools_prices_from_multiple_books(self):
        event = self._event()
        _attach_prop_markets(event, self._raw_response(), PROP_MARKET_KEYS["mlb"])
        thornton = next(m for m in event.markets if m.subject == "Zach Thornton")
        assert len(thornton.prices) == 4  # fanduel over/under + draftkings over/under
        assert {p.book for p in thornton.prices} == {"fanduel", "draftkings"}

    def test_outcome_names_are_over_under(self):
        event = self._event()
        _attach_prop_markets(event, self._raw_response(), PROP_MARKET_KEYS["mlb"])
        thornton = next(m for m in event.markets if m.subject == "Zach Thornton")
        assert {p.outcome for p in thornton.prices} == {"Over", "Under"}

    def test_ignores_markets_not_in_keymap(self):
        event = self._event()
        raw = {
            "bookmakers": [
                {"key": "fanduel", "markets": [{"key": "some_unmapped_market", "outcomes": [
                    {"name": "Over", "description": "Someone", "price": 100, "point": 1.5}
                ]}]}
            ]
        }
        _attach_prop_markets(event, raw, PROP_MARKET_KEYS["mlb"])
        assert event.markets == []

    def test_skips_outcomes_missing_required_fields(self):
        event = self._event()
        raw = {
            "bookmakers": [
                {"key": "fanduel", "markets": [{"key": "pitcher_strikeouts", "outcomes": [
                    {"name": "Over", "description": None, "price": 100, "point": 1.5},
                    {"name": "Over", "description": "Player", "price": None, "point": 1.5},
                    {"name": "Over", "description": "Player", "price": 100, "point": None},
                ]}]}
            ]
        }
        _attach_prop_markets(event, raw, PROP_MARKET_KEYS["mlb"])
        assert event.markets == []


class TestFetchProps:
    def _source(self):
        return TheOddsAPISource(api_key="dummy", regions=["us"], cache_dir="/tmp/test-oddsapi-cache")

    def _event(self, sport="mlb", event_id="e1"):
        return Event(
            event_id=event_id, sport=sport, league=sport.upper(),
            home_team="Home", away_team="Away",
            start_time=datetime.now(timezone.utc) + timedelta(hours=6),
        )

    def test_skips_unmapped_sport_without_calling_get(self):
        src = self._source()
        with patch.object(src, "_get") as mock_get:
            src.fetch_props([self._event(sport="tennis")])
        mock_get.assert_not_called()

    def test_respects_max_events(self):
        src = self._source()
        events = [self._event(event_id=f"e{i}") for i in range(3)]
        with patch.object(src, "_get", return_value={"bookmakers": []}) as mock_get:
            src.fetch_props(events, max_events=1)
        called_event_ids = {call.args[0].split("/")[-2] for call in mock_get.call_args_list}
        assert called_event_ids == {"e0"}

    def test_chunks_markets_into_groups_of_five(self):
        # nfl has 7 prop markets mapped -- must be requested in more than
        # one call, never all 7 at once.
        src = self._source()
        with patch.object(src, "_get", return_value={"bookmakers": []}) as mock_get:
            src.fetch_props([self._event(sport="nfl")])
        assert mock_get.call_count == 2
        market_params = [call.args[1]["markets"] for call in mock_get.call_args_list]
        assert all(len(p.split(",")) <= 5 for p in market_params)

    def test_one_events_failure_does_not_block_the_next(self):
        # nhl has 3 mapped prop markets -- one chunk, one call per event --
        # so this isolates failure-handling from the chunking behavior
        # already covered above.
        src = self._source()
        good_response = {
            "bookmakers": [
                {"key": "fanduel", "markets": [{"key": "player_points", "outcomes": [
                    {"name": "Over", "description": "Player X", "price": 100, "point": 4.5}
                ]}]}
            ]
        }

        def flaky_get(path, params):
            if "e-bad" in path:
                raise SourceError("simulated failure")
            return good_response

        events = [
            self._event(sport="nhl", event_id="e-bad"),
            self._event(sport="nhl", event_id="e-good"),
        ]
        with patch.object(src, "_get", side_effect=flaky_get):
            src.fetch_props(events)

        assert events[0].markets == []
        assert len(events[1].markets) == 1


class TestNWSWeather:
    def test_all_32_nfl_teams_have_venues(self):
        # A missing team means that team's games silently never get
        # weather -- worth catching directly rather than discovering it
        # the first time that team plays outdoors in the rain.
        assert len(NFL_VENUES) == 32

    def test_parse_wind_mph_single_value(self):
        assert _parse_wind_mph("10 mph") == 10.0

    def test_parse_wind_mph_range_takes_high_end(self):
        assert _parse_wind_mph("10 to 15 mph") == 15.0

    def test_parse_wind_mph_no_digits(self):
        assert _parse_wind_mph("Calm") == 0.0

    def test_closest_period_within_horizon(self):
        now = datetime.now(timezone.utc)
        periods = [
            {"startTime": (now + timedelta(hours=1)).isoformat()},
            {"startTime": (now + timedelta(hours=20)).isoformat()},
        ]
        chosen = _closest_period(periods, now + timedelta(hours=19))
        assert chosen is periods[1]

    def test_closest_period_beyond_horizon_returns_none(self):
        # Regression test: a naive "nearest available" match with no
        # ceiling would silently hand back today's weather mislabeled as a
        # forecast for a game a month away.
        now = datetime.now(timezone.utc)
        periods = [{"startTime": (now + timedelta(hours=1)).isoformat()}]
        assert _closest_period(periods, now + timedelta(days=40)) is None

    def test_closest_period_empty_list(self):
        assert _closest_period([], datetime.now(timezone.utc)) is None

    def test_dome_team_reports_without_any_http_call(self):
        event = MagicMock(event_id="e1", sport="nfl", home_team="Detroit Lions",
                           start_time=datetime.now(timezone.utc) + timedelta(hours=5))
        src = NWSWeatherSource()
        with patch("requests.get") as mock_get:
            reports = src.fetch_weather([event])
        mock_get.assert_not_called()
        assert reports["e1"].dome is True
        assert reports["e1"].wind_mph == 0.0

    def test_non_nfl_event_is_skipped(self):
        event = MagicMock(event_id="e1", sport="nba", home_team="Boston Celtics",
                           start_time=datetime.now(timezone.utc) + timedelta(hours=5))
        assert NWSWeatherSource().fetch_weather([event]) == {}

    def test_unknown_venue_is_skipped(self):
        event = MagicMock(event_id="e1", sport="nfl", home_team="Nonexistent Team",
                           start_time=datetime.now(timezone.utc) + timedelta(hours=5))
        assert NWSWeatherSource().fetch_weather([event]) == {}

    def test_outdoor_team_makes_the_two_call_chain(self):
        event = MagicMock(event_id="e1", sport="nfl", home_team="Green Bay Packers",
                           start_time=datetime.now(timezone.utc) + timedelta(hours=5))

        point_resp = MagicMock(status_code=200)
        point_resp.json.return_value = {
            "properties": {"forecastHourly": "https://api.weather.gov/gridpoints/X/1,1/forecast/hourly"}
        }
        forecast_resp = MagicMock(status_code=200)
        start = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        forecast_resp.json.return_value = {
            "properties": {
                "periods": [
                    {
                        "startTime": start,
                        "temperature": 55,
                        "windSpeed": "12 mph",
                        "probabilityOfPrecipitation": {"value": 30},
                        "shortForecast": "Rain",
                    }
                ]
            }
        }
        with patch("requests.get", side_effect=[point_resp, forecast_resp]) as mock_get:
            reports = NWSWeatherSource().fetch_weather([event])

        assert mock_get.call_count == 2
        report = reports["e1"]
        assert report.dome is False
        assert report.wind_mph == 12.0
        assert report.temperature_f == 55.0
        assert report.precipitation_chance == pytest.approx(0.30)
        assert report.description == "Rain"


class TestESPNInjuries:
    def test_status_mapping_known_values(self):
        assert _status_for("Out") == InjuryStatus.OUT
        assert _status_for("Injured Reserve") == InjuryStatus.OUT
        assert _status_for("Questionable") == InjuryStatus.QUESTIONABLE
        assert _status_for("Day-To-Day") == InjuryStatus.QUESTIONABLE
        assert _status_for("Probable") == InjuryStatus.PROBABLE
        assert _status_for("Active") == InjuryStatus.ACTIVE

    def test_unknown_status_defaults_to_questionable_not_active(self):
        # Defaulting an unrecognized status to "fine to play" would silently
        # hide real injuries behind a status ESPN happens to phrase
        # differently than expected.
        assert _status_for("Something ESPN Invented Tomorrow") == InjuryStatus.QUESTIONABLE

    def test_every_sport_position_table_is_nonempty(self):
        for sport in ("nfl", "nba", "wnba", "mlb", "nhl"):
            assert POSITION_POINT_VALUE[sport], f"{sport} has no position point values"

    def test_parse_injuries_realistic_payload(self):
        # Shape captured from a real ESPN injuries response.
        data = {
            "injuries": [
                {
                    "displayName": "Arizona Cardinals",
                    "injuries": [
                        {
                            "status": "Questionable",
                            "date": "2026-08-02T21:53Z",
                            "shortComment": "Limited in practice Thursday.",
                            "athlete": {
                                "displayName": "Reggie Virgil",
                                "position": {"abbreviation": "WR"},
                            },
                        }
                    ],
                }
            ]
        }
        reports = _parse_injuries(data, "nfl")
        assert len(reports) == 1
        r = reports[0]
        assert r.player == "Reggie Virgil"
        assert r.team == "Arizona Cardinals"
        assert r.status == InjuryStatus.QUESTIONABLE
        assert r.position == "WR"
        assert r.point_value == POSITION_POINT_VALUE["nfl"]["WR"]
        assert r.reported_at == datetime(2026, 8, 2, 21, 53, tzinfo=timezone.utc)

    def test_parse_injuries_skips_entries_without_a_player_name(self):
        data = {"injuries": [{"displayName": "Team", "injuries": [{"status": "Out", "athlete": {}}]}]}
        assert _parse_injuries(data, "nfl") == []

    def test_unlisted_position_gets_a_conservative_default_not_zero(self):
        data = {
            "injuries": [
                {
                    "displayName": "Team",
                    "injuries": [
                        {"status": "Out", "athlete": {"displayName": "Some Player", "position": {"abbreviation": "XYZ"}}}
                    ],
                }
            ]
        }
        reports = _parse_injuries(data, "nfl")
        assert reports[0].point_value > 0

    def test_fetch_injuries_one_sports_failure_does_not_break_others(self):
        def fake_get(url, timeout=None):
            resp = MagicMock()
            if "nfl" in url:
                resp.raise_for_status.side_effect = requests.exceptions.RequestException("boom")
            else:
                resp.raise_for_status.return_value = None
                resp.json.return_value = {
                    "injuries": [
                        {
                            "displayName": "Some Team",
                            "injuries": [
                                {"status": "Out", "athlete": {"displayName": "A Player", "position": {"abbreviation": "SP"}}}
                            ],
                        }
                    ]
                }
            return resp

        with patch("requests.get", side_effect=fake_get):
            reports = ESPNInjurySource().fetch_injuries(["nfl", "mlb"])
        assert len(reports) == 1
        assert reports[0].player == "A Player"

    def test_fetch_injuries_skips_unmapped_sports(self):
        with patch("requests.get") as mock_get:
            reports = ESPNInjurySource().fetch_injuries(["tennis"])
        mock_get.assert_not_called()
        assert reports == []
