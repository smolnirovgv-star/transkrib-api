-- Migration: create watchdog_alert_state table
-- Persists Watchdog alert state across Railway restarts.
-- Replaces the previous in-memory _alert_state dict in watchdog_alerts.py.

CREATE TABLE IF NOT EXISTS watchdog_alert_state (
    method         TEXT PRIMARY KEY,
    alerted        BOOLEAN      NOT NULL DEFAULT FALSE,
    last_alert_ts  TIMESTAMPTZ
);

-- Seed initial rows so upsert never hits empty-table edge cases
INSERT INTO watchdog_alert_state (method, alerted, last_alert_ts) VALUES
    ('yt_dlp',          FALSE, NULL),
    ('cobalt',          FALSE, NULL),
    ('rapidapi',        FALSE, NULL),
    ('supadata',        FALSE, NULL),
    ('telegram_direct', FALSE, NULL)
ON CONFLICT (method) DO NOTHING;
