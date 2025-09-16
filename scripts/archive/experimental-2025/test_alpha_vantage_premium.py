#!/usr/bin/env python3
"""
Test script for Alpha Vantage Premium API.

This script tests the enhanced capabilities of the Alpha Vantage premium API tier,
including increased rate limits and full historical data access.

It compares performance between standard and full output sizes,
and verifies that the premium tier enhancements work as expected.
"""

import argparse
import concurrent.futures
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm

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


def setup_data_feed(api_key: str, premium: bool = True) -> AlphaVantageDataFeed:
    """Set up a data feed with the given API key and premium status.

    Args:
        api_key: Alpha Vantage API key
        premium: Whether to use premium tier settings

    Returns:
        AlphaVantageDataFeed instance
    """
    config = {
        "api_key": api_key,
        "cache_data": False,  # Disable caching for testing
        "api_calls_per_minute": 75 if premium else 5,
        "premium_tier": premium,
        "symbols": ["EURUSD", "GBPUSD", "USDJPY", "MSFT", "AAPL", "GOOGL"],
    }

    return AlphaVantageDataFeed(config)


def test_rate_limits(
    feed: AlphaVantageDataFeed, num_requests: int = 30
) -> Tuple[bool, float, List[float]]:
    """Test the rate limits of the Alpha Vantage API.

    This function makes a series of rapid API calls to test if the
    premium tier rate limiting is working correctly.

    Args:
        feed: AlphaVantageDataFeed instance
        num_requests: Number of requests to make

    Returns:
        Tuple containing:
            - Success flag (bool)
            - Total time in seconds (float)
            - List of response times per request (List[float])
    """
    print(f"\n=== Testing Rate Limits ({num_requests} requests) ===")
    print(f"API calls per minute: {feed.api_calls_per_minute}")

    response_times = []
    start_time = time.time()
    success = True

    # Make multiple API calls to test rate limiting
    try:
        for i in tqdm(range(num_requests), desc="Making API calls"):
            request_start = time.time()

            # Make a simple API call - alternate between different calls to avoid caching effects
            if i % 3 == 0:
                # FX rate
                data = feed.get_exchange_rate("EUR", "USD")
                if not data or "exchange_rate" not in data:
                    success = False
                    logger.error(f"Request {i+1} failed: Invalid exchange rate data")
            elif i % 3 == 1:
                # Search
                data = feed.search_symbol("Microsoft")
                if data.empty:
                    success = False
                    logger.error(f"Request {i+1} failed: Empty search results")
            else:
                # Forex data
                data = feed.fetch_data(
                    symbol="EURUSD", timeframe="1d", data_type="forex"
                )
                if data.empty:
                    success = False
                    logger.error(f"Request {i+1} failed: Empty forex data")

            request_time = time.time() - request_start
            response_times.append(request_time)

    except Exception as e:
        success = False
        logger.error(f"Rate limit test failed: {e}")

    end_time = time.time()
    total_time = end_time - start_time

    print(f"Total time for {num_requests} requests: {total_time:.2f} seconds")
    print(
        f"Average time per request: {sum(response_times) / len(response_times):.2f} seconds"
    )

    # Calculate effective requests per minute
    req_per_minute = (num_requests / total_time) * 60
    print(f"Effective requests per minute: {req_per_minute:.2f}")

    if success:
        print("✅ Rate limit test passed successfully!")
    else:
        print("❌ Rate limit test failed")

    return success, total_time, response_times


def test_intraday_full_history(
    feed: AlphaVantageDataFeed, symbol: str = "EURUSD"
) -> Tuple[bool, int]:
    """Test retrieving full historical intraday data.

    This function verifies that full historical data is retrieved for intraday
    timeframes when using premium tier.

    Args:
        feed: AlphaVantageDataFeed instance
        symbol: Symbol to retrieve data for

    Returns:
        Tuple containing:
            - Success flag (bool)
            - Number of data points retrieved (int)
    """
    print(f"\n=== Testing Full Historical Intraday Data for {symbol} ===")

    try:
        # Get intraday data (should be full history with premium tier)
        data = feed.fetch_data(
            symbol=symbol,
            timeframe="1h",
            data_type="forex" if symbol in ["EURUSD", "GBPUSD", "USDJPY"] else "stock",
        )

        # Show summary
        print(f"Retrieved {len(data)} data points")
        print(f"Timeframe: From {data.index.min()} to {data.index.max()}")
        print(f"Data span: {(data.index.max() - data.index.min()).days} days")

        # Show sample data
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 120)
        print("\nSample data:")
        print(data.head(3))

        if len(data) > 100:
            print("✅ Full historical data retrieved successfully")
            return True, len(data)
        else:
            print("❌ Limited data retrieved, premium tier may not be working")
            return False, len(data)

    except Exception as e:
        logger.error(f"Error testing full historical data: {e}")
        return False, 0


