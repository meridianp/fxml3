"""Feature engineering module for Elliott Wave analysis."""

import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def extract_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Extract candlestick patterns from OHLCV data.

    Args:
        df: DataFrame with OHLCV data

    Returns:
        DataFrame with candlestick pattern features
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for candlestick pattern extraction")
        return df

    # Create a copy to avoid modifying the original
    result_df = df.copy()

    # Ensure required columns exist
    required_columns = ["open", "high", "low", "close"]
    for col in required_columns:
        if col not in result_df.columns:
            logger.error(f"Required column '{col}' not found in DataFrame")
            raise ValueError(f"Required column '{col}' not found in DataFrame")

    try:
        import pandas_ta as ta

        # Calculate candlestick pattern features
        # Body size (absolute and relative)
        result_df["body_size"] = abs(result_df["close"] - result_df["open"])
        result_df["body_size_relative"] = result_df["body_size"] / (
            result_df["high"] - result_df["low"]
        )

        # Upper and lower shadows
        result_df["upper_shadow"] = result_df.apply(
            lambda x: x["high"] - max(x["open"], x["close"]), axis=1
        )
        result_df["lower_shadow"] = result_df.apply(
            lambda x: min(x["open"], x["close"]) - x["low"], axis=1
        )

        # Shadow to body ratio
        result_df["upper_shadow_ratio"] = result_df["upper_shadow"] / result_df[
            "body_size"
        ].replace(0, np.nan)
        result_df["lower_shadow_ratio"] = result_df["lower_shadow"] / result_df[
            "body_size"
        ].replace(0, np.nan)

        # Candlestick direction
        result_df["candle_direction"] = np.where(
            result_df["close"] >= result_df["open"], 1, -1
        )

        # Range (high - low)
        result_df["range"] = result_df["high"] - result_df["low"]

        # Relative position of close within day's range
        result_df["close_position"] = (
            result_df["close"] - result_df["low"]
        ) / result_df["range"].replace(0, np.nan)

        # Specific candlestick patterns (using pandas_ta)
        # Doji
        result_df["doji"] = ta.cdl_pattern(
            open_=result_df["open"],
            high=result_df["high"],
            low=result_df["low"],
            close=result_df["close"],
            name="doji",
        )

        # Hammer
        result_df["hammer"] = ta.cdl_pattern(
            open_=result_df["open"],
            high=result_df["high"],
            low=result_df["low"],
            close=result_df["close"],
            name="hammer",
        )

        # Shooting Star
        result_df["shooting_star"] = ta.cdl_pattern(
            open_=result_df["open"],
            high=result_df["high"],
            low=result_df["low"],
            close=result_df["close"],
            name="shootingstar",
        )

        # Engulfing
        result_df["engulfing"] = ta.cdl_pattern(
            open_=result_df["open"],
            high=result_df["high"],
            low=result_df["low"],
            close=result_df["close"],
            name="engulfing",
        )

        return result_df

    except ImportError:
        logger.error("pandas_ta is required for candlestick pattern extraction")
        raise ImportError("pandas_ta is required for candlestick pattern extraction")


