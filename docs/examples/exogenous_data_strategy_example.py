#!/usr/bin/env python3
"""
Example of using exogenous economic data in a trading strategy.

This script demonstrates how to:
1. Load market data and economic indicators from TimescaleDB
2. Create features from economic data
3. Use economic regime detection to adjust a trading strategy
4. Backtest the strategy with and without economic data
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add the parent directory to the path to allow importing fxml4
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from dotenv import load_dotenv

from fxml4.data_engineering.timescaledb import TimescaleDBClient

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


def create_economic_features(economic_data: pd.DataFrame) -> pd.DataFrame:
    """
    Create features from economic data.

    Args:
        economic_data: DataFrame with economic data

    Returns:
        DataFrame with derived features
    """
    features = economic_data.copy()

    # Get list of indicators
    indicators = economic_data.columns.tolist()

    # Calculate rate of change for each indicator
    for indicator in indicators:
        # Skip if all NaN
        if features[indicator].isna().all():
            continue

        # Determine appropriate period for rate of change based on data frequency
        non_na_values = features[indicator].dropna()
        if len(non_na_values) < 2:
            continue

        # Determine frequency by looking at typical time between observations
        dates = non_na_values.index
        if len(dates) >= 2:
            median_days = np.median(
                [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
            )

            if median_days <= 1:  # Daily data
                # Month-over-month change (about 21 trading days)
                features[f"{indicator}_1m_change"] = features[indicator].pct_change(21)
                # Year-over-year change
                features[f"{indicator}_1y_change"] = features[indicator].pct_change(252)
            elif median_days <= 7:  # Weekly data
                # 4-week change
                features[f"{indicator}_4w_change"] = features[indicator].pct_change(4)
                # 52-week change
                features[f"{indicator}_52w_change"] = features[indicator].pct_change(52)
            elif median_days <= 31:  # Monthly data
                # 3-month change
                features[f"{indicator}_3m_change"] = features[indicator].pct_change(3)
                # 12-month change
                features[f"{indicator}_12m_change"] = features[indicator].pct_change(12)
            else:  # Quarterly or less frequent
                # 1-quarter change
                features[f"{indicator}_1q_change"] = features[indicator].pct_change(1)
                # 4-quarter change
                features[f"{indicator}_4q_change"] = features[indicator].pct_change(4)

    # Calculate z-scores (standardized values)
    for indicator in indicators:
        if features[indicator].isna().all():
            continue

        # Calculate rolling mean and std
        rolling_window = 12  # Use past 12 observations
        features[f"{indicator}_mean"] = (
            features[indicator].rolling(window=rolling_window).mean()
        )
        features[f"{indicator}_std"] = (
            features[indicator].rolling(window=rolling_window).std()
        )

        # Calculate z-score
        features[f"{indicator}_zscore"] = (
            features[indicator] - features[f"{indicator}_mean"]
        ) / features[f"{indicator}_std"]

    return features


def detect_economic_regime(
    features: pd.DataFrame, indicators_config: Dict[str, Dict[str, Any]]
) -> pd.Series:
    """
    Detect economic regime based on multiple indicators.

    Args:
        features: DataFrame with economic features
        indicators_config: Configuration for threshold values

    Returns:
        Series with economic regime classifications
    """
    regimes = pd.Series(index=features.index, dtype="object")

    # Fill with default regime
    regimes.iloc[:] = "normal"

    # Check for recession indicators
    # 1. Yield curve inversion (if available)
    if "T10Y2Y" in features.columns:
        # Yield curve inversion when 10Y-2Y spread is negative
        regimes = regimes.mask(features["T10Y2Y"] < -0.1, "recession_risk")

    # 2. High unemployment + negative GDP growth (if both available)
    if "UNRATE" in features.columns and "GDP_4q_change" in features.columns:
        # High unemployment and negative GDP growth
        recession_mask = (
            features["UNRATE"]
            > indicators_config.get("UNRATE", {}).get("high_threshold", 6.0)
        ) & (
            features["GDP_4q_change"] < -0.01
        )  # GDP declining
        regimes = regimes.mask(recession_mask, "recession")

    # Check for inflation regime
    if "CPIAUCSL_12m_change" in features.columns:
        # High inflation
        inflation_threshold = indicators_config.get("CPIAUCSL", {}).get(
            "high_threshold", 0.04
        )  # 4%
        high_inflation_mask = features["CPIAUCSL_12m_change"] > inflation_threshold

        # Modify existing regimes
        # If we're in recession risk or recession and have high inflation, it's stagflation
        stagflation_mask = high_inflation_mask & (
            (regimes == "recession_risk") | (regimes == "recession")
        )
        regimes = regimes.mask(stagflation_mask, "stagflation")

        # Otherwise, if we just have high inflation, it's an inflationary regime
        inflation_mask = high_inflation_mask & (regimes == "normal")
        regimes = regimes.mask(inflation_mask, "inflation")

    # Check for growth regime
    if "GDP_4q_change" in features.columns:
        # Strong growth
        growth_threshold = indicators_config.get("GDP", {}).get(
            "high_threshold", 0.03
        )  # 3%
        strong_growth_mask = (features["GDP_4q_change"] > growth_threshold) & (
            regimes == "normal"
        )  # Only if not already in another regime
        regimes = regimes.mask(strong_growth_mask, "growth")

    # Fill any remaining NaN values
    regimes = regimes.fillna("unknown")

    return regimes


def adjust_strategy_for_economic_regime(
    base_signal: pd.Series,
    economic_regime: pd.Series,
    adjustment_factors: Dict[str, float],
) -> pd.Series:
    """
    Adjust trading signals based on economic regime.

    Args:
        base_signal: Series with base trading signals (-1.0 to 1.0)
        economic_regime: Series with economic regime classifications
        adjustment_factors: Factors to adjust signal by for each regime

    Returns:
        Series with adjusted trading signals
    """
    adjusted_signal = base_signal.copy()

    # Apply adjustment factors for each regime
    for regime, factor in adjustment_factors.items():
        regime_mask = economic_regime == regime
        if regime_mask.any():
            # Adjust signal by factor in the regime
            adjusted_signal.loc[regime_mask] *= factor

    # Cap signal between -1.0 and 1.0
    adjusted_signal = adjusted_signal.clip(-1.0, 1.0)

    return adjusted_signal


def backtest_strategy(
    market_data: pd.DataFrame, signal: pd.Series, initial_capital: float = 10000.0
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Backtest a trading strategy.

    Args:
        market_data: DataFrame with market data (OHLCV)
        signal: Series with trading signals (-1.0 to 1.0)
        initial_capital: Initial capital amount

    Returns:
        Tuple of (equity curve DataFrame, performance metrics dict)
    """
    # Align signal with market data
    aligned_signal = signal.reindex(market_data.index).fillna(0)

    # Calculate returns
    market_data["returns"] = market_data["close"].pct_change()

    # Calculate strategy returns (signal * next bar return)
    strategy_returns = aligned_signal.shift(1) * market_data["returns"]

    # Calculate equity curve
    equity = (1 + strategy_returns).cumprod() * initial_capital

    # Calculate performance metrics
    total_return = (equity.iloc[-1] / initial_capital) - 1.0
    annualized_return = (1 + total_return) ** (252 / len(equity)) - 1.0

    # Calculate drawdowns
    rolling_max = equity.cummax()
    drawdowns = (equity / rolling_max) - 1.0
    max_drawdown = drawdowns.min()

    # Calculate Sharpe ratio (assuming 0% risk-free rate)
    daily_returns = strategy_returns[strategy_returns.index >= aligned_signal.index[0]]
    sharpe_ratio = np.sqrt(252) * daily_returns.mean() / daily_returns.std()

    # Calculate win rate
    wins = (daily_returns > 0).sum()
    total_trades = (daily_returns != 0).sum()
    win_rate = wins / total_trades if total_trades > 0 else 0.0

    # Create equity curve DataFrame
    equity_curve = pd.DataFrame(
        {"equity": equity, "returns": strategy_returns, "drawdown": drawdowns}
    )

    # Compile performance metrics
    metrics = {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "win_rate": win_rate,
        "total_trades": total_trades,
    }

    return equity_curve, metrics


