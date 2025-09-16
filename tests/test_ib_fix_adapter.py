"""Test suite for Interactive Brokers FIX Adapter.

This test suite validates the IB FIX adapter implementation with comprehensive
TDD coverage including connection pooling, FIX protocol integration,
order management, and performance requirements (<100ms order acknowledgment).

Test Categories:
- Connection management and pooling
- FIX session integration
- Order lifecycle management
- Market data handling
- Performance benchmarking
- Error handling and recovery
- Rate limiting and throttling
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.brokers.adapters.base import (
    AdapterConfig,
    BrokerAdapter,
    ConnectionStatus,
    OrderInfo,
    OrderStatus,
)
from fxml4.brokers.adapters.ib_fix_adapter import (
    ConnectionState,
    IBConnection,
    IBConnectionPool,
    IBFIXAdapter,
    IBFIXConfig,
    PerformanceMetrics,
)
from fxml4.fix.messages.admin import Heartbeat, Logon, Logout, TestRequest
from fxml4.fix.messages.orders import (
    ExecType,
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
    OrdStatus,
    OrdType,
    Side,
    TimeInForce,
)
from fxml4.fix.session_manager import FIXSession, SessionConfig, SessionState

logger = logging.getLogger(__name__)


class TestIBFIXAdapterConfiguration:
    """Test IB FIX adapter configuration and initialization."""

    def test_adapter_config_validation(self):
        """Test adapter configuration validation."""
        # Valid configuration
        config = IBFIXConfig(
            host="localhost",
            port=7497,
            client_id=1,
            account_id="DU123456",
            max_connections=5,
            connection_timeout=10,
            heartbeat_interval=30,
            order_timeout=30,
            market_data_timeout=5,
            enable_connection_pooling=True,
            max_orders_per_second=10,
            enable_performance_monitoring=True,
        )

        assert config.host == "localhost"
        assert config.port == 7497
        assert config.max_connections == 5
        assert config.enable_connection_pooling is True

    def test_adapter_initialization(self):
        """Test IB FIX adapter initialization."""
        config = IBFIXConfig()
        adapter = IBFIXAdapter(config)

        assert adapter.config == config
        assert adapter.connection_pool is not None
        assert adapter.performance_metrics is not None
        assert adapter.session_manager is not None
        assert len(adapter.active_orders) == 0

    def test_adapter_initialization_with_custom_config(self):
        """Test adapter initialization with custom configuration."""
        config = IBFIXConfig(
            host="gateway.ib.com", port=4001, client_id=100, max_connections=10
        )
        adapter = IBFIXAdapter(config)

        assert adapter.config.host == "gateway.ib.com"
        assert adapter.config.port == 4001
        assert adapter.config.client_id == 100
        assert adapter.config.max_connections == 10


class TestIBConnectionPool:
    """Test IB connection pool functionality."""

    @pytest.fixture
    def connection_pool(self):
        """Create connection pool for testing."""
        config = IBFIXConfig(max_connections=3)
        return IBConnectionPool(config)

    def test_connection_pool_initialization(self, connection_pool):
        """Test connection pool initialization."""
        assert connection_pool.config.max_connections == 3
        assert len(connection_pool.connections) == 0
        assert len(connection_pool.available_connections) == 0
        assert len(connection_pool.busy_connections) == 0

    @pytest.mark.asyncio
    async def test_acquire_connection_empty_pool(self, connection_pool):
        """Test acquiring connection from empty pool."""
        with patch.object(
            connection_pool, "_create_connection", return_value=Mock()
        ) as mock_create:
            connection = await connection_pool.acquire_connection()
            assert connection is not None
            mock_create.assert_called_once()
            assert len(connection_pool.busy_connections) == 1

    @pytest.mark.asyncio
    async def test_acquire_connection_with_available(self, connection_pool):
        """Test acquiring connection when available connections exist."""
        # Add available connection
        mock_connection = Mock()
        mock_connection.is_connected.return_value = True
        connection_pool.available_connections.append(mock_connection)

        connection = await connection_pool.acquire_connection()
        assert connection == mock_connection
        assert len(connection_pool.available_connections) == 0
        assert len(connection_pool.busy_connections) == 1

    @pytest.mark.asyncio
    async def test_release_connection(self, connection_pool):
        """Test releasing connection back to pool."""
        mock_connection = Mock()
        mock_connection.is_connected.return_value = True
        connection_pool.busy_connections.add(mock_connection)

        await connection_pool.release_connection(mock_connection)

        assert mock_connection not in connection_pool.busy_connections
        assert mock_connection in connection_pool.available_connections

    @pytest.mark.asyncio
    async def test_connection_pool_max_limit(self, connection_pool):
        """Test connection pool respects maximum connection limit."""
        # Fill pool to maximum
        for i in range(connection_pool.config.max_connections):
            mock_conn = Mock()
            connection_pool.busy_connections.add(mock_conn)

        # Should wait for available connection
        with patch.object(
            connection_pool, "_wait_for_available_connection", return_value=Mock()
        ) as mock_wait:
            await connection_pool.acquire_connection()
            mock_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_health_check(self, connection_pool):
        """Test connection health monitoring."""
        # Add unhealthy connection
        unhealthy_conn = Mock()
        unhealthy_conn.is_connected.return_value = False
        unhealthy_conn.is_healthy.return_value = False
        unhealthy_conn.disconnect = AsyncMock()
        unhealthy_conn.connection_id = "test_conn_1"
        connection_pool.available_connections.append(unhealthy_conn)

        await connection_pool.health_check()

        assert unhealthy_conn not in connection_pool.available_connections
        assert len(connection_pool.connections) == 0


class TestIBFIXSessionIntegration:
    """Test IB FIX adapter integration with FIX session manager."""

    @pytest.fixture
    def adapter(self):
        """Create IB FIX adapter for testing."""
        config = IBFIXConfig()
        return IBFIXAdapter(config)

    @pytest.mark.asyncio
    async def test_fix_session_creation(self, adapter):
        """Test FIX session creation for IB adapter."""
        session_config = SessionConfig(
            sender_comp_id="FXML4", target_comp_id="IB_GATEWAY", heartbeat_interval=30
        )

        session = adapter.session_manager.create_session("ib_session_1", session_config)

        assert session is not None
        assert session.config.sender_comp_id == "FXML4"
        assert session.config.target_comp_id == "IB_GATEWAY"
        assert session.state == SessionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_fix_session_logon_sequence(self, adapter):
        """Test FIX session logon sequence."""
        with patch.object(adapter, "_send_fix_message") as mock_send:
            await adapter._initiate_fix_session("test_session")

            # Should send logon message
            mock_send.assert_called()
            args = mock_send.call_args[0]
            assert isinstance(args[0], Logon)

    @pytest.mark.asyncio
    async def test_fix_session_heartbeat_handling(self, adapter):
        """Test FIX session heartbeat handling."""
        session = Mock()
        session.is_heartbeat_required.return_value = True
        session.state = SessionState.ACTIVE

        adapter.sessions["test"] = session

        with patch.object(adapter, "_send_heartbeat") as mock_heartbeat:
            await adapter._handle_session_heartbeats()
            mock_heartbeat.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_fix_message_routing(self, adapter):
        """Test FIX message routing to appropriate handlers."""
        # Test New Order Single routing
        new_order = NewOrderSingle(
            cl_ord_id="order_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        with patch.object(adapter, "_handle_new_order_single") as mock_handler:
            await adapter._route_fix_message(new_order)
            mock_handler.assert_called_once_with(new_order)


class TestIBOrderManagement:
    """Test IB FIX adapter order management capabilities."""

    @pytest.fixture
    def adapter(self):
        """Create IB FIX adapter for testing."""
        config = IBFIXConfig()
        adapter = IBFIXAdapter(config)
        adapter.connection_pool = Mock()
        adapter.ib_client = Mock()

        # Mock connection to be ready
        adapter.connection.status = ConnectionStatus.AUTHENTICATED
        adapter.connection.is_ready = Mock(return_value=True)

        return adapter

    @pytest.fixture
    def sample_order(self):
        """Create sample FIX new order single."""
        return NewOrderSingle(
            cl_ord_id="FXML4_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.DAY,
            transact_time=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_submit_market_order(self, adapter, sample_order):
        """Test submitting market order to IB."""
        # Mock successful connection acquisition
        mock_connection = Mock()
        mock_connection.client.placeOrder = Mock()
        mock_connection.order_count = 0
        adapter.connection_pool.acquire_connection = AsyncMock(
            return_value=mock_connection
        )
        adapter.connection_pool.release_connection = AsyncMock()
        adapter.ib_client.placeOrder = Mock()

        order_id = await adapter.submit_order(sample_order)

        assert order_id == "FXML4_001"
        assert sample_order.cl_ord_id in adapter.active_orders
        mock_connection.client.placeOrder.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_limit_order(self, adapter):
        """Test submitting limit order to IB."""
        limit_order = NewOrderSingle(
            cl_ord_id="FXML4_002",
            symbol="GBPUSD",
            side=Side.SELL,
            order_qty=50000,
            ord_type=OrdType.LIMIT,
            price=1.2500,
            time_in_force=TimeInForce.GOOD_TILL_CANCEL,
        )

        mock_connection = Mock()
        adapter.connection_pool.acquire_connection = AsyncMock(
            return_value=mock_connection
        )
        adapter.ib_client.placeOrder = Mock()

        await adapter.submit_order(limit_order)

        # Verify limit order parameters
        call_args = adapter.ib_client.placeOrder.call_args
        ib_order = call_args[0][2]  # Third argument is the IB order
        assert ib_order.orderType == "LMT"
        assert ib_order.lmtPrice == 1.2500

    @pytest.mark.asyncio
    async def test_cancel_order(self, adapter, sample_order):
        """Test canceling order in IB."""
        # Submit order first
        adapter.active_orders[sample_order.cl_ord_id] = OrderInfo(
            cl_ord_id=sample_order.cl_ord_id,
            status=OrderStatus.SUBMITTED,
            original_order=sample_order,
        )
        adapter.client_to_ib_orders[sample_order.cl_ord_id] = 1001

        # Cancel order
        cancel_request = OrderCancelRequest(
            cl_ord_id="CANCEL_001",
            orig_cl_ord_id=sample_order.cl_ord_id,
            symbol=sample_order.symbol,
            side=sample_order.side,
        )

        adapter.ib_client.cancelOrder = Mock()
        adapter.connection_pool.release_connection = AsyncMock()

        result = await adapter.cancel_order(cancel_request)

        assert result is True
        adapter.ib_client.cancelOrder.assert_called_once_with(1001)

    @pytest.mark.asyncio
    async def test_order_status_tracking(self, adapter, sample_order):
        """Test order status tracking and updates."""
        # Create order info
        order_info = OrderInfo(
            cl_ord_id=sample_order.cl_ord_id,
            status=OrderStatus.PENDING,
            original_order=sample_order,
        )
        adapter.active_orders[sample_order.cl_ord_id] = order_info

        # Simulate IB status update
        await adapter._handle_ib_order_status(
            orderId=1001,
            status="Submitted",
            filled=Decimal("0"),
            remaining=Decimal("100000"),
            avgFillPrice=0.0,
        )

        assert order_info.status == OrderStatus.SUBMITTED
        assert order_info.remaining_qty == 100000

    @pytest.mark.asyncio
    async def test_order_execution_handling(self, adapter, sample_order):
        """Test order execution and fill processing."""
        # Create order info
        order_info = OrderInfo(
            cl_ord_id=sample_order.cl_ord_id,
            status=OrderStatus.SUBMITTED,
            original_order=sample_order,
        )
        adapter.active_orders[sample_order.cl_ord_id] = order_info

        # Mock execution
        mock_execution = Mock()
        mock_execution.orderId = 1001
        mock_execution.execId = "EXEC_001"
        mock_execution.shares = Decimal("100000")
        mock_execution.price = 1.1250
        mock_execution.side = "BOT"  # IB side indicator

        with patch.object(adapter, "_create_execution_report") as mock_create_report:
            await adapter._handle_ib_execution(1001, mock_execution)

            mock_create_report.assert_called_once()
            assert order_info.status == OrderStatus.FILLED


class TestIBFIXPerformance:
    """Test IB FIX adapter performance requirements."""

    @pytest.fixture
    def adapter(self):
        """Create IB FIX adapter for testing."""
        config = IBFIXConfig(enable_performance_monitoring=True)
        adapter = IBFIXAdapter(config)
        adapter.connection_pool = Mock()
        adapter.ib_client = Mock()
        return adapter

    @pytest.mark.asyncio
    async def test_order_acknowledgment_latency(self, adapter):
        """Test order acknowledgment latency (<100ms requirement)."""
        order = NewOrderSingle(
            cl_ord_id="PERF_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        # Mock fast connection and submission
        mock_connection = Mock()
        adapter.connection_pool.acquire_connection = AsyncMock(
            return_value=mock_connection
        )
        adapter.ib_client.placeOrder = Mock()

        # Measure latency
        start_time = time.time()
        await adapter.submit_order(order)

        # Simulate immediate IB acknowledgment
        await adapter._handle_ib_order_status(
            orderId=1001,
            status="Submitted",
            filled=Decimal("0"),
            remaining=Decimal("100000"),
            avgFillPrice=0.0,
        )

        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000

        # Should be well under 100ms for mocked operations
        assert latency_ms < 100, f"Order acknowledgment took {latency_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_connection_pool_performance(self, adapter):
        """Test connection pool performance under load."""
        config = IBFIXConfig(max_connections=5)
        pool = IBConnectionPool(config)

        # Mock connection creation
        with patch.object(
            pool, "_create_connection", return_value=Mock()
        ) as mock_create:
            # Acquire multiple connections concurrently
            start_time = time.time()

            tasks = []
            for i in range(10):  # More requests than pool size
                task = asyncio.create_task(pool.acquire_connection())
                tasks.append(task)

            connections = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()

            # All requests should complete
            assert len([c for c in connections if not isinstance(c, Exception)]) == 10

            # Should not take too long even with queuing
            total_time_ms = (end_time - start_time) * 1000
            assert total_time_ms < 1000, f"Pool operations took {total_time_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, adapter):
        """Test performance metrics collection."""
        # Submit multiple orders to generate metrics
        orders = []
        for i in range(5):
            order = NewOrderSingle(
                cl_ord_id=f"METRIC_{i}",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=10000,
                ord_type=OrdType.MARKET,
            )
            orders.append(order)

        mock_connection = Mock()
        adapter.connection_pool.acquire_connection = AsyncMock(
            return_value=mock_connection
        )
        adapter.ib_client.placeOrder = Mock()

        # Submit orders
        for order in orders:
            await adapter.submit_order(order)

        # Check metrics
        metrics = adapter.performance_metrics
        assert metrics.total_orders_submitted >= 5
        assert metrics.orders_per_second > 0
        assert len(metrics.latency_samples) > 0

    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self, adapter):
        """Test order rate limiting enforcement."""
        adapter.config.max_orders_per_second = 2  # Very low limit for testing

        orders = []
        for i in range(5):  # More than rate limit
            order = NewOrderSingle(
                cl_ord_id=f"RATE_{i}",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=10000,
                ord_type=OrdType.MARKET,
            )
            orders.append(order)

        mock_connection = Mock()
        adapter.connection_pool.acquire_connection = AsyncMock(
            return_value=mock_connection
        )
        adapter.ib_client.placeOrder = Mock()

        # Submit orders rapidly
        start_time = time.time()
        for order in orders:
            await adapter.submit_order(order)
        end_time = time.time()

        # Should be rate limited (take more time)
        duration = end_time - start_time
        expected_min_duration = len(orders) / adapter.config.max_orders_per_second

        assert duration >= expected_min_duration * 0.8  # Allow some tolerance


class TestIBFIXErrorHandling:
    """Test IB FIX adapter error handling and recovery."""

    @pytest.fixture
    def adapter(self):
        """Create IB FIX adapter for testing."""
        config = IBFIXConfig()
        adapter = IBFIXAdapter(config)
        adapter.connection_pool = Mock()
        adapter.ib_client = Mock()
        return adapter

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self, adapter):
        """Test handling of connection failures."""
        # Mock connection failure
        adapter.connection_pool.acquire_connection = AsyncMock(
            side_effect=ConnectionError("IB Gateway not available")
        )

        order = NewOrderSingle(
            cl_ord_id="ERROR_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        with pytest.raises(ConnectionError):
            await adapter.submit_order(order)

    @pytest.mark.asyncio
    async def test_order_rejection_handling(self, adapter):
        """Test handling of order rejections from IB."""
        order = NewOrderSingle(
            cl_ord_id="REJECT_001",
            symbol="INVALID",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        # Create order info
        order_info = OrderInfo(
            cl_ord_id=order.cl_ord_id,
            status=OrderStatus.PENDING,
            original_order=order,
            ib_order_id=1001,
        )
        adapter.active_orders[order.cl_ord_id] = order_info
        adapter.pending_orders[1001] = order_info

        # Simulate IB rejection
        await adapter._handle_ib_error(1001, 200, "No security definition found")

        assert order_info.status == OrderStatus.REJECTED
        assert "No security definition found" in order_info.error_message

    @pytest.mark.asyncio
    async def test_session_recovery(self, adapter):
        """Test FIX session recovery after disconnect."""
        session = Mock()
        session.state = SessionState.ERROR
        session.session_id = "recovery_test"

        adapter.sessions["recovery_test"] = session

        with patch.object(adapter, "_reconnect_session") as mock_reconnect:
            await adapter._handle_session_recovery()
            mock_reconnect.assert_called_once_with("recovery_test")

    @pytest.mark.asyncio
    async def test_connection_pool_recovery(self, adapter):
        """Test connection pool recovery from failures."""
        config = IBFIXConfig(max_connections=2)
        pool = IBConnectionPool(config)

        # Add failed connection
        failed_conn = Mock()
        failed_conn.is_connected.return_value = False
        pool.available_connections.append(failed_conn)

        # Health check should remove failed connection
        await pool.health_check()

        assert failed_conn not in pool.available_connections
        assert len(pool.connections) == 0


class TestIBFIXMarketData:
    """Test IB FIX adapter market data capabilities."""

    @pytest.fixture
    def adapter(self):
        """Create IB FIX adapter for testing."""
        config = IBFIXConfig()
        adapter = IBFIXAdapter(config)
        adapter.ib_client = Mock()
        return adapter

    @pytest.mark.asyncio
    async def test_market_data_subscription(self, adapter):
        """Test market data subscription for symbols."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]

        result = await adapter.subscribe_market_data(symbols)

        assert result is True
        assert len(adapter.market_data_subscriptions) == 3

        # Verify IB market data requests
        assert adapter.ib_client.reqMktData.call_count == 3

    @pytest.mark.asyncio
    async def test_market_data_unsubscription(self, adapter):
        """Test market data unsubscription."""
        # Set up existing subscriptions
        adapter.market_data_subscriptions = {"EURUSD": 10001, "GBPUSD": 10002}

        await adapter.unsubscribe_market_data(["EURUSD"])

        assert "EURUSD" not in adapter.market_data_subscriptions
        assert "GBPUSD" in adapter.market_data_subscriptions

        adapter.ib_client.cancelMktData.assert_called_once_with(10001)

    @pytest.mark.asyncio
    async def test_market_data_processing(self, adapter):
        """Test processing of market data ticks."""
        # Set up subscription
        adapter.market_data_subscriptions["EURUSD"] = 10001

        with patch.object(adapter, "_process_market_tick") as mock_process:
            await adapter._handle_ib_tick_price(10001, 1, 1.1250)  # Bid price

            mock_process.assert_called_once_with("EURUSD", "bid", 1.1250)


