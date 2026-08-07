"""Synthetic market generator.

Exists so the whole pipeline can be run, tested, and demonstrated without an
API key, and so the tests have a market whose ground truth is known.

The generator is not random noise dressed up as odds. It simulates the actual
structure of a sportsbook market:

* a true probability, which only the generator knows
* market makers pricing close to it with a thin margin
* retail books shading toward the public side -- favorites, overs, and
  popular teams -- and charging a fatter margin
* a subset of soft books left deliberately stale after a simulated line move,
  which is what the pipeline should find

That last piece matters: a demo where edges are uniform noise would validate
nothing, because a screen that finds noise finds it everywhere. Here the
+EV bets are the stale books and the over-shaded retail sides, which is what
the real edges look like.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from ..models import (
    Event,
    InjuryReport,
    InjuryStatus,
    Market,
    MarketType,
    NewsItem,
    Price,
    PublicBetting,
    WeatherReport,
)
from ..oddsmath import (
    prob_to_american,
    prob_to_decimal,
    spread_to_prob,
    total_over_prob,
)
from ..market.books import BOOKS, get_book

NFL_TEAMS = [
    "Kansas City Chiefs", "Buffalo Bills", "Philadelphia Eagles", "San Francisco 49ers",
    "Baltimore Ravens", "Detroit Lions", "Dallas Cowboys", "Miami Dolphins",
    "Green Bay Packers", "Cincinnati Bengals", "Houston Texans", "Cleveland Browns",
    "New York Jets", "Denver Broncos", "Seattle Seahawks", "Los Angeles Chargers",
]

NBA_TEAMS = [
    "Boston Celtics", "Denver Nuggets", "Milwaukee Bucks", "Phoenix Suns",
    "Los Angeles Lakers", "Golden State Warriors", "Miami Heat", "New York Knicks",
    "Philadelphia 76ers", "Dallas Mavericks", "Minnesota Timberwolves", "Utah Jazz",
]

WNBA_TEAMS = [
    "Las Vegas Aces", "New York Liberty", "Connecticut Sun", "Minnesota Lynx",
    "Seattle Storm", "Phoenix Mercury", "Indiana Fever", "Chicago Sky",
    "Atlanta Dream", "Washington Mystics", "Dallas Wings", "Los Angeles Sparks",
]

# Team pool and typical combined final score, per sport. Explicit per sport
# rather than a binary if/else -- a fallback that quietly hands an unlisted
# sport the wrong league's teams and scoring level is a bug waiting for the
# next sport added, which is exactly how WNBA's team pool was almost wired up
# to reuse the NBA's.
SPORT_TEAMS: dict[str, list[str]] = {
    "nfl": NFL_TEAMS,
    "nba": NBA_TEAMS,
    "wnba": WNBA_TEAMS,
}

# WNBA quarters run 10 minutes to the NBA's 12 and rosters carry fewer high-
# usage scorers, so the combined final score sits well below the NBA's.
SPORT_BASE_TOTAL: dict[str, float] = {
    "nfl": 44.5,
    "nba": 224.5,
    "wnba": 163.5,
}

# Teams the public bets regardless of price. Retail books shade their numbers
# because they know the money is coming either way.
PUBLIC_TEAMS = {
    "Kansas City Chiefs", "Dallas Cowboys", "Green Bay Packers", "Philadelphia Eagles",
    "Los Angeles Lakers", "Golden State Warriors", "Boston Celtics", "New York Knicks",
    "New York Liberty", "Las Vegas Aces", "Indiana Fever",
}


class DemoSource:
    """Generates a realistic slate. Seeded, so runs are reproducible."""

    name = "demo"

    def __init__(self, seed: int = 7, n_events: int = 8, stale_rate: float = 0.30):
        self.rng = random.Random(seed)
        self.n_events = n_events
        self.stale_rate = stale_rate
        self._truth: dict[str, dict] = {}

    # -- odds ---------------------------------------------------------------

    def fetch_events(self, sports: list[str] | None = None) -> list[Event]:
        sports = sports or ["nfl", "nba"]
        events: list[Event] = []
        now = datetime.now(timezone.utc)

        for i in range(self.n_events):
            sport = sports[i % len(sports)]
            teams = SPORT_TEAMS.get(sport, NBA_TEAMS)
            pool = self.rng.sample(teams, 2)
            home, away = pool[0], pool[1]

            true_spread = round(self.rng.uniform(-10.5, 10.5) * 2) / 2  # home spread
            base_total = SPORT_BASE_TOTAL.get(sport, 224.5)
            true_total = round((base_total + self.rng.uniform(-8, 8)) * 2) / 2
            hours_out = self.rng.uniform(2, 72)

            event = Event(
                event_id=f"{sport}-{i:03d}",
                sport=sport,
                league=sport.upper(),
                home_team=home,
                away_team=away,
                start_time=now + timedelta(hours=hours_out),
                metadata=self._metadata(sport, home, away),
            )

            self._truth[event.event_id] = {
                "spread": true_spread,
                "total": true_total,
                "home_prob": spread_to_prob(true_spread, sport),
            }

            event.markets = [
                self._moneyline(event, true_spread, now),
                self._spread(event, true_spread, now),
                self._total(event, true_total, now),
            ]
            events.append(event)

        return events

    # -- market construction ------------------------------------------------

    def _book_keys(self) -> list[str]:
        return list(BOOKS.keys())

    def _shade(self, book_key: str, is_public_side: bool, is_over: bool) -> float:
        """Probability points a book adds to the popular side.

        Market makers do not shade. Retail books shade meaningfully, and soft
        books shade the most, because they are pricing for recreational flow
        rather than for accuracy.
        """
        book = get_book(book_key)
        if book.is_sharp:
            return 0.0
        base = {"retail_sharp": 0.006, "retail": 0.011, "soft": 0.018}.get(
            book.tier.value, 0.012
        )
        magnitude = 0.0
        if is_public_side:
            magnitude += base
        if is_over:
            magnitude += base * 0.6  # the public likes overs
        return magnitude

    def _margin(self, book_key: str) -> float:
        """Total overround the book charges on a two-way market."""
        book = get_book(book_key)
        return {
            "market_maker": 0.021,
            "exchange": 0.012,
            "retail_sharp": 0.042,
            "retail": 0.048,
            "soft": 0.058,
        }.get(book.tier.value, 0.048)

    def _stale_offset(self, book_key: str, event_id: str) -> float:
        """Points a slow book lags behind after a simulated market move."""
        book = get_book(book_key)
        if book.is_sharp or book.tier.value == "retail_sharp":
            return 0.0
        rng = random.Random(f"{event_id}-{book_key}")
        if rng.random() > self.stale_rate:
            return 0.0
        return rng.choice([0.5, 1.0, 1.0, 1.5])

    def _two_way_prices(
        self,
        event: Event,
        market_type: MarketType,
        outcome_a: str,
        outcome_b: str,
        true_prob_a: float,
        line_a: float | None,
        line_b: float | None,
        now: datetime,
        public_side: str | None = None,
    ) -> list[Price]:
        prices: list[Price] = []
        for book_key in self._book_keys():
            noise = self.rng.gauss(0, 0.006 if get_book(book_key).is_sharp else 0.013)
            shade_a = self._shade(
                book_key,
                is_public_side=(public_side == outcome_a),
                is_over=outcome_a.lower().startswith("over"),
            )
            shade_b = self._shade(
                book_key,
                is_public_side=(public_side == outcome_b),
                is_over=outcome_b.lower().startswith("over"),
            )

            p_a = min(max(true_prob_a + noise + shade_a - shade_b, 0.03), 0.97)
            p_b = 1.0 - p_a

            margin = self._margin(book_key)
            raw_a = p_a * (1.0 + margin)
            raw_b = p_b * (1.0 + margin)

            stale = self._stale_offset(book_key, event.event_id)
            la, lb = line_a, line_b
            if stale and line_a is not None and line_b is not None:
                # A slow book still showing the old number, which is better
                # for one side and worse for the other.
                la = line_a + stale
                lb = line_b - stale
                # The stale line is generous, so its price is too.
                raw_a *= 0.965

            age = timedelta(minutes=self.rng.uniform(0, 12) + (35 if stale else 0))
            for outcome, raw, line in ((outcome_a, raw_a, la), (outcome_b, raw_b, lb)):
                american = prob_to_american(min(max(raw, 0.02), 0.98))
                prices.append(
                    Price(
                        book=book_key,
                        outcome=outcome,
                        american=round(american / 5) * 5,
                        line=line,
                        timestamp=now - age,
                        limit=get_book(book_key).max_limit,
                    )
                )
        return prices

    def _moneyline(self, event: Event, spread: float, now: datetime) -> Market:
        p_home = spread_to_prob(spread, event.sport)
        public = event.home_team if event.home_team in PUBLIC_TEAMS else (
            event.away_team if event.away_team in PUBLIC_TEAMS else None
        )
        return Market(
            event_id=event.event_id,
            market_type=MarketType.MONEYLINE,
            outcomes=[event.home_team, event.away_team],
            prices=self._two_way_prices(
                event, MarketType.MONEYLINE, event.home_team, event.away_team,
                p_home, None, None, now, public,
            ),
        )

    def _spread(self, event: Event, spread: float, now: datetime) -> Market:
        public = event.home_team if event.home_team in PUBLIC_TEAMS else (
            event.away_team if event.away_team in PUBLIC_TEAMS else None
        )
        return Market(
            event_id=event.event_id,
            market_type=MarketType.SPREAD,
            outcomes=[event.home_team, event.away_team],
            prices=self._two_way_prices(
                event, MarketType.SPREAD, event.home_team, event.away_team,
                0.5, spread, -spread, now, public,
            ),
        )

    def _total(self, event: Event, total: float, now: datetime) -> Market:
        p_over = total_over_prob(total, total, event.sport)
        return Market(
            event_id=event.event_id,
            market_type=MarketType.TOTAL,
            outcomes=["Over", "Under"],
            prices=self._two_way_prices(
                event, MarketType.TOTAL, "Over", "Under",
                p_over, total, total, now, "Over",
            ),
        )

    def _metadata(self, sport: str, home: str, away: str) -> dict:
        meta: dict = {}
        if sport == "nba":
            meta["back_to_back"] = {away: self.rng.random() < 0.28, home: self.rng.random() < 0.14}
            meta["rest_days"] = {home: self.rng.choice([1, 2, 2, 3]), away: self.rng.choice([0, 1, 1, 2])}
        if sport == "wnba":
            # A much lighter schedule than the NBA's (roughly 40 games to 82),
            # so true back-to-backs are less common.
            meta["back_to_back"] = {away: self.rng.random() < 0.16, home: self.rng.random() < 0.08}
            meta["rest_days"] = {home: self.rng.choice([1, 2, 2, 3, 4]), away: self.rng.choice([1, 1, 2, 2, 3])}
        if sport == "nfl":
            meta["off_bye"] = {home: self.rng.random() < 0.10, away: self.rng.random() < 0.10}
            meta["short_week"] = {home: self.rng.random() < 0.08, away: self.rng.random() < 0.08}
        if self.rng.random() < 0.2:
            meta["spots"] = {self.rng.choice([home, away]): [self.rng.choice(["lookahead", "letdown"])]}
        return meta

    # -- ancillary feeds ----------------------------------------------------

    def fetch_news(self, events: list[Event] | None = None, since=None) -> list[NewsItem]:
        """A handful of headlines, some fresh enough to be actionable."""
        events = events or []
        now = datetime.now(timezone.utc)
        templates = [
            ("{player} ruled out for tonight's game with a knee injury", 4),
            ("{player} listed as questionable, coach calls him a game-time decision", 55),
            ("{player} expected to play after clearing concussion protocol", 180),
            ("{team} will be without three starters, per team announcement", 12),
            ("High winds and rain expected at kickoff, gusts up to 25 mph", 90),
        ]
        items: list[NewsItem] = []
        for event in events[:5]:
            template, age = self.rng.choice(templates)
            team = self.rng.choice([event.home_team, event.away_team])
            player = f"{self.rng.choice(['Jordan', 'Tyler', 'Marcus', 'Devin', 'Chris'])} " \
                     f"{self.rng.choice(['Hayes', 'Brooks', 'Ellis', 'Vance', 'Porter'])}"
            items.append(
                NewsItem(
                    headline=template.format(player=player, team=team.split()[-1]),
                    published=now - timedelta(minutes=age * self.rng.uniform(0.5, 1.5)),
                    source="demo-feed",
                    teams=[team],
                    players=[player] if "{player}" in template else [],
                )
            )
        return items

    def fetch_injuries(self, events: list[Event] | None = None) -> list[InjuryReport]:
        events = events or []
        now = datetime.now(timezone.utc)
        reports: list[InjuryReport] = []
        for event in events:
            if self.rng.random() > 0.45:
                continue
            team = self.rng.choice([event.home_team, event.away_team])
            if event.sport == "nfl":
                position, value = self.rng.choice([("QB", 6.5), ("WR", 1.4), ("EDGE", 1.3)])
            else:
                position, value = self.rng.choice([("STAR", 4.5), ("STARTER", 2.0)])
            reports.append(
                InjuryReport(
                    player=f"{self.rng.choice(['A.', 'J.', 'M.'])} "
                           f"{self.rng.choice(['Carter', 'Reed', 'Nolan', 'Shaw'])}",
                    team=team,
                    status=self.rng.choice(
                        [InjuryStatus.OUT, InjuryStatus.QUESTIONABLE, InjuryStatus.DOUBTFUL]
                    ),
                    position=position,
                    point_value=value,
                    reported_at=now - timedelta(minutes=self.rng.uniform(5, 400)),
                )
            )
        return reports

    def fetch_weather(self, events: list[Event]) -> dict[str, WeatherReport]:
        out: dict[str, WeatherReport] = {}
        for event in events:
            if event.sport != "nfl":
                continue
            dome = self.rng.random() < 0.3
            out[event.event_id] = WeatherReport(
                event_id=event.event_id,
                wind_mph=0.0 if dome else max(0.0, self.rng.gauss(9, 7)),
                temperature_f=70.0 if dome else self.rng.uniform(18, 78),
                precipitation_chance=0.0 if dome else max(0.0, self.rng.gauss(0.2, 0.25)),
                dome=dome,
            )
        return out

    def fetch_public(self, events: list[Event]) -> list[PublicBetting]:
        out: list[PublicBetting] = []
        for event in events:
            for market_type, outcome in (
                (MarketType.SPREAD, event.home_team),
                (MarketType.TOTAL, "Over"),
            ):
                tickets = self.rng.uniform(0.35, 0.82)
                # Public money is small money: handle share usually trails
                # ticket share on the popular side.
                handle = tickets + self.rng.gauss(-0.05, 0.12)
                out.append(
                    PublicBetting(
                        event_id=event.event_id,
                        market_type=market_type,
                        outcome=outcome,
                        ticket_pct=round(tickets, 3),
                        handle_pct=round(min(max(handle, 0.05), 0.95), 3),
                    )
                )
        return out

    def truth(self, event_id: str) -> dict:
        """Ground truth for tests. Not available from any real feed."""
        return self._truth.get(event_id, {})
