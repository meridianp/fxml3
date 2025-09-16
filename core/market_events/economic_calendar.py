"""
Economic Calendar Service for FXML4 Trading System

This module provides comprehensive economic calendar functionality, including
event data fetching, parsing, caching, and management. It integrates with
multiple economic data providers to ensure reliable event information.

Key Features:
- Multi-provider economic event data fetching
- Event caching and persistence
- Timezone-aware event handling
- Real-time calendar updates
- Event impact classification
- Currency-specific event filtering

Supported Events:
- Central Bank Decisions (Fed, ECB, BoE, BoJ, etc.)
- Employment Data (NFP, Unemployment Rate, etc.)
- Inflation Data (CPI, PPI, PCE, etc.)
- Economic Growth (GDP, Retail Sales, etc.)
- Manufacturing Data (PMI, Industrial Production, etc.)
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set

import aiohttp
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventImpact(Enum):
    """Economic event impact levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(Enum):
    """Economic event status."""

    SCHEDULED = "scheduled"
    RELEASED = "released"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


class CalendarProvider(Enum):
    """Economic calendar data providers."""

    FOREX_FACTORY = "forex_factory"
    TRADING_ECONOMICS = "trading_economics"
    ECONOMIC_CALENDAR_API = "economic_calendar_api"
    MOCK_PROVIDER = "mock_provider"  # For testing


@dataclass
class EconomicEvent:
    """Economic event data structure."""

    event_id: str
    title: str
    country: str
    currency: str
    date_time: datetime
    impact: EventImpact
    status: EventStatus = EventStatus.SCHEDULED
    category: str = ""
    description: str = ""
    previous_value: Optional[float] = None
    forecast_value: Optional[float] = None
    actual_value: Optional[float] = None
    unit: str = ""
    source: str = ""
    provider: CalendarProvider = CalendarProvider.MOCK_PROVIDER
    created_at: datetime = field(default_factory=lambda: datetime.utcnow())
    updated_at: datetime = field(default_factory=lambda: datetime.utcnow())

    @property
    def is_high_impact(self) -> bool:
        """Check if event is high impact."""
        return self.impact in [EventImpact.HIGH, EventImpact.CRITICAL]

    @property
    def is_upcoming(self) -> bool:
        """Check if event is upcoming."""
        return (
            self.date_time > datetime.utcnow() and self.status == EventStatus.SCHEDULED
        )

    @property
    def time_until_event(self) -> timedelta:
        """Get time until event occurs."""
        return self.date_time - datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "title": self.title,
            "country": self.country,
            "currency": self.currency,
            "date_time": self.date_time.isoformat(),
            "impact": self.impact.value,
            "status": self.status.value,
            "category": self.category,
            "description": self.description,
            "previous_value": self.previous_value,
            "forecast_value": self.forecast_value,
            "actual_value": self.actual_value,
            "unit": self.unit,
            "source": self.source,
            "provider": self.provider.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EconomicEvent":
        """Create event from dictionary."""
        return cls(
            event_id=data["event_id"],
            title=data["title"],
            country=data["country"],
            currency=data["currency"],
            date_time=datetime.fromisoformat(data["date_time"]),
            impact=EventImpact(data["impact"]),
            status=EventStatus(data["status"]),
            category=data.get("category", ""),
            description=data.get("description", ""),
            previous_value=data.get("previous_value"),
            forecast_value=data.get("forecast_value"),
            actual_value=data.get("actual_value"),
            unit=data.get("unit", ""),
            source=data.get("source", ""),
            provider=CalendarProvider(data.get("provider", "mock_provider")),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class EconomicDataProvider(ABC):
    """Abstract base class for economic data providers."""

    @abstractmethod
    async def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        currencies: Optional[Set[str]] = None,
    ) -> List[EconomicEvent]:
        """Fetch economic events from provider."""
        pass

    @abstractmethod
    async def get_event_details(self, event_id: str) -> Optional[EconomicEvent]:
        """Get detailed information for specific event."""
        pass


