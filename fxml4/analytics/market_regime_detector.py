"""
AI-Powered Market Regime Detection Engine for Phase 8

This module implements an advanced market regime detection system that combines:
- Machine learning models for regime classification
- Elliott Wave pattern analysis integration
- Real-time sentiment incorporation
- LLM-enhanced regime validation and explanation
"""

import asyncio
import json
import logging
import pickle
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from ..core.database import DatabaseManager
from ..data_engineering.features import FeatureEngineer
from ..llm_integration.llm_client import LLMClient
from ..llm_integration.sentiment_analysis import MarketSentimentAnalyzer
from ..wave_analysis.elliott_wave import ElliottWaveAnalyzer

logger = logging.getLogger(__name__)


class MarketRegimeType(Enum):
    """Market regime classifications."""

    TRENDING_BULL = "trending_bull"
    TRENDING_BEAR = "trending_bear"
    RANGING_LOW_VOL = "ranging_low_vol"
    RANGING_HIGH_VOL = "ranging_high_vol"
    VOLATILE_UNCERTAIN = "volatile_uncertain"
    BREAKOUT_BULL = "breakout_bull"
    BREAKOUT_BEAR = "breakout_bear"
    CRISIS_MODE = "crisis_mode"


@dataclass
class RegimeCharacteristics:
    """Characteristics of a market regime."""

    volatility_level: float
    trend_strength: float
    momentum: float
    volume_profile: float
    sentiment_bias: float
    wave_structure_quality: float
    duration_stability: float
    reversion_tendency: float


@dataclass
class RegimeDetection:
    """Market regime detection result."""

    regime_type: MarketRegimeType
    confidence: float
    characteristics: RegimeCharacteristics
    duration_minutes: int
    supporting_evidence: List[str]
    risk_factors: List[str]
    expected_duration: int
    transition_probability: Dict[MarketRegimeType, float]
    llm_explanation: str
    actionable_insights: List[str]


