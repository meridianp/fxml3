"""Unit tests for FXCM Broker Adapter.

This module provides comprehensive tests for the FXCM adapter implementation including:
- Initialization and configuration
- Connection and disconnection scenarios
- Order submission, cancellation, and modification
- Error handling and edge cases
- Bridge service communication
- Mock scenarios for external dependencies
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest

from fxml4.brokers.adapters.base import AdapterConfig, AdapterMetrics, ConnectionStatus
from fxml4.brokers.adapters.fxcm_adapter import FXCMBrokerAdapter
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)


@pytest.fixture
def fxcm_config():
    """Create FXCM adapter configuration for testing."""
    return AdapterConfig(
        adapter_type="fxcm",
        connection_params={
            "bridge_url": "http://test-bridge:9090",
            "api_key": "test_api_key",
        },
        authentication={"username": "test_user", "password": "test_pass"},
        timeouts={"connect": 30, "authenticate": 60, "order": 300},
        features={
            "supports_market_data": True,
            "supports_order_modification": False,
            "simulate_execution": True,
        },
    )


@pytest.fixture
def sample_order():
    """Create sample FIX order for testing."""
    return NewOrderSingle(
        cl_ord_id="TEST_ORDER_001",
        symbol="EURUSD",
        side=Side.BUY,
        order_qty=100000,
        ord_type=OrdType.MARKET,
        time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
    )


@pytest.fixture
def sample_limit_order():
    """Create sample limit order for testing."""
    return NewOrderSingle(
        cl_ord_id="TEST_LIMIT_001",
        symbol="GBPUSD",
        side=Side.SELL,
        order_qty=50000,
        ord_type=OrdType.LIMIT,
        price=1.2500,
        time_in_force=TimeInForce.DAY,
    )


@pytest.fixture
def mock_aiohttp_session():
    """Create mock aiohttp session."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock()

    # Create context manager for response
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    mock_session.get.return_value = mock_context
    mock_session.post.return_value = mock_context
    mock_session.delete.return_value = mock_context
    mock_session.close = AsyncMock()

    return mock_session, mock_response


