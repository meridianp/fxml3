"""Dynamic exit strategy that adapts to market conditions."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ExitReason(Enum):
    """Reasons for position exit."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_EXIT = "time_exit"
    SIGNAL_REVERSAL = "signal_reversal"
    VOLATILITY_EXIT = "volatility_exit"
    PARTIAL_PROFIT = "partial_profit"


@dataclass
class ExitConfig:
    """Configuration for exit strategy."""

    # Stop loss
    initial_stop_atr_multiplier: float = 2.0
    trailing_stop_atr_multiplier: float = 1.5
    breakeven_trigger_atr: float = 1.0

    # Take profit
    tp_levels: List[float] = None  # ATR multipliers for TP levels
    tp_portions: List[float] = None  # Portion to exit at each level

    # Time-based
    max_holding_bars: int = 50
    time_decay_bars: int = 20  # Start reducing position after this

    # Volatility
    volatility_exit_threshold: float = 3.0  # Exit if volatility spikes

    # Signal
    exit_on_opposite_signal: bool = True
    exit_on_weak_signal: bool = True
    weak_signal_threshold: float = 0.55

    def __post_init__(self):
        if self.tp_levels is None:
            self.tp_levels = [1.0, 2.0, 3.0, 5.0]
        if self.tp_portions is None:
            self.tp_portions = [0.3, 0.3, 0.2, 0.2]


