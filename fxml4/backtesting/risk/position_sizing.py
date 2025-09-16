"""Position sizing algorithms for backtesting.

This module consolidates all position sizing algorithms for risk management.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional, Tuple

import numpy as np
import pandas as pd

from fxml4.backtesting.event import SignalEvent


class StopLossType(Enum):
    """Types of stop-loss orders."""

    FIXED = "fixed"
    PERCENTAGE = "percentage"
    VOLATILITY = "volatility"
    TRAILING = "trailing"
    CHANDELIER = "chandelier"
    TIME = "time"


class PositionSizer(ABC):
    """Base class for position sizing algorithms."""

    @abstractmethod
    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate position size based on a signal.

        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price of the asset.

        Returns:
            Position size (quantity).
        """
        pass


class FixedPositionSizer(PositionSizer):
    """Fixed position sizer.

    Allocates a fixed amount of capital to each position.
    """

    def __init__(self, fixed_amount: float = 1000.0):
        """Initialize a fixed position sizer.

        Args:
            fixed_amount: Fixed amount of capital to allocate.
        """
        self.fixed_amount = fixed_amount

    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate fixed position size.

        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price of the asset.

        Returns:
            Position size (quantity).
        """
        # Use signal's fixed amount if provided, otherwise use default
        fixed_amount = signal.signal_data.get("fixed_amount", self.fixed_amount)

        # Calculate quantity based on current price
        quantity = fixed_amount / current_price if current_price > 0 else 0

        return quantity


class PercentagePositionSizer(PositionSizer):
    """Percentage position sizer.

    Allocates a percentage of the portfolio equity to each position.
    """

    def __init__(self, percentage: float = 0.02):
        """Initialize a percentage position sizer.

        Args:
            percentage: Percentage of portfolio equity to allocate (0.02 = 2%).
        """
        self.percentage = percentage

    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate percentage position size.

        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price of the asset.

        Returns:
            Position size (quantity).
        """
        # Use signal's percentage if provided, otherwise use default
        percentage = signal.signal_data.get("equity_pct", self.percentage)

        # Calculate amount to allocate
        amount = portfolio.equity * percentage

        # Calculate quantity based on current price
        quantity = amount / current_price if current_price > 0 else 0

        return quantity


