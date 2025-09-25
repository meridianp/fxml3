"""
Data Feed Manager for FXML4
===========================

Centralized management for multiple market data feeds with:
- Provider failover and redundancy
- Load balancing across feeds
- Health monitoring and alerting
- Performance tracking and optimization
- Configuration management

This manager orchestrates multiple data feeds to provide reliable,
high-performance market data for the trading system.
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .alpha_vantage_feed import AlphaVantageDataFeed
from .base_feed import BaseDataFeed, DataFeedStatus, MarketDataCandle, MarketDataTick
from .polygon_feed import PolygonDataFeed

logger = logging.getLogger(__name__)


class FeedPriority(Enum):
    """Feed priority levels for failover."""

    PRIMARY = 1
    SECONDARY = 2
    BACKUP = 3


@dataclass
class FeedConfig:
    """Configuration for a single data feed."""

    name: str
    feed_class: type
    config: Dict[str, Any]
    priority: FeedPriority = FeedPriority.SECONDARY
    enabled: bool = True
    symbols: Optional[List[str]] = None  # Supported symbols, None = all
    max_failures: int = 5
    failure_window_minutes: int = 15


@dataclass
class FeedMetrics:
    """Performance metrics for a data feed."""

    name: str
    requests_total: int = 0
    requests_successful: int = 0
    requests_failed: int = 0
    avg_response_time_ms: float = 0.0
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    consecutive_failures: int = 0
    uptime_percent: float = 100.0
    failure_times: List[datetime] = field(default_factory=list)


class DataFeedManager:
    """
    Centralized manager for multiple market data feeds.

    Provides high availability through feed redundancy, automatic failover,
    load balancing, and comprehensive monitoring.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.feeds: Dict[str, BaseDataFeed] = {}
        self.feed_configs: Dict[str, FeedConfig] = {}
        self.feed_metrics: Dict[str, FeedMetrics] = {}

        # Feed management
        self.active_feeds: Set[str] = set()
        self.failed_feeds: Set[str] = set()

        # Real-time subscriptions
        self.symbol_subscriptions: Dict[str, Set[str]] = defaultdict(
            set
        )  # symbol -> feed_names
        self.subscription_callbacks: Dict[str, Callable] = {}  # symbol -> callback

        # Monitoring
        self.health_check_interval = config.get("health_check_interval", 60)
        self.metrics_interval = config.get("metrics_interval", 300)  # 5 minutes
        self._monitoring_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._is_running = False

        # Load balancing
        self._request_counts: Dict[str, int] = defaultdict(int)
        self._last_used_feed: Dict[str, str] = {}  # symbol -> feed_name

    async def initialize(self, feed_configs: List[Dict[str, Any]]) -> bool:
        """Initialize all configured data feeds."""
        try:
            logger.info("🚀 Initializing Data Feed Manager...")

            # Create feed instances
            for feed_config in feed_configs:
                success = await self._create_feed(feed_config)
                if not success:
                    logger.warning(
                        f"⚠️ Failed to create feed: {feed_config.get('name', 'Unknown')}"
                    )

            if not self.feeds:
                logger.error("❌ No data feeds available")
                return False

            # Connect all feeds
            connection_tasks = []
            for feed_name, feed in self.feeds.items():
                task = asyncio.create_task(
                    self._connect_feed_with_metrics(feed_name, feed)
                )
                connection_tasks.append(task)

            results = await asyncio.gather(*connection_tasks, return_exceptions=True)

            # Count successful connections
            successful_connections = sum(1 for result in results if result is True)

            if successful_connections == 0:
                logger.error("❌ No data feeds connected successfully")
                return False

            logger.info(
                f"✅ Data Feed Manager initialized with {successful_connections}/{len(self.feeds)} feeds"
            )

            # Start monitoring
            await self._start_monitoring()
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize Data Feed Manager: {e}")
            return False

    async def _create_feed(self, feed_config: Dict[str, Any]) -> bool:
        """Create and configure a data feed instance."""
        try:
            name = feed_config.get("name")
            feed_type = feed_config.get("type")
            config = feed_config.get("config", {})

            if not all([name, feed_type]):
                logger.error(f"❌ Invalid feed configuration: missing name or type")
                return False

            # Map feed type to class
            feed_class_map = {
                "alpha_vantage": AlphaVantageDataFeed,
                "polygon": PolygonDataFeed,
            }

            feed_class = feed_class_map.get(feed_type)
            if not feed_class:
                logger.error(f"❌ Unknown feed type: {feed_type}")
                return False

            # Create feed configuration
            priority = FeedPriority(feed_config.get("priority", 2))
            symbols = feed_config.get("symbols")

            feed_cfg = FeedConfig(
                name=name,
                feed_class=feed_class,
                config=config,
                priority=priority,
                enabled=feed_config.get("enabled", True),
                symbols=symbols,
                max_failures=feed_config.get("max_failures", 5),
                failure_window_minutes=feed_config.get("failure_window_minutes", 15),
            )

            # Create feed instance
            feed_instance = feed_class(config)

            # Store configuration and instance
            self.feed_configs[name] = feed_cfg
            self.feeds[name] = feed_instance
            self.feed_metrics[name] = FeedMetrics(name=name)

            logger.info(f"✅ Created {feed_type} feed: {name}")
            return True

        except Exception as e:
            logger.error(f"❌ Error creating feed: {e}")
            return False

    async def _connect_feed_with_metrics(
        self, feed_name: str, feed: BaseDataFeed
    ) -> bool:
        """Connect feed and update metrics."""
        try:
            start_time = datetime.now()
            success = await feed.connect()
            response_time = (datetime.now() - start_time).total_seconds() * 1000

            metrics = self.feed_metrics[feed_name]
            metrics.requests_total += 1

            if success:
                metrics.requests_successful += 1
                metrics.last_success_time = datetime.now(timezone.utc)
                metrics.consecutive_failures = 0
                self.active_feeds.add(feed_name)
                self.failed_feeds.discard(feed_name)
                logger.info(f"✅ Connected to {feed_name} ({response_time:.1f}ms)")
            else:
                await self._handle_feed_failure(feed_name, "Connection failed")

            # Update average response time
            self._update_avg_response_time(feed_name, response_time)

            return success

        except Exception as e:
            await self._handle_feed_failure(feed_name, str(e))
            return False

    async def _handle_feed_failure(self, feed_name: str, error: str):
        """Handle feed failure and update metrics."""
        metrics = self.feed_metrics[feed_name]
        now = datetime.now(timezone.utc)

        metrics.requests_failed += 1
        metrics.last_failure_time = now
        metrics.consecutive_failures += 1
        metrics.failure_times.append(now)

        # Clean old failure times
        cutoff_time = now - timedelta(
            minutes=self.feed_configs[feed_name].failure_window_minutes
        )
        metrics.failure_times = [ft for ft in metrics.failure_times if ft > cutoff_time]

        # Check if feed should be disabled
        max_failures = self.feed_configs[feed_name].max_failures
        if len(metrics.failure_times) >= max_failures:
            self.active_feeds.discard(feed_name)
            self.failed_feeds.add(feed_name)
            logger.error(
                f"❌ {feed_name} disabled due to {len(metrics.failure_times)} failures: {error}"
            )
        else:
            logger.warning(
                f"⚠️ {feed_name} failure ({metrics.consecutive_failures}): {error}"
            )

    async def get_real_time_quote(
        self, symbol: str, preferred_feed: Optional[str] = None
    ) -> Optional[MarketDataTick]:
        """Get real-time quote with automatic feed selection and failover."""
        # Get list of available feeds for this symbol
        available_feeds = await self._get_available_feeds_for_symbol(symbol)
        if not available_feeds:
            logger.warning(f"⚠️ No available feeds for symbol: {symbol}")
            return None

        # Select feed based on preference and load balancing
        feed_name = await self._select_feed_for_request(
            symbol, available_feeds, preferred_feed
        )
        if not feed_name:
            return None

        # Attempt to get quote
        feed = self.feeds[feed_name]
        try:
            start_time = datetime.now()
            quote = await feed.get_real_time_quote(symbol)
            response_time = (datetime.now() - start_time).total_seconds() * 1000

            if quote:
                # Update metrics
                self._update_success_metrics(feed_name, response_time)
                self._last_used_feed[symbol] = feed_name
                return quote
            else:
                # Try fallback feeds
                return await self._try_fallback_feeds(
                    symbol, available_feeds, feed_name
                )

        except Exception as e:
            await self._handle_feed_failure(feed_name, str(e))
            return await self._try_fallback_feeds(symbol, available_feeds, feed_name)

    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        preferred_feed: Optional[str] = None,
    ) -> List[MarketDataCandle]:
        """Get historical data with automatic feed selection and failover."""
        available_feeds = await self._get_available_feeds_for_symbol(symbol)
        if not available_feeds:
            logger.warning(f"⚠️ No available feeds for symbol: {symbol}")
            return []

        feed_name = await self._select_feed_for_request(
            symbol, available_feeds, preferred_feed
        )
        if not feed_name:
            return []

        feed = self.feeds[feed_name]
        try:
            start_time_req = datetime.now()
            candles = await feed.get_historical_data(
                symbol, timeframe, start_time, end_time, limit
            )
            response_time = (datetime.now() - start_time_req).total_seconds() * 1000

            if candles:
                self._update_success_metrics(feed_name, response_time)
                return candles
            else:
                # Try fallback feeds
                return await self._try_fallback_historical_data(
                    symbol,
                    timeframe,
                    start_time,
                    end_time,
                    limit,
                    available_feeds,
                    feed_name,
                )

        except Exception as e:
            await self._handle_feed_failure(feed_name, str(e))
            return await self._try_fallback_historical_data(
                symbol,
                timeframe,
                start_time,
                end_time,
                limit,
                available_feeds,
                feed_name,
            )

    async def subscribe_real_time(
        self, symbols: List[str], callback: Callable
    ) -> Dict[str, bool]:
        """Subscribe to real-time data across multiple feeds for redundancy."""
        results = {}

        for symbol in symbols:
            self.subscription_callbacks[symbol] = callback
            available_feeds = await self._get_available_feeds_for_symbol(symbol)

            symbol_success = False
            for feed_name in available_feeds:
                try:
                    feed = self.feeds[feed_name]
                    success = await feed.subscribe_real_time([symbol], callback)

                    if success:
                        self.symbol_subscriptions[symbol].add(feed_name)
                        symbol_success = True
                        logger.info(f"📡 Subscribed {symbol} to {feed_name}")

                        # For redundancy, subscribe to multiple feeds if available
                        if len(self.symbol_subscriptions[symbol]) >= 2:
                            break

                except Exception as e:
                    logger.error(
                        f"❌ Subscription failed for {symbol} on {feed_name}: {e}"
                    )
                    await self._handle_feed_failure(feed_name, str(e))

            results[symbol] = symbol_success

        return results

    async def unsubscribe_real_time(self, symbols: List[str]) -> Dict[str, bool]:
        """Unsubscribe from real-time data across all feeds."""
        results = {}

        for symbol in symbols:
            symbol_feeds = self.symbol_subscriptions.get(symbol, set()).copy()
            symbol_success = True

            for feed_name in symbol_feeds:
                try:
                    feed = self.feeds[feed_name]
                    success = await feed.unsubscribe_real_time([symbol])
                    if not success:
                        symbol_success = False
                except Exception as e:
                    logger.error(
                        f"❌ Unsubscription failed for {symbol} on {feed_name}: {e}"
                    )
                    symbol_success = False

            # Clean up subscriptions
            self.symbol_subscriptions[symbol].clear()
            self.subscription_callbacks.pop(symbol, None)
            results[symbol] = symbol_success

        return results

    async def _get_available_feeds_for_symbol(self, symbol: str) -> List[str]:
        """Get list of available feeds that support the given symbol."""
        available = []

        for feed_name in self.active_feeds:
            feed_config = self.feed_configs[feed_name]
            if not feed_config.enabled:
                continue

            # Check if feed supports this symbol
            if feed_config.symbols is None:
                # No symbol restriction, check if feed validates symbol
                feed = self.feeds[feed_name]
                if feed.validate_symbol(symbol):
                    available.append(feed_name)
            elif symbol in feed_config.symbols:
                available.append(feed_name)

        # Sort by priority (lower number = higher priority)
        available.sort(key=lambda name: self.feed_configs[name].priority.value)
        return available

    async def _select_feed_for_request(
        self,
        symbol: str,
        available_feeds: List[str],
        preferred_feed: Optional[str] = None,
    ) -> Optional[str]:
        """Select best feed for request based on preference, load balancing, and performance."""
        if not available_feeds:
            return None

        # Use preferred feed if available and active
        if preferred_feed and preferred_feed in available_feeds:
            return preferred_feed

        # Use last successful feed for this symbol if still available
        last_used = self._last_used_feed.get(symbol)
        if last_used and last_used in available_feeds:
            return last_used

        # Load balancing: select feed with lowest request count
        feed_loads = {feed: self._request_counts[feed] for feed in available_feeds}
        return min(feed_loads, key=feed_loads.get)

    async def _try_fallback_feeds(
        self, symbol: str, available_feeds: List[str], failed_feed: str
    ) -> Optional[MarketDataTick]:
        """Try fallback feeds when primary feed fails."""
        fallback_feeds = [f for f in available_feeds if f != failed_feed]

        for feed_name in fallback_feeds:
            try:
                feed = self.feeds[feed_name]
                start_time = datetime.now()
                quote = await feed.get_real_time_quote(symbol)
                response_time = (datetime.now() - start_time).total_seconds() * 1000

                if quote:
                    self._update_success_metrics(feed_name, response_time)
                    self._last_used_feed[symbol] = feed_name
                    logger.info(f"✅ Fallback success: {symbol} from {feed_name}")
                    return quote

            except Exception as e:
                await self._handle_feed_failure(feed_name, str(e))
                continue

        logger.error(f"❌ All feeds failed for {symbol}")
        return None

    async def _try_fallback_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        limit: Optional[int],
        available_feeds: List[str],
        failed_feed: str,
    ) -> List[MarketDataCandle]:
        """Try fallback feeds for historical data when primary feed fails."""
        fallback_feeds = [f for f in available_feeds if f != failed_feed]

        for feed_name in fallback_feeds:
            try:
                feed = self.feeds[feed_name]
                start_time_req = datetime.now()
                candles = await feed.get_historical_data(
                    symbol, timeframe, start_time, end_time, limit
                )
                response_time = (datetime.now() - start_time_req).total_seconds() * 1000

                if candles:
                    self._update_success_metrics(feed_name, response_time)
                    logger.info(
                        f"✅ Fallback success: {len(candles)} candles for {symbol} from {feed_name}"
                    )
                    return candles

            except Exception as e:
                await self._handle_feed_failure(feed_name, str(e))
                continue

        logger.error(f"❌ All feeds failed for historical data: {symbol}")
        return []

    def _update_success_metrics(self, feed_name: str, response_time_ms: float):
        """Update success metrics for a feed."""
        metrics = self.feed_metrics[feed_name]
        metrics.requests_total += 1
        metrics.requests_successful += 1
        metrics.last_success_time = datetime.now(timezone.utc)
        metrics.consecutive_failures = 0
        self._request_counts[feed_name] += 1
        self._update_avg_response_time(feed_name, response_time_ms)

    def _update_avg_response_time(self, feed_name: str, response_time_ms: float):
        """Update average response time using exponential moving average."""
        metrics = self.feed_metrics[feed_name]
        alpha = 0.2  # Smoothing factor

        if metrics.avg_response_time_ms == 0:
            metrics.avg_response_time_ms = response_time_ms
        else:
            metrics.avg_response_time_ms = (
                alpha * response_time_ms + (1 - alpha) * metrics.avg_response_time_ms
            )

    async def _start_monitoring(self):
        """Start monitoring tasks."""
        self._is_running = True

        self._monitoring_task = asyncio.create_task(self._health_monitor())
        self._metrics_task = asyncio.create_task(self._metrics_reporter())

        logger.info("🔍 Started data feed monitoring")

    async def _health_monitor(self):
        """Background health monitoring for all feeds."""
        while self._is_running:
            try:
                await asyncio.sleep(self.health_check_interval)

                if not self._is_running:
                    break

                # Health check all feeds
                for feed_name, feed in self.feeds.items():
                    if feed_name in self.active_feeds:
                        try:
                            is_healthy = await feed._perform_health_check()
                            if not is_healthy:
                                logger.warning(f"⚠️ Health check failed for {feed_name}")
                                await self._handle_feed_failure(
                                    feed_name, "Health check failed"
                                )
                        except Exception as e:
                            await self._handle_feed_failure(
                                feed_name, f"Health check error: {e}"
                            )

                    elif feed_name in self.failed_feeds:
                        # Try to reconnect failed feeds
                        try:
                            logger.info(f"🔄 Attempting to reconnect {feed_name}")
                            success = await self._connect_feed_with_metrics(
                                feed_name, feed
                            )
                            if success:
                                logger.info(f"✅ Successfully reconnected {feed_name}")
                        except Exception as e:
                            logger.debug(f"❌ Reconnection failed for {feed_name}: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Health monitor error: {e}")

    async def _metrics_reporter(self):
        """Background metrics reporting."""
        while self._is_running:
            try:
                await asyncio.sleep(self.metrics_interval)

                if not self._is_running:
                    break

                logger.info("📊 Data Feed Performance Metrics:")
                for feed_name, metrics in self.feed_metrics.items():
                    uptime = self._calculate_uptime(metrics)
                    metrics.uptime_percent = uptime

                    status = "🟢" if feed_name in self.active_feeds else "🔴"
                    logger.info(
                        f"  {status} {feed_name}: "
                        f"{metrics.requests_successful}/{metrics.requests_total} "
                        f"({uptime:.1f}% uptime, {metrics.avg_response_time_ms:.1f}ms avg)"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Metrics reporter error: {e}")

    def _calculate_uptime(self, metrics: FeedMetrics) -> float:
        """Calculate uptime percentage for a feed."""
        if metrics.requests_total == 0:
            return 100.0

        return (metrics.requests_successful / metrics.requests_total) * 100.0

    async def shutdown(self):
        """Gracefully shutdown the data feed manager."""
        logger.info("🛑 Shutting down Data Feed Manager...")

        self._is_running = False

        # Cancel monitoring tasks
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass

        # Disconnect all feeds
        disconnect_tasks = []
        for feed_name, feed in self.feeds.items():
            task = asyncio.create_task(feed.disconnect())
            disconnect_tasks.append(task)

        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)

        logger.info("✅ Data Feed Manager shutdown complete")

    def get_feed_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive statistics for all feeds."""
        stats = {}

        for feed_name, metrics in self.feed_metrics.items():
            feed_stats = {
                "name": feed_name,
                "status": "active" if feed_name in self.active_feeds else "failed",
                "total_requests": metrics.requests_total,
                "successful_requests": metrics.requests_successful,
                "failed_requests": metrics.requests_failed,
                "success_rate_percent": (
                    (metrics.requests_successful / metrics.requests_total * 100)
                    if metrics.requests_total > 0
                    else 0
                ),
                "avg_response_time_ms": round(metrics.avg_response_time_ms, 2),
                "uptime_percent": round(metrics.uptime_percent, 2),
                "consecutive_failures": metrics.consecutive_failures,
                "last_success_time": (
                    metrics.last_success_time.isoformat()
                    if metrics.last_success_time
                    else None
                ),
                "last_failure_time": (
                    metrics.last_failure_time.isoformat()
                    if metrics.last_failure_time
                    else None
                ),
                "recent_failures": len(metrics.failure_times),
            }

            # Add feed-specific stats
            if feed_name in self.feeds:
                feed_specific_stats = self.feeds[feed_name].get_statistics()
                feed_stats.update(feed_specific_stats)

            stats[feed_name] = feed_stats

        return stats

    def get_active_feeds(self) -> List[str]:
        """Get list of currently active feed names."""
        return list(self.active_feeds)

    def get_failed_feeds(self) -> List[str]:
        """Get list of currently failed feed names."""
        return list(self.failed_feeds)
