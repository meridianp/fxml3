#!/usr/bin/env python
"""Enhanced Elliott Wave analysis with visual charts and Claude Opus 4."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import warnings
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from fxml4.llm_integration.llm_client import LLMClient
from fxml4.wave_analysis.chart_generator import ElliottWaveChartGenerator
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.fibonacci import FibonacciCalculator


class VisualElliottWaveAnalyzer:
    """Elliott Wave analyzer with visual chart generation and LLM analysis."""

    def __init__(self):
        # Initialize components
        self.llm_client = LLMClient(provider="anthropic")
        self.wave_analyzer = ElliottWaveAnalyzer()
        self.fib_calculator = FibonacciCalculator()
        self.chart_generator = ElliottWaveChartGenerator()

        # Analysis cache
        self.analysis_cache = {}

    def analyze_complete(
        self, price_data: pd.DataFrame, symbol: str = "GBPUSD"
    ) -> dict:
        """Complete Elliott Wave analysis with visual and algorithmic components."""

        print(f"\n{'='*60}")
        print(f"Elliott Wave Analysis for {symbol}")
        print(f"{'='*60}")

        # Step 1: Algorithmic wave detection
        print("\n1. Running algorithmic wave detection...")
        algo_analysis = self._run_algorithmic_analysis(price_data)

        # Step 2: Generate visual chart
        print("\n2. Generating annotated chart...")
        chart_fig, chart_base64 = self._generate_visual_chart(
            price_data, algo_analysis["patterns"]
        )

        # Step 3: LLM analysis with visual context
        print("\n3. Getting Claude Opus 4 analysis...")
        llm_analysis = self._get_llm_visual_analysis(
            price_data, algo_analysis, chart_base64, symbol
        )

        # Step 4: Synthesize trading decision
        print("\n4. Synthesizing trading decision...")
        trading_decision = self._create_trading_decision(
            algo_analysis, llm_analysis, price_data
        )

        # Save chart
        chart_path = f"output/elliott_wave_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        Path("output").mkdir(exist_ok=True)
        chart_fig.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close(chart_fig)

        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "current_price": float(price_data["close"].iloc[-1]),
            "algorithmic_analysis": algo_analysis,
            "llm_analysis": llm_analysis,
            "trading_decision": trading_decision,
            "chart_path": chart_path,
            "chart_base64": chart_base64,
        }

    def _run_algorithmic_analysis(self, price_data: pd.DataFrame) -> dict:
        """Run mathematical Elliott Wave analysis."""

        # Detect peaks and troughs
        extremes_df = self.wave_analyzer.detect_peaks_and_troughs(price_data)

        # Compute waves
        waves = self.wave_analyzer.compute_waves(extremes_df)

        # Find patterns
        impulse_patterns = self.wave_analyzer.find_impulse_waves(waves)
        corrective_patterns = self.wave_analyzer.find_corrective_waves(waves)

        # Calculate Fibonacci levels
        swing_high = price_data["high"].tail(50).max()
        swing_low = price_data["low"].tail(50).min()
        fib_levels = self.fib_calculator.calculate_retracement_levels(
            swing_high, swing_low
        )

        # Find best pattern
        all_patterns = impulse_patterns + corrective_patterns
        best_pattern = (
            max(all_patterns, key=lambda x: x["confidence"]) if all_patterns else None
        )

        return {
            "waves": waves,
            "patterns": all_patterns,
            "best_pattern": best_pattern,
            "fibonacci_levels": fib_levels,
            "pattern_count": {
                "impulse": len(impulse_patterns),
                "corrective": len(corrective_patterns),
            },
        }

    def _generate_visual_chart(self, price_data: pd.DataFrame, patterns: list) -> tuple:
        """Generate annotated Elliott Wave chart."""

        # Prepare Fibonacci levels
        swing_high = price_data["high"].tail(50).max()
        swing_low = price_data["low"].tail(50).min()
        fib_levels = self.fib_calculator.calculate_retracement_levels(
            swing_high, swing_low
        )

        # Format Fibonacci levels for display
        fib_display = {f"{float(k)*100:.1f}%": v for k, v in fib_levels.items()}

        # Generate chart
        fig, base64_img = self.chart_generator.generate_elliott_wave_chart(
            price_data.tail(100),  # Last 100 bars
            patterns[:3],  # Top 3 patterns
            fibonacci_levels=fib_display,
            indicators=(
                ["volume", "rsi"] if "rsi_14" in price_data.columns else ["volume"]
            ),
            title=f"Elliott Wave Analysis - {price_data.index[-1].strftime('%Y-%m-%d %H:%M')}",
        )

        return fig, base64_img

    def _get_llm_visual_analysis(
        self,
        price_data: pd.DataFrame,
        algo_analysis: dict,
        chart_base64: str,
        symbol: str,
    ) -> dict:
        """Get LLM analysis with visual context."""

        # Prepare algorithmic findings summary
        algo_summary = self._format_algo_findings(algo_analysis)

        # Current market data
        current_price = price_data["close"].iloc[-1]
        price_change = price_data["close"].pct_change().iloc[-1] * 100

        prompt = f"""You are an expert CMT (Chartered Market Technician) analyzing a {symbol} Elliott Wave chart.

