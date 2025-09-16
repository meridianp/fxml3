"""Production-ready Interactive Brokers data client with robust error handling.

This module provides a production-grade IB client with:
- Automatic reconnection logic
- Circuit breaker pattern for error handling
- Connection health monitoring
- Request rate limiting
- Comprehensive logging and metrics
- Multi-timeframe data optimization
- Graceful degradation under failure conditions
"""

import asyncio
import logging
import queue
import sys
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

import pandas as pd

# Add official IB SDK to Python path
ib_sdk_path = Path.home() / "code" / "IBJts" / "source" / "pythonclient"
if ib_sdk_path.exists():
    sys.path.insert(0, str(ib_sdk_path))

# IB API imports from official SDK
try:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.ticktype import TickTypeEnum
    from ibapi.wrapper import EWrapper

    IB_API_AVAILABLE = True
except ImportError:
    IB_API_AVAILABLE = False

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class DataRequestType(Enum):
    """Data request type enumeration."""

    HISTORICAL = "historical"
    REALTIME = "realtime"
    SNAPSHOT = "snapshot"


@dataclass
class ConnectionMetrics:
    """Connection metrics tracking."""

    connection_attempts: int = 0
    successful_connections: int = 0
    connection_failures: int = 0
    last_connection_time: Optional[datetime] = None
    last_disconnection_time: Optional[datetime] = None
    total_uptime: timedelta = timedelta()
    reconnection_attempts: int = 0
    data_requests_sent: int = 0
    data_responses_received: int = 0
    error_count: int = 0
    circuit_breaker_triggers: int = 0


@dataclass
class DataRequest:
    """Data request tracking."""

    req_id: int
    symbol: str
    request_type: DataRequestType
    timeframe: str
    timestamp: datetime
    timeout: float
    callback: Optional[Callable] = None
    retries: int = 0
    max_retries: int = 3
    status: str = "pending"  # pending, completed, failed, timeout


class CircuitBreaker:
    """Circuit breaker for IB connection failures."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN - too many failures")

        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.reset()
            return result
        except Exception as e:
            self._record_failure()
            raise e

    def _record_failure(self):
        """Record a failure."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"Circuit breaker OPENED after {self.failure_count} failures"
            )

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit breaker."""
        if not self.last_failure_time:
            return True

        return (
            datetime.now() - self.last_failure_time
        ).total_seconds() > self.recovery_timeout

    def reset(self):
        """Reset the circuit breaker."""
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None
        logger.info("Circuit breaker RESET")


class RateLimiter:
    """Rate limiter for IB API requests."""

    def __init__(self, max_requests_per_second: int = 10):
        self.max_requests_per_second = max_requests_per_second
        self.requests = deque()
        self.lock = threading.Lock()

    def acquire(self) -> bool:
        """Acquire permission to make a request."""
        with self.lock:
            now = time.time()

            # Remove old requests
            while self.requests and self.requests[0] <= now - 1.0:
                self.requests.popleft()

            # Check if we can make a request
            if len(self.requests) < self.max_requests_per_second:
                self.requests.append(now)
                return True

            return False

    def wait_if_needed(self):
        """Wait if rate limiting is needed."""
        while not self.acquire():
            time.sleep(0.1)


class RobustIBWrapper(EWrapper):
    """Enhanced IB wrapper with comprehensive error handling."""

    def __init__(self, client_handler):
        super().__init__()
        self.client_handler = client_handler

    def nextValidId(self, orderId: int):
        """Connection established callback."""
        self.client_handler._handle_connection_established(orderId)

    def connectAck(self):
        """Connection acknowledgment."""
        logger.info("IB connection acknowledged")

    def connectionClosed(self):
        """Connection closed callback."""
        self.client_handler._handle_connection_closed()

    def error(
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ):
        """Enhanced error handling."""
        self.client_handler._handle_error(
            reqId, errorCode, errorString, advancedOrderRejectJson
        )

    def historicalData(self, reqId: int, bar):
        """Historical data callback."""
        self.client_handler._handle_historical_data(reqId, bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Historical data end callback."""
        self.client_handler._handle_historical_data_end(reqId, start, end)

    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """Tick price callback."""
        self.client_handler._handle_tick_price(reqId, tickType, price, attrib)

    def tickSize(self, reqId: int, tickType: int, size: int):
        """Tick size callback."""
        self.client_handler._handle_tick_size(reqId, tickType, size)


