#!/usr/bin/env python
"""Enhanced ML signal generator with market regime filters and improved features."""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from fxml4.features import UnifiedFeatureEngineer
from fxml4.ml.features import add_lagged_features, create_technical_features
from fxml4.ml.models import ClassicMLModel

logger = logging.getLogger(__name__)


@dataclass
class MLSignal:
    """ML trading signal with enhanced metadata."""

    action: str  # LONG/SHORT/HOLD
    confidence: float
    predicted_return: float
    market_regime: str
    volatility_regime: str
    trend_strength: float
    feature_importance: Dict[str, float]
    filters_passed: List[str]
    filters_failed: List[str]


class EnhancedMLSignalGenerator:
    """Enhanced ML signal generator with market regime awareness."""

    def __init__(
        self,
        model=None,
        min_confidence: float = 0.65,  # Higher threshold
        max_signals_per_week: int = 3,
        use_market_regime_filter: bool = True,
        use_volatility_filter: bool = True,
        use_trend_filter: bool = True,
        use_time_filter: bool = True,
    ):
        self.model = model
        self.min_confidence = min_confidence
        self.max_signals_per_week = max_signals_per_week
        self.use_market_regime_filter = use_market_regime_filter
        self.use_volatility_filter = use_volatility_filter
        self.use_trend_filter = use_trend_filter
        self.use_time_filter = use_time_filter

        # Track recent signals
        self.recent_signals = []

    def generate_signal(
        self, data: pd.DataFrame, current_time: pd.Timestamp
    ) -> Optional[MLSignal]:
        """Generate ML signal with comprehensive filtering."""

        # Check signal frequency limit
        if not self._check_signal_frequency(current_time):
            return None

        # Create enhanced features
        features = self._create_enhanced_features(data)

        if features.empty or self.model is None:
            return None

        # Get ML prediction
        try:
            prediction = self.model.predict(features.iloc[-1:])

            if prediction is None or len(prediction) == 0:
                return None

            # Get prediction details
            signal_value = prediction[0]

            # Get confidence/probability
            try:
                proba = self.model.predict_proba(features.iloc[-1:])
                confidence = float(max(proba[0]))
            except:
                confidence = min(abs(signal_value) * 0.8, 0.9)

            # Determine action
            if signal_value > 0:
                action = "LONG"
            elif signal_value < 0:
                action = "SHORT"
            else:
                action = "HOLD"

            # Get market regime
            market_regime = self._determine_market_regime(data)
            volatility_regime = self._determine_volatility_regime(data)
            trend_strength = self._calculate_trend_strength(data)

            # Apply filters
            filters_passed = []
            filters_failed = []

            # Market regime filter
            if self.use_market_regime_filter:
                if self._check_market_regime_filter(action, market_regime):
                    filters_passed.append("market_regime")
                else:
                    filters_failed.append("market_regime")
                    return None  # Fail fast

            # Volatility filter
            if self.use_volatility_filter:
                if self._check_volatility_filter(volatility_regime):
                    filters_passed.append("volatility")
                else:
                    filters_failed.append("volatility")
                    confidence *= 0.8  # Reduce confidence

            # Trend filter
            if self.use_trend_filter:
                if self._check_trend_filter(action, data):
                    filters_passed.append("trend")
                else:
                    filters_failed.append("trend")
                    confidence *= 0.7  # Reduce confidence

            # Time filter
            if self.use_time_filter:
                if self._check_time_filter(current_time):
                    filters_passed.append("time")
                else:
                    filters_failed.append("time")
                    confidence *= 0.9  # Slight reduction

            # Check minimum confidence after filters
            if confidence < self.min_confidence:
                return None

            # Calculate predicted return
            predicted_return = self._calculate_predicted_return(features, signal_value)

            # Get feature importance
            feature_importance = self._get_feature_importance(features)

            # Create signal
            signal = MLSignal(
                action=action,
                confidence=confidence,
                predicted_return=predicted_return,
                market_regime=market_regime,
                volatility_regime=volatility_regime,
                trend_strength=trend_strength,
                feature_importance=feature_importance,
                filters_passed=filters_passed,
                filters_failed=filters_failed,
            )

            # Record signal
            self.recent_signals.append(
                {"time": current_time, "action": action, "confidence": confidence}
            )

            return signal

        except Exception as e:
            logger.error(f"ML signal generation error: {e}")
            return None

    def _create_enhanced_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create enhanced feature set for ML model using unified feature engineering."""

        # Use unified feature engineering to generate all features
        feature_engineer = UnifiedFeatureEngineer(
            {
                "advanced_features": True,
                "elliott_wave_features": True,
                "regime_features": True,
                "microstructure_features": True,
            }
        )

        # Generate all features
        features = feature_engineer.generate_features(data.copy())

        if features.empty:
            return features

        # Add additional time-based features if not already present
        if isinstance(features.index, pd.DatetimeIndex):
            if "hour" not in features.columns:
                features["hour"] = features.index.hour
            if "day_of_week" not in features.columns:
                features["day_of_week"] = features.index.dayofweek
            if "is_london_session" not in features.columns:
                features["is_london_session"] = (
                    (features.index.hour >= 8) & (features.index.hour < 17)
                ).astype(int)
            if "is_ny_session" not in features.columns:
                features["is_ny_session"] = (
                    (features.index.hour >= 13) & (features.index.hour < 22)
                ).astype(int)

        # Add lagged features for key indicators
        key_features = ["close", "rsi_14", "macd", "bb_width", "atr_14"]
        for feat in key_features:
            if feat in features.columns:
                for lag in [1, 2, 5]:
                    features[f"{feat}_lag_{lag}"] = features[feat].shift(lag)

        # Clean up any NaN values
        features = features.fillna(method="ffill").fillna(method="bfill").fillna(0)

        return features

    def _determine_market_regime(self, data: pd.DataFrame) -> str:
        """Determine current market regime."""

        # Use ADX for trend strength
        adx = self._calculate_adx(data)

        # Use price position relative to moving averages
        current_price = data["close"].iloc[-1]
        sma_20 = data["close"].rolling(20).mean().iloc[-1]
        sma_50 = data["close"].rolling(50).mean().iloc[-1]

        # Determine regime
        if adx > 25:
            if current_price > sma_20 > sma_50:
                return "strong_uptrend"
            elif current_price < sma_20 < sma_50:
                return "strong_downtrend"
            else:
                return "choppy_trend"
        elif adx > 20:
            if current_price > sma_50:
                return "weak_uptrend"
            else:
                return "weak_downtrend"
        else:
            return "ranging"

    def _determine_volatility_regime(self, data: pd.DataFrame) -> str:
        """Determine volatility regime."""

        # Calculate current vs historical volatility
        current_vol = data["close"].pct_change().tail(20).std()
        hist_vol = data["close"].pct_change().tail(100).std()

        vol_ratio = current_vol / hist_vol if hist_vol > 0 else 1

        if vol_ratio > 1.5:
            return "high_volatility"
        elif vol_ratio > 1.2:
            return "elevated_volatility"
        elif vol_ratio < 0.8:
            return "low_volatility"
        else:
            return "normal_volatility"

    def _calculate_trend_strength(self, data: pd.DataFrame) -> float:
        """Calculate trend strength (0-1)."""

        # Use combination of ADX and price position
        adx = self._calculate_adx(data)

        # Normalize ADX (0-50 range typically)
        trend_strength = min(adx / 50, 1.0)

        return trend_strength

    def _calculate_adx(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average Directional Index."""

        if "adx" in data.columns:
            return float(data["adx"].iloc[-1])

        # Manual calculation
        high = data["high"]
        low = data["low"]
        close = data["close"]

        # Calculate +DM and -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        # Calculate TR
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Calculate +DI and -DI
        plus_di = 100 * (plus_dm.rolling(period).mean() / tr.rolling(period).mean())
        minus_di = 100 * (minus_dm.rolling(period).mean() / tr.rolling(period).mean())

        # Calculate DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()

        return float(adx.iloc[-1]) if not adx.empty else 20

    def _calculate_volatility_ratio(self, data: pd.DataFrame) -> float:
        """Calculate volatility ratio."""

        current_vol = data["close"].pct_change().tail(20).std()
        hist_vol = data["close"].pct_change().tail(100).std()

        return current_vol / hist_vol if hist_vol > 0 else 1

    def _check_signal_frequency(self, current_time: pd.Timestamp) -> bool:
        """Check if we haven't exceeded signal frequency limit."""

        # Remove old signals (older than 7 days)
        cutoff_time = current_time - pd.Timedelta(days=7)
        self.recent_signals = [
            s for s in self.recent_signals if s["time"] > cutoff_time
        ]

        # Check limit
        return len(self.recent_signals) < self.max_signals_per_week

    def _check_market_regime_filter(self, action: str, regime: str) -> bool:
        """Check if signal aligns with market regime."""

        # Don't trade against strong trends
        if action == "LONG" and regime == "strong_downtrend":
            return False
        if action == "SHORT" and regime == "strong_uptrend":
            return False

        # Avoid ranging markets for trend following
        if regime == "ranging" and action != "HOLD":
            return False  # Could be modified for range trading strategies

        return True

    def _check_volatility_filter(self, regime: str) -> bool:
        """Check if volatility regime is suitable for trading."""

        # Avoid extremely high volatility
        if regime == "high_volatility":
            return False

        return True

    def _check_trend_filter(self, action: str, data: pd.DataFrame) -> bool:
        """Check if signal aligns with trend."""

        # Simple trend check using multiple timeframes
        sma_20 = data["close"].rolling(20).mean().iloc[-1]
        sma_50 = data["close"].rolling(50).mean().iloc[-1]
        current_price = data["close"].iloc[-1]

        if action == "LONG":
            # For long, prefer price above short-term MA
            return current_price > sma_20
        elif action == "SHORT":
            # For short, prefer price below short-term MA
            return current_price < sma_20

        return True

    def _check_time_filter(self, current_time: pd.Timestamp) -> bool:
        """Check if current time is suitable for trading."""

        hour = current_time.hour

        # Avoid major news times (example)
        # Avoid low liquidity times
        if hour < 6 or hour > 22:  # Avoid overnight for 4H bars
            return False

        return True

    def _calculate_predicted_return(
        self, features: pd.DataFrame, signal_value: float
    ) -> float:
        """Calculate predicted return based on model output."""

        # This would ideally come from the model
        # For now, use a simple mapping
        base_return = abs(signal_value) * 0.002  # 0.2% per signal unit

        # Adjust for volatility
        if "volatility_ratio" in features.columns:
            vol_adjustment = 1.0 / features["volatility_ratio"].iloc[-1]
            base_return *= vol_adjustment

        return base_return

    def _get_feature_importance(self, features: pd.DataFrame) -> Dict[str, float]:
        """Get feature importance for the signal."""

        # This would come from the model in production
        # For now, return mock importance
        top_features = {
            "rsi_14": 0.15,
            "trend_strength": 0.12,
            "returns_20": 0.10,
            "volume_ratio": 0.08,
            "sma_ratio": 0.07,
        }

        return top_features


