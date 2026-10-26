"""
MarketScope Real Intraday Candlestick Archive
Stores verified closed exchange candles in SQLite with upsert semantics.
Never archives ungrounded or stale-reused data.
"""

from __future__ import annotations
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CANDLES_DB = os.environ.get(
    "MS_CANDLES_DB_PATH",
    str(Path(__file__).parent.parent / "work" / "runtime" / "candles.db"),
)


class CandleArchive:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_CANDLES_DB
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    timeframe INTEGER NOT NULL,
                    ts INTEGER NOT NULL,
                    o REAL NOT NULL,
                    h REAL NOT NULL,
                    l REAL NOT NULL,
                    c REAL NOT NULL,
                    v REAL NOT NULL,
                    source TEXT NOT NULL,
                    PRIMARY KEY (symbol, timeframe, ts)
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_ts 
                ON candles (symbol, timeframe, ts);
            """)

    def archive_closed_candles(
        self,
        symbol: str,
        timeframe: int,
        candles: List[Dict[str, Any]],
        source: str = "exchange",
    ) -> int:
        """
        Upserts verified closed candles.
        Silently skips open/forming candles (closed == False).
        """
        if not candles or not symbol:
            return 0

        rows = []
        for c in candles:
            if not c.get("closed", False):
                continue
            ts = c.get("t") or c.get("time")
            if ts is None:
                continue
            try:
                ts_int = int(ts)
            except (ValueError, TypeError):
                continue
            if ts_int <= 0:
                continue

            o = float(c.get("o", c.get("open", 0.0)))
            h = float(c.get("h", c.get("high", 0.0)))
            l = float(c.get("l", c.get("low", 0.0)))
            close_val = float(c.get("c", c.get("close", 0.0)))
            v = float(c.get("v", c.get("volume", 0.0)))

            rows.append((symbol.upper(), int(timeframe), ts_int, o, h, l, close_val, v, source))

        if not rows:
            return 0

        with self._get_connection() as conn:
            conn.executemany("""
                INSERT INTO candles (symbol, timeframe, ts, o, h, l, c, v, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe, ts) DO UPDATE SET
                    o = excluded.o,
                    h = excluded.h,
                    l = excluded.l,
                    c = excluded.c,
                    v = excluded.v,
                    source = excluded.source;
            """, rows)
            return len(rows)

    def get_prior_session_close(self, symbol: str, timeframe: int, before_ts: int) -> Optional[float]:
        """Returns the close of the most recent candle prior to before_ts (>= 2024-01-01)."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT c FROM candles
                WHERE symbol = ? AND timeframe = ? AND ts < ? AND ts >= 1704067200
                ORDER BY ts DESC LIMIT 1
            """, (symbol.upper(), int(timeframe), int(before_ts)))
            row = cur.fetchone()
            if row and row["c"] is not None:
                return float(row["c"])
            return None

    def get_stats(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT symbol, timeframe, count(*) as count, min(ts) as min_ts, max(ts) as max_ts
                FROM candles
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe;
            """)
            return [dict(r) for r in cur.fetchall()]

    def get_latest_session_date(self) -> Optional[str]:
        """Returns the latest session date (YYYY-MM-DD in IST) found in archived candles."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT max(ts) as max_ts FROM candles WHERE ts > 0")
            row = cur.fetchone()
            if not row or row["max_ts"] is None:
                return None
            try:
                from marketscope.market_schedule import IST
            except ImportError:
                from market_schedule import IST
            return datetime.fromtimestamp(row["max_ts"], IST).strftime("%Y-%m-%d")

    def get_candles_for_session(
        self,
        symbol: str,
        timeframe: int,
        session_date: str,
    ) -> List[Dict[str, Any]]:
        """Returns candles for a specific stock, timeframe, and session_date (YYYY-MM-DD in IST)."""
        try:
            from marketscope.market_schedule import IST
        except ImportError:
            from market_schedule import IST
        if not isinstance(session_date, str):
            return []
        try:
            target_date = datetime.strptime(session_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return []

        start_dt = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=IST)
        end_dt = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=IST)
        start_ts = max(int(start_dt.timestamp()), 1704067200)
        end_ts = int(end_dt.timestamp())

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT symbol, timeframe, ts, o, h, l, c, v, source
                FROM candles
                WHERE symbol = ? AND timeframe = ? AND ts BETWEEN ? AND ?
                ORDER BY ts ASC
                """,
                (symbol.upper(), int(timeframe), start_ts, end_ts),
            )
            rows = cur.fetchall()
            return [
                {
                    "t": r["ts"],
                    "o": r["o"],
                    "h": r["h"],
                    "l": r["l"],
                    "c": r["c"],
                    "v": int(r["v"]),
                    "closed": True,
                }
                for r in rows
            ]


_archive_instance: Optional[CandleArchive] = None

def get_candle_archive() -> CandleArchive:
    global _archive_instance
    if _archive_instance is None:
        _archive_instance = CandleArchive()
    return _archive_instance
