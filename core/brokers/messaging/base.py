"""Message Broker Abstraction.

This module provides abstract interfaces for message brokers, allowing
the system to work with different messaging backends (RabbitMQ, Kafka, Redis, etc.)
without coupling to specific implementations.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class MessageStatus(Enum):
    """Message delivery status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"


class QueueType(Enum):
    """Queue type for different message patterns."""

    DIRECT = "direct"  # Point-to-point
    FANOUT = "fanout"  # Broadcast to all consumers
    TOPIC = "topic"  # Pattern-based routing
    WORK_QUEUE = "work_queue"  # Load-balanced work distribution


@dataclass
class MessageMetadata:
    """Metadata for a message."""

    message_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sender_id: str = ""
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    content_type: str = "application/json"
    priority: int = 0
    ttl_seconds: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
            "sender_id": self.sender_id,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "content_type": self.content_type,
            "priority": self.priority,
            "ttl_seconds": self.ttl_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


@dataclass
class Message:
    """Generic message container."""

    data: Dict[str, Any]
    metadata: MessageMetadata
    routing_key: str = ""
    queue_name: str = ""
    status: MessageStatus = MessageStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "data": self.data,
            "metadata": self.metadata.to_dict(),
            "routing_key": self.routing_key,
            "queue_name": self.queue_name,
            "status": self.status.value,
        }


@dataclass
class QueueConfig:
    """Configuration for a message queue."""

    name: str
    queue_type: QueueType = QueueType.DIRECT
    durable: bool = True
    auto_delete: bool = False
    exclusive: bool = False
    max_size: Optional[int] = None
    ttl_seconds: Optional[int] = None
    dead_letter_queue: Optional[str] = None
    routing_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "queue_type": self.queue_type.value,
            "durable": self.durable,
            "auto_delete": self.auto_delete,
            "exclusive": self.exclusive,
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "dead_letter_queue": self.dead_letter_queue,
            "routing_patterns": self.routing_patterns,
        }


@dataclass
class ConsumerConfig:
    """Configuration for message consumer."""

    queue_name: str
    handler: Callable[[Message], Any]
    auto_ack: bool = True
    prefetch_count: int = 1
    exclusive: bool = False
    consumer_tag: Optional[str] = None
    error_handler: Optional[Callable[[Exception, Message], Any]] = None
    retry_handler: Optional[Callable[[Message], bool]] = None


class MessageHandler(ABC):
    """Abstract base class for message handlers."""

    @abstractmethod
    async def handle_message(self, message: Message) -> bool:
        """Handle incoming message.

        Args:
            message: The message to handle.

        Returns:
            True if message was handled successfully, False otherwise.
        """
        pass

    async def handle_error(self, error: Exception, message: Message) -> bool:
        """Handle error during message processing.

        Args:
            error: The exception that occurred.
            message: The message that caused the error.

        Returns:
            True if error was handled (message should be acked), False otherwise.
        """
        logger.error(f"Error handling message {message.metadata.message_id}: {error}")
        return False


