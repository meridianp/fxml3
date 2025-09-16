"""
ML Model Ensemble for GBP/USD Trading Strategy

This module implements the comprehensive ML model ensemble that serves as a core component
of the FXML4 trading system. It manages 29+ ML models across different algorithms:

- XGBoost models (8 variants): Different hyperparameters, timeframes, features
- LightGBM models (7 variants): Optimized for speed and accuracy
- Random Forest models (6 variants): Ensemble diversity and robustness
- Neural Network models (8 variants): Deep learning approaches

The ensemble provides:
- Model training and retraining pipeline
- Real-time prediction aggregation
- Confidence scoring and uncertainty quantification
- Feature importance analysis
- Model performance tracking and validation

Architecture follows the documented FXML4 vision for full ML functionality.
"""

import asyncio
import json
import logging
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim

# ML libraries
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    mean_squared_error,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import RobustScaler, StandardScaler

from fxml4.data_engineering.feature_versioning import FeatureRegistry


@dataclass
class ModelPrediction:
    """Result of ML model prediction"""

    model_id: str
    model_type: str
    prediction: float  # -1 to 1 for direction, or specific price target
    confidence: float  # 0 to 1
    probability: Optional[float]  # For classification models
    feature_importance: Dict[str, float]
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class EnsemblePrediction:
    """Aggregated prediction from model ensemble"""

    ensemble_prediction: float  # -1 to 1
    confidence: float  # 0 to 1
    individual_predictions: List[ModelPrediction]
    model_weights: Dict[str, float]
    agreement_score: float  # How much models agree (0 to 1)
    uncertainty: float  # Prediction uncertainty (0 to 1)
    timestamp: datetime
    metadata: Dict[str, Any]


class BaseMLModel(ABC):
    """Abstract base class for all ML models in the ensemble"""

    def __init__(self, model_id: str, config: Dict[str, Any]):
        self.model_id = model_id
        self.config = config
        self.model = None
        self.scaler = None
        self.feature_columns = []
        self.is_trained = False
        self.training_history = []
        self.performance_metrics = {}
        self.last_retrain = None
        self.logger = logging.getLogger(f"fxml4.ml.{model_id}")

    @abstractmethod
    async def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Train the model"""
        pass

    @abstractmethod
    async def predict(self, X: pd.DataFrame) -> ModelPrediction:
        """Generate prediction"""
        pass

    @abstractmethod
    async def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores"""
        pass

    async def save_model(self, path: Path) -> bool:
        """Save trained model to disk"""
        try:
            model_data = {
                "model": self.model,
                "scaler": self.scaler,
                "feature_columns": self.feature_columns,
                "config": self.config,
                "performance_metrics": self.performance_metrics,
                "training_history": self.training_history,
                "last_retrain": self.last_retrain,
            }

            joblib.dump(model_data, path / f"{self.model_id}.pkl")
            self.logger.info(f"Model {self.model_id} saved to {path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving model {self.model_id}: {e}")
            return False

    async def load_model(self, path: Path) -> bool:
        """Load trained model from disk"""
        try:
            model_data = joblib.load(path / f"{self.model_id}.pkl")

            self.model = model_data["model"]
            self.scaler = model_data["scaler"]
            self.feature_columns = model_data["feature_columns"]
            self.performance_metrics = model_data["performance_metrics"]
            self.training_history = model_data["training_history"]
            self.last_retrain = model_data["last_retrain"]
            self.is_trained = True

            self.logger.info(f"Model {self.model_id} loaded from {path}")
            return True

        except Exception as e:
            self.logger.error(f"Error loading model {self.model_id}: {e}")
            return False


