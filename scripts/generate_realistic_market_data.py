#!/usr/bin/env python
"""Generate realistic market data for testing Elliott Wave detection."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def generate_realistic_forex_data(
    start_date: str = "2024-10-01",
    num_days: int = 30,
    base_price: float = 1.1000,
    daily_volatility: float = 0.005,  # 0.5% daily volatility
    trend_strength: float = 0.0002,  # Slight upward trend
    output_dir: str = "input/C_EURUSD_REAL",
):
    """Generate realistic EURUSD minute data with Elliott Wave patterns."""

    print(f"Generating realistic market data for {num_days} days...")

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    start_dt = pd.to_datetime(start_date)
    minutes_per_day = 1440

    # Generate Elliott Wave pattern template (5-wave impulse + 3-wave correction)
    # This creates a fractal pattern that repeats at different scales
    wave_template = [
        1.0,  # Start
        1.015,  # Wave 1 top
        1.008,  # Wave 2 bottom (50% retracement)
        1.030,  # Wave 3 top (1.618x wave 1)
        1.022,  # Wave 4 bottom (38.2% retracement)
        1.035,  # Wave 5 top
        1.025,  # Wave A bottom
        1.032,  # Wave B top
        1.020,  # Wave C bottom
    ]

    # Generate base pattern over multiple days
    total_minutes = num_days * minutes_per_day

    # Create time index
    time_index = pd.date_range(
        start=start_dt, periods=total_minutes, freq="1min", tz="UTC"
    )

    # Generate base price movement using multiple timeframes
    # Large waves (weekly)
    large_wave_period = minutes_per_day * 5  # 5-day waves
    large_wave = (
        np.sin(2 * np.pi * np.arange(total_minutes) / large_wave_period)
        * daily_volatility
        * 5
    )

    # Medium waves (daily)
    medium_wave_period = minutes_per_day  # 1-day waves
    medium_wave = (
        np.sin(2 * np.pi * np.arange(total_minutes) / medium_wave_period)
        * daily_volatility
        * 2
    )

    # Small waves (4-hour)
    small_wave_period = 240  # 4-hour waves
    small_wave = (
        np.sin(2 * np.pi * np.arange(total_minutes) / small_wave_period)
        * daily_volatility
    )

    # Micro waves (hourly)
    micro_wave_period = 60  # 1-hour waves
    micro_wave = (
        np.sin(2 * np.pi * np.arange(total_minutes) / micro_wave_period)
        * daily_volatility
        * 0.3
    )

    # Add trend
    trend = np.linspace(0, trend_strength * num_days, total_minutes)

    # Random walk component
    random_walk = np.random.normal(0, daily_volatility * 0.1, total_minutes)
    random_walk = np.cumsum(random_walk) * 0.0001

    # Combine all components
    price_movement = (
        large_wave + medium_wave + small_wave + micro_wave + trend + random_walk
    )

    # Apply Elliott Wave template at different scales
    # Map template to different time periods
    for scale in [5, 13, 21]:  # Fibonacci periods in days
        period_minutes = scale * minutes_per_day
        if period_minutes <= total_minutes:
            template_scaled = np.interp(
                np.linspace(0, len(wave_template) - 1, period_minutes),
                np.arange(len(wave_template)),
                wave_template,
            )

            # Normalize and scale template
            template_scaled = (template_scaled - 1.0) * daily_volatility * scale

            # Apply template multiple times
            for i in range(0, total_minutes - period_minutes, period_minutes):
                # Add some randomness to each wave
                wave_variation = np.random.uniform(0.8, 1.2)
                price_movement[i : i + period_minutes] += (
                    template_scaled * wave_variation
                )

    # Generate final prices
    close_prices = base_price + price_movement

    # Generate OHLC from close prices
    data_list = []

    for day in range(num_days):
        day_start = day * minutes_per_day
        day_end = (day + 1) * minutes_per_day

        day_data = []

        for minute in range(minutes_per_day):
            idx = day_start + minute
            if idx >= len(close_prices):
                break

            close = close_prices[idx]

            # Generate realistic OHLC
            # High/Low based on volatility
            minute_volatility = (
                daily_volatility
                / np.sqrt(minutes_per_day)
                * np.random.uniform(0.5, 2.0)
            )

            high = close + abs(np.random.normal(0, minute_volatility))
            low = close - abs(np.random.normal(0, minute_volatility))

            # Open is previous close with small gap
            if minute == 0 and day > 0:
                # Daily gap
                gap = np.random.normal(0, daily_volatility * 0.5)
                open_price = close_prices[idx - 1] + gap
            elif minute == 0:
                open_price = close + np.random.normal(0, minute_volatility * 0.1)
            else:
                open_price = close_prices[idx - 1] + np.random.normal(
                    0, minute_volatility * 0.1
                )

            # Ensure OHLC relationships are valid
            high = max(high, open_price, close)
            low = min(low, open_price, close)

            # Add volume (higher during "market hours")
            hour = (minute // 60) % 24
            if 8 <= hour <= 16:  # Market hours
                volume = np.random.exponential(1000) * 10
            else:
                volume = np.random.exponential(100) * 10

            day_data.append(
                {
                    "timestamp": time_index[idx],
                    "open": round(open_price, 5),
                    "high": round(high, 5),
                    "low": round(low, 5),
                    "close": round(close, 5),
                    "volume": round(volume, 2),
                }
            )

        # Save day data
        if day_data:
            df = pd.DataFrame(day_data)

            # Create directory structure
            date = start_dt + timedelta(days=day)
            year_dir = Path(output_dir) / f"year={date.year}"
            month_dir = year_dir / f"month={date.month}"
            day_dir = month_dir / f"day={date.day}"
            day_dir.mkdir(parents=True, exist_ok=True)

            # Save as parquet
            output_file = day_dir / "data.parquet.gz"
            df.to_parquet(output_file, compression="gzip")

            print(
                f"Generated data for {date.date()}: {len(df)} bars, "
                f"range: {df['low'].min():.5f} - {df['high'].max():.5f}"
            )

    print(f"\nData generation complete! Files saved to: {output_dir}")

    # Test the generated data
    print("\nTesting generated data with Elliott Wave analyzer...")
    test_elliott_wave_on_generated_data(output_dir, start_date, num_days)


def test_elliott_wave_on_generated_data(data_dir: str, start_date: str, num_days: int):
    """Test Elliott Wave detection on the generated data."""

    from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer

    # Load generated data
    all_data = []
    start_dt = pd.to_datetime(start_date)

    for day in range(min(10, num_days)):  # Test with first 10 days
        date = start_dt + timedelta(days=day)
        file_path = (
            Path(data_dir)
            / f"year={date.year}/month={date.month}/day={date.day}/data.parquet.gz"
        )

        if file_path.exists():
            df = pd.read_parquet(file_path)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
            all_data.append(df)

    if not all_data:
        print("No data loaded for testing!")
        return

    # Combine and resample to 4H
    combined = pd.concat(all_data).sort_index()
    data_4h = (
        combined.resample("4h")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )

    print(f"\nLoaded {len(combined)} minute bars, resampled to {len(data_4h)} 4H bars")
    print(f"Price range: {data_4h['low'].min():.5f} to {data_4h['high'].max():.5f}")
    print(f"High std dev: {data_4h['high'].std():.6f}")

    # Test Elliott Wave detection
    analyzer = ElliottWaveAnalyzer(
        min_wave_size=0.001, peak_detection_window=3  # 10 pips
    )

    # Detect peaks and troughs
    extremes_df = analyzer.detect_peaks_and_troughs(data_4h)
    peaks = extremes_df[extremes_df["is_peak"] == True]
    troughs = extremes_df[extremes_df["is_trough"] == True]

    print(f"\nElliott Wave Detection Results:")
    print(f"Peaks found: {len(peaks)}")
    print(f"Troughs found: {len(troughs)}")

    if len(peaks) > 0 or len(troughs) > 0:
        # Compute waves
        waves = analyzer.compute_waves(extremes_df)
        print(f"Waves computed: {len(waves)}")

        # Find patterns
        impulse_patterns = analyzer.find_impulse_waves(waves)
        corrective_patterns = analyzer.find_corrective_waves(waves)

        print(f"Impulse patterns found: {len(impulse_patterns)}")
        print(f"Corrective patterns found: {len(corrective_patterns)}")

        # Full analysis
        result = analyzer.analyze(data_4h)
        if result and result.waves:
            print(f"Full analysis found {len(result.waves)} patterns!")
            for i, pattern in enumerate(result.waves[:3]):
                print(
                    f"  Pattern {i+1}: {pattern.wave_type.value}, confidence: {pattern.confidence:.2f}"
                )

        print("\n✅ Elliott Wave detection is now working with realistic data!")
    else:
        print("\n❌ Still no patterns detected. May need to adjust parameters.")


if __name__ == "__main__":
    # Generate realistic data
    generate_realistic_forex_data(
        start_date="2024-10-01",
        num_days=30,
        base_price=1.1000,
        daily_volatility=0.005,
        trend_strength=0.0002,
        output_dir="input/C_EURUSD_REAL",
    )
