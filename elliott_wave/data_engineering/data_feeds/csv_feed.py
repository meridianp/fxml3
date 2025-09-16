"""CSV data feed for FXML3.

This data feed loads data from local CSV files. The files should have OHLCV data
with datetime as the index.
"""

import glob
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

from fxml3.data_engineering.data_feeds.base_feed import DataFeed


class CSVDataFeed(DataFeed):
    """Data feed using local CSV files."""

    def __init__(
        self,
        data_dir: str,
        filename_pattern: str = "{symbol}_{timeframe}.csv",
        date_column: str = "datetime",
        datetime_format: Optional[str] = None,
        **kwargs,
    ):
        """Initialize the CSV data feed.

        Args:
            data_dir: Directory containing CSV files
            filename_pattern: Pattern for CSV filenames. Should contain {symbol} and {timeframe}
                placeholders, e.g., "{symbol}_{timeframe}.csv"
            date_column: Name of the date/time column in the CSV
            datetime_format: Format string for parsing dates, e.g., "%Y-%m-%d %H:%M:%S".
                If None, pandas will try to infer the format.
            **kwargs: Additional keyword arguments (passed to parent)
        """
        super().__init__(**kwargs)

        self.data_dir = data_dir
        self.filename_pattern = filename_pattern
        self.date_column = date_column
        self.datetime_format = datetime_format

        # Create a cache of available files
        self._available_files = {}
        self._load_available_files()

    def _load_available_files(self) -> None:
        """Scan the data directory and cache available files."""
        if not os.path.exists(self.data_dir):
            return

        # Get all CSV files in the directory
        csv_files = glob.glob(os.path.join(self.data_dir, "*.csv"))

        for file_path in csv_files:
            filename = os.path.basename(file_path)

            # Try to extract symbol and timeframe from filename
            # The filename_pattern could be like "{symbol}_{timeframe}.csv"
            # We need to reverse-engineer symbol and timeframe from actual filenames

            # First, replace curly braces with actual pattern characters
            pattern = self.filename_pattern.replace("{", "(?P<").replace("}", ">.*?)")

            import re

            match = re.match(pattern, filename)
            if match:
                symbol = match.group("symbol")
                timeframe = match.group("timeframe")

                # Cache the file path
                if symbol not in self._available_files:
                    self._available_files[symbol] = {}

                self._available_files[symbol][timeframe] = file_path

    def _get_file_path(self, symbol: str, timeframe: str) -> Optional[str]:
        """Get the file path for a given symbol and timeframe.

        Args:
            symbol: Symbol to get data for
            timeframe: Timeframe for the data

        Returns:
            Path to the CSV file, or None if not found
        """
        # Check cache first
        if (
            symbol in self._available_files
            and timeframe in self._available_files[symbol]
        ):
            return self._available_files[symbol][timeframe]

        # Try to construct the filename
        filename = self.filename_pattern.format(symbol=symbol, timeframe=timeframe)
        file_path = os.path.join(self.data_dir, filename)

        # Check if the file exists
        if os.path.exists(file_path):
            # Cache it for future use
            if symbol not in self._available_files:
                self._available_files[symbol] = {}

            self._available_files[symbol][timeframe] = file_path
            return file_path

        return None

    def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Optional[Union[str, datetime]] = None,
        timeframe: str = "1D",
        include_after_hours: bool = False,
    ) -> pd.DataFrame:
        """Get historical price data from CSV file.

        Args:
            symbol: Symbol to get data for
            start_date: Start date (YYYY-MM-DD string or datetime object)
            end_date: End date (YYYY-MM-DD string or datetime object). If None, current date is used.
            timeframe: Timeframe for the data
            include_after_hours: Not used for CSV feed

        Returns:
            DataFrame with OHLCV data

        Raises:
            ValueError: If the symbol, timeframe, or date range is invalid
            FileNotFoundError: If the CSV file is not found
        """
        # Get the file path
        file_path = self._get_file_path(symbol, timeframe)
        if file_path is None:
            raise FileNotFoundError(
                f"CSV file for {symbol} with timeframe {timeframe} not found"
            )

        try:
            # Read the CSV file
            if self.date_column == "index":
                # Date is the index (unnamed column 0)
                df = pd.read_csv(
                    file_path,
                    index_col=0,
                    parse_dates=True,
                    date_format=self.datetime_format,
                )
            else:
                # Date is a named column
                df = pd.read_csv(file_path)

                # Parse the date column
                if self.datetime_format:
                    df[self.date_column] = pd.to_datetime(
                        df[self.date_column],
                        format=self.datetime_format,
                    )
                else:
                    df[self.date_column] = pd.to_datetime(df[self.date_column])

                # Set the date column as index
                df.set_index(self.date_column, inplace=True)

            # Ensure index is sorted
            df = df.sort_index()

            # Ensure column names are lowercase
            df.columns = [col.lower() for col in df.columns]

            # Ensure required columns exist
            required_columns = ["open", "high", "low", "close"]
            existing_columns = df.columns.tolist()

            for col in required_columns:
                if col not in existing_columns:
                    raise ValueError(f"Required column '{col}' not found in CSV file")

            # Filter by date range
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, "%Y-%m-%d")

            if end_date is None:
                end_date = datetime.now()
            elif isinstance(end_date, str):
                end_date = datetime.strptime(end_date, "%Y-%m-%d")

            # Add one day to end_date to include the end date in the range
            end_date = end_date + timedelta(days=1)

            mask = (df.index >= start_date) & (df.index < end_date)
            filtered_df = df.loc[mask]

            return filtered_df

        except Exception as e:
            raise ValueError(f"Error reading CSV file: {str(e)}")

    def get_latest_data(
        self,
        symbol: str,
        bars: int = 1,
        timeframe: str = "1D",
    ) -> pd.DataFrame:
        """Get the latest N bars from the CSV file.

        Args:
            symbol: Symbol to get data for
            bars: Number of bars to retrieve
            timeframe: Timeframe for the data

        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Get the full dataset
            file_path = self._get_file_path(symbol, timeframe)
            if file_path is None:
                raise FileNotFoundError(
                    f"CSV file for {symbol} with timeframe {timeframe} not found"
                )

            if self.date_column == "index":
                df = pd.read_csv(
                    file_path,
                    index_col=0,
                    parse_dates=True,
                    date_format=self.datetime_format,
                )
            else:
                df = pd.read_csv(file_path)

                if self.datetime_format:
                    df[self.date_column] = pd.to_datetime(
                        df[self.date_column],
                        format=self.datetime_format,
                    )
                else:
                    df[self.date_column] = pd.to_datetime(df[self.date_column])

                df.set_index(self.date_column, inplace=True)

            # Ensure index is sorted
            df = df.sort_index()

            # Ensure column names are lowercase
            df.columns = [col.lower() for col in df.columns]

            # Return only the last N bars
            return df.iloc[-bars:]

        except Exception as e:
            raise ValueError(f"Error reading CSV file: {str(e)}")

    def get_available_symbols(self) -> List[str]:
        """Get a list of available symbols from the data directory.

        Returns:
            List of symbols that have CSV files
        """
        return list(self._available_files.keys())

    def get_available_timeframes(self, symbol: str) -> List[str]:
        """Get a list of available timeframes for a symbol.

        Args:
            symbol: Symbol to check

        Returns:
            List of timeframes available for the symbol
        """
        if symbol in self._available_files:
            return list(self._available_files[symbol].keys())
        return []
