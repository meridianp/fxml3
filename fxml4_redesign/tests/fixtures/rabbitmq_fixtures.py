"""RabbitMQ fixtures for testing."""

import asyncio
import json
from datetime import datetime
from typing import Any, Callable, Dict, List
from unittest.mock import AsyncMock, MagicMock

import aio_pika


class MockMessage:
    """Mock RabbitMQ message."""

    def __init__(self, body: Dict[str, Any], routing_key: str = ""):
        self._body = json.dumps(body).encode()
        self.routing_key = routing_key
        self.delivery_tag = 1
        self.redelivered = False
        self.exchange = "test_exchange"
        self.headers = {}

    @property
    def body(self) -> bytes:
        return self._body

    def process(self):
        """Context manager for message processing."""
        return MockMessageProcessor(self)


class MockMessageProcessor:
    """Mock message processor context manager."""

    def __init__(self, message: MockMessage):
        self.message = message
        self.acked = False
        self.nacked = False
        self.rejected = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            self.acked = True
        else:
            self.nacked = True
        return False


class MockQueue:
    """Mock RabbitMQ queue."""

    def __init__(self, name: str):
        self.name = name
        self.messages: List[MockMessage] = []
        self.consumers: List[Callable] = []
        self.bound_exchanges = []

    async def bind(self, exchange, routing_key: str = ""):
        """Bind queue to exchange."""
        self.bound_exchanges.append((exchange, routing_key))

    async def consume(self, callback: Callable):
        """Add consumer callback."""
        self.consumers.append(callback)

    async def put(self, message: MockMessage):
        """Add message to queue."""
        self.messages.append(message)

        # Notify consumers
        for consumer in self.consumers:
            await consumer(message)

    def iterator(self):
        """Get queue iterator."""
        return MockQueueIterator(self)


class MockQueueIterator:
    """Mock queue iterator for consuming messages."""

    def __init__(self, queue: MockQueue):
        self.queue = queue
        self.index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        # Wait for messages
        while self.index >= len(self.queue.messages):
            await asyncio.sleep(0.01)

        message = self.queue.messages[self.index]
        self.index += 1
        return message


class MockExchange:
    """Mock RabbitMQ exchange."""

    def __init__(self, name: str, type: str = "topic"):
        self.name = name
        self.type = type
        self.bound_queues: Dict[str, List[str]] = {}  # queue_name -> routing_keys
        self.published_messages: List[Dict[str, Any]] = []

    async def publish(self, message: aio_pika.Message, routing_key: str = ""):
        """Publish message to exchange."""
        # Decode message
        body = json.loads(message.body.decode())

        # Store published message
        self.published_messages.append(
            {"body": body, "routing_key": routing_key, "timestamp": datetime.utcnow()}
        )

        # Route to bound queues
        for queue_name, patterns in self.bound_queues.items():
            if self._matches_routing_key(routing_key, patterns):
                # In real implementation, would deliver to queue
                pass

    def bind_queue(self, queue_name: str, routing_key: str = ""):
        """Bind queue to exchange."""
        if queue_name not in self.bound_queues:
            self.bound_queues[queue_name] = []
        self.bound_queues[queue_name].append(routing_key)

    def _matches_routing_key(self, key: str, patterns: List[str]) -> bool:
        """Check if routing key matches any pattern."""
        for pattern in patterns:
            if pattern == "#" or pattern == key:
                return True

            # Simple wildcard matching
            pattern_parts = pattern.split(".")
            key_parts = key.split(".")

            if len(pattern_parts) != len(key_parts):
                continue

            match = True
            for p, k in zip(pattern_parts, key_parts):
                if p != "*" and p != k:
                    match = False
                    break

            if match:
                return True

        return False


class MockChannel:
    """Mock RabbitMQ channel."""

    def __init__(self):
        self.exchanges: Dict[str, MockExchange] = {}
        self.queues: Dict[str, MockQueue] = {}
        self.is_closed = False
        self.qos_prefetch = 1

    async def set_qos(self, prefetch_count: int = 1):
        """Set QOS settings."""
        self.qos_prefetch = prefetch_count

    async def declare_exchange(
        self,
        name: str,
        type: str = "topic",
        durable: bool = True,
        auto_delete: bool = False,
    ):
        """Declare exchange."""
        if name not in self.exchanges:
            self.exchanges[name] = MockExchange(name, type)
        return self.exchanges[name]

    async def get_exchange(self, name: str) -> MockExchange:
        """Get exchange by name."""
        if name not in self.exchanges:
            raise ValueError(f"Exchange {name} not found")
        return self.exchanges[name]

    async def declare_queue(
        self,
        name: str = "",
        durable: bool = True,
        exclusive: bool = False,
        auto_delete: bool = False,
    ):
        """Declare queue."""
        if not name:
            name = f"queue_{len(self.queues)}"

        if name not in self.queues:
            self.queues[name] = MockQueue(name)
        return self.queues[name]

    async def get_queue(self, name: str) -> MockQueue:
        """Get queue by name."""
        if name not in self.queues:
            raise ValueError(f"Queue {name} not found")
        return self.queues[name]

    async def close(self):
        """Close channel."""
        self.is_closed = True


