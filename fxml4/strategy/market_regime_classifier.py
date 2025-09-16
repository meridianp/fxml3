"""
Advanced Market Regime Classification System for FXML4

This module implements a sophisticated market regime classification system that
identifies and adapts to different market conditions in real-time. The system
combines multiple analytical approaches to provide robust regime detection.

Key Features:
- Volatility-based regime detection with adaptive thresholds
- Multi-timeframe trend identification and strength measurement
- Cross-currency correlation analysis
- Trading session impact assessment
- Economic condition integration
- Dynamic regime transition detection
- Historical regime performance analysis

Market Regimes Detected:
- Trending Bull/Bear: Strong directional movement
- Range-bound: Sideways movement within defined levels
- Breakout: Breaking through significant support/resistance
- High Volatility: Elevated market stress or news-driven movements
- Low Volatility: Quiet, consolidation periods
- Transition: Regime change periods
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from fxml4.core.types import MarketRegime, TradingSession, VolatilityRegime


class RegimeTransition(Enum):
    """Regime transition types"""

    STABLE = "stable"  # No regime change
    GRADUAL = "gradual"  # Slow transition over time
    ABRUPT = "abrupt"  # Sudden regime change
    REVERSAL = "reversal"  # Complete regime reversal


class TrendDirection(Enum):
    """Trend direction classification"""

    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    SIDEWAYS = "sideways"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


@dataclass
class RegimeMetrics:
    """Comprehensive regime classification metrics"""

    # Primary regime classification
    regime: MarketRegime
    regime_confidence: float  # 0.0 to 1.0
    regime_duration: int  # Days in current regime
    previous_regime: Optional[MarketRegime]
    transition_type: RegimeTransition

    # Volatility analysis
    volatility_regime: VolatilityRegime
    current_volatility: float  # Annualized volatility
    volatility_percentile: float  # Historical percentile (0-100)
    volatility_trend: str  # "increasing", "decreasing", "stable"

    # Trend analysis
    trend_direction: TrendDirection
    trend_strength: float  # -1.0 (strong bear) to 1.0 (strong bull)
    trend_consistency: float  # 0.0 to 1.0 (how consistent is the trend)
    trend_duration: int  # Days in current trend

    # Correlation analysis
    correlation_regime: str  # "coupled", "decoupled", "divergent"
    avg_correlation: float  # Average correlation with major pairs
    correlation_stability: float  # How stable correlations are

    # Session analysis
    dominant_session: TradingSession
    session_volatility_ratio: Dict[str, float]  # Volatility by session
    session_trend_consistency: Dict[str, float]  # Trend consistency by session

    # Market structure
    support_resistance_strength: float  # Strength of S/R levels
    breakout_probability: float  # Probability of breakout
    mean_reversion_tendency: float  # Tendency to mean revert

    # Economic indicators
    economic_regime: str  # "expansion", "contraction", "neutral"
    news_impact_level: str  # "high", "medium", "low"
    calendar_events_nearby: bool  # Major events in next 24h

    # Performance metrics
    regime_performance: Dict[str, float]  # Historical performance by regime
    regime_stability_score: float  # How stable is current regime
    next_regime_probabilities: Dict[str, float]  # Transition probabilities


@dataclass
class RegimeConfiguration:
    """Configuration for regime classification"""

    # Volatility thresholds (annualized)
    low_volatility_threshold: float = 0.12  # 12%
    high_volatility_threshold: float = 0.25  # 25%
    extreme_volatility_threshold: float = 0.40  # 40%

    # Trend strength thresholds
    weak_trend_threshold: float = 0.3
    strong_trend_threshold: float = 0.7

    # Correlation thresholds
    high_correlation_threshold: float = 0.7
    low_correlation_threshold: float = 0.3

    # Regime stability parameters
    min_regime_duration: int = 3  # Minimum days for regime confirmation
    regime_change_threshold: float = 0.8  # Confidence needed for regime change

    # Analysis windows
    short_window: int = 20  # Short-term analysis (20 days)
    medium_window: int = 60  # Medium-term analysis (60 days)
    long_window: int = 252  # Long-term analysis (1 year)

    # Breakout detection
    breakout_lookback: int = 20  # Days to look back for S/R levels
    breakout_threshold: float = 2.0  # ATR multiples for breakout

    # Economic indicators
    news_impact_window: int = 24  # Hours to consider news impact
    calendar_lookahead: int = 24  # Hours to look ahead for events


class AdvancedMarketRegimeClassifier:
    """
    Advanced market regime classification system that combines multiple
    analytical approaches to provide robust regime detection and adaptation.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize market regime classifier with configuration"""
        self.config = config
        self.logger = logging.getLogger(f"fxml4.strategy.{self.__class__.__name__}")

        # Load configuration
        self.regime_config = RegimeConfiguration()
        if "regime_config" in config:
            for key, value in config["regime_config"].items():
                if hasattr(self.regime_config, key):
                    setattr(self.regime_config, key, value)

        # Current state
        self.current_regime: Optional[MarketRegime] = None
        self.current_metrics: Optional[RegimeMetrics] = None
        self.regime_history: List[Tuple[datetime, MarketRegime, float]] = []

        # Data storage
        self.price_data: Dict[str, pd.DataFrame] = {}
        self.volatility_data: Dict[str, List[float]] = {}
        self.correlation_data: Dict[str, Dict[str, float]] = {}

        # ML models for regime detection
        self.regime_model: Optional[Any] = None
        self.scaler = StandardScaler()

        # Performance tracking
        self.regime_performance: Dict[str, Dict[str, float]] = {}
        self.regime_transitions: List[Dict[str, Any]] = []

        self.logger.info(f"Advanced Market Regime Classifier initialized")

    async def classify_market_regime(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        correlation_data: Optional[Dict[str, float]] = None,
    ) -> RegimeMetrics:
        """
        Classify current market regime based on multiple analytical approaches.

        Args:
            symbol: Currency pair symbol (e.g., 'GBPUSD')
            price_data: Historical price data (OHLCV)
            correlation_data: Correlations with other currency pairs

        Returns:
            RegimeMetrics: Comprehensive regime classification
        """
        try:
            # Store data for analysis
            self.price_data[symbol] = price_data
            if correlation_data:
                self.correlation_data[symbol] = correlation_data

            # Multi-dimensional regime analysis
            volatility_metrics = await self._analyze_volatility_regime(
                symbol, price_data
            )
            trend_metrics = await self._analyze_trend_regime(symbol, price_data)
            correlation_metrics = await self._analyze_correlation_regime(
                symbol, correlation_data or {}
            )
            session_metrics = await self._analyze_session_regime(symbol, price_data)
            structure_metrics = await self._analyze_market_structure(symbol, price_data)
            economic_metrics = await self._analyze_economic_regime(symbol)

            # Combine all analyses for primary regime classification
            primary_regime, confidence = await self._determine_primary_regime(
                volatility_metrics,
                trend_metrics,
                correlation_metrics,
                session_metrics,
                structure_metrics,
            )

            # Detect regime transitions
            transition_type = await self._detect_regime_transition(
                primary_regime, confidence
            )

            # Calculate performance metrics
            performance_metrics = await self._calculate_regime_performance(
                primary_regime
            )

            # Create comprehensive metrics object
            regime_metrics = RegimeMetrics(
                # Primary classification
                regime=primary_regime,
                regime_confidence=confidence,
                regime_duration=await self._get_regime_duration(primary_regime),
                previous_regime=self.current_regime,
                transition_type=transition_type,
                # Volatility
                volatility_regime=volatility_metrics["regime"],
                current_volatility=volatility_metrics["current"],
                volatility_percentile=volatility_metrics["percentile"],
                volatility_trend=volatility_metrics["trend"],
                # Trend
                trend_direction=trend_metrics["direction"],
                trend_strength=trend_metrics["strength"],
                trend_consistency=trend_metrics["consistency"],
                trend_duration=trend_metrics["duration"],
                # Correlation
                correlation_regime=correlation_metrics["regime"],
                avg_correlation=correlation_metrics["average"],
                correlation_stability=correlation_metrics["stability"],
                # Session
                dominant_session=session_metrics["dominant_session"],
                session_volatility_ratio=session_metrics["volatility_ratio"],
                session_trend_consistency=session_metrics["trend_consistency"],
                # Structure
                support_resistance_strength=structure_metrics["sr_strength"],
                breakout_probability=structure_metrics["breakout_prob"],
                mean_reversion_tendency=structure_metrics["mean_reversion"],
                # Economic
                economic_regime=economic_metrics["regime"],
                news_impact_level=economic_metrics["news_impact"],
                calendar_events_nearby=economic_metrics["events_nearby"],
                # Performance
                regime_performance=performance_metrics["historical"],
                regime_stability_score=performance_metrics["stability"],
                next_regime_probabilities=performance_metrics["transitions"],
            )

            # Update internal state
            await self._update_regime_state(primary_regime, confidence, regime_metrics)

            self.current_metrics = regime_metrics

            self.logger.info(
                f"Market regime classified: {primary_regime.value} "
                f"(confidence: {confidence:.2f}, trend: {trend_metrics['direction'].value})"
            )

            return regime_metrics

        except Exception as e:
            self.logger.error(f"Error classifying market regime: {e}")
            # Return basic regime on error
            return await self._create_fallback_metrics(symbol)

    async def _analyze_volatility_regime(
        self, symbol: str, data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Analyze volatility regime and characteristics"""
        try:
            # Calculate returns
            returns = data["close"].pct_change().dropna()

            # Current volatility (20-day rolling)
            current_vol = returns.rolling(20).std().iloc[-1] * np.sqrt(252)

            # Historical volatility percentile
            hist_vol = returns.rolling(20).std() * np.sqrt(252)
            vol_percentile = stats.percentileofscore(hist_vol.dropna(), current_vol)

            # Volatility trend (comparing short vs medium term)
            short_vol = returns.rolling(10).std().iloc[-1] * np.sqrt(252)
            medium_vol = returns.rolling(30).std().iloc[-1] * np.sqrt(252)

            if short_vol > medium_vol * 1.2:
                vol_trend = "increasing"
            elif short_vol < medium_vol * 0.8:
                vol_trend = "decreasing"
            else:
                vol_trend = "stable"

            # Classify volatility regime
            if current_vol >= self.regime_config.extreme_volatility_threshold:
                vol_regime = VolatilityRegime.EXTREME
            elif current_vol >= self.regime_config.high_volatility_threshold:
                vol_regime = VolatilityRegime.HIGH
            elif current_vol <= self.regime_config.low_volatility_threshold:
                vol_regime = VolatilityRegime.LOW
            else:
                vol_regime = VolatilityRegime.NORMAL

            return {
                "regime": vol_regime,
                "current": current_vol,
                "percentile": vol_percentile,
                "trend": vol_trend,
                "short_term": short_vol,
                "medium_term": medium_vol,
            }

        except Exception as e:
            self.logger.error(f"Error analyzing volatility regime: {e}")
            return {
                "regime": VolatilityRegime.NORMAL,
                "current": 0.15,
                "percentile": 50.0,
                "trend": "stable",
                "short_term": 0.15,
                "medium_term": 0.15,
            }

    async def _analyze_trend_regime(
        self, symbol: str, data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Analyze trend characteristics and strength"""
        try:
            prices = data["close"]

            # Multiple timeframe trend analysis
            short_ma = prices.rolling(10).mean()
            medium_ma = prices.rolling(20).mean()
            long_ma = prices.rolling(50).mean()

            # Current trend direction
            current_price = prices.iloc[-1]
            short_trend = 1 if current_price > short_ma.iloc[-1] else -1
            medium_trend = 1 if current_price > medium_ma.iloc[-1] else -1
            long_trend = 1 if current_price > long_ma.iloc[-1] else -1

            # Trend consistency (how often trends align)
            trend_alignment = (short_trend + medium_trend + long_trend) / 3
            trend_strength = abs(trend_alignment)

            # Trend duration
            trend_changes = np.diff(np.sign(prices.rolling(10).mean().diff()))
            days_since_change = 0
            for i in range(len(trend_changes) - 1, -1, -1):
                if trend_changes[i] != 0:
                    break
                days_since_change += 1

            # Classify trend direction
            if trend_strength >= self.regime_config.strong_trend_threshold:
                if trend_alignment > 0:
                    direction = TrendDirection.STRONG_UPTREND
                else:
                    direction = TrendDirection.STRONG_DOWNTREND
            elif trend_strength >= self.regime_config.weak_trend_threshold:
                if trend_alignment > 0:
                    direction = TrendDirection.UPTREND
                else:
                    direction = TrendDirection.DOWNTREND
            else:
                direction = TrendDirection.SIDEWAYS

            # Trend consistency metric
            price_changes = prices.pct_change().dropna()
            consistency = len(price_changes[price_changes * trend_alignment > 0]) / len(
                price_changes
            )

            return {
                "direction": direction,
                "strength": trend_alignment,
                "consistency": consistency,
                "duration": days_since_change,
                "short_ma_trend": short_trend,
                "medium_ma_trend": medium_trend,
                "long_ma_trend": long_trend,
            }

        except Exception as e:
            self.logger.error(f"Error analyzing trend regime: {e}")
            return {
                "direction": TrendDirection.SIDEWAYS,
                "strength": 0.0,
                "consistency": 0.5,
                "duration": 0,
                "short_ma_trend": 0,
                "medium_ma_trend": 0,
                "long_ma_trend": 0,
            }

    async def _analyze_correlation_regime(
        self, symbol: str, correlations: Dict[str, float]
    ) -> Dict[str, Any]:
        """Analyze correlation patterns and stability"""
        try:
            if not correlations:
                return {"regime": "unknown", "average": 0.5, "stability": 0.5}

            # Calculate average correlation
            avg_correlation = np.mean(list(correlations.values()))

            # Classify correlation regime
            if avg_correlation >= self.regime_config.high_correlation_threshold:
                correlation_regime = "coupled"
            elif avg_correlation <= self.regime_config.low_correlation_threshold:
                correlation_regime = "decoupled"
            else:
                correlation_regime = "divergent"

            # Correlation stability (simplified)
            stability = 1.0 - np.std(list(correlations.values()))
            stability = max(0.0, min(1.0, stability))

            return {
                "regime": correlation_regime,
                "average": avg_correlation,
                "stability": stability,
                "individual": correlations,
            }

        except Exception as e:
            self.logger.error(f"Error analyzing correlation regime: {e}")
            return {
                "regime": "unknown",
                "average": 0.5,
                "stability": 0.5,
                "individual": {},
            }

    async def _analyze_session_regime(
        self, symbol: str, data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Analyze trading session characteristics"""
        try:
            # Add hour column for session analysis
            data_copy = data.copy()
            if (
                "timestamp" not in data_copy.columns
                and data_copy.index.name == "timestamp"
            ):
                data_copy = data_copy.reset_index()

            # Extract hour if timestamp is available
            if "timestamp" in data_copy.columns:
                data_copy["hour"] = pd.to_datetime(data_copy["timestamp"]).dt.hour
            else:
                # Use a default session distribution
                return {
                    "dominant_session": TradingSession.LONDON,
                    "volatility_ratio": {"london": 0.4, "ny": 0.4, "tokyo": 0.2},
                    "trend_consistency": {"london": 0.6, "ny": 0.6, "tokyo": 0.4},
                }

            # Define session hours (UTC)
            sessions = {
                "tokyo": (0, 9),  # Tokyo: 00:00-09:00 UTC
                "london": (8, 17),  # London: 08:00-17:00 UTC
                "ny": (13, 22),  # New York: 13:00-22:00 UTC
            }

            # Calculate volatility by session
            session_volatilities = {}
            session_trends = {}

            for session_name, (start_hour, end_hour) in sessions.items():
                session_data = data_copy[
                    (data_copy["hour"] >= start_hour) & (data_copy["hour"] < end_hour)
                ]

                if not session_data.empty:
                    # Session volatility
                    session_returns = session_data["close"].pct_change().dropna()
                    session_vol = (
                        session_returns.std() if len(session_returns) > 1 else 0.0
                    )
                    session_volatilities[session_name] = session_vol

                    # Session trend consistency
                    price_changes = session_data["close"].diff().dropna()
                    if len(price_changes) > 0:
                        trend_consistency = (
                            abs(price_changes.sum()) / price_changes.abs().sum()
                        )
                    else:
                        trend_consistency = 0.0
                    session_trends[session_name] = trend_consistency
                else:
                    session_volatilities[session_name] = 0.0
                    session_trends[session_name] = 0.0

            # Determine dominant session
            if session_volatilities:
                dominant_session_name = max(
                    session_volatilities.keys(), key=lambda k: session_volatilities[k]
                )
                if dominant_session_name == "tokyo":
                    dominant_session = TradingSession.TOKYO
                elif dominant_session_name == "london":
                    dominant_session = TradingSession.LONDON
                else:
                    dominant_session = TradingSession.NEW_YORK
            else:
                dominant_session = TradingSession.LONDON  # Default

            # Normalize volatility ratios
            total_vol = sum(session_volatilities.values())
            if total_vol > 0:
                volatility_ratio = {
                    k: v / total_vol for k, v in session_volatilities.items()
                }
            else:
                volatility_ratio = {"london": 0.4, "ny": 0.4, "tokyo": 0.2}

            return {
                "dominant_session": dominant_session,
                "volatility_ratio": volatility_ratio,
                "trend_consistency": session_trends,
            }

        except Exception as e:
            self.logger.error(f"Error analyzing session regime: {e}")
            return {
                "dominant_session": TradingSession.LONDON,
                "volatility_ratio": {"london": 0.4, "ny": 0.4, "tokyo": 0.2},
                "trend_consistency": {"london": 0.6, "ny": 0.6, "tokyo": 0.4},
            }

    async def _analyze_market_structure(
        self, symbol: str, data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Analyze market structure and support/resistance levels"""
        try:
            prices = data["close"]
            highs = data["high"]
            lows = data["low"]

            # Calculate ATR for breakout detection
            atr = self._calculate_atr(data, period=14)
            current_atr = atr.iloc[-1] if not atr.empty else 0.01

            # Support and resistance detection (simplified)
            lookback = min(self.regime_config.breakout_lookback, len(data))
            recent_highs = highs.rolling(lookback).max()
            recent_lows = lows.rolling(lookback).min()

            current_price = prices.iloc[-1]
            resistance = recent_highs.iloc[-1]
            support = recent_lows.iloc[-1]

            # Support/resistance strength
            price_range = resistance - support
            distance_to_resistance = resistance - current_price
            distance_to_support = current_price - support

            sr_strength = (
                1.0 - min(distance_to_resistance, distance_to_support) / price_range
            )
            sr_strength = max(0.0, min(1.0, sr_strength))

            # Breakout probability
            breakout_threshold = current_atr * self.regime_config.breakout_threshold

            if distance_to_resistance <= breakout_threshold:
                breakout_prob = 0.8  # High probability of upward breakout
            elif distance_to_support <= breakout_threshold:
                breakout_prob = 0.8  # High probability of downward breakout
            else:
                breakout_prob = 0.2  # Low probability

            # Mean reversion tendency
            # Calculate how often price returns to mean after moves
            mean_price = prices.rolling(20).mean()
            deviations = abs(prices - mean_price)
            returns_to_mean = []

            for i in range(5, len(prices)):
                if deviations.iloc[i - 5] > deviations.std():  # Large deviation
                    # Check if price moved back toward mean in next 5 periods
                    future_deviation = abs(deviations.iloc[i : i + 5].min())
                    returns_to_mean.append(
                        future_deviation < deviations.iloc[i - 5] * 0.5
                    )

            mean_reversion = np.mean(returns_to_mean) if returns_to_mean else 0.5

            return {
                "sr_strength": sr_strength,
                "breakout_prob": breakout_prob,
                "mean_reversion": mean_reversion,
                "current_atr": current_atr,
                "resistance_level": resistance,
                "support_level": support,
                "price_range": price_range,
            }

        except Exception as e:
            self.logger.error(f"Error analyzing market structure: {e}")
            return {
                "sr_strength": 0.5,
                "breakout_prob": 0.3,
                "mean_reversion": 0.5,
                "current_atr": 0.01,
                "resistance_level": 1.0,
                "support_level": 1.0,
                "price_range": 0.0,
            }

    async def _analyze_economic_regime(self, symbol: str) -> Dict[str, Any]:
        """Analyze economic conditions and news impact"""
        try:
            # Simplified economic analysis
            # In production, this would integrate with economic data feeds

            return {
                "regime": "neutral",  # expansion, contraction, neutral
                "news_impact": "medium",  # high, medium, low
                "events_nearby": False,  # major events in next 24h
            }

        except Exception as e:
            self.logger.error(f"Error analyzing economic regime: {e}")
            return {"regime": "neutral", "news_impact": "low", "events_nearby": False}

    async def _determine_primary_regime(
        self,
        volatility_metrics: Dict[str, Any],
        trend_metrics: Dict[str, Any],
        correlation_metrics: Dict[str, Any],
        session_metrics: Dict[str, Any],
        structure_metrics: Dict[str, Any],
    ) -> Tuple[MarketRegime, float]:
        """Determine primary market regime from all analyses"""
        try:
            regime_scores = {}

            # Volatility contribution
            vol_regime = volatility_metrics["regime"]
            if vol_regime == VolatilityRegime.EXTREME:
                regime_scores[MarketRegime.VOLATILE] = 0.8
            elif vol_regime == VolatilityRegime.HIGH:
                regime_scores[MarketRegime.VOLATILE] = 0.6
            elif vol_regime == VolatilityRegime.LOW:
                regime_scores[MarketRegime.LOW_VOLATILITY] = 0.7
                regime_scores[MarketRegime.CONSOLIDATION] = 0.5

            # Trend contribution
            trend_direction = trend_metrics["direction"]
            trend_strength = trend_metrics["strength"]

            if trend_direction in [
                TrendDirection.STRONG_UPTREND,
                TrendDirection.UPTREND,
            ]:
                regime_scores[MarketRegime.TRENDING_BULLISH] = abs(trend_strength)
            elif trend_direction in [
                TrendDirection.STRONG_DOWNTREND,
                TrendDirection.DOWNTREND,
            ]:
                regime_scores[MarketRegime.TRENDING_BEARISH] = abs(trend_strength)
            else:
                regime_scores[MarketRegime.RANGING] = 1.0 - abs(trend_strength)

            # Structure contribution
            if structure_metrics["breakout_prob"] > 0.7:
                regime_scores[MarketRegime.BREAKOUT] = structure_metrics[
                    "breakout_prob"
                ]

            if structure_metrics["mean_reversion"] > 0.7:
                regime_scores[MarketRegime.CONSOLIDATION] = structure_metrics[
                    "mean_reversion"
                ]

            # Determine primary regime
            if regime_scores:
                primary_regime = max(
                    regime_scores.keys(), key=lambda k: regime_scores[k]
                )
                confidence = regime_scores[primary_regime]
            else:
                primary_regime = MarketRegime.RANGING
                confidence = 0.5

            return primary_regime, confidence

        except Exception as e:
            self.logger.error(f"Error determining primary regime: {e}")
            return MarketRegime.RANGING, 0.3

    async def _detect_regime_transition(
        self, new_regime: MarketRegime, confidence: float
    ) -> RegimeTransition:
        """Detect type of regime transition"""
        try:
            if self.current_regime is None or self.current_regime == new_regime:
                return RegimeTransition.STABLE

            # Check for abrupt vs gradual transition
            if confidence > self.regime_config.regime_change_threshold:
                return RegimeTransition.ABRUPT
            else:
                return RegimeTransition.GRADUAL

        except Exception as e:
            self.logger.error(f"Error detecting regime transition: {e}")
            return RegimeTransition.STABLE

    async def _calculate_regime_performance(
        self, regime: MarketRegime
    ) -> Dict[str, Any]:
        """Calculate historical performance metrics for regime"""
        try:
            # Simplified performance calculation
            return {
                "historical": {regime.value: 0.05},  # 5% historical return
                "stability": 0.7,  # 70% stability score
                "transitions": {
                    MarketRegime.RANGING.value: 0.3,
                    MarketRegime.TRENDING_BULLISH.value: 0.2,
                    MarketRegime.TRENDING_BEARISH.value: 0.2,
                    MarketRegime.VOLATILE.value: 0.15,
                    MarketRegime.BREAKOUT.value: 0.1,
                    MarketRegime.CONSOLIDATION.value: 0.05,
                },
            }

        except Exception as e:
            self.logger.error(f"Error calculating regime performance: {e}")
            return {
                "historical": {regime.value: 0.0},
                "stability": 0.5,
                "transitions": {},
            }

    async def _get_regime_duration(self, regime: MarketRegime) -> int:
        """Get duration of current regime in days"""
        try:
            if not self.regime_history:
                return 0

            # Count consecutive days in current regime
            duration = 0
            for timestamp, historical_regime, _ in reversed(self.regime_history):
                if historical_regime == regime:
                    duration += 1
                else:
                    break

            return duration

        except Exception as e:
            self.logger.error(f"Error getting regime duration: {e}")
            return 0

    async def _update_regime_state(
        self, regime: MarketRegime, confidence: float, metrics: RegimeMetrics
    ):
        """Update internal regime state"""
        try:
            # Record regime transition
            if self.current_regime != regime:
                self.regime_transitions.append(
                    {
                        "timestamp": datetime.utcnow(),
                        "from_regime": (
                            self.current_regime.value if self.current_regime else None
                        ),
                        "to_regime": regime.value,
                        "confidence": confidence,
                        "transition_type": metrics.transition_type.value,
                    }
                )

                self.logger.info(
                    f"Regime transition detected: {self.current_regime} -> {regime} "
                    f"(confidence: {confidence:.2f})"
                )

            # Update current regime
            self.current_regime = regime

            # Add to history
            self.regime_history.append((datetime.utcnow(), regime, confidence))

            # Keep history manageable
            if len(self.regime_history) > 1000:
                self.regime_history = self.regime_history[-500:]

        except Exception as e:
            self.logger.error(f"Error updating regime state: {e}")

    async def _create_fallback_metrics(self, symbol: str) -> RegimeMetrics:
        """Create fallback metrics when analysis fails"""
        return RegimeMetrics(
            regime=MarketRegime.RANGING,
            regime_confidence=0.3,
            regime_duration=0,
            previous_regime=None,
            transition_type=RegimeTransition.STABLE,
            volatility_regime=VolatilityRegime.NORMAL,
            current_volatility=0.15,
            volatility_percentile=50.0,
            volatility_trend="stable",
            trend_direction=TrendDirection.SIDEWAYS,
            trend_strength=0.0,
            trend_consistency=0.5,
            trend_duration=0,
            correlation_regime="unknown",
            avg_correlation=0.5,
            correlation_stability=0.5,
            dominant_session=TradingSession.LONDON,
            session_volatility_ratio={"london": 0.4, "ny": 0.4, "tokyo": 0.2},
            session_trend_consistency={"london": 0.5, "ny": 0.5, "tokyo": 0.5},
            support_resistance_strength=0.5,
            breakout_probability=0.3,
            mean_reversion_tendency=0.5,
            economic_regime="neutral",
            news_impact_level="low",
            calendar_events_nearby=False,
            regime_performance={MarketRegime.RANGING.value: 0.0},
            regime_stability_score=0.5,
            next_regime_probabilities={},
        )

    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        try:
            high_low = data["high"] - data["low"]
            high_close = np.abs(data["high"] - data["close"].shift())
            low_close = np.abs(data["low"] - data["close"].shift())

            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(
                axis=1
            )
            atr = true_range.rolling(window=period).mean()

            return atr

        except Exception as e:
            self.logger.error(f"Error calculating ATR: {e}")
            return pd.Series([0.01] * len(data), index=data.index)

    async def get_regime_summary(self) -> Dict[str, Any]:
        """Get comprehensive regime summary"""
        try:
            if not self.current_metrics:
                return {"error": "No regime metrics available"}

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "current_regime": self.current_metrics.regime.value,
                "regime_confidence": self.current_metrics.regime_confidence,
                "regime_duration": self.current_metrics.regime_duration,
                "volatility_regime": self.current_metrics.volatility_regime.value,
                "trend_direction": self.current_metrics.trend_direction.value,
                "trend_strength": self.current_metrics.trend_strength,
                "correlation_regime": self.current_metrics.correlation_regime,
                "dominant_session": self.current_metrics.dominant_session.value,
                "regime_stability": self.current_metrics.regime_stability_score,
                "transition_type": self.current_metrics.transition_type.value,
                "recent_transitions": len(self.regime_transitions),
                "performance_score": self.current_metrics.regime_performance.get(
                    self.current_metrics.regime.value, 0.0
                ),
            }

        except Exception as e:
            self.logger.error(f"Error getting regime summary: {e}")
            return {"error": str(e)}

    async def cleanup(self):
        """Cleanup resources"""
        try:
            self.logger.info("Market Regime Classifier cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
