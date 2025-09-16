"""
Real-Time Market Data Handler for Live Trading Validation

Streams real-time market data from Interactive Brokers TWS API for paper trading validation.
Ensures data quality, handles connection failures, and provides SLA-compliant data delivery.

Key Requirements:
- Stream live GBP/USD market data from IB TWS
- Handle >1000 price updates per second during active sessions
- Maintain data quality and detect stale/missing data
- Provide <10 second data delivery SLA
- Support graceful reconnection on failures
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from ..brokers.adapters.ib_adapter import IBBrokerAdapter
from ..data_engineering.timescaledb import TimescaleDBManager


class MarketDataStatus(Enum):
    """Market data connection status"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    STALE = "stale"
    ERROR = "error"


@dataclass
class MarketDataTick:
    """Individual market data tick"""

    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    last: float
    last_size: float
    volume: float
    spread: float = field(init=False)
    mid: float = field(init=False)

    def __post_init__(self):
        self.spread = self.ask - self.bid if self.ask and self.bid else 0.0
        self.mid = (self.bid + self.ask) / 2 if self.ask and self.bid else self.last

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/logging"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "bid": self.bid,
            "ask": self.ask,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "last": self.last,
            "last_size": self.last_size,
            "volume": self.volume,
            "spread": self.spread,
            "mid": self.mid,
        }


