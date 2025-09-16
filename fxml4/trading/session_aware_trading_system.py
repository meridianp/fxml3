"""
Session-Aware Trading System for Global Forex Markets

This module implements a comprehensive session-aware trading system that:
- Optimizes trading strategies for Tokyo, London, New York sessions
- Analyzes session-specific volatility and liquidity patterns
- Implements session overlap detection and optimization
- Provides currency pair session preferences and scoring
- Integrates with economic calendar for session-based events
- Offers real-time session transition management
"""

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import pytz

logger = logging.getLogger(__name__)


class TradingSession(Enum):
    """Global forex trading sessions."""

    TOKYO = "tokyo"  # 00:00-09:00 UTC (Asian session)
    LONDON = "london"  # 08:00-16:00 UTC (European session)
    NEW_YORK = "new_york"  # 13:00-21:00 UTC (North American session)
    SYDNEY = "sydney"  # 22:00-07:00 UTC (Asia-Pacific session)

    # Session overlaps (highest activity periods)
    TOKYO_LONDON = "tokyo_london"  # 08:00-09:00 UTC
    LONDON_NY = "london_new_york"  # 13:00-16:00 UTC

    # Extended sessions
    EXTENDED_LONDON = "extended_london"  # 07:00-17:00 UTC
    EXTENDED_NY = "extended_new_york"  # 12:00-22:00 UTC


class SessionIntensity(Enum):
    """Session trading intensity levels."""

    VERY_LOW = 0.2
    LOW = 0.4
    MODERATE = 0.6
    HIGH = 0.8
    VERY_HIGH = 1.0


@dataclass
class SessionCharacteristics:
    """Characteristics of a trading session."""

    name: str
    start_utc: int  # Start hour in UTC
    end_utc: int  # End hour in UTC
    peak_hours: List[int]  # Peak activity hours
    typical_spread: float  # Typical spread in pips
    average_volatility: float  # Average volatility
    liquidity_score: float  # Liquidity rating 0-1
    preferred_pairs: List[str]  # Preferred currency pairs
    economic_events: List[str]  # Typical economic events
    market_makers: List[str]  # Active market makers
    trading_style: str  # 'trend_following', 'range_bound', 'breakout'


@dataclass
class SessionMetrics:
    """Real-time session trading metrics."""

    session: TradingSession
    current_intensity: float
    volatility_percentile: float
    spread_percentile: float
    volume_percentile: float
    momentum_score: float
    reversal_probability: float
    optimal_pairs: List[str]
    risk_level: str
    trading_recommendation: str


@dataclass
class CurrencySessionPreference:
    """Currency pair session preferences."""

    pair: str
    session_scores: Dict[TradingSession, float]
    optimal_sessions: List[TradingSession]
    avoid_sessions: List[TradingSession]
    volatility_by_session: Dict[TradingSession, float]
    spread_by_session: Dict[TradingSession, float]
    historical_performance: Dict[TradingSession, float]


