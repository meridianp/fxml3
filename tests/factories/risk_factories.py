"""
Risk Management Factory Definitions
===================================

Factory Boy factories for creating risk limits, metrics, drawdown events,
and exposure calculations for testing risk management systems.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import factory
import factory.fuzzy
from faker import Faker

fake = Faker()


class RiskLimitFactory(factory.Factory):
    """
    Factory for creating risk limit configurations and thresholds.

    Generates realistic risk management parameters including position limits,
    loss limits, exposure limits, and compliance thresholds.
    """

    class Meta:
        model = dict

    # Limit identification
    limit_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    account_id = factory.Sequence(lambda n: f"ACC{n:08d}")
    limit_name = factory.fuzzy.FuzzyChoice(
        [
            "Daily Loss Limit",
            "Position Size Limit",
            "Leverage Limit",
            "Exposure Limit",
            "Concentration Limit",
            "Correlation Limit",
            "Volatility Limit",
            "Drawdown Limit",
            "VaR Limit",
        ]
    )

    # Limit type and scope
    limit_type = factory.fuzzy.FuzzyChoice(["absolute", "percentage", "relative"])
    limit_scope = factory.fuzzy.FuzzyChoice(
        ["account", "symbol", "strategy", "portfolio"]
    )
    currency = factory.fuzzy.FuzzyChoice(["USD", "EUR", "GBP"])

    # Limit values
    limit_value = factory.LazyAttribute(
        lambda obj: {
            "Daily Loss Limit": fake.random.uniform(1000, 10000),
            "Position Size Limit": fake.random.uniform(1.0, 100.0),
            "Leverage Limit": fake.random.uniform(1, 500),
            "Exposure Limit": fake.random.uniform(100000, 1000000),
            "Concentration Limit": fake.random.uniform(0.1, 0.5),  # 10-50%
            "Drawdown Limit": fake.random.uniform(0.05, 0.25),  # 5-25%
            "VaR Limit": fake.random.uniform(0.01, 0.05),  # 1-5%
        }.get(obj.limit_name, fake.random.uniform(1000, 100000))
    )

    # Warning thresholds
    warning_threshold = factory.LazyAttribute(
        lambda obj: obj.limit_value * Decimal(str(fake.random.uniform(0.7, 0.9)))
    )
    breach_threshold = factory.LazyAttribute(lambda obj: obj.limit_value)

    # Current utilization
    current_value = factory.LazyAttribute(
        lambda obj: obj.limit_value * Decimal(str(fake.random.uniform(0.0, 1.2)))
    )
    utilization_percentage = factory.LazyAttribute(
        lambda obj: (
            (obj.current_value / obj.limit_value) * 100
            if obj.limit_value != 0
            else Decimal("0")
        )
    )

    # Status and alerts
    status = factory.LazyAttribute(
        lambda obj: (
            "breached"
            if obj.current_value > obj.breach_threshold
            else "warning" if obj.current_value > obj.warning_threshold else "normal"
        )
    )
    alert_sent = factory.LazyAttribute(lambda obj: obj.status != "normal")
    last_breach_time = factory.LazyAttribute(
        lambda obj: (
            fake.date_time_between(start_date="-30d", end_date="now")
            if obj.status == "breached"
            else None
        )
    )

    # Time-based limits
    time_window = factory.fuzzy.FuzzyChoice(
        ["daily", "weekly", "monthly", "yearly", "real_time"]
    )
    reset_frequency = factory.LazyAttribute(lambda obj: obj.time_window)
    last_reset = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )
    next_reset = factory.LazyAttribute(
        lambda obj: {
            "daily": obj.last_reset + timedelta(days=1),
            "weekly": obj.last_reset + timedelta(weeks=1),
            "monthly": obj.last_reset + timedelta(days=30),
            "yearly": obj.last_reset + timedelta(days=365),
        }.get(obj.time_window, obj.last_reset + timedelta(days=1))
    )

    # Enforcement actions
    enforcement_action = factory.fuzzy.FuzzyChoice(
        [
            "warning_only",
            "block_new_trades",
            "close_positions",
            "reduce_positions",
            "notify_manager",
        ]
    )
    auto_enforcement = factory.fuzzy.FuzzyChoice([True, False])

    # Metadata
    created_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-90d", end_date="-1d")
    )
    updated_at = factory.LazyAttribute(
        lambda obj: obj.created_at + timedelta(days=fake.random_int(1, 30))
    )
    is_active = True
    created_by = factory.fuzzy.FuzzyChoice(
        ["risk_manager", "compliance_officer", "system_admin"]
    )

    class Params:
        # Traits for different limit scenarios
        strict_limits = factory.Trait(
            warning_threshold=factory.LazyAttribute(
                lambda obj: obj.limit_value * Decimal("0.5")
            ),
            auto_enforcement=True,
            enforcement_action="block_new_trades",
        )

        breached_limit = factory.Trait(
            current_value=factory.LazyAttribute(
                lambda obj: obj.limit_value * Decimal("1.2")
            ),
            status="breached",
            alert_sent=True,
        )

        conservative_limits = factory.Trait(
            limit_value=factory.fuzzy.FuzzyDecimal(500.0, 2000.0, 2),
            warning_threshold=factory.LazyAttribute(
                lambda obj: obj.limit_value * Decimal("0.6")
            ),
        )


class RiskMetricFactory(factory.Factory):
    """
    Factory for creating risk metric calculations and assessments.
    """

    class Meta:
        model = dict

    # Metric identification
    metric_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    account_id = factory.Sequence(lambda n: f"ACC{n:08d}")
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY", "Portfolio"])

    # Metric type
    metric_name = factory.fuzzy.FuzzyChoice(
        [
            "Value at Risk (VaR)",
            "Expected Shortfall",
            "Maximum Drawdown",
            "Sharpe Ratio",
            "Sortino Ratio",
            "Beta",
            "Alpha",
            "Correlation",
            "Volatility",
            "Tracking Error",
            "Information Ratio",
        ]
    )

    # Risk calculations
    current_value = factory.LazyAttribute(
        lambda obj: {
            "Value at Risk (VaR)": fake.random.uniform(500, 5000),
            "Expected Shortfall": fake.random.uniform(800, 8000),
            "Maximum Drawdown": fake.random.uniform(0.05, 0.30),
            "Sharpe Ratio": fake.random.uniform(-0.5, 3.0),
            "Sortino Ratio": fake.random.uniform(-0.5, 4.0),
            "Beta": fake.random.uniform(0.5, 2.0),
            "Alpha": fake.random.uniform(-0.05, 0.10),
            "Correlation": fake.random.uniform(-1.0, 1.0),
            "Volatility": fake.random.uniform(0.10, 0.40),
            "Tracking Error": fake.random.uniform(0.02, 0.15),
            "Information Ratio": fake.random.uniform(-1.0, 2.0),
        }.get(obj.metric_name, fake.random.uniform(0, 100))
    )

    # Historical values (last 30 days)
    historical_values = factory.LazyAttribute(
        lambda obj: [
            obj.current_value + fake.random.uniform(-0.2, 0.2) * abs(obj.current_value)
            for _ in range(30)
        ]
    )

    # Statistical measures
    percentile_95 = factory.LazyAttribute(lambda obj: max(obj.historical_values) * 0.95)
    percentile_5 = factory.LazyAttribute(lambda obj: min(obj.historical_values) * 1.05)
    mean_value = factory.LazyAttribute(
        lambda obj: sum(obj.historical_values) / len(obj.historical_values)
    )
    std_deviation = factory.LazyAttribute(
        lambda obj: (
            sum([(x - obj.mean_value) ** 2 for x in obj.historical_values])
            / len(obj.historical_values)
        )
        ** 0.5
    )

    # Confidence intervals
    confidence_level = factory.fuzzy.FuzzyDecimal(0.90, 0.99, 2)
    lower_bound = factory.LazyAttribute(
        lambda obj: obj.current_value - obj.std_deviation * 1.96
    )
    upper_bound = factory.LazyAttribute(
        lambda obj: obj.current_value + obj.std_deviation * 1.96
    )

    # Time horizon and methodology
    time_horizon_days = factory.fuzzy.FuzzyInteger(1, 365)
    calculation_method = factory.fuzzy.FuzzyChoice(
        ["Historical Simulation", "Monte Carlo", "Parametric", "EWMA", "GARCH"]
    )

    # Risk interpretation
    risk_level = factory.LazyAttribute(
        lambda obj: {
            "Value at Risk (VaR)": (
                "high"
                if obj.current_value > 3000
                else "medium" if obj.current_value > 1500 else "low"
            ),
            "Maximum Drawdown": (
                "high"
                if obj.current_value > 0.20
                else "medium" if obj.current_value > 0.10 else "low"
            ),
            "Sharpe Ratio": (
                "low"
                if obj.current_value > 1.5
                else "medium" if obj.current_value > 0.5 else "high"
            ),
            "Volatility": (
                "high"
                if obj.current_value > 0.25
                else "medium" if obj.current_value > 0.15 else "low"
            ),
        }.get(obj.metric_name, fake.random_element(["low", "medium", "high"]))
    )

    # Calculation metadata
    calculated_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1d", end_date="now")
    )
    calculation_frequency = factory.fuzzy.FuzzyChoice(
        ["real_time", "hourly", "daily", "weekly"]
    )
    data_points_used = factory.fuzzy.FuzzyInteger(100, 1000)
    is_valid = True


class DrawdownEventFactory(factory.Factory):
    """
    Factory for creating drawdown event records with recovery tracking.
    """

    class Meta:
        model = dict

    # Event identification
    event_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    account_id = factory.Sequence(lambda n: f"ACC{n:08d}")
    strategy_name = factory.fuzzy.FuzzyChoice(
        ["GBP_USD_Strategy", "EUR_USD_Scalper", "Trend_Following"]
    )

    # Drawdown details
    drawdown_start = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-90d", end_date="-30d")
    )
    drawdown_end = factory.LazyAttribute(
        lambda obj: (
            obj.drawdown_start + timedelta(days=fake.random_int(1, 30))
            if fake.random.random() > 0.3
            else None
        )  # 30% still ongoing
    )

    # Financial impact
    peak_balance = factory.fuzzy.FuzzyDecimal(10000.0, 100000.0, 2)
    trough_balance = factory.LazyAttribute(
        lambda obj: obj.peak_balance * Decimal(str(fake.random.uniform(0.7, 0.95)))
    )
    max_drawdown_amount = factory.LazyAttribute(
        lambda obj: obj.peak_balance - obj.trough_balance
    )
    max_drawdown_percent = factory.LazyAttribute(
        lambda obj: (obj.max_drawdown_amount / obj.peak_balance) * 100
    )

    # Recovery tracking
    current_balance = factory.LazyAttribute(
        lambda obj: (
            obj.trough_balance
            + (Decimal(str(fake.random.uniform(0.0, float(obj.max_drawdown_amount)))))
            if obj.drawdown_end
            else obj.trough_balance
        )
    )
    recovery_percent = factory.LazyAttribute(
        lambda obj: (
            ((obj.current_balance - obj.trough_balance) / obj.max_drawdown_amount) * 100
            if obj.max_drawdown_amount > 0
            else Decimal("0")
        )
    )
    is_recovered = factory.LazyAttribute(
        lambda obj: obj.current_balance >= obj.peak_balance
    )

    # Duration analysis
    drawdown_duration_days = factory.LazyAttribute(
        lambda obj: (
            (obj.drawdown_end - obj.drawdown_start).days
            if obj.drawdown_end
            else (datetime.utcnow() - obj.drawdown_start).days
        )
    )
    recovery_duration_days = factory.LazyAttribute(
        lambda obj: (
            (datetime.utcnow() - obj.drawdown_end).days
            if obj.drawdown_end and obj.is_recovered
            else None
        )
    )

    # Contributing factors
    primary_cause = factory.fuzzy.FuzzyChoice(
        [
            "market_volatility",
            "strategy_failure",
            "position_sizing",
            "risk_management",
            "external_shock",
            "correlation_breakdown",
            "liquidity_crisis",
        ]
    )
    contributing_trades = factory.fuzzy.FuzzyInteger(1, 20)
    largest_loss_trade = factory.LazyAttribute(
        lambda obj: obj.max_drawdown_amount
        * Decimal(str(fake.random.uniform(0.2, 0.6)))
    )

    # Risk metrics during drawdown
    avg_daily_volatility = factory.fuzzy.FuzzyDecimal(0.015, 0.050, 3)
    max_daily_loss = factory.LazyAttribute(
        lambda obj: obj.max_drawdown_amount
        * Decimal(str(fake.random.uniform(0.1, 0.4)))
    )
    correlation_with_market = factory.fuzzy.FuzzyDecimal(-1.0, 1.0, 2)

    # Recovery strategy
    recovery_actions = factory.LazyFunction(
        lambda: fake.random_elements(
            [
                "reduced_position_size",
                "increased_diversification",
                "tightened_stops",
                "paused_trading",
                "strategy_adjustment",
                "risk_limit_reduction",
            ],
            length=fake.random_int(1, 3),
        )
    )

    class Params:
        # Traits for different drawdown scenarios
        severe_drawdown = factory.Trait(
            max_drawdown_percent=factory.fuzzy.FuzzyDecimal(25.0, 50.0, 2),
            drawdown_duration_days=factory.fuzzy.FuzzyInteger(20, 90),
            primary_cause="strategy_failure",
        )

        quick_recovery = factory.Trait(
            is_recovered=True,
            recovery_duration_days=factory.fuzzy.FuzzyInteger(1, 10),
            recovery_percent=Decimal("100.0"),
        )

        ongoing_drawdown = factory.Trait(
            drawdown_end=None,
            is_recovered=False,
            recovery_percent=factory.fuzzy.FuzzyDecimal(0.0, 30.0, 2),
        )


class ExposureFactory(factory.Factory):
    """
    Factory for creating portfolio exposure calculations and limits.
    """

    class Meta:
        model = dict

    # Exposure identification
    exposure_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    account_id = factory.Sequence(lambda n: f"ACC{n:08d}")
    exposure_type = factory.fuzzy.FuzzyChoice(
        [
            "currency_exposure",
            "sector_exposure",
            "country_exposure",
            "strategy_exposure",
            "time_exposure",
            "correlation_exposure",
        ]
    )

    # Exposure target
    exposure_target = factory.LazyAttribute(
        lambda obj: {
            "currency_exposure": fake.random_element(
                ["USD", "EUR", "GBP", "JPY", "CHF"]
            ),
            "sector_exposure": fake.random_element(
                ["Technology", "Healthcare", "Finance", "Energy"]
            ),
            "country_exposure": fake.random_element(["US", "EU", "UK", "JP", "CH"]),
            "strategy_exposure": fake.random_element(
                ["Trend", "Mean_Reversion", "Momentum"]
            ),
            "time_exposure": fake.random_element(
                ["London_Session", "New_York_Session", "Tokyo_Session"]
            ),
            "correlation_exposure": fake.random_element(
                ["High_Correlation", "Low_Correlation"]
            ),
        }.get(obj.exposure_type, "Unknown")
    )

    # Exposure amounts
    gross_exposure = factory.fuzzy.FuzzyDecimal(10000.0, 500000.0, 2)
    net_exposure = factory.LazyAttribute(
        lambda obj: obj.gross_exposure * Decimal(str(fake.random.uniform(0.2, 0.8)))
    )
    long_exposure = factory.LazyAttribute(
        lambda obj: obj.gross_exposure * Decimal(str(fake.random.uniform(0.4, 0.7)))
    )
    short_exposure = factory.LazyAttribute(
        lambda obj: obj.gross_exposure - obj.long_exposure
    )

    # Exposure limits
    exposure_limit = factory.LazyAttribute(
        lambda obj: obj.gross_exposure * Decimal(str(fake.random.uniform(1.1, 2.0)))
    )
    exposure_utilization = factory.LazyAttribute(
        lambda obj: (
            (obj.gross_exposure / obj.exposure_limit) * 100
            if obj.exposure_limit > 0
            else Decimal("0")
        )
    )

    # Risk adjusted exposure
    risk_weighted_exposure = factory.LazyAttribute(
        lambda obj: obj.gross_exposure * Decimal(str(fake.random.uniform(0.8, 1.2)))
    )
    volatility_adjustment = factory.fuzzy.FuzzyDecimal(0.8, 1.5, 2)
    correlation_adjustment = factory.fuzzy.FuzzyDecimal(0.7, 1.3, 2)

    # Time-based analysis
    exposure_duration_hours = factory.fuzzy.FuzzyInteger(1, 720)  # Up to 30 days
    avg_holding_period_hours = factory.fuzzy.FuzzyInteger(4, 168)  # 4 hours to 1 week

    # Concentration analysis
    concentration_score = factory.fuzzy.FuzzyDecimal(0.1, 1.0, 2)
    diversification_ratio = factory.fuzzy.FuzzyDecimal(0.3, 1.0, 2)
    max_single_position_percent = factory.fuzzy.FuzzyDecimal(5.0, 50.0, 1)

    # Calculation metadata
    calculated_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1h", end_date="now")
    )
    calculation_method = factory.fuzzy.FuzzyChoice(
        ["real_time", "mark_to_market", "theoretical"]
    )
    is_intraday = factory.fuzzy.FuzzyChoice([True, False])

    class Params:
        # Traits for different exposure scenarios
        high_concentration = factory.Trait(
            concentration_score=factory.fuzzy.FuzzyDecimal(0.7, 1.0, 2),
            max_single_position_percent=factory.fuzzy.FuzzyDecimal(25.0, 50.0, 1),
            diversification_ratio=factory.fuzzy.FuzzyDecimal(0.3, 0.6, 2),
        )

        well_diversified = factory.Trait(
            concentration_score=factory.fuzzy.FuzzyDecimal(0.1, 0.4, 2),
            max_single_position_percent=factory.fuzzy.FuzzyDecimal(5.0, 15.0, 1),
            diversification_ratio=factory.fuzzy.FuzzyDecimal(0.7, 1.0, 2),
        )

        over_limit = factory.Trait(
            exposure_utilization=factory.fuzzy.FuzzyDecimal(100.0, 150.0, 2),
            gross_exposure=factory.LazyAttribute(
                lambda obj: obj.exposure_limit * Decimal("1.2")
            ),
        )
