"""
TDD Tests for Real-Time WebSocket Market Data Pipeline

Following the FXML4 TDD Action Plan - High Priority Task 1:
Implement WebSocket market data streaming tests and infrastructure

Test Categories:
- Connection establishment and management
- Real-time price streaming with sub-millisecond latency
- Auto-reconnection and failover logic
- Load testing for 1000+ concurrent connections
- Data validation and error handling

Following strict Red-Green-Refactor TDD methodology.
"""

import asyncio
import json
import pytest
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

from core.api.websocket_market_data import (
    WebSocketMarketDataManager,
    TickData,
    TimeFrame,
    OHLCBarAggregator,
    FeedFailoverManager,
    PriceFeedMonitor,
    FeedSource,
    FeedStatus,
    MarketDataSubscriptionManager,
)


class MockWebSocketConnection:
    """Mock WebSocket connection for testing."""

    def __init__(self, client_id: str = None, should_fail: bool = False):
        self.client_id = client_id or f"client_{id(self)}"
        self.connected = True
        self.should_fail = should_fail
        self.messages_sent = []
        self.close_called = False
        self.connection_time = time.time()

    async def send(self, message: str):
        """Send message to WebSocket."""
        if not self.connected or self.should_fail:
            raise ConnectionError("WebSocket connection failed")

        self.messages_sent.append(
            {
                "data": json.loads(message),
                "timestamp": time.time(),
                "send_time": time.time(),
            }
        )

    async def close(self):
        """Close WebSocket connection."""
        self.connected = False
        self.close_called = True

    def get_messages(self) -> List[Dict]:
        """Get all sent messages."""
        return self.messages_sent

    def get_price_messages(self) -> List[Dict]:
        """Get only price update messages (filter out connection confirmations)."""
        return [
            msg
            for msg in self.messages_sent
            if msg.get("data", {}).get("type") != "connection_confirmed"
        ]

    def clear_messages(self):
        """Clear all messages."""
        self.messages_sent.clear()


class MockTimescaleDBPool:
    """Mock TimescaleDB connection pool."""

    def __init__(self):
        self.connected = True
        self.queries_executed = []

    async def fetch(self, query: str, *params):
        """Mock fetch method."""
        self.queries_executed.append({"query": query, "params": params})
        return []

    async def execute(self, query: str, *params):
        """Mock execute method."""
        self.queries_executed.append({"query": query, "params": params})
        return "OK"


@pytest.fixture
def websocket_manager():
    """Create WebSocket manager for testing."""
    return WebSocketMarketDataManager()


@pytest.fixture
def mock_connections():
    """Create multiple mock WebSocket connections."""
    return [MockWebSocketConnection(f"client_{i}") for i in range(5)]


@pytest.fixture
def sample_market_data():
    """Generate realistic market data for testing."""
    base_time = datetime.utcnow()
    return [
        {
            "symbol": "EUR/USD",
            "bid": 1.0850 + (i * 0.0001),
            "ask": 1.0852 + (i * 0.0001),
            "timestamp": (base_time + timedelta(milliseconds=i * 100)).isoformat(),
            "volume": 100000,
        }
        for i in range(1000)  # 100 seconds of data at 10Hz
    ]


# =============================================================================
# RED PHASE TESTS - Connection Establishment and Management
# =============================================================================


class TestWebSocketConnectionEstablishment:
    """Test WebSocket connection establishment following TDD Action Plan."""

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_websocket_connection_establishes_within_100ms(
        self, websocket_manager
    ):
        """
        RED: WebSocket connection should establish within 100ms for authenticated trader.

        Business Rule: Professional traders require ultra-low latency connections.
        Performance Target: Connection establishment < 100ms
        """
        # Arrange
        mock_websocket = MockWebSocketConnection("trader_123")
        start_time = time.time()

        # Act
        await websocket_manager.register_client(mock_websocket)
        connection_time = time.time() - start_time

        # Assert - Will fail initially until implementation
        assert connection_time < 0.1  # 100ms requirement
        assert websocket_manager.active_connections == 1
        assert mock_websocket.client_id in websocket_manager.connections

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_connection_confirmation_message_sent(self, websocket_manager):
        """
        RED: Client should receive connection confirmation message.

        Acceptance Criteria: Connection confirmation contains client_id and status.
        """
        # Arrange
        mock_websocket = MockWebSocketConnection("trader_456")

        # Act
        await websocket_manager.register_client(mock_websocket)

        # Assert - Will fail until confirmation message implemented
        messages = mock_websocket.get_messages()
        assert len(messages) == 1

        confirmation = messages[0]["data"]
        assert confirmation["type"] == "connection_confirmed"
        assert confirmation["client_id"] == "trader_456"
        assert confirmation["status"] == "connected"
        assert "timestamp" in confirmation

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_handles_1000_concurrent_connections(self, websocket_manager):
        """
        RED: System should handle 1000+ concurrent connections.

        Performance Requirement: Support high-frequency trading infrastructure.
        Load Target: 1000+ simultaneous WebSocket connections.
        """
        # Arrange
        connections = [MockWebSocketConnection(f"client_{i}") for i in range(1000)]
        start_time = time.time()

        # Act
        registration_tasks = []
        for conn in connections:
            task = websocket_manager.register_client(conn)
            registration_tasks.append(task)

        await asyncio.gather(*registration_tasks)
        registration_time = time.time() - start_time

        # Assert - Will fail until scalable implementation
        assert websocket_manager.active_connections == 1000
        assert registration_time < 5.0  # Should register 1000 clients within 5 seconds

        # Verify all connections are tracked
        for conn in connections:
            assert conn.client_id in websocket_manager.connections


