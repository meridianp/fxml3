#!/usr/bin/env python3
"""
Example of market regime analysis and regime-adaptive trading.

This script demonstrates how to:
1. Load market data and economic indicators
2. Detect market regimes using clustering
3. Analyze market regime characteristics
4. Create a regime-adaptive trading strategy
5. Compare performance against a non-adaptive strategy
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add the parent directory to the path to allow importing fxml4
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from dotenv import load_dotenv

from fxml4.data_engineering.timescaledb import TimescaleDBClient
from fxml4.ml.features import create_ml_features
from fxml4.ml.market_regimes import (
    MarketRegimeClassifier,
    classify_market_regimes,
    get_regime_descriptions,
)

# Load environment variables
load_dotenv()


# Connect to TimescaleDB
def get_db_client() -> TimescaleDBClient:
    """Get a TimescaleDB client."""
    host = os.environ.get("TIMESCALEDB_HOST", "localhost")
    port = int(os.environ.get("TIMESCALEDB_PORT", "5432"))
    dbname = os.environ.get("TIMESCALEDB_DATABASE", "fxml4")
    user = os.environ.get("TIMESCALEDB_USER", "postgres")
    password = os.environ.get("TIMESCALEDB_PASSWORD", "postgres")

    return TimescaleDBClient(
        host=host, port=port, dbname=dbname, user=user, password=password
    )


def load_market_data(
    symbol: str, timeframe: str, start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    """
    Load market data from TimescaleDB.

    Args:
        symbol: Symbol to load data for
        timeframe: Timeframe to load (e.g., "1h", "4h", "1d")
        start_date: Start date for data
        end_date: End date for data

    Returns:
        DataFrame with market data
    """
    db_client = get_db_client()
    return db_client.get_ohlcv_data(
        symbol=symbol, timeframe=timeframe, start_time=start_date, end_time=end_date
    )


def load_economic_data(
    indicators: List[str],
    start_date: datetime,
    end_date: datetime,
    source: str = "fred",
) -> pd.DataFrame:
    """
    Load economic data from TimescaleDB.

    Args:
        indicators: List of indicator names to load
        start_date: Start date for data
        end_date: End date for data
        source: Data source (default: "fred")

    Returns:
        DataFrame with economic data (indicator values in columns)
    """
    db_client = get_db_client()

    # Connect to database
    with db_client.get_connection() as conn:
        cursor = conn.cursor()

        # Check if exogenous_data table exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'exogenous_data'
            );
        """
        )

        if not cursor.fetchone()[0]:
            raise ValueError("exogenous_data table does not exist in TimescaleDB")

        # Fetch data for all indicators
        placeholders = ", ".join(["%s"] * len(indicators))
        query = f"""
            SELECT time, indicator_name, value
            FROM exogenous_data
            WHERE source = %s
              AND indicator_name IN ({placeholders})
              AND time BETWEEN %s AND %s
            ORDER BY time, indicator_name;
        """

        cursor.execute(query, [source] + indicators + [start_date, end_date])
        data = cursor.fetchall()

        if not data:
            print(f"No economic data found for indicators {indicators}")
            return pd.DataFrame()

        # Process the data into a wide format DataFrame
        records = []
        for time, indicator, value in data:
            records.append({"time": time, "indicator": indicator, "value": value})

        # Create DataFrame
        df = pd.DataFrame(records)

        # Pivot to have indicators as columns
        pivoted = df.pivot(index="time", columns="indicator", values="value")

        # Make sure all requested indicators are included
        for indicator in indicators:
            if indicator not in pivoted.columns:
                pivoted[indicator] = np.nan

        return pivoted


