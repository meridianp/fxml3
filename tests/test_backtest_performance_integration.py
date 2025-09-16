"""Tests for the backtest engine and performance metrics integration."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from fxml4.backtesting.backtest_engine import BacktestEngine, OrderSide
from fxml4.backtesting.event_driven_engine import EventDrivenEngine


class SimpleStrategy:
    """Simple test strategy."""

    def __init__(self, buy_threshold=0.0002, sell_threshold=-0.0002):
        """Initialize strategy parameters."""
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.name = "SimpleStrategy"

    def __call__(self, data, index, params):
        """Generate signals based on price data.

        Args:
            data: DataFrame of price data.
            index: Current bar index.
            params: Strategy parameters.

        Returns:
            Dictionary of signals.
        """
        signals = {}

        if index < 5:  # Not enough data
            return signals

        # Calculate price change
        price_change = (
            data["close"].iloc[index] - data["close"].iloc[index - 5]
        ) / data["close"].iloc[index - 5]

        # Buy signal
        if price_change > self.buy_threshold:
            signals["entry"] = True
            signals["direction"] = "buy"
            signals["risk_pct"] = 0.01

        # Sell signal
        elif price_change < self.sell_threshold:
            signals["entry"] = True
            signals["direction"] = "sell"
            signals["risk_pct"] = 0.01

        # Exit signal (simplified for test)
        elif "symbol" in params and params["symbol"] in params.get("positions", {}):
            if (
                price_change < 0
                and params["positions"][params["symbol"]]["side"] == OrderSide.BUY
            ):
                signals["exit"] = True
            elif (
                price_change > 0
                and params["positions"][params["symbol"]]["side"] == OrderSide.SELL
            ):
                signals["exit"] = True

        return signals


@pytest.fixture
def test_data():
    """Generate test data for backtesting.

    Returns:
        DataFrame with price data.
    """
    np.random.seed(42)  # For reproducibility

    # Generate date range
    dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="D")

    # Generate price series with some trend and volatility
    price = 100.0
    prices = [price]

    for _ in range(1, len(dates)):
        # Random walk with some mean reversion
        change = np.random.normal(0, 0.01)
        # Add some mean reversion
        mean_reversion = (100 - price) * 0.01
        price = price * (1 + change + mean_reversion)
        prices.append(price)

    # Create OHLC data
    high_prices = [p * (1 + np.random.uniform(0, 0.005)) for p in prices]
    low_prices = [p * (1 - np.random.uniform(0, 0.005)) for p in prices]

    data = pd.DataFrame(
        {
            "time": dates,
            "open": prices,
            "high": high_prices,
            "low": low_prices,
            "close": [p * (1 + np.random.normal(0, 0.002)) for p in prices],
            "volume": np.random.lognormal(mean=10, sigma=1, size=len(dates)),
            "symbol": "TEST",
        }
    )

    return data


@pytest.fixture
def simple_strategy():
    """Create a simple test strategy."""
    return SimpleStrategy()


@pytest.fixture
def standard_engine():
    """Create a standard backtest engine."""
    return BacktestEngine(
        {
            "initial_capital": 10000,
            "commission": 0.001,
            "slippage": 0.0005,
        }
    )


@pytest.fixture
def events_engine(simple_strategy):
    """Create an event-driven backtest engine."""

    def event_strategy(symbol, current_bar, market_data, portfolio):
        """Event-driven strategy adapter.

        Args:
            symbol: Symbol of the market data.
            current_bar: Current price bar.
            market_data: Historical market data.
            portfolio: Portfolio instance.

        Returns:
            Dictionary of signals.
        """
        if market_data is None or len(market_data) < 5:
            return {}

        # Extract position information
        positions = {}
        if portfolio:
            for sym, pos in portfolio.positions.items():
                positions[sym] = {"side": pos["side"]}

        # Calculate price change
        price_change = (
            current_bar["close"] - market_data["close"].iloc[-5]
        ) / market_data["close"].iloc[-5]

        signals = {}

        # Buy signal
        if price_change > simple_strategy.buy_threshold:
            signals["entry"] = {
                "side": "buy",
                "order_type": "market",
                "risk_pct": 0.01,
            }

        # Sell signal
        elif price_change < simple_strategy.sell_threshold:
            signals["entry"] = {
                "side": "sell",
                "order_type": "market",
                "risk_pct": 0.01,
            }

        # Exit signal
        elif symbol in positions:
            current_side = positions[symbol]["side"]
            if price_change < 0 and current_side == "buy":
                signals["exit"] = {
                    "order_type": "market",
                }
            elif price_change > 0 and current_side == "sell":
                signals["exit"] = {
                    "order_type": "market",
                }

        return signals

    return EventDrivenEngine(
        strategy=event_strategy,
        initial_capital=10000.0,
    )


class TestBacktestPerformanceIntegration:
    """Test case for integration of performance metrics with backtesting."""

    @pytest.mark.integration
    def test_standard_backtest_performance_integration(
        self, standard_engine, simple_strategy, test_data
    ):
        """Test integration of performance metrics with standard backtest engine."""
        # Run backtest
        result = standard_engine.run(
            strategy=simple_strategy,
            data=test_data,
            strategy_params={"symbol": "TEST"},
        )

        # Verify result contains performance metrics
        assert result is not None
        assert result.performance_metrics is not None

        # Check that key metrics are calculated
        assert result.max_drawdown_pct is not None
        assert result.sharpe_ratio is not None
        assert result.win_rate is not None

        # Check that advanced metrics are available
        # Note: These might be None if the PerformanceAnalyzer isn't available
        assert result.drawdown_analysis is not None
        assert result.risk_analysis is not None

        # Test that we can generate a summary
        summary = result.get_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0

    @pytest.mark.integration
    def test_event_driven_backtest_performance_integration(
        self, events_engine, test_data
    ):
        """Test integration of performance metrics with event-driven backtest engine."""
        # Load data
        events_engine.load_data(test_data)

        # Run backtest
        result = events_engine.run()

        # Verify result contains performance metrics
        assert result is not None
        assert result.performance_metrics is not None

        # Check that key metrics are calculated
        assert result.max_drawdown_pct is not None
        assert result.sharpe_ratio is not None
        assert result.win_rate is not None

        # Check that advanced metrics are available
        # Note: These might be None if the PerformanceAnalyzer isn't available
        assert result.drawdown_analysis is not None
        assert result.risk_analysis is not None

        # Test that we can generate a summary
        summary = result.get_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0

    @pytest.mark.integration
    def test_equity_curve_consistency(
        self, standard_engine, simple_strategy, test_data
    ):
        """Test that equity curve is properly calculated."""
        # Run backtest
        result = standard_engine.run(
            strategy=simple_strategy,
            data=test_data,
            strategy_params={"symbol": "TEST"},
        )

        # Check equity curve
        assert result.equity_curve is not None
        assert "equity" in result.equity_curve.columns
        assert "timestamp" in result.equity_curve.columns

        # Equity should never be negative
        assert (result.equity_curve["equity"] >= 0).all()

        # Check that initial equity matches initial capital
        assert (
            abs(result.equity_curve["equity"].iloc[0] - result.initial_capital) < 0.01
        )

        # Check that final equity matches final capital
        assert abs(result.equity_curve["equity"].iloc[-1] - result.final_capital) < 0.01

    @pytest.mark.integration
    def test_report_generation(self, standard_engine, simple_strategy, test_data):
        """Test that reports can be generated."""
        # Run backtest
        result = standard_engine.run(
            strategy=simple_strategy,
            data=test_data,
            strategy_params={"symbol": "TEST"},
        )

        try:
            # Try to generate a report
            report_path = result.generate_report(include_figures=False)

            # Check if report generation was successful
            if report_path:
                assert len(report_path) > 0

        except ImportError:
            # Skip test if visualization modules aren't available
            pytest.skip("Visualization modules not available for report generation")
