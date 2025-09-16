"""
TDD Tests for Base Broker Adapter Interface.

Following TDD methodology: Write failing tests first (RED phase)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fxml4.brokers.adapters.base import (
    AdapterConfig,
    BrokerAdapter,
    BrokerConnection,
    ConnectionStatus,
    OrderInfo,
    OrderStatus,
)
from fxml4.fix.messages.admin import Heartbeat, Logon, Logout
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)


class MockBrokerAdapter(BrokerAdapter):
    """Mock implementation for testing base functionality."""

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.mock_connection_status = ConnectionStatus.DISCONNECTED
        self.mock_orders: Dict[str, OrderInfo] = {}
        self.mock_connection_failure = False
        self.mock_auth_failure = False
        self.heartbeat_count = 0
        self.connection_attempts = 0

    async def connect(self) -> bool:
        """Mock connection implementation."""
        self.connection_attempts += 1
        if self.mock_connection_failure:
            self.mock_connection_status = ConnectionStatus.ERROR
            return False
        self.mock_connection_status = ConnectionStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        """Mock disconnect implementation."""
        self.mock_connection_status = ConnectionStatus.DISCONNECTED

    async def authenticate(self) -> bool:
        """Mock authentication implementation."""
        if self.mock_auth_failure:
            self.mock_connection_status = ConnectionStatus.ERROR
            return False
        if self.mock_connection_status == ConnectionStatus.CONNECTED:
            self.mock_connection_status = ConnectionStatus.AUTHENTICATED
            return True
        return False

    async def is_connected(self) -> bool:
        """Mock connection check."""
        return self.mock_connection_status in [
            ConnectionStatus.CONNECTED,
            ConnectionStatus.AUTHENTICATED,
        ]

    async def submit_order(self, order: NewOrderSingle) -> str:
        """Mock order submission."""
        cl_ord_id = order.fields.get("11", f"test_order_{len(self.mock_orders)}")
        order_info = OrderInfo(
            cl_ord_id=cl_ord_id, status=OrderStatus.SUBMITTED, original_order=order
        )
        self.mock_orders[cl_ord_id] = order_info
        return cl_ord_id

    async def cancel_order(self, cancel_request: OrderCancelRequest) -> bool:
        """Mock order cancellation."""
        cl_ord_id = cancel_request.fields.get("11", "")
        if cl_ord_id in self.mock_orders:
            self.mock_orders[cl_ord_id].status = OrderStatus.CANCELLED
            return True
        return False

    async def get_order_status(self, cl_ord_id: str) -> Optional[OrderInfo]:
        """Mock order status retrieval."""
        return self.mock_orders.get(cl_ord_id)

    async def get_open_orders(self) -> List[OrderInfo]:
        """Mock open orders retrieval."""
        return [
            order
            for order in self.mock_orders.values()
            if order.status
            not in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]
        ]

    async def send_heartbeat(self) -> bool:
        """Mock heartbeat."""
        self.heartbeat_count += 1
        return True

    async def get_account_info(self) -> Dict[str, Any]:
        """Mock account info."""
        return {
            "account_id": "TEST_ACCOUNT",
            "balance": 10000.0,
            "equity": 10000.0,
            "margin": 1000.0,
            "currency": "USD",
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Mock positions."""
        return [
            {
                "symbol": "EURUSD",
                "quantity": 10000,
                "side": "long",
                "avg_price": 1.1000,
                "unrealized_pnl": 50.0,
            }
        ]


class TestConnectionStatus:
    """Test connection status enumeration."""

    def test_connection_status_values(self):
        """Test that all expected connection statuses exist."""
        expected_statuses = {
            "disconnected",
            "connecting",
            "connected",
            "authenticating",
            "authenticated",
            "error",
            "maintenance",
        }

        actual_statuses = {status.value for status in ConnectionStatus}
        assert expected_statuses == actual_statuses

    def test_connection_status_enum_consistency(self):
        """Test connection status enum is well-defined."""
        # Test that each status is a unique value
        statuses = list(ConnectionStatus)
        status_values = [status.value for status in statuses]

        assert len(statuses) == len(set(status_values))
        assert all(isinstance(status.value, str) for status in statuses)


