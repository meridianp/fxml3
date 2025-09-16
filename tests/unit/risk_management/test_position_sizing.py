"""Tests for position sizing strategies."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.risk_management.position_sizing import KellyCriterionSizer, PositionSizer


class MockPositionSizer(PositionSizer):
    """Mock implementation of PositionSizer for testing."""

    def calculate_size(
        self, signal, account_balance, current_price, market_conditions=None
    ):
        """Mock implementation that returns fixed size."""
        return 10000.0  # Fixed size for testing


class TestPositionSizer:
    """Test base PositionSizer abstract class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that abstract PositionSizer cannot be instantiated directly."""
        with pytest.raises(TypeError):
            PositionSizer()

    def test_mock_implementation(self):
        """Test mock implementation works correctly."""
        sizer = MockPositionSizer()

        signal = {"strength": 0.8, "direction": "buy"}
        size = sizer.calculate_size(
            signal=signal, account_balance=100000.0, current_price=1.1000
        )

        assert size == 10000.0


class TestKellyCriterionSizer:
    """Test Kelly Criterion position sizing."""

    @pytest.fixture
    def kelly_sizer(self):
        """Create Kelly criterion sizer with default parameters."""
        return KellyCriterionSizer(
            win_rate=0.55, avg_win_loss_ratio=1.5, kelly_fraction=0.25
        )

    @pytest.fixture
    def conservative_kelly_sizer(self):
        """Create conservative Kelly criterion sizer."""
        return KellyCriterionSizer(
            win_rate=0.6,
            avg_win_loss_ratio=2.0,
            kelly_fraction=0.1,  # Very conservative
        )

    def test_initialization(self, kelly_sizer):
        """Test Kelly sizer initialization."""
        assert kelly_sizer.win_rate == 0.55
        assert kelly_sizer.avg_win_loss_ratio == 1.5
        assert kelly_sizer.kelly_fraction == 0.25

    def test_calculate_size_basic(self, kelly_sizer):
        """Test basic position size calculation."""
        signal = {"strength": 0.8, "direction": "buy", "confidence": 0.7}

        size = kelly_sizer.calculate_size(
            signal=signal, account_balance=100000.0, current_price=1.1000
        )

        # Kelly formula: f = p - q/b where p=0.55, q=0.45, b=1.5
        # f = 0.55 - 0.45/1.5 = 0.55 - 0.3 = 0.25
        # With kelly_fraction=0.25: f = 0.25 * 0.25 = 0.0625
        # Position value = 100000 * 0.0625 = 6250
        # Position size = 6250 / 1.1 = 5681.8

        assert size > 0
        assert size < 100000  # Should be reasonable portion of balance
        expected_size = (100000 * 0.25 * 0.25) / 1.1000
        assert abs(size - expected_size) < 100  # Allow for small differences

    def test_calculate_size_with_signal_strength(self, kelly_sizer):
        """Test position size with different signal strengths."""
        base_signal = {"direction": "buy", "confidence": 0.7}

        # Strong signal
        strong_signal = {**base_signal, "strength": 0.9}
        strong_size = kelly_sizer.calculate_size(
            signal=strong_signal, account_balance=100000.0, current_price=1.1000
        )

        # Weak signal
        weak_signal = {**base_signal, "strength": 0.3}
        weak_size = kelly_sizer.calculate_size(
            signal=weak_signal, account_balance=100000.0, current_price=1.1000
        )

        # Strong signal should result in larger position
        assert strong_size > weak_size

    def test_calculate_size_conservative_parameters(self, conservative_kelly_sizer):
        """Test position sizing with conservative parameters."""
        signal = {"strength": 0.8, "direction": "buy"}

        size = conservative_kelly_sizer.calculate_size(
            signal=signal, account_balance=100000.0, current_price=1.1000
        )

        # Conservative sizer should produce smaller positions
        # Kelly: f = 0.6 - 0.4/2.0 = 0.6 - 0.2 = 0.4
        # With fraction=0.1: f = 0.4 * 0.1 = 0.04
        expected_size = (100000 * 0.4 * 0.1) / 1.1000
        assert abs(size - expected_size) < 50

    def test_calculate_size_negative_kelly(self):
        """Test position sizing when Kelly criterion is negative."""
        # Set up parameters that would give negative Kelly
        sizer = KellyCriterionSizer(
            win_rate=0.4,  # Low win rate
            avg_win_loss_ratio=1.0,  # Even win/loss ratio
            kelly_fraction=0.25,
        )

        signal = {"strength": 0.8, "direction": "buy"}
        size = sizer.calculate_size(
            signal=signal, account_balance=100000.0, current_price=1.1000
        )

        # Should return 0 for negative Kelly
        assert size == 0

    def test_calculate_size_with_market_conditions(self, kelly_sizer):
        """Test position sizing with market conditions."""
        signal = {"strength": 0.7, "direction": "buy"}

        # High volatility market conditions
        high_vol_conditions = {
            "volatility": 0.05,  # 5% volatility
            "market_regime": "high_volatility",
        }

        high_vol_size = kelly_sizer.calculate_size(
            signal=signal,
            account_balance=100000.0,
            current_price=1.1000,
            market_conditions=high_vol_conditions,
        )

        # Low volatility market conditions
        low_vol_conditions = {
            "volatility": 0.01,  # 1% volatility
            "market_regime": "low_volatility",
        }

        low_vol_size = kelly_sizer.calculate_size(
            signal=signal,
            account_balance=100000.0,
            current_price=1.1000,
            market_conditions=low_vol_conditions,
        )

        # Should adjust for volatility (high vol = smaller position)
        assert high_vol_size <= low_vol_size

    def test_calculate_size_different_prices(self, kelly_sizer):
        """Test position sizing with different asset prices."""
        signal = {"strength": 0.7, "direction": "buy"}
        account_balance = 100000.0

        # High-priced asset
        high_price_size = kelly_sizer.calculate_size(
            signal=signal, account_balance=account_balance, current_price=2.0000
        )

        # Low-priced asset
        low_price_size = kelly_sizer.calculate_size(
            signal=signal, account_balance=account_balance, current_price=1.0000
        )

        # For same dollar allocation, should get fewer units of higher-priced asset
        assert high_price_size < low_price_size

        # But dollar values should be similar
        high_price_value = high_price_size * 2.0000
        low_price_value = low_price_size * 1.0000
        assert (
            abs(high_price_value - low_price_value) < 1000
        )  # Allow for small differences

    def test_kelly_formula_calculation(self, kelly_sizer):
        """Test the underlying Kelly formula calculation."""
        # Test the Kelly calculation directly
        win_rate = 0.6
        avg_win_loss_ratio = 2.0

        # Kelly formula: f = p - q/b
        loss_rate = 1 - win_rate  # q = 0.4
        kelly_optimal = win_rate - (loss_rate / avg_win_loss_ratio)
        # kelly_optimal = 0.6 - 0.4/2.0 = 0.6 - 0.2 = 0.4

        assert kelly_optimal == 0.4

        # With safety fraction
        kelly_fraction = 0.25
        safe_kelly = kelly_optimal * kelly_fraction
        assert safe_kelly == 0.1  # 0.4 * 0.25 = 0.1

    def test_position_size_limits(self, kelly_sizer):
        """Test that position sizes respect reasonable limits."""
        signal = {"strength": 1.0, "direction": "buy"}  # Maximum strength

        size = kelly_sizer.calculate_size(
            signal=signal, account_balance=100000.0, current_price=1.1000
        )

        position_value = size * 1.1000
        position_percentage = position_value / 100000.0

        # Even with maximum signal strength, should not exceed reasonable limits
        assert position_percentage <= 0.5  # Max 50% of account
        assert position_percentage >= 0.0  # Should be positive

    def test_edge_cases(self, kelly_sizer):
        """Test edge cases and error handling."""
        signal = {"strength": 0.7, "direction": "buy"}

        # Zero account balance
        size = kelly_sizer.calculate_size(
            signal=signal, account_balance=0.0, current_price=1.1000
        )
        assert size == 0

        # Zero price (should not crash)
        with pytest.raises((ZeroDivisionError, ValueError)):
            kelly_sizer.calculate_size(
                signal=signal, account_balance=100000.0, current_price=0.0
            )

        # Negative account balance
        size = kelly_sizer.calculate_size(
            signal=signal, account_balance=-10000.0, current_price=1.1000
        )
        assert size == 0  # Should handle gracefully

    def test_signal_strength_modulation(self, kelly_sizer):
        """Test how signal strength modulates position size."""
        base_signal = {"direction": "buy"}
        account_balance = 100000.0
        current_price = 1.1000

        # Test different signal strengths
        strengths = [0.1, 0.3, 0.5, 0.7, 0.9]
        sizes = []

        for strength in strengths:
            signal = {**base_signal, "strength": strength}
            size = kelly_sizer.calculate_size(
                signal=signal,
                account_balance=account_balance,
                current_price=current_price,
            )
            sizes.append(size)

        # Sizes should generally increase with signal strength
        for i in range(1, len(sizes)):
            assert (
                sizes[i] >= sizes[i - 1]
            ), f"Size decreased from {sizes[i-1]} to {sizes[i]} at strength {strengths[i]}"


@pytest.mark.unit
class TestPositionSizingIntegration:
    """Integration tests for position sizing."""

    def test_multiple_sizers_comparison(self):
        """Test comparison between different sizer configurations."""
        # Conservative sizer
        conservative = KellyCriterionSizer(
            win_rate=0.55,
            avg_win_loss_ratio=1.5,
            kelly_fraction=0.1,  # Very conservative
        )

        # Aggressive sizer
        aggressive = KellyCriterionSizer(
            win_rate=0.6, avg_win_loss_ratio=2.0, kelly_fraction=0.5  # More aggressive
        )

        signal = {"strength": 0.8, "direction": "buy"}
        account_balance = 100000.0
        current_price = 1.1000

        conservative_size = conservative.calculate_size(
            signal, account_balance, current_price
        )
        aggressive_size = aggressive.calculate_size(
            signal, account_balance, current_price
        )

        # Aggressive sizer should produce larger positions
        assert aggressive_size > conservative_size

        # Both should be reasonable
        assert conservative_size > 0
        assert aggressive_size > 0
        assert (
            aggressive_size < account_balance / current_price
        )  # Should not exceed full account

    def test_portfolio_allocation_scenario(self):
        """Test position sizing in a portfolio context."""
        kelly_sizer = KellyCriterionSizer(win_rate=0.58, avg_win_loss_ratio=1.8)

        # Portfolio with multiple signals
        signals = [
            {"strength": 0.9, "direction": "buy", "symbol": "EURUSD"},
            {"strength": 0.7, "direction": "sell", "symbol": "GBPUSD"},
            {"strength": 0.5, "direction": "buy", "symbol": "USDJPY"},
        ]

        prices = {"EURUSD": 1.1000, "GBPUSD": 1.3000, "USDJPY": 110.00}
        account_balance = 100000.0

        total_allocation = 0
        position_sizes = {}

        for signal in signals:
            symbol = signal["symbol"]
            size = kelly_sizer.calculate_size(
                signal=signal,
                account_balance=account_balance,
                current_price=prices[symbol],
            )

            position_value = size * prices[symbol]
            position_sizes[symbol] = size
            total_allocation += position_value

        # Total allocation should be reasonable (not exceed account balance significantly)
        assert total_allocation <= account_balance * 1.5  # Allow for some leverage

        # Strongest signal should get largest allocation
        eurusd_value = position_sizes["EURUSD"] * prices["EURUSD"]
        gbpusd_value = position_sizes["GBPUSD"] * prices["GBPUSD"]
        usdjpy_value = position_sizes["USDJPY"] * prices["USDJPY"]

        assert eurusd_value >= gbpusd_value  # Stronger signal gets more
        assert gbpusd_value >= usdjpy_value  # Medium signal gets more than weak


@pytest.mark.performance
def test_position_sizer_performance():
    """Test position sizer performance with many calculations."""
    kelly_sizer = KellyCriterionSizer()

    import time

    start_time = time.time()

    # Perform 10000 position size calculations
    for i in range(10000):
        signal = {
            "strength": 0.5 + 0.4 * (i % 100) / 100.0,  # Vary between 0.5-0.9
            "direction": "buy" if i % 2 == 0 else "sell",
        }

        size = kelly_sizer.calculate_size(
            signal=signal,
            account_balance=100000.0,
            current_price=1.0 + (i % 1000) * 0.001,  # Vary price
        )

        assert size >= 0  # Basic sanity check

    end_time = time.time()
    execution_time = end_time - start_time

    # Should complete 10k calculations in under 1 second
    assert execution_time < 1.0
