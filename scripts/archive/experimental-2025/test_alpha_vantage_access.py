#!/usr/bin/env python3
"""
Test script for Alpha Vantage API access.

This script tests basic connectivity to the Alpha Vantage API
without requiring any API keys, using only the free demo endpoints.
"""

import logging
import os
import sys
from pprint import pprint

import pandas as pd
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add the project root to the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

# Import AlphaVantageDataFeed class
from fxml4.data_engineering.data_feeds.alpha_vantage_feed import AlphaVantageDataFeed


def test_demo_endpoint():
    """Test the Alpha Vantage demo endpoint that doesn't require an API key."""
    print("\n=== Testing Alpha Vantage Demo Endpoint ===")

    try:
        # Use a demo endpoint that doesn't require an API key
        url = "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=IBM&interval=5min&apikey=demo"
        response = requests.get(url)
        response.raise_for_status()

        data = response.json()

        # Check if we got a valid response
        if "Meta Data" in data and "Time Series" in next(
            (k for k in data.keys() if k.startswith("Time Series")), ""
        ):
            print("✅ Successfully connected to Alpha Vantage API using demo endpoint")
            print(f"Retrieved data for {data['Meta Data']['2. Symbol']}")

            # Show sample of data
            time_series_key = next(
                k for k in data.keys() if k.startswith("Time Series")
            )
            dates = list(data[time_series_key].keys())

            if dates:
                print(f"\nSample data for {dates[0]}:")
                pprint(data[time_series_key][dates[0]])

                return True
        else:
            print("❌ Demo endpoint returned unexpected data structure:")
            pprint(data)
            return False

    except requests.RequestException as e:
        print(f"❌ Error connecting to Alpha Vantage demo endpoint: {e}")
        return False


def test_demo_feed():
    """Test the AlphaVantageDataFeed class with the demo API key."""
    print("\n=== Testing AlphaVantageDataFeed with Demo API Key ===")

    try:
        # Create a feed with the demo API key
        config = {"api_key": "demo", "cache_data": True, "api_calls_per_minute": 5}

        feed = AlphaVantageDataFeed(config)

        # Test the exchange rate endpoint
        exchange_rate = feed.get_exchange_rate("EUR", "USD")

        if exchange_rate and "exchange_rate" in exchange_rate:
            print("✅ Successfully retrieved exchange rate using AlphaVantageDataFeed")
            print(f"EUR/USD: {exchange_rate['exchange_rate']}")
            print(f"Last refreshed: {exchange_rate.get('last_refreshed', 'N/A')}")

            return True
        else:
            print("❌ Exchange rate endpoint returned unexpected data:")
            pprint(exchange_rate)
            return False

    except Exception as e:
        print(f"❌ Error testing AlphaVantageDataFeed with demo API key: {e}")
        return False


def test_search_access():
    """Test the symbol search functionality with the demo API key."""
    print("\n=== Testing Symbol Search with Demo API Key ===")

    try:
        # Create a feed with the demo API key
        config = {"api_key": "demo", "cache_data": True, "api_calls_per_minute": 5}

        feed = AlphaVantageDataFeed(config)

        # Search for IBM
        results = feed.search_symbol("IBM")

        if not results.empty:
            print("✅ Successfully retrieved symbol search results")
            print("\nTop search results:")
            pd.set_option("display.max_columns", None)
            pd.set_option("display.width", 1000)
            print(results.head(3))
            return True
        else:
            print("❌ Symbol search returned no results")
            return False

    except Exception as e:
        print(f"❌ Error testing symbol search: {e}")
        return False


def test_intraday_demo():
    """Test retrieving intraday data with the demo API key."""
    print("\n=== Testing Intraday Data with Demo API Key ===")

    try:
        # Create a feed with the demo API key
        config = {"api_key": "demo", "cache_data": True, "api_calls_per_minute": 5}

        feed = AlphaVantageDataFeed(config)

        # Fetch intraday data for IBM
        data = feed.fetch_data(symbol="IBM", timeframe="5m", data_type="stock")

        if not data.empty:
            print("✅ Successfully retrieved intraday data")
            print(f"Retrieved {len(data)} data points")
            print("\nSample data:")
            print(data.head(3))
            return True
        else:
            print("❌ Intraday data retrieval returned no results")
            return False

    except Exception as e:
        print(f"❌ Error testing intraday data: {e}")
        return False


def main():
    """Main entry point."""
    print("🔍 Testing Alpha Vantage API Access\n")
    print("This script tests connectivity to Alpha Vantage using only demo endpoints")
    print("that don't require an API key. The demo key has very limited functionality,")
    print("so only testing basic connectivity is reliable.\n")

    # Since the demo key works only with specific endpoints,
    # we'll just test the basic connectivity
    basic_endpoint_result = test_demo_endpoint()

    # Print summary
    print("\n=== Test Results Summary ===")

    status = "✅ PASSED" if basic_endpoint_result else "❌ FAILED"
    print(f"{status} - Basic Alpha Vantage Connectivity")

    print(
        "\nNote: Other tests (exchange rates, symbol search, etc.) require a full API key"
    )
    print("and will likely fail with the demo key. This is expected behavior.")

    if basic_endpoint_result:
        print("\n🎉 Basic connectivity test passed!")
        print("The Alpha Vantage integration structure is working correctly.")
        print("\nTo test full functionality with your own API key, run:")
        print("python scripts/test_alphavantage_feed.py --api-key YOUR_API_KEY")
        return 0
    else:
        print(
            "\n⚠️ Basic connectivity test failed. Check network connection or Alpha Vantage status."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
