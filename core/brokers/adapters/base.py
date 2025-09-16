"""Base Broker Adapter Interface.

This module defines the abstract interface that all broker adapters
must implement to participate in the FIX-based broker abstraction system.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from ...fix.messages.admin import Heartbeat, Logon, Logout, TestRequest
from ...fix.messages.base import FIXMessage
from ...fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Broker connection status."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class OrderStatus(Enum):
    """Order lifecycle status."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    WORKING = "working"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class AdapterConfig:
    """Configuration for broker adapter."""

    adapter_type: str
    connection_params: Dict[str, Any]
    authentication: Dict[str, Any]
    timeouts: Dict[str, int] = field(
        default_factory=lambda: {
            "connect": 30,
            "authenticate": 60,
            "order": 300,
            "heartbeat": 30,
        }
    )
    retry_policy: Dict[str, Any] = field(
        default_factory=lambda: {
            "max_retries": 3,
            "base_delay": 1.0,
            "max_delay": 60.0,
            "exponential_base": 2.0,
        }
    )
    limits: Dict[str, Any] = field(
        default_factory=lambda: {
            "max_orders_per_second": 10,
            "max_daily_volume": 100000000.0,
            "max_position_size": 10000000.0,
        }
    )
    features: Dict[str, bool] = field(
        default_factory=lambda: {
            "supports_market_data": True,
            "supports_order_modification": True,
            "supports_bulk_operations": False,
            "supports_portfolio_queries": True,
        }
    )
    enabled: bool = True


@dataclass
class AdapterMetrics:
    """Adapter performance metrics."""

    total_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0
    failed_orders: int = 0
    total_modifications: int = 0
    failed_modifications: int = 0
    last_connect_time: Optional[datetime] = None
    last_disconnect_time: Optional[datetime] = None
    bytes_sent: int = 0
    bytes_received: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    uptime_seconds: float = 0.0


@dataclass
class BrokerConnection:
    """Broker connection information."""

    adapter_type: str
    status: ConnectionStatus
    connected_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    session_id: Optional[str] = None
    error_message: Optional[str] = None
    connection_count: int = 0
    uptime_seconds: float = 0.0

    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self.status in [
            ConnectionStatus.CONNECTED,
            ConnectionStatus.AUTHENTICATED,
        ]

    def is_ready(self) -> bool:
        """Check if connection is ready for trading."""
        return self.status == ConnectionStatus.AUTHENTICATED


@dataclass
class OrderInfo:
    """Order tracking information."""

    cl_ord_id: str
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    original_order: Optional[FIXMessage] = None
    last_execution: Optional[ExecutionReport] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    fills: List[ExecutionReport] = field(default_factory=list)
    total_filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    remaining_qty: float = 0.0
    error_message: Optional[str] = None


