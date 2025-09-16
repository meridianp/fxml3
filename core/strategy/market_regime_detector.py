"""Market regime detection for adaptive trading strategies."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime types."""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CHOPPY = "choppy"
    BREAKOUT = "breakout"


class VolatilityRegime(Enum):
    """Volatility regime types."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class RegimeConfig:
    """Configuration for regime detection."""

    # Trend detection
    adx_trend_threshold: float = 25.0
    adx_strong_trend: float = 40.0
    ma_lookback_fast: int = 20
    ma_lookback_slow: int = 50

    # Volatility detection
    atr_lookback: int = 14
    volatility_percentiles: List[float] = None

    # Market structure
    support_resistance_lookback: int = 100
    breakout_atr_multiplier: float = 2.0

    # Efficiency
    efficiency_ratio_period: int = 20
    efficiency_threshold: float = 0.3

    # Time filters
    session_filters: Dict[str, Tuple[int, int]] = None  # Trading session hours

    def __post_init__(self):
        if self.volatility_percentiles is None:
            self.volatility_percentiles = [25, 50, 75, 90]
        if self.session_filters is None:
            # Default forex sessions (UTC)
            self.session_filters = {
                "asian": (0, 8),
                "european": (7, 16),
                "american": (13, 22),
            }


class MarketRegimeDetector:
    """
    Detects market regime to filter trading opportunities.

    Features:
    - Trend strength detection (ADX-based)
    - Volatility regime classification
    - Market efficiency calculation
    - Support/resistance analysis
    - Multi-timeframe regime confirmation
    - Session-based filtering
    """

    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()
        self.volatility_history = []
        self.regime_history = []

    def analyze_market(self, df: pd.DataFrame, current_idx: int) -> Dict[str, any]:
        """
        Comprehensive market analysis.

        Args:
            df: DataFrame with OHLCV and indicators
            current_idx: Current bar index

        Returns:
            Dictionary with market analysis results
        """
        # Ensure we have enough data
        if current_idx < max(
            self.config.ma_lookback_slow, self.config.support_resistance_lookback
        ):
            return self._default_analysis()

        # Get current and historical data
        current_bar = df.iloc[current_idx]
        lookback_data = df.iloc[
            max(0, current_idx - self.config.support_resistance_lookback) : current_idx
            + 1
        ]

        # Detect regimes
        market_regime = self._detect_market_regime(lookback_data, current_bar)
        volatility_regime = self._detect_volatility_regime(lookback_data, current_bar)

        # Calculate market metrics
        trend_strength = self._calculate_trend_strength(lookback_data, current_bar)
        market_efficiency = self._calculate_market_efficiency(lookback_data)

        # Detect market structure
        support_resistance = self._find_support_resistance(lookback_data)
        is_breakout = self._detect_breakout(
            lookback_data, current_bar, support_resistance
        )

        # Session analysis
        current_session = self._get_trading_session(current_bar.name)
        is_good_session = self._is_favorable_session(current_session, market_regime)

        # Trading conditions
        is_tradeable = self._evaluate_trading_conditions(
            market_regime, volatility_regime, trend_strength, market_efficiency
        )

        # Recommended position sizing adjustment
        position_size_multiplier = self._calculate_position_adjustment(
            volatility_regime, market_regime, trend_strength
        )

        analysis = {
            "market_regime": market_regime,
            "volatility_regime": volatility_regime,
            "trend_strength": trend_strength,
            "market_efficiency": market_efficiency,
            "support_levels": support_resistance["support"],
            "resistance_levels": support_resistance["resistance"],
            "is_breakout": is_breakout,
            "current_session": current_session,
            "is_good_session": is_good_session,
            "is_tradeable": is_tradeable,
            "position_size_multiplier": position_size_multiplier,
            "regime_confidence": self._calculate_regime_confidence(lookback_data),
        }

        # Store in history
        self.regime_history.append(
            {
                "timestamp": current_bar.name,
                "regime": market_regime,
                "volatility": volatility_regime,
            }
        )

        return analysis

    def _detect_market_regime(
        self, data: pd.DataFrame, current_bar: pd.Series
    ) -> MarketRegime:
        """Detect current market regime."""

        # Get indicators
        adx = current_bar.get("adx_14", 0)
        plus_di = current_bar.get("plus_di_14", 0)
        minus_di = current_bar.get("minus_di_14", 0)

        # Calculate MAs if not available
        if "sma_20" not in current_bar:
            sma_fast = (
                data["close"].rolling(self.config.ma_lookback_fast).mean().iloc[-1]
            )
            sma_slow = (
                data["close"].rolling(self.config.ma_lookback_slow).mean().iloc[-1]
            )
        else:
            sma_fast = current_bar.get("sma_20", current_bar["close"])
            sma_slow = current_bar.get("sma_50", current_bar["close"])

        # Strong trend detection
        if adx > self.config.adx_strong_trend:
            if plus_di > minus_di and sma_fast > sma_slow:
                return MarketRegime.TRENDING_UP
            elif minus_di > plus_di and sma_fast < sma_slow:
                return MarketRegime.TRENDING_DOWN

        # Moderate trend
        elif adx > self.config.adx_trend_threshold:
            if plus_di > minus_di:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.TRENDING_DOWN

        # Check for choppy market
        else:
            # Calculate price oscillation
            high_low_ratio = (
                data["high"].rolling(20).max() / data["low"].rolling(20).min()
            )
            recent_ratio = high_low_ratio.iloc[-1]

            if recent_ratio > 1.02:  # More than 2% range
                # Check if it's ranging or choppy
                closes = data["close"].tail(20)
                direction_changes = ((closes.diff() > 0).astype(int).diff() != 0).sum()

                if direction_changes > 12:  # Many direction changes
                    return MarketRegime.CHOPPY
                else:
                    return MarketRegime.RANGING
            else:
                return MarketRegime.RANGING

    def _detect_volatility_regime(
        self, data: pd.DataFrame, current_bar: pd.Series
    ) -> VolatilityRegime:
        """Detect current volatility regime."""

        # Get ATR
        current_atr = current_bar.get("atr_14", None)

        # Calculate true range if needed
        if current_atr is None or "atr_14" not in data.columns:
            # Calculate ATR
            high_low = data["high"] - data["low"]
            high_close = abs(data["high"] - data["close"].shift(1))
            low_close = abs(data["low"] - data["close"].shift(1))

            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(
                axis=1
            )
            historical_atr = true_range.rolling(self.config.atr_lookback).mean()

            if current_atr is None:
                current_atr = historical_atr.iloc[-1]
        else:
            # Use existing ATR column
            historical_atr = data["atr_14"]

        # Add current ATR to history
        self.volatility_history.append(current_atr)
        if len(self.volatility_history) > 1000:
            self.volatility_history.pop(0)

        # Calculate percentile
        if len(self.volatility_history) > 50:
            percentile = np.percentile(self.volatility_history, [25, 50, 75, 90])

            if current_atr < percentile[0]:
                return VolatilityRegime.LOW
            elif current_atr < percentile[1]:
                return VolatilityRegime.NORMAL
            elif current_atr < percentile[3]:
                return VolatilityRegime.HIGH
            else:
                return VolatilityRegime.EXTREME
        else:
            # Not enough history, use relative measure
            avg_atr = (
                np.mean(self.volatility_history)
                if self.volatility_history
                else current_atr
            )

            if current_atr < avg_atr * 0.7:
                return VolatilityRegime.LOW
            elif current_atr < avg_atr * 1.3:
                return VolatilityRegime.NORMAL
            elif current_atr < avg_atr * 2.0:
                return VolatilityRegime.HIGH
            else:
                return VolatilityRegime.EXTREME

    def _calculate_trend_strength(
        self, data: pd.DataFrame, current_bar: pd.Series
    ) -> float:
        """Calculate trend strength (0-100)."""

        # Primary: ADX
        adx = current_bar.get("adx_14", 0)
        trend_strength = min(adx / 50 * 100, 100)  # Normalize to 0-100

        # Secondary: Price vs MA
        sma_20 = current_bar.get("sma_20", current_bar["close"])
        sma_50 = current_bar.get("sma_50", current_bar["close"])

        price_ma_score = 0
        if current_bar["close"] > sma_20 > sma_50:
            price_ma_score = 100
        elif current_bar["close"] < sma_20 < sma_50:
            price_ma_score = 100
        else:
            price_ma_score = 50

        # Combine scores
        return trend_strength * 0.7 + price_ma_score * 0.3

    def _calculate_market_efficiency(self, data: pd.DataFrame) -> float:
        """
        Calculate market efficiency ratio.
        Higher values indicate more directional movement.
        """
        period = min(self.config.efficiency_ratio_period, len(data) - 1)

        if period < 2:
            return 0.5

        # Calculate net price change
        net_change = abs(data["close"].iloc[-1] - data["close"].iloc[-period])

        # Calculate sum of individual moves
        individual_moves = abs(data["close"].diff()).tail(period).sum()

        if individual_moves == 0:
            return 0

        efficiency = net_change / individual_moves

        return min(efficiency, 1.0)

    def _find_support_resistance(self, data: pd.DataFrame) -> Dict[str, List[float]]:
        """Find key support and resistance levels."""

        # Simple peak/trough detection
        highs = data["high"].rolling(5, center=True).max() == data["high"]
        lows = data["low"].rolling(5, center=True).min() == data["low"]

        resistance_levels = data.loc[highs, "high"].tail(5).tolist()
        support_levels = data.loc[lows, "low"].tail(5).tolist()

        # Add psychological levels (round numbers)
        current_price = data["close"].iloc[-1]
        round_interval = 0.0010 if current_price < 2 else 0.0100  # Pip-based

        psychological_levels = []
        for i in range(-5, 6):
            level = (
                round(current_price / round_interval) * round_interval
                + i * round_interval
            )
            if abs(level - current_price) / current_price < 0.02:  # Within 2%
                psychological_levels.append(level)

        return {
            "support": sorted(support_levels),
            "resistance": sorted(resistance_levels),
            "psychological": sorted(psychological_levels),
        }

    def _detect_breakout(
        self, data: pd.DataFrame, current_bar: pd.Series, support_resistance: Dict
    ) -> bool:
        """Detect if current bar is a breakout."""

        current_price = current_bar["close"]
        current_atr = current_bar.get("atr_14", current_price * 0.001)

        # Check resistance breakout
        for resistance in support_resistance["resistance"]:
            if current_price > resistance and current_bar["open"] < resistance:
                # Confirm with volume if available
                if "volume" in current_bar:
                    avg_volume = data["volume"].rolling(20).mean().iloc[-1]
                    if current_bar["volume"] > avg_volume * 1.5:
                        return True
                else:
                    return True

        # Check support breakdown
        for support in support_resistance["support"]:
            if current_price < support and current_bar["open"] > support:
                if "volume" in current_bar:
                    avg_volume = data["volume"].rolling(20).mean().iloc[-1]
                    if current_bar["volume"] > avg_volume * 1.5:
                        return True
                else:
                    return True

        return False

    def _get_trading_session(self, timestamp: pd.Timestamp) -> str:
        """Determine current trading session."""
        hour = timestamp.hour

        for session, (start, end) in self.config.session_filters.items():
            if start <= hour < end:
                return session

        return "off_hours"

    def _is_favorable_session(self, session: str, market_regime: MarketRegime) -> bool:
        """Check if current session is favorable for the regime."""

        # Best sessions for different regimes
        favorable_sessions = {
            MarketRegime.TRENDING_UP: ["european", "american"],
            MarketRegime.TRENDING_DOWN: ["european", "american"],
            MarketRegime.RANGING: ["asian"],
            MarketRegime.VOLATILE: ["american"],
            MarketRegime.CHOPPY: [],  # Avoid choppy markets
            MarketRegime.BREAKOUT: ["european", "american"],
        }

        return session in favorable_sessions.get(market_regime, [])

    def _evaluate_trading_conditions(
        self,
        market_regime: MarketRegime,
        volatility_regime: VolatilityRegime,
        trend_strength: float,
        market_efficiency: float,
    ) -> bool:
        """Evaluate if conditions are suitable for trading."""

        # Avoid choppy markets
        if market_regime == MarketRegime.CHOPPY:
            return False

        # Avoid extreme volatility
        if volatility_regime == VolatilityRegime.EXTREME:
            return False

        # For trending markets, require minimum trend strength
        if market_regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            if trend_strength < 40:  # Weak trend
                return False

        # For ranging markets, require normal volatility
        if market_regime == MarketRegime.RANGING:
            if volatility_regime not in [
                VolatilityRegime.NORMAL,
                VolatilityRegime.HIGH,
            ]:
                return False

        # Require minimum market efficiency
        if market_efficiency < self.config.efficiency_threshold:
            return False

        return True

    def _calculate_position_adjustment(
        self,
        volatility_regime: VolatilityRegime,
        market_regime: MarketRegime,
        trend_strength: float,
    ) -> float:
        """Calculate position size adjustment multiplier."""

        base_multiplier = 1.0

        # Adjust for volatility
        volatility_multipliers = {
            VolatilityRegime.LOW: 1.2,
            VolatilityRegime.NORMAL: 1.0,
            VolatilityRegime.HIGH: 0.7,
            VolatilityRegime.EXTREME: 0.3,
        }
        base_multiplier *= volatility_multipliers.get(volatility_regime, 1.0)

        # Adjust for market regime
        if market_regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            # Increase size in strong trends
            base_multiplier *= 1.0 + (trend_strength / 100) * 0.5
        elif market_regime == MarketRegime.CHOPPY:
            base_multiplier *= 0.5

        return round(base_multiplier, 2)

    def _calculate_regime_confidence(self, data: pd.DataFrame) -> float:
        """Calculate confidence in regime detection."""

        if len(self.regime_history) < 10:
            return 0.5

        # Check regime stability
        recent_regimes = [r["regime"] for r in self.regime_history[-10:]]
        unique_regimes = len(set(recent_regimes))

        # More stable = higher confidence
        stability_score = 1.0 - (unique_regimes - 1) / 10

        return stability_score

    def _default_analysis(self) -> Dict:
        """Return default analysis when insufficient data."""
        return {
            "market_regime": MarketRegime.RANGING,
            "volatility_regime": VolatilityRegime.NORMAL,
            "trend_strength": 0,
            "market_efficiency": 0.5,
            "support_levels": [],
            "resistance_levels": [],
            "is_breakout": False,
            "current_session": "unknown",
            "is_good_session": False,
            "is_tradeable": False,
            "position_size_multiplier": 0.5,
            "regime_confidence": 0,
        }
