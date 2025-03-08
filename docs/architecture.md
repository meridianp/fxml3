# FXML3 System Architecture

This document provides an overview of the FXML3 system architecture, designed based on the multi-agent approach outlined in the reference scientific paper.

## Multi-Agent System Architecture

FXML3 implements a decentralized, agent-oriented architecture where different specialized components work together to perform Elliott Wave analysis and generate trading signals. 

![FXML3 Architecture Diagram](assets/architecture_diagram.png)

### Hierarchical Agent Coordination

The system follows a hierarchical design with:

1. **Main Coordination Agent**: Orchestrates all sub-agents and manages the overall workflow
2. **Task-Specific Agents**: Specialized agents handling distinct responsibilities:
   - Data Retrieval Agent
   - Preprocessing Agent
   - Wave Detection Agent
   - LLM Reasoning Agent
   - DRL Optimization Agent
   - Visualization Agent
   - Trading Strategy Agent

### Task Decomposition and Dynamic Scaling

The multi-agent design enables:
- Parallel execution of independent tasks
- Dynamic resource allocation based on workload
- Fault isolation and graceful degradation
- Modular development and testing

## Core Components

### Data Engineering

The Data Engineering module acquires, cleans, and preprocesses financial data:

- **Data Feeds**: Interface with external data sources (Yahoo Finance, FXCM, Interactive Brokers)
- **Data Loader**: Unified API for loading data from different sources
- **Preprocessing**: Cleaning, normalization, and feature engineering
- **Pipeline**: End-to-end data processing workflow

### Elliott Wave Principle (EWP) Implementation

The Wave Analysis module implements comprehensive Elliott Wave pattern detection:

- **Peak/Trough Detection**: Identifies potential turning points in price data
- **Fractal Structure Handling**: Multi-timeframe wave identification and tracking
- **Fibonacci Validation**: Validates wave relationships using Fibonacci ratios
- **Pattern Recognition**: Identifies impulse (1-2-3-4-5) and corrective (A-B-C) wave patterns
- **Wave Labeling**: Labels waves according to Elliott Wave Principle
- **Wave Counting Constraints**: Enforces EWP rules like "wave 3 cannot be the shortest"

### Large Language Models (LLMs) Integration

The LLM Integration module enhances wave detection using large language models:

- **Knowledge Base**: Elliott Wave theory texts and examples
- **Retrieval-Augmented Generation (RAG)**: Retrieves relevant knowledge before making predictions
- **ReAct Framework**: Reasoning and Acting loop for decision-making
- **NLP for Market Sentiment**: Analyzing financial news and reports
- **Prompt Generation**: Creates structured prompts for LLM analysis
- **Response Parsing**: Interprets LLM outputs for wave confirmation

### Deep Reinforcement Learning (DRL)

The Reinforcement Learning module optimizes wave detection parameters:

- **Environment**: Simulated trading environment for wave detection
- **Policy Optimization**: Learns optimal parameters for Elliott Wave recognition
- **Reward Function**: Based on wave detection accuracy and trading profit
- **Exploration vs. Exploitation**: Balance between trying new strategies and using proven ones
- **Experience Replay**: Storage for training examples

### Visualization and Reporting

The Visualization module provides interactive charts and dashboards:

- **Chart Generation**: Candlestick charts with technical indicators
- **Wave Visualization**: Visual representation of detected waves
- **Trade Signal Reports**: Structured buy/sell recommendations
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
4. **LLM Validation**: Labeled Waves → LLM Prompts → RAG Enhancement → LLM Reasoning → Validated Waves
5. **DRL Optimization**: Historical Validation → Parameter Learning → Optimized Wave Detection
6. **Strategy Generation**: Validated Waves → Signal Generation → Trading Strategy
7. **Visualization**: All Stages → Interactive Charts → User Interface
8. **Agent Communication**: Cross-component messaging for collaboration

## Scalability and System Adaptation

FXML3 is designed for flexibility and growth:

- **Dynamic Context Management**: Agents update their knowledge as market conditions evolve
- **Modular Design**: The system can incorporate new AI techniques and market models over time
- **Future Trading Integration**: Architecture supports extending to autonomous trading systems

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

## Implementation Status and Roadmap

The implementation follows a phased approach:

### Phase 1: Core Data Infrastructure & Preprocessing ✅
- Data feed system with multiple sources
- Preprocessing pipeline
- Technical indicators and feature engineering

### Phase 2: Elliott Wave Detection Engine ✅
- Peak/trough detection algorithm
- Fibonacci ratio calculator and validation
- Impulse and corrective wave pattern recognition
- Wave counting constraints validation

### Phase 3: LLM Integration & Enhancement ⬜
- Elliott Wave theory knowledge database
- Retrieval system for relevant wave principles
- LLM prompting strategy for wave validation

### Phase 4: Reinforcement Learning & Optimization ⬜
- State representation for RL agent
- Reward function based on prediction accuracy
- DRL agent for parameter optimization

### Phase 5: Trading Strategy & Signal Generation ⬜
- Entry/exit signal generation based on wave patterns
- Risk management system
- Position sizing algorithms

### Phase 6: UI/Dashboard & Deployment ⬜
- Streamlit dashboard with key metrics
- Chart visualization with wave overlays
- User configuration interface