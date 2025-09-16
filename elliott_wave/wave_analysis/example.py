"""Example usage of Elliott Wave detection."""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

from fxml3.visualization.chart import plot_interactive_chart, plot_wave_analysis
from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml3.wave_analysis.fibonacci import FibonacciCalculator


def download_sample_data() -> pd.DataFrame:
    """Download sample forex data using yfinance.

    Returns:
        DataFrame with OHLCV data
    """
    # Download EUR/USD daily data for the past year
    ticker = "EURUSD=X"
    df = yf.download(ticker, period="1y", interval="1d")

    # Rename columns to lowercase
    df.columns = [col.lower() for col in df.columns]

    return df


def create_synthetic_elliott_wave_data() -> pd.DataFrame:
    """Create synthetic data with a clear Elliott Wave pattern.

    Returns:
        DataFrame with OHLCV data containing an Elliott Wave pattern
    """
    # Create dates for one year of daily data
    dates = pd.date_range(start="2023-01-01", periods=250, freq="D")

    # Start with a base price and add some noise
    base_price = 100
    noise_factor = 1.0

    # Create an array for prices
    prices = []
    current_price = base_price

    # Generate a complete market cycle with Elliott Waves

    # Initial uptrend with 5-wave impulse
    # Wave 1
    wave1_length = 40
    wave1_move = 15
    for i in range(wave1_length):
        progress = i / wave1_length
        price_change = wave1_move * progress
        noise = np.random.normal(0, noise_factor)
        current_price = base_price + price_change + noise
        prices.append(max(1, current_price))  # Ensure price doesn't go below 1

    # Wave 2 (retraces ~50% of wave 1)
    wave2_length = 25
    wave2_move = -wave1_move * 0.5
    start_price = prices[-1]
    for i in range(wave2_length):
        progress = i / wave2_length
        price_change = wave2_move * progress
        noise = np.random.normal(0, noise_factor)
        current_price = start_price + price_change + noise
        prices.append(max(1, current_price))

    # Wave 3 (longest and strongest, 1.618 times wave 1)
    wave3_length = 60
    wave3_move = wave1_move * 1.618
    start_price = prices[-1]
    for i in range(wave3_length):
        progress = i / wave3_length
        # Accelerating move to simulate strong trend
        price_change = wave3_move * (progress**1.5)
        noise = np.random.normal(0, noise_factor * 0.5)  # Less noise in strong trend
        current_price = start_price + price_change + noise
        prices.append(max(1, current_price))

    # Wave 4 (retraces ~38% of wave 3)
    wave4_length = 30
    wave4_move = -wave3_move * 0.382
    start_price = prices[-1]
    for i in range(wave4_length):
        progress = i / wave4_length
        price_change = wave4_move * progress
        noise = np.random.normal(0, noise_factor * 1.2)  # More noise in consolidation
        current_price = start_price + price_change + noise
        prices.append(max(1, current_price))

    # Wave 5 (similar to wave 1)
    wave5_length = 45
    wave5_move = wave1_move * 0.9  # Slightly weaker than wave 1
    start_price = prices[-1]
    for i in range(wave5_length):
        progress = i / wave5_length
        price_change = wave5_move * progress
        noise = np.random.normal(0, noise_factor)
        current_price = start_price + price_change + noise
        prices.append(max(1, current_price))

    # Complete with an A-B-C corrective pattern
    # Wave A (sharp decline)
    waveA_length = 35
    waveA_move = -(wave1_move + wave3_move + wave5_move) * 0.5  # Significant correction
    start_price = prices[-1]
    for i in range(waveA_length):
        progress = i / waveA_length
        price_change = waveA_move * progress
        noise = np.random.normal(0, noise_factor * 0.7)  # Less noise in sharp decline
        current_price = start_price + price_change + noise
        prices.append(max(1, current_price))

    # Wave B (retraces ~62% of wave A)
    waveB_length = 30
    waveB_move = -waveA_move * 0.618
    start_price = prices[-1]
    for i in range(waveB_length):
        progress = i / waveB_length
        price_change = waveB_move * progress
        noise = np.random.normal(0, noise_factor * 1.2)
        current_price = start_price + price_change + noise
        prices.append(max(1, current_price))

    # Wave C (similar to wave A)
    waveC_length = 35
    waveC_move = waveA_move * 1.0
    start_price = prices[-1]
    for i in range(waveC_length):
        progress = i / waveC_length
        price_change = waveC_move * progress
        noise = np.random.normal(0, noise_factor * 0.7)
        current_price = start_price + price_change + noise
        prices.append(max(1, current_price))

    # Trim to fit our date range
    prices = prices[: len(dates)]

    # Generate OHLCV data from the close prices
    df = pd.DataFrame(index=dates[: len(prices)])
    df["close"] = prices

    # Generate open, high, low based on close
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0])
    daily_volatility = df["close"].pct_change().std() * 2

    df["high"] = df.apply(
        lambda row: max(row["open"], row["close"])
        * (1 + np.random.uniform(0.001, daily_volatility)),
        axis=1,
    )
    df["low"] = df.apply(
        lambda row: min(row["open"], row["close"])
        * (1 - np.random.uniform(0.001, daily_volatility)),
        axis=1,
    )

    # Add random volume
    df["volume"] = np.random.randint(1000, 100000, size=len(df))

    return df


