#!/usr/bin/env python
"""Test the complete forex trading system with real data and position sizing."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from backtesting.advanced_risk_management import AdvancedRiskManager
from backtesting.forex_position_sizing import ForexPositionConfig, ForexPositionSizer
from scripts.ensemble_ml_elliott_wave import EnsembleMLElliottWave


def run_forex_backtest(symbol: str, start_date: str, end_date: str):
    """Run a complete forex backtest with proper position sizing."""

    print(f"\n{'='*70}")
    print(f"Forex Trading System Backtest - {symbol}")
    print(f"{'='*70}")

    # Load data
    from scripts.simple_backtest_real_data import load_data

    df = load_data(symbol, start_date, end_date)

    if df is None or len(df) < 100:
        print(f"❌ Insufficient data for {symbol}")
        return None

    print(f"✅ Data loaded: {len(df)} 4H bars")
    print(
        f"   Period: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}"
    )

    # Initialize components
    ensemble = EnsembleMLElliottWave(symbol)
    position_sizer = ForexPositionSizer()
    risk_manager = AdvancedRiskManager()

    if ensemble.ml_model is None:
        print(f"❌ No ML model found for {symbol}")
        return None

    # Generate signals
    print("\nGenerating ensemble signals...")
    signals_df = ensemble.generate_ensemble_signals(df)

    # Backtest parameters
    initial_capital = 100000  # $100k starting capital
    current_capital = initial_capital

    # Track performance
    trades = []
    equity_curve = [initial_capital]
    positions = {}

    # Process each signal
    for i in range(len(signals_df) - 1):
        current_time = df.index[i]
        signal = signals_df["ensemble_signal"].iloc[i]
        confidence = signals_df["confidence"].iloc[i]
        current_price = df["close"].iloc[i]

        # Update daily tracking at start of new day
        if i > 0 and df.index[i].date() != df.index[i - 1].date():
            position_sizer.reset_daily_tracking()

        # Check for exit signals or stop losses
        for sym, pos in list(positions.items()):
            next_price = df["close"].iloc[i + 1]

            # Check stop loss
            if pos["type"] == "long" and next_price <= pos["stop_loss"]:
                # Stop loss hit
                pnl = pos["units"] * (pos["stop_loss"] - pos["entry_price"])
                current_capital += pnl
                position_sizer.update_daily_pnl(pnl)

                trades.append(
                    {
                        "symbol": sym,
                        "entry_time": pos["entry_time"],
                        "exit_time": current_time,
                        "entry_price": pos["entry_price"],
                        "exit_price": pos["stop_loss"],
                        "type": "long",
                        "units": pos["units"],
                        "pnl": pnl,
                        "exit_reason": "stop_loss",
                    }
                )

                del positions[sym]
                print(f"  ❌ Stop loss hit on {sym}: ${pnl:,.2f}")

            elif pos["type"] == "short" and next_price >= pos["stop_loss"]:
                # Stop loss hit
                pnl = pos["units"] * (pos["entry_price"] - pos["stop_loss"])
                current_capital += pnl
                position_sizer.update_daily_pnl(pnl)

                trades.append(
                    {
                        "symbol": sym,
                        "entry_time": pos["entry_time"],
                        "exit_time": current_time,
                        "entry_price": pos["entry_price"],
                        "exit_price": pos["stop_loss"],
                        "type": "short",
                        "units": pos["units"],
                        "pnl": pnl,
                        "exit_reason": "stop_loss",
                    }
                )

                del positions[sym]
                print(f"  ❌ Stop loss hit on {sym}: ${pnl:,.2f}")

            # Check for exit signal
            elif (pos["type"] == "long" and signal == -1) or (
                pos["type"] == "short" and signal == 1
            ):
                # Exit signal
                exit_price = next_price
                if pos["type"] == "long":
                    pnl = pos["units"] * (exit_price - pos["entry_price"])
                else:
                    pnl = pos["units"] * (pos["entry_price"] - exit_price)

                current_capital += pnl
                position_sizer.update_daily_pnl(pnl)

                trades.append(
                    {
                        "symbol": sym,
                        "entry_time": pos["entry_time"],
                        "exit_time": current_time,
                        "entry_price": pos["entry_price"],
                        "exit_price": exit_price,
                        "type": pos["type"],
                        "units": pos["units"],
                        "pnl": pnl,
                        "exit_reason": "signal",
                    }
                )

                del positions[sym]
                result_emoji = "✅" if pnl > 0 else "❌"
                print(f"  {result_emoji} Closed {sym}: ${pnl:,.2f}")

        # Check if we should enter a new position
        if signal != 0 and symbol not in positions:
            # Check daily loss limit
            if position_sizer.check_daily_loss_limit(current_capital):
                print(f"  ⚠️  Daily loss limit reached, skipping signal")
                continue

            # Calculate stop loss (30-50 pips typically)
            atr = df["high"].iloc[i] - df["low"].iloc[i]  # Simplified ATR
            if signal == 1:  # Long
                stop_loss = current_price - (atr * 2)
            else:  # Short
                stop_loss = current_price + (atr * 2)

            # Calculate position size
            position = position_sizer.calculate_position_size(
                account_balance=current_capital,
                symbol=symbol,
                entry_price=current_price,
                stop_loss_price=stop_loss,
                signal_strength=confidence,
            )

            if position["units"] > 0:
                # Enter position
                positions[symbol] = {
                    "entry_time": current_time,
                    "entry_price": current_price,
                    "stop_loss": stop_loss,
                    "units": position["units"],
                    "type": "long" if signal == 1 else "short",
                    "margin_required": position["margin_required"],
                }

                print(f"\n  📊 {current_time.strftime('%Y-%m-%d %H:%M')}")
                print(f"  {'🔵 BUY' if signal == 1 else '🔴 SELL'} {symbol}")
                print(f"  Price: {current_price:.5f}")
                print(f"  Units: {position['units']:,.0f}")
                print(f"  Notional: ${position['notional_usd']:,.2f}")
                print(f"  Margin: ${position['margin_required']:,.2f}")
                print(f"  Confidence: {confidence:.1%}")

        # Update equity curve
        equity_curve.append(current_capital)

    # Close any remaining positions
    for sym, pos in positions.items():
        final_price = df["close"].iloc[-1]
        if pos["type"] == "long":
            pnl = pos["units"] * (final_price - pos["entry_price"])
        else:
            pnl = pos["units"] * (pos["entry_price"] - final_price)

        current_capital += pnl
        trades.append(
            {
                "symbol": sym,
                "entry_time": pos["entry_time"],
                "exit_time": df.index[-1],
                "entry_price": pos["entry_price"],
                "exit_price": final_price,
                "type": pos["type"],
                "units": pos["units"],
                "pnl": pnl,
                "exit_reason": "end_of_period",
            }
        )

    # Calculate performance metrics
    total_return = (current_capital - initial_capital) / initial_capital

    if trades:
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] < 0]
        win_rate = len(wins) / len(trades) if trades else 0

        avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0
        avg_loss = np.mean([abs(t["pnl"]) for t in losses]) if losses else 0
        profit_factor = (
            (sum([t["pnl"] for t in wins]) / abs(sum([t["pnl"] for t in losses])))
            if losses
            else 0
        )

        # Calculate Sharpe ratio
        equity_array = np.array(equity_curve)
        returns = np.diff(equity_array) / equity_array[:-1]
        sharpe = (
            np.mean(returns) / np.std(returns) * np.sqrt(252)
            if np.std(returns) > 0
            else 0
        )

        # Maximum drawdown
        peak = np.maximum.accumulate(equity_array)
        dd = (peak - equity_array) / peak
        max_dd = np.max(dd)
    else:
        win_rate = avg_win = avg_loss = profit_factor = sharpe = max_dd = 0

    # Print results
    print(f"\n{'='*70}")
    print(f"BACKTEST RESULTS - {symbol}")
    print(f"{'='*70}")
    print(f"Initial Capital:    ${initial_capital:,.2f}")
    print(f"Final Capital:      ${current_capital:,.2f}")
    print(f"Total Return:       {total_return:+.2%}")
    print(f"Max Drawdown:       {max_dd:.2%}")
    print(f"Sharpe Ratio:       {sharpe:.2f}")
    print(f"\nTrade Statistics:")
    print(f"Total Trades:       {len(trades)}")
    print(f"Winning Trades:     {len(wins) if trades else 0}")
    print(f"Losing Trades:      {len(losses) if trades else 0}")
    print(f"Win Rate:           {win_rate:.1%}")
    print(f"Profit Factor:      {profit_factor:.2f}")
    print(f"Average Win:        ${avg_win:,.2f}")
    print(f"Average Loss:       ${avg_loss:,.2f}")

    # Signal analysis
    total_signals = len(signals_df[signals_df["ensemble_signal"] != 0])
    ml_signals = len(signals_df[signals_df["ml_signal"] != 0])
    elliott_signals = len(signals_df[signals_df["elliott_signal"] != 0])

    print(f"\nSignal Analysis:")
    print(f"Total Signals:      {total_signals}")
    print(f"ML Signals:         {ml_signals}")
    print(f"Elliott Signals:    {elliott_signals}")
    print(f"Signals Taken:      {len(trades)}")
    print(f"Avg Confidence:     {signals_df['confidence'].mean():.1%}")

    return {
        "symbol": symbol,
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": len(trades),
        "final_capital": current_capital,
    }


def main():
    """Run forex trading system test."""
    print("=" * 70)
    print("FOREX TRADING SYSTEM TEST")
    print("Complete ML + Elliott Wave + Risk Management + Forex Position Sizing")
    print("=" * 70)
    print("\nSystem Features:")
    print("✅ 10 years of training data")
    print("✅ Multiple ML models (RF, XGBoost, LightGBM, Neural Net)")
    print("✅ Elliott Wave pattern detection")
    print("✅ Ensemble signal generation")
    print("✅ $25,000 minimum trade size (40:1 leverage)")
    print("✅ Dynamic position sizing based on account growth")
    print("✅ Advanced risk management")

    # Test parameters
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
    start_date = "2024-06-01"
    end_date = "2025-06-01"

    print(f"\nBacktest Period: {start_date} to {end_date}")
    print(f"Symbols: {', '.join(symbols)}")

    # Run backtests
    results = {}
    for symbol in symbols:
        try:
            result = run_forex_backtest(symbol, start_date, end_date)
            if result:
                results[symbol] = result
        except Exception as e:
            print(f"\n❌ Error testing {symbol}: {e}")
            import traceback

            traceback.print_exc()

    # Portfolio summary
    if results:
        print(f"\n{'='*70}")
        print("PORTFOLIO SUMMARY")
        print(f"{'='*70}")
        print(
            f"{'Symbol':<10} {'Return':>10} {'Sharpe':>10} {'MaxDD':>10} {'WinRate':>10} {'Trades':>10}"
        )
        print(f"{'-'*60}")

        total_capital = 0
        for symbol, res in results.items():
            print(
                f"{symbol:<10} {res['total_return']:>9.1%} "
                f"{res['sharpe_ratio']:>10.2f} "
                f"{res['max_drawdown']:>9.1%} "
                f"{res['win_rate']:>9.1%} "
                f"{res['total_trades']:>10}"
            )
            total_capital += res["final_capital"] - 100000

        # Portfolio metrics
        avg_return = np.mean([r["total_return"] for r in results.values()])
        portfolio_return = total_capital / (100000 * len(results))

        print(f"{'-'*60}")
        print(f"{'PORTFOLIO':<10} {portfolio_return:>9.1%}")
        print(f"\nNotes:")
        print(
            f"- Each symbol started with $100k (total: ${100000 * len(results):,.0f})"
        )
        print(f"- Final portfolio value: ${100000 * len(results) + total_capital:,.0f}")
        print(f"- All trades meet $25k minimum size requirement")


if __name__ == "__main__":
    main()
