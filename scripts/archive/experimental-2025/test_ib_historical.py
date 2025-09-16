#!/usr/bin/env python3
"""
Interactive Brokers TWS API historical data test for FXML4.

This script tests retrieving historical forex data from Interactive Brokers.
"""

import argparse
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

try:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.ticktype import TickTypeEnum
    from ibapi.wrapper import EWrapper

    IB_API_AVAILABLE = True

    # Log the version of the API
    import ibapi

    logger.info(f"Using IB API version: {ibapi.__version__}")
except ImportError:
    logger.warning("IB API not available. Please install ibapi package.")
    IB_API_AVAILABLE = False


class IBAPIApp(EWrapper, EClient):
    """
    Interactive Brokers API application.
    Combines EWrapper and EClient functionality.
    """

    def __init__(self):
        """Initialize the application."""
        EClient.__init__(self, self)

        # State management
        self.next_req_id = 1
        self.connected = False

        # Data containers
        self.historical_data = []

        # Event flags
        self.historical_data_end_event = False

    def nextValidId(self, orderId: int):
        """Callback for next valid order ID."""
        self.connected = True
        logger.info(f"Connected to TWS")

    def connectAck(self):
        """Callback for connection acknowledgement."""
        logger.info("Connection to TWS acknowledged")

    def error(
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ):
        """Callback for error messages."""
        # Ignore certain informational messages
        if errorCode in [2104, 2106, 2158]:  # Market data farm connection messages
            return

        logger.error(f"Error {errorCode}: {errorString}")

    def historicalData(self, reqId: int, bar):
        """Callback for historical data."""
        self.historical_data.append(
            [bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume]
        )
        logger.debug(
            f"Historical data: {bar.date} - OHLCV: {bar.open}/{bar.high}/{bar.low}/{bar.close}/{bar.volume}"
        )

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Callback for end of historical data."""
        logger.info(
            f"Historical data retrieval completed. {len(self.historical_data)} bars received."
        )
        self.historical_data_end_event = True


def create_forex_contract(symbol: str) -> Contract:
    """Create a forex contract for a given symbol.

    Args:
        symbol: Forex pair symbol (e.g., "GBPUSD" or "GBP.USD")

    Returns:
        Contract object
    """
    # Handle both formats: GBPUSD and GBP.USD
    if "." in symbol:
        base_currency = symbol.split(".")[0]
        quote_currency = symbol.split(".")[1]
    else:
        base_currency = symbol[:3]
        quote_currency = symbol[3:]

    contract = Contract()
    contract.symbol = base_currency
    contract.secType = "CASH"
    contract.currency = quote_currency
    contract.exchange = "IDEALPRO"

    logger.info(f"Created contract for {base_currency}/{quote_currency}")
    return contract


def test_historical_data(
    host: str,
    port: int,
    client_id: int,
    symbol: str,
    duration: str = "1 D",
    bar_size: str = "1 hour",
) -> bool:
    """Test retrieving historical data from Interactive Brokers TWS API.

    Args:
        host: TWS host
        port: TWS port
        client_id: Client ID
        symbol: Forex pair symbol (e.g., "GBPUSD")
        duration: Duration of historical data (e.g., "1 D", "1 W")
        bar_size: Bar size (e.g., "1 min", "1 hour", "1 day")

    Returns:
        True if historical data retrieval successful, False otherwise
    """
    if not IB_API_AVAILABLE:
        logger.error("IB API not available. Please install ibapi package.")
        return False

    app = IBAPIApp()

    try:
        logger.info(f"Connecting to TWS at {host}:{port} with client ID {client_id}")
        app.connect(host, port, client_id)

        # Start API event loop in a separate thread
        api_thread = threading.Thread(target=app.run)
        api_thread.start()

        # Wait for connection
        max_wait_time = 10  # seconds
        wait_time = 0
        wait_interval = 0.5  # seconds

        while not app.connected and wait_time < max_wait_time:
            time.sleep(wait_interval)
            wait_time += wait_interval

        if not app.connected:
            logger.error("Failed to connect to TWS")
            app.disconnect()
            return False

        # Create contract
        contract = create_forex_contract(symbol)

        # Request historical data
        end_time = datetime.now().strftime("%Y%m%d %H:%M:%S")
        end_time_with_tz = f"{end_time} US/Eastern"
        logger.info(
            f"Requesting historical data for {symbol} with duration {duration} and bar size {bar_size}"
        )

        app.reqHistoricalData(
            reqId=1,
            contract=contract,
            endDateTime=end_time_with_tz,
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="MIDPOINT",
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[],
        )

        # Wait for historical data
        wait_time = 0
        max_wait_time = 30  # seconds

        while not app.historical_data_end_event and wait_time < max_wait_time:
            time.sleep(wait_interval)
            wait_time += wait_interval

        if not app.historical_data_end_event and len(app.historical_data) == 0:
            logger.error(f"Failed to receive historical data for {symbol}")
            app.disconnect()
            return False

        # Convert to DataFrame
        df = pd.DataFrame(
            app.historical_data,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )

        if len(df) > 0:
            # Check the format of the first timestamp
            logger.info(
                f"First timestamp sample: {df['timestamp'].iloc[0]} (type: {type(df['timestamp'].iloc[0]).__name__})"
            )

            # Try to convert timestamps based on their format
            try:
                if isinstance(df["timestamp"].iloc[0], str):
                    if " " in df["timestamp"].iloc[0]:
                        # Format like "20250310 16:30:00"
                        df["timestamp"] = pd.to_datetime(
                            df["timestamp"], format="%Y%m%d %H:%M:%S"
                        )
                    else:
                        # Some other string format
                        df["timestamp"] = pd.to_datetime(df["timestamp"])
                else:
                    # Numeric timestamp (Unix timestamp)
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            except Exception as e:
                logger.warning(f"Error converting timestamps: {e}")

            df = df.set_index("timestamp")
            df = df.sort_index()

            # Print the first few rows
            logger.info(f"Historical data for {symbol}:")
            logger.info(f"\n{df.head().to_string()}")
            logger.info(f"Total bars received: {len(df)}")
        else:
            logger.warning(f"No historical data received for {symbol}")

        # Disconnect
        app.disconnect()
        logger.info("Disconnected from TWS")

        return len(df) > 0

    except Exception as e:
        logger.error(f"Error testing historical data: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Interactive Brokers historical data retrieval"
    )
    parser.add_argument("--host", default="127.0.0.1", help="TWS host")
    parser.add_argument(
        "--port", type=int, default=7496, help="TWS port (7496 for TWS Live)"
    )
    parser.add_argument("--client-id", type=int, default=0, help="Client ID")
    parser.add_argument(
        "--symbol", default="GBPUSD", help="Symbol to test historical data"
    )
    parser.add_argument("--duration", default="1 D", help="Duration of historical data")
    parser.add_argument("--bar-size", default="1 hour", help="Bar size")
    parser.add_argument("--save", action="store_true", help="Save data to file")
    args = parser.parse_args()

    # Check if ibapi package is available
    if not IB_API_AVAILABLE:
        logger.error("IB API not available. Please install ibapi package first.")
        return 1

    # Test historical data
    logger.info(f"Testing historical data retrieval for {args.symbol}")
    if not test_historical_data(
        args.host, args.port, args.client_id, args.symbol, args.duration, args.bar_size
    ):
        logger.error("Historical data test failed")
        return 1

    logger.info("Historical data test successful")
    return 0


if __name__ == "__main__":
    sys.exit(main())
