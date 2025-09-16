"""Simplified test suite for RabbitMQ Message Routing Infrastructure.

This test suite validates the core functionality of our RabbitMQ message routing
implementation with focus on the actual classes we've built.
"""

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.messaging import (
    ExecutionMessage,
    MessagePriority,
    OrderMessage,
    RabbitMQMessageRouter,
    RiskCheckMessage,
)
from fxml4.messaging.messages import OrderSide, OrderStatus, OrderType, RiskCheckStatus


class TestMessageClasses:
    """Test message classes and serialization."""

    def test_order_message_creation(self):
        """Test OrderMessage creation and validation."""
        order_msg = OrderMessage(
            order_id="ORD_001",
            client_order_id="CLI_001",
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
            broker="IB",
            account_id="ACC_123",
        )

        assert order_msg.order_id == "ORD_001"
        assert order_msg.symbol == "EURUSD"
        assert order_msg.side == OrderSide.BUY
        assert order_msg.quantity == Decimal("100000")
        assert order_msg.status == OrderStatus.NEW
        assert order_msg.filled_quantity == Decimal("0")

    def test_order_message_json_serialization(self):
        """Test OrderMessage JSON serialization/deserialization."""
        order_msg = OrderMessage(
            order_id="ORD_002",
            client_order_id="CLI_002",
            symbol="GBPUSD",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("50000"),
            price=Decimal("1.2500"),
            broker="FXCM",
            account_id="ACC_456",
        )

        # Serialize to JSON
        json_str = order_msg.to_json()
        assert isinstance(json_str, str)

        # Deserialize from JSON
        restored_msg = OrderMessage.from_json(json_str)
        assert restored_msg.order_id == order_msg.order_id
        assert restored_msg.symbol == order_msg.symbol
        assert restored_msg.quantity == order_msg.quantity
        assert restored_msg.price == order_msg.price

    def test_risk_check_message_creation(self):
        """Test RiskCheckMessage creation and validation."""
        risk_msg = RiskCheckMessage(
            order_id="ORD_003",
            symbol="USDJPY",
            side=OrderSide.BUY,
            quantity=Decimal("100000"),
            account_id="ACC_789",
            position_size_usd=Decimal("130000"),
            account_balance=Decimal("50000"),
            current_exposure=Decimal("25000"),
            max_position_size=Decimal("200000"),
            max_daily_loss=Decimal("2000"),
            current_daily_pnl=Decimal("-500"),
        )

        assert risk_msg.order_id == "ORD_003"
        assert risk_msg.symbol == "USDJPY"
        assert risk_msg.status == RiskCheckStatus.PENDING
        assert risk_msg.account_balance == Decimal("50000")

    def test_execution_message_creation(self):
        """Test ExecutionMessage creation and validation."""
        exec_msg = ExecutionMessage(
            execution_id="EXEC_001",
            order_id="ORD_004",
            client_order_id="CLI_004",
            symbol="USDCHF",
            side=OrderSide.SELL,
            quantity=Decimal("75000"),
            price=Decimal("0.9200"),
            broker="IB",
            account_id="ACC_101",
        )

        assert exec_msg.execution_id == "EXEC_001"
        assert exec_msg.order_id == "ORD_004"
        assert exec_msg.symbol == "USDCHF"
        assert exec_msg.side == OrderSide.SELL

        # Test notional calculation
        notional = exec_msg.calculate_notional_value()
        expected = Decimal("75000") * Decimal("0.9200")
        assert notional == expected

    def test_message_routing_keys(self):
        """Test message routing key generation."""
        order_msg = OrderMessage(
            order_id="ORD_005",
            client_order_id="CLI_005",
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
            broker="IB",
            account_id="ACC_123",
        )

        routing_key = order_msg.get_routing_key()
        assert routing_key == "order.IB.EURUSD"

        risk_msg = RiskCheckMessage(
            order_id="ORD_005",
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=Decimal("100000"),
            account_id="ACC_123",
            position_size_usd=Decimal("100000"),
            account_balance=Decimal("50000"),
            current_exposure=Decimal("0"),
            max_position_size=Decimal("200000"),
            max_daily_loss=Decimal("2000"),
            current_daily_pnl=Decimal("0"),
        )

        risk_routing_key = risk_msg.get_routing_key()
        assert risk_routing_key == "risk.ACC_123.EURUSD"