def extract_fibonacci_features(df: pd.DataFrame, window_size: int = 20) -> pd.DataFrame:
    """Extract Fibonacci-related features from price data.

    Args:
        df: DataFrame with OHLCV data
        window_size: Window size for local highs and lows detection

    Returns:
        DataFrame with Fibonacci features
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for Fibonacci feature extraction")
        return df

    # Create a copy to avoid modifying the original
    result_df = df.copy()

    # Ensure required columns exist
    required_columns = ["high", "low", "close"]
    for col in required_columns:
        if col not in result_df.columns:
            logger.error(f"Required column '{col}' not found in DataFrame")
            raise ValueError(f"Required column '{col}' not found in DataFrame")

    # Find local highs and lows
    result_df["local_high"] = (
        result_df["high"].rolling(window=window_size, center=True).max()
    )
    result_df["local_low"] = (
        result_df["low"].rolling(window=window_size, center=True).min()
    )

    # Calculate the range
    result_df["local_range"] = result_df["local_high"] - result_df["local_low"]

    # Fibonacci retracement levels (from recent high)
    fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]

    for level in fib_levels:
        # Retracement from high
        result_df[f"fib_high_{int(level*1000)}"] = result_df["local_high"] - (
            result_df["local_range"] * level
        )
        # Retracement from low
        result_df[f"fib_low_{int(level*1000)}"] = result_df["local_low"] + (
            result_df["local_range"] * level
        )

    # Distance of current price to Fibonacci levels
    for level in fib_levels:
        # Distance to retracement from high
        result_df[f"dist_fib_high_{int(level*1000)}"] = abs(
            result_df["close"] - result_df[f"fib_high_{int(level*1000)}"]
        )
        # Distance to retracement from low
        result_df[f"dist_fib_low_{int(level*1000)}"] = abs(
            result_df["close"] - result_df[f"fib_low_{int(level*1000)}"]
        )

    # Proximity to any Fibonacci level
    all_fib_columns = [f"fib_high_{int(level*1000)}" for level in fib_levels] + [
        f"fib_low_{int(level*1000)}" for level in fib_levels
    ]

    # Calculate minimum distance to any Fibonacci level
    result_df["min_fib_distance"] = result_df.apply(
        lambda row: min([abs(row["close"] - row[col]) for col in all_fib_columns]),
        axis=1,
    )

    # Calculate which Fibonacci level is closest
    def closest_fib_level(row):
        distances = {col: abs(row["close"] - row[col]) for col in all_fib_columns}
        return min(distances, key=distances.get)

    result_df["closest_fib_level"] = result_df.apply(closest_fib_level, axis=1)

    # Calculate relative position between recent high and low (0 = at low, 1 = at high)
    result_df["relative_position"] = (
        result_df["close"] - result_df["local_low"]
    ) / result_df["local_range"].replace(0, np.nan)

    return result_df


def extract_trend_features(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    """Extract trend-related features from price data.

    Args:
        df: DataFrame with OHLCV data
        periods: List of periods for moving averages and other indicators

    Returns:
        DataFrame with trend features
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for trend feature extraction")
        return df

    # Create a copy to avoid modifying the original
    result_df = df.copy()

    # Ensure required columns exist
    if "close" not in result_df.columns:
        logger.error("Required column 'close' not found in DataFrame")
        raise ValueError("Required column 'close' not found in DataFrame")

    # Default periods if none specified
    if periods is None:
        periods = [10, 20, 50, 100, 200]

    try:
        import pandas_ta as ta

        # Add simple moving averages
        for period in periods:
            result_df[f"sma_{period}"] = ta.sma(result_df["close"], length=period)

        # Calculate price relative to moving averages
        for period in periods:
            # Price relative to SMA (above/below)
            result_df[f"price_rel_sma_{period}"] = (
                result_df["close"] / result_df[f"sma_{period}"] - 1
            )

        # Moving average crossovers
        # Fast MA crossing Slow MA
        for i, fast_period in enumerate(periods[:-1]):
            for slow_period in periods[i + 1 :]:
                result_df[f"sma_{fast_period}_cross_sma_{slow_period}"] = np.where(
                    result_df[f"sma_{fast_period}"] > result_df[f"sma_{slow_period}"],
                    1,
                    -1,
                )

        # Slope of moving averages
        for period in periods:
            # Calculate the slope of SMA using rolling regression
            result_df[f"sma_{period}_slope"] = ta.slope(
                result_df[f"sma_{period}"], length=5
            )

        # Add momentum indicators
        # RSI
        result_df["rsi_14"] = ta.rsi(result_df["close"], length=14)

        # MACD
        macd = ta.macd(result_df["close"], fast=12, slow=26, signal=9)
        result_df = pd.concat([result_df, macd], axis=1)

        # ADX (trend strength)
        adx = ta.adx(
            high=result_df["high"],
            low=result_df["low"],
            close=result_df["close"],
            length=14,
        )
        result_df = pd.concat([result_df, adx], axis=1)

        return result_df

    except ImportError:
        logger.error("pandas_ta is required for trend feature extraction")
        raise ImportError("pandas_ta is required for trend feature extraction")


