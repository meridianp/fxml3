-- Order Management Schema
-- Adds proper order management tables for live trading

-- Orders table for live trading orders
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    symbol_id UUID REFERENCES symbols(id),
    order_type TEXT NOT NULL,  -- market, limit, stop, stop_limit
    side TEXT NOT NULL,        -- buy, sell
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8),       -- NULL for market orders
    stop_price DECIMAL(18,8),  -- For stop orders
    time_in_force TEXT NOT NULL DEFAULT 'DAY', -- DAY, GTC, IOC, FOK
    status TEXT NOT NULL,      -- pending, submitted, acknowledged, working, partially_filled, filled, rejected, cancelled
    broker TEXT NOT NULL,      -- ib, fxcm, manual
    broker_order_id TEXT,      -- External broker order ID
    filled_quantity DECIMAL(18,8) DEFAULT 0,
    average_fill_price DECIMAL(18,8),
    commission DECIMAL(18,8) DEFAULT 0,
    rejection_reason TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    submitted_at TIMESTAMP WITH TIME ZONE,
    filled_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE
);

-- Positions table for tracking open positions
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    symbol_id UUID REFERENCES symbols(id),
    side TEXT NOT NULL,        -- long, short
    quantity DECIMAL(18,8) NOT NULL,
    average_price DECIMAL(18,8) NOT NULL,
    current_price DECIMAL(18,8),
    unrealized_pnl DECIMAL(18,8) DEFAULT 0,
    realized_pnl DECIMAL(18,8) DEFAULT 0,
    commission_paid DECIMAL(18,8) DEFAULT 0,
    broker TEXT NOT NULL,      -- ib, fxcm, manual
    broker_position_id TEXT,   -- External broker position ID
    status TEXT NOT NULL DEFAULT 'open', -- open, closed
    metadata JSONB,
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE
);

-- Trades table for completed trades (order fills)
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES orders(id),
    position_id UUID REFERENCES positions(id),
    user_id UUID REFERENCES users(id),
    symbol_id UUID REFERENCES symbols(id),
    side TEXT NOT NULL,        -- buy, sell
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    commission DECIMAL(18,8) DEFAULT 0,
    pnl DECIMAL(18,8),        -- Realized P&L for this trade
    broker TEXT NOT NULL,      -- ib, fxcm, manual
    broker_trade_id TEXT,      -- External broker trade ID
    metadata JSONB,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Account snapshots for tracking account balance/equity over time
CREATE TABLE IF NOT EXISTS account_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    broker TEXT NOT NULL,
    account_id TEXT NOT NULL,
    balance DECIMAL(18,8) NOT NULL,
    equity DECIMAL(18,8) NOT NULL,
    unrealized_pnl DECIMAL(18,8) DEFAULT 0,
    margin_used DECIMAL(18,8) DEFAULT 0,
    margin_available DECIMAL(18,8) DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Risk events for compliance and monitoring
CREATE TABLE IF NOT EXISTS risk_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    order_id UUID REFERENCES orders(id),
    event_type TEXT NOT NULL,  -- position_limit, order_size_limit, daily_loss_limit, etc.
    severity TEXT NOT NULL,    -- info, warning, error, critical
    message TEXT NOT NULL,
    details JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_user_status ON orders(user_id, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_symbol_status ON orders(symbol_id, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_broker_status ON orders(broker, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_user_status ON positions(user_id, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_symbol_status ON positions(symbol_id, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_broker_status ON positions(broker, status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_user_executed ON trades(user_id, executed_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_symbol_executed ON trades(symbol_id, executed_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_order_id ON trades(order_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_position_id ON trades(position_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_account_snapshots_user_created ON account_snapshots(user_id, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_account_snapshots_broker_created ON account_snapshots(broker, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_risk_events_user_created ON risk_events(user_id, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_risk_events_type_resolved ON risk_events(event_type, resolved);

-- Add missing symbols that are referenced by the system
INSERT INTO symbols (name, display_name, asset_class) VALUES
    ('USDCHF', 'USD/CHF', 'forex'),
    ('USDCAD', 'USD/CAD', 'forex'),
    ('NZDUSD', 'NZD/USD', 'forex')
ON CONFLICT (name) DO NOTHING;

-- Create RLS policies if using with Supabase
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgsodium') THEN
        -- Enable Row Level Security
        ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
        ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
        ALTER TABLE account_snapshots ENABLE ROW LEVEL SECURITY;
        ALTER TABLE risk_events ENABLE ROW LEVEL SECURITY;

        -- Create policies
        CREATE POLICY orders_owner_access ON orders
            USING (user_id = auth.uid());

        CREATE POLICY positions_owner_access ON positions
            USING (user_id = auth.uid());

        CREATE POLICY trades_owner_access ON trades
            USING (user_id = auth.uid());

        CREATE POLICY account_snapshots_owner_access ON account_snapshots
            USING (user_id = auth.uid());

        CREATE POLICY risk_events_owner_access ON risk_events
            USING (user_id = auth.uid());
    END IF;
END
$$;
