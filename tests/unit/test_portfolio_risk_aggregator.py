"""
TDD Tests for Portfolio Risk Aggregator - RED Phase
Comprehensive portfolio risk calculation and monitoring
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List
from unittest.mock import Mock, patch

import pytest

# Import the aggregator we're testing (will be created in GREEN phase)
from core.risk_management.portfolio_risk import PortfolioRiskAggregator


class TestPortfolioRiskAggregator:
    """
    TDD tests for Portfolio Risk Aggregator following Red-Green-Refactor.
    Critical component for portfolio-level risk management.
    """

    # ========== RED PHASE: Write Failing Tests First ==========

    def test_calculates_total_portfolio_risk(self):
        """
        RED: Calculate total risk exposure across all positions
        Requirement: Aggregate risk from multiple positions
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(
            account_balance=100000, max_portfolio_risk=10.0  # 10% max portfolio risk
        )

        positions = [
            {
                "symbol": "EUR/USD",
                "side": "buy",
                "quantity": 1.0,
                "entry_price": 1.1000,
                "stop_loss": 1.0950,
                "position_value": 110000,
                "risk_amount": 500,
            },
            {
                "symbol": "GBP/USD",
                "side": "sell",
                "quantity": 0.5,
                "entry_price": 1.2500,
                "stop_loss": 1.2600,
                "position_value": 62500,
                "risk_amount": 250,
            },
        ]

        # Act
        portfolio_risk = aggregator.calculate_total_risk(positions)

        # Assert
        assert portfolio_risk["total_risk_amount"] == 750  # 500 + 250
        assert portfolio_risk["total_portfolio_value"] == 172500  # 110000 + 62500
        assert portfolio_risk["risk_percentage"] == pytest.approx(
            0.75, abs=0.01
        )  # 750/100000
        assert portfolio_risk["positions_count"] == 2

    def test_calculates_correlation_adjusted_risk(self):
        """
        RED: Adjust risk based on correlation between positions
        Requirement: Account for diversification benefits
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(account_balance=50000)

        positions = [
            {"symbol": "EUR/USD", "risk_amount": 500, "quantity": 1.0},
            {"symbol": "GBP/USD", "risk_amount": 300, "quantity": 0.5},
            {"symbol": "USD/JPY", "risk_amount": 400, "quantity": 0.8},
        ]

        # Correlation matrix
        correlation_matrix = {
            ("EUR/USD", "GBP/USD"): 0.85,  # High correlation
            ("EUR/USD", "USD/JPY"): -0.30,  # Negative correlation
            ("GBP/USD", "USD/JPY"): -0.25,  # Negative correlation
        }

        # Act
        adjusted_risk = aggregator.calculate_correlation_adjusted_risk(
            positions, correlation_matrix
        )

        # Assert
        # With correlations, total risk should be less than sum (1200)
        assert adjusted_risk["raw_risk"] == 1200  # 500 + 300 + 400
        assert adjusted_risk["correlation_adjusted_risk"] < 1200
        assert adjusted_risk["diversification_benefit"] > 0
        assert adjusted_risk["effective_risk_reduction"] > 0

    def test_calculates_var_portfolio_risk(self):
        """
        RED: Calculate Value at Risk (VaR) for portfolio
        Requirement: Statistical risk measurement
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(
            account_balance=100000,
            var_confidence=0.95,  # 95% confidence
            var_horizon_days=1,  # 1-day VaR
        )

        # Historical returns for portfolio components
        historical_returns = {
            "EUR/USD": [-0.02, 0.015, -0.008, 0.012, -0.018, 0.009, -0.005],
            "GBP/USD": [-0.025, 0.018, -0.012, 0.015, -0.022, 0.011, -0.007],
            "USD/JPY": [0.018, -0.010, 0.008, -0.015, 0.020, -0.009, 0.006],
        }

        positions = [
            {"symbol": "EUR/USD", "position_value": 110000, "weight": 0.5},
            {"symbol": "GBP/USD", "position_value": 62500, "weight": 0.3},
            {"symbol": "USD/JPY", "position_value": 55000, "weight": 0.2},
        ]

        # Act
        var_result = aggregator.calculate_portfolio_var(positions, historical_returns)

        # Assert
        assert var_result["var_amount"] > 0
        assert var_result["var_percentage"] > 0
        assert var_result["confidence_level"] == 0.95
        assert var_result["horizon_days"] == 1
        assert "worst_case_loss" in var_result

    def test_calculates_concentration_risk(self):
        """
        RED: Identify concentration risk in portfolio
        Requirement: Prevent over-concentration in single positions
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(
            max_single_position=15.0,  # Max 15% in single position
            max_sector_concentration=30.0,  # Max 30% in single sector
        )

        positions = [
            {
                "symbol": "EUR/USD",
                "position_value": 25000,
                "sector": "forex_major",
                "risk_amount": 500,
            },
            {
                "symbol": "GBP/USD",
                "position_value": 20000,
                "sector": "forex_major",
                "risk_amount": 400,
            },
            {
                "symbol": "AUD/USD",
                "position_value": 15000,
                "sector": "forex_major",
                "risk_amount": 300,
            },
        ]

        portfolio_value = 100000

        # Act
        concentration = aggregator.calculate_concentration_risk(
            positions, portfolio_value
        )

        # Assert
        assert concentration["largest_position_pct"] == 25.0  # EUR/USD
        assert concentration["forex_major_concentration"] == 60.0  # 60% in forex majors
        assert concentration["concentration_warning"] == True
        assert concentration["over_concentrated_sectors"] == ["forex_major"]

    def test_calculates_leverage_exposure(self):
        """
        RED: Calculate total leverage exposure across positions
        Requirement: Monitor leverage limits
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(
            account_balance=50000, max_total_leverage=10.0  # Max 10:1 total leverage
        )

        positions = [
            {
                "symbol": "EUR/USD",
                "position_value": 220000,  # 2.2M notional
                "margin_used": 4400,  # 50:1 leverage
                "leverage": 50,
            },
            {
                "symbol": "GBP/USD",
                "position_value": 125000,  # 1.25M notional
                "margin_used": 2500,  # 50:1 leverage
                "leverage": 50,
            },
        ]

        # Act
        leverage_exposure = aggregator.calculate_leverage_exposure(positions)

        # Assert
        assert leverage_exposure["total_notional"] == 345000  # 220k + 125k
        assert leverage_exposure["total_margin_used"] == 6900  # 4400 + 2500
        assert leverage_exposure["effective_leverage"] == pytest.approx(
            6.9, abs=0.1
        )  # 345k/50k
        assert leverage_exposure["margin_utilization"] == pytest.approx(
            13.8, abs=0.1
        )  # 6900/50k

    def test_validates_risk_limits(self):
        """
        RED: Validate portfolio against risk limits
        Requirement: Enforce risk management rules
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(
            account_balance=100000,
            max_portfolio_risk=5.0,  # 5% max portfolio risk
            max_daily_loss=2.0,  # 2% max daily loss
            max_single_position=10.0,  # 10% max single position
            max_correlation_exposure=25.0,  # 25% max correlated exposure
        )

        positions = [
            {
                "symbol": "EUR/USD",
                "position_value": 15000,  # 15% - over limit
                "risk_amount": 600,
                "daily_pnl": -1500,
            }
        ]

        current_daily_pnl = -2500  # 2.5% loss - over limit

        # Act
        validation = aggregator.validate_risk_limits(positions, current_daily_pnl)

        # Assert
        assert validation["within_limits"] == False
        assert "single_position_breach" in validation["violations"]
        assert "daily_loss_breach" in validation["violations"]
        assert len(validation["violations"]) >= 2

    def test_calculates_margin_to_equity_ratio(self):
        """
        RED: Calculate margin utilization relative to equity
        Requirement: Monitor margin safety
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(
            account_balance=100000,
            warning_margin_ratio=50.0,  # Warning at 50% margin utilization
            critical_margin_ratio=80.0,  # Critical at 80% margin utilization
        )

        positions = [
            {"margin_used": 25000, "symbol": "EUR/USD"},
            {"margin_used": 15000, "symbol": "GBP/USD"},
            {"margin_used": 20000, "symbol": "USD/JPY"},
        ]

        current_equity = 110000  # Account balance + unrealized P&L

        # Act
        margin_analysis = aggregator.calculate_margin_analysis(
            positions, current_equity
        )

        # Assert
        assert margin_analysis["total_margin_used"] == 60000
        assert margin_analysis["margin_to_equity_ratio"] == pytest.approx(54.5, abs=0.1)
        assert margin_analysis["available_margin"] == 50000  # 110k - 60k
        assert margin_analysis["margin_level"] == "warning"  # Above 50%

    def test_calculates_sector_exposure(self):
        """
        RED: Calculate exposure by sector/asset class
        Requirement: Diversification monitoring
        """
        # Arrange
        aggregator = PortfolioRiskAggregator()

        positions = [
            {"symbol": "EUR/USD", "sector": "forex_major", "position_value": 50000},
            {"symbol": "GBP/USD", "sector": "forex_major", "position_value": 30000},
            {"symbol": "AUD/CAD", "sector": "forex_cross", "position_value": 20000},
            {"symbol": "XAUUSD", "sector": "commodities", "position_value": 25000},
        ]

        total_portfolio_value = 125000

        # Act
        sector_exposure = aggregator.calculate_sector_exposure(
            positions, total_portfolio_value
        )

        # Assert
        assert sector_exposure["forex_major"]["value"] == 80000
        assert sector_exposure["forex_major"]["percentage"] == 64.0
        assert sector_exposure["forex_cross"]["percentage"] == 16.0
        assert sector_exposure["commodities"]["percentage"] == 20.0

    def test_calculates_drawdown_risk(self):
        """
        RED: Calculate potential drawdown scenarios
        Requirement: Stress testing portfolio
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(account_balance=100000)

        positions = [
            {
                "symbol": "EUR/USD",
                "position_value": 55000,
                "stop_loss_risk": 500,
                "stress_scenario_loss": 1200,
            },
            {
                "symbol": "GBP/USD",
                "position_value": 45000,
                "stop_loss_risk": 400,
                "stress_scenario_loss": 1000,
            },
        ]

        # Act
        drawdown_analysis = aggregator.calculate_drawdown_scenarios(positions)

        # Assert
        assert (
            drawdown_analysis["normal_scenario"]["max_loss"] == 900
        )  # Sum of stop losses
        assert (
            drawdown_analysis["stress_scenario"]["max_loss"] == 2200
        )  # Sum of stress losses
        assert drawdown_analysis["normal_scenario"]["drawdown_pct"] < 1.0
        assert drawdown_analysis["stress_scenario"]["drawdown_pct"] > 2.0

    def test_monitors_real_time_risk_changes(self):
        """
        RED: Monitor risk changes as prices move
        Requirement: Real-time risk monitoring
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(account_balance=100000)

        initial_positions = [
            {
                "symbol": "EUR/USD",
                "entry_price": 1.1000,
                "current_price": 1.1000,
                "quantity": 1.0,
                "stop_loss": 1.0950,
            }
        ]

        updated_positions = [
            {
                "symbol": "EUR/USD",
                "entry_price": 1.1000,
                "current_price": 1.1030,  # Price moved up
                "quantity": 1.0,
                "stop_loss": 1.0950,
            }
        ]

        # Act
        risk_change = aggregator.calculate_risk_change(
            initial_positions, updated_positions
        )

        # Assert
        assert risk_change["price_change"]["EUR/USD"] == pytest.approx(
            0.0030, abs=0.0001
        )
        assert risk_change["unrealized_pnl_change"] == pytest.approx(
            30, abs=1
        )  # 30 pips * 1 lot * $1 per pip
        assert (
            risk_change["portfolio_risk_change"] < 0
        )  # Risk decreased (profit increases equity)

    def test_calculates_beta_adjusted_portfolio_risk(self):
        """
        RED: Calculate portfolio beta and systematic risk
        Requirement: Market risk exposure measurement
        """
        # Arrange
        aggregator = PortfolioRiskAggregator()

        positions = [
            {
                "symbol": "EUR/USD",
                "position_value": 60000,
                "beta": 1.2,  # 20% more volatile than market
                "weight": 0.6,
            },
            {
                "symbol": "USD/JPY",
                "position_value": 40000,
                "beta": 0.8,  # 20% less volatile than market
                "weight": 0.4,
            },
        ]

        market_volatility = 0.015  # 1.5% daily market volatility

        # Act
        beta_analysis = aggregator.calculate_portfolio_beta(
            positions, market_volatility
        )

        # Assert
        # Portfolio beta = 0.6 * 1.2 + 0.4 * 0.8 = 1.04
        assert beta_analysis["portfolio_beta"] == pytest.approx(1.04, abs=0.01)
        assert beta_analysis["systematic_risk"] > 0
        assert beta_analysis["market_correlation"] > 0

    def test_identifies_risk_hotspots(self):
        """
        RED: Identify areas of elevated risk in portfolio
        Requirement: Risk monitoring and alerts
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(
            account_balance=100000,
            risk_threshold_warning=3.0,  # 3% warning threshold
            risk_threshold_critical=5.0,  # 5% critical threshold
        )

        positions = [
            {
                "symbol": "EUR/USD",
                "risk_amount": 600,  # 0.6% risk
                "concentration": 25.0,  # 25% of portfolio
                "correlation_risk": "high",
                "leverage": 50,
            },
            {
                "symbol": "GBP/USD",
                "risk_amount": 400,  # 0.4% risk
                "concentration": 40.0,  # 40% of portfolio - HIGH
                "correlation_risk": "medium",
                "leverage": 30,
            },
        ]

        # Act
        hotspots = aggregator.identify_risk_hotspots(positions)

        # Assert
        assert "concentration" in hotspots["critical_risks"]
        assert hotspots["risk_score"] > 3.0  # Above warning threshold
        assert "GBP/USD" in hotspots["high_risk_positions"]

    def test_calculates_liquidity_risk(self):
        """
        RED: Assess liquidity risk of portfolio positions
        Requirement: Ensure positions can be closed quickly
        """
        # Arrange
        aggregator = PortfolioRiskAggregator()

        positions = [
            {
                "symbol": "EUR/USD",
                "position_value": 50000,
                "avg_daily_volume": 5000000000,  # $5B daily volume
                "bid_ask_spread": 0.00015,  # 1.5 pip spread
                "market_impact": 0.001,  # 0.1% market impact
            },
            {
                "symbol": "EUR/TRY",
                "position_value": 30000,
                "avg_daily_volume": 100000000,  # $100M daily volume
                "bid_ask_spread": 0.0020,  # 20 pip spread
                "market_impact": 0.05,  # 5% market impact
            },
        ]

        # Act
        liquidity_analysis = aggregator.calculate_liquidity_risk(positions)

        # Assert
        assert liquidity_analysis["EUR/USD"]["liquidity_score"] > 6.0  # High liquidity
        assert liquidity_analysis["EUR/TRY"]["liquidity_score"] < 4.0  # Low liquidity
        assert liquidity_analysis["portfolio_liquidity_risk"] in [
            "medium",
            "high",
        ]  # Acceptable range

    def test_handles_currency_exposure_risk(self):
        """
        RED: Calculate currency exposure across portfolio
        Requirement: Monitor FX risk in multi-currency portfolio
        """
        # Arrange
        aggregator = PortfolioRiskAggregator(base_currency="USD")

        positions = [
            {
                "symbol": "EUR/USD",
                "base_currency_exposure": 110000,  # Long EUR, Short USD
                "quote_currency_exposure": -110000,
            },
            {
                "symbol": "GBP/USD",
                "base_currency_exposure": 62500,  # Long GBP, Short USD
                "quote_currency_exposure": -62500,
            },
            {
                "symbol": "USD/JPY",
                "base_currency_exposure": 55000,  # Long USD, Short JPY
                "quote_currency_exposure": -55000,
            },
        ]

        # Act
        currency_exposure = aggregator.calculate_currency_exposure(positions)

        # Assert
        assert currency_exposure["USD"]["net_exposure"] == pytest.approx(
            -117500, abs=100
        )
        assert currency_exposure["EUR"]["net_exposure"] == 110000
        assert currency_exposure["GBP"]["net_exposure"] == 62500
        assert currency_exposure["JPY"]["net_exposure"] == -55000


class TestPortfolioRiskEdgeCases:
    """Test edge cases and error handling"""

    def test_handles_empty_portfolio(self):
        """Handle empty portfolio"""
        aggregator = PortfolioRiskAggregator(account_balance=100000)

        result = aggregator.calculate_total_risk([])

        assert result["total_risk_amount"] == 0
        assert result["risk_percentage"] == 0
        assert result["positions_count"] == 0

    def test_handles_missing_correlation_data(self):
        """Handle missing correlation matrix"""
        aggregator = PortfolioRiskAggregator(account_balance=50000)

        positions = [
            {"symbol": "EUR/USD", "risk_amount": 500},
            {"symbol": "GBP/USD", "risk_amount": 300},
        ]

        # Act with empty correlation matrix
        result = aggregator.calculate_correlation_adjusted_risk(positions, {})

        # Assert - Should fall back to assuming independence
        assert result["correlation_adjusted_risk"] <= result["raw_risk"]

    def test_handles_extreme_leverage(self):
        """Handle extremely high leverage scenarios"""
        aggregator = PortfolioRiskAggregator(
            account_balance=10000, max_total_leverage=5.0
        )

        positions = [
            {
                "symbol": "EUR/USD",
                "position_value": 1000000,  # 100:1 leverage
                "margin_used": 10000,
                "leverage": 100,
            }
        ]

        with pytest.raises(ValueError, match="Leverage limit exceeded"):
            aggregator.validate_leverage_limits(positions)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=core.risk_management.portfolio_risk"])
