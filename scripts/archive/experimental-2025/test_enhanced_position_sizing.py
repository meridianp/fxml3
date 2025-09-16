#!/usr/bin/env python
"""Test script for enhanced position sizing algorithms."""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from fxml4.backtesting.enhanced_position_sizing import (
    PerformanceTracker,
    VolatilityRegimeDetector,
)
from fxml4.backtesting.event import SignalEvent, SignalType
from fxml4.backtesting.multi_timeframe_sizing import MultiTimeframePositionSizer
from fxml4.backtesting.position_sizing_factory import position_sizing_factory

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockPortfolio:
    """Mock portfolio for testing."""

    def __init__(self, equity: float = 10000.0):
        self.equity = equity
        self.positions = {}


def test_confidence_weighted_sizing():
    """Test confidence-weighted position sizing."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Confidence-Weighted Position Sizing")
    logger.info("=" * 60)

    # Create sizer
    sizer = position_sizing_factory.create(
        "confidence_weighted",
        config={
            "base_position_pct": 0.02,
            "min_confidence": 0.6,
            "max_confidence": 0.9,
            "confidence_power": 2.0,
        },
        enable_dynamic_adjustment=False,
    )

    portfolio = MockPortfolio(equity=10000)
    current_price = 1.1000

    # Test different confidence levels
    confidence_levels = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]

    for confidence in confidence_levels:
        signal = SignalEvent(
            signal_type=SignalType.ENTRY_LONG,
            symbol="EURUSD",
            strength=confidence,
            timestamp=datetime.now(),
            signal_data={"metadata": {"raw_probability": confidence}},
        )

        size = sizer.calculate_position_size(signal, portfolio, current_price)
        position_value = size * current_price
        position_pct = position_value / portfolio.equity * 100

        logger.info(
            f"Confidence: {confidence:.2f} -> Size: {size:,.0f} units "
            f"(${position_value:,.2f}, {position_pct:.2f}% of equity)"
        )


def test_enhanced_kelly_sizing():
    """Test enhanced Kelly criterion sizing."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Enhanced Kelly Criterion Position Sizing")
    logger.info("=" * 60)

    # Create sizer
    sizer = position_sizing_factory.create(
        "enhanced_kelly",
        config={
            "kelly_fraction": 0.25,
            "max_position_pct": 0.1,
            "confidence_weight": 0.5,
            "use_rolling_stats": False,  # Use provided stats for testing
        },
        enable_dynamic_adjustment=False,
    )

    portfolio = MockPortfolio(equity=10000)
    current_price = 1.1000

    # Test different scenarios
    scenarios = [
        {"confidence": 0.7, "win_rate": 0.6, "avg_win": 100, "avg_loss": 80},
        {"confidence": 0.8, "win_rate": 0.55, "avg_win": 150, "avg_loss": 100},
        {"confidence": 0.6, "win_rate": 0.65, "avg_win": 80, "avg_loss": 60},
        {"confidence": 0.9, "win_rate": 0.5, "avg_win": 200, "avg_loss": 100},
    ]

    for scenario in scenarios:
        signal = SignalEvent(
            signal_type=SignalType.ENTRY_LONG,
            symbol="EURUSD",
            strength=scenario["confidence"],
            timestamp=datetime.now(),
            signal_data={
                "ml_confidence": scenario["confidence"],
                "win_rate": scenario["win_rate"],
                "avg_win": scenario["avg_win"],
                "avg_loss": scenario["avg_loss"],
            },
        )

        size = sizer.calculate_position_size(signal, portfolio, current_price)
        position_value = size * current_price
        position_pct = position_value / portfolio.equity * 100

        # Get Kelly calculation details
        sizing_info = signal.signal_data.get("position_sizing", {})

        logger.info(
            f"\nScenario: Confidence={scenario['confidence']}, "
            f"Win Rate={scenario['win_rate']}, W/L Ratio={scenario['avg_win']/scenario['avg_loss']:.2f}"
        )
        logger.info(
            f"  Adjusted Win Rate: {sizing_info.get('adjusted_win_rate', 0):.3f}"
        )
        logger.info(f"  Kelly %: {sizing_info.get('kelly_pct', 0)*100:.2f}%")
        logger.info(
            f"  Final Position: {size:,.0f} units (${position_value:,.2f}, {position_pct:.2f}% of equity)"
        )


