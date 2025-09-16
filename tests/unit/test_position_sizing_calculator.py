"""
TDD Tests for Position Sizing Calculator - RED Phase
Comprehensive position sizing for risk management
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

# Import the calculator we're testing (will be created in GREEN phase)
from core.risk_management.position_sizing import PositionSizingCalculator


class TestPositionSizingCalculator:
    """
    TDD tests for Position Sizing Calculator following Red-Green-Refactor.
    Critical component for risk management in trading.
    """

    # ========== RED PHASE: Write Failing Tests First ==========

    def test_calculates_position_size_with_fixed_risk(self):
        """
        RED: Calculate position size based on fixed risk percentage
        Requirement: Risk only 2% of account per trade
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=10000, risk_percentage=2.0
        )

        # Calculate for a trade
        position = calculator.calculate_position_size(
            entry_price=1.1000, stop_loss=1.0950, symbol="EUR/USD"
        )

        # Assert
        # Risk = $200 (2% of $10,000)
        # Stop distance = 50 pips
        # Position size = $200 / 50 pips = 0.4 lots (40,000 units)
        assert position["lots"] == pytest.approx(0.4, abs=0.01)
        assert position["units"] == 40000
        assert position["risk_amount"] == 200.0
        assert position["stop_distance_pips"] == 50

    def test_respects_maximum_position_size(self):
        """
        RED: Never exceed maximum position size even if risk allows
        Requirement: Cap position size for risk management
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=100000,
            risk_percentage=2.0,
            max_position_size=1.0,  # Max 1 standard lot
        )

        # Very tight stop that would normally allow huge position
        position = calculator.calculate_position_size(
            entry_price=1.1000, stop_loss=1.0999, symbol="EUR/USD"  # 1 pip stop
        )

        # Assert - Should be capped at 1.0 lot
        assert position["lots"] == 1.0
        assert position["capped"] == True
        assert position["original_lots"] > 1.0

    def test_calculates_kelly_criterion_sizing(self):
        """
        RED: Use Kelly Criterion for optimal position sizing
        Requirement: Optimize growth rate based on win probability
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=10000, sizing_method="kelly"
        )

        # Calculate with win rate and risk/reward
        position = calculator.calculate_kelly_position(
            win_rate=0.60,  # 60% win rate
            avg_win=150.0,  # Average win $150
            avg_loss=100.0,  # Average loss $100
            confidence_factor=0.25,  # Use 25% of Kelly (conservative)
        )

        # Kelly formula: f = (p*b - q) / b
        # where p=0.6, q=0.4, b=1.5
        # f = (0.6*1.5 - 0.4) / 1.5 = 0.5 / 1.5 = 0.333
        # With 25% Kelly: 0.333 * 0.25 = 0.083 (8.3% of capital)
        assert position["kelly_percentage"] == pytest.approx(8.33, rel=0.01)
        assert position["position_value"] == pytest.approx(833, rel=1)

    def test_adjusts_for_correlation_risk(self):
        """
        RED: Adjust position size based on portfolio correlation
        Requirement: Reduce size when adding correlated positions
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=10000, risk_percentage=2.0
        )

        # Existing positions
        existing_positions = [
            {"symbol": "EUR/USD", "lots": 0.5, "correlation": 1.0},
            {"symbol": "GBP/USD", "lots": 0.3, "correlation": 0.8},
        ]

        # Calculate new position with correlation adjustment
        position = calculator.calculate_with_correlation(
            entry_price=1.2500,
            stop_loss=1.2450,
            symbol="GBP/USD",
            existing_positions=existing_positions,
        )

        # Assert - Position should be reduced due to correlation
        assert position["lots"] < 0.4  # Less than normal 2% risk
        assert position["correlation_adjustment"] > 0
        assert position["effective_risk"] < 2.0

    def test_implements_anti_martingale_sizing(self):
        """
        RED: Increase size after wins, decrease after losses
        Requirement: Anti-Martingale money management
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=10000,
            risk_percentage=2.0,
            sizing_strategy="anti_martingale",
        )

        # Recent trading results (wins and losses)
        recent_trades = [
            {"result": "win", "pnl": 150},
            {"result": "win", "pnl": 200},
            {"result": "win", "pnl": 100},
        ]

        # Calculate with anti-martingale adjustment
        position = calculator.calculate_anti_martingale(
            base_lots=0.5,
            recent_trades=recent_trades,
            increase_factor=1.5,
            decrease_factor=0.5,
        )

        # After 3 wins, should increase position
        assert position["adjusted_lots"] > 0.5
        assert position["streak_multiplier"] > 1.0
        assert position["strategy"] == "anti_martingale"

    def test_calculates_risk_parity_position(self):
        """
        RED: Size positions for equal risk contribution
        Requirement: Risk parity across portfolio
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=50000,
            target_portfolio_risk=10.0,  # 10% portfolio volatility target
        )

        # Calculate risk parity position
        position = calculator.calculate_risk_parity(
            symbol="EUR/USD",
            volatility=0.008,  # 0.8% daily volatility
            portfolio_positions=[
                {"symbol": "USD/JPY", "volatility": 0.006, "value": 20000},
                {"symbol": "GBP/USD", "volatility": 0.010, "value": 15000},
            ],
        )

        # Assert equal risk contribution
        assert position["risk_contribution"] == pytest.approx(3.33, rel=0.1)
        assert position["position_value"] > 0
        assert position["weight"] > 0

    def test_applies_volatility_based_sizing(self):
        """
        RED: Adjust position size based on market volatility
        Requirement: Smaller positions in volatile markets
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=10000, risk_percentage=2.0, use_volatility_sizing=True
        )

        # Calculate with current volatility vs average
        position = calculator.calculate_volatility_adjusted(
            entry_price=1.1000,
            stop_loss=1.0950,
            symbol="EUR/USD",
            current_atr=0.0080,  # Current ATR
            average_atr=0.0050,  # Historical average ATR
        )

        # Higher volatility should reduce position size
        volatility_ratio = 0.0080 / 0.0050  # 1.6x normal volatility
        assert position["volatility_multiplier"] == pytest.approx(0.625, rel=0.01)
        assert position["adjusted_lots"] < 0.4  # Less than normal size

    def test_respects_margin_requirements(self):
        """
        RED: Never exceed available margin
        Requirement: Prevent margin calls
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=5000,
            available_margin=1000,  # Only $1000 available
            leverage=50,
        )

        # Calculate position respecting margin
        position = calculator.calculate_with_margin_check(
            entry_price=1.1000, stop_loss=1.0950, symbol="EUR/USD"
        )

        # Assert position doesn't exceed available margin
        required_margin = position["units"] * 1.1000 / 50
        assert required_margin <= 1000
        assert position["margin_used"] <= 1000
        assert position["margin_limited"] == True

    def test_implements_pyramid_position_building(self):
        """
        RED: Build positions gradually (pyramiding)
        Requirement: Scale into winning positions
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=10000, risk_percentage=2.0, pyramiding_enabled=True
        )

        # Existing profitable position
        existing_position = {
            "symbol": "EUR/USD",
            "entry": 1.1000,
            "current_price": 1.1050,
            "lots": 0.3,
            "unrealized_pnl": 150,
        }

        # Calculate pyramid addition
        pyramid = calculator.calculate_pyramid_addition(
            existing_position=existing_position,
            new_entry=1.1040,
            new_stop=1.1020,
            max_pyramid_units=3,
        )

        # Assert pyramid rules
        assert pyramid["add_lots"] < existing_position["lots"]  # Smaller than initial
        assert pyramid["total_units"] <= 3  # Max 3 units
        assert pyramid["weighted_entry"] > existing_position["entry"]

    def test_calculates_optimal_f_position_sizing(self):
        """
        RED: Use Ralph Vince's Optimal f for position sizing
        Requirement: Maximize geometric growth rate
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=20000, sizing_method="optimal_f"
        )

        # Historical trade results
        trade_history = [200, -100, 150, -80, 300, -120, 180, -90, 250, -110]

        # Calculate Optimal f position
        position = calculator.calculate_optimal_f(
            trade_history=trade_history, safety_factor=0.5  # Use 50% of optimal f
        )

        # Assert
        assert position["optimal_f"] > 0
        assert position["optimal_f"] < 1.0
        assert position["risk_amount"] == pytest.approx(
            20000 * position["optimal_f"] * 0.5, rel=0.01
        )

    def test_adjusts_for_news_events(self):
        """
        RED: Reduce position size before high-impact news
        Requirement: Risk management around news events
        """
        # Arrange
        calculator = PositionSizingCalculator(
            account_balance=10000, risk_percentage=2.0, news_adjustment=True
        )

        # Calculate with upcoming news event
        position = calculator.calculate_with_news_adjustment(
            entry_price=1.1000,
            stop_loss=1.0950,
            symbol="EUR/USD",
            upcoming_news=[
                {"impact": "high", "currency": "EUR", "minutes_until": 30},
                {"impact": "medium", "currency": "USD", "minutes_until": 120},
            ],
        )

        # High impact news should reduce position
        assert position["news_multiplier"] < 1.0
        assert position["adjusted_lots"] < 0.4
        assert "high_impact_warning" in position

    def test_implements_fixed_ratio_money_management(self):
        """
        RED: Ryan Jones Fixed Ratio position sizing
        Requirement: Geometric position growth with profits
        """
        # Arrange
        calculator = PositionSizingCalculator(
            starting_balance=10000,
            current_balance=15000,
            sizing_method="fixed_ratio",
            delta=2000,  # Increase 1 contract per $2000 profit
        )

        # Calculate fixed ratio position
        position = calculator.calculate_fixed_ratio(
            base_units=1, min_units=1, max_units=10
        )

        # With $5000 profit and $2000 delta: 1 + (5000/2000) = 3.5 units
        assert position["units"] == 3  # Rounded down
        assert position["method"] == "fixed_ratio"
        assert position["profit_per_unit"] == 2000


class TestPositionSizingEdgeCases:
    """Test edge cases and error handling"""

    def test_handles_zero_stop_loss(self):
        """Handle invalid stop loss"""
        calculator = PositionSizingCalculator(account_balance=10000)

        with pytest.raises(ValueError, match="Invalid stop loss"):
            calculator.calculate_position_size(
                entry_price=1.1000, stop_loss=1.1000, symbol="EUR/USD"  # Same as entry
            )

    def test_handles_insufficient_balance(self):
        """Handle insufficient account balance"""
        calculator = PositionSizingCalculator(
            account_balance=100, risk_percentage=2.0  # Very small account
        )

        position = calculator.calculate_position_size(
            entry_price=1.1000, stop_loss=1.0950, symbol="EUR/USD"
        )

        assert position["lots"] == 0  # Cannot trade
        assert position["error"] == "Insufficient balance"

    def test_handles_negative_kelly_criterion(self):
        """Handle negative Kelly (don't trade)"""
        calculator = PositionSizingCalculator(
            account_balance=10000, sizing_method="kelly"
        )

        position = calculator.calculate_kelly_position(
            win_rate=0.30,  # Low win rate
            avg_win=100,
            avg_loss=150,  # Losses bigger than wins
            confidence_factor=0.25,
        )

        assert position["kelly_percentage"] == 0
        assert position["recommendation"] == "DO_NOT_TRADE"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=core.risk_management.position_sizing"])