class BrokerAdapter(ABC):
    """Abstract base class for all broker adapters.

    This class defines the standard interface that all broker adapters
    must implement to integrate with the FXML4 broker abstraction system.

    Key responsibilities:
    - Connection management and authentication
    - Order lifecycle management (submit, cancel, modify)
    - Execution report processing and forwarding
    - Market data subscription and distribution
    - Error handling and recovery
    - Session management and heartbeats
    """

    def __init__(self, config: AdapterConfig):
        """Initialize broker adapter.

        Args:
            config: Adapter configuration.
        """
        self.config = config
        self.adapter_type = config.adapter_type
        self.connection = BrokerConnection(
            adapter_type=self.adapter_type, status=ConnectionStatus.DISCONNECTED
        )

        # Order tracking
        self.active_orders: Dict[str, OrderInfo] = {}
        self.order_history: List[OrderInfo] = []

        # Event callbacks
        self.execution_callback: Optional[Callable[[ExecutionReport], None]] = None
        self.status_callback: Optional[Callable[[BrokerConnection], None]] = None
        self.error_callback: Optional[Callable[[Exception], None]] = None

        # Session management
        self.session_active = False
        self.last_heartbeat_sent = datetime.utcnow()
        self.heartbeat_interval = 30  # seconds

        # Rate limiting
        self.order_rate_limiter: Dict[str, List[datetime]] = {"orders": []}

        logger.info("Initialized %s adapter", self.adapter_type)

    # Connection Management

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to broker.

        Returns:
            True if connection successful.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from broker."""
        pass

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with broker.

        Returns:
            True if authentication successful.
        """
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to broker.

        Returns:
            True if connected and authenticated.
        """
        pass

    # Order Management

    @abstractmethod
    async def submit_order(self, order: NewOrderSingle) -> str:
        """Submit new order to broker.

        Args:
            order: Order to submit.

        Returns:
            Client order ID for tracking.
        """
        pass

    @abstractmethod
    async def cancel_order(self, cancel_request: OrderCancelRequest) -> bool:
        """Cancel existing order.

        Args:
            cancel_request: Order cancellation request.

        Returns:
            True if cancellation request accepted.
        """
        pass

    async def modify_order(self, modify_request: FIXMessage) -> bool:
        """Modify existing order (optional).

        Args:
            modify_request: Order modification request.

        Returns:
            True if modification request accepted.
        """
        # Default implementation - not all brokers support modification
        logger.warning(
            "%s adapter does not support order modification", self.adapter_type
        )
        return False

    @abstractmethod
    async def get_order_status(self, cl_ord_id: str) -> Optional[OrderInfo]:
        """Get status of specific order.

        Args:
            cl_ord_id: Client order ID.

        Returns:
            Order information or None if not found.
        """
        pass

    @abstractmethod
    async def get_open_orders(self) -> List[OrderInfo]:
        """Get all open orders.

        Returns:
            List of open order information.
        """
        pass

    # Market Data (Optional)

    async def subscribe_market_data(self, symbols: List[str]) -> bool:
        """Subscribe to market data for symbols.

        Args:
            symbols: List of symbols to subscribe to.

        Returns:
            True if subscription successful.
        """
        logger.warning("%s adapter does not support market data", self.adapter_type)
        return False

    async def unsubscribe_market_data(self, symbols: List[str]) -> bool:
        """Unsubscribe from market data.

        Args:
            symbols: List of symbols to unsubscribe from.

        Returns:
            True if unsubscription successful.
        """
        logger.warning("%s adapter does not support market data", self.adapter_type)
        return False

    # Session Management

    @abstractmethod
    async def send_heartbeat(self) -> bool:
        """Send heartbeat to maintain session.

        Returns:
            True if heartbeat sent successfully.
        """
        pass

    async def handle_test_request(self, test_request: TestRequest) -> bool:
        """Handle incoming test request.

        Args:
            test_request: Test request message.

        Returns:
            True if handled successfully.
        """
        # Default implementation - send heartbeat response
        return await self.send_heartbeat()

    # Administrative Functions

    @abstractmethod
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information.

        Returns:
            Account information dictionary.
        """
        pass

    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions.

        Returns:
            List of position dictionaries.
        """
        pass

    async def get_adapter_info(self) -> Dict[str, Any]:
        """Get adapter information and statistics.

        Returns:
            Adapter information dictionary.
        """
        return {
            "adapter_type": self.adapter_type,
            "connection_status": self.connection.status.value,
            "connected_at": (
                self.connection.connected_at.isoformat()
                if self.connection.connected_at
                else None
            ),
            "session_active": self.session_active,
            "active_orders": len(self.active_orders),
            "total_orders": len(self.order_history),
            "config": {
                "enabled": self.config.enabled,
                "features": self.config.features,
            },
        }

    # Event Handling

    def set_execution_callback(
        self, callback: Callable[[ExecutionReport], None]
    ) -> None:
        """Set callback for execution reports.

        Args:
            callback: Function to call with execution reports.
        """
        self.execution_callback = callback

    def set_status_callback(self, callback: Callable[[BrokerConnection], None]) -> None:
        """Set callback for connection status changes.

        Args:
            callback: Function to call with connection updates.
        """
        self.status_callback = callback

    def set_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """Set callback for errors.

        Args:
            callback: Function to call with errors.
        """
        self.error_callback = callback

    # Protected Helper Methods

    def _update_connection_status(
        self, status: ConnectionStatus, error: Optional[str] = None
    ) -> None:
        """Update connection status and notify callbacks.

        Args:
            status: New connection status.
            error: Optional error message.
        """
        old_status = self.connection.status
        self.connection.status = status
        self.connection.error_message = error

        if status == ConnectionStatus.CONNECTED:
            self.connection.connected_at = datetime.utcnow()
            self.connection.connection_count += 1
        elif status == ConnectionStatus.DISCONNECTED:
            self.connection.connected_at = None
            self.session_active = False

        # Notify callback if status changed
        if old_status != status and self.status_callback:
            try:
                self.status_callback(self.connection)
            except Exception as e:
                logger.error("Error in status callback: %s", e)

        logger.info(
            "%s adapter status: %s -> %s",
            self.adapter_type,
            old_status.value,
            status.value,
        )

    def _process_execution_report(self, execution: ExecutionReport) -> None:
        """Process incoming execution report.

        Args:
            execution: Execution report to process.
        """
        cl_ord_id = execution.cl_ord_id

        # Update order tracking
        if cl_ord_id in self.active_orders:
            order_info = self.active_orders[cl_ord_id]
            order_info.last_execution = execution
            order_info.updated_at = datetime.utcnow()

            # Update order status based on execution type
            exec_type = execution.exec_type
            if hasattr(exec_type, "value"):
                exec_type_val = exec_type.value
            else:
                exec_type_val = str(exec_type)

            if exec_type_val in ["F", "G"]:  # Trade or Trade Correct
                order_info.fills.append(execution)
                if execution.last_qty:
                    order_info.total_filled_qty += execution.last_qty
                if execution.avg_px:
                    order_info.avg_fill_price = execution.avg_px
                if execution.leaves_qty is not None:
                    order_info.remaining_qty = execution.leaves_qty

                # Update status based on remaining quantity
                if order_info.remaining_qty == 0:
                    order_info.status = OrderStatus.FILLED
                else:
                    order_info.status = OrderStatus.PARTIALLY_FILLED

            elif exec_type_val == "8":  # Rejected
                order_info.status = OrderStatus.REJECTED
                order_info.error_message = execution.text

            elif exec_type_val == "4":  # Cancelled
                order_info.status = OrderStatus.CANCELLED

        # Notify callback
        if self.execution_callback:
            try:
                self.execution_callback(execution)
            except Exception as e:
                logger.error("Error in execution callback: %s", e)

        logger.debug(
            "Processed execution: order=%s, type=%s, qty=%s, price=%s",
            cl_ord_id,
            execution.exec_type,
            execution.last_qty,
            execution.last_px,
        )

    def _track_order(self, order: NewOrderSingle) -> OrderInfo:
        """Add order to tracking.

        Args:
            order: Order to track.

        Returns:
            Order tracking information.
        """
        order_info = OrderInfo(
            cl_ord_id=order.cl_ord_id,
            original_order=order,
            status=OrderStatus.SUBMITTED,
            remaining_qty=order.order_qty or 0.0,
        )

        self.active_orders[order.cl_ord_id] = order_info
        self.order_history.append(order_info)

        logger.debug("Tracking order: %s", order.cl_ord_id)
        return order_info

    def _check_rate_limits(self, operation: str = "orders") -> bool:
        """Check if operation is within rate limits.

        Args:
            operation: Operation type to check.

        Returns:
            True if within limits.
        """
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=1)

        # Clean old entries
        if operation in self.order_rate_limiter:
            self.order_rate_limiter[operation] = [
                ts for ts in self.order_rate_limiter[operation] if ts > window_start
            ]
        else:
            self.order_rate_limiter[operation] = []

        # Check limit
        limit_key = f"max_{operation}_per_second"
        max_ops = self.config.limits.get(limit_key, 10)

        if len(self.order_rate_limiter[operation]) >= max_ops:
            logger.warning(
                "Rate limit exceeded for %s: %d/%d",
                operation,
                len(self.order_rate_limiter[operation]),
                max_ops,
            )
            return False

        # Record this operation
        self.order_rate_limiter[operation].append(now)
        return True

    def _handle_error(self, error: Exception) -> None:
        """Handle and report errors.

        Args:
            error: Exception that occurred.
        """
        logger.error("%s adapter error: %s", self.adapter_type, error)

        # Update connection status if connection-related
        if isinstance(error, (ConnectionError, TimeoutError)):
            self._update_connection_status(ConnectionStatus.ERROR, str(error))

        # Notify callback
        if self.error_callback:
            try:
                self.error_callback(error)
            except Exception as e:
                logger.error("Error in error callback: %s", e)

    # Context Manager Support

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
