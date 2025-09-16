"""
Test reliable message queue implementation.

This module tests the reliable message queue with persistence,
retry logic, circuit breakers, and dead letter handling.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aio_pika
import pytest

from fxml4.brokers.messaging.reliable_queue import (
    CircuitBreakerState,
    MessagePriority,
    MessageStatus,
    QueueMessage,
    ReliableMessageQueue,
)


@pytest.fixture
async def message_queue():
    """Create message queue instance."""
    queue = ReliableMessageQueue(
        rabbitmq_url="amqp://test:test@localhost/",
        redis_url="redis://localhost:6379",
        persistence_enabled=True,
    )
    yield queue
    # Cleanup
    if queue.rabbitmq_connection:
        await queue.disconnect()


@pytest.fixture
def sample_message():
    """Create sample message."""
    return QueueMessage(
        message_id="test-123",
        queue_name="test_queue",
        payload={"action": "process", "data": {"id": 1}},
        priority=MessagePriority.NORMAL,
    )


class TestQueueMessage:
    """Test QueueMessage class."""

    def test_message_serialization(self, sample_message):
        """Test message serialization to JSON."""
        json_str = sample_message.to_json()
        data = json.loads(json_str)

        assert data["message_id"] == "test-123"
        assert data["queue_name"] == "test_queue"
        assert data["payload"]["action"] == "process"
        assert data["priority"] == MessagePriority.NORMAL.value
        assert data["status"] == MessageStatus.PENDING.value

    def test_message_deserialization(self, sample_message):
        """Test message deserialization from JSON."""
        json_str = sample_message.to_json()
        restored = QueueMessage.from_json(json_str)

        assert restored.message_id == sample_message.message_id
        assert restored.queue_name == sample_message.queue_name
        assert restored.payload == sample_message.payload
        assert restored.priority == sample_message.priority
        assert restored.status == sample_message.status

    def test_message_with_expiration(self):
        """Test message with expiration."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        message = QueueMessage(
            message_id="exp-123", queue_name="test", payload={}, expires_at=expires_at
        )

        json_str = message.to_json()
        restored = QueueMessage.from_json(json_str)

        assert restored.expires_at == expires_at


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        breaker = CircuitBreakerState()

        assert breaker.state == "closed"
        assert breaker.can_process() is True

        # Record some successes
        for _ in range(3):
            breaker.record_success()

        assert breaker.state == "closed"
        assert breaker.success_count == 3

    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after failures."""
        breaker = CircuitBreakerState()

        # Record failures
        for _ in range(5):
            breaker.record_failure()

        assert breaker.state == "open"
        assert breaker.failure_count == 5
        assert breaker.can_process() is False

    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery through half-open state."""
        breaker = CircuitBreakerState()

        # Open the breaker
        for _ in range(5):
            breaker.record_failure()

        # Mock time passage
        breaker.last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=31)

        # Should allow processing (half-open)
        assert breaker.can_process() is True
        assert breaker.state == "half_open"

        # Record successes to close
        for _ in range(3):
            breaker.record_success()

        assert breaker.state == "closed"
        assert breaker.failure_count == 0


