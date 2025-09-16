"""
Enhanced Order Lifecycle Management for Phase 5.

This module provides comprehensive order tracking and lifecycle management
across the full order journey from submission to completion, with real-time
performance monitoring and advanced state management.

Key Features:
- Comprehensive order state tracking with validation
- Performance metrics collection (latency, throughput, success rates)
- Real-time order monitoring and alerting
- Advanced error handling and recovery mechanisms
- Integration with compliance and audit systems
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ..api.auth.compliance_logger import soc2_compliance_logger
from ..core.logging import get_logger
from ..fix.messages.base import OrdType, Side

logger = get_logger(__name__)


class OrderLifecycleStatus(Enum):
    """Enhanced order lifecycle status enumeration."""

    # Pre-submission states
    VALIDATING = "VALIDATING"
    ROUTING = "ROUTING"

    # Submission states
    SUBMITTED = "SUBMITTED"
    PENDING_ACKNOWLEDGMENT = "PENDING_ACKNOWLEDGMENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"

    # Execution states
    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"

    # Terminal states
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class OrderPriority(Enum):
    """Order priority levels for routing and processing."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


@dataclass
class OrderPerformanceMetrics:
    """Performance metrics for individual orders."""

    submission_timestamp: datetime
    acknowledgment_timestamp: Optional[datetime] = None
    first_fill_timestamp: Optional[datetime] = None
    completion_timestamp: Optional[datetime] = None

    acknowledgment_latency_ms: Optional[float] = None
    first_fill_latency_ms: Optional[float] = None
    total_execution_time_ms: Optional[float] = None

    routing_time_ms: Optional[float] = None
    broker_processing_time_ms: Optional[float] = None
    network_latency_ms: Optional[float] = None

    retry_count: int = 0
    broker_switches: int = 0
    compliance_check_time_ms: Optional[float] = None


