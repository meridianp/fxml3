"""Example of using the risk management components in FXML4.

This script demonstrates how to use position sizing, stop-loss management,
drawdown control, and portfolio risk metrics in a backtesting context.
"""

import logging
import os
import sys
from datetime import datetime, timedelta
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
from fxml4.backtesting.risk_management import (
    DrawdownControl,
    KellyPositionSizer,
    PercentagePositionSizer,
    PortfolioRiskMetrics,
    RiskManager,
    StopLossManager,
    VolatilityPositionSizer,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Reduce log volume for demo
logging.getLogger("matplotlib").setLevel(logging.WARNING)


def load_sample_data() -> pd.DataFrame:
    """Load sample forex data.

    Returns:
        DataFrame with sample data.
    """
    # Generate sample forex data (EURUSD)
    np.random.seed(42)

    # Create date range
    dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="1h")

    # Generate random walk prices with trends and volatility clusters
    price = 1.1000  # Starting price
    prices = [price]
    volatilities = [0.0005]  # Starting volatility

    # Create trends and regimes
    trend_change_points = [int(len(dates) * x) for x in [0.25, 0.5, 0.75]]
    current_trend = 0.0001  # Initial trend

    for i in range(1, len(dates)):
        # Change trend at specified points
        if i in trend_change_points:
            current_trend = np.random.choice([-0.0001, 0, 0.0001])

        # Update volatility (volatility clustering)
        target_vol = np.random.choice([0.0003, 0.0005, 0.0010], p=[0.3, 0.5, 0.2])
        volatilities.append(volatilities[-1] * 0.9 + target_vol * 0.1)

        # Random price change with trend and time-varying volatility
        change = np.random.normal(0, volatilities[-1]) + current_trend

        # Add some mean reversion
        mean_reversion = (1.1000 - price) * 0.01
        price = price + change + mean_reversion
        prices.append(price)

    # Create volume data with some spikes
    base_volumes = np.random.lognormal(mean=10, sigma=1, size=len(dates))
    volume_spikes = (
        np.random.randint(0, 100, size=len(dates)) == 0
    )  # Random volume spikes
    volumes = base_volumes * (1 + 5 * volume_spikes)

    # Generate OHLC data with realistic high-low ranges
    data = pd.DataFrame(
        {
            "time": dates,
            "open": prices,
            "close": prices,  # Will adjust below
            "volume": volumes,
            "symbol": "EURUSD",
        }
    )

    # Create more realistic OHLC data
    for i in range(len(data)):
        volatility = volatilities[i]
        open_price = data.loc[i, "open"]

        # Randomly determine if candle is bullish or bearish
        if np.random.rand() < 0.5:  # Bullish
            data.loc[i, "close"] = open_price * (
                1 + np.random.normal(0.0001, volatility)
            )
            data.loc[i, "high"] = max(data.loc[i, "open"], data.loc[i, "close"]) * (
                1 + abs(np.random.normal(0, volatility))
            )
            data.loc[i, "low"] = min(data.loc[i, "open"], data.loc[i, "close"]) * (
                1 - abs(np.random.normal(0, volatility))
            )
        else:  # Bearish
            data.loc[i, "close"] = open_price * (
                1 - np.random.normal(0.0001, volatility)
            )
            data.loc[i, "high"] = max(data.loc[i, "open"], data.loc[i, "close"]) * (
                1 + abs(np.random.normal(0, volatility))
            )
            data.loc[i, "low"] = min(data.loc[i, "open"], data.loc[i, "close"]) * (
                1 - abs(np.random.normal(0, volatility))
            )

    # Adjust next day's open to be close to previous day's close
    for i in range(1, len(data)):
        prev_close = data.loc[i - 1, "close"]
        data.loc[i, "open"] = prev_close * (1 + np.random.normal(0, 0.0002))

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


