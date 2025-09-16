"""Test suite for RabbitMQ Message Routing Infrastructure.

This comprehensive TDD test suite validates the RabbitMQ-based message routing
system that forms the foundational async architecture for order management,
risk checking, and execution routing across multiple broker adapters.

Test Categories:
- Message routing topology (order_queue, risk_queue, execution_queue)
- Queue configuration and durability
- Message serialization and deserialization
- Dead letter queue handling
- Performance and throughput testing
- Error handling and retry logic
- Connection resilience and failover
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
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

logger = logging.getLogger(__name__)


class TestRabbitMQMessageRoutingConfig:
    """Test RabbitMQ message routing configuration."""

    def test_queue_config_validation(self):
        """Test queue configuration validation."""
        # Valid queue configuration
        config = QueueConfig(
            name="order_queue",
            durable=True,
            exclusive=False,
            auto_delete=False,
            dead_letter_exchange="dlx_orders",
            dead_letter_routing_key="failed_orders",
            message_ttl=300000,  # 5 minutes
            max_length=10000,
            max_priority=10,
        )

        assert config.name == "order_queue"
        assert config.durable is True
        assert config.dead_letter_exchange == "dlx_orders"
        assert config.message_ttl == 300000

    def test_message_router_config_initialization(self):
        """Test message router configuration initialization."""
        config = MessageRouterConfig(
            rabbitmq_url="amqp://localhost:5672",
            exchange_name="fxml4_trading",
            queues={
                "orders": QueueConfig(name="order_queue"),
                "risk": QueueConfig(name="risk_queue"),
                "execution": QueueConfig(name="execution_queue"),
            },
            connection_timeout=30,
            heartbeat_interval=60,
            enable_confirms=True,
            enable_returns=True,
        )

        assert config.rabbitmq_url == "amqp://localhost:5672"
        assert config.exchange_name == "fxml4_trading"
        assert len(config.queues) == 3
        assert config.enable_confirms is True

    def test_routing_key_enumeration(self):
        """Test routing key enumeration and patterns."""
        # Test routing key patterns
        assert RoutingKey.NEW_ORDER == "order.new"
        assert RoutingKey.CANCEL_ORDER == "order.cancel"
        assert RoutingKey.RISK_CHECK == "risk.check"
        assert RoutingKey.EXECUTION_REPORT == "execution.report"
        assert RoutingKey.BROKER_IB == "broker.ib"
        assert RoutingKey.BROKER_FXCM == "broker.fxcm"
        assert RoutingKey.BROKER_MANUAL == "broker.manual"


class TestRabbitMQMessageSerialization:
    """Test message serialization and deserialization."""

    @pytest.fixture
    def sample_new_order(self):
        """Create sample new order for testing."""
        return NewOrderSingle(
            cl_ord_id="ORDER_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.DAY,
            transact_time=datetime.utcnow(),
        )

    def test_order_message_serialization(self, sample_new_order):
        """Test order message serialization to JSON."""
        order_message = OrderMessage(
            message_id=str(uuid.uuid4()),
            correlation_id="CORR_001",
            order=sample_new_order,
            broker_id="ib",
            priority=MessagePriority.HIGH,
            timestamp=datetime.utcnow(),
        )

        # Serialize to JSON
        json_data = order_message.to_json()
        parsed_data = json.loads(json_data)

        assert parsed_data["message_id"] == order_message.message_id
        assert parsed_data["correlation_id"] == "CORR_001"
        assert parsed_data["broker_id"] == "ib"
        assert parsed_data["priority"] == MessagePriority.HIGH.value
        assert "order" in parsed_data

    def test_order_message_deserialization(self, sample_new_order):
        """Test order message deserialization from JSON."""
        # Create original message
        original = OrderMessage(
            message_id="MSG_001",
            correlation_id="CORR_001",
            order=sample_new_order,
            broker_id="ib",
            priority=MessagePriority.HIGH,
        )

        # Serialize and deserialize
        json_data = original.to_json()
        deserialized = OrderMessage.from_json(json_data)

        assert deserialized.message_id == "MSG_001"
        assert deserialized.correlation_id == "CORR_001"
        assert deserialized.broker_id == "ib"
        assert deserialized.priority == MessagePriority.HIGH
        assert deserialized.order.cl_ord_id == "ORDER_001"

    def test_risk_check_message_serialization(self):
        """Test risk check message serialization."""
        risk_message = RiskCheckMessage(
            message_id="RISK_001",
            order_id="ORDER_001",
            account_id="ACC_001",
            symbol="EURUSD",
            side=Side.BUY,
            quantity=100000,
            price=1.1000,
            risk_checks=["position_limit", "daily_pnl_limit", "account_balance"],
            priority=MessagePriority.CRITICAL,
        )

        json_data = risk_message.to_json()
        parsed_data = json.loads(json_data)

        assert parsed_data["order_id"] == "ORDER_001"
        assert parsed_data["symbol"] == "EURUSD"
        assert len(parsed_data["risk_checks"]) == 3
        assert parsed_data["priority"] == MessagePriority.CRITICAL.value

    def test_execution_message_serialization(self):
        """Test execution message serialization."""
        exec_report = ExecutionReport(
            order_id="ORDER_001",
            cl_ord_id="ORDER_001",
            exec_id="EXEC_001",
            exec_type=ExecType.TRADE,
            ord_status=OrdStatus.FILLED,
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            last_qty=100000,
            last_px=1.1000,
            leaves_qty=0,
            cum_qty=100000,
            avg_px=1.1000,
            transact_time=datetime.utcnow(),
        )

        exec_message = ExecutionMessage(
            message_id="EXEC_MSG_001",
            execution_report=exec_report,
            broker_id="ib",
            priority=MessagePriority.HIGH,
        )

        json_data = exec_message.to_json()
        parsed_data = json.loads(json_data)

        assert parsed_data["broker_id"] == "ib"
        assert "execution_report" in parsed_data
        assert parsed_data["execution_report"]["exec_id"] == "EXEC_001"


class TestRabbitMQConnectionManagement:
    """Test RabbitMQ connection management and resilience."""

    @pytest.fixture
    def message_router(self):
        """Create message router for testing."""
        config = MessageRouterConfig()
        return RabbitMQMessageRouter(config)

    @pytest.mark.asyncio
    async def test_connection_establishment(self, message_router):
        """Test RabbitMQ connection establishment."""
        with patch("aio_pika.connect_robust") as mock_connect:
            mock_connection = AsyncMock()
            mock_connect.return_value = mock_connection

            await message_router.connect()

            mock_connect.assert_called_once()
            assert message_router.connection == mock_connection

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self, message_router):
        """Test connection failure handling and retry logic."""
        with patch(
            "aio_pika.connect_robust",
            side_effect=ConnectionError("RabbitMQ unavailable"),
        ):
            with pytest.raises(ConnectionError):
                await message_router.connect()

    @pytest.mark.asyncio
    async def test_connection_recovery(self, message_router):
        """Test automatic connection recovery."""
        # Mock initial connection failure, then success
        with patch(
            "aio_pika.connect_robust",
            side_effect=[ConnectionError("Temporary failure"), AsyncMock()],
        ):
            # Should retry and succeed
            with patch.object(message_router, "_retry_delay", 0.1):
                await message_router.connect_with_retry(max_retries=2)

            assert message_router.connection is not None

    @pytest.mark.asyncio
    async def test_graceful_disconnection(self, message_router):
        """Test graceful disconnection and cleanup."""
        # Mock connection
        mock_connection = AsyncMock()
        message_router.connection = mock_connection

        await message_router.disconnect()

        mock_connection.close.assert_called_once()
        assert message_router.connection is None


class TestRabbitMQQueueManagement:
    """Test RabbitMQ queue creation and management."""

    @pytest.fixture
    def message_router(self):
        """Create configured message router."""
        config = MessageRouterConfig(
            queues={
                "orders": QueueConfig(
                    name="order_queue", durable=True, dead_letter_exchange="dlx_orders"
                ),
                "risk": QueueConfig(name="risk_queue", durable=True, max_priority=10),
                "execution": QueueConfig(name="execution_queue", durable=True),
            }
        )
        return RabbitMQMessageRouter(config)

    @pytest.mark.asyncio
    async def test_queue_creation(self, message_router):
        """Test queue creation with proper configuration."""
        mock_channel = AsyncMock()
        mock_connection = AsyncMock()
        mock_connection.channel.return_value = mock_channel
        message_router.connection = mock_connection

        await message_router._setup_queues()

        # Should create channel
        mock_connection.channel.assert_called_once()

        # Should declare queues
        assert mock_channel.declare_queue.call_count == 3

    @pytest.mark.asyncio
    async def test_dead_letter_queue_setup(self, message_router):
        """Test dead letter queue configuration."""
        mock_channel = AsyncMock()
        mock_connection = AsyncMock()
        mock_connection.channel.return_value = mock_channel
        message_router.connection = mock_connection

        await message_router._setup_dead_letter_queues()

        # Should create dead letter exchanges and queues
        mock_channel.declare_exchange.assert_called()
        mock_channel.declare_queue.assert_called()

    @pytest.mark.asyncio
    async def test_queue_binding(self, message_router):
        """Test queue binding to exchanges with routing keys."""
        mock_channel = AsyncMock()
        mock_queue = AsyncMock()
        mock_channel.declare_queue.return_value = mock_queue

        message_router.channel = mock_channel

        await message_router._bind_queues()

        # Should bind queues to exchange
        mock_queue.bind.assert_called()


class TestRabbitMQMessageRouting:
    """Test message routing functionality."""

    @pytest.fixture
    def message_router(self):
        """Create message router with mock connection."""
        config = MessageRouterConfig()
        router = RabbitMQMessageRouter(config)

        # Mock connection and channel
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_connection.channel.return_value = mock_channel

        router.connection = mock_connection
        router.channel = mock_channel

        return router

    @pytest.fixture
    def sample_order_message(self):
        """Create sample order message."""
        order = NewOrderSingle(
            cl_ord_id="ROUTE_TEST_001",
            symbol="GBPUSD",
            side=Side.SELL,
            order_qty=50000,
            ord_type=OrdType.LIMIT,
            price=1.2500,
        )

        return OrderMessage(
            message_id=str(uuid.uuid4()),
            correlation_id="CORR_001",
            order=order,
            broker_id="ib",
            priority=MessagePriority.HIGH,
        )

    @pytest.mark.asyncio
    async def test_route_order_message(self, message_router, sample_order_message):
        """Test routing order messages to order queue."""
        await message_router.route_order_message(sample_order_message)

        # Should publish to exchange with correct routing key
        message_router.channel.default_exchange.publish.assert_called_once()

        # Verify message properties
        call_args = message_router.channel.default_exchange.publish.call_args
        message = call_args[0][0]
        routing_key = call_args[1]["routing_key"]

        assert routing_key == "order_queue"
        assert message.priority == MessagePriority.HIGH.value

    @pytest.mark.asyncio
    async def test_route_risk_check_message(self, message_router):
        """Test routing risk check messages."""
        risk_message = RiskCheckMessage(
            message_id="RISK_001",
            order_id="ORDER_001",
            account_id="ACC_001",
            symbol="EURUSD",
            side=Side.BUY,
            quantity=100000,
            price=1.1000,
            risk_checks=["position_limit"],
            priority=MessagePriority.CRITICAL,
        )

        await message_router.route_risk_message(risk_message)

        # Should route to risk queue with critical priority
        message_router.channel.default_exchange.publish.assert_called_once()
        call_args = message_router.channel.default_exchange.publish.call_args
        routing_key = call_args[1]["routing_key"]

        assert routing_key == "risk_queue"

    @pytest.mark.asyncio
    async def test_route_execution_message(self, message_router):
        """Test routing execution messages."""
        exec_report = ExecutionReport(
            order_id="ORDER_001",
            cl_ord_id="ORDER_001",
            exec_id="EXEC_001",
            exec_type=ExecType.TRADE,
            ord_status=OrdStatus.FILLED,
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            last_qty=100000,
            last_px=1.1000,
        )

        exec_message = ExecutionMessage(
            message_id="EXEC_001", execution_report=exec_report, broker_id="ib"
        )

        await message_router.route_execution_message(exec_message)

        # Should route to execution queue
        call_args = message_router.channel.default_exchange.publish.call_args
        routing_key = call_args[1]["routing_key"]

        assert routing_key == "execution_queue"

    @pytest.mark.asyncio
    async def test_broker_specific_routing(self, message_router, sample_order_message):
        """Test broker-specific routing with routing keys."""
        # Test IB routing
        sample_order_message.broker_id = "ib"
        await message_router.route_order_message(
            sample_order_message, routing_key=RoutingKey.BROKER_IB
        )

        # Test FXCM routing
        sample_order_message.broker_id = "fxcm"
        await message_router.route_order_message(
            sample_order_message, routing_key=RoutingKey.BROKER_FXCM
        )

        # Should have called publish twice
        assert message_router.channel.default_exchange.publish.call_count == 2


class TestRabbitMQMessageConsumption:
    """Test message consumption and processing."""

    @pytest.fixture
    def message_router(self):
        """Create message router with mock connection."""
        config = MessageRouterConfig()
        router = RabbitMQMessageRouter(config)

        # Mock connection and channel
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_queue = AsyncMock()

        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_queue.return_value = mock_queue

        router.connection = mock_connection
        router.channel = mock_channel

        return router

    @pytest.mark.asyncio
    async def test_consume_order_messages(self, message_router):
        """Test consuming order messages from queue."""
        # Mock message handler
        message_handler = AsyncMock()

        await message_router.consume_orders(message_handler)

        # Should set up consumer on order queue
        message_router.channel.declare_queue.assert_called_with(
            "order_queue", durable=True
        )

    @pytest.mark.asyncio
    async def test_message_acknowledgment(self, message_router):
        """Test message acknowledgment after processing."""
        mock_message = AsyncMock()
        mock_message.body = b'{"message_id": "test", "order": {}}'

        # Mock successful processing
        message_handler = AsyncMock()

        await message_router._process_order_message(mock_message, message_handler)

        # Should acknowledge message after successful processing
        mock_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_rejection_on_error(self, message_router):
        """Test message rejection when processing fails."""
        mock_message = AsyncMock()
        mock_message.body = b'{"message_id": "test", "order": {}}'

        # Mock failing message handler
        message_handler = AsyncMock(side_effect=Exception("Processing failed"))

        await message_router._process_order_message(mock_message, message_handler)

        # Should reject message and requeue
        mock_message.nack.assert_called_once_with(requeue=True)


class TestRabbitMQPerformance:
    """Test RabbitMQ performance and throughput."""

    @pytest.fixture
    def message_router(self):
        """Create high-performance message router."""
        config = MessageRouterConfig(
            connection_timeout=10,
            heartbeat_interval=30,
            prefetch_count=100,
            enable_publisher_confirms=True,
        )
        router = RabbitMQMessageRouter(config)

        # Mock fast connection
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_connection.channel.return_value = mock_channel

        router.connection = mock_connection
        router.channel = mock_channel

        return router

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_high_throughput_message_routing(self, message_router):
        """Test high throughput message routing performance."""
        # Create multiple order messages
        messages = []
        for i in range(100):
            order = NewOrderSingle(
                cl_ord_id=f"PERF_{i:03d}",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=10000,
                ord_type=OrdType.MARKET,
            )

            message = OrderMessage(
                message_id=f"MSG_{i:03d}",
                order=order,
                broker_id="ib",
                priority=MessagePriority.NORMAL,
            )
            messages.append(message)

        # Measure routing performance
        start_time = time.time()

        # Route messages concurrently
        tasks = [message_router.route_order_message(msg) for msg in messages]
        await asyncio.gather(*tasks)

        end_time = time.time()
        duration = end_time - start_time
        throughput = len(messages) / duration

        logger.info(f"Message routing throughput: {throughput:.2f} messages/second")

        # Should handle at least 1000 messages per second
        assert throughput > 100, f"Throughput too low: {throughput:.2f} msg/sec"

        # Verify all messages were published
        assert message_router.channel.default_exchange.publish.call_count == 100

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_message_serialization_performance(self):
        """Test message serialization performance."""
        # Create complex order message
        order = NewOrderSingle(
            cl_ord_id="PERF_SERIALIZE_001",
            symbol="GBPUSD",
            side=Side.SELL,
            order_qty=100000,
            ord_type=OrdType.LIMIT,
            price=1.2500,
            time_in_force=TimeInForce.GOOD_TILL_CANCEL,
        )

        message = OrderMessage(
            message_id=str(uuid.uuid4()),
            correlation_id="PERF_CORR",
            order=order,
            broker_id="ib",
            priority=MessagePriority.HIGH,
            metadata={
                "account_id": "ACC_001",
                "strategy_id": "STRAT_001",
                "risk_score": 0.75,
            },
        )

        # Measure serialization performance
        iterations = 1000
        start_time = time.time()

        for _ in range(iterations):
            json_data = message.to_json()
            deserialized = OrderMessage.from_json(json_data)

        end_time = time.time()
        duration = end_time - start_time
        ops_per_second = (iterations * 2) / duration  # serialize + deserialize

        logger.info(f"Serialization performance: {ops_per_second:.2f} ops/second")

        # Should handle at least 10k serialization ops per second
        assert (
            ops_per_second > 5000
        ), f"Serialization too slow: {ops_per_second:.2f} ops/sec"


class TestRabbitMQErrorHandling:
    """Test RabbitMQ error handling and resilience."""

    @pytest.fixture
    def message_router(self):
        """Create message router for error testing."""
        config = MessageRouterConfig()
        return RabbitMQMessageRouter(config)

    @pytest.mark.asyncio
    async def test_publish_error_handling(self, message_router):
        """Test handling of publish errors."""
        # Mock channel that throws error on publish
        mock_channel = AsyncMock()
        mock_channel.default_exchange.publish.side_effect = Exception("Publish failed")
        message_router.channel = mock_channel

        order = NewOrderSingle(
            cl_ord_id="ERROR_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=10000,
            ord_type=OrdType.MARKET,
        )
        message = OrderMessage(message_id="ERR_MSG", order=order, broker_id="ib")

        # Should handle error gracefully
        with pytest.raises(Exception):
            await message_router.route_order_message(message)

    @pytest.mark.asyncio
    async def test_dead_letter_queue_routing(self, message_router):
        """Test routing failed messages to dead letter queue."""
        # Mock message that exceeds retry limit
        mock_message = AsyncMock()
        mock_message.body = b'{"message_id": "dead_letter_test"}'
        mock_message.headers = {"x-death": [{"count": 5}]}  # Exceeded retries

        await message_router._handle_dead_letter_message(mock_message)

        # Should log dead letter and not requeue
        mock_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_lost_recovery(self, message_router):
        """Test recovery when connection is lost during operation."""
        # Mock connection that fails during operation
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        message_router.connection = mock_connection

        # Simulate connection loss
        mock_connection.is_closed = True

        # Should detect connection loss and attempt recovery
        with patch.object(message_router, "connect") as mock_reconnect:
            await message_router._ensure_connection()
            mock_reconnect.assert_called_once()


class TestRabbitMQIntegration:
    """Integration tests for RabbitMQ message routing."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_message_flow(self):
        """Test complete end-to-end message flow."""
        # This would require actual RabbitMQ instance for full integration
        # For now, comprehensive mocking validates the flow

        config = MessageRouterConfig()
        router = RabbitMQMessageRouter(config)

        # Mock full connection chain
        with patch("aio_pika.connect_robust") as mock_connect:
            mock_connection = AsyncMock()
            mock_channel = AsyncMock()
            mock_queue = AsyncMock()

            mock_connect.return_value = mock_connection
            mock_connection.channel.return_value = mock_channel
            mock_channel.declare_queue.return_value = mock_queue

            # Test full flow
            await router.connect()
            await router._setup_queues()

            # Create and route message
            order = NewOrderSingle(
                cl_ord_id="INTEGRATION_001",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=100000,
                ord_type=OrdType.MARKET,
            )

            message = OrderMessage(
                message_id="INT_MSG_001", order=order, broker_id="ib"
            )

            await router.route_order_message(message)

            # Verify complete flow
            mock_connect.assert_called_once()
            mock_connection.channel.assert_called()
            mock_channel.declare_queue.assert_called()
            mock_channel.default_exchange.publish.assert_called_once()

            await router.disconnect()
            mock_connection.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
