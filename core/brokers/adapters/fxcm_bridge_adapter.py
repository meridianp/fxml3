"""FXML4 FXCM Bridge Adapter.

This adapter bridges between FXML4's FIX-based order management system
and the existing ForexConnect RabbitMQ middleware, enabling seamless
integration with FXCM's ForexConnect API while maintaining Python
version compatibility.
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import aio_pika
import aiohttp
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractQueue
from pydantic import BaseModel, Field

from ...core.exceptions import BrokerError
from ...core.exceptions import ConnectionError as FXMLConnectionError
from ...core.exceptions import OrderRejectedError
from ...core.exceptions import TimeoutError as FXMLTimeoutError
from ...core.logging import get_logger
from ...fix.messages.base import OrdType, Side, TimeInForce
from ...fix.messages.orders import ExecutionReport as FIXExecutionReport
from ...fix.messages.orders import NewOrderSingle
from ..base import BrokerAdapter, ExecutionReport, OrderStatus

logger = get_logger(__name__)


class ForexConnectOrder(BaseModel):
    """Order model for ForexConnect bridge communication."""

    type: str = Field(default="order_request", description="Message type")
    request_id: str = Field(description="Unique request ID")
    correlation_id: str = Field(description="Correlation ID for tracking")
    order_type: str = Field(description="Order type (market, limit, stop)")
    instrument: str = Field(description="Trading instrument (EUR/USD format)")
    side: str = Field(description="Order side (buy/sell)")
    amount: int = Field(description="Order amount in units")
    rate: Optional[float] = Field(
        default=None, description="Order rate (for limit orders)"
    )
    time_in_force: str = Field(default="IOC", description="Time in force")
    account_id: Optional[str] = Field(default=None, description="Account ID")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ForexConnectResponse(BaseModel):
    """Response model from ForexConnect bridge."""

    type: str = Field(description="Response type")
    request_id: str = Field(description="Original request ID")
    correlation_id: str = Field(description="Correlation ID")
    status: str = Field(description="Response status")
    order_id: Optional[str] = Field(default=None, description="ForexConnect order ID")
    trade_id: Optional[str] = Field(default=None, description="ForexConnect trade ID")
    amount: Optional[int] = Field(default=None, description="Executed amount")
    rate: Optional[float] = Field(default=None, description="Execution rate")
    message: Optional[str] = Field(default=None, description="Status message")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = Field(default=None, description="Error message if any")


class MarketDataUpdate(BaseModel):
    """Market data update from ForexConnect bridge."""

    type: str = Field(default="price_update", description="Update type")
    instrument: str = Field(description="Trading instrument")
    bid: float = Field(description="Bid price")
    ask: float = Field(description="Ask price")
    timestamp: str = Field(description="Update timestamp")
    digits: Optional[int] = Field(default=None, description="Price digits")


class FXCMBridgeAdapter(BrokerAdapter):
    """FXML4 adapter for FXCM ForexConnect integration via RabbitMQ bridge."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize FXCM bridge adapter.

        Args:
            config: Adapter configuration including bridge URL and RabbitMQ settings
        """
        super().__init__("fxcm_bridge")
        self.config = config

        # Bridge service configuration
        self.bridge_url = config.get("bridge_url", "http://forex-middleware:8080")
        self.api_key = config.get("api_key")

        # RabbitMQ configuration
        rabbitmq_config = config.get("rabbitmq", {})
        self.rabbitmq_url = (
            f"amqp://{rabbitmq_config.get('username', 'fxml4')}:"
            f"{rabbitmq_config.get('password', 'fxml4_pass')}@"
            f"{rabbitmq_config.get('host', 'rabbitmq')}:"
            f"{rabbitmq_config.get('port', 5672)}/"
        )

        # Connection management
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._http_session: Optional[aiohttp.ClientSession] = None

        # Message queues
        self._order_request_queue: Optional[AbstractQueue] = None
        self._order_response_queue: Optional[AbstractQueue] = None
        self._market_data_queue: Optional[AbstractQueue] = None

        # Order tracking
        self._pending_orders: Dict[str, dict] = {}
        self._order_callbacks: Dict[str, Callable] = {}

        # Market data subscriptions
        self._market_data_callbacks: Dict[str, List[Callable]] = {}

        # Connection status
        self._connected = False
        self._bridge_healthy = False

        logger.info(
            f"Initialized FXCM bridge adapter with bridge URL: {self.bridge_url}"
        )

    @property
    def is_connected(self) -> bool:
        """Check if adapter is connected to both RabbitMQ and bridge service."""
        return self._connected and self._bridge_healthy

    async def connect(self) -> None:
        """Connect to RabbitMQ and bridge service."""
        try:
            logger.info("Connecting FXCM bridge adapter...")

            # Connect to RabbitMQ
            await self._connect_rabbitmq()

            # Connect to bridge service
            await self._connect_bridge()

            # Start message consumers
            await self._start_consumers()

            # Verify bridge health
            await self._check_bridge_health()

            self._connected = True
            logger.info("FXCM bridge adapter connected successfully")

        except Exception as e:
            logger.error(f"Failed to connect FXCM bridge adapter: {e}")
            await self.disconnect()
            raise FXMLConnectionError(f"FXCM bridge connection failed: {e}")

    async def disconnect(self) -> None:
        """Disconnect from RabbitMQ and bridge service."""
        logger.info("Disconnecting FXCM bridge adapter...")

        self._connected = False
        self._bridge_healthy = False

        try:
            # Close RabbitMQ connection
            if self._connection and not self._connection.is_closed:
                await self._connection.close()
                self._connection = None
                self._channel = None

            # Close HTTP session
            if self._http_session and not self._http_session.closed:
                await self._http_session.close()
                self._http_session = None

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

        logger.info("FXCM bridge adapter disconnected")

    async def _connect_rabbitmq(self) -> None:
        """Connect to RabbitMQ and set up channels/queues."""
        logger.debug("Connecting to RabbitMQ...")

        self._connection = await aio_pika.connect_robust(
            self.rabbitmq_url, loop=asyncio.get_event_loop()
        )

        self._channel = await self._connection.channel()

        # Set QoS for fair message distribution
        await self._channel.set_qos(prefetch_count=10)

        # Declare exchanges (should already exist from definitions.json)
        await self._channel.declare_exchange(
            "forex.orders", aio_pika.ExchangeType.TOPIC, durable=True
        )
        await self._channel.declare_exchange(
            "forex.market_data", aio_pika.ExchangeType.TOPIC, durable=True
        )

        # Declare queues
        self._order_request_queue = await self._channel.declare_queue(
            "forex.orders.request",
            durable=True,
            arguments={"x-message-ttl": 300000, "x-max-length": 10000},
        )

        self._order_response_queue = await self._channel.declare_queue(
            "forex.orders.response",
            durable=True,
            arguments={"x-message-ttl": 300000, "x-max-length": 10000},
        )

        self._market_data_queue = await self._channel.declare_queue(
            "forex.market_data.stream",
            durable=False,
            auto_delete=True,
            arguments={"x-message-ttl": 5000, "x-max-length": 1000},
        )

        logger.debug("RabbitMQ connection established")

    async def _connect_bridge(self) -> None:
        """Connect to ForexConnect bridge service."""
        logger.debug("Connecting to ForexConnect bridge service...")

        # Create HTTP session with timeout
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        self._http_session = aiohttp.ClientSession(timeout=timeout, headers=headers)

        logger.debug("Bridge service connection established")

    async def _start_consumers(self) -> None:
        """Start RabbitMQ message consumers."""
        logger.debug("Starting message consumers...")

        # Consumer for order responses from ForexConnect middleware
        await self._order_response_queue.consume(
            self._handle_order_response, no_ack=False
        )

        # Consumer for market data updates
        await self._market_data_queue.consume(self._handle_market_data, no_ack=False)

        logger.debug("Message consumers started")

    async def _check_bridge_health(self) -> None:
        """Check bridge service health."""
        try:
            async with self._http_session.get(f"{self.bridge_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    self._bridge_healthy = health_data.get("status") == "healthy"

                    if self._bridge_healthy:
                        logger.debug("Bridge service is healthy")
                    else:
                        logger.warning(f"Bridge service unhealthy: {health_data}")
                else:
                    logger.warning(
                        f"Bridge health check failed with status {response.status}"
                    )
                    self._bridge_healthy = False

        except Exception as e:
            logger.error(f"Bridge health check failed: {e}")
            self._bridge_healthy = False

    def _convert_fix_to_forex_order(
        self, fix_order: NewOrderSingle
    ) -> ForexConnectOrder:
        """Convert FIX order to ForexConnect format.

        Args:
            fix_order: FIX NewOrderSingle message

        Returns:
            ForexConnect order model
        """
        # Convert symbol format (EURUSD -> EUR/USD)
        instrument = fix_order.symbol
        if len(instrument) == 6 and instrument.isalpha():
            instrument = f"{instrument[:3]}/{instrument[3:]}"

        # Convert order type
        order_type_map = {
            OrdType.MARKET: "market",
            OrdType.LIMIT: "limit",
            OrdType.STOP: "stop",
            OrdType.STOP_LIMIT: "stop_limit",
        }

        # Convert side
        side = "buy" if fix_order.side == Side.BUY else "sell"

        # Convert time in force
        tif_map = {
            TimeInForce.IOC: "IOC",
            TimeInForce.FOK: "FOK",
            TimeInForce.DAY: "DAY",
            TimeInForce.GTC: "GTC",
        }

        return ForexConnectOrder(
            request_id=str(uuid.uuid4()),
            correlation_id=fix_order.cl_ord_id,
            order_type=order_type_map.get(fix_order.ord_type, "market"),
            instrument=instrument,
            side=side,
            amount=int(fix_order.order_qty),  # Convert to units
            rate=getattr(fix_order, "price", None),
            time_in_force=tif_map.get(
                getattr(fix_order, "time_in_force", TimeInForce.IOC), "IOC"
            ),
        )

    def _convert_forex_to_execution_report(
        self, forex_response: ForexConnectResponse, original_order: NewOrderSingle
    ) -> FIXExecutionReport:
        """Convert ForexConnect response to FIX execution report.

        Args:
            forex_response: ForexConnect response
            original_order: Original FIX order

        Returns:
            FIX execution report
        """
        # Map status
        status_map = {
            "waiting": OrderStatus.PENDING_NEW,
            "inprocess": OrderStatus.PENDING_NEW,
            "executing": OrderStatus.NEW,
            "executed": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELED,
            "rejected": OrderStatus.REJECTED,
            "expired": OrderStatus.EXPIRED,
        }

        ord_status = status_map.get(forex_response.status.lower(), OrderStatus.REJECTED)

        # Calculate executed quantities
        cum_qty = forex_response.amount or 0
        leaves_qty = max(0, original_order.order_qty - cum_qty)

        return FIXExecutionReport(
            order_id=forex_response.order_id or "",
            cl_ord_id=forex_response.correlation_id,
            exec_id=str(uuid.uuid4()),
            exec_type=ord_status,
            ord_status=ord_status,
            symbol=original_order.symbol,
            side=original_order.side,
            order_qty=original_order.order_qty,
            cum_qty=cum_qty,
            leaves_qty=leaves_qty,
            avg_px=forex_response.rate or 0.0,
            last_px=forex_response.rate or 0.0,
            last_qty=forex_response.amount or 0,
            text=forex_response.message or "",
        )

    async def submit_order(self, order: NewOrderSingle) -> str:
        """Submit order to ForexConnect bridge.

        Args:
            order: FIX order to submit

        Returns:
            Order ID from bridge service

        Raises:
            BrokerError: If order submission fails
        """
        if not self.is_connected:
            raise BrokerError("Adapter not connected")

        try:
            # Convert to ForexConnect format
            forex_order = self._convert_fix_to_forex_order(order)

            # Store pending order for correlation
            self._pending_orders[forex_order.correlation_id] = {
                "fix_order": order,
                "forex_order": forex_order,
                "submitted_at": datetime.utcnow(),
            }

            # Publish to RabbitMQ for bridge consumption
            message_body = json.dumps(forex_order.dict()).encode()
            message = aio_pika.Message(
                body=message_body,
                headers={
                    "correlation_id": forex_order.correlation_id,
                    "request_id": forex_order.request_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                correlation_id=forex_order.correlation_id,
            )

            # Publish to orders exchange
            exchange = await self._channel.get_exchange("forex.orders")
            await exchange.publish(message, routing_key="order.request")

            logger.info(
                f"Order submitted: {forex_order.correlation_id} -> {forex_order.instrument}"
            )

            return forex_order.correlation_id

        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            # Cleanup pending order
            self._pending_orders.pop(order.cl_ord_id, None)
            raise BrokerError(f"Order submission failed: {e}")

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order via bridge service.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancellation request sent successfully
        """
        try:
            if not self.is_connected:
                raise BrokerError("Adapter not connected")

            # Send cancellation request via HTTP to bridge
            cancel_data = {
                "type": "cancel_request",
                "order_id": order_id,
                "correlation_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
            }

            async with self._http_session.post(
                f"{self.bridge_url}/orders/{order_id}/cancel", json=cancel_data
            ) as response:

                if response.status == 200:
                    logger.info(f"Cancel request sent for order {order_id}")
                    return True
                else:
                    error_msg = await response.text()
                    logger.error(
                        f"Cancel request failed: {response.status} - {error_msg}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return False

    async def subscribe_market_data(
        self, symbols: List[str], callback: Callable[[str, Dict[str, Any]], None]
    ) -> None:
        """Subscribe to market data for symbols.

        Args:
            symbols: List of symbols to subscribe to
            callback: Callback function for price updates
        """
        try:
            if not self.is_connected:
                raise BrokerError("Adapter not connected")

            # Convert symbols to ForexConnect format
            forex_symbols = []
            for symbol in symbols:
                if len(symbol) == 6 and symbol.isalpha():
                    forex_symbols.append(f"{symbol[:3]}/{symbol[3:]}")
                else:
                    forex_symbols.append(symbol)

            # Store callback for each symbol
            for symbol in symbols:
                if symbol not in self._market_data_callbacks:
                    self._market_data_callbacks[symbol] = []
                self._market_data_callbacks[symbol].append(callback)

            # Send subscription request to bridge
            sub_data = {
                "type": "market_data_subscription",
                "symbols": forex_symbols,
                "correlation_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
            }

            async with self._http_session.post(
                f"{self.bridge_url}/market-data/subscribe", json=sub_data
            ) as response:

                if response.status == 200:
                    logger.info(f"Market data subscription successful for {symbols}")
                else:
                    error_msg = await response.text()
                    logger.error(f"Market data subscription failed: {error_msg}")

        except Exception as e:
            logger.error(f"Market data subscription failed: {e}")

    async def _handle_order_response(self, message: aio_pika.IncomingMessage) -> None:
        """Handle order response from ForexConnect bridge.

        Args:
            message: Incoming RabbitMQ message
        """
        try:
            async with message.process():
                # Parse response
                response_data = json.loads(message.body.decode())
                forex_response = ForexConnectResponse(**response_data)

                # Find original order
                correlation_id = forex_response.correlation_id
                pending_order = self._pending_orders.get(correlation_id)

                if not pending_order:
                    logger.warning(
                        f"Received response for unknown order: {correlation_id}"
                    )
                    return

                # Convert to execution report
                fix_order = pending_order["fix_order"]
                execution_report = self._convert_forex_to_execution_report(
                    forex_response, fix_order
                )

                # Call registered callback if any
                callback = self._order_callbacks.get(correlation_id)
                if callback:
                    await callback(execution_report)

                # Clean up completed/rejected orders
                if forex_response.status.lower() in [
                    "executed",
                    "rejected",
                    "canceled",
                    "expired",
                ]:
                    self._pending_orders.pop(correlation_id, None)
                    self._order_callbacks.pop(correlation_id, None)

                logger.debug(
                    f"Processed order response: {correlation_id} -> {forex_response.status}"
                )

        except Exception as e:
            logger.error(f"Error handling order response: {e}")

    async def _handle_market_data(self, message: aio_pika.IncomingMessage) -> None:
        """Handle market data update from ForexConnect bridge.

        Args:
            message: Incoming RabbitMQ message
        """
        try:
            async with message.process():
                # Parse market data
                data = json.loads(message.body.decode())
                market_update = MarketDataUpdate(**data)

                # Convert symbol format back to FIX (EUR/USD -> EURUSD)
                symbol = market_update.instrument.replace("/", "")

                # Call registered callbacks
                callbacks = self._market_data_callbacks.get(symbol, [])
                for callback in callbacks:
                    try:
                        await callback(
                            symbol,
                            {
                                "bid": market_update.bid,
                                "ask": market_update.ask,
                                "timestamp": market_update.timestamp,
                                "digits": market_update.digits,
                            },
                        )
                    except Exception as e:
                        logger.error(f"Error in market data callback: {e}")

        except Exception as e:
            logger.error(f"Error handling market data: {e}")

    def register_order_callback(self, order_id: str, callback: Callable) -> None:
        """Register callback for order status updates.

        Args:
            order_id: Order ID to watch
            callback: Callback function
        """
        self._order_callbacks[order_id] = callback

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information from bridge service.

        Returns:
            Account information dictionary
        """
        try:
            if not self.is_connected:
                raise BrokerError("Adapter not connected")

            async with self._http_session.get(f"{self.bridge_url}/account") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_msg = await response.text()
                    raise BrokerError(f"Failed to get account info: {error_msg}")

        except Exception as e:
            logger.error(f"Get account info failed: {e}")
            raise BrokerError(f"Get account info failed: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Check adapter health status.

        Returns:
            Health status dictionary
        """
        health = {
            "adapter": "fxcm_bridge",
            "connected": self._connected,
            "bridge_healthy": self._bridge_healthy,
            "pending_orders": len(self._pending_orders),
            "subscriptions": len(self._market_data_callbacks),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Check bridge service health
        try:
            if self._http_session:
                async with self._http_session.get(
                    f"{self.bridge_url}/health"
                ) as response:
                    if response.status == 200:
                        bridge_health = await response.json()
                        health["bridge_status"] = bridge_health
                    else:
                        health["bridge_status"] = {
                            "status": "unhealthy",
                            "code": response.status,
                        }
        except Exception as e:
            health["bridge_status"] = {"status": "error", "error": str(e)}

        return health

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Factory function for easy instantiation
def create_fxcm_bridge_adapter(config: Dict[str, Any]) -> FXCMBridgeAdapter:
    """Create FXCM bridge adapter with configuration.

    Args:
        config: Adapter configuration

    Returns:
        Configured adapter instance
    """
    return FXCMBridgeAdapter(config)


if __name__ == "__main__":
    """Main entry point for standalone adapter service."""
    import os
    import signal

    async def run_adapter():
        """Run adapter as standalone service."""
        config = {
            "bridge_url": os.getenv("FOREX_BRIDGE_URL", "http://forex-middleware:8080"),
            "api_key": os.getenv("FOREX_BRIDGE_API_KEY"),
            "rabbitmq": {
                "host": os.getenv("FXML4_RABBITMQ_HOST", "rabbitmq"),
                "port": int(os.getenv("FXML4_RABBITMQ_PORT", "5672")),
                "username": os.getenv("FXML4_RABBITMQ_USERNAME", "fxml4"),
                "password": os.getenv("FXML4_RABBITMQ_PASSWORD", "fxml4_pass"),
            },
        }

        adapter = create_fxcm_bridge_adapter(config)

        # Handle graceful shutdown
        shutdown_event = asyncio.Event()

        def signal_handler():
            logger.info("Received shutdown signal")
            shutdown_event.set()

        # Register signal handlers
        for sig in [signal.SIGINT, signal.SIGTERM]:
            asyncio.get_event_loop().add_signal_handler(sig, signal_handler)

        try:
            async with adapter:
                logger.info("FXCM bridge adapter service started")
                await shutdown_event.wait()

        except Exception as e:
            logger.error(f"Adapter service error: {e}")
            raise

        logger.info("FXCM bridge adapter service stopped")

    # Run adapter service
    asyncio.run(run_adapter())