class TestFXCMAdapterInitialization:
    """Test FXCM adapter initialization and configuration."""

    def test_adapter_initialization(self, fxcm_config):
        """Test successful adapter initialization."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        assert adapter.bridge_url == "http://test-bridge:9090"
        assert adapter.api_key == "test_api_key"
        assert adapter.adapter_type == "fxcm"
        assert adapter.connection.status == ConnectionStatus.DISCONNECTED
        assert adapter.session is None
        assert len(adapter.active_orders) == 0
        assert len(adapter.order_map) == 0

    def test_adapter_initialization_default_bridge_url(self):
        """Test adapter initialization with default bridge URL."""
        config = AdapterConfig(
            adapter_type="fxcm", connection_params={}, authentication={}
        )

        adapter = FXCMBrokerAdapter(config)
        assert adapter.bridge_url == "http://fxcm-bridge:9090"
        assert adapter.api_key is None

    def test_adapter_initialization_with_custom_timeouts(self):
        """Test adapter initialization with custom timeout settings."""
        config = AdapterConfig(
            adapter_type="fxcm",
            connection_params={
                "bridge_url": "http://custom-bridge:8080",
                "connect_timeout": 45,
                "order_timeout": 600,
            },
            authentication={},
        )

        adapter = FXCMBrokerAdapter(config)
        assert adapter.bridge_url == "http://custom-bridge:8080"


class TestFXCMAdapterConnection:
    """Test FXCM adapter connection management."""

    @pytest.mark.asyncio
    async def test_successful_connection(self, fxcm_config, mock_aiohttp_session):
        """Test successful connection to FXCM bridge."""
        mock_session, mock_response = mock_aiohttp_session

        # Mock health and status responses
        mock_response.json.side_effect = [
            {"connected": True, "status": "ok"},  # Health check
            {"account_id": "123456789", "connected": True},  # Status check
        ]

        adapter = FXCMBrokerAdapter(fxcm_config)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch.object(adapter, "_monitor_bridge", new=AsyncMock()):
                result = await adapter.connect()

        assert result is True
        assert adapter.connection.status == ConnectionStatus.READY
        assert adapter.bridge_connected is True
        assert adapter.account_id == "123456789"
        assert adapter.metrics.last_connect_time is not None

    @pytest.mark.asyncio
    async def test_connection_health_check_failure(
        self, fxcm_config, mock_aiohttp_session
    ):
        """Test connection failure during health check."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.status = 500

        adapter = FXCMBrokerAdapter(fxcm_config)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await adapter.connect()

        assert result is False
        assert adapter.connection.status == ConnectionStatus.ERROR
        assert adapter.session is None

    @pytest.mark.asyncio
    async def test_connection_bridge_not_connected(
        self, fxcm_config, mock_aiohttp_session
    ):
        """Test connection when bridge is not connected to FXCM."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.json.side_effect = [
            {"connected": False, "status": "disconnected"},  # Health check
            {"account_id": None, "connected": False},  # Status check
        ]

        adapter = FXCMBrokerAdapter(fxcm_config)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch.object(adapter, "_monitor_bridge", new=AsyncMock()):
                result = await adapter.connect()

        assert result is True  # Adapter connects but bridge is not connected
        assert adapter.connection.status == ConnectionStatus.READY
        assert adapter.bridge_connected is False

    @pytest.mark.asyncio
    async def test_connection_exception_handling(self, fxcm_config):
        """Test connection exception handling."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        with patch("aiohttp.ClientSession", side_effect=Exception("Connection failed")):
            result = await adapter.connect()

        assert result is False
        assert adapter.connection.status == ConnectionStatus.ERROR
        assert "Connection failed" in adapter.connection.error

    @pytest.mark.asyncio
    async def test_successful_disconnect(self, fxcm_config):
        """Test successful disconnection."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        # Set up connected state
        adapter.connection.status = ConnectionStatus.READY
        adapter.session = MagicMock()
        adapter._monitor_task = MagicMock()
        adapter._monitor_task.cancel = MagicMock()
        adapter._monitor_task.done = MagicMock(return_value=True)
        adapter.active_orders["TEST"] = {"test": "data"}
        adapter.order_map["TEST"] = "BRIDGE_ID"

        await adapter.disconnect()

        assert adapter.connection.status == ConnectionStatus.DISCONNECTED
        assert len(adapter.active_orders) == 0
        assert len(adapter.order_map) == 0
        assert adapter.bridge_connected is False
        assert adapter.metrics.last_disconnect_time is not None

    @pytest.mark.asyncio
    async def test_disconnect_with_monitor_task(self, fxcm_config):
        """Test disconnection with active monitor task."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        # Set up monitor task
        monitor_task = MagicMock()
        monitor_task.cancel = MagicMock()
        adapter._monitor_task = monitor_task

        # Mock session
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        adapter.session = mock_session

        await adapter.disconnect()

        monitor_task.cancel.assert_called_once()
        mock_session.close.assert_called_once()


