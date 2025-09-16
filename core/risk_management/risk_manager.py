"""
Risk Manager for FXML4.

This module provides comprehensive risk management functionality.

WARNING: This module is deprecated and will be removed in a future version.
Please migrate to the unified risk management system:
- Use BaseRiskManager, LiveRiskManager, BacktestRiskManager, or BrokerRiskManager
- Import from fxml4.risk_management.base, .live, .backtest, or .broker
"""

import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Issue deprecation warning when this module is imported
warnings.warn(
    "fxml4.risk_management.risk_manager is deprecated. "
    "Please migrate to the unified risk management system in fxml4.risk_management.base, .live, .backtest, or .broker",
    DeprecationWarning,
    stacklevel=2,
)


@dataclass
class RiskConfig:
    """Risk management configuration."""

    max_position_size: float = 0.1  # 10% of capital
    max_portfolio_risk: float = 0.06  # 6% total portfolio risk
    max_correlation: float = 0.7  # Maximum correlation between positions
    max_daily_loss: float = 0.03  # 3% daily loss limit
    max_drawdown: float = 0.15  # 15% maximum drawdown
    min_risk_reward: float = 1.5  # Minimum risk/reward ratio
    use_trailing_stop: bool = True
    trailing_stop_distance: float = 0.02  # 2% trailing stop
    max_leverage: float = 1.0  # Maximum leverage
    position_sizing_method: str = "fixed_risk"  # 'fixed_risk', 'kelly', 'volatility'


