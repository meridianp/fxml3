# Broker Abstraction Architecture

## System Architecture Diagram

```mermaid
graph TB
    subgraph "FXML4 Core System"
        TS[Trading Strategies]
        RM[Risk Manager]
        OM[Order Manager]
        PM[Portfolio Manager]
    end

    subgraph "FIX Infrastructure"
        FB[FIX Builder]
        FP[FIX Parser]
        FV[FIX Validator]
    end

    subgraph "Message Router"
        MR[Message Router]
        RR[Routing Rules]
        BM[Broker Metrics]
    end

    subgraph "RabbitMQ Message Bus"
        subgraph "Exchanges"
            OE[orders.outbound]
            EE[orders.executions]
            AE[admin.commands]
            ME[market.data.feed]
        end

        subgraph "Queues"
            IBQ[orders.ib.inbound]
            MQ[orders.manual.inbound]
            FQ[orders.fxcm.inbound]
            NQ[orders.fix.inbound]
            EXQ[executions.all]
        end
    end

    subgraph "Broker Adapters"
        IBA[IB Adapter]
        MA[Manual Adapter]
        FA[FXCM Adapter]
        NA[Native FIX Adapter]
    end

    subgraph "External Brokers"
        IB[Interactive Brokers TWS/Gateway]
        HT[Human Trader]
        FC[FXCM ForexConnect]
        FB2[FIX Broker]
    end

    %% Core to Router flow
    TS --> OM
    OM --> MR
    RM --> MR
    MR --> FB

    %% Router to RabbitMQ
    FB --> OE
    MR -.-> RR
    MR -.-> BM

    %% RabbitMQ routing
    OE --> IBQ
    OE --> MQ
    OE --> FQ
    OE --> NQ

    %% Queue to Adapters
    IBQ --> IBA
    MQ --> MA
    FQ --> FA
    NQ --> NA

    %% Adapters to Brokers
    IBA <--> IB
    MA <--> HT
    FA <--> FC
    NA <--> FB2

    %% Execution flow back
    IBA --> EE
    MA --> EE
    FA --> EE
    NA --> EE
    EE --> EXQ
    EXQ --> PM

    %% Market data flow
    IB --> IBA
    FC --> FA
    IBA --> ME
    FA --> ME

    classDef core fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef infra fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef router fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef mq fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    classDef adapter fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef broker fill:#efebe9,stroke:#3e2723,stroke-width:2px

    class TS,RM,OM,PM core
    class FB,FP,FV infra
    class MR,RR,BM router
    class OE,EE,AE,ME,IBQ,MQ,FQ,NQ,EXQ mq
    class IBA,MA,FA,NA adapter
    class IB,HT,FC,FB2 broker
```

## Message Flow Sequence

```mermaid
sequenceDiagram
    participant S as Strategy
    participant R as Router
    participant MQ as RabbitMQ
    participant A as Adapter
    participant B as Broker
    participant P as Portfolio

    S->>R: Submit Order
    R->>R: Apply Routing Rules
    R->>MQ: Publish to orders.outbound
    MQ->>A: Deliver to broker queue
    A->>B: Send Order (Native API)
    B-->>A: Acknowledge
    B-->>A: Execution Report
    A->>MQ: Publish to orders.executions
    MQ->>P: Update Portfolio
    P-->>S: Position Updated
```

## Component Responsibilities

### Message Router
- **Routing Decision**: Selects optimal broker based on rules and metrics
- **Load Balancing**: Distributes orders across available brokers
- **Failover**: Routes to backup brokers when primary unavailable
- **Monitoring**: Tracks broker performance and availability

### RabbitMQ Topology
- **Order Distribution**: Topic exchange routes by broker type
- **Execution Aggregation**: Collects reports from all brokers
- **Dead Letter Handling**: Failed messages go to DLQ
- **Priority Queues**: Urgent orders get expedited processing

### Broker Adapters
- **Protocol Translation**: Convert between FIX and native broker API
- **Connection Management**: Handle reconnects and heartbeats
- **State Tracking**: Maintain order lifecycle status
- **Error Recovery**: Implement retry logic and failover

## Key Design Decisions

1. **FIX as Internal Protocol**
   - Industry standard for financial messaging
   - Well-defined message types and workflows
   - Enables future direct FIX connections

2. **RabbitMQ for Decoupling**
   - Reliable message delivery with persistence
   - Flexible routing with topic exchanges
   - Built-in dead letter handling
   - Horizontal scalability

3. **Adapter Pattern**
   - Isolates broker-specific logic
   - Enables independent scaling
   - Simplifies testing with mock adapters
   - Supports diverse broker types

4. **Non-HFT Optimization**
   - Focus on reliability over microsecond latency
   - Human-readable message formats
   - Comprehensive logging and auditing
   - Graceful error handling

## Routing Strategies

### 1. Best Execution (Default)
```python
score = latency_weight * (1/latency_ms) +
        fill_rate_weight * fill_rate_pct +
        commission_weight * (1 - commission_rate) +
        load_weight * (1 - current_load)
```

### 2. Symbol Affinity
- FX pairs → FXCM (preferred) → IB (fallback)
- Equities → IB (preferred) → Manual (fallback)
- Large orders → Manual review

### 3. Load Balancing
- Round-robin across available brokers
- Least-loaded broker selection
- Daily volume limits per broker

### 4. Risk-Based Routing
- High-risk orders → Manual approval
- After-hours → Brokers with extended hours
- New strategies → Paper trading first

## Failure Scenarios

### Broker Unavailable
1. Router detects offline status
2. Routes to next available broker
3. Notifies monitoring system
4. Attempts reconnection in background

### Message Queue Failure
1. Publisher detects connection loss
2. Buffers messages locally
3. Retries with exponential backoff
4. Alerts operations team

### Adapter Crash
1. Manager detects missing heartbeat
2. Attempts adapter restart
3. Routes orders to other brokers
4. Preserves in-flight order state

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Order Routing Latency | < 100ms | TBD |
| Message Delivery Rate | 99.9% | TBD |
| Adapter Uptime | 99.5% | TBD |
| Failover Time | < 5s | TBD |
| Daily Order Capacity | 100K | TBD |

## Security Considerations

1. **Authentication**
   - Per-adapter credentials
   - API key rotation support
   - Certificate-based auth for FIX

2. **Encryption**
   - TLS for all external connections
   - Encrypted message payloads
   - Secure credential storage

3. **Authorization**
   - Role-based access control
   - Per-strategy broker limits
   - Manual approval thresholds

4. **Audit Trail**
   - All messages logged
   - Order state transitions tracked
   - Compliance reporting ready
