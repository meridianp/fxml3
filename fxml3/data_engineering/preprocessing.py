"""Data preprocessing module for cleaning and transforming forex data."""

import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean OHLCV data by handling missing values and outliers.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        Cleaned DataFrame
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for cleaning")
        return df
    
    # Create a copy to avoid modifying the original
    cleaned_df = df.copy()
    
    # Ensure expected columns exist
    required_columns = ["open", "high", "low", "close"]
    existing_columns = cleaned_df.columns.tolist()
    
    for col in required_columns:
        if col not in existing_columns:
            logger.error(f"Required column '{col}' not found in DataFrame")
            raise ValueError(f"Required column '{col}' not found in DataFrame")
    
    # Handle missing values
    # For OHLC, forward fill is often appropriate (use last known price)
    cleaned_df[required_columns] = cleaned_df[required_columns].ffill()
    
    # If we still have NaN at the beginning, backfill
    cleaned_df[required_columns] = cleaned_df[required_columns].bfill()
    
    # Handle volume separately if it exists (replace NaN with 0)
    if "volume" in existing_columns:
        cleaned_df["volume"] = cleaned_df["volume"].fillna(0)
    
    # Ensure OHLC relationships are maintained
    # High should be >= Open, Close, Low
    # Low should be <= Open, Close, High
    cleaned_df["high"] = cleaned_df[["high", "open", "close"]].max(axis=1)
    cleaned_df["low"] = cleaned_df[["low", "open", "close"]].min(axis=1)
    
    # Detect and handle outliers using rolling median
    for col in required_columns:
        # Calculate rolling median and standard deviation
        rolling_median = cleaned_df[col].rolling(window=20, min_periods=1).median()
        rolling_std = cleaned_df[col].rolling(window=20, min_periods=1).std()
        
        # Define upper and lower bounds (5 standard deviations)
        upper_bound = rolling_median + 5 * rolling_std
        lower_bound = rolling_median - 5 * rolling_std
        
        # Find outliers
        outliers = (cleaned_df[col] > upper_bound) | (cleaned_df[col] < lower_bound)
        
        if outliers.any():
            n_outliers = outliers.sum()
            logger.warning(f"Found {n_outliers} outliers in '{col}' column")
            
            # Replace outliers with rolling median
            cleaned_df.loc[outliers, col] = rolling_median[outliers]
    
    return cleaned_df


