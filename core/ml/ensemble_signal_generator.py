"""
Ensemble-based Signal Generator for FXML4

This module provides advanced signal generation using ensemble methods:
1. Multiple model consensus for robust signals
2. Confidence-weighted signal generation
3. Dynamic model selection based on market conditions
4. Signal aggregation and filtering
5. Real-time ensemble updating
"""

import logging
import warnings
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.ml.ensemble_models import DynamicEnsemble, StackingEnsemble, VotingEnsemble
from fxml4.ml.features import FeatureEngineering
from fxml4.ml.model_loader import ModelLoader

# FXML4 imports
from fxml4.ml.models import ClassicMLModel, EnsembleModel

logger = logging.getLogger(__name__)


class SignalConfig:
    """Configuration for signal generation."""

    def __init__(
        self,
        signal_threshold: float = 0.6,
        min_models_agree: int = 2,
        use_confidence_weighting: bool = True,
        confidence_threshold: float = 0.7,
        signal_decay_hours: int = 4,
        max_signal_age_hours: int = 24,
        use_kelly_sizing: bool = True,
        max_position_size: float = 0.1,
        min_position_size: float = 0.01,
    ):
        """
        Initialize signal configuration.

        Args:
            signal_threshold: Minimum probability for signal generation
            min_models_agree: Minimum number of models that must agree
            use_confidence_weighting: Whether to weight by model confidence
            confidence_threshold: Minimum confidence for signal
            signal_decay_hours: Hours before signal strength starts decaying
            max_signal_age_hours: Maximum age for valid signal
            use_kelly_sizing: Whether to use Kelly criterion for position sizing
            max_position_size: Maximum position size as fraction of capital
            min_position_size: Minimum position size as fraction of capital
        """
        self.signal_threshold = signal_threshold
        self.min_models_agree = min_models_agree
        self.use_confidence_weighting = use_confidence_weighting
        self.confidence_threshold = confidence_threshold
        self.signal_decay_hours = signal_decay_hours
        self.max_signal_age_hours = max_signal_age_hours
        self.use_kelly_sizing = use_kelly_sizing
        self.max_position_size = max_position_size
        self.min_position_size = min_position_size


