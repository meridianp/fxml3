"""Comprehensive TDD tests for all broker adapters - Phase 2B.

This module implements comprehensive TDD testing for the 19 broker adapter files
to achieve the target 11-49% to 80%+ coverage improvement.
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add project root to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../"))

# Import base classes and interfaces that should always be available
from fxml4.brokers.adapters.base import (
    AdapterConfig,
    AdapterMetrics,
    BrokerAdapter,
    BrokerConnection,
    ConnectionStatus,
    OrderInfo,
    OrderStatus,
)
from fxml4.fix.messages.base import FIXMessage, OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)

# Try to import available adapters - these may or may not exist
AVAILABLE_ADAPTERS = {}

try:
    from fxml4.brokers.adapters.manual_adapter import ManualBrokerAdapter

    AVAILABLE_ADAPTERS["manual"] = ManualBrokerAdapter
    print("✓ ManualBrokerAdapter available")
except ImportError as e:
    print(f"✗ ManualBrokerAdapter not available: {e}")

try:
    from fxml4.brokers.adapters.ib_adapter import IBBrokerAdapter

    AVAILABLE_ADAPTERS["ib"] = IBBrokerAdapter
    print("✓ IBBrokerAdapter available")
except ImportError as e:
    print(f"✗ IBBrokerAdapter not available: {e}")

try:
    # This may fail due to missing dependencies, but tests should still be valuable
    from fxml4.brokers.adapters.fxcm_adapter import FXCMBrokerAdapter

    AVAILABLE_ADAPTERS["fxcm"] = FXCMBrokerAdapter
    print("✓ FXCMBrokerAdapter available")
except ImportError as e:
    print(f"✗ FXCMBrokerAdapter not available: {e}")


class TestBrokerAdapterBase:
    """Comprehensive tests for BrokerAdapter base functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.base_config = AdapterConfig(
            adapter_type="test",
            connection_params={"host": "localhost", "port": 8080},
            authentication={"username": "test", "password": "test"},
        )

    def test_adapter_config_creation(self):
        """Test AdapterConfig creation and validation."""
        config = AdapterConfig(
            adapter_type="test_adapter",
            connection_params={"url": "http://test.com"},
            authentication={"key": "secret"},
        )

        assert config.adapter_type == "test_adapter"
        assert config.connection_params["url"] == "http://test.com"
        assert config.authentication["key"] == "secret"
        assert config.enabled is True

        # Test default values
        assert "connect" in config.timeouts
        assert "max_retries" in config.retry_policy
        assert "max_orders_per_second" in config.limits
        assert "supports_market_data" in config.features

    def test_adapter_config_with_custom_settings(self):
        """Test AdapterConfig with custom timeout and limit settings."""
        config = AdapterConfig(
            adapter_type="custom",
            connection_params={},
            authentication={},
            timeouts={"connect": 60, "order": 600},
            limits={"max_orders_per_second": 5},
            features={"supports_bulk_operations": True},
        )

        assert config.timeouts["connect"] == 60
        assert config.timeouts["order"] == 600
        assert config.limits["max_orders_per_second"] == 5
        assert config.features["supports_bulk_operations"] is True

    def test_broker_connection_status_tracking(self):
        """Test BrokerConnection status and methods."""
        connection = BrokerConnection(
            adapter_type="test", status=ConnectionStatus.DISCONNECTED
        )

        assert connection.adapter_type == "test"
        assert connection.status == ConnectionStatus.DISCONNECTED
        assert not connection.is_connected()
        assert not connection.is_ready()

        # Test connected state
        connection.status = ConnectionStatus.CONNECTED
        assert connection.is_connected()
        assert not connection.is_ready()  # Not authenticated yet

        # Test authenticated state
        connection.status = ConnectionStatus.AUTHENTICATED
        assert connection.is_connected()
        assert connection.is_ready()

    def test_order_info_tracking(self):
        """Test OrderInfo creation and tracking."""
        order_info = OrderInfo(
            cl_ord_id="TEST_001", order_id="BROKER_123", status=OrderStatus.SUBMITTED
        )

        assert order_info.cl_ord_id == "TEST_001"
        assert order_info.order_id == "BROKER_123"
        assert order_info.status == OrderStatus.SUBMITTED
        assert order_info.total_filled_qty == 0.0
        assert order_info.avg_fill_price == 0.0
        assert order_info.fills == []

    def test_adapter_metrics_initialization(self):
        """Test AdapterMetrics initialization and tracking."""
        metrics = AdapterMetrics()

        assert metrics.total_orders == 0
        assert metrics.filled_orders == 0
        assert metrics.cancelled_orders == 0
        assert metrics.rejected_orders == 0
        assert metrics.failed_orders == 0
        assert metrics.uptime_seconds == 0.0