class RiskManager:
    """Comprehensive risk management system."""

    def __init__(self, config: Optional[RiskConfig] = None):
        """Initialize risk manager."""
        self.config = config or RiskConfig()
        self.positions = {}
        self.daily_pnl = []
        self.peak_portfolio_value = 0
        self.current_portfolio_value = 0

    def validate_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        account_balance: float,
        current_positions: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Validate a trade against risk rules.

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check position size
        position_value = quantity * price
        if position_value > account_balance * self.config.max_position_size:
            return (
                False,
                f"Position size exceeds limit ({self.config.max_position_size*100}% of capital)",
            )

        # Check daily loss limit
        if self._check_daily_loss_exceeded():
            return False, "Daily loss limit exceeded"

        # Check maximum drawdown
        if self._check_max_drawdown_exceeded():
            return False, "Maximum drawdown limit exceeded"

        # Check portfolio risk
        total_risk = self._calculate_portfolio_risk(current_positions)
        new_risk = self._calculate_position_risk(quantity, price)

        if total_risk + new_risk > account_balance * self.config.max_portfolio_risk:
            return (
                False,
                f"Total portfolio risk would exceed limit ({self.config.max_portfolio_risk*100}%)",
            )

        # Check correlation with existing positions
        if not self._check_correlation_limits(symbol, current_positions):
            return (
                False,
                f"Position correlation exceeds limit ({self.config.max_correlation})",
            )

        return True, "Trade validated"

    def calculate_position_size(
        self,
        symbol: str,
        signal_strength: float,
        account_balance: float,
        current_price: float,
        stop_loss: float,
        volatility: Optional[float] = None,
    ) -> float:
        """Calculate optimal position size based on risk parameters."""
        if self.config.position_sizing_method == "fixed_risk":
            return self._fixed_risk_position_size(
                account_balance, current_price, stop_loss
            )
        elif self.config.position_sizing_method == "kelly":
            return self._kelly_position_size(
                signal_strength, account_balance, current_price
            )
        elif self.config.position_sizing_method == "volatility":
            return self._volatility_position_size(
                account_balance, current_price, volatility or 0.01
            )
        else:
            # Default to fixed risk
            return self._fixed_risk_position_size(
                account_balance, current_price, stop_loss
            )

    def _fixed_risk_position_size(
        self, account_balance: float, current_price: float, stop_loss: float
    ) -> float:
        """Calculate position size using fixed risk method."""
        risk_amount = account_balance * 0.02  # 2% risk per trade
        price_risk = abs(current_price - stop_loss)

        if price_risk == 0:
            return 0

        position_size = risk_amount / price_risk

        # Apply maximum position size limit
        max_position_value = account_balance * self.config.max_position_size
        max_position_size = max_position_value / current_price

        return min(position_size, max_position_size)

    def _kelly_position_size(
        self,
        win_probability: float,
        account_balance: float,
        current_price: float,
        avg_win_loss_ratio: float = 1.5,
    ) -> float:
        """Calculate position size using Kelly Criterion."""
        # Kelly formula: f = p - q/b
        # where p = win probability, q = loss probability, b = win/loss ratio
        q = 1 - win_probability
        kelly_fraction = win_probability - (q / avg_win_loss_ratio)

        # Apply Kelly fraction with safety factor
        kelly_fraction = max(0, min(kelly_fraction * 0.25, 0.25))  # Cap at 25%

        position_value = account_balance * kelly_fraction
        return position_value / current_price

    def _volatility_position_size(
        self, account_balance: float, current_price: float, volatility: float
    ) -> float:
        """Calculate position size based on volatility."""
        # Target 1% portfolio volatility contribution
        target_volatility = 0.01

        if volatility == 0:
            return 0

        position_weight = target_volatility / volatility
        position_weight = min(position_weight, self.config.max_position_size)

        position_value = account_balance * position_weight
        return position_value / current_price

    def update_stop_loss(
        self, symbol: str, current_price: float, position: Dict[str, Any]
    ) -> Optional[float]:
        """Update stop loss for a position (trailing stop)."""
        if not self.config.use_trailing_stop:
            return position.get("stop_loss")

        entry_price = position["entry_price"]
        current_stop = position.get("stop_loss", 0)
        side = position["side"]

        if side == "BUY":
            # For long positions
            new_stop = current_price * (1 - self.config.trailing_stop_distance)
            if new_stop > current_stop:
                return new_stop
        else:
            # For short positions
            new_stop = current_price * (1 + self.config.trailing_stop_distance)
            if current_stop == 0 or new_stop < current_stop:
                return new_stop

        return current_stop

    def _check_daily_loss_exceeded(self) -> bool:
        """Check if daily loss limit is exceeded."""
        if not self.daily_pnl:
            return False

        today_pnl = sum(
            pnl for date, pnl in self.daily_pnl if date.date() == datetime.now().date()
        )

        return today_pnl < -self.config.max_daily_loss * self.current_portfolio_value

    def _check_max_drawdown_exceeded(self) -> bool:
        """Check if maximum drawdown is exceeded."""
        if self.peak_portfolio_value == 0:
            return False

        current_drawdown = (
            self.peak_portfolio_value - self.current_portfolio_value
        ) / self.peak_portfolio_value

        return current_drawdown > self.config.max_drawdown

    def _calculate_portfolio_risk(self, positions: Dict[str, Any]) -> float:
        """Calculate total portfolio risk."""
        total_risk = 0

        for symbol, position in positions.items():
            position_risk = self._calculate_position_risk(
                position["quantity"], position["current_price"]
            )
            total_risk += position_risk

        return total_risk

    def _calculate_position_risk(self, quantity: float, price: float) -> float:
        """Calculate risk for a single position."""
        # Simplified: assume 2% price risk
        return quantity * price * 0.02

    def _check_correlation_limits(
        self, symbol: str, current_positions: Dict[str, Any]
    ) -> bool:
        """Check if correlation limits are respected."""
        # Simplified: check currency pairs correlation
        correlated_pairs = {
            "EURUSD": ["GBPUSD", "EURGBP"],
            "GBPUSD": ["EURUSD", "EURGBP"],
            "USDJPY": ["EURJPY", "GBPJPY"],
            "AUDUSD": ["NZDUSD", "AUDNZD"],
            "NZDUSD": ["AUDUSD", "AUDNZD"],
        }

        if symbol not in correlated_pairs:
            return True

        correlated_count = sum(
            1
            for pos_symbol in current_positions
            if pos_symbol in correlated_pairs.get(symbol, [])
        )

        # Allow maximum 2 correlated positions
        return correlated_count < 2

    def update_portfolio_value(self, value: float):
        """Update current portfolio value."""
        self.current_portfolio_value = value
        if value > self.peak_portfolio_value:
            self.peak_portfolio_value = value

    def add_daily_pnl(self, pnl: float):
        """Add daily P&L entry."""
        self.daily_pnl.append((datetime.now(), pnl))

        # Keep only last 30 days
        cutoff_date = datetime.now() - timedelta(days=30)
        self.daily_pnl = [
            (date, pnl) for date, pnl in self.daily_pnl if date > cutoff_date
        ]

    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics."""
        return {
            "current_drawdown": self._calculate_current_drawdown(),
            "daily_pnl": sum(
                pnl
                for date, pnl in self.daily_pnl
                if date.date() == datetime.now().date()
            ),
            "portfolio_risk": self._calculate_portfolio_risk(self.positions),
            "position_count": len(self.positions),
            "peak_value": self.peak_portfolio_value,
            "current_value": self.current_portfolio_value,
        }

    def _calculate_current_drawdown(self) -> float:
        """Calculate current drawdown percentage."""
        if self.peak_portfolio_value == 0:
            return 0

        return (
            self.peak_portfolio_value - self.current_portfolio_value
        ) / self.peak_portfolio_value