# =============================================================================
# RED PHASE TESTS - Real-Time Price Streaming
# =============================================================================


class TestRealTimePriceStreaming:
    """Test real-time price streaming with sub-millisecond latency."""

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_price_updates_stream_within_1ms(self, websocket_manager):
        """
        RED: Price updates should be delivered within 1ms of reception.

        Business Critical: Sub-millisecond latency for competitive advantage.
        Performance Target: < 1ms latency for price distribution.
        """
        # Arrange
        mock_websocket = MockWebSocketConnection("hft_trader")
        await websocket_manager.register_client(mock_websocket)
        await websocket_manager.subscribe_client_to_symbol("hft_trader", "EUR/USD")

        price_update = {
            "symbol": "EUR/USD",
            "bid": 1.0850,
            "ask": 1.0852,
            "volume": 100000,
        }

        # Act
        start_time = time.time()
        await websocket_manager.broadcast_to_symbol_subscribers("EUR/USD", price_update)
        end_time = time.time()

        latency_ms = (end_time - start_time) * 1000

        # Assert - Will fail until optimized implementation
        assert latency_ms < 1.0  # Sub-millisecond requirement

        messages = mock_websocket.get_messages()
        assert len(messages) == 1
        assert messages[0]["data"]["symbol"] == "EUR/USD"
        assert messages[0]["data"]["bid"] == 1.0850

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_price_updates_contain_required_fields(self, websocket_manager):
        """
        RED: Price updates must contain bid, ask, timestamp, and symbol.

        Compliance Requirement: All price data must include regulatory fields.
        """
        # Arrange
        mock_websocket = MockWebSocketConnection("compliance_trader")
        await websocket_manager.register_client(mock_websocket)
        await websocket_manager.subscribe_client_to_symbol(
            "compliance_trader", "GBP/USD"
        )

        price_update = {"symbol": "GBP/USD", "bid": 1.2650, "ask": 1.2652}

        # Act
        await websocket_manager.broadcast_to_symbol_subscribers("GBP/USD", price_update)

        # Assert - Will fail until field validation implemented
        messages = mock_websocket.get_messages()
        received_data = messages[0]["data"]

        # Required fields for regulatory compliance
        assert "symbol" in received_data
        assert "bid" in received_data
        assert "ask" in received_data
        assert "timestamp" in received_data
        assert "type" in received_data

        # Validate data types
        assert isinstance(received_data["bid"], float)
        assert isinstance(received_data["ask"], float)
        assert received_data["ask"] > received_data["bid"]  # Ask > Bid

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.performance
    async def test_streaming_performance_under_high_frequency(
        self, websocket_manager, sample_market_data
    ):
        """
        RED: System maintains performance under high-frequency data streams.

        Performance Target: Process 10,000 price updates/second without degradation.
        """
        # Arrange
        mock_websocket = MockWebSocketConnection("perf_trader")
        await websocket_manager.register_client(mock_websocket)
        await websocket_manager.subscribe_client_to_symbol("perf_trader", "EUR/USD")

        # Act - Stream 1000 price updates rapidly
        start_time = time.time()

        streaming_tasks = []
        for price_data in sample_market_data:
            task = websocket_manager.broadcast_to_symbol_subscribers(
                "EUR/USD", price_data
            )
            streaming_tasks.append(task)

        await asyncio.gather(*streaming_tasks)

        total_time = time.time() - start_time
        throughput = len(sample_market_data) / total_time

        # Assert - Will fail until optimized for high frequency
        assert throughput > 10000  # 10k updates per second
        assert total_time < 0.1  # 1000 updates in under 100ms

        # Verify all messages were delivered
        messages = mock_websocket.get_messages()
        assert len(messages) == len(sample_market_data)


