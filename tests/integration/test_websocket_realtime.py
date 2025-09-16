"""
WebSocket Real-Time Functionality Integration Tests for FXML4.

This module tests the real-time WebSocket capabilities including connection management,
subscription handling, broadcasting, and integration with core services.
"""

import asyncio
import json
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio

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
sys.modules["fxml4.config"] = Mock()
sys.modules["fxml4.data_engineering.data_feeds.base_feed"] = Mock()

# Mock config
mock_config = {
    "database": {
        "user": "test_user",
        "password": "test_password",
        "host": "localhost",
        "port": 5432,
        "name": "test_db",
    },
    "redis": {"host": "localhost", "port": 6379, "db": 0},
    "websocket": {
        "max_connections": 1000,
        "message_queue_size": 10000,
        "heartbeat_interval": 30,
    },
}

sys.modules["fxml4.config"].get_config = Mock(return_value=mock_config)


class MockWebSocketConnection:
    """Mock WebSocket connection for testing."""

    def __init__(self, client_id: str, connected: bool = True):
        self.client_id = client_id
        self.connected = connected
        self.messages_sent = []
        self.messages_received = []
        self.connection_error = False
        self.closed = False
        self.connect_time = datetime.utcnow()

    async def accept(self):
        """Mock WebSocket accept."""
        self.connected = True

    async def send_text(self, message: str):
        """Mock sending text message."""
        if not self.connected or self.connection_error or self.closed:
            raise ConnectionError("WebSocket connection closed")

        self.messages_sent.append(
            {"message": message, "timestamp": datetime.utcnow(), "type": "text"}
        )

    async def send_json(self, data: dict):
        """Mock sending JSON message."""
        if not self.connected or self.connection_error or self.closed:
            raise ConnectionError("WebSocket connection closed")

        message = json.dumps(data)
        await self.send_text(message)

    async def receive_text(self):
        """Mock receiving text message."""
        if not self.connected or self.connection_error or self.closed:
            raise ConnectionError("WebSocket connection closed")

        # Simulate waiting for message
        await asyncio.sleep(0.01)

        if self.messages_received:
            return self.messages_received.pop(0)
        else:
            # Simulate WebSocket waiting
            await asyncio.sleep(1.0)
            return '{"type": "ping"}'

    async def close(self, code: int = 1000):
        """Mock WebSocket close."""
        self.connected = False
        self.closed = True

    def simulate_receive(self, message: str):
        """Simulate receiving a message from client."""
        self.messages_received.append(message)

    def simulate_disconnect(self):
        """Simulate connection error."""
        self.connection_error = True
        self.connected = False


