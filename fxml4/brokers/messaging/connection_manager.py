"""RabbitMQ Connection Manager.

This module provides a centralized connection management system for RabbitMQ
operations, eliminating code duplication across broker adapters.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

try:
    import pika
    import pika.adapters.asyncio_connection

    PIKA_AVAILABLE = True
except ImportError:
    PIKA_AVAILABLE = False
    pika = None

logger = logging.getLogger(__name__)


@dataclass
class RabbitMQConfig:
    """RabbitMQ connection configuration."""

    host: str = "localhost"
    port: int = 5672
    virtual_host: str = "/"
    username: str = "guest"
    password: str = "guest"

    # Connection settings
    heartbeat: int = 600
    blocked_connection_timeout: int = 300
    socket_timeout: int = 10

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0

    # Exchange settings
    exchange_name: str = "broker_exchange"
    exchange_type: str = "topic"
    exchange_durable: bool = True

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "RabbitMQConfig":
        """Create configuration from dictionary."""
        rabbitmq_config = config.get("rabbitmq", {})

        return cls(
            host=rabbitmq_config.get("host", "localhost"),
            port=rabbitmq_config.get("port", 5672),
            virtual_host=rabbitmq_config.get("virtual_host", "/"),
            username=rabbitmq_config.get("username", "guest"),
            password=rabbitmq_config.get("password", "guest"),
            heartbeat=rabbitmq_config.get("heartbeat", 600),
            blocked_connection_timeout=rabbitmq_config.get(
                "blocked_connection_timeout", 300
            ),
            socket_timeout=rabbitmq_config.get("socket_timeout", 10),
            exchange_name=rabbitmq_config.get("exchange_name", "broker_exchange"),
            exchange_type=rabbitmq_config.get("exchange_type", "topic"),
            exchange_durable=rabbitmq_config.get("exchange_durable", True),
        )


class RabbitMQConnectionManager:
    """Centralized RabbitMQ connection management."""

    def __init__(self, config: RabbitMQConfig, adapter_id: str):
        """Initialize connection manager.

        Args:
            config: RabbitMQ configuration.
            adapter_id: Unique identifier for the adapter.
        """
        self.config = config
        self.adapter_id = adapter_id

        # Connection state
        self.connection: Optional[
            pika.adapters.asyncio_connection.AsyncioConnection
        ] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.connected = False
        self.connecting = False

        # Connection tracking
        self.connection_attempts = 0
        self.last_connection_attempt: Optional[datetime] = None
        self.connected_at: Optional[datetime] = None

        # Callbacks
        self.on_connection_open: Optional[Callable] = None
        self.on_connection_closed: Optional[Callable] = None
        self.on_connection_error: Optional[Callable] = None

        # Mock mode for testing
        self.mock_mode = not PIKA_AVAILABLE

        if self.mock_mode:
            logger.warning(
                f"RabbitMQ manager for {adapter_id} running in mock mode (pika not available)"
            )

        logger.info(f"Initialized RabbitMQ connection manager for {adapter_id}")

    async def connect(self) -> bool:
        """Establish connection to RabbitMQ server.

        Returns:
            True if connection successful, False otherwise.
        """
        if self.connected:
            return True

        if self.connecting:
            logger.debug(f"Connection already in progress for {self.adapter_id}")
            return False

        if self.mock_mode:
            return await self._mock_connect()

        self.connecting = True
        self.connection_attempts += 1
        self.last_connection_attempt = datetime.now(timezone.utc)

        try:
            # Create connection parameters
            credentials = pika.PlainCredentials(
                self.config.username, self.config.password
            )

            parameters = pika.ConnectionParameters(
                host=self.config.host,
                port=self.config.port,
                virtual_host=self.config.virtual_host,
                credentials=credentials,
                heartbeat=self.config.heartbeat,
                blocked_connection_timeout=self.config.blocked_connection_timeout,
                socket_timeout=self.config.socket_timeout,
            )

            # Establish connection
            self.connection = await asyncio.get_event_loop().run_in_executor(
                None, pika.BlockingConnection, parameters
            )

            # Create channel
            self.channel = self.connection.channel()

            # Declare exchange
            self.channel.exchange_declare(
                exchange=self.config.exchange_name,
                exchange_type=self.config.exchange_type,
                durable=self.config.exchange_durable,
            )

            self.connected = True
            self.connecting = False
            self.connected_at = datetime.now(timezone.utc)

            logger.info(
                f"Successfully connected {self.adapter_id} to RabbitMQ at {self.config.host}:{self.config.port}"
            )

            if self.on_connection_open:
                await self.on_connection_open()

            return True

        except Exception as e:
            self.connecting = False
            self.connected = False

            logger.error(f"Failed to connect {self.adapter_id} to RabbitMQ: {e}")

            if self.on_connection_error:
                await self.on_connection_error(e)

            return False

    async def disconnect(self):
        """Close RabbitMQ connection."""
        if self.mock_mode:
            await self._mock_disconnect()
            return

        if not self.connected:
            return

        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()

            if self.connection and not self.connection.is_closed:
                self.connection.close()

        except Exception as e:
            logger.error(f"Error during {self.adapter_id} RabbitMQ disconnect: {e}")

        finally:
            self.connected = False
            self.connection = None
            self.channel = None

            logger.info(f"Disconnected {self.adapter_id} from RabbitMQ")

            if self.on_connection_closed:
                await self.on_connection_closed()

    async def publish_message(
        self, message: Dict[str, Any], routing_key: str, exchange: Optional[str] = None
    ) -> bool:
        """Publish message to RabbitMQ.

        Args:
            message: Message data to publish.
            routing_key: Routing key for message.
            exchange: Exchange name (uses default if None).

        Returns:
            True if message published successfully.
        """
        if self.mock_mode:
            return await self._mock_publish(message, routing_key)

        if not self.connected or not self.channel:
            logger.warning(
                f"Cannot publish message - {self.adapter_id} not connected to RabbitMQ"
            )
            return False

        try:
            exchange_name = exchange or self.config.exchange_name

            # Add adapter metadata
            enriched_message = {
                **message,
                "adapter_id": self.adapter_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message_id": f"{self.adapter_id}_{datetime.now(timezone.utc).timestamp()}",
            }

            # Publish message
            self.channel.basic_publish(
                exchange=exchange_name,
                routing_key=routing_key,
                body=json.dumps(enriched_message, default=str),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,  # Make message persistent
                    timestamp=int(datetime.now(timezone.utc).timestamp()),
                ),
            )

            logger.debug(
                f"Published message from {self.adapter_id} with routing key: {routing_key}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish message from {self.adapter_id}: {e}")
            return False

    async def publish_status_update(self, status_data: Dict[str, Any]) -> bool:
        """Publish adapter status update.

        Args:
            status_data: Status information to publish.

        Returns:
            True if published successfully.
        """
        status_message = {
            "event_type": "status_update",
            "adapter_id": self.adapter_id,
            "status": status_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return await self.publish_message(
            status_message, f"status.{self.adapter_id}", self.config.exchange_name
        )

    async def publish_order_event(
        self, event_type: str, order_data: Dict[str, Any]
    ) -> bool:
        """Publish order-related event.

        Args:
            event_type: Type of order event (submitted, filled, cancelled, etc.).
            order_data: Order information.

        Returns:
            True if published successfully.
        """
        order_message = {
            "event_type": event_type,
            "adapter_id": self.adapter_id,
            "order": order_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return await self.publish_message(
            order_message,
            f"orders.{event_type}.{self.adapter_id}",
            self.config.exchange_name,
        )

    async def publish_execution_report(self, execution_data: Dict[str, Any]) -> bool:
        """Publish execution report.

        Args:
            execution_data: Execution report information.

        Returns:
            True if published successfully.
        """
        execution_message = {
            "event_type": "execution_report",
            "adapter_id": self.adapter_id,
            "execution": execution_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return await self.publish_message(
            execution_message,
            f"executions.{self.adapter_id}",
            self.config.exchange_name,
        )

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics.

        Returns:
            Dictionary containing connection metrics.
        """
        return {
            "adapter_id": self.adapter_id,
            "connected": self.connected,
            "mock_mode": self.mock_mode,
            "connection_attempts": self.connection_attempts,
            "last_connection_attempt": (
                self.last_connection_attempt.isoformat()
                if self.last_connection_attempt
                else None
            ),
            "connected_at": (
                self.connected_at.isoformat() if self.connected_at else None
            ),
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self.connected_at).total_seconds()
                if self.connected_at
                else 0
            ),
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "exchange": self.config.exchange_name,
            },
        }

    # Mock methods for testing
    async def _mock_connect(self) -> bool:
        """Mock connection for testing."""
        await asyncio.sleep(0.1)  # Simulate connection delay
        self.connected = True
        self.connected_at = datetime.now(timezone.utc)
        logger.info(f"Mock RabbitMQ connection established for {self.adapter_id}")

        if self.on_connection_open:
            await self.on_connection_open()

        return True

    async def _mock_disconnect(self):
        """Mock disconnection for testing."""
        self.connected = False
        logger.info(f"Mock RabbitMQ disconnection for {self.adapter_id}")

        if self.on_connection_closed:
            await self.on_connection_closed()

    async def _mock_publish(self, message: Dict[str, Any], routing_key: str) -> bool:
        """Mock message publishing for testing."""
        logger.debug(f"Mock publish from {self.adapter_id}: {routing_key}")
        return True


# Convenience factory function
def create_rabbitmq_manager(
    config: Dict[str, Any], adapter_id: str
) -> RabbitMQConnectionManager:
    """Create RabbitMQ connection manager from configuration.

    Args:
        config: Configuration dictionary.
        adapter_id: Unique adapter identifier.

    Returns:
        Configured RabbitMQ connection manager.
    """
    rabbitmq_config = RabbitMQConfig.from_dict(config)
    return RabbitMQConnectionManager(rabbitmq_config, adapter_id)
