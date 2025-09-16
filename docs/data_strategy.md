# FXML4 Data Strategy

This document outlines the data strategy for FXML4, including market scope, data sources, storage solutions, and processing pipelines.

## Market Scope

### Target Currency Pairs
- **Primary Focus**:
  - GBP/USD
  - USD/CHF
  - EUR/USD
  - USD/JPY

### Timeframes
- **Primary Analysis Timeframe**: 4-hour intervals
- **Base Data Resolution**: 1-minute data
- **Alternative Resolutions**: 5-minute, 15-minute, 1-hour, daily (derived from 1-minute data)

## Data Sources

### Historical Data
- **Primary Source**: Polygon.io (10 years of 1-minute data)
- **Location**: `./input/` directory
- **Format**: Parquet files

### Real-time Data
- **Primary Source**: Interactive Brokers TWS API
- **Resolution**: Tick-level data
- **Usage**: Real-time trading signals and execution

### Backfill Data
- **Source**: Alpha Vantage API
- **Purpose**: Fill gaps between historical Polygon.io data and present
- **Integration**: Must match existing data structure before storage

### External Data

#### Macroeconomic Indicators
- **Sources**:
  - FRED (Federal Reserve Economic Data)
  - Trading Economics API
- **Key Indicators**:
  - CPI (Consumer Price Index)
  - GDP (Gross Domestic Product)
  - Interest Rates
  - Employment Reports

#### Market Sentiment
- **Sources**:
  - Alpha Vantage Sentiment API
  - EOD Historical Data
  - GDELT Project
  - FXStreet (for economic events)
  - Trading Economics (for economic sentiment)

## Data Storage Architecture

### Time-Series Market Data
- **Primary Storage**: TimescaleDB (PostgreSQL extension)
- **Key Features**:
  - Hypertables for efficient time-based partitioning
  - Continuous aggregates for pre-computed views
  - Compression for older data to reduce storage costs
- **Schema**: See "Database Schema" section

### Computed Features & Indicators
- **Storage Format**: Parquet files
- **Organization**: Hierarchical structure by symbol/timeframe/date
- **Computation Frequency**: 4-hour intervals, pre-computed for backtesting

### Backtesting Results
- **Storage Format**: Structured tables in PostgreSQL
- **Data Points**: Entry/exit points, P&L, drawdowns, metrics

## Data Processing Pipeline

### Historical Data Processing
1. **Data Acquisition**:
   - Load existing Polygon.io data from `./input/` directory
   - Identify latest timestamp in existing data
   - Fetch missing data from Alpha Vantage to fill gaps

2. **Data Normalization**:
   - Standardize column names
   - Handle timezone conversions (ensure UTC consistency)
   - Apply quality filters (remove outliers, handle gaps)

3. **Feature Engineering**:
   - Compute technical indicators at 4-hour intervals
   - Create derived timeframes (5m, 15m, 1h, 4h, 1d)
   - Generate ML features

4. **Storage**:
   - Store raw data in TimescaleDB
   - Store computed features in Parquet files

### Real-time Data Processing
1. **Data Collection**:
   - Connect to Interactive Brokers TWS API
   - Stream tick-level data
   - Process into 1-minute candles

2. **Backfilling**:
   - Compare with existing data
   - Fill any gaps
   - Normalize to match historical data structure

3. **Feature Computation**:
   - Calculate indicators and features in real-time
   - Update feature store

4. **Signal Generation**:
   - Feed data to ML models and Elliott Wave analysis
   - Generate trading signals
   - Apply risk management rules

## Immediate Implementation Tasks

1. **Data Gap Analysis**:
   - Examine existing data in `./input/` directory
   - Identify the latest timestamp for each currency pair
   - Calculate the date range to backfill

2. **Backfill Implementation**:
   - Create Alpha Vantage API client
   - Fetch missing data for identified gaps
   - Normalize and validate fetched data

3. **Data Storage Setup**:
   - Configure TimescaleDB extension in PostgreSQL
   - Create hypertables for time-series data
   - Set up continuous aggregates for common queries

4. **Integration with Signal Generation**:
   - Ensure data pipeline feeds into ML model inputs
   - Connect with Elliott Wave detection algorithms
   - Validate signal generation with latest data

## Database Schema

### Tick Data (Hypertable)
```sql
CREATE TABLE tick_data (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    size INTEGER,
    tick_type TEXT NOT NULL,  -- 'bid', 'ask', 'trade', etc.
    source TEXT NOT NULL,     -- 'ib', 'alpha_vantage', etc.

    PRIMARY KEY (time, symbol, tick_type)
);

-- Convert to hypertable
SELECT create_hypertable('tick_data', 'time');
```

### OHLCV Data (Hypertable)
```sql
CREATE TABLE market_data_1m (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume INTEGER NOT NULL,
    tick_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,

    PRIMARY KEY (time, symbol)
);

-- Convert to hypertable
SELECT create_hypertable('market_data_1m', 'time');

-- Create continuous aggregate for 5-minute candles
CREATE MATERIALIZED VIEW market_data_5m
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
```

### Technical Indicators
```sql
CREATE TABLE technical_indicators (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,

    PRIMARY KEY (time, symbol, timeframe, indicator_name)
);

-- Convert to hypertable
SELECT create_hypertable('technical_indicators', 'time');
```

### Compression and Retention Policies
```sql
-- Set compression policy for tick_data (compress after 1 day)
ALTER TABLE tick_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, tick_type'
);

SELECT add_compression_policy('tick_data', INTERVAL '1 day');

-- Set retention policy (keep tick data for 30 days to save space)
SELECT add_retention_policy('tick_data', INTERVAL '30 days');

-- Set compression policy for market_data_1m (compress after 7 days)
ALTER TABLE market_data_1m SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

SELECT add_compression_policy('market_data_1m', INTERVAL '7 days');

-- Keep 1-minute data for 2 years
SELECT add_retention_policy('market_data_1m', INTERVAL '2 years');
```

## Data Quality and Monitoring

### Quality Checks
- Missing data detection
- Outlier identification
- Volume anomaly detection
- Price gap analysis

### Monitoring
- Data freshness metrics
- API quota usage
- Storage utilization
- Processing latency

## Notes for Integration
- Ensure all timestamps are in UTC
- Use ISO-8601 format for date/time representation
- Apply consistent naming conventions across all data sources
- Implement graceful handling of API failures
