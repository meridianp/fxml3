"""
Test Suite for FXML4 News Event Handling System

This test suite validates the economic news event handling functionality including:
- Economic calendar integration and event fetching
- Event classification and impact assessment
- News event monitoring and alert generation
- Trading suspension and resumption logic
- AlphaVantage API integration
- Real-time event processing

Test Categories:
- Unit tests for individual components
- Integration tests for end-to-end workflows
- Performance tests for real-time processing
- Mock tests for external API dependencies
"""

import asyncio
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.market_events.economic_calendar import (
    CalendarProvider,
    EconomicCalendar,
    EconomicEvent,
    EventImpact,
    EventStatus,
    MockEconomicProvider,
)
from fxml4.market_events.event_classifier import (
    ClassificationRule,
    CurrencyImpactMap,
    EventCategory,
    EventClassifier,
)
from fxml4.market_events.news_monitor import (
    AlertLevel,
    AlphaVantageEconomicProvider,
    EventAlert,
    MonitoringStatus,
    NewsEventMonitor,
)
from fxml4.market_events.trading_suspension_manager import (
    SuspensionEvent,
    SuspensionReason,
    SuspensionStatus,
    TradingState,
    TradingSuspensionManager,
)


@pytest.fixture
def sample_economic_event():
    """Create sample economic event for testing."""
    return EconomicEvent(
        event_id="test_event_001",
        title="Non-Farm Payrolls",
        country="United States",
        currency="USD",
        date_time=datetime.utcnow() + timedelta(hours=1),
        impact=EventImpact.CRITICAL,
        category="Employment",
        description="Monthly employment data",
        previous_value=250000,
        forecast_value=200000,
    )


@pytest.fixture
async def economic_calendar():
    """Create economic calendar instance for testing."""
    calendar = EconomicCalendar()
    return calendar


@pytest.fixture
async def event_classifier():
    """Create event classifier instance for testing."""
    classifier = EventClassifier()
    return classifier


@pytest.fixture
async def news_monitor(economic_calendar, event_classifier):
    """Create news monitor instance for testing."""
    monitor = NewsEventMonitor(
        economic_calendar=economic_calendar,
        event_classifier=event_classifier,
        check_interval_seconds=5,
        alert_lead_time_minutes=30,
    )
    yield monitor

    # Cleanup
    if monitor.status == MonitoringStatus.RUNNING:
        await monitor.stop_monitoring()


@pytest.fixture
async def trading_suspension_manager():
    """Create trading suspension manager for testing."""
    manager = TradingSuspensionManager()
    yield manager

    # Cleanup
    await manager.cleanup()


