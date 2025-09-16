"""
Property-based testing for financial calculations.

Tests mathematical properties and invariants of financial calculations
using Hypothesis to generate comprehensive test cases following TDD methodology.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, assume, example, given, settings
from hypothesis import strategies as st

# Test categories
pytestmark = [
    pytest.mark.property_based,
    pytest.mark.financial,
    pytest.mark.calculations,
]


class FinancialCalculator:
    """Financial calculation utilities for testing."""

    @staticmethod
    def calculate_pnl(
        entry_price: float, exit_price: float, quantity: float, is_long: bool = True
    ) -> float:
        """Calculate profit/loss for a trade."""
        if is_long:
            return (exit_price - entry_price) * quantity
        else:
            return (entry_price - exit_price) * quantity

    @staticmethod
    def calculate_pnl_decimal(
        entry_price: Decimal,
        exit_price: Decimal,
        quantity: Decimal,
        is_long: bool = True,
    ) -> Decimal:
        """Calculate profit/loss using Decimal for precision."""
        if is_long:
            return (exit_price - entry_price) * quantity
        else:
            return (entry_price - exit_price) * quantity

    @staticmethod
    def calculate_percentage_return(initial_value: float, final_value: float) -> float:
        """Calculate percentage return."""
        if initial_value == 0:
            return 0.0
        return ((final_value - initial_value) / initial_value) * 100

    @staticmethod
    def convert_currency(amount: float, exchange_rate: float) -> float:
        """Convert currency using exchange rate."""
        return amount * exchange_rate

    @staticmethod
    def compound_interest(principal: float, rate: float, periods: int) -> float:
        """Calculate compound interest."""
        if rate <= -1:  # Prevent negative or zero base
            return 0.0
        return principal * ((1 + rate) ** periods)

    @staticmethod
    def position_size(
        account_balance: float,
        risk_percentage: float,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """Calculate position size based on risk management."""
        if entry_price == stop_loss or entry_price <= 0 or stop_loss <= 0:
            return 0.0

        risk_amount = account_balance * (risk_percentage / 100)
        price_diff = abs(entry_price - stop_loss)

        if price_diff == 0:
            return 0.0

        return risk_amount / price_diff

    @staticmethod
    def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio."""
        if not returns or len(returns) < 2:
            return 0.0

        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate

        if np.std(excess_returns) == 0:
            return 0.0

        return np.mean(excess_returns) / np.std(excess_returns)

    @staticmethod
    def max_drawdown(equity_curve: List[float]) -> float:
        """Calculate maximum drawdown."""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value

            drawdown = (peak - value) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, drawdown)

        return max_dd

    @staticmethod
    def round_to_pip(price: float, pip_size: float = 0.0001) -> float:
        """Round price to pip precision."""
        if pip_size <= 0:
            return price
        return round(price / pip_size) * pip_size


# Strategy definitions for Hypothesis
@st.composite
def currency_prices(draw):
    """Generate realistic currency prices."""
    return draw(
        st.floats(
            min_value=0.0001, max_value=10.0, allow_nan=False, allow_infinity=False
        )
    )


@st.composite
def trade_quantities(draw):
    """Generate realistic trade quantities."""
    return draw(
        st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        )
    )


@st.composite
def percentage_values(draw):
    """Generate percentage values (0-100)."""
    return draw(
        st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )


@st.composite
def account_balances(draw):
    """Generate realistic account balances."""
    return draw(
        st.floats(
            min_value=100.0, max_value=1000000.0, allow_nan=False, allow_infinity=False
        )
    )


@st.composite
def exchange_rates(draw):
    """Generate realistic exchange rates."""
    return draw(
        st.floats(
            min_value=0.0001, max_value=1000.0, allow_nan=False, allow_infinity=False
        )
    )


@st.composite
def interest_rates(draw):
    """Generate realistic interest rates (-50% to +50%)."""
    return draw(
        st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False)
    )


