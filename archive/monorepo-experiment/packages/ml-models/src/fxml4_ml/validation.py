"""
Model validation utilities for time-series data.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

from fxml4_core.logging import get_logger
from fxml4_ml.models import MLModel

logger = get_logger(__name__)


class TimeSeriesCrossValidator:
    """Time-series cross-validation for ML models."""
    
    def __init__(
        self,
        n_splits: int = 5,
        gap: int = 0,
        max_train_size: Optional[int] = None
    ):
        self.n_splits = n_splits
        self.gap = gap
        self.max_train_size = max_train_size
        self.validation_results = []
    
    def evaluate(
        self,
        model: MLModel,
        X: pd.DataFrame,
        y: pd.Series,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Evaluate model using time-series cross-validation."""
        if metrics is None:
            metrics = ["accuracy", "precision", "recall", "f1_score"]
        
        tscv = TimeSeriesSplit(
            n_splits=self.n_splits,
            gap=self.gap,
            max_train_size=self.max_train_size
        )
        
        fold_results = []
        
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            logger.info(f"Evaluating fold {fold + 1}/{self.n_splits}")
            
            # Split data
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            # Train model
            model.fit(X_train, y_train)
            
            # Make predictions
            y_pred = model.predict(X_val)
            y_proba = model.predict_proba(X_val) if hasattr(model, 'predict_proba') else None
            
            # Calculate metrics
            fold_metrics = self._calculate_metrics(y_val, y_pred, metrics)
            fold_metrics['fold'] = fold
            fold_metrics['train_size'] = len(train_idx)
            fold_metrics['val_size'] = len(val_idx)
            
            fold_results.append(fold_metrics)
        
        # Aggregate results
        aggregated_results = self._aggregate_results(fold_results, metrics)
        
        # Store results
        validation_result = {
            "model_name": model.name,
            "timestamp": datetime.now().isoformat(),
            "n_splits": self.n_splits,
            "fold_results": fold_results,
            "aggregated_results": aggregated_results
        }
        
        self.validation_results.append(validation_result)
        
        return validation_result
    
    def walk_forward_validation(
        self,
        model: MLModel,
        X: pd.DataFrame,
        y: pd.Series,
        initial_train_size: int,
        step_size: int = 1,
        retrain_every: int = 1
    ) -> Dict[str, Any]:
        """Perform walk-forward validation."""
        results = []
        n_samples = len(X)
        
        # Initialize training window
        train_start = 0
        train_end = initial_train_size
        
        # Track if model needs retraining
        steps_since_retrain = 0
        
        while train_end < n_samples - 1:
            # Define validation window
            val_start = train_end
            val_end = min(train_end + step_size, n_samples)
            
            # Split data
            X_train = X.iloc[train_start:train_end]
            y_train = y.iloc[train_start:train_end]
            X_val = X.iloc[val_start:val_end]
            y_val = y.iloc[val_start:val_end]
            
            # Retrain model if needed
            if steps_since_retrain == 0:
                model.fit(X_train, y_train)
                logger.debug(f"Model retrained on samples {train_start}:{train_end}")
            
            # Make predictions
            y_pred = model.predict(X_val)
            
            # Calculate metrics
            step_metrics = self._calculate_metrics(y_val, y_pred, ["accuracy"])
            step_metrics['step'] = len(results)
            step_metrics['train_size'] = len(X_train)
            step_metrics['val_size'] = len(X_val)
            
            results.append(step_metrics)
            
            # Update windows
            train_end += step_size
            steps_since_retrain = (steps_since_retrain + 1) % retrain_every
        
        # Aggregate results
        avg_accuracy = np.mean([r['accuracy'] for r in results])
        
        logger.info(f"Walk-forward validation complete - Average accuracy: {avg_accuracy:.4f}")
        
        return {
            "model_name": model.name,
            "timestamp": datetime.now().isoformat(),
            "initial_train_size": initial_train_size,
            "step_size": step_size,
            "retrain_every": retrain_every,
            "n_steps": len(results),
            "step_results": results,
            "avg_accuracy": avg_accuracy
        }
    
    def plot_validation_results(self, save_path: Optional[str] = None) -> None:
        """Plot validation results."""
        if not self.validation_results:
            logger.warning("No validation results to plot")
            return
        
        latest_result = self.validation_results[-1]
        fold_results = latest_result['fold_results']
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle(f"Validation Results for {latest_result['model_name']}", fontsize=16)
        
        # Plot 1: Metrics by fold
        ax = axes[0, 0]
        metrics = ['accuracy', 'precision', 'recall', 'f1_score']
        folds = range(len(fold_results))
        
        for metric in metrics:
            values = [r[metric] for r in fold_results]
            ax.plot(folds, values, marker='o', label=metric)
        
        ax.set_xlabel('Fold')
        ax.set_ylabel('Score')
        ax.set_title('Metrics by Fold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Plot 2: Training size vs performance
        ax = axes[0, 1]
        train_sizes = [r['train_size'] for r in fold_results]
        accuracies = [r['accuracy'] for r in fold_results]
        
        ax.plot(train_sizes, accuracies, marker='o', color='blue')
        ax.set_xlabel('Training Size')
        ax.set_ylabel('Accuracy')
        ax.set_title('Training Size vs Performance')
        ax.grid(True, alpha=0.3)
        
        # Plot 3: Box plot of metrics
        ax = axes[1, 0]
        metric_data = []
        metric_labels = []
        
        for metric in metrics:
            values = [r[metric] for r in fold_results]
            metric_data.append(values)
            metric_labels.append(metric)
        
        ax.boxplot(metric_data, labels=metric_labels)
        ax.set_ylabel('Score')
        ax.set_title('Metric Distribution')
        ax.grid(True, alpha=0.3)
        
        # Plot 4: Summary statistics
        ax = axes[1, 1]
        ax.axis('off')
        
        summary_text = f"Cross-Validation Summary\n\n"
        aggregated = latest_result['aggregated_results']
        
        for metric in metrics:
            mean_val = aggregated[f'{metric}_mean']
            std_val = aggregated[f'{metric}_std']
            summary_text += f"{metric.capitalize()}: {mean_val:.4f} (±{std_val:.4f})\n"
        
        ax.text(0.1, 0.5, summary_text, fontsize=12, verticalalignment='center')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Validation plot saved to {save_path}")
        
        plt.show()
    
    def _calculate_metrics(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
        metrics: List[str]
    ) -> Dict[str, float]:
        """Calculate specified metrics."""
        results = {}
        
        if "accuracy" in metrics:
            results["accuracy"] = accuracy_score(y_true, y_pred)
        
        if "precision" in metrics:
            results["precision"] = precision_score(
                y_true, y_pred, average='weighted', zero_division=0
            )
        
        if "recall" in metrics:
            results["recall"] = recall_score(
                y_true, y_pred, average='weighted', zero_division=0
            )
        
        if "f1_score" in metrics:
            results["f1_score"] = f1_score(
                y_true, y_pred, average='weighted', zero_division=0
            )
        
        return results
    
    def _aggregate_results(
        self,
        fold_results: List[Dict[str, Any]],
        metrics: List[str]
    ) -> Dict[str, float]:
        """Aggregate results across folds."""
        aggregated = {}
        
        for metric in metrics:
            values = [r[metric] for r in fold_results]
            aggregated[f'{metric}_mean'] = np.mean(values)
            aggregated[f'{metric}_std'] = np.std(values)
            aggregated[f'{metric}_min'] = np.min(values)
            aggregated[f'{metric}_max'] = np.max(values)
        
        return aggregated