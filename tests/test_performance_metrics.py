"""Tests for performance metrics module."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from fxml4.backtesting.performance_metrics import PerformanceAnalyzer, ScenarioAnalyzer


@pytest.fixture
def equity_curve():
    """Create sample equity curve for testing."""
    dates = pd.date_range(start="2022-01-01", end="2022-12-31", freq="D")
    equity = np.array([10000.0])  # Starting equity

    # Simulate an equity curve with some ups and downs
    for i in range(1, len(dates)):
        daily_return = np.random.normal(0.0005, 0.01)  # Mean: 0.05%, Std: 1%
        equity = np.append(equity, equity[-1] * (1 + daily_return))

    return pd.DataFrame({"timestamp": dates, "equity": equity})


@pytest.fixture
def sample_trades():
    """Create sample trades for testing."""
    dates = pd.date_range(start="2022-01-01", end="2022-12-31", freq="D")
    trades = []

    for i in range(50):  # 50 trades
        entry_time = dates[np.random.randint(0, len(dates) - 10)]
        exit_time = entry_time + timedelta(days=np.random.randint(1, 10))
        is_win = np.random.random() > 0.4  # 60% win rate

        pnl = np.random.normal(200, 50) if is_win else np.random.normal(-100, 30)

        trades.append(
            {
                "entry_time": entry_time,
                "exit_time": exit_time,
                "pnl": pnl,
                "symbol": np.random.choice(["EURUSD", "GBPUSD", "USDJPY"]),
                "side": "buy" if np.random.random() > 0.5 else "sell",
                "commission": np.random.uniform(5, 15),
                "slippage": np.random.uniform(1, 5),
                "metadata": {
                    "market_regime": np.random.choice(["trend", "range", "volatile"])
                },
            }
        )

    return trades


@pytest.fixture
def benchmark_data():
    """Create benchmark data for testing."""
    dates = pd.date_range(start="2022-01-01", end="2022-12-31", freq="D")
    benchmark_equity = np.array([10000.0])

    for i in range(1, len(dates)):
        daily_return = np.random.normal(0.0003, 0.008)  # Lower return, lower volatility
        benchmark_equity = np.append(
            benchmark_equity, benchmark_equity[-1] * (1 + daily_return)
        )

    return pd.DataFrame({"timestamp": dates, "close": benchmark_equity}).set_index(
        "timestamp"
    )


@pytest.fixture
def performance_analyzer(benchmark_data):
    """Create performance analyzer for testing."""
    return PerformanceAnalyzer(
        risk_free_rate=0.02, benchmark_data=benchmark_data  # 2% annual risk-free rate
    )


@pytest.fixture
def scenario_analyzer(performance_analyzer):
    """Create scenario analyzer for testing."""
    return ScenarioAnalyzer(performance_analyzer)


class TestPerformanceMetrics:
    """Test case for performance metrics module."""

    def test_calculate_metrics(self, performance_analyzer, equity_curve, sample_trades):
        """Test calculate_metrics method."""
        metrics = performance_analyzer.calculate_metrics(equity_curve, sample_trades)

        # Basic checks to ensure metrics are calculated
        assert metrics.total_return is not None
        assert metrics.sharpe_ratio is not None
        assert metrics.max_drawdown is not None
        assert metrics.win_rate is not None

        # Check types
        assert isinstance(metrics.total_return, float)
        assert isinstance(metrics.annualized_return, float)
        assert isinstance(metrics.drawdown_duration, timedelta)

        # Verify benchmark comparison metrics are calculated
        assert metrics.alpha is not None
        assert metrics.beta is not None

        # Check that monthly returns table was created
        assert metrics.monthly_returns is not None
        assert isinstance(metrics.monthly_returns, pd.DataFrame)

    def test_analyze_drawdowns(self, performance_analyzer, equity_curve):
        """Test analyze_drawdowns method."""
        drawdowns = performance_analyzer.analyze_drawdowns(
            equity_curve,
            min_drawdown_pct=0.01,  # Lower threshold to ensure we capture some drawdowns
            top_n=3,
        )

        # Check if we found any drawdowns
        if not drawdowns.empty:
            # Basic checks
            assert len(drawdowns) <= 3  # Should have at most 3 drawdowns
            assert "start_date" in drawdowns.columns
            assert "max_drawdown_pct" in drawdowns.columns

            # Check values
            assert all(
                drawdowns["max_drawdown_pct"] <= 0
            )  # Drawdowns should be negative

    def test_risk_contribution_analysis(self, performance_analyzer, sample_trades):
        """Test risk_contribution_analysis method."""
        risk_analysis = performance_analyzer.risk_contribution_analysis(sample_trades)

        # Check if analysis was performed
        assert "by_symbol" in risk_analysis
        assert "by_regime" in risk_analysis
        assert "by_hour" in risk_analysis

        # Check symbol analysis
        symbol_analysis = risk_analysis["by_symbol"]
        assert len(symbol_analysis) > 0
        assert "symbol" in symbol_analysis.columns
        assert "win_rate" in symbol_analysis.columns

        # Check regime analysis
        regime_analysis = risk_analysis["by_regime"]
        assert len(regime_analysis) > 0
        assert "regime" in regime_analysis.columns

    @pytest.mark.slow
    def test_monte_carlo_simulation(self, performance_analyzer, sample_trades):
        """Test monte_carlo_simulation method."""
        simulation = performance_analyzer.create_monte_carlo_simulation(
            sample_trades,
            initial_capital=10000.0,
            num_simulations=100,  # Lower for faster tests
        )

        # Check simulation results
        assert "final_equity_percentiles" in simulation
        assert "drawdown_percentiles" in simulation
        assert "probability_of_profit" in simulation

        # Check percentiles
        percentiles = simulation["final_equity_percentiles"]
        assert 5 in percentiles
        assert 95 in percentiles
        assert (
            percentiles[95] > percentiles[5]
        )  # Higher percentile should have higher value

    def test_scenario_analyzer(self, scenario_analyzer, equity_curve, sample_trades):
        """Test scenario analyzer."""
        # Add two scenarios with different parameters
        scenario_analyzer.add_scenario(
            name="Baseline",
            equity_curve=equity_curve,
            trades=sample_trades,
            parameters={"stop_loss": 0.02, "take_profit": 0.04},
        )

        # Create a modified equity curve for second scenario
        equity2 = equity_curve.copy()
        equity2["equity"] = equity2["equity"] * 1.05  # 5% better performance

        scenario_analyzer.add_scenario(
            name="Improved",
            equity_curve=equity2,
            trades=sample_trades,
            parameters={"stop_loss": 0.025, "take_profit": 0.05},
        )

        # Test comparison
        comparison = scenario_analyzer.compare_scenarios()
        assert len(comparison) == 2
        assert "Baseline" in comparison.index
        assert "Improved" in comparison.index

        # Test parameter sensitivity
        sensitivity = scenario_analyzer.analyze_parameter_sensitivity("stop_loss")
        assert len(sensitivity) == 2
        assert "parameter" in sensitivity.columns
        assert "metric" in sensitivity.columns

        # Test finding optimal scenario
        optimal_name, _ = scenario_analyzer.find_optimal_scenario("total_return_pct")
        assert (
            optimal_name == "Improved"
        )  # The improved scenario should have better returns