def normalize_data(
    df: pd.DataFrame,
    method: str = "min_max",
    feature_range: Tuple[float, float] = (0, 1)
) -> Tuple[pd.DataFrame, Dict]:
    """Normalize OHLCV data for machine learning.
    
    Args:
        df: DataFrame with OHLCV data
        method: Normalization method ('min_max', 'z_score', 'decimal_scaling')
        feature_range: Range for min-max scaling (if method is 'min_max')
        
    Returns:
        Tuple of (normalized DataFrame, normalization parameters)
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for normalization")
        return df, {}
    
    # Create a copy to avoid modifying the original
    normalized_df = df.copy()
    
    # Columns to normalize (typically OHLC)
    price_columns = ["open", "high", "low", "close"]
    available_columns = [col for col in price_columns if col in normalized_df.columns]
    
    if not available_columns:
        logger.warning("No price columns found for normalization")
        return normalized_df, {}
    
    # Normalization parameters to return
    params = {}
    
    if method == "min_max":
        # Min-max scaling: (x - min) / (max - min) * (range_max - range_min) + range_min
        min_val = normalized_df[available_columns].min().min()
        max_val = normalized_df[available_columns].max().max()
        
        if max_val == min_val:
            logger.warning("Max value equals min value, skipping normalization")
            return normalized_df, {"min": min_val, "max": max_val}
        
        range_min, range_max = feature_range
        
        for col in available_columns:
            normalized_df[col] = (normalized_df[col] - min_val) / (max_val - min_val) * (range_max - range_min) + range_min
        
        params = {"method": "min_max", "min": min_val, "max": max_val, "feature_range": feature_range}
        
    elif method == "z_score":
        # Z-score scaling: (x - mean) / std
        means = {}
        stds = {}
        
        for col in available_columns:
            mean_val = normalized_df[col].mean()
            std_val = normalized_df[col].std()
            
            if std_val == 0:
                logger.warning(f"Standard deviation is 0 for '{col}', skipping normalization")
                continue
            
            normalized_df[col] = (normalized_df[col] - mean_val) / std_val
            means[col] = mean_val
            stds[col] = std_val
        
        params = {"method": "z_score", "means": means, "stds": stds}
        
    elif method == "decimal_scaling":
        # Decimal scaling: x / 10^d where d is the smallest integer such that max(|x|) < 1
        max_abs = {}
        scaling_factors = {}
        
        for col in available_columns:
            max_abs_val = abs(normalized_df[col]).max()
            scaling_factor = 10 ** len(str(int(max_abs_val)))
            
            normalized_df[col] = normalized_df[col] / scaling_factor
            max_abs[col] = max_abs_val
            scaling_factors[col] = scaling_factor
        
        params = {"method": "decimal_scaling", "max_abs": max_abs, "scaling_factors": scaling_factors}
        
    else:
        logger.error(f"Unsupported normalization method: {method}")
        raise ValueError(f"Unsupported normalization method: {method}")
    
    return normalized_df, params


def denormalize_data(
    df: pd.DataFrame,
    params: Dict
) -> pd.DataFrame:
    """Denormalize data back to original scale.
    
    Args:
        df: Normalized DataFrame
        params: Normalization parameters returned by normalize_data
        
    Returns:
        Denormalized DataFrame
    """
    if df.empty or not params:
        return df
    
    # Create a copy to avoid modifying the original
    denormalized_df = df.copy()
    
    method = params.get("method")
    
    if method == "min_max":
        min_val = params.get("min")
        max_val = params.get("max")
        feature_range = params.get("feature_range", (0, 1))
        range_min, range_max = feature_range
        
        price_columns = ["open", "high", "low", "close"]
        available_columns = [col for col in price_columns if col in denormalized_df.columns]
        
        for col in available_columns:
            denormalized_df[col] = (denormalized_df[col] - range_min) / (range_max - range_min) * (max_val - min_val) + min_val
    
    elif method == "z_score":
        means = params.get("means", {})
        stds = params.get("stds", {})
        
        for col, mean_val in means.items():
            if col in denormalized_df.columns:
                std_val = stds.get(col)
                denormalized_df[col] = denormalized_df[col] * std_val + mean_val
    
    elif method == "decimal_scaling":
        scaling_factors = params.get("scaling_factors", {})
        
        for col, factor in scaling_factors.items():
            if col in denormalized_df.columns:
                denormalized_df[col] = denormalized_df[col] * factor
    
    return denormalized_df


def add_technical_indicators(
    df: pd.DataFrame,
    indicators: List[str] = None,
    periods: List[int] = None,
) -> pd.DataFrame:
    """Add technical indicators to the DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
        indicators: List of indicators to add ('sma', 'ema', 'rsi', 'macd', 'bollinger', etc.)
        periods: List of periods to use for indicators
        
    Returns:
        DataFrame with added indicators
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for adding indicators")
        return df
    
    # Create a copy to avoid modifying the original
    result_df = df.copy()
    
    # Default indicators if none specified
    if indicators is None:
        indicators = ["sma", "ema", "rsi"]
    
    # Default periods if none specified
    if periods is None:
        periods = [14, 20, 50, 200]
    
    # Ensure required columns exist
    required_columns = ["close"]
    if "volume" in indicators:
        required_columns.append("volume")
    
    for col in required_columns:
        if col not in result_df.columns:
            logger.error(f"Required column '{col}' not found in DataFrame")
            raise ValueError(f"Required column '{col}' not found in DataFrame")
    
    try:
        import pandas_ta as ta
        
        for indicator in indicators:
            if indicator == "sma":
                # Simple Moving Average
                for period in periods:
                    result_df[f"sma_{period}"] = ta.sma(result_df["close"], length=period)
            
            elif indicator == "ema":
                # Exponential Moving Average
                for period in periods:
                    result_df[f"ema_{period}"] = ta.ema(result_df["close"], length=period)
            
            elif indicator == "rsi":
                # Relative Strength Index
                for period in periods:
                    result_df[f"rsi_{period}"] = ta.rsi(result_df["close"], length=period)
            
            elif indicator == "macd":
                # Moving Average Convergence Divergence
                macd = ta.macd(result_df["close"], fast=12, slow=26, signal=9)
                # Merge MACD columns into main dataframe
                result_df = pd.concat([result_df, macd], axis=1)
            
            elif indicator == "bollinger":
                # Bollinger Bands
                for period in periods:
                    bbands = ta.bbands(result_df["close"], length=period)
                    # Rename columns for clarity
                    bbands.columns = [f"bb_{period}_upper", f"bb_{period}_middle", f"bb_{period}_lower"]
                    result_df = pd.concat([result_df, bbands], axis=1)
            
            elif indicator == "atr":
                # Average True Range
                for period in periods:
                    result_df[f"atr_{period}"] = ta.atr(
                        high=result_df["high"],
                        low=result_df["low"],
                        close=result_df["close"],
                        length=period
                    )
            
            elif indicator == "adx":
                # Average Directional Index
                for period in periods:
                    adx = ta.adx(
                        high=result_df["high"],
                        low=result_df["low"],
                        close=result_df["close"],
                        length=period
                    )
                    # Rename columns for clarity
                    adx.columns = [f"adx_{period}", f"dmp_{period}", f"dmn_{period}"]
                    result_df = pd.concat([result_df, adx], axis=1)
            
            else:
                logger.warning(f"Unsupported indicator: {indicator}")
    
    except ImportError:
        logger.error("pandas_ta is required for technical indicators")
        raise ImportError("pandas_ta is required for technical indicators")
    
    return result_df


