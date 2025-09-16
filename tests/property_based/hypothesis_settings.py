"""
Hypothesis Configuration for FXML4 Property-Based Testing
========================================================

Global configuration and custom profiles for Hypothesis property-based testing.
This ensures consistent behavior across all property-based tests and provides
different profiles for different testing scenarios.
"""

import os

from hypothesis import HealthCheck, Phase, Verbosity, settings
from hypothesis.strategies import composite

# ============================================================================
# Global Hypothesis Settings
# ============================================================================

# Default profile for development
settings.register_profile(
    "dev",
    max_examples=50,  # Reduced for faster development feedback
    deadline=5000,  # 5 second deadline per example
    verbosity=Verbosity.normal,
    print_blob=True,  # Print failing examples
    suppress_health_checks=[
        HealthCheck.too_slow,
        HealthCheck.data_too_large,
    ],
    phases=[
        Phase.explicit,  # Run explicit examples first
        Phase.reuse,  # Reuse previous failures
        Phase.generate,  # Generate new examples
        Phase.shrink,  # Shrink failing examples
    ],
)

# Thorough profile for CI/CD
settings.register_profile(
    "ci",
    max_examples=200,  # More thorough testing in CI
    deadline=10000,  # 10 second deadline
    verbosity=Verbosity.verbose,
    print_blob=True,
    derandomize=True,  # Deterministic for CI
    suppress_health_checks=[
        HealthCheck.too_slow,
    ],
)

# Quick profile for smoke testing
settings.register_profile(
    "quick",
    max_examples=10,  # Very fast for smoke tests
    deadline=2000,  # 2 second deadline
    verbosity=Verbosity.quiet,
    print_blob=False,
    phases=[Phase.explicit, Phase.generate],  # Skip shrinking for speed
)

# Intensive profile for finding edge cases
settings.register_profile(
    "intensive",
    max_examples=1000,  # Maximum thoroughness
    deadline=30000,  # 30 second deadline
    verbosity=Verbosity.verbose,
    print_blob=True,
    suppress_health_checks=[
        HealthCheck.too_slow,
        HealthCheck.data_too_large,
    ],
)

# Performance testing profile
settings.register_profile(
    "performance",
    max_examples=100,
    deadline=1000,  # Strict deadline for performance tests
    verbosity=Verbosity.normal,
    print_blob=True,
    suppress_health_checks=[
        HealthCheck.data_too_large,
    ],
)

# Select profile based on environment
profile_name = os.environ.get("HYPOTHESIS_PROFILE", "dev")
settings.load_profile(profile_name)


# ============================================================================
# Custom Health Checks for Financial Testing
# ============================================================================


class FinancialHealthChecks:
    """Custom health checks for financial testing."""

    @staticmethod
    def check_price_precision(prices):
        """Ensure prices have reasonable precision."""
        for price in prices:
            if isinstance(price, float):
                # Check for excessive precision (more than 5 decimal places)
                decimal_places = len(str(price).split(".")[-1])
                if decimal_places > 5:
                    return False, f"Price {price} has excessive precision"
        return True, "Price precision OK"

    @staticmethod
    def check_financial_ranges(values, value_type="generic"):
        """Check that financial values are within reasonable ranges."""
        range_checks = {
            "price": (0.0001, 10000.0),
            "quantity": (0.01, 1000000.0),
            "percentage": (-1.0, 10.0),  # -100% to 1000%
            "balance": (0.0, 1000000000.0),  # $1B max
        }

        if value_type in range_checks:
            min_val, max_val = range_checks[value_type]
            for value in values:
                if not (min_val <= value <= max_val):
                    return (
                        False,
                        f"{value_type} {value} outside range [{min_val}, {max_val}]",
                    )

        return True, f"{value_type} values within acceptable range"


# ============================================================================
# Custom Hypothesis Decorators
# ============================================================================


def financial_property(max_examples=None, deadline=None):
    """
    Decorator for financial property tests with appropriate settings.

    Usage:
        @financial_property(max_examples=100)
        def test_trading_property(data):
            # Test logic here
            pass
    """

    def decorator(test_func):
        # Apply financial-specific settings
        financial_settings = {}

        if max_examples is not None:
            financial_settings["max_examples"] = max_examples

        if deadline is not None:
            financial_settings["deadline"] = deadline

        # Add financial-specific health check suppressions
        financial_settings["suppress_health_checks"] = [
            HealthCheck.too_slow,
            HealthCheck.data_too_large,
        ]

        return settings(**financial_settings)(test_func)

    return decorator


def trading_property(max_examples=50):
    """
    Specific decorator for trading logic tests.

    Usage:
        @trading_property(max_examples=100)
        def test_position_sizing(account_balance, risk_percent):
            # Test trading logic
            pass
    """
    return financial_property(
        max_examples=max_examples,
        deadline=8000,  # Trading tests might need more time
    )


