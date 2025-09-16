"""
TDD Tests for Stop Loss Calculator - RED Phase
Comprehensive stop loss calculations for risk management
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

# Import the calculator we're testing (will be created in GREEN phase)
from core.risk_management.stop_loss import StopLossCalculator


class TestStopLossCalculator:
    """
    TDD tests for Stop Loss Calculator following Red-Green-Refactor.
    Critical component for protecting trading capital.
    """

    # ========== RED PHASE: Write Failing Tests First ==========

    def test_calculates_fixed_pip_stop_loss(self):
        """
        RED: Calculate stop loss at fixed pip distance
        Requirement: Simple fixed pip stop loss for consistency
        """
        # Arrange
        calculator = StopLossCalculator(default_stop_pips=50, method="fixed_pips")

        # Calculate stop loss for long position
        stop_long = calculator.calculate_stop_loss(
            entry_price=1.1000, side="buy", symbol="EUR/USD"
        )

        # Calculate stop loss for short position
        stop_short = calculator.calculate_stop_loss(
            entry_price=1.1000, side="sell", symbol="EUR/USD"
        )

        # Assert
        assert stop_long["stop_loss"] == pytest.approx(1.0950, abs=0.0001)
        assert stop_long["distance_pips"] == 50
        assert stop_long["risk_reward_ratio"] is None  # No target provided

        assert stop_short["stop_loss"] == pytest.approx(1.1050, abs=0.0001)
        assert stop_short["distance_pips"] == 50

    def test_calculates_atr_based_stop_loss(self):
        """
        RED: Calculate stop loss based on Average True Range
        Requirement: Dynamic stops that adjust to market volatility
        """
        # Arrange
        calculator = StopLossCalculator(method="atr_based", atr_multiplier=2.0)

        # Calculate with current ATR
        stop = calculator.calculate_atr_stop(
            entry_price=1.1000,
            side="buy",
            current_atr=0.0080,  # 80 pip ATR
            symbol="EUR/USD",
        )

        # Assert - Stop at 2x ATR = 160 pips
        assert stop["stop_loss"] == pytest.approx(1.0840, abs=0.0001)
        assert stop["distance_pips"] == pytest.approx(160, abs=1)
        assert stop["atr_value"] == 0.0080
        assert stop["multiplier"] == 2.0

    def test_calculates_percentage_based_stop(self):
        """
        RED: Calculate stop loss at percentage distance
        Requirement: Percentage-based stops for stocks/indices
        """
        # Arrange
        calculator = StopLossCalculator(
            method="percentage", stop_percentage=2.5  # 2.5% stop
        )

        # Calculate percentage stop
        stop = calculator.calculate_percentage_stop(
            entry_price=150.00, side="buy", symbol="SPX500"
        )

        # Assert - 2.5% below entry
        assert stop["stop_loss"] == pytest.approx(146.25, abs=0.01)
        assert stop["percentage"] == 2.5
        assert stop["dollar_risk"] == 3.75

    def test_calculates_support_resistance_stop(self):
        """
        RED: Place stop loss below support/above resistance
        Requirement: Technical analysis-based stop placement
        """
        # Arrange
        calculator = StopLossCalculator(method="support_resistance")

        # Recent price levels
        price_data = {
            "recent_low": 1.0920,
            "recent_high": 1.1080,
            "support_levels": [1.0950, 1.0900, 1.0850],
            "resistance_levels": [1.1050, 1.1100, 1.1150],
        }

        # Calculate for long position (below support)
        stop_long = calculator.calculate_technical_stop(
            entry_price=1.1000, side="buy", price_data=price_data, buffer_pips=5
        )

        # Calculate for short position (above resistance)
        stop_short = calculator.calculate_technical_stop(
            entry_price=1.1000, side="sell", price_data=price_data, buffer_pips=5
        )

        # Assert
        assert stop_long["stop_loss"] == pytest.approx(
            1.0945, abs=0.0001
        )  # 5 pips below support
        assert stop_long["based_on"] == "support"
        assert stop_long["level_used"] == 1.0950

        assert stop_short["stop_loss"] == pytest.approx(
            1.1055, abs=0.0001
        )  # 5 pips above resistance
        assert stop_short["based_on"] == "resistance"
        assert stop_short["level_used"] == 1.1050

    def test_calculates_time_based_stop(self):
        """
        RED: Exit position after specific time period
        Requirement: Time-based exits for day trading
        """
        # Arrange
        calculator = StopLossCalculator(method="time_based", max_hold_hours=4)

        # Position opened at 10 AM
        entry_time = datetime(2025, 1, 15, 10, 0, 0)
        current_time = datetime(2025, 1, 15, 14, 30, 0)  # 4.5 hours later

        # Check if time stop triggered
        result = calculator.check_time_stop(
            entry_time=entry_time,
            current_time=current_time,
            entry_price=1.1000,
            current_price=1.0980,  # Small loss
        )

        # Assert
        assert result["stop_triggered"] == True
        assert result["hours_held"] == 4.5
        assert result["reason"] == "max_hold_time_exceeded"

    def test_implements_breakeven_stop(self):
        """
        RED: Move stop to breakeven after profit target
        Requirement: Protect profits by moving stop to entry
        """
        # Arrange
        calculator = StopLossCalculator(
            enable_breakeven=True, breakeven_trigger_pips=30
        )

        # Position with 40 pips profit
        result = calculator.adjust_to_breakeven(
            entry_price=1.1000,
            current_price=1.1040,
            side="buy",
            current_stop=1.0950,
            buffer_pips=2,
        )

        # Assert - Stop moved to breakeven + buffer
        assert result["new_stop"] == pytest.approx(1.1002, abs=0.0001)
        assert result["moved_to_breakeven"] == True
        assert result["profit_pips"] == 40

    def test_calculates_trailing_stop_loss(self):
        """
        RED: Implement trailing stop that follows price
        Requirement: Dynamic stop adjustment in profitable trades
        """
        # Arrange
        calculator = StopLossCalculator(method="trailing", trailing_distance_pips=25)

        # Update trailing stop with price movement
        result = calculator.update_trailing_stop(
            entry_price=1.1000,
            highest_price=1.1080,  # 80 pip high
            current_price=1.1060,
            side="buy",
            current_stop=1.1030,
        )

        # Assert - Stop trails 25 pips from high
        assert result["new_stop"] == pytest.approx(1.1055, abs=0.0001)
        assert result["stop_moved"] == True
        assert result["distance_from_high"] == 25

    def test_calculates_chandelier_exit_stop(self):
        """
        RED: Chandelier Exit (ATR from highest high)
        Requirement: Volatility-adjusted trailing stop
        """
        # Arrange
        calculator = StopLossCalculator(method="chandelier", atr_multiplier=3.0)

        # Calculate Chandelier Exit
        result = calculator.calculate_chandelier_exit(
            highest_high=1.1100, current_atr=0.0060, side="buy"  # 60 pip ATR
        )

        # Assert - 3 ATRs below highest high
        assert result["stop_loss"] == pytest.approx(1.0920, abs=0.0001)
        assert result["distance_from_high"] == pytest.approx(180, abs=1)

    def test_calculates_parabolic_sar_stop(self):
        """
        RED: Parabolic SAR stop calculation
        Requirement: Trend-following stop system
        """
        # Arrange
        calculator = StopLossCalculator(method="parabolic_sar")

        # Calculate PSAR
        result = calculator.calculate_parabolic_sar(
            prices=[1.0950, 1.1000, 1.1050, 1.1080, 1.1060],
            highs=[1.0960, 1.1010, 1.1060, 1.1090, 1.1070],
            lows=[1.0940, 1.0990, 1.1040, 1.1070, 1.1050],
            acceleration_factor=0.02,
            max_acceleration=0.20,
        )

        # Assert
        assert result["sar_value"] > 0
        assert result["position_side"] in ["long", "short"]
        assert "acceleration_factor" in result

    def test_calculates_risk_reward_adjusted_stop(self):
        """
        RED: Adjust stop based on risk/reward ratio
        Requirement: Ensure minimum R:R ratio
        """
        # Arrange
        calculator = StopLossCalculator(min_risk_reward=2.0)  # Minimum 1:2 R:R

        # Calculate stop with profit target
        result = calculator.calculate_rr_adjusted_stop(
            entry_price=1.1000,
            target_price=1.1100,  # 100 pip target
            side="buy",
            max_stop_distance=60,  # Max 60 pips risk
        )

        # Assert - Stop ensures 1:2 R:R (50 pip stop for 100 pip target)
        assert result["stop_loss"] == pytest.approx(1.0950, abs=0.0001)
        assert result["risk_pips"] == 50
        assert result["reward_pips"] == 100
        assert result["risk_reward_ratio"] == 2.0

    def test_calculates_volatility_adjusted_stop(self):
        """
        RED: Adjust stop distance based on market conditions
        Requirement: Wider stops in volatile markets
        """
        # Arrange
        calculator = StopLossCalculator(base_stop_pips=50)

        # Calculate with high volatility
        result = calculator.calculate_volatility_adjusted(
            entry_price=1.1000,
            side="buy",
            current_volatility=0.015,  # 1.5% daily volatility
            average_volatility=0.008,  # 0.8% average
            symbol="EUR/USD",
        )

        # Assert - Stop widened due to high volatility
        volatility_ratio = 0.015 / 0.008  # 1.875x
        expected_stop_pips = 50 * volatility_ratio  # ~94 pips
        assert result["stop_pips"] == pytest.approx(94, abs=1)
        assert result["volatility_multiplier"] == pytest.approx(1.875, abs=0.01)

    def test_implements_guaranteed_stop_loss(self):
        """
        RED: Guaranteed stop loss (GSL) for gap protection
        Requirement: Protection against weekend/news gaps
        """
        # Arrange
        calculator = StopLossCalculator(
            enable_guaranteed_stops=True,
            gsl_premium_pips=2,  # 2 pip premium for guarantee
        )

        # Calculate guaranteed stop
        result = calculator.calculate_guaranteed_stop(
            entry_price=1.1000, requested_stop=1.0950, side="buy", symbol="EUR/USD"
        )

        # Assert
        assert result["guaranteed_stop"] == 1.0950
        assert result["premium_pips"] == 2
        assert result["additional_cost"] == True
        assert result["gap_protection"] == True

    def test_calculates_multi_timeframe_stop(self):
        """
        RED: Combine stops from multiple timeframes
        Requirement: Respect both short and long-term levels
        """
        # Arrange
        calculator = StopLossCalculator(method="multi_timeframe")

        # Stops from different timeframes
        timeframe_data = {
            "M5": {"stop": 1.0970, "strength": 0.3},
            "H1": {"stop": 1.0950, "strength": 0.5},
            "D1": {"stop": 1.0920, "strength": 0.8},
        }

        # Calculate combined stop
        result = calculator.calculate_multi_tf_stop(
            entry_price=1.1000,
            side="buy",
            timeframe_data=timeframe_data,
            weight_by_strength=True,
        )

        # Assert - Weighted average favoring higher timeframes
        assert result["combined_stop"] < 1.0950  # Influenced by daily
        assert result["primary_timeframe"] == "D1"
        assert len(result["timeframes_used"]) == 3

    def test_handles_stop_hunting_protection(self):
        """
        RED: Avoid obvious stop levels to prevent stop hunting
        Requirement: Place stops away from round numbers
        """
        # Arrange
        calculator = StopLossCalculator(
            avoid_round_numbers=True, round_number_buffer_pips=3
        )

        # Calculate stop avoiding round numbers
        result = calculator.calculate_anti_hunt_stop(
            entry_price=1.1000,
            initial_stop=1.0950,  # Round number
            side="buy",
            symbol="EUR/USD",
        )

        # Assert - Stop adjusted away from 1.0950
        assert result["adjusted_stop"] != 1.0950
        assert result["adjusted_stop"] == pytest.approx(1.0947, abs=0.0001)
        assert result["reason"] == "round_number_avoidance"

    def test_validates_minimum_stop_distance(self):
        """
        RED: Enforce minimum stop distance for viability
        Requirement: Prevent stops that are too tight
        """
        # Arrange
        calculator = StopLossCalculator(min_stop_distance_pips=10)

        # Try to set stop too close
        with pytest.raises(ValueError, match="Stop too close"):
            calculator.validate_stop_distance(
                entry_price=1.1000,
                stop_loss=1.0995,  # Only 5 pips
                side="buy",
                symbol="EUR/USD",
            )


class TestStopLossEdgeCases:
    """Test edge cases and error handling"""

    def test_handles_invalid_side(self):
        """Handle invalid position side"""
        calculator = StopLossCalculator()

        with pytest.raises(ValueError, match="Invalid side"):
            calculator.calculate_stop_loss(
                entry_price=1.1000, side="invalid", symbol="EUR/USD"
            )

    def test_handles_zero_atr(self):
        """Handle zero ATR (no volatility)"""
        calculator = StopLossCalculator(method="atr_based")

        # Should fall back to minimum stop
        result = calculator.calculate_atr_stop(
            entry_price=1.1000, side="buy", current_atr=0.0, symbol="EUR/USD"
        )

        assert result["stop_loss"] > 0
        assert result["fallback_used"] == True

    def test_handles_weekend_gap_scenario(self):
        """Handle weekend gap risk"""
        calculator = StopLossCalculator()

        # Friday close position
        result = calculator.assess_gap_risk(
            entry_time=datetime(2025, 1, 17, 20, 0, 0),  # Friday 8 PM
            symbol="EUR/USD",
            current_stop=1.0950,
        )

        assert result["gap_risk"] == "high"
        assert result["recommendation"] == "consider_guaranteed_stop"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=core.risk_management.stop_loss"])
