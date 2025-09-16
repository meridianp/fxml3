"""
Comprehensive retrospective test coverage for FXCM Bridge Adapter.

This module provides comprehensive test coverage for the FXML4 FXCM Bridge Adapter,
which handles integration between FXML4's FIX-based order management and FXCM's
ForexConnect API through RabbitMQ middleware.

Following TDD principles with retrospective testing approach:
- Testing existing production functionality
- Ensuring comprehensive coverage of all adapter features
- Validating integration patterns and error handling
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from fxml4.brokers.adapters.base import (
    AdapterConfig,
    BrokerAdapter,
    ConnectionStatus,
    OrderInfo,
    OrderStatus,
)
from fxml4.brokers.adapters.fxcm_bridge_adapter import (
    ConnectionState,
    ForexConnectOrder,
    FXCMBridgeAdapter,
    OrderState,
)
from fxml4.core.exceptions import BrokerError
from fxml4.core.exceptions import ConnectionError as FXMLConnectionError
from fxml4.core.exceptions import OrderRejectedError
from fxml4.core.exceptions import TimeoutError as FXMLTimeoutError
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import ExecutionReport as FIXExecutionReport
from fxml4.fix.messages.orders import NewOrderSingle


class TestFXCMBridgeAdapterInitialization:
    """Test adapter initialization and configuration."""

    def test_initialization_with_default_config(self):
        """Test adapter initializes correctly with default configuration."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge",
            endpoint="http://localhost:8080/forexconnect",
            credentials={"username": "test", "password": "test"},
        )

        adapter = FXCMBridgeAdapter(config)

        assert adapter.adapter_type == "fxcm_bridge"
        assert adapter.endpoint == "http://localhost:8080/forexconnect"
        assert adapter.connection_state == ConnectionState.DISCONNECTED
        assert len(adapter.pending_orders) == 0
        assert adapter.session is None

    def test_initialization_with_custom_rabbitmq_config(self):
        """Test adapter initialization with custom RabbitMQ configuration."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge",
            endpoint="http://custom-host:9090/forexconnect",
            credentials={"username": "test", "password": "test"},
            rabbitmq_url="amqp://user:pass@custom-rabbitmq:5672/",
            order_queue="custom_orders",
            execution_queue="custom_executions",
        )

        adapter = FXCMBridgeAdapter(config)

        assert adapter.rabbitmq_url == "amqp://user:pass@custom-rabbitmq:5672/"
        assert adapter.order_queue_name == "custom_orders"
        assert adapter.execution_queue_name == "custom_executions"

    def test_initialization_missing_credentials_raises_error(self):
        """Test adapter initialization fails with missing credentials."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge", endpoint="http://localhost:8080/forexconnect"
        )

        with pytest.raises(ValueError, match="Missing required credentials"):
            FXCMBridgeAdapter(config)

    def test_initialization_invalid_endpoint_format(self):
        """Test adapter initialization with invalid endpoint format."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge",
            endpoint="invalid-endpoint",
            credentials={"username": "test", "password": "test"},
        )

        with pytest.raises(ValueError, match="Invalid endpoint format"):
            FXCMBridgeAdapter(config)


class TestFXCMBridgeAdapterConnection:
    """Test connection management functionality."""

    @pytest.fixture
    def adapter(self):
        """Create adapter fixture for testing."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge",
            endpoint="http://localhost:8080/forexconnect",
            credentials={"username": "test", "password": "test"},
        )
        return FXCMBridgeAdapter(config)

    @pytest.mark.asyncio
    async def test_connect_successful(self, adapter):
        """Test successful connection establishment."""
        with (
            patch("aiohttp.ClientSession.post") as mock_post,
            patch("aio_pika.connect_robust") as mock_connect,
        ):

            # Mock HTTP authentication response
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                "status": "success",
                "session_id": "test-session-123",
            }
            mock_post.return_value.__aenter__.return_value = mock_response

            # Mock RabbitMQ connection
            mock_connection = AsyncMock()
            mock_channel = AsyncMock()
            mock_connection.channel.return_value = mock_channel
            mock_connect.return_value = mock_connection

            result = await adapter.connect()

            assert result is True
            assert adapter.connection_state == ConnectionState.CONNECTED
            assert adapter.session_id == "test-session-123"
            assert adapter.connection is not None
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_authentication_failure(self, adapter):
        """Test connection failure due to authentication error."""
        with patch("aiohttp.ClientSession.post") as mock_post:

            # Mock authentication failure
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                "status": "error",
                "message": "Invalid credentials",
            }
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await adapter.connect()

            assert result is False
            assert adapter.connection_state == ConnectionState.ERROR
            assert adapter.session_id is None

    @pytest.mark.asyncio
    async def test_connect_rabbitmq_failure(self, adapter):
        """Test connection failure due to RabbitMQ connectivity issues."""
        with (
            patch("aiohttp.ClientSession.post") as mock_post,
            patch("aio_pika.connect_robust") as mock_connect,
        ):

            # Mock successful authentication
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                "status": "success",
                "session_id": "test-session-123",
            }
            mock_post.return_value.__aenter__.return_value = mock_response

            # Mock RabbitMQ connection failure
            mock_connect.side_effect = FXMLConnectionError("RabbitMQ unavailable")

            result = await adapter.connect()

            assert result is False
            assert adapter.connection_state == ConnectionState.ERROR

    @pytest.mark.asyncio
    async def test_disconnect_successful(self, adapter):
        """Test successful disconnection."""
        # Set up connected state
        adapter.connection_state = ConnectionState.CONNECTED
        adapter.session_id = "test-session-123"
        adapter.connection = AsyncMock()
        adapter.channel = AsyncMock()

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = {"status": "success"}
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await adapter.disconnect()

            assert result is True
            assert adapter.connection_state == ConnectionState.DISCONNECTED
            assert adapter.session_id is None
            adapter.connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat_mechanism(self, adapter):
        """Test heartbeat mechanism maintains connection."""
        adapter.connection_state = ConnectionState.CONNECTED
        adapter.session_id = "test-session-123"

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = {"status": "alive"}
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await adapter._send_heartbeat()

            assert result is True
            mock_get.assert_called_once_with(
                f"{adapter.endpoint}/heartbeat",
                params={"session_id": "test-session-123"},
            )