class XGBoostModel(BaseMLModel):
    """XGBoost implementation for ensemble (8 variants)"""

    def __init__(self, model_id: str, config: Dict[str, Any]):
        super().__init__(model_id, config)

        # XGBoost-specific parameters
        self.xgb_params = config.get(
            "xgb_params",
            {
                "objective": "reg:squarederror",
                "eval_metric": "rmse",
                "max_depth": 6,
                "learning_rate": 0.1,
                "n_estimators": 100,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
            },
        )

        self.task_type = config.get("task_type", "regression")  # or 'classification'

    async def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Train XGBoost model"""
        try:
            self.feature_columns = X.columns.tolist()

            # Prepare data scaling
            self.scaler = RobustScaler()
            X_scaled = pd.DataFrame(
                self.scaler.fit_transform(X), columns=X.columns, index=X.index
            )

            # Time series split for validation
            tscv = TimeSeriesSplit(n_splits=5)

            if self.task_type == "regression":
                self.model = xgb.XGBRegressor(**self.xgb_params)
            else:
                self.model = xgb.XGBClassifier(**self.xgb_params)

            # Train model
            self.model.fit(X_scaled, y)

            # Cross-validation score
            cv_scores = cross_val_score(
                self.model, X_scaled, y, cv=tscv, scoring="neg_mean_squared_error"
            )

            # Performance metrics
            y_pred = self.model.predict(X_scaled)

            if self.task_type == "regression":
                mse = mean_squared_error(y, y_pred)
                rmse = np.sqrt(mse)
                self.performance_metrics = {
                    "mse": mse,
                    "rmse": rmse,
                    "cv_score_mean": -cv_scores.mean(),
                    "cv_score_std": cv_scores.std(),
                }
            else:
                # Classification metrics
                accuracy = accuracy_score(y, y_pred)
                precision = precision_score(y, y_pred, average="weighted")
                recall = recall_score(y, y_pred, average="weighted")
                self.performance_metrics = {
                    "accuracy": accuracy,
                    "precision": precision,
                    "recall": recall,
                    "cv_score_mean": -cv_scores.mean(),
                    "cv_score_std": cv_scores.std(),
                }

            self.is_trained = True
            self.last_retrain = datetime.utcnow()

            # Update training history
            training_record = {
                "timestamp": self.last_retrain,
                "samples": len(X),
                "features": len(self.feature_columns),
                "performance": self.performance_metrics.copy(),
            }
            self.training_history.append(training_record)

            self.logger.info(f"XGBoost model {self.model_id} trained successfully")
            self.logger.info(f"Performance metrics: {self.performance_metrics}")

            return self.performance_metrics

        except Exception as e:
            self.logger.error(f"Error training XGBoost model {self.model_id}: {e}")
            raise

    async def predict(self, X: pd.DataFrame) -> ModelPrediction:
        """Generate XGBoost prediction"""
        if not self.is_trained:
            raise ValueError(f"Model {self.model_id} is not trained")

        try:
            # Ensure feature alignment
            X_aligned = X[self.feature_columns]
            X_scaled = pd.DataFrame(
                self.scaler.transform(X_aligned),
                columns=self.feature_columns,
                index=X_aligned.index,
            )

            # Make prediction
            prediction = self.model.predict(X_scaled.iloc[-1:].values)[0]

            # Get prediction probability (for classification) or confidence (for regression)
            confidence = 0.5  # Default
            probability = None

            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(X_scaled.iloc[-1:].values)[0]
                probability = max(proba)
                confidence = probability
            else:
                # For regression, use feature importance and historical performance as confidence
                feature_importance_sum = sum(
                    abs(v) for v in self.model.feature_importances_
                )
                confidence = min(
                    feature_importance_sum / len(self.feature_columns), 1.0
                )

            # Normalize prediction to -1 to 1 range for direction
            if self.task_type == "regression":
                # Assume prediction is price change percentage
                normalized_prediction = np.tanh(prediction * 10)  # Scale and normalize
            else:
                # For classification, convert to directional signal
                normalized_prediction = (prediction - 0.5) * 2  # 0/1 to -1/1

            # Get feature importance
            feature_importance = await self.get_feature_importance()

            return ModelPrediction(
                model_id=self.model_id,
                model_type="xgboost",
                prediction=normalized_prediction,
                confidence=confidence,
                probability=probability,
                feature_importance=feature_importance,
                timestamp=datetime.utcnow(),
                metadata={
                    "raw_prediction": prediction,
                    "task_type": self.task_type,
                    "n_features": len(self.feature_columns),
                },
            )

        except Exception as e:
            self.logger.error(
                f"Error making prediction with model {self.model_id}: {e}"
            )
            raise

    async def get_feature_importance(self) -> Dict[str, float]:
        """Get XGBoost feature importance"""
        if not self.is_trained:
            return {}

        try:
            importance_scores = self.model.feature_importances_
            return dict(zip(self.feature_columns, importance_scores))
        except Exception as e:
            self.logger.error(
                f"Error getting feature importance for {self.model_id}: {e}"
            )
            return {}


class LightGBMModel(BaseMLModel):
    """LightGBM implementation for ensemble (7 variants)"""

    def __init__(self, model_id: str, config: Dict[str, Any]):
        super().__init__(model_id, config)

        # LightGBM-specific parameters
        self.lgb_params = config.get(
            "lgb_params",
            {
                "objective": "regression",
                "metric": "rmse",
                "boosting_type": "gbdt",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "feature_fraction": 0.9,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "verbose": -1,
                "random_state": 42,
            },
        )

        self.task_type = config.get("task_type", "regression")

    async def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Train LightGBM model"""
        try:
            self.feature_columns = X.columns.tolist()

            # LightGBM can handle raw features better, but still apply light scaling
            self.scaler = StandardScaler()
            X_scaled = pd.DataFrame(
                self.scaler.fit_transform(X), columns=X.columns, index=X.index
            )

            # Create LightGBM dataset
            train_data = lgb.Dataset(X_scaled, label=y)

            # Train model
            self.model = lgb.train(
                self.lgb_params,
                train_data,
                num_boost_round=100,
                valid_sets=[train_data],
                callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)],
            )

            # Performance metrics
            y_pred = self.model.predict(X_scaled)

            if self.task_type == "regression":
                mse = mean_squared_error(y, y_pred)
                rmse = np.sqrt(mse)
                self.performance_metrics = {"mse": mse, "rmse": rmse}
            else:
                # For classification tasks
                y_pred_binary = (y_pred > 0.5).astype(int)
                accuracy = accuracy_score(y, y_pred_binary)
                self.performance_metrics = {"accuracy": accuracy}

            self.is_trained = True
            self.last_retrain = datetime.utcnow()

            # Update training history
            training_record = {
                "timestamp": self.last_retrain,
                "samples": len(X),
                "features": len(self.feature_columns),
                "performance": self.performance_metrics.copy(),
            }
            self.training_history.append(training_record)

            self.logger.info(f"LightGBM model {self.model_id} trained successfully")

            return self.performance_metrics

        except Exception as e:
            self.logger.error(f"Error training LightGBM model {self.model_id}: {e}")
            raise

    async def predict(self, X: pd.DataFrame) -> ModelPrediction:
        """Generate LightGBM prediction"""
        if not self.is_trained:
            raise ValueError(f"Model {self.model_id} is not trained")

        try:
            X_aligned = X[self.feature_columns]
            X_scaled = self.scaler.transform(X_aligned.iloc[-1:])

            prediction = self.model.predict(X_scaled)[0]

            # Calculate confidence based on feature importance and model certainty
            confidence = (
                min(abs(prediction), 1.0) if self.task_type == "regression" else 0.7
            )

            # Normalize prediction
            normalized_prediction = (
                np.tanh(prediction * 5)
                if self.task_type == "regression"
                else prediction
            )

            feature_importance = await self.get_feature_importance()

            return ModelPrediction(
                model_id=self.model_id,
                model_type="lightgbm",
                prediction=normalized_prediction,
                confidence=confidence,
                probability=None,
                feature_importance=feature_importance,
                timestamp=datetime.utcnow(),
                metadata={"raw_prediction": prediction, "task_type": self.task_type},
            )

        except Exception as e:
            self.logger.error(
                f"Error making prediction with model {self.model_id}: {e}"
            )
            raise

    async def get_feature_importance(self) -> Dict[str, float]:
        """Get LightGBM feature importance"""
        if not self.is_trained:
            return {}

        try:
            importance_scores = self.model.feature_importance(importance_type="gain")
            return dict(zip(self.feature_columns, importance_scores))
        except Exception as e:
            self.logger.error(
                f"Error getting feature importance for {self.model_id}: {e}"
            )
            return {}