def compare_output_sizes(
    feed: AlphaVantageDataFeed, symbol: str = "MSFT"
) -> Tuple[bool, Dict[str, Any]]:
    """Compare performance between standard and full output sizes.

    This function compares the data retrieval performance between
    standard (compact) and full output sizes.

    Args:
        feed: AlphaVantageDataFeed instance
        symbol: Symbol to retrieve data for

    Returns:
        Tuple containing:
            - Success flag (bool)
            - Dictionary with comparison metrics
    """
    print(f"\n=== Comparing Output Sizes for {symbol} ===")

    results = {"compact": {"time": 0, "points": 0}, "full": {"time": 0, "points": 0}}

    try:
        # First test with explicit compact output_size parameter
        start_time = time.time()
        data_compact = feed.fetch_data(
            symbol=symbol, timeframe="1d", data_type="stock", output_size="compact"
        )
        compact_time = time.time() - start_time

        print(
            f"Compact output size: {len(data_compact)} data points in {compact_time:.2f} seconds"
        )

        results["compact"]["time"] = compact_time
        results["compact"]["points"] = len(data_compact)

        # Wait to avoid rate limiting issues
        time.sleep(2)

        # Then test with explicit full output_size parameter
        start_time = time.time()
        data_full = feed.fetch_data(
            symbol=symbol, timeframe="1d", data_type="stock", output_size="full"
        )
        full_time = time.time() - start_time

        print(
            f"Full output size: {len(data_full)} data points in {full_time:.2f} seconds"
        )

        results["full"]["time"] = full_time
        results["full"]["points"] = len(data_full)

        # Show comparison
        print("\nComparison:")
        print(
            f"Compact data span: {(data_compact.index.max() - data_compact.index.min()).days} days"
        )
        print(
            f"Full data span: {(data_full.index.max() - data_full.index.min()).days} days"
        )

        # Calculate efficiency (points per second)
        compact_efficiency = len(data_compact) / compact_time
        full_efficiency = len(data_full) / full_time

        print(f"Compact efficiency: {compact_efficiency:.2f} points/second")
        print(f"Full efficiency: {full_efficiency:.2f} points/second")

        results["compact"]["efficiency"] = compact_efficiency
        results["full"]["efficiency"] = full_efficiency

        if len(data_full) > len(data_compact):
            print("✅ Full output size retrieved more data than compact")
            success = True
        else:
            print("❓ Full output size did not retrieve more data than compact")
            success = False

        return success, results

    except Exception as e:
        logger.error(f"Error comparing output sizes: {e}")
        return False, results


def test_parallel_requests(feed: AlphaVantageDataFeed, num_parallel: int = 5) -> bool:
    """Test running parallel requests with the premium tier.

    This function tests the ability to make multiple concurrent API calls
    with the premium tier, which should handle them efficiently.

    Args:
        feed: AlphaVantageDataFeed instance
        num_parallel: Number of parallel requests to make

    Returns:
        Success flag (bool)
    """
    print(f"\n=== Testing Parallel Requests ({num_parallel} concurrent) ===")

    # Define different request types to run in parallel
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "MSFT", "AAPL"][:num_parallel]
    success = True

    try:
        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=num_parallel
        ) as executor:
            futures = []

            for i, symbol in enumerate(symbols):
                if i % 2 == 0:
                    # Forex data
                    futures.append(
                        executor.submit(
                            feed.fetch_data,
                            symbol=symbol,
                            timeframe="1d",
                            data_type=(
                                "forex"
                                if symbol in ["EURUSD", "GBPUSD", "USDJPY"]
                                else "stock"
                            ),
                        )
                    )
                else:
                    # Stock data
                    futures.append(
                        executor.submit(
                            feed.fetch_data,
                            symbol=symbol,
                            timeframe="1d",
                            data_type="stock",
                        )
                    )

            # Wait for results and check they're valid
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    data = future.result()
                    if data.empty:
                        logger.error(f"Parallel request {i+1} returned empty data")
                        success = False
                    else:
                        print(
                            f"Parallel request {i+1} retrieved {len(data)} data points"
                        )
                except Exception as e:
                    logger.error(f"Parallel request {i+1} failed: {e}")
                    success = False

        total_time = time.time() - start_time
        print(
            f"Total time for {num_parallel} parallel requests: {total_time:.2f} seconds"
        )
        print(f"Average time per request: {total_time / num_parallel:.2f} seconds")

        if success:
            print("✅ Parallel request test passed successfully")
        else:
            print("❌ Parallel request test failed")

        return success

    except Exception as e:
        logger.error(f"Error testing parallel requests: {e}")
        return False