def extract_wave_features(
    df: pd.DataFrame, min_length: int = 5, max_length: int = 50
) -> pd.DataFrame:
    """Extract features that help identify Elliott Wave patterns.

    Args:
        df: DataFrame with OHLCV data
        min_length: Minimum length for wave detection
        max_length: Maximum length for wave detection

    Returns:
        DataFrame with wave-related features
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for wave feature extraction")
        return df

    # Create a copy to avoid modifying the original
    result_df = df.copy()

    # Ensure required columns exist
    required_columns = ["high", "low", "close"]
    for col in required_columns:
        if col not in result_df.columns:
            logger.error(f"Required column '{col}' not found in DataFrame")
            raise ValueError(f"Required column '{col}' not found in DataFrame")

    # Identify potential peaks and troughs
    # A peak is where the price is higher than the n points before and after
    # A trough is where the price is lower than the n points before and after
    def is_peak(series, i, n):
        """Check if point i is a peak in the series."""
        if i < n or i >= len(series) - n:
            return False

        return all(series[i] > series[i - j] for j in range(1, n + 1)) and all(
            series[i] > series[i + j] for j in range(1, n + 1)
        )

    def is_trough(series, i, n):
        """Check if point i is a trough in the series."""
        if i < n or i >= len(series) - n:
            return False

        return all(series[i] < series[i - j] for j in range(1, n + 1)) and all(
            series[i] < series[i + j] for j in range(1, n + 1)
        )

    # Test multiple look-back/look-forward periods
    look_periods = [3, 5, 8, 13]  # Fibonacci numbers are often effective

    for n in look_periods:
        # Initialize peak and trough columns
        peak_col = f"peak_{n}"
        trough_col = f"trough_{n}"
        result_df[peak_col] = False
        result_df[trough_col] = False

        # Identify peaks and troughs
        for i in range(len(result_df)):
            result_df.at[i, peak_col] = is_peak(result_df["high"].values, i, n)
            result_df.at[i, trough_col] = is_trough(result_df["low"].values, i, n)

    # Calculate waves between peaks and troughs
    def extract_waves(df, n):
        """Extract waves from peaks and troughs."""
        peaks = df[df[f"peak_{n}"]].index.tolist()
        troughs = df[df[f"trough_{n}"]].index.tolist()

        # Combine and sort
        all_extremes = [(idx, "peak") for idx in peaks] + [
            (idx, "trough") for idx in troughs
        ]
        all_extremes.sort()

        # Need at least 2 extremes to form a wave
        if len(all_extremes) < 2:
            return pd.DataFrame()

        waves = []
        for i in range(len(all_extremes) - 1):
            start_idx, start_type = all_extremes[i]
            end_idx, end_type = all_extremes[i + 1]

            # Only consider valid waves (peak->trough or trough->peak)
            if start_type == end_type:
                continue

            # Check if wave length is within bounds
            wave_length = end_idx - start_idx
            if wave_length < min_length or wave_length > max_length:
                continue

            # Calculate wave properties
            if start_type == "peak":
                # Downwave (peak to trough)
                wave_type = "down"
                wave_start = df.loc[start_idx, "high"]
                wave_end = df.loc[end_idx, "low"]
            else:
                # Upwave (trough to peak)
                wave_type = "up"
                wave_start = df.loc[start_idx, "low"]
                wave_end = df.loc[end_idx, "high"]

            wave_size = abs(wave_end - wave_start)
            wave_size_pct = wave_size / wave_start * 100

            waves.append(
                {
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "wave_type": wave_type,
                    "wave_length": wave_length,
                    "wave_size": wave_size,
                    "wave_size_pct": wave_size_pct,
                    "start_price": wave_start,
                    "end_price": wave_end,
                }
            )

        return pd.DataFrame(waves)

    # Extract waves for each look period
    wave_dfs = {}
    for n in look_periods:
        wave_dfs[n] = extract_waves(result_df, n)

    # Calculate wave sequence features
    for n in look_periods:
        wave_df = wave_dfs[n]

        if wave_df.empty:
            continue

        # Identify possible impulse wave patterns (5-wave structure)
        # For simplicity, we're looking for 5 consecutive waves with alternating direction
        for i in range(len(wave_df) - 4):
            is_impulse = True
            current_direction = wave_df.iloc[i]["wave_type"]

            for j in range(1, 5):
                next_direction = wave_df.iloc[i + j]["wave_type"]
                if next_direction == current_direction:
                    is_impulse = False
                    break
                current_direction = next_direction

            if is_impulse:
                # Mark the waves as part of an impulse pattern
                for j in range(5):
                    wave_idx = i + j
                    wave_num = j + 1
                    wave_df.at[wave_idx, f"impulse_wave_{n}"] = wave_num

        # Identify possible corrective wave patterns (3-wave structure)
        for i in range(len(wave_df) - 2):
            is_corrective = True
            current_direction = wave_df.iloc[i]["wave_type"]

            for j in range(1, 3):
                next_direction = wave_df.iloc[i + j]["wave_type"]
                if next_direction == current_direction:
                    is_corrective = False
                    break
                current_direction = next_direction

            if is_corrective:
                # Mark the waves as part of a corrective pattern
                for j in range(3):
                    wave_idx = i + j
                    wave_num = j + 1
                    wave_df.at[wave_idx, f"corrective_wave_{n}"] = wave_num

    # Add features to the result DataFrame
    for n in look_periods:
        wave_df = wave_dfs[n]

        if wave_df.empty:
            continue

        # Initialize columns for wave patterns
        result_df[f"impulse_wave_{n}"] = 0
        result_df[f"corrective_wave_{n}"] = 0

        # Populate the DataFrame with wave information
        for _, wave in wave_df.iterrows():
            start_idx = wave["start_idx"]
            end_idx = wave["end_idx"]

            # Mark the wave type and number in the original DataFrame
            if f"impulse_wave_{n}" in wave and not pd.isna(wave[f"impulse_wave_{n}"]):
                wave_num = int(wave[f"impulse_wave_{n}"])
                result_df.loc[start_idx:end_idx, f"impulse_wave_{n}"] = wave_num

            if f"corrective_wave_{n}" in wave and not pd.isna(
                wave[f"corrective_wave_{n}"]
            ):
                wave_num = int(wave[f"corrective_wave_{n}"])
                result_df.loc[start_idx:end_idx, f"corrective_wave_{n}"] = wave_num

    return result_df
