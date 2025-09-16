-- FXML4 Trading System Database Schema
-- TimescaleDB initialization script

-- Create extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create schema
CREATE SCHEMA IF NOT EXISTS trading;

-- Set search path
SET search_path TO trading, public;

-- Symbols table
CREATE TABLE IF NOT EXISTS symbols (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    base_currency VARCHAR(3) NOT NULL,
    quote_currency VARCHAR(3) NOT NULL,
    pip_size DECIMAL(10,5) NOT NULL,
    min_tick_size DECIMAL(10,5) NOT NULL,
    contract_size INTEGER DEFAULT 100000,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Market data table (hypertable)
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open DECIMAL(20,5) NOT NULL,
    high DECIMAL(20,5) NOT NULL,
    low DECIMAL(20,5) NOT NULL,
    close DECIMAL(20,5) NOT NULL,
    volume BIGINT DEFAULT 0,
    tick_count INTEGER DEFAULT 0,
    vwap DECIMAL(20,5),
    spread DECIMAL(10,5),
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

-- Create hypertable for market data
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX idx_market_data_symbol_time ON market_data (symbol, time DESC);

-- Set compression policy (compress data older than 7 days)
SELECT add_compression_policy('market_data', INTERVAL '7 days', if_not_exists => TRUE);

-- Technical indicators table (hypertable)
CREATE TABLE IF NOT EXISTS indicators (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    rsi_14 DECIMAL(10,2),
    atr_14 DECIMAL(20,5),
    sma_20 DECIMAL(20,5),
    sma_50 DECIMAL(20,5),
    sma_200 DECIMAL(20,5),
    ema_9 DECIMAL(20,5),
    ema_21 DECIMAL(20,5),
    bb_upper DECIMAL(20,5),
    bb_middle DECIMAL(20,5),
    bb_lower DECIMAL(20,5),
    macd_line DECIMAL(20,5),
    macd_signal DECIMAL(20,5),
    macd_histogram DECIMAL(20,5),
    adx DECIMAL(10,2),
    plus_di DECIMAL(10,2),
    minus_di DECIMAL(10,2),
    stoch_k DECIMAL(10,2),
    stoch_d DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

-- Create hypertable for indicators
SELECT create_hypertable('indicators', 'time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX idx_indicators_symbol_timeframe_time ON indicators (symbol, timeframe, time DESC);

-- ML signals table
CREATE TABLE IF NOT EXISTS ml_signals (
    id SERIAL PRIMARY KEY,
    signal_time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50),
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('BUY', 'SELL', 'NEUTRAL')),
    confidence DECIMAL(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    features JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

-- Create index
CREATE INDEX idx_ml_signals_symbol_time ON ml_signals (symbol, signal_time DESC);

-- Elliott Wave patterns table
CREATE TABLE IF NOT EXISTS elliott_patterns (
    id SERIAL PRIMARY KEY,
    detection_time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,
    wave_degree VARCHAR(20),
    current_wave VARCHAR(10),
    confidence DECIMAL(5,4) NOT NULL,
    entry_price DECIMAL(20,5),
    target_prices DECIMAL(20,5)[],
    stop_loss DECIMAL(20,5),
    pattern_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

-- LLM validations table
CREATE TABLE IF NOT EXISTS llm_validations (
    id SERIAL PRIMARY KEY,
    validation_time TIMESTAMPTZ NOT NULL,
    signal_id INTEGER,
    pattern_id INTEGER,
    symbol VARCHAR(10) NOT NULL,
    llm_model VARCHAR(50) NOT NULL,
    validation_type VARCHAR(50) NOT NULL,
    chart_image_url TEXT,
    llm_confidence DECIMAL(5,4),
    timeframe_alignment DECIMAL(5,4),
    pattern_clarity DECIMAL(5,4),
    enhanced_confidence DECIMAL(5,4),
    visual_patterns TEXT[],
    key_observations TEXT[],
    concerns TEXT[],
    recommendation VARCHAR(20),
    response_data JSONB,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

-- Trading signals table (combined signals ready for execution)
CREATE TABLE IF NOT EXISTS trading_signals (
    id SERIAL PRIMARY KEY,
    signal_time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    signal_type VARCHAR(50) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    ml_confidence DECIMAL(5,4),
    ew_confidence DECIMAL(5,4),
    llm_confidence DECIMAL(5,4),
    entry_price DECIMAL(20,5) NOT NULL,
    stop_loss DECIMAL(20,5) NOT NULL,
    take_profit_1 DECIMAL(20,5),
    take_profit_2 DECIMAL(20,5),
    take_profit_3 DECIMAL(20,5),
    risk_reward_ratio DECIMAL(10,2),
    position_size_percent DECIMAL(5,2),
    metadata JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

-- Create index
CREATE INDEX idx_trading_signals_status_time ON trading_signals (status, signal_time DESC);

-- Trades table
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES trading_signals(id),
    symbol VARCHAR(10) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    entry_price DECIMAL(20,5) NOT NULL,
    position_size DECIMAL(20,8) NOT NULL,
    leverage INTEGER DEFAULT 1,
    exit_time TIMESTAMPTZ,
    exit_price DECIMAL(20,5),
    stop_loss DECIMAL(20,5),
    take_profit DECIMAL(20,5),
    trailing_stop_active BOOLEAN DEFAULT false,
    trailing_stop_distance DECIMAL(20,5),
    commission DECIMAL(20,8),
    swap DECIMAL(20,8),
    gross_pnl DECIMAL(20,8),
    net_pnl DECIMAL(20,8),
    pnl_percent DECIMAL(10,4),
    status VARCHAR(20) DEFAULT 'open',
    close_reason VARCHAR(50),
    ib_order_id INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

-- Create indexes
CREATE INDEX idx_trades_status ON trades (status);
CREATE INDEX idx_trades_entry_time ON trades (entry_time DESC);

-- Account balance history
CREATE TABLE IF NOT EXISTS account_balance (
    time TIMESTAMPTZ NOT NULL,
    balance DECIMAL(20,8) NOT NULL,
    equity DECIMAL(20,8) NOT NULL,
    margin_used DECIMAL(20,8) DEFAULT 0,
    margin_free DECIMAL(20,8) NOT NULL,
    unrealized_pnl DECIMAL(20,8) DEFAULT 0,
    realized_pnl DECIMAL(20,8) DEFAULT 0,
    open_positions INTEGER DEFAULT 0,
    metadata JSONB
);

-- Create hypertable
SELECT create_hypertable('account_balance', 'time', if_not_exists => TRUE);

-- Performance metrics table
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(20) NOT NULL, -- daily, weekly, monthly
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2),
    avg_win DECIMAL(20,8),
    avg_loss DECIMAL(20,8),
    profit_factor DECIMAL(10,2),
    sharpe_ratio DECIMAL(10,4),
    max_drawdown_percent DECIMAL(10,4),
    total_pnl DECIMAL(20,8),
    total_commission DECIMAL(20,8),
    net_pnl DECIMAL(20,8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System events table for monitoring
CREATE TABLE IF NOT EXISTS system_events (
    id SERIAL PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL,
    service_name VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- info, warning, error, critical
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index
CREATE INDEX idx_system_events_service_time ON system_events (service_name, event_time DESC);

-- Insert default symbols
INSERT INTO symbols (symbol, base_currency, quote_currency, pip_size, min_tick_size) VALUES
    ('EURUSD', 'EUR', 'USD', 0.0001, 0.00001),
    ('GBPUSD', 'GBP', 'USD', 0.0001, 0.00001),
    ('USDJPY', 'USD', 'JPY', 0.01, 0.001),
    ('USDCHF', 'USD', 'CHF', 0.0001, 0.00001),
    ('AUDUSD', 'AUD', 'USD', 0.0001, 0.00001),
    ('USDCAD', 'USD', 'CAD', 0.0001, 0.00001),
    ('NZDUSD', 'NZD', 'USD', 0.0001, 0.00001)
ON CONFLICT (symbol) DO NOTHING;

-- Create continuous aggregates for different timeframes
-- 1-minute aggregate
CREATE MATERIALIZED VIEW market_data_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    symbol,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume,
    SUM(tick_count) as tick_count,
    AVG(spread) as avg_spread
FROM market_data
GROUP BY bucket, symbol
WITH NO DATA;

-- 5-minute aggregate
CREATE MATERIALIZED VIEW market_data_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    symbol,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume,
    SUM(tick_count) as tick_count,
    AVG(spread) as avg_spread
FROM market_data
GROUP BY bucket, symbol
WITH NO DATA;

-- 15-minute aggregate
CREATE MATERIALIZED VIEW market_data_15m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('15 minutes', time) AS bucket,
    symbol,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume,
    SUM(tick_count) as tick_count,
    AVG(spread) as avg_spread
FROM market_data
GROUP BY bucket, symbol
WITH NO DATA;

-- 1-hour aggregate
CREATE MATERIALIZED VIEW market_data_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    symbol,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume,
    SUM(tick_count) as tick_count,
    AVG(spread) as avg_spread
FROM market_data
GROUP BY bucket, symbol
WITH NO DATA;

-- 4-hour aggregate
CREATE MATERIALIZED VIEW market_data_4h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('4 hours', time) AS bucket,
    symbol,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume,
    SUM(tick_count) as tick_count,
    AVG(spread) as avg_spread
FROM market_data
GROUP BY bucket, symbol
WITH NO DATA;

-- Add refresh policies for continuous aggregates
SELECT add_continuous_aggregate_policy('market_data_1m',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('market_data_5m',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('market_data_15m',
    start_offset => INTERVAL '4 hours',
    end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('market_data_1h',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('market_data_4h',
    start_offset => INTERVAL '2 days',
    end_offset => INTERVAL '4 hours',
    schedule_interval => INTERVAL '4 hours',
    if_not_exists => TRUE);

-- Create retention policy (keep raw data for 1 year)
SELECT add_retention_policy('market_data', INTERVAL '1 year', if_not_exists => TRUE);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA trading TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA trading TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA trading TO postgres;
