#!/usr/bin/env python3
"""Multi-Adapter Integration Tests.

This module tests the integration of multiple broker adapters working together
through the FIX broker abstraction system.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pika
import pytest

from fxml4.brokers.adapters.base import AdapterConfig
from fxml4.brokers.adapters.manager import AdapterManager
from fxml4.brokers.messaging.router import MessageRouter, RoutingRule
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import NewOrderSingle, OrderCancelRequest

logger = logging.getLogger(__name__)


class MockRabbitMQConnection:
    """Mock RabbitMQ connection for testing without actual message queue."""

    def __init__(self):
        self.published_messages = []
        self.consumed_messages = []

    def publish(self, exchange, routing_key, body, properties=None):
        """Mock publish method."""
        self.published_messages.append(
            {
                "exchange": exchange,
                "routing_key": routing_key,
                "body": body,
                "properties": properties,
                "timestamp": datetime.now(timezone.utc),
            }
        )

    def consume(self, queue, callback):
        """Mock consume method."""
        # Simulate message consumption
        pass


@pytest.fixture
async def adapter_manager():
    """Create adapter manager with test configuration."""
    manager = AdapterManager()

    # Configure test adapters
    configs = {
        "ib": AdapterConfig(
            broker_type="ib",
            adapter_type="ib",
            connection_params={"mock": True},
            features={"market_data": True},
            limits={"max_orders_per_second": 10},
        ),
        "manual": AdapterConfig(
            broker_type="manual",
            adapter_type="manual",
            connection_params={},
            features={"auto_reject_timeout": 30, "simulate_execution": True},
            limits={},
        ),
    }

    # Initialize adapters
    for broker_type, config in configs.items():
        await manager.initialize_adapter(broker_type, config)

    yield manager

    # Cleanup
    await manager.shutdown()


@pytest.fixture
def message_router():
    """Create message router with test rules."""
    router = MessageRouter()

    # Add routing rules
    rules = [
        RoutingRule(
            name="large_orders_to_manual",
            priority=1,
            conditions={"min_quantity": 1000000},
            target_brokers=["manual"],
            fallback_brokers=["ib"],
        ),
        RoutingRule(
            name="default_to_ib",
            priority=10,
            conditions={},
            target_brokers=["ib"],
            fallback_brokers=["manual"],
        ),
    ]

    for rule in rules:
        router.add_rule(rule)

    return router


class TestMultiAdapterIntegration:
    """Test multiple adapters working together."""

    @pytest.mark.asyncio
    async def test_adapter_initialization(self, adapter_manager):
        """Test that multiple adapters can be initialized."""
        # Check adapter states
        states = await adapter_manager.get_adapter_states()

        assert "ib" in states
        assert "manual" in states
        assert states["ib"]["connected"] is True
        assert states["manual"]["connected"] is True

    @pytest.mark.asyncio
    async def test_order_routing_by_size(self, adapter_manager, message_router):
        """Test order routing based on order size."""
        # Small order - should go to IB
        small_order = NewOrderSingle(
            cl_ord_id=f"TEST_SMALL_{uuid.uuid4().hex[:8]}",
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=10000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IOC,
            transact_time=datetime.now(timezone.utc),
        )

        # Route order
        selected_broker = message_router.route_order(small_order)
        assert selected_broker == "ib"

        # Large order - should go to manual
        large_order = NewOrderSingle(
            cl_ord_id=f"TEST_LARGE_{uuid.uuid4().hex[:8]}",
            symbol="EUR/USD",
            side=Side.SELL,
            order_qty=5000000,
            ord_type=OrdType.LIMIT,
            price=1.0850,
            time_in_force=TimeInForce.DAY,
            transact_time=datetime.now(timezone.utc),
        )

        selected_broker = message_router.route_order(large_order)
        assert selected_broker == "manual"

    @pytest.mark.asyncio
    async def test_failover_routing(self, adapter_manager, message_router):
        """Test failover to secondary broker."""
        # Disconnect primary broker
        ib_adapter = adapter_manager.adapters.get("ib")
        if ib_adapter:
            await ib_adapter.disconnect()

        # Update adapter availability
        available_brokers = []
        for broker_type, adapter in adapter_manager.adapters.items():
            if adapter.connection.is_connected():
                available_brokers.append(broker_type)

        # Order should failover to manual
        order = NewOrderSingle(
            cl_ord_id=f"TEST_FAILOVER_{uuid.uuid4().hex[:8]}",
            symbol="GBP/USD",
            side=Side.BUY,
            order_qty=50000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.FOK,
            transact_time=datetime.now(timezone.utc),
        )

        # Get routing rule
        rule = message_router._select_routing_rule(order)
        assert rule is not None

        # Check fallback routing
        for broker in rule.target_brokers:
            if broker in available_brokers:
                selected_broker = broker
                break
        else:
            for broker in rule.fallback_brokers:
                if broker in available_brokers:
                    selected_broker = broker
                    break

        assert selected_broker == "manual"

    @pytest.mark.asyncio
    async def test_concurrent_order_submission(self, adapter_manager):
        """Test submitting orders to multiple adapters concurrently."""
        orders = []

        # Create multiple orders
        for i in range(10):
            order = NewOrderSingle(
                cl_ord_id=f"TEST_CONCURRENT_{i}_{uuid.uuid4().hex[:8]}",
                symbol="USD/JPY",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                order_qty=100000 + (i * 10000),
                ord_type=OrdType.LIMIT,
                price=110.00 + (i * 0.01),
                time_in_force=TimeInForce.DAY,
                transact_time=datetime.now(timezone.utc),
            )
            orders.append(order)

        # Submit orders concurrently
        tasks = []
        for i, order in enumerate(orders):
            # Alternate between adapters
            broker_type = "ib" if i % 2 == 0 else "manual"
            adapter = adapter_manager.adapters.get(broker_type)
            if adapter and adapter.connection.is_connected():
                task = adapter.submit_order(order)
                tasks.append(task)

        # Wait for all submissions
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check results
        successful_submissions = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_submissions) >= 8  # Allow for some failures

    @pytest.mark.asyncio
    async def test_adapter_health_monitoring(self, adapter_manager):
        """Test health monitoring across adapters."""
        # Get initial health status
        health_status = {}

        for broker_type, adapter in adapter_manager.adapters.items():
            metrics = adapter.get_metrics()
            health_status[broker_type] = {
                "connected": adapter.connection.is_connected(),
                "total_orders": metrics.total_orders,
                "failed_orders": metrics.failed_orders,
                "last_heartbeat": metrics.last_heartbeat_time,
            }

        # Verify all adapters are healthy
        for broker_type, status in health_status.items():
            assert status["connected"] is True
            assert status["failed_orders"] == 0

    @pytest.mark.asyncio
    async def test_order_cancellation_across_adapters(self, adapter_manager):
        """Test order cancellation on different adapters."""
        # Submit orders to different adapters
        orders = {
            "ib": NewOrderSingle(
                cl_ord_id=f"CANCEL_IB_{uuid.uuid4().hex[:8]}",
                symbol="EUR/USD",
                side=Side.BUY,
                order_qty=10000,
                ord_type=OrdType.LIMIT,
                price=1.0850,
                time_in_force=TimeInForce.DAY,
                transact_time=datetime.now(timezone.utc),
            ),
            "manual": NewOrderSingle(
                cl_ord_id=f"CANCEL_MANUAL_{uuid.uuid4().hex[:8]}",
                symbol="GBP/USD",
                side=Side.SELL,
                order_qty=20000,
                ord_type=OrdType.LIMIT,
                price=1.2650,
                time_in_force=TimeInForce.DAY,
                transact_time=datetime.now(timezone.utc),
            ),
        }

        order_ids = {}

        # Submit orders
        for broker_type, order in orders.items():
            adapter = adapter_manager.adapters.get(broker_type)
            if adapter:
                order_id = await adapter.submit_order(order)
                order_ids[broker_type] = (order.cl_ord_id, order_id)

        # Wait a bit
        await asyncio.sleep(1)

        # Cancel orders
        cancel_results = {}

        for broker_type, (cl_ord_id, order_id) in order_ids.items():
            adapter = adapter_manager.adapters.get(broker_type)
            if adapter:
                cancel_request = OrderCancelRequest(
                    orig_cl_ord_id=cl_ord_id,
                    cl_ord_id=f"CANCEL_{cl_ord_id}",
                    symbol=orders[broker_type].symbol,
                    side=orders[broker_type].side,
                    transact_time=datetime.now(timezone.utc),
                )

                result = await adapter.cancel_order(cancel_request)
                cancel_results[broker_type] = result

        # Verify cancellations
        assert all(cancel_results.values())

    @pytest.mark.asyncio
    async def test_adapter_recovery(self, adapter_manager):
        """Test adapter recovery after disconnection."""
        # Disconnect and reconnect each adapter
        for broker_type, adapter in adapter_manager.adapters.items():
            # Disconnect
            await adapter.disconnect()
            assert not adapter.connection.is_connected()

            # Reconnect
            connected = await adapter.connect()
            assert connected
            assert adapter.connection.is_connected()

            # Test order submission after recovery
            test_order = NewOrderSingle(
                cl_ord_id=f"RECOVERY_{broker_type}_{uuid.uuid4().hex[:8]}",
                symbol="USD/CHF",
                side=Side.BUY,
                order_qty=10000,
                ord_type=OrdType.MARKET,
                time_in_force=TimeInForce.IOC,
                transact_time=datetime.now(timezone.utc),
            )

            order_id = await adapter.submit_order(test_order)
            assert order_id is not None


class TestMessageRouting:
    """Test message routing logic."""

    def test_routing_rule_priority(self, message_router):
        """Test that routing rules are applied by priority."""
        rules = message_router.rules

        # Verify rules are sorted by priority
        priorities = [rule.priority for rule in rules]
        assert priorities == sorted(priorities)

    def test_symbol_based_routing(self):
        """Test routing based on symbol patterns."""
        router = MessageRouter()

        # Add symbol-based rules
        router.add_rule(
            RoutingRule(
                name="fx_majors_to_ib",
                priority=1,
                conditions={"symbols": ["EUR/USD", "GBP/USD", "USD/JPY"]},
                target_brokers=["ib"],
                fallback_brokers=["manual"],
            )
        )

        # Test FX major routing
        fx_order = NewOrderSingle(
            cl_ord_id="TEST_FX",
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IOC,
            transact_time=datetime.now(timezone.utc),
        )

        broker = router.route_order(fx_order)
        assert broker == "ib"

        # Test non-FX major routing
        exotic_order = NewOrderSingle(
            cl_ord_id="TEST_EXOTIC",
            symbol="USD/TRY",
            side=Side.SELL,
            order_qty=50000,
            ord_type=OrdType.LIMIT,
            price=8.5000,
            time_in_force=TimeInForce.DAY,
            transact_time=datetime.now(timezone.utc),
        )

        broker = router.route_order(exotic_order)
        assert broker != "ib"  # Should use default rule


class TestPerformanceAndLoad:
    """Test system performance under load."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_high_volume_order_flow(self, adapter_manager):
        """Test system under high order volume."""
        order_count = 100
        orders = []

        # Generate orders
        for i in range(order_count):
            order = NewOrderSingle(
                cl_ord_id=f"LOAD_TEST_{i}_{uuid.uuid4().hex[:8]}",
                symbol="EUR/USD",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                order_qty=10000 + (i * 100),
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
        for i, order in enumerate(orders):
            broker_type = "ib" if i < 50 else "manual"
            adapter = adapter_manager.adapters.get(broker_type)
            if adapter:
                task = adapter.submit_order(order)
                tasks.append((broker_type, task))

        # Wait for completion
        results = await asyncio.gather(
            *[task for _, task in tasks], return_exceptions=True
        )

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # Calculate metrics
        successful = len([r for r in results if not isinstance(r, Exception)])
        orders_per_second = successful / duration

        # Performance assertions
        assert successful >= 90  # 90% success rate
        assert orders_per_second >= 10  # At least 10 orders/second

        logger.info(
            f"Performance test: {successful}/{order_count} orders in {duration:.2f}s "
            f"({orders_per_second:.1f} orders/sec)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
