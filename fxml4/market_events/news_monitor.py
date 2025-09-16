"""
News Event Monitor for FXML4 Trading System

This module provides real-time monitoring of economic news events, integrating
with the economic calendar and event classifier to generate timely alerts
and trading suspension recommendations.

Key Features:
- Real-time event monitoring with configurable check intervals
- Multi-level alert system with escalation
- Integration with AlphaVantage economic calendar API
- Automated trading suspension triggers
- Event-driven notification system
- Comprehensive logging and audit trail

Alert Levels:
- INFO: Upcoming medium-impact events
- WARNING: High-impact events within suspension window
- CRITICAL: Critical events requiring immediate action
- EMERGENCY: System failures or data inconsistencies
"""

import asyncio
import json
import logging
import os
import time
import weakref
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set

import aiohttp

from .economic_calendar import (
    CalendarProvider,
    EconomicCalendar,
    EconomicDataProvider,
    EconomicEvent,
    EventImpact,
)
from .event_classifier import EventCategory, EventClassifier

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MonitoringStatus(Enum):
    """News monitoring service status."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class EventAlert:
    """News event alert structure."""

    alert_id: str
    timestamp: datetime
    level: AlertLevel
    event: EconomicEvent
    alert_type: str
    title: str
    description: str
    suspension_recommended: bool = False
    affected_pairs: Set[str] = field(default_factory=set)
    time_until_event_minutes: Optional[int] = None
    acknowledged: bool = False
    escalated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "event_id": self.event.event_id,
            "event_title": self.event.title,
            "event_time": self.event.date_time.isoformat(),
            "alert_type": self.alert_type,
            "title": self.title,
            "description": self.description,
            "suspension_recommended": self.suspension_recommended,
            "affected_pairs": list(self.affected_pairs),
            "time_until_event_minutes": self.time_until_event_minutes,
            "acknowledged": self.acknowledged,
            "escalated": self.escalated,
        }


class AlphaVantageEconomicProvider(EconomicDataProvider):
    """AlphaVantage economic calendar data provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30.0)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        currencies: Optional[Set[str]] = None,
    ) -> List[EconomicEvent]:
        """Fetch economic events from AlphaVantage."""
        try:
            session = await self._get_session()

            # AlphaVantage economic calendar API
            params = {"function": "ECONOMIC_CALENDAR", "apikey": self.api_key}

            async with session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_alphavantage_events(
                        data, start_date, end_date, currencies
                    )
                else:
                    logger.error(f"AlphaVantage API error: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Error fetching events from AlphaVantage: {e}")
            return []

    def _parse_alphavantage_events(
        self,
        data: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        currencies: Optional[Set[str]] = None,
    ) -> List[EconomicEvent]:
        """Parse AlphaVantage economic calendar response."""
        events = []

        if "data" not in data:
            logger.warning("No data field in AlphaVantage response")
            return events

        for event_data in data["data"]:
            try:
                # Parse event date/time
                event_time_str = event_data.get("time", "")
                if not event_time_str:
                    continue

                event_datetime = datetime.fromisoformat(
                    event_time_str.replace("Z", "+00:00")
                )

                # Filter by date range
                if not (start_date <= event_datetime <= end_date):
                    continue

                # Extract currency
                currency = event_data.get("currency", "USD").upper()

                # Filter by currency if specified
                if currencies and currency not in currencies:
                    continue

                # Map AlphaVantage importance to our impact levels
                importance = event_data.get("importance", "Low").lower()
                impact_mapping = {
                    "low": EventImpact.LOW,
                    "medium": EventImpact.MEDIUM,
                    "high": EventImpact.HIGH,
                    "critical": EventImpact.CRITICAL,
                }
                impact = impact_mapping.get(importance, EventImpact.LOW)

                # Create event
                event = EconomicEvent(
                    event_id=f"av_{event_data.get('id', str(hash(event_data.get('event', ''))))}",
                    title=event_data.get("event", "Unknown Event"),
                    country=event_data.get("country", "Unknown"),
                    currency=currency,
                    date_time=event_datetime,
                    impact=impact,
                    category=event_data.get("category", ""),
                    description=event_data.get("description", ""),
                    previous_value=self._parse_float(event_data.get("previous")),
                    forecast_value=self._parse_float(event_data.get("forecast")),
                    actual_value=self._parse_float(event_data.get("actual")),
                    unit=event_data.get("unit", ""),
                    source="AlphaVantage",
                    provider=CalendarProvider.TRADING_ECONOMICS,
                )

                events.append(event)

            except Exception as e:
                logger.error(f"Error parsing AlphaVantage event: {e}")
                continue

        logger.info(f"Parsed {len(events)} events from AlphaVantage")
        return events

    def _parse_float(self, value: Any) -> Optional[float]:
        """Safely parse float value."""
        if value is None or value == "":
            return None
        try:
            return float(str(value).replace("%", "").replace(",", ""))
        except (ValueError, TypeError):
            return None

    async def get_event_details(self, event_id: str) -> Optional[EconomicEvent]:
        """Get detailed event information (AlphaVantage doesn't support this directly)."""
        # AlphaVantage doesn't provide individual event detail endpoints
        # Would need to fetch full calendar and filter
        return None

    async def close(self):
        """Close HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()


class NewsEventMonitor:
    """
    Real-time news event monitoring service.

    Monitors economic events and generates alerts for trading system
    based on event timing, impact, and classification.
    """

    def __init__(
        self,
        economic_calendar: EconomicCalendar,
        event_classifier: EventClassifier,
        check_interval_seconds: int = 60,
        alert_lead_time_minutes: int = 30,
    ):
        self.economic_calendar = economic_calendar
        self.event_classifier = event_classifier
        self.check_interval = check_interval_seconds
        self.alert_lead_time_minutes = alert_lead_time_minutes

        # Monitoring state
        self.status = MonitoringStatus.STOPPED
        self.monitor_task: Optional[asyncio.Task] = None
        self.last_check_time: Optional[datetime] = None

        # Alert management
        self.active_alerts: Dict[str, EventAlert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.acknowledged_events: Set[str] = set()

        # Event callbacks
        self.alert_listeners: List[weakref.ReferenceType] = []
        self.suspension_listeners: List[weakref.ReferenceType] = []

        # Configuration
        self.alert_thresholds = {
            EventImpact.LOW: timedelta(hours=6),
            EventImpact.MEDIUM: timedelta(hours=2),
            EventImpact.HIGH: timedelta(minutes=60),
            EventImpact.CRITICAL: timedelta(minutes=120),
        }

        # Statistics
        self.stats = {
            "total_checks": 0,
            "events_processed": 0,
            "alerts_generated": 0,
            "suspensions_triggered": 0,
            "last_error": None,
            "uptime_start": datetime.utcnow(),
        }

        logger.info(
            f"NewsEventMonitor initialized with {check_interval_seconds}s check interval"
        )

    async def start_monitoring(self) -> None:
        """Start the news event monitoring service."""
        if self.status == MonitoringStatus.RUNNING:
            logger.warning("News monitoring is already running")
            return

        self.status = MonitoringStatus.STARTING
        logger.info("Starting news event monitoring...")

        try:
            # Initialize AlphaVantage provider if API key is available
            await self._initialize_alphavantage_provider()

            # Start monitoring loop
            self.monitor_task = asyncio.create_task(self._monitoring_loop())
            self.status = MonitoringStatus.RUNNING

            logger.info("News event monitoring started successfully")

        except Exception as e:
            self.status = MonitoringStatus.ERROR
            self.stats["last_error"] = str(e)
            logger.error(f"Failed to start news monitoring: {e}")
            raise

    async def stop_monitoring(self) -> None:
        """Stop the news event monitoring service."""
        if self.status == MonitoringStatus.STOPPED:
            return

        logger.info("Stopping news event monitoring...")
        self.status = MonitoringStatus.STOPPED

        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("News event monitoring stopped")

    async def pause_monitoring(self) -> None:
        """Pause monitoring temporarily."""
        if self.status == MonitoringStatus.RUNNING:
            self.status = MonitoringStatus.PAUSED
            logger.info("News event monitoring paused")

    async def resume_monitoring(self) -> None:
        """Resume paused monitoring."""
        if self.status == MonitoringStatus.PAUSED:
            self.status = MonitoringStatus.RUNNING
            logger.info("News event monitoring resumed")

    async def _initialize_alphavantage_provider(self) -> None:
        """Initialize AlphaVantage provider if API key is available."""
        api_key = os.getenv("ALPHAVANTAGE_API_KEY") or os.getenv(
            "ALPHA_VANTAGE_API_KEY"
        )

        if api_key:
            try:
                alphavantage_provider = AlphaVantageEconomicProvider(api_key)

                # Add to economic calendar providers
                if alphavantage_provider not in self.economic_calendar.providers:
                    self.economic_calendar.providers.append(alphavantage_provider)
                    logger.info("AlphaVantage economic data provider initialized")
                else:
                    logger.info("AlphaVantage provider already initialized")

            except Exception as e:
                logger.error(f"Failed to initialize AlphaVantage provider: {e}")
        else:
            logger.warning("AlphaVantage API key not found in environment variables")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Starting news event monitoring loop")

        while self.status in [MonitoringStatus.RUNNING, MonitoringStatus.PAUSED]:
            try:
                if self.status == MonitoringStatus.RUNNING:
                    await self._perform_monitoring_check()

                # Update statistics
                self.stats["total_checks"] += 1
                self.last_check_time = datetime.utcnow()

                # Wait for next check
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                self.stats["last_error"] = str(e)
                self.status = MonitoringStatus.ERROR
                await asyncio.sleep(self.check_interval)  # Continue despite errors

        logger.info("News event monitoring loop stopped")

    async def _perform_monitoring_check(self) -> None:
        """Perform a single monitoring check."""
        now = datetime.utcnow()

        # Get upcoming events (next 24 hours)
        upcoming_events = await self.economic_calendar.get_upcoming_events(
            hours_ahead=24, min_impact=EventImpact.LOW
        )

        self.stats["events_processed"] += len(upcoming_events)

        # Process each upcoming event
        for event in upcoming_events:
            await self._process_event_for_alerts(event, now)

        # Clean up old alerts
        await self._cleanup_old_alerts()

    async def _process_event_for_alerts(
        self, event: EconomicEvent, current_time: datetime
    ) -> None:
        """Process a single event for alert generation."""
        # Skip if event already acknowledged
        if event.event_id in self.acknowledged_events:
            return

        # Skip if alert already exists for this event
        if any(
            alert.event.event_id == event.event_id
            for alert in self.active_alerts.values()
        ):
            return

        # Calculate time until event
        time_until_event = event.date_time - current_time
        time_until_minutes = int(time_until_event.total_seconds() / 60)

        # Check if we should generate an alert
        if await self._should_generate_alert(event, time_until_event):
            await self._generate_event_alert(event, time_until_minutes)

    async def _should_generate_alert(
        self, event: EconomicEvent, time_until_event: timedelta
    ) -> bool:
        """Determine if an alert should be generated for this event."""
        # Check alert threshold based on event impact
        alert_threshold = self.alert_thresholds.get(event.impact, timedelta(hours=1))

        # Generate alert if within threshold
        if time_until_event <= alert_threshold and time_until_event > timedelta(0):
            return True

        # Always alert for critical events within 2 hours
        if event.impact == EventImpact.CRITICAL and time_until_event <= timedelta(
            hours=2
        ):
            return True

        return False

    async def _generate_event_alert(
        self, event: EconomicEvent, time_until_minutes: int
    ) -> None:
        """Generate alert for an economic event."""
        # Get event classification and suspension recommendation
        impact, category, affected_pairs = self.event_classifier.classify_event(event)
        suspension_rec = self.event_classifier.get_trading_suspension_recommendation(
            event
        )

        # Determine alert level
        alert_level = self._determine_alert_level(event, time_until_minutes)

        # Create alert
        alert_id = f"news_{event.event_id}_{int(time.time())}"
        alert = EventAlert(
            alert_id=alert_id,
            timestamp=datetime.utcnow(),
            level=alert_level,
            event=event,
            alert_type="economic_event",
            title=f"{event.impact.value.upper()} Impact: {event.title}",
            description=f"{event.title} scheduled for {event.date_time.strftime('%Y-%m-%d %H:%M:%S UTC')} "
            f"affecting {event.currency} pairs. Time until event: {time_until_minutes} minutes.",
            suspension_recommended=suspension_rec["suspension_recommended"],
            affected_pairs=set(suspension_rec["affected_pairs"]),
            time_until_event_minutes=time_until_minutes,
        )

        # Store alert
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        self.stats["alerts_generated"] += 1

        # Log alert
        logger.warning(f"Generated {alert_level.value.upper()} alert: {alert.title}")

        # Notify listeners
        await self._notify_alert_listeners(alert)

        # Trigger suspension if recommended
        if suspension_rec["suspension_recommended"]:
            await self._trigger_trading_suspension(alert, suspension_rec)

    def _determine_alert_level(
        self, event: EconomicEvent, time_until_minutes: int
    ) -> AlertLevel:
        """Determine appropriate alert level."""
        if event.impact == EventImpact.CRITICAL:
            if time_until_minutes <= 30:
                return AlertLevel.EMERGENCY
            else:
                return AlertLevel.CRITICAL
        elif event.impact == EventImpact.HIGH:
            if time_until_minutes <= 15:
                return AlertLevel.CRITICAL
            else:
                return AlertLevel.WARNING
        elif event.impact == EventImpact.MEDIUM:
            return AlertLevel.WARNING
        else:
            return AlertLevel.INFO

    async def _trigger_trading_suspension(
        self, alert: EventAlert, suspension_rec: Dict[str, Any]
    ) -> None:
        """Trigger trading suspension based on event."""
        self.stats["suspensions_triggered"] += 1

        logger.critical(f"Triggering trading suspension for event: {alert.event.title}")

        # Notify suspension listeners
        await self._notify_suspension_listeners(alert, suspension_rec)

    async def _cleanup_old_alerts(self) -> None:
        """Clean up old and expired alerts."""
        current_time = datetime.utcnow()
        expired_alerts = []

        for alert_id, alert in self.active_alerts.items():
            # Remove alerts for events that have passed
            if alert.event.date_time < current_time:
                expired_alerts.append(alert_id)
            # Remove old acknowledged alerts
            elif alert.acknowledged and (current_time - alert.timestamp).days > 1:
                expired_alerts.append(alert_id)

        for alert_id in expired_alerts:
            del self.active_alerts[alert_id]

        if expired_alerts:
            logger.debug(f"Cleaned up {len(expired_alerts)} expired alerts")

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        if alert_id not in self.active_alerts:
            return False

        alert = self.active_alerts[alert_id]
        alert.acknowledged = True
        self.acknowledged_events.add(alert.event.event_id)

        logger.info(f"Alert acknowledged: {alert_id}")
        return True

    async def escalate_alert(self, alert_id: str) -> bool:
        """Escalate an alert to higher severity."""
        if alert_id not in self.active_alerts:
            return False

        alert = self.active_alerts[alert_id]
        alert.escalated = True

        # Upgrade alert level
        if alert.level == AlertLevel.INFO:
            alert.level = AlertLevel.WARNING
        elif alert.level == AlertLevel.WARNING:
            alert.level = AlertLevel.CRITICAL
        elif alert.level == AlertLevel.CRITICAL:
            alert.level = AlertLevel.EMERGENCY

        logger.warning(f"Alert escalated to {alert.level.value}: {alert_id}")

        # Notify listeners of escalation
        await self._notify_alert_listeners(alert)

        return True

    async def add_alert_listener(self, callback: Callable) -> None:
        """Add alert notification listener."""
        self.alert_listeners.append(weakref.ref(callback))

    async def add_suspension_listener(self, callback: Callable) -> None:
        """Add trading suspension listener."""
        self.suspension_listeners.append(weakref.ref(callback))

    async def _notify_alert_listeners(self, alert: EventAlert) -> None:
        """Notify alert listeners."""
        for listener_ref in self.alert_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.alert_listeners.remove(listener_ref)
            else:
                try:
                    await listener(alert)
                except Exception as e:
                    logger.error(f"Alert listener error: {e}")

    async def _notify_suspension_listeners(
        self, alert: EventAlert, suspension_rec: Dict[str, Any]
    ) -> None:
        """Notify trading suspension listeners."""
        for listener_ref in self.suspension_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.suspension_listeners.remove(listener_ref)
            else:
                try:
                    await listener(alert, suspension_rec)
                except Exception as e:
                    logger.error(f"Suspension listener error: {e}")

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get comprehensive monitoring status."""
        now = datetime.utcnow()
        uptime_seconds = (now - self.stats["uptime_start"]).total_seconds()

        # Active alerts by level
        alerts_by_level = {}
        for level in AlertLevel:
            alerts_by_level[level.value] = len(
                [
                    a
                    for a in self.active_alerts.values()
                    if a.level == level and not a.acknowledged
                ]
            )

        # Recent alert history
        recent_alerts = [
            alert.to_dict()
            for alert in list(self.alert_history)[-20:]  # Last 20 alerts
        ]

        return {
            "timestamp": now.isoformat(),
            "status": self.status.value,
            "uptime_seconds": round(uptime_seconds, 1),
            "last_check": (
                self.last_check_time.isoformat() if self.last_check_time else None
            ),
            "check_interval_seconds": self.check_interval,
            "active_alerts_count": len(self.active_alerts),
            "alerts_by_level": alerts_by_level,
            "statistics": {
                "total_checks": self.stats["total_checks"],
                "events_processed": self.stats["events_processed"],
                "alerts_generated": self.stats["alerts_generated"],
                "suspensions_triggered": self.stats["suspensions_triggered"],
                "last_error": self.stats["last_error"],
            },
            "configuration": {
                "alert_lead_time_minutes": self.alert_lead_time_minutes,
                "alert_thresholds": {
                    impact.value: threshold.total_seconds()
                    for impact, threshold in self.alert_thresholds.items()
                },
            },
            "recent_alerts": recent_alerts,
        }

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts."""
        return [alert.to_dict() for alert in self.active_alerts.values()]

    def get_critical_alerts(self) -> List[Dict[str, Any]]:
        """Get only critical and emergency alerts."""
        critical_alerts = [
            alert
            for alert in self.active_alerts.values()
            if alert.level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]
            and not alert.acknowledged
        ]
        return [alert.to_dict() for alert in critical_alerts]

    async def force_check(self) -> Dict[str, Any]:
        """Force an immediate monitoring check."""
        logger.info("Forcing immediate monitoring check")

        start_time = datetime.utcnow()
        await self._perform_monitoring_check()
        end_time = datetime.utcnow()

        check_duration = (end_time - start_time).total_seconds()

        return {
            "check_completed": True,
            "check_duration_seconds": round(check_duration, 3),
            "timestamp": end_time.isoformat(),
            "new_alerts": len(
                [
                    a
                    for a in self.active_alerts.values()
                    if (end_time - a.timestamp).total_seconds() < 60
                ]
            ),
        }
