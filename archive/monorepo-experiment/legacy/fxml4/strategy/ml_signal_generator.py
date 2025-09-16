"""Machine learning-based signal generator.

This module provides a signal generator that uses ML models
to generate trading signals.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.config import get_config
from fxml4.ml.features import create_technical_features
from fxml4.strategy.integrated_strategy import Signal, SignalGenerator, SignalSource, SignalType

logger = logging.getLogger(__name__)


class MLSignalGenerator(SignalGenerator):
    """Signal generator using machine learning models."""
    
    def __init__(
        self,
        model: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the ML signal generator.
        
        Args:
            model: ML model for generating signals.
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.model = model
        self.threshold = self.config.get("threshold", 0.6)
        self.probability_mode = self.config.get("probability_mode", True)
        self.feature_columns = self.config.get("feature_columns", None)
        self.signal_cooldown = self.config.get("signal_cooldown", 0)
        self.last_signal_time: Dict[SignalType, Optional[pd.Timestamp]] = {
            SignalType.ENTRY_LONG: None,
            SignalType.ENTRY_SHORT: None,
            SignalType.EXIT_LONG: None,
            SignalType.EXIT_SHORT: None,
        }
        
        # Set up feature engineering
        self.feature_lookback = self.config.get("feature_lookback", 100)
        self.use_technical_features = self.config.get("use_technical_features", True)
        self.tech_indicators = self.config.get("technical_indicators", [
            "sma", "ema", "rsi", "macd", "bollinger", "atr", "adx"
        ])
        self.custom_indicators = self.config.get("custom_indicators", [])
        
        logger.info("Initialized ML signal generator using model: %s", self.model.__class__.__name__)
    
    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for model prediction.
        
        Args:
            data: Market data.
            
        Returns:
            DataFrame with prepared features.
        """
        features = data.copy()
        
        # Generate technical indicators if requested
        if self.use_technical_features:
            features = create_technical_features(
                features,
                indicators=self.tech_indicators
            )
        
        # Drop rows with NaN values
        features = features.dropna()
        
        # Use only specified feature columns if provided
        if self.feature_columns:
            features = features[self.feature_columns]
        
        return features
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> List[Signal]:
        """Generate trading signals using ML model.
        
        Args:
            data: Market data.
            **kwargs: Additional arguments.
            
        Returns:
            List of generated signals.
        """
        signals = []
        
        # Extract metadata
        symbol = kwargs.get("symbol", data.get("symbol", ["unknown"])[0] 
                             if "symbol" in data.columns else "unknown")
        timeframe = kwargs.get("timeframe", data.get("timeframe", ["unknown"])[0] 
                               if "timeframe" in data.columns else "unknown")
        
        # Prepare features for the model
        features = self.prepare_features(data)
        
        if len(features) == 0:
            logger.warning("No valid features after preparation")
            return signals
        
        # Get the latest timestamp
        latest_timestamp = features.index[-1] if isinstance(features.index, pd.DatetimeIndex) else pd.Timestamp.now()
        
        try:
            # Make prediction with model
            if self.probability_mode:
                predictions = self.model.predict_proba(features.iloc[[-1]])
                
                # Handle different model outputs
                if isinstance(predictions, list) and len(predictions) > 1:
                    # Multi-class model with separate probabilities for each class
                    probabilities = predictions[1]  # Positive class probability
                else:
                    # Binary model
                    probabilities = predictions[:, 1] if predictions.shape[1] > 1 else predictions
                
                probability = float(probabilities[0])
            else:
                # Using raw model output
                prediction = self.model.predict(features.iloc[[-1]])
                probability = float(prediction[0])
            
            # Convert to signal strength
            signal_strength = probability
            
            # Check if signal is strong enough
            if signal_strength >= self.threshold:
                signal_type = SignalType.ENTRY_LONG
                
                # Check cooldown period
                if (self.signal_cooldown > 0 and 
                    self.last_signal_time[signal_type] is not None and 
                    (latest_timestamp - self.last_signal_time[signal_type]).total_seconds() < self.signal_cooldown):
                    logger.debug("Signal suppressed due to cooldown period")
                    return signals
                
                # Create signal
                signal = Signal(
                    signal_type=signal_type,
                    strength=signal_strength,
                    source=SignalSource.ML,
                    timestamp=latest_timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "model_name": self.model.__class__.__name__,
                        "raw_probability": probability,
                        "features_used": list(features.columns),
                    },
                )
                signals.append(signal)
                
                # Update last signal time
                self.last_signal_time[signal_type] = latest_timestamp
            
            # Check for short entry signal
            if signal_strength <= (1 - self.threshold):
                signal_type = SignalType.ENTRY_SHORT
                short_strength = 1 - signal_strength
                
                # Check cooldown period
                if (self.signal_cooldown > 0 and 
                    self.last_signal_time[signal_type] is not None and 
                    (latest_timestamp - self.last_signal_time[signal_type]).total_seconds() < self.signal_cooldown):
                    logger.debug("Signal suppressed due to cooldown period")
                    return signals
                
                # Create signal
                signal = Signal(
                    signal_type=signal_type,
                    strength=short_strength,
                    source=SignalSource.ML,
                    timestamp=latest_timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "model_name": self.model.__class__.__name__,
                        "raw_probability": probability,
                        "features_used": list(features.columns),
                    },
                )
                signals.append(signal)
                
                # Update last signal time
                self.last_signal_time[signal_type] = latest_timestamp
            
        except Exception as e:
            logger.exception("Error generating ML signals: %s", e)
        
        return signals


