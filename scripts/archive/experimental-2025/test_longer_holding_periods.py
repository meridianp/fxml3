#!/usr/bin/env python
"""Test strategy with longer holding periods (3-10 days)."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from fxml4.strategy.dynamic_exit_strategy import DynamicExitStrategy, ExitConfig
from fxml4.strategy.market_regime_detector import MarketRegimeDetector, RegimeConfig

print("=" * 80)
print("TESTING LONGER HOLDING PERIODS")
print("=" * 80)


class LongerHoldingStrategy:
    """Test strategy with extended holding periods."""

    def __init__(self, symbol: str, initial_capital: float = 10000.0):
        self.symbol = symbol
        self.initial_capital = initial_capital

        # Load model
        self.model = joblib.load(f"models/{symbol}/best_model_lightgbm.joblib")
        self.scaler = joblib.load(f"models/{symbol}/scaler.joblib")

        # Load data
        self.df = pd.read_parquet(
            f"data/features/{symbol}_4h_features_advanced.parquet"
        )
        self.feature_cols = [
            col
            for col in self.df.columns
            if col not in ["open", "high", "low", "close", "volume"]
        ]

    def run_backtest(
        self,
        start_date: str,
        end_date: str,
        holding_days: int,
        confidence_threshold: float = 0.65,
        use_confidence_sizing: bool = True,
    ):
        """Run backtest with specified holding period."""

        test_data = self.df[start_date:end_date]

        # Convert holding days to 4h bars
        holding_bars = holding_days * 6  # 6 bars per day

        # Initialize components
        exit_strategy = DynamicExitStrategy(
            ExitConfig(
                initial_stop_atr_multiplier=2.5,  # Wider stop for longer holds
                trailing_stop_atr_multiplier=2.0,
                tp_levels=[1.5, 3.0, 4.5, 6.0],  # Higher targets for longer holds
                tp_portions=[0.25, 0.25, 0.25, 0.25],
                max_holding_bars=holding_bars,
                exit_on_opposite_signal=True,
                exit_on_weak_signal=False,  # Don't exit on weak signals for longer holds
                weak_signal_threshold=0.5,
            )
        )

        regime_detector = MarketRegimeDetector(
            RegimeConfig(
                adx_trend_threshold=25.0,  # Stronger trend requirement
                efficiency_threshold=0.30,
            )
        )

        # Backtest state
        equity = self.initial_capital
        positions = {}
        trades = []
        position_counter = 0

        print(f"\nTesting {holding_days} day holding period")
        print(f"Period: {test_data.index[0]} to {test_data.index[-1]}")
        print(f"Bars: {len(test_data)}")

        # Main loop
        for i in range(100, len(test_data)):
            current_bar = test_data.iloc[i]
            current_time = test_data.index[i]
            current_price = current_bar["close"]
            current_atr = current_bar.get("atr_14", current_price * 0.001)

            # Check exits
            for pos_id in list(positions.keys()):
                pos = positions[pos_id]

                # Get current signal
                try:
                    X = test_data[self.feature_cols].iloc[i : i + 1]
                    if not X.isnull().any().any():
                        X_scaled = self.scaler.transform(X)
                        pred = self.model.predict(X_scaled)[0]
                        proba = self.model.predict_proba(X_scaled)[0]
                        signal = pred - 1
                        confidence = max(proba)
                    else:
                        signal = 0
                        confidence = 0.5
                except:
                    signal = 0
                    confidence = 0.5

                # Check exit
                should_exit, exit_price, exit_reason, exit_size = (
                    exit_strategy.update_position(
                        pos_id, current_price, current_atr, signal, confidence
                    )
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
                            "days_held": (
                                i - test_data.index.get_loc(pos["entry_time"])
                            )
                            / 6,
                        }
                    )

                    pos["remaining_size"] -= exit_size
                    if pos["remaining_size"] <= 0:
                        del positions[pos_id]
                        exit_strategy.remove_position(pos_id)

            # New signals (one position at a time)
            if len(positions) == 0:
                try:
                    X = test_data[self.feature_cols].iloc[i : i + 1]
                    if not X.isnull().any().any():
                        X_scaled = self.scaler.transform(X)
                        pred = self.model.predict(X_scaled)[0]
                        proba = self.model.predict_proba(X_scaled)[0]
                        signal = pred - 1
                        confidence = max(proba)
                    else:
                        continue
                except:
                    continue

                if signal != 0 and confidence > confidence_threshold:
                    # Market regime check
                    global_idx = self.df.index.get_loc(current_time)
                    regime_analysis = regime_detector.analyze_market(
                        self.df, global_idx
                    )

                    # Stronger filter for longer holds
                    if (
                        regime_analysis["is_tradeable"]
                        and regime_analysis["trend_strength"] > 30
                    ):
                        position_counter += 1
                        pos_id = f"pos_{position_counter}"

                        # Position sizing
                        if use_confidence_sizing:
                            # Scale by confidence
                            confidence_multiplier = 0.5 + (confidence - 0.5) * 2.0
                            base_size = (
                                equity
                                * 0.015
                                * confidence_multiplier
                                / (2.5 * current_atr)
                            )
                        else:
                            base_size = equity * 0.015 / (2.5 * current_atr)

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
                        }

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
                    "bars_held": len(test_data)
                    - test_data.index.get_loc(pos["entry_time"]),
                    "days_held": (
                        len(test_data) - test_data.index.get_loc(pos["entry_time"])
                    )
                    / 6,
                }
            )

        # Calculate results
        return self._calculate_results(trades, equity)

    def _calculate_results(self, trades, final_equity):
        """Calculate performance metrics."""
        if not trades:
            return {
                "total_return": 0,
                "num_trades": 0,
                "win_rate": 0,
                "avg_holding_days": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
            }

        trades_df = pd.DataFrame(trades)

        total_return = (final_equity - self.initial_capital) / self.initial_capital
        winning_trades = trades_df[trades_df["net_pnl"] > 0]
        win_rate = len(winning_trades) / len(trades_df)
        avg_holding_days = trades_df["days_held"].mean()

        # Sharpe estimation
        returns_per_trade = trades_df["net_pnl"] / self.initial_capital
        if returns_per_trade.std() > 0:
            sharpe = (
                returns_per_trade.mean()
                / returns_per_trade.std()
                * np.sqrt(252 * 6 / trades_df["bars_held"].mean())
            )
        else:
            sharpe = 0

        # Max drawdown
        cumulative_pnl = trades_df["net_pnl"].cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = (cumulative_pnl - running_max) / self.initial_capital
        max_drawdown = drawdown.min()

        return {
            "total_return": total_return,
            "num_trades": len(trades_df),
            "win_rate": win_rate,
            "avg_holding_days": avg_holding_days,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "final_equity": final_equity,
            "trades_df": trades_df,
        }


def main():
    # Test different holding periods
    holding_periods = [3, 5, 7, 10]  # days
    confidence_thresholds = [0.60, 0.65, 0.70]

    strategy = LongerHoldingStrategy("GBPUSD", initial_capital=10000.0)

    results = []

    print("\nTesting different holding periods and confidence thresholds...")

    for days in holding_periods:
        for conf_threshold in confidence_thresholds:
            result = strategy.run_backtest(
                "2023-01-01",
                "2024-06-30",
                holding_days=days,
                confidence_threshold=conf_threshold,
                use_confidence_sizing=True,
            )

            result["holding_days"] = days
            result["confidence_threshold"] = conf_threshold
            results.append(result)

            print(f"\n{days} days, {conf_threshold} confidence:")
            print(f"  Return: {result['total_return']*100:.2f}%")
            print(f"  Trades: {result['num_trades']}")
            print(f"  Win Rate: {result['win_rate']*100:.1f}%")
            print(f"  Sharpe: {result['sharpe_ratio']:.2f}")

    # Find best configuration
    best_result = max(
        results, key=lambda x: x["sharpe_ratio"] if x["num_trades"] > 5 else -np.inf
    )

    print("\n" + "=" * 80)
    print("BEST CONFIGURATION")
    print("=" * 80)
    print(f"Holding Period: {best_result['holding_days']} days")
    print(f"Confidence Threshold: {best_result['confidence_threshold']}")
    print(f"Total Return: {best_result['total_return']*100:.2f}%")
    print(f"Win Rate: {best_result['win_rate']*100:.1f}%")
    print(f"Sharpe Ratio: {best_result['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {best_result['max_drawdown']*100:.2f}%")
    print(f"Number of Trades: {best_result['num_trades']}")
    print(f"Average Holding: {best_result['avg_holding_days']:.1f} days")

    # Compare with original short holding
    print("\n" + "=" * 80)
    print("COMPARISON: SHORT vs LONG HOLDING")
    print("=" * 80)
    print(f"Original (9.1 hours): +0.10% return, 79.4% win rate")
    print(
        f"Best Long ({best_result['holding_days']} days): {best_result['total_return']*100:+.2f}% return, {best_result['win_rate']*100:.1f}% win rate"
    )

    # Exit reason analysis for best config
    if "trades_df" in best_result:
        trades_df = best_result["trades_df"]
        exit_counts = trades_df["exit_reason"].value_counts()
        print(f"\nExit Reasons (Best Config):")
        for reason, count in exit_counts.items():
            print(f"  {reason}: {count} ({count/len(trades_df)*100:.1f}%)")


if __name__ == "__main__":
    main()