@dataclass
class MarketDataMetrics:
    """Real-time market data quality metrics"""

    connection_start: datetime = field(default_factory=datetime.utcnow)
    total_ticks_received: int = 0
    valid_ticks: int = 0
    invalid_ticks: int = 0
    stale_data_events: int = 0
    connection_failures: int = 0

    # Latency metrics (milliseconds)
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0

    # Data quality metrics
    avg_spread_bps: float = 0.0
    min_spread_bps: float = float("inf")
    max_spread_bps: float = 0.0

    # Throughput metrics
    ticks_per_second: float = 0.0
    peak_ticks_per_second: float = 0.0
    data_gaps: int = 0

    # SLA compliance
    sla_violations: int = 0  # Data delivery >10s
    uptime_percentage: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for monitoring"""
        return {
            "connection_start": self.connection_start.isoformat(),
            "total_ticks_received": self.total_ticks_received,
            "valid_ticks": self.valid_ticks,
            "invalid_ticks": self.invalid_ticks,
            "stale_data_events": self.stale_data_events,
            "connection_failures": self.connection_failures,
            "avg_latency_ms": self.avg_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "avg_spread_bps": self.avg_spread_bps,
            "ticks_per_second": self.ticks_per_second,
            "peak_ticks_per_second": self.peak_ticks_per_second,
            "sla_violations": self.sla_violations,
            "uptime_percentage": self.uptime_percentage,
        }


class RealTimeMarketDataHandler:
    """
    Handles real-time market data streaming from Interactive Brokers for live trading validation.

    Provides high-quality, low-latency market data with comprehensive monitoring and
    automatic failover capabilities for the paper trading validation system.
    """

    def __init__(
        self,
        symbol: str = "GBPUSD",
        timeout_seconds: int = 10,
        max_reconnect_attempts: int = 5,
        stale_data_threshold_seconds: int = 30,
    ):
        self.symbol = symbol
        self.timeout_seconds = timeout_seconds
        self.max_reconnect_attempts = max_reconnect_attempts
        self.stale_data_threshold = stale_data_threshold_seconds

        # Connection and status
        self.status = MarketDataStatus.DISCONNECTED
        self.ib_adapter: Optional[IBBrokerAdapter] = None
        self.db_manager: Optional[TimescaleDBManager] = None

        # Data storage and processing
        self.current_tick: Optional[MarketDataTick] = None
        self.tick_buffer = deque(maxlen=1000)  # Keep last 1000 ticks
        self.latency_buffer = deque(maxlen=100)  # Track last 100 latencies

        # Metrics and monitoring
        self.metrics = MarketDataMetrics()
        self.last_data_time: Optional[datetime] = None
        self.reconnect_count = 0

        # Event handlers
        self.data_callbacks: List[Callable[[MarketDataTick], None]] = []
        self.status_callbacks: List[Callable[[MarketDataStatus], None]] = []

        # Control flags
        self.is_streaming = False
        self.should_reconnect = True

        self.logger = logging.getLogger(__name__)

    async def initialize(self) -> bool:
        """Initialize market data connection"""
        try:
            self.logger.info(f"Initializing real-time market data for {self.symbol}...")

            # Initialize database connection
            self.db_manager = TimescaleDBManager()
            await self.db_manager.initialize()

            # Initialize Interactive Brokers adapter
            self.ib_adapter = IBBrokerAdapter(
                paper_trading=True,  # Always use paper trading for validation
                connection_timeout=self.timeout_seconds,
            )

            # Connect to IB TWS
            success = await self._connect_to_ib()
            if not success:
                return False

            # Start market data streaming
            await self._start_market_data_subscription()

            self.logger.info(f"✅ Real-time market data initialized for {self.symbol}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize market data: {e}")
            self.status = MarketDataStatus.ERROR
            return False

    async def _connect_to_ib(self) -> bool:
        """Connect to Interactive Brokers TWS"""
        try:
            self.status = MarketDataStatus.CONNECTING
            self._notify_status_change()

            # Connect to IB TWS (paper trading)
            success = await self.ib_adapter.connect()
            if not success:
                self.logger.error("Failed to connect to Interactive Brokers TWS")
                self.status = MarketDataStatus.ERROR
                return False

            # Verify connection
            if not await self.ib_adapter.is_connected():
                self.logger.error("IB TWS connection verification failed")
                self.status = MarketDataStatus.ERROR
                return False

            self.status = MarketDataStatus.CONNECTED
            self.metrics.connection_start = datetime.utcnow()
            self._notify_status_change()

            self.logger.info("✅ Connected to Interactive Brokers TWS (Paper Trading)")
            return True

        except Exception as e:
            self.logger.error(f"Error connecting to IB TWS: {e}")
            self.status = MarketDataStatus.ERROR
            self.metrics.connection_failures += 1
            return False

    async def _start_market_data_subscription(self):
        """Start real-time market data subscription"""
        try:
            self.logger.info(f"Starting market data subscription for {self.symbol}...")

            # Subscribe to real-time market data
            success = await self.ib_adapter.subscribe_market_data(
                symbol=self.symbol, callback=self._handle_market_data_update
            )

            if not success:
                raise Exception("Failed to subscribe to market data")

            self.status = MarketDataStatus.STREAMING
            self.is_streaming = True
            self._notify_status_change()

            # Start monitoring and health check tasks
            asyncio.create_task(self._monitor_data_quality())
            asyncio.create_task(self._health_check_loop())

            self.logger.info(f"✅ Market data streaming started for {self.symbol}")

        except Exception as e:
            self.logger.error(f"Error starting market data subscription: {e}")
            self.status = MarketDataStatus.ERROR
            raise

    async def _handle_market_data_update(self, data: Dict[str, Any]):
        """Handle incoming market data updates from IB"""
        try:
            receive_time = datetime.utcnow()

            # Parse IB market data format
            tick = MarketDataTick(
                symbol=data.get("symbol", self.symbol),
                timestamp=data.get("timestamp", receive_time),
                bid=float(data.get("bid", 0)),
                ask=float(data.get("ask", 0)),
                bid_size=float(data.get("bid_size", 0)),
                ask_size=float(data.get("ask_size", 0)),
                last=float(data.get("last", 0)),
                last_size=float(data.get("last_size", 0)),
                volume=float(data.get("volume", 0)),
            )

            # Calculate latency
            if "exchange_timestamp" in data:
                exchange_time = data["exchange_timestamp"]
                latency_ms = (receive_time - exchange_time).total_seconds() * 1000
                self._update_latency_metrics(latency_ms)

            # Data quality validation
            if self._validate_tick_data(tick):
                self.current_tick = tick
                self.tick_buffer.append(tick)
                self.last_data_time = receive_time
                self.metrics.valid_ticks += 1

                # Update spread metrics
                self._update_spread_metrics(tick)

                # Notify callbacks
                for callback in self.data_callbacks:
                    try:
                        await callback(tick)
                    except Exception as e:
                        self.logger.warning(f"Error in data callback: {e}")
            else:
                self.metrics.invalid_ticks += 1
                self.logger.warning(f"Invalid tick data received: {tick.to_dict()}")

            self.metrics.total_ticks_received += 1

            # Store in database (batch processing)
            if self.metrics.total_ticks_received % 100 == 0:  # Store every 100 ticks
                await self._store_tick_batch()

        except Exception as e:
            self.logger.error(f"Error handling market data update: {e}")
            self.metrics.invalid_ticks += 1

    def _validate_tick_data(self, tick: MarketDataTick) -> bool:
        """Validate tick data quality"""
        try:
            # Basic data validation
            if not tick.bid or not tick.ask or tick.bid <= 0 or tick.ask <= 0:
                return False

            # Spread validation (reasonable spread for GBPUSD)
            if tick.spread < 0 or tick.spread > 0.01:  # >100 pips is suspicious
                return False

            # Price validation (reasonable range for GBPUSD)
            if tick.bid < 0.8 or tick.bid > 2.0 or tick.ask < 0.8 or tick.ask > 2.0:
                return False

            # Timestamp validation (not too old)
            if tick.timestamp < datetime.utcnow() - timedelta(minutes=5):
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating tick data: {e}")
            return False

    def _update_latency_metrics(self, latency_ms: float):
        """Update latency metrics"""
        self.latency_buffer.append(latency_ms)

        # Update average latency
        if len(self.latency_buffer) > 0:
            self.metrics.avg_latency_ms = sum(self.latency_buffer) / len(
                self.latency_buffer
            )
            self.metrics.max_latency_ms = max(self.metrics.max_latency_ms, latency_ms)

            # Calculate 95th percentile
            if len(self.latency_buffer) >= 20:
                self.metrics.p95_latency_ms = np.percentile(
                    list(self.latency_buffer), 95
                )

    def _update_spread_metrics(self, tick: MarketDataTick):
        """Update spread metrics"""
        spread_bps = tick.spread * 10000  # Convert to basis points

        # Update spread statistics
        if self.metrics.valid_ticks == 1:
            self.metrics.avg_spread_bps = spread_bps
        else:
            # Running average
            self.metrics.avg_spread_bps = (
                self.metrics.avg_spread_bps * (self.metrics.valid_ticks - 1)
                + spread_bps
            ) / self.metrics.valid_ticks

        self.metrics.min_spread_bps = min(self.metrics.min_spread_bps, spread_bps)
        self.metrics.max_spread_bps = max(self.metrics.max_spread_bps, spread_bps)

    async def _monitor_data_quality(self):
        """Monitor data quality and detect issues"""
        while self.is_streaming:
            try:
                await asyncio.sleep(60)  # Check every minute

                current_time = datetime.utcnow()

                # Check for stale data
                if self.last_data_time:
                    stale_duration = (
                        current_time - self.last_data_time
                    ).total_seconds()
                    if stale_duration > self.stale_data_threshold:
                        self.metrics.stale_data_events += 1
                        self.logger.warning(
                            f"⚠️ Stale market data detected: {stale_duration:.1f}s since last update"
                        )

                        if stale_duration > self.timeout_seconds:
                            self.metrics.sla_violations += 1
                            self.logger.error(
                                f"❌ Market data SLA violation: {stale_duration:.1f}s > {self.timeout_seconds}s"
                            )

                # Calculate throughput metrics
                if len(self.tick_buffer) >= 60:
                    recent_ticks = [
                        tick
                        for tick in self.tick_buffer
                        if tick.timestamp > current_time - timedelta(seconds=60)
                    ]
                    self.metrics.ticks_per_second = len(recent_ticks) / 60.0
                    self.metrics.peak_ticks_per_second = max(
                        self.metrics.peak_ticks_per_second,
                        self.metrics.ticks_per_second,
                    )

                # Update uptime percentage
                if self.metrics.connection_start:
                    total_time = (
                        current_time - self.metrics.connection_start
                    ).total_seconds()
                    downtime = (
                        self.metrics.connection_failures * 30
                    )  # Assume 30s per failure
                    self.metrics.uptime_percentage = max(
                        0, (total_time - downtime) / total_time * 100
                    )

                # Log periodic quality report
                if (
                    self.metrics.total_ticks_received > 0
                    and self.metrics.total_ticks_received % 1000 == 0
                ):
                    self.logger.info(
                        f"📊 Market Data Quality: "
                        f"{self.metrics.valid_ticks}/{self.metrics.total_ticks_received} valid ticks, "
                        f"{self.metrics.avg_latency_ms:.1f}ms avg latency, "
                        f"{self.metrics.avg_spread_bps:.1f} bps avg spread"
                    )

            except Exception as e:
                self.logger.error(f"Error in data quality monitoring: {e}")

    async def _health_check_loop(self):
        """Continuous health check and auto-recovery"""
        while self.should_reconnect:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                if not await self.health_check():
                    self.logger.warning("Health check failed - attempting reconnection")
                    await self._attempt_reconnection()

            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")

    async def health_check(self) -> bool:
        """Perform comprehensive health check"""
        try:
            # Check IB connection
            if not self.ib_adapter or not await self.ib_adapter.is_connected():
                return False

            # Check data freshness
            if self.last_data_time:
                stale_duration = (
                    datetime.utcnow() - self.last_data_time
                ).total_seconds()
                if stale_duration > self.stale_data_threshold:
                    return False

            # Check recent data quality
            if self.metrics.total_ticks_received > 100:
                recent_invalid_rate = (
                    self.metrics.invalid_ticks / self.metrics.total_ticks_received
                )
                if recent_invalid_rate > 0.1:  # >10% invalid data
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
            return False

    async def _attempt_reconnection(self):
        """Attempt to reconnect to market data"""
        if self.reconnect_count >= self.max_reconnect_attempts:
            self.logger.error(
                f"❌ Max reconnection attempts ({self.max_reconnect_attempts}) reached"
            )
            self.status = MarketDataStatus.ERROR
            return

        try:
            self.logger.info(f"🔄 Attempting reconnection #{self.reconnect_count + 1}")
            self.reconnect_count += 1

            # Cleanup existing connection
            if self.ib_adapter:
                await self.ib_adapter.disconnect()

            # Wait before reconnecting
            await asyncio.sleep(
                min(self.reconnect_count * 5, 30)
            )  # Exponential backoff

            # Reconnect
            success = await self._connect_to_ib()
            if success:
                await self._start_market_data_subscription()
                self.reconnect_count = 0  # Reset on successful connection
                self.logger.info("✅ Reconnection successful")

        except Exception as e:
            self.logger.error(f"Error during reconnection attempt: {e}")
            self.metrics.connection_failures += 1

    async def get_latest_data(self) -> Optional[Dict[str, Any]]:
        """Get the latest market data for trading decisions"""
        if not self.current_tick:
            return None

        # Check data freshness
        if self.last_data_time:
            age_seconds = (datetime.utcnow() - self.last_data_time).total_seconds()
            if age_seconds > self.timeout_seconds:
                self.logger.warning(f"Market data is stale: {age_seconds:.1f}s old")
                return None

        return {
            "symbol": self.current_tick.symbol,
            "timestamp": self.current_tick.timestamp,
            "bid": self.current_tick.bid,
            "ask": self.current_tick.ask,
            "mid": self.current_tick.mid,
            "spread": self.current_tick.spread,
            "last": self.current_tick.last,
            "volume": self.current_tick.volume,
            "data_age_seconds": (
                datetime.utcnow() - self.current_tick.timestamp
            ).total_seconds(),
        }

    async def get_current_prices(self) -> Dict[str, float]:
        """Get current prices for position valuation"""
        if not self.current_tick:
            return {}

        return {self.symbol: self.current_tick.mid}

    async def get_historical_data(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Get historical tick data from buffer or database"""
        end_time = end_time or datetime.utcnow()

        # First try from buffer (recent data)
        recent_ticks = [
            tick
            for tick in self.tick_buffer
            if start_time <= tick.timestamp <= end_time
        ]

        if len(recent_ticks) >= limit:
            # Sufficient data in buffer
            data = [tick.to_dict() for tick in recent_ticks[-limit:]]
        else:
            # Need to fetch from database
            if self.db_manager:
                data = await self.db_manager.get_market_data(
                    symbol=self.symbol,
                    start_time=start_time,
                    end_time=end_time,
                    limit=limit,
                )
            else:
                data = [tick.to_dict() for tick in recent_ticks]

        return pd.DataFrame(data) if data else pd.DataFrame()

    async def _store_tick_batch(self):
        """Store batch of ticks to database"""
        if not self.db_manager or len(self.tick_buffer) == 0:
            return

        try:
            # Get recent ticks not yet stored
            recent_ticks = list(self.tick_buffer)[-100:]  # Store last 100 ticks
            tick_data = [tick.to_dict() for tick in recent_ticks]

            await self.db_manager.store_market_data_batch(tick_data)

        except Exception as e:
            self.logger.error(f"Error storing tick batch: {e}")

    def add_data_callback(self, callback: Callable[[MarketDataTick], None]):
        """Add callback for market data updates"""
        self.data_callbacks.append(callback)

    def add_status_callback(self, callback: Callable[[MarketDataStatus], None]):
        """Add callback for status changes"""
        self.status_callbacks.append(callback)

    def _notify_status_change(self):
        """Notify all status callbacks"""
        for callback in self.status_callbacks:
            try:
                callback(self.status)
            except Exception as e:
                self.logger.warning(f"Error in status callback: {e}")

    async def get_data_quality_report(self) -> Dict[str, Any]:
        """Get comprehensive data quality report"""
        return {
            "status": self.status.value,
            "symbol": self.symbol,
            "connection_uptime_hours": (
                (datetime.utcnow() - self.metrics.connection_start).total_seconds()
                / 3600
                if self.metrics.connection_start
                else 0
            ),
            "metrics": self.metrics.to_dict(),
            "current_tick": self.current_tick.to_dict() if self.current_tick else None,
            "buffer_size": len(self.tick_buffer),
            "is_streaming": self.is_streaming,
            "health_status": "healthy" if await self.health_check() else "unhealthy",
        }

    async def cleanup(self):
        """Cleanup resources and connections"""
        try:
            self.logger.info("Cleaning up market data handler...")
            self.is_streaming = False
            self.should_reconnect = False

            # Store final batch
            if len(self.tick_buffer) > 0:
                await self._store_tick_batch()

            # Disconnect from IB
            if self.ib_adapter:
                await self.ib_adapter.unsubscribe_market_data(self.symbol)
                await self.ib_adapter.disconnect()

            # Cleanup database
            if self.db_manager:
                await self.db_manager.cleanup()

            self.status = MarketDataStatus.DISCONNECTED
            self.logger.info("✅ Market data handler cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during market data cleanup: {e}")
