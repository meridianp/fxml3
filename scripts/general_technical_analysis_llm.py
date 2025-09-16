#!/usr/bin/env python
"""General technical analysis using LLM for comprehensive market analysis."""

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TechnicalAnalysisSignal:
    """Comprehensive technical analysis signal."""

    bias: str  # LONG/SHORT/NEUTRAL
    confidence: float
    entry_zones: List[float]
    stop_loss: float
    targets: List[float]
    key_levels: Dict[str, List[float]]
    technical_confluences: List[str]
    market_structure: str
    risk_reward: float
    time_horizon: str


class GeneralTechnicalAnalysisLLM:
    """LLM-based general technical analysis beyond just Elliott Waves."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def analyze_market(
        self, data: pd.DataFrame, symbol: str, timeframe: str = "4H"
    ) -> TechnicalAnalysisSignal:
        """Perform comprehensive technical analysis using LLM."""

        # Prepare market data summary
        market_summary = self._prepare_market_summary(data)

        # Create comprehensive prompt
        prompt = self._create_analysis_prompt(market_summary, symbol, timeframe)

        # Get LLM analysis
        if self.llm_client:
            analysis = self.llm_client.generate_text(
                prompt=prompt,
                system_prompt=self._get_system_prompt(),
                temperature=0.2,
                max_tokens=1500,
            )

            # Parse LLM response
            return self._parse_llm_response(analysis, data)
        else:
            # Fallback to rule-based analysis
            return self._perform_rule_based_analysis(data, market_summary)

    def _prepare_market_summary(self, data: pd.DataFrame) -> Dict:
        """Prepare comprehensive market data summary."""

        current_price = float(data["close"].iloc[-1])

        # Price action analysis
        high_20 = float(data["high"].tail(20).max())
        low_20 = float(data["low"].tail(20).min())
        high_50 = float(data["high"].tail(50).max())
        low_50 = float(data["low"].tail(50).min())

        # Moving averages
        sma_20 = float(data["close"].tail(20).mean())
        sma_50 = float(data["close"].tail(50).mean())
        sma_200 = float(data["close"].tail(200).mean()) if len(data) >= 200 else sma_50

        # Momentum indicators
        rsi = float(data["rsi_14"].iloc[-1]) if "rsi_14" in data else 50

        # Volatility
        atr = (
            float(data["atr_14"].iloc[-1])
            if "atr_14" in data
            else (high_20 - low_20) / 20
        )

        # Volume analysis
        avg_volume = float(data["volume"].tail(20).mean()) if "volume" in data else 0
        current_volume = float(data["volume"].iloc[-1]) if "volume" in data else 0
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

        # Market structure
        higher_highs = self._count_higher_highs(data)
        lower_lows = self._count_lower_lows(data)

        # Support/Resistance levels
        support_levels = self._find_support_levels(data)
        resistance_levels = self._find_resistance_levels(data)

        return {
            "current_price": current_price,
            "high_20": high_20,
            "low_20": low_20,
            "high_50": high_50,
            "low_50": low_50,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "rsi": rsi,
            "atr": atr,
            "volume_ratio": volume_ratio,
            "higher_highs": higher_highs,
            "lower_lows": lower_lows,
            "support_levels": support_levels,
            "resistance_levels": resistance_levels,
            "price_position": (
                (current_price - low_20) / (high_20 - low_20)
                if high_20 > low_20
                else 0.5
            ),
        }

    def _create_analysis_prompt(
        self, summary: Dict, symbol: str, timeframe: str
    ) -> str:
        """Create comprehensive technical analysis prompt."""

        return f"""Analyze the following {symbol} {timeframe} chart data and provide a comprehensive technical trading analysis:

CURRENT MARKET DATA:
- Current Price: {summary['current_price']:.5f}
- 20-period High/Low: {summary['high_20']:.5f} / {summary['low_20']:.5f}
- 50-period High/Low: {summary['high_50']:.5f} / {summary['low_50']:.5f}

