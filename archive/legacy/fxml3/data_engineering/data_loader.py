"""Data loader module for fetching and processing forex data."""

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

from fxml3.data_engineering.data_feeds import create_data_feed


class ForexDataLoader:
    """Handles loading and preprocessing of forex data from various sources.
    
    This class provides a unified interface for loading forex data from different
    sources (Yahoo Finance, FXCM, Interactive Brokers, CSV files).
    """

    def __init__(
        self,
        data_source: str = "yahoo",
        cache_dir: Optional[str] = None,
        **kwargs,
    ):
        """Initialize the data loader.

        Args:
            data_source: Source of the data. Options are "yahoo", "fxcm", "ib", or "csv".
            cache_dir: Directory to cache downloaded data. If None, no caching is used.
            **kwargs: Additional arguments passed to the specific data feed
                For CSV: data_dir, filename_pattern, date_column, datetime_format
                For FXCM: api_key, access_token, demo
                For IB: account_id, host, port, client_id
        """
        self.data_source = data_source
        self.cache_dir = cache_dir
        
        # Create data directory if it doesn't exist
        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize the appropriate data feed
        self.feed = create_data_feed(data_source, cache_dir=cache_dir, **kwargs)
    
    def load_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Optional[Union[str, datetime]] = None,
        timeframe: str = "1D",
        include_after_hours: bool = False,
    ) -> pd.DataFrame:
        """Load forex data for a given symbol and time range.

        Args:
            symbol: Forex pair symbol (e.g., "EURUSD")
            start_date: Start date in YYYY-MM-DD format or datetime object
            end_date: End date in YYYY-MM-DD format or datetime object. If None, current date is used.
            timeframe: Data timeframe (e.g., "1H", "4H", "1D")
            include_after_hours: Whether to include after-hours data (only relevant for some feeds)

        Returns:
            DataFrame with OHLCV data (datetime index, open, high, low, close, volume columns)
        
        Raises:
            ValueError: If the symbol, timeframe, or date range is invalid
            ConnectionError: If there's an issue connecting to the data source
            FileNotFoundError: If using CSV feed and the file is not found
        """
        return self.feed.get_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            include_after_hours=include_after_hours,
        )
    
    def load_latest_data(
        self,
        symbol: str,
        bars: int = 1,
        timeframe: str = "1D",
    ) -> pd.DataFrame:
        """Load the latest N bars of forex data for a given symbol.

        Args:
            symbol: Forex pair symbol (e.g., "EURUSD")
            bars: Number of bars to retrieve
            timeframe: Data timeframe (e.g., "1H", "4H", "1D")

        Returns:
            DataFrame with OHLCV data
        """
        return self.feed.get_latest_data(
            symbol=symbol,
            bars=bars,
            timeframe=timeframe,
        )
    
    def get_available_symbols(self) -> List[str]:
        """Get a list of available symbols from the data source.

        Returns:
            List of available symbols
        
        Raises:
            NotImplementedError: If the data source doesn't support listing symbols
        """
        return self.feed.get_available_symbols()
    
    def is_market_open(self, symbol: str) -> bool:
        """Check if the market for a given symbol is currently open.

        Args:
            symbol: Symbol to check
            
        Returns:
            True if market is open, False otherwise
        
        Raises:
            NotImplementedError: If the data source doesn't support checking market status
        """
        return self.feed.is_market_open(symbol)
    
    def change_data_source(
        self,
        data_source: str,
        **kwargs,
    ) -> None:
        """Change the data source.

        Args:
            data_source: New data source ("yahoo", "fxcm", "ib", or "csv")
            **kwargs: Additional arguments for the new data source
        """
        self.data_source = data_source
        self.feed = create_data_feed(data_source, cache_dir=self.cache_dir, **kwargs)
    
    def get_account_info(self) -> Dict:
        """Get information about the trading account associated with the data feed.

        Returns:
            Dictionary with account information
        
        Raises:
            NotImplementedError: If the data feed doesn't support account information
        """
        return self.feed.get_account_info()
    
    def place_order(self, **kwargs) -> Dict:
        """Place an order through the data feed (if it supports trading).

        Args:
            **kwargs: Order parameters (symbol, order_type, side, amount, price, etc.)
            
        Returns:
            Dictionary with order information
        
        Raises:
            NotImplementedError: If the data feed doesn't support trading
        """
        return self.feed.place_order(**kwargs)
    
    def get_orders(self) -> List[Dict]:
        """Get a list of open orders.

        Returns:
            List of dictionaries with order information
        
        Raises:
            NotImplementedError: If the data feed doesn't support trading
        """
        return self.feed.get_orders()
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: ID of the order to cancel
            
        Returns:
            True if the order was canceled successfully, False otherwise
        
        Raises:
            NotImplementedError: If the data feed doesn't support trading
        """
        return self.feed.cancel_order(order_id)
    
    def get_positions(self) -> List[Dict]:
        """Get a list of open positions.

        Returns:
            List of dictionaries with position information
        
        Raises:
            NotImplementedError: If the data feed doesn't support trading
        """
        return self.feed.get_positions()