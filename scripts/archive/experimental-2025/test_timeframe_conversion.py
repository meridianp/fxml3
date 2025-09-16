#!/usr/bin/env python3
"""
Test script for timeframe conversion and derived timeframes.

This script demonstrates how to:
1. Create sample OHLCV data
2. Use the TimeframeConverter to derive higher timeframes
3. Visualize and compare timeframes
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add the project root to the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from fxml4.data_engineering.timeframe_conversion import (
    TimeframeConverter,
    convert_to_pandas_freq,
    resample_ohlcv,
)


def create_sample_data(symbol: str, days: int = 5) -> pd.DataFrame:
    """Create sample 1-minute OHLCV data.

    Args:
        symbol: Symbol to create data for
        days: Number of days of data to create

    Returns:
        DataFrame with 1-minute OHLCV data
    """
    # Start from the beginning of a day
    start_time = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Generate timestamps for each minute
    minutes_per_day = 24 * 60
    total_minutes = days * minutes_per_day
    timestamps = [start_time + timedelta(minutes=i) for i in range(total_minutes)]

    # Create price data with some volatility and trend
    prices = []
    price = 100.0

    # Add daily patterns and trends
    for i in range(total_minutes):
        # Time of day effect (U-shaped volatility)
        hour = (start_time + timedelta(minutes=i)).hour
        minute = (start_time + timedelta(minutes=i)).minute

        # More volatility at market open and close
        time_volatility = 0.15
        if 0 <= hour < 8:  # Overnight
            time_volatility = 0.02
        elif 8 <= hour < 10:  # Market open
            time_volatility = 0.2
        elif 10 <= hour < 15:  # Mid-day
            time_volatility = 0.08
        elif 15 <= hour < 17:  # Market close
            time_volatility = 0.15
        else:  # Evening
            time_volatility = 0.05

        # Add some mean reversion
        mean_reversion = 0.02 * (100.0 - price)

        # Add some trending behavior
        day = i // minutes_per_day
        trend = 0.05 * np.sin(day * np.pi / 2)  # Cycle every 4 days

        # Random walk with all components
        step = np.random.normal(0, time_volatility)
        price += step + mean_reversion + trend
        prices.append(price)

    # Create OHLCV data with some realistic behavior
    data = []
    for i, ts in enumerate(timestamps):
        close_price = prices[i]

        # Generate realistic OHLC relationships
        price_range = 0.2 * np.sqrt(np.abs(prices[i] - prices[i - 1])) if i > 0 else 0.1
        high_price = close_price + np.random.uniform(0.01, price_range)
        low_price = close_price - np.random.uniform(0.01, price_range)

        # Ensure high >= open/close >= low
        if i > 0:
            open_price = prices[i - 1]  # Open = previous close
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
        else:
            open_price = close_price - np.random.uniform(-0.05, 0.05)
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)

        # Volume tends to be higher during volatile periods
        volume_base = np.random.randint(500, 1500)
        volume_volatility = np.abs(prices[i] - prices[i - 1]) * 5000 if i > 0 else 0
        volume = volume_base + int(volume_volatility)

        data.append(
            {
                "timestamp": ts,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
            }
        )

    # Create DataFrame
    df = pd.DataFrame(data)
    df.set_index("timestamp", inplace=True)

    print(
        f"Created sample data for {symbol}: {len(df)} rows from {df.index.min()} to {df.index.max()}"
    )
    return df


def plot_timeframes(symbol: str, timeframe_data: dict):
    """Plot data for multiple timeframes.

    Args:
        symbol: Symbol being plotted
        timeframe_data: Dictionary mapping timeframe to DataFrame
    """
    # Create a figure with subplots
    fig, axes = plt.subplots(len(timeframe_data), 1, figsize=(12, 10), sharex=True)

    # If only one timeframe, make axes a list
    if len(timeframe_data) == 1:
        axes = [axes]

    # Plot each timeframe
    for i, (timeframe, df) in enumerate(timeframe_data.items()):
        ax = axes[i]

        # Plot OHLC
        for idx, row in df.iterrows():
            # Determine candle color (green for up, red for down)
            color = "green" if row["close"] >= row["open"] else "red"

            # Plot candle body
            body_bottom = min(row["open"], row["close"])
            body_top = max(row["open"], row["close"])
            body_height = body_top - body_bottom

            # Plot candle body
            ax.bar(
                idx, body_height, bottom=body_bottom, width=0.6, color=color, alpha=0.6
            )

            # Plot high/low wicks
            ax.plot([idx, idx], [row["low"], body_bottom], color="black", linewidth=1)
            ax.plot([idx, idx], [body_top, row["high"]], color="black", linewidth=1)

        # Set title and labels
        ax.set_title(f"{symbol} - {timeframe}")
        ax.set_ylabel("Price")

        # Format x-axis for better readability
        if i == len(timeframe_data) - 1:  # Only for the last subplot
            ax.tick_params(axis="x", rotation=45)

    # Add volume subplot
    ax_vol = plt.subplot(
        len(timeframe_data) + 1, 1, len(timeframe_data) + 1, sharex=axes[0]
    )

    # Get the 1-minute data for volume
    if "1m" in timeframe_data:
        volume_df = timeframe_data["1m"]
    else:
        volume_df = list(timeframe_data.values())[
            0
        ]  # Use the first available timeframe

    # Plot volume bars
    ax_vol.bar(volume_df.index, volume_df["volume"], width=0.6, color="blue", alpha=0.5)
    ax_vol.set_ylabel("Volume")

    # Format the plot
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.3)

    # Show the plot
    plt.show()


def test_timeframe_conversion():
    """Test timeframe conversion with sample data."""
    # Create sample data
    symbol = "EUR.USD"
    one_min_data = create_sample_data(symbol, days=2)

    # Create timeframe converter
    converter = TimeframeConverter(
        base_timeframe="1m", derived_timeframes=["5m", "15m", "1h", "4h"]
    )

    # Update with sample data
    result = converter.update_data(symbol, one_min_data)

    # Print summary of derived timeframes
    print("\nDerived Timeframes Summary:")
    for tf, df in result.items():
        print(f"{tf}: {len(df)} rows")

    # Get and print a sample of the data
    print("\nSample 1-hour data:")
    hourly_data = converter.get_data(symbol, "1h")
    if not hourly_data.empty:
        print(hourly_data.head())

    # Plot the data for different timeframes
    timeframe_data = {
        "1m": converter.get_data(symbol, "1m").tail(60),  # Last 60 minutes
        "5m": converter.get_data(symbol, "5m").tail(24),  # Last 2 hours
        "15m": converter.get_data(symbol, "15m").tail(16),  # Last 4 hours
        "1h": converter.get_data(symbol, "1h").tail(8),  # Last 8 hours
    }

    print("\nPlotting timeframes...")
    plot_timeframes(symbol, timeframe_data)


if __name__ == "__main__":
    test_timeframe_conversion()
