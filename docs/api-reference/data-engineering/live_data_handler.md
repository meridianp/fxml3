# LiveDataHandler

The `LiveDataHandler` class provides a robust service for managing continuous data streams from Interactive Brokers, with proper connection management, reconnection logic, and handling of market hours and trading sessions.

## Overview

The LiveDataHandler builds on top of the `IBDataFeed` class and adds the following capabilities:

1. **Robust Connection Management**: Automatic reconnection with configurable retry policies
2. **Market Hours Awareness**: Understanding of trading hours for different market types
3. **Multi-Threading Architecture**: Separate threads for connection management, health checks, data processing, and market hour tracking
4. **Callback System**: Event-based notification system for connection status and data updates
5. **Symbol Subscription Management**: Efficient handling of market data subscriptions
6. **Error Handling & Resilience**: Comprehensive error handling and recovery strategies

## Usage

### Basic Usage

```python
from fxml4.data_engineering.live_data_handler import LiveDataHandler

# Configure the handler
config = {
    "market_type": "forex",
    "symbols": ["GBPUSD", "EURUSD"],
    "timeframes": ["1m", "5m", "15m", "1h"],
    "ib_config": {
        "host": "127.0.0.1",
        "port": 7497  # Paper trading port
    }
}

# Create and start the handler
handler = LiveDataHandler(config)
handler.start()

# Register a callback for candles
def on_candle(symbol, timeframe, candles):
    latest = candles.iloc[-1]
    print(f"New {timeframe} candle for {symbol}: {latest['close']}")

handler.register_candle_callback("GBPUSD", "1h", on_candle)

# Subscribe to additional symbols
handler.subscribe_symbol("USDJPY")

# Get latest candles
latest_candles = handler.get_latest_candles("GBPUSD", "1h", limit=10)

# Check market status
status = handler.get_current_market_status()
print(f"Connection: {status['connection_state']}, Market: {status['market_status']}")

# Stop when done
handler.stop()
```

### Example Script

For a complete example of using the LiveDataHandler, see the [live_data_example.py](/examples/live_data_example.py) script.

## Configuration Options

The LiveDataHandler supports the following configuration options:

### Basic Configuration

- `market_type` - Market type (e.g., "forex" or "us_equities")
- `symbols` - List of symbols to subscribe to
- `timeframes` - List of timeframes to process (e.g., ["1m", "5m", "1h"])
- `base_timeframe` - Base timeframe for data processing (default: "1m")

### Market Hours Configuration

- `observe_market_hours` - Whether to observe market trading hours (default: True)
- `holidays` - List of holiday dates to exclude from trading (in "YYYY-MM-DD" format)

### Connection Management

- `max_reconnect_attempts` - Maximum number of reconnection attempts (default: 5)
- `reconnect_delay` - Delay between reconnection attempts in seconds (default: 30)
- `health_check_interval` - Interval between health checks in seconds (default: 60)
- `data_timeout` - Timeout for data freshness checks in seconds (default: 300)

### IB Connection Configuration

- `ib_config` - Dictionary with IB connection settings:
  - `host` - TWS/IB Gateway host (default: "127.0.0.1")
  - `port` - TWS/IB Gateway port (default: 7497 for paper trading)
  - `client_id` - Client ID for IB connection (default: 1)
  - `real_time_updates` - Whether to enable real-time updates (default: True)
  - `update_interval` - How often to process ticks in seconds (default: 1.0)
  - `tick_storage_limit` - Maximum number of ticks to store (default: 10000)
  - `candle_storage_days` - Number of days of candle history to keep (default: 7)

### Storage Configuration

- `store_in_db` - Whether to store data in TimescaleDB (default: True)

## Market Hours

The LiveDataHandler has built-in knowledge of market hours for different market types. The supported market types are:

### Forex Market Hours

- **Weekly Schedule**:
  - Opens: Sunday 21:00 UTC
  - Closes: Friday 21:00 UTC
- **Daily Maintenance**:
  - Daily rollover period: 21:55-22:05 UTC

### US Equities Market Hours

- **Regular Market Hours**:
  - Opens: 14:30 UTC (9:30 AM ET)
  - Closes: 21:00 UTC (4:00 PM ET)
