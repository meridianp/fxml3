"""Example of using the news event filter in FXML4.

This script demonstrates how to use the news event filter for risk management
to avoid trading during major economic news events.
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

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
from fxml4.backtesting.execution import ExecutionHandler
from fxml4.backtesting.news_filter import IntegratedNewsFilter, NewsEventFilter
from fxml4.backtesting.risk_management import (
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
    """Load sample forex data with some major news events.

    Returns:
        DataFrame with sample data.
    """
    # Generate sample forex data (EURUSD)
    np.random.seed(42)

    # Create date range (use real dates for news event matching)
    start_date = datetime(2023, 3, 1)
    end_date = datetime(2023, 3, 31)
    dates = pd.date_range(start=start_date, end=end_date, freq="15min")

    # Generate random walk prices with trends and volatility clusters
    price = 1.1000  # Starting price
    prices = [price]
    volatilities = [0.0002]  # Starting volatility

    # Create trends and regimes
    trend_change_points = [int(len(dates) * x) for x in [0.25, 0.5, 0.75]]
    current_trend = 0.00005  # Initial trend

    for i in range(1, len(dates)):
        # Change trend at specified points
        if i in trend_change_points:
            current_trend = np.random.choice([-0.00005, 0, 0.00005])

        # Update volatility (volatility clustering)
        target_vol = np.random.choice([0.0001, 0.0002, 0.0004], p=[0.3, 0.5, 0.2])
        volatilities.append(volatilities[-1] * 0.9 + target_vol * 0.1)

        # Random price change with trend and time-varying volatility
        change = np.random.normal(0, volatilities[-1]) + current_trend

        # Add some mean reversion
        mean_reversion = (1.1000 - price) * 0.001
        price = price + change + mean_reversion
        prices.append(price)

    # Create OHLC data
    data = pd.DataFrame(
        {
            "time": dates,
            "open": prices,
            "close": prices,  # Will adjust below
            "volume": np.random.lognormal(mean=10, sigma=1, size=len(dates)),
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
                1 + np.random.normal(0.00005, volatility)
            )
            data.loc[i, "high"] = max(data.loc[i, "open"], data.loc[i, "close"]) * (
                1 + abs(np.random.normal(0, volatility))
            )
            data.loc[i, "low"] = min(data.loc[i, "open"], data.loc[i, "close"]) * (
                1 - abs(np.random.normal(0, volatility))
            )
        else:  # Bearish
            data.loc[i, "close"] = open_price * (
                1 - np.random.normal(0.00005, volatility)
            )
            data.loc[i, "high"] = max(data.loc[i, "open"], data.loc[i, "close"]) * (
                1 + abs(np.random.normal(0, volatility))
            )
            data.loc[i, "low"] = min(data.loc[i, "open"], data.loc[i, "close"]) * (
                1 - abs(np.random.normal(0, volatility))
            )

    # Add simulated news events (normally we'd get these from ForexFactory/FRED)
    # These are just for demo purposes - in real usage, the news filter will fetch actual events
    news_events = [
        # NFP day (first Friday of the month)
        {
            "datetime": datetime(2023, 3, 3, 8, 30),
            "currency": "USD",
            "impact": "high",
            "title": "Non-Farm Payrolls",
        },
        # ECB meeting day (second Thursday of the month)
        {
            "datetime": datetime(2023, 3, 9, 7, 45),
            "currency": "EUR",
            "impact": "high",
            "title": "ECB Interest Rate Decision",
        },
        # FOMC meeting day (third Wednesday of the month)
        {
            "datetime": datetime(2023, 3, 15, 14, 0),
            "currency": "USD",
            "impact": "high",
            "title": "FOMC Interest Rate Decision",
        },
        # Add a few more medium/low impact events
        {
            "datetime": datetime(2023, 3, 7, 10, 0),
            "currency": "EUR",
            "impact": "medium",
            "title": "GDP q/q",
        },
        {
            "datetime": datetime(2023, 3, 14, 8, 30),
            "currency": "USD",
            "impact": "medium",
            "title": "CPI m/m",
        },
        {
            "datetime": datetime(2023, 3, 21, 5, 0),
            "currency": "EUR",
            "impact": "low",
            "title": "German ZEW Economic Sentiment",
        },
    ]

    return data, news_events


def create_example_news_filter(news_events: List[Dict]) -> NewsEventFilter:
    """Create a news event filter with example events.

    Args:
        news_events: List of example news events.

    Returns:
        Configured NewsEventFilter.
    """
    # Create news filter with default settings
    news_filter = NewsEventFilter(
        high_impact_only=True,
        event_buffer_before=60,  # minutes before event
        event_buffer_after=30,  # minutes after event
        currency_specific=True,
        cache_duration=24,  # hours
    )

    # Manually add events to filter (normally these would be fetched from ForexFactory/FRED)
    # Group events by date
    for event in news_events:
        event_date = event["datetime"].replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if event_date not in news_filter.events_by_date:
            news_filter.events_by_date[event_date] = []
        news_filter.events_by_date[event_date].append(event)

    news_filter.last_cache_update = datetime.now()

    return news_filter


# Simple example strategy
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
    if market_data is None or len(market_data) < 30:
        return signals

    # Calculate moving averages
    short_window = 10
    long_window = 30

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
                    "risk_pct": 0.01,  # Risk 1% of portfolio per trade
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
                        "risk_pct": 0.01,  # Risk 1% of portfolio per trade
                    }

    return signals


def compare_with_without_news_filter():
    """Compare backtest results with and without news event filtering."""
    # Load sample data
    data, news_events = load_sample_data()

    # Create news filter
    news_filter = create_example_news_filter(news_events)

    # Test cases
    test_cases = {
        "Without News Filter": {
            "avoid_news": False,
        },
        "With News Filter": {
            "avoid_news": True,
        },
    }

    # Store results for comparison
    results = {}

    # Run tests
    for name, config in test_cases.items():
        print(f"\nRunning backtest {name}...")

        # Create risk manager
        risk_manager = RiskManager(
            position_sizer=VolatilityPositionSizer(risk_pct=0.01),
            stop_loss_manager=StopLossManager(),
            news_filter=news_filter,
            avoid_high_impact_news=config["avoid_news"],
        )

        # Create portfolio with risk manager
        portfolio = Portfolio(initial_capital=10000.0)
        portfolio.risk_manager = risk_manager

        # Create execution handler
        execution_handler = ExecutionHandler()

        # Create engine and run backtest
        engine = EventDrivenEngine(
            strategy=ma_crossover_strategy,
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
    print("\nBacktest Comparison Results:")
    for name, result in results.items():
        print(f"{name}:")
        print(f"  Final Capital: ${result['final_capital']:.2f}")
        print(f"  Return: {result['return_pct']:.2f}%")
        print(f"  Win Rate: {result['win_rate'] * 100:.2f}%")
        print(f"  Max Drawdown: {result['drawdown']:.2f}%")
        print(f"  Sharpe Ratio: {result['sharpe']:.2f}")
        print(f"  Sortino Ratio: {result['sortino']:.2f}")
        print(f"  Number of Trades: {len(result['trades'])}")

    # Plot equity curves
    plt.figure(figsize=(12, 6))
    for name, result in results.items():
        equity_df = result["equity_curve"]
        plt.plot(equity_df["timestamp"], equity_df["equity"], label=name)

    # Mark news events on the chart
    ylim = plt.ylim()
    for event in news_events:
        if event["impact"] == "high":
            plt.axvline(x=event["datetime"], color="r", linestyle="--", alpha=0.5)
            plt.text(
                event["datetime"],
                ylim[1] * 0.95,
                event["title"],
                rotation=90,
                verticalalignment="top",
            )

    plt.title("Equity Curves With and Without News Filtering")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.legend()
    plt.grid(True)

    # Plot trades
    plt.figure(figsize=(12, 6))

    # Plot price data
    plt.plot(data["time"], data["close"], color="gray", alpha=0.5, label="EURUSD")

    # Plot trades for each test case
    markers = {"Without News Filter": "o", "With News Filter": "s"}
    colors = {"buy": "green", "sell": "red"}

    for name, result in results.items():
        for trade in result["trades"]:
            if trade.entry_time and trade.exit_time:
                # Plot entry
                plt.scatter(
                    trade.entry_time,
                    trade.entry_price,
                    marker=markers[name],
                    color=colors.get(trade.side, "blue"),
                    s=100,
                    alpha=0.7,
                    label=(
                        f"{name} {trade.side.capitalize()}"
                        if f"{name} {trade.side.capitalize()}"
                        not in plt.gca().get_legend_handles_labels()[1]
                        else ""
                    ),
                )

                # Plot exit
                plt.scatter(
                    trade.exit_time,
                    trade.exit_price,
                    marker="x",
                    color=colors.get(trade.side, "blue"),
                    s=100,
                    alpha=0.7,
                )

                # Connect entry and exit
                plt.plot(
                    [trade.entry_time, trade.exit_time],
                    [trade.entry_price, trade.exit_price],
                    color=colors.get(trade.side, "blue"),
                    alpha=0.3,
                )

    # Mark news events on the chart
    for event in news_events:
        if event["impact"] == "high":
            plt.axvline(x=event["datetime"], color="r", linestyle="--", alpha=0.5)
            plt.text(
                event["datetime"],
                plt.ylim()[1] * 0.98,
                event["title"],
                rotation=90,
                verticalalignment="top",
            )

    plt.title("Trades With and Without News Filtering")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def visualize_upcoming_events():
    """Visualize upcoming news events."""
    print("\nVisualizing upcoming news events...")

    # Create news filter
    news_filter = IntegratedNewsFilter(
        high_impact_only=True,
        event_buffer_before=120,  # minutes before event
        event_buffer_after=60,  # minutes after event
        currency_specific=True,
    )

    # Try to update calendars (will fetch real data if API keys are set)
    try:
        news_filter.update_calendars()

        # Get upcoming events for a few currency pairs
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        days_ahead = 7

        for symbol in symbols:
            upcoming_events = news_filter.get_upcoming_events(
                days_ahead=days_ahead, symbol=symbol
            )

            print(f"\nUpcoming events for {symbol} (next {days_ahead} days):")
            if not upcoming_events:
                print("  No major events found.")
            else:
                for event in upcoming_events:
                    event_time = event["datetime"]
                    event_title = event["title"]
                    event_currency = event["currency"]
                    event_impact = event["impact"]

                    print(
                        f"  {event_time.strftime('%Y-%m-%d %H:%M')} - {event_currency} - {event_impact.upper()} - {event_title}"
                    )

    except Exception as e:
        print(f"Error fetching real news events: {e}")
        print(
            "This example works better with SCRAPER_API_KEY and FRED_API_KEY set in the environment."
        )


if __name__ == "__main__":
    print("=== FXML4 News Event Filter Example ===")

    # Run comparison backtest
    print("\n1. Comparing Backtest Results With and Without News Filtering...")
    compare_with_without_news_filter()

    # Visualize upcoming real events (if API keys are available)
    print("\n2. Checking Upcoming Events from Real Sources...")
    visualize_upcoming_events()
