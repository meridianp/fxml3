"""Base data feed implementation.

This module provides base classes for data feed implementations.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

import pandas as pd

logger = logging.getLogger(__name__)


class DataFeed(ABC):
    """Abstract base class for data feeds.
    
    A data feed is responsible for retrieving market data from a specific source.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the data feed.
        
        Args:
            config: Configuration dictionary for the data feed.
        """
        self.config = config
        self.name = self.__class__.__name__
        logger.info("Initializing data feed: %s", self.name)
    
    @abstractmethod
    def fetch_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch data from the data source.
        
        Args:
            symbol: Trading symbol to fetch data for.
            timeframe: Timeframe for the data (e.g., "1m", "1h", "1d").
            start_date: Start date for the data.
            end_date: End date for the data.
            **kwargs: Additional arguments for the data feed.
            
        Returns:
            DataFrame containing the fetched data.
        """
        pass
    
    @abstractmethod
    def get_available_symbols(self) -> List[str]:
        """Get the list of available symbols for this data feed.
        
        Returns:
            List of available symbols.
        """
        pass
    
    @abstractmethod
    def get_available_timeframes(self) -> List[str]:
        """Get the list of available timeframes for this data feed.
        
        Returns:
            List of available timeframes.
        """
        pass


class DataFeedFactory:
    """Factory for creating data feed instances."""
    
    _feeds: Dict[str, Type[DataFeed]] = {}
    
    @classmethod
    def register(cls, name: str) -> callable:
        """Register a data feed class with the factory.
        
        Args:
            name: Name to register the data feed under.
            
        Returns:
            Decorator function that registers the decorated class.
        """
        def decorator(feed_cls: Type[DataFeed]) -> Type[DataFeed]:
            cls._feeds[name] = feed_cls
            return feed_cls
        return decorator
    
    @classmethod
    def create(cls, name: str, config: Dict[str, Any]) -> DataFeed:
        """Create a data feed instance.
        
        Args:
            name: Name of the data feed to create.
            config: Configuration dictionary for the data feed.
            
        Returns:
            Instance of the requested data feed.
            
        Raises:
            ValueError: If the requested data feed is not registered.
        """
        if name not in cls._feeds:
            raise ValueError(f"Unknown data feed: {name}")
        
        return cls._feeds[name](config)