#!/usr/bin/env python3
"""
Advanced Test Data Factories for Complex Scenarios

This module provides advanced factory classes for generating complex
test scenarios including ML features, backtesting data, and risk scenarios.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from .simple_data_factories import (
    AccountFactory,
    MarketDataFactory,
    OrderFactory,
    OrderSide,
    PositionFactory,
    SignalFactory,
    SignalStrength,
)


@dataclass
class MLFeatures:
    """Machine learning features for trading models."""

    timestamp: datetime
    symbol: str

    # Price features
    returns_1h: float
    returns_4h: float
    returns_1d: float
    log_returns: float
    volatility: float

    # Technical indicators
    rsi: float
    macd: float
    macd_signal: float
    ema_12: float
    ema_26: float
    ema_50: float
    ema_200: float
    bollinger_upper: float
    bollinger_lower: float
    atr: float
    adx: float

    # Market microstructure
    spread: float
    volume: int
    bid_ask_imbalance: float

    # Time features
    hour_of_day: int
    day_of_week: int
    is_london_session: bool
    is_ny_session: bool
    is_tokyo_session: bool

    # Sentiment features
    sentiment_score: float
    news_count: int

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestScenario:
    """Complete backtesting scenario."""

    name: str
    description: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    symbols: List[str]
    market_data: Dict[str, List[Any]]
    signals: Dict[str, List[Any]]
    risk_parameters: Dict[str, float]
    expected_metrics: Dict[str, float]


@dataclass
class RiskScenario:
    """Risk management test scenario."""

    scenario_id: str
    name: str
    description: str
    market_condition: str
    volatility_multiplier: float
    drawdown_threshold: float
    positions: List[Any]
    risk_events: List[Dict[str, Any]]
    expected_actions: List[str]


class MLFeatureFactory:
    """Factory for generating ML features."""

    @classmethod
    def create(cls, symbol: str = "EURUSD", **kwargs) -> MLFeatures:
        """Create ML features for a single point in time."""
        timestamp = kwargs.get("timestamp", datetime.now())

        # Generate correlated price features
        base_return = np.random.normal(0, 0.001)

        returns_1h = kwargs.get("returns_1h", base_return + np.random.normal(0, 0.0002))
        returns_4h = kwargs.get(
            "returns_4h", base_return * 4 + np.random.normal(0, 0.0005)
        )
        returns_1d = kwargs.get(
            "returns_1d", base_return * 24 + np.random.normal(0, 0.001)
        )
        log_returns = np.log(1 + returns_1h)
        volatility = kwargs.get("volatility", abs(np.random.normal(0.001, 0.0003)))

        # Technical indicators with realistic ranges
        rsi = kwargs.get("rsi", np.clip(50 + np.random.normal(0, 20), 0, 100))
        macd = kwargs.get("macd", np.random.normal(0, 0.0005))
        macd_signal = kwargs.get(
            "macd_signal", macd * 0.8 + np.random.normal(0, 0.0001)
        )

        # EMAs with realistic relationships
        base_price = 1.1000
        ema_12 = kwargs.get("ema_12", base_price + np.random.normal(0, 0.001))
        ema_26 = kwargs.get("ema_26", base_price + np.random.normal(0, 0.0015))
        ema_50 = kwargs.get("ema_50", base_price + np.random.normal(0, 0.002))
        ema_200 = kwargs.get("ema_200", base_price + np.random.normal(0, 0.003))

        # Bollinger Bands
        std_dev = volatility * base_price
        bollinger_upper = kwargs.get("bollinger_upper", base_price + 2 * std_dev)
        bollinger_lower = kwargs.get("bollinger_lower", base_price - 2 * std_dev)

        # Other indicators
        atr = kwargs.get("atr", abs(np.random.normal(0.001, 0.0003)))
        adx = kwargs.get("adx", np.clip(25 + np.random.normal(0, 15), 0, 100))

        # Market microstructure
        spread = kwargs.get("spread", abs(np.random.normal(0.00015, 0.00005)))
        volume = kwargs.get("volume", int(abs(np.random.normal(100000, 50000))))
        bid_ask_imbalance = kwargs.get("bid_ask_imbalance", np.random.uniform(-1, 1))

        # Time features
        hour_of_day = timestamp.hour
        day_of_week = timestamp.weekday()

        # Trading session detection
        is_london_session = 8 <= hour_of_day < 16
        is_ny_session = 13 <= hour_of_day < 21
        is_tokyo_session = hour_of_day < 8 or hour_of_day >= 23

        # Sentiment features
        sentiment_score = kwargs.get("sentiment_score", np.random.uniform(-1, 1))
        news_count = kwargs.get("news_count", np.random.poisson(2))

        return MLFeatures(
            timestamp=timestamp,
            symbol=symbol,
            returns_1h=returns_1h,
            returns_4h=returns_4h,
            returns_1d=returns_1d,
            log_returns=log_returns,
            volatility=volatility,
            rsi=rsi,
            macd=macd,
            macd_signal=macd_signal,
            ema_12=ema_12,
            ema_26=ema_26,
            ema_50=ema_50,
            ema_200=ema_200,
            bollinger_upper=bollinger_upper,
            bollinger_lower=bollinger_lower,
            atr=atr,
            adx=adx,
            spread=spread,
            volume=volume,
            bid_ask_imbalance=bid_ask_imbalance,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            is_london_session=is_london_session,
            is_ny_session=is_ny_session,
            is_tokyo_session=is_tokyo_session,
            sentiment_score=sentiment_score,
            news_count=news_count,
            metadata=kwargs.get("metadata", {}),
        )

    @classmethod
    def create_feature_matrix(
        cls, periods: int = 100, symbol: str = "EURUSD"
    ) -> np.ndarray:
        """Create a feature matrix for ML model training."""
        features = []
        start_time = datetime.now() - timedelta(hours=periods)

        for i in range(periods):
            timestamp = start_time + timedelta(hours=i)
            feature_set = cls.create(symbol=symbol, timestamp=timestamp)

            # Convert to feature vector
            feature_vector = [
                feature_set.returns_1h,
                feature_set.returns_4h,
                feature_set.returns_1d,
                feature_set.volatility,
                feature_set.rsi / 100,  # Normalize
                feature_set.macd,
                feature_set.atr,
                feature_set.adx / 100,  # Normalize
                feature_set.spread,
                feature_set.bid_ask_imbalance,
                feature_set.hour_of_day / 24,  # Normalize
                feature_set.day_of_week / 7,  # Normalize
                int(feature_set.is_london_session),
                int(feature_set.is_ny_session),
                int(feature_set.is_tokyo_session),
                feature_set.sentiment_score,
                min(feature_set.news_count / 10, 1),  # Normalize and cap
            ]

            features.append(feature_vector)

        return np.array(features)

    @classmethod
    def create_labeled_dataset(
        cls, periods: int = 1000
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Create labeled dataset for supervised learning."""
        X = cls.create_feature_matrix(periods)

        # Generate labels based on features (simplified logic)
        y = []
        for features in X:
            # Use multiple features to determine label
            signal_strength = (
                features[4] * 0.3  # RSI
                + features[5] * 100  # MACD
                + features[15] * 0.2  # Sentiment
            )

            if signal_strength > 0.1:
                y.append(1)  # Buy
            elif signal_strength < -0.1:
                y.append(-1)  # Sell
            else:
                y.append(0)  # Hold

        return X, np.array(y)


