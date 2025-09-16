"""RabbitMQ implementation of MessageBroker abstraction.

This module provides a RabbitMQ-specific implementation of the MessageBroker
interface, integrating with the existing RabbitMQ connection manager.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import pika
    import pika.adapters.asyncio_connection

    PIKA_AVAILABLE = True
except ImportError:
    PIKA_AVAILABLE = False
    pika = None

from .base import (
    ConsumerConfig,
    Message,
    MessageBroker,
    MessageMetadata,
    MessageStatus,
    QueueConfig,
    QueueType,
)
from .connection_manager import RabbitMQConfig, RabbitMQConnectionManager

logger = logging.getLogger(__name__)


class RabbitMQMessageBroker(MessageBroker):
    """RabbitMQ implementation of MessageBroker interface."""

    def __init__(
        self,
        broker_id: str,
        config: RabbitMQConfig,
        connection_manager: Optional[RabbitMQConnectionManager] = None,
    ):
        """Initialize RabbitMQ message broker.

        Args:
            broker_id: Unique identifier for this broker instance.
            config: RabbitMQ configuration.
            connection_manager: Optional existing connection manager.
        """
        super().__init__(broker_id)

        self.config = config
        self.connection_manager = connection_manager or RabbitMQConnectionManager(
            config, broker_id
        )

        # RabbitMQ specific state
        self.exchanges: Dict[str, str] = {}  # name -> type
        self.consumer_channels: Dict[str, Any] = {}  # consumer_tag -> channel
        self.consumer_callbacks: Dict[str, Any] = {}  # consumer_tag -> callback

        # Message delivery tracking
        self.pending_confirmations: Dict[int, Message] = {}
        self.delivery_tags: Dict[str, int] = {}  # message_id -> delivery_tag

        # Mock mode fallback
        self.mock_mode = not PIKA_AVAILABLE

        if self.mock_mode:
            logger.warning(
                f"RabbitMQ broker {broker_id} running in mock mode (pika not available)"
            )

    async def connect(self) -> bool:
        """Connect to RabbitMQ."""
        if self.mock_mode:
            return await self._mock_connect()

        try:
            success = await self.connection_manager.connect()
            if success:
                self.connected = True

                # Declare default exchange
                await self._declare_exchange(
                    self.config.exchange_name, self.config.exchange_type
                )

                if self.on_connect:
                    await self.on_connect()

                logger.info(f"RabbitMQ broker {self.broker_id} connected successfully")

            return success

        except Exception as e:
            logger.error(f"Failed to connect RabbitMQ broker {self.broker_id}: {e}")
            if self.on_error:
                await self.on_error(e)
            return False

    async def disconnect(self):
        """Disconnect from RabbitMQ."""
        if self.mock_mode:
            await self._mock_disconnect()
            return

        try:
            # Close all consumer channels
            for channel in self.consumer_channels.values():
                try:
                    if not channel.is_closed:
                        channel.close()
                except Exception as e:
                    logger.error(f"Error closing consumer channel: {e}")

            self.consumer_channels.clear()
            self.consumer_callbacks.clear()

            # Disconnect connection manager
            await self.connection_manager.disconnect()
            self.connected = False

            if self.on_disconnect:
                await self.on_disconnect()

            logger.info(f"RabbitMQ broker {self.broker_id} disconnected")

        except Exception as e:
            logger.error(f"Error disconnecting RabbitMQ broker {self.broker_id}: {e}")
            if self.on_error:
                await self.on_error(e)

    async def create_queue(self, config: QueueConfig) -> bool:
        """Create RabbitMQ queue."""
        if self.mock_mode:
            self.queues[config.name] = config
            return True

        if not self.connected:
            logger.error(f"Cannot create queue - broker {self.broker_id} not connected")
            return False

        try:
            channel = self.connection_manager.connection.channel()

            # Convert QueueType to RabbitMQ exchange type
            exchange_type = self._get_rabbitmq_exchange_type(config.queue_type)

            # Declare exchange if needed
            if config.queue_type != QueueType.DIRECT:
                exchange_name = f"{config.name}_exchange"
                channel.exchange_declare(
                    exchange=exchange_name,
                    exchange_type=exchange_type,
                    durable=config.durable,
                )
                self.exchanges[exchange_name] = exchange_type

            # Prepare queue arguments
            arguments = {}
            if config.max_size:
                arguments["x-max-length"] = config.max_size
            if config.ttl_seconds:
                arguments["x-message-ttl"] = config.ttl_seconds * 1000
            if config.dead_letter_queue:
                arguments["x-dead-letter-exchange"] = ""
                arguments["x-dead-letter-routing-key"] = config.dead_letter_queue

            # Declare queue
            channel.queue_declare(
                queue=config.name,
                durable=config.durable,
                exclusive=config.exclusive,
                auto_delete=config.auto_delete,
                arguments=arguments if arguments else None,
            )

            # Bind queue to exchange for topic/fanout patterns
            if config.queue_type != QueueType.DIRECT and config.routing_patterns:
                exchange_name = f"{config.name}_exchange"
                for pattern in config.routing_patterns:
                    channel.queue_bind(
                        exchange=exchange_name, queue=config.name, routing_key=pattern
                    )

            channel.close()
            self.queues[config.name] = config

            logger.debug(f"Created RabbitMQ queue: {config.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create queue {config.name}: {e}")
            if self.on_error:
                await self.on_error(e)
            return False

    async def delete_queue(self, queue_name: str) -> bool:
        """Delete RabbitMQ queue."""
        if self.mock_mode:
            self.queues.pop(queue_name, None)
            return True

        if not self.connected:
            return False

        try:
            channel = self.connection_manager.connection.channel()
            channel.queue_delete(queue=queue_name)
            channel.close()

            self.queues.pop(queue_name, None)

            logger.debug(f"Deleted RabbitMQ queue: {queue_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete queue {queue_name}: {e}")
            return False

    async def publish_message(
        self, message: Message, exchange: Optional[str] = None
    ) -> bool:
        """Publish message to RabbitMQ."""
        if self.mock_mode:
            return await self._mock_publish(message)

        if not self.connected:
            logger.error(
                f"Cannot publish message - broker {self.broker_id} not connected"
            )
            return False

        try:
            exchange_name = exchange or self.config.exchange_name
            routing_key = message.routing_key or message.queue_name

            # Prepare message body
            message_body = {
                "data": message.data,
                "metadata": message.metadata.to_dict(),
                "broker_id": self.broker_id,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }

            # Prepare message properties
            properties = pika.BasicProperties(
                content_type=message.metadata.content_type,
                delivery_mode=(
                    2
                    if self.queues.get(message.queue_name, {}).get("durable", True)
                    else 1
                ),
                priority=message.metadata.priority,
                message_id=message.metadata.message_id,
                timestamp=int(message.metadata.timestamp.timestamp()),
                correlation_id=message.metadata.correlation_id,
                reply_to=message.metadata.reply_to,
                expiration=(
                    str(message.metadata.ttl_seconds * 1000)
                    if message.metadata.ttl_seconds
                    else None
                ),
            )

            # Publish message
            channel = self.connection_manager.channel
            channel.basic_publish(
                exchange=exchange_name,
                routing_key=routing_key,
                body=json.dumps(message_body, default=str),
                properties=properties,
            )

            message.status = MessageStatus.SENT
            self.messages_sent += 1

            logger.debug(
                f"Published message {message.metadata.message_id} to {routing_key}"
            )
            return True

        except Exception as e:
            self.messages_failed += 1
            message.status = MessageStatus.FAILED
            logger.error(
                f"Failed to publish message {message.metadata.message_id}: {e}"
            )
            if self.on_error:
                await self.on_error(e)
            return False

    async def subscribe(self, config: ConsumerConfig) -> str:
        """Subscribe to RabbitMQ queue."""
        if self.mock_mode:
            return await self._mock_subscribe(config)

        if not self.connected:
            logger.error(f"Cannot subscribe - broker {self.broker_id} not connected")
            return ""

        try:
            # Create a new channel for this consumer
            channel = self.connection_manager.connection.channel()
            channel.basic_qos(prefetch_count=config.prefetch_count)

            consumer_tag = (
                config.consumer_tag
                or f"consumer_{len(self.consumers)}_{config.queue_name}"
            )

            # Create callback wrapper
            def message_callback(ch, method, properties, body):
                asyncio.create_task(
                    self._handle_message_callback(
                        consumer_tag, ch, method, properties, body
                    )
                )

            # Start consuming
            channel.basic_consume(
                queue=config.queue_name,
                on_message_callback=message_callback,
                auto_ack=config.auto_ack,
                exclusive=config.exclusive,
                consumer_tag=consumer_tag,
            )

            # Store consumer state
            self.consumers[consumer_tag] = config
            self.consumer_channels[consumer_tag] = channel
            self.consumer_callbacks[consumer_tag] = message_callback

            # Start consuming in a separate task
            asyncio.create_task(self._start_consuming(consumer_tag, channel))

            logger.debug(
                f"Subscribed to queue {config.queue_name} with tag {consumer_tag}"
            )
            return consumer_tag

        except Exception as e:
            logger.error(f"Failed to subscribe to queue {config.queue_name}: {e}")
            if self.on_error:
                await self.on_error(e)
            return ""

    async def unsubscribe(self, consumer_tag: str) -> bool:
        """Unsubscribe from RabbitMQ queue."""
        if self.mock_mode:
            return await self._mock_unsubscribe(consumer_tag)

        try:
            if consumer_tag in self.consumer_channels:
                channel = self.consumer_channels[consumer_tag]

                if not channel.is_closed:
                    channel.basic_cancel(consumer_tag)
                    channel.close()

                del self.consumer_channels[consumer_tag]

            self.consumers.pop(consumer_tag, None)
            self.consumer_callbacks.pop(consumer_tag, None)

            logger.debug(f"Unsubscribed consumer {consumer_tag}")
            return True

        except Exception as e:
            logger.error(f"Failed to unsubscribe consumer {consumer_tag}: {e}")
            return False

    async def acknowledge_message(self, message: Message) -> bool:
        """Acknowledge message in RabbitMQ."""
        if self.mock_mode:
            message.status = MessageStatus.ACKNOWLEDGED
            return True

        try:
            delivery_tag = self.delivery_tags.get(message.metadata.message_id)
            if delivery_tag:
                # Find the channel that received this message
                for consumer_tag, config in self.consumers.items():
                    if not config.auto_ack:  # Only manually ack if auto_ack is False
                        channel = self.consumer_channels.get(consumer_tag)
                        if channel and not channel.is_closed:
                            channel.basic_ack(delivery_tag=delivery_tag)
                            message.status = MessageStatus.ACKNOWLEDGED
                            return True

            return True

        except Exception as e:
            logger.error(
                f"Failed to acknowledge message {message.metadata.message_id}: {e}"
            )
            return False

    async def reject_message(self, message: Message, requeue: bool = False) -> bool:
        """Reject message in RabbitMQ."""
        if self.mock_mode:
            message.status = MessageStatus.FAILED
            return True

        try:
            delivery_tag = self.delivery_tags.get(message.metadata.message_id)
            if delivery_tag:
                # Find the channel that received this message
                for consumer_tag, config in self.consumers.items():
                    if not config.auto_ack:
                        channel = self.consumer_channels.get(consumer_tag)
                        if channel and not channel.is_closed:
                            channel.basic_reject(
                                delivery_tag=delivery_tag, requeue=requeue
                            )
                            message.status = MessageStatus.FAILED
                            return True

            return True

        except Exception as e:
            logger.error(f"Failed to reject message {message.metadata.message_id}: {e}")
            return False

    async def _declare_exchange(self, name: str, exchange_type: str):
        """Declare RabbitMQ exchange."""
        try:
            channel = self.connection_manager.connection.channel()
            channel.exchange_declare(
                exchange=name, exchange_type=exchange_type, durable=True
            )
            channel.close()
            self.exchanges[name] = exchange_type

        except Exception as e:
            logger.error(f"Failed to declare exchange {name}: {e}")
            raise

    def _get_rabbitmq_exchange_type(self, queue_type: QueueType) -> str:
        """Convert QueueType to RabbitMQ exchange type."""
        mapping = {
            QueueType.DIRECT: "direct",
            QueueType.FANOUT: "fanout",
            QueueType.TOPIC: "topic",
            QueueType.WORK_QUEUE: "direct",
        }
        return mapping.get(queue_type, "direct")

    async def _handle_message_callback(
        self, consumer_tag: str, channel: Any, method: Any, properties: Any, body: bytes
    ):
        """Handle incoming message from RabbitMQ."""
        try:
            # Parse message
            message_data = json.loads(body.decode("utf-8"))

            # Reconstruct metadata
            metadata_dict = message_data.get("metadata", {})
            metadata = MessageMetadata(
                message_id=metadata_dict.get("message_id", ""),
                timestamp=datetime.fromisoformat(
                    metadata_dict.get(
                        "timestamp", datetime.now(timezone.utc).isoformat()
                    )
                ),
                sender_id=metadata_dict.get("sender_id", ""),
                correlation_id=metadata_dict.get("correlation_id"),
                reply_to=metadata_dict.get("reply_to"),
                content_type=metadata_dict.get("content_type", "application/json"),
                priority=metadata_dict.get("priority", 0),
                ttl_seconds=metadata_dict.get("ttl_seconds"),
                retry_count=metadata_dict.get("retry_count", 0),
                max_retries=metadata_dict.get("max_retries", 3),
            )

            # Create message object
            message = Message(
                data=message_data.get("data", {}),
                metadata=metadata,
                routing_key=method.routing_key,
                queue_name=method.routing_key,
                status=MessageStatus.DELIVERED,
            )

            # Track delivery tag for manual acknowledgment
            self.delivery_tags[metadata.message_id] = method.delivery_tag
            self.messages_received += 1

            # Get consumer config
            config = self.consumers.get(consumer_tag)
            if not config:
                logger.error(f"No consumer config found for {consumer_tag}")
                return

            try:
                # Handle message
                if hasattr(config.handler, "handle_message"):
                    success = await config.handler.handle_message(message)
                else:
                    success = await config.handler(message)

                # Manual acknowledgment if needed
                if not config.auto_ack:
                    if success:
                        await self.acknowledge_message(message)
                    else:
                        await self.reject_message(message, requeue=True)

            except Exception as e:
                self.messages_failed += 1
                logger.error(f"Error handling message {metadata.message_id}: {e}")

                # Handle error
                if config.error_handler:
                    try:
                        should_ack = await config.error_handler(e, message)
                        if not config.auto_ack:
                            if should_ack:
                                await self.acknowledge_message(message)
                            else:
                                await self.reject_message(message, requeue=True)
                    except Exception as handler_error:
                        logger.error(f"Error in error handler: {handler_error}")
                        if not config.auto_ack:
                            await self.reject_message(message, requeue=False)
                else:
                    if not config.auto_ack:
                        await self.reject_message(message, requeue=False)

        except Exception as e:
            logger.error(f"Error processing RabbitMQ message: {e}")
            if not getattr(method, "auto_ack", True):
                try:
                    channel.basic_reject(
                        delivery_tag=method.delivery_tag, requeue=False
                    )
                except Exception:
                    pass

    async def _start_consuming(self, consumer_tag: str, channel: Any):
        """Start consuming messages on a channel."""
        try:
            # This runs the pika event loop for this consumer
            await asyncio.get_event_loop().run_in_executor(
                None, channel.start_consuming
            )
        except Exception as e:
            logger.error(f"Error in consumer {consumer_tag}: {e}")

    # Mock methods for testing
    async def _mock_connect(self) -> bool:
        """Mock connection for testing."""
        await asyncio.sleep(0.1)
        self.connected = True
        logger.info(f"Mock RabbitMQ broker {self.broker_id} connected")
        if self.on_connect:
            await self.on_connect()
        return True

    async def _mock_disconnect(self):
        """Mock disconnection for testing."""
        self.connected = False
        logger.info(f"Mock RabbitMQ broker {self.broker_id} disconnected")
        if self.on_disconnect:
            await self.on_disconnect()

    async def _mock_publish(self, message: Message) -> bool:
        """Mock message publishing for testing."""
        message.status = MessageStatus.SENT
        self.messages_sent += 1
        logger.debug(f"Mock published message {message.metadata.message_id}")
        return True

    async def _mock_subscribe(self, config: ConsumerConfig) -> str:
        """Mock subscription for testing."""
        consumer_tag = config.consumer_tag or f"mock_consumer_{len(self.consumers)}"
        self.consumers[consumer_tag] = config
        logger.debug(f"Mock subscribed to {config.queue_name} with tag {consumer_tag}")
        return consumer_tag

    async def _mock_unsubscribe(self, consumer_tag: str) -> bool:
        """Mock unsubscription for testing."""
        self.consumers.pop(consumer_tag, None)
        logger.debug(f"Mock unsubscribed consumer {consumer_tag}")
        return True


# Factory function for creating RabbitMQ brokers
def create_rabbitmq_broker(
    broker_id: str,
    config_dict: Dict[str, Any],
    connection_manager: Optional[RabbitMQConnectionManager] = None,
) -> RabbitMQMessageBroker:
    """Create RabbitMQ message broker from configuration.

    Args:
        broker_id: Unique broker identifier.
        config_dict: Configuration dictionary.
        connection_manager: Optional existing connection manager.

    Returns:
        Configured RabbitMQ message broker.
    """
    config = RabbitMQConfig.from_dict(config_dict)
    return RabbitMQMessageBroker(broker_id, config, connection_manager)
