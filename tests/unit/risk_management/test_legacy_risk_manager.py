"""Tests for legacy risk management system.

This module tests the deprecated risk_manager.py for backward compatibility
and migration support.
"""

import warnings
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Import with deprecation warning suppression for testing
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from fxml4.risk_management.risk_manager import RiskConfig, RiskManager


class TestRiskConfig:
    """Test RiskConfig data class."""

    def test_default_risk_config(self):
        """Test default risk configuration."""
        config = RiskConfig()

        assert config.max_position_size == 0.1  # 10%
        assert config.max_portfolio_risk == 0.06  # 6%
        assert config.max_correlation == 0.7
        assert config.max_daily_loss == 0.03  # 3%
        assert config.max_drawdown == 0.15  # 15%
        assert config.min_risk_reward == 1.5
        assert config.use_trailing_stop is True
        assert config.trailing_stop_distance == 0.02  # 2%
        assert config.max_leverage == 1.0
        assert config.position_sizing_method == "fixed_risk"

    def test_custom_risk_config(self):
        """Test custom risk configuration."""
        config = RiskConfig(
            max_position_size=0.05,
            max_daily_loss=0.02,
            use_trailing_stop=False,
            position_sizing_method="kelly",
        )

        assert config.max_position_size == 0.05
        assert config.max_daily_loss == 0.02
        assert config.use_trailing_stop is False
        assert config.position_sizing_method == "kelly"


