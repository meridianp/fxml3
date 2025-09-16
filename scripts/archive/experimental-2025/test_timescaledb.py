#!/usr/bin/env python3
"""
Test TimescaleDB integration in FXML4.

This script tests the TimescaleDB integration with storage and retrieval
of tick data and OHLC candles at different timeframes.
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pprint import pprint

import numpy as np
import pandas as pd
import psycopg2

# Add the project root to the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from fxml4.data_engineering.timescaledb import TimescaleDBClient


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


def test_database_connection(client):
    """Test connection to the TimescaleDB database."""
    print("\n=== Testing Database Connection ===")

    try:
        # Get a connection
        conn = client.get_connection()

        # Check if the connection is valid
        if conn.closed:
            print("❌ Connection is closed")
            return False

        # Check if we can execute a query
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        print(f"✅ Connected to database: {version}")
        return True

    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return False


def test_store_ticks(client, symbol="EURUSD", count=10):
    """Test storing ticks in the database."""
    print("\n=== Testing Tick Storage ===")

    try:
        # Create some sample ticks
        base_time = datetime.now(timezone.utc)
        ticks = []

        for i in range(count):
            # Create a tick at a random time point within the last hour
            seconds_ago = np.random.randint(0, 3600)
            tick_time = base_time - timedelta(seconds=seconds_ago)

            # Generate a random price
            price = 1.1000 + np.random.normal(0, 0.0010)

            # Generate a random size
            size = np.random.randint(100, 1000)

            # Add the tick
            ticks.append(
                {
                    "symbol": symbol,
                    "timestamp": tick_time,
                    "price": price,
                    "size": size,
                    "tick_type": "trade",
                    "source": "test",
                }
            )

        # Store the ticks
        start_time = time.time()
        stored_count = client.store_ticks(ticks)
        end_time = time.time()

        print(f"✅ Stored {stored_count} ticks in {end_time - start_time:.3f} seconds")

        # Verify the stored ticks
        total_count = client.get_tick_count(symbol=symbol)
        print(f"Total ticks for {symbol} in database: {total_count}")

        return stored_count == count

    except Exception as e:
        print(f"❌ Error testing tick storage: {e}")
        return False


def test_store_candles(client, symbol="EURUSD", count=10):
    """Test storing candles in the database."""
    print("\n=== Testing Candle Storage ===")

    try:
        # Create some sample candles
        base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        candles = []

        for i in range(count):
            # Create a candle for a minute in the past
            candle_time = base_time - timedelta(minutes=i)

            # Generate random OHLC data
            close_price = 1.1000 + np.random.normal(0, 0.0010)
            open_price = close_price + np.random.normal(0, 0.0005)
            high_price = max(open_price, close_price) + abs(np.random.normal(0, 0.0005))
            low_price = min(open_price, close_price) - abs(np.random.normal(0, 0.0005))

            # Generate a random volume
            volume = np.random.randint(1000, 5000)

            # Add the candle
            candles.append(
                {
                    "symbol": symbol,
                    "timestamp": candle_time,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                    "tick_count": np.random.randint(10, 50),
                    "source": "test",
                }
            )

        # Store the candles
        start_time = time.time()
        stored_count = client.store_candles(candles)
        end_time = time.time()

        print(
            f"✅ Stored {stored_count} candles in {end_time - start_time:.3f} seconds"
        )

        # Verify the stored candles
        total_count = client.get_candle_count("1m", symbol=symbol)
        print(f"Total 1-minute candles for {symbol} in database: {total_count}")

        return stored_count == count

    except Exception as e:
        print(f"❌ Error testing candle storage: {e}")
        return False


def test_retrieve_candles(client, symbol="EURUSD"):
    """Test retrieving candles from the database."""
    print("\n=== Testing Candle Retrieval ===")

    try:
        # Get the current time
        now = datetime.now(timezone.utc)

        # Get candles for the last hour
        start_time = now - timedelta(hours=1)
        end_time = now

        # Get 1-minute candles
        candles_1m = client.get_ohlcv_data(symbol, "1m", start_time, end_time)
        print(f"Retrieved {len(candles_1m)} 1-minute candles")

        # Get 5-minute candles
        candles_5m = client.get_ohlcv_data(symbol, "5m", start_time, end_time)
        print(f"Retrieved {len(candles_5m)} 5-minute candles")

        # Get 15-minute candles
        candles_15m = client.get_ohlcv_data(symbol, "15m", start_time, end_time)
        print(f"Retrieved {len(candles_15m)} 15-minute candles")

        # Display the candles
        if not candles_1m.empty:
            display_dataframe(candles_1m.tail(5), f"{symbol} 1-minute Candles")

        if not candles_5m.empty:
            display_dataframe(candles_5m.tail(5), f"{symbol} 5-minute Candles")

        if not candles_15m.empty:
            display_dataframe(candles_15m.tail(5), f"{symbol} 15-minute Candles")

        # Get the latest candle
        latest_candle = client.get_latest_candle(symbol, "1m")
        if latest_candle:
            print(f"\nLatest 1-minute candle for {symbol}:")
            pprint(latest_candle)

        return True

    except Exception as e:
        print(f"❌ Error testing candle retrieval: {e}")
        return False


def test_continuous_aggregates(client, symbol="EURUSD"):
    """Test TimescaleDB continuous aggregates."""
    print("\n=== Testing Continuous Aggregates ===")

    try:
        # Get the current time
        now = datetime.now(timezone.utc)

        # Get candles for various timeframes
        timeframes = ["1m", "5m", "15m", "30m", "1h", "4h"]

        for timeframe in timeframes:
            # For higher timeframes, we need a longer time range
            if timeframe in ["1h", "4h"]:
                start_time = now - timedelta(days=7)
            elif timeframe in ["15m", "30m"]:
                start_time = now - timedelta(days=1)
            else:
                start_time = now - timedelta(hours=6)

            # Get candle count
            count = client.get_candle_count(
                timeframe, symbol=symbol, start_time=start_time
            )
            print(f"Found {count} {timeframe} candles for {symbol} since {start_time}")

            # Get the latest candle
            latest_candle = client.get_latest_candle(symbol, timeframe)
            if latest_candle:
                print(
                    f"  Latest {timeframe} candle time: {latest_candle.get('time') or latest_candle.get('bucket')}"
                )

        return True

    except Exception as e:
        print(f"❌ Error testing continuous aggregates: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test TimescaleDB integration")
    parser.add_argument("--host", default="localhost", help="Database host")
    parser.add_argument("--port", type=int, default=5432, help="Database port")
    parser.add_argument("--dbname", default="fxml4", help="Database name")
    parser.add_argument("--user", default="postgres", help="Database user")
    parser.add_argument("--password", default="postgres", help="Database password")
    parser.add_argument("--symbol", default="EURUSD", help="Symbol to use for testing")
    parser.add_argument("--skip-setup", action="store_true", help="Skip database setup")
    args = parser.parse_args()

    if not args.skip_setup:
        # Set up the database
        print("Setting up TimescaleDB...")

        # Execute the setup script
        setup_script = os.path.join(root_dir, "scripts", "setup_timescaledb.py")
        if os.path.exists(setup_script):
            os.system(
                f"python {setup_script} --host {args.host} --port {args.port} "
                + f"--user {args.user} --password {args.password} --dbname {args.dbname}"
            )
        else:
            print(f"❌ Setup script not found: {setup_script}")
            return 1

        # Execute the migration
        migration_script = os.path.join(
            root_dir, "db", "migrations", "002_add_tick_data_schema.sql"
        )
        if os.path.exists(migration_script):
            print(f"Applying migration: {migration_script}")
            try:
                # Connect to the database
                conn = psycopg2.connect(
                    host=args.host,
                    port=args.port,
                    dbname=args.dbname,
                    user=args.user,
                    password=args.password,
                )
                conn.set_session(autocommit=True)

                # Execute the migration
                with conn.cursor() as cursor:
                    with open(migration_script, "r") as f:
                        cursor.execute(f.read())

                conn.close()
                print("✅ Migration applied successfully")
            except Exception as e:
                print(f"❌ Error applying migration: {e}")
                return 1
        else:
            print(f"❌ Migration script not found: {migration_script}")
            return 1

    # Create the TimescaleDB client
    client = TimescaleDBClient(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
    )

    # Run the tests
    test_results = [
        ("Database Connection", test_database_connection(client)),
        ("Tick Storage", test_store_ticks(client, symbol=args.symbol, count=100)),
        ("Candle Storage", test_store_candles(client, symbol=args.symbol, count=50)),
        ("Candle Retrieval", test_retrieve_candles(client, symbol=args.symbol)),
        (
            "Continuous Aggregates",
            test_continuous_aggregates(client, symbol=args.symbol),
        ),
    ]

    # Print test results
    print("\n=== Test Results Summary ===")
    all_passed = True

    for name, passed in test_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All tests passed! TimescaleDB integration is working correctly.")
        return 0
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