def plot_rate_limit_metrics(
    standard_time: float,
    standard_rpm: float,
    premium_time: float,
    premium_rpm: float,
    num_requests: int = 30,
):
    """Plot rate limit metrics comparison between standard and premium tiers.

    Args:
        standard_time: Total time for standard tier requests
        standard_rpm: Requests per minute for standard tier
        premium_time: Total time for premium tier requests
        premium_rpm: Requests per minute for premium tier
        num_requests: Number of requests made in each test
    """
    plt.figure(figsize=(10, 6))

    # Plot 1: Total time comparison
    plt.subplot(1, 2, 1)
    bars = plt.bar(
        ["Standard", "Premium"], [standard_time, premium_time], color=["red", "green"]
    )
    plt.title(f"Total Time for {num_requests} Requests")
    plt.ylabel("Time (seconds)")
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Add data labels
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.1f}s",
            ha="center",
            va="bottom",
        )

    # Plot 2: Requests per minute comparison
    plt.subplot(1, 2, 2)
    bars = plt.bar(
        ["Standard", "Premium"], [standard_rpm, premium_rpm], color=["red", "green"]
    )
    plt.title("Effective Requests Per Minute")
    plt.ylabel("Requests/minute")
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Add data labels and highlight limits
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.1f}",
            ha="center",
            va="bottom",
        )

    # Add reference lines for the tier limits
    plt.axhline(y=5, color="r", linestyle="--", alpha=0.5, label="Standard Limit (5)")
    plt.axhline(y=75, color="g", linestyle="--", alpha=0.5, label="Premium Limit (75)")
    plt.legend()

    plt.tight_layout()
    plt.show()


