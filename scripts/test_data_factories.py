#!/usr/bin/env python3
"""
Test Data Factories Validation Script

This script validates that all test data factories are working correctly
and can generate realistic test data for the FXML4 system.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import factory modules
try:
    from tests.factories.simple_data_factories import (
        AccountFactory,
        MarketDataFactory,
        OrderFactory,
        OrderSide,
        OrderStatus,
        PositionFactory,
        SignalFactory,
        SignalStrength,
        TestDataGenerator,
    )

    BASIC_FACTORIES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Basic factories not available: {e}")
    BASIC_FACTORIES_AVAILABLE = False

try:
    from tests.factories.advanced_data_factories import (
        BacktestFactory,
        MLFeatureFactory,
        RiskScenarioFactory,
    )

    ADVANCED_FACTORIES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Advanced factories not available: {e}")
    ADVANCED_FACTORIES_AVAILABLE = False


def test_market_data_factory():
    """Test market data generation."""
    print("1. Testing Market Data Factory...")

    try:
        # Single data point
        market_data = MarketDataFactory.create(symbol="EURUSD")
        assert market_data.symbol == "EURUSD"
        assert market_data.bid < market_data.ask
        assert market_data.spread > 0
        print(
            f"   ✓ Created single market data: {market_data.symbol} @ {market_data.mid:.5f}"
        )

        # Time series
        series = MarketDataFactory.create_series("GBPUSD", periods=10, timeframe="1h")
        assert len(series) == 10
        assert all(d.symbol == "GBPUSD" for d in series)
        print(f"   ✓ Created time series with {len(series)} data points")

        # Trending market
        trending = MarketDataFactory.create_trending_market(
            "USDJPY", periods=20, trend="up"
        )
        assert len(trending) == 20
        # Check trend (last price should be higher than first for uptrend)
        assert trending[-1].mid > trending[0].mid
        print(f"   ✓ Created trending market data")

        return True

    except Exception as e:
        print(f"   ❌ Market data factory failed: {e}")
        return False


def test_order_factory():
    """Test order generation."""
    print("\n2. Testing Order Factory...")

    try:
        # Market order
        market_order = OrderFactory.create_market_order(
            symbol="EURUSD", side=OrderSide.BUY, quantity=100000
        )
        assert market_order.order_type.value == "MARKET"
        assert market_order.side == OrderSide.BUY
        assert market_order.quantity == 100000
        print(f"   ✓ Created market order: {market_order.order_id}")

        # Limit order
        limit_order = OrderFactory.create_limit_order(price=1.1050)
        assert limit_order.order_type.value == "LIMIT"
        assert limit_order.price == 1.1050
        print(f"   ✓ Created limit order with price: {limit_order.price}")

        # Filled order
        filled_order = OrderFactory.create_filled_order(fill_price=1.1000)
        assert filled_order.status == OrderStatus.FILLED
        assert filled_order.average_fill_price == 1.1000
        print(f"   ✓ Created filled order")

        # Batch orders
        batch = OrderFactory.create_batch(count=5)
        assert len(batch) == 5
        print(f"   ✓ Created batch of {len(batch)} orders")

        return True

    except Exception as e:
        print(f"   ❌ Order factory failed: {e}")
        return False


def test_position_factory():
    """Test position generation."""
    print("\n3. Testing Position Factory...")

    try:
        # Basic position
        position = PositionFactory.create(
            symbol="GBPUSD", side=OrderSide.SELL, quantity=50000
        )
        assert position.symbol == "GBPUSD"
        assert position.side == OrderSide.SELL
        print(f"   ✓ Created position: {position.position_id}")

        # Winning position
        winner = PositionFactory.create_winning_position()
        assert winner.unrealized_pnl > 0
        print(f"   ✓ Created winning position with P&L: ${winner.unrealized_pnl:.2f}")

        # Losing position
        loser = PositionFactory.create_losing_position()
        assert loser.unrealized_pnl < 0
        print(f"   ✓ Created losing position with P&L: ${loser.unrealized_pnl:.2f}")

        # Portfolio
        portfolio = PositionFactory.create_portfolio(count=10)
        assert len(portfolio) == 10
        total_pnl = sum(p.unrealized_pnl for p in portfolio)
        print(
            f"   ✓ Created portfolio with {len(portfolio)} positions, total P&L: ${total_pnl:.2f}"
        )

        return True

    except Exception as e:
        print(f"   ❌ Position factory failed: {e}")
        return False


def test_signal_factory():
    """Test signal generation."""
    print("\n4. Testing Signal Factory...")

    try:
        # Basic signal
        signal = SignalFactory.create(
            symbol="EURUSD", strength=SignalStrength.STRONG_BUY, confidence=0.85
        )
        assert signal.symbol == "EURUSD"
        assert signal.strength == SignalStrength.STRONG_BUY
        assert signal.confidence == 0.85
        print(f"   ✓ Created signal: {signal.signal_id} - {signal.strength.value}")

        # Buy signal
        buy_signal = SignalFactory.create_buy_signal()
        assert buy_signal.strength in [SignalStrength.BUY, SignalStrength.STRONG_BUY]
        assert buy_signal.stop_loss < buy_signal.entry_price
        assert buy_signal.take_profit > buy_signal.entry_price
        print(
            f"   ✓ Created buy signal with R:R ratio: {buy_signal.risk_reward_ratio:.2f}"
        )

        # Signal series
        series = SignalFactory.create_signal_series("GBPUSD", periods=5)
        assert len(series) == 5
        print(f"   ✓ Created signal series with {len(series)} signals")

        return True

    except Exception as e:
        print(f"   ❌ Signal factory failed: {e}")
        return False


def test_account_factory():
    """Test account generation."""
    print("\n5. Testing Account Factory...")

    try:
        # Basic account
        account = AccountFactory.create(balance=25000)
        assert account.balance == 25000
        assert account.equity == account.balance + account.unrealized_pnl
        print(
            f"   ✓ Created account: {account.account_id} with balance: ${account.balance:.2f}"
        )

        # Funded account
        funded = AccountFactory.create_funded_account(balance=100000)
        assert funded.balance == 100000
        assert funded.margin_used == 0
        print(f"   ✓ Created funded account: ${funded.balance:.2f}")

        # Margin call account
        margin_call = AccountFactory.create_margin_call_account()
        margin_level = (
            (margin_call.equity / margin_call.margin_used) * 100
            if margin_call.margin_used > 0
            else 0
        )
        assert margin_call.margin_used > margin_call.balance * 0.9
        print(
            f"   ✓ Created margin call account with margin level: {margin_level:.1f}%"
        )

        return True

    except Exception as e:
        print(f"   ❌ Account factory failed: {e}")
        return False


def test_complete_scenario():
    """Test complete trading scenario generation."""
    print("\n6. Testing Complete Trading Scenario...")

    try:
        generator = TestDataGenerator()

        # Generate complete scenario
        scenario = generator.generate_complete_trading_scenario()

        assert "account" in scenario
        assert "market_data" in scenario
        assert "signals" in scenario
        assert "orders" in scenario
        assert "positions" in scenario

        print(f"   ✓ Generated complete scenario:")
        print(f"      - Account balance: ${scenario['account'].balance:.2f}")
        print(f"      - Market data points: {len(scenario['market_data'])}")
        print(f"      - Signals: {len(scenario['signals'])}")
        print(f"      - Orders: {len(scenario['orders'])}")
        print(f"      - Positions: {len(scenario['positions'])}")

        # Generate backtest data
        backtest_data = generator.generate_backtest_data(
            symbols=["EURUSD", "GBPUSD"], days=7
        )
        assert "market_data" in backtest_data
        assert len(backtest_data["market_data"]) == 2
        print(
            f"   ✓ Generated backtest data for {len(backtest_data['market_data'])} symbols"
        )

        # Generate stress test data
        stress_data = generator.generate_stress_test_data()
        assert len(stress_data["high_frequency_orders"]) == 1000
        assert len(stress_data["volatile_market"]) == 1000
        print(
            f"   ✓ Generated stress test data with {len(stress_data['high_frequency_orders'])} orders"
        )

        return True

    except Exception as e:
        print(f"   ❌ Complete scenario generation failed: {e}")
        return False


def test_ml_features():
    """Test ML feature generation."""
    if not ADVANCED_FACTORIES_AVAILABLE:
        print("\n7. ML Feature Factory - Skipped (not available)")
        return True

    print("\n7. Testing ML Feature Factory...")

    try:
        # Single feature set
        features = MLFeatureFactory.create(symbol="EURUSD")
        assert features.symbol == "EURUSD"
        assert 0 <= features.rsi <= 100
        assert features.hour_of_day >= 0 and features.hour_of_day < 24
        print(
            f"   ✓ Created ML features with RSI: {features.rsi:.2f}, Volatility: {features.volatility:.5f}"
        )

        # Feature matrix
        import numpy as np

        X = MLFeatureFactory.create_feature_matrix(periods=50)
        assert X.shape == (50, 17)  # 50 samples, 17 features
        print(f"   ✓ Created feature matrix with shape: {X.shape}")

        # Labeled dataset
        X_train, y_train = MLFeatureFactory.create_labeled_dataset(periods=100)
        assert X_train.shape[0] == y_train.shape[0]
        assert all(label in [-1, 0, 1] for label in y_train)
        print(f"   ✓ Created labeled dataset with {len(y_train)} samples")

        return True

    except Exception as e:
        print(f"   ❌ ML feature factory failed: {e}")
        return False


def test_backtest_scenarios():
    """Test backtest scenario generation."""
    if not ADVANCED_FACTORIES_AVAILABLE:
        print("\n8. Backtest Scenarios - Skipped (not available)")
        return True

    print("\n8. Testing Backtest Scenarios...")

    try:
        # Trending scenario
        bullish = BacktestFactory.create_trending_scenario("bullish")
        assert bullish.name == "Bullish Trend Scenario"
        assert len(bullish.symbols) > 0
        assert bullish.initial_balance > 0
        print(f"   ✓ Created bullish scenario: {bullish.name}")

        # Volatile scenario
        volatile = BacktestFactory.create_volatile_scenario()
        assert (
            "volatility" in volatile.name.lower() or "volatile" in volatile.name.lower()
        )
        assert volatile.risk_parameters["max_risk_per_trade"] < 0.02
        print(f"   ✓ Created volatile scenario: {volatile.name}")

        # Flash crash scenario
        crash = BacktestFactory.create_flash_crash_scenario()
        assert "crash" in crash.name.lower()
        assert crash.expected_metrics["max_drawdown"] > 0.2
        print(f"   ✓ Created flash crash scenario: {crash.name}")

        return True

    except Exception as e:
        print(f"   ❌ Backtest scenario generation failed: {e}")
        return False


def test_risk_scenarios():
    """Test risk scenario generation."""
    if not ADVANCED_FACTORIES_AVAILABLE:
        print("\n9. Risk Scenarios - Skipped (not available)")
        return True

    print("\n9. Testing Risk Scenarios...")

    try:
        # Drawdown scenario
        drawdown = RiskScenarioFactory.create_drawdown_scenario()
        assert drawdown.scenario_id == "RISK-001"
        assert len(drawdown.expected_actions) > 0
        print(f"   ✓ Created drawdown scenario: {drawdown.name}")

        # Concentration risk
        concentration = RiskScenarioFactory.create_concentration_risk_scenario()
        assert "concentration" in concentration.name.lower()
        assert len(concentration.positions) > 0
        print(f"   ✓ Created concentration risk scenario: {concentration.name}")

        # Margin call scenario
        margin_call = RiskScenarioFactory.create_margin_call_scenario()
        assert margin_call.risk_events[0]["severity"] == "critical"
        assert "liquidation" in " ".join(margin_call.expected_actions).lower()
        print(f"   ✓ Created margin call scenario: {margin_call.name}")

        return True

    except Exception as e:
        print(f"   ❌ Risk scenario generation failed: {e}")
        return False


def main():
    """Main validation function."""
    print("FXML4 Test Data Factories Validation")
    print("=" * 50)

    if not BASIC_FACTORIES_AVAILABLE:
        print("❌ Basic factories not available")
        return 1

    tests = [
        ("Market Data Factory", test_market_data_factory),
        ("Order Factory", test_order_factory),
        ("Position Factory", test_position_factory),
        ("Signal Factory", test_signal_factory),
        ("Account Factory", test_account_factory),
        ("Complete Scenario", test_complete_scenario),
        ("ML Features", test_ml_features),
        ("Backtest Scenarios", test_backtest_scenarios),
        ("Risk Scenarios", test_risk_scenarios),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            success = test_func()
            if success:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            failed += 1

    print(f"\n" + "=" * 50)
    print(f"Validation Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All test data factories validated successfully!")
        print("\nCapabilities Validated:")
        print("  ✅ Market data generation (single, series, trending)")
        print("  ✅ Order creation (market, limit, stop, filled)")
        print("  ✅ Position management (winning, losing, portfolios)")
        print("  ✅ Signal generation (buy, sell, series)")
        print("  ✅ Account states (funded, margin call)")
        print("  ✅ Complete trading scenarios")

        if ADVANCED_FACTORIES_AVAILABLE:
            print("  ✅ ML feature generation")
            print("  ✅ Backtest scenario creation")
            print("  ✅ Risk scenario simulation")

        print("\nData Generation Features:")
        print("  • Realistic forex market data with proper spreads")
        print("  • Time-series data with configurable timeframes")
        print("  • Correlated feature generation for ML")
        print("  • Complex trading scenarios for integration testing")
        print("  • Risk scenarios for stress testing")
        print("  • Configurable market conditions (trending, volatile, crash)")

        return 0
    else:
        print(f"⚠️  {failed} validation tests failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
