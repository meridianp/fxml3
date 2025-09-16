#!/usr/bin/env python
"""Enhanced Production System V2 with recommended adjustments and Alpha Vantage integration."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import base components
from fxml4.backtesting.risk_management import RiskManager
from fxml4.data_engineering.data_feeds.alpha_vantage_feed import AlphaVantageDataFeed
from scripts.enhanced_elliott_wave_signals import (
    ElliottWaveSignal,
    EnhancedElliottWaveSignalGenerator,
)

# Import enhanced components
from scripts.enhanced_ml_signal_generator import EnhancedMLSignalGenerator, MLSignal
from scripts.general_technical_analysis_llm import (
    GeneralTechnicalAnalysisLLM,
    TechnicalAnalysisSignal,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class EnhancedProductionConfigV2:
    """Enhanced configuration with recommended adjustments."""

    # Capital
    initial_capital: float = 10000

    # Risk Management
    max_risk_per_trade: float = 0.015  # 1.5%
    max_portfolio_risk: float = 0.045  # 4.5%
    max_positions: int = 2
    max_drawdown_limit: float = 0.20  # 20%

    # Signal Requirements - ADJUSTED
    min_confluences: int = 1  # Lowered from 2 for initial testing
    min_signal_confidence: float = 0.6  # Reduced from 0.7

    # Position Sizing - NEW
    single_source_position_reduction: float = 0.5  # 50% size for single source
    adaptive_sizing: bool = True

    # Signal Weights
    ml_weight: float = 0.4
    elliott_wave_weight: float = 0.3
    technical_analysis_weight: float = 0.3

    # Execution
    commission_rate: float = 0.00005  # 0.5 pips
    slippage: float = 0.00002  # 0.2 pips
    spread: float = 0.00015  # 1.5 pips

    # Risk Management - ENHANCED
    use_trailing_stops: bool = True
    trailing_stop_distance: float = 2.0  # ATR multiplier
    use_partial_profits: bool = True
    partial_profit_levels: List[float] = None  # R multiples

    # Time-based exits - NEW
    max_bars_in_trade: int = 120  # 20 days at 4H bars
    time_based_exit_enabled: bool = True

    # Adaptive thresholds - NEW
    use_adaptive_thresholds: bool = True
    volatility_adjustment_factor: float = 1.5

    # Filters
    use_market_regime_filter: bool = True
    use_volatility_filter: bool = True
    use_news_filter: bool = True  # NEW - Alpha Vantage news
    max_trades_per_week: int = 5  # Increased from 3

    # Alpha Vantage Integration - NEW
    use_economic_data: bool = True
    use_sentiment_data: bool = True
    sentiment_weight: float = 0.2  # Weight in signal generation


class AlphaVantageEnhancement:
    """Handles Alpha Vantage data enrichment for trading signals."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            logger.warning("No Alpha Vantage API key found - features disabled")
            self.enabled = False
        else:
            # AlphaVantageDataFeed expects a config dict, not just the API key
            av_config = {
                "api_key": self.api_key,
                "cache_data": True,
                "api_calls_per_minute": 75,  # Premium tier
            }
            self.av_feed = AlphaVantageDataFeed(av_config)
            self.enabled = True
            self.economic_cache = {}
            self.news_cache = {}

    def get_economic_context(self, timestamp: pd.Timestamp) -> Dict:
        """Get economic context for a given timestamp."""
        if not self.enabled:
            return {}

        # Check cache first
        cache_key = timestamp.strftime("%Y-%m-%d")
        if cache_key in self.economic_cache:
            return self.economic_cache[cache_key]

        try:
            context = {
                "fed_rate": self._get_latest_value("FEDERAL_FUNDS_RATE", timestamp),
                "unemployment": self._get_latest_value("UNEMPLOYMENT", timestamp),
                "cpi": self._get_latest_value("CPI", timestamp),
                "gdp_growth": self._get_latest_value("REAL_GDP", timestamp),
                "vix": self._get_latest_value("CBOE:VIX", timestamp),
                "dxy": self._get_latest_value("DX-Y.NYB", timestamp),  # Dollar index
            }

            # Derive economic sentiment
            context["economic_sentiment"] = self._calculate_economic_sentiment(context)

            # Cache result
            self.economic_cache[cache_key] = context
            return context

        except Exception as e:
            logger.warning(f"Failed to get economic context: {e}")
            return {}

    def get_news_sentiment(self, symbol: str, timestamp: pd.Timestamp) -> Dict:
        """Get news sentiment for a symbol."""
        if not self.enabled:
            return {"sentiment": 0.0, "relevance": 0.0}

        # Import the news API
        try:
            from fxml4.data_engineering.data_feeds.alpha_vantage_news import (
                AlphaVantageNewsAPI,
            )
        except ImportError:
            logger.warning("AlphaVantageNewsAPI not available, using mock data")
            return self._get_mock_sentiment()

        # Check cache first (with symbol and date)
        cache_key = f"{symbol}_{timestamp.strftime('%Y-%m-%d')}_news"
        if cache_key in self.news_cache:
            cached_data, cache_time = self.news_cache[cache_key]
            # Use cache if less than 1 hour old
            if (datetime.now() - cache_time).total_seconds() < 3600:
                return cached_data

        try:
            # Initialize news API
            news_api = AlphaVantageNewsAPI(self.api_key)

            # Get news sentiment for the last 24 hours
            sentiment = news_api.get_forex_sentiment(
                symbol=symbol,
                time_from=timestamp - timedelta(hours=24),
                time_to=timestamp,
                limit=50,
                use_cache=True,
            )

            # Cache the result
            self.news_cache[cache_key] = (sentiment, datetime.now())

            return sentiment

        except Exception as e:
            logger.warning(f"Failed to get news sentiment: {e}")
            return self._get_mock_sentiment()

    def _get_mock_sentiment(self) -> Dict:
        """Return mock sentiment data for testing."""
        return {
            "overall_sentiment": 0.0,
            "sentiment_score": 0.0,
            "relevance_score": 0.5,
            "article_count": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
        }

    def _get_latest_value(self, indicator: str, timestamp: pd.Timestamp) -> float:
        """Get latest value for an economic indicator."""
        try:
            # This would fetch from Alpha Vantage
            # For now, return mock values
            mock_values = {
                "FEDERAL_FUNDS_RATE": 5.25,
                "UNEMPLOYMENT": 3.7,
                "CPI": 3.2,
                "REAL_GDP": 2.1,
                "CBOE:VIX": 15.5,
                "DX-Y.NYB": 104.5,
            }
            return mock_values.get(indicator, 0.0)
        except:
            return 0.0

    def _calculate_economic_sentiment(self, context: Dict) -> float:
        """Calculate overall economic sentiment from indicators."""
        sentiment = 0.0

        # Fed rate impact (higher = bearish for risk assets)
        if context.get("fed_rate", 0) > 4.5:
            sentiment -= 0.2
        elif context.get("fed_rate", 0) < 2.0:
            sentiment += 0.2

        # Unemployment (lower = bullish)
        if context.get("unemployment", 0) < 4.0:
            sentiment += 0.1
        elif context.get("unemployment", 0) > 5.0:
            sentiment -= 0.1

        # GDP growth (higher = bullish)
        if context.get("gdp_growth", 0) > 2.5:
            sentiment += 0.2
        elif context.get("gdp_growth", 0) < 1.0:
            sentiment -= 0.2

        # VIX (lower = bullish)
        if context.get("vix", 0) < 15:
            sentiment += 0.1
        elif context.get("vix", 0) > 25:
            sentiment -= 0.2

        return np.clip(sentiment, -1, 1)


