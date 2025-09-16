"""Messaging infrastructure for broker adapters.

This module provides a unified messaging abstraction that allows broker adapters
to work with different messaging systems (RabbitMQ, Kafka, Redis, etc.) through
a common interface.
"""

# Legacy components (kept for backward compatibility)
try:
    from .consumer import BrokerMessageConsumer
    from .publisher import BrokerMessagePublisher
    from .router import MessageRouter
    from .topology import BrokerMessageTopology

    LEGACY_COMPONENTS_AVAILABLE = True
except ImportError:
    # Legacy components require pika, skip if not available
    LEGACY_COMPONENTS_AVAILABLE = False

# Core abstractions
from .base import (
    ConsumerConfig,
    InMemoryMessageBroker,
    Message,
    MessageBroker,
    MessageHandler,
    MessageMetadata,
    MessageStatus,
    QueueConfig,
    QueueType,
)
from .connection_manager import (
    RabbitMQConfig,
    RabbitMQConnectionManager,
    create_rabbitmq_manager,
)

# Factory and builders
from .factory import (
    BrokerConfigBuilder,
    BrokerType,
    MessageBrokerFactory,
    create_development_broker,
    create_in_memory_message_broker,
    create_message_broker,
    create_production_broker,
    create_rabbitmq_message_broker,
    create_test_broker,
)

# RabbitMQ implementation
from .rabbitmq_broker import RabbitMQMessageBroker, create_rabbitmq_broker

# Build __all__ dynamically based on available components
__all__ = []

# Add legacy components if available
if LEGACY_COMPONENTS_AVAILABLE:
    __all__.extend(
        [
            "BrokerMessageTopology",
            "BrokerMessagePublisher",
            "BrokerMessageConsumer",
            "MessageRouter",
        ]
    )

# Core abstractions (always available)
__all__.extend(
    [
        "MessageBroker",
        "Message",
        "MessageMetadata",
        "MessageStatus",
        "QueueConfig",
        "QueueType",
        "ConsumerConfig",
        "MessageHandler",
        "InMemoryMessageBroker",
        # RabbitMQ implementation
        "RabbitMQMessageBroker",
        "create_rabbitmq_broker",
        "RabbitMQConnectionManager",
        "RabbitMQConfig",
        "create_rabbitmq_manager",
        # Factory and builders
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
)
