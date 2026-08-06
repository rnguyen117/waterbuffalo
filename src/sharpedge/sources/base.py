"""Data source interface.

Feeds change, get rate limited, and go down. Everything downstream depends on
:class:`Event` objects rather than any provider's JSON, so swapping a feed is
a single class and nothing else moves.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..models import Event, InjuryReport, NewsItem, PublicBetting, WeatherReport


class OddsSource(Protocol):
    """Anything that can produce priced events."""

    name: str

    def fetch_events(self, sports: list[str]) -> list[Event]:
        ...


class NewsSource(Protocol):
    """Anything that can produce headlines."""

    name: str

    def fetch_news(self, since: datetime | None = None) -> list[NewsItem]:
        ...


class InjurySource(Protocol):
    name: str

    def fetch_injuries(self, league: str) -> list[InjuryReport]:
        ...


class WeatherSource(Protocol):
    name: str

    def fetch_weather(self, events: list[Event]) -> dict[str, WeatherReport]:
        ...


class PublicBettingSource(Protocol):
    name: str

    def fetch_public(self, events: list[Event]) -> list[PublicBetting]:
        ...


class SourceError(RuntimeError):
    """Raised when a feed fails in a way the pipeline should report, not crash on."""
