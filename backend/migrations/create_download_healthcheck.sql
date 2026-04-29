CREATE TABLE IF NOT EXISTS download_healthcheck (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    method TEXT NOT NULL CHECK (method IN ('yt_dlp', 'rapidapi', 'cobalt', 'supadata', 'telegram_direct')),
    ok BOOLEAN NOT NULL,
    latency_ms INTEGER,
    bytes_downloaded BIGINT,
    error_message TEXT,
    test_source TEXT NOT NULL DEFAULT 'scheduler'
);
CREATE INDEX IF NOT EXISTS idx_healthcheck_ts ON download_healthcheck (ts DESC);
CREATE INDEX IF NOT EXISTS idx_healthcheck_method_ts ON download_healthcheck (method, ts DESC);