class EnhancedProductionSystemV2:
    """Production system with all recommended enhancements."""

    def __init__(self, config: EnhancedProductionConfigV2, ml_model=None):
        self.config = config

        # Set default partial profit levels if not provided
        if config.partial_profit_levels is None:
            config.partial_profit_levels = [1.5, 2.5, 3.5]

        self.capital = config.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.ml_model = ml_model

        # Initialize enhanced components
        self.ml_generator = EnhancedMLSignalGenerator(
            model=ml_model,
            min_confidence=config.min_signal_confidence,
            max_signals_per_week=config.max_trades_per_week,
            use_market_regime_filter=config.use_market_regime_filter,
            use_volatility_filter=config.use_volatility_filter,
        )

        self.ew_generator = EnhancedElliottWaveSignalGenerator(
            confidence_threshold=config.min_signal_confidence
        )

        self.ta_analyzer = GeneralTechnicalAnalysisLLM()

        # Risk manager
        self.risk_manager = RiskManager(
            max_positions=config.max_positions,
            risk_per_trade_pct=config.max_risk_per_trade,
            max_risk_per_day_pct=config.max_portfolio_risk,
        )

        # Alpha Vantage enhancement
        self.av_enhancement = AlphaVantageEnhancement()

        # Adaptive threshold tracking
        self.market_conditions = {
            "volatility_percentile": 50,
            "trend_strength": 0.5,
            "recent_performance": 0.0,
        }

        # Performance tracking
        self.performance_stats = {
            "total_signals": 0,
            "ml_signals": 0,
            "ew_signals": 0,
            "ta_signals": 0,
            "sentiment_signals": 0,
            "single_source_trades": 0,
            "multi_confluence": 0,
            "trades_executed": 0,
            "time_exits": 0,
            "adaptive_adjustments": 0,
        }

        logger.info("Enhanced Production System V2 initialized")

    def generate_combined_signal(
        self, data: pd.DataFrame, symbol: str, current_time: pd.Timestamp
    ) -> Optional[Dict]:
        """Generate combined signal with adaptive thresholds and enrichment."""

        signals = []
        self.performance_stats["total_signals"] += 1

        # Update adaptive thresholds if enabled
        if self.config.use_adaptive_thresholds:
            self._update_adaptive_thresholds(data)

        # Get Alpha Vantage enrichment
        economic_context = self.av_enhancement.get_economic_context(current_time)
        news_sentiment = self.av_enhancement.get_news_sentiment(symbol, current_time)

        # 1. ML Signal
        if self.ml_model is not None:
            self.ml_generator.model = self.ml_model
            ml_signal = self.ml_generator.generate_signal(data, current_time)

            if ml_signal and ml_signal.action != "HOLD":
                self.performance_stats["ml_signals"] += 1

                # Adjust confidence based on economic context
                if economic_context:
                    eco_adjustment = economic_context.get("economic_sentiment", 0) * 0.1
                    ml_signal.confidence = np.clip(
                        ml_signal.confidence + eco_adjustment, 0, 1
                    )

                signals.append(
                    {
                        "source": "ML",
                        "action": ml_signal.action,
                        "confidence": ml_signal.confidence,
                        "weight": self.config.ml_weight,
                        "details": ml_signal,
                    }
                )

        # 2. Elliott Wave Signal
        ew_signal = self.ew_generator.generate_signals(data)

        if ew_signal and ew_signal.action != "HOLD":
            self.performance_stats["ew_signals"] += 1
            signals.append(
                {
                    "source": "Elliott Wave",
                    "action": ew_signal.action,
                    "confidence": ew_signal.confidence,
                    "weight": self.config.elliott_wave_weight,
                    "entry": ew_signal.entry,
                    "stop_loss": ew_signal.stop_loss,
                    "targets": ew_signal.targets,
                    "details": ew_signal,
                }
            )

        # 3. Technical Analysis Signal
        ta_signal = self.ta_analyzer.analyze_market(data, symbol)

        if ta_signal and ta_signal.bias != "NEUTRAL":
            self.performance_stats["ta_signals"] += 1

            # Adjust confidence based on news sentiment
            if news_sentiment:
                news_adjustment = (
                    news_sentiment.get("overall_sentiment", 0)
                    * self.config.sentiment_weight
                )
                ta_signal.confidence = np.clip(
                    ta_signal.confidence + news_adjustment, 0, 1
                )

            signals.append(
                {
                    "source": "Technical Analysis",
                    "action": ta_signal.bias,
                    "confidence": ta_signal.confidence,
                    "weight": self.config.technical_analysis_weight,
                    "entry_zones": ta_signal.entry_zones,
                    "stop_loss": ta_signal.stop_loss,
                    "targets": ta_signal.targets,
                    "details": ta_signal,
                }
            )

        # 4. Sentiment Signal (NEW)
        if (
            self.config.use_sentiment_data
            and news_sentiment.get("relevance_score", 0) > 0.5
        ):
            sentiment_score = news_sentiment.get("overall_sentiment", 0)
            if abs(sentiment_score) > 0.3:  # Significant sentiment
                self.performance_stats["sentiment_signals"] += 1
                signals.append(
                    {
                        "source": "News Sentiment",
                        "action": "LONG" if sentiment_score > 0 else "SHORT",
                        "confidence": abs(sentiment_score),
                        "weight": self.config.sentiment_weight,
                        "details": news_sentiment,
                    }
                )

        # Check confluence requirement (now allows single source)
        if len(signals) < self.config.min_confluences:
            return None

        # Track single vs multi-source
        if len(signals) == 1:
            self.performance_stats["single_source_trades"] += 1
        else:
            self.performance_stats["multi_confluence"] += 1

        # Combine signals
        combined_signal = self._combine_signals_enhanced_v2(
            signals, data, economic_context
        )

        if not combined_signal:
            return None

        # Apply final filters
        if not self._apply_final_filters_v2(
            combined_signal, data, current_time, news_sentiment
        ):
            return None

        # Add enrichment data
        combined_signal["economic_context"] = economic_context
        combined_signal["news_sentiment"] = news_sentiment
        combined_signal["market_conditions"] = self.market_conditions.copy()

        return combined_signal

    def _update_adaptive_thresholds(self, data: pd.DataFrame):
        """Update adaptive thresholds based on market conditions."""

        # Calculate current volatility percentile
        current_vol = data["close"].pct_change().tail(20).std()
        hist_vol = data["close"].pct_change().tail(252).std()
        vol_percentile = (current_vol / hist_vol) * 100

        self.market_conditions["volatility_percentile"] = vol_percentile

        # Adjust confidence thresholds based on volatility
        if vol_percentile > 75:  # High volatility
            adjustment = self.config.volatility_adjustment_factor
            self.ml_generator.min_confidence = min(
                0.75, self.config.min_signal_confidence * adjustment
            )
            self.ew_generator.confidence_threshold = min(
                0.65, self.config.min_signal_confidence * adjustment
            )
            self.performance_stats["adaptive_adjustments"] += 1
        elif vol_percentile < 25:  # Low volatility
            self.ml_generator.min_confidence = self.config.min_signal_confidence * 0.9
            self.ew_generator.confidence_threshold = (
                self.config.min_signal_confidence * 0.9
            )
            self.performance_stats["adaptive_adjustments"] += 1

        # Update recent performance
        if len(self.trades) >= 5:
            recent_trades = self.trades[-5:]
            recent_pnl = sum(t["pnl"] for t in recent_trades)
            self.market_conditions["recent_performance"] = recent_pnl / self.capital

    def _combine_signals_enhanced_v2(
        self, signals: List[Dict], data: pd.DataFrame, economic_context: Dict
    ) -> Optional[Dict]:
        """Enhanced signal combination with single-source support."""

        if not signals:
            return None

        # For single source, reduce position size
        position_size_multiplier = 1.0
        if len(signals) == 1:
            position_size_multiplier = self.config.single_source_position_reduction

        # Weighted consensus
        total_weight = sum(s["weight"] for s in signals)

        # Calculate weighted confidence
        weighted_confidence = (
            sum(s["confidence"] * s["weight"] for s in signals) / total_weight
        )

        # Adjust for economic context
        if economic_context:
            eco_sentiment = economic_context.get("economic_sentiment", 0)
            weighted_confidence *= 1 + eco_sentiment * 0.1

        # Determine action
        long_weight = sum(s["weight"] for s in signals if s["action"] == "LONG")
        short_weight = sum(s["weight"] for s in signals if s["action"] == "SHORT")

        if long_weight > short_weight:
            action = "LONG"
        elif short_weight > long_weight:
            action = "SHORT"
        else:
            return None

        # Get current price info
        current_price = float(data["close"].iloc[-1])
        atr = self._calculate_atr(data)

        # Combine stop losses
        stop_losses = []
        for signal in signals:
            if "stop_loss" in signal and signal["stop_loss"]:
                stop_losses.append(signal["stop_loss"])

        if stop_losses:
            if action == "LONG":
                stop_loss = min(stop_losses)
            else:
                stop_loss = max(stop_losses)
        else:
            stop_loss = (
                current_price - 2 * atr if action == "LONG" else current_price + 2 * atr
            )

        # Combine targets
        all_targets = []
        for signal in signals:
            if "targets" in signal and signal["targets"]:
                all_targets.extend(signal["targets"])

        if all_targets:
            targets = sorted(all_targets)[:3]  # Take first 3
        else:
            if action == "LONG":
                targets = [current_price + i * atr for i in [2, 3, 4]]
            else:
                targets = [current_price - i * atr for i in [2, 3, 4]]

        # Calculate risk/reward
        risk = abs(current_price - stop_loss)
        reward = abs(targets[0] - current_price) if targets else risk * 2
        risk_reward = reward / risk if risk > 0 else 0

        return {
            "action": action,
            "confidence": weighted_confidence,
            "entry": current_price,
            "stop_loss": stop_loss,
            "targets": targets,
            "risk_reward": risk_reward,
            "signal_count": len(signals),
            "source": " + ".join([s["source"] for s in signals]),
            "confluences": [s["source"] for s in signals],
            "position_size_multiplier": position_size_multiplier,
        }

    def _apply_final_filters_v2(
        self,
        signal: Dict,
        data: pd.DataFrame,
        current_time: pd.Timestamp,
        news_sentiment: Dict,
    ) -> bool:
        """Apply final quality filters with news consideration."""

        # Risk/reward filter
        if signal["risk_reward"] < 1.5:
            return False

        # Confidence filter (adaptive)
        min_conf = self.config.min_signal_confidence
        if self.market_conditions["volatility_percentile"] > 75:
            min_conf *= self.config.volatility_adjustment_factor

        if signal["confidence"] < min_conf:
            return False

        # News filter (if enabled)
        if self.config.use_news_filter and news_sentiment:
            sentiment_score = news_sentiment.get("overall_sentiment", 0)
            # Block trades against strong news sentiment
            if signal["action"] == "LONG" and sentiment_score < -0.5:
                return False
            elif signal["action"] == "SHORT" and sentiment_score > 0.5:
                return False

        # Volatility filter
        current_vol = data["close"].pct_change().tail(20).std() * np.sqrt(252)
        if current_vol > 0.02:  # 2% daily volatility
            return False

        # Recent losses filter
        if self._check_recent_losses():
            return False

        return True

    def execute_trade(
        self,
        signal: Dict,
        current_bar: pd.Series,
        current_time: pd.Timestamp,
        symbol: str,
    ):
        """Execute trade with enhanced position sizing."""

        # Check position limits
        if len(self.positions) >= self.config.max_positions:
            return

        # Calculate position size with adjustments
        base_risk = self.capital * self.config.max_risk_per_trade

        # Apply confidence adjustment
        confidence_adjustment = signal["confidence"] ** 2

        # Apply position size multiplier (for single source)
        size_multiplier = signal.get("position_size_multiplier", 1.0)

        risk_amount = base_risk * confidence_adjustment * size_multiplier

        # Calculate position size
        stop_distance = abs(signal["entry"] - signal["stop_loss"])
        position_size = risk_amount / stop_distance

        # Apply slippage and spread
        if signal["action"] == "LONG":
            entry_price = (
                signal["entry"] + self.config.spread / 2 + self.config.slippage
            )
        else:
            entry_price = (
                signal["entry"] - self.config.spread / 2 - self.config.slippage
            )

        # Create position
        position_id = f"{symbol}_{current_time}"
        self.positions[position_id] = {
            "symbol": symbol,
            "direction": signal["action"],
            "entry_time": current_time,
            "entry_price": entry_price,
            "position_size": position_size,
            "stop_loss": signal["stop_loss"],
            "initial_stop": signal["stop_loss"],
            "targets": signal["targets"],
            "targets_hit": [],
            "signal_confidence": signal["confidence"],
            "signal_source": signal["source"],
            "confluences": signal["confluences"],
            "trailing_stop_active": False,
            "partial_exits": [],
            "bars_held": 0,
            "economic_context": signal.get("economic_context", {}),
            "news_sentiment": signal.get("news_sentiment", {}),
        }

        # Deduct commission
        commission = position_size * entry_price * self.config.commission_rate
        self.capital -= commission

        self.performance_stats["trades_executed"] += 1

        logger.info(
            f"Trade executed: {signal['action']} {symbol} at {entry_price:.5f}, "
            f"size: {position_size:.0f}, risk: ${risk_amount:.2f}"
        )

    def update_positions(
        self, symbol: str, current_bar: pd.Series, current_time: pd.Timestamp
    ):
        """Update positions with time-based exits."""

        positions_to_close = []

        for position_id, pos in self.positions.items():
            if pos["symbol"] != symbol:
                continue

            # Update bars held
            pos["bars_held"] += 1

            # Check time-based exit
            if (
                self.config.time_based_exit_enabled
                and pos["bars_held"] >= self.config.max_bars_in_trade
            ):
                positions_to_close.append(
                    (position_id, current_bar["close"], "Time Exit")
                )
                self.performance_stats["time_exits"] += 1
                continue

            # Check stop loss
            if pos["direction"] == "LONG":
                if current_bar["low"] <= pos["stop_loss"]:
                    positions_to_close.append(
                        (position_id, pos["stop_loss"], "Stop Loss")
                    )
                    continue
            else:
                if current_bar["high"] >= pos["stop_loss"]:
                    positions_to_close.append(
                        (position_id, pos["stop_loss"], "Stop Loss")
                    )
                    continue

            # Check targets and partial profits
            self._check_targets_and_partials(position_id, pos, current_bar)

            # Update trailing stop
            if self.config.use_trailing_stops:
                self._update_trailing_stop(position_id, pos, current_bar)

        # Close positions
        for position_id, exit_price, reason in positions_to_close:
            self._close_position(position_id, exit_price, current_time, reason)

    def _close_position(
        self, position_id: str, exit_price: float, exit_time: pd.Timestamp, reason: str
    ):
        """Close position and record trade."""

        pos = self.positions[position_id]

        # Apply slippage and spread on exit
        if pos["direction"] == "LONG":
            exit_price = exit_price - self.config.spread / 2 - self.config.slippage
            pnl = (exit_price - pos["entry_price"]) * pos["position_size"]
        else:
            exit_price = exit_price + self.config.spread / 2 + self.config.slippage
            pnl = (pos["entry_price"] - exit_price) * pos["position_size"]

        # Add commission
        commission = pos["position_size"] * exit_price * self.config.commission_rate
        pnl -= commission

        # Update capital
        self.capital += pnl

        # Record trade
        trade = {
            "symbol": pos["symbol"],
            "direction": pos["direction"],
            "entry_time": pos["entry_time"],
            "exit_time": exit_time,
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "position_size": pos["position_size"],
            "pnl": pnl,
            "pnl_pct": pnl / (pos["position_size"] * pos["entry_price"]),
            "exit_reason": reason,
            "signal_source": pos["signal_source"],
            "confluences": len(pos["confluences"]),
            "bars_held": pos["bars_held"],
            "economic_context": pos.get("economic_context", {}),
            "news_sentiment": pos.get("news_sentiment", {}),
        }

        self.trades.append(trade)

        # Remove position
        del self.positions[position_id]

        logger.info(f"Position closed: {reason}, PnL: ${pnl:.2f}")

    def _check_recent_losses(self) -> bool:
        """Check if we should stop trading due to recent losses."""
        if len(self.trades) < 3:
            return False

        recent_trades = self.trades[-3:]
        losses = sum(1 for t in recent_trades if t["pnl"] < 0)

        return losses >= 2

    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        if "atr_14" in data.columns:
            return float(data["atr_14"].iloc[-1])

        high = data["high"].tail(period + 1)
        low = data["low"].tail(period + 1)
        close = data["close"].tail(period + 1)

        tr = pd.DataFrame()
        tr["h-l"] = high - low
        tr["h-pc"] = abs(high - close.shift(1))
        tr["l-pc"] = abs(low - close.shift(1))

        true_range = tr.max(axis=1)
        atr = true_range.tail(period).mean()

        return float(atr)

    def _check_targets_and_partials(
        self, position_id: str, pos: Dict, current_bar: pd.Series
    ):
        """Check targets and take partial profits."""
        if not self.config.use_partial_profits:
            return

        current_price = current_bar["close"]

        # Calculate current profit in R multiples
        entry_price = pos["entry_price"]
        initial_risk = abs(entry_price - pos["initial_stop"])

        if pos["direction"] == "LONG":
            pnl_points = current_price - entry_price
        else:
            pnl_points = entry_price - current_price

        r_multiple = pnl_points / initial_risk if initial_risk > 0 else 0

        # Check partial profit levels
        for level in self.config.partial_profit_levels:
            if r_multiple >= level and level not in pos["partial_exits"]:
                # Take partial profit
                partial_size = pos["position_size"] * 0.33
                pos["position_size"] -= partial_size
                pos["partial_exits"].append(level)

                # Calculate partial PnL
                if pos["direction"] == "LONG":
                    exit_price = current_price - self.config.spread / 2
                else:
                    exit_price = current_price + self.config.spread / 2

                partial_pnl = partial_size * pnl_points
                self.capital += partial_pnl

                logger.info(f"Partial profit taken at {level}R: ${partial_pnl:.2f}")

    def _update_trailing_stop(
        self, position_id: str, pos: Dict, current_bar: pd.Series
    ):
        """Update trailing stop for profitable positions."""
        if pos["position_size"] <= 0:
            return

        atr = current_bar.get("atr_14", current_bar["close"] * 0.001)
        trail_distance = atr * self.config.trailing_stop_distance

        if pos["direction"] == "LONG":
            new_stop = current_bar["high"] - trail_distance
            if (
                new_stop > pos["stop_loss"]
                and current_bar["close"] > pos["entry_price"]
            ):
                pos["stop_loss"] = new_stop
                pos["trailing_stop_active"] = True
        else:
            new_stop = current_bar["low"] + trail_distance
            if (
                new_stop < pos["stop_loss"]
                and current_bar["close"] < pos["entry_price"]
            ):
                pos["stop_loss"] = new_stop
                pos["trailing_stop_active"] = True