def plot_historical_data_comparison(
    premium_points: int, standard_points: int, symbol: str = "EURUSD"
):
    """Plot comparison between standard and premium historical data points.

    Args:
        premium_points: Number of data points with premium tier
        standard_points: Number of data points with standard tier
        symbol: Symbol used for the test
    """
    plt.figure(figsize=(8, 6))

    bars = plt.bar(
        ["Standard", "Premium"],
        [standard_points, premium_points],
        color=["red", "green"],
    )
    plt.title(f"Historical Data Points for {symbol}")
    plt.ylabel("Number of Data Points")
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Add data labels
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height}",
            ha="center",
            va="bottom",
        )

    # Add multiplier label
    if standard_points > 0:
        multiplier = premium_points / standard_points
        plt.text(
            1.5,
            premium_points / 2,
            f"{multiplier:.1f}x more data",
            ha="center",
            va="center",
            bbox=dict(facecolor="white", alpha=0.5),
        )

    plt.tight_layout()
    plt.show()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Alpha Vantage Premium API")
    parser.add_argument("--api-key", help="Alpha Vantage API key")
    parser.add_argument(
        "--requests",
        type=int,
        default=30,
        help="Number of requests for rate limit test",
    )
    parser.add_argument(
        "--parallel", type=int, default=5, help="Number of parallel requests to test"
    )
    parser.add_argument("--symbol", default="EURUSD", help="Symbol to use for testing")
    parser.add_argument(
        "--stock", default="MSFT", help="Stock symbol to use for testing"
    )
    parser.add_argument("--no-plots", action="store_true", help="Disable plotting")
    args = parser.parse_args()

    # Get API key from arguments or config
    api_key = args.api_key
    if not api_key:
        config = get_data_feed_config("alpha_vantage")
        api_key = config.get("api_key", "")

    if not api_key:
        print("ERROR: Alpha Vantage API key is required")
        print("Please provide it using --api-key or add it to config/default.yaml")
        return 1

    print("=== Alpha Vantage Premium API Test ===")
    print("This test verifies that premium tier features are working correctly.")
    print("It will compare performance between standard and premium tiers.")

    # Test with premium tier configuration
    print("\n🚀 TESTING WITH PREMIUM TIER CONFIGURATION")
    premium_feed = setup_data_feed(api_key, premium=True)

    # Test rate limits with premium tier
    premium_success, premium_time, premium_response_times = test_rate_limits(
        premium_feed, num_requests=args.requests
    )

    # Calculate effective requests per minute
    premium_rpm = (args.requests / premium_time) * 60

    # Test historical data with premium tier
    premium_history_success, premium_points = test_intraday_full_history(
        premium_feed, symbol=args.symbol
    )

    # Test output size comparison
    output_size_success, output_metrics = compare_output_sizes(
        premium_feed, symbol=args.stock
    )

    # Test parallel requests
    parallel_success = test_parallel_requests(premium_feed, num_parallel=args.parallel)

    # Now test with standard tier configuration for comparison
    print("\n🚀 TESTING WITH STANDARD TIER CONFIGURATION FOR COMPARISON")
    standard_feed = setup_data_feed(api_key, premium=False)

    # Test rate limits with standard tier (fewer requests to avoid timeouts)
    standard_requests = min(10, args.requests)
    standard_success, standard_time, standard_response_times = test_rate_limits(
        standard_feed, num_requests=standard_requests
    )

    # Scale standard time to match the number of premium requests
    if standard_requests < args.requests:
        standard_time = standard_time * (args.requests / standard_requests)
        print(
            f"Note: Standard tier time scaled to equivalent of {args.requests} requests: {standard_time:.2f}s"
        )

    # Calculate effective requests per minute
    standard_rpm = (
        (standard_requests / standard_time) * 60 * (args.requests / standard_requests)
    )

    # Test historical data with standard tier
    standard_history_success, standard_points = test_intraday_full_history(
        standard_feed, symbol=args.symbol
    )

    # Show summary
    print("\n=== TEST SUMMARY ===")

    print("\nRate Limit Tests:")
    print(
        f"Premium tier: {premium_rpm:.2f} requests/minute, {premium_time:.2f}s for {args.requests} requests"
    )
    print(
        f"Standard tier: {standard_rpm:.2f} requests/minute, {standard_time:.2f}s for {args.requests} requests"
    )
    print(
        f"Speed improvement: {standard_time / premium_time:.2f}x faster with premium tier"
    )

    print("\nHistorical Data Tests:")
    print(f"Premium tier: {premium_points} data points")
    print(f"Standard tier: {standard_points} data points")
    if standard_points > 0:
        print(
            f"Data amount: {premium_points / standard_points:.2f}x more data with premium tier"
        )

    print("\nOutput Size Comparison:")
    compact_points = output_metrics["compact"]["points"]
    full_points = output_metrics["full"]["points"]
    print(
        f"Compact output: {compact_points} data points, {output_metrics['compact']['time']:.2f}s"
    )
    print(
        f"Full output: {full_points} data points, {output_metrics['full']['time']:.2f}s"
    )
    if compact_points > 0:
        print(
            f"Data amount: {full_points / compact_points:.2f}x more data with full output"
        )

    print("\nParallel Request Test:")
    print(
        f"Premium tier handled {args.parallel} concurrent requests: {'Successfully' if parallel_success else 'Failed'}"
    )

    # Overall assessment
    overall_success = (
        premium_success
        and premium_history_success
        and output_size_success
        and parallel_success
    )

    if overall_success:
        print("\n✅ OVERALL RESULT: Premium tier features are working correctly")
    else:
        print(
            "\n⚠️ OVERALL RESULT: Some premium tier features may not be working correctly"
        )

    # Create plots if not disabled
    if not args.no_plots:
        # Plot rate limit metrics
        plot_rate_limit_metrics(
            standard_time, standard_rpm, premium_time, premium_rpm, args.requests
        )

        # Plot historical data comparison
        plot_historical_data_comparison(premium_points, standard_points, args.symbol)

    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
