"""
Stop Loss and Take Profit Manager for FXML4

TDD-driven implementation of automated stop loss and take profit management.
Includes trailing stops, break-even stops, and dynamic profit targets.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class StopLossType(str, Enum):
    """Stop loss types."""

    FIXED = "fixed"
    TRAILING = "trailing"
    BREAKEVEN = "breakeven"
    ATR = "atr"  # Based on Average True Range
    PERCENTAGE = "percentage"


class TakeProfitType(str, Enum):
    """Take profit types."""

    FIXED = "fixed"
    RISK_REWARD = "risk_reward"
    FIBONACCI = "fibonacci"
    ATR_MULTIPLE = "atr_multiple"
    PERCENTAGE = "percentage"


@dataclass
class StopLossConfig:
    """Configuration for stop loss."""

    stop_type: StopLossType
    value: Decimal  # Pips, percentage, or ATR multiplier
    trail_start: Optional[Decimal] = None  # When to start trailing
    trail_distance: Optional[Decimal] = None  # Trailing distance
    move_to_breakeven_at: Optional[Decimal] = None  # Profit level to move to BE
    breakeven_plus: Optional[Decimal] = None  # Additional pips above breakeven


@dataclass
class TakeProfitConfig:
    """Configuration for take profit."""

    tp_type: TakeProfitType
    value: Decimal  # Target value based on type
    partial_targets: Optional[List[Dict[str, Decimal]]] = None  # Partial TP levels
    move_stop_at_target: Optional[bool] = False  # Move stop when TP hit


class StopLossManager:
    """Manager for stop loss and take profit automation."""

    def __init__(self):
        """Initialize stop loss manager."""
        self.active_stops: Dict[str, StopLossConfig] = {}
        self.active_profits: Dict[str, TakeProfitConfig] = {}
        self.position_stops: Dict[str, Decimal] = {}
        self.position_profits: Dict[str, Decimal] = {}

    def calculate_initial_stop_loss(
        self,
        entry_price: Decimal,
        side: str,
        stop_config: StopLossConfig,
        atr_value: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate initial stop loss price."""
        if stop_config.stop_type == StopLossType.FIXED:
            # Fixed distance in pips
            pip_distance = stop_config.value / Decimal("10000")
            if side == "long":
                return entry_price - pip_distance
            else:
                return entry_price + pip_distance

        elif stop_config.stop_type == StopLossType.PERCENTAGE:
            # Percentage of entry price
            distance = entry_price * (stop_config.value / Decimal("100"))
            if side == "long":
                return entry_price - distance
            else:
                return entry_price + distance

        elif stop_config.stop_type == StopLossType.ATR:
            # ATR-based stop loss
            if not atr_value:
                raise ValueError("ATR value required for ATR-based stop loss")
            distance = atr_value * stop_config.value
            if side == "long":
                return entry_price - distance
            else:
                return entry_price + distance

        return entry_price

    def calculate_take_profit(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        side: str,
        profit_config: TakeProfitConfig,
        atr_value: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate take profit price."""
        if profit_config.tp_type == TakeProfitType.FIXED:
            # Fixed distance in pips
            pip_distance = profit_config.value / Decimal("10000")
            if side == "long":
                return entry_price + pip_distance
            else:
                return entry_price - pip_distance

        elif profit_config.tp_type == TakeProfitType.RISK_REWARD:
            # Risk:Reward ratio
            risk = abs(entry_price - stop_loss)
            reward = risk * profit_config.value
            if side == "long":
                return entry_price + reward
            else:
                return entry_price - reward

        elif profit_config.tp_type == TakeProfitType.PERCENTAGE:
            # Percentage of entry price
            distance = entry_price * (profit_config.value / Decimal("100"))
            if side == "long":
                return entry_price + distance
            else:
                return entry_price - distance

        elif profit_config.tp_type == TakeProfitType.ATR_MULTIPLE:
            # ATR-based take profit
            if not atr_value:
                raise ValueError("ATR value required for ATR-based take profit")
            distance = atr_value * profit_config.value
            if side == "long":
                return entry_price + distance
            else:
                return entry_price - distance

        return entry_price

    def update_trailing_stop(
        self,
        position_id: str,
        current_price: Decimal,
        highest_price: Decimal,
        lowest_price: Decimal,
        side: str,
        stop_config: StopLossConfig,
    ) -> Optional[Decimal]:
        """Update trailing stop loss based on current price."""
        current_stop = self.position_stops.get(position_id)
        if not current_stop:
            return None

        if stop_config.stop_type != StopLossType.TRAILING:
            return current_stop

        # Check if trailing should start
        if stop_config.trail_start:
            entry_price = self._get_entry_price(position_id)
            if not entry_price:
                return current_stop

            profit_pips = self._calculate_profit_pips(
                entry_price, current_price, side
            )

            if profit_pips < stop_config.trail_start:
                return current_stop

        # Calculate new trailing stop
        trail_distance = stop_config.trail_distance / Decimal("10000")

        if side == "long":
            new_stop = highest_price - trail_distance
            # Only move stop up, never down
            if new_stop > current_stop:
                self.position_stops[position_id] = new_stop
                return new_stop
        else:
            new_stop = lowest_price + trail_distance
            # Only move stop down (more favorable), never up
            if new_stop < current_stop:
                self.position_stops[position_id] = new_stop
                return new_stop

        return current_stop

    def check_breakeven_stop(
        self,
        position_id: str,
        entry_price: Decimal,
        current_price: Decimal,
        side: str,
        stop_config: StopLossConfig,
    ) -> Optional[Decimal]:
        """Check and update breakeven stop."""
        if not stop_config.move_to_breakeven_at:
            return None

        # Calculate profit in pips
        profit_pips = self._calculate_profit_pips(entry_price, current_price, side)

        # Check if profit target reached for breakeven
        if profit_pips >= stop_config.move_to_breakeven_at:
            # Calculate breakeven stop price
            breakeven_plus_distance = (
                stop_config.breakeven_plus / Decimal("10000")
                if stop_config.breakeven_plus
                else Decimal("0")
            )

            if side == "long":
                new_stop = entry_price + breakeven_plus_distance
            else:
                new_stop = entry_price - breakeven_plus_distance

            # Update stop loss
            current_stop = self.position_stops.get(position_id)
            if not current_stop or (
                (side == "long" and new_stop > current_stop)
                or (side == "short" and new_stop < current_stop)
            ):
                self.position_stops[position_id] = new_stop
                return new_stop

        return None

    def calculate_partial_targets(
        self,
        entry_price: Decimal,
        final_target: Decimal,
        num_partials: int = 3,
    ) -> List[Dict[str, Any]]:
        """Calculate partial take profit targets."""
        targets = []
        distance = final_target - entry_price

        for i in range(1, num_partials + 1):
            partial_distance = distance * Decimal(i) / Decimal(num_partials)
            target_price = entry_price + partial_distance

            targets.append({
                "level": i,
                "price": target_price,
                "percentage": Decimal(100) / Decimal(num_partials),
                "cumulative_percentage": Decimal(100) * Decimal(i) / Decimal(num_partials),
            })

        return targets

    def should_close_position(
        self,
        position_id: str,
        current_price: Decimal,
        side: str,
    ) -> Dict[str, Any]:
        """Check if position should be closed based on stop/target."""
        stop_loss = self.position_stops.get(position_id)
        take_profit = self.position_profits.get(position_id)

        result = {
            "should_close": False,
            "reason": None,
            "price": None,
        }

        # Check stop loss
        if stop_loss:
            if (side == "long" and current_price <= stop_loss) or (
                side == "short" and current_price >= stop_loss
            ):
                result["should_close"] = True
                result["reason"] = "stop_loss_hit"
                result["price"] = stop_loss

        # Check take profit
        if take_profit and not result["should_close"]:
            if (side == "long" and current_price >= take_profit) or (
                side == "short" and current_price <= take_profit
            ):
                result["should_close"] = True
                result["reason"] = "take_profit_hit"
                result["price"] = take_profit

        return result

    def register_position(
        self,
        position_id: str,
        entry_price: Decimal,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        stop_config: Optional[StopLossConfig] = None,
        profit_config: Optional[TakeProfitConfig] = None,
    ):
        """Register a new position with stop loss and take profit."""
        if stop_loss:
            self.position_stops[position_id] = stop_loss
        if take_profit:
            self.position_profits[position_id] = take_profit
        if stop_config:
            self.active_stops[position_id] = stop_config
        if profit_config:
            self.active_profits[position_id] = profit_config

        # Store entry price for calculations
        self._entry_prices = getattr(self, "_entry_prices", {})
        self._entry_prices[position_id] = entry_price

    def unregister_position(self, position_id: str):
        """Remove position from monitoring."""
        self.position_stops.pop(position_id, None)
        self.position_profits.pop(position_id, None)
        self.active_stops.pop(position_id, None)
        self.active_profits.pop(position_id, None)

        if hasattr(self, "_entry_prices"):
            self._entry_prices.pop(position_id, None)

    def _calculate_profit_pips(
        self, entry_price: Decimal, current_price: Decimal, side: str
    ) -> Decimal:
        """Calculate profit in pips."""
        if side == "long":
            return (current_price - entry_price) * Decimal("10000")
        else:
            return (entry_price - current_price) * Decimal("10000")

    def _get_entry_price(self, position_id: str) -> Optional[Decimal]:
        """Get stored entry price for position."""
        if hasattr(self, "_entry_prices"):
            return self._entry_prices.get(position_id)
        return None

    def get_risk_reward_ratio(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
    ) -> Decimal:
        """Calculate risk:reward ratio for a trade."""
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)

        if risk == 0:
            return Decimal("0")

        return reward / risk