class TestFXCMAdapterOrderManagement:
    """Test FXCM adapter order management operations."""

    @pytest.mark.asyncio
    async def test_successful_order_submission(
        self, fxcm_config, sample_order, mock_aiohttp_session
    ):
        """Test successful order submission."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.json.return_value = {
            "success": True,
            "order_id": "FXCM_12345",
            "message": "Order submitted successfully",
        }

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        with patch.object(adapter.fix_builder, "build", return_value="FIX_MESSAGE"):
            result = await adapter.submit_order(sample_order)

        assert result == "FXCM_12345"
        assert sample_order.cl_ord_id in adapter.active_orders
        assert adapter.order_map[sample_order.cl_ord_id] == "FXCM_12345"
        assert adapter.metrics.total_orders == 1

    @pytest.mark.asyncio
    async def test_order_submission_without_connection(self, fxcm_config, sample_order):
        """Test order submission without active connection."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        with pytest.raises(Exception, match="Not connected to bridge service"):
            await adapter.submit_order(sample_order)

    @pytest.mark.asyncio
    async def test_order_submission_bridge_error(
        self, fxcm_config, sample_order, mock_aiohttp_session
    ):
        """Test order submission with bridge error response."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Invalid order parameters")

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        with patch.object(adapter.fix_builder, "build", return_value="FIX_MESSAGE"):
            with pytest.raises(Exception, match="Order submission failed"):
                await adapter.submit_order(sample_order)

        assert adapter.metrics.failed_orders == 1

    @pytest.mark.asyncio
    async def test_order_submission_bridge_failure_response(
        self, fxcm_config, sample_order, mock_aiohttp_session
    ):
        """Test order submission with bridge failure response."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.json.return_value = {
            "success": False,
            "message": "Insufficient margin",
        }

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        with patch.object(adapter.fix_builder, "build", return_value="FIX_MESSAGE"):
            with pytest.raises(Exception, match="Insufficient margin"):
                await adapter.submit_order(sample_order)

    @pytest.mark.asyncio
    async def test_successful_order_cancellation(
        self, fxcm_config, mock_aiohttp_session
    ):
        """Test successful order cancellation."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.json.return_value = {
            "success": True,
            "message": "Order cancelled",
        }

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        # Set up existing order
        cl_ord_id = "TEST_CANCEL_001"
        bridge_order_id = "FXCM_CANCEL_123"
        adapter.active_orders[cl_ord_id] = {
            "bridge_order_id": bridge_order_id,
            "status": "Submitted",
        }
        adapter.order_map[cl_ord_id] = bridge_order_id

        cancel_request = OrderCancelRequest(
            orig_cl_ord_id=cl_ord_id,
            cl_ord_id="CANCEL_REQ_001",
            symbol="EURUSD",
            side=Side.BUY,
        )

        result = await adapter.cancel_order(cancel_request)

        assert result is True
        assert adapter.active_orders[cl_ord_id]["status"] == "Cancelled"
        assert adapter.metrics.cancelled_orders == 1

    @pytest.mark.asyncio
    async def test_order_cancellation_not_found(
        self, fxcm_config, mock_aiohttp_session
    ):
        """Test order cancellation for non-existent order."""
        mock_session, mock_response = mock_aiohttp_session

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        cancel_request = OrderCancelRequest(
            orig_cl_ord_id="NON_EXISTENT",
            cl_ord_id="CANCEL_REQ_002",
            symbol="EURUSD",
            side=Side.BUY,
        )

        result = await adapter.cancel_order(cancel_request)

        assert result is False

    @pytest.mark.asyncio
    async def test_order_cancellation_bridge_error(
        self, fxcm_config, mock_aiohttp_session
    ):
        """Test order cancellation with bridge error."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Order not found")

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        # Set up existing order
        cl_ord_id = "TEST_CANCEL_ERROR"
        bridge_order_id = "FXCM_ERROR_123"
        adapter.order_map[cl_ord_id] = bridge_order_id

        cancel_request = OrderCancelRequest(
            orig_cl_ord_id=cl_ord_id,
            cl_ord_id="CANCEL_REQ_003",
            symbol="EURUSD",
            side=Side.BUY,
        )

        result = await adapter.cancel_order(cancel_request)

        assert result is False


class TestFXCMAdapterOrderStatus:
    """Test FXCM adapter order status operations."""

    @pytest.mark.asyncio
    async def test_get_order_status_success(self, fxcm_config, mock_aiohttp_session):
        """Test successful order status retrieval."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.json.return_value = {
            "status": "Executing",
            "filled_qty": 0,
            "remaining_qty": 100000,
        }

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        # Set up existing order
        cl_ord_id = "TEST_STATUS_001"
        bridge_order_id = "FXCM_STATUS_123"
        sample_order = NewOrderSingle(
            cl_ord_id=cl_ord_id,
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        adapter.active_orders[cl_ord_id] = {
            "bridge_order_id": bridge_order_id,
            "order": sample_order,
            "status": "Submitted",
        }
        adapter.order_map[cl_ord_id] = bridge_order_id

        result = await adapter.get_order_status(cl_ord_id)

        assert result is not None
        assert isinstance(result, ExecutionReport)
        assert result.cl_ord_id == cl_ord_id
        assert result.order_id == bridge_order_id

    @pytest.mark.asyncio
    async def test_get_order_status_not_found(self, fxcm_config, mock_aiohttp_session):
        """Test order status retrieval for non-existent order."""
        mock_session, mock_response = mock_aiohttp_session

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        result = await adapter.get_order_status("NON_EXISTENT")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_order_status_bridge_404(self, fxcm_config, mock_aiohttp_session):
        """Test order status retrieval with bridge 404 response."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.status = 404

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        # Set up existing order
        cl_ord_id = "TEST_404"
        bridge_order_id = "FXCM_404"
        adapter.order_map[cl_ord_id] = bridge_order_id

        result = await adapter.get_order_status(cl_ord_id)

        assert result is None