class TestIBFIXIntegration:
    """Integration tests for IB FIX adapter."""

    @pytest.fixture
    def adapter(self):
        """Create fully configured IB FIX adapter."""
        config = IBFIXConfig(
            host="localhost",
            port=7497,
            enable_connection_pooling=True,
            max_connections=3,
            enable_performance_monitoring=True,
        )
        adapter = IBFIXAdapter(config)
        return adapter

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_order_lifecycle(self, adapter):
        """Test complete order lifecycle from submission to fill."""
        # Mock all external dependencies
        adapter.connection_pool = Mock()
        adapter.ib_client = Mock()

        mock_connection = Mock()
        adapter.connection_pool.acquire_connection = AsyncMock(
            return_value=mock_connection
        )

        # 1. Submit order
        order = NewOrderSingle(
            cl_ord_id="INTEGRATION_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        order_id = await adapter.submit_order(order)
        assert order_id == "INTEGRATION_001"
        assert order.cl_ord_id in adapter.active_orders

        # 2. Handle acknowledgment
        await adapter._handle_ib_order_status(
            orderId=1001,
            status="Submitted",
            filled=Decimal("0"),
            remaining=Decimal("100000"),
            avgFillPrice=0.0,
        )

        order_info = adapter.active_orders[order.cl_ord_id]
        assert order_info.status == OrderStatus.SUBMITTED

        # 3. Handle execution
        mock_execution = Mock()
        mock_execution.orderId = 1001
        mock_execution.execId = "EXEC_001"
        mock_execution.shares = Decimal("100000")
        mock_execution.price = 1.1250

        await adapter._handle_ib_execution(1001, mock_execution)

        assert order_info.status == OrderStatus.FILLED
        assert order_info.total_filled_qty == 100000
        assert order_info.avg_fill_price == 1.1250

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_order_handling(self, adapter):
        """Test handling multiple concurrent orders."""
        # Mock dependencies
        adapter.connection_pool = Mock()
        adapter.ib_client = Mock()

        mock_connection = Mock()
        adapter.connection_pool.acquire_connection = AsyncMock(
            return_value=mock_connection
        )

        # Submit multiple orders concurrently
        orders = []
        for i in range(5):
            order = NewOrderSingle(
                cl_ord_id=f"CONCURRENT_{i}",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=10000,
                ord_type=OrdType.MARKET,
            )
            orders.append(order)

        # Submit all orders
        tasks = [adapter.submit_order(order) for order in orders]
        order_ids = await asyncio.gather(*tasks)

        assert len(order_ids) == 5
        assert len(adapter.active_orders) == 5

        # Verify all orders were submitted to IB
        assert adapter.ib_client.placeOrder.call_count == 5

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_high_frequency_order_submission(self, adapter):
        """Test high-frequency order submission performance."""
        # Configure for high frequency
        adapter.config.max_orders_per_second = 100

        # Mock dependencies for speed
        adapter.connection_pool = Mock()
        adapter.ib_client = Mock()

        mock_connection = Mock()
        adapter.connection_pool.acquire_connection = AsyncMock(
            return_value=mock_connection
        )

        # Generate many orders
        orders = []
        for i in range(50):
            order = NewOrderSingle(
                cl_ord_id=f"HF_{i:03d}",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=1000,
                ord_type=OrdType.MARKET,
            )
            orders.append(order)

        # Submit orders and measure performance
        start_time = time.time()

        for order in orders:
            await adapter.submit_order(order)

        end_time = time.time()
        duration = end_time - start_time
        orders_per_second = len(orders) / duration

        logger.info(f"High-frequency test: {orders_per_second:.2f} orders/second")

        # Should handle at least configured rate
        assert orders_per_second >= adapter.config.max_orders_per_second * 0.8


# Performance benchmarks
class TestIBFIXBenchmarks:
    """Performance benchmarks for IB FIX adapter."""

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_order_submission_benchmark(self, benchmark):
        """Benchmark order submission performance."""
        config = IBFIXConfig()
        adapter = IBFIXAdapter(config)

        # Mock dependencies
        adapter.connection_pool = Mock()
        adapter.ib_client = Mock()

        mock_connection = Mock()
        adapter.connection_pool.acquire_connection = AsyncMock(
            return_value=mock_connection
        )

        order = NewOrderSingle(
            cl_ord_id="BENCHMARK_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        # Benchmark the submission
        result = await benchmark.pedantic(
            adapter.submit_order, args=(order,), iterations=100, rounds=10
        )

        assert result == "BENCHMARK_001"

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_connection_pool_benchmark(self, benchmark):
        """Benchmark connection pool performance."""
        config = IBFIXConfig(max_connections=10)
        pool = IBConnectionPool(config)

        # Mock connection creation
        with patch.object(pool, "_create_connection", return_value=Mock()):
            # Benchmark connection acquisition
            connection = await benchmark.pedantic(
                pool.acquire_connection, iterations=100, rounds=10
            )

            assert connection is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
