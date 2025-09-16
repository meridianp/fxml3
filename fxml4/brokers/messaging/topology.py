"""RabbitMQ Topology for Broker Message Routing.

This module defines the message queue topology for broker abstraction,
including exchanges, queues, and routing keys for FIX message flow.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set

import pika
from pika.exceptions import ChannelClosed, ConnectionClosed

logger = logging.getLogger(__name__)


class ExchangeType(Enum):
    """RabbitMQ exchange types."""

    DIRECT = "direct"
    TOPIC = "topic"
    FANOUT = "fanout"
    HEADERS = "headers"


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 10


@dataclass
class ExchangeConfig:
    """Configuration for RabbitMQ exchange."""

    name: str
    type: ExchangeType
    durable: bool = True
    auto_delete: bool = False
    arguments: Optional[Dict] = None


@dataclass
class QueueConfig:
    """Configuration for RabbitMQ queue."""

    name: str
    durable: bool = True
    exclusive: bool = False
    auto_delete: bool = False
    arguments: Optional[Dict] = None
    max_length: Optional[int] = None
    message_ttl: Optional[int] = None
    max_priority: int = 10


@dataclass
class BindingConfig:
    """Configuration for queue-to-exchange binding."""

    queue: str
    exchange: str
    routing_key: str
    arguments: Optional[Dict] = None


class BrokerMessageTopology:
    """Manages RabbitMQ topology for broker message routing.

    This class defines and manages the complete message routing topology
    for the FIX-based broker abstraction system.

    Topology Design:

    1. Order Flow (Request/Response):
       - orders.outbound -> [broker adapters] -> broker-specific queues
       - broker-specific queues -> orders.executions -> execution handlers

    2. Market Data Flow:
       - market.data.requests -> broker adapters
       - broker adapters -> market.data.feed -> subscribers

    3. Administrative Flow:
       - admin.commands -> broker adapters
       - broker adapters -> admin.status -> monitoring

    4. Dead Letter Handling:
       - All queues have DLX configured for failed message handling
    """

    def __init__(self, connection_params: pika.ConnectionParameters):
        """Initialize topology manager.

        Args:
            connection_params: RabbitMQ connection parameters.
        """
        self.connection_params = connection_params
        self.connection = None
        self.channel = None

        # Define topology configuration
        self.exchanges = self._define_exchanges()
        self.queues = self._define_queues()
        self.bindings = self._define_bindings()

    def _define_exchanges(self) -> List[ExchangeConfig]:
        """Define all exchanges in the topology."""
        return [
            # Order management exchanges
            ExchangeConfig(
                name="orders.outbound",
                type=ExchangeType.TOPIC,
                durable=True,
                arguments={"description": "Outbound order routing to brokers"},
            ),
            ExchangeConfig(
                name="orders.executions",
                type=ExchangeType.TOPIC,
                durable=True,
                arguments={"description": "Execution reports from brokers"},
            ),
            # Market data exchanges
            ExchangeConfig(
                name="market.data.requests",
                type=ExchangeType.TOPIC,
                durable=True,
                arguments={"description": "Market data subscription requests"},
            ),
            ExchangeConfig(
                name="market.data.feed",
                type=ExchangeType.TOPIC,
                durable=True,
                arguments={"description": "Real-time market data distribution"},
            ),
            # Administrative exchanges
            ExchangeConfig(
                name="admin.commands",
                type=ExchangeType.DIRECT,
                durable=True,
                arguments={"description": "Administrative commands to brokers"},
            ),
            ExchangeConfig(
                name="admin.status",
                type=ExchangeType.FANOUT,
                durable=True,
                arguments={"description": "Broker status broadcasts"},
            ),
            # Dead letter exchange
            ExchangeConfig(
                name="dlx.failed.messages",
                type=ExchangeType.DIRECT,
                durable=True,
                arguments={"description": "Dead letter exchange for failed messages"},
            ),
            # High priority exchange for urgent messages
            ExchangeConfig(
                name="priority.urgent",
                type=ExchangeType.DIRECT,
                durable=True,
                arguments={"description": "High priority message routing"},
            ),
        ]

    def _define_queues(self) -> List[QueueConfig]:
        """Define all queues in the topology."""
        # Common queue arguments for DLX
        dlx_args = {
            "x-dead-letter-exchange": "dlx.failed.messages",
            "x-dead-letter-routing-key": "failed",
        }

        return [
            # Broker-specific order queues
            QueueConfig(
                name="orders.ib.inbound",
                durable=True,
                arguments={**dlx_args, "description": "Interactive Brokers orders"},
                max_length=10000,
                message_ttl=300000,  # 5 minutes
                max_priority=10,
            ),
            QueueConfig(
                name="orders.manual.inbound",
                durable=True,
                arguments={**dlx_args, "description": "Manual execution orders"},
                max_length=1000,
                message_ttl=3600000,  # 1 hour for manual review
                max_priority=10,
            ),
            QueueConfig(
                name="orders.fxcm.inbound",
                durable=True,
                arguments={**dlx_args, "description": "FXCM ForexConnect orders"},
                max_length=5000,
                message_ttl=300000,
                max_priority=10,
            ),
            QueueConfig(
                name="orders.fix.inbound",
                durable=True,
                arguments={**dlx_args, "description": "Native FIX broker orders"},
                max_length=10000,
                message_ttl=300000,
                max_priority=10,
            ),
            # Execution report queues
            QueueConfig(
                name="executions.all",
                durable=True,
                arguments={**dlx_args, "description": "All execution reports"},
                max_length=50000,
                message_ttl=86400000,  # 24 hours
                max_priority=10,
            ),
            QueueConfig(
                name="executions.fills",
                durable=True,
                arguments={**dlx_args, "description": "Fill executions only"},
                max_length=20000,
                message_ttl=86400000,
                max_priority=10,
            ),
            QueueConfig(
                name="executions.rejections",
                durable=True,
                arguments={**dlx_args, "description": "Order rejections"},
                max_length=5000,
                message_ttl=86400000,
                max_priority=10,
            ),
            # Market data queues
            QueueConfig(
                name="market.data.ib",
                durable=True,
                arguments={**dlx_args, "description": "IB market data"},
                max_length=100000,
                message_ttl=60000,  # 1 minute for real-time data
                max_priority=5,
            ),
            QueueConfig(
                name="market.data.fxcm",
                durable=True,
                arguments={**dlx_args, "description": "FXCM market data"},
                max_length=100000,
                message_ttl=60000,
                max_priority=5,
            ),
            QueueConfig(
                name="market.data.aggregated",
                durable=True,
                arguments={**dlx_args, "description": "Aggregated market data feed"},
                max_length=200000,
                message_ttl=60000,
                max_priority=5,
            ),
            # Administrative queues
            QueueConfig(
                name="admin.ib.commands",
                durable=True,
                arguments={**dlx_args, "description": "IB admin commands"},
                max_length=1000,
                message_ttl=3600000,
                max_priority=8,
            ),
            QueueConfig(
                name="admin.manual.commands",
                durable=True,
                arguments={**dlx_args, "description": "Manual broker commands"},
                max_length=1000,
                message_ttl=3600000,
                max_priority=8,
            ),
            QueueConfig(
                name="admin.fxcm.commands",
                durable=True,
                arguments={**dlx_args, "description": "FXCM admin commands"},
                max_length=1000,
                message_ttl=3600000,
                max_priority=8,
            ),
            QueueConfig(
                name="admin.fix.commands",
                durable=True,
                arguments={**dlx_args, "description": "FIX broker commands"},
                max_length=1000,
                message_ttl=3600000,
                max_priority=8,
            ),
            QueueConfig(
                name="admin.status.all",
                durable=True,
                arguments={**dlx_args, "description": "All broker status updates"},
                max_length=10000,
                message_ttl=3600000,
                max_priority=5,
            ),
            # Dead letter queues
            QueueConfig(
                name="dlq.failed.messages",
                durable=True,
                arguments={"description": "Dead letter queue for failed messages"},
                max_length=50000,
                message_ttl=604800000,  # 7 days
                max_priority=1,
            ),
            # High priority queues
            QueueConfig(
                name="priority.urgent.orders",
                durable=True,
                arguments={**dlx_args, "description": "Urgent order processing"},
                max_length=1000,
                message_ttl=30000,  # 30 seconds
                max_priority=10,
            ),
            QueueConfig(
                name="priority.urgent.admin",
                durable=True,
                arguments={**dlx_args, "description": "Urgent admin commands"},
                max_length=100,
                message_ttl=30000,
                max_priority=10,
            ),
        ]

    def _define_bindings(self) -> List[BindingConfig]:
        """Define all queue-to-exchange bindings."""
        return [
            # Order routing bindings
            BindingConfig("orders.ib.inbound", "orders.outbound", "orders.ib"),
            BindingConfig("orders.ib.inbound", "orders.outbound", "orders.ib.*"),
            BindingConfig("orders.manual.inbound", "orders.outbound", "orders.manual"),
            BindingConfig(
                "orders.manual.inbound", "orders.outbound", "orders.manual.*"
            ),
            BindingConfig("orders.fxcm.inbound", "orders.outbound", "orders.fxcm"),
            BindingConfig("orders.fxcm.inbound", "orders.outbound", "orders.fxcm.*"),
            BindingConfig("orders.fix.inbound", "orders.outbound", "orders.fix"),
            BindingConfig("orders.fix.inbound", "orders.outbound", "orders.fix.*"),
            # Execution report bindings
            BindingConfig("executions.all", "orders.executions", "executions.*"),
            BindingConfig("executions.fills", "orders.executions", "executions.fill"),
            BindingConfig(
                "executions.fills", "orders.executions", "executions.partial_fill"
            ),
            BindingConfig(
                "executions.rejections", "orders.executions", "executions.reject"
            ),
            BindingConfig(
                "executions.rejections", "orders.executions", "executions.cancel_reject"
            ),
            # Market data bindings
            BindingConfig("market.data.ib", "market.data.feed", "market.ib.*"),
            BindingConfig("market.data.fxcm", "market.data.feed", "market.fxcm.*"),
            BindingConfig(
                "market.data.aggregated", "market.data.feed", "market.aggregated.*"
            ),
            # Administrative bindings
            BindingConfig("admin.ib.commands", "admin.commands", "ib"),
            BindingConfig("admin.manual.commands", "admin.commands", "manual"),
            BindingConfig("admin.fxcm.commands", "admin.commands", "fxcm"),
            BindingConfig("admin.fix.commands", "admin.commands", "fix"),
            BindingConfig("admin.status.all", "admin.status", ""),  # Fanout binding
            # Dead letter bindings
            BindingConfig("dlq.failed.messages", "dlx.failed.messages", "failed"),
            # Priority bindings
            BindingConfig("priority.urgent.orders", "priority.urgent", "orders"),
            BindingConfig("priority.urgent.admin", "priority.urgent", "admin"),
        ]

    def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        try:
            self.connection = pika.BlockingConnection(self.connection_params)
            self.channel = self.connection.channel()
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error("Failed to connect to RabbitMQ: %s", e)
            raise

    def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.warning("Error during disconnect: %s", e)

    def setup_topology(self) -> None:
        """Create all exchanges, queues, and bindings."""
        if not self.channel:
            raise RuntimeError("Must connect before setting up topology")

        try:
            # Create exchanges
            logger.info("Creating exchanges...")
            for exchange in self.exchanges:
                self.channel.exchange_declare(
                    exchange=exchange.name,
                    exchange_type=exchange.type.value,
                    durable=exchange.durable,
                    auto_delete=exchange.auto_delete,
                    arguments=exchange.arguments,
                )
                logger.debug("Created exchange: %s", exchange.name)

            # Create queues
            logger.info("Creating queues...")
            for queue in self.queues:
                arguments = queue.arguments or {}
                if queue.max_length:
                    arguments["x-max-length"] = queue.max_length
                if queue.message_ttl:
                    arguments["x-message-ttl"] = queue.message_ttl
                if queue.max_priority:
                    arguments["x-max-priority"] = queue.max_priority

                self.channel.queue_declare(
                    queue=queue.name,
                    durable=queue.durable,
                    exclusive=queue.exclusive,
                    auto_delete=queue.auto_delete,
                    arguments=arguments,
                )
                logger.debug("Created queue: %s", queue.name)

            # Create bindings
            logger.info("Creating bindings...")
            for binding in self.bindings:
                self.channel.queue_bind(
                    exchange=binding.exchange,
                    queue=binding.queue,
                    routing_key=binding.routing_key,
                    arguments=binding.arguments,
                )
                logger.debug(
                    "Created binding: %s -> %s [%s]",
                    binding.exchange,
                    binding.queue,
                    binding.routing_key,
                )

            logger.info("Topology setup completed successfully")

        except Exception as e:
            logger.error("Failed to setup topology: %s", e)
            raise

    def teardown_topology(self) -> None:
        """Remove all topology elements (for testing)."""
        if not self.channel:
            raise RuntimeError("Must connect before tearing down topology")

        try:
            # Delete queues
            for queue in self.queues:
                try:
                    self.channel.queue_delete(queue.name)
                    logger.debug("Deleted queue: %s", queue.name)
                except Exception as e:
                    logger.warning("Failed to delete queue %s: %s", queue.name, e)

            # Delete exchanges
            for exchange in self.exchanges:
                try:
                    self.channel.exchange_delete(exchange.name)
                    logger.debug("Deleted exchange: %s", exchange.name)
                except Exception as e:
                    logger.warning("Failed to delete exchange %s: %s", exchange.name, e)

            logger.info("Topology teardown completed")

        except Exception as e:
            logger.error("Failed to teardown topology: %s", e)
            raise

    def get_queue_info(self, queue_name: str) -> Optional[Dict]:
        """Get information about a specific queue.

        Args:
            queue_name: Name of the queue to inspect.

        Returns:
            Queue information dictionary or None if not found.
        """
        if not self.channel:
            raise RuntimeError("Must connect before getting queue info")

        try:
            method = self.channel.queue_declare(queue_name, passive=True)
            return {
                "name": queue_name,
                "message_count": method.method.message_count,
                "consumer_count": method.method.consumer_count,
            }
        except Exception as e:
            logger.warning("Failed to get queue info for %s: %s", queue_name, e)
            return None

    def purge_queue(self, queue_name: str) -> int:
        """Purge all messages from a queue.

        Args:
            queue_name: Name of the queue to purge.

        Returns:
            Number of messages purged.
        """
        if not self.channel:
            raise RuntimeError("Must connect before purging queue")

        try:
            method = self.channel.queue_purge(queue_name)
            purged_count = method.method.message_count
            logger.info("Purged %d messages from queue %s", purged_count, queue_name)
            return purged_count
        except Exception as e:
            logger.error("Failed to purge queue %s: %s", queue_name, e)
            raise

    def get_broker_queue_name(self, broker_type: str) -> str:
        """Get the inbound queue name for a specific broker type.

        Args:
            broker_type: Type of broker (ib, manual, fxcm, fix).

        Returns:
            Queue name for the broker.
        """
        return f"orders.{broker_type}.inbound"

    def get_routing_key(self, broker_type: str, message_type: str = "") -> str:
        """Get the routing key for a broker and message type.

        Args:
            broker_type: Type of broker (ib, manual, fxcm, fix).
            message_type: Optional message type suffix.

        Returns:
            Routing key string.
        """
        if message_type:
            return f"orders.{broker_type}.{message_type}"
        return f"orders.{broker_type}"

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
