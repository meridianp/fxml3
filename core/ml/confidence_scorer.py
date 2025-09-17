"""
Confidence Scorer for ML Pipeline

TDD-driven implementation for calculating confidence scores from ensemble predictions.
Following Green phase - minimal implementation to pass tests.
"""

from typing import Dict, Any, Optional
import numpy as np
from collections import Counter


class ConfidenceScorer:
    """Calculate confidence scores for ML predictions."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize confidence scorer."""
        self.config = config or {}
        self.details = {}

    def calculate_confidence(self, model_predictions: Dict[str, Dict]) -> float:
        """Calculate overall confidence score from multiple model predictions."""
        if not model_predictions:
            return 0.0

        signals = []
        probabilities = []
        weights = {}

        for model_name, prediction in model_predictions.items():
            signal = prediction.get("signal", "HOLD")
            prob = prediction.get("probability", 0.5)

            signals.append(signal)
            probabilities.append(prob)

            if model_name == "random_forest":
                weights[model_name] = 0.4
            elif model_name == "xgboost":
                weights[model_name] = 0.35
            elif model_name == "lstm":
                weights[model_name] = 0.25
            else:
                weights[model_name] = 1.0 / len(model_predictions)

        signal_counts = Counter(signals)
        majority_signal = signal_counts.most_common(1)[0][0]
        agreement_score = signal_counts[majority_signal] / len(signals)

        weighted_confidence = 0.0
        total_weight = 0.0

        for model_name, prediction in model_predictions.items():
            if prediction.get("signal") == majority_signal:
                weight = weights[model_name]
                prob = prediction.get("probability", 0.5)
                weighted_confidence += weight * prob
                total_weight += weight

        if total_weight > 0:
            weighted_confidence /= total_weight

        overall_confidence = (agreement_score * 0.4) + (weighted_confidence * 0.6)

        self.details = {
            "agreement_score": agreement_score,
            "weighted_confidence": weighted_confidence,
            "signal_distribution": dict(signal_counts),
            "majority_signal": majority_signal,
            "model_weights": weights,
        }

        return min(1.0, max(0.0, overall_confidence))

    def get_details(self) -> Dict[str, Any]:
        """Get detailed breakdown of confidence calculation."""
        return self.details
