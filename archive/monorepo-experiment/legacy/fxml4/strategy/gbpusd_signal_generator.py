"""GBP/USD signal generator.

This module provides a specialized signal generator for GBP/USD trading
using ML models optimized for this currency pair.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml4.config import get_config
from fxml4.ml.gbpusd_model import GBPUSDModel
from fxml4.strategy.integrated_strategy import Signal, SignalGenerator, SignalSource, SignalType

logger = logging.getLogger(__name__)


class GBPUSDSignalGenerator(SignalGenerator):
    """Signal generator for GBP/USD trading."""
    
    def __init__(
        self,
        model: Optional[GBPUSDModel] = None,
        model_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the GBP/USD signal generator.
        
        Args:
            model: Pre-loaded GBP/USD model
            model_path: Path to model to load (name and directory)
            config: Configuration dictionary
        """
        super().__init__(config)
        
        # Load model if provided
        if model is not None:
            self.model = model
        elif model_path is not None:
            model_name, directory = model_path
            self.model = GBPUSDModel.load(model_name, directory)
        else:
            # Try to load default model
            try:
                model_config = get_config("ml.gbpusd_model", {})
                model_name = model_config.get("name", "gbpusd_rf_model")
                model_dir = model_config.get("directory", "models")
                self.model = GBPUSDModel.load(model_name, model_dir)
            except Exception as e:
                logger.warning(f"Could not load default GBP/USD model: {e}")
                self.model = None
        
        # Configuration
        self.threshold = self.config.get("threshold", 0.65)
        self.signal_cooldown = self.config.get("signal_cooldown", 4 * 3600)  # 4 hours in seconds
        self.probability_mode = self.config.get("probability_mode", True)
        self.last_signal_time = {}
        
        # Confirm model is loaded
        if self.model is not None:
            logger.info(f"Initialized GBP/USD signal generator with model: {self.model.name}")
        else:
            logger.warning("GBP/USD signal generator initialized without a model")
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs: Any
    ) -> List[Signal]:
        """Generate trading signals for GBP/USD.
        
        Args:
            data: Market data
            **kwargs: Additional arguments
            
        Returns:
            List of generated signals
        """
        if self.model is None:
            logger.warning("No model available for signal generation")
            return []
        
        signals = []
        
        try:
            # Extract metadata
            symbol = kwargs.get("symbol", "GBPUSD")
            timeframe = kwargs.get("timeframe", "4h")
            
            # Get the latest timestamp
            if isinstance(data.index, pd.DatetimeIndex):
                latest_timestamp = data.index[-1]
            else:
                latest_timestamp = pd.Timestamp.now()
            
            # Prepare features
            features = self.model.prepare_features(
                data,
                target_horizon=12,  # 12 periods for 4h timeframe
                add_lag_features=True,
                create_target=False
            )
            
            if len(features) == 0:
                logger.warning("No valid features after preparation")
                return signals
            
            # Get latest features
            latest_features = features.iloc[[-1]]
            
            # Make prediction
            if self.probability_mode:
                probas = self.model.predict_proba(latest_features)
                prediction = np.argmax(probas[0])
                confidence = probas[0][prediction]
                
                # Map prediction to signal type (0 = neutral, 1 = bullish, 2 = bearish)
                if prediction == 1 and confidence >= self.threshold:
                    signal_type = SignalType.ENTRY_LONG
                    signal_strength = confidence
                elif prediction == 2 and confidence >= self.threshold:
                    signal_type = SignalType.ENTRY_SHORT
                    signal_strength = confidence
                else:
                    # No signal
                    return signals
            else:
                # Use raw prediction
                prediction = self.model.predict(latest_features)[0]
                
                # Map prediction to signal type
                if prediction == 1:
                    signal_type = SignalType.ENTRY_LONG
                    signal_strength = 0.8  # Default strength
                elif prediction == -1:
                    signal_type = SignalType.ENTRY_SHORT
                    signal_strength = 0.8  # Default strength
                else:
                    # No signal
                    return signals
            
            # Check cooldown period
            if signal_type in self.last_signal_time:
                last_time = self.last_signal_time[signal_type]
                time_diff = (latest_timestamp - last_time).total_seconds()
                
                if time_diff < self.signal_cooldown:
                    logger.debug(f"Signal suppressed due to cooldown period ({time_diff}s < {self.signal_cooldown}s)")
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
                    "model_name": self.model.name,
                    "raw_prediction": int(prediction),
                    "probability": float(confidence) if self.probability_mode else None,
                }
            )
            
            signals.append(signal)
            
            # Update last signal time
            self.last_signal_time[signal_type] = latest_timestamp
            
        except Exception as e:
            logger.exception(f"Error generating GBP/USD signals: {e}")
        
        return signals
    
    def backtest(
        self,
        data: pd.DataFrame,
        target_horizon: int = 12,
        **kwargs: Any
    ) -> pd.DataFrame:
        """Backtest the signal generator on historical data.
        
        Args:
            data: Historical market data
            target_horizon: Number of periods ahead for the target
            **kwargs: Additional arguments
            
        Returns:
            DataFrame with backtest results
        """
        if self.model is None:
            logger.warning("No model available for backtesting")
            return pd.DataFrame()
        
        try:
            # Prepare features with target
            features = self.model.prepare_features(
                data,
                target_horizon=target_horizon,
                add_lag_features=True,
                create_target=True
            )
            
            # Get target column
            target_col = f'target_{target_horizon}'
            
            # Make predictions on all data
            if self.probability_mode:
                probas = self.model.predict_proba(features.drop(columns=[target_col]))
                predictions = np.zeros(len(features))
                
                for i in range(len(probas)):
                    pred = np.argmax(probas[i])
                    conf = probas[i][pred]
                    
                    if pred == 1 and conf >= self.threshold:
                        predictions[i] = 1
                    elif pred == 2 and conf >= self.threshold:
                        predictions[i] = -1
            else:
                predictions = self.model.predict(features.drop(columns=[target_col]))
            
            # Create results DataFrame
            results = pd.DataFrame({
                'timestamp': features.index,
                'prediction': predictions,
                'actual': features[target_col],
                'close': features['close']
            })
            
            # Calculate forward returns
            results['forward_return'] = results['close'].shift(-target_horizon) / results['close'] - 1
            
            # Calculate signal returns
            results['signal_return'] = results['prediction'] * results['forward_return']
            
            # Calculate cumulative returns
            results['cum_return'] = (1 + results['signal_return'].fillna(0)).cumprod() - 1
            
            # Calculate drawdowns
            results['cum_max'] = results['cum_return'].cummax()
            results['drawdown'] = results['cum_return'] - results['cum_max']
            
            return results
            
        except Exception as e:
            logger.exception(f"Error in backtesting: {e}")
            return pd.DataFrame()