class MockEconomicProvider(EconomicDataProvider):
    """Mock economic data provider for testing."""

    def __init__(self):
        self.mock_events = self._generate_mock_events()

    def _generate_mock_events(self) -> List[EconomicEvent]:
        """Generate mock economic events for testing."""
        now = datetime.utcnow()
        events = []

        # NFP (First Friday of month)
        nfp_date = now.replace(day=1)
        while nfp_date.weekday() != 4:  # Find first Friday
            nfp_date += timedelta(days=1)
        nfp_date = nfp_date.replace(
            hour=13, minute=30, second=0, microsecond=0
        )  # 1:30 PM ET

        events.append(
            EconomicEvent(
                event_id="nfp_001",
                title="Non-Farm Payrolls",
                country="United States",
                currency="USD",
                date_time=nfp_date,
                impact=EventImpact.CRITICAL,
                category="Employment",
                description="Monthly change in the number of employed people",
                previous_value=250000,
                forecast_value=200000,
                unit="Jobs",
                source="Bureau of Labor Statistics",
                provider=CalendarProvider.MOCK_PROVIDER,
            )
        )

        # CPI (Mid-month)
        cpi_date = now.replace(day=15, hour=13, minute=30, second=0, microsecond=0)
        if cpi_date < now:
            cpi_date = cpi_date.replace(month=cpi_date.month + 1)

        events.append(
            EconomicEvent(
                event_id="cpi_001",
                title="Consumer Price Index",
                country="United States",
                currency="USD",
                date_time=cpi_date,
                impact=EventImpact.HIGH,
                category="Inflation",
                description="Monthly change in the price of goods and services",
                previous_value=0.3,
                forecast_value=0.2,
                unit="%",
                source="Bureau of Labor Statistics",
                provider=CalendarProvider.MOCK_PROVIDER,
            )
        )

        # Fed Rate Decision (FOMC meetings)
        fed_date = now.replace(
            day=20, hour=19, minute=0, second=0, microsecond=0
        )  # 2:00 PM ET
        if fed_date < now:
            fed_date = fed_date.replace(month=fed_date.month + 1)

        events.append(
            EconomicEvent(
                event_id="fed_001",
                title="Federal Funds Rate Decision",
                country="United States",
                currency="USD",
                date_time=fed_date,
                impact=EventImpact.CRITICAL,
                category="Monetary Policy",
                description="Federal Reserve interest rate decision",
                previous_value=5.25,
                forecast_value=5.25,
                unit="%",
                source="Federal Reserve",
                provider=CalendarProvider.MOCK_PROVIDER,
            )
        )

        # UK CPI
        uk_cpi_date = now.replace(
            day=18, hour=10, minute=0, second=0, microsecond=0
        )  # 10:00 AM GMT
        if uk_cpi_date < now:
            uk_cpi_date = uk_cpi_date.replace(month=uk_cpi_date.month + 1)

        events.append(
            EconomicEvent(
                event_id="uk_cpi_001",
                title="UK Consumer Price Index",
                country="United Kingdom",
                currency="GBP",
                date_time=uk_cpi_date,
                impact=EventImpact.HIGH,
                category="Inflation",
                description="UK monthly change in consumer prices",
                previous_value=0.4,
                forecast_value=0.3,
                unit="%",
                source="Office for National Statistics",
                provider=CalendarProvider.MOCK_PROVIDER,
            )
        )

        # EUR PMI
        eur_pmi_date = now.replace(
            day=24, hour=9, minute=0, second=0, microsecond=0
        )  # 9:00 AM CET
        if eur_pmi_date < now:
            eur_pmi_date = eur_pmi_date.replace(month=eur_pmi_date.month + 1)

        events.append(
            EconomicEvent(
                event_id="eur_pmi_001",
                title="Eurozone Manufacturing PMI",
                country="Eurozone",
                currency="EUR",
                date_time=eur_pmi_date,
                impact=EventImpact.MEDIUM,
                category="Manufacturing",
                description="Purchasing Managers Index for manufacturing",
                previous_value=46.5,
                forecast_value=47.0,
                unit="Index",
                source="S&P Global",
                provider=CalendarProvider.MOCK_PROVIDER,
            )
        )

        return events

    async def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        currencies: Optional[Set[str]] = None,
    ) -> List[EconomicEvent]:
        """Fetch mock events within date range."""
        events = []

        for event in self.mock_events:
            if start_date <= event.date_time <= end_date:
                if currencies is None or event.currency in currencies:
                    events.append(event)

        return events

    async def get_event_details(self, event_id: str) -> Optional[EconomicEvent]:
        """Get mock event details."""
        for event in self.mock_events:
            if event.event_id == event_id:
                return event
        return None