class BacktestFactory:
    """Factory for generating backtesting scenarios."""

    @classmethod
    def create_trending_scenario(cls, trend: str = "bullish") -> BacktestScenario:
        """Create a trending market scenario."""
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        # Generate trending market data
        market_factory = MarketDataFactory()
        market_data = {}
        signals = {}

        for symbol in ["EURUSD", "GBPUSD"]:
            if trend == "bullish":
                market_data[symbol] = market_factory.create_trending_market(
                    symbol, periods=720, trend="up"  # 30 days of hourly data
                )
                # Generate buy-biased signals
                signal_factory = SignalFactory()
                signals[symbol] = [
                    signal_factory.create_buy_signal(symbol=symbol) for _ in range(20)
                ]
            else:
                market_data[symbol] = market_factory.create_trending_market(
                    symbol, periods=720, trend="down"
                )
                # Generate sell-biased signals
                signal_factory = SignalFactory()
                signals[symbol] = [
                    signal_factory.create_sell_signal(symbol=symbol) for _ in range(20)
                ]

        return BacktestScenario(
            name=f"{trend.capitalize()} Trend Scenario",
            description=f"A {trend} trending market over 30 days",
            start_date=start_date,
            end_date=end_date,
            initial_balance=50000,
            symbols=["EURUSD", "GBPUSD"],
            market_data=market_data,
            signals=signals,
            risk_parameters={
                "max_position_size": 100000,
                "max_risk_per_trade": 0.02,
                "max_daily_drawdown": 0.05,
                "stop_loss_pips": 50,
                "take_profit_pips": 100,
            },
            expected_metrics={
                "total_trades": 40,
                "win_rate": 0.65 if trend == "bullish" else 0.35,
                "sharpe_ratio": 1.5 if trend == "bullish" else -0.5,
                "max_drawdown": 0.10,
                "profit_factor": 2.0 if trend == "bullish" else 0.5,
            },
        )

    @classmethod
    def create_volatile_scenario(cls) -> BacktestScenario:
        """Create a volatile market scenario."""
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        market_factory = MarketDataFactory()
        signal_factory = SignalFactory()

        market_data = {}
        signals = {}

        # High volatility market data
        for symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
            data_points = []
            base_price = 1.1000 if symbol == "EURUSD" else 1.2500

            for i in range(168):  # 7 days of hourly data
                # Add high volatility
                volatility = 0.005  # 5x normal volatility
                price = base_price + np.random.normal(0, volatility)

                data_points.append(
                    market_factory.create(
                        symbol=symbol,
                        timestamp=start_date + timedelta(hours=i),
                        mid=price,
                    )
                )

            market_data[symbol] = data_points

            # Mixed signals due to volatility
            signals[symbol] = []
            for _ in range(10):
                if random.random() > 0.5:
                    signals[symbol].append(
                        signal_factory.create_buy_signal(symbol=symbol)
                    )
                else:
                    signals[symbol].append(
                        signal_factory.create_sell_signal(symbol=symbol)
                    )

        return BacktestScenario(
            name="High Volatility Scenario",
            description="Volatile market conditions over 7 days",
            start_date=start_date,
            end_date=end_date,
            initial_balance=100000,
            symbols=["EURUSD", "GBPUSD", "USDJPY"],
            market_data=market_data,
            signals=signals,
            risk_parameters={
                "max_position_size": 50000,  # Reduced due to volatility
                "max_risk_per_trade": 0.01,  # Reduced risk
                "max_daily_drawdown": 0.03,
                "stop_loss_pips": 100,  # Wider stops
                "take_profit_pips": 150,
            },
            expected_metrics={
                "total_trades": 30,
                "win_rate": 0.45,
                "sharpe_ratio": 0.5,
                "max_drawdown": 0.20,
                "profit_factor": 1.1,
            },
        )

    @classmethod
    def create_flash_crash_scenario(cls) -> BacktestScenario:
        """Create a flash crash scenario for stress testing."""
        start_date = datetime.now() - timedelta(hours=24)
        end_date = datetime.now()

        market_factory = MarketDataFactory()
        market_data = {"EURUSD": []}

        base_price = 1.1000

        # Normal market for first 20 hours
        for i in range(20):
            market_data["EURUSD"].append(
                market_factory.create(
                    symbol="EURUSD",
                    timestamp=start_date + timedelta(hours=i),
                    mid=base_price + np.random.normal(0, 0.0005),
                )
            )

        # Flash crash at hour 20-21
        crash_magnitude = 0.05  # 5% crash
        for i in range(20, 22):
            progress = (i - 20) / 2
            crash_price = base_price * (1 - crash_magnitude * progress)
            market_data["EURUSD"].append(
                market_factory.create(
                    symbol="EURUSD",
                    timestamp=start_date + timedelta(hours=i),
                    mid=crash_price,
                    spread=0.001,  # Widened spread during crash
                )
            )

        # Recovery
        for i in range(22, 24):
            recovery_price = base_price * (
                1 - crash_magnitude * 0.5
            )  # Partial recovery
            market_data["EURUSD"].append(
                market_factory.create(
                    symbol="EURUSD",
                    timestamp=start_date + timedelta(hours=i),
                    mid=recovery_price,
                )
            )

        return BacktestScenario(
            name="Flash Crash Scenario",
            description="Sudden market crash and partial recovery",
            start_date=start_date,
            end_date=end_date,
            initial_balance=50000,
            symbols=["EURUSD"],
            market_data=market_data,
            signals={},  # No signals during crash
            risk_parameters={
                "max_position_size": 100000,
                "max_risk_per_trade": 0.02,
                "max_daily_drawdown": 0.10,
                "stop_loss_pips": 50,
                "take_profit_pips": 100,
                "circuit_breaker_threshold": 0.03,  # 3% move triggers circuit breaker
            },
            expected_metrics={
                "total_trades": 0,  # Should halt trading
                "win_rate": 0,
                "sharpe_ratio": -5.0,
                "max_drawdown": 0.30,
                "profit_factor": 0,
            },
        )