@dataclass
class OrderTracker:
    """Comprehensive order tracking and lifecycle management."""

    # Identification
    tracking_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_order_id: str = ""
    broker_order_id: Optional[str] = None

    # Order details
    symbol: str = ""
    side: Side = Side.BUY
    quantity: Decimal = Decimal("0")
    order_type: OrdType = OrdType.MARKET
    price: Optional[Decimal] = None
    time_in_force: str = "DAY"

    # User context
    user_id: str = ""
    account_id: str = ""
    strategy_id: Optional[str] = None

    # State management
    status: OrderLifecycleStatus = OrderLifecycleStatus.VALIDATING
    previous_status: Optional[OrderLifecycleStatus] = None
    status_history: List[Dict[str, Any]] = field(default_factory=list)

    # Execution tracking
    filled_quantity: Decimal = Decimal("0")
    remaining_quantity: Decimal = Decimal("0")
    average_price: Optional[Decimal] = None
    commission: Decimal = Decimal("0")

    # Broker information
    selected_broker: Optional[str] = None
    execution_broker: Optional[str] = None
    routing_attempts: int = 0
    broker_routing_history: List[str] = field(default_factory=list)

    # Performance metrics
    performance_metrics: OrderPerformanceMetrics = field(default_factory=lambda: None)

    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    # Priority and routing
    priority: OrderPriority = OrderPriority.NORMAL
    routing_strategy: str = "default"

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Compliance and audit
    compliance_validated: bool = False
    compliance_checks: Dict[str, bool] = field(default_factory=dict)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize performance metrics if not provided."""
        if self.performance_metrics is None:
            self.performance_metrics = OrderPerformanceMetrics(
                submission_timestamp=self.created_at
            )

        # Initialize remaining quantity
        if self.remaining_quantity == Decimal("0"):
            self.remaining_quantity = self.quantity

    def update_status(
        self,
        new_status: OrderLifecycleStatus,
        broker_order_id: Optional[str] = None,
        filled_quantity: Optional[Decimal] = None,
        average_price: Optional[Decimal] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update order status with validation."""
        # Validate state transition
        if not self._is_valid_transition(self.status, new_status):
            logger.warning(
                f"Invalid status transition from {self.status} to {new_status} "
                f"for order {self.client_order_id}"
            )
            return False

        # Record status history
        status_change = {
            "from_status": self.status.value,
            "to_status": new_status.value,
            "timestamp": datetime.now(timezone.utc),
            "broker_order_id": broker_order_id,
            "error_message": error_message,
        }
        self.status_history.append(status_change)

        # Update status
        self.previous_status = self.status
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

        # Update additional fields
        if broker_order_id:
            self.broker_order_id = broker_order_id

        if filled_quantity is not None:
            self.filled_quantity = filled_quantity
            self.remaining_quantity = self.quantity - self.filled_quantity

        if average_price is not None:
            self.average_price = average_price

        if error_message:
            self.error_message = error_message

        # Update performance metrics
        self._update_performance_metrics(new_status)

        # Add to audit trail
        self._add_audit_entry(
            "status_update",
            {
                "status": new_status.value,
                "broker_order_id": broker_order_id,
                "filled_quantity": str(filled_quantity) if filled_quantity else None,
                "average_price": str(average_price) if average_price else None,
            },
        )

        return True

    def _is_valid_transition(
        self, from_status: OrderLifecycleStatus, to_status: OrderLifecycleStatus
    ) -> bool:
        """Validate order status transitions."""
        valid_transitions = {
            OrderLifecycleStatus.VALIDATING: {
                OrderLifecycleStatus.ROUTING,
                OrderLifecycleStatus.REJECTED,
                OrderLifecycleStatus.FAILED,
            },
            OrderLifecycleStatus.ROUTING: {
                OrderLifecycleStatus.SUBMITTED,
                OrderLifecycleStatus.REJECTED,
                OrderLifecycleStatus.FAILED,
            },
            OrderLifecycleStatus.SUBMITTED: {
                OrderLifecycleStatus.PENDING_ACKNOWLEDGMENT,
                OrderLifecycleStatus.ACKNOWLEDGED,
                OrderLifecycleStatus.REJECTED,
                OrderLifecycleStatus.FAILED,
            },
            OrderLifecycleStatus.PENDING_ACKNOWLEDGMENT: {
                OrderLifecycleStatus.ACKNOWLEDGED,
                OrderLifecycleStatus.REJECTED,
                OrderLifecycleStatus.FAILED,
                OrderLifecycleStatus.EXPIRED,
            },
            OrderLifecycleStatus.ACKNOWLEDGED: {
                OrderLifecycleStatus.WORKING,
                OrderLifecycleStatus.CANCELLED,
                OrderLifecycleStatus.REJECTED,
                OrderLifecycleStatus.EXPIRED,
            },
            OrderLifecycleStatus.WORKING: {
                OrderLifecycleStatus.PARTIALLY_FILLED,
                OrderLifecycleStatus.FILLED,
                OrderLifecycleStatus.CANCELLED,
                OrderLifecycleStatus.REJECTED,
                OrderLifecycleStatus.EXPIRED,
            },
            OrderLifecycleStatus.PARTIALLY_FILLED: {
                OrderLifecycleStatus.FILLED,
                OrderLifecycleStatus.CANCELLED,
                OrderLifecycleStatus.EXPIRED,
            },
            # Terminal states cannot transition
            OrderLifecycleStatus.FILLED: set(),
            OrderLifecycleStatus.CANCELLED: set(),
            OrderLifecycleStatus.REJECTED: set(),
            OrderLifecycleStatus.EXPIRED: set(),
            OrderLifecycleStatus.FAILED: set(),
        }

        return to_status in valid_transitions.get(from_status, set())

    def _update_performance_metrics(self, new_status: OrderLifecycleStatus):
        """Update performance metrics based on status change."""
        current_time = datetime.now(timezone.utc)
        metrics = self.performance_metrics

        if (
            new_status == OrderLifecycleStatus.ACKNOWLEDGED
            and metrics.acknowledgment_timestamp is None
        ):
            metrics.acknowledgment_timestamp = current_time
            metrics.acknowledgment_latency_ms = (
                current_time - metrics.submission_timestamp
            ).total_seconds() * 1000

        elif (
            new_status == OrderLifecycleStatus.PARTIALLY_FILLED
            and metrics.first_fill_timestamp is None
        ):
            metrics.first_fill_timestamp = current_time
            metrics.first_fill_latency_ms = (
                current_time - metrics.submission_timestamp
            ).total_seconds() * 1000

        elif new_status in {
            OrderLifecycleStatus.FILLED,
            OrderLifecycleStatus.CANCELLED,
            OrderLifecycleStatus.REJECTED,
            OrderLifecycleStatus.EXPIRED,
        }:
            metrics.completion_timestamp = current_time
            metrics.total_execution_time_ms = (
                current_time - metrics.submission_timestamp
            ).total_seconds() * 1000

    def _add_audit_entry(self, action: str, data: Dict[str, Any]):
        """Add entry to audit trail."""
        audit_entry = {
            "action": action,
            "timestamp": datetime.now(timezone.utc),
            "data": data,
            "user_id": self.user_id,
            "status": self.status.value,
        }
        self.audit_trail.append(audit_entry)

    @property
    def is_terminal_state(self) -> bool:
        """Check if order is in a terminal state."""
        return self.status in {
            OrderLifecycleStatus.FILLED,
            OrderLifecycleStatus.CANCELLED,
            OrderLifecycleStatus.REJECTED,
            OrderLifecycleStatus.EXPIRED,
            OrderLifecycleStatus.FAILED,
        }

    @property
    def fill_percentage(self) -> float:
        """Calculate fill percentage."""
        if self.quantity == 0:
            return 0.0
        return float((self.filled_quantity / self.quantity) * 100)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tracking_id": self.tracking_id,
            "client_order_id": self.client_order_id,
            "broker_order_id": self.broker_order_id,
            "symbol": self.symbol,
            "side": self.side.value if isinstance(self.side, Side) else self.side,
            "quantity": str(self.quantity),
            "order_type": (
                self.order_type.value
                if isinstance(self.order_type, OrdType)
                else self.order_type
            ),
            "price": str(self.price) if self.price else None,
            "status": self.status.value,
            "filled_quantity": str(self.filled_quantity),
            "remaining_quantity": str(self.remaining_quantity),
            "average_price": str(self.average_price) if self.average_price else None,
            "selected_broker": self.selected_broker,
            "execution_broker": self.execution_broker,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "performance_metrics": (
                {
                    "acknowledgment_latency_ms": (
                        self.performance_metrics.acknowledgment_latency_ms
                    ),
                    "total_execution_time_ms": (
                        self.performance_metrics.total_execution_time_ms
                    ),
                    "routing_time_ms": self.performance_metrics.routing_time_ms,
                    "retry_count": self.performance_metrics.retry_count,
                }
                if self.performance_metrics
                else None
            ),
            "metadata": self.metadata,
        }


