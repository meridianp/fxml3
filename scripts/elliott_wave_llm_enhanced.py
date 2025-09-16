#!/usr/bin/env python
"""Enhanced Elliott Wave analysis using Claude for pattern validation and trading signals."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
from datetime import datetime

import numpy as np
import pandas as pd

from fxml4.llm_integration.llm_client import LLMClient
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml4.wave_analysis.fibonacci import FibonacciCalculator


class LLMEnhancedElliottWaveAnalyzer:
    """Elliott Wave analyzer enhanced with Claude's expertise."""

    def __init__(self):
        # Initialize LLM client with Claude
        # Will use LLM_MODEL from .env file (claude-opus-4-20250514)
        self.llm_client = LLMClient(
            provider="anthropic"
            # model parameter omitted to use LLM_MODEL from environment
        )

        # Initialize traditional analyzers
        self.wave_analyzer = ElliottWaveAnalyzer()
        self.fib_calculator = FibonacciCalculator()

    def analyze_with_llm(
        self, price_data: pd.DataFrame, symbol: str = "GBPUSD"
    ) -> dict:
        """Analyze price patterns using Claude's Elliott Wave expertise."""

        # Get recent price data
        recent_data = price_data.tail(50)

        # Prepare price data for Claude
        price_summary = self._prepare_price_summary(recent_data)

        # Create enhanced Elliott Wave prompt
        prompt = f"""You are an expert Elliott Wave analyst with 20+ years of experience. Analyze the following {symbol} price data and provide a detailed Elliott Wave count.

PRICE DATA (4-hour bars, most recent last):
{price_summary}

TECHNICAL CONTEXT:
- Current Price: {recent_data['close'].iloc[-1]:.5f}
- 20-bar High: {recent_data['high'].tail(20).max():.5f}
- 20-bar Low: {recent_data['low'].tail(20).min():.5f}
- ATR(14): {recent_data.get('atr_14', 0.0001):.5f}
- RSI(14): {recent_data.get('rsi_14', 50):.1f}

Please provide:

1. PRIMARY WAVE COUNT:
   - Current wave position (e.g., "Wave 3 of larger degree Wave III")
   - Wave type (Impulse/Corrective/Diagonal)
   - Confidence level (0-100%)

2. KEY FIBONACCI LEVELS:
   - Support levels with wave labels
   - Resistance levels with wave labels
   - Critical invalidation level

3. TRADING SIGNAL:
   - Direction: LONG/SHORT/NEUTRAL
   - Entry zone (if applicable)
   - Stop loss level with rationale
   - Target levels (T1, T2, T3) with wave-based reasoning
   - Signal confidence (0-100%)

4. ALTERNATE COUNT (if confidence < 80%):
   - Brief description
   - Key difference from primary count

5. MARKET PSYCHOLOGY:
   - Current sentiment based on wave position
   - Expected sentiment shift at next wave transition

Format your response as a structured analysis. Be specific with price levels and wave labels."""

        system_prompt = """You are a professional Elliott Wave analyst. Your analysis should be:
- Technically precise with proper wave notation
- Based on Elliott Wave rules (wave 2 never retraces >100% of wave 1, wave 3 is never the shortest, wave 4 doesn't overlap wave 1 territory)
- Include Fibonacci relationships between waves
- Consider both impulse (5-wave) and corrective (3-wave) patterns
- Account for wave degree (Primary, Intermediate, Minor, Minute, Minuette)
- Practical for trading decisions"""

        # Get Claude's analysis
        analysis = self.llm_client.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for more consistent technical analysis
            max_tokens=1500,
        )

        # Parse the LLM response
        parsed_analysis = self._parse_llm_analysis(analysis)

        # Combine with algorithmic wave detection for validation
        algo_waves = self.wave_analyzer.detect_waves(recent_data)

        # Enhance the analysis with both approaches
        return {
            "llm_analysis": parsed_analysis,
            "raw_llm_response": analysis,
            "algorithmic_waves": algo_waves,
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "current_price": float(recent_data["close"].iloc[-1]),
        }

    def _prepare_price_summary(self, data: pd.DataFrame) -> str:
        """Prepare price data in a format optimal for LLM analysis."""
        summary_lines = []

        # Include every 2nd bar to reduce noise but maintain pattern visibility
        step = 2
        for i in range(0, len(data), step):
            row = data.iloc[i]
            if hasattr(data.index[i], "strftime"):
                date_str = data.index[i].strftime("%Y-%m-%d %H:%M")
            else:
                date_str = str(data.index[i])

            summary_lines.append(
                f"{date_str} | O: {row['open']:.5f} H: {row['high']:.5f} "
                f"L: {row['low']:.5f} C: {row['close']:.5f}"
            )

        return "\n".join(summary_lines[-25:])  # Last 25 summary lines

    def _parse_llm_analysis(self, analysis: str) -> dict:
        """Parse Claude's analysis into structured data."""
        parsed = {
            "wave_count": {},
            "fibonacci_levels": {},
            "trading_signal": {},
            "alternate_count": None,
            "market_psychology": {},
        }

        try:
            # Extract sections
            sections = analysis.split("\n\n")
            current_section = None

            for section in sections:
                section_lower = section.lower()

                if (
                    "primary wave count" in section_lower
                    or "wave count:" in section_lower
                ):
                    # Parse wave count
                    lines = section.split("\n")
                    for line in lines:
                        if "wave position" in line.lower() or "current" in line.lower():
                            parsed["wave_count"]["position"] = line.split(":", 1)[
                                -1
                            ].strip()
                        elif "type" in line.lower():
                            parsed["wave_count"]["type"] = line.split(":", 1)[
                                -1
                            ].strip()
                        elif "confidence" in line.lower():
                            conf_text = line.split(":", 1)[-1].strip()
                            # Extract percentage
                            import re

                            conf_match = re.search(r"(\d+)%?", conf_text)
                            if conf_match:
                                parsed["wave_count"]["confidence"] = int(
                                    conf_match.group(1)
                                )

                elif "fibonacci" in section_lower or "key levels" in section_lower:
                    # Parse Fibonacci levels
                    lines = section.split("\n")
                    for line in lines:
                        # Look for price levels
                        price_match = re.search(r"(\d+\.\d+)", line)
                        if price_match and any(
                            word in line.lower()
                            for word in ["support", "resistance", "invalidation"]
                        ):
                            level = float(price_match.group(1))
                            if "support" in line.lower():
                                if "support" not in parsed["fibonacci_levels"]:
                                    parsed["fibonacci_levels"]["support"] = []
                                parsed["fibonacci_levels"]["support"].append(level)
                            elif "resistance" in line.lower():
                                if "resistance" not in parsed["fibonacci_levels"]:
                                    parsed["fibonacci_levels"]["resistance"] = []
                                parsed["fibonacci_levels"]["resistance"].append(level)
                            elif "invalidation" in line.lower():
                                parsed["fibonacci_levels"]["invalidation"] = level

                elif "trading signal" in section_lower or "signal:" in section_lower:
                    # Parse trading signal
                    lines = section.split("\n")
                    for line in lines:
                        if "direction" in line.lower():
                            direction_text = line.split(":", 1)[-1].strip().upper()
                            if "LONG" in direction_text:
                                parsed["trading_signal"]["direction"] = "LONG"
                            elif "SHORT" in direction_text:
                                parsed["trading_signal"]["direction"] = "SHORT"
                            else:
                                parsed["trading_signal"]["direction"] = "NEUTRAL"
                        elif "entry" in line.lower():
                            entry_match = re.search(r"(\d+\.\d+)", line)
                            if entry_match:
                                parsed["trading_signal"]["entry"] = float(
                                    entry_match.group(1)
                                )
                        elif "stop" in line.lower():
                            stop_match = re.search(r"(\d+\.\d+)", line)
                            if stop_match:
                                parsed["trading_signal"]["stop_loss"] = float(
                                    stop_match.group(1)
                                )
                        elif re.search(r"t[123]|target", line.lower()):
                            target_match = re.search(r"(\d+\.\d+)", line)
                            if target_match:
                                if "targets" not in parsed["trading_signal"]:
                                    parsed["trading_signal"]["targets"] = []
                                parsed["trading_signal"]["targets"].append(
                                    float(target_match.group(1))
                                )
                        elif "confidence" in line.lower():
                            conf_match = re.search(r"(\d+)%?", line)
                            if conf_match:
                                parsed["trading_signal"]["confidence"] = int(
                                    conf_match.group(1)
                                )

                elif (
                    "market psychology" in section_lower or "sentiment" in section_lower
                ):
                    parsed["market_psychology"]["analysis"] = section.strip()

        except Exception as e:
            print(f"Error parsing LLM analysis: {e}")
            parsed["error"] = str(e)

        return parsed

    def get_trading_recommendation(self, analysis: dict) -> dict:
        """Convert analysis into actionable trading recommendation."""

        llm_analysis = analysis.get("llm_analysis", {})
        signal = llm_analysis.get("trading_signal", {})

        # Default recommendation
        recommendation = {
            "action": "HOLD",
            "confidence": 0,
            "entry": None,
            "stop_loss": None,
            "take_profits": [],
            "risk_reward": None,
            "reasoning": "",
        }

        # Check if we have a valid signal
        if signal.get("direction") in ["LONG", "SHORT"]:
            recommendation["action"] = signal["direction"]
            recommendation["confidence"] = signal.get("confidence", 50) / 100.0
            recommendation["entry"] = signal.get("entry", analysis["current_price"])
            recommendation["stop_loss"] = signal.get("stop_loss")
            recommendation["take_profits"] = signal.get("targets", [])

            # Calculate risk/reward
            if recommendation["stop_loss"] and recommendation["take_profits"]:
                risk = abs(recommendation["entry"] - recommendation["stop_loss"])
                reward = abs(
                    recommendation["take_profits"][0] - recommendation["entry"]
                )
                if risk > 0:
                    recommendation["risk_reward"] = reward / risk

            # Add wave-based reasoning
            wave_count = llm_analysis.get("wave_count", {})
            recommendation["reasoning"] = (
                f"Elliott Wave: {wave_count.get('position', 'Unknown')} "
                f"({wave_count.get('type', 'Unknown')} pattern, "
                f"{wave_count.get('confidence', 0)}% confidence)"
            )

        return recommendation


