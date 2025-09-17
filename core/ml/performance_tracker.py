"""
Model Performance Tracker for ML Pipeline

TDD-driven implementation for tracking and evaluating model performance.
Following Green phase - minimal implementation to pass tests.
"""

from typing import Dict, List, Any, Optional
from collections import defaultdict
import numpy as np


class ModelPerformanceTracker:
    """Track and evaluate model performance over time."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize performance tracker."""
        self.config = config or {}
        self.predictions = defaultdict(list)
        self.model_metrics = defaultdict(
            lambda: {
                "total": 0,
                "correct": 0,
                "true_positives": 0,
                "false_positives": 0,
                "true_negatives": 0,
                "false_negatives": 0,
            }
        )

    def add_prediction(
        self, model: str, prediction: str, actual: str, confidence: float
    ):
        """Add a prediction result for tracking."""
        self.predictions[model].append(
            {
                "prediction": prediction,
                "actual": actual,
                "confidence": confidence,
                "correct": prediction == actual,
            }
        )

        metrics = self.model_metrics[model]
        metrics["total"] += 1

        if prediction == actual:
            metrics["correct"] += 1
            if prediction == "BUY":
                metrics["true_positives"] += 1
            elif prediction == "SELL":
                metrics["true_negatives"] += 1
        else:
            if prediction == "BUY":
                metrics["false_positives"] += 1
            elif prediction == "SELL":
                metrics["false_negatives"] += 1

    def get_model_metrics(self, model: str) -> Dict[str, float]:
        """Get performance metrics for a specific model."""
        metrics = self.model_metrics[model]

        if metrics["total"] == 0:
            return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1_score": 0.0}

        accuracy = metrics["correct"] / metrics["total"]

        tp = metrics["true_positives"]
        fp = metrics["false_positives"]
        fn = metrics["false_negatives"]

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0

        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
        }

    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get metrics for all tracked models."""
        return {
            model: self.get_model_metrics(model) for model in self.model_metrics.keys()
        }