class SessionAwareAnalyzer:
    """Analyzes trading session characteristics and patterns."""

    def __init__(self):
        """Initialize session analyzer."""
        self.session_definitions = self._initialize_session_definitions()
        self.currency_preferences = self._initialize_currency_preferences()
        self.session_history = deque(maxlen=1000)
        self.volatility_cache = {}
        self.spread_cache = {}

    def _initialize_session_definitions(
        self,
    ) -> Dict[TradingSession, SessionCharacteristics]:
        """Initialize session definitions with characteristics."""
        return {
            TradingSession.TOKYO: SessionCharacteristics(
                name="Tokyo/Asian Session",
                start_utc=0,
                end_utc=9,
                peak_hours=[2, 3, 4, 5],
                typical_spread=1.8,
                average_volatility=0.0065,
                liquidity_score=0.6,
                preferred_pairs=["USDJPY", "AUDJPY", "NZDJPY", "EURJPY"],
                economic_events=["BOJ_RATE", "JAPAN_GDP", "TANKAN_SURVEY"],
                market_makers=["Japanese_Banks", "Asian_Hedge_Funds"],
                trading_style="range_bound",
            ),
            TradingSession.LONDON: SessionCharacteristics(
                name="London/European Session",
                start_utc=8,
                end_utc=16,
                peak_hours=[9, 10, 11, 14, 15],
                typical_spread=0.8,
                average_volatility=0.0095,
                liquidity_score=1.0,
                preferred_pairs=["EURUSD", "GBPUSD", "EURGBP", "USDCHF"],
                economic_events=["ECB_RATE", "BOE_RATE", "EU_GDP", "UK_INFLATION"],
                market_makers=["European_Banks", "London_Funds"],
                trading_style="trend_following",
            ),
            TradingSession.NEW_YORK: SessionCharacteristics(
                name="New York/North American Session",
                start_utc=13,
                end_utc=21,
                peak_hours=[14, 15, 16, 19, 20],
                typical_spread=0.9,
                average_volatility=0.0085,
                liquidity_score=0.9,
                preferred_pairs=["EURUSD", "GBPUSD", "USDCAD", "USDMXN"],
                economic_events=["FED_RATE", "NFP", "US_GDP", "US_INFLATION"],
                market_makers=["US_Banks", "Hedge_Funds", "Pension_Funds"],
                trading_style="breakout",
            ),
            TradingSession.SYDNEY: SessionCharacteristics(
                name="Sydney/Asia-Pacific Session",
                start_utc=22,
                end_utc=7,  # Next day
                peak_hours=[23, 0, 1, 5, 6],
                typical_spread=2.2,
                average_volatility=0.0055,
                liquidity_score=0.4,
                preferred_pairs=["AUDUSD", "NZDUSD", "AUDNZD", "AUDJPY"],
                economic_events=["RBA_RATE", "AU_GDP", "NZ_GDP"],
                market_makers=["Australian_Banks", "NZ_Banks"],
                trading_style="range_bound",
            ),
            TradingSession.LONDON_NY: SessionCharacteristics(
                name="London-New York Overlap",
                start_utc=13,
                end_utc=16,
                peak_hours=[13, 14, 15],
                typical_spread=0.6,
                average_volatility=0.0125,
                liquidity_score=1.2,
                preferred_pairs=["EURUSD", "GBPUSD", "USDCHF", "USDCAD"],
                economic_events=["CROSS_SESSION_EVENTS"],
                market_makers=["Global_Banks", "Institutional_Flows"],
                trading_style="trend_following",
            ),
            TradingSession.TOKYO_LONDON: SessionCharacteristics(
                name="Tokyo-London Overlap",
                start_utc=8,
                end_utc=9,
                peak_hours=[8],
                typical_spread=1.1,
                average_volatility=0.0075,
                liquidity_score=0.8,
                preferred_pairs=["USDJPY", "EURJPY", "GBPJPY"],
                economic_events=["ASIA_EUROPE_TRANSITION"],
                market_makers=["Asian_European_Banks"],
                trading_style="breakout",
            ),
        }

    def _initialize_currency_preferences(self) -> Dict[str, CurrencySessionPreference]:
        """Initialize currency pair session preferences."""
        return {
            "EURUSD": CurrencySessionPreference(
                pair="EURUSD",
                session_scores={
                    TradingSession.TOKYO: 0.4,
                    TradingSession.LONDON: 1.0,
                    TradingSession.NEW_YORK: 0.9,
                    TradingSession.SYDNEY: 0.3,
                    TradingSession.LONDON_NY: 1.2,
                    TradingSession.TOKYO_LONDON: 0.6,
                },
                optimal_sessions=[TradingSession.LONDON_NY, TradingSession.LONDON],
                avoid_sessions=[TradingSession.SYDNEY],
                volatility_by_session={
                    TradingSession.TOKYO: 0.0055,
                    TradingSession.LONDON: 0.0095,
                    TradingSession.NEW_YORK: 0.0085,
                    TradingSession.LONDON_NY: 0.0125,
                },
                spread_by_session={
                    TradingSession.TOKYO: 1.5,
                    TradingSession.LONDON: 0.7,
                    TradingSession.NEW_YORK: 0.8,
                    TradingSession.LONDON_NY: 0.5,
                },
                historical_performance={
                    TradingSession.LONDON: 0.067,
                    TradingSession.LONDON_NY: 0.089,
                    TradingSession.NEW_YORK: 0.045,
                },
            ),
            "GBPUSD": CurrencySessionPreference(
                pair="GBPUSD",
                session_scores={
                    TradingSession.TOKYO: 0.3,
                    TradingSession.LONDON: 1.2,
                    TradingSession.NEW_YORK: 0.8,
                    TradingSession.SYDNEY: 0.2,
                    TradingSession.LONDON_NY: 1.1,
                    TradingSession.TOKYO_LONDON: 0.7,
                },
                optimal_sessions=[TradingSession.LONDON],
                avoid_sessions=[TradingSession.SYDNEY, TradingSession.TOKYO],
                volatility_by_session={
                    TradingSession.TOKYO: 0.0045,
                    TradingSession.LONDON: 0.0115,
                    TradingSession.NEW_YORK: 0.0075,
                    TradingSession.LONDON_NY: 0.0105,
                },
                spread_by_session={
                    TradingSession.TOKYO: 2.1,
                    TradingSession.LONDON: 0.9,
                    TradingSession.NEW_YORK: 1.1,
                    TradingSession.LONDON_NY: 0.7,
                },
                historical_performance={
                    TradingSession.LONDON: 0.078,
                    TradingSession.LONDON_NY: 0.058,
                    TradingSession.NEW_YORK: 0.032,
                },
            ),
            "USDJPY": CurrencySessionPreference(
                pair="USDJPY",
                session_scores={
                    TradingSession.TOKYO: 1.1,
                    TradingSession.LONDON: 0.7,
                    TradingSession.NEW_YORK: 0.9,
                    TradingSession.SYDNEY: 0.8,
                    TradingSession.LONDON_NY: 0.8,
                    TradingSession.TOKYO_LONDON: 1.0,
                },
                optimal_sessions=[TradingSession.TOKYO, TradingSession.TOKYO_LONDON],
                avoid_sessions=[],
                volatility_by_session={
                    TradingSession.TOKYO: 0.0085,
                    TradingSession.LONDON: 0.0065,
                    TradingSession.NEW_YORK: 0.0075,
                    TradingSession.TOKYO_LONDON: 0.0095,
                },
                spread_by_session={
                    TradingSession.TOKYO: 1.2,
                    TradingSession.LONDON: 1.8,
                    TradingSession.NEW_YORK: 1.5,
                    TradingSession.TOKYO_LONDON: 1.0,
                },
                historical_performance={
                    TradingSession.TOKYO: 0.054,
                    TradingSession.TOKYO_LONDON: 0.071,
                    TradingSession.NEW_YORK: 0.038,
                },
            ),
            "USDCHF": CurrencySessionPreference(
                pair="USDCHF",
                session_scores={
                    TradingSession.TOKYO: 0.4,
                    TradingSession.LONDON: 0.9,
                    TradingSession.NEW_YORK: 0.8,
                    TradingSession.SYDNEY: 0.3,
                    TradingSession.LONDON_NY: 1.0,
                    TradingSession.TOKYO_LONDON: 0.6,
                },
                optimal_sessions=[TradingSession.LONDON_NY, TradingSession.LONDON],
                avoid_sessions=[TradingSession.SYDNEY],
                volatility_by_session={
                    TradingSession.TOKYO: 0.0045,
                    TradingSession.LONDON: 0.0075,
                    TradingSession.NEW_YORK: 0.0065,
                    TradingSession.LONDON_NY: 0.0095,
                },
                spread_by_session={
                    TradingSession.TOKYO: 2.0,
                    TradingSession.LONDON: 1.1,
                    TradingSession.NEW_YORK: 1.3,
                    TradingSession.LONDON_NY: 0.8,
                },
                historical_performance={
                    TradingSession.LONDON: 0.043,
                    TradingSession.LONDON_NY: 0.056,
                    TradingSession.NEW_YORK: 0.029,
                },
            ),
        }

    def get_current_session(
        self, utc_time: datetime = None
    ) -> Tuple[TradingSession, float]:
        """Get current trading session and intensity."""
        if utc_time is None:
            utc_time = datetime.now(timezone.utc)

        hour = utc_time.hour
        minute = utc_time.minute
        time_decimal = hour + minute / 60.0

        # Check for overlap sessions first (highest priority)
        if 13 <= hour < 16:
            intensity = self._calculate_overlap_intensity(time_decimal, 13, 16)
            return TradingSession.LONDON_NY, intensity

        elif 8 <= hour < 9:
            intensity = self._calculate_overlap_intensity(time_decimal, 8, 9)
            return TradingSession.TOKYO_LONDON, intensity

        # Check regular sessions
        for session, characteristics in self.session_definitions.items():
            if session in [TradingSession.LONDON_NY, TradingSession.TOKYO_LONDON]:
                continue  # Already checked overlaps

            start_hour = characteristics.start_utc
            end_hour = characteristics.end_utc

            if self._is_in_session(hour, start_hour, end_hour):
                intensity = self._calculate_session_intensity(
                    time_decimal, characteristics
                )
                return session, intensity

        # Default fallback
        return TradingSession.SYDNEY, 0.3

    def _is_in_session(self, current_hour: int, start_hour: int, end_hour: int) -> bool:
        """Check if current hour is within session."""
        if start_hour <= end_hour:
            return start_hour <= current_hour < end_hour
        else:  # Session crosses midnight
            return current_hour >= start_hour or current_hour < end_hour

    def _calculate_session_intensity(
        self, time_decimal: float, characteristics: SessionCharacteristics
    ) -> float:
        """Calculate session intensity based on time and characteristics."""
        start_time = characteristics.start_utc
        end_time = characteristics.end_utc
        peak_hours = characteristics.peak_hours

        # Base intensity from session time
        if end_time > start_time:
            session_duration = end_time - start_time
            time_from_start = time_decimal - start_time
        else:  # Crosses midnight
            session_duration = (24 - start_time) + end_time
            if time_decimal >= start_time:
                time_from_start = time_decimal - start_time
            else:
                time_from_start = (24 - start_time) + time_decimal

        # Create intensity curve (ramp up, peak, ramp down)
        session_progress = time_from_start / session_duration

        base_intensity = 0.3
        if session_progress <= 0.3:  # Ramp up
            base_intensity = 0.3 + (session_progress / 0.3) * 0.4
        elif session_progress <= 0.7:  # Peak period
            base_intensity = 0.7 + 0.3 * np.sin((session_progress - 0.3) / 0.4 * np.pi)
        else:  # Ramp down
            base_intensity = 0.7 - ((session_progress - 0.7) / 0.3) * 0.4

        # Boost for peak hours
        current_hour = int(time_decimal)
        if current_hour in peak_hours:
            base_intensity *= 1.3

        return min(1.0, base_intensity)

    def _calculate_overlap_intensity(
        self, time_decimal: float, start: int, end: int
    ) -> float:
        """Calculate intensity for overlap periods."""
        duration = end - start
        time_from_start = time_decimal - start

        # Overlap periods have high, sustained intensity
        progress = time_from_start / duration

        # Peak in the middle of overlap
        if progress <= 0.5:
            return 0.8 + 0.4 * (progress * 2)  # 0.8 to 1.2
        else:
            return 1.2 - 0.4 * ((progress - 0.5) * 2)  # 1.2 to 0.8

    def get_session_score_for_pair(self, pair: str, session: TradingSession) -> float:
        """Get session preference score for currency pair."""
        preferences = self.currency_preferences.get(pair)
        if not preferences:
            return 0.5  # Default neutral score

        return preferences.session_scores.get(session, 0.5)

    def get_optimal_pairs_for_session(
        self, session: TradingSession, min_score: float = 0.8
    ) -> List[str]:
        """Get optimal currency pairs for trading session."""
        optimal_pairs = []

        for pair, preferences in self.currency_preferences.items():
            score = preferences.session_scores.get(session, 0.0)
            if score >= min_score:
                optimal_pairs.append(pair)

        # Sort by score
        optimal_pairs.sort(
            key=lambda p: self.currency_preferences[p].session_scores.get(session, 0.0),
            reverse=True,
        )

        return optimal_pairs

    def analyze_session_transition(
        self, current_session: TradingSession, next_session: TradingSession
    ) -> Dict[str, Any]:
        """Analyze trading implications of session transition."""
        current_chars = self.session_definitions[current_session]
        next_chars = self.session_definitions[next_session]

        # Calculate transition metrics
        liquidity_change = next_chars.liquidity_score - current_chars.liquidity_score
        volatility_change = (
            next_chars.average_volatility - current_chars.average_volatility
        )
        spread_change = next_chars.typical_spread - current_chars.typical_spread

        # Determine transition type
        transition_type = "neutral"
        if liquidity_change > 0.2:
            transition_type = "increasing_activity"
        elif liquidity_change < -0.2:
            transition_type = "decreasing_activity"

        # Risk implications
        risk_level = "low"
        if abs(volatility_change) > 0.003 or abs(spread_change) > 0.5:
            risk_level = "medium"
        if abs(volatility_change) > 0.005 or abs(spread_change) > 1.0:
            risk_level = "high"

        # Trading recommendations
        recommendations = []
        if transition_type == "increasing_activity":
            recommendations.append("Prepare for increased volatility")
            recommendations.append("Tighten stop losses")
            recommendations.append("Consider momentum strategies")
        elif transition_type == "decreasing_activity":
            recommendations.append("Reduce position sizes")
            recommendations.append("Focus on range-bound strategies")
            recommendations.append("Widen spreads")

        return {
            "transition_type": transition_type,
            "liquidity_change": liquidity_change,
            "volatility_change": volatility_change,
            "spread_change": spread_change,
            "risk_level": risk_level,
            "recommendations": recommendations,
            "optimal_pairs_current": self.get_optimal_pairs_for_session(
                current_session
            ),
            "optimal_pairs_next": self.get_optimal_pairs_for_session(next_session),
        }


