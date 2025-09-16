"""Adapter Mixins for Shared Functionality.

This module provides mixins that can be composed into broker adapters
to provide common functionality like order tracking, status management,
and metrics collection.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from ...fix.messages.base import ExecType, OrdStatus, Side
from ...fix.messages.orders import ExecutionReport, NewOrderSingle
from .base import ConnectionStatus, OrderStatus

logger = logging.getLogger(__name__)


@dataclass
class OrderInfo:
    """Information about an order being tracked."""

    cl_ord_id: str
    broker_order_id: Optional[str]
    symbol: str
    side: Side
    quantity: float
    order_type: str
    price: Optional[float]

    status: OrderStatus
    submitted_at: datetime
    last_update: datetime

    fills: List[Dict[str, Any]] = field(default_factory=list)
    total_filled: float = 0.0
    avg_fill_price: float = 0.0
    remaining_qty: float = 0.0

    def __post_init__(self):
        """Initialize calculated fields."""
        self.remaining_qty = self.quantity

    def add_fill(
        self, fill_qty: float, fill_price: float, fill_time: Optional[datetime] = None
    ):
        """Add a fill to this order."""
        fill_time = fill_time or datetime.now(timezone.utc)

        self.fills.append(
            {
                "quantity": fill_qty,
                "price": fill_price,
                "time": fill_time,
                "value": fill_qty * fill_price,
            }
        )

        # Update totals
        total_value = sum(f["value"] for f in self.fills)
        self.total_filled = sum(f["quantity"] for f in self.fills)
        self.avg_fill_price = (
            total_value / self.total_filled if self.total_filled > 0 else 0.0
        )
        self.remaining_qty = self.quantity - self.total_filled
        self.last_update = fill_time

        # Update status
        if self.remaining_qty <= 0:
            self.status = OrderStatus.FILLED
        elif self.total_filled > 0:
            self.status = OrderStatus.PARTIALLY_FILLED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cl_ord_id": self.cl_ord_id,
            "broker_order_id": self.broker_order_id,
            "symbol": self.symbol,
            "side": self.side.value if hasattr(self.side, "value") else str(self.side),
            "quantity": self.quantity,
            "order_type": self.order_type,
            "price": self.price,
            "status": self.status.value,
            "submitted_at": self.submitted_at.isoformat(),
            "last_update": self.last_update.isoformat(),
            "fills": self.fills,
            "total_filled": self.total_filled,
            "avg_fill_price": self.avg_fill_price,
            "remaining_qty": self.remaining_qty,
        }


class OrderTrackingMixin:
    """Mixin for order tracking functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Order tracking
        self.active_orders: Dict[str, OrderInfo] = {}
        self.order_map: Dict[str, str] = {}  # broker_order_id -> cl_ord_id
        self.completed_orders: deque = deque(maxlen=1000)  # Recent completed orders

        # Order statistics
        self.orders_submitted = 0
        self.orders_filled = 0
        self.orders_cancelled = 0
        self.orders_rejected = 0

        logger.debug(
            f"Initialized order tracking for {getattr(self, 'adapter_id', 'unknown')}"
        )

    def track_order(
        self, order: NewOrderSingle, broker_order_id: Optional[str] = None
    ) -> OrderInfo:
        """Start tracking an order.

        Args:
            order: Order to track.
            broker_order_id: Broker's identifier for the order.

        Returns:
            OrderInfo object for the tracked order.
        """
        order_info = OrderInfo(
            cl_ord_id=order.cl_ord_id,
            broker_order_id=broker_order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.order_qty,
            order_type=str(order.ord_type),
            price=getattr(order, "price", None),
            status=OrderStatus.SUBMITTED,
            submitted_at=datetime.now(timezone.utc),
            last_update=datetime.now(timezone.utc),
        )

        self.active_orders[order.cl_ord_id] = order_info

        if broker_order_id:
            self.order_map[broker_order_id] = order.cl_ord_id

        self.orders_submitted += 1

        logger.debug(f"Started tracking order {order.cl_ord_id}")
        return order_info

    def update_order_status(
        self, cl_ord_id: str, status: OrderStatus, broker_order_id: Optional[str] = None
    ):
        """Update order status.

        Args:
            cl_ord_id: Client order ID.
            status: New order status.
            broker_order_id: Broker order ID (if available).
        """
        if cl_ord_id in self.active_orders:
            order_info = self.active_orders[cl_ord_id]
            order_info.status = status
            order_info.last_update = datetime.now(timezone.utc)

            if broker_order_id and not order_info.broker_order_id:
                order_info.broker_order_id = broker_order_id
                self.order_map[broker_order_id] = cl_ord_id

            # Move to completed if final status
            if status in [
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED,
            ]:
                self.completed_orders.append(order_info.to_dict())
                del self.active_orders[cl_ord_id]

                if (
                    order_info.broker_order_id
                    and order_info.broker_order_id in self.order_map
                ):
                    del self.order_map[order_info.broker_order_id]

                # Update statistics
                if status == OrderStatus.FILLED:
                    self.orders_filled += 1
                elif status == OrderStatus.CANCELLED:
                    self.orders_cancelled += 1
                elif status == OrderStatus.REJECTED:
                    self.orders_rejected += 1

            logger.debug(f"Updated order {cl_ord_id} status to {status.value}")

    def add_order_fill(self, cl_ord_id: str, fill_qty: float, fill_price: float):
        """Add a fill to an order.

        Args:
            cl_ord_id: Client order ID.
            fill_qty: Quantity filled.
            fill_price: Fill price.
        """
        if cl_ord_id in self.active_orders:
            order_info = self.active_orders[cl_ord_id]
            order_info.add_fill(fill_qty, fill_price)

            logger.debug(f"Added fill to order {cl_ord_id}: {fill_qty} @ {fill_price}")

    def get_order_info(self, cl_ord_id: str) -> Optional[OrderInfo]:
        """Get order information.

        Args:
            cl_ord_id: Client order ID.

        Returns:
            OrderInfo if found, None otherwise.
        """
        return self.active_orders.get(cl_ord_id)

    def get_order_by_broker_id(self, broker_order_id: str) -> Optional[OrderInfo]:
        """Get order by broker order ID.

        Args:
            broker_order_id: Broker's order identifier.

        Returns:
            OrderInfo if found, None otherwise.
        """
        cl_ord_id = self.order_map.get(broker_order_id)
        return self.active_orders.get(cl_ord_id) if cl_ord_id else None

    def get_order_statistics(self) -> Dict[str, Any]:
        """Get order tracking statistics.

        Returns:
            Dictionary containing order statistics.
        """
        return {
            "active_orders": len(self.active_orders),
            "orders_submitted": self.orders_submitted,
            "orders_filled": self.orders_filled,
            "orders_cancelled": self.orders_cancelled,
            "orders_rejected": self.orders_rejected,
            "fill_rate": (
                self.orders_filled / self.orders_submitted * 100
                if self.orders_submitted > 0
                else 0
            ),
            "rejection_rate": (
                self.orders_rejected / self.orders_submitted * 100
                if self.orders_submitted > 0
                else 0
            ),
        }