class EnsembleMLSignalGenerator(SignalGenerator):
    """Signal generator using ensemble of ML models."""
    
    def __init__(
        self,
        models: List[Any],
        weights: Optional[List[float]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the ensemble ML signal generator.
        
        Args:
            models: List of ML models.
            weights: List of weights for each model.
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.models = models
        
        # Initialize weights
        if weights is None:
            self.weights = [1.0 / len(models)] * len(models)
        else:
            if len(weights) != len(models):
                raise ValueError("Number of weights must match number of models")
            weight_sum = sum(weights)
            self.weights = [w / weight_sum for w in weights]
        
        # Create individual signal generators for each model
        self.generators = []
        for i, model in enumerate(models):
            model_config = self.config.copy()
            model_config["name"] = f"Model_{i}"
            generator = MLSignalGenerator(model, model_config)
            self.generators.append(generator)
        
        self.threshold = self.config.get("threshold", 0.6)
        
        logger.info("Initialized ensemble ML signal generator with %d models", len(models))
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> List[Signal]:
        """Generate trading signals using ensemble of ML models.
        
        Args:
            data: Market data.
            **kwargs: Additional arguments.
            
        Returns:
            List of generated signals.
        """
        all_signals = []
        
        # Generate signals from each model
        for generator in self.generators:
            signals = generator.generate_signals(data, **kwargs)
            all_signals.extend(signals)
        
        # Combine signals by type
        signals_by_type = {}
        for signal in all_signals:
            if signal.signal_type not in signals_by_type:
                signals_by_type[signal.signal_type] = []
            signals_by_type[signal.signal_type].append(signal)
        
        # Create ensemble signals for each type
        final_signals = []
        
        for signal_type, signals in signals_by_type.items():
            if not signals:
                continue
            
            # Calculate ensemble strength
            ensemble_strength = 0.0
            model_contributions = []
            
            for signal in signals:
                model_idx = int(signal.metadata.get("model_name", "Model_0").split("_")[1])
                if model_idx < len(self.weights):
                    weight = self.weights[model_idx]
                else:
                    weight = 1.0 / len(signals)
                
                contribution = signal.strength * weight
                ensemble_strength += contribution
                model_contributions.append({
                    "model": signal.metadata.get("model_name", "Unknown"),
                    "strength": signal.strength,
                    "weight": weight,
                    "contribution": contribution,
                })
            
            # Check if ensemble signal is strong enough
            if ensemble_strength >= self.threshold:
                # Create ensemble signal
                ensemble_signal = Signal(
                    signal_type=signal_type,
                    strength=ensemble_strength,
                    source=SignalSource.ML,
                    timestamp=signals[0].timestamp,
                    symbol=signals[0].symbol,
                    timeframe=signals[0].timeframe,
                    metadata={
                        "model_name": "Ensemble",
                        "model_contributions": model_contributions,
                        "component_signals": [s.to_dict() for s in signals],
                    },
                )
                final_signals.append(ensemble_signal)
        
        return final_signals