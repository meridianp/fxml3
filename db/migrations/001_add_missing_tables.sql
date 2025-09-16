-- PHASE 1 GREEN: TDD Database Schema Fixes
-- This migration adds missing tables identified by our comprehensive tests
-- Adding tables: accounts, account_snapshots, market_data

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create accounts table (referenced by orders)
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_number TEXT NOT NULL UNIQUE,
    broker TEXT NOT NULL,
    account_type TEXT NOT NULL CHECK (account_type IN ('paper', 'live', 'demo')),
    base_currency TEXT NOT NULL DEFAULT 'USD',
    balance NUMERIC(15, 2) NOT NULL DEFAULT 0,
    equity NUMERIC(15, 2) NOT NULL DEFAULT 0,
    margin_used NUMERIC(15, 2) DEFAULT 0,
    margin_available NUMERIC(15, 2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create account_snapshots table (missing and referenced in order management)
CREATE TABLE IF NOT EXISTS account_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL,
    balance NUMERIC(15, 2) NOT NULL,
    equity NUMERIC(15, 2) NOT NULL,
    margin_used NUMERIC(15, 2),
    margin_available NUMERIC(15, 2),
    unrealized_pl NUMERIC(15, 2),
    snapshot_time TIMESTAMP WITH TIME ZONE NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- Create market_data table (standardized market data view)
CREATE TABLE IF NOT EXISTS market_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    open NUMERIC(12, 5) NOT NULL,
    high NUMERIC(12, 5) NOT NULL,
    low NUMERIC(12, 5) NOT NULL,
    close NUMERIC(12, 5) NOT NULL,
    volume BIGINT DEFAULT 0,
    timeframe TEXT NOT NULL CHECK (timeframe IN ('1m', '5m', '15m', '30m', '1h', '4h', '1d')),
    source TEXT NOT NULL DEFAULT 'unknown',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add missing foreign key constraints to existing tables
-- Add account_id foreign key to orders table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'orders_account_id_fkey'
    ) THEN
        -- First add the account_id column if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'orders' AND column_name = 'account_id'
        ) THEN
            ALTER TABLE orders ADD COLUMN account_id UUID;
        END IF;

        -- Add the foreign key constraint
        ALTER TABLE orders
        ADD CONSTRAINT orders_account_id_fkey
        FOREIGN KEY (account_id) REFERENCES accounts(id);
    END IF;
END $$;

-- Add account_id foreign key to positions table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'positions_account_id_fkey'
    ) THEN
        -- First add the account_id column if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'positions' AND column_name = 'account_id'
        ) THEN
            ALTER TABLE positions ADD COLUMN account_id UUID;
        END IF;

        -- Add the foreign key constraint
        ALTER TABLE positions
        ADD CONSTRAINT positions_account_id_fkey
        FOREIGN KEY (account_id) REFERENCES accounts(id);
    END IF;
END $$;

-- Add order_id foreign key to trades table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'trades_order_id_fkey'
    ) THEN
        -- First add the order_id column if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'trades' AND column_name = 'order_id'
        ) THEN
            ALTER TABLE trades ADD COLUMN order_id UUID;
        END IF;

        -- Add the foreign key constraint
        ALTER TABLE trades
        ADD CONSTRAINT trades_order_id_fkey
        FOREIGN KEY (order_id) REFERENCES orders(id);
    END IF;
END $$;

-- Create required indexes for performance
CREATE INDEX IF NOT EXISTS idx_orders_account_id ON orders(account_id);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);

CREATE INDEX IF NOT EXISTS idx_positions_account_id ON positions(account_id);
CREATE INDEX IF NOT EXISTS idx_trades_order_id ON trades(order_id);

CREATE INDEX IF NOT EXISTS idx_account_snapshots_account_id ON account_snapshots(account_id);
CREATE INDEX IF NOT EXISTS idx_account_snapshots_time ON account_snapshots(snapshot_time);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_market_data_timeframe ON market_data(timeframe);

-- Add missing constraints for positive quantities
DO $$
BEGIN
    -- Add quantity > 0 constraint to orders if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints cc
        JOIN information_schema.constraint_column_usage ccu
          ON cc.constraint_name = ccu.constraint_name
        WHERE ccu.table_name = 'orders'
          AND ccu.column_name = 'quantity'
          AND cc.check_clause LIKE '%> 0%'
    ) THEN
        ALTER TABLE orders ADD CONSTRAINT orders_quantity_positive CHECK (quantity > 0);
    END IF;

    -- Add quantity > 0 constraint to trades if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints cc
        JOIN information_schema.constraint_column_usage ccu
          ON cc.constraint_name = ccu.constraint_name
        WHERE ccu.table_name = 'trades'
          AND ccu.column_name = 'quantity'
          AND cc.check_clause LIKE '%> 0%'
    ) THEN
        -- First add quantity column to trades if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'trades' AND column_name = 'quantity'
        ) THEN
            ALTER TABLE trades ADD COLUMN quantity NUMERIC NOT NULL DEFAULT 0;
        END IF;

        ALTER TABLE trades ADD CONSTRAINT trades_quantity_positive CHECK (quantity > 0);
    END IF;

    -- Add quantity > 0 constraint to positions if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints cc
        JOIN information_schema.constraint_column_usage ccu
          ON cc.constraint_name = ccu.constraint_name
        WHERE ccu.table_name = 'positions'
          AND ccu.column_name = 'quantity'
          AND cc.check_clause LIKE '%> 0%'
    ) THEN
        -- First add quantity column to positions if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'positions' AND column_name = 'quantity'
        ) THEN
            ALTER TABLE positions ADD COLUMN quantity NUMERIC NOT NULL DEFAULT 0;
        END IF;

        ALTER TABLE positions ADD CONSTRAINT positions_quantity_positive CHECK (quantity > 0);
    END IF;
END $$;

-- Insert a default account for testing
INSERT INTO accounts (account_number, broker, account_type, base_currency, balance, equity)
VALUES ('DEFAULT_TEST_001', 'test_broker', 'paper', 'USD', 10000.00, 10000.00)
ON CONFLICT (account_number) DO NOTHING;

-- Create TimescaleDB hypertables if TimescaleDB extension is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        -- Convert market_data to hypertable if not already
        IF NOT EXISTS (
            SELECT 1 FROM timescaledb_information.hypertables
            WHERE table_name = 'market_data'
        ) THEN
            PERFORM create_hypertable('market_data', 'timestamp');
        END IF;

        -- Convert account_snapshots to hypertable if not already
        IF NOT EXISTS (
            SELECT 1 FROM timescaledb_information.hypertables
            WHERE table_name = 'account_snapshots'
        ) THEN
            PERFORM create_hypertable('account_snapshots', 'snapshot_time');
        END IF;
    END IF;
END $$;

COMMIT;