def test_dynamic_position_sizing():
    """Test dynamic position sizing with performance tracking."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Dynamic Position Sizing")
    logger.info("=" * 60)

    # Create performance tracker and volatility detector
    performance_tracker = PerformanceTracker()
    volatility_detector = VolatilityRegimeDetector()

    # Simulate some trade history
    trade_history = [
        {"pnl": 100, "return": 0.01},
        {"pnl": -50, "return": -0.005},
        {"pnl": 150, "return": 0.015},
        {"pnl": -30, "return": -0.003},
        {"pnl": 80, "return": 0.008},
        {"pnl": -100, "return": -0.01},
        {"pnl": 200, "return": 0.02},
    ]

    for trade in trade_history:
        performance_tracker.add_trade(trade)

    # Update volatility history
    returns = pd.Series([t["return"] for t in trade_history])
    volatility_detector.update_volatility("EURUSD", returns)

    # Create base sizer
    base_sizer = position_sizing_factory.create(
        "percentage", config={"percentage": 0.02}, enable_dynamic_adjustment=False
    )

    # Create dynamic sizer
    from fxml4.backtesting.enhanced_position_sizing import DynamicPositionSizer

    dynamic_sizer = DynamicPositionSizer(
        base_sizer=base_sizer,
        performance_tracker=performance_tracker,
        volatility_detector=volatility_detector,
        performance_weight=0.3,
        volatility_weight=0.3,
        drawdown_weight=0.4,
    )

    portfolio = MockPortfolio(equity=10000)
    current_price = 1.1000

    signal = SignalEvent(
        signal_type=SignalType.ENTRY_LONG,
        symbol="EURUSD",
        strength=0.7,
        timestamp=datetime.now(),
        signal_data={},
    )

    # Get base size
    base_size = base_sizer.calculate_position_size(signal, portfolio, current_price)
    base_value = base_size * current_price

    # Get dynamic size
    dynamic_size = dynamic_sizer.calculate_position_size(
        signal, portfolio, current_price
    )
    dynamic_value = dynamic_size * current_price

    # Get adjustment details
    adjustments = signal.signal_data.get("position_sizing", {}).get(
        "dynamic_adjustments", {}
    )

    logger.info(f"\nBase Position: {base_size:,.0f} units (${base_value:,.2f})")
    logger.info(f"Performance Score: {adjustments.get('performance_score', 0):.3f}")
    logger.info(f"Volatility Regime: {adjustments.get('volatility_regime', 'unknown')}")
    logger.info(f"Current Drawdown: {adjustments.get('current_drawdown', 0)*100:.1f}%")
    logger.info(f"Total Multiplier: {adjustments.get('total_multiplier', 1):.3f}")
    logger.info(f"Dynamic Position: {dynamic_size:,.0f} units (${dynamic_value:,.2f})")
    logger.info(f"Adjustment: {(dynamic_size/base_size - 1)*100:+.1f}%")


def test_risk_parity_sizing():
    """Test risk parity position sizing."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Risk Parity Position Sizing")
    logger.info("=" * 60)

    # Create sizer
    sizer = position_sizing_factory.create(
        "risk_parity",
        config={
            "target_risk": 0.01,
            "lookback_periods": 60,
            "use_correlation": True,
            "max_position_pct": 0.2,
        },
        enable_dynamic_adjustment=False,
    )

    # Generate sample returns data
    np.random.seed(42)
    returns_eurusd = pd.Series(np.random.normal(0.0001, 0.01, 100))
    returns_gbpusd = pd.Series(np.random.normal(0.0001, 0.012, 100))

    # Update sizer with returns
    if hasattr(sizer, "update_returns"):
        sizer.update_returns("EURUSD", returns_eurusd)
        sizer.update_returns("GBPUSD", returns_gbpusd)

    portfolio = MockPortfolio(equity=10000)

    # Test for different symbols
    symbols = ["EURUSD", "GBPUSD"]
    prices = {"EURUSD": 1.1000, "GBPUSD": 1.2500}

    for symbol in symbols:
        signal = SignalEvent(
            signal_type=SignalType.ENTRY_LONG,
            symbol=symbol,
            strength=0.7,
            timestamp=datetime.now(),
            signal_data={},
        )

        size = sizer.calculate_position_size(signal, portfolio, prices[symbol])
        position_value = size * prices[symbol]
        position_pct = position_value / portfolio.equity * 100

        sizing_info = signal.signal_data.get("position_sizing", {})

        logger.info(f"\n{symbol}:")
        logger.info(f"  Volatility: {sizing_info.get('volatility', 0)*100:.2f}%")
        logger.info(f"  Target Risk: {sizing_info.get('target_risk', 0)*100:.2f}%")
        logger.info(
            f"  Position: {size:,.0f} units (${position_value:,.2f}, {position_pct:.2f}% of equity)"
        )


