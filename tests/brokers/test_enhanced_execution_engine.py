import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fxml4.brokers.enhanced_execution_engine import (
    EnhancedExecutionEngine,
    EnhancedExecutionEngineError,
    OrderLifecycleStatus,
    SystemHealthMetrics,
    ThroughputMetrics,
    create_enhanced_execution_engine,
)


# Test fixtures
@pytest.fixture
def mock_order():
    """Create a minimal FIX NewOrderSingle-like object for tests.

    Includes attributes used by the engine: cl_ord_id, symbol, side, order_qty,
    ord_type, and price (optional). Side/ord_type expose `.value` like an Enum.
    """

    class Side:
        def __init__(self, value):
            self.value = value

    class OrdType:
        def __init__(self, value):
            self.value = value

    return SimpleNamespace(
        cl_ord_id="CID123",
        symbol="EUR/USD",
        side=Side("BUY"),
        order_qty=Decimal("100000"),
        ord_type=OrdType("LIMIT"),
        price=Decimal("1.2345"),
    )


@pytest.fixture
def engine_config():
    """Provide a baseline configuration for the enhanced engine."""
    return {
        "max_concurrent_orders": 3,
        "order_timeout_seconds": 60,
        "enable_performance_monitoring": True,
        "enable_intelligent_routing": True,
        "circuit_breaker_threshold": 2,
        "lifecycle": {},
        "routing": {},
        "messaging": {},
    }


@pytest.fixture
def patched_components():
    """Patch broker-facing components to isolate engine logic.

    - OrderLifecycleManager.create_order_tracker returns a tracking id.
    - OrderLifecycleManager.get_order_tracker/update_order_status are async mocks.
    - IntelligentRoutingEngine.initialize/get_optimal_broker_routing are async mocks.
    - EnhancedMessageRouter.initialize/route_order_message/shutdown are async mocks.
    - TradeExecutionEngine is stubbed since it's not used directly in tests here.
    """

    with (
        patch(
            "fxml4.brokers.enhanced_execution_engine.OrderLifecycleManager",
            autospec=True,
        ) as MockLifecycle,
        patch(
            "fxml4.brokers.enhanced_execution_engine.IntelligentRoutingEngine",
            autospec=True,
        ) as MockRouting,
        patch(
            "fxml4.brokers.enhanced_execution_engine.EnhancedMessageRouter",
            autospec=True,
        ) as MockRouter,
        patch(
            "fxml4.brokers.enhanced_execution_engine.TradeExecutionEngine",
            autospec=True,
        ) as MockBaseEngine,
    ):
        # Lifecycle manager async behaviors
        lifecycle_instance = MockLifecycle.return_value
        lifecycle_instance.initialize = AsyncMock(return_value=None)
        lifecycle_instance.create_order_tracker = AsyncMock(
            side_effect=lambda **kwargs: asyncio.Future()
        )

        async def _create_order_tracker(**kwargs):
            fut = asyncio.Future()
            fut.set_result("TRACK-1")
            return await fut

        lifecycle_instance.create_order_tracker.side_effect = _create_order_tracker
        lifecycle_instance.get_order_tracker = AsyncMock(return_value=None)
        lifecycle_instance.update_order_status = AsyncMock(return_value=True)
        lifecycle_instance.get_performance_summary = AsyncMock(
            return_value={"ok": True}
        )

        # Routing engine async behaviors
        routing_instance = MockRouting.return_value
        routing_instance.initialize = AsyncMock(return_value=None)
        routing_instance.get_optimal_broker_routing = AsyncMock(return_value=None)
        routing_instance.trigger_broker_failover = AsyncMock(
            return_value=SimpleNamespace(success=True, new_broker="B2")
        )

        # Message router async behaviors
        router_instance = MockRouter.return_value
        router_instance.initialize = AsyncMock(return_value=None)
        router_instance.route_order_message = AsyncMock(return_value=True)
        router_instance.shutdown = AsyncMock(return_value=None)

        # Base engine stub
        base_engine_instance = MockBaseEngine.return_value
        base_engine_instance.initialize = AsyncMock(return_value=None)

        yield {
            "lifecycle": lifecycle_instance,
            "routing": routing_instance,
            "router": router_instance,
            "base": base_engine_instance,
        }


@pytest.mark.unit
def test_throughput_metrics_utilization_when_basic_then_computed_correctly():
    """Validate ThroughputMetrics.utilization_percent for normal and boundary cases."""
    tm = ThroughputMetrics(orders_per_second=5.0, current_load=50, max_capacity=100)
    assert tm.utilization_percent == 50.0

    tm.current_load = 0
    assert tm.utilization_percent == 0.0

    tm.max_capacity = 0  # boundary: avoid division by zero
    assert tm.utilization_percent == 0.0

    tm.max_capacity = 10
    tm.current_load = 15  # can exceed 100%
    assert tm.utilization_percent == 150.0


