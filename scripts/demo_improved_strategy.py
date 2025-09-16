#!/usr/bin/env python
"""Demonstrate improved strategy with clear before/after comparison."""

# Import paths handled by PYTHONPATH wrapper

import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from fxml4.strategy.dynamic_exit_strategy import DynamicExitStrategy, ExitConfig
from fxml4.strategy.market_regime_detector import MarketRegimeDetector, RegimeConfig

print("=" * 80)
print("STRATEGY IMPROVEMENT DEMONSTRATION")
print("=" * 80)

# Load model and data
symbol = "GBPUSD"
model = joblib.load(f"models/{symbol}/best_model_lightgbm.joblib")
scaler = joblib.load(f"models/{symbol}/scaler.joblib")

# Get actual feature columns from data
df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")
feature_cols = [
    col for col in df.columns if col not in ["open", "high", "low", "close", "volume"]
]

# Test data
test_data = df["2023-01-01":"2024-06-30"]

print(f"\nTest Period: {test_data.index[0]} to {test_data.index[-1]}")
print(f"Total Bars: {len(test_data)}")

# =============================================================================
# STRATEGY 1: Original (Fixed Exits, No Filtering)
# =============================================================================
print("\n" + "-" * 80)
print("STRATEGY 1: ORIGINAL (BASELINE)")
print("-" * 80)

equity1 = 10000.0
trades1 = []
position1 = None

for i in range(100, len(test_data)):
    current_bar = test_data.iloc[i]
    current_price = current_bar["close"]

    # Get signal
    try:
        X = test_data[feature_cols].iloc[i : i + 1]
        if not X.isnull().any().any():
            X_scaled = scaler.transform(X)
            pred = model.predict(X_scaled)[0]
            proba = model.predict_proba(X_scaled)[0]
            signal = pred - 1
            confidence = max(proba)
        else:
            continue
    except:
        continue

    # Original logic
    if position1 is None and confidence > 0.65 and signal != 0:
        atr = current_bar.get("atr_14", current_price * 0.001)
        position1 = {
            "type": "long" if signal == 1 else "short",
            "entry": current_price,
            "stop": current_price - signal * 2 * atr,
            "target": current_price + signal * 4 * atr,  # 2:1 R/R
            "size": equity1 * 0.02 / (2 * atr),
        }

    elif position1 is not None:
        # Fixed exits
        exit_trade = False
        if position1["type"] == "long":
            if current_price <= position1["stop"]:
                exit_trade = True
                exit_reason = "Stop Loss"
            elif current_price >= position1["target"]:
                exit_trade = True
                exit_reason = "Take Profit"
        else:
            if current_price >= position1["stop"]:
                exit_trade = True
                exit_reason = "Stop Loss"
            elif current_price <= position1["target"]:
                exit_trade = True
                exit_reason = "Take Profit"

        if exit_trade:
            # Calculate P&L
            if position1["type"] == "long":
                pnl = (current_price - position1["entry"]) * position1["size"]
            else:
                pnl = (position1["entry"] - current_price) * position1["size"]

            pnl -= position1["size"] * current_price * 0.00007  # Costs
            equity1 += pnl

            trades1.append({"pnl": pnl, "exit_reason": exit_reason})
            position1 = None

# Results for Strategy 1
total_trades1 = len(trades1)
winning_trades1 = len([t for t in trades1 if t["pnl"] > 0])
total_pnl1 = sum(t["pnl"] for t in trades1)
return1 = (equity1 - 10000) / 10000

print(f"\nResults:")
print(f"Total Trades: {total_trades1}")
print(
    f"Win Rate: {winning_trades1/total_trades1*100:.1f}%"
    if total_trades1 > 0
    else "N/A"
)
print(f"Total Return: {return1*100:.2f}%")
print(f"Final Equity: ${equity1:,.2f}")

# Exit breakdown
if trades1:
    exit_counts = {}
    for t in trades1:
        reason = t["exit_reason"]
        exit_counts[reason] = exit_counts.get(reason, 0) + 1
    print(f"\nExit Breakdown:")
    for reason, count in exit_counts.items():
        print(f"  {reason}: {count} ({count/total_trades1*100:.1f}%)")

# =============================================================================
# STRATEGY 2: Improved (Dynamic Exits, Market Filtering)
# =============================================================================
print("\n" + "-" * 80)
print("STRATEGY 2: IMPROVED (WITH ENHANCEMENTS)")
print("-" * 80)

# Initialize components
exit_strategy = DynamicExitStrategy(
    ExitConfig(
        initial_stop_atr_multiplier=2.0,
        trailing_stop_atr_multiplier=1.5,
        tp_levels=[1.0, 2.0, 3.0],  # Multiple TP levels
        tp_portions=[0.4, 0.3, 0.3],
        exit_on_opposite_signal=True,
    )
)

regime_detector = MarketRegimeDetector(
    RegimeConfig(
        adx_trend_threshold=20.0,  # Lowered for more opportunities
        efficiency_threshold=0.25,  # Lowered for more opportunities
    )
)

equity2 = 10000.0
trades2 = []
rejected_signals = []
positions2 = {}
pos_counter = 0