# Simple example strategy: Moving Average Crossover with Risk Management
def ma_crossover_strategy_with_risk(
    symbol: str,
    current_bar: pd.Series,
    market_data: Optional[pd.DataFrame],
    portfolio: Optional[Portfolio] = None,
) -> Dict[str, Dict]:
    """Moving average crossover strategy with risk management.

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
                    # Risk management parameters
                    "risk_pct": 0.01,  # Risk 1% of portfolio per trade
                    "stop_type": "volatility",  # ATR-based stop loss
                    "atr_multiple": 2.0,  # Stop is 2 ATR below entry
                    "trailing_percentage": 0.01,  # 1% trailing stop when in profit
                    # Position sizing (overrides default in risk manager)
                    "position_sizing": "volatility",  # Volatility-based sizing
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
                        # Risk management parameters
                        "risk_pct": 0.01,  # Risk 1% of portfolio per trade
                        "stop_type": "volatility",  # ATR-based stop loss
                        "atr_multiple": 2.0,  # Stop is 2 ATR above entry
                        "trailing_percentage": 0.01,  # 1% trailing stop when in profit
                        # Position sizing
                        "position_sizing": "volatility",  # Volatility-based sizing
                    }

    return signals


def compare_position_sizers():
    """Compare different position sizing methods."""
    # Load sample data
    data = load_sample_data()

    # Different position sizers to test
    position_sizers = {
        "Fixed": PercentagePositionSizer(percentage=0.02),  # Fixed 2% of equity
        "Volatility": VolatilityPositionSizer(
            risk_pct=0.01
        ),  # 1% risk with ATR-based stops
        "Kelly": KellyPositionSizer(
            default_win_rate=0.55, default_win_loss_ratio=1.5, fraction=0.5
        ),
    }

    # Store results for comparison
    results = {}

    # Run backtest with each position sizer
    for name, position_sizer in position_sizers.items():
        print(f"\nRunning backtest with {name} position sizing...")

        # Create risk manager
        risk_manager = RiskManager(
            position_sizer=position_sizer,
            stop_loss_manager=StopLossManager(),
            drawdown_control=DrawdownControl(),
            max_positions=10,
            risk_per_trade_pct=0.01,
        )

        # Create portfolio and add risk manager
        portfolio = Portfolio(initial_capital=10000.0)
        portfolio.risk_manager = risk_manager

        # Create execution handler
        execution_handler = ExecutionHandler()

        # Create engine and run backtest
        engine = EventDrivenEngine(
            strategy=ma_crossover_strategy_with_risk,
            portfolio=portfolio,
            execution_handler=execution_handler,
        )

        engine.load_data(data)
        result = engine.run()

        # Store results
        results[name] = {
            "final_capital": result.final_capital,
            "return_pct": result.total_return_pct,
            "win_rate": result.win_rate,
            "drawdown": result.max_drawdown_pct,
            "sharpe": result.sharpe_ratio,
            "sortino": result.sortino_ratio,
            "equity_curve": result.equity_curve,
            "trades": result.trades,
        }

    # Compare and visualize results
    print("\nPosition Sizing Comparison Results:")
    for name, result in results.items():
        print(f"{name} Position Sizing:")
        print(f"  Final Capital: ${result['final_capital']:.2f}")
        print(f"  Return: {result['return_pct']:.2f}%")
        print(f"  Win Rate: {result['win_rate'] * 100:.2f}%")
        print(f"  Max Drawdown: {result['drawdown']:.2f}%")
        print(f"  Sharpe Ratio: {result['sharpe']:.2f}")
        print(f"  Sortino Ratio: {result['sortino']:.2f}")
        print(f"  Trades: {len(result['trades'])}")

    # Plot equity curves
    plt.figure(figsize=(12, 6))
    for name, result in results.items():
        equity_df = result["equity_curve"]
        plt.plot(equity_df["timestamp"], equity_df["equity"], label=f"{name} Sizing")

    plt.title("Equity Curves with Different Position Sizing Methods")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    # Plot trade sizes
    plt.figure(figsize=(12, 6))
    for name, result in results.items():
        trade_sizes = [t.quantity for t in result["trades"]]
        if trade_sizes:
            plt.hist(trade_sizes, bins=20, alpha=0.5, label=f"{name} Sizing")

    plt.title("Distribution of Trade Sizes by Position Sizing Method")
    plt.xlabel("Position Size (quantity)")
    plt.ylabel("Frequency")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    plt.show()


def analyze_stop_loss_types():
    """Analyze different stop-loss types."""
    # Load sample data
    data = load_sample_data()

    # Different stop-loss types to test
    stop_types = {
        "Percentage": {"stop_type": "percentage", "stop_percentage": 0.02},  # 2% stop
        "Volatility": {"stop_type": "volatility", "atr_multiple": 2.0},  # 2 ATR stop
        "Trailing": {
            "stop_type": "trailing",
            "trailing_percentage": 0.015,
        },  # 1.5% trailing stop
        "Chandelier": {
            "stop_type": "chandelier",
            "atr_multiple": 3.0,
        },  # Chandelier exit
    }

    # Store results for comparison
    results = {}

    # Modified strategy with different stop types
    def strategy_with_stop_type(
        symbol, current_bar, market_data, portfolio, stop_config
    ):
        signals = ma_crossover_strategy_with_risk(
            symbol, current_bar, market_data, portfolio
        )

        # Modify entry signals with specified stop type
        if "entry" in signals:
            signals["entry"].update(stop_config)

        return signals

    # Run backtest with each stop type
    for name, stop_config in stop_types.items():
        print(f"\nRunning backtest with {name} stop-loss...")

        # Create strategy with this stop type
        strategy = lambda s, b, d, p: strategy_with_stop_type(s, b, d, p, stop_config)

        # Run backtest
        result = run_event_driven_backtest(
            strategy=strategy,
            data=data,
            initial_capital=10000.0,
        )

        # Store results
        results[name] = {
            "final_capital": result.final_capital,
            "return_pct": result.total_return_pct,
            "win_rate": result.win_rate,
            "drawdown": result.max_drawdown_pct,
            "sharpe": result.sharpe_ratio,
            "sortino": result.sortino_ratio,
            "avg_profit": result.avg_profit_per_trade,
            "avg_loss": result.avg_loss_per_trade,
            "trades": result.trades,
        }

    # Compare and visualize results
    print("\nStop-Loss Type Comparison Results:")
    for name, result in results.items():
        print(f"{name} Stop-Loss:")
        print(f"  Final Capital: ${result['final_capital']:.2f}")
        print(f"  Return: {result['return_pct']:.2f}%")
        print(f"  Win Rate: {result['win_rate'] * 100:.2f}%")
        print(f"  Max Drawdown: {result['drawdown']:.2f}%")
        print(f"  Avg Profit: ${result['avg_profit']:.2f}")
        print(f"  Avg Loss: ${result['avg_loss']:.2f}")
        print(f"  Profit Factor: {abs(result['avg_profit'] / result['avg_loss']):.2f}")

    # Plot trade P&L distribution
    plt.figure(figsize=(12, 8))
    for i, (name, result) in enumerate(results.items()):
        plt.subplot(2, 2, i + 1)
        trade_pnls = [t.pnl for t in result["trades"] if t.pnl is not None]
        if trade_pnls:
            plt.hist(trade_pnls, bins=20, alpha=0.7)
            plt.axvline(x=0, color="r", linestyle="--")
            plt.title(f"{name} Stop - P&L Distribution")
            plt.xlabel("Trade P&L ($)")
            plt.ylabel("Frequency")
            plt.grid(True)

    plt.tight_layout()
    plt.show()


def demonstrate_drawdown_control():
    """Demonstrate the impact of drawdown control."""
    # Load sample data
    data = create_multi_symbol_data()

    # Create a more volatile version of the data for stress testing
    volatile_data = {}
    for symbol, df in data.items():
        volatile_df = df.copy()
        volatile_df["high"] = volatile_df["high"] * 1.002  # Increase highs
        volatile_df["low"] = volatile_df["low"] * 0.998  # Decrease lows

        # Add some price shocks
        shock_idx = len(volatile_df) // 2  # Middle of dataset
        if symbol == "EURUSD":
            # Add a 5% drop
            volatile_df.loc[shock_idx:, ["open", "high", "low", "close"]] *= 0.95
        elif symbol == "GBPUSD":
            # Add a 7% drop a bit later
            volatile_df.loc[shock_idx + 100 :, ["open", "high", "low", "close"]] *= 0.93

        volatile_data[symbol] = volatile_df

    # Test with and without drawdown control
    test_cases = {
        "No Drawdown Control": {
            "drawdown_control": None,
        },
        "With Drawdown Control": {
            "drawdown_control": DrawdownControl(
                max_drawdown_pct=0.10,  # 10% max drawdown
                per_symbol_drawdown_pct=0.05,  # 5% per symbol
                cooling_off_days=10,
                reduction_factor=0.5,
            ),
        },
    }

    # Store results for comparison
    results = {}

    # Run tests
    for name, config in test_cases.items():
        print(f"\nRunning backtest {name}...")

        # Create risk manager
        risk_manager = RiskManager(
            position_sizer=VolatilityPositionSizer(risk_pct=0.02),
            stop_loss_manager=StopLossManager(),
            drawdown_control=config["drawdown_control"],
            max_positions=5,
            risk_per_trade_pct=0.02,
        )

        # Create portfolio with risk manager
        portfolio = Portfolio(initial_capital=10000.0)
        portfolio.risk_manager = risk_manager

        # Create execution handler
        execution_handler = ExecutionHandler()

        # Create engine and run backtest on volatile data
        engine = EventDrivenEngine(
            strategy=ma_crossover_strategy_with_risk,
            portfolio=portfolio,
            execution_handler=execution_handler,
        )

        engine.load_data(volatile_data)
        result = engine.run()

        # Store results
        results[name] = {
            "final_capital": result.final_capital,
            "return_pct": result.total_return_pct,
            "drawdown": result.max_drawdown_pct,
            "sharpe": result.sharpe_ratio,
            "equity_curve": result.equity_curve,
        }

    # Compare and visualize results
    print("\nDrawdown Control Comparison Results:")
    for name, result in results.items():
        print(f"{name}:")
        print(f"  Final Capital: ${result['final_capital']:.2f}")
        print(f"  Return: {result['return_pct']:.2f}%")
        print(f"  Max Drawdown: {result['drawdown']:.2f}%")
        print(f"  Sharpe Ratio: {result['sharpe']:.2f}")

    # Plot equity curves
    plt.figure(figsize=(12, 6))
    for name, result in results.items():
        equity_df = result["equity_curve"]
        plt.plot(equity_df["timestamp"], equity_df["equity"], label=name)

    plt.title("Equity Curves With and Without Drawdown Control")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.legend()
    plt.grid(True)

    # Plot drawdowns
    plt.figure(figsize=(12, 6))
    for name, result in results.items():
        equity_df = result["equity_curve"]
        equity_series = equity_df["equity"]
        peak = equity_series.cummax()
        drawdown = (equity_series - peak) / peak * 100
        plt.plot(equity_df["timestamp"], drawdown, label=name)

    plt.title("Drawdown Comparison")
    plt.xlabel("Date")
    plt.ylabel("Drawdown (%)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def portfolio_risk_metrics_demo():
    """Demonstrate portfolio risk metrics calculation."""
    # Load multi-symbol data
    data = create_multi_symbol_data()

    # Create risk manager with various components
    risk_manager = RiskManager(
        position_sizer=VolatilityPositionSizer(risk_pct=0.01),
        stop_loss_manager=StopLossManager(),
        drawdown_control=DrawdownControl(),
        max_positions=10,
        max_correlated_positions=2,
        correlation_threshold=0.7,
        risk_per_trade_pct=0.01,
    )

    # Create portfolio with risk manager
    portfolio = Portfolio(initial_capital=10000.0)
    portfolio.risk_manager = risk_manager

    # Create execution handler
    execution_handler = ExecutionHandler()

    # Create risk metrics calculator
    risk_metrics = PortfolioRiskMetrics(
        lookback_days=90,
        benchmark_symbol="EURUSD",  # Use EURUSD as benchmark
        risk_free_rate=0.02 / 252,  # 2% annual risk-free rate
        calculation_frequency="daily",
    )

    # Create engine and run backtest
    engine = EventDrivenEngine(
        strategy=ma_crossover_strategy_with_risk,
        portfolio=portfolio,
        execution_handler=execution_handler,
    )

    # Load data and run backtest
    engine.load_data(data)
    result = engine.run()

    # Calculate risk metrics at the end
    final_metrics = risk_metrics.calculate_metrics(portfolio, datetime.now())

    # Print basic performance metrics
    print("\nBacktest Results:")
    print(f"Final Equity: ${result.final_capital:.2f}")
    print(f"Total Return: {result.total_return_pct:.2f}%")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {result.max_drawdown_pct:.2f}%")

    # Print detailed risk metrics
    print("\nDetailed Risk Metrics:")
    print(f"Value at Risk (95%): {final_metrics.get('var_95', 0) * 100:.2f}%")
    print(f"Conditional VaR (95%): {final_metrics.get('cvar_95', 0) * 100:.2f}%")

    if "beta" in final_metrics:
        print(f"Beta vs EURUSD: {final_metrics['beta']:.2f}")
        print(
            f"Alpha vs EURUSD: {final_metrics['alpha'] * 252 * 100:.2f}%"
        )  # Annualized

    if "leverage" in final_metrics:
        print(f"Leverage: {final_metrics['leverage']:.2f}x")
        print(f"Net Exposure: {final_metrics['net_exposure'] * 100:.2f}%")
        print(f"Portfolio Concentration: {final_metrics['concentration']:.2f}")

    # Plot risk metrics
    plt.figure(figsize=(12, 8))

    # Get equity curve
    equity_df = result.equity_curve

    # Plot equity curve
    plt.subplot(2, 2, 1)
    plt.plot(equity_df["timestamp"], equity_df["equity"])
    plt.title("Equity Curve")
    plt.grid(True)

    # Plot drawdown
    plt.subplot(2, 2, 2)
    equity_series = equity_df["equity"]
    peak = equity_series.cummax()
    drawdown = (equity_series - peak) / peak * 100
    plt.plot(equity_df["timestamp"], drawdown)
    plt.title("Drawdown (%)")
    plt.grid(True)

    # Plot return distribution
    plt.subplot(2, 2, 3)
    returns = equity_series.pct_change().dropna()
    plt.hist(returns * 100, bins=50, alpha=0.75)
    plt.axvline(x=0, color="r", linestyle="--")
    plt.title("Return Distribution (%)")
    plt.grid(True)

    # Plot underwater equity curve (how far below peak)
    plt.subplot(2, 2, 4)
    underwater = peak - equity_series
    plt.plot(equity_df["timestamp"], underwater)
    plt.title("Underwater Equity Curve")
    plt.grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    print("=== FXML4 Risk Management Examples ===")

    # Run position sizer comparison
    print("\n1. Comparing Different Position Sizing Methods...")
    compare_position_sizers()

    # Run stop-loss type analysis
    print("\n2. Analyzing Stop-Loss Types...")
    analyze_stop_loss_types()

    # Run drawdown control demonstration
    print("\n3. Demonstrating Drawdown Control...")
    demonstrate_drawdown_control()

    # Run portfolio risk metrics demo
    print("\n4. Portfolio Risk Metrics Calculation...")
    portfolio_risk_metrics_demo()
