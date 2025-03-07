# Visualization Module

The Visualization module provides tools for creating interactive charts and visualizations for forex data and Elliott Wave analysis.

## Component Overview

The Visualization module offers multiple visualization options to meet different needs:

1. **Static Charts**: Matplotlib-based charts for reports and publications
2. **Interactive Charts**: Plotly-based interactive charts for analysis and exploration
3. **Specialized Wave Charts**: Elliott Wave-specific visualizations with wave annotations
4. **Streamlit Integration**: Dashboard components for the web interface

## Candlestick Charts

The most basic visualization is the candlestick chart, which shows OHLC (Open, High, Low, Close) data:

```python
from fxml3.visualization.chart import plot_candlestick_chart
import pandas as pd

# Assuming df is a pandas DataFrame with OHLCV data
fig = plot_candlestick_chart(
    df,
    title="EUR/USD Daily Chart",
    volume=True,  # Whether to include volume subplot
    figsize=(12, 8),  # Figure size in inches
    indicators=["sma_20", "ema_50"],  # Technical indicators to include
)

# For displaying in Jupyter or saving to file
fig.savefig("eurusd_chart.png", dpi=300)
```

This creates a static candlestick chart using matplotlib, suitable for reports and publications.

## Interactive Charts

For more dynamic analysis, the module provides interactive charts using Plotly:

```python
from fxml3.visualization.chart import plot_interactive_chart

fig = plot_interactive_chart(
    df,
    title="EUR/USD Interactive Chart",
    volume=True,  # Include volume subplot
    indicators={
        "ma": ["sma_20", "ema_50", "sma_200"],  # Moving averages
        "oscillator": ["rsi_14"],  # Oscillators in separate subplot
        "bollinger": ["bb_20_upper", "bb_20_middle", "bb_20_lower"],  # Bollinger bands
    },
    show_fibonacci=True,  # Show Fibonacci retracement levels
    show_waves=False,  # Show detected Elliott waves (if available in the dataframe)
)

# For displaying in Jupyter, Streamlit, or as standalone HTML
fig.show()
# For saving to HTML file
fig.write_html("eurusd_interactive.html")
```

Interactive charts offer several advantages:

- **Zoom and Pan**: Explore specific time periods or price ranges
- **Hover Information**: Get detailed data when hovering over candles
- **Toggling**: Show/hide specific indicators or components
- **Export**: Export the chart as PNG or interactive HTML

## Elliott Wave Visualization

The module includes specialized visualization for Elliott Wave analysis:

```python
from fxml3.visualization.chart import plot_wave_analysis

fig = plot_wave_analysis(
    df,  # DataFrame with wave labels (must have "impulse_wave_X" column)
    title="EUR/USD Elliott Wave Analysis",
    wave_col="impulse_wave_5",  # Column containing wave numbers
)

fig.show()
```

This creates a specialized chart that displays:

- **Wave Numbers**: Labels for each wave (1-2-3-4-5 for impulse waves, A-B-C for corrective)
- **Wave Connections**: Lines connecting wave start/end points
- **Wave Annotations**: Additional information about wave structure

## Combining Multiple Charts

For comprehensive analysis, you can create multiple charts in a single dashboard:

```python
import plotly.subplots as sp

# Create individual figures
price_fig = plot_interactive_chart(df, volume=False)
wave_fig = plot_wave_analysis(df, wave_col="impulse_wave_5")

# Combine into a single figure
combined_fig = sp.make_subplots(rows=2, cols=1, shared_xaxes=True)

# Add traces from both figures
for trace in price_fig.data:
    combined_fig.add_trace(trace, row=1, col=1)
for trace in wave_fig.data:
    combined_fig.add_trace(trace, row=2, col=1)

# Update layout
combined_fig.update_layout(
    title="EUR/USD Price and Wave Analysis",
    height=800,
)

combined_fig.show()
```

## Streamlit Integration

The module integrates with Streamlit to create interactive web dashboards:

