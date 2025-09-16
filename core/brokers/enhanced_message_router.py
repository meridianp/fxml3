"""
Enhanced Message Router with Advanced RabbitMQ Integration for Phase 5.

This module provides intelligent message routing with priority handling,
dead letter queues, automatic failover, and comprehensive error recovery
mechanisms for the FXML4 broker integration system.

Key Features:
- Priority-based message routing with intelligent broker selection
- Dead letter queue handling for failed messages
- Message durability and recovery mechanisms
- Circuit breaker pattern for broker protection
- Comprehensive retry logic with exponential backoff
- Real-time monitoring and performance metrics
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import pika
from pika.exceptions import AMQPConnectionError

from ..core.exceptions import FXMLError
from ..core.logging import get_logger

logger = get_logger(__name__)


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Failing, rejecting requests
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


@dataclass
class MessageRoutingInfo:
    """Information about message routing decision."""

    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    routing_key: str = ""
    exchange: str = ""
    queue_name: str = ""
    priority: MessagePriority = MessagePriority.NORMAL
    queue_priority: int = 0
    broker_destination: Optional[str] = None
    routing_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    retry_count: int = 0
    max_retries: int = 3
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeadLetterQueueStatus:
    """Status of message in dead letter queue."""

    message_id: str
    is_in_dlq: bool = False
    retry_attempts: int = 0
    first_failure_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    final_error: Optional[str] = None
    recovery_eligible: bool = True


@dataclass
class CircuitBreakerStatus:
    """Circuit breaker status information."""

    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    next_retry_time: Optional[datetime] = None
    success_count_in_half_open: int = 0
    is_open: bool = False

    def __post_init__(self):
        self.is_open = self.state == CircuitBreakerState.OPEN


class EnhancedMessageRoutingError(FXMLError):
    """Exception raised for message routing errors."""

    pass


class EnhancedMessageRouter:
    """Advanced message router with intelligent routing and error handling."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize enhanced message router."""
        self.config = config

        # Connection management
        self.connection: Optional[Any] = None
        self.channels: Dict[str, Any] = {}
        self.is_connected = False

        # Routing configuration
        self.enable_dead_letter_queue = config.get("enable_dead_letter_queue", True)
        self.max_retry_attempts = config.get("max_retry_attempts", 3)
        self.retry_backoff_multiplier = config.get("retry_backoff_multiplier", 2.0)
        self.enable_priority_routing = config.get("enable_priority_routing", True)
        self.enable_message_durability = config.get("enable_message_durability", True)

        # Circuit breaker configuration
        self.circuit_breaker_threshold = config.get("circuit_breaker_threshold", 10)
        self.circuit_breaker_timeout_seconds = config.get(
            "circuit_breaker_timeout_seconds", 60
        )
        self.circuit_breaker_half_open_max_calls = config.get(
            "circuit_breaker_half_open_max_calls", 3
        )

        # State management
        self.pending_messages: Dict[str, Dict[str, Any]] = {}
        self.dead_letter_messages: Dict[str, DeadLetterQueueStatus] = {}
        self.circuit_breakers: Dict[str, CircuitBreakerStatus] = {}

        # Performance metrics
        self.routing_metrics = {
            "total_messages_routed": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "dlq_messages": 0,
            "average_routing_latency_ms": 0.0,
        }

        self.lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the enhanced message router."""
        try:
            await self._establish_connection()
            await self._setup_exchanges_and_queues()
            logger.info("Enhanced message router initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize message router: {e}")
            raise EnhancedMessageRoutingError(f"Router initialization failed: {e}")

    async def _establish_connection(self):
        """Establish RabbitMQ connection with retry logic."""
        rabbitmq_config = self.config.get("rabbitmq", {})
        host = rabbitmq_config.get("host", "localhost")
        port = rabbitmq_config.get("port", 5672)
        username = rabbitmq_config.get("username", "guest")
        password = rabbitmq_config.get("password", "guest")
        vhost = rabbitmq_config.get("vhost", "/")

        connection_params = pika.ConnectionParameters(
            host=host,
            port=port,
            virtual_host=vhost,
            credentials=pika.PlainCredentials(username, password),
            heartbeat=600,
            blocked_connection_timeout=300,
        )

        max_retries = 5
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                self.connection = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: pika.BlockingConnection(connection_params)
                )
                self.is_connected = True
                logger.info(f"Connected to RabbitMQ at {host}:{port}")
                return

            except AMQPConnectionError as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Connection attempt {attempt + 1} failed, "
                        f"retrying in {retry_delay}s"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise EnhancedMessageRoutingError(
                        f"Failed to connect after {max_retries} attempts: {e}"
                    )

    async def _setup_exchanges_and_queues(self):
        """Set up RabbitMQ exchanges and queues."""
        if not self.connection:
            raise EnhancedMessageRoutingError("No connection available")

        channel = self.connection.channel()

        # Main exchanges
        exchanges = [
            ("orders", "topic"),
            ("executions", "topic"),
            ("admin", "direct"),
            ("dlx", "direct"),  # Dead letter exchange
        ]

        for exchange_name, exchange_type in exchanges:
            channel.exchange_declare(
                exchange=exchange_name, exchange_type=exchange_type, durable=True
            )

        # Priority queues for different order types
        priority_queues = [
            ("orders.critical", 255),
            ("orders.urgent", 200),
            ("orders.high_priority", 150),
            ("orders.normal", 100),
            ("orders.low_priority", 50),
        ]

        for queue_name, priority in priority_queues:
            channel.queue_declare(
                queue=queue_name,
                durable=True,
                arguments={
                    "x-max-priority": priority,
                    "x-dead-letter-exchange": "dlx",
                    "x-dead-letter-routing-key": "failed",
                },
            )

            # Bind to orders exchange
            channel.queue_bind(
                exchange="orders", queue=queue_name, routing_key=queue_name
            )

        # Dead letter queue
        if self.enable_dead_letter_queue:
            channel.queue_declare(
                queue="failed_messages",
                durable=True,
                arguments={"x-message-ttl": 86400000},  # 24 hours TTL
            )

            channel.queue_bind(
                exchange="dlx", queue="failed_messages", routing_key="failed"
            )

        self.channels["default"] = channel
        logger.info("RabbitMQ exchanges and queues set up successfully")

    async def route_order_message(
        self, order_data: Dict[str, Any]
    ) -> MessageRoutingInfo:
        """Route order message with intelligent priority and broker selection."""
        start_time = time.time()

        try:
            # Determine message priority
            priority = self._determine_message_priority(order_data)

            # Select optimal routing
            routing_info = await self._select_optimal_routing(order_data, priority)

            # Check circuit breaker
            if await self._is_circuit_breaker_open(routing_info.broker_destination):
                raise EnhancedMessageRoutingError(
                    f"Circuit breaker open for broker {routing_info.broker_destination}"
                )

            # Publish message
            await self._publish_message(order_data, routing_info)

            # Update metrics
            routing_latency_ms = (time.time() - start_time) * 1000
            await self._update_routing_metrics(routing_latency_ms, success=True)

            logger.info(
                f"Successfully routed order {routing_info.message_id} "
                f"to {routing_info.queue_name}"
            )
            return routing_info

        except Exception as e:
            routing_latency_ms = (time.time() - start_time) * 1000
            await self._update_routing_metrics(routing_latency_ms, success=False)
            await self._handle_circuit_breaker_failure(order_data.get("broker"))
            raise EnhancedMessageRoutingError(f"Failed to route order message: {e}")

    def _determine_message_priority(
        self, order_data: Dict[str, Any]
    ) -> MessagePriority:
        """Determine message priority based on order characteristics."""
        # Check explicit priority
        if "priority" in order_data:
            priority_map = {
                "CRITICAL": MessagePriority.CRITICAL,
                "URGENT": MessagePriority.URGENT,
                "HIGH": MessagePriority.HIGH,
                "NORMAL": MessagePriority.NORMAL,
                "LOW": MessagePriority.LOW,
            }
            return priority_map.get(order_data["priority"], MessagePriority.NORMAL)

        # Determine priority by order characteristics
        quantity = float(order_data.get("quantity", 0))

        if quantity >= 10_000_000:  # $10M+
            return MessagePriority.CRITICAL
        elif quantity >= 1_000_000:  # $1M+
            return MessagePriority.HIGH
        elif quantity >= 100_000:  # $100K+
            return MessagePriority.NORMAL
        else:
            return MessagePriority.LOW

    async def _select_optimal_routing(
        self, order_data: Dict[str, Any], priority: MessagePriority
    ) -> MessageRoutingInfo:
        """Select optimal routing based on order characteristics and priority."""
        # Determine queue based on priority
        priority_queue_map = {
            MessagePriority.CRITICAL: ("orders.critical", 255),
            MessagePriority.URGENT: ("orders.urgent", 200),
            MessagePriority.HIGH: ("orders.high_priority", 150),
            MessagePriority.NORMAL: ("orders.normal", 100),
            MessagePriority.LOW: ("orders.low_priority", 50),
        }

        queue_name, queue_priority = priority_queue_map[priority]

        # Build routing key
        symbol = order_data.get("symbol", "unknown")
        order_type = order_data.get("order_type", "market")
        routing_key = f"{queue_name}.{symbol.lower()}.{order_type.lower()}"

        # Determine TTL based on order type and priority
        ttl_map = {
            MessagePriority.CRITICAL: 300,  # 5 minutes
            MessagePriority.URGENT: 600,  # 10 minutes
            MessagePriority.HIGH: 1800,  # 30 minutes
            MessagePriority.NORMAL: 3600,  # 1 hour
            MessagePriority.LOW: 7200,  # 2 hours
        }

        return MessageRoutingInfo(
            routing_key=routing_key,
            exchange="orders",
            queue_name=queue_name,
            priority=priority,
            queue_priority=queue_priority,
            broker_destination=order_data.get("broker"),
            ttl_seconds=ttl_map[priority],
            metadata={
                "symbol": symbol,
                "order_type": order_type,
                "quantity": order_data.get("quantity"),
                "user_id": order_data.get("user_id"),
            },
        )

    async def _publish_message(
        self, message_data: Dict[str, Any], routing_info: MessageRoutingInfo
    ):
        """Publish message to RabbitMQ with durability and error handling."""
        if not self.is_connected or not self.channels.get("default"):
            await self._establish_connection()
            await self._setup_exchanges_and_queues()

        channel = self.channels["default"]

        # Prepare message properties
        properties = pika.BasicProperties(
            message_id=routing_info.message_id,
            timestamp=int(time.time()),
            priority=routing_info.queue_priority,
            delivery_mode=(
                2 if self.enable_message_durability else 1
            ),  # Persistent if durable
            expiration=(
                str(routing_info.ttl_seconds * 1000)
                if routing_info.ttl_seconds
                else None
            ),
            headers={
                "retry_count": routing_info.retry_count,
                "max_retries": routing_info.max_retries,
                "broker_destination": routing_info.broker_destination,
                "priority": routing_info.priority.value,
            },
        )

        # Add message to pending tracking
        self.pending_messages[routing_info.message_id] = {
            "data": message_data,
            "routing_info": routing_info,
            "published_at": datetime.now(timezone.utc),
        }

        # Publish message
        try:
            channel.basic_publish(
                exchange=routing_info.exchange,
                routing_key=routing_info.routing_key,
                body=json.dumps(message_data),
                properties=properties,
            )

            self.routing_metrics["total_messages_routed"] += 1

        except Exception as e:
            # Remove from pending if publish failed
            self.pending_messages.pop(routing_info.message_id, None)
            raise EnhancedMessageRoutingError(f"Failed to publish message: {e}")

    async def handle_processing_failure(
        self, message_id: str, error_message: str, retry_attempt: int
    ):
        """Handle message processing failure with retry logic."""
        async with self.lock:
            pending_msg = self.pending_messages.get(message_id)
            if not pending_msg:
                logger.warning(f"No pending message found for ID {message_id}")
                return

            routing_info = pending_msg["routing_info"]
            routing_info.retry_count = retry_attempt

            # Check if max retries exceeded
            if retry_attempt >= routing_info.max_retries:
                # Move to dead letter queue
                await self._move_to_dead_letter_queue(message_id, error_message)
                self.routing_metrics["dlq_messages"] += 1
            else:
                # Calculate retry delay with exponential backoff
                delay_seconds = self.retry_backoff_multiplier**retry_attempt

                # Schedule retry
                await asyncio.sleep(delay_seconds)
                await self._retry_message(message_id, retry_attempt + 1)

            self.routing_metrics["failed_deliveries"] += 1

    async def _move_to_dead_letter_queue(self, message_id: str, error_message: str):
        """Move failed message to dead letter queue."""
        pending_msg = self.pending_messages.pop(message_id, None)
        if not pending_msg:
            return

        dlq_status = DeadLetterQueueStatus(
            message_id=message_id,
            is_in_dlq=True,
            retry_attempts=pending_msg["routing_info"].retry_count,
            first_failure_time=pending_msg.get("first_failure_time"),
            last_failure_time=datetime.now(timezone.utc),
            final_error=error_message,
        )

        self.dead_letter_messages[message_id] = dlq_status

        logger.warning(
            f"Message {message_id} moved to dead letter queue: {error_message}"
        )

    async def _retry_message(self, message_id: str, retry_attempt: int):
        """Retry failed message with updated attempt count."""
        pending_msg = self.pending_messages.get(message_id)
        if not pending_msg:
            return

        routing_info = pending_msg["routing_info"]
        routing_info.retry_count = retry_attempt

        # Update message headers and republish
        await self._publish_message(pending_msg["data"], routing_info)

        logger.info(f"Retrying message {message_id}, attempt {retry_attempt}")

    async def check_dead_letter_queue_status(
        self, message_id: str
    ) -> DeadLetterQueueStatus:
        """Check if message is in dead letter queue."""
        return self.dead_letter_messages.get(
            message_id, DeadLetterQueueStatus(message_id=message_id)
        )

    async def _is_circuit_breaker_open(self, broker_id: Optional[str]) -> bool:
        """Check if circuit breaker is open for broker."""
        if not broker_id:
            return False

        breaker = self.circuit_breakers.get(broker_id)
        if not breaker:
            return False

        # Check if timeout period has elapsed for half-open state
        if (
            breaker.state == CircuitBreakerState.OPEN
            and breaker.next_retry_time
            and datetime.now(timezone.utc) >= breaker.next_retry_time
        ):
            breaker.state = CircuitBreakerState.HALF_OPEN
            breaker.success_count_in_half_open = 0

        return breaker.state == CircuitBreakerState.OPEN

    async def _handle_circuit_breaker_failure(self, broker_id: Optional[str]):
        """Handle circuit breaker failure for broker."""
        if not broker_id:
            return

        async with self.lock:
            if broker_id not in self.circuit_breakers:
                self.circuit_breakers[broker_id] = CircuitBreakerStatus()

            breaker = self.circuit_breakers[broker_id]
            breaker.failure_count += 1
            breaker.last_failure_time = datetime.now(timezone.utc)

            # Open circuit breaker if threshold exceeded
            if breaker.failure_count >= self.circuit_breaker_threshold:
                breaker.state = CircuitBreakerState.OPEN
                breaker.next_retry_time = datetime.now(timezone.utc) + timedelta(
                    seconds=self.circuit_breaker_timeout_seconds
                )
                breaker.is_open = True

                logger.warning(f"Circuit breaker OPEN for broker {broker_id}")

    async def _update_routing_metrics(self, latency_ms: float, success: bool):
        """Update routing performance metrics."""
        if success:
            self.routing_metrics["successful_deliveries"] += 1

        # Update average latency
        total_messages = self.routing_metrics["total_messages_routed"]
        if total_messages > 0:
            current_avg = self.routing_metrics["average_routing_latency_ms"]
            self.routing_metrics["average_routing_latency_ms"] = (
                current_avg * (total_messages - 1) + latency_ms
            ) / total_messages

    async def simulate_system_restart(self):
        """Simulate system restart for testing recovery."""
        # Close connections
        if self.connection and not self.connection.is_closed:
            self.connection.close()

        self.is_connected = False
        self.channels.clear()

        # Reinitialize
        await asyncio.sleep(1)  # Simulate restart delay
        await self.initialize()

    async def recover_pending_messages(self) -> List[Dict[str, Any]]:
        """Recover pending messages after system restart."""
        if not self.enable_message_durability:
            return []

        recovered_messages = []

        # In real implementation, this would query RabbitMQ for unacknowledged messages
        # For now, return messages that were durably stored
        for message_id, pending_msg in self.pending_messages.items():
            if pending_msg.get("durable", False):
                recovered_messages.append(pending_msg["data"])

        logger.info(f"Recovered {len(recovered_messages)} pending messages")
        return recovered_messages

    async def get_routing_metrics(self) -> Dict[str, Any]:
        """Get routing performance metrics."""
        return {
            **self.routing_metrics,
            "pending_messages": len(self.pending_messages),
            "dlq_messages_count": len(self.dead_letter_messages),
            "circuit_breakers": {
                broker_id: {
                    "state": breaker.state.value,
                    "failure_count": breaker.failure_count,
                    "is_open": breaker.is_open,
                }
                for broker_id, breaker in self.circuit_breakers.items()
            },
        }

    async def shutdown(self):
        """Gracefully shutdown the message router."""
        try:
            # Close channels
            for channel in self.channels.values():
                if hasattr(channel, "close") and not channel.is_closed:
                    channel.close()

            # Close connection
            if self.connection and not self.connection.is_closed:
                self.connection.close()

            self.is_connected = False
            logger.info("Enhanced message router shut down successfully")

        except Exception as e:
            logger.error(f"Error during message router shutdown: {e}")


# Factory function
def create_enhanced_message_router(config: Dict[str, Any]) -> EnhancedMessageRouter:
    """Create enhanced message router instance."""
    return EnhancedMessageRouter(config)
