"""
Base strategy module for FXML4.

This module provides the base class for all trading strategies.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class BaseStrategy(ABC):
    """Base class for all trading strategies."""

    def __init__(
        self, name: str = "BaseStrategy", params: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize base strategy.

        Args:
            name: Strategy name
            params: Strategy parameters
        """
        self.name = name
        self.params = params or {}
        self.positions = {}
        self.orders = []
        self.performance = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
        }

    @abstractmethod
    def generate_signals(
        self, data: pd.DataFrame, features: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Generate trading signals.

        Args:
            data: Market data
            features: Additional features

        Returns:
            DataFrame with signals
        """
        pass

    @abstractmethod
    def calculate_position_size(
        self, signal: Dict[str, Any], account_balance: float, current_price: float
    ) -> float:
        """
        Calculate position size for a signal.

        Args:
            signal: Trading signal
            account_balance: Current account balance
            current_price: Current asset price

        Returns:
            Position size
        """
        pass

    def validate_signal(
        self, signal: Dict[str, Any], current_state: Dict[str, Any]
    ) -> bool:
        """
        Validate a trading signal.

        Args:
            signal: Trading signal to validate
            current_state: Current market/account state

        Returns:
            True if signal is valid
        """
        # Default validation
        if signal.get("strength", 0) < self.params.get("min_signal_strength", 0.5):
            return False

        # Check if we already have a position
        symbol = signal.get("symbol")
        if symbol in self.positions and self.positions[symbol]["quantity"] > 0:
            # Already have a position
            if signal["type"] == self.positions[symbol]["side"]:
                return False  # Don't add to existing position

        return True

    def apply_risk_management(
        self, signal: Dict[str, Any], position_size: float, current_price: float
    ) -> Tuple[float, float]:
        """
        Apply risk management rules.

        Args:
            signal: Trading signal
            position_size: Calculated position size
            current_price: Current price

        Returns:
            Tuple of (stop_loss, take_profit)
        """
        # Default risk management
        risk_reward_ratio = self.params.get("risk_reward_ratio", 2.0)
        stop_loss_pct = self.params.get("stop_loss_pct", 0.02)

        if signal["type"] == "BUY":
            stop_loss = current_price * (1 - stop_loss_pct)
            take_profit = current_price * (1 + stop_loss_pct * risk_reward_ratio)
        else:  # SELL
            stop_loss = current_price * (1 + stop_loss_pct)
            take_profit = current_price * (1 - stop_loss_pct * risk_reward_ratio)

        return stop_loss, take_profit

    def update_performance(self, trade_result: Dict[str, Any]):
        """Update performance metrics."""
        self.performance["total_trades"] += 1

        pnl = trade_result.get("pnl", 0)
        self.performance["total_pnl"] += pnl

        if pnl > 0:
            self.performance["winning_trades"] += 1
        else:
            self.performance["losing_trades"] += 1

        # Update max drawdown
        if self.performance["total_pnl"] < self.performance.get("peak_pnl", 0):
            drawdown = self.performance["peak_pnl"] - self.performance["total_pnl"]
            self.performance["max_drawdown"] = max(
                self.performance["max_drawdown"], drawdown
            )
        else:
            self.performance["peak_pnl"] = self.performance["total_pnl"]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        total_trades = self.performance["total_trades"]
        if total_trades == 0:
            return self.performance

        win_rate = self.performance["winning_trades"] / total_trades

        return {
            **self.performance,
            "win_rate": win_rate,
            "profit_factor": self._calculate_profit_factor(),
            "sharpe_ratio": self._calculate_sharpe_ratio(),
        }

    def _calculate_profit_factor(self) -> float:
        """Calculate profit factor."""
        # Simplified calculation
        if self.performance["losing_trades"] == 0:
            return float("inf")

        avg_win = self.performance.get("total_wins", 0) / max(
            self.performance["winning_trades"], 1
        )
        avg_loss = abs(
            self.performance.get("total_losses", 0)
            / max(self.performance["losing_trades"], 1)
        )

        if avg_loss == 0:
            return float("inf")

        return avg_win / avg_loss

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio."""
        # Simplified calculation
        returns = self.performance.get("returns", [])
        if not returns:
            return 0.0

        returns_array = np.array(returns)
        if len(returns_array) < 2:
            return 0.0

        return np.sqrt(252) * np.mean(returns_array) / np.std(returns_array)

    def reset(self):
        """Reset strategy state."""
        self.positions = {}
        self.orders = []
        self.performance = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
        }


class TrendFollowingStrategy(BaseStrategy):
    """Simple trend following strategy implementation."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize trend following strategy."""
        default_params = {
            "fast_ma": 20,
            "slow_ma": 50,
            "min_signal_strength": 0.6,
            "stop_loss_pct": 0.02,
            "risk_reward_ratio": 2.0,
        }
        if params:
            default_params.update(params)

        super().__init__(name="TrendFollowing", params=default_params)

    def generate_signals(
        self, data: pd.DataFrame, features: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """Generate trend following signals."""
        signals = pd.DataFrame(index=data.index)

        # Calculate moving averages
        fast_ma = data["close"].rolling(self.params["fast_ma"]).mean()
        slow_ma = data["close"].rolling(self.params["slow_ma"]).mean()

        # Generate signals
        signals["signal"] = 0
        signals.loc[fast_ma > slow_ma, "signal"] = 1
        signals.loc[fast_ma < slow_ma, "signal"] = -1

        # Calculate signal strength
        signals["strength"] = abs(fast_ma - slow_ma) / slow_ma

        return signals

    def calculate_position_size(
        self, signal: Dict[str, Any], account_balance: float, current_price: float
    ) -> float:
        """Calculate position size using fixed percentage."""
        risk_per_trade = self.params.get("risk_per_trade", 0.02)
        position_value = account_balance * risk_per_trade

        return position_value / current_price
