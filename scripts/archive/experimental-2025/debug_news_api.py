#!/usr/bin/env python
"""Debug script for Alpha Vantage NEWS_SENTIMENT API."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import os
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_direct_api_call():
    """Test direct API call to understand response format."""
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("No API key found!")
        return

    print(f"API Key: ...{api_key[-4:]}")

    # Test 1: Basic NEWS_SENTIMENT call
    print("\n1. Testing basic NEWS_SENTIMENT endpoint...")
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&apikey={api_key}"

    try:
        response = requests.get(url)
        data = response.json()

        print(f"Status Code: {response.status_code}")
        print(f"Response Keys: {list(data.keys())}")

        if "Error Message" in data:
            print(f"Error: {data['Error Message']}")
        elif "Information" in data:
            print(f"Info: {data['Information']}")
        elif "feed" in data:
            print(f"Success! Found {len(data['feed'])} articles")
            print(
                f"First article keys: {list(data['feed'][0].keys()) if data['feed'] else 'No articles'}"
            )
        else:
            print(f"Unexpected response: {json.dumps(data, indent=2)[:500]}...")

    except Exception as e:
        print(f"Error: {e}")

    # Test 2: With forex tickers
    print("\n2. Testing with FOREX tickers...")
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=FOREX:USD&apikey={api_key}"

    try:
        response = requests.get(url)
        data = response.json()

        if "feed" in data:
            print(f"Success! Found {len(data['feed'])} articles")

            # Check for forex-related articles
            forex_articles = 0
            for article in data["feed"]:
                ticker_sentiments = article.get("ticker_sentiment", [])
                for ts in ticker_sentiments:
                    if ts.get("ticker", "").startswith("FOREX:"):
                        forex_articles += 1
                        print(f"  Found FOREX ticker: {ts['ticker']}")
                        break

            print(f"Articles with FOREX tickers: {forex_articles}")
        else:
            print("No feed data in response")

    except Exception as e:
        print(f"Error: {e}")

    # Test 3: With topics
    print("\n3. Testing with forex-related topics...")
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&topics=economy_monetary,financial_markets&apikey={api_key}&limit=10"

    try:
        response = requests.get(url)
        data = response.json()

        if "feed" in data:
            print(f"Success! Found {len(data['feed'])} articles")

            if data["feed"]:
                article = data["feed"][0]
                print(f"\nFirst article:")
                print(f"  Title: {article.get('title', 'N/A')[:80]}...")
                print(f"  Source: {article.get('source', 'N/A')}")
                print(f"  Time: {article.get('time_published', 'N/A')}")
                print(f"  Topics: {[t['topic'] for t in article.get('topics', [])]}")

    except Exception as e:
        print(f"Error: {e}")

    # Test 4: Check if it's a premium feature
    print("\n4. Checking API tier...")
    # Try a basic function that works on free tier
    url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=EUR&to_currency=USD&apikey={api_key}"

    try:
        response = requests.get(url)
        data = response.json()

        if "Realtime Currency Exchange Rate" in data:
            print("✓ API key is valid and working")
        else:
            print("✗ API key might be invalid")

    except Exception as e:
        print(f"Error: {e}")


def test_available_tickers():
    """Test what ticker formats work."""
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        return

    print("\n5. Testing different ticker formats...")

    ticker_formats = [
        "USD",
        "FOREX:USD",
        "EUR",
        "FOREX:EUR",
        "EURUSD",
        "EUR/USD",
        "CURRENCY:USD",
        "FX:USD",
    ]

    for ticker in ticker_formats:
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&apikey={api_key}&limit=1"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if "feed" in data and data["feed"]:
                    # Check if any article has this ticker
                    found = False
                    for article in data["feed"]:
                        for ts in article.get("ticker_sentiment", []):
                            if ticker in ts.get("ticker", ""):
                                found = True
                                break

                    if found:
                        print(f"  ✓ {ticker} - Found matching articles")
                    else:
                        print(f"  ⚠ {ticker} - No matching ticker sentiment")
                else:
                    print(f"  ✗ {ticker} - No feed data")
            else:
                print(f"  ✗ {ticker} - HTTP {response.status_code}")

        except Exception as e:
            print(f"  ✗ {ticker} - Error: {e}")

        # Rate limiting
        import time

        time.sleep(0.5)


if __name__ == "__main__":
    print("=" * 60)
    print("ALPHA VANTAGE NEWS_SENTIMENT API DEBUG")
    print("=" * 60)

    test_direct_api_call()
    test_available_tickers()

    print("\n" + "=" * 60)
    print("Debug complete!")
    print("=" * 60)