# =============================================================================
# RED PHASE TESTS - Auto-Reconnection and Failover
# =============================================================================


class TestConnectionRecovery:
    """Test automatic reconnection and failover capabilities."""

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_auto_reconnection_within_5_seconds(self, websocket_manager):
        """
        RED: System should auto-reconnect within 5 seconds of network failure.

        Resilience Requirement: Minimize data loss during network disruptions.
        Recovery Target: Auto-reconnect within 5 seconds.
        """
        # Arrange
        mock_websocket = MockWebSocketConnection("resilient_trader")
        await websocket_manager.register_client(mock_websocket)

        # Simulate connection failure
        mock_websocket.connected = False

        # Act - Simulate reconnection attempt
        start_time = time.time()

        # This will fail until auto-reconnection logic is implemented
        reconnection_successful = await websocket_manager._attempt_reconnection(
            mock_websocket.client_id
        )

        reconnection_time = time.time() - start_time

        # Assert - Will fail until reconnection implemented
        assert reconnection_successful is True
        assert reconnection_time < 5.0  # 5 second requirement
        assert mock_websocket.connected is True

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_no_data_loss_during_reconnection(self, websocket_manager):
        """
        RED: No data should be lost during network reconnection.

        Data Integrity: Ensure continuity of price stream during reconnection.
        """
        # Arrange
        mock_websocket = MockWebSocketConnection("data_sensitive_trader")
        await websocket_manager.register_client(mock_websocket)
        await websocket_manager.subscribe_client_to_symbol(
            "data_sensitive_trader", "USD/JPY"
        )

        # Act - Send data, simulate disconnection, reconnect, send more data
        pre_disconnect_data = {"symbol": "USD/JPY", "bid": 110.50, "ask": 110.52}
        await websocket_manager.broadcast_to_symbol_subscribers(
            "USD/JPY", pre_disconnect_data
        )

        # Simulate disconnection
        mock_websocket.connected = False

        # Data sent during disconnection should be queued
        during_disconnect_data = {"symbol": "USD/JPY", "bid": 110.55, "ask": 110.57}
        await websocket_manager.broadcast_to_symbol_subscribers(
            "USD/JPY", during_disconnect_data
        )

        # Reconnection
        await websocket_manager._attempt_reconnection(mock_websocket.client_id)
        mock_websocket.connected = True

        # Post reconnection data
        post_reconnect_data = {"symbol": "USD/JPY", "bid": 110.60, "ask": 110.62}
        await websocket_manager.broadcast_to_symbol_subscribers(
            "USD/JPY", post_reconnect_data
        )

        # Assert - Will fail until data buffering implemented
        messages = mock_websocket.get_messages()
        assert len(messages) == 3  # All messages should be received

        # Verify data integrity
        assert messages[0]["data"]["bid"] == 110.50  # Pre-disconnect
        assert messages[1]["data"]["bid"] == 110.55  # During disconnect (buffered)
        assert messages[2]["data"]["bid"] == 110.60  # Post-reconnect

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_failover_manager_switches_feeds(self):
        """
        RED: Feed failover manager should switch to backup feed on primary failure.

        High Availability: Ensure continuous data flow through backup feeds.
        """
        # Arrange
        failover_manager = FeedFailoverManager()

        primary_feed = FeedSource(
            name="primary_feed",
            priority=1,
            url="wss://primary.datafeed.com",
            symbols=["EUR/USD", "GBP/USD"],
            health_check_interval=30,
            max_latency_ms=10,
        )

        backup_feed = FeedSource(
            name="backup_feed",
            priority=2,
            url="wss://backup.datafeed.com",
            symbols=["EUR/USD", "GBP/USD"],
            health_check_interval=30,
            max_latency_ms=50,
        )

        # Mock feed objects
        primary_feed_obj = MagicMock()
        primary_feed_obj.connected = True
        backup_feed_obj = MagicMock()
        backup_feed_obj.connected = True

        await failover_manager.register_feed(primary_feed, primary_feed_obj)
        await failover_manager.register_feed(backup_feed, backup_feed_obj)

        # Initially select primary
        selected = await failover_manager.select_best_available_feed("EUR/USD")
        assert selected.name == "primary_feed"

        # Act - Simulate primary feed failure
        primary_feed_obj.connected = False

        # Handle failure and failover
        new_feed = await failover_manager.handle_feed_failure(
            primary_feed_obj, "EUR/USD"
        )

        # Assert - Will fail until failover logic implemented
        assert new_feed is not None
        assert new_feed.name == "backup_feed"
        assert failover_manager.current_active_feed.name == "backup_feed"

        # Verify failover event was logged
        events = failover_manager.get_failover_events()
        assert len(events) >= 1
        assert events[-1]["event_type"] == "failover"
        assert events[-1]["to_feed"] == "backup_feed"


