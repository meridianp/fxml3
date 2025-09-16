#!/usr/bin/env python
"""Optimize strategy parameters including holding periods and thresholds."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
from collections import defaultdict
from datetime import datetime
from itertools import product

import joblib
import numpy as np
import pandas as pd

from fxml4.strategy.dynamic_exit_strategy import DynamicExitStrategy, ExitConfig
from fxml4.strategy.market_regime_detector import MarketRegimeDetector, RegimeConfig
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.fibonacci import FibonacciCalculator

print("=" * 80)
print("STRATEGY PARAMETER OPTIMIZATION")
print("=" * 80)

# Parameters to test
PARAMETER_GRID = {
    "confidence_threshold": [0.55, 0.60, 0.65, 0.70],
    "holding_period_bars": [18, 30, 45, 60],  # 3, 5, 7.5, 10 days (4h bars)
    "position_size_method": ["fixed", "confidence_scaled", "volatility_adjusted"],
    "signal_combination": ["ml_only", "ml_elliott_combined"],
    "trend_filter": [True, False],
    "stop_loss_atr": [1.5, 2.0, 2.5],
    "take_profit_levels": [
        [1.0, 2.0, 3.0],  # Conservative
        [0.8, 1.5, 2.5, 4.0],  # Aggressive
    ],
}


class StrategyOptimizer:
    """Optimize strategy parameters through backtesting."""

    def __init__(self, symbol: str, initial_capital: float = 10000.0):
        self.symbol = symbol
        self.initial_capital = initial_capital

        # Load model and data
        self.model = joblib.load(f"models/{symbol}/best_model_lightgbm.joblib")
        self.scaler = joblib.load(f"models/{symbol}/scaler.joblib")

        # Load data
        self.df = pd.read_parquet(
            f"data/features/{symbol}_4h_features_advanced.parquet"
        )
        self.test_data = self.df["2023-01-01":"2024-06-30"]

        # Get features
        self.feature_cols = [
            col
            for col in self.df.columns
            if col not in ["open", "high", "low", "close", "volume"]
        ]

        # Initialize Elliott Wave analyzer
        self.wave_analyzer = ElliottWaveAnalyzer()
        self.fib_calculator = FibonacciCalculator()

        print(f"Loaded {self.symbol} data: {len(self.test_data)} bars")
        print(f"Test period: {self.test_data.index[0]} to {self.test_data.index[-1]}")

    def get_elliott_wave_signal(self, data: pd.DataFrame, idx: int) -> tuple:
        """Get Elliott Wave signal and confidence."""
        try:
            # Get recent price data for wave analysis
            lookback = min(200, idx)
            recent_data = data.iloc[idx - lookback : idx + 1]

            # Analyze waves
            waves = self.wave_analyzer.identify_waves(recent_data)

            if not waves:
                return 0, 0.5

            # Get current wave
            current_wave = waves[-1]

            # Determine signal based on wave pattern
            if current_wave.get("type") == "impulse":
                if current_wave.get("wave_number") in [1, 3, 5]:
                    signal = 1 if current_wave.get("direction") == "up" else -1
                    confidence = 0.7
                else:
                    signal = 0
                    confidence = 0.5
            elif current_wave.get("type") == "corrective":
                # Counter-trend during corrections
                signal = -1 if current_wave.get("direction") == "up" else 1
                confidence = 0.6
            else:
                signal = 0
                confidence = 0.5

            return signal, confidence

        except:
            return 0, 0.5

    def calculate_position_size(
        self,
        method: str,
        confidence: float,
        volatility: float,
        equity: float,
        price: float,
    ) -> float:
        """Calculate position size based on method."""
        base_risk = 0.02  # 2% risk per trade

        if method == "fixed":
            risk_amount = equity * base_risk
            position_value = risk_amount / (2.0 * volatility)  # Assuming 2 ATR stop
            return position_value / price

        elif method == "confidence_scaled":
            # Scale position size by confidence (0.5x to 1.5x)
            confidence_multiplier = 0.5 + (confidence - 0.5) * 2.0
            risk_amount = equity * base_risk * confidence_multiplier
            position_value = risk_amount / (2.0 * volatility)
            return position_value / price

        elif method == "volatility_adjusted":
            # Inverse volatility sizing
            target_volatility = 0.15  # 15% annual volatility target
            current_volatility = volatility * np.sqrt(252 * 6)  # Annualized
            vol_scalar = min(target_volatility / current_volatility, 2.0)
            risk_amount = equity * base_risk * vol_scalar
            position_value = risk_amount / (2.0 * volatility)
            return position_value / price

        return 0

    def apply_trend_filter(self, data: pd.DataFrame, idx: int) -> bool:
        """Apply trend filter to determine if trade is allowed."""
        try:
            # Simple trend filter using moving averages
            ma_20 = data["sma_20"].iloc[idx]
            ma_50 = data["sma_50"].iloc[idx]
            ma_200 = data["sma_200"].iloc[idx]

            # Price position relative to MAs
            price = data["close"].iloc[idx]

            # Trend strength
            trend_aligned = (ma_20 > ma_50 > ma_200) or (  # Strong uptrend
                ma_20 < ma_50 < ma_200
            )  # Strong downtrend

            # ADX filter
            adx = data.get("adx_14", pd.Series()).iloc[idx]
            if pd.notna(adx):
                return trend_aligned and adx > 20

            return trend_aligned

        except:
            return True  # Allow trade if filter fails

    def run_backtest(self, params: dict) -> dict:
        """Run backtest with given parameters."""
        # Initialize components
        exit_config = ExitConfig(
            initial_stop_atr_multiplier=params["stop_loss_atr"],
            trailing_stop_atr_multiplier=params["stop_loss_atr"] * 0.8,
            tp_levels=params["take_profit_levels"],
            tp_portions=[1.0 / len(params["take_profit_levels"])]
            * len(params["take_profit_levels"]),
            max_holding_bars=params["holding_period_bars"],
            exit_on_opposite_signal=True,
            exit_on_weak_signal=True,
            weak_signal_threshold=0.6,
        )

        exit_strategy = DynamicExitStrategy(exit_config)
        regime_detector = MarketRegimeDetector(RegimeConfig())

        # Backtest state
        equity = self.initial_capital
        positions = {}
        trades = []
        position_counter = 0
        signals_taken = 0
        signals_rejected = 0

        # Process bars
        for i in range(100, len(self.test_data)):
            current_bar = self.test_data.iloc[i]
            current_time = self.test_data.index[i]
            current_price = current_bar["close"]
            current_atr = current_bar.get("atr_14", current_price * 0.001)

            # Check exits
            for pos_id in list(positions.keys()):
                pos = positions[pos_id]

                # Get current signal for exit
                try:
                    X = self.test_data[self.feature_cols].iloc[i : i + 1]
                    if not X.isnull().any().any():
                        X_scaled = self.scaler.transform(X)
                        pred = self.model.predict(X_scaled)[0]
                        proba = self.model.predict_proba(X_scaled)[0]
                        ml_signal = pred - 1
                        ml_confidence = max(proba)
                    else:
                        ml_signal = 0
                        ml_confidence = 0.5
                except:
                    ml_signal = 0
                    ml_confidence = 0.5

                # Dynamic exit check
                should_exit, exit_price, exit_reason, exit_size = (
                    exit_strategy.update_position(
                        pos_id, current_price, current_atr, ml_signal, ml_confidence
                    )
                )

                if should_exit:
                    # Calculate P&L
                    if pos["type"] == "long":
                        gross_pnl = (exit_price - pos["entry_price"]) * exit_size
                    else:
                        gross_pnl = (pos["entry_price"] - exit_price) * exit_size

                    # Apply costs
                    costs = exit_size * exit_price * 0.00007
                    net_pnl = gross_pnl - costs

                    # Update equity
                    equity += net_pnl

                    # Record trade
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
                            "bars_held": i
                            - self.test_data.index.get_loc(pos["entry_time"]),
                        }
                    )

                    # Update position
                    pos["remaining_size"] -= exit_size
                    if pos["remaining_size"] <= 0:
                        del positions[pos_id]
                        exit_strategy.remove_position(pos_id)

            # Check for new signals (max one position at a time)
            if len(positions) == 0:
                # Get ML signal
                try:
                    X = self.test_data[self.feature_cols].iloc[i : i + 1]
                    if not X.isnull().any().any():
                        X_scaled = self.scaler.transform(X)
                        pred = self.model.predict(X_scaled)[0]
                        proba = self.model.predict_proba(X_scaled)[0]
                        ml_signal = pred - 1
                        ml_confidence = max(proba)
                    else:
                        continue
                except:
                    continue

                # Combine with Elliott Wave if specified
                if params["signal_combination"] == "ml_elliott_combined":
                    ew_signal, ew_confidence = self.get_elliott_wave_signal(
                        self.test_data, i
                    )

                    # Weighted combination
                    combined_signal = 0.7 * ml_signal + 0.3 * ew_signal
                    combined_confidence = 0.7 * ml_confidence + 0.3 * ew_confidence

                    # Discretize signal
                    if combined_signal > 0.3:
                        signal = 1
                    elif combined_signal < -0.3:
                        signal = -1
                    else:
                        signal = 0
                    confidence = combined_confidence
                else:
                    signal = ml_signal
                    confidence = ml_confidence

                # Entry criteria
                if signal != 0 and confidence > params["confidence_threshold"]:
                    # Trend filter
                    if params["trend_filter"] and not self.apply_trend_filter(
                        self.test_data, i
                    ):
                        signals_rejected += 1
                        continue

                    # Market regime check
                    global_idx = self.df.index.get_loc(current_time)
                    regime_analysis = regime_detector.analyze_market(
                        self.df, global_idx
                    )

                    if not regime_analysis["is_tradeable"]:
                        signals_rejected += 1
                    else:
                        # Enter position
                        position_counter += 1
                        pos_id = f"pos_{position_counter}"

                        # Calculate size
                        size = self.calculate_position_size(
                            params["position_size_method"],
                            confidence,
                            current_atr,
                            equity,
                            current_price,
                        )

                        # Cap exposure
                        max_size = equity * 0.1 / current_price
                        size = min(size, max_size)

                        # Initialize dynamic exits
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

                        signals_taken += 1

        # Force close remaining positions
        for pos_id in list(positions.keys()):
            pos = positions[pos_id]
            exit_price = self.test_data.iloc[-1]["close"]

            if pos["type"] == "long":
                pnl = (exit_price - pos["entry_price"]) * pos["remaining_size"]
            else:
                pnl = (pos["entry_price"] - exit_price) * pos["remaining_size"]

            pnl -= pos["remaining_size"] * exit_price * 0.00007
            equity += pnl

            trades.append(
                {
                    "entry_time": pos["entry_time"],
                    "exit_time": self.test_data.index[-1],
                    "type": pos["type"],
                    "entry_price": pos["entry_price"],
                    "exit_price": exit_price,
                    "size": pos["remaining_size"],
                    "net_pnl": pnl,
                    "exit_reason": "end_of_test",
                    "bars_held": len(self.test_data)
                    - self.test_data.index.get_loc(pos["entry_time"]),
                }
            )

        # Calculate metrics
        if not trades:
            return {
                "params": params,
                "total_return": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "win_rate": 0,
                "num_trades": 0,
                "profit_factor": 0,
                "avg_holding_hours": 0,
            }

        trades_df = pd.DataFrame(trades)

        # Calculate metrics
        total_return = (equity - self.initial_capital) / self.initial_capital
        winning_trades = trades_df[trades_df["net_pnl"] > 0]
        losing_trades = trades_df[trades_df["net_pnl"] <= 0]

        win_rate = len(winning_trades) / len(trades_df) if len(trades_df) > 0 else 0

        # Profit factor
        if len(losing_trades) > 0 and losing_trades["net_pnl"].sum() < 0:
            profit_factor = winning_trades["net_pnl"].sum() / abs(
                losing_trades["net_pnl"].sum()
            )
        else:
            profit_factor = np.inf if len(winning_trades) > 0 else 0

        # Average holding period
        avg_bars = trades_df["bars_held"].mean()
        avg_hours = avg_bars * 4  # 4h bars

        # Simple Sharpe estimation
        returns_per_trade = trades_df["net_pnl"] / self.initial_capital
        if returns_per_trade.std() > 0:
            sharpe = (
                returns_per_trade.mean()
                / returns_per_trade.std()
                * np.sqrt(252 * 6 / avg_bars)
            )
        else:
            sharpe = 0

        # Max drawdown (simplified)
        cumulative_pnl = trades_df["net_pnl"].cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = (cumulative_pnl - running_max) / self.initial_capital
        max_drawdown = drawdown.min()

        return {
            "params": params,
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "num_trades": len(trades_df),
            "profit_factor": profit_factor,
            "avg_holding_hours": avg_hours,
            "signals_taken": signals_taken,
            "signals_rejected": signals_rejected,
        }

    def optimize(self):
        """Run optimization across parameter grid."""
        print("\nStarting optimization...")
        print(
            f"Testing {len(list(product(*PARAMETER_GRID.values())))} parameter combinations"
        )

        results = []

        # Test each parameter combination
        for i, params in enumerate(product(*PARAMETER_GRID.values())):
            param_dict = dict(zip(PARAMETER_GRID.keys(), params))

            if i % 10 == 0:
                print(f"Progress: {i}/{len(list(product(*PARAMETER_GRID.values())))}")

            try:
                result = self.run_backtest(param_dict)
                results.append(result)
            except Exception as e:
                print(f"Error with params {param_dict}: {e}")
                continue

        # Sort by Sharpe ratio
        results.sort(key=lambda x: x["sharpe_ratio"], reverse=True)

        return results


def main():
    # Run optimization
    optimizer = StrategyOptimizer("GBPUSD", initial_capital=10000.0)
    results = optimizer.optimize()

    print("\n" + "=" * 80)
    print("TOP 10 PARAMETER COMBINATIONS")
    print("=" * 80)

    for i, result in enumerate(results[:10]):
        print(f"\n#{i+1} - Sharpe: {result['sharpe_ratio']:.2f}")
        print(
            f"Return: {result['total_return']*100:.2f}%, Win Rate: {result['win_rate']*100:.1f}%"
        )
        print(
            f"Trades: {result['num_trades']}, Avg Hold: {result['avg_holding_hours']:.1f}h"
        )
        print(
            f"Max DD: {result['max_drawdown']*100:.2f}%, PF: {result['profit_factor']:.2f}"
        )
        print(f"Parameters:")
        for k, v in result["params"].items():
            print(f"  {k}: {v}")

    # Save best parameters
    best_params = results[0]["params"]
    with open("models/optimized_parameters.json", "w") as f:
        json.dump(
            {
                "best_params": best_params,
                "performance": {
                    "total_return": results[0]["total_return"],
                    "sharpe_ratio": results[0]["sharpe_ratio"],
                    "win_rate": results[0]["win_rate"],
                    "max_drawdown": results[0]["max_drawdown"],
                },
                "optimization_date": datetime.now().isoformat(),
            },
            f,
            indent=2,
        )

    print(f"\nBest parameters saved to models/optimized_parameters.json")

    # Test longer holding periods specifically
    print("\n" + "=" * 80)
    print("HOLDING PERIOD ANALYSIS")
    print("=" * 80)

    holding_results = defaultdict(list)
    for result in results:
        holding_days = result["params"]["holding_period_bars"] * 4 / 24
        holding_results[holding_days].append(result)

    for days in sorted(holding_results.keys()):
        avg_return = np.mean([r["total_return"] for r in holding_results[days]])
        avg_sharpe = np.mean([r["sharpe_ratio"] for r in holding_results[days]])
        avg_trades = np.mean([r["num_trades"] for r in holding_results[days]])

        print(f"\n{days:.1f} days holding period:")
        print(f"  Avg Return: {avg_return*100:.2f}%")
        print(f"  Avg Sharpe: {avg_sharpe:.2f}")
        print(f"  Avg Trades: {avg_trades:.1f}")


if __name__ == "__main__":
    main()
