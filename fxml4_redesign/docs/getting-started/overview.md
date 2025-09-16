# Overview

## What is FXML4 Redesigned?

FXML4 Redesigned is a modern, microservices-based forex trading system that provides:

- **Automated Trading**: Execute trades based on technical and AI-driven signals
- **Multi-Broker Support**: Connect to multiple brokers simultaneously
- **Scalable Architecture**: Handle high-frequency data and multiple strategies
- **AI Integration**: Leverage LLMs for market analysis and decision-making

## System Philosophy

The redesigned system follows these core principles:

1. **Modularity**: Each service has a single responsibility
2. **Scalability**: Services can be scaled independently
3. **Resilience**: System continues operating if individual services fail
4. **Flexibility**: Easy to add new brokers, strategies, or analysis methods
5. **Observability**: Comprehensive monitoring and logging

## Use Cases

FXML4 Redesigned is suitable for:

- **Individual Traders**: Automate personal trading strategies
- **Trading Firms**: Deploy scalable trading infrastructure
- **Researchers**: Test and validate trading hypotheses
- **Developers**: Build custom trading applications

## System Requirements

### Minimum Requirements

- **CPU**: 4 cores
- **RAM**: 8 GB
- **Storage**: 50 GB SSD
- **OS**: Linux (Ubuntu 20.04+) or macOS
- **Docker**: Version 20.10+
- **Docker Compose**: Version 2.0+

### Recommended Requirements

- **CPU**: 8+ cores
- **RAM**: 16+ GB
- **Storage**: 200+ GB SSD
- **Network**: Low-latency connection to broker servers

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Message Queue** | RabbitMQ | Service communication |
| **Database** | TimescaleDB | Time-series data storage |
| **Cache** | Redis | High-speed data caching |
| **Services** | Python 3.11+ | Core business logic |
| **Containers** | Docker | Service isolation |
| **Orchestration** | Docker Compose | Service management |
| **API** | FastAPI | REST endpoints |
| **Monitoring** | Prometheus/Grafana | System metrics |

## Next Steps

Ready to get started? Continue to:

- [Installation Guide](installation.md) - Set up your environment
- [Configuration](configuration.md) - Configure the system
- [First Run](first-run.md) - Start trading

## Getting Support

If you need help:

1. Check the [Troubleshooting Guide](../deployment/troubleshooting.md)
2. Search [existing issues](https://github.com/fxml4/fxml4-redesigned/issues)
3. Ask in our [Discord community](https://discord.gg/fxml4)
4. Contact [support@fxml4.io](mailto:support@fxml4.io)
