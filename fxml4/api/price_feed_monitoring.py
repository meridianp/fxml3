"""Price Feed Monitoring and Failover Components.

Separate module for price feed reliability monitoring and automatic
failover management, following TDD implementation.
"""

from .websocket_market_data import (
    FeedFailoverManager,
    FeedHealthMetrics,
    FeedSource,
    FeedStatus,
    PriceFeedMonitor,
)

# Re-export for backward compatibility
__all__ = [
    "PriceFeedMonitor",
    "FeedFailoverManager",
    "FeedStatus",
    "FeedHealthMetrics",
    "FeedSource",
]