def api_property(max_examples=30):
    """
    Specific decorator for API tests.

    Usage:
        @api_property()
        def test_api_validation(request_data):
            # Test API behavior
            pass
    """
    return financial_property(
        max_examples=max_examples,
        deadline=3000,  # API tests should be fast
    )


# ============================================================================
# Hypothesis Strategy Registration
# ============================================================================


# Register common financial strategies globally
def register_financial_strategies():
    """Register commonly used financial strategies."""
    from hypothesis import strategies as st

    # Currency prices with realistic constraints
    st.register_strategy_for_type(
        "currency_price",
        st.floats(
            min_value=0.0001, max_value=10.0, allow_nan=False, allow_infinity=False
        ),
    )

    # Trading quantities
    st.register_strategy_for_type(
        "trading_quantity",
        st.floats(min_value=0.01, max_value=1000000.0, allow_nan=False),
    )

    # Percentage values
    st.register_strategy_for_type(
        "percentage", st.floats(min_value=-1.0, max_value=10.0, allow_nan=False)
    )


# Auto-register strategies when module is imported
register_financial_strategies()


# ============================================================================
# Utility Functions for Property-Based Testing
# ============================================================================


def assume_valid_financial_data(**kwargs):
    """
    Helper function to add common financial data assumptions.

    Usage:
        @given(price=st.floats(), quantity=st.floats())
        def test_trade_value(price, quantity):
            assume_valid_financial_data(price=price, quantity=quantity)
            # Test logic here
    """
    from hypothesis import assume

    # Price assumptions
    if "price" in kwargs:
        price = kwargs["price"]
        assume(price > 0)
        assume(price < 10000)
        assume(not (price != price))  # Not NaN

    # Quantity assumptions
    if "quantity" in kwargs:
        quantity = kwargs["quantity"]
        assume(quantity > 0)
        assume(quantity < 1000000)
        assume(not (quantity != quantity))  # Not NaN

    # Balance assumptions
    if "balance" in kwargs:
        balance = kwargs["balance"]
        assume(balance >= 0)
        assume(balance < 1000000000)

    # Percentage assumptions
    if "percentage" in kwargs:
        percentage = kwargs["percentage"]
        assume(percentage > -1.0)  # No more than 100% loss
        assume(percentage < 10.0)  # No more than 1000% gain


def is_reasonable_financial_value(value, value_type="generic"):
    """
    Check if a value is reasonable for financial calculations.

    Returns:
        bool: True if the value is reasonable
    """
    if value != value:  # NaN check
        return False

    if value == float("inf") or value == float("-inf"):
        return False

    # Type-specific checks
    if value_type == "price":
        return 0.0001 <= value <= 10000.0
    elif value_type == "quantity":
        return 0.01 <= value <= 1000000.0
    elif value_type == "percentage":
        return -1.0 <= value <= 10.0
    elif value_type == "balance":
        return 0.0 <= value <= 1000000000.0
    else:
        return True  # Generic check passed


def sanitize_financial_data(data_dict):
    """
    Sanitize financial data to ensure it's reasonable.

    Args:
        data_dict: Dictionary of financial data

    Returns:
        dict: Sanitized data
    """
    sanitized = {}

    for key, value in data_dict.items():
        if isinstance(value, (int, float)):
            if key in ["price", "open", "high", "low", "close"]:
                sanitized[key] = max(0.0001, min(10000.0, abs(value)))
            elif key in ["quantity", "volume"]:
                sanitized[key] = max(0.01, min(1000000.0, abs(value)))
            elif key in ["balance", "account_value"]:
                sanitized[key] = max(0.0, min(1000000000.0, abs(value)))
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value

    return sanitized


# ============================================================================
# Environment Configuration
# ============================================================================


def configure_hypothesis_for_environment():
    """Configure Hypothesis based on the current environment."""
    import sys

    # Check if running in CI
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        settings.load_profile("ci")
        print("Using Hypothesis CI profile")

    # Check if running with pytest-xdist (parallel)
    elif "pytest" in sys.modules and os.environ.get("PYTEST_XDIST_WORKER"):
        # Use less intensive settings for parallel workers
        settings.load_profile("quick")
        print("Using Hypothesis quick profile for parallel execution")

    # Check for performance testing
    elif os.environ.get("PERFORMANCE_TEST"):
        settings.load_profile("performance")
        print("Using Hypothesis performance profile")

    # Check for intensive testing
    elif os.environ.get("INTENSIVE_TEST"):
        settings.load_profile("intensive")
        print("Using Hypothesis intensive profile")

    else:
        settings.load_profile("dev")
        print("Using Hypothesis development profile")


# Auto-configure when module is imported
configure_hypothesis_for_environment()


# ============================================================================
# Export Configuration
# ============================================================================

__all__ = [
    "financial_property",
    "trading_property",
    "api_property",
    "assume_valid_financial_data",
    "is_reasonable_financial_value",
    "sanitize_financial_data",
    "FinancialHealthChecks",
    "configure_hypothesis_for_environment",
]
