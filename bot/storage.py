"""SQLite persistence for watchlists and price alerts."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from bot.config import logger

_lock = threading.Lock()
_db_path: Path | None = None

MAX_WATCHLIST = 10
MAX_ALERTS = 20


def _connect() -> sqlite3.Connection:
    if _db_path is None:
        raise RuntimeError("Storage not initialized; call init_storage() first.")
    conn = sqlite3.connect(_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_storage() -> None:
    global _db_path
    from bot.config import DATA_DIR

    data_dir = Path(DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    _db_path = data_dir / "bot.db"

    with _lock:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS watchlist (
                    chat_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now')),
                    PRIMARY KEY (chat_id, symbol)
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL CHECK (direction IN ('above', 'below')),
                    threshold REAL NOT NULL,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                );
                CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol);
                CREATE INDEX IF NOT EXISTS idx_alerts_chat ON alerts(chat_id);
                """
            )
            conn.commit()
            logger.info(f"SQLite storage ready at {_db_path}")
        finally:
            conn.close()


def watchlist_list(chat_id: int) -> list[str]:
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT symbol FROM watchlist WHERE chat_id = ? ORDER BY created_at ASC",
                (chat_id,),
            ).fetchall()
            return [r["symbol"] for r in rows]
        finally:
            conn.close()


def watchlist_add(chat_id: int, symbol: str) -> tuple[bool, str]:
    symbol = symbol.upper()
    with _lock:
        conn = _connect()
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM watchlist WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()["c"]
            if count >= MAX_WATCHLIST:
                return False, f"Watchlist is full (max {MAX_WATCHLIST})."
            try:
                conn.execute(
                    "INSERT INTO watchlist (chat_id, symbol) VALUES (?, ?)",
                    (chat_id, symbol),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return False, f"{symbol} is already on your watchlist."
            return True, f"Added {symbol} to your watchlist."
        finally:
            conn.close()


def watchlist_remove(chat_id: int, symbol: str) -> tuple[bool, str]:
    symbol = symbol.upper()
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM watchlist WHERE chat_id = ? AND symbol = ?",
                (chat_id, symbol),
            )
            conn.commit()
            if cur.rowcount == 0:
                return False, f"{symbol} was not on your watchlist."
            return True, f"Removed {symbol} from your watchlist."
        finally:
            conn.close()


def alert_add(
    chat_id: int, user_id: int, symbol: str, direction: str, threshold: float
) -> tuple[bool, str, int | None]:
    symbol = symbol.upper()
    direction = direction.lower()
    if direction not in ("above", "below"):
        return False, "Direction must be above or below.", None
    with _lock:
        conn = _connect()
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM alerts WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()["c"]
            if count >= MAX_ALERTS:
                return False, f"Alert limit reached (max {MAX_ALERTS}).", None
            cur = conn.execute(
                "INSERT INTO alerts (chat_id, user_id, symbol, direction, threshold) VALUES (?, ?, ?, ?, ?)",
                (chat_id, user_id, symbol, direction, threshold),
            )
            conn.commit()
            return True, f"Alert #{cur.lastrowid}: {symbol} {direction} {threshold}", cur.lastrowid
        finally:
            conn.close()


def alert_list(chat_id: int) -> list[dict]:
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT id, symbol, direction, threshold FROM alerts WHERE chat_id = ? ORDER BY id ASC",
                (chat_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def alert_remove(chat_id: int, alert_id: int) -> tuple[bool, str]:
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM alerts WHERE chat_id = ? AND id = ?",
                (chat_id, alert_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return False, f"Alert #{alert_id} not found."
            return True, f"Removed alert #{alert_id}."
        finally:
            conn.close()


def alert_delete_by_id(alert_id: int) -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
            conn.commit()
        finally:
            conn.close()


def alerts_all() -> list[dict]:
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT id, chat_id, user_id, symbol, direction, threshold FROM alerts ORDER BY id ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
