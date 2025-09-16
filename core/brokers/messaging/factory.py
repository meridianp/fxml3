"""Message Broker Factory.

This module provides factory functions for creating different message broker
implementations based on configuration, enabling easy switching between
broker types (RabbitMQ, Kafka, Redis, In-Memory) without code changes.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from .base import InMemoryMessageBroker, MessageBroker
from .connection_manager import RabbitMQConfig
from .rabbitmq_broker import RabbitMQMessageBroker, create_rabbitmq_broker

logger = logging.getLogger(__name__)


class BrokerType(Enum):
    """Supported message broker types."""

    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"
    REDIS = "redis"
    IN_MEMORY = "in_memory"
    MOCK = "mock"


class MessageBrokerFactory:
    """Factory for creating message broker instances."""

    # Registry of broker implementations
    _broker_registry: Dict[BrokerType, Type[MessageBroker]] = {
        BrokerType.RABBITMQ: RabbitMQMessageBroker,
        BrokerType.IN_MEMORY: InMemoryMessageBroker,
        BrokerType.MOCK: InMemoryMessageBroker,  # Use in-memory for mock
    }

    @classmethod
    def register_broker(
        cls, broker_type: BrokerType, broker_class: Type[MessageBroker]
    ):
        """Register a new broker implementation.

        Args:
            broker_type: Type identifier for the broker.
            broker_class: Broker implementation class.
        """
        cls._broker_registry[broker_type] = broker_class
        logger.info(f"Registered broker type: {broker_type.value}")

    @classmethod
    def create_broker(
        self,
        broker_id: str,
        broker_type: Union[str, BrokerType],
        config: Dict[str, Any],
    ) -> MessageBroker:
        """Create a message broker instance.

        Args:
            broker_id: Unique identifier for the broker.
            broker_type: Type of broker to create.
            config: Configuration dictionary.

        Returns:
            Configured message broker instance.

        Raises:
            ValueError: If broker type is not supported.
        """
        # Convert string to enum if needed
        if isinstance(broker_type, str):
            try:
                broker_type = BrokerType(broker_type.lower())
            except ValueError:
                raise ValueError(f"Unsupported broker type: {broker_type}")

        if broker_type not in self._broker_registry:
            raise ValueError(
                f"No implementation registered for broker type: {broker_type.value}"
            )

        # Create broker based on type
        if broker_type == BrokerType.RABBITMQ:
            return self._create_rabbitmq_broker(broker_id, config)
        elif broker_type in [BrokerType.IN_MEMORY, BrokerType.MOCK]:
            return self._create_in_memory_broker(broker_id, config)
        elif broker_type == BrokerType.KAFKA:
            return self._create_kafka_broker(broker_id, config)
        elif broker_type == BrokerType.REDIS:
            return self._create_redis_broker(broker_id, config)
        else:
            # Generic creation for registered types
            broker_class = self._broker_registry[broker_type]
            return broker_class(broker_id)

    @classmethod
    def _create_rabbitmq_broker(
        cls, broker_id: str, config: Dict[str, Any]
    ) -> RabbitMQMessageBroker:
        """Create RabbitMQ broker instance."""
        return create_rabbitmq_broker(broker_id, config)

    @classmethod
    def _create_in_memory_broker(
        cls, broker_id: str, config: Dict[str, Any]
    ) -> InMemoryMessageBroker:
        """Create in-memory broker instance."""
        return InMemoryMessageBroker(broker_id)

    @classmethod
    def _create_kafka_broker(
        cls, broker_id: str, config: Dict[str, Any]
    ) -> MessageBroker:
        """Create Kafka broker instance.

        Note: Kafka implementation would be added here when available.
        Currently returns in-memory broker as fallback.
        """
        logger.warning(
            f"Kafka broker not implemented, using in-memory broker for {broker_id}"
        )
        return InMemoryMessageBroker(broker_id)

    @classmethod
    def _create_redis_broker(
        cls, broker_id: str, config: Dict[str, Any]
    ) -> MessageBroker:
        """Create Redis broker instance.

        Note: Redis implementation would be added here when available.
        Currently returns in-memory broker as fallback.
        """
        logger.warning(
            f"Redis broker not implemented, using in-memory broker for {broker_id}"
        )
        return InMemoryMessageBroker(broker_id)

    @classmethod
    def get_supported_types(cls) -> List[str]:
        """Get list of supported broker types.

        Returns:
            List of supported broker type names.
        """
        return [broker_type.value for broker_type in cls._broker_registry.keys()]


# Convenience factory functions


def create_message_broker(
    broker_id: str,
    broker_type: Union[str, BrokerType] = BrokerType.IN_MEMORY,
    config: Optional[Dict[str, Any]] = None,
) -> MessageBroker:
    """Create a message broker instance.

    Args:
        broker_id: Unique identifier for the broker.
        broker_type: Type of broker to create (default: in_memory).
        config: Optional configuration dictionary.

    Returns:
        Configured message broker instance.
    """
    config = config or {}
    return MessageBrokerFactory.create_broker(broker_id, broker_type, config)


def create_rabbitmq_message_broker(
    broker_id: str,
    host: str = "localhost",
    port: int = 5672,
    username: str = "guest",
    password: str = "guest",
    virtual_host: str = "/",
    **kwargs,
) -> RabbitMQMessageBroker:
    """Create RabbitMQ message broker with simple parameters.

    Args:
        broker_id: Unique identifier for the broker.
        host: RabbitMQ server host.
        port: RabbitMQ server port.
        username: Username for authentication.
        password: Password for authentication.
        virtual_host: Virtual host to connect to.
        **kwargs: Additional configuration parameters.

    Returns:
        Configured RabbitMQ message broker.
    """
    config = {
        "rabbitmq": {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "virtual_host": virtual_host,
            **kwargs,
        }
    }

    return create_rabbitmq_broker(broker_id, config)


def create_in_memory_message_broker(broker_id: str) -> InMemoryMessageBroker:
    """Create in-memory message broker for testing.

    Args:
        broker_id: Unique identifier for the broker.

    Returns:
        In-memory message broker instance.
    """
    return InMemoryMessageBroker(broker_id)


# Configuration helpers


class BrokerConfigBuilder:
    """Builder for message broker configurations."""

    def __init__(self, broker_type: Union[str, BrokerType]):
        """Initialize config builder.

        Args:
            broker_type: Type of broker to configure.
        """
        self.broker_type = (
            BrokerType(broker_type) if isinstance(broker_type, str) else broker_type
        )
        self.config: Dict[str, Any] = {}

    def with_rabbitmq_config(
        self,
        host: str = "localhost",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
        virtual_host: str = "/",
        exchange_name: str = "broker_exchange",
        exchange_type: str = "topic",
    ) -> "BrokerConfigBuilder":
        """Configure RabbitMQ settings.

        Args:
            host: RabbitMQ server host.
            port: RabbitMQ server port.
            username: Username for authentication.
            password: Password for authentication.
            virtual_host: Virtual host to connect to.
            exchange_name: Default exchange name.
            exchange_type: Default exchange type.

        Returns:
            Self for method chaining.
        """
        self.config["rabbitmq"] = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "virtual_host": virtual_host,
            "exchange_name": exchange_name,
            "exchange_type": exchange_type,
        }
        return self

    def with_kafka_config(
        self, bootstrap_servers: List[str] = None, client_id: str = "", **kwargs
    ) -> "BrokerConfigBuilder":
        """Configure Kafka settings.

        Args:
            bootstrap_servers: List of Kafka bootstrap servers.
            client_id: Client identifier.
            **kwargs: Additional Kafka configuration.

        Returns:
            Self for method chaining.
        """
        bootstrap_servers = bootstrap_servers or ["localhost:9092"]
        self.config["kafka"] = {
            "bootstrap_servers": bootstrap_servers,
            "client_id": client_id,
            **kwargs,
        }
        return self

    def with_redis_config(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        **kwargs,
    ) -> "BrokerConfigBuilder":
        """Configure Redis settings.

        Args:
            host: Redis server host.
            port: Redis server port.
            db: Redis database number.
            password: Optional password for authentication.
            **kwargs: Additional Redis configuration.

        Returns:
            Self for method chaining.
        """
        self.config["redis"] = {
            "host": host,
            "port": port,
            "db": db,
            "password": password,
            **kwargs,
        }
        return self

    def with_retry_config(
        self, max_retries: int = 3, retry_delay: float = 1.0, retry_backoff: float = 2.0
    ) -> "BrokerConfigBuilder":
        """Configure retry settings.

        Args:
            max_retries: Maximum number of retries.
            retry_delay: Initial retry delay in seconds.
            retry_backoff: Backoff multiplier for retries.

        Returns:
            Self for method chaining.
        """
        self.config["retry"] = {
            "max_retries": max_retries,
            "retry_delay": retry_delay,
            "retry_backoff": retry_backoff,
        }
        return self

    def with_custom_config(self, key: str, value: Any) -> "BrokerConfigBuilder":
        """Add custom configuration.

        Args:
            key: Configuration key.
            value: Configuration value.

        Returns:
            Self for method chaining.
        """
        self.config[key] = value
        return self

    def build(self, broker_id: str) -> MessageBroker:
        """Build the message broker with configured settings.

        Args:
            broker_id: Unique identifier for the broker.

        Returns:
            Configured message broker instance.
        """
        return MessageBrokerFactory.create_broker(
            broker_id, self.broker_type, self.config
        )


# Convenience functions for common configurations


def create_development_broker(broker_id: str) -> MessageBroker:
    """Create message broker for development environment.

    Uses in-memory broker for fast setup and testing.

    Args:
        broker_id: Unique identifier for the broker.

    Returns:
        In-memory message broker.
    """
    return create_in_memory_message_broker(broker_id)


def create_production_broker(broker_id: str, config: Dict[str, Any]) -> MessageBroker:
    """Create message broker for production environment.

    Auto-detects broker type from configuration or defaults to RabbitMQ.

    Args:
        broker_id: Unique identifier for the broker.
        config: Configuration dictionary.

    Returns:
        Configured message broker.
    """
    # Auto-detect broker type from config
    if "rabbitmq" in config:
        broker_type = BrokerType.RABBITMQ
    elif "kafka" in config:
        broker_type = BrokerType.KAFKA
    elif "redis" in config:
        broker_type = BrokerType.REDIS
    else:
        # Default to RabbitMQ for production
        broker_type = BrokerType.RABBITMQ
        logger.info(
            f"No specific broker config found, defaulting to RabbitMQ for {broker_id}"
        )

    return MessageBrokerFactory.create_broker(broker_id, broker_type, config)


def create_test_broker(broker_id: str) -> MessageBroker:
    """Create message broker for testing.

    Uses in-memory broker for isolated testing.

    Args:
        broker_id: Unique identifier for the broker.

    Returns:
        In-memory message broker.
    """
    return create_in_memory_message_broker(broker_id)


# Export main factory and convenience functions
__all__ = [
    "MessageBrokerFactory",
    "BrokerType",
    "BrokerConfigBuilder",
    "create_message_broker",
    "create_rabbitmq_message_broker",
    "create_in_memory_message_broker",
    "create_development_broker",
    "create_production_broker",
    "create_test_broker",
]