def main():
    """Test the LLM-enhanced Elliott Wave analyzer."""

    print("=" * 80)
    print("LLM-ENHANCED ELLIOTT WAVE ANALYSIS")
    print("=" * 80)

    # Load price data
    symbol = "GBPUSD"
    df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")

    # Get recent data
    recent_data = df["2024-06-01":"2024-06-30"]

    print(
        f"\nAnalyzing {symbol} from {recent_data.index[0]} to {recent_data.index[-1]}"
    )
    print(f"Current Price: {recent_data['close'].iloc[-1]:.5f}")

    # Initialize analyzer
    analyzer = LLMEnhancedElliottWaveAnalyzer()

    print("\nRequesting Elliott Wave analysis from Claude...")

    # Get analysis
    analysis = analyzer.analyze_with_llm(recent_data, symbol)

    # Display results
    print("\n" + "=" * 80)
    print("CLAUDE'S ELLIOTT WAVE ANALYSIS")
    print("=" * 80)
    print(analysis["raw_llm_response"])

    # Get trading recommendation
    recommendation = analyzer.get_trading_recommendation(analysis)

    print("\n" + "=" * 80)
    print("TRADING RECOMMENDATION")
    print("=" * 80)
    print(f"Action: {recommendation['action']}")
    print(f"Confidence: {recommendation['confidence']*100:.1f}%")

    if recommendation["action"] != "HOLD":
        print(f"Entry: {recommendation['entry']:.5f}")
        print(f"Stop Loss: {recommendation['stop_loss']:.5f}")
        print(
            f"Take Profits: {', '.join([f'{tp:.5f}' for tp in recommendation['take_profits']])}"
        )
        if recommendation["risk_reward"]:
            print(f"Risk/Reward: 1:{recommendation['risk_reward']:.1f}")
        print(f"Reasoning: {recommendation['reasoning']}")

    # Save analysis
    output_file = f"models/elliott_wave_analysis_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"\n✅ Analysis saved to {output_file}")

    # Compare with algorithmic waves
    algo_waves = analysis.get("algorithmic_waves", {})
    if algo_waves:
        print(f"\n📊 Algorithmic detection found {len(algo_waves)} wave patterns")

    print("\n" + "=" * 80)
    print("KEY IMPROVEMENTS IN THIS APPROACH:")
    print("=" * 80)
    print("✓ Uses Claude's expertise in Elliott Wave theory")
    print("✓ Provides specific wave counts and labels")
    print("✓ Includes Fibonacci-based support/resistance")
    print("✓ Gives actionable trading signals with stops and targets")
    print("✓ Considers market psychology and sentiment")
    print("✓ Offers alternate counts when confidence is low")
    print("✓ Combines with algorithmic validation")


if __name__ == "__main__":
    main()
