"""
Position sizing module for Elliott Wave trading strategies.

This module implements various position sizing algorithms including
Kelly criterion optimization, volatility-adjusted position sizing,
and scaling methods for entering and exiting positions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml3.strategy.entry_signals import EntrySignal, SignalStrength, SignalType
from fxml3.strategy.risk_management import RiskManager


class PositionSizingMethod(Enum):
    """Position sizing method types."""

    FIXED_RISK = 1  # Fixed percentage risk (e.g., 2% of account per trade)
    KELLY = 2  # Kelly criterion optimization
    OPTIMAL_F = 3  # Optimal f (variation of Kelly)
    VOLATILITY_ADJUSTED = 4  # Position size based on volatility
    FIXED_SIZE = 5  # Fixed position size
    SCALING = 6  # Scaling in/out of positions


@dataclass
class PositionSize:
    """Represents a position size calculation result."""

    size: float  # The calculated position size
    method: PositionSizingMethod  # Method used for calculation
    risk_amount: float  # Risk amount in account currency
    risk_percentage: float  # Risk as percentage of account
    confidence: float  # Confidence level (0.0 to 1.0)
    metadata: Dict[str, Any] = None  # Additional metadata


class PositionSizer:
    """
    Implements position sizing algorithms for trading strategies.

    This class calculates optimal position sizes based on various methods,
    including Kelly criterion, volatility-adjusted sizing, and scaling methods.
    """

    def __init__(
        self,
        risk_manager: Optional[RiskManager] = None,
        default_risk_percent: float = 0.02,  # 2% of account per trade
        max_risk_percent: float = 0.05,  # 5% maximum risk per trade
        kelly_fraction: float = 0.5,  # Half-Kelly for more conservative sizing
        rolling_window: int = 30,  # Window for historical analysis
        use_compounding: bool = True,  # Whether to use compounding in calculations
    ):
        """
        Initialize the position sizer.

        Args:
            risk_manager: Risk manager for stop loss and risk calculations
            default_risk_percent: Default risk percentage per trade
            max_risk_percent: Maximum allowable risk percentage per trade
            kelly_fraction: Fraction of full Kelly to use (0.0 to 1.0)
            rolling_window: Window size for historical analysis
            use_compounding: Whether to use compounding in calculations
        """
        self.risk_manager = risk_manager or RiskManager()
        self.default_risk_percent = default_risk_percent
        self.max_risk_percent = max_risk_percent
        self.kelly_fraction = kelly_fraction
        self.rolling_window = rolling_window
        self.use_compounding = use_compounding

        # Trade history for Kelly calculation
        self.trade_history = []

    def calculate_position_size(
        self,
        entry_signal: EntrySignal,
        account_size: float,
        method: PositionSizingMethod = PositionSizingMethod.FIXED_RISK,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> PositionSize:
        """
        Calculate position size based on the specified method.

        Args:
            entry_signal: The entry signal to calculate position size for
            account_size: Current account size
            method: Position sizing method to use
            stop_loss: Optional stop loss price (if not provided, will use signal's)
            take_profit: Optional take profit price (if not provided, will use signal's)
            custom_data: Optional custom data for specialized calculations

        Returns:
            PositionSize object with calculated size and metadata
        """
        # Extract needed values from entry signal
        entry_price = entry_signal.entry_price
        signal_stop_loss = entry_signal.stop_loss if stop_loss is None else stop_loss
        signal_take_profit = (
            entry_signal.take_profit if take_profit is None else take_profit
        )

        # Calculate risk amount (in price terms)
        price_risk = abs(entry_price - signal_stop_loss)
        if price_risk == 0:
            # Can't calculate position size with zero risk
            return PositionSize(
                size=0.0,
                method=method,
                risk_amount=0.0,
                risk_percentage=0.0,
                confidence=0.0,
                metadata={"error": "Zero price risk"},
            )

        # Calculate position size based on specified method
        if method == PositionSizingMethod.FIXED_RISK:
            return self._fixed_risk_position_size(
                entry_price,
                signal_stop_loss,
                signal_take_profit,
                account_size,
                entry_signal,
            )

        elif method == PositionSizingMethod.KELLY:
            return self._kelly_position_size(
                entry_price,
                signal_stop_loss,
                signal_take_profit,
                account_size,
                entry_signal,
                custom_data,
            )

        elif method == PositionSizingMethod.VOLATILITY_ADJUSTED:
            return self._volatility_adjusted_position_size(
                entry_price,
                signal_stop_loss,
                signal_take_profit,
                account_size,
                entry_signal,
                custom_data,
            )

        elif method == PositionSizingMethod.SCALING:
            return self._scaling_position_size(
                entry_price,
                signal_stop_loss,
                signal_take_profit,
                account_size,
                entry_signal,
                custom_data,
            )

        elif method == PositionSizingMethod.FIXED_SIZE:
            # Use a fixed position size (from custom_data)
            fixed_size = 1.0  # Default to 1 unit
            if custom_data and "fixed_size" in custom_data:
                fixed_size = custom_data["fixed_size"]

            # Calculate risk amount and percentage
            risk_amount = fixed_size * price_risk
            risk_percentage = risk_amount / account_size

            return PositionSize(
                size=fixed_size,
                method=method,
                risk_amount=risk_amount,
                risk_percentage=risk_percentage,
                confidence=0.8,
                metadata={"calculation": "fixed_size"},
            )

        else:
            # Default to fixed risk method
            return self._fixed_risk_position_size(
                entry_price,
                signal_stop_loss,
                signal_take_profit,
                account_size,
                entry_signal,
            )

    def _fixed_risk_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        account_size: float,
        entry_signal: EntrySignal,
    ) -> PositionSize:
        """
        Calculate position size based on fixed risk percentage.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            account_size: Account size
            entry_signal: Entry signal

        Returns:
            PositionSize object
        """
        # Calculate risk amount based on default risk percentage
        risk_amount = account_size * self.default_risk_percent

        # Calculate position size based on price risk
        price_risk = abs(entry_price - stop_loss)
        position_size = risk_amount / price_risk if price_risk > 0 else 0

        # Adjust position size based on signal strength
        if entry_signal.strength == SignalStrength.STRONG:
            # Increase position size for strong signals
            position_size *= 1.2
        elif entry_signal.strength == SignalStrength.WEAK:
            # Decrease position size for weak signals
            position_size *= 0.8

        # Adjust for signal confidence
        position_size *= entry_signal.confidence

        return PositionSize(
            size=position_size,
            method=PositionSizingMethod.FIXED_RISK,
            risk_amount=risk_amount,
            risk_percentage=self.default_risk_percent,
            confidence=entry_signal.confidence,
            metadata={
                "calculation": "fixed_risk",
                "signal_strength": entry_signal.strength.name,
                "signal_confidence": entry_signal.confidence,
            },
        )

    def _kelly_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        account_size: float,
        entry_signal: EntrySignal,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> PositionSize:
        """
        Calculate position size using Kelly criterion optimization.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            account_size: Account size
            entry_signal: Entry signal
            custom_data: Optional custom data with win rate and profit/loss ratio

        Returns:
            PositionSize object
        """
        # Calculate win rate and profit/loss ratio
        win_rate = 0.5  # Default win rate if no historical data
        avg_win_loss_ratio = 2.0  # Default profit/loss ratio

        # If custom data contains historical win rate and profit/loss ratio, use those
        if custom_data:
            if "win_rate" in custom_data:
                win_rate = custom_data["win_rate"]
            if "avg_win_loss_ratio" in custom_data:
                avg_win_loss_ratio = custom_data["avg_win_loss_ratio"]
        # Otherwise, if we have trade history, calculate from it
        elif self.trade_history:
            win_rate, avg_win_loss_ratio = self._calculate_win_metrics_from_history()
        # Otherwise, estimate from the risk/reward ratio
        else:
            potential_profit = abs(take_profit - entry_price)
            potential_loss = abs(entry_price - stop_loss)

            if potential_loss > 0:
                avg_win_loss_ratio = potential_profit / potential_loss

            # Adjust win rate based on signal confidence
            win_rate = 0.4 + (
                entry_signal.confidence * 0.4
            )  # 0.4 to 0.8 based on confidence

        # Calculate Kelly fraction: f* = (p * b - q) / b
        # where p = win rate, q = loss rate (1-p), b = profit/loss ratio
        q = 1 - win_rate
        kelly_f = (win_rate * avg_win_loss_ratio - q) / avg_win_loss_ratio

        # Apply Kelly fraction to make it more conservative
        kelly_f *= self.kelly_fraction

        # Cap Kelly fraction at max risk percentage
        kelly_f = min(kelly_f, self.max_risk_percent)

        # Ensure Kelly is not negative (defensive position sizing)
        if kelly_f <= 0:
            # If Kelly suggests no position, use a very small fixed risk
            kelly_f = self.default_risk_percent * 0.25  # Quarter of the default risk

        # Calculate risk amount and position size
        risk_amount = account_size * kelly_f
        price_risk = abs(entry_price - stop_loss)
        position_size = risk_amount / price_risk if price_risk > 0 else 0

        return PositionSize(
            size=position_size,
            method=PositionSizingMethod.KELLY,
            risk_amount=risk_amount,
            risk_percentage=kelly_f,
            confidence=entry_signal.confidence,
            metadata={
                "calculation": "kelly",
                "win_rate": win_rate,
                "avg_win_loss_ratio": avg_win_loss_ratio,
                "kelly_fraction": self.kelly_fraction,
                "full_kelly": (
                    kelly_f / self.kelly_fraction if self.kelly_fraction > 0 else 0
                ),
            },
        )

    def _volatility_adjusted_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        account_size: float,
        entry_signal: EntrySignal,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> PositionSize:
        """
        Calculate position size adjusted for market volatility.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            account_size: Account size
            entry_signal: Entry signal
            custom_data: Optional custom data with volatility metrics

        Returns:
            PositionSize object
        """
        # Get ATR or other volatility measure
        atr = 0.001 * entry_price  # Default ATR as 0.1% of price
        historical_atr = atr  # Default historical ATR

        # If custom data contains ATR and historical ATR, use those
        if custom_data:
            if "atr" in custom_data:
                atr = custom_data["atr"]
            if "historical_atr" in custom_data:
                historical_atr = custom_data["historical_atr"]

        # Calculate volatility factor
        volatility_factor = 1.0  # Default (no adjustment)
        if historical_atr > 0:
            volatility_factor = atr / historical_atr

        # Adjust risk percentage based on volatility
        risk_percent = self.default_risk_percent

        # If current volatility is high, reduce risk
        if volatility_factor > 1.5:
            risk_percent *= 0.7  # Reduce by 30%
            volatility_condition = "high"
        # If current volatility is low, can increase risk slightly
        elif volatility_factor < 0.7:
            risk_percent *= 1.3  # Increase by 30%
            volatility_condition = "low"
        else:
            volatility_condition = "normal"

        # Cap at maximum risk percentage
        risk_percent = min(risk_percent, self.max_risk_percent)

        # Calculate risk amount and position size
        risk_amount = account_size * risk_percent
        price_risk = abs(entry_price - stop_loss)
        position_size = risk_amount / price_risk if price_risk > 0 else 0

        return PositionSize(
            size=position_size,
            method=PositionSizingMethod.VOLATILITY_ADJUSTED,
            risk_amount=risk_amount,
            risk_percentage=risk_percent,
            confidence=entry_signal.confidence,
            metadata={
                "calculation": "volatility_adjusted",
                "atr": atr,
                "historical_atr": historical_atr,
                "volatility_factor": volatility_factor,
                "volatility_condition": volatility_condition,
            },
        )

    def _scaling_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        account_size: float,
        entry_signal: EntrySignal,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> PositionSize:
        """
        Calculate position size for scaling in/out methods.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            account_size: Account size
            entry_signal: Entry signal
            custom_data: Optional custom data with scaling levels

        Returns:
            PositionSize object with scaling metadata
        """
        # Get scaling parameters
        scaling_levels = 3  # Default number of entry levels
        initial_percent = 0.4  # Default to 40% on first entry

        if custom_data:
            if "scaling_levels" in custom_data:
                scaling_levels = custom_data["scaling_levels"]
            if "initial_percent" in custom_data:
                initial_percent = custom_data["initial_percent"]

        # Calculate total risk amount (for all entries combined)
        total_risk_percent = self.default_risk_percent
        total_risk_amount = account_size * total_risk_percent

        # Calculate initial entry risk
        initial_risk_amount = total_risk_amount * initial_percent

        # Calculate position size for initial entry
        price_risk = abs(entry_price - stop_loss)
        initial_position_size = (
            initial_risk_amount / price_risk if price_risk > 0 else 0
        )

        # Calculate remaining position sizes for each level
        remaining_percent = 1.0 - initial_percent
        level_percents = []
        remaining_levels = scaling_levels - 1

        if remaining_levels > 0:
            # Calculate scaling percentages
            level_percents = self._calculate_scaling_levels(
                remaining_percent, remaining_levels
            )

        # Add all levels to metadata
        scaling_info = {
            "total_levels": scaling_levels,
            "initial_level": {
                "percent": initial_percent,
                "risk_amount": initial_risk_amount,
                "position_size": initial_position_size,
            },
            "additional_levels": [],
        }

        # Calculate position sizes for additional levels
        for i, level_pct in enumerate(level_percents):
            level_risk = total_risk_amount * level_pct
            # Note: price risk might be different for other levels
            # but we use the same for this example
            level_size = level_risk / price_risk if price_risk > 0 else 0

            scaling_info["additional_levels"].append(
                {
                    "level": i + 2,  # Level 2, 3, etc.
                    "percent": level_pct,
                    "risk_amount": level_risk,
                    "position_size": level_size,
                }
            )

        return PositionSize(
            size=initial_position_size,  # Return initial position size
            method=PositionSizingMethod.SCALING,
            risk_amount=initial_risk_amount,
            risk_percentage=total_risk_percent * initial_percent,
            confidence=entry_signal.confidence,
            metadata={
                "calculation": "scaling",
                "scaling_info": scaling_info,
                "total_risk_percent": total_risk_percent,
            },
        )

    def _calculate_scaling_levels(
        self, remaining_percent: float, num_levels: int
    ) -> List[float]:
        """
        Calculate percentages for scaling levels.

        Args:
            remaining_percent: Remaining percentage to distribute
            num_levels: Number of remaining levels

        Returns:
            List of percentages for each level
        """
        if num_levels <= 0:
            return []

        # Various scaling approaches can be implemented here
        # 1. Equal distribution
        if num_levels == 1:
            return [remaining_percent]

        # 2. Decreasing sizes (larger to smaller)
        # Geometric sequence: a, ar, ar^2, ...
        # where a = first term, r = common ratio
        # Sum = a(1-r^n)/(1-r)
        # We solve for a given sum = remaining_percent and n = num_levels

        # Use common ratio 0.8 (each level is 80% of previous)
        r = 0.8
        # Calculate first term
        a = remaining_percent * (1 - r) / (1 - r**num_levels)

        # Generate the sequence
        levels = [a * (r**i) for i in range(num_levels)]

        return levels

    def _calculate_win_metrics_from_history(self) -> Tuple[float, float]:
        """
        Calculate win rate and profit/loss ratio from trade history.

        Returns:
            Tuple of (win_rate, avg_win_loss_ratio)
        """
        if not self.trade_history:
            return 0.5, 2.0  # Default values

        # Count wins and calculate average profit/loss
        wins = 0
        total_profit = 0.0
        total_loss = 0.0

        for trade in self.trade_history:
            if trade.get("profit", 0) > 0:
                wins += 1
                total_profit += trade.get("profit", 0)
            else:
                total_loss += abs(trade.get("profit", 0))

        # Calculate win rate
        win_rate = wins / len(self.trade_history) if self.trade_history else 0.5

        # Calculate average profit/loss ratio
        avg_win = total_profit / wins if wins > 0 else 1.0
        avg_loss = (
            total_loss / (len(self.trade_history) - wins)
            if (len(self.trade_history) - wins) > 0
            else 1.0
        )
        avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 2.0

        return win_rate, avg_win_loss_ratio

    def add_trade_to_history(self, trade: Dict[str, Any]) -> None:
        """
        Add a completed trade to history for Kelly calculations.

        Args:
            trade: Dictionary with trade details (entry, exit, profit, etc.)
        """
        self.trade_history.append(trade)

        # Trim history if it gets too long
        max_history = 1000
        if len(self.trade_history) > max_history:
            self.trade_history = self.trade_history[-max_history:]

    def clear_trade_history(self) -> None:
        """Clear the trade history."""
        self.trade_history = []
