#!/usr/bin/env python3
"""
Test real-time tick data processing from Interactive Brokers.

This script demonstrates how to:
1. Connect to Interactive Brokers TWS API
2. Subscribe to real-time tick data for one or more symbols
3. Process ticks to build 1-minute candles
4. Display real-time candle data
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add the project root to the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from fxml4.data_engineering.data_feeds.ib_feed import IBDataFeed


def display_dataframe(df, title=None):
    """Display a pandas DataFrame nicely."""
    if title:
        print(f"\n=== {title} ===")

    if df.empty:
        print("No data available.")
        return

    # Format the DataFrame
    pd.set_option("display.max_rows", 10)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)
    pd.set_option("display.precision", 5)

    # Convert datetime index to string for better display
    df_display = df.copy()
    if isinstance(df_display.index, pd.DatetimeIndex):
        df_display.index = df_display.index.strftime("%Y-%m-%d %H:%M:%S")

    # Print the DataFrame
    print(df_display)
    print(f"Total rows: {len(df)}")


def test_realtime_feed(symbols, port=7497, duration_seconds=120, update_interval=5):
    """Test real-time data feed.

    Args:
        symbols: List of symbols to test
        port: TWS port (default: 7497 for paper trading)
        duration_seconds: How long to run the test (in seconds)
        update_interval: How often to display updates (in seconds)
    """
    # Load configuration from config file
    from fxml4.config import get_data_feed_config

    # Get IB config and customize for this test
    ib_config = get_data_feed_config("ib")

    # Override with test-specific settings
    ib_config.update(
        {
            "port": port,
            "client_id": 0,
            "real_time_updates": True,
            "update_interval": 0.5,  # Process ticks every 0.5 seconds
            "symbols": symbols,
        }
    )

    feed = IBDataFeed(ib_config)

    try:
        # Connect to TWS
        if not feed.connect():
            logger.error("Failed to connect to TWS")
            return

        logger.info(f"Connected to TWS. Testing real-time data for symbols: {symbols}")

        # Subscribe to market data for each symbol
        for symbol in symbols:
            feed.subscribe_market_data(symbol)

        # Run for the specified duration
        end_time = datetime.now() + timedelta(seconds=duration_seconds)
        next_update = datetime.now() + timedelta(seconds=update_interval)

        while datetime.now() < end_time:
            # Display updates periodically
            if datetime.now() >= next_update:
                next_update = datetime.now() + timedelta(seconds=update_interval)

                # Display latest ticks
                for symbol in symbols:
                    latest_tick = feed.get_latest_tick(symbol)
                    if latest_tick:
                        bid = latest_tick.get("bid", "N/A")
                        ask = latest_tick.get("ask", "N/A")
                        logger.info(f"Latest {symbol}: Bid={bid}, Ask={ask}")

                # Display 1-minute candles
                for symbol in symbols:
                    candles = feed.get_realtime_candles(symbol, timeframe=1, limit=5)
                    display_dataframe(candles, f"{symbol} 1-minute candles")

                # Display multiple timeframes
                for symbol in symbols:
                    # Show candles for various timeframes
                    for timeframe in ["5m", "15m", "1h"]:
                        candles = feed.get_realtime_candles(
                            symbol, timeframe=timeframe, limit=3
                        )
                        if not candles.empty:
                            display_dataframe(candles, f"{symbol} {timeframe} candles")

            # Sleep a bit to avoid high CPU usage
            time.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        # Disconnect from TWS
        feed.disconnect()
        logger.info("Test completed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test real-time IB data feed")
    parser.add_argument(
        "--symbols", default="GBP.USD", help="Comma-separated list of symbols"
    )
    parser.add_argument(
        "--port", type=int, default=7497, help="TWS port (7497 for paper trading)"
    )
    parser.add_argument(
        "--duration", type=int, default=120, help="Test duration in seconds"
    )
    parser.add_argument(
        "--interval", type=int, default=5, help="Update interval in seconds"
    )
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]

    test_realtime_feed(
        symbols=symbols,
        port=args.port,
        duration_seconds=args.duration,
        update_interval=args.interval,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
