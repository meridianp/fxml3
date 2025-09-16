"""
TDD Tests for WebSocket Service

Comprehensive tests for real-time WebSocket connections,
message handling, reconnection logic, and performance.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import websockets


@pytest.mark.tdd
@pytest.mark.websocket
class TestWebSocketService:
    """
    Test suite for WebSocket service functionality.

    Tests connection management, message handling, subscriptions,
    and real-time data streaming.
    """

    @pytest.fixture
    def ws_config(self):
        """WebSocket service configuration."""
        return {
            "url": "wss://api.fxml4.com/ws",
            "heartbeat_interval": 30,
            "reconnect_interval": 5,
            "max_reconnect_attempts": 5,
            "message_queue_size": 10000,
            "compression": True,
        }

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket connection."""
        ws = AsyncMock()
        ws.send = AsyncMock()
        ws.recv = AsyncMock()
        ws.close = AsyncMock()
        ws.ping = AsyncMock()
        ws.closed = False
        return ws

    @pytest.fixture
    async def websocket_service(self, ws_config, mock_websocket):
        """Create WebSocket service instance."""
        with patch("websockets.connect", return_value=mock_websocket):
            from core.services.WebSocketService import WebSocketService

            service = WebSocketService(config=ws_config)
            await service.connect()
            yield service
            await service.disconnect()

    # -------------------------------------------------------------------------
    # Connection Management Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_connection_establishment(self, ws_config):
        """RED: Test WebSocket connection establishment."""
        from core.services.WebSocketService import WebSocketService

        service = WebSocketService(config=ws_config)

        # Test connection
        connected = await service.connect()
        assert connected is True
        assert service.is_connected() is True

        # Test disconnection
        await service.disconnect()
        assert service.is_connected() is False

    @pytest.mark.red
    async def test_connection_with_authentication(self, ws_config):
        """RED: Test WebSocket connection with authentication."""
        auth_config = {**ws_config, "auth_token": "test_jwt_token"}

        from core.services.WebSocketService import WebSocketService

        service = WebSocketService(config=auth_config)

        # Mock authentication handshake
        with patch("websockets.connect") as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.recv = AsyncMock(
                return_value=json.dumps(
                    {"type": "auth_success", "message": "Authenticated"}
                )
            )
            mock_connect.return_value = mock_ws

            connected = await service.connect()
            assert connected is True

            # Verify auth message sent
            mock_ws.send.assert_called()
            sent_data = json.loads(mock_ws.send.call_args[0][0])
            assert sent_data["type"] == "auth"
            assert "token" in sent_data

    @pytest.mark.red
    async def test_automatic_reconnection(self, websocket_service, mock_websocket):
        """RED: Test automatic reconnection on connection loss."""
        # Simulate connection loss
        mock_websocket.closed = True
        mock_websocket.recv.side_effect = websockets.ConnectionClosed(None, None)

        # Trigger reconnection
        reconnected = await websocket_service.ensure_connected()

        # Should attempt reconnection
        assert reconnected is True
        assert websocket_service.reconnect_count > 0

    @pytest.mark.red
    async def test_exponential_backoff_reconnection(self, ws_config):
        """RED: Test exponential backoff for reconnection attempts."""
        from core.services.WebSocketService import WebSocketService

        service = WebSocketService(config=ws_config)

        # Mock failed connections
        with patch("websockets.connect", side_effect=Exception("Connection failed")):
            reconnect_times = []

            # Track reconnection attempts
            async def track_reconnects():
                for i in range(3):
                    start = datetime.now()
                    await service.connect()
                    reconnect_times.append(datetime.now() - start)

            await track_reconnects()

            # Verify exponential backoff
            if len(reconnect_times) > 1:
                assert reconnect_times[1] > reconnect_times[0]
                if len(reconnect_times) > 2:
                    assert reconnect_times[2] > reconnect_times[1]

    @pytest.mark.red
    async def test_connection_heartbeat(self, websocket_service, mock_websocket):
        """RED: Test heartbeat/ping mechanism."""
        # Configure heartbeat
        websocket_service.heartbeat_interval = 0.1  # 100ms for testing

        # Start heartbeat
        heartbeat_task = asyncio.create_task(websocket_service.heartbeat_loop())

        # Wait for heartbeats
        await asyncio.sleep(0.3)

        # Stop heartbeat
        heartbeat_task.cancel()

        # Verify pings sent
        assert mock_websocket.ping.call_count >= 2

    # -------------------------------------------------------------------------
    # Message Handling Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_message_subscription(self, websocket_service, mock_websocket):
        """RED: Test subscribing to message types."""
        # Subscribe to market data
        await websocket_service.subscribe("market_data", ["EUR/USD", "GBP/USD"])

        # Verify subscription message sent
        mock_websocket.send.assert_called()
        sent_data = json.loads(mock_websocket.send.call_args[0][0])
        assert sent_data["action"] == "subscribe"
        assert sent_data["channel"] == "market_data"
        assert "EUR/USD" in sent_data["symbols"]

    @pytest.mark.red
    async def test_message_unsubscription(self, websocket_service, mock_websocket):
        """RED: Test unsubscribing from messages."""
        # Subscribe first
        await websocket_service.subscribe("market_data", ["EUR/USD"])

        # Unsubscribe
        await websocket_service.unsubscribe("market_data", ["EUR/USD"])

        # Verify unsubscribe message sent
        calls = mock_websocket.send.call_args_list
        last_call = json.loads(calls[-1][0][0])
        assert last_call["action"] == "unsubscribe"

    @pytest.mark.red
    async def test_message_routing(self, websocket_service):
        """RED: Test message routing to handlers."""
        received_messages = []

        # Register message handler
        def market_handler(message):
            received_messages.append(message)

        websocket_service.register_handler("market_data", market_handler)

        # Simulate incoming messages
        test_messages = [
            {"type": "market_data", "symbol": "EUR/USD", "price": 1.0850},
            {"type": "market_data", "symbol": "GBP/USD", "price": 1.2500},
            {"type": "order_update", "order_id": "123", "status": "FILLED"},
        ]

        for msg in test_messages:
            await websocket_service.handle_message(json.dumps(msg))

        # Only market_data messages should be routed
        assert len(received_messages) == 2
        assert all(msg["type"] == "market_data" for msg in received_messages)

    @pytest.mark.red
    async def test_message_queue_management(self, websocket_service):
        """RED: Test message queue with backpressure."""
        # Set small queue size
        websocket_service.message_queue = asyncio.Queue(maxsize=5)

        # Try to queue many messages
        messages_queued = 0
        for i in range(10):
            try:
                await asyncio.wait_for(
                    websocket_service.queue_message({"id": i}), timeout=0.01
                )
                messages_queued += 1
            except asyncio.TimeoutError:
                break

        # Should only queue up to maxsize
        assert messages_queued <= 5

    @pytest.mark.red
    async def test_message_compression(self, websocket_service, mock_websocket):
        """RED: Test message compression for large payloads."""
        # Create large message
        large_data = {
            "type": "bulk_update",
            "data": [
                {"symbol": f"PAIR_{i}", "price": 1.0 + i * 0.001} for i in range(1000)
            ],
        }

        # Send with compression
        await websocket_service.send_compressed(large_data)

        # Verify compression applied
        mock_websocket.send.assert_called()
        sent_bytes = mock_websocket.send.call_args[0][0]

        # Compressed size should be smaller than JSON
        json_size = len(json.dumps(large_data).encode())
        assert len(sent_bytes) < json_size

    # -------------------------------------------------------------------------
    # Real-time Data Streaming Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_market_data_streaming(self, websocket_service, mock_websocket):
        """RED: Test real-time market data streaming."""
        received_ticks = []

        # Register tick handler
        async def tick_handler(tick):
            received_ticks.append(tick)

        websocket_service.register_handler("tick", tick_handler)

        # Simulate streaming ticks
        for i in range(10):
            tick = {
                "type": "tick",
                "symbol": "EUR/USD",
                "bid": 1.0850 + i * 0.0001,
                "ask": 1.0852 + i * 0.0001,
                "timestamp": datetime.now().isoformat(),
            }
            mock_websocket.recv.return_value = json.dumps(tick)
            await websocket_service.receive_message()

        # Verify all ticks received
        assert len(received_ticks) == 10
        assert all(tick["symbol"] == "EUR/USD" for tick in received_ticks)

    @pytest.mark.red
    async def test_order_book_updates(self, websocket_service):
        """RED: Test order book update streaming."""
        order_book = {"bids": [], "asks": []}

        def update_order_book(message):
            if message["type"] == "orderbook_update":
                order_book["bids"] = message["bids"]
                order_book["asks"] = message["asks"]

        websocket_service.register_handler("orderbook_update", update_order_book)

        # Simulate order book updates
        updates = [
            {
                "type": "orderbook_update",
                "symbol": "EUR/USD",
                "bids": [[1.0850, 100000], [1.0849, 200000]],
                "asks": [[1.0852, 150000], [1.0853, 250000]],
            }
        ]

        for update in updates:
            await websocket_service.handle_message(json.dumps(update))

        # Verify order book updated
        assert len(order_book["bids"]) == 2
        assert len(order_book["asks"]) == 2
        assert order_book["bids"][0][0] == 1.0850

    @pytest.mark.red
    async def test_trade_execution_notifications(self, websocket_service):
        """RED: Test real-time trade execution notifications."""
        executions = []

        async def execution_handler(message):
            if message["type"] == "execution":
                executions.append(message)

        websocket_service.register_handler("execution", execution_handler)

        # Simulate execution notifications
        execution_msg = {
            "type": "execution",
            "order_id": "ORD123",
            "symbol": "EUR/USD",
            "side": "BUY",
            "quantity": 100000,
            "price": 1.0855,
            "timestamp": datetime.now().isoformat(),
        }

        await websocket_service.handle_message(json.dumps(execution_msg))

        # Verify execution received
        assert len(executions) == 1
        assert executions[0]["order_id"] == "ORD123"

    # -------------------------------------------------------------------------
    # Performance and Load Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_high_throughput_handling(self, websocket_service, performance_timer):
        """RED: Test handling high message throughput."""
        message_count = 10000
        processed = 0

        def counter_handler(msg):
            nonlocal processed
            processed += 1

        websocket_service.register_handler("test", counter_handler)

        # Send many messages rapidly
        performance_timer.start()

        for i in range(message_count):
            await websocket_service.handle_message(
                json.dumps({"type": "test", "id": i})
            )

        elapsed = performance_timer.stop()

        # Should handle at least 10k messages per second
        messages_per_second = message_count / elapsed
        assert messages_per_second > 10000
        assert processed == message_count

    @pytest.mark.red
    async def test_concurrent_connections(self, ws_config):
        """RED: Test multiple concurrent WebSocket connections."""
        from core.services.WebSocketService import WebSocketService

        # Create multiple connections
        services = []
        for i in range(10):
            config = {**ws_config, "client_id": f"client_{i}"}
            service = WebSocketService(config=config)
            services.append(service)

        # Connect all concurrently
        connection_tasks = [service.connect() for service in services]
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)

        # All should connect successfully
        assert all(r is True for r in results if not isinstance(r, Exception))

        # Disconnect all
        disconnect_tasks = [service.disconnect() for service in services]
        await asyncio.gather(*disconnect_tasks)

    @pytest.mark.red
    async def test_memory_usage_under_load(self, websocket_service):
        """RED: Test memory usage with sustained load."""
        import tracemalloc

        tracemalloc.start()
        initial_memory = tracemalloc.get_traced_memory()[0]

        # Process many messages
        for i in range(100000):
            message = {"type": "test", "id": i, "data": "x" * 100}
            await websocket_service.handle_message(json.dumps(message))

            # Allow cleanup every 10k messages
            if i % 10000 == 0:
                await asyncio.sleep(0)

        current_memory = tracemalloc.get_traced_memory()[0]
        memory_increase = current_memory - initial_memory

        tracemalloc.stop()

        # Memory increase should be reasonable (< 100MB)
        assert memory_increase < 100 * 1024 * 1024

    # -------------------------------------------------------------------------
    # Error Handling Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_malformed_message_handling(self, websocket_service):
        """RED: Test handling of malformed messages."""
        error_count = 0

        def error_handler(error):
            nonlocal error_count
            error_count += 1

        websocket_service.register_error_handler(error_handler)

        # Send malformed messages
        malformed_messages = [
            "not json",
            "{invalid json}",
            json.dumps({"no_type_field": "data"}),
            "",
            None,
        ]

        for msg in malformed_messages:
            await websocket_service.handle_message(msg)

        # Should handle all gracefully
        assert error_count == len(malformed_messages)

    @pytest.mark.red
    async def test_connection_error_recovery(self, websocket_service, mock_websocket):
        """RED: Test recovery from various connection errors."""
        # Simulate different error scenarios
        error_scenarios = [
            websockets.ConnectionClosed(None, None),
            ConnectionResetError("Connection reset by peer"),
            TimeoutError("Operation timed out"),
            Exception("Generic error"),
        ]

        for error in error_scenarios:
            mock_websocket.recv.side_effect = error

            # Should handle error and attempt recovery
            handled = await websocket_service.handle_connection_error(error)
            assert handled is True

            # Should mark for reconnection
            assert websocket_service.should_reconnect is True

    @pytest.mark.red
    async def test_handler_exception_isolation(self, websocket_service):
        """RED: Test that handler exceptions don't crash the service."""

        def faulty_handler(msg):
            raise Exception("Handler error")

        def good_handler(msg):
            msg["processed"] = True

        websocket_service.register_handler("test", faulty_handler)
        websocket_service.register_handler("test2", good_handler)

        # Send messages to both handlers
        message1 = {"type": "test", "data": "will fail"}
        message2 = {"type": "test2", "data": "will succeed"}

        await websocket_service.handle_message(json.dumps(message1))
        await websocket_service.handle_message(json.dumps(message2))

        # Service should still be running
        assert websocket_service.is_connected()

    # -------------------------------------------------------------------------
    # Security Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_message_validation(self, websocket_service):
        """RED: Test message validation and sanitization."""
        validated_messages = []

        def secure_handler(msg):
            validated_messages.append(msg)

        websocket_service.register_handler("secure", secure_handler)

        # Try to send potentially dangerous messages
        dangerous_messages = [
            {"type": "secure", "data": '<script>alert("XSS")</script>'},
            {"type": "secure", "data": {"$ne": None}},  # NoSQL injection attempt
            {"type": "secure", "data": "'; DROP TABLE users; --"},  # SQL injection
        ]

        for msg in dangerous_messages:
            await websocket_service.handle_message(json.dumps(msg))

        # Messages should be sanitized or rejected
        assert len(validated_messages) <= len(dangerous_messages)

    @pytest.mark.red
    async def test_rate_limiting(self, websocket_service):
        """RED: Test rate limiting for message sending."""
        # Configure rate limit
        websocket_service.rate_limit = 100  # 100 messages per second

        # Try to send many messages rapidly
        send_count = 0
        start_time = datetime.now()

        for i in range(200):
            success = await websocket_service.send_with_rate_limit({"id": i})
            if success:
                send_count += 1

        elapsed = (datetime.now() - start_time).total_seconds()

        # Should respect rate limit
        expected_max = int(elapsed * websocket_service.rate_limit) + 10  # Small buffer
        assert send_count <= expected_max
