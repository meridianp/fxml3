"""
GBP/USD Primary Strategy Implementation

This module implements the core GBP/USD trading strategy that serves as the foundation
for the FXML4 trading system. It implements dual-timeframe analysis:
- 4H/1H timeframes for trend analysis and signal generation
- 1m/5m timeframes for precise entry timing and execution

The strategy integrates multiple signal sources:
- ML models (XGBoost, LightGBM, Random Forest, Neural Networks)
- Elliott Wave pattern recognition
- Technical indicators and market microstructure
- Risk management and position sizing

Architecture follows the documented FXML4 vision for full functionality.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from fxml4.core.types import MarketRegime, SignalStrength, Symbol, Timeframe
from fxml4.data_engineering.async_timescaledb import AsyncTimescaleDBClient
from fxml4.data_engineering.feature_versioning import FeatureRegistry
from fxml4.data_engineering.robust_ib_client import RobustIBClient
from fxml4.data_engineering.unified_pipeline import UnifiedDataPipeline
from fxml4.risk_management.drawdown_control import (
    AdvancedDrawdownController,
    PositionRisk,
)
from fxml4.strategy.market_regime_classifier import (
    AdvancedMarketRegimeClassifier,
    RegimeMetrics,
)
from fxml4.wave_analysis.gbpusd_elliott_wave import (
    GBPUSDElliottWaveAnalyzer,
    WaveSignal,
)


class TradingSignal(Enum):
    """Trading signal types for GBP/USD strategy"""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class MarketPhase(Enum):
    """Market phase classification for GBP/USD"""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    BREAKOUT = "breakout"
    CONSOLIDATION = "consolidation"


@dataclass
class StrategySignal:
    """Comprehensive strategy signal with confidence and metadata"""

    symbol: str
    signal: TradingSignal
    confidence: float  # 0.0 to 1.0
    entry_price: Optional[Decimal]
    stop_loss: Optional[Decimal]
    take_profit: Optional[Decimal]
    position_size: float  # % of portfolio
    timeframe: str
    timestamp: datetime
    signal_sources: Dict[str, float]  # Source -> Confidence mapping
    market_phase: MarketPhase
    risk_score: float  # 0.0 to 1.0 (higher = more risky)
    metadata: Dict[str, Any]


@dataclass
class MarketContext:
    """Current market context for GBP/USD analysis"""

    current_price: Decimal
    volatility_regime: str  # "low", "medium", "high"
    trend_strength: float  # -1.0 to 1.0
    market_phase: MarketPhase
    london_session: bool
    ny_session: bool
    news_events: List[str]
    economic_calendar: Dict[str, Any]
    correlations: Dict[str, float]  # Other pairs correlation


class GBPUSDStrategy:
    """
    Primary GBP/USD trading strategy implementing the FXML4 dual-timeframe architecture.

    This strategy serves as the core component of the trading system and implements:
    - Multi-timeframe analysis (4H analysis → 1m execution)
    - ML model ensemble with confidence scoring
    - Elliott Wave pattern integration
    - Advanced risk management with position sizing
    - Market regime classification and adaptation
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize GBP/USD strategy with configuration"""
        self.config = config
        self.symbol = "GBPUSD"
        self.logger = logging.getLogger(f"fxml4.strategy.{self.__class__.__name__}")

        # Core components
        self.ib_client: Optional[RobustIBClient] = None
        self.data_pipeline: Optional[UnifiedDataPipeline] = None
        self.feature_registry: Optional[FeatureRegistry] = None
        self.db_client: Optional[AsyncTimescaleDBClient] = None
        self.elliott_wave_analyzer: Optional[GBPUSDElliottWaveAnalyzer] = None
        self.drawdown_controller: Optional[AdvancedDrawdownController] = None
        self.regime_classifier: Optional[AdvancedMarketRegimeClassifier] = None

        # Strategy parameters from config
        self.analysis_timeframes = config.get("analysis_timeframes", ["4H", "1H"])
        self.execution_timeframes = config.get("execution_timeframes", ["5m", "1m"])
        self.max_position_size = config.get("max_position_size", 0.02)  # 2% per trade
        self.max_portfolio_exposure = config.get(
            "max_portfolio_exposure", 0.06
        )  # 6% total
        self.risk_free_rate = config.get("risk_free_rate", 0.045)  # 4.5% annual

        # ML model configuration
        self.ml_models = config.get(
            "ml_models", ["xgboost", "lightgbm", "random_forest", "neural_network"]
        )
        self.model_weights = config.get(
            "model_weights",
            {
                "xgboost": 0.3,
                "lightgbm": 0.25,
                "random_forest": 0.2,
                "neural_network": 0.25,
            },
        )

        # Technical indicator parameters
        self.ma_periods = config.get("ma_periods", [10, 20, 50, 200])
        self.rsi_period = config.get("rsi_period", 14)
        self.bollinger_period = config.get("bollinger_period", 20)
        self.atr_period = config.get("atr_period", 14)

        # Elliott Wave parameters
        self.wave_lookback = config.get("wave_lookback", 100)  # bars
        self.fibonacci_levels = [0.236, 0.382, 0.5, 0.618, 0.786]

        # Session timing (London and NY focus for GBP/USD)
        self.london_session = (8, 17)  # UTC
        self.ny_session = (13, 22)  # UTC

        # State tracking
        self.current_signals: Dict[str, StrategySignal] = {}
        self.market_context: Optional[MarketContext] = None
        self.last_analysis_time: Optional[datetime] = None

        self.logger.info(f"Initialized GBP/USD Strategy with config: {config}")

    async def initialize(self):
        """Initialize strategy components and connections"""
        try:
            # Initialize core components
            self.ib_client = RobustIBClient(self.config.get("ib_config", {}))
            await self.ib_client.initialize()

            self.data_pipeline = UnifiedDataPipeline(self.config.get("data_config", {}))
            await self.data_pipeline.initialize()

            self.feature_registry = FeatureRegistry(
                self.config.get("feature_config", {})
            )
            await self.feature_registry.initialize()

            # Initialize TimescaleDB client for pgvector Elliott Wave analysis
            self.db_client = AsyncTimescaleDBClient(self.config.get("db_config", {}))
            await self.db_client.initialize()

            # Initialize GBP/USD Elliott Wave analyzer with pgvector support
            self.elliott_wave_analyzer = GBPUSDElliottWaveAnalyzer(
                self.config.get("elliott_wave_config", {})
            )
            await self.elliott_wave_analyzer.initialize(self.db_client)

            # Initialize Advanced Drawdown Controller
            self.drawdown_controller = AdvancedDrawdownController(
                self.config.get("drawdown_config", {})
            )

            # Initialize Market Regime Classifier
            self.regime_classifier = AdvancedMarketRegimeClassifier(
                self.config.get("regime_config", {})
            )

            self.logger.info(
                "GBP/USD Strategy initialized successfully with Elliott Wave analysis, drawdown control, and market regime classification"
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize strategy: {e}")
            raise

    async def generate_signal(self) -> Optional[StrategySignal]:
        """
        Generate comprehensive trading signal for GBP/USD

        This is the main entry point for signal generation, combining:
        - Multi-timeframe technical analysis
        - ML model ensemble predictions
        - Elliott Wave pattern recognition
        - Risk assessment and position sizing

        Returns:
            StrategySignal with confidence scores and risk assessment
        """
        try:
            # Update market context
            await self._update_market_context()

            if not self.market_context:
                self.logger.warning("No market context available")
                return None

            # Multi-timeframe analysis
            analysis_signals = await self._analyze_timeframes()

            # ML model ensemble
            ml_signals = await self._generate_ml_signals()

            # Elliott Wave analysis
            wave_signals = await self._analyze_elliott_waves()

            # Combine signals with weighted confidence
            combined_signal = await self._combine_signals(
                analysis_signals, ml_signals, wave_signals
            )

            # Risk assessment and position sizing
            if combined_signal:
                combined_signal = await self._apply_risk_management(combined_signal)

                # Apply regime-based adaptations
                combined_signal = await self.adapt_strategy_to_regime(combined_signal)

            # Update strategy state
            if combined_signal:
                self.current_signals[self.symbol] = combined_signal
                self.last_analysis_time = datetime.utcnow()

            return combined_signal

        except Exception as e:
            self.logger.error(f"Error generating signal: {e}")
            return None

    async def _update_market_context(self):
        """Update current market context for GBP/USD"""
        try:
            # Get current price data
            current_data = await self.data_pipeline.get_latest_data(
                symbol=self.symbol, timeframe="1m", limit=1
            )

            if not current_data or current_data.empty:
                self.logger.warning("No current price data available")
                return

            current_price = Decimal(str(current_data.iloc[-1]["close"]))

            # Calculate volatility regime
            volatility_data = await self.data_pipeline.get_latest_data(
                symbol=self.symbol, timeframe="1H", limit=24  # 24 hours of data
            )

            volatility_regime = "medium"  # Default
            if not volatility_data.empty:
                returns = volatility_data["close"].pct_change().dropna()
                volatility = returns.std() * np.sqrt(24)  # Annualized

                if volatility < 0.1:  # 10%
                    volatility_regime = "low"
                elif volatility > 0.2:  # 20%
                    volatility_regime = "high"

            # Perform regime classification if available
            current_regime_metrics = None
            if self.regime_classifier:
                # Get extended data for regime analysis
                regime_data = await self.data_pipeline.get_latest_data(
                    symbol=self.symbol,
                    timeframe="1H",
                    limit=252,  # 1 year of hourly data for comprehensive analysis
                )

                if not regime_data.empty:
                    # Calculate correlations with other major pairs (simplified)
                    correlations = {
                        "EURUSD": 0.7,  # Typically highly correlated
                        "USDJPY": -0.3,  # Typically negatively correlated
                        "USDCHF": -0.5,  # Typically negatively correlated
                    }

                    current_regime_metrics = (
                        await self.regime_classifier.classify_market_regime(
                            symbol=self.symbol,
                            price_data=regime_data,
                            correlation_data=correlations,
                        )
                    )

                    self.logger.info(
                        f"Market regime: {current_regime_metrics.regime.value} "
                        f"(confidence: {current_regime_metrics.regime_confidence:.2f})"
                    )

            # Determine market phase (use regime if available, otherwise fallback)
            if current_regime_metrics:
                # Map regime to market phase
                regime_to_phase = {
                    MarketRegime.TRENDING_BULLISH: MarketPhase.TRENDING_UP,
                    MarketRegime.TRENDING_BEARISH: MarketPhase.TRENDING_DOWN,
                    MarketRegime.RANGING: MarketPhase.RANGING,
                    MarketRegime.BREAKOUT: MarketPhase.BREAKOUT,
                    MarketRegime.CONSOLIDATION: MarketPhase.CONSOLIDATION,
                    MarketRegime.VOLATILE: MarketPhase.RANGING,  # Default for volatile
                    MarketRegime.LOW_VOLATILITY: MarketPhase.CONSOLIDATION,
                }
                market_phase = regime_to_phase.get(
                    current_regime_metrics.regime, MarketPhase.RANGING
                )
            else:
                market_phase = await self._classify_market_phase()

            # Check trading sessions
            now = datetime.utcnow()
            current_hour = now.hour

            london_session = (
                self.london_session[0] <= current_hour < self.london_session[1]
            )
            ny_session = self.ny_session[0] <= current_hour < self.ny_session[1]

            # Calculate trend strength (use regime if available)
            if current_regime_metrics:
                trend_strength = current_regime_metrics.trend_strength
            else:
                trend_strength = await self._calculate_trend_strength()

            # Use regime-enhanced data if available
            correlations = {}
            if current_regime_metrics:
                correlations = current_regime_metrics.correlation_data.get(
                    "individual", {}
                )
                # Use regime-based volatility classification
                if current_regime_metrics.volatility_regime.value == "high":
                    volatility_regime = "high"
                elif current_regime_metrics.volatility_regime.value == "low":
                    volatility_regime = "low"
                else:
                    volatility_regime = "medium"

            self.market_context = MarketContext(
                current_price=current_price,
                volatility_regime=volatility_regime,
                trend_strength=trend_strength,
                market_phase=market_phase,
                london_session=london_session,
                ny_session=ny_session,
                news_events=[],  # TODO: Integrate news feed
                economic_calendar={},  # TODO: Integrate economic calendar
                correlations=correlations,
            )

            # Store regime metrics for later use
            if current_regime_metrics:
                self.market_context.regime_metrics = current_regime_metrics

        except Exception as e:
            self.logger.error(f"Error updating market context: {e}")

    async def _analyze_timeframes(self) -> Dict[str, float]:
        """Analyze multiple timeframes for GBP/USD signals"""
        signals = {}

        try:
            for timeframe in self.analysis_timeframes:
                # Get OHLCV data for timeframe
                data = await self.data_pipeline.get_latest_data(
                    symbol=self.symbol,
                    timeframe=timeframe,
                    limit=200,  # 200 periods for indicators
                )

                if data.empty:
                    continue

                # Calculate technical indicators
                indicators = await self._calculate_technical_indicators(data)

                # Generate signal from indicators
                signal_strength = await self._evaluate_technical_signal(
                    indicators, timeframe
                )
                signals[f"technical_{timeframe}"] = signal_strength

        except Exception as e:
            self.logger.error(f"Error in timeframe analysis: {e}")

        return signals

    async def _generate_ml_signals(self) -> Dict[str, float]:
        """Generate signals from ML model ensemble"""
        signals = {}

        try:
            # Get feature data for ML models
            features = await self._prepare_ml_features()

            if not features:
                self.logger.warning("No features available for ML models")
                return signals

            # Run each ML model
            for model_name in self.ml_models:
                try:
                    # TODO: Load trained model and predict
                    # For now, simulate model predictions
                    prediction = await self._simulate_ml_prediction(
                        model_name, features
                    )
                    signals[f"ml_{model_name}"] = prediction

                except Exception as e:
                    self.logger.error(f"Error with ML model {model_name}: {e}")

        except Exception as e:
            self.logger.error(f"Error generating ML signals: {e}")

        return signals

    async def _analyze_elliott_waves(self) -> Dict[str, float]:
        """Analyze Elliott Wave patterns for GBP/USD using pgvector-powered analyzer"""
        signals = {}

        try:
            if not self.elliott_wave_analyzer:
                self.logger.warning("Elliott Wave analyzer not initialized")
                return signals

            # Get price data for wave analysis
            wave_data = await self.data_pipeline.get_latest_data(
                symbol=self.symbol, timeframe="1H", limit=self.wave_lookback
            )

            if wave_data.empty:
                self.logger.warning("No wave data available for Elliott Wave analysis")
                return signals

            # Analyze GBP/USD Elliott Wave patterns
            patterns = await self.elliott_wave_analyzer.analyze_gbpusd_waves(wave_data)

            if not patterns:
                self.logger.info("No Elliott Wave patterns detected")
                return signals

            # Generate signals from detected patterns
            current_price = wave_data["close"].iloc[-1]
            wave_signals = await self.elliott_wave_analyzer.generate_wave_signals(
                current_price=current_price, patterns=patterns
            )

            # Convert wave signals to strategy signals
            for wave_signal in wave_signals:
                pattern_type = wave_signal.pattern.wave_type.value
                signal_key = f"elliott_wave_{pattern_type}"

                # Store the signal in database for future reference
                await self.elliott_wave_analyzer.store_wave_signal(wave_signal)

                # Use signal strength adjusted by confidence
                signal_strength = wave_signal.signal_strength * wave_signal.confidence
                signals[signal_key] = signal_strength

                self.logger.info(
                    f"Elliott Wave signal: {signal_key} = {signal_strength:.3f} "
                    f"(confidence: {wave_signal.confidence:.3f})"
                )

            # Find similar patterns for additional confirmation
            for pattern in patterns:
                try:
                    # Store pattern in database with pgvector embedding
                    await self.elliott_wave_analyzer.store_pattern(pattern)

                    # Find historically similar patterns
                    similar_patterns = (
                        await self.elliott_wave_analyzer.find_similar_patterns(
                            pattern=pattern, limit=3, min_similarity=0.75
                        )
                    )

                    if similar_patterns:
                        # Calculate historical performance of similar patterns
                        performance = await self.elliott_wave_analyzer.get_historical_pattern_performance(
                            pattern_type=pattern.wave_type, lookback_days=30
                        )

                        # Adjust signal based on historical performance
                        historical_success_rate = performance.get(
                            "target_completion_rate", 0.5
                        )
                        historical_confidence = performance.get("avg_confidence", 0.5)

                        # Create historical performance signal
                        historical_signal_key = (
                            f"elliott_historical_{pattern.wave_type.value}"
                        )
                        historical_strength = (
                            (historical_success_rate - 0.5) * 2 * historical_confidence
                        )
                        signals[historical_signal_key] = historical_strength

                        self.logger.info(
                            f"Historical Elliott Wave signal: {historical_signal_key} = {historical_strength:.3f} "
                            f"(success_rate: {historical_success_rate:.3f})"
                        )

                except Exception as pe:
                    self.logger.warning(
                        f"Error processing pattern {pattern.pattern_id}: {pe}"
                    )
                    continue

        except Exception as e:
            self.logger.error(f"Error in Elliott Wave analysis: {e}")

        return signals

    async def _combine_signals(
        self,
        analysis_signals: Dict[str, float],
        ml_signals: Dict[str, float],
        wave_signals: Dict[str, float],
    ) -> Optional[StrategySignal]:
        """Combine multiple signal sources into final trading signal"""

        try:
            all_signals = {**analysis_signals, **ml_signals, **wave_signals}

            if not all_signals:
                return None

            # Calculate weighted average signal
            total_weight = 0
            weighted_sum = 0

            # Technical analysis weight: 40%
            for key, value in analysis_signals.items():
                weight = 0.4 / len(analysis_signals)
                weighted_sum += value * weight
                total_weight += weight

            # ML models weight: 40%
            for key, value in ml_signals.items():
                model_name = key.replace("ml_", "")
                weight = 0.4 * self.model_weights.get(model_name, 0.25)
                weighted_sum += value * weight
                total_weight += weight

            # Elliott Wave weight: 20%
            for key, value in wave_signals.items():
                weight = 0.2 / len(wave_signals) if wave_signals else 0
                weighted_sum += value * weight
                total_weight += weight

            if total_weight == 0:
                return None

            final_signal_value = weighted_sum / total_weight
            confidence = min(abs(final_signal_value), 1.0)

            # Determine signal type
            if final_signal_value > 0.6:
                signal_type = TradingSignal.STRONG_BUY
            elif final_signal_value > 0.2:
                signal_type = TradingSignal.BUY
            elif final_signal_value < -0.6:
                signal_type = TradingSignal.STRONG_SELL
            elif final_signal_value < -0.2:
                signal_type = TradingSignal.SELL
            else:
                signal_type = TradingSignal.NEUTRAL

            # Calculate entry levels
            entry_price = (
                self.market_context.current_price if self.market_context else None
            )
            stop_loss, take_profit = await self._calculate_levels(
                signal_type, entry_price
            )

            return StrategySignal(
                symbol=self.symbol,
                signal=signal_type,
                confidence=confidence,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size=0.0,  # Will be calculated in risk management
                timeframe="combined",
                timestamp=datetime.utcnow(),
                signal_sources=all_signals,
                market_phase=(
                    self.market_context.market_phase
                    if self.market_context
                    else MarketPhase.RANGING
                ),
                risk_score=0.0,  # Will be calculated in risk management
                metadata={
                    "volatility_regime": (
                        self.market_context.volatility_regime
                        if self.market_context
                        else "unknown"
                    ),
                    "london_session": (
                        self.market_context.london_session
                        if self.market_context
                        else False
                    ),
                    "ny_session": (
                        self.market_context.ny_session if self.market_context else False
                    ),
                },
            )

        except Exception as e:
            self.logger.error(f"Error combining signals: {e}")
            return None

    async def _apply_risk_management(self, signal: StrategySignal) -> StrategySignal:
        """Apply risk management and position sizing to signal with drawdown control"""

        try:
            # Calculate risk score based on multiple factors
            risk_factors = []

            # Volatility risk
            if self.market_context and self.market_context.volatility_regime == "high":
                risk_factors.append(0.3)
            elif self.market_context and self.market_context.volatility_regime == "low":
                risk_factors.append(0.1)
            else:
                risk_factors.append(0.2)

            # Session risk (lower risk during main trading sessions)
            session_risk = 0.2
            if self.market_context:
                if self.market_context.london_session or self.market_context.ny_session:
                    session_risk = 0.1
            risk_factors.append(session_risk)

            # Signal confidence risk (higher confidence = lower risk)
            confidence_risk = max(0.1, 0.4 - signal.confidence * 0.3)
            risk_factors.append(confidence_risk)

            # Market phase risk
            phase_risk = 0.2
            if signal.market_phase in [
                MarketPhase.TRENDING_UP,
                MarketPhase.TRENDING_DOWN,
            ]:
                phase_risk = 0.15
            elif signal.market_phase == MarketPhase.RANGING:
                phase_risk = 0.25
            risk_factors.append(phase_risk)

            # Combined risk score
            risk_score = np.mean(risk_factors)

            # Position sizing based on Kelly Criterion approximation
            base_position_size = self.max_position_size

            # Apply drawdown control adjustments if available
            if self.drawdown_controller:
                # Check if new positions should be halted
                if await self.drawdown_controller.should_halt_new_positions():
                    self.logger.warning(f"New positions halted due to drawdown control")
                    signal.position_size = 0.0
                    signal.metadata["halt_reason"] = "drawdown_control"
                    return signal

                # Get drawdown-adjusted position size
                base_position_size = (
                    await self.drawdown_controller.get_position_size_adjustment(
                        base_size=base_position_size, symbol=self.symbol
                    )
                )

                # Update signal metadata with drawdown info
                drawdown_metrics = await self.drawdown_controller.get_drawdown_metrics()
                signal.metadata.update(
                    {
                        "current_drawdown": drawdown_metrics.current_drawdown,
                        "drawdown_level": self.drawdown_controller.current_risk_level.value,
                        "position_scale_factor": self.drawdown_controller.position_scale_factor,
                    }
                )

            # Adjust for confidence
            confidence_multiplier = (
                signal.confidence**0.5
            )  # Square root for smoother scaling

            # Adjust for risk
            risk_multiplier = 1 - risk_score

            # Calculate final position size
            position_size = base_position_size * confidence_multiplier * risk_multiplier
            position_size = min(position_size, self.max_position_size)
            position_size = max(position_size, 0.005)  # Minimum 0.5%

            # Update signal with risk management
            signal.risk_score = risk_score
            signal.position_size = position_size
            signal.metadata.update(
                {
                    "risk_factors": risk_factors,
                    "confidence_multiplier": confidence_multiplier,
                    "risk_multiplier": risk_multiplier,
                    "base_position_size": float(base_position_size),
                }
            )

            return signal

        except Exception as e:
            self.logger.error(f"Error applying risk management: {e}")
            return signal

    # Helper methods (simplified implementations for core functionality)

    async def _calculate_technical_indicators(
        self, data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate technical indicators for the data"""
        indicators = {}

        try:
            # Moving averages
            for period in self.ma_periods:
                if len(data) >= period:
                    indicators[f"ma_{period}"] = (
                        data["close"].rolling(period).mean().iloc[-1]
                    )

            # RSI
            if len(data) >= self.rsi_period:
                delta = data["close"].diff()
                gain = (
                    (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
                )
                loss = (
                    (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
                )
                rs = gain / loss
                indicators["rsi"] = 100 - (100 / (1 + rs)).iloc[-1]

            # Bollinger Bands
            if len(data) >= self.bollinger_period:
                bb_ma = data["close"].rolling(self.bollinger_period).mean()
                bb_std = data["close"].rolling(self.bollinger_period).std()
                indicators["bb_upper"] = (bb_ma + 2 * bb_std).iloc[-1]
                indicators["bb_lower"] = (bb_ma - 2 * bb_std).iloc[-1]
                indicators["bb_position"] = (
                    data["close"].iloc[-1] - indicators["bb_lower"]
                ) / (indicators["bb_upper"] - indicators["bb_lower"])

            # ATR
            if len(data) >= self.atr_period:
                high_low = data["high"] - data["low"]
                high_close = np.abs(data["high"] - data["close"].shift())
                low_close = np.abs(data["low"] - data["close"].shift())
                ranges = pd.concat([high_low, high_close, low_close], axis=1).max(
                    axis=1
                )
                indicators["atr"] = ranges.rolling(self.atr_period).mean().iloc[-1]

        except Exception as e:
            self.logger.error(f"Error calculating technical indicators: {e}")

        return indicators

    async def _evaluate_technical_signal(
        self, indicators: Dict[str, Any], timeframe: str
    ) -> float:
        """Evaluate technical indicators to generate signal strength"""

        if not indicators:
            return 0.0

        signals = []

        try:
            # Moving average signals
            if "ma_20" in indicators and "ma_50" in indicators:
                if indicators["ma_20"] > indicators["ma_50"]:
                    signals.append(0.3)
                else:
                    signals.append(-0.3)

            # RSI signals
            if "rsi" in indicators:
                rsi = indicators["rsi"]
                if rsi > 70:
                    signals.append(-0.4)  # Overbought
                elif rsi < 30:
                    signals.append(0.4)  # Oversold
                elif 40 <= rsi <= 60:
                    signals.append(0.0)  # Neutral

            # Bollinger Band signals
            if "bb_position" in indicators:
                bb_pos = indicators["bb_position"]
                if bb_pos > 0.8:
                    signals.append(-0.3)  # Near upper band
                elif bb_pos < 0.2:
                    signals.append(0.3)  # Near lower band

            # Return average signal
            return np.mean(signals) if signals else 0.0

        except Exception as e:
            self.logger.error(f"Error evaluating technical signal: {e}")
            return 0.0

    async def _prepare_ml_features(self) -> Optional[Dict[str, Any]]:
        """Prepare features for ML model input"""
        # Simplified feature preparation
        # In production, this would extract comprehensive features
        return {
            "price_features": np.random.randn(10).tolist(),
            "volume_features": np.random.randn(5).tolist(),
            "technical_features": np.random.randn(20).tolist(),
        }

    async def _simulate_ml_prediction(
        self, model_name: str, features: Dict[str, Any]
    ) -> float:
        """Simulate ML model prediction (placeholder)"""
        # This is a placeholder - in production, load actual trained models
        return np.random.uniform(-1, 1)

    async def _classify_market_phase(self) -> MarketPhase:
        """Classify current market phase"""
        # Simplified market phase classification
        return MarketPhase.RANGING  # Default

    async def _calculate_trend_strength(self) -> float:
        """Calculate trend strength (-1 to 1)"""
        # Simplified trend calculation
        return 0.0

    async def _detect_wave_patterns(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect Elliott Wave patterns in price data"""
        # Placeholder for Elliott Wave detection
        return []

    async def _analyze_pattern_outcomes(self, patterns: List[Dict[str, Any]]) -> float:
        """Analyze outcomes of similar Elliott Wave patterns"""
        # Placeholder for pattern outcome analysis
        return 0.0

    async def _calculate_levels(
        self, signal_type: TradingSignal, entry_price: Optional[Decimal]
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Calculate stop loss and take profit levels"""
        if not entry_price:
            return None, None

        # Simplified level calculation using ATR
        # In production, this would use more sophisticated methods
        atr_multiplier = 2.0
        risk_reward_ratio = 2.0

        if signal_type in [TradingSignal.BUY, TradingSignal.STRONG_BUY]:
            stop_loss = entry_price * Decimal("0.998")  # 0.2% below
            take_profit = entry_price * Decimal("1.004")  # 0.4% above
        elif signal_type in [TradingSignal.SELL, TradingSignal.STRONG_SELL]:
            stop_loss = entry_price * Decimal("1.002")  # 0.2% above
            take_profit = entry_price * Decimal("0.996")  # 0.4% below
        else:
            return None, None

        return stop_loss, take_profit

    async def get_current_signal(self) -> Optional[StrategySignal]:
        """Get the current signal for GBP/USD"""
        return self.current_signals.get(self.symbol)

    async def update_portfolio_value(self, portfolio_value: float):
        """Update portfolio value for drawdown monitoring"""
        try:
            if self.drawdown_controller:
                await self.drawdown_controller.update_portfolio_value(
                    timestamp=datetime.utcnow(), portfolio_value=portfolio_value
                )

                # Log drawdown status if significant
                metrics = await self.drawdown_controller.get_drawdown_metrics()
                if metrics.current_drawdown > 0.01:  # > 1%
                    self.logger.info(
                        f"Portfolio drawdown: {metrics.current_drawdown:.2%}, "
                        f"Risk level: {self.drawdown_controller.current_risk_level.value}"
                    )

        except Exception as e:
            self.logger.error(f"Error updating portfolio value: {e}")

    async def update_position_risk(
        self,
        position_id: str,
        symbol: str,
        unrealized_pnl: Decimal,
        position_size: float,
    ):
        """Update individual position risk assessment"""
        try:
            if self.drawdown_controller:
                # Create position risk object
                position_risk = PositionRisk(
                    position_id=position_id,
                    symbol=symbol,
                    unrealized_pnl=unrealized_pnl,
                    position_size=position_size,
                    risk_score=0.5,  # Will be calculated by controller
                    contribution_to_drawdown=0.0,  # Will be calculated
                    time_in_position=timedelta(hours=1),  # Placeholder
                    correlation_risk=0.3,
                    volatility_risk=0.2,
                    liquidity_risk=0.1,
                    priority_for_closure=5,
                )

                await self.drawdown_controller.update_position(position_risk)

        except Exception as e:
            self.logger.error(f"Error updating position risk: {e}")

    async def close_position_drawdown(self, position_id: str, reason: str = "strategy"):
        """Close position through drawdown controller"""
        try:
            if self.drawdown_controller:
                success = await self.drawdown_controller.close_position(
                    position_id, reason
                )
                if success:
                    self.logger.info(
                        f"Position {position_id} closed via drawdown controller: {reason}"
                    )
                return success
        except Exception as e:
            self.logger.error(f"Error closing position via drawdown controller: {e}")
        return False

    async def get_positions_to_close_for_risk(self) -> List[str]:
        """Get positions that should be closed due to risk management"""
        try:
            if self.drawdown_controller:
                return await self.drawdown_controller.get_positions_to_close()
        except Exception as e:
            self.logger.error(f"Error getting positions to close: {e}")
        return []

    async def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary including drawdown metrics"""
        try:
            summary = {
                "strategy": "GBP/USD",
                "timestamp": datetime.utcnow().isoformat(),
                "market_context": {
                    "current_price": (
                        float(self.market_context.current_price)
                        if self.market_context
                        else None
                    ),
                    "volatility_regime": (
                        self.market_context.volatility_regime
                        if self.market_context
                        else None
                    ),
                    "market_phase": (
                        self.market_context.market_phase.value
                        if self.market_context
                        else None
                    ),
                    "london_session": (
                        self.market_context.london_session
                        if self.market_context
                        else False
                    ),
                    "ny_session": (
                        self.market_context.ny_session if self.market_context else False
                    ),
                },
            }

            # Add drawdown controller metrics
            if self.drawdown_controller:
                drawdown_summary = await self.drawdown_controller.get_risk_summary()
                summary["drawdown_control"] = drawdown_summary

            # Add regime classifier metrics
            if self.regime_classifier:
                regime_summary = await self.regime_classifier.get_regime_summary()
                summary["market_regime"] = regime_summary

            return summary

        except Exception as e:
            self.logger.error(f"Error getting risk summary: {e}")
            return {"error": str(e)}

    async def get_regime_metrics(self) -> Optional[RegimeMetrics]:
        """Get current market regime metrics"""
        try:
            if self.regime_classifier and self.regime_classifier.current_metrics:
                return self.regime_classifier.current_metrics
            elif hasattr(self.market_context, "regime_metrics"):
                return self.market_context.regime_metrics
            return None
        except Exception as e:
            self.logger.error(f"Error getting regime metrics: {e}")
            return None

    async def adapt_strategy_to_regime(self, signal: StrategySignal) -> StrategySignal:
        """Adapt strategy signal based on current market regime"""
        try:
            regime_metrics = await self.get_regime_metrics()
            if not regime_metrics:
                return signal

            # Regime-specific adjustments
            regime_adjustments = {
                MarketRegime.TRENDING_BULLISH: {
                    "confidence_multiplier": 1.2,
                    "position_multiplier": 1.1,
                },
                MarketRegime.TRENDING_BEARISH: {
                    "confidence_multiplier": 1.2,
                    "position_multiplier": 1.1,
                },
                MarketRegime.RANGING: {
                    "confidence_multiplier": 0.8,
                    "position_multiplier": 0.9,
                },
                MarketRegime.VOLATILE: {
                    "confidence_multiplier": 0.7,
                    "position_multiplier": 0.8,
                },
                MarketRegime.BREAKOUT: {
                    "confidence_multiplier": 1.3,
                    "position_multiplier": 1.2,
                },
                MarketRegime.CONSOLIDATION: {
                    "confidence_multiplier": 0.9,
                    "position_multiplier": 0.9,
                },
                MarketRegime.LOW_VOLATILITY: {
                    "confidence_multiplier": 1.0,
                    "position_multiplier": 1.05,
                },
            }

            adjustments = regime_adjustments.get(
                regime_metrics.regime,
                {"confidence_multiplier": 1.0, "position_multiplier": 1.0},
            )

            # Apply regime-based adjustments
            signal.confidence *= adjustments["confidence_multiplier"]
            signal.confidence = min(1.0, signal.confidence)  # Cap at 1.0

            signal.position_size *= adjustments["position_multiplier"]
            signal.position_size = min(signal.position_size, self.max_position_size)

            # Add regime information to metadata
            signal.metadata.update(
                {
                    "regime": regime_metrics.regime.value,
                    "regime_confidence": regime_metrics.regime_confidence,
                    "trend_strength": regime_metrics.trend_strength,
                    "volatility_regime": regime_metrics.volatility_regime.value,
                    "regime_adjustment_applied": True,
                    "confidence_multiplier": adjustments["confidence_multiplier"],
                    "position_multiplier": adjustments["position_multiplier"],
                }
            )

            self.logger.info(
                f"Strategy adapted to {regime_metrics.regime.value} regime: "
                f"confidence adjusted by {adjustments['confidence_multiplier']:.2f}, "
                f"position size adjusted by {adjustments['position_multiplier']:.2f}"
            )

            return signal

        except Exception as e:
            self.logger.error(f"Error adapting strategy to regime: {e}")
            return signal

    async def cleanup(self):
        """Cleanup strategy resources"""
        try:
            if self.ib_client:
                await self.ib_client.disconnect()

            if self.data_pipeline:
                await self.data_pipeline.cleanup()

            if self.feature_registry:
                await self.feature_registry.cleanup()

            if self.elliott_wave_analyzer:
                await self.elliott_wave_analyzer.cleanup()

            if self.db_client:
                await self.db_client.close()

            if self.drawdown_controller:
                await self.drawdown_controller.cleanup()

            if self.regime_classifier:
                await self.regime_classifier.cleanup()

            self.logger.info("GBP/USD Strategy cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
