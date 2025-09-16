#!/usr/bin/env python3
"""
Test script for Alpha Vantage data feed.

This script demonstrates how to use the Alpha Vantage data feed to fetch
financial data for forex and stocks.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pprint import pprint

import matplotlib.pyplot as plt
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

from fxml4.config import get_data_feed_config
from fxml4.data_engineering.data_feeds.alpha_vantage_feed import AlphaVantageDataFeed


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

    # Print the DataFrame
    print(df)
    print(f"Total rows: {len(df)}")


def plot_ohlc(df, title=None):
    """Plot OHLC data with volume."""
    if df.empty:
        print("No data to plot.")
        return

    # Create a figure
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    # Plot OHLC
    ax1.plot(df.index, df["close"], label="Close")

    # Set title and labels
    if title:
        ax1.set_title(title)
    ax1.set_ylabel("Price")
    ax1.grid(True)
    ax1.legend()

    # Plot volume
    ax2.bar(df.index, df["volume"], color="blue", alpha=0.5)
    ax2.set_ylabel("Volume")
    ax2.grid(True)

    # Format the x-axis
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Show the plot
    plt.show()


def test_forex_data(feed, symbol="EURUSD", timeframe="1d", days_back=30):
    """Test fetching forex data."""
    print(f"\n=== Testing forex data for {symbol} ({timeframe}) ===")

    # Calculate start date
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    try:
        # Fetch the data
        data = feed.fetch_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            data_type="forex",
        )

        # Display the data
        display_dataframe(data, f"{symbol} Forex Data ({timeframe})")

        # Plot the data
        plot_ohlc(data, f"{symbol} Forex Data ({timeframe})")

        return data

    except Exception as e:
        logger.error(f"Error fetching forex data: {e}")
        return pd.DataFrame()


def test_stock_data(feed, symbol="MSFT", timeframe="1d", days_back=30):
    """Test fetching stock data."""
    print(f"\n=== Testing stock data for {symbol} ({timeframe}) ===")

    # Calculate start date
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    try:
        # Fetch the data
        data = feed.fetch_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            data_type="stock",
            adjusted=True,
        )

        # Display the data
        display_dataframe(data, f"{symbol} Stock Data ({timeframe})")

        # Plot the data
        plot_ohlc(data, f"{symbol} Stock Data ({timeframe})")

        return data

    except Exception as e:
        logger.error(f"Error fetching stock data: {e}")
        return pd.DataFrame()


def test_symbol_search(feed, keywords="Microsoft"):
    """Test symbol search functionality."""
    print(f"\n=== Testing symbol search for '{keywords}' ===")

    try:
        # Search for symbols
        results = feed.search_symbol(keywords)

        # Display the results
        display_dataframe(results, f"Symbol Search Results for '{keywords}'")

        return results

    except Exception as e:
        logger.error(f"Error searching for symbols: {e}")
        return pd.DataFrame()


def test_exchange_rate(feed, from_currency="EUR", to_currency="USD"):
    """Test exchange rate functionality."""
    print(f"\n=== Testing exchange rate for {from_currency}/{to_currency} ===")

    try:
        # Get exchange rate
        rate_data = feed.get_exchange_rate(from_currency, to_currency)

        # Display the data
        print("Exchange Rate Data:")
        pprint(rate_data)

        return rate_data

    except Exception as e:
        logger.error(f"Error getting exchange rate: {e}")
        return {}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Alpha Vantage data feed")
    parser.add_argument("--api-key", help="Alpha Vantage API key")
    parser.add_argument("--forex-symbol", default="EURUSD", help="Forex symbol to test")
    parser.add_argument("--stock-symbol", default="MSFT", help="Stock symbol to test")
    parser.add_argument("--timeframe", default="1d", help="Timeframe to test")
    parser.add_argument(
        "--days", type=int, default=30, help="Number of days of data to request"
    )
    parser.add_argument("--search", default="Microsoft", help="Keywords to search for")
    args = parser.parse_args()

    # Get Alpha Vantage config from project configuration
    config = get_data_feed_config("alpha_vantage")

    # Override with command line arguments if provided
    if args.api_key:
        config["api_key"] = args.api_key

    # Check if API key is available
    if not config.get("api_key"):
        print("ERROR: Alpha Vantage API key is required.")
        print("Please provide it using --api-key or add it to config/default.yaml")
        return 1

    # Create the data feed
    feed = AlphaVantageDataFeed(config)

    # Test forex data
    test_forex_data(feed, args.forex_symbol, args.timeframe, args.days)

    # Test stock data
    test_stock_data(feed, args.stock_symbol, args.timeframe, args.days)

    # Test symbol search
    test_symbol_search(feed, args.search)

    # Test exchange rate
    test_exchange_rate(feed, "EUR", "USD")

    return 0


if __name__ == "__main__":
    sys.exit(main())
