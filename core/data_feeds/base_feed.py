"""
Base Data Feed Interface for FXML4
==================================

Provides abstract base class and factory for all market data providers.
Ensures consistent API across different data sources with standardized
error handling, rate limiting, and data validation.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


class DataFeedStatus(Enum):
    """Data feed connection status."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass
class MarketDataTick:
    """Standardized market data tick structure."""

    timestamp: datetime
    symbol: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    volume: Optional[int] = None
    source: str = "unknown"
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MarketDataCandle:
    """Standardized OHLCV candle structure."""

    timestamp: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str
    metadata: Optional[Dict[str, Any]] = None


class RateLimiter:
    """Thread-safe rate limiter for API calls."""

    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.calls = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire a rate limit slot. Returns True if allowed, False if rate limited."""
        async with self._lock:
            now = time.time()
            # Remove calls older than 1 minute
            self.calls = [call_time for call_time in self.calls if now - call_time < 60]

            if len(self.calls) < self.calls_per_minute:
                self.calls.append(now)
                return True

            return False

    async def wait_for_slot(self):
        """Wait until a rate limit slot is available."""
        while not await self.acquire():
            await asyncio.sleep(1)


class BaseDataFeed(ABC):
    """
    Abstract base class for all market data feeds.

    Provides standardized interface with:
    - Connection management
    - Rate limiting
    - Error handling
    - Data validation
    - Health monitoring
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.status = DataFeedStatus.DISCONNECTED
        self.last_error: Optional[str] = None
        self.connection_count = 0
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.last_request_time: Optional[datetime] = None

        # Rate limiting
        rate_limit = config.get("rate_limit", 60)  # calls per minute
        self.rate_limiter = RateLimiter(rate_limit)

        # Health monitoring
        self.health_check_interval = config.get("health_check_interval", 60)  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_running = False

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the data feed."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close connection to the data feed."""
        pass

    @abstractmethod
    async def get_real_time_quote(self, symbol: str) -> Optional[MarketDataTick]:
        """Get real-time quote for a symbol."""
        pass

    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[MarketDataCandle]:
        """Get historical OHLCV data."""
        pass

    @abstractmethod
    async def subscribe_real_time(self, symbols: List[str], callback) -> bool:
        """Subscribe to real-time data stream."""
        pass

    @abstractmethod
    async def unsubscribe_real_time(self, symbols: List[str]) -> bool:
        """Unsubscribe from real-time data stream."""
        pass

    async def start(self) -> bool:
        """Start the data feed with health monitoring."""
        try:
            self._is_running = True
            self.status = DataFeedStatus.CONNECTING

            success = await self.connect()
            if success:
                self.status = DataFeedStatus.CONNECTED
                self.connection_count += 1

                # Start health monitoring
                self._health_check_task = asyncio.create_task(self._health_monitor())

                logger.info(f"✅ {self.__class__.__name__} started successfully")
                return True
            else:
                self.status = DataFeedStatus.ERROR
                logger.error(f"❌ Failed to start {self.__class__.__name__}")
                return False

        except Exception as e:
            self.last_error = str(e)
            self.status = DataFeedStatus.ERROR
            logger.error(f"❌ Error starting {self.__class__.__name__}: {e}")
            return False

    async def stop(self):
        """Stop the data feed and cleanup resources."""
        try:
            self._is_running = False

            # Stop health monitoring
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass

            # Disconnect
            await self.disconnect()
            self.status = DataFeedStatus.DISCONNECTED

            logger.info(f"✅ {self.__class__.__name__} stopped")

        except Exception as e:
            logger.error(f"❌ Error stopping {self.__class__.__name__}: {e}")

    async def _health_monitor(self):
        """Background task to monitor feed health."""
        while self._is_running:
            try:
                await asyncio.sleep(self.health_check_interval)

                if self._is_running:
                    is_healthy = await self._perform_health_check()

                    if not is_healthy and self.status == DataFeedStatus.CONNECTED:
                        logger.warning(
                            f"⚠️ {self.__class__.__name__} health check failed, attempting reconnection"
                        )
                        await self._attempt_reconnection()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"❌ Health monitor error for {self.__class__.__name__}: {e}"
                )

    async def _perform_health_check(self) -> bool:
        """Perform health check. Override in subclasses for specific checks."""
        try:
            # Default health check: try to get a quote for a major pair
            test_symbol = self.config.get("health_check_symbol", "EURUSD")
            quote = await self.get_real_time_quote(test_symbol)
            return quote is not None
        except Exception:
            return False

    async def _attempt_reconnection(self):
        """Attempt to reconnect after connection failure."""
        max_retries = self.config.get("max_reconnect_attempts", 3)
        retry_delay = self.config.get("reconnect_delay", 5)  # seconds

        self.status = DataFeedStatus.RECONNECTING

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"🔄 Reconnection attempt {attempt + 1}/{max_retries} for {self.__class__.__name__}"
                )

                await self.disconnect()
                await asyncio.sleep(retry_delay)

                success = await self.connect()
                if success:
                    self.status = DataFeedStatus.CONNECTED
                    self.connection_count += 1
                    logger.info(
                        f"✅ {self.__class__.__name__} reconnected successfully"
                    )
                    return

            except Exception as e:
                logger.error(f"❌ Reconnection attempt {attempt + 1} failed: {e}")

        # All reconnection attempts failed
        self.status = DataFeedStatus.ERROR
        self.last_error = "Failed to reconnect after multiple attempts"
        logger.error(
            f"❌ {self.__class__.__name__} reconnection failed after {max_retries} attempts"
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get feed performance statistics."""
        success_rate = 0.0
        if self.total_requests > 0:
            success_rate = (self.successful_requests / self.total_requests) * 100

        return {
            "status": self.status.value,
            "connection_count": self.connection_count,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate_percent": round(success_rate, 2),
            "last_request_time": (
                self.last_request_time.isoformat() if self.last_request_time else None
            ),
            "last_error": self.last_error,
        }

    def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol format is supported by this feed."""
        return len(symbol) >= 3  # Basic validation

    def normalize_timeframe(self, timeframe: str) -> str:
        """Normalize timeframe to feed-specific format."""
        return timeframe  # Override in subclasses

    async def _track_request(self, success: bool):
        """Track request statistics."""
        self.total_requests += 1
        self.last_request_time = datetime.now(timezone.utc)

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1


class DataFeedFactory:
    """Factory for creating data feed instances."""

    _feed_classes = {}

    @classmethod
    def register_feed(cls, name: str, feed_class: type):
        """Register a data feed class."""
        cls._feed_classes[name] = feed_class

    @classmethod
    def create_feed(cls, name: str, config: Dict[str, Any]) -> Optional[BaseDataFeed]:
        """Create a data feed instance by name."""
        feed_class = cls._feed_classes.get(name)
        if feed_class:
            return feed_class(config)

        logger.error(f"❌ Unknown data feed: {name}")
        return None

    @classmethod
    def list_available_feeds(cls) -> List[str]:
        """List all registered data feed names."""
        return list(cls._feed_classes.keys())


# Auto-register feeds when importing
def _auto_register_feeds():
    """Auto-register available data feeds."""
    try:
        from .alpha_vantage_feed import AlphaVantageDataFeed

        DataFeedFactory.register_feed("alpha_vantage", AlphaVantageDataFeed)
    except ImportError:
        pass

    try:
        from .polygon_feed import PolygonDataFeed

        DataFeedFactory.register_feed("polygon", PolygonDataFeed)
    except ImportError:
        pass


# Register feeds on module import
_auto_register_feeds()
