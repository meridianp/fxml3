"""
Machine learning models for FXML4.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, Union
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
import xgboost as xgb
import lightgbm as lgb
import joblib
from pathlib import Path

from fxml4_core.logging import get_logger
from fxml4_core.exceptions import ValidationError

logger = get_logger(__name__)


class MLModel(ABC):
    """Abstract base class for ML models."""
    
    def __init__(
        self,
        name: Optional[str] = None,
        model_type: str = "base",
        n_classes: int = 3,
        random_state: int = 42,
        **kwargs
    ):
        self.name = name or f"{model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.model_type = model_type
        self.n_classes = n_classes
        self.random_state = random_state
        self.model_params = kwargs
        self.model = None
        self.is_trained = False
        self.feature_names = None
        self.metadata = {
            "name": self.name,
            "model_type": self.model_type,
            "n_classes": self.n_classes,
            "created_at": datetime.now().isoformat()
        }
    
    @abstractmethod
    def _create_model(self) -> BaseEstimator:
        """Create the underlying model instance."""
        pass
    
    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Union[pd.Series, np.ndarray]) -> "MLModel":
        """Train the model."""
        if self.model is None:
            self.model = self._create_model()
        
        # Store feature names
        if isinstance(X, pd.DataFrame):
            self.feature_names = X.columns.tolist()
        
        # Train model
        self.model.fit(X, y)
        self.is_trained = True
        self.metadata["trained_at"] = datetime.now().isoformat()
        self.metadata["n_samples"] = len(y)
        
        logger.info(f"Model {self.name} trained on {len(y)} samples")
        return self
    
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Make predictions."""
        if not self.is_trained:
            raise ValidationError("Model must be trained before making predictions")
        return self.model.predict(X)
    
    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Get prediction probabilities."""
        if not self.is_trained:
            raise ValidationError("Model must be trained before making predictions")
        return self.model.predict_proba(X)
    
    def save(self, path: Union[str, Path]) -> None:
        """Save model to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save model and metadata
        model_data = {
            "model": self.model,
            "metadata": self.metadata,
            "feature_names": self.feature_names,
            "model_params": self.model_params
        }
        joblib.dump(model_data, path)
        logger.info(f"Model saved to {path}")
    
    def load(self, path: Union[str, Path]) -> None:
        """Load model from disk."""
        path = Path(path)
        model_data = joblib.load(path)
        
        self.model = model_data["model"]
        self.metadata = model_data["metadata"]
        self.feature_names = model_data.get("feature_names")
        self.model_params = model_data.get("model_params", {})
        self.is_trained = True
        
        logger.info(f"Model loaded from {path}")


class RandomForestModel(MLModel):
    """Random Forest classifier."""
    
    def __init__(self, name: Optional[str] = None, n_classes: int = 3, **kwargs):
        super().__init__(name, "random_forest", n_classes, **kwargs)
    
    def _create_model(self) -> BaseEstimator:
        default_params = {
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_split": 5,
            "min_samples_leaf": 2,
            "random_state": self.random_state,
            "n_jobs": -1
        }
        default_params.update(self.model_params)
        return RandomForestClassifier(**default_params)


class XGBoostModel(MLModel):
    """XGBoost classifier."""
    
    def __init__(self, name: Optional[str] = None, n_classes: int = 3, use_gpu: bool = False, **kwargs):
        super().__init__(name, "xgboost", n_classes, **kwargs)
        self.use_gpu = use_gpu
    
    def _create_model(self) -> BaseEstimator:
        default_params = {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "objective": "multi:softprob" if self.n_classes > 2 else "binary:logistic",
            "num_class": self.n_classes if self.n_classes > 2 else None,
            "random_state": self.random_state,
            "n_jobs": -1
        }
        
        # Add GPU parameters if available
        if self.use_gpu:
            default_params["tree_method"] = "gpu_hist"
            default_params["predictor"] = "gpu_predictor"
        
        default_params.update(self.model_params)
        
        # Remove None values
        default_params = {k: v for k, v in default_params.items() if v is not None}
        
        return xgb.XGBClassifier(**default_params)


class LightGBMModel(MLModel):
    """LightGBM classifier."""
    
    def __init__(self, name: Optional[str] = None, n_classes: int = 3, **kwargs):
        super().__init__(name, "lightgbm", n_classes, **kwargs)
    
    def _create_model(self) -> BaseEstimator:
        default_params = {
            "n_estimators": 100,
            "max_depth": -1,
            "learning_rate": 0.1,
            "num_leaves": 31,
            "objective": "multiclass" if self.n_classes > 2 else "binary",
            "num_class": self.n_classes if self.n_classes > 2 else 1,
            "random_state": self.random_state,
            "n_jobs": -1,
            "verbose": -1
        }
        default_params.update(self.model_params)
        return lgb.LGBMClassifier(**default_params)


class LogisticRegressionModel(MLModel):
    """Logistic Regression classifier."""
    
    def __init__(self, name: Optional[str] = None, n_classes: int = 3, **kwargs):
        super().__init__(name, "logistic_regression", n_classes, **kwargs)
    
    def _create_model(self) -> BaseEstimator:
        default_params = {
            "max_iter": 1000,
            "random_state": self.random_state,
            "n_jobs": -1
        }
        default_params.update(self.model_params)
        return LogisticRegression(**default_params)


class MLModelFactory:
    """Factory for creating ML models."""
    
    _models = {
        "random_forest": RandomForestModel,
        "xgboost": XGBoostModel,
        "lightgbm": LightGBMModel,
        "logistic_regression": LogisticRegressionModel
    }
    
    @classmethod
    def create(cls, model_type: str, **kwargs) -> MLModel:
        """Create a model instance."""
        if model_type not in cls._models:
            raise ValueError(f"Unknown model type: {model_type}. Available: {list(cls._models.keys())}")
        
        model_class = cls._models[model_type]
        return model_class(**kwargs)
    
    @classmethod
    def register(cls, name: str, model_class: type) -> None:
        """Register a new model type."""
        if not issubclass(model_class, MLModel):
            raise ValueError("Model class must inherit from MLModel")
        cls._models[name] = model_class