# =============================================================================
# RED PHASE TESTS - Data Validation and Error Handling
# =============================================================================


class TestDataValidation:
    """Test data validation and error handling for market data."""

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_rejects_invalid_price_data(self, websocket_manager):
        """
        RED: System should reject invalid price data (negative, NaN, null).

        Data Quality: Prevent corrupt data from reaching traders.
        """
        # Arrange
        mock_websocket = MockWebSocketConnection("quality_trader")
        await websocket_manager.register_client(mock_websocket)
        await websocket_manager.subscribe_client_to_symbol("quality_trader", "EUR/USD")

        invalid_data_samples = [
            {"symbol": "EUR/USD", "bid": -1.0850, "ask": 1.0852},  # Negative bid
            {"symbol": "EUR/USD", "bid": 1.0850, "ask": float("nan")},  # NaN ask
            {"symbol": "EUR/USD", "bid": None, "ask": 1.0852},  # None bid
            {"symbol": "EUR/USD", "bid": 1.0852, "ask": 1.0850},  # Ask < Bid
            {"symbol": "EUR/USD", "bid": "invalid", "ask": 1.0852},  # String bid
        ]

        # Act & Assert
        for invalid_data in invalid_data_samples:
            # Will fail until validation implemented
            validation_result = await websocket_manager._validate_price_data(
                invalid_data
            )
            assert validation_result.is_valid is False
            assert len(validation_result.errors) > 0

            # Should not broadcast invalid data
            await websocket_manager.broadcast_to_symbol_subscribers(
                "EUR/USD", invalid_data
            )

        # No price messages should be sent for invalid data (exclude connection confirmation)
        price_messages = mock_websocket.get_price_messages()
        assert len(price_messages) == 0

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_logs_data_validation_errors(self, websocket_manager):
        """
        RED: Data validation errors should be logged with violation details.

        Compliance: Maintain audit trail of data quality issues.
        """
        # Arrange
        invalid_data = {
            "symbol": "EUR/USD",
            "bid": -1.0850,
            "ask": 1.0852,
            "timestamp": "invalid_timestamp",
        }

        # Act - Will fail until logging implemented
        with patch("core.api.websocket_market_data.logger") as mock_logger:
            validation_result = await websocket_manager._validate_price_data(
                invalid_data
            )

            # Assert
            assert mock_logger.error.called
            error_call = mock_logger.error.call_args[0][0]
            assert "Data validation failed" in error_call
            assert "EUR/USD" in error_call
            assert "negative bid" in error_call.lower()

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_connection_cleanup_on_client_disconnect(self, websocket_manager):
        """
        RED: System should clean up resources when client disconnects.

        Resource Management: Prevent memory leaks from disconnected clients.
        """
        # Arrange
        mock_websocket = MockWebSocketConnection("disconnect_trader")
        await websocket_manager.register_client(mock_websocket)
        await websocket_manager.subscribe_client_to_symbol(
            "disconnect_trader", "GBP/USD"
        )

        # Verify initial state
        assert websocket_manager.active_connections == 1
        assert len(websocket_manager.subscriptions["GBP/USD"]) == 1

        # Act - Simulate client disconnect
        await mock_websocket.close()
        await websocket_manager.handle_client_disconnect(mock_websocket.client_id)

        # Assert - Will fail until cleanup implemented
        assert websocket_manager.active_connections == 0
        assert len(websocket_manager.subscriptions.get("GBP/USD", set())) == 0
        assert mock_websocket.client_id not in websocket_manager.connections
        assert mock_websocket.client_id not in websocket_manager.client_subscriptions


# =============================================================================
# RED PHASE TESTS - Integration with TimescaleDB
# =============================================================================


