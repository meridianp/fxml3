#!/usr/bin/env python
"""
Example of LiveDataHandler with Interactive Brokers in FXML4.

This script demonstrates how to use the LiveDataHandler class to connect to
Interactive Brokers, handle market hours, process real-time data, and
generate continuous candle data streams.
"""

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict

import numpy as np
import pandas as pd

from fxml4.data_engineering.live_data_handler import (
    ConnectionState,
    LiveDataHandler,
    MarketStatus,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global variables for signal handling
data_handler = None
is_running = True
status_lock = threading.Lock()
latest_status = {}
candle_data = {}


def signal_handler(sig, frame):
    """Handle interrupt signals to gracefully shut down."""
    global is_running
    logger.info("Shutdown signal received, stopping...")
    is_running = False


def status_callback(status: Dict[str, Any]):
    """Callback for connection and market status changes."""
    global latest_status
    with status_lock:
        latest_status = status.copy()

    logger.info(
        f"Status update: Connection={status['connection_state']}, Market={status['market_status']}"
    )

    # Log active symbols
    if status["active_symbols"]:
        logger.info(f"Active symbols: {', '.join(status['active_symbols'])}")


def candle_callback(symbol: str, timeframe: str, candles: pd.DataFrame):
    """Callback for new candle data."""
    global candle_data

    # Store the latest candle data
    if symbol not in candle_data:
        candle_data[symbol] = {}

    candle_data[symbol][timeframe] = candles

    # Get the latest candle
    latest_candle = candles.iloc[-1]

    logger.info(
        f"New {timeframe} candle for {symbol}: "
        + f"O:{latest_candle['open']:.5f} H:{latest_candle['high']:.5f} "
        + f"L:{latest_candle['low']:.5f} C:{latest_candle['close']:.5f}"
    )


def print_status_summary():
    """Print a summary of the current status."""
    global latest_status, candle_data

    with status_lock:
        status = latest_status.copy() if latest_status else {}

    if not status:
        logger.info("No status information available yet")
        return

    print("\n===== LiveDataHandler Status =====")
    print(f"Connection: {status.get('connection_state', 'Unknown')}")
    print(f"Market Status: {status.get('market_status', 'Unknown')}")
    print(f"Market Type: {status.get('market_type', 'Unknown')}")
    print(f"Trading Hours: {'Yes' if status.get('is_trading_hours', False) else 'No'}")
    print(f"Active Symbols: {', '.join(status.get('active_symbols', []))}")
    print(f"Pending Symbols: {', '.join(status.get('pending_symbols', []))}")
    print(f"Last Updated: {status.get('timestamp', 'Unknown')}")

    print("\n===== Latest Candle Data =====")
    for symbol, timeframes in candle_data.items():
        print(f"\nSymbol: {symbol}")
        for timeframe, data in timeframes.items():
            if not data.empty:
                latest = data.iloc[-1]
                print(
                    f"  {timeframe}: O:{latest['open']:.5f} H:{latest['high']:.5f} "
                    + f"L:{latest['low']:.5f} C:{latest['close']:.5f} Time:{latest.name}"
                )


def run_live_data_handler(args):
    """Run the LiveDataHandler example.

    Args:
        args: Command line arguments
    """
    global data_handler, is_running

    # Parse symbols
    symbols = args.symbols.split(",")

    # Configure LiveDataHandler
    config = {
        "market_type": args.market_type,
        "symbols": symbols,
        "timeframes": args.timeframes.split(","),
        "base_timeframe": "1m",
        "observe_market_hours": not args.ignore_market_hours,
        "holidays": args.holidays.split(",") if args.holidays else [],
        "max_reconnect_attempts": args.max_reconnect,
        "reconnect_delay": args.reconnect_delay,
        "health_check_interval": args.health_check_interval,
        "data_timeout": args.data_timeout,
        "store_in_db": args.store_in_db,
        "ib_config": {
            "host": args.host,
            "port": args.port,
            "client_id": args.client_id,
            "real_time_updates": True,
            "update_interval": 0.5,  # Process ticks every 0.5 seconds
        },
    }

    try:
        # Create and start LiveDataHandler
        logger.info("Creating LiveDataHandler...")
        data_handler = LiveDataHandler(config)

        # Register status callback
        data_handler.register_status_callback(status_callback)

        # Register candle callbacks for each symbol and timeframe
        for symbol in symbols:
            for timeframe in config["timeframes"]:
                data_handler.register_candle_callback(
                    symbol, timeframe, candle_callback
                )

        # Start the handler
        logger.info("Starting LiveDataHandler...")
        data_handler.start()

        # Wait for connect and subscribe
        logger.info("Waiting for connection and subscriptions...")
        time.sleep(5)

        # Initial status check
        status = data_handler.get_current_market_status()
        logger.info(
            f"Initial status: {status['connection_state']} / {status['market_status']}"
        )

        # Run main loop
        logger.info("Running main loop, press Ctrl+C to stop...")
        last_status_time = time.time()
        status_interval = args.status_interval

        while is_running:
            # Print status summary periodically
            now = time.time()
            if now - last_status_time >= status_interval:
                print_status_summary()
                last_status_time = now

            # Sleep to avoid high CPU usage
            time.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down...")

    except Exception as e:
        logger.error(f"Error in live data handler: {e}")

    finally:
        # Stop the handler
        if data_handler:
            logger.info("Stopping LiveDataHandler...")
            data_handler.stop()
            logger.info("LiveDataHandler stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="FXML4 Live Data Handler with Interactive Brokers"
    )

    # IB connection parameters
    parser.add_argument("--host", default="127.0.0.1", help="TWS/IB Gateway host")
    parser.add_argument(
        "--port",
        type=int,
        default=7497,
        help="TWS/IB Gateway port (7497 for paper trading)",
    )
    parser.add_argument(
        "--client-id", type=int, default=1, help="Client ID for IB connection"
    )

    # Market data parameters
    parser.add_argument(
        "--symbols", default="EURUSD,GBPUSD", help="Comma-separated list of symbols"
    )
    parser.add_argument(
        "--timeframes",
        default="1m,5m,15m,1h,4h",
        help="Comma-separated list of timeframes",
    )
    parser.add_argument(
        "--market-type",
        default="forex",
        choices=["forex", "us_equities"],
        help="Market type (affects trading hours)",
    )
    parser.add_argument(
        "--ignore-market-hours",
        action="store_true",
        help="Ignore market hours (treat market as always open)",
    )
    parser.add_argument(
        "--holidays",
        default="",
        help="Comma-separated list of holidays in YYYY-MM-DD format",
    )

    # Connection management parameters
    parser.add_argument(
        "--max-reconnect",
        type=int,
        default=5,
        help="Maximum number of reconnection attempts",
    )
    parser.add_argument(
        "--reconnect-delay",
        type=int,
        default=30,
        help="Delay in seconds between reconnection attempts",
    )
    parser.add_argument(
        "--health-check-interval",
        type=int,
        default=60,
        help="Interval in seconds between health checks",
    )
    parser.add_argument(
        "--data-timeout",
        type=int,
        default=300,
        help="Timeout in seconds for data freshness check",
    )

    # Display and storage options
    parser.add_argument(
        "--status-interval",
        type=int,
        default=10,
        help="Interval in seconds between status displays",
    )
    parser.add_argument(
        "--store-in-db", action="store_true", help="Store candle data in TimescaleDB"
    )

    args = parser.parse_args()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the example
    run_live_data_handler(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