class TestFXCMBridgeAdapterOrderManagement:
    """Test order lifecycle management functionality."""

    @pytest.fixture
    def connected_adapter(self):
        """Create connected adapter fixture."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge",
            endpoint="http://localhost:8080/forexconnect",
            credentials={"username": "test", "password": "test"},
        )
        adapter = FXCMBridgeAdapter(config)
        adapter.connection_state = ConnectionState.CONNECTED
        adapter.session_id = "test-session-123"
        adapter.channel = AsyncMock()
        return adapter

    @pytest.mark.asyncio
    async def test_submit_order_successful(self, connected_adapter):
        """Test successful order submission."""
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
            time_in_force=TimeInForce.IOC,
        )

        with patch.object(connected_adapter, "_publish_order") as mock_publish:
            mock_publish.return_value = "FXCM-ORDER-456"

            result = await connected_adapter.submit_order(order)

            assert result is True
            assert "ORDER-123" in connected_adapter.pending_orders
            order_info = connected_adapter.pending_orders["ORDER-123"]
            assert order_info.status == OrderStatus.SUBMITTED
            assert order_info.broker_order_id == "FXCM-ORDER-456"

    @pytest.mark.asyncio
    async def test_submit_order_invalid_symbol(self, connected_adapter):
        """Test order submission with invalid symbol."""
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="INVALID",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        with pytest.raises(OrderRejectedError, match="Invalid symbol"):
            await connected_adapter.submit_order(order)

    @pytest.mark.asyncio
    async def test_submit_order_insufficient_margin(self, connected_adapter):
        """Test order submission rejected due to insufficient margin."""
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=10000000.0,  # Very large quantity
        )

        with patch.object(connected_adapter, "_publish_order") as mock_publish:
            mock_publish.side_effect = OrderRejectedError("Insufficient margin")

            with pytest.raises(OrderRejectedError, match="Insufficient margin"):
                await connected_adapter.submit_order(order)

    @pytest.mark.asyncio
    async def test_cancel_order_successful(self, connected_adapter):
        """Test successful order cancellation."""
        # Set up existing order
        order_info = OrderInfo(
            cl_ord_id="ORDER-123",
            broker_order_id="FXCM-ORDER-456",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000.0,
            status=OrderStatus.WORKING,
        )
        connected_adapter.pending_orders["ORDER-123"] = order_info

        with patch.object(connected_adapter, "_publish_cancel") as mock_cancel:
            mock_cancel.return_value = True

            result = await connected_adapter.cancel_order("ORDER-123")

            assert result is True
            assert (
                connected_adapter.pending_orders["ORDER-123"].status
                == OrderStatus.PENDING_CANCEL
            )

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(self, connected_adapter):
        """Test cancellation of non-existent order."""
        result = await connected_adapter.cancel_order("NONEXISTENT")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_order_status_existing(self, connected_adapter):
        """Test retrieving status of existing order."""
        order_info = OrderInfo(
            cl_ord_id="ORDER-123",
            broker_order_id="FXCM-ORDER-456",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000.0,
            status=OrderStatus.FILLED,
            filled_qty=100000.0,
            avg_fill_price=1.1850,
        )
        connected_adapter.pending_orders["ORDER-123"] = order_info

        status = await connected_adapter.get_order_status("ORDER-123")

        assert status is not None
        assert status.status == OrderStatus.FILLED
        assert status.filled_qty == 100000.0
        assert status.avg_fill_price == 1.1850

    @pytest.mark.asyncio
    async def test_get_order_status_not_found(self, connected_adapter):
        """Test retrieving status of non-existent order."""
        status = await connected_adapter.get_order_status("NONEXISTENT")

        assert status is None


class TestFXCMBridgeAdapterMessageTranslation:
    """Test message translation between FIX and ForexConnect formats."""

    @pytest.fixture
    def adapter(self):
        """Create adapter fixture for testing."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge",
            endpoint="http://localhost:8080/forexconnect",
            credentials={"username": "test", "password": "test"},
        )
        return FXCMBridgeAdapter(config)

    def test_translate_fix_to_forexconnect_market_order(self, adapter):
        """Test FIX to ForexConnect message translation for market order."""
        fix_order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
            time_in_force=TimeInForce.IOC,
        )

        forex_order = adapter._translate_fix_to_forexconnect(fix_order)

        assert forex_order.symbol == "EUR/USD"
        assert forex_order.buy_sell == "B"
        assert forex_order.order_type == "M"  # Market
        assert forex_order.amount == 100
        assert forex_order.time_in_force == "IOC"

    def test_translate_fix_to_forexconnect_limit_order(self, adapter):
        """Test FIX to ForexConnect message translation for limit order."""
        fix_order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="GBPUSD",
            side=Side.SELL,
            ord_type=OrdType.LIMIT,
            order_qty=50000.0,
            price=1.3500,
            time_in_force=TimeInForce.GTC,
        )

        forex_order = adapter._translate_fix_to_forexconnect(fix_order)

        assert forex_order.symbol == "GBP/USD"
        assert forex_order.buy_sell == "S"
        assert forex_order.order_type == "L"  # Limit
        assert forex_order.amount == 50
        assert forex_order.rate == 1.3500
        assert forex_order.time_in_force == "GTC"

    def test_translate_forexconnect_to_fix_execution(self, adapter):
        """Test ForexConnect to FIX execution report translation."""
        forex_execution = {
            "order_id": "FXCM-ORDER-456",
            "client_order_id": "ORDER-123",
            "symbol": "EUR/USD",
            "buy_sell": "B",
            "amount": 100,
            "rate": 1.1850,
            "status": "F",  # Filled
            "exec_time": "2024-08-24T10:15:30.000Z",
        }

        fix_execution = adapter._translate_forexconnect_to_fix(forex_execution)

        assert fix_execution.order_id == "FXCM-ORDER-456"
        assert fix_execution.cl_ord_id == "ORDER-123"
        assert fix_execution.symbol == "EURUSD"
        assert fix_execution.side == Side.BUY
        assert fix_execution.last_qty == 100000.0
        assert fix_execution.last_px == 1.1850
        assert fix_execution.ord_status == "2"  # Filled

    def test_symbol_mapping_major_pairs(self, adapter):
        """Test symbol mapping for major forex pairs."""
        mappings = [
            ("EURUSD", "EUR/USD"),
            ("GBPUSD", "GBP/USD"),
            ("USDJPY", "USD/JPY"),
            ("AUDUSD", "AUD/USD"),
            ("USDCHF", "USD/CHF"),
            ("USDCAD", "USD/CAD"),
        ]

        for fix_symbol, forex_symbol in mappings:
            assert adapter._map_fix_to_forex_symbol(fix_symbol) == forex_symbol
            assert adapter._map_forex_to_fix_symbol(forex_symbol) == fix_symbol