class MessageBroker(ABC):
    """Abstract interface for message brokers."""

    def __init__(self, broker_id: str):
        """Initialize message broker.

        Args:
            broker_id: Unique identifier for this broker instance.
        """
        self.broker_id = broker_id
        self.connected = False
        self.consumers: Dict[str, ConsumerConfig] = {}
        self.queues: Dict[str, QueueConfig] = {}

        # Message tracking
        self.messages_sent = 0
        self.messages_received = 0
        self.messages_failed = 0

        # Connection callbacks
        self.on_connect: Optional[Callable[[], Any]] = None
        self.on_disconnect: Optional[Callable[[], Any]] = None
        self.on_error: Optional[Callable[[Exception], Any]] = None

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the message broker.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from the message broker."""
        pass

    @abstractmethod
    async def create_queue(self, config: QueueConfig) -> bool:
        """Create a queue with the given configuration.

        Args:
            config: Queue configuration.

        Returns:
            True if queue was created successfully.
        """
        pass

    @abstractmethod
    async def delete_queue(self, queue_name: str) -> bool:
        """Delete a queue.

        Args:
            queue_name: Name of the queue to delete.

        Returns:
            True if queue was deleted successfully.
        """
        pass

    @abstractmethod
    async def publish_message(
        self, message: Message, exchange: Optional[str] = None
    ) -> bool:
        """Publish a message.

        Args:
            message: Message to publish.
            exchange: Exchange to publish to (broker-specific).

        Returns:
            True if message was published successfully.
        """
        pass

    @abstractmethod
    async def subscribe(self, config: ConsumerConfig) -> str:
        """Subscribe to a queue for message consumption.

        Args:
            config: Consumer configuration.

        Returns:
            Consumer tag/ID for managing the subscription.
        """
        pass

    @abstractmethod
    async def unsubscribe(self, consumer_tag: str) -> bool:
        """Unsubscribe from message consumption.

        Args:
            consumer_tag: Consumer identifier from subscribe().

        Returns:
            True if unsubscribed successfully.
        """
        pass

    @abstractmethod
    async def acknowledge_message(self, message: Message) -> bool:
        """Acknowledge message processing.

        Args:
            message: Message to acknowledge.

        Returns:
            True if acknowledged successfully.
        """
        pass

    @abstractmethod
    async def reject_message(self, message: Message, requeue: bool = False) -> bool:
        """Reject a message.

        Args:
            message: Message to reject.
            requeue: Whether to requeue the message.

        Returns:
            True if rejected successfully.
        """
        pass

    # High-level convenience methods

    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        routing_key: Optional[str] = None,
        metadata: Optional[MessageMetadata] = None,
    ) -> bool:
        """Publish an event message.

        Args:
            event_type: Type of event.
            data: Event data.
            routing_key: Optional routing key.
            metadata: Optional message metadata.

        Returns:
            True if published successfully.
        """
        if metadata is None:
            metadata = MessageMetadata(
                message_id=f"{self.broker_id}_{datetime.now(timezone.utc).timestamp()}",
                sender_id=self.broker_id,
            )

        event_data = {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        message = Message(
            data=event_data,
            metadata=metadata,
            routing_key=routing_key or f"events.{event_type}",
        )

        return await self.publish_message(message)

    async def publish_command(
        self,
        command_type: str,
        target: str,
        data: Dict[str, Any],
        metadata: Optional[MessageMetadata] = None,
    ) -> bool:
        """Publish a command message.

        Args:
            command_type: Type of command.
            target: Target service/component.
            data: Command data.
            metadata: Optional message metadata.

        Returns:
            True if published successfully.
        """
        if metadata is None:
            metadata = MessageMetadata(
                message_id=f"{self.broker_id}_{datetime.now(timezone.utc).timestamp()}",
                sender_id=self.broker_id,
            )

        command_data = {
            "command_type": command_type,
            "target": target,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        message = Message(
            data=command_data,
            metadata=metadata,
            routing_key=f"commands.{target}.{command_type}",
        )

        return await self.publish_message(message)

    async def request_response(
        self,
        request_data: Dict[str, Any],
        target_queue: str,
        timeout_seconds: float = 30.0,
        metadata: Optional[MessageMetadata] = None,
    ) -> Optional[Message]:
        """Send a request and wait for response.

        Args:
            request_data: Request data.
            target_queue: Queue to send request to.
            timeout_seconds: Timeout for response.
            metadata: Optional message metadata.

        Returns:
            Response message or None if timeout.
        """
        # This is a default implementation that can be overridden
        # by specific broker implementations for more efficient RPC

        if metadata is None:
            metadata = MessageMetadata(
                message_id=f"{self.broker_id}_{datetime.now(timezone.utc).timestamp()}",
                sender_id=self.broker_id,
            )

        # Create temporary response queue
        response_queue = f"response_{metadata.message_id}"
        metadata.reply_to = response_queue

        # Set up response handler
        response_future = asyncio.Future()

        async def response_handler(message: Message) -> bool:
            if not response_future.done():
                response_future.set_result(message)
            return True

        # Subscribe to response queue
        response_config = ConsumerConfig(
            queue_name=response_queue, handler=response_handler, auto_ack=True
        )

        try:
            # Create temporary queue
            queue_config = QueueConfig(
                name=response_queue, auto_delete=True, exclusive=True
            )
            await self.create_queue(queue_config)

            # Subscribe to responses
            consumer_tag = await self.subscribe(response_config)

            # Send request
            request_message = Message(
                data=request_data, metadata=metadata, queue_name=target_queue
            )

            success = await self.publish_message(request_message)
            if not success:
                return None

            # Wait for response
            try:
                response = await asyncio.wait_for(
                    response_future, timeout=timeout_seconds
                )
                return response

            except asyncio.TimeoutError:
                logger.warning(
                    f"Request timeout after {timeout_seconds}s for {metadata.message_id}"
                )
                return None

        finally:
            # Clean up
            try:
                if "consumer_tag" in locals():
                    await self.unsubscribe(consumer_tag)
                await self.delete_queue(response_queue)
            except Exception as e:
                logger.error(f"Error cleaning up request-response: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get broker statistics.

        Returns:
            Dictionary containing broker statistics.
        """
        return {
            "broker_id": self.broker_id,
            "connected": self.connected,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "messages_failed": self.messages_failed,
            "active_consumers": len(self.consumers),
            "configured_queues": len(self.queues),
            "success_rate": (
                (self.messages_sent - self.messages_failed) / self.messages_sent * 100
                if self.messages_sent > 0
                else 100
            ),
        }


