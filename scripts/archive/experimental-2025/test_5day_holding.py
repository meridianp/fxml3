#!/usr/bin/env python
"""Test 5-day holding period specifically."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import warnings

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from fxml4.strategy.dynamic_exit_strategy import DynamicExitStrategy, ExitConfig
from fxml4.strategy.market_regime_detector import MarketRegimeDetector, RegimeConfig

print("=" * 80)
print("5-DAY HOLDING PERIOD TEST")
print("=" * 80)

# Parameters
symbol = "GBPUSD"
initial_capital = 10000.0
holding_days = 5
confidence_threshold = 0.65

# Load model
model = joblib.load(f"models/{symbol}/best_model_lightgbm.joblib")
scaler = joblib.load(f"models/{symbol}/scaler.joblib")

# Load data
df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")
test_data = df["2023-01-01":"2024-06-30"]

# Get features
feature_cols = [
    col for col in df.columns if col not in ["open", "high", "low", "close", "volume"]
]

print(f"\nTest Period: {test_data.index[0]} to {test_data.index[-1]}")
print(f"Total Bars: {len(test_data)}")
print(f"Holding Period: {holding_days} days ({holding_days * 6} bars)")

# Initialize strategies
exit_strategy = DynamicExitStrategy(
    ExitConfig(
        initial_stop_atr_multiplier=2.5,  # Wider stops for longer holds
        trailing_stop_atr_multiplier=2.0,
        tp_levels=[1.5, 3.0, 4.5, 6.0],  # Higher targets
        tp_portions=[0.25, 0.25, 0.25, 0.25],
        max_holding_bars=holding_days * 6,
        exit_on_opposite_signal=True,
        exit_on_weak_signal=False,  # Don't exit on weak signals
    )
)

regime_detector = MarketRegimeDetector(
    RegimeConfig(
        adx_trend_threshold=25.0, efficiency_threshold=0.30  # Require stronger trends
    )
)

# Backtest state
equity = initial_capital
positions = {}
trades = []
position_counter = 0
signals_taken = 0
signals_rejected = 0

print("\nRunning 5-day holding backtest...")

# Process bars
for i in range(100, len(test_data)):
    if i % 500 == 0:
        print(f"Progress: {i}/{len(test_data)} bars")

    current_bar = test_data.iloc[i]
    current_time = test_data.index[i]
    current_price = current_bar["close"]
    current_atr = current_bar.get("atr_14", current_price * 0.001)

    # Check exits
    for pos_id in list(positions.keys()):
        pos = positions[pos_id]

        # Get current signal
        try:
            X = test_data[feature_cols].iloc[i : i + 1]
            if not X.isnull().any().any():
                X_scaled = scaler.transform(X)
                pred = model.predict(X_scaled)[0]
                proba = model.predict_proba(X_scaled)[0]
                signal = pred - 1
                confidence = max(proba)
            else:
                signal = 0
                confidence = 0.5
        except:
            signal = 0
            confidence = 0.5

        # Dynamic exit check
        should_exit, exit_price, exit_reason, exit_size = exit_strategy.update_position(
            pos_id, current_price, current_atr, signal, confidence
        )

        if should_exit:
            # Calculate P&L
            if pos["type"] == "long":
                gross_pnl = (exit_price - pos["entry_price"]) * exit_size
            else:
                gross_pnl = (pos["entry_price"] - exit_price) * exit_size

            costs = exit_size * exit_price * 0.00007
            net_pnl = gross_pnl - costs

            equity += net_pnl

            trades.append(
                {
                    "entry_time": pos["entry_time"],
                    "exit_time": current_time,
                    "type": pos["type"],
                    "entry_price": pos["entry_price"],
                    "exit_price": exit_price,
                    "size": exit_size,
                    "net_pnl": net_pnl,
                    "exit_reason": (
                        exit_reason.value
                        if hasattr(exit_reason, "value")
                        else str(exit_reason)
                    ),
                    "bars_held": i - test_data.index.get_loc(pos["entry_time"]),
                    "days_held": (i - test_data.index.get_loc(pos["entry_time"])) / 6,
                }
            )

            pos["remaining_size"] -= exit_size
            if pos["remaining_size"] <= 0:
                del positions[pos_id]
                exit_strategy.remove_position(pos_id)

    # Check for new signals (one position at a time)
    if len(positions) == 0:
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

        if signal != 0 and confidence > confidence_threshold:
            # Market regime check
            global_idx = df.index.get_loc(current_time)
            regime_analysis = regime_detector.analyze_market(df, global_idx)

            # Stronger filter for longer holds
            if (
                regime_analysis["is_tradeable"]
                and regime_analysis["trend_strength"] > 30
            ):
                position_counter += 1
                pos_id = f"pos_{position_counter}"

                # Confidence-based sizing
                confidence_multiplier = 0.5 + (confidence - 0.5) * 2.0
                base_size = equity * 0.015 * confidence_multiplier / (2.5 * current_atr)

                size = base_size * regime_analysis["position_size_multiplier"]

                # Cap exposure
                max_size = equity * 0.08 / current_price
                size = min(size, max_size)

                # Initialize position
                exit_levels = exit_strategy.initialize_position(
                    pos_id,
                    current_price,
                    "long" if signal == 1 else "short",
                    current_atr,
                    size,
                    confidence,
                )

                positions[pos_id] = {
                    "entry_time": current_time,
                    "entry_price": current_price,
                    "type": "long" if signal == 1 else "short",
                    "original_size": size,
                    "remaining_size": size,
                    "confidence": confidence,
                    "regime": (
                        regime_analysis["market_regime"].value
                        if regime_analysis["market_regime"]
                        else "unknown"
                    ),
                }

                signals_taken += 1
            else:
                signals_rejected += 1

# Close remaining positions
for pos_id in list(positions.keys()):
    pos = positions[pos_id]
    exit_price = test_data.iloc[-1]["close"]

    if pos["type"] == "long":
        pnl = (exit_price - pos["entry_price"]) * pos["remaining_size"]
    else:
        pnl = (pos["entry_price"] - exit_price) * pos["remaining_size"]

    pnl -= pos["remaining_size"] * exit_price * 0.00007
    equity += pnl

    trades.append(
        {
            "entry_time": pos["entry_time"],
            "exit_time": test_data.index[-1],
            "type": pos["type"],
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "size": pos["remaining_size"],
            "net_pnl": pnl,
            "exit_reason": "end_of_test",
            "bars_held": len(test_data) - test_data.index.get_loc(pos["entry_time"]),
            "days_held": (len(test_data) - test_data.index.get_loc(pos["entry_time"]))
            / 6,
        }
    )

# Results
print("\n" + "=" * 80)
print("5-DAY HOLDING STRATEGY RESULTS")
print("=" * 80)

total_return = (equity - initial_capital) / initial_capital

print(f"\nPerformance Summary:")
print(f"Initial Capital: ${initial_capital:,.2f}")
print(f"Final Equity: ${equity:,.2f}")
print(f"Total Return: {total_return*100:.2f}%")
print(f"Total P&L: ${equity - initial_capital:,.2f}")

if trades:
    trades_df = pd.DataFrame(trades)
    winning = trades_df[trades_df["net_pnl"] > 0]
    losing = trades_df[trades_df["net_pnl"] <= 0]

    print(f"\nTrading Statistics:")
    print(f"Total Trades: {len(trades_df)}")
    print(f"Winning Trades: {len(winning)} ({len(winning)/len(trades_df)*100:.1f}%)")
    print(f"Losing Trades: {len(losing)} ({len(losing)/len(trades_df)*100:.1f}%)")
    print(f"Signals Taken: {signals_taken}")
    print(f"Signals Rejected: {signals_rejected}")

    if len(winning) > 0:
        print(f"Average Win: ${winning['net_pnl'].mean():.2f}")
        print(f"Largest Win: ${winning['net_pnl'].max():.2f}")

    if len(losing) > 0:
        print(f"Average Loss: ${losing['net_pnl'].mean():.2f}")
        print(f"Largest Loss: ${losing['net_pnl'].min():.2f}")

        if len(winning) > 0:
            profit_factor = winning["net_pnl"].sum() / abs(losing["net_pnl"].sum())
            print(f"Profit Factor: {profit_factor:.2f}")

    # Holding period analysis
    print(f"\nHolding Period Analysis:")
    print(f"Average: {trades_df['days_held'].mean():.1f} days")
    print(f"Median: {trades_df['days_held'].median():.1f} days")
    print(f"Max: {trades_df['days_held'].max():.1f} days")

    # Exit analysis
    print(f"\nExit Analysis:")
    exit_counts = trades_df["exit_reason"].value_counts()
    for reason, count in exit_counts.items():
        print(f"  {reason}: {count} ({count/len(trades_df)*100:.1f}%)")

    # Risk metrics
    cumulative_pnl = trades_df["net_pnl"].cumsum()
    running_max = cumulative_pnl.expanding().max()
    drawdown = (cumulative_pnl - running_max) / initial_capital
    max_dd = drawdown.min()

    # Sharpe
    returns_per_trade = trades_df["net_pnl"] / initial_capital
    if returns_per_trade.std() > 0:
        sharpe = (
            returns_per_trade.mean()
            / returns_per_trade.std()
            * np.sqrt(252 * 6 / trades_df["bars_held"].mean())
        )
    else:
        sharpe = 0

    print(f"\nRisk Metrics:")
    print(f"Maximum Drawdown: {max_dd*100:.2f}%")
    print(f"Sharpe Ratio: {sharpe:.2f}")

# Comparison
print("\n" + "=" * 80)
print("COMPARISON WITH SHORT HOLDING")
print("=" * 80)
print(
    f"\n{'Strategy':<25} {'Return':<15} {'Win Rate':<15} {'Trades':<10} {'Avg Hold':<15}"
)
print("-" * 80)
print(
    f"{'Original (9.1h)':<25} {'0.10%':<15} {'79.4%':<15} {'34':<10} {'9.1 hours':<15}"
)
win_rate = f"{len(winning)/len(trades_df)*100:.1f}%" if trades else "N/A"
avg_hold = f"{trades_df['days_held'].mean():.1f} days" if trades else "N/A"
print(
    f"{'5-Day Holding':<25} {total_return*100:.2f}%{'':<10} {win_rate:<15} {len(trades_df) if trades else 0:<10} {avg_hold:<15}"
)

print("\n" + "=" * 80)
print("KEY DIFFERENCES:")
print("=" * 80)
print("✓ Wider stop losses (2.5x ATR vs 1.5x)")
print("✓ Higher profit targets (1.5-6x ATR vs 0.8-4x)")
print("✓ Stronger trend requirement (ADX > 25 vs > 20)")
print("✓ Confidence-based position sizing")
print("✓ No exit on weak signals")
print(f"✓ Maximum holding: {holding_days} days vs ~2 days")

if trades and total_return > 0.001:
    print(f"\n🎯 5-day holding improved returns to {total_return*100:.2f}%!")
elif trades:
    print(f"\n⚠️ 5-day holding underperformed: {total_return*100:.2f}%")
