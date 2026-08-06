"""Bet ledger.

Every recommendation and every result, in SQLite. This is not bookkeeping,
it is the feedback loop -- without a record of what was bet at what price you
cannot compute closing line value, cannot check whether the probabilities are
calibrated, and cannot tell a broken model from a bad month.

The schema stores the model's *reasoning* alongside the bet: the fair
probability at the time, the EV claimed, and the closing price once it is
known. That triple is what makes a post-mortem possible.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..models import BetCandidate, BetStatus, utcnow
from ..oddsmath import american_to_decimal, american_to_prob


@dataclass
class LedgerEntry:
    id: int
    placed_at: datetime
    event_id: str
    event_name: str
    league: str
    market_type: str
    outcome: str
    line: float | None
    book: str
    american: float
    stake: float
    fair_probability: float
    model_probability: float
    ev: float
    confidence: str
    status: str
    profit: float | None
    closing_american: float | None
    rationale: str

    @property
    def decimal(self) -> float:
        return american_to_decimal(self.american)

    @property
    def clv(self) -> float | None:
        if self.closing_american is None:
            return None
        from ..market.movement import closing_line_value

        return closing_line_value(self.american, self.closing_american)


class Ledger:
    """Persistent record of bets."""

    def __init__(self, path: str | Path = "data/bets.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                placed_at TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                league TEXT NOT NULL,
                start_time TEXT,
                market_type TEXT NOT NULL,
                outcome TEXT NOT NULL,
                line REAL,
                book TEXT NOT NULL,
                american REAL NOT NULL,
                stake REAL NOT NULL,
                fair_probability REAL NOT NULL,
                model_probability REAL NOT NULL,
                ev REAL NOT NULL,
                confidence TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                profit REAL,
                closing_american REAL,
                settled_at TEXT,
                rationale TEXT,
                signals TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_bets_status ON bets(status);
            CREATE INDEX IF NOT EXISTS idx_bets_event ON bets(event_id);
            CREATE INDEX IF NOT EXISTS idx_bets_placed ON bets(placed_at);
            """
        )
        self.conn.commit()

    # -- writing ------------------------------------------------------------

    def record(self, bet: BetCandidate, placed_at: datetime | None = None) -> int:
        """Log a placed bet and return its ledger id."""
        placed_at = placed_at or utcnow()
        rationale = "; ".join(
            c.rationale for c in bet.signals if abs(c.effective) > 1e-4
        )
        signals_json = json.dumps(
            [
                {
                    "name": c.name,
                    "adjustment": round(c.logit_adjustment, 5),
                    "weight": round(c.weight, 4),
                    "rationale": c.rationale,
                    "points": c.points,
                }
                for c in bet.signals
            ]
        )
        cursor = self.conn.execute(
            """
            INSERT INTO bets (
                placed_at, event_id, event_name, league, start_time, market_type,
                outcome, line, book, american, stake, fair_probability,
                model_probability, ev, confidence, status, rationale, signals
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                placed_at.isoformat(),
                bet.event.event_id,
                bet.event.name,
                bet.event.league,
                bet.event.start_time.isoformat(),
                bet.market_type.value,
                bet.outcome,
                bet.line,
                bet.book,
                bet.american,
                bet.stake,
                bet.fair.probability,
                bet.model_probability,
                bet.ev,
                bet.confidence.value,
                BetStatus.PENDING.value,
                rationale,
                signals_json,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def record_slate(self, bets: list[BetCandidate], placed_at: datetime | None = None) -> list[int]:
        return [self.record(b, placed_at) for b in bets]

    def settle(self, bet_id: int, status: BetStatus, closing_american: float | None = None) -> float:
        """Grade a bet and return the realized profit."""
        row = self.conn.execute("SELECT * FROM bets WHERE id=?", (bet_id,)).fetchone()
        if row is None:
            raise KeyError(f"no bet with id {bet_id}")

        stake = row["stake"]
        decimal = american_to_decimal(row["american"])
        profit = {
            BetStatus.WON: stake * (decimal - 1.0),
            BetStatus.LOST: -stake,
            BetStatus.PUSHED: 0.0,
            BetStatus.VOIDED: 0.0,
        }.get(status, 0.0)

        self.conn.execute(
            "UPDATE bets SET status=?, profit=?, closing_american=COALESCE(?, closing_american),"
            " settled_at=? WHERE id=?",
            (status.value, profit, closing_american, utcnow().isoformat(), bet_id),
        )
        self.conn.commit()
        return profit

    def set_closing_price(self, bet_id: int, closing_american: float) -> None:
        """Attach the closing number, which is how CLV gets computed."""
        self.conn.execute(
            "UPDATE bets SET closing_american=? WHERE id=?", (closing_american, bet_id)
        )
        self.conn.commit()

    # -- reading ------------------------------------------------------------

    def pending(self) -> list[LedgerEntry]:
        return self._query("SELECT * FROM bets WHERE status='pending' ORDER BY start_time")

    def settled(self, limit: int | None = None) -> list[LedgerEntry]:
        sql = "SELECT * FROM bets WHERE status NOT IN ('pending') ORDER BY placed_at DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self._query(sql)

    def all(self) -> list[LedgerEntry]:
        return self._query("SELECT * FROM bets ORDER BY placed_at DESC")

    def _query(self, sql: str, params: tuple = ()) -> list[LedgerEntry]:
        return [_to_entry(r) for r in self.conn.execute(sql, params)]

    # -- summary ------------------------------------------------------------

    def summary(self) -> dict:
        """Headline performance numbers.

        Read the CLV line before the profit line. Over any realistic sample
        the profit figure is mostly noise and the CLV figure is mostly signal.
        """
        rows = self.settled()
        if not rows:
            return {
                "bets": 0,
                "staked": 0.0,
                "profit": 0.0,
                "roi": 0.0,
                "win_rate": 0.0,
                "clv_mean": None,
                "beat_close_rate": None,
            }

        graded = [r for r in rows if r.status in ("won", "lost")]
        staked = sum(r.stake for r in rows)
        profit = sum(r.profit or 0.0 for r in rows)
        wins = sum(1 for r in graded if r.status == "won")
        clvs = [r.clv for r in rows if r.clv is not None]

        return {
            "bets": len(rows),
            "staked": staked,
            "profit": profit,
            "roi": profit / staked if staked > 0 else 0.0,
            "win_rate": wins / len(graded) if graded else 0.0,
            "clv_mean": sum(clvs) / len(clvs) if clvs else None,
            "beat_close_rate": (
                sum(1 for c in clvs if c > 0) / len(clvs) if clvs else None
            ),
            "expected_profit": sum(r.stake * r.ev for r in rows),
        }

    def by_dimension(self, column: str) -> dict[str, dict]:
        """Break performance down by book, league, market, or confidence tier.

        The most useful view in the whole package. Edges are rarely uniform:
        a bettor is usually strong in one market and quietly bleeding in
        another, and the aggregate hides it.
        """
        allowed = {"book", "league", "market_type", "confidence"}
        if column not in allowed:
            raise ValueError(f"column must be one of {sorted(allowed)}")

        out: dict[str, dict] = {}
        for row in self.settled():
            key = getattr(row, "book" if column == "book" else column, "unknown")
            bucket = out.setdefault(
                key, {"bets": 0, "staked": 0.0, "profit": 0.0, "clv": []}
            )
            bucket["bets"] += 1
            bucket["staked"] += row.stake
            bucket["profit"] += row.profit or 0.0
            if row.clv is not None:
                bucket["clv"].append(row.clv)

        for bucket in out.values():
            bucket["roi"] = (
                bucket["profit"] / bucket["staked"] if bucket["staked"] > 0 else 0.0
            )
            clvs = bucket.pop("clv")
            bucket["clv_mean"] = sum(clvs) / len(clvs) if clvs else None
        return out

    def close(self) -> None:
        self.conn.close()


def _to_entry(row: sqlite3.Row) -> LedgerEntry:
    return LedgerEntry(
        id=row["id"],
        placed_at=_parse(row["placed_at"]),
        event_id=row["event_id"],
        event_name=row["event_name"],
        league=row["league"],
        market_type=row["market_type"],
        outcome=row["outcome"],
        line=row["line"],
        book=row["book"],
        american=row["american"],
        stake=row["stake"],
        fair_probability=row["fair_probability"],
        model_probability=row["model_probability"],
        ev=row["ev"],
        confidence=row["confidence"],
        status=row["status"],
        profit=row["profit"],
        closing_american=row["closing_american"],
        rationale=row["rationale"] or "",
    )


def _parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
