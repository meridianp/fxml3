-- Create optimized get_ohlcv function for TimescaleDB
-- Performance target: <100ms for market data queries

CREATE OR REPLACE FUNCTION get_ohlcv(
    p_symbol TEXT,
    p_timeframe TEXT,
    p_start_time TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    p_end_time TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    p_limit INTEGER DEFAULT 1000
)
RETURNS TABLE (
    "time" TIMESTAMP WITH TIME ZONE,
    symbol TEXT,
    "open" NUMERIC,
    high NUMERIC,
    low NUMERIC,
    "close" NUMERIC,
    volume BIGINT,
    tick_count INTEGER
) AS $$
DECLARE
    v_interval INTERVAL;
    v_start_time TIMESTAMP WITH TIME ZONE;
    v_end_time TIMESTAMP WITH TIME ZONE;
BEGIN
    -- Set default time range if not provided
    v_end_time := COALESCE(p_end_time, NOW());
    v_start_time := COALESCE(p_start_time, v_end_time - INTERVAL '30 days');

    -- Convert timeframe to interval for aggregation
    v_interval := CASE p_timeframe
        WHEN '1m' THEN INTERVAL '1 minute'
        WHEN '5m' THEN INTERVAL '5 minutes'
        WHEN '15m' THEN INTERVAL '15 minutes'
        WHEN '30m' THEN INTERVAL '30 minutes'
        WHEN '1h' THEN INTERVAL '1 hour'
        WHEN '4h' THEN INTERVAL '4 hours'
        WHEN '1d' THEN INTERVAL '1 day'
        ELSE INTERVAL '1 hour'
    END;

    -- For 1-minute data, query directly from ticks/candles table
    IF p_timeframe = '1m' THEN
        RETURN QUERY
        SELECT
            time_bucket(v_interval, mdc.timestamp) as time,
            mdc.symbol::TEXT,
            first(mdc.open, mdc.timestamp) as open,
            max(mdc.high) as high,
            min(mdc.low) as low,
            last(mdc.close, mdc.timestamp) as close,
            sum(mdc.volume)::BIGINT as volume,
            sum(mdc.tick_count)::INTEGER as tick_count
        FROM market_data_candles mdc
        WHERE mdc.symbol = p_symbol
            AND mdc.timestamp >= v_start_time
            AND mdc.timestamp <= v_end_time
        GROUP BY time_bucket(v_interval, mdc.timestamp), mdc.symbol
        ORDER BY time DESC
        LIMIT p_limit;
    ELSE
        -- For higher timeframes, aggregate from 1-minute data
        RETURN QUERY
        SELECT
            time_bucket(v_interval, mdc.timestamp) as time,
            mdc.symbol::TEXT,
            first(mdc.open, mdc.timestamp) as open,
            max(mdc.high) as high,
            min(mdc.low) as low,
            last(mdc.close, mdc.timestamp) as close,
            sum(mdc.volume)::BIGINT as volume,
            sum(mdc.tick_count)::INTEGER as tick_count
        FROM market_data_candles mdc
        WHERE mdc.symbol = p_symbol
            AND mdc.timestamp >= v_start_time
            AND mdc.timestamp <= v_end_time
        GROUP BY time_bucket(v_interval, mdc.timestamp), mdc.symbol
        ORDER BY time DESC
        LIMIT p_limit;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create indexes for optimal performance
CREATE INDEX IF NOT EXISTS idx_market_data_candles_symbol_timestamp
ON market_data_candles (symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_market_data_candles_timestamp_symbol
ON market_data_candles (timestamp DESC, symbol);

-- Create continuous aggregates for common timeframes (if they don't exist)
DO $$
BEGIN
    -- 5-minute aggregate
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.continuous_aggregates
        WHERE view_name = 'market_data_5m'
    ) THEN
        CREATE MATERIALIZED VIEW market_data_5m
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('5 minutes', timestamp) as time,
            symbol,
            first(open, timestamp) as open,
            max(high) as high,
            min(low) as low,
            last(close, timestamp) as close,
            sum(volume) as volume,
            sum(tick_count) as tick_count
        FROM market_data_candles
        GROUP BY time, symbol;

        -- Add refresh policy
        SELECT add_continuous_aggregate_policy('market_data_5m',
            start_offset => INTERVAL '1 hour',
            end_offset => INTERVAL '1 minute',
            schedule_interval => INTERVAL '1 minute',
            if_not_exists => true);
    END IF;

    -- 1-hour aggregate
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.continuous_aggregates
        WHERE view_name = 'market_data_1h'
    ) THEN
        CREATE MATERIALIZED VIEW market_data_1h
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', timestamp) as time,
            symbol,
            first(open, timestamp) as open,
            max(high) as high,
            min(low) as low,
            last(close, timestamp) as close,
            sum(volume) as volume,
            sum(tick_count) as tick_count
        FROM market_data_candles
        GROUP BY time, symbol;

        -- Add refresh policy
        SELECT add_continuous_aggregate_policy('market_data_1h',
            start_offset => INTERVAL '2 hours',
            end_offset => INTERVAL '5 minutes',
            schedule_interval => INTERVAL '5 minutes',
            if_not_exists => true);
    END IF;

    -- 1-day aggregate
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.continuous_aggregates
        WHERE view_name = 'market_data_1d'
    ) THEN
        CREATE MATERIALIZED VIEW market_data_1d
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', timestamp) as time,
            symbol,
            first(open, timestamp) as open,
            max(high) as high,
            min(low) as low,
            last(close, timestamp) as close,
            sum(volume) as volume,
            sum(tick_count) as tick_count
        FROM market_data_candles
        GROUP BY time, symbol;

        -- Add refresh policy
        SELECT add_continuous_aggregate_policy('market_data_1d',
            start_offset => INTERVAL '1 day',
            end_offset => INTERVAL '10 minutes',
            schedule_interval => INTERVAL '10 minutes',
            if_not_exists => true);
    END IF;
END $$;

-- Grant necessary permissions
GRANT EXECUTE ON FUNCTION get_ohlcv TO postgres;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO postgres;

-- Analyze tables for optimal query planning
ANALYZE market_data_candles;
ANALYZE market_data_ticks;

COMMENT ON FUNCTION get_ohlcv IS 'Optimized OHLCV data retrieval function with <100ms target performance';
