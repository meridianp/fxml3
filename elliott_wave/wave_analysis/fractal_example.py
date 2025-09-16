"""Example demonstration of fractal degree handling in Elliott Wave analysis."""

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
from fxml3.wave_analysis.fractal import FractalDegreeHandler


def download_multi_timeframe_data(
    symbol: str = "EURUSD=X",
    timeframes: List[str] = ["1d", "1wk", "4h"],
    periods: List[str] = ["1y", "3y", "1mo"],
) -> Dict[str, pd.DataFrame]:
    """Download data for multiple timeframes.

    Args:
        symbol: Ticker symbol to download
        timeframes: List of timeframes to download (yahoo finance format)
        periods: Corresponding periods to download for each timeframe

    Returns:
        Dictionary mapping timeframes to DataFrames
    """
    data_dict = {}

    # Map yahoo finance intervals to our timeframe names
    interval_map = {
        "1d": "daily",
        "1wk": "weekly",
        "1h": "1h",
        "4h": "4h",
        "15m": "15m",
    }

    # Download data for each timeframe
    for tf, period in zip(timeframes, periods):
        try:
            print(f"Downloading {symbol} data for {tf} timeframe ({period})...")
            df = yf.download(symbol, interval=tf, period=period)

            # Convert to lowercase column names
            df.columns = [col.lower() for col in df.columns]

            # Map yahoo interval to our timeframe name
            timeframe_name = interval_map.get(tf, tf)

            # Store in dictionary
            data_dict[timeframe_name] = df
            print(f"Downloaded {len(df)} rows for {timeframe_name}")

        except Exception as e:
            print(f"Error downloading {tf} data: {str(e)}")

    return data_dict


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
        periods=50,
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
        periods=250,
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
        periods=1500,
        freq="4H",
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
    df = pd.DataFrame(
        {
            "open": [prices[0]] + prices[:-1],  # Shift prices by 1 for open
            "high": [p * (1 + np.random.uniform(0.001, 0.01)) for p in prices],
            "low": [p * (1 - np.random.uniform(0.001, 0.01)) for p in prices],
            "close": prices,
            "volume": np.random.randint(1000, 10000, size=len(prices)),
        },
        index=dates[: len(prices)],
    )

    return df


def analyze_multi_timeframe_data(
    data_dict: Dict[str, pd.DataFrame], output_dir: str = "./output/fractal"
) -> None:
    """Analyze multi-timeframe data and visualize the results.

    Args:
        data_dict: Dictionary mapping timeframes to DataFrames
        output_dir: Directory to save output charts
    """
    # Initialize fractal degree handler
    handler = FractalDegreeHandler(
        base_timeframe="daily", higher_degrees=1, lower_degrees=1
    )

    # Analyze all timeframes
    results = handler.analyze_timeframes(data_dict)

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Visualize each timeframe
    for timeframe, result in results.items():
        print(f"\nAnalyzing {timeframe} timeframe:")
        degree = result["degree"]
        labeled_df = result["labeled_data"]
        wave_points = result["wave_points"]

        # Show wave counts
        impulse_cols = [col for col in labeled_df.columns if col.startswith("impulse_")]
        corrective_cols = [
            col for col in labeled_df.columns if col.startswith("corrective_")
        ]

        print(f"Detected patterns in {degree} degree:")
        for col in impulse_cols:
            waves = labeled_df[labeled_df[col] > 0][col].unique()
            if len(waves) > 0:
                print(f"  - {col}: {len(waves)} waves")

        for col in corrective_cols:
            waves = labeled_df[labeled_df[col] > 0][col].unique()
            if len(waves) > 0:
                print(f"  - {col}: {len(waves)} waves")

        # Label with nested wave information
        nested_df = handler.label_nested_waves(
            labeled_df,
            timeframe=timeframe,
            show_higher_degree=True,
            show_lower_degree=True,
        )

        # Visualize each detected pattern in this timeframe
        for col in impulse_cols + corrective_cols:
            if col in labeled_df.columns:
                waves = labeled_df[labeled_df[col] > 0][col].unique()
                if len(waves) > 0:
                    # Get degree-appropriate labels
                    wave_labels = handler.get_wave_annotations(
                        timeframe=timeframe, wave_col=col, use_degree_labels=True
                    )

                    # Create chart with wave annotations
                    is_impulse = col.startswith("impulse_")
                    pattern_type = "Impulse" if is_impulse else "Corrective"

                    chart_title = (
                        f"{degree} Degree {pattern_type} Pattern - {timeframe}"
                    )

                    # Create interactive chart with wave labels
                    try:
                        # Plot wave analysis
                        fig = plot_wave_analysis(
                            nested_df, wave_col=col, title=chart_title
                        )

                        # Save to file
                        output_file = f"{output_dir}/{timeframe}_{col}.html"
                        fig.write_html(output_file)
                        print(f"Chart saved to {output_file}")
                    except Exception as e:
                        print(f"Error creating chart for {col}: {str(e)}")

    # Get the complete nested structure
    structure = handler.get_complete_wave_structure()

    # Print the nested structure
    print("\nComplete Wave Structure:")
    print_structure(structure, indent=0)


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
        print(
            f"{indent_str}[{degree}] {wave_type.capitalize()} Wave {wave_num} ({timeframe}): {start} → {end}"
        )

        # Print subwaves recursively
        if wave["subwaves"]:
            print_structure(wave["subwaves"], indent=indent + 1)


def main():
    """Run the fractal degree Elliott Wave analysis example."""
    print("Fractal Degree Elliott Wave Analysis Example")
    print("===========================================")

    # Choose data source
    use_synthetic = input("Use synthetic data? (y/n, default: y): ").lower() != "n"

    if use_synthetic:
        print("Generating synthetic multi-timeframe data...")
        data_dict = create_synthetic_multi_timeframe_data()
    else:
        # Get symbol and timeframes
        symbol = input("Enter ticker symbol (default: EURUSD=X): ") or "EURUSD=X"
        data_dict = download_multi_timeframe_data(symbol=symbol)

    # Set output path
    output_dir = "./output/fractal"

    # Run analysis
    print(
        f"Analyzing multi-timeframe data ({sum(len(df) for df in data_dict.values())} total rows)..."
    )
    analyze_multi_timeframe_data(data_dict, output_dir=output_dir)

    print("Analysis complete")


if __name__ == "__main__":
    main()
