#!/usr/bin/env python3
"""
Test the integration between Interactive Brokers and TimescaleDB.

This script tests the end-to-end flow from IB tick data to TimescaleDB storage.
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from fxml4.config import get_config, init_config
from fxml4.data_engineering.data_feeds.ib_feed import IBDataFeed
from fxml4.data_engineering.timescaledb import TimescaleDBClient


def test_ib_connection(ib_feed):
    """Test connection to Interactive Brokers."""
    print("\n=== Testing IB Connection ===")

    if ib_feed.connect():
        print("✅ Connected to Interactive Brokers TWS API")
        return True
    else:
        print("❌ Failed to connect to Interactive Brokers TWS API")
        return False


def test_market_data_subscription(ib_feed, symbol="EURUSD"):
    """Test market data subscription."""
    print(f"\n=== Testing Market Data Subscription for {symbol} ===")

    try:
        req_id = ib_feed.subscribe_market_data(symbol)
        print(f"✅ Subscribed to market data for {symbol} (reqId: {req_id})")

        # Wait for a few seconds to receive some data
        print("Waiting for market data...")
        time.sleep(5)

        # Get latest tick
        latest_tick = ib_feed.get_latest_tick(symbol)
        if latest_tick:
            print(f"✅ Received market data for {symbol}:")
            print(f"   Timestamp: {latest_tick['timestamp']}")
            print(f"   Bid: {latest_tick.get('bid', 'N/A')}")
            print(f"   Ask: {latest_tick.get('ask', 'N/A')}")
            print(f"   Last: {latest_tick.get('last', 'N/A')}")
        else:
            print(f"❌ No market data received for {symbol}")
            return False

        # Cancel subscription
        ib_feed.cancel_market_data(symbol)
        print(f"Cancelled market data subscription for {symbol}")

        return True

    except Exception as e:
        print(f"❌ Error testing market data subscription: {e}")
        return False


def test_tick_storage(ib_feed, tsdb_client, symbol="EURUSD", duration=30):
    """Test tick storage in TimescaleDB."""
    print(f"\n=== Testing Tick Storage for {symbol} in TimescaleDB ===")

    try:
        # Get initial tick count
        initial_count = tsdb_client.get_tick_count(symbol=symbol)
        print(f"Initial tick count for {symbol}: {initial_count}")

        # Enable real-time updates
        ib_feed.real_time_updates = True

        # Enable storing ticks in DB
        ib_feed.config["store_ticks_in_db"] = True

        # Subscribe to market data
        req_id = ib_feed.subscribe_market_data(symbol)
        print(f"Subscribed to market data for {symbol} (reqId: {req_id})")

        # Start tick processor
        ib_feed.start_tick_processor()
        print("Started tick processor")

        # Wait for specified duration to collect ticks
        print(f"Collecting ticks for {duration} seconds...")
        time.sleep(duration)

        # Stop tick processor
        ib_feed.stop_tick_processor()
        print("Stopped tick processor")

        # Cancel subscription
        ib_feed.cancel_market_data(symbol)
        print(f"Cancelled market data subscription for {symbol}")

        # Get final tick count
        final_count = tsdb_client.get_tick_count(symbol=symbol)
        print(f"Final tick count for {symbol}: {final_count}")
        print(f"Ticks added: {final_count - initial_count}")

        if final_count > initial_count:
            print(f"✅ Successfully stored ticks for {symbol} in TimescaleDB")
            return True
        else:
            print(f"❌ No new ticks stored for {symbol} in TimescaleDB")
            return False

    except Exception as e:
        print(f"❌ Error testing tick storage: {e}")
        import traceback

        print(traceback.format_exc())
        return False


def test_candle_generation(ib_feed, tsdb_client, symbol="EURUSD", duration=120):
    """Test candle generation and storage in TimescaleDB."""
    print(f"\n=== Testing Candle Generation for {symbol} in TimescaleDB ===")

    try:
        # Get initial candle count for 1-minute timeframe
        initial_count = tsdb_client.get_candle_count("1m", symbol=symbol)
        print(f"Initial 1-minute candle count for {symbol}: {initial_count}")

        # Enable real-time updates
        ib_feed.real_time_updates = True

        # Enable storing ticks in DB
        ib_feed.config["store_ticks_in_db"] = True

        # Subscribe to market data
        req_id = ib_feed.subscribe_market_data(symbol)
        print(f"Subscribed to market data for {symbol} (reqId: {req_id})")

        # Start tick processor
        ib_feed.start_tick_processor()
        print("Started tick processor")

        # Wait for specified duration to collect ticks and generate candles
        # Should be at least 1 minute to see a complete candle
        print(f"Collecting ticks and generating candles for {duration} seconds...")
        time.sleep(duration)

        # Stop tick processor
        ib_feed.stop_tick_processor()
        print("Stopped tick processor")

        # Cancel subscription
        ib_feed.cancel_market_data(symbol)
        print(f"Cancelled market data subscription for {symbol}")

        # Force completion of any pending candles
        if ib_feed.tick_aggregator:
            completed = ib_feed.tick_aggregator.force_complete_all_candles()
            print(f"Forced completion of {len(completed)} candles")

            # Handle the completed candles
            for timeframe, candles in completed.items():
                for candle in candles:
                    if timeframe == 1:  # Only store 1-minute candles
                        ib_feed._handle_completed_candles(
                            candle["symbol"], {timeframe: candle}
                        )

        # Get final candle count
        final_count = tsdb_client.get_candle_count("1m", symbol=symbol)
        print(f"Final 1-minute candle count for {symbol}: {final_count}")
        print(f"Candles added: {final_count - initial_count}")

        # Get the latest candle
        latest_candle = tsdb_client.get_latest_candle(symbol, "1m")
        if latest_candle:
            print(f"\nLatest 1-minute candle for {symbol}:")
            print(f"  Time: {latest_candle.get('time')}")
            print(f"  Open: {latest_candle.get('open')}")
            print(f"  High: {latest_candle.get('high')}")
            print(f"  Low: {latest_candle.get('low')}")
            print(f"  Close: {latest_candle.get('close')}")
            print(f"  Volume: {latest_candle.get('volume')}")
            print(f"  Tick count: {latest_candle.get('tick_count')}")

        if final_count > initial_count:
            print(
                f"✅ Successfully generated and stored candles for {symbol} in TimescaleDB"
            )
            return True
        else:
            print(f"❌ No new candles stored for {symbol} in TimescaleDB")
            return False

    except Exception as e:
        print(f"❌ Error testing candle generation: {e}")
        import traceback

        print(traceback.format_exc())
        return False


def test_derived_timeframes(tsdb_client, symbol="EURUSD"):
    """Test derived timeframes in TimescaleDB."""
    print(f"\n=== Testing Derived Timeframes for {symbol} in TimescaleDB ===")

    try:
        # Check counts for different timeframes
        timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

        for tf in timeframes:
            count = tsdb_client.get_candle_count(tf, symbol=symbol)
            print(f"Candle count for {symbol} at {tf}: {count}")

            # Get the latest candle
            latest_candle = tsdb_client.get_latest_candle(symbol, tf)
            if latest_candle:
                time_key = "time" if tf == "1m" else "bucket"
                print(f"  Latest {tf} candle time: {latest_candle.get(time_key)}")

        # Get OHLCV data for a recent time period
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=24)

        print(
            f"\nRetrieving 4-hour OHLCV data for {symbol} from {start_time} to {end_time}"
        )
        df = tsdb_client.get_ohlcv_data(symbol, "4h", start_time, end_time)

        if not df.empty:
            print(f"Retrieved {len(df)} 4-hour candles")
            print(df.head(3))
            return True
        else:
            print("No 4-hour candles retrieved")
            return False

    except Exception as e:
        print(f"❌ Error testing derived timeframes: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test IB-TimescaleDB integration")
    parser.add_argument("--ib-host", default="localhost", help="TWS API host")
    parser.add_argument("--ib-port", type=int, default=7497, help="TWS API port")
    parser.add_argument("--ib-client-id", type=int, default=1, help="TWS API client ID")
    parser.add_argument("--db-host", default="localhost", help="TimescaleDB host")
    parser.add_argument("--db-port", type=int, default=5433, help="TimescaleDB port")
    parser.add_argument("--db-name", default="fxml4", help="TimescaleDB database name")
    parser.add_argument("--db-user", default="postgres", help="TimescaleDB user")
    parser.add_argument(
        "--db-password", default="postgres", help="TimescaleDB password"
    )
    parser.add_argument("--symbol", default="EURUSD", help="Symbol to use for testing")
    parser.add_argument(
        "--skip-ib-tests", action="store_true", help="Skip IB connection tests"
    )
    parser.add_argument(
        "--skip-tick-tests", action="store_true", help="Skip tick storage tests"
    )
    parser.add_argument(
        "--skip-candle-tests", action="store_true", help="Skip candle generation tests"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds for data collection",
    )
    args = parser.parse_args()

    # Initialize configuration
    config_path = os.path.join(project_root, "config", "default.yaml")
    init_config(config_path)

    # Override database configuration
    config = get_config()
    config["database"] = {
        "type": "postgresql",
        "host": args.db_host,
        "port": args.db_port,
        "name": args.db_name,
        "user": args.db_user,
        "password": args.db_password,
    }

    # Create TimescaleDB client
    tsdb_client = TimescaleDBClient(
        host=args.db_host,
        port=args.db_port,
        dbname=args.db_name,
        user=args.db_user,
        password=args.db_password,
    )

    # Create IB feed
    ib_config = {
        "host": args.ib_host,
        "port": args.ib_port,
        "client_id": args.ib_client_id,
        "real_time_updates": True,
        "store_ticks_in_db": True,
        "symbols": [args.symbol],
    }
    ib_feed = IBDataFeed(ib_config)

    # Run tests
    test_results = []

    if not args.skip_ib_tests:
        # Test IB connection
        connection_result = test_ib_connection(ib_feed)
        test_results.append(("IB Connection", connection_result))

        if connection_result:
            # Test market data subscription
            market_data_result = test_market_data_subscription(ib_feed, args.symbol)
            test_results.append(("Market Data Subscription", market_data_result))
        else:
            print("Skipping market data tests due to connection failure")

    if not args.skip_tick_tests and (args.skip_ib_tests or test_results[-1][1]):
        # Test tick storage
        tick_storage_result = test_tick_storage(
            ib_feed, tsdb_client, args.symbol, duration=min(args.duration, 30)
        )
        test_results.append(("Tick Storage", tick_storage_result))

    if not args.skip_candle_tests and (args.skip_ib_tests or test_results[-1][1]):
        # Test candle generation
        candle_result = test_candle_generation(
            ib_feed, tsdb_client, args.symbol, duration=args.duration
        )
        test_results.append(("Candle Generation", candle_result))

    # Test derived timeframes
    timeframe_result = test_derived_timeframes(tsdb_client, args.symbol)
    test_results.append(("Derived Timeframes", timeframe_result))

    # Print test results
    print("\n=== Test Results Summary ===")

    all_passed = True
    for name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {name}")
        if not result:
            all_passed = False

    # Disconnect from IB
    if not args.skip_ib_tests:
        ib_feed.disconnect()
        print("\nDisconnected from Interactive Brokers")

    if all_passed:
        print("\n🎉 All tests passed! IB-TimescaleDB integration is working correctly.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
