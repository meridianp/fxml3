"""Base class for all data feeds in FXML3."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd


class DataFeed(ABC):
    """Abstract base class for all data feeds.
    
    All data feeds should inherit from this class and implement the required methods.
    This ensures a consistent interface for all data sources.
    """
    
    def __init__(self, cache_dir: Optional[str] = None, **kwargs):
        """Initialize the data feed.
        
        Args:
            cache_dir: Directory to cache downloaded data. If None, no caching is used.
            **kwargs: Additional keyword arguments specific to the feed
        """
        self.cache_dir = cache_dir
    
    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Optional[Union[str, datetime]] = None,
        timeframe: str = "1D",
        include_after_hours: bool = False,
    ) -> pd.DataFrame:
        """Get historical price data for a given symbol and time range.
        
        Args:
            symbol: Symbol to get data for (format depends on the feed)
            start_date: Start date (YYYY-MM-DD string or datetime object)
            end_date: End date (YYYY-MM-DD string or datetime object). If None, current date is used.
            timeframe: Timeframe for the data (e.g., "1m", "5m", "1h", "1d")
            include_after_hours: Whether to include after-hours data
            
        Returns:
            DataFrame with OHLCV data. Should have these columns:
                - datetime: Datetime index
                - open: Open price
                - high: High price
                - low: Low price
                - close: Close price
                - volume: Volume (optional, can be NaN if not available)
        
        Raises:
            ValueError: If the symbol, timeframe, or date range is invalid
            ConnectionError: If there's an issue connecting to the data source
        """
        pass
    
    @abstractmethod
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
            DataFrame with OHLCV data (same format as get_historical_data)
        """
        pass
    
    def standardize_symbol(self, symbol: str) -> str:
        """Standardize the symbol to the format required by this feed.
        
        Args:
            symbol: Symbol in a generic format (e.g., "EURUSD")
            
        Returns:
            Symbol in the format required by this feed
        """
        # Default implementation just returns the symbol unchanged
        # Override in derived classes if needed
        return symbol
    
    def standardize_timeframe(self, timeframe: str) -> str:
        """Standardize the timeframe to the format required by this feed.
        
        Args:
            timeframe: Timeframe in a generic format (e.g., "1D", "1H", "5m")
            
        Returns:
            Timeframe in the format required by this feed
        """
        # Default implementation just returns the timeframe unchanged
        # Override in derived classes if needed
        return timeframe
    
    def get_available_symbols(self) -> List[str]:
        """Get a list of available symbols from this feed.
        
        Returns:
            List of available symbols
        
        Raises:
            NotImplementedError: If the feed doesn't support listing symbols
        """
        raise NotImplementedError("This feed doesn't support listing available symbols")
    
    def is_market_open(self, symbol: str) -> bool:
        """Check if the market for a given symbol is currently open.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if market is open, False otherwise
        
        Raises:
            NotImplementedError: If the feed doesn't support checking market status
        """
        raise NotImplementedError("This feed doesn't support checking market status")
    
    def get_account_info(self) -> Dict:
        """Get information about the trading account associated with this feed.
        
        Returns:
            Dictionary with account information
        
        Raises:
            NotImplementedError: If the feed doesn't support account information
        """
        raise NotImplementedError("This feed doesn't support account information")
    
    def place_order(self, **kwargs) -> Dict:
        """Place an order through this feed (if it supports trading).
        
        Args:
            **kwargs: Order parameters (symbol, order_type, quantity, etc.)
            
        Returns:
            Dictionary with order information
        
        Raises:
            NotImplementedError: If the feed doesn't support trading
        """
        raise NotImplementedError("This feed doesn't support trading")
    
    def get_orders(self) -> List[Dict]:
        """Get a list of open orders.
        
        Returns:
            List of dictionaries with order information
        
        Raises:
            NotImplementedError: If the feed doesn't support trading
        """
        raise NotImplementedError("This feed doesn't support trading")
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.
        
        Args:
            order_id: ID of the order to cancel
            
        Returns:
            True if the order was canceled successfully, False otherwise
        
        Raises:
            NotImplementedError: If the feed doesn't support trading
        """
        raise NotImplementedError("This feed doesn't support trading")
    
    def get_positions(self) -> List[Dict]:
        """Get a list of open positions.
        
        Returns:
            List of dictionaries with position information
        
        Raises:
            NotImplementedError: If the feed doesn't support trading
        """
        raise NotImplementedError("This feed doesn't support trading")