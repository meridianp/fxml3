#!/usr/bin/env python
"""Create a comprehensive summary of all generated features."""

from pathlib import Path

import numpy as np
import pandas as pd

# Configuration
symbols = ["GBPUSD", "EURUSD", "USDJPY", "USDCHF"]
timeframe = "4h"
features_dir = Path(__file__).parent.parent / "data" / "features"

print("=== FEATURE ENGINEERING SUMMARY ===")
print("=" * 60)

# Feature categories
basic_features = {
    "Price": ["open", "high", "low", "close", "volume"],
    "Moving Averages": [
        "sma_5",
        "sma_21",
        "sma_55",
        "sma_200",
        "ema_5",
        "ema_21",
        "ema_55",
        "ema_200",
    ],
    "Momentum": ["rsi_14", "macd", "macd_signal", "macd_hist", "stoch_k", "stoch_d"],
    "Volatility": [
        "bb_middle",
        "bb_std",
        "bb_upper",
        "bb_lower",
        "bb_width",
        "bb_squeeze",
        "atr_14",
    ],
    "Trend": ["adx_14", "di_plus_14", "di_minus_14"],
    "Returns": ["daily_return", "volatility_14", "weekly_change"],
}

advanced_features = {
    "Market Microstructure": [
        "high_low_spread",
        "close_to_high",
        "parkinson_vol",
        "volume_sma_20",
        "volume_ratio",
    ],
    "Momentum Extended": ["momentum_3", "momentum_10", "momentum_30"],
    "Support/Resistance": [
        "resistance_20",
        "support_20",
        "price_to_resistance",
        "price_to_support",
        "channel_position",
    ],
    "Elliott Wave": [
        "wave_trend",
        "fib_support",
        "fib_resistance",
        "dist_to_fib_support",
        "dist_to_fib_resistance",
    ],
    "Market Regime": [
        "vol_regime",
        "trend_regime",
        "momentum_regime",
        "trend_strength",
    ],
}

# Check each symbol
for symbol in symbols:
    print(f"\n{symbol}")
    print("-" * 60)

    # Basic features
    basic_file = features_dir / f"{symbol}_{timeframe}_features.parquet"
    if basic_file.exists():
        basic_df = pd.read_parquet(basic_file)
        print(
            f"Basic features: {len(basic_df.columns)} features, {len(basic_df):,} samples"
        )
        print(f"Date range: {basic_df.index.min()} to {basic_df.index.max()}")
    else:
        print("Basic features: NOT FOUND")
        continue

    # Advanced features
    advanced_file = features_dir / f"{symbol}_{timeframe}_features_advanced.parquet"
    if advanced_file.exists():
        advanced_df = pd.read_parquet(advanced_file)
        print(
            f"Advanced features: {len(advanced_df.columns)} features, {len(advanced_df):,} samples"
        )

        # Check feature quality
        nan_pct = (advanced_df.isnull().sum() / len(advanced_df) * 100).mean()
        print(f"Average NaN percentage: {nan_pct:.2f}%")

        # Sample statistics
        print(f"\nKey statistics:")
        print(f"  RSI-14 mean: {advanced_df['rsi_14'].mean():.2f}")
        print(
            f"  Wave trend distribution: Up={(advanced_df['wave_trend'] > 0).sum():,}, "
            f"Down={(advanced_df['wave_trend'] < 0).sum():,}, "
            f"Neutral={(advanced_df['wave_trend'] == 0).sum():,}"
        )
        print(
            f"  Trend regime: Trending={advanced_df['trend_regime'].sum():,}, "
            f"Non-trending={(~advanced_df['trend_regime'].astype(bool)).sum():,}"
        )
    else:
        print("Advanced features: NOT FOUND")

# Feature categories summary
print("\n" + "=" * 60)
print("FEATURE CATEGORIES")
print("=" * 60)

print("\nBASIC FEATURES (35 total):")
for category, features in basic_features.items():
    print(f"  {category}: {len(features)} features")

print("\nADVANCED FEATURES (22 additional):")
for category, features in advanced_features.items():
    print(f"  {category}: {len(features)} features")

print("\nTOTAL FEATURES: 57")

# Memory usage
print("\n" + "=" * 60)
print("MEMORY USAGE")
print("=" * 60)

total_size = 0
for symbol in symbols:
    basic_file = features_dir / f"{symbol}_{timeframe}_features.parquet"
    advanced_file = features_dir / f"{symbol}_{timeframe}_features_advanced.parquet"

    if basic_file.exists():
        basic_size = basic_file.stat().st_size / (1024 * 1024)  # MB
        total_size += basic_size
        print(f"{symbol} basic: {basic_size:.2f} MB")

    if advanced_file.exists():
        advanced_size = advanced_file.stat().st_size / (1024 * 1024)  # MB
        total_size += advanced_size
        print(f"{symbol} advanced: {advanced_size:.2f} MB")

print(f"\nTotal disk usage: {total_size:.2f} MB")

print("\n" + "=" * 60)
print("✓ FEATURE ENGINEERING COMPLETE")
print("=" * 60)
print("\nNext steps:")
print("1. Train ML models on these features")
print("2. Run backtests to evaluate performance")
print("3. Deploy best models for paper trading")