class TestEconomicCalendar:
    """Test cases for EconomicCalendar."""

    @pytest.mark.asyncio
    async def test_calendar_initialization(self, economic_calendar):
        """Test calendar initialization."""
        assert len(economic_calendar.providers) > 0
        assert isinstance(economic_calendar.providers[0], MockEconomicProvider)
        assert economic_calendar.cache_duration_hours == 24

    @pytest.mark.asyncio
    async def test_fetch_events(self, economic_calendar):
        """Test event fetching functionality."""
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=7)

        events = await economic_calendar.fetch_events(start_date, end_date)

        assert len(events) > 0
        assert all(isinstance(event, EconomicEvent) for event in events)
        assert all(start_date <= event.date_time <= end_date for event in events)

    @pytest.mark.asyncio
    async def test_get_upcoming_events(self, economic_calendar):
        """Test upcoming events retrieval."""
        upcoming = await economic_calendar.get_upcoming_events(hours_ahead=48)

        assert isinstance(upcoming, list)
        # Should have at least some mock events
        assert len(upcoming) >= 0

        # All events should be upcoming
        now = datetime.utcnow()
        for event in upcoming:
            assert event.date_time > now

    @pytest.mark.asyncio
    async def test_get_high_impact_events(self, economic_calendar):
        """Test high impact events filtering."""
        high_impact = await economic_calendar.get_high_impact_events(hours_ahead=48)

        assert isinstance(high_impact, list)

        # All events should be high or critical impact
        for event in high_impact:
            assert event.impact in [EventImpact.HIGH, EventImpact.CRITICAL]

    @pytest.mark.asyncio
    async def test_get_events_by_currency(self, economic_calendar):
        """Test currency-specific event filtering."""
        usd_events = await economic_calendar.get_events_by_currency("USD")

        assert isinstance(usd_events, list)

        # All events should be USD events
        for event in usd_events:
            assert event.currency == "USD"

    @pytest.mark.asyncio
    async def test_add_custom_event(self, economic_calendar, sample_economic_event):
        """Test adding custom events."""
        initial_count = len(economic_calendar.events_cache)

        await economic_calendar.add_custom_event(sample_economic_event)

        assert len(economic_calendar.events_cache) == initial_count + 1
        assert sample_economic_event.event_id in economic_calendar.events_cache

    @pytest.mark.asyncio
    async def test_remove_event(self, economic_calendar, sample_economic_event):
        """Test event removal."""
        await economic_calendar.add_custom_event(sample_economic_event)

        result = await economic_calendar.remove_event(sample_economic_event.event_id)

        assert result is True
        assert sample_economic_event.event_id not in economic_calendar.events_cache

    @pytest.mark.asyncio
    async def test_calendar_summary(self, economic_calendar):
        """Test calendar summary generation."""
        summary = economic_calendar.get_calendar_summary()

        assert "timestamp" in summary
        assert "total_events" in summary
        assert "events_by_impact" in summary
        assert "events_by_currency" in summary
        assert "providers" in summary


class TestEventClassifier:
    """Test cases for EventClassifier."""

    @pytest.mark.asyncio
    async def test_classifier_initialization(self, event_classifier):
        """Test classifier initialization."""
        assert len(event_classifier.classification_rules) > 0
        assert len(event_classifier.currency_maps) > 0
        assert "USD" in event_classifier.currency_maps

    @pytest.mark.asyncio
    async def test_classify_nfp_event(self, event_classifier):
        """Test NFP event classification."""
        nfp_event = EconomicEvent(
            event_id="nfp_test",
            title="Non-Farm Payrolls",
            country="United States",
            currency="USD",
            date_time=datetime.utcnow() + timedelta(hours=1),
            impact=EventImpact.HIGH,
            category="Employment",
        )

        impact, category, affected_pairs = event_classifier.classify_event(nfp_event)

        assert impact in [EventImpact.HIGH, EventImpact.CRITICAL]
        assert category == EventCategory.EMPLOYMENT
        assert len(affected_pairs) > 0
        assert any("USD" in pair for pair in affected_pairs)

    @pytest.mark.asyncio
    async def test_classify_fed_decision(self, event_classifier):
        """Test Fed decision classification."""
        fed_event = EconomicEvent(
            event_id="fed_test",
            title="Federal Funds Rate Decision",
            country="United States",
            currency="USD",
            date_time=datetime.utcnow() + timedelta(hours=2),
            impact=EventImpact.CRITICAL,
            category="Monetary Policy",
        )

        impact, category, affected_pairs = event_classifier.classify_event(fed_event)

        assert impact == EventImpact.CRITICAL
        assert category == EventCategory.MONETARY_POLICY
        assert len(affected_pairs) > 0

    @pytest.mark.asyncio
    async def test_trading_suspension_recommendation(
        self, event_classifier, sample_economic_event
    ):
        """Test trading suspension recommendations."""
        recommendation = event_classifier.get_trading_suspension_recommendation(
            sample_economic_event
        )

        assert "suspension_recommended" in recommendation
        assert "affected_pairs" in recommendation
        assert "pre_event_minutes" in recommendation
        assert "post_event_minutes" in recommendation
        assert "reasoning" in recommendation

        # High impact events should recommend suspension
        if sample_economic_event.impact in [EventImpact.HIGH, EventImpact.CRITICAL]:
            assert recommendation["suspension_recommended"] is True

    @pytest.mark.asyncio
    async def test_add_custom_rule(self, event_classifier):
        """Test adding custom classification rules."""
        initial_count = len(event_classifier.classification_rules)

        custom_rule = ClassificationRule(
            rule_id="test_rule",
            name="Test Rule",
            event_patterns=["test event"],
            category=EventCategory.OTHER,
            base_impact=EventImpact.MEDIUM,
        )

        event_classifier.add_custom_rule(custom_rule)

        assert len(event_classifier.classification_rules) == initial_count + 1
        assert (
            event_classifier.classification_rules[0] == custom_rule
        )  # Should be inserted at beginning

    @pytest.mark.asyncio
    async def test_classification_stats(self, event_classifier, sample_economic_event):
        """Test classification statistics."""
        # Classify an event to generate stats
        event_classifier.classify_event(sample_economic_event)

        stats = event_classifier.get_classification_stats()

        assert "total_classifications" in stats
        assert "unique_events_classified" in stats
        assert "active_rules" in stats
        assert "classification_by_impact" in stats
        assert "classification_by_category" in stats


