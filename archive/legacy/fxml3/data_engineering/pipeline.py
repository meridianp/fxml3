"""Data pipeline for FXML3."""

import logging
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

from fxml3.data_engineering.data_feeds import create_data_feed
from fxml3.data_engineering.data_loader import ForexDataLoader
from fxml3.data_engineering.feature_engineering import (
    extract_candlestick_patterns,
    extract_fibonacci_features,
    extract_trend_features,
    extract_wave_features,
)
from fxml3.data_engineering.preprocessing import (
    add_technical_indicators,
    clean_data,
    normalize_data,
    resample_data,
)

logger = logging.getLogger(__name__)


class DataPipeline:
    """Pipeline for loading, processing, and feature engineering of forex data."""

    def __init__(
        self,
        data_source: str = "yahoo",
        cache_dir: Optional[str] = None,
        **kwargs,
    ):
        """Initialize the data pipeline.

        Args:
            data_source: Source of the data ("yahoo", "fxcm", "ib", "csv")
            cache_dir: Directory to cache downloaded data
            **kwargs: Additional arguments for the data loader
        """
        self.data_loader = ForexDataLoader(
            data_source=data_source,
            cache_dir=cache_dir,
            **kwargs,
        )
        
        # Pipeline configuration
        self.clean_data = True
        self.add_indicators = True
        self.normalize = False
        self.add_candlestick_patterns = False
        self.add_fibonacci_features = False
        self.add_trend_features = False
        self.add_wave_features = False
        
        # Default indicator settings
        self.indicators = ["sma", "ema", "rsi", "macd", "bollinger", "atr"]
        self.periods = [14, 20, 50, 200]
        
        # Default resampling settings
        self.resampled_timeframe = None
        
        # Normalization parameters
        self.normalization_method = "min_max"
        self.normalization_params = {}
    
    def set_config(
        self,
        clean_data: bool = True,
        add_indicators: bool = True,
        normalize: bool = False,
        add_candlestick_patterns: bool = False,
        add_fibonacci_features: bool = False,
        add_trend_features: bool = False,
        add_wave_features: bool = False,
        indicators: Optional[List[str]] = None,
        periods: Optional[List[int]] = None,
        resampled_timeframe: Optional[str] = None,
        normalization_method: str = "min_max",
    ) -> None:
        """Configure the pipeline.

        Args:
            clean_data: Whether to clean the data
            add_indicators: Whether to add technical indicators
            normalize: Whether to normalize the data
            add_candlestick_patterns: Whether to extract candlestick patterns
            add_fibonacci_features: Whether to extract Fibonacci features
            add_trend_features: Whether to extract trend features
            add_wave_features: Whether to extract wave features
            indicators: List of indicators to add
            periods: List of periods for indicators
            resampled_timeframe: Target timeframe for resampling
            normalization_method: Method for normalization
        """
        self.clean_data = clean_data
        self.add_indicators = add_indicators
        self.normalize = normalize
        self.add_candlestick_patterns = add_candlestick_patterns
        self.add_fibonacci_features = add_fibonacci_features
        self.add_trend_features = add_trend_features
        self.add_wave_features = add_wave_features
        
        if indicators is not None:
            self.indicators = indicators
            
        if periods is not None:
            self.periods = periods
            
        self.resampled_timeframe = resampled_timeframe
        self.normalization_method = normalization_method
    
    def process(
        self,
        symbol: str,
        start_date: Union[str, pd.Timestamp],
        end_date: Optional[Union[str, pd.Timestamp]] = None,
        timeframe: str = "1D",
        include_after_hours: bool = False,
    ) -> Tuple[pd.DataFrame, Dict]:
        """Load and process data through the pipeline.

        Args:
            symbol: Symbol to process
            start_date: Start date
            end_date: End date (defaults to current date)
            timeframe: Timeframe for the data
            include_after_hours: Whether to include after-hours data

        Returns:
            Tuple of (processed DataFrame, processing metadata)
        """
        # Load data
        logger.info(f"Loading data for {symbol} from {start_date} to {end_date}")
        df = self.data_loader.load_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            include_after_hours=include_after_hours,
        )
        
        if df.empty:
            logger.warning(f"No data found for {symbol}")
            return df, {}
        
        # Metadata to track processing steps
        metadata = {
            "symbol": symbol,
            "start_date": str(start_date),
            "end_date": str(end_date) if end_date else None,
            "timeframe": timeframe,
            "original_shape": df.shape,
            "processing_steps": [],
        }
        
        # Clean data
        if self.clean_data:
            try:
                logger.info("Cleaning data")
                df = clean_data(df)
                metadata["processing_steps"].append("clean_data")
            except Exception as e:
                logger.error(f"Error cleaning data: {str(e)}")
        
        # Resample data if needed
        if self.resampled_timeframe is not None:
            try:
                logger.info(f"Resampling data to {self.resampled_timeframe}")
                df = resample_data(df, self.resampled_timeframe)
                metadata["processing_steps"].append(f"resample_{self.resampled_timeframe}")
                metadata["resampled_timeframe"] = self.resampled_timeframe
            except Exception as e:
                logger.error(f"Error resampling data: {str(e)}")
        
        # Add technical indicators
        if self.add_indicators:
            try:
                logger.info(f"Adding technical indicators: {', '.join(self.indicators)}")
                df = add_technical_indicators(df, self.indicators, self.periods)
                metadata["processing_steps"].append("add_indicators")
                metadata["indicators"] = self.indicators
                metadata["periods"] = self.periods
            except Exception as e:
                logger.error(f"Error adding technical indicators: {str(e)}")
        
        # Add candlestick patterns
        if self.add_candlestick_patterns:
            try:
                logger.info("Extracting candlestick patterns")
                df = extract_candlestick_patterns(df)
                metadata["processing_steps"].append("extract_candlestick_patterns")
            except Exception as e:
                logger.error(f"Error extracting candlestick patterns: {str(e)}")
        
        # Add Fibonacci features
        if self.add_fibonacci_features:
            try:
                logger.info("Extracting Fibonacci features")
                df = extract_fibonacci_features(df)
                metadata["processing_steps"].append("extract_fibonacci_features")
            except Exception as e:
                logger.error(f"Error extracting Fibonacci features: {str(e)}")
        
        # Add trend features
        if self.add_trend_features:
            try:
                logger.info("Extracting trend features")
                df = extract_trend_features(df, self.periods)
                metadata["processing_steps"].append("extract_trend_features")
            except Exception as e:
                logger.error(f"Error extracting trend features: {str(e)}")
        
        # Add wave features
        if self.add_wave_features:
            try:
                logger.info("Extracting wave features")
                df = extract_wave_features(df)
                metadata["processing_steps"].append("extract_wave_features")
            except Exception as e:
                logger.error(f"Error extracting wave features: {str(e)}")
        
        # Normalize data
        if self.normalize:
            try:
                logger.info(f"Normalizing data using {self.normalization_method}")
                df, norm_params = normalize_data(df, method=self.normalization_method)
                self.normalization_params = norm_params
                metadata["processing_steps"].append("normalize")
                metadata["normalization_method"] = self.normalization_method
                metadata["normalization_params"] = norm_params
            except Exception as e:
                logger.error(f"Error normalizing data: {str(e)}")
        
        # Final metadata
        metadata["final_shape"] = df.shape
        metadata["columns"] = df.columns.tolist()
        
        logger.info(f"Processing complete. Original shape: {metadata['original_shape']}, Final shape: {metadata['final_shape']}")
        
        return df, metadata
    
    def process_multiple(
        self,
        symbols: List[str],
        start_date: Union[str, pd.Timestamp],
        end_date: Optional[Union[str, pd.Timestamp]] = None,
        timeframe: str = "1D",
        include_after_hours: bool = False,
    ) -> Dict[str, Tuple[pd.DataFrame, Dict]]:
        """Process multiple symbols through the pipeline.

        Args:
            symbols: List of symbols to process
            start_date: Start date
            end_date: End date (defaults to current date)
            timeframe: Timeframe for the data
            include_after_hours: Whether to include after-hours data

        Returns:
            Dictionary mapping symbols to (processed DataFrame, processing metadata)
        """
        results = {}
        
        for symbol in symbols:
            try:
                df, metadata = self.process(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=timeframe,
                    include_after_hours=include_after_hours,
                )
                results[symbol] = (df, metadata)
            except Exception as e:
                logger.error(f"Error processing {symbol}: {str(e)}")
                results[symbol] = (pd.DataFrame(), {"error": str(e)})
        
        return results