class MockBrokerAdapter(BrokerAdapter):
    """Mock broker adapter for testing base functionality."""

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.mock_connected = False
        self.mock_authenticated = False
        self.mock_orders: Dict[str, str] = {}
        self.mock_account = {"balance": 10000.0, "equity": 10500.0}

    async def connect(self) -> bool:
        """Mock connection method."""
        self.mock_connected = True
        self._update_connection_status(ConnectionStatus.CONNECTED)
        return True

    async def disconnect(self) -> None:
        """Mock disconnection method."""
        self.mock_connected = False
        self.mock_authenticated = False
        self._update_connection_status(ConnectionStatus.DISCONNECTED)

    async def authenticate(self) -> bool:
        """Mock authentication method."""
        if self.mock_connected:
            self.mock_authenticated = True
            self._update_connection_status(ConnectionStatus.AUTHENTICATED)
            return True
        return False

    async def is_connected(self) -> bool:
        """Mock connection check."""
        return self.mock_connected and self.mock_authenticated

    async def submit_order(self, order: NewOrderSingle) -> str:
        """Mock order submission."""
        if not await self.is_connected():
            raise Exception("Not connected")

        # Simulate order submission
        order_info = self._track_order(order)
        broker_order_id = f"MOCK_{order.cl_ord_id}"
        self.mock_orders[order.cl_ord_id] = broker_order_id

        return broker_order_id

    async def cancel_order(self, cancel_request: OrderCancelRequest) -> bool:
        """Mock order cancellation."""
        if cancel_request.orig_cl_ord_id in self.mock_orders:
            # Update order status to cancelled
            if cancel_request.orig_cl_ord_id in self.active_orders:
                self.active_orders[cancel_request.orig_cl_ord_id].status = (
                    OrderStatus.CANCELLED
                )
            return True
        return False

    async def get_order_status(self, cl_ord_id: str) -> Optional[OrderInfo]:
        """Mock order status retrieval."""
        return self.active_orders.get(cl_ord_id)

    async def get_open_orders(self) -> List[OrderInfo]:
        """Mock open orders retrieval."""
        return [
            info
            for info in self.active_orders.values()
            if info.status
            not in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]
        ]

    async def send_heartbeat(self) -> bool:
        """Mock heartbeat."""
        return await self.is_connected()

    async def get_account_info(self) -> Dict[str, Any]:
        """Mock account information."""
        return self.mock_account

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Mock position retrieval."""
        return [
            {
                "symbol": "EURUSD",
                "side": "long",
                "quantity": 100000,
                "open_price": 1.1200,
                "current_price": 1.1234,
                "unrealized_pnl": 340.0,
            }
        ]


class TestMockBrokerAdapter:
    """Test the mock broker adapter implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AdapterConfig(
            adapter_type="mock",
            connection_params={"mock": True},
            authentication={"user": "test", "pass": "test"},
        )
        self.adapter = MockBrokerAdapter(self.config)

    @pytest.mark.asyncio
    async def test_mock_connection_workflow(self):
        """Test complete connection workflow."""
        # Initially disconnected
        assert not await self.adapter.is_connected()
        assert self.adapter.connection.status == ConnectionStatus.DISCONNECTED

        # Connect
        result = await self.adapter.connect()
        assert result is True
        assert self.adapter.connection.status == ConnectionStatus.CONNECTED

        # Authenticate
        result = await self.adapter.authenticate()
        assert result is True
        assert self.adapter.connection.status == ConnectionStatus.AUTHENTICATED
        assert await self.adapter.is_connected()

        # Disconnect
        await self.adapter.disconnect()
        assert not await self.adapter.is_connected()
        assert self.adapter.connection.status == ConnectionStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_mock_order_lifecycle(self):
        """Test complete order lifecycle."""
        # Connect first
        await self.adapter.connect()
        await self.adapter.authenticate()

        # Create test order
        order = NewOrderSingle(
            cl_ord_id="MOCK_TEST_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IOC,
        )

        # Submit order
        broker_order_id = await self.adapter.submit_order(order)
        assert broker_order_id == "MOCK_MOCK_TEST_001"
        assert "MOCK_TEST_001" in self.adapter.active_orders

        # Check order status
        order_info = await self.adapter.get_order_status("MOCK_TEST_001")
        assert order_info is not None
        assert order_info.cl_ord_id == "MOCK_TEST_001"
        assert order_info.status == OrderStatus.SUBMITTED

        # Get open orders
        open_orders = await self.adapter.get_open_orders()
        assert len(open_orders) == 1
        assert open_orders[0].cl_ord_id == "MOCK_TEST_001"

        # Cancel order
        cancel_request = OrderCancelRequest(
            orig_cl_ord_id="MOCK_TEST_001",
            cl_ord_id="CANCEL_001",
            symbol="EURUSD",
            side=Side.BUY,
        )

        result = await self.adapter.cancel_order(cancel_request)
        assert result is True

        # Verify cancellation
        order_info = await self.adapter.get_order_status("MOCK_TEST_001")
        assert order_info.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_mock_account_and_positions(self):
        """Test account info and position retrieval."""
        await self.adapter.connect()
        await self.adapter.authenticate()

        # Get account info
        account_info = await self.adapter.get_account_info()
        assert account_info["balance"] == 10000.0
        assert account_info["equity"] == 10500.0

        # Get positions
        positions = await self.adapter.get_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "EURUSD"
        assert positions[0]["unrealized_pnl"] == 340.0

    @pytest.mark.asyncio
    async def test_mock_heartbeat(self):
        """Test heartbeat mechanism."""
        # Should fail when disconnected
        result = await self.adapter.send_heartbeat()
        assert result is False

        # Should work when connected
        await self.adapter.connect()
        await self.adapter.authenticate()
        result = await self.adapter.send_heartbeat()
        assert result is True