class TestFXCMAdapterMarketData:
    """Test FXCM adapter market data operations."""

    @pytest.mark.asyncio
    async def test_successful_market_data_subscription(
        self, fxcm_config, mock_aiohttp_session
    ):
        """Test successful market data subscription."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.json.return_value = {
            "success": True,
            "message": "Subscribed successfully",
        }

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        result = await adapter.subscribe_market_data(symbols)

        assert result is True

    @pytest.mark.asyncio
    async def test_market_data_subscription_failure(
        self, fxcm_config, mock_aiohttp_session
    ):
        """Test market data subscription failure."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.status = 400

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        symbols = ["INVALID_SYMBOL"]
        result = await adapter.subscribe_market_data(symbols)

        assert result is False

    @pytest.mark.asyncio
    async def test_market_data_subscription_without_connection(self, fxcm_config):
        """Test market data subscription without connection."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        symbols = ["EURUSD"]
        result = await adapter.subscribe_market_data(symbols)

        assert result is False

    @pytest.mark.asyncio
    async def test_successful_market_data_unsubscription(
        self, fxcm_config, mock_aiohttp_session
    ):
        """Test successful market data unsubscription."""
        mock_session, mock_response = mock_aiohttp_session

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        symbols = ["EURUSD", "GBPUSD"]
        result = await adapter.unsubscribe_market_data(symbols)

        assert result is True


class TestFXCMAdapterMonitoring:
    """Test FXCM adapter monitoring and health checks."""

    @pytest.mark.asyncio
    async def test_monitor_bridge_health_check(self, fxcm_config, mock_aiohttp_session):
        """Test bridge monitoring health check."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.json.return_value = {"connected": True, "status": "ok"}

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session
        adapter.connection.status = ConnectionStatus.CONNECTED

        # Test single monitor iteration
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await adapter._monitor_bridge()

        assert adapter.bridge_connected is True
        assert adapter.last_heartbeat is not None

    @pytest.mark.asyncio
    async def test_monitor_bridge_connection_lost(
        self, fxcm_config, mock_aiohttp_session
    ):
        """Test monitoring when bridge loses connection."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.json.return_value = {"connected": False, "status": "disconnected"}

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session
        adapter.connection.status = ConnectionStatus.READY

        # Test single monitor iteration
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await adapter._monitor_bridge()

        assert adapter.bridge_connected is False
        assert adapter.connection.status == ConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_monitor_bridge_status_error(self, fxcm_config, mock_aiohttp_session):
        """Test monitoring with bridge status error."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.status = 500

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        # Test single monitor iteration
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await adapter._monitor_bridge()


class TestFXCMAdapterUtilities:
    """Test FXCM adapter utility methods."""

    def test_map_order_status_known_statuses(self, fxcm_config):
        """Test order status mapping for known statuses."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        status_mappings = [
            ("Executing", OrdStatus.NEW),
            ("Executed", OrdStatus.FILLED),
            ("Cancelled", OrdStatus.CANCELED),
            ("Rejected", OrdStatus.REJECTED),
            ("Expired", OrdStatus.EXPIRED),
            ("PartiallyFilled", OrdStatus.PARTIALLY_FILLED),
        ]

        for bridge_status, expected_fix_status in status_mappings:
            result = adapter._map_order_status(bridge_status)
            assert result == expected_fix_status

    def test_map_order_status_unknown_status(self, fxcm_config):
        """Test order status mapping for unknown status."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        result = adapter._map_order_status("UnknownStatus")
        assert result == OrdStatus.NEW

    @pytest.mark.asyncio
    async def test_process_execution_report(self, fxcm_config):
        """Test execution report processing."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        # Mock FIX parser
        mock_parser = MagicMock()
        mock_execution_report = MagicMock()
        mock_execution_report.cl_ord_id = "TEST_EXEC_001"
        mock_execution_report.ord_status.name = "FILLED"
        mock_parser.parse.return_value = mock_execution_report
        adapter.fix_parser = mock_parser

        # Set up order tracking
        adapter.active_orders["TEST_EXEC_001"] = {"status": "Submitted"}

        await adapter._process_execution_report("FIX_MESSAGE")

        assert adapter.active_orders["TEST_EXEC_001"]["status"] == "FILLED"


class TestFXCMAdapterEdgeCases:
    """Test FXCM adapter edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_modify_order_not_implemented(self, fxcm_config):
        """Test that order modification is not implemented."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        mock_modify_request = MagicMock()
        result = await adapter.modify_order(mock_modify_request)

        assert result is False

    @pytest.mark.asyncio
    async def test_connection_with_missing_api_key(self):
        """Test connection without API key."""
        config = AdapterConfig(
            adapter_type="fxcm",
            connection_params={"bridge_url": "http://test-bridge:9090"},
            authentication={},
        )

        adapter = FXCMBrokerAdapter(config)
        assert adapter.api_key is None

        # Should still work without API key
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            # Mock successful responses
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"connected": True})

            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_session.get.return_value = mock_context

            with patch.object(adapter, "_monitor_bridge", new=AsyncMock()):
                result = await adapter.connect()

            assert result is True

    @pytest.mark.asyncio
    async def test_order_submission_with_execution_report(
        self, fxcm_config, sample_order, mock_aiohttp_session
    ):
        """Test order submission that includes execution report in response."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.json.return_value = {
            "success": True,
            "order_id": "FXCM_WITH_EXEC",
            "execution_report": "FIX_EXEC_REPORT",
        }

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        with patch.object(adapter.fix_builder, "build", return_value="FIX_MESSAGE"):
            with patch.object(
                adapter, "_process_execution_report", new=AsyncMock()
            ) as mock_process:
                result = await adapter.submit_order(sample_order)

                mock_process.assert_called_once_with("FIX_EXEC_REPORT")

        assert result == "FXCM_WITH_EXEC"

    @pytest.mark.asyncio
    async def test_order_submission_missing_order_id(
        self, fxcm_config, sample_order, mock_aiohttp_session
    ):
        """Test order submission with missing order ID in response."""
        mock_session, mock_response = mock_aiohttp_session
        mock_response.json.return_value = {
            "success": True,
            "message": "Order submitted",
            # Missing order_id
        }

        adapter = FXCMBrokerAdapter(fxcm_config)
        adapter.session = mock_session

        with patch.object(adapter.fix_builder, "build", return_value="FIX_MESSAGE"):
            with pytest.raises(Exception, match="No order ID returned from bridge"):
                await adapter.submit_order(sample_order)