@pytest.mark.unit
def test_system_health_metrics_defaults_then_initialized_with_timezone():
    """Ensure SystemHealthMetrics defaults and timezone-aware timestamps are set."""
    shm = SystemHealthMetrics()
    assert shm.cpu_usage_percent == 0.0
    assert shm.memory_usage_percent == 0.0
    assert shm.active_connections == 0
    assert shm.queue_depth == 0
    assert shm.error_rate_percent == 0.0
    assert isinstance(shm.last_updated, datetime)
    assert (
        shm.last_updated.tzinfo is not None
        and shm.last_updated.tzinfo.utcoffset(shm.last_updated) is not None
    )


@pytest.mark.unit
def test_factory_function_when_called_then_returns_engine_instance(engine_config):
    """Factory should return an EnhancedExecutionEngine with provided config."""
    engine = create_enhanced_execution_engine(engine_config)
    assert isinstance(engine, EnhancedExecutionEngine)
    assert engine.config["max_concurrent_orders"] == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_initialize_when_all_good_then_engine_ready(
    engine_config, patched_components
):
    """Engine.initialize sets up components and enables monitoring."""
    engine = EnhancedExecutionEngine(engine_config)

    await engine.initialize()
    assert engine.is_initialized is True
    assert engine.performance_enabled is True
    assert engine.routing_engine is not None
    assert engine.message_router is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_initialize_when_router_init_fails_then_raises(engine_config):
    """If a component init fails, EnhancedExecutionEngineError is raised."""
    with (
        patch(
            "fxml4.brokers.enhanced_execution_engine.EnhancedMessageRouter",
            autospec=True,
        ) as MockRouter,
        patch(
            "fxml4.brokers.enhanced_execution_engine.OrderLifecycleManager",
            autospec=True,
        ) as MockLifecycle,
    ):
        MockLifecycle.return_value.initialize = AsyncMock(return_value=None)
        inst = MockRouter.return_value
        inst.initialize = AsyncMock(side_effect=RuntimeError("router down"))

        engine = EnhancedExecutionEngine({"enable_intelligent_routing": False})
        with pytest.raises(EnhancedExecutionEngineError):
            await engine.initialize()


@pytest.mark.broker
@pytest.mark.fix_protocol
def test_order_to_dict_when_fix_fields_then_value_extracted(mock_order):
    """Validate FIX-like message transformation to dict, including .value extraction and price conversion."""
    engine = EnhancedExecutionEngine({})
    out = engine._order_to_dict(mock_order, user_id="U1")

    assert out["client_order_id"] == "CID123"
    assert out["symbol"] == "EUR/USD"
    assert out["side"] == "BUY"
    assert out["quantity"] == float(Decimal("100000"))
    assert out["order_type"] == "LIMIT"
    assert out["price"] == float(Decimal("1.2345"))
    assert out["user_id"] == "U1"
    assert "timestamp" in out and isinstance(out["timestamp"], str)


@pytest.mark.broker
@pytest.mark.asyncio
async def test_submit_order_with_tracking_when_not_initialized_then_error(mock_order):
    """Submitting before initialize should raise engine-not-initialized error."""
    engine = EnhancedExecutionEngine({})
    with pytest.raises(EnhancedExecutionEngineError):
        await engine.submit_order_with_tracking(mock_order, user_id="U1")


@pytest.mark.broker
@pytest.mark.asyncio
async def test_submit_order_with_tracking_when_capacity_exceeded_then_error(
    engine_config, patched_components, mock_order
):
    """Capacity limits are enforced and raise EnhancedExecutionEngineError."""
    engine = EnhancedExecutionEngine({**engine_config, "max_concurrent_orders": 1})
    await engine.initialize()

    # First order takes the only slot
    tid1 = await engine.submit_order_with_tracking(mock_order, user_id="U1")
    assert tid1 == "TRACK-1"
    assert engine.throughput_metrics.current_load == 1

    # Second order should fail due to capacity
    with pytest.raises(EnhancedExecutionEngineError):
        await engine.submit_order_with_tracking(mock_order, user_id="U1")


@pytest.mark.broker
@pytest.mark.asyncio
async def test_submit_order_with_tracking_when_ok_then_updates_metrics(
    engine_config, patched_components, mock_order
):
    """Successful submission adds to active set and increments counters."""
    engine = EnhancedExecutionEngine(engine_config)
    await engine.initialize()

    tracking_id = await engine.submit_order_with_tracking(mock_order, user_id="U1")
    assert tracking_id == "TRACK-1"
    assert "TRACK-1" in engine.active_orders
    assert engine.execution_metrics["total_orders_submitted"] == 1
    assert engine.throughput_metrics.current_load == 1


