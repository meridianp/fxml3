"""Chart visualizations for FXML3."""

from typing import Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_candlestick_chart(
    df: pd.DataFrame,
    title: str = "Price Chart",
    volume: bool = True,
    figsize: Tuple[int, int] = (12, 8),
    indicators: Optional[List[str]] = None,
) -> plt.Figure:
    """Create a candlestick chart with matplotlib.

    Args:
        df: DataFrame with OHLCV data
        title: Chart title
        volume: Whether to include volume subplot
        figsize: Figure size
        indicators: List of indicators to include

    Returns:
        Matplotlib figure
    """
    # Ensure required columns exist
    required_columns = ["open", "high", "low", "close"]
    existing_columns = df.columns.tolist()

    for col in required_columns:
        if col not in existing_columns:
            raise ValueError(f"Required column '{col}' not found in DataFrame")

    # Set up figure and axes
    n_rows = 1 + (1 if volume and "volume" in df.columns else 0)

    fig, axes = plt.subplots(
        n_rows,
        1,
        figsize=figsize,
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1] if n_rows > 1 else [1]},
    )

    if n_rows == 1:
        axes = [axes]

    # Plot candlesticks
    price_ax = axes[0]

    # Up and down days
    up = df[df["close"] >= df["open"]]
    down = df[df["close"] < df["open"]]

    # Plot candlesticks
    width = 0.8
    width2 = 0.1

    # Up days
    price_ax.bar(
        up.index,
        up["close"] - up["open"],
        width,
        bottom=up["open"],
        color="green",
        alpha=0.5,
    )
    price_ax.bar(
        up.index,
        up["high"] - up["close"],
        width2,
        bottom=up["close"],
        color="green",
        alpha=0.5,
    )
    price_ax.bar(
        up.index,
        up["open"] - up["low"],
        width2,
        bottom=up["low"],
        color="green",
        alpha=0.5,
    )

    # Down days
    price_ax.bar(
        down.index,
        down["open"] - down["close"],
        width,
        bottom=down["close"],
        color="red",
        alpha=0.5,
    )
    price_ax.bar(
        down.index,
        down["high"] - down["open"],
        width2,
        bottom=down["open"],
        color="red",
        alpha=0.5,
    )
    price_ax.bar(
        down.index,
        down["close"] - down["low"],
        width2,
        bottom=down["low"],
        color="red",
        alpha=0.5,
    )

    # Plot indicators
    if indicators:
        for indicator in indicators:
            if indicator in df.columns:
                price_ax.plot(df.index, df[indicator], label=indicator)
            elif indicator.startswith("sma_") and indicator in df.columns:
                price_ax.plot(df.index, df[indicator], label=indicator)
            elif indicator.startswith("ema_") and indicator in df.columns:
                price_ax.plot(df.index, df[indicator], label=indicator)

    price_ax.set_title(title)
    price_ax.set_ylabel("Price")
    price_ax.grid(True)
    price_ax.legend()

    # Volume subplot if requested
    if volume and "volume" in df.columns and n_rows > 1:
        volume_ax = axes[1]
        volume_ax.bar(up.index, up["volume"], width, color="green", alpha=0.5)
        volume_ax.bar(down.index, down["volume"], width, color="red", alpha=0.5)
        volume_ax.set_ylabel("Volume")
        volume_ax.grid(True)

    plt.tight_layout()
    return fig


