"""
Model training utilities for time-series data.
"""

from typing import Dict, Any, Optional, Tuple, Union, List
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import optuna
from datetime import datetime

from fxml4_core.logging import get_logger
from fxml4_ml.models import MLModel

logger = get_logger(__name__)


class TimeSeriesTrainer:
    """Trainer for time-series ML models."""
    
    def __init__(
        self,
        model: MLModel,
        n_splits: int = 5,
        validation_ratio: float = 0.2,
        test_ratio: float = 0.1
    ):
        self.model = model
        self.n_splits = n_splits
        self.validation_ratio = validation_ratio
        self.test_ratio = test_ratio
        self.training_history = []
    
    def split_data(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
        """Split data into train, validation, and test sets."""
        n_samples = len(X)
        
        # Calculate split points
        test_size = int(n_samples * self.test_ratio)
        val_size = int(n_samples * self.validation_ratio)
        train_size = n_samples - test_size - val_size
        
        # Split data
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        
        X_val = X.iloc[train_size:train_size + val_size]
        y_val = y.iloc[train_size:train_size + val_size]
        
        X_test = X.iloc[train_size + val_size:]
        y_test = y.iloc[train_size + val_size:]
        
        logger.info(f"Data split - Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
        
        return X_train, X_val, X_test, y_train, y_val, y_test
    
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        validation_data: Optional[Tuple[pd.DataFrame, pd.Series]] = None
    ) -> Dict[str, Any]:
        """Train the model with time-series validation."""
        start_time = datetime.now()
        
        # Split data if validation data not provided
        if validation_data is None:
            X_train, X_val, X_test, y_train, y_val, y_test = self.split_data(X, y)
        else:
            X_train, y_train = X, y
            X_val, y_val = validation_data
            X_test, y_test = None, None
        
        # Train model
        self.model.fit(X_train, y_train)
        
        # Evaluate on validation set
        val_predictions = self.model.predict(X_val)
        val_metrics = self._calculate_metrics(y_val, val_predictions)
        
        # Evaluate on test set if available
        test_metrics = None
        if X_test is not None:
            test_predictions = self.model.predict(X_test)
            test_metrics = self._calculate_metrics(y_test, test_predictions)
        
        # Store training results
        training_time = (datetime.now() - start_time).total_seconds()
        results = {
            "model_name": self.model.name,
            "training_time": training_time,
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "test_samples": len(X_test) if X_test is not None else 0,
            "val_metrics": val_metrics,
            "test_metrics": test_metrics,
            "timestamp": datetime.now().isoformat()
        }
        
        self.training_history.append(results)
        logger.info(f"Training completed in {training_time:.2f}s - Val accuracy: {val_metrics['accuracy']:.4f}")
        
        return results
    
    def cross_validate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """Perform time-series cross-validation."""
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        cv_scores = []
        
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            logger.info(f"Cross-validation fold {fold + 1}/{self.n_splits}")
            
            # Split data
            X_train_cv = X.iloc[train_idx]
            y_train_cv = y.iloc[train_idx]
            X_val_cv = X.iloc[val_idx]
            y_val_cv = y.iloc[val_idx]
            
            # Train model
            self.model.fit(X_train_cv, y_train_cv)
            
            # Evaluate
            val_predictions = self.model.predict(X_val_cv)
            metrics = self._calculate_metrics(y_val_cv, val_predictions)
            cv_scores.append(metrics)
        
        # Calculate average metrics
        avg_metrics = {}
        for metric in cv_scores[0].keys():
            values = [score[metric] for score in cv_scores]
            avg_metrics[f"{metric}_mean"] = np.mean(values)
            avg_metrics[f"{metric}_std"] = np.std(values)
        
        logger.info(f"Cross-validation complete - Mean accuracy: {avg_metrics['accuracy_mean']:.4f} (±{avg_metrics['accuracy_std']:.4f})")
        
        return {
            "cv_scores": cv_scores,
            "avg_metrics": avg_metrics,
            "n_splits": self.n_splits
        }
    
    def _calculate_metrics(self, y_true: pd.Series, y_pred: np.ndarray) -> Dict[str, float]:
        """Calculate classification metrics."""
        return {
            "accuracy": accuracy_score(y_true, y_pred),
            "precision": precision_score(y_true, y_pred, average='weighted', zero_division=0),
            "recall": recall_score(y_true, y_pred, average='weighted', zero_division=0),
            "f1_score": f1_score(y_true, y_pred, average='weighted', zero_division=0)
        }


class HyperparameterOptimizer:
    """Hyperparameter optimization using Optuna."""
    
    def __init__(
        self,
        model_type: str,
        n_trials: int = 100,
        n_jobs: int = 1,
        random_state: int = 42
    ):
        self.model_type = model_type
        self.n_trials = n_trials
        self.n_jobs = n_jobs
        self.random_state = random_state
        self.best_params = None
        self.study = None
    
    def optimize(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series
    ) -> Dict[str, Any]:
        """Optimize hyperparameters."""
        from fxml4_ml.models import MLModelFactory
        
        def objective(trial):
            # Define hyperparameter search space
            params = self._get_search_space(trial)
            
            # Create and train model
            model = MLModelFactory.create(self.model_type, **params)
            model.fit(X_train, y_train)
            
            # Evaluate
            predictions = model.predict(X_val)
            accuracy = accuracy_score(y_val, predictions)
            
            return accuracy
        
        # Run optimization
        self.study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=self.random_state)
        )
        
        self.study.optimize(
            objective,
            n_trials=self.n_trials,
            n_jobs=self.n_jobs,
            show_progress_bar=True
        )
        
        self.best_params = self.study.best_params
        logger.info(f"Optimization complete - Best accuracy: {self.study.best_value:.4f}")
        
        return {
            "best_params": self.best_params,
            "best_value": self.study.best_value,
            "n_trials": len(self.study.trials)
        }
    
    def _get_search_space(self, trial) -> Dict[str, Any]:
        """Define hyperparameter search space for each model type."""
        if self.model_type == "random_forest":
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 300),
                "max_depth": trial.suggest_int("max_depth", 3, 20),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                "random_state": self.random_state
            }
        
        elif self.model_type == "xgboost":
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 300),
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "random_state": self.random_state
            }
        
        elif self.model_type == "lightgbm":
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 300),
                "num_leaves": trial.suggest_int("num_leaves", 20, 300),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
                "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
                "random_state": self.random_state
            }
        
        else:
            return {"random_state": self.random_state}