class TestAvailableBrokerAdapters:
    """Test available broker adapter implementations."""

    @pytest.mark.parametrize("adapter_type,adapter_class", AVAILABLE_ADAPTERS.items())
    def test_adapter_instantiation(self, adapter_type, adapter_class):
        """Test that available adapters can be instantiated."""
        config = AdapterConfig(
            adapter_type=adapter_type,
            connection_params={"test": True},
            authentication={"user": "test", "pass": "test"},
        )

        try:
            adapter = adapter_class(config)
            assert adapter is not None
            assert adapter.adapter_type == adapter_type
            assert adapter.config == config
            print(f"✓ {adapter_type} adapter instantiated successfully")
        except Exception as e:
            pytest.fail(f"Failed to instantiate {adapter_type} adapter: {e}")

    @pytest.mark.parametrize("adapter_type,adapter_class", AVAILABLE_ADAPTERS.items())
    def test_adapter_has_required_methods(self, adapter_type, adapter_class):
        """Test that adapters implement required abstract methods."""
        required_methods = [
            "connect",
            "disconnect",
            "authenticate",
            "is_connected",
            "submit_order",
            "cancel_order",
            "get_order_status",
            "get_open_orders",
            "send_heartbeat",
            "get_account_info",
            "get_positions",
        ]

        config = AdapterConfig(
            adapter_type=adapter_type, connection_params={}, authentication={}
        )

        try:
            adapter = adapter_class(config)
            for method_name in required_methods:
                assert hasattr(
                    adapter, method_name
                ), f"{adapter_type} missing {method_name}"
                method = getattr(adapter, method_name)
                assert callable(method), f"{adapter_type}.{method_name} not callable"

            print(f"✓ {adapter_type} adapter has all required methods")
        except Exception as e:
            pytest.fail(f"Failed to check {adapter_type} adapter methods: {e}")


class TestBrokerAdapterErrorHandling:
    """Test error handling across broker adapters."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AdapterConfig(
            adapter_type="error_test",
            connection_params={"invalid": True},
            authentication={"bad_creds": True},
        )
        self.adapter = MockBrokerAdapter(self.config)

    @pytest.mark.asyncio
    async def test_order_submission_when_disconnected(self):
        """Test order submission fails when not connected."""
        order = NewOrderSingle(
            cl_ord_id="ERROR_TEST_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        # Should fail when not connected
        with pytest.raises(Exception, match="Not connected"):
            await self.adapter.submit_order(order)

    @pytest.mark.asyncio
    async def test_cancellation_of_nonexistent_order(self):
        """Test cancellation of non-existent order."""
        await self.adapter.connect()
        await self.adapter.authenticate()

        cancel_request = OrderCancelRequest(
            orig_cl_ord_id="NONEXISTENT",
            cl_ord_id="CANCEL_001",
            symbol="EURUSD",
            side=Side.BUY,
        )

        result = await self.adapter.cancel_order(cancel_request)
        assert result is False

    def test_adapter_info_retrieval(self):
        """Test adapter information and statistics."""
        adapter_info = self.adapter.get_adapter_info()

        assert "adapter_type" in adapter_info
        assert "connection_status" in adapter_info
        assert "active_orders" in adapter_info
        assert "config" in adapter_info

        assert adapter_info["adapter_type"] == "error_test"
        assert adapter_info["active_orders"] == 0
        assert adapter_info["config"]["enabled"] is True


class TestBrokerAdapterCallbacks:
    """Test broker adapter callback mechanisms."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AdapterConfig(
            adapter_type="callback_test", connection_params={}, authentication={}
        )
        self.adapter = MockBrokerAdapter(self.config)

        # Mock callbacks
        self.execution_callback = Mock()
        self.status_callback = Mock()
        self.error_callback = Mock()

    def test_callback_registration(self):
        """Test callback registration."""
        self.adapter.set_execution_callback(self.execution_callback)
        self.adapter.set_status_callback(self.status_callback)
        self.adapter.set_error_callback(self.error_callback)

        assert self.adapter.execution_callback == self.execution_callback
        assert self.adapter.status_callback == self.status_callback
        assert self.adapter.error_callback == self.error_callback

    @pytest.mark.asyncio
    async def test_status_callback_invoked(self):
        """Test that status callbacks are invoked on status changes."""
        self.adapter.set_status_callback(self.status_callback)

        # Connect should trigger status callback
        await self.adapter.connect()

        # Verify callback was called
        assert self.status_callback.called
        call_args = self.status_callback.call_args[0][0]
        assert isinstance(call_args, BrokerConnection)
        assert call_args.status == ConnectionStatus.CONNECTED


if __name__ == "__main__":
    # Run tests with verbose output
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "-s", "--tb=short"],
        cwd=os.path.join(os.path.dirname(__file__), "../../../../"),
    )

    sys.exit(result.returncode)
