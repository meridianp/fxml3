"""
FXML4 Streaming Data Processing Module

High-throughput real-time data processing for trading systems:
- Real-time tick data processing at 1M+ ticks/second
- Time-window aggregation with sliding windows
- Change data capture for cache invalidation
- Stream processing with backpressure handling
"""

from .aggregation_engine import AggregationEngine, AggregationWindow, TimeWindow
from .cdc_handler import CDCHandler, ChangeEvent, ChangeType
from .tick_processor import ProcessingStats, TickData, TickProcessor

__all__ = [
    "TickProcessor",
    "TickData",
    "ProcessingStats",
    "AggregationEngine",
    "AggregationWindow",
    "TimeWindow",
    "CDCHandler",
    "ChangeEvent",
    "ChangeType",
]
