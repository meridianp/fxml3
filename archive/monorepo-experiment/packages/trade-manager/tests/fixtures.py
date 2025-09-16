"""Common test fixtures for Trade Manager tests."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any

from fxml4_trade_manager.domain import (
    MockTimeProvider, MockBrokerAdapter, MockEventPublisher,
    InMemoryMetricsCollector, InMemoryPositionRepository,
    MockMarketDataProvider, SimpleRiskCalculator,
    UTCTimeProvider
)


@pytest.fixture
def mock_time_provider():
    """Create a mock time provider for testing."""
    return MockTimeProvider()


@pytest.fixture
def utc_time_provider():
    """Create a UTC time provider."""
    return UTCTimeProvider()


@pytest.fixture
def mock_broker_adapter():
    """Create a mock broker adapter."""
    return MockBrokerAdapter()


@pytest.fixture
def mock_event_publisher():
    """Create a mock event publisher."""
    return MockEventPublisher()


@pytest.fixture
def mock_metrics_collector():
    """Create a mock metrics collector."""
    return InMemoryMetricsCollector()


@pytest.fixture
def mock_position_repository():
    """Create a mock position repository."""
    return InMemoryPositionRepository()


@pytest.fixture
def mock_market_data_provider():
    """Create a mock market data provider."""
    return MockMarketDataProvider()


@pytest.fixture
def mock_risk_calculator():
    """Create a mock risk calculator."""
    return SimpleRiskCalculator()


@pytest.fixture
def sample_position_data():
    """Sample position data for testing."""
    return {
        'position_id': 'pos_123',
        'signal_id': 'sig_456',
        'trade_id': 'trade_789',
        'symbol': 'EURUSD',
        'side': 'BUY',
        'target_quantity': 10000,
        'filled_quantity': 0,
        'remaining_quantity': 0,
        'target_entry': 1.1000,
        'avg_entry_price': 0,
        'current_price': 1.1000,
        'stop_loss': 1.0950,
        'take_profit_1': 1.1050,
        'take_profit_2': 1.1100,
        'take_profit_3': 1.1150,
        'broker': 'test_broker',
        'strategy': 'test_strategy'
    }


@pytest.fixture
def sample_order_request():
    """Sample order request data."""
    from fxml4_trade_manager.domain import OrderRequest, OrderSide, OrderType
    
    return OrderRequest(
        symbol='EURUSD',
        side=OrderSide.BUY,
        quantity=Decimal('10000'),
        order_type=OrderType.MARKET,
        metadata={'position_id': 'pos_123'}
    )


@pytest.fixture
def sample_trade_data():
    """Sample trade data."""
    return {
        'symbol': 'EURUSD',
        'side': 'BUY',
        'quantity': Decimal('10000'),
        'price': Decimal('1.1000'),
        'stop_loss': Decimal('1.0950'),
        'take_profit': Decimal('1.1050'),
        'metadata': {'strategy': 'test_strategy'}
    }


@pytest.fixture
def sample_account_data():
    """Sample account data."""
    return {
        'balance': Decimal('100000'),
        'equity': Decimal('100000'),
        'margin_used': Decimal('0'),
        'margin_available': Decimal('100000'),
        'peak_balance': Decimal('100000'),
        'currency': 'USD'
    }


@pytest.fixture
def sample_market_data():
    """Sample market data."""
    return {
        'symbol': 'EURUSD',
        'current_price': Decimal('1.1000'),
        'bid': Decimal('1.0999'),
        'ask': Decimal('1.1001'),
        'volume': Decimal('1000000'),
        'volatility': Decimal('0.001'),
        'atr': Decimal('0.0050'),
        'timestamp': datetime.now(timezone.utc)
    }