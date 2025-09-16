"""
Comprehensive retrospective test coverage for RabbitMQ Base Adapter.

This module provides comprehensive test coverage for the FXML4 RabbitMQ Base Adapter,
which provides the foundation for all RabbitMQ-based broker adapters, handling
message queuing, routing, and asynchronous communication patterns.

Following TDD principles with retrospective testing approach:
- Testing existing production RabbitMQ integration functionality
- Ensuring comprehensive coverage of messaging patterns and error handling
- Validating connection management and message routing
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import aio_pika
import pytest
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractMessage,
    AbstractQueue,
)

from fxml4.brokers.adapters.base import (
    AdapterConfig,
    BrokerAdapter,
    ConnectionStatus,
    OrderInfo,
    OrderStatus,
)
from fxml4.brokers.adapters.rabbitmq_base import (
    ConnectionPool,
    MessageRouter,
    MessageSerializationError,
    QueueManager,
    RabbitMQBrokerAdapter,
    RabbitMQConfig,
    RabbitMQError,
)
from fxml4.core.exceptions import BrokerError
from fxml4.core.exceptions import ConnectionError as FXMLConnectionError
from fxml4.core.logging import get_logger
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle


class TestRabbitMQBrokerAdapterInitialization:
    """Test RabbitMQ adapter initialization and configuration."""

    def test_initialization_with_default_config(self):
        """Test adapter initializes correctly with default RabbitMQ configuration."""
        config = AdapterConfig(
            adapter_type="rabbitmq_test",
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            order_queue="orders",
            execution_queue="executions",
        )

        adapter = RabbitMQBrokerAdapter(config)

        assert adapter.adapter_type == "rabbitmq_test"
        assert adapter.rabbitmq_url == "amqp://guest:guest@localhost:5672/"
        assert adapter.order_queue_name == "orders"
        assert adapter.execution_queue_name == "executions"
        assert adapter.connection is None
        assert adapter.channel is None
        assert len(adapter.message_handlers) == 0

    def test_initialization_with_custom_configuration(self):
        """Test adapter initialization with custom RabbitMQ configuration."""
        config = AdapterConfig(
            adapter_type="rabbitmq_test",
            rabbitmq_url="amqp://user:pass@rabbit.example.com:5672/vhost",
            order_queue="custom_orders",
            execution_queue="custom_executions",
            heartbeat_interval=60,
            connection_timeout=30,
            max_retries=5,
        )

        adapter = RabbitMQBrokerAdapter(config)

        assert adapter.rabbitmq_url == "amqp://user:pass@rabbit.example.com:5672/vhost"
        assert adapter.order_queue_name == "custom_orders"
        assert adapter.execution_queue_name == "custom_executions"
        assert adapter.heartbeat_interval == 60
        assert adapter.connection_timeout == 30
        assert adapter.max_retries == 5

    def test_initialization_validates_required_config(self):
        """Test adapter initialization validates required configuration."""
        invalid_configs = [
            # Missing RabbitMQ URL
            {"adapter_type": "rabbitmq_test"},
            # Empty RabbitMQ URL
            {"adapter_type": "rabbitmq_test", "rabbitmq_url": ""},
            # Invalid URL format
            {"adapter_type": "rabbitmq_test", "rabbitmq_url": "invalid-url"},
        ]

        for config_dict in invalid_configs:
            config = AdapterConfig(**config_dict)
            with pytest.raises(ValueError):
                RabbitMQBrokerAdapter(config)

    def test_initialization_with_ssl_configuration(self):
        """Test adapter initialization with SSL/TLS configuration."""
        config = AdapterConfig(
            adapter_type="rabbitmq_test",
            rabbitmq_url="amqps://user:pass@rabbit.example.com:5671/",
            ssl_context={
                "cert_file": "/path/to/cert.pem",
                "key_file": "/path/to/key.pem",
                "ca_file": "/path/to/ca.pem",
            },
        )

        adapter = RabbitMQBrokerAdapter(config)

        assert adapter.rabbitmq_url.startswith("amqps://")
        assert adapter.ssl_context is not None
        assert adapter.ssl_context["cert_file"] == "/path/to/cert.pem"

    def test_initialization_with_connection_pooling(self):
        """Test adapter initialization with connection pooling enabled."""
        config = AdapterConfig(
            adapter_type="rabbitmq_test",
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            enable_connection_pooling=True,
            max_pool_size=10,
            pool_recycle_time=3600,
        )

        adapter = RabbitMQBrokerAdapter(config)

        assert adapter.enable_connection_pooling is True
        assert adapter.max_pool_size == 10
        assert adapter.pool_recycle_time == 3600
        assert isinstance(adapter.connection_pool, ConnectionPool)


class TestRabbitMQBrokerAdapterConnection:
    """Test RabbitMQ connection management functionality."""

    @pytest.fixture
    def adapter(self):
        """Create adapter fixture for testing."""
        config = AdapterConfig(
            adapter_type="rabbitmq_test",
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            order_queue="orders",
            execution_queue="executions",
        )
        return RabbitMQBrokerAdapter(config)

    @pytest.mark.asyncio
    async def test_connect_successful(self, adapter):
        """Test successful RabbitMQ connection establishment."""
        with patch("aio_pika.connect_robust") as mock_connect:
            mock_connection = AsyncMock(spec=AbstractConnection)
            mock_channel = AsyncMock(spec=AbstractChannel)

            mock_connection.channel.return_value = mock_channel
            mock_connect.return_value = mock_connection

            result = await adapter.connect()

            assert result is True
            assert adapter.connection == mock_connection
            assert adapter.channel == mock_channel
            assert adapter.connection_status == ConnectionStatus.CONNECTED

            mock_connect.assert_called_once_with(
                adapter.rabbitmq_url,
                heartbeat=adapter.heartbeat_interval,
                timeout=adapter.connection_timeout,
            )

    @pytest.mark.asyncio
    async def test_connect_connection_failure(self, adapter):
        """Test connection failure handling."""
        with patch("aio_pika.connect_robust") as mock_connect:
            mock_connect.side_effect = FXMLConnectionError("RabbitMQ unavailable")

            result = await adapter.connect()

            assert result is False
            assert adapter.connection is None
            assert adapter.channel is None
            assert adapter.connection_status == ConnectionStatus.ERROR

    @pytest.mark.asyncio
    async def test_connect_with_retry_mechanism(self, adapter):
        """Test connection with automatic retry mechanism."""
        adapter.max_retries = 3

        with patch("aio_pika.connect_robust") as mock_connect:
            # First two attempts fail, third succeeds
            mock_connection = AsyncMock(spec=AbstractConnection)
            mock_channel = AsyncMock(spec=AbstractChannel)
            mock_connection.channel.return_value = mock_channel

            mock_connect.side_effect = [
                FXMLConnectionError("Failed"),
                FXMLConnectionError("Failed"),
                mock_connection,
            ]

            result = await adapter.connect()

            assert result is True
            assert mock_connect.call_count == 3
            assert adapter.connection == mock_connection

    @pytest.mark.asyncio
    async def test_disconnect_successful(self, adapter):
        """Test successful disconnection."""
        # Set up connected state
        mock_connection = AsyncMock(spec=AbstractConnection)
        mock_channel = AsyncMock(spec=AbstractChannel)

        adapter.connection = mock_connection
        adapter.channel = mock_channel
        adapter.connection_status = ConnectionStatus.CONNECTED

        result = await adapter.disconnect()

        assert result is True
        assert adapter.connection is None
        assert adapter.channel is None
        assert adapter.connection_status == ConnectionStatus.DISCONNECTED

        mock_channel.close.assert_called_once()
        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_connection_automatic_reconnection(self, adapter):
        """Test automatic reconnection when connection is lost."""
        with patch.object(adapter, "connect") as mock_connect:
            # Initially disconnected
            adapter.connection_status = ConnectionStatus.DISCONNECTED
            mock_connect.return_value = True

            result = await adapter._ensure_connection()

            assert result is True
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat_mechanism(self, adapter):
        """Test RabbitMQ heartbeat mechanism."""
        mock_connection = AsyncMock(spec=AbstractConnection)
        mock_connection.is_closed = False

        adapter.connection = mock_connection
        adapter.connection_status = ConnectionStatus.CONNECTED

        # Start heartbeat monitoring
        heartbeat_task = asyncio.create_task(adapter._monitor_heartbeat())

        # Let it run briefly
        await asyncio.sleep(0.1)

        # Stop heartbeat
        heartbeat_task.cancel()

        # Connection should remain healthy
        assert adapter.connection_status == ConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_connection_recovery_on_failure(self, adapter):
        """Test connection recovery after unexpected failure."""
        mock_connection = AsyncMock(spec=AbstractConnection)
        adapter.connection = mock_connection
        adapter.connection_status = ConnectionStatus.CONNECTED

        # Simulate connection failure
        mock_connection.is_closed = True

        with patch.object(adapter, "connect") as mock_reconnect:
            mock_reconnect.return_value = True

            await adapter._handle_connection_failure()

            mock_reconnect.assert_called_once()


class TestRabbitMQBrokerAdapterQueueManagement:
    """Test queue management functionality."""

    @pytest.fixture
    def connected_adapter(self):
        """Create connected adapter fixture."""
        config = AdapterConfig(
            adapter_type="rabbitmq_test",
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            order_queue="orders",
            execution_queue="executions",
        )
        adapter = RabbitMQBrokerAdapter(config)
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.connection_status = ConnectionStatus.CONNECTED
        return adapter

    @pytest.mark.asyncio
    async def test_setup_queues_successful(self, connected_adapter):
        """Test successful queue setup and binding."""
        mock_order_queue = AsyncMock(spec=AbstractQueue)
        mock_execution_queue = AsyncMock(spec=AbstractQueue)

        connected_adapter.channel.declare_queue.side_effect = [
            mock_order_queue,
            mock_execution_queue,
        ]

        await connected_adapter._setup_queues()

        assert connected_adapter.order_queue == mock_order_queue
        assert connected_adapter.execution_queue == mock_execution_queue

        # Verify queue declarations
        assert connected_adapter.channel.declare_queue.call_count == 2
        connected_adapter.channel.declare_queue.assert_any_call("orders", durable=True)
        connected_adapter.channel.declare_queue.assert_any_call(
            "executions", durable=True
        )

    @pytest.mark.asyncio
    async def test_setup_queues_with_bindings(self, connected_adapter):
        """Test queue setup with exchange bindings."""
        connected_adapter.exchange_name = "trading_exchange"
        connected_adapter.order_routing_key = "orders.submit"
        connected_adapter.execution_routing_key = "executions.report"

        mock_exchange = AsyncMock()
        mock_queue = AsyncMock(spec=AbstractQueue)

        connected_adapter.channel.declare_exchange.return_value = mock_exchange
        connected_adapter.channel.declare_queue.return_value = mock_queue

        await connected_adapter._setup_queues()

        # Verify exchange declaration
        connected_adapter.channel.declare_exchange.assert_called_once_with(
            "trading_exchange", type="topic", durable=True
        )

        # Verify queue bindings
        assert mock_queue.bind.call_count == 2

    @pytest.mark.asyncio
    async def test_setup_dead_letter_queues(self, connected_adapter):
        """Test setup of dead letter queues for error handling."""
        connected_adapter.enable_dead_letter_queue = True

        mock_dlq = AsyncMock(spec=AbstractQueue)
        connected_adapter.channel.declare_queue.return_value = mock_dlq

        await connected_adapter._setup_dead_letter_queues()

        connected_adapter.channel.declare_queue.assert_called_with(
            "orders.dlq", durable=True
        )

    @pytest.mark.asyncio
    async def test_queue_consumer_setup(self, connected_adapter):
        """Test setup of queue consumers."""
        mock_queue = AsyncMock(spec=AbstractQueue)
        connected_adapter.execution_queue = mock_queue

        message_handler = AsyncMock()

        await connected_adapter._setup_consumers([("execution_queue", message_handler)])

        mock_queue.consume.assert_called_once_with(message_handler, auto_ack=False)

    @pytest.mark.asyncio
    async def test_queue_purging(self, connected_adapter):
        """Test queue purging functionality."""
        mock_order_queue = AsyncMock(spec=AbstractQueue)
        mock_execution_queue = AsyncMock(spec=AbstractQueue)

        connected_adapter.order_queue = mock_order_queue
        connected_adapter.execution_queue = mock_execution_queue

        await connected_adapter.purge_queues()

        mock_order_queue.purge.assert_called_once()
        mock_execution_queue.purge.assert_called_once()

    @pytest.mark.asyncio
    async def test_queue_statistics(self, connected_adapter):
        """Test retrieval of queue statistics."""
        mock_queue = AsyncMock(spec=AbstractQueue)
        mock_queue.declaration_result.method.message_count = 10
        mock_queue.declaration_result.method.consumer_count = 2

        connected_adapter.order_queue = mock_queue

        stats = await connected_adapter.get_queue_stats("order_queue")

        assert stats["message_count"] == 10
        assert stats["consumer_count"] == 2


class TestRabbitMQBrokerAdapterMessageHandling:
    """Test message publishing and consumption functionality."""

    @pytest.fixture
    def connected_adapter(self):
        """Create connected adapter fixture."""
        config = AdapterConfig(
            adapter_type="rabbitmq_test",
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            order_queue="orders",
            execution_queue="executions",
        )
        adapter = RabbitMQBrokerAdapter(config)
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.connection_status = ConnectionStatus.CONNECTED

        # Mock queues
        adapter.order_queue = AsyncMock(spec=AbstractQueue)
        adapter.execution_queue = AsyncMock(spec=AbstractQueue)

        return adapter

    @pytest.mark.asyncio
    async def test_publish_order_message(self, connected_adapter):
        """Test publishing order messages to RabbitMQ."""
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        await connected_adapter._publish_order(order)

        # Verify message was published to order queue
        connected_adapter.channel.default_exchange.publish.assert_called_once()
        call_args = connected_adapter.channel.default_exchange.publish.call_args

        message = call_args[0][0]
        assert "ORDER-123" in message.body.decode()
        assert call_args[1]["routing_key"] == "orders"

    @pytest.mark.asyncio
    async def test_publish_with_message_properties(self, connected_adapter):
        """Test publishing messages with custom properties."""
        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        properties = {
            "priority": 5,
            "expiration": "60000",  # 60 seconds
            "correlation_id": "CORR-456",
            "reply_to": "reply_queue",
        }

        await connected_adapter._publish_order(order, **properties)

        call_args = connected_adapter.channel.default_exchange.publish.call_args
        message = call_args[0][0]

        assert message.priority == 5
        assert message.expiration == "60000"
        assert message.correlation_id == "CORR-456"
        assert message.reply_to == "reply_queue"

    @pytest.mark.asyncio
    async def test_consume_execution_report_message(self, connected_adapter):
        """Test consuming execution report messages."""
        execution_data = {
            "order_id": "BROKER-456",
            "client_order_id": "ORDER-123",
            "symbol": "EURUSD",
            "side": "B",
            "quantity": 100000.0,
            "price": 1.1850,
            "status": "F",  # Filled
            "exec_time": "2024-08-24T10:15:30.000Z",
        }

        # Mock message
        mock_message = AsyncMock(spec=AbstractMessage)
        mock_message.body = json.dumps(execution_data).encode()
        mock_message.correlation_id = "CORR-456"
        mock_message.reply_to = None

        # Process message
        await connected_adapter._handle_execution_report(mock_message)

        # Verify message was acknowledged
        mock_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_serialization_json(self, connected_adapter):
        """Test JSON message serialization."""
        data = {
            "order_id": "ORDER-123",
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": 100000.0,
            "timestamp": datetime.now().isoformat(),
        }

        serialized = connected_adapter._serialize_message(data, format="json")
        deserialized = connected_adapter._deserialize_message(serialized, format="json")

        assert deserialized["order_id"] == "ORDER-123"
        assert deserialized["symbol"] == "EURUSD"
        assert deserialized["quantity"] == 100000.0

    @pytest.mark.asyncio
    async def test_message_compression(self, connected_adapter):
        """Test message compression for large payloads."""
        connected_adapter.enable_compression = True

        # Large message data
        large_data = {
            "order_id": "ORDER-123",
            "large_field": "x" * 10000,  # 10KB of data
        }

        compressed = connected_adapter._compress_message(large_data)
        decompressed = connected_adapter._decompress_message(compressed)

        assert decompressed["order_id"] == "ORDER-123"
        assert len(decompressed["large_field"]) == 10000
        assert len(compressed) < len(json.dumps(large_data))

    @pytest.mark.asyncio
    async def test_message_routing_by_symbol(self, connected_adapter):
        """Test message routing based on symbol."""
        # Set up routing rules
        connected_adapter.symbol_routing = {
            "EURUSD": "eurusd_orders",
            "GBPUSD": "gbpusd_orders",
        }

        eur_order = NewOrderSingle(
            cl_ord_id="EUR-ORDER",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        gbp_order = NewOrderSingle(
            cl_ord_id="GBP-ORDER",
            symbol="GBPUSD",
            side=Side.SELL,
            ord_type=OrdType.MARKET,
            order_qty=50000.0,
        )

        # Publish orders
        await connected_adapter._publish_order(eur_order)
        await connected_adapter._publish_order(gbp_order)

        # Verify routing
        publish_calls = (
            connected_adapter.channel.default_exchange.publish.call_args_list
        )

        assert len(publish_calls) == 2
        assert publish_calls[0][1]["routing_key"] == "eurusd_orders"
        assert publish_calls[1][1]["routing_key"] == "gbpusd_orders"

    @pytest.mark.asyncio
    async def test_batch_message_publishing(self, connected_adapter):
        """Test batch publishing of multiple messages."""
        orders = []
        for i in range(5):
            order = NewOrderSingle(
                cl_ord_id=f"BATCH-ORDER-{i}",
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=10000.0,
            )
            orders.append(order)

        await connected_adapter._publish_batch(orders)

        # Verify all messages were published
        assert connected_adapter.channel.default_exchange.publish.call_count == 5

    @pytest.mark.asyncio
    async def test_message_acknowledgment_handling(self, connected_adapter):
        """Test proper message acknowledgment handling."""
        mock_message = AsyncMock(spec=AbstractMessage)
        mock_message.body = json.dumps({"test": "data"}).encode()

        # Successful processing
        connected_adapter.auto_ack = False
        await connected_adapter._process_message(mock_message, lambda x: None)
        mock_message.ack.assert_called_once()

        # Failed processing
        mock_message.reset_mock()

        def failing_handler(msg):
            raise Exception("Processing failed")

        await connected_adapter._process_message(mock_message, failing_handler)
        mock_message.nack.assert_called_once()


class TestRabbitMQBrokerAdapterErrorHandling:
    """Test error handling and recovery mechanisms."""

    @pytest.fixture
    def adapter(self):
        """Create adapter fixture for testing."""
        config = AdapterConfig(
            adapter_type="rabbitmq_test",
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
        )
        return RabbitMQBrokerAdapter(config)

    @pytest.mark.asyncio
    async def test_connection_failure_recovery(self, adapter):
        """Test recovery from connection failures."""
        with patch("aio_pika.connect_robust") as mock_connect:
            # First connection attempt fails
            mock_connect.side_effect = FXMLConnectionError("Connection failed")

            result = await adapter.connect()
            assert result is False

            # Second attempt succeeds
            mock_connection = AsyncMock(spec=AbstractConnection)
            mock_channel = AsyncMock(spec=AbstractChannel)
            mock_connection.channel.return_value = mock_channel
            mock_connect.side_effect = None
            mock_connect.return_value = mock_connection

            result = await adapter.connect()
            assert result is True

    @pytest.mark.asyncio
    async def test_message_serialization_error_handling(self, adapter):
        """Test handling of message serialization errors."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)

        # Invalid data that cannot be serialized
        invalid_data = {
            "timestamp": datetime.now(),  # Not JSON serializable
            "complex_object": object(),
        }

        with pytest.raises(MessageSerializationError):
            adapter._serialize_message(invalid_data, format="json")

    @pytest.mark.asyncio
    async def test_queue_declaration_failure_handling(self, adapter):
        """Test handling of queue declaration failures."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.connection_status = ConnectionStatus.CONNECTED

        # Queue declaration fails
        adapter.channel.declare_queue.side_effect = RabbitMQError(
            "Queue declaration failed"
        )

        with pytest.raises(RabbitMQError):
            await adapter._setup_queues()

    @pytest.mark.asyncio
    async def test_message_publishing_failure_handling(self, adapter):
        """Test handling of message publishing failures."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.connection_status = ConnectionStatus.CONNECTED

        # Publishing fails
        adapter.channel.default_exchange.publish.side_effect = RabbitMQError(
            "Publishing failed"
        )

        order = NewOrderSingle(
            cl_ord_id="ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        with pytest.raises(RabbitMQError):
            await adapter._publish_order(order)

    @pytest.mark.asyncio
    async def test_consumer_failure_recovery(self, adapter):
        """Test consumer failure recovery mechanisms."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.execution_queue = AsyncMock(spec=AbstractQueue)

        # Consumer fails
        async def failing_consumer():
            raise RabbitMQError("Consumer failed")

        with patch.object(adapter, "_setup_consumers") as mock_setup:
            mock_setup.return_value = failing_consumer()

            # Should attempt to restart consumer
            await adapter._handle_consumer_failure("execution_consumer")

            # Verify recovery attempt
            assert mock_setup.call_count >= 1

    @pytest.mark.asyncio
    async def test_connection_timeout_handling(self, adapter):
        """Test handling of connection timeouts."""
        adapter.connection_timeout = 1  # Short timeout for testing

        with patch("aio_pika.connect_robust") as mock_connect:
            mock_connect.side_effect = asyncio.TimeoutError("Connection timeout")

            result = await adapter.connect()

            assert result is False
            assert adapter.connection_status == ConnectionStatus.ERROR

    @pytest.mark.asyncio
    async def test_dead_letter_queue_processing(self, adapter):
        """Test processing of messages in dead letter queues."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.dead_letter_queue = AsyncMock(spec=AbstractQueue)

        # Mock dead letter message
        dead_message = AsyncMock(spec=AbstractMessage)
        dead_message.body = json.dumps(
            {
                "original_order_id": "ORDER-123",
                "error_reason": "Processing failed",
                "retry_count": 3,
            }
        ).encode()

        await adapter._process_dead_letter_message(dead_message)

        # Should acknowledge dead letter message
        dead_message.ack.assert_called_once()


class TestRabbitMQBrokerAdapterPerformance:
    """Test performance characteristics and optimization."""

    @pytest.fixture
    def adapter(self):
        """Create adapter fixture for performance testing."""
        config = AdapterConfig(
            adapter_type="rabbitmq_test",
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            prefetch_count=100,
            enable_publisher_confirms=True,
        )
        return RabbitMQBrokerAdapter(config)

    @pytest.mark.asyncio
    async def test_high_throughput_publishing(self, adapter):
        """Test high-throughput message publishing."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.connection_status = ConnectionStatus.CONNECTED

        # Generate many orders
        orders = []
        for i in range(100):
            order = NewOrderSingle(
                cl_ord_id=f"PERF-ORDER-{i}",
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=10000.0,
            )
            orders.append(order)

        start_time = datetime.now()

        # Publish all orders
        for order in orders:
            await adapter._publish_order(order)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Should publish 100 messages quickly
        assert duration < 1.0  # Less than 1 second
        assert adapter.channel.default_exchange.publish.call_count == 100

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, adapter):
        """Test concurrent processing of multiple messages."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)

        # Mock multiple messages
        messages = []
        for i in range(10):
            message = AsyncMock(spec=AbstractMessage)
            message.body = json.dumps(
                {"order_id": f"ORDER-{i}", "symbol": "EURUSD"}
            ).encode()
            messages.append(message)

        # Process messages concurrently
        processing_handler = AsyncMock()

        tasks = [adapter._process_message(msg, processing_handler) for msg in messages]

        await asyncio.gather(*tasks)

        # Verify all messages were processed
        assert processing_handler.call_count == 10

        for message in messages:
            message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_usage_with_large_queues(self, adapter):
        """Test memory usage with large queue volumes."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)

        # Simulate large queue with many messages
        queue_size = 1000
        messages = []

        for i in range(queue_size):
            message_data = {
                "order_id": f"LARGE-QUEUE-ORDER-{i}",
                "symbol": "EURUSD",
                "data": "x" * 1000,  # 1KB per message
            }
            messages.append(message_data)

        # Process large batch efficiently
        batch_size = 50
        for i in range(0, queue_size, batch_size):
            batch = messages[i : i + batch_size]
            await adapter._process_message_batch(batch)

        # Memory usage should remain reasonable
        # (This is more of a smoke test - actual memory monitoring would require additional tools)
        assert len(messages) == queue_size

    @pytest.mark.asyncio
    async def test_publisher_confirms_performance(self, adapter):
        """Test performance with publisher confirms enabled."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.enable_publisher_confirms = True

        # Mock publisher confirm
        adapter.channel.confirm_delivery.return_value = True

        orders = []
        for i in range(20):
            order = NewOrderSingle(
                cl_ord_id=f"CONFIRM-ORDER-{i}",
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=10000.0,
            )
            orders.append(order)

        start_time = datetime.now()

        for order in orders:
            await adapter._publish_order_with_confirm(order)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Should handle confirms efficiently
        assert duration < 2.0  # Allow more time for confirms
        assert adapter.channel.confirm_delivery.call_count == 20

    @pytest.mark.asyncio
    async def test_connection_pooling_performance(self, adapter):
        """Test performance benefits of connection pooling."""
        adapter.enable_connection_pooling = True
        adapter.max_pool_size = 5

        # Mock connection pool
        mock_pool = AsyncMock()
        mock_connections = [AsyncMock(spec=AbstractConnection) for _ in range(5)]

        mock_pool.acquire.side_effect = mock_connections
        adapter.connection_pool = mock_pool

        # Simulate multiple concurrent operations
        tasks = []
        for i in range(10):
            task = adapter._execute_with_pooled_connection(lambda conn: conn.channel())
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        # Should efficiently reuse connections
        assert mock_pool.acquire.call_count == 10


class TestRabbitMQBrokerAdapterIntegration:
    """Test integration scenarios and complete workflows."""

    @pytest.fixture
    def adapter(self):
        """Create adapter fixture for integration testing."""
        config = AdapterConfig(
            adapter_type="rabbitmq_test",
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            order_queue="orders",
            execution_queue="executions",
        )
        return RabbitMQBrokerAdapter(config)

    @pytest.mark.asyncio
    async def test_complete_order_workflow(self, adapter):
        """Test complete order workflow from submission to execution."""
        # Mock connected state
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.order_queue = AsyncMock(spec=AbstractQueue)
        adapter.execution_queue = AsyncMock(spec=AbstractQueue)
        adapter.connection_status = ConnectionStatus.CONNECTED

        # Submit order
        order = NewOrderSingle(
            cl_ord_id="WORKFLOW-ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        await adapter._publish_order(order)

        # Verify order was published
        adapter.channel.default_exchange.publish.assert_called_once()

        # Simulate execution report
        execution_data = {
            "order_id": "BROKER-456",
            "client_order_id": "WORKFLOW-ORDER-123",
            "symbol": "EURUSD",
            "status": "F",  # Filled
            "fill_price": 1.1850,
            "fill_quantity": 100000.0,
        }

        mock_execution_message = AsyncMock(spec=AbstractMessage)
        mock_execution_message.body = json.dumps(execution_data).encode()

        await adapter._handle_execution_report(mock_execution_message)

        # Verify execution was processed
        mock_execution_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_symbol_routing_workflow(self, adapter):
        """Test routing workflow for multiple symbols."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.connection_status = ConnectionStatus.CONNECTED

        # Set up symbol-specific routing
        adapter.symbol_routing = {
            "EURUSD": "eur_orders",
            "GBPUSD": "gbp_orders",
            "USDJPY": "jpy_orders",
        }

        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        orders = []

        for i, symbol in enumerate(symbols):
            order = NewOrderSingle(
                cl_ord_id=f"MULTI-ORDER-{i}",
                symbol=symbol,
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
            )
            orders.append(order)
            await adapter._publish_order(order)

        # Verify routing
        publish_calls = adapter.channel.default_exchange.publish.call_args_list
        expected_routing_keys = ["eur_orders", "gbp_orders", "jpy_orders"]

        for i, call in enumerate(publish_calls):
            assert call[1]["routing_key"] == expected_routing_keys[i]

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery_workflow(self, adapter):
        """Test complete error handling and recovery workflow."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.connection_status = ConnectionStatus.CONNECTED

        # Initial order submission succeeds
        order = NewOrderSingle(
            cl_ord_id="ERROR-ORDER-123",
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
        )

        await adapter._publish_order(order)
        assert adapter.channel.default_exchange.publish.call_count == 1

        # Simulate connection failure
        adapter.connection.is_closed = True
        adapter.connection_status = ConnectionStatus.ERROR

        # Attempt recovery
        with patch.object(adapter, "connect") as mock_connect:
            mock_connect.return_value = True

            await adapter._handle_connection_failure()

            mock_connect.assert_called_once()

        # Retry order submission after recovery
        adapter.connection_status = ConnectionStatus.CONNECTED
        await adapter._publish_order(order)

        assert adapter.channel.default_exchange.publish.call_count == 2

    @pytest.mark.asyncio
    async def test_load_balancing_across_queues(self, adapter):
        """Test load balancing orders across multiple queues."""
        adapter.connection = AsyncMock(spec=AbstractConnection)
        adapter.channel = AsyncMock(spec=AbstractChannel)
        adapter.connection_status = ConnectionStatus.CONNECTED

        # Set up multiple order queues for load balancing
        adapter.load_balance_queues = ["orders_1", "orders_2", "orders_3"]
        adapter.current_queue_index = 0

        orders = []
        for i in range(9):  # 3 orders per queue
            order = NewOrderSingle(
                cl_ord_id=f"LB-ORDER-{i}",
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=10000.0,
            )
            orders.append(order)
            await adapter._publish_order_with_load_balancing(order)

        # Verify load distribution
        publish_calls = adapter.channel.default_exchange.publish.call_args_list
        routing_keys = [call[1]["routing_key"] for call in publish_calls]

        # Should cycle through queues evenly
        expected_keys = ["orders_1", "orders_2", "orders_3"] * 3
        assert routing_keys == expected_keys
