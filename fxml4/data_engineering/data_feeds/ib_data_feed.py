"""Interactive Brokers data feed implementation for FXML4.

This module provides a data feed that connects to Interactive Brokers TWS/Gateway
for real-time and historical market data.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper

from .base_feed import DataFeed, DataFeedFactory

logger = logging.getLogger(__name__)


class IBWrapper(EWrapper):
    """IB API wrapper for handling callbacks."""

    def __init__(self):
        super().__init__()
        self.historical_data = []
        self.next_order_id = None
        self.is_connected = False
        self.error_messages = []

    def nextValidId(self, orderId: int):
        """Callback for next valid order ID."""
        self.next_order_id = orderId
        logger.info("Next valid order ID: %d", orderId)

    def historicalData(self, reqId: int, bar):
        """Callback for historical data."""
        self.historical_data.append(
            {
                "datetime": bar.date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "wap": bar.wap,
                "count": bar.count,
            }
        )

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Callback for end of historical data."""
        logger.info("Historical data received: %d bars", len(self.historical_data))

    def error(self, reqId: int, errorCode: int, errorString: str):
        """Callback for errors."""
        error_msg = f"Error {errorCode}: {errorString} (reqId: {reqId})"
        self.error_messages.append(error_msg)
        if errorCode in [502, 504]:  # Cannot connect to TWS
            logger.error(error_msg)
            self.is_connected = False
        else:
            logger.warning(error_msg)

    def connectAck(self):
        """Callback for connection acknowledgment."""
        logger.info("Connected to IB Gateway/TWS")
        self.is_connected = True

    def connectionClosed(self):
        """Callback for connection closed."""
        logger.info("Connection to IB Gateway/TWS closed")
        self.is_connected = False


class IBClient(EClient):
    """IB API client for sending requests."""

    def __init__(self, wrapper):
        super().__init__(wrapper)


