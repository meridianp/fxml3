# Visualization API Reference

This document provides detailed API reference for the Visualization module.

> Note: This API documentation is under development and will be expanded as the project progresses.

## Chart Module

### Candlestick Charts

```python
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
```

### Interactive Charts

```python
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
```

### Elliott Wave Visualization

```python
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
```

## Extended Visualization Functions

These functions are planned for future implementation:

### Multi-Timeframe Analysis

```python
def plot_multi_timeframe(
    symbol: str,
    timeframes: List[str],
    start_date: str,
    end_date: str,
    data_source: str = "yahoo",
    indicators: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, go.Figure]:
    """Create charts for multiple timeframes.
    
    Args:
        symbol: Symbol to chart
        timeframes: List of timeframes to display
        start_date: Start date
        end_date: End date
        data_source: Data source to use
        indicators: Dictionary of indicators to display
        
    Returns:
        Dictionary mapping timeframes to Plotly figures
    """
```

### Comparison Charts

```python
def plot_comparison(
    symbols: List[str],
    start_date: str,
    end_date: str,
    timeframe: str = "1D",
    normalize: bool = True,
    data_source: str = "yahoo",
) -> go.Figure:
    """Create a comparison chart for multiple symbols.
    
    Args:
        symbols: List of symbols to compare
        start_date: Start date
        end_date: End date
        timeframe: Timeframe for the data
        normalize: Whether to normalize prices to the same starting point
        data_source: Data source to use
        
    Returns:
        Plotly figure with comparison chart
    """
```

### Indicator Plots

```python
def plot_indicators(
    df: pd.DataFrame,
    indicators: List[str],
    title: str = "Technical Indicators",
) -> go.Figure:
    """Create a specialized plot for technical indicators.
    
    Args:
        df: DataFrame with OHLCV and indicator data
        indicators: List of indicators to plot
        title: Chart title
        
    Returns:
        Plotly figure with indicator plots
    """
```

### Chart Patterns Visualization

```python
def plot_chart_patterns(
    df: pd.DataFrame,
    patterns: List[str] = None,
    title: str = "Chart Patterns",
) -> go.Figure:
    """Create a visualization of detected chart patterns.
    
    Args:
        df: DataFrame with OHLCV and pattern data
        patterns: List of patterns to highlight
        title: Chart title
        
    Returns:
        Plotly figure with highlighted patterns
    """
```

## Streamlit Components

These components are planned for integration with the Streamlit UI:

### Chart Dashboard

```python
def create_chart_dashboard(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "1D",
    data_source: str = "yahoo",
) -> None:
    """Create a complete chart dashboard in Streamlit.
    
    Args:
        symbol: Symbol to chart
        start_date: Start date
        end_date: End date
        timeframe: Timeframe for the data
        data_source: Data source to use
    """
```

### Wave Analysis Dashboard

```python
def create_wave_dashboard(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "1D",
    data_source: str = "yahoo",
) -> None:
    """Create an Elliott Wave analysis dashboard in Streamlit.
    
    Args:
        symbol: Symbol to analyze
        start_date: Start date
        end_date: End date
        timeframe: Timeframe for the data
        data_source: Data source to use
    """
```

### Multi-Symbol Dashboard

```python
def create_multi_symbol_dashboard(
    symbols: List[str],
    start_date: str,
    end_date: str,
    timeframe: str = "1D",
    data_source: str = "yahoo",
) -> None:
    """Create a dashboard for multiple symbols in Streamlit.
    
    Args:
        symbols: List of symbols to display
        start_date: Start date
        end_date: End date
        timeframe: Timeframe for the data
        data_source: Data source to use
    """
```