class StatusManagementMixin:
    """Mixin for connection and adapter status management."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Status tracking
        self.status_history: deque = deque(maxlen=100)
        self.last_heartbeat: Optional[datetime] = None
        self.error_count = 0
        self.warning_count = 0

        # Connection metrics
        self.connection_attempts = 0
        self.reconnection_count = 0
        self.total_downtime = timedelta()
        self.last_disconnect_time: Optional[datetime] = None

        logger.debug(
            f"Initialized status management for {getattr(self, 'adapter_id', 'unknown')}"
        )

    def update_status(
        self,
        status: ConnectionStatus,
        message: Optional[str] = None,
        error: Optional[Exception] = None,
    ):
        """Update adapter status.

        Args:
            status: New connection status.
            message: Optional status message.
            error: Optional error if status is ERROR.
        """
        previous_status = getattr(self.connection, "status", None)

        # Update connection object
        self.connection.status = status
        self.connection.last_heartbeat = datetime.now(timezone.utc)

        if error:
            self.connection.error_message = str(error)
            self.error_count += 1

        # Track status changes
        status_entry = {
            "timestamp": datetime.now(timezone.utc),
            "status": status.value,
            "previous_status": previous_status.value if previous_status else None,
            "message": message,
            "error": str(error) if error else None,
        }
        self.status_history.append(status_entry)

        # Handle specific status transitions
        if status == ConnectionStatus.CONNECTED and previous_status in [
            ConnectionStatus.DISCONNECTED,
            ConnectionStatus.ERROR,
        ]:
            self.connection.connected_at = datetime.now(timezone.utc)
            if self.last_disconnect_time:
                self.total_downtime += (
                    datetime.now(timezone.utc) - self.last_disconnect_time
                )
                self.last_disconnect_time = None
            if previous_status != ConnectionStatus.DISCONNECTED:
                self.reconnection_count += 1

        elif (
            status in [ConnectionStatus.DISCONNECTED, ConnectionStatus.ERROR]
            and previous_status == ConnectionStatus.CONNECTED
        ):
            self.last_disconnect_time = datetime.now(timezone.utc)
            self.connection.connected_at = None

        # Update heartbeat
        self.last_heartbeat = datetime.now(timezone.utc)

        logger.debug(f"Status updated to {status.value}: {message}")

    def record_heartbeat(self):
        """Record a heartbeat timestamp."""
        self.last_heartbeat = datetime.now(timezone.utc)
        self.connection.last_heartbeat = self.last_heartbeat

    def is_healthy(self) -> bool:
        """Check if adapter is healthy.

        Returns:
            True if adapter is healthy, False otherwise.
        """
        if not self.connection.is_connected():
            return False

        # Check heartbeat (should be within last 60 seconds)
        if self.last_heartbeat:
            time_since_heartbeat = datetime.now(timezone.utc) - self.last_heartbeat
            if time_since_heartbeat > timedelta(seconds=60):
                return False

        return True

    def get_uptime(self) -> timedelta:
        """Get current uptime.

        Returns:
            Current uptime or zero if not connected.
        """
        if self.connection.connected_at:
            return datetime.now(timezone.utc) - self.connection.connected_at
        return timedelta()

    def get_status_summary(self) -> Dict[str, Any]:
        """Get status summary.

        Returns:
            Dictionary containing status information.
        """
        return {
            "current_status": self.connection.status.value,
            "is_healthy": self.is_healthy(),
            "connected_at": (
                self.connection.connected_at.isoformat()
                if self.connection.connected_at
                else None
            ),
            "last_heartbeat": (
                self.last_heartbeat.isoformat() if self.last_heartbeat else None
            ),
            "uptime_seconds": self.get_uptime().total_seconds(),
            "connection_attempts": self.connection_attempts,
            "reconnection_count": self.reconnection_count,
            "total_downtime_seconds": self.total_downtime.total_seconds(),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }


class MetricsMixin:
    """Mixin for performance metrics collection."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Performance metrics
        self.response_times: deque = deque(maxlen=1000)
        self.request_count = 0
        self.error_count = 0
        self.success_count = 0

        # Throughput metrics
        self.messages_sent = 0
        self.messages_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0

        # Rate limiting
        self.requests_per_minute: deque = deque(maxlen=60)
        self.current_minute = datetime.now(timezone.utc).minute

        logger.debug(
            f"Initialized metrics collection for {getattr(self, 'adapter_id', 'unknown')}"
        )

    def record_request(
        self,
        response_time: float,
        success: bool = True,
        bytes_sent: int = 0,
        bytes_received: int = 0,
    ):
        """Record a request metric.

        Args:
            response_time: Request response time in seconds.
            success: Whether the request was successful.
            bytes_sent: Number of bytes sent.
            bytes_received: Number of bytes received.
        """
        self.response_times.append(response_time)
        self.request_count += 1

        if success:
            self.success_count += 1
        else:
            self.error_count += 1

        self.bytes_sent += bytes_sent
        self.bytes_received += bytes_received

        # Update rate limiting
        current_minute = datetime.now(timezone.utc).minute
        if current_minute != self.current_minute:
            self.requests_per_minute.append(0)
            self.current_minute = current_minute

        if self.requests_per_minute:
            self.requests_per_minute[-1] += 1
        else:
            self.requests_per_minute.append(1)

    def record_message_sent(self, bytes_count: int = 0):
        """Record a sent message."""
        self.messages_sent += 1
        self.bytes_sent += bytes_count

    def record_message_received(self, bytes_count: int = 0):
        """Record a received message."""
        self.messages_received += 1
        self.bytes_received += bytes_count

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics.

        Returns:
            Dictionary containing performance metrics.
        """
        if self.response_times:
            response_times_list = list(self.response_times)
            avg_response_time = sum(response_times_list) / len(response_times_list)
            min_response_time = min(response_times_list)
            max_response_time = max(response_times_list)

            # Calculate percentiles
            sorted_times = sorted(response_times_list)
            p95_index = int(len(sorted_times) * 0.95)
            p99_index = int(len(sorted_times) * 0.99)
            p95_response_time = (
                sorted_times[p95_index]
                if p95_index < len(sorted_times)
                else max_response_time
            )
            p99_response_time = (
                sorted_times[p99_index]
                if p99_index < len(sorted_times)
                else max_response_time
            )
        else:
            avg_response_time = min_response_time = max_response_time = 0
            p95_response_time = p99_response_time = 0

        current_rpm = sum(self.requests_per_minute) if self.requests_per_minute else 0

        return {
            "request_count": self.request_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": (
                self.success_count / self.request_count * 100
                if self.request_count > 0
                else 100
            ),
            "error_rate": (
                self.error_count / self.request_count * 100
                if self.request_count > 0
                else 0
            ),
            "avg_response_time_ms": avg_response_time * 1000,
            "min_response_time_ms": min_response_time * 1000,
            "max_response_time_ms": max_response_time * 1000,
            "p95_response_time_ms": p95_response_time * 1000,
            "p99_response_time_ms": p99_response_time * 1000,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "requests_per_minute": current_rpm,
        }


class RateLimitingMixin:
    """Mixin for rate limiting functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Rate limiting configuration
        self.max_requests_per_second = getattr(
            self.config.limits, "max_orders_per_second", 10
        )
        self.max_requests_per_minute = self.max_requests_per_second * 60

        # Rate tracking
        self.request_timestamps: deque = deque()
        self.requests_this_second = 0
        self.requests_this_minute = 0
        self.current_second = datetime.now(timezone.utc).second
        self.current_minute = datetime.now(timezone.utc).minute

        # Throttling
        self.throttled_requests = 0

        logger.debug(
            f"Initialized rate limiting for {getattr(self, 'adapter_id', 'unknown')}"
        )

    async def check_rate_limit(self) -> bool:
        """Check if request is within rate limits.

        Returns:
            True if request is allowed, False if throttled.
        """
        now = datetime.now(timezone.utc)
        current_second = now.second
        current_minute = now.minute

        # Clean old timestamps
        cutoff_time = now - timedelta(seconds=60)
        while self.request_timestamps and self.request_timestamps[0] < cutoff_time:
            self.request_timestamps.popleft()

        # Reset counters if needed
        if current_second != self.current_second:
            self.requests_this_second = 0
            self.current_second = current_second

        if current_minute != self.current_minute:
            self.requests_this_minute = 0
            self.current_minute = current_minute

        # Count recent requests
        recent_requests = len(
            [ts for ts in self.request_timestamps if ts > now - timedelta(seconds=1)]
        )

        # Check limits
        if recent_requests >= self.max_requests_per_second:
            self.throttled_requests += 1
            logger.warning(
                f"Rate limit exceeded (per second): {recent_requests}/{self.max_requests_per_second}"
            )
            return False

        if len(self.request_timestamps) >= self.max_requests_per_minute:
            self.throttled_requests += 1
            logger.warning(
                f"Rate limit exceeded (per minute): {len(self.request_timestamps)}/{self.max_requests_per_minute}"
            )
            return False

        # Record this request
        self.request_timestamps.append(now)
        self.requests_this_second += 1
        self.requests_this_minute += 1

        return True

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get rate limiting status.

        Returns:
            Dictionary containing rate limit information.
        """
        now = datetime.now(timezone.utc)

        recent_requests_1s = len(
            [ts for ts in self.request_timestamps if ts > now - timedelta(seconds=1)]
        )

        recent_requests_1m = len(self.request_timestamps)

        return {
            "max_requests_per_second": self.max_requests_per_second,
            "max_requests_per_minute": self.max_requests_per_minute,
            "requests_last_second": recent_requests_1s,
            "requests_last_minute": recent_requests_1m,
            "throttled_requests": self.throttled_requests,
            "utilization_percent_1s": (
                recent_requests_1s / self.max_requests_per_second
            )
            * 100,
            "utilization_percent_1m": (
                recent_requests_1m / self.max_requests_per_minute
            )
            * 100,
        }
