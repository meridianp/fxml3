#!/usr/bin/env python3
"""
Alpha Vantage API connection test for FXML4.

This script tests the connection to Alpha Vantage API
and verifies basic functionality like retrieving forex data
and technical indicators.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Alpha Vantage API configuration
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_RATE_LIMIT_DELAY = 15  # seconds (Alpha Vantage free tier: 5 calls/minute)


def get_api_key() -> str:
    """Get Alpha Vantage API key from environment variable.

    Returns:
        API key

    Raises:
        ValueError: If API key is not set
    """
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY environment variable not set")

    return api_key


def test_forex_data(api_key: str, from_currency: str, to_currency: str) -> bool:
    """Test retrieving forex data from Alpha Vantage.

    Args:
        api_key: Alpha Vantage API key
        from_currency: From currency (e.g., "GBP")
        to_currency: To currency (e.g., "USD")

    Returns:
        True if data retrieval successful, False otherwise
    """
    params = {
        "function": "FX_DAILY",
        "from_symbol": from_currency,
        "to_symbol": to_currency,
        "outputsize": "compact",
        "datatype": "json",
        "apikey": api_key,
    }

    try:
        logger.info(f"Retrieving forex data for {from_currency}/{to_currency}")
        response = requests.get(ALPHA_VANTAGE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # Check for error messages
        if "Error Message" in data:
            logger.error(f"Alpha Vantage API error: {data['Error Message']}")
            return False

        # Check for rate limit messages
        if "Note" in data and "call frequency" in data["Note"]:
            logger.warning(f"Alpha Vantage API rate limit warning: {data['Note']}")

        # Check if time series data is present
        if "Time Series FX (Daily)" not in data:
            logger.error("No forex data received")
            return False

        # Get time series data
        time_series = data["Time Series FX (Daily)"]

        # Print a few sample data points
        logger.info(f"Received {len(time_series)} data points")

        sample_dates = list(time_series.keys())[:5]
        for date in sample_dates:
            values = time_series[date]
            logger.info(
                f"{date}: Open: {values['1. open']}, Close: {values['4. close']}"
            )

        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving forex data: {e}")
        return False
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error parsing forex data response: {e}")
        return False


def test_technical_indicator(
    api_key: str, from_currency: str, to_currency: str, indicator: str
) -> bool:
    """Test retrieving technical indicator data from Alpha Vantage.

    Args:
        api_key: Alpha Vantage API key
        from_currency: From currency (e.g., "GBP")
        to_currency: To currency (e.g., "USD")
        indicator: Technical indicator function (e.g., "RSI", "SMA", "EMA")

    Returns:
        True if data retrieval successful, False otherwise
    """
    # Parameters for the technical indicator
    params = {
        "function": indicator,
        "symbol": f"{from_currency}{to_currency}",
        "interval": "daily",
        "time_period": "14",  # Default for most indicators
        "series_type": "close",
        "datatype": "json",
        "apikey": api_key,
    }

    # Special handling for SMA and EMA which require additional parameters
    if indicator in ["SMA", "EMA"]:
        params["time_period"] = "20"

    try:
        logger.info(f"Retrieving {indicator} data for {from_currency}{to_currency}")
        response = requests.get(ALPHA_VANTAGE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # Check for error messages
        if "Error Message" in data:
            logger.error(f"Alpha Vantage API error: {data['Error Message']}")
            return False

        # Check for rate limit messages
        if "Note" in data and "call frequency" in data["Note"]:
            logger.warning(f"Alpha Vantage API rate limit warning: {data['Note']}")

        # Check if technical indicator data is present
        indicator_key = f"Technical Analysis: {indicator}"
        if indicator_key not in data:
            logger.error(f"No {indicator} data received")
            return False

        # Get indicator data
        indicator_data = data[indicator_key]

        # Print a few sample data points
        logger.info(f"Received {len(indicator_data)} data points")

        sample_dates = list(indicator_data.keys())[:5]
        for date in sample_dates:
            values = indicator_data[date]
            logger.info(f"{date}: {indicator}: {list(values.values())[0]}")

        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving {indicator} data: {e}")
        return False
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error parsing {indicator} data response: {e}")
        return False


def test_market_sentiment(api_key: str, ticker: str = "FOREX:GBP/USD") -> bool:
    """Test retrieving market sentiment data from Alpha Vantage.

    Args:
        api_key: Alpha Vantage API key
        ticker: Ticker symbol (e.g., "FOREX:GBP/USD")

    Returns:
        True if data retrieval successful, False otherwise
    """
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker,
        "topics": "financial_markets",
        "sort": "RELEVANCE",
        "limit": "10",
        "apikey": api_key,
    }

    try:
        logger.info(f"Retrieving market sentiment for {ticker}")
        response = requests.get(ALPHA_VANTAGE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # Check for error messages
        if "Error Message" in data:
            logger.error(f"Alpha Vantage API error: {data['Error Message']}")
            return False

        # Check for rate limit messages
        if "Note" in data and "call frequency" in data["Note"]:
            logger.warning(f"Alpha Vantage API rate limit warning: {data['Note']}")

        # Check if feed data is present
        if "feed" not in data:
            logger.error("No news sentiment data received")
            return False

        # Get news feed
        feed = data["feed"]

        # Print a few sample news items
        logger.info(f"Received {len(feed)} news items")

        for item in feed[:3]:
            title = item.get("title", "No title")
            sentiment = item.get("overall_sentiment_score", "N/A")
            logger.info(f"Title: {title}")
            logger.info(f"Sentiment: {sentiment}")
            logger.info("---")

        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving market sentiment: {e}")
        return False
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error parsing market sentiment response: {e}")
        return False


def save_sample_data(
    api_key: str, from_currency: str, to_currency: str, output_dir: str
) -> bool:
    """Save sample forex data to file.

    Args:
        api_key: Alpha Vantage API key
        from_currency: From currency (e.g., "GBP")
        to_currency: To currency (e.g., "USD")
        output_dir: Output directory

    Returns:
        True if data saving successful, False otherwise
    """
    params = {
        "function": "FX_DAILY",
        "from_symbol": from_currency,
        "to_symbol": to_currency,
        "outputsize": "full",
        "datatype": "json",
        "apikey": api_key,
    }

    try:
        logger.info(f"Retrieving forex data for {from_currency}/{to_currency}")
        response = requests.get(ALPHA_VANTAGE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # Check for error messages
        if "Error Message" in data:
            logger.error(f"Alpha Vantage API error: {data['Error Message']}")
            return False

        # Convert to DataFrame
        if "Time Series FX (Daily)" not in data:
            logger.error("No forex data received")
            return False

        time_series = data["Time Series FX (Daily)"]

        # Create DataFrame
        records = []
        for date_str, values in time_series.items():
            record = {
                "date": pd.Timestamp(date_str),
                "open": float(values["1. open"]),
                "high": float(values["2. high"]),
                "low": float(values["3. low"]),
                "close": float(values["4. close"]),
            }
            records.append(record)

        df = pd.DataFrame(records)

        # Sort by date
        df.sort_values("date", inplace=True)

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Save to CSV and Parquet
        symbol = f"{from_currency}{to_currency}"
        csv_file = os.path.join(output_dir, f"{symbol}_daily.csv")
        parquet_file = os.path.join(output_dir, f"{symbol}_daily.parquet")

        df.to_csv(csv_file, index=False)
        df.to_parquet(parquet_file, index=False)

        logger.info(f"Saved {len(df)} records to {csv_file} and {parquet_file}")

        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving forex data: {e}")
        return False
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error parsing forex data response: {e}")
        return False
    except Exception as e:
        logger.error(f"Error saving data: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Alpha Vantage API connection")
    parser.add_argument("--from-currency", default="GBP", help="From currency")
    parser.add_argument("--to-currency", default="USD", help="To currency")
    parser.add_argument("--save-data", action="store_true", help="Save sample data")
    parser.add_argument(
        "--output-dir",
        default="./alpha_vantage_data",
        help="Output directory for sample data",
    )
    args = parser.parse_args()

    try:
        # Get API key
        api_key = get_api_key()

        # Test forex data
        if not test_forex_data(api_key, args.from_currency, args.to_currency):
            logger.error("Forex data test failed")
            return 1

        logger.info("Forex data test successful")

        # Wait for rate limit
        logger.info(
            f"Waiting {ALPHA_VANTAGE_RATE_LIMIT_DELAY} seconds for rate limiting..."
        )
        time.sleep(ALPHA_VANTAGE_RATE_LIMIT_DELAY)

        # Test technical indicator
        if not test_technical_indicator(
            api_key, args.from_currency, args.to_currency, "RSI"
        ):
            logger.error("Technical indicator test failed")
            return 1

        logger.info("Technical indicator test successful")

        # Wait for rate limit
        logger.info(
            f"Waiting {ALPHA_VANTAGE_RATE_LIMIT_DELAY} seconds for rate limiting..."
        )
        time.sleep(ALPHA_VANTAGE_RATE_LIMIT_DELAY)

        # Test market sentiment
        ticker = f"FOREX:{args.from_currency}/{args.to_currency}"
        if not test_market_sentiment(api_key, ticker):
            logger.error("Market sentiment test failed")
            return 1

        logger.info("Market sentiment test successful")

        # Save sample data if requested
        if args.save_data:
            # Wait for rate limit
            logger.info(
                f"Waiting {ALPHA_VANTAGE_RATE_LIMIT_DELAY} seconds for rate limiting..."
            )
            time.sleep(ALPHA_VANTAGE_RATE_LIMIT_DELAY)

            if not save_sample_data(
                api_key, args.from_currency, args.to_currency, args.output_dir
            ):
                logger.error("Save sample data failed")
                return 1

            logger.info("Save sample data successful")

        logger.info("All tests completed successfully")
        return 0

    except ValueError as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
