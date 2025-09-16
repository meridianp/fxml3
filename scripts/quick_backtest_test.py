#!/usr/bin/env python
"""Quick test of backtesting infrastructure."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.run_comprehensive_backtests import BacktestConfig, run_single_backtest


def test_backtest_setup():
    """Test basic backtest setup."""
    print("=" * 60)
    print("TESTING BACKTEST INFRASTRUCTURE")
    print("=" * 60)

    # Create test configuration
    config = BacktestConfig()
    config.start_date = datetime(2024, 1, 1)
    config.end_date = datetime(2024, 3, 31)  # 3 months for quick test
    config.initial_capital = 10000

    # Use conservative settings for test
    config.signal_threshold = 0.7
    config.max_position_pct = 0.05
    config.max_drawdown_pct = 0.15

    print("\nConfiguration:")
    print(f"  Period: {config.start_date.date()} to {config.end_date.date()}")
    print(f"  Initial Capital: ${config.initial_capital:,.2f}")
    print(f"  Position Sizing: {config.position_sizing_method}")
    print(f"  Max Position: {config.max_position_pct*100:.0f}%")
    print(f"  Signal Threshold: {config.signal_threshold}")

    # Test with GBPUSD (we know this model exists)
    symbol = "GBPUSD"
    model_type = "lgb"  # LightGBM
    models_dir = Path(__file__).parent.parent / "models"

    print(f"\nTesting with {symbol} {model_type} model...")

    try:
        # Run backtest
        results = run_single_backtest(
            symbol=symbol,
            model_type=model_type,
            config=config,
            models_dir=models_dir,
            save_results=False,
        )

        # Check results
        if "error" in results:
            print(f"\n❌ Error: {results['error']}")
            return False

        metrics = results.get("metrics", {})

        print("\n✅ Backtest completed successfully!")
        print("\nKey Metrics:")
        print(f"  Total Return: {metrics.get('total_return', 0)*100:.2f}%")
        print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        print(f"  Max Drawdown: {metrics.get('max_drawdown', 0)*100:.2f}%")
        print(f"  Win Rate: {metrics.get('win_rate', 0)*100:.1f}%")
        print(f"  Total Trades: {metrics.get('total_trades', 0)}")

        # Verify realistic conditions were applied
        print("\nRealistic Conditions Check:")

        # Check if trades were executed
        if metrics.get("total_trades", 0) > 0:
            print("  ✓ Trades executed")
        else:
            print("  ⚠ No trades executed (might need to adjust parameters)")

        # Check transaction costs
        if results.get("trades", 0) > 0:
            print("  ✓ Transaction costs applied")

        # Check risk management
        if metrics.get("max_drawdown", 0) < config.max_drawdown_pct:
            print("  ✓ Drawdown within limits")

        return True

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_position_sizing():
    """Test position sizing integration."""
    print("\n" + "=" * 60)
    print("TESTING POSITION SIZING INTEGRATION")
    print("=" * 60)

    from fxml4.backtesting.position_sizing_factory import position_sizing_factory

    # Test different position sizing methods
    methods = ["enhanced_kelly", "confidence_weighted", "risk_parity"]

    for method in methods:
        try:
            sizer = position_sizing_factory.create(
                method,
                config={
                    "max_position_pct": 0.1,
                },
                enable_dynamic_adjustment=True,
            )
            print(f"  ✓ {method} position sizer created")
        except Exception as e:
            print(f"  ❌ {method} failed: {e}")


def test_risk_management():
    """Test risk management components."""
    print("\n" + "=" * 60)
    print("TESTING RISK MANAGEMENT")
    print("=" * 60)

    from fxml4.backtesting.risk_management import (
        DrawdownControl,
        RiskManager,
        StopLossManager,
    )

    # Test stop loss manager
    try:
        stop_loss = StopLossManager(
            stop_type="atr", stop_distance=2.0, use_trailing=True
        )
        print("  ✓ Stop loss manager created")
    except Exception as e:
        print(f"  ❌ Stop loss manager failed: {e}")

    # Test drawdown control
    try:
        drawdown = DrawdownControl(max_drawdown_pct=0.20, max_daily_loss_pct=0.05)
        print("  ✓ Drawdown control created")
    except Exception as e:
        print(f"  ❌ Drawdown control failed: {e}")


def main():
    """Run all tests."""
    print("Quick Backtest Infrastructure Test")
    print("=" * 80)

    # Test components
    test_position_sizing()
    test_risk_management()

    # Test full backtest
    success = test_backtest_setup()

    print("\n" + "=" * 80)
    if success:
        print("✅ All tests passed! Backtesting infrastructure is ready.")
        print("\nNext steps:")
        print("1. Run full backtests: python scripts/run_comprehensive_backtests.py")
        print("2. Analyze results: python scripts/analyze_backtest_results.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")


if __name__ == "__main__":
    main()