@pytest.mark.broker
@pytest.mark.asyncio
async def test_submit_order_with_tracking_when_create_fails_then_circuit_breaker_increments(
    engine_config, patched_components, mock_order
):
    """Failure during submission increments circuit breaker and eventually opens it."""
    engine = EnhancedExecutionEngine({**engine_config, "circuit_breaker_threshold": 1})
    await engine.initialize()

    # Force create tracker failure
    patched_components["lifecycle"].create_order_tracker.side_effect = RuntimeError(
        "db down"
    )

    with pytest.raises(EnhancedExecutionEngineError):
        await engine.submit_order_with_tracking(mock_order, user_id="U1")

    status = await engine.get_circuit_breaker_status()
    assert status.failure_count >= 1
    assert status.is_open is True  # threshold reached


@pytest.mark.broker
@pytest.mark.asyncio
async def test_submit_order_with_tracking_when_circuit_open_then_rejected(
    engine_config, patched_components, mock_order
):
    """When circuit breaker is open, new orders are rejected immediately."""
    engine = EnhancedExecutionEngine(engine_config)
    await engine.initialize()

    engine.circuit_breaker_open = True
    with pytest.raises(EnhancedExecutionEngineError):
        await engine.submit_order_with_tracking(mock_order, user_id="U1")


@pytest.mark.broker
@pytest.mark.asyncio
async def test_full_pipeline_when_routing_enabled_then_updates_tracker(
    engine_config, patched_components, mock_order
):
    """Full pipeline performs routing and populates routing info on the tracker."""
    engine = EnhancedExecutionEngine(engine_config)
    await engine.initialize()

    # Prepare routing decision mock
    decision = SimpleNamespace(
        primary_broker="B1",
        fallback_brokers=["B2", "B3"],
        routing_strategy=SimpleNamespace(value="FASTEST_PATH"),
    )
    patched_components["routing"].get_optimal_broker_routing.return_value = decision

    # Prepare tracker object to be returned and then updated
    tracker = SimpleNamespace(
        selected_broker=None,
        routing_strategy=None,
        broker_routing_history=[],
    )
    patched_components["lifecycle"].get_order_tracker.return_value = tracker

    tid = await engine.submit_order_with_full_pipeline(mock_order, user_id="U1")
    assert tid == "TRACK-1"
    assert tracker.selected_broker == "B1"
    assert tracker.routing_strategy == "FASTEST_PATH"
    assert tracker.broker_routing_history == ["B1", "B2", "B3"]


@pytest.mark.broker
@pytest.mark.asyncio
async def test_update_order_status_when_terminal_filled_then_metrics_and_cleanup(
    engine_config, patched_components
):
    """Updating to a terminal FILLED state cleans up active orders and increments success count."""
    engine = EnhancedExecutionEngine(engine_config)
    await engine.initialize()

    # Seed active orders
    engine.active_orders.add("TRACK-1")
    engine.throughput_metrics.current_load = 1

    tracker = SimpleNamespace(
        is_terminal_state=True,
        status=OrderLifecycleStatus.FILLED,
        quantity=Decimal("1"),
    )
    patched_components["lifecycle"].get_order_tracker.return_value = tracker
    patched_components["lifecycle"].update_order_status.return_value = True

    ok = await engine.update_order_status("TRACK-1", OrderLifecycleStatus.FILLED)
    assert ok is True
    assert "TRACK-1" not in engine.active_orders
    assert engine.throughput_metrics.current_load == 0
    assert engine.execution_metrics["successful_executions"] == 1


@pytest.mark.broker
@pytest.mark.asyncio
async def test_update_order_status_when_terminal_rejected_then_failed_metrics(
    engine_config, patched_components
):
    """Terminal REJECTED increments failed executions metric."""
    engine = EnhancedExecutionEngine(engine_config)
    await engine.initialize()

    engine.active_orders.add("TRACK-2")
    engine.throughput_metrics.current_load = 1

    tracker = SimpleNamespace(
        is_terminal_state=True, status=OrderLifecycleStatus.REJECTED
    )
    patched_components["lifecycle"].get_order_tracker.return_value = tracker
    patched_components["lifecycle"].update_order_status.return_value = True

    ok = await engine.update_order_status("TRACK-2", OrderLifecycleStatus.REJECTED)
    assert ok is True
    assert "TRACK-2" not in engine.active_orders
    assert engine.execution_metrics["failed_executions"] == 1