- **Pre-Market Hours**:
  - Opens: 09:00 UTC (4:00 AM ET)
  - Closes: 14:30 UTC (9:30 AM ET)
- **After-Market Hours**:
  - Opens: 21:00 UTC (4:00 PM ET)
  - Closes: 01:00 UTC (8:00 PM ET)

## Market Status

The LiveDataHandler tracks the current market status, which can be one of the following:

- `OPEN`: The market is open for regular trading
- `CLOSED`: The market is closed for trading
- `PRE_MARKET`: Pre-market trading session (US equities)
- `AFTER_MARKET`: After-market trading session (US equities)
- `MAINTENANCE`: Market maintenance period (e.g., forex rollover)
- `WEEKEND`: Weekend closure (Saturday-Sunday)
- `HOLIDAY`: Market holiday (as specified in configuration)

## Connection States

The LiveDataHandler tracks the current connection state, which can be one of the following:

- `DISCONNECTED`: Not connected to IB
- `CONNECTING`: Connection attempt in progress
- `CONNECTED`: Successfully connected to IB
- `RECONNECTING`: Attempting to reconnect after a failure
- `ERROR`: Connection error state

## Data Callbacks

The LiveDataHandler provides a callback-based system for data and status notifications:

### Candle Callbacks

```python
def on_candle(symbol: str, timeframe: str, candles: pd.DataFrame):
    # Process new candle data
    latest = candles.iloc[-1]
    print(f"New {timeframe} candle: {latest['close']}")

handler.register_candle_callback("GBPUSD", "1h", on_candle)
```

### Status Callbacks

```python
def on_status_change(status: Dict[str, Any]):
    # Process status changes
    print(f"Connection: {status['connection_state']}, Market: {status['market_status']}")
    print(f"Active symbols: {status['active_symbols']}")

handler.register_status_callback(on_status_change)
```

## Symbol Management

The LiveDataHandler provides methods for managing symbol subscriptions:

```python
# Subscribe to a new symbol
handler.subscribe_symbol("USDJPY")

# Unsubscribe from a symbol
handler.unsubscribe_symbol("EURUSD")
```

## Historical Data

You can also fetch historical data for a specific symbol and timeframe:

```python
# Get historical data for the past week
from datetime import datetime, timedelta, timezone
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=7)

historical_data = handler.get_historical_data(
    symbol="GBPUSD",
    timeframe="1h",
    start_date=start_date,
    end_date=end_date
)
```

## Threading Architecture

The LiveDataHandler uses a multi-threading architecture with the following components:

1. **Connection Management Thread**: Handles connection establishment and subscription management
2. **Market Hours Monitoring Thread**: Monitors and updates market status based on time
3. **Health Check Thread**: Performs regular health checks on the connection
4. **Data Processing Thread**: Processes incoming data and generates candles

Each thread runs independently and communicates through shared state with proper locking.

## Error Handling

The LiveDataHandler implements comprehensive error handling with:

1. **Automatic Reconnection**: Attempts to reconnect when the connection is lost
2. **Data Freshness Checks**: Monitors for stale data and resubscribes if needed
3. **Market Hours Awareness**: Avoids unnecessary reconnection attempts during market closures
4. **Recovery Strategies**: Implements different strategies for various error conditions

## Performance Considerations

When using the LiveDataHandler, consider the following performance aspects:

1. **Memory Usage**: The handler stores candle data in memory; limit the number of symbols and timeframes for resource-constrained environments
2. **CPU Usage**: Processing tick data consumes CPU; adjust the update_interval parameter based on your hardware
3. **Network Traffic**: Subscribing to many symbols increases network traffic; prioritize the most important symbols
4. **Database Load**: When store_in_db is enabled, candles are stored in TimescaleDB; ensure your database is properly sized

## Best Practices

1. **Start Small**: Begin with a few essential symbols and timeframes
2. **Monitor Memory Usage**: Watch for memory growth, especially with many symbols
3. **Handle Callbacks Efficiently**: Keep callback functions lightweight and fast
4. **Proper Shutdown**: Always call stop() when finished to release resources
5. **Error Logging**: Monitor logs for connection and data issues
6. **Market Hours**: Configure market hours correctly for your use case
7. **Health Checks**: Adjust health check parameters based on your network reliability