```python
import streamlit as st
from fxml3.visualization.chart import plot_interactive_chart

# Load data (assuming you have a DataFrame 'df')
# ...

# Create interactive chart
fig = plot_interactive_chart(
    df,
    title="EUR/USD Analysis",
    volume=True,
    indicators={"ma": ["sma_20", "sma_50"]},
)

# Display in Streamlit
st.plotly_chart(fig, use_container_width=True)
```

This integrates seamlessly with the Streamlit UI, allowing for interactive data exploration and analysis.

## Customization Options

The visualization module offers extensive customization options:

### Chart Appearance

```python
# For matplotlib charts
fig = plot_candlestick_chart(
    df,
    title="Custom Chart",
    figsize=(15, 10),
    # Custom colors
    up_color="green",
    down_color="red",
    volume_up_color="darkgreen",
    volume_down_color="darkred",
    grid=True,
    # Custom fonts
    title_fontsize=16,
    axis_fontsize=12,
)

# For Plotly charts
fig = plot_interactive_chart(
    df,
    title="Custom Interactive Chart",
    # Custom theme
    template="plotly_dark",  # Options: "plotly_white", "plotly_dark", "ggplot2", etc.
    # Custom colors
    candle_up_color="lime",
    candle_down_color="crimson",
)
```

### Indicator Styling

```python
# For matplotlib charts
fig = plot_candlestick_chart(
    df,
    indicators=["sma_20", "ema_50"],
    indicator_colors=["blue", "red"],
    indicator_styles=["-", "--"],  # Line styles
    indicator_widths=[1, 2],  # Line widths
)

# For Plotly charts
fig = plot_interactive_chart(
    df,
    indicators={
        "ma": ["sma_20", "ema_50"],
    },
    indicator_styles={
        "sma_20": {"color": "blue", "width": 1, "dash": "solid"},
        "ema_50": {"color": "red", "width": 2, "dash": "dash"},
    },
)
```

### Wave Annotation Styling

```python
fig = plot_wave_analysis(
    df,
    wave_col="impulse_wave_5",
    # Custom wave styling
    wave_colors={
        1: "green",
        2: "red",
        3: "green",
        4: "red",
        5: "green",
    },
    annotation_size=15,
    line_width=2,
)
```

## Advanced Features

### Multi-Timeframe Analysis

```python
from fxml3.visualization.chart import plot_multi_timeframe

figs = plot_multi_timeframe(
    symbol="EURUSD",
    timeframes=["1D", "4H", "1H"],
    start_date="2023-01-01",
    end_date="2023-01-31",
    data_source="yahoo",
    indicators={"ma": ["sma_20"]},
)

# Display each chart
for tf, fig in figs.items():
    st.subheader(f"{tf} Chart")
    st.plotly_chart(fig)
```

### Comparison Charts

```python
from fxml3.visualization.chart import plot_comparison

fig = plot_comparison(
    symbols=["EURUSD", "GBPUSD", "USDJPY"],
    start_date="2023-01-01",
    end_date="2023-12-31",
    timeframe="1D",
    normalize=True,  # Normalize to same starting point
    data_source="yahoo",
)

fig.show()
```

### Chart Annotations

```python
fig = plot_interactive_chart(df)

# Add custom annotations
fig.add_annotation(
    x="2023-01-15",  # Date
    y=1.05,  # Price level
    text="Key reversal",
    showarrow=True,
    arrowhead=1,
)

# Add shapes (lines, rectangles, etc.)
fig.add_shape(
    type="line",
    x0="2023-01-01",
    y0=1.05,
    x1="2023-01-31",
    y1=1.05,
    line=dict(color="red", width=2, dash="dash"),
)

fig.show()
```

## Performance Tips

For optimal performance when working with visualizations:

1. **Limit Data Size**: Focus on specific time periods rather than visualizing all data
2. **Selective Indicators**: Include only the most relevant indicators
3. **Use Static Charts for Large Datasets**: Interactive charts can become slow with very large datasets
4. **Export to HTML**: For sharing interactive charts without running the code

## Next Steps

After creating visualizations with the Visualization module, you can:

1. Integrate them into the Streamlit UI
2. Export for reports and presentations
3. Use them to validate Elliott Wave analysis results