"""TDD Tests for WebSocket Market Data Streaming Enhancements.

Following Test-Driven Development approach:
1. Write failing tests first
2. Implement minimal code to pass tests
3. Refactor for performance and maintainability
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets
from websockets.exceptions import ConnectionClosed

from fxml4.api.websocket_market_data import (
    HistoricalDataMerger,
    MarketDataSubscriptionManager,
    OHLCBarAggregator,
    PriceFeedMonitor,
    WebSocketMarketDataManager,
)
from fxml4.brokers.adapters.message_translator import get_message_translator


class MockWebSocket:
    """Mock WebSocket connection for testing."""

    def __init__(self, client_id: str = None):
        self.client_id = client_id or f"client_{id(self)}"
        self.closed = False
        self.messages_sent = []
        self.subscriptions = set()

    async def send(self, message: str):
        """Mock send method."""
        if self.closed:
            raise ConnectionClosed(None, None)
        self.messages_sent.append(
            {"message": json.loads(message), "timestamp": datetime.utcnow()}
        )

    async def close(self):
        """Mock close method."""
        self.closed = True

    @property
    def remote_address(self):
        return ("127.0.0.1", 12345)


@pytest.fixture
def mock_websockets():
    """Create multiple mock WebSocket connections."""
    return [MockWebSocket(f"client_{i}") for i in range(3)]


@pytest.fixture
def market_data_manager():
    """Create WebSocket market data manager for testing."""
    return WebSocketMarketDataManager()


@pytest.fixture
def subscription_manager():
    """Create subscription manager for testing."""
    return MarketDataSubscriptionManager()


@pytest.fixture
def ohlc_aggregator():
    """Create OHLC bar aggregator for testing."""
    return OHLCBarAggregator()


@pytest.fixture
def price_feed_monitor():
    """Create price feed monitor for testing."""
    return PriceFeedMonitor()


@pytest.fixture
def sample_tick_data():
    """Generate sample tick data for testing."""
    base_time = datetime.utcnow()
    return [
        {
            "symbol": "EURUSD",
            "bid": 1.1234,
            "ask": 1.1236,
            "timestamp": (base_time + timedelta(seconds=i)).isoformat(),
        }
        for i in range(60)  # 60 seconds of tick data
    ]


@pytest.mark.asyncio
class TestWebSocketMarketDataBroadcasting:
    """TDD tests for WebSocket market data broadcasting functionality."""

    async def test_websocket_manager_initialization(self, market_data_manager):
        """Test WebSocket manager initializes correctly."""
        assert market_data_manager is not None
        assert market_data_manager.active_connections == 0
        assert len(market_data_manager.connections) == 0

    async def test_client_connection_registration(
        self, market_data_manager, mock_websockets
    ):
        """Test client WebSocket connections can be registered."""
        # Initially no connections
        assert market_data_manager.active_connections == 0

        # Register clients
        for ws in mock_websockets:
            await market_data_manager.register_client(ws)

        # Verify connections registered
        assert market_data_manager.active_connections == len(mock_websockets)

        # Verify each client is tracked
        for ws in mock_websockets:
            assert ws.client_id in market_data_manager.connections

    async def test_client_connection_cleanup_on_disconnect(
        self, market_data_manager, mock_websockets
    ):
        """Test clients are cleaned up when they disconnect."""
        # Register clients
        for ws in mock_websockets:
            await market_data_manager.register_client(ws)

        initial_count = market_data_manager.active_connections

        # Disconnect one client
        disconnected_client = mock_websockets[0]
        await market_data_manager.unregister_client(disconnected_client.client_id)

        # Verify client was removed
        assert market_data_manager.active_connections == initial_count - 1
        assert disconnected_client.client_id not in market_data_manager.connections

    async def test_market_data_broadcast_to_all_clients(
        self, market_data_manager, mock_websockets
    ):
        """Test market data is broadcast to all connected clients."""
        # Register clients
        for ws in mock_websockets:
            await market_data_manager.register_client(ws)

        # Create test market data update
        market_update = {
            "type": "price_update",
            "symbol": "EURUSD",
            "bid": 1.1234,
            "ask": 1.1236,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Broadcast update
        await market_data_manager.broadcast_to_all(market_update)

        # Verify all clients received the message
        for ws in mock_websockets:
            assert len(ws.messages_sent) == 1
            sent_message = ws.messages_sent[0]["message"]
            assert sent_message["symbol"] == "EURUSD"
            assert sent_message["bid"] == 1.1234
            assert sent_message["ask"] == 1.1236

    async def test_selective_broadcast_by_symbol_subscription(
        self, market_data_manager, mock_websockets
    ):
        """Test market data is only sent to clients subscribed to specific symbols."""
        # Register clients with different subscriptions
        await market_data_manager.register_client(mock_websockets[0])
        await market_data_manager.subscribe_client_to_symbol(
            mock_websockets[0].client_id, "EURUSD"
        )

        await market_data_manager.register_client(mock_websockets[1])
        await market_data_manager.subscribe_client_to_symbol(
            mock_websockets[1].client_id, "GBPUSD"
        )

        await market_data_manager.register_client(mock_websockets[2])
        await market_data_manager.subscribe_client_to_symbol(
            mock_websockets[2].client_id, "EURUSD"
        )

        # Broadcast EURUSD update
        eurusd_update = {
            "type": "price_update",
            "symbol": "EURUSD",
            "bid": 1.1234,
            "ask": 1.1236,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await market_data_manager.broadcast_to_symbol_subscribers(
            "EURUSD", eurusd_update
        )

        # Verify only EURUSD subscribers received the message
        assert len(mock_websockets[0].messages_sent) == 1  # Subscribed to EURUSD
        assert len(mock_websockets[1].messages_sent) == 0  # Subscribed to GBPUSD
        assert len(mock_websockets[2].messages_sent) == 1  # Subscribed to EURUSD

    async def test_websocket_connection_error_handling(
        self, market_data_manager, mock_websockets
    ):
        """Test WebSocket manager handles connection errors gracefully."""
        # Register clients
        for ws in mock_websockets:
            await market_data_manager.register_client(ws)

        # Simulate one client disconnecting ungracefully
        mock_websockets[1].closed = True

        # Broadcast should continue working for healthy connections
        market_update = {
            "type": "price_update",
            "symbol": "GBPUSD",
            "bid": 1.2500,
            "ask": 1.2502,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await market_data_manager.broadcast_to_all(market_update)

        # Healthy clients should receive message
        assert len(mock_websockets[0].messages_sent) == 1
        assert len(mock_websockets[2].messages_sent) == 1

        # Disconnected client should be automatically removed
        assert mock_websockets[1].client_id not in market_data_manager.connections
        assert market_data_manager.active_connections == 2

    async def test_market_data_message_formatting(
        self, market_data_manager, mock_websockets
    ):
        """Test market data messages are properly formatted for WebSocket clients."""
        await market_data_manager.register_client(mock_websockets[0])

        # Test different types of market data
        test_cases = [
            # Basic price update
            {
                "input": {"symbol": "EURUSD", "bid": 1.1234, "ask": 1.1236},
                "expected_fields": ["type", "symbol", "bid", "ask", "timestamp"],
            },
            # Price update with spread
            {
                "input": {
                    "symbol": "GBPUSD",
                    "bid": 1.2500,
                    "ask": 1.2503,
                    "spread": 0.0003,
                },
                "expected_fields": [
                    "type",
                    "symbol",
                    "bid",
                    "ask",
                    "spread",
                    "timestamp",
                ],
            },
            # Price update with volume
            {
                "input": {
                    "symbol": "USDJPY",
                    "bid": 110.45,
                    "ask": 110.47,
                    "volume": 1000000,
                },
                "expected_fields": [
                    "type",
                    "symbol",
                    "bid",
                    "ask",
                    "volume",
                    "timestamp",
                ],
            },
        ]

        for test_case in test_cases:
            await market_data_manager.broadcast_to_all(test_case["input"])

            # Get the last sent message
            sent_message = mock_websockets[0].messages_sent[-1]["message"]

            # Verify all expected fields are present
            for field in test_case["expected_fields"]:
                assert field in sent_message, f"Missing field: {field}"

            # Verify timestamp is recent
            msg_timestamp = datetime.fromisoformat(
                sent_message["timestamp"].replace("Z", "+00:00")
            )
            assert (
                datetime.utcnow() - msg_timestamp.replace(tzinfo=None)
            ).total_seconds() < 1


@pytest.mark.asyncio
class TestMarketDataSubscriptionManagement:
    """TDD tests for market data subscription management."""

    async def test_subscription_manager_initialization(self, subscription_manager):
        """Test subscription manager initializes correctly."""
        assert subscription_manager is not None
        assert len(subscription_manager.subscriptions) == 0
        assert len(subscription_manager.symbol_subscribers) == 0

    async def test_client_symbol_subscription(self, subscription_manager):
        """Test clients can subscribe to specific symbols."""
        client_id = "test_client_001"
        symbol = "EURUSD"

        # Initially no subscriptions
        assert not subscription_manager.is_client_subscribed_to_symbol(
            client_id, symbol
        )

        # Subscribe client to symbol
        await subscription_manager.subscribe_client_to_symbol(client_id, symbol)

        # Verify subscription
        assert subscription_manager.is_client_subscribed_to_symbol(client_id, symbol)
        assert symbol in subscription_manager.get_client_subscriptions(client_id)
        assert client_id in subscription_manager.get_symbol_subscribers(symbol)

    async def test_client_symbol_unsubscription(self, subscription_manager):
        """Test clients can unsubscribe from symbols."""
        client_id = "test_client_002"
        symbol = "GBPUSD"

        # Subscribe first
        await subscription_manager.subscribe_client_to_symbol(client_id, symbol)
        assert subscription_manager.is_client_subscribed_to_symbol(client_id, symbol)

        # Unsubscribe
        await subscription_manager.unsubscribe_client_from_symbol(client_id, symbol)

        # Verify unsubscription
        assert not subscription_manager.is_client_subscribed_to_symbol(
            client_id, symbol
        )
        assert symbol not in subscription_manager.get_client_subscriptions(client_id)
        assert client_id not in subscription_manager.get_symbol_subscribers(symbol)

    async def test_multiple_symbol_subscriptions_per_client(self, subscription_manager):
        """Test clients can subscribe to multiple symbols."""
        client_id = "test_client_003"
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]

        # Subscribe to multiple symbols
        for symbol in symbols:
            await subscription_manager.subscribe_client_to_symbol(client_id, symbol)

        # Verify all subscriptions
        client_subscriptions = subscription_manager.get_client_subscriptions(client_id)
        assert len(client_subscriptions) == len(symbols)
        for symbol in symbols:
            assert symbol in client_subscriptions
            assert subscription_manager.is_client_subscribed_to_symbol(
                client_id, symbol
            )

    async def test_multiple_clients_per_symbol(self, subscription_manager):
        """Test multiple clients can subscribe to the same symbol."""
        symbol = "EURUSD"
        client_ids = ["client_001", "client_002", "client_003"]

        # Subscribe multiple clients to same symbol
        for client_id in client_ids:
            await subscription_manager.subscribe_client_to_symbol(client_id, symbol)

        # Verify all subscriptions
        symbol_subscribers = subscription_manager.get_symbol_subscribers(symbol)
        assert len(symbol_subscribers) == len(client_ids)
        for client_id in client_ids:
            assert client_id in symbol_subscribers
            assert subscription_manager.is_client_subscribed_to_symbol(
                client_id, symbol
            )

    async def test_client_cleanup_removes_all_subscriptions(self, subscription_manager):
        """Test removing client cleans up all their subscriptions."""
        client_id = "test_client_004"
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]

        # Subscribe to multiple symbols
        for symbol in symbols:
            await subscription_manager.subscribe_client_to_symbol(client_id, symbol)

        # Verify subscriptions exist
        assert len(subscription_manager.get_client_subscriptions(client_id)) == len(
            symbols
        )

        # Remove client
        await subscription_manager.remove_client(client_id)

        # Verify all subscriptions are cleaned up
        assert len(subscription_manager.get_client_subscriptions(client_id)) == 0
        for symbol in symbols:
            assert client_id not in subscription_manager.get_symbol_subscribers(symbol)

    async def test_subscription_statistics(self, subscription_manager):
        """Test subscription manager provides useful statistics."""
        # Add some subscriptions
        clients = ["client_001", "client_002", "client_003"]
        symbols = ["EURUSD", "GBPUSD"]

        for client_id in clients:
            for symbol in symbols:
                await subscription_manager.subscribe_client_to_symbol(client_id, symbol)

        # Get statistics
        stats = subscription_manager.get_subscription_stats()

        # Verify statistics
        assert stats["total_clients"] == len(clients)
        assert stats["total_symbols"] == len(symbols)
        assert stats["total_subscriptions"] == len(clients) * len(symbols)
        assert "most_subscribed_symbol" in stats
        assert "client_subscription_counts" in stats


@pytest.mark.asyncio
class TestIntegrationWithForexConnectBridge:
    """TDD tests for integration between WebSocket streaming and ForexConnect bridge."""

    async def test_bridge_market_data_triggers_websocket_broadcast(
        self, market_data_manager, mock_websockets
    ):
        """Test market data from bridge triggers WebSocket broadcasts."""
        # Register WebSocket clients
        for ws in mock_websockets:
            await market_data_manager.register_client(ws)
            await market_data_manager.subscribe_client_to_symbol(ws.client_id, "EURUSD")

        # Simulate market data from ForexConnect bridge
        forex_market_data = {
            "type": "price_update",
            "instrument": "EUR/USD",  # ForexConnect format
            "bid": 1.1234,
            "ask": 1.1236,
            "timestamp": datetime.utcnow().isoformat(),
            "digits": 5,
        }

        # Process through message translator and broadcast
        translator = get_message_translator()
        fxml4_market_data = translator.translate_market_data_to_fxml(forex_market_data)

        await market_data_manager.broadcast_to_symbol_subscribers(
            "EURUSD", fxml4_market_data
        )

        # Verify all subscribed clients received the update
        for ws in mock_websockets:
            assert len(ws.messages_sent) == 1
            message = ws.messages_sent[0]["message"]
            assert message["symbol"] == "EURUSD"
            assert message["bid_price"] == 1.1234
            assert message["ask_price"] == 1.1236

    async def test_websocket_subscription_changes_affect_bridge_subscriptions(
        self, market_data_manager, subscription_manager
    ):
        """Test WebSocket client subscriptions influence bridge subscriptions."""
        # This test ensures the bridge only subscribes to symbols that WebSocket clients want

        # Initially no bridge subscriptions should be active
        bridge_subscriptions = (
            await market_data_manager.get_active_bridge_subscriptions()
        )
        assert len(bridge_subscriptions) == 0

        # Add WebSocket client subscriptions
        await subscription_manager.subscribe_client_to_symbol("client_001", "EURUSD")
        await subscription_manager.subscribe_client_to_symbol("client_002", "GBPUSD")

        # Update bridge subscriptions based on WebSocket demand
        await market_data_manager.sync_bridge_subscriptions_with_websocket_demand(
            subscription_manager
        )

        # Verify bridge now subscribes to requested symbols
        bridge_subscriptions = (
            await market_data_manager.get_active_bridge_subscriptions()
        )
        assert "EURUSD" in bridge_subscriptions
        assert "GBPUSD" in bridge_subscriptions

        # Remove WebSocket subscription
        await subscription_manager.unsubscribe_client_from_symbol(
            "client_002", "GBPUSD"
        )
        await market_data_manager.sync_bridge_subscriptions_with_websocket_demand(
            subscription_manager
        )

        # Verify bridge unsubscribes from unused symbols
        bridge_subscriptions = (
            await market_data_manager.get_active_bridge_subscriptions()
        )
        assert "EURUSD" in bridge_subscriptions
        assert "GBPUSD" not in bridge_subscriptions


if __name__ == "__main__":
    """Run WebSocket market data streaming tests."""
    pytest.main([__file__, "-v"])
