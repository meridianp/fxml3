"""
Comprehensive retrospective test coverage for Adapter Management System.

This module provides comprehensive test coverage for the FXML4 Broker Adapter
Management System, which handles registration, lifecycle management, and
coordination of multiple broker adapters in a unified trading environment.

Following TDD principles with retrospective testing approach:
- Testing existing production adapter management functionality
- Ensuring comprehensive coverage of registry and manager components
- Validating multi-adapter coordination and error handling
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from fxml4.brokers.adapters.adapter_management import (
    AdapterInfo,
    AdapterState,
    BrokerAdapterManager,
    BrokerAdapterRegistry,
    HealthStatus,
    ManagementError,
    RegistryError,
)
from fxml4.brokers.adapters.base import (
    AdapterConfig,
    BrokerAdapter,
    ConnectionStatus,
    OrderInfo,
    OrderStatus,
)
from fxml4.core.exceptions import BrokerError, ValidationError
from fxml4.core.messaging import MessageHandler
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle


class TestBrokerAdapterRegistry:
    """Test broker adapter registry functionality."""

    def test_registry_initialization(self):
        """Test registry initializes correctly with empty state."""
        registry = BrokerAdapterRegistry()

        assert len(registry.adapters) == 0
        assert len(registry.adapter_configs) == 0
        assert registry.default_adapter is None
        assert registry.is_initialized is True

    def test_register_adapter_successful(self):
        """Test successful adapter registration."""
        registry = BrokerAdapterRegistry()

        config = AdapterConfig(
            adapter_type="ib", name="ib_primary", endpoint="localhost:7497"
        )

        mock_adapter = MagicMock(spec=BrokerAdapter)
        mock_adapter.adapter_type = "ib"
        mock_adapter.config = config

        result = registry.register_adapter("ib_primary", mock_adapter, config)

        assert result is True
        assert "ib_primary" in registry.adapters
        assert registry.adapters["ib_primary"] == mock_adapter
        assert registry.adapter_configs["ib_primary"] == config

    def test_register_duplicate_adapter_name_fails(self):
        """Test registration fails for duplicate adapter names."""
        registry = BrokerAdapterRegistry()

        config = AdapterConfig(adapter_type="ib", name="ib_primary")
        mock_adapter = MagicMock(spec=BrokerAdapter)

        # First registration succeeds
        registry.register_adapter("ib_primary", mock_adapter, config)

        # Second registration with same name fails
        with pytest.raises(RegistryError, match="Adapter already registered"):
            registry.register_adapter("ib_primary", mock_adapter, config)

    def test_register_adapter_validates_config(self):
        """Test adapter registration validates configuration."""
        registry = BrokerAdapterRegistry()

        invalid_configs = [
            None,
            AdapterConfig(adapter_type=""),  # Empty type
            AdapterConfig(adapter_type="invalid", name=""),  # Empty name
        ]

        mock_adapter = MagicMock(spec=BrokerAdapter)

        for config in invalid_configs:
            with pytest.raises(ValidationError):
                registry.register_adapter("test", mock_adapter, config)

    def test_unregister_adapter_successful(self):
        """Test successful adapter unregistration."""
        registry = BrokerAdapterRegistry()

        config = AdapterConfig(adapter_type="ib", name="ib_primary")
        mock_adapter = MagicMock(spec=BrokerAdapter)

        registry.register_adapter("ib_primary", mock_adapter, config)
        assert "ib_primary" in registry.adapters

        result = registry.unregister_adapter("ib_primary")

        assert result is True
        assert "ib_primary" not in registry.adapters
        assert "ib_primary" not in registry.adapter_configs

    def test_unregister_nonexistent_adapter(self):
        """Test unregistering non-existent adapter returns False."""
        registry = BrokerAdapterRegistry()

        result = registry.unregister_adapter("nonexistent")

        assert result is False

    def test_get_adapter_by_name(self):
        """Test retrieving adapter by name."""
        registry = BrokerAdapterRegistry()

        config = AdapterConfig(adapter_type="ib", name="ib_primary")
        mock_adapter = MagicMock(spec=BrokerAdapter)

        registry.register_adapter("ib_primary", mock_adapter, config)

        retrieved = registry.get_adapter("ib_primary")
        assert retrieved == mock_adapter

        # Test non-existent adapter
        assert registry.get_adapter("nonexistent") is None

    def test_get_adapters_by_type(self):
        """Test retrieving adapters by type."""
        registry = BrokerAdapterRegistry()

        # Register multiple IB adapters
        for i in range(3):
            config = AdapterConfig(adapter_type="ib", name=f"ib_{i}")
            mock_adapter = MagicMock(spec=BrokerAdapter)
            mock_adapter.adapter_type = "ib"
            registry.register_adapter(f"ib_{i}", mock_adapter, config)

        # Register FXCM adapter
        fxcm_config = AdapterConfig(adapter_type="fxcm", name="fxcm_primary")
        fxcm_adapter = MagicMock(spec=BrokerAdapter)
        fxcm_adapter.adapter_type = "fxcm"
        registry.register_adapter("fxcm_primary", fxcm_adapter, fxcm_config)

        ib_adapters = registry.get_adapters_by_type("ib")
        assert len(ib_adapters) == 3

        fxcm_adapters = registry.get_adapters_by_type("fxcm")
        assert len(fxcm_adapters) == 1

        nonexistent = registry.get_adapters_by_type("nonexistent")
        assert len(nonexistent) == 0

    def test_set_default_adapter(self):
        """Test setting default adapter."""
        registry = BrokerAdapterRegistry()

        config = AdapterConfig(adapter_type="ib", name="ib_primary")
        mock_adapter = MagicMock(spec=BrokerAdapter)

        registry.register_adapter("ib_primary", mock_adapter, config)

        result = registry.set_default_adapter("ib_primary")
        assert result is True
        assert registry.default_adapter == "ib_primary"

        # Test setting non-existent adapter as default
        result = registry.set_default_adapter("nonexistent")
        assert result is False
        assert registry.default_adapter == "ib_primary"  # Unchanged

    def test_list_adapters(self):
        """Test listing all registered adapters."""
        registry = BrokerAdapterRegistry()

        # Empty registry
        adapters = registry.list_adapters()
        assert len(adapters) == 0

        # Add adapters
        for i in range(3):
            config = AdapterConfig(adapter_type="ib", name=f"ib_{i}")
            mock_adapter = MagicMock(spec=BrokerAdapter)
            registry.register_adapter(f"ib_{i}", mock_adapter, config)

        adapters = registry.list_adapters()
        assert len(adapters) == 3
        assert "ib_0" in adapters
        assert "ib_1" in adapters
        assert "ib_2" in adapters

    def test_registry_state_persistence(self):
        """Test registry state remains consistent across operations."""
        registry = BrokerAdapterRegistry()

        # Register multiple adapters
        configs = []
        for i in range(5):
            config = AdapterConfig(adapter_type=f"type_{i}", name=f"adapter_{i}")
            mock_adapter = MagicMock(spec=BrokerAdapter)
            mock_adapter.adapter_type = f"type_{i}"

            registry.register_adapter(f"adapter_{i}", mock_adapter, config)
            configs.append(config)

        assert len(registry.adapters) == 5
        assert len(registry.adapter_configs) == 5

        # Unregister some adapters
        registry.unregister_adapter("adapter_1")
        registry.unregister_adapter("adapter_3")

        assert len(registry.adapters) == 3
        assert len(registry.adapter_configs) == 3
        assert "adapter_1" not in registry.adapters
        assert "adapter_3" not in registry.adapters

        # Remaining adapters should be intact
        for i in [0, 2, 4]:
            assert f"adapter_{i}" in registry.adapters
            assert registry.adapter_configs[f"adapter_{i}"] == configs[i]


class TestBrokerAdapterManager:
    """Test broker adapter manager functionality."""

    @pytest.fixture
    def manager(self):
        """Create manager fixture for testing."""
        return BrokerAdapterManager()

    @pytest.fixture
    def mock_adapter(self):
        """Create mock adapter for testing."""
        adapter = AsyncMock(spec=BrokerAdapter)
        adapter.adapter_type = "ib"
        adapter.config = AdapterConfig(adapter_type="ib", name="ib_test")
        adapter.connection = MagicMock()
        adapter.connection.status = ConnectionStatus.DISCONNECTED
        return adapter

    def test_manager_initialization(self, manager):
        """Test manager initializes correctly."""
        assert isinstance(manager.registry, BrokerAdapterRegistry)
        assert len(manager.adapter_states) == 0
        assert manager.message_handler is not None
        assert manager.health_monitor is not None
        assert manager.is_running is False

    @pytest.mark.asyncio
    async def test_add_adapter_successful(self, manager, mock_adapter):
        """Test successful adapter addition to manager."""
        config = mock_adapter.config

        result = await manager.add_adapter("ib_test", mock_adapter, config)

        assert result is True
        assert "ib_test" in manager.registry.adapters
        assert "ib_test" in manager.adapter_states
        assert manager.adapter_states["ib_test"].state == AdapterState.REGISTERED

    @pytest.mark.asyncio
    async def test_add_adapter_validates_configuration(self, manager):
        """Test adapter addition validates configuration."""
        mock_adapter = AsyncMock(spec=BrokerAdapter)
        invalid_config = None

        with pytest.raises(ValidationError):
            await manager.add_adapter("invalid", mock_adapter, invalid_config)

    @pytest.mark.asyncio
    async def test_remove_adapter_successful(self, manager, mock_adapter):
        """Test successful adapter removal."""
        config = mock_adapter.config
        await manager.add_adapter("ib_test", mock_adapter, config)

        result = await manager.remove_adapter("ib_test")

        assert result is True
        assert "ib_test" not in manager.registry.adapters
        assert "ib_test" not in manager.adapter_states

    @pytest.mark.asyncio
    async def test_start_adapter_successful(self, manager, mock_adapter):
        """Test successful adapter startup."""
        config = mock_adapter.config
        await manager.add_adapter("ib_test", mock_adapter, config)

        mock_adapter.connect.return_value = True
        mock_adapter.connection.status = ConnectionStatus.CONNECTED

        result = await manager.start_adapter("ib_test")

        assert result is True
        mock_adapter.connect.assert_called_once()
        assert manager.adapter_states["ib_test"].state == AdapterState.STARTED

    @pytest.mark.asyncio
    async def test_start_adapter_connection_failure(self, manager, mock_adapter):
        """Test adapter startup with connection failure."""
        config = mock_adapter.config
        await manager.add_adapter("ib_test", mock_adapter, config)

        mock_adapter.connect.return_value = False

        result = await manager.start_adapter("ib_test")

        assert result is False
        assert manager.adapter_states["ib_test"].state == AdapterState.ERROR

    @pytest.mark.asyncio
    async def test_stop_adapter_successful(self, manager, mock_adapter):
        """Test successful adapter shutdown."""
        config = mock_adapter.config
        await manager.add_adapter("ib_test", mock_adapter, config)
        await manager.start_adapter("ib_test")

        mock_adapter.disconnect.return_value = True

        result = await manager.stop_adapter("ib_test")

        assert result is True
        mock_adapter.disconnect.assert_called_once()
        assert manager.adapter_states["ib_test"].state == AdapterState.STOPPED

    @pytest.mark.asyncio
    async def test_start_all_adapters(self, manager):
        """Test starting all registered adapters."""
        # Add multiple adapters
        adapters = []
        for i in range(3):
            adapter = AsyncMock(spec=BrokerAdapter)
            adapter.adapter_type = "ib"
            adapter.config = AdapterConfig(adapter_type="ib", name=f"ib_{i}")
            adapter.connect.return_value = True
            adapter.connection.status = ConnectionStatus.CONNECTED
            adapters.append(adapter)

            await manager.add_adapter(f"ib_{i}", adapter, adapter.config)

        results = await manager.start_all_adapters()

        assert len(results) == 3
        assert all(results.values())

        for i, adapter in enumerate(adapters):
            adapter.connect.assert_called_once()
            assert manager.adapter_states[f"ib_{i}"].state == AdapterState.STARTED

    @pytest.mark.asyncio
    async def test_stop_all_adapters(self, manager):
        """Test stopping all registered adapters."""
        # Add and start multiple adapters
        adapters = []
        for i in range(3):
            adapter = AsyncMock(spec=BrokerAdapter)
            adapter.adapter_type = "ib"
            adapter.config = AdapterConfig(adapter_type="ib", name=f"ib_{i}")
            adapter.connect.return_value = True
            adapter.disconnect.return_value = True
            adapters.append(adapter)

            await manager.add_adapter(f"ib_{i}", adapter, adapter.config)
            await manager.start_adapter(f"ib_{i}")

        results = await manager.stop_all_adapters()

        assert len(results) == 3
        assert all(results.values())

        for i, adapter in enumerate(adapters):
            adapter.disconnect.assert_called_once()
            assert manager.adapter_states[f"ib_{i}"].state == AdapterState.STOPPED

    @pytest.mark.asyncio
    async def test_submit_order_to_default_adapter(self, manager, mock_adapter):
        """Test order submission to default adapter."""
        config = mock_adapter.config
        await manager.add_adapter("ib_test", mock_adapter, config)
        await manager.start_adapter("ib_test")
        manager.registry.set_default_adapter("ib_test")

        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        mock_adapter.submit_order.return_value = True

        result = await manager.submit_order(order)

        assert result is True
        mock_adapter.submit_order.assert_called_once_with(order)

    @pytest.mark.asyncio
    async def test_submit_order_to_specific_adapter(self, manager, mock_adapter):
        """Test order submission to specific adapter."""
        config = mock_adapter.config
        await manager.add_adapter("ib_test", mock_adapter, config)
        await manager.start_adapter("ib_test")

        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        mock_adapter.submit_order.return_value = True

        result = await manager.submit_order(order, adapter_name="ib_test")

        assert result is True
        mock_adapter.submit_order.assert_called_once_with(order)

    @pytest.mark.asyncio
    async def test_submit_order_no_default_adapter_fails(self, manager):
        """Test order submission fails when no default adapter set."""
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        with pytest.raises(ManagementError, match="No default adapter"):
            await manager.submit_order(order)

    @pytest.mark.asyncio
    async def test_cancel_order_routing(self, manager, mock_adapter):
        """Test order cancellation routing to correct adapter."""
        config = mock_adapter.config
        await manager.add_adapter("ib_test", mock_adapter, config)
        await manager.start_adapter("ib_test")

        # Track order submission
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        mock_adapter.submit_order.return_value = True
        await manager.submit_order(order, adapter_name="ib_test")

        # Cancel order
        mock_adapter.cancel_order.return_value = True
        result = await manager.cancel_order("ORDER-123")

        assert result is True
        mock_adapter.cancel_order.assert_called_once_with("ORDER-123")

    @pytest.mark.asyncio
    async def test_get_order_status_routing(self, manager, mock_adapter):
        """Test order status retrieval routing."""
        config = mock_adapter.config
        await manager.add_adapter("ib_test", mock_adapter, config)
        await manager.start_adapter("ib_test")

        # Mock order status
        order_info = OrderInfo(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000.0,
            status=OrderStatus.FILLED,
        )
        mock_adapter.get_order_status.return_value = order_info

        # Submit order first to establish routing
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )
        await manager.submit_order(order, adapter_name="ib_test")

        # Get order status
        status = await manager.get_order_status("ORDER-123")

        assert status == order_info
        mock_adapter.get_order_status.assert_called_once_with("ORDER-123")


class TestBrokerAdapterManagerHealthMonitoring:
    """Test health monitoring functionality."""

    @pytest.fixture
    def manager(self):
        """Create manager fixture for testing."""
        return BrokerAdapterManager()

    @pytest.mark.asyncio
    async def test_health_check_all_adapters(self, manager):
        """Test health check across all adapters."""
        # Add multiple adapters with different health states
        adapters = []
        for i in range(3):
            adapter = AsyncMock(spec=BrokerAdapter)
            adapter.adapter_type = "ib"
            adapter.config = AdapterConfig(adapter_type="ib", name=f"ib_{i}")
            adapter.is_connected.return_value = i < 2  # First 2 connected
            adapters.append(adapter)

            await manager.add_adapter(f"ib_{i}", adapter, adapter.config)

        health_report = await manager.check_health()

        assert len(health_report) == 3
        assert health_report["ib_0"]["status"] == HealthStatus.HEALTHY
        assert health_report["ib_1"]["status"] == HealthStatus.HEALTHY
        assert health_report["ib_2"]["status"] == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_health_monitoring_service(self, manager):
        """Test continuous health monitoring service."""
        adapter = AsyncMock(spec=BrokerAdapter)
        adapter.adapter_type = "ib"
        adapter.config = AdapterConfig(adapter_type="ib", name="ib_test")
        adapter.is_connected.return_value = True

        await manager.add_adapter("ib_test", adapter, adapter.config)

        # Start health monitoring
        manager.health_check_interval = 0.1  # Fast interval for testing
        monitoring_task = asyncio.create_task(manager.start_health_monitoring())

        # Let it run for short time
        await asyncio.sleep(0.3)

        # Stop monitoring
        monitoring_task.cancel()

        # Health checks should have been performed
        assert adapter.is_connected.call_count >= 2

    @pytest.mark.asyncio
    async def test_adapter_failure_recovery(self, manager):
        """Test automatic adapter failure recovery."""
        adapter = AsyncMock(spec=BrokerAdapter)
        adapter.adapter_type = "ib"
        adapter.config = AdapterConfig(adapter_type="ib", name="ib_test")

        await manager.add_adapter("ib_test", adapter, adapter.config)
        await manager.start_adapter("ib_test")

        # Simulate adapter failure
        adapter.is_connected.return_value = False
        adapter.connect.return_value = True

        # Trigger recovery
        await manager.recover_failed_adapter("ib_test")

        # Should attempt reconnection
        assert adapter.connect.call_count >= 1
        assert manager.adapter_states["ib_test"].state == AdapterState.STARTED

    @pytest.mark.asyncio
    async def test_adapter_metrics_collection(self, manager):
        """Test collection of adapter performance metrics."""
        adapter = AsyncMock(spec=BrokerAdapter)
        adapter.adapter_type = "ib"
        adapter.config = AdapterConfig(adapter_type="ib", name="ib_test")

        # Mock metrics
        adapter.get_metrics.return_value = {
            "orders_submitted": 100,
            "orders_filled": 95,
            "orders_rejected": 5,
            "avg_latency_ms": 150,
            "uptime_seconds": 3600,
        }

        await manager.add_adapter("ib_test", adapter, adapter.config)

        metrics = await manager.get_adapter_metrics("ib_test")

        assert metrics["orders_submitted"] == 100
        assert metrics["orders_filled"] == 95
        assert metrics["avg_latency_ms"] == 150

    @pytest.mark.asyncio
    async def test_performance_monitoring(self, manager):
        """Test performance monitoring and alerting."""
        adapter = AsyncMock(spec=BrokerAdapter)
        adapter.adapter_type = "ib"
        adapter.config = AdapterConfig(adapter_type="ib", name="ib_test")

        # Mock poor performance metrics
        adapter.get_metrics.return_value = {
            "avg_latency_ms": 5000,  # High latency
            "error_rate": 0.15,  # High error rate
            "success_rate": 0.85,
        }

        await manager.add_adapter("ib_test", adapter, adapter.config)

        alerts = await manager.check_performance_alerts("ib_test")

        assert len(alerts) > 0
        alert_types = [alert["type"] for alert in alerts]
        assert "high_latency" in alert_types
        assert "high_error_rate" in alert_types


class TestBrokerAdapterManagerErrorHandling:
    """Test error handling and recovery mechanisms."""

    @pytest.fixture
    def manager(self):
        """Create manager fixture for testing."""
        return BrokerAdapterManager()

    @pytest.mark.asyncio
    async def test_adapter_startup_failure_handling(self, manager):
        """Test handling of adapter startup failures."""
        adapter = AsyncMock(spec=BrokerAdapter)
        adapter.adapter_type = "ib"
        adapter.config = AdapterConfig(adapter_type="ib", name="ib_test")
        adapter.connect.side_effect = BrokerError("Connection failed")

        await manager.add_adapter("ib_test", adapter, adapter.config)

        result = await manager.start_adapter("ib_test")

        assert result is False
        assert manager.adapter_states["ib_test"].state == AdapterState.ERROR
        assert manager.adapter_states["ib_test"].error_message == "Connection failed"

    @pytest.mark.asyncio
    async def test_order_submission_failure_handling(self, manager):
        """Test handling of order submission failures."""
        adapter = AsyncMock(spec=BrokerAdapter)
        adapter.adapter_type = "ib"
        adapter.config = AdapterConfig(adapter_type="ib", name="ib_test")
        adapter.submit_order.side_effect = BrokerError("Order rejected")

        await manager.add_adapter("ib_test", adapter, adapter.config)
        await manager.start_adapter("ib_test")
        manager.registry.set_default_adapter("ib_test")

        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        with pytest.raises(BrokerError, match="Order rejected"):
            await manager.submit_order(order)

    @pytest.mark.asyncio
    async def test_adapter_disconnection_handling(self, manager):
        """Test handling of unexpected adapter disconnections."""
        adapter = AsyncMock(spec=BrokerAdapter)
        adapter.adapter_type = "ib"
        adapter.config = AdapterConfig(adapter_type="ib", name="ib_test")

        await manager.add_adapter("ib_test", adapter, adapter.config)
        await manager.start_adapter("ib_test")

        # Simulate disconnection
        adapter.is_connected.return_value = False
        adapter.connection.status = ConnectionStatus.DISCONNECTED

        # Manager should detect disconnection
        await manager.handle_adapter_disconnection("ib_test")

        assert manager.adapter_states["ib_test"].state == AdapterState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_invalid_adapter_operations(self, manager):
        """Test operations on invalid or non-existent adapters."""
        # Operations on non-existent adapter
        with pytest.raises(ManagementError, match="Adapter not found"):
            await manager.start_adapter("nonexistent")

        with pytest.raises(ManagementError, match="Adapter not found"):
            await manager.stop_adapter("nonexistent")

        # Order operations without adapter
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        with pytest.raises(ManagementError):
            await manager.submit_order(order, adapter_name="nonexistent")

    @pytest.mark.asyncio
    async def test_concurrent_operation_safety(self, manager):
        """Test safety of concurrent adapter operations."""
        adapter = AsyncMock(spec=BrokerAdapter)
        adapter.adapter_type = "ib"
        adapter.config = AdapterConfig(adapter_type="ib", name="ib_test")
        adapter.connect.return_value = True
        adapter.disconnect.return_value = True

        await manager.add_adapter("ib_test", adapter, adapter.config)

        # Concurrent start/stop operations
        start_tasks = [manager.start_adapter("ib_test") for _ in range(5)]
        stop_tasks = [manager.stop_adapter("ib_test") for _ in range(5)]

        all_tasks = start_tasks + stop_tasks
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Should handle concurrent operations gracefully
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) > 0


class TestBrokerAdapterManagerIntegration:
    """Test integration scenarios and complex workflows."""

    @pytest.fixture
    def manager(self):
        """Create manager fixture for integration testing."""
        return BrokerAdapterManager()

    @pytest.mark.asyncio
    async def test_multi_adapter_order_routing(self, manager):
        """Test order routing across multiple adapters."""
        # Set up multiple adapters for different symbols
        adapters = {
            "ib_forex": AsyncMock(spec=BrokerAdapter),
            "fxcm_primary": AsyncMock(spec=BrokerAdapter),
            "manual_backup": AsyncMock(spec=BrokerAdapter),
        }

        for name, adapter in adapters.items():
            adapter.adapter_type = name.split("_")[0]
            adapter.config = AdapterConfig(adapter_type=adapter.adapter_type, name=name)
            adapter.submit_order.return_value = True

            await manager.add_adapter(name, adapter, adapter.config)
            await manager.start_adapter(name)

        # Set routing rules
        manager.set_symbol_routing("EURUSD", "ib_forex")
        manager.set_symbol_routing("GBPUSD", "fxcm_primary")

        # Submit orders for different symbols
        orders = [
            NewOrderSingle(
                cl_ord_id="EUR-1",
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
            ),
            NewOrderSingle(
                cl_ord_id="GBP-1",
                symbol="GBPUSD",
                side=Side.SELL,
                ord_type=OrdType.MARKET,
                order_qty=50000.0,
            ),
        ]

        for order in orders:
            await manager.submit_order(order)

        # Verify routing
        adapters["ib_forex"].submit_order.assert_called_once()
        adapters["fxcm_primary"].submit_order.assert_called_once()
        adapters["manual_backup"].submit_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_adapter_failover_mechanism(self, manager):
        """Test automatic failover between adapters."""
        # Primary and backup adapters
        primary = AsyncMock(spec=BrokerAdapter)
        primary.adapter_type = "ib"
        primary.config = AdapterConfig(adapter_type="ib", name="ib_primary")

        backup = AsyncMock(spec=BrokerAdapter)
        backup.adapter_type = "ib"
        backup.config = AdapterConfig(adapter_type="ib", name="ib_backup")

        await manager.add_adapter("ib_primary", primary, primary.config)
        await manager.add_adapter("ib_backup", backup, backup.config)
        await manager.start_adapter("ib_primary")
        await manager.start_adapter("ib_backup")

        # Configure failover
        manager.set_failover_adapter("ib_primary", "ib_backup")
        manager.registry.set_default_adapter("ib_primary")

        # Primary fails
        primary.submit_order.side_effect = BrokerError("Connection lost")
        primary.is_connected.return_value = False

        # Backup succeeds
        backup.submit_order.return_value = True
        backup.is_connected.return_value = True

        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        # Should automatically failover to backup
        result = await manager.submit_order(order)

        assert result is True
        backup.submit_order.assert_called_once_with(order)

    @pytest.mark.asyncio
    async def test_load_balancing_across_adapters(self, manager):
        """Test load balancing orders across multiple adapters."""
        # Set up multiple identical adapters
        adapters = []
        for i in range(3):
            adapter = AsyncMock(spec=BrokerAdapter)
            adapter.adapter_type = "ib"
            adapter.config = AdapterConfig(adapter_type="ib", name=f"ib_{i}")
            adapter.submit_order.return_value = True
            adapters.append(adapter)

            await manager.add_adapter(f"ib_{i}", adapter, adapter.config)
            await manager.start_adapter(f"ib_{i}")

        # Enable load balancing for IB adapters
        manager.enable_load_balancing("ib")

        # Submit multiple orders
        orders = []
        for i in range(9):  # Should distribute 3 orders per adapter
            order = NewOrderSingle(
                cl_ord_id=f"ORDER-{i}",
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=10000.0,
            )
            orders.append(order)
            await manager.submit_order(order)

        # Verify load distribution
        for adapter in adapters:
            assert adapter.submit_order.call_count == 3

    @pytest.mark.asyncio
    async def test_complete_trading_session_lifecycle(self, manager):
        """Test complete trading session from startup to shutdown."""
        # Add multiple adapters
        adapter_configs = [
            {"name": "ib_primary", "type": "ib"},
            {"name": "fxcm_secondary", "type": "fxcm"},
            {"name": "manual_backup", "type": "manual"},
        ]

        adapters = {}
        for config in adapter_configs:
            adapter = AsyncMock(spec=BrokerAdapter)
            adapter.adapter_type = config["type"]
            adapter.config = AdapterConfig(
                adapter_type=config["type"], name=config["name"]
            )
            adapter.connect.return_value = True
            adapter.disconnect.return_value = True
            adapter.submit_order.return_value = True
            adapters[config["name"]] = adapter

            await manager.add_adapter(config["name"], adapter, adapter.config)

        # Session startup
        startup_results = await manager.start_all_adapters()
        assert all(startup_results.values())

        # Set default adapter
        manager.registry.set_default_adapter("ib_primary")

        # Execute trading operations
        orders = []
        for i in range(5):
            order = NewOrderSingle(
                cl_ord_id=f"SESSION-ORDER-{i}",
                symbol="EURUSD",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
            )
            orders.append(order)
            result = await manager.submit_order(order)
            assert result is True

        # Verify order submissions
        assert adapters["ib_primary"].submit_order.call_count == 5

        # Health monitoring check
        health_report = await manager.check_health()
        assert len(health_report) == 3

        # Session shutdown
        shutdown_results = await manager.stop_all_adapters()
        assert all(shutdown_results.values())

        # Verify all adapters disconnected
        for adapter in adapters.values():
            adapter.disconnect.assert_called_once()