def analyze_and_plot(df: pd.DataFrame, output_path: Optional[str] = None) -> None:
    """Analyze data for Elliott Wave patterns and plot the results.

    Args:
        df: DataFrame with OHLCV data
        output_path: Path to save the output chart
    """
    # Initialize analyzers
    wave_analyzer = ElliottWaveAnalyzer(
        fib_tolerance=0.15,
        min_wave_size=0.01,
        peak_detection_window=5,
        min_wave_length=3,
        look_back_periods=[5, 8, 13, 21],
    )

    fib_calculator = FibonacciCalculator(tolerance=0.15)

    # Detect Elliott Wave patterns
    wave_points = wave_analyzer.detect_waves(df)

    # Label data with wave annotations
    labeled_df = wave_analyzer.label_chart_data(df, wave_points, output_form="columns")

    # Add Fibonacci price zones
    labeled_df = fib_calculator.calculate_fibonacci_price_zones(
        labeled_df, window_size=21
    )

    # Create interactive chart
    pattern_types = set([label.split("_")[0] for label in wave_points.keys()])

    # Find the wave pattern with the most points
    pattern_counts = {}
    for pattern in pattern_types:
        pattern_counts[pattern] = sum(
            1 for label in wave_points.keys() if label.startswith(pattern)
        )

    # Use the pattern with the most points as the main pattern to visualize
    if pattern_counts:
        main_pattern = max(pattern_counts.items(), key=lambda x: x[1])[0]
        print(f"Main pattern detected: {main_pattern}")

        # Create and show chart
        try:
            # For pattern types like 'impulse_5' or 'corrective_8'
            for period in [5, 8, 13, 21]:
                pattern_col = f"{main_pattern}_{period}"
                if pattern_col in labeled_df.columns and labeled_df[pattern_col].any():
                    print(f"Plotting pattern: {pattern_col}")
                    fig = plot_wave_analysis(
                        labeled_df,
                        wave_col=pattern_col,
                        title=f"Elliott Wave Analysis - {pattern_col}",
                    )

                    if output_path:
                        # Check if output directory exists
                        output_dir = os.path.dirname(output_path)
                        if output_dir and not os.path.exists(output_dir):
                            os.makedirs(output_dir)

                        # Save figure
                        plt_out = f"{output_path}_{period}.html"
                        fig.write_html(plt_out)
                        print(f"Chart saved to {plt_out}")
                    else:
                        # Display figure
                        fig.show()
        except Exception as e:
            print(f"Error plotting wave analysis: {str(e)}")

            # Fallback to regular chart with Fibonacci levels
            fig = plot_interactive_chart(
                labeled_df,
                title="Forex Price Chart with Fibonacci Levels",
                volume=True,
                indicators={"ma": ["sma_20", "sma_50"], "oscillator": ["rsi_14"]},
                show_fibonacci=True,
            )

            if output_path:
                plt_out = f"{output_path}_basic.html"
                fig.write_html(plt_out)
                print(f"Basic chart saved to {plt_out}")
            else:
                fig.show()
    else:
        print("No patterns detected")


def main():
    """Run the Elliott Wave analysis example."""
    print("Elliott Wave Analysis Example")
    print("============================")

    # Choose data source
    use_synthetic = input("Use synthetic data? (y/n, default: y): ").lower() != "n"

    if use_synthetic:
        print("Generating synthetic Elliott Wave data...")
        df = create_synthetic_elliott_wave_data()
    else:
        print("Downloading EUR/USD data...")
        df = download_sample_data()

    # Set output path
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "elliott_wave_analysis")

    # Run analysis
    print(f"Analyzing data ({len(df)} rows)...")
    analyze_and_plot(df, output_path)

    print("Analysis complete")


if __name__ == "__main__":
    main()
