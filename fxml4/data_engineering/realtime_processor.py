"""Real-time data processing system for FXML4.

This module provides a comprehensive real-time data processing system that:
- Converts IB tick data into 1-minute candles in real-time
- Supports multi-timeframe architecture (4H analysis, 1m execution)
- Integrates with TimescaleDB for storage
- Provides real-time signals to trading system
- Includes production-ready monitoring and error handling
"""

import asyncio
import logging
import queue
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

import numpy as np
import pandas as pd

from .robust_ib_client import RobustIBClient
from .tick_to_candle import TickAggregator
from .timeframe_conversion import TimeframeConverter

logger = logging.getLogger(__name__)


class ProcessorState(Enum):
    """Real-time processor state."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ProcessingMetrics:
    """Real-time processing metrics."""

    ticks_received: int = 0
    candles_generated: int = 0
    errors_count: int = 0
    start_time: Optional[datetime] = None
    last_tick_time: Optional[datetime] = None
    symbols_processed: Set[str] = field(default_factory=set)
    timeframes_active: List[str] = field(default_factory=list)
    processing_latency_ms: deque = field(default_factory=lambda: deque(maxlen=1000))

    def add_latency_measurement(self, latency_ms: float):
        """Add a latency measurement."""
        self.processing_latency_ms.append(latency_ms)

    def get_average_latency_ms(self) -> float:
        """Get average processing latency."""
        if not self.processing_latency_ms:
            return 0.0
        return sum(self.processing_latency_ms) / len(self.processing_latency_ms)


class CandleStreamHandler:
    """Handler for real-time candle streams."""

    def __init__(self):
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self.logger = logging.getLogger(__name__ + ".CandleStreamHandler")

    def register_callback(
        self, symbol: str, callback: Callable[[Dict[str, Any]], None]
    ):
        """Register a callback for new candles of a specific symbol.

        Args:
            symbol: Symbol to monitor
            callback: Function to call with new candle data
        """
        self.callbacks[symbol].append(callback)
        self.logger.info(f"Registered candle callback for {symbol}")

    def unregister_callback(self, symbol: str, callback: Callable):
        """Unregister a callback.

        Args:
            symbol: Symbol to stop monitoring
            callback: Function to remove
        """
        if symbol in self.callbacks:
            try:
                self.callbacks[symbol].remove(callback)
                self.logger.info(f"Unregistered candle callback for {symbol}")
            except ValueError:
                self.logger.warning(f"Callback not found for {symbol}")

    def notify_candle_complete(self, candle: Dict[str, Any]):
        """Notify all registered callbacks of a completed candle.

        Args:
            candle: Completed candle data
        """
        symbol = candle.get("symbol")
        if symbol and symbol in self.callbacks:
            for callback in self.callbacks[symbol]:
                try:
                    callback(candle)
                except Exception as e:
                    self.logger.error(f"Error in candle callback for {symbol}: {e}")


class RealTimeProcessor:
    """Production-ready real-time data processing system."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the real-time processor.

        Args:
            config: Configuration dictionary with:
                - symbols: List of symbols to process
                - timeframes: List of timeframes in minutes [1, 5, 15, 60, 240]
                - ib_config: Interactive Brokers configuration
                - storage_config: Database storage configuration
                - processing_threads: Number of processing threads
                - max_queue_size: Maximum tick queue size
                - candle_retention_days: Days to keep candles in memory
        """
        self.config = config
        self.state = ProcessorState.STOPPED

        # Processing configuration
        self.symbols = config.get("symbols", ["GBPUSD", "EURUSD", "USDJPY", "USDCHF"])
        self.timeframes = config.get(
            "timeframes", [1, 5, 15, 60, 240]
        )  # Architecture priorities
        self.processing_threads = config.get("processing_threads", 4)
        self.max_queue_size = config.get("max_queue_size", 10000)
        self.candle_retention_days = config.get("candle_retention_days", 7)

        # Core components
        self.ib_client: Optional[RobustIBClient] = None
        self.tick_aggregator = TickAggregator(timeframes=self.timeframes)
        self.timeframe_converter = TimeframeConverter(
            base_timeframe="1m", derived_timeframes=["5m", "15m", "1h", "4h", "1d"]
        )

        # Processing queues and threads
        self.tick_queue = queue.Queue(maxsize=self.max_queue_size)
        self.candle_queue = queue.Queue(maxsize=1000)
        self.processing_threads_list: List[threading.Thread] = []
        self.tick_processor_thread: Optional[threading.Thread] = None
        self.candle_processor_thread: Optional[threading.Thread] = None

        # Event management
        self.shutdown_event = threading.Event()
        self.candle_stream_handler = CandleStreamHandler()

        # Metrics and monitoring
        self.metrics = ProcessingMetrics()
        self.metrics.timeframes_active = [f"{tf}m" for tf in self.timeframes]

        # Storage integration
        self.storage_enabled = config.get("enable_storage", True)
        self.timescaledb_client = None

        # Symbol subscriptions tracking
        self.active_subscriptions: Set[str] = set()

        logger.info(f"Initialized RealTimeProcessor for symbols: {self.symbols}")
        logger.info(f"Timeframes: {self.timeframes} minutes")
        logger.info(f"Processing threads: {self.processing_threads}")

    def start(self) -> bool:
        """Start the real-time processing system.

        Returns:
            True if started successfully, False otherwise
        """
        if self.state != ProcessorState.STOPPED:
            logger.warning(f"Processor already in state: {self.state.value}")
            return self.state == ProcessorState.RUNNING

        logger.info("🚀 Starting FXML4 Real-Time Data Processor...")
        self.state = ProcessorState.STARTING

        try:
            # Initialize metrics
            self.metrics.start_time = datetime.now()
            self.shutdown_event.clear()

            # Initialize IB client
            if not self._initialize_ib_client():
                logger.error("❌ Failed to initialize IB client")
                self.state = ProcessorState.ERROR
                return False

            # Initialize storage if enabled
            if self.storage_enabled:
                if not self._initialize_storage():
                    logger.warning(
                        "⚠️ Storage initialization failed, continuing without storage"
                    )

            # Start processing threads
            self._start_processing_threads()

            # Subscribe to market data for all symbols
            if not self._subscribe_to_symbols():
                logger.error("❌ Failed to subscribe to symbols")
                self.state = ProcessorState.ERROR
                return False

            self.state = ProcessorState.RUNNING
            logger.info("✅ Real-Time Data Processor started successfully!")
            logger.info(
                f"📊 Processing {len(self.symbols)} symbols across {len(self.timeframes)} timeframes"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Error starting processor: {e}")
            self.state = ProcessorState.ERROR
            return False

    def stop(self):
        """Stop the real-time processing system gracefully."""
        if self.state == ProcessorState.STOPPED:
            return

        logger.info("🛑 Stopping Real-Time Data Processor...")
        self.state = ProcessorState.STOPPING

        # Signal shutdown
        self.shutdown_event.set()

        # Unsubscribe from market data
        self._unsubscribe_from_symbols()

        # Stop processing threads
        self._stop_processing_threads()

        # Force complete any pending candles
        self._force_complete_candles()

        # Disconnect IB client
        if self.ib_client:
            self.ib_client.disconnect()

        # Update state
        self.state = ProcessorState.STOPPED

        # Log final metrics
        self._log_final_metrics()

        logger.info("✅ Real-Time Data Processor stopped")

    def get_latest_candle(
        self, symbol: str, timeframe: str = "1m"
    ) -> Optional[Dict[str, Any]]:
        """Get the latest candle for a symbol.

        Args:
            symbol: Symbol to get candle for
            timeframe: Timeframe (default: "1m")

        Returns:
            Latest candle data or None
        """
        if timeframe.endswith("m"):
            tf_minutes = int(timeframe[:-1])
        elif timeframe.endswith("h"):
            tf_minutes = int(timeframe[:-1]) * 60
        else:
            tf_minutes = 1

        return self.tick_aggregator.get_latest_candle(
            symbol, tf_minutes, include_current=True
        )

    def get_candles(
        self, symbol: str, timeframe: str = "1m", limit: int = 100
    ) -> pd.DataFrame:
        """Get historical candles from the aggregator.

        Args:
            symbol: Symbol to get candles for
            timeframe: Timeframe (default: "1m")
            limit: Maximum number of candles

        Returns:
            DataFrame with candles
        """
        if timeframe.endswith("m"):
            tf_minutes = int(timeframe[:-1])
        elif timeframe.endswith("h"):
            tf_minutes = int(timeframe[:-1]) * 60
        else:
            tf_minutes = 1

        return self.tick_aggregator.get_candles(symbol, tf_minutes, limit)

    def register_candle_callback(
        self, symbol: str, callback: Callable[[Dict[str, Any]], None]
    ):
        """Register a callback for new candles.

        Args:
            symbol: Symbol to monitor
            callback: Function to call with new candle data
        """
        self.candle_stream_handler.register_callback(symbol, callback)

    def get_metrics(self) -> ProcessingMetrics:
        """Get current processing metrics.

        Returns:
            Current metrics
        """
        return self.metrics

    def get_status(self) -> Dict[str, Any]:
        """Get detailed processor status.

        Returns:
            Status dictionary
        """
        uptime = None
        if self.metrics.start_time:
            uptime = datetime.now() - self.metrics.start_time

        return {
            "state": self.state.value,
            "uptime_seconds": uptime.total_seconds() if uptime else 0,
            "symbols_active": list(self.active_subscriptions),
            "timeframes": self.metrics.timeframes_active,
            "ticks_processed": self.metrics.ticks_received,
            "candles_generated": self.metrics.candles_generated,
            "errors": self.metrics.errors_count,
            "avg_latency_ms": self.metrics.get_average_latency_ms(),
            "ib_connected": self.ib_client.is_healthy() if self.ib_client else False,
            "queue_sizes": {
                "tick_queue": self.tick_queue.qsize(),
                "candle_queue": self.candle_queue.qsize(),
            },
        }

    # Private methods

    def _initialize_ib_client(self) -> bool:
        """Initialize Interactive Brokers client."""
        try:
            ib_config = self.config.get("ib_config", {})
            ib_config.setdefault("host", "127.0.0.1")
            ib_config.setdefault("port", 7497)  # Paper trading
            ib_config.setdefault("client_id", 1)
            ib_config.setdefault("real_time_updates", True)

            self.ib_client = RobustIBClient(ib_config)

            if self.ib_client.connect():
                logger.info("✅ IB client connected successfully")
                return True
            else:
                logger.error("❌ Failed to connect IB client")
                return False

        except Exception as e:
            logger.error(f"❌ Error initializing IB client: {e}")
            return False

    def _initialize_storage(self) -> bool:
        """Initialize TimescaleDB storage."""
        try:
            from .timescaledb import TimescaleDBClient

            storage_config = self.config.get("storage_config", {})
            storage_config.setdefault("host", "localhost")
            storage_config.setdefault("port", 5433)
            storage_config.setdefault("dbname", "fxml4")

            self.timescaledb_client = TimescaleDBClient(**storage_config)

            logger.info("✅ TimescaleDB client initialized")
            return True

        except Exception as e:
            logger.error(f"❌ Error initializing storage: {e}")
            return False

    def _start_processing_threads(self):
        """Start all processing threads."""
        # Tick processing thread
        self.tick_processor_thread = threading.Thread(
            target=self._tick_processor_loop, name="TickProcessor", daemon=True
        )
        self.tick_processor_thread.start()

        # Candle processing thread
        self.candle_processor_thread = threading.Thread(
            target=self._candle_processor_loop, name="CandleProcessor", daemon=True
        )
        self.candle_processor_thread.start()

        logger.info(f"✅ Started {2} processing threads")

    def _stop_processing_threads(self):
        """Stop all processing threads."""
        # Wait for threads to finish
        threads_to_wait = []

        if self.tick_processor_thread and self.tick_processor_thread.is_alive():
            threads_to_wait.append(self.tick_processor_thread)

        if self.candle_processor_thread and self.candle_processor_thread.is_alive():
            threads_to_wait.append(self.candle_processor_thread)

        for thread in threads_to_wait:
            thread.join(timeout=5.0)

        logger.info("✅ Processing threads stopped")

    def _subscribe_to_symbols(self) -> bool:
        """Subscribe to market data for all symbols."""
        success_count = 0

        for symbol in self.symbols:
            try:
                # Convert to IB format (e.g., GBPUSD -> GBP.USD)
                ib_symbol = self._convert_to_ib_symbol(symbol)

                # Subscribe to streaming market data
                req_id = self.ib_client.subscribe_market_data(ib_symbol, snapshot=False)

                self.active_subscriptions.add(symbol)
                self.metrics.symbols_processed.add(symbol)

                success_count += 1
                logger.info(f"✅ Subscribed to {symbol} market data (reqId: {req_id})")

                # Small delay between subscriptions
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ Failed to subscribe to {symbol}: {e}")

        logger.info(
            f"📊 Successfully subscribed to {success_count}/{len(self.symbols)} symbols"
        )
        return success_count > 0

    def _unsubscribe_from_symbols(self):
        """Unsubscribe from all market data."""
        for symbol in list(self.active_subscriptions):
            try:
                ib_symbol = self._convert_to_ib_symbol(symbol)
                self.ib_client.cancel_market_data(ib_symbol)
                self.active_subscriptions.discard(symbol)
                logger.info(f"✅ Unsubscribed from {symbol}")
            except Exception as e:
                logger.error(f"❌ Error unsubscribing from {symbol}: {e}")

    def _convert_to_ib_symbol(self, symbol: str) -> str:
        """Convert symbol to IB format.

        Args:
            symbol: Symbol in FXML4 format (e.g., GBPUSD)

        Returns:
            Symbol in IB format (e.g., GBP.USD)
        """
        if "." in symbol:
            return symbol  # Already in IB format

        if len(symbol) == 6:  # GBPUSD format
            return f"{symbol[:3]}.{symbol[3:]}"

        return symbol

    def _tick_processor_loop(self):
        """Main tick processing loop."""
        logger.info("🔄 Tick processor loop started")

        while not self.shutdown_event.is_set():
            try:
                # Get ticks from IB client
                if self.ib_client and self.ib_client.is_healthy():
                    ticks = self.ib_client.app.get_ticks(max_ticks=100)

                    for tick in ticks:
                        self._process_single_tick(tick)

                    if ticks:
                        self.metrics.ticks_received += len(ticks)
                        self.metrics.last_tick_time = datetime.now()

                # Small sleep to prevent CPU spinning
                time.sleep(0.01)

            except Exception as e:
                logger.error(f"❌ Error in tick processor loop: {e}")
                self.metrics.errors_count += 1
                time.sleep(1.0)

        logger.info("🔄 Tick processor loop stopped")

    def _process_single_tick(self, tick: Dict[str, Any]):
        """Process a single tick.

        Args:
            tick: Tick data from IB client
        """
        try:
            start_time = time.time()

            # Extract tick data
            symbol = tick.get("symbol")
            price = tick.get("price")
            size = tick.get("size", 0.0)
            timestamp = tick.get("timestamp", datetime.now(timezone.utc))

            if not symbol or price is None:
                return

            # Convert IB symbol format back to FXML4 format
            fxml4_symbol = symbol.replace(".", "")

            # Process through tick aggregator
            completed_candles = self.tick_aggregator.process_tick(
                symbol=fxml4_symbol,
                timestamp=timestamp,
                price=price,
                size=size,
                store_in_db=self.storage_enabled,
            )

            # Queue completed candles for further processing
            for timeframe, candle in completed_candles.items():
                if candle:
                    candle["timeframe"] = f"{timeframe}m"
                    try:
                        self.candle_queue.put_nowait(candle)
                        self.metrics.candles_generated += 1
                    except queue.Full:
                        logger.warning("⚠️ Candle queue full, dropping candle")

            # Record processing latency
            processing_time_ms = (time.time() - start_time) * 1000
            self.metrics.add_latency_measurement(processing_time_ms)

        except Exception as e:
            logger.error(f"❌ Error processing tick: {e}")
            self.metrics.errors_count += 1

    def _candle_processor_loop(self):
        """Main candle processing loop."""
        logger.info("🔄 Candle processor loop started")

        while not self.shutdown_event.is_set():
            try:
                # Get candle from queue with timeout
                try:
                    candle = self.candle_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Process the completed candle
                self._process_completed_candle(candle)

                # Mark task as done
                self.candle_queue.task_done()

            except Exception as e:
                logger.error(f"❌ Error in candle processor loop: {e}")
                self.metrics.errors_count += 1
                time.sleep(1.0)

        logger.info("🔄 Candle processor loop stopped")

    def _process_completed_candle(self, candle: Dict[str, Any]):
        """Process a completed candle.

        Args:
            candle: Completed candle data
        """
        try:
            symbol = candle["symbol"]
            timeframe = candle.get("timeframe", "1m")

            # Update derived timeframes if this is a 1-minute candle
            if timeframe == "1m":
                self._update_derived_timeframes(candle)

            # Store in TimescaleDB if enabled
            if self.storage_enabled and self.timescaledb_client:
                self._store_candle_in_db(candle)

            # Notify callbacks
            self.candle_stream_handler.notify_candle_complete(candle)

            # Log significant candles (every 100th or higher timeframes)
            if self.metrics.candles_generated % 100 == 0 or timeframe in ["4h", "1d"]:
                logger.info(
                    f"🕯️ {symbol} {timeframe} candle: "
                    + f"O={candle['open']:.5f} H={candle['high']:.5f} "
                    + f"L={candle['low']:.5f} C={candle['close']:.5f}"
                )

        except Exception as e:
            logger.error(f"❌ Error processing completed candle: {e}")
            self.metrics.errors_count += 1

    def _update_derived_timeframes(self, one_min_candle: Dict[str, Any]):
        """Update derived timeframes from 1-minute candle.

        Args:
            one_min_candle: 1-minute candle data
        """
        try:
            symbol = one_min_candle["symbol"]

            # Convert to DataFrame
            candle_df = pd.DataFrame(
                [
                    {
                        "open": one_min_candle["open"],
                        "high": one_min_candle["high"],
                        "low": one_min_candle["low"],
                        "close": one_min_candle["close"],
                        "volume": one_min_candle["volume"],
                    }
                ],
                index=[one_min_candle["timestamp"]],
            )

            # Update timeframe converter
            self.timeframe_converter.update_data(symbol, candle_df, timeframe="1m")

        except Exception as e:
            logger.error(f"❌ Error updating derived timeframes: {e}")

    def _store_candle_in_db(self, candle: Dict[str, Any]):
        """Store candle in TimescaleDB.

        Args:
            candle: Candle data to store
        """
        try:
            if candle.get("timeframe") == "1m":  # Only store 1-minute candles directly
                self.timescaledb_client.store_candle(
                    symbol=candle["symbol"],
                    timestamp=candle["timestamp"],
                    open_price=candle["open"],
                    high_price=candle["high"],
                    low_price=candle["low"],
                    close_price=candle["close"],
                    volume=int(candle["volume"]),
                    tick_count=candle.get("tick_count", 0),
                    source="realtime_processor",
                )
        except Exception as e:
            logger.error(f"❌ Error storing candle in database: {e}")

    def _force_complete_candles(self):
        """Force completion of all pending candles."""
        try:
            logger.info("🔄 Force completing pending candles...")
            completed = self.tick_aggregator.force_complete_all_candles()

            total_completed = sum(len(candles) for candles in completed.values())
            if total_completed > 0:
                logger.info(f"✅ Force completed {total_completed} candles")

        except Exception as e:
            logger.error(f"❌ Error force completing candles: {e}")

    def _log_final_metrics(self):
        """Log final processing metrics."""
        uptime = (
            (datetime.now() - self.metrics.start_time)
            if self.metrics.start_time
            else timedelta()
        )

        logger.info("📊 Final Processing Metrics:")
        logger.info(f"   ⏱️ Uptime: {uptime}")
        logger.info(f"   📈 Ticks processed: {self.metrics.ticks_received:,}")
        logger.info(f"   🕯️ Candles generated: {self.metrics.candles_generated:,}")
        logger.info(f"   ❌ Errors: {self.metrics.errors_count}")
        logger.info(f"   📊 Symbols processed: {len(self.metrics.symbols_processed)}")
        logger.info(f"   ⚡ Avg latency: {self.metrics.get_average_latency_ms():.2f}ms")

        if self.metrics.ticks_received > 0:
            ticks_per_second = (
                self.metrics.ticks_received / uptime.total_seconds()
                if uptime.total_seconds() > 0
                else 0
            )
            logger.info(f"   🚀 Processing rate: {ticks_per_second:.1f} ticks/second")

    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.stop()
        except:
            pass
