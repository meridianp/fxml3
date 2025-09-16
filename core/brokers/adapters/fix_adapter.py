"""Native FIX Protocol Broker Adapter.

This adapter provides direct FIX protocol connectivity to brokers,
using simplefix for message handling and our custom session management.
"""

import asyncio
import logging
import socket
import ssl
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ...fix.messages.admin import Heartbeat, Logon, Logout, Reject, TestRequest
from ...fix.messages.base import ExecType, FIXMessage, FIXMessageType, OrdStatus, Side
from ...fix.messages.market_data import (
    MarketDataIncrementalRefresh,
    MarketDataRequest,
    MarketDataRequestReject,
    MarketDataSnapshot,
    MDEntryType,
    SubscriptionRequestType,
)
from ...fix.messages.order_modify import (
    OrderCancelReject,
    OrderCancelReplaceRequest,
    OrderStatusRequest,
)
from ...fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest
from ...fix.session_manager import (
    FIXSession,
    FIXSessionManager,
    SessionConfig,
    SessionState,
)
from ...fix.simplefix_translator import SIMPLEFIX_AVAILABLE, SimpleFIXTranslator
from .base import AdapterConfig, AdapterMetrics, BrokerAdapter, ConnectionStatus

logger = logging.getLogger(__name__)


class FIXConnection:
    """Handles FIX protocol network connection."""

    def __init__(
        self,
        host: str,
        port: int,
        use_ssl: bool = False,
        ssl_cert: Optional[str] = None,
        ssl_key: Optional[str] = None,
    ):
        """Initialize FIX connection.

        Args:
            host: FIX server hostname.
            port: FIX server port.
            use_ssl: Whether to use SSL/TLS.
            ssl_cert: Path to SSL certificate.
            ssl_key: Path to SSL private key.
        """
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key

        self.socket: Optional[socket.socket] = None
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False

    async def connect(self) -> bool:
        """Establish connection to FIX server."""
        try:
            if self.use_ssl:
                # Create SSL context
                ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                if self.ssl_cert and self.ssl_key:
                    ssl_context.load_cert_chain(self.ssl_cert, self.ssl_key)

                self.reader, self.writer = await asyncio.open_connection(
                    self.host, self.port, ssl=ssl_context
                )
            else:
                self.reader, self.writer = await asyncio.open_connection(
                    self.host, self.port
                )

            self.connected = True
            logger.info(f"Connected to FIX server at {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to FIX server: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Close FIX connection."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

        self.reader = None
        self.writer = None
        self.connected = False
        logger.info("Disconnected from FIX server")

    async def send(self, data: bytes) -> bool:
        """Send data over connection.

        Args:
            data: Raw bytes to send.

        Returns:
            True if sent successfully.
        """
        if not self.connected or not self.writer:
            return False

        try:
            self.writer.write(data)
            await self.writer.drain()
            return True
        except Exception as e:
            logger.error(f"Failed to send data: {e}")
            self.connected = False
            return False

    async def receive(self) -> Optional[bytes]:
        """Receive data from connection.

        Returns:
            Received bytes or None if error/disconnected.
        """
        if not self.connected or not self.reader:
            return None

        try:
            # Read up to 4KB at a time
            data = await self.reader.read(4096)
            if not data:
                # Connection closed
                self.connected = False
                return None
            return data
        except Exception as e:
            logger.error(f"Failed to receive data: {e}")
            self.connected = False
            return None


class FixBrokerAdapter(BrokerAdapter):
    """Native FIX protocol broker adapter implementation."""

    def __init__(self, config: AdapterConfig):
        """Initialize FIX adapter.

        Args:
            config: Adapter configuration.
        """
        super().__init__(config)

        if not SIMPLEFIX_AVAILABLE:
            raise ImportError(
                "simplefix library required. Install with: pip install simplefix"
            )

        # Connection parameters
        self.host = config.connection_params.get("host", "localhost")
        self.port = config.connection_params.get("port", 9876)
        self.use_ssl = config.connection_params.get("use_ssl", False)
        self.ssl_cert = config.connection_params.get("ssl_cert")
        self.ssl_key = config.connection_params.get("ssl_key")

        # Session configuration
        session_config = config.connection_params.get("session", {})
        self.session_config = SessionConfig(
            sender_comp_id=session_config.get("sender_comp_id", "FXML4"),
            target_comp_id=session_config.get("target_comp_id", "BROKER"),
            fix_version=session_config.get("fix_version", "FIX.4.2"),
            heartbeat_interval=session_config.get("heartbeat_interval", 30),
            logon_timeout=session_config.get("logon_timeout", 10),
            reset_on_logon=session_config.get("reset_on_logon", True),
        )

        # Components
        self.fix_connection = FIXConnection(
            self.host, self.port, self.use_ssl, self.ssl_cert, self.ssl_key
        )
        self.session_manager = FIXSessionManager()
        self.session: Optional[FIXSession] = None
        self.translator = SimpleFIXTranslator(
            self.session_config.sender_comp_id, self.session_config.target_comp_id
        )

        # Message handling
        self.receive_task: Optional[asyncio.Task] = None
        self.pending_orders: Dict[str, NewOrderSingle] = {}
        self.order_map: Dict[str, str] = {}  # cl_ord_id -> order_id
        self.pending_modifications: Dict[str, OrderCancelReplaceRequest] = {}

        # Market data subscriptions
        self.market_data_subscriptions: Dict[str, MarketDataRequest] = {}
        self.market_data_callback: Optional[Callable[[MarketDataSnapshot], None]] = None

        # Connection recovery
        self.reconnect_task: Optional[asyncio.Task] = None
        self.max_reconnect_attempts = config.connection_params.get(
            "max_reconnect_attempts", 5
        )
        self.reconnect_delay = config.connection_params.get("reconnect_delay", 5)
        self.reconnect_attempts = 0

        # Mock mode for testing
        self.mock_mode = config.connection_params.get("mock", False)

        # Metrics tracking
        self.metrics = AdapterMetrics()
        self.last_heartbeat_received = datetime.utcnow()

        # Shutdown flag for graceful disconnection
        self._shutdown_flag = False

        logger.info(f"Initialized FIX adapter for {self.host}:{self.port}")

    async def connect(self) -> bool:
        """Connect to FIX server and establish session."""
        try:
            logger.info(f"Connecting FIX adapter to {self.host}:{self.port}...")

            if self.mock_mode:
                # Mock connection for testing
                logger.info("Running in mock mode - simulating connection")
                self.fix_connection.connected = True
                self.connection.status = ConnectionStatus.CONNECTED

                # Create mock session
                self.session = self.session_manager.create_session(
                    session_id="MOCK_SESSION",
                    config=self.session_config,
                    message_callback=self._handle_message,
                )
                self.session.state = SessionState.ACTIVE

                # Simulate successful logon
                await asyncio.sleep(0.1)
                self.connection.status = ConnectionStatus.AUTHENTICATED

                logger.info("Mock FIX connection established")
                return True

            # Real connection
            self.connection.status = ConnectionStatus.CONNECTING

            # Connect to server
            if not await self.fix_connection.connect():
                self.connection.status = ConnectionStatus.ERROR
                self.connection.error_message = "Failed to connect to server"
                return False

            self.connection.status = ConnectionStatus.CONNECTED

            # Create session
            self.session = self.session_manager.create_session(
                session_id=f"{self.session_config.sender_comp_id}_{self.session_config.target_comp_id}",
                config=self.session_config,
                message_callback=self._handle_message,
            )

            # Start receiving messages
            self.receive_task = asyncio.create_task(self._receive_loop())

            # Send logon
            await self._send_logon()

            # Wait for logon response
            timeout = self.session_config.logon_timeout
            start_time = datetime.utcnow()

            while self.session.state != SessionState.ACTIVE:
                if (datetime.utcnow() - start_time).total_seconds() > timeout:
                    logger.error("Logon timeout")
                    await self.disconnect()
                    return False
                await asyncio.sleep(0.1)

            self.connection.status = ConnectionStatus.AUTHENTICATED
            self.metrics.last_connect_time = datetime.utcnow()

            logger.info("FIX adapter connected and logged on")
            return True

        except Exception as e:
            logger.error(f"Failed to connect FIX adapter: {e}")
            self.connection.status = ConnectionStatus.ERROR
            self.connection.error_message = str(e)
            return False

    async def disconnect(self) -> None:
        """Disconnect from FIX server."""
        try:
            logger.info("Disconnecting FIX adapter...")

            # Set shutdown flag to prevent reconnection
            self._shutdown_flag = True

            # Send logout if connected
            if self.session and self.session.state == SessionState.ACTIVE:
                await self._send_logout()
                await asyncio.sleep(1)  # Wait for logout response

            # Stop receiving
            if self.receive_task:
                self.receive_task.cancel()
                try:
                    await self.receive_task
                except asyncio.CancelledError:
                    pass

            # Close connection
            if not self.mock_mode:
                await self.fix_connection.disconnect()

            # Clean up session
            if self.session:
                self.session_manager.remove_session(self.session.session_id)
                self.session = None

            # Update status
            self.connection.status = ConnectionStatus.DISCONNECTED
            self.metrics.last_disconnect_time = datetime.utcnow()

            logger.info("FIX adapter disconnected")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def submit_order(self, order: NewOrderSingle) -> str:
        """Submit new order via FIX.

        Args:
            order: Order to submit.

        Returns:
            Order ID for tracking.
        """
        if not self._is_ready():
            raise RuntimeError("FIX adapter not ready")

        try:
            # Generate order ID
            order_id = f"FIX_{uuid.uuid4().hex[:8].upper()}"

            # Store order
            self.pending_orders[order.cl_ord_id] = order
            self.order_map[order.cl_ord_id] = order_id

            # Send order
            if self.mock_mode:
                # Simulate order submission
                logger.info(f"Mock order submitted: {order.cl_ord_id}")

                # Simulate acknowledgment after delay
                asyncio.create_task(self._simulate_order_ack(order, order_id))
            else:
                # Send real FIX message
                await self._send_message(order)

            self.metrics.total_orders += 1
            logger.info(f"Order submitted: {order.cl_ord_id} -> {order_id}")
            return order_id

        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            self.metrics.failed_orders += 1
            raise

    async def cancel_order(self, cancel_request: OrderCancelRequest) -> bool:
        """Cancel order via FIX.

        Args:
            cancel_request: Cancellation request.

        Returns:
            True if cancel request sent successfully.
        """
        if not self._is_ready():
            return False

        try:
            if self.mock_mode:
                # Simulate cancel
                logger.info(f"Mock cancel sent: {cancel_request.orig_cl_ord_id}")

                # Simulate cancel ack
                asyncio.create_task(self._simulate_cancel_ack(cancel_request))
            else:
                # Send real cancel
                await self._send_message(cancel_request)

            self.metrics.cancelled_orders += 1
            return True

        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False

    async def modify_order(self, modify_request: OrderCancelReplaceRequest) -> bool:
        """Modify order using OrderCancelReplaceRequest (35=G).

        Args:
            modify_request: Order modification request.

        Returns:
            True if modify request sent successfully.
        """
        if not self._is_ready():
            logger.error("FIX adapter not ready for order modification")
            return False

        try:
            # Validate the modification request
            if not modify_request.orig_cl_ord_id:
                logger.error("Original client order ID required for modification")
                return False

            # Check if original order exists
            if modify_request.orig_cl_ord_id not in self.pending_orders:
                logger.warning(
                    f"Original order {modify_request.orig_cl_ord_id} not found in pending orders"
                )

            # Store pending modification
            self.pending_modifications[modify_request.cl_ord_id] = modify_request

            if self.mock_mode:
                # Simulate modification
                logger.info(
                    f"Mock order modification: {modify_request.orig_cl_ord_id} -> {modify_request.cl_ord_id}"
                )

                # Simulate modification acknowledgment
                asyncio.create_task(self._simulate_modification_ack(modify_request))
            else:
                # Send real FIX modification message
                await self._send_message(modify_request)

            self.metrics.total_modifications += 1
            logger.info(
                f"Order modification sent: {modify_request.orig_cl_ord_id} -> {modify_request.cl_ord_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to modify order: {e}")
            self.metrics.failed_modifications += 1
            return False

    async def get_order_status(self, cl_ord_id: str) -> Optional[ExecutionReport]:
        """Get order status by requesting from broker.

        Args:
            cl_ord_id: Client order ID.

        Returns:
            Latest execution report or None.
        """
        if not self._is_ready():
            return None

        try:
            # Create order status request
            status_request = OrderStatusRequest(
                cl_ord_id=cl_ord_id,
                symbol="UNKNOWN",  # Would need to track original order details
                side=Side.BUY,  # Would need to track original order details
            )

            if self.mock_mode:
                # Return mock status
                return await self._get_mock_order_status(cl_ord_id)
            else:
                # Send status request
                await self._send_message(status_request)
                # In real implementation, would wait for response
                return None

        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return None

    async def _get_mock_order_status(self, cl_ord_id: str) -> Optional[ExecutionReport]:
        """Get mock order status for testing."""
        if cl_ord_id in self.pending_orders:
            order = self.pending_orders[cl_ord_id]
            order_id = self.order_map.get(cl_ord_id, "MOCK_ORDER_ID")

            return ExecutionReport(
                order_id=order_id,
                cl_ord_id=cl_ord_id,
                exec_id=f"EXEC_{uuid.uuid4().hex[:8]}",
                exec_type=ExecType.ORDER_STATUS,
                ord_status=OrdStatus.NEW,
                symbol=order.symbol,
                side=order.side,
                order_qty=order.order_qty,
                cum_qty=0,
                leaves_qty=order.order_qty,
                avg_px=0,
                transact_time=datetime.utcnow(),
                text="Order status - working",
            )
        return None

    def _is_ready(self) -> bool:
        """Check if adapter is ready for operations."""
        return (
            self.connection.is_ready()
            and self.session is not None
            and self.session.state == SessionState.ACTIVE
        )

    async def _send_message(self, message: FIXMessage) -> bool:
        """Send FIX message.

        Args:
            message: Message to send.

        Returns:
            True if sent successfully.
        """
        if not self.session:
            return False

        try:
            # Get sequence number
            seq_num = self.session.get_next_seq_num()

            # Encode message
            msg_bytes = self.translator.encode_bytes(message, seq_num)

            # Store for resend
            self.session.store_sent_message(seq_num, message)

            # Send
            if self.mock_mode:
                logger.debug(f"Mock send: {msg_bytes}")
            else:
                success = await self.fix_connection.send(msg_bytes)
                if not success:
                    return False

            # Update stats
            self.session.stats.messages_sent += 1
            self.session.stats.bytes_sent += len(msg_bytes)
            self.session.stats.last_sent_time = datetime.utcnow()

            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def _receive_loop(self):
        """Receive and process FIX messages."""
        buffer = b""

        while self.fix_connection.connected:
            try:
                # Receive data
                data = await self.fix_connection.receive()
                if not data:
                    logger.warning("Connection closed by server")
                    break

                buffer += data

                # Parse messages
                while True:
                    message = self.translator.parse_bytes(buffer)
                    if not message:
                        break

                    # Remove parsed message from buffer
                    # This is simplified - real implementation would track position
                    buffer = b""

                    # Process message
                    await self._process_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Receive loop error: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, message: FIXMessage):
        """Process received FIX message."""
        if not self.session:
            return

        # Update session stats
        self.session.stats.messages_received += 1
        self.session.stats.last_received_time = datetime.utcnow()

        # Handle by message type
        if isinstance(message, ExecutionReport):
            await self._handle_execution_report(message)
        elif isinstance(message, MarketDataSnapshot):
            await self._handle_market_data_snapshot(message)
        elif isinstance(message, MarketDataIncrementalRefresh):
            await self._handle_market_data_incremental(message)
        elif isinstance(message, MarketDataRequestReject):
            await self._handle_market_data_reject(message)
        elif isinstance(message, OrderCancelReject):
            await self._handle_cancel_reject(message)
        elif isinstance(message, TestRequest):
            await self.handle_test_request(message)
        elif isinstance(message, Heartbeat):
            await self._handle_heartbeat_received(message)
        elif isinstance(message, Logout):
            await self._handle_logout_received(message)
        else:
            # Pass to session callback
            if self.session.message_callback:
                self.session.message_callback(message)

    def _handle_message(self, message: FIXMessage):
        """Session callback for non-order messages."""
        logger.debug(f"Received message: {type(message).__name__}")

    async def _handle_execution_report(self, report: ExecutionReport):
        """Handle execution report."""
        logger.info(f"Execution report: {report.cl_ord_id} - {report.ord_status.name}")

        # Update metrics based on status
        if report.ord_status == OrdStatus.FILLED:
            self.metrics.filled_orders += 1
        elif report.ord_status == OrdStatus.REJECTED:
            self.metrics.rejected_orders += 1

        # Remove from pending if terminal state
        if report.ord_status in [
            OrdStatus.FILLED,
            OrdStatus.CANCELED,
            OrdStatus.REJECTED,
        ]:
            self.pending_orders.pop(report.cl_ord_id, None)

    async def _send_logon(self):
        """Send FIX logon message."""
        try:
            # Create logon message
            logon = Logon(
                heartbt_int=self.session_config.heartbeat_interval,
                username=self.config.authentication.get("username"),
                password=self.config.authentication.get("password"),
                reset_seq_num_flag=self.session_config.reset_on_logon,
            )

            if self.session and self.session.config.reset_on_logon:
                self.session.reset_sequence_numbers()

            # Send logon message
            await self._send_message(logon)
            logger.info("FIX logon message sent")

        except Exception as e:
            logger.error(f"Failed to send logon: {e}")
            raise

    async def _send_logout(self):
        """Send FIX logout message."""
        try:
            # Create logout message
            logout = Logout(text="Normal logout")

            # Send logout message
            await self._send_message(logout)
            logger.info("FIX logout message sent")

        except Exception as e:
            logger.error(f"Failed to send logout: {e}")

    async def _send_heartbeat(self):
        """Send FIX heartbeat."""
        if self.session:
            self.session.update_heartbeat_sent()

    async def _simulate_order_ack(self, order: NewOrderSingle, order_id: str):
        """Simulate order acknowledgment for testing."""
        await asyncio.sleep(0.1)

        # Create execution report
        report = ExecutionReport(
            order_id=order_id,
            cl_ord_id=order.cl_ord_id,
            exec_id=f"EXEC_{uuid.uuid4().hex[:8]}",
            exec_type=ExecType.NEW,
            ord_status=OrdStatus.NEW,
            symbol=order.symbol,
            side=order.side,
            order_qty=order.order_qty,
            price=getattr(order, "price", 0),
            cum_qty=0,
            leaves_qty=order.order_qty,
            avg_px=0,
            transact_time=datetime.utcnow(),
            text="Order acknowledged",
        )

        await self._handle_execution_report(report)

        # Simulate fill after delay
        if self.config.features.get("simulate_fills", True):
            asyncio.create_task(self._simulate_order_fill(order, order_id))

    async def _simulate_order_fill(self, order: NewOrderSingle, order_id: str):
        """Simulate order fill for testing."""
        await asyncio.sleep(1)

        fill_price = getattr(order, "price", 1.0)
        if fill_price == 0:  # Market order
            fill_price = 1.0850  # Mock price

        report = ExecutionReport(
            order_id=order_id,
            cl_ord_id=order.cl_ord_id,
            exec_id=f"EXEC_{uuid.uuid4().hex[:8]}",
            exec_type=ExecType.TRADE,
            ord_status=OrdStatus.FILLED,
            symbol=order.symbol,
            side=order.side,
            order_qty=order.order_qty,
            price=fill_price,
            cum_qty=order.order_qty,
            leaves_qty=0,
            avg_px=fill_price,
            transact_time=datetime.utcnow(),
            text="Order filled",
        )

        await self._handle_execution_report(report)

    # Market Data Methods

    async def subscribe_market_data(self, symbols: List[str]) -> bool:
        """Subscribe to market data for symbols.

        Args:
            symbols: List of symbols to subscribe to.

        Returns:
            True if subscription successful.
        """
        if not self._is_ready():
            logger.error("FIX adapter not ready for market data subscription")
            return False

        try:
            # Create market data request
            md_request = MarketDataRequest(
                symbols=symbols,
                md_entry_types=[MDEntryType.BID, MDEntryType.OFFER, MDEntryType.TRADE],
                subscription_request_type=SubscriptionRequestType.SNAPSHOT_PLUS_UPDATES,
                market_depth=1,
            )

            # Store subscription
            self.market_data_subscriptions[md_request.md_req_id] = md_request

            if self.mock_mode:
                # Simulate market data subscription
                logger.info(f"Mock market data subscription for: {symbols}")

                # Simulate market data snapshot
                asyncio.create_task(
                    self._simulate_market_data_snapshot(
                        symbols[0], md_request.md_req_id
                    )
                )
            else:
                # Send real market data request
                await self._send_message(md_request)

            logger.info(f"Market data subscription sent for symbols: {symbols}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to market data: {e}")
            return False

    async def unsubscribe_market_data(self, symbols: List[str]) -> bool:
        """Unsubscribe from market data.

        Args:
            symbols: List of symbols to unsubscribe from.

        Returns:
            True if unsubscription successful.
        """
        if not self._is_ready():
            return False

        try:
            # Create unsubscribe request
            md_request = MarketDataRequest(
                symbols=symbols,
                subscription_request_type=SubscriptionRequestType.DISABLE_PREVIOUS,
            )

            if self.mock_mode:
                logger.info(f"Mock market data unsubscription for: {symbols}")
            else:
                await self._send_message(md_request)

            # Remove from subscriptions
            for req_id, req in list(self.market_data_subscriptions.items()):
                if any(symbol in req.symbols for symbol in symbols):
                    del self.market_data_subscriptions[req_id]

            logger.info(f"Market data unsubscription sent for symbols: {symbols}")
            return True

        except Exception as e:
            logger.error(f"Failed to unsubscribe from market data: {e}")
            return False

    def set_market_data_callback(
        self, callback: Callable[[MarketDataSnapshot], None]
    ) -> None:
        """Set callback for market data updates.

        Args:
            callback: Function to call with market data snapshots.
        """
        self.market_data_callback = callback

    async def _simulate_market_data_snapshot(self, symbol: str, md_req_id: str):
        """Simulate market data snapshot for testing."""
        await asyncio.sleep(0.2)

        from ...fix.messages.market_data import create_market_data_snapshot

        # Create mock snapshot
        snapshot = create_market_data_snapshot(
            symbol=symbol,
            bid_price=1.08450,
            bid_size=1000000,
            offer_price=1.08470,
            offer_size=1500000,
            md_req_id=md_req_id,
        )

        await self._handle_market_data_snapshot(snapshot)

    async def _handle_market_data_snapshot(self, snapshot: MarketDataSnapshot):
        """Handle incoming market data snapshot."""
        logger.debug(
            f"Market data snapshot: {snapshot.symbol} - {len(snapshot.entries)} entries"
        )

        # Notify callback
        if self.market_data_callback:
            try:
                self.market_data_callback(snapshot)
            except Exception as e:
                logger.error(f"Error in market data callback: {e}")

    # Session Management Enhancements

    async def send_heartbeat(self) -> bool:
        """Send heartbeat to maintain session.

        Returns:
            True if heartbeat sent successfully.
        """
        if not self.session:
            return False

        try:
            heartbeat = Heartbeat()

            if self.mock_mode:
                logger.debug("Mock heartbeat sent")
                self.last_heartbeat_received = datetime.utcnow()
            else:
                await self._send_message(heartbeat)

            self.session.update_heartbeat_sent()
            return True

        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False

    async def handle_test_request(self, test_request: TestRequest) -> bool:
        """Handle incoming test request.

        Args:
            test_request: Test request message.

        Returns:
            True if handled successfully.
        """
        try:
            # Respond with heartbeat containing test request ID
            heartbeat = Heartbeat(test_req_id=test_request.test_req_id)

            if self.mock_mode:
                logger.debug(
                    f"Mock heartbeat response to test request: {test_request.test_req_id}"
                )
            else:
                await self._send_message(heartbeat)

            logger.debug(f"Responded to test request: {test_request.test_req_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to handle test request: {e}")
            return False

    async def _simulate_cancel_ack(self, cancel: OrderCancelRequest):
        """Simulate cancel acknowledgment for testing."""
        await asyncio.sleep(0.1)

        order_id = self.order_map.get(cancel.orig_cl_ord_id, "UNKNOWN")

        report = ExecutionReport(
            order_id=order_id,
            cl_ord_id=cancel.orig_cl_ord_id,
            exec_id=f"EXEC_{uuid.uuid4().hex[:8]}",
            exec_type=ExecType.CANCELED,
            ord_status=OrdStatus.CANCELED,
            symbol=cancel.symbol,
            side=cancel.side,
            order_qty=0,
            cum_qty=0,
            leaves_qty=0,
            avg_px=0,
            transact_time=datetime.utcnow(),
            text="Order cancelled",
        )

        await self._handle_execution_report(report)

    async def _simulate_modification_ack(
        self, modify_request: OrderCancelReplaceRequest
    ):
        """Simulate order modification acknowledgment for testing."""
        await asyncio.sleep(0.1)

        # Create execution report for cancel of original order
        orig_order_id = self.order_map.get(modify_request.orig_cl_ord_id, "UNKNOWN")

        cancel_report = ExecutionReport(
            order_id=orig_order_id,
            cl_ord_id=modify_request.orig_cl_ord_id,
            exec_id=f"EXEC_{uuid.uuid4().hex[:8]}",
            exec_type=ExecType.CANCELED,
            ord_status=OrdStatus.CANCELED,
            symbol=modify_request.symbol,
            side=modify_request.side,
            order_qty=0,
            cum_qty=0,
            leaves_qty=0,
            avg_px=0,
            transact_time=datetime.utcnow(),
            text="Order cancelled for replacement",
        )

        await self._handle_execution_report(cancel_report)

        # Create execution report for new order
        new_order_id = f"FIX_{uuid.uuid4().hex[:8].upper()}"
        self.order_map[modify_request.cl_ord_id] = new_order_id

        new_report = ExecutionReport(
            order_id=new_order_id,
            cl_ord_id=modify_request.cl_ord_id,
            exec_id=f"EXEC_{uuid.uuid4().hex[:8]}",
            exec_type=ExecType.NEW,
            ord_status=OrdStatus.NEW,
            symbol=modify_request.symbol,
            side=modify_request.side,
            order_qty=modify_request.order_qty,
            price=modify_request.price,
            cum_qty=0,
            leaves_qty=modify_request.order_qty,
            avg_px=0,
            transact_time=datetime.utcnow(),
            text="Order replaced",
        )

        await self._handle_execution_report(new_report)

    # Additional Message Handlers

    async def _handle_market_data_incremental(
        self, incremental: MarketDataIncrementalRefresh
    ):
        """Handle market data incremental refresh."""
        logger.debug(f"Market data incremental: {len(incremental.entries)} entries")

        # Convert to snapshot format for callback
        if self.market_data_callback and incremental.entries:
            # For simplicity, create a minimal snapshot
            snapshot = MarketDataSnapshot(
                symbol="UNKNOWN",  # Would need to track symbol mapping
                entries=incremental.entries,
                md_req_id=incremental.md_req_id,
            )
            await self._handle_market_data_snapshot(snapshot)

    async def _handle_market_data_reject(self, reject: MarketDataRequestReject):
        """Handle market data request rejection."""
        logger.warning(
            f"Market data request rejected: {reject.md_req_id} - {reject.text}"
        )

        # Remove from subscriptions
        if reject.md_req_id in self.market_data_subscriptions:
            del self.market_data_subscriptions[reject.md_req_id]

    async def _handle_cancel_reject(self, reject: OrderCancelReject):
        """Handle order cancel/replace rejection."""
        logger.warning(
            f"Order cancel/replace rejected: {reject.cl_ord_id} - {reject.text}"
        )

        # Remove from pending modifications if this was a replace
        if reject.cl_ord_id in self.pending_modifications:
            del self.pending_modifications[reject.cl_ord_id]
            self.metrics.failed_modifications += 1

    async def _handle_heartbeat_received(self, heartbeat: Heartbeat):
        """Handle received heartbeat."""
        self.last_heartbeat_received = datetime.utcnow()
        if self.session:
            self.session.update_heartbeat_received()
        logger.debug("Heartbeat received")

    async def _handle_logout_received(self, logout: Logout):
        """Handle received logout."""
        logger.info(f"Logout received: {logout.text}")

        # Update session state
        if self.session:
            self.session.state = SessionState.DISCONNECTED

        # Update connection status
        self.connection.status = ConnectionStatus.DISCONNECTED

        # Trigger reconnection if not expected
        if not self._shutdown_flag:
            logger.warning("Unexpected logout received - attempting reconnection")
            self._schedule_reconnection()

    def _schedule_reconnection(self):
        """Schedule automatic reconnection."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                f"Max reconnection attempts ({self.max_reconnect_attempts}) exceeded"
            )
            return

        if self.reconnect_task and not self.reconnect_task.done():
            return  # Reconnection already scheduled

        self.reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self):
        """Attempt to reconnect after delay."""
        try:
            self.reconnect_attempts += 1
            delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 60)

            logger.info(
                f"Reconnection attempt {self.reconnect_attempts} in {delay} seconds"
            )
            await asyncio.sleep(delay)

            # Attempt reconnection
            if await self.connect():
                logger.info("Reconnection successful")
                self.reconnect_attempts = 0
            else:
                logger.error("Reconnection failed")
                self._schedule_reconnection()

        except Exception as e:
            logger.error(f"Reconnection error: {e}")
            self._schedule_reconnection()

    # Abstract Method Implementations from BrokerAdapter

    async def authenticate(self) -> bool:
        """Authenticate with broker (handled during logon)."""
        # Authentication is handled during the logon process in FIX
        return self.connection.status == ConnectionStatus.AUTHENTICATED

    async def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self.connection.is_ready()

    async def get_open_orders(self) -> List[Any]:
        """Get all open orders."""
        # Convert pending orders to the expected format
        from .base import OrderInfo, OrderStatus

        open_orders = []
        for cl_ord_id, order in self.pending_orders.items():
            order_info = OrderInfo(
                cl_ord_id=cl_ord_id,
                order_id=self.order_map.get(cl_ord_id),
                status=OrderStatus.WORKING,  # Simplified status
                original_order=order,
                created_at=datetime.utcnow(),  # Would track real creation time
                remaining_qty=order.order_qty or 0,
            )
            open_orders.append(order_info)

        return open_orders

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        return {
            "account_id": self.config.authentication.get("account", "UNKNOWN"),
            "adapter_type": "FIX",
            "connection_status": self.connection.status.value,
            "session_active": self.session
            and self.session.state == SessionState.ACTIVE,
            "host": self.host,
            "port": self.port,
            "sender_comp_id": self.session_config.sender_comp_id,
            "target_comp_id": self.session_config.target_comp_id,
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        # FIX protocol doesn't provide position information directly
        # Would need separate position reporting or maintain internal tracking
        return []
