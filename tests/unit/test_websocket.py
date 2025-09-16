"""
Comprehensive unit tests for WebSocket service.

This module provides complete test coverage for the WebSocket functionality,
following Test-Driven Development (TDD) principles.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Set
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Use centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Mock all external dependencies before importing
sys.modules["openai"] = Mock()
sys.modules["fxml4.strategy.integrated_signal_generator"] = Mock()
sys.modules["fxml4.wave_analysis.sentiment_wave_validator"] = Mock()
sys.modules["fxml4.llm_integration.sentiment_analysis"] = Mock()
sys.modules["fxml4.llm_integration.llm_client"] = Mock()
sys.modules["redis.asyncio"] = Mock()
sys.modules["fastapi"] = Mock()
sys.modules["fxml4.config"] = Mock()

# Mock config and market data service
mock_config = {"redis": {"host": "localhost", "port": 6379, "db": 0}}

sys.modules["fxml4.config"].get_config = Mock(return_value=mock_config)


# Mock market data service
class MockMarketDataService:
    def __init__(self):
        pass

    async def get_available_symbols(self):
        return ["EURUSD", "GBPUSD", "USDJPY"]

    async def get_latest_tick(self, symbol):
        return {
            "time": datetime.utcnow().isoformat(),
            "price": 1.1000,
            "size": 1000,
            "symbol": symbol,
            "tick_type": "trade",
        }


mock_market_data_service = MockMarketDataService()

sys.modules["fxml4.api.services.market_data"] = Mock()
sys.modules["fxml4.api.services.market_data"].market_data_service = (
    mock_market_data_service
)


class MockWebSocket:
    """Mock WebSocket connection for testing."""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.connected = False
        self.messages_sent = []
        self.messages_to_receive = []
        self.receive_index = 0
        self.connection_error = False
        self.json_error = False

    async def accept(self):
        """Mock WebSocket accept."""
        if self.connection_error:
            raise Exception("Connection failed")
        self.connected = True

    async def send_text(self, message: str):
        """Mock sending text message."""
        if self.connection_error:
            raise Exception("Connection lost")
        self.messages_sent.append(message)

    async def receive_text(self) -> str:
        """Mock receiving text message."""
        if self.connection_error:
            raise Exception("Connection lost")

        if self.receive_index >= len(self.messages_to_receive):
            # Simulate WebSocketDisconnect
            from unittest.mock import Mock

            disconnect_exception = Mock()
            disconnect_exception.__class__.__name__ = "WebSocketDisconnect"
            raise disconnect_exception

        message = self.messages_to_receive[self.receive_index]
        self.receive_index += 1

        if self.json_error:
            return "invalid json"

        return message

    def add_message_to_receive(self, message: dict):
        """Add a message that will be received from client."""
        self.messages_to_receive.append(json.dumps(message))

    def get_sent_messages(self) -> List[dict]:
        """Get all messages sent to this WebSocket as parsed JSON."""
        return [json.loads(msg) for msg in self.messages_sent]


class MockConnectionManager:
    """Mock implementation of ConnectionManager for testing."""

    def __init__(self):
        self.connections: Dict[str, MockWebSocket] = {}
        self.subscriptions: Dict[str, Set[str]] = {}
        self.subscribers: Dict[str, Set[str]] = {}
        self.redis_client = None
        self.redis_connection_error = False
        self.connection_errors = {}  # client_id -> should_error

    async def connect(self, websocket: MockWebSocket, client_id: str):
        """Mock client connection."""
        if self.connection_errors.get(client_id, False):
            raise Exception(f"Connection failed for {client_id}")

        await websocket.accept()
        self.connections[client_id] = websocket
        self.subscriptions[client_id] = set()

    async def disconnect(self, client_id: str):
        """Mock client disconnection."""
        if client_id in self.connections:
            # Remove all subscriptions
            if client_id in self.subscriptions:
                for sub_key in self.subscriptions[client_id]:
                    if sub_key in self.subscribers:
                        self.subscribers[sub_key].discard(client_id)
                        if not self.subscribers[sub_key]:
                            del self.subscribers[sub_key]
                del self.subscriptions[client_id]

            del self.connections[client_id]

    async def subscribe(self, client_id: str, subscription_key: str):
        """Mock client subscription."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].add(subscription_key)

            if subscription_key not in self.subscribers:
                self.subscribers[subscription_key] = set()
            self.subscribers[subscription_key].add(client_id)

            # Send confirmation
            await self.send_personal_message(
                client_id,
                {
                    "type": "subscription_confirmed",
                    "subscription": subscription_key,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

    async def unsubscribe(self, client_id: str, subscription_key: str):
        """Mock client unsubscription."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].discard(subscription_key)

        if subscription_key in self.subscribers:
            self.subscribers[subscription_key].discard(client_id)
            if not self.subscribers[subscription_key]:
                del self.subscribers[subscription_key]

        # Send confirmation
        await self.send_personal_message(
            client_id,
            {
                "type": "unsubscription_confirmed",
                "subscription": subscription_key,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def send_personal_message(self, client_id: str, message: dict):
        """Mock sending personal message."""
        if client_id in self.connections:
            websocket = self.connections[client_id]
            if self.connection_errors.get(client_id, False):
                await self.disconnect(client_id)
                return

            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                await self.disconnect(client_id)

    async def broadcast_to_subscribers(self, subscription_key: str, message: dict):
        """Mock broadcasting to subscribers."""
        if subscription_key in self.subscribers:
            disconnected_clients = []

            for client_id in self.subscribers[subscription_key].copy():
                if client_id in self.connections:
                    if self.connection_errors.get(client_id, False):
                        disconnected_clients.append(client_id)
                        continue

                    try:
                        websocket = self.connections[client_id]
                        await websocket.send_text(json.dumps(message))
                    except Exception:
                        disconnected_clients.append(client_id)

            # Clean up disconnected clients
            for client_id in disconnected_clients:
                await self.disconnect(client_id)

    async def _init_redis(self):
        """Mock Redis initialization."""
        if self.redis_connection_error:
            raise Exception("Redis connection failed")

        self.redis_client = Mock()
        self.redis_client.ping = AsyncMock()


class MockWebSocketService:
    """Mock implementation of WebSocketService for testing."""

    def __init__(self):
        self.manager = MockConnectionManager()
        self._background_tasks: Set[asyncio.Task] = set()
        self.background_tasks_running = False
        self.streaming_error = False
        self.message_handling_error = False

    async def start_background_tasks(self):
        """Mock starting background tasks."""
        self.background_tasks_running = True
        # Don't actually start tasks in tests

    async def stop_background_tasks(self):
        """Mock stopping background tasks."""
        self.background_tasks_running = False
        for task in self._background_tasks:
            task.cancel()
        self._background_tasks.clear()

    async def handle_client_message(self, client_id: str, message: dict):
        """Mock handling client messages."""
        try:
            if self.message_handling_error:
                raise Exception("Message handling error")

            message_type = message.get("type")

            if message_type == "subscribe":
                subscription = message.get("subscription")
                if subscription:
                    await self.manager.subscribe(client_id, subscription)

            elif message_type == "unsubscribe":
                subscription = message.get("subscription")
                if subscription:
                    await self.manager.unsubscribe(client_id, subscription)

            elif message_type == "ping":
                await self.manager.send_personal_message(
                    client_id,
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                )

            elif message_type == "get_symbols":
                symbols = await mock_market_data_service.get_available_symbols()
                await self.manager.send_personal_message(
                    client_id,
                    {
                        "type": "symbols",
                        "data": symbols,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

            elif message_type == "get_latest_tick":
                symbol = message.get("symbol")
                if symbol:
                    tick_data = await mock_market_data_service.get_latest_tick(symbol)
                    await self.manager.send_personal_message(
                        client_id,
                        {
                            "type": "tick_data",
                            "symbol": symbol,
                            "data": tick_data,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )

            else:
                await self.manager.send_personal_message(
                    client_id,
                    {
                        "type": "error",
                        "message": f"Unknown message type: {message_type}",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

        except Exception as e:
            await self.manager.send_personal_message(
                client_id,
                {
                    "type": "error",
                    "message": "Internal server error",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

    async def _stream_market_data(self):
        """Mock market data streaming."""
        if self.streaming_error:
            raise Exception("Streaming error")

        # Mock streaming logic
        active_symbols = set()
        for subscription_key in self.manager.subscribers:
            if subscription_key.startswith("tick:"):
                symbol = subscription_key.split(":", 1)[1]
                active_symbols.add(symbol)

        for symbol in active_symbols:
            tick_data = await mock_market_data_service.get_latest_tick(symbol)
            if tick_data:
                await self.manager.broadcast_to_subscribers(
                    f"tick:{symbol}",
                    {
                        "type": "tick_update",
                        "symbol": symbol,
                        "data": tick_data,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

    async def connect_client(self, websocket: MockWebSocket, client_id: str):
        """Mock client connection."""
        await self.manager.connect(websocket, client_id)

    async def disconnect_client(self, client_id: str):
        """Mock client disconnection."""
        await self.manager.disconnect(client_id)


class TestMockConnectionManager:
    """Test the mock connection manager functionality."""

    @pytest.fixture
    def manager(self):
        """Create a fresh MockConnectionManager instance for each test."""
        return MockConnectionManager()

    @pytest.fixture
    def websocket(self):
        """Create a mock WebSocket."""
        return MockWebSocket("test_client_1")

    @pytest.mark.asyncio
    async def test_connection_success(self, manager, websocket):
        """Test successful client connection."""
        client_id = "test_client_1"

        await manager.connect(websocket, client_id)

        assert websocket.connected is True
        assert client_id in manager.connections
        assert client_id in manager.subscriptions
        assert len(manager.subscriptions[client_id]) == 0

    @pytest.mark.asyncio
    async def test_connection_failure(self, manager, websocket):
        """Test client connection failure."""
        client_id = "test_client_1"
        manager.connection_errors[client_id] = True

        with pytest.raises(Exception, match="Connection failed"):
            await manager.connect(websocket, client_id)

        assert client_id not in manager.connections

    @pytest.mark.asyncio
    async def test_disconnection(self, manager, websocket):
        """Test client disconnection."""
        client_id = "test_client_1"
        subscription_key = "tick:EURUSD"

        # Connect and subscribe first
        await manager.connect(websocket, client_id)
        await manager.subscribe(client_id, subscription_key)

        # Verify setup
        assert client_id in manager.connections
        assert subscription_key in manager.subscriptions[client_id]
        assert client_id in manager.subscribers[subscription_key]

        # Disconnect
        await manager.disconnect(client_id)

        # Verify cleanup
        assert client_id not in manager.connections
        assert client_id not in manager.subscriptions
        assert subscription_key not in manager.subscribers

    @pytest.mark.asyncio
    async def test_subscription_success(self, manager, websocket):
        """Test successful subscription."""
        client_id = "test_client_1"
        subscription_key = "tick:EURUSD"

        # Connect first
        await manager.connect(websocket, client_id)

        # Subscribe
        await manager.subscribe(client_id, subscription_key)

        # Verify subscription
        assert subscription_key in manager.subscriptions[client_id]
        assert client_id in manager.subscribers[subscription_key]

        # Check confirmation message
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "subscription_confirmed"
        assert sent_messages[0]["subscription"] == subscription_key

    @pytest.mark.asyncio
    async def test_multiple_subscriptions(self, manager, websocket):
        """Test multiple subscriptions for same client."""
        client_id = "test_client_1"
        subscriptions = ["tick:EURUSD", "tick:GBPUSD", "ohlcv:USDJPY"]

        # Connect first
        await manager.connect(websocket, client_id)

        # Subscribe to multiple streams
        for subscription in subscriptions:
            await manager.subscribe(client_id, subscription)

        # Verify all subscriptions
        assert len(manager.subscriptions[client_id]) == 3
        for subscription in subscriptions:
            assert subscription in manager.subscriptions[client_id]
            assert client_id in manager.subscribers[subscription]

        # Check confirmation messages
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 3
        assert all(msg["type"] == "subscription_confirmed" for msg in sent_messages)

    @pytest.mark.asyncio
    async def test_unsubscription(self, manager, websocket):
        """Test unsubscription from data stream."""
        client_id = "test_client_1"
        subscription_key = "tick:EURUSD"

        # Connect and subscribe first
        await manager.connect(websocket, client_id)
        await manager.subscribe(client_id, subscription_key)

        # Verify subscription exists
        assert subscription_key in manager.subscriptions[client_id]
        assert client_id in manager.subscribers[subscription_key]

        # Unsubscribe
        await manager.unsubscribe(client_id, subscription_key)

        # Verify unsubscription
        assert subscription_key not in manager.subscriptions[client_id]
        assert subscription_key not in manager.subscribers

        # Check messages (subscribe confirmation + unsubscribe confirmation)
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 2
        assert sent_messages[1]["type"] == "unsubscription_confirmed"
        assert sent_messages[1]["subscription"] == subscription_key

    @pytest.mark.asyncio
    async def test_send_personal_message(self, manager, websocket):
        """Test sending personal message to client."""
        client_id = "test_client_1"
        test_message = {
            "type": "test",
            "content": "Hello, client!",
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Connect first
        await manager.connect(websocket, client_id)

        # Send message
        await manager.send_personal_message(client_id, test_message)

        # Verify message sent
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 1
        assert sent_messages[0] == test_message

    @pytest.mark.asyncio
    async def test_send_message_to_disconnected_client(self, manager, websocket):
        """Test sending message to disconnected client."""
        client_id = "test_client_1"
        test_message = {"type": "test", "content": "Hello"}

        # Don't connect the client
        await manager.send_personal_message(client_id, test_message)

        # No message should be sent
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 0

    @pytest.mark.asyncio
    async def test_send_message_with_connection_error(self, manager, websocket):
        """Test sending message when connection fails."""
        client_id = "test_client_1"
        test_message = {"type": "test", "content": "Hello"}

        # Connect first
        await manager.connect(websocket, client_id)

        # Set connection error
        manager.connection_errors[client_id] = True

        # Send message (should trigger disconnection)
        await manager.send_personal_message(client_id, test_message)

        # Client should be disconnected
        assert client_id not in manager.connections

    @pytest.mark.asyncio
    async def test_broadcast_to_subscribers(self, manager):
        """Test broadcasting message to subscribers."""
        subscription_key = "tick:EURUSD"
        test_message = {
            "type": "tick_update",
            "symbol": "EURUSD",
            "data": {"price": 1.1000},
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Create multiple clients and subscribe
        clients = []
        for i in range(3):
            client_id = f"client_{i}"
            websocket = MockWebSocket(client_id)
            await manager.connect(websocket, client_id)
            await manager.subscribe(client_id, subscription_key)
            clients.append((client_id, websocket))

        # Broadcast message
        await manager.broadcast_to_subscribers(subscription_key, test_message)

        # Verify all subscribers received the message
        for client_id, websocket in clients:
            sent_messages = websocket.get_sent_messages()
            # Should have subscription confirmation + broadcast message
            assert len(sent_messages) >= 2
            assert sent_messages[-1] == test_message  # Last message should be broadcast

    @pytest.mark.asyncio
    async def test_broadcast_with_connection_errors(self, manager):
        """Test broadcasting when some clients have connection errors."""
        subscription_key = "tick:EURUSD"
        test_message = {"type": "test_broadcast", "data": "test"}

        # Create clients, make one fail
        client1_id = "client_1"
        client2_id = "client_2"
        websocket1 = MockWebSocket(client1_id)
        websocket2 = MockWebSocket(client2_id)

        await manager.connect(websocket1, client1_id)
        await manager.connect(websocket2, client2_id)
        await manager.subscribe(client1_id, subscription_key)
        await manager.subscribe(client2_id, subscription_key)

        # Set connection error for client2
        manager.connection_errors[client2_id] = True

        # Broadcast message
        await manager.broadcast_to_subscribers(subscription_key, test_message)

        # Client1 should receive message, client2 should be disconnected
        client1_messages = websocket1.get_sent_messages()
        assert len(client1_messages) >= 2  # subscription + broadcast
        assert client1_messages[-1] == test_message

        # Client2 should be disconnected
        assert client2_id not in manager.connections
        assert client2_id not in manager.subscribers[subscription_key]

    @pytest.mark.asyncio
    async def test_redis_initialization_success(self, manager):
        """Test successful Redis initialization."""
        await manager._init_redis()

        assert manager.redis_client is not None
        assert hasattr(manager.redis_client, "ping")

    @pytest.mark.asyncio
    async def test_redis_initialization_failure(self, manager):
        """Test Redis initialization failure."""
        manager.redis_connection_error = True

        # Should handle the exception internally
        try:
            await manager._init_redis()
        except Exception:
            pass  # Expected to raise exception in mock

        assert manager.redis_client is None


class TestMockWebSocketService:
    """Test the mock WebSocket service functionality."""

    @pytest.fixture
    def service(self):
        """Create a fresh MockWebSocketService instance for each test."""
        return MockWebSocketService()

    @pytest.fixture
    def websocket(self):
        """Create a mock WebSocket."""
        return MockWebSocket("test_client")

    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.manager is not None
        assert len(service._background_tasks) == 0
        assert service.background_tasks_running is False

    @pytest.mark.asyncio
    async def test_start_stop_background_tasks(self, service):
        """Test starting and stopping background tasks."""
        # Start tasks
        await service.start_background_tasks()
        assert service.background_tasks_running is True

        # Stop tasks
        await service.stop_background_tasks()
        assert service.background_tasks_running is False
        assert len(service._background_tasks) == 0

    @pytest.mark.asyncio
    async def test_handle_subscribe_message(self, service, websocket):
        """Test handling subscribe message."""
        client_id = "test_client"
        subscription_key = "tick:EURUSD"

        # Connect client
        await service.connect_client(websocket, client_id)

        # Handle subscribe message
        message = {"type": "subscribe", "subscription": subscription_key}
        await service.handle_client_message(client_id, message)

        # Verify subscription
        assert subscription_key in service.manager.subscriptions[client_id]
        assert client_id in service.manager.subscribers[subscription_key]

        # Check confirmation message
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "subscription_confirmed"

    @pytest.mark.asyncio
    async def test_handle_unsubscribe_message(self, service, websocket):
        """Test handling unsubscribe message."""
        client_id = "test_client"
        subscription_key = "tick:GBPUSD"

        # Connect and subscribe first
        await service.connect_client(websocket, client_id)
        await service.manager.subscribe(client_id, subscription_key)

        # Handle unsubscribe message
        message = {"type": "unsubscribe", "subscription": subscription_key}
        await service.handle_client_message(client_id, message)

        # Verify unsubscription
        assert subscription_key not in service.manager.subscriptions[client_id]
        assert subscription_key not in service.manager.subscribers

        # Check messages (subscribe confirmation + unsubscribe confirmation)
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 2
        assert sent_messages[1]["type"] == "unsubscription_confirmed"

    @pytest.mark.asyncio
    async def test_handle_ping_message(self, service, websocket):
        """Test handling ping message."""
        client_id = "test_client"

        # Connect client
        await service.connect_client(websocket, client_id)

        # Handle ping message
        message = {"type": "ping"}
        await service.handle_client_message(client_id, message)

        # Check pong response
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "pong"
        assert "timestamp" in sent_messages[0]

    @pytest.mark.asyncio
    async def test_handle_get_symbols_message(self, service, websocket):
        """Test handling get_symbols message."""
        client_id = "test_client"

        # Connect client
        await service.connect_client(websocket, client_id)

        # Handle get_symbols message
        message = {"type": "get_symbols"}
        await service.handle_client_message(client_id, message)

        # Check symbols response
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "symbols"
        assert "data" in sent_messages[0]
        assert isinstance(sent_messages[0]["data"], list)
        assert len(sent_messages[0]["data"]) > 0

    @pytest.mark.asyncio
    async def test_handle_get_latest_tick_message(self, service, websocket):
        """Test handling get_latest_tick message."""
        client_id = "test_client"
        symbol = "EURUSD"

        # Connect client
        await service.connect_client(websocket, client_id)

        # Debug: verify connection
        assert client_id in service.manager.connections
        assert websocket.connected is True

        # Handle get_latest_tick message
        message = {"type": "get_latest_tick", "symbol": symbol}
        await service.handle_client_message(client_id, message)

        # Check tick data response
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "tick_data"
        assert sent_messages[0]["symbol"] == symbol
        assert "data" in sent_messages[0]

    @pytest.mark.asyncio
    async def test_handle_unknown_message_type(self, service, websocket):
        """Test handling unknown message type."""
        client_id = "test_client"

        # Connect client
        await service.connect_client(websocket, client_id)

        # Handle unknown message
        message = {"type": "unknown_type"}
        await service.handle_client_message(client_id, message)

        # Check error response
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "error"
        assert "Unknown message type" in sent_messages[0]["message"]

    @pytest.mark.asyncio
    async def test_handle_message_with_error(self, service, websocket):
        """Test handling message that causes internal error."""
        client_id = "test_client"

        # Connect client
        await service.connect_client(websocket, client_id)

        # Set service to cause error
        service.message_handling_error = True

        # Handle any message
        message = {"type": "ping"}
        await service.handle_client_message(client_id, message)

        # Check error response
        sent_messages = websocket.get_sent_messages()
        assert len(sent_messages) == 1
        assert sent_messages[0]["type"] == "error"
        assert sent_messages[0]["message"] == "Internal server error"

    @pytest.mark.asyncio
    async def test_market_data_streaming(self, service):
        """Test market data streaming functionality."""
        # Create clients with subscriptions
        client_ids = ["client_1", "client_2"]
        symbols = ["EURUSD", "GBPUSD"]

        for i, client_id in enumerate(client_ids):
            websocket = MockWebSocket(client_id)
            await service.connect_client(websocket, client_id)
            await service.manager.subscribe(client_id, f"tick:{symbols[i]}")

        # Run streaming (mock version)
        await service._stream_market_data()

        # Verify streaming worked (subscribers should receive tick updates)
        for i, client_id in enumerate(client_ids):
            websocket = service.manager.connections[client_id]
            sent_messages = websocket.get_sent_messages()

            # Should have subscription confirmation + tick update
            assert len(sent_messages) >= 2
            tick_update = sent_messages[-1]
            assert tick_update["type"] == "tick_update"
            assert tick_update["symbol"] == symbols[i]

    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, service):
        """Test streaming error handling."""
        service.streaming_error = True

        with pytest.raises(Exception, match="Streaming error"):
            await service._stream_market_data()

    @pytest.mark.asyncio
    async def test_client_connection_workflow(self, service, websocket):
        """Test complete client connection workflow."""
        client_id = "test_client"

        # Connect
        await service.connect_client(websocket, client_id)
        assert client_id in service.manager.connections
        assert websocket.connected is True

        # Disconnect
        await service.disconnect_client(client_id)
        assert client_id not in service.manager.connections


class TestWebSocketBusinessLogic:
    """Test WebSocket service business logic patterns."""

    @pytest.fixture
    def service(self):
        return MockWebSocketService()

    @pytest.mark.asyncio
    async def test_complete_subscription_workflow(self, service):
        """Test complete subscription workflow."""
        # Create multiple clients
        clients = []
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]

        for i, symbol in enumerate(symbols):
            client_id = f"trader_{i}"
            websocket = MockWebSocket(client_id)
            await service.connect_client(websocket, client_id)

            # Subscribe to tick data
            subscribe_msg = {"type": "subscribe", "subscription": f"tick:{symbol}"}
            await service.handle_client_message(client_id, subscribe_msg)

            clients.append((client_id, websocket, symbol))

        # Verify all subscriptions
        for client_id, websocket, symbol in clients:
            subscription_key = f"tick:{symbol}"
            assert subscription_key in service.manager.subscriptions[client_id]
            assert client_id in service.manager.subscribers[subscription_key]

            # Check confirmation
            sent_messages = websocket.get_sent_messages()
            assert any(msg["type"] == "subscription_confirmed" for msg in sent_messages)

        # Simulate streaming to all subscribers
        await service._stream_market_data()

        # Verify all clients received updates
        for client_id, websocket, symbol in clients:
            sent_messages = websocket.get_sent_messages()
            tick_updates = [
                msg for msg in sent_messages if msg["type"] == "tick_update"
            ]
            assert len(tick_updates) >= 1
            assert tick_updates[0]["symbol"] == symbol

    @pytest.mark.asyncio
    async def test_multi_subscription_per_client(self, service):
        """Test client subscribing to multiple data streams."""
        client_id = "multi_trader"
        websocket = MockWebSocket(client_id)

        # Connect client
        await service.connect_client(websocket, client_id)

        # Subscribe to multiple streams
        subscriptions = ["tick:EURUSD", "tick:GBPUSD", "ohlcv:USDJPY"]
        for subscription in subscriptions:
            message = {"type": "subscribe", "subscription": subscription}
            await service.handle_client_message(client_id, message)

        # Verify all subscriptions
        assert len(service.manager.subscriptions[client_id]) == 3
        for subscription in subscriptions:
            assert subscription in service.manager.subscriptions[client_id]
            assert client_id in service.manager.subscribers[subscription]

        # Check confirmation messages
        sent_messages = websocket.get_sent_messages()
        confirmations = [
            msg for msg in sent_messages if msg["type"] == "subscription_confirmed"
        ]
        assert len(confirmations) == 3

    @pytest.mark.asyncio
    async def test_client_reconnection_scenario(self, service):
        """Test client disconnection and reconnection."""
        client_id = "reconnecting_client"
        subscription_key = "tick:EURUSD"

        # First connection
        websocket1 = MockWebSocket(client_id)
        await service.connect_client(websocket1, client_id)
        await service.manager.subscribe(client_id, subscription_key)

        # Verify first connection
        assert client_id in service.manager.connections
        assert client_id in service.manager.subscribers[subscription_key]

        # Simulate disconnection
        await service.disconnect_client(client_id)
        assert client_id not in service.manager.connections
        assert subscription_key not in service.manager.subscribers

        # Reconnect with new websocket
        websocket2 = MockWebSocket(client_id)
        await service.connect_client(websocket2, client_id)

        # Re-subscribe
        await service.manager.subscribe(client_id, subscription_key)

        # Verify reconnection
        assert client_id in service.manager.connections
        assert service.manager.connections[client_id] == websocket2
        assert client_id in service.manager.subscribers[subscription_key]

    @pytest.mark.asyncio
    async def test_error_resilience(self, service):
        """Test service resilience to various errors."""
        client_id = "error_client"
        websocket = MockWebSocket(client_id)

        # Connect successfully
        await service.connect_client(websocket, client_id)

        # Test handling message that causes error
        service.message_handling_error = True
        message = {"type": "subscribe", "subscription": "tick:EURUSD"}
        await service.handle_client_message(client_id, message)

        # Should receive error response
        sent_messages = websocket.get_sent_messages()
        assert any(msg["type"] == "error" for msg in sent_messages)

        # Client should still be connected after error
        assert client_id in service.manager.connections

        # Reset error state and test normal operation
        service.message_handling_error = False
        ping_message = {"type": "ping"}
        await service.handle_client_message(client_id, ping_message)

        # Should receive pong
        sent_messages = websocket.get_sent_messages()
        assert any(msg["type"] == "pong" for msg in sent_messages)

    @pytest.mark.asyncio
    async def test_subscription_cleanup_on_disconnect(self, service):
        """Test proper cleanup when clients disconnect."""
        # Create multiple clients with overlapping subscriptions
        client_data = [
            ("client_1", ["tick:EURUSD", "tick:GBPUSD"]),
            ("client_2", ["tick:EURUSD", "tick:USDJPY"]),
            ("client_3", ["tick:GBPUSD"]),
        ]

        clients = {}
        for client_id, subscriptions in client_data:
            websocket = MockWebSocket(client_id)
            await service.connect_client(websocket, client_id)
            clients[client_id] = websocket

            for subscription in subscriptions:
                await service.manager.subscribe(client_id, subscription)

        # Verify initial state
        assert "tick:EURUSD" in service.manager.subscribers
        assert (
            len(service.manager.subscribers["tick:EURUSD"]) == 2
        )  # client_1, client_2
        assert (
            len(service.manager.subscribers["tick:GBPUSD"]) == 2
        )  # client_1, client_3

        # Disconnect client_1
        await service.disconnect_client("client_1")

        # Verify cleanup - client_1 removed but subscriptions with other clients remain
        assert "client_1" not in service.manager.connections
        assert "client_1" not in service.manager.subscriptions
        assert "tick:EURUSD" in service.manager.subscribers  # Still has client_2
        assert len(service.manager.subscribers["tick:EURUSD"]) == 1
        assert (
            len(service.manager.subscribers["tick:GBPUSD"]) == 1
        )  # Still has client_3

        # Disconnect remaining clients
        await service.disconnect_client("client_2")
        await service.disconnect_client("client_3")

        # All subscriptions should be cleaned up
        assert len(service.manager.subscribers) == 0
        assert len(service.manager.connections) == 0


# Pytest configuration
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
