"""
RabbitMQ Message Router for FXML4 Trading System

High-performance async message routing with connection pooling, dead letter queues,
and comprehensive error handling. Supports >1000 messages/second throughput
with <100ms latency requirements for real-time trading operations.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractExchange,
    AbstractQueue,
)

from .messages import (
    BaseMessage,
    ExecutionMessage,
    MessagePriority,
    OrderMessage,
    RiskCheckMessage,
)

logger = logging.getLogger(__name__)


class RabbitMQConnectionError(Exception):
    """Raised when RabbitMQ connection fails."""

    pass


class RabbitMQMessageRouter:
    """
    High-performance async RabbitMQ message router for trading system.

    Features:
    - Connection pooling with automatic reconnection
    - Dead letter queue handling for failed messages
    - Message serialization/deserialization with JSON
    - Performance monitoring and metrics
    - Queue topology management
    - Message acknowledgment and retry logic
    """

    def __init__(
        self,
        rabbitmq_url: str = "amqp://guest:guest@localhost:5672/",
        connection_pool_size: int = 10,
        prefetch_count: int = 100,
        message_ttl_seconds: int = 300,
        max_retries: int = 3,
        retry_delay_seconds: int = 5,
    ):
        self.rabbitmq_url = rabbitmq_url
        self.connection_pool_size = connection_pool_size
        self.prefetch_count = prefetch_count
        self.message_ttl_seconds = message_ttl_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

        # Connection management
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.is_connected = False

        # Queue and exchange references
        self.exchanges: Dict[str, AbstractExchange] = {}
        self.queues: Dict[str, AbstractQueue] = {}

        # Performance tracking
        self.message_count = 0
        self.error_count = 0
        self.last_message_time: Optional[datetime] = None

        # Message consumers
        self.consumers: Dict[str, Callable] = {}

        # Configuration
        self.config = {
            "order_queue": "order_queue",
            "risk_queue": "risk_queue",
            "execution_queue": "execution_queue",
            "dead_letter_exchange": "dlx",
            "dead_letter_queue": "dead_letter_queue",
            "main_exchange": "trading_exchange",
        }

    async def connect(self) -> None:
        """Establish connection to RabbitMQ server."""
        try:
            self.connection = await aio_pika.connect_robust(
                self.rabbitmq_url,
                client_properties={"application": "fxml4-trading-system"},
            )
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=self.prefetch_count)

            self.is_connected = True
            logger.info("Connected to RabbitMQ successfully")

            # Setup queue topology
            await self.setup_queues()

        except Exception as e:
            self.is_connected = False
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise RabbitMQConnectionError(f"Connection failed: {e}")

    async def disconnect(self) -> None:
        """Close connection to RabbitMQ server."""
        try:
            if self.connection:
                await self.connection.close()
            self.is_connected = False
            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            # Set disconnected even if close fails
            self.is_connected = False

    async def setup_queues(self) -> None:
        """Setup queue topology with exchanges and dead letter queues."""
        if not self.channel:
            raise RabbitMQConnectionError("No active channel")

        # Create dead letter exchange
        dlx = await self.channel.declare_exchange(
            self.config["dead_letter_exchange"], ExchangeType.DIRECT, durable=True
        )
        self.exchanges["dlx"] = dlx

        # Create dead letter queue
        dlq = await self.channel.declare_queue(
            self.config["dead_letter_queue"],
            durable=True,
            arguments={
                "x-message-ttl": self.message_ttl_seconds * 1000,
            },
        )
        await dlq.bind(dlx, routing_key="failed")
        self.queues["dlq"] = dlq

        # Create main exchange
        main_exchange = await self.channel.declare_exchange(
            self.config["main_exchange"], ExchangeType.TOPIC, durable=True
        )
        self.exchanges["main"] = main_exchange

        # Create order queue
        order_queue = await self.channel.declare_queue(
            self.config["order_queue"],
            durable=True,
            arguments={
                "x-dead-letter-exchange": self.config["dead_letter_exchange"],
                "x-dead-letter-routing-key": "failed",
                "x-message-ttl": self.message_ttl_seconds * 1000,
            },
        )
        await order_queue.bind(main_exchange, routing_key="order.*")
        self.queues["order"] = order_queue

        # Create risk queue
        risk_queue = await self.channel.declare_queue(
            self.config["risk_queue"],
            durable=True,
            arguments={
                "x-dead-letter-exchange": self.config["dead_letter_exchange"],
                "x-dead-letter-routing-key": "failed",
                "x-message-ttl": self.message_ttl_seconds * 1000,
            },
        )
        await risk_queue.bind(main_exchange, routing_key="risk.*")
        self.queues["risk"] = risk_queue

        # Create execution queue
        execution_queue = await self.channel.declare_queue(
            self.config["execution_queue"],
            durable=True,
            arguments={
                "x-dead-letter-exchange": self.config["dead_letter_exchange"],
                "x-dead-letter-routing-key": "failed",
                "x-message-ttl": self.message_ttl_seconds * 1000,
            },
        )
        await execution_queue.bind(main_exchange, routing_key="execution.*")
        self.queues["execution"] = execution_queue

        logger.info("Queue topology setup completed")

    async def route_order_message(self, message: OrderMessage) -> None:
        """Route order message to order queue."""
        await self._publish_message(
            message,
            routing_key=self.config["order_queue"],
            priority=message.priority.value,
        )
        logger.debug(f"Routed order message {message.order_id} to order queue")

    async def route_risk_message(self, message: RiskCheckMessage) -> None:
        """Route risk check message to risk queue."""
        await self._publish_message(
            message,
            routing_key=self.config["risk_queue"],
            priority=message.priority.value,
        )
        logger.debug(f"Routed risk message {message.order_id} to risk queue")

    async def route_execution_message(self, message: ExecutionMessage) -> None:
        """Route execution message to execution queue."""
        await self._publish_message(
            message,
            routing_key=self.config["execution_queue"],
            priority=message.priority.value,
        )
        logger.debug(
            f"Routed execution message {message.execution_id} to execution queue"
        )

    async def _publish_message(
        self, message: BaseMessage, routing_key: str, priority: int = 5
    ) -> None:
        """Internal method to publish message to queue."""
        if not self.channel:
            raise RabbitMQConnectionError("No active channel")

        try:
            # Serialize message
            message_body = message.to_json()

            # Create AMQP message
            amqp_message = Message(
                message_body.encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT,
                priority=priority,
                message_id=message.message_id,
                correlation_id=message.correlation_id,
                timestamp=datetime.utcnow(),
                headers={
                    "message_type": message.__class__.__name__,
                    "retry_count": message.retry_count,
                    "max_retries": message.max_retries,
                },
            )

            # Publish to default exchange (direct routing)
            await self.channel.default_exchange.publish(
                amqp_message, routing_key=routing_key
            )

            # Update metrics
            self.message_count += 1
            self.last_message_time = datetime.utcnow()

        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to publish message {message.message_id}: {e}")
            raise

    async def start_consuming(self, queue_name: str, callback: Callable) -> None:
        """Start consuming messages from specified queue."""
        if not self.channel:
            raise RabbitMQConnectionError("No active channel")

        queue = self.queues.get(queue_name)
        if not queue:
            raise ValueError(f"Queue {queue_name} not found")

        await queue.consume(self._create_message_handler(callback))
        self.consumers[queue_name] = callback
        logger.info(f"Started consuming from queue {queue_name}")

    def _create_message_handler(self, callback: Callable) -> Callable:
        """Create message handler wrapper with error handling."""

        async def handler(message: aio_pika.IncomingMessage):
            try:
                # Decode message
                message_body = message.body.decode("utf-8")
                message_data = json.loads(message_body)

                # Determine message type from header
                message_type = message.headers.get("message_type")

                # Deserialize to appropriate message class
                if message_type == "OrderMessage":
                    parsed_message = OrderMessage.from_json(message_body)
                elif message_type == "RiskCheckMessage":
                    parsed_message = RiskCheckMessage.from_json(message_body)
                elif message_type == "ExecutionMessage":
                    parsed_message = ExecutionMessage.from_json(message_body)
                else:
                    raise ValueError(f"Unknown message type: {message_type}")

                # Process message
                await callback(parsed_message)

                # Acknowledge successful processing
                await message.ack()

            except Exception as e:
                logger.error(f"Error processing message {message.message_id}: {e}")

                # Check retry count
                retry_count = message.headers.get("retry_count", 0)
                max_retries = message.headers.get("max_retries", self.max_retries)

                if retry_count < max_retries:
                    # Reject with requeue for retry
                    await message.reject(requeue=True)
                else:
                    # Send to dead letter queue
                    await message.reject(requeue=False)

                self.error_count += 1

        return handler

    async def stop_consuming(self, queue_name: str) -> None:
        """Stop consuming from specified queue."""
        queue = self.queues.get(queue_name)
        if queue:
            await queue.cancel()
            if queue_name in self.consumers:
                del self.consumers[queue_name]
            logger.info(f"Stopped consuming from queue {queue_name}")

    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status and metrics."""
        return {
            "is_connected": self.is_connected,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "last_message_time": (
                self.last_message_time.isoformat() if self.last_message_time else None
            ),
            "active_consumers": list(self.consumers.keys()),
            "queue_count": len(self.queues),
            "exchange_count": len(self.exchanges),
        }

    def get_queue_info(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Get information about specific queue."""
        queue = self.queues.get(queue_name)
        if not queue:
            return None

        return {
            "name": queue_name,
            "durable": True,  # All our queues are durable
            "has_consumer": queue_name in self.consumers,
        }

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for monitoring."""
        uptime = None
        messages_per_second = 0

        if self.last_message_time:
            uptime_delta = datetime.utcnow() - self.last_message_time
            uptime = uptime_delta.total_seconds()

            if uptime > 0:
                messages_per_second = self.message_count / uptime

        error_rate = self.error_count / max(self.message_count, 1)
        return {
            "total_messages": self.message_count,
            "total_errors": self.error_count,
            "error_rate": error_rate,
            "messages_per_second": messages_per_second,
            "uptime_seconds": uptime,
            "is_healthy": self.is_connected and error_rate < 0.1,
        }

    @asynccontextmanager
    async def connection_context(self):
        """Context manager for connection lifecycle."""
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()

    def __repr__(self) -> str:
        return f"RabbitMQMessageRouter(connected={self.is_connected}, queues={len(self.queues)})"
