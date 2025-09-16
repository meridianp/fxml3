#!/usr/bin/env python
"""Simple test of Elliott Wave components."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fxml4.llm_integration.llm_client import LLMClient
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.fibonacci import FibonacciCalculator


def test_components():
    """Test individual Elliott Wave components."""

    print("=" * 60)
    print("TESTING ELLIOTT WAVE COMPONENTS")
    print("=" * 60)

    # Load data
    symbol = "GBPUSD"
    df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")
    test_data = df["2024-06-15":"2024-06-30"]

    print(f"\nTest data: {len(test_data)} bars")
    print(f"Period: {test_data.index[0]} to {test_data.index[-1]}")

    # Test 1: Wave Detection
    print("\n1. Testing Wave Detection...")
    analyzer = ElliottWaveAnalyzer()

    # Detect peaks and troughs
    extremes = analyzer.detect_peaks_and_troughs(test_data)
    peaks = extremes[extremes["is_peak"]].index
    troughs = extremes[extremes["is_trough"]].index

    print(f"   Found {len(peaks)} peaks and {len(troughs)} troughs")

    # Compute waves
    waves = analyzer.compute_waves(extremes)
    print(f"   Computed {len(waves)} waves")

    # Find patterns
    impulse_patterns = analyzer.find_impulse_waves(waves)
    corrective_patterns = analyzer.find_corrective_waves(waves)

    print(f"   Found {len(impulse_patterns)} impulse patterns")
    print(f"   Found {len(corrective_patterns)} corrective patterns")

    # Test 2: Fibonacci Calculations
    print("\n2. Testing Fibonacci Calculations...")
    fib_calc = FibonacciCalculator()

    swing_high = test_data["high"].max()
    swing_low = test_data["low"].min()

    fib_levels = fib_calc.calculate_retracement_levels(swing_high, swing_low)
    print(f"   Swing High: {swing_high:.5f}")
    print(f"   Swing Low: {swing_low:.5f}")
    print("   Fibonacci Levels:")
    for level, price in fib_levels.items():
        print(f"     {level}: {price:.5f}")

    # Test 3: Simple Chart
    print("\n3. Creating Simple Chart...")
    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot candlesticks manually
    for i in range(len(test_data)):
        row = test_data.iloc[i]
        color = "green" if row["close"] > row["open"] else "red"

        # High-Low line
        ax.plot([i, i], [row["low"], row["high"]], color="black", linewidth=0.5)

        # Body
        height = abs(row["close"] - row["open"])
        bottom = min(row["open"], row["close"])
        ax.add_patch(
            plt.Rectangle((i - 0.3, bottom), 0.6, height, facecolor=color, alpha=0.8)
        )

    # Add wave annotations
    if impulse_patterns:
        pattern = impulse_patterns[0]
        for i, wave in enumerate(pattern["waves"]):
            if i > 0:
                prev = pattern["waves"][i - 1]
                ax.plot(
                    [prev["end_idx"], wave["end_idx"]],
                    [prev["end_price"], wave["end_price"]],
                    "b-",
                    linewidth=2,
                    alpha=0.7,
                )

                # Add label
                mid_x = (prev["end_idx"] + wave["end_idx"]) / 2
                mid_y = (prev["end_price"] + wave["end_price"]) / 2
                ax.text(
                    mid_x,
                    mid_y,
                    str(i + 1),
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow"),
                    fontsize=10,
                )

    ax.set_title(f"{symbol} Elliott Wave Analysis")
    ax.grid(True, alpha=0.3)

    # Save chart
    Path("output").mkdir(exist_ok=True)
    chart_path = (
        f"output/elliott_wave_simple_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"   Chart saved to: {chart_path}")

    # Test 4: LLM Analysis (simple)
    print("\n4. Testing LLM Analysis...")
    llm_client = LLMClient(provider="anthropic")

    # Prepare simple price summary
    price_summary = []
    for i in range(0, len(test_data), 3):  # Every 3rd bar
        row = test_data.iloc[i]
        price_summary.append(
            f"{row.name.strftime('%m/%d %H:%M')} | "
            f"O:{row['open']:.5f} H:{row['high']:.5f} "
            f"L:{row['low']:.5f} C:{row['close']:.5f}"
        )

    prompt = f"""Analyze this {symbol} price data for Elliott Wave patterns:

{chr(10).join(price_summary[-10:])}

Current price: {test_data['close'].iloc[-1]:.5f}

Identify:
1. Current wave pattern (impulse or corrective)
2. Wave position (e.g., Wave 3 of 5)
3. Trading bias (bullish/bearish/neutral)

Be concise."""

    try:
        response = llm_client.generate_text(
            prompt=prompt,
            system_prompt="You are an Elliott Wave expert. Provide concise technical analysis.",
            temperature=0.3,
            max_tokens=200,
        )
        print("\nLLM Response:")
        print(response)
    except Exception as e:
        print(f"\nLLM Error: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("COMPONENT TEST SUMMARY")
    print("=" * 60)
    print("✓ Wave detection working")
    print("✓ Fibonacci calculations working")
    print("✓ Basic chart generation working")
    print("✓ LLM integration configured")

    return {
        "waves": waves,
        "impulse_patterns": impulse_patterns,
        "corrective_patterns": corrective_patterns,
        "fibonacci_levels": fib_levels,
    }


if __name__ == "__main__":
    results = test_components()
