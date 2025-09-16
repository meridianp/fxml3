-- FXML4 Migration: Add data quality assessment schema
-- This file creates tables and views for storing data quality metrics

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create data_quality_metrics hypertable for storing quality assessment results
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    time TIMESTAMPTZ NOT NULL,
    pair TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    completeness_score DOUBLE PRECISION NOT NULL,
    price_spikes_score DOUBLE PRECISION NOT NULL,
    price_freezes_score DOUBLE PRECISION NOT NULL,
    ohlc_integrity_score DOUBLE PRECISION NOT NULL,
    volatility_score DOUBLE PRECISION NOT NULL,
    overall_score DOUBLE PRECISION NOT NULL,
    completeness_pct DOUBLE PRECISION NOT NULL,
    data_points INTEGER NOT NULL,
    expected_points INTEGER NOT NULL,
    gap_count INTEGER NOT NULL,
    max_gap_duration DOUBLE PRECISION,
    spike_count INTEGER NOT NULL,
    max_spike_pct DOUBLE PRECISION,
    freeze_count INTEGER NOT NULL,
    longest_freeze INTEGER,
    anomaly_count INTEGER NOT NULL,
    anomaly_details JSONB,
    avg_volatility DOUBLE PRECISION,
    low_volatility_periods INTEGER,
    details JSONB,

    PRIMARY KEY (time, pair, timeframe)
);

-- Check if TimescaleDB extension is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        -- Convert to hypertable
        PERFORM create_hypertable('data_quality_metrics', 'time', if_not_exists => TRUE);

        -- Set compression policy
        ALTER TABLE data_quality_metrics SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'pair, timeframe'
        );

        -- Add compression policy (compress data older than 7 days)
        SELECT add_compression_policy('data_quality_metrics', INTERVAL '7 days');

        -- Add retention policy (keep data for 2 years by default)
        -- Uncomment for production use
        -- SELECT add_retention_policy('data_quality_metrics', INTERVAL '2 years');

        -- Create indexes for faster queries
        CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_pair ON data_quality_metrics (pair, time DESC);
        CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_timeframe ON data_quality_metrics (timeframe, time DESC);
        CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_overall_score ON data_quality_metrics (overall_score);

        -- Create materialized view for daily quality summary
        CREATE MATERIALIZED VIEW IF NOT EXISTS data_quality_daily_summary
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', time) AS day,
            pair,
            timeframe,
            avg(overall_score) AS avg_overall_score,
            min(overall_score) AS min_overall_score,
            max(overall_score) AS max_overall_score,
            avg(completeness_score) AS avg_completeness_score,
            avg(price_spikes_score) AS avg_price_spikes_score,
            avg(price_freezes_score) AS avg_price_freezes_score,
            avg(ohlc_integrity_score) AS avg_ohlc_integrity_score,
            avg(volatility_score) AS avg_volatility_score,
            sum(gap_count) AS total_gaps,
            sum(spike_count) AS total_spikes,
            sum(freeze_count) AS total_freezes,
            sum(anomaly_count) AS total_anomalies,
            count(*) AS assessment_count
        FROM data_quality_metrics
        GROUP BY day, pair, timeframe;

        -- Add refresh policy for the materialized view (refresh daily)
        SELECT add_continuous_aggregate_policy('data_quality_daily_summary',
            start_offset => INTERVAL '1 month',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day');
    END IF;
END
$$;

-- Create table to store quality assessment reports
CREATE TABLE IF NOT EXISTS data_quality_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    report_date DATE NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    pairs TEXT[] NOT NULL,
    timeframes TEXT[] NOT NULL,
    summary JSONB NOT NULL,
    report_markdown TEXT,
    report_json JSONB,
    visualization_path TEXT
);

-- Create index on report_date
CREATE INDEX IF NOT EXISTS idx_data_quality_reports_date ON data_quality_reports (report_date DESC);

-- Create function to get quality metrics for a specific pair and timeframe
CREATE OR REPLACE FUNCTION get_quality_metrics(
    p_pair TEXT,
    p_timeframe TEXT,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ
) RETURNS TABLE (
    time TIMESTAMPTZ,
    pair TEXT,
    timeframe TEXT,
    overall_score DOUBLE PRECISION,
    completeness_score DOUBLE PRECISION,
    price_spikes_score DOUBLE PRECISION,
    price_freezes_score DOUBLE PRECISION,
    ohlc_integrity_score DOUBLE PRECISION,
    volatility_score DOUBLE PRECISION,
    completeness_pct DOUBLE PRECISION,
    data_points INTEGER,
    expected_points INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        q.time,
        q.pair,
        q.timeframe,
        q.overall_score,
        q.completeness_score,
        q.price_spikes_score,
        q.price_freezes_score,
        q.ohlc_integrity_score,
        q.volatility_score,
        q.completeness_pct,
        q.data_points,
        q.expected_points
    FROM data_quality_metrics q
    WHERE q.pair = p_pair
    AND q.timeframe = p_timeframe
    AND q.time BETWEEN p_start_time AND p_end_time
    ORDER BY q.time;
END;
$$ LANGUAGE plpgsql;

-- Create function to get the quality trend over time
CREATE OR REPLACE FUNCTION get_quality_trend(
    p_pairs TEXT[],
    p_timeframe TEXT,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ
) RETURNS TABLE (
    day DATE,
    pair TEXT,
    avg_score DOUBLE PRECISION,
    min_score DOUBLE PRECISION,
    max_score DOUBLE PRECISION,
    assessment_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.day::DATE,
        s.pair,
        s.avg_overall_score,
        s.min_overall_score,
        s.max_overall_score,
        s.assessment_count
    FROM data_quality_daily_summary s
    WHERE s.pair = ANY(p_pairs)
    AND s.timeframe = p_timeframe
    AND s.day BETWEEN p_start_time AND p_end_time
    ORDER BY s.day, s.pair;
END;
$$ LANGUAGE plpgsql;

-- Create function to get recent quality issues
CREATE OR REPLACE FUNCTION get_recent_quality_issues(
    p_lookback_days INTEGER DEFAULT 7,
    p_min_score DOUBLE PRECISION DEFAULT 70.0
) RETURNS TABLE (
    time TIMESTAMPTZ,
    pair TEXT,
    timeframe TEXT,
    overall_score DOUBLE PRECISION,
    completeness_pct DOUBLE PRECISION,
    gap_count INTEGER,
    spike_count INTEGER,
    freeze_count INTEGER,
    anomaly_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        q.time,
        q.pair,
        q.timeframe,
        q.overall_score,
        q.completeness_pct,
        q.gap_count,
        q.spike_count,
        q.freeze_count,
        q.anomaly_count
    FROM data_quality_metrics q
    WHERE q.time > NOW() - make_interval(days => p_lookback_days)
    AND q.overall_score < p_min_score
    ORDER BY q.overall_score ASC, q.time DESC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;