def create_signals_by_regime(
    data: pd.DataFrame, regimes: pd.Series, regime_configs: Dict[int, Dict[str, Any]]
) -> pd.Series:
    """
    Create trading signals using regime-specific parameters.

    Args:
        data: Market data with price and technical indicators
        regimes: Series with regime classifications
        regime_configs: Dictionary with regime-specific parameters

    Returns:
        Series with trading signals (-1, 0, 1)
    """
    # Initialize signals
    signals = pd.Series(0, index=data.index)

    # Process each regime separately
    for regime_id, config in regime_configs.items():
        # Create mask for this regime
        regime_mask = regimes == regime_id

        if not regime_mask.any():
            continue

        # Get regime-specific strategy parameters
        lookback = config.get("lookback", 20)
        rsi_high = config.get("rsi_high", 70)
        rsi_low = config.get("rsi_low", 30)
        use_rsi = config.get("use_rsi", True)
        use_sma = config.get("use_sma", True)
        use_volume = config.get("use_volume", False)
        sma_fast = config.get("sma_fast", 10)
        sma_slow = config.get("sma_slow", 50)

        # Create signals based on configuration
        regime_signals = pd.Series(0, index=data.index)

        # RSI signals (if enabled)
        if use_rsi and "rsi_14" in data.columns:
            # Oversold conditions (buy)
            regime_signals[data["rsi_14"] < rsi_low] = 1
            # Overbought conditions (sell)
            regime_signals[data["rsi_14"] > rsi_high] = -1

        # Moving average signals (if enabled)
        if (
            use_sma
            and f"sma_{sma_fast}" in data.columns
            and f"sma_{sma_slow}" in data.columns
        ):
            # Golden cross (buy)
            golden_cross = (data[f"sma_{sma_fast}"] > data[f"sma_{sma_slow}"]) & (
                data[f"sma_{sma_fast}"].shift(1) <= data[f"sma_{sma_slow}"].shift(1)
            )
            regime_signals[golden_cross] = 1

            # Death cross (sell)
            death_cross = (data[f"sma_{sma_fast}"] < data[f"sma_{sma_slow}"]) & (
                data[f"sma_{sma_fast}"].shift(1) >= data[f"sma_{sma_slow}"].shift(1)
            )
            regime_signals[death_cross] = -1

        # Volume confirmation (if enabled)
        if use_volume and "volume_ratio_10" in data.columns:
            # Only confirm signals on high volume
            high_volume = data["volume_ratio_10"] > 1.2
            regime_signals[~high_volume] = 0

        # Apply signals only for this regime
        signals[regime_mask] = regime_signals[regime_mask]

    return signals


def create_standard_signals(data: pd.DataFrame) -> pd.Series:
    """
    Create trading signals using standard parameters (no regime adaptation).

    Args:
        data: Market data with price and technical indicators

    Returns:
        Series with trading signals (-1, 0, 1)
    """
    # Initialize signals
    signals = pd.Series(0, index=data.index)

    # RSI signals
    if "rsi_14" in data.columns:
        # Oversold conditions (buy)
        signals[data["rsi_14"] < 30] = 1
        # Overbought conditions (sell)
        signals[data["rsi_14"] > 70] = -1

    # Moving average signals
    if "sma_20" in data.columns and "sma_50" in data.columns:
        # Golden cross (buy)
        golden_cross = (data["sma_20"] > data["sma_50"]) & (
            data["sma_20"].shift(1) <= data["sma_50"].shift(1)
        )
        signals[golden_cross] = 1

        # Death cross (sell)
        death_cross = (data["sma_20"] < data["sma_50"]) & (
            data["sma_20"].shift(1) >= data["sma_50"].shift(1)
        )
        signals[death_cross] = -1

    return signals