class TestFXCMBridgeAdapterRabbitMQ:
    """Test RabbitMQ integration functionality."""

    @pytest.fixture
    def connected_adapter(self):
        """Create connected adapter with RabbitMQ mocked."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge",
            endpoint="http://localhost:8080/forexconnect",
            credentials={"username": "test", "password": "test"},
        )
        adapter = FXCMBridgeAdapter(config)
        adapter.connection_state = ConnectionState.CONNECTED
        adapter.channel = AsyncMock()
        return adapter

    @pytest.mark.asyncio
    async def test_publish_order_message(self, connected_adapter):
        """Test publishing order message to RabbitMQ."""
        order = ForexConnectOrder(
            request_id="REQ-123",
            correlation_id="CORR-456",
            symbol="EUR/USD",
            buy_sell="B",
            amount=100,
            order_type="M",
        )

        await connected_adapter._publish_order(order)

        connected_adapter.channel.default_exchange.publish.assert_called_once()
        call_args = connected_adapter.channel.default_exchange.publish.call_args
        message = call_args[0][0]
        assert "REQ-123" in message.body.decode()
        assert call_args[1]["routing_key"] == connected_adapter.order_queue_name

    @pytest.mark.asyncio
    async def test_consume_execution_reports(self, connected_adapter):
        """Test consuming execution reports from RabbitMQ."""
        mock_queue = AsyncMock()
        connected_adapter.execution_queue = mock_queue

        # Mock execution report message
        execution_data = {
            "order_id": "FXCM-ORDER-456",
            "client_order_id": "ORDER-123",
            "symbol": "EUR/USD",
            "status": "F",
        }

        mock_message = AsyncMock()
        mock_message.body = json.dumps(execution_data).encode()

        with patch.object(
            connected_adapter, "_process_execution_report"
        ) as mock_process:
            await connected_adapter._handle_execution_message(mock_message)

            mock_process.assert_called_once_with(execution_data)
            mock_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_rabbitmq_reconnection_on_failure(self, connected_adapter):
        """Test automatic RabbitMQ reconnection on connection failure."""
        # Simulate connection failure
        connected_adapter.connection.is_closed = True

        with patch.object(connected_adapter, "_setup_rabbitmq") as mock_setup:
            mock_setup.return_value = (AsyncMock(), AsyncMock())

            await connected_adapter._ensure_rabbitmq_connection()

            mock_setup.assert_called_once()


class TestFXCMBridgeAdapterErrorHandling:
    """Test error handling and recovery mechanisms."""

    @pytest.fixture
    def adapter(self):
        """Create adapter fixture for testing."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge",
            endpoint="http://localhost:8080/forexconnect",
            credentials={"username": "test", "password": "test"},
        )
        return FXCMBridgeAdapter(config)

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, adapter):
        """Test handling of network timeouts."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.side_effect = asyncio.TimeoutError("Network timeout")

            result = await adapter.connect()

            assert result is False
            assert adapter.connection_state == ConnectionState.ERROR

    @pytest.mark.asyncio
    async def test_invalid_json_response_handling(self, adapter):
        """Test handling of invalid JSON responses."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await adapter.connect()

            assert result is False
            assert adapter.connection_state == ConnectionState.ERROR

    @pytest.mark.asyncio
    async def test_order_rejection_handling(self, adapter):
        """Test proper handling of order rejections."""
        adapter.connection_state = ConnectionState.CONNECTED
        adapter.channel = AsyncMock()

        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        # Mock rejection response
        rejection_data = {
            "order_id": "FXCM-ORDER-456",
            "client_order_id": "ORDER-123",
            "status": "R",  # Rejected
            "reject_reason": "Insufficient margin",
        }

        with patch.object(adapter, "_publish_order") as mock_publish:
            mock_publish.side_effect = OrderRejectedError("Insufficient margin")

            with pytest.raises(OrderRejectedError):
                await adapter.submit_order(order)

    def test_configuration_validation_errors(self):
        """Test configuration validation error handling."""
        invalid_configs = [
            # Missing credentials
            {"adapter_type": "fxcm_bridge", "endpoint": "http://localhost:8080"},
            # Invalid endpoint
            {"adapter_type": "fxcm_bridge", "endpoint": "invalid", "credentials": {}},
            # Empty credentials
            {
                "adapter_type": "fxcm_bridge",
                "endpoint": "http://localhost:8080",
                "credentials": {},
            },
        ]

        for config_dict in invalid_configs:
            config = AdapterConfig(**config_dict)
            with pytest.raises(ValueError):
                FXCMBridgeAdapter(config)


