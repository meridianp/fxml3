"""RabbitMQ configuration for FXML4 trading system."""

from enum import Enum
from typing import Any, Dict


class ExchangeTypes(str, Enum):
    """RabbitMQ exchange types."""

    DIRECT = "direct"
    TOPIC = "topic"
    FANOUT = "fanout"
    HEADERS = "headers"


class Exchanges(str, Enum):
    """System exchanges."""

    MARKET_DATA = "market_data"
    SIGNALS = "signals"
    TRADES = "trades"
    SYSTEM = "system"


class RoutingKeys:
    """Routing keys for messages."""

    # Market data routing keys
    MARKET_TICK = "market.tick.{symbol}"
    MARKET_1MIN = "market.1min.{symbol}"
    MARKET_READY = "market.ready.{symbol}"

    # Signal routing keys
    SIGNAL_ML = "signal.ml.{symbol}"
    SIGNAL_ELLIOTT = "signal.elliott.{symbol}"
    SIGNAL_COMBINED = "signal.combined.{symbol}"
    SIGNAL_VALIDATED = "signal.validated.{symbol}"

    # Trade routing keys
    TRADE_ENTRY = "trade.entry.{symbol}"
    TRADE_EXIT = "trade.exit.{symbol}"
    TRADE_UPDATE = "trade.update.{symbol}"
    TRADE_EXECUTED = "trade.executed.{symbol}"

    # System routing keys
    SYSTEM_HEARTBEAT = "system.heartbeat.{service}"
    SYSTEM_ALERT = "system.alert.{severity}"
    SYSTEM_METRICS = "system.metrics.{service}"


class Queues(str, Enum):
    """System queues."""

    # Data queues
    DATA_ANALYSIS = "data_analysis"
    DATA_1MIN_STREAM = "data_1min_stream"

    # Signal queues
    SIGNAL_GENERATION = "signal_generation"
    SIGNAL_VALIDATION = "signal_validation"

    # Trading queues
    TRADE_ENTRY_QUEUE = "trade_entry"
    TRADE_MANAGEMENT = "trade_management"

    # System queues
    SYSTEM_MONITORING = "system_monitoring"
    SYSTEM_ALERTS = "system_alerts"


class RabbitMQConfig:
    """RabbitMQ configuration."""

    @staticmethod
    def get_exchange_config() -> Dict[str, Dict[str, Any]]:
        """Get exchange configurations."""
        return {
            Exchanges.MARKET_DATA: {
                "type": ExchangeTypes.TOPIC,
                "durable": True,
                "auto_delete": False,
                "arguments": {},
            },
            Exchanges.SIGNALS: {
                "type": ExchangeTypes.TOPIC,
                "durable": True,
                "auto_delete": False,
                "arguments": {},
            },
            Exchanges.TRADES: {
                "type": ExchangeTypes.TOPIC,
                "durable": True,
                "auto_delete": False,
                "arguments": {},
            },
            Exchanges.SYSTEM: {
                "type": ExchangeTypes.TOPIC,
                "durable": True,
                "auto_delete": False,
                "arguments": {},
            },
        }

    @staticmethod
    def get_queue_config() -> Dict[str, Dict[str, Any]]:
        """Get queue configurations."""
        return {
            Queues.DATA_ANALYSIS: {
                "durable": True,
                "exclusive": False,
                "auto_delete": False,
                "arguments": {
                    "x-message-ttl": 3600000,  # 1 hour
                    "x-max-length": 10000,
                },
            },
            Queues.DATA_1MIN_STREAM: {
                "durable": True,
                "exclusive": False,
                "auto_delete": False,
                "arguments": {
                    "x-message-ttl": 300000,  # 5 minutes
                    "x-max-length": 5000,
                },
            },
            Queues.SIGNAL_GENERATION: {
                "durable": True,
                "exclusive": False,
                "auto_delete": False,
                "arguments": {
                    "x-message-ttl": 600000,  # 10 minutes
                    "x-max-length": 1000,
                },
            },
            Queues.SIGNAL_VALIDATION: {
                "durable": True,
                "exclusive": False,
                "auto_delete": False,
                "arguments": {
                    "x-message-ttl": 300000,  # 5 minutes
                    "x-max-length": 500,
                    "x-max-priority": 10,  # Priority queue
                },
            },
            Queues.TRADE_ENTRY_QUEUE: {
                "durable": True,
                "exclusive": False,
                "auto_delete": False,
                "arguments": {
                    "x-message-ttl": 60000,  # 1 minute
                    "x-max-length": 100,
                    "x-max-priority": 10,  # Priority queue
                },
            },
            Queues.TRADE_MANAGEMENT: {
                "durable": True,
                "exclusive": False,
                "auto_delete": False,
                "arguments": {
                    "x-message-ttl": 300000,  # 5 minutes
                    "x-max-length": 1000,
                },
            },
            Queues.SYSTEM_MONITORING: {
                "durable": True,
                "exclusive": False,
                "auto_delete": False,
                "arguments": {
                    "x-message-ttl": 86400000,  # 24 hours
                    "x-max-length": 10000,
                },
            },
            Queues.SYSTEM_ALERTS: {
                "durable": True,
                "exclusive": False,
                "auto_delete": False,
                "arguments": {
                    "x-message-ttl": 3600000,  # 1 hour
                    "x-max-length": 1000,
                    "x-max-priority": 10,  # Priority queue
                },
            },
        }

    @staticmethod
    def get_bindings() -> list[Dict[str, Any]]:
        """Get queue bindings."""
        return [
            # Market data bindings
            {
                "queue": Queues.DATA_ANALYSIS,
                "exchange": Exchanges.MARKET_DATA,
                "routing_key": "market.1min.*",
            },
            {
                "queue": Queues.DATA_1MIN_STREAM,
                "exchange": Exchanges.MARKET_DATA,
                "routing_key": "market.tick.*",
            },
            # Signal bindings
            {
                "queue": Queues.SIGNAL_GENERATION,
                "exchange": Exchanges.MARKET_DATA,
                "routing_key": "market.ready.*",
            },
            {
                "queue": Queues.SIGNAL_VALIDATION,
                "exchange": Exchanges.SIGNALS,
                "routing_key": "signal.combined.*",
            },
            # Trade bindings
            {
                "queue": Queues.TRADE_ENTRY_QUEUE,
                "exchange": Exchanges.SIGNALS,
                "routing_key": "signal.validated.*",
            },
            {
                "queue": Queues.TRADE_MANAGEMENT,
                "exchange": Exchanges.TRADES,
                "routing_key": "trade.executed.*",
            },
            {
                "queue": Queues.TRADE_MANAGEMENT,
                "exchange": Exchanges.MARKET_DATA,
                "routing_key": "market.tick.*",
            },
            # System bindings
            {
                "queue": Queues.SYSTEM_MONITORING,
                "exchange": Exchanges.SYSTEM,
                "routing_key": "system.heartbeat.*",
            },
            {
                "queue": Queues.SYSTEM_MONITORING,
                "exchange": Exchanges.SYSTEM,
                "routing_key": "system.metrics.*",
            },
            {
                "queue": Queues.SYSTEM_ALERTS,
                "exchange": Exchanges.SYSTEM,
                "routing_key": "system.alert.*",
            },
        ]


class MessagePriority:
    """Message priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


def format_routing_key(template: str, **kwargs) -> str:
    """Format routing key with parameters.

    Args:
        template: Routing key template
        **kwargs: Parameters to format

    Returns:
        Formatted routing key
    """
    return template.format(**kwargs)