class TestRiskManager:
    """Test legacy RiskManager class."""

    @pytest.fixture
    def risk_manager(self):
        """Create a risk manager with default config."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return RiskManager()

    @pytest.fixture
    def custom_risk_manager(self):
        """Create a risk manager with custom config."""
        config = RiskConfig(
            max_position_size=0.05,
            max_daily_loss=0.02,
            position_sizing_method="volatility",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return RiskManager(config)

    def test_initialization(self, risk_manager):
        """Test risk manager initialization."""
        assert isinstance(risk_manager.config, RiskConfig)
        assert risk_manager.positions == {}
        assert risk_manager.daily_pnl == []
        assert risk_manager.peak_portfolio_value == 0
        assert risk_manager.current_portfolio_value == 0

    def test_initialization_with_custom_config(self, custom_risk_manager):
        """Test initialization with custom config."""
        assert custom_risk_manager.config.max_position_size == 0.05
        assert custom_risk_manager.config.max_daily_loss == 0.02
        assert custom_risk_manager.config.position_sizing_method == "volatility"

    def test_deprecation_warning(self):
        """Test that deprecation warning is raised."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from fxml4.risk_management.risk_manager import RiskManager

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message)

    def test_validate_trade_success(self, risk_manager):
        """Test successful trade validation."""
        is_valid, reason = risk_manager.validate_trade(
            symbol="EURUSD",
            side="BUY",
            quantity=50000,
            price=1.1000,
            account_balance=100000.0,
            current_positions={},
        )

        assert is_valid is True
        assert reason == "Trade validated"

    def test_validate_trade_position_size_exceeded(self, risk_manager):
        """Test trade validation with position size exceeded."""
        is_valid, reason = risk_manager.validate_trade(
            symbol="EURUSD",
            side="BUY",
            quantity=200000,  # Large position: 200k * 1.1 = 220k > 10k limit
            price=1.1000,
            account_balance=100000.0,
            current_positions={},
        )

        assert is_valid is False
        assert "Position size exceeds limit" in reason

    def test_validate_trade_daily_loss_exceeded(self, risk_manager):
        """Test trade validation with daily loss limit exceeded."""
        # Set up daily loss history
        risk_manager.daily_pnl = [(datetime.now(), -3500.0)]  # 3.5% loss
        risk_manager.current_portfolio_value = 100000.0

        is_valid, reason = risk_manager.validate_trade(
            symbol="EURUSD",
            side="BUY",
            quantity=50000,
            price=1.1000,
            account_balance=100000.0,
            current_positions={},
        )

        assert is_valid is False
        assert reason == "Daily loss limit exceeded"

    def test_validate_trade_max_drawdown_exceeded(self, risk_manager):
        """Test trade validation with max drawdown exceeded."""
        risk_manager.peak_portfolio_value = 100000.0
        risk_manager.current_portfolio_value = 80000.0  # 20% drawdown > 15% limit

        is_valid, reason = risk_manager.validate_trade(
            symbol="EURUSD",
            side="BUY",
            quantity=50000,
            price=1.1000,
            account_balance=100000.0,
            current_positions={},
        )

        assert is_valid is False
        assert reason == "Maximum drawdown limit exceeded"

    def test_validate_trade_correlation_exceeded(self, risk_manager):
        """Test trade validation with correlation limit exceeded."""
        current_positions = {
            "GBPUSD": {"side": "BUY", "quantity": 100000},
            "EURGBP": {"side": "SELL", "quantity": 50000},
        }

        is_valid, reason = risk_manager.validate_trade(
            symbol="EURUSD",  # Correlated with GBP pairs
            side="BUY",
            quantity=50000,
            price=1.1000,
            account_balance=100000.0,
            current_positions=current_positions,
        )

        assert is_valid is False
        assert "correlation exceeds limit" in reason

    def test_calculate_position_size_fixed_risk(self, risk_manager):
        """Test position size calculation with fixed risk method."""
        position_size = risk_manager.calculate_position_size(
            symbol="EURUSD",
            signal_strength=0.8,
            account_balance=100000.0,
            current_price=1.1000,
            stop_loss=1.0950,
            volatility=0.01,
        )

        # Risk amount = 100000 * 0.02 = 2000
        # Price risk = 1.1000 - 1.0950 = 0.005
        # Position size = 2000 / 0.005 = 400000
        # But capped at max position size: 100000 * 0.1 / 1.1 = 9090.9

        assert position_size > 0
        assert position_size <= 100000 * risk_manager.config.max_position_size / 1.1000

    def test_calculate_position_size_kelly(self, custom_risk_manager):
        """Test position size calculation with Kelly criterion."""
        custom_risk_manager.config.position_sizing_method = "kelly"

        position_size = custom_risk_manager.calculate_position_size(
            symbol="EURUSD",
            signal_strength=0.6,  # 60% win probability
            account_balance=100000.0,
            current_price=1.1000,
            stop_loss=1.0950,
            volatility=0.01,
        )

        assert position_size > 0
        # Kelly with 60% win rate should give reasonable position size
        max_allowed = 100000.0 * 0.25 / 1.1000  # 25% max Kelly position
        assert position_size <= max_allowed

    def test_calculate_position_size_volatility(self, custom_risk_manager):
        """Test position size calculation with volatility method."""
        custom_risk_manager.config.position_sizing_method = "volatility"

        position_size = custom_risk_manager.calculate_position_size(
            symbol="EURUSD",
            signal_strength=0.7,
            account_balance=100000.0,
            current_price=1.1000,
            stop_loss=1.0950,
            volatility=0.02,  # 2% volatility
        )

        assert position_size > 0
        # Target 1% portfolio volatility / 2% asset volatility = 0.5 weight
        expected_weight = min(0.01 / 0.02, custom_risk_manager.config.max_position_size)
        expected_position = 100000.0 * expected_weight / 1.1000

        assert (
            abs(position_size - expected_position) < 100
        )  # Allow small rounding differences

    def test_calculate_position_size_zero_stop_loss(self, risk_manager):
        """Test position size calculation with zero stop loss distance."""
        position_size = risk_manager.calculate_position_size(
            symbol="EURUSD",
            signal_strength=0.8,
            account_balance=100000.0,
            current_price=1.1000,
            stop_loss=1.1000,  # Same as current price
            volatility=0.01,
        )

        assert position_size == 0  # Should return 0 for zero risk distance

    def test_update_stop_loss_trailing_long(self, risk_manager):
        """Test trailing stop loss update for long position."""
        position = {"entry_price": 1.1000, "stop_loss": 1.0950, "side": "BUY"}

        # Price moves up - should update trailing stop
        new_stop = risk_manager.update_stop_loss("EURUSD", 1.1100, position)
        expected_stop = 1.1100 * (1 - 0.02)  # 2% trailing distance

        assert new_stop == expected_stop

        # Price moves down - should not update stop
        new_stop = risk_manager.update_stop_loss("EURUSD", 1.1050, position)
        assert new_stop == expected_stop  # Should stay at previous higher level

    def test_update_stop_loss_trailing_short(self, risk_manager):
        """Test trailing stop loss update for short position."""
        position = {
            "entry_price": 1.1000,
            "stop_loss": 0,  # Not set initially
            "side": "SELL",
        }

        # Price moves down - should set/update trailing stop
        new_stop = risk_manager.update_stop_loss("EURUSD", 1.0950, position)
        expected_stop = 1.0950 * (1 + 0.02)  # 2% trailing distance above price

        assert new_stop == expected_stop

        # Update position and test further movement
        position["stop_loss"] = new_stop
        new_stop = risk_manager.update_stop_loss("EURUSD", 1.0900, position)
        expected_stop2 = 1.0900 * (1 + 0.02)

        assert new_stop == expected_stop2

    def test_update_stop_loss_disabled(self, risk_manager):
        """Test stop loss update when trailing stop is disabled."""
        risk_manager.config.use_trailing_stop = False

        position = {"entry_price": 1.1000, "stop_loss": 1.0950, "side": "BUY"}

        new_stop = risk_manager.update_stop_loss("EURUSD", 1.1100, position)
        assert new_stop == 1.0950  # Should remain unchanged

    def test_update_portfolio_value(self, risk_manager):
        """Test portfolio value update."""
        risk_manager.update_portfolio_value(100000.0)
        assert risk_manager.current_portfolio_value == 100000.0
        assert risk_manager.peak_portfolio_value == 100000.0

        # Update with higher value
        risk_manager.update_portfolio_value(105000.0)
        assert risk_manager.current_portfolio_value == 105000.0
        assert risk_manager.peak_portfolio_value == 105000.0

        # Update with lower value (peak should remain)
        risk_manager.update_portfolio_value(102000.0)
        assert risk_manager.current_portfolio_value == 102000.0
        assert risk_manager.peak_portfolio_value == 105000.0

    def test_add_daily_pnl(self, risk_manager):
        """Test adding daily P&L entries."""
        risk_manager.add_daily_pnl(500.0)
        risk_manager.add_daily_pnl(-200.0)

        assert len(risk_manager.daily_pnl) == 2
        assert risk_manager.daily_pnl[0][1] == 500.0
        assert risk_manager.daily_pnl[1][1] == -200.0

        # Verify timestamps are datetime objects
        assert isinstance(risk_manager.daily_pnl[0][0], datetime)
        assert isinstance(risk_manager.daily_pnl[1][0], datetime)

    def test_add_daily_pnl_cleanup(self, risk_manager):
        """Test that old P&L entries are cleaned up."""
        # Add old entries
        old_date = datetime.now() - timedelta(days=40)
        risk_manager.daily_pnl = [(old_date, -1000.0)]

        # Add new entry - should trigger cleanup
        risk_manager.add_daily_pnl(100.0)

        # Old entry should be removed
        assert len(risk_manager.daily_pnl) == 1
        assert risk_manager.daily_pnl[0][1] == 100.0

    def test_get_risk_metrics(self, risk_manager):
        """Test risk metrics calculation."""
        # Set up risk manager state
        risk_manager.peak_portfolio_value = 105000.0
        risk_manager.current_portfolio_value = 100000.0
        risk_manager.positions = {
            "EURUSD": {"quantity": 100000, "current_price": 1.1000}
        }
        risk_manager.daily_pnl = [(datetime.now(), 200.0), (datetime.now(), -150.0)]

        metrics = risk_manager.get_risk_metrics()

        assert metrics["current_drawdown"] == (105000.0 - 100000.0) / 105000.0
        assert metrics["daily_pnl"] == 50.0  # 200 - 150
        assert metrics["portfolio_risk"] > 0
        assert metrics["position_count"] == 1
        assert metrics["peak_value"] == 105000.0
        assert metrics["current_value"] == 100000.0

    def test_check_daily_loss_exceeded(self, risk_manager):
        """Test daily loss limit check."""
        risk_manager.current_portfolio_value = 100000.0

        # Add today's P&L that exceeds limit
        today = datetime.now()
        risk_manager.daily_pnl = [
            (today, -2000.0),  # 2% loss
            (today, -1500.0),  # 1.5% loss
            # Total: 3.5% loss > 3% limit
        ]

        assert risk_manager._check_daily_loss_exceeded() is True

        # Test within limit
        risk_manager.daily_pnl = [(today, -2000.0)]  # 2% loss < 3% limit
        assert risk_manager._check_daily_loss_exceeded() is False

    def test_check_max_drawdown_exceeded(self, risk_manager):
        """Test maximum drawdown check."""
        risk_manager.peak_portfolio_value = 100000.0

        # Test drawdown within limit
        risk_manager.current_portfolio_value = 88000.0  # 12% drawdown < 15% limit
        assert risk_manager._check_max_drawdown_exceeded() is False

        # Test drawdown exceeding limit
        risk_manager.current_portfolio_value = 80000.0  # 20% drawdown > 15% limit
        assert risk_manager._check_max_drawdown_exceeded() is True

        # Test no peak set
        risk_manager.peak_portfolio_value = 0
        assert risk_manager._check_max_drawdown_exceeded() is False

    def test_calculate_portfolio_risk(self, risk_manager):
        """Test portfolio risk calculation."""
        positions = {
            "EURUSD": {"quantity": 100000, "current_price": 1.1000},
            "GBPUSD": {"quantity": 50000, "current_price": 1.3000},
        }

        total_risk = risk_manager._calculate_portfolio_risk(positions)

        # Each position has 2% price risk
        expected_risk = (100000 * 1.1000 * 0.02) + (50000 * 1.3000 * 0.02)
        assert total_risk == expected_risk

    def test_calculate_position_risk(self, risk_manager):
        """Test individual position risk calculation."""
        risk = risk_manager._calculate_position_risk(100000, 1.1000)
        expected_risk = 100000 * 1.1000 * 0.02  # 2% price risk

        assert risk == expected_risk

    def test_check_correlation_limits(self, risk_manager):
        """Test correlation limits checking."""
        # Test no correlation issue
        positions = {"USDJPY": {}}
        assert risk_manager._check_correlation_limits("EURUSD", positions) is True

        # Test correlation limit exceeded
        positions = {"GBPUSD": {}, "EURGBP": {}}
        # EURUSD is correlated with both GBPUSD and EURGBP
        assert risk_manager._check_correlation_limits("EURUSD", positions) is False

        # Test unknown symbol
        assert risk_manager._check_correlation_limits("UNKNOWN", positions) is True


