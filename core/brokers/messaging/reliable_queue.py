"""
Reliable message queue implementation with persistence and retry.

This module provides a robust message queue system with:
- Message persistence and durability
- Automatic retry with exponential backoff
- Dead letter queue for failed messages
- Circuit breaker pattern for failing consumers
- Message deduplication
- Priority queuing
"""

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import aio_pika
import redis.asyncio as redis
from aio_pika import DeliveryMode, ExchangeType, Message

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 7
    CRITICAL = 9


class MessageStatus(Enum):
    """Message processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class QueueMessage:
    """Reliable message with tracking."""

    message_id: str
    queue_name: str
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    status: MessageStatus = MessageStatus.PENDING
    error_message: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_json(self) -> str:
        """Serialize message to JSON."""
        data = asdict(self)
        # Convert datetime objects
        for key in [
            "created_at",
            "expires_at",
            "processing_started_at",
            "completed_at",
        ]:
            if data[key]:
                data[key] = data[key].isoformat()
        # Convert enums
        data["priority"] = self.priority.value
        data["status"] = self.status.value
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "QueueMessage":
        """Deserialize message from JSON."""
        data = json.loads(json_str)
        # Convert datetime strings
        for key in [
            "created_at",
            "expires_at",
            "processing_started_at",
            "completed_at",
        ]:
            if data[key]:
                data[key] = datetime.fromisoformat(data[key])
        # Convert enums
        data["priority"] = MessagePriority(data["priority"])
        data["status"] = MessageStatus(data["status"])
        return cls(**data)


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for consumer protection."""

    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "closed"  # closed, open, half_open

    def record_success(self):
        """Record successful processing."""
        self.success_count += 1
        if self.state == "half_open" and self.success_count >= 3:
            self.state = "closed"
            self.failure_count = 0
            logger.info("Circuit breaker closed after successful recovery")

    def record_failure(self):
        """Record failed processing."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.failure_count >= 5 and self.state == "closed":
            self.state = "open"
            logger.warning("Circuit breaker opened after 5 failures")

    def can_process(self) -> bool:
        """Check if processing is allowed."""
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if we should try half-open
            if self.last_failure_time:
                elapsed = datetime.now(timezone.utc) - self.last_failure_time
                if elapsed > timedelta(seconds=30):
                    self.state = "half_open"
                    self.success_count = 0
                    logger.info("Circuit breaker entering half-open state")
                    return True
            return False

        # half_open state
        return True


class ReliableMessageQueue:
    """
    Reliable message queue with persistence and retry capabilities.
    """

    def __init__(
        self,
        rabbitmq_url: str = "amqp://guest:guest@localhost/",
        redis_url: str = "redis://localhost:6379",
        persistence_enabled: bool = True,
    ):
        """
        Initialize reliable message queue.

        Args:
            rabbitmq_url: RabbitMQ connection URL
            redis_url: Redis connection URL for persistence
            persistence_enabled: Enable message persistence in Redis
        """
        self.rabbitmq_url = rabbitmq_url
        self.redis_url = redis_url
        self.persistence_enabled = persistence_enabled

        # Connections
        self.rabbitmq_connection: Optional[aio_pika.Connection] = None
        self.rabbitmq_channel: Optional[aio_pika.Channel] = None
        self.redis_client: Optional[redis.Redis] = None

        # Exchanges and queues
        self.exchanges: Dict[str, aio_pika.Exchange] = {}
        self.queues: Dict[str, aio_pika.Queue] = {}

        # Message tracking
        self.processing_messages: Dict[str, QueueMessage] = {}
        self.message_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.dead_letter_handlers: List[Callable] = []

        # Circuit breakers for each queue
        self.circuit_breakers: Dict[str, CircuitBreakerState] = defaultdict(
            CircuitBreakerState
        )

        # Deduplication
        self.processed_messages: Set[str] = set()
        self.dedup_window_seconds = 300  # 5 minutes

        # Monitoring
        self.metrics = {
            "messages_sent": 0,
            "messages_received": 0,
            "messages_completed": 0,
            "messages_failed": 0,
            "messages_dead_lettered": 0,
            "messages_expired": 0,
        }

    async def connect(self):
        """Establish connections to RabbitMQ and Redis."""
        # Connect to RabbitMQ
        self.rabbitmq_connection = await aio_pika.connect_robust(
            self.rabbitmq_url, reconnect_interval=5, connection_attempts=10
        )

        self.rabbitmq_channel = await self.rabbitmq_connection.channel()
        await self.rabbitmq_channel.set_qos(prefetch_count=10)

        # Create exchanges
        self.exchanges["direct"] = await self.rabbitmq_channel.declare_exchange(
            "fxml4.direct", type=ExchangeType.DIRECT, durable=True
        )

        self.exchanges["topic"] = await self.rabbitmq_channel.declare_exchange(
            "fxml4.topic", type=ExchangeType.TOPIC, durable=True
        )

        self.exchanges["dlx"] = await self.rabbitmq_channel.declare_exchange(
            "fxml4.dlx", type=ExchangeType.DIRECT, durable=True
        )

        # Connect to Redis if persistence enabled
        if self.persistence_enabled:
            self.redis_client = await redis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )

            # Restore any pending messages
            await self._restore_pending_messages()

        logger.info("Reliable message queue connected")

    async def disconnect(self):
        """Close all connections."""
        if self.rabbitmq_connection:
            await self.rabbitmq_connection.close()

        if self.redis_client:
            await self.redis_client.close()

        logger.info("Reliable message queue disconnected")

    async def declare_queue(
        self,
        queue_name: str,
        durable: bool = True,
        priority_queue: bool = False,
        message_ttl: Optional[int] = None,
    ) -> aio_pika.Queue:
        """
        Declare a queue with optional features.

        Args:
            queue_name: Name of the queue
            durable: Persist queue to disk
            priority_queue: Enable priority queuing
            message_ttl: Message TTL in milliseconds
        """
        arguments = {
            "x-dead-letter-exchange": "fxml4.dlx",
            "x-dead-letter-routing-key": f"{queue_name}.dlq",
        }

        if priority_queue:
            arguments["x-max-priority"] = 10

        if message_ttl:
            arguments["x-message-ttl"] = message_ttl

        # Declare main queue
        queue = await self.rabbitmq_channel.declare_queue(
            queue_name, durable=durable, arguments=arguments
        )

        # Bind to direct exchange
        await queue.bind(self.exchanges["direct"], routing_key=queue_name)

        # Declare dead letter queue
        dlq = await self.rabbitmq_channel.declare_queue(
            f"{queue_name}.dlq", durable=durable
        )
        await dlq.bind(self.exchanges["dlx"], routing_key=f"{queue_name}.dlq")

        self.queues[queue_name] = queue
        self.queues[f"{queue_name}.dlq"] = dlq

        logger.info(f"Queue declared: {queue_name}")
        return queue

    async def send_message(
        self,
        queue_name: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None,
        expiration_seconds: Optional[int] = None,
        deduplication_id: Optional[str] = None,
    ) -> str:
        """
        Send a reliable message to a queue.

        Args:
            queue_name: Target queue name
            payload: Message payload
            priority: Message priority
            correlation_id: Correlation ID for request-response
            expiration_seconds: Message expiration time
            deduplication_id: ID for deduplication

        Returns:
            Message ID
        """
        # Check deduplication
        if deduplication_id and deduplication_id in self.processed_messages:
            logger.info(f"Duplicate message skipped: {deduplication_id}")
            return deduplication_id

        # Create message
        message = QueueMessage(
            message_id=str(uuid.uuid4()),
            queue_name=queue_name,
            payload=payload,
            priority=priority,
            correlation_id=correlation_id,
            expires_at=(
                datetime.now(timezone.utc) + timedelta(seconds=expiration_seconds)
                if expiration_seconds
                else None
            ),
        )

        # Persist if enabled
        if self.persistence_enabled:
            await self._persist_message(message)

        # Create AMQP message
        amqp_message = Message(
            body=message.to_json().encode(),
            message_id=message.message_id,
            correlation_id=correlation_id,
            priority=priority.value,
            delivery_mode=DeliveryMode.PERSISTENT,
            expiration=expiration_seconds * 1000 if expiration_seconds else None,
        )

        # Send message
        exchange = self.exchanges["direct"]
        await exchange.publish(amqp_message, routing_key=queue_name)

        self.metrics["messages_sent"] += 1

        # Track deduplication
        if deduplication_id:
            self.processed_messages.add(deduplication_id)
            # Clean old entries periodically
            asyncio.create_task(self._cleanup_dedup_cache(deduplication_id))

        logger.info(f"Message sent: {message.message_id} to {queue_name}")
        return message.message_id

    async def consume_messages(
        self, queue_name: str, handler: Callable, auto_ack: bool = False
    ):
        """
        Consume messages from a queue with reliability features.

        Args:
            queue_name: Queue to consume from
            handler: Async message handler function
            auto_ack: Automatically acknowledge messages
        """
        if queue_name not in self.queues:
            await self.declare_queue(queue_name)

        queue = self.queues[queue_name]
        self.message_handlers[queue_name].append(handler)

        async with queue.iterator() as queue_iter:
            async for amqp_message in queue_iter:
                try:
                    # Check circuit breaker
                    breaker = self.circuit_breakers[queue_name]
                    if not breaker.can_process():
                        logger.warning(
                            f"Circuit breaker open for {queue_name}, rejecting message"
                        )
                        await amqp_message.reject(requeue=True)
                        await asyncio.sleep(1)
                        continue

                    # Parse message
                    message = QueueMessage.from_json(amqp_message.body.decode())

                    # Check expiration
                    if (
                        message.expires_at
                        and datetime.now(timezone.utc) > message.expires_at
                    ):
                        logger.warning(f"Message expired: {message.message_id}")
                        await amqp_message.ack()
                        self.metrics["messages_expired"] += 1
                        continue

                    # Update status
                    message.status = MessageStatus.PROCESSING
                    message.processing_started_at = datetime.now(timezone.utc)
                    self.processing_messages[message.message_id] = message

                    if self.persistence_enabled:
                        await self._persist_message(message)

                    self.metrics["messages_received"] += 1

                    # Process message
                    await self._process_message(message, handler, amqp_message, breaker)

                    if auto_ack:
                        await amqp_message.ack()

                except Exception as e:
                    logger.error(f"Error consuming message: {e}")
                    if not auto_ack:
                        await amqp_message.reject(requeue=True)

    async def _process_message(
        self,
        message: QueueMessage,
        handler: Callable,
        amqp_message: aio_pika.IncomingMessage,
        breaker: CircuitBreakerState,
    ):
        """Process a message with error handling and retry."""
        try:
            # Call handler
            await handler(message.payload, message)

            # Success
            message.status = MessageStatus.COMPLETED
            message.completed_at = datetime.now(timezone.utc)

            await amqp_message.ack()

            breaker.record_success()
            self.metrics["messages_completed"] += 1

            # Clean up
            self.processing_messages.pop(message.message_id, None)
            if self.persistence_enabled:
                await self._remove_persisted_message(message.message_id)

        except Exception as e:
            logger.error(f"Error processing message {message.message_id}: {e}")

            breaker.record_failure()
            message.retry_count += 1
            message.error_message = str(e)

            if message.retry_count <= message.max_retries:
                # Retry with exponential backoff
                delay = min(2**message.retry_count, 300)  # Max 5 minutes
                logger.info(f"Retrying message {message.message_id} in {delay}s")

                await amqp_message.reject(requeue=True)
                await asyncio.sleep(delay)

            else:
                # Send to dead letter queue
                message.status = MessageStatus.DEAD_LETTER
                await amqp_message.reject(requeue=False)

                self.metrics["messages_dead_lettered"] += 1

                # Notify dead letter handlers
                for handler in self.dead_letter_handlers:
                    try:
                        await handler(message)
                    except Exception as handler_error:
                        logger.error(f"Dead letter handler error: {handler_error}")

                # Clean up
                self.processing_messages.pop(message.message_id, None)
                if self.persistence_enabled:
                    await self._persist_dead_letter(message)

            self.metrics["messages_failed"] += 1

    async def _persist_message(self, message: QueueMessage):
        """Persist message to Redis."""
        if not self.redis_client:
            return

        key = f"mq:message:{message.message_id}"
        await self.redis_client.setex(
            key, timedelta(days=7), message.to_json()  # Keep for 7 days
        )

        # Add to queue set
        queue_key = f"mq:queue:{message.queue_name}"
        await self.redis_client.sadd(queue_key, message.message_id)

    async def _remove_persisted_message(self, message_id: str):
        """Remove persisted message from Redis."""
        if not self.redis_client:
            return

        key = f"mq:message:{message_id}"
        message_json = await self.redis_client.get(key)

        if message_json:
            message = QueueMessage.from_json(message_json)
            queue_key = f"mq:queue:{message.queue_name}"
            await self.redis_client.srem(queue_key, message_id)

        await self.redis_client.delete(key)

    async def _persist_dead_letter(self, message: QueueMessage):
        """Persist dead letter message."""
        if not self.redis_client:
            return

        key = f"mq:dead_letter:{message.message_id}"
        await self.redis_client.setex(
            key, timedelta(days=30), message.to_json()  # Keep for 30 days
        )

        # Add to dead letter set
        dlq_key = f"mq:dead_letter_queue"
        await self.redis_client.sadd(dlq_key, message.message_id)

    async def _restore_pending_messages(self):
        """Restore pending messages from persistence on startup."""
        if not self.redis_client:
            return

        # Get all queue keys
        queue_keys = await self.redis_client.keys("mq:queue:*")

        for queue_key in queue_keys:
            queue_name = queue_key.split(":")[-1]
            message_ids = await self.redis_client.smembers(queue_key)

            for message_id in message_ids:
                message_key = f"mq:message:{message_id}"
                message_json = await self.redis_client.get(message_key)

                if message_json:
                    message = QueueMessage.from_json(message_json)

                    # Re-send if it was pending or processing
                    if message.status in [
                        MessageStatus.PENDING,
                        MessageStatus.PROCESSING,
                    ]:
                        logger.info(f"Restoring message: {message_id}")
                        await self.send_message(
                            message.queue_name,
                            message.payload,
                            message.priority,
                            message.correlation_id,
                        )

    async def _cleanup_dedup_cache(self, dedup_id: str):
        """Remove deduplication ID after window expires."""
        await asyncio.sleep(self.dedup_window_seconds)
        self.processed_messages.discard(dedup_id)

    def add_dead_letter_handler(self, handler: Callable):
        """Add a handler for dead letter messages."""
        self.dead_letter_handlers.append(handler)

    async def get_queue_metrics(self, queue_name: str) -> Dict[str, Any]:
        """Get metrics for a specific queue."""
        queue = self.queues.get(queue_name)
        if not queue:
            return {}

        # Get queue info
        queue_info = await queue.declare(passive=True)

        breaker = self.circuit_breakers[queue_name]

        return {
            "message_count": queue_info.message_count,
            "consumer_count": queue_info.consumer_count,
            "circuit_breaker_state": breaker.state,
            "failure_count": breaker.failure_count,
            "processing_count": len(
                [
                    m
                    for m in self.processing_messages.values()
                    if m.queue_name == queue_name
                ]
            ),
        }

    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global queue metrics."""
        return {
            **self.metrics,
            "processing_messages": len(self.processing_messages),
            "active_queues": len(self.queues),
            "circuit_breakers_open": len(
                [b for b in self.circuit_breakers.values() if b.state == "open"]
            ),
        }
