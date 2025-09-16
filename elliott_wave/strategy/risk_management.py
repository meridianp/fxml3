"""
Risk management module for Elliott Wave trading strategies.

This module implements dynamic risk management based on wave structure,
pattern invalidation detection, and adaptive position sizing.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from fxml3.strategy.entry_signals import EntrySignal, SignalType
from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer


class InvalidationLevel(Enum):
    """Wave pattern invalidation levels."""

    NONE = 0  # No invalidation
    MINOR = 1  # Minor invalidation (pattern may still be valid)
    MODERATE = 2  # Moderate invalidation (pattern is questionable)
    SEVERE = 3  # Severe invalidation (pattern is likely invalid)
    CRITICAL = 4  # Critical invalidation (pattern is definitely invalid)


class RiskManager:
    """
    Implements dynamic risk management based on Elliott Wave patterns.

    This class analyzes wave structures to determine optimal stop loss levels,
    calculates volatility-adjusted position sizes, and detects pattern invalidation.
    """

    def __init__(
        self,
        wave_analyzer: Optional[ElliottWaveAnalyzer] = None,
        max_risk_per_trade: float = 0.02,  # 2% of account per trade
        volatility_lookback: int = 20,
        fibonacci_levels: List[float] = None,
        use_atr_for_stops: bool = True,
        atr_multiple: float = 2.0,
        multi_timeframe_mapping: Dict[str, str] = None,
    ):
        """
        Initialize the risk manager.

        Args:
            wave_analyzer: Elliott Wave analyzer for pattern validation
            max_risk_per_trade: Maximum risk percentage per trade
            volatility_lookback: Lookback period for volatility calculation
            fibonacci_levels: Custom Fibonacci levels for risk calculation
            use_atr_for_stops: Whether to use ATR for stop loss calculation
            atr_multiple: Multiple of ATR to use for stop loss calculation
            multi_timeframe_mapping: Mapping between timeframes and their parent timeframes
        """
        self.wave_analyzer = wave_analyzer or ElliottWaveAnalyzer()
        self.max_risk_per_trade = max_risk_per_trade
        self.volatility_lookback = volatility_lookback
        self.fibonacci_levels = fibonacci_levels or [
            0.382,
            0.5,
            0.618,
            0.786,
            1.0,
            1.272,
            1.618,
        ]
        self.use_atr_for_stops = use_atr_for_stops
        self.atr_multiple = atr_multiple

        # Default mapping between timeframes
        self.multi_timeframe_mapping = multi_timeframe_mapping or {
            "1m": "5m",
            "5m": "15m",
            "15m": "1H",
            "30m": "4H",
            "1H": "4H",
            "4H": "1D",
            "1D": "1W",
        }

    def calculate_dynamic_stop_loss(
        self,
        data: pd.DataFrame,
        entry_signal: EntrySignal,
        account_size: float = 10000.0,
        lookback_periods: int = None,
        timeframes: List[str] = None,
        multi_tf_data: Dict[str, pd.DataFrame] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate a dynamic stop loss based on wave structure.

        Args:
            data: DataFrame with OHLCV data and wave annotations
            entry_signal: The entry signal to calculate stop loss for
            account_size: Account size for risk calculation
            lookback_periods: Number of periods to look back for analysis
            timeframes: List of timeframes to consider for multi-timeframe analysis
            multi_tf_data: Optional dictionary with data for different timeframes

        Returns:
            Tuple of (stop_loss_price, metadata_dict)
        """
        if lookback_periods is None:
            lookback_periods = self.volatility_lookback

        # Get a copy of the data slice needed for calculation
        # Find the index position that corresponds to the signal timestamp
        signal_idx = None
        for i, idx in enumerate(data.index):
            if pd.Timestamp(idx) == entry_signal.timestamp:
                signal_idx = i
                break

        if signal_idx is None:
            # If exact timestamp not found, use the last available row
            signal_idx = len(data) - 1

        # Get relevant data slice
        start_idx = max(0, signal_idx - lookback_periods)
        data_slice = data.iloc[start_idx : signal_idx + 1].copy()

        # Extract signal properties
        signal_type = entry_signal.signal_type
        pattern = entry_signal.pattern
        entry_price = entry_signal.entry_price

        # Calculate stop loss based on wave pattern and position type
        if self._is_impulse_pattern(pattern):
            stop_loss, meta = self._calculate_impulse_wave_stop(
                data_slice, signal_idx - start_idx, signal_type, pattern
            )
        elif self._is_corrective_pattern(pattern):
            stop_loss, meta = self._calculate_corrective_wave_stop(
                data_slice, signal_idx - start_idx, signal_type, pattern
            )
        else:
            # Default to volatility-based stop loss
            stop_loss, meta = self._calculate_volatility_stop(
                data_slice, signal_idx - start_idx, signal_type
            )

        # Ensure we have a valid stop loss
        if stop_loss is None or not np.isfinite(stop_loss):
            # Fallback to simple percentage-based stop loss
            risk_percent = 0.02  # 2% default risk
            if signal_type == SignalType.LONG:
                stop_loss = entry_price * (1 - risk_percent)
            else:
                stop_loss = entry_price * (1 + risk_percent)
            meta["calculation_method"] = "percentage_fallback"
            meta["risk_percentage"] = risk_percent

        # Apply volatility adjustment to the stop loss
        adjusted_stop_loss, volatility_meta = self._apply_volatility_adjustment(
            data_slice, stop_loss, signal_idx - start_idx, signal_type, entry_price
        )

        # Add volatility metadata
        meta.update(volatility_meta)

        # If multiple timeframes provided, perform multi-timeframe validation
        if timeframes and len(timeframes) > 1 and entry_signal.timeframe in timeframes:
            multi_tf_meta = self._validate_stop_with_multiple_timeframes(
                adjusted_stop_loss, entry_signal, timeframes, multi_tf_data
            )
            meta.update(multi_tf_meta)

            # If multi-timeframe validation resulted in an adjusted stop loss, use it
            if "multi_tf_adjusted_stop" in multi_tf_meta:
                adjusted_stop_loss = multi_tf_meta["multi_tf_adjusted_stop"]

        # Calculate position size based on risk, adjusted for volatility
        volatility_factor = meta.get("volatility_factor", 1.0)
        adjusted_risk = (
            self.max_risk_per_trade * volatility_factor
        )  # Adjust risk based on volatility
        adjusted_risk = min(
            adjusted_risk, self.max_risk_per_trade * 1.5
        )  # Cap at 150% of max risk
        adjusted_risk = max(
            adjusted_risk, self.max_risk_per_trade * 0.5
        )  # Floor at 50% of max risk

        risk_amount = account_size * adjusted_risk
        price_risk = abs(entry_price - adjusted_stop_loss)
        position_size = risk_amount / price_risk if price_risk > 0 else 0

        # Add position sizing to metadata
        meta["risk_amount"] = risk_amount
        meta["price_risk"] = price_risk
        meta["position_size"] = position_size
        meta["account_size"] = account_size
        meta["max_risk_percent"] = self.max_risk_per_trade
        meta["adjusted_risk_percent"] = adjusted_risk
        meta["final_stop_loss"] = adjusted_stop_loss

        return adjusted_stop_loss, meta

    def _apply_volatility_adjustment(
        self,
        data: pd.DataFrame,
        stop_loss: float,
        current_idx: int,
        signal_type: SignalType,
        entry_price: float,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Apply a volatility adjustment to the stop loss.

        Args:
            data: DataFrame with OHLCV data
            stop_loss: Initial stop loss price
            current_idx: Index of current row in the data
            signal_type: Type of trade signal (LONG/SHORT)
            entry_price: Entry price for the trade

        Returns:
            Tuple of (adjusted_stop_loss, metadata_dict)
        """
        meta = {"volatility_adjustment_applied": True}

        # Calculate Average True Range (ATR)
        atr = self._calculate_atr(data, current_idx)
        if atr is None:
            # Not enough data for ATR calculation
            return stop_loss, {
                "volatility_adjustment_applied": False,
                "reason": "insufficient_data",
            }

        # Calculate the initial risk in price terms
        initial_risk = abs(entry_price - stop_loss)

        # Calculate volatility factor based on current ATR vs historical
        if len(data) >= 50:  # Make sure we have enough data for historical comparison
            recent_atr = atr
            historical_atr = self._calculate_historical_atr(
                data, current_idx, window=50
            )

            if historical_atr > 0:  # Prevent division by zero
                volatility_factor = recent_atr / historical_atr
                meta["volatility_factor"] = volatility_factor
                meta["recent_atr"] = recent_atr
                meta["historical_atr"] = historical_atr

                # If current volatility is high, tighten stop loss
                if volatility_factor > 1.5:
                    # High volatility - reduce risk by tightening stop
                    adjustment_factor = 0.7  # Reduce risk by 30%
                    meta["volatility_condition"] = "high"
                    meta["adjustment_factor"] = adjustment_factor

                # If current volatility is low, allow wider stop
                elif volatility_factor < 0.7:
                    # Low volatility - allow wider stop
                    adjustment_factor = 1.3  # Increase risk by 30%
                    meta["volatility_condition"] = "low"
                    meta["adjustment_factor"] = adjustment_factor

                else:
                    # Normal volatility - no adjustment
                    adjustment_factor = 1.0
                    meta["volatility_condition"] = "normal"
                    meta["adjustment_factor"] = adjustment_factor

                # Apply the adjustment factor to the stop loss
                adjusted_risk = initial_risk * adjustment_factor

                # Calculate the new stop loss based on adjusted risk
                if signal_type == SignalType.LONG:
                    adjusted_stop_loss = entry_price - adjusted_risk
                else:
                    adjusted_stop_loss = entry_price + adjusted_risk

                meta["initial_stop"] = stop_loss
                meta["initial_risk"] = initial_risk
                meta["adjusted_risk"] = adjusted_risk

                return adjusted_stop_loss, meta

        # If we couldn't perform volatility adjustment, return original stop loss
        return stop_loss, {
            "volatility_adjustment_applied": False,
            "reason": "no_adjustment_needed",
        }

    def _calculate_atr(
        self, data: pd.DataFrame, current_idx: int, window: int = 14
    ) -> Optional[float]:
        """
        Calculate Average True Range.

        Args:
            data: DataFrame with OHLCV data
            current_idx: Index of current row
            window: ATR calculation window

        Returns:
            ATR value or None if not enough data
        """
        if len(data) < window + 1 or current_idx < window:
            return None

        # Calculate True Range
        high_low = data["high"] - data["low"]
        high_close = abs(data["high"] - data["close"].shift(1))
        low_close = abs(data["low"] - data["close"].shift(1))

        # Combine into True Range
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)

        # Calculate ATR
        atr = true_range.rolling(window).mean().iloc[current_idx]

        return atr

    def _calculate_historical_atr(
        self, data: pd.DataFrame, current_idx: int, window: int = 50
    ) -> float:
        """
        Calculate historical ATR for volatility comparison.

        Args:
            data: DataFrame with OHLCV data
            current_idx: Current index in the data
            window: Window for historical calculation

        Returns:
            Historical ATR value
        """
        if current_idx < window * 2:
            # Not enough historical data, use what we have
            if current_idx < window:
                return (
                    self._calculate_atr(data, current_idx, max(5, current_idx // 2))
                    or 0.0
                )
            else:
                historical_slice = data.iloc[0 : current_idx - window]
        else:
            # Use window data from further back
            historical_slice = data.iloc[
                current_idx - window * 2 : current_idx - window
            ]

        # Calculate ATR on historical slice
        high_low = historical_slice["high"] - historical_slice["low"]
        high_close = abs(historical_slice["high"] - historical_slice["close"].shift(1))
        low_close = abs(historical_slice["low"] - historical_slice["close"].shift(1))

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)

        # Return mean of true range as historical ATR
        return true_range.mean()

    def _validate_stop_with_multiple_timeframes(
        self,
        stop_loss: float,
        entry_signal: EntrySignal,
        timeframes: List[str],
        multi_tf_data: Dict[str, pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Validate stop loss using multiple timeframes.

        Args:
            stop_loss: Calculated stop loss price
            entry_signal: Entry signal generating the trade
            timeframes: List of timeframes to consider
            multi_tf_data: Optional dictionary with data for different timeframes

        Returns:
            Dictionary with validation metadata
        """
        meta = {
            "multi_timeframe_validation": True,
            "primary_timeframe": entry_signal.timeframe,
            "considered_timeframes": timeframes,
        }

        # Order timeframes by size
        tf_ordering = {
            "1m": 1,
            "5m": 2,
            "15m": 3,
            "30m": 4,
            "1H": 5,
            "4H": 6,
            "1D": 7,
            "1W": 8,
        }

        ordered_timeframes = sorted(
            [tf for tf in timeframes if tf in tf_ordering],
            key=lambda x: tf_ordering.get(x, 0),
        )

        meta["ordered_timeframes"] = ordered_timeframes

        # Find the position of our current timeframe
        if entry_signal.timeframe in ordered_timeframes:
            current_tf_idx = ordered_timeframes.index(entry_signal.timeframe)

            # Look for higher timeframes
            higher_timeframes = (
                ordered_timeframes[current_tf_idx + 1 :]
                if current_tf_idx < len(ordered_timeframes) - 1
                else []
            )
            lower_timeframes = (
                ordered_timeframes[:current_tf_idx] if current_tf_idx > 0 else []
            )

            meta["higher_timeframes"] = higher_timeframes
            meta["lower_timeframes"] = lower_timeframes

            # If we have multi-timeframe data, perform actual validation
            if multi_tf_data and higher_timeframes:
                adjusted_stop, validation_meta = (
                    self._adjust_stop_with_higher_timeframes(
                        stop_loss, entry_signal, higher_timeframes, multi_tf_data
                    )
                )

                meta.update(validation_meta)
                meta["original_stop"] = stop_loss
                meta["multi_tf_adjusted_stop"] = adjusted_stop
                return meta

            # Placeholder result based on available timeframes
            if higher_timeframes:
                meta["validation_result"] = "validated_with_higher_timeframes"
            elif lower_timeframes:
                meta["validation_result"] = "validated_with_lower_timeframes"
            else:
                meta["validation_result"] = "single_timeframe_only"
        else:
            meta["validation_result"] = "timeframe_not_in_list"

        return meta

    def _adjust_stop_with_higher_timeframes(
        self,
        stop_loss: float,
        entry_signal: EntrySignal,
        higher_timeframes: List[str],
        multi_tf_data: Dict[str, pd.DataFrame],
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Adjust stop loss based on key levels from higher timeframes.

        Args:
            stop_loss: Initial stop loss price
            entry_signal: Entry signal generating the trade
            higher_timeframes: List of higher timeframes to consider
            multi_tf_data: Dictionary with data for different timeframes

        Returns:
            Tuple of (adjusted_stop_loss, metadata_dict)
        """
        meta = {"higher_tf_analysis": True}
        adjusted_stop = stop_loss
        signal_type = entry_signal.signal_type
        entry_price = entry_signal.entry_price

        # Check each higher timeframe for key levels
        for tf in higher_timeframes:
            if tf not in multi_tf_data:
                continue

            tf_data = multi_tf_data[tf]

            # Find key support/resistance levels
            key_levels = self._find_key_levels(tf_data, signal_type, entry_price)

            if not key_levels:
                continue

            meta[f"{tf}_key_levels"] = key_levels

            # Check if stop loss is too close to a key level
            if signal_type == SignalType.LONG:
                # For long positions, stop loss is below entry
                # Check if stop loss is just above a support level
                for level in key_levels:
                    if (
                        level["type"] == "support"
                        and stop_loss > level["price"] > stop_loss * 0.99
                    ):
                        # Stop is just above support - move it below the support
                        new_stop = level["price"] * 0.995  # 0.5% below support
                        meta[f"{tf}_stop_adjustment"] = {
                            "action": "moved_below_support",
                            "level": level["price"],
                            "original_stop": stop_loss,
                            "new_stop": new_stop,
                        }
                        adjusted_stop = new_stop
                        break
            else:
                # For short positions, stop loss is above entry
                # Check if stop loss is just below a resistance level
                for level in key_levels:
                    if (
                        level["type"] == "resistance"
                        and stop_loss < level["price"] < stop_loss * 1.01
                    ):
                        # Stop is just below resistance - move it above the resistance
                        new_stop = level["price"] * 1.005  # 0.5% above resistance
                        meta[f"{tf}_stop_adjustment"] = {
                            "action": "moved_above_resistance",
                            "level": level["price"],
                            "original_stop": stop_loss,
                            "new_stop": new_stop,
                        }
                        adjusted_stop = new_stop
                        break

        return adjusted_stop, meta

    def _find_key_levels(
        self, data: pd.DataFrame, signal_type: SignalType, entry_price: float
    ) -> List[Dict[str, Any]]:
        """
        Find key support and resistance levels in the data.

        Args:
            data: DataFrame with price data
            signal_type: Type of trade signal (LONG/SHORT)
            entry_price: Entry price for reference

        Returns:
            List of dictionaries with key levels
        """
        key_levels = []

        # Look for swing highs and lows
        if len(data) < 20:
            return key_levels

        # Use peak detection for finding swing points
        # For a full implementation, use a more sophisticated algorithm
        highs = []
        lows = []

        # Simple swing detection (not optimal but works for demonstration)
        window = 5
        for i in range(window, len(data) - window):
            # Check for swing highs
            if all(
                data.iloc[i]["high"] > data.iloc[i - j]["high"]
                for j in range(1, window + 1)
            ) and all(
                data.iloc[i]["high"] > data.iloc[i + j]["high"]
                for j in range(1, window + 1)
            ):
                highs.append(
                    {
                        "price": float(data.iloc[i]["high"]),
                        "index": i,
                        "type": "resistance",
                    }
                )

            # Check for swing lows
            if all(
                data.iloc[i]["low"] < data.iloc[i - j]["low"]
                for j in range(1, window + 1)
            ) and all(
                data.iloc[i]["low"] < data.iloc[i + j]["low"]
                for j in range(1, window + 1)
            ):
                lows.append(
                    {"price": float(data.iloc[i]["low"]), "index": i, "type": "support"}
                )

        # Filter the levels based on relevance to the current trade
        if signal_type == SignalType.LONG:
            # For long trades, we're interested in support levels below entry
            relevant_levels = [level for level in lows if level["price"] < entry_price]
            # Sort from highest to lowest (closest to entry first)
            relevant_levels.sort(key=lambda x: -x["price"])
        else:
            # For short trades, we're interested in resistance levels above entry
            relevant_levels = [level for level in highs if level["price"] > entry_price]
            # Sort from lowest to highest (closest to entry first)
            relevant_levels.sort(key=lambda x: x["price"])

        # Take the most relevant levels (closest to entry)
        key_levels = relevant_levels[:3] if relevant_levels else []

        return key_levels

    def _calculate_impulse_wave_stop(
        self,
        data: pd.DataFrame,
        current_idx: int,
        signal_type: SignalType,
        pattern: str,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate stop loss for an impulse wave pattern.

        Args:
            data: DataFrame with OHLCV data and wave annotations
            current_idx: Index of the current row in the data
            signal_type: Type of trade signal (LONG/SHORT)
            pattern: Pattern name

        Returns:
            Tuple of (stop_loss_price, metadata_dict)
        """
        current_price = data.iloc[current_idx]["close"]
        meta = {"calculation_method": "impulse_wave", "pattern": pattern}

        # Check for specific wave patterns and set stop levels accordingly
        if pattern == "wave_3_start":
            # For wave 3 start, stop should be beyond wave 2 extreme
            if signal_type == SignalType.LONG:
                # Find wave 2 low
                wave2_low = self._find_wave2_low(data, current_idx)
                if wave2_low is not None:
                    # Set stop slightly below wave 2 low
                    stop_loss = wave2_low * 0.997  # 0.3% below wave 2 low
                    meta["wave2_low"] = wave2_low
                    return stop_loss, meta
            else:  # SHORT
                # Find wave 2 high
                wave2_high = self._find_wave2_high(data, current_idx)
                if wave2_high is not None:
                    # Set stop slightly above wave 2 high
                    stop_loss = wave2_high * 1.003  # 0.3% above wave 2 high
                    meta["wave2_high"] = wave2_high
                    return stop_loss, meta

        elif pattern == "wave_5_start":
            # For wave 5 start, stop should be beyond wave 4 extreme
            if signal_type == SignalType.LONG:
                # Find wave 4 low
                wave4_low = self._find_wave4_low(data, current_idx)
                if wave4_low is not None:
                    # Set stop slightly below wave 4 low
                    stop_loss = wave4_low * 0.997  # 0.3% below wave 4 low
                    meta["wave4_low"] = wave4_low
                    return stop_loss, meta
            else:  # SHORT
                # Find wave 4 high
                wave4_high = self._find_wave4_high(data, current_idx)
                if wave4_high is not None:
                    # Set stop slightly above wave 4 high
                    stop_loss = wave4_high * 1.003  # 0.3% above wave 4 high
                    meta["wave4_high"] = wave4_high
                    return stop_loss, meta

        # Fallback to ATR-based stop if wave points not found
        return self._calculate_volatility_stop(data, current_idx, signal_type)

    def _calculate_corrective_wave_stop(
        self,
        data: pd.DataFrame,
        current_idx: int,
        signal_type: SignalType,
        pattern: str,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate stop loss for a corrective wave pattern.

        Args:
            data: DataFrame with OHLCV data and wave annotations
            current_idx: Index of the current row in the data
            signal_type: Type of trade signal (LONG/SHORT)
            pattern: Pattern name

        Returns:
            Tuple of (stop_loss_price, metadata_dict)
        """
        current_price = data.iloc[current_idx]["close"]
        meta = {"calculation_method": "corrective_wave", "pattern": pattern}

        # Check for specific corrective patterns
        if pattern == "abc_completion":
            # For an A-B-C completion, stop should be beyond the C wave extreme
            if signal_type == SignalType.LONG:
                # Find wave C low
                wave_c_low = self._find_wave_c_low(data, current_idx)
                if wave_c_low is not None:
                    # Set stop slightly below wave C low
                    stop_loss = wave_c_low * 0.997  # 0.3% below wave C low
                    meta["wave_c_low"] = wave_c_low
                    return stop_loss, meta
            else:  # SHORT
                # Find wave C high
                wave_c_high = self._find_wave_c_high(data, current_idx)
                if wave_c_high is not None:
                    # Set stop slightly above wave C high
                    stop_loss = wave_c_high * 1.003  # 0.3% above wave C high
                    meta["wave_c_high"] = wave_c_high
                    return stop_loss, meta

        elif pattern == "triangle_breakout":
            # For triangle breakout, use the last swing before breakout
            # This would depend on specific triangle annotation in the data
            # This is a simplified implementation
            if signal_type == SignalType.LONG:
                # Find the lowest point in recent data
                lookback = min(15, current_idx)
                recent_low = data.iloc[current_idx - lookback : current_idx + 1][
                    "low"
                ].min()
                stop_loss = recent_low * 0.997  # 0.3% below recent low
                meta["recent_low"] = recent_low
                return stop_loss, meta
            else:  # SHORT
                # Find the highest point in recent data
                lookback = min(15, current_idx)
                recent_high = data.iloc[current_idx - lookback : current_idx + 1][
                    "high"
                ].max()
                stop_loss = recent_high * 1.003  # 0.3% above recent high
                meta["recent_high"] = recent_high
                return stop_loss, meta

        # Fallback to ATR-based stop if specific pattern handling not available
        return self._calculate_volatility_stop(data, current_idx, signal_type)

    def _calculate_volatility_stop(
        self, data: pd.DataFrame, current_idx: int, signal_type: SignalType
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate stop loss based on market volatility using ATR.

        Args:
            data: DataFrame with OHLCV data
            current_idx: Index of the current row in the data
            signal_type: Type of trade signal (LONG/SHORT)

        Returns:
            Tuple of (stop_loss_price, metadata_dict)
        """
        current_price = data.iloc[current_idx]["close"]
        meta = {"calculation_method": "volatility_based"}

        # Calculate ATR if we have enough data
        if len(data) >= 14 and current_idx >= 14:
            # Simple ATR calculation
            high_low = data["high"] - data["low"]
            high_close = abs(data["high"] - data["close"].shift(1))
            low_close = abs(data["low"] - data["close"].shift(1))

            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(14).mean().iloc[current_idx]

            # Set stop based on ATR multiple
            if signal_type == SignalType.LONG:
                stop_loss = current_price - (atr * self.atr_multiple)
            else:  # SHORT
                stop_loss = current_price + (atr * self.atr_multiple)

            meta["atr"] = atr
            meta["atr_multiple"] = self.atr_multiple
            return stop_loss, meta

        else:
            # Not enough data for ATR, use simple percentage
            risk_percent = 0.02  # 2% default risk
            if signal_type == SignalType.LONG:
                stop_loss = current_price * (1 - risk_percent)
            else:
                stop_loss = current_price * (1 + risk_percent)

            meta["calculation_method"] = "percentage_fallback"
            meta["risk_percentage"] = risk_percent
            return stop_loss, meta

    def detect_pattern_invalidation(
        self,
        data: pd.DataFrame,
        pattern_type: str,
        pattern_start_idx: int,
        current_idx: int,
    ) -> Tuple[InvalidationLevel, Dict[str, Any]]:
        """
        Detect if a wave pattern has been invalidated by price action.

        Args:
            data: DataFrame with OHLCV data and wave annotations
            pattern_type: Type of pattern to validate
            pattern_start_idx: Index where the pattern started
            current_idx: Current index in the data

        Returns:
            Tuple of (invalidation_level, metadata_dict)
        """
        # Implementation will depend on pattern type
        # This is a placeholder with basic logic
        meta = {"pattern_type": pattern_type}

        # Check for specific invalidation conditions
        if self._is_impulse_pattern(pattern_type):
            return self._check_impulse_invalidation(
                data, pattern_start_idx, current_idx
            )
        elif self._is_corrective_pattern(pattern_type):
            return self._check_corrective_invalidation(
                data, pattern_start_idx, current_idx
            )
        else:
            # Unknown pattern type
            return InvalidationLevel.NONE, meta

    def _check_impulse_invalidation(
        self, data: pd.DataFrame, pattern_start_idx: int, current_idx: int
    ) -> Tuple[InvalidationLevel, Dict[str, Any]]:
        """
        Check if an impulse wave pattern has been invalidated.

        Args:
            data: DataFrame with OHLCV data and wave annotations
            pattern_start_idx: Index where the pattern started
            current_idx: Current index in the data

        Returns:
            Tuple of (invalidation_level, metadata_dict)
        """
        meta = {"pattern_type": "impulse"}

        # Check if wave 4 overlaps with wave 1 territory (basic impulse rule)
        # This would require wave labeling in the data
        # For now, we'll implement a simplified check

        # Check for columns indicating wave numbers
        wave_columns = [col for col in data.columns if "wave_" in col]

        if not wave_columns:
            # No wave annotations, can't check impulse rules
            return InvalidationLevel.NONE, meta

        # Look for wave 4 and wave 1 price levels
        wave1_high = None
        wave1_low = None
        wave4_high = None
        wave4_low = None

        # Try to find wave labels in the data
        for i in range(pattern_start_idx, current_idx + 1):
            row = data.iloc[i]

            # Check for wave 1 markers
            if any(
                row.get(f"wave_1_{point}", False)
                for point in ["end", "high", "complete"]
            ):
                wave1_high = row["high"]
                wave1_low = row["low"]

            # Check for wave 4 markers
            if any(
                row.get(f"wave_4_{point}", False)
                for point in ["end", "low", "complete"]
            ):
                wave4_high = row["high"]
                wave4_low = row["low"]

        # If we found both wave points, check for overlap
        if (
            wave1_high is not None
            and wave1_low is not None
            and wave4_high is not None
            and wave4_low is not None
        ):

            # Check if wave 4 low is below wave 1 high (overlap)
            if wave4_low < wave1_high:
                meta["invalidation_reason"] = "wave4_overlap_wave1"
                meta["wave1_high"] = wave1_high
                meta["wave4_low"] = wave4_low
                return InvalidationLevel.SEVERE, meta

        # No invalidation detected
        return InvalidationLevel.NONE, meta

    def _check_corrective_invalidation(
        self, data: pd.DataFrame, pattern_start_idx: int, current_idx: int
    ) -> Tuple[InvalidationLevel, Dict[str, Any]]:
        """
        Check if a corrective wave pattern has been invalidated.

        Args:
            data: DataFrame with OHLCV data and wave annotations
            pattern_start_idx: Index where the pattern started
            current_idx: Current index in the data

        Returns:
            Tuple of (invalidation_level, metadata_dict)
        """
        meta = {"pattern_type": "corrective"}

        # For corrective patterns, typically wave C shouldn't go beyond the start of wave A
        # This would require wave labeling in the data
        # For now, we'll implement a simplified check

        # This is a placeholder implementation
        return InvalidationLevel.NONE, meta

    def _is_impulse_pattern(self, pattern: str) -> bool:
        """Check if a pattern is an impulse wave pattern."""
        impulse_patterns = [
            "wave_3_start",
            "wave_5_start",
            "impulse_complete",
            "wave_1_complete",
            "wave_3_complete",
            "wave_5_complete",
        ]
        return any(p in pattern for p in impulse_patterns)

    def _is_corrective_pattern(self, pattern: str) -> bool:
        """Check if a pattern is a corrective wave pattern."""
        corrective_patterns = [
            "abc_completion",
            "correction_complete",
            "triangle_breakout",
            "flat_pattern",
            "zigzag_complete",
            "double_correction",
        ]
        return any(p in pattern for p in corrective_patterns)

    def _find_wave2_low(self, data: pd.DataFrame, index: int) -> Optional[float]:
        """Find the wave 2 low price for a bullish wave 3 entry."""
        # Look back for wave 2 low
        for i in range(index, max(0, index - 20), -1):
            row = data.iloc[i]

            # Check for wave 2 end indicators
            wave2_indicators = [
                "wave_2_end",
                "impulse_wave_2_end",
                "second_wave_end",
                "wave_2_complete",
            ]

            for indicator in wave2_indicators:
                if indicator in row and row[indicator]:
                    return row["low"]

        return None

    def _find_wave2_high(self, data: pd.DataFrame, index: int) -> Optional[float]:
        """Find the wave 2 high price for a bearish wave 3 entry."""
        # Look back for wave 2 high
        for i in range(index, max(0, index - 20), -1):
            row = data.iloc[i]

            # Check for wave 2 end indicators
            wave2_indicators = [
                "wave_2_end",
                "impulse_wave_2_end",
                "second_wave_end",
                "wave_2_complete",
            ]

            for indicator in wave2_indicators:
                if indicator in row and row[indicator]:
                    return row["high"]

        return None

    def _find_wave4_low(self, data: pd.DataFrame, index: int) -> Optional[float]:
        """Find the wave 4 low price for a bullish wave 5 entry."""
        # Look back for wave 4 low
        for i in range(index, max(0, index - 15), -1):
            row = data.iloc[i]

            # Check for wave 4 end indicators
            wave4_indicators = [
                "wave_4_end",
                "impulse_wave_4_end",
                "fourth_wave_end",
                "wave_4_complete",
            ]

            for indicator in wave4_indicators:
                if indicator in row and row[indicator]:
                    return row["low"]

        return None

    def _find_wave4_high(self, data: pd.DataFrame, index: int) -> Optional[float]:
        """Find the wave 4 high price for a bearish wave 5 entry."""
        # Look back for wave 4 high
        for i in range(index, max(0, index - 15), -1):
            row = data.iloc[i]

            # Check for wave 4 end indicators
            wave4_indicators = [
                "wave_4_end",
                "impulse_wave_4_end",
                "fourth_wave_end",
                "wave_4_complete",
            ]

            for indicator in wave4_indicators:
                if indicator in row and row[indicator]:
                    return row["high"]

        return None

    def _find_wave_c_low(self, data: pd.DataFrame, index: int) -> Optional[float]:
        """Find the wave C low price for a bullish entry after correction."""
        # Look back for wave C low
        for i in range(index, max(0, index - 15), -1):
            row = data.iloc[i]

            # Check for wave C end indicators
            wave_c_indicators = [
                "wave_c_end",
                "corrective_wave_c_end",
                "wave_C_end",
                "wave_c_complete",
            ]

            for indicator in wave_c_indicators:
                if indicator in row and row[indicator]:
                    return row["low"]

        return None

    def _find_wave_c_high(self, data: pd.DataFrame, index: int) -> Optional[float]:
        """Find the wave C high price for a bearish entry after correction."""
        # Look back for wave C high
        for i in range(index, max(0, index - 15), -1):
            row = data.iloc[i]

            # Check for wave C end indicators
            wave_c_indicators = [
                "wave_c_end",
                "corrective_wave_c_end",
                "wave_C_end",
                "wave_c_complete",
            ]

            for indicator in wave_c_indicators:
                if indicator in row and row[indicator]:
                    return row["high"]

        return None
