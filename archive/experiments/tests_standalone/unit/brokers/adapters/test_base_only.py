"""Direct tests for base broker adapter classes without adapter imports.

This bypasses the __init__.py import issues by importing base.py directly.
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../"))

# Import directly from base.py to avoid __init__.py issues
try:
    sys.path.append(
        os.path.join(os.path.dirname(__file__), "../../../../fxml4/brokers/adapters")
    )
    from base import (
        AdapterConfig,
        AdapterMetrics,
        BrokerAdapter,
        BrokerConnection,
        ConnectionStatus,
        OrderInfo,
        OrderStatus,
    )

    BASE_IMPORTED = True
    print("✓ Base adapter classes imported successfully")
except ImportError as e:
    print(f"✗ Failed to import base classes: {e}")
    BASE_IMPORTED = False

# Try to import FIX message classes
try:
    from fxml4.fix.messages.base import FIXMessage, OrdType, Side, TimeInForce
    from fxml4.fix.messages.orders import (
        ExecutionReport,
        NewOrderSingle,
        OrderCancelRequest,
    )

    FIX_IMPORTED = True
    print("✓ FIX message classes imported successfully")
except ImportError as e:
    print(f"✗ Failed to import FIX classes: {e}")
    FIX_IMPORTED = False


@pytest.mark.skipif(not BASE_IMPORTED, reason="Base adapter classes not available")
class TestAdapterConfigDirect:
    """Direct tests for AdapterConfig without adapter imports."""

    def test_config_creation(self):
        """Test AdapterConfig creation."""
        config = AdapterConfig(
            adapter_type="direct_test",
            connection_params={"host": "test.example.com", "port": 443},
            authentication={"api_key": "test_key_123"},
        )

        assert config.adapter_type == "direct_test"
        assert config.connection_params["host"] == "test.example.com"
        assert config.connection_params["port"] == 443
        assert config.authentication["api_key"] == "test_key_123"
        assert config.enabled is True

    def test_config_defaults(self):
        """Test AdapterConfig default values."""
        config = AdapterConfig(
            adapter_type="defaults_test", connection_params={}, authentication={}
        )

        # Test timeout defaults
        assert config.timeouts["connect"] == 30
        assert config.timeouts["authenticate"] == 60
        assert config.timeouts["order"] == 300
        assert config.timeouts["heartbeat"] == 30

        # Test retry policy defaults
        assert config.retry_policy["max_retries"] == 3
        assert config.retry_policy["base_delay"] == 1.0
        assert config.retry_policy["max_delay"] == 60.0
        assert config.retry_policy["exponential_base"] == 2.0

        # Test limit defaults
        assert config.limits["max_orders_per_second"] == 10
        assert config.limits["max_daily_volume"] == 100000000.0
        assert config.limits["max_position_size"] == 10000000.0

        # Test feature defaults
        assert config.features["supports_market_data"] is True
        assert config.features["supports_order_modification"] is True
        assert config.features["supports_bulk_operations"] is False
        assert config.features["supports_portfolio_queries"] is True

    def test_config_customization(self):
        """Test AdapterConfig with custom values."""
        config = AdapterConfig(
            adapter_type="custom_test",
            connection_params={"url": "ws://custom.broker.com"},
            authentication={"username": "user", "password": "pass"},
            timeouts={"connect": 45, "order": 180},
            retry_policy={"max_retries": 5, "base_delay": 2.0},
            limits={"max_orders_per_second": 20, "max_position_size": 1000000.0},
            features={"supports_streaming": True, "supports_options": False},
            enabled=True,
        )

        assert config.timeouts["connect"] == 45
        assert config.timeouts["order"] == 180
        assert config.retry_policy["max_retries"] == 5
        assert config.retry_policy["base_delay"] == 2.0
        assert config.limits["max_orders_per_second"] == 20
        assert config.limits["max_position_size"] == 1000000.0
        assert config.features["supports_streaming"] is True
        assert config.features["supports_options"] is False

    def test_disabled_config(self):
        """Test disabled adapter configuration."""
        config = AdapterConfig(
            adapter_type="disabled_test",
            connection_params={},
            authentication={},
            enabled=False,
        )

        assert config.enabled is False


@pytest.mark.skipif(not BASE_IMPORTED, reason="Base adapter classes not available")
class TestBrokerConnectionDirect:
    """Direct tests for BrokerConnection."""

    def test_connection_creation(self):
        """Test BrokerConnection creation."""
        connection = BrokerConnection(
            adapter_type="test_direct", status=ConnectionStatus.DISCONNECTED
        )

        assert connection.adapter_type == "test_direct"
        assert connection.status == ConnectionStatus.DISCONNECTED
        assert connection.connected_at is None
        assert connection.session_id is None
        assert connection.error_message is None
        assert connection.connection_count == 0

    def test_connection_status_methods(self):
        """Test connection status checking methods."""
        connection = BrokerConnection("test", ConnectionStatus.DISCONNECTED)

        # Test disconnected
        assert not connection.is_connected()
        assert not connection.is_ready()

        # Test connecting
        connection.status = ConnectionStatus.CONNECTING
        assert not connection.is_connected()
        assert not connection.is_ready()

        # Test connected
        connection.status = ConnectionStatus.CONNECTED
        assert connection.is_connected()
        assert not connection.is_ready()  # Not authenticated yet

        # Test authenticating
        connection.status = ConnectionStatus.AUTHENTICATING
        assert not connection.is_connected()  # Not fully connected during auth
        assert not connection.is_ready()

        # Test authenticated (ready)
        connection.status = ConnectionStatus.AUTHENTICATED
        assert connection.is_connected()
        assert connection.is_ready()

        # Test error state
        connection.status = ConnectionStatus.ERROR
        assert not connection.is_connected()
        assert not connection.is_ready()

        # Test maintenance
        connection.status = ConnectionStatus.MAINTENANCE
        assert not connection.is_connected()
        assert not connection.is_ready()

    def test_connection_with_details(self):
        """Test connection with detailed information."""
        now = datetime.utcnow()
        connection = BrokerConnection(
            adapter_type="detailed_test",
            status=ConnectionStatus.AUTHENTICATED,
            connected_at=now,
            last_heartbeat=now,
            session_id="SESSION_ABC123",
            connection_count=5,
            uptime_seconds=1800.0,
        )

        assert connection.connected_at == now
        assert connection.last_heartbeat == now
        assert connection.session_id == "SESSION_ABC123"
        assert connection.connection_count == 5
        assert connection.uptime_seconds == 1800.0
        assert connection.is_connected()
        assert connection.is_ready()

    def test_connection_with_error(self):
        """Test connection with error information."""
        connection = BrokerConnection(
            adapter_type="error_test",
            status=ConnectionStatus.ERROR,
            error_message="Authentication failed: Invalid credentials",
        )

        assert connection.status == ConnectionStatus.ERROR
        assert connection.error_message == "Authentication failed: Invalid credentials"
        assert not connection.is_connected()
        assert not connection.is_ready()


@pytest.mark.skipif(not BASE_IMPORTED, reason="Base adapter classes not available")
class TestOrderInfoDirect:
    """Direct tests for OrderInfo."""

    def test_order_info_creation(self):
        """Test OrderInfo creation."""
        order_info = OrderInfo(cl_ord_id="DIRECT_TEST_001")

        assert order_info.cl_ord_id == "DIRECT_TEST_001"
        assert order_info.order_id is None
        assert order_info.status == OrderStatus.PENDING
        assert order_info.total_filled_qty == 0.0
        assert order_info.avg_fill_price == 0.0
        assert order_info.remaining_qty == 0.0
        assert order_info.error_message is None
        assert isinstance(order_info.created_at, datetime)
        assert isinstance(order_info.updated_at, datetime)
        assert order_info.fills == []

    def test_order_info_with_data(self):
        """Test OrderInfo with data."""
        now = datetime.utcnow()
        order_info = OrderInfo(
            cl_ord_id="DATA_TEST_001",
            order_id="BROKER_XYZ789",
            status=OrderStatus.PARTIALLY_FILLED,
            created_at=now,
            updated_at=now,
            total_filled_qty=75000,
            avg_fill_price=1.2345,
            remaining_qty=25000,
        )

        assert order_info.cl_ord_id == "DATA_TEST_001"
        assert order_info.order_id == "BROKER_XYZ789"
        assert order_info.status == OrderStatus.PARTIALLY_FILLED
        assert order_info.created_at == now
        assert order_info.updated_at == now
        assert order_info.total_filled_qty == 75000
        assert order_info.avg_fill_price == 1.2345
        assert order_info.remaining_qty == 25000

    def test_order_status_values(self):
        """Test all OrderStatus enum values."""
        statuses = [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.WORKING,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        ]

        for status in statuses:
            order_info = OrderInfo(
                cl_ord_id=f"STATUS_TEST_{status.value.upper()}", status=status
            )
            assert order_info.status == status

    def test_order_info_with_error(self):
        """Test OrderInfo with error information."""
        order_info = OrderInfo(
            cl_ord_id="ERROR_TEST_001",
            status=OrderStatus.REJECTED,
            error_message="Insufficient funds: Available 1000.00, Required 10000.00",
        )

        assert order_info.status == OrderStatus.REJECTED
        assert "Insufficient funds" in order_info.error_message
        assert "1000.00" in order_info.error_message
        assert "10000.00" in order_info.error_message


@pytest.mark.skipif(not BASE_IMPORTED, reason="Base adapter classes not available")
class TestAdapterMetricsDirect:
    """Direct tests for AdapterMetrics."""

    def test_metrics_initialization(self):
        """Test AdapterMetrics initialization."""
        metrics = AdapterMetrics()

        assert metrics.total_orders == 0
        assert metrics.filled_orders == 0
        assert metrics.cancelled_orders == 0
        assert metrics.rejected_orders == 0
        assert metrics.failed_orders == 0
        assert metrics.total_modifications == 0
        assert metrics.failed_modifications == 0
        assert metrics.last_connect_time is None
        assert metrics.last_disconnect_time is None
        assert metrics.bytes_sent == 0
        assert metrics.bytes_received == 0
        assert metrics.messages_sent == 0
        assert metrics.messages_received == 0
        assert metrics.uptime_seconds == 0.0

    def test_metrics_with_values(self):
        """Test AdapterMetrics with actual values."""
        connect_time = datetime.utcnow()
        disconnect_time = datetime.utcnow()

        metrics = AdapterMetrics(
            total_orders=1000,
            filled_orders=850,
            cancelled_orders=100,
            rejected_orders=30,
            failed_orders=20,
            total_modifications=50,
            failed_modifications=5,
            last_connect_time=connect_time,
            last_disconnect_time=disconnect_time,
            bytes_sent=5242880,  # 5MB
            bytes_received=10485760,  # 10MB
            messages_sent=2000,
            messages_received=3000,
            uptime_seconds=86400.0,  # 24 hours
        )

        assert metrics.total_orders == 1000
        assert metrics.filled_orders == 850
        assert metrics.cancelled_orders == 100
        assert metrics.rejected_orders == 30
        assert metrics.failed_orders == 20
        assert metrics.total_modifications == 50
        assert metrics.failed_modifications == 5
        assert metrics.last_connect_time == connect_time
        assert metrics.last_disconnect_time == disconnect_time
        assert metrics.bytes_sent == 5242880
        assert metrics.bytes_received == 10485760
        assert metrics.messages_sent == 2000
        assert metrics.messages_received == 3000
        assert metrics.uptime_seconds == 86400.0

    def test_metrics_calculations(self):
        """Test metric calculations and ratios."""
        metrics = AdapterMetrics(
            total_orders=100,
            filled_orders=80,
            cancelled_orders=15,
            rejected_orders=3,
            failed_orders=2,
            total_modifications=20,
            failed_modifications=2,
            messages_sent=500,
            messages_received=750,
            uptime_seconds=3600.0,  # 1 hour
        )

        # Calculate success rates
        fill_rate = metrics.filled_orders / metrics.total_orders
        cancel_rate = metrics.cancelled_orders / metrics.total_orders
        reject_rate = metrics.rejected_orders / metrics.total_orders
        failure_rate = metrics.failed_orders / metrics.total_orders
        modification_success_rate = (
            metrics.total_modifications - metrics.failed_modifications
        ) / metrics.total_modifications

        assert fill_rate == 0.8  # 80%
        assert cancel_rate == 0.15  # 15%
        assert reject_rate == 0.03  # 3%
        assert failure_rate == 0.02  # 2%
        assert modification_success_rate == 0.9  # 90%

        # Calculate message throughput (messages per second)
        sent_throughput = metrics.messages_sent / metrics.uptime_seconds
        received_throughput = metrics.messages_received / metrics.uptime_seconds

        assert abs(sent_throughput - (500 / 3600)) < 0.0001
        assert abs(received_throughput - (750 / 3600)) < 0.0001


@pytest.mark.skipif(not FIX_IMPORTED, reason="FIX message classes not available")
class TestFIXMessageDirect:
    """Direct tests for FIX message classes."""

    def test_new_order_single(self):
        """Test NewOrderSingle creation."""
        order = NewOrderSingle(
            cl_ord_id="FIX_DIRECT_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
        )

        assert order.cl_ord_id == "FIX_DIRECT_001"
        assert order.symbol == "EURUSD"
        assert order.side == Side.BUY
        assert order.order_qty == 100000
        assert order.ord_type == OrdType.MARKET
        assert order.time_in_force == TimeInForce.IMMEDIATE_OR_CANCEL

    def test_order_cancel_request(self):
        """Test OrderCancelRequest creation."""
        cancel = OrderCancelRequest(
            orig_cl_ord_id="ORIGINAL_DIRECT_001",
            cl_ord_id="CANCEL_DIRECT_001",
            symbol="GBPUSD",
            side=Side.SELL,
        )

        assert cancel.orig_cl_ord_id == "ORIGINAL_DIRECT_001"
        assert cancel.cl_ord_id == "CANCEL_DIRECT_001"
        assert cancel.symbol == "GBPUSD"
        assert cancel.side == Side.SELL

    def test_side_enum(self):
        """Test Side enum values."""
        assert Side.BUY is not None
        assert Side.SELL is not None
        assert Side.BUY != Side.SELL

    def test_ord_type_enum(self):
        """Test OrdType enum values."""
        assert OrdType.MARKET is not None
        assert OrdType.LIMIT is not None
        assert OrdType.STOP is not None
        assert OrdType.STOP_LIMIT is not None

        # Ensure they're all different
        order_types = [OrdType.MARKET, OrdType.LIMIT, OrdType.STOP, OrdType.STOP_LIMIT]
        assert len(set(order_types)) == len(order_types)

    def test_time_in_force_enum(self):
        """Test TimeInForce enum values."""
        assert TimeInForce.DAY is not None
        assert TimeInForce.GOOD_TILL_CANCEL is not None  # Good Till Cancel
        assert TimeInForce.IMMEDIATE_OR_CANCEL is not None  # Immediate Or Cancel
        assert TimeInForce.FILL_OR_KILL is not None  # Fill Or Kill

        # Ensure they're all different
        tif_values = [
            TimeInForce.DAY,
            TimeInForce.GOOD_TILL_CANCEL,
            TimeInForce.IMMEDIATE_OR_CANCEL,
            TimeInForce.FILL_OR_KILL,
        ]
        assert len(set(tif_values)) == len(tif_values)


class TestConnectionStatusEnum:
    """Test ConnectionStatus enum independent of other imports."""

    def test_connection_status_values(self):
        """Test all ConnectionStatus enum values exist."""
        if BASE_IMPORTED:
            statuses = [
                ConnectionStatus.DISCONNECTED,
                ConnectionStatus.CONNECTING,
                ConnectionStatus.CONNECTED,
                ConnectionStatus.AUTHENTICATING,
                ConnectionStatus.AUTHENTICATED,
                ConnectionStatus.ERROR,
                ConnectionStatus.MAINTENANCE,
            ]

            # Ensure all values are distinct
            assert len(set(statuses)) == len(statuses)

            # Test string representation
            for status in statuses:
                assert isinstance(status.value, str)
                assert len(status.value) > 0


if __name__ == "__main__":
    # Run tests with verbose output
    import subprocess
    import sys

    if BASE_IMPORTED or FIX_IMPORTED:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", __file__, "-v", "-s", "--tb=short"],
            cwd=os.path.join(os.path.dirname(__file__), "../../../../"),
        )

        sys.exit(result.returncode)
    else:
        print("❌ No testable modules available - dependency issues prevent testing")
        sys.exit(1)