class OrderLifecycleManager:
    """Manager for enhanced order lifecycle tracking."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize lifecycle manager."""
        self.config = config or {}
        self.order_trackers: Dict[str, OrderTracker] = {}
        self.user_orders: Dict[str, Set[str]] = {}
        self.broker_orders: Dict[str, Set[str]] = {}

        # Performance tracking
        self.performance_stats = {
            "total_orders": 0,
            "completed_orders": 0,
            "average_latency_ms": 0.0,
            "success_rate": 0.0,
        }

        self.lock = asyncio.Lock()

    async def create_order_tracker(
        self,
        client_order_id: str,
        user_id: str,
        symbol: str,
        side: Side,
        quantity: Decimal,
        order_type: OrdType = OrdType.MARKET,
        price: Optional[Decimal] = None,
        priority: OrderPriority = OrderPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create new order tracker."""
        async with self.lock:
            tracker = OrderTracker(
                client_order_id=client_order_id,
                user_id=user_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price,
                priority=priority,
                metadata=metadata or {},
            )

            tracking_id = tracker.tracking_id
            self.order_trackers[tracking_id] = tracker

            # Update indices
            if user_id not in self.user_orders:
                self.user_orders[user_id] = set()
            self.user_orders[user_id].add(tracking_id)

            # Log order creation
            await soc2_compliance_logger.log_trading_transaction(
                session=None,  # Would be provided by calling context
                user_id=user_id,
                transaction_data={
                    "action": "order_created",
                    "tracking_id": tracking_id,
                    "client_order_id": client_order_id,
                    "symbol": symbol,
                    "quantity": str(quantity),
                    "order_type": order_type.value,
                },
                compliance_frameworks=["SOC_2", "MIFID_II"],
            )

            self.performance_stats["total_orders"] += 1
            logger.info(f"Created order tracker {tracking_id} for user {user_id}")

            return tracking_id

    async def get_order_tracker(self, tracking_id: str) -> Optional[OrderTracker]:
        """Get order tracker by ID."""
        return self.order_trackers.get(tracking_id)

    async def update_order_status(
        self,
        tracking_id: str,
        new_status: OrderLifecycleStatus,
        broker_order_id: Optional[str] = None,
        filled_quantity: Optional[Decimal] = None,
        average_price: Optional[Decimal] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update order status with comprehensive tracking."""
        async with self.lock:
            tracker = self.order_trackers.get(tracking_id)
            if not tracker:
                logger.warning(f"Order tracker {tracking_id} not found")
                return False

            success = tracker.update_status(
                new_status=new_status,
                broker_order_id=broker_order_id,
                filled_quantity=filled_quantity,
                average_price=average_price,
                error_message=error_message,
            )

            if success:
                # Update broker index
                if broker_order_id and tracker.execution_broker:
                    if tracker.execution_broker not in self.broker_orders:
                        self.broker_orders[tracker.execution_broker] = set()
                    self.broker_orders[tracker.execution_broker].add(tracking_id)

                # Update performance stats
                if tracker.is_terminal_state:
                    self.performance_stats["completed_orders"] += 1
                    self._update_performance_stats(tracker)

                logger.info(f"Updated order {tracking_id} status to {new_status.value}")

            return success

    def _update_performance_stats(self, tracker: OrderTracker):
        """Update aggregate performance statistics."""
        if tracker.performance_metrics.total_execution_time_ms:
            completed = self.performance_stats["completed_orders"]
            current_avg = self.performance_stats["average_latency_ms"]
            new_latency = tracker.performance_metrics.total_execution_time_ms

            # Calculate running average
            self.performance_stats["average_latency_ms"] = (
                current_avg * (completed - 1) + new_latency
            ) / completed

        # Calculate success rate
        total = self.performance_stats["total_orders"]
        completed = self.performance_stats["completed_orders"]
        success_orders = sum(
            1
            for t in self.order_trackers.values()
            if t.is_terminal_state and t.status == OrderLifecycleStatus.FILLED
        )

        if total > 0:
            self.performance_stats["success_rate"] = (success_orders / total) * 100

    async def get_orders_by_user(self, user_id: str) -> List[OrderTracker]:
        """Get all orders for a specific user."""
        user_tracking_ids = self.user_orders.get(user_id, set())
        return [
            self.order_trackers[tid]
            for tid in user_tracking_ids
            if tid in self.order_trackers
        ]

    async def get_orders_by_broker(self, broker_id: str) -> List[OrderTracker]:
        """Get all orders for a specific broker."""
        broker_tracking_ids = self.broker_orders.get(broker_id, set())
        return [
            self.order_trackers[tid]
            for tid in broker_tracking_ids
            if tid in self.order_trackers
        ]

    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        return {
            "total_orders_processed": self.performance_stats["total_orders"],
            "completed_orders": self.performance_stats["completed_orders"],
            "average_acknowledgment_latency_ms": self.performance_stats[
                "average_latency_ms"
            ],
            "success_rate_percent": self.performance_stats["success_rate"],
            "p50_acknowledgment_latency_ms": self._calculate_percentile_latency(50),
            "p95_acknowledgment_latency_ms": self._calculate_percentile_latency(95),
            "p99_acknowledgment_latency_ms": self._calculate_percentile_latency(99),
            "active_orders": len(
                [t for t in self.order_trackers.values() if not t.is_terminal_state]
            ),
        }

    def _calculate_percentile_latency(self, percentile: int) -> Optional[float]:
        """Calculate latency percentile."""
        latencies = [
            t.performance_metrics.acknowledgment_latency_ms
            for t in self.order_trackers.values()
            if (
                t.performance_metrics
                and t.performance_metrics.acknowledgment_latency_ms is not None
            )
        ]

        if not latencies:
            return None

        latencies.sort()
        index = int((percentile / 100.0) * len(latencies))
        return latencies[min(index, len(latencies) - 1)]

    async def cleanup_completed_orders(self, max_age_hours: int = 24):
        """Clean up old completed orders to manage memory."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        async with self.lock:
            to_remove = []
            for tracking_id, tracker in self.order_trackers.items():
                if tracker.is_terminal_state and tracker.updated_at < cutoff_time:
                    to_remove.append(tracking_id)

            for tracking_id in to_remove:
                tracker = self.order_trackers[tracking_id]

                # Remove from indices
                if tracker.user_id in self.user_orders:
                    self.user_orders[tracker.user_id].discard(tracking_id)

                if tracker.execution_broker in self.broker_orders:
                    self.broker_orders[tracker.execution_broker].discard(tracking_id)

                # Remove tracker
                del self.order_trackers[tracking_id]

            logger.info(f"Cleaned up {len(to_remove)} completed orders")


# Global lifecycle manager instance
_lifecycle_manager = None


def get_lifecycle_manager() -> OrderLifecycleManager:
    """Get global order lifecycle manager instance."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = OrderLifecycleManager()
    return _lifecycle_manager
