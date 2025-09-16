"""
TDD-based Order Manager for FXML4 Trading Platform.

Comprehensive order lifecycle management with intelligent routing,
state tracking, and enterprise-grade capabilities.
"""

import asyncio
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from core.exceptions import BrokerError, OrderError, RiskError
from core.order_management.order_types import Order, OrderStatus


class OrderManager:
    """
    Enterprise-grade order lifecycle management system.

    Handles order submission, routing, state management, modifications,
    cancellations, and comprehensive tracking with persistence.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        order_router=None,
        risk_manager=None,
        persistence=None,
    ):
        """Initialize OrderManager with configuration and dependencies."""
        self.config = config
        self.order_router = order_router
        self.risk_manager = risk_manager
        self.persistence = persistence

        # Order tracking
        self.active_orders: Dict[str, Order] = {}
        self.historical_orders: Dict[str, Order] = {}

        # Threading support
        self._lock = threading.RLock()

        # Metrics tracking
        self.metrics = {
            "total_orders": 0,
            "filled_orders": 0,
            "cancelled_orders": 0,
            "rejected_orders": 0,
            "fill_times": [],
            "routing_times": [],
        }

    def submit_order(self, order: Order) -> Dict[str, Any]:
        """Submit order for routing and execution."""
        import time

        with self._lock:
            # Validate order
            self._validate_order(order)

            # Check for duplicates
            if (
                order.order_id in self.active_orders
                or order.order_id in self.historical_orders
            ):
                raise OrderError(f"Duplicate order ID: {order.order_id}")

            # Route order with retry logic
            max_retries = self.config.get("max_retries", 3)
            retry_delay = self.config.get("retry_delay_seconds", 1)

            for attempt in range(max_retries):
                try:
                    routing_decision = self.order_router.route_order(order)

                    # Check for rejection
                    if (
                        isinstance(routing_decision, dict)
                        and routing_decision.get("status") == "rejected"
                    ):
                        self.metrics["rejected_orders"] += 1
                        raise OrderError(
                            f"Order rejected: {routing_decision.get('reason', 'unknown')}"
                        )

                    break  # Success

                except BrokerError as e:
                    if attempt < max_retries - 1:  # Not the last attempt
                        time.sleep(retry_delay)
                        continue
                    else:
                        # Final attempt failed
                        raise e

            # Update order status
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.now()

            # Track order
            self.active_orders[order.order_id] = order
            self.metrics["total_orders"] += 1

            # Persist order
            if self.persistence:
                self.persistence.save_order(order)

            return {
                "status": "submitted",
                "order_id": order.order_id,
                "routing_decision": routing_decision,
            }

    def _validate_order(self, order: Order) -> None:
        """Validate order before submission."""
        # Always call risk manager first if available
        if self.risk_manager:
            self.risk_manager.validate_order(order)

        # Then check basic validations
        if order.quantity <= 0:
            raise OrderError(f"Invalid quantity: {order.quantity}")

        # Check order limits
        self._check_order_limits(order)

    def _check_order_limits(self, order: Order) -> None:
        """Check order limits and constraints."""
        # Check max orders per symbol
        max_per_symbol = self.config.get("max_orders_per_symbol", 100)
        current_count = len(
            [o for o in self.active_orders.values() if o.symbol == order.symbol]
        )
        if current_count >= max_per_symbol:
            raise OrderError(f"Maximum orders per symbol exceeded: {max_per_symbol}")

        # Check max total orders
        max_total = self.config.get("max_total_orders", 1000)
        if len(self.active_orders) >= max_total:
            raise OrderError(f"Maximum total orders exceeded: {max_total}")

    def get_order(self, order_id: str) -> Order:
        """Retrieve order by ID."""
        if order_id in self.active_orders:
            return self.active_orders[order_id]
        elif order_id in self.historical_orders:
            return self.historical_orders[order_id]
        else:
            raise OrderError(f"Order not found: {order_id}")

    def acknowledge_order(self, order_id: str, broker: str) -> None:
        """Mark order as acknowledged by broker."""
        with self._lock:
            if order_id not in self.active_orders:
                raise OrderError(f"Order not found: {order_id}")

            order = self.active_orders[order_id]
            order.status = OrderStatus.ACKNOWLEDGED
            order.acknowledged_at = datetime.now()
            order.routed_broker = broker

            # Persist change
            if self.persistence:
                self.persistence.save_order(order)

    def process_fill(
        self, order_id: str, filled_quantity: int, fill_price: Decimal
    ) -> None:
        """Process order fill (partial or complete)."""
        with self._lock:
            if order_id not in self.active_orders:
                raise OrderError(f"Order not found: {order_id}")

            order = self.active_orders[order_id]

            # Update fill quantities
            order.filled_quantity += filled_quantity
            order.remaining_quantity = order.quantity - order.filled_quantity

            # Calculate average fill price
            if order.average_fill_price is None:
                order.average_fill_price = fill_price
            else:
                # Weighted average calculation
                prev_total = (
                    order.filled_quantity - filled_quantity
                ) * order.average_fill_price
                new_total = filled_quantity * fill_price
                order.average_fill_price = (
                    prev_total + new_total
                ) / order.filled_quantity

            # Update status
            if order.remaining_quantity == 0:
                order.status = OrderStatus.FILLED
                order.filled_at = datetime.now()
                self.metrics["filled_orders"] += 1

                # Move to historical orders
                self.historical_orders[order_id] = self.active_orders.pop(order_id)
            else:
                order.status = OrderStatus.PARTIALLY_FILLED

            # Persist change
            if self.persistence:
                self.persistence.save_order(order)

    def cancel_order(self, order_id: str, reason: str = None) -> Dict[str, Any]:
        """Cancel order and update state."""
        with self._lock:
            if order_id not in self.active_orders:
                raise OrderError(f"Order not found: {order_id}")

            order = self.active_orders[order_id]
            order.status = OrderStatus.CANCELLED
            order.metadata["cancellation_reason"] = reason or "user_requested"

            # Move to historical orders
            self.historical_orders[order_id] = self.active_orders.pop(order_id)
            self.metrics["cancelled_orders"] += 1

            # Persist change
            if self.persistence:
                self.persistence.save_order(order)

            return {"status": "cancelled", "order_id": order_id, "reason": reason}

    def modify_order(
        self, order_id: str, modifications: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Modify order attributes."""
        with self._lock:
            if order_id not in self.active_orders:
                raise OrderError(f"Order not found: {order_id}")

            order = self.active_orders[order_id]

            # Validate modifications
            if "price" in modifications:
                if modifications["price"] <= 0:
                    raise OrderError("Invalid price for modification")
                order.price = modifications["price"]

            if "quantity" in modifications:
                if modifications["quantity"] <= 0:
                    raise OrderError("Invalid quantity for modification")
                order.quantity = modifications["quantity"]
                order.remaining_quantity = order.quantity - order.filled_quantity

            # Persist change
            if self.persistence:
                self.persistence.save_order(order)

            return {
                "status": "modified",
                "order_id": order_id,
                "modifications": modifications,
            }

    def submit_batch_orders(self, orders: List[Order]) -> List[Dict[str, Any]]:
        """Submit batch of orders."""
        results = []
        for order in orders:
            try:
                result = self.submit_order(order)
                results.append(result)
            except Exception as e:
                results.append(
                    {"status": "failed", "order_id": order.order_id, "error": str(e)}
                )
        return results

    def process_timeouts(self) -> List[str]:
        """Process order timeouts."""
        expired_orders = []
        current_time = datetime.now()
        timeout_threshold = timedelta(
            seconds=self.config.get("order_timeout_seconds", 30)
        )

        with self._lock:
            for order_id, order in list(self.active_orders.items()):
                if (
                    order.submitted_at
                    and (current_time - order.submitted_at) > timeout_threshold
                ):
                    # Mark as expired instead of cancelled for timeouts
                    order.status = OrderStatus.EXPIRED
                    self.historical_orders[order_id] = self.active_orders.pop(order_id)
                    expired_orders.append(order_id)

        return expired_orders

    def recover_orders(self) -> int:
        """Recover orders from persistence."""
        if not self.persistence:
            return 0

        persisted_orders = self.persistence.load_orders()
        recovered_count = 0

        for order_data in persisted_orders:
            # Reconstruct order from persisted data (simplified)
            if order_data.get("status") in [
                "submitted",
                "acknowledged",
                "partially_filled",
            ]:
                recovered_count += 1

        return recovered_count

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        total_orders = self.metrics["total_orders"]
        filled_orders = self.metrics["filled_orders"]

        return {
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "cancelled_orders": self.metrics["cancelled_orders"],
            "rejected_orders": self.metrics["rejected_orders"],
            "fill_rate": filled_orders / total_orders if total_orders > 0 else 0.0,
            "average_fill_time": (
                sum(self.metrics["fill_times"]) / len(self.metrics["fill_times"])
                if self.metrics["fill_times"]
                else 0.0
            ),
        }

    def calculate_order_statistics(self) -> Dict[str, Any]:
        """Calculate order statistics."""
        total_orders = len(self.active_orders) + len(self.historical_orders)
        filled_orders = len(
            [
                o
                for o in self.historical_orders.values()
                if o.status == OrderStatus.FILLED
            ]
        )
        partially_filled = len(
            [
                o
                for o in self.active_orders.values()
                if o.status == OrderStatus.PARTIALLY_FILLED
            ]
        )
        cancelled_orders = len(
            [
                o
                for o in self.historical_orders.values()
                if o.status == OrderStatus.CANCELLED
            ]
        )

        # Calculate total volume and average fill price
        total_volume = sum(
            o.filled_quantity or 0
            for o in list(self.active_orders.values())
            + list(self.historical_orders.values())
        )
        filled_orders_list = [
            o
            for o in self.historical_orders.values()
            if o.status == OrderStatus.FILLED and o.average_fill_price
        ]
        avg_fill_price = (
            sum(o.average_fill_price for o in filled_orders_list)
            / len(filled_orders_list)
            if filled_orders_list
            else 0
        )

        return {
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "partially_filled_orders": partially_filled,
            "cancelled_orders": cancelled_orders,
            "total_volume_traded": total_volume,
            "average_fill_price": avg_fill_price,
        }

    def set_order_expiration(self, order_id: str, expiration_time: datetime) -> None:
        """Set order expiration time."""
        with self._lock:
            if order_id in self.active_orders:
                order = self.active_orders[order_id]
                order.metadata["expiration_time"] = expiration_time

    def process_expirations(self) -> List[str]:
        """Process expired orders."""
        expired_orders = []
        current_time = datetime.now()

        with self._lock:
            for order_id, order in list(self.active_orders.items()):
                expiration_time = order.metadata.get("expiration_time")
                if expiration_time and current_time > expiration_time:
                    order.status = OrderStatus.EXPIRED
                    self.historical_orders[order_id] = self.active_orders.pop(order_id)
                    expired_orders.append(order_id)

        return expired_orders

    def generate_order_report(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Generate comprehensive order report."""
        # Collect orders within time range
        relevant_orders = []
        for order in list(self.active_orders.values()) + list(
            self.historical_orders.values()
        ):
            if order.created_at >= start_time and order.created_at <= end_time:
                relevant_orders.append(order)

        # Group by symbol and status
        orders_by_symbol = defaultdict(list)
        orders_by_status = defaultdict(int)

        for order in relevant_orders:
            orders_by_symbol[order.symbol].append(order)
            orders_by_status[order.status.value] += 1

        return {
            "summary": {
                "total_orders": len(relevant_orders),
                "time_range": f"{start_time} to {end_time}",
            },
            "orders_by_symbol": dict(orders_by_symbol),
            "orders_by_status": dict(orders_by_status),
            "performance_metrics": self.get_performance_metrics(),
        }
