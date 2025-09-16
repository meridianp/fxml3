# FXML4 Redesigned - Microservices Architecture

## Overview

This is a complete architectural redesign of the FXML4 trading system, implementing a microservices approach with proper separation of concerns. The system is designed for personal swing trading with multi-timeframe analysis (4H for setups, 1m for precise entries).

## Architecture

### Core Services

1. **Data Collector Service** - Dual-speed market data collection
2. **Signal Generator Service** - ML and Elliott Wave signal generation
3. **LLM Analyzer Service** - GPT-4V chart analysis and validation
4. **Entry Manager Service** - Precision entry timing and execution
5. **Trade Manager Service** - Position management and exits
6. **Monitor Service** - System monitoring and web dashboard

### Infrastructure

- **TimescaleDB** - Time-series database with hypertables
- **RabbitMQ** - Message broker for service communication
- **Redis** - Caching and session storage
- **Docker Compose** - Container orchestration

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for development)
- Interactive Brokers Gateway (for live trading)

### Environment Setup

1. Clone and navigate to the redesign directory:
```bash
cd fxml4_redesign
```

2. Copy environment template:
```bash
cp .env.example .env
```

3. Edit `.env` with your configuration:
```bash
# IB Gateway settings
IB_GATEWAY_HOST=127.0.0.1
IB_GATEWAY_PORT=7497  # 7497 for paper, 7496 for live
IB_CLIENT_ID=1

# API Keys (optional for testing)
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

### Running the System

1. Start infrastructure services:
```bash
docker-compose up -d timescaledb rabbitmq redis
```

2. Wait for services to be healthy:
```bash
docker-compose ps
```

3. Start trading services:
```bash
docker-compose up -d data_collector signal_generator llm_analyzer
docker-compose up -d entry_manager trade_manager monitor
```

4. Access the monitoring dashboard:
```
http://localhost:8080
```

### Development Mode

For development, you can run services locally:

```bash
# Install dependencies
pip install -r requirements-base.txt

# Set environment variables
export PYTHONPATH=$PWD
export DB_HOST=localhost
export RABBITMQ_HOST=localhost
export REDIS_HOST=localhost

# Run a service
cd services/data_collector
python main.py
```

## System Features

### Data Collection
- **Dual-speed collection**: 5-minute intervals for all symbols, 30-second intervals for active symbols
- **Smart activation**: Symbols become "active" when there are recent signals or open trades
- **Tick processing**: Real-time tick data processing and aggregation
- **Quality monitoring**: Data validation and gap detection

### Signal Generation
- **ML Ensemble**: Random Forest + XGBoost with walk-forward validation
- **Elliott Wave**: Pattern recognition with confidence scoring
- **Multi-timeframe**: Confluence across daily, 4H, and 1H timeframes
- **Risk management**: Automatic position sizing and stop-loss calculation

### LLM Integration
- **Chart analysis**: GPT-4V visual analysis of multi-timeframe charts
- **Pattern validation**: AI confirmation of technical patterns
- **Market context**: Sentiment and news integration
- **Cost optimization**: Smart caching and selective LLM usage

### Trade Management
- **Precision entries**: 1-minute data for optimal entry timing
- **Dynamic stops**: Trailing stops with volatility adjustment
- **Multiple exits**: Partial profit-taking at multiple levels
- **Risk controls**: Maximum drawdown and position size limits

## Configuration

### Service Configuration

Each service can be configured via environment variables or configuration files:

```yaml
# config/data_collector.yml
collection:
  slow_interval: 300  # 5 minutes
  fast_interval: 30   # 30 seconds
  buffer_size: 100

symbols:
  - EURUSD
  - GBPUSD
  - USDJPY
  - AUDUSD
```

### Database Schema

The system uses TimescaleDB with the following key tables:

- `market_data` - Raw tick and bar data (hypertable)
- `indicators` - Technical indicators by timeframe
- `ml_signals` - Machine learning signals
- `elliott_patterns` - Elliott Wave patterns
- `llm_validations` - LLM analysis results
- `trading_signals` - Combined signals ready for execution
- `trades` - Trade execution and management

### Message Queue Design

RabbitMQ exchanges and routing:

- `market_data` exchange - Market data flow
  - `market.tick.{symbol}` - Tick data
  - `market.1min.{symbol}` - 1-minute bars
  - `market.ready.{symbol}` - Analysis-ready data

- `signals` exchange - Signal flow
  - `signal.ml.{symbol}` - ML signals
  - `signal.elliott.{symbol}` - Elliott Wave signals
  - `signal.validated.{symbol}` - LLM-validated signals

- `trades` exchange - Trade execution
  - `trade.entry.{symbol}` - Entry orders
  - `trade.executed.{symbol}` - Executed trades
  - `trade.update.{symbol}` - Trade updates

## Monitoring

### Health Checks

Each service provides health check endpoints:

```bash
# Check individual service health
curl http://localhost:8080/health/data-collector
curl http://localhost:8080/health/signal-generator
```

### Metrics

System metrics are available via the monitoring service:

- Service health and uptime
- Message queue statistics
- Database performance
- Trading performance metrics

### Logging

Structured logging with multiple levels:

- **INFO**: Normal operations
- **WARNING**: Non-critical issues
- **ERROR**: Service errors
- **CRITICAL**: System failures

Logs are centralized and can be viewed via:

```bash
docker-compose logs -f data_collector
docker-compose logs -f --tail=100 signal_generator
```

## Testing

### Unit Tests

Run tests for individual services:

```bash
cd services/data_collector
python -m pytest tests/ -v
```

### Integration Tests

Test the complete system:

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
python -m pytest tests/integration/ -v
```

### Performance Testing

Load testing tools are provided:

```bash
# Generate test market data
python tools/generate_test_data.py

# Run performance tests
python tools/performance_test.py
```

## Deployment

### Local Production

For local production deployment:

```bash
# Use production configuration
docker-compose -f docker-compose.prod.yml up -d
```

### VPS Deployment

The system is designed for single VPS deployment:

1. **Requirements**: 4GB RAM, 2 CPU cores, 50GB SSD
2. **Cost**: Approximately $20-40/month
3. **Monitoring**: Built-in health checks and alerting

## Performance Targets

### Latency (95th percentile)
- Data collection: < 100ms
- Signal generation: < 2s
- LLM validation: < 10s
- Trade execution: < 500ms

### Throughput
- Market data: 1000+ ticks/second
- Signal processing: 100+ signals/minute
- Database writes: 10000+ inserts/second

### Resource Usage
- Memory: < 2GB total
- CPU: < 50% average
- Storage: < 1GB/month growth

## Support

### Documentation
- [Technical Documentation](docs/technical-documentation-index.md)
- [API Reference](docs/api-reference/swagger-spec.yaml)
- [Troubleshooting Guide](docs/troubleshooting/troubleshooting-guide.md)

### Development
- Use GitHub issues for bug reports
- Follow conventional commit messages
- Maintain test coverage > 80%

## License

This project is proprietary software for personal trading use.