def resample_data(
    df: pd.DataFrame,
    timeframe: str,
    agg_dict: Optional[Dict] = None,
) -> pd.DataFrame:
    """Resample OHLCV data to a different timeframe.
    
    Args:
        df: DataFrame with OHLCV data (must have datetime index)
        timeframe: Target timeframe ('1min', '5min', '15min', '1h', '4h', '1d', '1w', etc.)
        agg_dict: Custom aggregation dictionary
        
    Returns:
        Resampled DataFrame
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for resampling")
        return df
    
    # Ensure DataFrame has datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        logger.error("DataFrame must have DatetimeIndex for resampling")
        raise ValueError("DataFrame must have DatetimeIndex for resampling")
    
    # Convert timeframe to pandas frequency string
    freq_map = {
        "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
        "1h": "1H", "2h": "2H", "4h": "4H", "8h": "8H",
        "1d": "1D", "1w": "1W", "1mo": "1M"
    }
    
    # Clean the timeframe string
    clean_tf = timeframe.lower().replace(" ", "")
    
    # Try to get the pandas frequency string
    pandas_freq = freq_map.get(clean_tf)
    if pandas_freq is None:
        # If not in the map, try to use the string directly
        pandas_freq = clean_tf
    
    # Default aggregation dictionary for OHLCV data
    if agg_dict is None:
        agg_dict = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last"
        }
        
        # Add volume if it exists
        if "volume" in df.columns:
            agg_dict["volume"] = "sum"
    
    # Ensure required columns exist
    for col in agg_dict.keys():
        if col not in df.columns:
            logger.warning(f"Column '{col}' specified in aggregation dictionary not found in DataFrame")
            # Remove from aggregation dictionary
            agg_dict.pop(col)
    
    if not agg_dict:
        logger.error("No valid columns found for resampling")
        raise ValueError("No valid columns found for resampling")
    
    try:
        # Resample the data
        resampled = df.resample(pandas_freq).agg(agg_dict)
        
        # Check if resampling created empty rows
        if resampled.isna().all(axis=1).any():
            # Remove rows with all NaN values
            resampled = resampled.dropna(how="all")
        
        return resampled
    
    except Exception as e:
        logger.error(f"Error during resampling: {str(e)}")
        raise ValueError(f"Error during resampling: {str(e)}")