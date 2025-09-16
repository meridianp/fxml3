"""
Real-time Sentiment-Driven Trade Signal Generator for Phase 8

This module implements an advanced trading signal generation system that combines:
- Multi-source sentiment analysis (news, social media, market data)
- LLM-powered sentiment interpretation and reasoning
- Elliott Wave pattern validation with sentiment confluence
- Real-time signal generation with confidence scoring
- Risk-adjusted position sizing based on sentiment volatility
"""

import asyncio
import json
import logging
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from ..analytics.market_regime_detector import MarketRegimeDetector
from ..core.database import DatabaseManager
from ..llm_integration.llm_client import LLMClient
from ..llm_integration.multi_source_sentiment import MultiSourceSentimentAggregator
from ..llm_integration.sentiment_analysis import MarketSentimentAnalyzer
from ..risk_management.portfolio_manager import PortfolioManager
from ..wave_analysis.elliott_wave import ElliottWaveAnalyzer

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of trading signals."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


class SignalStrength(Enum):
    """Signal strength classifications."""

    VERY_STRONG = "very_strong"  # 90%+
    STRONG = "strong"  # 75-90%
    MODERATE = "moderate"  # 60-75%
    WEAK = "weak"  # 40-60%
    VERY_WEAK = "very_weak"  # <40%


class SentimentTrigger(Enum):
    """Sentiment-based signal triggers."""

    NEWS_BREAKOUT = "news_breakout"
    SOCIAL_MOMENTUM = "social_momentum"
    SENTIMENT_REVERSAL = "sentiment_reversal"
    SENTIMENT_DIVERGENCE = "sentiment_divergence"
    CONFIDENCE_SURGE = "confidence_surge"
    FEAR_SPIKE = "fear_spike"
    CONTRARIAN_SETUP = "contrarian_setup"


@dataclass
class SentimentSignalComponents:
    """Components that contribute to sentiment signal."""

    news_sentiment: float
    social_sentiment: float
    market_sentiment: float
    sentiment_momentum: float
    sentiment_volatility: float
    sentiment_divergence: float
    llm_reasoning_score: float
    historical_accuracy: float


@dataclass
class SentimentTradeSignal:
    """Complete sentiment-driven trade signal."""

    signal_id: str
    symbol: str
    timeframe: str
    signal_type: SignalType
    signal_strength: SignalStrength

    # Core signal data
    confidence: float
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward_ratio: float

    # Sentiment analysis
    sentiment_components: SentimentSignalComponents
    trigger_type: SentimentTrigger
    sentiment_explanation: str
    llm_reasoning: str

    # Technical validation
    wave_pattern_support: bool
    regime_alignment: bool
    technical_confirmation: bool

    # Risk management
    position_size: float
    risk_percentage: float
    max_drawdown: float

    # Timing
    signal_time: datetime
    expiry_time: datetime
    expected_duration: int  # hours

    # Performance tracking
    entry_filled: bool = False
    exit_filled: bool = False
    actual_pnl: Optional[float] = None
    max_adverse_excursion: Optional[float] = None
    max_favorable_excursion: Optional[float] = None


