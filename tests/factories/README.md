# FXML4 Test Data Factories

This directory contains comprehensive Factory Boy factories for generating realistic test data across all FXML4 components. These factories eliminate test data duplication, ensure consistency, and provide realistic financial data for testing.

## 📋 Table of Contents

- [Overview](#overview)
- [Available Factories](#available-factories)
- [Quick Start](#quick-start)
- [Factory Features](#factory-features)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)
- [Advanced Usage](#advanced-usage)

## 🎯 Overview

The factory system provides:
- **Realistic Financial Data**: Proper OHLC relationships, valid spreads, realistic P&L calculations
- **Relationship Management**: Consistent foreign keys and entity relationships
- **Trait System**: Pre-configured variations (profitable trades, high-risk accounts, etc.)
- **Batch Creation**: Efficient generation of large datasets
- **Customization**: Override any field while maintaining data integrity

## 🏭 Available Factories

### User and Account Management
- `UserFactory` - User accounts with authentication data
- `TradingAccountFactory` - Trading accounts with balances and settings
- `UserProfileFactory` - User preferences and configurations
- `BrokerAccountFactory` - Broker-specific account settings

### Trading Entities
- `CurrencyPairFactory` - Forex pairs with realistic constraints
- `TradeFactory` - Completed trades with P&L calculations
- `PositionFactory` - Open positions with unrealized P&L
- `OrderFactory` - Trading orders with execution tracking
- `ExecutionFactory` - Trade execution details

### Market Data
- `MarketDataFactory` - OHLCV candlestick data
- `CandlestickFactory` - Enhanced candlestick patterns
- `TickDataFactory` - Bid/ask tick-level data
- `MarketSessionFactory` - Trading session characteristics
- `NewsEventFactory` - Market-moving news events

### Machine Learning
- `ModelFactory` - ML model configurations and metrics
- `FeatureFactory` - Feature engineering data
- `SignalFactory` - Trading signals with confidence scores
- `PredictionFactory` - ML predictions with uncertainty
- `BacktestFactory` - Backtest configurations
- `BacktestResultFactory` - Backtest performance results

### Analysis and Patterns
- `WavePatternFactory` - Elliott Wave pattern analysis
- `TechnicalIndicatorFactory` - Technical indicator calculations
- `MarketRegimeFactory` - Market regime classifications
- `SentimentDataFactory` - Market sentiment analysis
- `PatternRecognitionFactory` - Chart pattern detection

### Risk Management
- `RiskLimitFactory` - Risk limits and thresholds
- `RiskMetricFactory` - Risk calculations (VaR, drawdown, etc.)
- `DrawdownEventFactory` - Drawdown tracking and recovery
- `ExposureFactory` - Portfolio exposure analysis

### Compliance
- `ComplianceEventFactory` - Compliance violations and events
- `AuditLogFactory` - Comprehensive audit trails
- `RegulatoryReportFactory` - Regulatory submissions
- `TradeReportFactory` - Individual trade reports

### Infrastructure
- `BrokerConnectionFactory` - Broker integration settings
- `FIXSessionFactory` - FIX protocol session configs
- `MessageQueueFactory` - RabbitMQ queue management
- `DatabaseConnectionFactory` - Database connection monitoring

## 🚀 Quick Start

```python
from tests.factories import (
    UserFactory, TradingAccountFactory, TradeFactory,
    MarketDataFactory, SignalFactory
)

# Create basic entities
user = UserFactory()
account = TradingAccountFactory(user_id=user['user_id'])
trade = TradeFactory(account_id=account['account_id'])

# Create market data
candle = MarketDataFactory(symbol='EURUSD', trending_up=True)

# Create ML signal
signal = SignalFactory(symbol='EURUSD', high_confidence=True)

print(f"Created profitable trade: ${trade['net_pnl']:.2f}")
```

## ✨ Factory Features

### 🎭 Trait System
Use traits to create pre-configured variations:

```python
# User traits
new_user = UserFactory(new_user=True)          # Unverified user
premium_user = UserFactory(premium_user=True)  # High-privilege user
locked_user = UserFactory(locked_user=True)    # Account locked

# Trade traits
profitable_trade = TradeFactory(profitable=True)  # Guaranteed profit
losing_trade = TradeFactory(losing=True)          # Guaranteed loss
scalp_trade = TradeFactory(scalp=True)            # Short duration

# Market data traits
trending_up = MarketDataFactory(trending_up=True)
high_volatility = MarketDataFactory(high_volatility=True)
sideways = MarketDataFactory(sideways=True)
```

### 🔗 Relationship Management
Factories handle foreign key relationships automatically:

```python
# Manual relationship
user = UserFactory()
account = TradingAccountFactory(user_id=user['user_id'])

# Automatic relationship (generates linked user)
account = TradingAccountFactory()  # Creates user automatically
```

### 🎯 Realistic Constraints
All factories enforce financial and logical constraints:

```python
# Currency pair constraints
pair = CurrencyPairFactory(symbol='USDJPY')
assert pair['pip_size'] == Decimal('0.01')  # JPY pairs
assert pair['bid_price'] < pair['ask_price']

# Trade P&L calculations
trade = TradeFactory()
expected_pnl = (trade['exit_price'] - trade['entry_price']) * trade['quantity']
assert trade['gross_pnl'] == expected_pnl  # For LONG positions
```

## 📖 Usage Examples

### Creating Test Data for Backtesting

```python
from tests.factories import (
    MarketDataFactory, ModelFactory, BacktestFactory, BacktestResultFactory
)

# Create market data series
market_data = MarketDataFactory.create_batch(
    100,
    symbol='EURUSD',
    timeframe='1h',
    trending_up=True
)

# Create ML model
model = ModelFactory(
    algorithm='XGBoost',
    symbol='EURUSD',
    high_performer=True
)

# Create backtest
backtest = BacktestFactory(
    model_id=model['model_id'],
    symbols=['EURUSD']
)

# Create results
results = BacktestResultFactory(
    backtest_id=backtest['backtest_id'],
    profitable_strategy=True
)
```

### Risk Management Testing

```python
from tests.factories import RiskLimitFactory, DrawdownEventFactory, ExposureFactory

# Create risk limits
daily_loss_limit = RiskLimitFactory(
    limit_name='Daily Loss Limit',
    limit_value=5000,
    strict_limits=True
)

# Create drawdown event
drawdown = DrawdownEventFactory(
    severe_drawdown=True,
    ongoing_drawdown=True
)

# Create exposure analysis
exposure = ExposureFactory(
    exposure_type='currency_exposure',
    high_concentration=True
)
```

### Compliance Testing

```python
from tests.factories import ComplianceEventFactory, AuditLogFactory, TradeReportFactory

# Create compliance violation
violation = ComplianceEventFactory(
    event_type='position_limit_breach',
    high_severity=True
)

# Create audit trail
audit_logs = AuditLogFactory.create_batch(
    50,
    trading_activity=True
)

# Create regulatory reports
trade_reports = TradeReportFactory.create_batch(
    100,
    large_trade=True
)
```

### Performance Testing Data

```python
from tests.factories import (
    UserFactory, TradingAccountFactory, TradeFactory,
    MessageQueueFactory, DatabaseConnectionFactory
)

# Create high-volume trading scenario
users = UserFactory.create_batch(1000)
accounts = [
    TradingAccountFactory(user_id=user['user_id'], high_balance=True)
    for user in users[:100]  # Only 100 high-balance accounts
]
trades = TradeFactory.create_batch(10000)  # 10,000 trades

# Create infrastructure load scenario
message_queues = MessageQueueFactory.create_batch(
    10,
    high_throughput=True
)

db_connections = DatabaseConnectionFactory.create_batch(
    5,
    production_database=True
)
```

## 🎯 Best Practices

### 1. Use Appropriate Traits
```python
# Good: Use traits for common scenarios
profitable_trade = TradeFactory(profitable=True)
demo_account = TradingAccountFactory(demo_account=True)

# Avoid: Manual configuration of complex scenarios
trade = TradeFactory(
    exit_price=...,  # Complex manual calculation
    exit_reason='TAKE_PROFIT',
    net_pnl=...  # Error-prone manual calculation
)
```

### 2. Batch Creation for Performance
```python
# Good: Batch creation for large datasets
trades = TradeFactory.create_batch(1000)

# Avoid: Individual creation in loops
trades = [TradeFactory() for _ in range(1000)]  # Slower
```

### 3. Maintain Relationships
```python
# Good: Consistent relationships
user = UserFactory()
accounts = TradingAccountFactory.create_batch(3, user_id=user['user_id'])

# Avoid: Orphaned entities
accounts = TradingAccountFactory.create_batch(3)  # Different users
```

### 4. Use Realistic Constraints
```python
# Good: Use factory constraints
pair = CurrencyPairFactory(symbol='EURUSD')  # Proper pip size

# Avoid: Manual constraint violations
pair = CurrencyPairFactory(
    symbol='EURUSD',
    pip_size=Decimal('0.01')  # Wrong for EUR pairs
)
```

## 🔧 Advanced Usage

### Custom Factory Subclassing
```python
import factory
from tests.factories import TradeFactory

class ScalpingTradeFactory(TradeFactory):
    """Factory for scalping trades."""

    class Meta:
        model = dict

    # Override defaults for scalping
    duration_minutes = factory.fuzzy.FuzzyInteger(1, 10)
    quantity = factory.fuzzy.FuzzyDecimal(1.0, 5.0, 2)
    strategy_name = 'Scalping_Strategy'

    class Params:
        quick_profit = factory.Trait(
            exit_reason='TAKE_PROFIT',
            duration_minutes=factory.fuzzy.FuzzyInteger(1, 3)
        )
```

### Dynamic Relationship Building
```python
def create_trading_scenario(num_users=10, trades_per_user=50):
    """Create complete trading scenario."""
    scenario_data = {
        'users': [],
        'accounts': [],
        'trades': []
    }

    for _ in range(num_users):
        user = UserFactory(premium_user=True)
        account = TradingAccountFactory(
            user_id=user['user_id'],
            high_balance=True
        )

        trades = TradeFactory.create_batch(
            trades_per_user,
            account_id=account['account_id']
        )

        scenario_data['users'].append(user)
        scenario_data['accounts'].append(account)
        scenario_data['trades'].extend(trades)

    return scenario_data
```

### Integration with Test Fixtures
```python
import pytest
from tests.factories import MarketDataFactory

@pytest.fixture
def market_data_series():
    """Fixture providing realistic market data series."""
    return MarketDataFactory.create_batch(
        100,
        symbol='EURUSD',
        timeframe='1h'
    )

@pytest.fixture
def trading_environment():
    """Fixture providing complete trading environment."""
    user = UserFactory(premium_user=True)
    account = TradingAccountFactory(user_id=user['user_id'])

    return {
        'user': user,
        'account': account,
        'market_data': MarketDataFactory.create_batch(50)
    }

def test_trading_strategy(trading_environment):
    """Test using factory-generated environment."""
    account = trading_environment['account']
    assert account['trading_enabled'] is True
```

## 🧪 Testing the Factories

Run the comprehensive factory test suite:

```bash
# Test all factories
pytest tests/test_factories_comprehensive.py -v

# Test specific factory categories
pytest tests/test_factories_comprehensive.py::TestTradingFactories -v
pytest tests/test_factories_comprehensive.py::TestMLFactories -v

# Test factory performance
pytest tests/test_factories_comprehensive.py::TestFactoryPerformance -v
```

## 🤝 Contributing

When adding new factories:

1. Follow existing naming conventions (`EntityFactory`)
2. Include comprehensive traits for common scenarios
3. Validate all mathematical relationships
4. Add realistic constraints and ranges
5. Include test coverage in `test_factories_comprehensive.py`
6. Document usage examples in this README

## 📚 Integration with FXML4

These factories integrate seamlessly with:
- **Property-based testing** (Hypothesis strategies)
- **Performance benchmarks** (realistic load testing data)
- **API testing** (request/response validation)
- **ML pipeline testing** (training/validation datasets)
- **Risk management testing** (edge case scenarios)
- **Compliance testing** (regulatory scenarios)

For more information, see:
- [Property-based testing guide](../property_based/README.md)
- [Performance benchmarking](../performance/README.md)
- [API testing framework](../api/README.md)
