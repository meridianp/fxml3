"""
Comprehensive unit tests for Advanced Drawdown Controller.

Tests position sizing, risk limits, drawdown control, and circuit breakers
following TDD methodology for increased test coverage.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.risk_management.drawdown_control import (
    AdvancedDrawdownController,
    CircuitBreakerLevel,
    DrawdownState,
    PositionRisk,
    RiskMetrics,
)


@pytest.fixture
def risk_config():
    """Configuration for advanced drawdown controller."""
    return {
        "max_portfolio_risk": 0.06,  # 6% max portfolio risk
        "max_daily_loss": 0.03,  # 3% max daily loss
        "max_drawdown": 0.15,  # 15% max drawdown
        "position_size_base": 0.02,  # 2% base position size
        "volatility_lookback": 20,  # 20 periods for volatility calculation
        "circuit_breaker_levels": [0.05, 0.10, 0.15],  # 5%, 10%, 15%
        "recovery_threshold": 0.5,  # 50% recovery before increasing size
        "risk_scaling_factor": 2.0,  # Risk scaling multiplier
        "min_position_size": 0.005,  # 0.5% minimum position
        "max_position_size": 0.05,  # 5% maximum position
    }


@pytest.fixture
def sample_portfolio_history():
    """Generate sample portfolio performance history."""
    dates = pd.date_range(start="2024-01-01", periods=60, freq="1D")
    np.random.seed(42)

    # Generate realistic portfolio returns
    daily_returns = np.random.normal(0.0005, 0.015, 60)  # 0.05% daily return, 1.5% vol
    cumulative_returns = np.cumprod(1 + daily_returns) - 1
    portfolio_values = 10000 * (1 + cumulative_returns)

    history = []
    for i, (date, value, ret) in enumerate(zip(dates, portfolio_values, daily_returns)):
        history.append(
            {
                "date": date,
                "portfolio_value": value,
                "daily_return": ret,
                "cumulative_return": cumulative_returns[i],
                "positions_count": np.random.randint(1, 5),
                "max_single_position": np.random.uniform(0.01, 0.04),
            }
        )

    return pd.DataFrame(history)


@pytest.fixture
def mock_portfolio_manager():
    """Mock portfolio manager."""
    mock = Mock()
    mock.get_total_portfolio_value.return_value = 10000.0
    mock.get_current_positions.return_value = [
        {"symbol": "EURUSD", "size": 0.02, "unrealized_pnl": 150.0},
        {"symbol": "GBPUSD", "size": 0.015, "unrealized_pnl": -75.0},
    ]
    mock.get_daily_pnl.return_value = -125.0
    return mock


@pytest.fixture
def mock_volatility_estimator():
    """Mock volatility estimator."""
    mock = Mock()
    mock.estimate_portfolio_volatility.return_value = 0.018  # 1.8% daily vol
    mock.estimate_symbol_volatility.return_value = 0.012  # 1.2% symbol vol
    mock.get_correlation_matrix.return_value = np.array([[1.0, 0.6], [0.6, 1.0]])
    return mock


@pytest.fixture
async def drawdown_controller(
    risk_config,
    sample_portfolio_history,
    mock_portfolio_manager,
    mock_volatility_estimator,
):
    """Create advanced drawdown controller with dependencies."""
    controller = AdvancedDrawdownController(risk_config)

    # Inject dependencies
    controller.portfolio_manager = mock_portfolio_manager
    controller.volatility_estimator = mock_volatility_estimator
    controller.portfolio_history = sample_portfolio_history

    await controller.initialize()
    return controller


class TestAdvancedDrawdownControllerInitialization:
    """Test drawdown controller initialization."""

    def test_controller_creation_with_valid_config(self, risk_config):
        """Test controller can be created with valid configuration."""
        controller = AdvancedDrawdownController(risk_config)

        assert controller.max_portfolio_risk == 0.06
        assert controller.max_daily_loss == 0.03
        assert controller.max_drawdown == 0.15
        assert len(controller.circuit_breaker_levels) == 3

    def test_controller_creation_with_invalid_risk_params(self, risk_config):
        """Test controller validates risk parameters."""
        risk_config["max_portfolio_risk"] = 1.5  # 150% - impossible

        with pytest.raises(ValueError, match="Invalid risk parameters"):
            AdvancedDrawdownController(risk_config)

    def test_controller_creation_with_inconsistent_levels(self, risk_config):
        """Test controller validates circuit breaker level consistency."""
        risk_config["circuit_breaker_levels"] = [0.10, 0.05, 0.15]  # Not ascending

        with pytest.raises(
            ValueError, match="Circuit breaker levels must be ascending"
        ):
            AdvancedDrawdownController(risk_config)

    @pytest.mark.asyncio
    async def test_controller_initialization_success(self, drawdown_controller):
        """Test successful controller initialization."""
        assert drawdown_controller.is_initialized
        assert drawdown_controller.current_drawdown is not None
        assert drawdown_controller.circuit_breaker_state is not None


class TestPositionSizeCalculation:
    """Test position sizing algorithms."""

    @pytest.mark.asyncio
    async def test_base_position_size_calculation(self, drawdown_controller):
        """Test basic position size calculation."""
        signal_confidence = 0.8
        symbol_volatility = 0.012

        position_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD",
            signal_confidence=signal_confidence,
            volatility=symbol_volatility,
        )

        # Position size should be positive and within limits
        assert 0 < position_size <= drawdown_controller.max_position_size
        assert position_size >= drawdown_controller.min_position_size

    @pytest.mark.asyncio
    async def test_position_size_volatility_adjustment(self, drawdown_controller):
        """Test position size adjusts for volatility."""
        signal_confidence = 0.8

        # Low volatility scenario
        low_vol_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD",
            signal_confidence=signal_confidence,
            volatility=0.005,  # Low vol
        )

        # High volatility scenario
        high_vol_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD",
            signal_confidence=signal_confidence,
            volatility=0.025,  # High vol
        )

        # Lower volatility should allow larger position
        assert low_vol_size > high_vol_size

    @pytest.mark.asyncio
    async def test_position_size_confidence_scaling(self, drawdown_controller):
        """Test position size scales with signal confidence."""
        volatility = 0.012

        # Low confidence
        low_conf_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD", signal_confidence=0.6, volatility=volatility
        )

        # High confidence
        high_conf_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD", signal_confidence=0.95, volatility=volatility
        )

        # Higher confidence should allow larger position
        assert high_conf_size > low_conf_size

    @pytest.mark.asyncio
    async def test_position_size_drawdown_scaling(self, drawdown_controller):
        """Test position size reduces during drawdown."""
        # Simulate current drawdown
        drawdown_controller.current_drawdown = 0.08  # 8% drawdown

        normal_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD", signal_confidence=0.8, volatility=0.012
        )

        # Reset drawdown for comparison
        drawdown_controller.current_drawdown = 0.01  # 1% drawdown

        low_drawdown_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD", signal_confidence=0.8, volatility=0.012
        )

        # Position should be smaller during higher drawdown
        assert normal_size < low_drawdown_size


class TestRiskLimitEnforcement:
    """Test risk limit checking and enforcement."""

    @pytest.mark.asyncio
    async def test_portfolio_risk_limit_check(self, drawdown_controller):
        """Test portfolio risk limit enforcement."""
        # Setup scenario with high current risk
        drawdown_controller.portfolio_manager.get_current_positions.return_value = [
            {"symbol": "EURUSD", "size": 0.03, "unrealized_pnl": -200},
            {"symbol": "GBPUSD", "size": 0.025, "unrealized_pnl": -150},
            {"symbol": "USDJPY", "size": 0.02, "unrealized_pnl": -100},
        ]

        new_position_risk = PositionRisk(
            symbol="USDCHF", position_size=0.02, max_loss=200.0, volatility=0.015
        )

        # Check if new position exceeds portfolio risk limits
        can_add = await drawdown_controller.check_portfolio_risk_limits(
            new_position_risk
        )

        # Should reject due to high existing risk
        assert not can_add

    @pytest.mark.asyncio
    async def test_daily_loss_limit_check(self, drawdown_controller):
        """Test daily loss limit enforcement."""
        # Setup scenario with high daily losses
        drawdown_controller.portfolio_manager.get_daily_pnl.return_value = (
            -280.0
        )  # -2.8%

        new_position_risk = PositionRisk(
            symbol="EURUSD", position_size=0.015, max_loss=150.0, volatility=0.012
        )

        can_add = await drawdown_controller.check_daily_loss_limits(new_position_risk)

        # Should reject to prevent exceeding daily loss limit
        assert not can_add

    @pytest.mark.asyncio
    async def test_position_concentration_limit(self, drawdown_controller):
        """Test individual position concentration limits."""
        large_position_risk = PositionRisk(
            symbol="EURUSD",
            position_size=0.08,  # 8% - exceeds max individual position
            max_loss=800.0,
            volatility=0.012,
        )

        can_add = await drawdown_controller.check_position_concentration(
            large_position_risk
        )

        assert not can_add

    @pytest.mark.asyncio
    async def test_correlation_risk_check(self, drawdown_controller):
        """Test correlation-based risk limits."""
        # Setup high correlation scenario
        drawdown_controller.portfolio_manager.get_current_positions.return_value = [
            {"symbol": "EURUSD", "size": 0.03, "unrealized_pnl": -100},
            {"symbol": "GBPUSD", "size": 0.025, "unrealized_pnl": -80},
        ]

        # High correlation matrix
        drawdown_controller.volatility_estimator.get_correlation_matrix.return_value = (
            np.array([[1.0, 0.95, 0.9], [0.95, 1.0, 0.92], [0.9, 0.92, 1.0]])
        )

        new_position_risk = PositionRisk(
            symbol="EURGBP",  # Highly correlated with existing positions
            position_size=0.025,
            max_loss=250.0,
            volatility=0.015,
        )

        can_add = await drawdown_controller.check_correlation_limits(new_position_risk)

        # Should reject due to high correlation risk
        assert not can_add


class TestCircuitBreakerMechanism:
    """Test circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_level_1_trigger(self, drawdown_controller):
        """Test Level 1 circuit breaker activation."""
        # Simulate 5.5% drawdown - triggers Level 1
        drawdown_controller.current_drawdown = 0.055

        await drawdown_controller.update_circuit_breaker_state()

        assert drawdown_controller.circuit_breaker_state == CircuitBreakerLevel.LEVEL_1
        assert (
            drawdown_controller.position_size_multiplier <= 0.75
        )  # Reduced position sizing

    @pytest.mark.asyncio
    async def test_circuit_breaker_level_2_trigger(self, drawdown_controller):
        """Test Level 2 circuit breaker activation."""
        # Simulate 12% drawdown - triggers Level 2
        drawdown_controller.current_drawdown = 0.12

        await drawdown_controller.update_circuit_breaker_state()

        assert drawdown_controller.circuit_breaker_state == CircuitBreakerLevel.LEVEL_2
        assert drawdown_controller.position_size_multiplier <= 0.5  # Further reduced

    @pytest.mark.asyncio
    async def test_circuit_breaker_level_3_trigger(self, drawdown_controller):
        """Test Level 3 circuit breaker (trading halt) activation."""
        # Simulate 16% drawdown - triggers Level 3
        drawdown_controller.current_drawdown = 0.16

        await drawdown_controller.update_circuit_breaker_state()

        assert drawdown_controller.circuit_breaker_state == CircuitBreakerLevel.LEVEL_3
        assert drawdown_controller.position_size_multiplier == 0.0  # No new positions
        assert not await drawdown_controller.can_open_new_positions()

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, drawdown_controller):
        """Test circuit breaker recovery mechanism."""
        # Start with Level 2 triggered
        drawdown_controller.current_drawdown = 0.12
        await drawdown_controller.update_circuit_breaker_state()
        assert drawdown_controller.circuit_breaker_state == CircuitBreakerLevel.LEVEL_2

        # Simulate recovery
        drawdown_controller.current_drawdown = 0.06  # Recovered to 6%
        await drawdown_controller.update_circuit_breaker_state()

        # Should move to Level 1
        assert drawdown_controller.circuit_breaker_state == CircuitBreakerLevel.LEVEL_1

        # Further recovery
        drawdown_controller.current_drawdown = 0.03  # Recovered to 3%
        await drawdown_controller.update_circuit_breaker_state()

        # Should be back to normal
        assert drawdown_controller.circuit_breaker_state == CircuitBreakerLevel.NORMAL


