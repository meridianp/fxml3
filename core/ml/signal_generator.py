"""
Signal Generator for ML Pipeline

TDD-driven implementation of trading signal generation from ML predictions.
Following Green phase - minimal implementation to pass tests.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any


class SignalGenerator:
    """Generate trading signals from ML predictions."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        confidence_threshold: float = 0.65,
    ):
        """Initialize signal generator."""
        self.config = config or {}
        self.confidence_threshold = (
            confidence_threshold
            if config is None
            else config.get("confidence_threshold", 0.65)
        )
        self.active_signals = {}

    def generate_signal(
        self, symbol: str, prediction: Dict[str, Any], current_price: float
    ) -> Dict[str, Any]:
        """Generate trading signal from ML prediction."""
        signal = {
            "symbol": symbol,
            "action": prediction["signal"],
            "confidence": prediction["confidence"],
            "price": current_price,
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "model": prediction.get("model", "ensemble"),
                "prediction_details": prediction,
            },
        }

        # Store active signal
        self.active_signals[symbol] = signal

        return signal

    def filter_signal(self, prediction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter signal based on confidence threshold."""
        if prediction["confidence"] >= self.confidence_threshold:
            return prediction
        return None

    def apply_risk_adjustment(
        self, signal: Dict[str, Any], risk_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Apply risk adjustments to trading signal."""
        adjusted = signal.copy()

        # Calculate position size based on risk metrics
        base_position = 100000  # Base position size

        # Adjust for portfolio VaR
        var_adjustment = 1.0
        if risk_metrics.get("portfolio_var", 0) > 0.015:  # If VaR > 1.5%
            var_adjustment = 0.5  # Reduce position size

        # Adjust for drawdown
        dd_adjustment = 1.0
        if risk_metrics.get("max_drawdown", 0) > 0.03:  # If drawdown > 3%
            dd_adjustment = 0.7

        # Adjust for Sharpe ratio
        sharpe_adjustment = min(1.5, max(0.5, risk_metrics.get("sharpe_ratio", 1.0)))

        # Calculate adjusted position size
        adjusted["position_size"] = int(
            base_position
            * var_adjustment
            * dd_adjustment
            * sharpe_adjustment
            * signal["confidence"]
        )

        # Calculate stop loss and take profit
        if signal["action"] == "BUY":
            adjusted["stop_loss"] = signal["price"] * 0.995  # 0.5% stop loss
            adjusted["take_profit"] = signal["price"] * 1.01  # 1% take profit
        elif signal["action"] == "SELL":
            adjusted["stop_loss"] = signal["price"] * 1.005
            adjusted["take_profit"] = signal["price"] * 0.99
        else:  # HOLD
            adjusted["stop_loss"] = None
            adjusted["take_profit"] = None

        return adjusted