MOVING AVERAGES:
- SMA 20: {summary['sma_20']:.5f} ({self._compare_price(summary['current_price'], summary['sma_20'])})
- SMA 50: {summary['sma_50']:.5f} ({self._compare_price(summary['current_price'], summary['sma_50'])})
- SMA 200: {summary['sma_200']:.5f} ({self._compare_price(summary['current_price'], summary['sma_200'])})

MOMENTUM & VOLUME:
- RSI(14): {summary['rsi']:.1f}
- ATR(14): {summary['atr']:.5f}
- Volume Ratio: {summary['volume_ratio']:.2f}x average

MARKET STRUCTURE:
- Recent Higher Highs: {summary['higher_highs']}
- Recent Lower Lows: {summary['lower_lows']}
- Price Position in Range: {summary['price_position']*100:.1f}%

KEY LEVELS:
- Support: {', '.join([f'{s:.5f}' for s in summary['support_levels'][:3]])}
- Resistance: {', '.join([f'{r:.5f}' for r in summary['resistance_levels'][:3]])}

Provide your analysis in the following JSON format:
{{
    "bias": "LONG/SHORT/NEUTRAL",
    "confidence": 0.0-1.0,
    "entry_zones": [price1, price2],
    "stop_loss": price,
    "targets": [tp1, tp2, tp3],
    "key_levels": {{
        "support": [s1, s2, s3],
        "resistance": [r1, r2, r3]
    }},
    "technical_confluences": [
        "confluence1",
        "confluence2",
        "confluence3"
    ],
    "market_structure": "trending_up/trending_down/ranging/breakout",
    "risk_reward": ratio,
    "time_horizon": "intraday/swing/position"
}}

Focus on:
1. Overall trend and market structure
2. Key support/resistance levels
3. Momentum and volume confirmation
4. Entry zones with multiple confluences
5. Clear risk management levels
6. Realistic profit targets"""

    def _get_system_prompt(self) -> str:
        """Get system prompt for technical analysis."""

        return """You are a professional technical analyst with 20+ years of experience in forex markets.
Your analysis should be:
1. Objective and data-driven
2. Focus on high-probability setups only
3. Consider multiple technical factors
4. Provide clear risk/reward ratios
5. Be conservative with stop losses
6. Give realistic profit targets