class InMemoryMessageBroker(MessageBroker):
    """In-memory message broker for testing and development."""

    def __init__(self, broker_id: str):
        """Initialize in-memory broker."""
        super().__init__(broker_id)
        self.message_queues: Dict[str, List[Message]] = {}
        self.consumer_tasks: Dict[str, asyncio.Task] = {}
        self.running = False

    async def connect(self) -> bool:
        """Connect to in-memory broker."""
        self.connected = True
        self.running = True
        logger.info(f"Connected in-memory broker: {self.broker_id}")

        if self.on_connect:
            await self.on_connect()

        return True

    async def disconnect(self):
        """Disconnect from in-memory broker."""
        self.running = False

        # Cancel all consumer tasks
        for task in self.consumer_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.consumer_tasks.clear()
        self.connected = False

        logger.info(f"Disconnected in-memory broker: {self.broker_id}")

        if self.on_disconnect:
            await self.on_disconnect()

    async def create_queue(self, config: QueueConfig) -> bool:
        """Create in-memory queue."""
        self.queues[config.name] = config
        self.message_queues[config.name] = []
        logger.debug(f"Created queue: {config.name}")
        return True

    async def delete_queue(self, queue_name: str) -> bool:
        """Delete in-memory queue."""
        if queue_name in self.queues:
            del self.queues[queue_name]
        if queue_name in self.message_queues:
            del self.message_queues[queue_name]
        logger.debug(f"Deleted queue: {queue_name}")
        return True

    async def publish_message(
        self, message: Message, exchange: Optional[str] = None
    ) -> bool:
        """Publish message to in-memory queue."""
        if not self.connected:
            return False

        queue_name = message.queue_name or message.routing_key

        if queue_name not in self.message_queues:
            # Auto-create queue
            config = QueueConfig(name=queue_name)
            await self.create_queue(config)

        message.status = MessageStatus.SENT
        self.message_queues[queue_name].append(message)
        self.messages_sent += 1

        logger.debug(f"Published message to queue: {queue_name}")
        return True

    async def subscribe(self, config: ConsumerConfig) -> str:
        """Subscribe to in-memory queue."""
        consumer_tag = f"consumer_{len(self.consumers)}_{config.queue_name}"
        self.consumers[consumer_tag] = config

        # Start consumer task
        task = asyncio.create_task(self._consume_messages(consumer_tag))
        self.consumer_tasks[consumer_tag] = task

        logger.debug(
            f"Subscribed to queue: {config.queue_name} with tag: {consumer_tag}"
        )
        return consumer_tag

    async def unsubscribe(self, consumer_tag: str) -> bool:
        """Unsubscribe from in-memory queue."""
        if consumer_tag in self.consumer_tasks:
            self.consumer_tasks[consumer_tag].cancel()
            try:
                await self.consumer_tasks[consumer_tag]
            except asyncio.CancelledError:
                pass
            del self.consumer_tasks[consumer_tag]

        if consumer_tag in self.consumers:
            del self.consumers[consumer_tag]

        logger.debug(f"Unsubscribed consumer: {consumer_tag}")
        return True

    async def acknowledge_message(self, message: Message) -> bool:
        """Acknowledge message (no-op for in-memory)."""
        message.status = MessageStatus.ACKNOWLEDGED
        return True

    async def reject_message(self, message: Message, requeue: bool = False) -> bool:
        """Reject message."""
        if requeue and message.queue_name in self.message_queues:
            # Re-add to front of queue
            self.message_queues[message.queue_name].insert(0, message)

        message.status = MessageStatus.FAILED
        return True

    async def _consume_messages(self, consumer_tag: str):
        """Consume messages for a specific consumer."""
        config = self.consumers[consumer_tag]
        queue_name = config.queue_name

        try:
            while self.running:
                if (
                    queue_name in self.message_queues
                    and self.message_queues[queue_name]
                ):
                    message = self.message_queues[queue_name].pop(0)
                    message.status = MessageStatus.DELIVERED
                    self.messages_received += 1

                    try:
                        # Handle message
                        if hasattr(config.handler, "handle_message"):
                            success = await config.handler.handle_message(message)
                        else:
                            success = await config.handler(message)

                        if success and config.auto_ack:
                            await self.acknowledge_message(message)

                    except Exception as e:
                        self.messages_failed += 1
                        logger.error(f"Error processing message: {e}")

                        if config.error_handler:
                            try:
                                await config.error_handler(e, message)
                            except Exception as handler_error:
                                logger.error(f"Error in error handler: {handler_error}")

                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting

        except asyncio.CancelledError:
            logger.debug(f"Consumer {consumer_tag} cancelled")
