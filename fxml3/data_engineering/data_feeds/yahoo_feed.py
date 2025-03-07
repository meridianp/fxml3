"""Yahoo Finance data feed for FXML3."""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import pandas as pd
import yfinance as yf

from fxml3.data_engineering.data_feeds.base_feed import DataFeed


class YahooDataFeed(DataFeed):
    """Data feed using Yahoo Finance API."""
    
    def __init__(self, cache_dir: Optional[str] = None, **kwargs):
        """Initialize the Yahoo Finance data feed.
        
        Args:
            cache_dir: Directory to cache downloaded data
            **kwargs: Additional keyword arguments (not used by this feed)
        """
        super().__init__(cache_dir=cache_dir, **kwargs)
    
    def standardize_symbol(self, symbol: str) -> str:
        """Standardize the symbol for Yahoo Finance.
        
        Args:
            symbol: Symbol in generic format (e.g., "EURUSD")
            
        Returns:
            Symbol in Yahoo Finance format (e.g., "EURUSD=X")
        """
        # For forex pairs in Yahoo Finance, we need to add "=X"
        if symbol.upper() == symbol and len(symbol) == 6 and not symbol.endswith("=X"):
            return f"{symbol}=X"
        return symbol
    
    def standardize_timeframe(self, timeframe: str) -> str:
        """Standardize the timeframe for Yahoo Finance.
        
        Args:
            timeframe: Timeframe in generic format (e.g., "1D", "1H", "5m")
            
        Returns:
            Timeframe in Yahoo Finance format (e.g., "1d", "1h", "5m")
        """
        # Yahoo Finance uses lowercase timeframes
        # 1D -> 1d, 1H -> 1h, etc.
        return timeframe.lower()
    
    def _load_from_cache(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Optional[Union[str, datetime]],
        timeframe: str,
    ) -> Optional[pd.DataFrame]:
        """Load data from cache if available.
        
        Args:
            symbol: Symbol to get data for
            start_date: Start date
            end_date: End date
            timeframe: Timeframe for the data
            
        Returns:
            DataFrame with data if cache hit, None if cache miss
        """
        if self.cache_dir is None:
            return None
        
        # Convert dates to strings for filename
        if isinstance(start_date, datetime):
            start_date_str = start_date.strftime("%Y-%m-%d")
        else:
            start_date_str = start_date
        
        if end_date is None:
            end_date_str = datetime.now().strftime("%Y-%m-%d")
        elif isinstance(end_date, datetime):
            end_date_str = end_date.strftime("%Y-%m-%d")
        else:
            end_date_str = end_date
        
        # Create cache filename
        std_symbol = self.standardize_symbol(symbol)
        std_timeframe = self.standardize_timeframe(timeframe)
        cache_filename = f"{std_symbol}_{std_timeframe}_{start_date_str}_{end_date_str}.csv"
        cache_path = os.path.join(self.cache_dir, cache_filename)
        
        # Check if cache file exists and is recent
        if os.path.exists(cache_path):
            # Get file modification time
            mod_time = os.path.getmtime(cache_path)
            mod_date = datetime.fromtimestamp(mod_time)
            
            # If the file was modified today and end_date is today or None, use cache
            if (
                mod_date.date() == datetime.now().date()
                and (end_date is None or (isinstance(end_date, datetime) and end_date.date() >= datetime.now().date()))
            ):
                try:
                    data = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                    return data
                except Exception:
                    # If there's an error reading the cache, ignore it and fetch fresh data
                    return None
        
        return None
    
    def _save_to_cache(
        self,
        data: pd.DataFrame,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Optional[Union[str, datetime]],
        timeframe: str,
    ) -> None:
        """Save data to cache.
        
        Args:
            data: DataFrame to save
            symbol: Symbol the data is for
            start_date: Start date
            end_date: End date
            timeframe: Timeframe for the data
        """
        if self.cache_dir is None or data.empty:
            return
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Convert dates to strings for filename
        if isinstance(start_date, datetime):
            start_date_str = start_date.strftime("%Y-%m-%d")
        else:
            start_date_str = start_date
        
        if end_date is None:
            end_date_str = datetime.now().strftime("%Y-%m-%d")
        elif isinstance(end_date, datetime):
            end_date_str = end_date.strftime("%Y-%m-%d")
        else:
            end_date_str = end_date
        
        # Create cache filename
        std_symbol = self.standardize_symbol(symbol)
        std_timeframe = self.standardize_timeframe(timeframe)
        cache_filename = f"{std_symbol}_{std_timeframe}_{start_date_str}_{end_date_str}.csv"
        cache_path = os.path.join(self.cache_dir, cache_filename)
        
        # Save to cache
        data.to_csv(cache_path)
    
    def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Optional[Union[str, datetime]] = None,
        timeframe: str = "1D",
        include_after_hours: bool = False,  # Not used for Yahoo Finance
    ) -> pd.DataFrame:
        """Get historical price data for a given symbol and time range.
        
        Args:
            symbol: Symbol to get data for
            start_date: Start date (YYYY-MM-DD string or datetime object)
            end_date: End date (YYYY-MM-DD string or datetime object). If None, current date is used.
            timeframe: Timeframe for the data (e.g., "1d", "1h", "5m")
            include_after_hours: Not used for Yahoo Finance
            
        Returns:
            DataFrame with OHLCV data
            
        Raises:
            ValueError: If the symbol, timeframe, or date range is invalid
            ConnectionError: If there's an issue connecting to Yahoo Finance
        """
        # Standardize inputs
        std_symbol = self.standardize_symbol(symbol)
        std_timeframe = self.standardize_timeframe(timeframe)
        
        # Check cache first
        cached_data = self._load_from_cache(symbol, start_date, end_date, timeframe)
        if cached_data is not None:
            return cached_data
        
        # Convert dates if needed
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        
        if end_date is None:
            end_date = datetime.now()
        elif isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
            
        # Add one day to end_date to make sure we get data for the end date
        end_date = end_date + timedelta(days=1)
        
        try:
            # Use yfinance to get data
            ticker = yf.Ticker(std_symbol)
            data = ticker.history(
                start=start_date,
                end=end_date,
                interval=std_timeframe,
            )
            
            # Rename columns to our standard format
            column_map = {
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
            
            data = data.rename(columns=column_map)
            
            # Make the index timezone naive
            data.index = data.index.tz_localize(None)
            
            # Cache the data
            self._save_to_cache(data, symbol, start_date, end_date, timeframe)
            
            return data
        
        except Exception as e:
            raise ConnectionError(f"Error fetching data from Yahoo Finance: {str(e)}")
    
    def get_latest_data(
        self,
        symbol: str,
        bars: int = 1,
        timeframe: str = "1D",
    ) -> pd.DataFrame:
        """Get the latest N bars of data for a symbol.
        
        Args:
            symbol: Symbol to get data for
            bars: Number of bars to retrieve
            timeframe: Timeframe for the data
            
        Returns:
            DataFrame with OHLCV data
        """
        # Calculate start date based on bars and timeframe
        end_date = datetime.now()
        
        # Convert timeframe to timedelta
        tf_map = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "30m": timedelta(minutes=30),
            "1h": timedelta(hours=1),
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
        }
        
        std_timeframe = self.standardize_timeframe(timeframe)
        if std_timeframe in tf_map:
            delta = tf_map[std_timeframe] * (bars + 10)  # Add buffer to ensure we get enough bars
        else:
            # Default to 1 day * bars * 2 for buffer
            delta = timedelta(days=bars * 2)
        
        start_date = end_date - delta
        
        # Get historical data
        data = self.get_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )
        
        # Return only the latest N bars
        return data.iloc[-bars:] if len(data) >= bars else data
    
    def get_available_symbols(self) -> List[str]:
        """Yahoo Finance doesn't easily support listing all available symbols."""
        raise NotImplementedError("Yahoo Finance doesn't support listing all available symbols")
    
    def is_market_open(self, symbol: str) -> bool:
        """Check if the market for a given symbol is currently open.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if market is open, False otherwise
        """
        try:
            # Get the ticker info
            ticker = yf.Ticker(self.standardize_symbol(symbol))
            info = ticker.info
            
            # Check if 'regular_market_time' is close to current time
            if 'regularMarketTime' in info:
                market_time = datetime.fromtimestamp(info['regularMarketTime'])
                now = datetime.now()
                
                # If the market time is recent (last 10 minutes), assume market is open
                return (now - market_time).total_seconds() < 600
            
            return False
        except Exception:
            return False