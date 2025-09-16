# IB API Integration

This tutorial explains how to set up and use the Interactive Brokers (IB) API integration in FXML4.

## Prerequisites

Before you begin, you need:

1. An Interactive Brokers account (paper trading or live)
2. Trader Workstation (TWS) or IB Gateway installed
3. Basic familiarity with forex trading concepts

## Setting Up Interactive Brokers

### Step 1: Install Trader Workstation (TWS)

1. Download TWS from the [Interactive Brokers website](https://www.interactivebrokers.com/en/index.php?f=14099#tws-software)
2. Install TWS following the on-screen instructions
3. Launch TWS and log in with your IB credentials

### Step 2: Configure TWS for API Access

1. In TWS, go to **Edit > Global Configuration > API > Settings**
2. Enable "**Enable ActiveX and Socket Clients**"
3. Set the socket port to 7497 for paper trading (or 7496 for live trading)
4. Click "**Apply**" and "**OK**"

![TWS API Settings](../assets/tws-api-settings.png)

## Installing the IB API

FXML4 requires the official IB API Python client. The client should be installed automatically when you install FXML4 dependencies, but if you need to install it manually:

```bash
# Install IB API from TWS source
cd /path/to/TWS/source/ibapi
python setup.py install
```

Or directly from the requirements:

```bash
pip install -r requirements.txt
```

## Testing the Connection

FXML4 includes a script for testing the IB API connection:

```bash
python scripts/test_ib_feed.py --port 7497 --symbol GBP.USD
```

If successful, you should see output similar to:

```
2025-03-10 16:31:20,587 - __main__ - INFO - Using IB API version: 10.30.1
2025-03-10 16:31:20,588 - __main__ - INFO - Testing historical data retrieval for GBP.USD
...
2025-03-10 16:31:22,126 - __main__ - INFO - Total bars received: 112
...
2025-03-10 16:31:22,126 - __main__ - INFO - All tests passed
```

## Using the IB Data Feed

Here's how to use the IB data feed in your code:

```python
from fxml4.data_engineering.data_feeds.ib_feed import IBDataFeed

# Create the data feed with paper trading port
config = {
    "port": 7497,  # Paper trading port
    "client_id": 0,
    "symbols": ["EUR.USD", "GBP.USD", "USD.JPY"]
}
feed = IBDataFeed(config)

# Connect to TWS
if feed.connect():
    try:
        # Fetch 1-hour data for GBP/USD
        df = feed.fetch_data("GBP.USD", timeframe="1h")

        # Print the data
        print(df.head())

        # Get real-time market data
        market_data = feed.get_market_data("GBP.USD")
        print(f"Current bid: {market_data.get('BID')}")
        print(f"Current ask: {market_data.get('ASK')}")

    finally:
        # Always disconnect when done
        feed.disconnect()
else:
    print("Failed to connect to TWS")
```

## Available Timeframes

The IB data feed supports the following timeframes:

| FXML4 Timeframe | IB Bar Size  | Description           |
|-----------------|-------------|-----------------------|
| 1m              | 1 min       | 1-minute bars         |
| 5m              | 5 mins      | 5-minute bars         |
| 15m             | 15 mins     | 15-minute bars        |
| 30m             | 30 mins     | 30-minute bars        |
| 1h              | 1 hour      | 1-hour bars           |
| 2h              | 2 hours     | 2-hour bars           |
| 4h              | 4 hours     | 4-hour bars           |
| 1d              | 1 day       | Daily bars            |
| 1w              | 1 week      | Weekly bars           |
| 1M              | 1 month     | Monthly bars          |

## Troubleshooting

### Connection Issues

If you encounter connection issues:

1. Ensure TWS is running and logged in
2. Verify the API settings in TWS (Edit > Global Configuration > API > Settings)
3. Confirm you're using the correct port (7497 for paper trading, 7496 for live trading)
4. Check the TWS API activity log for error messages

### Market Data Issues

If you're not receiving market data:

1. Verify you have a valid market data subscription for the requested symbols
2. Check if you're requesting data during market hours
3. Ensure your account has permissions for the requested instrument type

## Next Steps

After successfully integrating with the IB API, you can:

1. Build trading strategies using FXML4's strategy framework
2. Backtest your strategies with historical data from IB
3. Deploy your strategies for automated trading

For more information, see the [Strategy Development](../tutorials/custom-strategies.md) tutorial.