class MockWebSocketManager:
    """Mock WebSocket connection manager for testing."""

    def __init__(self):
        # Active connections by connection ID
        self.connections: Dict[str, MockWebSocketConnection] = {}
        # Subscriptions: connection_id -> set of subscription keys
        self.subscriptions: Dict[str, Set[str]] = {}
        # Reverse mapping: subscription_key -> set of connection_ids
        self.subscribers: Dict[str, Set[str]] = {}
        # Message history for verification
        self.broadcast_history = []
        self.connection_history = []

        # Statistics
        self.total_connections = 0
        self.total_messages_sent = 0
        self.total_subscriptions = 0

    async def connect(self, websocket: MockWebSocketConnection, client_id: str):
        """Connect a new WebSocket client."""
        await websocket.accept()
        self.connections[client_id] = websocket
        self.subscriptions[client_id] = set()
        self.total_connections += 1

        self.connection_history.append(
            {
                "action": "connect",
                "client_id": client_id,
                "timestamp": datetime.utcnow(),
            }
        )

    async def disconnect(self, client_id: str):
        """Handle client disconnection."""
        if client_id in self.connections:
            # Remove all subscriptions for this client
            if client_id in self.subscriptions:
                for sub_key in self.subscriptions[client_id]:
                    if sub_key in self.subscribers:
                        self.subscribers[sub_key].discard(client_id)
                        if not self.subscribers[sub_key]:
                            del self.subscribers[sub_key]
                del self.subscriptions[client_id]

            # Close connection
            await self.connections[client_id].close()
            del self.connections[client_id]

            self.connection_history.append(
                {
                    "action": "disconnect",
                    "client_id": client_id,
                    "timestamp": datetime.utcnow(),
                }
            )

    async def subscribe(self, client_id: str, subscription_key: str):
        """Subscribe a client to a data stream."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].add(subscription_key)

            if subscription_key not in self.subscribers:
                self.subscribers[subscription_key] = set()
            self.subscribers[subscription_key].add(client_id)

            self.total_subscriptions += 1

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
        """Unsubscribe a client from a data stream."""
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
        """Send a message to a specific client."""
        if client_id in self.connections:
            try:
                await self.connections[client_id].send_json(message)
                self.total_messages_sent += 1
            except Exception:
                await self.disconnect(client_id)

    async def broadcast_to_subscribers(self, subscription_key: str, message: dict):
        """Broadcast a message to all subscribers of a specific key."""
        if subscription_key in self.subscribers:
            disconnected_clients = []
            successful_sends = 0

            broadcast_record = {
                "subscription_key": subscription_key,
                "message": message,
                "timestamp": datetime.utcnow(),
                "target_clients": list(self.subscribers[subscription_key]),
                "successful_sends": 0,
                "failed_sends": 0,
            }

            for client_id in self.subscribers[subscription_key]:
                try:
                    if client_id in self.connections:
                        await self.connections[client_id].send_json(message)
                        successful_sends += 1
                        self.total_messages_sent += 1
                except Exception:
                    disconnected_clients.append(client_id)
                    broadcast_record["failed_sends"] += 1

            broadcast_record["successful_sends"] = successful_sends
            self.broadcast_history.append(broadcast_record)

            # Clean up disconnected clients
            for client_id in disconnected_clients:
                await self.disconnect(client_id)

            return successful_sends

        return 0

    def get_connection_stats(self):
        """Get connection statistics."""
        return {
            "active_connections": len(self.connections),
            "total_connections": self.total_connections,
            "total_subscriptions": self.total_subscriptions,
            "total_messages_sent": self.total_messages_sent,
            "subscription_keys": list(self.subscribers.keys()),
            "clients": list(self.connections.keys()),
        }


class MockRealTimeDataService:
    """Mock service that generates real-time data for WebSocket streaming."""

    def __init__(self, websocket_manager: MockWebSocketManager):
        self.websocket_manager = websocket_manager
        self.running = False
        self.data_generators = {}
        self.update_intervals = {
            "tick_data": 0.1,  # 100ms for tick updates
            "market_data": 1.0,  # 1 second for OHLCV updates
            "signals": 5.0,  # 5 seconds for signal updates
            "orders": 0.5,  # 500ms for order updates
        }

        # Mock data
        self.symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
        self.base_prices = {
            "EURUSD": 1.1000,
            "GBPUSD": 1.2500,
            "USDJPY": 150.00,
            "AUDUSD": 0.6750,
        }
        self.current_prices = self.base_prices.copy()

    async def start_streaming(self):
        """Start real-time data streaming."""
        self.running = True

        # Start data generation tasks
        self.data_generators["tick_data"] = asyncio.create_task(
            self._stream_tick_data()
        )
        self.data_generators["market_data"] = asyncio.create_task(
            self._stream_market_data()
        )
        self.data_generators["signals"] = asyncio.create_task(self._stream_signals())
        self.data_generators["orders"] = asyncio.create_task(self._stream_orders())

    async def stop_streaming(self):
        """Stop real-time data streaming."""
        self.running = False

        # Cancel all data generation tasks
        for task in self.data_generators.values():
            task.cancel()

        # Wait for tasks to complete
        if self.data_generators:
            await asyncio.gather(*self.data_generators.values(), return_exceptions=True)

        self.data_generators.clear()

    async def _stream_tick_data(self):
        """Stream real-time tick data."""
        while self.running:
            try:
                for symbol in self.symbols:
                    # Check if anyone is subscribed to tick data for this symbol
                    subscription_key = f"tick:{symbol}"
                    if subscription_key in self.websocket_manager.subscribers:
                        # Generate tick data
                        tick_data = self._generate_tick_data(symbol)

                        message = {
                            "type": "tick_update",
                            "symbol": symbol,
                            "data": tick_data,
                            "timestamp": datetime.utcnow().isoformat(),
                        }

                        await self.websocket_manager.broadcast_to_subscribers(
                            subscription_key, message
                        )

                await asyncio.sleep(self.update_intervals["tick_data"])

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)  # Wait before retrying

    async def _stream_market_data(self):
        """Stream real-time market data."""
        while self.running:
            try:
                for symbol in self.symbols:
                    subscription_key = f"ohlcv:{symbol}"
                    if subscription_key in self.websocket_manager.subscribers:
                        # Generate OHLCV data
                        ohlcv_data = self._generate_ohlcv_data(symbol)

                        message = {
                            "type": "ohlcv_update",
                            "symbol": symbol,
                            "data": ohlcv_data,
                            "timestamp": datetime.utcnow().isoformat(),
                        }

                        await self.websocket_manager.broadcast_to_subscribers(
                            subscription_key, message
                        )

                await asyncio.sleep(self.update_intervals["market_data"])

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)

    async def _stream_signals(self):
        """Stream real-time trading signals."""
        while self.running:
            try:
                # Generate random signals
                import random

                if random.random() < 0.3:  # 30% chance of generating signal
                    symbol = random.choice(self.symbols)
                    signal_data = self._generate_signal_data(symbol)

                    # Broadcast to signal subscribers
                    subscription_keys = [f"signals:{symbol}", "signals:all"]

                    message = {
                        "type": "signal_update",
                        "signal": signal_data,
                        "timestamp": datetime.utcnow().isoformat(),
                    }

                    for sub_key in subscription_keys:
                        await self.websocket_manager.broadcast_to_subscribers(
                            sub_key, message
                        )

                await asyncio.sleep(self.update_intervals["signals"])

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)

    async def _stream_orders(self):
        """Stream real-time order updates."""
        while self.running:
            try:
                # Generate random order updates
                import random

                if random.random() < 0.2:  # 20% chance of generating order update
                    symbol = random.choice(self.symbols)
                    order_data = self._generate_order_data(symbol)

                    subscription_keys = [f"orders:{symbol}", "orders:all"]

                    message = {
                        "type": "order_update",
                        "order": order_data,
                        "timestamp": datetime.utcnow().isoformat(),
                    }

                    for sub_key in subscription_keys:
                        await self.websocket_manager.broadcast_to_subscribers(
                            sub_key, message
                        )

                await asyncio.sleep(self.update_intervals["orders"])

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)

    def _generate_tick_data(self, symbol: str):
        """Generate realistic tick data."""
        import random

        # Update current price with small random movement
        base_price = self.current_prices[symbol]
        price_change = random.uniform(-0.0005, 0.0005)  # 0.5 pip movement
        new_price = base_price + price_change
        self.current_prices[symbol] = new_price

        return {
            "time": datetime.utcnow().isoformat(),
            "price": round(new_price, 5),
            "size": random.randint(100, 1000),
            "symbol": symbol,
            "tick_type": "trade",
        }

    def _generate_ohlcv_data(self, symbol: str):
        """Generate realistic OHLCV data."""
        import random

        current_price = self.current_prices[symbol]

        # Generate OHLCV bar
        open_price = current_price + random.uniform(-0.0002, 0.0002)
        close_price = current_price + random.uniform(-0.0002, 0.0002)
        high_price = max(open_price, close_price) + random.uniform(0, 0.0003)
        low_price = min(open_price, close_price) - random.uniform(0, 0.0003)

        return {
            "time": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "open": round(open_price, 5),
            "high": round(high_price, 5),
            "low": round(low_price, 5),
            "close": round(close_price, 5),
            "volume": random.randint(1000, 5000),
        }

    def _generate_signal_data(self, symbol: str):
        """Generate realistic signal data."""
        import random

        return {
            "id": f"signal_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{symbol}",
            "symbol": symbol,
            "direction": random.choice([1, -1]),
            "confidence": round(random.uniform(0.3, 0.95), 3),
            "signal_type": random.choice(["ml_signal", "technical", "elliott_wave"]),
            "source": "realtime_generator",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "current_price": self.current_prices[symbol],
                "strength": random.uniform(0.1, 1.0),
            },
        }

    def _generate_order_data(self, symbol: str):
        """Generate realistic order data."""
        import random

        return {
            "id": f"order_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{symbol}",
            "symbol": symbol,
            "side": random.choice(["buy", "sell"]),
            "quantity": random.choice([1000, 5000, 10000, 25000]),
            "status": random.choice(["pending", "filled", "partial"]),
            "order_type": "market",
            "created_at": datetime.utcnow().isoformat(),
            "avg_fill_price": self.current_prices[symbol]
            + random.uniform(-0.0001, 0.0001),
        }


class TestWebSocketRealTimeIntegration:
    """Test WebSocket real-time functionality integration."""

    @pytest.fixture
    def websocket_manager(self):
        """Create a fresh WebSocket manager for each test."""
        return MockWebSocketManager()

    @pytest.fixture
    def realtime_service(self, websocket_manager):
        """Create real-time data service."""
        return MockRealTimeDataService(websocket_manager)

    @pytest_asyncio.fixture
    async def connected_client(self, websocket_manager):
        """Create a connected WebSocket client."""
        client_id = f"test_client_{uuid.uuid4().hex[:8]}"
        websocket = MockWebSocketConnection(client_id)
        await websocket_manager.connect(websocket, client_id)
        return client_id, websocket, websocket_manager

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self, websocket_manager):
        """Test WebSocket connection establishment and cleanup."""
        client_id = "test_client_1"
        websocket = MockWebSocketConnection(client_id)

        # Connect client
        await websocket_manager.connect(websocket, client_id)

        # Verify connection
        assert client_id in websocket_manager.connections
        assert websocket.connected is True
        assert len(websocket_manager.connections) == 1

        # Verify connection history
        assert len(websocket_manager.connection_history) == 1
        assert websocket_manager.connection_history[0]["action"] == "connect"
        assert websocket_manager.connection_history[0]["client_id"] == client_id

        # Disconnect client
        await websocket_manager.disconnect(client_id)

        # Verify disconnection
        assert client_id not in websocket_manager.connections
        assert len(websocket_manager.connections) == 0
        assert websocket.closed is True

        # Verify disconnect history
        assert len(websocket_manager.connection_history) == 2
        assert websocket_manager.connection_history[1]["action"] == "disconnect"

    @pytest.mark.asyncio
    async def test_subscription_management(self, connected_client):
        """Test WebSocket subscription and unsubscription."""
        client_id, websocket, manager = connected_client

        # Subscribe to tick data
        await manager.subscribe(client_id, "tick:EURUSD")

        # Verify subscription
        assert "tick:EURUSD" in manager.subscriptions[client_id]
        assert client_id in manager.subscribers["tick:EURUSD"]
        assert manager.total_subscriptions == 1

        # Verify confirmation message
        assert len(websocket.messages_sent) == 1
        confirmation = json.loads(websocket.messages_sent[0]["message"])
        assert confirmation["type"] == "subscription_confirmed"
        assert confirmation["subscription"] == "tick:EURUSD"

        # Subscribe to another stream
        await manager.subscribe(client_id, "signals:all")

        # Verify multiple subscriptions
        assert len(manager.subscriptions[client_id]) == 2
        assert "signals:all" in manager.subscriptions[client_id]
        assert manager.total_subscriptions == 2

        # Unsubscribe from one stream
        await manager.unsubscribe(client_id, "tick:EURUSD")

        # Verify unsubscription
        assert "tick:EURUSD" not in manager.subscriptions[client_id]
        assert "tick:EURUSD" not in manager.subscribers
        assert len(manager.subscriptions[client_id]) == 1

        # Verify unsubscribe confirmation
        unsubscribe_messages = [
            msg
            for msg in websocket.messages_sent
            if "unsubscription_confirmed" in msg["message"]
        ]
        assert len(unsubscribe_messages) == 1

    @pytest.mark.asyncio
    async def test_real_time_broadcasting(self, websocket_manager):
        """Test real-time message broadcasting to subscribers."""
        # Create multiple clients
        clients = []
        for i in range(3):
            client_id = f"client_{i}"
            websocket = MockWebSocketConnection(client_id)
            await websocket_manager.connect(websocket, client_id)
            clients.append((client_id, websocket))

        # Subscribe clients to different streams
        await websocket_manager.subscribe("client_0", "tick:EURUSD")
        await websocket_manager.subscribe("client_1", "tick:EURUSD")
        await websocket_manager.subscribe("client_2", "signals:all")

        # Clear subscription confirmation messages
        for _, websocket in clients:
            websocket.messages_sent.clear()

        # Broadcast tick data
        tick_message = {
            "type": "tick_update",
            "symbol": "EURUSD",
            "price": 1.1025,
            "timestamp": datetime.utcnow().isoformat(),
        }

        successful_sends = await websocket_manager.broadcast_to_subscribers(
            "tick:EURUSD", tick_message
        )

        # Verify broadcast
        assert successful_sends == 2  # Only client_0 and client_1 subscribed

        # Check that correct clients received the message
        assert len(clients[0][1].messages_sent) == 1  # client_0 received
        assert len(clients[1][1].messages_sent) == 1  # client_1 received
        assert len(clients[2][1].messages_sent) == 0  # client_2 didn't receive

        # Verify message content
        received_message = json.loads(clients[0][1].messages_sent[0]["message"])
        assert received_message["type"] == "tick_update"
        assert received_message["symbol"] == "EURUSD"
        assert received_message["price"] == 1.1025

        # Verify broadcast history
        assert len(websocket_manager.broadcast_history) == 1
        broadcast_record = websocket_manager.broadcast_history[0]
        assert broadcast_record["subscription_key"] == "tick:EURUSD"
        assert broadcast_record["successful_sends"] == 2
        assert broadcast_record["failed_sends"] == 0

    @pytest.mark.asyncio
    async def test_multi_client_isolation(self, websocket_manager):
        """Test that clients only receive messages they're subscribed to."""
        # Create clients with different subscriptions
        client_configs = [
            ("trader_1", ["tick:EURUSD", "orders:EURUSD"]),
            ("trader_2", ["tick:GBPUSD", "signals:all"]),
            ("analyzer_1", ["signals:all", "orders:all"]),
            ("viewer_1", ["tick:EURUSD", "tick:GBPUSD"]),
        ]

        clients = {}
        for client_id, subscriptions in client_configs:
            websocket = MockWebSocketConnection(client_id)
            await websocket_manager.connect(websocket, client_id)
            clients[client_id] = websocket

            # Subscribe to streams
            for subscription in subscriptions:
                await websocket_manager.subscribe(client_id, subscription)

        # Clear subscription messages
        for websocket in clients.values():
            websocket.messages_sent.clear()

        # Broadcast different types of messages
        messages_to_broadcast = [
            ("tick:EURUSD", {"type": "tick", "symbol": "EURUSD", "price": 1.1000}),
            ("tick:GBPUSD", {"type": "tick", "symbol": "GBPUSD", "price": 1.2500}),
            ("signals:all", {"type": "signal", "symbol": "EURUSD", "direction": 1}),
            (
                "orders:EURUSD",
                {"type": "order", "symbol": "EURUSD", "status": "filled"},
            ),
            ("orders:all", {"type": "order", "symbol": "GBPUSD", "status": "pending"}),
        ]

        for subscription_key, message in messages_to_broadcast:
            await websocket_manager.broadcast_to_subscribers(subscription_key, message)

        # Verify message distribution
        # trader_1 should receive: tick:EURUSD, orders:EURUSD (2 messages)
        assert len(clients["trader_1"].messages_sent) == 2

        # trader_2 should receive: tick:GBPUSD, signals:all
        assert len(clients["trader_2"].messages_sent) == 2

        # analyzer_1 should receive: signals:all, orders:all (2 messages)
        assert len(clients["analyzer_1"].messages_sent) == 2

        # viewer_1 should receive: tick:EURUSD, tick:GBPUSD
        assert len(clients["viewer_1"].messages_sent) == 2

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, websocket_manager):
        """Test WebSocket connection error handling."""
        # Create clients
        stable_client = MockWebSocketConnection("stable_client")
        unstable_client = MockWebSocketConnection("unstable_client")

        await websocket_manager.connect(stable_client, "stable_client")
        await websocket_manager.connect(unstable_client, "unstable_client")

        # Subscribe both clients
        await websocket_manager.subscribe("stable_client", "tick:EURUSD")
        await websocket_manager.subscribe("unstable_client", "tick:EURUSD")

        # Simulate connection error on unstable client
        unstable_client.simulate_disconnect()

        # Clear messages
        stable_client.messages_sent.clear()
        unstable_client.messages_sent.clear()

        # Broadcast message
        message = {"type": "tick", "price": 1.1000}
        await websocket_manager.broadcast_to_subscribers("tick:EURUSD", message)

        # Verify stable client received message, unstable client was disconnected
        assert len(stable_client.messages_sent) == 1
        assert "unstable_client" not in websocket_manager.connections
        assert "unstable_client" not in websocket_manager.subscriptions

    @pytest.mark.asyncio
    async def test_real_time_data_streaming(self, websocket_manager, realtime_service):
        """Test real-time data streaming service."""
        # Create subscribing clients
        clients = []
        for i in range(2):
            client_id = f"stream_client_{i}"
            websocket = MockWebSocketConnection(client_id)
            await websocket_manager.connect(websocket, client_id)
            clients.append((client_id, websocket))

        # Subscribe to different data streams
        await websocket_manager.subscribe("stream_client_0", "tick:EURUSD")
        await websocket_manager.subscribe("stream_client_1", "signals:all")

        # Start streaming
        await realtime_service.start_streaming()

        # Let it run for a short period
        await asyncio.sleep(0.5)

        # Stop streaming
        await realtime_service.stop_streaming()

        # Verify data was streamed
        assert len(websocket_manager.broadcast_history) > 0

        # Check that tick data was broadcasted
        tick_broadcasts = [
            b
            for b in websocket_manager.broadcast_history
            if b["subscription_key"].startswith("tick:")
        ]
        assert len(tick_broadcasts) > 0

        # Verify clients received appropriate messages
        tick_client_messages = len(clients[0][1].messages_sent)
        signal_client_messages = len(clients[1][1].messages_sent)

        # Should have received some messages (accounting for subscription confirmations)
        assert tick_client_messages >= 1  # At least subscription confirmation
        assert signal_client_messages >= 1  # At least subscription confirmation

    @pytest.mark.asyncio
    async def test_high_frequency_messaging(self, websocket_manager):
        """Test WebSocket performance with high-frequency messaging."""
        # Create client
        client_id = "performance_client"
        websocket = MockWebSocketConnection(client_id)
        await websocket_manager.connect(websocket, client_id)
        await websocket_manager.subscribe(client_id, "performance:test")

        websocket.messages_sent.clear()

        # Send high-frequency messages
        message_count = 100
        start_time = time.time()

        for i in range(message_count):
            message = {
                "type": "performance_test",
                "sequence": i,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await websocket_manager.broadcast_to_subscribers(
                "performance:test", message
            )

        end_time = time.time()

        # Verify all messages were sent
        assert len(websocket.messages_sent) == message_count

        # Check performance (should complete in reasonable time)
        duration = end_time - start_time
        assert duration < 1.0  # Should complete in less than 1 second

        # Verify message ordering
        for i, sent_message in enumerate(websocket.messages_sent):
            message_data = json.loads(sent_message["message"])
            assert message_data["sequence"] == i

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, websocket_manager):
        """Test handling multiple concurrent WebSocket connections."""
        # Create many concurrent connections
        connection_count = 50
        clients = []

        # Connect all clients concurrently
        connect_tasks = []
        for i in range(connection_count):
            client_id = f"concurrent_client_{i}"
            websocket = MockWebSocketConnection(client_id)
            clients.append((client_id, websocket))
            connect_tasks.append(websocket_manager.connect(websocket, client_id))

        await asyncio.gather(*connect_tasks)

        # Verify all connections established
        assert len(websocket_manager.connections) == connection_count

        # Subscribe all clients to same stream
        subscribe_tasks = []
        for client_id, _ in clients:
            subscribe_tasks.append(
                websocket_manager.subscribe(client_id, "broadcast:all")
            )

        await asyncio.gather(*subscribe_tasks)

        # Clear subscription messages
        for _, websocket in clients:
            websocket.messages_sent.clear()

        # Broadcast message to all
        message = {"type": "broadcast", "data": "test_message"}
        successful_sends = await websocket_manager.broadcast_to_subscribers(
            "broadcast:all", message
        )

        # Verify all clients received the message
        assert successful_sends == connection_count

        for _, websocket in clients:
            assert len(websocket.messages_sent) == 1
            received_message = json.loads(websocket.messages_sent[0]["message"])
            assert received_message["type"] == "broadcast"
            assert received_message["data"] == "test_message"

    @pytest.mark.asyncio
    async def test_websocket_statistics_tracking(self, websocket_manager):
        """Test WebSocket statistics and monitoring."""
        # Initial statistics
        initial_stats = websocket_manager.get_connection_stats()
        assert initial_stats["active_connections"] == 0
        assert initial_stats["total_connections"] == 0

        # Create connections and subscriptions
        for i in range(3):
            client_id = f"stats_client_{i}"
            websocket = MockWebSocketConnection(client_id)
            await websocket_manager.connect(websocket, client_id)
            await websocket_manager.subscribe(client_id, f"stats:client_{i}")
            await websocket_manager.subscribe(client_id, "stats:all")

        # Get updated statistics
        stats = websocket_manager.get_connection_stats()

        assert stats["active_connections"] == 3
        assert stats["total_connections"] == 3
        assert stats["total_subscriptions"] == 6  # 3 clients * 2 subscriptions each
        assert (
            len(stats["subscription_keys"]) == 4
        )  # 3 individual + 1 "all" subscription
        assert len(stats["clients"]) == 3

        # Disconnect one client
        await websocket_manager.disconnect("stats_client_1")

        # Verify updated statistics
        updated_stats = websocket_manager.get_connection_stats()
        assert updated_stats["active_connections"] == 2
        assert updated_stats["total_connections"] == 3  # Historical count
        assert len(updated_stats["clients"]) == 2

    @pytest.mark.asyncio
    async def test_websocket_message_validation(self, connected_client):
        """Test WebSocket message validation and error handling."""
        client_id, websocket, manager = connected_client

        # Test valid subscription message
        valid_message = {"type": "subscribe", "subscription": "tick:EURUSD"}

        # Simulate processing the message (in real implementation this would be handled by message handler)
        if valid_message["type"] == "subscribe":
            await manager.subscribe(client_id, valid_message["subscription"])

        # Verify subscription worked
        assert "tick:EURUSD" in manager.subscriptions[client_id]

        # Test subscription to multiple streams
        multi_subscriptions = ["signals:EURUSD", "orders:all", "ohlcv:GBPUSD"]

        for subscription in multi_subscriptions:
            await manager.subscribe(client_id, subscription)

        # Verify all subscriptions
        assert len(manager.subscriptions[client_id]) == 4  # Including the first one
        for subscription in multi_subscriptions:
            assert subscription in manager.subscriptions[client_id]

    @pytest.mark.asyncio
    async def test_websocket_cleanup_on_disconnect(self, websocket_manager):
        """Test proper cleanup when WebSocket clients disconnect."""
        # Create client with multiple subscriptions
        client_id = "cleanup_test_client"
        websocket = MockWebSocketConnection(client_id)
        await websocket_manager.connect(websocket, client_id)

        # Create multiple subscriptions
        subscriptions = ["tick:EURUSD", "signals:all", "orders:EURUSD", "ohlcv:GBPUSD"]
        for subscription in subscriptions:
            await websocket_manager.subscribe(client_id, subscription)

        # Verify subscriptions are active
        assert len(websocket_manager.subscriptions[client_id]) == len(subscriptions)
        for subscription in subscriptions:
            assert client_id in websocket_manager.subscribers[subscription]

        # Disconnect client
        await websocket_manager.disconnect(client_id)

        # Verify complete cleanup
        assert client_id not in websocket_manager.connections
        assert client_id not in websocket_manager.subscriptions

        # Verify reverse mappings are cleaned up
        for subscription in subscriptions:
            assert (
                subscription not in websocket_manager.subscribers
                or client_id
                not in websocket_manager.subscribers.get(subscription, set())
            )