@st.composite
def time_periods(draw):
    """Generate time periods for compound interest."""
    return draw(st.integers(min_value=1, max_value=100))


@st.composite
def returns_list(draw):
    """Generate list of returns for Sharpe ratio calculation."""
    length = draw(st.integers(min_value=2, max_value=1000))
    return draw(
        st.lists(
            st.floats(
                min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False
            ),
            min_size=length,
            max_size=length,
        )
    )


@st.composite
def equity_curve(draw):
    """Generate equity curve for drawdown calculation."""
    length = draw(st.integers(min_value=2, max_value=1000))
    initial_value = draw(st.floats(min_value=1000.0, max_value=100000.0))

    values = [initial_value]
    for _ in range(length - 1):
        change = draw(st.floats(min_value=-0.1, max_value=0.1))  # ±10% change
        new_value = max(0.01, values[-1] * (1 + change))  # Prevent negative values
        values.append(new_value)

    return values


class TestPnLCalculationProperties:
    """Test properties of P&L calculations."""

    @given(
        entry_price=currency_prices(),
        exit_price=currency_prices(),
        quantity=trade_quantities(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pnl_sign_consistency(self, entry_price, exit_price, quantity):
        """Test that P&L sign is consistent with price direction."""
        assume(quantity > 0)
        assume(abs(entry_price - exit_price) > 0.0001)  # Avoid near-zero differences

        long_pnl = FinancialCalculator.calculate_pnl(
            entry_price, exit_price, quantity, is_long=True
        )
        short_pnl = FinancialCalculator.calculate_pnl(
            entry_price, exit_price, quantity, is_long=False
        )

        # Long position profits when exit > entry
        if exit_price > entry_price:
            assert (
                long_pnl > 0
            ), f"Long PnL should be positive when exit ({exit_price}) > entry ({entry_price})"
            assert (
                short_pnl < 0
            ), f"Short PnL should be negative when exit ({exit_price}) > entry ({entry_price})"
        elif exit_price < entry_price:
            assert (
                long_pnl < 0
            ), f"Long PnL should be negative when exit ({exit_price}) < entry ({entry_price})"
            assert (
                short_pnl > 0
            ), f"Short PnL should be positive when exit ({exit_price}) < entry ({entry_price})"

    @given(
        entry_price=currency_prices(),
        exit_price=currency_prices(),
        quantity=trade_quantities(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pnl_zero_at_breakeven(self, entry_price, exit_price, quantity):
        """Test that P&L is zero when entry equals exit price."""
        assume(quantity > 0)

        # Test with same entry and exit price
        long_pnl = FinancialCalculator.calculate_pnl(
            entry_price, entry_price, quantity, is_long=True
        )
        short_pnl = FinancialCalculator.calculate_pnl(
            entry_price, entry_price, quantity, is_long=False
        )

        assert (
            abs(long_pnl) < 1e-10
        ), f"Long PnL should be zero at breakeven, got {long_pnl}"
        assert (
            abs(short_pnl) < 1e-10
        ), f"Short PnL should be zero at breakeven, got {short_pnl}"

    @given(
        entry_price=currency_prices(),
        exit_price=currency_prices(),
        quantity=trade_quantities(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pnl_quantity_scaling(self, entry_price, exit_price, quantity):
        """Test that P&L scales linearly with quantity."""
        assume(quantity > 0)
        assume(abs(entry_price - exit_price) > 0.0001)

        base_pnl = FinancialCalculator.calculate_pnl(
            entry_price, exit_price, quantity, is_long=True
        )
        double_pnl = FinancialCalculator.calculate_pnl(
            entry_price, exit_price, quantity * 2, is_long=True
        )

        assert (
            abs(double_pnl - (base_pnl * 2)) < 1e-6
        ), f"P&L should scale linearly with quantity"

    @given(
        entry_price=currency_prices(),
        exit_price=currency_prices(),
        quantity=trade_quantities(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pnl_decimal_precision(self, entry_price, exit_price, quantity):
        """Test that Decimal calculation is more precise than float."""
        assume(quantity > 0)
        assume(abs(entry_price - exit_price) > 0.000001)

        # Use very small price difference to test precision
        small_diff = 0.00001
        exit_price_precise = entry_price + small_diff

        float_pnl = FinancialCalculator.calculate_pnl(
            entry_price, exit_price_precise, quantity
        )
        decimal_pnl = FinancialCalculator.calculate_pnl_decimal(
            Decimal(str(entry_price)),
            Decimal(str(exit_price_precise)),
            Decimal(str(quantity)),
        )

        # Decimal should be at least as accurate
        expected_pnl = small_diff * quantity
        decimal_error = abs(float(decimal_pnl) - expected_pnl)
        float_error = abs(float_pnl - expected_pnl)

        assert decimal_error <= float_error or decimal_error < 1e-12


class TestCurrencyConversionProperties:
    """Test properties of currency conversion."""

    @given(
        amount=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        ),
        rate=exchange_rates(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_currency_conversion_reversibility(self, amount, rate):
        """Test that currency conversion is reversible."""
        assume(rate > 0.0001)  # Avoid division by very small numbers

        converted = FinancialCalculator.convert_currency(amount, rate)
        reverted = FinancialCalculator.convert_currency(converted, 1.0 / rate)

        # Should be approximately equal due to floating point precision
        assert (
            abs(reverted - amount) / amount < 1e-10
        ), f"Conversion should be reversible"

    @given(
        amount=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        ),
        rate1=exchange_rates(),
        rate2=exchange_rates(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_currency_conversion_transitivity(self, amount, rate1, rate2):
        """Test transitivity of currency conversions."""
        assume(rate1 > 0.0001 and rate2 > 0.0001)

        # Convert A->B->C vs A->C directly
        step_by_step = FinancialCalculator.convert_currency(
            FinancialCalculator.convert_currency(amount, rate1), rate2
        )
        direct = FinancialCalculator.convert_currency(amount, rate1 * rate2)

        assert abs(step_by_step - direct) / max(step_by_step, direct) < 1e-10

    @given(
        amount=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        )
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_currency_conversion_identity(self, amount):
        """Test that converting with rate 1.0 returns original amount."""
        converted = FinancialCalculator.convert_currency(amount, 1.0)
        assert (
            abs(converted - amount) < 1e-12
        ), f"Conversion by 1.0 should return original amount"


class TestPercentageReturnProperties:
    """Test properties of percentage return calculations."""

    @given(
        initial=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        ),
        final=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_percentage_return_sign(self, initial, final):
        """Test that percentage return sign matches value change direction."""
        return_pct = FinancialCalculator.calculate_percentage_return(initial, final)

        if final > initial:
            assert return_pct > 0, f"Return should be positive when final > initial"
        elif final < initial:
            assert return_pct < 0, f"Return should be negative when final < initial"
        else:
            assert (
                abs(return_pct) < 1e-10
            ), f"Return should be zero when final == initial"

    @given(
        initial=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        )
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_percentage_return_zero_change(self, initial):
        """Test that zero change results in zero return."""
        return_pct = FinancialCalculator.calculate_percentage_return(initial, initial)
        assert abs(return_pct) < 1e-10, f"Zero change should result in zero return"

    @given(
        initial=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        ),
        multiplier=st.floats(
            min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_percentage_return_doubling(self, initial, multiplier):
        """Test percentage return for doubling/halving."""
        final = initial * multiplier
        return_pct = FinancialCalculator.calculate_percentage_return(initial, final)
        expected_return = (multiplier - 1) * 100

        assert (
            abs(return_pct - expected_return) < 1e-10
        ), f"Return calculation incorrect for multiplier {multiplier}"


class TestCompoundInterestProperties:
    """Test properties of compound interest calculations."""

    @given(principal=account_balances(), rate=interest_rates(), periods=time_periods())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_compound_interest_zero_rate(self, principal, rate, periods):
        """Test that zero interest rate returns principal."""
        assume(principal > 0)

        result = FinancialCalculator.compound_interest(principal, 0.0, periods)
        assert abs(result - principal) < 1e-10, f"Zero rate should return principal"

    @given(
        principal=account_balances(),
        rate=st.floats(
            min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False
        ),
        periods=time_periods(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_compound_interest_positive_growth(self, principal, rate, periods):
        """Test that positive rate results in growth."""
        assume(principal > 0)
        assume(rate > 0)
        assume(periods > 0)

        result = FinancialCalculator.compound_interest(principal, rate, periods)
        assert result > principal, f"Positive rate should result in growth"

    @given(
        principal=account_balances(),
        rate=st.floats(
            min_value=0.01, max_value=0.2, allow_nan=False, allow_infinity=False
        ),
        periods=time_periods(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_compound_interest_period_doubling(self, principal, rate, periods):
        """Test that doubling periods doesn't equal squaring the result."""
        assume(principal > 0)
        assume(rate > 0)
        assume(periods > 0)

        single_period_result = FinancialCalculator.compound_interest(
            principal, rate, periods
        )
        double_period_result = FinancialCalculator.compound_interest(
            principal, rate, periods * 2
        )

        # Double periods should be more than squaring (due to compounding)
        squared_result = (single_period_result / principal) ** 2 * principal
        assert (
            double_period_result >= squared_result
        ), f"Compound interest should show compounding effect"


class TestPositionSizeProperties:
    """Test properties of position size calculations."""

    @given(
        balance=account_balances(),
        risk_pct=percentage_values(),
        entry=currency_prices(),
        stop=currency_prices(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_position_size_risk_scaling(self, balance, risk_pct, entry, stop):
        """Test that position size scales with risk percentage."""
        assume(balance > 0)
        assume(risk_pct > 0 and risk_pct <= 100)
        assume(abs(entry - stop) > 0.0001)  # Meaningful difference
        assume(entry > 0 and stop > 0)

        size1 = FinancialCalculator.position_size(balance, risk_pct, entry, stop)
        size2 = FinancialCalculator.position_size(balance, risk_pct * 2, entry, stop)

        if size1 > 0:  # Valid position calculated
            assert (
                abs(size2 - size1 * 2) / size1 < 1e-6
            ), f"Position size should scale with risk percentage"

    @given(
        balance=account_balances(),
        risk_pct=percentage_values(),
        price=currency_prices(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_position_size_zero_when_no_risk(self, balance, risk_pct, price):
        """Test that position size is zero when entry equals stop loss."""
        assume(balance > 0)
        assume(price > 0)

        size = FinancialCalculator.position_size(balance, risk_pct, price, price)
        assert size == 0.0, f"Position size should be zero when entry equals stop loss"

    @given(
        balance=account_balances(),
        risk_pct=percentage_values(),
        entry=currency_prices(),
        stop=currency_prices(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_position_size_positive(self, balance, risk_pct, entry, stop):
        """Test that position size is always non-negative."""
        assume(balance > 0)
        assume(risk_pct >= 0)
        assume(entry > 0 and stop > 0)

        size = FinancialCalculator.position_size(balance, risk_pct, entry, stop)
        assert size >= 0, f"Position size should never be negative"


class TestSharpeRatioProperties:
    """Test properties of Sharpe ratio calculations."""

    @given(returns=returns_list())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_sharpe_ratio_zero_volatility(self, returns):
        """Test Sharpe ratio when all returns are identical (zero volatility)."""
        assume(len(returns) >= 2)

        # Create constant returns
        constant_return = 0.05
        constant_returns = [constant_return] * len(returns)

        sharpe = FinancialCalculator.sharpe_ratio(constant_returns, 0.0)
        assert sharpe == 0.0, f"Sharpe ratio should be zero for constant returns"

    @given(
        returns=returns_list(),
        risk_free_rate=st.floats(
            min_value=-0.1, max_value=0.1, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_sharpe_ratio_sign_consistency(self, returns, risk_free_rate):
        """Test that Sharpe ratio sign matches excess return direction."""
        assume(len(returns) >= 2)
        assume(np.std(returns) > 1e-10)  # Non-zero volatility

        sharpe = FinancialCalculator.sharpe_ratio(returns, risk_free_rate)
        mean_return = np.mean(returns)

        if mean_return > risk_free_rate:
            assert (
                sharpe >= 0
            ), f"Sharpe ratio should be non-negative when mean return > risk-free rate"
        elif mean_return < risk_free_rate:
            assert (
                sharpe <= 0
            ), f"Sharpe ratio should be non-positive when mean return < risk-free rate"

    @given(returns=returns_list())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_sharpe_ratio_scaling_invariance(self, returns):
        """Test that Sharpe ratio is invariant to scaling all returns."""
        assume(len(returns) >= 2)
        assume(np.std(returns) > 1e-10)

        original_sharpe = FinancialCalculator.sharpe_ratio(returns, 0.0)
        scaled_returns = [r * 2 for r in returns]
        scaled_sharpe = FinancialCalculator.sharpe_ratio(scaled_returns, 0.0)

        assert (
            abs(original_sharpe - scaled_sharpe) < 1e-10
        ), f"Sharpe ratio should be scale-invariant"


class TestMaxDrawdownProperties:
    """Test properties of maximum drawdown calculations."""

    @given(curve=equity_curve())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_max_drawdown_range(self, curve):
        """Test that maximum drawdown is between 0 and 1."""
        assume(len(curve) >= 2)
        assume(all(v > 0 for v in curve))

        max_dd = FinancialCalculator.max_drawdown(curve)
        assert (
            0.0 <= max_dd <= 1.0
        ), f"Maximum drawdown should be between 0 and 1, got {max_dd}"

    @given(
        initial_value=st.floats(
            min_value=1000.0, max_value=100000.0, allow_nan=False, allow_infinity=False
        ),
        length=st.integers(min_value=2, max_value=100),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_max_drawdown_monotonic_increase(self, initial_value, length):
        """Test that maximum drawdown is zero for monotonically increasing curve."""
        # Create monotonically increasing curve
        curve = [initial_value * (1 + 0.01) ** i for i in range(length)]

        max_dd = FinancialCalculator.max_drawdown(curve)
        assert (
            abs(max_dd) < 1e-10
        ), f"Maximum drawdown should be zero for increasing curve"

    @given(
        initial_value=st.floats(
            min_value=1000.0, max_value=100000.0, allow_nan=False, allow_infinity=False
        ),
        drop_percentage=st.floats(
            min_value=0.1, max_value=0.9, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_max_drawdown_single_drop(self, initial_value, drop_percentage):
        """Test maximum drawdown calculation for single drop scenario."""
        final_value = initial_value * (1 - drop_percentage)
        curve = [initial_value, final_value]

        max_dd = FinancialCalculator.max_drawdown(curve)
        expected_dd = drop_percentage

        assert (
            abs(max_dd - expected_dd) < 1e-10
        ), f"Maximum drawdown should equal drop percentage"


class TestPipRoundingProperties:
    """Test properties of pip rounding."""

    @given(
        price=currency_prices(),
        pip_size=st.floats(
            min_value=0.00001, max_value=0.1, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pip_rounding_idempotent(self, price, pip_size):
        """Test that rounding twice gives same result as rounding once."""
        rounded_once = FinancialCalculator.round_to_pip(price, pip_size)
        rounded_twice = FinancialCalculator.round_to_pip(rounded_once, pip_size)

        assert (
            abs(rounded_once - rounded_twice) < 1e-12
        ), f"Pip rounding should be idempotent"

    @given(
        price=currency_prices(),
        pip_size=st.floats(
            min_value=0.00001, max_value=0.1, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pip_rounding_precision(self, price, pip_size):
        """Test that rounded price is multiple of pip size."""
        rounded = FinancialCalculator.round_to_pip(price, pip_size)

        # Check if rounded price is multiple of pip_size
        multiple = rounded / pip_size
        assert (
            abs(multiple - round(multiple)) < 1e-10
        ), f"Rounded price should be multiple of pip size"

    @given(
        price=currency_prices(),
        pip_size=st.floats(
            min_value=0.00001, max_value=0.1, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pip_rounding_distance(self, price, pip_size):
        """Test that rounding doesn't change price by more than half pip."""
        rounded = FinancialCalculator.round_to_pip(price, pip_size)
        distance = abs(price - rounded)

        assert (
            distance <= pip_size / 2 + 1e-12
        ), f"Rounding should not change price by more than half pip"


class TestMathematicalInvariants:
    """Test mathematical invariants across all calculations."""

    @given(
        a=st.floats(
            min_value=-1000000.0,
            max_value=1000000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        b=st.floats(
            min_value=-1000000.0,
            max_value=1000000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        c=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pnl_linearity(self, a, b, c):
        """Test linearity property of P&L calculations."""
        assume(c > 0)

        # P&L should be linear in price difference
        pnl1 = FinancialCalculator.calculate_pnl(a, b, c)
        pnl2 = FinancialCalculator.calculate_pnl(a, a + 2 * (b - a), c)

        if abs(b - a) > 1e-10:  # Avoid division by very small numbers
            # PnL should double when price difference doubles
            expected_ratio = 2.0
            actual_ratio = pnl2 / pnl1 if abs(pnl1) > 1e-10 else float("inf")

            if abs(actual_ratio - expected_ratio) > 1e-6:
                # Only assert if the difference is significant
                if abs(pnl1) > 1e-6:  # Only for meaningful P&L values
                    assert (
                        abs(actual_ratio - expected_ratio) < 1e-6
                    ), f"P&L linearity violated"

    @given(
        x=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        ),
        y=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_percentage_return_inverse_relationship(self, x, y):
        """Test inverse relationship in percentage returns."""
        return_xy = FinancialCalculator.calculate_percentage_return(x, y)
        return_yx = FinancialCalculator.calculate_percentage_return(y, x)

        # When x->y has positive return, y->x should have negative return
        if abs(return_xy) > 1e-6:  # Avoid near-zero returns
            assert (
                return_xy * return_yx < 0
            ), f"Inverse returns should have opposite signs"


# Example-based tests for edge cases
class TestExampleBasedProperties:
    """Test specific examples to ensure property-based tests work correctly."""

    @example(entry_price=1.2650, exit_price=1.2750, quantity=10000.0)
    @given(
        entry_price=currency_prices(),
        exit_price=currency_prices(),
        quantity=trade_quantities(),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pnl_example_validation(self, entry_price, exit_price, quantity):
        """Validate P&L calculation with known examples."""
        assume(quantity > 0)

        pnl = FinancialCalculator.calculate_pnl(
            entry_price, exit_price, quantity, is_long=True
        )
        expected_pnl = (exit_price - entry_price) * quantity

        assert (
            abs(pnl - expected_pnl) < 1e-10
        ), f"P&L calculation should match expected formula"

    @example(initial=1000.0, final=1100.0)
    @given(
        initial=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        ),
        final=st.floats(
            min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_percentage_return_example_validation(self, initial, final):
        """Validate percentage return with known examples."""
        return_pct = FinancialCalculator.calculate_percentage_return(initial, final)
        expected_return = ((final - initial) / initial) * 100

        assert (
            abs(return_pct - expected_return) < 1e-10
        ), f"Percentage return should match expected formula"


if __name__ == "__main__":
    # Run property-based tests
    pytest.main([__file__, "-v", "--tb=short"])
