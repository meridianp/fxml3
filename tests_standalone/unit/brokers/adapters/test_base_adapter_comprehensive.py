"""Comprehensive TDD tests for base broker adapter functionality.

This module focuses on testing the base adapter interface and core functionality
without dependencies on specific adapter implementations that might have missing imports.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../"))

# Import only the base classes to avoid dependency issues
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


class TestAdapterConfigValidation:
    """Comprehensive tests for AdapterConfig validation and defaults."""

    def test_minimal_config_creation(self):
        """Test creating config with minimal parameters."""
        config = AdapterConfig(
            adapter_type="minimal_test",
            connection_params={"host": "localhost"},
            authentication={"token": "test_token"},
        )

        assert config.adapter_type == "minimal_test"
        assert config.connection_params["host"] == "localhost"
        assert config.authentication["token"] == "test_token"
        assert config.enabled is True

    def test_default_timeout_values(self):
        """Test that default timeout values are reasonable."""
        config = AdapterConfig(
            adapter_type="timeout_test", connection_params={}, authentication={}
        )

        # Check default timeouts
        assert config.timeouts["connect"] == 30
        assert config.timeouts["authenticate"] == 60
        assert config.timeouts["order"] == 300
        assert config.timeouts["heartbeat"] == 30

    def test_custom_timeout_override(self):
        """Test overriding default timeout values."""
        custom_timeouts = {
            "connect": 45,
            "authenticate": 90,
            "order": 600,
            "heartbeat": 15,
        }

        config = AdapterConfig(
            adapter_type="custom_timeout",
            connection_params={},
            authentication={},
            timeouts=custom_timeouts,
        )

        assert config.timeouts["connect"] == 45
        assert config.timeouts["authenticate"] == 90
        assert config.timeouts["order"] == 600
        assert config.timeouts["heartbeat"] == 15

    def test_default_retry_policy(self):
        """Test default retry policy values."""
        config = AdapterConfig(
            adapter_type="retry_test", connection_params={}, authentication={}
        )

        assert config.retry_policy["max_retries"] == 3
        assert config.retry_policy["base_delay"] == 1.0
        assert config.retry_policy["max_delay"] == 60.0
        assert config.retry_policy["exponential_base"] == 2.0

    def test_custom_retry_policy(self):
        """Test custom retry policy configuration."""
        custom_retry = {
            "max_retries": 5,
            "base_delay": 2.0,
            "max_delay": 120.0,
            "exponential_base": 1.5,
        }

        config = AdapterConfig(
            adapter_type="custom_retry",
            connection_params={},
            authentication={},
            retry_policy=custom_retry,
        )

        assert config.retry_policy["max_retries"] == 5
        assert config.retry_policy["base_delay"] == 2.0
        assert config.retry_policy["max_delay"] == 120.0
        assert config.retry_policy["exponential_base"] == 1.5

    def test_default_limits(self):
        """Test default rate limiting and size limits."""
        config = AdapterConfig(
            adapter_type="limits_test", connection_params={}, authentication={}
        )

        assert config.limits["max_orders_per_second"] == 10
        assert config.limits["max_daily_volume"] == 100000000.0
        assert config.limits["max_position_size"] == 10000000.0

    def test_custom_limits(self):
        """Test custom limit configuration."""
        custom_limits = {
            "max_orders_per_second": 5,
            "max_daily_volume": 50000000.0,
            "max_position_size": 5000000.0,
            "max_open_positions": 20,
        }

        config = AdapterConfig(
            adapter_type="custom_limits",
            connection_params={},
            authentication={},
            limits=custom_limits,
        )

        assert config.limits["max_orders_per_second"] == 5
        assert config.limits["max_daily_volume"] == 50000000.0
        assert config.limits["max_position_size"] == 5000000.0
        assert config.limits["max_open_positions"] == 20

    def test_default_features(self):
        """Test default feature flags."""
        config = AdapterConfig(
            adapter_type="features_test", connection_params={}, authentication={}
        )

        assert config.features["supports_market_data"] is True
        assert config.features["supports_order_modification"] is True
        assert config.features["supports_bulk_operations"] is False
        assert config.features["supports_portfolio_queries"] is True

    def test_custom_features(self):
        """Test custom feature configuration."""
        custom_features = {
            "supports_market_data": False,
            "supports_order_modification": False,
            "supports_bulk_operations": True,
            "supports_portfolio_queries": False,
            "supports_streaming": True,
        }

        config = AdapterConfig(
            adapter_type="custom_features",
            connection_params={},
            authentication={},
            features=custom_features,
        )

        assert config.features["supports_market_data"] is False
        assert config.features["supports_order_modification"] is False
        assert config.features["supports_bulk_operations"] is True
        assert config.features["supports_portfolio_queries"] is False
        assert config.features["supports_streaming"] is True

    def test_disabled_adapter_config(self):
        """Test creating disabled adapter configuration."""
        config = AdapterConfig(
            adapter_type="disabled_test",
            connection_params={},
            authentication={},
            enabled=False,
        )

        assert config.enabled is False


class TestBrokerConnectionStatus:
    """Comprehensive tests for BrokerConnection status management."""

    def test_connection_initial_state(self):
        """Test initial connection state."""
        connection = BrokerConnection(
            adapter_type="test_adapter", status=ConnectionStatus.DISCONNECTED
        )

        assert connection.adapter_type == "test_adapter"
        assert connection.status == ConnectionStatus.DISCONNECTED
        assert connection.connected_at is None
        assert connection.last_heartbeat is None
        assert connection.session_id is None
        assert connection.error_message is None
        assert connection.connection_count == 0
        assert connection.uptime_seconds == 0.0

    def test_connection_status_transitions(self):
        """Test all connection status transitions."""
        connection = BrokerConnection("test", ConnectionStatus.DISCONNECTED)

        # Test each status
        statuses = [
            ConnectionStatus.CONNECTING,
            ConnectionStatus.CONNECTED,
            ConnectionStatus.AUTHENTICATING,
            ConnectionStatus.AUTHENTICATED,
            ConnectionStatus.ERROR,
            ConnectionStatus.MAINTENANCE,
        ]

        for status in statuses:
            connection.status = status
            assert connection.status == status

    def test_is_connected_logic(self):
        """Test is_connected() method logic."""
        connection = BrokerConnection("test", ConnectionStatus.DISCONNECTED)

        # Should be False for disconnected states
        assert not connection.is_connected()

        connection.status = ConnectionStatus.CONNECTING
        assert not connection.is_connected()

        connection.status = ConnectionStatus.AUTHENTICATING
        assert not connection.is_connected()

        connection.status = ConnectionStatus.ERROR
        assert not connection.is_connected()

        connection.status = ConnectionStatus.MAINTENANCE
        assert not connection.is_connected()

        # Should be True for connected states
        connection.status = ConnectionStatus.CONNECTED
        assert connection.is_connected()

        connection.status = ConnectionStatus.AUTHENTICATED
        assert connection.is_connected()

    def test_is_ready_logic(self):
        """Test is_ready() method logic."""
        connection = BrokerConnection("test", ConnectionStatus.DISCONNECTED)

        # Should only be True for authenticated state
        assert not connection.is_ready()

        connection.status = ConnectionStatus.CONNECTING
        assert not connection.is_ready()

        connection.status = ConnectionStatus.CONNECTED
        assert not connection.is_ready()

        connection.status = ConnectionStatus.AUTHENTICATING
        assert not connection.is_ready()

        connection.status = ConnectionStatus.ERROR
        assert not connection.is_ready()

        connection.status = ConnectionStatus.MAINTENANCE
        assert not connection.is_ready()

        # Only authenticated should be ready
        connection.status = ConnectionStatus.AUTHENTICATED
        assert connection.is_ready()

    def test_connection_with_session_info(self):
        """Test connection with session information."""
        now = datetime.utcnow()
        connection = BrokerConnection(
            adapter_type="session_test",
            status=ConnectionStatus.AUTHENTICATED,
            connected_at=now,
            last_heartbeat=now,
            session_id="SESSION_123",
            connection_count=3,
            uptime_seconds=3600.0,
        )

        assert connection.connected_at == now
        assert connection.last_heartbeat == now
        assert connection.session_id == "SESSION_123"
        assert connection.connection_count == 3
        assert connection.uptime_seconds == 3600.0

    def test_connection_with_error(self):
        """Test connection with error information."""
        connection = BrokerConnection(
            adapter_type="error_test",
            status=ConnectionStatus.ERROR,
            error_message="Connection timeout",
        )

        assert connection.status == ConnectionStatus.ERROR
        assert connection.error_message == "Connection timeout"
        assert not connection.is_connected()
        assert not connection.is_ready()


class TestOrderInfoTracking:
    """Comprehensive tests for OrderInfo tracking."""

    def test_order_info_creation(self):
        """Test basic OrderInfo creation."""
        order_info = OrderInfo(cl_ord_id="TEST_ORDER_001")

        assert order_info.cl_ord_id == "TEST_ORDER_001"
        assert order_info.order_id is None
        assert order_info.status == OrderStatus.PENDING
        assert order_info.original_order is None
        assert order_info.last_execution is None
        assert isinstance(order_info.created_at, datetime)
        assert isinstance(order_info.updated_at, datetime)
        assert order_info.fills == []
        assert order_info.total_filled_qty == 0.0
        assert order_info.avg_fill_price == 0.0
        assert order_info.remaining_qty == 0.0
        assert order_info.error_message is None

    def test_order_info_with_broker_id(self):
        """Test OrderInfo with broker order ID."""
        order_info = OrderInfo(
            cl_ord_id="TEST_002", order_id="BROKER_456", status=OrderStatus.SUBMITTED
        )

        assert order_info.cl_ord_id == "TEST_002"
        assert order_info.order_id == "BROKER_456"
        assert order_info.status == OrderStatus.SUBMITTED

    def test_order_info_with_fills(self):
        """Test OrderInfo with fill information."""
        # Mock execution report
        execution = Mock()
        execution.last_qty = 50000
        execution.last_px = 1.1234

        order_info = OrderInfo(
            cl_ord_id="TEST_003",
            status=OrderStatus.PARTIALLY_FILLED,
            total_filled_qty=50000,
            avg_fill_price=1.1234,
            remaining_qty=50000,
        )
        order_info.fills.append(execution)

        assert order_info.status == OrderStatus.PARTIALLY_FILLED
        assert order_info.total_filled_qty == 50000
        assert order_info.avg_fill_price == 1.1234
        assert order_info.remaining_qty == 50000
        assert len(order_info.fills) == 1

    def test_order_info_with_error(self):
        """Test OrderInfo with error information."""
        order_info = OrderInfo(
            cl_ord_id="ERROR_ORDER",
            status=OrderStatus.REJECTED,
            error_message="Insufficient margin",
        )

        assert order_info.status == OrderStatus.REJECTED
        assert order_info.error_message == "Insufficient margin"

    def test_all_order_statuses(self):
        """Test all possible order statuses."""
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
            order_info = OrderInfo(cl_ord_id=f"TEST_{status.value}", status=status)
            assert order_info.status == status


class TestAdapterMetrics:
    """Comprehensive tests for AdapterMetrics tracking."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
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

    def test_metrics_with_data(self):
        """Test metrics with actual data."""
        now = datetime.utcnow()
        metrics = AdapterMetrics(
            total_orders=100,
            filled_orders=85,
            cancelled_orders=10,
            rejected_orders=3,
            failed_orders=2,
            total_modifications=15,
            failed_modifications=1,
            last_connect_time=now,
            bytes_sent=1024000,
            bytes_received=2048000,
            messages_sent=500,
            messages_received=750,
            uptime_seconds=7200.0,
        )

        assert metrics.total_orders == 100
        assert metrics.filled_orders == 85
        assert metrics.cancelled_orders == 10
        assert metrics.rejected_orders == 3
        assert metrics.failed_orders == 2
        assert metrics.total_modifications == 15
        assert metrics.failed_modifications == 1
        assert metrics.last_connect_time == now
        assert metrics.bytes_sent == 1024000
        assert metrics.bytes_received == 2048000
        assert metrics.messages_sent == 500
        assert metrics.messages_received == 750
        assert metrics.uptime_seconds == 7200.0

    def test_order_success_rate_calculation(self):
        """Test calculating order success metrics."""
        metrics = AdapterMetrics(
            total_orders=100,
            filled_orders=80,
            cancelled_orders=15,
            rejected_orders=3,
            failed_orders=2,
        )

        # Calculate success rates
        fill_rate = (
            metrics.filled_orders / metrics.total_orders
            if metrics.total_orders > 0
            else 0
        )
        rejection_rate = (
            metrics.rejected_orders / metrics.total_orders
            if metrics.total_orders > 0
            else 0
        )
        failure_rate = (
            metrics.failed_orders / metrics.total_orders
            if metrics.total_orders > 0
            else 0
        )

        assert fill_rate == 0.8  # 80%
        assert rejection_rate == 0.03  # 3%
        assert failure_rate == 0.02  # 2%

    def test_throughput_calculations(self):
        """Test throughput calculations."""
        metrics = AdapterMetrics(
            messages_sent=1000, messages_received=1500, uptime_seconds=3600.0  # 1 hour
        )

        # Calculate message throughput
        sent_per_second = metrics.messages_sent / metrics.uptime_seconds
        received_per_second = metrics.messages_received / metrics.uptime_seconds

        assert abs(sent_per_second - (1000 / 3600)) < 0.001
        assert abs(received_per_second - (1500 / 3600)) < 0.001