class RobustIBClient:
    """Production-ready Interactive Brokers client with robust error handling."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the robust IB client.

        Args:
            config: Configuration dictionary with:
                - host: IB Gateway host (default: "127.0.0.1")
                - port: IB Gateway port (default: 8888 for containerized, 7497 for desktop)
                - client_id: Client ID (default: 0)
                - reconnect_attempts: Max reconnection attempts (default: 10)
                - reconnect_delay: Delay between reconnects in seconds (default: 5)
                - request_timeout: Request timeout in seconds (default: 30)
                - rate_limit_rps: Requests per second limit (default: 10)
                - circuit_breaker_threshold: Circuit breaker failure threshold (default: 5)
                - health_check_interval: Health check interval in seconds (default: 30)
        """
        if not IB_API_AVAILABLE:
            raise ImportError(
                "IB API not available. Ensure official IB SDK is at ~/code/IBJts/source/pythonclient"
            )

        # Configuration
        self.config = config
        self.host = config.get("host", "127.0.0.1")
        # Default port 8888 for containerized IB Gateway, fallback to 7497 for desktop TWS
        self.port = config.get("port", 8888)
        self.client_id = config.get("client_id", 0)
        self.reconnect_attempts = config.get("reconnect_attempts", 10)
        self.reconnect_delay = config.get("reconnect_delay", 5)
        self.request_timeout = config.get("request_timeout", 30)

        # State management
        self.state = ConnectionState.DISCONNECTED
        self.next_req_id = 1
        self.req_id_lock = threading.Lock()

        # IB API components
        self.wrapper = RobustIBWrapper(self)
        self.client = EClient(self.wrapper)
        self.api_thread: Optional[threading.Thread] = None

        # Data storage
        self.historical_data_store: Dict[int, List[Dict]] = {}
        self.market_data_store: Dict[int, Dict[str, Any]] = {}
        self.active_requests: Dict[int, DataRequest] = {}

        # Event management
        self.data_events: Dict[int, threading.Event] = {}
        self.connection_event = threading.Event()

        # Reliability components
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.get("circuit_breaker_threshold", 5),
            recovery_timeout=config.get("circuit_breaker_recovery", 60),
        )
        self.rate_limiter = RateLimiter(config.get("rate_limit_rps", 10))
        self.metrics = ConnectionMetrics()

        # Health monitoring
        self.health_check_interval = config.get("health_check_interval", 30)
        self.health_monitor_thread: Optional[threading.Thread] = None
        self.last_heartbeat = datetime.now()
        self.shutdown_event = threading.Event()

        # Symbol mapping
        self.req_id_to_symbol: Dict[int, str] = {}
        self.symbol_subscriptions: Dict[str, int] = {}

        logger.info(
            f"Initialized RobustIBClient: {self.host}:{self.port} (client_id: {self.client_id})"
        )

    def connect(self) -> bool:
        """Connect to IB with robust error handling and reconnection.

        Returns:
            True if connected successfully, False otherwise
        """
        return self.circuit_breaker.call(self._connect_internal)

    def _connect_internal(self) -> bool:
        """Internal connection method."""
        if self.state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING]:
            return True

        self.state = ConnectionState.CONNECTING
        self.metrics.connection_attempts += 1

        try:
            logger.info(f"Connecting to IB at {self.host}:{self.port}")

            # Clear previous connection state
            self.connection_event.clear()

            # Connect to IB
            self.client.connect(self.host, self.port, self.client_id)

            # Start API thread
            if not self.api_thread or not self.api_thread.is_alive():
                self.api_thread = threading.Thread(
                    target=self._run_api_thread, daemon=True
                )
                self.api_thread.start()

            # Wait for connection with timeout
            connected = self.connection_event.wait(timeout=30)

            if connected and self.state == ConnectionState.CONNECTED:
                self.metrics.successful_connections += 1
                self.metrics.last_connection_time = datetime.now()
                self._start_health_monitor()
                logger.info("✅ Successfully connected to IB")
                return True
            else:
                self.state = ConnectionState.FAILED
                self.metrics.connection_failures += 1
                logger.error("❌ Failed to connect to IB within timeout")
                return False

        except Exception as e:
            self.state = ConnectionState.FAILED
            self.metrics.connection_failures += 1
            logger.error(f"❌ Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from IB gracefully."""
        logger.info("Disconnecting from IB...")

        self.shutdown_event.set()

        # Stop health monitor
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            self.health_monitor_thread.join(timeout=5)

        # Cancel active subscriptions
        self._cancel_all_subscriptions()

        # Disconnect client
        if self.client.isConnected():
            self.client.disconnect()

        # Wait for API thread to finish
        if self.api_thread and self.api_thread.is_alive():
            self.api_thread.join(timeout=5)

        self.state = ConnectionState.DISCONNECTED
        self.metrics.last_disconnection_time = datetime.now()

        logger.info("✅ Disconnected from IB")

    def reconnect(self) -> bool:
        """Reconnect to IB with exponential backoff."""
        if self.state == ConnectionState.CONNECTED:
            return True

        self.state = ConnectionState.RECONNECTING
        self.metrics.reconnection_attempts += 1

        logger.info("🔄 Attempting to reconnect to IB...")

        for attempt in range(self.reconnect_attempts):
            # Exponential backoff
            delay = min(self.reconnect_delay * (2**attempt), 60)

            logger.info(
                f"Reconnection attempt {attempt + 1}/{self.reconnect_attempts} (delay: {delay}s)"
            )

            if attempt > 0:
                time.sleep(delay)

            # Disconnect first
            if self.client.isConnected():
                self.client.disconnect()
                time.sleep(2)

            # Attempt connection
            if self._connect_internal():
                logger.info("✅ Reconnection successful!")
                return True

            logger.warning(f"❌ Reconnection attempt {attempt + 1} failed")

        logger.error("❌ All reconnection attempts failed")
        self.state = ConnectionState.FAILED
        return False

    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        duration: str = "1 D",
        end_time: Optional[datetime] = None,
        what_to_show: str = "TRADES",
        use_rth: bool = True,
        timeout: Optional[float] = None,
    ) -> pd.DataFrame:
        """Get historical data with robust error handling.

        Args:
            symbol: Symbol to fetch (e.g., "EURUSD")
            timeframe: Timeframe (e.g., "1 min", "1 hour")
            duration: Duration string (e.g., "1 D", "1 W")
            end_time: End time for data
            what_to_show: Data type to show
            use_rth: Use regular trading hours
            timeout: Request timeout

        Returns:
            DataFrame with historical data
        """
        if not self._ensure_connected():
            raise ConnectionError("Failed to establish IB connection")

        # Rate limiting
        self.rate_limiter.wait_if_needed()

        # Create request
        req_id = self._get_next_req_id()
        timeout = timeout or self.request_timeout

        request = DataRequest(
            req_id=req_id,
            symbol=symbol,
            request_type=DataRequestType.HISTORICAL,
            timeframe=timeframe,
            timestamp=datetime.now(),
            timeout=timeout,
        )

        self.active_requests[req_id] = request
        self.historical_data_store[req_id] = []
        self.data_events[req_id] = threading.Event()
        self.req_id_to_symbol[req_id] = symbol

        try:
            # Create contract
            contract = self._create_forex_contract(symbol)

            # Format end time
            if end_time is None:
                end_time = datetime.now()
            end_time_str = end_time.strftime("%Y%m%d %H:%M:%S")

            logger.info(
                f"📊 Requesting {timeframe} data for {symbol} (reqId: {req_id})"
            )

            # Request data
            self.client.reqHistoricalData(
                reqId=req_id,
                contract=contract,
                endDateTime=end_time_str,
                durationStr=duration,
                barSizeSetting=timeframe,
                whatToShow=what_to_show,
                useRTH=1 if use_rth else 0,
                formatDate=1,
                keepUpToDate=False,
                chartOptions=[],
            )

            self.metrics.data_requests_sent += 1

            # Wait for completion
            if self.data_events[req_id].wait(timeout=timeout):
                data = self.historical_data_store.get(req_id, [])

                if data:
                    df = pd.DataFrame(data)
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df.set_index("timestamp", inplace=True)
                    df.sort_index(inplace=True)

                    self.metrics.data_responses_received += 1
                    request.status = "completed"

                    logger.info(f"✅ Received {len(df)} bars for {symbol}")
                    return df
                else:
                    request.status = "failed"
                    logger.warning(f"⚠️ No data received for {symbol}")
                    return pd.DataFrame()
            else:
                request.status = "timeout"
                logger.error(f"❌ Timeout waiting for {symbol} data")
                raise TimeoutError(f"Timeout waiting for historical data: {symbol}")

        finally:
            # Cleanup
            self._cleanup_request(req_id)

    def subscribe_market_data(self, symbol: str, snapshot: bool = False) -> int:
        """Subscribe to market data with error handling.

        Args:
            symbol: Symbol to subscribe to
            snapshot: Request snapshot instead of streaming

        Returns:
            Request ID for the subscription
        """
        if not self._ensure_connected():
            raise ConnectionError("Failed to establish IB connection")

        # Check if already subscribed
        if symbol in self.symbol_subscriptions:
            logger.info(f"Already subscribed to {symbol}")
            return self.symbol_subscriptions[symbol]

        # Rate limiting
        self.rate_limiter.wait_if_needed()

        req_id = self._get_next_req_id()
        contract = self._create_forex_contract(symbol)

        # Track subscription
        self.symbol_subscriptions[symbol] = req_id
        self.req_id_to_symbol[req_id] = symbol
        self.market_data_store[req_id] = {}

        try:
            logger.info(f"📡 Subscribing to {symbol} market data (reqId: {req_id})")

            self.client.reqMktData(
                reqId=req_id,
                contract=contract,
                genericTickList="",
                snapshot=snapshot,
                regulatorySnapshot=False,
                mktDataOptions=[],
            )

            self.metrics.data_requests_sent += 1
            return req_id

        except Exception as e:
            # Cleanup on error
            if symbol in self.symbol_subscriptions:
                del self.symbol_subscriptions[symbol]
            if req_id in self.req_id_to_symbol:
                del self.req_id_to_symbol[req_id]
            if req_id in self.market_data_store:
                del self.market_data_store[req_id]

            logger.error(f"❌ Failed to subscribe to {symbol}: {e}")
            raise

    def get_market_data(self, symbol: str, timeout: float = 10) -> Dict[str, Any]:
        """Get current market data for a symbol.

        Args:
            symbol: Symbol to get data for
            timeout: Timeout in seconds

        Returns:
            Dictionary with market data
        """
        req_id = self.subscribe_market_data(symbol, snapshot=True)

        # Wait for data
        start_time = time.time()
        while time.time() - start_time < timeout:
            if req_id in self.market_data_store and self.market_data_store[req_id]:
                data = self.market_data_store[req_id].copy()

                # Cancel subscription
                self.cancel_market_data(symbol)

                return data

            time.sleep(0.1)

        # Timeout
        self.cancel_market_data(symbol)
        raise TimeoutError(f"Timeout getting market data for {symbol}")

    def cancel_market_data(self, symbol: str) -> bool:
        """Cancel market data subscription.

        Args:
            symbol: Symbol to cancel

        Returns:
            True if canceled successfully
        """
        if symbol not in self.symbol_subscriptions:
            return False

        req_id = self.symbol_subscriptions[symbol]

        try:
            self.client.cancelMktData(req_id)
            logger.info(f"📡 Canceled {symbol} market data subscription")

            # Cleanup
            del self.symbol_subscriptions[symbol]
            if req_id in self.req_id_to_symbol:
                del self.req_id_to_symbol[req_id]
            if req_id in self.market_data_store:
                del self.market_data_store[req_id]

            return True

        except Exception as e:
            logger.error(f"❌ Error canceling {symbol} subscription: {e}")
            return False

    def get_connection_metrics(self) -> ConnectionMetrics:
        """Get connection metrics.

        Returns:
            Current connection metrics
        """
        # Update uptime
        if (
            self.state == ConnectionState.CONNECTED
            and self.metrics.last_connection_time
        ):
            self.metrics.total_uptime = (
                datetime.now() - self.metrics.last_connection_time
            )

        return self.metrics

    def is_healthy(self) -> bool:
        """Check if the connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        if self.state != ConnectionState.CONNECTED:
            return False

        if not self.client.isConnected():
            return False

        # Check if heartbeat is recent
        heartbeat_age = (datetime.now() - self.last_heartbeat).total_seconds()
        if heartbeat_age > 60:  # 1 minute threshold
            return False

        return True

    # Internal methods

    def _ensure_connected(self) -> bool:
        """Ensure we have a healthy connection."""
        if self.is_healthy():
            return True

        logger.info("Connection unhealthy, attempting to reconnect...")
        return self.reconnect()

    def _get_next_req_id(self) -> int:
        """Get next request ID thread-safely."""
        with self.req_id_lock:
            req_id = self.next_req_id
            self.next_req_id += 1
            return req_id

    def _create_forex_contract(self, symbol: str) -> Contract:
        """Create forex contract from symbol."""
        if "." in symbol:
            base, quote = symbol.split(".", 1)
        else:
            base = symbol[:3]
            quote = symbol[3:]

        contract = Contract()
        contract.symbol = base
        contract.secType = "CASH"
        contract.currency = quote
        contract.exchange = "IDEALPRO"

        return contract

    def _run_api_thread(self):
        """Run the IB API message loop."""
        try:
            logger.info("Starting IB API thread...")
            self.client.run()
        except Exception as e:
            logger.error(f"❌ API thread error: {e}")
            self.state = ConnectionState.FAILED
        finally:
            logger.info("IB API thread stopped")

    def _start_health_monitor(self):
        """Start health monitoring thread."""
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            return

        self.health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop, daemon=True
        )
        self.health_monitor_thread.start()
        logger.info("Started health monitor")

    def _health_monitor_loop(self):
        """Health monitoring loop."""
        while not self.shutdown_event.is_set():
            try:
                if self.state == ConnectionState.CONNECTED:
                    if not self.client.isConnected():
                        logger.warning("⚠️ Lost IB connection, attempting reconnect...")
                        self.reconnect()
                    else:
                        self.last_heartbeat = datetime.now()

                # Check for timed out requests
                self._check_timed_out_requests()

            except Exception as e:
                logger.error(f"❌ Health monitor error: {e}")

            self.shutdown_event.wait(self.health_check_interval)

    def _check_timed_out_requests(self):
        """Check for and handle timed out requests."""
        now = datetime.now()
        timed_out_requests = []

        for req_id, request in self.active_requests.items():
            age = (now - request.timestamp).total_seconds()
            if age > request.timeout:
                timed_out_requests.append(req_id)

        for req_id in timed_out_requests:
            logger.warning(f"⏰ Request {req_id} timed out")
            self._cleanup_request(req_id)

    def _cleanup_request(self, req_id: int):
        """Clean up request data."""
        if req_id in self.active_requests:
            del self.active_requests[req_id]
        if req_id in self.historical_data_store:
            del self.historical_data_store[req_id]
        if req_id in self.data_events:
            del self.data_events[req_id]
        if req_id in self.req_id_to_symbol:
            del self.req_id_to_symbol[req_id]

    def _cancel_all_subscriptions(self):
        """Cancel all active market data subscriptions."""
        symbols_to_cancel = list(self.symbol_subscriptions.keys())
        for symbol in symbols_to_cancel:
            self.cancel_market_data(symbol)

    # IB Callback handlers

    def _handle_connection_established(self, order_id: int):
        """Handle successful connection."""
        self.state = ConnectionState.CONNECTED
        self.next_req_id = order_id
        self.connection_event.set()
        self.last_heartbeat = datetime.now()
        logger.info(f"✅ IB connection established (next_order_id: {order_id})")

    def _handle_connection_closed(self):
        """Handle connection closed."""
        if self.state == ConnectionState.CONNECTED:
            logger.warning("⚠️ IB connection closed unexpectedly")
            self.state = ConnectionState.DISCONNECTED

            # Attempt reconnection if not shutting down
            if not self.shutdown_event.is_set():
                threading.Thread(target=self.reconnect, daemon=True).start()

    def _handle_error(
        self, req_id: int, error_code: int, error_string: str, advanced_json: str = ""
    ):
        """Enhanced error handling."""
        self.metrics.error_count += 1

        # Categorize errors
        if error_code in [502, 504]:  # Connection errors
            logger.error(f"❌ Connection error {error_code}: {error_string}")
            self.state = ConnectionState.FAILED
            self.circuit_breaker._record_failure()

        elif error_code in [200, 162, 300]:  # No security definition, no data, etc.
            logger.warning(
                f"⚠️ Data error {error_code}: {error_string} (reqId: {req_id})"
            )
            if req_id in self.active_requests:
                self.active_requests[req_id].status = "failed"
            self._signal_request_complete(req_id)

        elif error_code in [2104, 2106, 2158]:  # Informational
            logger.debug(f"ℹ️ Info {error_code}: {error_string}")

        else:
            logger.error(f"❌ Error {error_code}: {error_string} (reqId: {req_id})")

    def _handle_historical_data(self, req_id: int, bar):
        """Handle historical data bar."""
        if req_id not in self.historical_data_store:
            self.historical_data_store[req_id] = []

        self.historical_data_store[req_id].append(
            {
                "timestamp": bar.date,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": int(bar.volume) if bar.volume != -1 else 0,
            }
        )

    def _handle_historical_data_end(self, req_id: int, start: str, end: str):
        """Handle end of historical data."""
        logger.debug(f"Historical data complete for reqId {req_id}")
        self._signal_request_complete(req_id)

    def _handle_tick_price(self, req_id: int, tick_type: int, price: float, attrib):
        """Handle tick price data."""
        if req_id not in self.market_data_store:
            self.market_data_store[req_id] = {}

        # Get tick name
        if hasattr(TickTypeEnum, "toStr"):
            tick_name = TickTypeEnum.toStr(tick_type)
        else:
            tick_name = TickTypeEnum.to_str(tick_type)

        self.market_data_store[req_id][tick_name] = price
        self.last_heartbeat = datetime.now()

    def _handle_tick_size(self, req_id: int, tick_type: int, size: int):
        """Handle tick size data."""
        if req_id not in self.market_data_store:
            self.market_data_store[req_id] = {}

        # Get tick name
        if hasattr(TickTypeEnum, "toStr"):
            tick_name = TickTypeEnum.toStr(tick_type)
        else:
            tick_name = TickTypeEnum.to_str(tick_type)

        self.market_data_store[req_id][f"{tick_name}_SIZE"] = size

    def _signal_request_complete(self, req_id: int):
        """Signal that a request is complete."""
        if req_id in self.data_events:
            self.data_events[req_id].set()

    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.disconnect()
        except:
            pass
