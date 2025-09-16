"""
FXML4 Confidence Scoring System

Advanced confidence scoring system for ML predictions and trading signals in the
FXML4 trading system. Provides reliability assessment and quality indicators for
all trading decisions, based on lessons learned from the PDF policy processor.

Key Features:
- Multi-dimensional confidence calculation for ML predictions
- Trading signal confidence scoring with market condition analysis
- Historical performance-based confidence adjustment
- Model ensemble confidence aggregation
- Real-time confidence monitoring and alerting
- Risk-adjusted confidence thresholds

Author: FXML4 Development Team
Created: 2024-12-28
"""

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence levels for predictions and signals."""

    VERY_HIGH = "very_high"  # > 90% - High conviction trades
    HIGH = "high"  # 80-90% - Standard trades
    MEDIUM = "medium"  # 60-80% - Reduced position sizing
    LOW = "low"  # 40-60% - Minimal position sizing
    VERY_LOW = "very_low"  # < 40% - Signal rejection


class ConfidenceComponent(Enum):
    """Components that contribute to confidence scoring."""

    MODEL_CERTAINTY = "model_certainty"  # ML model prediction confidence
    DATA_QUALITY = "data_quality"  # Input data quality assessment
    MARKET_REGIME = "market_regime"  # Market condition suitability
    HISTORICAL_PERFORMANCE = "historical_performance"  # Past prediction accuracy
    FEATURE_STABILITY = "feature_stability"  # Input feature consistency
    ENSEMBLE_AGREEMENT = "ensemble_agreement"  # Multi-model consensus
    VOLATILITY_CONTEXT = "volatility_context"  # Market volatility appropriateness
    LIQUIDITY_CONTEXT = "liquidity_context"  # Market liquidity assessment


@dataclass
class ConfidenceScore:
    """Comprehensive confidence score for predictions and signals."""

    overall_confidence: float  # 0.0 - 1.0 overall confidence
    confidence_level: ConfidenceLevel  # Categorical confidence level
    component_scores: Dict[ConfidenceComponent, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate confidence score and set level."""
        if not 0.0 <= self.overall_confidence <= 1.0:
            raise ValueError(
                f"Confidence score must be 0.0-1.0, got {self.overall_confidence}"
            )

        # Set confidence level based on score
        if self.overall_confidence >= 0.9:
            self.confidence_level = ConfidenceLevel.VERY_HIGH
        elif self.overall_confidence >= 0.8:
            self.confidence_level = ConfidenceLevel.HIGH
        elif self.overall_confidence >= 0.6:
            self.confidence_level = ConfidenceLevel.MEDIUM
        elif self.overall_confidence >= 0.4:
            self.confidence_level = ConfidenceLevel.LOW
        else:
            self.confidence_level = ConfidenceLevel.VERY_LOW

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "overall_confidence": self.overall_confidence,
            "confidence_level": self.confidence_level.value,
            "component_scores": {
                comp.value: score for comp, score in self.component_scores.items()
            },
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ModelPredictionInput:
    """Input for ML model prediction confidence scoring."""

    prediction: Union[float, np.ndarray]  # Model prediction(s)
    prediction_probabilities: Optional[np.ndarray] = (
        None  # Class probabilities if available
    )
    feature_values: Optional[np.ndarray] = None  # Input feature values
    model_name: str = "unknown"  # Model identifier
    training_accuracy: Optional[float] = None  # Historical training accuracy
    validation_accuracy: Optional[float] = None  # Historical validation accuracy
    prediction_variance: Optional[float] = None  # Prediction uncertainty measure


@dataclass
class TradingSignalInput:
    """Input for trading signal confidence scoring."""

    signal_strength: float  # Signal strength (-1 to 1)
    symbol: str  # Trading symbol
    timeframe: str  # Signal timeframe
    market_data: Dict[str, Any]  # Current market data
    technical_indicators: Dict[str, float]  # Technical indicator values
    volume_profile: Optional[Dict[str, Any]] = None  # Volume analysis
    sentiment_score: Optional[float] = None  # Market sentiment
    news_impact: Optional[float] = None  # News impact assessment


