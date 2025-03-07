# FXML3 System Architecture

This document provides an overview of the FXML3 system architecture, including its components, data flow, and design patterns.

## Architecture Overview

FXML3 follows a multi-agent architecture pattern, where specialized components work together to perform Elliott Wave analysis and generate trading signals. The system is designed to be modular, allowing for easy extension and replacement of components.

![FXML3 Architecture Diagram](assets/architecture_diagram.png)

## Core Components

### Data Engineering

The Data Engineering module is responsible for acquiring, cleaning, and preprocessing financial data. It includes:

- **Data Feeds**: Interface with external data sources (Yahoo Finance, FXCM, Interactive Brokers)
- **Data Loader**: Unified API for loading data from different sources
- **Preprocessing**: Cleaning, normalization, and feature engineering
- **Pipeline**: End-to-end data processing workflow

### Wave Analysis

The Wave Analysis module is the core of the system, implementing Elliott Wave pattern detection:

- **Peak/Trough Detection**: Identifies potential turning points in price data
- **Fibonacci Validation**: Validates wave relationships using Fibonacci ratios
- **Pattern Recognition**: Identifies impulse and corrective wave patterns
- **Wave Labeling**: Labels waves according to Elliott Wave Principle

### LLM Integration

The LLM Integration module enhances wave detection using large language models:

- **Knowledge Base**: Elliott Wave theory texts and examples
- **RAG System**: Retrieval-augmented generation for wave validation
- **Prompt Generation**: Creates prompts for LLM analysis
- **Response Parsing**: Interprets LLM outputs for wave confirmation

### Reinforcement Learning

The Reinforcement Learning module optimizes wave detection parameters:

- **Environment**: Simulated trading environment for wave detection
- **Agent**: DRL agent that learns optimal parameters
- **Reward Function**: Based on wave detection accuracy and profit
- **Experience Replay**: Storage for training examples

### Visualization

The Visualization module provides interactive charts and dashboards:

- **Chart Library**: Candlestick charts with technical indicators
- **Wave Visualization**: Visual representation of detected waves
- **Dashboard**: Comprehensive analysis interface
- **Export**: Tools for exporting charts and analysis

### Strategy Generation

The Strategy Generation module creates trading signals:

- **Entry/Exit Rules**: Based on wave patterns
- **Risk Management**: Stop loss and take profit placement
- **Position Sizing**: Risk-based position sizing
- **Portfolio Management**: Multi-pair strategy integration

## Data Flow

1. **Data Acquisition**: External data sources → Data Feeds → Data Loader
2. **Preprocessing**: Data Loader → Cleaning → Feature Engineering → Normalized Data
3. **Wave Analysis**: Normalized Data → Peak/Trough Detection → Wave Identification → Labeled Waves
4. **LLM Validation**: Labeled Waves → LLM Prompts → LLM API → Validated Waves
5. **Strategy Generation**: Validated Waves → Signal Generation → Trading Strategy
6. **Visualization**: All Stages → Interactive Charts → User Interface

## Design Patterns

FXML3 employs several design patterns to ensure maintainability and extensibility:

### Factory Pattern

Used in the Data Feeds module to create the appropriate data feed based on configuration:

```python
# Factory function in data_feeds/__init__.py
def create_data_feed(source_type, **kwargs):
    source_map = {
        "yahoo": YahooDataFeed,
        "csv": CSVDataFeed,
        # ...
    }
    return source_map[source_type](**kwargs)
```

### Strategy Pattern

Used in the preprocessing module to apply different normalization strategies:

```python
# Different normalization strategies in preprocessing.py
if method == "min_max":
    # Min-max scaling implementation
elif method == "z_score":
    # Z-score normalization implementation
elif method == "decimal_scaling":
    # Decimal scaling implementation
```

### Observer Pattern

Used for logging and monitoring throughout the system:

```python
# Pipeline emits events during processing
logger.info(f"Processing complete. Original shape: {metadata['original_shape']}, Final shape: {metadata['final_shape']}")
```

### Dependency Injection

Used to provide configurable dependencies to components:

```python
# DataPipeline receives a data loader instance
self.data_loader = ForexDataLoader(
    data_source=data_source,
    cache_dir=cache_dir,
    **kwargs,
)
```

## Configuration Management

FXML3 uses a multi-layered configuration approach:

1. **Default Values**: Hardcoded defaults in the codebase
2. **YAML Configuration**: Override defaults with YAML config files
3. **Environment Variables**: Override YAML settings with environment variables
4. **Command Line Arguments**: Highest precedence for specific runs

This hierarchy allows for flexible configuration while maintaining sensible defaults.

## Error Handling

The system employs comprehensive error handling:

- **Input Validation**: Validates inputs before processing
- **Graceful Degradation**: Falls back to alternatives when components fail
- **Detailed Logging**: Captures errors with contextual information
- **User Feedback**: Provides clear error messages to users

## Future Architecture Enhancements

Planned architectural improvements:

1. **Microservices**: Split into independent services for better scalability
2. **Real-time Processing**: Support for streaming data
3. **Distributed Computing**: Parallel processing for large-scale analysis
4. **Cloud Deployment**: Containerization and cloud-native deployment
5. **API Gateway**: Unified API interface for external integrations