"""Historical data handler for backtesting framework.

This module provides data handling functionality for event-driven backtesting,
implementing the interface required by the backtesting test suite.
"""

import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


class HistoricalDataHandler:
    """Handles historical market data for backtesting simulation.

    This class provides market data access methods required by the backtesting
    framework tests, implementing a rolling window approach for event-driven
    simulation.
    """

    def __init__(self, market_data: Dict[str, pd.DataFrame]):
        """Initialize with historical market data.

        Args:
            market_data: Dictionary mapping symbol -> DataFrame with OHLCV data
                        DataFrame should have datetime index and columns:
                        ['open', 'high', 'low', 'close', 'volume', 'spread']
        """
        self.market_data = market_data
        self.symbols = list(market_data.keys())
        self.current_index = 0

        # Validate data structure
        self._validate_data()

        # Get the common date range across all symbols
        self._align_data_indices()

        logger.info(
            f"Initialized HistoricalDataHandler with {len(self.symbols)} symbols"
        )
        logger.info(f"Date range: {self.start_date} to {self.end_date}")
        logger.info(f"Total bars per symbol: {self.total_bars}")

    def _validate_data(self) -> None:
        """Validate the structure of provided market data."""
        required_columns = ["open", "high", "low", "close", "volume"]

        for symbol, df in self.market_data.items():
            if not isinstance(df, pd.DataFrame):
                raise ValueError(f"Data for {symbol} must be a pandas DataFrame")

            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing columns for {symbol}: {missing_cols}")

            if not isinstance(df.index, pd.DatetimeIndex):
                raise ValueError(f"DataFrame index for {symbol} must be DatetimeIndex")

    def _align_data_indices(self) -> None:
        """Align data indices across all symbols to ensure consistent timeline."""
        if not self.market_data:
            raise ValueError("No market data provided")

        # Find common date range
        start_dates = []
        end_dates = []

        for df in self.market_data.values():
            start_dates.append(df.index.min())
            end_dates.append(df.index.max())

        self.start_date = max(start_dates)  # Latest start date
        self.end_date = min(end_dates)  # Earliest end date

        # Trim all dataframes to common range
        for symbol in self.symbols:
            mask = (self.market_data[symbol].index >= self.start_date) & (
                self.market_data[symbol].index <= self.end_date
            )
            self.market_data[symbol] = self.market_data[symbol].loc[mask]

        # Get total bars (use first symbol as reference)
        first_symbol = self.symbols[0]
        self.total_bars = len(self.market_data[first_symbol])
        self.datetime_index = self.market_data[first_symbol].index

    def get_latest_bars(
        self, symbols: Optional[List[str]] = None
    ) -> Dict[str, Optional[pd.Series]]:
        """Get the latest bar data for specified symbols.

        Args:
            symbols: List of symbols to get data for. If None, gets all symbols.

        Returns:
            Dict mapping symbol -> Series with OHLCV data, or None if no data available
        """
        if symbols is None:
            symbols = self.symbols

        result = {}

        # Check if we have data available at current index
        if self.current_index >= self.total_bars:
            # No more data available
            for symbol in symbols:
                result[symbol] = None
            return result

        # Get current timestamp
        current_timestamp = self.datetime_index[self.current_index]

        # Get bar data for each symbol
        for symbol in symbols:
            if symbol not in self.market_data:
                result[symbol] = None
                continue

            df = self.market_data[symbol]

            # Find the bar for current timestamp
            try:
                bar_data = df.loc[current_timestamp].copy()
                bar_data.name = current_timestamp  # Ensure timestamp is preserved
                result[symbol] = bar_data
            except KeyError:
                # No data available for this timestamp
                result[symbol] = None

        return result

    def get_latest_bar(self, symbol: str) -> Optional[pd.Series]:
        """Get the latest bar for a single symbol.

        Args:
            symbol: Symbol to get data for

        Returns:
            Series with OHLCV data or None if no data available
        """
        bars = self.get_latest_bars([symbol])
        return bars.get(symbol)

    def update_bars(self) -> None:
        """Move to the next time step in the data."""
        self.current_index += 1

        if self.current_index < self.total_bars:
            current_timestamp = self.datetime_index[self.current_index]
            logger.debug(f"Updated to bar {self.current_index}: {current_timestamp}")

    def get_historical_bars(
        self, symbol: str, lookback_periods: int, end_index: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """Get historical bars for a symbol.

        Args:
            symbol: Symbol to get data for
            lookback_periods: Number of periods to look back
            end_index: End index (if None, uses current_index)

        Returns:
            DataFrame with historical data or None if insufficient data
        """
        if symbol not in self.market_data:
            return None

        if end_index is None:
            end_index = self.current_index

        start_index = max(0, end_index - lookback_periods + 1)

        if start_index >= end_index or end_index >= self.total_bars:
            return None

        df = self.market_data[symbol]
        return df.iloc[start_index : end_index + 1].copy()

    def get_bar_count(self, symbol: str) -> int:
        """Get total number of bars available for a symbol.

        Args:
            symbol: Symbol to get count for

        Returns:
            Number of bars available
        """
        if symbol not in self.market_data:
            return 0
        return len(self.market_data[symbol])

    def get_current_timestamp(self) -> Optional[pd.Timestamp]:
        """Get the current timestamp in the simulation.

        Returns:
            Current timestamp or None if no data available
        """
        if self.current_index >= self.total_bars:
            return None
        return self.datetime_index[self.current_index]

    def reset(self) -> None:
        """Reset the data handler to the beginning."""
        self.current_index = 0
        logger.info("Reset data handler to beginning")

    def has_more_data(self) -> bool:
        """Check if more data is available.

        Returns:
            True if more data is available, False otherwise
        """
        return self.current_index < self.total_bars

    def get_symbols(self) -> List[str]:
        """Get list of available symbols.

        Returns:
            List of symbol strings
        """
        return self.symbols.copy()

    def get_date_range(self) -> tuple:
        """Get the date range of available data.

        Returns:
            Tuple of (start_date, end_date)
        """
        return (self.start_date, self.end_date)

    def get_data_summary(self) -> Dict[str, Any]:
        """Get summary of available data.

        Returns:
            Dictionary with data summary information
        """
        return {
            "symbols": self.symbols,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_bars": self.total_bars,
            "current_index": self.current_index,
            "has_more_data": self.has_more_data(),
        }