@pytest.mark.broker
@pytest.mark.asyncio
async def test_simulate_broker_rejection_then_circuit_breaker_records_failure(
    engine_config, patched_components
):
    """Broker rejection path should feed circuit breaker failure handling."""
    engine = EnhancedExecutionEngine({**engine_config, "circuit_breaker_threshold": 99})
    await engine.initialize()

    await engine.simulate_broker_rejection("TRACK-9", reason="invalid price")
    status = await engine.get_circuit_breaker_status()
    assert status.failure_count == 1
    assert status.is_open is False  # threshold not reached


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_order_routing_info_when_tracker_missing_then_none(
    engine_config, patched_components
):
    """Missing tracker returns None for routing info."""
    engine = EnhancedExecutionEngine(engine_config)
    await engine.initialize()
    patched_components["lifecycle"].get_order_tracker.return_value = None
    assert await engine.get_order_routing_info("T0") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_order_performance_metrics_when_present_then_serialized(
    engine_config, patched_components
):
    """Validate serialization of performance metrics timestamps and numeric fields."""
    engine = EnhancedExecutionEngine(engine_config)
    await engine.initialize()

    perf = SimpleNamespace(
        acknowledgment_latency_ms=5.0,
        total_execution_time_ms=25.0,
        routing_time_ms=10.0,
        broker_processing_time_ms=15.0,
        retry_count=1,
        submission_timestamp=datetime.now(timezone.utc),
        completion_timestamp=datetime.now(timezone.utc),
    )
    tracker = SimpleNamespace(performance_metrics=perf)
    patched_components["lifecycle"].get_order_tracker.return_value = tracker

    out = await engine.get_order_performance_metrics("T1")
    assert out["acknowledgment_latency_ms"] == 5.0
    assert isinstance(out["submission_timestamp"], str)
    assert isinstance(out["completion_timestamp"], str)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_execution_metrics_when_aggregated_then_contains_expected_keys(
    engine_config, patched_components
):
    """Aggregated execution metrics include nested performance and routing info."""
    engine = EnhancedExecutionEngine(engine_config)
    await engine.initialize()

    perf = SimpleNamespace(
        acknowledgment_latency_ms=1.0,
        total_execution_time_ms=2.0,
        routing_time_ms=3.0,
        broker_processing_time_ms=4.0,
        retry_count=0,
        submission_timestamp=datetime.now(timezone.utc),
        completion_timestamp=datetime.now(timezone.utc),
    )
    tracker = SimpleNamespace(
        performance_metrics=perf,
        selected_broker="B1",
        routing_strategy="FASTEST_PATH",
        routing_attempts=1,
        broker_routing_history=["B1"],
    )
    patched_components["lifecycle"].get_order_tracker.return_value = tracker

    out = await engine.get_execution_metrics("T2")
    assert out["tracking_id"] == "T2"
    assert out["performance_metrics"]["total_execution_time_ms"] == 2.0
    assert out["routing_info"]["selected_broker"] == "B1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_system_and_throughput_metrics_when_updated_then_values_consistent(
    engine_config, patched_components
):
    """System health metrics reflect queue depth and error rates from execution stats."""
    engine = EnhancedExecutionEngine(engine_config)
    await engine.initialize()

    # Seed some state
    engine.throughput_metrics.queue_backlog = 2
    engine.execution_metrics["total_orders_submitted"] = 10
    engine.execution_metrics["failed_executions"] = 2
    engine.active_orders = {"A", "B"}

    # Update health metrics via private method
    await engine._update_system_health_metrics()
    shm = await engine.get_system_health_metrics()
    assert shm.active_connections == 2
    assert shm.queue_depth == 2
    assert shm.error_rate_percent == 20.0

    tm = await engine.get_throughput_metrics()
    assert isinstance(tm, ThroughputMetrics)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_trigger_broker_failover_when_routing_disabled_then_error():
    """Failover requires routing engine; otherwise raises EnhancedExecutionEngineError."""
    engine = EnhancedExecutionEngine({"enable_intelligent_routing": False})
    await engine.initialize()

    with pytest.raises(EnhancedExecutionEngineError):
        await engine.trigger_broker_failover("T3")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_shutdown_when_pending_orders_then_logs_and_completes(
    engine_config, patched_components, caplog
):
    """Shutdown turns off monitoring and invokes router.shutdown; pending orders are tolerated."""
    engine = EnhancedExecutionEngine(engine_config)
    await engine.initialize()

    # Leave one active order to exercise warning path
    engine.active_orders.add("PENDING")
    await engine.shutdown()
    assert engine.performance_enabled is False
    # Router.shutdown should have been awaited
    patched_components["router"].shutdown.assert_awaited()