def backtest_strategy(
    market_data: pd.DataFrame,
    signals: pd.Series,
    initial_capital: float = 10000.0,
    position_size: float = 0.1,  # 10% of capital per trade
    stop_loss: float = 0.02,  # 2% stop loss
    take_profit: float = 0.04,  # 4% take profit
    max_positions: int = 5,  # Maximum number of simultaneous positions
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Backtest a trading strategy.

    Args:
        market_data: DataFrame with market data (OHLCV)
        signals: Series with trading signals (-1, 0, 1)
        initial_capital: Initial capital amount
        position_size: Fraction of capital per trade
        stop_loss: Stop loss percentage
        take_profit: Take profit percentage
        max_positions: Maximum number of simultaneous positions

    Returns:
        Tuple of (equity curve DataFrame, performance metrics dict)
    """
    # Initialize backtest variables
    capital = initial_capital
    equity = pd.Series(capital, index=market_data.index)
    positions = []  # List to track open positions
    trades = []  # List to track completed trades

    # Iterate through each bar
    for i, (timestamp, bar) in enumerate(market_data.iterrows()):
        close_price = bar["close"]

        # Check for stop loss / take profit on open positions
        closed_positions = []
        for pos in positions:
            entry_price = pos["entry_price"]
            entry_size = pos["size"]
            direction = pos["direction"]

            # Calculate profit/loss
            if direction == 1:  # Long position
                pnl_pct = (close_price / entry_price) - 1
            else:  # Short position
                pnl_pct = 1 - (close_price / entry_price)

            # Check for stop loss / take profit
            if (pnl_pct <= -stop_loss) or (pnl_pct >= take_profit):
                # Close position
                pnl = entry_size * pnl_pct
                capital += entry_size + pnl

                # Record trade
                trades.append(
                    {
                        "entry_time": pos["entry_time"],
                        "exit_time": timestamp,
                        "direction": direction,
                        "entry_price": entry_price,
                        "exit_price": close_price,
                        "size": entry_size,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "exit_reason": (
                            "stop_loss" if pnl_pct <= -stop_loss else "take_profit"
                        ),
                    }
                )

                closed_positions.append(pos)

        # Remove closed positions
        for pos in closed_positions:
            positions.remove(pos)

        # Process new signal
        current_signal = signals.iloc[i] if i < len(signals) else 0

        if current_signal != 0:
            # Check if we have capacity for new positions
            if len(positions) < max_positions:
                # Calculate position size
                pos_size = capital * position_size

                if pos_size > 0:
                    # Open new position
                    positions.append(
                        {
                            "entry_time": timestamp,
                            "entry_price": close_price,
                            "direction": current_signal,
                            "size": pos_size,
                        }
                    )

                    # Deduct position size from capital
                    capital -= pos_size

        # Update equity
        positions_value = sum(
            pos["size"]
            * (1 + (bar["close"] / pos["entry_price"] - 1) * pos["direction"])
            for pos in positions
        )
        equity.iloc[i] = capital + positions_value

    # Close any remaining positions at the end
    final_bar = market_data.iloc[-1]
    for pos in positions:
        entry_price = pos["entry_price"]
        entry_size = pos["size"]
        direction = pos["direction"]

        # Calculate profit/loss
        if direction == 1:  # Long position
            pnl_pct = (final_bar["close"] / entry_price) - 1
        else:  # Short position
            pnl_pct = 1 - (final_bar["close"] / entry_price)

        pnl = entry_size * pnl_pct

        # Record trade
        trades.append(
            {
                "entry_time": pos["entry_time"],
                "exit_time": market_data.index[-1],
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": final_bar["close"],
                "size": entry_size,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "exit_reason": "end_of_test",
            }
        )

    # Create DataFrame from trades
    if trades:
        trades_df = pd.DataFrame(trades)
    else:
        trades_df = pd.DataFrame(
            columns=[
                "entry_time",
                "exit_time",
                "direction",
                "entry_price",
                "exit_price",
                "size",
                "pnl",
                "pnl_pct",
                "exit_reason",
            ]
        )

    # Calculate performance metrics
    total_return = (equity.iloc[-1] / initial_capital) - 1.0

    # Annualized return (252 trading days per year)
    days = (market_data.index[-1] - market_data.index[0]).days
    trading_years = days / 365.0
    annualized_return = (1 + total_return) ** (1 / trading_years) - 1.0

    # Calculate drawdowns
    rolling_max = equity.cummax()
    drawdowns = (equity / rolling_max) - 1.0
    max_drawdown = drawdowns.min()

    # Calculate Sharpe ratio (assuming 0% risk-free rate)
    equity_returns = equity.pct_change().dropna()
    sharpe_ratio = (
        np.sqrt(252) * equity_returns.mean() / equity_returns.std()
        if len(equity_returns) > 1
        else 0
    )

    # Calculate win rate
    if len(trades_df) > 0:
        win_rate = (trades_df["pnl"] > 0).mean()
        avg_win = (
            trades_df.loc[trades_df["pnl"] > 0, "pnl_pct"].mean()
            if any(trades_df["pnl"] > 0)
            else 0
        )
        avg_loss = (
            trades_df.loc[trades_df["pnl"] < 0, "pnl_pct"].mean()
            if any(trades_df["pnl"] < 0)
            else 0
        )
    else:
        win_rate = 0
        avg_win = 0
        avg_loss = 0

    # Create equity curve DataFrame
    equity_curve = pd.DataFrame(
        {
            "equity": equity,
            "drawdown": drawdowns,
            "returns": equity_returns.reindex(equity.index),
        }
    )

    # Compile performance metrics
    metrics = {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "total_trades": len(trades_df),
        "net_profit": equity.iloc[-1] - initial_capital,
        "profit_factor": (
            abs(
                trades_df.loc[trades_df["pnl"] > 0, "pnl"].sum()
                / trades_df.loc[trades_df["pnl"] < 0, "pnl"].sum()
            )
            if any(trades_df["pnl"] < 0)
            else float("inf")
        ),
    }

    return equity_curve, metrics, trades_df


def main():
    # Load environment variables
    load_dotenv()

    # Define parameters
    symbol = "EURUSD"
    timeframe = "1d"
    start_date = datetime(2018, 1, 1)
    end_date = datetime(2023, 12, 31)
    n_regimes = 4  # Number of regimes to detect

    # Load market data
    print(
        f"Loading market data for {symbol} ({timeframe}) from {start_date.date()} to {end_date.date()}..."
    )
    market_data = load_market_data(symbol, timeframe, start_date, end_date)

    if market_data.empty:
        print(
            "No market data found. Please make sure market data is loaded in TimescaleDB."
        )
        return 1

    print(f"Loaded {len(market_data)} bars of market data.")

    # Load economic indicators
    indicators = [
        "UNRATE",  # Unemployment Rate
        "CPIAUCSL",  # Consumer Price Index
        "GDP",  # Gross Domestic Product
        "FEDFUNDS",  # Federal Funds Rate
        "T10Y2Y",  # 10Y-2Y Treasury Spread (yield curve)
        "VIXCLS",  # VIX Volatility Index
    ]

    print(f"Loading economic indicators: {', '.join(indicators)}...")
    economic_data = load_economic_data(indicators, start_date, end_date)

    if economic_data.empty:
        print(
            "No economic data found. Please run scripts/collect_economic_data.py to collect FRED data."
        )
        return 1

    print(f"Loaded economic data with shape: {economic_data.shape}")

    # Create features
    print("Creating features...")
    config = {
        "features": {
            "technical_indicators": True,
            "price_patterns": True,
            "volume_analysis": True,
            "session_features": False,
            "wave_features": False,
            "economic_features": True,
        }
    }
    features = create_ml_features(market_data, economic_data, config)

    # Detect market regimes
    print(f"Detecting {n_regimes} market regimes...")
    regimes = classify_market_regimes(features, economic_data, n_regimes=n_regimes)

    # Get regime descriptions
    print("Analyzing regime characteristics...")
    regime_descriptions = get_regime_descriptions(features, regimes, economic_data)

    # Print regime descriptions
    print("\nMarket Regime Characteristics:")
    print("-" * 80)
    for regime_id, desc in regime_descriptions.items():
        print(
            f"Regime {regime_id} ({desc['frequency']:.1%} of time): {desc['summary']}"
        )

    # Create regime-specific strategy parameters
    regime_configs = {}

    # Define strategy parameters for each regime
    for regime_id, desc in regime_descriptions.items():
        volatility = desc.get("volatility", "medium")
        trend = desc.get("trend", "sideways")
        momentum = desc.get("momentum", "neutral")

        # Default configuration
        config = {
            "lookback": 20,
            "rsi_high": 70,
            "rsi_low": 30,
            "use_rsi": True,
            "use_sma": True,
            "use_volume": False,
            "sma_fast": 10,
            "sma_slow": 50,
        }

        # Adjust parameters based on regime characteristics

        # Volatile regimes: tighten RSI bands, use shorter lookbacks
        if volatility == "high":
            config["rsi_high"] = 75
            config["rsi_low"] = 25
            config["lookback"] = 10
            config["use_volume"] = True  # Use volume confirmation in high volatility
        elif volatility == "low":
            config["rsi_high"] = 65
            config["rsi_low"] = 35
            config["lookback"] = 30

        # Trend regimes: emphasize moving averages
        if "bullish" in trend:
            config["use_sma"] = True
            config["sma_fast"] = 5 if "strong" in trend else 10
            config["use_rsi"] = (
                "strong" not in trend
            )  # In strong trends, RSI can stay overbought
        elif "bearish" in trend:
            config["use_sma"] = True
            config["sma_fast"] = 5 if "strong" in trend else 10
            config["use_rsi"] = (
                "strong" not in trend
            )  # In strong trends, RSI can stay oversold
        elif trend == "sideways":
            config["use_sma"] = (
                False  # Moving averages less effective in sideways markets
            )
            config["use_rsi"] = True  # RSI more effective in sideways markets

        # Save configuration for this regime
        regime_configs[regime_id] = config

    # Create signals for both strategies
    print("Creating trading signals...")

    # Standard strategy (no regime adaptation)
    standard_signals = create_standard_signals(features)

    # Regime-adaptive strategy
    adaptive_signals = create_signals_by_regime(features, regimes, regime_configs)

    # Backtest both strategies
    print("Backtesting strategies...")

    # Standard strategy
    standard_equity, standard_metrics, standard_trades = backtest_strategy(
        market_data, standard_signals, initial_capital=10000.0
    )

    # Regime-adaptive strategy
    adaptive_equity, adaptive_metrics, adaptive_trades = backtest_strategy(
        market_data, adaptive_signals, initial_capital=10000.0
    )

    # Print backtest results
    print("\nBacktest Results:")
    print("-" * 80)
    print(
        f"{'Metric':<20} {'Standard Strategy':<18} {'Adaptive Strategy':<18} {'Difference':<12}"
    )
    print("-" * 80)

    for metric in [
        "total_return",
        "annualized_return",
        "max_drawdown",
        "sharpe_ratio",
        "win_rate",
    ]:
        std_val = standard_metrics[metric]
        adp_val = adaptive_metrics[metric]
        diff = adp_val - std_val

        # Format as percentage for certain metrics
        if metric in ["total_return", "annualized_return", "max_drawdown", "win_rate"]:
            print(
                f"{metric:<20} {std_val*100:>15.2f}% {adp_val*100:>15.2f}% {diff*100:>+10.2f}%"
            )
        else:
            print(f"{metric:<20} {std_val:>15.2f} {adp_val:>15.2f} {diff:>+10.2f}")

    print(
        f"{'total_trades':<20} {standard_metrics['total_trades']:>15} {adaptive_metrics['total_trades']:>15} {adaptive_metrics['total_trades']-standard_metrics['total_trades']:>+10}"
    )

    # Plot results
    plt.style.use("ggplot")

    # Figure 1: Equity Curves
    plt.figure(figsize=(12, 14))

    # Plot 1: Price and regimes
    ax1 = plt.subplot(3, 1, 1)
    market_data["close"].plot(ax=ax1, label="Price", color="black", alpha=0.7)
    ax1.set_title(f"{symbol} Price and Market Regimes", fontsize=14)
    ax1.set_ylabel("Price", fontsize=12)

    # Add colored background for regimes
    colors = plt.cm.tab10(np.linspace(0, 1, n_regimes))

    for i in range(n_regimes):
        regime_mask = regimes == i
        if not regime_mask.any():
            continue

        # Find continuous segments of this regime
        regime_changes = regime_mask.astype(int).diff().fillna(0)
        segment_starts = market_data.index[regime_changes == 1].tolist()
        segment_ends = market_data.index[regime_changes == -1].tolist()

        # Handle first and last segments
        if regime_mask.iloc[0]:
            segment_starts.insert(0, market_data.index[0])
        if regime_mask.iloc[-1]:
            segment_ends.append(market_data.index[-1])

        # Plot each segment
        for start, end in zip(segment_starts, segment_ends):
            ax1.axvspan(
                start,
                end,
                alpha=0.3,
                color=colors[i],
                label=f"Regime {i}" if start == segment_starts[0] else "",
            )

    ax1.legend(loc="best")

    # Add regime descriptions as annotations
    y_pos = ax1.get_ylim()[1] * 1.05
    for i, (regime_id, desc) in enumerate(regime_descriptions.items()):
        if i < len(colors):
            plt.figtext(
                0.15 + i * 0.2,
                0.95,
                f"Regime {regime_id}: {desc['volatility']} vol, {desc['trend']} trend",
                color=colors[regime_id],
                fontsize=9,
                verticalalignment="top",
            )

    # Plot 2: Equity curves
    ax2 = plt.subplot(3, 1, 2)
    standard_equity["equity"].plot(
        ax=ax2, label="Standard Strategy", color="blue", alpha=0.8
    )
    adaptive_equity["equity"].plot(
        ax=ax2, label="Regime-Adaptive Strategy", color="green", alpha=0.8
    )
    ax2.set_title("Strategy Equity Curves", fontsize=14)
    ax2.set_ylabel("Equity ($)", fontsize=12)
    ax2.legend(loc="best")

    # Plot 3: Drawdowns
    ax3 = plt.subplot(3, 1, 3)
    standard_equity["drawdown"].plot(
        ax=ax3, label="Standard Strategy", color="blue", alpha=0.8
    )
    adaptive_equity["drawdown"].plot(
        ax=ax3, label="Regime-Adaptive Strategy", color="green", alpha=0.8
    )
    ax3.set_title("Strategy Drawdowns", fontsize=14)
    ax3.set_ylabel("Drawdown (%)", fontsize=12)
    ax3.set_ylim(
        bottom=min(standard_equity["drawdown"].min(), adaptive_equity["drawdown"].min())
        * 1.1,
        top=0.01,
    )
    ax3.legend(loc="best")

    # Format dates on x-axis
    for ax in [ax1, ax2, ax3]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        plt.setp(ax.get_xticklabels(), rotation=45)

    plt.tight_layout(h_pad=0.5)
    plt.savefig("market_regime_analysis.png", dpi=300, bbox_inches="tight")
    print("\nSaved market regime analysis chart to market_regime_analysis.png")

    # Figure 2: Trade Analysis
    plt.figure(figsize=(12, 10))

    # Plot 1: Trade P&L by Regime (Adaptive Strategy)
    ax1 = plt.subplot(2, 1, 1)

    # Add regime information to trades
    if not adaptive_trades.empty:
        adaptive_trades["regime"] = adaptive_trades["entry_time"].map(regimes)

        # Plot P&L by regime
        for i in range(n_regimes):
            regime_trades = adaptive_trades[adaptive_trades["regime"] == i]
            if not regime_trades.empty:
                ax1.scatter(
                    regime_trades["entry_time"],
                    regime_trades["pnl_pct"] * 100,
                    label=f"Regime {i}",
                    color=colors[i],
                    alpha=0.7,
                    s=50,
                )

    ax1.axhline(y=0, color="gray", linestyle="-", alpha=0.4)
    ax1.set_title("Trade P&L by Market Regime (Adaptive Strategy)", fontsize=14)
    ax1.set_ylabel("Trade P&L (%)", fontsize=12)
    ax1.legend(loc="best")

    # Plot 2: Trade P&L Distribution by Regime
    ax2 = plt.subplot(2, 1, 2)

    if not adaptive_trades.empty and "regime" in adaptive_trades.columns:
        # Create data for boxplots
        data = []
        labels = []

        for i in range(n_regimes):
            regime_trades = adaptive_trades[adaptive_trades["regime"] == i]
            if not regime_trades.empty:
                data.append(regime_trades["pnl_pct"] * 100)
                labels.append(f"Regime {i}")

        if data:
            ax2.boxplot(
                data,
                labels=labels,
                patch_artist=True,
                boxprops=dict(facecolor="lightblue", color="blue", alpha=0.7),
                medianprops=dict(color="red"),
            )

    ax2.axhline(y=0, color="gray", linestyle="-", alpha=0.4)
    ax2.set_title("Trade P&L Distribution by Market Regime", fontsize=14)
    ax2.set_ylabel("Trade P&L (%)", fontsize=12)

    # Format dates on x-axis
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    plt.setp(ax1.get_xticklabels(), rotation=45)

    plt.tight_layout()
    plt.savefig("trade_analysis_by_regime.png", dpi=300, bbox_inches="tight")
    print("Saved trade analysis chart to trade_analysis_by_regime.png")

    return 0


if __name__ == "__main__":
    sys.exit(main())