class SessionAwareTradingSystem:
    """Complete session-aware trading system."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize session-aware trading system."""
        self.config = config or self._get_default_config()
        self.session_analyzer = SessionAwareAnalyzer()

        # Session monitoring
        self.current_session = None
        self.session_intensity = 0.0
        self.session_start_time = None
        self.next_session_time = None

        # Performance tracking
        self.session_performance = defaultdict(
            lambda: {"trades": 0, "pnl": 0.0, "win_rate": 0.0}
        )
        self.pair_session_performance = defaultdict(dict)

        # Real-time data
        self.current_spreads = {}
        self.current_volatilities = {}
        self.current_volumes = {}

        # Trading parameters by session
        self.session_trading_params = self._initialize_session_params()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "session_transition_buffer": 30,  # minutes before/after session
            "min_intensity_for_trading": 0.4,
            "max_pairs_per_session": 3,
            "session_momentum_threshold": 0.8,
            "volatility_adjustment_factor": 1.5,
            "spread_penalty_factor": 0.1,
            "overlap_bonus_factor": 1.3,
            "session_switch_delay": 15,  # minutes
            "risk_adjustment_by_session": True,
            "auto_close_before_session_end": True,
            "session_based_position_sizing": True,
        }

    def _initialize_session_params(self) -> Dict[TradingSession, Dict[str, Any]]:
        """Initialize trading parameters by session."""
        return {
            TradingSession.TOKYO: {
                "max_risk_per_trade": 0.015,
                "preferred_strategy_style": "range_bound",
                "stop_loss_multiplier": 1.2,
                "take_profit_multiplier": 1.5,
                "position_hold_time_max": 4,  # hours
                "risk_reward_min": 1.5,
            },
            TradingSession.LONDON: {
                "max_risk_per_trade": 0.025,
                "preferred_strategy_style": "trend_following",
                "stop_loss_multiplier": 1.0,
                "take_profit_multiplier": 2.0,
                "position_hold_time_max": 6,  # hours
                "risk_reward_min": 2.0,
            },
            TradingSession.NEW_YORK: {
                "max_risk_per_trade": 0.02,
                "preferred_strategy_style": "breakout",
                "stop_loss_multiplier": 1.1,
                "take_profit_multiplier": 1.8,
                "position_hold_time_max": 5,  # hours
                "risk_reward_min": 1.8,
            },
            TradingSession.LONDON_NY: {
                "max_risk_per_trade": 0.03,
                "preferred_strategy_style": "trend_following",
                "stop_loss_multiplier": 0.9,
                "take_profit_multiplier": 2.5,
                "position_hold_time_max": 3,  # hours
                "risk_reward_min": 2.5,
            },
            TradingSession.SYDNEY: {
                "max_risk_per_trade": 0.01,
                "preferred_strategy_style": "range_bound",
                "stop_loss_multiplier": 1.3,
                "take_profit_multiplier": 1.2,
                "position_hold_time_max": 8,  # hours
                "risk_reward_min": 1.2,
            },
        }

    async def update_session_context(self):
        """Update current session context."""
        try:
            # Get current session
            session, intensity = self.session_analyzer.get_current_session()

            # Check for session change
            if session != self.current_session:
                await self._handle_session_transition(self.current_session, session)
                self.current_session = session
                self.session_start_time = datetime.now(timezone.utc)

            self.session_intensity = intensity

            # Calculate next session time
            self.next_session_time = self._calculate_next_session_time()

            # Update market data
            await self._update_market_data()

        except Exception as e:
            logger.error(f"Error updating session context: {str(e)}")

    async def _handle_session_transition(
        self, old_session: TradingSession, new_session: TradingSession
    ):
        """Handle transition between trading sessions."""
        logger.info(f"Session transition: {old_session} -> {new_session}")

        if old_session:
            # Analyze transition implications
            transition_analysis = self.session_analyzer.analyze_session_transition(
                old_session, new_session
            )

            # Log transition metrics
            logger.info(
                f"Transition analysis: {transition_analysis['transition_type']}"
            )
            logger.info(f"Risk level: {transition_analysis['risk_level']}")

            # Handle position management for session change
            await self._manage_positions_for_session_change(
                old_session, new_session, transition_analysis
            )

        # Update trading parameters for new session
        self._update_trading_parameters(new_session)

        # Log session characteristics
        session_chars = self.session_analyzer.session_definitions[new_session]
        logger.info(f"New session: {session_chars.name}")
        logger.info(f"Preferred pairs: {session_chars.preferred_pairs}")
        logger.info(f"Trading style: {session_chars.trading_style}")

    async def _manage_positions_for_session_change(
        self,
        old_session: TradingSession,
        new_session: TradingSession,
        transition_analysis: Dict[str, Any],
    ):
        """Manage existing positions during session transition."""
        # This would integrate with the portfolio manager
        # to adjust stops, take profits, or close positions
        # based on session change implications

        risk_level = transition_analysis["risk_level"]

        if risk_level == "high":
            logger.info("High risk session transition - consider tightening stops")

        # Example logic:
        # - Close positions in pairs that are suboptimal for new session
        # - Adjust position sizes based on new session characteristics
        # - Update stop losses based on new session volatility expectations

    def _update_trading_parameters(self, session: TradingSession):
        """Update trading parameters for new session."""
        params = self.session_trading_params.get(session, {})

        # Update global trading parameters based on session
        self.current_max_risk = params.get("max_risk_per_trade", 0.02)
        self.current_strategy_style = params.get(
            "preferred_strategy_style", "trend_following"
        )
        self.current_stop_multiplier = params.get("stop_loss_multiplier", 1.0)
        self.current_tp_multiplier = params.get("take_profit_multiplier", 2.0)

        logger.info(f"Updated trading parameters for {session.value}")
        logger.info(
            f"Max risk: {self.current_max_risk}, Style: {self.current_strategy_style}"
        )

    def _calculate_next_session_time(self) -> datetime:
        """Calculate when the next session starts."""
        current_time = datetime.now(timezone.utc)
        current_hour = current_time.hour

        # Define session start times
        session_starts = [0, 8, 13, 22]  # Tokyo, London, NY, Sydney

        # Find next session start
        next_start = None
        for start in session_starts:
            if start > current_hour:
                next_start = start
                break

        if next_start is None:
            next_start = session_starts[0]  # Next day
            next_day = current_time + timedelta(days=1)
            return next_day.replace(hour=next_start, minute=0, second=0, microsecond=0)
        else:
            return current_time.replace(
                hour=next_start, minute=0, second=0, microsecond=0
            )

    async def _update_market_data(self):
        """Update real-time market data for session analysis."""
        # Placeholder - would fetch real market data
        # Update spreads, volatilities, volumes for each pair
        pass

    def get_session_metrics(self) -> SessionMetrics:
        """Get current session metrics."""
        if not self.current_session:
            return SessionMetrics(
                session=TradingSession.SYDNEY,
                current_intensity=0.0,
                volatility_percentile=50.0,
                spread_percentile=50.0,
                volume_percentile=50.0,
                momentum_score=0.0,
                reversal_probability=0.5,
                optimal_pairs=[],
                risk_level="medium",
                trading_recommendation="Wait for session clarity",
            )

        # Calculate percentiles and scores
        volatility_percentile = self._calculate_volatility_percentile()
        spread_percentile = self._calculate_spread_percentile()
        volume_percentile = self._calculate_volume_percentile()
        momentum_score = self._calculate_momentum_score()
        reversal_probability = self._calculate_reversal_probability()

        # Get optimal pairs for current session
        optimal_pairs = self.session_analyzer.get_optimal_pairs_for_session(
            self.current_session
        )

        # Determine risk level
        risk_level = self._determine_risk_level()

        # Generate trading recommendation
        trading_recommendation = self._generate_trading_recommendation()

        return SessionMetrics(
            session=self.current_session,
            current_intensity=self.session_intensity,
            volatility_percentile=volatility_percentile,
            spread_percentile=spread_percentile,
            volume_percentile=volume_percentile,
            momentum_score=momentum_score,
            reversal_probability=reversal_probability,
            optimal_pairs=optimal_pairs,
            risk_level=risk_level,
            trading_recommendation=trading_recommendation,
        )

    def _calculate_volatility_percentile(self) -> float:
        """Calculate current volatility percentile for session."""
        # Placeholder - would calculate from historical data
        return 65.0

    def _calculate_spread_percentile(self) -> float:
        """Calculate current spread percentile for session."""
        # Placeholder - would calculate from current vs historical spreads
        return 45.0

    def _calculate_volume_percentile(self) -> float:
        """Calculate current volume percentile for session."""
        # Placeholder - would calculate from current vs historical volume
        return 78.0

    def _calculate_momentum_score(self) -> float:
        """Calculate current momentum score."""
        # Placeholder - would analyze price momentum across pairs
        return 0.72

    def _calculate_reversal_probability(self) -> float:
        """Calculate probability of trend reversal."""
        # Placeholder - would use ML model or technical analysis
        return 0.25

    def _determine_risk_level(self) -> str:
        """Determine current risk level."""
        if self.session_intensity < 0.4:
            return "low"
        elif self.session_intensity < 0.7:
            return "medium"
        else:
            return "high"

    def _generate_trading_recommendation(self) -> str:
        """Generate trading recommendation based on session context."""
        intensity = self.session_intensity
        session_chars = self.session_analyzer.session_definitions[self.current_session]

        if intensity < 0.4:
            return f"Low activity - consider {session_chars.trading_style} with reduced size"
        elif intensity < 0.7:
            return f"Moderate activity - normal {session_chars.trading_style} approach"
        else:
            return f"High activity - aggressive {session_chars.trading_style} with tight risk management"

    def calculate_session_adjusted_position_size(
        self, base_size: float, pair: str
    ) -> float:
        """Calculate position size adjusted for session characteristics."""
        if not self.current_session:
            return base_size

        # Get session score for pair
        session_score = self.session_analyzer.get_session_score_for_pair(
            pair, self.current_session
        )

        # Get session parameters
        session_params = self.session_trading_params.get(self.current_session, {})
        max_risk = session_params.get("max_risk_per_trade", 0.02)

        # Adjust based on session intensity
        intensity_multiplier = 0.5 + (self.session_intensity * 0.5)  # 0.5 to 1.0

        # Adjust based on pair-session fit
        session_multiplier = 0.5 + (session_score * 0.5)  # 0.5 to 1.0

        # Calculate adjusted size
        adjusted_size = base_size * intensity_multiplier * session_multiplier

        # Apply session risk limits
        max_size = base_size * (max_risk / 0.02)  # Normalize to base 2% risk
        adjusted_size = min(adjusted_size, max_size)

        return adjusted_size

    def should_trade_pair_in_session(self, pair: str, min_score: float = 0.6) -> bool:
        """Determine if pair should be traded in current session."""
        if not self.current_session:
            return False

        # Check session score
        session_score = self.session_analyzer.get_session_score_for_pair(
            pair, self.current_session
        )
        if session_score < min_score:
            return False

        # Check session intensity
        if self.session_intensity < self.config["min_intensity_for_trading"]:
            return False

        # Check if pair is in avoid list for session
        preferences = self.session_analyzer.currency_preferences.get(pair)
        if preferences and self.current_session in preferences.avoid_sessions:
            return False

        return True

    def get_time_until_session_end(self) -> timedelta:
        """Get time remaining in current session."""
        if not self.current_session or not self.session_start_time:
            return timedelta(0)

        session_chars = self.session_analyzer.session_definitions[self.current_session]
        current_time = datetime.now(timezone.utc)

        # Calculate session end time
        start_hour = session_chars.start_utc
        end_hour = session_chars.end_utc

        if end_hour > start_hour:
            session_end = current_time.replace(
                hour=end_hour, minute=0, second=0, microsecond=0
            )
            if current_time.hour >= end_hour:
                session_end += timedelta(days=1)
        else:  # Session crosses midnight
            if current_time.hour >= start_hour:
                session_end = (current_time + timedelta(days=1)).replace(
                    hour=end_hour, minute=0, second=0, microsecond=0
                )
            else:
                session_end = current_time.replace(
                    hour=end_hour, minute=0, second=0, microsecond=0
                )

        return session_end - current_time

    def get_session_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary by session."""
        return {
            "session_performance": dict(self.session_performance),
            "pair_session_performance": dict(self.pair_session_performance),
            "current_session": (
                self.current_session.value if self.current_session else None
            ),
            "session_intensity": self.session_intensity,
            "time_until_session_end": str(self.get_time_until_session_end()),
            "next_session_time": (
                self.next_session_time.isoformat() if self.next_session_time else None
            ),
            "optimal_pairs_current_session": (
                self.session_analyzer.get_optimal_pairs_for_session(
                    self.current_session
                )
                if self.current_session
                else []
            ),
        }