class DynamicExitStrategy:
    """
    Implements dynamic exit strategy with multiple exit conditions.

    Features:
    - Dynamic stop loss adjustment based on price action
    - Multiple take profit levels with partial exits
    - Trailing stops for winning positions
    - Time-based exits with position decay
    - Volatility-based emergency exits
    - Signal reversal exits
    """

    def __init__(self, config: Optional[ExitConfig] = None):
        self.config = config or ExitConfig()
        self.positions = {}  # Track position states

    def initialize_position(
        self,
        position_id: str,
        entry_price: float,
        position_type: str,  # 'long' or 'short'
        atr: float,
        size: float,
        confidence: float = 0.7,
    ) -> Dict:
        """Initialize exit levels for a new position."""

        # Calculate initial levels
        if position_type == "long":
            initial_stop = entry_price - self.config.initial_stop_atr_multiplier * atr
            take_profit_levels = [
                entry_price + tp_mult * atr for tp_mult in self.config.tp_levels
            ]
        else:  # short
            initial_stop = entry_price + self.config.initial_stop_atr_multiplier * atr
            take_profit_levels = [
                entry_price - tp_mult * atr for tp_mult in self.config.tp_levels
            ]

        # Adjust levels based on confidence
        if confidence < 0.7:
            # Tighter stops for low confidence
            if position_type == "long":
                initial_stop = (
                    entry_price - self.config.initial_stop_atr_multiplier * atr * 0.8
                )
            else:
                initial_stop = (
                    entry_price + self.config.initial_stop_atr_multiplier * atr * 0.8
                )

        position_state = {
            "entry_price": entry_price,
            "position_type": position_type,
            "current_stop": initial_stop,
            "trailing_stop": None,
            "take_profit_levels": take_profit_levels,
            "tp_portions": self.config.tp_portions.copy(),
            "remaining_size": size,
            "original_size": size,
            "bars_held": 0,
            "max_profit": 0,
            "max_price": entry_price if position_type == "long" else entry_price,
            "min_price": entry_price if position_type == "short" else entry_price,
            "entry_atr": atr,
            "breakeven_triggered": False,
            "partial_exits": [],
        }

        self.positions[position_id] = position_state

        return {
            "stop_loss": initial_stop,
            "take_profit_levels": take_profit_levels,
            "tp_portions": self.config.tp_portions,
        }

    def update_position(
        self,
        position_id: str,
        current_price: float,
        current_atr: float,
        current_signal: Optional[int] = None,
        signal_confidence: Optional[float] = None,
        market_volatility: Optional[float] = None,
    ) -> Tuple[bool, Optional[float], Optional[ExitReason], Optional[float]]:
        """
        Update position and check exit conditions.

        Returns:
            Tuple of (should_exit, exit_price, exit_reason, exit_size)
        """
        if position_id not in self.positions:
            return False, None, None, None

        pos = self.positions[position_id]
        pos["bars_held"] += 1

        # Update price extremes
        if pos["position_type"] == "long":
            pos["max_price"] = max(pos["max_price"], current_price)
            profit = current_price - pos["entry_price"]
        else:
            pos["min_price"] = min(pos["min_price"], current_price)
            profit = pos["entry_price"] - current_price

        pos["max_profit"] = max(pos["max_profit"], profit)

        # Check various exit conditions

        # 1. Stop Loss Check
        if self._check_stop_loss(pos, current_price):
            return True, current_price, ExitReason.STOP_LOSS, pos["remaining_size"]

        # 2. Partial Take Profit
        partial_exit = self._check_partial_profits(pos, current_price)
        if partial_exit[0]:
            return partial_exit

        # 3. Update Trailing Stop
        self._update_trailing_stop(pos, current_price, current_atr)

        # 4. Check Trailing Stop
        if self._check_trailing_stop(pos, current_price):
            return True, current_price, ExitReason.TRAILING_STOP, pos["remaining_size"]

        # 5. Time-based Exit
        if self._check_time_exit(pos):
            return True, current_price, ExitReason.TIME_EXIT, pos["remaining_size"]

        # 6. Signal Reversal
        if current_signal is not None and self._check_signal_exit(
            pos, current_signal, signal_confidence
        ):
            return (
                True,
                current_price,
                ExitReason.SIGNAL_REVERSAL,
                pos["remaining_size"],
            )

        # 7. Volatility Exit
        if market_volatility and self._check_volatility_exit(
            pos, market_volatility, current_atr
        ):
            return (
                True,
                current_price,
                ExitReason.VOLATILITY_EXIT,
                pos["remaining_size"],
            )

        return False, None, None, None

    def _check_stop_loss(self, pos: Dict, current_price: float) -> bool:
        """Check if stop loss is hit."""
        if pos["position_type"] == "long":
            return current_price <= pos["current_stop"]
        else:
            return current_price >= pos["current_stop"]

    def _check_partial_profits(
        self, pos: Dict, current_price: float
    ) -> Tuple[bool, Optional[float], Optional[ExitReason], Optional[float]]:
        """Check for partial profit taking."""

        for i, (tp_level, portion) in enumerate(
            zip(pos["take_profit_levels"], pos["tp_portions"])
        ):
            if portion <= 0:  # Already taken
                continue

            # Check if TP level is hit
            if pos["position_type"] == "long" and current_price >= tp_level:
                exit_size = pos["original_size"] * portion
                pos["tp_portions"][i] = 0  # Mark as taken
                pos["remaining_size"] -= exit_size
                pos["partial_exits"].append(
                    {"level": i + 1, "price": current_price, "size": exit_size}
                )

                # Move stop to breakeven after first TP
                if not pos["breakeven_triggered"]:
                    pos["current_stop"] = pos["entry_price"]
                    pos["breakeven_triggered"] = True

                return True, current_price, ExitReason.PARTIAL_PROFIT, exit_size

            elif pos["position_type"] == "short" and current_price <= tp_level:
                exit_size = pos["original_size"] * portion
                pos["tp_portions"][i] = 0
                pos["remaining_size"] -= exit_size
                pos["partial_exits"].append(
                    {"level": i + 1, "price": current_price, "size": exit_size}
                )

                if not pos["breakeven_triggered"]:
                    pos["current_stop"] = pos["entry_price"]
                    pos["breakeven_triggered"] = True

                return True, current_price, ExitReason.PARTIAL_PROFIT, exit_size

        return False, None, None, None

    def _update_trailing_stop(
        self, pos: Dict, current_price: float, current_atr: float
    ):
        """Update trailing stop for winning positions."""

        # Only trail stops for positions in profit
        if pos["position_type"] == "long":
            profit_atr = (current_price - pos["entry_price"]) / current_atr

            if profit_atr > self.config.breakeven_trigger_atr:
                # Calculate trailing stop
                trail_distance = self.config.trailing_stop_atr_multiplier * current_atr
                new_stop = current_price - trail_distance

                # Only move stop up, never down
                if new_stop > pos["current_stop"]:
                    pos["current_stop"] = new_stop
                    pos["trailing_stop"] = new_stop

        else:  # short
            profit_atr = (pos["entry_price"] - current_price) / current_atr

            if profit_atr > self.config.breakeven_trigger_atr:
                trail_distance = self.config.trailing_stop_atr_multiplier * current_atr
                new_stop = current_price + trail_distance

                # Only move stop down, never up
                if new_stop < pos["current_stop"]:
                    pos["current_stop"] = new_stop
                    pos["trailing_stop"] = new_stop

    def _check_trailing_stop(self, pos: Dict, current_price: float) -> bool:
        """Check if trailing stop is hit."""
        if pos["trailing_stop"] is None:
            return False

        if pos["position_type"] == "long":
            return current_price <= pos["trailing_stop"]
        else:
            return current_price >= pos["trailing_stop"]

    def _check_time_exit(self, pos: Dict) -> bool:
        """Check for time-based exit."""

        # Hard exit after max holding period
        if pos["bars_held"] >= self.config.max_holding_bars:
            return True

        # Gradual exit for positions held too long without profit
        if pos["bars_held"] >= self.config.time_decay_bars:
            # Exit if position hasn't reached first TP
            if pos["partial_exits"] == []:
                return True

        return False

    def _check_signal_exit(
        self, pos: Dict, current_signal: int, signal_confidence: Optional[float]
    ) -> bool:
        """Check for signal-based exit."""

        # Exit on opposite signal
        if self.config.exit_on_opposite_signal:
            if pos["position_type"] == "long" and current_signal == -1:
                return True
            elif pos["position_type"] == "short" and current_signal == 1:
                return True

        # Exit on weak signal
        if self.config.exit_on_weak_signal and signal_confidence:
            if signal_confidence < self.config.weak_signal_threshold:
                # Exit if current signal doesn't strongly support position
                if pos["position_type"] == "long" and current_signal != 1:
                    return True
                elif pos["position_type"] == "short" and current_signal != -1:
                    return True

        return False

    def _check_volatility_exit(
        self, pos: Dict, market_volatility: float, current_atr: float
    ) -> bool:
        """Check for volatility-based emergency exit."""

        # Compare current volatility to entry volatility
        volatility_ratio = current_atr / pos["entry_atr"]

        # Exit if volatility has spiked significantly
        if volatility_ratio > self.config.volatility_exit_threshold:
            # Only exit losing positions during volatility spikes
            if pos["position_type"] == "long":
                if pos["max_price"] < pos["entry_price"] * 1.005:  # Not in profit
                    return True
            else:
                if pos["min_price"] > pos["entry_price"] * 0.995:  # Not in profit
                    return True

        return False

    def get_position_info(self, position_id: str) -> Optional[Dict]:
        """Get current position information."""
        return self.positions.get(position_id)

    def remove_position(self, position_id: str):
        """Remove position from tracking."""
        if position_id in self.positions:
            del self.positions[position_id]

    def get_exit_analysis(self, position_id: str) -> Dict:
        """Get detailed exit analysis for a position."""
        if position_id not in self.positions:
            return {}

        pos = self.positions[position_id]

        return {
            "bars_held": pos["bars_held"],
            "max_profit_atr": pos["max_profit"] / pos["entry_atr"],
            "current_stop": pos["current_stop"],
            "trailing_active": pos["trailing_stop"] is not None,
            "partial_exits_taken": len(pos["partial_exits"]),
            "remaining_size_pct": pos["remaining_size"] / pos["original_size"],
            "breakeven_triggered": pos["breakeven_triggered"],
        }
