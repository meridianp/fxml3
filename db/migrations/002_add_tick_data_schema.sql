-- FXML4 Migration: Add Tick Data Schema and Enhanced OHLCV Tables

-- Enable TimescaleDB extension if not already enabled
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create tick_data table to store raw tick data
CREATE TABLE IF NOT EXISTS tick_data (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    size INTEGER,
    tick_type TEXT NOT NULL,  -- 'bid', 'ask', 'trade', etc.
    source TEXT NOT NULL,     -- 'ib', 'alpha_vantage', etc.

    PRIMARY KEY (time, symbol, tick_type)
);

-- Convert tick_data to hypertable
SELECT create_hypertable('tick_data', 'time', if_not_exists => TRUE);

-- Create table for storing 1-minute candles (market_data_1m)
CREATE TABLE IF NOT EXISTS market_data_1m (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume INTEGER NOT NULL,
    tick_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,     -- 'ib', 'alpha_vantage', 'calculated', etc.

    PRIMARY KEY (time, symbol)
);

-- Convert market_data_1m to hypertable
SELECT create_hypertable('market_data_1m', 'time', if_not_exists => TRUE);

-- Set compression policy for tick_data (compress after 1 day)
ALTER TABLE tick_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, tick_type'
);

SELECT add_compression_policy('tick_data', INTERVAL '1 day');

-- Set compression policy for market_data_1m (compress after 7 days)
ALTER TABLE market_data_1m SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

SELECT add_compression_policy('market_data_1m', INTERVAL '7 days');

-- Create retention policies
-- Keep tick data for 30 days (to save space)
SELECT add_retention_policy('tick_data', INTERVAL '30 days');

-- Keep 1-minute data for 2 years
SELECT add_retention_policy('market_data_1m', INTERVAL '2 years');

-- Create continuous aggregates for higher timeframes

-- 5-minute candles
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    symbol,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(tick_count) AS tick_count,
    'calculated' AS source
FROM market_data_1m
GROUP BY bucket, symbol;

-- 15-minute candles
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_15m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('15 minutes', time) AS bucket,
    symbol,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(tick_count) AS tick_count,
    'calculated' AS source
FROM market_data_1m
GROUP BY bucket, symbol;

-- 30-minute candles
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_30m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('30 minutes', time) AS bucket,
    symbol,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(tick_count) AS tick_count,
    'calculated' AS source
FROM market_data_1m
GROUP BY bucket, symbol;

-- 1-hour candles
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    symbol,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(tick_count) AS tick_count,
    'calculated' AS source
FROM market_data_1m
GROUP BY bucket, symbol;

-- 4-hour candles
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_4h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('4 hours', time) AS bucket,
    symbol,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(tick_count) AS tick_count,
    'calculated' AS source
FROM market_data_1m
GROUP BY bucket, symbol;

-- Daily candles
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_1d
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    symbol,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    sum(tick_count) AS tick_count,
    'calculated' AS source
FROM market_data_1m
GROUP BY bucket, symbol;

-- Create refresh policies for continuous aggregates
SELECT add_continuous_aggregate_policy('market_data_5m',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes');

SELECT add_continuous_aggregate_policy('market_data_15m',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes');

SELECT add_continuous_aggregate_policy('market_data_30m',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '30 minutes',
    schedule_interval => INTERVAL '30 minutes');

SELECT add_continuous_aggregate_policy('market_data_1h',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

SELECT add_continuous_aggregate_policy('market_data_4h',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '4 hours',
    schedule_interval => INTERVAL '4 hours');

SELECT add_continuous_aggregate_policy('market_data_1d',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- Create indexes for faster queries

-- Index on symbol for tick_data
CREATE INDEX IF NOT EXISTS idx_tick_data_symbol ON tick_data (symbol, tick_type);

-- Index on symbol for market_data_1m
CREATE INDEX IF NOT EXISTS idx_market_data_1m_symbol ON market_data_1m (symbol);

-- Create functions for common operations

-- Function to get the latest tick price for a symbol
CREATE OR REPLACE FUNCTION get_latest_tick(
    p_symbol TEXT,
    p_tick_type TEXT DEFAULT 'trade'
) RETURNS TABLE (
    time TIMESTAMPTZ,
    price DOUBLE PRECISION,
    size INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT td.time, td.price, td.size
    FROM tick_data td
    WHERE td.symbol = p_symbol AND td.tick_type = p_tick_type
    ORDER BY td.time DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to get OHLCV data for a specific timeframe
CREATE OR REPLACE FUNCTION get_ohlcv(
    p_symbol TEXT,
    p_timeframe TEXT,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ
) RETURNS TABLE (
    time TIMESTAMPTZ,
    symbol TEXT,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume INTEGER,
    tick_count INTEGER
) AS $$
BEGIN
    IF p_timeframe = '1m' THEN
        RETURN QUERY
        SELECT md.time, md.symbol, md.open, md.high, md.low, md.close, md.volume, md.tick_count
        FROM market_data_1m md
        WHERE md.symbol = p_symbol
        AND md.time BETWEEN p_start_time AND p_end_time
        ORDER BY md.time;
    ELSIF p_timeframe = '5m' THEN
        RETURN QUERY
        SELECT md.bucket as time, md.symbol, md.open, md.high, md.low, md.close, md.volume, md.tick_count
        FROM market_data_5m md
        WHERE md.symbol = p_symbol
        AND md.bucket BETWEEN p_start_time AND p_end_time
        ORDER BY md.bucket;
    ELSIF p_timeframe = '15m' THEN
        RETURN QUERY
        SELECT md.bucket as time, md.symbol, md.open, md.high, md.low, md.close, md.volume, md.tick_count
        FROM market_data_15m md
        WHERE md.symbol = p_symbol
        AND md.bucket BETWEEN p_start_time AND p_end_time
        ORDER BY md.bucket;
    ELSIF p_timeframe = '30m' THEN
        RETURN QUERY
        SELECT md.bucket as time, md.symbol, md.open, md.high, md.low, md.close, md.volume, md.tick_count
        FROM market_data_30m md
        WHERE md.symbol = p_symbol
        AND md.bucket BETWEEN p_start_time AND p_end_time
        ORDER BY md.bucket;
    ELSIF p_timeframe = '1h' THEN
        RETURN QUERY
        SELECT md.bucket as time, md.symbol, md.open, md.high, md.low, md.close, md.volume, md.tick_count
        FROM market_data_1h md
        WHERE md.symbol = p_symbol
        AND md.bucket BETWEEN p_start_time AND p_end_time
        ORDER BY md.bucket;
    ELSIF p_timeframe = '4h' THEN
        RETURN QUERY
        SELECT md.bucket as time, md.symbol, md.open, md.high, md.low, md.close, md.volume, md.tick_count
        FROM market_data_4h md
        WHERE md.symbol = p_symbol
        AND md.bucket BETWEEN p_start_time AND p_end_time
        ORDER BY md.bucket;
    ELSIF p_timeframe = '1d' THEN
        RETURN QUERY
        SELECT md.bucket as time, md.symbol, md.open, md.high, md.low, md.close, md.volume, md.tick_count
        FROM market_data_1d md
        WHERE md.symbol = p_symbol
        AND md.bucket BETWEEN p_start_time AND p_end_time
        ORDER BY md.bucket;
    ELSE
        RAISE EXCEPTION 'Invalid timeframe: %', p_timeframe;
    END IF;
END;
$$ LANGUAGE plpgsql;