class TestRabbitMQMessageRouter:
    """Test RabbitMQMessageRouter functionality with mocks."""

    def test_router_initialization(self):
        """Test router initialization with default config."""
        router = RabbitMQMessageRouter()

        assert router.rabbitmq_url == "amqp://guest:guest@localhost:5672/"
        assert router.connection_pool_size == 10
        assert router.prefetch_count == 100
        assert router.max_retries == 3
        assert router.is_connected is False
        assert router.connection is None
        assert router.channel is None

    def test_router_custom_config(self):
        """Test router initialization with custom config."""
        router = RabbitMQMessageRouter(
            rabbitmq_url="amqp://user:pass@rabbitmq.example.com:5672/",
            connection_pool_size=5,
            prefetch_count=50,
            message_ttl_seconds=600,
            max_retries=5,
        )

        assert router.rabbitmq_url == "amqp://user:pass@rabbitmq.example.com:5672/"
        assert router.connection_pool_size == 5
        assert router.prefetch_count == 50
        assert router.message_ttl_seconds == 600
        assert router.max_retries == 5

    def test_connection_status(self):
        """Test connection status reporting."""
        router = RabbitMQMessageRouter()

        status = router.get_connection_status()
        assert isinstance(status, dict)
        assert "is_connected" in status
        assert "message_count" in status
        assert "error_count" in status
        assert status["is_connected"] is False
        assert status["message_count"] == 0
        assert status["error_count"] == 0

    @pytest.mark.asyncio
    async def test_connect_disconnect_flow(self):
        """Test connection and disconnection flow with mocks."""
        router = RabbitMQMessageRouter()

        # Mock aio_pika connection
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_connection.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_connection

            # Test connection
            await router.connect()

            assert router.is_connected is True
            assert router.connection == mock_connection
            assert router.channel == mock_channel
            mock_channel.set_qos.assert_called_once_with(prefetch_count=100)

            # Test disconnection
            await router.disconnect()

            mock_connection.close.assert_called_once()
            assert router.is_connected is False

    @pytest.mark.asyncio
    async def test_message_routing_with_mocks(self):
        """Test message routing functionality with mocked RabbitMQ."""
        router = RabbitMQMessageRouter()

        # Setup mocks
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()
        mock_connection.channel.return_value = mock_channel
        mock_channel.default_exchange = mock_exchange
        mock_channel.declare_exchange = AsyncMock()
        mock_channel.declare_queue = AsyncMock()

        router.connection = mock_connection
        router.channel = mock_channel
        router.is_connected = True

        # Create test order message
        order_msg = OrderMessage(
            order_id="ORD_ROUTE_001",
            client_order_id="CLI_ROUTE_001",
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
            broker="IB",
            account_id="ACC_ROUTE",
            priority=MessagePriority.HIGH,
        )

        # Test routing
        await router.route_order_message(order_msg)

        # Verify publish was called
        mock_exchange.publish.assert_called_once()

        # Check call arguments
        call_args = mock_exchange.publish.call_args
        message = call_args[0][0]
        routing_key = call_args[1]["routing_key"]

        assert routing_key == "order_queue"
        assert message.priority == MessagePriority.HIGH.value
        assert router.message_count == 1

    @pytest.mark.asyncio
    async def test_performance_metrics(self):
        """Test performance metrics tracking."""
        router = RabbitMQMessageRouter()

        # Initial metrics
        router.is_connected = True  # Set connected for health check
        metrics = await router.get_performance_metrics()
        assert metrics["total_messages"] == 0
        assert metrics["total_errors"] == 0
        assert metrics["error_rate"] == 0
        assert metrics["messages_per_second"] == 0
        assert metrics["is_healthy"] is True  # Connected with no errors

        # Simulate some activity
        router.message_count = 100
        router.error_count = 5
        router.last_message_time = datetime.utcnow()

        metrics = await router.get_performance_metrics()
        assert metrics["total_messages"] == 100
        assert metrics["total_errors"] == 5
        assert metrics["error_rate"] == 0.05
        assert metrics["is_healthy"] is True  # Error rate < 10%

    def test_queue_info(self):
        """Test queue information retrieval."""
        router = RabbitMQMessageRouter()

        # Queue not found
        info = router.get_queue_info("nonexistent_queue")
        assert info is None

        # Mock a queue
        mock_queue = Mock()
        router.queues["test_queue"] = mock_queue
        router.consumers["test_queue"] = Mock()

        info = router.get_queue_info("test_queue")
        assert info is not None
        assert info["name"] == "test_queue"
        assert info["durable"] is True
        assert info["has_consumer"] is True


@pytest.mark.asyncio
async def test_connection_context_manager():
    """Test connection context manager."""
    router = RabbitMQMessageRouter()

    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_connection.channel.return_value = mock_channel

    with patch("aio_pika.connect_robust", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_connection

        async with router.connection_context() as ctx_router:
            assert ctx_router.is_connected is True
            assert ctx_router == router

        # Should disconnect after context
        mock_connection.close.assert_called_once()
        assert router.is_connected is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
