-- Optional Tiger Data / TimescaleDB schema. The app continues with memory telemetry if unavailable.
CREATE TABLE IF NOT EXISTS telemetry (
    timestamp TIMESTAMPTZ NOT NULL,
    simulation_time DOUBLE PRECISION NOT NULL,
    driver_id TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    decision TEXT NOT NULL,
    order_ids TEXT[] NOT NULL DEFAULT '{}',
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    distance DOUBLE PRECISION NOT NULL,
    duration DOUBLE PRECISION NOT NULL,
    earnings DOUBLE PRECISION NOT NULL,
    traffic DOUBLE PRECISION NOT NULL,
    weather DOUBLE PRECISION NOT NULL,
    temperature DOUBLE PRECISION NOT NULL,
    surge DOUBLE PRECISION NOT NULL,
    late_orders INTEGER NOT NULL
);

-- Run only when TimescaleDB is installed:
-- SELECT create_hypertable('telemetry', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS telemetry_driver_time_idx ON telemetry (driver_id, timestamp DESC);

CREATE OR REPLACE VIEW driver_metric_rollup AS
SELECT driver_id, agent_type, max(timestamp) AS last_timestamp,
       max(earnings) AS gross_earnings_mxn, max(distance) AS distance_km,
       max(late_orders) AS late_orders
FROM telemetry
GROUP BY driver_id, agent_type;

