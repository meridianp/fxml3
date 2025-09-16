"""
EUR/USD Signal Generator Implementation.

This module provides specialized signal generation for EUR/USD trading,
incorporating European Central Bank policy analysis, Federal Reserve correlation,
and EUR/USD specific market microstructure patterns.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..data_engineering.feature_engineering import FeatureEngineer
from ..wave_analysis.elliott_wave_detector import ElliottWaveDetector
from .signals import SignalGenerator
from .technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class EURUSDSignalGenerator(SignalGenerator):
    """
    EUR/USD specialized signal generator.

    Features:
    - ECB policy impact analysis
    - Federal Reserve correlation patterns
    - European trading session optimization
    - EUR/USD volatility clustering patterns
    - Cross-asset correlation with European indices
    """

    def __init__(
        self, lookback_period: int = 100, confidence_threshold: float = 0.65, **kwargs
    ):
        """
        Initialize EUR/USD signal generator.

        Args:
            lookback_period: Historical data lookback for analysis
            confidence_threshold: Minimum confidence for signal generation
            **kwargs: Additional configuration parameters
        """
        super().__init__(
            symbol="EURUSD",
            lookback_period=lookback_period,
            confidence_threshold=confidence_threshold,
            **kwargs,
        )

        # EUR/USD specific configuration
        self.config = {
            # Trading sessions (UTC)
            "european_session": {"start": 7, "end": 16},
            "us_session": {"start": 12, "end": 21},
            "overlap_session": {"start": 12, "end": 16},
            # Volatility parameters
            "volatility_threshold": 0.0015,  # 15 pips
            "high_volatility_threshold": 0.0030,  # 30 pips
            "volatility_lookback": 20,
            # ECB/Fed policy parameters
            "policy_impact_duration": 24,  # hours
            "policy_volatility_multiplier": 1.5,
            # Technical parameters
            "rsi_period": 14,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "bollinger_period": 20,
            "atr_period": 14,
            # Elliott Wave parameters
            "wave_min_confidence": 0.6,
            "fibonacci_tolerance": 0.0020,  # 20 pips
            # News impact parameters
            "high_impact_buffer": 2,  # hours before/after
            "medium_impact_buffer": 1,  # hours before/after
        }

        self.config.update(kwargs)

        # Initialize components
        self.technical = TechnicalIndicators()
        self.wave_detector = ElliottWaveDetector()
        self.feature_engineer = FeatureEngineer()

        # EUR/USD specific state
        self.last_ecb_event = None
        self.last_fed_event = None
        self.current_session = "unknown"
        self.volatility_regime = "normal"

        logger.info("Initialized EUR/USD signal generator")

    def generate_signals(
        self, data: pd.DataFrame, features: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Generate EUR/USD trading signals.

        Args:
            data: OHLCV price data for EUR/USD
            features: Pre-computed features (optional)

        Returns:
            Dictionary containing signals and metadata
        """
        try:
            if data.empty or len(data) < self.lookback_period:
                logger.warning("Insufficient data for EUR/USD signal generation")
                return self._empty_signal_result()

            logger.info(
                f"Generating EUR/USD signals for period ending {data.index[-1]}"
            )

            # Step 1: Market session and regime analysis
            session_analysis = self._analyze_market_session(data)
            volatility_regime = self._analyze_volatility_regime(data)

            # Step 2: Technical analysis
            technical_signals = self._generate_technical_signals(data)

            # Step 3: Elliott Wave analysis
            wave_analysis = self._analyze_elliott_waves(data)

            # Step 4: Policy impact analysis
            policy_impact = self._analyze_policy_impact(data)

            # Step 5: Cross-asset correlation analysis
            correlation_signals = self._analyze_cross_asset_correlation(data)

            # Step 6: Generate features if not provided
            if features is None:
                features = self._generate_features(data)

            # Step 7: Combine all signals
            combined_signal = self._combine_signals(
                technical_signals,
                wave_analysis,
                policy_impact,
                correlation_signals,
                session_analysis,
                volatility_regime,
            )

            # Step 8: Risk assessment
            risk_assessment = self._assess_risk(
                data, combined_signal, volatility_regime
            )

            # Step 9: Final signal generation
            final_signal = self._finalize_signal(
                combined_signal, risk_assessment, session_analysis
            )

            result = {
                "signal": final_signal,
                "confidence": combined_signal.get("confidence", 0),
                "metadata": {
                    "symbol": "EURUSD",
                    "timestamp": data.index[-1],
                    "session": session_analysis,
                    "volatility_regime": volatility_regime,
                    "technical_signals": technical_signals,
                    "wave_analysis": wave_analysis,
                    "policy_impact": policy_impact,
                    "risk_assessment": risk_assessment,
                    "features": (
                        features.iloc[-1].to_dict() if not features.empty else {}
                    ),
                },
            }

            logger.info(
                f"Generated EUR/USD signal: {final_signal} (confidence: {combined_signal.get('confidence', 0):.2f})"
            )

            return result

        except Exception as e:
            logger.error(f"Error generating EUR/USD signals: {str(e)}")
            return self._empty_signal_result()

    def _analyze_market_session(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze current EUR/USD trading session."""
        try:
            current_time = data.index[-1]

            # Convert to UTC if needed
            if hasattr(current_time, "tz_convert"):
                utc_time = current_time.tz_convert("UTC")
            else:
                utc_time = current_time

            hour = utc_time.hour if hasattr(utc_time, "hour") else 12

            # Determine session
            european_active = (
                self.config["european_session"]["start"]
                <= hour
                < self.config["european_session"]["end"]
            )
            us_active = (
                self.config["us_session"]["start"]
                <= hour
                < self.config["us_session"]["end"]
            )
            overlap_active = (
                self.config["overlap_session"]["start"]
                <= hour
                < self.config["overlap_session"]["end"]
            )

            if overlap_active:
                session = "overlap"
                liquidity = "high"
                volatility_expectation = "high"
            elif european_active:
                session = "european"
                liquidity = "medium"
                volatility_expectation = "medium"
            elif us_active:
                session = "us"
                liquidity = "medium"
                volatility_expectation = "medium"
            else:
                session = "asian"
                liquidity = "low"
                volatility_expectation = "low"

            # Calculate session-specific metrics
            session_volume = (
                data["volume"].iloc[-20:].mean() if "volume" in data.columns else 0
            )
            session_volatility = (data["high"] - data["low"]).iloc[-20:].mean()

            return {
                "current_session": session,
                "liquidity": liquidity,
                "volatility_expectation": volatility_expectation,
                "session_volume": session_volume,
                "session_volatility": session_volatility,
                "hour_utc": hour,
                "is_optimal_trading_time": overlap_active or european_active,
            }

        except Exception as e:
            logger.error(f"Error analyzing EUR/USD market session: {str(e)}")
            return {
                "current_session": "unknown",
                "liquidity": "medium",
                "volatility_expectation": "medium",
                "is_optimal_trading_time": True,
            }

    def _analyze_volatility_regime(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze EUR/USD volatility regime."""
        try:
            # Calculate ATR-based volatility
            atr = self.technical.calculate_atr(data, period=self.config["atr_period"])
            current_atr = atr.iloc[-1] if not atr.empty else 0

            # Historical percentile
            lookback = self.config["volatility_lookback"] * 5  # 100 periods
            atr_percentile = (
                atr.iloc[-lookback:].rank(pct=True).iloc[-1]
                if len(atr) >= lookback
                else 0.5
            )

            # Classify regime
            if current_atr > self.config["high_volatility_threshold"]:
                regime = "high"
                trading_adjustment = 0.7  # Reduce position size
            elif current_atr > self.config["volatility_threshold"]:
                regime = "medium"
                trading_adjustment = 1.0  # Normal position size
            else:
                regime = "low"
                trading_adjustment = 0.8  # Slightly reduce due to low volatility

            # Volatility clustering analysis
            vol_changes = atr.diff().iloc[-10:]
            volatility_trend = "increasing" if vol_changes.mean() > 0 else "decreasing"

            return {
                "regime": regime,
                "current_atr": current_atr,
                "atr_percentile": atr_percentile,
                "volatility_trend": volatility_trend,
                "trading_adjustment": trading_adjustment,
                "risk_multiplier": 1.0 / trading_adjustment,
            }

        except Exception as e:
            logger.error(f"Error analyzing EUR/USD volatility regime: {str(e)}")
            return {
                "regime": "medium",
                "trading_adjustment": 1.0,
                "risk_multiplier": 1.0,
            }

    def _generate_technical_signals(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Generate technical analysis signals for EUR/USD."""
        try:
            signals = {}

            # RSI analysis
            rsi = self.technical.calculate_rsi(data["close"], self.config["rsi_period"])
            signals["rsi"] = {
                "value": rsi.iloc[-1] if not rsi.empty else 50,
                "signal": self._interpret_rsi(rsi.iloc[-1] if not rsi.empty else 50),
                "strength": abs(rsi.iloc[-1] - 50) / 50 if not rsi.empty else 0,
            }

            # MACD analysis
            macd_line, macd_signal, macd_histogram = self.technical.calculate_macd(
                data["close"],
                fast=self.config["macd_fast"],
                slow=self.config["macd_slow"],
                signal=self.config["macd_signal"],
            )

            signals["macd"] = {
                "line": macd_line.iloc[-1] if not macd_line.empty else 0,
                "signal_line": macd_signal.iloc[-1] if not macd_signal.empty else 0,
                "histogram": macd_histogram.iloc[-1] if not macd_histogram.empty else 0,
                "signal": self._interpret_macd(macd_line, macd_signal, macd_histogram),
                "strength": (
                    abs(macd_histogram.iloc[-1]) if not macd_histogram.empty else 0
                ),
            }

            # Bollinger Bands analysis
            bb_upper, bb_middle, bb_lower = self.technical.calculate_bollinger_bands(
                data["close"], period=self.config["bollinger_period"]
            )

            current_price = data["close"].iloc[-1]
            bb_position = (
                (current_price - bb_lower.iloc[-1])
                / (bb_upper.iloc[-1] - bb_lower.iloc[-1])
                if not bb_upper.empty and bb_upper.iloc[-1] != bb_lower.iloc[-1]
                else 0.5
            )

            signals["bollinger"] = {
                "position": bb_position,
                "signal": self._interpret_bollinger(bb_position),
                "strength": abs(bb_position - 0.5) * 2,
                "squeeze": (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1]
                < 0.02,
            }

            # Support/Resistance levels
            sr_levels = self._identify_support_resistance(data)
            signals["support_resistance"] = sr_levels

            # Trend analysis
            trend_analysis = self._analyze_trend(data)
            signals["trend"] = trend_analysis

            # Combine technical signals
            technical_score = self._combine_technical_signals(signals)

            return {
                "individual_signals": signals,
                "combined_score": technical_score,
                "overall_signal": np.sign(technical_score),
                "strength": abs(technical_score),
            }

        except Exception as e:
            logger.error(f"Error generating EUR/USD technical signals: {str(e)}")
            return {"combined_score": 0, "overall_signal": 0, "strength": 0}

    def _analyze_elliott_waves(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze Elliott Wave patterns for EUR/USD."""
        try:
            # Detect Elliott Wave patterns
            wave_patterns = self.wave_detector.analyze_patterns(
                data, lookback_period=self.lookback_period
            )

            if not wave_patterns:
                return {
                    "pattern_detected": False,
                    "signal": 0,
                    "confidence": 0,
                    "wave_count": None,
                }

            # Get the most recent pattern
            current_pattern = wave_patterns[-1]
            confidence = current_pattern.get("confidence", 0)

            if confidence < self.config["wave_min_confidence"]:
                return {
                    "pattern_detected": True,
                    "signal": 0,
                    "confidence": confidence,
                    "wave_count": current_pattern.get("wave_count"),
                    "pattern_type": current_pattern.get("type"),
                    "reason": "Low confidence",
                }

            # Interpret wave pattern
            wave_signal = self._interpret_wave_pattern(current_pattern, data)

            # Fibonacci analysis
            fib_analysis = self._analyze_fibonacci_levels(data, current_pattern)

            return {
                "pattern_detected": True,
                "signal": wave_signal,
                "confidence": confidence,
                "wave_count": current_pattern.get("wave_count"),
                "pattern_type": current_pattern.get("type"),
                "fibonacci_analysis": fib_analysis,
                "target_levels": self._calculate_wave_targets(current_pattern, data),
            }

        except Exception as e:
            logger.error(f"Error analyzing EUR/USD Elliott Waves: {str(e)}")
            return {"pattern_detected": False, "signal": 0, "confidence": 0}

    def _analyze_policy_impact(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze ECB and Fed policy impact on EUR/USD."""
        try:
            current_time = data.index[-1]

            # This would typically integrate with economic calendar
            # For now, implement basic policy cycle awareness

            # Check for potential policy announcement periods
            policy_impact = {
                "ecb_impact": "neutral",
                "fed_impact": "neutral",
                "combined_impact": "neutral",
                "policy_uncertainty": 0.0,
            }

            # Month-end policy considerations (simplified)
            if hasattr(current_time, "day"):
                day_of_month = current_time.day

                # ECB meetings typically first Thursday of month
                if 1 <= day_of_month <= 7:
                    policy_impact["ecb_impact"] = "potential_announcement"
                    policy_impact["policy_uncertainty"] += 0.3

                # Fed meetings (8 times per year, roughly every 6-7 weeks)
                # This is simplified - real implementation would use actual calendar
                if day_of_month in [15, 16, 17]:  # Mid-month approximate
                    policy_impact["fed_impact"] = "potential_announcement"
                    policy_impact["policy_uncertainty"] += 0.3

            # Analyze recent volatility for policy impact signatures
            recent_vol = self._analyze_volatility_regime(data)
            if recent_vol["regime"] == "high":
                policy_impact["policy_uncertainty"] += 0.2

            # Combined impact assessment
            if policy_impact["policy_uncertainty"] > 0.4:
                policy_impact["combined_impact"] = "high_uncertainty"
            elif policy_impact["policy_uncertainty"] > 0.2:
                policy_impact["combined_impact"] = "moderate_uncertainty"

            return policy_impact

        except Exception as e:
            logger.error(f"Error analyzing EUR/USD policy impact: {str(e)}")
            return {
                "ecb_impact": "neutral",
                "fed_impact": "neutral",
                "combined_impact": "neutral",
                "policy_uncertainty": 0.0,
            }

    def _analyze_cross_asset_correlation(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze EUR/USD correlation with other assets."""
        try:
            # This would typically analyze correlation with:
            # - EUR/GBP, EUR/JPY for EUR strength
            # - USD/JPY, GBP/USD for USD strength
            # - German Bund yields, US Treasury yields
            # - European equity indices (DAX, STOXX50)

            # For now, implement basic cross-asset analysis using price action
            correlation_signals = {
                "eur_strength_indicator": 0.0,
                "usd_strength_indicator": 0.0,
                "risk_sentiment": "neutral",
                "yield_differential_impact": "neutral",
            }

            # Analyze recent price momentum as proxy for currency strength
            price_momentum = data["close"].pct_change(20).iloc[-1]  # 20-period momentum

            if price_momentum > 0.02:  # 2% appreciation
                correlation_signals["eur_strength_indicator"] = 1.0
                correlation_signals["usd_strength_indicator"] = -0.5
            elif price_momentum < -0.02:  # 2% depreciation
                correlation_signals["eur_strength_indicator"] = -1.0
                correlation_signals["usd_strength_indicator"] = 1.0

            # Risk sentiment analysis (simplified)
            volatility = self._analyze_volatility_regime(data)
            if volatility["regime"] == "high":
                correlation_signals["risk_sentiment"] = (
                    "risk_off"  # Typically USD positive
                )
            elif volatility["regime"] == "low":
                correlation_signals["risk_sentiment"] = (
                    "risk_on"  # Typically EUR positive
                )

            return correlation_signals

        except Exception as e:
            logger.error(f"Error analyzing EUR/USD cross-asset correlation: {str(e)}")
            return {
                "eur_strength_indicator": 0.0,
                "usd_strength_indicator": 0.0,
                "risk_sentiment": "neutral",
            }

    def _combine_signals(
        self,
        technical_signals: Dict,
        wave_analysis: Dict,
        policy_impact: Dict,
        correlation_signals: Dict,
        session_analysis: Dict,
        volatility_regime: Dict,
    ) -> Dict[str, Any]:
        """Combine all signal sources for EUR/USD."""
        try:
            # Signal weights (EUR/USD specific)
            weights = {
                "technical": 0.30,
                "elliott_wave": 0.35,
                "policy": 0.15,
                "correlation": 0.20,
            }

            # Base signals
            technical_score = technical_signals.get("combined_score", 0)
            wave_score = wave_analysis.get("signal", 0) * wave_analysis.get(
                "confidence", 0
            )

            # Policy adjustment
            policy_uncertainty = policy_impact.get("policy_uncertainty", 0)
            policy_adjustment = 1.0 - (
                policy_uncertainty * 0.5
            )  # Reduce signals during uncertainty

            # Correlation adjustment
            eur_strength = correlation_signals.get("eur_strength_indicator", 0)
            usd_strength = correlation_signals.get("usd_strength_indicator", 0)
            correlation_score = eur_strength - usd_strength  # Net EUR strength

            # Session adjustment
            session_multiplier = 1.0
            if session_analysis.get("is_optimal_trading_time", True):
                session_multiplier = 1.2
            elif session_analysis.get("current_session") == "asian":
                session_multiplier = 0.6  # Reduce signals during low liquidity

            # Volatility adjustment
            vol_adjustment = volatility_regime.get("trading_adjustment", 1.0)

            # Combined signal
            combined_score = (
                (
                    weights["technical"] * technical_score
                    + weights["elliott_wave"] * wave_score
                    + weights["correlation"] * correlation_score
                )
                * policy_adjustment
                * session_multiplier
                * vol_adjustment
            )

            # Calculate confidence
            individual_confidences = [
                technical_signals.get("strength", 0),
                wave_analysis.get("confidence", 0),
                abs(correlation_score),
                1.0 - policy_uncertainty,
            ]

            combined_confidence = np.mean(individual_confidences) * session_multiplier

            return {
                "signal": np.clip(combined_score, -1, 1),
                "confidence": np.clip(combined_confidence, 0, 1),
                "components": {
                    "technical": technical_score,
                    "elliott_wave": wave_score,
                    "correlation": correlation_score,
                    "policy_adjustment": policy_adjustment,
                    "session_multiplier": session_multiplier,
                    "volatility_adjustment": vol_adjustment,
                },
            }

        except Exception as e:
            logger.error(f"Error combining EUR/USD signals: {str(e)}")
            return {"signal": 0, "confidence": 0, "components": {}}

    # Helper methods for signal interpretation

    def _interpret_rsi(self, rsi_value: float) -> int:
        """Interpret RSI signal for EUR/USD."""
        if rsi_value < 30:
            return 1  # Oversold, buy signal
        elif rsi_value > 70:
            return -1  # Overbought, sell signal
        else:
            return 0  # Neutral

    def _interpret_macd(
        self, macd_line: pd.Series, macd_signal: pd.Series, macd_histogram: pd.Series
    ) -> int:
        """Interpret MACD signal for EUR/USD."""
        try:
            if macd_line.empty or macd_signal.empty or macd_histogram.empty:
                return 0

            current_macd = macd_line.iloc[-1]
            current_signal = macd_signal.iloc[-1]
            current_hist = macd_histogram.iloc[-1]

            # Bullish: MACD above signal line and histogram positive
            if current_macd > current_signal and current_hist > 0:
                return 1
            # Bearish: MACD below signal line and histogram negative
            elif current_macd < current_signal and current_hist < 0:
                return -1
            else:
                return 0

        except Exception:
            return 0

    def _interpret_bollinger(self, bb_position: float) -> int:
        """Interpret Bollinger Bands signal for EUR/USD."""
        if bb_position < 0.2:  # Near lower band
            return 1  # Mean reversion buy
        elif bb_position > 0.8:  # Near upper band
            return -1  # Mean reversion sell
        else:
            return 0  # Neutral

    def _identify_support_resistance(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Identify support and resistance levels for EUR/USD."""
        try:
            # EUR/USD psychological levels
            psychological_levels = [1.0000, 1.0500, 1.1000, 1.1500, 1.2000]
            current_price = data["close"].iloc[-1]

            # Find nearest levels
            distances = [abs(current_price - level) for level in psychological_levels]
            nearest_distance = min(distances)
            nearest_level = psychological_levels[distances.index(nearest_distance)]

            # Dynamic support/resistance from recent highs/lows
            recent_highs = data["high"].rolling(20).max()
            recent_lows = data["low"].rolling(20).min()

            return {
                "nearest_psychological_level": nearest_level,
                "distance_to_level": nearest_distance,
                "dynamic_resistance": recent_highs.iloc[-1],
                "dynamic_support": recent_lows.iloc[-1],
                "signal": self._sr_signal(
                    current_price, nearest_level, nearest_distance
                ),
            }

        except Exception as e:
            logger.error(f"Error identifying EUR/USD support/resistance: {str(e)}")
            return {"signal": 0}

    def _sr_signal(self, price: float, level: float, distance: float) -> int:
        """Generate signal based on support/resistance proximity."""
        if distance < 0.0050:  # Within 50 pips
            if price < level:
                return 1  # Buy near support
            else:
                return -1  # Sell near resistance
        return 0

    def _analyze_trend(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze EUR/USD trend."""
        try:
            # Multiple timeframe trend analysis
            ema_20 = data["close"].ewm(span=20).mean()
            ema_50 = data["close"].ewm(span=50).mean()

            current_price = data["close"].iloc[-1]

            # Trend determination
            if current_price > ema_20.iloc[-1] > ema_50.iloc[-1]:
                trend = "bullish"
                strength = min(
                    (current_price - ema_50.iloc[-1]) / ema_50.iloc[-1] * 100, 5
                )
            elif current_price < ema_20.iloc[-1] < ema_50.iloc[-1]:
                trend = "bearish"
                strength = min(
                    (ema_50.iloc[-1] - current_price) / ema_50.iloc[-1] * 100, 5
                )
            else:
                trend = "sideways"
                strength = 0

            return {
                "direction": trend,
                "strength": strength,
                "signal": (
                    1 if trend == "bullish" else (-1 if trend == "bearish" else 0)
                ),
            }

        except Exception as e:
            logger.error(f"Error analyzing EUR/USD trend: {str(e)}")
            return {"direction": "sideways", "strength": 0, "signal": 0}

    def _combine_technical_signals(self, signals: Dict) -> float:
        """Combine individual technical signals."""
        try:
            weights = {
                "rsi": 0.25,
                "macd": 0.30,
                "bollinger": 0.20,
                "trend": 0.15,
                "support_resistance": 0.10,
            }

            combined = 0.0
            for signal_type, weight in weights.items():
                if signal_type in signals:
                    signal_value = signals[signal_type].get("signal", 0)
                    strength = signals[signal_type].get("strength", 1)
                    combined += weight * signal_value * strength

            return np.clip(combined, -1, 1)

        except Exception as e:
            logger.error(f"Error combining EUR/USD technical signals: {str(e)}")
            return 0.0

    def _interpret_wave_pattern(
        self, pattern: Dict[str, Any], data: pd.DataFrame
    ) -> float:
        """Interpret Elliott Wave pattern for EUR/USD signals."""
        try:
            wave_type = pattern.get("type", "")
            wave_count = pattern.get("wave_count", 0)
            direction = pattern.get("direction", "neutral")

            if wave_type == "impulse":
                if wave_count in [1, 3, 5]:  # Impulse waves
                    signal = 1.0 if direction == "up" else -1.0
                elif wave_count in [2, 4]:  # Corrective waves
                    signal = -0.5 if direction == "up" else 0.5
                else:
                    signal = 0.0
            elif wave_type == "corrective":
                if wave_count == 1:  # Wave A
                    signal = -0.8 if direction == "down" else 0.8
                elif wave_count == 2:  # Wave B
                    signal = 0.3 if direction == "up" else -0.3
                elif wave_count == 3:  # Wave C
                    signal = -1.0 if direction == "down" else 1.0
                else:
                    signal = 0.0
            else:
                signal = 0.0

            return signal

        except Exception as e:
            logger.error(f"Error interpreting EUR/USD wave pattern: {str(e)}")
            return 0.0

    def _analyze_fibonacci_levels(
        self, data: pd.DataFrame, pattern: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze Fibonacci levels for EUR/USD."""
        try:
            current_price = data["close"].iloc[-1]
            pattern_high = pattern.get("high", current_price)
            pattern_low = pattern.get("low", current_price)

            if pattern_high <= pattern_low:
                return {"near_fibonacci": False, "level": None, "signal": 0}

            # Calculate Fibonacci retracement levels
            fib_range = pattern_high - pattern_low
            fib_levels = {
                0.236: pattern_high - 0.236 * fib_range,
                0.382: pattern_high - 0.382 * fib_range,
                0.500: pattern_high - 0.500 * fib_range,
                0.618: pattern_high - 0.618 * fib_range,
                0.786: pattern_high - 0.786 * fib_range,
            }

            # Check if near any Fibonacci level
            tolerance = self.config["fibonacci_tolerance"]

            for ratio, level in fib_levels.items():
                if abs(current_price - level) <= tolerance:
                    signal_strength = 1.5 if ratio in [0.382, 0.618] else 1.0
                    signal = (
                        signal_strength
                        if pattern.get("direction") == "up"
                        else -signal_strength
                    )

                    return {
                        "near_fibonacci": True,
                        "level": ratio,
                        "price_level": level,
                        "signal": signal,
                    }

            return {"near_fibonacci": False, "level": None, "signal": 0}

        except Exception as e:
            logger.error(f"Error analyzing EUR/USD Fibonacci levels: {str(e)}")
            return {"near_fibonacci": False, "level": None, "signal": 0}

    def _calculate_wave_targets(
        self, pattern: Dict[str, Any], data: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate Elliott Wave price targets for EUR/USD."""
        try:
            current_price = data["close"].iloc[-1]
            pattern_high = pattern.get("high", current_price)
            pattern_low = pattern.get("low", current_price)

            if pattern_high <= pattern_low:
                return {}

            wave_range = pattern_high - pattern_low

            # Extension targets
            targets = {
                "target_1.272": pattern_high + 1.272 * wave_range,
                "target_1.618": pattern_high + 1.618 * wave_range,
                "target_2.000": pattern_high + 2.000 * wave_range,
            }

            # Adjust for direction
            if pattern.get("direction") == "down":
                targets = {
                    key: pattern_low - (value - pattern_high)
                    for key, value in targets.items()
                }

            return targets

        except Exception as e:
            logger.error(f"Error calculating EUR/USD wave targets: {str(e)}")
            return {}

    def _generate_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate EUR/USD specific features."""
        try:
            features = self.feature_engineer.create_features(
                data,
                lookback_periods=[5, 10, 20, 50],
                include_technical=True,
                include_statistical=True,
            )

            # Add EUR/USD specific features
            features["hour_utc"] = (
                data.index.hour if hasattr(data.index, "hour") else 12
            )
            features["is_european_session"] = (features["hour_utc"] >= 7) & (
                features["hour_utc"] < 16
            )
            features["is_overlap_session"] = (features["hour_utc"] >= 12) & (
                features["hour_utc"] < 16
            )

            return features

        except Exception as e:
            logger.error(f"Error generating EUR/USD features: {str(e)}")
            return pd.DataFrame()

    def _assess_risk(
        self,
        data: pd.DataFrame,
        signal: Dict[str, Any],
        volatility_regime: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assess trading risk for EUR/USD signals."""
        try:
            # Base risk assessment
            signal_strength = abs(signal.get("signal", 0))
            confidence = signal.get("confidence", 0)

            # Volatility risk
            vol_risk = volatility_regime.get("risk_multiplier", 1.0)

            # Session risk
            current_hour = (
                data.index[-1].hour if hasattr(data.index[-1], "hour") else 12
            )
            session_risk = (
                1.5 if current_hour < 7 or current_hour > 21 else 1.0
            )  # Asian session risk

            # Overall risk score
            risk_score = vol_risk * session_risk

            # Position sizing recommendation
            if risk_score > 2.0:
                position_size = 0.5  # Half size
                risk_level = "high"
            elif risk_score > 1.5:
                position_size = 0.75  # Three-quarter size
                risk_level = "medium"
            else:
                position_size = 1.0  # Full size
                risk_level = "low"

            return {
                "risk_level": risk_level,
                "risk_score": risk_score,
                "position_size_multiplier": position_size,
                "volatility_risk": vol_risk,
                "session_risk": session_risk,
                "recommended_stop_loss": self._calculate_stop_loss(
                    data, volatility_regime
                ),
            }

        except Exception as e:
            logger.error(f"Error assessing EUR/USD risk: {str(e)}")
            return {
                "risk_level": "medium",
                "risk_score": 1.0,
                "position_size_multiplier": 1.0,
            }

    def _calculate_stop_loss(
        self, data: pd.DataFrame, volatility_regime: Dict[str, Any]
    ) -> float:
        """Calculate appropriate stop loss for EUR/USD."""
        try:
            atr = self.technical.calculate_atr(data, period=14)
            current_atr = atr.iloc[-1] if not atr.empty else 0.0020  # Default 20 pips

            # Adjust for volatility regime
            vol_multiplier = volatility_regime.get("risk_multiplier", 1.0)

            # EUR/USD specific stop loss (typically 1.5-2.5x ATR)
            stop_loss_distance = current_atr * 2.0 * vol_multiplier

            return min(max(stop_loss_distance, 0.0015), 0.0050)  # 15-50 pips range

        except Exception as e:
            logger.error(f"Error calculating EUR/USD stop loss: {str(e)}")
            return 0.0020  # Default 20 pips

    def _finalize_signal(
        self,
        combined_signal: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        session_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Finalize EUR/USD trading signal."""
        try:
            base_signal = combined_signal.get("signal", 0)
            confidence = combined_signal.get("confidence", 0)

            # Apply minimum confidence threshold
            if confidence < self.confidence_threshold:
                return {
                    "action": "hold",
                    "direction": 0,
                    "strength": 0,
                    "confidence": confidence,
                    "reason": "Below confidence threshold",
                }

            # Apply risk-based position sizing
            position_multiplier = risk_assessment.get("position_size_multiplier", 1.0)

            # Determine final action
            if abs(base_signal) < 0.3:
                action = "hold"
                direction = 0
            elif base_signal > 0:
                action = "buy"
                direction = 1
            else:
                action = "sell"
                direction = -1

            strength = abs(base_signal) * position_multiplier

            return {
                "action": action,
                "direction": direction,
                "strength": strength,
                "confidence": confidence,
                "position_size_multiplier": position_multiplier,
                "stop_loss_distance": risk_assessment.get(
                    "recommended_stop_loss", 0.0020
                ),
                "take_profit_distance": risk_assessment.get(
                    "recommended_stop_loss", 0.0020
                )
                * 2,
                "optimal_session": session_analysis.get(
                    "is_optimal_trading_time", True
                ),
            }

        except Exception as e:
            logger.error(f"Error finalizing EUR/USD signal: {str(e)}")
            return {"action": "hold", "direction": 0, "strength": 0, "confidence": 0}

    def _empty_signal_result(self) -> Dict[str, Any]:
        """Return empty signal result."""
        return {
            "signal": {
                "action": "hold",
                "direction": 0,
                "strength": 0,
                "confidence": 0,
            },
            "confidence": 0,
            "metadata": {
                "symbol": "EURUSD",
                "error": "Insufficient data or processing error",
            },
        }
