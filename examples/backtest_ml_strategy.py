"""
Example: Backtesting ML Trading Strategy with FXML4

This example demonstrates how to:
1. Load data from TimescaleDB
2. Use a trained ML model for signal generation
3. Apply risk management
4. Run a backtest
5. Analyze results
"""

import os
import sys
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fxml4.backtesting import BacktestEngine, EventDrivenEngine, PerformanceAnalyzer
from fxml4.backtesting.data import TimescaleDataHandler
from fxml4.backtesting.position_sizing import ATRBasedSizer
from fxml4.backtesting.risk import AdvancedRiskManager
from fxml4.backtesting.strategy import (
    ClassificationMLStrategy,
    trend_filter,
    volatility_filter,
)


def load_ml_model(model_path: str):
    """Load a trained ML model."""
    if os.path.exists(model_path):
        return joblib.load(model_path)
    else:
        # Create a dummy model for demonstration
        from sklearn.ensemble import RandomForestClassifier

        model = RandomForestClassifier(n_estimators=100, random_state=42)
        # You would normally train this model
        return model


def main():
    """Run ML strategy backtest."""

    # Configuration
    config = {
        "symbol": "EURUSD",
        "start_date": "2024-01-01",
        "end_date": "2024-03-01",
        "timeframe": "1h",
        "initial_capital": 100000,
        "commission": 0.00002,  # 2 pips
        "slippage": 0.00001,  # 1 pip
    }

    # Database connection parameters
    db_params = {
        "host": os.environ.get("TIMESCALE_HOST", "localhost"),
        "port": os.environ.get("TIMESCALE_PORT", 5432),
        "database": os.environ.get("TIMESCALE_DB", "fxml4"),
        "user": os.environ.get("TIMESCALE_USER", "postgres"),
        "password": os.environ.get("TIMESCALE_PASSWORD", "password"),
    }

    print("1. Loading data from TimescaleDB...")
    try:
        data_handler = TimescaleDataHandler(
            connection_params=db_params,
            symbols=[config["symbol"]],
            start_date=config["start_date"],
            end_date=config["end_date"],
            timeframe=config["timeframe"],
        )
        print(f"   Loaded {len(data_handler.data_cache[config['symbol']])} bars")
    except Exception as e:
        print(f"   Failed to load from TimescaleDB: {e}")
        print("   Using sample data instead...")

        # Generate sample data for demonstration
        dates = pd.date_range(
            start=config["start_date"], end=config["end_date"], freq="1h"
        )

        sample_data = pd.DataFrame(
            {
                "open": np.random.randn(len(dates)).cumsum() + 1.1000,
                "high": np.random.randn(len(dates)).cumsum() + 1.1010,
                "low": np.random.randn(len(dates)).cumsum() + 1.0990,
                "close": np.random.randn(len(dates)).cumsum() + 1.1000,
                "volume": np.random.randint(1000, 10000, len(dates)),
                "rsi_14": np.random.uniform(30, 70, len(dates)),
                "atr_14": np.random.uniform(0.0005, 0.002, len(dates)),
                "macd_signal": np.random.randn(len(dates)) * 0.0001,
                "adx_14": np.random.uniform(20, 40, len(dates)),
            },
            index=dates,
        )

        # Create simple data handler
        from fxml4.backtesting.data import DataHandler

        data_handler = DataHandler()
        data_handler.data_cache = {config["symbol"]: sample_data}
        data_handler.symbols = [config["symbol"]]
        data_handler.current_index = {config["symbol"]: 0}

    print("\n2. Loading ML model...")
    model = load_ml_model("models/forex_classifier.pkl")

    # Define feature columns
    feature_columns = [
        "rsi_14",
        "macd_signal",
        "atr_14",
        "adx_14",
        "volume",
        "returns",
        "volatility",
    ]

    print("\n3. Setting up risk management...")
    # Position sizing based on ATR
    position_sizer = ATRBasedSizer(
        risk_per_trade=0.02,  # 2% risk per trade
        atr_multiplier=2.0,  # 2x ATR for stop loss
    )

    # Advanced risk manager
    risk_manager = AdvancedRiskManager(
        max_positions=3,
        max_risk_per_trade=0.02,
        max_daily_loss=0.05,
        max_correlation=0.7,
    )

    print("\n4. Creating ML strategy...")
    strategy = ClassificationMLStrategy(
        model=model,
        feature_columns=feature_columns,
        prediction_threshold=0.6,
        position_size=10000,  # Will be overridden by position sizer
        risk_manager=risk_manager,
        signal_filters=[trend_filter, volatility_filter],
    )

    print("\n5. Running backtest...")
    # Create event-driven engine
    engine = EventDrivenEngine(
        data_handler=data_handler,
        strategy=strategy,
        initial_capital=config["initial_capital"],
        commission=config["commission"],
        slippage=config["slippage"],
    )

    # Run backtest
    results = engine.run()

    print("\n6. Analyzing results...")
    analyzer = PerformanceAnalyzer()
    metrics = analyzer.calculate_metrics(results)

    # Display results
    print("\n" + "=" * 50)
    print("BACKTEST RESULTS")
    print("=" * 50)
    print(f"Period: {config['start_date']} to {config['end_date']}")
    print(f"Symbol: {config['symbol']}")
    print(f"Timeframe: {config['timeframe']}")
    print("\nPerformance Metrics:")
    print(f"  Initial Capital: ${config['initial_capital']:,.2f}")
    print(f"  Final Capital: ${metrics.get('final_capital', 0):,.2f}")
    print(f"  Total Return: {metrics.get('total_return_pct', 0):.2%}")
    print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
    print(f"  Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2%}")
    print(f"\nTrading Statistics:")
    print(f"  Total Trades: {metrics.get('total_trades', 0)}")
    print(f"  Win Rate: {metrics.get('win_rate', 0):.2%}")
    print(f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}")
    print(f"  Avg Win: ${metrics.get('avg_win', 0):,.2f}")
    print(f"  Avg Loss: ${metrics.get('avg_loss', 0):,.2f}")
    print(f"  Avg Trade Duration: {metrics.get('avg_trade_duration', 0):.1f} hours")

    # Save detailed results
    print("\n7. Saving results...")
    results_df = pd.DataFrame(results["trades"])
    results_df.to_csv("backtest_results.csv", index=False)

    # Plot equity curve
    try:
        import matplotlib.pyplot as plt

        equity_curve = results["equity_curve"]
        plt.figure(figsize=(12, 6))
        plt.plot(equity_curve.index, equity_curve.values)
        plt.title("Equity Curve")
        plt.xlabel("Date")
        plt.ylabel("Portfolio Value ($)")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig("equity_curve.png")
        print("   Equity curve saved to equity_curve.png")
    except ImportError:
        print("   Matplotlib not installed, skipping equity curve plot")

    print("\nBacktest complete!")

    # Additional analysis
    if "trades" in results and len(results["trades"]) > 0:
        trades_df = pd.DataFrame(results["trades"])

        # Best and worst trades
        best_trade = trades_df.loc[trades_df["pnl"].idxmax()]
        worst_trade = trades_df.loc[trades_df["pnl"].idxmin()]

        print(f"\nBest Trade:")
        print(f"  PnL: ${best_trade['pnl']:,.2f}")
        print(f"  Entry: {best_trade['entry_time']}")
        print(f"  Duration: {best_trade['duration_hours']:.1f} hours")

        print(f"\nWorst Trade:")
        print(f"  PnL: ${worst_trade['pnl']:,.2f}")
        print(f"  Entry: {worst_trade['entry_time']}")
        print(f"  Duration: {worst_trade['duration_hours']:.1f} hours")

        # Monthly breakdown
        trades_df["month"] = pd.to_datetime(trades_df["entry_time"]).dt.to_period("M")
        monthly_pnl = trades_df.groupby("month")["pnl"].sum()

        print("\nMonthly Performance:")
        for month, pnl in monthly_pnl.items():
            print(f"  {month}: ${pnl:,.2f}")


if __name__ == "__main__":
    main()