class RiskScenarioFactory:
    """Factory for generating risk management scenarios."""

    @classmethod
    def create_drawdown_scenario(cls) -> RiskScenario:
        """Create a drawdown risk scenario."""
        position_factory = PositionFactory()

        # Create losing positions
        positions = [
            position_factory.create_losing_position(
                symbol="EURUSD",
                quantity=100000,
                entry_price=1.1000,
                current_price=1.0950,  # 50 pip loss
            )
            for _ in range(5)
        ]

        risk_events = [
            {
                "timestamp": datetime.now(),
                "event_type": "drawdown_threshold_reached",
                "severity": "high",
                "current_drawdown": 0.15,
                "threshold": 0.10,
            }
        ]

        expected_actions = [
            "reduce_position_sizes",
            "close_losing_positions",
            "halt_new_trades",
            "send_risk_alert",
        ]

        return RiskScenario(
            scenario_id="RISK-001",
            name="Maximum Drawdown Breach",
            description="Portfolio drawdown exceeds maximum threshold",
            market_condition="volatile",
            volatility_multiplier=2.0,
            drawdown_threshold=0.10,
            positions=positions,
            risk_events=risk_events,
            expected_actions=expected_actions,
        )

    @classmethod
    def create_concentration_risk_scenario(cls) -> RiskScenario:
        """Create a concentration risk scenario."""
        position_factory = PositionFactory()

        # Create concentrated positions in one symbol
        positions = [
            position_factory.create(
                symbol="EURUSD", quantity=500000, side=OrderSide.BUY
            )
            for _ in range(3)
        ]

        # Add one position in different symbol
        positions.append(position_factory.create(symbol="GBPUSD", quantity=50000))

        risk_events = [
            {
                "timestamp": datetime.now(),
                "event_type": "concentration_limit_breach",
                "severity": "medium",
                "symbol": "EURUSD",
                "exposure": 1500000,
                "limit": 1000000,
            }
        ]

        expected_actions = [
            "reduce_eurusd_exposure",
            "diversify_portfolio",
            "apply_position_limits",
        ]

        return RiskScenario(
            scenario_id="RISK-002",
            name="Position Concentration Risk",
            description="Excessive exposure to single currency pair",
            market_condition="normal",
            volatility_multiplier=1.0,
            drawdown_threshold=0.05,
            positions=positions,
            risk_events=risk_events,
            expected_actions=expected_actions,
        )

    @classmethod
    def create_margin_call_scenario(cls) -> RiskScenario:
        """Create a margin call scenario."""
        position_factory = PositionFactory()
        account_factory = AccountFactory()

        # Create positions using most of available margin
        positions = [
            position_factory.create_losing_position(quantity=200000, margin_used=9000)
            for _ in range(3)
        ]

        risk_events = [
            {
                "timestamp": datetime.now(),
                "event_type": "margin_call_warning",
                "severity": "critical",
                "margin_level": 0.25,  # 25% margin level
                "required_margin": 30000,
                "available_margin": 7500,
            }
        ]

        expected_actions = [
            "close_largest_losing_position",
            "reduce_all_positions_by_50%",
            "disable_new_trades",
            "send_urgent_margin_alert",
            "initiate_emergency_liquidation",
        ]

        return RiskScenario(
            scenario_id="RISK-003",
            name="Margin Call Emergency",
            description="Account approaching margin call level",
            market_condition="crisis",
            volatility_multiplier=3.0,
            drawdown_threshold=0.20,
            positions=positions,
            risk_events=risk_events,
            expected_actions=expected_actions,
        )