@DataFeedFactory.register("ib")
class IBDataFeed(DataFeed):
    """Interactive Brokers data feed implementation."""

    # Timeframe mappings for IB API
    TIMEFRAME_MAPPING = {
        "1m": ("1 min", "60 S"),
        "5m": ("5 mins", "300 S"),
        "15m": ("15 mins", "900 S"),
        "30m": ("30 mins", "1800 S"),
        "1h": ("1 hour", "3600 S"),
        "4h": ("4 hours", "14400 S"),
        "1d": ("1 day", "1 D"),
        "1w": ("1 week", "1 W"),
        "1M": ("1 month", "1 M"),
    }

    def __init__(self, config: Dict[str, Any]):
        """Initialize the IB data feed.

        Args:
            config: Configuration dictionary with the following keys:
                - host: IB Gateway/TWS host (default: "127.0.0.1")
                - port: IB Gateway/TWS port (default: 7497 for TWS, 4001 for Gateway)
                - client_id: Client ID for connection (default: 0)
                - timeout: Connection timeout in seconds (default: 10)
        """
        super().__init__(config)

        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 7497)  # 7497 for TWS, 4001 for Gateway
        self.client_id = config.get("client_id", 0)
        self.timeout = config.get("timeout", 10)

        self.wrapper = IBWrapper()
        self.client = IBClient(self.wrapper)
        self.thread = None
        self.req_id_counter = 0

        logger.info(
            "IB data feed initialized (host: %s, port: %d)", self.host, self.port
        )

    def connect(self) -> bool:
        """Connect to IB Gateway/TWS.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client.connect(self.host, self.port, self.client_id)

            # Start message processing thread
            self.thread = threading.Thread(target=self._run_client, daemon=True)
            self.thread.start()

            # Wait for connection
            start_time = time.time()
            while (
                not self.wrapper.is_connected
                and time.time() - start_time < self.timeout
            ):
                time.sleep(0.1)

            if self.wrapper.is_connected:
                logger.info("Successfully connected to IB Gateway/TWS")
                return True
            else:
                logger.error("Failed to connect to IB Gateway/TWS within timeout")
                return False

        except Exception as e:
            logger.error("Error connecting to IB Gateway/TWS: %s", e)
            return False

    def disconnect(self):
        """Disconnect from IB Gateway/TWS."""
        if self.client.isConnected():
            self.client.disconnect()
            logger.info("Disconnected from IB Gateway/TWS")

    def fetch_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch historical data from Interactive Brokers.

        Args:
            symbol: Trading symbol (e.g., "EUR", "AAPL")
            timeframe: Timeframe for the data
            start_date: Start date for historical data
            end_date: End date for historical data
            **kwargs: Additional arguments:
                - exchange: Exchange (default: "SMART")
                - currency: Currency (default: "USD")
                - sec_type: Security type (default: "STK")

        Returns:
            DataFrame with market data
        """
        if not self.client.isConnected():
            if not self.connect():
                raise ConnectionError("Failed to connect to IB Gateway/TWS")

        # Create contract
        contract = Contract()
        contract.symbol = symbol
        contract.exchange = kwargs.get("exchange", "SMART")
        contract.currency = kwargs.get("currency", "USD")
        contract.secType = kwargs.get("sec_type", "STK")

        # Determine duration and bar size
        if timeframe not in self.TIMEFRAME_MAPPING:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        bar_size, duration_unit = self.TIMEFRAME_MAPPING[timeframe]

        # Calculate duration
        if end_date is None:
            end_date = datetime.now()
        elif isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)

        if start_date is None:
            # Default to 1 day of data
            duration = "1 D"
        else:
            if isinstance(start_date, str):
                start_date = pd.to_datetime(start_date)

            # Calculate duration
            delta = end_date - start_date
            if delta.days > 365:
                duration = f"{delta.days // 365} Y"
            elif delta.days > 30:
                duration = f"{delta.days // 30} M"
            elif delta.days > 1:
                duration = f"{delta.days} D"
            else:
                duration = f"{int(delta.total_seconds())} S"

        # Clear previous data
        self.wrapper.historical_data = []

        # Request historical data
        req_id = self._get_next_req_id()
        end_datetime = end_date.strftime("%Y%m%d %H:%M:%S")

        logger.info(
            "Requesting historical data: symbol=%s, duration=%s, bar_size=%s",
            symbol,
            duration,
            bar_size,
        )

        self.client.reqHistoricalData(
            req_id,
            contract,
            end_datetime,
            duration,
            bar_size,
            "TRADES",
            1,  # Use RTH (Regular Trading Hours)
            1,  # Format date as yyyyMMdd HH:mm:ss
            False,  # Keep up to date
            [],
        )

        # Wait for data
        start_time = time.time()
        timeout = 30  # 30 seconds timeout for historical data

        while (
            len(self.wrapper.historical_data) == 0
            and time.time() - start_time < timeout
        ):
            time.sleep(0.1)

        if len(self.wrapper.historical_data) == 0:
            logger.error("No historical data received within timeout")
            if self.wrapper.error_messages:
                logger.error("Errors: %s", self.wrapper.error_messages)
            raise TimeoutError("No historical data received")

        # Convert to DataFrame
        df = pd.DataFrame(self.wrapper.historical_data)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
        df = df.sort_index()

        # Filter by date range if needed
        if start_date is not None:
            df = df[df.index >= start_date]

        logger.info("Received %d bars of historical data", len(df))

        return df

    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols.

        Note: IB doesn't provide a simple way to list all symbols,
        so this returns a predefined list of common symbols.

        Returns:
            List of available symbols
        """
        # Common forex pairs
        forex_symbols = ["EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]

        # Common stocks
        stock_symbols = [
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "FB",
            "TSLA",
            "JPM",
            "BAC",
            "WMT",
            "JNJ",
            "PG",
            "UNH",
        ]

        return forex_symbols + stock_symbols

    def get_available_timeframes(self) -> List[str]:
        """Get list of available timeframes.

        Returns:
            List of available timeframes
        """
        return list(self.TIMEFRAME_MAPPING.keys())

    def get_real_time_data(self, symbol: str, callback: callable, **kwargs: Any) -> int:
        """Subscribe to real-time market data.

        Args:
            symbol: Trading symbol
            callback: Callback function for data updates
            **kwargs: Additional arguments

        Returns:
            Request ID for the subscription
        """
        if not self.client.isConnected():
            if not self.connect():
                raise ConnectionError("Failed to connect to IB Gateway/TWS")

        # Create contract
        contract = Contract()
        contract.symbol = symbol
        contract.exchange = kwargs.get("exchange", "SMART")
        contract.currency = kwargs.get("currency", "USD")
        contract.secType = kwargs.get("sec_type", "STK")

        # Request market data
        req_id = self._get_next_req_id()

        self.client.reqMktData(
            req_id,
            contract,
            "",  # Generic tick list
            False,  # Snapshot
            False,  # Regulatory snapshot
            [],
        )

        logger.info("Subscribed to real-time data for %s (reqId: %d)", symbol, req_id)

        return req_id

    def cancel_real_time_data(self, req_id: int):
        """Cancel real-time market data subscription.

        Args:
            req_id: Request ID of the subscription
        """
        self.client.cancelMktData(req_id)
        logger.info("Cancelled real-time data subscription (reqId: %d)", req_id)

    def _run_client(self):
        """Run the IB client message processing loop."""
        self.client.run()

    def _get_next_req_id(self) -> int:
        """Get next request ID.

        Returns:
            Next request ID
        """
        self.req_id_counter += 1
        return self.req_id_counter

    def __del__(self):
        """Cleanup on deletion."""
        self.disconnect()
