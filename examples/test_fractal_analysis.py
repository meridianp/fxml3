"""Example script demonstrating fractal degree analysis in Elliott Wave theory.

This script shows how to use the FractalDegreeHandler to analyze price patterns
across multiple timeframes and identify nested wave structures.
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Ensure FXML4 is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.fibonacci import FibonacciCalculator
from fxml4.wave_analysis.fractal import FractalDegreeHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_synthetic_multi_timeframe_data() -> Dict[str, pd.DataFrame]:
    """Create synthetic data for multiple timeframes with nested patterns.

    Returns:
        Dictionary mapping timeframes to DataFrames
    """
    data_dict = {}
    start_date = datetime(2023, 1, 1)

    # Create data for each timeframe with appropriate patterns

    # Weekly data (highest degree, Primary)
    # This will be a 5-wave impulse pattern spanning the entire dataset
    weekly_df = create_test_data(
        start_date=start_date,
        periods=20,  # Reduced for testing
        freq="W",
        pattern_type="impulse",
        base_price=100.0,
        volatility=2.0,
        wave_pcts=[0.2, -0.1, 0.35, -0.15, 0.25],  # 5-wave impulse
    )
    data_dict["weekly"] = weekly_df

    # Daily data (intermediate degree)
    # Create a more detailed pattern within the weekly structure
    daily_df = create_test_data(
        start_date=start_date,
        periods=50,  # Reduced for testing
        freq="D",
        pattern_type="complex",
        base_price=100.0,
        volatility=1.0,
        wave_pcts=[
            0.15,
            -0.08,
            0.25,
            -0.1,
            0.18,
            -0.12,
            0.09,
            -0.05,
            0.12,
        ],  # Complex pattern with sub-waves
    )
    data_dict["daily"] = daily_df

    # 4-hour data (minor degree)
    # Even more detailed pattern within the daily structure
    hourly_df = create_test_data(
        start_date=start_date,
        periods=200,  # Use fewer periods for testing
        freq="4h",  # Using lowercase 'h' to avoid FutureWarning
        pattern_type="mixed",
        base_price=100.0,
        volatility=0.5,
        wave_pcts=None,  # Will use default mixed pattern
    )
    data_dict["4h"] = hourly_df

    return data_dict


def create_test_data(
    start_date: datetime,
    periods: int,
    freq: str,
    pattern_type: str = "impulse",
    base_price: float = 100.0,
    volatility: float = 1.0,
    wave_pcts: Optional[List[float]] = None,
) -> pd.DataFrame:
    """Create test price data with Elliott Wave patterns.

    Args:
        start_date: Starting date
        periods: Number of periods
        freq: Frequency ('D', 'W', '4H', etc.)
        pattern_type: 'impulse', 'corrective', 'complex', or 'mixed'
        base_price: Starting price
        volatility: Amount of random noise
        wave_pcts: Optional list of percentage moves for each wave

    Returns:
        DataFrame with price data
    """
    # Create date range
    dates = pd.date_range(start=start_date, periods=periods, freq=freq)

    # Wave sizes and durations depend on pattern type
    if wave_pcts is None:
        if pattern_type == "impulse":
            # 5-wave impulse pattern (up-down-up-down-up)
            wave_pcts = [0.15, -0.08, 0.32, -0.12, 0.18]
        elif pattern_type == "corrective":
            # 3-wave corrective pattern (down-up-down)
            wave_pcts = [-0.2, 0.12, -0.18]
        elif pattern_type == "complex":
            # 9-wave complex pattern (5-wave impulse + 3-wave correction + another impulse start)
            wave_pcts = [0.15, -0.08, 0.25, -0.1, 0.18, -0.12, 0.09, -0.05, 0.12]
        elif pattern_type == "mixed":
            # Mixed pattern with multiple impulse and corrective structures
            wave_pcts = []
            # Add several impulse-correction sequences
            for _ in range(3):
                wave_pcts.extend([0.08, -0.04, 0.12, -0.06, 0.09])  # Impulse
                wave_pcts.extend([-0.07, 0.04, -0.06])  # Correction

    # Wave durations proportional to the number of waves
    total_waves = len(wave_pcts)
    wave_durations = []
    remaining_periods = periods

    for i in range(total_waves):
        # Last wave gets all remaining periods
        if i == total_waves - 1:
            wave_durations.append(remaining_periods)
        else:
            # Allocate periods proportionally
            # Waves 3 (impulse) and A (corrective) are typically longer
            if (pattern_type == "impulse" and i == 2) or (
                pattern_type == "corrective" and i == 0
            ):
                duration = max(1, int(periods * 1.5 / total_waves))
            else:
                duration = max(1, int(periods / total_waves))

            wave_durations.append(duration)
            remaining_periods -= duration

    # Create price data with patterns
    prices = []
    current_price = base_price

    for duration, pct_move in zip(wave_durations, wave_pcts):
        for i in range(duration):
            # Calculate progress through this wave (0 to 1)
            progress = i / max(1, duration - 1)

            # Calculate price change based on wave move
            # Use a curve for more realistic price movement
            if pct_move > 0:
                # Upward wave (accelerates in the middle)
                curve_factor = 4 * progress * (1 - progress)  # Parabolic curve
                price_change = current_price * pct_move * curve_factor
            else:
                # Downward wave (more linear)
                price_change = current_price * pct_move * progress

            # Add some random noise
            noise = np.random.normal(0, volatility * 0.01 * current_price)

            # Update the price
            new_price = current_price + price_change + noise
            prices.append(max(1.0, new_price))  # Ensure price is positive

        # Update the starting price for the next wave
        current_price = prices[-1]

    # If we didn't fill all periods, pad with flat prices
    while len(prices) < periods:
        prices.append(prices[-1])

    # Create DataFrame
    open_prices = np.roll(prices, 1)
    open_prices[0] = prices[0] * 0.99
    high_prices = np.array([p * (1 + np.random.uniform(0.001, 0.01)) for p in prices])
    low_prices = np.array([p * (1 - np.random.uniform(0.001, 0.01)) for p in prices])
    volumes = np.random.randint(1000, 10000, size=len(prices))

    df = pd.DataFrame(
        {
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": prices,
            "volume": volumes,
        },
        index=dates,
    )

    return df


def analyze_multi_timeframe_data(data_dict: Dict[str, pd.DataFrame]) -> Dict:
    """Analyze multi-timeframe data and identify nested wave structures.

    Args:
        data_dict: Dictionary mapping timeframes to DataFrames

    Returns:
        Dictionary containing analysis results
    """
    logger.info(f"Analyzing {len(data_dict)} timeframes")

    # Initialize fractal degree handler
    handler = FractalDegreeHandler(
        base_timeframe="daily", higher_degrees=1, lower_degrees=1
    )

    # Analyze all timeframes
    results = handler.analyze_timeframes(data_dict)
    logger.info(f"Analysis complete. Found patterns in {len(results)} timeframes")

    # For each timeframe, print summary of detected patterns
    for timeframe, result in results.items():
        logger.info(
            f"\nAnalysis for {timeframe} timeframe ({result['degree']} degree):"
        )

        labeled_df = result["labeled_data"]
        wave_points = result["wave_points"]

        # Count wave patterns
        impulse_cols = [col for col in labeled_df.columns if col.startswith("impulse_")]
        corrective_cols = [
            col for col in labeled_df.columns if col.startswith("corrective_")
        ]

        logger.info(f"Detected patterns:")

        for col in impulse_cols:
            waves = labeled_df[labeled_df[col] > 0][col].unique()
            if len(waves) > 0:
                logger.info(f"  - {col}: {len(waves)} waves")

        for col in corrective_cols:
            waves = labeled_df[labeled_df[col] > 0][col].unique()
            if len(waves) > 0:
                logger.info(f"  - {col}: {len(waves)} waves")

    # Get nested structure
    structure = handler.get_complete_wave_structure()

    # Print structure
    logger.info("\nNested Wave Structure:")
    print_structure(structure)

    return {"results": results, "structure": structure, "handler": handler}


def print_structure(structure: Dict, indent: int = 0) -> None:
    """Print the nested wave structure in a readable format.

    Args:
        structure: Wave structure dictionary
        indent: Indentation level
    """
    indent_str = "  " * indent

    for wave_key, wave in structure.items():
        # Extract wave information
        degree = wave["degree"]
        timeframe = wave["timeframe"]
        wave_type = wave["type"]
        wave_num = wave["number"]
        start = wave["start"].strftime("%Y-%m-%d")
        end = wave["end"].strftime("%Y-%m-%d")

        # Print wave details
        logger.info(
            f"{indent_str}[{degree}] {wave_type.capitalize()} Wave {wave_num} ({timeframe}): {start} → {end}"
        )

        # Print subwaves recursively
        if wave["subwaves"]:
            print_structure(wave["subwaves"], indent=indent + 1)


def plot_waves(
    data: pd.DataFrame,
    timeframe: str,
    wave_points: Dict[str, List[Tuple[int, float]]],
    output_dir: Optional[str] = None,
) -> None:
    """Plot price data with wave annotations.

    Args:
        data: DataFrame with OHLCV price data
        timeframe: Timeframe label
        wave_points: Dictionary with wave points from ElliottWaveAnalyzer
    """
    plt.figure(figsize=(12, 8))

    # Plot price data
    plt.plot(data.index, data["close"], color="black", linewidth=1, label="Price")

    # Colors for different wave types
    impulse_colors = ["blue", "red", "green", "orange", "purple"]
    corrective_colors = ["brown", "teal", "pink"]

    # Plot wave points
    for label, points in wave_points.items():
        parts = label.split("_")

        # Skip if not enough parts
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

        # Get x and y coordinates for this wave
        x = [data.index[idx] for idx, _ in points]
        y = [price for _, price in points]

        # Plot points
        plt.scatter(
            x, y, color=color, s=50, label=f"{pattern_type}_{wave_num}_{point_type}"
        )

        # Label points
        for i, (idx, price) in enumerate(points):
            plt.annotate(
                f"{wave_num}",
                (data.index[idx], price),
                xytext=(5, 5),
                textcoords="offset points",
                color=color,
                fontweight="bold",
            )

    plt.title(f"Elliott Wave Analysis - {timeframe.capitalize()} Timeframe")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.grid(True)
    plt.tight_layout()
    plt.legend(loc="upper left")

    # Save or show plot
    if output_dir:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Save plot
        output_file = os.path.join(output_dir, f"wave_analysis_{timeframe}.png")
        plt.savefig(output_file)
        logger.info(f"Plot saved to {output_file}")
        plt.close()
    else:
        # Show plot
        plt.show()


def main():
    """Main function to run the fractal degree analysis example."""
    logger.info("Starting Fractal Degree Analysis Example")

    # Check if this is a test run
    import sys

    is_test = "--test" in sys.argv
    output_dir = "./output/fractal" if is_test else None

    # Generate synthetic data for multiple timeframes
    logger.info("Generating synthetic multi-timeframe data")
    data_dict = create_synthetic_multi_timeframe_data()
    logger.info(f"Created data for {len(data_dict)} timeframes")

    for tf, df in data_dict.items():
        logger.info(f"  - {tf}: {len(df)} bars from {df.index[0]} to {df.index[-1]}")

    # Analyze data
    logger.info("Analyzing multi-timeframe data")
    analysis_results = analyze_multi_timeframe_data(data_dict)

    # Plot waves for each timeframe
    for timeframe, result in analysis_results["results"].items():
        logger.info(f"Plotting {timeframe} timeframe")
        plot_waves(
            data_dict[timeframe],
            timeframe,
            result["wave_points"],
            output_dir=output_dir,
        )

    logger.info("Fractal Degree Analysis Example Complete")


if __name__ == "__main__":
    main()
