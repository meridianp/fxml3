"""
Model Drift Detector for ML Pipeline

TDD-driven implementation for detecting model drift and distribution changes.
Following Green phase - minimal implementation to pass tests.
"""

from typing import Dict, Any, Optional
import numpy as np
from scipy import stats


class ModelDriftDetector:
    """Detect drift in model predictions and data distributions."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize drift detector."""
        self.config = config or {}
        self.significance_level = self.config.get("significance_level", 0.05)
        self.statistics = {}

    def detect_drift(self, historical: np.ndarray, current: np.ndarray) -> bool:
        """Detect if there is significant drift between historical and current data."""
        if len(historical) < 2 or len(current) < 2:
            return False

        ks_statistic, p_value = stats.ks_2samp(historical, current)

        mean_shift = np.abs(np.mean(current) - np.mean(historical))
        std_historical = np.std(historical)

        if std_historical > 0:
            drift_score = mean_shift / std_historical
        else:
            drift_score = mean_shift

        drift_detected = bool(p_value < self.significance_level or drift_score > 2.0)

        self.statistics = {
            "ks_statistic": float(ks_statistic),
            "p_value": float(p_value),
            "drift_score": float(drift_score),
            "mean_shift": float(mean_shift),
            "historical_mean": float(np.mean(historical)),
            "current_mean": float(np.mean(current)),
            "historical_std": float(np.std(historical)),
            "current_std": float(np.std(current)),
        }

        return drift_detected

    def get_statistics(self) -> Dict[str, float]:
        """Get detailed drift detection statistics."""
        return self.statistics

    def calculate_psi(
        self, expected: np.ndarray, actual: np.ndarray, bins: int = 10
    ) -> float:
        """Calculate Population Stability Index (PSI)."""
        breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))

        expected_counts = np.histogram(expected, bins=breakpoints)[0]
        actual_counts = np.histogram(actual, bins=breakpoints)[0]

        expected_percents = expected_counts / len(expected)
        actual_percents = actual_counts / len(actual)

        expected_percents = np.where(expected_percents == 0, 0.0001, expected_percents)
        actual_percents = np.where(actual_percents == 0, 0.0001, actual_percents)

        psi = np.sum(
            (actual_percents - expected_percents)
            * np.log(actual_percents / expected_percents)
        )

        return float(psi)
