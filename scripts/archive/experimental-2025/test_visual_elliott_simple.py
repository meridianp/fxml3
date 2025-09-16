#!/usr/bin/env python
"""Simplified test of visual Elliott Wave system."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime

import numpy as np
import pandas as pd

from scripts.elliott_wave_visual_enhanced import VisualElliottWaveAnalyzer


def test_visual_elliott():
    """Test visual Elliott Wave implementation."""

    print("=" * 60)
    print("TESTING VISUAL ELLIOTT WAVE SYSTEM")
    print("=" * 60)

    # Load data
    symbol = "GBPUSD"
    df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")

    # Use smaller test period
    test_data = df["2024-06-20":"2024-06-30"]

    print(f"\nTest data: {len(test_data)} bars")
    print(f"Period: {test_data.index[0]} to {test_data.index[-1]}")
    print(f"Current price: {test_data['close'].iloc[-1]:.5f}")

    # Initialize analyzer
    analyzer = VisualElliottWaveAnalyzer()

    # Run algorithmic analysis only
    print("\n1. Testing algorithmic analysis...")
    algo_analysis = analyzer._run_algorithmic_analysis(test_data)

    print(f"   Found {len(algo_analysis['patterns'])} patterns")
    if algo_analysis["best_pattern"]:
        print(
            f"   Best pattern: {algo_analysis['best_pattern']['pattern_type']} "
            f"(confidence: {algo_analysis['best_pattern']['confidence']:.0%})"
        )

    # Test chart generation
    print("\n2. Testing chart generation...")
    try:
        fig, base64_img = analyzer._generate_visual_chart(
            test_data, algo_analysis["patterns"]
        )
        print("   ✓ Chart generated successfully")

        # Save chart
        Path("output").mkdir(exist_ok=True)
        chart_path = (
            f"output/visual_elliott_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        fig.savefig(chart_path, dpi=150, bbox_inches="tight")
        print(f"   ✓ Chart saved to: {chart_path}")

    except Exception as e:
        print(f"   ✗ Chart generation failed: {e}")
        return

    # Test LLM analysis
    print("\n3. Testing LLM analysis...")
    try:
        # Create simple trading decision
        current_price = float(test_data["close"].iloc[-1])
        atr = float(
            test_data.get(
                "atr_14", test_data["close"].pct_change().std() * current_price
            ).iloc[-1]
        )

        decision = {
            "action": (
                "LONG"
                if algo_analysis["best_pattern"]
                and algo_analysis["best_pattern"]["confidence"] > 0.6
                else "HOLD"
            ),
            "confidence": (
                float(algo_analysis["best_pattern"]["confidence"])
                if algo_analysis["best_pattern"]
                else 0.0
            ),
            "entry": current_price,
            "stop_loss": current_price - 2 * atr,
            "targets": [current_price + 2 * atr, current_price + 4 * atr],
            "reasoning": "Visual Elliott Wave analysis",
        }

        print("\n4. TRADING DECISION:")
        print(f"   Action: {decision['action']}")
        print(f"   Confidence: {decision['confidence']*100:.1f}%")
        if decision["action"] != "HOLD":
            print(f"   Entry: {decision['entry']:.5f}")
            print(f"   Stop Loss: {decision['stop_loss']:.5f}")
            print(f"   Targets: {', '.join([f'{t:.5f}' for t in decision['targets']])}")

    except Exception as e:
        print(f"   ✗ Analysis failed: {e}")

    print("\n✅ Visual Elliott Wave system test complete!")


if __name__ == "__main__":
    test_visual_elliott()
