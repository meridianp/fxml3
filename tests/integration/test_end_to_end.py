#!/usr/bin/env python3
"""End-to-End Integration Tests for FIX Broker Abstraction.

This module tests the complete order flow from submission through execution
across the entire broker abstraction system.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pika
import pytest

from fxml4.brokers.adapters.base import AdapterConfig
from fxml4.brokers.adapters.manager import AdapterManager
from fxml4.brokers.adapters.registry import BrokerRegistry
from fxml4.brokers.messaging.consumer import BrokerMessageConsumer, MessageHandler
from fxml4.brokers.messaging.publisher import BrokerMessagePublisher
from fxml4.brokers.messaging.router import MessageRouter, RoutingRule
from fxml4.brokers.messaging.topology import QueueTopology
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle
from fxml4.fix.utils.builder import FIXMessageBuilder
from fxml4.fix.utils.parser import FIXParser

logger = logging.getLogger(__name__)


class OrderFlowTracker:
    """Tracks orders through the system for testing."""

    def __init__(self):
        self.submitted_orders: Dict[str, NewOrderSingle] = {}
        self.execution_reports: Dict[str, List[ExecutionReport]] = {}
        self.order_states: Dict[str, str] = {}
        self.routing_decisions: Dict[str, str] = {}
        self.timestamps: Dict[str, Dict[str, datetime]] = {}

    def track_submission(self, order: NewOrderSingle, broker: str):
        """Track order submission."""
        self.submitted_orders[order.cl_ord_id] = order
        self.routing_decisions[order.cl_ord_id] = broker
        self.timestamps[order.cl_ord_id] = {"submitted": datetime.now(timezone.utc)}

    def track_execution_report(self, report: ExecutionReport):
        """Track execution report."""
        cl_ord_id = report.cl_ord_id

        if cl_ord_id not in self.execution_reports:
            self.execution_reports[cl_ord_id] = []

        self.execution_reports[cl_ord_id].append(report)
        self.order_states[cl_ord_id] = report.ord_status.name

        # Track state transitions
        if cl_ord_id in self.timestamps:
            state_key = f"state_{report.ord_status.name}"
            self.timestamps[cl_ord_id][state_key] = datetime.now(timezone.utc)

    def get_order_latency(self, cl_ord_id: str) -> Optional[float]:
        """Get order processing latency in milliseconds."""
        if cl_ord_id not in self.timestamps:
            return None

        timestamps = self.timestamps[cl_ord_id]
        if "submitted" in timestamps and "state_NEW" in timestamps:
            delta = timestamps["state_NEW"] - timestamps["submitted"]
            return delta.total_seconds() * 1000

        return None

    def get_fill_latency(self, cl_ord_id: str) -> Optional[float]:
        """Get order fill latency in milliseconds."""
        if cl_ord_id not in self.timestamps:
            return None

        timestamps = self.timestamps[cl_ord_id]
        if "state_NEW" in timestamps and "state_FILLED" in timestamps:
            delta = timestamps["state_FILLED"] - timestamps["state_NEW"]
            return delta.total_seconds() * 1000

        return None


class TestMessageHandler(MessageHandler):
    """Test message handler for capturing execution reports."""

    def __init__(self, tracker: OrderFlowTracker):
        self.tracker = tracker

    def handle_execution_report(
        self, message: ExecutionReport, envelope: Dict[str, Any]
    ) -> bool:
        """Handle execution report."""
        self.tracker.track_execution_report(message)
        return True

    def handle_admin_response(
        self, response: Dict[str, Any], envelope: Dict[str, Any]
    ) -> bool:
        """Handle admin response."""
        logger.info(f"Admin response: {response}")
        return True

    def handle_market_data(
        self, data: Dict[str, Any], envelope: Dict[str, Any]
    ) -> bool:
        """Handle market data."""
        # Not used in this test
        return True


@pytest.fixture
async def test_environment():
    """Set up complete test environment."""
    # Create order tracker
    tracker = OrderFlowTracker()

    # Create RabbitMQ connection parameters
    connection_params = pika.ConnectionParameters(
        host="localhost", port=5672, credentials=pika.PlainCredentials("guest", "guest")
    )

    # Check if RabbitMQ is available
    try:
        test_connection = pika.BlockingConnection(connection_params)
        test_connection.close()
        rabbitmq_available = True
    except:
        rabbitmq_available = False
        logger.warning("RabbitMQ not available - using mock mode")

    # Create components
    components = {
        "tracker": tracker,
        "rabbitmq_available": rabbitmq_available,
        "connection_params": connection_params if rabbitmq_available else None,
        "adapters": {},
        "publisher": None,
        "consumer": None,
        "router": MessageRouter(),
        "manager": AdapterManager(),
    }

    # Set up routing rules
    components["router"].add_rule(
        RoutingRule(
            name="large_to_manual",
            priority=1,
            conditions={"min_quantity": 1000000},
            target_brokers=["manual"],
            fallback_brokers=["ib"],
        )
    )

    components["router"].add_rule(
        RoutingRule(
            name="default_to_ib",
            priority=10,
            conditions={},
            target_brokers=["ib"],
            fallback_brokers=["manual"],
        )
    )

    # Initialize adapters
    adapter_configs = {
        "ib": AdapterConfig(
            broker_type="ib",
            adapter_type="ib" + ("_rabbitmq" if rabbitmq_available else ""),
            connection_params=(
                {
                    "mock": True,  # Use mock mode for testing
                    "rabbitmq": {
                        "host": "localhost",
                        "port": 5672,
                        "username": "guest",
                        "password": "guest",
                    },
                }
                if rabbitmq_available
                else {"mock": True}
            ),
            features={"market_data": True},
            limits={"max_orders_per_second": 50},
        ),
        "manual": AdapterConfig(
            broker_type="manual",
            adapter_type="manual" + ("_rabbitmq" if rabbitmq_available else ""),
            connection_params=(
                {
                    "rabbitmq": {
                        "host": "localhost",
                        "port": 5672,
                        "username": "guest",
                        "password": "guest",
                    }
                }
                if rabbitmq_available
                else {}
            ),
            features={
                "auto_reject_timeout": 30,
                "simulate_execution": True,
                "simulated_fill_delay": 1,
            },
            limits={},
        ),
    }

    # Initialize adapters
    for broker_type, config in adapter_configs.items():
        await components["manager"].initialize_adapter(broker_type, config)
        components["adapters"][broker_type] = components["manager"].adapters[
            broker_type
        ]

    # Set up message queue if available
    if rabbitmq_available:
        # Create publisher
        components["publisher"] = BrokerMessagePublisher(connection_params)
        components["publisher"].connect()

        # Create consumer with test handler
        handler = TestMessageHandler(tracker)
        components["consumer"] = BrokerMessageConsumer(connection_params, handler)
        components["consumer"].connect()

        # Set up queues
        topology = QueueTopology()
        topology.setup_broker_queues(components["publisher"].channel, ["ib", "manual"])

        # Start consuming execution reports
        components["consumer"].channel.basic_consume(
            queue="executions.all",
            on_message_callback=components["consumer"]._handle_execution_report,
            auto_ack=False,
        )

        # Run consumer in background
        asyncio.create_task(components["consumer"].run_async())

    yield components

    # Cleanup
    await components["manager"].shutdown()

    if components["publisher"]:
        components["publisher"].disconnect()
    if components["consumer"]:
        components["consumer"].stop_consuming()
        components["consumer"].disconnect()


class TestEndToEndOrderFlow:
    """Test complete order flow through the system."""

    @pytest.mark.asyncio
    async def test_simple_order_flow(self, test_environment):
        """Test simple order submission and execution."""
        tracker = test_environment["tracker"]
        router = test_environment["router"]
        adapters = test_environment["adapters"]

        # Create test order
        order = NewOrderSingle(
            cl_ord_id=f"E2E_SIMPLE_{uuid.uuid4().hex[:8]}",
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IOC,
            transact_time=datetime.now(timezone.utc),
        )

        # Route order
        selected_broker = router.route_order(order)
        assert selected_broker == "ib"  # Should go to IB based on size

        # Track submission
        tracker.track_submission(order, selected_broker)

        # Submit order
        adapter = adapters[selected_broker]
        order_id = await adapter.submit_order(order)
        assert order_id is not None

        # Wait for execution reports
        await asyncio.sleep(2)

        # Check order state
        assert order.cl_ord_id in tracker.order_states

        # Verify latency
        latency = tracker.get_order_latency(order.cl_ord_id)
        if latency:
            assert latency < 1000  # Should be less than 1 second

    @pytest.mark.asyncio
    async def test_manual_approval_flow(self, test_environment):
        """Test order requiring manual approval."""
        tracker = test_environment["tracker"]
        router = test_environment["router"]
        adapters = test_environment["adapters"]

        # Create large order requiring manual approval
        order = NewOrderSingle(
            cl_ord_id=f"E2E_MANUAL_{uuid.uuid4().hex[:8]}",
            symbol="GBP/USD",
            side=Side.SELL,
            order_qty=5000000,  # Large order
            ord_type=OrdType.LIMIT,
            price=1.2650,
            time_in_force=TimeInForce.DAY,
            transact_time=datetime.now(timezone.utc),
        )

        # Route order
        selected_broker = router.route_order(order)
        assert selected_broker == "manual"  # Should go to manual

        # Track submission
        tracker.track_submission(order, selected_broker)

        # Submit order
        adapter = adapters[selected_broker]
        order_id = await adapter.submit_order(order)
        assert order_id is not None

        # Simulate manual approval
        if hasattr(adapter, "approve_order"):
            await asyncio.sleep(1)  # Wait a bit

            approved = await adapter.approve_order(
                cl_ord_id=order.cl_ord_id,
                reviewer="test_approver",
                notes="E2E test approval",
            )
            assert approved

        # Wait for execution
        await asyncio.sleep(3)

        # Check final state
        assert order.cl_ord_id in tracker.order_states

    @pytest.mark.asyncio
    async def test_multi_broker_order_flow(self, test_environment):
        """Test orders going to different brokers."""
        tracker = test_environment["tracker"]
        router = test_environment["router"]
        adapters = test_environment["adapters"]

        # Create multiple orders
        orders = [
            # Small order - IB
            NewOrderSingle(
                cl_ord_id=f"E2E_IB_{uuid.uuid4().hex[:8]}",
                symbol="USD/JPY",
                side=Side.BUY,
                order_qty=50000,
                ord_type=OrdType.LIMIT,
                price=110.50,
                time_in_force=TimeInForce.DAY,
                transact_time=datetime.now(timezone.utc),
            ),
            # Large order - Manual
            NewOrderSingle(
                cl_ord_id=f"E2E_MANUAL_{uuid.uuid4().hex[:8]}",
                symbol="EUR/GBP",
                side=Side.SELL,
                order_qty=2000000,
                ord_type=OrdType.MARKET,
                time_in_force=TimeInForce.FOK,
                transact_time=datetime.now(timezone.utc),
            ),
        ]

        # Submit orders
        submission_tasks = []

        for order in orders:
            # Route order
            broker = router.route_order(order)
            tracker.track_submission(order, broker)

            # Submit to appropriate adapter
            adapter = adapters[broker]
            task = adapter.submit_order(order)
            submission_tasks.append((order.cl_ord_id, broker, task))

        # Wait for all submissions
        for cl_ord_id, broker, task in submission_tasks:
            order_id = await task
            assert order_id is not None
            logger.info(f"Order {cl_ord_id} submitted to {broker}: {order_id}")

        # Auto-approve manual orders for testing
        manual_adapter = adapters.get("manual")
        if manual_adapter and hasattr(manual_adapter, "get_pending_orders"):
            await asyncio.sleep(1)

            pending = await manual_adapter.get_pending_orders()
            for pending_order in pending:
                await manual_adapter.approve_order(
                    cl_ord_id=pending_order["cl_ord_id"],
                    reviewer="auto_test",
                    notes="Auto-approved for E2E test",
                )

        # Wait for executions
        await asyncio.sleep(3)

        # Verify all orders were processed
        for order in orders:
            assert order.cl_ord_id in tracker.submitted_orders
            assert order.cl_ord_id in tracker.routing_decisions

    @pytest.mark.asyncio
    async def test_order_lifecycle_tracking(self, test_environment):
        """Test complete order lifecycle tracking."""
        tracker = test_environment["tracker"]
        router = test_environment["router"]
        adapters = test_environment["adapters"]

        # Create order
        order = NewOrderSingle(
            cl_ord_id=f"E2E_LIFECYCLE_{uuid.uuid4().hex[:8]}",
            symbol="AUD/USD",
            side=Side.BUY,
            order_qty=75000,
            ord_type=OrdType.LIMIT,
            price=0.7250,
            time_in_force=TimeInForce.GTC,
            transact_time=datetime.now(timezone.utc),
        )

        # Submit order
        broker = router.route_order(order)
        tracker.track_submission(order, broker)

        adapter = adapters[broker]
        order_id = await adapter.submit_order(order)

        # Wait for state transitions
        await asyncio.sleep(2)

        # Check lifecycle timestamps
        if order.cl_ord_id in tracker.timestamps:
            timestamps = tracker.timestamps[order.cl_ord_id]
            assert "submitted" in timestamps

            # Calculate latencies
            order_latency = tracker.get_order_latency(order.cl_ord_id)
            fill_latency = tracker.get_fill_latency(order.cl_ord_id)

            logger.info(f"Order lifecycle for {order.cl_ord_id}:")
            logger.info(f"  - Order latency: {order_latency}ms")
            logger.info(f"  - Fill latency: {fill_latency}ms")

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, test_environment):
        """Test error handling and recovery scenarios."""
        tracker = test_environment["tracker"]
        router = test_environment["router"]
        adapters = test_environment["adapters"]

        # Test invalid order
        invalid_order = NewOrderSingle(
            cl_ord_id=f"E2E_INVALID_{uuid.uuid4().hex[:8]}",
            symbol="INVALID/SYMBOL",
            side=Side.BUY,
            order_qty=-1000,  # Invalid quantity
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IOC,
            transact_time=datetime.now(timezone.utc),
        )

        # Try to submit
        broker = router.route_order(invalid_order)
        adapter = adapters[broker]

        # Should handle error gracefully
        try:
            order_id = await adapter.submit_order(invalid_order)
            # Some adapters might accept and then reject
        except Exception as e:
            logger.info(f"Expected error for invalid order: {e}")

        # Test adapter recovery
        # Disconnect adapter
        await adapter.disconnect()
        assert not adapter.connection.is_connected()

        # Reconnect
        connected = await adapter.connect()
        assert connected

        # Submit valid order after recovery
        recovery_order = NewOrderSingle(
            cl_ord_id=f"E2E_RECOVERY_{uuid.uuid4().hex[:8]}",
            symbol="USD/CHF",
            side=Side.SELL,
            order_qty=25000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IOC,
            transact_time=datetime.now(timezone.utc),
        )

        order_id = await adapter.submit_order(recovery_order)
        assert order_id is not None


class TestPerformanceMetrics:
    """Test system performance metrics."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_throughput_measurement(self, test_environment):
        """Measure system throughput."""
        tracker = test_environment["tracker"]
        router = test_environment["router"]
        adapters = test_environment["adapters"]

        # Generate test orders
        order_count = 50
        orders = []

        for i in range(order_count):
            order = NewOrderSingle(
                cl_ord_id=f"PERF_{i}_{uuid.uuid4().hex[:8]}",
                symbol="EUR/USD",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                order_qty=10000 + (i * 1000),
                ord_type=OrdType.LIMIT,
                price=1.0800 + (i * 0.0001),
                time_in_force=TimeInForce.DAY,
                transact_time=datetime.now(timezone.utc),
            )
            orders.append(order)

        # Measure submission time
        start_time = datetime.now(timezone.utc)

        # Submit all orders
        tasks = []
        for order in orders:
            broker = router.route_order(order)
            tracker.track_submission(order, broker)

            adapter = adapters[broker]
            task = adapter.submit_order(order)
            tasks.append(task)

        # Wait for all submissions
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = datetime.now(timezone.utc)

        # Calculate metrics
        duration = (end_time - start_time).total_seconds()
        successful = len([r for r in results if not isinstance(r, Exception)])
        throughput = successful / duration

        logger.info(f"Performance metrics:")
        logger.info(f"  - Orders submitted: {successful}/{order_count}")
        logger.info(f"  - Duration: {duration:.2f}s")
        logger.info(f"  - Throughput: {throughput:.1f} orders/sec")

        # Performance assertions
        assert successful >= order_count * 0.95  # 95% success rate
        assert throughput >= 10  # At least 10 orders/second


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
