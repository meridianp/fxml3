"""Tests for Native FIX Protocol Broker Adapter."""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.brokers.adapters.base import AdapterConfig, ConnectionStatus
from fxml4.brokers.adapters.fix_adapter import FixBrokerAdapter, FIXConnection
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)
from fxml4.fix.session_manager import SessionState


@pytest.fixture
def adapter_config():
    """Create test adapter configuration."""
    return AdapterConfig(
        adapter_id="fix_test",
        broker_type="fix",
        broker_name="Mock FIX",
        connection_params={
            "host": "localhost",
            "port": 9876,
            "mock": True,  # Enable mock mode
            "session": {
                "sender_comp_id": "TEST",
                "target_comp_id": "BROKER",
                "fix_version": "FIX.4.2",
                "heartbeat_interval": 30,
            },
        },
        features={"simulate_fills": True, "fill_delay_ms": 100},
        enabled=True,
    )


@pytest.fixture
def mock_fix_adapter(adapter_config):
    """Create mock FIX adapter."""
    return FixBrokerAdapter(adapter_config)


@pytest.fixture
def sample_order():
    """Create sample order."""
    return NewOrderSingle(
        cl_ord_id=f"ORD_{uuid.uuid4().hex[:8]}",
        symbol="EUR/USD",
        side=Side.BUY,
        order_qty=100000,
        ord_type=OrdType.LIMIT,
        price=1.0850,
        time_in_force=TimeInForce.GTC,
        transact_time=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_cancel():
    """Create sample cancel request."""
    return OrderCancelRequest(
        cl_ord_id=f"CXL_{uuid.uuid4().hex[:8]}",
        orig_cl_ord_id="ORD_12345678",
        symbol="EUR/USD",
        side=Side.BUY,
        transact_time=datetime.now(timezone.utc),
    )


class TestFIXConnection:
    """Test FIX connection handling."""

    @pytest.mark.asyncio
    async def test_connection_init(self):
        """Test connection initialization."""
        conn = FIXConnection("localhost", 9876, use_ssl=False)

        assert conn.host == "localhost"
        assert conn.port == 9876
        assert conn.use_ssl is False
        assert conn.connected is False
        assert conn.socket is None

    @pytest.mark.asyncio
    async def test_connection_with_ssl(self):
        """Test SSL connection parameters."""
        conn = FIXConnection(
            "fix.broker.com",
            443,
            use_ssl=True,
            ssl_cert="/path/to/cert",
            ssl_key="/path/to/key",
        )

        assert conn.use_ssl is True
        assert conn.ssl_cert == "/path/to/cert"
        assert conn.ssl_key == "/path/to/key"

    @pytest.mark.asyncio
    async def test_mock_connection(self):
        """Test mock connection mode."""
        conn = FIXConnection("localhost", 9876)

        # Mock the asyncio.open_connection
        with patch("asyncio.open_connection") as mock_open:
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_open.return_value = (mock_reader, mock_writer)

            result = await conn.connect()

            assert result is True
            assert conn.connected is True
            assert conn.reader is mock_reader
            assert conn.writer is mock_writer

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test connection failure handling."""
        conn = FIXConnection("invalid.host", 9999)

        with patch(
            "asyncio.open_connection", side_effect=Exception("Connection failed")
        ):
            result = await conn.connect()

            assert result is False
            assert conn.connected is False


class TestFixBrokerAdapter:
    """Test FIX broker adapter."""

    @pytest.mark.asyncio
    async def test_adapter_init(self, mock_fix_adapter):
        """Test adapter initialization."""
        assert mock_fix_adapter.host == "localhost"
        assert mock_fix_adapter.port == 9876
        assert mock_fix_adapter.mock_mode is True
        assert mock_fix_adapter.session is None
        assert len(mock_fix_adapter.pending_orders) == 0

    @pytest.mark.asyncio
    async def test_mock_connect(self, mock_fix_adapter):
        """Test mock mode connection."""
        result = await mock_fix_adapter.connect()

        assert result is True
        assert mock_fix_adapter.adapter_connection.is_connected()
        assert mock_fix_adapter.adapter_connection.is_ready()
        assert mock_fix_adapter.session is not None
        assert mock_fix_adapter.session.state == SessionState.ACTIVE

    @pytest.mark.asyncio
    async def test_mock_disconnect(self, mock_fix_adapter):
        """Test mock mode disconnection."""
        # Connect first
        await mock_fix_adapter.connect()
        assert mock_fix_adapter.adapter_connection.is_connected()

        # Disconnect
        await mock_fix_adapter.disconnect()

        assert not mock_fix_adapter.adapter_connection.is_connected()
        assert mock_fix_adapter.session is None

    @pytest.mark.asyncio
    async def test_submit_order_mock(self, mock_fix_adapter, sample_order):
        """Test order submission in mock mode."""
        # Connect first
        await mock_fix_adapter.connect()

        # Submit order
        order_id = await mock_fix_adapter.submit_order(sample_order)

        assert order_id.startswith("FIX_")
        assert sample_order.cl_ord_id in mock_fix_adapter.pending_orders
        assert mock_fix_adapter.order_map[sample_order.cl_ord_id] == order_id
        assert mock_fix_adapter.metrics.total_orders == 1

        # Wait for mock acknowledgment
        await asyncio.sleep(0.2)

        # Order should be acknowledged
        assert mock_fix_adapter.metrics.filled_orders == 0  # Not filled yet

    @pytest.mark.asyncio
    async def test_submit_order_not_connected(self, mock_fix_adapter, sample_order):
        """Test order submission when not connected."""
        with pytest.raises(RuntimeError, match="FIX adapter not ready"):
            await mock_fix_adapter.submit_order(sample_order)

    @pytest.mark.asyncio
    async def test_cancel_order_mock(
        self, mock_fix_adapter, sample_order, sample_cancel
    ):
        """Test order cancellation in mock mode."""
        # Connect and submit order first
        await mock_fix_adapter.connect()
        order_id = await mock_fix_adapter.submit_order(sample_order)

        # Update cancel request with correct cl_ord_id
        sample_cancel.orig_cl_ord_id = sample_order.cl_ord_id

        # Cancel order
        result = await mock_fix_adapter.cancel_order(sample_cancel)

        assert result is True
        assert mock_fix_adapter.metrics.cancelled_orders == 1

        # Wait for mock cancel acknowledgment
        await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_execution_report_handling(self, mock_fix_adapter):
        """Test execution report handling."""
        await mock_fix_adapter.connect()

        # Create execution report
        report = ExecutionReport(
            order_id="FIX_12345678",
            cl_ord_id="ORD_ABCDEF",
            exec_id="EXEC_001",
            exec_type=ExecType.TRADE,
            ord_status=OrdStatus.FILLED,
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=100000,
            price=1.0850,
            cum_qty=100000,
            leaves_qty=0,
            avg_px=1.0850,
            transact_time=datetime.now(timezone.utc),
        )

        # Add order to pending
        mock_fix_adapter.pending_orders[report.cl_ord_id] = Mock()

        # Handle report
        await mock_fix_adapter._handle_execution_report(report)

        assert mock_fix_adapter.metrics.filled_orders == 1
        assert report.cl_ord_id not in mock_fix_adapter.pending_orders

    @pytest.mark.asyncio
    async def test_rejected_order_handling(self, mock_fix_adapter):
        """Test rejected order handling."""
        await mock_fix_adapter.connect()

        report = ExecutionReport(
            order_id="FIX_12345678",
            cl_ord_id="ORD_REJECT",
            exec_id="EXEC_REJ",
            exec_type=ExecType.REJECTED,
            ord_status=OrdStatus.REJECTED,
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=100000,
            cum_qty=0,
            leaves_qty=0,
            avg_px=0,
            transact_time=datetime.now(timezone.utc),
            text="Insufficient margin",
        )

        await mock_fix_adapter._handle_execution_report(report)

        assert mock_fix_adapter.metrics.rejected_orders == 1

    @pytest.mark.asyncio
    async def test_message_sequence_handling(self, mock_fix_adapter):
        """Test message sequence number handling."""
        await mock_fix_adapter.connect()

        session = mock_fix_adapter.session
        assert session is not None

        # Get sequence numbers
        seq1 = session.get_next_seq_num()
        seq2 = session.get_next_seq_num()
        seq3 = session.get_next_seq_num()

        assert seq2 == seq1 + 1
        assert seq3 == seq2 + 1

    @pytest.mark.asyncio
    async def test_heartbeat_monitoring(self, mock_fix_adapter):
        """Test heartbeat monitoring."""
        await mock_fix_adapter.connect()

        session = mock_fix_adapter.session
        assert session is not None

        # Check heartbeat required
        assert not session.is_heartbeat_required()  # Just connected

        # Simulate time passing
        session.last_heartbeat_sent = datetime.now(timezone.utc)
        assert session.is_connection_alive()

    @pytest.mark.asyncio
    async def test_real_connection_mode(self, adapter_config):
        """Test real connection mode (without mock)."""
        # Disable mock mode
        adapter_config.connection_params["mock"] = False
        adapter = FixBrokerAdapter(adapter_config)

        # Mock the connection
        with patch.object(adapter.connection, "connect", return_value=True):
            with patch.object(adapter, "_send_logon", new_callable=AsyncMock):
                with patch.object(adapter, "_receive_loop", new_callable=AsyncMock):
                    # This should timeout waiting for logon
                    result = await adapter.connect()

                    assert result is False  # Logon timeout

    def test_is_ready_checks(self, mock_fix_adapter):
        """Test adapter readiness checks."""
        # Not connected
        assert not mock_fix_adapter._is_ready()

        # Mock connected but no session
        mock_fix_adapter.adapter_connection._connected = True
        mock_fix_adapter.adapter_connection._authenticated = True
        assert not mock_fix_adapter._is_ready()

        # Mock session but not active
        mock_fix_adapter.session = Mock()
        mock_fix_adapter.session.state = SessionState.CONNECTING
        assert not mock_fix_adapter._is_ready()

        # Fully ready
        mock_fix_adapter.session.state = SessionState.ACTIVE
        assert mock_fix_adapter._is_ready()


class TestSimulatedFills:
    """Test simulated order fills in mock mode."""

    @pytest.mark.asyncio
    async def test_simulated_fill(self, mock_fix_adapter, sample_order):
        """Test simulated order fill."""
        await mock_fix_adapter.connect()

        # Submit order
        order_id = await mock_fix_adapter.submit_order(sample_order)

        # Wait for acknowledgment
        await asyncio.sleep(0.2)

        # Wait for simulated fill
        await asyncio.sleep(1.2)  # Default fill delay is 1 second

        # Check metrics
        assert mock_fix_adapter.metrics.filled_orders == 1
        assert sample_order.cl_ord_id not in mock_fix_adapter.pending_orders

    @pytest.mark.asyncio
    async def test_market_order_fill(self, mock_fix_adapter):
        """Test market order fill simulation."""
        await mock_fix_adapter.connect()

        # Create market order
        market_order = NewOrderSingle(
            cl_ord_id=f"MKT_{uuid.uuid4().hex[:8]}",
            symbol="GBP/USD",
            side=Side.SELL,
            order_qty=50000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IOC,
            transact_time=datetime.now(timezone.utc),
        )

        # Submit and wait for fill
        order_id = await mock_fix_adapter.submit_order(market_order)
        await asyncio.sleep(1.5)

        assert mock_fix_adapter.metrics.filled_orders == 1