class SentimentSignalGenerator:
    """Real-time sentiment-driven trade signal generator."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the sentiment signal generator.

        Args:
            config: Configuration dictionary
        """
        self.config = config or self._get_default_config()

        # Initialize components
        self.llm_client = LLMClient()
        self.sentiment_analyzer = MarketSentimentAnalyzer()
        self.multi_source_sentiment = MultiSourceSentimentAggregator()
        self.wave_analyzer = ElliottWaveAnalyzer()
        self.regime_detector = MarketRegimeDetector()
        self.db_manager = DatabaseManager()
        self.portfolio_manager = PortfolioManager()

        # Signal generation parameters
        self.min_confidence = config.get("min_confidence", 0.65)
        self.min_sentiment_change = config.get("min_sentiment_change", 0.15)
        self.sentiment_lookback = config.get("sentiment_lookback", 24)  # hours

        # Real-time tracking
        self.active_signals = {}
        self.sentiment_history = deque(maxlen=1000)
        self.performance_metrics = {
            "total_signals": 0,
            "winning_signals": 0,
            "total_pnl": 0.0,
            "avg_confidence": 0.0,
            "best_trigger_type": None,
        }

        # Signal filters
        self.signal_filters = {
            "news_impact_threshold": 0.7,
            "social_momentum_threshold": 0.8,
            "sentiment_volatility_max": 0.3,
            "regime_alignment_required": True,
            "wave_confirmation_required": False,
            "max_concurrent_signals": 5,
        }

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "min_confidence": 0.65,
            "min_sentiment_change": 0.15,
            "sentiment_lookback": 24,
            "signal_expiry_hours": 8,
            "position_sizing_method": "sentiment_adjusted",
            "base_risk_per_trade": 0.02,
            "max_risk_per_trade": 0.05,
            "sentiment_amplifier": 1.5,
            "news_weight": 0.4,
            "social_weight": 0.3,
            "market_weight": 0.3,
            "llm_validation_enabled": True,
            "historical_validation_days": 90,
            "min_risk_reward": 1.5,
            "max_position_correlation": 0.7,
        }

    async def generate_signals(
        self, symbols: List[str], timeframes: List[str] = None
    ) -> List[SentimentTradeSignal]:
        """Generate sentiment-driven trade signals for multiple symbols.

        Args:
            symbols: List of trading symbols
            timeframes: List of timeframes to analyze

        Returns:
            List of generated trade signals
        """
        if timeframes is None:
            timeframes = ["1h", "4h"]

        all_signals = []

        try:
            # Generate signals for each symbol-timeframe combination
            for symbol in symbols:
                for timeframe in timeframes:
                    signals = await self._generate_symbol_signals(symbol, timeframe)
                    all_signals.extend(signals)

            # Filter and rank signals
            filtered_signals = await self._filter_and_rank_signals(all_signals)

            # Validate signal portfolio
            final_signals = await self._validate_signal_portfolio(filtered_signals)

            # Store signals
            for signal in final_signals:
                await self._store_signal(signal)
                self.active_signals[signal.signal_id] = signal

            # Update performance metrics
            await self._update_performance_metrics()

            return final_signals

        except Exception as e:
            logger.error(f"Error generating signals: {str(e)}")
            return []

    async def _generate_symbol_signals(
        self, symbol: str, timeframe: str
    ) -> List[SentimentTradeSignal]:
        """Generate signals for a specific symbol and timeframe."""
        signals = []

        try:
            # Get comprehensive sentiment analysis
            sentiment_data = await self._get_comprehensive_sentiment(symbol)

            # Get market data and technical context
            market_data = await self._get_market_context(symbol, timeframe)

            # Analyze sentiment triggers
            triggers = await self._analyze_sentiment_triggers(
                sentiment_data, market_data
            )

            # Generate signals for each significant trigger
            for trigger in triggers:
                if trigger["significance"] >= self.min_confidence:
                    signal = await self._create_signal_from_trigger(
                        symbol, timeframe, trigger, sentiment_data, market_data
                    )
                    if signal:
                        signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {str(e)}")
            return []

    async def _get_comprehensive_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive multi-source sentiment analysis."""
        try:
            # Real-time sentiment from multiple sources
            realtime_sentiment = await self.sentiment_analyzer.get_realtime_sentiment(
                symbol
            )

            # Multi-source aggregation
            multi_source = await self.multi_source_sentiment.aggregate_sentiment(
                symbol=symbol, lookback_hours=self.sentiment_lookback
            )

            # Historical sentiment trend
            historical_trend = await self._get_sentiment_trend(symbol)

            # Sentiment momentum and volatility
            momentum_data = await self._calculate_sentiment_momentum(symbol)

            # LLM-powered sentiment interpretation
            llm_analysis = await self._get_llm_sentiment_analysis(
                symbol, realtime_sentiment, multi_source
            )

            return {
                "realtime": realtime_sentiment,
                "multi_source": multi_source,
                "historical_trend": historical_trend,
                "momentum": momentum_data,
                "llm_analysis": llm_analysis,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Error getting comprehensive sentiment: {str(e)}")
            return {}

    async def _get_market_context(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Get market context including technical and regime analysis."""
        try:
            # Price data
            end_time = datetime.now()
            start_time = end_time - timedelta(days=30)

            price_data = await self.db_manager.get_market_data(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                timeframe=timeframe,
            )

            # Current market regime
            regime = await self.regime_detector.detect_regime(symbol, timeframe)

            # Elliott Wave analysis
            df_with_peaks = self.wave_analyzer.detect_peaks_and_troughs(price_data)
            waves = self.wave_analyzer.compute_waves(df_with_peaks)

            # Technical indicators
            technical_indicators = self._calculate_technical_indicators(price_data)

            return {
                "price_data": price_data,
                "current_price": (
                    price_data.iloc[-1]["close"] if len(price_data) > 0 else 0
                ),
                "regime": regime,
                "waves": waves,
                "technical_indicators": technical_indicators,
                "volatility": self._calculate_volatility(price_data),
                "volume_profile": self._analyze_volume_profile(price_data),
            }

        except Exception as e:
            logger.error(f"Error getting market context: {str(e)}")
            return {}

    async def _analyze_sentiment_triggers(
        self, sentiment_data: Dict[str, Any], market_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze sentiment data for trading triggers."""
        triggers = []

        try:
            if not sentiment_data or not market_data:
                return triggers

            realtime = sentiment_data.get("realtime", {})
            multi_source = sentiment_data.get("multi_source", {})
            momentum = sentiment_data.get("momentum", {})
            llm_analysis = sentiment_data.get("llm_analysis", {})

            # News breakout trigger
            news_impact = realtime.get("news_impact", 0)
            if news_impact >= self.signal_filters["news_impact_threshold"]:
                triggers.append(
                    {
                        "type": SentimentTrigger.NEWS_BREAKOUT,
                        "significance": news_impact,
                        "direction": (
                            1 if realtime.get("news_sentiment", 0.5) > 0.5 else -1
                        ),
                        "data": {
                            "news_sentiment": realtime.get("news_sentiment", 0.5),
                            "news_volume": realtime.get("news_volume", 0),
                            "headline_impact": realtime.get("headline_impact", 0),
                        },
                    }
                )

            # Social momentum trigger
            social_momentum = momentum.get("social_momentum", 0)
            if abs(social_momentum) >= self.signal_filters["social_momentum_threshold"]:
                triggers.append(
                    {
                        "type": SentimentTrigger.SOCIAL_MOMENTUM,
                        "significance": abs(social_momentum),
                        "direction": 1 if social_momentum > 0 else -1,
                        "data": {
                            "social_sentiment": realtime.get("social_sentiment", 0.5),
                            "social_volume": multi_source.get("social_volume", 0),
                            "momentum_acceleration": momentum.get(
                                "momentum_acceleration", 0
                            ),
                        },
                    }
                )

            # Sentiment reversal trigger
            sentiment_change = momentum.get("sentiment_change", 0)
            if abs(sentiment_change) >= self.min_sentiment_change:
                triggers.append(
                    {
                        "type": SentimentTrigger.SENTIMENT_REVERSAL,
                        "significance": abs(sentiment_change),
                        "direction": 1 if sentiment_change > 0 else -1,
                        "data": {
                            "change_magnitude": abs(sentiment_change),
                            "reversal_speed": momentum.get("reversal_speed", 0),
                            "confirmation_score": momentum.get("confirmation_score", 0),
                        },
                    }
                )

            # Sentiment divergence trigger
            price_momentum = market_data.get("technical_indicators", {}).get(
                "momentum", 0
            )
            sentiment_momentum = momentum.get("overall_momentum", 0)

            if abs(price_momentum - sentiment_momentum) > 0.3:  # Divergence threshold
                triggers.append(
                    {
                        "type": SentimentTrigger.SENTIMENT_DIVERGENCE,
                        "significance": abs(price_momentum - sentiment_momentum),
                        "direction": (
                            -1 if price_momentum > sentiment_momentum else 1
                        ),  # Contrarian
                        "data": {
                            "price_momentum": price_momentum,
                            "sentiment_momentum": sentiment_momentum,
                            "divergence_strength": abs(
                                price_momentum - sentiment_momentum
                            ),
                        },
                    }
                )

            # LLM confidence surge trigger
            llm_confidence = llm_analysis.get("confidence", 0)
            if llm_confidence >= 0.85:
                triggers.append(
                    {
                        "type": SentimentTrigger.CONFIDENCE_SURGE,
                        "significance": llm_confidence,
                        "direction": 1 if llm_analysis.get("bias", 0) > 0 else -1,
                        "data": {
                            "llm_confidence": llm_confidence,
                            "llm_reasoning": llm_analysis.get("reasoning", ""),
                            "key_factors": llm_analysis.get("key_factors", []),
                        },
                    }
                )

            # Fear spike trigger (contrarian)
            fear_level = realtime.get("fear_greed_index", 50) / 100.0
            if fear_level <= 0.2 or fear_level >= 0.8:  # Extreme fear or greed
                triggers.append(
                    {
                        "type": (
                            SentimentTrigger.FEAR_SPIKE
                            if fear_level <= 0.2
                            else SentimentTrigger.CONTRARIAN_SETUP
                        ),
                        "significance": 1.0
                        - abs(fear_level - 0.5) * 2,  # Distance from neutral
                        "direction": (
                            1 if fear_level <= 0.2 else -1
                        ),  # Buy fear, sell greed
                        "data": {
                            "fear_greed_level": fear_level,
                            "extreme_reading": True,
                            "contrarian_setup": True,
                        },
                    }
                )

            # Sort triggers by significance
            triggers.sort(key=lambda x: x["significance"], reverse=True)

            return triggers

        except Exception as e:
            logger.error(f"Error analyzing sentiment triggers: {str(e)}")
            return []

    async def _create_signal_from_trigger(
        self,
        symbol: str,
        timeframe: str,
        trigger: Dict[str, Any],
        sentiment_data: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> Optional[SentimentTradeSignal]:
        """Create a complete trade signal from a sentiment trigger."""
        try:
            # Determine signal type
            direction = trigger["direction"]
            signal_type = SignalType.BUY if direction > 0 else SignalType.SELL

            # Calculate signal strength
            signal_strength = self._calculate_signal_strength(trigger["significance"])

            # Get current price and calculate entry/exit levels
            current_price = market_data.get("current_price", 0)
            if current_price == 0:
                return None

            # Calculate entry, target, and stop loss based on sentiment and technical analysis
            entry_price = current_price
            target_price, stop_loss = await self._calculate_price_targets(
                symbol, signal_type, current_price, sentiment_data, market_data
            )

            # Risk-reward validation
            risk_reward_ratio = self._calculate_risk_reward(
                entry_price, target_price, stop_loss, signal_type
            )
            if risk_reward_ratio < self.config["min_risk_reward"]:
                return None

            # Build sentiment components
            sentiment_components = self._build_sentiment_components(sentiment_data)

            # Generate LLM reasoning
            llm_reasoning = await self._generate_llm_reasoning(
                symbol, signal_type, trigger, sentiment_data, market_data
            )

            # Technical validation
            wave_support = await self._validate_wave_pattern_support(
                signal_type, market_data
            )
            regime_alignment = self._validate_regime_alignment(signal_type, market_data)
            technical_confirmation = self._validate_technical_confirmation(
                signal_type, market_data
            )

            # Position sizing
            position_size, risk_percentage = await self._calculate_position_size(
                symbol, signal_strength, sentiment_components, risk_reward_ratio
            )

            # Signal timing
            signal_time = datetime.now()
            expiry_time = signal_time + timedelta(
                hours=self.config["signal_expiry_hours"]
            )
            expected_duration = self._estimate_signal_duration(trigger, sentiment_data)

            # Create signal
            signal = SentimentTradeSignal(
                signal_id=f"sent_{symbol}_{timeframe}_{int(signal_time.timestamp())}",
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type,
                signal_strength=signal_strength,
                confidence=trigger["significance"],
                entry_price=entry_price,
                target_price=target_price,
                stop_loss=stop_loss,
                risk_reward_ratio=risk_reward_ratio,
                sentiment_components=sentiment_components,
                trigger_type=trigger["type"],
                sentiment_explanation=self._create_sentiment_explanation(
                    trigger, sentiment_data
                ),
                llm_reasoning=llm_reasoning,
                wave_pattern_support=wave_support,
                regime_alignment=regime_alignment,
                technical_confirmation=technical_confirmation,
                position_size=position_size,
                risk_percentage=risk_percentage,
                max_drawdown=risk_percentage * 2,  # 2x risk for max drawdown
                signal_time=signal_time,
                expiry_time=expiry_time,
                expected_duration=expected_duration,
            )

            return signal

        except Exception as e:
            logger.error(f"Error creating signal from trigger: {str(e)}")
            return None

    def _calculate_signal_strength(self, significance: float) -> SignalStrength:
        """Calculate signal strength based on significance."""
        if significance >= 0.9:
            return SignalStrength.VERY_STRONG
        elif significance >= 0.75:
            return SignalStrength.STRONG
        elif significance >= 0.6:
            return SignalStrength.MODERATE
        elif significance >= 0.4:
            return SignalStrength.WEAK
        else:
            return SignalStrength.VERY_WEAK

    async def _calculate_price_targets(
        self,
        symbol: str,
        signal_type: SignalType,
        current_price: float,
        sentiment_data: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> Tuple[float, float]:
        """Calculate target price and stop loss."""
        try:
            # Base target calculation using volatility
            volatility = market_data.get("volatility", 0.01)

            # Sentiment-adjusted target multiplier
            sentiment_strength = sentiment_data.get("realtime", {}).get(
                "overall_sentiment", 0.5
            )
            sentiment_multiplier = 1.0 + abs(sentiment_strength - 0.5) * 2  # 1.0 to 2.0

            # Base target distance (2x volatility)
            base_target_distance = volatility * 2 * sentiment_multiplier

            if signal_type == SignalType.BUY:
                target_price = current_price * (1 + base_target_distance)
                stop_loss = current_price * (
                    1 - base_target_distance * 0.6
                )  # Tighter stop
            else:
                target_price = current_price * (1 - base_target_distance)
                stop_loss = current_price * (1 + base_target_distance * 0.6)

            # Adjust based on support/resistance levels if available
            technical_indicators = market_data.get("technical_indicators", {})
            if (
                "nearest_support" in technical_indicators
                and "nearest_resistance" in technical_indicators
            ):
                support = technical_indicators["nearest_support"]
                resistance = technical_indicators["nearest_resistance"]

                if signal_type == SignalType.BUY:
                    # Use resistance as target if it's reasonable
                    if resistance > current_price and resistance < target_price * 1.5:
                        target_price = resistance * 0.98  # Slightly below resistance
                    # Use support as stop if it's reasonable
                    if support < current_price and support > stop_loss * 0.8:
                        stop_loss = support * 0.98  # Slightly below support
                else:
                    # Use support as target if it's reasonable
                    if support < current_price and support > target_price * 0.5:
                        target_price = support * 1.02  # Slightly above support
                    # Use resistance as stop if it's reasonable
                    if resistance > current_price and resistance < stop_loss * 1.2:
                        stop_loss = resistance * 1.02  # Slightly above resistance

            return target_price, stop_loss

        except Exception as e:
            logger.error(f"Error calculating price targets: {str(e)}")
            # Fallback to simple percentage-based targets
            if signal_type == SignalType.BUY:
                return current_price * 1.02, current_price * 0.99
            else:
                return current_price * 0.98, current_price * 1.01

    def _calculate_risk_reward(
        self, entry: float, target: float, stop: float, signal_type: SignalType
    ) -> float:
        """Calculate risk-reward ratio."""
        if signal_type == SignalType.BUY:
            potential_profit = target - entry
            potential_loss = entry - stop
        else:
            potential_profit = entry - target
            potential_loss = stop - entry

        if potential_loss <= 0:
            return 0.0

        return potential_profit / potential_loss

    def _build_sentiment_components(
        self, sentiment_data: Dict[str, Any]
    ) -> SentimentSignalComponents:
        """Build sentiment components from sentiment data."""
        realtime = sentiment_data.get("realtime", {})
        momentum = sentiment_data.get("momentum", {})
        llm_analysis = sentiment_data.get("llm_analysis", {})

        return SentimentSignalComponents(
            news_sentiment=realtime.get("news_sentiment", 0.5),
            social_sentiment=realtime.get("social_sentiment", 0.5),
            market_sentiment=realtime.get("overall_sentiment", 0.5),
            sentiment_momentum=momentum.get("overall_momentum", 0.0),
            sentiment_volatility=momentum.get("sentiment_volatility", 0.0),
            sentiment_divergence=momentum.get("divergence_score", 0.0),
            llm_reasoning_score=llm_analysis.get("confidence", 0.5),
            historical_accuracy=0.75,  # Placeholder - would be calculated from historical performance
        )

    async def _generate_llm_reasoning(
        self,
        symbol: str,
        signal_type: SignalType,
        trigger: Dict[str, Any],
        sentiment_data: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> str:
        """Generate LLM reasoning for the signal."""
        try:
            if not self.config["llm_validation_enabled"]:
                return "LLM validation disabled"

            # Prepare context for LLM
            context = {
                "symbol": symbol,
                "signal_type": signal_type.value,
                "trigger_type": trigger["type"].value,
                "trigger_significance": trigger["significance"],
                "current_price": market_data.get("current_price", 0),
                "sentiment_summary": {
                    "news_sentiment": sentiment_data.get("realtime", {}).get(
                        "news_sentiment", 0.5
                    ),
                    "social_sentiment": sentiment_data.get("realtime", {}).get(
                        "social_sentiment", 0.5
                    ),
                    "overall_sentiment": sentiment_data.get("realtime", {}).get(
                        "overall_sentiment", 0.5
                    ),
                    "sentiment_momentum": sentiment_data.get("momentum", {}).get(
                        "overall_momentum", 0.0
                    ),
                },
                "market_regime": (
                    market_data.get("regime", {}).get("regime_type", "unknown")
                    if market_data.get("regime")
                    else "unknown"
                ),
            }

            prompt = f"""
            Analyze this sentiment-driven trading signal for {symbol}:

            Signal: {signal_type.value.upper()}
            Trigger: {trigger['type'].value} (confidence: {trigger['significance']:.2f})

            Sentiment Analysis:
            - News Sentiment: {context['sentiment_summary']['news_sentiment']:.2f}
            - Social Sentiment: {context['sentiment_summary']['social_sentiment']:.2f}
            - Overall Sentiment: {context['sentiment_summary']['overall_sentiment']:.2f}
            - Momentum: {context['sentiment_summary']['sentiment_momentum']:.2f}

            Market Context:
            - Current Price: {context['current_price']:.4f}
            - Market Regime: {context['market_regime']}

            Provide a concise explanation (2-3 sentences) of:
            1. Why this sentiment pattern suggests a {signal_type.value} signal
            2. The key risk factors to consider
            3. The expected outcome based on similar historical patterns

            Focus on actionable insights for traders.
            """

            response = await self.llm_client.generate_completion(
                prompt=prompt, max_tokens=200, temperature=0.2
            )

            return response.strip()

        except Exception as e:
            logger.error(f"Error generating LLM reasoning: {str(e)}")
            return f"Signal triggered by {trigger['type'].value} with {trigger['significance']:.0%} confidence. Monitor for confirmation."

    async def _validate_wave_pattern_support(
        self, signal_type: SignalType, market_data: Dict[str, Any]
    ) -> bool:
        """Validate if Elliott Wave patterns support the signal."""
        try:
            waves = market_data.get("waves", [])
            if not waves:
                return True  # No contradiction if no waves detected

            # Simple validation - check if latest wave direction aligns with signal
            if len(waves) > 0:
                latest_wave = waves[-1]
                wave_direction = latest_wave.get("direction", 0)

                if signal_type == SignalType.BUY:
                    return wave_direction >= 0  # Bullish or neutral
                else:
                    return wave_direction <= 0  # Bearish or neutral

            return True

        except Exception as e:
            logger.error(f"Error validating wave pattern support: {str(e)}")
            return True

    def _validate_regime_alignment(
        self, signal_type: SignalType, market_data: Dict[str, Any]
    ) -> bool:
        """Validate if market regime aligns with signal direction."""
        try:
            regime = market_data.get("regime")
            if not regime:
                return True

            regime_type = regime.get("regime_type", "").lower()

            bullish_regimes = ["trending_bull", "breakout_bull"]
            bearish_regimes = ["trending_bear", "breakout_bear"]

            if signal_type == SignalType.BUY:
                return any(br in regime_type for br in bullish_regimes)
            else:
                return any(br in regime_type for br in bearish_regimes)

        except Exception as e:
            logger.error(f"Error validating regime alignment: {str(e)}")
            return True

    def _validate_technical_confirmation(
        self, signal_type: SignalType, market_data: Dict[str, Any]
    ) -> bool:
        """Validate signal with technical indicators."""
        try:
            indicators = market_data.get("technical_indicators", {})

            # Check multiple technical factors
            confirmations = 0
            total_checks = 0

            # RSI check
            rsi = indicators.get("rsi", 50)
            total_checks += 1
            if signal_type == SignalType.BUY and rsi < 70:  # Not overbought
                confirmations += 1
            elif signal_type == SignalType.SELL and rsi > 30:  # Not oversold
                confirmations += 1

            # MACD check
            macd_signal = indicators.get("macd_signal", 0)
            total_checks += 1
            if signal_type == SignalType.BUY and macd_signal > 0:  # Bullish MACD
                confirmations += 1
            elif signal_type == SignalType.SELL and macd_signal < 0:  # Bearish MACD
                confirmations += 1

            # Moving average check
            ma_trend = indicators.get("ma_trend", 0)
            total_checks += 1
            if signal_type == SignalType.BUY and ma_trend > 0:  # Uptrend
                confirmations += 1
            elif signal_type == SignalType.SELL and ma_trend < 0:  # Downtrend
                confirmations += 1

            # Require majority confirmation
            return confirmations >= (total_checks / 2) if total_checks > 0 else True

        except Exception as e:
            logger.error(f"Error validating technical confirmation: {str(e)}")
            return True

    async def _calculate_position_size(
        self,
        symbol: str,
        signal_strength: SignalStrength,
        sentiment_components: SentimentSignalComponents,
        risk_reward_ratio: float,
    ) -> Tuple[float, float]:
        """Calculate position size based on sentiment and risk parameters."""
        try:
            # Base risk percentage
            base_risk = self.config["base_risk_per_trade"]

            # Adjust based on signal strength
            strength_multipliers = {
                SignalStrength.VERY_STRONG: 1.5,
                SignalStrength.STRONG: 1.2,
                SignalStrength.MODERATE: 1.0,
                SignalStrength.WEAK: 0.7,
                SignalStrength.VERY_WEAK: 0.5,
            }

            strength_multiplier = strength_multipliers.get(signal_strength, 1.0)

            # Adjust based on sentiment confidence
            sentiment_confidence = (
                sentiment_components.llm_reasoning_score * 0.3
                + sentiment_components.historical_accuracy * 0.3
                + (1.0 - sentiment_components.sentiment_volatility) * 0.4
            )

            # Adjust based on risk-reward ratio
            rr_multiplier = min(2.0, risk_reward_ratio / 2.0)  # Cap at 2x

            # Calculate final risk percentage
            risk_percentage = (
                base_risk * strength_multiplier * sentiment_confidence * rr_multiplier
            )
            risk_percentage = max(
                0.005, min(self.config["max_risk_per_trade"], risk_percentage)
            )

            # Get account balance for position sizing
            account_balance = await self.portfolio_manager.get_account_balance()
            position_size = (
                account_balance * risk_percentage
            ) / 100  # Convert percentage to dollar amount

            return position_size, risk_percentage

        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return 1000.0, self.config["base_risk_per_trade"]  # Default values

    # Helper methods (abbreviated implementations)

    async def _get_sentiment_trend(self, symbol: str) -> Dict[str, Any]:
        """Get historical sentiment trend."""
        # Placeholder implementation
        return {"trend": "neutral", "strength": 0.5}

    async def _calculate_sentiment_momentum(self, symbol: str) -> Dict[str, Any]:
        """Calculate sentiment momentum metrics."""
        return {
            "overall_momentum": 0.0,
            "social_momentum": 0.0,
            "momentum_acceleration": 0.0,
            "sentiment_change": 0.0,
            "reversal_speed": 0.0,
            "confirmation_score": 0.0,
            "sentiment_volatility": 0.1,
            "divergence_score": 0.0,
        }

    async def _get_llm_sentiment_analysis(
        self, symbol: str, realtime: Dict, multi_source: Dict
    ) -> Dict[str, Any]:
        """Get LLM analysis of sentiment data."""
        return {
            "confidence": 0.75,
            "bias": 0.1,
            "reasoning": "Neutral market sentiment with slight bullish bias",
            "key_factors": ["Economic data", "Central bank policy"],
        }

    def _calculate_technical_indicators(
        self, price_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate technical indicators."""
        if len(price_data) < 20:
            return {}

        closes = price_data["close"].values

        # Simple implementations
        rsi = 50.0  # Placeholder
        macd_signal = 0.0  # Placeholder
        ma_trend = 1 if closes[-1] > np.mean(closes[-20:]) else -1

        return {
            "rsi": rsi,
            "macd_signal": macd_signal,
            "ma_trend": ma_trend,
            "momentum": (
                (closes[-1] - closes[-5]) / closes[-5] if len(closes) >= 5 else 0
            ),
            "nearest_support": np.min(closes[-20:]) * 1.01,
            "nearest_resistance": np.max(closes[-20:]) * 0.99,
        }

    def _calculate_volatility(self, price_data: pd.DataFrame) -> float:
        """Calculate price volatility."""
        if len(price_data) < 2:
            return 0.01

        returns = np.diff(np.log(price_data["close"].values))
        return np.std(returns)

    def _analyze_volume_profile(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze volume profile."""
        return {"average_volume": 1000000, "volume_trend": "increasing"}

    def _create_sentiment_explanation(
        self, trigger: Dict[str, Any], sentiment_data: Dict[str, Any]
    ) -> str:
        """Create human-readable sentiment explanation."""
        trigger_type = trigger["type"].value
        significance = trigger["significance"]

        return (
            f"{trigger_type.replace('_', ' ').title()} detected with {significance:.0%} confidence. "
            f"Sentiment analysis indicates strong directional bias supporting this signal."
        )

    def _estimate_signal_duration(
        self, trigger: Dict[str, Any], sentiment_data: Dict[str, Any]
    ) -> int:
        """Estimate expected signal duration in hours."""
        # Base durations by trigger type
        base_durations = {
            SentimentTrigger.NEWS_BREAKOUT: 4,
            SentimentTrigger.SOCIAL_MOMENTUM: 8,
            SentimentTrigger.SENTIMENT_REVERSAL: 12,
            SentimentTrigger.SENTIMENT_DIVERGENCE: 6,
            SentimentTrigger.CONFIDENCE_SURGE: 3,
            SentimentTrigger.FEAR_SPIKE: 2,
            SentimentTrigger.CONTRARIAN_SETUP: 24,
        }

        return base_durations.get(trigger["type"], 6)

    async def _filter_and_rank_signals(
        self, signals: List[SentimentTradeSignal]
    ) -> List[SentimentTradeSignal]:
        """Filter and rank signals by quality."""
        # Filter by minimum requirements
        filtered = [
            signal
            for signal in signals
            if signal.confidence >= self.min_confidence
            and signal.risk_reward_ratio >= self.config["min_risk_reward"]
        ]

        # Sort by confidence score
        filtered.sort(key=lambda s: s.confidence, reverse=True)

        return filtered[: self.signal_filters["max_concurrent_signals"]]

    async def _validate_signal_portfolio(
        self, signals: List[SentimentTradeSignal]
    ) -> List[SentimentTradeSignal]:
        """Validate signal portfolio for correlation and risk."""
        # Simple implementation - remove highly correlated signals
        final_signals = []

        for signal in signals:
            # Check correlation with existing signals
            is_correlated = False
            for existing in final_signals:
                if (
                    existing.symbol == signal.symbol
                    and existing.signal_type == signal.signal_type
                ):
                    is_correlated = True
                    break

            if not is_correlated:
                final_signals.append(signal)

        return final_signals

    async def _store_signal(self, signal: SentimentTradeSignal):
        """Store signal in database."""
        try:
            signal_data = asdict(signal)
            signal_data["sentiment_components"] = asdict(signal.sentiment_components)
            signal_data["signal_type"] = signal.signal_type.value
            signal_data["signal_strength"] = signal.signal_strength.value
            signal_data["trigger_type"] = signal.trigger_type.value

            await self.db_manager.store_sentiment_signal(signal_data)

        except Exception as e:
            logger.error(f"Error storing signal: {str(e)}")

    async def _update_performance_metrics(self):
        """Update performance tracking metrics."""
        try:
            # Update performance metrics based on closed signals
            self.performance_metrics["total_signals"] = len(self.active_signals)

            # Calculate other metrics from historical data
            # (Implementation would query database for historical performance)

        except Exception as e:
            logger.error(f"Error updating performance metrics: {str(e)}")

    async def get_signal_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive signal performance summary."""
        return {
            "performance_metrics": self.performance_metrics,
            "active_signals": len(self.active_signals),
            "signal_filters": self.signal_filters,
            "last_updated": datetime.now().isoformat(),
        }
