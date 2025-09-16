"""Base broker adapter interface for all broker implementations."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from ..schemas.broker_messages import (
    AccountReport,
    BrokerCapabilities,
    BrokerError,
    BrokerMessage,
    BrokerStatus,
    BrokerType,
    ExecutionReport,
    MarketDataRequest,
    MarketDataSnapshot,
    OrderCancelRequest,
    OrderModifyRequest,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    PositionReport,
)


class BrokerConnectionError(Exception):
    """Broker connection related errors."""

    pass


class BrokerOrderError(Exception):
    """Broker order related errors."""

    pass


class BrokerAuthenticationError(Exception):
    """Broker authentication errors."""

    pass


class BaseBrokerAdapter(ABC):
    """Base class for all broker adapters.

    This abstract class defines the interface that all broker adapters must implement.
    It provides a standardized way to interact with different brokers while handling
    their specific API requirements internally.
    """

    def __init__(self, broker_type: BrokerType, config: Dict[str, Any]):
        """Initialize broker adapter.

        Args:
            broker_type: Type of broker (IB, FXCM, Oanda, etc.)
            config: Broker-specific configuration
        """
        self.broker_type = broker_type
        self.config = config
        self.logger = logging.getLogger(f"BrokerAdapter-{broker_type.value}")

        # Connection state
        self.connected = False
        self.authenticated = False
        self.connection_quality = "UNKNOWN"

        # Event callbacks
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.error_handlers: List[Callable] = []

        # Order tracking
        self.active_orders: Dict[str, OrderRequest] = {}
        self.order_status: Dict[str, OrderStatus] = {}

        # Account information
        self.account_id: Optional[str] = None
        self.account_info: Optional[AccountReport] = None
        self.positions: Dict[str, PositionReport] = {}

        # Rate limiting
        self.last_request_time = {}
        self.request_counts = {}

        # Capabilities
        self._capabilities: Optional[BrokerCapabilities] = None

    # Abstract methods that must be implemented by each broker

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the broker.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the broker.

        Returns:
            True if disconnection successful, False otherwise
        """
        pass

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with the broker.

        Args:
            credentials: Authentication credentials (API key, secret, etc.)

        Returns:
            True if authentication successful, False otherwise
        """
        pass

    @abstractmethod
    async def submit_order(self, order: OrderRequest) -> OrderResponse:
        """Submit an order to the broker.

        Args:
            order: Order request to submit

        Returns:
            Order response from broker

        Raises:
            BrokerOrderError: If order submission fails
        """
        pass

    @abstractmethod
    async def cancel_order(self, cancel_request: OrderCancelRequest) -> OrderResponse:
        """Cancel an existing order.

        Args:
            cancel_request: Order cancellation request

        Returns:
            Order response confirming cancellation

        Raises:
            BrokerOrderError: If cancellation fails
        """
        pass

    @abstractmethod
    async def modify_order(self, modify_request: OrderModifyRequest) -> OrderResponse:
        """Modify an existing order.

        Args:
            modify_request: Order modification request

        Returns:
            Order response confirming modification

        Raises:
            BrokerOrderError: If modification fails
        """
        pass

    @abstractmethod
    async def get_account_info(self) -> AccountReport:
        """Get current account information.

        Returns:
            Account report with balances and margins
        """
        pass

    @abstractmethod
    async def get_positions(self) -> List[PositionReport]:
        """Get current positions.

        Returns:
            List of position reports
        """
        pass

    @abstractmethod
    async def get_open_orders(self) -> List[OrderResponse]:
        """Get all open orders.

        Returns:
            List of open orders
        """
        pass

    @abstractmethod
    async def subscribe_market_data(self, request: MarketDataRequest) -> bool:
        """Subscribe to market data.

        Args:
            request: Market data subscription request

        Returns:
            True if subscription successful, False otherwise
        """
        pass

    @abstractmethod
    async def unsubscribe_market_data(self, request_id: str) -> bool:
        """Unsubscribe from market data.

        Args:
            request_id: Market data request ID to unsubscribe

        Returns:
            True if unsubscription successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_market_data_snapshot(
        self, symbol: str
    ) -> Optional[MarketDataSnapshot]:
        """Get current market data snapshot.

        Args:
            symbol: Symbol to get data for

        Returns:
            Market data snapshot or None if not available
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> BrokerCapabilities:
        """Get broker capabilities and limitations.

        Returns:
            Broker capabilities object
        """
        pass

    # Common implementation methods

    async def initialize(self) -> bool:
        """Initialize the broker adapter.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info(f"Initializing {self.broker_type.value} adapter")

            # Load capabilities
            self._capabilities = self.get_capabilities()

            # Perform broker-specific initialization
            await self._broker_specific_initialization()

            self.logger.info(f"{self.broker_type.value} adapter initialized")
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to initialize {self.broker_type.value} adapter: {e}"
            )
            return False

    async def _broker_specific_initialization(self):
        """Override in subclasses for broker-specific initialization."""
        pass

    def add_message_handler(self, message_type: str, handler: Callable):
        """Add a message handler for specific message types.

        Args:
            message_type: Type of message to handle
            handler: Async function to handle the message
        """
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)

    def add_error_handler(self, handler: Callable):
        """Add an error handler.

        Args:
            handler: Async function to handle errors
        """
        self.error_handlers.append(handler)

    async def _emit_message(self, message: BrokerMessage):
        """Emit a message to registered handlers.

        Args:
            message: Message to emit
        """
        message_type = message.message_type

        if message_type in self.message_handlers:
            for handler in self.message_handlers[message_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    self.logger.error(f"Error in message handler: {e}")

    async def _emit_error(self, error: BrokerError):
        """Emit an error to registered handlers.

        Args:
            error: Error to emit
        """
        for handler in self.error_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(error)
                else:
                    handler(error)
            except Exception as e:
                self.logger.error(f"Error in error handler: {e}")

    def _validate_order(self, order: OrderRequest) -> bool:
        """Validate order against broker capabilities.

        Args:
            order: Order to validate

        Returns:
            True if order is valid, False otherwise
        """
        if not self._capabilities:
            return True  # Can't validate without capabilities

        # Check order type support
        if order.order_type not in self._capabilities.supported_order_types:
            self.logger.warning(f"Order type {order.order_type} not supported")
            return False

        # Check time in force support
        if order.time_in_force not in self._capabilities.supported_time_in_force:
            self.logger.warning(f"Time in force {order.time_in_force} not supported")
            return False

        # Check order size limits
        symbol = order.symbol
        if symbol in self._capabilities.min_order_size:
            if order.quantity < self._capabilities.min_order_size[symbol]:
                self.logger.warning(f"Order quantity below minimum for {symbol}")
                return False

        if symbol in self._capabilities.max_order_size:
            if order.quantity > self._capabilities.max_order_size[symbol]:
                self.logger.warning(f"Order quantity above maximum for {symbol}")
                return False

        return True

    async def _check_rate_limits(self, operation: str) -> bool:
        """Check if operation is within rate limits.

        Args:
            operation: Operation type (e.g., 'order', 'cancel', 'modify')

        Returns:
            True if within limits, False otherwise
        """
        if not self._capabilities:
            return True

        current_time = datetime.utcnow()

        # Check per-second limits
        if self._capabilities.max_orders_per_second:
            second_key = f"{operation}_{current_time.strftime('%Y%m%d_%H%M%S')}"
            count = self.request_counts.get(second_key, 0)

            if count >= self._capabilities.max_orders_per_second:
                return False

            self.request_counts[second_key] = count + 1

            # Clean old entries
            old_keys = [
                k
                for k in self.request_counts.keys()
                if not k.startswith(
                    f"{operation}_{current_time.strftime('%Y%m%d_%H%M')}"
                )
            ]
            for key in old_keys:
                del self.request_counts[key]

        # Check per-minute limits
        if self._capabilities.max_orders_per_minute:
            minute_key = f"{operation}_{current_time.strftime('%Y%m%d_%H%M')}"
            count = self.request_counts.get(minute_key, 0)

            if count >= self._capabilities.max_orders_per_minute:
                return False

            self.request_counts[minute_key] = count + 1

        return True

    def _update_order_status(self, client_order_id: str, status: OrderStatus):
        """Update internal order status tracking.

        Args:
            client_order_id: Client order ID
            status: New order status
        """
        self.order_status[client_order_id] = status

        # Remove from active orders if filled or cancelled
        if status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            self.active_orders.pop(client_order_id, None)

    def _update_position(self, position: PositionReport):
        """Update internal position tracking.

        Args:
            position: Position report to update
        """
        self.positions[position.symbol] = position

    def _update_account_info(self, account_info: AccountReport):
        """Update internal account information.

        Args:
            account_info: Account report to update
        """
        self.account_info = account_info

    async def get_order_status(self, client_order_id: str) -> Optional[OrderStatus]:
        """Get current status of an order.

        Args:
            client_order_id: Client order ID

        Returns:
            Current order status or None if not found
        """
        return self.order_status.get(client_order_id)

    async def get_position(self, symbol: str) -> Optional[PositionReport]:
        """Get current position for a symbol.

        Args:
            symbol: Symbol to get position for

        Returns:
            Position report or None if no position
        """
        return self.positions.get(symbol)

    def is_connected(self) -> bool:
        """Check if broker is connected.

        Returns:
            True if connected, False otherwise
        """
        return self.connected and self.authenticated

    def get_connection_status(self) -> BrokerStatus:
        """Get current connection status.

        Returns:
            Broker status message
        """
        status = "CONNECTED" if self.connected else "DISCONNECTED"

        return BrokerStatus(
            broker_type=self.broker_type,
            account_id=self.account_id or "unknown",
            status=status,
            connection_quality=self.connection_quality,
            server_time=datetime.utcnow(),
            market_open=True,  # Override in subclasses
            supported_order_types=(
                self._capabilities.supported_order_types if self._capabilities else []
            ),
            supported_time_in_force=(
                self._capabilities.supported_time_in_force if self._capabilities else []
            ),
        )

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check.

        Returns:
            Health check results
        """
        health = {
            "broker_type": self.broker_type.value,
            "connected": self.connected,
            "authenticated": self.authenticated,
            "connection_quality": self.connection_quality,
            "active_orders": len(self.active_orders),
            "open_positions": len(self.positions),
            "last_account_update": (
                self.account_info.report_time if self.account_info else None
            ),
        }

        # Add broker-specific health checks
        broker_health = await self._broker_health_check()
        health.update(broker_health)

        return health

    async def _broker_health_check(self) -> Dict[str, Any]:
        """Override in subclasses for broker-specific health checks.

        Returns:
            Broker-specific health information
        """
        return {}

    async def cleanup(self):
        """Clean up resources before shutdown."""
        try:
            # Cancel any pending orders if needed
            # Close connections
            # Clean up subscriptions
            await self.disconnect()

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


class BrokerAdapterFactory:
    """Factory for creating broker adapters."""

    _adapters: Dict[BrokerType, type] = {}

    @classmethod
    def register_adapter(cls, broker_type: BrokerType, adapter_class: type):
        """Register a broker adapter class.

        Args:
            broker_type: Type of broker
            adapter_class: Adapter class to register
        """
        cls._adapters[broker_type] = adapter_class

    @classmethod
    def create_adapter(
        cls, broker_type: BrokerType, config: Dict[str, Any]
    ) -> BaseBrokerAdapter:
        """Create a broker adapter instance.

        Args:
            broker_type: Type of broker to create
            config: Broker configuration

        Returns:
            Broker adapter instance

        Raises:
            ValueError: If broker type is not registered
        """
        if broker_type not in cls._adapters:
            raise ValueError(f"No adapter registered for broker type: {broker_type}")

        adapter_class = cls._adapters[broker_type]
        return adapter_class(broker_type, config)

    @classmethod
    def get_supported_brokers(cls) -> List[BrokerType]:
        """Get list of supported broker types.

        Returns:
            List of supported broker types
        """
        return list(cls._adapters.keys())
