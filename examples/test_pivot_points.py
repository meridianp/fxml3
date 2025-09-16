"""Test script for pivot point analysis.

This script tests the pivot point analysis functions on a sample dataset.
"""

import logging
import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add the parent directory to sys.path to import the modules directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fxml4.ml.features import (
    calculate_session_pivot_levels,
    calculate_weekly_pivot_points,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directory paths
OUTPUT_DIR = "output"


def create_sample_data():
    """Create a sample dataset for testing pivot points.

    Returns:
        DataFrame with OHLC price data
    """
    logger.info("Creating sample data")

    # Create a date range
    dates = pd.date_range(start="2023-01-01", end="2023-01-31", freq="4H")

    # Create OHLC data with a realistic trend
    np.random.seed(42)  # For reproducibility

    # Starting price
    price = 1.25

    # Arrays to store OHLC
    opens = []
    highs = []
    lows = []
    closes = []

    # Create trending price data
    for i in range(len(dates)):
        # Calculate random changes with momentum
        if i > 0:
            momentum = 0.3 * (closes[-1] - opens[-1])
            daily_drift = 0.0001 * np.sin(i / 30)  # Slight cyclical bias
        else:
            momentum = 0
            daily_drift = 0

        # Generate OHLC for this period
        daily_volatility = 0.002
        open_price = price
        close_price = price * (
            1 + np.random.normal(momentum + daily_drift, daily_volatility)
        )
        high_price = max(open_price, close_price) * (
            1 + abs(np.random.normal(0, daily_volatility * 0.5))
        )
        low_price = min(open_price, close_price) * (
            1 - abs(np.random.normal(0, daily_volatility * 0.5))
        )

        # Store values
        opens.append(open_price)
        highs.append(high_price)
        lows.append(low_price)
        closes.append(close_price)

        # Update price for next period
        price = close_price

    # Create DataFrame
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes}, index=dates
    )

    logger.info(f"Created sample data with {len(df)} rows")

    return df


def validate_pivot_calculations(df_with_pivots):
    """Validate pivot point calculations against expected values.

    Args:
        df_with_pivots: DataFrame with calculated pivot points

    Returns:
        Boolean indicating if validation passed
    """
    logger.info("Validating pivot point calculations")

    # Make sure pivot columns exist
    required_pivot_cols = ["PP", "R1", "S1", "R2", "S2"]
    missing_cols = [
        col for col in required_pivot_cols if col not in df_with_pivots.columns
    ]

    if missing_cols:
        logger.error(f"Missing pivot columns: {missing_cols}")
        return False

    # Validate a specific weekly pivot calculation
    # Get a week of data
    weekly_df = (
        df_with_pivots.resample("W-SUN")
        .agg({"high": "max", "low": "min", "close": "last"})
        .iloc[0]
    )

    # Calculate expected pivot levels
    high = weekly_df["high"]
    low = weekly_df["low"]
    close = weekly_df["close"]

    expected_pp = (high + low + close) / 3
    expected_r1 = 2 * expected_pp - low
    expected_s1 = 2 * expected_pp - high

    # Get the calculated pivot values for the first day of the next week
    next_week_start = df_with_pivots.resample("W-SUN").first().index[1]
    calculated_pivots = df_with_pivots.loc[next_week_start]

    # Compare values (allowing for small floating point differences)
    pp_diff = abs(calculated_pivots["PP"] - expected_pp)
    r1_diff = abs(calculated_pivots["R1"] - expected_r1)
    s1_diff = abs(calculated_pivots["S1"] - expected_s1)

    # Tolerance for comparison
    tolerance = 1e-10

    if pp_diff > tolerance or r1_diff > tolerance or s1_diff > tolerance:
        logger.error("Pivot point calculations do not match expected values")
        logger.error(
            f"Expected PP: {expected_pp}, Calculated: {calculated_pivots['PP']}"
        )
        logger.error(
            f"Expected R1: {expected_r1}, Calculated: {calculated_pivots['R1']}"
        )
        logger.error(
            f"Expected S1: {expected_s1}, Calculated: {calculated_pivots['S1']}"
        )
        return False

    logger.info("Pivot point calculations validated successfully")
    return True


def visualize_sample_with_pivots(df_with_pivots):
    """Create visualization of sample data with pivot points.

    Args:
        df_with_pivots: DataFrame with calculated pivot points
    """
    logger.info("Creating visualization")

    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Create plot
    plt.figure(figsize=(15, 8))

    # Plot price
    plt.plot(
        df_with_pivots.index, df_with_pivots["close"], label="Close", color="black"
    )

    # Plot pivot points
    plt.plot(
        df_with_pivots.index, df_with_pivots["PP"], label="Pivot Point", color="blue"
    )
    plt.plot(
        df_with_pivots.index,
        df_with_pivots["R1"],
        label="R1",
        color="red",
        linestyle="--",
    )
    plt.plot(
        df_with_pivots.index,
        df_with_pivots["S1"],
        label="S1",
        color="green",
        linestyle="--",
    )

    # Highlight where price crosses R1 or S1
    above_r1 = df_with_pivots.index[df_with_pivots["close"] > df_with_pivots["R1"]]
    below_s1 = df_with_pivots.index[df_with_pivots["close"] < df_with_pivots["S1"]]

    if len(above_r1) > 0:
        plt.scatter(
            above_r1,
            df_with_pivots.loc[above_r1, "close"],
            color="red",
            marker="^",
            s=100,
            label="Above R1",
        )

    if len(below_s1) > 0:
        plt.scatter(
            below_s1,
            df_with_pivots.loc[below_s1, "close"],
            color="green",
            marker="v",
            s=100,
            label="Below S1",
        )

    # Add chart elements
    plt.title("Sample Data with Weekly Pivot Points")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.grid(True, alpha=0.3)
    plt.legend()

    # Save figure
    plt.savefig(os.path.join(OUTPUT_DIR, "pivot_point_test.png"))
    plt.close()

    logger.info(
        f"Visualization saved to {os.path.join(OUTPUT_DIR, 'pivot_point_test.png')}"
    )


def main():
    """Test pivot point analysis functions."""
    logger.info("Testing pivot point analysis")

    # Create sample data
    sample_data = create_sample_data()

    # Calculate weekly pivot points
    logger.info("Calculating weekly pivot points")
    data_with_weekly_pivots = calculate_weekly_pivot_points(sample_data)

    # Calculate session/daily pivot points
    logger.info("Calculating session pivot points")
    data_with_all_pivots = calculate_session_pivot_levels(data_with_weekly_pivots)

    # Validate calculations
    validation_passed = validate_pivot_calculations(data_with_all_pivots)

    if validation_passed:
        logger.info("All pivot point calculations validated successfully")
    else:
        logger.warning("Pivot point calculation validation failed")

    # Create visualization
    visualize_sample_with_pivots(data_with_all_pivots)

    # Display summary of features
    pivot_columns = [
        col
        for col in data_with_all_pivots.columns
        if "PP" in col or "R1" in col or "S1" in col or "R2" in col or "S2" in col
    ]

    logger.info(f"Added {len(pivot_columns)} pivot-related columns:")
    for col in pivot_columns:
        logger.info(f"  - {col}")

    logger.info("Pivot point testing complete")


if __name__ == "__main__":
    main()
