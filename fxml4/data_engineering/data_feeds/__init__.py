"""Data feeds module."""

from .alpha_vantage_feed import AlphaVantageDataFeed as AlphaVantageFeed
from .base_feed import DataFeed as BaseFeed
from .csv_feed import CSVDataFeed as CSVFeed
from .fred_feed import FREDDataFeed as FredFeed
from .ib_data_feed import IBDataFeed
from .ib_feed import IBDataFeed as IBFeed


class DataFeedFactory:
    """Factory for creating data feeds."""

    @staticmethod
    def create_feed(feed_type: str, **kwargs):
        """Create a data feed of the specified type."""
        if feed_type.lower() == "alpha_vantage":
            return AlphaVantageFeed(**kwargs)
        elif feed_type.lower() == "fred":
            return FredFeed(**kwargs)
        elif feed_type.lower() == "ib":
            return IBFeed(**kwargs)
        elif feed_type.lower() == "csv":
            return CSVFeed(**kwargs)
        elif feed_type.lower() == "ib_data":
            return IBDataFeed(**kwargs)
        else:
            raise ValueError(f"Unknown feed type: {feed_type}")


__all__ = [
    "BaseFeed",
    "AlphaVantageFeed",
    "FredFeed",
    "IBFeed",
    "CSVFeed",
    "IBDataFeed",
    "DataFeedFactory",
]