class TestFIXMessageIntegration:
    """Test integration with FIX message types."""

    def test_new_order_single_creation(self):
        """Test creating NewOrderSingle messages."""
        order = NewOrderSingle(
            cl_ord_id="FIX_TEST_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IOC,
        )

        assert order.cl_ord_id == "FIX_TEST_001"
        assert order.symbol == "EURUSD"
        assert order.side == Side.BUY
        assert order.order_qty == 100000
        assert order.ord_type == OrdType.MARKET
        assert order.time_in_force == TimeInForce.IOC

    def test_order_cancel_request_creation(self):
        """Test creating OrderCancelRequest messages."""
        cancel = OrderCancelRequest(
            orig_cl_ord_id="ORIGINAL_001",
            cl_ord_id="CANCEL_001",
            symbol="GBPUSD",
            side=Side.SELL,
        )

        assert cancel.orig_cl_ord_id == "ORIGINAL_001"
        assert cancel.cl_ord_id == "CANCEL_001"
        assert cancel.symbol == "GBPUSD"
        assert cancel.side == Side.SELL

    def test_execution_report_creation(self):
        """Test creating ExecutionReport messages."""
        # ExecutionReport creation depends on the specific implementation
        # For now, test that the class can be imported
        assert ExecutionReport is not None

        # Test would be more comprehensive once ExecutionReport is fully implemented
        # execution = ExecutionReport(
        #     order_id="BROKER_123",
        #     cl_ord_id="CLIENT_001",
        #     exec_id="EXEC_456",
        #     # ... other fields
        # )

    def test_side_enum_values(self):
        """Test Side enum values."""
        assert Side.BUY is not None
        assert Side.SELL is not None
        # Test that these are distinct
        assert Side.BUY != Side.SELL

    def test_ord_type_enum_values(self):
        """Test OrdType enum values."""
        assert OrdType.MARKET is not None
        assert OrdType.LIMIT is not None
        assert OrdType.STOP is not None
        # Test that these are distinct
        assert OrdType.MARKET != OrdType.LIMIT
        assert OrdType.LIMIT != OrdType.STOP

    def test_time_in_force_enum_values(self):
        """Test TimeInForce enum values."""
        assert TimeInForce.DAY is not None
        assert TimeInForce.GTC is not None  # Good Till Cancelled
        assert TimeInForce.IOC is not None  # Immediate Or Cancel
        assert TimeInForce.FOK is not None  # Fill Or Kill

        # Test that these are distinct
        assert TimeInForce.DAY != TimeInForce.GTC
        assert TimeInForce.GTC != TimeInForce.IOC
        assert TimeInForce.IOC != TimeInForce.FOK


