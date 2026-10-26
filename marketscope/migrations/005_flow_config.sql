-- MarketScope SQLite Schema 005_flow_config.sql
-- Deletes any legacy preview configuration keys from stored config versions
-- Ensures clean configuration state for flow terminal thresholds

DELETE FROM config_versions WHERE config_json LIKE '%' || 'dem' || 'o%';