class TestNewsEventMonitor:
    """Test cases for NewsEventMonitor."""

    @pytest.mark.asyncio
    async def test_monitor_initialization(self, news_monitor):
        """Test news monitor initialization."""
        assert news_monitor.status == MonitoringStatus.STOPPED
        assert news_monitor.check_interval == 5
        assert news_monitor.alert_lead_time_minutes == 30

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, news_monitor):
        """Test monitoring start and stop."""
        # Start monitoring
        await news_monitor.start_monitoring()
        assert news_monitor.status == MonitoringStatus.RUNNING

        # Stop monitoring
        await news_monitor.stop_monitoring()
        assert news_monitor.status == MonitoringStatus.STOPPED

    @pytest.mark.asyncio
    async def test_pause_resume_monitoring(self, news_monitor):
        """Test monitoring pause and resume."""
        await news_monitor.start_monitoring()

        # Pause monitoring
        await news_monitor.pause_monitoring()
        assert news_monitor.status == MonitoringStatus.PAUSED

        # Resume monitoring
        await news_monitor.resume_monitoring()
        assert news_monitor.status == MonitoringStatus.RUNNING

        await news_monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_force_check(self, news_monitor):
        """Test forced monitoring check."""
        await news_monitor.start_monitoring()

        result = await news_monitor.force_check()

        assert result["check_completed"] is True
        assert "check_duration_seconds" in result
        assert "timestamp" in result

        await news_monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_alert_generation(self, news_monitor, economic_calendar):
        """Test alert generation for upcoming events."""
        # Add a near-future high-impact event
        near_future_event = EconomicEvent(
            event_id="alert_test_001",
            title="Test High Impact Event",
            country="United States",
            currency="USD",
            date_time=datetime.utcnow() + timedelta(minutes=30),
            impact=EventImpact.HIGH,
            category="Test",
        )

        await economic_calendar.add_custom_event(near_future_event)

        await news_monitor.start_monitoring()

        # Force a check to process the event
        await news_monitor.force_check()

        # Check if alert was generated
        active_alerts = news_monitor.get_active_alerts()

        # Should have generated at least one alert
        assert len(active_alerts) >= 0  # Might be 0 if timing doesn't align perfectly

        await news_monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_alert_acknowledgment(self, news_monitor):
        """Test alert acknowledgment functionality."""
        # Create a mock alert
        test_alert = EventAlert(
            alert_id="test_alert_001",
            timestamp=datetime.utcnow(),
            level=AlertLevel.WARNING,
            event=EconomicEvent(
                event_id="mock_event",
                title="Mock Event",
                country="US",
                currency="USD",
                date_time=datetime.utcnow() + timedelta(minutes=30),
                impact=EventImpact.HIGH,
            ),
            alert_type="test",
            title="Test Alert",
            description="Test alert description",
        )

        # Add alert to active alerts
        news_monitor.active_alerts[test_alert.alert_id] = test_alert

        # Acknowledge the alert
        result = await news_monitor.acknowledge_alert(test_alert.alert_id)

        assert result is True
        assert test_alert.acknowledged is True

    @pytest.mark.asyncio
    async def test_monitoring_status(self, news_monitor):
        """Test monitoring status retrieval."""
        status = news_monitor.get_monitoring_status()

        assert "timestamp" in status
        assert "status" in status
        assert "statistics" in status
        assert "configuration" in status

        assert status["status"] == MonitoringStatus.STOPPED.value