class TestBaseAdapterInterface:
    """Test the BrokerAdapter abstract interface."""

    def test_adapter_abstract_methods(self):
        """Test that BrokerAdapter has required abstract methods."""
        # These methods should be abstract and require implementation
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

        for method_name in required_methods:
            assert hasattr(BrokerAdapter, method_name)
            method = getattr(BrokerAdapter, method_name)
            assert callable(method)

    def test_adapter_optional_methods(self):
        """Test optional methods with default implementations."""
        optional_methods = [
            "modify_order",
            "subscribe_market_data",
            "unsubscribe_market_data",
            "handle_test_request",
            "get_adapter_info",
        ]

        for method_name in optional_methods:
            assert hasattr(BrokerAdapter, method_name)
            method = getattr(BrokerAdapter, method_name)
            assert callable(method)

    def test_adapter_callback_methods(self):
        """Test callback setter methods."""
        callback_methods = [
            "set_execution_callback",
            "set_status_callback",
            "set_error_callback",
        ]

        for method_name in callback_methods:
            assert hasattr(BrokerAdapter, method_name)
            method = getattr(BrokerAdapter, method_name)
            assert callable(method)


if __name__ == "__main__":
    # Run tests with verbose output
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "-s", "--tb=short"],
        cwd=os.path.join(os.path.dirname(__file__), "../../../../"),
    )

    sys.exit(result.returncode)