class TestDrawdownCalculation:
    """Test drawdown calculation and tracking."""

    @pytest.mark.asyncio
    async def test_current_drawdown_calculation(self, drawdown_controller):
        """Test current drawdown calculation from portfolio history."""
        # Setup portfolio history with peak and current value
        portfolio_values = [10000, 10500, 11000, 10800, 10200, 9800]  # Peak at 11000

        current_drawdown = await drawdown_controller.calculate_current_drawdown(
            current_value=9800, historical_values=portfolio_values
        )

        expected_drawdown = (11000 - 9800) / 11000  # ~10.9%
        assert abs(current_drawdown - expected_drawdown) < 0.01

    @pytest.mark.asyncio
    async def test_maximum_drawdown_tracking(self, drawdown_controller):
        """Test maximum drawdown tracking over time."""
        portfolio_values = [10000, 12000, 8000, 9000, 15000, 7500]

        max_drawdown = await drawdown_controller.calculate_maximum_drawdown(
            portfolio_values
        )

        # Max drawdown should be from 15000 to 7500 = 50%
        expected_max_dd = (15000 - 7500) / 15000
        assert abs(max_drawdown - expected_max_dd) < 0.01

    @pytest.mark.asyncio
    async def test_drawdown_duration_tracking(self, drawdown_controller):
        """Test drawdown duration calculation."""
        # Simulate portfolio in drawdown for extended period
        dates = pd.date_range(start="2024-01-01", periods=30, freq="1D")
        values = [10000] + [9500] * 20 + [10200] * 9  # 20 days in drawdown

        drawdown_duration = await drawdown_controller.calculate_drawdown_duration(
            dates, values
        )

        assert drawdown_duration == 20  # 20 days in drawdown