@pytest.mark.unit
class TestRiskManagerIntegration:
    """Integration tests for legacy risk manager."""

    def test_complete_trading_workflow(self):
        """Test complete trading workflow with risk management."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            risk_manager = RiskManager()

        # 1. Calculate position size
        position_size = risk_manager.calculate_position_size(
            symbol="EURUSD",
            signal_strength=0.7,
            account_balance=100000.0,
            current_price=1.1000,
            stop_loss=1.0950,
        )

        assert position_size > 0

        # 2. Validate trade
        is_valid, reason = risk_manager.validate_trade(
            symbol="EURUSD",
            side="BUY",
            quantity=position_size,
            price=1.1000,
            account_balance=100000.0,
            current_positions={},
        )

        assert is_valid is True

        # 3. Update portfolio value
        risk_manager.update_portfolio_value(100000.0)

        # 4. Add position and update metrics
        position = {
            "entry_price": 1.1000,
            "stop_loss": 1.0950,
            "side": "BUY",
            "quantity": position_size,
            "current_price": 1.1050,
        }

        # 5. Update trailing stop
        new_stop = risk_manager.update_stop_loss("EURUSD", 1.1050, position)
        assert new_stop >= position["stop_loss"]

        # 6. Add P&L and check metrics
        risk_manager.add_daily_pnl(500.0)
        metrics = risk_manager.get_risk_metrics()

        assert metrics["daily_pnl"] == 500.0
        assert metrics["current_value"] == 100000.0


@pytest.mark.performance
def test_risk_manager_performance():
    """Test risk manager performance with multiple operations."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        risk_manager = RiskManager()

    start_time = datetime.now()

    # Perform 1000 validations
    for i in range(1000):
        risk_manager.validate_trade(
            symbol=f"PAIR{i % 10}",
            side="BUY" if i % 2 == 0 else "SELL",
            quantity=10000,
            price=1.0000 + (i % 100) * 0.0001,
            account_balance=100000.0,
            current_positions={},
        )

    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()

    # Should complete in under 2 seconds
    assert execution_time < 2.0