class RandomForestModel(BaseMLModel):
    """Random Forest implementation for ensemble (6 variants)"""

    def __init__(self, model_id: str, config: Dict[str, Any]):
        super().__init__(model_id, config)

        self.rf_params = config.get(
            "rf_params",
            {
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 5,
                "min_samples_leaf": 2,
                "max_features": "sqrt",
                "random_state": 42,
                "n_jobs": -1,
            },
        )

        self.task_type = config.get("task_type", "regression")

    async def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Train Random Forest model"""
        try:
            self.feature_columns = X.columns.tolist()

            # Random Forest handles raw features well, minimal scaling
            self.scaler = StandardScaler()
            X_scaled = pd.DataFrame(
                self.scaler.fit_transform(X), columns=X.columns, index=X.index
            )

            # Create model
            if self.task_type == "regression":
                self.model = RandomForestRegressor(**self.rf_params)
            else:
                self.model = RandomForestClassifier(**self.rf_params)

            # Train
            self.model.fit(X_scaled, y)

            # Performance metrics
            y_pred = self.model.predict(X_scaled)

            if self.task_type == "regression":
                mse = mean_squared_error(y, y_pred)
                rmse = np.sqrt(mse)
                self.performance_metrics = {
                    "mse": mse,
                    "rmse": rmse,
                    "oob_score": getattr(self.model, "oob_score_", None),
                }
            else:
                accuracy = accuracy_score(y, y_pred)
                self.performance_metrics = {
                    "accuracy": accuracy,
                    "oob_score": getattr(self.model, "oob_score_", None),
                }

            self.is_trained = True
            self.last_retrain = datetime.utcnow()

            training_record = {
                "timestamp": self.last_retrain,
                "samples": len(X),
                "features": len(self.feature_columns),
                "performance": self.performance_metrics.copy(),
            }
            self.training_history.append(training_record)

            self.logger.info(
                f"Random Forest model {self.model_id} trained successfully"
            )

            return self.performance_metrics

        except Exception as e:
            self.logger.error(
                f"Error training Random Forest model {self.model_id}: {e}"
            )
            raise

    async def predict(self, X: pd.DataFrame) -> ModelPrediction:
        """Generate Random Forest prediction"""
        if not self.is_trained:
            raise ValueError(f"Model {self.model_id} is not trained")

        try:
            X_aligned = X[self.feature_columns]
            X_scaled = self.scaler.transform(X_aligned.iloc[-1:])

            prediction = self.model.predict(X_scaled)[0]

            # For Random Forest, use prediction variance as confidence measure
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(X_scaled)[0]
                confidence = max(proba)
                probability = max(proba)
            else:
                # For regression, use tree predictions variance
                tree_predictions = [
                    tree.predict(X_scaled)[0] for tree in self.model.estimators_
                ]
                confidence = 1.0 - (
                    np.std(tree_predictions) / (np.mean(tree_predictions) + 1e-8)
                )
                confidence = max(0.1, min(confidence, 1.0))
                probability = None

            # Normalize prediction
            normalized_prediction = (
                np.tanh(prediction * 3)
                if self.task_type == "regression"
                else prediction
            )

            feature_importance = await self.get_feature_importance()

            return ModelPrediction(
                model_id=self.model_id,
                model_type="random_forest",
                prediction=normalized_prediction,
                confidence=confidence,
                probability=probability,
                feature_importance=feature_importance,
                timestamp=datetime.utcnow(),
                metadata={
                    "raw_prediction": prediction,
                    "n_trees": self.rf_params["n_estimators"],
                },
            )

        except Exception as e:
            self.logger.error(
                f"Error making prediction with model {self.model_id}: {e}"
            )
            raise

    async def get_feature_importance(self) -> Dict[str, float]:
        """Get Random Forest feature importance"""
        if not self.is_trained:
            return {}

        try:
            importance_scores = self.model.feature_importances_
            return dict(zip(self.feature_columns, importance_scores))
        except Exception as e:
            return {}


class NeuralNetworkModel(BaseMLModel):
    """Neural Network implementation for ensemble (8 variants)"""

    def __init__(self, model_id: str, config: Dict[str, Any]):
        super().__init__(model_id, config)

        self.nn_params = config.get(
            "nn_params",
            {
                "hidden_layer_sizes": (100, 50),
                "activation": "relu",
                "solver": "adam",
                "learning_rate": "adaptive",
                "max_iter": 500,
                "random_state": 42,
            },
        )

        self.task_type = config.get("task_type", "regression")

    async def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Train Neural Network model"""
        try:
            self.feature_columns = X.columns.tolist()

            # Neural networks require good scaling
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            # Create model
            if self.task_type == "regression":
                self.model = MLPRegressor(**self.nn_params)
            else:
                self.model = MLPClassifier(**self.nn_params)

            # Train
            self.model.fit(X_scaled, y)

            # Performance metrics
            y_pred = self.model.predict(X_scaled)

            if self.task_type == "regression":
                mse = mean_squared_error(y, y_pred)
                rmse = np.sqrt(mse)
                self.performance_metrics = {
                    "mse": mse,
                    "rmse": rmse,
                    "loss": self.model.loss_,
                }
            else:
                accuracy = accuracy_score(y, y_pred)
                self.performance_metrics = {
                    "accuracy": accuracy,
                    "loss": self.model.loss_,
                }

            self.is_trained = True
            self.last_retrain = datetime.utcnow()

            training_record = {
                "timestamp": self.last_retrain,
                "samples": len(X),
                "features": len(self.feature_columns),
                "performance": self.performance_metrics.copy(),
            }
            self.training_history.append(training_record)

            self.logger.info(
                f"Neural Network model {self.model_id} trained successfully"
            )

            return self.performance_metrics

        except Exception as e:
            self.logger.error(
                f"Error training Neural Network model {self.model_id}: {e}"
            )
            raise

    async def predict(self, X: pd.DataFrame) -> ModelPrediction:
        """Generate Neural Network prediction"""
        if not self.is_trained:
            raise ValueError(f"Model {self.model_id} is not trained")

        try:
            X_aligned = X[self.feature_columns]
            X_scaled = self.scaler.transform(X_aligned.iloc[-1:])

            prediction = self.model.predict(X_scaled)[0]

            # For neural networks, use prediction confidence based on output layer activations
            confidence = 0.7  # Default confidence for neural networks
            probability = None

            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(X_scaled)[0]
                confidence = max(proba)
                probability = max(proba)

            # Normalize prediction
            normalized_prediction = (
                np.tanh(prediction * 2)
                if self.task_type == "regression"
                else prediction
            )

            return ModelPrediction(
                model_id=self.model_id,
                model_type="neural_network",
                prediction=normalized_prediction,
                confidence=confidence,
                probability=probability,
                feature_importance={},  # Neural networks don't provide easy feature importance
                timestamp=datetime.utcnow(),
                metadata={
                    "raw_prediction": prediction,
                    "hidden_layers": self.nn_params["hidden_layer_sizes"],
                    "loss": self.model.loss_,
                },
            )

        except Exception as e:
            self.logger.error(
                f"Error making prediction with model {self.model_id}: {e}"
            )
            raise

    async def get_feature_importance(self) -> Dict[str, float]:
        """Neural networks don't provide direct feature importance"""
        return {}


