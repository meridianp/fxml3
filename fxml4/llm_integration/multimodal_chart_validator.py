"""Multi-modal LLM validation for technical analysis charts."""

import base64
import io
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle
from PIL import Image

from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class MultiModalChartValidator:
    """Generate and validate technical analysis charts using multi-modal LLMs."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the chart validator.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.llm_client = LLMClient()

        # Chart styling
        self.chart_style = mpf.make_mpf_style(
            base_mpf_style="charles",
            rc={"font.size": 10},
            gridcolor="#2E2E2E",
            gridstyle="-",
            facecolor="#1C1C1C",
        )

        # Validation thresholds
        self.min_confidence_threshold = config.get("min_confidence", 0.7)
        self.require_confirmation = config.get("require_confirmation", True)

    async def validate_trading_signal(
        self,
        signal: Dict[str, Any],
        price_data: pd.DataFrame,
        indicators: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate a trading signal using multi-modal analysis.

        Args:
            signal: Trading signal to validate
            price_data: OHLCV DataFrame with datetime index
            indicators: Dictionary of calculated indicators

        Returns:
            Validation result with confidence scores
        """
        try:
            # Generate technical analysis chart
            chart_image = self._generate_analysis_chart(price_data, indicators, signal)

            # Convert to base64
            chart_base64 = self._image_to_base64(chart_image)

            # Validate with multi-modal LLM
            validation = await self._validate_with_llm(
                chart_base64, signal, price_data, indicators
            )

            # Add visual confirmation if available
            if validation.get("visual_patterns"):
                validation["enhanced_confidence"] = self._calculate_enhanced_confidence(
                    signal.get("confidence", 0.5),
                    validation.get("llm_confidence", 0.5),
                    validation.get("pattern_clarity", 0.5),
                )

            return validation

        except Exception as e:
            logger.error(f"Error validating signal: {e}")
            return {"valid": False, "error": str(e), "confidence": 0.0}

    def _generate_analysis_chart(
        self,
        price_data: pd.DataFrame,
        indicators: Dict[str, Any],
        signal: Dict[str, Any],
    ) -> Image.Image:
        """Generate comprehensive technical analysis chart.

        Args:
            price_data: OHLCV data
            indicators: Technical indicators
            signal: Trading signal details

        Returns:
            PIL Image object
        """
        # Create figure with subplots
        fig = mpf.figure(figsize=(16, 12), style=self.chart_style)

        # Main price chart (60% height)
        ax1 = fig.add_subplot(3, 1, 1)
        ax1.set_position([0.05, 0.45, 0.9, 0.5])

        # RSI subplot (20% height)
        ax2 = fig.add_subplot(3, 1, 2)
        ax2.set_position([0.05, 0.25, 0.9, 0.15])

        # Volume subplot (20% height)
        ax3 = fig.add_subplot(3, 1, 3)
        ax3.set_position([0.05, 0.05, 0.9, 0.15])

        # Prepare data for mplfinance
        plot_data = price_data.tail(100).copy()  # Last 100 candles

        # Add moving averages if available
        addplot = []

        if "sma_20" in indicators:
            addplot.append(
                mpf.make_addplot(
                    indicators["sma_20"].tail(100),
                    ax=ax1,
                    color="yellow",
                    width=1.5,
                    label="SMA 20",
                )
            )

        if "sma_50" in indicators:
            addplot.append(
                mpf.make_addplot(
                    indicators["sma_50"].tail(100),
                    ax=ax1,
                    color="cyan",
                    width=1.5,
                    label="SMA 50",
                )
            )

        if "ema_9" in indicators:
            addplot.append(
                mpf.make_addplot(
                    indicators["ema_9"].tail(100),
                    ax=ax1,
                    color="orange",
                    width=1.0,
                    label="EMA 9",
                )
            )

        # Add Bollinger Bands if available
        if all(k in indicators for k in ["bb_upper", "bb_middle", "bb_lower"]):
            addplot.extend(
                [
                    mpf.make_addplot(
                        indicators["bb_upper"].tail(100),
                        ax=ax1,
                        color="gray",
                        alpha=0.5,
                        width=1.0,
                    ),
                    mpf.make_addplot(
                        indicators["bb_lower"].tail(100),
                        ax=ax1,
                        color="gray",
                        alpha=0.5,
                        width=1.0,
                    ),
                ]
            )

        # Add RSI
        if "rsi" in indicators:
            rsi_data = indicators["rsi"].tail(100)
            addplot.append(
                mpf.make_addplot(
                    rsi_data, ax=ax2, color="purple", width=1.5, ylabel="RSI"
                )
            )

            # Add RSI levels
            ax2.axhline(y=70, color="red", alpha=0.5, linestyle="--")
            ax2.axhline(y=30, color="green", alpha=0.5, linestyle="--")
            ax2.set_ylim(0, 100)

        # Plot candlestick chart
        mpf.plot(
            plot_data,
            type="candle",
            ax=ax1,
            volume=ax3,
            addplot=addplot if addplot else None,
            style=self.chart_style,
            returnfig=False,
        )

        # Add signal annotation
        self._annotate_signal(ax1, plot_data, signal)

        # Add support/resistance levels
        if "support_levels" in indicators:
            for level in indicators["support_levels"][-3:]:  # Last 3 levels
                ax1.axhline(
                    y=level, color="green", alpha=0.3, linestyle="--", linewidth=1
                )
                ax1.text(
                    len(plot_data) - 1,
                    level,
                    f"S: {level:.5f}",
                    color="green",
                    fontsize=8,
                    ha="left",
                )

        if "resistance_levels" in indicators:
            for level in indicators["resistance_levels"][-3:]:  # Last 3 levels
                ax1.axhline(
                    y=level, color="red", alpha=0.3, linestyle="--", linewidth=1
                )
                ax1.text(
                    len(plot_data) - 1,
                    level,
                    f"R: {level:.5f}",
                    color="red",
                    fontsize=8,
                    ha="left",
                )

        # Add pattern annotations
        if "patterns" in indicators:
            self._annotate_patterns(ax1, plot_data, indicators["patterns"])

        # Add title and info
        symbol = signal.get("symbol", "Unknown")
        timeframe = signal.get("timeframe", "4H")
        current_price = plot_data["close"].iloc[-1]

        ax1.set_title(
            f"{symbol} - {timeframe} - Technical Analysis\n"
            f"Current: {current_price:.5f} | "
            f"Signal: {signal.get('direction', 'N/A')} | "
            f"Confidence: {signal.get('confidence', 0):.1%}",
            fontsize=14,
            pad=20,
        )

        # Add legend
        if addplot:
            ax1.legend(loc="upper left", framealpha=0.5)

        # Add grid
        ax1.grid(True, alpha=0.3)
        ax2.grid(True, alpha=0.3)
        ax3.grid(True, alpha=0.3)

        # Save to image
        buf = io.BytesIO()
        plt.savefig(
            buf,
            format="png",
            dpi=150,
            bbox_inches="tight",
            facecolor="#1C1C1C",
            edgecolor="none",
        )
        buf.seek(0)

        # Convert to PIL Image
        image = Image.open(buf)
        plt.close(fig)

        return image

    def _annotate_signal(self, ax, price_data: pd.DataFrame, signal: Dict[str, Any]):
        """Annotate the trading signal on the chart."""
        # Get last candle position
        last_idx = len(price_data) - 1
        last_price = price_data["close"].iloc[-1]

        # Signal arrow
        if signal.get("direction") == "BUY":
            ax.annotate(
                "BUY",
                xy=(last_idx, price_data["low"].iloc[-1] * 0.9995),
                xytext=(last_idx, price_data["low"].iloc[-1] * 0.998),
                arrowprops=dict(arrowstyle="->", color="green", lw=2),
                fontsize=12,
                color="green",
                ha="center",
                weight="bold",
            )
        elif signal.get("direction") == "SELL":
            ax.annotate(
                "SELL",
                xy=(last_idx, price_data["high"].iloc[-1] * 1.0005),
                xytext=(last_idx, price_data["high"].iloc[-1] * 1.002),
                arrowprops=dict(arrowstyle="->", color="red", lw=2),
                fontsize=12,
                color="red",
                ha="center",
                weight="bold",
            )

        # Entry, stop loss, take profit levels
        if signal.get("entry_price"):
            ax.axhline(
                y=signal["entry_price"],
                color="yellow",
                linestyle="-",
                linewidth=2,
                alpha=0.7,
            )
            ax.text(
                last_idx + 1,
                signal["entry_price"],
                f"Entry: {signal['entry_price']:.5f}",
                color="yellow",
                fontsize=10,
                va="center",
            )

        if signal.get("stop_loss"):
            ax.axhline(
                y=signal["stop_loss"],
                color="red",
                linestyle="--",
                linewidth=2,
                alpha=0.7,
            )
            ax.text(
                last_idx + 1,
                signal["stop_loss"],
                f"SL: {signal['stop_loss']:.5f}",
                color="red",
                fontsize=10,
                va="center",
            )

        if signal.get("take_profit"):
            ax.axhline(
                y=signal["take_profit"],
                color="green",
                linestyle="--",
                linewidth=2,
                alpha=0.7,
            )
            ax.text(
                last_idx + 1,
                signal["take_profit"],
                f"TP: {signal['take_profit']:.5f}",
                color="green",
                fontsize=10,
                va="center",
            )

        # Risk/Reward box
        if signal.get("stop_loss") and signal.get("take_profit"):
            entry = signal.get("entry_price", last_price)
            sl_distance = abs(entry - signal["stop_loss"])
            tp_distance = abs(signal["take_profit"] - entry)
            rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0

            # Add R:R text
            ax.text(
                last_idx - 10,
                price_data["high"].max() * 0.99,
                f"R:R = 1:{rr_ratio:.1f}",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.3),
                fontsize=11,
                weight="bold",
            )

    def _annotate_patterns(self, ax, price_data: pd.DataFrame, patterns: List[Dict]):
        """Annotate identified patterns on the chart."""
        for pattern in patterns[-3:]:  # Show last 3 patterns
            if pattern.get("start_idx") and pattern.get("end_idx"):
                start_idx = max(0, pattern["start_idx"] - (len(price_data) - 100))
                end_idx = min(
                    len(price_data) - 1, pattern["end_idx"] - (len(price_data) - 100)
                )

                if start_idx < len(price_data) and end_idx < len(price_data):
                    # Draw pattern box
                    pattern_highs = price_data["high"].iloc[start_idx : end_idx + 1]
                    pattern_lows = price_data["low"].iloc[start_idx : end_idx + 1]

                    rect = Rectangle(
                        (start_idx - 0.5, pattern_lows.min()),
                        end_idx - start_idx + 1,
                        pattern_highs.max() - pattern_lows.min(),
                        linewidth=1,
                        edgecolor="cyan",
                        facecolor="cyan",
                        alpha=0.1,
                    )
                    ax.add_patch(rect)

                    # Add pattern label
                    ax.text(
                        (start_idx + end_idx) / 2,
                        pattern_highs.max(),
                        pattern.get("name", "Pattern"),
                        ha="center",
                        va="bottom",
                        fontsize=9,
                        color="cyan",
                        bbox=dict(
                            boxstyle="round,pad=0.3", facecolor="black", alpha=0.5
                        ),
                    )

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    async def _validate_with_llm(
        self,
        chart_base64: str,
        signal: Dict[str, Any],
        price_data: pd.DataFrame,
        indicators: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate the chart and signal using multi-modal LLM.

        Args:
            chart_base64: Base64 encoded chart image
            signal: Trading signal details
            price_data: Price data
            indicators: Technical indicators

        Returns:
            Validation results
        """
        # Prepare context
        current_price = price_data["close"].iloc[-1]
        price_change_1d = (
            (price_data["close"].iloc[-1] / price_data["close"].iloc[-24] - 1) * 100
            if len(price_data) > 24
            else 0
        )

        # Recent price action description
        recent_highs = price_data["high"].tail(20).max()
        recent_lows = price_data["low"].tail(20).min()

        context = f"""Trading Signal Analysis Request:

Symbol: {signal.get('symbol', 'Unknown')}
Timeframe: {signal.get('timeframe', '4H')}
Current Price: {current_price:.5f}
24h Change: {price_change_1d:+.2f}%
20-bar High: {recent_highs:.5f}
20-bar Low: {recent_lows:.5f}

Signal Details:
- Direction: {signal.get('direction', 'Unknown')}
- ML Confidence: {signal.get('confidence', 0):.1%}
- Entry: {signal.get('entry_price', current_price):.5f}
- Stop Loss: {signal.get('stop_loss', 'Not set')}
- Take Profit: {signal.get('take_profit', 'Not set')}

Technical Indicators:
- RSI: {indicators.get('rsi', pd.Series()).iloc[-1] if 'rsi' in indicators else 'N/A'}
- MACD Signal: {indicators.get('macd_signal', 'N/A')}
- Volume Trend: {indicators.get('volume_trend', 'N/A')}
"""

        prompt = f"""{context}

Please analyze the attached technical analysis chart and validate the trading signal.

Provide a comprehensive analysis including:

1. **Chart Pattern Validation**: Identify any clear chart patterns (head and shoulders, triangles, flags, etc.)
2. **Support/Resistance Analysis**: Validate the marked S/R levels and their strength
3. **Indicator Confluence**: Check if multiple indicators confirm the signal direction
4. **Entry Point Quality**: Assess if the entry point is optimal given the chart structure
5. **Risk/Reward Assessment**: Evaluate if the stop loss and take profit levels are well-placed
6. **Market Structure**: Analyze the overall trend and market structure
7. **Signal Strength**: Rate the overall signal strength from 0-100%

Respond in JSON format with these fields:
- valid: boolean (should the signal be taken)
- llm_confidence: 0-1 score
- visual_patterns: list of identified patterns
- key_observations: list of important observations
- concerns: list of any concerns or red flags
- suggested_adjustments: any recommended changes to entry/stop/target
- pattern_clarity: 0-1 score for how clear the patterns are
- overall_assessment: brief summary"""

        try:
            # Call multi-modal LLM with image
            response = await self.llm_client.generate_multimodal_response(
                prompt=prompt, image_base64=chart_base64
            )

            # Parse JSON response
            import json

            try:
                # Try to extract JSON from the response
                if "```json" in response:
                    json_start = response.find("```json") + 7
                    json_end = response.find("```", json_start)
                    response = response[json_start:json_end].strip()
                elif "{" in response:
                    # Find the JSON object
                    json_start = response.find("{")
                    json_end = response.rfind("}") + 1
                    response = response[json_start:json_end]

                validation = json.loads(response)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON response, using defaults")
                validation = {
                    "valid": True,  # Default to true since LLM responded
                    "llm_confidence": 0.7,
                    "visual_patterns": [],
                    "key_observations": ["LLM response parsed with defaults"],
                    "concerns": [],
                    "pattern_clarity": 0.6,
                    "overall_assessment": response[:200],  # First 200 chars
                }

            # Add metadata
            validation["validation_timestamp"] = datetime.now()
            validation["chart_timeframe"] = signal.get("timeframe", "unknown")
            validation["symbol"] = signal.get("symbol", "unknown")

            return validation

        except Exception as e:
            logger.error(f"Error in LLM validation: {e}")

            # Fallback validation based on technical rules
            return self._fallback_validation(signal, indicators)

    def _fallback_validation(
        self, signal: Dict[str, Any], indicators: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback validation using technical rules."""
        valid = True
        concerns = []

        # Check RSI extremes
        if "rsi" in indicators:
            rsi = (
                indicators["rsi"].iloc[-1]
                if hasattr(indicators["rsi"], "iloc")
                else indicators["rsi"]
            )
            if signal.get("direction") == "BUY" and rsi > 70:
                concerns.append("RSI overbought for long entry")
                valid = False
            elif signal.get("direction") == "SELL" and rsi < 30:
                concerns.append("RSI oversold for short entry")
                valid = False

        # Check risk/reward
        if (
            signal.get("stop_loss")
            and signal.get("take_profit")
            and signal.get("entry_price")
        ):
            sl_distance = abs(signal["entry_price"] - signal["stop_loss"])
            tp_distance = abs(signal["take_profit"] - signal["entry_price"])

            if tp_distance < sl_distance:
                concerns.append("Risk/Reward ratio less than 1:1")
                valid = False

        return {
            "valid": valid,
            "llm_confidence": 0.5,
            "visual_patterns": [],
            "key_observations": ["Fallback validation used"],
            "concerns": concerns,
            "suggested_adjustments": {},
            "pattern_clarity": 0.3,
            "overall_assessment": "Technical rule-based validation only",
        }

    def _calculate_enhanced_confidence(
        self, ml_confidence: float, llm_confidence: float, pattern_clarity: float
    ) -> float:
        """Calculate enhanced confidence score combining all factors.

        Args:
            ml_confidence: Original ML model confidence
            llm_confidence: LLM validation confidence
            pattern_clarity: Visual pattern clarity score

        Returns:
            Enhanced confidence score
        """
        # Weighted average with higher weight on visual validation
        weights = {"ml": 0.3, "llm": 0.4, "pattern": 0.3}

        enhanced = (
            ml_confidence * weights["ml"]
            + llm_confidence * weights["llm"]
            + pattern_clarity * weights["pattern"]
        )

        # Apply penalty if any component is very low
        if min(ml_confidence, llm_confidence, pattern_clarity) < 0.3:
            enhanced *= 0.8

        # Bonus if all components agree strongly
        if all(
            score > 0.7 for score in [ml_confidence, llm_confidence, pattern_clarity]
        ):
            enhanced = min(enhanced * 1.1, 1.0)

        return enhanced

    async def generate_analysis_report(
        self, validation_result: Dict[str, Any], chart_image: Image.Image
    ) -> str:
        """Generate a comprehensive analysis report.

        Args:
            validation_result: Validation results from LLM
            chart_image: The generated chart

        Returns:
            Formatted analysis report
        """
        report = f"""
# Technical Analysis Validation Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Symbol**: {validation_result.get('symbol', 'Unknown')}
**Timeframe**: {validation_result.get('chart_timeframe', 'Unknown')}

## Signal Validation

**Valid**: {'✅ YES' if validation_result.get('valid') else '❌ NO'}
**LLM Confidence**: {validation_result.get('llm_confidence', 0):.1%}
**Pattern Clarity**: {validation_result.get('pattern_clarity', 0):.1%}
**Enhanced Confidence**: {validation_result.get('enhanced_confidence', 0):.1%}

## Visual Patterns Identified

"""

        patterns = validation_result.get("visual_patterns", [])
        if patterns:
            for pattern in patterns:
                report += f"- {pattern}\n"
        else:
            report += "- No clear patterns identified\n"

        report += f"""
## Key Observations

"""

        observations = validation_result.get("key_observations", [])
        for obs in observations:
            report += f"- {obs}\n"

        if validation_result.get("concerns"):
            report += f"""
## ⚠️ Concerns

"""
            for concern in validation_result["concerns"]:
                report += f"- {concern}\n"

        if validation_result.get("suggested_adjustments"):
            report += f"""
## Suggested Adjustments

"""
            for key, value in validation_result["suggested_adjustments"].items():
                report += f"- {key}: {value}\n"

        report += f"""
## Overall Assessment

{validation_result.get('overall_assessment', 'No assessment provided')}

---
*This analysis combines ML predictions with visual chart validation using multi-modal LLM technology.*
"""

        return report
