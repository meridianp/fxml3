"""Fibonacci calculator for wave analysis.

This module provides Fibonacci calculation utilities for Elliott Wave analysis
and general technical analysis.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FibonacciCalculator:
    """Calculator for Fibonacci levels and relationships."""

    # Standard Fibonacci ratios
    FIBONACCI_RATIOS = {
        "retracement": [0.236, 0.382, 0.5, 0.618, 0.786],
        "extension": [0.618, 1.0, 1.272, 1.618, 2.0, 2.618, 3.618, 4.236],
        "projection": [0.618, 1.0, 1.618, 2.618],
    }

    # Golden ratio constants
    PHI = 1.618033988749895  # (1 + sqrt(5)) / 2
    PHI_INVERSE = 0.618033988749895  # 1 / PHI

    def __init__(self):
        """Initialize the Fibonacci calculator."""
        logger.info("Fibonacci calculator initialized")

    def calculate_retracement(
        self, high: float, low: float, custom_levels: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """Calculate Fibonacci retracement levels.

        Args:
            high: High price point
            low: Low price point
            custom_levels: Optional custom Fibonacci levels

        Returns:
            Dictionary mapping level names to prices
        """
        if high <= low:
            raise ValueError("High must be greater than low")

        levels = custom_levels or self.FIBONACCI_RATIOS["retracement"]
        range_size = high - low

        retracements = {
            "0.0": high,  # Top
            "100.0": low,  # Bottom
        }

        # Calculate retracement levels from high
        for level in levels:
            level_name = f"{level * 100:.1f}"
            retracements[level_name] = high - (range_size * level)

        logger.debug(
            "Calculated retracements from %.4f to %.4f: %s", low, high, retracements
        )

        return retracements

    def calculate_extension(
        self,
        point_a: float,
        point_b: float,
        point_c: float,
        custom_levels: Optional[List[float]] = None,
    ) -> Dict[str, float]:
        """Calculate Fibonacci extension levels.

        Used for projecting targets beyond the initial move.

        Args:
            point_a: Starting point of initial move
            point_b: End point of initial move
            point_c: Retracement point
            custom_levels: Optional custom extension levels

        Returns:
            Dictionary mapping extension levels to prices
        """
        levels = custom_levels or self.FIBONACCI_RATIOS["extension"]
        initial_move = point_b - point_a

        extensions = {}

        for level in levels:
            level_name = f"{level * 100:.1f}"
            extensions[level_name] = point_c + (initial_move * level)

        logger.debug(
            "Calculated extensions from A=%.4f, B=%.4f, C=%.4f: %s",
            point_a,
            point_b,
            point_c,
            extensions,
        )

        return extensions

    def calculate_projection(
        self,
        wave_1_start: float,
        wave_1_end: float,
        wave_2_end: float,
        custom_levels: Optional[List[float]] = None,
    ) -> Dict[str, float]:
        """Calculate Fibonacci projection levels for wave targets.

        Commonly used for projecting Wave 3 and Wave 5 targets.

        Args:
            wave_1_start: Start of Wave 1
            wave_1_end: End of Wave 1
            wave_2_end: End of Wave 2 (retracement)
            custom_levels: Optional custom projection levels

        Returns:
            Dictionary mapping projection levels to prices
        """
        levels = custom_levels or self.FIBONACCI_RATIOS["projection"]
        wave_1_size = abs(wave_1_end - wave_1_start)
        direction = 1 if wave_1_end > wave_1_start else -1

        projections = {}

        for level in levels:
            level_name = f"{level * 100:.1f}"
            projections[level_name] = wave_2_end + (wave_1_size * level * direction)

        return projections

    def find_fibonacci_clusters(
        self, price_levels: List[Dict[str, float]], tolerance: float = 0.002
    ) -> List[Dict[str, Union[float, List[str]]]]:
        """Find clusters of Fibonacci levels from multiple calculations.

        Args:
            price_levels: List of dictionaries containing Fibonacci levels
            tolerance: Price tolerance for clustering (as ratio)

        Returns:
            List of clusters with price and contributing levels
        """
        # Flatten all levels
        all_levels = []
        for level_dict in price_levels:
            for name, price in level_dict.items():
                all_levels.append({"name": name, "price": price})

        # Sort by price
        all_levels.sort(key=lambda x: x["price"])

        # Find clusters
        clusters = []
        current_cluster = []

        for level in all_levels:
            if not current_cluster:
                current_cluster = [level]
            else:
                # Check if within tolerance of cluster average
                cluster_avg = np.mean([l["price"] for l in current_cluster])
                if abs(level["price"] - cluster_avg) / cluster_avg <= tolerance:
                    current_cluster.append(level)
                else:
                    # Save current cluster and start new one
                    if len(current_cluster) >= 2:  # Only keep clusters with 2+ levels
                        clusters.append(
                            {
                                "price": cluster_avg,
                                "levels": [l["name"] for l in current_cluster],
                                "strength": len(current_cluster),
                            }
                        )
                    current_cluster = [level]

        # Don't forget the last cluster
        if len(current_cluster) >= 2:
            cluster_avg = np.mean([l["price"] for l in current_cluster])
            clusters.append(
                {
                    "price": cluster_avg,
                    "levels": [l["name"] for l in current_cluster],
                    "strength": len(current_cluster),
                }
            )

        # Sort by strength
        clusters.sort(key=lambda x: x["strength"], reverse=True)

        return clusters

    def calculate_time_projections(
        self,
        start_time: pd.Timestamp,
        end_time: pd.Timestamp,
        custom_ratios: Optional[List[float]] = None,
    ) -> Dict[str, pd.Timestamp]:
        """Calculate Fibonacci time projections.

        Args:
            start_time: Start timestamp
            end_time: End timestamp
            custom_ratios: Optional custom time ratios

        Returns:
            Dictionary mapping ratios to projected timestamps
        """
        ratios = custom_ratios or [0.382, 0.5, 0.618, 1.0, 1.618, 2.618]
        time_diff = end_time - start_time

        projections = {}

        for ratio in ratios:
            ratio_name = f"{ratio * 100:.1f}%"
            projections[ratio_name] = end_time + (time_diff * ratio)

        return projections

    def is_fibonacci_number(self, n: int) -> bool:
        """Check if a number is in the Fibonacci sequence.

        Args:
            n: Number to check

        Returns:
            True if number is in Fibonacci sequence
        """

        # A number is Fibonacci if one of (5*n^2 + 4) or (5*n^2 - 4) is a perfect square
        def is_perfect_square(x):
            sqrt = int(np.sqrt(x))
            return sqrt * sqrt == x

        return is_perfect_square(5 * n * n + 4) or is_perfect_square(5 * n * n - 4)

    def get_fibonacci_sequence(self, n: int) -> List[int]:
        """Generate Fibonacci sequence up to n terms.

        Args:
            n: Number of terms

        Returns:
            List of Fibonacci numbers
        """
        if n <= 0:
            return []
        elif n == 1:
            return [0]
        elif n == 2:
            return [0, 1]

        sequence = [0, 1]
        for i in range(2, n):
            sequence.append(sequence[-1] + sequence[-2])

        return sequence

    def calculate_fibonacci_spirals(
        self, center_price: float, price_range: float, num_spirals: int = 5
    ) -> List[Dict[str, float]]:
        """Calculate Fibonacci spiral levels around a center price.

        Args:
            center_price: Center price for spirals
            price_range: Price range for spiral calculation
            num_spirals: Number of spirals to calculate

        Returns:
            List of spiral dictionaries with inner and outer bounds
        """
        spirals = []
        fib_sequence = self.get_fibonacci_sequence(num_spirals + 2)[2:]  # Skip 0, 1

        for i, fib_num in enumerate(fib_sequence[:num_spirals]):
            spiral_range = price_range * (fib_num / fib_sequence[0])

            spirals.append(
                {
                    "spiral_number": i + 1,
                    "fibonacci_number": fib_num,
                    "inner_bound": center_price - spiral_range,
                    "outer_bound": center_price + spiral_range,
                    "range": spiral_range * 2,
                }
            )

        return spirals

    def calculate_golden_ratio_levels(
        self, price: float, direction: str = "both"
    ) -> Dict[str, float]:
        """Calculate golden ratio-based price levels.

        Args:
            price: Base price
            direction: 'up', 'down', or 'both'

        Returns:
            Dictionary of golden ratio levels
        """
        levels = {}

        # Powers of phi
        phi_powers = [
            self.PHI_INVERSE**2,  # 0.382
            self.PHI_INVERSE,  # 0.618
            1.0,  # 1.000
            self.PHI,  # 1.618
            self.PHI**2,  # 2.618
            self.PHI**3,  # 4.236
        ]

        for power in phi_powers:
            if direction in ["up", "both"]:
                levels[f"phi_{power:.3f}_up"] = price * power
            if direction in ["down", "both"]:
                levels[f"phi_{power:.3f}_down"] = price / power

        return levels

    def analyze_price_relationships(self, prices: List[float]) -> Dict[str, Any]:
        """Analyze Fibonacci relationships between price points.

        Args:
            prices: List of price points

        Returns:
            Dictionary of identified relationships
        """
        if len(prices) < 2:
            return {}

        relationships = {"ratios": [], "golden_ratios": [], "fibonacci_ratios": []}

        # Calculate all ratios between price points
        for i in range(len(prices)):
            for j in range(i + 1, len(prices)):
                ratio = prices[j] / prices[i] if prices[i] != 0 else 0
                inverse_ratio = prices[i] / prices[j] if prices[j] != 0 else 0

                ratio_info = {
                    "index_1": i,
                    "index_2": j,
                    "price_1": prices[i],
                    "price_2": prices[j],
                    "ratio": ratio,
                    "inverse_ratio": inverse_ratio,
                }

                relationships["ratios"].append(ratio_info)

                # Check for golden ratio relationships
                if abs(ratio - self.PHI) < 0.01 or abs(inverse_ratio - self.PHI) < 0.01:
                    relationships["golden_ratios"].append(ratio_info)

                # Check for common Fibonacci ratios
                fib_ratios = [0.236, 0.382, 0.5, 0.618, 0.786, 1.272, 1.618, 2.618]
                for fib_ratio in fib_ratios:
                    if (
                        abs(ratio - fib_ratio) < 0.01
                        or abs(inverse_ratio - fib_ratio) < 0.01
                    ):
                        ratio_info["fibonacci_ratio"] = fib_ratio
                        relationships["fibonacci_ratios"].append(ratio_info)
                        break

        return relationships

    def calculate_abc_correction_targets(
        self, wave_a_start: float, wave_a_end: float, wave_b_end: float
    ) -> Dict[str, float]:
        """Calculate targets for ABC corrective pattern.

        Args:
            wave_a_start: Start of Wave A
            wave_a_end: End of Wave A
            wave_b_end: End of Wave B

        Returns:
            Dictionary of Wave C targets
        """
        wave_a_size = abs(wave_a_end - wave_a_start)
        direction = -1 if wave_a_end > wave_a_start else 1  # C moves opposite to A

        targets = {
            "61.8%_of_A": wave_b_end + (wave_a_size * 0.618 * direction),
            "100%_of_A": wave_b_end + (wave_a_size * 1.0 * direction),
            "127.2%_of_A": wave_b_end + (wave_a_size * 1.272 * direction),
            "161.8%_of_A": wave_b_end + (wave_a_size * 1.618 * direction),
        }

        return targets
