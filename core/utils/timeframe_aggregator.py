"""Utility for aggregating data across multiple timeframes."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TimeframeAggregator:
    """Aggregate price data across multiple timeframes."""

    # Mapping of timeframe strings to pandas resample rules
    TIMEFRAME_MAP = {
        "1T": "1T",  # 1 minute
        "5T": "5T",  # 5 minutes
        "15T": "15T",  # 15 minutes
        "30T": "30T",  # 30 minutes
        "1H": "1H",  # 1 hour
        "4H": "4H",  # 4 hours
        "D": "D",  # Daily
        "W": "W",  # Weekly
        "M": "M",  # Monthly
    }

    def __init__(self):
        """Initialize the timeframe aggregator."""
        pass

    def aggregate_to_timeframes(
        self, base_data: pd.DataFrame, base_timeframe: str, target_timeframes: List[str]
    ) -> Dict[str, pd.DataFrame]:
        """Aggregate base data to multiple timeframes.

        Args:
            base_data: Base OHLCV DataFrame with datetime index
            base_timeframe: Base timeframe (e.g., '15T', '1H')
            target_timeframes: List of target timeframes to aggregate to

        Returns:
            Dictionary of DataFrames by timeframe
        """
        result = {}

        # Always include base timeframe
        result[base_timeframe] = base_data.copy()

        # Convert base timeframe to minutes for comparison
        base_minutes = self._timeframe_to_minutes(base_timeframe)

        for target_tf in target_timeframes:
            if target_tf == base_timeframe:
                continue

            target_minutes = self._timeframe_to_minutes(target_tf)

            if target_minutes > base_minutes:
                # Aggregate up (e.g., 15m to 1H)
                result[target_tf] = self._aggregate_up(base_data, target_tf)
            else:
                logger.warning(
                    f"Cannot aggregate from {base_timeframe} to {target_tf} (higher resolution)"
                )

        return result

    def _aggregate_up(self, data: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
        """Aggregate data to a higher timeframe.

        Args:
            data: Source OHLCV data
            target_timeframe: Target timeframe

        Returns:
            Aggregated DataFrame
        """
        rule = self.TIMEFRAME_MAP.get(target_timeframe)
        if not rule:
            raise ValueError(f"Unknown timeframe: {target_timeframe}")

        # Resample using OHLC aggregation
        agg_rules = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }

        # Perform aggregation
        aggregated = data.resample(rule).agg(agg_rules)

        # Remove any rows with NaN values
        aggregated = aggregated.dropna()

        return aggregated

    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes.

        Args:
            timeframe: Timeframe string

        Returns:
            Number of minutes
        """
        conversions = {
            "1T": 1,
            "5T": 5,
            "15T": 15,
            "30T": 30,
            "1H": 60,
            "4H": 240,
            "D": 1440,
            "W": 10080,
            "M": 43200,  # Approximate
        }

        return conversions.get(timeframe, 0)

    def calculate_mtf_indicators(
        self, price_data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, Dict[str, pd.Series]]:
        """Calculate technical indicators for each timeframe.

        Args:
            price_data_dict: Dictionary of price data by timeframe

        Returns:
            Dictionary of indicators by timeframe
        """
        indicators_dict = {}

        for timeframe, data in price_data_dict.items():
            indicators = {}

            # Moving averages
            indicators["sma_20"] = data["close"].rolling(20).mean()
            indicators["sma_50"] = data["close"].rolling(50).mean()
            indicators["ema_9"] = data["close"].ewm(span=9).mean()

            # RSI
            delta = data["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            indicators["rsi"] = 100 - (100 / (1 + rs))

            # Bollinger Bands
            bb_sma = data["close"].rolling(20).mean()
            bb_std = data["close"].rolling(20).std()
            indicators["bb_upper"] = bb_sma + (bb_std * 2)
            indicators["bb_middle"] = bb_sma
            indicators["bb_lower"] = bb_sma - (bb_std * 2)

            # Support/Resistance levels
            indicators["support_levels"] = self._find_support_resistance(
                data, "support"
            )
            indicators["resistance_levels"] = self._find_support_resistance(
                data, "resistance"
            )

            # MACD
            exp1 = data["close"].ewm(span=12, adjust=False).mean()
            exp2 = data["close"].ewm(span=26, adjust=False).mean()
            indicators["macd"] = exp1 - exp2
            indicators["macd_signal"] = (
                indicators["macd"].ewm(span=9, adjust=False).mean()
            )
            indicators["macd_histogram"] = (
                indicators["macd"] - indicators["macd_signal"]
            )

            # ATR (Average True Range)
            high_low = data["high"] - data["low"]
            high_close = np.abs(data["high"] - data["close"].shift())
            low_close = np.abs(data["low"] - data["close"].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            indicators["atr"] = true_range.rolling(14).mean()

            indicators_dict[timeframe] = indicators

        return indicators_dict

    def _find_support_resistance(
        self,
        data: pd.DataFrame,
        type: str = "support",
        lookback: int = 50,
        num_levels: int = 3,
    ) -> List[float]:
        """Find support/resistance levels using local extrema.

        Args:
            data: Price data
            type: 'support' or 'resistance'
            lookback: Number of periods to look back
            num_levels: Number of levels to return

        Returns:
            List of price levels
        """
        if len(data) < lookback:
            return []

        levels = []

        if type == "support":
            # Find local minima
            lows = data["low"].tail(lookback)

            # Use rolling window to find local minima
            for i in range(5, len(lows) - 5):
                if lows.iloc[i] == lows.iloc[i - 5 : i + 6].min():
                    levels.append(lows.iloc[i])
        else:
            # Find local maxima
            highs = data["high"].tail(lookback)

            # Use rolling window to find local maxima
            for i in range(5, len(highs) - 5):
                if highs.iloc[i] == highs.iloc[i - 5 : i + 6].max():
                    levels.append(highs.iloc[i])

        # Remove duplicates and sort
        levels = sorted(list(set(levels)))

        # Return top N levels
        if type == "support":
            return levels[-num_levels:] if levels else []
        else:
            return levels[:num_levels] if levels else []

    def align_timeframe_data(
        self,
        price_data_dict: Dict[str, pd.DataFrame],
        reference_time: Optional[datetime] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Align data across timeframes to a reference point.

        Args:
            price_data_dict: Dictionary of price data by timeframe
            reference_time: Reference time to align to (default: latest common time)

        Returns:
            Dictionary of aligned DataFrames
        """
        if not reference_time:
            # Find the latest time common to all timeframes
            latest_times = [df.index[-1] for df in price_data_dict.values()]
            reference_time = min(latest_times)

        aligned_data = {}

        for timeframe, data in price_data_dict.items():
            # Filter data up to reference time
            aligned = data[data.index <= reference_time].copy()

            # Ensure we have enough history
            min_bars = 100  # Minimum bars needed for analysis
            if len(aligned) >= min_bars:
                aligned_data[timeframe] = aligned
            else:
                logger.warning(f"Insufficient data for {timeframe} timeframe")

        return aligned_data
