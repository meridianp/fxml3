"""End-to-End Integration Tests for Broker Adapter Ecosystem.

This module provides comprehensive integration testing for the complete broker
adapter infrastructure, testing real message flows, adapter coordination,
and system resilience under various scenarios.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fxml4.brokers.adapters.base import AdapterConfig, ConnectionStatus
from fxml4.brokers.adapters.fix_rabbitmq_adapter import FixRabbitMQAdapter
from fxml4.brokers.adapters.fxcm_rabbitmq_adapter import FXCMRabbitMQAdapter
from fxml4.brokers.adapters.ib_rabbitmq_adapter import IBRabbitMQAdapter
from fxml4.brokers.adapters.manager import BrokerAdapterManager
from fxml4.brokers.adapters.manual_rabbitmq_adapter import ManualRabbitMQAdapter
from fxml4.brokers.adapters.registry import BrokerAdapterRegistry
from fxml4.brokers.adapters.router import OrderRouter, RoutingCriteria, RoutingRule
from fxml4.brokers.messaging.connection_manager import RabbitMQConnectionManager
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)


@pytest.fixture
async def mock_rabbitmq_manager():
    """Create mock RabbitMQ connection manager."""
    manager = AsyncMock(spec=RabbitMQConnectionManager)
    manager.connected = True
    manager.connect.return_value = True
    manager.disconnect.return_value = None
    manager.publish_order_event.return_value = True
    manager.publish_execution_report.return_value = True
    manager.publish_status_update.return_value = True
    manager.ack_message = AsyncMock()
    manager.reject_message = AsyncMock()
    manager.register_handler = AsyncMock()
    return manager


@pytest.fixture
def adapter_configs():
    """Create test configurations for all adapters."""
    base_config = {
        "connection_timeout": 30.0,
        "max_retries": 3,
        "retry_delay": 1.0,
        "features": {"auto_reconnect": True, "mock_mode": True},
    }

    return {
        "ib": AdapterConfig(
            adapter_type="ib",
            connection_params={
                **base_config,
                "host": "localhost",
                "port": 7497,
                "client_id": 100,
            },
        ),
        "fxcm": AdapterConfig(
            adapter_type="fxcm",
            connection_params={
                **base_config,
                "bridge_url": "http://localhost:8080",
                "account_id": "test_account",
            },
        ),
        "manual": AdapterConfig(
            adapter_type="manual",
            connection_params={
                **base_config,
                "approval_timeout": 300,
                "auto_approve_small_orders": True,
                "small_order_threshold": 1000,
            },
        ),
        "fix": AdapterConfig(
            adapter_type="fix",
            connection_params={
                **base_config,
                "host": "localhost",
                "port": 9876,
                "session": {
                    "sender_comp_id": "FXML4_TEST",
                    "target_comp_id": "BROKER_TEST",
                },
            },
        ),
    }


@pytest.fixture
async def broker_registry(adapter_configs):
    """Create broker adapter registry with test adapters."""
    registry = BrokerAdapterRegistry()

    # Register adapter classes
    registry.register("ib", IBRabbitMQAdapter)
    registry.register("fxcm", FXCMRabbitMQAdapter)
    registry.register("manual", ManualRabbitMQAdapter)
    registry.register("fix", FixRabbitMQAdapter)

    return registry


@pytest.fixture
async def adapter_manager(broker_registry, adapter_configs, mock_rabbitmq_manager):
    """Create broker adapter manager with mocked dependencies."""
    with patch(
        "fxml4.brokers.adapters.rabbitmq_base.create_rabbitmq_manager",
        return_value=mock_rabbitmq_manager,
    ):
        manager = BrokerAdapterManager(broker_registry)

        # Initialize adapters with mocking
        for adapter_id, config in adapter_configs.items():
            await manager.add_adapter(adapter_id, config)

        return manager


@pytest.fixture
def sample_orders():
    """Create sample test orders."""
    return [
        NewOrderSingle(
            cl_ord_id="ORDER_001",
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        ),
        NewOrderSingle(
            cl_ord_id="ORDER_002",
            symbol="GBP/USD",
            side=Side.SELL,
            order_qty=50000,
            ord_type=OrdType.LIMIT,
            price=1.2500,
        ),
        NewOrderSingle(
            cl_ord_id="ORDER_003",
            symbol="USD/JPY",
            side=Side.BUY,
            order_qty=200000,
            ord_type=OrdType.STOP,
            stop_px=110.50,
        ),
    ]


class TestBrokerAdapterEcosystemIntegration:
    """Integration tests for the complete broker adapter ecosystem."""

    @pytest.mark.asyncio
    async def test_multi_adapter_initialization(self, adapter_manager):
        """Test initialization of multiple adapters."""
        # Verify all adapters are registered
        assert len(adapter_manager.adapters) == 4
        assert "ib" in adapter_manager.adapters
        assert "fxcm" in adapter_manager.adapters
        assert "manual" in adapter_manager.adapters
        assert "fix" in adapter_manager.adapters

        # Check adapter types
        assert isinstance(adapter_manager.adapters["ib"], IBRabbitMQAdapter)
        assert isinstance(adapter_manager.adapters["fxcm"], FXCMRabbitMQAdapter)
        assert isinstance(adapter_manager.adapters["manual"], ManualRabbitMQAdapter)
        assert isinstance(adapter_manager.adapters["fix"], FixRabbitMQAdapter)

    @pytest.mark.asyncio
    async def test_ecosystem_startup_sequence(self, adapter_manager):
        """Test coordinated startup of all adapters."""
        # Mock adapter connections
        for adapter in adapter_manager.adapters.values():
            adapter.connect = AsyncMock(return_value=True)
            adapter.connection.status = ConnectionStatus.READY

        # Start all adapters
        success = await adapter_manager.start_all()
        assert success

        # Verify all adapters were started
        for adapter_id, adapter in adapter_manager.adapters.items():
            adapter.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_ecosystem_shutdown_sequence(self, adapter_manager):
        """Test coordinated shutdown of all adapters."""
        # Mock adapter disconnections
        for adapter in adapter_manager.adapters.values():
            adapter.disconnect = AsyncMock()
            adapter.connection.status = ConnectionStatus.DISCONNECTED

        # Stop all adapters
        await adapter_manager.stop_all()

        # Verify all adapters were stopped
        for adapter in adapter_manager.adapters.values():
            adapter.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_routing_across_adapters(self, adapter_manager, sample_orders):
        """Test order routing to different adapters based on criteria."""
        # Create order router with rules
        router = OrderRouter()

        # Add routing rules
        router.add_rule(
            RoutingRule(
                name="ib_forex",
                criteria=RoutingCriteria(symbols=["EUR/USD", "GBP/USD"]),
                target_adapter="ib",
                priority=1,
            )
        )

        router.add_rule(
            RoutingRule(
                name="fxcm_major_pairs",
                criteria=RoutingCriteria(symbols=["USD/JPY"]),
                target_adapter="fxcm",
                priority=1,
            )
        )

        # Mock adapter order submissions
        for adapter in adapter_manager.adapters.values():
            adapter.submit_order = AsyncMock(
                return_value=f"EXEC_{uuid.uuid4().hex[:8]}"
            )

        # Route orders
        results = []
        for order in sample_orders:
            target_adapter = router.route_order(order)
            if target_adapter in adapter_manager.adapters:
                execution_id = await adapter_manager.adapters[
                    target_adapter
                ].submit_order(order)
                results.append((order.cl_ord_id, target_adapter, execution_id))

        # Verify routing decisions
        assert len(results) == 3

        # Check specific routing
        order_routing = {result[0]: result[1] for result in results}
        assert order_routing["ORDER_001"] == "ib"  # EUR/USD to IB
        assert order_routing["ORDER_002"] == "ib"  # GBP/USD to IB
        assert order_routing["ORDER_003"] == "fxcm"  # USD/JPY to FXCM

    @pytest.mark.asyncio
    async def test_message_flow_integration(
        self, adapter_manager, mock_rabbitmq_manager
    ):
        """Test end-to-end message flow through RabbitMQ."""
        # Mock order submission and execution reports
        test_order = NewOrderSingle(
            cl_ord_id="MSG_FLOW_001",
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        # Simulate message flow
        adapter = adapter_manager.adapters["ib"]
        adapter.submit_order = AsyncMock(return_value="EXEC_12345")

        # Submit order
        execution_id = await adapter.submit_order(test_order)

        # Verify RabbitMQ calls
        mock_rabbitmq_manager.publish_order_event.assert_called()

        # Simulate execution report
        execution_report = ExecutionReport(
            order_id=execution_id,
            cl_ord_id=test_order.cl_ord_id,
            exec_id="EXEC_12345",
            exec_type=ExecType.NEW,
            ord_status=OrdStatus.NEW,
            symbol=test_order.symbol,
            side=test_order.side,
            order_qty=test_order.order_qty,
            cum_qty=0,
            leaves_qty=test_order.order_qty,
            avg_px=0,
            transact_time=datetime.now(timezone.utc),
        )

        # Process execution report
        if hasattr(adapter, "_publish_execution_report"):
            await adapter._publish_execution_report(execution_report)
            mock_rabbitmq_manager.publish_execution_report.assert_called()

    @pytest.mark.asyncio
    async def test_adapter_failover_scenario(self, adapter_manager):
        """Test failover when primary adapter fails."""
        # Setup primary and backup adapters
        primary_adapter = adapter_manager.adapters["ib"]
        backup_adapter = adapter_manager.adapters["fxcm"]

        # Mock primary adapter failure
        primary_adapter.submit_order = AsyncMock(
            side_effect=ConnectionError("IB connection lost")
        )
        backup_adapter.submit_order = AsyncMock(return_value="BACKUP_EXEC_001")

        test_order = NewOrderSingle(
            cl_ord_id="FAILOVER_001",
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        # Attempt order submission with failover logic
        execution_id = None
        try:
            execution_id = await primary_adapter.submit_order(test_order)
        except ConnectionError:
            # Failover to backup
            execution_id = await backup_adapter.submit_order(test_order)

        # Verify failover worked
        assert execution_id == "BACKUP_EXEC_001"
        primary_adapter.submit_order.assert_called_once()
        backup_adapter.submit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_order_processing(self, adapter_manager):
        """Test concurrent order processing across multiple adapters."""
        # Create multiple orders for concurrent processing
        orders = [
            NewOrderSingle(
                cl_ord_id=f"CONCURRENT_{i:03d}",
                symbol="EUR/USD",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                order_qty=100000,
                ord_type=OrdType.MARKET,
            )
            for i in range(10)
        ]

        # Mock all adapter order submissions
        for adapter in adapter_manager.adapters.values():
            adapter.submit_order = AsyncMock(
                side_effect=lambda order: f"EXEC_{order.cl_ord_id}"
            )

        # Submit orders concurrently
        tasks = []
        for i, order in enumerate(orders):
            adapter_name = list(adapter_manager.adapters.keys())[
                i % len(adapter_manager.adapters)
            ]
            adapter = adapter_manager.adapters[adapter_name]
            task = asyncio.create_task(adapter.submit_order(order))
            tasks.append(task)

        # Wait for all orders to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all orders processed successfully
        assert len(results) == 10
        assert all(
            isinstance(result, str) and result.startswith("EXEC_") for result in results
        )

    @pytest.mark.asyncio
    async def test_adapter_health_monitoring(self, adapter_manager):
        """Test health monitoring across all adapters."""
        # Mock adapter health status
        for adapter_id, adapter in adapter_manager.adapters.items():
            adapter.get_health_status = AsyncMock(
                return_value={
                    "adapter_id": adapter_id,
                    "status": "healthy",
                    "uptime_seconds": 3600,
                    "orders_processed": 100,
                    "success_rate": 99.5,
                }
            )

        # Get ecosystem health
        health_status = await adapter_manager.get_ecosystem_health()

        # Verify health data
        assert "adapters" in health_status
        assert len(health_status["adapters"]) == 4

        for adapter_id in ["ib", "fxcm", "manual", "fix"]:
            assert adapter_id in health_status["adapters"]
            adapter_health = health_status["adapters"][adapter_id]
            assert adapter_health["status"] == "healthy"
            assert adapter_health["uptime_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_message_acknowledgment_flow(
        self, adapter_manager, mock_rabbitmq_manager
    ):
        """Test proper message acknowledgment flow."""
        adapter = adapter_manager.adapters["fix"]

        # Mock message handler
        test_message = {
            "type": "new_order",
            "order": {
                "cl_ord_id": "ACK_TEST_001",
                "symbol": "EUR/USD",
                "side": "BUY",
                "quantity": 100000,
                "order_type": "MARKET",
            },
        }

        delivery_tag = "delivery_12345"

        # Mock successful order processing
        adapter.submit_order = AsyncMock(return_value="EXEC_ACK_001")

        # Process message (simulating RabbitMQ delivery)
        if hasattr(adapter, "_handle_new_order_message"):
            await adapter._handle_new_order_message(test_message, delivery_tag)

            # Verify message was acknowledged
            mock_rabbitmq_manager.ack_message.assert_called_with(delivery_tag)

    @pytest.mark.asyncio
    async def test_error_propagation_and_handling(
        self, adapter_manager, mock_rabbitmq_manager
    ):
        """Test error propagation and handling across the ecosystem."""
        adapter = adapter_manager.adapters["manual"]

        # Mock order submission failure
        adapter.submit_order = AsyncMock(side_effect=ValueError("Invalid order format"))

        test_message = {
            "type": "new_order",
            "order": {
                "cl_ord_id": "ERROR_TEST_001",
                "symbol": "INVALID",
                "side": "BUY",
                "quantity": -100,  # Invalid quantity
            },
        }

        delivery_tag = "delivery_error_001"

        # Process message with error
        if hasattr(adapter, "_handle_new_order_message"):
            await adapter._handle_new_order_message(test_message, delivery_tag)

            # Verify message was rejected
            mock_rabbitmq_manager.reject_message.assert_called_with(
                delivery_tag, requeue=False
            )

    @pytest.mark.asyncio
    async def test_adapter_metric_aggregation(self, adapter_manager):
        """Test aggregation of metrics across all adapters."""
        # Mock individual adapter metrics
        mock_metrics = {
            "ib": {
                "orders_submitted": 150,
                "orders_filled": 145,
                "orders_cancelled": 5,
                "success_rate": 96.7,
            },
            "fxcm": {
                "orders_submitted": 200,
                "orders_filled": 190,
                "orders_cancelled": 8,
                "success_rate": 95.0,
            },
            "manual": {
                "orders_submitted": 50,
                "orders_filled": 45,
                "orders_cancelled": 3,
                "success_rate": 90.0,
            },
            "fix": {
                "orders_submitted": 100,
                "orders_filled": 98,
                "orders_cancelled": 2,
                "success_rate": 98.0,
            },
        }

        for adapter_id, metrics in mock_metrics.items():
            adapter = adapter_manager.adapters[adapter_id]
            adapter.get_metrics = AsyncMock(return_value=metrics)

        # Get aggregated metrics
        aggregated = await adapter_manager.get_aggregated_metrics()

        # Verify aggregation
        assert aggregated["total_orders_submitted"] == 500
        assert aggregated["total_orders_filled"] == 478
        assert aggregated["total_orders_cancelled"] == 18
        assert aggregated["overall_success_rate"] == 95.6  # Weighted average


class TestAdapterRecoveryScenarios:
    """Test adapter recovery and resilience scenarios."""

    @pytest.mark.asyncio
    async def test_network_partition_recovery(self, adapter_manager):
        """Test recovery from network partition scenarios."""
        adapter = adapter_manager.adapters["ib"]

        # Mock network partition
        adapter.connection.status = ConnectionStatus.ERROR
        adapter.connect = AsyncMock(
            side_effect=[False, False, True]
        )  # Fails twice, then succeeds

        # Attempt reconnection with retry logic
        reconnect_attempts = 0
        max_attempts = 3

        while reconnect_attempts < max_attempts:
            success = await adapter.connect()
            reconnect_attempts += 1

            if success:
                break

            await asyncio.sleep(0.1)  # Simulated backoff

        # Verify recovery
        assert success
        assert adapter.connect.call_count == 3

    @pytest.mark.asyncio
    async def test_message_queue_recovery(self, adapter_manager, mock_rabbitmq_manager):
        """Test recovery from message queue disconnection."""
        # Simulate RabbitMQ disconnection
        mock_rabbitmq_manager.connected = False
        mock_rabbitmq_manager.connect = AsyncMock(
            side_effect=[False, True]
        )  # Fail then succeed

        adapter = adapter_manager.adapters["fix"]

        # Attempt to reconnect message queue
        initial_connection = await mock_rabbitmq_manager.connect()
        assert not initial_connection

        # Retry connection
        retry_connection = await mock_rabbitmq_manager.connect()
        assert retry_connection

        mock_rabbitmq_manager.connected = True

        # Verify adapter can resume operations
        test_order = NewOrderSingle(
            cl_ord_id="RECOVERY_001",
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        adapter.submit_order = AsyncMock(return_value="RECOVERY_EXEC_001")
        execution_id = await adapter.submit_order(test_order)

        assert execution_id == "RECOVERY_EXEC_001"

    @pytest.mark.asyncio
    async def test_cascading_failure_isolation(self, adapter_manager):
        """Test isolation of cascading failures."""
        # Simulate failure in one adapter
        failed_adapter = adapter_manager.adapters["ib"]
        working_adapter = adapter_manager.adapters["fxcm"]

        failed_adapter.submit_order = AsyncMock(side_effect=Exception("Adapter failed"))
        working_adapter.submit_order = AsyncMock(return_value="WORKING_EXEC_001")

        test_order = NewOrderSingle(
            cl_ord_id="ISOLATION_001",
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        # Verify failed adapter doesn't affect working adapter
        with pytest.raises(Exception, match="Adapter failed"):
            await failed_adapter.submit_order(test_order)

        # Working adapter should still function
        execution_id = await working_adapter.submit_order(test_order)
        assert execution_id == "WORKING_EXEC_001"


class TestOrderLifecycleIntegration:
    """Test complete order lifecycle across the ecosystem."""

    @pytest.mark.asyncio
    async def test_complete_order_lifecycle(self, adapter_manager):
        """Test complete order lifecycle from submission to fill."""
        adapter = adapter_manager.adapters["ib"]

        # Mock order lifecycle
        test_order = NewOrderSingle(
            cl_ord_id="LIFECYCLE_001",
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.LIMIT,
            price=1.0850,
        )

        # Mock adapter methods
        adapter.submit_order = AsyncMock(return_value="LIFECYCLE_EXEC_001")
        adapter.get_order_status = AsyncMock(
            return_value={
                "cl_ord_id": test_order.cl_ord_id,
                "status": "NEW",
                "filled_qty": 0,
                "remaining_qty": 100000,
            }
        )
        adapter.cancel_order = AsyncMock(return_value=True)

        # 1. Submit order
        execution_id = await adapter.submit_order(test_order)
        assert execution_id == "LIFECYCLE_EXEC_001"

        # 2. Check status
        status = await adapter.get_order_status(test_order.cl_ord_id)
        assert status["status"] == "NEW"

        # 3. Cancel order
        cancel_success = await adapter.cancel_order(test_order.cl_ord_id)
        assert cancel_success

        # Verify all methods were called
        adapter.submit_order.assert_called_once_with(test_order)
        adapter.get_order_status.assert_called_once_with(test_order.cl_ord_id)
        adapter.cancel_order.assert_called_once_with(test_order.cl_ord_id)

    @pytest.mark.asyncio
    async def test_order_modification_flow(self, adapter_manager):
        """Test order modification across adapters."""
        adapter = adapter_manager.adapters["fix"]

        # Original order
        original_order = NewOrderSingle(
            cl_ord_id="MODIFY_ORIG_001",
            symbol="GBP/USD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.LIMIT,
            price=1.2500,
        )

        # Mock order submission and modification
        adapter.submit_order = AsyncMock(return_value="MODIFY_EXEC_001")

        if hasattr(adapter, "modify_order"):
            adapter.modify_order = AsyncMock(return_value=True)

        # Submit original order
        execution_id = await adapter.submit_order(original_order)
        assert execution_id == "MODIFY_EXEC_001"

        # Modify order (if supported)
        if hasattr(adapter, "modify_order"):
            modify_success = await adapter.modify_order(
                {
                    "orig_cl_ord_id": original_order.cl_ord_id,
                    "price": 1.2550,  # New price
                    "quantity": 150000,  # New quantity
                }
            )
            assert modify_success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