def plot_interactive_chart(
    df: pd.DataFrame,
    title: str = "Interactive Price Chart",
    volume: bool = True,
    indicators: Optional[Dict[str, List[str]]] = None,
    show_fibonacci: bool = False,
    show_waves: bool = False,
) -> go.Figure:
    """Create an interactive candlestick chart with Plotly.

    Args:
        df: DataFrame with OHLCV data
        title: Chart title
        volume: Whether to include volume subplot
        indicators: Dictionary mapping indicator type to list of column names
                   Example: {"ma": ["sma_20", "ema_50"], "oscillator": ["rsi_14"]}
        show_fibonacci: Whether to show Fibonacci levels
        show_waves: Whether to show detected Elliott waves

    Returns:
        Plotly figure
    """
    # Ensure required columns exist
    required_columns = ["open", "high", "low", "close"]
    existing_columns = df.columns.tolist()

    for col in required_columns:
        if col not in existing_columns:
            raise ValueError(f"Required column '{col}' not found in DataFrame")

    # Determine required subplots
    n_rows = 1
    row_heights = [0.7]

    # Add volume subplot if requested
    volume_present = volume and "volume" in df.columns
    if volume_present:
        n_rows += 1
        row_heights.append(0.15)

    # Add oscillator subplot if needed
    has_oscillators = False
    if indicators and "oscillator" in indicators:
        oscillator_cols = [col for col in indicators["oscillator"] if col in df.columns]
        if oscillator_cols:
            has_oscillators = True
            n_rows += 1
            row_heights.append(0.15)

    # Create subplot structure
    subplot_titles = [title]
    if volume_present:
        subplot_titles.append("Volume")
    if has_oscillators:
        subplot_titles.append("Indicators")

    # Create figure with subplots
    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=subplot_titles,
        row_heights=row_heights,
    )

    # Add candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
        ),
        row=1,
        col=1,
    )

    # Add moving averages and other price indicators
    if indicators and "ma" in indicators:
        for ma in indicators["ma"]:
            if ma in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df[ma],
                        name=ma,
                        line=dict(width=1),
                    ),
                    row=1,
                    col=1,
                )

    # Add Bollinger Bands
    if indicators and "bollinger" in indicators:
        for bb in indicators["bollinger"]:
            if bb.startswith("bb_") and bb in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df[bb],
                        name=bb,
                        line=dict(width=1, dash="dash"),
                    ),
                    row=1,
                    col=1,
                )

    # Add volume
    current_row = 2
    if volume_present:
        colors = [
            "green" if row["close"] >= row["open"] else "red"
            for _, row in df.iterrows()
        ]

        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["volume"],
                name="Volume",
                marker=dict(color=colors),
            ),
            row=current_row,
            col=1,
        )
        current_row += 1

    # Add oscillators (e.g., RSI, MACD)
    if has_oscillators:
        for osc in indicators["oscillator"]:
            if osc in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df[osc],
                        name=osc,
                        line=dict(width=1),
                    ),
                    row=current_row,
                    col=1,
                )

        # Add horizontal lines for RSI
        for osc in indicators["oscillator"]:
            if osc.startswith("rsi_"):
                fig.add_shape(
                    type="line",
                    x0=df.index[0],
                    y0=70,
                    x1=df.index[-1],
                    y1=70,
                    line=dict(color="red", width=1, dash="dash"),
                    row=current_row,
                    col=1,
                )
                fig.add_shape(
                    type="line",
                    x0=df.index[0],
                    y0=30,
                    x1=df.index[-1],
                    y1=30,
                    line=dict(color="green", width=1, dash="dash"),
                    row=current_row,
                    col=1,
                )

    # Add Fibonacci retracement levels if requested
    if show_fibonacci:
        fib_levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]

        # Find relevant high and low for Fibonacci levels
        price_max = df["high"].max()
        price_min = df["low"].min()
        price_range = price_max - price_min

        for level in fib_levels:
            level_price = price_max - (price_range * level)
            fig.add_shape(
                type="line",
                x0=df.index[0],
                y0=level_price,
                x1=df.index[-1],
                y1=level_price,
                line=dict(color="purple", width=1, dash="dot"),
                row=1,
                col=1,
            )
            fig.add_annotation(
                x=df.index[0],
                y=level_price,
                text=f"{level:.3f}",
                showarrow=False,
                xshift=-40,
                row=1,
                col=1,
            )

    # Add detected waves if requested
    if show_waves:
        wave_cols = [
            col
            for col in df.columns
            if col.startswith("impulse_wave_") or col.startswith("corrective_wave_")
        ]

        if wave_cols:
            for wave_col in wave_cols:
                wave_values = df[wave_col].values
                for wave_num in range(1, 6):  # For impulse waves 1-5
                    if wave_num in wave_values:
                        wave_df = df[df[wave_col] == wave_num]
                        fig.add_trace(
                            go.Scatter(
                                x=wave_df.index,
                                y=wave_df["high"],
                                name=f"Wave {wave_num}",
                                mode="markers",
                                marker=dict(
                                    symbol=(
                                        "triangle-down"
                                        if wave_num % 2 == 0
                                        else "triangle-up"
                                    ),
                                    size=10,
                                    color=f"rgba({50*wave_num}, 100, 200, 0.8)",
                                ),
                            ),
                            row=1,
                            col=1,
                        )

    # Update layout
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    # Update y-axis properties
    fig.update_yaxes(autorange=True, fixedrange=False)

    # Set background colors
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    return fig