# Example usage and testing
if __name__ == "__main__":
    # Test ML Feature Factory
    print("Testing ML Feature Factory...")
    ml_features = MLFeatureFactory.create()
    print(f"  RSI: {ml_features.rsi:.2f}")
    print(f"  Volatility: {ml_features.volatility:.5f}")
    print(f"  London Session: {ml_features.is_london_session}")

    # Create feature matrix
    X = MLFeatureFactory.create_feature_matrix(periods=10)
    print(f"  Feature matrix shape: {X.shape}")

    # Test Backtest Factory
    print("\nTesting Backtest Factory...")
    bullish_scenario = BacktestFactory.create_trending_scenario("bullish")
    print(f"  Scenario: {bullish_scenario.name}")
    print(f"  Symbols: {bullish_scenario.symbols}")
    print(f"  Expected win rate: {bullish_scenario.expected_metrics['win_rate']:.1%}")

    volatile_scenario = BacktestFactory.create_volatile_scenario()
    print(f"  Volatile scenario: {volatile_scenario.name}")
    print(
        f"  Risk parameters: {volatile_scenario.risk_parameters['max_risk_per_trade']:.1%} max risk"
    )

    # Test Risk Scenario Factory
    print("\nTesting Risk Scenario Factory...")
    drawdown_scenario = RiskScenarioFactory.create_drawdown_scenario()
    print(f"  Scenario: {drawdown_scenario.name}")
    print(f"  Expected actions: {', '.join(drawdown_scenario.expected_actions[:2])}")

    margin_scenario = RiskScenarioFactory.create_margin_call_scenario()
    print(f"  Margin scenario: {margin_scenario.name}")
    print(f"  Severity: {margin_scenario.risk_events[0]['severity']}")

    print("\n✅ All advanced factories working correctly!")
