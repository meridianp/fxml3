# Getting Started with FXML3

This guide will help you set up and start using the FXML3 system for Elliott Wave analysis.

## Installation

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Git (optional, for cloning the repository)

### Setting Up a Virtual Environment

It's recommended to use a virtual environment for FXML3:

```bash
# Clone the repository (if you haven't already)
git clone https://github.com/yourusername/fxml3.git
cd fxml3

# Create a virtual environment
python3.11 -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Installing Dependencies

Install all required dependencies:

```bash
# Install core dependencies
pip install -e .

# Install development dependencies
pip install -e ".[dev]"

# Install optional API dependencies
pip install -e ".[api]"
```

## Basic Usage

### Data Retrieval and Processing

```python
from fxml3.data_engineering.pipeline import DataPipeline

# Initialize the pipeline with Yahoo Finance as data source
pipeline = DataPipeline(data_source="yahoo", cache_dir="data/cache")

# Configure the pipeline
pipeline.set_config(
    clean_data=True,
    add_indicators=True,
    normalize=False,
    add_candlestick_patterns=True,
    add_fibonacci_features=True,
    add_trend_features=True,
    indicators=["sma", "ema", "rsi", "macd", "bollinger"],
    periods=[14, 20, 50, 200],
)

# Process data for a forex pair
data, metadata = pipeline.process(
    symbol="EURUSD",
    start_date="2023-01-01",
    end_date="2023-12-31",
    timeframe="1D",
)
```

### Visualization

```python
from fxml3.visualization.chart import plot_interactive_chart

# Create an interactive chart
fig = plot_interactive_chart(
    data,
    title="EUR/USD Daily Chart",
    volume=True,
    indicators={
        "ma": ["sma_20", "sma_50", "ema_200"],
        "oscillator": ["rsi_14"],
        "bollinger": ["bb_20_upper", "bb_20_middle", "bb_20_lower"],
    },
    show_fibonacci=True,
)

# Display the chart (in Jupyter or Streamlit)
fig.show()
```

## Configuration

### Environment Variables

Create a `.env` file in the project root to configure the application:

```
# Data Feed Credentials
FOREX_API_KEY=your_forex_api_key_here
FXCM_API_KEY=your_fxcm_api_key_here
FXCM_ACCESS_TOKEN=your_fxcm_access_token_here
IB_ACCOUNT_ID=your_ib_account_id_here

# Data Settings
DATA_SOURCE=yahoo  # yahoo, fxcm, ib, csv
DATA_CACHE_DIR=data/cache
CSV_DATA_DIR=data/csv
```

### YAML Configuration

You can also use YAML configuration files. Create a custom config in the `config/` directory:

```yaml
# Data settings
data:
  source: yahoo
  symbols:
    - EURUSD=X
    - GBPUSD=X
    - USDJPY=X
  timeframes:
    - 1H
    - 4H
    - 1D
  start_date: 2020-01-01
  cache_dir: data/cache

# Elliott Wave Analysis settings
wave:
  min_wave_size: 0.01
  max_wave_size: 10.0
  fib_tolerance: 0.1
```

Then load it in your application:

```python
from fxml3.config import Config

config = Config.from_yaml("config/my_config.yaml")
```

## Command Line Interface

FXML3 provides a command-line interface for common operations:

```bash
# Run the data fetching module
python run.py --mode fetch --symbols EURUSD=X GBPUSD=X --timeframes 1D --start-date 2023-01-01

# Run the analysis module
python run.py --mode analyze --symbols EURUSD=X --timeframes 1D

# Start the Streamlit UI
python run.py --mode ui
```

## Next Steps

- Read the [Architecture](architecture.md) documentation for an overview of the system design
- Learn more about the [Data Engineering](data-engineering.md) module
- Explore the [Visualization](visualization.md) capabilities
- Dive into [Elliott Wave Analysis](elliott-wave-analysis.md) functionality