def plot_wave_analysis(
    df: pd.DataFrame,
    title: str = "Elliott Wave Analysis",
    wave_col: str = "impulse_wave_5",
) -> go.Figure:
    """Create a specialized chart for Elliott Wave analysis.

    Args:
        df: DataFrame with OHLCV and wave data
        title: Chart title
        wave_col: Column containing wave numbers

    Returns:
        Plotly figure
    """
    # Ensure required columns exist
    required_columns = ["open", "high", "low", "close"]
    existing_columns = df.columns.tolist()

    for col in required_columns:
        if col not in existing_columns:
            raise ValueError(f"Required column '{col}' not found in DataFrame")

    if wave_col not in existing_columns:
        raise ValueError(f"Wave column '{wave_col}' not found in DataFrame")

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add candlestick trace
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
        ),
        secondary_y=False,
    )

    # Add wave numbers as annotations
    wave_numbers = sorted(df[df[wave_col] > 0][wave_col].unique())

    for wave_num in wave_numbers:
        wave_df = df[df[wave_col] == wave_num]

        if len(wave_df) == 0:
            continue

        # Calculate average price for annotation
        if wave_num % 2 == 0:  # Even waves (2,4) are down
            anchor_price = wave_df["low"].iloc[len(wave_df) // 2]
        else:  # Odd waves (1,3,5) are up
            anchor_price = wave_df["high"].iloc[len(wave_df) // 2]

        # Get datetime for middle of wave
        anchor_date = wave_df.index[len(wave_df) // 2]

        # Add annotation
        fig.add_annotation(
            x=anchor_date,
            y=anchor_price,
            text=str(int(wave_num)),
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor="#636363",
            font=dict(size=20, color="black"),
            bordercolor="#c7c7c7",
            borderwidth=2,
            borderpad=4,
            bgcolor="#ff7f0e" if wave_num % 2 == 0 else "#2ca02c",
            opacity=0.8,
        )

        # Add lines connecting waves
        if wave_num > 1:
            prev_wave_df = df[df[wave_col] == wave_num - 1]
            if len(prev_wave_df) == 0:
                continue

            # Get end of previous wave and start of current wave
            if (wave_num - 1) % 2 == 0:  # Previous wave is down
                prev_end = prev_wave_df["low"].iloc[-1]
            else:  # Previous wave is up
                prev_end = prev_wave_df["high"].iloc[-1]

            prev_date = prev_wave_df.index[-1]

            if wave_num % 2 == 0:  # Current wave is down
                curr_start = wave_df["high"].iloc[0]
            else:  # Current wave is up
                curr_start = wave_df["low"].iloc[0]

            curr_date = wave_df.index[0]

            # Add connecting line
            fig.add_shape(
                type="line",
                x0=prev_date,
                y0=prev_end,
                x1=curr_date,
                y1=curr_start,
                line=dict(color="blue", width=2, dash="dash"),
            )

    # Update layout
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        template="plotly_white",
    )

    # Hide secondary y-axis
    fig.update_yaxes(showticklabels=False, secondary_y=True)

    return fig
