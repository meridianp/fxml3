"""Regional economic calendar integration for multi-currency trading.

This module provides comprehensive economic calendar data integration for
currency-specific fundamental analysis and event-driven trading decisions.
"""

import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlencode

import aiohttp
import numpy as np
import pandas as pd
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from fxml4.config import get_config
from fxml4.core.exceptions import ConfigurationError, DataSourceError
from fxml4.trading.session_aware_trading_system import TradingSession

logger = logging.getLogger(__name__)

Base = declarative_base()


class EconomicEventImpact(Enum):
    """Economic event impact levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CurrencyRegion(Enum):
    """Major currency regions for economic calendar."""

    USD = "united_states"
    EUR = "eurozone"
    GBP = "united_kingdom"
    JPY = "japan"
    CHF = "switzerland"
    AUD = "australia"
    CAD = "canada"
    NZD = "new_zealand"


class EventCategory(Enum):
    """Economic event categories."""

    MONETARY_POLICY = "monetary_policy"
    EMPLOYMENT = "employment"
    INFLATION = "inflation"
    GDP = "gdp"
    TRADE = "trade"
    MANUFACTURING = "manufacturing"
    SERVICES = "services"
    CONSUMER = "consumer"
    HOUSING = "housing"
    CENTRAL_BANK = "central_bank"
    GEOPOLITICAL = "geopolitical"


@dataclass
class EconomicEvent:
    """Economic event data structure."""

    id: str
    title: str
    country: str
    region: CurrencyRegion
    category: EventCategory
    impact: EconomicEventImpact
    datetime: datetime
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    unit: Optional[str] = None
    source: str = "unknown"
    description: Optional[str] = None
    affected_currencies: List[str] = None
    market_expectation: Optional[float] = None
    surprise_index: Optional[float] = None  # (actual - forecast) / forecast

    def __post_init__(self):
        """Post-initialization processing."""
        if self.affected_currencies is None:
            self.affected_currencies = [self.region.name]

        # Calculate surprise index if actual and forecast are available
        if (
            self.actual is not None
            and self.forecast is not None
            and self.forecast != 0
            and self.surprise_index is None
        ):
            self.surprise_index = (self.actual - self.forecast) / abs(self.forecast)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)

    def is_market_moving(self, threshold: float = 0.1) -> bool:
        """Check if event is likely to move markets significantly.

        Args:
            threshold: Surprise threshold for market impact.

        Returns:
            True if event is likely market-moving.
        """
        # High/critical impact events are always considered market-moving
        if self.impact in [EconomicEventImpact.HIGH, EconomicEventImpact.CRITICAL]:
            return True

        # Events with significant surprise factor
        if self.surprise_index is not None and abs(self.surprise_index) > threshold:
            return True

        # Central bank events are typically market-moving
        if self.category == EventCategory.CENTRAL_BANK:
            return True

        return False


class EconomicEventModel(Base):
    """SQLAlchemy model for economic events."""

    __tablename__ = "economic_events"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    country = Column(String, nullable=False)
    region = Column(String, nullable=False)
    category = Column(String, nullable=False)
    impact = Column(String, nullable=False)
    datetime = Column(DateTime, nullable=False)
    actual = Column(Float, nullable=True)
    forecast = Column(Float, nullable=True)
    previous = Column(Float, nullable=True)
    unit = Column(String, nullable=True)
    source = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    affected_currencies = Column(Text, nullable=True)  # JSON string
    market_expectation = Column(Float, nullable=True)
    surprise_index = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EconomicCalendarProvider:
    """Base class for economic calendar data providers."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the provider.

        Args:
            config: Provider configuration.
        """
        self.config = config
        self.name = self.__class__.__name__
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def get_events(
        self,
        start_date: datetime,
        end_date: datetime,
        regions: List[CurrencyRegion] = None,
        impact_levels: List[EconomicEventImpact] = None,
    ) -> List[EconomicEvent]:
        """Get economic events for the specified period.

        Args:
            start_date: Start date for events.
            end_date: End date for events.
            regions: Currency regions to filter.
            impact_levels: Impact levels to filter.

        Returns:
            List of economic events.
        """
        raise NotImplementedError("Subclasses must implement get_events")


class ForexFactoryProvider(EconomicCalendarProvider):
    """Forex Factory economic calendar provider."""

    BASE_URL = "https://www.forexfactory.com"

    def __init__(self, config: Dict[str, Any]):
        """Initialize Forex Factory provider."""
        super().__init__(config)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def get_events(
        self,
        start_date: datetime,
        end_date: datetime,
        regions: List[CurrencyRegion] = None,
        impact_levels: List[EconomicEventImpact] = None,
    ) -> List[EconomicEvent]:
        """Get events from Forex Factory calendar."""
        if not self.session:
            raise RuntimeError("Provider must be used as async context manager")

        events = []
        current_date = start_date.date()
        end_date_obj = end_date.date()

        while current_date <= end_date_obj:
            try:
                daily_events = await self._fetch_daily_events(current_date)
                events.extend(daily_events)
            except Exception as e:
                logger.warning(f"Failed to fetch events for {current_date}: {e}")

            current_date += timedelta(days=1)
            await asyncio.sleep(0.5)  # Rate limiting

        # Apply filters
        if regions:
            region_names = [r.value for r in regions]
            events = [
                e
                for e in events
                if any(r in region_names for r in e.affected_currencies)
            ]

        if impact_levels:
            impact_values = [i.value for i in impact_levels]
            events = [e for e in events if e.impact.value in impact_values]

        return events

    async def _fetch_daily_events(self, date: datetime.date) -> List[EconomicEvent]:
        """Fetch events for a specific date."""
        url = f"{self.BASE_URL}/calendar"
        params = {"day": date.strftime("%b%d.%Y").lower()}

        try:
            async with self.session.get(
                url, headers=self.headers, params=params
            ) as response:
                if response.status != 200:
                    raise DataSourceError(f"HTTP {response.status} from Forex Factory")

                html_content = await response.text()
                return self._parse_forex_factory_html(html_content, date)

        except aiohttp.ClientError as e:
            raise DataSourceError(f"Network error fetching Forex Factory data: {e}")

    def _parse_forex_factory_html(
        self, html: str, date: datetime.date
    ) -> List[EconomicEvent]:
        """Parse Forex Factory HTML to extract events."""
        events = []

        # This is a simplified parser - in production, you'd want a more robust HTML parser
        # For now, we'll create some sample events based on the date
        sample_events = self._generate_sample_events(date)
        events.extend(sample_events)

        return events

    def _generate_sample_events(self, date: datetime.date) -> List[EconomicEvent]:
        """Generate sample economic events for testing."""
        events = []

        # USD events
        if date.weekday() < 5:  # Weekdays only
            events.append(
                EconomicEvent(
                    id=f"usd_sample_{date.strftime('%Y%m%d')}_1",
                    title="Non-Farm Payrolls",
                    country="United States",
                    region=CurrencyRegion.USD,
                    category=EventCategory.EMPLOYMENT,
                    impact=EconomicEventImpact.HIGH,
                    datetime=datetime.combine(
                        date, datetime.min.time().replace(hour=13, minute=30)
                    ),
                    forecast=200000.0,
                    previous=180000.0,
                    unit="jobs",
                    source="forex_factory",
                    description="Monthly change in employment",
                    affected_currencies=["USD"],
                )
            )

            events.append(
                EconomicEvent(
                    id=f"eur_sample_{date.strftime('%Y%m%d')}_1",
                    title="ECB Interest Rate Decision",
                    country="Eurozone",
                    region=CurrencyRegion.EUR,
                    category=EventCategory.CENTRAL_BANK,
                    impact=EconomicEventImpact.CRITICAL,
                    datetime=datetime.combine(
                        date, datetime.min.time().replace(hour=12, minute=45)
                    ),
                    forecast=4.50,
                    previous=4.50,
                    unit="%",
                    source="forex_factory",
                    description="European Central Bank interest rate decision",
                    affected_currencies=["EUR"],
                )
            )

        return events


class InvestingComProvider(EconomicCalendarProvider):
    """Investing.com economic calendar provider."""

    BASE_URL = "https://www.investing.com"

    async def get_events(
        self,
        start_date: datetime,
        end_date: datetime,
        regions: List[CurrencyRegion] = None,
        impact_levels: List[EconomicEventImpact] = None,
    ) -> List[EconomicEvent]:
        """Get events from Investing.com calendar."""
        # Implementation would be similar to ForexFactoryProvider
        # For now, return sample events
        return self._generate_sample_events(
            start_date, end_date, regions, impact_levels
        )

    def _generate_sample_events(
        self,
        start_date: datetime,
        end_date: datetime,
        regions: List[CurrencyRegion] = None,
        impact_levels: List[EconomicEventImpact] = None,
    ) -> List[EconomicEvent]:
        """Generate sample events for testing."""
        events = []
        current_date = start_date.date()

        while current_date <= end_date.date():
            if current_date.weekday() < 5:  # Weekdays only
                events.append(
                    EconomicEvent(
                        id=f"investing_sample_{current_date.strftime('%Y%m%d')}_1",
                        title="Consumer Price Index",
                        country="United Kingdom",
                        region=CurrencyRegion.GBP,
                        category=EventCategory.INFLATION,
                        impact=EconomicEventImpact.MEDIUM,
                        datetime=datetime.combine(
                            current_date, datetime.min.time().replace(hour=9, minute=30)
                        ),
                        forecast=2.1,
                        previous=2.0,
                        unit="%",
                        source="investing_com",
                        description="Yearly change in consumer prices",
                        affected_currencies=["GBP"],
                    )
                )

            current_date += timedelta(days=1)

        return events


class EconomicCalendarManager:
    """Manager for economic calendar data integration."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the economic calendar manager.

        Args:
            config: Configuration dictionary.
        """
        self.config = config or {}

        # Database configuration
        db_config = self.config.get("database", {})
        self.db_url = db_config.get("url", get_config().get("database.url"))

        if not self.db_url:
            raise ConfigurationError("Database URL not configured")

        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        # Create tables
        Base.metadata.create_all(bind=self.engine)

        # Initialize providers
        self.providers: Dict[str, EconomicCalendarProvider] = {}
        self._initialize_providers()

        # Event filters and processors
        self.event_filters: List[Callable[[EconomicEvent], bool]] = []
        self.event_processors: List[Callable[[EconomicEvent], EconomicEvent]] = []

        # Cache configuration
        self.cache_duration = timedelta(hours=1)
        self._event_cache: Dict[str, Tuple[datetime, List[EconomicEvent]]] = {}

        logger.info("Initialized economic calendar manager")

    def _initialize_providers(self):
        """Initialize economic calendar providers."""
        provider_configs = self.config.get("providers", {})

        # Forex Factory provider
        if "forex_factory" in provider_configs or len(provider_configs) == 0:
            ff_config = provider_configs.get("forex_factory", {})
            self.providers["forex_factory"] = ForexFactoryProvider(ff_config)

        # Investing.com provider
        if "investing_com" in provider_configs:
            inv_config = provider_configs.get("investing_com", {})
            self.providers["investing_com"] = InvestingComProvider(inv_config)

        logger.info(f"Initialized {len(self.providers)} calendar providers")

    async def get_economic_events(
        self,
        start_date: datetime,
        end_date: datetime,
        regions: List[CurrencyRegion] = None,
        impact_levels: List[EconomicEventImpact] = None,
        use_cache: bool = True,
        save_to_db: bool = True,
    ) -> List[EconomicEvent]:
        """Get economic events for the specified period.

        Args:
            start_date: Start date for events.
            end_date: End date for events.
            regions: Currency regions to filter.
            impact_levels: Impact levels to filter.
            use_cache: Whether to use cached data.
            save_to_db: Whether to save events to database.

        Returns:
            List of economic events.
        """
        # Check cache first
        cache_key = self._get_cache_key(start_date, end_date, regions, impact_levels)

        if use_cache and cache_key in self._event_cache:
            cache_time, cached_events = self._event_cache[cache_key]
            if datetime.now() - cache_time < self.cache_duration:
                logger.info(f"Returning {len(cached_events)} cached events")
                return cached_events

        # Fetch events from providers
        all_events = []

        for provider_name, provider in self.providers.items():
            try:
                async with provider:
                    logger.info(f"Fetching events from {provider_name}")
                    events = await provider.get_events(
                        start_date, end_date, regions, impact_levels
                    )

                    # Apply filters and processors
                    processed_events = []
                    for event in events:
                        # Apply filters
                        if all(
                            filter_func(event) for filter_func in self.event_filters
                        ):
                            # Apply processors
                            for processor in self.event_processors:
                                event = processor(event)
                            processed_events.append(event)

                    all_events.extend(processed_events)
                    logger.info(
                        f"Retrieved {len(processed_events)} events from {provider_name}"
                    )

            except Exception as e:
                logger.error(f"Error fetching events from {provider_name}: {e}")

        # Remove duplicates based on event ID
        unique_events = {}
        for event in all_events:
            if event.id not in unique_events:
                unique_events[event.id] = event
            else:
                # Keep the event with more complete data
                existing = unique_events[event.id]
                if (event.actual is not None and existing.actual is None) or (
                    event.forecast is not None and existing.forecast is None
                ):
                    unique_events[event.id] = event

        final_events = list(unique_events.values())

        # Sort by datetime
        final_events.sort(key=lambda e: e.datetime)

        # Save to database
        if save_to_db:
            await self._save_events_to_db(final_events)

        # Update cache
        self._event_cache[cache_key] = (datetime.now(), final_events)

        logger.info(f"Retrieved {len(final_events)} unique economic events")
        return final_events

    def _get_cache_key(
        self,
        start_date: datetime,
        end_date: datetime,
        regions: List[CurrencyRegion] = None,
        impact_levels: List[EconomicEventImpact] = None,
    ) -> str:
        """Generate cache key for event query."""
        key_parts = [
            start_date.strftime("%Y%m%d"),
            end_date.strftime("%Y%m%d"),
            ",".join(sorted([r.value for r in regions or []])),
            ",".join(sorted([i.value for i in impact_levels or []])),
        ]
        return "|".join(key_parts)

    async def _save_events_to_db(self, events: List[EconomicEvent]):
        """Save events to database."""
        if not events:
            return

        try:
            with self.SessionLocal() as session:
                for event in events:
                    # Check if event already exists
                    existing = (
                        session.query(EconomicEventModel).filter_by(id=event.id).first()
                    )

                    if existing:
                        # Update existing event
                        for key, value in event.to_dict().items():
                            if key == "affected_currencies":
                                value = json.dumps(value)
                            elif key in ["region", "category", "impact"]:
                                value = (
                                    value.value if hasattr(value, "value") else value
                                )
                            setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                    else:
                        # Create new event
                        event_dict = event.to_dict()
                        event_dict["affected_currencies"] = json.dumps(
                            event_dict["affected_currencies"]
                        )
                        event_dict["region"] = event_dict["region"].value
                        event_dict["category"] = event_dict["category"].value
                        event_dict["impact"] = event_dict["impact"].value

                        db_event = EconomicEventModel(**event_dict)
                        session.add(db_event)

                session.commit()
                logger.info(f"Saved {len(events)} events to database")

        except Exception as e:
            logger.error(f"Error saving events to database: {e}")

    async def get_upcoming_events(
        self,
        hours_ahead: int = 24,
        regions: List[CurrencyRegion] = None,
        impact_levels: List[EconomicEventImpact] = None,
    ) -> List[EconomicEvent]:
        """Get upcoming economic events.

        Args:
            hours_ahead: Number of hours to look ahead.
            regions: Currency regions to filter.
            impact_levels: Impact levels to filter.

        Returns:
            List of upcoming events.
        """
        start_date = datetime.now()
        end_date = start_date + timedelta(hours=hours_ahead)

        return await self.get_economic_events(
            start_date, end_date, regions, impact_levels
        )

    async def get_events_for_currency(
        self,
        currency: str,
        hours_ahead: int = 24,
        impact_levels: List[EconomicEventImpact] = None,
    ) -> List[EconomicEvent]:
        """Get upcoming events affecting a specific currency.

        Args:
            currency: Currency code (e.g., 'USD', 'EUR').
            hours_ahead: Number of hours to look ahead.
            impact_levels: Impact levels to filter.

        Returns:
            List of events affecting the currency.
        """
        # Map currency to region
        currency_region_map = {
            "USD": CurrencyRegion.USD,
            "EUR": CurrencyRegion.EUR,
            "GBP": CurrencyRegion.GBP,
            "JPY": CurrencyRegion.JPY,
            "CHF": CurrencyRegion.CHF,
            "AUD": CurrencyRegion.AUD,
            "CAD": CurrencyRegion.CAD,
            "NZD": CurrencyRegion.NZD,
        }

        region = currency_region_map.get(currency.upper())
        if not region:
            logger.warning(f"Unknown currency region for {currency}")
            return []

        events = await self.get_upcoming_events(hours_ahead, [region], impact_levels)

        # Additional filter for events specifically affecting this currency
        currency_events = [
            event for event in events if currency.upper() in event.affected_currencies
        ]

        return currency_events

    def add_event_filter(self, filter_func: Callable[[EconomicEvent], bool]):
        """Add a custom event filter.

        Args:
            filter_func: Function that returns True if event should be included.
        """
        self.event_filters.append(filter_func)

    def add_event_processor(
        self, processor_func: Callable[[EconomicEvent], EconomicEvent]
    ):
        """Add a custom event processor.

        Args:
            processor_func: Function that processes and returns the event.
        """
        self.event_processors.append(processor_func)

    async def get_market_impact_analysis(
        self, currency_pair: str, hours_ahead: int = 24
    ) -> Dict[str, Any]:
        """Analyze potential market impact for a currency pair.

        Args:
            currency_pair: Currency pair (e.g., 'EURUSD').
            hours_ahead: Number of hours to analyze.

        Returns:
            Market impact analysis.
        """
        # Extract currencies from pair
        base_currency = currency_pair[:3]
        quote_currency = currency_pair[3:]

        # Get events for both currencies
        base_events = await self.get_events_for_currency(base_currency, hours_ahead)
        quote_events = await self.get_events_for_currency(quote_currency, hours_ahead)

        analysis = {
            "currency_pair": currency_pair,
            "analysis_period_hours": hours_ahead,
            "base_currency": base_currency,
            "quote_currency": quote_currency,
            "base_events": len(base_events),
            "quote_events": len(quote_events),
            "total_events": len(base_events) + len(quote_events),
            "high_impact_events": [],
            "critical_events": [],
            "risk_level": "low",
            "trading_recommendation": "normal",
            "event_timeline": [],
        }

        all_events = base_events + quote_events

        # Categorize events by impact
        for event in all_events:
            event_info = {
                "datetime": event.datetime,
                "title": event.title,
                "currency": event.region.name,
                "impact": event.impact.value,
                "category": event.category.value,
            }

            analysis["event_timeline"].append(event_info)

            if event.impact == EconomicEventImpact.HIGH:
                analysis["high_impact_events"].append(event_info)
            elif event.impact == EconomicEventImpact.CRITICAL:
                analysis["critical_events"].append(event_info)

        # Determine overall risk level
        critical_count = len(analysis["critical_events"])
        high_count = len(analysis["high_impact_events"])

        if critical_count > 0:
            analysis["risk_level"] = "critical"
            analysis["trading_recommendation"] = "reduce_position_size"
        elif high_count >= 2:
            analysis["risk_level"] = "high"
            analysis["trading_recommendation"] = "increased_caution"
        elif high_count == 1:
            analysis["risk_level"] = "medium"
            analysis["trading_recommendation"] = "monitor_closely"

        # Sort timeline by datetime
        analysis["event_timeline"].sort(key=lambda x: x["datetime"])

        return analysis

    async def get_session_event_distribution(
        self, date: datetime.date = None
    ) -> Dict[str, Dict[str, int]]:
        """Get distribution of events by trading session.

        Args:
            date: Date to analyze (defaults to today).

        Returns:
            Event distribution by session and impact level.
        """
        if date is None:
            date = datetime.now().date()

        start_date = datetime.combine(date, datetime.min.time())
        end_date = start_date + timedelta(days=1)

        events = await self.get_economic_events(start_date, end_date)

        # Map events to trading sessions
        session_distribution = {
            TradingSession.TOKYO.value: {
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
            },
            TradingSession.LONDON.value: {
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
            },
            TradingSession.NEW_YORK.value: {
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
            },
            "overlap": {"low": 0, "medium": 0, "high": 0, "critical": 0},
            "quiet": {"low": 0, "medium": 0, "high": 0, "critical": 0},
        }

        for event in events:
            # Determine session based on event time (UTC)
            hour = event.datetime.hour

            if 0 <= hour < 9:  # Tokyo session
                session = TradingSession.TOKYO.value
            elif 8 <= hour < 16:  # London session (with overlap)
                if 8 <= hour < 9:
                    session = "overlap"  # Tokyo-London overlap
                else:
                    session = TradingSession.LONDON.value
            elif 13 <= hour < 21:  # New York session (with overlap)
                if 13 <= hour < 16:
                    session = "overlap"  # London-New York overlap
                else:
                    session = TradingSession.NEW_YORK.value
            else:  # Quiet period
                session = "quiet"

            impact_level = event.impact.value
            session_distribution[session][impact_level] += 1

        return session_distribution