def test_multi_timeframe_sizing():
    """Test multi-timeframe position sizing."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Multi-Timeframe Position Sizing")
    logger.info("=" * 60)

    # Create multi-timeframe sizer
    mtf_sizer = MultiTimeframePositionSizer(
        base_position_pct=0.02,
        timeframes=["4h", "1d"],
        use_trend_alignment=True,
        use_volatility_scaling=True,
        use_support_resistance=True,
    )

    # Generate sample data for different timeframes
    dates = pd.date_range(end=datetime.now(), periods=100, freq="4h")

    # 4h data
    data_4h = pd.DataFrame(
        {
            "open": 1.1000 + np.random.randn(100).cumsum() * 0.001,
            "high": 1.1050 + np.random.randn(100).cumsum() * 0.001,
            "low": 1.0950 + np.random.randn(100).cumsum() * 0.001,
            "close": 1.1000 + np.random.randn(100).cumsum() * 0.001,
            "volume": np.random.randint(1000, 5000, 100),
        },
        index=dates,
    )

    # 1d data (resample from 4h)
    data_1d = (
        data_4h.resample("1d")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )

    # Update timeframe data
    mtf_sizer.update_timeframe_data("4h", data_4h)
    mtf_sizer.update_timeframe_data("1d", data_1d)

    portfolio = MockPortfolio(equity=10000)
    current_price = data_4h["close"].iloc[-1]

    # Test long and short signals
    signal_types = [SignalType.ENTRY_LONG, SignalType.ENTRY_SHORT]

    for signal_type in signal_types:
        signal = SignalEvent(
            signal_type=signal_type,
            symbol="EURUSD",
            strength=0.7,
            timestamp=datetime.now(),
            signal_data={},
        )

        size = mtf_sizer.calculate_position_size(signal, portfolio, current_price)
        position_value = size * current_price
        position_pct = position_value / portfolio.equity * 100

        sizing_info = signal.signal_data.get("position_sizing", {})
        adjustments = sizing_info.get("adjustments", {})

        logger.info(f"\n{signal_type.value}:")
        logger.info(f"  Trend Alignment: {adjustments.get('trend_alignment', 1):.3f}")
        logger.info(f"  Volatility Adjustment: {adjustments.get('volatility', 1):.3f}")
        logger.info(
            f"  Support/Resistance: {adjustments.get('support_resistance', 1):.3f}"
        )
        logger.info(f"  Total Adjustment: {sizing_info.get('total_adjustment', 1):.3f}")
        logger.info(
            f"  Position: {size:,.0f} units (${position_value:,.2f}, {position_pct:.2f}% of equity)"
        )


def test_ensemble_sizing():
    """Test ensemble position sizing."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Ensemble Position Sizing")
    logger.info("=" * 60)

    # Create ensemble of different algorithms
    algorithms = {
        "confidence_weighted": {
            "base_position_pct": 0.02,
            "min_confidence": 0.6,
            "max_confidence": 0.9,
        },
        "enhanced_kelly": {
            "kelly_fraction": 0.25,
            "max_position_pct": 0.1,
            "use_rolling_stats": False,
        },
        "volatility": {
            "risk_per_trade": 0.01,
            "atr_multiplier": 2.0,
        },
    }

    weights = {
        "confidence_weighted": 0.4,
        "enhanced_kelly": 0.4,
        "volatility": 0.2,
    }

    ensemble = position_sizing_factory.create_ensemble(algorithms, weights)

    portfolio = MockPortfolio(equity=10000)
    current_price = 1.1000

    signal = SignalEvent(
        signal_type=SignalType.ENTRY_LONG,
        symbol="EURUSD",
        strength=0.75,
        timestamp=datetime.now(),
        signal_data={
            "ml_confidence": 0.75,
            "win_rate": 0.6,
            "avg_win": 100,
            "avg_loss": 80,
            "atr": 0.0050,  # 50 pips
        },
    )

    size = ensemble.calculate_position_size(signal, portfolio, current_price)
    position_value = size * current_price
    position_pct = position_value / portfolio.equity * 100

    sizing_info = signal.signal_data.get("position_sizing", {})
    component_sizes = sizing_info.get("component_sizes", {})

    logger.info("\nEnsemble Position Sizing:")
    logger.info(f"  Component Sizes:")
    for algo, comp_size in component_sizes.items():
        comp_value = comp_size * current_price
        logger.info(f"    {algo}: {comp_size:,.0f} units (${comp_value:,.2f})")

    logger.info(f"\n  Weights: {weights}")
    logger.info(
        f"  Final Position: {size:,.0f} units (${position_value:,.2f}, {position_pct:.2f}% of equity)"
    )


def main():
    """Run all position sizing tests."""
    logger.info("Testing Enhanced Position Sizing Algorithms")
    logger.info("=" * 80)

    test_confidence_weighted_sizing()
    test_enhanced_kelly_sizing()
    test_dynamic_position_sizing()
    test_risk_parity_sizing()
    test_multi_timeframe_sizing()
    test_ensemble_sizing()

    logger.info("\n" + "=" * 80)
    logger.info("All tests completed successfully!")


if __name__ == "__main__":
    main()
