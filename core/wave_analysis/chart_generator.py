"""Chart generation utilities for Elliott Wave analysis."""

import base64
import io
from typing import Dict, List, Optional, Tuple

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle


class ElliottWaveChartGenerator:
    """Generate annotated charts for Elliott Wave analysis."""

    def __init__(self):
        # Color scheme
        self.colors = {
            "impulse": "#2E86AB",  # Blue for impulse waves
            "corrective": "#E63946",  # Red for corrective waves
            "fibonacci": "#FFB700",  # Gold for Fibonacci levels
            "support": "#06D6A0",  # Green for support
            "resistance": "#E63946",  # Red for resistance
            "background": "#F8F9FA",
            "grid": "#DEE2E6",
        }

        # Style configuration
        self.style = mpf.make_mpf_style(
            base_mpf_style="charles",
            gridstyle=":",
            gridcolor=self.colors["grid"],
            facecolor=self.colors["background"],
            edgecolor="black",
            figcolor="white",
        )

    def generate_elliott_wave_chart(
        self,
        price_data: pd.DataFrame,
        wave_patterns: List[Dict],
        fibonacci_levels: Optional[Dict] = None,
        indicators: List[str] = ["volume", "rsi"],
        title: str = "Elliott Wave Analysis",
    ) -> Tuple[plt.Figure, str]:
        """Generate a comprehensive Elliott Wave chart with annotations.

        Returns:
            Tuple of (figure, base64_encoded_image)
        """
        # Ensure we have OHLCV data with datetime index
        if not isinstance(price_data.index, pd.DatetimeIndex):
            price_data = price_data.copy()
            price_data.index = pd.to_datetime(price_data.index)

        # Calculate additional plots
        additional_plots = self._prepare_additional_plots(price_data, indicators)

        # Create the chart
        fig, axes = mpf.plot(
            price_data,
            type="candle",
            style=self.style,
            volume=("volume" in indicators and "volume" in price_data.columns),
            addplot=additional_plots,
            returnfig=True,
            figsize=(14, 10),
            title=title,
            ylabel="Price",
            ylabel_lower="Volume" if "volume" in indicators else None,
        )

        # Get the main price axis
        ax_price = axes[0]

        # Add wave annotations
        self._add_wave_annotations(ax_price, price_data, wave_patterns)

        # Add Fibonacci levels
        if fibonacci_levels:
            self._add_fibonacci_levels(ax_price, fibonacci_levels, price_data)

        # Add support/resistance zones
        self._add_support_resistance(ax_price, price_data)

        # Add info box
        self._add_info_box(ax_price, price_data, wave_patterns)

        # Convert to base64
        buffer = io.BytesIO()
        fig.savefig(
            buffer,
            format="png",
            dpi=150,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return fig, image_base64

    def _prepare_additional_plots(
        self, data: pd.DataFrame, indicators: List[str]
    ) -> List:
        """Prepare additional indicator plots."""
        plots = []

        # RSI
        if "rsi" in indicators and "rsi_14" in data.columns:
            # RSI plot
            plots.append(
                mpf.make_addplot(
                    data["rsi_14"], panel=2, color="purple", ylabel="RSI", ylim=(0, 100)
                )
            )

            # Overbought/Oversold lines
            plots.append(
                mpf.make_addplot(
                    pd.Series(70, index=data.index),
                    panel=2,
                    color="red",
                    linestyle="--",
                    alpha=0.5,
                )
            )
            plots.append(
                mpf.make_addplot(
                    pd.Series(30, index=data.index),
                    panel=2,
                    color="green",
                    linestyle="--",
                    alpha=0.5,
                )
            )

        # Moving averages
        for ma_col in ["sma_20", "sma_50", "sma_200"]:
            if ma_col in data.columns:
                period = int(ma_col.split("_")[1])
                color = "blue" if period == 20 else "orange" if period == 50 else "red"
                plots.append(
                    mpf.make_addplot(data[ma_col], panel=0, color=color, alpha=0.8)
                )

        return plots

    def _add_wave_annotations(self, ax, data: pd.DataFrame, wave_patterns: List[Dict]):
        """Add Elliott Wave annotations to the chart."""

        for pattern in wave_patterns:
            pattern_type = pattern.get("pattern_type", "unknown")
            waves = pattern.get("waves", [])
            confidence = pattern.get("confidence", 0)

            # Skip low confidence patterns
            if confidence < 0.5:
                continue

            # Draw wave connections
            for i, wave in enumerate(waves):
                if i == 0:
                    continue

                # Get coordinates
                prev_wave = waves[i - 1]

                # Convert indices to matplotlib coordinates
                x1 = prev_wave["end_idx"]
                y1 = prev_wave["end_price"]
                x2 = wave["end_idx"]
                y2 = wave["end_price"]

                # Draw wave line
                color = (
                    self.colors["impulse"]
                    if pattern_type == "impulse"
                    else self.colors["corrective"]
                )
                ax.plot([x1, x2], [y1, y2], color=color, alpha=0.7)

                # Add wave label
                wave_label = (
                    str(i + 1) if pattern_type == "impulse" else chr(65 + i)
                )  # 1-5 or A-C
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2

                # Create fancy label
                bbox_props = dict(
                    boxstyle="round,pad=0.3",
                    facecolor="white",
                    edgecolor=color,
                    alpha=0.9,
                )
                ax.text(
                    mid_x,
                    mid_y,
                    wave_label,
                    bbox=bbox_props,
                    fontsize=10,
                    fontweight="bold",
                    ha="center",
                    va="center",
                )

        # Add wave count summary
        if wave_patterns:
            best_pattern = max(wave_patterns, key=lambda x: x.get("confidence", 0))
            pattern_text = f"{best_pattern['pattern_type'].upper()} Pattern\nConfidence: {best_pattern['confidence']:.0%}"

            ax.text(
                0.02,
                0.98,
                pattern_text,
                transform=ax.transAxes,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
                fontsize=10,
            )

    def _add_fibonacci_levels(self, ax, fib_levels: Dict, data: pd.DataFrame):
        """Add Fibonacci retracement/extension levels."""

        # Get price range for positioning
        y_min, y_max = ax.get_ylim()
        x_max = len(data)

        for level_name, level_price in fib_levels.items():
            if y_min <= level_price <= y_max:
                # Draw level
                ax.axhline(
                    y=level_price,
                    color=self.colors["fibonacci"],
                    linestyle="--",
                    alpha=0.6,
                )

                # Add label
                ax.text(
                    x_max * 0.98,
                    level_price,
                    f" {level_name}",
                    ha="right",
                    va="center",
                    bbox=dict(
                        boxstyle="round,pad=0.2",
                        facecolor=self.colors["fibonacci"],
                        alpha=0.3,
                    ),
                    fontsize=8,
                )

    def _add_support_resistance(self, ax, data: pd.DataFrame):
        """Add support and resistance zones."""

        # Find recent swing highs and lows
        window = 20

        # Recent highs (resistance)
        recent_highs = data["high"].rolling(window).max()
        resistance_levels = recent_highs.dropna().unique()[-3:]  # Top 3 recent

        # Recent lows (support)
        recent_lows = data["low"].rolling(window).min()
        support_levels = recent_lows.dropna().unique()[:3]  # Bottom 3 recent

        # Draw zones
        x_max = len(data)

        for resistance in resistance_levels:
            ax.axhline(
                y=resistance, color=self.colors["resistance"], linestyle=":", alpha=0.5
            )
            ax.text(
                x_max * 0.02,
                resistance,
                "R",
                color=self.colors["resistance"],
                fontweight="bold",
                va="center",
            )

        for support in support_levels:
            ax.axhline(
                y=support, color=self.colors["support"], linestyle=":", alpha=0.5
            )
            ax.text(
                x_max * 0.02,
                support,
                "S",
                color=self.colors["support"],
                fontweight="bold",
                va="center",
            )

    def _add_info_box(self, ax, data: pd.DataFrame, wave_patterns: List[Dict]):
        """Add information box with key metrics."""

        current_price = data["close"].iloc[-1]
        price_change = data["close"].pct_change().iloc[-1] * 100

        # Calculate metrics
        atr = data.get("atr_14", data["high"] - data["low"]).iloc[-1]
        rsi = data.get("rsi_14", pd.Series()).iloc[-1] if "rsi_14" in data else None

        info_text = f"Current: {current_price:.5f} ({price_change:+.2f}%)\n"
        info_text += f"ATR: {atr:.5f}\n"
        if rsi:
            info_text += f"RSI: {rsi:.1f}\n"
        info_text += f"Patterns Found: {len(wave_patterns)}"

        # Add info box
        props = dict(boxstyle="round", facecolor="lightblue", alpha=0.8)
        ax.text(
            0.98,
            0.02,
            info_text,
            transform=ax.transAxes,
            fontsize=9,
            verticalalignment="bottom",
            horizontalalignment="right",
            bbox=props,
        )


def create_multi_timeframe_chart(
    symbol: str,
    data_4h: pd.DataFrame,
    data_1d: pd.DataFrame,
    wave_patterns_4h: List[Dict],
    wave_patterns_1d: List[Dict],
) -> Tuple[plt.Figure, str]:
    """Create a multi-timeframe Elliott Wave chart."""

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 12), gridspec_kw={"height_ratios": [1, 1]}
    )

    # Create generator
    generator = ElliottWaveChartGenerator()

    # Plot 4H chart
    plt.sca(ax1)
    generator.generate_elliott_wave_chart(
        data_4h.tail(100), wave_patterns_4h, title=f"{symbol} 4H Elliott Wave Analysis"
    )

    # Plot Daily chart
    plt.sca(ax2)
    generator.generate_elliott_wave_chart(
        data_1d.tail(100),
        wave_patterns_1d,
        title=f"{symbol} Daily Elliott Wave Analysis",
    )

    plt.tight_layout()

    # Convert to base64
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return fig, image_base64
