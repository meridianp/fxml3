-- Migration to add paper trading schema to TimescaleDB
-- This includes tables for portfolio snapshots, fills, and trades

-- Create the paper trading snapshots hypertable
CREATE TABLE IF NOT EXISTS paper_trading_snapshots (
    timestamp TIMESTAMPTZ NOT NULL,
    cash DOUBLE PRECISION NOT NULL,
    equity DOUBLE PRECISION NOT NULL,
    unrealized_pnl DOUBLE PRECISION NOT NULL,
    positions_count INTEGER NOT NULL,
    drawdown DOUBLE PRECISION NOT NULL,
    max_drawdown DOUBLE PRECISION NOT NULL
);

-- Convert to hypertable
SELECT create_hypertable('paper_trading_snapshots', 'timestamp', if_not_exists => TRUE);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_paper_trading_snapshots_timestamp ON paper_trading_snapshots (timestamp DESC);

-- Create the paper trading fills table
CREATE TABLE IF NOT EXISTS paper_trading_fills (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    fill_price DOUBLE PRECISION NOT NULL,
    commission DOUBLE PRECISION NOT NULL
);

-- Convert to hypertable
SELECT create_hypertable('paper_trading_fills', 'timestamp', if_not_exists => TRUE);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_paper_trading_fills_timestamp ON paper_trading_fills (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trading_fills_symbol ON paper_trading_fills (symbol, timestamp DESC);

-- Create the paper trading trades table (completed trades)
CREATE TABLE IF NOT EXISTS paper_trading_trades (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    exit_price DOUBLE PRECISION NOT NULL,
    size DOUBLE PRECISION NOT NULL,
    pnl DOUBLE PRECISION NOT NULL
);

-- Convert to hypertable
SELECT create_hypertable('paper_trading_trades', 'timestamp', if_not_exists => TRUE);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_paper_trading_trades_timestamp ON paper_trading_trades (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trading_trades_symbol ON paper_trading_trades (symbol, timestamp DESC);

-- Create continuous aggregate view for daily portfolio performance
CREATE MATERIALIZED VIEW IF NOT EXISTS paper_trading_daily_performance
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', timestamp) AS day,
    first(cash, timestamp) AS start_cash,
    last(cash, timestamp) AS end_cash,
    first(equity, timestamp) AS start_equity,
    last(equity, timestamp) AS end_equity,
    min(equity) AS min_equity,
    max(equity) AS max_equity,
    min(drawdown) AS max_daily_drawdown,
    last(max_drawdown, timestamp) AS max_overall_drawdown,
    count(*) AS snapshot_count
FROM paper_trading_snapshots
GROUP BY day;

-- Create continuous aggregate view for daily trading activity
CREATE MATERIALIZED VIEW IF NOT EXISTS paper_trading_daily_activity
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', timestamp) AS day,
    symbol,
    count(*) AS trade_count,
    sum(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
    sum(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) AS losing_trades,
    sum(pnl) AS total_pnl,
    avg(pnl) AS avg_pnl,
    sum(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) AS gross_profit,
    sum(CASE WHEN pnl <= 0 THEN pnl ELSE 0 END) AS gross_loss
FROM paper_trading_trades
GROUP BY day, symbol;

-- Create retention policy to remove data older than 90 days
SELECT add_retention_policy('paper_trading_snapshots', INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('paper_trading_fills', INTERVAL '90 days', if_not_exists => TRUE);

-- Keep trades data longer - 1 year
SELECT add_retention_policy('paper_trading_trades', INTERVAL '365 days', if_not_exists => TRUE);

-- Create compression policy (compress data older than 7 days)
SELECT add_compression_policy('paper_trading_snapshots', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('paper_trading_fills', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('paper_trading_trades', INTERVAL '30 days', if_not_exists => TRUE);
