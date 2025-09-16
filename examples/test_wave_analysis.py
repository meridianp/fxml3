"""Example script demonstrating Elliott Wave analysis functionality.

This script shows how to use the Elliott Wave analysis components
to detect wave patterns in price data and visualize the results.
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Ensure FXML4 is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.fibonacci import FibonacciCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_test_data(periods: int = 100) -> pd.DataFrame:
    """Create test price data with clear wave patterns.

    Args:
        periods: Number of periods to generate

    Returns:
        DataFrame with OHLCV price data
    """
    logger.info(f"Generating {periods} periods of test data")

    # Create date range
    dates = pd.date_range(start="2023-01-01", periods=periods, freq="D")

    # Create a structured price series that resembles an Elliott wave pattern
    # This is stylized to have clear impulse and corrective waves

    # Start with a base price
    base_price = 100

    # Create arrays to store the values
    close_prices = np.zeros(periods)

    # Create a 5-3-5-3-5 wave structure (impulse, corrective, impulse)
    # Wave 1: Up
    wave1_length = 10
    wave1_height = 10
    for i in range(wave1_length):
        progress = i / wave1_length
        close_prices[i] = base_price + wave1_height * progress

    # Wave 2: Down (corrective)
    wave2_length = 5
    wave2_height = 6  # 60% retracement of wave 1
    for i in range(wave1_length, wave1_length + wave2_length):
        progress = (i - wave1_length) / wave2_length
        close_prices[i] = base_price + wave1_height - wave2_height * progress

    # Wave 3: Up (strongest)
    wave3_length = 15
    wave3_height = 25  # Wave 3 is typically the longest
    for i in range(
        wave1_length + wave2_length, wave1_length + wave2_length + wave3_length
    ):
        progress = (i - (wave1_length + wave2_length)) / wave3_length
        close_prices[i] = (
            base_price + wave1_height - wave2_height + wave3_height * progress
        )

    # Wave 4: Down (corrective)
    wave4_length = 8
    wave4_height = 10  # About 38% retracement of wave 3
    for i in range(
        wave1_length + wave2_length + wave3_length,
        wave1_length + wave2_length + wave3_length + wave4_length,
    ):
        progress = (i - (wave1_length + wave2_length + wave3_length)) / wave4_length
        close_prices[i] = (
            base_price
            + wave1_height
            - wave2_height
            + wave3_height
            - wave4_height * progress
        )

    # Wave 5: Up (final impulse)
    wave5_length = 12
    wave5_height = 15
    for i in range(
        wave1_length + wave2_length + wave3_length + wave4_length,
        wave1_length + wave2_length + wave3_length + wave4_length + wave5_length,
    ):
        progress = (
            i - (wave1_length + wave2_length + wave3_length + wave4_length)
        ) / wave5_length
        close_prices[i] = (
            base_price
            + wave1_height
            - wave2_height
            + wave3_height
            - wave4_height
            + wave5_height * progress
        )

    # Wave A: Down (start of corrective pattern)
    wave_a_length = 10
    wave_a_height = 20
    for i in range(
        wave1_length + wave2_length + wave3_length + wave4_length + wave5_length,
        wave1_length
        + wave2_length
        + wave3_length
        + wave4_length
        + wave5_length
        + wave_a_length,
    ):
        progress = (
            i
            - (wave1_length + wave2_length + wave3_length + wave4_length + wave5_length)
        ) / wave_a_length
        close_prices[i] = (
            base_price
            + wave1_height
            - wave2_height
            + wave3_height
            - wave4_height
            + wave5_height
            - wave_a_height * progress
        )

    # Wave B: Up (corrective)
    wave_b_length = 7
    wave_b_height = 12  # About 60% retracement of wave A
    for i in range(
        wave1_length
        + wave2_length
        + wave3_length
        + wave4_length
        + wave5_length
        + wave_a_length,
        wave1_length
        + wave2_length
        + wave3_length
        + wave4_length
        + wave5_length
        + wave_a_length
        + wave_b_length,
    ):
        progress = (
            i
            - (
                wave1_length
                + wave2_length
                + wave3_length
                + wave4_length
                + wave5_length
                + wave_a_length
            )
        ) / wave_b_length
        close_prices[i] = (
            base_price
            + wave1_height
            - wave2_height
            + wave3_height
            - wave4_height
            + wave5_height
            - wave_a_height
            + wave_b_height * progress
        )

    # Wave C: Down (final corrective)
    wave_c_length = 13
    wave_c_height = 25
    for i in range(
        wave1_length
        + wave2_length
        + wave3_length
        + wave4_length
        + wave5_length
        + wave_a_length
        + wave_b_length,
        min(
            periods,
            wave1_length
            + wave2_length
            + wave3_length
            + wave4_length
            + wave5_length
            + wave_a_length
            + wave_b_length
            + wave_c_length,
        ),
    ):
        progress = (
            i
            - (
                wave1_length
                + wave2_length
                + wave3_length
                + wave4_length
                + wave5_length
                + wave_a_length
                + wave_b_length
            )
        ) / wave_c_length
        close_prices[i] = (
            base_price
            + wave1_height
            - wave2_height
            + wave3_height
            - wave4_height
            + wave5_height
            - wave_a_height
            + wave_b_height
            - wave_c_height * progress
        )

    # Fill any remaining indices with a slight uptrend
    remaining_start = (
        wave1_length
        + wave2_length
        + wave3_length
        + wave4_length
        + wave5_length
        + wave_a_length
        + wave_b_length
        + wave_c_length
    )
    for i in range(remaining_start, periods):
        if i >= len(close_prices):
            break
        close_prices[i] = (
            close_prices[remaining_start - 1] + (i - remaining_start + 1) * 0.5
        )

    # Add small random noise to make it more realistic
    noise = np.random.normal(0, 1, periods)
    close_prices = close_prices + noise

    # Create open, high, low values based on close
    open_prices = np.roll(close_prices, 1)
    open_prices[0] = close_prices[0] - 1

    high_prices = np.maximum(open_prices, close_prices) + np.random.uniform(
        0.1, 0.5, periods
    )
    low_prices = np.minimum(open_prices, close_prices) - np.random.uniform(
        0.1, 0.5, periods
    )
    volume = np.random.randint(1000, 10000, periods)

    # Create the DataFrame all at once to avoid chained indexing warnings
    df = pd.DataFrame(
        {
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volume,
        },
        index=dates,
    )

    return df


def plot_wave_patterns(
    price_data: pd.DataFrame, wave_points: Dict[str, List[Tuple[int, float]]]
) -> None:
    """Plot price data with identified Elliott Wave patterns.

    Args:
        price_data: DataFrame with OHLCV price data
        wave_points: Dictionary with wave points from ElliottWaveAnalyzer
    """
    logger.info("Plotting wave patterns")

    # Create plotly figure
    fig = make_subplots(
        rows=1, cols=1, shared_xaxes=True, subplot_titles=["Elliott Wave Analysis"]
    )

    # Add candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=price_data.index,
            open=price_data["open"],
            high=price_data["high"],
            low=price_data["low"],
            close=price_data["close"],
            name="Price",
        )
    )

    # Colors for different wave types
    impulse_colors = ["blue", "red", "green", "orange", "purple"]
    corrective_colors = ["brown", "teal", "pink"]

    # Add wave points as scatter plots with annotations
    for label, points in wave_points.items():
        parts = label.split("_")

        # Extract pattern type, wave number, and point type
        if len(parts) < 3:
            continue

        pattern_type = parts[0]
        wave_num = parts[1]
        point_type = parts[2]  # 'start' or 'end'

        # Skip if no points
        if not points:
            continue

        # Select color based on pattern
        if "impulse" in pattern_type:
            if wave_num.isdigit() and 1 <= int(wave_num) <= 5:
                color = impulse_colors[int(wave_num) - 1]
            else:
                color = "gray"
        elif "corrective" in pattern_type:
            if wave_num in ["A", "B", "C"]:
                color = corrective_colors[ord(wave_num) - ord("A")]
            else:
                color = "gray"
        else:
            color = "gray"

        # Get point coordinates
        x_values = [price_data.index[idx] for idx, _ in points]
        y_values = [price for _, price in points]

        # Add scatter points
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="markers+text",
                marker=dict(color=color, size=10),
                text=[f"{wave_num}" for _ in points],
                textposition="top center",
                name=f"{pattern_type}_{wave_num}_{point_type}",
            )
        )

    # Update layout
    fig.update_layout(
        title="Elliott Wave Pattern Detection",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        height=800,
        width=1200,
    )

    # Show figure
    fig.show()


def create_sample_wave_points(df: pd.DataFrame) -> Dict[str, List[Tuple[int, float]]]:
    """Create sample wave points for demonstration purposes.

    This function manually creates wave points at specific locations in the data
    to ensure we have some patterns to display, even if the automatic detection fails.

    Args:
        df: DataFrame with price data

    Returns:
        Dictionary with wave points
    """
    logger.info("Creating sample wave points for demonstration")

    wave_points = {}

    # Create a 5-wave impulse pattern
    # Wave 1
    wave_points["impulse_2_1_start"] = [(0, float(df["close"].iloc[0]))]
    wave_points["impulse_2_1_end"] = [(10, float(df["close"].iloc[10]))]

    # Wave 2
    wave_points["impulse_2_2_start"] = [(10, float(df["close"].iloc[10]))]
    wave_points["impulse_2_2_end"] = [(15, float(df["close"].iloc[15]))]

    # Wave 3
    wave_points["impulse_2_3_start"] = [(15, float(df["close"].iloc[15]))]
    wave_points["impulse_2_3_end"] = [(30, float(df["close"].iloc[30]))]

    # Wave 4
    wave_points["impulse_2_4_start"] = [(30, float(df["close"].iloc[30]))]
    wave_points["impulse_2_4_end"] = [(38, float(df["close"].iloc[38]))]

    # Wave 5
    wave_points["impulse_2_5_start"] = [(38, float(df["close"].iloc[38]))]
    wave_points["impulse_2_5_end"] = [(50, float(df["close"].iloc[50]))]

    # Create a 3-wave corrective pattern
    # Wave A
    wave_points["corrective_2_A_start"] = [(50, float(df["close"].iloc[50]))]
    wave_points["corrective_2_A_end"] = [(60, float(df["close"].iloc[60]))]

    # Wave B
    wave_points["corrective_2_B_start"] = [(60, float(df["close"].iloc[60]))]
    wave_points["corrective_2_B_end"] = [(67, float(df["close"].iloc[67]))]

    # Wave C
    wave_points["corrective_2_C_start"] = [(67, float(df["close"].iloc[67]))]
    wave_points["corrective_2_C_end"] = [(80, float(df["close"].iloc[80]))]

    return wave_points


def main():
    """Main function demonstrating Elliott Wave analysis."""
    logger.info("Starting Elliott Wave analysis example")

    # Create test data
    df = create_test_data(periods=100)
    logger.info(f"Created test data: {len(df)} data points")

    # Initialize Elliott Wave analyzer with very relaxed parameters for the test data
    analyzer = ElliottWaveAnalyzer(
        fib_tolerance=0.3,  # Use much wider tolerance for test data
        min_wave_size=0.001,  # Allow very small waves
        peak_detection_window=2,  # Small window to detect more peaks
        min_wave_length=2,  # Allow short waves
        look_back_periods=[2, 3, 4],  # Multiple window sizes for detection
    )
    logger.info("Initialized Elliott Wave analyzer")

    # Attempt automatic wave detection
    wave_points = analyzer.detect_waves(df)
    logger.info(f"Detected {len(wave_points)} wave points")

    # If no wave points detected, create sample ones for demonstration
    if len(wave_points) == 0:
        logger.info(
            "No wave patterns detected automatically. Using sample patterns for demonstration."
        )
        wave_points = create_sample_wave_points(df)

    # Create labeled dataframe
    labeled_df = analyzer.label_chart_data(df, wave_points)
    logger.info(f"Created labeled DataFrame with wave patterns")

    # Log detected wave patterns
    for label, points in wave_points.items():
        if points:
            logger.info(f"Wave {label}: {len(points)} points")

    # Create Fibonacci calculator for additional analysis
    fib_calculator = FibonacciCalculator(tolerance=0.1)

    # Calculate Fibonacci price zones
    fib_zones_df = fib_calculator.calculate_fibonacci_price_zones(df, window_size=10)
    logger.info(f"Calculated Fibonacci price zones")

    # Print some Fibonacci levels
    for i in range(20, 30):
        fib_levels = ", ".join(
            [
                f"{col}:{fib_zones_df[col].iloc[i]:.2f}"
                for col in fib_zones_df.columns
                if col.startswith("fib_level_")
            ]
        )
        logger.info(f"Date {fib_zones_df.index[i]}: {fib_levels}")

    # Plot wave patterns
    try:
        plot_wave_patterns(df, wave_points)
    except Exception as e:
        logger.error(f"Error plotting wave patterns: {e}")
        # If plotly fails, use matplotlib as fallback
        plt.figure(figsize=(12, 8))
        plt.plot(df.index, df["close"], label="Close")
        plt.title("Price Chart with Elliott Wave Analysis")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.legend()
        plt.tight_layout()
        plt.show()

    logger.info("Elliott Wave analysis example completed")


if __name__ == "__main__":
    main()
