"""OHLC Bar Aggregation Components.

Separate module for OHLC (Open, High, Low, Close) bar aggregation
from tick data, following TDD implementation.
"""

from .websocket_market_data import OHLCBar, OHLCBarAggregator, TickData, TimeFrame

# Re-export for backward compatibility
__all__ = ["OHLCBarAggregator", "OHLCBar", "TickData", "TimeFrame"]
