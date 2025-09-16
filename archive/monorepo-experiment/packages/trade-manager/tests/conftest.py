"""Pytest configuration for Trade Manager tests."""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_broker_client():
    """Mock broker client for testing."""
    from unittest.mock import AsyncMock
    
    client = AsyncMock()
    client.get_account_info.return_value = {
        'account_id': 'test_account',
        'balance': 100000,
        'equity': 100000,
        'margin_used': 10000,
        'margin_available': 90000,
        'currency': 'USD'
    }
    
    client.place_order.return_value = {
        'order_id': 'order_123',
        'status': 'FILLED',
        'filled_quantity': 10000,
        'avg_fill_price': 1.1000,
        'commission': 10
    }
    
    client.get_positions.return_value = []
    
    client.get_market_data.return_value = {
        'symbol': 'EURUSD',
        'bid': 1.0999,
        'ask': 1.1001,
        'last': 1.1000,
        'volume': 1000000,
        'timestamp': datetime.now(timezone.utc)
    }
    
    return client


@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        'risk': {
            'max_position_size': 50000,
            'max_positions': 10,
            'max_positions_per_symbol': 3,
            'daily_loss_limit': 0.02,
            'max_drawdown': 0.15,
            'max_exposure': 0.30,
            'max_risk_per_trade': 0.02
        },
        'exit': {
            'trailing_stop_enabled': True,
            'trailing_stop_type': 'fixed',
            'trailing_stop_distance': 0.005,
            'breakeven_enabled': True,
            'breakeven_trigger': 0.003,
            'breakeven_offset': 0.0001,
            'partial_exit_enabled': True,
            'partial_exits': [
                {'profit_target': 0.005, 'exit_percentage': 0.33},
                {'profit_target': 0.010, 'exit_percentage': 0.50}
            ],
            'time_stop_enabled': True,
            'max_hold_time_minutes': 240
        },
        'pnl': {
            'track_daily': True,
            'track_symbol': True,
            'snapshot_interval_minutes': 5
        }
    }


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )