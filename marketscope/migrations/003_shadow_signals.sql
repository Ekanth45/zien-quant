-- MarketScope SQLite Schema 003_shadow_signals.sql
-- Adds shadow logging columns for gated setups (R:R < 1.5)
ALTER TABLE signals ADD COLUMN gated INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN gate_reason TEXT;
ALTER TABLE signals ADD COLUMN shadow_stop_loss REAL;
ALTER TABLE signals ADD COLUMN shadow_target_1 REAL;
ALTER TABLE signals ADD COLUMN shadow_target_2 REAL;
ALTER TABLE signals ADD COLUMN shadow_rr REAL;

CREATE INDEX IF NOT EXISTS idx_signals_gated ON signals(gated);
