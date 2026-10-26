-- MarketScope SQLite Schema 004_session_snapshots.sql
-- Adds session_snapshots table for immutable completed historical session data
-- Cleans any legacy preview configuration from stored config versions

CREATE TABLE IF NOT EXISTS session_snapshots (
    session_date TEXT NOT NULL,
    timeframe INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    complete INTEGER NOT NULL,
    data_source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_date, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_session_snapshots_lookup ON session_snapshots (session_date, timeframe);
