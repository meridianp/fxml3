"""Shared fixtures for broker adapter testing.

This module provides reusable fixtures for testing broker adapters,
reducing code duplication and ensuring consistency across test files.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from fxml4.brokers.adapters.base import AdapterConfig, AdapterMetrics, ConnectionStatus
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.market_data import MarketDataRequest, MarketDataSnapshot
from fxml4.fix.messages.order_modify import OrderCancelReplaceRequest
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)
from fxml4.fix.session_manager import FIXSession, SessionConfig, SessionState


# Configuration Fixtures
@pytest.fixture
def manual_adapter_config():
    """Manual adapter configuration for testing."""
    return AdapterConfig(
        adapter_type="manual",
        connection_params={},
        authentication={},
        features={
            "auto_reject_timeout": 300,
            "require_two_factor": False,
            "allow_risk_override": True,
            "simulate_execution": True,
            "simulated_fill_delay": 1,
            "audit_trail": True,
        },
        limits={"max_override_amount": 1000000},
    )


@pytest.fixture
def fix_adapter_config():
    """FIX adapter configuration for testing."""
    return AdapterConfig(
        adapter_type="fix",
        connection_params={
            "host": "test-fix-server.com",
            "port": 9876,
            "use_ssl": False,
            "session": {
                "sender_comp_id": "FXML4_TEST",
                "target_comp_id": "FIX_BROKER",
                "fix_version": "FIX.4.2",
                "heartbeat_interval": 30,
                "logon_timeout": 10,
                "reset_on_logon": True,
            },
            "max_reconnect_attempts": 3,
            "reconnect_delay": 5,
            "mock": False,
        },
        authentication={"username": "fix_user", "password": "fix_pass"},
        features={
            "supports_market_data": True,
            "supports_order_modification": True,
            "simulate_fills": True,
        },
    )


@pytest.fixture
def ssl_fix_adapter_config(fix_adapter_config):
    """SSL-enabled FIX adapter configuration."""
    config = fix_adapter_config
    config.connection_params.update(
        {
            "use_ssl": True,
            "ssl_cert": "/path/to/cert.pem",
            "ssl_key": "/path/to/key.pem",
        }
    )
    return config


@pytest.fixture
def ib_adapter_config():
    """Interactive Brokers adapter configuration for testing."""
    return AdapterConfig(
        adapter_type="ib",
        connection_params={
            "host": "127.0.0.1",
            "port": 7497,
            "client_id": 1,
            "account": "TEST_ACCOUNT",
            "timeout": 30,
            "mock": False,
        },
        authentication={"username": "ib_user", "password": "ib_pass"},
        features={
            "supports_market_data": True,
            "supports_historical_data": True,
            "supports_options": False,
            "real_time_bars": True,
        },
    )


@pytest.fixture
def fxcm_adapter_config():
    """FXCM adapter configuration for testing."""
    return AdapterConfig(
        adapter_type="fxcm",
        connection_params={
            "environment": "demo",
            "server": "demo-api.fxcm.com",
            "port": 443,
            "use_ssl": True,
            "mock": False,
        },
        authentication={
            "access_token": "test_access_token",
            "account_id": "test_account",
        },
        features={
            "supports_market_data": True,
            "supports_historical_data": True,
            "max_positions": 50,
        },
    )


# Order Fixtures
@pytest.fixture
def sample_market_order():
    """Sample market order for testing."""
    return NewOrderSingle(
        cl_ord_id=f"MKT_{uuid.uuid4().hex[:8].upper()}",
        symbol="EURUSD",
        side=Side.BUY,
        order_qty=100000,
        ord_type=OrdType.MARKET,
        time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
    )


@pytest.fixture
def sample_limit_order():
    """Sample limit order for testing."""
    return NewOrderSingle(
        cl_ord_id=f"LMT_{uuid.uuid4().hex[:8].upper()}",
        symbol="GBPUSD",
        side=Side.SELL,
        order_qty=50000,
        ord_type=OrdType.LIMIT,
        price=1.2500,
        time_in_force=TimeInForce.DAY,
    )


@pytest.fixture
def sample_stop_order():
    """Sample stop order for testing."""
    return NewOrderSingle(
        cl_ord_id=f"STP_{uuid.uuid4().hex[:8].upper()}",
        symbol="USDJPY",
        side=Side.BUY,
        order_qty=75000,
        ord_type=OrdType.STOP,
        stop_px=110.50,
        time_in_force=TimeInForce.DAY,
    )


@pytest.fixture
def sample_orders_batch(sample_market_order, sample_limit_order, sample_stop_order):
    """Batch of sample orders for testing."""
    return [sample_market_order, sample_limit_order, sample_stop_order]


# Execution Report Fixtures
@pytest.fixture
def sample_execution_report(sample_market_order):
    """Sample execution report for testing."""
    return ExecutionReport(
        order_id="ORDER_001",
        cl_ord_id=sample_market_order.cl_ord_id,
        exec_id=f"EXEC_{uuid.uuid4().hex[:8].upper()}",
        exec_type=ExecType.FILL,
        ord_status=OrdStatus.FILLED,
        symbol=sample_market_order.symbol,
        side=sample_market_order.side,
        order_qty=sample_market_order.order_qty,
        cum_qty=sample_market_order.order_qty,
        avg_px=1.0850,
        last_qty=sample_market_order.order_qty,
        last_px=1.0850,
        transact_time=datetime.utcnow(),
    )


@pytest.fixture
def partial_fill_report(sample_limit_order):
    """Partial fill execution report for testing."""
    return ExecutionReport(
        order_id="ORDER_002",
        cl_ord_id=sample_limit_order.cl_ord_id,
        exec_id=f"EXEC_{uuid.uuid4().hex[:8].upper()}",
        exec_type=ExecType.PARTIAL_FILL,
        ord_status=OrdStatus.PARTIALLY_FILLED,
        symbol=sample_limit_order.symbol,
        side=sample_limit_order.side,
        order_qty=sample_limit_order.order_qty,
        cum_qty=25000,  # Half filled
        avg_px=1.2500,
        last_qty=25000,
        last_px=1.2500,
        transact_time=datetime.utcnow(),
    )


@pytest.fixture
def rejection_report(sample_market_order):
    """Order rejection execution report for testing."""
    return ExecutionReport(
        order_id="ORDER_003",
        cl_ord_id=sample_market_order.cl_ord_id,
        exec_id=f"EXEC_{uuid.uuid4().hex[:8].upper()}",
        exec_type=ExecType.REJECTED,
        ord_status=OrdStatus.REJECTED,
        symbol=sample_market_order.symbol,
        side=sample_market_order.side,
        order_qty=sample_market_order.order_qty,
        cum_qty=0,
        text="Insufficient funds",
        transact_time=datetime.utcnow(),
    )


# Cancel/Modify Fixtures
@pytest.fixture
def sample_cancel_request(sample_limit_order):
    """Sample order cancellation request."""
    return OrderCancelRequest(
        orig_cl_ord_id=sample_limit_order.cl_ord_id,
        cl_ord_id=f"CANCEL_{uuid.uuid4().hex[:8].upper()}",
        symbol=sample_limit_order.symbol,
        side=sample_limit_order.side,
        transact_time=datetime.utcnow(),
    )


@pytest.fixture
def sample_modify_request(sample_limit_order):
    """Sample order modification request."""
    return OrderCancelReplaceRequest(
        orig_cl_ord_id=sample_limit_order.cl_ord_id,
        cl_ord_id=f"MODIFY_{uuid.uuid4().hex[:8].upper()}",
        symbol=sample_limit_order.symbol,
        side=sample_limit_order.side,
        order_qty=sample_limit_order.order_qty + 25000,  # Increase quantity
        ord_type=sample_limit_order.ord_type,
        price=1.2510,  # Better price
        time_in_force=sample_limit_order.time_in_force,
        transact_time=datetime.utcnow(),
    )


# Market Data Fixtures
@pytest.fixture
def sample_market_data_request():
    """Sample market data request."""
    return MarketDataRequest(
        md_req_id=f"MDR_{uuid.uuid4().hex[:8].upper()}",
        subscription_request_type="1",  # Snapshot + updates
        market_depth=1,
        md_entry_types=["0", "1"],  # Bid, Ask
        no_related_sym=[{"symbol": "EURUSD"}, {"symbol": "GBPUSD"}],
    )


@pytest.fixture
def sample_market_data_snapshot():
    """Sample market data snapshot."""
    return MarketDataSnapshot(
        symbol="EURUSD",
        md_entries=[
            {
                "md_entry_type": "0",
                "md_entry_px": 1.0850,
                "md_entry_size": 1000000,
            },  # Bid
            {
                "md_entry_type": "1",
                "md_entry_px": 1.0852,
                "md_entry_size": 1000000,
            },  # Ask
        ],
        timestamp=datetime.utcnow(),
    )


# Mock Objects
@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    websocket.receive_json = AsyncMock()
    websocket.close = AsyncMock()
    websocket.closed = False
    return websocket


@pytest.fixture
def mock_fix_session():
    """Mock FIX session."""
    session = MagicMock(spec=FIXSession)
    session.session_id = "TEST_SESSION_001"
    session.state = SessionState.ACTIVE
    session.get_next_seq_num.return_value = 1
    session.store_sent_message = MagicMock()
    session.reset_sequence_numbers = MagicMock()
    session.update_heartbeat_sent = MagicMock()
    session.update_heartbeat_received = MagicMock()

    # Mock stats
    session.stats = MagicMock()
    session.stats.messages_sent = 0
    session.stats.messages_received = 0
    session.stats.heartbeats_sent = 0
    session.stats.heartbeats_received = 0

    return session


@pytest.fixture
def mock_connection():
    """Mock adapter connection."""
    connection = MagicMock()
    connection.status = ConnectionStatus.DISCONNECTED
    connection.is_connected = False
    connection.connect = AsyncMock()
    connection.disconnect = AsyncMock()
    connection.send_message = AsyncMock()
    connection.last_heartbeat = datetime.utcnow()
    return connection


@pytest.fixture
def mock_ib_client():
    """Mock Interactive Brokers client."""
    client = MagicMock()
    client.connect = MagicMock()
    client.disconnect = MagicMock()
    client.isConnected = MagicMock(return_value=False)
    client.placeOrder = MagicMock()
    client.cancelOrder = MagicMock()
    client.reqMarketDataType = MagicMock()
    client.reqMktData = MagicMock()
    client.reqAccountUpdates = MagicMock()
    return client


@pytest.fixture
def mock_fxcm_connection():
    """Mock FXCM connection."""
    connection = MagicMock()
    connection.is_connected = MagicMock(return_value=False)
    connection.connect = MagicMock()
    connection.close = MagicMock()
    connection.get_instruments = MagicMock(return_value=["EURUSD", "GBPUSD"])
    connection.get_prices = MagicMock()
    connection.create_market_buy_order = MagicMock()
    connection.create_market_sell_order = MagicMock()
    return connection


@pytest.fixture
def mock_ib_adapter(mock_ib_client):
    """Mock Interactive Brokers adapter."""
    from fxml4.brokers.adapters.base import BrokerAdapter

    adapter = MagicMock(spec=BrokerAdapter)
    adapter.adapter_id = "test_ib_adapter"
    adapter.adapter_type = "ib"
    adapter.client = mock_ib_client
    adapter.connection_status = ConnectionStatus.DISCONNECTED
    adapter.is_connected = AsyncMock(return_value=False)
    adapter.connect = AsyncMock()
    adapter.disconnect = AsyncMock()
    adapter.submit_order = AsyncMock()
    adapter.cancel_order = AsyncMock()
    adapter.modify_order = AsyncMock()
    adapter.get_account_info = AsyncMock()
    adapter.get_positions = AsyncMock()
    adapter.subscribe_market_data = AsyncMock()
    adapter.unsubscribe_market_data = AsyncMock()

    # Mock metrics
    adapter.get_metrics = MagicMock()
    adapter.get_metrics.return_value = AdapterMetrics(
        orders_submitted=0,
        orders_filled=0,
        orders_rejected=0,
        orders_cancelled=0,
        connection_count=0,
        reconnection_count=0,
        last_heartbeat=datetime.utcnow(),
        uptime_seconds=0,
    )

    return adapter


# Adapter Metrics Fixtures
@pytest.fixture
def sample_adapter_metrics():
    """Sample adapter metrics for testing."""
    return AdapterMetrics(
        orders_submitted=10,
        orders_filled=8,
        orders_rejected=1,
        orders_cancelled=1,
        connection_count=5,
        reconnection_count=2,
        last_heartbeat=datetime.utcnow(),
        uptime_seconds=3600,
    )


# Test Data Fixtures
@pytest.fixture
def sample_trade_data():
    """Sample trade execution data."""
    return {
        "trade_id": f"TRADE_{uuid.uuid4().hex[:8].upper()}",
        "symbol": "EURUSD",
        "side": "BUY",
        "quantity": 100000,
        "price": 1.0850,
        "timestamp": datetime.utcnow(),
        "commission": 2.50,
        "execution_venue": "TEST_VENUE",
    }


@pytest.fixture
def sample_account_info():
    """Sample account information."""
    return {
        "account_id": "TEST_ACCOUNT_001",
        "currency": "USD",
        "balance": 100000.00,
        "equity": 105000.00,
        "margin_used": 5000.00,
        "margin_available": 95000.00,
        "open_positions": 3,
        "realized_pnl": 500.00,
        "unrealized_pnl": 5000.00,
    }


@pytest.fixture
def sample_position_data():
    """Sample position data."""
    return {
        "symbol": "EURUSD",
        "side": "LONG",
        "quantity": 100000,
        "avg_price": 1.0840,
        "current_price": 1.0850,
        "unrealized_pnl": 100.00,
        "timestamp": datetime.utcnow(),
    }
