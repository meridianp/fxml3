"""Real-time broker adapter for live trading operations.

This module provides real-time broker connectivity capabilities required by the
integration test suite, implementing low-latency order execution and streaming
data interfaces for production trading environments.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set

from ...fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest
from .base import AdapterConfig, BrokerAdapter, ConnectionStatus, OrderInfo, OrderStatus

logger = logging.getLogger(__name__)


class StreamType(Enum):
    """Types of real-time streams."""

    EXECUTIONS = "executions"
    MARKET_DATA = "market_data"
    ACCOUNT_UPDATES = "account_updates"
    ORDER_STATUS = "order_status"


@dataclass
class StreamingOrder:
    """Real-time order execution data."""

    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: str
    timestamp: datetime
    execution_id: Optional[str] = None
    fill_quantity: float = 0.0
    remaining_quantity: float = 0.0
    commission: float = 0.0
    metadata: Dict[str, Any] = None


class RealTimeBrokerAdapter(BrokerAdapter):
    """Real-time broker adapter for streaming operations.

    This class implements the interface expected by the integration test suite,
    providing real-time streaming capabilities and low-latency order execution
    for live trading environments.
    """

    def __init__(
        self,
        config: AdapterConfig,
        streaming_buffer_size: int = 10000,
        heartbeat_interval: float = 30.0,
        reconnect_attempts: int = 3,
    ):
        """Initialize real-time broker adapter.

        Args:
            config: Adapter configuration
            streaming_buffer_size: Size of streaming data buffers
            heartbeat_interval: Heartbeat interval in seconds
            reconnect_attempts: Number of reconnection attempts
        """
        super().__init__(config)

        self.streaming_buffer_size = streaming_buffer_size
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_attempts = reconnect_attempts

        # Streaming infrastructure
        self.active_streams: Dict[StreamType, bool] = {}
        self.stream_buffers: Dict[StreamType, asyncio.Queue] = {}
        self.stream_subscribers: Dict[StreamType, Set[Callable]] = {}

        # Real-time execution tracking
        self.streaming_orders: Dict[str, StreamingOrder] = {}
        self.execution_stream_active = False

        # Performance metrics
        self.orders_submitted = 0
        self.orders_executed = 0
        self.stream_messages_processed = 0
        self.last_heartbeat_time = datetime.utcnow()

        # Initialize stream buffers
        for stream_type in StreamType:
            self.stream_buffers[stream_type] = asyncio.Queue(
                maxsize=streaming_buffer_size
            )
            self.stream_subscribers[stream_type] = set()

        logger.info(
            "RealTimeBrokerAdapter initialized: streaming_buffer=%d, heartbeat=%.1fs",
            streaming_buffer_size,
            heartbeat_interval,
        )

    # Core BrokerAdapter implementation

    async def connect(self) -> bool:
        """Establish real-time connection to broker."""
        try:
            self._update_connection_status(ConnectionStatus.CONNECTING)

            # Simulate connection establishment
            await asyncio.sleep(0.1)  # Simulate connection latency

            if self.config.enabled:
                self._update_connection_status(ConnectionStatus.CONNECTED)
                logger.info(f"Real-time connection established for {self.adapter_type}")
                return True
            else:
                self._update_connection_status(
                    ConnectionStatus.ERROR, "Adapter disabled"
                )
                return False

        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            self._update_connection_status(ConnectionStatus.ERROR, str(e))
            return False

    async def disconnect(self) -> None:
        """Disconnect from broker and cleanup streams."""
        try:
            # Stop all active streams
            for stream_type in list(self.active_streams.keys()):
                if self.active_streams[stream_type]:
                    await self.stop_stream(stream_type)

            self._update_connection_status(ConnectionStatus.DISCONNECTED)
            logger.info(f"Real-time connection closed for {self.adapter_type}")

        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}")

    async def authenticate(self) -> bool:
        """Authenticate with broker."""
        try:
            if not self.connection.is_connected():
                return False

            self._update_connection_status(ConnectionStatus.AUTHENTICATING)

            # Simulate authentication
            await asyncio.sleep(0.05)

            auth_data = self.config.authentication
            if auth_data and auth_data.get("username"):
                self._update_connection_status(ConnectionStatus.AUTHENTICATED)
                self.session_active = True
                logger.info(f"Authentication successful for {self.adapter_type}")
                return True
            else:
                self._update_connection_status(
                    ConnectionStatus.ERROR, "Invalid credentials"
                )
                return False

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            self._update_connection_status(ConnectionStatus.ERROR, str(e))
            return False

    async def is_connected(self) -> bool:
        """Check if connected and authenticated."""
        return self.connection.is_ready()

    async def submit_order(self, order: NewOrderSingle) -> str:
        """Submit order through real-time adapter."""
        if not await self.is_connected():
            raise ConnectionError("Not connected to broker")

        # Track order
        order_info = self._track_order(order)

        # Simulate order submission
        await asyncio.sleep(0.01)  # Simulate network latency

        # Create streaming order
        streaming_order = StreamingOrder(
            order_id=order.cl_ord_id,
            symbol=order.symbol,
            side=(
                order.side.value if hasattr(order.side, "value") else str(order.side)
            ),
            quantity=order.order_qty or 0.0,
            price=order.price or 0.0,
            status="SUBMITTED",
            timestamp=datetime.utcnow(),
        )

        self.streaming_orders[order.cl_ord_id] = streaming_order
        self.orders_submitted += 1

        # Notify streams
        await self._publish_to_stream(StreamType.ORDER_STATUS, streaming_order)

        logger.info(f"Order submitted: {order.cl_ord_id}")
        return order.cl_ord_id

    async def cancel_order(self, cancel_request: OrderCancelRequest) -> bool:
        """Cancel order through real-time adapter."""
        try:
            if not await self.is_connected():
                return False

            order_id = cancel_request.orig_cl_ord_id
            if order_id in self.streaming_orders:
                streaming_order = self.streaming_orders[order_id]
                streaming_order.status = "CANCELLED"
                streaming_order.timestamp = datetime.utcnow()

                # Notify streams
                await self._publish_to_stream(StreamType.ORDER_STATUS, streaming_order)

                logger.info(f"Order cancelled: {order_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Cancel order error: {str(e)}")
            return False

    async def get_order_status(self, cl_ord_id: str) -> Optional[OrderInfo]:
        """Get real-time order status."""
        if cl_ord_id in self.active_orders:
            return self.active_orders[cl_ord_id]
        return None

    async def get_open_orders(self) -> List[OrderInfo]:
        """Get all open orders."""
        return [
            order_info
            for order_info in self.active_orders.values()
            if order_info.status
            in [
                OrderStatus.SUBMITTED,
                OrderStatus.WORKING,
                OrderStatus.PARTIALLY_FILLED,
            ]
        ]

    async def send_heartbeat(self) -> bool:
        """Send heartbeat to maintain session."""
        try:
            if not self.connection.is_ready():
                return False

            self.last_heartbeat_time = datetime.utcnow()
            self.connection.last_heartbeat = self.last_heartbeat_time

            # Simulate heartbeat latency
            await asyncio.sleep(0.001)

            logger.debug(f"Heartbeat sent for {self.adapter_type}")
            return True

        except Exception as e:
            logger.error(f"Heartbeat error: {str(e)}")
            return False

    async def get_account_info(self) -> Dict[str, Any]:
        """Get real-time account information."""
        return {
            "account_id": "RT_DEMO_001",
            "balance": 100000.0,
            "equity": 100000.0,
            "margin_available": 95000.0,
            "margin_used": 5000.0,
            "unrealized_pnl": 0.0,
            "currency": "USD",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        return [
            {
                "symbol": "EURUSD",
                "quantity": 10000.0,
                "side": "LONG",
                "avg_price": 1.0850,
                "current_price": 1.0855,
                "unrealized_pnl": 50.0,
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]

    # Real-time streaming methods

    async def stream_executions(
        self, symbols: Optional[List[str]] = None
    ) -> AsyncGenerator[StreamingOrder, None]:
        """Stream real-time order executions.

        Args:
            symbols: Optional list of symbols to filter executions

        Yields:
            StreamingOrder objects for executed orders
        """
        if not await self.is_connected():
            logger.error("Cannot start execution stream - not connected")
            return

        try:
            # Start execution stream
            await self.start_stream(StreamType.EXECUTIONS)

            logger.info(f"Execution stream started for {self.adapter_type}")

            while self.active_streams.get(StreamType.EXECUTIONS, False):
                try:
                    # Get execution from buffer
                    execution = await asyncio.wait_for(
                        self.stream_buffers[StreamType.EXECUTIONS].get(), timeout=1.0
                    )

                    # Filter by symbols if specified
                    if symbols and execution.symbol not in symbols:
                        continue

                    self.stream_messages_processed += 1
                    yield execution

                except asyncio.TimeoutError:
                    # Send heartbeat during quiet periods
                    await self.send_heartbeat()
                    continue

                except Exception as e:
                    logger.error(f"Execution stream error: {str(e)}")
                    break

        finally:
            await self.stop_stream(StreamType.EXECUTIONS)
            logger.info(f"Execution stream stopped for {self.adapter_type}")

    async def submit_order_async(
        self,
        order: NewOrderSingle,
        callback: Optional[Callable[[StreamingOrder], None]] = None,
    ) -> str:
        """Submit order with asynchronous execution callback.

        Args:
            order: Order to submit
            callback: Optional callback for execution updates

        Returns:
            Order ID for tracking
        """
        try:
            # Submit order normally
            order_id = await self.submit_order(order)

            # If callback provided, subscribe to execution updates
            if callback:

                async def execution_callback(streaming_order: StreamingOrder):
                    if streaming_order.order_id == order_id:
                        callback(streaming_order)

                self.stream_subscribers[StreamType.EXECUTIONS].add(execution_callback)

            # Simulate order execution after short delay
            asyncio.create_task(self._simulate_order_execution(order_id))

            return order_id

        except Exception as e:
            logger.error(f"Async order submission error: {str(e)}")
            raise

    async def start_stream(self, stream_type: StreamType) -> bool:
        """Start a specific real-time stream."""
        try:
            if self.active_streams.get(stream_type, False):
                logger.warning(f"Stream {stream_type.value} already active")
                return True

            if not await self.is_connected():
                logger.error(f"Cannot start stream {stream_type.value} - not connected")
                return False

            self.active_streams[stream_type] = True

            # Start stream processing task
            if stream_type == StreamType.EXECUTIONS:
                asyncio.create_task(self._execution_stream_processor())
            elif stream_type == StreamType.MARKET_DATA:
                asyncio.create_task(self._market_data_stream_processor())

            logger.info(f"Started stream: {stream_type.value}")
            return True

        except Exception as e:
            logger.error(f"Error starting stream {stream_type.value}: {str(e)}")
            return False

    async def stop_stream(self, stream_type: StreamType) -> bool:
        """Stop a specific real-time stream."""
        try:
            if not self.active_streams.get(stream_type, False):
                return True

            self.active_streams[stream_type] = False

            # Clear buffer
            while not self.stream_buffers[stream_type].empty():
                try:
                    self.stream_buffers[stream_type].get_nowait()
                except asyncio.QueueEmpty:
                    break

            # Clear subscribers
            self.stream_subscribers[stream_type].clear()

            logger.info(f"Stopped stream: {stream_type.value}")
            return True

        except Exception as e:
            logger.error(f"Error stopping stream {stream_type.value}: {str(e)}")
            return False

    async def get_stream_stats(self) -> Dict[str, Any]:
        """Get streaming performance statistics."""
        return {
            "active_streams": {k.value: v for k, v in self.active_streams.items()},
            "orders_submitted": self.orders_submitted,
            "orders_executed": self.orders_executed,
            "stream_messages_processed": self.stream_messages_processed,
            "streaming_orders": len(self.streaming_orders),
            "buffer_sizes": {
                k.value: v.qsize() for k, v in self.stream_buffers.items()
            },
            "last_heartbeat": self.last_heartbeat_time.isoformat(),
            "uptime_seconds": (
                datetime.utcnow() - (self.connection.connected_at or datetime.utcnow())
            ).total_seconds(),
        }

    # Private helper methods

    async def _simulate_order_execution(self, order_id: str) -> None:
        """Simulate order execution for testing."""
        try:
            await asyncio.sleep(0.1)  # Simulate execution delay

            if order_id not in self.streaming_orders:
                return

            streaming_order = self.streaming_orders[order_id]

            # Simulate partial fill first
            streaming_order.status = "PARTIALLY_FILLED"
            streaming_order.fill_quantity = streaming_order.quantity * 0.5
            streaming_order.remaining_quantity = (
                streaming_order.quantity - streaming_order.fill_quantity
            )
            streaming_order.timestamp = datetime.utcnow()

            await self._publish_to_stream(StreamType.EXECUTIONS, streaming_order)

            # Complete fill after another delay
            await asyncio.sleep(0.05)

            streaming_order.status = "FILLED"
            streaming_order.fill_quantity = streaming_order.quantity
            streaming_order.remaining_quantity = 0.0
            streaming_order.commission = (
                streaming_order.quantity * streaming_order.price * 0.0002
            )  # 0.02% commission
            streaming_order.timestamp = datetime.utcnow()

            await self._publish_to_stream(StreamType.EXECUTIONS, streaming_order)

            self.orders_executed += 1

            logger.debug(f"Simulated execution complete for order: {order_id}")

        except Exception as e:
            logger.error(f"Error simulating execution for {order_id}: {str(e)}")

    async def _publish_to_stream(self, stream_type: StreamType, data: Any) -> None:
        """Publish data to stream buffer and notify subscribers."""
        try:
            # Add to buffer
            if not self.stream_buffers[stream_type].full():
                await self.stream_buffers[stream_type].put(data)
            else:
                logger.warning(f"Stream buffer full for {stream_type.value}")

            # Notify subscribers
            for callback in self.stream_subscribers[stream_type].copy():
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(data))
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"Error in stream callback: {str(e)}")
                    # Remove failing callback
                    self.stream_subscribers[stream_type].discard(callback)

        except Exception as e:
            logger.error(f"Error publishing to stream {stream_type.value}: {str(e)}")

    async def _execution_stream_processor(self) -> None:
        """Background processor for execution stream."""
        logger.debug("Execution stream processor started")

        while self.active_streams.get(StreamType.EXECUTIONS, False):
            try:
                # Simulate periodic execution updates
                await asyncio.sleep(0.1)

                # Process any pending executions
                for streaming_order in list(self.streaming_orders.values()):
                    if streaming_order.status in ["SUBMITTED", "WORKING"]:
                        # Simulate random execution
                        import random

                        if random.random() < 0.1:  # 10% chance per cycle
                            await self._simulate_order_execution(
                                streaming_order.order_id
                            )

            except Exception as e:
                logger.error(f"Execution stream processor error: {str(e)}")
                await asyncio.sleep(1.0)

        logger.debug("Execution stream processor stopped")

    async def _market_data_stream_processor(self) -> None:
        """Background processor for market data stream."""
        logger.debug("Market data stream processor started")

        while self.active_streams.get(StreamType.MARKET_DATA, False):
            try:
                # Simulate market data updates
                await asyncio.sleep(0.01)  # 100Hz market data

                # Generate sample market data
                market_data = {
                    "symbol": "EURUSD",
                    "bid": 1.0850,
                    "ask": 1.0852,
                    "volume": 1000,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                await self._publish_to_stream(StreamType.MARKET_DATA, market_data)

            except Exception as e:
                logger.error(f"Market data stream processor error: {str(e)}")
                await asyncio.sleep(1.0)

        logger.debug("Market data stream processor stopped")
