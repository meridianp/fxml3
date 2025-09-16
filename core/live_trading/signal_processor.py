"""
Live Signal Processor for Real-Time Trading Validation

Processes real-time market data through ML models to generate trading signals for paper trading validation.
Integrates with existing signal generation framework and ensures <2 second signal generation SLA.

Key Requirements:
- Process real-time market data through existing ML models
- Generate signals within 2-second SLA requirement
- Maintain signal quality and model performance monitoring
- Support existing GBP/USD strategy and ML models
- Validate signal strength and confidence before execution
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..database.timescaledb import TimescaleDBManager
from ..ml.features import FeatureEngineering
from ..ml.models import MLModelRegistry
from ..strategy.gbpusd_signal_generator import GBPUSDSignalGenerator
from ..strategy.integrated_signal_generator import IntegratedSignalGenerator
from .market_data import MarketDataTick


class SignalQuality(Enum):
    """Signal quality classification"""

    EXCELLENT = "excellent"  # >90% confidence, all conditions met
    GOOD = "good"  # >75% confidence, most conditions met
    FAIR = "fair"  # >60% confidence, basic conditions met
    POOR = "poor"  # <60% confidence, insufficient conditions
    INVALID = "invalid"  # Invalid or missing data


@dataclass
class LiveTradingSignal:
    """Live trading signal with validation metrics"""

    # Core signal data
    timestamp: datetime
    symbol: str
    action: str  # 'buy', 'sell', 'hold'
    confidence: float  # 0-1 confidence score
    strength: float  # Signal strength magnitude

    # Signal source information
    signal_source: str  # 'ml_model', 'elliott_wave', 'integrated'
    model_version: str
    feature_count: int

    # Market context
    current_price: float
    bid_ask_spread: float
    market_session: str  # 'london', 'ny', 'overlap', 'closed'
    volatility: float

    # Risk and sizing recommendations
    suggested_position_size: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_risk_pct: float = 0.02  # Default 2%

    # Quality metrics
    signal_quality: SignalQuality = SignalQuality.FAIR
    quality_score: float = 0.0
    validation_errors: List[str] = field(default_factory=list)

    # Generation metrics
    generation_time_ms: float = 0.0
    feature_calculation_time_ms: float = 0.0
    model_inference_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "action": self.action,
            "confidence": self.confidence,
            "strength": self.strength,
            "signal_source": self.signal_source,
            "model_version": self.model_version,
            "current_price": self.current_price,
            "bid_ask_spread": self.bid_ask_spread,
            "market_session": self.market_session,
            "volatility": self.volatility,
            "suggested_position_size": self.suggested_position_size,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "signal_quality": self.signal_quality.value,
            "quality_score": self.quality_score,
            "validation_errors": self.validation_errors,
            "generation_time_ms": self.generation_time_ms,
        }


@dataclass
class SignalProcessorMetrics:
    """Live signal processor performance metrics"""

    processor_start: datetime = field(default_factory=datetime.utcnow)
    total_signals_generated: int = 0
    signals_by_action: Dict[str, int] = field(
        default_factory=lambda: {"buy": 0, "sell": 0, "hold": 0}
    )
    signals_by_quality: Dict[str, int] = field(
        default_factory=lambda: {
            "excellent": 0,
            "good": 0,
            "fair": 0,
            "poor": 0,
            "invalid": 0,
        }
    )

    # Performance timing metrics
    avg_generation_time_ms: float = 0.0
    max_generation_time_ms: float = 0.0
    p95_generation_time_ms: float = 0.0
    sla_violations: int = 0  # >2000ms generation time

    # Model performance
    avg_confidence: float = 0.0
    avg_strength: float = 0.0
    high_confidence_signals: int = 0  # >80% confidence

    # Feature engineering performance
    avg_feature_time_ms: float = 0.0
    feature_calculation_failures: int = 0

    # Model inference performance
    avg_inference_time_ms: float = 0.0
    model_inference_failures: int = 0
    model_cache_hits: int = 0
    model_cache_misses: int = 0

    # Signal validation
    signal_validation_failures: int = 0
    market_condition_rejections: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for monitoring"""
        return {
            "processor_start": self.processor_start.isoformat(),
            "total_signals_generated": self.total_signals_generated,
            "signals_by_action": self.signals_by_action,
            "signals_by_quality": self.signals_by_quality,
            "avg_generation_time_ms": self.avg_generation_time_ms,
            "max_generation_time_ms": self.max_generation_time_ms,
            "sla_violations": self.sla_violations,
            "avg_confidence": self.avg_confidence,
            "avg_strength": self.avg_strength,
            "high_confidence_signals": self.high_confidence_signals,
            "feature_calculation_failures": self.feature_calculation_failures,
            "model_inference_failures": self.model_inference_failures,
            "signal_validation_failures": self.signal_validation_failures,
        }


