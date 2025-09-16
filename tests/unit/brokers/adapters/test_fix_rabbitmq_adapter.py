"""Unit tests for FIX RabbitMQ Broker Adapter.

This module provides comprehensive tests for the FIX RabbitMQ adapter implementation including:
- Initialization and configuration
- Connection and disconnection scenarios
- RabbitMQ message handling and processing
- Order submission, cancellation, and modification via messages
- Market data subscription handling
- Execution report processing and forwarding
- Message acknowledgment and rejection
- Error handling and edge cases
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.brokers.adapters.base import AdapterConfig, AdapterMetrics, ConnectionStatus
from fxml4.brokers.adapters.fix_rabbitmq_adapter import FixRabbitMQAdapter
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.market_data import MarketDataRequest, MarketDataSnapshot
from fxml4.fix.messages.order_modify import OrderCancelReplaceRequest
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)


@pytest.fixture
def fix_rabbitmq_config():
    """Create FIX RabbitMQ adapter configuration for testing."""
    return AdapterConfig(
        adapter_type="fix_rabbitmq",
        connection_params={
            # FIX connection params
            "host": "test-fix-server",
            "port": 9876,
            "session": {
                "sender_comp_id": "FXML4_TEST",
                "target_comp_id": "FIX_BROKER",
                "fix_version": "FIX.4.2",
                "heartbeat_interval": 30,
            },
            # RabbitMQ connection params
            "rabbitmq": {
                "host": "test-rabbitmq",
                "port": 5672,
                "username": "test_user",
                "password": "test_pass",
                "virtual_host": "/test",
            },
        },
        authentication={"username": "fix_user", "password": "fix_pass"},
        features={"supports_market_data": True, "supports_order_modification": True},
    )


@pytest.fixture
def mock_rabbitmq_manager():
    """Create mock RabbitMQ connection manager."""
    manager = MagicMock()
    manager.connect = AsyncMock(return_value=True)
    manager.disconnect = AsyncMock()
    manager.publish_execution_report = AsyncMock()
    manager.publish_market_data = AsyncMock()
    manager.register_handler = AsyncMock()
    manager.ack_message = AsyncMock()
    manager.reject_message = AsyncMock()
    return manager


@pytest.fixture
def mock_fix_adapter():
    """Create mock FIX adapter."""
    adapter = MagicMock()
    adapter.connect = AsyncMock(return_value=True)
    adapter.disconnect = AsyncMock()
    adapter.submit_order = AsyncMock(return_value="FIX_ORDER_123")
    adapter.cancel_order = AsyncMock(return_value=True)
    adapter.modify_order = AsyncMock(return_value=True)
    adapter.request_market_data = AsyncMock(return_value=True)
    adapter._is_ready = MagicMock(return_value=True)

    # Mock session
    mock_session = MagicMock()
    mock_session.session_id = "TEST_SESSION"
    mock_session.stats.to_dict = MagicMock(
        return_value={"messages_sent": 10, "messages_received": 8}
    )
    adapter.session = mock_session

    return adapter


@pytest.fixture
def sample_order():
    """Create sample FIX order for testing."""
    return NewOrderSingle(
        cl_ord_id="FIXRABBITMQ_001",
        symbol="EURUSD",
        side=Side.BUY,
        order_qty=100000,
        ord_type=OrdType.MARKET,
    )


@pytest.fixture
def sample_execution_report():
    """Create sample execution report."""
    return ExecutionReport(
        order_id="FIX_ORDER_123",
        cl_ord_id="FIXRABBITMQ_001",
        exec_id="EXEC_456",
        exec_type=ExecType.NEW,
        ord_status=OrdStatus.NEW,
        symbol="EURUSD",
        side=Side.BUY,
        order_qty=100000,
        cum_qty=0,
        leaves_qty=100000,
        avg_px=0,
        transact_time=datetime.now(timezone.utc),
    )


class TestFixRabbitMQAdapterInitialization:
    """Test FIX RabbitMQ adapter initialization and configuration."""

    @patch("fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager")
    @patch("fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter")
    def test_adapter_initialization(
        self, mock_fix_class, mock_rabbitmq_factory, fix_rabbitmq_config
    ):
        """Test successful adapter initialization."""
        mock_rabbitmq_manager = MagicMock()
        mock_rabbitmq_factory.return_value = mock_rabbitmq_manager
        mock_fix_adapter = MagicMock()
        mock_fix_class.return_value = mock_fix_adapter

        adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

        assert adapter.adapter_type == "fix_rabbitmq"
        assert adapter.fix_adapter == mock_fix_adapter
        assert adapter.rabbitmq_manager == mock_rabbitmq_manager
        assert len(adapter.order_tracking) == 0
        assert len(adapter.market_data_subscriptions) == 0

        # Verify message handlers are set up
        expected_handlers = [
            "new_order",
            "cancel_order",
            "modify_order",
            "market_data_request",
            "order_status_request",
        ]

        for handler_type in expected_handlers:
            assert handler_type in adapter._message_handlers

    @patch("fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager")
    @patch("fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter")
    def test_adapter_initialization_callbacks_setup(
        self, mock_fix_class, mock_rabbitmq_factory, fix_rabbitmq_config
    ):
        """Test that callbacks are properly set up during initialization."""
        mock_rabbitmq_manager = MagicMock()
        mock_rabbitmq_factory.return_value = mock_rabbitmq_manager
        mock_fix_adapter = MagicMock()
        mock_fix_class.return_value = mock_fix_adapter

        adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

        # Verify RabbitMQ callbacks
        assert adapter.rabbitmq_manager.on_connection_open is not None
        assert adapter.rabbitmq_manager.on_connection_closed is not None
        assert adapter.rabbitmq_manager.on_connection_error is not None


class TestFixRabbitMQAdapterConnection:
    """Test FIX RabbitMQ adapter connection management."""

    @pytest.mark.asyncio
    async def test_successful_connection(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test successful connection to both RabbitMQ and FIX."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                with patch.object(
                    adapter, "_start_message_consumption", new=AsyncMock()
                ) as mock_consumption:
                    result = await adapter.connect()

        assert result is True
        mock_rabbitmq_manager.connect.assert_called_once()
        mock_fix_adapter.connect.assert_called_once()
        mock_consumption.assert_called_once()

        # Verify callbacks are set
        assert (
            adapter.fix_adapter.execution_callback == adapter._handle_execution_report
        )
        assert (
            adapter.fix_adapter.market_data_callback
            == adapter._handle_market_data_update
        )

    @pytest.mark.asyncio
    async def test_connection_rabbitmq_failure(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test connection failure when RabbitMQ connection fails."""
        mock_rabbitmq_manager.connect.return_value = False

        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                result = await adapter._connect_to_broker()

        assert result is False
        mock_rabbitmq_manager.connect.assert_called_once()
        mock_fix_adapter.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_connection_fix_failure(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test connection failure when FIX connection fails."""
        mock_fix_adapter.connect.return_value = False

        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                result = await adapter._connect_to_broker()

        assert result is False
        mock_rabbitmq_manager.connect.assert_called_once()
        mock_fix_adapter.connect.assert_called_once()
        mock_rabbitmq_manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_disconnect(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test successful disconnection."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                await adapter._disconnect_from_broker()

        mock_fix_adapter.disconnect.assert_called_once()


class TestFixRabbitMQAdapterOrderOperations:
    """Test FIX RabbitMQ adapter order operations."""

    @pytest.mark.asyncio
    async def test_successful_order_submission(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter, sample_order
    ):
        """Test successful order submission to FIX broker."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                result = await adapter._submit_order_to_broker(sample_order)

        assert result == "FIX_ORDER_123"
        mock_fix_adapter.submit_order.assert_called_once_with(sample_order)

        # Verify order tracking
        assert sample_order.cl_ord_id in adapter.order_tracking
        order_info = adapter.order_tracking[sample_order.cl_ord_id]
        assert order_info["execution_id"] == "FIX_ORDER_123"
        assert order_info["order"] == sample_order
        assert order_info["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_order_submission_exception(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter, sample_order
    ):
        """Test order submission with FIX adapter exception."""
        mock_fix_adapter.submit_order.side_effect = Exception("FIX submission failed")

        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                with pytest.raises(Exception, match="FIX submission failed"):
                    await adapter._submit_order_to_broker(sample_order)

    @pytest.mark.asyncio
    async def test_successful_order_cancellation(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test successful order cancellation."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                # Set up existing order
                cl_ord_id = "CANCEL_TEST_001"
                sample_order = NewOrderSingle(
                    cl_ord_id=cl_ord_id,
                    symbol="EURUSD",
                    side=Side.BUY,
                    order_qty=100000,
                    ord_type=OrdType.MARKET,
                )

                adapter.order_tracking[cl_ord_id] = {
                    "execution_id": "FIX_CANCEL_123",
                    "order": sample_order,
                    "status": "submitted",
                }

                result = await adapter._cancel_order_with_broker(cl_ord_id)

        assert result is True
        mock_fix_adapter.cancel_order.assert_called_once()

        # Verify cancel request was properly constructed
        cancel_call = mock_fix_adapter.cancel_order.call_args[0][0]
        assert cancel_call.orig_cl_ord_id == cl_ord_id
        assert cancel_call.symbol == "EURUSD"
        assert cancel_call.side == Side.BUY

        # Verify order tracking updated
        order_info = adapter.order_tracking[cl_ord_id]
        assert order_info["status"] == "cancel_requested"
        assert "cancel_time" in order_info

    @pytest.mark.asyncio
    async def test_order_cancellation_not_found(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test order cancellation for non-existent order."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                result = await adapter._cancel_order_with_broker("NON_EXISTENT")

        assert result is False
        mock_fix_adapter.cancel_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_order_cancellation_exception(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test order cancellation with exception."""
        mock_fix_adapter.cancel_order.side_effect = Exception("Cancel failed")

        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                # Set up existing order
                cl_ord_id = "EXCEPTION_TEST"
                sample_order = NewOrderSingle(
                    cl_ord_id=cl_ord_id,
                    symbol="EURUSD",
                    side=Side.BUY,
                    order_qty=100000,
                    ord_type=OrdType.MARKET,
                )

                adapter.order_tracking[cl_ord_id] = {
                    "execution_id": "FIX_EXC_123",
                    "order": sample_order,
                    "status": "submitted",
                }

                result = await adapter._cancel_order_with_broker(cl_ord_id)

        assert result is False


class TestFixRabbitMQAdapterStatusOperations:
    """Test FIX RabbitMQ adapter status and data operations."""

    @pytest.mark.asyncio
    async def test_get_order_status(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test getting order status from tracking."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                # Set up order tracking
                cl_ord_id = "STATUS_TEST_001"
                submit_time = datetime.now(timezone.utc)
                adapter.order_tracking[cl_ord_id] = {
                    "execution_id": "FIX_STATUS_123",
                    "status": "working",
                    "submit_time": submit_time,
                    "last_update": submit_time,
                }

                result = await adapter._get_order_status_from_broker(cl_ord_id)

        assert result is not None
        assert result["cl_ord_id"] == cl_ord_id
        assert result["execution_id"] == "FIX_STATUS_123"
        assert result["status"] == "working"
        assert result["submit_time"] == submit_time.isoformat()

    @pytest.mark.asyncio
    async def test_get_order_status_not_found(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test getting status for non-existent order."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                result = await adapter._get_order_status_from_broker("NON_EXISTENT")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_open_orders(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test getting open orders from tracking."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                # Set up mixed order tracking
                adapter.order_tracking = {
                    "OPEN_1": {"status": "working"},
                    "FILLED_1": {"status": "filled"},
                    "OPEN_2": {"status": "submitted"},
                    "CANCELLED_1": {"status": "cancelled"},
                }

                with patch.object(
                    adapter,
                    "_get_order_status_from_broker",
                    side_effect=lambda cl_ord_id: (
                        {"cl_ord_id": cl_ord_id}
                        if cl_ord_id.startswith("OPEN")
                        else None
                    ),
                ):
                    result = await adapter._get_open_orders_from_broker()

        assert len(result) == 2
        open_order_ids = [order["cl_ord_id"] for order in result]
        assert "OPEN_1" in open_order_ids
        assert "OPEN_2" in open_order_ids

    @pytest.mark.asyncio
    async def test_get_positions(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test getting positions (should return empty for FIX)."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                result = await adapter._get_positions_from_broker()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_account_info(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test getting account information."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                # Set up some order tracking
                adapter.order_tracking = {"ORDER_1": {}, "ORDER_2": {}}

                with patch.object(
                    adapter,
                    "_get_open_orders_from_broker",
                    return_value=[{"cl_ord_id": "ORDER_1"}],
                ):
                    result = await adapter._get_account_info_from_broker()

        assert result["adapter_type"] == "fix"
        assert result["session_id"] == "TEST_SESSION"
        assert result["connected"] is True
        assert result["total_orders"] == 2
        assert result["open_orders"] == 1


class TestFixRabbitMQAdapterMessageHandling:
    """Test FIX RabbitMQ adapter message handling."""

    @pytest.mark.asyncio
    async def test_start_message_consumption(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test starting message consumption from RabbitMQ."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                await adapter._start_message_consumption()

        # Verify all message handlers were registered
        expected_handlers = [
            "new_order",
            "cancel_order",
            "modify_order",
            "market_data_request",
            "order_status_request",
        ]

        assert mock_rabbitmq_manager.register_handler.call_count == len(
            expected_handlers
        )

    @pytest.mark.asyncio
    async def test_handle_new_order_message(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test handling new order message from RabbitMQ."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                message = {
                    "order": {
                        "cl_ord_id": "MSG_ORDER_001",
                        "symbol": "GBPUSD",
                        "side": "BUY",
                        "quantity": 150000,
                        "order_type": "LIMIT",
                        "price": 1.2500,
                        "time_in_force": "DAY",
                    }
                }

                with patch.object(
                    adapter, "submit_order", new=AsyncMock(return_value="EXEC_123")
                ) as mock_submit:
                    await adapter._handle_new_order_message(message, "delivery_tag_123")

        mock_submit.assert_called_once()
        submitted_order = mock_submit.call_args[0][0]
        assert submitted_order.cl_ord_id == "MSG_ORDER_001"
        assert submitted_order.symbol == "GBPUSD"
        assert submitted_order.side == Side.BUY
        assert submitted_order.order_qty == 150000
        assert submitted_order.ord_type == OrdType.LIMIT
        assert submitted_order.price == 1.2500

        mock_rabbitmq_manager.ack_message.assert_called_once_with("delivery_tag_123")

    @pytest.mark.asyncio
    async def test_handle_new_order_message_with_defaults(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test handling new order message with default values."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                message = {
                    "order": {
                        "symbol": "EURUSD",
                        "side": "SELL",
                        "quantity": 100000,
                        # Missing cl_ord_id and order_type - should use defaults
                    }
                }

                with patch.object(
                    adapter, "submit_order", new=AsyncMock(return_value="EXEC_456")
                ) as mock_submit:
                    await adapter._handle_new_order_message(message, "delivery_tag_456")

        submitted_order = mock_submit.call_args[0][0]
        assert submitted_order.cl_ord_id.startswith("FIX_")
        assert submitted_order.ord_type == OrdType.MARKET

    @pytest.mark.asyncio
    async def test_handle_new_order_message_exception(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test handling new order message with exception."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                message = {
                    "order": {
                        "symbol": "INVALID",
                        "side": "INVALID_SIDE",
                        "quantity": "NOT_A_NUMBER",
                    }
                }

                with patch.object(
                    adapter, "submit_order", side_effect=Exception("Invalid order")
                ):
                    await adapter._handle_new_order_message(
                        message, "delivery_tag_error"
                    )

        mock_rabbitmq_manager.reject_message.assert_called_once_with(
            "delivery_tag_error", requeue=False
        )

    @pytest.mark.asyncio
    async def test_handle_cancel_order_message(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test handling cancel order message from RabbitMQ."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                message = {"cl_ord_id": "CANCEL_MSG_001"}

                with patch.object(
                    adapter, "cancel_order", new=AsyncMock(return_value=True)
                ) as mock_cancel:
                    await adapter._handle_cancel_order_message(
                        message, "delivery_tag_cancel"
                    )

        mock_cancel.assert_called_once_with("CANCEL_MSG_001")
        mock_rabbitmq_manager.ack_message.assert_called_once_with("delivery_tag_cancel")

    @pytest.mark.asyncio
    async def test_handle_cancel_order_message_missing_id(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test handling cancel order message with missing cl_ord_id."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                message = {}  # Missing cl_ord_id

                await adapter._handle_cancel_order_message(
                    message, "delivery_tag_missing"
                )

        mock_rabbitmq_manager.reject_message.assert_called_once_with(
            "delivery_tag_missing", requeue=False
        )

    @pytest.mark.asyncio
    async def test_handle_modify_order_message(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test handling modify order message from RabbitMQ."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                # Set up existing order
                orig_order = NewOrderSingle(
                    cl_ord_id="ORIG_ORDER_001",
                    symbol="EURUSD",
                    side=Side.BUY,
                    order_qty=100000,
                    ord_type=OrdType.LIMIT,
                    price=1.0800,
                )

                adapter.order_tracking["ORIG_ORDER_001"] = {
                    "order": orig_order,
                    "status": "working",
                }

                message = {
                    "orig_cl_ord_id": "ORIG_ORDER_001",
                    "quantity": 200000,
                    "price": 1.0850,
                    "order_type": "LIMIT",
                }

                await adapter._handle_modify_order_message(
                    message, "delivery_tag_modify"
                )

        mock_fix_adapter.modify_order.assert_called_once()
        modify_request = mock_fix_adapter.modify_order.call_args[0][0]
        assert modify_request.orig_cl_ord_id == "ORIG_ORDER_001"
        assert modify_request.order_qty == 200000
        assert modify_request.price == 1.0850

        mock_rabbitmq_manager.ack_message.assert_called_once_with("delivery_tag_modify")

    @pytest.mark.asyncio
    async def test_handle_modify_order_message_order_not_found(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test handling modify order message for non-existent order."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                message = {"orig_cl_ord_id": "NON_EXISTENT_ORDER", "quantity": 200000}

                await adapter._handle_modify_order_message(
                    message, "delivery_tag_not_found"
                )

        mock_rabbitmq_manager.reject_message.assert_called_once_with(
            "delivery_tag_not_found", requeue=False
        )

    @pytest.mark.asyncio
    async def test_handle_market_data_request(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test handling market data request from RabbitMQ."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                message = {
                    "symbols": ["EURUSD", "GBPUSD"],
                    "md_req_id": "MD_REQ_123",
                    "subscription_type": "1",
                    "market_depth": 5,
                }

                await adapter._handle_market_data_request(message, "delivery_tag_md")

        mock_fix_adapter.request_market_data.assert_called_once()
        md_request = mock_fix_adapter.request_market_data.call_args[0][0]
        assert md_request.md_req_id == "MD_REQ_123"
        assert md_request.symbols == ["EURUSD", "GBPUSD"]
        assert md_request.market_depth == 5

        # Verify subscription tracking
        assert "MD_REQ_123" in adapter.market_data_subscriptions

        mock_rabbitmq_manager.ack_message.assert_called_once_with("delivery_tag_md")

    @pytest.mark.asyncio
    async def test_handle_order_status_request(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test handling order status request from RabbitMQ."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                message = {"cl_ord_id": "STATUS_REQ_001"}

                with patch.object(
                    adapter,
                    "get_order_status",
                    new=AsyncMock(return_value={"status": "working"}),
                ) as mock_status:
                    with patch.object(
                        adapter, "_publish_order_event", new=AsyncMock()
                    ) as mock_publish:
                        await adapter._handle_order_status_request(
                            message, "delivery_tag_status"
                        )

        mock_status.assert_called_once_with("STATUS_REQ_001")
        mock_publish.assert_called_once_with(
            "status_response",
            {"cl_ord_id": "STATUS_REQ_001", "status": {"status": "working"}},
        )
        mock_rabbitmq_manager.ack_message.assert_called_once_with("delivery_tag_status")


class TestFixRabbitMQAdapterCallbacks:
    """Test FIX RabbitMQ adapter callback handling."""

    @pytest.mark.asyncio
    async def test_handle_execution_report(
        self,
        fix_rabbitmq_config,
        mock_rabbitmq_manager,
        mock_fix_adapter,
        sample_execution_report,
    ):
        """Test handling execution report from FIX adapter."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                # Set up order tracking
                adapter.order_tracking[sample_execution_report.cl_ord_id] = {
                    "status": "submitted",
                    "executions": [],
                }

                with patch.object(
                    adapter, "_publish_execution_report", new=AsyncMock()
                ) as mock_publish:
                    await adapter._handle_execution_report(sample_execution_report)

        # Verify order tracking updated
        order_info = adapter.order_tracking[sample_execution_report.cl_ord_id]
        assert order_info["status"] == sample_execution_report.ord_status.value
        assert len(order_info["executions"]) == 1

        execution = order_info["executions"][0]
        assert execution["exec_id"] == sample_execution_report.exec_id
        assert execution["exec_type"] == sample_execution_report.exec_type.value
        assert execution["ord_status"] == sample_execution_report.ord_status.value

        # Verify execution report published
        mock_publish.assert_called_once_with(sample_execution_report)

    @pytest.mark.asyncio
    async def test_handle_execution_report_new_order(
        self,
        fix_rabbitmq_config,
        mock_rabbitmq_manager,
        mock_fix_adapter,
        sample_execution_report,
    ):
        """Test handling execution report for order not in tracking."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                with patch.object(
                    adapter, "_publish_execution_report", new=AsyncMock()
                ) as mock_publish:
                    await adapter._handle_execution_report(sample_execution_report)

        # Should still publish even if not tracked
        mock_publish.assert_called_once_with(sample_execution_report)

    @pytest.mark.asyncio
    async def test_handle_market_data_update(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test handling market data update from FIX adapter."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                md_update = {
                    "symbol": "EURUSD",
                    "bid": 1.0850,
                    "ask": 1.0852,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                await adapter._handle_market_data_update(md_update)

        mock_rabbitmq_manager.publish_market_data.assert_called_once_with(md_update)


class TestFixRabbitMQAdapterPublicMethods:
    """Test FIX RabbitMQ adapter public methods."""

    @pytest.mark.asyncio
    async def test_modify_order(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test modify order public method."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                modify_request = OrderCancelReplaceRequest(
                    orig_cl_ord_id="ORIG_123",
                    cl_ord_id="MOD_456",
                    symbol="EURUSD",
                    side=Side.BUY,
                    order_qty=200000,
                    ord_type=OrdType.LIMIT,
                    price=1.0850,
                )

                with patch.object(
                    adapter, "_publish_order_event", new=AsyncMock()
                ) as mock_publish:
                    result = await adapter.modify_order(modify_request)

        assert result is True
        mock_fix_adapter.modify_order.assert_called_once_with(modify_request)
        mock_publish.assert_called_once_with(
            "modify_requested",
            {"orig_cl_ord_id": "ORIG_123", "new_cl_ord_id": "MOD_456", "success": True},
        )

    @pytest.mark.asyncio
    async def test_modify_order_failure(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test modify order with failure."""
        mock_fix_adapter.modify_order.side_effect = Exception("Modify failed")

        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                modify_request = OrderCancelReplaceRequest(
                    orig_cl_ord_id="FAIL_123",
                    cl_ord_id="FAIL_456",
                    symbol="EURUSD",
                    side=Side.BUY,
                    order_qty=100000,
                    ord_type=OrdType.MARKET,
                )

                with patch.object(
                    adapter, "_publish_order_event", new=AsyncMock()
                ) as mock_publish:
                    result = await adapter.modify_order(modify_request)

        assert result is False
        mock_publish.assert_called_once_with(
            "modify_error", {"orig_cl_ord_id": "FAIL_123", "error": "Modify failed"}
        )

    @pytest.mark.asyncio
    async def test_request_market_data(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test request market data public method."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                md_request = MarketDataRequest(
                    md_req_id="PUBLIC_MD_001",
                    symbols=["EURUSD", "GBPUSD"],
                    subscription_request_type="1",
                    market_depth=1,
                )

                with patch.object(
                    adapter, "_publish_order_event", new=AsyncMock()
                ) as mock_publish:
                    result = await adapter.request_market_data(md_request)

        assert result is True
        mock_fix_adapter.request_market_data.assert_called_once_with(md_request)

        # Verify subscription tracking
        assert "PUBLIC_MD_001" in adapter.market_data_subscriptions

        mock_publish.assert_called_once_with(
            "market_data_requested",
            {
                "md_req_id": "PUBLIC_MD_001",
                "symbols": ["EURUSD", "GBPUSD"],
                "success": True,
            },
        )

    @pytest.mark.asyncio
    async def test_request_market_data_failure(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test request market data with failure."""
        mock_fix_adapter.request_market_data.side_effect = Exception(
            "MD request failed"
        )

        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                md_request = MarketDataRequest(
                    md_req_id="FAIL_MD_001",
                    symbols=["INVALID"],
                    subscription_request_type="1",
                    market_depth=1,
                )

                result = await adapter.request_market_data(md_request)

        assert result is False
        assert "FAIL_MD_001" not in adapter.market_data_subscriptions


class TestFixRabbitMQAdapterMetrics:
    """Test FIX RabbitMQ adapter metrics and monitoring."""

    @pytest.mark.asyncio
    async def test_get_metrics(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test getting comprehensive adapter metrics."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                # Set up tracking data
                adapter.order_tracking = {
                    "ORDER_1": {"status": "working"},
                    "ORDER_2": {"status": "filled"},
                    "ORDER_3": {"status": "working"},
                    "ORDER_4": {"status": "cancelled"},
                }

                adapter.market_data_subscriptions = {"MD_1": {}, "MD_2": {}}

                with patch.object(
                    adapter,
                    "_get_health_status",
                    new=AsyncMock(return_value={"health": "good"}),
                ):
                    result = await adapter.get_metrics()

        assert "health" in result
        assert "fix_metrics" in result
        assert "order_metrics" in result

        # Verify FIX metrics
        fix_metrics = result["fix_metrics"]
        assert "session_stats" in fix_metrics
        assert "sequence_numbers" in fix_metrics

        # Verify order metrics
        order_metrics = result["order_metrics"]
        assert order_metrics["total_orders_tracked"] == 4
        assert order_metrics["market_data_subscriptions"] == 2

        # Verify status breakdown
        status_breakdown = order_metrics["order_status_breakdown"]
        assert status_breakdown["working"] == 2
        assert status_breakdown["filled"] == 1
        assert status_breakdown["cancelled"] == 1


class TestFixRabbitMQAdapterEdgeCases:
    """Test FIX RabbitMQ adapter edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_message_handling_exceptions(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test message handling with various exceptions."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                # Test exception during execution report handling
                sample_execution_report = ExecutionReport(
                    order_id="ERROR_ORDER",
                    cl_ord_id="ERROR_CL_ORD",
                    exec_id="ERROR_EXEC",
                    exec_type=ExecType.NEW,
                    ord_status=OrdStatus.NEW,
                    symbol="EURUSD",
                    side=Side.BUY,
                    order_qty=100000,
                    transact_time=datetime.now(timezone.utc),
                )

                with patch.object(
                    adapter,
                    "_publish_execution_report",
                    side_effect=Exception("Publish failed"),
                ):
                    # Should not raise exception
                    await adapter._handle_execution_report(sample_execution_report)

    @pytest.mark.asyncio
    async def test_market_data_callback_exception(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test market data callback with exception."""
        mock_rabbitmq_manager.publish_market_data.side_effect = Exception(
            "Publish failed"
        )

        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                md_update = {"symbol": "EURUSD", "bid": 1.0850}

                # Should not raise exception
                await adapter._handle_market_data_update(md_update)

    @pytest.mark.asyncio
    async def test_order_status_with_cancel_time(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test order status retrieval with cancel time."""
        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                # Set up order with cancel time
                cancel_time = datetime.now(timezone.utc)
                adapter.order_tracking["CANCEL_TIME_TEST"] = {
                    "execution_id": "EXEC_123",
                    "status": "cancelled",
                    "submit_time": datetime.now(timezone.utc),
                    "cancel_time": cancel_time,
                    "last_update": datetime.now(timezone.utc),
                }

                result = await adapter._get_order_status_from_broker("CANCEL_TIME_TEST")

        assert result["cancel_time"] == cancel_time.isoformat()

    @pytest.mark.asyncio
    async def test_start_message_consumption_exception(
        self, fix_rabbitmq_config, mock_rabbitmq_manager, mock_fix_adapter
    ):
        """Test start message consumption with exception."""
        mock_rabbitmq_manager.register_handler.side_effect = Exception(
            "Registration failed"
        )

        with patch(
            "fxml4.brokers.adapters.fix_rabbitmq_adapter.create_rabbitmq_manager",
            return_value=mock_rabbitmq_manager,
        ):
            with patch(
                "fxml4.brokers.adapters.fix_rabbitmq_adapter.FixBrokerAdapter",
                return_value=mock_fix_adapter,
            ):
                adapter = FixRabbitMQAdapter(fix_rabbitmq_config)

                with pytest.raises(Exception, match="Registration failed"):
                    await adapter._start_message_consumption()
