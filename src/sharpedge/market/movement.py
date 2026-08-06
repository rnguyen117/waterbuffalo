"""Line movement: steam, reverse line movement, stale prices, and CLV.

Prices are a time series, and the shape of that series carries information the
current snapshot does not. Three patterns pay for themselves:

**Steam.** Several high-limit books move the same direction within minutes.
That is a syndicate firing at multiple outlets simultaneously, and the number
they left behind at slow books is briefly wrong. Chasing steam after the
market has adjusted is a losing game -- the value is entirely in the books
that have not moved yet.

**Reverse line movement.** The line moves *against* the side taking most of
the tickets. If 70% of bets are on the favorite and the favorite's price gets
cheaper, the money disagrees with the tickets: a small number of large,
respected wagers are on the other side. This is the classic public-fade
signal and it is one of the few sentiment indicators with durable published
support.

**Staleness.** The sharp market has moved and a soft book has not repriced.
This is not a prediction at all, it is a latency arbitrage against a slow
operator, and it is where most realized profit in this package comes from.

The fourth thing tracked here is **closing line value**, which is the only
honest scoreboard for a bettor. Results over any single season are mostly
variance; beating the closing number is not.
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..models import LineSnapshot, Market, MarketType, PublicBetting, utcnow
from ..oddsmath import american_to_prob, devig, logit
from .books import get_book


# ---------------------------------------------------------------------------
# Snapshot storage
# ---------------------------------------------------------------------------


class LineHistory:
    """Durable store of every line we have seen.

    SQLite because the daily run should be able to answer "where did this
    open" months later without keeping a process alive, and because closing
    line value cannot be computed at all without a persistent record.
    """

    def __init__(self, path: str | Path = "data/lines.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                market_type TEXT NOT NULL,
                outcome TEXT NOT NULL,
                book TEXT NOT NULL,
                american REAL NOT NULL,
                line REAL,
                ts TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snap_lookup
                ON snapshots(event_id, market_type, outcome, book, ts);
            CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshots(ts);
            """
        )
        self.conn.commit()

    def record_market(self, market: Market, now: datetime | None = None) -> int:
        """Persist every price currently in a market. Returns rows written."""
        now = now or utcnow()
        rows = [
            (
                market.event_id,
                market.market_type.value,
                p.outcome,
                p.book,
                p.american,
                p.line,
                (p.timestamp or now).isoformat(),
            )
            for p in market.prices
        ]
        if not rows:
            return 0
        self.conn.executemany(
            "INSERT INTO snapshots (event_id, market_type, outcome, book, american, line, ts)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()
        return len(rows)

    def series(
        self,
        event_id: str,
        market_type: MarketType,
        outcome: str,
        book: str | None = None,
    ) -> list[LineSnapshot]:
        """Every observation for one outcome, oldest first."""
        sql = (
            "SELECT * FROM snapshots WHERE event_id=? AND market_type=? AND outcome=?"
        )
        params: list = [event_id, market_type.value, outcome]
        if book:
            sql += " AND book=?"
            params.append(book)
        sql += " ORDER BY ts ASC"
        return [
            LineSnapshot(
                event_id=r["event_id"],
                market_type=MarketType(r["market_type"]),
                outcome=r["outcome"],
                book=r["book"],
                american=r["american"],
                line=r["line"],
                timestamp=_parse_ts(r["ts"]),
            )
            for r in self.conn.execute(sql, params)
        ]

    def opener(
        self, event_id: str, market_type: MarketType, outcome: str
    ) -> LineSnapshot | None:
        """The first price we ever recorded, preferring a sharp book."""
        rows = self.series(event_id, market_type, outcome)
        if not rows:
            return None
        sharp = [r for r in rows if get_book(r.book).is_sharp]
        return (sharp or rows)[0]

    def closing(
        self, event_id: str, market_type: MarketType, outcome: str, start_time: datetime
    ) -> LineSnapshot | None:
        """The last sharp price before kickoff -- the number that grades CLV."""
        rows = [
            r
            for r in self.series(event_id, market_type, outcome)
            if r.timestamp <= start_time
        ]
        if not rows:
            return None
        sharp = [r for r in rows if get_book(r.book).is_sharp]
        return (sharp or rows)[-1]

    def close(self) -> None:
        self.conn.close()


def _parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Movement analysis
# ---------------------------------------------------------------------------


@dataclass
class MovementRead:
    """What the price history says about one outcome."""

    outcome: str
    opening_line: float | None = None
    current_line: float | None = None
    opening_american: float | None = None
    current_american: float | None = None
    steam: bool = False
    steam_direction: int = 0          # +1 toward this outcome, -1 away
    reverse_line_movement: bool = False
    stale_books: list[tuple[str, float]] = None  # (book, points behind sharp)
    sharp_move_points: float = 0.0
    notes: list[str] = None

    def __post_init__(self) -> None:
        if self.stale_books is None:
            self.stale_books = []
        if self.notes is None:
            self.notes = []

    @property
    def line_move(self) -> float:
        """How far the line has traveled since it opened, in points."""
        if self.opening_line is None or self.current_line is None:
            return 0.0
        return self.current_line - self.opening_line

    @property
    def price_move_prob(self) -> float:
        """Movement in implied-probability terms, for moneyline markets."""
        if self.opening_american is None or self.current_american is None:
            return 0.0
        return american_to_prob(self.current_american) - american_to_prob(
            self.opening_american
        )


def detect_steam(
    history: list[LineSnapshot],
    window_minutes: float = 20.0,
    min_books: int = 3,
    min_move: float = 0.5,
) -> tuple[bool, int]:
    """Detect a coordinated move across multiple high-limit books.

    Returns ``(is_steam, direction)``. Only sharp and retail-sharp books
    count: three soft books following each other twenty minutes late is the
    echo of a steam move, not the move itself, and by then the price is gone.
    """
    if len(history) < 2:
        return False, 0

    relevant = [s for s in history if get_book(s.book).sharpness >= 0.40]
    if not relevant:
        return False, 0

    latest = max(s.timestamp for s in relevant)
    window_start = latest - timedelta(minutes=window_minutes)

    moves: dict[str, float] = {}
    by_book: dict[str, list[LineSnapshot]] = defaultdict(list)
    for s in relevant:
        by_book[s.book].append(s)

    for book, snaps in by_book.items():
        snaps.sort(key=lambda s: s.timestamp)
        before = [s for s in snaps if s.timestamp <= window_start]
        during = [s for s in snaps if s.timestamp > window_start]
        if not before or not during:
            continue
        start, end = before[-1], during[-1]
        if start.line is not None and end.line is not None:
            moves[book] = end.line - start.line
        else:
            moves[book] = american_to_prob(end.american) - american_to_prob(
                start.american
            )

    movers = [m for m in moves.values() if abs(m) >= min_move * 0.5]
    if len(movers) < min_books:
        return False, 0

    positive = sum(1 for m in movers if m > 0)
    negative = sum(1 for m in movers if m < 0)
    # Genuine steam is one-directional. Books drifting both ways is churn.
    if positive >= min_books and negative == 0:
        return True, 1
    if negative >= min_books and positive == 0:
        return True, -1
    return False, 0


def detect_reverse_line_movement(
    outcome: str,
    opening_line: float | None,
    current_line: float | None,
    public: PublicBetting | None,
    ticket_threshold: float = 0.60,
) -> tuple[bool, str]:
    """Detect the line moving against the majority of tickets.

    The interpretation matters more than the detection. RLM says large,
    respected wagers landed on the unpopular side hard enough to overcome the
    public flow the book was happy to take. It is evidence about *who* is on
    a side, not proof that side wins.
    """
    if public is None or opening_line is None or current_line is None:
        return False, ""
    if public.ticket_pct < ticket_threshold:
        return False, ""

    move = current_line - opening_line
    # For the side with heavy ticket support, a line moving in that side's
    # favor (more negative spread number for a favorite) is ordinary. The
    # line moving the other way is the signal.
    if public.outcome == outcome and move > 0.5:
        return True, (
            f"{public.ticket_pct:.0%} of tickets on {outcome} but the line moved "
            f"{move:+.1f} against it -- money is on the other side"
        )
    return False, ""


def sharp_money_indicator(public: PublicBetting) -> tuple[float, str]:
    """Score the ticket-versus-handle split.

    Handle share well above ticket share means the average bet on that side
    is large. Large bets skew toward informed accounts. Returns a score in
    roughly -1..1 and a description.
    """
    d = public.divergence
    if abs(d) < 0.05:
        return 0.0, "ticket and handle share are aligned"
    score = max(min(d / 0.25, 1.0), -1.0)
    if d > 0:
        return score, (
            f"{public.handle_pct:.0%} of dollars on only {public.ticket_pct:.0%} of "
            "tickets -- larger wagers are on this side"
        )
    return score, (
        f"only {public.handle_pct:.0%} of dollars on {public.ticket_pct:.0%} of "
        "tickets -- small-ticket money, larger wagers elsewhere"
    )


def find_stale_lines(
    market: Market, sharp_consensus_line: float | None, min_gap: float = 0.5
) -> list[tuple[str, str, float]]:
    """Books whose posted line trails the sharp number.

    Returns ``(book, outcome, gap_in_points)`` where a positive gap means the
    book is offering a better number than the sharp market. This is the
    highest-conviction, lowest-variance category the package produces,
    because it does not require the model to be right about anything.
    """
    if sharp_consensus_line is None:
        return []
    out: list[tuple[str, str, float]] = []
    for price in market.prices:
        if price.line is None:
            continue
        book = get_book(price.book)
        if book.is_sharp or not book.bettable:
            continue
        gap = price.line - sharp_consensus_line
        if gap >= min_gap:
            out.append((price.book, price.outcome, gap))
    return sorted(out, key=lambda t: -t[2])


def analyze(
    market: Market,
    history: LineHistory | None,
    outcome: str,
    public: PublicBetting | None = None,
    sharp_line_now: float | None = None,
) -> MovementRead:
    """Full movement read for one outcome."""
    read = MovementRead(outcome=outcome)

    current = [p for p in market.prices_for(outcome)]
    if current:
        sharp_now = [p for p in current if get_book(p.book).is_sharp]
        reference = max(sharp_now or current, key=lambda p: p.timestamp)
        read.current_line = reference.line
        read.current_american = reference.american

    if history is not None:
        snaps = history.series(market.event_id, market.market_type, outcome)
        if snaps:
            opener = history.opener(market.event_id, market.market_type, outcome)
            if opener:
                read.opening_line = opener.line
                read.opening_american = opener.american
            steam, direction = detect_steam(snaps)
            read.steam = steam
            read.steam_direction = direction
            if steam:
                read.notes.append(
                    "steam detected: multiple high-limit books moved together "
                    f"{'toward' if direction > 0 else 'away from'} {outcome}"
                )

    rlm, why = detect_reverse_line_movement(
        outcome, read.opening_line, read.current_line, public
    )
    read.reverse_line_movement = rlm
    if why:
        read.notes.append(why)

    read.stale_books = [
        (book, gap)
        for book, out, gap in find_stale_lines(market, sharp_line_now)
        if out == outcome
    ]
    if read.stale_books:
        best = read.stale_books[0]
        read.notes.append(
            f"{best[0]} is {best[1]:+.1f} points off the sharp number"
        )

    read.sharp_move_points = read.line_move
    return read


# ---------------------------------------------------------------------------
# Closing line value
# ---------------------------------------------------------------------------


def closing_line_value(bet_american: float, closing_american: float) -> float:
    """CLV as a fraction: how much better your price was than the close.

    Computed against the raw closing price. Positive means you got a number
    the market later agreed was too generous. Sustained positive CLV is the
    only thing that reliably precedes long-run profit, and a bettor with
    positive CLV and a losing season is doing better than one with the
    reverse.
    """
    ours = american_to_prob(bet_american)
    theirs = american_to_prob(closing_american)
    if theirs <= 0:
        return 0.0
    return (theirs - ours) / theirs


def clv_in_cents(bet_american: float, closing_american: float) -> float:
    """CLV expressed in American-odds cents, the way bettors talk about it."""
    return bet_american - closing_american if bet_american * closing_american > 0 else (
        bet_american - closing_american
    )


def no_vig_clv(
    bet_american: float, closing_prices: list[float], method: str = "shin"
) -> float:
    """CLV measured against the vig-free closing price.

    The honest version. Beating a -110 close by getting -105 is not really
    beating the market by five cents, because the -110 includes juice. Strip
    it first and the comparison is against what the market actually believed.
    """
    if len(closing_prices) < 2:
        return 0.0
    raw = [american_to_prob(a) for a in closing_prices]
    fair = devig(raw, method=method)
    fair_p = fair[0]
    ours = american_to_prob(bet_american)
    if fair_p <= 0:
        return 0.0
    return (fair_p - ours) / fair_p


def expected_roi_from_clv(mean_clv: float) -> float:
    """Translate an average CLV into a rough long-run ROI expectation.

    The relationship is close to one-to-one before vig. A bettor averaging
    2% CLV should expect low-single-digit ROI, and anyone projecting 15%
    from 2% CLV is fooling themselves.
    """
    return mean_clv * 0.92


def beat_close_rate(clv_values: list[float]) -> float:
    """Share of bets that beat the closing number."""
    if not clv_values:
        return 0.0
    return sum(1 for c in clv_values if c > 0) / len(clv_values)


def clv_significance(clv_values: list[float]) -> tuple[float, str]:
    """t-statistic on mean CLV, plus a plain-language verdict.

    CLV converges far faster than profit does, so a few hundred bets can
    already say something meaningful about whether an approach has an edge.
    """
    n = len(clv_values)
    if n < 2:
        return 0.0, "not enough bets to say anything"
    mean = sum(clv_values) / n
    var = sum((c - mean) ** 2 for c in clv_values) / (n - 1)
    if var <= 0:
        return 0.0, "no variance in CLV"
    t = mean / math.sqrt(var / n)
    if t > 2.5:
        verdict = "strong evidence of a real edge"
    elif t > 1.5:
        verdict = "suggestive but not yet conclusive"
    elif t > -1.5:
        verdict = "indistinguishable from no edge"
    else:
        verdict = "evidence of a negative edge -- the process is losing to the close"
    return t, verdict
