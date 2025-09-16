"""CSV data feed implementation for FXML4.

This module provides a data feed that reads market data from CSV files.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from .base_feed import DataFeed, DataFeedFactory

logger = logging.getLogger(__name__)


@DataFeedFactory.register("csv")
class CSVDataFeed(DataFeed):
    """Data feed implementation for reading data from CSV files."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the CSV data feed.

        Args:
            config: Configuration dictionary with the following keys:
                - data_directory: Path to directory containing CSV files
                - file_pattern: Pattern for CSV file names (default: "{symbol}_{timeframe}.csv")
                - datetime_column: Name of datetime column (default: "datetime")
                - datetime_format: Datetime format string (optional)
                - index_col: Column to use as index (default: datetime column)
        """
        super().__init__(config)

        self.data_directory = Path(config.get("data_directory", "./data"))
        self.file_pattern = config.get("file_pattern", "{symbol}_{timeframe}.csv")
        self.datetime_column = config.get("datetime_column", "datetime")
        self.datetime_format = config.get("datetime_format")
        self.index_col = config.get("index_col", self.datetime_column)

        # Ensure data directory exists
        if not self.data_directory.exists():
            logger.warning("Data directory does not exist: %s", self.data_directory)
            self.data_directory.mkdir(parents=True, exist_ok=True)

        logger.info("CSV data feed initialized with directory: %s", self.data_directory)

    def fetch_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Fetch data from CSV file.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe for the data
            start_date: Start date for filtering
            end_date: End date for filtering
            **kwargs: Additional arguments

        Returns:
            DataFrame with market data
        """
        # Generate file path
        filename = self.file_pattern.format(symbol=symbol, timeframe=timeframe)
        filepath = self.data_directory / filename

        if not filepath.exists():
            logger.error("CSV file not found: %s", filepath)
            raise FileNotFoundError(f"CSV file not found: {filepath}")

        logger.info("Reading data from CSV file: %s", filepath)

        # Read CSV file
        try:
            df = pd.read_csv(
                filepath,
                parse_dates=[self.datetime_column] if self.datetime_column else False,
                date_format=self.datetime_format,
                index_col=self.index_col if self.index_col else None,
            )
        except Exception as e:
            logger.error("Error reading CSV file %s: %s", filepath, e)
            raise

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if self.datetime_column in df.columns:
                df.index = pd.to_datetime(df[self.datetime_column])
            else:
                logger.warning("No datetime column found, using numeric index")

        # Standardize column names
        df = self._standardize_columns(df)

        # Filter by date range if specified
        if start_date is not None or end_date is not None:
            df = self._filter_by_date(df, start_date, end_date)

        # Sort by index
        df = df.sort_index()

        logger.info("Loaded %d rows from CSV file", len(df))

        return df

    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols from CSV files.

        Returns:
            List of available symbols
        """
        symbols = set()

        for filepath in self.data_directory.glob("*.csv"):
            # Extract symbol from filename
            filename = filepath.stem
            parts = filename.split("_")
            if parts:
                symbols.add(parts[0])

        return sorted(list(symbols))

    def get_available_timeframes(self) -> List[str]:
        """Get list of available timeframes from CSV files.

        Returns:
            List of available timeframes
        """
        timeframes = set()

        for filepath in self.data_directory.glob("*.csv"):
            # Extract timeframe from filename
            filename = filepath.stem
            parts = filename.split("_")
            if len(parts) >= 2:
                timeframes.add(parts[1])

        return sorted(list(timeframes))

    def save_data(
        self, data: pd.DataFrame, symbol: str, timeframe: str, **kwargs: Any
    ) -> None:
        """Save data to CSV file.

        Args:
            data: DataFrame to save
            symbol: Trading symbol
            timeframe: Timeframe
            **kwargs: Additional arguments
        """
        filename = self.file_pattern.format(symbol=symbol, timeframe=timeframe)
        filepath = self.data_directory / filename

        logger.info("Saving data to CSV file: %s", filepath)

        # Ensure datetime column exists
        if self.datetime_column not in data.columns and isinstance(
            data.index, pd.DatetimeIndex
        ):
            data = data.copy()
            data[self.datetime_column] = data.index

        # Save to CSV
        data.to_csv(filepath, index=True, date_format=self.datetime_format)

        logger.info("Saved %d rows to CSV file", len(data))

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names to lowercase.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with standardized columns
        """
        # Common column mappings
        column_mapping = {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Date": "datetime",
            "Time": "time",
            "Timestamp": "datetime",
        }

        # Apply mappings
        df = df.rename(columns=column_mapping)

        # Convert remaining columns to lowercase
        df.columns = df.columns.str.lower()

        return df

    def _filter_by_date(
        self,
        df: pd.DataFrame,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
    ) -> pd.DataFrame:
        """Filter DataFrame by date range.

        Args:
            df: Input DataFrame
            start_date: Start date
            end_date: End date

        Returns:
            Filtered DataFrame
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            logger.warning("DataFrame index is not DatetimeIndex, skipping date filter")
            return df

        # Convert dates to datetime if needed
        if start_date is not None and not isinstance(start_date, datetime):
            start_date = pd.to_datetime(start_date)
        if end_date is not None and not isinstance(end_date, datetime):
            end_date = pd.to_datetime(end_date)

        # Apply filters
        if start_date is not None:
            df = df[df.index >= start_date]
        if end_date is not None:
            df = df[df.index <= end_date]

        return df

    def list_files(self) -> List[Dict[str, str]]:
        """List all available CSV files.

        Returns:
            List of dictionaries with file information
        """
        files = []

        for filepath in self.data_directory.glob("*.csv"):
            filename = filepath.stem
            parts = filename.split("_")

            file_info = {
                "filename": filepath.name,
                "filepath": str(filepath),
                "symbol": parts[0] if parts else "unknown",
                "timeframe": parts[1] if len(parts) >= 2 else "unknown",
                "size": os.path.getsize(filepath),
                "modified": datetime.fromtimestamp(os.path.getmtime(filepath)),
            }
            files.append(file_info)

        return files