class ConfidenceScorer:
    """
    Advanced confidence scoring system for FXML4 trading system.

    Provides comprehensive confidence assessment for ML predictions and trading
    signals based on multiple factors including model certainty, data quality,
    market conditions, and historical performance.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize confidence scorer.

        Args:
            config: Configuration dictionary with scoring parameters
        """
        self.config = config or {}
        self.logger = logger.getChild("confidence_scorer")

        # Configure component weights
        self._configure_weights()

        # Historical performance tracking
        self.performance_history: Dict[str, List[Dict[str, Any]]] = {}
        self.market_regime_cache: Dict[str, Any] = {}

        self.logger.info(
            "ConfidenceScorer initialized with comprehensive scoring components"
        )

    def _configure_weights(self):
        """Configure weights for confidence components."""
        self.component_weights = self.config.get(
            "component_weights",
            {
                ConfidenceComponent.MODEL_CERTAINTY: 0.25,
                ConfidenceComponent.DATA_QUALITY: 0.15,
                ConfidenceComponent.MARKET_REGIME: 0.15,
                ConfidenceComponent.HISTORICAL_PERFORMANCE: 0.15,
                ConfidenceComponent.FEATURE_STABILITY: 0.10,
                ConfidenceComponent.ENSEMBLE_AGREEMENT: 0.10,
                ConfidenceComponent.VOLATILITY_CONTEXT: 0.05,
                ConfidenceComponent.LIQUIDITY_CONTEXT: 0.05,
            },
        )

        # Validate weights sum to 1.0
        total_weight = sum(self.component_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            self.logger.warning(
                f"Component weights sum to {total_weight}, normalizing to 1.0"
            )
            for component in self.component_weights:
                self.component_weights[component] /= total_weight

    def score_ml_prediction(
        self, prediction_input: ModelPredictionInput
    ) -> ConfidenceScore:
        """
        Score confidence for ML model prediction.

        Args:
            prediction_input: ML prediction input data

        Returns:
            Comprehensive confidence score
        """
        try:
            component_scores = {}

            # Model certainty - based on prediction probabilities or variance
            component_scores[ConfidenceComponent.MODEL_CERTAINTY] = (
                self._score_model_certainty(
                    prediction_input.prediction,
                    prediction_input.prediction_probabilities,
                    prediction_input.prediction_variance,
                )
            )

            # Data quality - based on feature completeness and validity
            component_scores[ConfidenceComponent.DATA_QUALITY] = (
                self._score_data_quality(prediction_input.feature_values)
            )

            # Historical performance - based on model's past accuracy
            component_scores[ConfidenceComponent.HISTORICAL_PERFORMANCE] = (
                self._score_historical_performance(
                    prediction_input.model_name,
                    prediction_input.training_accuracy,
                    prediction_input.validation_accuracy,
                )
            )

            # Feature stability - based on input consistency
            component_scores[ConfidenceComponent.FEATURE_STABILITY] = (
                self._score_feature_stability(
                    prediction_input.feature_values, prediction_input.model_name
                )
            )

            # Calculate weighted overall confidence
            overall_confidence = self._calculate_weighted_confidence(component_scores)

            # Create confidence score
            confidence_score = ConfidenceScore(
                overall_confidence=overall_confidence,
                confidence_level=ConfidenceLevel.MEDIUM,  # Will be set in __post_init__
                component_scores=component_scores,
                metadata={
                    "model_name": prediction_input.model_name,
                    "prediction_type": "ml_prediction",
                    "prediction_value": (
                        float(prediction_input.prediction)
                        if np.isscalar(prediction_input.prediction)
                        else prediction_input.prediction.tolist()
                    ),
                },
            )

            self.logger.debug(
                f"ML prediction confidence: {overall_confidence:.3f} ({confidence_score.confidence_level.value})"
            )
            return confidence_score

        except Exception as e:
            self.logger.error(f"Error scoring ML prediction confidence: {e}")
            # Return low confidence score on error
            return ConfidenceScore(
                overall_confidence=0.3,
                confidence_level=ConfidenceLevel.LOW,
                metadata={"error": str(e), "prediction_type": "ml_prediction"},
            )

    def score_trading_signal(self, signal_input: TradingSignalInput) -> ConfidenceScore:
        """
        Score confidence for trading signal.

        Args:
            signal_input: Trading signal input data

        Returns:
            Comprehensive confidence score
        """
        try:
            component_scores = {}

            # Market regime analysis
            component_scores[ConfidenceComponent.MARKET_REGIME] = (
                self._score_market_regime(
                    signal_input.symbol,
                    signal_input.market_data,
                    signal_input.technical_indicators,
                )
            )

            # Volatility context
            component_scores[ConfidenceComponent.VOLATILITY_CONTEXT] = (
                self._score_volatility_context(
                    signal_input.market_data, signal_input.signal_strength
                )
            )

            # Liquidity context
            component_scores[ConfidenceComponent.LIQUIDITY_CONTEXT] = (
                self._score_liquidity_context(
                    signal_input.volume_profile, signal_input.market_data
                )
            )

            # Data quality for trading signal
            component_scores[ConfidenceComponent.DATA_QUALITY] = (
                self._score_signal_data_quality(
                    signal_input.market_data, signal_input.technical_indicators
                )
            )

            # Historical performance for signal type
            component_scores[ConfidenceComponent.HISTORICAL_PERFORMANCE] = (
                self._score_signal_historical_performance(
                    signal_input.symbol,
                    signal_input.timeframe,
                    abs(signal_input.signal_strength),
                )
            )

            # Calculate weighted overall confidence
            overall_confidence = self._calculate_weighted_confidence(component_scores)

            # Create confidence score
            confidence_score = ConfidenceScore(
                overall_confidence=overall_confidence,
                confidence_level=ConfidenceLevel.MEDIUM,  # Will be set in __post_init__
                component_scores=component_scores,
                metadata={
                    "symbol": signal_input.symbol,
                    "timeframe": signal_input.timeframe,
                    "prediction_type": "trading_signal",
                    "signal_strength": signal_input.signal_strength,
                    "sentiment_score": signal_input.sentiment_score,
                    "news_impact": signal_input.news_impact,
                },
            )

            self.logger.debug(
                f"Trading signal confidence for {signal_input.symbol}: {overall_confidence:.3f} ({confidence_score.confidence_level.value})"
            )
            return confidence_score

        except Exception as e:
            self.logger.error(f"Error scoring trading signal confidence: {e}")
            # Return low confidence score on error
            return ConfidenceScore(
                overall_confidence=0.3,
                confidence_level=ConfidenceLevel.LOW,
                metadata={
                    "error": str(e),
                    "prediction_type": "trading_signal",
                    "symbol": signal_input.symbol,
                },
            )

    def score_ensemble_prediction(
        self,
        individual_scores: List[ConfidenceScore],
        ensemble_prediction: Union[float, np.ndarray],
        ensemble_method: str = "weighted_average",
    ) -> ConfidenceScore:
        """
        Score confidence for ensemble model prediction.

        Args:
            individual_scores: Individual model confidence scores
            ensemble_prediction: Final ensemble prediction
            ensemble_method: Method used for ensemble aggregation

        Returns:
            Ensemble confidence score
        """
        try:
            if not individual_scores:
                return ConfidenceScore(
                    overall_confidence=0.0,
                    confidence_level=ConfidenceLevel.VERY_LOW,
                    metadata={
                        "error": "No individual scores provided",
                        "prediction_type": "ensemble",
                    },
                )

            # Calculate ensemble agreement
            individual_confidences = [
                score.overall_confidence for score in individual_scores
            ]
            agreement_score = self._calculate_ensemble_agreement(individual_confidences)

            # Base confidence from individual scores
            if ensemble_method == "weighted_average":
                base_confidence = np.mean(individual_confidences)
            elif ensemble_method == "confidence_weighted":
                weights = np.array(individual_confidences)
                weights = weights / weights.sum()
                base_confidence = np.sum(weights * individual_confidences)
            else:
                base_confidence = np.mean(individual_confidences)

            # Boost confidence based on agreement
            ensemble_confidence = min(
                1.0, base_confidence * (0.7 + 0.3 * agreement_score)
            )

            # Aggregate component scores
            aggregated_components = {}
            for component in ConfidenceComponent:
                component_values = []
                for score in individual_scores:
                    if component in score.component_scores:
                        component_values.append(score.component_scores[component])

                if component_values:
                    aggregated_components[component] = np.mean(component_values)

            # Add ensemble-specific component
            aggregated_components[ConfidenceComponent.ENSEMBLE_AGREEMENT] = (
                agreement_score
            )

            # Create ensemble confidence score
            confidence_score = ConfidenceScore(
                overall_confidence=ensemble_confidence,
                confidence_level=ConfidenceLevel.MEDIUM,  # Will be set in __post_init__
                component_scores=aggregated_components,
                metadata={
                    "prediction_type": "ensemble",
                    "ensemble_method": ensemble_method,
                    "num_models": len(individual_scores),
                    "individual_confidences": individual_confidences,
                    "agreement_score": agreement_score,
                    "ensemble_prediction": (
                        float(ensemble_prediction)
                        if np.isscalar(ensemble_prediction)
                        else ensemble_prediction.tolist()
                    ),
                },
            )

            self.logger.debug(
                f"Ensemble confidence: {ensemble_confidence:.3f} from {len(individual_scores)} models"
            )
            return confidence_score

        except Exception as e:
            self.logger.error(f"Error scoring ensemble prediction confidence: {e}")
            return ConfidenceScore(
                overall_confidence=0.2,
                confidence_level=ConfidenceLevel.VERY_LOW,
                metadata={"error": str(e), "prediction_type": "ensemble"},
            )

    def _score_model_certainty(
        self,
        prediction: Union[float, np.ndarray],
        probabilities: Optional[np.ndarray],
        variance: Optional[float],
    ) -> float:
        """Score model prediction certainty."""
        try:
            if probabilities is not None and len(probabilities) > 1:
                # Classification: use entropy of probabilities
                probabilities = np.array(probabilities)
                probabilities = probabilities / probabilities.sum()  # Normalize
                entropy = -np.sum(probabilities * np.log2(probabilities + 1e-10))
                max_entropy = np.log2(len(probabilities))
                certainty = 1.0 - (entropy / max_entropy)
                return max(0.0, min(1.0, certainty))

            elif variance is not None:
                # Regression: use prediction variance
                # Lower variance = higher certainty
                if variance <= 0:
                    return 1.0
                # Normalize variance to 0-1 scale (assuming variance typically < 1)
                normalized_variance = min(1.0, variance)
                return 1.0 - normalized_variance

            else:
                # Default: assume medium certainty without additional info
                return 0.7

        except Exception as e:
            self.logger.error(f"Error scoring model certainty: {e}")
            return 0.5

    def _score_data_quality(self, feature_values: Optional[np.ndarray]) -> float:
        """Score input data quality."""
        try:
            if feature_values is None:
                return 0.5

            feature_array = np.array(feature_values)

            # Check for missing values
            missing_ratio = np.isnan(feature_array).sum() / len(feature_array)

            # Check for infinite values
            infinite_ratio = np.isinf(feature_array).sum() / len(feature_array)

            # Check for zero variance (constant features)
            non_nan_values = feature_array[~np.isnan(feature_array)]
            if len(non_nan_values) > 1:
                variance_score = min(1.0, np.var(non_nan_values))
            else:
                variance_score = 0.0

            # Combine quality metrics
            quality_score = (
                (1.0 - missing_ratio) * 0.4
                + (1.0 - infinite_ratio) * 0.3
                + variance_score * 0.3
            )

            return max(0.0, min(1.0, quality_score))

        except Exception as e:
            self.logger.error(f"Error scoring data quality: {e}")
            return 0.5

    def _score_historical_performance(
        self,
        model_name: str,
        training_accuracy: Optional[float],
        validation_accuracy: Optional[float],
    ) -> float:
        """Score based on historical model performance."""
        try:
            # Use validation accuracy if available, otherwise training accuracy
            if validation_accuracy is not None:
                base_score = validation_accuracy
            elif training_accuracy is not None:
                base_score = training_accuracy * 0.8  # Discount training accuracy
            else:
                # Check historical performance cache
                if model_name in self.performance_history:
                    recent_performance = self.performance_history[model_name][
                        -10:
                    ]  # Last 10 records
                    if recent_performance:
                        avg_performance = np.mean(
                            [p["accuracy"] for p in recent_performance]
                        )
                        return max(0.0, min(1.0, avg_performance))

                return 0.6  # Default for unknown models

            return max(0.0, min(1.0, base_score))

        except Exception as e:
            self.logger.error(f"Error scoring historical performance: {e}")
            return 0.5

    def _score_feature_stability(
        self, feature_values: Optional[np.ndarray], model_name: str
    ) -> float:
        """Score feature stability and consistency."""
        try:
            if feature_values is None:
                return 0.5

            # Simple stability measure: check for extreme values
            feature_array = np.array(feature_values)
            non_nan_features = feature_array[~np.isnan(feature_array)]

            if len(non_nan_features) == 0:
                return 0.0

            # Check for values beyond reasonable ranges (3 standard deviations)
            mean_val = np.mean(non_nan_features)
            std_val = np.std(non_nan_features)

            if std_val > 0:
                outlier_ratio = np.sum(
                    np.abs(non_nan_features - mean_val) > 3 * std_val
                ) / len(non_nan_features)
                stability_score = 1.0 - outlier_ratio
            else:
                stability_score = 0.8  # Constant features have medium stability

            return max(0.0, min(1.0, stability_score))

        except Exception as e:
            self.logger.error(f"Error scoring feature stability: {e}")
            return 0.5

    def _score_market_regime(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        technical_indicators: Dict[str, float],
    ) -> float:
        """Score market regime suitability for trading."""
        try:
            # Extract key market indicators
            volatility = market_data.get("volatility", 0.02)
            volume = market_data.get("volume", 1000000)
            bid_ask_spread = market_data.get("bid_ask_spread", 0.0001)

            # Volatility assessment (moderate volatility is optimal)
            optimal_volatility = 0.015  # 1.5% daily volatility
            volatility_score = 1.0 - min(
                1.0, abs(volatility - optimal_volatility) / optimal_volatility
            )

            # Volume assessment (higher volume generally better)
            typical_volume = 10000000  # Typical daily volume
            volume_score = min(1.0, volume / typical_volume)

            # Spread assessment (tighter spreads better)
            max_acceptable_spread = 0.0005  # 0.05%
            spread_score = max(0.0, 1.0 - (bid_ask_spread / max_acceptable_spread))

            # Technical regime assessment
            trend_strength = technical_indicators.get("trend_strength", 0.5)
            momentum = technical_indicators.get("momentum", 0.0)

            technical_score = (abs(trend_strength) + abs(momentum)) / 2.0

            # Combine regime scores
            regime_score = (
                volatility_score * 0.3
                + volume_score * 0.2
                + spread_score * 0.2
                + technical_score * 0.3
            )

            return max(0.0, min(1.0, regime_score))

        except Exception as e:
            self.logger.error(f"Error scoring market regime: {e}")
            return 0.5

    def _score_volatility_context(
        self, market_data: Dict[str, Any], signal_strength: float
    ) -> float:
        """Score appropriateness of signal strength for current volatility."""
        try:
            volatility = market_data.get("volatility", 0.02)

            # Strong signals should match high volatility periods
            signal_magnitude = abs(signal_strength)

            if volatility > 0.03:  # High volatility
                # Reward strong signals in high volatility
                return min(1.0, signal_magnitude * 1.5)
            elif volatility < 0.01:  # Low volatility
                # Penalize very strong signals in low volatility
                if signal_magnitude > 0.7:
                    return 0.3
                else:
                    return 0.8
            else:  # Medium volatility
                # Standard scoring
                return 0.7 + 0.3 * signal_magnitude

        except Exception as e:
            self.logger.error(f"Error scoring volatility context: {e}")
            return 0.6

    def _score_liquidity_context(
        self, volume_profile: Optional[Dict[str, Any]], market_data: Dict[str, Any]
    ) -> float:
        """Score liquidity context for trading signal."""
        try:
            if volume_profile is None:
                # Use basic volume from market data
                volume = market_data.get("volume", 1000000)
                typical_volume = 10000000
                return min(1.0, volume / typical_volume)

            # Detailed volume profile analysis
            current_volume = volume_profile.get("current_volume", 1000000)
            average_volume = volume_profile.get("average_volume", 1000000)
            volume_trend = volume_profile.get("volume_trend", 0.0)

            # Volume ratio score
            volume_ratio = current_volume / max(1, average_volume)
            volume_score = min(1.0, volume_ratio)

            # Volume trend score (increasing volume is positive)
            trend_score = max(0.0, min(1.0, 0.5 + volume_trend))

            # Combined liquidity score
            liquidity_score = volume_score * 0.7 + trend_score * 0.3

            return max(0.0, min(1.0, liquidity_score))

        except Exception as e:
            self.logger.error(f"Error scoring liquidity context: {e}")
            return 0.6

    def _score_signal_data_quality(
        self, market_data: Dict[str, Any], technical_indicators: Dict[str, float]
    ) -> float:
        """Score data quality for trading signal."""
        try:
            # Check completeness of market data
            required_fields = ["open", "high", "low", "close", "volume"]
            available_fields = sum(
                1 for field in required_fields if field in market_data
            )
            completeness_score = available_fields / len(required_fields)

            # Check technical indicators availability
            indicator_count = len(technical_indicators)
            indicator_score = min(1.0, indicator_count / 10.0)  # Expect ~10 indicators

            # Check for reasonable values
            reasonableness_score = 1.0
            if "close" in market_data:
                close_price = market_data["close"]
                if close_price <= 0 or close_price > 1000000:  # Unreasonable price
                    reasonableness_score *= 0.3

            # Combined quality score
            quality_score = (
                completeness_score * 0.5
                + indicator_score * 0.3
                + reasonableness_score * 0.2
            )

            return max(0.0, min(1.0, quality_score))

        except Exception as e:
            self.logger.error(f"Error scoring signal data quality: {e}")
            return 0.5

    def _score_signal_historical_performance(
        self, symbol: str, timeframe: str, signal_magnitude: float
    ) -> float:
        """Score historical performance for similar signals."""
        try:
            signal_key = f"{symbol}_{timeframe}"

            if signal_key in self.performance_history:
                similar_signals = [
                    p
                    for p in self.performance_history[signal_key]
                    if abs(p.get("signal_magnitude", 0) - signal_magnitude) < 0.2
                ]

                if similar_signals:
                    avg_success_rate = np.mean([p["success"] for p in similar_signals])
                    return max(0.0, min(1.0, avg_success_rate))

            # Default score based on signal magnitude
            # Moderate signals tend to be more reliable
            if 0.3 <= signal_magnitude <= 0.7:
                return 0.7
            elif signal_magnitude < 0.3:
                return 0.5  # Weak signals
            else:
                return 0.6  # Very strong signals (potentially overconfident)

        except Exception as e:
            self.logger.error(f"Error scoring signal historical performance: {e}")
            return 0.6

    def _calculate_ensemble_agreement(self, confidence_scores: List[float]) -> float:
        """Calculate agreement score for ensemble predictions."""
        try:
            if not confidence_scores:
                return 0.0

            confidence_array = np.array(confidence_scores)

            # Standard deviation approach: lower deviation = higher agreement
            if len(confidence_scores) == 1:
                return 1.0

            std_dev = np.std(confidence_array)
            max_possible_std = 0.5  # Maximum expected standard deviation

            agreement = max(0.0, 1.0 - (std_dev / max_possible_std))
            return min(1.0, agreement)

        except Exception as e:
            self.logger.error(f"Error calculating ensemble agreement: {e}")
            return 0.5

    def _calculate_weighted_confidence(
        self, component_scores: Dict[ConfidenceComponent, float]
    ) -> float:
        """Calculate overall weighted confidence score."""
        try:
            total_score = 0.0
            total_weight = 0.0

            for component, score in component_scores.items():
                if component in self.component_weights:
                    weight = self.component_weights[component]
                    total_score += score * weight
                    total_weight += weight

            # Normalize by actual total weight (in case some components missing)
            if total_weight > 0:
                weighted_confidence = total_score / total_weight
            else:
                weighted_confidence = 0.5

            return max(0.0, min(1.0, weighted_confidence))

        except Exception as e:
            self.logger.error(f"Error calculating weighted confidence: {e}")
            return 0.5

    def update_performance_history(
        self,
        model_or_signal_id: str,
        prediction_confidence: float,
        actual_outcome: float,
        outcome_type: str = "accuracy",
    ) -> None:
        """
        Update historical performance tracking.

        Args:
            model_or_signal_id: Identifier for model or signal type
            prediction_confidence: Original prediction confidence
            actual_outcome: Actual result (accuracy, profit, etc.)
            outcome_type: Type of outcome measure
        """
        try:
            if model_or_signal_id not in self.performance_history:
                self.performance_history[model_or_signal_id] = []

            performance_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "prediction_confidence": prediction_confidence,
                "actual_outcome": actual_outcome,
                "outcome_type": outcome_type,
                "accuracy": (
                    actual_outcome
                    if outcome_type == "accuracy"
                    else float(actual_outcome > 0)
                ),
                "success": (
                    actual_outcome > 0.5
                    if outcome_type == "accuracy"
                    else actual_outcome > 0
                ),
            }

            self.performance_history[model_or_signal_id].append(performance_record)

            # Keep only last 1000 records per model/signal
            if len(self.performance_history[model_or_signal_id]) > 1000:
                self.performance_history[model_or_signal_id] = self.performance_history[
                    model_or_signal_id
                ][-1000:]

            self.logger.debug(
                f"Updated performance history for {model_or_signal_id}: {actual_outcome}"
            )

        except Exception as e:
            self.logger.error(f"Error updating performance history: {e}")

    def get_confidence_threshold_for_risk_level(self, risk_level: str) -> float:
        """
        Get minimum confidence threshold for given risk level.

        Args:
            risk_level: Risk level ("conservative", "moderate", "aggressive")

        Returns:
            Minimum confidence threshold
        """
        thresholds = {
            "conservative": 0.8,  # High confidence required
            "moderate": 0.6,  # Medium confidence acceptable
            "aggressive": 0.4,  # Lower confidence acceptable
        }

        return thresholds.get(risk_level, 0.6)

    def get_position_size_multiplier(self, confidence_score: ConfidenceScore) -> float:
        """
        Get position size multiplier based on confidence score.

        Args:
            confidence_score: Confidence score for prediction

        Returns:
            Position size multiplier (0.0 - 1.0)
        """
        confidence = confidence_score.overall_confidence

        if confidence >= 0.9:
            return 1.0  # Full position size
        elif confidence >= 0.8:
            return 0.8  # 80% position size
        elif confidence >= 0.6:
            return 0.5  # 50% position size
        elif confidence >= 0.4:
            return 0.2  # 20% position size
        else:
            return 0.0  # No position

    def should_reject_signal(
        self, confidence_score: ConfidenceScore, risk_level: str = "moderate"
    ) -> bool:
        """
        Determine if signal should be rejected based on confidence.

        Args:
            confidence_score: Confidence score for signal
            risk_level: Current risk tolerance level

        Returns:
            True if signal should be rejected
        """
        threshold = self.get_confidence_threshold_for_risk_level(risk_level)
        return confidence_score.overall_confidence < threshold

    def get_system_health_metrics(self) -> Dict[str, Any]:
        """Get overall confidence scoring system health metrics."""
        try:
            total_predictions = sum(
                len(history) for history in self.performance_history.values()
            )

            if total_predictions == 0:
                return {
                    "total_predictions_scored": 0,
                    "average_confidence_accuracy": 0.0,
                    "models_tracked": 0,
                    "confidence_calibration": 0.0,
                    "system_healthy": True,
                }

            # Calculate confidence calibration (how well confidence predicts accuracy)
            all_records = []
            for history in self.performance_history.values():
                all_records.extend(history)

            if all_records:
                confidences = [r["prediction_confidence"] for r in all_records]
                accuracies = [r["accuracy"] for r in all_records]

                # Simple calibration measure: correlation between confidence and accuracy
                calibration = (
                    np.corrcoef(confidences, accuracies)[0, 1]
                    if len(confidences) > 1
                    else 0.0
                )
                avg_accuracy = np.mean(accuracies)
            else:
                calibration = 0.0
                avg_accuracy = 0.0

            return {
                "total_predictions_scored": total_predictions,
                "average_confidence_accuracy": avg_accuracy,
                "models_tracked": len(self.performance_history),
                "confidence_calibration": calibration,
                "system_healthy": calibration > 0.3 and avg_accuracy > 0.5,
            }

        except Exception as e:
            self.logger.error(f"Error getting system health metrics: {e}")
            return {
                "total_predictions_scored": 0,
                "system_healthy": False,
                "error": str(e),
            }
