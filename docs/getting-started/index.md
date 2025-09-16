# Getting Started

Welcome to FXML4! This section will help you get up and running with the platform quickly.

## What is FXML4?

FXML4 is an integrated forex trading platform that combines:

- **Machine Learning**: Advanced feature engineering and signal generation
- **Elliott Wave Analysis**: Visual pattern recognition with Claude Opus 4
- **Backtesting**: Event-driven engine with comprehensive metrics
- **Paper Trading**: Live trading simulation with Interactive Brokers
- **Risk Management**: Professional-grade position sizing and controls

## Prerequisites

Before you begin, ensure you have:

- Python 3.10 or higher
- PostgreSQL 14+ or TimescaleDB
- Git
- A trading account with Interactive Brokers (for paper trading)
- API keys for:
  - Anthropic (Claude Opus 4)
  - Alpha Vantage (market data)
  - Google Cloud (optional, for Vertex AI)

## Quick Navigation

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Installation**

    ---

    Set up your development environment and install dependencies

    [:octicons-arrow-right-24: Installation guide](installation.md)

-   :material-rocket:{ .lg .middle } **Quick Start**

    ---

    Run your first backtest and generate trading signals

    [:octicons-arrow-right-24: Quick start tutorial](quick-start.md)

-   :material-cog:{ .lg .middle } **Configuration**

    ---

    Configure API keys, database connections, and trading parameters

    [:octicons-arrow-right-24: Configuration guide](configuration.md)

-   :material-view-dashboard:{ .lg .middle } **Dashboard**

    ---

    Set up and use the web dashboard for monitoring

    [:octicons-arrow-right-24: Dashboard setup](dashboard.md)

</div>

## Key Concepts

### Trading Signals

FXML4 generates trading signals using multiple approaches:

1. **Machine Learning Signals**: Based on technical indicators and market patterns
2. **Elliott Wave Signals**: Using visual chart analysis with AI
3. **Hybrid Signals**: Combining ML and Elliott Wave for higher confidence

### Backtesting

The event-driven backtesting engine simulates realistic trading conditions:

- Order execution with slippage
- Transaction costs and fees
- Position sizing based on risk
- Multi-asset portfolio support

### Paper Trading

Test strategies in real-time with simulated trading:

- Live market data from Interactive Brokers
- Real-time position tracking
- Risk management controls
- Performance monitoring

## Getting Help

- Check the [FAQ](../troubleshooting/faq.md) for common questions
- Review [troubleshooting guide](../troubleshooting/common-issues.md) for issues
- Join our [community forum](https://github.com/meridianp/fxml4/discussions)
- Report bugs on [GitHub Issues](https://github.com/meridianp/fxml4/issues)

## Next Steps

1. Follow the [installation guide](installation.md) to set up your environment
2. Complete the [quick start tutorial](quick-start.md) to run your first backtest
3. Explore the [Elliott Wave features](../features/elliott-wave/index.md) for advanced analysis
4. Learn about [trading strategies](../guides/trading-strategies.md) to develop your own

!!! tip "Pro Tip"
    Start with paper trading to test your strategies risk-free before moving to live trading.

Ready to begin? Head to the [installation guide](installation.md) →
