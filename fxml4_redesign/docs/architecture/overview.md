# Architecture Overview

## Design Principles

FXML4 Redesigned follows a microservices architecture with these key principles:

1. **Service Independence**: Each service can be developed, deployed, and scaled independently
2. **Message-Driven**: Services communicate via RabbitMQ message queues
3. **Event Sourcing**: All events are logged for audit and replay capabilities
4. **Fault Tolerance**: System continues operating even when individual services fail
5. **Broker Agnostic**: Support for multiple brokers through adapter pattern

## High-Level Architecture

```mermaid
graph TB
    subgraph "External Layer"
        B1[Interactive Brokers]
        B2[FXCM]
        B3[Oanda]
        B4[Manual Trading]
        API[REST API]
        WS[WebSocket]
    end

    subgraph "Service Layer"
        DC[Data Collector<br/>Service]
        SG[Signal Generator<br/>Service]
        LLM[LLM Analyzer<br/>Service]
        EM[Entry Manager<br/>Service]
        TM[Trade Manager<br/>Service]
        MON[Monitor<br/>Service]
    end

    subgraph "Infrastructure Layer"
        RMQ[RabbitMQ<br/>Message Bus]
        TS[(TimescaleDB<br/>Time Series)]
        REDIS[(Redis<br/>Cache)]
        PROM[Prometheus<br/>Metrics]
    end

    B1 & B2 & B3 & B4 <--> DC
    API & WS <--> MON

    DC --> RMQ
    RMQ --> SG & LLM
    SG & LLM --> RMQ
    RMQ --> EM
    EM --> RMQ
    RMQ --> TM
    TM <--> B1 & B2 & B3 & B4

    DC & SG & LLM & EM & TM --> TS
    SG & EM <--> REDIS
    ALL --> PROM

    style DC fill:#4CAF50
    style SG fill:#2196F3
    style LLM fill:#FF9800
    style EM fill:#9C27B0
    style TM fill:#F44336
    style MON fill:#00BCD4
```

## Core Components

### Service Layer

| Service | Responsibility | Status |
|---------|---------------|--------|
| **Data Collector** | Ingests market data from brokers | ✅ Complete |
| **Signal Generator** | Generates trading signals | 🚧 In Progress |
| **LLM Analyzer** | AI-powered market analysis | 🚧 In Progress |
| **Entry Manager** | Manages order placement | 📅 Planned |
| **Trade Manager** | Manages open positions | 📅 Planned |
| **Monitor** | System monitoring and API | ✅ Complete |

### Infrastructure Layer

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Message Bus** | Service communication | RabbitMQ |
| **Time Series DB** | Market data storage | TimescaleDB |
| **Cache** | High-speed data access | Redis |
| **Metrics** | Performance monitoring | Prometheus |

### Broker Adapter Layer

The system uses a plugin architecture for broker connectivity:

```python
# Base adapter interface
class BaseBrokerAdapter:
    async def connect(self) -> None
    async def disconnect(self) -> None
    async def subscribe_market_data(self, symbols: List[str]) -> None
    async def place_order(self, order: Order) -> OrderResult
    async def get_positions(self) -> List[Position]
```

## Data Flow

### Market Data Flow

```mermaid
sequenceDiagram
    participant Broker
    participant DataCollector
    participant RabbitMQ
    participant SignalGenerator
    participant Database

    Broker->>DataCollector: Market Data
    DataCollector->>DataCollector: Validate & Transform
    DataCollector->>RabbitMQ: Publish market.data
    DataCollector->>Database: Store raw data
    RabbitMQ->>SignalGenerator: market.data event
    SignalGenerator->>SignalGenerator: Calculate indicators
    SignalGenerator->>RabbitMQ: Publish signals
```

### Trade Execution Flow

```mermaid
sequenceDiagram
    participant SignalGenerator
    participant RabbitMQ
    participant EntryManager
    participant TradeManager
    participant Broker

    SignalGenerator->>RabbitMQ: trading.signal
    RabbitMQ->>EntryManager: Signal event
    EntryManager->>EntryManager: Risk checks
    EntryManager->>RabbitMQ: trading.order
    RabbitMQ->>TradeManager: Order event
    TradeManager->>Broker: Place order
    Broker->>TradeManager: Order confirmation
    TradeManager->>RabbitMQ: order.filled
```

## Message Queue Design

### Exchange Architecture

```mermaid
graph LR
    subgraph "RabbitMQ Exchanges"
        ME[market.events<br/>Topic Exchange]
        TE[trading.events<br/>Topic Exchange]
        SE[system.events<br/>Topic Exchange]
    end

    subgraph "Queues"
        MQ1[data.collector.queue]
        MQ2[signal.generator.queue]
        MQ3[llm.analyzer.queue]
        TQ1[entry.manager.queue]
        TQ2[trade.manager.queue]
        SQ1[monitor.queue]
    end

    ME --> MQ1 & MQ2 & MQ3
    TE --> TQ1 & TQ2
    SE --> SQ1
```

### Message Types

| Exchange | Routing Key | Description |
|----------|-------------|-------------|
| `market.events` | `data.{symbol}.{timeframe}` | Market data updates |
| `market.events` | `indicator.{symbol}.{name}` | Technical indicators |
| `trading.events` | `signal.{symbol}.{strategy}` | Trading signals |
| `trading.events` | `order.{action}.{symbol}` | Order events |
| `system.events` | `health.{service}` | Health checks |
| `system.events` | `error.{service}.{severity}` | Error events |

## Scalability Patterns

### Horizontal Scaling

Services can be scaled horizontally by running multiple instances:

```yaml
# docker-compose.scale.yml
services:
  signal_generator:
    deploy:
      replicas: 3

  data_collector:
    deploy:
      replicas: 2
```

### Load Distribution

RabbitMQ automatically distributes messages across service instances:

```mermaid
graph LR
    RMQ[RabbitMQ]
    SG1[Signal Gen 1]
    SG2[Signal Gen 2]
    SG3[Signal Gen 3]

    RMQ -->|Round Robin| SG1
    RMQ -->|Round Robin| SG2
    RMQ -->|Round Robin| SG3
```

## Security Architecture

### Network Security

- Services communicate only through RabbitMQ
- No direct service-to-service communication
- TLS encryption for broker connections
- API authentication via JWT tokens

### Data Security

- Encrypted credentials in environment variables
- No sensitive data in logs
- Audit trail for all trading decisions
- Role-based access control (RBAC)

## Next Steps

- Learn about [individual microservices](microservices.md)
- Understand [data flow patterns](data-flow.md)
- Explore [message queue design](message-queue.md)
- Review [database schema](database-schema.md)