class MLEnsemble:
    """
    ML Model Ensemble Manager

    Manages the complete ensemble of 29+ ML models and provides:
    - Model training and lifecycle management
    - Real-time prediction aggregation
    - Confidence scoring and uncertainty quantification
    - Performance monitoring and retraining
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.models: Dict[str, BaseMLModel] = {}
        self.model_weights: Dict[str, float] = {}
        self.feature_registry: Optional[FeatureRegistry] = None
        self.logger = logging.getLogger(f"fxml4.ml.{self.__class__.__name__}")

        # Model configuration
        self.model_configs = self._create_model_configurations()

        # Ensemble parameters
        self.min_models_for_prediction = config.get("min_models_for_prediction", 5)
        self.weight_update_frequency = config.get(
            "weight_update_frequency", 24
        )  # hours
        self.retrain_threshold = config.get(
            "retrain_threshold", 0.1
        )  # performance degradation

        # Initialize models
        self._initialize_models()

    def _create_model_configurations(self) -> Dict[str, Dict[str, Any]]:
        """Create configuration for all 29+ models"""
        configs = {}

        # XGBoost models (8 variants)
        xgb_variants = [
            {"max_depth": 4, "learning_rate": 0.15, "n_estimators": 150},
            {"max_depth": 6, "learning_rate": 0.1, "n_estimators": 100},
            {"max_depth": 8, "learning_rate": 0.05, "n_estimators": 200},
            {
                "max_depth": 5,
                "learning_rate": 0.2,
                "n_estimators": 80,
                "task_type": "classification",
            },
            {
                "max_depth": 3,
                "learning_rate": 0.25,
                "n_estimators": 120,
                "subsample": 0.9,
            },
            {
                "max_depth": 7,
                "learning_rate": 0.08,
                "n_estimators": 180,
                "colsample_bytree": 0.7,
            },
            {
                "max_depth": 6,
                "learning_rate": 0.12,
                "n_estimators": 140,
                "reg_lambda": 1.0,
            },
            {
                "max_depth": 5,
                "learning_rate": 0.18,
                "n_estimators": 110,
                "reg_alpha": 0.5,
            },
        ]

        for i, params in enumerate(xgb_variants):
            configs[f"xgb_{i+1}"] = {
                "model_class": XGBoostModel,
                "xgb_params": {**params, "random_state": 42 + i},
                "task_type": params.get("task_type", "regression"),
            }

        # LightGBM models (7 variants)
        lgb_variants = [
            {"num_leaves": 31, "learning_rate": 0.05, "feature_fraction": 0.9},
            {"num_leaves": 50, "learning_rate": 0.08, "feature_fraction": 0.8},
            {"num_leaves": 20, "learning_rate": 0.12, "feature_fraction": 0.95},
            {"num_leaves": 40, "learning_rate": 0.06, "bagging_fraction": 0.9},
            {"num_leaves": 60, "learning_rate": 0.04, "min_data_in_leaf": 10},
            {"num_leaves": 25, "learning_rate": 0.1, "reg_lambda": 1.0},
            {"num_leaves": 35, "learning_rate": 0.07, "reg_alpha": 0.3},
        ]

        for i, params in enumerate(lgb_variants):
            configs[f"lgb_{i+1}"] = {
                "model_class": LightGBMModel,
                "lgb_params": {**params, "random_state": 42 + i},
                "task_type": "regression",
            }

        # Random Forest models (6 variants)
        rf_variants = [
            {"n_estimators": 100, "max_depth": 10, "min_samples_split": 5},
            {"n_estimators": 150, "max_depth": 8, "min_samples_split": 3},
            {"n_estimators": 200, "max_depth": 12, "min_samples_leaf": 3},
            {
                "n_estimators": 80,
                "max_depth": 15,
                "max_features": 0.8,
                "task_type": "classification",
            },
            {"n_estimators": 120, "max_depth": 6, "min_samples_split": 8},
            {"n_estimators": 180, "max_depth": 9, "min_samples_leaf": 4},
        ]

        for i, params in enumerate(rf_variants):
            configs[f"rf_{i+1}"] = {
                "model_class": RandomForestModel,
                "rf_params": {**params, "random_state": 42 + i},
                "task_type": params.get("task_type", "regression"),
            }

        # Neural Network models (8 variants)
        nn_variants = [
            {
                "hidden_layer_sizes": (100, 50),
                "activation": "relu",
                "learning_rate": "adaptive",
            },
            {
                "hidden_layer_sizes": (150, 75, 25),
                "activation": "tanh",
                "learning_rate": "constant",
            },
            {
                "hidden_layer_sizes": (80, 40),
                "activation": "logistic",
                "learning_rate": "invscaling",
            },
            {
                "hidden_layer_sizes": (200, 100, 50),
                "activation": "relu",
                "task_type": "classification",
            },
            {"hidden_layer_sizes": (60, 30, 15), "activation": "tanh", "alpha": 0.01},
            {"hidden_layer_sizes": (120, 60), "activation": "relu", "alpha": 0.001},
            {
                "hidden_layer_sizes": (90, 45, 20),
                "activation": "logistic",
                "beta_1": 0.8,
            },
            {"hidden_layer_sizes": (180, 90, 45), "activation": "relu", "beta_2": 0.95},
        ]

        for i, params in enumerate(nn_variants):
            configs[f"nn_{i+1}"] = {
                "model_class": NeuralNetworkModel,
                "nn_params": {**params, "random_state": 42 + i, "max_iter": 500},
                "task_type": params.get("task_type", "regression"),
            }

        return configs

    def _initialize_models(self):
        """Initialize all models in the ensemble"""
        for model_id, config in self.model_configs.items():
            try:
                model_class = config.pop("model_class")
                model = model_class(model_id, config)
                self.models[model_id] = model

                # Initialize equal weights
                self.model_weights[model_id] = 1.0 / len(self.model_configs)

            except Exception as e:
                self.logger.error(f"Error initializing model {model_id}: {e}")

        self.logger.info(f"Initialized {len(self.models)} models in ensemble")

    async def train_ensemble(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Train all models in the ensemble"""
        training_results = {}

        for model_id, model in self.models.items():
            try:
                self.logger.info(f"Training model {model_id}...")
                results = await model.train(X, y)
                training_results[model_id] = results

                # Update model weight based on performance
                if "rmse" in results:
                    # Lower RMSE = higher weight (inverted)
                    weight = 1.0 / (results["rmse"] + 1e-8)
                elif "accuracy" in results:
                    # Higher accuracy = higher weight
                    weight = results["accuracy"]
                else:
                    weight = 0.5  # Default

                self.model_weights[model_id] = weight

            except Exception as e:
                self.logger.error(f"Error training model {model_id}: {e}")
                training_results[model_id] = {"error": str(e)}

        # Normalize weights
        total_weight = sum(self.model_weights.values())
        if total_weight > 0:
            for model_id in self.model_weights:
                self.model_weights[model_id] /= total_weight

        self.logger.info(f"Ensemble training completed. Results: {training_results}")

        return training_results

    async def predict_ensemble(self, X: pd.DataFrame) -> EnsemblePrediction:
        """Generate ensemble prediction from all trained models"""
        individual_predictions = []

        # Collect predictions from all trained models
        for model_id, model in self.models.items():
            if model.is_trained:
                try:
                    prediction = await model.predict(X)
                    individual_predictions.append(prediction)
                except Exception as e:
                    self.logger.error(f"Error getting prediction from {model_id}: {e}")

        if len(individual_predictions) < self.min_models_for_prediction:
            raise ValueError(
                f"Not enough trained models ({len(individual_predictions)}) for reliable prediction"
            )

        # Calculate weighted ensemble prediction
        weighted_sum = 0.0
        total_weight = 0.0

        for pred in individual_predictions:
            weight = self.model_weights.get(pred.model_id, 0.0)
            weighted_sum += pred.prediction * weight * pred.confidence
            total_weight += weight * pred.confidence

        ensemble_prediction = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Calculate ensemble confidence
        confidences = [pred.confidence for pred in individual_predictions]
        ensemble_confidence = np.mean(confidences) * (
            1 + np.std(confidences)
        )  # Penalize high variance
        ensemble_confidence = min(ensemble_confidence, 1.0)

        # Calculate agreement score
        predictions = [pred.prediction for pred in individual_predictions]
        agreement_score = 1.0 - (
            np.std(predictions) / (np.mean(np.abs(predictions)) + 1e-8)
        )
        agreement_score = max(0.0, min(agreement_score, 1.0))

        # Calculate uncertainty
        prediction_variance = np.var(predictions)
        uncertainty = min(prediction_variance * 10, 1.0)  # Scale and cap at 1.0

        return EnsemblePrediction(
            ensemble_prediction=ensemble_prediction,
            confidence=ensemble_confidence,
            individual_predictions=individual_predictions,
            model_weights=self.model_weights.copy(),
            agreement_score=agreement_score,
            uncertainty=uncertainty,
            timestamp=datetime.utcnow(),
            metadata={
                "n_models_used": len(individual_predictions),
                "prediction_variance": prediction_variance,
                "confidence_distribution": confidences,
            },
        )

    async def get_model_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all models"""
        summary = {}

        for model_id, model in self.models.items():
            if model.is_trained:
                summary[model_id] = {
                    "performance_metrics": model.performance_metrics,
                    "weight": self.model_weights.get(model_id, 0.0),
                    "last_retrain": model.last_retrain,
                    "training_history_count": len(model.training_history),
                }

        return summary
