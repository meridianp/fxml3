#!/usr/bin/env python
"""Quick demonstration of improved backtest using existing model with new strategies."""

# Import paths handled by PYTHONPATH wrapper

import json
import logging
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from fxml4.strategy.dynamic_exit_strategy import DynamicExitStrategy, ExitConfig
from fxml4.strategy.market_regime_detector import MarketRegimeDetector, RegimeConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_improved_backtest_demo():
    """Run a quick demo comparing original vs improved strategies."""
    print("=" * 80)
    print("IMPROVED STRATEGY BACKTEST DEMONSTRATION")
    print("=" * 80)

    # Parameters
    symbol = "GBPUSD"
    initial_capital = 10000.0

    # Load existing model (use the original one for fair comparison)
    model_dir = Path(f"models/{symbol}")
    model = joblib.load(model_dir / "best_model_lightgbm.joblib")
    scaler = joblib.load(model_dir / "scaler.joblib")

    with open(model_dir / "selected_features.json", "r") as f:
        features = json.load(f)

    # Load data
    df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")

    # Test period
    test_data = df["2023-01-01":"2024-06-30"]
    print(f"\nTest Period: {test_data.index[0]} to {test_data.index[-1]}")
    print(f"Total Bars: {len(test_data)}")

    # Initialize strategies
    exit_strategy = DynamicExitStrategy(
        ExitConfig(
            initial_stop_atr_multiplier=2.0,
            trailing_stop_atr_multiplier=1.5,
            tp_levels=[1.0, 2.0, 3.0, 5.0],
            tp_portions=[0.3, 0.3, 0.2, 0.2],
            exit_on_opposite_signal=True,
        )
    )

    regime_detector = MarketRegimeDetector(
        RegimeConfig(adx_trend_threshold=25.0, efficiency_threshold=0.3)
    )

    # Track results
    trades = []
    equity = initial_capital
    positions = {}
    position_counter = 0
    rejected_signals = []

    print("\nRunning improved backtest...")

    # Main loop
    for i in range(100, len(test_data)):
        current_bar = test_data.iloc[i]
        current_time = test_data.index[i]
        current_price = current_bar["close"]

        # Check exits for existing positions
        for pos_id in list(positions.keys()):
            pos = positions[pos_id]

            # Get signal for exit check
            try:
                X = test_data[features].iloc[i : i + 1]
                if not X.isnull().any().any():
                    X_scaled = scaler.transform(X)
                    pred = model.predict(X_scaled)[0]
                    signal = pred - 1
                    confidence = 0.7
                else:
                    signal = 0
                    confidence = 0.5
            except:
                signal = 0
                confidence = 0.5

            # Dynamic exit check
            should_exit, exit_price, exit_reason, exit_size = (
                exit_strategy.update_position(
                    pos_id,
                    current_price,
                    current_bar.get("atr_14", current_price * 0.001),
                    signal,
                    confidence,
                )
            )

            if should_exit:
                # Calculate P&L
                if pos["type"] == "long":
                    pnl = (
                        exit_price - pos["entry_price"]
                    ) * exit_size - exit_size * exit_price * 0.00007
                else:
                    pnl = (
                        pos["entry_price"] - exit_price
                    ) * exit_size - exit_size * exit_price * 0.00007

                equity += pnl

                trades.append(
                    {
                        "entry_time": pos["entry_time"],
                        "exit_time": current_time,
                        "type": pos["type"],
                        "entry_price": pos["entry_price"],
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "exit_reason": (
                            exit_reason.value
                            if hasattr(exit_reason, "value")
                            else str(exit_reason)
                        ),
                        "regime": pos["regime"],
                    }
                )

                pos["size"] -= exit_size
                if pos["size"] <= 0:
                    del positions[pos_id]
                    exit_strategy.remove_position(pos_id)

        # Check for new signals
        if len(positions) == 0:  # Simple: one position at a time
            # Get regime
            global_idx = df.index.get_loc(current_time)
            regime_analysis = regime_detector.analyze_market(df, global_idx)

            # Get signal
            try:
                X = test_data[features].iloc[i : i + 1]
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
                if not regime_analysis["is_tradeable"]:
                    rejected_signals.append(
                        {
                            "time": current_time,
                            "regime": regime_analysis["market_regime"].value,
                            "volatility": regime_analysis["volatility_regime"].value,
                        }
                    )
                else:
                    # Enter position
                    position_counter += 1
                    pos_id = f"pos_{position_counter}"

                    # Calculate size with regime adjustment
                    base_size = (
                        equity
                        * 0.02
                        / (current_bar.get("atr_14", current_price * 0.001) * 2)
                    )
                    adjusted_size = (
                        base_size * regime_analysis["position_size_multiplier"]
                    )

                    # Initialize exits
                    exit_levels = exit_strategy.initialize_position(
                        pos_id,
                        current_price,
                        "long" if signal == 1 else "short",
                        current_bar.get("atr_14", current_price * 0.001),
                        adjusted_size,
                        confidence,
                    )

                    positions[pos_id] = {
                        "entry_time": current_time,
                        "entry_price": current_price,
                        "type": "long" if signal == 1 else "short",
                        "size": adjusted_size,
                        "regime": regime_analysis["market_regime"].value,
                    }

    # Results
    print("\n" + "=" * 80)
    print("IMPROVED STRATEGY RESULTS")
    print("=" * 80)

    if trades:
        trades_df = pd.DataFrame(trades)
        total_pnl = trades_df["pnl"].sum()
        total_return = (equity - initial_capital) / initial_capital

        winning = trades_df[trades_df["pnl"] > 0]
        losing = trades_df[trades_df["pnl"] <= 0]

        print(f"\nPerformance:")
        print(f"Initial Capital: ${initial_capital:,.2f}")
        print(f"Final Equity: ${equity:,.2f}")
        print(f"Total Return: {total_return*100:.2f}%")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Win Rate: {len(winning)/len(trades_df)*100:.1f}%")

        if len(winning) > 0 and len(losing) > 0:
            profit_factor = winning["pnl"].sum() / abs(losing["pnl"].sum())
            print(f"Profit Factor: {profit_factor:.2f}")

        # Exit analysis
        print(f"\nExit Analysis:")
        exit_counts = trades_df["exit_reason"].value_counts()
        for reason, count in exit_counts.items():
            print(f"  {reason}: {count} ({count/len(trades_df)*100:.1f}%)")

        # Regime performance
        print(f"\nRegime Performance:")
        regime_perf = trades_df.groupby("regime")["pnl"].agg(["count", "sum", "mean"])
        print(regime_perf)

        print(f"\nRejected Signals: {len(rejected_signals)}")

        # Calculate Sharpe
        equity_curve = [initial_capital]
        for trade in trades:
            equity_curve.append(equity_curve[-1] + trade["pnl"])

        returns = pd.Series(equity_curve).pct_change().dropna()
        if returns.std() > 0:
            sharpe = returns.mean() / returns.std() * np.sqrt(252 * 6)
            print(f"Sharpe Ratio: {sharpe:.2f}")

        # Drawdown
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        max_dd = drawdown.min()
        print(f"Max Drawdown: {max_dd*100:.2f}%")

    else:
        print("No trades executed")

    print("\n" + "=" * 80)
    print("KEY IMPROVEMENTS DEMONSTRATED:")
    print("- Dynamic exits with partial profit taking")
    print("- Market regime filtering (rejected bad market conditions)")
    print("- Volatility-adjusted position sizing")
    print("- Signal confidence thresholds")
    print("=" * 80)


