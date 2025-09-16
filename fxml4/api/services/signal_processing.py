"""
Signal Processing Service for FXML4 API.

This service connects ML models and signal generators to real-time market data,
providing live trading signals through WebSocket and storing them in TimescaleDB.
"""

import asyncio
import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd
from pydantic import BaseModel

from fxml4.api.services.market_data import MarketDataPoint, market_data_service
from fxml4.config import get_config
from fxml4.ml.model_loader import ModelLoader
from fxml4.strategy.integrated_signal_generator import (
    IntegratedSignal,
    IntegratedSignalGenerator,
)

logger = logging.getLogger(__name__)


class SignalData(BaseModel):
    """Signal data model for API responses."""

    timestamp: datetime
    symbol: str
    timeframe: str
    direction: int  # -1, 0, 1 for sell, hold, buy
    confidence: float
    signal_type: str
    source: str
    metadata: Dict[str, Any]


class SignalProcessingService:
    """Service for processing trading signals from market data."""

    def __init__(self):
        self.config = get_config()
        self.model_loader = ModelLoader()
        self.signal_generators: Dict[str, IntegratedSignalGenerator] = {}
        self.active_symbols: Set[str] = set()
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self._pool = None

    async def initialize(self):
        """Initialize the signal processing service."""
        try:
            logger.info("Initializing Signal Processing Service...")

            # Load available models and signal generators
            await self._load_signal_generators()

            # Get database connection pool
            self._pool = await market_data_service.get_connection_pool()

            logger.info("Signal Processing Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Signal Processing Service: {e}")
            raise

    async def _load_signal_generators(self):
        """Load signal generators for active symbols."""
        try:
            # Get available symbols
            symbols = await market_data_service.get_available_symbols()
            logger.info(f"Loading signal generators for symbols: {symbols}")

            for symbol in symbols:
                try:
                    # Try to load an integrated signal generator for each symbol
                    signal_generator = await self._create_signal_generator(symbol)
                    if signal_generator:
                        self.signal_generators[symbol] = signal_generator
                        self.active_symbols.add(symbol)
                        logger.info(f"Loaded signal generator for {symbol}")
                    else:
                        logger.warning(f"No signal generator available for {symbol}")

                except Exception as e:
                    logger.error(f"Failed to load signal generator for {symbol}: {e}")
                    continue

            logger.info(
                f"Loaded signal generators for {len(self.signal_generators)} symbols"
            )

        except Exception as e:
            logger.error(f"Failed to load signal generators: {e}")

    async def _create_signal_generator(
        self, symbol: str
    ) -> Optional[IntegratedSignalGenerator]:
        """Create an integrated signal generator for a symbol."""
        try:
            # Load configuration for the symbol
            signal_config = self.config.get("signals", {}).get(symbol, {})

            # Try to load ML model for this symbol
            try:
                model_info = await asyncio.get_event_loop().run_in_executor(
                    None, self.model_loader.load_latest_model, symbol
                )

                if not model_info:
                    logger.warning(
                        f"No ML model available for {symbol}, creating simple signal generator"
                    )
                    return None

                ml_model = model_info.get("model")
                ml_scaler = model_info.get("scaler")
                ml_features = model_info.get("features", [])

                if not all([ml_model, ml_scaler, ml_features]):
                    logger.warning(f"Incomplete ML model components for {symbol}")
                    return None

            except Exception as e:
                logger.warning(f"Failed to load ML model for {symbol}: {e}")
                return None

            # Create integrated signal generator with proper parameters
            signal_generator = IntegratedSignalGenerator(
                ml_model=ml_model,
                ml_scaler=ml_scaler,
                ml_features=ml_features,
                use_llm_validation=signal_config.get("use_llm_validation", True),
            )

            return signal_generator

        except Exception as e:
            logger.warning(f"Could not create signal generator for {symbol}: {e}")
            return None

    async def start_signal_processing(self, symbols: Optional[List[str]] = None):
        """Start processing signals for specified symbols."""
        try:
            target_symbols = symbols or list(self.active_symbols)

            for symbol in target_symbols:
                if (
                    symbol in self.signal_generators
                    and symbol not in self.processing_tasks
                ):
                    task = asyncio.create_task(self._process_symbol_signals(symbol))
                    self.processing_tasks[symbol] = task
                    logger.info(f"Started signal processing for {symbol}")

            logger.info(
                f"Signal processing started for {len(self.processing_tasks)} symbols"
            )

        except Exception as e:
            logger.error(f"Failed to start signal processing: {e}")

    async def stop_signal_processing(self, symbols: Optional[List[str]] = None):
        """Stop processing signals for specified symbols."""
        try:
            target_symbols = symbols or list(self.processing_tasks.keys())

            for symbol in target_symbols:
                if symbol in self.processing_tasks:
                    self.processing_tasks[symbol].cancel()
                    del self.processing_tasks[symbol]
                    logger.info(f"Stopped signal processing for {symbol}")

            logger.info(f"Signal processing stopped for {len(target_symbols)} symbols")

        except Exception as e:
            logger.error(f"Failed to stop signal processing: {e}")

    async def _process_symbol_signals(self, symbol: str):
        """Process signals for a specific symbol."""
        logger.info(f"Starting signal processing loop for {symbol}")

        signal_generator = self.signal_generators[symbol]
        last_processed_time = None

        try:
            while True:
                try:
                    # Get recent market data
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(
                        hours=24
                    )  # Last 24 hours for context

                    market_data = await market_data_service.get_ohlcv_data(
                        symbol=symbol,
                        timeframe="1h",  # Standard timeframe for signals
                        start_time=start_time,
                        end_time=end_time,
                        limit=50,  # Last 50 data points for analysis
                    )

                    if not market_data:
                        logger.debug(f"No market data available for {symbol}")
                        await asyncio.sleep(60)  # Wait 1 minute before retrying
                        continue

                    # Convert to DataFrame for signal generation
                    df_data = []
                    for point in market_data:
                        df_data.append(
                            {
                                "timestamp": point.time,
                                "open": point.open,
                                "high": point.high,
                                "low": point.low,
                                "close": point.close,
                                "volume": point.volume,
                            }
                        )

                    df = pd.DataFrame(df_data)
                    df.set_index("timestamp", inplace=True)
                    df.sort_index(inplace=True)

                    # Only process if we have new data
                    latest_time = df.index[-1]
                    if last_processed_time and latest_time <= last_processed_time:
                        await asyncio.sleep(30)  # Wait 30 seconds for new data
                        continue

                    # Generate signal using the integrated signal generator
                    signal = await self._generate_signal(signal_generator, symbol, df)

                    if signal:
                        # Store signal in database
                        await self._store_signal(signal)

                        # Broadcast signal via WebSocket
                        await self._broadcast_signal(signal)

                        logger.info(
                            f"Generated {signal.direction:+d} signal for {symbol} "
                            f"(confidence: {signal.confidence:.2f})"
                        )

                    last_processed_time = latest_time

                    # Wait before next processing cycle
                    await asyncio.sleep(60)  # Process every minute

                except asyncio.CancelledError:
                    logger.info(f"Signal processing for {symbol} cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error processing signals for {symbol}: {e}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(30)  # Wait before retrying

        except Exception as e:
            logger.error(f"Fatal error in signal processing for {symbol}: {e}")
        finally:
            logger.info(f"Signal processing for {symbol} ended")

    async def _generate_signal(
        self,
        signal_generator: IntegratedSignalGenerator,
        symbol: str,
        market_data: pd.DataFrame,
    ) -> Optional[SignalData]:
        """Generate a trading signal from market data."""
        try:
            # Run signal generation in executor to avoid blocking
            loop = asyncio.get_event_loop()

            # Call the signal generator's generate method
            if hasattr(signal_generator, "generate_signal"):
                integrated_signal = await loop.run_in_executor(
                    None, signal_generator.generate_signal, market_data
                )
            else:
                # Fallback: create a simple signal
                logger.warning(
                    f"Signal generator for {symbol} doesn't have generate_signal method"
                )
                return self._create_simple_signal(symbol, market_data)

            if integrated_signal:
                # Convert IntegratedSignal to SignalData
                signal_data = SignalData(
                    timestamp=integrated_signal.timestamp,
                    symbol=symbol,
                    timeframe="1h",
                    direction=integrated_signal.direction,
                    confidence=integrated_signal.confidence,
                    signal_type="integrated",
                    source="signal_processing_service",
                    metadata={
                        "ml_signal": integrated_signal.ml_signal,
                        "ml_confidence": integrated_signal.ml_confidence,
                        "wave_pattern": integrated_signal.wave_pattern,
                        "wave_confidence": integrated_signal.wave_confidence,
                        "sentiment_score": integrated_signal.sentiment_score,
                        "market_regime": integrated_signal.market_regime,
                        "risk_score": integrated_signal.risk_score,
                        "reasoning": integrated_signal.reasoning,
                    },
                )

                return signal_data

            return None

        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {e}")
            return None

    def _create_simple_signal(
        self, symbol: str, market_data: pd.DataFrame
    ) -> SignalData:
        """Create a simple moving average crossover signal as fallback."""
        try:
            # Simple moving average crossover strategy
            close_prices = market_data["close"]
            ma_short = close_prices.rolling(window=5).mean()
            ma_long = close_prices.rolling(window=20).mean()

            # Get latest values
            latest_ma_short = ma_short.iloc[-1]
            latest_ma_long = ma_long.iloc[-1]
            prev_ma_short = ma_short.iloc[-2]
            prev_ma_long = ma_long.iloc[-2]

            # Determine signal
            if latest_ma_short > latest_ma_long and prev_ma_short <= prev_ma_long:
                direction = 1  # Buy signal
                confidence = 0.6
            elif latest_ma_short < latest_ma_long and prev_ma_short >= prev_ma_long:
                direction = -1  # Sell signal
                confidence = 0.6
            else:
                direction = 0  # Hold
                confidence = 0.3

            return SignalData(
                timestamp=market_data.index[-1],
                symbol=symbol,
                timeframe="1h",
                direction=direction,
                confidence=confidence,
                signal_type="simple_ma",
                source="fallback_signal",
                metadata={
                    "ma_short": float(latest_ma_short),
                    "ma_long": float(latest_ma_long),
                    "strategy": "moving_average_crossover",
                },
            )

        except Exception as e:
            logger.error(f"Error creating simple signal: {e}")
            return None

    async def _store_signal(self, signal: SignalData):
        """Store signal in TimescaleDB."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO signals (
                        timestamp, symbol_id, timeframe_id, signal_type,
                        direction, strength, source, metadata
                    ) VALUES (
                        $1,
                        (SELECT id FROM symbols WHERE name = $2),
                        (SELECT id FROM timeframes WHERE name = $3),
                        $4, $5, $6, $7, $8
                    )
                """,
                    signal.timestamp,
                    signal.symbol,
                    signal.timeframe,
                    signal.signal_type,
                    signal.direction,
                    signal.confidence,
                    signal.source,
                    json.dumps(signal.metadata),
                )

        except Exception as e:
            logger.error(f"Error storing signal: {e}")

    async def _broadcast_signal(self, signal: SignalData):
        """Broadcast signal via WebSocket."""
        try:
            # Import here to avoid circular imports
            from fxml4.api.services.websocket import websocket_service

            # Broadcast to signal subscribers
            subscription_key = f"signals:{signal.symbol}"
            message = {
                "type": "signal_update",
                "signal": {
                    "timestamp": signal.timestamp.isoformat(),
                    "symbol": signal.symbol,
                    "timeframe": signal.timeframe,
                    "direction": signal.direction,
                    "confidence": signal.confidence,
                    "signal_type": signal.signal_type,
                    "source": signal.source,
                    "metadata": signal.metadata,
                },
            }

            await websocket_service.manager.broadcast_to_subscribers(
                subscription_key, message
            )

        except Exception as e:
            logger.error(f"Error broadcasting signal: {e}")

    async def get_recent_signals(
        self, symbol: str, limit: int = 10, hours_back: int = 24
    ) -> List[SignalData]:
        """Get recent signals for a symbol."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT s.*, sym.name as symbol_name, tf.name as timeframe_name
                    FROM signals s
                    JOIN symbols sym ON s.symbol_id = sym.id
                    JOIN timeframes tf ON s.timeframe_id = tf.id
                    WHERE sym.name = $1
                    AND s.timestamp >= NOW() - INTERVAL '%s hours'
                    ORDER BY s.timestamp DESC
                    LIMIT $2
                """,
                    symbol,
                    limit,
                    hours_back=hours_back,
                )

                signals = []
                for row in rows:
                    signal = SignalData(
                        timestamp=row["timestamp"],
                        symbol=row["symbol_name"],
                        timeframe=row["timeframe_name"],
                        direction=int(row["direction"]),
                        confidence=float(row["strength"]),
                        signal_type=row["signal_type"],
                        source=row["source"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                    signals.append(signal)

                return signals

        except Exception as e:
            logger.error(f"Error retrieving recent signals: {e}")
            return []

    async def close(self):
        """Close the signal processing service."""
        try:
            # Stop all processing tasks
            await self.stop_signal_processing()

            # Wait for tasks to complete
            if self.processing_tasks:
                await asyncio.gather(
                    *self.processing_tasks.values(), return_exceptions=True
                )

            logger.info("Signal Processing Service closed")

        except Exception as e:
            logger.error(f"Error closing Signal Processing Service: {e}")


# Global service instance
signal_processing_service = SignalProcessingService()
