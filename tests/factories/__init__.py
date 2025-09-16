"""
Test Data Factories for FXML4
============================

This module provides Factory Boy factories for creating consistent, realistic test data
across the FXML4 test suite. Factories help eliminate test data duplication and ensure
consistent data structures for testing.

Key Features:
- Realistic financial data generation with proper constraints
- Relationship handling between related entities
- Customizable traits and sequences
- Integration with existing fixtures and test patterns
- Support for different market regimes and trading scenarios

Usage:
    from tests.factories import UserFactory, TradingAccountFactory, TradeFactory

    # Simple factory usage
    user = UserFactory()
    account = TradingAccountFactory(user=user)
    trade = TradeFactory(account=account)

    # Batch creation
    users = UserFactory.create_batch(10)

    # Custom attributes
    high_balance_account = TradingAccountFactory(balance=100000)

    # Using traits
    profitable_trade = TradeFactory(profitable=True)
    risky_trade = TradeFactory(high_risk=True)

Available Factories:
- UserFactory: User accounts with authentication data
- TradingAccountFactory: Trading accounts with realistic balances and settings
- CurrencyPairFactory: Currency pairs with proper constraints
- MarketDataFactory: OHLCV market data with realistic price movements
- TradeFactory: Individual trades with proper execution data
- PositionFactory: Trading positions with risk management data
- SignalFactory: Trading signals with ML predictions
- BacktestFactory: Backtest results and performance metrics
- ModelFactory: ML model metadata and configurations
- WavePatternFactory: Elliott Wave pattern data
- RiskLimitFactory: Risk management configurations
- ComplianceEventFactory: Regulatory compliance events
- AuditLogFactory: Security and trading audit logs
"""

from .analysis_factories import (
    MarketRegimeFactory,
    SentimentDataFactory,
    TechnicalIndicatorFactory,
    WavePatternFactory,
)
from .compliance_factories import (
    AuditLogFactory,
    ComplianceEventFactory,
    RegulatoryReportFactory,
    TradeReportFactory,
)
from .infrastructure_factories import (
    BrokerConnectionFactory,
    DatabaseConnectionFactory,
    FIXSessionFactory,
    MessageQueueFactory,
)
from .market_data_factories import (
    CandlestickFactory,
    MarketDataFactory,
    MarketSessionFactory,
    TickDataFactory,
)
from .ml_factories import (
    BacktestFactory,
    BacktestResultFactory,
    FeatureFactory,
    ModelFactory,
    PredictionFactory,
    SignalFactory,
)
from .risk_factories import (
    DrawdownEventFactory,
    ExposureFactory,
    RiskLimitFactory,
    RiskMetricFactory,
)
from .trading_factories import (
    CurrencyPairFactory,
    ExecutionFactory,
    OrderFactory,
    PositionFactory,
    TradeFactory,
)
from .user_factories import TradingAccountFactory, UserFactory, UserProfileFactory

__all__ = [
    # User and Account Factories
    "UserFactory",
    "TradingAccountFactory",
    "UserProfileFactory",
    # Trading Factories
    "CurrencyPairFactory",
    "TradeFactory",
    "PositionFactory",
    "OrderFactory",
    "ExecutionFactory",
    # Market Data Factories
    "MarketDataFactory",
    "CandlestickFactory",
    "TickDataFactory",
    "MarketSessionFactory",
    # ML and Signal Factories
    "SignalFactory",
    "ModelFactory",
    "FeatureFactory",
    "PredictionFactory",
    "BacktestFactory",
    "BacktestResultFactory",
    # Analysis Factories
    "WavePatternFactory",
    "TechnicalIndicatorFactory",
    "MarketRegimeFactory",
    "SentimentDataFactory",
    # Risk Management Factories
    "RiskLimitFactory",
    "RiskMetricFactory",
    "DrawdownEventFactory",
    "ExposureFactory",
    # Compliance Factories
    "ComplianceEventFactory",
    "AuditLogFactory",
    "RegulatoryReportFactory",
    "TradeReportFactory",
    # Infrastructure Factories
    "BrokerConnectionFactory",
    "FIXSessionFactory",
    "MessageQueueFactory",
    "DatabaseConnectionFactory",
]
