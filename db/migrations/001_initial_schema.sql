-- FXML4 Initial Database Schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create symbols table
CREATE TABLE IF NOT EXISTS symbols (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create timeframes table
CREATE TABLE IF NOT EXISTS timeframes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    minutes INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create models table
CREATE TABLE IF NOT EXISTS models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    model_type TEXT NOT NULL,
    symbol_id UUID REFERENCES symbols(id),
    timeframe_id UUID REFERENCES timeframes(id),
    metadata JSONB,
    file_path TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (name, version)
);

-- Create signals table
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol_id UUID REFERENCES symbols(id),
    timeframe_id UUID REFERENCES timeframes(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    signal_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    strength FLOAT NOT NULL,
    source TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create backtests table
CREATE TABLE IF NOT EXISTS backtests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    user_id UUID REFERENCES users(id),
    symbol_id UUID REFERENCES symbols(id),
    timeframe_id UUID REFERENCES timeframes(id),
    strategy TEXT NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    initial_capital FLOAT NOT NULL,
    final_capital FLOAT NOT NULL,
    total_return FLOAT NOT NULL,
    total_return_pct FLOAT NOT NULL,
    max_drawdown FLOAT NOT NULL,
    sharpe_ratio FLOAT NOT NULL,
    sortino_ratio FLOAT NOT NULL,
    win_rate FLOAT NOT NULL,
    parameters JSONB,
    results JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create backtest_trades table
CREATE TABLE IF NOT EXISTS backtest_trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backtest_id UUID REFERENCES backtests(id),
    entry_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_timestamp TIMESTAMP WITH TIME ZONE,
    direction TEXT NOT NULL,
    entry_price FLOAT NOT NULL,
    exit_price FLOAT,
    quantity FLOAT NOT NULL,
    pnl FLOAT,
    pnl_pct FLOAT,
    status TEXT NOT NULL,
    metadata JSONB
);

-- Create api_keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    scopes TEXT[] NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE
);

-- Create wave_patterns table
CREATE TABLE IF NOT EXISTS wave_patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol_id UUID REFERENCES symbols(id),
    timeframe_id UUID REFERENCES timeframes(id),
    start_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    end_timestamp TIMESTAMP WITH TIME ZONE,
    wave_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    sub_waves JSONB,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create knowledge_vectors table
-- Note: Vector extension might not be available in local PostgreSQL
-- In production, we'll use pgvector
CREATE TABLE IF NOT EXISTS knowledge_vectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT NOT NULL,
    content_type TEXT NOT NULL,
    category TEXT NOT NULL,
    embedding JSONB, -- Stored as JSON array for local development
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create RLS policies if using with Supabase
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgsodium') THEN
        -- Enable Row Level Security
        ALTER TABLE users ENABLE ROW LEVEL SECURITY;
        ALTER TABLE backtests ENABLE ROW LEVEL SECURITY;
        ALTER TABLE backtest_trades ENABLE ROW LEVEL SECURITY;
        ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
        ALTER TABLE wave_patterns ENABLE ROW LEVEL SECURITY;

        -- Create policies
        CREATE POLICY user_self_access ON users
            USING (id = auth.uid());

        CREATE POLICY backtest_owner_access ON backtests
            USING (user_id = auth.uid());

        CREATE POLICY backtest_trades_via_backtest ON backtest_trades
            USING (backtest_id IN (SELECT id FROM backtests WHERE user_id = auth.uid()));

        CREATE POLICY api_key_owner_access ON api_keys
            USING (user_id = auth.uid());

        CREATE POLICY wave_patterns_access ON wave_patterns
            FOR SELECT USING (true);
    END IF;
END
$$;

-- Create initial data
INSERT INTO timeframes (name, minutes, display_name) VALUES
    ('1m', 1, '1 Minute'),
    ('5m', 5, '5 Minutes'),
    ('15m', 15, '15 Minutes'),
    ('30m', 30, '30 Minutes'),
    ('1h', 60, '1 Hour'),
    ('4h', 240, '4 Hours'),
    ('1d', 1440, '1 Day')
ON CONFLICT (name) DO NOTHING;

INSERT INTO symbols (name, display_name, asset_class) VALUES
    ('EURUSD', 'EUR/USD', 'forex'),
    ('GBPUSD', 'GBP/USD', 'forex'),
    ('USDJPY', 'USD/JPY', 'forex'),
    ('AUDUSD', 'AUD/USD', 'forex')
ON CONFLICT (name) DO NOTHING;
