"""
Unified Signal Generation System for FXML4.

This module consolidates all signal generators (ML, Wave, Sentiment, Combined)
into a unified system with shared infrastructure and consistent interfaces.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.config import get_config
from fxml4.strategy.integrated_strategy import (
    Signal,
    SignalGenerator,
    SignalSource,
    SignalType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ENHANCED SIGNAL TYPES AND ENUMS
# =============================================================================


class SignalConfidence(Enum):
    """Signal confidence levels."""

    VERY_LOW = 0.2
    LOW = 0.4
    MEDIUM = 0.6
    HIGH = 0.8
    VERY_HIGH = 0.95


class SignalPriority(Enum):
    """Signal priority levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


# =============================================================================
# BASE SIGNAL GENERATOR
# =============================================================================


class BaseSignalGenerator(SignalGenerator):
    """Enhanced base class for all signal generators with shared infrastructure."""

    def __init__(
        self, config: Optional[Dict[str, Any]] = None, signal_type: str = "base"
    ):
        """Initialize base signal generator.

        Args:
            config: Configuration dictionary
            signal_type: Type identifier for this signal generator
        """
        super().__init__(config)
        self.signal_type = signal_type

        # Common configuration
        self.threshold = self.config.get("threshold", 0.6)
        self.signal_cooldown = self.config.get("signal_cooldown", 0)
        self.max_signals_per_day = self.config.get("max_signals_per_day", 10)
        self.min_confidence = self.config.get("min_confidence", 0.5)

        # Signal tracking
        self.last_signal_time: Dict[SignalType, Optional[pd.Timestamp]] = {
            SignalType.ENTRY_LONG: None,
            SignalType.ENTRY_SHORT: None,
            SignalType.EXIT_LONG: None,
            SignalType.EXIT_SHORT: None,
        }

        # Signal counting for rate limiting
        self.daily_signal_count: Dict[str, int] = {}
        self.last_reset_date = datetime.now().date()

        logger.info(f"Initialized {signal_type} signal generator")

    def _reset_daily_counters(self):
        """Reset daily signal counters if needed."""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_signal_count.clear()
            self.last_reset_date = current_date

    def _check_signal_limits(self, signal_type: SignalType) -> bool:
        """Check if signal generation is within limits."""
        self._reset_daily_counters()

        # Check daily limit
        date_key = datetime.now().strftime("%Y%m%d")
        if self.daily_signal_count.get(date_key, 0) >= self.max_signals_per_day:
            return False

        # Check cooldown
        if self.signal_cooldown > 0:
            last_time = self.last_signal_time.get(signal_type)
            if (
                last_time
                and (pd.Timestamp.now() - last_time).total_seconds()
                < self.signal_cooldown
            ):
                return False

        return True

    def _create_signal(
        self,
        signal_type: SignalType,
        confidence: float,
        price: float,
        timestamp: pd.Timestamp,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """Create a signal with validation and tracking."""
        # Validate confidence
        if confidence < self.min_confidence:
            return None

        # Check limits
        if not self._check_signal_limits(signal_type):
            return None

        # Create signal
        signal = Signal(
            signal_type=signal_type,
            confidence=confidence,
            price=price,
            timestamp=timestamp,
            source=SignalSource.STRATEGY,
            metadata=metadata or {},
        )

        # Update tracking
        self.last_signal_time[signal_type] = timestamp
        date_key = timestamp.strftime("%Y%m%d")
        self.daily_signal_count[date_key] = self.daily_signal_count.get(date_key, 0) + 1

        return signal

    @abstractmethod
    def _generate_signals_impl(
        self, data: pd.DataFrame, symbol: str, timeframe: str, **kwargs: Any
    ) -> List[Signal]:
        """Implementation-specific signal generation logic."""
        pass

    def generate_signals(
        self, data: pd.DataFrame, symbol: str, timeframe: str, **kwargs: Any
    ) -> List[Signal]:
        """Generate signals with common validation and post-processing."""
        try:
            signals = self._generate_signals_impl(data, symbol, timeframe, **kwargs)

            # Filter signals by confidence threshold
            filtered_signals = [
                signal for signal in signals if signal.confidence >= self.threshold
            ]

            logger.debug(
                f"Generated {len(signals)} signals, filtered to {len(filtered_signals)} "
                f"above threshold {self.threshold}"
            )

            return filtered_signals

        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return []


# =============================================================================
# ML SIGNAL GENERATOR
# =============================================================================


class MLSignalGenerator(BaseSignalGenerator):
    """Signal generator using machine learning models."""

    def __init__(self, model: Any, config: Optional[Dict[str, Any]] = None):
        """Initialize the ML signal generator.

        Args:
            model: ML model for generating signals
            config: Configuration dictionary
        """
        super().__init__(config, "ml")
        self.model = model

        # ML-specific configuration
        self.probability_mode = self.config.get("probability_mode", True)
        self.feature_columns = self.config.get("feature_columns", None)

        # Feature engineering settings
        self.feature_lookback = self.config.get("feature_lookback", 100)
        self.use_technical_features = self.config.get("use_technical_features", True)
        self.tech_indicators = self.config.get(
            "technical_indicators",
            ["sma", "ema", "rsi", "macd", "bollinger", "atr", "adx"],
        )

        logger.info(
            f"Initialized ML signal generator with model: {self.model.__class__.__name__}"
        )

    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for model prediction."""
        features = data.copy()

        # Generate technical indicators if requested
        if self.use_technical_features:
            from fxml4.ml.features import create_technical_features

            features = create_technical_features(
                features, indicators=self.tech_indicators
            )

        # Drop rows with NaN values
        features = features.dropna()

        # Use only specified feature columns if provided
        if self.feature_columns:
            features = features[self.feature_columns]

        return features

    def _generate_signals_impl(
        self, data: pd.DataFrame, symbol: str, timeframe: str, **kwargs: Any
    ) -> List[Signal]:
        """Generate ML-based signals."""
        if len(data) < self.feature_lookback:
            logger.warning(
                f"Insufficient data for ML signals: {len(data)} < {self.feature_lookback}"
            )
            return []

        # Prepare features
        features = self.prepare_features(data)
        if features.empty:
            return []

        # Get predictions
        try:
            if self.probability_mode and hasattr(self.model, "predict_proba"):
                predictions = self.model.predict_proba(features.values)
                # Assuming binary classification: [prob_negative, prob_positive]
                if predictions.shape[1] >= 2:
                    long_confidence = predictions[-1, 1]  # Most recent prediction
                    short_confidence = predictions[-1, 0]
                else:
                    long_confidence = predictions[-1, 0]
                    short_confidence = 1 - long_confidence
            else:
                prediction = self.model.predict(features.values)
                if prediction[-1] > 0:
                    long_confidence = abs(prediction[-1])
                    short_confidence = 0.0
                else:
                    long_confidence = 0.0
                    short_confidence = abs(prediction[-1])

        except Exception as e:
            logger.error(f"Model prediction error: {e}")
            return []

        # Generate signals based on predictions
        signals = []
        timestamp = features.index[-1]
        price = data.loc[timestamp, "close"]

        # Entry signals
        if long_confidence > self.threshold:
            signal = self._create_signal(
                SignalType.ENTRY_LONG,
                long_confidence,
                price,
                timestamp,
                {
                    "model_type": self.model.__class__.__name__,
                    "features_used": len(features.columns),
                    "prediction_confidence": long_confidence,
                },
            )
            if signal:
                signals.append(signal)

        elif short_confidence > self.threshold:
            signal = self._create_signal(
                SignalType.ENTRY_SHORT,
                short_confidence,
                price,
                timestamp,
                {
                    "model_type": self.model.__class__.__name__,
                    "features_used": len(features.columns),
                    "prediction_confidence": short_confidence,
                },
            )
            if signal:
                signals.append(signal)

        return signals


# =============================================================================
# WAVE SIGNAL GENERATOR
# =============================================================================


class WaveSignalGenerator(BaseSignalGenerator):
    """Signal generator using Elliott Wave patterns."""

    def __init__(self, wave_analyzer: Any, config: Optional[Dict[str, Any]] = None):
        """Initialize the Elliott Wave signal generator.

        Args:
            wave_analyzer: Elliott Wave analyzer
            config: Configuration dictionary
        """
        super().__init__(config, "wave")
        self.wave_analyzer = wave_analyzer

        # Wave-specific configuration
        self.position_weights = self.config.get(
            "position_weights",
            {
                "impulse_end_5": 0.9,
                "correction_end_c": 0.8,
                "impulse_end_3": 0.7,
                "diagonal_end": 0.7,
                "triangle_end": 0.6,
                "correction_end_a": 0.4,
            },
        )

        self.pattern_thresholds = self.config.get(
            "pattern_thresholds",
            {
                "impulse": 0.7,
                "correction": 0.65,
                "diagonal": 0.75,
                "triangle": 0.7,
            },
        )

        # Entry/exit position configurations
        self.entry_positions = self.config.get(
            "entry_positions", ["correction_end_c", "triangle_end"]
        )

        self.exit_positions = self.config.get(
            "exit_positions", ["impulse_end_5", "diagonal_end", "impulse_end_3"]
        )

        # LLM integration
        self.use_llm = self.config.get("use_llm", True)
        self.llm_confidence_weight = self.config.get("llm_confidence_weight", 0.5)

        logger.info("Initialized Elliott Wave signal generator")

    def _generate_signals_impl(
        self, data: pd.DataFrame, symbol: str, timeframe: str, **kwargs: Any
    ) -> List[Signal]:
        """Generate Elliott Wave-based signals."""
        try:
            # Analyze wave patterns
            wave_analysis = self.wave_analyzer.analyze(data)

            if not wave_analysis or not wave_analysis.get("patterns"):
                return []

            signals = []
            timestamp = data.index[-1]
            price = data.loc[timestamp, "close"]

            # Process wave patterns
            for pattern in wave_analysis["patterns"]:
                confidence = pattern.get("confidence", 0.0)
                position = pattern.get("position", "")
                pattern_type = pattern.get("type", "")

                # Check if pattern meets threshold
                pattern_threshold = self.pattern_thresholds.get(pattern_type, 0.7)
                if confidence < pattern_threshold:
                    continue

                # Apply position weighting
                position_weight = self.position_weights.get(position, 0.5)
                weighted_confidence = confidence * position_weight

                # Generate entry signals
                if position in self.entry_positions:
                    signal_type = self._determine_wave_signal_type(pattern, True)
                    if signal_type:
                        signal = self._create_signal(
                            signal_type,
                            weighted_confidence,
                            price,
                            timestamp,
                            {
                                "wave_pattern": pattern_type,
                                "wave_position": position,
                                "pattern_confidence": confidence,
                                "position_weight": position_weight,
                            },
                        )
                        if signal:
                            signals.append(signal)

                # Generate exit signals
                elif position in self.exit_positions:
                    signal_type = self._determine_wave_signal_type(pattern, False)
                    if signal_type:
                        signal = self._create_signal(
                            signal_type,
                            weighted_confidence,
                            price,
                            timestamp,
                            {
                                "wave_pattern": pattern_type,
                                "wave_position": position,
                                "pattern_confidence": confidence,
                                "position_weight": position_weight,
                            },
                        )
                        if signal:
                            signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"Elliott Wave analysis error: {e}")
            return []

    def _determine_wave_signal_type(
        self, pattern: Dict[str, Any], is_entry: bool
    ) -> Optional[SignalType]:
        """Determine signal type based on wave pattern."""
        wave_direction = pattern.get("direction", "up")

        if is_entry:
            if wave_direction == "up":
                return SignalType.ENTRY_LONG
            else:
                return SignalType.ENTRY_SHORT
        else:
            if wave_direction == "up":
                return SignalType.EXIT_LONG
            else:
                return SignalType.EXIT_SHORT


# =============================================================================
# SENTIMENT SIGNAL GENERATOR
# =============================================================================


class SentimentSignalGenerator(BaseSignalGenerator):
    """Signal generator using market sentiment analysis."""

    def __init__(
        self, sentiment_analyzer: Any, config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the sentiment signal generator.

        Args:
            sentiment_analyzer: Sentiment analyzer component
            config: Configuration dictionary
        """
        super().__init__(config, "sentiment")
        self.sentiment_analyzer = sentiment_analyzer

        # Sentiment-specific configuration
        self.lookback_days = self.config.get("lookback_days", 3)
        self.news_limit = self.config.get("news_limit", 50)
        self.use_weighted_sentiment = self.config.get("use_weighted_sentiment", True)
        self.recency_weight = self.config.get("recency_weight", 0.6)
        self.relevance_weight = self.config.get("relevance_weight", 0.4)

        # News sources
        self.news_sources = self.config.get(
            "news_sources", ["yahoo", "reuters", "bloomberg"]
        )

        # Cache settings
        self.use_cache = self.config.get("use_cache", True)
        self.cache_expiry = self.config.get("cache_expiry", 6)  # hours
        self._sentiment_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("Initialized sentiment signal generator")

    def get_market_sentiment(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Get market sentiment for a specific symbol."""
        cache_key = f"{symbol}_{timeframe}_{self.lookback_days}d"
        current_time = datetime.now()

        # Check cache
        if (
            self.use_cache
            and cache_key in self._sentiment_cache
            and (
                current_time - self._sentiment_cache[cache_key]["timestamp"]
            ).total_seconds()
            < self.cache_expiry * 3600
        ):
            return self._sentiment_cache[cache_key]["data"]

        # Fetch fresh sentiment data
        try:
            sentiment_data = self.sentiment_analyzer.analyze_symbol_sentiment(
                symbol=symbol,
                lookback_days=self.lookback_days,
                news_limit=self.news_limit,
                sources=self.news_sources,
            )

            # Cache the result
            if self.use_cache:
                self._sentiment_cache[cache_key] = {
                    "data": sentiment_data,
                    "timestamp": current_time,
                }

            return sentiment_data

        except Exception as e:
            logger.error(f"Error getting sentiment for {symbol}: {e}")
            return {}

    def _generate_signals_impl(
        self, data: pd.DataFrame, symbol: str, timeframe: str, **kwargs: Any
    ) -> List[Signal]:
        """Generate sentiment-based signals."""
        # Get sentiment analysis
        sentiment_data = self.get_market_sentiment(symbol, timeframe)

        if not sentiment_data:
            return []

        signals = []
        timestamp = data.index[-1]
        price = data.loc[timestamp, "close"]

        # Extract sentiment metrics
        overall_sentiment = sentiment_data.get("overall_sentiment", 0.0)
        sentiment_score = sentiment_data.get("sentiment_score", 0.0)
        news_count = sentiment_data.get("news_count", 0)

        # Calculate weighted sentiment if enabled
        if self.use_weighted_sentiment:
            recency_score = sentiment_data.get("recency_score", 0.0)
            relevance_score = sentiment_data.get("relevance_score", 0.0)

            weighted_sentiment = (
                overall_sentiment * (1 - self.recency_weight - self.relevance_weight)
                + recency_score * self.recency_weight
                + relevance_score * self.relevance_weight
            )
        else:
            weighted_sentiment = overall_sentiment

        # Generate signals based on sentiment
        confidence = min(abs(weighted_sentiment), 0.95)

        if weighted_sentiment > self.threshold and news_count >= 3:
            signal = self._create_signal(
                SignalType.ENTRY_LONG,
                confidence,
                price,
                timestamp,
                {
                    "sentiment_score": sentiment_score,
                    "overall_sentiment": overall_sentiment,
                    "weighted_sentiment": weighted_sentiment,
                    "news_count": news_count,
                    "sources": self.news_sources,
                },
            )
            if signal:
                signals.append(signal)

        elif weighted_sentiment < -self.threshold and news_count >= 3:
            signal = self._create_signal(
                SignalType.ENTRY_SHORT,
                confidence,
                price,
                timestamp,
                {
                    "sentiment_score": sentiment_score,
                    "overall_sentiment": overall_sentiment,
                    "weighted_sentiment": weighted_sentiment,
                    "news_count": news_count,
                    "sources": self.news_sources,
                },
            )
            if signal:
                signals.append(signal)

        return signals


# =============================================================================
# COMBINED SIGNAL GENERATOR
# =============================================================================


class CombinedSignalGenerator(BaseSignalGenerator):
    """Signal generator that combines multiple signal sources."""

    def __init__(
        self,
        generators: List[BaseSignalGenerator],
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the combined signal generator.

        Args:
            generators: List of signal generators to combine
            config: Configuration dictionary
        """
        super().__init__(config, "combined")
        self.generators = generators

        # Combination strategy
        self.combination_method = self.config.get(
            "combination_method", "weighted_average"
        )
        self.weights = self.config.get("weights", {})
        self.require_consensus = self.config.get("require_consensus", False)
        self.consensus_threshold = self.config.get("consensus_threshold", 0.6)

        # Signal filtering
        self.max_signals_per_generator = self.config.get("max_signals_per_generator", 2)

        logger.info(
            f"Initialized combined signal generator with {len(generators)} generators"
        )

    def _generate_signals_impl(
        self, data: pd.DataFrame, symbol: str, timeframe: str, **kwargs: Any
    ) -> List[Signal]:
        """Generate combined signals from multiple generators."""
        all_signals = []

        # Collect signals from all generators
        for generator in self.generators:
            try:
                signals = generator.generate_signals(data, symbol, timeframe, **kwargs)

                # Limit signals per generator
                if len(signals) > self.max_signals_per_generator:
                    signals = sorted(signals, key=lambda s: s.confidence, reverse=True)[
                        : self.max_signals_per_generator
                    ]

                all_signals.extend(signals)

            except Exception as e:
                logger.error(f"Error from generator {generator.signal_type}: {e}")

        # Combine signals
        if self.combination_method == "weighted_average":
            return self._combine_weighted_average(all_signals)
        elif self.combination_method == "consensus":
            return self._combine_consensus(all_signals)
        elif self.combination_method == "best_signal":
            return self._combine_best_signal(all_signals)
        else:
            return self._combine_simple_average(all_signals)

    def _combine_weighted_average(self, signals: List[Signal]) -> List[Signal]:
        """Combine signals using weighted average."""
        if not signals:
            return []

        # Group signals by type
        signal_groups = {}
        for signal in signals:
            key = signal.signal_type
            if key not in signal_groups:
                signal_groups[key] = []
            signal_groups[key].append(signal)

        combined_signals = []

        for signal_type, group_signals in signal_groups.items():
            if len(group_signals) == 1:
                combined_signals.append(group_signals[0])
                continue

            # Calculate weighted average confidence
            total_weight = 0
            weighted_confidence = 0

            for signal in group_signals:
                weight = self.weights.get(
                    signal.metadata.get("generator_type", "default"), 1.0
                )
                weighted_confidence += signal.confidence * weight
                total_weight += weight

            if total_weight > 0:
                avg_confidence = weighted_confidence / total_weight

                # Use the most recent signal as base
                latest_signal = max(group_signals, key=lambda s: s.timestamp)

                combined_signal = self._create_signal(
                    signal_type,
                    avg_confidence,
                    latest_signal.price,
                    latest_signal.timestamp,
                    {
                        "combination_method": "weighted_average",
                        "combined_from": len(group_signals),
                        "original_signals": [s.metadata for s in group_signals],
                    },
                )

                if combined_signal:
                    combined_signals.append(combined_signal)

        return combined_signals

    def _combine_consensus(self, signals: List[Signal]) -> List[Signal]:
        """Combine signals requiring consensus."""
        # Group by signal type
        signal_groups = {}
        for signal in signals:
            key = signal.signal_type
            if key not in signal_groups:
                signal_groups[key] = []
            signal_groups[key].append(signal)

        consensus_signals = []

        for signal_type, group_signals in signal_groups.items():
            # Check if we have enough signals for consensus
            required_count = max(
                2, int(len(self.generators) * self.consensus_threshold)
            )

            if len(group_signals) >= required_count:
                # Calculate average confidence
                avg_confidence = sum(s.confidence for s in group_signals) / len(
                    group_signals
                )

                latest_signal = max(group_signals, key=lambda s: s.timestamp)

                consensus_signal = self._create_signal(
                    signal_type,
                    avg_confidence,
                    latest_signal.price,
                    latest_signal.timestamp,
                    {
                        "combination_method": "consensus",
                        "consensus_count": len(group_signals),
                        "required_count": required_count,
                        "original_signals": [s.metadata for s in group_signals],
                    },
                )

                if consensus_signal:
                    consensus_signals.append(consensus_signal)

        return consensus_signals

    def _combine_best_signal(self, signals: List[Signal]) -> List[Signal]:
        """Return only the best signal of each type."""
        if not signals:
            return []

        # Group by signal type and return highest confidence
        signal_groups = {}
        for signal in signals:
            key = signal.signal_type
            if (
                key not in signal_groups
                or signal.confidence > signal_groups[key].confidence
            ):
                signal_groups[key] = signal

        return list(signal_groups.values())

    def _combine_simple_average(self, signals: List[Signal]) -> List[Signal]:
        """Combine signals using simple average."""
        # Group signals by type
        signal_groups = {}
        for signal in signals:
            key = signal.signal_type
            if key not in signal_groups:
                signal_groups[key] = []
            signal_groups[key].append(signal)

        combined_signals = []

        for signal_type, group_signals in signal_groups.items():
            if len(group_signals) == 1:
                combined_signals.append(group_signals[0])
                continue

            # Calculate simple average
            avg_confidence = sum(s.confidence for s in group_signals) / len(
                group_signals
            )
            latest_signal = max(group_signals, key=lambda s: s.timestamp)

            combined_signal = self._create_signal(
                signal_type,
                avg_confidence,
                latest_signal.price,
                latest_signal.timestamp,
                {
                    "combination_method": "simple_average",
                    "combined_from": len(group_signals),
                    "original_signals": [s.metadata for s in group_signals],
                },
            )

            if combined_signal:
                combined_signals.append(combined_signal)

        return combined_signals


# =============================================================================
# SIGNAL FACTORY
# =============================================================================


class SignalGeneratorFactory:
    """Factory for creating signal generators."""

    @staticmethod
    def create_ml_generator(
        model: Any, config: Optional[Dict[str, Any]] = None
    ) -> MLSignalGenerator:
        """Create ML signal generator."""
        return MLSignalGenerator(model, config)

    @staticmethod
    def create_wave_generator(
        wave_analyzer: Any, config: Optional[Dict[str, Any]] = None
    ) -> WaveSignalGenerator:
        """Create wave signal generator."""
        return WaveSignalGenerator(wave_analyzer, config)

    @staticmethod
    def create_sentiment_generator(
        sentiment_analyzer: Any, config: Optional[Dict[str, Any]] = None
    ) -> SentimentSignalGenerator:
        """Create sentiment signal generator."""
        return SentimentSignalGenerator(sentiment_analyzer, config)

    @staticmethod
    def create_combined_generator(
        generators: List[BaseSignalGenerator], config: Optional[Dict[str, Any]] = None
    ) -> CombinedSignalGenerator:
        """Create combined signal generator."""
        return CombinedSignalGenerator(generators, config)


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

# Aliases for backward compatibility
EnhancedMLSignalGenerator = MLSignalGenerator
EnhancedWaveSignalGenerator = WaveSignalGenerator
EnhancedSentimentSignalGenerator = SentimentSignalGenerator


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "SignalConfidence",
    "SignalPriority",
    # Base Classes
    "BaseSignalGenerator",
    # Specific Generators
    "MLSignalGenerator",
    "WaveSignalGenerator",
    "SentimentSignalGenerator",
    "CombinedSignalGenerator",
    # Factory
    "SignalGeneratorFactory",
    # Legacy Compatibility
    "EnhancedMLSignalGenerator",
    "EnhancedWaveSignalGenerator",
    "EnhancedSentimentSignalGenerator",
]
