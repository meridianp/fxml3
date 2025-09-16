"""Tests for automatic performance report generation."""

import os
import shutil
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.backtesting.backtest_engine import BacktestEngine
from fxml4.backtesting.event_driven_engine import EventDrivenEngine


@pytest.fixture
def test_output_dir():
    """Create temporary directory for test reports."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def test_data():
    """Generate sample data for testing."""
    dates = pd.date_range(start="2023-01-01", end="2023-01-31", freq="D")

    # Generate random prices with trend
    price = 100.0
    prices = [price]
    for _ in range(1, len(dates)):
        # Random price change with slight upward bias
        change = np.random.normal(0.001, 0.01)
        price = price * (1 + change)
        prices.append(price)

    # Create dataframe
    data = pd.DataFrame(
        {
            "time": dates,
            "open": prices,
            "high": [p * (1 + np.random.uniform(0, 0.005)) for p in prices],
            "low": [p * (1 - np.random.uniform(0, 0.005)) for p in prices],
            "close": [p * (1 + np.random.normal(0, 0.002)) for p in prices],
            "volume": np.random.lognormal(mean=10, sigma=1, size=len(dates)),
            "symbol": "TEST",
        }
    )

    return data


@pytest.fixture
def simple_strategy():
    """Simple test strategy for backtesting."""

    def strategy(data, idx, params):
        """Simple test strategy."""
        if idx < 5:
            return {}

        returns = data["close"].pct_change()
        if len(returns) > 5:
            # Buy if positive returns for last 3 days
            if all(returns.iloc[-3:] > 0):
                return {"entry": True, "direction": "buy", "risk_pct": 0.01}
            # Sell if we have a position and negative returns for last 3 days
            elif (
                all(returns.iloc[-3:] < 0)
                and "positions" in params
                and params.get("symbol") in params.get("positions", {})
            ):
                return {"exit": True}
        return {}

    return strategy


@pytest.fixture
def simple_event_strategy():
    """Simple event-driven strategy for testing."""

    def strategy(symbol, current_bar, market_data, portfolio):
        """Simple event-based strategy."""
        if market_data is None or len(market_data) < 5:
            return {}

        returns = market_data["close"].pct_change().dropna()
        if len(returns) > 3:
            # Buy if positive returns for last 3 days
            if all(returns.iloc[-3:] > 0):
                return {
                    "entry": {"side": "buy", "order_type": "market", "risk_pct": 0.01}
                }
            # Sell if we have a position and negative returns for last 3 days
            elif (
                all(returns.iloc[-3:] < 0)
                and portfolio
                and symbol in portfolio.positions
            ):
                return {"exit": {"order_type": "market"}}
        return {}

    return strategy


@pytest.fixture
def backtest_engine():
    """Create BacktestEngine for testing."""
    return BacktestEngine(
        {
            "initial_capital": 10000,
            "commission": 0.001,
            "slippage": 0.0005,
        }
    )


class TestAutoReporting:
    """Test automatic report generation for backtesting engines."""

    @patch("fxml4.config.get_config")
    def test_auto_reporting_standard_engine(
        self,
        mock_get_config,
        test_output_dir,
        test_data,
        simple_strategy,
        backtest_engine,
    ):
        """Test automatic report generation with standard backtest engine."""

        # Mock configuration to enable auto-reporting
        def config_side_effect(key, default=None):
            """Side effect function for mocked get_config."""
            if key == "backtesting.reporting.auto_generate":
                return True
            elif key == "backtesting.reporting.output_dir":
                return test_output_dir
            elif key == "backtesting.reporting.include_figures":
                return False  # Disable figures for faster testing
            elif key == "backtesting.reporting.export_pdf":
                return False
            return default

        mock_get_config.side_effect = config_side_effect

        # Mock the generate_report method to verify it's called and return a test path
        with patch(
            "fxml4.backtesting.backtest_engine.BacktestResult.generate_report"
        ) as mock_generate:
            mock_generate.return_value = os.path.join(
                test_output_dir, "test_report.html"
            )

            # Run backtest
            result = backtest_engine.run(
                strategy=simple_strategy,
                data=test_data,
                strategy_params={"symbol": "TEST"},
            )

            # Verify generate_report was called with correct args
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert kwargs["output_dir"] == test_output_dir
            assert kwargs["include_figures"] is False
            assert kwargs["export_pdf"] is False

    @patch("fxml4.config.get_config")
    def test_auto_reporting_event_driven_engine(
        self, mock_get_config, test_output_dir, test_data, simple_event_strategy
    ):
        """Test automatic report generation with event-driven backtest engine."""

        # Mock configuration to enable auto-reporting
        def config_side_effect(key, default=None):
            """Side effect function for mocked get_config."""
            if key == "backtesting.reporting.auto_generate":
                return True
            elif key == "backtesting.reporting.output_dir":
                return test_output_dir
            elif key == "backtesting.reporting.include_figures":
                return False  # Disable figures for faster testing
            elif key == "backtesting.reporting.export_pdf":
                return False
            return default

        mock_get_config.side_effect = config_side_effect

        # Create event-driven engine
        engine = EventDrivenEngine(
            strategy=simple_event_strategy,
            initial_capital=10000.0,
        )

        # Load data
        engine.load_data(test_data)

        # Mock the generate_report method
        with patch(
            "fxml4.backtesting.backtest_engine.BacktestResult.generate_report"
        ) as mock_generate:
            mock_generate.return_value = os.path.join(
                test_output_dir, "test_report.html"
            )

            # Run backtest
            result = engine.run()

            # Verify generate_report was called with correct args
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert kwargs["output_dir"] == test_output_dir
            assert kwargs["include_figures"] is False
            assert kwargs["export_pdf"] is False

    @patch("fxml4.config.get_config")
    def test_auto_reporting_disabled(
        self, mock_get_config, test_data, simple_strategy, backtest_engine
    ):
        """Test that reports are not generated when auto-reporting is disabled."""
        # Mock configuration to disable auto-reporting
        mock_get_config.return_value = False

        # Mock the generate_report method to verify it's not called
        with patch(
            "fxml4.backtesting.backtest_engine.BacktestResult.generate_report"
        ) as mock_generate:
            # Run backtest
            result = backtest_engine.run(
                strategy=simple_strategy,
                data=test_data,
                strategy_params={"symbol": "TEST"},
            )

            # Verify generate_report was not called
            mock_generate.assert_not_called()

    @patch("fxml4.config.get_config")
    def test_auto_reporting_with_custom_settings(
        self,
        mock_get_config,
        test_output_dir,
        test_data,
        simple_strategy,
        backtest_engine,
    ):
        """Test auto-reporting with custom output settings."""

        # Mock configuration with custom settings
        def config_side_effect(key, default=None):
            """Side effect function for mocked get_config."""
            settings = {
                "backtesting.reporting.auto_generate": True,
                "backtesting.reporting.output_dir": test_output_dir + "/custom",
                "backtesting.reporting.include_figures": True,
                "backtesting.reporting.export_pdf": True,
            }
            return settings.get(key, default)

        mock_get_config.side_effect = config_side_effect

        # Create directory for custom output
        os.makedirs(test_output_dir + "/custom", exist_ok=True)

        # Mock the generate_report method
        with patch(
            "fxml4.backtesting.backtest_engine.BacktestResult.generate_report"
        ) as mock_generate:
            mock_generate.return_value = os.path.join(
                test_output_dir, "custom", "test_report.html"
            )

            # Run backtest
            result = backtest_engine.run(
                strategy=simple_strategy,
                data=test_data,
                strategy_params={"symbol": "TEST"},
            )

            # Verify generate_report was called with correct custom args
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert kwargs["output_dir"] == test_output_dir + "/custom"
            assert kwargs["include_figures"] is True
            assert kwargs["export_pdf"] is True
