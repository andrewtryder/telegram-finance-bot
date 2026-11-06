CREATE TABLE IF NOT EXISTS watchlist (
  user_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  created_at REAL NOT NULL DEFAULT (strftime('%s','now')),
  PRIMARY KEY (user_id, symbol)
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('above', 'below')),
  threshold REAL NOT NULL,
  created_at REAL NOT NULL DEFAULT (strftime('%s','now')),
  claimed_until REAL
);
CREATE INDEX IF NOT EXISTS idx_alerts_chat ON alerts(chat_id);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol);