class TestOrderStatus:
    """Test order status enumeration."""

    def test_order_status_values(self):
        """Test that all expected order statuses exist."""
        expected_statuses = {
            "pending",
            "submitted",
            "acknowledged",
            "working",
            "partially_filled",
            "filled",
            "cancelled",
            "rejected",
            "expired",
        }

        actual_statuses = {status.value for status in OrderStatus}
        assert expected_statuses == actual_statuses

    def test_order_lifecycle_states(self):
        """Test order status represents complete lifecycle."""
        # Terminal states (order lifecycle ends here)
        terminal_states = {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }

        # Active states (order is still being processed)
        active_states = {
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.WORKING,
            OrderStatus.PARTIALLY_FILLED,
        }

        all_states = set(OrderStatus)
        assert terminal_states.union(active_states) == all_states
        assert terminal_states.intersection(active_states) == set()


class TestAdapterConfig:
    """Test adapter configuration dataclass."""

    def test_adapter_config_creation(self):
        """Test adapter config can be created."""
        config = AdapterConfig(
            adapter_type="test_broker",
            connection_params={
                "host": "localhost",
                "port": 1234,
                "connection_string": "test://localhost:1234",
            },
            authentication={
                "username": "test_user",
                "password": "test_password",
                "account_id": "TEST_ACCOUNT",
            },
        )

        assert config.adapter_type == "test_broker"
        assert config.connection_params["host"] == "localhost"
        assert config.connection_params["port"] == 1234
        assert config.authentication["username"] == "test_user"
        assert config.authentication["password"] == "test_password"
        assert config.authentication["account_id"] == "TEST_ACCOUNT"

    def test_adapter_config_defaults(self):
        """Test adapter config default values."""
        config = AdapterConfig(
            adapter_type="minimal", connection_params={}, authentication={}
        )

        # Should have reasonable defaults
        assert config.adapter_type == "minimal"
        assert hasattr(config, "timeouts")
        assert hasattr(config, "retry_policy")
        assert hasattr(config, "limits")
        assert hasattr(config, "features")
        assert config.enabled is True

        # Check default timeout values
        assert config.timeouts["connect"] == 30
        assert config.timeouts["authenticate"] == 60
        assert config.timeouts["heartbeat"] == 30

        # Check default retry policy
        assert config.retry_policy["max_retries"] == 3
        assert config.retry_policy["base_delay"] == 1.0


class TestBrokerConnection:
    """Test broker connection dataclass."""

    def test_broker_connection_creation(self):
        """Test broker connection can be created."""
        now = datetime.utcnow()
        conn_info = BrokerConnection(
            adapter_type="test_broker",
            status=ConnectionStatus.CONNECTED,
            connected_at=now,
            session_id="TEST_SESSION_123",
        )

        assert conn_info.adapter_type == "test_broker"
        assert conn_info.status == ConnectionStatus.CONNECTED
        assert conn_info.connected_at == now
        assert conn_info.session_id == "TEST_SESSION_123"

    def test_is_connected_method(self):
        """Test is_connected method logic."""
        # Connected status
        conn_info = BrokerConnection(
            adapter_type="test", status=ConnectionStatus.CONNECTED
        )
        assert conn_info.is_connected() is True

        # Authenticated status
        conn_info.status = ConnectionStatus.AUTHENTICATED
        assert conn_info.is_connected() is True

        # Disconnected status
        conn_info.status = ConnectionStatus.DISCONNECTED
        assert conn_info.is_connected() is False

        # Error status
        conn_info.status = ConnectionStatus.ERROR
        assert conn_info.is_connected() is False

    def test_is_ready_method(self):
        """Test is_ready method logic."""
        conn_info = BrokerConnection(
            adapter_type="test", status=ConnectionStatus.CONNECTED
        )

        # Only authenticated should be ready
        conn_info.status = ConnectionStatus.AUTHENTICATED
        assert conn_info.is_ready() is True

        conn_info.status = ConnectionStatus.CONNECTED
        assert conn_info.is_ready() is False

        conn_info.status = ConnectionStatus.DISCONNECTED
        assert conn_info.is_ready() is False


