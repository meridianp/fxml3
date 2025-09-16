# Configuration Guide

This guide covers all configuration options for FXML4, from basic setup to advanced customization.

## Environment Configuration

### Creating the Environment File

First, create a `.env` file in the project root:

```bash
cp .env.example .env
```

### Essential Configuration

```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fxml4
TIMESCALEDB_HOST=localhost
TIMESCALEDB_PORT=5433
TIMESCALEDB_USER=postgres
TIMESCALEDB_PASSWORD=postgres
TIMESCALEDB_DATABASE=fxml4

# API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here
OPENAI_API_KEY=your_openai_key_here  # Optional

# LLM Configuration
LLM_MODEL=claude-opus-4-20250514
LLM_PROVIDER=anthropic

# Interactive Brokers
IB_GATEWAY_HOST=localhost
IB_GATEWAY_PORT=7497  # 7497 for paper, 7496 for live
IB_CLIENT_ID=1
IB_ACCOUNT=DU1234567  # Your paper trading account

# Google Cloud (Optional)
GCP_PROJECT=your-gcp-project
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

## Database Configuration

### PostgreSQL Setup

1. **Create the database**:
```sql
CREATE DATABASE fxml4;
CREATE USER fxml4_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE fxml4 TO fxml4_user;
```

2. **Run migrations**:
```bash
python scripts/init_db.py
```

### TimescaleDB Setup

For time-series data optimization:

```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create hypertable for market data
SELECT create_hypertable('market_data', 'timestamp');

-- Add compression policy
SELECT add_compression_policy('market_data', INTERVAL '7 days');
```

## Trading Configuration

### Strategy Parameters

Create `config/trading.yaml`:

```yaml
# Risk Management
risk:
  max_position_size: 0.02  # 2% per trade
  max_portfolio_risk: 0.06  # 6% total risk
  stop_loss_atr_multiplier: 2.0
  take_profit_atr_multiplier: 3.0

# Signal Generation
signals:
  ml_weight: 0.7  # 70% ML signals
  elliott_wave_weight: 0.3  # 30% Elliott Wave
  min_confidence: 0.6  # Minimum confidence threshold

# Elliott Wave Configuration
elliott_wave:
  use_visual_analysis: true
  chart_timeframes: ["4h", "1d"]
  min_wave_confidence: 0.5
  fibonacci_tolerance: 0.02  # 2% tolerance

# Backtesting
backtesting:
  initial_capital: 10000
  commission: 0.00005  # 0.5 pips
  slippage: 0.00002  # 0.2 pips
  use_spread: true
```

### Symbol Configuration

Define trading symbols in `config/symbols.yaml`:

```yaml
symbols:
  - symbol: EURUSD
    pip_size: 0.0001
    contract_size: 100000
    margin_requirement: 0.02
    trading_hours: "00:00-23:59"

  - symbol: GBPUSD
    pip_size: 0.0001
    contract_size: 100000
    margin_requirement: 0.02
    trading_hours: "00:00-23:59"

  - symbol: USDJPY
    pip_size: 0.01
    contract_size: 100000
    margin_requirement: 0.02
    trading_hours: "00:00-23:59"
```

## API Configuration

### FastAPI Settings

Configure the API server in `config/api.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  reload: false  # Set to true for development

cors:
  origins:
    - "http://localhost:3000"
    - "https://app.fxml4.io"
  allow_credentials: true
  allow_methods: ["*"]
  allow_headers: ["*"]

rate_limiting:
  enabled: true
  requests_per_minute: 60
  burst_size: 10

authentication:
  secret_key: "your-secret-key-here"
  algorithm: "HS256"
  access_token_expire_minutes: 1440  # 24 hours
```

## Feature Toggles

Control feature availability in `config/features.yaml`:

```yaml
features:
  elliott_wave_visual: true
  ml_signals: true
  paper_trading: true
  live_trading: false  # Requires additional setup
  vertex_ai_integration: false
  advanced_risk_management: true
  multi_timeframe_analysis: true
  sentiment_analysis: false
```

## Logging Configuration

Configure logging in `config/logging.yaml`:

```yaml
version: 1
disable_existing_loggers: false

formatters:
  default:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: default
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: detailed
    filename: logs/fxml4.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

loggers:
  fxml4:
    level: DEBUG
    handlers: [console, file]
    propagate: false

  fxml4.elliott_wave:
    level: INFO
    handlers: [console, file]

  fxml4.trading:
    level: INFO
    handlers: [console, file]

root:
  level: INFO
  handlers: [console]
```

## Performance Tuning

### Database Optimization

```yaml
# config/database.yaml
pool:
  size: 20
  max_overflow: 0
  timeout: 30
  recycle: 3600

query_optimization:
  enable_query_cache: true
  cache_size: 1000
  batch_size: 1000

indexes:
  - table: market_data
    columns: [symbol, timeframe, timestamp]
  - table: signals
    columns: [symbol, timestamp, signal_type]
```

### Memory Settings

```yaml
# config/performance.yaml
memory:
  max_dataframe_size: 1000000  # rows
  cache_size: 500  # MB
  gc_threshold: 0.8  # Trigger GC at 80% memory usage

processing:
  chunk_size: 10000
  parallel_workers: 4
  use_multiprocessing: true
```

## Docker Configuration

### Docker Compose Override

Create `docker-compose.override.yml` for local development:

```yaml
version: '3.8'

services:
  api:
    environment:
      - DEBUG=true
      - RELOAD=true
    volumes:
      - ./logs:/app/logs
      - ./output:/app/output
    ports:
      - "8000:8000"

  postgres:
    ports:
      - "5432:5432"

  timescaledb:
    ports:
      - "5433:5432"
```

## Validation

### Configuration Validation Script

Run the validation script to check your configuration:

```bash
python scripts/validate_config.py
```

This will check:
- Environment variables are set
- Database connections work
- API keys are valid
- File permissions are correct
- Required directories exist

### Common Issues

1. **Missing API Keys**
   ```
   Error: ANTHROPIC_API_KEY not set
   Solution: Add to .env file
   ```

2. **Database Connection Failed**
   ```
   Error: Could not connect to PostgreSQL
   Solution: Check DATABASE_URL and ensure PostgreSQL is running
   ```

3. **Invalid Configuration**
   ```
   Error: Invalid value for risk.max_position_size
   Solution: Ensure value is between 0.001 and 0.1
   ```

## Best Practices

1. **Security**
   - Never commit `.env` files to version control
   - Use strong passwords for database
   - Rotate API keys regularly
   - Use environment-specific configurations

2. **Performance**
   - Adjust worker counts based on CPU cores
   - Configure appropriate database pool sizes
   - Enable caching for frequently accessed data
   - Use batch processing for large datasets

3. **Monitoring**
   - Set up proper logging levels
   - Configure error alerting
   - Monitor resource usage
   - Track API rate limits

## Next Steps

- Review [trading strategies](../guides/trading-strategies.md) configuration
- Set up [Interactive Brokers](../integrations/interactive-brokers.md) connection
- Configure [Elliott Wave parameters](../features/elliott-wave/configuration.md)
- Optimize [performance settings](../troubleshooting/performance-tuning-guide.md)