# Integration-style tests
class TestFXCMAdapterIntegration:
    """Integration-style tests for FXCM adapter workflows."""

    @pytest.mark.asyncio
    async def test_complete_order_lifecycle(self, fxcm_config):
        """Test complete order lifecycle: submit -> status -> cancel."""
        adapter = FXCMBrokerAdapter(fxcm_config)

        # Mock session with multiple responses
        mock_session = MagicMock()
        mock_session.close = AsyncMock()

        # Order submission response
        submit_response = MagicMock()
        submit_response.status = 200
        submit_response.json = AsyncMock(
            return_value={"success": True, "order_id": "LIFECYCLE_001"}
        )

        # Status check response
        status_response = MagicMock()
        status_response.status = 200
        status_response.json = AsyncMock(return_value={"status": "Executing"})

        # Cancel response
        cancel_response = MagicMock()
        cancel_response.status = 200
        cancel_response.json = AsyncMock(return_value={"success": True})

        # Set up context managers
        submit_context = MagicMock()
        submit_context.__aenter__ = AsyncMock(return_value=submit_response)
        submit_context.__aexit__ = AsyncMock(return_value=None)

        status_context = MagicMock()
        status_context.__aenter__ = AsyncMock(return_value=status_response)
        status_context.__aexit__ = AsyncMock(return_value=None)

        cancel_context = MagicMock()
        cancel_context.__aenter__ = AsyncMock(return_value=cancel_response)
        cancel_context.__aexit__ = AsyncMock(return_value=None)

        mock_session.post.return_value = submit_context
        mock_session.get.return_value = status_context
        mock_session.delete.return_value = cancel_context

        adapter.session = mock_session

        # Create test order
        order = NewOrderSingle(
            cl_ord_id="LIFECYCLE_ORDER",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        # Submit order
        with patch.object(adapter.fix_builder, "build", return_value="FIX_MESSAGE"):
            order_id = await adapter.submit_order(order)

        assert order_id == "LIFECYCLE_001"
        assert order.cl_ord_id in adapter.active_orders

        # Check status
        status = await adapter.get_order_status(order.cl_ord_id)
        assert status is not None

        # Cancel order
        cancel_request = OrderCancelRequest(
            orig_cl_ord_id=order.cl_ord_id,
            cl_ord_id="CANCEL_LIFECYCLE",
            symbol="EURUSD",
            side=Side.BUY,
        )

        cancel_result = await adapter.cancel_order(cancel_request)
        assert cancel_result is True
        assert adapter.active_orders[order.cl_ord_id]["status"] == "Cancelled"
