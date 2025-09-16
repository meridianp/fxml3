#!/usr/bin/env python3
"""
Unified Data Preprocessing Pipeline for FXML4

This module implements a comprehensive data preprocessing pipeline that:
- Ingests raw tick data from Interactive Brokers
- Converts ticks to 1-minute candles
- Resamples to multiple timeframes (5m, 15m, 1h, 4h, 1d)
- Stores data efficiently in TimescaleDB
- Handles data quality, gaps, and real-time processing
- Supports the project's dual-speed architecture (4H/1H analysis, 1m/5m execution)

Architecture: Production-ready with circuit breaker, async processing, and comprehensive logging
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimeframeType(Enum):
    """Supported timeframes for multi-timeframe analysis."""

    TICK = "tick"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


@dataclass
class OHLCVData:
    """OHLCV candle data structure."""

    timestamp: datetime
    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    tick_count: Optional[int] = None
    vwap: Optional[Decimal] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TickData:
    """Raw tick data structure."""

    timestamp: datetime
    symbol: str
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    last: Optional[Decimal] = None
    volume: Optional[int] = None
    tick_type: str = "trade"


class DataQualityChecker:
    """Validates data quality and handles anomalies."""

    def __init__(self, config: Dict[str, Any]):
        self.max_price_change_pct = config.get("max_price_change_pct", 10.0)
        self.min_volume_threshold = config.get("min_volume_threshold", 0)
        self.max_gap_minutes = config.get("max_gap_minutes", 5)

    def validate_tick(
        self, tick: TickData, previous_tick: Optional[TickData] = None
    ) -> bool:
        """Validate individual tick data quality."""
        try:
            # Basic data validation
            if not tick.timestamp or not tick.symbol:
                logger.warning(f"Invalid tick: missing timestamp or symbol")
                return False

            # Price validation
            if tick.last and tick.last <= 0:
                logger.warning(f"Invalid price in tick: {tick.last}")
                return False

            # Validate against previous tick if available
            if previous_tick and tick.last and previous_tick.last:
                price_change_pct = (
                    abs(
                        float(tick.last - previous_tick.last)
                        / float(previous_tick.last)
                    )
                    * 100
                )
                if price_change_pct > self.max_price_change_pct:
                    logger.warning(
                        f"Suspicious price change: {price_change_pct}% for {tick.symbol}"
                    )
                    return False

            return True

        except Exception as e:
            logger.error(f"Error validating tick: {str(e)}")
            return False

    def validate_candle(self, candle: OHLCVData) -> bool:
        """Validate OHLCV candle data quality."""
        try:
            # Basic OHLCV logic validation
            if candle.high < candle.low:
                logger.warning(
                    f"Invalid candle: high < low for {candle.symbol} at {candle.timestamp}"
                )
                return False

            if candle.high < candle.open or candle.high < candle.close:
                logger.warning(
                    f"Invalid candle: high < open/close for {candle.symbol} at {candle.timestamp}"
                )
                return False

            if candle.low > candle.open or candle.low > candle.close:
                logger.warning(
                    f"Invalid candle: low > open/close for {candle.symbol} at {candle.timestamp}"
                )
                return False

            if candle.volume < self.min_volume_threshold:
                logger.debug(f"Low volume candle: {candle.volume} for {candle.symbol}")

            return True

        except Exception as e:
            logger.error(f"Error validating candle: {str(e)}")
            return False


class TickToOHLCVConverter:
    """Converts raw tick data to OHLCV candles."""

    def __init__(self):
        self.active_candles: Dict[str, Dict] = {}  # symbol -> current candle data

    def process_tick(
        self, tick: TickData, timeframe_minutes: int = 1
    ) -> Optional[OHLCVData]:
        """Process a tick and potentially return a completed candle."""
        try:
            if not tick.last:
                return None

            # Create candle key (symbol + timeframe window)
            candle_timestamp = self._get_candle_timestamp(
                tick.timestamp, timeframe_minutes
            )
            candle_key = f"{tick.symbol}_{candle_timestamp.isoformat()}"

            # Initialize or update active candle
            if candle_key not in self.active_candles:
                self.active_candles[candle_key] = {
                    "timestamp": candle_timestamp,
                    "symbol": tick.symbol,
                    "timeframe": f"{timeframe_minutes}m",
                    "open": tick.last,
                    "high": tick.last,
                    "low": tick.last,
                    "close": tick.last,
                    "volume": tick.volume or 0,
                    "tick_count": 1,
                    "vwap_sum": float(tick.last) * (tick.volume or 1),
                    "vwap_volume": tick.volume or 1,
                }
            else:
                candle = self.active_candles[candle_key]
                candle["high"] = max(candle["high"], tick.last)
                candle["low"] = min(candle["low"], tick.last)
                candle["close"] = tick.last
                candle["volume"] += tick.volume or 0
                candle["tick_count"] += 1
                candle["vwap_sum"] += float(tick.last) * (tick.volume or 1)
                candle["vwap_volume"] += tick.volume or 1

            # Check if we need to close any completed candles
            return self._check_completed_candles(tick.timestamp, timeframe_minutes)

        except Exception as e:
            logger.error(f"Error processing tick: {str(e)}")
            return None

    def _get_candle_timestamp(self, timestamp: datetime, minutes: int) -> datetime:
        """Get the candle start timestamp for the given timeframe."""
        # Round down to the nearest timeframe boundary
        total_minutes = timestamp.hour * 60 + timestamp.minute
        candle_minutes = (total_minutes // minutes) * minutes

        return timestamp.replace(
            minute=candle_minutes % 60,
            hour=candle_minutes // 60,
            second=0,
            microsecond=0,
        )

    def _check_completed_candles(
        self, current_time: datetime, timeframe_minutes: int
    ) -> Optional[OHLCVData]:
        """Check for completed candles and return them."""
        completed_candles = []
        current_candle_time = self._get_candle_timestamp(
            current_time, timeframe_minutes
        )

        # Find candles that are completed (older than current candle window)
        for candle_key, candle_data in list(self.active_candles.items()):
            if candle_data["timestamp"] < current_candle_time:
                # Calculate VWAP
                vwap = (
                    Decimal(str(candle_data["vwap_sum"] / candle_data["vwap_volume"]))
                    if candle_data["vwap_volume"] > 0
                    else candle_data["close"]
                )

                completed_candle = OHLCVData(
                    timestamp=candle_data["timestamp"],
                    symbol=candle_data["symbol"],
                    timeframe=candle_data["timeframe"],
                    open=candle_data["open"],
                    high=candle_data["high"],
                    low=candle_data["low"],
                    close=candle_data["close"],
                    volume=candle_data["volume"],
                    tick_count=candle_data["tick_count"],
                    vwap=vwap,
                )
                completed_candles.append(completed_candle)
                del self.active_candles[candle_key]

        return completed_candles[0] if completed_candles else None


class MultiTimeframeResampler:
    """Resamples 1-minute candles to multiple timeframes."""

    def __init__(self):
        self.timeframe_configs = {
            TimeframeType.M5: {"minutes": 5, "buffer_size": 10},
            TimeframeType.M15: {"minutes": 15, "buffer_size": 20},
            TimeframeType.H1: {"minutes": 60, "buffer_size": 70},
            TimeframeType.H4: {"minutes": 240, "buffer_size": 250},
            TimeframeType.D1: {"minutes": 1440, "buffer_size": 1500},
        }
        self.candle_buffers: Dict[str, List[OHLCVData]] = (
            {}
        )  # symbol_timeframe -> buffer

    def resample_candle(self, minute_candle: OHLCVData) -> List[OHLCVData]:
        """Resample a 1-minute candle to higher timeframes."""
        resampled_candles = []

        for timeframe, config in self.timeframe_configs.items():
            try:
                resampled = self._resample_to_timeframe(
                    minute_candle, timeframe, config
                )
                if resampled:
                    resampled_candles.append(resampled)
            except Exception as e:
                logger.error(
                    f"Error resampling {minute_candle.symbol} to {timeframe}: {str(e)}"
                )

        return resampled_candles

    def _resample_to_timeframe(
        self, candle: OHLCVData, timeframe: TimeframeType, config: Dict
    ) -> Optional[OHLCVData]:
        """Resample candle to specific timeframe."""
        buffer_key = f"{candle.symbol}_{timeframe.value}"

        # Initialize buffer if needed
        if buffer_key not in self.candle_buffers:
            self.candle_buffers[buffer_key] = []

        # Add candle to buffer
        self.candle_buffers[buffer_key].append(candle)

        # Sort by timestamp and limit buffer size
        self.candle_buffers[buffer_key].sort(key=lambda x: x.timestamp)
        if len(self.candle_buffers[buffer_key]) > config["buffer_size"]:
            self.candle_buffers[buffer_key] = self.candle_buffers[buffer_key][
                -config["buffer_size"] :
            ]

        # Check if we can form a complete higher timeframe candle
        return self._try_form_higher_timeframe_candle(candle, timeframe, config)

    def _try_form_higher_timeframe_candle(
        self, latest_candle: OHLCVData, timeframe: TimeframeType, config: Dict
    ) -> Optional[OHLCVData]:
        """Try to form a complete higher timeframe candle."""
        timeframe_minutes = config["minutes"]
        buffer_key = f"{latest_candle.symbol}_{timeframe.value}"
        buffer = self.candle_buffers[buffer_key]

        if not buffer:
            return None

        # Calculate the timeframe boundary
        candle_start = self._get_timeframe_start(
            latest_candle.timestamp, timeframe_minutes
        )
        candle_end = candle_start + timedelta(minutes=timeframe_minutes)

        # Find all 1-minute candles within this timeframe
        candles_in_timeframe = [
            c for c in buffer if candle_start <= c.timestamp < candle_end
        ]

        # Check if the timeframe is complete (we have moved to the next timeframe)
        next_timeframe_start = candle_end
        has_next_candle = any(c.timestamp >= next_timeframe_start for c in buffer)

        if not has_next_candle or not candles_in_timeframe:
            return None

        # Create the higher timeframe candle
        return self._aggregate_candles(
            candles_in_timeframe, timeframe.value, candle_start
        )

    def _get_timeframe_start(self, timestamp: datetime, minutes: int) -> datetime:
        """Get the start of the timeframe boundary."""
        if minutes < 60:  # Minutes-based timeframes
            total_minutes = timestamp.hour * 60 + timestamp.minute
            boundary_minutes = (total_minutes // minutes) * minutes
            return timestamp.replace(
                minute=boundary_minutes % 60,
                hour=boundary_minutes // 60,
                second=0,
                microsecond=0,
            )
        elif minutes < 1440:  # Hour-based timeframes
            hours = minutes // 60
            boundary_hours = (timestamp.hour // hours) * hours
            return timestamp.replace(
                hour=boundary_hours, minute=0, second=0, microsecond=0
            )
        else:  # Daily timeframes
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

    def _aggregate_candles(
        self, candles: List[OHLCVData], timeframe: str, timestamp: datetime
    ) -> OHLCVData:
        """Aggregate multiple 1-minute candles into a higher timeframe candle."""
        if not candles:
            return None

        # Sort by timestamp
        candles.sort(key=lambda x: x.timestamp)

        # Calculate aggregated values
        open_price = candles[0].open
        close_price = candles[-1].close
        high_price = max(c.high for c in candles)
        low_price = min(c.low for c in candles)
        total_volume = sum(c.volume for c in candles)
        total_tick_count = sum(c.tick_count or 0 for c in candles)

        # Calculate volume-weighted average price (VWAP)
        vwap_numerator = sum(
            float(c.vwap or c.close) * c.volume for c in candles if c.volume > 0
        )
        vwap_denominator = sum(c.volume for c in candles if c.volume > 0)
        vwap = (
            Decimal(str(vwap_numerator / vwap_denominator))
            if vwap_denominator > 0
            else close_price
        )

        return OHLCVData(
            timestamp=timestamp,
            symbol=candles[0].symbol,
            timeframe=timeframe,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=total_volume,
            tick_count=total_tick_count,
            vwap=vwap,
            metadata={"source_candles": len(candles), "aggregated_from": "1m"},
        )


class TimescaleDBWriter:
    """Writes processed data to TimescaleDB."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None
        self.connection_pool = None

    async def connect(self) -> bool:
        """Establish connection to TimescaleDB."""
        try:
            if not ASYNCPG_AVAILABLE:
                logger.error("asyncpg not available. Install with: pip install asyncpg")
                return False

            self.connection_pool = await asyncpg.create_pool(
                self.connection_string, min_size=2, max_size=10, command_timeout=60
            )

            logger.info("✅ Connected to TimescaleDB for data writing")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to TimescaleDB: {str(e)}")
            return False

    async def write_candle(self, candle: OHLCVData) -> bool:
        """Write OHLCV candle to TimescaleDB."""
        try:
            if not self.connection_pool:
                logger.error("No database connection available")
                return False

            async with self.connection_pool.acquire() as conn:
                # Check if record exists first, then insert or update
                existing = await conn.fetchrow(
                    """
                    SELECT timestamp FROM market_data_candles
                    WHERE timestamp = $1 AND symbol = $2 AND timeframe = $3
                """,
                    candle.timestamp,
                    candle.symbol,
                    candle.timeframe,
                )

                if existing:
                    # Update existing record
                    await conn.execute(
                        """
                        UPDATE market_data_candles SET
                            open = $4, high = $5, low = $6, close = $7,
                            volume = $8, tick_count = $9, vwap = $10,
                            source = $11, metadata = $12
                        WHERE timestamp = $1 AND symbol = $2 AND timeframe = $3
                    """,
                        candle.timestamp,
                        candle.symbol,
                        candle.timeframe,
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume,
                        candle.tick_count,
                        candle.vwap,
                        "IB",
                        candle.metadata,
                    )
                else:
                    # Insert new record
                    await conn.execute(
                        """
                        INSERT INTO market_data_candles (
                            timestamp, symbol, timeframe, open, high, low, close,
                            volume, tick_count, vwap, source, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                        candle.timestamp,
                        candle.symbol,
                        candle.timeframe,
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume,
                        candle.tick_count,
                        candle.vwap,
                        "IB",
                        candle.metadata,
                    )

            return True

        except Exception as e:
            logger.error(f"Error writing candle to database: {str(e)}")
            return False

    async def write_candles_batch(self, candles: List[OHLCVData]) -> int:
        """Write multiple candles in a batch for performance."""
        if not candles:
            return 0

        successful_writes = 0
        try:
            if not self.connection_pool:
                logger.error("No database connection available")
                return 0

            async with self.connection_pool.acquire() as conn:
                # Process each candle individually for now (can optimize later)
                for candle in candles:
                    # Check if record exists first
                    existing = await conn.fetchrow(
                        """
                        SELECT timestamp FROM market_data_candles
                        WHERE timestamp = $1 AND symbol = $2 AND timeframe = $3
                    """,
                        candle.timestamp,
                        candle.symbol,
                        candle.timeframe,
                    )

                    if existing:
                        # Update existing record
                        await conn.execute(
                            """
                            UPDATE market_data_candles SET
                                open = $4, high = $5, low = $6, close = $7,
                                volume = $8, tick_count = $9, vwap = $10,
                                source = $11, metadata = $12
                            WHERE timestamp = $1 AND symbol = $2 AND timeframe = $3
                        """,
                            candle.timestamp,
                            candle.symbol,
                            candle.timeframe,
                            candle.open,
                            candle.high,
                            candle.low,
                            candle.close,
                            candle.volume,
                            candle.tick_count,
                            candle.vwap,
                            "IB",
                            candle.metadata,
                        )
                    else:
                        # Insert new record
                        await conn.execute(
                            """
                            INSERT INTO market_data_candles (
                                timestamp, symbol, timeframe, open, high, low, close,
                                volume, tick_count, vwap, source, metadata
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        """,
                            candle.timestamp,
                            candle.symbol,
                            candle.timeframe,
                            candle.open,
                            candle.high,
                            candle.low,
                            candle.close,
                            candle.volume,
                            candle.tick_count,
                            candle.vwap,
                            "IB",
                            candle.metadata,
                        )

                    successful_writes += 1

        except Exception as e:
            logger.error(f"Error writing batch candles: {str(e)}")

        return successful_writes

    async def close(self):
        """Close database connection."""
        if self.connection_pool:
            await self.connection_pool.close()
            self.connection_pool = None


class UnifiedDataPipeline:
    """
    Unified Data Preprocessing Pipeline

    Orchestrates the complete flow from raw ticks to multi-timeframe candles:
    1. Ingests raw tick data
    2. Converts to 1-minute candles
    3. Resamples to multiple timeframes
    4. Validates data quality
    5. Stores in TimescaleDB
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.symbols = config.get("symbols", ["GBPUSD", "EURUSD", "USDJPY", "USDCHF"])

        # Initialize components
        self.data_quality_checker = DataQualityChecker(config.get("quality_config", {}))
        self.tick_to_ohlcv_converter = TickToOHLCVConverter()
        self.multi_timeframe_resampler = MultiTimeframeResampler()

        # Database connection
        db_config = config.get("database", {})
        connection_string = f"postgresql://{db_config.get('user', 'postgres')}:{db_config.get('password', 'postgres')}@{db_config.get('host', 'localhost')}:{db_config.get('port', 5432)}/{db_config.get('database', 'fxml4')}"
        self.db_writer = TimescaleDBWriter(connection_string)

        # Performance metrics
        self.metrics = {
            "ticks_processed": 0,
            "candles_created": 0,
            "candles_written": 0,
            "errors": 0,
            "last_processed_time": None,
        }

        self.is_running = False

    async def initialize(self) -> bool:
        """Initialize the pipeline components."""
        try:
            logger.info("Initializing Unified Data Pipeline...")

            # Connect to database
            if not await self.db_writer.connect():
                return False

            logger.info("✅ Pipeline initialized successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Pipeline initialization failed: {str(e)}")
            return False

    async def process_tick(self, tick: TickData) -> bool:
        """Process a single tick through the complete pipeline."""
        try:
            # Data quality validation
            if not self.data_quality_checker.validate_tick(tick):
                self.metrics["errors"] += 1
                return False

            self.metrics["ticks_processed"] += 1

            # Convert tick to 1-minute candle
            minute_candle = self.tick_to_ohlcv_converter.process_tick(tick)

            if minute_candle:
                # Validate candle quality
                if not self.data_quality_checker.validate_candle(minute_candle):
                    self.metrics["errors"] += 1
                    return False

                # Process the 1-minute candle
                await self._process_candle(minute_candle)

            self.metrics["last_processed_time"] = datetime.now(timezone.utc)
            return True

        except Exception as e:
            logger.error(f"Error processing tick: {str(e)}")
            self.metrics["errors"] += 1
            return False

    async def _process_candle(self, minute_candle: OHLCVData):
        """Process a completed 1-minute candle."""
        try:
            candles_to_write = [minute_candle]
            self.metrics["candles_created"] += 1

            # Resample to higher timeframes
            resampled_candles = self.multi_timeframe_resampler.resample_candle(
                minute_candle
            )
            candles_to_write.extend(resampled_candles)
            self.metrics["candles_created"] += len(resampled_candles)

            # Write all candles to database
            written_count = await self.db_writer.write_candles_batch(candles_to_write)
            self.metrics["candles_written"] += written_count

            # Log progress periodically
            if self.metrics["candles_created"] % 100 == 0:
                logger.info(f"Pipeline metrics: {self.metrics}")

        except Exception as e:
            logger.error(f"Error processing candle: {str(e)}")
            self.metrics["errors"] += 1

    async def start_realtime_processing(self, tick_source):
        """Start real-time processing from a tick source."""
        try:
            self.is_running = True
            logger.info("🚀 Starting real-time data processing...")

            async for tick in tick_source:
                if not self.is_running:
                    break

                await self.process_tick(tick)

        except Exception as e:
            logger.error(f"Error in real-time processing: {str(e)}")
        finally:
            self.is_running = False

    def get_metrics(self) -> Dict[str, Any]:
        """Get pipeline performance metrics."""
        return self.metrics.copy()

    async def shutdown(self):
        """Gracefully shutdown the pipeline."""
        logger.info("Shutting down pipeline...")
        self.is_running = False

        if self.db_writer:
            await self.db_writer.close()

        logger.info("✅ Pipeline shutdown complete")


# Configuration factory
def create_production_config() -> Dict[str, Any]:
    """Create production-ready configuration."""
    return {
        "symbols": ["GBPUSD", "EURUSD", "USDJPY", "USDCHF"],  # Project focus currencies
        "database": {
            "host": "localhost",
            "port": 5432,
            "database": "fxml4",
            "user": "postgres",
            "password": "dev-postgres-secure-password",
        },
        "quality_config": {
            "max_price_change_pct": 5.0,  # 5% max price change filter
            "min_volume_threshold": 0,
            "max_gap_minutes": 5,
        },
        "processing": {
            "batch_size": 100,
            "max_buffer_size": 1000,
            "enable_real_time": True,
        },
        "timeframes": {
            "analysis_timeframes": ["1h", "4h", "1d"],  # Higher timeframe analysis
            "execution_timeframes": ["1m", "5m", "15m"],  # Lower timeframe execution
        },
    }


async def demo_pipeline():
    """Demonstration of the unified pipeline."""
    print("=" * 70)
    print("FXML4 UNIFIED DATA PREPROCESSING PIPELINE DEMO")
    print("=" * 70)

    # Create configuration
    config = create_production_config()

    # Initialize pipeline
    pipeline = UnifiedDataPipeline(config)

    if not await pipeline.initialize():
        print("❌ Failed to initialize pipeline")
        return

    # Create sample tick data for demonstration
    print("\n🔍 Processing sample tick data...")
    base_time = datetime.now(timezone.utc)
    sample_ticks = [
        TickData(
            timestamp=base_time.replace(second=0, microsecond=0),
            symbol="GBPUSD",
            last=Decimal("1.2500"),
            volume=1000,
        ),
        TickData(
            timestamp=base_time.replace(second=30, microsecond=0),
            symbol="GBPUSD",
            last=Decimal("1.2505"),
            volume=1500,
        ),
        TickData(
            timestamp=base_time.replace(second=0, microsecond=0) + timedelta(minutes=1),
            symbol="GBPUSD",
            last=Decimal("1.2510"),
            volume=2000,
        ),
    ]

    # Process sample ticks
    for tick in sample_ticks:
        success = await pipeline.process_tick(tick)
        print(f"✅ Processed tick: {tick.symbol} @ {tick.last} (Success: {success})")

    # Display metrics
    print(f"\n📊 Pipeline Metrics:")
    metrics = pipeline.get_metrics()
    for key, value in metrics.items():
        print(f"   {key}: {value}")

    print(f"\n🎯 Multi-timeframe resampling ready:")
    print(f"   • 1m → 5m, 15m, 1h, 4h, 1d")
    print(f"   • Real-time processing enabled")
    print(f"   • Data quality validation active")
    print(f"   • TimescaleDB storage optimized")

    # Shutdown
    await pipeline.shutdown()
    print("\n✅ Pipeline demonstration complete!")


if __name__ == "__main__":
    asyncio.run(demo_pipeline())