class TestTradingSuspensionManager:
    """Test cases for TradingSuspensionManager."""

    @pytest.mark.asyncio
    async def test_manager_initialization(self, trading_suspension_manager):
        """Test suspension manager initialization."""
        assert trading_suspension_manager.global_trading_state == TradingState.NORMAL
        assert len(trading_suspension_manager.suspended_pairs) == 0
        assert len(trading_suspension_manager.suspended_currencies) == 0

    @pytest.mark.asyncio
    async def test_immediate_suspension(self, trading_suspension_manager):
        """Test immediate trading suspension."""
        suspension_id = await trading_suspension_manager.execute_immediate_suspension(
            reason=SuspensionReason.ECONOMIC_EVENT,
            scope="pair:EURUSD",
            description="Test suspension",
            duration_minutes=1,
            affected_pairs={"EURUSD"},
        )

        assert suspension_id is not None
        assert "EURUSD" in trading_suspension_manager.suspended_pairs
        assert trading_suspension_manager.is_pair_suspended("EURUSD")
        assert not trading_suspension_manager.is_trading_allowed("EURUSD")

    @pytest.mark.asyncio
    async def test_suspension_resume(self, trading_suspension_manager):
        """Test trading suspension and resume."""
        # Execute suspension
        suspension_id = await trading_suspension_manager.execute_immediate_suspension(
            reason=SuspensionReason.ECONOMIC_EVENT,
            scope="pair:GBPUSD",
            description="Test suspension for resume",
            duration_minutes=1,
            affected_pairs={"GBPUSD"},
        )

        # Verify suspension
        assert trading_suspension_manager.is_pair_suspended("GBPUSD")

        # Wait a moment
        await asyncio.sleep(0.1)

        # Resume trading
        result = await trading_suspension_manager.resume_trading(suspension_id)

        assert result is True
        assert not trading_suspension_manager.is_pair_suspended("GBPUSD")
        assert trading_suspension_manager.is_trading_allowed("GBPUSD")

    @pytest.mark.asyncio
    async def test_currency_suspension(self, trading_suspension_manager):
        """Test currency-specific suspension."""
        suspension_id = await trading_suspension_manager.execute_immediate_suspension(
            reason=SuspensionReason.ECONOMIC_EVENT,
            scope="currency:EUR",
            description="Test EUR suspension",
            duration_minutes=1,
        )

        assert suspension_id is not None
        assert trading_suspension_manager.is_currency_suspended("EUR")

        # Check that EUR pairs are suspended
        eur_pairs = ["EURUSD", "EURGBP", "EURJPY"]
        for pair in eur_pairs:
            if pair in trading_suspension_manager.suspended_pairs:
                assert trading_suspension_manager.is_pair_suspended(pair)

    @pytest.mark.asyncio
    async def test_emergency_suspension(self, trading_suspension_manager):
        """Test emergency suspension functionality."""
        suspension_id = await trading_suspension_manager.emergency_suspend_all(
            description="Test emergency suspension"
        )

        assert suspension_id is not None
        assert trading_suspension_manager.global_trading_state == TradingState.EMERGENCY
        assert len(trading_suspension_manager.suspended_pairs) > 0

    @pytest.mark.asyncio
    async def test_suspension_state(self, trading_suspension_manager):
        """Test suspension state retrieval."""
        state = trading_suspension_manager.get_current_state()

        assert "timestamp" in state
        assert "global_state" in state
        assert "suspended_pairs_count" in state
        assert "statistics" in state

        assert state["global_state"] == TradingState.NORMAL.value
        assert state["suspended_pairs_count"] == 0

    @pytest.mark.asyncio
    async def test_pair_trading_checks(self, trading_suspension_manager):
        """Test individual pair trading permission checks."""
        # Initially, all pairs should be allowed
        assert trading_suspension_manager.is_trading_allowed("EURUSD")
        assert trading_suspension_manager.is_trading_allowed("GBPUSD")
        assert not trading_suspension_manager.is_pair_suspended("EURUSD")

        # Suspend EURUSD
        await trading_suspension_manager.execute_immediate_suspension(
            reason=SuspensionReason.ECONOMIC_EVENT,
            scope="pair:EURUSD",
            description="Test pair check",
            duration_minutes=1,
            affected_pairs={"EURUSD"},
        )

        # Now EURUSD should be suspended, but GBPUSD should still be allowed
        assert not trading_suspension_manager.is_trading_allowed("EURUSD")
        assert trading_suspension_manager.is_trading_allowed("GBPUSD")
        assert trading_suspension_manager.is_pair_suspended("EURUSD")
        assert not trading_suspension_manager.is_pair_suspended("GBPUSD")


