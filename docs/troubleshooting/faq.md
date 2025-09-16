# FXML4 Frequently Asked Questions (FAQ)

## Table of Contents

1. [General Questions](#general-questions)
2. [Installation and Setup](#installation-and-setup)
3. [API Usage](#api-usage)
4. [Data and Market Information](#data-and-market-information)
5. [Backtesting](#backtesting)
6. [Authentication and Security](#authentication-and-security)
7. [Performance and Scaling](#performance-and-scaling)
8. [Troubleshooting](#troubleshooting)
9. [Development and Integration](#development-and-integration)

## General Questions

### Q: What is FXML4?

**A:** FXML4 is a comprehensive forex trading platform that combines machine learning, Elliott Wave analysis, and traditional technical analysis to generate trading signals and perform sophisticated backtesting. It integrates data from multiple sources and provides both API access and a user-friendly dashboard.

### Q: What makes FXML4 different from other trading platforms?

**A:** FXML4 uniquely combines:
- **Multi-strategy approach**: ML models, Elliott Wave analysis, and technical indicators
- **Advanced backtesting**: Event-driven engine with realistic execution modeling
- **LLM integration**: Uses GPT models for market analysis and pattern recognition
- **Cloud-native architecture**: Scalable, containerized deployment
- **Multiple data sources**: Alpha Vantage, Interactive Brokers, Yahoo Finance
- **Professional-grade infrastructure**: Monitoring, alerting, and operational excellence

### Q: What markets and instruments does FXML4 support?

**A:** Currently supported:
- **Forex pairs**: EURUSD, GBPUSD, USDCHF, USDJPY, and other major pairs
- **Timeframes**: 1 minute to 1 month intervals
- **Data sources**: Real-time and historical data from multiple providers

*Note: Cryptocurrency and stock support is in development.*

### Q: Is FXML4 suitable for live trading?

**A:** FXML4 provides paper trading capabilities and signal generation, but live trading should be approached with caution. Always:
- Test thoroughly in paper trading mode
- Start with small position sizes
- Understand the risks involved
- Comply with local regulations
- Consider this software as educational/research tool

## Installation and Setup

### Q: What are the system requirements for FXML4?

**A:** **Minimum requirements:**
- CPU: 2 cores, 2.0 GHz
- RAM: 4 GB
- Storage: 20 GB SSD
- Docker Engine 20.10+
- Network: Stable internet connection

**Recommended for production:**
- CPU: 8 cores, 3.0 GHz
- RAM: 16 GB
- Storage: 100 GB SSD
- Load balancer and redundancy

### Q: How do I install FXML4 locally?

**A:** Follow these steps:

```bash
# 1. Clone the repository
git clone https://github.com/meridianp/fxml4.git
cd fxml4

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# 3. Start with Docker Compose
docker-compose -f docker-compose.dev.yml up -d

# 4. Initialize the database
python scripts/init_db.py

# 5. Access the application
# API: http://localhost:8000
# Dashboard: http://localhost:8501
```

### Q: What external services do I need API keys for?

**A:** Required API keys:
- **Alpha Vantage**: For market data (free tier available)
- **OpenAI**: For LLM integration (paid service)

Optional services:
- **Interactive Brokers**: For live data and paper trading
- **Google Cloud**: For Vertex AI ML models

### Q: How do I get an Alpha Vantage API key?

**A:**
1. Visit [Alpha Vantage website](https://www.alphavantage.co/support/#api-key)
2. Sign up for a free account
3. Get your API key from the dashboard
4. Add it to your `.env` file: `ALPHA_VANTAGE_API_KEY=your_key_here`

*Note: Free tier has rate limits (5 calls/minute, 500 calls/day)*

## API Usage

### Q: How do I authenticate with the FXML4 API?

**A:** FXML4 uses JWT token authentication:

```bash
# 1. Get access token
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your_username&password=your_password"

# 2. Use token in subsequent requests
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/data
```

### Q: What are the API rate limits?

**A:** Default rate limits:
- **Data endpoints**: 100 requests/minute
- **Signal generation**: 50 requests/minute
- **Backtesting**: 10 requests/hour
- **General endpoints**: 200 requests/minute

*Rate limits can be adjusted in configuration for enterprise usage.*

### Q: How do I get market data via the API?

**A:** Use the `/data` endpoint:

```bash
curl -X POST http://localhost:8000/data \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": "1h",
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "limit": 1000
  }'
```

### Q: What data format does the API return?

**A:** All responses are in JSON format. Market data returns:

```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "count": 1000,
  "source": "alpha_vantage",
  "data": [
    {
      "timestamp": "2023-01-01T00:00:00Z",
      "open": 1.0701,
      "high": 1.0725,
      "low": 1.0698,
      "close": 1.0712,
      "volume": 15432
    }
  ]
}
```

### Q: How do I generate trading signals?

**A:** Use the `/signals` endpoint:

```bash
curl -X POST http://localhost:8000/signals \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": "4h",
    "strategy": "ml_strategy",
    "parameters": {
      "model": "random_forest",
      "threshold": 0.7
    }
  }'
```

## Data and Market Information

### Q: What data sources does FXML4 use?

**A:** FXML4 integrates multiple data sources:
- **Alpha Vantage**: Primary source for forex, stocks, crypto
- **Interactive Brokers**: Real-time data and paper trading
- **Yahoo Finance**: Backup source for some instruments
- **Economic calendars**: For fundamental analysis

### Q: How often is market data updated?

**A:** Update frequencies:
- **Real-time data**: Every few seconds (when markets are open)
- **Minute data**: Every minute
- **Hourly/Daily data**: At interval completion
- **Historical data**: On-demand via API calls

### Q: What happens if a data source is unavailable?

**A:** FXML4 implements fallback mechanisms:
1. **Primary source fails**: Automatically switch to backup source
2. **All sources fail**: Use cached data with staleness warnings
3. **Extended outages**: Generate alerts and notifications
4. **Recovery**: Automatic synchronization when sources return

### Q: How far back does historical data go?

**A:** Data availability varies by source:
- **Alpha Vantage**: 10+ years for major forex pairs
- **Interactive Brokers**: 1-2 years typically
- **Stored locally**: Accumulates over time as system runs

### Q: Can I import my own data?

**A:** Yes, FXML4 supports custom data import:

```python
# Example data import script
import pandas as pd
from fxml4.data_engineering.data_feeds.custom_feed import CustomDataFeed

# Prepare your data in OHLCV format
data = pd.read_csv('your_data.csv')
feed = CustomDataFeed()
feed.import_data(data, symbol='CUSTOM_PAIR', timeframe='1h')
```

## Backtesting

### Q: How do I run a backtest?

**A:** Use the `/backtest` endpoint:

```bash
curl -X POST http://localhost:8000/backtest \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": "4h",
    "strategy": "integrated_strategy",
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "initial_capital": 10000
  }'
```

### Q: What makes FXML4's backtesting realistic?

**A:** FXML4 uses advanced backtesting features:
- **Event-driven execution**: Processes data bar-by-bar
- **Realistic fills**: Models slippage and market impact
- **Commission modeling**: Includes broker fees
- **Latency simulation**: Accounts for execution delays
- **Position sizing**: Implements risk management rules
- **Walk-forward testing**: Prevents look-ahead bias

### Q: How long does a backtest take to run?

**A:** Execution time depends on:
- **Data range**: 1 year typically takes 30 seconds to 2 minutes
- **Timeframe**: Lower timeframes take longer
- **Strategy complexity**: ML strategies are slower than simple ones
- **System resources**: More CPU/RAM = faster execution

### Q: What performance metrics are calculated?

**A:** Comprehensive metrics including:
- **Return metrics**: Total, annualized, monthly returns
- **Risk metrics**: Sharpe ratio, Sortino ratio, maximum drawdown
- **Trade statistics**: Win rate, profit factor, average win/loss
- **Advanced metrics**: Recovery factor, expectancy, risk of ruin

### Q: Can I compare multiple backtests?

**A:** Yes, use the comparative analysis endpoint:

```bash
curl -X POST http://localhost:8000/performance/compare \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "backtest_ids": ["BT-20231201-143022", "BT-20231201-150133"],
    "metrics": ["total_return_pct", "sharpe_ratio", "max_drawdown_pct"]
  }'
```

### Q: How do I interpret backtest results?

**A:** Key metrics to focus on:
- **Total Return**: Overall profitability
- **Sharpe Ratio**: Risk-adjusted returns (>1.0 is good, >2.0 is excellent)
- **Maximum Drawdown**: Worst peak-to-trough decline (<20% preferred)
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Ratio of gross profit to gross loss (>1.5 preferred)

*Always consider multiple metrics together, not in isolation.*

## Authentication and Security

### Q: How secure is FXML4?

**A:** FXML4 implements multiple security layers:
- **JWT authentication**: Secure token-based authentication
- **HTTPS only**: All communications encrypted
- **API rate limiting**: Prevents abuse
- **Input validation**: Protects against injection attacks
- **Secret management**: Secure handling of API keys
- **Audit logging**: Tracks all user actions

### Q: How do I reset my password?

**A:** Currently, password reset is handled by administrators:
1. Contact support team
2. Provide username and verification
3. Administrator will reset password
4. You'll receive temporary credentials

*Self-service password reset is planned for future releases.*

### Q: Can I use FXML4 with my existing authentication system?

**A:** FXML4 supports integration with external auth systems:
- **LDAP/Active Directory**: Enterprise authentication
- **OAuth providers**: Google, GitHub, etc.
- **SAML**: Enterprise SSO solutions
- **Custom backends**: Via plugin architecture

Contact support for integration assistance.

### Q: How are API keys stored securely?

**A:** API keys are protected through:
- **Environment variables**: Never hardcoded
- **Kubernetes secrets**: Encrypted at rest
- **Least privilege**: Limited access to key stores
- **Rotation policies**: Regular key updates
- **Audit trails**: All key access logged

## Performance and Scaling

### Q: How many concurrent users can FXML4 handle?

**A:** Performance depends on deployment:
- **Single instance**: 10-50 concurrent users
- **Horizontal scaling**: 100s-1000s of users
- **Load balancer**: Distributes traffic across instances
- **Database scaling**: Separate read/write databases

### Q: How do I scale FXML4 for production?

**A:** Scaling strategies:

1. **Horizontal scaling**: Add more API instances
   ```bash
   kubectl scale deployment ftml4-api --replicas=5
   ```

2. **Database optimization**: Use read replicas, connection pooling

3. **Caching**: Implement Redis for frequently accessed data

4. **CDN**: Serve static content from edge locations

### Q: What monitoring is available?

**A:** Comprehensive monitoring includes:
- **Application metrics**: Response times, error rates, throughput
- **Infrastructure metrics**: CPU, memory, disk, network
- **Business metrics**: Signal accuracy, backtest performance
- **Alerts**: Proactive notifications for issues

### Q: How do I optimize API response times?

**A:** Performance optimization techniques:
- **Database indexing**: Optimize queries
- **Caching**: Cache frequently requested data
- **Compression**: Enable gzip compression
- **CDN**: Use content delivery networks
- **Query optimization**: Limit data returned

Example caching implementation:
```python
@cache.memoize(timeout=300)  # Cache for 5 minutes
def get_market_data(symbol, timeframe):
    return fetch_from_database(symbol, timeframe)
```

## Troubleshooting

### Q: API returns "Internal Server Error" (500)

**A:** Common causes and solutions:
1. **Database connection issues**: Check database status
2. **Memory limits**: Increase container memory
3. **External API failures**: Check third-party service status
4. **Configuration errors**: Verify environment variables

See [Troubleshooting Guide](troubleshooting-guide.md) for detailed steps.

### Q: Why am I getting "Rate limit exceeded" errors?

**A:** This occurs when you exceed API quotas:
1. **Check your usage**: Review request frequency
2. **Implement backoff**: Add delays between requests
3. **Optimize calls**: Cache responses, batch requests
4. **Upgrade plan**: Contact support for higher limits

### Q: Market data appears stale or missing

**A:** Data issues can be caused by:
1. **Data source problems**: Alpha Vantage API issues
2. **Network connectivity**: Check internet connection
3. **API key problems**: Verify key validity and quotas
4. **Market hours**: Some data only updates when markets are open

### Q: Backtests are running very slowly

**A:** Performance optimization:
1. **Reduce data range**: Test shorter periods first
2. **Increase timeframe**: Use 4h instead of 1m data
3. **Simplify strategy**: Remove complex calculations
4. **Add more resources**: Increase CPU/memory allocation

### Q: Dashboard won't load or is showing errors

**A:** Dashboard troubleshooting:
1. **Check API connectivity**: Ensure API is running
2. **Browser cache**: Clear cache and reload
3. **JavaScript errors**: Check browser console
4. **Authentication**: Verify you're logged in

## Development and Integration

### Q: How do I add a custom trading strategy?

**A:** Create a custom strategy function:

```python
# fxml4/strategy/my_custom_strategy.py
def my_custom_strategy(data, index, params):
    """
    Custom strategy implementation

    Args:
        data: OHLCV DataFrame
        index: Current bar index
        params: Strategy parameters

    Returns:
        dict: Signals dictionary
    """
    signals = {}

    # Your strategy logic here
    if your_entry_condition(data, index):
        signals['entry'] = True
        signals['direction'] = 'buy'  # or 'sell'
        signals['risk_pct'] = 0.02

    if your_exit_condition(data, index):
        signals['exit'] = True

    return signals
```

### Q: Can I integrate FXML4 with other trading platforms?

**A:** Yes, integration options include:
- **REST API**: Standard HTTP integration
- **WebSocket**: Real-time data streaming
- **Webhooks**: Event-driven notifications
- **Message queues**: Async communication via Redis/RabbitMQ

### Q: How do I contribute to FXML4 development?

**A:** Contributing process:
1. **Fork the repository** on GitHub
2. **Create feature branch**: `git checkout -b feature/my-feature`
3. **Make changes** and add tests
4. **Submit pull request** with clear description
5. **Code review** process with maintainers

### Q: What programming languages can I use with FXML4?

**A:** FXML4 is Python-based but supports integration via:
- **Python**: Native integration with full access
- **REST API**: Any language with HTTP support
- **WebSocket**: Real-time integration in any language
- **Command line**: Shell scripting integration

### Q: How do I add a new data source?

**A:** Implement the DataFeed interface:

```python
from fxml4.data_engineering.data_feeds.base_feed import DataFeed

class MyCustomFeed(DataFeed):
    def __init__(self, config):
        self.config = config

    def fetch_data(self, symbol, timeframe, start_date=None, end_date=None):
        # Implement your data fetching logic
        return pandas_dataframe

    def get_supported_symbols(self):
        return ['SYMBOL1', 'SYMBOL2']
```

### Q: Is there a Python SDK for FXML4?

**A:** Yes, you can use the FXML4 client library:

```python
from fxml4.client import FXML4Client

client = FXML4Client(
    base_url="https://api.fxml4.com",
    token="your_jwt_token"
)

# Get market data
data = client.get_market_data(
    symbol="EURUSD",
    timeframe="1h",
    start_date="2023-01-01"
)

# Run backtest
result = client.run_backtest(
    symbol="EURUSD",
    strategy="ml_strategy",
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

### Q: How do I set up a development environment?

**A:** Development setup:

```bash
# 1. Clone and setup
git clone https://github.com/meridianp/fxml4.git
cd fxml4
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Setup pre-commit hooks
pre-commit install

# 4. Run tests
pytest tests/

# 5. Start development server
uvicorn fxml4.api.main:app --reload
```

### Q: Where can I find API documentation?

**A:** API documentation is available:
- **Interactive docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI spec**: http://localhost:8000/openapi.json
- **Written docs**: [API Reference](../api-reference/)

### Q: How do I report bugs or request features?

**A:** Use GitHub for all issues:
- **Bug reports**: [GitHub Issues](https://github.com/meridianp/fxml4/issues)
- **Feature requests**: [GitHub Discussions](https://github.com/meridianp/fxml4/discussions)
- **Security issues**: Email security@ftml4.com
- **General questions**: [GitHub Discussions](https://github.com/meridianp/fxml4/discussions)

---

**Still have questions?**
- Check the [Documentation](../index.md)
- Browse [GitHub Discussions](https://github.com/meridianp/fxml4/discussions)
- Contact support: support@fxml4.com