class LiveSignalProcessor:
    """
    Processes real-time market data to generate trading signals for live paper trading validation.

    Integrates with existing ML models and signal generation framework to provide
    high-quality, low-latency trading signals with comprehensive monitoring.
    """

    def __init__(
        self,
        symbol: str = "GBPUSD",
        max_generation_time: int = 2,  # 2 second SLA
        min_confidence_threshold: float = 0.6,
        enable_model_caching: bool = True,
    ):
        self.symbol = symbol
        self.max_generation_time = max_generation_time
        self.min_confidence_threshold = min_confidence_threshold
        self.enable_model_caching = enable_model_caching

        # Signal generation components
        self.gbpusd_generator: Optional[GBPUSDSignalGenerator] = None
        self.integrated_generator: Optional[IntegratedSignalGenerator] = None
        self.feature_engineering: Optional[FeatureEngineering] = None
        self.model_registry: Optional[MLModelRegistry] = None
        self.db_manager: Optional[TimescaleDBManager] = None

        # Data and state management
        self.tick_history = deque(
            maxlen=1000
        )  # Keep recent ticks for feature calculation
        self.signal_history = deque(maxlen=100)  # Recent signals
        self.generation_times = deque(maxlen=100)  # Performance tracking

        # Metrics and monitoring
        self.metrics = SignalProcessorMetrics()

        # Model caching
        self.feature_cache: Dict[str, Tuple[pd.DataFrame, datetime]] = {}
        self.model_predictions_cache: Dict[str, Tuple[Any, datetime]] = {}
        self.cache_ttl_seconds = 30  # Cache TTL

        # Market session tracking
        self.current_session = "closed"
        self.session_volatility = 0.0

        self.logger = logging.getLogger(__name__)

    async def initialize(self) -> bool:
        """Initialize signal processing components"""
        try:
            self.logger.info(f"Initializing live signal processor for {self.symbol}...")

            # Initialize database connection
            self.db_manager = TimescaleDBManager()
            await self.db_manager.initialize()

            # Initialize feature engineering
            self.feature_engineering = FeatureEngineering()

            # Initialize ML model registry
            self.model_registry = MLModelRegistry()
            await self.model_registry.initialize()

            # Initialize GBP/USD signal generator
            self.gbpusd_generator = GBPUSDSignalGenerator()
            await self.gbpusd_generator.initialize()

            # Initialize integrated signal generator
            self.integrated_generator = IntegratedSignalGenerator()
            await self.integrated_generator.initialize()

            # Load and validate models
            await self._load_and_validate_models()

            self.metrics.processor_start = datetime.utcnow()
            self.logger.info("✅ Live signal processor initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize signal processor: {e}")
            return False

    async def _load_and_validate_models(self):
        """Load and validate ML models for signal generation"""
        try:
            # Load active GBP/USD model
            active_models = await self.model_registry.get_active_models(
                symbol=self.symbol
            )
            if not active_models:
                raise Exception(f"No active ML models found for {self.symbol}")

            self.logger.info(
                f"Loaded {len(active_models)} active models for {self.symbol}"
            )

            # Validate models with sample data
            for model in active_models:
                try:
                    # Create sample features for validation
                    sample_features = await self._create_sample_features()

                    # Test model inference
                    start_time = time.time()
                    prediction = await model.predict(sample_features)
                    inference_time = (time.time() - start_time) * 1000

                    if inference_time > 1000:  # >1 second is concerning
                        self.logger.warning(
                            f"Model {model.name} inference time: {inference_time:.1f}ms"
                        )

                    self.logger.info(
                        f"✅ Validated model {model.name} - inference time: {inference_time:.1f}ms"
                    )

                except Exception as e:
                    self.logger.error(
                        f"❌ Model validation failed for {model.name}: {e}"
                    )

        except Exception as e:
            self.logger.error(f"Error loading models: {e}")
            raise

    async def _create_sample_features(self) -> pd.DataFrame:
        """Create sample features for model validation"""
        # Create sample market data for testing
        sample_data = []
        base_price = 1.2500

        for i in range(100):  # 100 data points
            sample_data.append(
                {
                    "timestamp": datetime.utcnow() - timedelta(minutes=i),
                    "symbol": self.symbol,
                    "open": base_price + np.random.normal(0, 0.001),
                    "high": base_price + np.random.normal(0.001, 0.001),
                    "low": base_price + np.random.normal(-0.001, 0.001),
                    "close": base_price + np.random.normal(0, 0.001),
                    "volume": np.random.randint(1000, 10000),
                }
            )

        df = pd.DataFrame(sample_data)

        # Generate sample features
        if self.feature_engineering:
            features = await self.feature_engineering.generate_features(df)
            return features.tail(1)  # Return latest features only

        return df.tail(1)

    async def generate_live_signal(
        self, market_data: Dict[str, Any]
    ) -> Optional[LiveTradingSignal]:
        """Generate trading signal from real-time market data"""
        generation_start = time.time()

        try:
            # Add market data to history
            tick = self._convert_to_tick(market_data)
            self.tick_history.append(tick)

            # Update market session and volatility
            await self._update_market_context()

            # Skip signal generation during market close
            if self.current_session == "closed":
                return None

            # Generate signal using integrated approach
            signal = await self._generate_integrated_signal(
                market_data, generation_start
            )

            if signal:
                # Update metrics
                self._update_generation_metrics(signal, generation_start)

                # Store signal for tracking
                self.signal_history.append(signal)

                # Store in database for analysis
                await self._store_signal(signal)

            return signal

        except Exception as e:
            self.logger.error(f"Error generating live signal: {e}")
            self.metrics.signal_validation_failures += 1
            return None

    async def _generate_integrated_signal(
        self, market_data: Dict[str, Any], generation_start: float
    ) -> Optional[LiveTradingSignal]:
        """Generate integrated signal using multiple approaches"""
        try:
            # 1. Feature calculation
            feature_start = time.time()
            features = await self._calculate_live_features(market_data)
            feature_time = (time.time() - feature_start) * 1000

            if features is None or features.empty:
                self.metrics.feature_calculation_failures += 1
                return None

            # 2. ML model inference
            inference_start = time.time()
            ml_prediction = await self._get_ml_prediction(features)
            inference_time = (time.time() - inference_start) * 1000

            # 3. Technical analysis signal
            technical_signal = await self._get_technical_signal(market_data)

            # 4. Integrate signals
            integrated_signal = await self._integrate_signals(
                ml_prediction, technical_signal, market_data
            )

            if not integrated_signal:
                return None

            # 5. Create live trading signal
            signal = LiveTradingSignal(
                timestamp=datetime.utcnow(),
                symbol=self.symbol,
                action=integrated_signal["action"],
                confidence=integrated_signal["confidence"],
                strength=integrated_signal["strength"],
                signal_source="integrated",
                model_version=integrated_signal.get("model_version", "v1.0"),
                feature_count=len(features.columns) if features is not None else 0,
                current_price=market_data.get("mid", market_data.get("last", 0)),
                bid_ask_spread=market_data.get("spread", 0),
                market_session=self.current_session,
                volatility=self.session_volatility,
                suggested_position_size=integrated_signal.get("position_size", 0.01),
                stop_loss=integrated_signal.get("stop_loss"),
                take_profit=integrated_signal.get("take_profit"),
                generation_time_ms=(time.time() - generation_start) * 1000,
                feature_calculation_time_ms=feature_time,
                model_inference_time_ms=inference_time,
            )

            # 6. Validate signal quality
            await self._validate_signal_quality(signal)

            return signal

        except Exception as e:
            self.logger.error(f"Error in integrated signal generation: {e}")
            return None

    async def _calculate_live_features(
        self, market_data: Dict[str, Any]
    ) -> Optional[pd.DataFrame]:
        """Calculate features from live market data"""
        try:
            # Check cache first
            cache_key = f"features_{self.symbol}_{market_data.get('timestamp', datetime.utcnow())}"
            if self.enable_model_caching and cache_key in self.feature_cache:
                cached_features, cache_time = self.feature_cache[cache_key]
                if (
                    datetime.utcnow() - cache_time
                ).total_seconds() < self.cache_ttl_seconds:
                    self.metrics.model_cache_hits += 1
                    return cached_features

            self.metrics.model_cache_misses += 1

            # Convert tick history to DataFrame
            if len(self.tick_history) < 50:  # Need sufficient history
                return None

            tick_data = []
            for tick in list(self.tick_history)[-100:]:  # Use last 100 ticks
                tick_data.append(
                    {
                        "timestamp": tick.timestamp,
                        "symbol": tick.symbol,
                        "open": tick.mid,  # Use mid price as OHLC approximation
                        "high": max(tick.bid, tick.ask, tick.last),
                        "low": min(tick.bid, tick.ask, tick.last),
                        "close": tick.mid,
                        "volume": tick.volume,
                        "bid": tick.bid,
                        "ask": tick.ask,
                        "spread": tick.spread,
                    }
                )

            df = pd.DataFrame(tick_data)

            # Generate features using existing framework
            if self.feature_engineering:
                features = await self.feature_engineering.generate_features(df)

                # Cache results
                if self.enable_model_caching and features is not None:
                    self.feature_cache[cache_key] = (features.copy(), datetime.utcnow())

                return features.tail(1) if features is not None else None

            return None

        except Exception as e:
            self.logger.error(f"Error calculating live features: {e}")
            self.metrics.feature_calculation_failures += 1
            return None

    async def _get_ml_prediction(
        self, features: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """Get ML model prediction from features"""
        try:
            if self.model_registry is None:
                return None

            # Get active models
            active_models = await self.model_registry.get_active_models(
                symbol=self.symbol
            )
            if not active_models:
                return None

            # Use the first active model (could implement ensemble here)
            model = active_models[0]

            # Check prediction cache
            feature_hash = str(hash(str(features.values.tobytes())))
            cache_key = f"prediction_{model.name}_{feature_hash}"

            if self.enable_model_caching and cache_key in self.model_predictions_cache:
                cached_prediction, cache_time = self.model_predictions_cache[cache_key]
                if (
                    datetime.utcnow() - cache_time
                ).total_seconds() < self.cache_ttl_seconds:
                    self.metrics.model_cache_hits += 1
                    return cached_prediction

            self.metrics.model_cache_misses += 1

            # Make prediction
            prediction = await model.predict(features)

            # Convert prediction to standard format
            ml_signal = {
                "action": self._convert_prediction_to_action(prediction),
                "confidence": float(
                    abs(prediction[0])
                    if hasattr(prediction, "__len__")
                    else abs(prediction)
                ),
                "strength": float(
                    abs(prediction[0])
                    if hasattr(prediction, "__len__")
                    else abs(prediction)
                ),
                "model_version": model.version,
                "prediction_raw": float(
                    prediction[0] if hasattr(prediction, "__len__") else prediction
                ),
            }

            # Cache result
            if self.enable_model_caching:
                self.model_predictions_cache[cache_key] = (
                    ml_signal.copy(),
                    datetime.utcnow(),
                )

            return ml_signal

        except Exception as e:
            self.logger.error(f"Error getting ML prediction: {e}")
            self.metrics.model_inference_failures += 1
            return None

    def _convert_prediction_to_action(self, prediction) -> str:
        """Convert model prediction to trading action"""
        try:
            # Extract scalar value
            pred_value = prediction[0] if hasattr(prediction, "__len__") else prediction
            pred_value = float(pred_value)

            # Convert to action based on threshold
            if pred_value > 0.1:
                return "buy"
            elif pred_value < -0.1:
                return "sell"
            else:
                return "hold"

        except Exception:
            return "hold"

    async def _get_technical_signal(
        self, market_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get technical analysis signal"""
        try:
            if self.gbpusd_generator is None:
                return None

            # Convert market data to format expected by signal generator
            signal_data = {
                "symbol": self.symbol,
                "timestamp": market_data.get("timestamp", datetime.utcnow()),
                "price": market_data.get("mid", market_data.get("last", 0)),
                "volume": market_data.get("volume", 0),
                "bid": market_data.get("bid", 0),
                "ask": market_data.get("ask", 0),
            }

            # Generate technical signal
            signal = await self.gbpusd_generator.generate_signal(signal_data)

            return signal if signal else None

        except Exception as e:
            self.logger.error(f"Error getting technical signal: {e}")
            return None

    async def _integrate_signals(
        self,
        ml_prediction: Optional[Dict[str, Any]],
        technical_signal: Optional[Dict[str, Any]],
        market_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Integrate ML and technical signals"""
        try:
            # If no signals available, return None
            if not ml_prediction and not technical_signal:
                return None

            # Use ML prediction as primary signal
            if (
                ml_prediction
                and ml_prediction.get("confidence", 0) > self.min_confidence_threshold
            ):
                integrated = ml_prediction.copy()

                # Enhance with technical signal if available
                if technical_signal:
                    # Check signal alignment
                    ml_action = ml_prediction.get("action", "hold")
                    tech_action = technical_signal.get("action", "hold")

                    if ml_action == tech_action and ml_action != "hold":
                        # Signals aligned - increase confidence
                        integrated["confidence"] = min(
                            1.0, integrated["confidence"] * 1.2
                        )
                        integrated["strength"] = min(1.0, integrated["strength"] * 1.1)
                    elif ml_action != tech_action and tech_action != "hold":
                        # Signals conflicting - reduce confidence
                        integrated["confidence"] *= 0.8
                        integrated["strength"] *= 0.9

                # Add position sizing
                integrated["position_size"] = self._calculate_position_size(
                    integrated, market_data
                )

                # Add stop loss and take profit
                stop_loss, take_profit = self._calculate_stop_take_levels(
                    integrated, market_data
                )
                integrated["stop_loss"] = stop_loss
                integrated["take_profit"] = take_profit

                return integrated

            # Fall back to technical signal if ML confidence is low
            elif (
                technical_signal
                and technical_signal.get("confidence", 0)
                > self.min_confidence_threshold
            ):
                return technical_signal

            return None

        except Exception as e:
            self.logger.error(f"Error integrating signals: {e}")
            return None

    def _calculate_position_size(
        self, signal: Dict[str, Any], market_data: Dict[str, Any]
    ) -> float:
        """Calculate position size based on signal confidence"""
        try:
            base_size = 0.01  # 1% base position
            confidence = signal.get("confidence", 0.5)

            # Scale position size with confidence
            position_size = base_size * confidence

            # Adjust for market volatility
            if self.session_volatility > 0:
                volatility_adjustment = min(1.0, 1.0 / (self.session_volatility * 100))
                position_size *= volatility_adjustment

            # Cap at maximum position size
            return min(position_size, 0.02)  # Max 2%

        except Exception:
            return 0.01  # Default 1%

    def _calculate_stop_take_levels(
        self, signal: Dict[str, Any], market_data: Dict[str, Any]
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate stop loss and take profit levels"""
        try:
            current_price = market_data.get("mid", market_data.get("last", 0))
            if not current_price:
                return None, None

            action = signal.get("action", "hold")
            strength = signal.get("strength", 0.5)
            spread = market_data.get("spread", 0.0001)  # Default 1 pip

            # Base risk levels
            stop_distance = max(20 * spread, current_price * 0.005)  # 20 pips or 0.5%
            take_distance = (
                stop_distance * 2 * strength
            )  # Risk-reward ratio based on strength

            if action == "buy":
                stop_loss = current_price - stop_distance
                take_profit = current_price + take_distance
            elif action == "sell":
                stop_loss = current_price + stop_distance
                take_profit = current_price - take_distance
            else:
                return None, None

            return stop_loss, take_profit

        except Exception:
            return None, None

    async def _validate_signal_quality(self, signal: LiveTradingSignal):
        """Validate and assess signal quality"""
        try:
            validation_errors = []
            quality_score = 0.0

            # Check confidence threshold
            if signal.confidence >= 0.9:
                quality_score += 30
            elif signal.confidence >= 0.75:
                quality_score += 20
            elif signal.confidence >= 0.6:
                quality_score += 10
            else:
                validation_errors.append("Low confidence score")

            # Check generation time SLA
            if signal.generation_time_ms <= 1000:  # <1 second is excellent
                quality_score += 25
            elif signal.generation_time_ms <= 2000:  # <2 seconds meets SLA
                quality_score += 15
            else:
                validation_errors.append("Generation time SLA violation")

            # Check market conditions
            if signal.market_session in ["london", "ny", "overlap"]:
                quality_score += 15
            else:
                validation_errors.append("Poor market session timing")

            # Check spread conditions
            if signal.bid_ask_spread <= 0.0005:  # <=5 pips is good for GBPUSD
                quality_score += 15
            elif signal.bid_ask_spread <= 0.001:  # <=10 pips is acceptable
                quality_score += 5
            else:
                validation_errors.append("Wide bid-ask spread")

            # Check volatility conditions
            if 0.1 <= self.session_volatility <= 0.8:  # Moderate volatility is ideal
                quality_score += 15
            else:
                validation_errors.append("Suboptimal volatility conditions")

            # Assign quality classification
            signal.quality_score = quality_score
            signal.validation_errors = validation_errors

            if quality_score >= 80:
                signal.signal_quality = SignalQuality.EXCELLENT
            elif quality_score >= 65:
                signal.signal_quality = SignalQuality.GOOD
            elif quality_score >= 50:
                signal.signal_quality = SignalQuality.FAIR
            elif quality_score >= 30:
                signal.signal_quality = SignalQuality.POOR
            else:
                signal.signal_quality = SignalQuality.INVALID

        except Exception as e:
            self.logger.error(f"Error validating signal quality: {e}")
            signal.signal_quality = SignalQuality.INVALID
            signal.validation_errors = ["Signal validation failed"]

    def _convert_to_tick(self, market_data: Dict[str, Any]) -> MarketDataTick:
        """Convert market data dictionary to MarketDataTick"""
        return MarketDataTick(
            symbol=market_data.get("symbol", self.symbol),
            timestamp=market_data.get("timestamp", datetime.utcnow()),
            bid=float(market_data.get("bid", 0)),
            ask=float(market_data.get("ask", 0)),
            bid_size=float(market_data.get("bid_size", 0)),
            ask_size=float(market_data.get("ask_size", 0)),
            last=float(market_data.get("last", market_data.get("mid", 0))),
            last_size=float(market_data.get("last_size", 0)),
            volume=float(market_data.get("volume", 0)),
        )

    async def _update_market_context(self):
        """Update market session and volatility context"""
        try:
            current_hour = datetime.utcnow().hour

            # Determine market session
            if 7 <= current_hour < 16:  # London session
                if 12 <= current_hour < 16:  # London-NY overlap
                    self.current_session = "overlap"
                else:
                    self.current_session = "london"
            elif 12 <= current_hour < 21:  # NY session
                if 12 <= current_hour < 16:  # Already handled in overlap
                    pass
                else:
                    self.current_session = "ny"
            else:
                self.current_session = "closed"

            # Calculate session volatility
            if len(self.tick_history) >= 20:
                recent_prices = [tick.mid for tick in list(self.tick_history)[-20:]]
                price_changes = [
                    abs(recent_prices[i] - recent_prices[i - 1]) / recent_prices[i - 1]
                    for i in range(1, len(recent_prices))
                ]
                self.session_volatility = (
                    np.std(price_changes) if price_changes else 0.0
                )

        except Exception as e:
            self.logger.error(f"Error updating market context: {e}")

    def _update_generation_metrics(
        self, signal: LiveTradingSignal, generation_start: float
    ):
        """Update signal generation performance metrics"""
        try:
            self.metrics.total_signals_generated += 1

            # Update action counts
            self.metrics.signals_by_action[signal.action] += 1

            # Update quality counts
            self.metrics.signals_by_quality[signal.signal_quality.value] += 1

            # Update timing metrics
            generation_time = signal.generation_time_ms
            self.generation_times.append(generation_time)

            # Update averages
            total = self.metrics.total_signals_generated
            self.metrics.avg_generation_time_ms = (
                self.metrics.avg_generation_time_ms * (total - 1) + generation_time
            ) / total
            self.metrics.max_generation_time_ms = max(
                self.metrics.max_generation_time_ms, generation_time
            )

            # Calculate p95
            if len(self.generation_times) >= 20:
                self.metrics.p95_generation_time_ms = np.percentile(
                    list(self.generation_times), 95
                )

            # Check SLA violations
            if generation_time > self.max_generation_time * 1000:  # Convert to ms
                self.metrics.sla_violations += 1

            # Update confidence and strength averages
            self.metrics.avg_confidence = (
                self.metrics.avg_confidence * (total - 1) + signal.confidence
            ) / total
            self.metrics.avg_strength = (
                self.metrics.avg_strength * (total - 1) + signal.strength
            ) / total

            # High confidence signals
            if signal.confidence > 0.8:
                self.metrics.high_confidence_signals += 1

            # Feature engineering metrics
            self.metrics.avg_feature_time_ms = (
                self.metrics.avg_feature_time_ms * (total - 1)
                + signal.feature_calculation_time_ms
            ) / total

            # Model inference metrics
            self.metrics.avg_inference_time_ms = (
                self.metrics.avg_inference_time_ms * (total - 1)
                + signal.model_inference_time_ms
            ) / total

        except Exception as e:
            self.logger.error(f"Error updating generation metrics: {e}")

    async def _store_signal(self, signal: LiveTradingSignal):
        """Store signal in database for analysis"""
        try:
            if self.db_manager:
                signal_data = signal.to_dict()
                await self.db_manager.store_trading_signal(signal_data)
        except Exception as e:
            self.logger.error(f"Error storing signal: {e}")

    async def get_processor_metrics(self) -> Dict[str, Any]:
        """Get comprehensive processor metrics"""
        return {
            "processor_status": "active" if self.gbpusd_generator else "inactive",
            "symbol": self.symbol,
            "current_session": self.current_session,
            "session_volatility": self.session_volatility,
            "tick_history_size": len(self.tick_history),
            "signal_history_size": len(self.signal_history),
            "metrics": self.metrics.to_dict(),
            "cache_status": {
                "feature_cache_size": len(self.feature_cache),
                "prediction_cache_size": len(self.model_predictions_cache),
                "cache_enabled": self.enable_model_caching,
            },
        }

    async def cleanup(self):
        """Cleanup processor resources"""
        try:
            self.logger.info("Cleaning up signal processor...")

            # Clear caches
            self.feature_cache.clear()
            self.model_predictions_cache.clear()

            # Cleanup components
            if self.gbpusd_generator:
                await self.gbpusd_generator.cleanup()
            if self.integrated_generator:
                await self.integrated_generator.cleanup()
            if self.model_registry:
                await self.model_registry.cleanup()
            if self.db_manager:
                await self.db_manager.cleanup()

            self.logger.info("✅ Signal processor cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during signal processor cleanup: {e}")
