# Data Engineering API Reference

This document provides detailed API reference for the Data Engineering module.

> Note: This API documentation is under development and will be expanded as the project progresses.

## Data Feeds

### Base Class

#### `DataFeed`

Abstract base class that defines the interface for all data feeds.

```python
class DataFeed(ABC):
    def __init__(self, cache_dir: Optional[str] = None, **kwargs):
        """Initialize the data feed.
        
        Args:
            cache_dir: Directory to cache downloaded data. If None, no caching is used.
            **kwargs: Additional keyword arguments specific to the feed
        """
        
    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Optional[Union[str, datetime]] = None,
        timeframe: str = "1D",
        include_after_hours: bool = False,
    ) -> pd.DataFrame:
        """Get historical price data for a given symbol and time range."""
        
    @abstractmethod
    def get_latest_data(
        self,
        symbol: str,
        bars: int = 1,
        timeframe: str = "1D",
    ) -> pd.DataFrame:
        """Get the latest N bars of data for a symbol."""
        
    def standardize_symbol(self, symbol: str) -> str:
        """Standardize the symbol to the format required by this feed."""
        
    def standardize_timeframe(self, timeframe: str) -> str:
        """Standardize the timeframe to the format required by this feed."""
        
    def get_available_symbols(self) -> List[str]:
        """Get a list of available symbols from this feed."""
        
    def is_market_open(self, symbol: str) -> bool:
        """Check if the market for a given symbol is currently open."""
        
    def get_account_info(self) -> Dict:
        """Get information about the trading account associated with this feed."""
        
    def place_order(self, **kwargs) -> Dict:
        """Place an order through this feed (if it supports trading)."""
        
    def get_orders(self) -> List[Dict]:
        """Get a list of open orders."""
        
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        
    def get_positions(self) -> List[Dict]:
        """Get a list of open positions."""
```

### Implemented Feeds

#### `YahooDataFeed`

Data feed for retrieving data from Yahoo Finance.

```python
class YahooDataFeed(DataFeed):
    def __init__(self, cache_dir: Optional[str] = None, **kwargs):
        """Initialize the Yahoo Finance data feed."""
        
    def get_historical_data(...) -> pd.DataFrame:
        """Get historical price data from Yahoo Finance."""
        
    def get_latest_data(...) -> pd.DataFrame:
        """Get the latest N bars from Yahoo Finance."""
        
    def standardize_symbol(self, symbol: str) -> str:
        """Standardize the symbol for Yahoo Finance (e.g., EURUSD -> EURUSD=X)."""
        
    def standardize_timeframe(self, timeframe: str) -> str:
        """Standardize the timeframe for Yahoo Finance (e.g., 1D -> 1d)."""
        
    def is_market_open(self, symbol: str) -> bool:
        """Check if the market for a given symbol is currently open."""
```

#### `CSVDataFeed`

Data feed for loading data from local CSV files.

```python
class CSVDataFeed(DataFeed):
    def __init__(
        self,
        data_dir: str,
        filename_pattern: str = "{symbol}_{timeframe}.csv",
        date_column: str = "datetime",
        datetime_format: Optional[str] = None,
        **kwargs,
    ):
        """Initialize the CSV data feed."""
        
    def get_historical_data(...) -> pd.DataFrame:
        """Get historical price data from CSV file."""
        
    def get_latest_data(...) -> pd.DataFrame:
        """Get the latest N bars from CSV file."""
        
    def get_available_symbols(self) -> List[str]:
        """Get a list of available symbols from the data directory."""
        
    def get_available_timeframes(self, symbol: str) -> List[str]:
        """Get a list of available timeframes for a symbol."""
```

#### `FXCMDataFeed`

Data feed for connecting to FXCM API (stub implementation).

#### `IBDataFeed`

Data feed for connecting to Interactive Brokers API (stub implementation).

### Factory Function

```python
def create_data_feed(source_type: str, **kwargs) -> DataFeed:
    """Factory function to create a data feed based on source type.
    
    Args:
        source_type: Type of data feed ("yahoo", "csv", "fxcm", "ib")
        **kwargs: Additional keyword arguments for the specific feed
        
    Returns:
        DataFeed: An instance of the appropriate data feed
        
    Raises:
        ValueError: If the source type is not supported
    """
```

