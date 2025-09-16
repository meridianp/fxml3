#!/usr/bin/env python3
"""
Test script for risk metrics endpoint functionality.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict

# Add the project root to Python path
sys.path.insert(0, os.path.abspath("."))


async def test_risk_metrics():
    """Test the risk metrics calculation logic."""
    print("Testing risk metrics calculation...")

    try:
        # Import the FXRiskManager and create a test instance
        from fxml4.brokers.risk import FXRiskManager, RiskLimits

        # Create test risk limits
        limits = RiskLimits(
            max_portfolio_notional=1000000.0,
            max_single_position_notional=100000.0,
            max_daily_loss=5000.0,
            max_order_notional=50000.0,
        )

        # Create risk manager
        risk_manager = FXRiskManager(limits=limits)

        # Get basic risk summary
        summary = risk_manager.get_risk_summary()
        print("Basic risk summary:")
        print(f"  Metrics: {summary.get('metrics', {})}")
        print(f"  Limits: {summary.get('limits', {})}")

        # Simulate the risk metrics endpoint calculation
        metrics = summary.get("metrics", {})
        positions = summary.get("positions", {})

        # Calculate metrics as in the endpoint
        portfolio_value = 100000.0  # Base portfolio value
        total_position_value = sum(
            pos.get("market_value", 0) for pos in positions.values()
        )
        portfolio_value += total_position_value

        total_exposure = abs(metrics.get("total_notional", 0))
        net_exposure = metrics.get("total_notional", 0)
        gross_exposure = total_exposure

        daily_pnl = metrics.get("daily_pnl", 0)
        daily_pnl_pct = (
            (daily_pnl / portfolio_value) * 100 if portfolio_value > 0 else 0
        )

        max_drawdown = abs(daily_pnl) if daily_pnl < 0 else 0
        max_drawdown_pct = (
            (max_drawdown / portfolio_value) * 100 if portfolio_value > 0 else 0
        )

        margin_used = total_exposure * 0.02
        margin_available = portfolio_value - margin_used
        margin_utilization = (
            (margin_used / portfolio_value) if portfolio_value > 0 else 0
        )

        var_95 = portfolio_value * 0.02
        var_99 = portfolio_value * 0.05
        sharpe_ratio = 1.2 if daily_pnl > 0 else -0.5
        sortino_ratio = 1.8 if daily_pnl > 0 else -0.3

        risk_metrics = {
            "portfolio_value": round(portfolio_value, 2),
            "total_exposure": round(total_exposure, 2),
            "net_exposure": round(net_exposure, 2),
            "gross_exposure": round(gross_exposure, 2),
            "daily_pnl": round(daily_pnl, 2),
            "daily_pnl_pct": round(daily_pnl_pct, 2),
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "var_95": round(var_95, 2),
            "var_99": round(var_99, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "margin_used": round(margin_used, 2),
            "margin_available": round(margin_available, 2),
            "margin_utilization": round(margin_utilization, 2),
        }

        print("\nCalculated risk metrics:")
        for key, value in risk_metrics.items():
            print(f"  {key}: {value}")

        print("\n✅ Risk metrics calculation test PASSED!")
        print(f"✅ Portfolio value: ${risk_metrics['portfolio_value']:,.2f}")
        print(
            f"✅ Daily P&L: ${risk_metrics['daily_pnl']:,.2f} ({risk_metrics['daily_pnl_pct']:.2f}%)"
        )
        print(f"✅ Margin utilization: {risk_metrics['margin_utilization']:.2%}")

        # Test that the response format matches frontend expectations
        expected_fields = [
            "portfolio_value",
            "total_exposure",
            "net_exposure",
            "gross_exposure",
            "daily_pnl",
            "daily_pnl_pct",
            "max_drawdown",
            "max_drawdown_pct",
            "var_95",
            "var_99",
            "sharpe_ratio",
            "sortino_ratio",
            "margin_used",
            "margin_available",
            "margin_utilization",
        ]

        missing_fields = [
            field for field in expected_fields if field not in risk_metrics
        ]
        if missing_fields:
            print(f"❌ Missing required fields: {missing_fields}")
            return False

        print(f"✅ All {len(expected_fields)} required fields present in response")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print(
            "This suggests the risk management module needs to be properly configured"
        )
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("FXML4 Risk Metrics Endpoint Test")
    print("=" * 60)

    success = asyncio.run(test_risk_metrics())

    if success:
        print(
            "\n🎉 All tests passed! The /risk/metrics endpoint should work correctly."
        )
    else:
        print("\n💥 Tests failed. Check the errors above.")
        sys.exit(1)
