"""
Shared Market Data Fixtures for FXML4 Tests
===========================================

Centralized market data generation and fixtures to eliminate duplication
across the test suite. Provides realistic, configurable data for:

1. OHLCV data generation with realistic price movements
2. Tick-by-tick data with proper spread and volume
3. Multi-timeframe data aggregation
4. Economic indicators and sentiment data
5. Historical pattern templates
6. Real-time streaming simulation
7. Error scenario generation

This consolidation addresses the medium-priority task M1 from our action plan.
"""

import asyncio
import json
import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import pytest
from faker import Faker

# Initialize with fixed seed for reproducible tests
fake = Faker()
fake.seed_instance(42)
np.random.seed(42)


class MarketRegime(Enum):
    """Market regime classifications."""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    QUIET = "quiet"


class SessionType(Enum):
    """Trading session types."""

    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP_LONDON_NY = "overlap_london_ny"


class MarketDataGenerator:
    """
    Advanced market data generator with realistic price dynamics,
    session effects, and regime-dependent behavior.
    """

    # Currency pair specifications
    CURRENCY_SPECS = {
        "EURUSD": {"base_price": 1.1000, "pip_value": 0.0001, "spread": 0.00015},
        "GBPUSD": {"base_price": 1.3000, "pip_value": 0.0001, "spread": 0.00020},
        "USDJPY": {"base_price": 110.00, "pip_value": 0.01, "spread": 0.015},
        "AUDUSD": {"base_price": 0.7500, "pip_value": 0.0001, "spread": 0.00018},
        "USDCAD": {"base_price": 1.2500, "pip_value": 0.0001, "spread": 0.00017},
        "NZDUSD": {"base_price": 0.6800, "pip_value": 0.0001, "spread": 0.00022},
        "USDCHF": {"base_price": 0.9200, "pip_value": 0.0001, "spread": 0.00016},
        "EURJPY": {"base_price": 121.00, "pip_value": 0.01, "spread": 0.018},
        "GBPJPY": {"base_price": 143.00, "pip_value": 0.01, "spread": 0.025},
        "AUDJPY": {"base_price": 82.50, "pip_value": 0.01, "spread": 0.020},
    }

    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

    def generate_ohlcv_data(
        self,
        symbol: str = "EURUSD",
        start_date: Union[str, datetime] = "2024-01-01",
        periods: int = 1000,
        timeframe: str = "1H",
        regime: MarketRegime = MarketRegime.SIDEWAYS,
        volatility_factor: float = 1.0,
        trend_strength: float = 0.0,
        session_effects: bool = True,
        include_gaps: bool = False,
    ) -> pd.DataFrame:
        """
        Generate comprehensive OHLCV data with realistic market dynamics.

        Args:
            symbol: Currency pair symbol
            start_date: Start date for data generation
            periods: Number of periods to generate
            timeframe: Time interval (1M, 5M, 15M, 1H, 4H, 1D)
            regime: Market regime affecting price behavior
            volatility_factor: Multiplier for base volatility
            trend_strength: Trend strength (-1 to 1, 0 is sideways)
            session_effects: Whether to include trading session effects
            include_gaps: Whether to include weekend/holiday gaps
        """

        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)

        # Get currency specifications
        spec = self.CURRENCY_SPECS.get(symbol, self.CURRENCY_SPECS["EURUSD"])
        base_price = spec["base_price"]
        pip_value = spec["pip_value"]

        # Generate time series
        freq_map = {
            "1M": "1min",
            "5M": "5min",
            "15M": "15min",
            "30M": "30min",
            "1H": "1H",
            "4H": "4H",
            "1D": "1D",
            "1W": "1W",
        }
        freq = freq_map.get(timeframe, "1H")

        dates = pd.date_range(start=start_date, periods=periods, freq=freq)

        # Regime-dependent parameters
        regime_params = self._get_regime_parameters(regime, volatility_factor)
        base_volatility = regime_params["volatility"]
        mean_reversion = regime_params["mean_reversion"]
        jump_probability = regime_params["jump_probability"]

        # Generate price series
        prices = self._generate_price_series(
            periods=periods,
            base_price=base_price,
            volatility=base_volatility,
            trend_strength=trend_strength,
            mean_reversion=mean_reversion,
            jump_probability=jump_probability,
        )

        # Apply session effects
        if session_effects:
            prices = self._apply_session_effects(prices, dates)

        # Generate OHLCV from price series
        data = []
        for i, (timestamp, price) in enumerate(zip(dates, prices)):
            ohlcv = self._generate_ohlcv_bar(
                timestamp=timestamp,
                price=price,
                prev_price=prices[i - 1] if i > 0 else price,
                volatility=base_volatility,
                pip_value=pip_value,
                include_gap=include_gaps and self._is_gap_period(timestamp),
            )
            ohlcv["symbol"] = symbol
            data.append(ohlcv)

        df = pd.DataFrame(data)

        # Ensure OHLC relationships are valid
        df = self._validate_ohlc_relationships(df)

        return df

    def generate_tick_data(
        self,
        symbol: str = "EURUSD",
        start_time: Optional[datetime] = None,
        duration_minutes: int = 60,
        avg_ticks_per_minute: int = 20,
        regime: MarketRegime = MarketRegime.SIDEWAYS,
        session: SessionType = SessionType.LONDON,
    ) -> List[Dict[str, Any]]:
        """
        Generate realistic tick-by-tick data with proper bid/ask spreads.
        """
        if start_time is None:
            start_time = datetime.now(timezone.utc)

        spec = self.CURRENCY_SPECS.get(symbol, self.CURRENCY_SPECS["EURUSD"])
        base_price = spec["base_price"]
        base_spread = spec["spread"]

        # Session-dependent adjustments
        session_multiplier = self._get_session_multiplier(session)
        tick_frequency = int(avg_ticks_per_minute * session_multiplier)
        spread_multiplier = (
            1.0 / session_multiplier
        )  # Tighter spreads in active sessions

        total_ticks = duration_minutes * tick_frequency
        ticks = []

        current_price = base_price
        current_time = start_time

        for i in range(total_ticks):
            # Time increment (irregular intervals)
            interval_ms = np.random.exponential(60000 / tick_frequency)
            current_time += timedelta(milliseconds=interval_ms)

            # Price movement
            price_change = self._generate_tick_price_change(regime, spec["pip_value"])
            current_price += price_change

            # Bid/Ask spread
            spread = base_spread * spread_multiplier * np.random.uniform(0.8, 1.2)
            mid_price = current_price
            bid = mid_price - spread / 2
            ask = mid_price + spread / 2

            # Volume (size)
            bid_size = self._generate_tick_volume(session)
            ask_size = self._generate_tick_volume(session)

            tick = {
                "symbol": symbol,
                "timestamp": current_time,
                "bid": round(bid, 5),
                "ask": round(ask, 5),
                "bid_size": bid_size,
                "ask_size": ask_size,
                "spread": round(ask - bid, 5),
                "mid": round(mid_price, 5),
            }

            ticks.append(tick)

        return ticks

    def generate_multi_timeframe_data(
        self,
        symbol: str = "EURUSD",
        base_timeframe: str = "1M",
        target_timeframes: List[str] = ["5M", "15M", "1H", "4H"],
        periods: int = 1440,  # 24 hours of 1M data
        **kwargs,
    ) -> Dict[str, pd.DataFrame]:
        """
        Generate multi-timeframe data with proper aggregation relationships.
        """
        # Generate base timeframe data
        base_data = self.generate_ohlcv_data(
            symbol=symbol, timeframe=base_timeframe, periods=periods, **kwargs
        )

        result = {base_timeframe: base_data}

        # Aggregate to higher timeframes
        for tf in target_timeframes:
            aggregated = self._aggregate_timeframe(base_data, base_timeframe, tf)
            result[tf] = aggregated

        return result

    def generate_economic_indicators(
        self,
        start_date: Union[str, datetime] = "2024-01-01",
        periods: int = 252,  # Trading days in a year
    ) -> pd.DataFrame:
        """
        Generate economic indicators that affect currency movements.
        """
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)

        dates = pd.date_range(
            start=start_date, periods=periods, freq="B"
        )  # Business days

        indicators = []

        for date in dates:
            # Interest rates (random walk with bounds)
            us_rate = max(0, min(10, 2.5 + np.random.normal(0, 0.01)))
            eu_rate = max(0, min(10, 1.8 + np.random.normal(0, 0.008)))
            uk_rate = max(0, min(10, 3.2 + np.random.normal(0, 0.012)))

            # Economic indicators
            gdp_us = np.random.normal(2.1, 0.3)
            gdp_eu = np.random.normal(1.5, 0.4)
            inflation_us = np.random.normal(2.8, 0.2)
            inflation_eu = np.random.normal(2.0, 0.3)
            unemployment_us = np.random.normal(3.8, 0.1)
            unemployment_eu = np.random.normal(6.2, 0.2)

            # Market sentiment indicators
            vix = max(10, min(80, 18.5 + np.random.normal(0, 2)))
            dollar_index = 95 + np.random.normal(0, 0.5)

            indicators.append(
                {
                    "date": date,
                    "us_interest_rate": us_rate,
                    "eu_interest_rate": eu_rate,
                    "uk_interest_rate": uk_rate,
                    "us_gdp_growth": gdp_us,
                    "eu_gdp_growth": gdp_eu,
                    "us_inflation": inflation_us,
                    "eu_inflation": inflation_eu,
                    "us_unemployment": unemployment_us,
                    "eu_unemployment": unemployment_eu,
                    "vix": vix,
                    "dollar_index": dollar_index,
                }
            )

        return pd.DataFrame(indicators)

    def generate_pattern_templates(self) -> Dict[str, pd.DataFrame]:
        """
        Generate common chart patterns for pattern recognition testing.
        """
        patterns = {}

        # Head and Shoulders
        patterns["head_shoulders"] = self._generate_head_shoulders_pattern()

        # Double Top/Bottom
        patterns["double_top"] = self._generate_double_top_pattern()
        patterns["double_bottom"] = self._generate_double_bottom_pattern()

        # Triangle patterns
        patterns["ascending_triangle"] = self._generate_triangle_pattern("ascending")
        patterns["descending_triangle"] = self._generate_triangle_pattern("descending")
        patterns["symmetrical_triangle"] = self._generate_triangle_pattern(
            "symmetrical"
        )

        # Flag and Pennant
        patterns["bull_flag"] = self._generate_flag_pattern("bull")
        patterns["bear_flag"] = self._generate_flag_pattern("bear")

        return patterns

    def generate_stress_test_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """
        Generate extreme market scenarios for stress testing.
        """
        scenarios = {
            "flash_crash": {
                "description": "Sudden 5% drop in 1 minute",
                "data": self._generate_flash_crash_scenario(),
                "expected_drawdown": 0.05,
            },
            "gap_opening": {
                "description": "5% gap opening after weekend",
                "data": self._generate_gap_scenario(),
                "expected_gap": 0.05,
            },
            "high_volatility": {
                "description": "Extended period of 5x normal volatility",
                "data": self.generate_ohlcv_data(
                    periods=480,
                    timeframe="5M",
                    regime=MarketRegime.VOLATILE,
                    volatility_factor=5.0,
                ),
                "expected_volatility_increase": 5.0,
            },
            "trending_market": {
                "description": "Strong 10% trend over 1 month",
                "data": self.generate_ohlcv_data(
                    periods=720,
                    timeframe="1H",
                    regime=MarketRegime.TRENDING_UP,
                    trend_strength=0.8,
                ),
                "expected_return": 0.10,
            },
            "whipsaw_market": {
                "description": "Multiple false breakouts",
                "data": self._generate_whipsaw_scenario(),
                "expected_false_signals": 8,
            },
        }

        return scenarios

    def _get_regime_parameters(
        self, regime: MarketRegime, volatility_factor: float
    ) -> Dict:
        """Get regime-specific parameters."""
        base_params = {
            MarketRegime.TRENDING_UP: {
                "volatility": 0.0008 * volatility_factor,
                "mean_reversion": 0.02,
                "jump_probability": 0.001,
            },
            MarketRegime.TRENDING_DOWN: {
                "volatility": 0.0012 * volatility_factor,
                "mean_reversion": 0.03,
                "jump_probability": 0.002,
            },
            MarketRegime.SIDEWAYS: {
                "volatility": 0.0006 * volatility_factor,
                "mean_reversion": 0.08,
                "jump_probability": 0.0005,
            },
            MarketRegime.VOLATILE: {
                "volatility": 0.002 * volatility_factor,
                "mean_reversion": 0.01,
                "jump_probability": 0.005,
            },
            MarketRegime.QUIET: {
                "volatility": 0.0003 * volatility_factor,
                "mean_reversion": 0.1,
                "jump_probability": 0.0001,
            },
        }

        return base_params[regime]

    def _generate_price_series(
        self,
        periods: int,
        base_price: float,
        volatility: float,
        trend_strength: float,
        mean_reversion: float,
        jump_probability: float,
    ) -> np.ndarray:
        """Generate realistic price series with various market dynamics."""
        prices = np.zeros(periods)
        prices[0] = base_price

        log_prices = np.log(prices[0])

        for i in range(1, periods):
            # Trend component
            trend = trend_strength * volatility

            # Mean reversion component
            deviation = log_prices - np.log(base_price)
            mean_revert = -mean_reversion * deviation

            # Random component
            random_shock = np.random.normal(0, volatility)

            # Jump component (rare large moves)
            if np.random.random() < jump_probability:
                jump = np.random.normal(0, volatility * 5)
                random_shock += jump

            # Update log price
            log_prices += trend + mean_revert + random_shock
            prices[i] = np.exp(log_prices)

        return prices

    def _apply_session_effects(
        self, prices: np.ndarray, dates: pd.DatetimeIndex
    ) -> np.ndarray:
        """Apply trading session effects to price series."""
        modified_prices = prices.copy()

        for i, timestamp in enumerate(dates):
            hour_utc = timestamp.hour

            # Session-based volatility multipliers
            if 0 <= hour_utc < 6:  # Asian session - lower volatility
                multiplier = 0.7
            elif 8 <= hour_utc < 16:  # London session - high volatility
                multiplier = 1.2
            elif 13 <= hour_utc < 21:  # NY session - high volatility
                multiplier = 1.1
            elif 13 <= hour_utc < 16:  # London-NY overlap - highest volatility
                multiplier = 1.3
            else:  # Off-hours - lower volatility
                multiplier = 0.5

            if i > 0:
                price_change = modified_prices[i] - modified_prices[i - 1]
                modified_prices[i] = modified_prices[i - 1] + (
                    price_change * multiplier
                )

        return modified_prices

    def _generate_ohlcv_bar(
        self,
        timestamp: datetime,
        price: float,
        prev_price: float,
        volatility: float,
        pip_value: float,
        include_gap: bool = False,
    ) -> Dict[str, Any]:
        """Generate a single OHLCV bar."""
        if include_gap:
            # Create a gap
            gap_size = np.random.normal(0, volatility * 10)
            open_price = prev_price + gap_size
        else:
            # Small gap or no gap
            gap_size = np.random.normal(0, volatility * 0.1)
            open_price = prev_price + gap_size

        close_price = price

        # Generate high and low
        intrabar_range = np.random.exponential(volatility * 2)
        high_offset = np.random.uniform(0, intrabar_range)
        low_offset = np.random.uniform(0, intrabar_range)

        high = max(open_price, close_price) + high_offset
        low = min(open_price, close_price) - low_offset

        # Ensure high >= low
        if high < low:
            high, low = low, high

        # Volume (higher during active periods)
        base_volume = np.random.randint(1000, 5000)
        hour = timestamp.hour
        if 8 <= hour < 16 or 13 <= hour < 21:  # Active sessions
            volume_multiplier = np.random.uniform(1.5, 3.0)
        else:
            volume_multiplier = np.random.uniform(0.3, 0.8)

        volume = int(base_volume * volume_multiplier)

        return {
            "timestamp": timestamp,
            "open": round(open_price, 5),
            "high": round(high, 5),
            "low": round(low, 5),
            "close": round(close_price, 5),
            "volume": volume,
        }

    def _validate_ohlc_relationships(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure OHLC relationships are mathematically valid."""
        df = df.copy()

        # Ensure High >= max(Open, Close) and Low <= min(Open, Close)
        df["high"] = df[["high", "open", "close"]].max(axis=1)
        df["low"] = df[["low", "open", "close"]].min(axis=1)

        return df

    def _get_session_multiplier(self, session: SessionType) -> float:
        """Get activity multiplier for different trading sessions."""
        multipliers = {
            SessionType.ASIAN: 0.6,
            SessionType.LONDON: 1.2,
            SessionType.NEW_YORK: 1.1,
            SessionType.OVERLAP_LONDON_NY: 1.4,
        }
        return multipliers[session]

    def _generate_tick_price_change(
        self, regime: MarketRegime, pip_value: float
    ) -> float:
        """Generate realistic tick-level price changes."""
        regime_volatilities = {
            MarketRegime.QUIET: pip_value * 0.1,
            MarketRegime.SIDEWAYS: pip_value * 0.2,
            MarketRegime.TRENDING_UP: pip_value * 0.3,
            MarketRegime.TRENDING_DOWN: pip_value * 0.3,
            MarketRegime.VOLATILE: pip_value * 0.8,
        }

        volatility = regime_volatilities[regime]
        return np.random.normal(0, volatility)

    def _generate_tick_volume(self, session: SessionType) -> int:
        """Generate realistic tick volumes."""
        base_sizes = {
            SessionType.ASIAN: (100000, 500000),
            SessionType.LONDON: (500000, 2000000),
            SessionType.NEW_YORK: (300000, 1500000),
            SessionType.OVERLAP_LONDON_NY: (1000000, 5000000),
        }

        min_size, max_size = base_sizes[session]
        return np.random.randint(min_size, max_size)

    def _is_gap_period(self, timestamp: datetime) -> bool:
        """Check if timestamp represents a potential gap period."""
        # Weekend gaps
        if timestamp.weekday() == 6:  # Sunday
            return True

        # Holiday gaps (simplified)
        if timestamp.month == 12 and timestamp.day in [25, 26]:
            return True
        if timestamp.month == 1 and timestamp.day == 1:
            return True

        return False

    def _aggregate_timeframe(
        self, base_data: pd.DataFrame, base_tf: str, target_tf: str
    ) -> pd.DataFrame:
        """Aggregate data from base timeframe to target timeframe."""
        # Set timestamp as index for resampling
        df = base_data.set_index("timestamp")

        # Resample rules
        resample_rules = {
            "5M": "5min",
            "15M": "15min",
            "30M": "30min",
            "1H": "1H",
            "4H": "4H",
            "1D": "1D",
            "1W": "1W",
        }

        rule = resample_rules.get(target_tf, "1H")

        # Aggregate OHLCV data
        aggregated = (
            df.groupby("symbol")
            .resample(rule)
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
        )

        # Reset index
        aggregated = aggregated.reset_index()

        return aggregated

    # Pattern generation methods
    def _generate_head_shoulders_pattern(self) -> pd.DataFrame:
        """Generate Head and Shoulders pattern."""
        # Simplified pattern generation
        periods = 100
        base_price = 1.1000

        # Create the pattern shape
        left_shoulder = np.linspace(0, 0.02, 20)
        head_up = np.linspace(0.02, 0.04, 15)
        head_down = np.linspace(0.04, 0.01, 15)
        right_shoulder_up = np.linspace(0.01, 0.025, 15)
        right_shoulder_down = np.linspace(0.025, -0.01, 20)
        breakdown = np.linspace(-0.01, -0.03, 15)

        pattern = np.concatenate(
            [
                left_shoulder,
                head_up,
                head_down,
                right_shoulder_up,
                right_shoulder_down,
                breakdown,
            ]
        )

        # Add noise
        noise = np.random.normal(0, 0.002, len(pattern))
        prices = base_price + pattern + noise

        # Generate timestamps
        dates = pd.date_range(start="2024-01-01", periods=len(prices), freq="1H")

        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            prev_price = prices[i - 1] if i > 0 else price
            bar = self._generate_ohlcv_bar(date, price, prev_price, 0.0005, 0.0001)
            bar["symbol"] = "EURUSD"
            data.append(bar)

        return pd.DataFrame(data)

    def _generate_double_top_pattern(self) -> pd.DataFrame:
        """Generate Double Top pattern."""
        # Similar to head and shoulders but with two equal peaks
        periods = 80
        base_price = 1.1000

        # Pattern shape
        first_peak = np.concatenate(
            [np.linspace(0, 0.03, 15), np.linspace(0.03, 0.01, 15)]
        )
        valley = np.linspace(0.01, 0.005, 10)
        second_peak = np.concatenate(
            [np.linspace(0.005, 0.03, 15), np.linspace(0.03, -0.02, 25)]
        )

        pattern = np.concatenate([first_peak, valley, second_peak])
        noise = np.random.normal(0, 0.001, len(pattern))
        prices = base_price + pattern + noise

        dates = pd.date_range(start="2024-01-01", periods=len(prices), freq="1H")

        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            prev_price = prices[i - 1] if i > 0 else price
            bar = self._generate_ohlcv_bar(date, price, prev_price, 0.0005, 0.0001)
            bar["symbol"] = "EURUSD"
            data.append(bar)

        return pd.DataFrame(data)

    def _generate_double_bottom_pattern(self) -> pd.DataFrame:
        """Generate Double Bottom pattern."""
        # Inverted double top
        double_top_data = self._generate_double_top_pattern()

        # Invert the pattern
        base_price = double_top_data["close"].iloc[0]
        double_top_data["open"] = 2 * base_price - double_top_data["open"]
        double_top_data["high"] = 2 * base_price - double_top_data["high"]
        double_top_data["low"] = 2 * base_price - double_top_data["low"]
        double_top_data["close"] = 2 * base_price - double_top_data["close"]

        # Swap high and low
        high_values = double_top_data["high"].copy()
        double_top_data["high"] = double_top_data["low"]
        double_top_data["low"] = high_values

        return double_top_data

    def _generate_triangle_pattern(self, triangle_type: str) -> pd.DataFrame:
        """Generate triangle patterns."""
        periods = 60
        base_price = 1.1000

        if triangle_type == "ascending":
            # Flat resistance, rising support
            resistance = np.full(periods, 0.02)
            support = np.linspace(-0.01, 0.015, periods)
        elif triangle_type == "descending":
            # Falling resistance, flat support
            resistance = np.linspace(0.02, 0.005, periods)
            support = np.full(periods, -0.01)
        else:  # symmetrical
            # Converging resistance and support
            resistance = np.linspace(0.02, 0.005, periods)
            support = np.linspace(-0.01, 0.002, periods)

        # Generate prices within the triangle
        prices = []
        for i in range(periods):
            # Alternate between testing support and resistance
            if i % 8 < 4:  # Test resistance
                target = base_price + resistance[i] - np.random.uniform(0.002, 0.008)
            else:  # Test support
                target = base_price + support[i] + np.random.uniform(0.002, 0.008)

            prices.append(target)

        # Add breakout
        breakout_direction = 1 if triangle_type == "ascending" else -1
        for i in range(10):
            breakout_move = breakout_direction * 0.002 * (i + 1)
            prices.append(prices[-1] + breakout_move)

        dates = pd.date_range(start="2024-01-01", periods=len(prices), freq="1H")

        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            prev_price = prices[i - 1] if i > 0 else price
            bar = self._generate_ohlcv_bar(date, price, prev_price, 0.0005, 0.0001)
            bar["symbol"] = "EURUSD"
            data.append(bar)

        return pd.DataFrame(data)

    def _generate_flag_pattern(self, flag_type: str) -> pd.DataFrame:
        """Generate flag patterns."""
        # Strong move followed by consolidation
        periods = 50
        base_price = 1.1000

        # Initial strong move
        direction = 1 if flag_type == "bull" else -1
        strong_move = np.linspace(0, direction * 0.03, 15)

        # Flag consolidation (slight retracement)
        flag_slope = -direction * 0.001
        consolidation = (
            base_price + strong_move[-1] + np.linspace(0, flag_slope * 20, 20)
        )

        # Breakout continuation
        continuation = np.linspace(0, direction * 0.02, 15)

        # Combine
        move_prices = base_price + strong_move
        flag_prices = consolidation
        breakout_prices = flag_prices[-1] + continuation

        all_prices = np.concatenate([move_prices, flag_prices, breakout_prices])

        # Add noise
        noise = np.random.normal(0, 0.0005, len(all_prices))
        prices = all_prices + noise

        dates = pd.date_range(start="2024-01-01", periods=len(prices), freq="1H")

        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            prev_price = prices[i - 1] if i > 0 else price
            bar = self._generate_ohlcv_bar(date, price, prev_price, 0.0005, 0.0001)
            bar["symbol"] = "EURUSD"
            data.append(bar)

        return pd.DataFrame(data)

    def _generate_flash_crash_scenario(self) -> pd.DataFrame:
        """Generate flash crash scenario."""
        # Normal trading followed by sudden crash and recovery
        normal_periods = 100
        crash_periods = 5
        recovery_periods = 20

        # Normal trading
        normal_data = self.generate_ohlcv_data(
            periods=normal_periods,
            timeframe="1M",
            regime=MarketRegime.QUIET,
        )

        # Flash crash
        crash_price = normal_data["close"].iloc[-1]
        crash_low = crash_price * 0.95  # 5% drop

        crash_data = []
        for i in range(crash_periods):
            timestamp = normal_data["timestamp"].iloc[-1] + timedelta(minutes=i + 1)

            if i == 0:
                # Initial crash bar
                bar = {
                    "timestamp": timestamp,
                    "symbol": "EURUSD",
                    "open": crash_price,
                    "high": crash_price,
                    "low": crash_low,
                    "close": crash_low * 1.01,  # Small bounce
                    "volume": 50000,  # High volume
                }
            else:
                # Recovery bars
                recovery_factor = i / crash_periods
                current_price = (
                    crash_low + (crash_price - crash_low) * recovery_factor * 0.8
                )

                bar = {
                    "timestamp": timestamp,
                    "symbol": "EURUSD",
                    "open": crash_data[i - 1]["close"],
                    "high": current_price * 1.002,
                    "low": crash_data[i - 1]["close"] * 0.999,
                    "close": current_price,
                    "volume": 30000 - i * 5000,  # Decreasing volume
                }

            crash_data.append(bar)

        # Combine all data
        all_data = pd.concat([normal_data, pd.DataFrame(crash_data)], ignore_index=True)

        return all_data

    def _generate_gap_scenario(self) -> pd.DataFrame:
        """Generate weekend gap scenario."""
        # Friday data
        friday_data = self.generate_ohlcv_data(
            periods=50,
            timeframe="1H",
            start_date="2024-01-05",  # Friday
        )

        # Gap opening on Sunday
        friday_close = friday_data["close"].iloc[-1]
        gap_size = friday_close * 0.05  # 5% gap

        sunday_open = friday_close + gap_size

        # Sunday data with gap
        sunday_data = self.generate_ohlcv_data(
            periods=24,
            timeframe="1H",
            start_date="2024-01-07",  # Sunday
        )

        # Adjust Sunday data to start with gap
        price_adjustment = sunday_open - sunday_data["open"].iloc[0]
        sunday_data["open"] += price_adjustment
        sunday_data["high"] += price_adjustment
        sunday_data["low"] += price_adjustment
        sunday_data["close"] += price_adjustment

        # Combine
        gap_data = pd.concat([friday_data, sunday_data], ignore_index=True)

        return gap_data

    def _generate_whipsaw_scenario(self) -> pd.DataFrame:
        """Generate whipsaw scenario with multiple false breakouts."""
        base_data = self.generate_ohlcv_data(
            periods=200,
            timeframe="5M",
            regime=MarketRegime.SIDEWAYS,
        )

        # Add false breakouts every 25 periods
        whipsaw_data = base_data.copy()

        for i in range(8):  # 8 false breakouts
            start_idx = 25 * i
            if start_idx >= len(whipsaw_data):
                break

            # Create false breakout
            base_price = whipsaw_data["close"].iloc[start_idx]

            # Breakout direction (alternating)
            direction = 1 if i % 2 == 0 else -1

            # False breakout (3-5 bars)
            for j in range(1, 4):
                idx = start_idx + j
                if idx >= len(whipsaw_data):
                    break

                if j == 1:  # Breakout bar
                    breakout_move = direction * 0.008
                    whipsaw_data.loc[idx, "close"] = base_price + breakout_move
                    whipsaw_data.loc[idx, "high"] = max(
                        whipsaw_data.loc[idx, "high"], whipsaw_data.loc[idx, "close"]
                    )
                    whipsaw_data.loc[idx, "low"] = min(
                        whipsaw_data.loc[idx, "low"], whipsaw_data.loc[idx, "close"]
                    )
                else:  # Reversal
                    reversal_move = -direction * 0.012  # Stronger reversal
                    whipsaw_data.loc[idx, "close"] = base_price + reversal_move
                    whipsaw_data.loc[idx, "high"] = max(
                        whipsaw_data.loc[idx, "high"], whipsaw_data.loc[idx, "close"]
                    )
                    whipsaw_data.loc[idx, "low"] = min(
                        whipsaw_data.loc[idx, "low"], whipsaw_data.loc[idx, "close"]
                    )

        return whipsaw_data


# ============================================================================
# Pytest Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def market_data_generator():
    """Provides a market data generator instance."""
    return MarketDataGenerator(seed=42)


@pytest.fixture
def sample_ohlcv_data(market_data_generator):
    """Provides sample OHLCV data for testing."""
    return market_data_generator.generate_ohlcv_data(
        symbol="EURUSD",
        periods=100,
        timeframe="1H",
        regime=MarketRegime.SIDEWAYS,
    )


@pytest.fixture
def sample_tick_data(market_data_generator):
    """Provides sample tick data for testing."""
    return market_data_generator.generate_tick_data(
        symbol="EURUSD",
        duration_minutes=60,
        session=SessionType.LONDON,
    )


@pytest.fixture
def multi_timeframe_data(market_data_generator):
    """Provides multi-timeframe data for testing."""
    return market_data_generator.generate_multi_timeframe_data(
        symbol="EURUSD",
        periods=480,  # 8 hours of 1M data
        target_timeframes=["5M", "15M", "1H"],
    )


@pytest.fixture
def economic_indicators(market_data_generator):
    """Provides economic indicators data for testing."""
    return market_data_generator.generate_economic_indicators(periods=30)


@pytest.fixture
def chart_patterns(market_data_generator):
    """Provides chart patterns for testing."""
    return market_data_generator.generate_pattern_templates()


@pytest.fixture
def stress_scenarios(market_data_generator):
    """Provides stress test scenarios for testing."""
    return market_data_generator.generate_stress_test_scenarios()


@pytest.fixture(params=["EURUSD", "GBPUSD", "USDJPY"])
def major_currency_pair(request):
    """Parametrized fixture for testing with major currency pairs."""
    return request.param


@pytest.fixture(params=["1M", "5M", "15M", "1H", "4H"])
def common_timeframe(request):
    """Parametrized fixture for testing with common timeframes."""
    return request.param


@pytest.fixture(
    params=[
        MarketRegime.TRENDING_UP,
        MarketRegime.TRENDING_DOWN,
        MarketRegime.SIDEWAYS,
        MarketRegime.VOLATILE,
    ]
)
def market_regime(request):
    """Parametrized fixture for testing different market regimes."""
    return request.param


# ============================================================================
# Utility Functions
# ============================================================================


def create_custom_market_data(symbol: str, scenario: str, **kwargs) -> pd.DataFrame:
    """
    Convenience function to create custom market data for specific test scenarios.

    Args:
        symbol: Currency pair symbol
        scenario: Predefined scenario name
        **kwargs: Additional parameters for the generator

    Returns:
        Generated market data as DataFrame
    """
    generator = MarketDataGenerator()

    scenario_configs = {
        "quiet_market": {
            "regime": MarketRegime.QUIET,
            "periods": 100,
            "volatility_factor": 0.5,
        },
        "trending_bull": {
            "regime": MarketRegime.TRENDING_UP,
            "periods": 200,
            "trend_strength": 0.6,
        },
        "trending_bear": {
            "regime": MarketRegime.TRENDING_DOWN,
            "periods": 200,
            "trend_strength": -0.6,
        },
        "high_volatility": {
            "regime": MarketRegime.VOLATILE,
            "periods": 150,
            "volatility_factor": 3.0,
        },
        "consolidation": {
            "regime": MarketRegime.SIDEWAYS,
            "periods": 300,
            "trend_strength": 0.0,
        },
    }

    config = scenario_configs.get(scenario, {})
    config.update(kwargs)

    return generator.generate_ohlcv_data(symbol=symbol, **config)


def validate_market_data_integrity(data: pd.DataFrame) -> Dict[str, bool]:
    """
    Validate the integrity of market data.

    Returns:
        Dictionary of validation results
    """
    validations = {}

    # Check required columns
    required_columns = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
    validations["has_required_columns"] = all(
        col in data.columns for col in required_columns
    )

    # Check OHLC relationships
    validations["valid_ohlc_relationships"] = (
        data["high"] >= data[["open", "close"]].max(axis=1)
    ).all() and (data["low"] <= data[["open", "close"]].min(axis=1)).all()

    # Check for missing data
    validations["no_missing_data"] = not data[required_columns].isnull().any().any()

    # Check for negative prices
    price_columns = ["open", "high", "low", "close"]
    validations["positive_prices"] = (data[price_columns] > 0).all().all()

    # Check for negative volumes
    validations["positive_volumes"] = (data["volume"] >= 0).all()

    # Check timestamp ordering
    validations["ordered_timestamps"] = data["timestamp"].is_monotonic_increasing

    return validations


# Export key components for easy importing
__all__ = [
    "MarketDataGenerator",
    "MarketRegime",
    "SessionType",
    "market_data_generator",
    "sample_ohlcv_data",
    "sample_tick_data",
    "multi_timeframe_data",
    "economic_indicators",
    "chart_patterns",
    "stress_scenarios",
    "major_currency_pair",
    "common_timeframe",
    "market_regime",
    "create_custom_market_data",
    "validate_market_data_integrity",
]
