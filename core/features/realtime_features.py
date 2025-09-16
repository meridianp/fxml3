"""Real-time feature engineering module for live trading.

This module provides real-time feature computation capabilities required by the
integration test suite, implementing efficient streaming feature calculation for
production trading environments.
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class RealTimeFeatureEngine:
    """Real-time feature computation engine for live trading signals.

    This class implements the interface expected by the integration test suite,
    providing low-latency feature calculation and efficient data buffering for
    real-time trading operations.
    """

    def __init__(
        self,
        buffer_size: int = 1000,
        feature_window: int = 20,
        update_frequency: float = 1.0,
        enable_advanced_features: bool = True,
    ):
        """Initialize the real-time feature engine.

        Args:
            buffer_size: Maximum number of data points to buffer per symbol
            feature_window: Number of periods for rolling calculations
            update_frequency: Minimum seconds between feature updates
            enable_advanced_features: Enable compute-intensive advanced features
        """
        self.buffer_size = buffer_size
        self.feature_window = feature_window
        self.update_frequency = update_frequency
        self.enable_advanced_features = enable_advanced_features

        # Data buffers for each symbol
        self.price_buffers: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=buffer_size)
        )
        self.volume_buffers: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=buffer_size)
        )
        self.timestamp_buffers: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=buffer_size)
        )

        # Current features cache
        self.current_features: Dict[str, Dict[str, float]] = {}
        self.last_update_time: Dict[str, datetime] = {}

        # Statistics tracking
        self.update_count = 0
        self.feature_computation_time = 0.0
        self.symbols_tracked = set()

        # Threading for concurrent processing
        self._feature_lock = threading.RLock()
        self._computation_lock = threading.RLock()

        logger.info(
            "RealTimeFeatureEngine initialized: buffer_size=%d, window=%d",
            buffer_size,
            feature_window,
        )

    def update_features(
        self, symbol: str, price_data: Dict[str, Any], force_update: bool = False
    ) -> bool:
        """Update features for a symbol with new market data.

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            price_data: Dictionary containing price/volume data
            force_update: Force feature computation regardless of frequency limits

        Returns:
            True if features were updated successfully
        """
        try:
            current_time = datetime.utcnow()

            # Check update frequency limits
            if not force_update and symbol in self.last_update_time:
                time_since_update = (
                    current_time - self.last_update_time[symbol]
                ).total_seconds()
                if time_since_update < self.update_frequency:
                    return False

            # Extract price and volume data
            price = price_data.get("price", price_data.get("close", 0.0))
            volume = price_data.get("volume", price_data.get("vol", 1.0))
            timestamp = price_data.get("timestamp", current_time)

            # Validate data
            if price <= 0:
                logger.warning(f"Invalid price data for {symbol}: {price}")
                return False

            # Update buffers
            with self._feature_lock:
                self.price_buffers[symbol].append(price)
                self.volume_buffers[symbol].append(volume)
                self.timestamp_buffers[symbol].append(timestamp)
                self.symbols_tracked.add(symbol)

            # Compute features
            start_time = time.time()
            features = self._compute_features(symbol)
            computation_time = time.time() - start_time

            # Update cache
            with self._computation_lock:
                self.current_features[symbol] = features
                self.last_update_time[symbol] = current_time
                self.update_count += 1
                self.feature_computation_time += computation_time

            logger.debug(
                f"Features updated for {symbol}: {len(features)} features "
                f"(computation: {computation_time*1000:.1f}ms)"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating features for {symbol}: {str(e)}")
            return False

    def get_current_features(
        self, symbol: str, feature_names: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Get current features for a symbol.

        Args:
            symbol: Trading symbol
            feature_names: Specific feature names to retrieve (optional)

        Returns:
            Dictionary of current feature values
        """
        with self._computation_lock:
            if symbol not in self.current_features:
                logger.warning(f"No features available for {symbol}")
                return self._default_features()

            features = self.current_features[symbol].copy()

            # Filter to specific feature names if requested
            if feature_names:
                filtered_features = {}
                for name in feature_names:
                    filtered_features[name] = features.get(name, 0.0)
                return filtered_features

            return features

    def get_all_current_features(self) -> Dict[str, Dict[str, float]]:
        """Get current features for all tracked symbols.

        Returns:
            Dictionary mapping symbols to their feature dictionaries
        """
        with self._computation_lock:
            return {
                symbol: features.copy()
                for symbol, features in self.current_features.items()
            }

    def get_feature_stats(self) -> Dict[str, Any]:
        """Get feature engine performance statistics.

        Returns:
            Dictionary containing performance metrics
        """
        avg_computation_time = (
            self.feature_computation_time / self.update_count
            if self.update_count > 0
            else 0.0
        )

        return {
            "total_updates": self.update_count,
            "symbols_tracked": len(self.symbols_tracked),
            "avg_computation_time_ms": avg_computation_time * 1000,
            "buffer_size": self.buffer_size,
            "feature_window": self.feature_window,
            "total_computation_time": self.feature_computation_time,
            "active_symbols": list(self.symbols_tracked),
        }

    def clear_symbol_data(self, symbol: str) -> bool:
        """Clear all data for a specific symbol.

        Args:
            symbol: Symbol to clear data for

        Returns:
            True if data was cleared successfully
        """
        try:
            with self._feature_lock:
                self.price_buffers.pop(symbol, None)
                self.volume_buffers.pop(symbol, None)
                self.timestamp_buffers.pop(symbol, None)

            with self._computation_lock:
                self.current_features.pop(symbol, None)
                self.last_update_time.pop(symbol, None)
                self.symbols_tracked.discard(symbol)

            logger.info(f"Cleared all data for symbol: {symbol}")
            return True

        except Exception as e:
            logger.error(f"Error clearing data for {symbol}: {str(e)}")
            return False

    # Private feature computation methods

    def _compute_features(self, symbol: str) -> Dict[str, float]:
        """Compute all features for a symbol."""
        features = {}

        # Get data arrays
        prices = np.array(self.price_buffers[symbol])
        volumes = np.array(self.volume_buffers[symbol])

        if len(prices) < 2:
            return self._default_features()

        # Basic price features
        features.update(self._compute_price_features(prices))

        # Volume features
        features.update(self._compute_volume_features(volumes))

        # Technical indicators
        features.update(self._compute_technical_features(prices, volumes))

        # Advanced features (if enabled)
        if self.enable_advanced_features and len(prices) >= self.feature_window:
            features.update(self._compute_advanced_features(prices, volumes))

        # Market microstructure features
        features.update(self._compute_microstructure_features(prices, volumes))

        return features

    def _compute_price_features(self, prices: np.ndarray) -> Dict[str, float]:
        """Compute basic price-based features."""
        features = {}

        # Current price
        features["price"] = float(prices[-1])

        # Returns
        if len(prices) >= 2:
            returns = np.diff(prices) / prices[:-1]
            features["return"] = float(returns[-1]) if len(returns) > 0 else 0.0

            # Return statistics (if sufficient data)
            if len(returns) >= 5:
                features["return_mean"] = float(np.mean(returns[-5:]))
                features["return_std"] = float(np.std(returns[-5:]))
                skew_data = returns[-10:] if len(returns) >= 10 else []
                features["return_skew"] = float(
                    stats.skew(skew_data) if len(skew_data) >= 3 else 0.0
                )

        # Price changes
        if len(prices) >= self.feature_window:
            window_prices = prices[-self.feature_window :]
            features["price_change_pct"] = float(
                (prices[-1] - window_prices[0]) / window_prices[0] * 100
            )
            features["price_range_pct"] = float(
                (np.max(window_prices) - np.min(window_prices)) / window_prices[0] * 100
            )

        return features

    def _compute_volume_features(self, volumes: np.ndarray) -> Dict[str, float]:
        """Compute volume-based features."""
        features = {}

        # Current volume
        features["volume"] = float(volumes[-1]) if len(volumes) > 0 else 0.0

        # Volume statistics
        if len(volumes) >= 5:
            recent_volumes = volumes[-5:]
            features["volume_mean"] = float(np.mean(recent_volumes))
            features["volume_std"] = float(np.std(recent_volumes))

            # Volume trend
            if len(volumes) >= 10:
                recent_vol = np.mean(volumes[-5:])
                prev_vol = np.mean(volumes[-10:-5])
                features["volume_trend"] = float(recent_vol - prev_vol)

        return features

    def _compute_technical_features(
        self, prices: np.ndarray, volumes: np.ndarray
    ) -> Dict[str, float]:
        """Compute technical indicator features."""
        features = {}

        if len(prices) < 5:
            return features

        # Simple Moving Averages
        if len(prices) >= 5:
            features["sma_5"] = float(np.mean(prices[-5:]))
        if len(prices) >= 10:
            features["sma_10"] = float(np.mean(prices[-10:]))
        if len(prices) >= 20:
            features["sma_20"] = float(np.mean(prices[-20:]))

        # RSI approximation
        if len(prices) >= 14:
            returns = np.diff(prices[-15:])  # 14 + 1 for diff
            gains = np.where(returns > 0, returns, 0)
            losses = np.where(returns < 0, -returns, 0)

            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)

            if avg_loss > 0:
                rs = avg_gain / avg_loss
                features["rsi"] = float(100 - (100 / (1 + rs)))
            else:
                features["rsi"] = 100.0

        # MACD approximation
        if len(prices) >= 26:
            ema_12 = self._compute_ema(prices, 12)
            ema_26 = self._compute_ema(prices, 26)
            features["macd"] = float(ema_12 - ema_26)

        # Bollinger Bands
        if len(prices) >= 20:
            sma_20 = np.mean(prices[-20:])
            std_20 = np.std(prices[-20:])
            features["bb_upper"] = float(sma_20 + 2 * std_20)
            features["bb_lower"] = float(sma_20 - 2 * std_20)
            features["bb_position"] = float(
                (prices[-1] - features["bb_lower"])
                / (features["bb_upper"] - features["bb_lower"])
            )

        # Volatility (rolling standard deviation)
        if len(prices) >= 10:
            returns = (
                np.diff(prices[-11:]) / prices[-12:-1]
            )  # 10 returns from 11 prices
            features["volatility"] = float(np.std(returns))

        return features

    def _compute_advanced_features(
        self, prices: np.ndarray, volumes: np.ndarray
    ) -> Dict[str, float]:
        """Compute advanced statistical features."""
        features = {}

        # Higher-order moments
        returns = np.diff(prices) / prices[:-1]
        if len(returns) >= self.feature_window:
            recent_returns = returns[-self.feature_window :]

            # Skewness and kurtosis
            features["skewness"] = float(stats.skew(recent_returns))
            features["kurtosis"] = float(stats.kurtosis(recent_returns))

            # Momentum indicators
            features["momentum"] = float(prices[-1] / prices[-self.feature_window] - 1)

            # Rate of change
            features["roc"] = (
                float((prices[-1] - prices[-5]) / prices[-5] * 100)
                if len(prices) >= 5
                else 0.0
            )

        # Hurst exponent approximation
        if len(prices) >= 50:
            features["hurst_exponent"] = self._compute_hurst_exponent(returns[-50:])

        return features

    def _compute_microstructure_features(
        self, prices: np.ndarray, volumes: np.ndarray
    ) -> Dict[str, float]:
        """Compute market microstructure features."""
        features = {}

        # Price-volume relationship
        if len(prices) >= 5 and len(volumes) >= 5:
            # Volume-weighted average price (VWAP) approximation
            recent_prices = prices[-5:]
            recent_volumes = volumes[-5:]
            total_volume = np.sum(recent_volumes)

            if total_volume > 0:
                features["vwap"] = float(
                    np.sum(recent_prices * recent_volumes) / total_volume
                )
                features["price_vwap_diff"] = float(prices[-1] - features["vwap"])

        # Spread approximation (using price volatility)
        if len(prices) >= 10:
            price_changes = np.abs(np.diff(prices[-10:]))
            features["spread_estimate"] = float(np.mean(price_changes))

        return features

    def _compute_ema(self, prices: np.ndarray, period: int) -> float:
        """Compute exponential moving average."""
        if len(prices) < period:
            return float(np.mean(prices))

        alpha = 2.0 / (period + 1)
        ema = prices[0]

        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema

        return float(ema)

    def _compute_hurst_exponent(self, returns: np.ndarray) -> float:
        """Compute Hurst exponent for trend analysis."""
        try:
            if len(returns) < 20:
                return 0.5  # Random walk default

            # Simple Hurst exponent calculation
            lags = range(2, min(20, len(returns) // 4))
            tau = []

            for lag in lags:
                # Calculate lag differences
                lag_returns = [
                    returns[i] - returns[i - lag] for i in range(lag, len(returns))
                ]
                if lag_returns:
                    tau.append(np.std(lag_returns))
                else:
                    tau.append(0.0)

            if len(tau) >= 2 and all(t > 0 for t in tau):
                # Linear regression in log space
                log_lags = np.log(lags)
                log_tau = np.log(tau)

                slope, _, _, _, _ = stats.linregress(log_lags, log_tau)
                hurst = slope

                # Clamp to reasonable range
                return float(max(0.0, min(1.0, hurst)))

            return 0.5

        except Exception as e:
            logger.debug(f"Error computing Hurst exponent: {e}")
            return 0.5

    def _default_features(self) -> Dict[str, float]:
        """Return default feature values when insufficient data."""
        return {
            "price": 0.0,
            "return": 0.0,
            "volume": 0.0,
            "volatility": 0.0,
            "rsi": 50.0,
            "macd": 0.0,
            "bb_upper": 0.0,
            "bb_lower": 0.0,
            "bb_position": 0.5,
            "sma_5": 0.0,
            "sma_10": 0.0,
            "sma_20": 0.0,
            "momentum": 0.0,
            "vwap": 0.0,
        }


class StreamingFeatureProcessor:
    """High-frequency streaming processor for ultra-low latency features.

    This class complements RealTimeFeatureEngine for scenarios requiring
    sub-millisecond feature computation for high-frequency trading.
    """

    def __init__(self, feature_engine: RealTimeFeatureEngine):
        """Initialize streaming processor.

        Args:
            feature_engine: RealTimeFeatureEngine instance
        """
        self.feature_engine = feature_engine
        self.micro_buffers = defaultdict(lambda: deque(maxlen=100))
        self._processing_lock = threading.Lock()

        logger.info("StreamingFeatureProcessor initialized")

    async def process_tick(
        self, symbol: str, tick_data: Dict[str, Any]
    ) -> Optional[Dict[str, float]]:
        """Process individual tick for ultra-low latency features.

        Args:
            symbol: Trading symbol
            tick_data: Individual tick data

        Returns:
            Computed features or None if processing failed
        """
        try:
            with self._processing_lock:
                # Update micro buffer
                self.micro_buffers[symbol].append(tick_data)

                # Compute micro features
                if len(self.micro_buffers[symbol]) >= 5:
                    micro_features = self._compute_micro_features(symbol)

                    # Update main feature engine
                    success = self.feature_engine.update_features(
                        symbol, tick_data, force_update=True
                    )

                    if success:
                        # Combine with main features
                        main_features = self.feature_engine.get_current_features(symbol)
                        return {**main_features, **micro_features}

                return None

        except Exception as e:
            logger.error(f"Error processing tick for {symbol}: {e}")
            return None

    def _compute_micro_features(self, symbol: str) -> Dict[str, float]:
        """Compute ultra-short-term features from micro buffer."""
        ticks = list(self.micro_buffers[symbol])
        if len(ticks) < 2:
            return {}

        prices = [tick.get("price", 0.0) for tick in ticks]

        return {
            "tick_direction": float(1 if prices[-1] > prices[-2] else -1),
            "tick_volatility": float(np.std(prices[-5:]) if len(prices) >= 5 else 0.0),
            "price_momentum_micro": (
                float((prices[-1] - prices[0]) / prices[0] * 100)
                if prices[0] > 0
                else 0.0
            ),
        }