class TestRiskMetricsCalculation:
    """Test various risk metrics calculations."""

    @pytest.mark.asyncio
    async def test_value_at_risk_calculation(self, drawdown_controller):
        """Test Value at Risk (VaR) calculation."""
        portfolio_returns = np.random.normal(0.001, 0.02, 252)  # 1 year of returns
        confidence_level = 0.95

        var_95 = await drawdown_controller.calculate_var(
            portfolio_returns, confidence_level
        )

        # VaR should be negative (representing potential loss)
        assert var_95 < 0
        # VaR should be reasonable for given volatility
        assert -0.05 < var_95 < -0.01

    @pytest.mark.asyncio
    async def test_expected_shortfall_calculation(self, drawdown_controller):
        """Test Expected Shortfall (Conditional VaR) calculation."""
        portfolio_returns = np.random.normal(0.001, 0.02, 252)
        confidence_level = 0.95

        var_95 = await drawdown_controller.calculate_var(
            portfolio_returns, confidence_level
        )
        es_95 = await drawdown_controller.calculate_expected_shortfall(
            portfolio_returns, confidence_level
        )

        # Expected Shortfall should be more negative than VaR
        assert es_95 < var_95

    @pytest.mark.asyncio
    async def test_portfolio_beta_calculation(self, drawdown_controller):
        """Test portfolio beta calculation against benchmark."""
        portfolio_returns = np.random.normal(0.001, 0.015, 100)
        benchmark_returns = np.random.normal(0.0005, 0.01, 100)

        beta = await drawdown_controller.calculate_portfolio_beta(
            portfolio_returns, benchmark_returns
        )

        # Beta should be reasonable
        assert -2.0 < beta < 3.0

    @pytest.mark.asyncio
    async def test_sharpe_ratio_calculation(self, drawdown_controller):
        """Test Sharpe ratio calculation."""
        portfolio_returns = np.random.normal(
            0.002, 0.015, 252
        )  # Positive expected return
        risk_free_rate = 0.03 / 252  # 3% annual risk-free rate

        sharpe_ratio = await drawdown_controller.calculate_sharpe_ratio(
            portfolio_returns, risk_free_rate
        )

        # Should be positive for profitable strategy
        assert sharpe_ratio > 0
        assert sharpe_ratio < 5.0  # Reasonable upper bound


