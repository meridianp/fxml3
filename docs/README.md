# FXML3 Documentation

Welcome to the FXML3 documentation. This directory contains comprehensive documentation for the FXML3 project, an AI-Enhanced Elliott Wave Analysis tool for forex markets.

## Contents

- [Getting Started](getting-started.md) - Installation and basic usage
- [Architecture](architecture.md) - System architecture and design
- [Data Engineering](data-engineering.md) - Data feeds, preprocessing, and feature engineering
- [Visualization](visualization.md) - Chart visualization components
- [Elliott Wave Analysis](elliott-wave-analysis.md) - Elliott Wave pattern detection
- [Trading Strategy](trading-strategy.md) - Entry/exit signals, risk management, and position sizing
- [Backtesting](backtesting.md) - Strategy backtesting and validation framework
- [API Reference](api-reference/) - Detailed API documentation
  - [Data Engineering API](api-reference/data-engineering.md)
  - [Visualization API](api-reference/visualization.md)
  - [Wave Analysis API](api-reference/wave-analysis.md)
  - [Backtesting API](api-reference/backtesting.md)
- [Examples](examples/) - Usage examples and tutorials

## Project Overview

FXML3 is a Python-based forex analysis platform that combines traditional Elliott Wave Principle (EWP) with modern AI techniques to identify trading opportunities. The system uses a multi-agent architecture to handle different aspects of the analysis process, from data collection to trade recommendation.

### Key Features

- **Modular Data Feeds**: Support for multiple data sources (Yahoo Finance, FXCM, Interactive Brokers, CSV)
- **Advanced Preprocessing**: Cleaning, normalization, and feature engineering tailored for forex data
- **Elliott Wave Detection**: Automated identification of Elliott Wave patterns
- **LLM Integration**: Enhanced pattern validation using Large Language Models
- **Reinforcement Learning**: Optimization of pattern detection parameters
- **Interactive Visualization**: Rich, interactive charts for analysis and interpretation
- **Trading Strategy Generation**: Signal generation based on identified patterns

### Development Status

The project is under active development. We have completed the following phases:

- ✅ **Phase 1**: Data Infrastructure & Preprocessing
- ✅ **Phase 2**: Elliott Wave Detection Engine
- ✅ **Phase 3**: Multi-Agent System & LLM Integration
- ✅ **Phase 4**: Reinforcement Learning & Optimization
- ✅ **Phase 5**: Trading Strategy & Signal Generation
  - ✅ Entry/Exit Signal Generation
  - ✅ Risk Management System
  - ✅ Position Sizing Algorithms
  - ✅ Portfolio Strategy Logic
- ✅ **Phase 6**: Advanced Backtesting & Validation
  - ✅ Realistic Market Simulation
  - ✅ Strategy Performance Analysis
  - ✅ Monte Carlo Simulation
  - ✅ Walk-Forward Analysis
  - ✅ Cross-Market Validation
- 🔄 **Phase 7**: UI/Dashboard & Deployment (in progress)
  - ✅ Basic Streamlit UI Skeleton
  - 🔄 Interactive Dashboard (in progress)
  - 🔄 Chart Visualization with Wave Overlay (in progress)

We are currently implementing the web interface components and integrating the multi-agent system with the advanced backtesting framework.