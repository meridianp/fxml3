"""
Test Suite for Trade Size Validation System (Phase 12)
Validates absolute dollar limits for individual trades and daily exposure.

Requirements:
- Prevent any single trade >$10,000 equivalent
- Prevent daily exposure >$50,000 equivalent
- Multi-currency support with USD conversion
- Real-time compliance monitoring
- Comprehensive audit trail

Test Categories:
- Single trade size validation
- Daily exposure accumulation
- Multi-currency conversion accuracy
- Edge case handling
- Integration with existing risk system
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from fxml4.core.exceptions import RiskError, ValidationError
from fxml4.risk_management.trade_size_validator import (
    DailyExposureTracker,
    TradeSizeComplianceStatus,
    TradeSizeValidationResult,
    TradeSizeValidator,
    TradeSizeViolation,
    TradeSizeViolationType,
)


@pytest.fixture
def mock_currency_converter():
    """Mock currency converter for testing."""
    converter = AsyncMock()

    # USD conversion rates (mocked)
    conversion_rates = {
        "GBP": 1.25,  # 1 GBP = 1.25 USD
        "EUR": 1.10,  # 1 EUR = 1.10 USD
        "JPY": 0.007,  # 1 JPY = 0.007 USD
        "CHF": 1.05,  # 1 CHF = 1.05 USD
        "USD": 1.00,  # 1 USD = 1.00 USD
    }

    async def mock_convert_to_usd(amount, from_currency):
        rate = conversion_rates.get(from_currency, 1.0)
        return float(amount * rate)

    converter.convert_to_usd.side_effect = mock_convert_to_usd
    return converter


@pytest.fixture
def mock_ib_adapter():
    """Mock Interactive Brokers adapter for testing."""
    adapter = AsyncMock()

    # Mock account info
    adapter.get_account_info.return_value = {
        "TotalCashValue": "100000",  # $100,000 account balance
        "Currency": "USD",
    }

    # Mock market data (standard forex prices)
    market_prices = {
        "GBPUSD": {"price": "1.2500"},  # 1 GBP = 1.25 USD
        "EURUSD": {"price": "1.1000"},  # 1 EUR = 1.10 USD
        "USDJPY": {"price": "150.00"},  # 1 USD = 150 JPY
        "USDCHF": {"price": "0.9500"},  # 1 USD = 0.95 CHF
    }

    async def mock_get_market_data(symbol):
        return market_prices.get(symbol, {"price": "1.0000"})

    adapter.get_market_data.side_effect = mock_get_market_data
    return adapter


@pytest.fixture
def trade_size_validator(mock_currency_converter, mock_ib_adapter):
    """Create configured trade size validator for testing."""
    config = {
        "max_single_trade_usd": 10000.0,  # $10,000 max per trade
        "max_daily_exposure_usd": 50000.0,  # $50,000 max daily exposure
        "warning_threshold_percentage": 80.0,  # Warn at 80% of limits
    }

    async def _create_validator():
        validator = TradeSizeValidator(config)
        validator.currency_converter = mock_currency_converter
        validator.ib_adapter = mock_ib_adapter
        await validator.initialize()
        return validator

    return asyncio.get_event_loop().run_until_complete(_create_validator())


class TestSingleTradeValidation:
    """Test single trade size validation against $10,000 limit."""

    @pytest.mark.asyncio
    async def test_compliant_trade_under_limit(self, trade_size_validator):
        """Test that trades under $10,000 are approved."""
        # Test $5,000 GBPUSD trade (4,000 GBP * 1.25 = $5,000)
        result = await trade_size_validator.validate_single_trade(
            symbol="GBPUSD", trade_size=4000.0, side="BUY"  # 4,000 GBP
        )

        assert result.status == TradeSizeComplianceStatus.COMPLIANT
        assert result.trade_value_usd == pytest.approx(5000.0, abs=1.0)
        assert result.is_compliant
        assert len(result.violations) == 0
        assert "approved" in result.message.lower()

    @pytest.mark.asyncio
    async def test_violation_trade_over_limit(self, trade_size_validator):
        """Test that trades over $10,000 are rejected."""
        # Test $15,000 EURUSD trade (15,000 EUR * 1.10 = $16,500)
        result = await trade_size_validator.validate_single_trade(
            symbol="EURUSD", trade_size=15000.0, side="SELL"  # 15,000 EUR
        )

        assert result.status == TradeSizeComplianceStatus.VIOLATION
        assert result.trade_value_usd == pytest.approx(16500.0, abs=1.0)
        assert not result.is_compliant
        assert len(result.violations) == 1
        assert (
            result.violations[0].violation_type
            == TradeSizeViolationType.SINGLE_TRADE_EXCEEDED
        )
        assert "exceeds maximum" in result.violations[0].message.lower()

    @pytest.mark.asyncio
    async def test_exact_limit_boundary(self, trade_size_validator):
        """Test trade exactly at $10,000 limit."""
        # Test exactly $10,000 GBPUSD trade (8,000 GBP * 1.25 = $10,000)
        result = await trade_size_validator.validate_single_trade(
            symbol="GBPUSD", trade_size=8000.0, side="BUY"  # 8,000 GBP
        )

        assert result.status == TradeSizeComplianceStatus.COMPLIANT
        assert result.trade_value_usd == pytest.approx(10000.0, abs=1.0)
        assert result.is_compliant
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_warning_threshold_approaching_limit(self, trade_size_validator):
        """Test warning when approaching $10,000 limit (80% = $8,000)."""
        # Test $9,000 trade (should trigger warning)
        result = await trade_size_validator.validate_single_trade(
            symbol="GBPUSD", trade_size=7200.0, side="BUY"  # 7,200 GBP * 1.25 = $9,000
        )

        assert result.status == TradeSizeComplianceStatus.WARNING
        assert result.trade_value_usd == pytest.approx(9000.0, abs=1.0)
        assert result.is_compliant  # Still compliant but with warning
        assert len(result.warnings) == 1
        assert "approaching limit" in result.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_multi_currency_conversion_accuracy(self, trade_size_validator):
        """Test accurate USD conversion for different currencies."""
        test_cases = [
            # (symbol, trade_size, expected_usd_value)
            ("GBPUSD", 4000.0, 5000.0),  # 4,000 GBP * 1.25 = $5,000
            ("EURUSD", 5000.0, 5500.0),  # 5,000 EUR * 1.10 = $5,500
            ("USDJPY", 150000.0, 1050.0),  # 150,000 JPY * 0.007 = $1,050
            ("USDCHF", 5000.0, 5250.0),  # 5,000 CHF * 1.05 = $5,250
        ]

        for symbol, trade_size, expected_usd in test_cases:
            result = await trade_size_validator.validate_single_trade(
                symbol=symbol, trade_size=trade_size, side="BUY"
            )

            assert result.trade_value_usd == pytest.approx(
                expected_usd, abs=10.0
            ), f"Failed for {symbol}: expected ${expected_usd}, got ${result.trade_value_usd}"
            assert result.is_compliant


class TestDailyExposureValidation:
    """Test daily exposure accumulation against $50,000 limit."""

    @pytest.mark.asyncio
    async def test_daily_exposure_accumulation(self, trade_size_validator):
        """Test that daily exposure accumulates correctly across multiple trades."""
        # Execute multiple trades throughout the day
        trades = [
            ("GBPUSD", 4000.0, "BUY"),  # $5,000
            ("EURUSD", 3636.0, "SELL"),  # $4,000
            ("USDJPY", 71428.0, "BUY"),  # $500
            ("USDCHF", 4762.0, "SELL"),  # $5,000
        ]

        total_expected_exposure = 0.0

        for symbol, trade_size, side in trades:
            result = await trade_size_validator.validate_trade_with_daily_exposure(
                symbol=symbol, trade_size=trade_size, side=side
            )

            assert result.is_compliant, f"Trade {symbol} should be compliant"

            # Calculate expected exposure for this trade
            if symbol == "GBPUSD":
                trade_value = trade_size * 1.25
            elif symbol == "EURUSD":
                trade_value = trade_size * 1.10
            elif symbol == "USDJPY":
                trade_value = trade_size * 0.007
            elif symbol == "USDCHF":
                trade_value = trade_size * 1.05

            total_expected_exposure += trade_value

            # Check accumulated exposure
            assert result.current_daily_exposure == pytest.approx(
                total_expected_exposure, abs=10.0
            )
            assert result.current_daily_exposure < 50000.0  # Under $50K limit

    @pytest.mark.asyncio
    async def test_daily_exposure_violation(self, trade_size_validator):
        """Test that daily exposure over $50,000 is rejected."""
        # First, use up most of daily limit with large trades
        large_trades = [
            ("GBPUSD", 16000.0, "BUY"),  # $20,000
            ("EURUSD", 18181.0, "SELL"),  # $20,000
        ]

        for symbol, trade_size, side in large_trades:
            result = await trade_size_validator.validate_trade_with_daily_exposure(
                symbol=symbol, trade_size=trade_size, side=side
            )
            assert result.is_compliant, f"Setup trade {symbol} should be compliant"

        # Now attempt a trade that would exceed $50K daily limit
        # Current exposure: $40,000, attempting $15,000 more = $55,000 total
        violation_result = (
            await trade_size_validator.validate_trade_with_daily_exposure(
                symbol="USDCHF", trade_size=14285.0, side="BUY"  # ~$15,000
            )
        )

        assert violation_result.status == TradeSizeComplianceStatus.VIOLATION
        assert not violation_result.is_compliant
        assert len(violation_result.violations) == 1
        assert (
            violation_result.violations[0].violation_type
            == TradeSizeViolationType.DAILY_EXPOSURE_EXCEEDED
        )
        assert violation_result.current_daily_exposure > 50000.0

    @pytest.mark.asyncio
    async def test_daily_exposure_reset_at_midnight(self, trade_size_validator):
        """Test that daily exposure resets at midnight."""
        # Execute large trade
        result1 = await trade_size_validator.validate_trade_with_daily_exposure(
            symbol="GBPUSD", trade_size=32000.0, side="BUY"  # $40,000
        )

        assert result1.is_compliant
        assert result1.current_daily_exposure == pytest.approx(40000.0, abs=100.0)

        # Simulate day change (mock the daily exposure tracker)
        with patch.object(
            trade_size_validator.daily_tracker,
            "get_current_daily_exposure",
            return_value=0.0,
        ):
            # Should be able to trade large amount again after reset
            result2 = await trade_size_validator.validate_trade_with_daily_exposure(
                symbol="EURUSD", trade_size=36363.0, side="SELL"  # $40,000
            )

            assert result2.is_compliant

    @pytest.mark.asyncio
    async def test_daily_exposure_warning_threshold(self, trade_size_validator):
        """Test warning when approaching $50,000 daily limit (80% = $40,000)."""
        # Execute trades totaling ~$42,000 (should trigger warning)
        result = await trade_size_validator.validate_trade_with_daily_exposure(
            symbol="GBPUSD", trade_size=33600.0, side="BUY"  # $42,000
        )

        assert result.status == TradeSizeComplianceStatus.WARNING
        assert result.is_compliant  # Still compliant but with warning
        assert len(result.warnings) == 1
        assert "daily exposure approaching" in result.warnings[0].lower()
        assert result.current_daily_exposure == pytest.approx(42000.0, abs=100.0)


class TestIntegratedValidation:
    """Test integrated validation with both single trade and daily exposure limits."""

    @pytest.mark.asyncio
    async def test_both_limits_enforced_simultaneously(self, trade_size_validator):
        """Test that both single trade and daily exposure limits are enforced."""
        # Attempt a single trade that violates both limits
        # $60,000 trade exceeds both $10K single trade and $50K daily limits
        result = await trade_size_validator.validate_complete_trade_compliance(
            symbol="GBPUSD", trade_size=48000.0, side="BUY"  # $60,000
        )

        assert result.status == TradeSizeComplianceStatus.VIOLATION
        assert not result.is_compliant
        assert len(result.violations) == 2  # Both violations present

        violation_types = [v.violation_type for v in result.violations]
        assert TradeSizeViolationType.SINGLE_TRADE_EXCEEDED in violation_types
        assert TradeSizeViolationType.DAILY_EXPOSURE_EXCEEDED in violation_types

    @pytest.mark.asyncio
    async def test_daily_exposure_prevents_compliant_single_trades(
        self, trade_size_validator
    ):
        """Test that daily exposure limit can prevent otherwise compliant single trades."""
        # First, exhaust most of daily limit
        for i in range(5):
            result = await trade_size_validator.validate_trade_with_daily_exposure(
                symbol="GBPUSD",
                trade_size=8000.0,  # $10,000 each (at single trade limit)
                side="BUY",
            )
            assert result.is_compliant

        # Current daily exposure: $50,000 (at limit)

        # Now attempt another $10K trade (compliant for single trade but violates daily)
        final_result = await trade_size_validator.validate_complete_trade_compliance(
            symbol="EURUSD", trade_size=9090.0, side="SELL"  # $10,000
        )

        assert final_result.status == TradeSizeComplianceStatus.VIOLATION
        assert not final_result.is_compliant
        assert len(final_result.violations) == 1
        assert (
            final_result.violations[0].violation_type
            == TradeSizeViolationType.DAILY_EXPOSURE_EXCEEDED
        )


class TestAuditTrailAndReporting:
    """Test audit trail and compliance reporting functionality."""

    @pytest.mark.asyncio
    async def test_violation_audit_trail(self, trade_size_validator):
        """Test that violations are properly recorded in audit trail."""
        # Execute violating trade
        result = await trade_size_validator.validate_complete_trade_compliance(
            symbol="GBPUSD",
            trade_size=16000.0,  # $20,000 (violates $10K limit)
            side="BUY",
        )

        assert not result.is_compliant

        # Check audit trail
        violations = await trade_size_validator.get_violations_history()
        assert len(violations) >= 1

        latest_violation = violations[-1]
        assert latest_violation.symbol == "GBPUSD"
        assert latest_violation.attempted_trade_size == 16000.0
        assert (
            latest_violation.violation_type
            == TradeSizeViolationType.SINGLE_TRADE_EXCEEDED
        )
        assert latest_violation.trade_rejected is True

    @pytest.mark.asyncio
    async def test_compliance_report_generation(self, trade_size_validator):
        """Test generation of comprehensive compliance report."""
        # Execute mix of compliant and non-compliant trades
        test_trades = [
            ("GBPUSD", 4000.0, "BUY"),  # $5K - compliant
            ("EURUSD", 15000.0, "SELL"),  # $16.5K - violation
            ("USDJPY", 71428.0, "BUY"),  # $500 - compliant
            ("USDCHF", 20000.0, "SELL"),  # $21K - violation
        ]

        for symbol, trade_size, side in test_trades:
            await trade_size_validator.validate_complete_trade_compliance(
                symbol=symbol, trade_size=trade_size, side=side
            )

        # Generate compliance report
        report = await trade_size_validator.generate_compliance_report()

        assert report.total_validations == 4
        assert report.total_violations == 2
        assert report.compliance_rate == 50.0  # 2/4 = 50%
        assert not report.is_fully_compliant
        assert len(report.violations) == 2

    @pytest.mark.asyncio
    async def test_real_time_compliance_monitoring(self, trade_size_validator):
        """Test real-time compliance status monitoring."""
        # Check initial status
        status = await trade_size_validator.get_real_time_compliance_status()
        assert status["current_daily_exposure"] == 0.0
        assert status["compliance_status"] == "COMPLIANT"
        assert status["violations_today"] == 0

        # Execute compliant trade
        await trade_size_validator.validate_trade_with_daily_exposure(
            symbol="GBPUSD", trade_size=4000.0, side="BUY"
        )

        # Check updated status
        status = await trade_size_validator.get_real_time_compliance_status()
        assert status["current_daily_exposure"] == pytest.approx(5000.0, abs=10.0)
        assert status["compliance_status"] == "COMPLIANT"

        # Execute violating trade
        await trade_size_validator.validate_complete_trade_compliance(
            symbol="EURUSD", trade_size=15000.0, side="SELL"
        )

        # Check violation recorded
        status = await trade_size_validator.get_real_time_compliance_status()
        assert status["violations_today"] >= 1
        assert status["compliance_status"] in ["WARNING", "VIOLATION"]


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios."""

    @pytest.mark.asyncio
    async def test_zero_trade_size(self, trade_size_validator):
        """Test handling of zero trade size."""
        result = await trade_size_validator.validate_single_trade(
            symbol="GBPUSD", trade_size=0.0, side="BUY"
        )

        assert result.is_compliant
        assert result.trade_value_usd == 0.0
        assert "zero trade size" in result.message.lower()

    @pytest.mark.asyncio
    async def test_negative_trade_size(self, trade_size_validator):
        """Test handling of negative trade size."""
        with pytest.raises(ValidationError):
            await trade_size_validator.validate_single_trade(
                symbol="GBPUSD", trade_size=-1000.0, side="BUY"
            )

    @pytest.mark.asyncio
    async def test_invalid_currency_pair(self, trade_size_validator):
        """Test handling of invalid currency pair."""
        with pytest.raises(ValidationError):
            await trade_size_validator.validate_single_trade(
                symbol="INVALID", trade_size=1000.0, side="BUY"
            )

    @pytest.mark.asyncio
    async def test_currency_conversion_failure(self, trade_size_validator):
        """Test handling of currency conversion failures."""
        # Mock currency converter to raise exception
        trade_size_validator.currency_converter.convert_to_usd.side_effect = Exception(
            "Conversion failed"
        )

        with pytest.raises(ValidationError):
            await trade_size_validator.validate_single_trade(
                symbol="GBPUSD", trade_size=1000.0, side="BUY"
            )

    @pytest.mark.asyncio
    async def test_market_data_unavailable(self, trade_size_validator):
        """Test handling when market data is unavailable."""
        # Mock adapter to return invalid price
        trade_size_validator.ib_adapter.get_market_data.return_value = {"price": "0.0"}

        with pytest.raises(ValidationError):
            await trade_size_validator.validate_single_trade(
                symbol="GBPUSD", trade_size=1000.0, side="BUY"
            )


@pytest.mark.integration
class TestIntegrationWithExistingRiskSystem:
    """Test integration with existing percentage-based risk management system."""

    @pytest.mark.asyncio
    async def test_compatibility_with_existing_risk_manager(self, trade_size_validator):
        """Test that trade size validator works alongside existing risk manager."""
        # This would test integration with the existing RiskManagementValidator
        # to ensure both percentage and absolute limits are enforced
        pass

    @pytest.mark.asyncio
    async def test_consolidated_risk_reporting(self, trade_size_validator):
        """Test consolidated reporting across all risk management systems."""
        # This would test that both percentage-based and absolute limit
        # violations are reported in a unified compliance report
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
