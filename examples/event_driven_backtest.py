"""Example of using the event-driven backtesting engine.

This script demonstrates how to use the event-driven backtesting engine with
realistic execution features such as slippage, fees, and market impact.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fxml4.backtesting.event import SignalEvent
from fxml4.backtesting.event_driven_engine import (
    EventDrivenEngine,
    Portfolio,
    run_event_driven_backtest,
)
from fxml4.backtesting.execution import ExecutionHandler, HybridSlippageModel
from fxml4.backtesting.market_impact import MarketImpactHandler, PowerLawModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Reduce log volume for demo
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)


# Simple example strategy: Moving Average Crossover
def ma_crossover_strategy(
    symbol: str,
    current_bar: pd.Series,
    market_data: Optional[pd.DataFrame],
    portfolio: Optional[Portfolio] = None,
) -> Dict[str, Dict]:
    """Moving average crossover strategy.

    Args:
        symbol: Market symbol.
        current_bar: Current price bar.
        market_data: Historical market data.
        portfolio: Portfolio instance.

    Returns:
        Dictionary of signals.
    """
    signals = {}

    # Need enough data for moving averages
    if market_data is None or len(market_data) < 50:
        return signals

    # Calculate moving averages
    short_window = 20
    long_window = 50

    if len(market_data) >= long_window:
        # Use only close prices for the moving averages
        close_prices = market_data["close"]

        short_ma = close_prices.rolling(window=short_window).mean()
        long_ma = close_prices.rolling(window=long_window).mean()

        # Get current and previous MAs
        current_short_ma = short_ma.iloc[-1]
        current_long_ma = long_ma.iloc[-1]

        # Check if we have enough data for previous values
        if len(short_ma) > 1 and len(long_ma) > 1:
            prev_short_ma = short_ma.iloc[-2]
            prev_long_ma = long_ma.iloc[-2]

            # Check for crossover
            # Buy signal: short MA crosses above long MA
            if prev_short_ma <= prev_long_ma and current_short_ma > current_long_ma:
                signals["entry"] = {
                    "side": "buy",
                    "order_type": "market",
                    "risk_pct": 0.02,
                    "stop_loss": current_bar["close"] * 0.98,  # 2% stop loss
                    "position_sizing": "fixed_risk",
                }

            # Sell signal: short MA crosses below long MA
            elif prev_short_ma >= prev_long_ma and current_short_ma < current_long_ma:
                # Check if we have an open position
                if portfolio and symbol in portfolio.positions:
                    signals["exit"] = {
                        "order_type": "market",
                    }
                else:
                    # If we don't have a position, generate a short signal
                    signals["entry"] = {
                        "side": "sell",
                        "order_type": "market",
                        "risk_pct": 0.02,
                        "stop_loss": current_bar["close"] * 1.02,  # 2% stop loss
                        "position_sizing": "fixed_risk",
                    }

    return signals


def load_sample_data() -> pd.DataFrame:
    """Load sample forex data.

    Returns:
        DataFrame with sample data.
    """
    # Generate sample forex data (EURUSD)
    np.random.seed(42)

    # Create date range
    dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="1h")

    # Generate random walk prices
    price = 1.1000  # Starting price
    prices = [price]

    for _ in range(1, len(dates)):
        # Random price change with some mean reversion
        change = np.random.normal(0, 0.0005)
        # Add some mean reversion
        mean_reversion = (1.1000 - price) * 0.01
        price = price + change + mean_reversion
        prices.append(price)

    # Create volume data
    volumes = np.random.lognormal(mean=10, sigma=1, size=len(dates))

    # Generate OHLC data
    data = pd.DataFrame(
        {
            "time": dates,
            "open": prices,
            "high": [p * (1 + np.random.uniform(0, 0.001)) for p in prices],
            "low": [p * (1 - np.random.uniform(0, 0.001)) for p in prices],
            "close": [p * (1 + np.random.normal(0, 0.0002)) for p in prices],
            "volume": volumes,
            "symbol": "EURUSD",
        }
    )

    return data


def create_multi_symbol_data() -> Dict[str, pd.DataFrame]:
    """Create sample data for multiple symbols.

    Returns:
        Dictionary of DataFrames by symbol.
    """
    # Create data for EURUSD
    eurusd_data = load_sample_data()

    # Create data for GBPUSD with some correlation to EURUSD
    np.random.seed(43)
    dates = eurusd_data["time"].copy()

    price = 1.3000  # Starting price for GBPUSD
    eurusd_changes = eurusd_data["close"].pct_change().fillna(0).values

    prices = [price]
    for i in range(1, len(dates)):
        # Correlated change with EURUSD (0.7 correlation) plus some noise
        eurusd_change = eurusd_changes[i]
        gbpusd_change = 0.7 * eurusd_change + 0.3 * np.random.normal(0, 0.0005)
        price = price * (1 + gbpusd_change)
        prices.append(price)

    # Generate OHLC data for GBPUSD
    gbpusd_data = pd.DataFrame(
        {
            "time": dates,
            "open": prices,
            "high": [p * (1 + np.random.uniform(0, 0.001)) for p in prices],
            "low": [p * (1 - np.random.uniform(0, 0.001)) for p in prices],
            "close": [p * (1 + np.random.normal(0, 0.0002)) for p in prices],
            "volume": np.random.lognormal(mean=9, sigma=1, size=len(dates)),
            "symbol": "GBPUSD",
        }
    )

    # Create data for USDJPY (negative correlation with EURUSD)
    np.random.seed(44)
    price = 110.00  # Starting price for USDJPY

    prices = [price]
    for i in range(1, len(dates)):
        # Negatively correlated change with EURUSD (-0.5 correlation) plus some noise
        eurusd_change = eurusd_changes[i]
        usdjpy_change = -0.5 * eurusd_change + 0.5 * np.random.normal(0, 0.0005)
        price = price * (1 + usdjpy_change)
        prices.append(price)

    # Generate OHLC data for USDJPY
    usdjpy_data = pd.DataFrame(
        {
            "time": dates,
            "open": prices,
            "high": [p * (1 + np.random.uniform(0, 0.001)) for p in prices],
            "low": [p * (1 - np.random.uniform(0, 0.001)) for p in prices],
            "close": [p * (1 + np.random.normal(0, 0.0002)) for p in prices],
            "volume": np.random.lognormal(mean=9.5, sigma=1, size=len(dates)),
            "symbol": "USDJPY",
        }
    )

    # Return as dict of DataFrames by symbol
    return {
        "EURUSD": eurusd_data,
        "GBPUSD": gbpusd_data,
        "USDJPY": usdjpy_data,
    }


def run_simple_backtest():
    """Run a simple backtest with the event-driven engine."""
    # Load sample data
    data = load_sample_data()

    # Run backtest
    result = run_event_driven_backtest(
        strategy=ma_crossover_strategy,
        data=data,
        initial_capital=10000.0,
        fee_model="forex",
    )

    # Print results
    print("\nBacktest Results:")
    print(f"Strategy: {result.strategy_name}")
    print(f"Symbol: {result.symbol}")
    print(f"Period: {result.start_date} to {result.end_date}")
    print(f"Initial Capital: ${result.initial_capital:.2f}")
    print(f"Final Capital: ${result.final_capital:.2f}")
    print(f"Total Return: ${result.total_return:.2f} ({result.total_return_pct:.2f}%)")
    print(f"Annualized Return: {result.annualized_return:.2f}%")
    print(f"Max Drawdown: {result.max_drawdown_pct:.2f}%")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Sortino Ratio: {result.sortino_ratio:.2f}")
    print(f"Win Rate: {result.win_rate * 100:.2f}%")
    print(f"Profit Factor: {result.profit_factor:.2f}")
    print(f"Avg Profit per Trade: ${result.avg_profit_per_trade:.2f}")
    print(f"Avg Loss per Trade: ${result.avg_loss_per_trade:.2f}")
    print(f"Total Trades: {len(result.trades)}")

    # Plot equity curve
    plt.figure(figsize=(12, 6))
    plt.plot(result.equity_curve["timestamp"], result.equity_curve["equity"])
    plt.title("Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def run_multi_symbol_backtest():
    """Run a multi-symbol backtest with the event-driven engine."""
    # Load multi-symbol data
    data_dict = create_multi_symbol_data()

    # Create slippage model with realistic parameters
    slippage_model = HybridSlippageModel(
        base_slippage_pct=0.0001,
        volume_factor=0.1,
        volatility_window=20,
        volatility_factor=0.5,
        random_factor=0.2,
        max_slippage_pct=0.001,
    )

    # Create market impact model
    market_impact = MarketImpactHandler(
        model=PowerLawModel(
            k=0.1,
            exponent=0.6,
            volatility_window=20,
            adv_window=20,
        )
    )

    # Create execution handler with slippage and market impact
    execution_handler = ExecutionHandler(slippage_model=slippage_model)

    # Create portfolio with initial capital
    portfolio = Portfolio(initial_capital=10000.0, fee_model="forex")

    # Create event-driven engine
    engine = EventDrivenEngine(
        strategy=ma_crossover_strategy,
        portfolio=portfolio,
        execution_handler=execution_handler,
    )

    # Load data and run backtest
    engine.load_data(data_dict)
    result = engine.run()

    # Print results
    print("\nMulti-Symbol Backtest Results:")
    print(f"Symbols: {result.symbol}")
    print(f"Period: {result.start_date} to {result.end_date}")
    print(f"Initial Capital: ${result.initial_capital:.2f}")
    print(f"Final Capital: ${result.final_capital:.2f}")
    print(f"Total Return: ${result.total_return:.2f} ({result.total_return_pct:.2f}%)")
    print(f"Annualized Return: {result.annualized_return:.2f}%")
    print(f"Max Drawdown: {result.max_drawdown_pct:.2f}%")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Sortino Ratio: {result.sortino_ratio:.2f}")
    print(f"Win Rate: {result.win_rate * 100:.2f}%")
    print(f"Profit Factor: {result.profit_factor:.2f}")
    print(f"Total Trades: {len(result.trades)}")

    # Get detailed results
    detailed_results = engine.get_results()

    # Plot equity curve
    plt.figure(figsize=(12, 6))
    equity_df = pd.DataFrame(detailed_results["equity_curve"])
    plt.plot(equity_df["timestamp"], equity_df["equity"])
    plt.title("Multi-Symbol Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.grid(True)
    plt.tight_layout()

    # Plot trades by symbol
    trades_df = pd.DataFrame(detailed_results["trades"])

    if not trades_df.empty:
        plt.figure(figsize=(12, 6))
        for symbol in trades_df["symbol"].unique():
            symbol_trades = trades_df[trades_df["symbol"] == symbol]
            plt.scatter(
                x=symbol_trades["close_time"],
                y=symbol_trades["realized_pnl"],
                label=symbol,
                alpha=0.7,
                s=50,
            )
        plt.axhline(y=0, color="black", linestyle="--")
        plt.title("Trade P&L by Symbol")
        plt.xlabel("Date")
        plt.ylabel("P&L ($)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()

    plt.show()


def compare_slippage_settings():
    """Compare different slippage settings to demonstrate their impact."""
    # Load sample data
    data = load_sample_data()

    # Different slippage levels to test
    slippage_levels = {
        "None": None,  # No slippage
        "Low": HybridSlippageModel(
            base_slippage_pct=0.00005,
            volume_factor=0.05,
            volatility_factor=0.3,
            max_slippage_pct=0.0005,
        ),
        "Medium": HybridSlippageModel(
            base_slippage_pct=0.0001,
            volume_factor=0.1,
            volatility_factor=0.5,
            max_slippage_pct=0.001,
        ),
        "High": HybridSlippageModel(
            base_slippage_pct=0.0002,
            volume_factor=0.2,
            volatility_factor=1.0,
            max_slippage_pct=0.003,
        ),
    }

    # Store results for comparison
    results = {}

    # Run backtest with each slippage setting
    for name, slippage_model in slippage_levels.items():
        print(f"\nRunning backtest with {name} slippage...")
        result = run_event_driven_backtest(
            strategy=ma_crossover_strategy,
            data=data,
            initial_capital=10000.0,
            fee_model="forex",
            slippage_model=slippage_model,
        )

        results[name] = {
            "final_capital": result.final_capital,
            "return_pct": result.total_return_pct,
            "win_rate": result.win_rate,
            "equity_curve": result.equity_curve,
        }

    # Compare and visualize results
    print("\nSlippage Comparison Results:")
    for name, result in results.items():
        print(f"{name} Slippage:")
        print(f"  Final Capital: ${result['final_capital']:.2f}")
        print(f"  Return: {result['return_pct']:.2f}%")
        print(f"  Win Rate: {result['win_rate'] * 100:.2f}%")

    # Plot equity curves
    plt.figure(figsize=(12, 6))
    for name, result in results.items():
        equity_df = result["equity_curve"]
        plt.plot(equity_df["timestamp"], equity_df["equity"], label=f"{name} Slippage")

    plt.title("Equity Curves with Different Slippage Models")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    print("=== FXML4 Event-Driven Backtesting Examples ===")

    # Run the simple backtest example
    print("\n1. Running simple single-symbol backtest...")
    run_simple_backtest()

    # Run the multi-symbol backtest example
    print("\n2. Running multi-symbol backtest...")
    run_multi_symbol_backtest()

    # Compare different slippage settings
    print("\n3. Comparing different slippage settings...")
    compare_slippage_settings()
