"""Test fixtures for FXML4 testing."""

from .database_fixtures import DatabaseFixtures, generate_complete_test_dataset
from .market_data_fixtures import (
    IndicatorDataGenerator,
    MarketDataGenerator,
    SignalDataGenerator,
)
from .rabbitmq_fixtures import (
    MockChannel,
    MockConnection,
    MockExchange,
    MockMessage,
    MockQueue,
    RabbitMQTestHarness,
    create_test_messages,
)

__all__ = [
    # Database
    "DatabaseFixtures",
    "generate_complete_test_dataset",
    # RabbitMQ
    "MockMessage",
    "MockQueue",
    "MockExchange",
    "MockChannel",
    "MockConnection",
    "RabbitMQTestHarness",
    "create_test_messages",
    # Market Data
    "MarketDataGenerator",
    "IndicatorDataGenerator",
    "SignalDataGenerator",
]