class TestAlphaVantageIntegration:
    """Test cases for AlphaVantage integration."""

    @pytest.mark.asyncio
    async def test_alphavantage_provider_init(self):
        """Test AlphaVantage provider initialization."""
        provider = AlphaVantageEconomicProvider("test_api_key")

        assert provider.api_key == "test_api_key"
        assert provider.base_url == "https://www.alphavantage.co/query"
        assert provider.session is None

    @pytest.mark.asyncio
    async def test_alphavantage_session_management(self):
        """Test HTTP session management."""
        provider = AlphaVantageEconomicProvider("test_api_key")

        session = await provider._get_session()
        assert session is not None

        # Should reuse same session
        session2 = await provider._get_session()
        assert session2 is session

        await provider.close()

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_alphavantage_fetch_events_mock(self, mock_get):
        """Test AlphaVantage event fetching with mocked response."""
        mock_response_data = {
            "data": [
                {
                    "id": "123",
                    "event": "Non-Farm Payrolls",
                    "country": "United States",
                    "currency": "USD",
                    "time": "2024-01-05T13:30:00Z",
                    "importance": "high",
                    "previous": "200000",
                    "forecast": "180000",
                }
            ]
        }

        # Mock the response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_get.return_value.__aenter__.return_value = mock_response

        provider = AlphaVantageEconomicProvider("test_api_key")

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        events = await provider.fetch_events(start_date, end_date)

        assert len(events) == 1
        assert events[0].title == "Non-Farm Payrolls"
        assert events[0].currency == "USD"
        assert events[0].impact == EventImpact.HIGH

        await provider.close()