class TestOrderInfo:
    """Test order information dataclass."""

    def test_order_info_creation(self):
        """Test order info can be created."""
        order_info = OrderInfo(
            cl_ord_id="TEST_ORDER_001",
            order_id="BROKER_ORDER_123",
            status=OrderStatus.WORKING,
        )

        assert order_info.cl_ord_id == "TEST_ORDER_001"
        assert order_info.order_id == "BROKER_ORDER_123"
        assert order_info.status == OrderStatus.WORKING
        assert isinstance(order_info.created_at, datetime)
        assert isinstance(order_info.updated_at, datetime)
        assert order_info.fills == []
        assert order_info.total_filled_qty == 0.0
        assert order_info.avg_fill_price == 0.0

    def test_order_info_fill_tracking(self):
        """Test order fill tracking capabilities."""
        order_info = OrderInfo(cl_ord_id="TEST_FILL", status=OrderStatus.WORKING)

        # Should be able to track multiple fills
        assert len(order_info.fills) == 0
        assert order_info.total_filled_qty == 0.0
        assert order_info.remaining_qty == 0.0

        # Fields should be mutable for tracking updates
        order_info.total_filled_qty = 1000.0
        order_info.avg_fill_price = 1.1234
        order_info.remaining_qty = 2000.0

        assert order_info.total_filled_qty == 1000.0
        assert order_info.avg_fill_price == 1.1234
        assert order_info.remaining_qty == 2000.0


class TestBrokerAdapterBase:
    """Test base broker adapter functionality."""

    @pytest.fixture
    def adapter_config(self):
        """Create test adapter configuration."""
        return AdapterConfig(
            adapter_type="mock_broker",
            connection_params={
                "broker_name": "Mock Broker",
                "connection_string": "mock://test",
            },
            authentication={
                "username": "test_user",
                "password": "test_pass",
                "account_id": "TEST_ACCOUNT",
            },
        )

    @pytest.fixture
    def mock_adapter(self, adapter_config):
        """Create mock adapter instance."""
        return MockBrokerAdapter(adapter_config)

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, mock_adapter):
        """Test complete connection lifecycle."""
        # Initial state
        assert not await mock_adapter.is_connected()

        # Connect
        result = await mock_adapter.connect()
        assert result is True
        assert await mock_adapter.is_connected()

        # Authenticate
        auth_result = await mock_adapter.authenticate()
        assert auth_result is True

        # Disconnect
        await mock_adapter.disconnect()
        assert not await mock_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self, mock_adapter):
        """Test connection failure scenarios."""
        # Simulate connection failure
        mock_adapter.mock_connection_failure = True

        result = await mock_adapter.connect()
        assert result is False
        assert not await mock_adapter.is_connected()

        # Should track connection attempts
        assert mock_adapter.connection_attempts == 1

    @pytest.mark.asyncio
    async def test_authentication_failure_handling(self, mock_adapter):
        """Test authentication failure scenarios."""
        # Connect successfully first
        await mock_adapter.connect()
        assert await mock_adapter.is_connected()

        # Simulate auth failure
        mock_adapter.mock_auth_failure = True

        auth_result = await mock_adapter.authenticate()
        assert auth_result is False

    @pytest.mark.asyncio
    async def test_order_lifecycle(self, mock_adapter):
        """Test complete order lifecycle."""
        # Setup connection
        await mock_adapter.connect()
        await mock_adapter.authenticate()

        # Create test order
        test_order = MagicMock(spec=NewOrderSingle)
        test_order.fields = {"11": "TEST_ORDER_001", "55": "EURUSD", "54": "1"}

        # Submit order
        cl_ord_id = await mock_adapter.submit_order(test_order)
        assert cl_ord_id == "TEST_ORDER_001"

        # Check order status
        order_info = await mock_adapter.get_order_status(cl_ord_id)
        assert order_info is not None
        assert order_info.cl_ord_id == cl_ord_id
        assert order_info.status == OrderStatus.SUBMITTED

        # Get open orders
        open_orders = await mock_adapter.get_open_orders()
        assert len(open_orders) == 1
        assert open_orders[0].cl_ord_id == cl_ord_id

        # Cancel order
        cancel_request = MagicMock(spec=OrderCancelRequest)
        cancel_request.fields = {"11": cl_ord_id}

        cancel_result = await mock_adapter.cancel_order(cancel_request)
        assert cancel_result is True

        # Verify cancellation
        order_info = await mock_adapter.get_order_status(cl_ord_id)
        assert order_info.status == OrderStatus.CANCELLED

        # Should not appear in open orders
        open_orders = await mock_adapter.get_open_orders()
        assert len(open_orders) == 0

    @pytest.mark.asyncio
    async def test_heartbeat_mechanism(self, mock_adapter):
        """Test heartbeat functionality."""
        initial_count = mock_adapter.heartbeat_count

        result = await mock_adapter.send_heartbeat()
        assert result is True
        assert mock_adapter.heartbeat_count == initial_count + 1

        # Multiple heartbeats
        for _ in range(5):
            await mock_adapter.send_heartbeat()

        assert mock_adapter.heartbeat_count == initial_count + 6

    @pytest.mark.asyncio
    async def test_account_information(self, mock_adapter):
        """Test account information retrieval."""
        await mock_adapter.connect()
        await mock_adapter.authenticate()

        account_info = await mock_adapter.get_account_info()

        assert isinstance(account_info, dict)
        assert "account_id" in account_info
        assert "balance" in account_info
        assert "equity" in account_info
        assert account_info["account_id"] == "TEST_ACCOUNT"
        assert isinstance(account_info["balance"], (int, float))
        assert isinstance(account_info["equity"], (int, float))

    @pytest.mark.asyncio
    async def test_position_information(self, mock_adapter):
        """Test position information retrieval."""
        await mock_adapter.connect()
        await mock_adapter.authenticate()

        positions = await mock_adapter.get_positions()

        assert isinstance(positions, list)
        assert len(positions) > 0

        position = positions[0]
        assert "symbol" in position
        assert "quantity" in position
        assert "side" in position
        assert "avg_price" in position
        assert position["symbol"] == "EURUSD"
        assert isinstance(position["quantity"], (int, float))


