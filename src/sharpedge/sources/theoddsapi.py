"""The Odds API adapter.

Covers most US books across the markets that matter, with a free tier that is
enough to run a daily card. Set ``ODDS_API_KEY`` in the environment.

Two operational details that are easy to get wrong and expensive to learn the
hard way:

**Credits are consumed per region per market.** Requesting three regions and
three markets in one call costs nine credits, not one. The default quota
disappears in a morning if you poll every minute across every sport.

**Freshness is what you are paying for.** A cached response is worth much less
than a live one, because the entire premise of stale-line detection is that
your snapshot is newer than the slow book's price. The cache TTL here is
deliberately short, and polling frequency should be driven by how close to
kickoff you are rather than by a fixed interval.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import Event, Market, MarketType, Price
from .base import SourceError

BASE_URL = "https://api.the-odds-api.com/v4"

# The Odds API sport keys for the leagues this package understands.
SPORT_KEYS: dict[str, str] = {
    "nfl": "americanfootball_nfl",
    "ncaaf": "americanfootball_ncaaf",
    "nba": "basketball_nba",
    "ncaab": "basketball_ncaab",
    "wnba": "basketball_wnba",
    "mlb": "baseball_mlb",
    "npb": "baseball_npb",
    "nhl": "icehockey_nhl",
    "soccer": "soccer_epl",
}

MARKET_KEYS: dict[str, MarketType] = {
    "h2h": MarketType.MONEYLINE,
    "spreads": MarketType.SPREAD,
    "totals": MarketType.TOTAL,
    "alternate_spreads": MarketType.ALTERNATE_SPREAD,
    "alternate_totals": MarketType.ALTERNATE_TOTAL,
}

# The Odds API's player-prop market keys, mapped onto this package's
# internal stat names (market/taxonomy.py's PROP_PROFILES -- only stats
# that already have a real profile there are listed; a market with no
# profile would just fall back to "unprofiled, treated conservatively"
# pricing, which is not worth the extra API call). Props are priced per
# *event*, not bulk per sport the way fetch_events pulls core markets --
# see fetch_props for why that changes how this gets called.
#
# NPB (baseball_npb) has no entry here on purpose: The Odds API does not
# list player-prop markets for it, only h2h/spreads/totals. fetch_props
# already treats a missing keymap as "nothing to fetch" and moves on, so
# this is the correct way to represent "core markets only."
PROP_MARKET_KEYS: dict[str, dict[str, str]] = {
    "nfl": {
        "player_pass_yds": "passing_yards",
        "player_pass_tds": "passing_tds",
        "player_pass_completions": "completions",
        "player_rush_yds": "rushing_yards",
        "player_receptions": "receptions",
        "player_reception_yds": "receiving_yards",
        "player_anytime_td": "anytime_td",
    },
    "nba": {
        "player_points": "points",
        "player_rebounds": "rebounds",
        "player_assists": "assists",
        "player_threes": "threes_made",
        "player_steals": "steals",
        "player_blocks": "blocks",
        "player_points_rebounds_assists": "pra",
    },
    "wnba": {
        "player_points": "points",
        "player_rebounds": "rebounds",
        "player_assists": "assists",
        "player_threes": "threes_made",
        "player_steals": "steals",
        "player_blocks": "blocks",
        "player_points_rebounds_assists": "pra",
    },
    "mlb": {
        "pitcher_strikeouts": "strikeouts",
        "pitcher_hits_allowed": "hits_allowed",
        "pitcher_earned_runs": "earned_runs",
        "batter_hits": "hits",
        "batter_total_bases": "total_bases",
        "batter_rbis": "rbis",
        "batter_runs_scored": "runs_scored",
        "batter_home_runs": "home_runs",
    },
    "nhl": {
        "player_points": "player_points",
        "player_shots_on_goal": "shots_on_goal",
        "player_total_saves": "saves",
    },
}

# The Odds API rejects a request for too many markets at once; chunk to
# stay under that regardless of how many stats a sport's map above grows to.
_PROPS_PER_REQUEST = 5

# Their bookmaker keys mapped onto ours.
BOOK_ALIASES: dict[str, str] = {
    "pinnacle": "pinnacle",
    "circasports": "circa",
    "betfair_ex_uk": "betfair",
    "betfair_ex_eu": "betfair",
    "betfair": "betfair",
    "draftkings": "draftkings",
    "fanduel": "fanduel",
    "betmgm": "betmgm",
    "williamhill_us": "caesars",
    "caesars": "caesars",
    "betrivers": "betrivers",
    "espnbet": "espnbet",
    "fanatics": "fanatics",
    "hardrockbet": "hardrock",
    "bovada": "bovada",
    "betonlineag": "bookmaker",
    "lowvig": "bookmaker",
}


class TheOddsAPISource:
    """Live odds from The Odds API v4."""

    name = "theoddsapi"

    def __init__(
        self,
        api_key: str,
        regions: list[str] | None = None,
        markets: list[str] | None = None,
        cache_dir: str | Path = "data/cache",
        cache_ttl: int = 120,
        timeout: float = 12.0,
    ):
        if not api_key:
            raise SourceError(
                "no API key. Set ODDS_API_KEY in the environment or api_key in the config."
            )
        self.api_key = api_key
        self.regions = regions or ["us", "us2"]
        self.markets = markets or ["h2h", "spreads", "totals"]
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.credits_remaining: int | None = None
        self.credits_used: int | None = None

    # -- HTTP ---------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise SourceError(
                "the live feed needs `requests` installed: pip install requests"
            ) from exc

        params = {**params, "apiKey": self.api_key}
        cache_key = self._cache_key(path, params)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{BASE_URL}{path}"
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
        except Exception as exc:
            raise SourceError(f"request to {path} failed: {exc}") from exc

        if response.status_code == 401:
            raise SourceError("API key rejected (401). Check ODDS_API_KEY.")
        if response.status_code == 429:
            raise SourceError("rate limited (429). Slow down or upgrade the plan.")
        if response.status_code >= 400:
            raise SourceError(f"{path} returned {response.status_code}: {response.text[:200]}")

        # These headers are the only way to know how much quota is left.
        self.credits_remaining = _int_or_none(response.headers.get("x-requests-remaining"))
        self.credits_used = _int_or_none(response.headers.get("x-requests-used"))

        data = response.json()
        self._write_cache(cache_key, data)
        return data

    def _cache_key(self, path: str, params: dict) -> str:
        safe = {k: v for k, v in params.items() if k != "apiKey"}
        raw = path + json.dumps(safe, sort_keys=True)
        return str(abs(hash(raw)))

    def _read_cache(self, key: str) -> Any | None:
        p = self.cache_dir / f"{key}.json"
        if not p.exists():
            return None
        if time.time() - p.stat().st_mtime > self.cache_ttl:
            return None
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

    def _write_cache(self, key: str, data: Any) -> None:
        try:
            (self.cache_dir / f"{key}.json").write_text(json.dumps(data))
        except Exception:
            pass  # a failed cache write must never break a run

    # -- public API ---------------------------------------------------------

    def fetch_events(self, sports: list[str]) -> list[Event]:
        """Fetch and normalize odds for the requested leagues."""
        events: list[Event] = []
        for sport in sports:
            key = SPORT_KEYS.get(sport.lower())
            if key is None:
                continue
            raw = self._get(
                f"/sports/{key}/odds",
                {
                    "regions": ",".join(self.regions),
                    "markets": ",".join(self.markets),
                    "oddsFormat": "american",
                    "dateFormat": "iso",
                },
            )
            events.extend(self._parse_events(raw, sport))
        return events

    def _parse_events(self, raw: list[dict], sport: str) -> list[Event]:
        out: list[Event] = []
        for item in raw:
            try:
                event = Event(
                    event_id=item["id"],
                    sport=sport,
                    league=sport.upper(),
                    home_team=item["home_team"],
                    away_team=item["away_team"],
                    start_time=_parse_iso(item["commence_time"]),
                )
            except (KeyError, ValueError):
                continue

            by_market: dict[MarketType, Market] = {}
            for bookmaker in item.get("bookmakers", []):
                book_key = BOOK_ALIASES.get(bookmaker.get("key", ""), bookmaker.get("key", ""))
                updated = _parse_iso(bookmaker.get("last_update")) if bookmaker.get(
                    "last_update"
                ) else datetime.now(timezone.utc)

                for market in bookmaker.get("markets", []):
                    mtype = MARKET_KEYS.get(market.get("key", ""))
                    if mtype is None:
                        continue
                    outcomes = market.get("outcomes", [])
                    if not outcomes:
                        continue

                    target = by_market.get(mtype)
                    if target is None:
                        target = Market(
                            event_id=event.event_id,
                            market_type=mtype,
                            outcomes=[_outcome_name(o, event) for o in outcomes],
                        )
                        by_market[mtype] = target

                    for outcome in outcomes:
                        name = _outcome_name(outcome, event)
                        if name not in target.outcomes:
                            target.outcomes.append(name)
                        price = outcome.get("price")
                        if price is None:
                            continue
                        target.prices.append(
                            Price(
                                book=book_key,
                                outcome=name,
                                american=float(price),
                                line=_line_of(outcome),
                                timestamp=updated,
                            )
                        )

            event.markets = list(by_market.values())
            if event.markets:
                out.append(event)
        return out

    def fetch_props(self, events: list[Event], max_events: int | None = None) -> None:
        """Attach player-prop markets to each event, in place.

        Unlike ``fetch_events``, which pulls a whole sport's core markets in
        one call, props are priced per event -- there is no bulk endpoint.
        That means one additional request per event per market chunk, which
        is real credit cost, not a free extension of the odds pull. Callers
        should pass an already-filtered near-term slate (a season's worth
        of events each getting a props call would burn a quota in minutes),
        and ``max_events`` is a second, explicit backstop on top of that.

        A failure fetching one event's props (a market not offered, a rate
        limit, whatever) is swallowed and moves on to the next event --
        losing one game's props is not worth losing the whole card over.
        """
        targets = events[:max_events] if max_events is not None else events
        for event in targets:
            keymap = PROP_MARKET_KEYS.get(event.sport.lower())
            sport_key = SPORT_KEYS.get(event.sport.lower())
            if not keymap or sport_key is None:
                continue
            market_keys = list(keymap.keys())
            for start in range(0, len(market_keys), _PROPS_PER_REQUEST):
                chunk = market_keys[start : start + _PROPS_PER_REQUEST]
                try:
                    raw = self._get(
                        f"/sports/{sport_key}/events/{event.event_id}/odds",
                        {
                            "regions": ",".join(self.regions),
                            "markets": ",".join(chunk),
                            "oddsFormat": "american",
                        },
                    )
                except SourceError:
                    continue
                _attach_prop_markets(event, raw, keymap)

    def fetch_scores(self, sport: str, days_back: int = 2) -> list[dict]:
        """Final scores, for settling bets and grading the model."""
        key = SPORT_KEYS.get(sport.lower())
        if key is None:
            return []
        return self._get(f"/sports/{key}/scores", {"daysFrom": days_back})

    def quota(self) -> str:
        """Human-readable credit status after at least one request."""
        if self.credits_remaining is None:
            return "quota unknown (no request made yet)"
        return f"{self.credits_remaining} credits remaining, {self.credits_used} used"


def _attach_prop_markets(event: Event, raw: dict, keymap: dict[str, str]) -> None:
    """Parse one event-odds response into PLAYER_PROP markets, one per (stat, player)."""
    by_subject: dict[tuple[str, str], Market] = {}
    for bookmaker in raw.get("bookmakers", []):
        book_key = BOOK_ALIASES.get(bookmaker.get("key", ""), bookmaker.get("key", ""))
        updated = (
            _parse_iso(bookmaker["last_update"])
            if bookmaker.get("last_update")
            else datetime.now(timezone.utc)
        )
        for market in bookmaker.get("markets", []):
            stat = keymap.get(market.get("key", ""))
            if stat is None:
                continue
            for outcome in market.get("outcomes", []):
                # Player props carry the subject in "description" rather
                # than "name" -- "name" is Over/Under here, same as totals.
                player = outcome.get("description")
                price = outcome.get("price")
                line = _line_of(outcome)
                if not player or price is None or line is None:
                    continue
                key = (stat, player)
                target = by_subject.get(key)
                if target is None:
                    target = Market(
                        event_id=event.event_id,
                        market_type=MarketType.PLAYER_PROP,
                        outcomes=["Over", "Under"],
                        subject=player,
                        metadata={"stat": stat},
                    )
                    by_subject[key] = target
                target.prices.append(
                    Price(
                        book=book_key,
                        outcome=_outcome_name(outcome, event),
                        american=float(price),
                        line=line,
                        timestamp=updated,
                    )
                )
    event.markets.extend(by_subject.values())


def _outcome_name(outcome: dict, event: Event) -> str:
    """Normalize an outcome label. Totals come back as Over/Under."""
    name = outcome.get("name", "")
    if name.lower() in ("over", "under"):
        return name.title()
    return name


def _line_of(outcome: dict) -> float | None:
    point = outcome.get("point")
    return float(point) if point is not None else None


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