class TestFXCMBridgeAdapterPerformance:
    """Test performance characteristics and optimization."""

    @pytest.fixture
    def adapter(self):
        """Create adapter fixture for performance testing."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge",
            endpoint="http://localhost:8080/forexconnect",
            credentials={"username": "test", "password": "test"},
        )
        return FXCMBridgeAdapter(config)

    @pytest.mark.asyncio
    async def test_concurrent_order_submissions(self, adapter):
        """Test handling of concurrent order submissions."""
        adapter.connection_state = ConnectionState.CONNECTED
        adapter.channel = AsyncMock()

        orders = [
            NewOrderSingle(
                cl_ord_id=f"ORDER-{i}",
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=10000.0,
            )
            for i in range(10)
        ]

        with patch.object(adapter, "_publish_order") as mock_publish:
            mock_publish.return_value = "FXCM-ORDER-123"

            tasks = [adapter.submit_order(order) for order in orders]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = sum(1 for r in results if r is True)
            assert success_count == 10
            assert len(adapter.pending_orders) == 10

    @pytest.mark.asyncio
    async def test_message_processing_throughput(self, adapter):
        """Test message processing throughput under load."""
        adapter.connection_state = ConnectionState.CONNECTED

        # Generate large number of execution reports
        execution_reports = [
            {
                "order_id": f"FXCM-ORDER-{i}",
                "client_order_id": f"ORDER-{i}",
                "symbol": "EUR/USD",
                "status": "F",
            }
            for i in range(100)
        ]

        start_time = datetime.now()

        for report in execution_reports:
            await adapter._process_execution_report(report)

        processing_time = (datetime.now() - start_time).total_seconds()

        # Should process 100 reports in under 1 second
        assert processing_time < 1.0

    def test_memory_usage_order_tracking(self, adapter):
        """Test memory usage remains reasonable with large number of orders."""
        # Simulate tracking many orders
        for i in range(1000):
            order_info = OrderInfo(
                cl_ord_id=f"ORDER-{i}",
                broker_order_id=f"FXCM-ORDER-{i}",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=10000.0,
                status=OrderStatus.FILLED,
            )
            adapter.pending_orders[f"ORDER-{i}"] = order_info

        assert len(adapter.pending_orders) == 1000

        # Test cleanup of filled orders
        adapter._cleanup_completed_orders()

        # Should maintain reasonable memory usage
        assert len(adapter.pending_orders) <= 1000


class TestFXCMBridgeAdapterIntegration:
    """Test integration scenarios and workflows."""

    @pytest.fixture
    def connected_adapter(self):
        """Create fully connected adapter for integration tests."""
        config = AdapterConfig(
            adapter_type="fxcm_bridge",
            endpoint="http://localhost:8080/forexconnect",
            credentials={"username": "test", "password": "test"},
        )
        adapter = FXCMBridgeAdapter(config)
        adapter.connection_state = ConnectionState.CONNECTED
        adapter.session_id = "test-session-123"
        adapter.channel = AsyncMock()
        return adapter

    @pytest.mark.asyncio
    async def test_complete_order_lifecycle(self, connected_adapter):
        """Test complete order lifecycle from submission to execution."""
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        with patch.object(connected_adapter, "_publish_order") as mock_publish:
            mock_publish.return_value = "FXCM-ORDER-456"

            # Submit order
            result = await connected_adapter.submit_order(order)
            assert result is True

            # Simulate acknowledgment
            ack_data = {
                "order_id": "FXCM-ORDER-456",
                "client_order_id": "ORDER-123",
                "status": "A",  # Acknowledged
            }
            await connected_adapter._process_execution_report(ack_data)

            order_info = connected_adapter.pending_orders["ORDER-123"]
            assert order_info.status == OrderStatus.ACKNOWLEDGED

            # Simulate execution
            exec_data = {
                "order_id": "FXCM-ORDER-456",
                "client_order_id": "ORDER-123",
                "symbol": "EUR/USD",
                "buy_sell": "B",
                "amount": 100,
                "rate": 1.1850,
                "status": "F",  # Filled
            }
            await connected_adapter._process_execution_report(exec_data)

            order_info = connected_adapter.pending_orders["ORDER-123"]
            assert order_info.status == OrderStatus.FILLED
            assert order_info.filled_qty == 100000.0
            assert order_info.avg_fill_price == 1.1850

    @pytest.mark.asyncio
    async def test_partial_fill_handling(self, connected_adapter):
        """Test handling of partial order fills."""
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.LIMIT,
            order_qty=100000.0,
            price=1.1800,
        )

        with patch.object(connected_adapter, "_publish_order") as mock_publish:
            mock_publish.return_value = "FXCM-ORDER-456"

            await connected_adapter.submit_order(order)

            # First partial fill
            partial_exec = {
                "order_id": "FXCM-ORDER-456",
                "client_order_id": "ORDER-123",
                "symbol": "EUR/USD",
                "amount": 30,  # Partial amount
                "rate": 1.1800,
                "status": "P",  # Partially filled
            }
            await connected_adapter._process_execution_report(partial_exec)

            order_info = connected_adapter.pending_orders["ORDER-123"]
            assert order_info.status == OrderStatus.PARTIALLY_FILLED
            assert order_info.filled_qty == 30000.0

            # Complete the fill
            final_exec = {
                "order_id": "FXCM-ORDER-456",
                "client_order_id": "ORDER-123",
                "symbol": "EUR/USD",
                "amount": 70,  # Remaining amount
                "rate": 1.1800,
                "status": "F",  # Filled
            }
            await connected_adapter._process_execution_report(final_exec)

            order_info = connected_adapter.pending_orders["ORDER-123"]
            assert order_info.status == OrderStatus.FILLED
            assert order_info.filled_qty == 100000.0

    @pytest.mark.asyncio
    async def test_connection_recovery_workflow(self, connected_adapter):
        """Test connection recovery and order state preservation."""
        # Submit orders before disconnection
        orders = [
            NewOrderSingle(
                cl_ord_id=f"ORDER-{i}",
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=10000.0,
            )
            for i in range(5)
        ]

        with patch.object(connected_adapter, "_publish_order") as mock_publish:
            mock_publish.return_value = "FXCM-ORDER-456"

            for order in orders:
                await connected_adapter.submit_order(order)

        assert len(connected_adapter.pending_orders) == 5

        # Simulate disconnection
        connected_adapter.connection_state = ConnectionState.DISCONNECTED

        # Simulate reconnection
        with patch.object(connected_adapter, "connect") as mock_connect:
            mock_connect.return_value = True

            result = await connected_adapter.connect()
            assert result is True

            # Orders should still be tracked
            assert len(connected_adapter.pending_orders) == 5