class EconomicCalendar:
    """
    Economic calendar service for managing economic events.

    Provides comprehensive economic event management including fetching,
    caching, filtering, and real-time updates.
    """

    def __init__(
        self,
        providers: Optional[List[EconomicDataProvider]] = None,
        cache_duration_hours: int = 24,
    ):
        self.providers = providers or [MockEconomicProvider()]
        self.cache_duration_hours = cache_duration_hours

        # Event storage
        self.events_cache: Dict[str, EconomicEvent] = {}
        self.events_by_date: Dict[str, List[str]] = defaultdict(
            list
        )  # date -> event_ids
        self.events_by_currency: Dict[str, List[str]] = defaultdict(
            list
        )  # currency -> event_ids

        # Cache management
        self.last_cache_update: Optional[datetime] = None
        self.cache_lock = asyncio.Lock()

        # Event filters
        self.high_impact_events = {
            "Non-Farm Payrolls",
            "Federal Funds Rate",
            "Consumer Price Index",
            "Gross Domestic Product",
            "European Central Bank Rate",
            "Bank of England Rate",
            "Employment Change",
            "Unemployment Rate",
            "Retail Sales",
            "Producer Price Index",
            "Core CPI",
        }

        logger.info(
            f"EconomicCalendar initialized with {len(self.providers)} providers"
        )

    async def fetch_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        currencies: Optional[Set[str]] = None,
        force_refresh: bool = False,
    ) -> List[EconomicEvent]:
        """Fetch economic events from providers."""
        # Set default date range if not provided
        if start_date is None:
            start_date = datetime.utcnow()
        if end_date is None:
            end_date = start_date + timedelta(days=30)

        # Check cache validity
        if not force_refresh and await self._is_cache_valid():
            return await self._get_cached_events(start_date, end_date, currencies)

        async with self.cache_lock:
            # Fetch from all providers
            all_events = []
            for provider in self.providers:
                try:
                    provider_events = await provider.fetch_events(
                        start_date, end_date, currencies
                    )
                    all_events.extend(provider_events)
                    logger.info(
                        f"Fetched {len(provider_events)} events from {provider.__class__.__name__}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error fetching events from {provider.__class__.__name__}: {e}"
                    )

            # Update cache
            await self._update_cache(all_events)
            self.last_cache_update = datetime.utcnow()

            logger.info(f"Updated calendar cache with {len(all_events)} total events")
            return all_events

    async def get_upcoming_events(
        self,
        hours_ahead: int = 24,
        currencies: Optional[Set[str]] = None,
        min_impact: EventImpact = EventImpact.MEDIUM,
    ) -> List[EconomicEvent]:
        """Get upcoming events within specified time window."""
        now = datetime.utcnow()
        end_time = now + timedelta(hours=hours_ahead)

        events = await self.fetch_events(now, end_time, currencies)

        # Filter by impact and upcoming status
        upcoming_events = [
            event
            for event in events
            if (
                event.is_upcoming
                and event.impact.value >= min_impact.value
                and now <= event.date_time <= end_time
            )
        ]

        # Sort by date
        upcoming_events.sort(key=lambda x: x.date_time)

        return upcoming_events

    async def get_high_impact_events(
        self, hours_ahead: int = 24, currencies: Optional[Set[str]] = None
    ) -> List[EconomicEvent]:
        """Get high-impact events within specified time window."""
        return await self.get_upcoming_events(
            hours_ahead=hours_ahead, currencies=currencies, min_impact=EventImpact.HIGH
        )

    async def get_events_by_currency(
        self,
        currency: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[EconomicEvent]:
        """Get events affecting specific currency."""
        events = await self.fetch_events(start_date, end_date, {currency})
        return [event for event in events if event.currency == currency]

    async def get_events_by_impact(
        self,
        impact: EventImpact,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[EconomicEvent]:
        """Get events by impact level."""
        events = await self.fetch_events(start_date, end_date)
        return [event for event in events if event.impact == impact]

    async def get_next_major_event(
        self, currencies: Optional[Set[str]] = None
    ) -> Optional[EconomicEvent]:
        """Get the next major (high/critical impact) event."""
        upcoming = await self.get_upcoming_events(
            hours_ahead=24 * 7,  # Look ahead 7 days
            currencies=currencies,
            min_impact=EventImpact.HIGH,
        )

        return upcoming[0] if upcoming else None

    async def is_trading_safe_period(
        self, currencies: Optional[Set[str]] = None, hours_buffer: int = 1
    ) -> bool:
        """Check if current time is safe for trading (no major events soon)."""
        upcoming = await self.get_high_impact_events(
            hours_ahead=hours_buffer, currencies=currencies
        )

        return len(upcoming) == 0

    async def get_event_details(self, event_id: str) -> Optional[EconomicEvent]:
        """Get detailed information for specific event."""
        # Check cache first
        if event_id in self.events_cache:
            return self.events_cache[event_id]

        # Fetch from providers
        for provider in self.providers:
            try:
                event = await provider.get_event_details(event_id)
                if event:
                    self.events_cache[event_id] = event
                    return event
            except Exception as e:
                logger.error(
                    f"Error getting event details from {provider.__class__.__name__}: {e}"
                )

        return None

    async def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if self.last_cache_update is None:
            return False

        cache_age = datetime.utcnow() - self.last_cache_update
        return cache_age.total_seconds() < (self.cache_duration_hours * 3600)

    async def _get_cached_events(
        self,
        start_date: datetime,
        end_date: datetime,
        currencies: Optional[Set[str]] = None,
    ) -> List[EconomicEvent]:
        """Get events from cache within date range."""
        cached_events = []

        for event in self.events_cache.values():
            if start_date <= event.date_time <= end_date:
                if currencies is None or event.currency in currencies:
                    cached_events.append(event)

        return cached_events

    async def _update_cache(self, events: List[EconomicEvent]) -> None:
        """Update event cache with new data."""
        # Clear existing cache
        self.events_cache.clear()
        self.events_by_date.clear()
        self.events_by_currency.clear()

        # Populate caches
        for event in events:
            self.events_cache[event.event_id] = event

            # Index by date
            date_key = event.date_time.date().isoformat()
            self.events_by_date[date_key].append(event.event_id)

            # Index by currency
            self.events_by_currency[event.currency].append(event.event_id)

    def get_calendar_summary(self) -> Dict[str, Any]:
        """Get calendar summary statistics."""
        total_events = len(self.events_cache)

        # Count by impact
        impact_counts = defaultdict(int)
        currency_counts = defaultdict(int)
        upcoming_count = 0

        for event in self.events_cache.values():
            impact_counts[event.impact.value] += 1
            currency_counts[event.currency] += 1
            if event.is_upcoming:
                upcoming_count += 1

        # Check cache validity synchronously
        cache_valid = False
        if self.last_cache_update is not None:
            cache_age = datetime.utcnow() - self.last_cache_update
            cache_valid = cache_age.total_seconds() < (self.cache_duration_hours * 3600)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_events": total_events,
            "upcoming_events": upcoming_count,
            "events_by_impact": dict(impact_counts),
            "events_by_currency": dict(currency_counts),
            "cache_last_updated": (
                self.last_cache_update.isoformat() if self.last_cache_update else None
            ),
            "cache_valid": cache_valid,
            "providers": [provider.__class__.__name__ for provider in self.providers],
        }

    async def add_custom_event(self, event: EconomicEvent) -> None:
        """Add custom event to calendar."""
        async with self.cache_lock:
            self.events_cache[event.event_id] = event

            # Update indices
            date_key = event.date_time.date().isoformat()
            self.events_by_date[date_key].append(event.event_id)
            self.events_by_currency[event.currency].append(event.event_id)

            logger.info(f"Added custom event: {event.title} ({event.event_id})")

    async def remove_event(self, event_id: str) -> bool:
        """Remove event from calendar."""
        async with self.cache_lock:
            if event_id not in self.events_cache:
                return False

            event = self.events_cache[event_id]

            # Remove from cache
            del self.events_cache[event_id]

            # Remove from indices
            date_key = event.date_time.date().isoformat()
            if event_id in self.events_by_date[date_key]:
                self.events_by_date[date_key].remove(event_id)

            if event_id in self.events_by_currency[event.currency]:
                self.events_by_currency[event.currency].remove(event_id)

            logger.info(f"Removed event: {event.title} ({event_id})")
            return True

    async def update_event_status(
        self, event_id: str, status: EventStatus, actual_value: Optional[float] = None
    ) -> bool:
        """Update event status and actual value."""
        if event_id not in self.events_cache:
            return False

        event = self.events_cache[event_id]
        event.status = status
        event.updated_at = datetime.utcnow()

        if actual_value is not None:
            event.actual_value = actual_value

        logger.info(
            f"Updated event {event_id}: status={status.value}, actual={actual_value}"
        )
        return True
