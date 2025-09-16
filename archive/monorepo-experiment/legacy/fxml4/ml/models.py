"""
Machine Learning Models Module

This module provides functionality for training and evaluating machine learning models
adapted specifically for the FXML4 platform. It includes:

- Classic ML models (Random Forest, XGBoost, Logistic Regression)
- Support for GPU acceleration where available
- Model metadata tracking
- Ensemble methods
- Evaluation metrics specifically for trading
- Apple Silicon optimizations for local development

The implementation supports both local training on macOS/Apple Silicon and
distributed training on GPU-enabled servers for improved performance.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Union, Optional, Any, Callable

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ML libraries
import joblib
from sklearn.base import BaseEstimator
from sklearn.model_selection import (
    cross_val_score, TimeSeriesSplit, GridSearchCV, train_test_split
)
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix, roc_curve, auc
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

# XGBoost - check for GPU compatibility
import xgboost as xgb
try:
    # Check if GPU is available for XGBoost
    xgb_params = {"tree_method": "gpu_hist", "gpu_id": 0}
    dtrain = xgb.DMatrix(np.array([[0, 1], [2, 3]]), label=np.array([0, 1]))
    bst = xgb.train(xgb_params, dtrain, num_boost_round=1)
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False

# Check for Apple Silicon optimizations
import platform
IS_APPLE_SILICON = platform.processor() == 'arm' and platform.system() == 'Darwin'

# Configure logging
logger = logging.getLogger(__name__)


class MLModelBase:
    """Base class for all ML models in FXML4."""
    
    def __init__(
        self,
        name: Optional[str] = None,
        model_type: str = "base",
        n_classes: int = 3,
        random_state: int = 42,
        model_params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize base ML model.
        
        Args:
            name: Model name (default: auto-generated)
            model_type: Type of model (e.g., "random_forest", "xgboost")
            n_classes: Number of target classes
            random_state: Random seed for reproducibility
            model_params: Model hyperparameters
            metadata: Additional metadata to store
        """
        # Set model name
        if name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.name = f"{model_type}_{timestamp}"
        else:
            self.name = name
        
        self.model_type = model_type
        self.n_classes = n_classes
        self.random_state = random_state
        self.model_params = model_params or {}
        
        # Initialize model metadata
        self.metadata = metadata or {}
        self.metadata.update({
            "name": self.name,
            "model_type": self.model_type,
            "n_classes": self.n_classes,
            "random_state": self.random_state,
            "created_at": datetime.now().isoformat(),
            "platform": {
                "system": platform.system(),
                "processor": platform.processor(),
                "is_apple_silicon": IS_APPLE_SILICON,
                "gpu_available": GPU_AVAILABLE
            }
        })
        
        # Placeholders for feature information
        self.feature_names = None
        self.feature_importance = None
        
        # Placeholder for model
        self.model = None
        
        # Training metrics
        self.training_metrics = {}
    
    def train(
        self,
        X_train: Union[pd.DataFrame, np.ndarray],
        y_train: Union[pd.Series, np.ndarray],
        validation_data: Optional[Tuple[Union[pd.DataFrame, np.ndarray], Union[pd.Series, np.ndarray]]] = None,
        feature_names: Optional[List[str]] = None
    ) -> None:
        """
        Train the model.
        
        Args:
            X_train: Training features
            y_train: Training labels
            validation_data: Optional (X_val, y_val) tuple for validation
            feature_names: Optional list of feature names
        """
        raise NotImplementedError("Subclasses must implement train()")
    
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Make class predictions.
        
        Args:
            X: Input features
            
        Returns:
            Predicted class labels
        """
        raise NotImplementedError("Subclasses must implement predict()")
    
    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Make probability predictions.
        
        Args:
            X: Input features
            
        Returns:
            Predicted class probabilities
        """
        raise NotImplementedError("Subclasses must implement predict_proba()")
    
    def _store_feature_names(
        self, 
        X_train: Union[pd.DataFrame, np.ndarray],
        feature_names: Optional[List[str]] = None
    ) -> None:
        """
        Store feature names.
        
        Args:
            X_train: Training features
            feature_names: Optional explicit feature names
        """
        if feature_names is not None:
            self.feature_names = feature_names
        elif isinstance(X_train, pd.DataFrame):
            self.feature_names = X_train.columns.tolist()
        else:
            self.feature_names = [f"feature_{i}" for i in range(X_train.shape[1])]
        
        # Update metadata
        self.metadata["feature_names"] = self.feature_names
    
    def evaluate(
        self,
        X_test: Union[pd.DataFrame, np.ndarray],
        y_test: Union[pd.Series, np.ndarray],
        returns: Optional[Union[pd.Series, np.ndarray]] = None,
        plot: bool = False,
        figsize: Tuple[int, int] = (12, 10)
    ) -> Dict[str, Any]:
        """
        Evaluate model performance.
        
        Args:
            X_test: Test features
            y_test: Test labels
            returns: Optional returns series for calculating financial metrics
            plot: Whether to plot evaluation results
            figsize: Figure size for plots
            
        Returns:
            Dictionary of evaluation metrics
        """
        # Make predictions
        y_pred = self.predict(X_test)
        
        # Get probabilities if available
        try:
            y_proba = self.predict_proba(X_test)
        except:
            y_proba = None
        
        # Calculate standard metrics
        metrics = {}
        metrics["accuracy"] = accuracy_score(y_test, y_pred)
        metrics["precision"] = precision_score(y_test, y_pred, average="weighted")
        metrics["recall"] = recall_score(y_test, y_pred, average="weighted")
        metrics["f1"] = f1_score(y_test, y_pred, average="weighted")
        
        # Calculate class-specific metrics
        metrics["class_report"] = classification_report(y_test, y_pred, output_dict=True)
        metrics["confusion_matrix"] = confusion_matrix(y_test, y_pred).tolist()
        
        # Calculate financial metrics if returns provided
        if returns is not None:
            metrics.update(self._calculate_financial_metrics(y_test, y_pred, returns))
        
        # Store evaluation results in metadata
        self.metadata["evaluation"] = {
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "timestamp": datetime.now().isoformat()
        }
        
        # Add financial metrics to metadata if available
        if "profit_factor" in metrics:
            self.metadata["evaluation"].update({
                "profit_factor": metrics["profit_factor"],
                "win_rate": metrics["win_rate"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown": metrics["max_drawdown"]
            })
        
        # Plot results if requested
        if plot:
            self._plot_evaluation(y_test, y_pred, y_proba, figsize)
        
        return metrics
    
    def _calculate_financial_metrics(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_pred: np.ndarray,
        returns: Union[pd.Series, np.ndarray]
    ) -> Dict[str, float]:
        """
        Calculate financial metrics for trading models.
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            returns: Future returns for each prediction
            
        Returns:
            Dictionary of financial metrics
        """
        # Convert to numpy arrays if needed
        if isinstance(y_true, pd.Series):
            y_true = y_true.values
        if isinstance(returns, pd.Series):
            returns = returns.values
        
        metrics = {}
        
        # No financial metrics implementation in base class
        metrics["profit_factor"] = 0.0
        metrics["win_rate"] = 0.0
        metrics["sharpe_ratio"] = 0.0
        metrics["max_drawdown"] = 0.0
        
        return metrics
    
    def _plot_evaluation(
        self,
        y_test: Union[pd.Series, np.ndarray],
        y_pred: np.ndarray,
        y_proba: Optional[np.ndarray] = None,
        figsize: Tuple[int, int] = (12, 10)
    ) -> None:
        """
        Plot evaluation results.
        
        Args:
            y_test: Test labels
            y_pred: Predicted labels
            y_proba: Predicted probabilities
            figsize: Figure size
        """
        plt.figure(figsize=figsize)
        
        # Plot confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        
        # Compute percentages
        cm_pct = cm.astype("float") / cm.sum(axis=1)[:, np.newaxis] * 100
        
        # Plot as heatmap
        plt.subplot(2, 2, 1)
        plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
        plt.title("Confusion Matrix")
        
        # Add labels
        tick_marks = np.arange(self.n_classes)
        class_labels = [str(i) for i in range(self.n_classes)]
        plt.xticks(tick_marks, class_labels)
        plt.yticks(tick_marks, class_labels)
        
        # Add text annotations
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                text = f"{cm[i, j]}\n({cm_pct[i, j]:.1f}%)"
                plt.text(j, i, text, ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
        
        plt.xlabel("Predicted")
        plt.ylabel("True")
        
        # Plot class-specific metrics
        plt.subplot(2, 2, 2)
        report = classification_report(y_test, y_pred, output_dict=True)
        
        # Extract class metrics
        class_metrics = []
        for class_label in range(self.n_classes):
            if str(class_label) in report:
                metrics = report[str(class_label)]
                class_metrics.append({
                    "class": class_label,
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
                    "f1-score": metrics["f1-score"],
                    "support": metrics["support"]
                })
        
        # Convert to DataFrame for plotting
        report_df = pd.DataFrame(class_metrics)
        
        # Plot metrics
        bar_width = 0.25
        index = np.arange(len(class_metrics))
        
        plt.bar(index, report_df["precision"], bar_width, label="Precision")
        plt.bar(index + bar_width, report_df["recall"], bar_width, label="Recall")
        plt.bar(index + 2 * bar_width, report_df["f1-score"], bar_width, label="F1")
        
        plt.xlabel("Class")
        plt.ylabel("Score")
        plt.title("Classification Report")
        plt.xticks(index + bar_width, report_df["class"])
        plt.legend()
        
        # Plot ROC curve for binary classification
        if self.n_classes == 2 and y_proba is not None:
            plt.subplot(2, 2, 3)
            
            # Calculate ROC curve
            fpr, tpr, _ = roc_curve(y_test, y_proba[:, 1])
            roc_auc = auc(fpr, tpr)
            
            # Plot
            plt.plot(fpr, tpr, label=f"ROC curve (AUC = {roc_auc:.2f})")
            plt.plot([0, 1], [0, 1], "k--")  # Diagonal reference line
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.xlabel("False Positive Rate")
            plt.ylabel("True Positive Rate")
            plt.title("Receiver Operating Characteristic")
            plt.legend(loc="lower right")
        
        # Plot feature importance if available
        if self.feature_importance is not None and self.feature_names is not None:
            plt.subplot(2, 2, 4)
            
            # Sort features by importance
            indices = np.argsort(self.feature_importance)[::-1]
            top_n = min(10, len(indices))
            
            # Plot top N features
            top_indices = indices[:top_n]
            top_features = [self.feature_names[i] for i in top_indices]
            top_importance = self.feature_importance[top_indices]
            
            plt.barh(range(top_n), top_importance, align="center")
            plt.yticks(range(top_n), top_features)
            plt.xlabel("Importance")
            plt.ylabel("Feature")
            plt.title("Top Feature Importance")
        
        plt.tight_layout()
        plt.show()
    
    def save(self, directory: str = "models") -> Dict[str, str]:
        """
        Save model to disk.
        
        Args:
            directory: Directory to save the model
            
        Returns:
            Dictionary with paths to saved files
        """
        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        
        # Update metadata with save timestamp
        self.metadata["saved_at"] = datetime.now().isoformat()
        
        # Save model file paths
        saved_files = {}
        
        # Save metadata
        metadata_path = os.path.join(directory, f"{self.name}_metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(self.metadata, f, indent=2)
        saved_files["metadata"] = metadata_path
        
        return saved_files
    
    @classmethod
    def load(cls, name: str, directory: str = "models") -> "MLModelBase":
        """
        Load model from disk.
        
        Args:
            name: Model name
            directory: Directory where model is saved
            
        Returns:
            Loaded model instance
        """
        raise NotImplementedError("Subclasses must implement load()")


class ClassicMLModel(MLModelBase):
    """
    Implementation of classic machine learning models 
    (RandomForest, XGBoost, LogisticRegression).
    """
    
    def __init__(
        self,
        model_type: str = "random_forest",
        name: Optional[str] = None,
        n_classes: int = 3,
        random_state: int = 42,
        model_params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize classic ML model.
        
        Args:
            model_type: Type of model ("random_forest", "xgboost", "logistic")
            name: Model name (default: auto-generated)
            n_classes: Number of target classes
            random_state: Random seed for reproducibility
            model_params: Model hyperparameters
            metadata: Additional metadata to store
        """
        super().__init__(name, model_type, n_classes, random_state, model_params, metadata)
        
        # Set default parameters based on model type
        self._set_default_params()
        
        # Create model
        self.model = self._create_model()
        
        # Label transformation metadata
        self.label_map = None
        self.inverse_label_map = None
    
    def _set_default_params(self) -> None:
        """Set default parameters based on model type."""
        if self.model_type == "logistic":
            defaults = {
                "C": 1.0,
                "penalty": "l2",
                "solver": "liblinear",
                "max_iter": 1000,
                "random_state": self.random_state
            }
        elif self.model_type == "random_forest":
            defaults = {
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 2,
                "min_samples_leaf": 1,
                "random_state": self.random_state
            }
        elif self.model_type == "xgboost":
            defaults = {
                "n_estimators": 100,
                "max_depth": 6,
                "learning_rate": 0.1,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "objective": "multi:softmax" if self.n_classes > 2 else "binary:logistic",
                "num_class": self.n_classes if self.n_classes > 2 else None,
                "random_state": self.random_state
            }
            
            # Add GPU acceleration if available
            if GPU_AVAILABLE:
                defaults["tree_method"] = "gpu_hist"
                defaults["gpu_id"] = 0
            # Optimize for Apple Silicon if needed
            elif IS_APPLE_SILICON:
                defaults["tree_method"] = "hist"
                defaults["use_label_encoder"] = False
            
            # Remove None values
            defaults = {k: v for k, v in defaults.items() if v is not None}
        else:
            defaults = {}
        
        # Update with user-provided parameters
        for key, value in self.model_params.items():
            defaults[key] = value
        
        self.model_params = defaults
        
        # Update metadata
        self.metadata["model_params"] = self.model_params
    
    def _create_model(self) -> BaseEstimator:
        """
        Create model instance based on model type.
        
        Returns:
            Initialized model
        """
        if self.model_type == "logistic":
            return LogisticRegression(**self.model_params)
        elif self.model_type == "random_forest":
            return RandomForestClassifier(**self.model_params)
        elif self.model_type == "xgboost":
            return xgb.XGBClassifier(**self.model_params)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
    
    def train(
        self,
        X_train: Union[pd.DataFrame, np.ndarray],
        y_train: Union[pd.Series, np.ndarray],
        validation_data: Optional[Tuple[Union[pd.DataFrame, np.ndarray], Union[pd.Series, np.ndarray]]] = None,
        feature_names: Optional[List[str]] = None
    ) -> None:
        """
        Train the model.
        
        Args:
            X_train: Training features
            y_train: Training labels
            validation_data: Optional (X_val, y_val) tuple for validation
            feature_names: Optional list of feature names
        """
        # Store feature names
        self._store_feature_names(X_train, feature_names)
        
        # Convert to numpy arrays if needed
        if isinstance(X_train, pd.DataFrame):
            X_train_values = X_train.values
        else:
            X_train_values = X_train
            
        if isinstance(y_train, pd.Series):
            y_train_values = y_train.values
        else:
            y_train_values = y_train
        
        # Transform target labels for XGBoost if needed
        if self.model_type == "xgboost" and self.n_classes > 2:
            # Check if we have negative class labels or non-consecutive labels
            unique_labels = np.unique(y_train_values)
            if -1 in unique_labels or not np.array_equal(unique_labels, np.arange(len(unique_labels))):
                logger.info("Transforming class labels for XGBoost: mapping to consecutive integers")
                
                # Map labels to consecutive integers starting from 0
                label_map = {label: i for i, label in enumerate(sorted(unique_labels))}
                y_train_transformed = np.array([label_map[label] for label in y_train_values])
                
                # Store mapping for inverse transform during prediction
                self.label_map = label_map
                self.inverse_label_map = {v: k for k, v in label_map.items()}
                
                # Handle class imbalance for multiclass
                # Calculate sample weights - higher weights for minority classes
                if self.n_classes > 2:
                    class_counts = pd.Series(y_train_transformed).value_counts()
                    max_count = class_counts.max()
                    class_weights = {cls: max_count / count for cls, count in class_counts.items()}
                    sample_weights = np.array([class_weights[cls] for cls in y_train_transformed])
                    
                    # Train model with transformed labels and sample weights
                    self.model.fit(X_train_values, y_train_transformed, sample_weight=sample_weights)
                    logger.info(f"Applied class weights: {class_weights}")
                else:
                    # Train with transformed labels
                    self.model.fit(X_train_values, y_train_transformed)
            else:
                # No transformation needed
                self.model.fit(X_train_values, y_train_values)
        else:
            # For other models, train normally
            self.model.fit(X_train_values, y_train_values)
        
        # Store feature importance if available
        self._store_feature_importance()
        
        # Store training metadata
        self.metadata["training"] = {
            "samples": len(X_train),
            "features": X_train.shape[1],
            "class_distribution": {
                str(label): int(count) 
                for label, count in zip(*np.unique(y_train_values, return_counts=True))
            },
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Trained {self.model_type} model with {X_train.shape[0]} samples")
    
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Make class predictions.
        
        Args:
            X: Input features
            
        Returns:
            Predicted class labels
        """
        if self.model is None:
            raise ValueError("Model has not been trained yet")
        
        # Convert to numpy array if needed
        if isinstance(X, pd.DataFrame):
            X_values = X.values
        else:
            X_values = X
        
        # Make predictions
        predictions = self.model.predict(X_values)
        
        # For XGBoost with transformed labels, convert back to original format
        if self.model_type == "xgboost" and self.inverse_label_map is not None:
            return np.array([self.inverse_label_map[p] for p in predictions])
        
        return predictions
    
    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Make probability predictions.
        
        Args:
            X: Input features
            
        Returns:
            Predicted class probabilities
        """
        if self.model is None:
            raise ValueError("Model has not been trained yet")
        
        # Convert to numpy array if needed
        if isinstance(X, pd.DataFrame):
            X_values = X.values
        else:
            X_values = X
        
        # Make probability predictions
        probas = self.model.predict_proba(X_values)
        
        # For XGBoost with transformed labels, we need to reorder the columns
        if self.model_type == "xgboost" and self.label_map is not None:
            # Create a mapping that tells us where to move each column
            # This is needed because the probability columns correspond to class indices
            new_order = [self.label_map[label] for label in sorted(self.label_map.keys())]
            return probas[:, new_order]
        
        return probas
    
    def _store_feature_importance(self) -> None:
        """Store feature importance if available."""
        if hasattr(self.model, "feature_importances_"):
            self.feature_importance = self.model.feature_importances_
            
            # Store in metadata
            if self.feature_names is not None:
                importance_dict = {
                    name: float(importance)
                    for name, importance in zip(self.feature_names, self.feature_importance)
                }
                self.metadata["feature_importance"] = importance_dict
                
        elif self.model_type == "logistic":
            # For logistic regression, use coefficients as feature importance
            if self.n_classes == 2:
                self.feature_importance = np.abs(self.model.coef_[0])
            else:
                # Average absolute coefficients for multi-class
                self.feature_importance = np.mean(np.abs(self.model.coef_), axis=0)
            
            # Store in metadata
            if self.feature_names is not None:
                importance_dict = {
                    name: float(importance)
                    for name, importance in zip(self.feature_names, self.feature_importance)
                }
                self.metadata["feature_importance"] = importance_dict
    
    def _calculate_financial_metrics(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_pred: np.ndarray,
        returns: Union[pd.Series, np.ndarray],
        transaction_cost: float = 0.0001
    ) -> Dict[str, float]:
        """
        Calculate financial metrics for trading models.
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            returns: Future returns for each prediction
            transaction_cost: Trading cost per transaction
            
        Returns:
            Dictionary of financial metrics
        """
        # Convert to numpy arrays if needed
        if isinstance(y_true, pd.Series):
            y_true = y_true.values
        if isinstance(returns, pd.Series):
            returns = returns.values
        
        # Filter for positions where we predicted action (long or short)
        is_position = (y_pred != 0)
        
        # Initialize metrics
        metrics = {
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "total_trades": 0
        }
        
        # If no positions, return zero metrics
        if not np.any(is_position):
            return metrics
        
        # Calculate actual returns from our predictions
        position_returns = np.zeros_like(returns)
        position_returns[y_pred == 1] = returns[y_pred == 1]  # Long
        position_returns[y_pred == -1] = -returns[y_pred == -1]  # Short
        
        # Apply transaction costs
        position_returns[is_position] -= transaction_cost
        
        # Calculate win rate
        winning_trades = np.sum(position_returns[is_position] > 0)
        total_trades = np.sum(is_position)
        metrics["win_rate"] = winning_trades / total_trades if total_trades > 0 else 0.0
        metrics["total_trades"] = int(total_trades)
        
        # Calculate profit factor
        profits = position_returns[position_returns > 0]
        losses = position_returns[position_returns < 0]
        
        gross_profits = np.sum(profits) if len(profits) > 0 else 0
        gross_losses = np.abs(np.sum(losses)) if len(losses) > 0 else 0
        
        # Avoid division by zero
        metrics["profit_factor"] = gross_profits / gross_losses if gross_losses > 0 else float('inf')
        
        # Calculate average profit and loss
        metrics["avg_profit"] = np.mean(profits) if len(profits) > 0 else 0.0
        metrics["avg_loss"] = np.mean(losses) if len(losses) > 0 else 0.0
        
        # Calculate Sharpe ratio
        mean_return = np.mean(position_returns[is_position])
        std_return = np.std(position_returns[is_position])
        metrics["sharpe_ratio"] = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0.0
        
        # Calculate max drawdown
        # Use cumulative product to account for compounding
        cum_returns = np.cumprod(1 + position_returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdowns = (running_max - cum_returns) / running_max
        metrics["max_drawdown"] = np.max(drawdowns) if len(drawdowns) > 0 else 0.0
        
        return metrics
    
    def cross_validate(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        returns: Optional[Union[pd.Series, np.ndarray]] = None,
        n_splits: int = 5,
        time_series: bool = True,
        scoring: str = "f1_weighted",
        plot: bool = False
    ) -> Dict[str, Any]:
        """
        Perform cross-validation.
        
        Args:
            X: Features
            y: Target labels
            returns: Optional returns for financial metrics
            n_splits: Number of CV splits
            time_series: Whether to use time series splitting
            scoring: Scoring metric
            plot: Whether to plot results
            
        Returns:
            Dictionary of cross-validation results
        """
        # Convert to numpy arrays if needed
        if isinstance(X, pd.DataFrame):
            X_values = X.values
            feature_names = X.columns.tolist()
        else:
            X_values = X
            feature_names = [f"feature_{i}" for i in range(X.shape[1])]
            
        if isinstance(y, pd.Series):
            y_values = y.values
        else:
            y_values = y
            
        if returns is not None and isinstance(returns, pd.Series):
            returns_values = returns.values
        else:
            returns_values = returns
        
        # Create cross-validation strategy
        if time_series:
            cv = TimeSeriesSplit(n_splits=n_splits)
        else:
            from sklearn.model_selection import StratifiedKFold
            cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=self.random_state)
        
        # Perform cross-validation
        standard_scores = {
            "accuracy": [],
            "precision": [],
            "recall": [],
            "f1": []
        }
        
        financial_scores = {
            "profit_factor": [],
            "win_rate": [],
            "sharpe_ratio": [],
            "max_drawdown": []
        }
        
        # Manually iterate through CV splits
        for train_idx, test_idx in cv.split(X_values, y_values):
            # Split data
            X_train_cv, X_test_cv = X_values[train_idx], X_values[test_idx]
            y_train_cv, y_test_cv = y_values[train_idx], y_values[test_idx]
            
            # Create and train model for this split
            cv_model = self._create_model()
            
            # XGBoost special handling
            if self.model_type == "xgboost" and self.n_classes > 2:
                # Check if we need to transform labels
                unique_labels = np.unique(y_train_cv)
                if -1 in unique_labels or not np.array_equal(unique_labels, np.arange(len(unique_labels))):
                    # Map labels to consecutive integers
                    label_map = {label: i for i, label in enumerate(sorted(unique_labels))}
                    y_train_cv_transformed = np.array([label_map[label] for label in y_train_cv])
                    
                    # Train with transformed labels
                    cv_model.fit(X_train_cv, y_train_cv_transformed)
                    
                    # Predict
                    y_pred_cv_transformed = cv_model.predict(X_test_cv)
                    
                    # Convert back to original labels
                    inverse_label_map = {v: k for k, v in label_map.items()}
                    y_pred_cv = np.array([inverse_label_map[label] for label in y_pred_cv_transformed])
                else:
                    # No transformation needed
                    cv_model.fit(X_train_cv, y_train_cv)
                    y_pred_cv = cv_model.predict(X_test_cv)
            else:
                # Regular training and prediction
                cv_model.fit(X_train_cv, y_train_cv)
                y_pred_cv = cv_model.predict(X_test_cv)
            
            # Calculate standard metrics
            standard_scores["accuracy"].append(accuracy_score(y_test_cv, y_pred_cv))
            standard_scores["precision"].append(precision_score(y_test_cv, y_pred_cv, average="weighted"))
            standard_scores["recall"].append(recall_score(y_test_cv, y_pred_cv, average="weighted"))
            standard_scores["f1"].append(f1_score(y_test_cv, y_pred_cv, average="weighted"))
            
            # Calculate financial metrics if returns provided
            if returns is not None:
                returns_test_cv = returns_values[test_idx]
                fin_metrics = self._calculate_financial_metrics(y_test_cv, y_pred_cv, returns_test_cv)
                
                financial_scores["profit_factor"].append(fin_metrics["profit_factor"])
                financial_scores["win_rate"].append(fin_metrics["win_rate"])
                financial_scores["sharpe_ratio"].append(fin_metrics["sharpe_ratio"])
                financial_scores["max_drawdown"].append(fin_metrics["max_drawdown"])
        
        # Calculate mean and std for all metrics
        cv_results = {}
        for metric, values in standard_scores.items():
            cv_results[f"{metric}_mean"] = float(np.mean(values))
            cv_results[f"{metric}_std"] = float(np.std(values))
            cv_results[f"{metric}_values"] = values
        
        # Add financial metrics if available
        if returns is not None:
            for metric, values in financial_scores.items():
                cv_results[f"{metric}_mean"] = float(np.mean(values))
                cv_results[f"{metric}_std"] = float(np.std(values))
                cv_results[f"{metric}_values"] = values
        
        # Store in metadata
        self.metadata["cross_validation"] = {
            "n_splits": n_splits,
            "time_series": time_series,
            "accuracy": cv_results["accuracy_mean"],
            "precision": cv_results["precision_mean"],
            "recall": cv_results["recall_mean"],
            "f1": cv_results["f1_mean"],
            "timestamp": datetime.now().isoformat()
        }
        
        # Add financial metrics to metadata if available
        if returns is not None:
            self.metadata["cross_validation"].update({
                "profit_factor": cv_results["profit_factor_mean"],
                "win_rate": cv_results["win_rate_mean"],
                "sharpe_ratio": cv_results["sharpe_ratio_mean"],
                "max_drawdown": cv_results["max_drawdown_mean"]
            })
        
        # Plot results if requested
        if plot:
            self._plot_cv_results(cv_results, returns is not None)
        
        return cv_results
    
    def _plot_cv_results(self, cv_results: Dict[str, Any], include_financial: bool = False) -> None:
        """
        Plot cross-validation results.
        
        Args:
            cv_results: Cross-validation results
            include_financial: Whether to include financial metrics
        """
        # Set up plot
        if include_financial:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        else:
            fig, ax1 = plt.subplots(1, 1, figsize=(8, 6))
        
        # Plot standard metrics
        standard_metrics = ["accuracy", "precision", "recall", "f1"]
        means = [cv_results[f"{m}_mean"] for m in standard_metrics]
        stds = [cv_results[f"{m}_std"] for m in standard_metrics]
        
        # Plot mean scores
        ax1.bar(range(len(standard_metrics)), means, yerr=stds, capsize=10)
        ax1.set_xlabel("Metric")
        ax1.set_ylabel("Score")
        ax1.set_title("Cross-validation Results - Standard Metrics")
        ax1.set_xticks(range(len(standard_metrics)))
        ax1.set_xticklabels(standard_metrics)
        ax1.set_ylim(0, 1)
        
        # Add text annotations
        for i, metric in enumerate(standard_metrics):
            ax1.text(i, means[i] + stds[i] + 0.05,
                    f"{means[i]:.3f} ± {stds[i]:.3f}",
                    ha="center", va="center", fontsize=9)
        
        # Plot financial metrics if available
        if include_financial:
            financial_metrics = ["profit_factor", "win_rate", "sharpe_ratio"]
            means = [cv_results[f"{m}_mean"] for m in financial_metrics]
            stds = [cv_results[f"{m}_std"] for m in financial_metrics]
            
            # Plot mean scores
            ax2.bar(range(len(financial_metrics)), means, yerr=stds, capsize=10)
            ax2.set_xlabel("Metric")
            ax2.set_ylabel("Score")
            ax2.set_title("Cross-validation Results - Financial Metrics")
            ax2.set_xticks(range(len(financial_metrics)))
            ax2.set_xticklabels(financial_metrics)
            
            # Add text annotations
            for i, metric in enumerate(financial_metrics):
                ax2.text(i, means[i] + stds[i] + 0.05,
                        f"{means[i]:.3f} ± {stds[i]:.3f}",
                        ha="center", va="center", fontsize=9)
        
        plt.tight_layout()
        plt.show()
    
    def save(self, directory: str = "models") -> Dict[str, str]:
        """
        Save model to disk.
        
        Args:
            directory: Directory to save the model
            
        Returns:
            Dictionary with paths to saved files
        """
        # Call parent save method to save metadata
        saved_files = super().save(directory)
        
        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        
        # Save model file
        model_path = os.path.join(directory, f"{self.name}.joblib")
        
        # Save label mapping if exists
        if self.label_map is not None:
            self.metadata["label_map"] = self.label_map
            self.metadata["inverse_label_map"] = self.inverse_label_map
        
        # Save model with joblib
        joblib.dump(self.model, model_path)
        saved_files["model"] = model_path
        
        logger.info(f"Model saved to {model_path}")
        
        return saved_files
    
    @classmethod
    def load(cls, name: str, directory: str = "models") -> "ClassicMLModel":
        """
        Load model from disk.
        
        Args:
            name: Model name
            directory: Directory where model is saved
            
        Returns:
            Loaded model instance
        """
        # Load metadata
        metadata_path = os.path.join(directory, f"{name}_metadata.json")
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        # Create model instance
        model_instance = cls(
            model_type=metadata["model_type"],
            name=metadata["name"],
            n_classes=metadata["n_classes"],
            random_state=metadata["random_state"],
            model_params=metadata.get("model_params", {}),
            metadata=metadata
        )
        
        # Load model
        model_path = os.path.join(directory, f"{name}.joblib")
        model_instance.model = joblib.load(model_path)
        
        # Load feature names
        model_instance.feature_names = metadata.get("feature_names")
        
        # Load label mapping if exists
        if "label_map" in metadata and "inverse_label_map" in metadata:
            model_instance.label_map = metadata["label_map"]
            model_instance.inverse_label_map = metadata["inverse_label_map"]
        
        # Store feature importance if available
        if hasattr(model_instance.model, "feature_importances_"):
            model_instance.feature_importance = model_instance.model.feature_importances_
        elif model_instance.model_type == "logistic":
            if model_instance.n_classes == 2:
                model_instance.feature_importance = np.abs(model_instance.model.coef_[0])
            else:
                model_instance.feature_importance = np.mean(np.abs(model_instance.model.coef_), axis=0)
        
        logger.info(f"Model loaded from {model_path}")
        
        return model_instance


class EnsembleModel(MLModelBase):
    """
    Ensemble model that combines multiple base models.
    """
    
    def __init__(
        self,
        models: List[Union[ClassicMLModel, "EnsembleModel"]],
        name: Optional[str] = None,
        ensemble_method: str = "weighted",
        weights: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize ensemble model.
        
        Args:
            models: List of base models
            name: Model name (default: auto-generated)
            ensemble_method: Method for combining predictions
                "vote": Majority vote for classification
                "average": Simple average of probabilities
                "weighted": Weighted average of probabilities
            weights: Weights for each model (default: equal)
            metadata: Additional metadata
        """
        # Get n_classes from the first model
        if not models:
            raise ValueError("At least one model must be provided")
        
        n_classes = models[0].n_classes
        random_state = models[0].random_state
        
        # Check if all models have the same number of classes
        for model in models:
            if model.n_classes != n_classes:
                raise ValueError("All models must have the same number of classes")
        
        # Initialize base class
        super().__init__(
            name=name,
            model_type="ensemble",
            n_classes=n_classes,
            random_state=random_state,
            metadata=metadata
        )
        
        # Store models
        self.models = models
        self.ensemble_method = ensemble_method
        
        # Set weights
        if weights is None:
            self.weights = [1.0 / len(models)] * len(models)
        else:
            if len(weights) != len(models):
                raise ValueError("Number of weights must match number of models")
            
            # Normalize weights
            sum_weights = sum(weights)
            self.weights = [w / sum_weights for w in weights]
        
        # Update metadata
        self.metadata.update({
            "ensemble_method": self.ensemble_method,
            "weights": self.weights,
            "base_models": [model.name for model in self.models]
        })
        
        # No need to train ensemble - it's composed of already trained models
        # But we'll store feature names from base models
        feature_names_sets = []
        
        for model in models:
            if model.feature_names:
                feature_names_sets.append(set(model.feature_names))
        
        # Use common feature names across all models
        if feature_names_sets:
            common_features = set.intersection(*feature_names_sets)
            self.feature_names = list(common_features)
        else:
            self.feature_names = None
    
    def train(
        self,
        X_train: Union[pd.DataFrame, np.ndarray],
        y_train: Union[pd.Series, np.ndarray],
        validation_data: Optional[Tuple[Union[pd.DataFrame, np.ndarray], Union[pd.Series, np.ndarray]]] = None,
        feature_names: Optional[List[str]] = None
    ) -> None:
        """
        Train method for ensemble - not needed as base models are already trained.
        This method just stores metadata.
        
        Args:
            X_train: Training features
            y_train: Training labels
            validation_data: Optional (X_val, y_val) tuple for validation
            feature_names: Optional list of feature names
        """
        # Store feature names
        self._store_feature_names(X_train, feature_names)
        
        # Store training metadata
        self.metadata["training"] = {
            "samples": len(X_train),
            "features": X_train.shape[1],
            "class_distribution": {
                str(label): int(count) 
                for label, count in pd.Series(y_train).value_counts().items()
            },
            "timestamp": datetime.now().isoformat(),
            "note": "Ensemble model does not require training - using pretrained base models"
        }
        
        logger.info(f"Ensemble model metadata updated with {X_train.shape[0]} samples")
    
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Make class predictions by combining base model predictions.
        
        Args:
            X: Input features
            
        Returns:
            Predicted class labels
        """
        if self.ensemble_method == "vote":
            # Get predictions from all models
            predictions = []
            
            for model in self.models:
                y_pred = model.predict(X)
                predictions.append(y_pred)
            
            # Convert to array
            predictions = np.array(predictions)
            
            # Majority vote
            if self.n_classes == 2:
                # Binary classification
                votes = np.sum(predictions, axis=0)
                return (votes >= len(predictions) / 2).astype(int)
            else:
                # Multi-class classification
                # Count votes for each class
                votes = np.zeros((len(X), self.n_classes))
                
                for i in range(len(predictions)):
                    for j in range(len(X)):
                        votes[j, predictions[i, j]] += 1
                
                # Return class with most votes
                return np.argmax(votes, axis=1)
        else:
            # Use probabilities
            probas = self.predict_proba(X)
            
            # Return class with highest probability
            return np.argmax(probas, axis=1)
    
    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Make probability predictions by combining base model probabilities.
        
        Args:
            X: Input features
            
        Returns:
            Predicted class probabilities
        """
        # Get probabilities from all models
        all_probas = []
        all_weights = []
        
        for i, model in enumerate(self.models):
            try:
                y_proba = model.predict_proba(X)
                all_probas.append(y_proba)
                all_weights.append(self.weights[i])
            except Exception as e:
                logger.warning(f"Error getting probabilities from model {model.name}: {e}")
        
        if not all_probas:
            raise ValueError("No valid probability predictions from base models")
        
        # Normalize weights for models that provided valid predictions
        sum_weights = sum(all_weights)
        norm_weights = [w / sum_weights for w in all_weights]
        
        # Combine probabilities
        if self.ensemble_method == "average":
            # Simple average
            probas = np.mean(all_probas, axis=0)
        elif self.ensemble_method == "weighted":
            # Weighted average
            probas = np.zeros_like(all_probas[0])
            for i in range(len(all_probas)):
                probas += all_probas[i] * norm_weights[i]
        else:
            # Vote method (convert to one-hot)
            predictions = [np.argmax(p, axis=1) for p in all_probas]
            
            # Create one-hot encoding
            probas = np.zeros((len(X), self.n_classes))
            
            for i, pred in enumerate(predictions):
                for j in range(len(X)):
                    probas[j, pred[j]] += norm_weights[i]
            
            # Normalize
            row_sums = probas.sum(axis=1, keepdims=True)
            probas = probas / row_sums
        
        return probas
    
    def save(self, directory: str = "models", save_base_models: bool = False) -> Dict[str, str]:
        """
        Save ensemble model to disk.
        
        Args:
            directory: Directory to save the model
            save_base_models: Whether to also save base models
            
        Returns:
            Dictionary with paths to saved files
        """
        # Call parent save method to save metadata
        saved_files = super().save(directory)
        
        # Save base models if requested
        if save_base_models:
            for model in self.models:
                model_files = model.save(directory)
                saved_files.update(model_files)
        
        logger.info(f"Ensemble model saved to {saved_files['metadata']}")
        
        return saved_files
    
    @classmethod
    def load(cls, name: str, directory: str = "models", 
             load_base_models: bool = True) -> "EnsembleModel":
        """
        Load ensemble model from disk.
        
        Args:
            name: Model name
            directory: Directory where model is saved
            load_base_models: Whether to also load base models
            
        Returns:
            Loaded ensemble model instance
        """
        # Load metadata
        metadata_path = os.path.join(directory, f"{name}_metadata.json")
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        # Check if this is really an ensemble model
        if metadata.get("model_type") != "ensemble":
            raise ValueError(f"Model {name} is not an ensemble model")
        
        # Load base models if requested
        models = []
        
        if load_base_models:
            for base_model_name in metadata.get("base_models", []):
                try:
                    # Try loading as ClassicMLModel first
                    model = ClassicMLModel.load(base_model_name, directory)
                    models.append(model)
                except Exception as e:
                    # If that fails, it might be an ensemble itself
                    try:
                        model = cls.load(base_model_name, directory, load_base_models=True)
                        models.append(model)
                    except Exception as e2:
                        logger.warning(f"Could not load base model {base_model_name}: {e2}")
        
        # If we couldn't load any base models, raise error
        if load_base_models and not models:
            raise ValueError(f"Could not load any base models for ensemble {name}")
        
        # Create ensemble instance
        ensemble = cls(
            models=models,
            name=name,
            ensemble_method=metadata.get("ensemble_method", "weighted"),
            weights=metadata.get("weights"),
            metadata=metadata
        )
        
        logger.info(f"Ensemble model loaded from {metadata_path}")
        
        return ensemble


# Helper functions for model creation and utilities

def create_model(
    model_type: str,
    n_classes: int = 3,
    name: Optional[str] = None,
    model_params: Optional[Dict[str, Any]] = None
) -> Union[ClassicMLModel, MLModelBase]:
    """
    Create a new ML model of the specified type.
    
    Args:
        model_type: Type of model to create
            "random_forest", "xgboost", "logistic" for classic ML models
        n_classes: Number of target classes
        name: Model name (auto-generated if None)
        model_params: Model hyperparameters
        
    Returns:
        Initialized model instance
    """
    # Create classic ML model
    if model_type in ["random_forest", "xgboost", "logistic"]:
        return ClassicMLModel(
            model_type=model_type,
            n_classes=n_classes,
            name=name,
            model_params=model_params
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")

def compare_models(
    models: List[Union[ClassicMLModel, EnsembleModel]],
    X_test: Union[pd.DataFrame, np.ndarray],
    y_test: Union[pd.Series, np.ndarray],
    returns: Optional[Union[pd.Series, np.ndarray]] = None,
    plot: bool = True
) -> pd.DataFrame:
    """
    Compare multiple models on the same test data.
    
    Args:
        models: List of models to compare
        X_test: Test features
        y_test: Test labels
        returns: Optional returns for financial metrics
        plot: Whether to plot comparison results
        
    Returns:
        DataFrame with comparison results
    """
    # Evaluate each model
    results = []
    
    for model in models:
        # Evaluate model
        metrics = model.evaluate(X_test, y_test, returns, plot=False)
        
        # Add model name and type
        metrics_row = {
            "model_name": model.name,
            "model_type": model.model_type,
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"]
        }
        
        # Add financial metrics if available
        if "profit_factor" in metrics:
            metrics_row.update({
                "profit_factor": metrics["profit_factor"],
                "win_rate": metrics["win_rate"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown": metrics["max_drawdown"]
            })
        
        results.append(metrics_row)
    
    # Create DataFrame
    comparison_df = pd.DataFrame(results)
    
    # Sort by F1 score
    comparison_df = comparison_df.sort_values("f1", ascending=False)
    
    # Plot comparison if requested
    if plot:
        # Set up plot
        if "profit_factor" in comparison_df.columns:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        else:
            fig, ax1 = plt.subplots(1, 1, figsize=(8, 6))
        
        # Plot standard metrics
        metrics = ["accuracy", "precision", "recall", "f1"]
        n_models = len(comparison_df)
        
        # Create a grouped bar chart
        bar_width = 0.2
        index = np.arange(n_models)
        
        for i, metric in enumerate(metrics):
            ax1.bar(index + i * bar_width, comparison_df[metric], bar_width, label=metric)
        
        ax1.set_xlabel("Model")
        ax1.set_ylabel("Score")
        ax1.set_title("Model Comparison - Standard Metrics")
        ax1.set_xticks(index + bar_width * (len(metrics) - 1) / 2)
        ax1.set_xticklabels(comparison_df["model_name"], rotation=45)
        ax1.legend()
        
        # Plot financial metrics if available
        if "profit_factor" in comparison_df.columns:
            financial_metrics = ["profit_factor", "win_rate", "sharpe_ratio"]
            
            for i, metric in enumerate(financial_metrics):
                ax2.bar(index + i * bar_width, comparison_df[metric], bar_width, label=metric)
            
            ax2.set_xlabel("Model")
            ax2.set_ylabel("Score")
            ax2.set_title("Model Comparison - Financial Metrics")
            ax2.set_xticks(index + bar_width * (len(financial_metrics) - 1) / 2)
            ax2.set_xticklabels(comparison_df["model_name"], rotation=45)
            ax2.legend()
        
        plt.tight_layout()
        plt.show()
    
    return comparison_df

def create_ensemble(
    models: List[Union[ClassicMLModel, EnsembleModel]],
    name: Optional[str] = None,
    ensemble_method: str = "weighted",
    weights: Optional[List[float]] = None
) -> EnsembleModel:
    """
    Create an ensemble model from existing models.
    
    Args:
        models: List of base models
        name: Model name (auto-generated if None)
        ensemble_method: Method for combining predictions
            "vote", "average", or "weighted"
        weights: Weights for each model (equal if None)
        
    Returns:
        Ensemble model instance
    """
    return EnsembleModel(
        models=models,
        name=name,
        ensemble_method=ensemble_method,
        weights=weights
    )