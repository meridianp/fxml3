"""
Stop Loss Calculator - TDD Implementation (GREEN Phase)
Minimal implementation to make tests pass
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


class StopLossCalculator:
    """
    Calculate and manage stop loss orders for risk management.
    GREEN phase: Minimal implementation to pass tests.
    """

    def __init__(
        self,
        default_stop_pips: float = 50,
        method: str = "fixed_pips",
        atr_multiplier: float = 2.0,
        stop_percentage: float = 2.5,
        trailing_distance_pips: float = 25,
        enable_breakeven: bool = False,
        breakeven_trigger_pips: float = 30,
        min_risk_reward: float = 2.0,
        base_stop_pips: float = 50,
        enable_guaranteed_stops: bool = False,
        gsl_premium_pips: float = 2,
        avoid_round_numbers: bool = False,
        round_number_buffer_pips: float = 3,
        min_stop_distance_pips: float = 10,
        max_hold_hours: float = 4,
    ):
        """Initialize stop loss calculator."""
        self.default_stop_pips = default_stop_pips
        self.method = method
        self.atr_multiplier = atr_multiplier
        self.stop_percentage = stop_percentage
        self.trailing_distance_pips = trailing_distance_pips
        self.enable_breakeven = enable_breakeven
        self.breakeven_trigger_pips = breakeven_trigger_pips
        self.min_risk_reward = min_risk_reward
        self.base_stop_pips = base_stop_pips
        self.enable_guaranteed_stops = enable_guaranteed_stops
        self.gsl_premium_pips = gsl_premium_pips
        self.avoid_round_numbers = avoid_round_numbers
        self.round_number_buffer_pips = round_number_buffer_pips
        self.min_stop_distance_pips = min_stop_distance_pips
        self.max_hold_hours = max_hold_hours

    def calculate_stop_loss(
        self, entry_price: float, side: str, symbol: str
    ) -> Dict[str, Any]:
        """Calculate stop loss based on fixed pip distance."""
        if side not in ["buy", "sell"]:
            raise ValueError(f"Invalid side: {side}")

        # Calculate stop based on side
        if side == "buy":
            stop_loss = entry_price - (self.default_stop_pips / 10000)
        else:  # sell
            stop_loss = entry_price + (self.default_stop_pips / 10000)

        return {
            "stop_loss": round(stop_loss, 4),
            "distance_pips": self.default_stop_pips,
            "risk_reward_ratio": None,
        }

    def calculate_atr_stop(
        self, entry_price: float, side: str, current_atr: float, symbol: str
    ) -> Dict[str, Any]:
        """Calculate stop loss based on ATR."""
        # Handle zero ATR
        if current_atr == 0:
            # Fallback to minimum stop
            stop_distance = self.min_stop_distance_pips / 10000
            fallback_used = True
        else:
            # Calculate stop distance based on ATR
            stop_distance = current_atr * self.atr_multiplier
            fallback_used = False

        # Calculate stop price
        if side == "buy":
            stop_loss = entry_price - stop_distance
        else:
            stop_loss = entry_price + stop_distance

        result = {
            "stop_loss": round(stop_loss, 4),
            "distance_pips": round(stop_distance * 10000, 0),
            "atr_value": current_atr,
            "multiplier": self.atr_multiplier,
        }

        if fallback_used:
            result["fallback_used"] = True

        return result

    def calculate_percentage_stop(
        self, entry_price: float, side: str, symbol: str
    ) -> Dict[str, Any]:
        """Calculate stop loss at percentage distance."""
        # Calculate percentage distance
        dollar_risk = entry_price * (self.stop_percentage / 100)

        # Calculate stop price
        if side == "buy":
            stop_loss = entry_price - dollar_risk
        else:
            stop_loss = entry_price + dollar_risk

        return {
            "stop_loss": round(stop_loss, 2),
            "percentage": self.stop_percentage,
            "dollar_risk": round(dollar_risk, 2),
        }

    def calculate_technical_stop(
        self,
        entry_price: float,
        side: str,
        price_data: Dict[str, Any],
        buffer_pips: float,
    ) -> Dict[str, Any]:
        """Calculate stop based on support/resistance levels."""
        buffer = buffer_pips / 10000

        if side == "buy":
            # Use nearest support level below entry
            support_levels = price_data.get("support_levels", [])
            # Find closest support below entry
            valid_supports = [s for s in support_levels if s < entry_price]
            if valid_supports:
                level_used = max(valid_supports)  # Nearest support
                stop_loss = level_used - buffer
                based_on = "support"
            else:
                # Fallback
                level_used = entry_price - (self.default_stop_pips / 10000)
                stop_loss = level_used - buffer
                based_on = "support"
        else:
            # Use nearest resistance level above entry
            resistance_levels = price_data.get("resistance_levels", [])
            # Find closest resistance above entry
            valid_resistances = [r for r in resistance_levels if r > entry_price]
            if valid_resistances:
                level_used = min(valid_resistances)  # Nearest resistance
                stop_loss = level_used + buffer
                based_on = "resistance"
            else:
                # Fallback
                level_used = entry_price + (self.default_stop_pips / 10000)
                stop_loss = level_used + buffer
                based_on = "resistance"

        return {
            "stop_loss": round(stop_loss, 4),
            "based_on": based_on,
            "level_used": level_used,
        }

    def check_time_stop(
        self,
        entry_time: datetime,
        current_time: datetime,
        entry_price: float,
        current_price: float,
    ) -> Dict[str, Any]:
        """Check if time-based stop is triggered."""
        # Calculate hours held
        time_diff = current_time - entry_time
        hours_held = time_diff.total_seconds() / 3600

        # Check if max hold time exceeded
        stop_triggered = hours_held > self.max_hold_hours

        return {
            "stop_triggered": stop_triggered,
            "hours_held": hours_held,
            "reason": "max_hold_time_exceeded" if stop_triggered else None,
        }

    def adjust_to_breakeven(
        self,
        entry_price: float,
        current_price: float,
        side: str,
        current_stop: float,
        buffer_pips: float,
    ) -> Dict[str, Any]:
        """Adjust stop to breakeven when in profit."""
        buffer = buffer_pips / 10000

        # Calculate profit in pips
        if side == "buy":
            profit_pips = (current_price - entry_price) * 10000
            new_stop = entry_price + buffer
        else:
            profit_pips = (entry_price - current_price) * 10000
            new_stop = entry_price - buffer

        # Check if breakeven trigger met
        moved_to_breakeven = profit_pips >= self.breakeven_trigger_pips

        return {
            "new_stop": round(new_stop, 4) if moved_to_breakeven else current_stop,
            "moved_to_breakeven": moved_to_breakeven,
            "profit_pips": round(profit_pips, 0),
        }

    def update_trailing_stop(
        self,
        entry_price: float,
        highest_price: float,
        current_price: float,
        side: str,
        current_stop: float,
    ) -> Dict[str, Any]:
        """Update trailing stop based on price movement."""
        trailing_distance = self.trailing_distance_pips / 10000

        if side == "buy":
            # Trail from highest high
            new_stop = highest_price - trailing_distance
            stop_moved = new_stop > current_stop
        else:
            # Trail from lowest low
            new_stop = (
                highest_price + trailing_distance
            )  # highest is actually lowest for shorts
            stop_moved = new_stop < current_stop

        return {
            "new_stop": round(new_stop, 4),
            "stop_moved": stop_moved,
            "distance_from_high": self.trailing_distance_pips,
        }

    def calculate_chandelier_exit(
        self, highest_high: float, current_atr: float, side: str
    ) -> Dict[str, Any]:
        """Calculate Chandelier Exit stop."""
        # Calculate stop distance
        stop_distance = current_atr * self.atr_multiplier

        # Calculate stop price
        if side == "buy":
            stop_loss = highest_high - stop_distance
        else:
            stop_loss = highest_high + stop_distance

        return {
            "stop_loss": round(stop_loss, 4),
            "distance_from_high": round(stop_distance * 10000, 0),
        }

    def calculate_parabolic_sar(
        self,
        prices: List[float],
        highs: List[float],
        lows: List[float],
        acceleration_factor: float,
        max_acceleration: float,
    ) -> Dict[str, Any]:
        """Calculate Parabolic SAR."""
        # Simplified PSAR calculation
        if len(prices) < 2:
            return {"sar_value": 0, "position_side": "long", "acceleration_factor": 0}

        # Determine trend direction
        if prices[-1] > prices[0]:
            position_side = "long"
            sar_value = min(lows)  # SAR below in uptrend
        else:
            position_side = "short"
            sar_value = max(highs)  # SAR above in downtrend

        return {
            "sar_value": round(sar_value, 4),
            "position_side": position_side,
            "acceleration_factor": acceleration_factor,
        }

    def calculate_rr_adjusted_stop(
        self,
        entry_price: float,
        target_price: float,
        side: str,
        max_stop_distance: float,
    ) -> Dict[str, Any]:
        """Calculate stop based on risk/reward ratio."""
        # Calculate reward distance
        if side == "buy":
            reward_pips = (target_price - entry_price) * 10000
        else:
            reward_pips = (entry_price - target_price) * 10000

        # Calculate required risk for minimum R:R
        risk_pips = reward_pips / self.min_risk_reward

        # Cap at max stop distance
        risk_pips = min(risk_pips, max_stop_distance)

        # Calculate stop price
        if side == "buy":
            stop_loss = entry_price - (risk_pips / 10000)
        else:
            stop_loss = entry_price + (risk_pips / 10000)

        return {
            "stop_loss": round(stop_loss, 4),
            "risk_pips": round(risk_pips, 0),
            "reward_pips": round(reward_pips, 0),
            "risk_reward_ratio": round(reward_pips / risk_pips, 1),
        }

    def calculate_volatility_adjusted(
        self,
        entry_price: float,
        side: str,
        current_volatility: float,
        average_volatility: float,
        symbol: str,
    ) -> Dict[str, Any]:
        """Adjust stop based on volatility."""
        # Calculate volatility ratio
        volatility_ratio = current_volatility / average_volatility

        # Adjust stop distance
        adjusted_stop_pips = self.base_stop_pips * volatility_ratio

        # Calculate stop price
        if side == "buy":
            stop_loss = entry_price - (adjusted_stop_pips / 10000)
        else:
            stop_loss = entry_price + (adjusted_stop_pips / 10000)

        return {
            "stop_loss": round(stop_loss, 4),
            "stop_pips": round(adjusted_stop_pips, 0),
            "volatility_multiplier": round(volatility_ratio, 3),
        }

    def calculate_guaranteed_stop(
        self, entry_price: float, requested_stop: float, side: str, symbol: str
    ) -> Dict[str, Any]:
        """Calculate guaranteed stop loss with premium."""
        return {
            "guaranteed_stop": requested_stop,
            "premium_pips": self.gsl_premium_pips,
            "additional_cost": True,
            "gap_protection": True,
        }

    def calculate_multi_tf_stop(
        self,
        entry_price: float,
        side: str,
        timeframe_data: Dict[str, Dict],
        weight_by_strength: bool,
    ) -> Dict[str, Any]:
        """Calculate stop from multiple timeframes."""
        if not timeframe_data:
            return {
                "combined_stop": 0,
                "primary_timeframe": None,
                "timeframes_used": [],
            }

        # Find primary timeframe (highest strength)
        primary_tf = max(timeframe_data.items(), key=lambda x: x[1]["strength"])
        primary_timeframe = primary_tf[0]

        if weight_by_strength:
            # Calculate weighted average
            total_weight = sum(tf["strength"] for tf in timeframe_data.values())
            weighted_stop = sum(
                tf["stop"] * tf["strength"] for tf in timeframe_data.values()
            )
            combined_stop = weighted_stop / total_weight if total_weight > 0 else 0
        else:
            # Simple average
            stops = [tf["stop"] for tf in timeframe_data.values()]
            combined_stop = sum(stops) / len(stops) if stops else 0

        return {
            "combined_stop": round(combined_stop, 4),
            "primary_timeframe": primary_timeframe,
            "timeframes_used": list(timeframe_data.keys()),
        }

    def calculate_anti_hunt_stop(
        self, entry_price: float, initial_stop: float, side: str, symbol: str
    ) -> Dict[str, Any]:
        """Adjust stop to avoid round numbers."""
        buffer = self.round_number_buffer_pips / 10000

        # Check if stop is at round number
        if abs(initial_stop * 10000 % 50) < 1:  # Near 50 or 00 level
            # Adjust away from round number
            if side == "buy":
                adjusted_stop = initial_stop - buffer
            else:
                adjusted_stop = initial_stop + buffer
        else:
            adjusted_stop = initial_stop

        return {
            "adjusted_stop": round(adjusted_stop, 4),
            "reason": (
                "round_number_avoidance" if adjusted_stop != initial_stop else None
            ),
        }

    def validate_stop_distance(
        self, entry_price: float, stop_loss: float, side: str, symbol: str
    ) -> None:
        """Validate minimum stop distance."""
        # Calculate distance in pips
        distance_pips = abs(entry_price - stop_loss) * 10000

        if distance_pips < self.min_stop_distance_pips:
            raise ValueError(
                f"Stop too close: {distance_pips:.1f} pips < minimum {self.min_stop_distance_pips} pips"
            )

    def assess_gap_risk(
        self, entry_time: datetime, symbol: str, current_stop: float
    ) -> Dict[str, Any]:
        """Assess weekend gap risk."""
        # Check if it's Friday evening
        weekday = entry_time.weekday()
        hour = entry_time.hour

        if weekday == 4 and hour >= 17:  # Friday after 5 PM
            gap_risk = "high"
            recommendation = "consider_guaranteed_stop"
        else:
            gap_risk = "low"
            recommendation = None

        return {"gap_risk": gap_risk, "recommendation": recommendation}
