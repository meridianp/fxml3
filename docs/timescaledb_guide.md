# FXML4 TimescaleDB Guide

This guide provides information on how to use TimescaleDB in the FXML4 project for efficient time-series data storage and retrieval.

## Overview

TimescaleDB is an extension to PostgreSQL that optimizes it for time-series data. In FXML4, we use TimescaleDB to store:

1. Tick data from trading sources
2. OHLCV candle data at various timeframes
3. Technical indicators and derived features

## Connection Details

TimescaleDB is configured to run on port 5433 to avoid conflicts with the standard PostgreSQL instance:

```
TIMESCALEDB_HOST=localhost
TIMESCALEDB_PORT=5433
TIMESCALEDB_USER=postgres
TIMESCALEDB_PASSWORD=postgres
TIMESCALEDB_DATABASE=fxml4
```

## Database Schema

### Tick Data

Tick data is stored in the `tick_data` hypertable with the following schema:

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
```

### OHLCV Data

OHLCV data is stored in the `market_data_1m` hypertable with the following schema:

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
    source TEXT NOT NULL,     -- 'ib', 'alpha_vantage', 'calculated', etc.

    PRIMARY KEY (time, symbol)
);
```

### Continuous Aggregates

TimescaleDB automatically creates and maintains continuous aggregates (materialized views) for higher timeframes:

- `market_data_5m`: 5-minute candles
- `market_data_15m`: 15-minute candles
- `market_data_30m`: 30-minute candles
- `market_data_1h`: 1-hour candles
- `market_data_4h`: 4-hour candles
- `market_data_1d`: 1-day candles

These aggregates are automatically updated by TimescaleDB's background worker.

## Data Management

### Compression Policies

To optimize storage, TimescaleDB automatically compresses older data:

- Tick data is compressed after 1 day
- 1-minute candle data is compressed after 7 days

### Retention Policies

To manage storage space, data is automatically removed after a certain period:

- Tick data is kept for 30 days
- 1-minute candle data is kept for 2 years

## Common Operations

### Querying OHLCV Data

To query OHLCV data for a specific symbol and timeframe:

```sql
-- Get 1-minute data
SELECT * FROM market_data_1m
WHERE symbol = 'EURUSD'
AND time BETWEEN '2023-01-01' AND '2023-01-02'
ORDER BY time;

-- Get 5-minute data
SELECT * FROM market_data_5m
WHERE symbol = 'EURUSD'
AND bucket BETWEEN '2023-01-01' AND '2023-01-02'
ORDER BY bucket;
```

### Using Utility Functions

TimescaleDB provides several utility functions:

```sql
-- Get the latest tick for a symbol
SELECT * FROM get_latest_tick('EURUSD', 'trade');

-- Get OHLCV data for a specific timeframe
SELECT * FROM get_ohlcv('EURUSD', '4h', '2023-01-01', '2023-01-31');
```

## Using the TimescaleDBClient

FXML4 provides a `TimescaleDBClient` class for programmatically interacting with TimescaleDB:

```python
from fxml4.data_engineering.timescaledb import TimescaleDBClient

# Initialize client
client = TimescaleDBClient(
    host="localhost",
    port=5433,
    dbname="fxml4",
    user="postgres",
    password="postgres"
)

# Store ticks
ticks = [
    {
        "symbol": "EURUSD",
        "timestamp": datetime.now(timezone.utc),
        "price": 1.1234,
        "size": 100,
        "tick_type": "trade",
        "source": "ib"
    }
]
client.store_ticks(ticks)

# Store candles
candles = [
    {
        "symbol": "EURUSD",
        "timestamp": datetime.now(timezone.utc).replace(second=0, microsecond=0),
        "open": 1.1234,
        "high": 1.1245,
        "low": 1.1230,
        "close": 1.1240,
        "volume": 1000,
        "tick_count": 50,
        "source": "calculated"
    }
]
client.store_candles(candles)

# Get OHLCV data
start_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
end_time = datetime(2023, 1, 31, tzinfo=timezone.utc)
df = client.get_ohlcv_data("EURUSD", "4h", start_time, end_time)

# Get latest candle
latest = client.get_latest_candle("EURUSD", "1m")
```

## Administration

### Checking Continuous Aggregates

```sql
SELECT view_name FROM timescaledb_information.continuous_aggregates;
```

### Checking Compression Status

```sql
SELECT * FROM timescaledb_information.compression_settings;
```

### Checking Retention Policies

```sql
SELECT * FROM timescaledb_information.job_stats
WHERE proc_name = 'policy_retention';
```

## Best Practices

1. Always use timezone-aware timestamps (UTC) when working with TimescaleDB
2. Use batch inserts whenever possible for better performance
3. Prefer querying continuous aggregates for higher timeframes
4. Add appropriate indexes for frequently queried columns
5. Regularly monitor disk usage and compression status