class MockConnection:
    """Mock RabbitMQ connection."""

    def __init__(self):
        self.channels: List[MockChannel] = []
        self.is_closed = False

    async def channel(self) -> MockChannel:
        """Create channel."""
        channel = MockChannel()
        self.channels.append(channel)
        return channel

    async def close(self):
        """Close connection."""
        self.is_closed = True
        for channel in self.channels:
            await channel.close()


class RabbitMQTestHarness:
    """Test harness for RabbitMQ operations."""

    def __init__(self):
        self.connection = MockConnection()
        self.channel = None
        self.exchanges = {}
        self.queues = {}

    async def setup(self):
        """Set up test harness."""
        self.channel = await self.connection.channel()

        # Declare common exchanges
        await self.declare_exchange("market.data", "topic")
        await self.declare_exchange("trading.signals", "topic")
        await self.declare_exchange("system", "topic")

        # Declare common queues
        await self.declare_queue("market.data.eurusd")
        await self.declare_queue("trading.signals.all")
        await self.declare_queue("system.events")

    async def teardown(self):
        """Tear down test harness."""
        await self.connection.close()

    async def declare_exchange(self, name: str, type: str = "topic"):
        """Declare exchange."""
        exchange = await self.channel.declare_exchange(name, type)
        self.exchanges[name] = exchange
        return exchange

    async def declare_queue(self, name: str):
        """Declare queue."""
        queue = await self.channel.declare_queue(name)
        self.queues[name] = queue
        return queue

    async def bind_queue(
        self, queue_name: str, exchange_name: str, routing_key: str = "#"
    ):
        """Bind queue to exchange."""
        queue = self.queues.get(queue_name)
        exchange = self.exchanges.get(exchange_name)

        if queue and exchange:
            await queue.bind(exchange, routing_key)
            exchange.bind_queue(queue_name, routing_key)

    async def publish(self, exchange_name: str, routing_key: str, body: Dict[str, Any]):
        """Publish message."""
        exchange = self.exchanges.get(exchange_name)
        if not exchange:
            raise ValueError(f"Exchange {exchange_name} not found")

        message = aio_pika.Message(
            body=json.dumps(body).encode(), content_type="application/json"
        )

        await exchange.publish(message, routing_key)

    async def consume(self, queue_name: str, callback: Callable):
        """Consume from queue."""
        queue = self.queues.get(queue_name)
        if not queue:
            raise ValueError(f"Queue {queue_name} not found")

        await queue.consume(callback)

    def get_published_messages(self, exchange_name: str) -> List[Dict[str, Any]]:
        """Get all messages published to exchange."""
        exchange = self.exchanges.get(exchange_name)
        if not exchange:
            return []
        return exchange.published_messages

    async def simulate_message(
        self, queue_name: str, body: Dict[str, Any], routing_key: str = ""
    ):
        """Simulate receiving a message on a queue."""
        queue = self.queues.get(queue_name)
        if not queue:
            raise ValueError(f"Queue {queue_name} not found")

        message = MockMessage(body, routing_key)
        await queue.put(message)


# Fixture for creating test messages
def create_test_messages() -> Dict[str, Any]:
    """Create various test messages."""
    return {
        "market_update": {
            "symbol": "EURUSD",
            "timeframe": "4H",
            "data": {
                "time": datetime.utcnow().isoformat(),
                "open": 1.0850,
                "high": 1.0855,
                "low": 1.0845,
                "close": 1.0852,
                "volume": 1000,
            },
            "timestamp": datetime.utcnow().isoformat(),
            "service": "data-collector",
        },
        "trading_signal": {
            "symbol": "EURUSD",
            "direction": "BUY",
            "entry_price": 1.0850,
            "stop_loss": 1.0820,
            "take_profit": 1.0880,
            "confidence": 0.75,
            "timeframe": "4H",
            "source": "ml_model",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "signal-generator",
        },
        "trade_execution": {
            "trade_id": "TEST-001",
            "symbol": "EURUSD",
            "direction": "BUY",
            "entry_price": 1.0850,
            "position_size": 10000,
            "status": "filled",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "trade-manager",
        },
        "system_event": {
            "event_type": "service_started",
            "service_name": "test-service",
            "message": "Service started successfully",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "monitor",
        },
        "heartbeat": {
            "service_name": "test-service",
            "status": "healthy",
            "metrics": {
                "cpu_usage": 45.2,
                "memory_usage": 1024,
                "active_connections": 5,
            },
            "timestamp": datetime.utcnow().isoformat(),
            "service": "test-service",
        },
    }
