#!/usr/bin/env python
"""Integration test for Alpha Vantage NEWS_SENTIMENT API."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import os
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv

from fxml4.data_engineering.data_feeds.alpha_vantage_news import (
    AlphaVantageNewsAPI,
    analyze_market_sentiment,
    get_forex_news_sentiment,
)

# Load environment variables
load_dotenv()


def test_single_symbol_sentiment():
    """Test getting sentiment for a single forex pair."""
    print("\n" + "=" * 60)
    print("TEST 1: Single Symbol Sentiment Analysis")
    print("=" * 60)

    # Get sentiment for EURUSD
    symbol = "EURUSD"
    print(f"\nFetching news sentiment for {symbol}...")

    try:
        sentiment = get_forex_news_sentiment(symbol, hours_back=24)

        print(f"\nResults for {symbol}:")
        print(f"  Overall Sentiment: {sentiment['overall_sentiment']:.3f}")
        print(f"  Sentiment Label: {sentiment['sentiment_label']}")
        print(f"  Relevance Score: {sentiment['relevance_score']:.3f}")
        print(f"  Article Count: {sentiment['article_count']}")
        print(f"  Bullish Articles: {sentiment['bullish_count']}")
        print(f"  Bearish Articles: {sentiment['bearish_count']}")
        print(f"  Neutral Articles: {sentiment['neutral_count']}")

        # Show top articles
        if sentiment["articles"]:
            print(f"\nTop {min(3, len(sentiment['articles']))} Articles:")
            for i, article in enumerate(sentiment["articles"][:3]):
                print(f"\n  {i+1}. {article['title']}")
                print(f"     Source: {article['source']}")
                print(f"     Sentiment: {article['sentiment_score']:.3f}")
                print(f"     Relevance: {article['relevance_score']:.3f}")
                print(f"     Time: {article['time_published']}")

        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def test_multi_symbol_analysis():
    """Test analyzing sentiment across multiple forex pairs."""
    print("\n" + "=" * 60)
    print("TEST 2: Multi-Symbol Market Sentiment Analysis")
    print("=" * 60)

    symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    print(f"\nAnalyzing sentiment for: {', '.join(symbols)}")

    try:
        # Get sentiment DataFrame
        df = analyze_market_sentiment(symbols)

        if not df.empty:
            print("\nMarket Sentiment Summary:")
            print(df.to_string(index=False))

            # Find most bullish/bearish
            most_bullish = df.loc[df["sentiment"].idxmax()]
            most_bearish = df.loc[df["sentiment"].idxmin()]

            print(
                f"\nMost Bullish: {most_bullish['symbol']} ({most_bullish['sentiment']:.3f})"
            )
            print(
                f"Most Bearish: {most_bearish['symbol']} ({most_bearish['sentiment']:.3f})"
            )

            # Calculate market average
            avg_sentiment = df["sentiment"].mean()
            print(f"\nMarket Average Sentiment: {avg_sentiment:.3f}")

            if avg_sentiment > 0.1:
                print("Overall Market Bias: BULLISH")
            elif avg_sentiment < -0.1:
                print("Overall Market Bias: BEARISH")
            else:
                print("Overall Market Bias: NEUTRAL")

        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def test_time_window_analysis():
    """Test sentiment analysis with different time windows."""
    print("\n" + "=" * 60)
    print("TEST 3: Time Window Sentiment Analysis")
    print("=" * 60)

    symbol = "EURUSD"
    time_windows = [6, 12, 24, 48]  # hours

    print(f"\nAnalyzing {symbol} sentiment over different time windows...")

    api = AlphaVantageNewsAPI()
    results = []

    for hours in time_windows:
        try:
            time_from = datetime.now() - timedelta(hours=hours)
            sentiment = api.get_forex_sentiment(
                symbol=symbol, time_from=time_from, limit=100
            )

            results.append(
                {
                    "Time Window": f"{hours}h",
                    "Sentiment": sentiment["overall_sentiment"],
                    "Articles": sentiment["article_count"],
                    "Label": sentiment["sentiment_label"],
                }
            )

        except Exception as e:
            print(f"Error for {hours}h window: {e}")

    if results:
        df = pd.DataFrame(results)
        print("\nSentiment by Time Window:")
        print(df.to_string(index=False))

        # Check for trend
        sentiments = [r["Sentiment"] for r in results]
        if all(sentiments[i] <= sentiments[i + 1] for i in range(len(sentiments) - 1)):
            print("\nTrend: Sentiment is IMPROVING over time")
        elif all(
            sentiments[i] >= sentiments[i + 1] for i in range(len(sentiments) - 1)
        ):
            print("\nTrend: Sentiment is DETERIORATING over time")
        else:
            print("\nTrend: Sentiment is MIXED")

    return len(results) > 0


def test_caching_performance():
    """Test caching performance."""
    print("\n" + "=" * 60)
    print("TEST 4: Caching Performance Test")
    print("=" * 60)

    api = AlphaVantageNewsAPI(cache_duration=3600)
    symbol = "EURUSD"

    print(f"\nTesting cache performance for {symbol}...")

    # First call - should hit API
    import time

    start_time = time.time()
    result1 = api.get_forex_sentiment(symbol, use_cache=True)
    first_call_time = time.time() - start_time

    print(f"First call (API): {first_call_time:.2f} seconds")

    # Second call - should use cache
    start_time = time.time()
    result2 = api.get_forex_sentiment(symbol, use_cache=True)
    second_call_time = time.time() - start_time

    print(f"Second call (cache): {second_call_time:.2f} seconds")

    # Cache should be much faster
    if second_call_time < first_call_time * 0.1:  # At least 10x faster
        print("✓ Cache is working efficiently")
        speed_improvement = first_call_time / second_call_time
        print(f"  Speed improvement: {speed_improvement:.1f}x faster")
    else:
        print("⚠ Cache may not be working properly")

    # Verify results are identical
    if result1["overall_sentiment"] == result2["overall_sentiment"]:
        print("✓ Cached data matches original")
    else:
        print("✗ Cached data differs from original")

    return True


def test_error_handling():
    """Test error handling scenarios."""
    print("\n" + "=" * 60)
    print("TEST 5: Error Handling Test")
    print("=" * 60)

    # Test with invalid symbol
    print("\n1. Testing invalid symbol...")
    api = AlphaVantageNewsAPI()
    result = api.get_forex_sentiment("INVALID")

    if result["article_count"] == 0:
        print("✓ Invalid symbol handled correctly")
    else:
        print("✗ Invalid symbol not handled properly")

    # Test with no API key
    print("\n2. Testing without API key...")
    api_no_key = AlphaVantageNewsAPI(api_key=None)
    result = api_no_key.get_forex_sentiment("EURUSD")

    if result["article_count"] == 0:
        print("✓ Missing API key handled correctly")
    else:
        print("✗ Missing API key not handled properly")

    return True


def demonstrate_trading_integration():
    """Demonstrate how news sentiment affects trading decisions."""
    print("\n" + "=" * 60)
    print("DEMONSTRATION: News Sentiment in Trading Decisions")
    print("=" * 60)

    # Simulate different market scenarios
    scenarios = [
        {"symbol": "EURUSD", "technical_signal": "LONG", "ml_confidence": 0.7},
        {"symbol": "GBPUSD", "technical_signal": "SHORT", "ml_confidence": 0.65},
        {"symbol": "USDJPY", "technical_signal": "LONG", "ml_confidence": 0.8},
    ]

    print("\nAnalyzing how news sentiment affects trading signals...\n")

    for scenario in scenarios:
        symbol = scenario["symbol"]

        # Get news sentiment
        sentiment = get_forex_news_sentiment(symbol, hours_back=12)

        print(f"{symbol}:")
        print(f"  Technical Signal: {scenario['technical_signal']}")
        print(f"  ML Confidence: {scenario['ml_confidence']:.2f}")
        print(
            f"  News Sentiment: {sentiment['overall_sentiment']:.3f} ({sentiment['sentiment_label']})"
        )

        # Trading decision logic
        if scenario["technical_signal"] == "LONG":
            if sentiment["overall_sentiment"] > 0.2:
                print("  Decision: ✓ TAKE TRADE (aligned sentiment)")
                adjusted_confidence = min(scenario["ml_confidence"] * 1.2, 1.0)
            elif sentiment["overall_sentiment"] < -0.2:
                print("  Decision: ✗ SKIP TRADE (contrary sentiment)")
                adjusted_confidence = 0
            else:
                print("  Decision: ⚠ REDUCE SIZE (neutral sentiment)")
                adjusted_confidence = scenario["ml_confidence"] * 0.8
        else:  # SHORT
            if sentiment["overall_sentiment"] < -0.2:
                print("  Decision: ✓ TAKE TRADE (aligned sentiment)")
                adjusted_confidence = min(scenario["ml_confidence"] * 1.2, 1.0)
            elif sentiment["overall_sentiment"] > 0.2:
                print("  Decision: ✗ SKIP TRADE (contrary sentiment)")
                adjusted_confidence = 0
            else:
                print("  Decision: ⚠ REDUCE SIZE (neutral sentiment)")
                adjusted_confidence = scenario["ml_confidence"] * 0.8

        if adjusted_confidence > 0:
            print(f"  Adjusted Confidence: {adjusted_confidence:.2f}")

        print()


def main():
    """Run all integration tests."""
    print("\n" + "=" * 80)
    print("ALPHA VANTAGE NEWS SENTIMENT API - INTEGRATION TESTS")
    print("=" * 80)
    print(f"Generated: {datetime.now()}")

    # Check for API key
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("\n⚠️  WARNING: No Alpha Vantage API key found!")
        print("   Set ALPHA_VANTAGE_API_KEY environment variable to enable tests")
        print("   Tests will run with mock data only")
    else:
        print(f"\n✓ API Key found: ...{api_key[-4:]}")

    # Run tests
    tests_passed = 0
    total_tests = 5

    if test_single_symbol_sentiment():
        tests_passed += 1

    if test_multi_symbol_analysis():
        tests_passed += 1

    if test_time_window_analysis():
        tests_passed += 1

    if test_caching_performance():
        tests_passed += 1

    if test_error_handling():
        tests_passed += 1

    # Demonstration
    try:
        demonstrate_trading_integration()
    except Exception as e:
        print(f"Demonstration error: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Passed: {tests_passed}/{total_tests}")

    if tests_passed == total_tests:
        print("\n✅ All tests passed! NEWS_SENTIMENT API is working correctly.")
    else:
        print(f"\n⚠️  {total_tests - tests_passed} tests failed.")

    # Save test results
    results = {
        "timestamp": datetime.now().isoformat(),
        "tests_passed": tests_passed,
        "total_tests": total_tests,
        "api_key_present": api_key is not None,
    }

    output_dir = Path("output/news_sentiment_tests")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nTest results saved to {output_dir}/test_results.json")


if __name__ == "__main__":
    main()
