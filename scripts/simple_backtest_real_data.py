#!/usr/bin/env python
"""Simple backtest with real Polygon data."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import warnings
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from fxml4.features.feature_engineering import UnifiedFeatureEngineer


def load_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Load and resample data from parquet files."""
    # Use our polygon processed data path
    base_path = Path(f"/polygon/processed/C_{symbol}")

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    all_data = []
    current = start_dt

    while current <= end_dt:
        file_path = (
            base_path
            / f"year={current.year}"
            / f"month={current.month}"
            / f"day={current.day}"
            / "data.parquet.gz"
        )

        if file_path.exists():
            try:
                # Try to read with pyarrow if available, fallback to fastparquet
                try:
                    import pyarrow

                    df = pd.read_parquet(file_path, engine="pyarrow")
                except ImportError:
                    df = pd.read_parquet(file_path)

                # Set timestamp as index if it's a column
                if "timestamp" in df.columns:
                    df.set_index("timestamp", inplace=True)
                all_data.append(df)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                pass

        current += timedelta(days=1)

    if not all_data:
        return None

    # Combine and resample to 4H
    df = pd.concat(all_data).sort_index()
    df_4h = (
        df.resample("4h")
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

    return df_4h


def get_latest_model(symbol: str):
    """Get the latest trained model for a symbol."""
    model_dir = Path(f"models/{symbol}")
    if not model_dir.exists():
        return None, None, None

    # Find latest model file
    model_files = list(model_dir.glob("rf_model_*.joblib"))
    if not model_files:
        return None, None, None

    latest_model = sorted(model_files)[-1]
    # Extract full timestamp (date and time)
    timestamp_parts = latest_model.stem.split("_")[2:]  # Skip 'rf_model'
    timestamp = "_".join(timestamp_parts)

    # Load model, scaler, and metadata
    model = joblib.load(latest_model)
    scaler = joblib.load(model_dir / f"scaler_{timestamp}.joblib")

    with open(model_dir / f"metadata_{timestamp}.json", "r") as f:
        metadata = json.load(f)

    return model, scaler, metadata["feature_names"]


def simple_backtest(symbol: str):
    """Run a simple backtest for a symbol."""
    print(f"\n{'='*60}")
    print(f"Simple Backtest for {symbol}")
    print(f"{'='*60}")

    # Load model
    model, scaler, feature_names = get_latest_model(symbol)
    if model is None:
        print(f"❌ No trained model found for {symbol}")
        return None

    # Load data
    start_date = "2025-01-01"
    end_date = "2025-06-01"

    df = load_data(symbol, start_date, end_date)
    if df is None or len(df) < 100:
        print(f"❌ Insufficient data for backtest")
        return None

    print(f"✅ Loaded {len(df)} 4H bars")
    print(f"Period: {df.index[0]} to {df.index[-1]}")

    # Generate features
    feature_engineer = UnifiedFeatureEngineer()
    df_features = feature_engineer.generate_features(df)

    # Prepare features for prediction
    X = df_features[feature_names]

    # Remove rows with NaN
    valid_mask = ~X.isna().any(axis=1)
    X = X[valid_mask]
    df_features = df_features[valid_mask]

    # Scale features
    X_scaled = scaler.transform(X)

    # Get predictions
    predictions = model.predict(X_scaled)

    # Simple backtest logic
    initial_capital = 100000
    capital = initial_capital
    position = 0
    trades = []

    for i in range(len(predictions) - 1):
        current_price = df_features["close"].iloc[i]
        next_price = df_features["close"].iloc[i + 1]
        signal = predictions[i]

        # Position sizing: 2% risk per trade
        position_size = capital * 0.02 / current_price

        if signal == 1 and position <= 0:  # Buy signal
            # Close short if any
            if position < 0:
                pnl = position * (current_price - entry_price)
                capital += pnl
                trades.append(
                    {
                        "type": "close_short",
                        "price": current_price,
                        "pnl": pnl,
                        "capital": capital,
                    }
                )

            # Open long
            position = position_size
            entry_price = current_price
            trades.append(
                {
                    "type": "buy",
                    "price": current_price,
                    "size": position,
                    "capital": capital,
                }
            )

        elif signal == -1 and position >= 0:  # Sell signal
            # Close long if any
            if position > 0:
                pnl = position * (current_price - entry_price)
                capital += pnl
                trades.append(
                    {
                        "type": "close_long",
                        "price": current_price,
                        "pnl": pnl,
                        "capital": capital,
                    }
                )

            # Open short
            position = -position_size
            entry_price = current_price
            trades.append(
                {
                    "type": "sell",
                    "price": current_price,
                    "size": position,
                    "capital": capital,
                }
            )

    # Close final position
    if position != 0:
        final_price = df_features["close"].iloc[-1]
        pnl = position * (final_price - entry_price)
        capital += pnl
        trades.append(
            {
                "type": "close_final",
                "price": final_price,
                "pnl": pnl,
                "capital": capital,
            }
        )

    # Calculate metrics
    total_return = (capital - initial_capital) / initial_capital

    # Count wins/losses
    pnl_trades = [t for t in trades if "pnl" in t]
    if pnl_trades:
        wins = len([t for t in pnl_trades if t["pnl"] > 0])
        losses = len([t for t in pnl_trades if t["pnl"] <= 0])
        win_rate = wins / len(pnl_trades) if pnl_trades else 0

        avg_win = (
            np.mean([t["pnl"] for t in pnl_trades if t["pnl"] > 0]) if wins > 0 else 0
        )
        avg_loss = (
            np.mean([abs(t["pnl"]) for t in pnl_trades if t["pnl"] <= 0])
            if losses > 0
            else 0
        )
    else:
        wins = losses = 0
        win_rate = 0
        avg_win = avg_loss = 0

    # Print results
    print(f"\n{'='*40}")
    print("BACKTEST RESULTS")
    print(f"{'='*40}")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Final Capital: ${capital:,.2f}")
    print(f"Total Return: {total_return:.2%}")
    print(f"Total Trades: {len(pnl_trades)}")
    print(f"Win Rate: {win_rate:.2%}")
    print(f"Wins: {wins}, Losses: {losses}")
    print(f"Avg Win: ${avg_win:,.2f}")
    print(f"Avg Loss: ${avg_loss:,.2f}")

    # Signal distribution
    unique, counts = np.unique(predictions, return_counts=True)
    signal_dist = dict(zip(unique, counts))
    print(f"\nSignal Distribution:")
    for sig, count in signal_dist.items():
        label = {-1: "Sell", 0: "Hold", 1: "Buy"}[sig]
        pct = count / len(predictions) * 100
        print(f"  {label}: {count} ({pct:.1f}%)")

    return {
        "symbol": symbol,
        "total_return": total_return,
        "win_rate": win_rate,
        "total_trades": len(pnl_trades),
        "final_capital": capital,
    }


def main():
    """Run simple backtests for all symbols."""
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]

    print("Simple Backtest with Real Polygon Data")
    print(f"Symbols: {', '.join(symbols)}")

    results = {}
    for symbol in symbols:
        try:
            result = simple_backtest(symbol)
            if result:
                results[symbol] = result
        except Exception as e:
            print(f"❌ Error backtesting {symbol}: {e}")
            import traceback

            traceback.print_exc()

    # Summary
    if results:
        print(f"\n{'='*60}")
        print("BACKTEST SUMMARY")
        print(f"{'='*60}")
        print(f"{'Symbol':<10} {'Return':>10} {'Win Rate':>10} {'Trades':>10}")
        print(f"{'-'*40}")

        for symbol, res in results.items():
            print(
                f"{symbol:<10} {res['total_return']:>9.1%} "
                f"{res['win_rate']:>9.1%} "
                f"{res['total_trades']:>10}"
            )


if __name__ == "__main__":
    main()
