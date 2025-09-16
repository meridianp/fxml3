"""
USD/CHF Signal Generator for FXML4.

This module provides specialized signal generation for the USD/CHF currency pair,
incorporating Swiss National Bank policy analysis, safe-haven flow detection,
European session optimization, and cross-asset correlation analysis.

Key Components:
- Swiss National Bank (SNB) intervention level monitoring
- Safe-haven flow analysis during market stress periods
- European session trading pattern recognition
- Cross-correlation with gold, EUR/USD, and equity markets
- Multi-timeframe Elliott Wave pattern integration
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..data_engineering.features import FeatureEngineer
from ..ml.models.signal_model import SignalModel
from ..wave_analysis.elliott_wave import ElliottWaveAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class USDCHFMarketContext:
    """Market context specific to USD/CHF trading."""

    snb_intervention_risk: str = "normal"  # low, normal, high, extreme
    safe_haven_demand: str = "neutral"  # weak, neutral, strong
    european_session_active: bool = False
    cross_asset_momentum: Dict[str, float] = None
    volatility_regime: str = "normal"  # low, normal, high
    parity_proximity: float = 0.0  # Distance from 1.0000 level

    def __post_init__(self):
        if self.cross_asset_momentum is None:
            self.cross_asset_momentum = {
                "gold": 0.0,
                "eur_usd": 0.0,
                "spx": 0.0,
                "vix": 20.0,
            }


class USDCHFSignalGenerator:
    """
    Specialized signal generator for USD/CHF currency pair.

    Integrates Swiss market dynamics, SNB policy considerations,
    and safe-haven characteristics into signal generation.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize USD/CHF signal generator.

        Args:
            config: Configuration parameters
        """
        self.config = self._get_default_config()
        if config:
            self.config.update(config)

        # Initialize components
        self.signal_model = SignalModel(
            model_type="usdchf_neural_network", features=self.config["ml_features"]
        )
        self.elliott_wave = ElliottWaveAnalyzer()
        self.feature_engineer = FeatureEngineer()

        # Swiss market specific parameters
        self.snb_levels = {
            "strong_support": [0.8500, 0.9000, 0.9500],
            "strong_resistance": [1.0500, 1.1000, 1.1500],
            "intervention_threshold": 0.02,  # 2% proximity threshold
        }

        # Market context tracking
        self.current_context = USDCHFMarketContext()
        self.signal_history = []

        logger.info(
            "Initialized USD/CHF signal generator with Swiss market integration"
        )

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for USD/CHF signal generation."""
        return {
            "ml_features": [
                "price_momentum_5",
                "price_momentum_20",
                "rsi_14",
                "macd_signal",
                "bollinger_position",
                "volume_momentum",
                "swiss_session",
                "snb_proximity",
                "safe_haven_index",
                "gold_correlation",
                "eur_correlation",
                "volatility_regime",
            ],
            "elliott_wave_config": {
                "primary_timeframe": "1H",
                "secondary_timeframes": ["15M", "4H", "1D"],
                "min_wave_strength": 0.65,
                "fibonacci_levels": [0.236, 0.382, 0.500, 0.618, 0.786, 1.000],
            },
            "session_config": {
                "european_session": (7, 16),  # UTC hours
                "snb_active_hours": (8, 15),  # Peak SNB activity
                "low_liquidity_hours": [(22, 24), (0, 6)],
            },
            "risk_config": {
                "max_signal_strength": 0.95,
                "min_signal_strength": 0.3,
                "volatility_adjustment": True,
                "correlation_filter": True,
            },
            "safe_haven_config": {
                "vix_thresholds": {"low": 15, "medium": 25, "high": 35},
                "gold_correlation_threshold": 0.3,
                "equity_correlation_threshold": -0.4,
            },
        }

    def generate_signals(
        self,
        data: pd.DataFrame,
        external_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> pd.DataFrame:
        """
        Generate comprehensive USD/CHF trading signals.

        Args:
            data: Main USD/CHF price data (OHLCV)
            external_data: External market data (gold, VIX, EUR/USD, etc.)

        Returns:
            DataFrame with signals, strength, and Swiss market analysis
        """
        try:
            if len(data) < 50:
                logger.warning("Insufficient data for USD/CHF signal generation")
                return pd.DataFrame()

            logger.info(f"Generating USD/CHF signals for {len(data)} data points")

            # Update market context
            self._update_market_context(data, external_data)

            # Generate comprehensive features
            features = self._generate_comprehensive_features(data, external_data)

            # Multi-component signal generation
            signals_df = pd.DataFrame(index=data.index)

            # 1. Technical analysis signals
            technical_signals = self._generate_technical_signals(data, features)

            # 2. Swiss National Bank analysis
            snb_signals = self._generate_snb_signals(data, features)

            # 3. Safe-haven flow analysis
            safe_haven_signals = self._generate_safe_haven_signals(
                data, features, external_data
            )

            # 4. Session-based analysis
            session_signals = self._generate_session_signals(data, features)

            # 5. Elliott Wave analysis
            wave_signals = self._generate_elliott_wave_signals(data)

            # 6. Cross-asset correlation signals
            correlation_signals = self._generate_correlation_signals(
                data, external_data
            )

            # 7. ML-based prediction
            ml_signals = self._generate_ml_signals(features)

            # Combine all signal components
            final_signals = self._combine_all_signals(
                data,
                technical_signals,
                snb_signals,
                safe_haven_signals,
                session_signals,
                wave_signals,
                correlation_signals,
                ml_signals,
            )

            # Apply final filters and adjustments
            filtered_signals = self._apply_final_filters(final_signals, data)

            logger.info(f"Generated {len(filtered_signals)} USD/CHF signals")
            return filtered_signals

        except Exception as e:
            logger.error(f"Error in USD/CHF signal generation: {e}")
            return pd.DataFrame()

    def _update_market_context(
        self,
        data: pd.DataFrame,
        external_data: Optional[Dict[str, pd.DataFrame]] = None,
    ):
        """Update current market context for USD/CHF."""
        try:
            current_price = data["close"].iloc[-1]

            # Update SNB intervention risk
            self.current_context.snb_intervention_risk = self._assess_snb_risk(
                current_price
            )

            # Update parity proximity
            self.current_context.parity_proximity = abs(current_price - 1.0000) / 1.0000

            # Update session status
            current_hour = datetime.utcnow().hour
            session_start, session_end = self.config["session_config"][
                "european_session"
            ]
            self.current_context.european_session_active = (
                session_start <= current_hour <= session_end
            )

            # Update volatility regime
            if len(data) >= 20:
                recent_volatility = data["close"].pct_change().rolling(
                    20
                ).std() * np.sqrt(252)
                vol_percentile = recent_volatility.rolling(60).rank(pct=True).iloc[-1]

                if vol_percentile > 0.8:
                    self.current_context.volatility_regime = "high"
                elif vol_percentile < 0.3:
                    self.current_context.volatility_regime = "low"
                else:
                    self.current_context.volatility_regime = "normal"

            # Update cross-asset momentum
            if external_data:
                for asset, asset_data in external_data.items():
                    if len(asset_data) > 0:
                        momentum = (
                            asset_data["close"].pct_change(5).iloc[-1]
                            if "close" in asset_data
                            else 0
                        )
                        self.current_context.cross_asset_momentum[asset] = momentum

            logger.debug(f"Updated USD/CHF market context: {self.current_context}")

        except Exception as e:
            logger.warning(f"Error updating market context: {e}")

    def _assess_snb_risk(self, current_price: float) -> str:
        """Assess SNB intervention risk based on price levels."""
        all_levels = (
            self.snb_levels["strong_support"]
            + self.snb_levels["strong_resistance"]
            + [1.0000]  # Parity level
        )

        min_distance = min([abs(current_price - level) / level for level in all_levels])

        if min_distance < 0.005:  # Within 0.5%
            return "extreme"
        elif min_distance < 0.01:  # Within 1%
            return "high"
        elif min_distance < 0.02:  # Within 2%
            return "medium"
        else:
            return "low"

    def _generate_comprehensive_features(
        self,
        data: pd.DataFrame,
        external_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> pd.DataFrame:
        """Generate comprehensive features for USD/CHF analysis."""
        features = pd.DataFrame(index=data.index)

        # Basic technical features
        features = self.feature_engineer.add_technical_indicators(features, data)

        # Swiss-specific features
        features["swiss_session"] = self._calculate_session_indicator(data.index)
        features["snb_proximity"] = self._calculate_snb_proximity(data["close"])
        features["parity_distance"] = abs(data["close"] - 1.0000) / 1.0000

        # Safe-haven features
        features["volatility_surge"] = self._detect_volatility_surge(data)
        features["volume_anomaly"] = self._detect_volume_anomaly(data)
        features["price_gap"] = data["open"] - data["close"].shift(1)

        # Cross-asset features (if available)
        if external_data:
            features = self._add_cross_asset_features(features, external_data)

        # Time-based features
        features["hour_of_day"] = [t.hour for t in pd.to_datetime(data.index)]
        features["day_of_week"] = [t.dayofweek for t in pd.to_datetime(data.index)]

        return features

    def _calculate_session_indicator(self, timestamps) -> pd.Series:
        """Calculate Swiss/European session indicator."""
        session_indicator = pd.Series(0.0, index=timestamps)

        for timestamp in timestamps:
            hour = (
                timestamp.hour
                if hasattr(timestamp, "hour")
                else pd.to_datetime(timestamp).hour
            )

            # European session
            if 7 <= hour <= 16:
                session_indicator[timestamp] = 1.0
            # SNB peak hours
            if 8 <= hour <= 15:
                session_indicator[timestamp] = 1.2
            # Overlap periods
            elif 12 <= hour <= 16:  # EU-US overlap
                session_indicator[timestamp] = 1.1
            # Low liquidity
            elif 22 <= hour <= 6:
                session_indicator[timestamp] = 0.3

        return session_indicator

    def _calculate_snb_proximity(self, prices: pd.Series) -> pd.Series:
        """Calculate proximity to SNB intervention levels."""
        proximity = pd.Series(0.0, index=prices.index)

        all_levels = (
            self.snb_levels["strong_support"]
            + self.snb_levels["strong_resistance"]
            + [1.0000]
        )

        for timestamp, price in prices.items():
            distances = [abs(price - level) / level for level in all_levels]
            min_distance = min(distances)

            # Convert distance to proximity score (closer = higher score)
            proximity[timestamp] = max(0, 1 - min_distance * 50)  # Scale factor

        return proximity

    def _detect_volatility_surge(self, data: pd.DataFrame) -> pd.Series:
        """Detect volatility surges that might indicate safe-haven flows."""
        returns = data["close"].pct_change()
        rolling_vol = returns.rolling(20).std() * np.sqrt(252)
        vol_threshold = rolling_vol.rolling(60).quantile(0.8)

        return (rolling_vol > vol_threshold).astype(float)

    def _detect_volume_anomaly(self, data: pd.DataFrame) -> pd.Series:
        """Detect volume anomalies."""
        if "volume" not in data.columns:
            return pd.Series(0.0, index=data.index)

        volume_ma = data["volume"].rolling(20).mean()
        volume_std = data["volume"].rolling(20).std()
        volume_threshold = volume_ma + 2 * volume_std

        return (data["volume"] > volume_threshold).astype(float)

    def _add_cross_asset_features(
        self, features: pd.DataFrame, external_data: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """Add cross-asset correlation features."""

        # Gold correlation (safe-haven)
        if "gold" in external_data and "close" in external_data["gold"]:
            gold_returns = external_data["gold"]["close"].pct_change()
            features["gold_momentum"] = gold_returns.rolling(5).mean()
            features["gold_volatility"] = gold_returns.rolling(10).std()

        # VIX (market fear)
        if "vix" in external_data and "close" in external_data["vix"]:
            vix_values = external_data["vix"]["close"]
            features["vix_level"] = vix_values
            features["vix_change"] = vix_values.pct_change()

        # EUR/USD correlation
        if "eurusd" in external_data and "close" in external_data["eurusd"]:
            eur_returns = external_data["eurusd"]["close"].pct_change()
            features["eur_momentum"] = eur_returns.rolling(5).mean()

        # S&P 500 (risk sentiment)
        if "spx" in external_data and "close" in external_data["spx"]:
            spx_returns = external_data["spx"]["close"].pct_change()
            features["equity_momentum"] = spx_returns.rolling(5).mean()

        return features

    def _generate_technical_signals(
        self, data: pd.DataFrame, features: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate technical analysis signals."""
        signals = pd.DataFrame(index=data.index)

        # Moving average signals
        ma_fast = data["close"].rolling(10).mean()
        ma_slow = data["close"].rolling(30).mean()
        signals["ma_signal"] = np.where(ma_fast > ma_slow, 1, -1)
        signals["ma_strength"] = abs(ma_fast - ma_slow) / ma_slow

        # RSI signals
        if "rsi_14" in features:
            signals["rsi_signal"] = np.where(
                features["rsi_14"] < 30, 1, np.where(features["rsi_14"] > 70, -1, 0)
            )
            signals["rsi_strength"] = np.where(
                features["rsi_14"] < 30,
                (30 - features["rsi_14"]) / 30,
                np.where(features["rsi_14"] > 70, (features["rsi_14"] - 70) / 30, 0),
            )

        # MACD signals
        if "macd_signal" in features:
            signals["macd_signal"] = np.where(features["macd_signal"] > 0, 1, -1)
            signals["macd_strength"] = abs(features["macd_signal"]) / data["close"]

        return signals

    def _generate_snb_signals(
        self, data: pd.DataFrame, features: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate SNB-specific signals."""
        signals = pd.DataFrame(index=data.index)
        current_price = data["close"]

        # Initialize
        signals["snb_signal"] = 0
        signals["snb_strength"] = 0.0
        signals["intervention_risk"] = "low"

        # Check support levels
        for level in self.snb_levels["strong_support"]:
            near_support = abs(current_price - level) / level < 0.02
            signals.loc[near_support, "snb_signal"] = 1  # Buy near support
            signals.loc[near_support, "snb_strength"] = 0.8
            signals.loc[near_support, "intervention_risk"] = "high"

        # Check resistance levels
        for level in self.snb_levels["strong_resistance"]:
            near_resistance = abs(current_price - level) / level < 0.02
            signals.loc[near_resistance, "snb_signal"] = -1  # Sell near resistance
            signals.loc[near_resistance, "snb_strength"] = 0.8
            signals.loc[near_resistance, "intervention_risk"] = "high"

        # Parity level special handling
        parity_distance = abs(current_price - 1.0000) / 1.0000
        extreme_parity = parity_distance < 0.01
        signals.loc[extreme_parity, "intervention_risk"] = "extreme"
        signals.loc[extreme_parity, "snb_strength"] = 0.9

        return signals

    def _generate_safe_haven_signals(
        self,
        data: pd.DataFrame,
        features: pd.DataFrame,
        external_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> pd.DataFrame:
        """Generate safe-haven flow signals."""
        signals = pd.DataFrame(index=data.index)
        signals["safe_haven_signal"] = 0
        signals["safe_haven_strength"] = 0.0

        # Volatility-based safe haven
        if "volatility_surge" in features:
            vol_surge = features["volatility_surge"] > 0
            signals.loc[vol_surge, "safe_haven_signal"] = (
                -1
            )  # CHF strengthens (USD/CHF falls)
            signals.loc[vol_surge, "safe_haven_strength"] = 0.6

        # VIX-based safe haven
        if external_data and "vix" in external_data:
            vix_data = external_data["vix"]
            if len(vix_data) > 0:
                high_vix = vix_data["close"] > 25
                signals.loc[high_vix, "safe_haven_signal"] = -1
                signals.loc[high_vix, "safe_haven_strength"] = np.minimum(
                    (vix_data["close"] - 25) / 25, 0.8
                )

        # Risk-off conditions
        volume_spike = features.get("volume_anomaly", 0) > 0
        price_gap = abs(features.get("price_gap", 0)) > data["close"] * 0.005

        risk_off = volume_spike & price_gap
        signals.loc[risk_off, "safe_haven_signal"] = -1
        signals.loc[risk_off, "safe_haven_strength"] = 0.5

        return signals

    def _generate_session_signals(
        self, data: pd.DataFrame, features: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate session-based trading signals."""
        signals = pd.DataFrame(index=data.index)

        # Session momentum
        session_active = features["swiss_session"] > 1.0
        price_momentum = data["close"].pct_change(3).rolling(3).mean()

        signals["session_signal"] = 0
        signals["session_strength"] = 0.0

        # Strong signals during Swiss session
        strong_momentum = abs(price_momentum) > 0.002
        session_signals = session_active & strong_momentum

        signals.loc[session_signals & (price_momentum > 0), "session_signal"] = 1
        signals.loc[session_signals & (price_momentum < 0), "session_signal"] = -1
        signals.loc[session_signals, "session_strength"] = np.minimum(
            abs(price_momentum) * 200 + features["swiss_session"] * 0.2, 1.0
        )

        return signals

    def _generate_elliott_wave_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate Elliott Wave-based signals."""
        signals = pd.DataFrame(index=data.index)
        signals["wave_signal"] = 0
        signals["wave_strength"] = 0.0
        signals["wave_position"] = "unknown"

        try:
            wave_analysis = self.elliott_wave.analyze_waves(data)

            if wave_analysis and "current_wave" in wave_analysis:
                current_wave = wave_analysis["current_wave"]
                wave_confidence = wave_analysis.get("confidence", 0.5)
                trend_direction = wave_analysis.get("trend_direction", "neutral")

                # Generate signals based on wave position
                if current_wave in ["wave_3", "wave_5"] and wave_confidence > 0.6:
                    if trend_direction == "bullish":
                        signals["wave_signal"] = 1
                    elif trend_direction == "bearish":
                        signals["wave_signal"] = -1

                    signals["wave_strength"] = wave_confidence

                signals["wave_position"] = current_wave

        except Exception as e:
            logger.warning(f"Elliott Wave analysis error: {e}")

        return signals

    def _generate_correlation_signals(
        self,
        data: pd.DataFrame,
        external_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> pd.DataFrame:
        """Generate cross-asset correlation signals."""
        signals = pd.DataFrame(index=data.index)
        signals["correlation_signal"] = 0
        signals["correlation_strength"] = 0.0

        if not external_data:
            return signals

        usd_chf_returns = data["close"].pct_change()

        total_signal = pd.Series(0.0, index=data.index)
        total_strength = pd.Series(0.0, index=data.index)

        # Gold correlation analysis
        if "gold" in external_data:
            gold_returns = external_data["gold"]["close"].pct_change()
            correlation = usd_chf_returns.rolling(20).corr(gold_returns)

            # CHF often moves with gold (both safe havens)
            gold_momentum = gold_returns.rolling(3).mean()
            correlation_signal = np.where(correlation > 0.3, np.sign(gold_momentum), 0)

            total_signal += correlation_signal * 0.3
            total_strength += abs(correlation) * 0.3

        # EUR/USD correlation
        if "eurusd" in external_data:
            eur_returns = external_data["eurusd"]["close"].pct_change()
            eur_correlation = usd_chf_returns.rolling(20).corr(eur_returns)

            # Both European currencies, often correlated
            eur_momentum = eur_returns.rolling(3).mean()
            eur_signal = np.where(
                abs(eur_correlation) > 0.4, np.sign(eur_momentum * eur_correlation), 0
            )

            total_signal += eur_signal * 0.4
            total_strength += abs(eur_correlation) * 0.4

        # Equity market correlation (risk sentiment)
        if "spx" in external_data:
            spx_returns = external_data["spx"]["close"].pct_change()
            spx_correlation = usd_chf_returns.rolling(20).corr(spx_returns)

            # USD/CHF often inversely correlated with risk assets
            spx_momentum = spx_returns.rolling(3).mean()
            risk_signal = np.where(spx_correlation < -0.3, -np.sign(spx_momentum), 0)

            total_signal += risk_signal * 0.3
            total_strength += abs(spx_correlation) * 0.3

        signals["correlation_signal"] = np.clip(total_signal, -1, 1)
        signals["correlation_strength"] = np.clip(total_strength, 0, 1)

        return signals

    def _generate_ml_signals(self, features: pd.DataFrame) -> pd.DataFrame:
        """Generate ML-based prediction signals."""
        signals = pd.DataFrame(index=features.index)
        signals["ml_signal"] = 0
        signals["ml_strength"] = 0.0
        signals["ml_confidence"] = 0.0

        try:
            # Select ML features
            ml_feature_cols = [
                col for col in self.config["ml_features"] if col in features.columns
            ]

            if len(ml_feature_cols) > 5 and len(features) > 50:
                ml_features = features[ml_feature_cols].fillna(0)

                # Generate ML predictions
                predictions = self.signal_model.predict_signals(ml_features)

                if predictions is not None and len(predictions) > 0:
                    signals["ml_signal"] = predictions.get("signal", 0)
                    signals["ml_strength"] = predictions.get("strength", 0)
                    signals["ml_confidence"] = predictions.get("confidence", 0)

        except Exception as e:
            logger.warning(f"ML signal generation error: {e}")

        return signals

    def _combine_all_signals(
        self,
        data: pd.DataFrame,
        technical_signals: pd.DataFrame,
        snb_signals: pd.DataFrame,
        safe_haven_signals: pd.DataFrame,
        session_signals: pd.DataFrame,
        wave_signals: pd.DataFrame,
        correlation_signals: pd.DataFrame,
        ml_signals: pd.DataFrame,
    ) -> pd.DataFrame:
        """Combine all signal components with appropriate weighting."""

        combined_signals = pd.DataFrame(index=data.index)

        # Define component weights
        weights = {
            "technical": 0.20,
            "snb": 0.25,
            "safe_haven": 0.20,
            "session": 0.15,
            "wave": 0.10,
            "correlation": 0.05,
            "ml": 0.05,
        }

        # Combine signals
        total_signal = pd.Series(0.0, index=data.index)
        total_strength = pd.Series(0.0, index=data.index)

        signal_components = [
            (technical_signals, "technical"),
            (snb_signals, "snb"),
            (safe_haven_signals, "safe_haven"),
            (session_signals, "session"),
            (wave_signals, "wave"),
            (correlation_signals, "correlation"),
            (ml_signals, "ml"),
        ]

        for signals_df, component_name in signal_components:
            weight = weights[component_name]
            signal_col = f"{component_name}_signal"
            strength_col = f"{component_name}_strength"

            if signal_col in signals_df.columns:
                component_signal = signals_df[signal_col].fillna(0)
                total_signal += component_signal * weight

            if strength_col in signals_df.columns:
                component_strength = signals_df[strength_col].fillna(0)
                total_strength += component_strength * weight

        # Generate final signals
        combined_signals["signal"] = np.where(
            total_signal > 0.15, 1, np.where(total_signal < -0.15, -1, 0)
        )

        combined_signals["strength"] = np.clip(total_strength, 0, 1)
        combined_signals["raw_signal"] = total_signal

        # Add market context information
        combined_signals["snb_risk"] = self.current_context.snb_intervention_risk
        combined_signals["safe_haven_demand"] = self.current_context.safe_haven_demand
        combined_signals["session_active"] = (
            self.current_context.european_session_active
        )
        combined_signals["volatility_regime"] = self.current_context.volatility_regime

        return combined_signals

    def _apply_final_filters(
        self, signals: pd.DataFrame, data: pd.DataFrame
    ) -> pd.DataFrame:
        """Apply final filters and risk adjustments."""
        filtered_signals = signals.copy()

        # Filter weak signals
        min_strength = self.config["risk_config"]["min_signal_strength"]
        weak_signals = filtered_signals["strength"] < min_strength
        filtered_signals.loc[weak_signals, "signal"] = 0

        # SNB risk adjustment
        extreme_snb_risk = filtered_signals["snb_risk"] == "extreme"
        filtered_signals.loc[extreme_snb_risk, "signal"] = 0  # No trading

        high_snb_risk = filtered_signals["snb_risk"] == "high"
        filtered_signals.loc[high_snb_risk, "strength"] *= 0.6  # Reduce strength

        # Volatility adjustment
        if self.config["risk_config"]["volatility_adjustment"]:
            high_vol = filtered_signals["volatility_regime"] == "high"
            filtered_signals.loc[high_vol, "strength"] *= 0.8

            low_vol = filtered_signals["volatility_regime"] == "low"
            filtered_signals.loc[low_vol, "strength"] *= 1.2

        # Session adjustment
        non_session = ~filtered_signals["session_active"]
        filtered_signals.loc[non_session, "strength"] *= 0.7

        # Final strength clipping
        max_strength = self.config["risk_config"]["max_signal_strength"]
        filtered_signals["strength"] = np.clip(
            filtered_signals["strength"], 0, max_strength
        )

        return filtered_signals

    def get_signal_summary(self) -> Dict[str, Any]:
        """Get current signal generation summary."""
        return {
            "generator": "USDCHFSignalGenerator",
            "market_context": {
                "snb_risk": self.current_context.snb_intervention_risk,
                "safe_haven_demand": self.current_context.safe_haven_demand,
                "session_active": self.current_context.european_session_active,
                "volatility_regime": self.current_context.volatility_regime,
                "parity_proximity": self.current_context.parity_proximity,
            },
            "signal_history_count": len(self.signal_history),
            "last_update": datetime.utcnow().isoformat(),
        }


# Factory function for easy instantiation
def create_usdchf_signal_generator(
    config: Optional[Dict[str, Any]] = None
) -> USDCHFSignalGenerator:
    """
    Factory function to create USD/CHF signal generator.

    Args:
        config: Optional configuration parameters

    Returns:
        Configured USDCHFSignalGenerator instance
    """
    return USDCHFSignalGenerator(config=config)
