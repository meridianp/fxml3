"""
Feature Extractor for ML Pipeline

TDD-driven implementation of feature extraction from market data.
Following Green phase - minimal implementation to pass tests.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any


class FeatureExtractor:
    """Extract features from market data for ML models."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize feature extractor with configuration."""
        self.config = config or {}
        self.features = self.config.get(
            "features", ["sma", "rsi", "macd", "volume_profile"]
        )
        self.lookback_period = self.config.get("lookback_period", 50)
        self.is_fitted = False
        self.scaler = None

    def extract_technical_features(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Extract technical indicator features from market data."""
        features = pd.DataFrame(index=market_data.index)

        # Simple Moving Average
        features["sma_20"] = (
            market_data["close"].rolling(window=20, min_periods=1).mean()
        )
        features["sma_50"] = (
            market_data["close"].rolling(window=50, min_periods=1).mean()
        )

        # RSI (Relative Strength Index)
        features["rsi_14"] = self._calculate_rsi(market_data["close"], period=14)

        # MACD
        macd_features = self._calculate_macd(market_data["close"])
        features["macd_line"] = macd_features["macd"]
        features["macd_signal"] = macd_features["signal"]
        features["macd_histogram"] = macd_features["histogram"]

        # Volume features
        features["volume_sma"] = (
            market_data["volume"].rolling(window=20, min_periods=1).mean()
        )
        features["volume_ratio"] = market_data["volume"] / features[
            "volume_sma"
        ].replace(0, 1)

        # Price features
        features["high_low_ratio"] = market_data["high"] / market_data["low"].replace(
            0, 1
        )
        features["close_open_ratio"] = market_data["close"] / market_data[
            "open"
        ].replace(0, 1)

        # Fill NaN values
        features.ffill(inplace=True)
        features.fillna(0, inplace=True)

        return features

    def extract_price_patterns(self, market_data: pd.DataFrame) -> Dict[str, bool]:
        """Extract price pattern features (candlestick patterns)."""
        patterns = {}

        if len(market_data) < 2:
            return {
                "bullish_engulfing": False,
                "bearish_engulfing": False,
                "doji": False,
            }

        # Get last two candles
        prev = market_data.iloc[-2]
        curr = market_data.iloc[-1]

        # Bullish Engulfing
        patterns["bullish_engulfing"] = (
            prev["close"] < prev["open"]  # Previous is bearish
            and curr["close"] > curr["open"]  # Current is bullish
            and curr["open"] <= prev["close"]  # Opens below prev close
            and curr["close"] >= prev["open"]  # Closes above prev open
        )

        # Bearish Engulfing
        patterns["bearish_engulfing"] = (
            prev["close"] > prev["open"]  # Previous is bullish
            and curr["close"] < curr["open"]  # Current is bearish
            and curr["open"] >= prev["close"]  # Opens above prev close
            and curr["close"] <= prev["open"]  # Closes below prev open
        )

        # Doji (small body)
        body_size = abs(curr["close"] - curr["open"])
        total_range = curr["high"] - curr["low"]
        patterns["doji"] = (
            body_size <= (total_range * 0.1) if total_range > 0 else False
        )

        return patterns

    def extract_microstructure_features(
        self, market_data: pd.DataFrame
    ) -> Dict[str, float]:
        """Extract market microstructure features."""
        features = {}

        # Bid-Ask Spread (simulated)
        features["bid_ask_spread"] = np.random.uniform(0.0001, 0.0005)

        # Order Flow Imbalance (simulated)
        if "volume" in market_data.columns:
            # Simple proxy: volume changes
            volume_change = market_data["volume"].pct_change().fillna(0)
            features["order_flow_imbalance"] = (
                volume_change.iloc[-1] if len(volume_change) > 0 else 0
            )
        else:
            features["order_flow_imbalance"] = 0

        # Volume Weighted Average Price
        if "volume" in market_data.columns and len(market_data) > 0:
            vwap = (market_data["close"] * market_data["volume"]).sum() / market_data[
                "volume"
            ].sum()
            features["volume_weighted_price"] = vwap
        else:
            features["volume_weighted_price"] = (
                market_data["close"].mean() if len(market_data) > 0 else 0
            )

        return features

    def normalize_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """Normalize features to [-1, 1] range."""
        normalized = pd.DataFrame(index=features.index, columns=features.columns)

        for col in features.columns:
            col_data = features[col]
            # Min-Max scaling to [-1, 1]
            min_val = col_data.min()
            max_val = col_data.max()

            if max_val != min_val:
                # Scale to [0, 1] then to [-1, 1]
                normalized[col] = 2 * ((col_data - min_val) / (max_val - min_val)) - 1
            else:
                normalized[col] = 0

        return normalized

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()

        rs = gain / loss.replace(0, 1)
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(
        self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Dict[str, pd.Series]:
        """Calculate MACD indicator."""
        # Calculate EMAs
        ema_fast = prices.ewm(span=fast, min_periods=1).mean()
        ema_slow = prices.ewm(span=slow, min_periods=1).mean()

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line
        signal_line = macd_line.ewm(span=signal, min_periods=1).mean()

        # Histogram
        histogram = macd_line - signal_line

        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}
