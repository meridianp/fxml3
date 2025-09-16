"""
Machine learning-based signal generation.
"""

from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import pandas as pd
import numpy as np

from fxml4_core.logging import get_logger
from fxml4_signals.base import Signal, SignalType, SignalSource
from fxml4_ml.models import MLModel, MLModelFactory

logger = get_logger(__name__)


class MLSignals(SignalSource):
    """Generate signals from ML model predictions."""
    
    def __init__(
        self,
        name: str = "ml",
        weight: float = 1.0,
        model: Optional[MLModel] = None,
        model_path: Optional[Union[str, Path]] = None,
        prediction_threshold: float = 0.6,
        feature_columns: Optional[List[str]] = None
    ):
        super().__init__(name, weight)
        self.model = model
        self.model_path = model_path
        self.prediction_threshold = prediction_threshold
        self.feature_columns = feature_columns
        
        # Load model if path provided
        if self.model_path and not self.model:
            self._load_model()
    
    def _load_model(self) -> None:
        """Load model from path."""
        try:
            # Determine model type from metadata or filename
            model_type = self._infer_model_type(self.model_path)
            self.model = MLModelFactory.create(model_type)
            self.model.load(self.model_path)
            
            # Get feature columns from model
            if self.model.feature_names:
                self.feature_columns = self.model.feature_names
            
            logger.info(f"Loaded {model_type} model from {self.model_path}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def _infer_model_type(self, path: Union[str, Path]) -> str:
        """Infer model type from path or metadata."""
        path = Path(path)
        
        # Try to infer from filename
        filename = path.stem.lower()
        for model_type in ["random_forest", "xgboost", "lightgbm", "logistic_regression"]:
            if model_type.replace("_", "") in filename:
                return model_type
        
        # Default to xgboost
        return "xgboost"
    
    def get_required_columns(self) -> List[str]:
        """Get required columns."""
        if self.feature_columns:
            return self.feature_columns
        
        # Default feature columns if not specified
        return [
            "open", "high", "low", "close", "volume",
            "sma_20", "sma_50", "rsi_14", "macd", "macd_signal",
            "bb_upper", "bb_middle", "bb_lower", "atr_14"
        ]
    
    def generate_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """Generate signals from ML predictions."""
        if self.model is None:
            logger.error("No model loaded for ML signal generation")
            return []
        
        signals = []
        
        # Prepare features
        features = self._prepare_features(data)
        if features.empty:
            return signals
        
        # Make predictions
        try:
            predictions = self.model.predict_proba(features)
            
            # Generate signals based on predictions
            for idx, proba in zip(features.index, predictions):
                signal = self._create_signal_from_prediction(
                    idx, proba, data.loc[idx], symbol
                )
                if signal:
                    signals.append(signal)
            
        except Exception as e:
            logger.error(f"Error generating ML signals: {e}")
        
        return signals
    
    def _prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for ML model."""
        # Select required columns
        available_cols = [col for col in self.get_required_columns() if col in data.columns]
        
        if not available_cols:
            logger.error("No required features available in data")
            return pd.DataFrame()
        
        features = data[available_cols].copy()
        
        # Handle missing values
        features = features.ffill().bfill()
        
        # Remove rows with any remaining NaN
        features = features.dropna()
        
        return features
    
    def _create_signal_from_prediction(
        self,
        timestamp: pd.Timestamp,
        probabilities: np.ndarray,
        row_data: pd.Series,
        symbol: str
    ) -> Optional[Signal]:
        """Create signal from model prediction."""
        # Assume 3 classes: 0=SELL, 1=HOLD, 2=BUY
        if len(probabilities) == 3:
            sell_prob = probabilities[0]
            hold_prob = probabilities[1]
            buy_prob = probabilities[2]
        elif len(probabilities) == 2:
            # Binary classification: 0=SELL, 1=BUY
            sell_prob = probabilities[0]
            buy_prob = probabilities[1]
            hold_prob = 0
        else:
            logger.error(f"Unexpected number of classes: {len(probabilities)}")
            return None
        
        # Determine signal type and confidence
        max_prob = max(sell_prob, hold_prob, buy_prob)
        
        if max_prob < self.prediction_threshold:
            return None  # No confident prediction
        
        if buy_prob == max_prob:
            signal_type = SignalType.BUY
            confidence = buy_prob
        elif sell_prob == max_prob:
            signal_type = SignalType.SELL
            confidence = sell_prob
        else:
            signal_type = SignalType.HOLD
            confidence = hold_prob
        
        # Don't generate HOLD signals
        if signal_type == SignalType.HOLD:
            return None
        
        return Signal(
            timestamp=timestamp,
            symbol=symbol,
            signal_type=signal_type,
            source=f"{self.name}_prediction",
            confidence=confidence,
            price=row_data['close'],
            metadata={
                "model_name": self.model.name,
                "buy_probability": float(buy_prob),
                "sell_probability": float(sell_prob),
                "hold_probability": float(hold_prob),
                "features_used": len(self.feature_columns) if self.feature_columns else 0
            }
        )


class EnsembleMLSignals(SignalSource):
    """Generate signals from ensemble of ML models."""
    
    def __init__(
        self,
        name: str = "ensemble_ml",
        weight: float = 1.0,
        models: Optional[List[MLModel]] = None,
        model_paths: Optional[List[Union[str, Path]]] = None,
        voting: str = "soft",
        min_agreement: float = 0.6
    ):
        super().__init__(name, weight)
        self.models = models or []
        self.model_paths = model_paths or []
        self.voting = voting
        self.min_agreement = min_agreement
        
        # Load models if paths provided
        if self.model_paths and not self.models:
            self._load_models()
    
    def _load_models(self) -> None:
        """Load all models from paths."""
        for path in self.model_paths:
            try:
                ml_signal = MLSignals(model_path=path)
                if ml_signal.model:
                    self.models.append(ml_signal.model)
            except Exception as e:
                logger.error(f"Failed to load model from {path}: {e}")
    
    def get_required_columns(self) -> List[str]:
        """Get required columns from all models."""
        all_columns = set()
        
        for model in self.models:
            if hasattr(model, 'feature_names') and model.feature_names:
                all_columns.update(model.feature_names)
        
        # Return default if no features found
        if not all_columns:
            return MLSignals().get_required_columns()
        
        return list(all_columns)
    
    def generate_signals(self, data: pd.DataFrame, symbol: str) -> List[Signal]:
        """Generate ensemble signals."""
        if not self.models:
            logger.error("No models available for ensemble")
            return []
        
        signals = []
        
        # Prepare features
        features = self._prepare_features(data)
        if features.empty:
            return signals
        
        # Get predictions from all models
        all_predictions = []
        for model in self.models:
            try:
                # Select features for this model
                model_features = features[[col for col in model.feature_names if col in features.columns]]
                predictions = model.predict_proba(model_features)
                all_predictions.append(predictions)
            except Exception as e:
                logger.error(f"Error getting predictions from {model.name}: {e}")
        
        if not all_predictions:
            return signals
        
        # Aggregate predictions
        if self.voting == "soft":
            # Average probabilities
            ensemble_predictions = np.mean(all_predictions, axis=0)
        else:
            # Majority voting
            class_predictions = [np.argmax(pred, axis=1) for pred in all_predictions]
            ensemble_predictions = self._hard_voting(class_predictions, len(all_predictions[0][0]))
        
        # Generate signals from ensemble predictions
        ml_signal_gen = MLSignals(prediction_threshold=self.min_agreement)
        
        for idx, proba in zip(features.index, ensemble_predictions):
            signal = ml_signal_gen._create_signal_from_prediction(
                idx, proba, data.loc[idx], symbol
            )
            if signal:
                signal.source = f"{self.name}_ensemble"
                signal.metadata["n_models"] = len(self.models)
                signals.append(signal)
        
        return signals
    
    def _prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for ensemble."""
        all_cols = self.get_required_columns()
        available_cols = [col for col in all_cols if col in data.columns]
        
        if not available_cols:
            return pd.DataFrame()
        
        features = data[available_cols].copy()
        features = features.ffill().bfill().dropna()
        
        return features
    
    def _hard_voting(self, predictions: List[np.ndarray], n_classes: int) -> np.ndarray:
        """Perform hard voting aggregation."""
        n_samples = len(predictions[0])
        ensemble_proba = np.zeros((n_samples, n_classes))
        
        for i in range(n_samples):
            votes = [pred[i] for pred in predictions]
            for cls in range(n_classes):
                ensemble_proba[i, cls] = votes.count(cls) / len(votes)
        
        return ensemble_proba