def create_ensemble_generator(
    model_paths: List[Tuple[str, str]],
    weights: Optional[List[float]] = None,
    config: Optional[Dict[str, Any]] = None
) -> 'GBPUSDEnsembleGenerator':
    """Create an ensemble signal generator from multiple models.
    
    Args:
        model_paths: List of (model_name, directory) tuples
        weights: Weights for each model
        config: Configuration dictionary
        
    Returns:
        Ensemble signal generator
    """
    # Load models
    models = []
    for model_name, directory in model_paths:
        try:
            model = GBPUSDModel.load(model_name, directory)
            models.append(model)
        except Exception as e:
            logger.warning(f"Could not load model {model_name}: {e}")
    
    # Create generators
    generators = []
    for model in models:
        model_config = config.copy() if config else {}
        model_config["name"] = model.name
        generator = GBPUSDSignalGenerator(model=model, config=model_config)
        generators.append(generator)
    
    # Create ensemble
    if weights is None:
        weights = [1.0] * len(generators)
    
    # Normalize weights
    weight_sum = sum(weights)
    weights = [w / weight_sum for w in weights]
    
    # Create ensemble generator
    ensemble_config = config.copy() if config else {}
    ensemble_config["generators"] = generators
    ensemble_config["weights"] = weights
    
    return GBPUSDEnsembleGenerator(
        generators=generators,
        weights=weights,
        config=ensemble_config
    )


class GBPUSDEnsembleGenerator(SignalGenerator):
    """Ensemble signal generator for GBP/USD trading."""
    
    def __init__(
        self,
        generators: List[GBPUSDSignalGenerator],
        weights: Optional[List[float]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the ensemble signal generator.
        
        Args:
            generators: List of individual signal generators
            weights: Weights for each generator
            config: Configuration dictionary
        """
        super().__init__(config)
        self.generators = generators
        
        # Set weights
        if weights is None:
            self.weights = [1.0 / len(generators)] * len(generators)
        else:
            if len(weights) != len(generators):
                raise ValueError("Number of weights must match number of generators")
            weight_sum = sum(weights)
            self.weights = [w / weight_sum for w in weights]
        
        # Configuration
        self.threshold = self.config.get("threshold", 0.7)
        
        logger.info(f"Initialized GBP/USD ensemble generator with {len(generators)} models")
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs: Any
    ) -> List[Signal]:
        """Generate trading signals using ensemble of models.
        
        Args:
            data: Market data
            **kwargs: Additional arguments
            
        Returns:
            List of generated signals
        """
        all_signals = []
        
        # Generate signals from each generator
        for i, generator in enumerate(self.generators):
            signals = generator.generate_signals(data, **kwargs)
            
            # Add weight to metadata
            for signal in signals:
                signal.metadata["weight"] = self.weights[i]
            
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
            weighted_signals = []
            
            for signal in signals:
                weight = signal.metadata.get("weight", 1.0 / len(signals))
                contribution = signal.strength * weight
                ensemble_strength += contribution
                weighted_signals.append({
                    "model": signal.metadata.get("model_name", "Unknown"),
                    "strength": signal.strength,
                    "weight": weight,
                    "contribution": contribution,
                })
            
            # Check if ensemble signal is strong enough
            if ensemble_strength >= self.threshold:
                # Extract metadata
                symbol = kwargs.get("symbol", signals[0].symbol)
                timeframe = kwargs.get("timeframe", signals[0].timeframe)
                
                # Create ensemble signal
                ensemble_signal = Signal(
                    signal_type=signal_type,
                    strength=ensemble_strength,
                    source=SignalSource.ML,
                    timestamp=signals[0].timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "model_name": "GBP/USD Ensemble",
                        "weighted_signals": weighted_signals,
                    }
                )
                
                final_signals.append(ensemble_signal)
        
        return final_signals