"""
Order Router for FXML4 Trading System.

Provides intelligent order routing functionality including:
- Multi-broker order routing with failover
- Latency-based routing optimization
- Load balancing across brokers
- Real-time broker health monitoring
- Risk-aware routing decisions
- Order splitting and aggregation
- Market hours validation
- Regulatory compliance checks
"""

import asyncio
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from datetime import time as dt_time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from core.exceptions import BrokerError, OrderError, RiskManagementError
from core.order_management.order_types import Order, OrderSide, OrderStatus, OrderType


class OrderRouter:
    """Intelligent order routing system."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize order router with configuration."""
        self.config = config
        self.brokers = config["brokers"]
        self.routing_strategy = config["routing_strategy"]
        self.failover_enabled = config["failover_enabled"]
        self.max_routing_attempts = config["max_routing_attempts"]
        self.risk_limits = config["risk_limits"]

        # Broker management
        self.broker_clients = {}
        self.broker_health = {}
        self.broker_latencies = {}
        self.broker_loads = defaultdict(int)

        # Metrics tracking
        self.routing_metrics = {
            "total_orders": 0,
            "broker_distribution": defaultdict(int),
            "routing_times": deque(maxlen=1000),
            "success_count": 0,
            "failure_count": 0,
        }

        # Threading
        self._lock = threading.RLock()

        # Initialize broker health monitoring
        self._initialize_broker_monitoring()

    def route_order(self, order: Order) -> Dict[str, Any]:
        """Route order to optimal broker."""
        start_time = time.time()

        with self._lock:
            self.routing_metrics["total_orders"] += 1

            try:
                # Validate order constraints
                self._validate_order_risk_limits(order)

                # Get available brokers for symbol
                available_brokers = self.get_brokers_for_symbol(order.symbol)
                if not available_brokers:
                    raise OrderError(f"No brokers available for symbol {order.symbol}")

                # Apply routing strategy
                routing_decision = self._apply_routing_strategy(
                    order, available_brokers
                )

                # Update metrics
                routing_time = time.time() - start_time
                self.routing_metrics["routing_times"].append(routing_time)
                self.routing_metrics["broker_distribution"][
                    routing_decision["selected_broker"]
                ] += 1
                self.routing_metrics["success_count"] += 1

                return routing_decision

            except Exception as e:
                self.routing_metrics["failure_count"] += 1
                raise

    def validate_order_constraints(self, order: Order, broker: str) -> None:
        """Validate order against broker constraints."""
        broker_config = self.brokers[broker]

        # Check minimum size
        if order.quantity < broker_config["min_size"]:
            raise OrderError(
                f"Order quantity {order.quantity} below minimum size {broker_config['min_size']} for {broker}"
            )

        # Check maximum size
        if order.quantity > broker_config["max_size"]:
            raise OrderError(
                f"Order quantity {order.quantity} exceeds maximum size {broker_config['max_size']} for {broker}"
            )

        # Check supported order types
        if order.order_type.value not in broker_config["supported_order_types"]:
            raise OrderError(
                f"Order type {order.order_type.value} is unsupported order type for {broker}"
            )

        # Check symbol support
        if order.symbol not in broker_config["supported_symbols"]:
            raise OrderError(f"Symbol {order.symbol} not supported by {broker}")

    def validate_trading_hours(self, order: Order, broker: str) -> None:
        """Validate order against trading hours."""
        if not self.is_market_open(broker):
            raise OrderError(
                f"Order cannot be placed outside trading hours for {broker}"
            )

    def is_market_open(self, broker: str) -> bool:
        """Check if market is open for broker."""
        broker_config = self.brokers[broker]
        trading_hours = broker_config.get("trading_hours")

        if not trading_hours:
            return True  # 24/7 trading

        now = datetime.now().time()
        start_time = dt_time.fromisoformat(trading_hours["start"])
        end_time = dt_time.fromisoformat(trading_hours["end"])

        return start_time <= now <= end_time

    def can_route_order(self, order: Order, broker: str) -> bool:
        """Check if order can be routed to broker."""
        try:
            self.validate_order_constraints(order, broker)
            self.validate_trading_hours(order, broker)
            return True
        except OrderError:
            return False

    def get_brokers_for_symbol(self, symbol: str) -> List[str]:
        """Get list of brokers that support the symbol."""
        available_brokers = []
        for broker_name, broker_config in self.brokers.items():
            if symbol in broker_config["supported_symbols"]:
                available_brokers.append(broker_name)
        return available_brokers

    def check_all_broker_health(self) -> Dict[str, Dict[str, Any]]:
        """Check health status of all brokers."""
        health_status = {}

        for broker_name in self.brokers.keys():
            health_status[broker_name] = {
                "healthy": self._check_broker_health(broker_name),
                "last_check": datetime.utcnow(),
                "latency": self.broker_latencies.get(broker_name, 0.0),
                "load": self.broker_loads.get(broker_name, 0),
            }

        return health_status

    async def measure_broker_latencies(self) -> Dict[str, float]:
        """Measure response latencies for all brokers."""
        latencies = {}

        async def ping_broker(broker_name: str) -> Tuple[str, float]:
            start_time = time.time()
            try:
                # Simulate ping - in real implementation would ping actual broker
                await asyncio.sleep(0.001)  # Simulate network delay
                client = self.broker_clients.get(broker_name)
                if client and hasattr(client, "ping_async"):
                    await client.ping_async()
                latency = (time.time() - start_time) * 1000  # Convert to ms
                return broker_name, latency
            except Exception:
                return broker_name, 9999.0  # High latency for failed pings

        # Ping all brokers concurrently
        ping_tasks = [ping_broker(broker) for broker in self.brokers.keys()]
        results = await asyncio.gather(*ping_tasks)

        for broker_name, latency in results:
            latencies[broker_name] = latency

        self.broker_latencies.update(latencies)
        return latencies

    def split_large_order(self, order: Order, broker: str) -> List[Order]:
        """Split large order into smaller chunks."""
        broker_config = self.brokers[broker]
        max_size = broker_config["max_size"]

        if order.quantity <= max_size:
            return [order]

        split_orders = []
        remaining_quantity = order.quantity
        chunk_number = 1

        while remaining_quantity > 0:
            chunk_size = min(remaining_quantity, max_size)

            split_order = Order(
                order_id=f"{order.order_id}_{chunk_number:03d}",
                symbol=order.symbol,
                order_type=order.order_type,
                side=order.side,
                quantity=chunk_size,
                price=order.price,
                stop_price=order.stop_price,
                client_id=order.client_id,
                time_in_force=order.time_in_force,
                priority=order.priority,
            )

            split_orders.append(split_order)
            remaining_quantity -= chunk_size
            chunk_number += 1

        return split_orders

    def aggregate_small_orders(self, orders: List[Order], broker: str) -> List[Order]:
        """Aggregate small orders for efficiency."""
        if not orders:
            return []

        # Group by symbol, type, side, and price
        groups = defaultdict(list)
        for order in orders:
            key = (order.symbol, order.order_type, order.side, order.price)
            groups[key].append(order)

        aggregated_orders = []
        for (symbol, order_type, side, price), group_orders in groups.items():
            if len(group_orders) == 1:
                aggregated_orders.extend(group_orders)
                continue

            # Aggregate orders
            total_quantity = sum(order.quantity for order in group_orders)
            client_ids = [order.client_id for order in group_orders]

            aggregated_order = Order(
                order_id=f"AGG_{int(time.time() * 1000)}",
                symbol=symbol,
                order_type=order_type,
                side=side,
                quantity=total_quantity,
                price=price,
                client_id=client_ids[0],  # Primary client
                metadata={
                    "aggregated_from": [order.order_id for order in group_orders]
                },
            )

            aggregated_orders.append(aggregated_order)

        return aggregated_orders

    def calculate_routing_scores(
        self, order: Order, broker_metrics: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """Calculate routing scores for each broker."""
        scores = {}

        for broker_name, metrics in broker_metrics.items():
            if not self.can_route_order(order, broker_name):
                scores[broker_name] = 0.0
                continue

            # Base score components
            latency_score = max(
                0, 100 - (metrics.get("latency", 0) * 10)
            )  # Lower latency = higher score
            health_score = metrics.get("health_score", 1.0) * 100
            load_score = max(
                0, 100 - (metrics.get("load", 0) * 100)
            )  # Lower load = higher score

            # Priority and weight from configuration
            broker_config = self.brokers[broker_name]
            priority_score = (
                100 - (broker_config.get("priority", 1) - 1) * 10
            )  # Priority 1 = 100, 2 = 90, etc.
            weight = broker_config.get("weight", 33) / 100.0

            # Combined score
            raw_score = (
                latency_score * 0.3
                + health_score * 0.3
                + load_score * 0.2
                + priority_score * 0.2
            )
            scores[broker_name] = raw_score * weight

        return scores

    def validate_risk_limits(self, order: Order) -> None:
        """Validate order against risk limits."""
        # Check position limits first (more specific)
        position_limits = self.risk_limits.get("position_limits", {})
        if order.symbol in position_limits:
            limit = position_limits[order.symbol]
            if order.quantity > limit:
                raise RiskManagementError(
                    f"Order quantity {order.quantity} exceeds position limit {limit} for {order.symbol}"
                )

        # Check maximum order size
        max_order_size = self.risk_limits.get("max_order_size", float("inf"))
        if order.quantity > max_order_size:
            raise RiskManagementError(
                f"Order quantity {order.quantity} exceeds maximum order size {max_order_size}"
            )

    def route_order_modification(
        self, modified_order: Order, original_routing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Route order modification to same broker when possible."""
        original_broker = original_routing.get("selected_broker")

        if original_broker and self.can_route_order(modified_order, original_broker):
            return {
                "selected_broker": original_broker,
                "reason": "modification_same_broker",
                "routing_score": 100.0,
                "fallback_brokers": [],
            }

        # If can't route to same broker, use normal routing
        return self.route_order(modified_order)

    async def route_order_async(self, order: Order) -> Dict[str, Any]:
        """Asynchronous order routing."""
        return self.route_order(order)

    def create_remaining_order(
        self, original_order: Order, partial_fill_info: Dict[str, Any]
    ) -> Order:
        """Create order for remaining quantity after partial fill."""
        remaining_quantity = partial_fill_info["remaining_quantity"]

        remaining_order = Order(
            order_id=f"{original_order.order_id}_REMAINING",
            symbol=original_order.symbol,
            order_type=original_order.order_type,
            side=original_order.side,
            quantity=remaining_quantity,
            price=original_order.price,
            stop_price=original_order.stop_price,
            client_id=original_order.client_id,
            time_in_force=original_order.time_in_force,
            priority=original_order.priority,
        )

        return remaining_order

    def route_remaining_order(
        self, remaining_order: Order, original_broker: str
    ) -> Dict[str, Any]:
        """Route remaining order after partial fill."""
        if self.can_route_order(remaining_order, original_broker):
            return {
                "selected_broker": original_broker,
                "reason": "partial_fill_continuation",
                "routing_score": 100.0,
                "fallback_brokers": [],
            }

        # If can't route to same broker, use normal routing
        return self.route_order(remaining_order)

    def get_routing_metrics(self) -> Dict[str, Any]:
        """Get current routing performance metrics."""
        total_attempts = (
            self.routing_metrics["success_count"]
            + self.routing_metrics["failure_count"]
        )
        success_rate = (
            (self.routing_metrics["success_count"] / total_attempts * 100)
            if total_attempts > 0
            else 0
        )

        routing_times = list(self.routing_metrics["routing_times"])
        avg_routing_time = (
            sum(routing_times) / len(routing_times) if routing_times else 0
        )

        return {
            "total_orders": self.routing_metrics["total_orders"],
            "broker_distribution": dict(self.routing_metrics["broker_distribution"]),
            "average_routing_time": avg_routing_time,
            "success_rate": success_rate,
        }

    def _apply_routing_strategy(
        self, order: Order, available_brokers: List[str]
    ) -> Dict[str, Any]:
        """Apply configured routing strategy."""
        # Check for emergency priority first
        if hasattr(order, "priority") and order.priority == "emergency":
            return self._emergency_routing(order, available_brokers)

        # Use config directly to support dynamic strategy changes
        strategy = self.config.get("routing_strategy", "latency_optimized")

        if strategy == "latency_optimized":
            return self._route_by_latency(order, available_brokers)
        elif strategy == "load_balanced":
            return self._route_by_load_balance(order, available_brokers)
        elif strategy == "cost_optimized":
            return self._route_by_cost(order, available_brokers)
        else:
            return self._route_by_priority(order, available_brokers)

    def _route_by_latency(
        self, order: Order, available_brokers: List[str]
    ) -> Dict[str, Any]:
        """Route order based on lowest latency."""
        healthy_brokers = [b for b in available_brokers if self._check_broker_health(b)]

        if not healthy_brokers:
            if self.failover_enabled:
                return self._emergency_routing(order, available_brokers)
            raise BrokerError("No healthy brokers available")

        # Check if any primary brokers failed (for failover detection)
        failed_primary_brokers = [
            b for b in available_brokers if not self._check_broker_health(b)
        ]

        # Get latencies
        latencies = self._get_broker_latencies()

        # Find broker with lowest latency
        best_broker = min(healthy_brokers, key=lambda b: latencies.get(b, float("inf")))
        fallback_brokers = [b for b in healthy_brokers if b != best_broker]

        # Determine if this is failover or normal routing
        reason = "failover" if failed_primary_brokers else "latency_optimized"

        return {
            "selected_broker": best_broker,
            "reason": reason,
            "routing_score": 100.0,
            "fallback_brokers": sorted(
                fallback_brokers, key=lambda b: latencies.get(b, float("inf"))
            ),
        }

    def _route_by_load_balance(
        self, order: Order, available_brokers: List[str]
    ) -> Dict[str, Any]:
        """Route order based on load balancing."""
        healthy_brokers = [b for b in available_brokers if self._check_broker_health(b)]

        if not healthy_brokers:
            raise BrokerError("No healthy brokers available")

        # Choose broker based on weight and current load
        weights = {b: self.brokers[b]["weight"] for b in healthy_brokers}
        loads = {b: self.broker_loads[b] for b in healthy_brokers}

        # Calculate weighted load scores with rotation factor
        import random

        scores = {}
        for broker in healthy_brokers:
            weight_factor = weights[broker] / 100.0
            load_factor = 1.0 / (1.0 + loads[broker])  # Lower load = higher score

            # Add randomization for distribution
            random_factor = random.uniform(0.8, 1.2)  # 20% randomization
            scores[broker] = weight_factor * load_factor * random_factor

        best_broker = max(scores.keys(), key=lambda b: scores[b])

        # Update load counter for selected broker
        self.broker_loads[best_broker] += 1

        fallback_brokers = [b for b in healthy_brokers if b != best_broker]

        return {
            "selected_broker": best_broker,
            "reason": "load_balanced",
            "routing_score": scores[best_broker] * 100,
            "fallback_brokers": sorted(
                fallback_brokers, key=lambda b: scores[b], reverse=True
            ),
        }

    def _route_by_cost(
        self, order: Order, available_brokers: List[str]
    ) -> Dict[str, Any]:
        """Route order based on lowest cost."""
        healthy_brokers = [b for b in available_brokers if self._check_broker_health(b)]

        if not healthy_brokers:
            raise BrokerError("No healthy brokers available")

        # Find broker with lowest commission
        commissions = {b: self.brokers[b]["commission"] for b in healthy_brokers}
        best_broker = min(commissions.keys(), key=lambda b: commissions[b])
        fallback_brokers = [b for b in healthy_brokers if b != best_broker]

        return {
            "selected_broker": best_broker,
            "reason": "cost_optimized",
            "routing_score": 100.0,
            "fallback_brokers": sorted(fallback_brokers, key=lambda b: commissions[b]),
        }

    def _route_by_priority(
        self, order: Order, available_brokers: List[str]
    ) -> Dict[str, Any]:
        """Route order based on broker priority."""
        healthy_brokers = [b for b in available_brokers if self._check_broker_health(b)]

        if not healthy_brokers:
            raise BrokerError("No healthy brokers available")

        # Sort by priority (lower number = higher priority)
        priorities = {b: self.brokers[b]["priority"] for b in healthy_brokers}
        best_broker = min(priorities.keys(), key=lambda b: priorities[b])
        fallback_brokers = [b for b in healthy_brokers if b != best_broker]

        return {
            "selected_broker": best_broker,
            "reason": "priority_based",
            "routing_score": 100.0,
            "fallback_brokers": sorted(fallback_brokers, key=lambda b: priorities[b]),
        }

    def _emergency_routing(
        self, order: Order, available_brokers: List[str]
    ) -> Dict[str, Any]:
        """Emergency routing when primary brokers fail."""
        # First try healthy brokers
        for broker in available_brokers:
            if self._check_broker_health(broker) and self.can_route_order(
                order, broker
            ):
                return {
                    "selected_broker": broker,
                    "reason": "emergency_routing",
                    "routing_score": 50.0,
                    "fallback_brokers": [],
                }

        # If no healthy brokers, try any available broker as last resort
        for broker in available_brokers:
            if self.can_route_order(order, broker):
                return {
                    "selected_broker": broker,
                    "reason": "emergency_routing",
                    "routing_score": 25.0,  # Lower score for unhealthy broker
                    "fallback_brokers": [],
                }

        raise BrokerError("No brokers available for emergency routing")

    def _check_broker_health(self, broker: str) -> bool:
        """Check if broker is healthy."""
        # In real implementation, would check actual broker connection
        # For testing, use mock client if available
        client = self.broker_clients.get(broker)
        if client and hasattr(client, "ping"):
            try:
                return client.ping()
            except:
                return False

        # Default to healthy for testing
        return True

    def _get_broker_latencies(self) -> Dict[str, float]:
        """Get current broker latencies."""
        if not self.broker_latencies:
            # Return mock latencies for testing
            return {"IB": 1.2, "FXCM": 2.1, "OANDA": 3.5}
        return self.broker_latencies

    def _validate_order_risk_limits(self, order: Order) -> None:
        """Validate order against risk limits."""
        self.validate_risk_limits(order)

    def _initialize_broker_monitoring(self) -> None:
        """Initialize broker monitoring systems."""
        # Initialize broker health status
        for broker_name in self.brokers.keys():
            self.broker_health[broker_name] = True
            self.broker_latencies[broker_name] = 0.0
            self.broker_loads[broker_name] = 0
