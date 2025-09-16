"""Signal Generator Service - ML and Elliott Wave signal generation."""

import asyncio
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from elliott_wave_engine import ElliottWaveEngine
from ml_signal_engine import MLSignalEngine
from shared.config.rabbitmq_config import (
    Exchanges,
    Queues,
    RoutingKeys,
    format_routing_key,
)
from shared.utils.base_service import BaseService, ServiceConfig
from signal_combiner import SignalCombiner


class SignalGeneratorService(BaseService):
    """Signal generation service using ML and Elliott Wave analysis."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("signal-generator", config)

        # Signal engines
        self.ml_engine = MLSignalEngine()
        self.elliott_engine = ElliottWaveEngine()
        self.signal_combiner = SignalCombiner()

        # Symbol processing
        self.active_symbols: set = set()
        self.symbol_data_cache: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.last_analysis_time: Dict[str, datetime] = {}

        # Configuration
        self.analysis_interval = 60  # Analyze every minute
        self.min_data_points = 200  # Minimum data points for analysis

        # Performance tracking
        self.signals_generated = 0
        self.processing_times = []

    async def service_setup(self):
        """Set up signal generator service."""
        # Load ML models
        await self.ml_engine.load_models()

        # Initialize Elliott Wave analyzer
        await self.elliott_engine.initialize()

        # Set up RabbitMQ
        await self.setup_rabbitmq()

        # Load active symbols
        await self.load_active_symbols()

        self.logger.info(
            f"Signal generator initialized for {len(self.active_symbols)} symbols"
        )

    async def service_teardown(self):
        """Clean up resources."""
        # Save ML models if needed
        await self.ml_engine.save_models()

        # Clean up Elliott Wave resources
        await self.elliott_engine.cleanup()

    async def service_run(self):
        """Main service loop."""
        # Start processing tasks
        self.add_task(self.market_data_consumer())
        self.add_task(self.signal_generation_loop())
        self.add_task(self.model_update_loop())
        self.add_task(self.heartbeat_loop())

        # Wait for shutdown
        while self.running:
            await asyncio.sleep(1)

    async def setup_rabbitmq(self):
        """Set up RabbitMQ exchanges and queues."""
        # Declare exchanges
        await self.rabbitmq_channel.declare_exchange(
            Exchanges.MARKET_DATA, type="topic", durable=True
        )

        await self.rabbitmq_channel.declare_exchange(
            Exchanges.SIGNALS, type="topic", durable=True
        )

        # Declare queues
        await self.rabbitmq_channel.declare_queue(
            Queues.SIGNAL_GENERATION, durable=True
        )

        self.logger.info("RabbitMQ setup complete")

    async def load_active_symbols(self):
        """Load active symbols from database."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT symbol
                FROM trading.symbols
                WHERE active = true
                ORDER BY symbol
            """
            )

            self.active_symbols = {row["symbol"] for row in rows}

    async def market_data_consumer(self):
        """Consume market data updates from RabbitMQ."""
        # Subscribe to market data ready messages
        queue = await self.rabbitmq_channel.get_queue(Queues.SIGNAL_GENERATION)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        data = json.loads(message.body.decode())
                        await self.process_market_data_update(data)

                    except Exception as e:
                        self.logger.error(f"Error processing market data: {e}")
                        await self.log_error(e, {"message": str(message.body)})

    async def process_market_data_update(self, data: Dict[str, Any]):
        """Process incoming market data update.

        Args:
            data: Market data update from data collector
        """
        symbol = data.get("symbol")
        timeframe = data.get("timeframe")

        if not symbol or not timeframe:
            return

        # Cache the data update
        if symbol not in self.symbol_data_cache:
            self.symbol_data_cache[symbol] = {}

        # Store indicators and market data
        market_data = data.get("data")
        indicators = data.get("indicators")

        if market_data and indicators:
            # Update cache with latest data point
            await self.update_symbol_cache(symbol, timeframe, market_data, indicators)

            # Trigger analysis if it's 4H data (our primary analysis timeframe)
            if timeframe == "4H":
                await self.trigger_signal_analysis(symbol)

    async def update_symbol_cache(
        self,
        symbol: str,
        timeframe: str,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any],
    ):
        """Update symbol data cache with new data point."""
        # Get recent data from database for complete dataset
        async with self.db_pool.acquire() as conn:
            # Get market data
            market_rows = await conn.fetch(
                f"""
                SELECT bucket as time, open, high, low, close, volume
                FROM trading.market_data_{timeframe.lower()}
                WHERE symbol = $1
                ORDER BY bucket DESC
                LIMIT 500
            """,
                symbol,
            )

            # Get indicators
            indicator_rows = await conn.fetch(
                """
                SELECT time, rsi_14, atr_14, sma_20, sma_50, sma_200,
                       ema_9, ema_21, bb_upper, bb_middle, bb_lower,
                       macd_line, macd_signal, macd_histogram,
                       adx, plus_di, minus_di, stoch_k, stoch_d
                FROM trading.indicators
                WHERE symbol = $1 AND timeframe = $2
                ORDER BY time DESC
                LIMIT 500
            """,
                symbol,
                timeframe,
            )

            if market_rows and indicator_rows:
                # Convert to DataFrames
                market_df = pd.DataFrame([dict(row) for row in market_rows])
                indicator_df = pd.DataFrame([dict(row) for row in indicator_rows])

                # Sort by time
                market_df = market_df.sort_values("time")
                indicator_df = indicator_df.sort_values("time")

                # Set time as index
                market_df.set_index("time", inplace=True)
                indicator_df.set_index("time", inplace=True)

                # Combine data
                combined_df = market_df.join(indicator_df, how="outer")
                combined_df = combined_df.dropna()

                # Cache the combined data
                self.symbol_data_cache[symbol][timeframe] = combined_df

                # Cache in Redis for other services
                await self.cache_json_set(
                    f"market_data:{symbol}:{timeframe}",
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "data_points": len(combined_df),
                        "latest_time": (
                            combined_df.index[-1].isoformat()
                            if not combined_df.empty
                            else None
                        ),
                    },
                    ttl=300,  # 5 minutes
                )

    async def trigger_signal_analysis(self, symbol: str):
        """Trigger signal analysis for a symbol."""
        # Check if we have enough data
        if symbol not in self.symbol_data_cache:
            return

        timeframe_data = self.symbol_data_cache[symbol]

        # Check if we have 4H data (primary timeframe)
        if "4H" not in timeframe_data:
            return

        primary_data = timeframe_data["4H"]

        if len(primary_data) < self.min_data_points:
            self.logger.debug(
                f"Insufficient data for {symbol}: {len(primary_data)} points"
            )
            return

        # Check if we've analyzed recently (avoid spam)
        last_analysis = self.last_analysis_time.get(symbol)
        if (
            last_analysis and (datetime.utcnow() - last_analysis).total_seconds() < 300
        ):  # 5 minutes
            return

        # Perform analysis
        await self.analyze_symbol(symbol)
        self.last_analysis_time[symbol] = datetime.utcnow()

    async def signal_generation_loop(self):
        """Periodic signal generation loop."""
        while self.running:
            try:
                # Analyze all active symbols periodically
                for symbol in list(self.active_symbols):
                    if not self.running:
                        break

                    try:
                        # Check if symbol has recent activity
                        recent_activity = await self.check_recent_activity(symbol)

                        if recent_activity:
                            await self.analyze_symbol(symbol)

                    except Exception as e:
                        self.logger.error(f"Error analyzing {symbol}: {e}")
                        await self.log_error(e, {"symbol": symbol})

                # Sleep until next analysis cycle
                await asyncio.sleep(self.analysis_interval)

            except Exception as e:
                self.logger.error(f"Error in signal generation loop: {e}")
                await asyncio.sleep(60)

    async def check_recent_activity(self, symbol: str) -> bool:
        """Check if symbol has recent trading activity."""
        async with self.db_pool.acquire() as conn:
            # Check for recent signals
            recent_signals = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM trading.trading_signals
                WHERE symbol = $1
                AND signal_time > NOW() - INTERVAL '4 hours'
            """,
                symbol,
            )

            # Check for open trades
            open_trades = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM trading.trades
                WHERE symbol = $1
                AND status = 'open'
            """,
                symbol,
            )

            # Check for recent market volatility
            recent_volatility = await conn.fetchval(
                """
                SELECT AVG(atr_14)
                FROM trading.indicators
                WHERE symbol = $1
                AND timeframe = '4H'
                AND time > NOW() - INTERVAL '24 hours'
            """,
                symbol,
            )

            # Consider active if recent signals, open trades, or high volatility
            return (
                recent_signals > 0
                or open_trades > 0
                or (recent_volatility and recent_volatility > 0.001)
            )

    async def analyze_symbol(self, symbol: str):
        """Perform comprehensive signal analysis for a symbol."""
        start_time = datetime.utcnow()

        try:
            self.logger.info(f"Analyzing {symbol}...")

            # Get symbol data
            if (
                symbol not in self.symbol_data_cache
                or "4H" not in self.symbol_data_cache[symbol]
            ):
                self.logger.warning(f"No data available for {symbol}")
                return

            data = self.symbol_data_cache[symbol]["4H"]

            # Generate ML signals
            ml_signals = await self.ml_engine.generate_signals(symbol, data)

            # Generate Elliott Wave signals
            ew_signals = await self.elliott_engine.generate_signals(symbol, data)

            # Combine signals
            combined_signals = await self.signal_combiner.combine_signals(
                symbol, ml_signals, ew_signals, data
            )

            # Store and publish signals
            for signal in combined_signals:
                await self.store_signal(signal)
                await self.publish_signal(signal)

            # Update performance metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.processing_times.append(processing_time)
            self.signals_generated += len(combined_signals)

            if combined_signals:
                self.logger.info(
                    f"Generated {len(combined_signals)} signals for {symbol}"
                )

            # Log analysis event
            await self.log_event(
                "signal_analysis",
                f"Analyzed {symbol}: {len(ml_signals)} ML, {len(ew_signals)} EW, {len(combined_signals)} combined",
                {
                    "symbol": symbol,
                    "ml_signals": len(ml_signals),
                    "ew_signals": len(ew_signals),
                    "combined_signals": len(combined_signals),
                    "processing_time": processing_time,
                },
            )

        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {e}")
            await self.log_error(e, {"symbol": symbol, "analysis": "signal_generation"})

    async def store_signal(self, signal: Dict[str, Any]):
        """Store signal in database."""
        async with self.db_pool.acquire() as conn:
            # Store ML signal if present
            if signal.get("ml_signal"):
                ml_sig = signal["ml_signal"]
                await conn.execute(
                    """
                    INSERT INTO trading.ml_signals
                    (signal_time, symbol, timeframe, model_name, model_version,
                     direction, confidence, features, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                    signal["timestamp"],
                    signal["symbol"],
                    signal["timeframe"],
                    ml_sig.get("model_name", "ensemble"),
                    ml_sig.get("model_version", "1.0"),
                    ml_sig["direction"],
                    ml_sig["confidence"],
                    json.dumps(ml_sig.get("features", {})),
                    json.dumps(ml_sig.get("metadata", {})),
                )

            # Store Elliott Wave pattern if present
            if signal.get("elliott_signal"):
                ew_sig = signal["elliott_signal"]
                await conn.execute(
                    """
                    INSERT INTO trading.elliott_patterns
                    (detection_time, symbol, timeframe, pattern_type, wave_degree,
                     current_wave, confidence, entry_price, target_prices,
                     stop_loss, pattern_data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                    signal["timestamp"],
                    signal["symbol"],
                    signal["timeframe"],
                    ew_sig.get("pattern_type", "unknown"),
                    ew_sig.get("wave_degree", "minor"),
                    ew_sig.get("current_wave", "unknown"),
                    ew_sig["confidence"],
                    ew_sig.get("entry_price"),
                    ew_sig.get("target_prices", []),
                    ew_sig.get("stop_loss"),
                    json.dumps(ew_sig.get("pattern_data", {})),
                )

            # Store combined trading signal
            signal_id = await conn.fetchval(
                """
                INSERT INTO trading.trading_signals
                (signal_time, symbol, direction, signal_type, confidence,
                 ml_confidence, ew_confidence, entry_price, stop_loss,
                 take_profit_1, take_profit_2, take_profit_3,
                 risk_reward_ratio, position_size_percent, metadata, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING id
            """,
                signal["timestamp"],
                signal["symbol"],
                signal["direction"],
                signal["signal_type"],
                signal["confidence"],
                signal.get("ml_confidence"),
                signal.get("ew_confidence"),
                signal["entry_price"],
                signal["stop_loss"],
                signal.get("take_profit_1"),
                signal.get("take_profit_2"),
                signal.get("take_profit_3"),
                signal.get("risk_reward_ratio", 1.0),
                signal.get("position_size_percent", 2.0),
                json.dumps(signal.get("metadata", {})),
                "pending",
            )

            # Add signal ID to the signal
            signal["signal_id"] = signal_id

    async def publish_signal(self, signal: Dict[str, Any]):
        """Publish signal to RabbitMQ."""
        # Publish ML signal
        if signal.get("ml_signal"):
            await self.publish_message(
                Exchanges.SIGNALS,
                format_routing_key(RoutingKeys.SIGNAL_ML, symbol=signal["symbol"]),
                signal,
            )

        # Publish Elliott Wave signal
        if signal.get("elliott_signal"):
            await self.publish_message(
                Exchanges.SIGNALS,
                format_routing_key(RoutingKeys.SIGNAL_ELLIOTT, symbol=signal["symbol"]),
                signal,
            )

        # Publish combined signal for validation
        await self.publish_message(
            Exchanges.SIGNALS,
            format_routing_key(RoutingKeys.SIGNAL_COMBINED, symbol=signal["symbol"]),
            signal,
        )

    async def model_update_loop(self):
        """Periodically update ML models with new data."""
        while self.running:
            try:
                # Check if it's time to retrain models (e.g., weekly)
                await self.ml_engine.check_retrain_schedule()

                # Sleep for 1 hour
                await asyncio.sleep(3600)

            except Exception as e:
                self.logger.error(f"Error in model update loop: {e}")
                await asyncio.sleep(3600)

    async def heartbeat_loop(self):
        """Send periodic heartbeats and metrics."""
        while self.running:
            try:
                # Calculate metrics
                avg_processing_time = (
                    np.mean(self.processing_times[-100:])
                    if self.processing_times
                    else 0
                )

                # Send heartbeat
                await self.publish_message(
                    Exchanges.SYSTEM,
                    format_routing_key(
                        RoutingKeys.SYSTEM_HEARTBEAT, service=self.service_name
                    ),
                    {
                        "active_symbols": list(self.active_symbols),
                        "cached_symbols": list(self.symbol_data_cache.keys()),
                        "signals_generated": self.signals_generated,
                        "avg_processing_time": avg_processing_time,
                        "health": await self.health_check(),
                    },
                )

                # Send metrics
                await self.publish_message(
                    Exchanges.SYSTEM,
                    format_routing_key(
                        RoutingKeys.SYSTEM_METRICS, service=self.service_name
                    ),
                    {
                        "signals_generated_total": self.signals_generated,
                        "avg_processing_time_seconds": avg_processing_time,
                        "active_symbols_count": len(self.active_symbols),
                        "cached_symbols_count": len(self.symbol_data_cache),
                    },
                )

                await asyncio.sleep(30)

            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(30)


if __name__ == "__main__":
    # Load configuration
    config = ServiceConfig.from_env()

    # Create and run service
    service = SignalGeneratorService(config)
    asyncio.run(service.run())