def compare_with_original():
    """Run original backtest for comparison."""
    print("\n\nRUNNING ORIGINAL STRATEGY FOR COMPARISON...")
    print("=" * 80)

    # Simple recreation of original logic
    symbol = "GBPUSD"
    initial_capital = 10000.0

    # Load model
    model = joblib.load(f"models/{symbol}/best_model_lightgbm.joblib")
    scaler = joblib.load(f"models/{symbol}/scaler.joblib")

    with open(f"models/{symbol}/selected_features.json", "r") as f:
        features = json.load(f)

    # Load data
    df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")
    test_data = df["2023-01-01":"2024-06-30"]

    # Simple backtest
    equity = initial_capital
    trades = []
    position = None

    for i in range(100, len(test_data)):
        current_bar = test_data.iloc[i]
        current_price = current_bar["close"]

        try:
            X = test_data[features].iloc[i : i + 1]
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

        # Original logic: enter on high confidence
        if position is None and confidence > 0.65:
            if signal != 0:
                position = {
                    "type": "long" if signal == 1 else "short",
                    "entry": current_price,
                    "stop": current_price
                    - signal * 2 * current_bar.get("atr_14", current_price * 0.001),
                    "target": current_price
                    + signal * 4 * current_bar.get("atr_14", current_price * 0.001),
                    "size": equity
                    * 0.02
                    / (2 * current_bar.get("atr_14", current_price * 0.001)),
                }

        elif position is not None:
            # Fixed exit logic
            if position["type"] == "long":
                if (
                    current_price <= position["stop"]
                    or current_price >= position["target"]
                ):
                    pnl = (current_price - position["entry"]) * position["size"]
                    pnl -= position["size"] * current_price * 0.00007
                    equity += pnl
                    trades.append(pnl)
                    position = None
            else:
                if (
                    current_price >= position["stop"]
                    or current_price <= position["target"]
                ):
                    pnl = (position["entry"] - current_price) * position["size"]
                    pnl -= position["size"] * current_price * 0.00007
                    equity += pnl
                    trades.append(pnl)
                    position = None

    # Results
    if trades:
        total_return = (equity - initial_capital) / initial_capital
        win_rate = len([t for t in trades if t > 0]) / len(trades)

        print(f"\nOriginal Strategy Results:")
        print(f"Total Return: {total_return*100:.2f}%")
        print(f"Total Trades: {len(trades)}")
        print(f"Win Rate: {win_rate*100:.1f}%")
        print(f"Final Equity: ${equity:,.2f}")


if __name__ == "__main__":
    # Run improved backtest
    run_improved_backtest_demo()

    # Compare with original
    compare_with_original()