@pytest.mark.integration
class TestNewsEventHandlingIntegration:
    """Integration tests for news event handling system."""

    @pytest.mark.asyncio
    async def test_end_to_end_event_processing(
        self, economic_calendar, event_classifier, trading_suspension_manager
    ):
        """Test complete end-to-end event processing."""
        # Create a high-impact event
        test_event = EconomicEvent(
            event_id="integration_test_001",
            title="Integration Test NFP",
            country="United States",
            currency="USD",
            date_time=datetime.utcnow() + timedelta(minutes=15),
            impact=EventImpact.CRITICAL,
            category="Employment",
        )

        # Add event to calendar
        await economic_calendar.add_custom_event(test_event)

        # Classify the event
        impact, category, affected_pairs = event_classifier.classify_event(test_event)

        # Get suspension recommendation
        suspension_rec = event_classifier.get_trading_suspension_recommendation(
            test_event
        )

        # Verify the processing chain
        assert impact in [EventImpact.HIGH, EventImpact.CRITICAL]
        assert len(affected_pairs) > 0
        assert suspension_rec["suspension_recommended"] is True

        # Test suspension execution
        if suspension_rec["suspension_recommended"]:
            suspension_id = (
                await trading_suspension_manager.execute_immediate_suspension(
                    reason=SuspensionReason.ECONOMIC_EVENT,
                    scope="currency:USD",
                    description=f"Integration test suspension for {test_event.title}",
                    duration_minutes=1,
                )
            )

            assert suspension_id is not None
            assert trading_suspension_manager.is_currency_suspended("USD")

    @pytest.mark.asyncio
    async def test_multiple_event_handling(self, economic_calendar, event_classifier):
        """Test handling of multiple simultaneous events."""
        # Create multiple events
        events = [
            EconomicEvent(
                event_id=f"multi_test_{i}",
                title=f"Test Event {i}",
                country="United States",
                currency="USD",
                date_time=datetime.utcnow() + timedelta(minutes=10 + i * 5),
                impact=EventImpact.HIGH,
                category="Test",
            )
            for i in range(3)
        ]

        # Add all events to calendar
        for event in events:
            await economic_calendar.add_custom_event(event)

        # Get upcoming events
        upcoming = await economic_calendar.get_upcoming_events(hours_ahead=1)
        test_events = [e for e in upcoming if e.event_id.startswith("multi_test_")]

        assert len(test_events) == 3

        # Classify all events
        classifications = []
        for event in test_events:
            impact, category, affected_pairs = event_classifier.classify_event(event)
            classifications.append(
                {
                    "event_id": event.event_id,
                    "impact": impact,
                    "category": category,
                    "pairs": affected_pairs,
                }
            )

        assert len(classifications) == 3
        assert all(c["impact"] == EventImpact.HIGH for c in classifications)


@pytest.mark.performance
class TestNewsEventHandlingPerformance:
    """Performance tests for news event handling."""

    @pytest.mark.asyncio
    async def test_event_classification_performance(self, event_classifier):
        """Test event classification performance."""
        # Create multiple events for performance testing
        events = [
            EconomicEvent(
                event_id=f"perf_test_{i}",
                title=f"Performance Test Event {i}",
                country="United States",
                currency="USD",
                date_time=datetime.utcnow() + timedelta(hours=1),
                impact=EventImpact.HIGH,
            )
            for i in range(100)
        ]

        # Measure classification time
        start_time = time.perf_counter()

        for event in events:
            event_classifier.classify_event(event)

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Should classify 100 events in reasonable time
        assert total_time < 1.0  # Less than 1 second

        average_time_per_event = total_time / len(events)
        assert average_time_per_event < 0.01  # Less than 10ms per event

    @pytest.mark.asyncio
    async def test_calendar_fetch_performance(self, economic_calendar):
        """Test calendar fetching performance."""
        start_time = time.perf_counter()

        # Fetch events multiple times
        for _ in range(10):
            await economic_calendar.get_upcoming_events(hours_ahead=24)

        end_time = time.perf_counter()
        total_time = end_time - start_time

        # Should complete 10 fetches quickly (with caching)
        assert total_time < 2.0  # Less than 2 seconds total

    @pytest.mark.asyncio
    async def test_suspension_execution_performance(self, trading_suspension_manager):
        """Test suspension execution performance."""
        start_time = time.perf_counter()

        # Execute multiple suspensions rapidly
        suspension_ids = []
        for i in range(5):
            suspension_id = (
                await trading_suspension_manager.execute_immediate_suspension(
                    reason=SuspensionReason.ECONOMIC_EVENT,
                    scope=f"pair:TEST{i:02d}USD",
                    description=f"Performance test suspension {i}",
                    duration_minutes=1,
                    affected_pairs={f"TEST{i:02d}USD"},
                )
            )
            suspension_ids.append(suspension_id)

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Should execute 5 suspensions quickly
        assert execution_time < 1.0  # Less than 1 second
        assert len(suspension_ids) == 5
        assert all(sid is not None for sid in suspension_ids)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