for i in range(100, len(test_data)):
    current_bar = test_data.iloc[i]
    current_time = test_data.index[i]
    current_price = current_bar["close"]

    # Check exits for existing positions
    for pos_id in list(positions2.keys()):
        pos = positions2[pos_id]

        # Get current signal for exit check
        try:
            X = test_data[feature_cols].iloc[i : i + 1]
            if not X.isnull().any().any():
                X_scaled = scaler.transform(X)
                pred = model.predict(X_scaled)[0]
                signal = pred - 1
                confidence = max(model.predict_proba(X_scaled)[0])
            else:
                signal = 0
                confidence = 0.5
        except:
            signal = 0
            confidence = 0.5

        # Dynamic exit check
        should_exit, exit_price, exit_reason, exit_size = exit_strategy.update_position(
            pos_id,
            current_price,
            current_bar.get("atr_14", current_price * 0.001),
            signal,
            confidence,
        )

        if should_exit:
            # Calculate P&L
            if pos["type"] == "long":
                pnl = (exit_price - pos["entry_price"]) * exit_size
            else:
                pnl = (pos["entry_price"] - exit_price) * exit_size

            pnl -= exit_size * exit_price * 0.00007  # Costs
            equity2 += pnl

            trades2.append(
                {
                    "pnl": pnl,
                    "exit_reason": (
                        exit_reason.value
                        if hasattr(exit_reason, "value")
                        else str(exit_reason)
                    ),
                    "size_pct": exit_size / pos["original_size"],
                }
            )

            pos["remaining_size"] -= exit_size
            if pos["remaining_size"] <= 0:
                del positions2[pos_id]
                exit_strategy.remove_position(pos_id)

    # Check for new signals (limit total exposure)
    total_exposure = sum(
        p["remaining_size"] * current_price for p in positions2.values()
    )
    if total_exposure < equity2 * 0.05:  # Max 5% exposure
        # Get signal
        try:
            X = test_data[feature_cols].iloc[i : i + 1]
            if not X.isnull().any().any():
                X_scaled = scaler.transform(X)
                pred = model.predict(X_scaled)[0]
                proba = model.predict_proba(X_scaled)[0]
                signal = pred - 1
                confidence = max(proba)
            else:
                continue
        except:
            continue

        # Apply filters
        if signal != 0 and confidence > 0.65:
            # Market regime check
            global_idx = df.index.get_loc(current_time)
            regime_analysis = regime_detector.analyze_market(df, global_idx)

            if not regime_analysis["is_tradeable"]:
                rejected_signals.append(
                    {
                        "regime": regime_analysis["market_regime"].value,
                        "volatility": regime_analysis["volatility_regime"].value,
                    }
                )
            else:
                # Enter position with improvements
                pos_counter += 1
                pos_id = f"pos_{pos_counter}"

                atr = current_bar.get("atr_14", current_price * 0.001)

                # Adjust size based on regime
                base_size = equity2 * 0.02 / (2 * atr)
                adjusted_size = base_size * regime_analysis["position_size_multiplier"]

                # Initialize dynamic exits
                exit_levels = exit_strategy.initialize_position(
                    pos_id,
                    current_price,
                    "long" if signal == 1 else "short",
                    atr,
                    adjusted_size,
                    confidence,
                )

                positions2[pos_id] = {
                    "entry_price": current_price,
                    "type": "long" if signal == 1 else "short",
                    "original_size": adjusted_size,
                    "remaining_size": adjusted_size,
                }

# Results for Strategy 2
total_trades2 = len(trades2)
winning_trades2 = len([t for t in trades2 if t["pnl"] > 0])
total_pnl2 = sum(t["pnl"] for t in trades2)
return2 = (equity2 - 10000) / 10000

print(f"\nResults:")
print(f"Total Trades: {total_trades2}")
print(
    f"Win Rate: {winning_trades2/total_trades2*100:.1f}%"
    if total_trades2 > 0
    else "N/A"
)
print(f"Total Return: {return2*100:.2f}%")
print(f"Final Equity: ${equity2:,.2f}")
print(f"Rejected Signals: {len(rejected_signals)}")

# Exit breakdown
if trades2:
    exit_counts = {}
    for t in trades2:
        reason = t["exit_reason"]
        exit_counts[reason] = exit_counts.get(reason, 0) + 1
    print(f"\nExit Breakdown:")
    for reason, count in sorted(exit_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason}: {count} ({count/total_trades2*100:.1f}%)")

# =============================================================================
# COMPARISON
# =============================================================================
print("\n" + "=" * 80)
print("PERFORMANCE COMPARISON")
print("=" * 80)

print(f"\n{'Metric':<20} {'Original':<15} {'Improved':<15} {'Change':<15}")
print("-" * 65)
print(
    f"{'Total Return':<20} {return1*100:>14.2f}% {return2*100:>14.2f}% {(return2-return1)*100:>+14.2f}%"
)
print(
    f"{'Win Rate':<20} {winning_trades1/total_trades1*100 if total_trades1 > 0 else 0:>14.1f}% {winning_trades2/total_trades2*100 if total_trades2 > 0 else 0:>14.1f}% {(winning_trades2/total_trades2 - winning_trades1/total_trades1)*100 if total_trades1 > 0 and total_trades2 > 0 else 0:>+14.1f}%"
)
print(
    f"{'Total Trades':<20} {total_trades1:>15} {total_trades2:>15} {total_trades2-total_trades1:>+15}"
)
print(
    f"{'Final Equity':<20} ${equity1:>13,.2f} ${equity2:>13,.2f} ${equity2-equity1:>+14,.2f}"
)

print("\n" + "=" * 80)
print("KEY IMPROVEMENTS DEMONSTRATED:")
print("=" * 80)
print("✓ Dynamic exits with partial profit taking")
print("✓ Trailing stops for winning positions")
print("✓ Market regime filtering (avoided bad conditions)")
print("✓ Exit on signal reversal")
print("✓ Volatility-adjusted position sizing")

if return2 > return1:
    improvement_pct = (
        ((return2 - return1) / abs(return1)) * 100 if return1 != 0 else 100
    )
    print(f"\n🎯 Strategy improved returns by {improvement_pct:.1f}%!")
else:
    print("\n⚠️ Strategy needs parameter tuning for this specific period")
