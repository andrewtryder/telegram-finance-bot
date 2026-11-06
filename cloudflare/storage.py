"""D1 storage implementation for Cloudflare Workers."""


class D1Storage:
    def __init__(self, db):
        if not db:
            raise ValueError("D1 binding is required")
        self.db = db

    def _changes(self, result):
        if hasattr(result, "meta") and hasattr(result.meta, "changes"):
            return result.meta.changes
        if hasattr(result, "changes"):
            return result.changes
        if isinstance(result, dict):
            return result.get("meta", {}).get("changes", result.get("changes", 0))
        return 0

    def _results(self, result):
        if hasattr(result, "results"):
            return result.results
        if isinstance(result, dict):
            return result.get("results", [])
        return result or []

    async def watchlist(self, user_id: int):
        stmt = self.db.prepare("SELECT symbol FROM watchlist WHERE user_id=? ORDER BY created_at, symbol").bind(user_id)
        res = await stmt.all()
        rows = self._results(res)
        return [r["symbol"] if isinstance(r, dict) else r.symbol for r in rows]

    async def add_watchlist(self, user_id: int, symbol: str):
        stmt = self.db.prepare(
            "INSERT OR IGNORE INTO watchlist (user_id,symbol) "
            "SELECT ?,? WHERE (SELECT COUNT(*) FROM watchlist WHERE user_id=?) < 10"
        ).bind(user_id, symbol, user_id)
        res = await stmt.run()
        if self._changes(res):
            return True, f"Added {symbol} to your watchlist."

        check_stmt = self.db.prepare("SELECT symbol FROM watchlist WHERE user_id=? AND symbol=?").bind(user_id, symbol)
        existing = await check_stmt.first()
        if existing:
            return False, f"{symbol} is already on your watchlist."
        return False, "Watchlist is full (max 10)."

    async def remove_watchlist(self, user_id: int, symbol: str):
        stmt = self.db.prepare("DELETE FROM watchlist WHERE user_id=? AND symbol=?").bind(user_id, symbol)
        res = await stmt.run()
        if self._changes(res):
            return True, f"Removed {symbol} from your watchlist."
        return False, f"{symbol} was not on your watchlist."

    async def alerts(self, chat_id: int):
        stmt = self.db.prepare("SELECT id,symbol,direction,threshold FROM alerts WHERE chat_id=? ORDER BY id").bind(
            chat_id
        )
        res = await stmt.all()
        return self._results(res)

    async def add_alert(self, chat_id: int, user_id: int, symbol: str, direction: str, threshold: float):
        stmt = self.db.prepare(
            "INSERT INTO alerts (chat_id,user_id,symbol,direction,threshold) "
            "SELECT ?,?,?,?,? WHERE (SELECT COUNT(*) FROM alerts WHERE chat_id=?) < 20 RETURNING id"
        ).bind(chat_id, user_id, symbol, direction, threshold, chat_id)
        row = await stmt.first()
        if not row:
            return False, "Alert limit reached (max 20)."
        alert_id = row["id"] if isinstance(row, dict) else getattr(row, "id", row)
        return True, f"Alert #{alert_id}: {symbol} {direction} {threshold}"

    async def remove_alert(self, chat_id: int, alert_id: int):
        stmt = self.db.prepare("DELETE FROM alerts WHERE chat_id=? AND id=?").bind(chat_id, alert_id)
        res = await stmt.run()
        if self._changes(res):
            return True, f"Removed alert #{alert_id}."
        return False, f"Alert #{alert_id} not found."

    async def all_alerts(self):
        stmt = self.db.prepare("SELECT id,chat_id,user_id,symbol,direction,threshold FROM alerts ORDER BY id")
        res = await stmt.all()
        return self._results(res)

    async def claim_alert(self, alert_id: int):
        stmt = self.db.prepare(
            "UPDATE alerts SET claimed_until=unixepoch()+120 "
            "WHERE id=? AND (claimed_until IS NULL OR claimed_until<unixepoch()) RETURNING id"
        ).bind(alert_id)
        return await stmt.first()

    async def finish_alert(self, alert_id: int):
        stmt = self.db.prepare("DELETE FROM alerts WHERE id=?").bind(alert_id)
        await stmt.run()

    async def release_alert(self, alert_id: int):
        stmt = self.db.prepare("UPDATE alerts SET claimed_until=NULL WHERE id=?").bind(alert_id)
        await stmt.run()

    async def claim_update(self, update_id: int) -> bool:
        """Atomically record update_id if not already processed. Returns True if new, False if duplicate."""
        stmt = self.db.prepare("INSERT OR IGNORE INTO processed_updates (update_id) VALUES (?)").bind(update_id)
        res = await stmt.run()
        return bool(self._changes(res))
