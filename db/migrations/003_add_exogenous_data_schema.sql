-- FXML4 Migration: Add exogenous_data table for economic indicators and external data sources

-- Create exogenous_data hypertable for storing economic indicators and other external data
-- This table will store data from sources like FRED, Alpha Vantage, etc.
CREATE TABLE IF NOT EXISTS exogenous_data (
    time TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,         -- 'fred', 'alpha_vantage', etc.
    indicator_name TEXT NOT NULL, -- 'UNRATE', 'GDP', 'CPI', etc.
    value DOUBLE PRECISION NOT NULL,
    frequency TEXT NOT NULL,      -- 'daily', 'weekly', 'monthly', 'quarterly', 'annual'
    metadata JSONB,

    PRIMARY KEY (time, source, indicator_name)
);

-- Check if TimescaleDB extension is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        -- Convert to hypertable
        PERFORM create_hypertable('exogenous_data', 'time', if_not_exists => TRUE);

        -- Create index for faster queries
        CREATE INDEX IF NOT EXISTS idx_exogenous_data_indicator ON exogenous_data (indicator_name, time DESC);
        CREATE INDEX IF NOT EXISTS idx_exogenous_data_source ON exogenous_data (source, time DESC);

        -- Create a view for the most recent values of each indicator
        CREATE OR REPLACE VIEW latest_exogenous_data AS
        SELECT DISTINCT ON (source, indicator_name)
            time,
            source,
            indicator_name,
            value,
            frequency,
            metadata
        FROM exogenous_data
        ORDER BY source, indicator_name, time DESC;

        -- Add retention policy (keep data for 10 years by default)
        -- Uncomment and adjust as needed for production
        -- SELECT add_retention_policy('exogenous_data', INTERVAL '10 years');

        -- Add compression policy (compress data older than 30 days)
        -- Uncomment and adjust as needed for production
        -- SELECT add_compression_policy('exogenous_data', INTERVAL '30 days');
    END IF;
END
$$;

-- Create table to store indicator metadata (for reference)
CREATE TABLE IF NOT EXISTS exogenous_indicators (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,
    frequency TEXT NOT NULL,
    units TEXT,
    category TEXT,
    last_updated TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (source, indicator_name)
);

-- Insert commonly used economic indicators
INSERT INTO exogenous_indicators (source, indicator_name, display_name, frequency, description, units, category) VALUES
    -- FRED indicators
    ('fred', 'UNRATE', 'Unemployment Rate', 'monthly', 'US Unemployment Rate, Seasonally Adjusted', 'percent', 'employment'),
    ('fred', 'GDP', 'Gross Domestic Product', 'quarterly', 'US Gross Domestic Product, Billions of Dollars', 'billion USD', 'output'),
    ('fred', 'CPIAUCSL', 'Consumer Price Index', 'monthly', 'Consumer Price Index for All Urban Consumers: All Items', 'index', 'inflation'),
    ('fred', 'FEDFUNDS', 'Federal Funds Rate', 'daily', 'Effective Federal Funds Rate', 'percent', 'interest_rates'),
    ('fred', 'T10Y2Y', 'Treasury Yield Spread (10Y-2Y)', 'daily', '10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity', 'percent', 'interest_rates'),
    ('fred', 'DTWEXBGS', 'US Dollar Index', 'daily', 'Trade Weighted U.S. Dollar Index: Broad, Goods and Services', 'index', 'forex'),
    ('fred', 'VIXCLS', 'VIX Volatility Index', 'daily', 'CBOE Volatility Index: VIX', 'index', 'market_volatility'),

    -- Alpha Vantage indicators
    ('alpha_vantage', 'REAL_GDP', 'Real GDP', 'quarterly', 'US Real Gross Domestic Product', 'billion USD', 'output'),
    ('alpha_vantage', 'INFLATION', 'Inflation Rate', 'annual', 'US Inflation Rate (Consumer Prices)', 'percent', 'inflation'),
    ('alpha_vantage', 'WTI', 'WTI Crude Oil Price', 'daily', 'West Texas Intermediate (WTI) Crude Oil Price', 'USD', 'commodities'),
    ('alpha_vantage', 'BRENT', 'Brent Crude Oil Price', 'daily', 'Brent (Europe) Crude Oil Price', 'USD', 'commodities'),
    ('alpha_vantage', 'NATURAL_GAS', 'Natural Gas Price', 'daily', 'Henry Hub Natural Gas Spot Price', 'USD', 'commodities')

ON CONFLICT (source, indicator_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    frequency = EXCLUDED.frequency,
    units = EXCLUDED.units,
    category = EXCLUDED.category,
    updated_at = NOW();

-- Create a function to get the most recent value of an indicator
CREATE OR REPLACE FUNCTION get_latest_indicator_value(
    p_source TEXT,
    p_indicator_name TEXT
) RETURNS TABLE (
    time TIMESTAMPTZ,
    value DOUBLE PRECISION,
    frequency TEXT,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT e.time, e.value, e.frequency, e.metadata
    FROM exogenous_data e
    WHERE e.source = p_source AND e.indicator_name = p_indicator_name
    ORDER BY e.time DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;