ALGORITHMIC FINDINGS:
{algo_summary}

CURRENT MARKET DATA:
- Price: {current_price:.5f} ({price_change:+.2f}% change)
- 20-bar High: {price_data['high'].tail(20).max():.5f}
- 20-bar Low: {price_data['low'].tail(20).min():.5f}
- RSI(14): {f"{price_data['rsi_14'].iloc[-1]:.1f}" if 'rsi_14' in price_data and not price_data['rsi_14'].isna().iloc[-1] else 'N/A'}
- ATR(14): {f"{price_data['atr_14'].iloc[-1]:.5f}" if 'atr_14' in price_data and not price_data['atr_14'].isna().iloc[-1] else 'N/A'}

Analyze the chart (which shows candlesticks, wave labels, Fibonacci levels, and indicators) and provide:

1. WAVE COUNT VALIDATION:
   - Is the algorithmic count correct? If not, what's the proper count?
   - Current wave position (e.g., "Wave 3 of intermediate degree")
   - Pattern quality (1-10 scale)

2. KEY OBSERVATIONS:
   - Any patterns the algorithm missed
   - Confluence of technical factors
   - Market structure insights

3. TRADING SETUP:
   - Direction: LONG/SHORT/NEUTRAL
   - Entry: Specific price level
   - Stop Loss: Wave invalidation point
   - Targets: Based on wave projections (T1, T2, T3)
   - Setup confidence: 0-100%

4. RISK FACTORS:
   - What could invalidate this analysis?
   - Alternative scenarios

