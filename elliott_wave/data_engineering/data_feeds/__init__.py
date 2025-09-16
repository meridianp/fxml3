"""Data feed package for FXML3."""

from fxml3.data_engineering.data_feeds.base_feed import DataFeed
from fxml3.data_engineering.data_feeds.csv_feed import CSVDataFeed
from fxml3.data_engineering.data_feeds.yahoo_feed import YahooDataFeed

# Try to import optional feeds
try:
    from fxml3.data_engineering.data_feeds.fxcm_feed import FXCMDataFeed
except ImportError:
    pass

try:
    from fxml3.data_engineering.data_feeds.ib_feed import IBDataFeed
except ImportError:
    pass


# Factory function to create data feeds
def create_data_feed(source_type, **kwargs):
    """Factory function to create a data feed based on source type.

    Args:
        source_type: Type of data feed ("yahoo", "csv", "fxcm", "ib")
        **kwargs: Additional keyword arguments for the specific feed

    Returns:
        DataFeed: An instance of the appropriate data feed

    Raises:
        ValueError: If the source type is not supported
    """
    source_map = {
        "yahoo": YahooDataFeed,
        "csv": CSVDataFeed,
    }

    # Add optional feeds if available
    try:
        source_map["fxcm"] = FXCMDataFeed
    except NameError:
        pass

    try:
        source_map["ib"] = IBDataFeed
    except NameError:
        pass

    source_type = source_type.lower()
    if source_type not in source_map:
        raise ValueError(
            f"Unsupported data source: {source_type}. "
            f"Supported sources: {', '.join(source_map.keys())}"
        )

    return source_map[source_type](**kwargs)