## Data Loader

### `ForexDataLoader`

High-level interface for loading forex data from different sources.

```python
class ForexDataLoader:
    def __init__(
        self,
        data_source: str = "yahoo",
        cache_dir: Optional[str] = None,
        **kwargs,
    ):
        """Initialize the data loader."""
        
    def load_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Optional[Union[str, datetime]] = None,
        timeframe: str = "1D",
        include_after_hours: bool = False,
    ) -> pd.DataFrame:
        """Load forex data for a given symbol and time range."""
        
    def load_latest_data(
        self,
        symbol: str,
        bars: int = 1,
        timeframe: str = "1D",
    ) -> pd.DataFrame:
        """Load the latest N bars of forex data for a given symbol."""
        
    def get_available_symbols(self) -> List[str]:
        """Get a list of available symbols from the data source."""
        
    def is_market_open(self, symbol: str) -> bool:
        """Check if the market for a given symbol is currently open."""
        
    def change_data_source(
        self,
        data_source: str,
        **kwargs,
    ) -> None:
        """Change the data source."""
        
    def get_account_info(self) -> Dict:
        """Get information about the trading account."""
        
    def place_order(self, **kwargs) -> Dict:
        """Place an order through the data feed."""
        
    def get_orders(self) -> List[Dict]:
        """Get a list of open orders."""
        
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        
    def get_positions(self) -> List[Dict]:
        """Get a list of open positions."""
```

## Preprocessing

### Data Cleaning

```python
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean OHLCV data by handling missing values and outliers.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        Cleaned DataFrame
    """
```

### Normalization

```python
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
```

### Denormalization

```python
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
```

### Technical Indicators

```python
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
```

### Resampling

```python
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
```

## Feature Engineering

### Candlestick Patterns

```python
def extract_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Extract candlestick patterns from OHLCV data.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        DataFrame with candlestick pattern features
    """
```

### Fibonacci Features

```python
def extract_fibonacci_features(df: pd.DataFrame, window_size: int = 20) -> pd.DataFrame:
    """Extract Fibonacci-related features from price data.
    
    Args:
        df: DataFrame with OHLCV data
        window_size: Window size for local highs and lows detection
        
    Returns:
        DataFrame with Fibonacci features
    """
```

### Trend Features

```python
def extract_trend_features(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    """Extract trend-related features from price data.
    
    Args:
        df: DataFrame with OHLCV data
        periods: List of periods for moving averages and other indicators
        
    Returns:
        DataFrame with trend features
    """
```

### Wave Features

```python
def extract_wave_features(df: pd.DataFrame, min_length: int = 5, max_length: int = 50) -> pd.DataFrame:
    """Extract features that help identify Elliott Wave patterns.
    
    Args:
        df: DataFrame with OHLCV data
        min_length: Minimum length for wave detection
        max_length: Maximum length for wave detection
        
    Returns:
        DataFrame with wave-related features
    """
```

## Data Pipeline

### `DataPipeline`

End-to-end workflow for data processing.

```python
class DataPipeline:
    def __init__(
        self,
        data_source: str = "yahoo",
        cache_dir: Optional[str] = None,
        **kwargs,
    ):
        """Initialize the data pipeline."""
        
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
        """Configure the pipeline."""
        
    def process(
        self,
        symbol: str,
        start_date: Union[str, pd.Timestamp],
        end_date: Optional[Union[str, pd.Timestamp]] = None,
        timeframe: str = "1D",
        include_after_hours: bool = False,
    ) -> Tuple[pd.DataFrame, Dict]:
        """Load and process data through the pipeline."""
        
    def process_multiple(
        self,
        symbols: List[str],
        start_date: Union[str, pd.Timestamp],
        end_date: Optional[Union[str, pd.Timestamp]] = None,
        timeframe: str = "1D",
        include_after_hours: bool = False,
    ) -> Dict[str, Tuple[pd.DataFrame, Dict]]:
        """Process multiple symbols through the pipeline."""
```