"""
Position sizing strategies for FXML4.

This module provides various position sizing algorithms.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


class PositionSizer(ABC):
    """Base class for position sizing strategies."""

    @abstractmethod
    def calculate_size(
        self,
        signal: Dict[str, Any],
        account_balance: float,
        current_price: float,
        market_conditions: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate position size."""
        pass


class KellyCriterionSizer(PositionSizer):
    """Kelly Criterion position sizing."""

    def __init__(
        self,
        win_rate: float = 0.55,
        avg_win_loss_ratio: float = 1.5,
        kelly_fraction: float = 0.25,
    ):
        """
        Initialize Kelly Criterion sizer.

        Args:
            win_rate: Historical win rate
            avg_win_loss_ratio: Average win/loss ratio
            kelly_fraction: Fraction of Kelly to use (for safety)
        """
        self.win_rate = win_rate
        self.avg_win_loss_ratio = avg_win_loss_ratio
        self.kelly_fraction = kelly_fraction

    def calculate_size(
        self,
        signal: Dict[str, Any],
        account_balance: float,
        current_price: float,
        market_conditions: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate position size using Kelly Criterion."""
        # Adjust win rate based on signal strength
        adjusted_win_rate = self.win_rate
        if "strength" in signal:
            # Scale win rate by signal strength
            adjusted_win_rate = (
                0.5 + (signal["strength"] - 0.5) * (self.win_rate - 0.5) / 0.5
            )

        # Kelly formula: f = p - q/b
        # where p = win probability, q = loss probability, b = win/loss ratio
        q = 1 - adjusted_win_rate
        kelly_full = adjusted_win_rate - (q / self.avg_win_loss_ratio)

        # Apply Kelly fraction for safety
        kelly_position = max(0, kelly_full * self.kelly_fraction)

        # Cap at maximum position size (e.g., 10% of capital)
        kelly_position = min(kelly_position, 0.1)

        # Convert to position size
        position_value = account_balance * kelly_position
        position_size = position_value / current_price

        return position_size


class VolatilityBasedSizer(PositionSizer):
    """Volatility-based position sizing."""

    def __init__(
        self,
        target_risk: float = 0.02,
        lookback_period: int = 20,
        volatility_scalar: float = 1.0,
    ):
        """
        Initialize volatility-based sizer.

        Args:
            target_risk: Target risk per trade (e.g., 2%)
            lookback_period: Period for volatility calculation
            volatility_scalar: Multiplier for volatility adjustment
        """
        self.target_risk = target_risk
        self.lookback_period = lookback_period
        self.volatility_scalar = volatility_scalar

    def calculate_size(
        self,
        signal: Dict[str, Any],
        account_balance: float,
        current_price: float,
        market_conditions: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate position size based on volatility."""
        # Get volatility from market conditions or use default
        volatility = 0.01  # Default 1% volatility

        if market_conditions:
            if "volatility" in market_conditions:
                volatility = market_conditions["volatility"]
            elif "atr" in market_conditions:
                # Use ATR as proxy for volatility
                atr = market_conditions["atr"]
                volatility = atr / current_price

        # Adjust volatility by scalar
        adjusted_volatility = volatility * self.volatility_scalar

        # Calculate position size to achieve target risk
        if adjusted_volatility > 0:
            position_weight = self.target_risk / adjusted_volatility
        else:
            position_weight = self.target_risk  # Fallback

        # Cap position size
        position_weight = min(position_weight, 0.1)  # Max 10% of capital

        # Convert to position size
        position_value = account_balance * position_weight
        position_size = position_value / current_price

        return position_size


class FixedRiskSizer(PositionSizer):
    """Fixed risk position sizing."""

    def __init__(self, risk_per_trade: float = 0.02, stop_loss_pct: float = 0.02):
        """
        Initialize fixed risk sizer.

        Args:
            risk_per_trade: Risk per trade as fraction of capital
            stop_loss_pct: Default stop loss percentage
        """
        self.risk_per_trade = risk_per_trade
        self.stop_loss_pct = stop_loss_pct

    def calculate_size(
        self,
        signal: Dict[str, Any],
        account_balance: float,
        current_price: float,
        market_conditions: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate position size for fixed risk."""
        # Get stop loss from signal or use default
        stop_loss = signal.get("stop_loss")

        if stop_loss is None:
            # Use percentage-based stop loss
            if signal.get("type") == "BUY":
                stop_loss = current_price * (1 - self.stop_loss_pct)
            else:
                stop_loss = current_price * (1 + self.stop_loss_pct)

        # Calculate price risk
        price_risk = abs(current_price - stop_loss)

        if price_risk == 0:
            return 0

        # Calculate position size
        risk_amount = account_balance * self.risk_per_trade
        position_size = risk_amount / price_risk

        # Cap at maximum position value (10% of capital)
        max_position_value = account_balance * 0.1
        max_position_size = max_position_value / current_price

        return min(position_size, max_position_size)


class DynamicPositionSizer(PositionSizer):
    """Dynamic position sizing based on multiple factors."""

    def __init__(
        self,
        base_risk: float = 0.02,
        max_risk: float = 0.05,
        confidence_weight: float = 0.3,
        volatility_weight: float = 0.3,
        trend_weight: float = 0.4,
    ):
        """
        Initialize dynamic position sizer.

        Args:
            base_risk: Base risk per trade
            max_risk: Maximum risk per trade
            confidence_weight: Weight for signal confidence
            volatility_weight: Weight for volatility adjustment
            trend_weight: Weight for trend strength
        """
        self.base_risk = base_risk
        self.max_risk = max_risk
        self.confidence_weight = confidence_weight
        self.volatility_weight = volatility_weight
        self.trend_weight = trend_weight

        # Sub-sizers
        self.volatility_sizer = VolatilityBasedSizer()
        self.fixed_risk_sizer = FixedRiskSizer(risk_per_trade=base_risk)

    def calculate_size(
        self,
        signal: Dict[str, Any],
        account_balance: float,
        current_price: float,
        market_conditions: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate dynamic position size."""
        # Start with base position size
        base_size = self.fixed_risk_sizer.calculate_size(
            signal, account_balance, current_price, market_conditions
        )

        # Adjustment factors
        confidence_factor = 1.0
        volatility_factor = 1.0
        trend_factor = 1.0

        # Confidence adjustment
        if "strength" in signal:
            # Higher confidence -> larger position
            confidence_factor = 0.5 + signal["strength"]

        # Volatility adjustment
        if market_conditions and "volatility" in market_conditions:
            # Lower volatility -> larger position
            vol = market_conditions["volatility"]
            volatility_factor = 1.5 - min(vol / 0.02, 1.5)

        # Trend adjustment
        if market_conditions and "trend_strength" in market_conditions:
            # Stronger trend -> larger position
            trend_factor = 0.5 + market_conditions["trend_strength"]

        # Calculate weighted adjustment
        total_weight = (
            self.confidence_weight + self.volatility_weight + self.trend_weight
        )

        adjustment = (
            confidence_factor * self.confidence_weight
            + volatility_factor * self.volatility_weight
            + trend_factor * self.trend_weight
        ) / total_weight

        # Apply adjustment
        adjusted_size = base_size * adjustment

        # Cap at maximum risk
        max_position_value = account_balance * self.max_risk
        max_position_size = max_position_value / current_price

        return min(adjusted_size, max_position_size)


# Factory function
def create_position_sizer(method: str = "fixed_risk", **kwargs) -> PositionSizer:
    """
    Create a position sizer instance.

    Args:
        method: Sizing method ('fixed_risk', 'kelly', 'volatility', 'dynamic')
        **kwargs: Method-specific parameters

    Returns:
        PositionSizer instance
    """
    if method == "kelly":
        return KellyCriterionSizer(**kwargs)
    elif method == "volatility":
        return VolatilityBasedSizer(**kwargs)
    elif method == "dynamic":
        return DynamicPositionSizer(**kwargs)
    else:
        return FixedRiskSizer(**kwargs)
