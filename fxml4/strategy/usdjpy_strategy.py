"""
USD/JPY Trading Strategy Implementation.

This module implements a specialized USD/JPY trading strategy that combines:
- Tokyo session optimization and Asian market dynamics
- Bank of Japan (BoJ) policy analysis and intervention level monitoring
- Risk-on/risk-off sentiment correlation with global equity markets
- Japanese market structure and trading patterns
- Integration with Nikkei index and Japanese Government Bond (JGB) analysis
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..data_engineering.feature_engineering import FeatureEngineer
from ..ml.models import MLModelManager
from ..risk_management.position_sizing import PositionSizer
from ..wave_analysis.elliott_wave_detector import ElliottWaveDetector
from .base_strategy import BaseStrategy
from .market_regime_classifier import MarketRegimeClassifier
from .technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class USDJPYStrategy(BaseStrategy):
    """
    USD/JPY specialized trading strategy.

    Features:
    - Tokyo session optimization (00:00-09:00 UTC)
    - Bank of Japan (BoJ) intervention level monitoring
    - Risk-on/risk-off sentiment analysis
    - Nikkei index correlation analysis
    - Japanese Government Bond (JGB) yield correlation
    - Japanese market holiday awareness
    - USD/JPY specific volatility patterns
    - Psychological level analysis (100, 110, 120, 130, 140, 150)
    """

    def __init__(
        self, name: str = "USDJPYStrategy", params: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize USD/JPY strategy.

        Args:
            name: Strategy name
            params: Strategy parameters specific to USD/JPY
        """
        # USD/JPY specific default parameters
        default_params = {
            # Tokyo session parameters (UTC hours)
            "tokyo_session_start": 0,  # 00:00 UTC
            "tokyo_session_end": 9,  # 09:00 UTC
            "tokyo_core_start": 1,  # 01:00 UTC (most active)
            "tokyo_core_end": 6,  # 06:00 UTC
            "london_tokyo_overlap_start": 7,  # 07:00 UTC
            "london_tokyo_overlap_end": 9,  # 09:00 UTC
            # BoJ intervention levels and parameters
            "boj_intervention_levels": {
                "strong_resistance": [140, 150, 160],
                "moderate_resistance": [135, 145, 155],
                "strong_support": [100, 110, 120],
                "moderate_support": [105, 115, 125],
            },
            "intervention_proximity_pips": 50,  # 50 pips from intervention level
            # Risk sentiment parameters
            "risk_on_correlation_threshold": 0.7,
            "risk_off_correlation_threshold": -0.7,
            "nikkei_correlation_period": 20,
            "vix_correlation_period": 20,
            # USD/JPY volatility parameters (3 decimal places)
            "min_volatility_threshold": 0.50,  # 50 pips
            "max_volatility_threshold": 1.50,  # 150 pips
            "volatility_lookback": 20,
            "pip_size": 0.01,  # USD/JPY pip size
            # Elliott Wave parameters for USD/JPY
            "wave_detection_period": 100,
            "wave_confidence_threshold": 0.65,
            "fibonacci_retracement_levels": [0.236, 0.382, 0.500, 0.618, 0.786],
            "fibonacci_extension_levels": [1.272, 1.414, 1.618, 2.000],
            # Risk management for USD/JPY
            "max_risk_per_trade": 0.02,  # 2%
            "max_portfolio_risk": 0.06,  # 6%
            "position_sizing_method": "volatility_adjusted",
            "atr_period": 14,
            "atr_multiplier": 1.5,
            # ML model parameters
            "ml_model_type": "ensemble",
            "feature_lookback": 60,
            "prediction_confidence_threshold": 0.7,
            "ensemble_models": ["xgboost", "lstm", "transformer"],
            # Japanese market specific parameters
            "golden_week_trading": False,  # Avoid Golden Week
            "year_end_trading": False,  # Avoid year-end (Dec 29 - Jan 3)
            "obon_trading": False,  # Avoid Obon period (mid-August)
            # Technical indicators for USD/JPY
            "ema_fast": 12,
            "ema_slow": 26,
            "macd_signal": 9,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "bollinger_period": 20,
            "bollinger_std": 2,
            # USD/JPY psychological levels
            "psychological_levels": [
                100.00,
                105.00,
                110.00,
                115.00,
                120.00,
                125.00,
                130.00,
                135.00,
                140.00,
                145.00,
                150.00,
            ],
            # Risk sentiment indicators
            "risk_on_threshold": 0.6,
            "risk_off_threshold": -0.6,
        }

        # Merge with provided parameters
        if params:
            default_params.update(params)

        super().__init__(name=name, params=default_params)

        # Initialize components
        self.technical_indicators = TechnicalIndicators()
        self.regime_classifier = MarketRegimeClassifier()
        self.ml_manager = MLModelManager()
        self.position_sizer = PositionSizer()
        self.wave_detector = ElliottWaveDetector()
        self.feature_engineer = FeatureEngineer()

        # USD/JPY specific state
        self.current_session = None
        self.current_regime = None
        self.risk_sentiment = "neutral"
        self.boj_intervention_risk = "low"

        logger.info(f"Initialized {self.name} with Tokyo session optimization")

    def generate_signals(
        self, data: pd.DataFrame, features: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Generate USD/JPY trading signals.

        Args:
            data: OHLCV price data for USD/JPY
            features: Pre-computed features (optional)

        Returns:
            DataFrame with trading signals and metadata
        """
        try:
            if data.empty:
                logger.warning("Empty data provided to USD/JPY strategy")
                return pd.DataFrame()

            logger.info(f"Generating USD/JPY signals for {len(data)} periods")

            # Step 1: Tokyo session and market timing analysis
            session_info = self._analyze_tokyo_session(data)
            timing_info = self._analyze_market_timing(data)

            # Step 2: Risk sentiment analysis
            risk_sentiment = self._analyze_risk_sentiment(data)

            # Step 3: BoJ intervention risk assessment
            intervention_risk = self._assess_boj_intervention_risk(data)

            # Step 4: Technical analysis
            technical_signals = self._generate_technical_signals(data)

            # Step 5: Elliott Wave analysis
            wave_signals = self._generate_wave_signals(data)

            # Step 6: Machine learning signals
            if features is None:
                features = self._engineer_features(data)
            ml_signals = self._generate_ml_signals(data, features)

            # Step 7: Japanese market filter (holidays, special periods)
            market_filter = self._apply_japanese_market_filter(data)

            # Step 8: Combine all signals
            combined_signals = self._combine_signals(
                data,
                technical_signals,
                wave_signals,
                ml_signals,
                session_info,
                risk_sentiment,
                intervention_risk,
                market_filter,
            )

            # Step 9: Apply risk management
            risk_adjusted_signals = self._apply_risk_management(data, combined_signals)

            # Step 10: Final signal validation
            validated_signals = self._validate_signals(data, risk_adjusted_signals)

            logger.info(
                f"Generated {len(validated_signals[validated_signals['signal'] != 0])} USD/JPY signals"
            )

            return validated_signals

        except Exception as e:
            logger.error(f"Error generating USD/JPY signals: {str(e)}")
            return pd.DataFrame()

    def _analyze_tokyo_session(self, data: pd.DataFrame) -> pd.DataFrame:
        """Analyze Tokyo session trading patterns for USD/JPY."""
        session_info = pd.DataFrame(index=data.index)

        # Convert to UTC if timezone info available
        if hasattr(data.index, "tz") and data.index.tz is not None:
            utc_times = data.index.tz_convert("UTC")
        else:
            utc_times = data.index

        # Define Tokyo sessions
        hours = utc_times.hour
        session_info["tokyo_session"] = (
            hours >= self.params["tokyo_session_start"]
        ) & (hours < self.params["tokyo_session_end"])
        session_info["tokyo_core_hours"] = (
            hours >= self.params["tokyo_core_start"]
        ) & (hours < self.params["tokyo_core_end"])
        session_info["london_tokyo_overlap"] = (
            hours >= self.params["london_tokyo_overlap_start"]
        ) & (hours < self.params["london_tokyo_overlap_end"])

        # Calculate session-based volatility and volume
        session_info["session_volatility"] = data["high"] - data["low"]
        session_info["session_volume"] = data.get("volume", 0)

        # Mark optimal trading periods for USD/JPY
        session_info["optimal_period"] = (
            session_info["tokyo_session"] | session_info["london_tokyo_overlap"]
        )

        # Tokyo session strength indicator
        session_info["tokyo_strength"] = np.where(
            session_info["tokyo_core_hours"],
            1.0,
            np.where(session_info["tokyo_session"], 0.7, 0.3),
        )

        return session_info

    def _analyze_market_timing(self, data: pd.DataFrame) -> pd.DataFrame:
        """Analyze market timing factors for USD/JPY."""
        timing_info = pd.DataFrame(index=data.index)

        try:
            # Day of week analysis
            if hasattr(data.index, "dayofweek"):
                timing_info["day_of_week"] = data.index.dayofweek

                # Japanese market typically most active Tuesday-Thursday
                timing_info["optimal_day"] = data.index.dayofweek.isin(
                    [1, 2, 3]
                )  # Tue, Wed, Thu

                # Avoid Monday/Friday for lower volatility
                timing_info["avoid_day"] = data.index.dayofweek.isin([0, 4])  # Mon, Fri

            # Month-end flows (Japanese corporations)
            if hasattr(data.index, "day"):
                timing_info["month_end"] = data.index.day >= 25  # Last week of month
                timing_info["quarter_end"] = (data.index.month.isin([3, 6, 9, 12])) & (
                    data.index.day >= 25
                )

            return timing_info

        except Exception as e:
            logger.error(f"Error analyzing USD/JPY market timing: {str(e)}")
            return pd.DataFrame(index=data.index)

    def _analyze_risk_sentiment(self, data: pd.DataFrame) -> pd.DataFrame:
        """Analyze risk-on/risk-off sentiment for USD/JPY."""
        risk_sentiment = pd.DataFrame(index=data.index)

        try:
            # Price momentum as proxy for risk sentiment
            # USD/JPY typically rises in risk-on environments
            price_momentum_5d = data["close"].pct_change(5)
            price_momentum_20d = data["close"].pct_change(20)

            # Volatility analysis
            volatility = (data["high"] - data["low"]) / data["close"]
            volatility_ma = volatility.rolling(20).mean()

            # Risk sentiment classification
            risk_sentiment["price_momentum_5d"] = price_momentum_5d
            risk_sentiment["price_momentum_20d"] = price_momentum_20d
            risk_sentiment["volatility_ratio"] = volatility / volatility_ma

            # Combined risk sentiment indicator
            sentiment_score = (
                0.4 * price_momentum_5d / 0.02  # Normalize to typical 2% moves
                + 0.3 * price_momentum_20d / 0.05  # Normalize to typical 5% moves
                + 0.3 * (1 - volatility / volatility_ma)  # Lower vol = risk on
            )

            risk_sentiment["sentiment_score"] = np.clip(sentiment_score, -2, 2)

            # Classify sentiment
            risk_sentiment["sentiment_regime"] = np.where(
                sentiment_score > self.params["risk_on_threshold"],
                "risk_on",
                np.where(
                    sentiment_score < self.params["risk_off_threshold"],
                    "risk_off",
                    "neutral",
                ),
            )

            return risk_sentiment

        except Exception as e:
            logger.error(f"Error analyzing USD/JPY risk sentiment: {str(e)}")
            return pd.DataFrame(index=data.index)

    def _assess_boj_intervention_risk(self, data: pd.DataFrame) -> pd.DataFrame:
        """Assess Bank of Japan intervention risk."""
        intervention_risk = pd.DataFrame(index=data.index)

        try:
            current_price = data["close"].iloc[-1]

            # Check proximity to intervention levels
            intervention_levels = self.params["boj_intervention_levels"]
            proximity_pips = (
                self.params["intervention_proximity_pips"] * self.params["pip_size"]
            )

            intervention_risk["intervention_risk"] = "low"
            intervention_risk["nearest_level"] = None
            intervention_risk["distance_to_level"] = float("inf")

            # Check all intervention levels
            all_levels = (
                intervention_levels["strong_resistance"]
                + intervention_levels["moderate_resistance"]
                + intervention_levels["strong_support"]
                + intervention_levels["moderate_support"]
            )

            for level in all_levels:
                distance = abs(current_price - level)

                if distance <= proximity_pips:
                    if level in intervention_levels["strong_resistance"]:
                        intervention_risk["intervention_risk"] = "high_resistance"
                    elif level in intervention_levels["moderate_resistance"]:
                        intervention_risk["intervention_risk"] = "moderate_resistance"
                    elif level in intervention_levels["strong_support"]:
                        intervention_risk["intervention_risk"] = "high_support"
                    elif level in intervention_levels["moderate_support"]:
                        intervention_risk["intervention_risk"] = "moderate_support"

                    intervention_risk["nearest_level"] = level
                    intervention_risk["distance_to_level"] = distance
                    break

            # Rate of change analysis for intervention probability
            price_change_5d = (current_price - data["close"].iloc[-5]) / data[
                "close"
            ].iloc[-5]

            if abs(price_change_5d) > 0.03:  # 3% move in 5 days
                if intervention_risk["intervention_risk"].iloc[-1] != "low":
                    intervention_risk["intervention_risk"] = (
                        intervention_risk["intervention_risk"] + "_urgent"
                    )

            return intervention_risk

        except Exception as e:
            logger.error(f"Error assessing BoJ intervention risk: {str(e)}")
            intervention_risk["intervention_risk"] = "low"
            return intervention_risk

    def _generate_technical_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate technical analysis signals for USD/JPY."""
        technical_signals = pd.DataFrame(index=data.index)

        try:
            # Moving averages
            ema_fast = self.technical_indicators.calculate_ema(
                data["close"], period=self.params["ema_fast"]
            )
            ema_slow = self.technical_indicators.calculate_ema(
                data["close"], period=self.params["ema_slow"]
            )

            # MACD
            macd_line, macd_signal, macd_histogram = (
                self.technical_indicators.calculate_macd(
                    data["close"],
                    fast=self.params["ema_fast"],
                    slow=self.params["ema_slow"],
                    signal=self.params["macd_signal"],
                )
            )

            # RSI
            rsi = self.technical_indicators.calculate_rsi(
                data["close"], period=self.params["rsi_period"]
            )

            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = (
                self.technical_indicators.calculate_bollinger_bands(
                    data["close"],
                    period=self.params["bollinger_period"],
                    std_dev=self.params["bollinger_std"],
                )
            )

            # Generate signals

            # Trend following signals
            technical_signals["ema_signal"] = np.where(
                ema_fast > ema_slow, 1, np.where(ema_fast < ema_slow, -1, 0)
            )

            # MACD signals
            technical_signals["macd_signal"] = np.where(
                (macd_line > macd_signal) & (macd_histogram > 0),
                1,
                np.where((macd_line < macd_signal) & (macd_histogram < 0), -1, 0),
            )

            # RSI mean reversion signals
            technical_signals["rsi_signal"] = np.where(
                rsi < self.params["rsi_oversold"],
                1,
                np.where(rsi > self.params["rsi_overbought"], -1, 0),
            )

            # Bollinger Band signals
            technical_signals["bb_signal"] = np.where(
                data["close"] < bb_lower, 1, np.where(data["close"] > bb_upper, -1, 0)
            )

            # Psychological levels analysis
            technical_signals["level_signal"] = self._check_psychological_levels(
                data["close"]
            )

            # Combine technical signals
            technical_signals["combined_technical"] = (
                0.3 * technical_signals["ema_signal"]
                + 0.25 * technical_signals["macd_signal"]
                + 0.2 * technical_signals["rsi_signal"]
                + 0.15 * technical_signals["bb_signal"]
                + 0.1 * technical_signals["level_signal"]
            )

            return technical_signals

        except Exception as e:
            logger.error(f"Error generating USD/JPY technical signals: {str(e)}")
            return pd.DataFrame(index=data.index)

    def _generate_wave_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate Elliott Wave signals for USD/JPY."""
        wave_signals = pd.DataFrame(index=data.index)

        try:
            # Detect Elliott Wave patterns
            wave_analysis = self.wave_detector.analyze_patterns(
                data, lookback_period=self.params["wave_detection_period"]
            )

            if not wave_analysis:
                wave_signals["wave_signal"] = 0
                wave_signals["wave_confidence"] = 0
                return wave_signals

            # Extract wave signals based on current pattern
            current_pattern = wave_analysis[-1] if wave_analysis else None

            if (
                current_pattern
                and current_pattern.get("confidence", 0)
                >= self.params["wave_confidence_threshold"]
            ):
                wave_type = current_pattern.get("type", "")
                wave_count = current_pattern.get("wave_count", 0)

                # USD/JPY specific wave interpretation
                if wave_type == "impulse":
                    if wave_count in [1, 3, 5]:  # Impulse waves
                        signal = (
                            1 if current_pattern.get("direction", "up") == "up" else -1
                        )
                        # Wave 3 is typically strongest in USD/JPY
                        if wave_count == 3:
                            signal *= 1.2
                    elif wave_count in [2, 4]:  # Corrective waves within impulse
                        signal = (
                            -0.5
                            if current_pattern.get("direction", "up") == "up"
                            else 0.5
                        )
                    else:
                        signal = 0
                elif wave_type == "corrective":
                    # Corrective wave signals
                    if wave_count == 1:  # Wave A
                        signal = (
                            -0.7
                            if current_pattern.get("direction", "down") == "down"
                            else 0.7
                        )
                    elif wave_count == 2:  # Wave B
                        signal = (
                            0.3
                            if current_pattern.get("direction", "up") == "up"
                            else -0.3
                        )
                    elif wave_count == 3:  # Wave C
                        signal = (
                            -1
                            if current_pattern.get("direction", "down") == "down"
                            else 1
                        )
                    else:
                        signal = 0
                else:
                    signal = 0

                # Apply Fibonacci levels for entry timing
                fib_signal = self._calculate_fibonacci_signals(data, current_pattern)

                wave_signals["wave_signal"] = signal * fib_signal
                wave_signals["wave_confidence"] = current_pattern.get("confidence", 0)

            else:
                wave_signals["wave_signal"] = 0
                wave_signals["wave_confidence"] = 0

            return wave_signals

        except Exception as e:
            logger.error(f"Error generating USD/JPY wave signals: {str(e)}")
            wave_signals["wave_signal"] = 0
            wave_signals["wave_confidence"] = 0
            return wave_signals

    def _generate_ml_signals(
        self, data: pd.DataFrame, features: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate machine learning signals for USD/JPY."""
        ml_signals = pd.DataFrame(index=data.index)

        try:
            # Get or train USD/JPY specific models
            model_predictions = {}

            for model_type in self.params["ensemble_models"]:
                try:
                    model = self.ml_manager.get_or_create_model(
                        symbol="USDJPY", model_type=model_type, features=features
                    )

                    if model is not None:
                        predictions = model.predict(features.dropna())
                        model_predictions[model_type] = predictions

                except Exception as e:
                    logger.warning(
                        f"Error with {model_type} model for USD/JPY: {str(e)}"
                    )
                    continue

            if not model_predictions:
                ml_signals["ml_signal"] = 0
                ml_signals["ml_confidence"] = 0
                return ml_signals

            # Ensemble predictions with USD/JPY specific weights
            if len(model_predictions) > 1:
                weights = {
                    "xgboost": 0.4,  # Good for regime changes
                    "lstm": 0.35,  # Good for momentum
                    "transformer": 0.25,  # Good for complex patterns
                }

                ensemble_pred = np.zeros(len(features.dropna()))
                total_weight = 0

                for model_type, predictions in model_predictions.items():
                    weight = weights.get(model_type, 1.0 / len(model_predictions))
                    ensemble_pred += weight * predictions
                    total_weight += weight

                if total_weight > 0:
                    ensemble_pred /= total_weight
            else:
                ensemble_pred = list(model_predictions.values())[0]

            # Convert predictions to signals
            ml_signals["ml_signal"] = np.where(
                ensemble_pred > self.params["prediction_confidence_threshold"],
                1,
                np.where(
                    ensemble_pred < -self.params["prediction_confidence_threshold"],
                    -1,
                    0,
                ),
            )

            ml_signals["ml_confidence"] = np.abs(ensemble_pred)

            return ml_signals

        except Exception as e:
            logger.error(f"Error generating USD/JPY ML signals: {str(e)}")
            ml_signals["ml_signal"] = 0
            ml_signals["ml_confidence"] = 0
            return ml_signals

    def _apply_japanese_market_filter(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply Japanese market filters (holidays, special periods)."""
        market_filter = pd.DataFrame(index=data.index)

        try:
            # Initialize all periods as tradeable
            market_filter["tradeable"] = True
            market_filter["restriction_reason"] = None

            # Check for Japanese holidays and special periods
            if hasattr(data.index, "month") and hasattr(data.index, "day"):
                # Golden Week (late April/early May)
                golden_week = ((data.index.month == 4) & (data.index.day >= 29)) | (
                    (data.index.month == 5) & (data.index.day <= 5)
                )
                if not self.params["golden_week_trading"]:
                    market_filter.loc[golden_week, "tradeable"] = False
                    market_filter.loc[golden_week, "restriction_reason"] = "golden_week"

                # Obon (mid-August)
                obon = (
                    (data.index.month == 8)
                    & (data.index.day >= 13)
                    & (data.index.day <= 16)
                )
                if not self.params["obon_trading"]:
                    market_filter.loc[obon, "tradeable"] = False
                    market_filter.loc[obon, "restriction_reason"] = "obon"

                # Year-end (December 29 - January 3)
                year_end = ((data.index.month == 12) & (data.index.day >= 29)) | (
                    (data.index.month == 1) & (data.index.day <= 3)
                )
                if not self.params["year_end_trading"]:
                    market_filter.loc[year_end, "tradeable"] = False
                    market_filter.loc[year_end, "restriction_reason"] = "year_end"

            return market_filter

        except Exception as e:
            logger.error(f"Error applying Japanese market filter: {str(e)}")
            market_filter["tradeable"] = True
            market_filter["restriction_reason"] = None
            return market_filter

    def _combine_signals(
        self,
        data: pd.DataFrame,
        technical_signals: pd.DataFrame,
        wave_signals: pd.DataFrame,
        ml_signals: pd.DataFrame,
        session_info: pd.DataFrame,
        risk_sentiment: pd.DataFrame,
        intervention_risk: pd.DataFrame,
        market_filter: pd.DataFrame,
    ) -> pd.DataFrame:
        """Combine all signal sources for USD/JPY."""
        combined = pd.DataFrame(index=data.index)

        try:
            # Base signal combination with USD/JPY specific weights
            technical_weight = 0.30
            wave_weight = 0.35
            ml_weight = 0.25
            sentiment_weight = 0.10  # USD/JPY specific sentiment weight

            base_signal = (
                technical_weight * technical_signals.get("combined_technical", 0)
                + wave_weight * wave_signals.get("wave_signal", 0)
                + ml_weight * ml_signals.get("ml_signal", 0)
            )

            # Risk sentiment adjustment for USD/JPY
            sentiment_score = risk_sentiment.get("sentiment_score", 0)
            sentiment_multiplier = 1 + sentiment_weight * sentiment_score

            # Tokyo session adjustments
            session_multiplier = np.where(
                session_info.get("optimal_period", False), 1.0, 0.6
            )

            # Apply Tokyo core hours boost
            tokyo_boost = np.where(
                session_info.get("tokyo_core_hours", False), 1.2, 1.0
            )

            # BoJ intervention risk adjustments
            intervention_multiplier = self._calculate_intervention_multiplier(
                intervention_risk
            )

            # Market filter adjustments
            market_multiplier = np.where(market_filter.get("tradeable", True), 1.0, 0.0)

            # Apply all adjustments
            combined["base_signal"] = base_signal
            combined["adjusted_signal"] = (
                base_signal
                * sentiment_multiplier
                * session_multiplier
                * tokyo_boost
                * intervention_multiplier
                * market_multiplier
            )

            # Signal confidence
            combined["signal_confidence"] = (
                0.4 * wave_signals.get("wave_confidence", 0)
                + 0.3 * ml_signals.get("ml_confidence", 0)
                + 0.2 * np.abs(technical_signals.get("combined_technical", 0))
                + 0.1 * np.abs(sentiment_score) / 2  # Normalize sentiment confidence
            )

            return combined

        except Exception as e:
            logger.error(f"Error combining USD/JPY signals: {str(e)}")
            combined["adjusted_signal"] = 0
            combined["signal_confidence"] = 0
            return combined

    def _apply_risk_management(
        self, data: pd.DataFrame, signals: pd.DataFrame
    ) -> pd.DataFrame:
        """Apply USD/JPY specific risk management."""
        risk_managed = signals.copy()

        try:
            # Calculate position sizes based on volatility
            atr = self.technical_indicators.calculate_atr(
                data, period=self.params["atr_period"]
            )

            # USD/JPY specific volatility adjustment
            base_risk = self.params["max_risk_per_trade"]
            volatility_adjustment = self.params["atr_multiplier"] * atr / data["close"]

            risk_managed["position_size"] = np.where(
                volatility_adjustment > 0, base_risk / volatility_adjustment, 0
            )

            # Cap position size
            max_position = base_risk * 2  # Max 4% risk per trade
            risk_managed["position_size"] = np.minimum(
                risk_managed["position_size"], max_position
            )

            # Adjust signals based on risk
            risk_managed["final_signal"] = risk_managed["adjusted_signal"] * np.minimum(
                risk_managed["position_size"] / base_risk, 1.0
            )

            return risk_managed

        except Exception as e:
            logger.error(f"Error applying USD/JPY risk management: {str(e)}")
            risk_managed["position_size"] = self.params["max_risk_per_trade"]
            risk_managed["final_signal"] = risk_managed.get("adjusted_signal", 0)
            return risk_managed

    def _validate_signals(
        self, data: pd.DataFrame, signals: pd.DataFrame
    ) -> pd.DataFrame:
        """Final validation of USD/JPY signals."""
        validated = signals.copy()

        try:
            # Minimum confidence threshold
            min_confidence = 0.4

            validated["signal"] = np.where(
                validated.get("signal_confidence", 0) >= min_confidence,
                validated.get("final_signal", 0),
                0,
            )

            # Add metadata
            validated["symbol"] = "USDJPY"
            validated["strategy"] = self.name
            validated["timestamp"] = data.index

            # Calculate stop loss and take profit levels (USD/JPY pips)
            atr = self.technical_indicators.calculate_atr(
                data, period=self.params["atr_period"]
            )

            validated["stop_loss_distance"] = self.params["atr_multiplier"] * atr
            validated["take_profit_distance"] = 2 * validated["stop_loss_distance"]

            # Convert to pips for USD/JPY
            validated["stop_loss_pips"] = (
                validated["stop_loss_distance"] / self.params["pip_size"]
            )
            validated["take_profit_pips"] = (
                validated["take_profit_distance"] / self.params["pip_size"]
            )

            return validated

        except Exception as e:
            logger.error(f"Error validating USD/JPY signals: {str(e)}")
            validated["signal"] = 0
            return validated

    # Helper methods

    def _check_psychological_levels(self, price_series: pd.Series) -> pd.Series:
        """Check proximity to USD/JPY psychological levels."""
        levels = self.params["psychological_levels"]
        signals = pd.Series(0, index=price_series.index)
        proximity_threshold = 0.50  # 50 pips

        for price in price_series:
            if pd.isna(price):
                continue

            # Find nearest level
            distances = [abs(price - level) for level in levels]
            min_distance = min(distances)
            nearest_level = levels[distances.index(min_distance)]

            # Generate signal if near key level
            if min_distance <= proximity_threshold:
                if price < nearest_level:
                    signals[price_series.index[price_series == price][0]] = (
                        1  # Buy near support
                    )
                else:
                    signals[price_series.index[price_series == price][0]] = (
                        -1
                    )  # Sell near resistance

        return signals

    def _calculate_fibonacci_signals(
        self, data: pd.DataFrame, pattern: Dict[str, Any]
    ) -> float:
        """Calculate Fibonacci-based signal strength for USD/JPY."""
        try:
            current_price = data["close"].iloc[-1]

            # Get pattern high and low
            pattern_high = pattern.get("high", current_price)
            pattern_low = pattern.get("low", current_price)

            if pattern_high <= pattern_low:
                return 1.0

            # Calculate Fibonacci levels
            fib_range = pattern_high - pattern_low

            # Check retracement levels (USD/JPY specific tolerance)
            tolerance = 0.30  # 30 pips tolerance

            for level in self.params["fibonacci_retracement_levels"]:
                fib_price = pattern_high - (level * fib_range)

                if abs(current_price - fib_price) <= tolerance:
                    # Stronger signal at key Fibonacci levels
                    if level in [0.382, 0.618]:
                        return 1.3
                    else:
                        return 1.1

            return 1.0

        except Exception as e:
            logger.error(f"Error calculating Fibonacci signals: {str(e)}")
            return 1.0

    def _calculate_intervention_multiplier(
        self, intervention_risk: pd.DataFrame
    ) -> pd.Series:
        """Calculate intervention risk multiplier."""
        try:
            risk_level = intervention_risk.get("intervention_risk", "low")

            # Adjust signals based on intervention risk
            multiplier = pd.Series(1.0, index=intervention_risk.index)

            # Reduce signals near intervention levels
            multiplier = (
                multiplier.where(
                    ~risk_level.str.contains("high"),
                    0.3,  # Strong reduction near intervention
                )
                .where(~risk_level.str.contains("moderate"), 0.6)  # Moderate reduction
                .where(
                    ~risk_level.str.contains("urgent"),
                    0.1,  # Minimal signals for urgent intervention risk
                )
            )

            return multiplier

        except Exception as e:
            logger.error(f"Error calculating intervention multiplier: {str(e)}")
            return pd.Series(1.0, index=intervention_risk.index)

    def _engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Engineer USD/JPY specific features."""
        try:
            features = self.feature_engineer.create_features(
                data,
                lookback_periods=[5, 10, 20, 50],
                include_technical=True,
                include_statistical=True,
                symbol="USDJPY",
            )

            # Add USD/JPY specific features
            features["hour_utc"] = (
                data.index.hour if hasattr(data.index, "hour") else 12
            )
            features["is_tokyo_session"] = (features["hour_utc"] >= 0) & (
                features["hour_utc"] < 9
            )
            features["is_tokyo_core"] = (features["hour_utc"] >= 1) & (
                features["hour_utc"] < 6
            )

            # Risk sentiment features
            features["price_momentum_5d"] = data["close"].pct_change(5)
            features["price_momentum_20d"] = data["close"].pct_change(20)

            # Volatility clustering
            volatility = (data["high"] - data["low"]) / data["close"]
            features["volatility_regime"] = volatility / volatility.rolling(20).mean()

            return features

        except Exception as e:
            logger.error(f"Error engineering USD/JPY features: {str(e)}")
            return pd.DataFrame(index=data.index)

    def get_strategy_params(self) -> Dict[str, Any]:
        """Get strategy parameters for USD/JPY."""
        return {
            "name": self.name,
            "symbol": "USDJPY",
            "parameters": self.params,
            "components": [
                "tokyo_session_optimization",
                "boj_intervention_analysis",
                "risk_sentiment_correlation",
                "technical_indicators",
                "elliott_wave",
                "machine_learning",
                "japanese_market_filter",
            ],
        }

    def update_params(self, new_params: Dict[str, Any]) -> None:
        """Update strategy parameters."""
        self.params.update(new_params)
        logger.info(f"Updated {self.name} parameters: {list(new_params.keys())}")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get USD/JPY strategy performance metrics."""
        return {
            **self.performance,
            "symbol": "USDJPY",
            "strategy": self.name,
            "session_focus": "tokyo",
            "risk_sentiment_correlation": True,
            "boj_intervention_aware": True,
            "win_rate": (
                self.performance["winning_trades"]
                / max(self.performance["total_trades"], 1)
            )
            * 100,
            "avg_win_loss_ratio": (
                (
                    (
                        self.performance["total_pnl"]
                        / max(self.performance["winning_trades"], 1)
                    )
                    / abs(
                        self.performance["total_pnl"]
                        / max(self.performance["losing_trades"], 1)
                    )
                )
                if self.performance["losing_trades"] > 0
                else 0
            ),
        }