class EnsembleSignalGenerator:
    """Generate trading signals using ensemble of models."""

    def __init__(
        self,
        models: List[Union[ClassicMLModel, EnsembleModel]],
        config: Optional[SignalConfig] = None,
        feature_engineering: Optional[FeatureEngineering] = None,
        model_weights: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize ensemble signal generator.

        Args:
            models: List of models to use in ensemble
            config: Signal configuration
            feature_engineering: Feature engineering instance
            model_weights: Optional weights for each model
        """
        self.models = models
        self.config = config or SignalConfig()
        self.feature_engineering = feature_engineering

        # Set model weights
        if model_weights is None:
            # Equal weights by default
            self.model_weights = {model.name: 1.0 / len(models) for model in models}
        else:
            # Normalize provided weights
            total_weight = sum(model_weights.values())
            self.model_weights = {
                name: weight / total_weight for name, weight in model_weights.items()
            }

        # Signal history for filtering and analysis
        self.signal_history = deque(maxlen=1000)

        # Performance tracking for dynamic weighting
        self.model_performance = {
            model.name: {"correct": 0, "total": 0, "recent_accuracy": deque(maxlen=100)}
            for model in models
        }

        # Market regime detection
        self.current_regime = "normal"
        self.regime_models = {}  # Models that perform best in each regime

    def generate_signal(
        self,
        features: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Generate trading signal from ensemble.

        Args:
            features: Feature DataFrame
            market_data: Optional market data for context
            timestamp: Signal timestamp

        Returns:
            Dictionary with signal information
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Get predictions from all models
        predictions = {}
        probabilities = {}
        confidences = {}

        for model in self.models:
            try:
                # Get prediction
                pred = model.predict(features)
                predictions[model.name] = pred[0] if len(pred) > 0 else 0

                # Get probabilities if available
                if hasattr(model, "predict_proba"):
                    proba = model.predict_proba(features)
                    probabilities[model.name] = (
                        proba[0] if len(proba) > 0 else [0.33, 0.34, 0.33]
                    )

                    # Calculate confidence as max probability
                    confidences[model.name] = (
                        np.max(proba[0]) if len(proba) > 0 else 0.5
                    )
                else:
                    # Default confidence
                    confidences[model.name] = 0.7

            except Exception as e:
                logger.warning(f"Error getting prediction from {model.name}: {str(e)}")
                predictions[model.name] = 0
                confidences[model.name] = 0.0

        # Aggregate predictions
        signal_info = self._aggregate_predictions(
            predictions, probabilities, confidences, timestamp
        )

        # Apply market regime adjustments
        if market_data is not None:
            signal_info = self._apply_regime_adjustments(signal_info, market_data)

        # Calculate position size
        if signal_info["signal"] != 0:
            signal_info["position_size"] = self._calculate_position_size(
                signal_info, market_data
            )
        else:
            signal_info["position_size"] = 0.0

        # Store in history
        self.signal_history.append(signal_info)

        # Log signal
        logger.info(
            f"Generated signal: {signal_info['signal']} "
            f"(confidence: {signal_info['confidence']:.2f}, "
            f"strength: {signal_info['signal_strength']:.2f})"
        )

        return signal_info

    def _aggregate_predictions(
        self,
        predictions: Dict[str, int],
        probabilities: Dict[str, np.ndarray],
        confidences: Dict[str, float],
        timestamp: datetime,
    ) -> Dict[str, Any]:
        """Aggregate predictions from multiple models."""
        # Count votes for each class
        vote_counts = {-1: 0, 0: 0, 1: 0}
        weighted_votes = {-1: 0.0, 0: 0.0, 1: 0.0}

        # Aggregate predictions
        for model_name, pred in predictions.items():
            vote_counts[pred] += 1

            # Weight by confidence if enabled
            if self.config.use_confidence_weighting:
                weight = self.model_weights.get(model_name, 1.0) * confidences.get(
                    model_name, 1.0
                )
                weighted_votes[pred] += weight

        # Determine signal
        if self.config.use_confidence_weighting:
            # Use weighted votes
            signal = max(weighted_votes, key=weighted_votes.get)
            signal_strength = weighted_votes[signal] / sum(weighted_votes.values())
        else:
            # Use simple majority
            signal = max(vote_counts, key=vote_counts.get)
            signal_strength = vote_counts[signal] / len(predictions)

        # Check if enough models agree
        models_agree = vote_counts[signal]
        if models_agree < self.config.min_models_agree:
            signal = 0  # No signal
            signal_strength = 0.0

        # Calculate overall confidence
        if probabilities:
            # Average probability for the chosen signal
            avg_probabilities = []
            for model_name, proba in probabilities.items():
                if len(proba) > 0:
                    # Map signal to probability index
                    if signal == -1:
                        prob_idx = 0
                    elif signal == 0:
                        prob_idx = 1
                    else:  # signal == 1
                        prob_idx = 2 if len(proba) > 2 else 1

                    if prob_idx < len(proba):
                        avg_probabilities.append(proba[prob_idx])

            confidence = np.mean(avg_probabilities) if avg_probabilities else 0.5
        else:
            confidence = np.mean(list(confidences.values()))

        # Apply thresholds
        if signal_strength < self.config.signal_threshold:
            signal = 0
        if confidence < self.config.confidence_threshold:
            signal = 0

        return {
            "signal": signal,
            "signal_strength": signal_strength,
            "confidence": confidence,
            "timestamp": timestamp,
            "predictions": predictions,
            "confidences": confidences,
            "vote_counts": vote_counts,
            "weighted_votes": weighted_votes,
            "models_agree": models_agree,
        }

    def _apply_regime_adjustments(
        self, signal_info: Dict[str, Any], market_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Apply adjustments based on market regime."""
        # Detect current market regime
        regime = self._detect_market_regime(market_data)
        signal_info["market_regime"] = regime

        # Adjust signal based on regime
        if regime == "high_volatility":
            # Reduce signal strength in high volatility
            signal_info["signal_strength"] *= 0.7
            signal_info["confidence"] *= 0.8
        elif regime == "trending":
            # Increase confidence in trending markets
            if signal_info["signal"] != 0:
                signal_info["confidence"] = min(1.0, signal_info["confidence"] * 1.2)
        elif regime == "ranging":
            # Reduce signals in ranging markets
            if abs(signal_info["signal"]) == 1:
                signal_info["signal_strength"] *= 0.8

        # Use regime-specific models if available
        if regime in self.regime_models:
            regime_model_names = self.regime_models[regime]
            # Boost weights for models that perform well in this regime
            for model_name in regime_model_names:
                if model_name in signal_info["predictions"]:
                    pred = signal_info["predictions"][model_name]
                    if pred == signal_info["signal"]:
                        signal_info["confidence"] = min(
                            1.0, signal_info["confidence"] * 1.1
                        )

        return signal_info

    def _detect_market_regime(self, market_data: pd.DataFrame) -> str:
        """Detect current market regime."""
        if market_data is None or len(market_data) < 20:
            return "normal"

        # Calculate volatility
        returns = market_data["close"].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252)  # Annualized

        # Calculate trend strength
        sma_20 = market_data["close"].rolling(20).mean()
        sma_50 = (
            market_data["close"].rolling(50).mean()
            if len(market_data) >= 50
            else sma_20
        )

        trend_strength = abs(sma_20.iloc[-1] - sma_50.iloc[-1]) / sma_50.iloc[-1]

        # Determine regime
        if volatility > 0.3:  # 30% annualized volatility
            return "high_volatility"
        elif trend_strength > 0.02:  # 2% difference between MAs
            return "trending"
        else:
            return "ranging"

    def _calculate_position_size(
        self, signal_info: Dict[str, Any], market_data: Optional[pd.DataFrame] = None
    ) -> float:
        """Calculate position size based on signal and market conditions."""
        base_size = self.config.max_position_size

        # Adjust by signal strength
        size = base_size * signal_info["signal_strength"]

        # Adjust by confidence
        size *= signal_info["confidence"]

        # Kelly criterion if enabled
        if self.config.use_kelly_sizing and market_data is not None:
            kelly_size = self._calculate_kelly_size(signal_info, market_data)
            size = min(size, kelly_size)

        # Apply limits
        size = max(
            self.config.min_position_size, min(self.config.max_position_size, size)
        )

        return size

    def _calculate_kelly_size(
        self, signal_info: Dict[str, Any], market_data: pd.DataFrame
    ) -> float:
        """Calculate position size using Kelly criterion."""
        # Estimate win probability from confidence
        win_prob = signal_info["confidence"]

        # Estimate win/loss ratio from recent market data
        if len(market_data) < 20:
            return self.config.max_position_size * 0.5

        returns = market_data["close"].pct_change().dropna()
        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]

        if len(positive_returns) > 0 and len(negative_returns) > 0:
            avg_win = positive_returns.mean()
            avg_loss = abs(negative_returns.mean())
            win_loss_ratio = avg_win / avg_loss
        else:
            win_loss_ratio = 1.5  # Default

        # Kelly formula: f = (p * b - q) / b
        # where p = win probability, q = loss probability, b = win/loss ratio
        kelly_fraction = (win_prob * win_loss_ratio - (1 - win_prob)) / win_loss_ratio

        # Apply Kelly fraction with safety factor
        kelly_fraction = max(0, kelly_fraction * 0.25)  # Use 1/4 Kelly

        return min(kelly_fraction, self.config.max_position_size)

    def update_performance(
        self, signal_id: str, actual_outcome: int, actual_return: float
    ) -> None:
        """
        Update model performance based on actual outcomes.

        Args:
            signal_id: ID of the signal
            actual_outcome: Actual market direction (-1, 0, 1)
            actual_return: Actual return achieved
        """
        # Find signal in history
        signal_info = None
        for sig in self.signal_history:
            if sig.get("id") == signal_id:
                signal_info = sig
                break

        if signal_info is None:
            logger.warning(f"Signal {signal_id} not found in history")
            return

        # Update performance for each model
        for model_name, prediction in signal_info["predictions"].items():
            if model_name in self.model_performance:
                perf = self.model_performance[model_name]

                # Update counts
                perf["total"] += 1
                if prediction == actual_outcome:
                    perf["correct"] += 1

                # Update recent accuracy
                is_correct = prediction == actual_outcome
                perf["recent_accuracy"].append(is_correct)

                # Calculate current accuracy
                if perf["total"] > 0:
                    overall_accuracy = perf["correct"] / perf["total"]
                    recent_accuracy = np.mean(list(perf["recent_accuracy"]))

                    # Update model weight based on performance
                    if len(perf["recent_accuracy"]) >= 20:
                        # Blend overall and recent accuracy
                        blended_accuracy = (
                            0.3 * overall_accuracy + 0.7 * recent_accuracy
                        )

                        # Adjust weight (keep it normalized later)
                        self.model_weights[model_name] = blended_accuracy

        # Normalize weights
        total_weight = sum(self.model_weights.values())
        if total_weight > 0:
            self.model_weights = {
                name: weight / total_weight
                for name, weight in self.model_weights.items()
            }

    def get_active_signals(
        self, current_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get currently active signals.

        Args:
            current_time: Current time for age calculation

        Returns:
            List of active signals
        """
        if current_time is None:
            current_time = datetime.now()

        active_signals = []

        for signal in self.signal_history:
            # Calculate age
            age = current_time - signal["timestamp"]
            age_hours = age.total_seconds() / 3600

            # Skip if too old
            if age_hours > self.config.max_signal_age_hours:
                continue

            # Skip if no signal
            if signal["signal"] == 0:
                continue

            # Apply decay if needed
            if age_hours > self.config.signal_decay_hours:
                decay_factor = 1.0 - (age_hours - self.config.signal_decay_hours) / (
                    self.config.max_signal_age_hours - self.config.signal_decay_hours
                )
                signal["signal_strength"] *= decay_factor
                signal["confidence"] *= decay_factor

            active_signals.append(signal)

        return active_signals

    def add_model(
        self, model: Union[ClassicMLModel, EnsembleModel], weight: float = 1.0
    ) -> None:
        """Add a new model to the ensemble."""
        self.models.append(model)
        self.model_weights[model.name] = weight

        # Normalize weights
        total_weight = sum(self.model_weights.values())
        self.model_weights = {
            name: w / total_weight for name, w in self.model_weights.items()
        }

        # Initialize performance tracking
        self.model_performance[model.name] = {
            "correct": 0,
            "total": 0,
            "recent_accuracy": deque(maxlen=100),
        }

        logger.info(f"Added model {model.name} to ensemble with weight {weight}")

    def remove_model(self, model_name: str) -> None:
        """Remove a model from the ensemble."""
        # Remove from models list
        self.models = [m for m in self.models if m.name != model_name]

        # Remove from weights
        if model_name in self.model_weights:
            del self.model_weights[model_name]

        # Remove from performance tracking
        if model_name in self.model_performance:
            del self.model_performance[model_name]

        # Normalize remaining weights
        total_weight = sum(self.model_weights.values())
        if total_weight > 0:
            self.model_weights = {
                name: w / total_weight for name, w in self.model_weights.items()
            }

        logger.info(f"Removed model {model_name} from ensemble")

    def get_model_performance_summary(self) -> pd.DataFrame:
        """Get summary of model performance."""
        summary_data = []

        for model_name, perf in self.model_performance.items():
            if perf["total"] > 0:
                overall_accuracy = perf["correct"] / perf["total"]
            else:
                overall_accuracy = 0.5

            recent_accuracy = (
                np.mean(list(perf["recent_accuracy"]))
                if perf["recent_accuracy"]
                else 0.5
            )

            summary_data.append(
                {
                    "model": model_name,
                    "weight": self.model_weights.get(model_name, 0.0),
                    "total_predictions": perf["total"],
                    "correct_predictions": perf["correct"],
                    "overall_accuracy": overall_accuracy,
                    "recent_accuracy": recent_accuracy,
                    "recent_samples": len(perf["recent_accuracy"]),
                }
            )

        return pd.DataFrame(summary_data).sort_values("weight", ascending=False)


class AdaptiveEnsembleSignalGenerator(EnsembleSignalGenerator):
    """
    Adaptive ensemble that dynamically adjusts to market conditions.
    """

    def __init__(
        self,
        model_loader: ModelLoader,
        initial_models: Optional[List[str]] = None,
        config: Optional[SignalConfig] = None,
        adaptation_interval_hours: int = 24,
        min_performance_threshold: float = 0.45,
    ):
        """
        Initialize adaptive ensemble signal generator.

        Args:
            model_loader: Model loader for dynamic model loading
            initial_models: Initial model names to load
            config: Signal configuration
            adaptation_interval_hours: Hours between adaptation cycles
            min_performance_threshold: Minimum accuracy to keep model
        """
        # Load initial models
        models = []
        if initial_models:
            for model_name in initial_models:
                try:
                    model = model_loader.load(model_name)
                    models.append(model)
                except Exception as e:
                    logger.warning(f"Failed to load model {model_name}: {str(e)}")

        super().__init__(models, config)

        self.model_loader = model_loader
        self.adaptation_interval_hours = adaptation_interval_hours
        self.min_performance_threshold = min_performance_threshold
        self.last_adaptation = datetime.now()

        # Track available models
        self.available_models = set(initial_models or [])
        self.inactive_models = set()

    def adapt_ensemble(self, force: bool = False) -> Dict[str, Any]:
        """
        Adapt ensemble based on performance.

        Args:
            force: Force adaptation regardless of interval

        Returns:
            Dictionary with adaptation results
        """
        current_time = datetime.now()
        time_since_adaptation = current_time - self.last_adaptation

        # Check if adaptation is needed
        if (
            not force
            and time_since_adaptation.total_seconds() / 3600
            < self.adaptation_interval_hours
        ):
            return {"adapted": False, "reason": "Too soon since last adaptation"}

        logger.info("Starting ensemble adaptation")

        adaptation_results = {
            "adapted": True,
            "removed_models": [],
            "added_models": [],
            "weight_changes": {},
        }

        # Evaluate current models
        performance_summary = self.get_model_performance_summary()

        # Remove underperforming models
        for _, row in performance_summary.iterrows():
            model_name = row["model"]
            recent_accuracy = row["recent_accuracy"]

            if (
                recent_accuracy < self.min_performance_threshold
                and row["recent_samples"] >= 20
            ):
                logger.info(
                    f"Removing underperforming model {model_name} (accuracy: {recent_accuracy:.2f})"
                )
                self.remove_model(model_name)
                self.inactive_models.add(model_name)
                adaptation_results["removed_models"].append(model_name)

        # Try to add new models if ensemble is small
        if len(self.models) < 5:
            # Look for models that might work better
            candidate_models = self.available_models - self.inactive_models
            candidate_models -= {m.name for m in self.models}  # Exclude current models

            for model_name in list(candidate_models)[:2]:  # Try up to 2 new models
                try:
                    model = self.model_loader.load(model_name)
                    self.add_model(model, weight=0.1)  # Start with low weight
                    adaptation_results["added_models"].append(model_name)
                    logger.info(f"Added model {model_name} to ensemble")
                except Exception as e:
                    logger.warning(f"Failed to add model {model_name}: {str(e)}")

        # Update weights based on performance
        if len(performance_summary) > 0:
            # Calculate new weights based on recent accuracy
            new_weights = {}
            for _, row in performance_summary.iterrows():
                model_name = row["model"]
                # Use combination of overall and recent accuracy
                combined_accuracy = (
                    0.3 * row["overall_accuracy"] + 0.7 * row["recent_accuracy"]
                )
                new_weights[model_name] = max(
                    0.05, combined_accuracy
                )  # Minimum weight of 5%

            # Normalize
            total_weight = sum(new_weights.values())
            for model_name in new_weights:
                old_weight = self.model_weights.get(model_name, 0)
                new_weight = new_weights[model_name] / total_weight

                if abs(new_weight - old_weight) > 0.05:
                    adaptation_results["weight_changes"][model_name] = {
                        "old": old_weight,
                        "new": new_weight,
                    }

                self.model_weights[model_name] = new_weight

        self.last_adaptation = current_time

        logger.info(
            f"Adaptation complete: {len(adaptation_results['removed_models'])} removed, "
            f"{len(adaptation_results['added_models'])} added"
        )

        return adaptation_results

    def register_available_model(self, model_name: str) -> None:
        """Register a model as available for the ensemble."""
        self.available_models.add(model_name)
        # Remove from inactive if it was there
        self.inactive_models.discard(model_name)


# Convenience function for creating ensemble signal generator
def create_ensemble_signal_generator(
    model_names: List[str],
    model_loader: Optional[ModelLoader] = None,
    config: Optional[SignalConfig] = None,
    adaptive: bool = False,
) -> Union[EnsembleSignalGenerator, AdaptiveEnsembleSignalGenerator]:
    """
    Create an ensemble signal generator.

    Args:
        model_names: List of model names to load
        model_loader: Model loader instance
        config: Signal configuration
        adaptive: Whether to create adaptive ensemble

    Returns:
        Ensemble signal generator instance
    """
    if model_loader is None:
        model_loader = ModelLoader()

    if adaptive:
        generator = AdaptiveEnsembleSignalGenerator(
            model_loader=model_loader, initial_models=model_names, config=config
        )
    else:
        # Load models
        models = []
        for model_name in model_names:
            try:
                model = model_loader.load(model_name)
                models.append(model)
            except Exception as e:
                logger.warning(f"Failed to load model {model_name}: {str(e)}")

        if not models:
            raise ValueError("No models could be loaded")

        generator = EnsembleSignalGenerator(models=models, config=config)

    return generator
