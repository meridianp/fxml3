"""Fibonacci calculations for Elliott Wave analysis."""

from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


class FibonacciCalculator:
    """Calculator for Fibonacci ratios and retracements in price data."""

    # Common Fibonacci ratios used in technical analysis
    FIBONACCI_RATIOS = {
        "0.236": 0.236,
        "0.382": 0.382,
        "0.5": 0.5,
        "0.618": 0.618,
        "0.786": 0.786,
        "1.0": 1.0,
        "1.618": 1.618,
        "2.618": 2.618,
        "3.618": 3.618,
        "4.236": 4.236,
    }

    def __init__(self, tolerance: float = 0.1):
        """Initialize the Fibonacci calculator.
        
        Args:
            tolerance: Tolerance percentage for ratio validation
        """
        self.tolerance = tolerance
        
    def calculate_retracement_levels(
        self,
        start_price: float,
        end_price: float,
        levels: List[float] = None
    ) -> Dict[str, float]:
        """Calculate Fibonacci retracement levels between two price points.
        
        Args:
            start_price: Starting price point
            end_price: Ending price point
            levels: List of Fibonacci levels to calculate
            
        Returns:
            Dictionary of Fibonacci levels and prices
        """
        if levels is None:
            levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        
        price_range = end_price - start_price
        result = {}
        
        for level in levels:
            retrace_price = end_price - (price_range * level)
            result[str(level)] = retrace_price
            
        return result
    
    def calculate_extension_levels(
        self,
        start_price: float,
        end_price: float,
        levels: List[float] = None
    ) -> Dict[str, float]:
        """Calculate Fibonacci extension levels beyond two price points.
        
        Args:
            start_price: Starting price point
            end_price: Ending price point
            levels: List of Fibonacci levels to calculate
            
        Returns:
            Dictionary of Fibonacci levels and prices
        """
        if levels is None:
            levels = [1.0, 1.618, 2.0, 2.618, 3.618, 4.236]
        
        price_range = abs(end_price - start_price)
        result = {}
        
        if start_price < end_price:
            # Uptrend
            for level in levels:
                extension_price = start_price + (price_range * level)
                result[str(level)] = extension_price
        else:
            # Downtrend
            for level in levels:
                extension_price = start_price - (price_range * level)
                result[str(level)] = extension_price
            
        return result
    
    def validate_ratio(
        self,
        actual_ratio: float,
        expected_ratio: float,
        tolerance: float = None
    ) -> bool:
        """Validate if an actual ratio is within tolerance of an expected ratio.
        
        Args:
            actual_ratio: The ratio to validate
            expected_ratio: The expected Fibonacci ratio
            tolerance: Tolerance range (percentage)
            
        Returns:
            Boolean indicating if the ratio is valid
        """
        if tolerance is None:
            tolerance = self.tolerance
            
        lower_bound = expected_ratio * (1 - tolerance)
        upper_bound = expected_ratio * (1 + tolerance)
        
        return lower_bound <= actual_ratio <= upper_bound
    
    def find_closest_ratio(
        self,
        actual_ratio: float,
        possible_ratios: List[float] = None
    ) -> Tuple[float, float]:
        """Find the Fibonacci ratio closest to the given ratio.
        
        Args:
            actual_ratio: The ratio to match
            possible_ratios: List of possible Fibonacci ratios
            
        Returns:
            Tuple of (closest_ratio, distance)
        """
        if possible_ratios is None:
            possible_ratios = list(self.FIBONACCI_RATIOS.values())
        
        absolute_ratio = abs(actual_ratio)
        distances = [(ratio, abs(absolute_ratio - ratio)) for ratio in possible_ratios]
        closest_ratio, distance = min(distances, key=lambda x: x[1])
        
        return closest_ratio, distance
    
    def get_ratio_significance(
        self,
        ratio: float,
        tolerance: float = None
    ) -> float:
        """Calculate how significant a ratio is in terms of Fibonacci values.
        
        Args:
            ratio: The ratio to evaluate
            tolerance: Tolerance for matching
            
        Returns:
            Score from 0 to 1 indicating significance
        """
        if tolerance is None:
            tolerance = self.tolerance
            
        closest_ratio, distance = self.find_closest_ratio(ratio)
        
        if distance <= closest_ratio * tolerance:
            # Within tolerance, high significance
            significance = 1.0 - (distance / (closest_ratio * tolerance))
        else:
            # Outside tolerance, decreasing significance
            significance = max(0, 0.5 - (distance / closest_ratio))
            
        return max(0, min(1, significance))
    
    def analyze_wave_ratios(
        self,
        waves: List[Dict]
    ) -> Dict[str, Dict]:
        """Analyze the ratios between consecutive waves.
        
        Args:
            waves: List of wave dictionaries
            
        Returns:
            Dictionary with wave ratio analysis
        """
        if len(waves) < 2:
            return {}
            
        result = {
            'size_ratios': {},
            'retracement_ratios': {},
            'extension_ratios': {},
            'time_ratios': {},
        }
        
        # Calculate ratios between consecutive waves
        for i in range(len(waves) - 1):
            current = waves[i]
            next_wave = waves[i+1]
            
            # Size ratio (next wave size / current wave size)
            size_ratio = next_wave['wave_size'] / current['wave_size']
            result['size_ratios'][f"{i+1}_{i+2}"] = {
                'value': size_ratio,
                'closest_fib': self.find_closest_ratio(size_ratio)[0],
                'significance': self.get_ratio_significance(size_ratio),
            }
            
            # Retracement ratio for corrective waves
            if (current['wave_type'] == 'up' and next_wave['wave_type'] == 'down') or \
               (current['wave_type'] == 'down' and next_wave['wave_type'] == 'up'):
                retrace_ratio = next_wave['wave_size'] / current['wave_size']
                result['retracement_ratios'][f"{i+1}_{i+2}"] = {
                    'value': retrace_ratio,
                    'closest_fib': self.find_closest_ratio(retrace_ratio)[0],
                    'significance': self.get_ratio_significance(retrace_ratio),
                }
            
            # Time ratio (next wave length / current wave length)
            time_ratio = next_wave['wave_length'] / current['wave_length']
            result['time_ratios'][f"{i+1}_{i+2}"] = {
                'value': time_ratio,
                'closest_fib': self.find_closest_ratio(time_ratio)[0],
                'significance': self.get_ratio_significance(time_ratio),
            }
        
        # Calculate extension ratios for non-consecutive waves
        for i in range(len(waves) - 2):
            for j in range(i + 2, len(waves)):
                # Only compare waves in the same direction
                if waves[i]['wave_type'] == waves[j]['wave_type']:
                    ext_ratio = waves[j]['wave_size'] / waves[i]['wave_size']
                    result['extension_ratios'][f"{i+1}_{j+1}"] = {
                        'value': ext_ratio,
                        'closest_fib': self.find_closest_ratio(ext_ratio)[0],
                        'significance': self.get_ratio_significance(ext_ratio),
                    }
        
        return result
    
    def calculate_pattern_significance(
        self,
        ratio_analysis: Dict[str, Dict]
    ) -> float:
        """Calculate overall significance of a wave pattern based on Fibonacci ratios.
        
        Args:
            ratio_analysis: Output from analyze_wave_ratios
            
        Returns:
            Score from 0 to 1 indicating pattern significance
        """
        if not ratio_analysis:
            return 0.0
            
        all_significances = []
        
        # Collect all significance scores
        for ratio_type, ratios in ratio_analysis.items():
            for _, details in ratios.items():
                all_significances.append(details['significance'])
                
        if not all_significances:
            return 0.0
            
        # Return average significance score
        return sum(all_significances) / len(all_significances)
    
    def calculate_fibonacci_price_zones(
        self,
        df: pd.DataFrame,
        window_size: int = 20
    ) -> pd.DataFrame:
        """Calculate Fibonacci price zones based on local highs and lows.
        
        Args:
            df: DataFrame with price data
            window_size: Window size for finding local highs and lows
            
        Returns:
            DataFrame with Fibonacci price zones
        """
        if df.empty or 'high' not in df.columns or 'low' not in df.columns:
            return df
            
        # Create a copy to avoid modifying the original
        result_df = df.copy()
        
        # Find local highs and lows
        result_df['local_high'] = result_df['high'].rolling(window=window_size, center=True).max()
        result_df['local_low'] = result_df['low'].rolling(window=window_size, center=True).min()
        result_df['local_range'] = result_df['local_high'] - result_df['local_low']
        
        # Calculate Fibonacci levels from high to low
        fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        
        for level in fib_levels:
            # Retracement from high to low
            result_df[f'fib_level_{int(level*1000)}'] = result_df['local_high'] - (result_df['local_range'] * level)
            
        # Calculate distance of current price to Fibonacci levels
        for level in fib_levels:
            result_df[f'fib_dist_{int(level*1000)}'] = (
                result_df['close'] - result_df[f'fib_level_{int(level*1000)}']
            ).abs()
            
        # Identify the closest Fibonacci level
        fib_dist_cols = [f'fib_dist_{int(level*1000)}' for level in fib_levels]
        result_df['closest_fib_level'] = result_df[fib_dist_cols].idxmin(axis=1)
        
        # Calculate distance to closest Fibonacci level as percentage of range
        result_df['closest_fib_dist_pct'] = result_df.apply(
            lambda row: row[row['closest_fib_level']] / row['local_range'] 
            if row['local_range'] > 0 else np.nan, 
            axis=1
        )
        
        # Flag potential reversal zones (very close to a Fibonacci level)
        result_df['at_fib_level'] = result_df['closest_fib_dist_pct'] < 0.02  # Within 2% of a Fibonacci level
        
        return result_df