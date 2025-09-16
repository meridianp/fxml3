#!/usr/bin/env python3
"""
Simple test script for Alpha Vantage Premium API rate limits.

This script tests the basic functionality of premium rate limits
using the demo API key and a compatible endpoint.
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime

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


def test_rate_limit(api_key, requests_per_minute, num_requests=10):
    """Test rate limits with a simple endpoint that works with the demo key."""
    print(f"\n=== Testing Rate Limits with {requests_per_minute} RPM setting ===")
    base_url = "https://www.alphavantage.co/query"

    # Use the TIME_SERIES_INTRADAY endpoint with demo compatibility
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": "IBM",
        "interval": "5min",
        "apikey": api_key,
    }

    response_times = []
    start_time = time.time()
    success_count = 0

    for i in range(num_requests):
        request_start = time.time()
        print(f"Making request {i+1}/{num_requests}...", end="", flush=True)

        # Sleep based on rate limit (for standard tier)
        if requests_per_minute == 5 and i > 0:
            sleep_time = 60.0 / requests_per_minute
            time.sleep(sleep_time)

        try:
            response = requests.get(base_url, params=params)
            if response.status_code == 200:
                data = response.json()
                if "Time Series" in next(
                    (k for k in data.keys() if k.startswith("Time Series")), ""
                ):
                    success_count += 1
                    print(" Success")
                else:
                    print(" Failed (No time series data)")
            else:
                print(f" Failed (Status code: {response.status_code})")
        except Exception as e:
            print(f" Error: {e}")

        request_time = time.time() - request_start
        response_times.append(request_time)

    end_time = time.time()
    total_time = end_time - start_time

    print(f"Total time for {num_requests} requests: {total_time:.2f} seconds")
    print(
        f"Average time per request: {sum(response_times) / len(response_times):.2f} seconds"
    )
    print(
        f"Success rate: {success_count}/{num_requests} ({success_count/num_requests*100:.0f}%)"
    )

    # Calculate effective requests per minute
    req_per_minute = (num_requests / total_time) * 60
    print(f"Effective requests per minute: {req_per_minute:.2f}")

    return total_time, req_per_minute, response_times


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Simple Alpha Vantage Premium API Test"
    )
    parser.add_argument(
        "--api-key", default="demo", help="Alpha Vantage API key (default: demo)"
    )
    parser.add_argument(
        "--requests", type=int, default=5, help="Number of requests to make"
    )
    args = parser.parse_args()

    print("=== Alpha Vantage Rate Limit Test ===")
    print("This test compares premium vs standard tier rate limits")
    print(f"Using API key: {args.api_key}")

    # Test with premium tier settings
    print("\n🚀 TESTING WITH PREMIUM TIER CONFIGURATION (75 calls/minute)")
    premium_time, premium_rpm, _ = test_rate_limit(args.api_key, 75, args.requests)

    # Test with standard tier settings
    print("\n🚀 TESTING WITH STANDARD TIER CONFIGURATION (5 calls/minute)")
    standard_time, standard_rpm, _ = test_rate_limit(args.api_key, 5, args.requests)

    # Show comparison
    print("\n=== COMPARISON ===")
    print(
        f"Premium configuration: {premium_rpm:.2f} req/min, {premium_time:.2f}s total"
    )
    print(
        f"Standard configuration: {standard_rpm:.2f} req/min, {standard_time:.2f}s total"
    )

    if premium_time < standard_time:
        speedup = standard_time / premium_time
        print(f"Premium is {speedup:.2f}x faster!")
    else:
        print("No speedup observed with premium configuration")

    return 0


if __name__ == "__main__":
    sys.exit(main())