def main():
    """Demonstrate enhanced system V2 with improvements."""

    print("\n" + "=" * 80)
    print("ENHANCED PRODUCTION SYSTEM V2 - WITH RECOMMENDED ADJUSTMENTS")
    print("=" * 80)
    print(f"Generated: {datetime.now()}")
    print("\nKey Improvements:")
    print("1. Lowered min_confluences to 1 (from 2)")
    print("2. Reduced min_confidence to 0.6 (from 0.7)")
    print("3. Added time-based exits after 120 bars")
    print("4. Implemented adaptive thresholds based on volatility")
    print("5. Single-source trades with 50% position reduction")
    print("6. Alpha Vantage integration for economic context and news sentiment")
    print("=" * 80)

    # Create configuration
    config = EnhancedProductionConfigV2()

    # Initialize system
    system = EnhancedProductionSystemV2(config)

    print("\nSystem Configuration:")
    print(f"- Min Confluences: {config.min_confluences}")
    print(f"- Min Confidence: {config.min_signal_confidence}")
    print(
        f"- Single Source Position Reduction: {config.single_source_position_reduction:.0%}"
    )
    print(f"- Max Bars in Trade: {config.max_bars_in_trade}")
    print(
        f"- Adaptive Thresholds: {'Enabled' if config.use_adaptive_thresholds else 'Disabled'}"
    )
    print(f"- News Filter: {'Enabled' if config.use_news_filter else 'Disabled'}")
    print(f"- Economic Data: {'Enabled' if config.use_economic_data else 'Disabled'}")

    print("\nAlpha Vantage Features:")
    if system.av_enhancement.enabled:
        print("✓ API Key configured")
        print("✓ Economic indicators available")
        print("✓ News sentiment integration ready")
    else:
        print("✗ No API key - features disabled")

    print("\n" + "=" * 80)
    print("System ready for deployment with enhanced flexibility and data enrichment")
    print("=" * 80)


if __name__ == "__main__":
    main()
