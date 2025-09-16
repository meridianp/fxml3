# FXML4 Architecture Redesign Documentation

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Proposed Architecture](#proposed-architecture)
4. [Service Specifications](#service-specifications)
5. [Data Flow Design](#data-flow-design)
6. [Database Schema](#database-schema)
7. [Message Queue Design](#message-queue-design)
8. [Implementation Plan](#implementation-plan)
9. [Risk Management](#risk-management)
10. [Success Metrics](#success-metrics)

---

## Executive Summary

### Purpose
Complete architectural redesign of FXML4 to address critical performance issues and properly utilize all built capabilities, particularly LLM integration for multi-timeframe analysis.

### Key Problems Identified
1. **Performance**: Current system showing -49% to -100% returns
2. **LLM Integration**: Built but not utilized - system falls back to rule-based analysis
3. **Architecture**: Tight coupling makes testing and debugging difficult
4. **Data Management**: No separation between analysis (4H) and execution (1m) timeframes
5. **Configuration**: Settings and thresholds scattered throughout codebase

### Solution Overview
Microservices architecture using RabbitMQ for communication, with:
- Dual-speed data collection (4H for analysis, 1m for execution)
- Proper separation of concerns across six core services
- Smart LLM utilization for high-value trade validation
- Cost-optimized design suitable for personal trading

### Expected Outcomes
- Profitable trading system with proper risk management
- Full utilization of ML and LLM capabilities
- Precision entries using 1-minute data
- Clear architecture enabling easy maintenance and testing
- Cost-effective operation ($50-100/month)

---

## Current State Analysis

### Architecture Issues

#### 1. Monolithic Design
```python
# Current: Everything tightly coupled
class TradingSystem:
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.ml_model = MLModel()
        self.elliott_wave = ElliottWave()
        self.llm_client = LLMClient()  # Built but unused!
        self.trader = Trader()

    def run(self):
        # All logic in one place, hard to test/debug
```

#### 2. LLM Fallback Problem
```python
# From general_technical_analysis_llm.py
if self.llm_client:
    # This path rarely executes
    analysis = self._perform_llm_analysis(data, market_summary)
else:
    # Always falls back to this
    return self._perform_rule_based_analysis(data, market_summary)
```

#### 3. Feature Engineering Issues
```python
# Column naming inconsistencies
'atr_14' vs 'atr'  # Causes ML prediction failures
'rsi_14' vs 'rsi'  # Causes TA signal errors
```

### Performance Analysis

#### Recent Backtest Results
- **Simple 400x System**: -100.12% (account blown)
- **Conservative System**: 0% return (no trades executed)
- **ML-Only System**: -49.3% return
- **Aggressive System**: +2.43% return (best result, but limited)

#### Root Causes
1. ML models trained on price movements, not profitable patterns
2. Overly conservative thresholds preventing trades
3. No multi-timeframe confluence
4. LLM validation never actually used

---

## Proposed Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FXML4 Trading System                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │Data Collector│  │   Signal     │  │     LLM      │            │
│  │              │  │  Generator   │  │   Analyzer   │            │
│  │ • 4H/1H: 5m │  │              │  │              │            │
│  │ • 1m/5m: 30s│  │ • ML Models  │  │ • GPT-4V     │            │
│  └──────┬───────┘  │ • Elliott W. │  │ • Charts     │            │
│         │          └──────┬────────┘  └──────┬───────┘            │
│         │                 │                   │                     │
│         ▼                 ▼                   ▼                     │
│  ┌────────────────────────────────────────────────┐               │
│  │              RabbitMQ Message Bus              │               │
│  │  Topics: data.*, signals.*, trades.*, llm.*   │               │
│  └────────────────────────────────────────────────┘               │
│         │                 │                   │                     │
│         ▼                 ▼                   ▼                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │    Entry     │  │    Trade     │  │   Monitor    │            │
│  │   Manager    │  │   Manager    │  │              │            │
│  │              │  │              │  │ • Dashboard  │            │
│  │ • 1m Entry   │  │ • IB API     │  │ • Alerts     │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │
│  │  TimescaleDB   │  │     Redis      │  │   Config DB    │      │
│  │                │  │                │  │                │      │
│  │ • Time-series  │  │ • Cache        │  │ • Settings     │      │
│  │ • Partitioned  │  │ • State        │  │ • Strategies   │      │
│  └────────────────┘  └────────────────┘  └────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Temporal Separation**
   - Analysis timeframes (4H, 1H) for setup identification
   - Execution timeframes (5m, 1m) for precise entries/exits
   - Adaptive data collection based on active setups

2. **Service Independence**
   - Each service has single responsibility
   - Communication only through message queue
   - Services can be tested in isolation

3. **Graceful Degradation**
   - LLM unavailable → Use ML signals only
   - ML degraded → Fall back to Elliott Wave
   - Data interrupted → Manage existing positions only

4. **Cost Optimization**
   - Collect 1m data only for active setups
   - Cache LLM analysis for 4 hours
   - Batch similar requests together

---

## Service Specifications

### 1. Data Collector Service

#### Purpose
Efficiently collect market data at appropriate frequencies based on trading needs.

#### Responsibilities
- Fetch candle data from Polygon/IB APIs
- Store in TimescaleDB with proper timestamps
- Publish updates to RabbitMQ
- Manage active symbol list for high-frequency collection

#### Implementation Details
```python
class DataCollectorService:
    """
    Dual-speed data collection:
    - Slow loop: All symbols, 4H/1H timeframes (5-minute intervals)
    - Fast loop: Active symbols only, 1m/5m timeframes (30-second intervals)
    """

    def __init__(self):
        self.config = {
            'analysis_timeframes': ['4H', '1H'],
            'execution_timeframes': ['5m', '1m'],
            'analysis_interval': 300,  # 5 minutes
            'execution_interval': 30,  # 30 seconds
            'all_symbols': ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'],
            'active_symbols': set(),  # Dynamically managed
        }

    async def collect_analysis_data(self):
        """Collect 4H/1H data for all symbols"""

    async def collect_execution_data(self):
        """Collect 1m/5m data for active symbols only"""

    async def on_watch_symbol(self, symbol: str, ttl: int = 86400):
        """Add symbol to high-frequency collection"""
```

#### Message Publishing
- `data.analysis.{symbol}.{timeframe}` - Analysis timeframe updates
- `data.execution.{symbol}.{timeframe}` - Execution timeframe updates

### 2. Signal Generator Service

#### Purpose
Generate trading signals from multiple sources with proper validation.

#### Responsibilities
- ML model predictions
- Elliott Wave pattern detection
- Technical indicator confluence
- Setup validation and filtering

#### Implementation Details
```python
class SignalGeneratorService:
    """
    Multi-source signal generation with validation
    """

    def __init__(self):
        self.ml_models = {}  # Per-symbol models
        self.elliott_analyzer = ElliottWaveAnalyzer()
        self.setup_validator = SetupValidator()
        self.min_confluences = 2

    async def on_analysis_data(self, data: MarketData):
        """Process 4H/1H data for setup identification"""

    def identify_setup(self, data: pd.DataFrame) -> Optional[Setup]:
        """
        Identify high-probability setups requiring:
        1. ML signal with >65% confidence
        2. Elliott Wave pattern completion
        3. Key level alignment
        4. Risk/reward ratio > 2:1
        """
```

#### Message Flow
- Subscribes: `data.analysis.*.4H`, `data.analysis.*.1H`
- Publishes: `setups.new`, `symbols.watch`, `llm.analyze.request`

### 3. LLM Analyzer Service

#### Purpose
Provide intelligent visual analysis using GPT-4V for high-value setups.

#### Responsibilities
- Generate multi-timeframe charts
- Obtain GPT-4V analysis
- Validate setup quality
- Cache results for cost efficiency

#### Implementation Details
```python
class LLMAnalyzerService:
    """
    Intelligent analysis with cost optimization
    """

    def __init__(self):
        self.gpt4v_client = OpenAI()
        self.chart_generator = ChartGenerator()
        self.cache = RedisCache()
        self.config = {
            'min_trade_value': 5000,  # Only analyze larger trades
            'cache_ttl': 14400,  # 4 hours
            'max_requests_per_hour': 20,
            'timeframes_to_analyze': ['D', '4H', '1H', '15m']
        }

    async def analyze_setup(self, setup: Setup) -> Analysis:
        """
        Generate charts and get GPT-4V analysis
        Only for setups meeting criteria
        """

    def should_analyze(self, setup: Setup) -> bool:
        """
        Criteria for LLM analysis:
        1. High confidence (>0.7)
        2. Multiple confluences
        3. Significant trade value
        4. Not recently analyzed (cache check)
        """
```

#### Message Flow
- Subscribes: `llm.analyze.request`
- Publishes: `signals.enhanced`, `analysis.complete`

### 4. Entry Manager Service

#### Purpose
Find precise entries using 1-minute price action within 4H context.

#### Responsibilities
- Monitor 1m data for entry patterns
- Validate entry conditions
- Calculate exact entry prices
- Manage entry timing

#### Implementation Details
```python
class EntryManagerService:
    """
    Precision entry management using 1m data
    """

    def __init__(self):
        self.active_setups = {}  # Setup ID -> Setup details
        self.entry_patterns = [
            PinBarPattern(),
            EngulfingPattern(),
            MomentumBreakPattern(),
            RetestPattern()
        ]

    async def on_setup_created(self, setup: Setup):
        """Register new setup for monitoring"""

    async def on_execution_data(self, data: MarketData):
        """
        Check 1m data for entry triggers:
        1. Price in entry zone
        2. Entry pattern formed
        3. Momentum confirmation
        4. Risk/reward still valid
        """

    def calculate_precise_entry(self, setup: Setup,
                              current_data: pd.DataFrame) -> Optional[Entry]:
        """Calculate exact entry based on 1m patterns"""
```

#### Message Flow
- Subscribes: `setups.new`, `data.execution.*.1m`
- Publishes: `entries.triggered`, `setups.expired`

### 5. Trade Manager Service

#### Purpose
Execute and manage trades with proper risk management.

#### Responsibilities
- Position sizing based on risk
- Order execution via broker API
- Stop loss and profit target management
- Real-time position tracking

#### Implementation Details
```python
class TradeManagerService:
    """
    Trade execution and management
    """

    def __init__(self):
        self.broker = IBClient() if LIVE_MODE else PaperTrader()
        self.risk_manager = RiskManager()
        self.positions = {}
        self.config = {
            'max_risk_per_trade': 0.02,  # 2%
            'max_portfolio_risk': 0.06,  # 6%
            'max_positions': 5,
            'min_position_value': 1000,
            'use_trailing_stops': True
        }

    async def on_entry_triggered(self, entry: Entry):
        """Execute trade with pre-trade validation"""

    async def on_execution_data(self, data: MarketData):
        """
        Manage positions using 1m data:
        1. Trail stops based on structure
        2. Take partial profits
        3. Monitor for exit signals
        """

    def calculate_position_size(self, entry: Entry) -> PositionSize:
        """
        Dynamic position sizing based on:
        1. Account risk (2%)
        2. Stop distance
        3. Confidence level
        4. Current portfolio exposure
        """
```

#### Message Flow
- Subscribes: `entries.triggered`, `data.execution.*.1m`, `risk.alerts`
- Publishes: `trades.executed`, `positions.updated`, `trades.closed`

### 6. Monitor Service

#### Purpose
Provide real-time visibility and alerting for the trading system.

#### Responsibilities
- Web dashboard for system monitoring
- Real-time position tracking
- Performance analytics
- Alert distribution

#### Implementation Details
```python
class MonitorService:
    """
    System monitoring and alerting
    """

    def __init__(self):
        self.app = FastAPI()
        self.websocket_manager = WebSocketManager()
        self.alert_channels = [
            EmailAlerts(),
            DiscordAlerts(),
            SMSAlerts()  # For critical alerts only
        ]

    # Dashboard endpoints
    @app.get("/api/positions")
    async def get_positions():
        """Current positions with real-time P&L"""

    @app.get("/api/performance")
    async def get_performance():
        """System performance metrics"""

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """Real-time updates for dashboard"""

    async def on_alert(self, alert: Alert):
        """Distribute alerts based on severity"""
```

#### Features
- Real-time position monitoring
- Performance analytics dashboard
- Trade history and analysis
- System health monitoring
- Alert management

---

## Data Flow Design

### Multi-Timeframe Data Flow

```
1. ANALYSIS PHASE (Every 5 minutes)
   ┌─────────────┐
   │ Polygon API │
   └──────┬──────┘
          │ 4H/1H candles
          ▼
   ┌─────────────┐      ┌──────────────┐
   │   Data      │─────▶│ TimescaleDB  │
   │ Collector   │      └──────────────┘
   └──────┬──────┘
          │ Publish: data.analysis.*
          ▼
   ┌─────────────┐
   │   Signal    │
   │ Generator   │
   └──────┬──────┘
          │ Setup identified
          ▼
   ┌─────────────┐      ┌──────────────┐
   │  RabbitMQ   │─────▶│ Watch Symbol │
   │setups.new   │      └──────────────┘
   └─────────────┘

2. ENTRY PHASE (Every 30 seconds for active symbols)
   ┌─────────────┐
   │ Polygon API │
   └──────┬──────┘
          │ 1m/5m candles
          ▼
   ┌─────────────┐      ┌──────────────┐
   │   Data      │─────▶│    Entry     │
   │ Collector   │      │   Manager    │
   └─────────────┘      └──────┬───────┘
                               │ Entry trigger
                               ▼
                        ┌──────────────┐
                        │    Trade     │
                        │   Manager    │
                        └──────────────┘

3. MANAGEMENT PHASE (Continuous for open positions)
   ┌─────────────┐
   │ 1m Updates  │
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐      ┌──────────────┐
   │   Trade     │─────▶│ Update Stops │
   │  Manager    │      │ Take Profits │
   └─────────────┘      └──────────────┘
```

### Signal Enhancement Flow

```
Standard Signal Path:
ML Signal ──┐
            ├──▶ Signal Validator ──▶ Setup Created
Elliott ────┘

Enhanced Path (High-Value Setups):
Setup ──▶ LLM Request ──▶ Chart Generation ──▶ GPT-4V ──▶ Enhanced Signal
```

---

## Database Schema

### TimescaleDB Tables

```sql
-- =====================================================
-- MARKET DATA TABLES
-- =====================================================

-- Main candle storage with timeframe partitioning
CREATE TABLE candles (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open NUMERIC(10,5) NOT NULL,
    high NUMERIC(10,5) NOT NULL,
    low NUMERIC(10,5) NOT NULL,
    close NUMERIC(10,5) NOT NULL,
    volume BIGINT,
    trades INTEGER,
    vwap NUMERIC(10,5),
    PRIMARY KEY (symbol, timeframe, time)
) PARTITION BY LIST (timeframe);

-- Create partitions for each timeframe
CREATE TABLE candles_daily PARTITION OF candles FOR VALUES IN ('D', '1D');
CREATE TABLE candles_4h PARTITION OF candles FOR VALUES IN ('4H', '240');
CREATE TABLE candles_1h PARTITION OF candles FOR VALUES IN ('1H', '60');
CREATE TABLE candles_5m PARTITION OF candles FOR VALUES IN ('5m', '5');
CREATE TABLE candles_1m PARTITION OF candles FOR VALUES IN ('1m', '1');

-- Hypertable for time-series optimization
SELECT create_hypertable('candles_1m', 'time', chunk_time_interval => INTERVAL '1 day');
SELECT create_hypertable('candles_5m', 'time', chunk_time_interval => INTERVAL '1 week');
SELECT create_hypertable('candles_1h', 'time', chunk_time_interval => INTERVAL '1 month');
SELECT create_hypertable('candles_4h', 'time', chunk_time_interval => INTERVAL '3 months');

-- Compression policy for older data
SELECT add_compression_policy('candles_1m', INTERVAL '7 days');
SELECT add_compression_policy('candles_5m', INTERVAL '30 days');

-- =====================================================
-- TRADING TABLES
-- =====================================================

-- Trading setups identified by the system
CREATE TABLE setups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    direction TEXT CHECK (direction IN ('LONG', 'SHORT')) NOT NULL,

    -- Entry criteria
    entry_zone_high NUMERIC(10,5),
    entry_zone_low NUMERIC(10,5),
    ideal_entry NUMERIC(10,5),

    -- Risk management
    stop_loss NUMERIC(10,5) NOT NULL,
    take_profit_1 NUMERIC(10,5),
    take_profit_2 NUMERIC(10,5),
    take_profit_3 NUMERIC(10,5),

    -- Signal sources and confidence
    ml_confidence NUMERIC(3,2),
    elliott_confidence NUMERIC(3,2),
    llm_confidence NUMERIC(3,2),
    overall_confidence NUMERIC(3,2) NOT NULL,
    signal_sources TEXT[] NOT NULL,

    -- Metadata
    pattern_type TEXT,
    key_levels JSONB,
    analysis_notes TEXT,
    chart_url TEXT,

    -- Lifecycle
    valid_until TIMESTAMPTZ NOT NULL,
    status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACTIVE', 'FILLED', 'EXPIRED', 'CANCELLED')),

    -- Indexes
    INDEX idx_setups_symbol_status (symbol, status),
    INDEX idx_setups_created (created_at DESC),
    INDEX idx_setups_valid_until (valid_until)
);

-- Executed trades
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    setup_id UUID REFERENCES setups(id),

    -- Execution details
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    symbol TEXT NOT NULL,
    direction TEXT CHECK (direction IN ('LONG', 'SHORT')) NOT NULL,

    -- Prices
    entry_price NUMERIC(10,5) NOT NULL,
    exit_price NUMERIC(10,5),
    stop_loss NUMERIC(10,5) NOT NULL,
    take_profit NUMERIC(10,5),

    -- Position details
    position_size NUMERIC NOT NULL,
    leverage NUMERIC(5,2) NOT NULL,
    commission NUMERIC(10,2),

    -- Results
    pnl NUMERIC(10,2),
    pnl_percent NUMERIC(6,4),
    max_profit NUMERIC(10,2),
    max_loss NUMERIC(10,2),

    -- Exit information
    exit_reason TEXT,
    exit_analysis JSONB,

    -- Status
    status TEXT DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'ERROR')),

    -- Metadata
    entry_analysis JSONB,
    management_log JSONB[],

    -- Indexes
    INDEX idx_trades_symbol (symbol),
    INDEX idx_trades_status (status),
    INDEX idx_trades_entry_time (entry_time DESC)
);

-- =====================================================
-- ANALYTICS VIEWS
-- =====================================================

-- Daily performance summary
CREATE MATERIALIZED VIEW daily_performance
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', exit_time) AS day,
    symbol,
    COUNT(*) as trade_count,
    SUM(pnl) as daily_pnl,
    AVG(pnl_percent) as avg_return,
    STDDEV(pnl_percent) as return_volatility,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate,
    MAX(pnl) as best_trade,
    MIN(pnl) as worst_trade
FROM trades
WHERE exit_time IS NOT NULL
GROUP BY day, symbol
WITH NO DATA;

-- Strategy performance by signal source
CREATE MATERIALIZED VIEW strategy_performance AS
SELECT
    signal_source,
    COUNT(*) as total_trades,
    AVG(t.pnl_percent) as avg_return,
    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate,
    SUM(t.pnl) as total_pnl,
    AVG(t.leverage) as avg_leverage
FROM trades t
JOIN setups s ON t.setup_id = s.id
CROSS JOIN LATERAL unnest(s.signal_sources) AS signal_source
WHERE t.exit_time IS NOT NULL
GROUP BY signal_source;

-- =====================================================
-- SYSTEM TABLES
-- =====================================================

-- Configuration management
CREATE TABLE system_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by TEXT
);

-- Insert default configuration
INSERT INTO system_config (key, value) VALUES
('risk_management', '{
    "max_risk_per_trade": 0.02,
    "max_portfolio_risk": 0.06,
    "max_positions": 5,
    "min_position_value": 1000
}'::jsonb),
('signal_thresholds', '{
    "ml_confidence": 0.65,
    "elliott_confidence": 0.5,
    "min_confluences": 2,
    "llm_required_above": 10000
}'::jsonb),
('data_collection', '{
    "analysis_interval": 300,
    "execution_interval": 30,
    "active_symbol_ttl": 86400
}'::jsonb);

-- Service health monitoring
CREATE TABLE service_health (
    service_name TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    status TEXT CHECK (status IN ('HEALTHY', 'DEGRADED', 'DOWN')),
    metrics JSONB,
    PRIMARY KEY (service_name, timestamp)
);

-- Create hypertable for service health
SELECT create_hypertable('service_health', 'timestamp',
    chunk_time_interval => INTERVAL '1 day');

-- Retention policy for service health (keep 30 days)
SELECT add_retention_policy('service_health', INTERVAL '30 days');
```

### Redis Schema

```yaml
# Cache Keys Structure
cache_keys:
  # LLM Analysis Cache
  llm_analysis:{symbol}:{timeframe}:{setup_hash}:
    type: hash
    ttl: 14400  # 4 hours
    fields:
      - analysis: JSON string
      - confidence: float
      - chart_url: string
      - timestamp: ISO timestamp

  # Active Setups
  setup:active:{symbol}:
    type: hash
    ttl: 86400  # 24 hours
    fields:
      - setup_id: UUID
      - direction: LONG/SHORT
      - entry_zone: JSON
      - created_at: timestamp

  # Symbol Watch List
  symbols:watch:
    type: set
    members: [symbol1, symbol2, ...]

  # Position State
  position:{symbol}:
    type: hash
    fields:
      - entry_price: float
      - current_stop: float
      - position_size: float
      - unrealized_pnl: float

  # Service State
  service:{service_name}:state:
    type: string
    value: JSON state object
```

---

## Message Queue Design

### RabbitMQ Architecture

```yaml
# Exchange Definitions
exchanges:
  # Market data distribution
  data.analysis:
    type: topic
    durable: true
    arguments:
      alternate-exchange: data.analysis.dlx
    description: "4H and 1H market data updates"
    bindings_example:
      - "EURUSD.4H"
      - "GBPUSD.1H"

  data.execution:
    type: topic
    durable: true
    arguments:
      alternate-exchange: data.execution.dlx
    description: "1m and 5m execution data"
    bindings_example:
      - "EURUSD.1m"
      - "GBPUSD.5m"

  # Trading signals
  signals:
    type: direct
    durable: true
    description: "Trading signals and setups"
    routing_keys:
      - "setup.new"
      - "entry.triggered"
      - "exit.signal"

  # Trade execution
  trades:
    type: direct
    durable: true
    arguments:
      x-message-ttl: 300000  # 5 minutes
    description: "Trade execution commands"
    routing_keys:
      - "execute.market"
      - "execute.limit"
      - "modify.order"
      - "cancel.order"

  # System events
  system:
    type: fanout
    durable: true
    description: "System-wide events and alerts"

  # Dead letter exchanges
  dlx:
    type: fanout
    durable: true
    description: "Failed message handling"

# Queue Definitions
queues:
  # Data consumption queues
  signal_generator.data:
    durable: true
    arguments:
      x-message-ttl: 3600000  # 1 hour
      x-max-length: 10000
    bindings:
      - exchange: data.analysis
        pattern: "*.4H"
      - exchange: data.analysis
        pattern: "*.1H"

  entry_manager.data:
    durable: true
    arguments:
      x-message-ttl: 300000  # 5 minutes
      x-max-length: 50000
    bindings:
      - exchange: data.execution
        pattern: "#"  # All execution data

  # Signal queues
  setups.pending:
    durable: true
    arguments:
      x-max-priority: 10
    bindings:
      - exchange: signals
        routing_key: "setup.new"

  entries.pending:
    durable: true
    arguments:
      x-max-priority: 10
      x-message-ttl: 300000  # 5 minutes
    bindings:
      - exchange: signals
        routing_key: "entry.triggered"

  # LLM analysis queue
  llm.requests:
    durable: true
    arguments:
      x-max-length: 100  # Rate limiting
      x-message-ttl: 1800000  # 30 minutes
    bindings:
      - exchange: signals
        routing_key: "llm.analyze"

  # Trade execution queues
  trades.pending:
    durable: true
    arguments:
      x-max-priority: 10
      x-message-ttl: 60000  # 1 minute
    bindings:
      - exchange: trades
        routing_key: "execute.market"
      - exchange: trades
        routing_key: "execute.limit"

  # System monitoring
  alerts.all:
    durable: true
    bindings:
      - exchange: system

  # Dead letter queue
  failed_messages:
    durable: true
    arguments:
      x-message-ttl: 86400000  # 24 hours
    bindings:
      - exchange: dlx

# Message Schemas
message_schemas:
  MarketData:
    type: object
    required: [symbol, timeframe, timestamp, candles]
    properties:
      symbol: string
      timeframe: string
      timestamp: ISO8601
      candles:
        type: array
        items:
          type: object
          properties:
            time: ISO8601
            open: number
            high: number
            low: number
            close: number
            volume: integer

  Setup:
    type: object
    required: [id, symbol, direction, confidence]
    properties:
      id: UUID
      symbol: string
      direction: enum[LONG, SHORT]
      entry_zone:
        high: number
        low: number
      stop_loss: number
      take_profit: array[number]
      confidence: number
      sources: array[string]
      metadata: object

  TradeCommand:
    type: object
    required: [action, symbol, size]
    properties:
      action: enum[BUY, SELL]
      symbol: string
      size: number
      order_type: enum[MARKET, LIMIT]
      price: number  # Required for LIMIT
      stop_loss: number
      take_profit: number
      metadata: object
```

### Message Flow Examples

```python
# 1. New candle data arrives
{
    "exchange": "data.analysis",
    "routing_key": "EURUSD.4H",
    "message": {
        "symbol": "EURUSD",
        "timeframe": "4H",
        "timestamp": "2024-01-20T12:00:00Z",
        "candles": [{
            "time": "2024-01-20T12:00:00Z",
            "open": 1.0890,
            "high": 1.0895,
            "low": 1.0885,
            "close": 1.0892,
            "volume": 125000
        }]
    }
}

# 2. Setup identified
{
    "exchange": "signals",
    "routing_key": "setup.new",
    "message": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "symbol": "EURUSD",
        "direction": "LONG",
        "entry_zone": {
            "high": 1.0895,
            "low": 1.0890
        },
        "stop_loss": 1.0880,
        "take_profit": [1.0910, 1.0920, 1.0940],
        "confidence": 0.75,
        "sources": ["ML", "Elliott"],
        "valid_until": "2024-01-21T12:00:00Z"
    }
}

# 3. Trade execution command
{
    "exchange": "trades",
    "routing_key": "execute.market",
    "priority": 9,
    "message": {
        "action": "BUY",
        "symbol": "EURUSD",
        "size": 10000,
        "order_type": "MARKET",
        "stop_loss": 1.0880,
        "take_profit": 1.0910,
        "metadata": {
            "setup_id": "550e8400-e29b-41d4-a716-446655440000",
            "entry_pattern": "pin_bar_reversal"
        }
    }
}
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)

#### Day 1-2: Infrastructure Setup
- [ ] Create project structure
- [ ] Set up Docker Compose environment
- [ ] Initialize databases (TimescaleDB, Redis)
- [ ] Configure RabbitMQ exchanges and queues
- [ ] Create base service template

#### Day 3-4: Data Collector Service
- [ ] Implement Polygon API integration
- [ ] Create dual-speed collection loops
- [ ] Set up TimescaleDB storage
- [ ] Implement message publishing
- [ ] Add error handling and retries

#### Day 5-7: Testing & Validation
- [ ] Unit tests for data collector
- [ ] Integration tests with RabbitMQ
- [ ] Verify data storage and retrieval
- [ ] Performance benchmarking
- [ ] Documentation updates

### Phase 2: Intelligence Layer (Week 2)

#### Day 8-9: Signal Generator Service
- [ ] Port existing ML models
- [ ] Integrate Elliott Wave analyzer
- [ ] Implement setup identification logic
- [ ] Create message consumers/publishers
- [ ] Add confluence validation

#### Day 10-11: LLM Analyzer Service
- [ ] Set up OpenAI GPT-4V client
- [ ] Implement chart generation
- [ ] Create analysis caching layer
- [ ] Add cost tracking
- [ ] Implement rate limiting

#### Day 12-14: Integration Testing
- [ ] End-to-end signal flow testing
- [ ] LLM analysis validation
- [ ] Performance optimization
- [ ] Error scenario testing
- [ ] Documentation

### Phase 3: Execution Layer (Week 3)

#### Day 15-16: Entry Manager Service
- [ ] Implement 1-minute monitoring
- [ ] Create entry pattern recognition
- [ ] Add entry validation logic
- [ ] Set up active setup tracking
- [ ] Message flow implementation

#### Day 17-18: Trade Manager Service
- [ ] IB API integration
- [ ] Position sizing algorithms
- [ ] Risk management implementation
- [ ] Order execution logic
- [ ] Position tracking system

#### Day 19-21: Paper Trading
- [ ] Complete system integration
- [ ] Paper trading mode
- [ ] Performance tracking
- [ ] Bug fixes and optimization
- [ ] Prepare for live deployment

### Phase 4: Production (Week 4)

#### Day 22-23: Monitor Service
- [ ] Web dashboard (FastAPI + Vue.js)
- [ ] WebSocket real-time updates
- [ ] Alert system implementation
- [ ] Performance analytics
- [ ] System health monitoring

#### Day 24-25: Production Hardening
- [ ] Comprehensive error handling
- [ ] Logging and monitoring setup
- [ ] Backup and recovery procedures
- [ ] Security audit
- [ ] Performance tuning

#### Day 26-28: Go Live
- [ ] Production deployment
- [ ] Start with minimal positions
- [ ] Monitor system closely
- [ ] Gather metrics
- [ ] Iterate based on results

---

## Risk Management

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Service failure | Medium | High | Each service runs independently; automatic restarts |
| Data feed interruption | Low | High | Multiple data sources; graceful degradation |
| Message queue failure | Low | High | Persistent messages; automatic reconnection |
| Database corruption | Very Low | Critical | Regular backups; replication |
| API rate limits | Medium | Medium | Caching; request throttling; multiple API keys |

### Trading Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Poor signal quality | Medium | High | Multiple validation layers; paper trading first |
| Execution slippage | Medium | Medium | Limit orders; realistic backtesting |
| Over-leveraging | Low | Critical | Hard position limits; risk checks |
| System bugs | Medium | High | Comprehensive testing; gradual rollout |
| Market gaps | Low | High | Stop losses; position limits |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| System downtime | Low | Medium | Automated monitoring; quick restart procedures |
| Configuration errors | Medium | Medium | Version control; validation checks |
| Cost overruns | Low | Low | Usage monitoring; spending alerts |
| Security breach | Low | High | Encryption; access controls; regular audits |

---

## Success Metrics

### System Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Data latency | < 1 second | Time from API to database |
| Signal generation | < 5 seconds | Time from data to signal |
| LLM analysis | < 30 seconds | Time for chart analysis |
| System uptime | > 99% | Monitoring service |
| Message processing | > 1000/second | RabbitMQ metrics |

### Trading Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Win rate | > 40% | Winning trades / Total trades |
| Average R:R | > 2:1 | Average profit / Average loss |
| Profit factor | > 1.5 | Gross profit / Gross loss |
| Max drawdown | < 10% | Peak to trough decline |
| Sharpe ratio | > 1.5 | Risk-adjusted returns |

### Operational Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Setup accuracy | > 70% | Valid setups / Total setups |
| Entry efficiency | > 80% | Filled entries / Entry attempts |
| Cost per trade | < $1 | Total costs / Trade count |
| LLM cache hit rate | > 60% | Cache hits / Total requests |
| Alert accuracy | > 90% | Valid alerts / Total alerts |

---

## Deployment Guide

### Local Development

```bash
# 1. Clone repository
git clone https://github.com/username/fxml4-redesign.git
cd fxml4-redesign

# 2. Create environment file
cp .env.example .env
# Edit .env with your API keys

# 3. Start infrastructure
docker-compose up -d

# 4. Initialize database
python scripts/init_database.py

# 5. Start services (in separate terminals)
python services/data_collector/main.py
python services/signal_generator/main.py
python services/llm_analyzer/main.py
python services/entry_manager/main.py
python services/trade_manager/main.py
python services/monitor/main.py

# 6. Access dashboard
open http://localhost:8000
```

### Production Deployment (Single VPS)

```bash
# 1. Server setup (Ubuntu 22.04)
sudo apt update && sudo apt upgrade -y
sudo apt install docker docker-compose python3.10 python3-pip

# 2. Clone and configure
git clone https://github.com/username/fxml4-redesign.git
cd fxml4-redesign
cp .env.production .env
# Edit .env with production settings

# 3. Build and deploy
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# 4. Set up systemd services
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fxml4-*
sudo systemctl start fxml4-*

# 5. Configure nginx
sudo cp deploy/nginx/fxml4.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/fxml4.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 6. Set up monitoring
# Install Prometheus node exporter
# Configure Grafana dashboards
# Set up alerts
```

### Production Checklist

- [ ] SSL certificates configured
- [ ] Firewall rules set (only required ports open)
- [ ] Database backups scheduled
- [ ] Log rotation configured
- [ ] Monitoring alerts set up
- [ ] API keys secured in environment variables
- [ ] Rate limiting configured
- [ ] Error tracking (Sentry) integrated
- [ ] Performance monitoring active
- [ ] Disaster recovery plan documented

---

## Maintenance Guide

### Daily Tasks
- Check system dashboard for anomalies
- Review overnight trades and positions
- Verify data collection is running
- Check for any critical alerts

### Weekly Tasks
- Review trading performance metrics
- Analyze losing trades for patterns
- Check system resource usage
- Update market symbols if needed
- Review and clear old logs

### Monthly Tasks
- Full system backup
- Performance analysis and optimization
- Review and update trading parameters
- Security audit
- Cost analysis and optimization

### Troubleshooting Guide

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| No signals generated | Check data flow, verify ML models loaded | Restart signal generator, check logs |
| High latency | Monitor RabbitMQ queue depth | Scale consumers, optimize queries |
| Missed entries | Check 1m data collection | Reduce execution interval |
| LLM errors | Check API limits, credentials | Implement retry logic, check cache |
| Database slow | Check query performance | Add indexes, optimize queries |

---

## Conclusion

This architecture redesign addresses all identified issues in the current FXML4 system:

1. **Proper LLM utilization** through dedicated analyzer service
2. **Improved performance** via better signal generation and validation
3. **Scalability** through microservices and message queuing
4. **Maintainability** with clear separation of concerns
5. **Cost-effectiveness** suitable for personal trading

The phased implementation approach allows for gradual rollout with continuous validation, minimizing risk while maximizing the probability of success.

## Appendices

### A. API Documentation
[Detailed API specifications for each service]

### B. Message Schema Reference
[Complete message format documentation]

### C. Configuration Reference
[All configuration options explained]

### D. Monitoring Setup
[Grafana dashboards and Prometheus queries]

### E. Disaster Recovery Procedures
[Step-by-step recovery guide]