class VolatilityPositionSizer(PositionSizer):
    """Volatility-based position sizer.

    Adjusts position size based on market volatility.
    """

    def __init__(
        self,
        risk_pct: float = 0.01,
        volatility_window: int = 20,
        atr_multiplier: float = 2.0,
    ):
        """Initialize a volatility-based position sizer.

        Args:
            risk_pct: Percentage of portfolio equity to risk per trade.
            volatility_window: Window for volatility/ATR calculation.
            atr_multiplier: Multiplier for ATR (stop distance).
        """
        self.risk_pct = risk_pct
        self.volatility_window = volatility_window
        self.atr_multiplier = atr_multiplier

    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate volatility-based position size.

        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price of the asset.

        Returns:
            Position size (quantity).
        """
        # Use signal's risk percentage if provided, otherwise use default
        risk_pct = signal.signal_data.get("risk_pct", self.risk_pct)

        # Calculate risk amount in currency
        risk_amount = portfolio.equity * risk_pct

        # Get market data from portfolio
        symbol = signal.symbol
        market_data = portfolio.market_data.get(symbol)

        if market_data is None or len(market_data) < self.volatility_window:
            # Not enough data, use simple calculation
            default_stop_distance = current_price * 0.01  # 1% default
            quantity = risk_amount / default_stop_distance
            return quantity

        # Calculate ATR (Average True Range)
        atr = self._calculate_atr(market_data, self.volatility_window)

        # Calculate stop distance based on ATR
        stop_distance = atr * self.atr_multiplier

        # If stop loss is explicitly provided in signal, use it instead
        if "stop_loss" in signal.signal_data:
            stop_loss = signal.signal_data["stop_loss"]
            stop_distance = abs(current_price - stop_loss)

        # Calculate position size based on risk amount and stop distance
        quantity = risk_amount / stop_distance if stop_distance > 0 else 0

        return quantity

    def _calculate_atr(self, market_data: pd.DataFrame, window: int) -> float:
        """Calculate Average True Range (ATR).

        Args:
            market_data: Market data with OHLC prices.
            window: Window size for ATR calculation.

        Returns:
            ATR value.
        """
        # Extract high, low, close prices
        high = market_data["high"].values
        low = market_data["low"].values
        close = market_data["close"].values

        # Calculate true range
        tr1 = np.abs(high[1:] - low[1:])
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])

        # True range is the maximum of the three
        tr = np.vstack([tr1, tr2, tr3]).max(axis=0)

        # Calculate ATR (simple average of true range over window)
        atr = np.mean(tr[-window:]) if len(tr) >= window else np.mean(tr)

        return atr


class KellyPositionSizer(PositionSizer):
    """Kelly criterion position sizer.

    Adjusts position size based on the Kelly criterion, using win rate and win/loss ratio.
    """

    def __init__(
        self,
        default_win_rate: float = 0.5,
        default_win_loss_ratio: float = 1.0,
        max_allocation: float = 0.2,
        lookback_trades: int = 20,
        fraction: float = 0.5,  # Half-Kelly for more conservative sizing
    ):
        """Initialize a Kelly position sizer.

        Args:
            default_win_rate: Default win rate to use if no history available.
            default_win_loss_ratio: Default win/loss ratio if no history available.
            max_allocation: Maximum allocation as a fraction of equity.
            lookback_trades: Number of past trades to consider for statistics.
            fraction: Fraction of Kelly to use (0.5 = Half Kelly).
        """
        self.default_win_rate = default_win_rate
        self.default_win_loss_ratio = default_win_loss_ratio
        self.max_allocation = max_allocation
        self.lookback_trades = lookback_trades
        self.fraction = fraction

    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate Kelly position size.

        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price of the asset.

        Returns:
            Position size (quantity).
        """
        # Calculate win rate and win/loss ratio from portfolio history
        win_rate, win_loss_ratio = self._calculate_statistics(portfolio, signal.symbol)

        # Allow overriding with signal data
        win_rate = signal.signal_data.get("win_rate", win_rate)
        win_loss_ratio = signal.signal_data.get("win_loss_ratio", win_loss_ratio)

        # Calculate Kelly percentage
        kelly_pct = win_rate - ((1 - win_rate) / win_loss_ratio)

        # Apply fraction and max allocation
        allocation_pct = min(kelly_pct * self.fraction, self.max_allocation)

        # Ensure non-negative allocation
        allocation_pct = max(allocation_pct, 0)

        # Calculate allocation amount
        amount = portfolio.equity * allocation_pct

        # Calculate quantity
        quantity = amount / current_price if current_price > 0 else 0

        return quantity

    def _calculate_statistics(
        self, portfolio: Any, symbol: Optional[str] = None
    ) -> Tuple[float, float]:
        """Calculate win rate and win/loss ratio from portfolio history.

        Args:
            portfolio: Portfolio instance.
            symbol: Symbol to filter trades by (optional).

        Returns:
            Tuple of (win_rate, win_loss_ratio).
        """
        closed_positions = portfolio.get_closed_positions()

        # Filter by symbol if provided
        if symbol:
            closed_positions = [
                p for p in closed_positions if p.get("symbol") == symbol
            ]

        # Limit to recent trades
        closed_positions = (
            closed_positions[-self.lookback_trades :] if closed_positions else []
        )

        if not closed_positions:
            return self.default_win_rate, self.default_win_loss_ratio

        # Calculate win rate
        winning_trades = [p for p in closed_positions if p.get("realized_pnl", 0) > 0]
        win_rate = len(winning_trades) / len(closed_positions)

        # Calculate average win and loss
        if winning_trades:
            avg_win = sum(p.get("realized_pnl", 0) for p in winning_trades) / len(
                winning_trades
            )
        else:
            avg_win = 0

        losing_trades = [p for p in closed_positions if p.get("realized_pnl", 0) <= 0]
        if losing_trades:
            avg_loss = abs(
                sum(p.get("realized_pnl", 0) for p in losing_trades)
                / len(losing_trades)
            )
        else:
            avg_loss = 1  # Avoid division by zero

        # Calculate win/loss ratio
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0

        return win_rate, win_loss_ratio


__all__ = [
    "StopLossType",
    "PositionSizer",
    "FixedPositionSizer",
    "PercentagePositionSizer",
    "VolatilityPositionSizer",
    "KellyPositionSizer",
]
