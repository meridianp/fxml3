# FXML4 Redesigned Documentation

<div align="center">
  <img src="assets/logo.png" alt="FXML4 Logo" width="200"/>
  <h3>Modern Microservices Trading System</h3>
  <p>Scalable, intelligent, and broker-agnostic forex trading platform</p>
</div>

## Welcome to FXML4 Redesigned

FXML4 Redesigned is a complete rewrite of the original FXML4 trading system, built from the ground up with a modern microservices architecture. This documentation covers the system architecture, services, deployment, and development guides.

## System Status

!!! info "Current Phase"
    - **Phase 1: Infrastructure** ✅ Complete
    - **Phase 2: Intelligence Layer** 🚧 In Progress
    - **Phase 3: Advanced Features** 📅 Planned

## Key Features

<div class="grid cards" markdown>

- :material-scale-balance: **Microservices Architecture**
  Scalable, fault-tolerant design with independent services

- :material-message-fast: **RabbitMQ Messaging**
  Asynchronous communication between services

- :material-database: **TimescaleDB Storage**
  Optimized time-series data handling

- :material-swap-horizontal: **Multi-Broker Support**
  Connect to multiple brokers simultaneously

- :material-brain: **AI/ML Integration**
  LLM-powered analysis and advanced signals

- :material-monitor-dashboard: **Real-time Monitoring**
  Comprehensive system and trade monitoring

</div>

## Quick Links

- [🚀 Getting Started](getting-started/overview.md) - Get up and running quickly
- [🏗️ Architecture](architecture/overview.md) - Understand the system design
- [📡 API Reference](api/rest-api.md) - Integrate with FXML4
- [🔧 Development](development/contributing.md) - Contribute to the project

## Architecture Overview

```mermaid
graph TB
    subgraph "External Sources"
        IB[Interactive Brokers]
        FXCM[FXCM]
        OANDA[Oanda]
        MT[Manual Trading]
    end

    subgraph "Core Services"
        DC[Data Collector]
        SG[Signal Generator]
        LLM[LLM Analyzer]
        EM[Entry Manager]
        TM[Trade Manager]
        MON[Monitor]
    end

    subgraph "Infrastructure"
        RMQ[RabbitMQ]
        TS[(TimescaleDB)]
        REDIS[(Redis)]
    end

    IB & FXCM & OANDA & MT --> DC
    DC --> RMQ
    RMQ --> SG & LLM
    SG & LLM --> EM
    EM --> TM
    TM --> IB & FXCM & OANDA & MT
    MON --> TS

    style DC fill:#4CAF50
    style SG fill:#2196F3
    style LLM fill:#FF9800
    style EM fill:#9C27B0
    style TM fill:#F44336
    style MON fill:#00BCD4
```

## System Components

### Phase 1: Infrastructure (Complete) ✅

- **Message Queue**: RabbitMQ-based event streaming
- **Database**: TimescaleDB for time-series data
- **Broker Adapters**: Multi-broker connectivity layer
- **Base Services**: Common service framework
- **Docker Infrastructure**: Containerized deployment

### Phase 2: Intelligence Layer (In Progress) 🚧

- **Signal Generator**: Technical analysis and pattern recognition
- **LLM Analyzer**: AI-powered market analysis
- **Entry Manager**: Smart order placement logic
- **Trade Manager**: Position and risk management

### Phase 3: Advanced Features (Planned) 📅

- Web dashboard and API
- Advanced risk management
- Portfolio optimization
- Backtesting engine
- Performance analytics

## Getting Help

- 📖 Browse the [documentation](getting-started/overview.md)
- 🐛 Report [issues on GitHub](https://github.com/fxml4/fxml4-redesigned/issues)
- 💬 Join our [Discord community](https://discord.gg/fxml4)
- 📧 Contact the team at [support@fxml4.io](mailto:support@fxml4.io)

## License

FXML4 Redesigned is licensed under the MIT License. See the [LICENSE](https://github.com/fxml4/fxml4-redesigned/LICENSE) file for details.
