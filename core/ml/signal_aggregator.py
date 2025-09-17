"""
Signal Aggregator for ML Pipeline

TDD-driven implementation for aggregating multiple ML trading signals.
Following Green phase - minimal implementation to pass tests.
"""

from typing import Dict, List, Any, Optional
from collections import Counter
import numpy as np


class SignalAggregator:
    """Aggregate multiple trading signals from different models or timeframes."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize signal aggregator."""
        self.config = config or {}
        self.aggregation_method = self.config.get("method", "weighted_voting")

    def aggregate_signals(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate multiple signals into a single consensus signal."""
        if not signals:
            return {}

        symbol = signals[0].get("symbol", "EUR/USD")

        action_votes = Counter()
        confidences = []
        confidence_by_action = {"BUY": [], "SELL": [], "HOLD": []}

        for signal in signals:
            action = signal.get("action", "HOLD")
            confidence = signal.get("confidence", 0.5)

            action_votes[action] += 1
            confidences.append(confidence)

            if action in confidence_by_action:
                confidence_by_action[action].append(confidence)

        most_common_action = action_votes.most_common(1)[0][0]

        winning_confidences = confidence_by_action[most_common_action]
        aggregated_confidence = (
            np.mean(winning_confidences) if winning_confidences else 0.5
        )

        return {
            "symbol": symbol,
            "action": most_common_action,
            "confidence": aggregated_confidence,
            "signal_count": len(signals),
            "action_distribution": dict(action_votes),
            "confidence_stats": {
                "mean": np.mean(confidences),
                "std": np.std(confidences),
                "min": np.min(confidences),
                "max": np.max(confidences),
            },
        }
