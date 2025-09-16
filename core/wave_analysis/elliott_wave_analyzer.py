"""Elliott Wave Analyzer for FXML4.

This module provides the main Elliott Wave analysis functionality,
integrating pattern recognition with market analysis.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

logger = logging.getLogger(__name__)


class ElliottWaveAnalyzer:
    """Main analyzer for Elliott Wave patterns in market data."""

    # Elliott Wave rules and guidelines
    WAVE_RULES = {
        "impulse": {
            "wave_2_retrace_max": 1.0,  # Wave 2 cannot retrace 100% of wave 1
            "wave_3_shortest": False,  # Wave 3 cannot be shortest
            "wave_4_overlap": False,  # Wave 4 cannot overlap wave 1
            "alternation": True,  # Waves 2 and 4 should alternate
        },
        "corrective": {
            "zigzag": {"waves": 3, "structure": "5-3-5"},
            "flat": {"waves": 3, "structure": "3-3-5"},
            "triangle": {"waves": 5, "structure": "3-3-3-3-3"},
        },
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Elliott Wave Analyzer.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}

        # Analysis parameters
        self.min_wave_size = self.config.get("min_wave_size", 20)
        self.lookback_periods = self.config.get("lookback_periods", 500)
        self.confidence_threshold = self.config.get("confidence_threshold", 0.6)

        # Fibonacci ratios for wave relationships
        self.fib_ratios = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.618]

        logger.info("Elliott Wave Analyzer initialized")

    def identify_waves(
        self, data: pd.DataFrame, symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Identify Elliott Wave patterns in price data.

        Args:
            data: DataFrame with OHLC data
            symbol: Trading symbol

        Returns:
            List of identified wave patterns
        """
        if len(data) < self.min_wave_size * 5:
            logger.warning("Insufficient data for wave analysis")
            return []

        # Find pivots (highs and lows)
        pivots = self._find_pivots(data)

        if len(pivots) < 5:
            return []

        # Identify potential wave patterns
        patterns = []

        # Look for impulse waves
        impulse_waves = self._identify_impulse_waves(data, pivots)
        patterns.extend(impulse_waves)

        # Look for corrective waves
        corrective_waves = self._identify_corrective_waves(data, pivots)
        patterns.extend(corrective_waves)

        # Add symbol to patterns
        for pattern in patterns:
            pattern["symbol"] = symbol or "UNKNOWN"

        # Sort by confidence
        patterns.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        logger.info("Identified %d wave patterns", len(patterns))

        return patterns

    def analyze_current_position(
        self, data: pd.DataFrame, pattern: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze current position within a wave pattern.

        Args:
            data: Price data
            pattern: Identified wave pattern

        Returns:
            Analysis results including current wave and projections
        """
        current_price = data["close"].iloc[-1]
        current_time = data.index[-1]

        analysis = {
            "current_price": current_price,
            "current_time": current_time,
            "pattern_type": pattern.get("type"),
            "pattern_confidence": pattern.get("confidence", 0),
        }

        # Determine current wave
        if pattern["type"] == "impulse":
            current_wave = self._determine_current_impulse_wave(
                data, pattern, current_price
            )
            analysis["current_wave"] = current_wave

            # Project next targets
            if current_wave in [1, 3, 5]:
                analysis["targets"] = self._project_impulse_targets(
                    pattern, current_wave, current_price
                )
            else:  # Corrective waves 2, 4
                analysis["support_levels"] = self._project_retracement_levels(
                    pattern, current_wave
                )

        elif pattern["type"] == "corrective":
            current_wave = self._determine_current_corrective_wave(
                data, pattern, current_price
            )
            analysis["current_wave"] = current_wave
            analysis["corrective_type"] = pattern.get("corrective_type")

            # Project completion levels
            analysis["completion_targets"] = self._project_corrective_targets(
                pattern, current_wave
            )

        return analysis

    def validate_wave_count(
        self, waves: List[Dict[str, Any]], wave_type: str = "impulse"
    ) -> Tuple[bool, List[str]]:
        """Validate if wave count follows Elliott Wave rules.

        Args:
            waves: List of wave dictionaries
            wave_type: Type of wave pattern

        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []

        if wave_type == "impulse" and len(waves) >= 5:
            # Check wave 2 retracement
            wave_1_size = abs(waves[0]["end_price"] - waves[0]["start_price"])
            wave_2_size = abs(waves[1]["end_price"] - waves[1]["start_price"])

            if wave_2_size >= wave_1_size:
                violations.append("Wave 2 retraced 100% or more of Wave 1")

            # Check wave 3 is not shortest
            wave_3_size = abs(waves[2]["end_price"] - waves[2]["start_price"])
            wave_5_size = (
                abs(waves[4]["end_price"] - waves[4]["start_price"])
                if len(waves) > 4
                else 0
            )

            if wave_3_size < wave_1_size and wave_3_size < wave_5_size:
                violations.append("Wave 3 is the shortest impulse wave")

            # Check wave 4 overlap with wave 1
            if len(waves) > 3:
                wave_1_end = waves[0]["end_price"]
                wave_4_extreme = waves[3]["end_price"]

                if waves[0]["direction"] == "up":
                    if wave_4_extreme < wave_1_end:
                        violations.append("Wave 4 overlaps with Wave 1 territory")
                else:
                    if wave_4_extreme > wave_1_end:
                        violations.append("Wave 4 overlaps with Wave 1 territory")

        is_valid = len(violations) == 0
        return is_valid, violations

    def _find_pivots(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Find pivot points (local highs and lows) in price data.

        Args:
            data: Price data

        Returns:
            List of pivot points
        """
        high_prices = data["high"].values
        low_prices = data["low"].values

        # Find local maxima and minima
        order = max(5, self.min_wave_size // 4)

        high_indices = argrelextrema(high_prices, np.greater, order=order)[0]
        low_indices = argrelextrema(low_prices, np.less, order=order)[0]

        pivots = []

        # Create pivot points
        for idx in high_indices:
            pivots.append(
                {
                    "index": idx,
                    "time": data.index[idx],
                    "price": high_prices[idx],
                    "type": "high",
                }
            )

        for idx in low_indices:
            pivots.append(
                {
                    "index": idx,
                    "time": data.index[idx],
                    "price": low_prices[idx],
                    "type": "low",
                }
            )

        # Sort by time
        pivots.sort(key=lambda x: x["index"])

        return pivots

    def _identify_impulse_waves(
        self, data: pd.DataFrame, pivots: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify impulse wave patterns.

        Args:
            data: Price data
            pivots: List of pivot points

        Returns:
            List of impulse wave patterns
        """
        patterns = []

        # Look for 5-wave structures
        for i in range(len(pivots) - 5):
            # Check if we have alternating highs and lows
            wave_pivots = pivots[i : i + 6]

            if not self._check_alternating_pivots(wave_pivots):
                continue

            # Extract wave information
            waves = []
            for j in range(5):
                wave = {
                    "number": j + 1,
                    "start_price": wave_pivots[j]["price"],
                    "end_price": wave_pivots[j + 1]["price"],
                    "start_time": wave_pivots[j]["time"],
                    "end_time": wave_pivots[j + 1]["time"],
                    "direction": (
                        "up"
                        if wave_pivots[j + 1]["price"] > wave_pivots[j]["price"]
                        else "down"
                    ),
                }
                waves.append(wave)

            # Validate impulse wave rules
            is_valid, violations = self.validate_wave_count(waves, "impulse")

            if is_valid or len(violations) <= 1:  # Allow one minor violation
                confidence = self._calculate_impulse_confidence(waves, violations)

                if confidence >= self.confidence_threshold:
                    pattern = {
                        "type": "impulse",
                        "waves": waves,
                        "start_time": waves[0]["start_time"],
                        "end_time": waves[-1]["end_time"],
                        "direction": self._determine_overall_direction(waves),
                        "confidence": confidence,
                        "violations": violations,
                        "wave_count": 5,
                        "is_complete": True,
                    }
                    patterns.append(pattern)

        return patterns

    def _identify_corrective_waves(
        self, data: pd.DataFrame, pivots: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify corrective wave patterns.

        Args:
            data: Price data
            pivots: List of pivot points

        Returns:
            List of corrective wave patterns
        """
        patterns = []

        # Look for 3-wave structures (zigzag, flat)
        for i in range(len(pivots) - 3):
            wave_pivots = pivots[i : i + 4]

            if not self._check_alternating_pivots(wave_pivots):
                continue

            # Extract wave information
            waves = []
            for j in range(3):
                wave = {
                    "number": j + 1,
                    "label": ["A", "B", "C"][j],
                    "start_price": wave_pivots[j]["price"],
                    "end_price": wave_pivots[j + 1]["price"],
                    "start_time": wave_pivots[j]["time"],
                    "end_time": wave_pivots[j + 1]["time"],
                    "direction": (
                        "up"
                        if wave_pivots[j + 1]["price"] > wave_pivots[j]["price"]
                        else "down"
                    ),
                }
                waves.append(wave)

            # Determine corrective type
            corrective_type = self._classify_corrective_pattern(waves)
            confidence = self._calculate_corrective_confidence(waves, corrective_type)

            if confidence >= self.confidence_threshold:
                pattern = {
                    "type": "corrective",
                    "corrective_type": corrective_type,
                    "waves": waves,
                    "start_time": waves[0]["start_time"],
                    "end_time": waves[-1]["end_time"],
                    "direction": self._determine_overall_direction(waves),
                    "confidence": confidence,
                    "wave_count": 3,
                    "is_complete": True,
                }
                patterns.append(pattern)

        return patterns

    def _check_alternating_pivots(self, pivots: List[Dict[str, Any]]) -> bool:
        """Check if pivots alternate between highs and lows.

        Args:
            pivots: List of pivot points

        Returns:
            True if pivots alternate properly
        """
        for i in range(len(pivots) - 1):
            if pivots[i]["type"] == pivots[i + 1]["type"]:
                return False
        return True

    def _determine_overall_direction(self, waves: List[Dict[str, Any]]) -> str:
        """Determine overall direction of wave pattern.

        Args:
            waves: List of waves

        Returns:
            'up' or 'down'
        """
        start_price = waves[0]["start_price"]
        end_price = waves[-1]["end_price"]

        return "up" if end_price > start_price else "down"

    def _calculate_impulse_confidence(
        self, waves: List[Dict[str, Any]], violations: List[str]
    ) -> float:
        """Calculate confidence score for impulse wave pattern.

        Args:
            waves: List of waves
            violations: List of rule violations

        Returns:
            Confidence score between 0 and 1
        """
        confidence = 1.0

        # Deduct for violations
        confidence -= len(violations) * 0.2

        # Check Fibonacci relationships
        # Wave 2 typically retraces 50-61.8% of wave 1
        wave_1_size = abs(waves[0]["end_price"] - waves[0]["start_price"])
        wave_2_size = abs(waves[1]["end_price"] - waves[1]["start_price"])
        wave_2_ratio = wave_2_size / wave_1_size if wave_1_size > 0 else 0

        if 0.5 <= wave_2_ratio <= 0.618:
            confidence += 0.1

        # Wave 3 is often 1.618 times wave 1
        wave_3_size = abs(waves[2]["end_price"] - waves[2]["start_price"])
        wave_3_ratio = wave_3_size / wave_1_size if wave_1_size > 0 else 0

        if 1.5 <= wave_3_ratio <= 1.8:
            confidence += 0.1

        # Wave 4 typically retraces 38.2-50% of wave 3
        if len(waves) > 3:
            wave_4_size = abs(waves[3]["end_price"] - waves[3]["start_price"])
            wave_4_ratio = wave_4_size / wave_3_size if wave_3_size > 0 else 0

            if 0.382 <= wave_4_ratio <= 0.5:
                confidence += 0.1

        return max(0, min(1, confidence))

    def _calculate_corrective_confidence(
        self, waves: List[Dict[str, Any]], corrective_type: str
    ) -> float:
        """Calculate confidence score for corrective wave pattern.

        Args:
            waves: List of waves
            corrective_type: Type of corrective pattern

        Returns:
            Confidence score between 0 and 1
        """
        confidence = 0.7  # Base confidence for corrective patterns

        # Check relationships based on corrective type
        if corrective_type == "zigzag":
            # Wave B typically retraces 50-61.8% of wave A
            wave_a_size = abs(waves[0]["end_price"] - waves[0]["start_price"])
            wave_b_size = abs(waves[1]["end_price"] - waves[1]["start_price"])
            wave_b_ratio = wave_b_size / wave_a_size if wave_a_size > 0 else 0

            if 0.5 <= wave_b_ratio <= 0.618:
                confidence += 0.2

        elif corrective_type == "flat":
            # Wave B retraces 90-100% of wave A
            wave_a_size = abs(waves[0]["end_price"] - waves[0]["start_price"])
            wave_b_size = abs(waves[1]["end_price"] - waves[1]["start_price"])
            wave_b_ratio = wave_b_size / wave_a_size if wave_a_size > 0 else 0

            if 0.9 <= wave_b_ratio <= 1.1:
                confidence += 0.2

        return min(1, confidence)

    def _classify_corrective_pattern(self, waves: List[Dict[str, Any]]) -> str:
        """Classify type of corrective pattern.

        Args:
            waves: List of waves

        Returns:
            Type of corrective pattern
        """
        # Calculate retracement ratios
        wave_a_size = abs(waves[0]["end_price"] - waves[0]["start_price"])
        wave_b_size = abs(waves[1]["end_price"] - waves[1]["start_price"])
        wave_b_ratio = wave_b_size / wave_a_size if wave_a_size > 0 else 0

        # Classify based on wave B retracement
        if wave_b_ratio < 0.7:
            return "zigzag"
        elif 0.9 <= wave_b_ratio <= 1.1:
            return "flat"
        else:
            return "complex"

    def _determine_current_impulse_wave(
        self, data: pd.DataFrame, pattern: Dict[str, Any], current_price: float
    ) -> int:
        """Determine which impulse wave is currently active.

        Args:
            data: Price data
            pattern: Wave pattern
            current_price: Current price

        Returns:
            Current wave number (1-5)
        """
        waves = pattern.get("waves", [])

        # If pattern is complete, we're beyond wave 5
        if pattern.get("is_complete", False):
            return 5

        # Check current position relative to wave endpoints
        for i, wave in enumerate(waves):
            if current_price <= wave["end_price"]:
                return i + 1

        return len(waves)

    def _determine_current_corrective_wave(
        self, data: pd.DataFrame, pattern: Dict[str, Any], current_price: float
    ) -> str:
        """Determine which corrective wave is currently active.

        Args:
            data: Price data
            pattern: Wave pattern
            current_price: Current price

        Returns:
            Current wave label (A, B, or C)
        """
        waves = pattern.get("waves", [])

        if pattern.get("is_complete", False):
            return "C"

        for wave in waves:
            if current_price <= wave["end_price"]:
                return wave.get("label", "A")

        return waves[-1].get("label", "C") if waves else "A"

    def _project_impulse_targets(
        self, pattern: Dict[str, Any], current_wave: int, current_price: float
    ) -> Dict[str, float]:
        """Project price targets for impulse waves.

        Args:
            pattern: Wave pattern
            current_wave: Current wave number
            current_price: Current price

        Returns:
            Dictionary of price targets
        """
        waves = pattern.get("waves", [])
        targets = {}

        if current_wave == 3 and len(waves) >= 2:
            # Wave 3 targets based on wave 1
            wave_1_size = abs(waves[0]["end_price"] - waves[0]["start_price"])
            wave_2_end = waves[1]["end_price"]

            direction = 1 if pattern["direction"] == "up" else -1

            targets["1.618_extension"] = wave_2_end + (wave_1_size * 1.618 * direction)
            targets["2.618_extension"] = wave_2_end + (wave_1_size * 2.618 * direction)

        elif current_wave == 5 and len(waves) >= 4:
            # Wave 5 targets
            wave_1_size = abs(waves[0]["end_price"] - waves[0]["start_price"])
            wave_3_size = abs(waves[2]["end_price"] - waves[2]["start_price"])
            wave_4_end = waves[3]["end_price"]

            direction = 1 if pattern["direction"] == "up" else -1

            # Wave 5 often equals wave 1
            targets["wave_1_equality"] = wave_4_end + (wave_1_size * direction)

            # Or 0.618 of wave 3
            targets["0.618_of_wave_3"] = wave_4_end + (wave_3_size * 0.618 * direction)

        return targets

    def _project_retracement_levels(
        self, pattern: Dict[str, Any], current_wave: int
    ) -> Dict[str, float]:
        """Project retracement levels for corrective waves.

        Args:
            pattern: Wave pattern
            current_wave: Current wave number

        Returns:
            Dictionary of retracement levels
        """
        waves = pattern.get("waves", [])
        levels = {}

        if current_wave == 2 and len(waves) >= 1:
            # Wave 2 retracement of wave 1
            wave_1_start = waves[0]["start_price"]
            wave_1_end = waves[0]["end_price"]
            wave_1_range = wave_1_end - wave_1_start

            for ratio in [0.382, 0.5, 0.618, 0.786]:
                levels[f"{ratio:.1%}_retracement"] = wave_1_end - (wave_1_range * ratio)

        elif current_wave == 4 and len(waves) >= 3:
            # Wave 4 retracement of wave 3
            wave_3_start = waves[2]["start_price"]
            wave_3_end = waves[2]["end_price"]
            wave_3_range = wave_3_end - wave_3_start

            for ratio in [0.382, 0.5]:
                levels[f"{ratio:.1%}_retracement"] = wave_3_end - (wave_3_range * ratio)

        return levels

    def _project_corrective_targets(
        self, pattern: Dict[str, Any], current_wave: str
    ) -> Dict[str, float]:
        """Project completion targets for corrective waves.

        Args:
            pattern: Wave pattern
            current_wave: Current wave label

        Returns:
            Dictionary of completion targets
        """
        waves = pattern.get("waves", [])
        corrective_type = pattern.get("corrective_type", "zigzag")
        targets = {}

        if current_wave == "C" and len(waves) >= 2:
            wave_a_size = abs(waves[0]["end_price"] - waves[0]["start_price"])
            wave_b_end = waves[1]["end_price"]

            direction = -1 if waves[0]["direction"] == "up" else 1

            if corrective_type == "zigzag":
                # Wave C often equals wave A
                targets["wave_a_equality"] = wave_b_end + (wave_a_size * direction)
                targets["1.618_of_wave_a"] = wave_b_end + (
                    wave_a_size * 1.618 * direction
                )

            elif corrective_type == "flat":
                # Wave C is often 1.0-1.618 of wave A
                targets["wave_a_equality"] = wave_b_end + (wave_a_size * direction)
                targets["1.272_of_wave_a"] = wave_b_end + (
                    wave_a_size * 1.272 * direction
                )

        return targets