class TestDynamicRiskAdjustment:
    """Test dynamic risk adjustment mechanisms."""

    @pytest.mark.asyncio
    async def test_volatility_regime_adjustment(self, drawdown_controller):
        """Test risk adjustment based on volatility regime."""
        # Low volatility environment
        drawdown_controller.volatility_estimator.estimate_portfolio_volatility.return_value = (
            0.008
        )

        low_vol_multiplier = (
            await drawdown_controller.get_volatility_adjusted_multiplier()
        )

        # High volatility environment
        drawdown_controller.volatility_estimator.estimate_portfolio_volatility.return_value = (
            0.035
        )

        high_vol_multiplier = (
            await drawdown_controller.get_volatility_adjusted_multiplier()
        )

        # Risk should be reduced in high volatility
        assert high_vol_multiplier < low_vol_multiplier

    @pytest.mark.asyncio
    async def test_performance_based_adjustment(self, drawdown_controller):
        """Test risk adjustment based on recent performance."""
        # Setup recent losing streak
        recent_trades = [
            {"pnl": -150, "date": datetime.now() - timedelta(days=1)},
            {"pnl": -200, "date": datetime.now() - timedelta(days=2)},
            {"pnl": -100, "date": datetime.now() - timedelta(days=3)},
        ]

        losing_multiplier = (
            await drawdown_controller.get_performance_adjusted_multiplier(recent_trades)
        )

        # Setup recent winning streak
        winning_trades = [
            {"pnl": 200, "date": datetime.now() - timedelta(days=1)},
            {"pnl": 150, "date": datetime.now() - timedelta(days=2)},
            {"pnl": 300, "date": datetime.now() - timedelta(days=3)},
        ]

        winning_multiplier = (
            await drawdown_controller.get_performance_adjusted_multiplier(
                winning_trades
            )
        )

        # Risk should be reduced after losses
        assert losing_multiplier < winning_multiplier

    @pytest.mark.asyncio
    async def test_correlation_adjustment(self, drawdown_controller):
        """Test risk adjustment based on portfolio correlation."""
        # High correlation scenario
        high_corr_matrix = np.array(
            [[1.0, 0.9, 0.85], [0.9, 1.0, 0.88], [0.85, 0.88, 1.0]]
        )

        high_corr_multiplier = (
            await drawdown_controller.get_correlation_adjusted_multiplier(
                high_corr_matrix
            )
        )

        # Low correlation scenario
        low_corr_matrix = np.array(
            [[1.0, 0.2, 0.1], [0.2, 1.0, 0.15], [0.1, 0.15, 1.0]]
        )

        low_corr_multiplier = (
            await drawdown_controller.get_correlation_adjusted_multiplier(
                low_corr_matrix
            )
        )

        # Risk should be reduced when correlations are high
        assert high_corr_multiplier < low_corr_multiplier


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_missing_portfolio_data_handling(self, drawdown_controller):
        """Test graceful handling of missing portfolio data."""
        drawdown_controller.portfolio_manager.get_total_portfolio_value.side_effect = (
            Exception("Data unavailable")
        )

        # Should use fallback methods
        position_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD", signal_confidence=0.8, volatility=0.012
        )

        # Should return conservative position size
        assert 0 < position_size <= drawdown_controller.min_position_size * 2

    @pytest.mark.asyncio
    async def test_extreme_volatility_handling(self, drawdown_controller):
        """Test handling of extreme volatility scenarios."""
        # Test extremely high volatility
        position_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD",
            signal_confidence=0.8,
            volatility=0.15,  # 15% daily volatility - extreme
        )

        # Should result in minimal position size
        assert position_size == drawdown_controller.min_position_size

    @pytest.mark.asyncio
    async def test_negative_portfolio_value_handling(self, drawdown_controller):
        """Test handling of negative portfolio values."""
        drawdown_controller.portfolio_manager.get_total_portfolio_value.return_value = (
            -1000.0
        )

        # Should prevent any new positions
        can_trade = await drawdown_controller.can_open_new_positions()
        assert not can_trade

    @pytest.mark.asyncio
    async def test_division_by_zero_protection(self, drawdown_controller):
        """Test protection against division by zero in calculations."""
        # Test with zero volatility
        position_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD", signal_confidence=0.8, volatility=0.0  # Zero volatility
        )

        # Should use default position size
        assert position_size == drawdown_controller.position_size_base


@pytest.mark.performance
class TestPerformanceRequirements:
    """Test performance requirements for risk calculations."""

    @pytest.mark.asyncio
    async def test_position_sizing_speed(self, drawdown_controller):
        """Test position sizing calculation speed."""
        import time

        start_time = time.time()
        position_size = await drawdown_controller.calculate_position_size(
            symbol="EURUSD", signal_confidence=0.8, volatility=0.012
        )
        end_time = time.time()

        execution_time = end_time - start_time
        assert execution_time < 0.1, f"Position sizing took {execution_time:.3f}s"

    @pytest.mark.asyncio
    async def test_risk_limit_check_speed(self, drawdown_controller):
        """Test risk limit checking speed."""
        import time

        position_risk = PositionRisk(
            symbol="EURUSD", position_size=0.02, max_loss=200.0, volatility=0.012
        )

        start_time = time.time()
        can_add = await drawdown_controller.check_all_risk_limits(position_risk)
        end_time = time.time()

        execution_time = end_time - start_time
        assert execution_time < 0.2, f"Risk checking took {execution_time:.3f}s"
