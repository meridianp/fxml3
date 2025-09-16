#!/usr/bin/env python3
"""
Test script for the Interactive Brokers data feed.

This script tests the IBDataFeed class from fxml4.data_engineering.data_feeds.ib_feed.
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add the project root to sys.path
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from fxml4.data_engineering.data_feeds.ib_feed import IBDataFeed
except ImportError:
    logger.error(
        "Failed to import IBDataFeed. Make sure the FXML4 package is installed."
    )
    sys.exit(1)


def test_historical_data(feed, symbol, timeframe, days_back=5):
    """Test fetching historical data.

    Args:
        feed: IBDataFeed instance
        symbol: Symbol to fetch data for
        timeframe: Timeframe to fetch data for
        days_back: Number of days to go back for end date

    Returns:
        True if test passes, False otherwise
    """
    try:
        # Calculate end date (days_back days ago)
        end_date = datetime.now() - timedelta(days=days_back)

        logger.info(
            f"Fetching {timeframe} historical data for {symbol} ending at {end_date}"
        )
        df = feed.fetch_data(symbol, timeframe, end_date=end_date)

        if df.empty:
            logger.warning(f"No data received for {symbol} {timeframe}")
            return False

        # Print data summary
        logger.info(f"Retrieved {len(df)} bars of {timeframe} data for {symbol}")
        logger.info(f"Date range: {df.index.min()} to {df.index.max()}")
        logger.info(f"Sample data:\n{df.head().to_string()}")

        return True

    except Exception as e:
        logger.error(f"Error testing historical data: {e}")
        return False


def test_market_data(feed, symbol):
    """Test fetching real-time market data.

    Args:
        feed: IBDataFeed instance
        symbol: Symbol to fetch data for

    Returns:
        True if test passes, False otherwise
    """
    try:
        logger.info(f"Fetching market data for {symbol}")
        market_data = feed.get_market_data(symbol)

        if not market_data:
            logger.warning(f"No market data received for {symbol}")
            return False

        # Print market data
        logger.info(f"Market data for {symbol}:")
        for key, value in market_data.items():
            logger.info(f"  {key}: {value}")

        return True

    except Exception as e:
        logger.error(f"Error testing market data: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test the Interactive Brokers data feed"
    )
    parser.add_argument("--host", default="127.0.0.1", help="TWS host")
    parser.add_argument(
        "--port", type=int, default=7497, help="TWS port (7497 for paper trading)"
    )
    parser.add_argument("--client-id", type=int, default=0, help="Client ID")
    parser.add_argument("--symbol", default="GBP.USD", help="Symbol to test")
    parser.add_argument(
        "--timeframe", default="1h", help="Timeframe to test (e.g., 1m, 1h, 1d)"
    )
    parser.add_argument(
        "--days-back", type=int, default=0, help="Days to go back for historical data"
    )
    parser.add_argument(
        "--historical-only", action="store_true", help="Test historical data only"
    )
    parser.add_argument(
        "--market-only", action="store_true", help="Test market data only"
    )
    args = parser.parse_args()

    # Create the IB data feed
    config = {
        "host": args.host,
        "port": args.port,
        "client_id": args.client_id,
        "symbols": [args.symbol],
    }

    try:
        feed = IBDataFeed(config)

        # Connect to TWS
        if not feed.connect():
            logger.error("Failed to connect to TWS")
            return 1

        # Run tests
        if args.historical_only or not args.market_only:
            if not test_historical_data(
                feed, args.symbol, args.timeframe, args.days_back
            ):
                logger.error("Historical data test failed")
                return 1

            logger.info("Historical data test passed")

        if args.market_only or not args.historical_only:
            if not test_market_data(feed, args.symbol):
                logger.error("Market data test failed")
                return 1

            logger.info("Market data test passed")

        # Disconnect
        feed.disconnect()
        logger.info("All tests passed")
        return 0

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return 1

    finally:
        # Ensure disconnection
        try:
            if "feed" in locals() and feed:
                feed.disconnect()
        except:
            pass


if __name__ == "__main__":
    sys.exit(main())
