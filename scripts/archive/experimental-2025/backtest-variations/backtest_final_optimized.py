#!/usr/bin/env python
"""Final optimized strategy combining all improvements."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import warnings
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from fxml4.strategy.dynamic_exit_strategy import DynamicExitStrategy, ExitConfig
from fxml4.strategy.market_regime_detector import MarketRegimeDetector, RegimeConfig
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.fibonacci import FibonacciCalculator

print("=" * 80)
print("FINAL OPTIMIZED STRATEGY")
print("=" * 80)


class OptimizedStrategy:
    """Final optimized strategy for paper trading."""

    def __init__(self, symbol: str, initial_capital: float = 10000.0):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.equity = initial_capital

        # Load ML model
        self.model = joblib.load(f"models/{symbol}/best_model_lightgbm.joblib")
        self.scaler = joblib.load(f"models/{symbol}/scaler.joblib")

        # Elliott Wave components
        self.wave_analyzer = ElliottWaveAnalyzer()
        self.fib_calculator = FibonacciCalculator()

        # Optimal parameters based on testing
        self.confidence_threshold = 0.65
        self.use_elliott_wave = True
        self.ml_weight = 0.7
        self.ew_weight = 0.3

        # Results tracking
        self.trades = []
        self.positions = {}
        self.equity_curve = []
        self.signal_log = []

    def get_elliott_wave_signal(self, data: pd.DataFrame, idx: int) -> tuple:
        """Simplified Elliott Wave signal."""
        try:
            lookback = min(100, idx)
            history = data.iloc[idx - lookback : idx + 1]

            # Simple wave detection
            high_20 = history["high"].rolling(20).max()
            low_20 = history["low"].rolling(20).min()

            current_price = data.iloc[idx]["close"]

            # Trend detection
            if current_price > high_20.iloc[-5]:
                # Breaking above recent highs - bullish
                return 1, 0.7
            elif current_price < low_20.iloc[-5]:
                # Breaking below recent lows - bearish
                return -1, 0.7
            else:
                # Range-bound
                return 0, 0.5

        except:
            return 0, 0.5

    def run_backtest(self, start_date: str, end_date: str):
        """Run the final optimized backtest."""

        # Load data
        df = pd.read_parquet(
            f"data/features/{self.symbol}_4h_features_advanced.parquet"
        )
        test_data = df[start_date:end_date]

        # Get features
        feature_cols = [
            col
            for col in df.columns
            if col not in ["open", "high", "low", "close", "volume"]
        ]

        print(f"\nBacktest Configuration:")
        print(f"Period: {test_data.index[0]} to {test_data.index[-1]}")
        print(f"Total Bars: {len(test_data)}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Confidence Threshold: {self.confidence_threshold}")
        print(f"Elliott Wave Integration: {self.use_elliott_wave}")

        # Initialize strategies with optimal parameters
        exit_strategy = DynamicExitStrategy(
            ExitConfig(
                initial_stop_atr_multiplier=1.5,  # Tighter stops (proven better)
                trailing_stop_atr_multiplier=1.2,
                tp_levels=[0.8, 1.5, 2.5, 4.0],  # Original aggressive levels
                tp_portions=[0.3, 0.3, 0.2, 0.2],
                max_holding_bars=40,  # ~6.7 days max
                exit_on_opposite_signal=True,
                exit_on_weak_signal=True,
                weak_signal_threshold=0.6,
            )
        )

        regime_detector = MarketRegimeDetector(
            RegimeConfig(
                adx_trend_threshold=20.0, efficiency_threshold=0.20  # More permissive
            )
        )

        position_counter = 0
        signals_taken = 0
        signals_rejected = 0

        # Main loop
        for i in range(100, len(test_data)):
            if i % 500 == 0:
                print(f"Progress: {i}/{len(test_data)} bars")

            current_bar = test_data.iloc[i]
            current_time = test_data.index[i]
            current_price = current_bar["close"]
            current_atr = current_bar.get("atr_14", current_price * 0.001)

            # Check exits for existing positions
            for pos_id in list(self.positions.keys()):
                pos = self.positions[pos_id]

                # Get current signal
                try:
                    X = test_data[feature_cols].iloc[i : i + 1]
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

                # Dynamic exit check
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

                    self.equity += net_pnl

                    self.trades.append(
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
                        }
                    )

                    pos["remaining_size"] -= exit_size
                    if pos["remaining_size"] <= 0:
                        del self.positions[pos_id]
                        exit_strategy.remove_position(pos_id)

            # Record equity periodically
            if i % 20 == 0:
                self.equity_curve.append({"time": current_time, "equity": self.equity})

            # Check for new signals (max one position)
            if len(self.positions) == 0:
                # Get ML signal
                try:
                    X = test_data[feature_cols].iloc[i : i + 1]
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

                # Combine with Elliott Wave if enabled
                if self.use_elliott_wave:
                    ew_signal, ew_confidence = self.get_elliott_wave_signal(
                        test_data, i
                    )

                    # Weighted combination
                    combined_signal = (
                        self.ml_weight * ml_signal + self.ew_weight * ew_signal
                    )
                    combined_confidence = (
                        self.ml_weight * ml_confidence + self.ew_weight * ew_confidence
                    )

                    # Boost confidence if signals agree
                    if ml_signal * ew_signal > 0:
                        combined_confidence = min(combined_confidence * 1.15, 0.95)

                    # Discretize
                    if combined_signal > 0.3:
                        final_signal = 1
                    elif combined_signal < -0.3:
                        final_signal = -1
                    else:
                        final_signal = 0

                    final_confidence = combined_confidence
                else:
                    final_signal = ml_signal
                    final_confidence = ml_confidence

                # Entry criteria
                if final_signal != 0 and final_confidence > self.confidence_threshold:
                    # Market regime check
                    global_idx = df.index.get_loc(current_time)
                    regime_analysis = regime_detector.analyze_market(df, global_idx)

                    # More permissive filter
                    is_tradeable = regime_analysis["is_tradeable"] or (
                        regime_analysis["trend_strength"] > 30
                        and regime_analysis["volatility_regime"].value
                        in ["normal", "high"]
                    )

                    if is_tradeable:
                        position_counter += 1
                        pos_id = f"pos_{position_counter}"

                        # Confidence-based sizing
                        confidence_multiplier = 0.5 + (final_confidence - 0.5) * 2.0
                        base_size = (
                            self.equity
                            * 0.02
                            * confidence_multiplier
                            / (1.5 * current_atr)
                        )

                        adjusted_size = (
                            base_size * regime_analysis["position_size_multiplier"]
                        )

                        # Cap exposure
                        max_size = self.equity * 0.1 / current_price
                        adjusted_size = min(adjusted_size, max_size)

                        # Initialize dynamic exits
                        exit_levels = exit_strategy.initialize_position(
                            pos_id,
                            current_price,
                            "long" if final_signal == 1 else "short",
                            current_atr,
                            adjusted_size,
                            final_confidence,
                        )

                        self.positions[pos_id] = {
                            "entry_time": current_time,
                            "entry_price": current_price,
                            "type": "long" if final_signal == 1 else "short",
                            "original_size": adjusted_size,
                            "remaining_size": adjusted_size,
                            "confidence": final_confidence,
                            "ml_signal": ml_signal,
                            "ew_signal": ew_signal if self.use_elliott_wave else None,
                        }

                        signals_taken += 1

                        # Log signal
                        self.signal_log.append(
                            {
                                "time": current_time,
                                "type": "long" if final_signal == 1 else "short",
                                "ml_confidence": ml_confidence,
                                "final_confidence": final_confidence,
                                "regime": (
                                    regime_analysis["market_regime"].value
                                    if regime_analysis["market_regime"]
                                    else "unknown"
                                ),
                            }
                        )
                    else:
                        signals_rejected += 1

        # Close remaining positions
        for pos_id in list(self.positions.keys()):
            pos = self.positions[pos_id]
            exit_price = test_data.iloc[-1]["close"]

            if pos["type"] == "long":
                pnl = (exit_price - pos["entry_price"]) * pos["remaining_size"]
            else:
                pnl = (pos["entry_price"] - exit_price) * pos["remaining_size"]

            pnl -= pos["remaining_size"] * exit_price * 0.00007
            self.equity += pnl

            self.trades.append(
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
                }
            )

        # Generate results
        self._generate_results(signals_taken, signals_rejected)

    def _generate_results(self, signals_taken, signals_rejected):
        """Generate comprehensive results."""
        print("\n" + "=" * 80)
        print("FINAL OPTIMIZED STRATEGY RESULTS")
        print("=" * 80)

        total_return = (self.equity - self.initial_capital) / self.initial_capital

        print(f"\nPerformance Summary:")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Final Equity: ${self.equity:,.2f}")
        print(f"Total Return: {total_return*100:.2f}%")
        print(f"Total P&L: ${self.equity - self.initial_capital:,.2f}")

        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            winning = trades_df[trades_df["net_pnl"] > 0]
            losing = trades_df[trades_df["net_pnl"] <= 0]

            print(f"\nTrading Statistics:")
            print(f"Total Trades: {len(trades_df)}")
            print(
                f"Winning Trades: {len(winning)} ({len(winning)/len(trades_df)*100:.1f}%)"
            )
            print(
                f"Losing Trades: {len(losing)} ({len(losing)/len(trades_df)*100:.1f}%)"
            )
            print(f"Signals Taken: {signals_taken}")
            print(f"Signals Rejected: {signals_rejected}")

            if len(winning) > 0:
                print(f"Average Win: ${winning['net_pnl'].mean():.2f}")
                print(f"Largest Win: ${winning['net_pnl'].max():.2f}")

            if len(losing) > 0:
                print(f"Average Loss: ${losing['net_pnl'].mean():.2f}")
                print(f"Largest Loss: ${losing['net_pnl'].min():.2f}")

                if len(winning) > 0:
                    profit_factor = winning["net_pnl"].sum() / abs(
                        losing["net_pnl"].sum()
                    )
                    print(f"Profit Factor: {profit_factor:.2f}")

            # Exit analysis
            print(f"\nExit Analysis:")
            exit_counts = trades_df["exit_reason"].value_counts()
            for reason, count in exit_counts.items():
                print(f"  {reason}: {count} ({count/len(trades_df)*100:.1f}%)")

            # Holding period
            avg_bars = trades_df["bars_held"].mean()
            print(
                f"\nAverage Holding Period: {avg_bars:.1f} bars ({avg_bars*4:.1f} hours)"
            )

            # Risk metrics
            if len(self.equity_curve) > 1:
                equity_series = pd.Series([e["equity"] for e in self.equity_curve])
                returns = equity_series.pct_change().dropna()

                # Max drawdown
                running_max = equity_series.expanding().max()
                drawdown = (equity_series - running_max) / running_max
                max_dd = drawdown.min()

                # Sharpe
                if returns.std() > 0:
                    sharpe = returns.mean() / returns.std() * np.sqrt(252 * 6)
                else:
                    sharpe = 0

                print(f"\nRisk Metrics:")
                print(f"Maximum Drawdown: {max_dd*100:.2f}%")
                print(f"Sharpe Ratio: {sharpe:.2f}")

        # Strategy summary
        print("\n" + "=" * 80)
        print("STRATEGY CONFIGURATION SUMMARY")
        print("=" * 80)
        print("✓ ML Model: LightGBM with 65% confidence threshold")
        print("✓ Elliott Wave: Simple trend breakout detection (30% weight)")
        print("✓ Dynamic Exits: Signal reversal, trailing stops, partial profits")
        print("✓ Position Sizing: Confidence-scaled (0.5x-1.5x base)")
        print("✓ Risk Management: 2% risk per trade, max 10% exposure")
        print("✓ Market Regime: ADX > 20, efficiency > 0.20")
        print("✓ Holding Period: Up to 6.7 days with dynamic exits")

        # Save configuration for paper trading
        config = {
            "symbol": self.symbol,
            "initial_capital": self.initial_capital,
            "confidence_threshold": self.confidence_threshold,
            "use_elliott_wave": self.use_elliott_wave,
            "ml_weight": self.ml_weight,
            "ew_weight": self.ew_weight,
            "exit_config": {
                "initial_stop_atr": 1.5,
                "trailing_stop_atr": 1.2,
                "tp_levels": [0.8, 1.5, 2.5, 4.0],
                "tp_portions": [0.3, 0.3, 0.2, 0.2],
                "max_holding_bars": 40,
            },
            "performance": {
                "total_return": total_return,
                "num_trades": len(self.trades),
                "win_rate": len(winning) / len(trades_df) if self.trades else 0,
                "sharpe_ratio": sharpe if "sharpe" in locals() else 0,
            },
            "backtest_date": datetime.now().isoformat(),
        }

        with open("models/paper_trading_config.json", "w") as f:
            json.dump(config, f, indent=2)

        print(f"\n✅ Configuration saved to models/paper_trading_config.json")
        print(f"Ready for paper trading with ${self.initial_capital:,.2f}!")


def main():
    # Run final optimized strategy
    strategy = OptimizedStrategy("GBPUSD", initial_capital=10000.0)
    strategy.run_backtest("2023-01-01", "2024-06-30")

    # Test on recent data
    print("\n" + "=" * 80)
    print("TESTING ON RECENT DATA (2024)")
    print("=" * 80)

    strategy2024 = OptimizedStrategy("GBPUSD", initial_capital=10000.0)
    strategy2024.run_backtest("2024-01-01", "2024-06-30")


if __name__ == "__main__":
    main()