class TestReliableMessageQueue:
    """Test reliable message queue functionality."""

    @pytest.mark.asyncio
    async def test_queue_connection(self, message_queue):
        """Test queue connection establishment."""
        # Mock connections
        mock_rabbitmq = AsyncMock()
        mock_channel = AsyncMock()
        mock_redis = AsyncMock()

        mock_rabbitmq.channel.return_value = mock_channel

        with patch("aio_pika.connect_robust", return_value=mock_rabbitmq):
            with patch("redis.asyncio.from_url", return_value=mock_redis):
                await message_queue.connect()

                assert message_queue.rabbitmq_connection is not None
                assert message_queue.rabbitmq_channel is not None
                assert message_queue.redis_client is not None
                assert len(message_queue.exchanges) > 0

    @pytest.mark.asyncio
    async def test_declare_queue(self, message_queue):
        """Test queue declaration."""
        mock_channel = AsyncMock()
        mock_queue = AsyncMock()
        mock_dlq = AsyncMock()

        mock_channel.declare_queue.side_effect = [mock_queue, mock_dlq]
        message_queue.rabbitmq_channel = mock_channel
        message_queue.exchanges = {"direct": AsyncMock(), "dlx": AsyncMock()}

        queue = await message_queue.declare_queue(
            "test_queue", priority_queue=True, message_ttl=60000
        )

        assert queue == mock_queue
        assert "test_queue" in message_queue.queues
        assert "test_queue.dlq" in message_queue.queues

        # Verify queue arguments
        call_args = mock_channel.declare_queue.call_args_list[0][1]
        assert call_args["arguments"]["x-max-priority"] == 10
        assert call_args["arguments"]["x-message-ttl"] == 60000

    @pytest.mark.asyncio
    async def test_send_message(self, message_queue):
        """Test sending a message."""
        mock_exchange = AsyncMock()
        mock_redis = AsyncMock()

        message_queue.exchanges = {"direct": mock_exchange}
        message_queue.redis_client = mock_redis
        message_queue.persistence_enabled = True

        message_id = await message_queue.send_message(
            "test_queue",
            {"data": "test"},
            priority=MessagePriority.HIGH,
            correlation_id="corr-123",
            expiration_seconds=300,
        )

        assert message_id is not None
        assert message_queue.metrics["messages_sent"] == 1

        # Verify message published
        mock_exchange.publish.assert_called_once()
        published_msg = mock_exchange.publish.call_args[0][0]
        assert published_msg.priority == MessagePriority.HIGH.value

        # Verify persistence
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_deduplication(self, message_queue):
        """Test message deduplication."""
        mock_exchange = AsyncMock()
        message_queue.exchanges = {"direct": mock_exchange}

        # Send first message
        message_id1 = await message_queue.send_message(
            "test_queue", {"data": "test"}, deduplication_id="dedup-123"
        )

        # Try to send duplicate
        message_id2 = await message_queue.send_message(
            "test_queue", {"data": "test"}, deduplication_id="dedup-123"
        )

        assert message_id2 == "dedup-123"  # Same ID returned
        assert mock_exchange.publish.call_count == 1  # Only sent once

    @pytest.mark.asyncio
    async def test_consume_messages_success(self, message_queue):
        """Test successful message consumption."""
        # Setup mock queue
        mock_queue = AsyncMock()
        mock_amqp_message = AsyncMock()

        test_message = QueueMessage(
            message_id="consume-123",
            queue_name="test_queue",
            payload={"action": "test"},
        )

        mock_amqp_message.body = test_message.to_json().encode()
        mock_queue.iterator.return_value.__aenter__.return_value = [mock_amqp_message]

        message_queue.queues = {"test_queue": mock_queue}

        # Handler
        handler_called = False

        async def test_handler(payload, message):
            nonlocal handler_called
            handler_called = True
            assert payload["action"] == "test"

        # Consume one message
        consume_task = asyncio.create_task(
            message_queue.consume_messages("test_queue", test_handler, auto_ack=True)
        )

        await asyncio.sleep(0.1)  # Let it process
        consume_task.cancel()

        assert handler_called
        assert message_queue.metrics["messages_received"] == 1
        assert message_queue.metrics["messages_completed"] == 1
        mock_amqp_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_consume_messages_with_retry(self, message_queue):
        """Test message consumption with retry on failure."""
        mock_queue = AsyncMock()
        mock_amqp_message = AsyncMock()

        test_message = QueueMessage(
            message_id="retry-123",
            queue_name="test_queue",
            payload={"action": "fail"},
            max_retries=2,
        )

        mock_amqp_message.body = test_message.to_json().encode()
        mock_queue.iterator.return_value.__aenter__.return_value = [mock_amqp_message]

        message_queue.queues = {"test_queue": mock_queue}

        # Handler that fails
        call_count = 0

        async def failing_handler(payload, message):
            nonlocal call_count
            call_count += 1
            raise Exception("Processing failed")

        # Process message
        with patch.object(message_queue, "_process_message") as mock_process:
            mock_process.side_effect = failing_handler

            consume_task = asyncio.create_task(
                message_queue.consume_messages("test_queue", failing_handler)
            )

            await asyncio.sleep(0.1)
            consume_task.cancel()

        # Should reject for retry
        mock_amqp_message.reject.assert_called_with(requeue=True)
        assert message_queue.metrics["messages_failed"] > 0

    @pytest.mark.asyncio
    async def test_expired_message_handling(self, message_queue):
        """Test handling of expired messages."""
        mock_queue = AsyncMock()
        mock_amqp_message = AsyncMock()

        # Create expired message
        test_message = QueueMessage(
            message_id="expired-123",
            queue_name="test_queue",
            payload={"action": "test"},
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        mock_amqp_message.body = test_message.to_json().encode()
        mock_queue.iterator.return_value.__aenter__.return_value = [mock_amqp_message]

        message_queue.queues = {"test_queue": mock_queue}

        handler_called = False

        async def test_handler(payload, message):
            nonlocal handler_called
            handler_called = True

        consume_task = asyncio.create_task(
            message_queue.consume_messages("test_queue", test_handler)
        )

        await asyncio.sleep(0.1)
        consume_task.cancel()

        # Handler should not be called
        assert not handler_called
        assert message_queue.metrics["messages_expired"] == 1
        mock_amqp_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_dead_letter_handling(self, message_queue):
        """Test dead letter queue handling."""
        # Setup for max retries exceeded
        test_message = QueueMessage(
            message_id="dlq-123",
            queue_name="test_queue",
            payload={"action": "fail"},
            retry_count=3,  # Already at max
            max_retries=3,
        )

        mock_amqp_message = AsyncMock()
        mock_redis = AsyncMock()
        message_queue.redis_client = mock_redis

        # Add dead letter handler
        dlq_handler_called = False

        async def dlq_handler(message):
            nonlocal dlq_handler_called
            dlq_handler_called = True
            assert message.status == MessageStatus.DEAD_LETTER

        message_queue.add_dead_letter_handler(dlq_handler)

        # Process failed message
        async def failing_handler(payload, message):
            raise Exception("Final failure")

        breaker = CircuitBreakerState()
        await message_queue._process_message(
            test_message, failing_handler, mock_amqp_message, breaker
        )

        assert dlq_handler_called
        assert message_queue.metrics["messages_dead_lettered"] == 1
        mock_amqp_message.reject.assert_called_with(requeue=False)

        # Verify persistence
        if message_queue.persistence_enabled:
            mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, message_queue):
        """Test circuit breaker prevents processing."""
        mock_queue = AsyncMock()
        mock_amqp_message = AsyncMock()

        test_message = QueueMessage(
            message_id="cb-123", queue_name="test_queue", payload={"action": "test"}
        )

        mock_amqp_message.body = test_message.to_json().encode()
        mock_queue.iterator.return_value.__aenter__.return_value = [mock_amqp_message]

        message_queue.queues = {"test_queue": mock_queue}

        # Open circuit breaker
        breaker = message_queue.circuit_breakers["test_queue"]
        for _ in range(5):
            breaker.record_failure()

        handler_called = False

        async def test_handler(payload, message):
            nonlocal handler_called
            handler_called = True

        consume_task = asyncio.create_task(
            message_queue.consume_messages("test_queue", test_handler)
        )

        await asyncio.sleep(0.1)
        consume_task.cancel()

        # Handler should not be called
        assert not handler_called
        # Message should be rejected with requeue
        mock_amqp_message.reject.assert_called_with(requeue=True)

    @pytest.mark.asyncio
    async def test_message_restoration(self, message_queue):
        """Test restoration of pending messages from persistence."""
        mock_redis = AsyncMock()
        message_queue.redis_client = mock_redis

        # Mock persisted messages
        mock_redis.keys.return_value = ["mq:queue:test_queue"]
        mock_redis.smembers.return_value = {"msg-1", "msg-2"}

        pending_message = QueueMessage(
            message_id="msg-1",
            queue_name="test_queue",
            payload={"restore": True},
            status=MessageStatus.PENDING,
        )

        mock_redis.get.return_value = pending_message.to_json()

        with patch.object(message_queue, "send_message") as mock_send:
            await message_queue._restore_pending_messages()

            # Should resend pending message
            mock_send.assert_called()
            call_args = mock_send.call_args[0]
            assert call_args[0] == "test_queue"
            assert call_args[1]["restore"] is True

    @pytest.mark.asyncio
    async def test_queue_metrics(self, message_queue):
        """Test queue metrics collection."""
        mock_queue = AsyncMock()
        queue_info = Mock()
        queue_info.message_count = 10
        queue_info.consumer_count = 2

        mock_queue.declare.return_value = queue_info
        message_queue.queues = {"test_queue": mock_queue}

        # Add some processing messages
        message_queue.processing_messages = {
            "1": QueueMessage("1", "test_queue", {}),
            "2": QueueMessage("2", "test_queue", {}),
            "3": QueueMessage("3", "other_queue", {}),
        }

        metrics = await message_queue.get_queue_metrics("test_queue")

        assert metrics["message_count"] == 10
        assert metrics["consumer_count"] == 2
        assert metrics["processing_count"] == 2
        assert metrics["circuit_breaker_state"] == "closed"

    def test_global_metrics(self, message_queue):
        """Test global metrics collection."""
        message_queue.metrics = {
            "messages_sent": 100,
            "messages_received": 95,
            "messages_completed": 90,
            "messages_failed": 5,
            "messages_dead_lettered": 2,
            "messages_expired": 3,
        }

        message_queue.processing_messages = {"1": Mock(), "2": Mock()}
        message_queue.queues = {"q1": Mock(), "q2": Mock()}

        # Open one circuit breaker
        message_queue.circuit_breakers["q1"].state = "open"

        metrics = message_queue.get_global_metrics()

        assert metrics["messages_sent"] == 100
        assert metrics["messages_completed"] == 90
        assert metrics["processing_messages"] == 2
        assert metrics["active_queues"] == 2
        assert metrics["circuit_breakers_open"] == 1