def main():
    # Load environment variables
    load_dotenv()

    # Define parameters
    symbol = "EURUSD"
    timeframe = "1d"
    start_date = datetime(2018, 1, 1)
    end_date = datetime(2023, 12, 31)

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

    # Create features from economic data
    print("Creating economic features...")
    economic_features = create_economic_features(economic_data)

    # Detect economic regimes
    print("Detecting economic regimes...")
    indicator_config = {
        "UNRATE": {"high_threshold": 6.0},  # 6% unemployment is high
        "CPIAUCSL": {"high_threshold": 0.04},  # 4% inflation is high
        "GDP": {"high_threshold": 0.03},  # 3% GDP growth is strong
    }

    economic_regime = detect_economic_regime(economic_features, indicator_config)
    regime_counts = economic_regime.value_counts()
    print("Economic regime distribution:")
    for regime, count in regime_counts.items():
        print(f"  {regime}: {count} days ({count/len(economic_regime)*100:.1f}%)")

    # Create a simple trend-following strategy
    print("Creating trend-following strategy...")

    # Calculate moving averages for trend
    market_data["sma20"] = market_data["close"].rolling(window=20).mean()
    market_data["sma50"] = market_data["close"].rolling(window=50).mean()

    # Generate base signal: 1 when fast MA > slow MA, -1 otherwise
    base_signal = pd.Series(0, index=market_data.index)
    base_signal[market_data["sma20"] > market_data["sma50"]] = 1.0
    base_signal[market_data["sma20"] < market_data["sma50"]] = -1.0

    # Adjust signal based on economic regime
    print("Adjusting strategy for economic regimes...")
    adjustment_factors = {
        "normal": 1.0,  # No adjustment
        "growth": 1.2,  # Increase exposure in growth regime
        "inflation": 0.7,  # Reduce exposure in inflationary regime
        "recession_risk": 0.5,  # Reduce exposure in recession risk regime
        "recession": 0.3,  # Significantly reduce exposure in recession
        "stagflation": 0.2,  # Minimal exposure in stagflation
        "unknown": 0.8,  # Reduce exposure in unknown regime
    }

    # Align economic regime with market data
    aligned_regime = economic_regime.reindex(
        pd.date_range(start=market_data.index[0], end=market_data.index[-1], freq="D")
    ).ffill()
    aligned_regime = aligned_regime.reindex(market_data.index).ffill()

    # Adjust signal based on economic regime
    adjusted_signal = adjust_strategy_for_economic_regime(
        base_signal, aligned_regime, adjustment_factors
    )

    # Backtest both strategies
    print("Backtesting strategies...")
    base_equity, base_metrics = backtest_strategy(market_data, base_signal)
    adjusted_equity, adjusted_metrics = backtest_strategy(market_data, adjusted_signal)

    # Print results
    print("\nStrategy Performance Comparison:")
    print(
        f"{'Metric':<20} {'Base Strategy':<15} {'Adjusted Strategy':<15} {'Difference':<15}"
    )
    print("-" * 65)

    for metric in [
        "total_return",
        "annualized_return",
        "max_drawdown",
        "sharpe_ratio",
        "win_rate",
    ]:
        base_val = base_metrics[metric]
        adj_val = adjusted_metrics[metric]
        diff = adj_val - base_val

        # Format as percentage for certain metrics
        if metric in ["total_return", "annualized_return", "max_drawdown", "win_rate"]:
            print(
                f"{metric:<20} {base_val*100:>12.2f}% {adj_val*100:>14.2f}% {diff*100:>13.2f}%"
            )
        else:
            print(f"{metric:<20} {base_val:>14.2f} {adj_val:>14.2f} {diff:>15.2f}")

    # Plot results
    plt.figure(figsize=(12, 8))

    # Plot 1: Equity curves
    plt.subplot(2, 1, 1)
    base_equity["equity"].plot(label="Base Strategy")
    adjusted_equity["equity"].plot(label="Regime-Adjusted Strategy")
    plt.title("Strategy Equity Curves")
    plt.ylabel("Equity ($)")
    plt.grid(True)
    plt.legend()

    # Plot 2: Drawdowns
    plt.subplot(2, 1, 2)
    base_equity["drawdown"].plot(label="Base Strategy")
    adjusted_equity["drawdown"].plot(label="Regime-Adjusted Strategy")
    plt.title("Strategy Drawdowns")
    plt.ylabel("Drawdown (%)")
    plt.xlabel("Date")
    plt.grid(True)
    plt.legend()

    plt.tight_layout()
    plt.savefig("strategy_comparison.png")
    print("Saved strategy comparison chart to strategy_comparison.png")

    # Plot economic regimes
    plt.figure(figsize=(12, 6))

    # Create a categorical color map for regimes
    unique_regimes = economic_regime.unique()
    colors = plt.cm.tab10(np.linspace(0, 1, len(unique_regimes)))
    regime_colors = {regime: colors[i] for i, regime in enumerate(unique_regimes)}

    # Convert economic_regime to numeric for plotting
    regime_numeric = pd.Series(index=economic_regime.index)
    for i, regime in enumerate(unique_regimes):
        regime_numeric[economic_regime == regime] = i

    # Plot
    for i, regime in enumerate(unique_regimes):
        mask = economic_regime == regime
        if mask.any():
            plt.scatter(
                economic_regime[mask].index,
                [i] * mask.sum(),
                marker="s",
                s=60,
                c=[regime_colors[regime]],
                label=regime,
            )

    plt.yticks(range(len(unique_regimes)), unique_regimes)
    plt.title("Economic Regimes Over Time")
    plt.xlabel("Date")
    plt.ylabel("Regime")
    plt.grid(True, axis="x")
    plt.legend(loc="upper right")

    plt.tight_layout()
    plt.savefig("economic_regimes.png")
    print("Saved economic regimes chart to economic_regimes.png")

    return 0


if __name__ == "__main__":
    sys.exit(main())