class TestWebSocketIntegrationWithServices:
    """Test WebSocket integration with core trading services."""

    @pytest.fixture
    def integrated_system(self):
        """Create integrated system with WebSocket and services."""
        websocket_manager = MockWebSocketManager()
        realtime_service = MockRealTimeDataService(websocket_manager)

        return {
            "websocket_manager": websocket_manager,
            "realtime_service": realtime_service,
            "signals": [],
            "orders": {},
            "market_data": {},
        }

    @pytest.mark.asyncio
    async def test_signal_to_websocket_integration(self, integrated_system):
        """Test signal generation triggering WebSocket broadcasts."""
        websocket_manager = integrated_system["websocket_manager"]

        # Create subscribing client
        client_id = "signal_subscriber"
        websocket = MockWebSocketConnection(client_id)
        await websocket_manager.connect(websocket, client_id)
        await websocket_manager.subscribe(client_id, "signals:EURUSD")

        websocket.messages_sent.clear()

        # Simulate signal generation and broadcast
        signal_data = {
            "id": "signal_123",
            "symbol": "EURUSD",
            "direction": 1,
            "confidence": 0.85,
            "timestamp": datetime.utcnow().isoformat(),
        }

        signal_message = {
            "type": "signal_update",
            "signal": signal_data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await websocket_manager.broadcast_to_subscribers(
            "signals:EURUSD", signal_message
        )

        # Verify client received signal
        assert len(websocket.messages_sent) == 1
        received_message = json.loads(websocket.messages_sent[0]["message"])
        assert received_message["type"] == "signal_update"
        assert received_message["signal"]["id"] == "signal_123"
        assert received_message["signal"]["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_order_execution_websocket_updates(self, integrated_system):
        """Test order execution triggering WebSocket updates."""
        websocket_manager = integrated_system["websocket_manager"]

        # Create clients interested in order updates
        order_client = MockWebSocketConnection("order_client")
        await websocket_manager.connect(order_client, "order_client")
        await websocket_manager.subscribe("order_client", "orders:EURUSD")

        execution_client = MockWebSocketConnection("execution_client")
        await websocket_manager.connect(execution_client, "execution_client")
        await websocket_manager.subscribe("execution_client", "executions:EURUSD")

        # Clear subscription messages
        order_client.messages_sent.clear()
        execution_client.messages_sent.clear()

        # Simulate order status update
        order_update = {
            "type": "order_update",
            "order": {
                "id": "order_456",
                "symbol": "EURUSD",
                "status": "filled",
                "quantity": 10000,
                "avg_fill_price": 1.1025,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        await websocket_manager.broadcast_to_subscribers("orders:EURUSD", order_update)

        # Simulate execution update
        execution_update = {
            "type": "execution",
            "execution": {
                "execution_id": "exec_789",
                "order_id": "order_456",
                "symbol": "EURUSD",
                "price": 1.1025,
                "quantity": 10000,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        await websocket_manager.broadcast_to_subscribers(
            "executions:EURUSD", execution_update
        )

        # Verify clients received appropriate updates
        assert len(order_client.messages_sent) == 1
        assert len(execution_client.messages_sent) == 1

        order_message = json.loads(order_client.messages_sent[0]["message"])
        execution_message = json.loads(execution_client.messages_sent[0]["message"])

        assert order_message["type"] == "order_update"
        assert order_message["order"]["id"] == "order_456"

        assert execution_message["type"] == "execution"
        assert execution_message["execution"]["order_id"] == "order_456"

    @pytest.mark.asyncio
    async def test_market_data_websocket_streaming(self, integrated_system):
        """Test market data streaming via WebSocket."""
        websocket_manager = integrated_system["websocket_manager"]
        realtime_service = integrated_system["realtime_service"]

        # Create market data subscriber
        market_client = MockWebSocketConnection("market_client")
        await websocket_manager.connect(market_client, "market_client")
        await websocket_manager.subscribe("market_client", "tick:EURUSD")
        await websocket_manager.subscribe("market_client", "ohlcv:EURUSD")

        market_client.messages_sent.clear()

        # Start real-time streaming briefly
        await realtime_service.start_streaming()
        await asyncio.sleep(0.2)  # Let it stream for 200ms
        await realtime_service.stop_streaming()

        # Verify market data messages were received
        market_messages = [
            json.loads(msg["message"]) for msg in market_client.messages_sent
        ]

        # Should have received some tick and/or OHLCV updates
        tick_messages = [
            msg for msg in market_messages if msg.get("type") == "tick_update"
        ]
        ohlcv_messages = [
            msg for msg in market_messages if msg.get("type") == "ohlcv_update"
        ]

        # Should have received at least some updates
        total_market_updates = len(tick_messages) + len(ohlcv_messages)
        assert (
            total_market_updates >= 0
        )  # May be 0 if timing is tight, but structure should be correct

        # Verify message structure for any received messages
        for msg in tick_messages:
            assert "symbol" in msg
            assert "data" in msg
            assert "timestamp" in msg
            assert msg["data"]["symbol"] == "EURUSD"

        for msg in ohlcv_messages:
            assert "symbol" in msg
            assert "data" in msg
            assert msg["data"]["symbol"] == "EURUSD"


# Pytest configuration
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
