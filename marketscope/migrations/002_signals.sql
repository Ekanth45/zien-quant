-- MarketScope SQLite Schema 002_signals.sql
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe INTEGER NOT NULL,
    action TEXT NOT NULL,
    grade TEXT NOT NULL,
    score INTEGER NOT NULL,
    conviction INTEGER NOT NULL,
    price REAL NOT NULL,
    entry_low REAL,
    entry_high REAL,
    stop_loss REAL,
    target_1 REAL,
    target_2 REAL,
    rr REAL,
    rvol REAL,
    rsi REAL,
    vwap REAL,
    config_version INTEGER DEFAULT 1,
    outcome TEXT NOT NULL DEFAULT 'OPEN' CHECK(outcome IN ('OPEN', 'T1', 'T2', 'SL', 'EXPIRED')),
    outcome_at TEXT,
    outcome_price REAL,
    mfe_pct REAL DEFAULT 0.0,
    mae_pct REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf ON signals(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_signals_outcome ON signals(outcome);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
