"""Technical indicator calculation for market data."""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import ta


class IndicatorCalculator:
    """Calculate technical indicators for market data."""

    def __init__(self):
        """Initialize indicator calculator."""
        pass

    def calculate_all(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators.

        Args:
            data: OHLCV DataFrame

        Returns:
            DataFrame with all indicators
        """
        df = data.copy()

        # Ensure we have the required columns
        required_columns = ["open", "high", "low", "close"]
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"DataFrame must contain columns: {required_columns}")

        # RSI
        df["rsi_14"] = self.calculate_rsi(df["close"], period=14)

        # ATR
        df["atr_14"] = self.calculate_atr(df, period=14)

        # Moving Averages
        df["sma_20"] = self.calculate_sma(df["close"], period=20)
        df["sma_50"] = self.calculate_sma(df["close"], period=50)
        df["sma_200"] = self.calculate_sma(df["close"], period=200)

        # Exponential Moving Averages
        df["ema_9"] = self.calculate_ema(df["close"], period=9)
        df["ema_21"] = self.calculate_ema(df["close"], period=21)

        # Bollinger Bands
        bb = self.calculate_bollinger_bands(df["close"], period=20, std=2)
        df["bb_upper"] = bb["upper"]
        df["bb_middle"] = bb["middle"]
        df["bb_lower"] = bb["lower"]

        # MACD
        macd = self.calculate_macd(df["close"])
        df["macd_line"] = macd["macd"]
        df["macd_signal"] = macd["signal"]
        df["macd_histogram"] = macd["histogram"]

        # ADX
        adx = self.calculate_adx(df)
        df["adx"] = adx["adx"]
        df["plus_di"] = adx["plus_di"]
        df["minus_di"] = adx["minus_di"]

        # Stochastic
        stoch = self.calculate_stochastic(df)
        df["stoch_k"] = stoch["%k"]
        df["stoch_d"] = stoch["%d"]

        return df

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index.

        Args:
            prices: Price series
            period: RSI period

        Returns:
            RSI values
        """
        return ta.momentum.RSIIndicator(close=prices, window=period).rsi()

    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range.

        Args:
            data: OHLC DataFrame
            period: ATR period

        Returns:
            ATR values
        """
        return ta.volatility.AverageTrueRange(
            high=data["high"], low=data["low"], close=data["close"], window=period
        ).average_true_range()

    def calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average.

        Args:
            prices: Price series
            period: SMA period

        Returns:
            SMA values
        """
        return prices.rolling(window=period).mean()

    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average.

        Args:
            prices: Price series
            period: EMA period

        Returns:
            EMA values
        """
        return prices.ewm(span=period).mean()

    def calculate_bollinger_bands(
        self, prices: pd.Series, period: int = 20, std: float = 2
    ) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands.

        Args:
            prices: Price series
            period: Period for moving average
            std: Standard deviation multiplier

        Returns:
            Dict with upper, middle, lower bands
        """
        bb = ta.volatility.BollingerBands(close=prices, window=period, window_dev=std)

        return {
            "upper": bb.bollinger_hband(),
            "middle": bb.bollinger_mavg(),
            "lower": bb.bollinger_lband(),
        }

    def calculate_macd(
        self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Dict[str, pd.Series]:
        """Calculate MACD.

        Args:
            prices: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period

        Returns:
            Dict with MACD line, signal line, histogram
        """
        macd = ta.trend.MACD(
            close=prices, window_fast=fast, window_slow=slow, window_sign=signal
        )

        return {
            "macd": macd.macd(),
            "signal": macd.macd_signal(),
            "histogram": macd.macd_diff(),
        }

    def calculate_adx(
        self, data: pd.DataFrame, period: int = 14
    ) -> Dict[str, pd.Series]:
        """Calculate Average Directional Index.

        Args:
            data: OHLC DataFrame
            period: ADX period

        Returns:
            Dict with ADX, +DI, -DI
        """
        adx = ta.trend.ADXIndicator(
            high=data["high"], low=data["low"], close=data["close"], window=period
        )

        return {"adx": adx.adx(), "plus_di": adx.adx_pos(), "minus_di": adx.adx_neg()}

    def calculate_stochastic(
        self, data: pd.DataFrame, k_period: int = 14, d_period: int = 3
    ) -> Dict[str, pd.Series]:
        """Calculate Stochastic Oscillator.

        Args:
            data: OHLC DataFrame
            k_period: %K period
            d_period: %D period

        Returns:
            Dict with %K and %D
        """
        stoch = ta.momentum.StochasticOscillator(
            high=data["high"],
            low=data["low"],
            close=data["close"],
            window=k_period,
            smooth_window=d_period,
        )

        return {"%k": stoch.stoch(), "%d": stoch.stoch_signal()}

    def calculate_williams_r(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Williams %R.

        Args:
            data: OHLC DataFrame
            period: Williams %R period

        Returns:
            Williams %R values
        """
        return ta.momentum.WilliamsRIndicator(
            high=data["high"], low=data["low"], close=data["close"], lbp=period
        ).williams_r()

    def calculate_cci(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Commodity Channel Index.

        Args:
            data: OHLC DataFrame
            period: CCI period

        Returns:
            CCI values
        """
        return ta.momentum.CCIIndicator(
            high=data["high"], low=data["low"], close=data["close"], window=period
        ).cci()

    def calculate_fibonacci_retracements(
        self, high_price: float, low_price: float
    ) -> Dict[str, float]:
        """Calculate Fibonacci retracement levels.

        Args:
            high_price: Swing high
            low_price: Swing low

        Returns:
            Dict with Fibonacci levels
        """
        diff = high_price - low_price

        levels = {
            "level_0": high_price,
            "level_236": high_price - (0.236 * diff),
            "level_382": high_price - (0.382 * diff),
            "level_500": high_price - (0.500 * diff),
            "level_618": high_price - (0.618 * diff),
            "level_786": high_price - (0.786 * diff),
            "level_100": low_price,
        }

        return levels

    def detect_support_resistance(
        self, data: pd.DataFrame, window: int = 20, min_touches: int = 2
    ) -> Dict[str, list]:
        """Detect support and resistance levels.

        Args:
            data: OHLC DataFrame
            window: Window for local extrema detection
            min_touches: Minimum touches for valid level

        Returns:
            Dict with support and resistance levels
        """
        highs = data["high"]
        lows = data["low"]

        # Find local maxima and minima
        resistance_candidates = []
        support_candidates = []

        for i in range(window, len(data) - window):
            # Check for local high
            if highs.iloc[i] == highs.iloc[i - window : i + window + 1].max():
                resistance_candidates.append(highs.iloc[i])

            # Check for local low
            if lows.iloc[i] == lows.iloc[i - window : i + window + 1].min():
                support_candidates.append(lows.iloc[i])

        # Cluster levels and find valid ones
        support_levels = self._cluster_levels(support_candidates, min_touches)
        resistance_levels = self._cluster_levels(resistance_candidates, min_touches)

        return {"support": support_levels, "resistance": resistance_levels}

    def _cluster_levels(
        self, levels: list, min_touches: int, tolerance: float = 0.001
    ) -> list:
        """Cluster price levels and return valid ones.

        Args:
            levels: List of price levels
            min_touches: Minimum touches for valid level
            tolerance: Price tolerance for clustering

        Returns:
            List of valid clustered levels
        """
        if not levels:
            return []

        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]

        for level in levels[1:]:
            if abs(level - current_cluster[-1]) / current_cluster[-1] <= tolerance:
                current_cluster.append(level)
            else:
                if len(current_cluster) >= min_touches:
                    clusters.append(np.mean(current_cluster))
                current_cluster = [level]

        # Check last cluster
        if len(current_cluster) >= min_touches:
            clusters.append(np.mean(current_cluster))

        return clusters