class TestTimescaleDBIntegration:
    """Test WebSocket integration with TimescaleDB for persistence."""

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.integration
    async def test_persists_streaming_data_to_timescaledb(self, websocket_manager):
        """
        RED: Streaming market data should be persisted to TimescaleDB.

        Data Persistence: Ensure all real-time data is stored for analysis.
        """
        # Arrange
        mock_db_pool = MockTimescaleDBPool()
        websocket_manager.db_pool = mock_db_pool

        streaming_data = {
            "symbol": "EUR/USD",
            "bid": 1.0850,
            "ask": 1.0852,
            "volume": 100000,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Act - Will fail until persistence implemented
        await websocket_manager.persist_market_data(streaming_data)

        # Assert
        assert len(mock_db_pool.queries_executed) == 1
        query = mock_db_pool.queries_executed[0]

        assert "INSERT INTO market_data" in query["query"]
        assert "EUR/USD" in str(query["params"])
        assert 1.0850 in query["params"]
        assert 1.0852 in query["params"]

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.integration
    async def test_batch_persistence_for_performance(
        self, websocket_manager, sample_market_data
    ):
        """
        RED: High-frequency data should be batched for efficient persistence.

        Performance: Batch inserts to maintain streaming performance.
        """
        # Arrange
        mock_db_pool = MockTimescaleDBPool()
        websocket_manager.db_pool = mock_db_pool
        websocket_manager.batch_size = 100

        # Act - Stream data that should trigger batching
        for data in sample_market_data[:100]:
            await websocket_manager.persist_market_data(data)

        # Force batch flush
        await websocket_manager.flush_pending_batches()

        # Assert - Will fail until batching implemented
        assert len(mock_db_pool.queries_executed) == 1  # Single batch insert
        batch_query = mock_db_pool.queries_executed[0]
        assert "INSERT INTO market_data" in batch_query["query"]
        assert len(batch_query["params"]) == 100  # Batched 100 records


# =============================================================================
# Performance Benchmark Tests
# =============================================================================


class TestPerformanceBenchmarks:
    """Performance benchmark tests for WebSocket infrastructure."""

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.performance
    @pytest.mark.slow
    async def test_latency_distribution_under_load(self, websocket_manager):
        """
        RED: Latency should maintain distribution under concurrent load.

        Performance Requirement: 95th percentile < 5ms, 99th percentile < 10ms
        """
        # Arrange - 100 concurrent connections
        connections = [MockWebSocketConnection(f"perf_client_{i}") for i in range(100)]

        for conn in connections:
            await websocket_manager.register_client(conn)
            await websocket_manager.subscribe_client_to_symbol(
                conn.client_id, "EUR/USD"
            )

        # Act - Measure latency distribution
        latencies = []
        test_data = {"symbol": "EUR/USD", "bid": 1.0850, "ask": 1.0852}

        for _ in range(1000):  # 1000 broadcasts
            start_time = time.time()
            await websocket_manager.broadcast_to_symbol_subscribers(
                "EUR/USD", test_data
            )
            end_time = time.time()

            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

        # Calculate percentiles
        latencies.sort()
        p95_latency = latencies[int(len(latencies) * 0.95)]
        p99_latency = latencies[int(len(latencies) * 0.99)]
        avg_latency = sum(latencies) / len(latencies)

        # Assert - Will fail until optimized
        assert p95_latency < 5.0  # 95th percentile < 5ms
        assert p99_latency < 10.0  # 99th percentile < 10ms
        assert avg_latency < 2.0  # Average < 2ms

    @pytest.mark.tdd
    @pytest.mark.red
    @pytest.mark.performance
    async def test_memory_usage_remains_stable(self, websocket_manager):
        """
        RED: Memory usage should remain stable under continuous operation.

        Resource Management: Prevent memory leaks during 24/7 operation.
        """
        import psutil
        import gc

        # Arrange
        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Act - Simulate 1 hour of intensive operations
        for iteration in range(3600):  # 1 hour at 1 second intervals
            # Create temporary connection
            temp_conn = MockWebSocketConnection(f"temp_{iteration}")
            await websocket_manager.register_client(temp_conn)

            # Send data
            test_data = {"symbol": "EUR/USD", "bid": 1.0850 + (iteration * 0.0001)}
            await websocket_manager.broadcast_to_all(test_data)

            # Clean up connection
            await websocket_manager.unregister_client(temp_conn.client_id)

            # Periodic memory check
            if iteration % 360 == 0:  # Every 6 minutes
                gc.collect()
                current_memory = process.memory_info().rss
                memory_growth = current_memory - initial_memory
                memory_growth_mb = memory_growth / (1024 * 1024)

                # Assert - Will fail if memory leaks exist
                assert memory_growth_mb < 100  # Less than 100MB growth per hour

        # Final memory check
        gc.collect()
        final_memory = process.memory_info().rss
        total_growth = (final_memory - initial_memory) / (1024 * 1024)

        assert total_growth < 50  # Less than 50MB total growth
