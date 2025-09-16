"""
EUR/USD Trading Strategy Implementation.

This module implements a specialized EUR/USD trading strategy that combines:
- Elliott Wave analysis optimized for EUR/USD patterns
- Machine learning models trained on EUR/USD data
- Session-aware trading considering European and US market overlap
- ECB and Fed policy analysis integration
- EUR/USD specific technical indicators and patterns
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


class EURUSDStrategy(BaseStrategy):
    """
    EUR/USD specialized trading strategy.

    Features:
    - EUR/USD optimized Elliott Wave patterns
    - European Central Bank (ECB) policy awareness
    - Federal Reserve (Fed) policy correlation
    - European session optimization (7-16 UTC)
    - US session overlap trading (12-16 UTC)
    - EUR/USD specific volatility patterns
    - Cross-correlation with EUR indices (DAX, STOXX50)
    """

    def __init__(
        self, name: str = "EURUSDStrategy", params: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize EUR/USD strategy.

        Args:
            name: Strategy name
            params: Strategy parameters specific to EUR/USD
        """
        # EUR/USD specific default parameters
        default_params = {
            # Trading sessions (UTC hours)
            "european_session_start": 7,
            "european_session_end": 16,
            "us_overlap_start": 12,
            "us_overlap_end": 16,
            "avoid_asian_session": True,
            # EUR/USD volatility parameters
            "min_volatility_threshold": 0.0008,  # 8 pips
            "max_volatility_threshold": 0.0025,  # 25 pips
            "volatility_lookback": 20,
            # Elliott Wave parameters for EUR/USD
            "wave_detection_period": 100,
            "wave_confidence_threshold": 0.65,
            "fibonacci_retracement_levels": [0.236, 0.382, 0.500, 0.618, 0.786],
            "fibonacci_extension_levels": [1.272, 1.414, 1.618, 2.000],
            # Risk management for EUR/USD
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
            # News and fundamentals
            "ecb_announcement_buffer_hours": 2,
            "fed_announcement_buffer_hours": 2,
            "high_impact_news_filter": True,
            "nfp_trading_restriction": True,  # Non-Farm Payrolls
            # Technical indicators
            "ema_fast": 12,
            "ema_slow": 26,
            "macd_signal": 9,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "bollinger_period": 20,
            "bollinger_std": 2,
            # EUR/USD specific levels
            "key_psychological_levels": [
                1.0000,
                1.0500,
                1.1000,
                1.1500,
                1.2000,
                1.2500,
            ],
            "ecb_intervention_levels": {"support": 1.0500, "resistance": 1.2500},
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

        # EUR/USD specific state
        self.current_session = None
        self.current_regime = None
        self.last_ecb_event = None
        self.last_fed_event = None

        logger.info(f"Initialized {self.name} with EUR/USD optimized parameters")

    def generate_signals(
        self, data: pd.DataFrame, features: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Generate EUR/USD trading signals.

        Args:
            data: OHLCV price data for EUR/USD
            features: Pre-computed features (optional)

        Returns:
            DataFrame with trading signals and metadata
        """
        try:
            if data.empty:
                logger.warning("Empty data provided to EUR/USD strategy")
                return pd.DataFrame()

            logger.info(f"Generating EUR/USD signals for {len(data)} periods")

            # Step 1: Session and regime analysis
            session_info = self._analyze_trading_sessions(data)
            regime_info = self._classify_market_regime(data)

            # Step 2: Technical analysis
            technical_signals = self._generate_technical_signals(data)

            # Step 3: Elliott Wave analysis
            wave_signals = self._generate_wave_signals(data)

            # Step 4: Machine learning signals
            if features is None:
                features = self._engineer_features(data)
            ml_signals = self._generate_ml_signals(data, features)

            # Step 5: Fundamental analysis (news/events)
            fundamental_filter = self._apply_fundamental_filter(data)

            # Step 6: Combine all signals
            combined_signals = self._combine_signals(
                data,
                technical_signals,
                wave_signals,
                ml_signals,
                session_info,
                regime_info,
                fundamental_filter,
            )

            # Step 7: Apply risk management
            risk_adjusted_signals = self._apply_risk_management(data, combined_signals)

            # Step 8: Final signal validation
            validated_signals = self._validate_signals(data, risk_adjusted_signals)

            logger.info(
                f"Generated {len(validated_signals[validated_signals['signal'] != 0])} EUR/USD signals"
            )

            return validated_signals

        except Exception as e:
            logger.error(f"Error generating EUR/USD signals: {str(e)}")
            return pd.DataFrame()

    def _analyze_trading_sessions(self, data: pd.DataFrame) -> pd.DataFrame:
        """Analyze EUR/USD trading sessions and optimal times."""
        session_info = pd.DataFrame(index=data.index)

        # Convert to UTC if timezone info available
        if hasattr(data.index, "tz") and data.index.tz is not None:
            utc_times = data.index.tz_convert("UTC")
        else:
            # Assume UTC if no timezone info
            utc_times = data.index

        # Define sessions
        hours = utc_times.hour
        session_info["european_session"] = (
            hours >= self.params["european_session_start"]
        ) & (hours < self.params["european_session_end"])
        session_info["us_overlap"] = (hours >= self.params["us_overlap_start"]) & (
            hours < self.params["us_overlap_end"]
        )
        session_info["asian_session"] = (hours >= 22) | (hours < 7)

        # Calculate session-based volatility
        session_info["session_volatility"] = data["high"] - data["low"]
        session_info["session_volume"] = data.get("volume", 0)

        # Mark optimal trading periods for EUR/USD
        session_info["optimal_period"] = (
            session_info["european_session"] | session_info["us_overlap"]
        )

        if self.params["avoid_asian_session"]:
            session_info["optimal_period"] = (
                session_info["optimal_period"] & ~session_info["asian_session"]
            )

        return session_info

    def _classify_market_regime(self, data: pd.DataFrame) -> pd.DataFrame:
        """Classify EUR/USD market regime."""
        try:
            # Use volatility, trend, and volume to classify regime
            lookback = self.params["volatility_lookback"]

            # Calculate volatility (ATR-based)
            atr = self.technical_indicators.calculate_atr(
                data, period=self.params["atr_period"]
            )

            # Volatility percentile for regime classification
            vol_percentile = atr.rolling(lookback * 5).rank(pct=True)

            # Trend strength using ADX
            adx = self.technical_indicators.calculate_adx(data, period=14)

            # Volume analysis (if available)
            volume_ma = (
                data.get("volume", pd.Series(0, index=data.index)).rolling(20).mean()
            )
            volume_ratio = data.get("volume", volume_ma) / volume_ma

            regime_info = pd.DataFrame(index=data.index)

            # Classify regimes
            regime_info["volatility_regime"] = pd.cut(
                vol_percentile,
                bins=[0, 0.33, 0.67, 1.0],
                labels=["low_vol", "medium_vol", "high_vol"],
            )

            regime_info["trend_regime"] = pd.cut(
                adx,
                bins=[0, 20, 40, 100],
                labels=["sideways", "trending", "strong_trend"],
            )

            regime_info["volume_regime"] = np.where(
                volume_ratio > 1.2,
                "high_volume",
                np.where(volume_ratio > 0.8, "normal_volume", "low_volume"),
            )

            return regime_info

        except Exception as e:
            logger.error(f"Error classifying EUR/USD market regime: {str(e)}")
            return pd.DataFrame(index=data.index)

    def _generate_technical_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate technical analysis signals for EUR/USD."""
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

            # Support/Resistance levels (EUR/USD psychological levels)
            technical_signals["level_signal"] = self._check_key_levels(data["close"])

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
            logger.error(f"Error generating EUR/USD technical signals: {str(e)}")
            return pd.DataFrame(index=data.index)

    def _generate_wave_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate Elliott Wave signals for EUR/USD."""
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

                if wave_type == "impulse":
                    # Impulse wave signals
                    if wave_count in [1, 3, 5]:  # Impulse waves
                        signal = (
                            1 if current_pattern.get("direction", "up") == "up" else -1
                        )
                    elif wave_count in [2, 4]:  # Corrective waves within impulse
                        signal = (
                            -0.5
                            if current_pattern.get("direction", "up") == "up"
                            else 0.5
                        )
                    else:
                        signal = 0
                elif wave_type == "corrective":
                    # Corrective wave signals (typically counter-trend)
                    if wave_count == 1:  # Wave A
                        signal = (
                            -0.7
                            if current_pattern.get("direction", "down") == "down"
                            else 0.7
                        )
                    elif wave_count == 2:  # Wave B (counter-correction)
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
            logger.error(f"Error generating EUR/USD wave signals: {str(e)}")
            wave_signals["wave_signal"] = 0
            wave_signals["wave_confidence"] = 0
            return wave_signals

    def _generate_ml_signals(
        self, data: pd.DataFrame, features: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate machine learning signals for EUR/USD."""
        ml_signals = pd.DataFrame(index=data.index)

        try:
            # Get or train EUR/USD specific models
            model_predictions = {}

            for model_type in self.params["ensemble_models"]:
                try:
                    model = self.ml_manager.get_or_create_model(
                        symbol="EURUSD", model_type=model_type, features=features
                    )

                    if model is not None:
                        predictions = model.predict(features.dropna())
                        model_predictions[model_type] = predictions

                except Exception as e:
                    logger.warning(
                        f"Error with {model_type} model for EUR/USD: {str(e)}"
                    )
                    continue

            if not model_predictions:
                ml_signals["ml_signal"] = 0
                ml_signals["ml_confidence"] = 0
                return ml_signals

            # Ensemble predictions
            if len(model_predictions) > 1:
                # Weighted ensemble
                weights = {"xgboost": 0.4, "lstm": 0.35, "transformer": 0.25}

                ensemble_pred = np.zeros(len(features.dropna()))
                total_weight = 0

                for model_type, predictions in model_predictions.items():
                    weight = weights.get(model_type, 1.0 / len(model_predictions))
                    ensemble_pred += weight * predictions
                    total_weight += weight

                if total_weight > 0:
                    ensemble_pred /= total_weight
            else:
                # Single model
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
            logger.error(f"Error generating EUR/USD ML signals: {str(e)}")
            ml_signals["ml_signal"] = 0
            ml_signals["ml_confidence"] = 0
            return ml_signals

    def _apply_fundamental_filter(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply fundamental analysis filters for EUR/USD."""
        fundamental_filter = pd.DataFrame(index=data.index)

        try:
            # Initialize all periods as tradeable
            fundamental_filter["tradeable"] = True
            fundamental_filter["news_impact"] = "low"

            # High impact news events (would normally come from economic calendar)
            # For now, implement basic filtering based on common patterns

            # Check for potential ECB/Fed announcement periods
            # This would typically integrate with economic calendar API

            # Friday close restrictions (for EUR/USD weekend gaps)
            if hasattr(data.index, "dayofweek"):
                friday_close = (data.index.dayofweek == 4) & (data.index.hour >= 21)
                fundamental_filter.loc[friday_close, "tradeable"] = False
                fundamental_filter.loc[friday_close, "news_impact"] = "high"

            # Month-end flows (EUR/USD often affected by portfolio rebalancing)
            if hasattr(data.index, "day"):
                month_end = data.index.day >= 28
                fundamental_filter.loc[month_end, "news_impact"] = "medium"

            # Quarter-end flows (stronger impact)
            if hasattr(data.index, "month") and hasattr(data.index, "day"):
                quarter_end = (data.index.month.isin([3, 6, 9, 12])) & (
                    data.index.day >= 28
                )
                fundamental_filter.loc[quarter_end, "news_impact"] = "high"

            return fundamental_filter

        except Exception as e:
            logger.error(f"Error applying EUR/USD fundamental filter: {str(e)}")
            fundamental_filter["tradeable"] = True
            fundamental_filter["news_impact"] = "low"
            return fundamental_filter

    def _combine_signals(
        self,
        data: pd.DataFrame,
        technical_signals: pd.DataFrame,
        wave_signals: pd.DataFrame,
        ml_signals: pd.DataFrame,
        session_info: pd.DataFrame,
        regime_info: pd.DataFrame,
        fundamental_filter: pd.DataFrame,
    ) -> pd.DataFrame:
        """Combine all signal sources for EUR/USD."""
        combined = pd.DataFrame(index=data.index)

        try:
            # Base signal combination
            technical_weight = 0.35
            wave_weight = 0.35
            ml_weight = 0.30

            combined["base_signal"] = (
                technical_weight * technical_signals.get("combined_technical", 0)
                + wave_weight * wave_signals.get("wave_signal", 0)
                + ml_weight * ml_signals.get("ml_signal", 0)
            )

            # Session adjustments
            session_multiplier = np.where(
                session_info.get("optimal_period", False), 1.0, 0.5
            )

            # Regime adjustments
            regime_multiplier = np.ones(len(data))

            if "volatility_regime" in regime_info.columns:
                vol_regime = regime_info["volatility_regime"]
                regime_multiplier = np.where(
                    vol_regime == "high_vol",
                    0.7,  # Reduce signals in high volatility
                    np.where(
                        vol_regime == "low_vol", 0.8, 1.0
                    ),  # Standard in normal vol
                )

            # News filter adjustments
            news_multiplier = np.where(
                fundamental_filter.get("tradeable", True), 1.0, 0.0
            )

            # Apply all adjustments
            combined["adjusted_signal"] = (
                combined["base_signal"]
                * session_multiplier
                * regime_multiplier
                * news_multiplier
            )

            # Signal confidence
            combined["signal_confidence"] = (
                0.4 * wave_signals.get("wave_confidence", 0)
                + 0.3 * ml_signals.get("ml_confidence", 0)
                + 0.3 * np.abs(technical_signals.get("combined_technical", 0))
            )

            return combined

        except Exception as e:
            logger.error(f"Error combining EUR/USD signals: {str(e)}")
            combined["adjusted_signal"] = 0
            combined["signal_confidence"] = 0
            return combined

    def _apply_risk_management(
        self, data: pd.DataFrame, signals: pd.DataFrame
    ) -> pd.DataFrame:
        """Apply EUR/USD specific risk management."""
        risk_managed = signals.copy()

        try:
            # Calculate position sizes based on volatility
            atr = self.technical_indicators.calculate_atr(
                data, period=self.params["atr_period"]
            )

            # Volatility-adjusted position sizing
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
            logger.error(f"Error applying EUR/USD risk management: {str(e)}")
            risk_managed["position_size"] = self.params["max_risk_per_trade"]
            risk_managed["final_signal"] = risk_managed.get("adjusted_signal", 0)
            return risk_managed

    def _validate_signals(
        self, data: pd.DataFrame, signals: pd.DataFrame
    ) -> pd.DataFrame:
        """Final validation of EUR/USD signals."""
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
            validated["symbol"] = "EURUSD"
            validated["strategy"] = self.name
            validated["timestamp"] = data.index

            # Calculate stop loss and take profit levels
            atr = self.technical_indicators.calculate_atr(
                data, period=self.params["atr_period"]
            )

            validated["stop_loss_distance"] = self.params["atr_multiplier"] * atr
            validated["take_profit_distance"] = 2 * validated["stop_loss_distance"]

            return validated

        except Exception as e:
            logger.error(f"Error validating EUR/USD signals: {str(e)}")
            validated["signal"] = 0
            return validated

    def _engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Engineer EUR/USD specific features."""
        try:
            features = self.feature_engineer.create_features(
                data,
                lookback_periods=[5, 10, 20, 50],
                include_technical=True,
                include_statistical=True,
                symbol="EURUSD",
            )

            # Add EUR/USD specific features
            features["eur_strength"] = self._calculate_currency_strength(data, "EUR")
            features["usd_strength"] = self._calculate_currency_strength(data, "USD")
            features["eur_usd_differential"] = (
                features["eur_strength"] - features["usd_strength"]
            )

            return features

        except Exception as e:
            logger.error(f"Error engineering EUR/USD features: {str(e)}")
            return pd.DataFrame(index=data.index)

    def _check_key_levels(self, price_series: pd.Series) -> pd.Series:
        """Check proximity to EUR/USD key psychological levels."""
        levels = self.params["key_psychological_levels"]
        signals = pd.Series(0, index=price_series.index)

        for price in price_series:
            if pd.isna(price):
                continue

            # Find nearest level
            distances = [abs(price - level) for level in levels]
            min_distance = min(distances)
            nearest_level = levels[distances.index(min_distance)]

            # Generate signal if near key level (within 50 pips)
            if min_distance <= 0.0050:
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
        """Calculate Fibonacci-based signal strength."""
        try:
            current_price = data["close"].iloc[-1]

            # Get pattern high and low
            pattern_high = pattern.get("high", current_price)
            pattern_low = pattern.get("low", current_price)

            if pattern_high <= pattern_low:
                return 1.0

            # Calculate Fibonacci levels
            fib_range = pattern_high - pattern_low

            # Check retracement levels
            for level in self.params["fibonacci_retracement_levels"]:
                fib_price = pattern_high - (level * fib_range)

                # If price is near Fibonacci level (within 10 pips)
                if abs(current_price - fib_price) <= 0.0010:
                    # Stronger signal at key Fibonacci levels
                    if level in [0.382, 0.618]:
                        return 1.2
                    else:
                        return 1.1

            return 1.0

        except Exception as e:
            logger.error(f"Error calculating Fibonacci signals: {str(e)}")
            return 1.0

    def _calculate_currency_strength(
        self, data: pd.DataFrame, currency: str
    ) -> pd.Series:
        """Calculate currency strength indicator."""
        # This would typically use basket of currency pairs
        # For now, use price momentum as proxy
        try:
            price_change = data["close"].pct_change(20)  # 20-period change

            if currency == "EUR":
                # EUR strength: positive EUR/USD change indicates EUR strength
                return price_change
            else:  # USD
                # USD strength: negative EUR/USD change indicates USD strength
                return -price_change

        except Exception as e:
            logger.error(f"Error calculating {currency} strength: {str(e)}")
            return pd.Series(0, index=data.index)

    def get_strategy_params(self) -> Dict[str, Any]:
        """Get strategy parameters for EUR/USD."""
        return {
            "name": self.name,
            "symbol": "EURUSD",
            "parameters": self.params,
            "components": [
                "technical_indicators",
                "elliott_wave",
                "machine_learning",
                "fundamental_analysis",
                "risk_management",
            ],
        }

    def update_params(self, new_params: Dict[str, Any]) -> None:
        """Update strategy parameters."""
        self.params.update(new_params)
        logger.info(f"Updated {self.name} parameters: {list(new_params.keys())}")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get EUR/USD strategy performance metrics."""
        return {
            **self.performance,
            "symbol": "EURUSD",
            "strategy": self.name,
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
