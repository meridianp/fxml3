"""
Data handling for backtesting.
"""

import logging
from datetime import datetime
from queue import Queue
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from fxml4.backtesting.events import EventType, MarketEvent

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DataHandler:
    """Handle market data for backtesting."""

    def __init__(
        self,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        events_queue: Queue,
        symbols: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        self.events_queue = events_queue
        self.start_date = start_date
        self.end_date = end_date

        # Process input data
        if isinstance(data, pd.DataFrame):
            # Single symbol data
            symbol = symbols[0] if symbols else "default"
            self.symbol_data = {symbol: self._prepare_data(data)}
            self.symbols = [symbol]
        else:
            # Multi-symbol data
            self.symbol_data = {
                symbol: self._prepare_data(df) for symbol, df in data.items()
            }
            self.symbols = list(self.symbol_data.keys())

        # Initialize iterators
        self.current_index = {symbol: 0 for symbol in self.symbols}
        self.latest_bars = {symbol: None for symbol in self.symbols}
        self.continue_backtest = True

        logger.info(
            "DataHandler initialized with %d symbols, %d total bars",
            len(self.symbols),
            sum(len(df) for df in self.symbol_data.values()),
        )

    def _prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare data for backtesting."""
        df = data.copy()

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp")
            else:
                df.index = pd.to_datetime(df.index)

        # Sort by date
        df = df.sort_index()

        # Filter by date range
        if self.start_date:
            df = df[df.index >= self.start_date]
        if self.end_date:
            df = df[df.index <= self.end_date]

        # Ensure required columns
        required_columns = ["open", "high", "low", "close", "volume"]
        missing_columns = set(required_columns) - set(df.columns)

        if missing_columns:
            logger.warning("Missing columns: %s", missing_columns)

            # Fill missing columns with reasonable defaults
            for col in missing_columns:
                if col == "volume":
                    df[col] = 0
                elif col in ["open", "high", "low"]:
                    df[col] = df.get("close", 0)
                else:
                    df[col] = 0

        return df

    def update_bars(self) -> None:
        """Push the next bars to the events queue."""
        bars_updated = False

        for symbol in self.symbols:
            if self._has_more_bars(symbol):
                # Get next bar
                bar = self._get_next_bar(symbol)
                if bar is not None:
                    # Create market event
                    event = MarketEvent(
                        type=EventType.MARKET,
                        timestamp=bar.name,
                        symbol=symbol,
                        data=bar,
                    )
                    self.events_queue.put(event)
                    bars_updated = True

        if not bars_updated:
            self.continue_backtest = False
            logger.info("No more data available")

    def get_latest_bar(self, symbol: str) -> Optional[pd.Series]:
        """Get the latest bar for a symbol."""
        return self.latest_bars.get(symbol)

    def get_latest_bars(self, symbol: str, n: int = 1) -> Optional[pd.DataFrame]:
        """Get the latest n bars for a symbol."""
        if symbol not in self.symbol_data:
            return None

        current_idx = self.current_index[symbol]
        if current_idx < n:
            return None

        return self.symbol_data[symbol].iloc[current_idx - n : current_idx]

    def get_all_bars(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get all available bars up to current point."""
        if symbol not in self.symbol_data:
            return None

        current_idx = self.current_index[symbol]
        return self.symbol_data[symbol].iloc[:current_idx]

    def _has_more_bars(self, symbol: str) -> bool:
        """Check if more bars are available for symbol."""
        current_idx = self.current_index[symbol]
        return current_idx < len(self.symbol_data[symbol])

    def _get_next_bar(self, symbol: str) -> Optional[pd.Series]:
        """Get next bar for symbol."""
        if not self._has_more_bars(symbol):
            return None

        current_idx = self.current_index[symbol]
        bar = self.symbol_data[symbol].iloc[current_idx]

        # Update tracking
        self.current_index[symbol] += 1
        self.latest_bars[symbol] = bar

        return bar

    def get_symbol_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get all data for a symbol."""
        return self.symbol_data.get(symbol)

    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols."""
        return self.symbols.copy()
