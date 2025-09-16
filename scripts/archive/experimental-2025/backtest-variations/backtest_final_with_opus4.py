#!/usr/bin/env python
"""Final optimized strategy with Claude Opus 4 Elliott Wave analysis."""

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

from fxml4.llm_integration.llm_client import LLMClient
from fxml4.strategy.dynamic_exit_strategy import DynamicExitStrategy, ExitConfig
from fxml4.strategy.market_regime_detector import MarketRegimeDetector, RegimeConfig

print("=" * 80)
print("FINAL STRATEGY WITH CLAUDE OPUS 4 ELLIOTT WAVE")
print("=" * 80)


class Opus4EnhancedStrategy:
    """Trading strategy enhanced with Claude Opus 4 Elliott Wave analysis."""

    def __init__(self, symbol: str, initial_capital: float = 10000.0):
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.equity = initial_capital

        # Load ML model
        self.model = joblib.load(f"models/{symbol}/best_model_lightgbm.joblib")
        self.scaler = joblib.load(f"models/{symbol}/scaler.joblib")

        # Initialize Claude (uses LLM_MODEL from .env)
        self.llm_client = LLMClient(
            provider="anthropic"
            # Uses LLM_MODEL=claude-opus-4-20250514 from environment
        )

        # Cache for Elliott Wave analysis (to avoid repeated API calls)
        self.ew_cache = {}

        # Results tracking
        self.trades = []
        self.positions = {}
        self.equity_curve = []
        self.llm_calls = 0

    def get_elliott_wave_signal_opus4(self, data: pd.DataFrame, idx: int) -> tuple:
        """Get Elliott Wave signal using Claude Opus 4."""

        # Check cache first (cache by date to avoid repeated calls)
        cache_key = f"{data.index[idx].date()}"
        if cache_key in self.ew_cache:
            return self.ew_cache[cache_key]

        try:
            # Get 50 bars of history
            lookback = min(50, idx)
            history = data.iloc[idx - lookback : idx + 1]

            # Prepare concise price data
            price_lines = []
            step = max(1, len(history) // 20)  # Show ~20 bars
            for i in range(0, len(history), step):
                bar = history.iloc[i]
                price_lines.append(
                    f"{bar.name.strftime('%m/%d %H:%M')} | "
                    f"O:{bar['open']:.5f} H:{bar['high']:.5f} "
                    f"L:{bar['low']:.5f} C:{bar['close']:.5f}"
                )

            current_price = history["close"].iloc[-1]

            # Concise prompt for signal generation
            prompt = f"""Analyze this {self.symbol} 4H price data for Elliott Wave patterns:

{chr(10).join(price_lines)}

Current: {current_price:.5f}
20-bar High: {history['high'].tail(20).max():.5f}
20-bar Low: {history['low'].tail(20).min():.5f}

Provide:
1. Current wave position (e.g. "Wave 3 of III")
2. Pattern type (Impulse/Corrective)
3. Trading signal: BUY/SELL/NEUTRAL
4. Confidence: 0-100%

Be concise. Format:
WAVE: [position]
TYPE: [pattern]
SIGNAL: [BUY/SELL/NEUTRAL]
CONFIDENCE: [0-100]%"""

            # Get Claude's analysis
            response = self.llm_client.generate_text(
                prompt=prompt,
                system_prompt="You are an Elliott Wave expert. Analyze price patterns and provide trading signals based on wave position. Be precise and concise.",
                temperature=0.2,
                max_tokens=200,
            )

            self.llm_calls += 1

            # Parse response
            signal = 0
            confidence = 0.5

            response_upper = response.upper()
            if "SIGNAL: BUY" in response_upper:
                signal = 1
            elif "SIGNAL: SELL" in response_upper:
                signal = -1

            # Extract confidence
            import re

            conf_match = re.search(r"CONFIDENCE:\s*(\d+)", response_upper)
            if conf_match:
                confidence = int(conf_match.group(1)) / 100.0

            # Cache result
            self.ew_cache[cache_key] = (signal, confidence)

            return signal, confidence

        except Exception as e:
            print(f"Elliott Wave error: {e}")
            return 0, 0.5

    def run_backtest(self, start_date: str, end_date: str):
        """Run backtest with Claude Opus 4 enhanced signals."""

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
        print(f"Using Claude Opus 4 for Elliott Wave analysis")

        # Initialize strategies
        exit_strategy = DynamicExitStrategy(
            ExitConfig(
                initial_stop_atr_multiplier=1.5,
                trailing_stop_atr_multiplier=1.2,
                tp_levels=[0.8, 1.5, 2.5, 4.0],
                tp_portions=[0.3, 0.3, 0.2, 0.2],
                max_holding_bars=40,
                exit_on_opposite_signal=True,
                exit_on_weak_signal=True,
                weak_signal_threshold=0.6,
            )
        )

        regime_detector = MarketRegimeDetector(
            RegimeConfig(adx_trend_threshold=20.0, efficiency_threshold=0.20)
        )

        position_counter = 0
        ew_signals_used = 0

        # Main loop
        for i in range(100, len(test_data)):
            if i % 100 == 0:
                print(
                    f"Progress: {i}/{len(test_data)} bars, LLM calls: {self.llm_calls}"
                )

            current_bar = test_data.iloc[i]
            current_time = test_data.index[i]
            current_price = current_bar["close"]
            current_atr = current_bar.get("atr_14", current_price * 0.001)

            # Check exits
            for pos_id in list(self.positions.keys()):
                pos = self.positions[pos_id]

                # Get ML signal for exit
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
                            "used_ew": pos.get("used_ew", False),
                        }
                    )

                    pos["remaining_size"] -= exit_size
                    if pos["remaining_size"] <= 0:
                        del self.positions[pos_id]
                        exit_strategy.remove_position(pos_id)

            # Record equity
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

                # Get Elliott Wave signal from Claude Opus 4
                # Only call LLM if ML has decent confidence
                if ml_confidence > 0.6:
                    ew_signal, ew_confidence = self.get_elliott_wave_signal_opus4(
                        test_data, i
                    )
                else:
                    ew_signal, ew_confidence = 0, 0.5

                # Combine signals (70% ML, 30% Elliott Wave)
                combined_signal = 0.7 * ml_signal + 0.3 * ew_signal
                combined_confidence = 0.7 * ml_confidence + 0.3 * ew_confidence

                # Boost confidence if signals agree
                if ml_signal * ew_signal > 0:
                    combined_confidence = min(combined_confidence * 1.15, 0.95)

                # Discretize signal
                if combined_signal > 0.3:
                    final_signal = 1
                elif combined_signal < -0.3:
                    final_signal = -1
                else:
                    final_signal = 0

                # Entry criteria
                if final_signal != 0 and combined_confidence > 0.65:
                    # Market regime check
                    global_idx = df.index.get_loc(current_time)
                    regime_analysis = regime_detector.analyze_market(df, global_idx)

                    is_tradeable = regime_analysis["is_tradeable"] or (
                        regime_analysis["trend_strength"] > 30
                        and regime_analysis["volatility_regime"].value
                        in ["normal", "high"]
                    )

                    if is_tradeable:
                        position_counter += 1
                        pos_id = f"pos_{position_counter}"

                        # Confidence-based sizing
                        confidence_multiplier = 0.5 + (combined_confidence - 0.5) * 2.0
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
                            combined_confidence,
                        )

                        self.positions[pos_id] = {
                            "entry_time": current_time,
                            "entry_price": current_price,
                            "type": "long" if final_signal == 1 else "short",
                            "original_size": adjusted_size,
                            "remaining_size": adjusted_size,
                            "confidence": combined_confidence,
                            "used_ew": ew_signal != 0,
                        }

                        if ew_signal != 0:
                            ew_signals_used += 1

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
                    "used_ew": pos.get("used_ew", False),
                }
            )

        # Generate results
        self._generate_results(ew_signals_used)

    def _generate_results(self, ew_signals_used):
        """Generate results summary."""
        print("\n" + "=" * 80)
        print("CLAUDE OPUS 4 ENHANCED STRATEGY RESULTS")
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
            print(f"Elliott Wave Signals Used: {ew_signals_used}")
            print(f"Claude Opus 4 API Calls: {self.llm_calls}")

            # EW analysis
            ew_trades = trades_df[trades_df["used_ew"]]
            if len(ew_trades) > 0:
                ew_win_rate = len(ew_trades[ew_trades["net_pnl"] > 0]) / len(ew_trades)
                print(f"\nElliott Wave Enhanced Trades:")
                print(f"  Count: {len(ew_trades)}")
                print(f"  Win Rate: {ew_win_rate*100:.1f}%")
                print(f"  Avg P&L: ${ew_trades['net_pnl'].mean():.2f}")

            if len(winning) > 0:
                print(f"\nAverage Win: ${winning['net_pnl'].mean():.2f}")
                print(f"Largest Win: ${winning['net_pnl'].max():.2f}")

            if len(losing) > 0:
                print(f"Average Loss: ${losing['net_pnl'].mean():.2f}")
                print(f"Largest Loss: ${losing['net_pnl'].min():.2f}")

                if len(winning) > 0:
                    profit_factor = winning["net_pnl"].sum() / abs(
                        losing["net_pnl"].sum()
                    )
                    print(f"Profit Factor: {profit_factor:.2f}")

            # Risk metrics
            if len(self.equity_curve) > 1:
                equity_series = pd.Series([e["equity"] for e in self.equity_curve])
                returns = equity_series.pct_change().dropna()

                running_max = equity_series.expanding().max()
                drawdown = (equity_series - running_max) / running_max
                max_dd = drawdown.min()

                if returns.std() > 0:
                    sharpe = returns.mean() / returns.std() * np.sqrt(252 * 6)
                else:
                    sharpe = 0

                print(f"\nRisk Metrics:")
                print(f"Maximum Drawdown: {max_dd*100:.2f}%")
                print(f"Sharpe Ratio: {sharpe:.2f}")

        print("\n" + "=" * 80)
        print("CLAUDE OPUS 4 ENHANCEMENTS:")
        print("=" * 80)
        print("✓ Expert Elliott Wave analysis with proper wave notation")
        print("✓ Context-aware pattern recognition")
        print("✓ Intelligent caching to minimize API calls")
        print("✓ Enhanced signal confidence when ML and EW agree")
        print("✓ Professional-grade wave count interpretation")


def main():
    # Run strategy with Claude Opus 4
    strategy = Opus4EnhancedStrategy("GBPUSD", initial_capital=10000.0)

    print("\nRunning backtest with Claude Opus 4 Elliott Wave analysis...")
    print("Note: This will make API calls to Claude for wave analysis")

    # Test on recent period to minimize API calls
    strategy.run_backtest("2024-05-01", "2024-06-30")


if __name__ == "__main__":
    main()