Be precise with price levels and focus on actionable insights."""

        # Since we can't send actual images yet, include chart description
        chart_description = self._create_chart_description(price_data, algo_analysis)

        response = self.llm_client.generate_text(
            prompt=prompt + f"\n\nCHART DESCRIPTION:\n{chart_description}",
            system_prompt="""You are a professional Elliott Wave analyst with 20+ years experience.
            Provide technically accurate analysis following Elliott Wave International standards.
            Be specific with wave degrees and price targets.""",
            temperature=0.2,
            max_tokens=800,
        )

        # Parse the response
        return self._parse_llm_response(response)

    def _format_algo_findings(self, algo_analysis: dict) -> str:
        """Format algorithmic findings for LLM."""

        lines = []

        # Pattern summary
        if algo_analysis["best_pattern"]:
            p = algo_analysis["best_pattern"]
            lines.append(
                f"Best Pattern: {p['pattern_type'].upper()} (confidence: {p['confidence']:.0%})"
            )

            # Wave details
            if "waves" in p:
                wave_sizes = p.get("wave_sizes", [])
                if wave_sizes:
                    lines.append(
                        f"Wave sizes: {', '.join([f'{s:.5f}' for s in wave_sizes[:5]])}"
                    )

        # Pattern counts
        lines.append(
            f"Patterns found: {algo_analysis['pattern_count']['impulse']} impulse, "
            f"{algo_analysis['pattern_count']['corrective']} corrective"
        )

        # Fibonacci levels
        if algo_analysis["fibonacci_levels"]:
            lines.append("\nKey Fibonacci levels:")
            for ratio, price in algo_analysis["fibonacci_levels"].items():
                lines.append(f"  {ratio}: {price:.5f}")

        return "\n".join(lines)

    def _create_chart_description(
        self, price_data: pd.DataFrame, algo_analysis: dict
    ) -> str:
        """Create detailed chart description for LLM."""

        desc = []

        # Price action
        desc.append(f"Chart shows {len(price_data)} bars of price action")

        # Trend description
        sma20 = price_data.get("sma_20", price_data["close"].rolling(20).mean()).iloc[
            -1
        ]
        sma50 = price_data.get("sma_50", price_data["close"].rolling(50).mean()).iloc[
            -1
        ]
        current = price_data["close"].iloc[-1]

        if current > sma20 > sma50:
            desc.append("Price in strong uptrend (above 20 & 50 SMA)")
        elif current < sma20 < sma50:
            desc.append("Price in strong downtrend (below 20 & 50 SMA)")
        else:
            desc.append("Price in consolidation")

        # Wave annotations
        if algo_analysis["patterns"]:
            desc.append(f"\nWave labels visible on chart:")
            for p in algo_analysis["patterns"][:2]:
                if p["pattern_type"] == "impulse":
                    desc.append(
                        "- Blue lines marking 5-wave impulse pattern (labeled 1-2-3-4-5)"
                    )
                else:
                    desc.append(
                        "- Orange lines marking 3-wave corrective pattern (labeled A-B-C)"
                    )

        # Support/Resistance
        desc.append("\nSupport/Resistance zones marked")
        desc.append("Fibonacci retracement levels displayed (23.6%, 38.2%, 50%, 61.8%)")

        # Indicators
        if "rsi_14" in price_data:
            rsi = price_data["rsi_14"].iloc[-1]
            if rsi > 70:
                desc.append(f"RSI showing overbought conditions ({rsi:.1f})")
            elif rsi < 30:
                desc.append(f"RSI showing oversold conditions ({rsi:.1f})")
            else:
                desc.append(f"RSI neutral ({rsi:.1f})")

        return "\n".join(desc)

    def _parse_llm_response(self, response: str) -> dict:
        """Parse LLM response into structured format."""

        import re

        parsed = {
            "wave_count": {},
            "observations": [],
            "trading_setup": {},
            "risks": [],
        }

        # Extract sections
        sections = response.split("\n\n")
        current_section = None

        for section in sections:
            section_lower = section.lower()

            # Wave count validation
            if "wave count" in section_lower or "validation" in section_lower:
                parsed["wave_count"]["analysis"] = section

                # Extract pattern quality
                quality_match = re.search(
                    r"(?:quality|score).*?(\d+)", section, re.IGNORECASE
                )
                if quality_match:
                    parsed["wave_count"]["quality"] = int(quality_match.group(1))

            # Trading setup
            elif "trading" in section_lower or "setup" in section_lower:
                # Direction
                if "LONG" in section.upper():
                    parsed["trading_setup"]["direction"] = "LONG"
                elif "SHORT" in section.upper():
                    parsed["trading_setup"]["direction"] = "SHORT"
                else:
                    parsed["trading_setup"]["direction"] = "NEUTRAL"

                # Extract price levels
                prices = re.findall(r"(\d+\.\d+)", section)
                if prices:
                    parsed["trading_setup"]["levels"] = [float(p) for p in prices]

                # Confidence
                conf_match = re.search(r"(\d+)%", section)
                if conf_match:
                    parsed["trading_setup"]["confidence"] = int(conf_match.group(1))

            # Risks
            elif "risk" in section_lower or "invalidat" in section_lower:
                parsed["risks"].append(section.strip())

        return parsed

    def _create_trading_decision(
        self, algo_analysis: dict, llm_analysis: dict, price_data: pd.DataFrame
    ) -> dict:
        """Create final trading decision combining all analyses."""

        decision = {
            "action": "HOLD",
            "confidence": 0.0,
            "entry": None,
            "stop_loss": None,
            "targets": [],
            "risk_reward": None,
            "reasoning": "",
        }

        # Get LLM trading setup
        setup = llm_analysis.get("trading_setup", {})

        if setup.get("direction") in ["LONG", "SHORT"]:
            decision["action"] = setup["direction"]
            decision["confidence"] = setup.get("confidence", 50) / 100.0

            # Use LLM levels if available
            levels = setup.get("levels", [])
            current_price = float(price_data["close"].iloc[-1])
            atr = price_data.get(
                "atr_14", price_data["close"].pct_change().std() * current_price
            ).iloc[-1]

            if len(levels) >= 3:
                # Assume: entry, stop, target1, target2...
                decision["entry"] = levels[0]
                decision["stop_loss"] = levels[1]
                decision["targets"] = levels[2:]
            else:
                # Fallback to algorithmic levels
                if decision["action"] == "LONG":
                    decision["entry"] = current_price
                    decision["stop_loss"] = current_price - 2 * atr

                    # Use Fibonacci extensions for targets
                    if algo_analysis["fibonacci_levels"]:
                        fib_levels = algo_analysis["fibonacci_levels"]
                        decision["targets"] = [
                            current_price
                            + (current_price - decision["stop_loss"]) * 1.618,
                            current_price
                            + (current_price - decision["stop_loss"]) * 2.618,
                        ]
                    else:
                        decision["targets"] = [
                            current_price + 2 * atr,
                            current_price + 4 * atr,
                        ]
                else:  # SHORT
                    decision["entry"] = current_price
                    decision["stop_loss"] = current_price + 2 * atr
                    decision["targets"] = [
                        current_price - 2 * atr,
                        current_price - 4 * atr,
                    ]

            # Calculate risk/reward
            if decision["stop_loss"] and decision["targets"]:
                risk = abs(decision["entry"] - decision["stop_loss"])
                reward = abs(decision["targets"][0] - decision["entry"])
                decision["risk_reward"] = reward / risk if risk > 0 else 0

            # Combine reasoning
            algo_conf = (
                algo_analysis["best_pattern"]["confidence"]
                if algo_analysis["best_pattern"]
                else 0
            )
            wave_quality = llm_analysis.get("wave_count", {}).get("quality", 5)

            decision["reasoning"] = (
                f"Algorithmic confidence: {algo_conf:.0%}, "
                f"Wave quality: {wave_quality}/10, "
                f"LLM confidence: {setup.get('confidence', 0)}%"
            )

        return decision


def test_visual_elliott_wave():
    """Test the visual Elliott Wave implementation."""

    print("=" * 80)
    print("VISUAL ELLIOTT WAVE ANALYSIS TEST")
    print("=" * 80)

    # Load data
    symbol = "GBPUSD"
    df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")

    # Test on recent data
    test_data = df["2024-06-01":"2024-06-30"]

    print(f"\nAnalyzing {symbol}")
    print(f"Period: {test_data.index[0]} to {test_data.index[-1]}")
    print(f"Bars: {len(test_data)}")

    # Run analysis
    analyzer = VisualElliottWaveAnalyzer()
    results = analyzer.analyze_complete(test_data, symbol)

    # Display results
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)

    # Algorithmic findings
    algo = results["algorithmic_analysis"]
    print(f"\n1. ALGORITHMIC ANALYSIS:")
    print(f"   Patterns found: {len(algo['patterns'])}")
    if algo["best_pattern"]:
        print(
            f"   Best pattern: {algo['best_pattern']['pattern_type']} "
            f"(confidence: {algo['best_pattern']['confidence']:.0%})"
        )

    # LLM analysis
    llm = results["llm_analysis"]
    print(f"\n2. LLM ANALYSIS (Claude Opus 4):")
    if llm.get("wave_count"):
        print(f"   Wave quality: {llm['wave_count'].get('quality', 'N/A')}/10")
    if llm.get("trading_setup"):
        print(f"   Trading direction: {llm['trading_setup'].get('direction', 'N/A')}")
        print(f"   Setup confidence: {llm['trading_setup'].get('confidence', 0)}%")

    # Trading decision
    decision = results["trading_decision"]
    print(f"\n3. TRADING DECISION:")
    print(f"   Action: {decision['action']}")
    print(f"   Confidence: {decision['confidence']*100:.1f}%")

    if decision["action"] != "HOLD":
        print(f"   Entry: {decision['entry']:.5f}")
        print(f"   Stop Loss: {decision['stop_loss']:.5f}")
        print(f"   Targets: {', '.join([f'{t:.5f}' for t in decision['targets']])}")
        print(f"   Risk/Reward: 1:{decision['risk_reward']:.1f}")
        print(f"   Reasoning: {decision['reasoning']}")

    print(f"\n4. CHART SAVED TO: {results['chart_path']}")

    # Save complete results
    output_file = f"output/elliott_wave_analysis_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        # Remove base64 image from saved JSON (too large)
        save_results = results.copy()
        save_results.pop("chart_base64", None)
        json.dump(save_results, f, indent=2, default=str)

    print(f"\n5. ANALYSIS SAVED TO: {output_file}")

    return results


def compare_approaches():
    """Compare text-only vs visual approaches."""

    print("\n" + "=" * 80)
    print("COMPARING ELLIOTT WAVE APPROACHES")
    print("=" * 80)

    # This would run both approaches and compare results
    # For now, we'll summarize the advantages

    print("\nTEXT-ONLY APPROACH:")
    print("- Pros: Fast, low API cost, simple implementation")
    print("- Cons: Limited pattern recognition, no visual context")
    print("- Best for: Quick screening, simple patterns")

    print("\nVISUAL HYBRID APPROACH:")
    print("- Pros: Superior pattern recognition, full context, professional analysis")
    print("- Cons: Higher complexity, requires chart generation")
    print("- Best for: Complex patterns, high-confidence trades")

    print("\nRECOMMENDATION:")
    print("Use visual approach for:")
    print("- Final trade confirmation")
    print("- Complex corrective patterns")
    print("- Multi-timeframe analysis")
    print("- When algorithmic confidence is 50-80%")


if __name__ == "__main__":
    # Run the test
    results = test_visual_elliott_wave()

    # Show comparison
    compare_approaches()

    print("\n✅ Visual Elliott Wave implementation complete!")