class MarketRegimeDetector:
    """AI-powered market regime detection system."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the market regime detector.

        Args:
            config: Configuration dictionary with model parameters
        """
        self.config = config or self._get_default_config()

        # Initialize components
        self.llm_client = LLMClient()
        self.sentiment_analyzer = MarketSentimentAnalyzer()
        self.wave_analyzer = ElliottWaveAnalyzer()
        self.feature_engineer = FeatureEngineer()
        self.db_manager = DatabaseManager()

        # ML models
        self.regime_classifier = None
        self.anomaly_detector = None
        self.transition_model = None
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=10)

        # Regime tracking
        self.current_regime = None
        self.regime_start_time = None
        self.regime_history = []
        self.confidence_threshold = config.get("confidence_threshold", 0.75)

        # Feature cache
        self.feature_cache = {}
        self.cache_duration = timedelta(minutes=5)

        # Load pre-trained models if available
        self._load_models()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "lookback_periods": [5, 10, 20, 50, 100, 200],
            "volatility_windows": [10, 20, 50],
            "momentum_periods": [5, 10, 20],
            "volume_periods": [10, 20, 50],
            "sentiment_weight": 0.2,
            "wave_weight": 0.3,
            "technical_weight": 0.5,
            "confidence_threshold": 0.75,
            "min_regime_duration": 30,  # minutes
            "max_regime_duration": 1440,  # minutes (24 hours)
            "transition_sensitivity": 0.8,
            "anomaly_threshold": 0.1,
            "retrain_frequency": 168,  # hours (1 week)
        }

    def _load_models(self):
        """Load pre-trained models from disk."""
        try:
            # Load main regime classifier
            self.regime_classifier = joblib.load("models/regime_classifier.pkl")
            self.anomaly_detector = joblib.load("models/anomaly_detector.pkl")
            self.transition_model = joblib.load("models/transition_model.pkl")
            self.scaler = joblib.load("models/regime_scaler.pkl")
            self.pca = joblib.load("models/regime_pca.pkl")
            logger.info("Loaded pre-trained regime detection models")
        except FileNotFoundError:
            logger.warning("Pre-trained models not found, will train on first use")
            self._initialize_models()

    def _initialize_models(self):
        """Initialize ML models with default parameters."""
        self.regime_classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
        )

        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)

        self.transition_model = RandomForestClassifier(
            n_estimators=50, max_depth=8, random_state=42
        )

    async def detect_regime(
        self, symbol: str, timeframe: str = "4h", use_llm_validation: bool = True
    ) -> RegimeDetection:
        """Detect current market regime for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'GBPUSD')
            timeframe: Analysis timeframe
            use_llm_validation: Whether to use LLM for regime validation

        Returns:
            RegimeDetection object with comprehensive analysis
        """
        try:
            # Get market data and features
            features = await self._get_regime_features(symbol, timeframe)

            # Primary regime classification
            regime_probs = self._predict_regime(features)
            primary_regime = max(regime_probs, key=regime_probs.get)
            primary_confidence = regime_probs[primary_regime]

            # Regime characteristics analysis
            characteristics = self._analyze_regime_characteristics(features)

            # Transition probability analysis
            transition_probs = self._predict_transitions(features, primary_regime)

            # Anomaly detection
            is_anomalous = self._detect_anomalies(features)

            # Supporting evidence and risk factors
            evidence, risks = self._analyze_evidence_and_risks(
                features, primary_regime, characteristics, is_anomalous
            )

            # Duration analysis
            current_duration = self._get_current_regime_duration()
            expected_duration = self._estimate_regime_duration(
                primary_regime, characteristics
            )

            # LLM validation and explanation
            llm_explanation = ""
            actionable_insights = []

            if use_llm_validation and primary_confidence > self.confidence_threshold:
                llm_analysis = await self._get_llm_regime_analysis(
                    symbol, primary_regime, characteristics, evidence, risks
                )
                llm_explanation = llm_analysis.get("explanation", "")
                actionable_insights = llm_analysis.get("insights", [])

            # Create detection result
            detection = RegimeDetection(
                regime_type=primary_regime,
                confidence=primary_confidence,
                characteristics=characteristics,
                duration_minutes=current_duration,
                supporting_evidence=evidence,
                risk_factors=risks,
                expected_duration=expected_duration,
                transition_probability=transition_probs,
                llm_explanation=llm_explanation,
                actionable_insights=actionable_insights,
            )

            # Update regime tracking
            self._update_regime_tracking(detection)

            # Store result in database
            await self._store_detection_result(symbol, timeframe, detection)

            return detection

        except Exception as e:
            logger.error(f"Error detecting regime for {symbol}: {str(e)}")
            raise

    async def _get_regime_features(self, symbol: str, timeframe: str) -> np.ndarray:
        """Get comprehensive features for regime detection.

        Args:
            symbol: Trading symbol
            timeframe: Analysis timeframe

        Returns:
            Feature array for regime classification
        """
        cache_key = f"{symbol}_{timeframe}_{datetime.now().hour}"

        # Check cache first
        if cache_key in self.feature_cache:
            cached_time, cached_features = self.feature_cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                return cached_features

        # Get market data
        end_time = datetime.now()
        start_time = end_time - timedelta(days=30)  # 30 days of data

        price_data = await self.db_manager.get_market_data(
            symbol=symbol, start_time=start_time, end_time=end_time, timeframe=timeframe
        )

        if len(price_data) < 200:
            raise ValueError(
                f"Insufficient data for regime detection: {len(price_data)} bars"
            )

        # Technical features
        technical_features = self._extract_technical_features(price_data)

        # Sentiment features
        sentiment_features = await self._extract_sentiment_features(symbol)

        # Elliott Wave features
        wave_features = await self._extract_wave_features(price_data)

        # Market microstructure features
        microstructure_features = self._extract_microstructure_features(price_data)

        # Volatility regime features
        volatility_features = self._extract_volatility_features(price_data)

        # Combine all features
        all_features = np.concatenate(
            [
                technical_features,
                sentiment_features,
                wave_features,
                microstructure_features,
                volatility_features,
            ]
        )

        # Cache the result
        self.feature_cache[cache_key] = (datetime.now(), all_features)

        return all_features

    def _extract_technical_features(self, price_data: pd.DataFrame) -> np.ndarray:
        """Extract technical analysis features."""
        features = []

        # Price features
        close_prices = price_data["close"].values
        high_prices = price_data["high"].values
        low_prices = price_data["low"].values
        volume = price_data.get("volume", pd.Series([1] * len(price_data))).values

        # Trend features
        for period in self.config["lookback_periods"]:
            if len(close_prices) >= period:
                # Moving averages
                sma = np.mean(close_prices[-period:])
                ema = self._calculate_ema(close_prices, period)
                features.extend([sma / close_prices[-1], ema / close_prices[-1]])

                # Trend strength
                trend_strength = (
                    close_prices[-1] - close_prices[-period]
                ) / close_prices[-period]
                features.append(trend_strength)

                # Price position within range
                period_high = np.max(high_prices[-period:])
                period_low = np.min(low_prices[-period:])
                if period_high != period_low:
                    price_position = (close_prices[-1] - period_low) / (
                        period_high - period_low
                    )
                    features.append(price_position)
                else:
                    features.append(0.5)

        # Momentum features
        for period in self.config["momentum_periods"]:
            if len(close_prices) >= period + 1:
                # Rate of change
                roc = (close_prices[-1] - close_prices[-period - 1]) / close_prices[
                    -period - 1
                ]
                features.append(roc)

                # RSI
                rsi = self._calculate_rsi(close_prices, period)
                features.append(rsi / 100.0)

        # Volatility features
        for window in self.config["volatility_windows"]:
            if len(close_prices) >= window:
                returns = np.diff(np.log(close_prices[-window - 1 :]))
                volatility = np.std(returns) * np.sqrt(252)  # Annualized
                features.append(volatility)

                # Volatility of volatility
                if len(returns) >= 10:
                    vol_of_vol = np.std(
                        [np.std(returns[i : i + 5]) for i in range(len(returns) - 4)]
                    )
                    features.append(vol_of_vol)
                else:
                    features.append(0.0)

        # Volume features
        for period in self.config["volume_periods"]:
            if len(volume) >= period:
                avg_volume = np.mean(volume[-period:])
                current_volume = volume[-1]
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
                features.append(volume_ratio)

        return np.array(features)

    async def _extract_sentiment_features(self, symbol: str) -> np.ndarray:
        """Extract sentiment-based features."""
        try:
            sentiment_data = await self.sentiment_analyzer.get_realtime_sentiment(
                symbol
            )

            features = [
                sentiment_data.get("overall_sentiment", 0.5),
                sentiment_data.get("news_sentiment", 0.5),
                sentiment_data.get("social_sentiment", 0.5),
                sentiment_data.get("sentiment_volatility", 0.0),
                sentiment_data.get("sentiment_momentum", 0.0),
                sentiment_data.get("news_volume_impact", 0.0),
            ]

            return np.array(features)

        except Exception as e:
            logger.warning(f"Error extracting sentiment features: {str(e)}")
            return np.array([0.5, 0.5, 0.5, 0.0, 0.0, 0.0])

    async def _extract_wave_features(self, price_data: pd.DataFrame) -> np.ndarray:
        """Extract Elliott Wave analysis features."""
        try:
            # Detect peaks and troughs
            df_with_peaks = self.wave_analyzer.detect_peaks_and_troughs(price_data)

            # Get wave structure features
            waves = self.wave_analyzer.compute_waves(df_with_peaks)

            features = []

            if len(waves) > 0:
                # Wave count and structure
                features.append(len(waves))

                # Average wave size
                wave_sizes = [
                    abs(wave.get("end_price", 0) - wave.get("start_price", 0))
                    for wave in waves
                ]
                avg_wave_size = np.mean(wave_sizes) if wave_sizes else 0
                features.append(avg_wave_size)

                # Wave structure quality
                quality_scores = [wave.get("quality_score", 0.5) for wave in waves]
                avg_quality = np.mean(quality_scores) if quality_scores else 0.5
                features.append(avg_quality)

                # Current wave position
                if waves:
                    current_wave = waves[-1]
                    features.extend(
                        [
                            current_wave.get("wave_degree", 0),
                            current_wave.get("fibonacci_ratio", 1.0),
                            current_wave.get("completion_ratio", 0.5),
                        ]
                    )
                else:
                    features.extend([0, 1.0, 0.5])
            else:
                features = [0, 0, 0.5, 0, 1.0, 0.5]

            # Pad or trim to fixed size
            target_size = 10
            while len(features) < target_size:
                features.append(0.0)
            features = features[:target_size]

            return np.array(features)

        except Exception as e:
            logger.warning(f"Error extracting wave features: {str(e)}")
            return np.array([0.0] * 10)

    def _extract_microstructure_features(self, price_data: pd.DataFrame) -> np.ndarray:
        """Extract market microstructure features."""
        features = []

        # Bid-ask spread proxy (high-low range)
        ranges = price_data["high"] - price_data["low"]
        avg_range = np.mean(ranges[-20:]) if len(ranges) >= 20 else 0
        features.append(avg_range)

        # Tick direction and momentum
        price_changes = np.diff(price_data["close"].values)
        if len(price_changes) >= 10:
            up_ticks = np.sum(price_changes[-10:] > 0)
            down_ticks = np.sum(price_changes[-10:] < 0)
            tick_imbalance = (up_ticks - down_ticks) / 10.0
            features.append(tick_imbalance)

            # Price momentum concentration
            momentum_concentration = (
                np.std(price_changes[-20:]) if len(price_changes) >= 20 else 0
            )
            features.append(momentum_concentration)
        else:
            features.extend([0.0, 0.0])

        # Intraday patterns
        if "datetime" in price_data.columns:
            hours = pd.to_datetime(price_data["datetime"]).dt.hour
            # Session features (London: 8-16, NY: 13-21, Tokyo: 0-9)
            london_activity = np.mean([(8 <= h <= 16) for h in hours[-20:]])
            ny_activity = np.mean([(13 <= h <= 21) for h in hours[-20:]])
            tokyo_activity = np.mean([(0 <= h <= 9) for h in hours[-20:]])
            features.extend([london_activity, ny_activity, tokyo_activity])
        else:
            features.extend([0.33, 0.33, 0.33])

        return np.array(features)

    def _extract_volatility_features(self, price_data: pd.DataFrame) -> np.ndarray:
        """Extract volatility regime features."""
        features = []

        close_prices = price_data["close"].values
        returns = np.diff(np.log(close_prices))

        if len(returns) >= 20:
            # Realized volatility
            realized_vol = np.std(returns[-20:]) * np.sqrt(252)
            features.append(realized_vol)

            # Volatility clustering (GARCH-like measure)
            squared_returns = returns**2
            vol_persistence = np.corrcoef(
                squared_returns[-20:-1], squared_returns[-19:]
            )[0, 1]
            features.append(vol_persistence if not np.isnan(vol_persistence) else 0.0)

            # Jump detection
            jump_threshold = 3 * np.std(returns[-100:]) if len(returns) >= 100 else 0.01
            jumps = np.sum(np.abs(returns[-20:]) > jump_threshold)
            features.append(jumps / 20.0)

            # Volatility skew
            vol_skew = np.mean(returns[-20:] ** 3) / (np.std(returns[-20:]) ** 3)
            features.append(vol_skew if not np.isnan(vol_skew) else 0.0)
        else:
            features = [0.1, 0.0, 0.0, 0.0]

        return np.array(features)

    def _predict_regime(self, features: np.ndarray) -> Dict[MarketRegimeType, float]:
        """Predict market regime probabilities."""
        if self.regime_classifier is None:
            # Return uniform distribution if model not trained
            regimes = list(MarketRegimeType)
            return {regime: 1.0 / len(regimes) for regime in regimes}

        try:
            # Preprocess features
            features_scaled = self.scaler.transform(features.reshape(1, -1))
            features_pca = self.pca.transform(features_scaled)

            # Get probabilities
            probs = self.regime_classifier.predict_proba(features_pca)[0]

            # Map to regime types
            regime_types = list(MarketRegimeType)
            regime_probs = {}

            for i, prob in enumerate(probs):
                if i < len(regime_types):
                    regime_probs[regime_types[i]] = prob

            return regime_probs

        except Exception as e:
            logger.error(f"Error predicting regime: {str(e)}")
            # Return default probabilities
            regimes = list(MarketRegimeType)
            return {regime: 1.0 / len(regimes) for regime in regimes}

    def _analyze_regime_characteristics(
        self, features: np.ndarray
    ) -> RegimeCharacteristics:
        """Analyze detailed characteristics of the current regime."""
        # Extract specific characteristics from features
        # This is a simplified implementation - in practice, you'd use
        # more sophisticated analysis

        feature_len = len(features)

        # Map features to characteristics (simplified)
        volatility_level = np.mean(
            features[int(feature_len * 0.6) : int(feature_len * 0.7)]
        )
        trend_strength = np.mean(
            features[int(feature_len * 0.2) : int(feature_len * 0.4)]
        )
        momentum = np.mean(features[int(feature_len * 0.4) : int(feature_len * 0.5)])
        volume_profile = np.mean(
            features[int(feature_len * 0.5) : int(feature_len * 0.6)]
        )
        sentiment_bias = np.mean(
            features[int(feature_len * 0.1) : int(feature_len * 0.2)]
        )
        wave_structure_quality = np.mean(
            features[int(feature_len * 0.7) : int(feature_len * 0.8)]
        )

        return RegimeCharacteristics(
            volatility_level=float(np.clip(volatility_level, 0, 1)),
            trend_strength=float(np.clip(trend_strength, 0, 1)),
            momentum=float(np.clip(momentum, -1, 1)),
            volume_profile=float(np.clip(volume_profile, 0, 2)),
            sentiment_bias=float(np.clip(sentiment_bias, 0, 1)),
            wave_structure_quality=float(np.clip(wave_structure_quality, 0, 1)),
            duration_stability=0.7,  # Placeholder - would be calculated from history
            reversion_tendency=0.3,  # Placeholder - would be calculated from transition matrix
        )

    def _predict_transitions(
        self, features: np.ndarray, current_regime: MarketRegimeType
    ) -> Dict[MarketRegimeType, float]:
        """Predict transition probabilities to other regimes."""
        if self.transition_model is None:
            # Return uniform distribution
            regimes = [r for r in MarketRegimeType if r != current_regime]
            return {regime: 1.0 / len(regimes) for regime in regimes}

        try:
            # Preprocess features
            features_scaled = self.scaler.transform(features.reshape(1, -1))
            features_pca = self.pca.transform(features_scaled)

            # Predict transition probabilities
            transition_probs = self.transition_model.predict_proba(features_pca)[0]

            # Map to regime types
            regime_types = [r for r in MarketRegimeType if r != current_regime]
            transition_dict = {}

            for i, prob in enumerate(transition_probs):
                if i < len(regime_types):
                    transition_dict[regime_types[i]] = prob

            return transition_dict

        except Exception as e:
            logger.error(f"Error predicting transitions: {str(e)}")
            regimes = [r for r in MarketRegimeType if r != current_regime]
            return {regime: 1.0 / len(regimes) for regime in regimes}

    def _detect_anomalies(self, features: np.ndarray) -> bool:
        """Detect if current market conditions are anomalous."""
        if self.anomaly_detector is None:
            return False

        try:
            features_scaled = self.scaler.transform(features.reshape(1, -1))
            features_pca = self.pca.transform(features_scaled)

            anomaly_score = self.anomaly_detector.decision_function(features_pca)[0]
            is_anomaly = anomaly_score < -self.config["anomaly_threshold"]

            return is_anomaly

        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}")
            return False

    def _analyze_evidence_and_risks(
        self,
        features: np.ndarray,
        regime: MarketRegimeType,
        characteristics: RegimeCharacteristics,
        is_anomalous: bool,
    ) -> Tuple[List[str], List[str]]:
        """Analyze supporting evidence and risk factors."""
        evidence = []
        risks = []

        # Evidence based on characteristics
        if characteristics.trend_strength > 0.7:
            evidence.append(
                f"Strong trend strength ({characteristics.trend_strength:.2f})"
            )

        if characteristics.volatility_level < 0.3:
            evidence.append("Low volatility environment supports regime stability")
        elif characteristics.volatility_level > 0.7:
            evidence.append("High volatility confirms dynamic regime")

        if characteristics.wave_structure_quality > 0.8:
            evidence.append("High-quality Elliott Wave patterns support classification")

        if abs(characteristics.momentum) > 0.6:
            direction = "bullish" if characteristics.momentum > 0 else "bearish"
            evidence.append(
                f"Strong {direction} momentum ({characteristics.momentum:.2f})"
            )

        # Risk factors
        if is_anomalous:
            risks.append(
                "Anomalous market conditions detected - regime may be unstable"
            )

        if characteristics.volatility_level > 0.8:
            risks.append(
                "Extremely high volatility increases regime change probability"
            )

        if characteristics.duration_stability < 0.5:
            risks.append("Low duration stability suggests potential regime shift")

        if characteristics.reversion_tendency > 0.7:
            risks.append("High reversion tendency - regime may reverse soon")

        # Regime-specific risks
        if regime in [MarketRegimeType.BREAKOUT_BULL, MarketRegimeType.BREAKOUT_BEAR]:
            risks.append("Breakout regimes are typically short-lived")

        if regime == MarketRegimeType.CRISIS_MODE:
            risks.append("Crisis mode regime - extreme caution advised")

        return evidence, risks

    async def _get_llm_regime_analysis(
        self,
        symbol: str,
        regime: MarketRegimeType,
        characteristics: RegimeCharacteristics,
        evidence: List[str],
        risks: List[str],
    ) -> Dict[str, Any]:
        """Get LLM analysis and explanation of the regime."""
        try:
            prompt = f"""
            Analyze the current market regime for {symbol}:

            Detected Regime: {regime.value}
            Confidence Characteristics:
            - Volatility Level: {characteristics.volatility_level:.2f}
            - Trend Strength: {characteristics.trend_strength:.2f}
            - Momentum: {characteristics.momentum:.2f}
            - Sentiment Bias: {characteristics.sentiment_bias:.2f}
            - Wave Structure Quality: {characteristics.wave_structure_quality:.2f}

            Supporting Evidence:
            {chr(10).join(f"- {e}" for e in evidence)}

            Risk Factors:
            {chr(10).join(f"- {r}" for r in risks)}

            Please provide:
            1. A clear explanation of what this regime means for traders
            2. 3-5 actionable insights based on this regime
            3. Key factors to monitor for regime changes

            Keep the response concise and practical.
            """

            response = await self.llm_client.generate_completion(
                prompt=prompt, max_tokens=500, temperature=0.3
            )

            # Parse response (simplified - in practice, you'd use structured parsing)
            lines = response.split("\n")
            explanation = ""
            insights = []

            current_section = "explanation"
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if "actionable insights" in line.lower():
                    current_section = "insights"
                    continue
                elif "factors to monitor" in line.lower():
                    current_section = "monitoring"
                    continue

                if current_section == "explanation":
                    explanation += line + " "
                elif current_section == "insights" and line.startswith("-"):
                    insights.append(line[1:].strip())

            return {"explanation": explanation.strip(), "insights": insights}

        except Exception as e:
            logger.error(f"Error getting LLM regime analysis: {str(e)}")
            return {
                "explanation": f"Market is in {regime.value} regime with {characteristics.trend_strength:.0%} trend strength.",
                "insights": [
                    "Monitor for regime changes",
                    "Adjust position sizing accordingly",
                ],
            }

    def _get_current_regime_duration(self) -> int:
        """Get duration of current regime in minutes."""
        if self.regime_start_time is None:
            return 0

        return int((datetime.now() - self.regime_start_time).total_seconds() / 60)

    def _estimate_regime_duration(
        self, regime: MarketRegimeType, characteristics: RegimeCharacteristics
    ) -> int:
        """Estimate expected duration of regime in minutes."""
        # Base durations by regime type (in minutes)
        base_durations = {
            MarketRegimeType.TRENDING_BULL: 480,  # 8 hours
            MarketRegimeType.TRENDING_BEAR: 360,  # 6 hours
            MarketRegimeType.RANGING_LOW_VOL: 720,  # 12 hours
            MarketRegimeType.RANGING_HIGH_VOL: 240,  # 4 hours
            MarketRegimeType.VOLATILE_UNCERTAIN: 120,  # 2 hours
            MarketRegimeType.BREAKOUT_BULL: 60,  # 1 hour
            MarketRegimeType.BREAKOUT_BEAR: 60,  # 1 hour
            MarketRegimeType.CRISIS_MODE: 180,  # 3 hours
        }

        base_duration = base_durations.get(regime, 240)

        # Adjust based on characteristics
        stability_factor = characteristics.duration_stability
        volatility_factor = 1.0 - characteristics.volatility_level * 0.5

        adjusted_duration = base_duration * stability_factor * volatility_factor

        return int(
            max(30, min(1440, adjusted_duration))
        )  # Clamp between 30 min and 24 hours

    def _update_regime_tracking(self, detection: RegimeDetection):
        """Update internal regime tracking."""
        # Check if regime changed
        if self.current_regime != detection.regime_type:
            # Store previous regime in history
            if self.current_regime is not None:
                duration = self._get_current_regime_duration()
                self.regime_history.append(
                    {
                        "regime": self.current_regime,
                        "duration": duration,
                        "end_time": datetime.now(),
                    }
                )

            # Update current regime
            self.current_regime = detection.regime_type
            self.regime_start_time = datetime.now()

        # Keep history manageable
        if len(self.regime_history) > 100:
            self.regime_history = self.regime_history[-50:]

    async def _store_detection_result(
        self, symbol: str, timeframe: str, detection: RegimeDetection
    ):
        """Store detection result in database."""
        try:
            result_data = {
                "symbol": symbol,
                "timeframe": timeframe,
                "regime_type": detection.regime_type.value,
                "confidence": detection.confidence,
                "characteristics": {
                    "volatility_level": detection.characteristics.volatility_level,
                    "trend_strength": detection.characteristics.trend_strength,
                    "momentum": detection.characteristics.momentum,
                    "volume_profile": detection.characteristics.volume_profile,
                    "sentiment_bias": detection.characteristics.sentiment_bias,
                    "wave_structure_quality": detection.characteristics.wave_structure_quality,
                    "duration_stability": detection.characteristics.duration_stability,
                    "reversion_tendency": detection.characteristics.reversion_tendency,
                },
                "duration_minutes": detection.duration_minutes,
                "expected_duration": detection.expected_duration,
                "supporting_evidence": detection.supporting_evidence,
                "risk_factors": detection.risk_factors,
                "llm_explanation": detection.llm_explanation,
                "actionable_insights": detection.actionable_insights,
                "timestamp": datetime.now(),
            }

            await self.db_manager.store_regime_detection(result_data)

        except Exception as e:
            logger.error(f"Error storing detection result: {str(e)}")

    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return np.mean(prices)

        multiplier = 2.0 / (period + 1)
        ema = prices[0]

        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1 + rs))

        return rsi

    async def train_models(self, symbol_list: List[str], lookback_days: int = 365):
        """Train regime detection models on historical data."""
        logger.info(f"Training regime detection models on {len(symbol_list)} symbols")

        try:
            # Collect training data
            training_features = []
            training_labels = []

            for symbol in symbol_list:
                logger.info(f"Collecting training data for {symbol}")

                # Get historical data
                end_time = datetime.now()
                start_time = end_time - timedelta(days=lookback_days)

                price_data = await self.db_manager.get_market_data(
                    symbol=symbol,
                    start_time=start_time,
                    end_time=end_time,
                    timeframe="4h",
                )

                if len(price_data) < 500:
                    logger.warning(
                        f"Insufficient data for {symbol}: {len(price_data)} bars"
                    )
                    continue

                # Extract features and labels for training
                symbol_features, symbol_labels = await self._prepare_training_data(
                    price_data
                )

                training_features.extend(symbol_features)
                training_labels.extend(symbol_labels)

            if len(training_features) < 1000:
                raise ValueError(
                    f"Insufficient training data: {len(training_features)} samples"
                )

            # Convert to numpy arrays
            X = np.array(training_features)
            y = np.array(training_labels)

            logger.info(f"Training with {len(X)} samples, {X.shape[1]} features")

            # Fit preprocessors
            self.scaler.fit(X)
            X_scaled = self.scaler.transform(X)

            self.pca.fit(X_scaled)
            X_pca = self.pca.transform(X_scaled)

            # Train models
            self.regime_classifier.fit(X_pca, y)
            self.anomaly_detector.fit(X_pca)

            # Train transition model (simplified)
            transition_X, transition_y = self._prepare_transition_data(X_pca, y)
            if len(transition_X) > 0:
                self.transition_model.fit(transition_X, transition_y)

            # Save models
            self._save_models()

            logger.info("Model training completed successfully")

        except Exception as e:
            logger.error(f"Error training models: {str(e)}")
            raise

    async def _prepare_training_data(
        self, price_data: pd.DataFrame
    ) -> Tuple[List[np.ndarray], List[str]]:
        """Prepare training data with features and regime labels."""
        features = []
        labels = []

        # Use sliding window approach
        window_size = 200  # Minimum data needed for feature extraction

        for i in range(window_size, len(price_data)):
            window_data = price_data.iloc[i - window_size : i]

            try:
                # Extract features for this window
                window_features = await self._get_regime_features_from_data(window_data)

                # Manually label regime (simplified - in practice, use expert labeling)
                regime_label = self._manual_regime_labeling(window_data)

                features.append(window_features)
                labels.append(regime_label)

            except Exception as e:
                logger.warning(f"Error preparing training sample {i}: {str(e)}")
                continue

        return features, labels

    async def _get_regime_features_from_data(
        self, price_data: pd.DataFrame
    ) -> np.ndarray:
        """Extract features from a specific data window."""
        # Simplified version of _get_regime_features for historical data
        technical_features = self._extract_technical_features(price_data)

        # For historical data, use simulated sentiment and wave features
        sentiment_features = np.array([0.5, 0.5, 0.5, 0.0, 0.0, 0.0])
        wave_features = np.array([0.0] * 10)
        microstructure_features = self._extract_microstructure_features(price_data)
        volatility_features = self._extract_volatility_features(price_data)

        return np.concatenate(
            [
                technical_features,
                sentiment_features,
                wave_features,
                microstructure_features,
                volatility_features,
            ]
        )

    def _manual_regime_labeling(self, price_data: pd.DataFrame) -> str:
        """Manual regime labeling based on technical analysis."""
        # Simplified labeling logic - in practice, use expert domain knowledge
        close_prices = price_data["close"].values

        # Calculate basic indicators
        sma_20 = np.mean(close_prices[-20:])
        sma_50 = np.mean(close_prices[-50:]) if len(close_prices) >= 50 else sma_20

        returns = np.diff(np.log(close_prices))
        volatility = np.std(returns[-20:]) if len(returns) >= 20 else 0.01

        trend = (close_prices[-1] - close_prices[-20]) / close_prices[-20]

        # Simple labeling rules
        if volatility > 0.02:  # High volatility
            if abs(trend) < 0.01:
                return MarketRegimeType.VOLATILE_UNCERTAIN.value
            else:
                return MarketRegimeType.CRISIS_MODE.value
        elif abs(trend) > 0.05:  # Strong trend
            if trend > 0:
                return MarketRegimeType.TRENDING_BULL.value
            else:
                return MarketRegimeType.TRENDING_BEAR.value
        elif abs(trend) > 0.02:  # Medium trend
            if trend > 0:
                return MarketRegimeType.BREAKOUT_BULL.value
            else:
                return MarketRegimeType.BREAKOUT_BEAR.value
        else:  # Low trend
            if volatility < 0.005:
                return MarketRegimeType.RANGING_LOW_VOL.value
            else:
                return MarketRegimeType.RANGING_HIGH_VOL.value

    def _prepare_transition_data(
        self, features: np.ndarray, labels: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare data for training transition model."""
        transition_features = []
        transition_labels = []

        # Create transition examples
        for i in range(len(labels) - 1):
            if labels[i] != labels[i + 1]:  # Regime transition occurred
                transition_features.append(features[i])
                transition_labels.append(labels[i + 1])

        return np.array(transition_features), np.array(transition_labels)

    def _save_models(self):
        """Save trained models to disk."""
        import os

        os.makedirs("models", exist_ok=True)

        joblib.dump(self.regime_classifier, "models/regime_classifier.pkl")
        joblib.dump(self.anomaly_detector, "models/anomaly_detector.pkl")
        joblib.dump(self.transition_model, "models/transition_model.pkl")
        joblib.dump(self.scaler, "models/regime_scaler.pkl")
        joblib.dump(self.pca, "models/regime_pca.pkl")

        logger.info("Models saved successfully")

    async def get_regime_summary(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive regime analysis summary."""
        try:
            detection = await self.detect_regime(symbol)

            return {
                "symbol": symbol,
                "current_regime": detection.regime_type.value,
                "confidence": detection.confidence,
                "duration_minutes": detection.duration_minutes,
                "expected_duration": detection.expected_duration,
                "characteristics": {
                    "volatility_level": detection.characteristics.volatility_level,
                    "trend_strength": detection.characteristics.trend_strength,
                    "momentum": detection.characteristics.momentum,
                    "sentiment_bias": detection.characteristics.sentiment_bias,
                },
                "transition_risk": (
                    max(detection.transition_probability.values())
                    if detection.transition_probability
                    else 0.0
                ),
                "key_insights": detection.actionable_insights[:3],
                "risk_level": (
                    "high"
                    if len(detection.risk_factors) > 2
                    else "medium" if len(detection.risk_factors) > 0 else "low"
                ),
                "last_updated": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting regime summary: {str(e)}")
            return {
                "symbol": symbol,
                "current_regime": "unknown",
                "confidence": 0.0,
                "error": str(e),
            }
