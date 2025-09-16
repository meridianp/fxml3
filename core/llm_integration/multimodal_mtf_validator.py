"""Multi-timeframe chart validation using multi-modal LLMs."""

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


class MultiTimeframeChartValidator:
    """Generate and validate multi-timeframe technical analysis charts using multi-modal LLMs."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the multi-timeframe chart validator.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.llm_client = LLMClient()

        # Chart styling
        self.chart_style = mpf.make_mpf_style(
            base_mpf_style="charles",
            rc={"font.size": 9},
            gridcolor="#2E2E2E",
            gridstyle="-",
            facecolor="#1C1C1C",
        )

        # Validation thresholds
        self.min_confidence_threshold = config.get("min_confidence", 0.7)
        self.require_confirmation = config.get("require_confirmation", True)

        # Timeframe configurations
        self.timeframes = config.get("timeframes", ["D", "4H", "1H"])
        self.candles_per_timeframe = config.get(
            "candles_per_timeframe",
            {
                "D": 50,  # 50 daily candles
                "4H": 100,  # 100 4-hour candles
                "1H": 100,  # 100 1-hour candles
                "15T": 100,  # 100 15-minute candles
            },
        )

    async def validate_trading_signal_mtf(
        self,
        signal: Dict[str, Any],
        price_data_dict: Dict[str, pd.DataFrame],
        indicators_dict: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Validate a trading signal using multi-timeframe analysis.

        Args:
            signal: Trading signal to validate
            price_data_dict: Dictionary of OHLCV DataFrames by timeframe
            indicators_dict: Dictionary of indicators by timeframe

        Returns:
            Validation result with confidence scores
        """
        try:
            # Generate multi-timeframe chart
            chart_image = self._generate_mtf_chart(
                price_data_dict, indicators_dict, signal
            )

            # Convert to base64
            chart_base64 = self._image_to_base64(chart_image)

            # Validate with multi-modal LLM
            validation = await self._validate_with_llm_mtf(
                chart_base64, signal, price_data_dict, indicators_dict
            )

            # Add visual confirmation if available
            if validation.get("visual_patterns"):
                validation["enhanced_confidence"] = self._calculate_enhanced_confidence(
                    signal.get("confidence", 0.5),
                    validation.get("llm_confidence", 0.5),
                    validation.get("pattern_clarity", 0.5),
                    validation.get("timeframe_alignment", 0.5),
                )

            return validation

        except Exception as e:
            logger.error(f"Error validating signal: {e}")
            return {"valid": False, "error": str(e), "confidence": 0.0}

    def _generate_mtf_chart(
        self,
        price_data_dict: Dict[str, pd.DataFrame],
        indicators_dict: Dict[str, Dict[str, Any]],
        signal: Dict[str, Any],
    ) -> Image.Image:
        """Generate multi-timeframe technical analysis chart.

        Args:
            price_data_dict: OHLCV data by timeframe
            indicators_dict: Technical indicators by timeframe
            signal: Trading signal details

        Returns:
            PIL Image object
        """
        # Create figure with subplots for each timeframe
        num_timeframes = len(self.timeframes)
        fig = mpf.figure(figsize=(20, 6 * num_timeframes), style=self.chart_style)

        # Calculate subplot positions
        for idx, timeframe in enumerate(self.timeframes):
            if timeframe not in price_data_dict:
                logger.warning(f"Timeframe {timeframe} not in price data")
                continue

            # Create subplot for this timeframe
            # Main price chart
            ax_main = fig.add_subplot(num_timeframes, 2, idx * 2 + 1)
            ax_main.set_position([0.05, 0.7 - idx * 0.3, 0.6, 0.25])

            # RSI subplot
            ax_rsi = fig.add_subplot(num_timeframes, 2, idx * 2 + 2)
            ax_rsi.set_position([0.7, 0.7 - idx * 0.3, 0.25, 0.25])

            # Get data for this timeframe
            price_data = price_data_dict[timeframe]
            indicators = indicators_dict.get(timeframe, {})

            # Determine number of candles to show
            num_candles = self.candles_per_timeframe.get(timeframe, 100)
            plot_data = price_data.tail(num_candles).copy()

            # Prepare addplot for indicators
            addplot = []

            # Add moving averages
            if "sma_20" in indicators:
                addplot.append(
                    mpf.make_addplot(
                        indicators["sma_20"].tail(num_candles),
                        ax=ax_main,
                        color="yellow",
                        width=1.5,
                        label="SMA 20",
                    )
                )

            if "sma_50" in indicators:
                addplot.append(
                    mpf.make_addplot(
                        indicators["sma_50"].tail(num_candles),
                        ax=ax_main,
                        color="cyan",
                        width=1.5,
                        label="SMA 50",
                    )
                )

            if "ema_9" in indicators:
                addplot.append(
                    mpf.make_addplot(
                        indicators["ema_9"].tail(num_candles),
                        ax=ax_main,
                        color="orange",
                        width=1.0,
                        label="EMA 9",
                    )
                )

            # Add Bollinger Bands
            if all(k in indicators for k in ["bb_upper", "bb_lower"]):
                addplot.extend(
                    [
                        mpf.make_addplot(
                            indicators["bb_upper"].tail(num_candles),
                            ax=ax_main,
                            color="gray",
                            alpha=0.5,
                            width=1.0,
                        ),
                        mpf.make_addplot(
                            indicators["bb_lower"].tail(num_candles),
                            ax=ax_main,
                            color="gray",
                            alpha=0.5,
                            width=1.0,
                        ),
                    ]
                )

            # Add RSI
            if "rsi" in indicators:
                rsi_data = indicators["rsi"].tail(num_candles)
                addplot.append(
                    mpf.make_addplot(
                        rsi_data, ax=ax_rsi, color="purple", width=1.5, ylabel="RSI"
                    )
                )

                # Add RSI levels
                ax_rsi.axhline(y=70, color="red", alpha=0.5, linestyle="--")
                ax_rsi.axhline(y=30, color="green", alpha=0.5, linestyle="--")
                ax_rsi.set_ylim(0, 100)

            # Plot candlestick chart
            mpf.plot(
                plot_data,
                type="candle",
                ax=ax_main,
                addplot=addplot if addplot else None,
                style=self.chart_style,
                returnfig=False,
                volume=False,  # We'll handle volume separately if needed
            )

            # Add signal annotation on primary timeframe
            if timeframe == signal.get("timeframe", "4H"):
                self._annotate_signal_mtf(ax_main, plot_data, signal)

            # Add support/resistance levels
            if "support_levels" in indicators:
                for level in indicators["support_levels"][-3:]:
                    ax_main.axhline(
                        y=level, color="green", alpha=0.3, linestyle="--", linewidth=1
                    )

            if "resistance_levels" in indicators:
                for level in indicators["resistance_levels"][-3:]:
                    ax_main.axhline(
                        y=level, color="red", alpha=0.3, linestyle="--", linewidth=1
                    )

            # Add title for this timeframe
            current_price = plot_data["close"].iloc[-1]
            price_change = (
                plot_data["close"].iloc[-1] / plot_data["close"].iloc[0] - 1
            ) * 100

            ax_main.set_title(
                f"{signal.get('symbol', 'Unknown')} - {timeframe} - {current_price:.5f} ({price_change:+.2f}%)",
                fontsize=12,
                pad=10,
            )

            # Add grid
            ax_main.grid(True, alpha=0.3)
            ax_rsi.grid(True, alpha=0.3)

            # Add timeframe alignment indicator
            if idx < num_timeframes - 1:
                # Draw connection line to next timeframe
                ax_main.annotate(
                    "",
                    xy=(1.02, 0.5),
                    xytext=(1.02, -0.5),
                    xycoords="axes fraction",
                    arrowprops=dict(arrowstyle="->", color="yellow", lw=2),
                )

        # Add main title
        fig.suptitle(
            f"Multi-Timeframe Analysis - {signal.get('symbol', 'Unknown')} - "
            f"{signal.get('direction', 'N/A')} Signal @ {signal.get('entry_price', 0):.5f}",
            fontsize=16,
            y=0.98,
        )

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

    def _annotate_signal_mtf(
        self, ax, price_data: pd.DataFrame, signal: Dict[str, Any]
    ):
        """Annotate the trading signal on the chart."""
        # Get last candle position
        last_idx = len(price_data) - 1
        last_price = price_data["close"].iloc[-1]

        # Signal marker
        if signal.get("direction") == "BUY":
            ax.scatter(
                last_idx, last_price * 0.998, marker="^", color="green", s=200, zorder=5
            )
            ax.text(
                last_idx,
                last_price * 0.995,
                "BUY",
                ha="center",
                va="top",
                fontsize=10,
                color="green",
                weight="bold",
            )
        elif signal.get("direction") == "SELL":
            ax.scatter(
                last_idx, last_price * 1.002, marker="v", color="red", s=200, zorder=5
            )
            ax.text(
                last_idx,
                last_price * 1.005,
                "SELL",
                ha="center",
                va="bottom",
                fontsize=10,
                color="red",
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
                fontsize=9,
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
                fontsize=9,
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
                fontsize=9,
                va="center",
            )

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    async def _validate_with_llm_mtf(
        self,
        chart_base64: str,
        signal: Dict[str, Any],
        price_data_dict: Dict[str, pd.DataFrame],
        indicators_dict: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Validate the multi-timeframe chart and signal using multi-modal LLM.

        Args:
            chart_base64: Base64 encoded chart image
            signal: Trading signal details
            price_data_dict: Price data by timeframe
            indicators_dict: Technical indicators by timeframe

        Returns:
            Validation results
        """
        # Build comprehensive context
        context_parts = [f"Multi-Timeframe Trading Signal Analysis Request:\n"]
        context_parts.append(f"Symbol: {signal.get('symbol', 'Unknown')}")
        context_parts.append(f"Primary Timeframe: {signal.get('timeframe', '4H')}")
        context_parts.append(f"Signal Direction: {signal.get('direction', 'Unknown')}")
        context_parts.append(f"ML Confidence: {signal.get('confidence', 0):.1%}")
        context_parts.append(f"Entry: {signal.get('entry_price', 0):.5f}")
        context_parts.append(f"Stop Loss: {signal.get('stop_loss', 'Not set')}")
        context_parts.append(f"Take Profit: {signal.get('take_profit', 'Not set')}")

        # Add timeframe-specific analysis
        context_parts.append("\nTimeframe Analysis:")
        for tf in self.timeframes:
            if tf in price_data_dict:
                data = price_data_dict[tf]
                indicators = indicators_dict.get(tf, {})

                current = data["close"].iloc[-1]
                high_20 = data["high"].tail(20).max()
                low_20 = data["low"].tail(20).min()
                change = (data["close"].iloc[-1] / data["close"].iloc[0] - 1) * 100

                context_parts.append(f"\n{tf} Timeframe:")
                context_parts.append(f"  - Current: {current:.5f}")
                context_parts.append(f"  - 20-bar Range: {low_20:.5f} - {high_20:.5f}")
                context_parts.append(f"  - Period Change: {change:+.2f}%")

                if "rsi" in indicators and len(indicators["rsi"]) > 0:
                    context_parts.append(f"  - RSI: {indicators['rsi'].iloc[-1]:.1f}")

        context = "\n".join(context_parts)

        prompt = f"""{context}

Please analyze the attached multi-timeframe technical analysis chart and validate the trading signal.

IMPORTANT: Focus on timeframe alignment and confluence across multiple timeframes.

Provide a comprehensive analysis including:

1. **Timeframe Alignment**: Do all timeframes support the signal direction?
   - Daily trend alignment
   - 4H structure confirmation
   - 1H entry timing quality

2. **Multi-Timeframe Patterns**: Identify patterns visible across timeframes
   - Major patterns on higher timeframes
   - Entry patterns on lower timeframes
   - Pattern confluence

3. **Support/Resistance Confluence**: Key levels across timeframes
   - Major daily S/R levels
   - Intraday structure levels
   - Level clustering

4. **Indicator Divergence**: Check for divergences between timeframes
   - RSI divergences
   - Moving average alignment
   - Momentum consistency

5. **Entry Timing**: Is this the optimal entry point considering all timeframes?
   - Higher timeframe trend stage
   - Lower timeframe entry trigger
   - Risk/reward optimization

6. **Risk Assessment**: Multi-timeframe risk factors
   - Counter-trend risks on higher timeframes
   - Volatility considerations
   - News/event risks

7. **Signal Strength**: Rate the overall signal strength from 0-100%

Respond in JSON format with these fields:
- valid: boolean (should the signal be taken)
- llm_confidence: 0-1 score
- timeframe_alignment: 0-1 score (how well timeframes align)
- visual_patterns: list of identified patterns with timeframe
- key_observations: list of important multi-timeframe observations
- concerns: list of any concerns or red flags
- suggested_adjustments: any recommended changes to entry/stop/target
- pattern_clarity: 0-1 score for pattern clarity
- optimal_entry_timeframe: best timeframe for entry timing
- overall_assessment: comprehensive summary"""

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
                    "valid": True,
                    "llm_confidence": 0.7,
                    "timeframe_alignment": 0.5,
                    "visual_patterns": [],
                    "key_observations": ["LLM response parsed with defaults"],
                    "concerns": [],
                    "pattern_clarity": 0.6,
                    "optimal_entry_timeframe": signal.get("timeframe", "4H"),
                    "overall_assessment": response[:200],
                }

            # Add metadata
            validation["validation_timestamp"] = datetime.now()
            validation["timeframes_analyzed"] = list(price_data_dict.keys())
            validation["symbol"] = signal.get("symbol", "unknown")

            return validation

        except Exception as e:
            logger.error(f"Error in LLM validation: {e}")

            # Fallback validation based on technical rules
            return self._fallback_validation_mtf(signal, indicators_dict)

    def _fallback_validation_mtf(
        self, signal: Dict[str, Any], indicators_dict: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fallback validation using technical rules across timeframes."""
        valid = True
        concerns = []
        timeframe_scores = []

        # Check each timeframe
        for tf in self.timeframes:
            if tf not in indicators_dict:
                continue

            indicators = indicators_dict[tf]
            tf_score = 0.5  # neutral

            # Check RSI
            if "rsi" in indicators:
                rsi = (
                    indicators["rsi"].iloc[-1]
                    if hasattr(indicators["rsi"], "iloc")
                    else indicators["rsi"]
                )
                if signal.get("direction") == "BUY" and rsi > 70:
                    concerns.append(f"{tf}: RSI overbought ({rsi:.1f})")
                    tf_score -= 0.2
                elif signal.get("direction") == "SELL" and rsi < 30:
                    concerns.append(f"{tf}: RSI oversold ({rsi:.1f})")
                    tf_score -= 0.2
                else:
                    tf_score += 0.1

            timeframe_scores.append(tf_score)

        # Calculate alignment
        avg_score = np.mean(timeframe_scores) if timeframe_scores else 0.5
        valid = avg_score > 0.4 and len(concerns) < len(self.timeframes) / 2

        return {
            "valid": valid,
            "llm_confidence": 0.5,
            "timeframe_alignment": avg_score,
            "visual_patterns": [],
            "key_observations": ["Fallback validation used"],
            "concerns": concerns,
            "suggested_adjustments": {},
            "pattern_clarity": 0.3,
            "optimal_entry_timeframe": signal.get("timeframe", "4H"),
            "overall_assessment": "Technical rule-based multi-timeframe validation",
        }

    def _calculate_enhanced_confidence(
        self,
        ml_confidence: float,
        llm_confidence: float,
        pattern_clarity: float,
        timeframe_alignment: float,
    ) -> float:
        """Calculate enhanced confidence score combining all factors.

        Args:
            ml_confidence: Original ML model confidence
            llm_confidence: LLM validation confidence
            pattern_clarity: Visual pattern clarity score
            timeframe_alignment: Multi-timeframe alignment score

        Returns:
            Enhanced confidence score
        """
        # Weighted average with emphasis on alignment
        weights = {"ml": 0.2, "llm": 0.3, "pattern": 0.2, "alignment": 0.3}

        enhanced = (
            ml_confidence * weights["ml"]
            + llm_confidence * weights["llm"]
            + pattern_clarity * weights["pattern"]
            + timeframe_alignment * weights["alignment"]
        )

        # Apply penalties
        if (
            min(ml_confidence, llm_confidence, pattern_clarity, timeframe_alignment)
            < 0.3
        ):
            enhanced *= 0.7  # Severe penalty for any very low score
        elif timeframe_alignment < 0.5:
            enhanced *= 0.85  # Penalty for poor alignment

        # Bonus for strong confluence
        if all(
            score > 0.7
            for score in [
                ml_confidence,
                llm_confidence,
                pattern_clarity,
                timeframe_alignment,
            ]
        ):
            enhanced = min(enhanced * 1.15, 1.0)

        return enhanced
