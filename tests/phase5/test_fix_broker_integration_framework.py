"""
Test-Driven Development for Phase 5: FIX Protocol & Broker Integration Framework.

This module tests the enhanced broker integration system including:
- Multi-broker intelligent routing with failover
- Enhanced order lifecycle management and tracking
- Real-time performance monitoring and optimization
- Advanced RabbitMQ routing with error handling
- Comprehensive broker adapter validation
- Production-ready FIX protocol integration

Following TDD methodology: Red → Green → Refactor
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest

from fxml4.brokers.adapters.base import (
    AdapterConfig,
    BrokerAdapter,
    ConnectionStatus,
    OrderInfo,
)
from fxml4.brokers.adapters.manager import BrokerAdapterManager
from fxml4.brokers.execution_engine import ExecutionEngine
from fxml4.brokers.messaging.router import MessageRouter, RoutingStrategy
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle
from fxml4.fix.session_manager import SessionManager


# Phase 5 Test Fixtures
@pytest.fixture
async def enhanced_execution_engine():
    """Create enhanced execution engine for Phase 5 testing."""
    config = {
        "max_concurrent_orders": 1000,
        "order_timeout_seconds": 300,
        "enable_performance_monitoring": True,
        "enable_intelligent_routing": True,
        "failover_detection_threshold": 3,
        "circuit_breaker_threshold": 10,
    }

    engine = ExecutionEngine(config)
    await engine.initialize()
    return engine


@pytest.fixture
async def multi_broker_manager():
    """Create multi-broker manager with Phase 5 enhancements."""
    config = {
        "brokers": {
            "ib": {"priority": 1, "max_capacity": 50},
            "fxcm": {"priority": 2, "max_capacity": 100},
            "manual": {"priority": 3, "max_capacity": 10},
        },
        "enable_load_balancing": True,
        "enable_failover": True,
        "health_check_interval": 5,
    }

    manager = BrokerAdapterManager(config)
    await manager.initialize()
    return manager


@pytest.fixture
def sample_order_request():
    """Create a sample order request for testing."""
    return {
        "client_order_id": str(uuid.uuid4()),
        "symbol": "EURUSD",
        "side": Side.BUY,
        "quantity": Decimal("100000"),
        "order_type": OrdType.MARKET,
        "time_in_force": TimeInForce.IOC,
        "account_id": "test_account",
        "user_id": "test_user",
    }


# Phase 5 Enhanced Order Lifecycle Management Tests
class TestPhase5OrderLifecycleManagement:
    """Test enhanced order lifecycle management system."""

    async def test_comprehensive_order_tracking(
        self,
        enhanced_execution_engine: ExecutionEngine,
        sample_order_request: Dict[str, Any],
    ):
        """Test comprehensive order tracking across the full lifecycle."""
        # Create new order with enhanced tracking
        order = NewOrderSingle(
            cl_ord_id=sample_order_request["client_order_id"],
            symbol=sample_order_request["symbol"],
            side=sample_order_request["side"],
            transact_time=datetime.now(timezone.utc),
            ord_type=sample_order_request["order_type"],
            order_qty=sample_order_request["quantity"],
        )

        # Submit order and track lifecycle
        tracking_id = await enhanced_execution_engine.submit_order_with_tracking(
            order, sample_order_request["user_id"]
        )

        # Verify tracking record creation
        assert tracking_id is not None
        order_tracker = await enhanced_execution_engine.get_order_tracker(tracking_id)
        assert order_tracker is not None
        assert order_tracker.status == "SUBMITTED"
        assert order_tracker.created_at is not None
        assert order_tracker.user_id == sample_order_request["user_id"]

    async def test_order_state_transitions_validation(
        self,
        enhanced_execution_engine: ExecutionEngine,
        sample_order_request: Dict[str, Any],
    ):
        """Test validation of order state transitions."""
        order = NewOrderSingle(
            cl_ord_id=sample_order_request["client_order_id"],
            symbol=sample_order_request["symbol"],
            side=sample_order_request["side"],
            transact_time=datetime.now(timezone.utc),
            ord_type=sample_order_request["order_type"],
            order_qty=sample_order_request["quantity"],
        )

        tracking_id = await enhanced_execution_engine.submit_order_with_tracking(
            order, sample_order_request["user_id"]
        )

        # Test valid state transition: SUBMITTED -> ACKNOWLEDGED
        await enhanced_execution_engine.update_order_status(
            tracking_id, "ACKNOWLEDGED", broker_order_id="BROKER123"
        )

        tracker = await enhanced_execution_engine.get_order_tracker(tracking_id)
        assert tracker.status == "ACKNOWLEDGED"
        assert tracker.broker_order_id == "BROKER123"

        # Test valid state transition: ACKNOWLEDGED -> PARTIALLY_FILLED
        await enhanced_execution_engine.update_order_status(
            tracking_id,
            "PARTIALLY_FILLED",
            filled_quantity=Decimal("50000"),
            average_price=Decimal("1.1234"),
        )

        tracker = await enhanced_execution_engine.get_order_tracker(tracking_id)
        assert tracker.status == "PARTIALLY_FILLED"
        assert tracker.filled_quantity == Decimal("50000")
        assert tracker.average_price == Decimal("1.1234")

    async def test_order_performance_metrics_tracking(
        self,
        enhanced_execution_engine: ExecutionEngine,
        sample_order_request: Dict[str, Any],
    ):
        """Test order performance metrics collection."""
        order = NewOrderSingle(
            cl_ord_id=sample_order_request["client_order_id"],
            symbol=sample_order_request["symbol"],
            side=sample_order_request["side"],
            transact_time=datetime.now(timezone.utc),
            ord_type=sample_order_request["order_type"],
            order_qty=sample_order_request["quantity"],
        )

        # Submit with performance tracking enabled
        tracking_id = await enhanced_execution_engine.submit_order_with_tracking(
            order, sample_order_request["user_id"], enable_performance_tracking=True
        )

        # Simulate acknowledgment latency
        await asyncio.sleep(0.1)  # 100ms latency simulation
        await enhanced_execution_engine.update_order_status(
            tracking_id, "ACKNOWLEDGED", broker_order_id="BROKER123"
        )

        # Verify performance metrics
        metrics = await enhanced_execution_engine.get_order_performance_metrics(
            tracking_id
        )
        assert metrics is not None
        assert metrics.acknowledgment_latency_ms >= 100
        assert metrics.submission_timestamp is not None
        assert metrics.acknowledgment_timestamp is not None


# Phase 5 Multi-Broker Intelligent Routing Tests
class TestPhase5IntelligentRouting:
    """Test intelligent multi-broker routing system."""

    async def test_intelligent_broker_selection(
        self,
        multi_broker_manager: BrokerAdapterManager,
        sample_order_request: Dict[str, Any],
    ):
        """Test intelligent broker selection based on order characteristics."""
        # Test routing for large FX order (should prefer FXCM)
        large_fx_order = sample_order_request.copy()
        large_fx_order["symbol"] = "EURUSD"
        large_fx_order["quantity"] = Decimal("1000000")  # $1M order

        routing_decision = await multi_broker_manager.get_optimal_broker_routing(
            large_fx_order
        )

        assert routing_decision is not None
        assert routing_decision.primary_broker == "fxcm"  # Best for large FX
        assert "ib" in routing_decision.fallback_brokers
        assert routing_decision.routing_reason == "large_fx_optimization"

    async def test_load_balancing_across_brokers(
        self,
        multi_broker_manager: BrokerAdapterManager,
        sample_order_request: Dict[str, Any],
    ):
        """Test load balancing across multiple brokers."""
        # Submit multiple orders to test load distribution
        orders = []
        routing_decisions = []

        for i in range(10):
            order = sample_order_request.copy()
            order["client_order_id"] = str(uuid.uuid4())

            routing = await multi_broker_manager.get_optimal_broker_routing(order)
            routing_decisions.append(routing.primary_broker)
            orders.append(order)

        # Verify load balancing (should not all go to same broker)
        unique_brokers = set(routing_decisions)
        assert (
            len(unique_brokers) > 1
        ), "Load balancing should distribute across brokers"

        # Verify broker capacity is considered
        broker_counts = {}
        for broker in routing_decisions:
            broker_counts[broker] = broker_counts.get(broker, 0) + 1

        # No broker should exceed capacity limits
        for broker, count in broker_counts.items():
            max_capacity = multi_broker_manager.config["brokers"][broker][
                "max_capacity"
            ]
            assert count <= max_capacity

    async def test_failover_mechanism(
        self,
        multi_broker_manager: BrokerAdapterManager,
        sample_order_request: Dict[str, Any],
    ):
        """Test automatic failover when primary broker fails."""
        # Simulate primary broker failure
        await multi_broker_manager.mark_broker_as_failed("ib", "connection_timeout")

        # Submit order - should automatically route to backup
        routing = await multi_broker_manager.get_optimal_broker_routing(
            sample_order_request
        )

        assert routing.primary_broker != "ib"  # Should failover from IB
        assert routing.primary_broker in ["fxcm", "manual"]
        assert routing.routing_reason == "failover_from_ib"

        # Verify failed broker marked appropriately
        broker_status = await multi_broker_manager.get_broker_status("ib")
        assert broker_status.connection_status == ConnectionStatus.ERROR
        assert broker_status.failure_reason == "connection_timeout"


# Phase 5 Performance Monitoring Tests
class TestPhase5PerformanceMonitoring:
    """Test real-time performance monitoring system."""

    async def test_real_time_latency_monitoring(
        self,
        enhanced_execution_engine: ExecutionEngine,
        sample_order_request: Dict[str, Any],
    ):
        """Test real-time order latency monitoring."""
        # Enable latency monitoring
        await enhanced_execution_engine.enable_performance_monitoring()

        # Submit orders with different latency profiles
        fast_order = sample_order_request.copy()
        fast_order["client_order_id"] = str(uuid.uuid4())

        slow_order = sample_order_request.copy()
        slow_order["client_order_id"] = str(uuid.uuid4())

        # Submit and track latencies
        fast_tracking_id = await enhanced_execution_engine.submit_order_with_tracking(
            NewOrderSingle.from_dict(fast_order), sample_order_request["user_id"]
        )

        # Simulate fast acknowledgment
        await enhanced_execution_engine.simulate_broker_acknowledgment(
            fast_tracking_id, latency_ms=50
        )

        slow_tracking_id = await enhanced_execution_engine.submit_order_with_tracking(
            NewOrderSingle.from_dict(slow_order), sample_order_request["user_id"]
        )

        # Simulate slow acknowledgment
        await enhanced_execution_engine.simulate_broker_acknowledgment(
            slow_tracking_id, latency_ms=500
        )

        # Verify latency metrics
        performance_summary = await enhanced_execution_engine.get_performance_summary()
        assert performance_summary.average_acknowledgment_latency_ms > 0
        assert (
            performance_summary.p95_acknowledgment_latency_ms
            > performance_summary.p50_acknowledgment_latency_ms
        )
        assert performance_summary.total_orders_processed >= 2

    async def test_throughput_monitoring(
        self,
        enhanced_execution_engine: ExecutionEngine,
        sample_order_request: Dict[str, Any],
    ):
        """Test throughput monitoring and capacity management."""
        # Submit burst of orders
        order_ids = []
        start_time = datetime.now(timezone.utc)

        for i in range(20):
            order = sample_order_request.copy()
            order["client_order_id"] = str(uuid.uuid4())

            tracking_id = await enhanced_execution_engine.submit_order_with_tracking(
                NewOrderSingle.from_dict(order), sample_order_request["user_id"]
            )
            order_ids.append(tracking_id)

        end_time = datetime.now(timezone.utc)

        # Verify throughput metrics
        throughput_metrics = await enhanced_execution_engine.get_throughput_metrics()
        time_window = (end_time - start_time).total_seconds()

        assert throughput_metrics.orders_per_second > 0
        assert throughput_metrics.current_load <= throughput_metrics.max_capacity
        assert len(order_ids) == 20

    async def test_circuit_breaker_mechanism(
        self,
        enhanced_execution_engine: ExecutionEngine,
        sample_order_request: Dict[str, Any],
    ):
        """Test circuit breaker for broker protection."""
        # Simulate high error rate to trigger circuit breaker
        for i in range(15):  # Exceeds circuit_breaker_threshold of 10
            order = sample_order_request.copy()
            order["client_order_id"] = str(uuid.uuid4())

            tracking_id = await enhanced_execution_engine.submit_order_with_tracking(
                NewOrderSingle.from_dict(order), sample_order_request["user_id"]
            )

            # Simulate broker rejection
            await enhanced_execution_engine.simulate_broker_rejection(
                tracking_id, "insufficient_funds"
            )

        # Verify circuit breaker is triggered
        circuit_status = await enhanced_execution_engine.get_circuit_breaker_status()
        assert circuit_status.is_open is True
        assert circuit_status.failure_count >= 10
        assert circuit_status.last_failure_time is not None

        # New orders should be rejected while circuit is open
        test_order = sample_order_request.copy()
        test_order["client_order_id"] = str(uuid.uuid4())

        with pytest.raises(Exception) as exc_info:
            await enhanced_execution_engine.submit_order_with_tracking(
                NewOrderSingle.from_dict(test_order), sample_order_request["user_id"]
            )

        assert "circuit_breaker_open" in str(exc_info.value)


# Phase 5 Advanced RabbitMQ Routing Tests
class TestPhase5RabbitMQRouting:
    """Test advanced RabbitMQ routing and error handling."""

    @pytest.fixture
    async def message_router(self):
        """Create enhanced message router for testing."""
        config = {
            "enable_dead_letter_queue": True,
            "max_retry_attempts": 3,
            "retry_backoff_multiplier": 2.0,
            "enable_priority_routing": True,
            "enable_message_durability": True,
        }

        router = MessageRouter(config)
        await router.initialize()
        return router

    async def test_priority_message_routing(
        self, message_router: MessageRouter, sample_order_request: Dict[str, Any]
    ):
        """Test priority-based message routing."""
        # Create high priority order (large size)
        high_priority_order = sample_order_request.copy()
        high_priority_order["quantity"] = Decimal("10000000")  # $10M order
        high_priority_order["priority"] = "HIGH"

        # Create normal priority order
        normal_priority_order = sample_order_request.copy()
        normal_priority_order["client_order_id"] = str(uuid.uuid4())
        normal_priority_order["priority"] = "NORMAL"

        # Submit orders
        high_priority_routing = await message_router.route_order_message(
            high_priority_order
        )
        normal_priority_routing = await message_router.route_order_message(
            normal_priority_order
        )

        # Verify priority routing
        assert (
            high_priority_routing.queue_priority
            > normal_priority_routing.queue_priority
        )
        assert high_priority_routing.routing_key.startswith("orders.high_priority")
        assert normal_priority_routing.routing_key.startswith("orders.normal")

    async def test_dead_letter_queue_handling(
        self, message_router: MessageRouter, sample_order_request: Dict[str, Any]
    ):
        """Test dead letter queue for failed messages."""
        # Create order that will fail processing
        failing_order = sample_order_request.copy()
        failing_order["symbol"] = "INVALID_SYMBOL"
        failing_order["client_order_id"] = str(uuid.uuid4())

        # Submit order and simulate processing failures
        routing_info = await message_router.route_order_message(failing_order)

        # Simulate multiple processing failures
        for attempt in range(4):  # Exceeds max_retry_attempts of 3
            await message_router.handle_processing_failure(
                routing_info.message_id,
                f"processing_error_attempt_{attempt}",
                attempt + 1,
            )

        # Verify message moved to dead letter queue
        dlq_status = await message_router.check_dead_letter_queue_status(
            routing_info.message_id
        )
        assert dlq_status.is_in_dlq is True
        assert dlq_status.retry_attempts == 3
        assert dlq_status.final_error is not None

    async def test_message_durability_and_recovery(
        self, message_router: MessageRouter, sample_order_request: Dict[str, Any]
    ):
        """Test message durability and recovery mechanisms."""
        # Submit durable order message
        durable_order = sample_order_request.copy()
        durable_order["client_order_id"] = str(uuid.uuid4())
        durable_order["require_durability"] = True

        routing_info = await message_router.route_order_message(durable_order)

        # Simulate system restart/recovery
        await message_router.simulate_system_restart()

        # Verify message recovery
        recovered_messages = await message_router.recover_pending_messages()
        recovered_order_ids = [msg["client_order_id"] for msg in recovered_messages]

        assert durable_order["client_order_id"] in recovered_order_ids
        assert len(recovered_messages) > 0


# Phase 5 Integration Validation Tests
class TestPhase5IntegrationValidation:
    """Test comprehensive integration validation."""

    async def test_end_to_end_order_flow(
        self,
        enhanced_execution_engine: ExecutionEngine,
        multi_broker_manager: BrokerAdapterManager,
        sample_order_request: Dict[str, Any],
    ):
        """Test complete end-to-end order processing flow."""
        # Submit order through full Phase 5 pipeline
        order = NewOrderSingle.from_dict(sample_order_request)

        # Stage 1: Order submission with intelligent routing
        tracking_id = await enhanced_execution_engine.submit_order_with_full_pipeline(
            order, sample_order_request["user_id"]
        )

        # Stage 2: Verify routing decision
        routing_info = await enhanced_execution_engine.get_order_routing_info(
            tracking_id
        )
        assert routing_info is not None
        assert routing_info.selected_broker in ["ib", "fxcm", "manual"]

        # Stage 3: Simulate broker processing
        await enhanced_execution_engine.simulate_full_execution_cycle(
            tracking_id, fill_price=Decimal("1.1234"), execution_time_ms=150
        )

        # Stage 4: Verify final state
        final_tracker = await enhanced_execution_engine.get_order_tracker(tracking_id)
        assert final_tracker.status == "FILLED"
        assert final_tracker.filled_quantity == sample_order_request["quantity"]
        assert final_tracker.average_price == Decimal("1.1234")

        # Stage 5: Verify performance metrics
        execution_metrics = await enhanced_execution_engine.get_execution_metrics(
            tracking_id
        )
        assert execution_metrics.total_execution_time_ms >= 150
        assert execution_metrics.routing_time_ms > 0
        assert execution_metrics.broker_processing_time_ms > 0

    async def test_multi_broker_failover_scenario(
        self,
        enhanced_execution_engine: ExecutionEngine,
        multi_broker_manager: BrokerAdapterManager,
        sample_order_request: Dict[str, Any],
    ):
        """Test complex failover scenario across multiple brokers."""
        # Submit order with multiple broker options
        order = NewOrderSingle.from_dict(sample_order_request)
        tracking_id = await enhanced_execution_engine.submit_order_with_full_pipeline(
            order, sample_order_request["user_id"]
        )

        # Simulate primary broker failure
        routing_info = await enhanced_execution_engine.get_order_routing_info(
            tracking_id
        )
        primary_broker = routing_info.selected_broker

        await multi_broker_manager.simulate_broker_failure(
            primary_broker, "connection_lost"
        )

        # Trigger failover
        failover_result = await enhanced_execution_engine.trigger_broker_failover(
            tracking_id
        )

        # Verify successful failover
        assert failover_result.success is True
        assert failover_result.new_broker != primary_broker
        assert failover_result.failover_time_ms < 1000  # Sub-second failover

        # Complete order on backup broker
        await enhanced_execution_engine.simulate_full_execution_cycle(
            tracking_id, fill_price=Decimal("1.1235"), execution_time_ms=200
        )

        # Verify final execution
        final_tracker = await enhanced_execution_engine.get_order_tracker(tracking_id)
        assert final_tracker.status == "FILLED"
        assert final_tracker.execution_broker == failover_result.new_broker

    async def test_system_performance_under_load(
        self,
        enhanced_execution_engine: ExecutionEngine,
        multi_broker_manager: BrokerAdapterManager,
    ):
        """Test system performance under sustained load."""
        # Submit high volume of concurrent orders
        concurrent_orders = 100
        tasks = []

        for i in range(concurrent_orders):
            order_request = {
                "client_order_id": str(uuid.uuid4()),
                "symbol": "EURUSD",
                "side": Side.BUY,
                "quantity": Decimal("10000"),
                "order_type": OrdType.MARKET,
                "user_id": f"user_{i % 10}",  # 10 different users
            }

            order = NewOrderSingle.from_dict(order_request)
            task = asyncio.create_task(
                enhanced_execution_engine.submit_order_with_full_pipeline(
                    order, order_request["user_id"]
                )
            )
            tasks.append(task)

        # Execute all orders concurrently
        start_time = datetime.now(timezone.utc)
        tracking_ids = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = datetime.now(timezone.utc)

        # Filter out exceptions
        successful_orders = [
            tid for tid in tracking_ids if not isinstance(tid, Exception)
        ]

        # Verify performance requirements
        total_time_seconds = (end_time - start_time).total_seconds()
        throughput = len(successful_orders) / total_time_seconds

        assert throughput >= 50  # Minimum 50 orders/second
        assert len(successful_orders) >= 95  # 95% success rate minimum

        # Verify system stability under load
        system_metrics = await enhanced_execution_engine.get_system_health_metrics()
        assert system_metrics.cpu_usage_percent < 80
        assert system_metrics.memory_usage_percent < 80
        assert system_metrics.active_connections < 1000


if __name__ == "__main__":
    # Run Phase 5 tests with: python -m pytest tests/phase5/test_fix_broker_integration_framework.py -v
    pytest.main([__file__, "-v"])
