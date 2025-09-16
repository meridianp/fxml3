"""
Enhanced Trade Execution Engine with Phase 5 Enhancements.

This module extends the existing execution engine with advanced features including:
- Enhanced order lifecycle management with comprehensive tracking
- Intelligent multi-broker routing with real-time optimization
- Advanced performance monitoring and circuit breaker protection
- Comprehensive integration with Phase 4 authentication and compliance

This serves as the main orchestrator for all Phase 5 trading operations.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Set

from ..core.exceptions import FXMLError
from ..core.logging import get_logger
from ..fix.messages.orders import NewOrderSingle
from .enhanced_message_router import CircuitBreakerStatus, EnhancedMessageRouter
from .enhanced_order_lifecycle import (
    OrderLifecycleManager,
    OrderLifecycleStatus,
    OrderTracker,
)
from .execution_engine import TradeExecutionEngine
from .intelligent_routing_engine import FailoverResult, IntelligentRoutingEngine

logger = get_logger(__name__)


@dataclass
class SystemHealthMetrics:
    """System health metrics for monitoring."""

    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    active_connections: int = 0
    queue_depth: int = 0
    error_rate_percent: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ThroughputMetrics:
    """Throughput metrics for capacity management."""

    orders_per_second: float = 0.0
    current_load: int = 0
    max_capacity: int = 1000
    queue_backlog: int = 0
    processing_latency_ms: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def utilization_percent(self) -> float:
        """Calculate current utilization percentage."""
        if self.max_capacity == 0:
            return 0.0
        return (self.current_load / self.max_capacity) * 100


class EnhancedExecutionEngineError(FXMLError):
    """Exception raised for enhanced execution engine errors."""

    pass


class EnhancedExecutionEngine:
    """Enhanced execution engine with Phase 5 capabilities."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize enhanced execution engine."""
        self.config = config

        # Core components
        self.lifecycle_manager = OrderLifecycleManager(config.get("lifecycle", {}))
        self.routing_engine: Optional[IntelligentRoutingEngine] = None
        self.message_router: Optional[EnhancedMessageRouter] = None
        self.base_execution_engine: Optional[TradeExecutionEngine] = None

        # Configuration
        self.max_concurrent_orders = config.get("max_concurrent_orders", 1000)
        self.order_timeout_seconds = config.get("order_timeout_seconds", 300)
        self.enable_performance_monitoring = config.get(
            "enable_performance_monitoring", True
        )
        self.enable_intelligent_routing = config.get("enable_intelligent_routing", True)
        self.circuit_breaker_threshold = config.get("circuit_breaker_threshold", 10)

        # Performance monitoring
        self.performance_enabled = False
        self.throughput_metrics = ThroughputMetrics(
            max_capacity=self.max_concurrent_orders
        )
        self.system_health_metrics = SystemHealthMetrics()

        # Circuit breaker
        self.circuit_breaker_failures = 0
        self.circuit_breaker_open = False
        self.circuit_breaker_last_failure: Optional[datetime] = None

        # State management
        self.is_initialized = False
        self.active_orders: Set[str] = set()
        self.execution_metrics = {
            "total_orders_submitted": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time_ms": 0.0,
        }

        self.lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the enhanced execution engine."""
        try:
            # Initialize core components
            (
                await self.lifecycle_manager.initialize()
                if hasattr(self.lifecycle_manager, "initialize")
                else None
            )

            # Initialize routing engine if enabled
            if self.enable_intelligent_routing:
                self.routing_engine = IntelligentRoutingEngine(
                    self.config.get("routing", {})
                )
                await self.routing_engine.initialize()

            # Initialize message router
            self.message_router = EnhancedMessageRouter(
                self.config.get("messaging", {})
            )
            await self.message_router.initialize()

            # Initialize base execution engine
            self.base_execution_engine = TradeExecutionEngine(self.config)
            # Note: base engine initialization would be called if it exists

            # Enable performance monitoring
            if self.enable_performance_monitoring:
                await self.enable_performance_monitoring_async()

            self.is_initialized = True
            logger.info("Enhanced execution engine initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize enhanced execution engine: {e}")
            raise EnhancedExecutionEngineError(f"Initialization failed: {e}")

    async def enable_performance_monitoring_async(self):
        """Enable performance monitoring."""
        self.performance_enabled = True

        # Start monitoring tasks
        asyncio.create_task(self._performance_monitoring_loop())
        asyncio.create_task(self._throughput_monitoring_loop())

        logger.info("Performance monitoring enabled")

    async def submit_order_with_tracking(
        self,
        order: NewOrderSingle,
        user_id: str,
        enable_performance_tracking: bool = True,
    ) -> str:
        """Submit order with comprehensive tracking."""
        if not self.is_initialized:
            raise EnhancedExecutionEngineError("Engine not initialized")

        # Check circuit breaker
        if self.circuit_breaker_open:
            raise EnhancedExecutionEngineError("circuit_breaker_open")

        # start_time = time.time()  # Reserved for performance tracking

        try:
            async with self.lock:
                # Check capacity
                if len(self.active_orders) >= self.max_concurrent_orders:
                    raise EnhancedExecutionEngineError("Maximum capacity exceeded")

            # Create order tracker
            tracking_id = await self.lifecycle_manager.create_order_tracker(
                client_order_id=order.cl_ord_id,
                user_id=user_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.order_qty,
                order_type=order.ord_type,
                price=getattr(order, "price", None),
            )

            # Add to active orders
            async with self.lock:
                self.active_orders.add(tracking_id)
                self.throughput_metrics.current_load += 1

            # Update metrics
            self.execution_metrics["total_orders_submitted"] += 1

            logger.info(f"Order {tracking_id} submitted for tracking")
            return tracking_id

        except Exception as e:
            await self._handle_circuit_breaker_failure()
            raise EnhancedExecutionEngineError(f"Failed to submit order: {e}")

    async def submit_order_with_full_pipeline(
        self, order: NewOrderSingle, user_id: str
    ) -> str:
        """Submit order through the full Phase 5 pipeline."""
        # Stage 1: Create comprehensive tracking
        tracking_id = await self.submit_order_with_tracking(order, user_id)

        # Stage 2: Intelligent routing
        if self.routing_engine:
            order_data = self._order_to_dict(order, user_id)
            routing_decision = await self.routing_engine.get_optimal_broker_routing(
                order_data
            )

            # Update tracker with routing info
            tracker = await self.lifecycle_manager.get_order_tracker(tracking_id)
            if tracker:
                tracker.selected_broker = routing_decision.primary_broker
                tracker.routing_strategy = routing_decision.routing_strategy.value
                tracker.broker_routing_history = [
                    routing_decision.primary_broker
                ] + routing_decision.fallback_brokers

        # Stage 3: Update status to routing
        await self.update_order_status(tracking_id, OrderLifecycleStatus.ROUTING)

        # Stage 4: Route through message queue
        if self.message_router:
            _ = await self.message_router.route_order_message(
                order_data
            )  # Routing complete

        # Stage 5: Update to submitted
        await self.update_order_status(tracking_id, OrderLifecycleStatus.SUBMITTED)

        return tracking_id

    def _order_to_dict(self, order: NewOrderSingle, user_id: str) -> Dict[str, Any]:
        """Convert order to dictionary for routing."""
        return {
            "client_order_id": order.cl_ord_id,
            "symbol": order.symbol,
            "side": (
                order.side.value if hasattr(order.side, "value") else str(order.side)
            ),
            "quantity": float(order.order_qty),
            "order_type": (
                order.ord_type.value
                if hasattr(order.ord_type, "value")
                else str(order.ord_type)
            ),
            "price": (
                float(getattr(order, "price", 0)) if hasattr(order, "price") else None
            ),
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_order_tracker(self, tracking_id: str) -> Optional[OrderTracker]:
        """Get order tracker by ID."""
        return await self.lifecycle_manager.get_order_tracker(tracking_id)

    async def update_order_status(
        self,
        tracking_id: str,
        new_status: OrderLifecycleStatus,
        broker_order_id: Optional[str] = None,
        filled_quantity: Optional[Decimal] = None,
        average_price: Optional[Decimal] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update order status with comprehensive logging."""
        success = await self.lifecycle_manager.update_order_status(
            tracking_id=tracking_id,
            new_status=new_status,
            broker_order_id=broker_order_id,
            filled_quantity=filled_quantity,
            average_price=average_price,
            error_message=error_message,
        )

        # Handle terminal states
        if success:
            tracker = await self.get_order_tracker(tracking_id)
            if tracker and tracker.is_terminal_state:
                await self._handle_order_completion(tracking_id, tracker)

        return success

    async def _handle_order_completion(self, tracking_id: str, tracker: OrderTracker):
        """Handle order completion and cleanup."""
        async with self.lock:
            self.active_orders.discard(tracking_id)
            self.throughput_metrics.current_load = max(
                0, self.throughput_metrics.current_load - 1
            )

        # Update success metrics
        if tracker.status == OrderLifecycleStatus.FILLED:
            self.execution_metrics["successful_executions"] += 1
        else:
            self.execution_metrics["failed_executions"] += 1

        # Log completion
        logger.info(f"Order {tracking_id} completed with status {tracker.status.value}")

    async def simulate_broker_acknowledgment(self, tracking_id: str, latency_ms: int):
        """Simulate broker acknowledgment for testing."""
        await asyncio.sleep(latency_ms / 1000.0)  # Convert to seconds
        await self.update_order_status(
            tracking_id,
            OrderLifecycleStatus.ACKNOWLEDGED,
            broker_order_id=f"BROKER_{tracking_id[:8]}",
        )

    async def simulate_broker_rejection(self, tracking_id: str, reason: str):
        """Simulate broker rejection for testing."""
        await self.update_order_status(
            tracking_id, OrderLifecycleStatus.REJECTED, error_message=reason
        )
        await self._handle_circuit_breaker_failure()

    async def simulate_full_execution_cycle(
        self, tracking_id: str, fill_price: Decimal, execution_time_ms: int
    ):
        """Simulate complete execution cycle for testing."""
        # Stage 1: Acknowledge
        await self.update_order_status(
            tracking_id,
            OrderLifecycleStatus.ACKNOWLEDGED,
            broker_order_id=f"BROKER_{tracking_id[:8]}",
        )

        # Stage 2: Working
        await asyncio.sleep(0.05)  # 50ms delay
        await self.update_order_status(tracking_id, OrderLifecycleStatus.WORKING)

        # Stage 3: Fill
        await asyncio.sleep(execution_time_ms / 1000.0)
        tracker = await self.get_order_tracker(tracking_id)
        if tracker:
            await self.update_order_status(
                tracking_id,
                OrderLifecycleStatus.FILLED,
                filled_quantity=tracker.quantity,
                average_price=fill_price,
            )

    async def get_order_routing_info(
        self, tracking_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get routing information for an order."""
        tracker = await self.get_order_tracker(tracking_id)
        if not tracker:
            return None

        return {
            "selected_broker": tracker.selected_broker,
            "routing_strategy": tracker.routing_strategy,
            "routing_attempts": tracker.routing_attempts,
            "broker_routing_history": tracker.broker_routing_history,
        }

    async def get_order_performance_metrics(
        self, tracking_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get performance metrics for an order."""
        tracker = await self.get_order_tracker(tracking_id)
        if not tracker or not tracker.performance_metrics:
            return None

        metrics = tracker.performance_metrics
        return {
            "acknowledgment_latency_ms": metrics.acknowledgment_latency_ms,
            "total_execution_time_ms": metrics.total_execution_time_ms,
            "routing_time_ms": metrics.routing_time_ms,
            "broker_processing_time_ms": metrics.broker_processing_time_ms,
            "retry_count": metrics.retry_count,
            "submission_timestamp": metrics.submission_timestamp.isoformat(),
            "completion_timestamp": (
                metrics.completion_timestamp.isoformat()
                if metrics.completion_timestamp
                else None
            ),
        }

    async def get_execution_metrics(self, tracking_id: str) -> Dict[str, Any]:
        """Get execution metrics for an order."""
        performance_metrics = await self.get_order_performance_metrics(tracking_id)
        routing_info = await self.get_order_routing_info(tracking_id)

        return {
            "tracking_id": tracking_id,
            "performance_metrics": performance_metrics,
            "routing_info": routing_info,
            "total_execution_time_ms": (
                performance_metrics.get("total_execution_time_ms")
                if performance_metrics
                else None
            ),
            "routing_time_ms": (
                performance_metrics.get("routing_time_ms")
                if performance_metrics
                else None
            ),
            "broker_processing_time_ms": (
                performance_metrics.get("broker_processing_time_ms")
                if performance_metrics
                else None
            ),
        }

    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        return await self.lifecycle_manager.get_performance_summary()

    async def get_throughput_metrics(self) -> ThroughputMetrics:
        """Get current throughput metrics."""
        return self.throughput_metrics

    async def get_circuit_breaker_status(self) -> CircuitBreakerStatus:
        """Get circuit breaker status."""
        return CircuitBreakerStatus(
            failure_count=self.circuit_breaker_failures,
            last_failure_time=self.circuit_breaker_last_failure,
            is_open=self.circuit_breaker_open,
        )

    async def get_system_health_metrics(self) -> SystemHealthMetrics:
        """Get system health metrics."""
        return self.system_health_metrics

    async def trigger_broker_failover(self, tracking_id: str) -> FailoverResult:
        """Trigger broker failover for an order."""
        if not self.routing_engine:
            raise EnhancedExecutionEngineError("Intelligent routing not enabled")

        return await self.routing_engine.trigger_broker_failover(tracking_id)

    async def _handle_circuit_breaker_failure(self):
        """Handle circuit breaker failure."""
        async with self.lock:
            self.circuit_breaker_failures += 1
            self.circuit_breaker_last_failure = datetime.now(timezone.utc)

            if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
                self.circuit_breaker_open = True
                logger.warning("Circuit breaker OPEN - rejecting new orders")

                # Schedule circuit breaker reset
                asyncio.create_task(self._reset_circuit_breaker_after_timeout())

    async def _reset_circuit_breaker_after_timeout(self, timeout_seconds: int = 60):
        """Reset circuit breaker after timeout period."""
        await asyncio.sleep(timeout_seconds)

        async with self.lock:
            self.circuit_breaker_open = False
            self.circuit_breaker_failures = 0
            self.circuit_breaker_last_failure = None
            logger.info("Circuit breaker CLOSED - accepting orders")

    async def _performance_monitoring_loop(self):
        """Background loop for performance monitoring."""
        while self.performance_enabled:
            try:
                await self._update_system_health_metrics()
                await asyncio.sleep(30)  # Update every 30 seconds
            except Exception as e:
                logger.error(f"Error in performance monitoring loop: {e}")
                await asyncio.sleep(5)

    async def _throughput_monitoring_loop(self):
        """Background loop for throughput monitoring."""
        last_order_count = 0

        while self.performance_enabled:
            try:
                # current_time = time.time()  # Reserved for future timing metrics
                current_count = self.execution_metrics["total_orders_submitted"]

                # Calculate orders per second
                time_diff = 1.0  # 1 second window
                orders_diff = current_count - last_order_count

                self.throughput_metrics.orders_per_second = orders_diff / time_diff
                self.throughput_metrics.queue_backlog = len(self.active_orders)
                self.throughput_metrics.last_updated = datetime.now(timezone.utc)

                last_order_count = current_count

                await asyncio.sleep(1)  # Update every second
            except Exception as e:
                logger.error(f"Error in throughput monitoring loop: {e}")
                await asyncio.sleep(5)

    async def _update_system_health_metrics(self):
        """Update system health metrics."""
        # In production, these would be real system metrics
        self.system_health_metrics.active_connections = len(self.active_orders)
        self.system_health_metrics.queue_depth = self.throughput_metrics.queue_backlog

        # Calculate error rate
        total_orders = self.execution_metrics["total_orders_submitted"]
        failed_orders = self.execution_metrics["failed_executions"]

        if total_orders > 0:
            self.system_health_metrics.error_rate_percent = (
                failed_orders / total_orders
            ) * 100

        self.system_health_metrics.last_updated = datetime.now(timezone.utc)

    async def shutdown(self):
        """Gracefully shutdown the execution engine."""
        try:
            self.performance_enabled = False

            # Shutdown components
            if self.message_router:
                await self.message_router.shutdown()

            # Wait for active orders to complete or timeout
            timeout = 30  # 30 seconds
            start_time = time.time()

            while self.active_orders and (time.time() - start_time) < timeout:
                await asyncio.sleep(1)

            if self.active_orders:
                logger.warning(f"Shutdown with {len(self.active_orders)} active orders")

            logger.info("Enhanced execution engine shut down successfully")

        except Exception as e:
            logger.error(f"Error during execution engine shutdown: {e}")


# Factory function
def create_enhanced_execution_engine(config: Dict[str, Any]) -> EnhancedExecutionEngine:
    """Create enhanced execution engine instance."""
    return EnhancedExecutionEngine(config)
