"""TDD Tests for Price Feed Monitoring and Failover.

Tests the reliability monitoring and automatic failover mechanisms
for market data feeds following TDD methodology.
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fxml4.api.price_feed_monitoring import (
    FeedFailoverManager,
    FeedHealthMetrics,
    FeedSource,
    FeedStatus,
    PriceFeedMonitor,
)


class MockPriceFeed:
    """Mock price feed for testing."""

    def __init__(self, name: str, reliability: float = 1.0):
        self.name = name
        self.reliability = reliability  # 0.0 to 1.0
        self.connected = False
        self.last_update = None
        self.update_count = 0
        self.error_count = 0
        self.subscribers = set()

    async def connect(self):
        """Mock connection method."""
        self.connected = True

    async def disconnect(self):
        """Mock disconnection method."""
        self.connected = False

    async def subscribe_to_symbol(self, symbol: str):
        """Mock subscription method."""
        if not self.connected:
            raise ConnectionError("Feed not connected")
        self.subscribers.add(symbol)

    async def get_price_update(self) -> Optional[Dict[str, Any]]:
        """Mock price update method."""
        if not self.connected:
            return None

        # Simulate reliability issues
        import random

        if random.random() > self.reliability:
            self.error_count += 1
            return None

        self.update_count += 1
        self.last_update = datetime.utcnow()

        return {
            "symbol": "EURUSD",
            "bid": 1.1234 + (self.update_count * 0.0001),
            "ask": 1.1236 + (self.update_count * 0.0001),
            "timestamp": self.last_update.isoformat(),
            "source": self.name,
        }


@pytest.fixture
def price_feed_monitor():
    """Create price feed monitor for testing."""
    return PriceFeedMonitor()


@pytest.fixture
def failover_manager():
    """Create failover manager for testing."""
    return FeedFailoverManager()


@pytest.fixture
def mock_feeds():
    """Create mock price feeds with different reliability levels."""
    return {
        "primary": MockPriceFeed("ForexConnect-Primary", reliability=0.95),
        "backup": MockPriceFeed("ForexConnect-Backup", reliability=0.90),
        "emergency": MockPriceFeed("Market-Data-API", reliability=0.80),
    }


@pytest.fixture
def feed_sources():
    """Create feed source configurations for testing."""
    return [
        FeedSource(
            name="primary",
            priority=1,
            url="tcp://forex-primary:5555",
            symbols=["EURUSD", "GBPUSD", "USDJPY"],
            health_check_interval=10,
            max_latency_ms=100,
        ),
        FeedSource(
            name="backup",
            priority=2,
            url="tcp://forex-backup:5556",
            symbols=["EURUSD", "GBPUSD", "USDJPY"],
            health_check_interval=15,
            max_latency_ms=200,
        ),
        FeedSource(
            name="emergency",
            priority=3,
            url="https://api.marketdata.com/v1/prices",
            symbols=["EURUSD", "GBPUSD"],
            health_check_interval=30,
            max_latency_ms=500,
        ),
    ]


@pytest.mark.asyncio
class TestPriceFeedMonitor:
    """TDD tests for price feed monitoring functionality."""

    async def test_monitor_initialization(self, price_feed_monitor):
        """Test price feed monitor initializes correctly."""
        assert price_feed_monitor is not None
        assert len(price_feed_monitor.monitored_feeds) == 0
        assert price_feed_monitor.active_feed is None
        assert price_feed_monitor.monitoring_active == False

    async def test_feed_registration(self, price_feed_monitor, feed_sources):
        """Test price feeds can be registered for monitoring."""
        # Register feeds
        for feed_source in feed_sources:
            await price_feed_monitor.register_feed(feed_source)

        # Verify registration
        assert len(price_feed_monitor.monitored_feeds) == len(feed_sources)

        # Verify feeds are sorted by priority
        registered_names = [
            feed.name for feed in price_feed_monitor.get_registered_feeds()
        ]
        expected_order = ["primary", "backup", "emergency"]  # By priority
        assert registered_names == expected_order

    async def test_feed_health_check_success(self, price_feed_monitor, mock_feeds):
        """Test health check correctly identifies healthy feeds."""
        feed = mock_feeds["primary"]
        await feed.connect()

        # Simulate successful price updates
        for _ in range(5):
            await feed.get_price_update()
            await asyncio.sleep(0.01)  # Small delay

        # Check feed health
        health_metrics = await price_feed_monitor.check_feed_health(feed)

        assert health_metrics.status == FeedStatus.HEALTHY
        assert health_metrics.update_count == 5
        assert health_metrics.error_rate < 0.1  # Should be very low
        assert health_metrics.last_update_age_ms < 1000  # Recent update

    async def test_feed_health_check_stale_data(self, price_feed_monitor, mock_feeds):
        """Test health check detects stale data feeds."""
        feed = mock_feeds["primary"]
        await feed.connect()

        # Simulate old update
        await feed.get_price_update()
        feed.last_update = datetime.utcnow() - timedelta(minutes=5)  # Make it stale

        # Check feed health
        health_metrics = await price_feed_monitor.check_feed_health(feed)

        assert health_metrics.status == FeedStatus.STALE
        assert health_metrics.last_update_age_ms > 300000  # > 5 minutes

    async def test_feed_health_check_high_error_rate(
        self, price_feed_monitor, mock_feeds
    ):
        """Test health check detects feeds with high error rates."""
        feed = mock_feeds["primary"]
        feed.reliability = 0.3  # Very unreliable
        await feed.connect()

        # Generate updates with high error rate
        for _ in range(20):
            await feed.get_price_update()

        # Check feed health
        health_metrics = await price_feed_monitor.check_feed_health(feed)

        assert health_metrics.status == FeedStatus.DEGRADED
        assert health_metrics.error_rate > 0.5  # High error rate

    async def test_feed_health_check_disconnected(self, price_feed_monitor, mock_feeds):
        """Test health check correctly identifies disconnected feeds."""
        feed = mock_feeds["primary"]
        # Don't connect the feed

        health_metrics = await price_feed_monitor.check_feed_health(feed)

        assert health_metrics.status == FeedStatus.DISCONNECTED
        assert health_metrics.update_count == 0
        assert health_metrics.last_update_age_ms is None

    async def test_continuous_monitoring(
        self, price_feed_monitor, mock_feeds, feed_sources
    ):
        """Test continuous monitoring of registered feeds."""
        # Register and connect feeds
        for i, feed_source in enumerate(feed_sources):
            await price_feed_monitor.register_feed(feed_source)
            feed_name = feed_source.name
            if feed_name in mock_feeds:
                await mock_feeds[feed_name].connect()

        # Start monitoring
        monitoring_task = asyncio.create_task(
            price_feed_monitor.start_monitoring(check_interval=0.1)  # Fast for testing
        )

        # Let it run briefly
        await asyncio.sleep(0.5)

        # Stop monitoring
        await price_feed_monitor.stop_monitoring()
        monitoring_task.cancel()

        # Verify monitoring occurred
        assert price_feed_monitor.monitoring_active == False

        # Check that health metrics were collected
        health_data = price_feed_monitor.get_current_health_snapshot()
        assert len(health_data) > 0

    async def test_feed_prioritization(self, price_feed_monitor, feed_sources):
        """Test feeds are properly prioritized by their priority values."""
        # Register feeds in random order
        import random

        shuffled_sources = feed_sources.copy()
        random.shuffle(shuffled_sources)

        for feed_source in shuffled_sources:
            await price_feed_monitor.register_feed(feed_source)

        # Get prioritized feed list
        prioritized_feeds = price_feed_monitor.get_feeds_by_priority()

        # Verify correct priority order (1 = highest priority)
        expected_order = ["primary", "backup", "emergency"]
        actual_order = [feed.name for feed in prioritized_feeds]
        assert actual_order == expected_order

    async def test_feed_symbol_filtering(self, price_feed_monitor, feed_sources):
        """Test feeds can be filtered by supported symbols."""
        # Register feeds
        for feed_source in feed_sources:
            await price_feed_monitor.register_feed(feed_source)

        # Get feeds supporting specific symbols
        eurusd_feeds = price_feed_monitor.get_feeds_supporting_symbol("EURUSD")
        gbpjpy_feeds = price_feed_monitor.get_feeds_supporting_symbol("GBPJPY")

        # EURUSD is supported by all feeds
        assert len(eurusd_feeds) == 3

        # GBPJPY is not explicitly supported by any feeds in our test data
        assert len(gbpjpy_feeds) == 0

    async def test_health_metrics_aggregation(self, price_feed_monitor, mock_feeds):
        """Test health metrics are properly aggregated and calculated."""
        feed = mock_feeds["primary"]
        await feed.connect()

        # Generate known pattern of updates and errors
        success_count = 0
        error_count = 0

        for i in range(100):
            if i % 10 == 0:  # Every 10th update fails
                feed.reliability = 0.0  # Force error
                result = await feed.get_price_update()
                if result is None:
                    error_count += 1
                feed.reliability = 1.0  # Reset
            else:
                await feed.get_price_update()
                success_count += 1

        # Check aggregated metrics
        health_metrics = await price_feed_monitor.check_feed_health(feed)

        expected_error_rate = error_count / (success_count + error_count)
        assert abs(health_metrics.error_rate - expected_error_rate) < 0.01
        assert health_metrics.update_count == success_count

    async def test_latency_measurement(self, price_feed_monitor, mock_feeds):
        """Test latency measurement for price feed updates."""
        feed = mock_feeds["primary"]
        await feed.connect()

        # Record latency measurements
        latencies = []

        for _ in range(10):
            start_time = datetime.utcnow()
            update = await feed.get_price_update()
            end_time = datetime.utcnow()

            if update:
                latency_ms = (end_time - start_time).total_seconds() * 1000
                latencies.append(latency_ms)

                # Record latency in monitor
                await price_feed_monitor.record_feed_latency(feed.name, latency_ms)

        # Get latency metrics
        health_metrics = await price_feed_monitor.check_feed_health(feed)

        assert health_metrics.avg_latency_ms is not None
        assert health_metrics.avg_latency_ms >= 0
        assert len(latencies) > 0


@pytest.mark.asyncio
class TestFeedFailoverManager:
    """TDD tests for automatic feed failover functionality."""

    async def test_failover_manager_initialization(self, failover_manager):
        """Test failover manager initializes correctly."""
        assert failover_manager is not None
        assert failover_manager.current_active_feed is None
        assert len(failover_manager.available_feeds) == 0
        assert failover_manager.failover_in_progress == False

    async def test_feed_selection_by_priority(
        self, failover_manager, mock_feeds, feed_sources
    ):
        """Test failover manager selects feeds by priority."""
        # Register feeds
        for feed_source in feed_sources:
            await failover_manager.register_feed(
                feed_source, mock_feeds.get(feed_source.name)
            )

        # Connect all feeds
        for feed in mock_feeds.values():
            await feed.connect()

        # Select best feed
        selected_feed = await failover_manager.select_best_available_feed("EURUSD")

        # Should select primary (highest priority)
        assert selected_feed.name == "primary"
        assert failover_manager.current_active_feed == selected_feed

    async def test_automatic_failover_on_feed_failure(
        self, failover_manager, mock_feeds, feed_sources
    ):
        """Test automatic failover when primary feed fails."""
        # Register feeds
        for feed_source in feed_sources:
            await failover_manager.register_feed(
                feed_source, mock_feeds.get(feed_source.name)
            )

        # Connect feeds
        await mock_feeds["primary"].connect()
        await mock_feeds["backup"].connect()

        # Select primary feed initially
        primary_feed = await failover_manager.select_best_available_feed("EURUSD")
        assert primary_feed.name == "primary"

        # Simulate primary feed failure
        await mock_feeds["primary"].disconnect()

        # Trigger failover
        new_feed = await failover_manager.handle_feed_failure(primary_feed, "EURUSD")

        # Should failover to backup
        assert new_feed.name == "backup"
        assert failover_manager.current_active_feed == new_feed

    async def test_failover_with_symbol_support_check(
        self, failover_manager, feed_sources
    ):
        """Test failover considers symbol support when selecting feeds."""
        # Create feeds with different symbol support
        specialized_feeds = [
            MockPriceFeed("major-pairs"),  # Will support major pairs only
            MockPriceFeed("all-pairs"),  # Will support all pairs
            MockPriceFeed("exotic-pairs"),  # Will support exotic pairs only
        ]

        specialized_sources = [
            FeedSource(
                "major-pairs", 1, "tcp://major:5555", ["EURUSD", "GBPUSD"], 10, 100
            ),
            FeedSource(
                "all-pairs",
                2,
                "tcp://all:5556",
                ["EURUSD", "GBPUSD", "USDTRY"],
                10,
                100,
            ),
            FeedSource(
                "exotic-pairs", 3, "tcp://exotic:5557", ["USDTRY", "USDZAR"], 10, 100
            ),
        ]

        # Register feeds
        for i, source in enumerate(specialized_sources):
            await failover_manager.register_feed(source, specialized_feeds[i])
            await specialized_feeds[i].connect()

        # Test failover for major pair
        selected_major = await failover_manager.select_best_available_feed("EURUSD")
        assert (
            selected_major.name == "major-pairs"
        )  # Highest priority supporting EURUSD

        # Test failover for exotic pair
        selected_exotic = await failover_manager.select_best_available_feed("USDTRY")
        assert selected_exotic.name == "all-pairs"  # Higher priority than exotic-pairs

    async def test_failback_to_primary_when_recovered(
        self, failover_manager, mock_feeds, feed_sources
    ):
        """Test failback to primary feed when it recovers."""
        # Register feeds
        for feed_source in feed_sources:
            await failover_manager.register_feed(
                feed_source, mock_feeds.get(feed_source.name)
            )

        # Connect only backup initially (primary is down)
        await mock_feeds["backup"].connect()

        # Select backup feed (primary unavailable)
        current_feed = await failover_manager.select_best_available_feed("EURUSD")
        assert current_feed.name == "backup"

        # Primary feed comes back online
        await mock_feeds["primary"].connect()

        # Check for better feed availability
        better_feed = await failover_manager.check_for_better_feed("EURUSD")

        # Should suggest failback to primary
        assert better_feed is not None
        assert better_feed.name == "primary"

        # Execute failback
        await failover_manager.switch_to_feed(better_feed, "EURUSD")
        assert failover_manager.current_active_feed.name == "primary"

    async def test_cascading_failover(self, failover_manager, mock_feeds, feed_sources):
        """Test cascading failover through multiple feed failures."""
        # Register feeds
        for feed_source in feed_sources:
            await failover_manager.register_feed(
                feed_source, mock_feeds.get(feed_source.name)
            )

        # Connect all feeds
        for feed in mock_feeds.values():
            await feed.connect()

        # Start with primary
        current_feed = await failover_manager.select_best_available_feed("EURUSD")
        assert current_feed.name == "primary"

        # Primary fails -> should move to backup
        await mock_feeds["primary"].disconnect()
        current_feed = await failover_manager.handle_feed_failure(
            current_feed, "EURUSD"
        )
        assert current_feed.name == "backup"

        # Backup also fails -> should move to emergency
        await mock_feeds["backup"].disconnect()
        current_feed = await failover_manager.handle_feed_failure(
            current_feed, "EURUSD"
        )
        assert current_feed.name == "emergency"

        # All feeds failed -> should return None
        await mock_feeds["emergency"].disconnect()
        final_feed = await failover_manager.handle_feed_failure(current_feed, "EURUSD")
        assert final_feed is None

    async def test_failover_latency_threshold(self, failover_manager):
        """Test failover based on latency thresholds."""
        # Create feeds with different latency characteristics
        slow_feed = MockPriceFeed("slow-feed")
        fast_feed = MockPriceFeed("fast-feed")

        slow_source = FeedSource(
            "slow-feed", 1, "tcp://slow:5555", ["EURUSD"], 10, 50
        )  # 50ms max
        fast_source = FeedSource(
            "fast-feed", 2, "tcp://fast:5556", ["EURUSD"], 10, 200
        )  # 200ms max

        await failover_manager.register_feed(slow_source, slow_feed)
        await failover_manager.register_feed(fast_source, fast_feed)

        await slow_feed.connect()
        await fast_feed.connect()

        # Start with slow feed (higher priority)
        current_feed = await failover_manager.select_best_available_feed("EURUSD")
        assert current_feed.name == "slow-feed"

        # Simulate high latency on slow feed
        await failover_manager.record_feed_latency(
            "slow-feed", 100
        )  # Exceeds 50ms threshold

        # Check if failover is triggered by latency
        should_failover = await failover_manager.should_failover_due_to_latency(
            "slow-feed"
        )
        assert should_failover == True

        # Execute latency-based failover
        new_feed = await failover_manager.failover_due_to_latency("slow-feed", "EURUSD")
        assert new_feed.name == "fast-feed"

    async def test_failover_event_logging(
        self, failover_manager, mock_feeds, feed_sources
    ):
        """Test failover events are properly logged for audit purposes."""
        # Register feeds
        for feed_source in feed_sources:
            await failover_manager.register_feed(
                feed_source, mock_feeds.get(feed_source.name)
            )

        await mock_feeds["primary"].connect()
        await mock_feeds["backup"].connect()

        # Initial selection
        await failover_manager.select_best_available_feed("EURUSD")

        # Trigger failover
        await mock_feeds["primary"].disconnect()
        await failover_manager.handle_feed_failure(mock_feeds["primary"], "EURUSD")

        # Check failover events were logged
        events = failover_manager.get_failover_events()

        assert len(events) >= 2  # Selection + Failover events

        # Verify event structure
        failover_event = [e for e in events if e["event_type"] == "failover"][0]
        assert failover_event["from_feed"] == "primary"
        assert failover_event["to_feed"] == "backup"
        assert failover_event["symbol"] == "EURUSD"
        assert "timestamp" in failover_event
        assert "reason" in failover_event


@pytest.mark.asyncio
class TestIntegratedFeedMonitoringAndFailover:
    """Integration tests combining monitoring and failover functionality."""

    async def test_integrated_monitoring_triggers_failover(
        self, price_feed_monitor, failover_manager, mock_feeds, feed_sources
    ):
        """Test monitoring system automatically triggers failover when issues detected."""
        # Setup integrated system
        for feed_source in feed_sources:
            await price_feed_monitor.register_feed(feed_source)
            await failover_manager.register_feed(
                feed_source, mock_feeds.get(feed_source.name)
            )

        # Connect feeds
        for feed in mock_feeds.values():
            await feed.connect()

        # Start monitoring
        monitoring_task = asyncio.create_task(
            price_feed_monitor.start_monitoring(check_interval=0.1)
        )

        # Set up failover monitoring
        failover_task = asyncio.create_task(
            failover_manager.start_automated_failover_monitoring(
                price_feed_monitor, check_interval=0.2
            )
        )

        try:
            # Make primary feed unreliable
            mock_feeds["primary"].reliability = 0.1  # Very unreliable

            # Wait for monitoring to detect issues and trigger failover
            await asyncio.sleep(1.0)

            # Check that failover occurred
            current_feed = failover_manager.current_active_feed
            assert current_feed is not None
            assert current_feed.name != "primary"  # Should have failed over

            # Verify failover was logged
            events = failover_manager.get_failover_events()
            failover_events = [e for e in events if e["event_type"] == "failover"]
            assert len(failover_events) > 0

        finally:
            # Cleanup
            monitoring_task.cancel()
            failover_task.cancel()
            await price_feed_monitor.stop_monitoring()
            await failover_manager.stop_automated_monitoring()


if __name__ == "__main__":
    """Run price feed monitoring and failover tests."""
    pytest.main([__file__, "-v"])
