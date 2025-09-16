"""
Timeframe conversion module.

This module provides functionality to convert data between different timeframes
through resampling, aggregation, and timeframe transformation.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Union, Any

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def resample_ohlcv(
    df: pd.DataFrame,
    timeframe: str,
    price_column: Optional[str] = None,
    volume_column: str = "volume",
    timestamp_column: Optional[str] = None,
) -> pd.DataFrame:
    """
    Resample OHLCV data to a different timeframe.
    
    Args:
        df: DataFrame containing OHLCV data
        timeframe: Target timeframe as a pandas-compatible string (e.g., '5T', '1H', '1D')
        price_column: Name of the price column if df has only one price column
        volume_column: Name of the volume column
        timestamp_column: Name of the timestamp column if not the index
        
    Returns:
        Resampled DataFrame with OHLCV data
        
    Note:
        If df has open, high, low, close columns, they will be resampled accordingly.
        If df has only one price column (specified by price_column), it will be used 
        to generate OHLC data.
    """
    # Handle case when timestamp is a column, not the index
    if timestamp_column is not None and timestamp_column in df.columns:
        df = df.set_index(timestamp_column)
    
    # Ensure the index is datetime type
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # Check if we have OHLC data or just price data
    has_ohlc = all(col in df.columns for col in ["open", "high", "low", "close"])
    
    if has_ohlc:
        # Resample OHLCV data
        resampled = df.resample(timeframe).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            volume_column: "sum"
        })
    elif price_column is not None:
        # If we only have a single price column, use it to generate OHLC
        resampled = df.resample(timeframe).agg({
            price_column: ["first", "max", "min", "last"],
            volume_column: "sum"
        })
        
        # Rename columns
        resampled.columns = ["open", "high", "low", "close", "volume"]
    else:
        raise ValueError("DataFrame must either have OHLC columns or a specified price column")
    
    # Drop rows with NaN values (can happen if there's no data in a time period)
    resampled = resampled.dropna()
    
    return resampled


def convert_timeframe(
    df: pd.DataFrame,
    source_timeframe: str,
    target_timeframe: str
) -> pd.DataFrame:
    """
    Convert data from one timeframe to another, handling both upsampling and downsampling.
    
    Args:
        df: DataFrame containing OHLCV data with timestamp index
        source_timeframe: Source timeframe as a pandas-compatible string (e.g., '1T', '5T')
        target_timeframe: Target timeframe as a pandas-compatible string (e.g., '5T', '1H')
        
    Returns:
        DataFrame with data converted to the target timeframe
        
    Note:
        This function handles both upsampling (e.g., 1min -> 5min) and downsampling
        (e.g., 1h -> 1min). When downsampling, values are interpolated or forward filled.
    """
    # Convert string timeframes to pandas frequency strings if needed
    source_freq = convert_to_pandas_freq(source_timeframe)
    target_freq = convert_to_pandas_freq(target_timeframe)
    
    # Parse frequencies to determine if we're upsampling or downsampling
    source_td = pd.tseries.frequencies.to_offset(source_freq).delta
    target_td = pd.tseries.frequencies.to_offset(target_freq).delta
    
    # Determine if we're upsampling (e.g., 1min -> 5min) or downsampling (e.g., 1h -> 1min)
    if target_td > source_td:
        # Upsampling
        return resample_ohlcv(df, target_freq)
    else:
        # Downsampling
        # For OHLCV data, downsampling doesn't make much sense from a trading perspective,
        # but we'll implement it for completeness
        
        # Create a new index with the target frequency
        start_time = df.index.min()
        end_time = df.index.max()
        new_index = pd.date_range(start=start_time, end=end_time, freq=target_freq)
        
        # Create a new DataFrame with this index
        new_df = pd.DataFrame(index=new_index)
        
        # Merge with the original data
        result = pd.merge_asof(
            new_df, 
            df, 
            left_index=True, 
            right_index=True,
            direction='backward'
        )
        
        # Forward fill missing values
        result = result.ffill()
        
        return result


def convert_to_pandas_freq(timeframe: str) -> str:
    """
    Convert a timeframe string to a pandas frequency string.
    
    Args:
        timeframe: Timeframe string (e.g., '1m', '5m', '1h', '4h', '1d')
        
    Returns:
        Pandas frequency string (e.g., '1T', '5T', '1H', '4H', '1D')
    """
    # If it's already a pandas frequency string, return it
    if timeframe[-1] in 'TWDMYS':
        return timeframe
    
    # Extract the number and unit
    numeric_part = ''.join(filter(str.isdigit, timeframe))
    unit = timeframe.strip(numeric_part).lower()
    
    # Map units to pandas frequency strings
    unit_map = {
        'm': 'T',  # minute -> T (not M which is month)
        'min': 'T',
        'minute': 'T',
        'h': 'H',
        'hr': 'H', 
        'hour': 'H',
        'd': 'D',
        'day': 'D',
        'w': 'W',
        'week': 'W',
        'mo': 'M',
        'month': 'M',
    }
    
    if unit not in unit_map:
        raise ValueError(f"Unsupported timeframe unit: {unit}")
    
    return f"{numeric_part}{unit_map[unit]}"


class TimeframeConverter:
    """
    Class for managing conversion between different timeframes.
    
    This class provides methods for converting data between different timeframes
    and for maintaining a set of derived timeframes from a base timeframe.
    """
    
    def __init__(
        self,
        base_timeframe: str = "1m",
        derived_timeframes: List[str] = None
    ):
        """
        Initialize the timeframe converter.
        
        Args:
            base_timeframe: Base timeframe for data (e.g., '1m')
            derived_timeframes: List of timeframes to derive from the base timeframe
                               (e.g., ['5m', '15m', '1h', '4h'])
        """
        self.base_timeframe = base_timeframe
        self.derived_timeframes = derived_timeframes or ["5m", "15m", "1h", "4h", "1d"]
        
        # Cache for converted data
        self.cache: Dict[str, Dict[str, pd.DataFrame]] = {}
        
        # Convert all timeframes to pandas frequency strings
        self.base_freq = convert_to_pandas_freq(base_timeframe)
        self.derived_freqs = [convert_to_pandas_freq(tf) for tf in self.derived_timeframes]
        
        logger.info(f"Initialized TimeframeConverter with base timeframe {base_timeframe}")
        logger.info(f"Derived timeframes: {self.derived_timeframes}")
    
    def update_data(
        self,
        symbol: str,
        data: pd.DataFrame,
        timeframe: str = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Update data for a symbol and convert to all derived timeframes.
        
        Args:
            symbol: Trading symbol
            data: DataFrame containing OHLCV data for the base timeframe
            timeframe: Timeframe of the provided data (if None, assumes base_timeframe)
            
        Returns:
            Dictionary mapping timeframe to converted DataFrame
        """
        # Use base timeframe if not specified
        if timeframe is None:
            timeframe = self.base_timeframe
        
        # Convert to pandas frequency string
        freq = convert_to_pandas_freq(timeframe)
        
        # Initialize cache for this symbol if needed
        if symbol not in self.cache:
            self.cache[symbol] = {}
        
        # Store the data for the provided timeframe
        self.cache[symbol][freq] = data
        
        # Convert to derived timeframes
        result = {freq: data}
        
        for target_freq in self.derived_freqs:
            # Skip if it's the same as the input timeframe
            if target_freq == freq:
                continue
            
            # Convert data
            try:
                converted = resample_ohlcv(data, target_freq)
                
                # Store in cache
                self.cache[symbol][target_freq] = converted
                
                # Add to result
                result[target_freq] = converted
            except Exception as e:
                logger.error(f"Error converting {symbol} from {freq} to {target_freq}: {e}")
        
        return result
    
    def get_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Get data for a symbol and timeframe from the cache.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe to retrieve
            start_time: Optional start time to filter data
            end_time: Optional end time to filter data
            
        Returns:
            DataFrame containing OHLCV data for the requested timeframe
        """
        # Convert to pandas frequency string
        freq = convert_to_pandas_freq(timeframe)
        
        # Check if we have data for this symbol and timeframe
        if symbol not in self.cache or freq not in self.cache[symbol]:
            logger.warning(f"No data found for {symbol} at timeframe {timeframe}")
            return pd.DataFrame()
        
        # Get the data
        df = self.cache[symbol][freq]
        
        # Apply time filters if provided
        if start_time is not None or end_time is not None:
            mask = True
            
            if start_time is not None:
                mask = mask & (df.index >= start_time)
            
            if end_time is not None:
                mask = mask & (df.index <= end_time)
            
            df = df[mask]
        
        return df
    
    def get_latest_candle(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[pd.Series]:
        """
        Get the latest candle for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe to retrieve
            
        Returns:
            Series containing the latest candle data or None if not available
        """
        # Get the data
        df = self.get_data(symbol, timeframe)
        
        if df.empty:
            return None
        
        # Return the latest candle
        return df.iloc[-1]
    
    def clear_cache(self):
        """Clear the data cache."""
        self.cache = {}
        logger.info("Cleared timeframe conversion cache")


def combine_timeframes(
    symbol: str,
    dataframes: Dict[str, pd.DataFrame]
) -> Dict[str, pd.DataFrame]:
    """
    Combine data from multiple timeframes for a symbol.
    
    This is useful for creating multi-timeframe features where you want
    different feature sets at different resolutions.
    
    Args:
        symbol: Trading symbol
        dataframes: Dictionary mapping timeframe to DataFrame
        
    Returns:
        Dictionary mapping timeframe to DataFrame with additional columns
        from other timeframes
    """
    result = {}
    
    # Sort timeframes by duration (shortest to longest)
    sorted_timeframes = sorted(
        dataframes.keys(), 
        key=lambda x: pd.tseries.frequencies.to_offset(convert_to_pandas_freq(x)).delta
    )
    
    # Start with the shortest timeframe
    base_tf = sorted_timeframes[0]
    base_df = dataframes[base_tf].copy()
    
    # Add features from longer timeframes
    for tf in sorted_timeframes[1:]:
        df = dataframes[tf]
        
        # Resample to the base timeframe with forward fill
        resampled = df.resample(convert_to_pandas_freq(base_tf)).ffill()
        
        # Rename columns to include the timeframe
        renamed = resampled.rename(columns={
            col: f"{col}_{tf}" for col in resampled.columns
        })
        
        # Join with the base DataFrame
        base_df = base_df.join(renamed, how='left')
        
        # Forward fill any missing values
        base_df = base_df.ffill()
    
    # Store the combined DataFrame
    result[base_tf] = base_df
    
    return result