def demonstrate_enhanced_ml():
    """Demonstrate the enhanced ML signal generator."""

    print("Enhanced ML Signal Generator")
    print("=" * 60)

    generator = EnhancedMLSignalGenerator(
        min_confidence=0.65,
        max_signals_per_week=3,
        use_market_regime_filter=True,
        use_volatility_filter=True,
        use_trend_filter=True,
        use_time_filter=True,
    )

    print("\nKey Improvements:")
    print("1. Market Regime Awareness:")
    print("   - Detects trending/ranging markets")
    print("   - Avoids trading against strong trends")
    print("   - Adapts to volatility regimes")

    print("\n2. Enhanced Features:")
    print("   - Market microstructure (volume)")
    print("   - Time-based features (sessions)")
    print("   - Trend strength indicators")
    print("   - Volatility ratios")

    print("\n3. Multi-Layer Filtering:")
    print("   - Market regime filter")
    print("   - Volatility filter")
    print("   - Trend alignment filter")
    print("   - Time/session filter")
    print("   - Signal frequency limit")

    print("\n4. Quality Control:")
    print("   - Higher confidence thresholds (65%+)")
    print("   - Maximum 3 signals per week")
    print("   - Multiple filter requirements")

    print("\n5. Rich Signal Output:")
    print("   - Predicted returns")
    print("   - Market context")
    print("   - Feature importance")
    print("   - Filter status")


if __name__ == "__main__":
    demonstrate_enhanced_ml()
