#!/usr/bin/env python
"""Compare different Elliott Wave implementation approaches."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import time
from datetime import datetime

import numpy as np
import pandas as pd

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from scripts.elliott_wave_llm_enhanced import run_llm_enhanced_analysis
from scripts.elliott_wave_optimal_hybrid import OptimalElliottWaveSystem


def compare_approaches():
    """Compare text-only vs visual hybrid Elliott Wave approaches."""

    print("=" * 80)
    print("ELLIOTT WAVE APPROACH COMPARISON")
    print("=" * 80)

    # Load test data
    symbol = "GBPUSD"
    df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")

    # Test on multiple periods
    test_periods = [
        ("2024-01-01", "2024-01-31", "January"),
        ("2024-03-01", "2024-03-31", "March"),
        ("2024-06-01", "2024-06-30", "June"),
    ]

    results = []

    for start, end, period_name in test_periods:
        test_data = df[start:end]
        print(f"\n{'='*60}")
        print(f"Testing Period: {period_name} 2024")
        print(f"Bars: {len(test_data)}")
        print(
            f"Price Range: {test_data['low'].min():.5f} - {test_data['high'].max():.5f}"
        )
        print(f"{'='*60}")

        period_results = {
            "period": period_name,
            "bars": len(test_data),
            "approaches": {},
        }

        # 1. Basic Algorithmic Approach
        print("\n1. BASIC ALGORITHMIC APPROACH")
        start_time = time.time()

        analyzer = ElliottWaveAnalyzer()
        algo_result = analyzer.analyze(test_data)

        algo_time = time.time() - start_time

        algo_confidence = 0.0
        algo_pattern = None
        if algo_result and algo_result.waves:
            algo_pattern = algo_result.waves[0]
            algo_confidence = algo_pattern.confidence

        print(f"   Time: {algo_time:.2f}s")
        print(f"   Patterns found: {len(algo_result.waves) if algo_result else 0}")
        print(f"   Best confidence: {algo_confidence:.2%}")

        period_results["approaches"]["algorithmic"] = {
            "time": algo_time,
            "patterns": len(algo_result.waves) if algo_result else 0,
            "confidence": algo_confidence,
            "signal": (
                "LONG"
                if algo_confidence > 0.6
                and algo_pattern
                and algo_pattern.wave_type.value == "impulse"
                else "HOLD"
            ),
        }

        # 2. Text-Only LLM Enhanced
        print("\n2. TEXT-ONLY LLM ENHANCED")
        start_time = time.time()

        try:
            llm_result = run_llm_enhanced_analysis(test_data, symbol)
            llm_time = time.time() - start_time

            # Extract signal from LLM response
            llm_signal = "HOLD"
            if "bullish" in llm_result.lower() or "long" in llm_result.lower():
                llm_signal = "LONG"
            elif "bearish" in llm_result.lower() or "short" in llm_result.lower():
                llm_signal = "SHORT"

            print(f"   Time: {llm_time:.2f}s")
            print(f"   Signal: {llm_signal}")
            print(f"   Response length: {len(llm_result)} chars")

            period_results["approaches"]["text_llm"] = {
                "time": llm_time,
                "signal": llm_signal,
                "response_length": len(llm_result),
            }

        except Exception as e:
            print(f"   Error: {e}")
            period_results["approaches"]["text_llm"] = {
                "time": 0,
                "signal": "ERROR",
                "error": str(e),
            }

        # 3. Visual Hybrid Approach
        print("\n3. VISUAL HYBRID APPROACH")
        start_time = time.time()

        try:
            hybrid_system = OptimalElliottWaveSystem()
            hybrid_result = hybrid_system.analyze_with_optimal_approach(
                test_data, symbol
            )
            hybrid_time = time.time() - start_time

            decision = hybrid_result.get("trading_decision", {})

            print(f"   Time: {hybrid_time:.2f}s")
            print(f"   Signal: {decision.get('action', 'HOLD')}")
            print(f"   Confidence: {decision.get('confidence', 0)*100:.1f}%")
            if decision.get("risk_reward"):
                print(f"   Risk/Reward: 1:{decision['risk_reward']:.1f}")

            period_results["approaches"]["visual_hybrid"] = {
                "time": hybrid_time,
                "signal": decision.get("action", "HOLD"),
                "confidence": decision.get("confidence", 0),
                "risk_reward": decision.get("risk_reward", 0),
            }

        except Exception as e:
            print(f"   Error: {e}")
            period_results["approaches"]["visual_hybrid"] = {
                "time": 0,
                "signal": "ERROR",
                "error": str(e),
            }

        results.append(period_results)

    # Summary Analysis
    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)

    # Calculate averages
    avg_times = {"algorithmic": [], "text_llm": [], "visual_hybrid": []}
    signal_counts = {
        "algorithmic": {"LONG": 0, "SHORT": 0, "HOLD": 0},
        "text_llm": {"LONG": 0, "SHORT": 0, "HOLD": 0},
        "visual_hybrid": {"LONG": 0, "SHORT": 0, "HOLD": 0},
    }

    for result in results:
        for approach, data in result["approaches"].items():
            if "time" in data and data["time"] > 0:
                avg_times[approach].append(data["time"])
            if "signal" in data and data["signal"] in ["LONG", "SHORT", "HOLD"]:
                signal_counts[approach][data["signal"]] += 1

    print("\nAverage Processing Time:")
    for approach, times in avg_times.items():
        if times:
            print(f"  {approach:20s}: {np.mean(times):6.2f}s")

    print("\nSignal Distribution:")
    for approach, signals in signal_counts.items():
        total = sum(signals.values())
        if total > 0:
            print(f"\n  {approach}:")
            for signal, count in signals.items():
                print(f"    {signal:5s}: {count}/{total} ({count/total*100:.0f}%)")

    # Detailed Comparison
    print("\n" + "=" * 80)
    print("APPROACH COMPARISON")
    print("=" * 80)

    print("\n1. BASIC ALGORITHMIC")
    print("   Pros:")
    print("   - Fastest processing (sub-second)")
    print("   - No API costs")
    print("   - Deterministic results")
    print("   - Good for initial screening")
    print("   Cons:")
    print("   - Limited pattern recognition")
    print("   - May miss complex patterns")
    print("   - No market context consideration")

    print("\n2. TEXT-ONLY LLM ENHANCED")
    print("   Pros:")
    print("   - Better pattern interpretation")
    print("   - Can consider market context")
    print("   - Provides reasoning")
    print("   Cons:")
    print("   - Limited by text description")
    print("   - May miss visual patterns")
    print("   - Higher API costs")

    print("\n3. VISUAL HYBRID (OPTIMAL)")
    print("   Pros:")
    print("   - Best pattern recognition")
    print("   - Combines algorithmic precision with visual analysis")
    print("   - Can spot patterns algorithms miss")
    print("   - Professional-grade analysis")
    print("   - Clear visual confirmation")
    print("   Cons:")
    print("   - Highest complexity")
    print("   - Requires chart generation")
    print("   - Highest processing time")

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    print("\n1. For High-Frequency Trading:")
    print("   Use algorithmic approach with tight filters")

    print("\n2. For Swing Trading:")
    print("   Use visual hybrid for entry/exit confirmation")

    print("\n3. For Position Trading:")
    print("   Always use visual hybrid for major decisions")

    print("\n4. Optimal Workflow:")
    print("   a) Algorithmic scan for potential setups")
    print("   b) Text LLM for quick validation")
    print("   c) Visual hybrid for final confirmation")
    print("   d) Risk management based on hybrid analysis")

    # Save results
    output_file = (
        f"output/elliott_wave_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    Path("output").mkdir(exist_ok=True)

    with open(output_file, "w") as f:
        f.write("Elliott Wave Approach Comparison Results\n")
        f.write("=" * 60 + "\n\n")

        for result in results:
            f.write(f"Period: {result['period']}\n")
            f.write(f"Bars: {result['bars']}\n")
            for approach, data in result["approaches"].items():
                f.write(f"\n{approach}:\n")
                for key, value in data.items():
                    f.write(f"  {key}: {value}\n")
            f.write("\n" + "-" * 40 + "\n")

    print(f"\n✅ Comparison results saved to: {output_file}")


if __name__ == "__main__":
    compare_approaches()