Always provide analysis in valid JSON format. If uncertain, bias should be NEUTRAL."""

    def _parse_llm_response(
        self, response: str, data: pd.DataFrame
    ) -> TechnicalAnalysisSignal:
        """Parse LLM response into structured signal."""

        try:
            # Extract JSON from response
            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                analysis_data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")

            return TechnicalAnalysisSignal(
                bias=analysis_data.get("bias", "NEUTRAL"),
                confidence=float(analysis_data.get("confidence", 0.5)),
                entry_zones=analysis_data.get(
                    "entry_zones", [float(data["close"].iloc[-1])]
                ),
                stop_loss=float(analysis_data.get("stop_loss", 0)),
                targets=analysis_data.get("targets", []),
                key_levels=analysis_data.get(
                    "key_levels", {"support": [], "resistance": []}
                ),
                technical_confluences=analysis_data.get("technical_confluences", []),
                market_structure=analysis_data.get("market_structure", "unknown"),
                risk_reward=float(analysis_data.get("risk_reward", 1.0)),
                time_horizon=analysis_data.get("time_horizon", "swing"),
            )

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            # Return neutral signal on error
            return self._create_neutral_signal(data)

    def _perform_rule_based_analysis(
        self, data: pd.DataFrame, summary: Dict
    ) -> TechnicalAnalysisSignal:
        """Fallback rule-based technical analysis."""

        current_price = summary["current_price"]
        atr = summary["atr"]

        # Determine bias based on multiple factors
        bias_score = 0
        confluences = []

        # Trend analysis
        if current_price > summary["sma_20"] > summary["sma_50"]:
            bias_score += 2
            confluences.append("Price above rising MAs")
        elif current_price < summary["sma_20"] < summary["sma_50"]:
            bias_score -= 2
            confluences.append("Price below falling MAs")

        # Market structure
        if summary["higher_highs"] >= 2:
            bias_score += 1
            confluences.append(f"{summary['higher_highs']} higher highs")
        if summary["lower_lows"] >= 2:
            bias_score -= 1
            confluences.append(f"{summary['lower_lows']} lower lows")

        # RSI analysis
        if 30 < summary["rsi"] < 50:
            bias_score += 1
            confluences.append("RSI pullback in uptrend zone")
        elif 50 < summary["rsi"] < 70:
            bias_score -= 1
            confluences.append("RSI pullback in downtrend zone")
        elif summary["rsi"] < 30:
            bias_score += 2
            confluences.append("RSI oversold")
        elif summary["rsi"] > 70:
            bias_score -= 2
            confluences.append("RSI overbought")

        # Volume confirmation
        if summary["volume_ratio"] > 1.5:
            confluences.append("High volume")
            bias_score = int(bias_score * 1.2)  # Boost signal with volume

        # Determine final bias
        if bias_score >= 2:
            bias = "LONG"
            stop_loss = current_price - 2 * atr
            targets = [
                current_price + 2 * atr,
                current_price + 3 * atr,
                current_price + 4 * atr,
            ]
        elif bias_score <= -2:
            bias = "SHORT"
            stop_loss = current_price + 2 * atr
            targets = [
                current_price - 2 * atr,
                current_price - 3 * atr,
                current_price - 4 * atr,
            ]
        else:
            bias = "NEUTRAL"
            stop_loss = current_price - 2 * atr
            targets = [current_price + 2 * atr]

        # Calculate confidence
        confidence = min(abs(bias_score) / 6.0, 0.9)

        # Determine market structure
        if abs(current_price - summary["sma_200"]) / summary["sma_200"] < 0.02:
            market_structure = "ranging"
        elif bias_score > 0:
            market_structure = "trending_up"
        elif bias_score < 0:
            market_structure = "trending_down"
        else:
            market_structure = "consolidating"

        # Risk/Reward calculation
        if bias != "NEUTRAL" and targets:
            risk = abs(current_price - stop_loss)
            reward = abs(targets[0] - current_price)
            risk_reward = reward / risk if risk > 0 else 1
        else:
            risk_reward = 1

        return TechnicalAnalysisSignal(
            bias=bias,
            confidence=confidence,
            entry_zones=(
                [current_price, current_price - atr * 0.5]
                if bias == "LONG"
                else [current_price, current_price + atr * 0.5]
            ),
            stop_loss=stop_loss,
            targets=targets,
            key_levels={
                "support": summary["support_levels"][:3],
                "resistance": summary["resistance_levels"][:3],
            },
            technical_confluences=confluences,
            market_structure=market_structure,
            risk_reward=risk_reward,
            time_horizon="swing",
        )

    def _compare_price(self, price: float, ma: float) -> str:
        """Compare price to moving average."""
        pct = ((price - ma) / ma) * 100
        if pct > 0:
            return f"+{pct:.1f}% above"
        else:
            return f"{pct:.1f}% below"

    def _count_higher_highs(self, data: pd.DataFrame, lookback: int = 10) -> int:
        """Count recent higher highs."""
        highs = data["high"].tail(lookback)
        count = 0
        for i in range(1, len(highs)):
            if highs.iloc[i] > highs.iloc[i - 1]:
                count += 1
        return count

    def _count_lower_lows(self, data: pd.DataFrame, lookback: int = 10) -> int:
        """Count recent lower lows."""
        lows = data["low"].tail(lookback)
        count = 0
        for i in range(1, len(lows)):
            if lows.iloc[i] < lows.iloc[i - 1]:
                count += 1
        return count

    def _find_support_levels(
        self, data: pd.DataFrame, lookback: int = 50
    ) -> List[float]:
        """Find key support levels."""
        lows = data["low"].tail(lookback)

        # Find local minima
        support_levels = []
        for i in range(2, len(lows) - 2):
            if (
                lows.iloc[i] < lows.iloc[i - 1]
                and lows.iloc[i] < lows.iloc[i - 2]
                and lows.iloc[i] < lows.iloc[i + 1]
                and lows.iloc[i] < lows.iloc[i + 2]
            ):
                support_levels.append(float(lows.iloc[i]))

        # Add recent low
        support_levels.append(float(lows.min()))

        # Remove duplicates and sort
        support_levels = sorted(list(set(support_levels)))

        return support_levels[:5]  # Return top 5

    def _find_resistance_levels(
        self, data: pd.DataFrame, lookback: int = 50
    ) -> List[float]:
        """Find key resistance levels."""
        highs = data["high"].tail(lookback)

        # Find local maxima
        resistance_levels = []
        for i in range(2, len(highs) - 2):
            if (
                highs.iloc[i] > highs.iloc[i - 1]
                and highs.iloc[i] > highs.iloc[i - 2]
                and highs.iloc[i] > highs.iloc[i + 1]
                and highs.iloc[i] > highs.iloc[i + 2]
            ):
                resistance_levels.append(float(highs.iloc[i]))

        # Add recent high
        resistance_levels.append(float(highs.max()))

        # Remove duplicates and sort
        resistance_levels = sorted(list(set(resistance_levels)), reverse=True)

        return resistance_levels[:5]  # Return top 5

    def _create_neutral_signal(self, data: pd.DataFrame) -> TechnicalAnalysisSignal:
        """Create a neutral signal when analysis fails."""
        current_price = float(data["close"].iloc[-1])
        atr = (
            float(data["atr_14"].iloc[-1])
            if "atr_14" in data
            else current_price * 0.001
        )

        return TechnicalAnalysisSignal(
            bias="NEUTRAL",
            confidence=0.0,
            entry_zones=[current_price],
            stop_loss=current_price - 2 * atr,
            targets=[current_price + 2 * atr],
            key_levels={"support": [], "resistance": []},
            technical_confluences=["Analysis error - neutral stance"],
            market_structure="unknown",
            risk_reward=1.0,
            time_horizon="swing",
        )


def demonstrate_technical_analysis():
    """Demonstrate the general technical analysis system."""

    print("General Technical Analysis with LLM")
    print("=" * 60)

    analyzer = GeneralTechnicalAnalysisLLM()

    print("\nKey Features:")
    print("1. Comprehensive Market Analysis:")
    print("   - Trend analysis with multiple MAs")
    print("   - Market structure (HH/LL patterns)")
    print("   - Support/Resistance identification")
    print("   - Momentum indicators (RSI, etc)")
    print("   - Volume analysis")

    print("\n2. Multiple Confluence Approach:")
    print("   - Requires multiple technical factors to align")
    print("   - Weights signals based on confluence strength")
    print("   - Considers market context")

    print("\n3. Dynamic Risk Management:")
    print("   - ATR-based stop losses")
    print("   - Multiple profit targets")
    print("   - Risk/Reward calculations")

    print("\n4. Structured Output:")
    print("   - Clear bias (LONG/SHORT/NEUTRAL)")
    print("   - Confidence scores")
    print("   - Entry zones (not just single price)")
    print("   - Key price levels")
    print("   - Technical reasoning")

    print("\n5. LLM Integration:")
    print("   - Can leverage Claude/GPT for nuanced analysis")
    print("   - Falls back to rule-based system if needed")
    print("   - Structured prompts for consistent output")


if __name__ == "__main__":
    demonstrate_technical_analysis()
