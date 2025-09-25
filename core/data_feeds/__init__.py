"""
FXML4 Data Feeds Module
======================

This module provides real-time market data integration from multiple providers:
- Alpha Vantage: Forex and stock market data
- Polygon.io: High-frequency tick data
- Interactive Brokers: Direct broker data feeds

All feeds implement the BaseDataFeed interface for consistent integration.
"""

from .alpha_vantage_feed import AlphaVantageDataFeed
from .base_feed import BaseDataFeed, DataFeedFactory
from .polygon_feed import PolygonDataFeed

__all__ = [
    "BaseDataFeed",
    "DataFeedFactory",
    "AlphaVantageDataFeed",
    "PolygonDataFeed",
]