@pytest.mark.unit
class TestBrokerAdapterIntegration:
    """Integration tests for broker adapter patterns."""

    @pytest.fixture
    def adapter_config(self):
        return AdapterConfig(
            adapter_type="integration_test", connection_params={}, authentication={}
        )

    @pytest.fixture
    def mock_adapter(self, adapter_config):
        return MockBrokerAdapter(adapter_config)

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, mock_adapter):
        """Test adapter handles concurrent operations."""
        await mock_adapter.connect()
        await mock_adapter.authenticate()

        # Create multiple orders concurrently
        orders = []
        for i in range(10):
            order = MagicMock(spec=NewOrderSingle)
            order.fields = {"11": f"CONCURRENT_ORDER_{i}", "55": "EURUSD"}
            orders.append(order)

        # Submit all orders concurrently
        tasks = [mock_adapter.submit_order(order) for order in orders]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert len(set(results)) == 10  # All unique order IDs

        # Verify all orders are tracked
        open_orders = await mock_adapter.get_open_orders()
        assert len(open_orders) == 10

    @pytest.mark.asyncio
    async def test_error_recovery_patterns(self, mock_adapter):
        """Test error recovery patterns."""
        # Test recovery from connection failure
        mock_adapter.mock_connection_failure = True

        # First attempt should fail
        result = await mock_adapter.connect()
        assert result is False

        # Recovery should work
        mock_adapter.mock_connection_failure = False
        result = await mock_adapter.connect()
        assert result is True

        # Test recovery from auth failure
        mock_adapter.mock_auth_failure = True
        auth_result = await mock_adapter.authenticate()
        assert auth_result is False

        # Recovery should work
        mock_adapter.mock_auth_failure = False
        auth_result = await mock_adapter.authenticate()
        assert auth_result is True


@pytest.mark.performance
def test_broker_adapter_performance():
    """Test broker adapter performance characteristics."""
    import time

    config = AdapterConfig(
        adapter_type="performance_test", connection_params={}, authentication={}
    )
    adapter = MockBrokerAdapter(config)

    # Test order creation performance
    start_time = time.time()

    orders = []
    for i in range(1000):
        order = MagicMock(spec=NewOrderSingle)
        order.fields = {"11": f"PERF_ORDER_{i}"}
        orders.append(order)

    end_time = time.time()

    # Should create orders quickly
    creation_time = end_time - start_time
    assert creation_time < 1.0  # Less than 1 second for 1000 orders

    # Test order tracking performance
    start_time = time.time()

    for order in orders[:100]:  # Test first 100
        order_info = OrderInfo(
            cl_ord_id=order.fields["11"],
            status=OrderStatus.SUBMITTED,
            original_order=order,
        )
        adapter.mock_orders[order.fields["11"]] = order_info

    end_time = time.time()
    tracking_time = end_time - start_time

    # Should track orders efficiently
    assert tracking_time < 0.1  # Less than 100ms for 100 orders
    assert len(adapter.mock_orders) == 100
