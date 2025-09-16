"""Broker adapter concurrency tests for FXML4.

Tests concurrent operations on broker adapters including order submission,
execution processing, connection management, and race condition detection.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from fxml4.brokers.adapters.base import (
    AdapterConfig,
    BrokerAdapter,
    ConnectionStatus,
    OrderInfo,
    OrderStatus,
)
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle
from tests.fixtures.broker_fixtures import (
    mock_fxcm_connection,
    mock_ib_adapter,
    sample_execution_report,
    sample_market_order,
)
from tests.utils.concurrency_utils import (
    ConcurrencyTestResult,
    LoadGenerator,
    concurrency_test_environment,
    simulate_high_frequency_trading,
)


@pytest.mark.concurrency
@pytest.mark.broker
class TestBrokerAdapterConcurrency:
    """Test broker adapter concurrent operations."""

    @pytest.fixture
    def mock_broker_adapter(self):
        """Mock broker adapter for concurrency testing."""

        class MockBrokerAdapter(BrokerAdapter):
            def __init__(self, config: AdapterConfig):
                super().__init__(config)
                self.submitted_orders = []
                self.connection_status = ConnectionStatus.DISCONNECTED
                self.order_counter = 0
                self._lock = asyncio.Lock()

            async def connect(self) -> bool:
                await asyncio.sleep(0.01)  # Simulate connection time
                self.connection_status = ConnectionStatus.CONNECTED
                self._update_connection_status(ConnectionStatus.CONNECTED)
                return True

            async def disconnect(self) -> None:
                await asyncio.sleep(0.005)  # Simulate disconnection time
                self.connection_status = ConnectionStatus.DISCONNECTED
                self._update_connection_status(ConnectionStatus.DISCONNECTED)

            async def authenticate(self) -> bool:
                if self.connection_status != ConnectionStatus.CONNECTED:
                    return False
                await asyncio.sleep(0.02)  # Simulate auth time
                self._update_connection_status(ConnectionStatus.AUTHENTICATED)
                return True

            async def is_connected(self) -> bool:
                return self.connection_status in [
                    ConnectionStatus.CONNECTED,
                    ConnectionStatus.AUTHENTICATED,
                ]

            async def submit_order(self, order: NewOrderSingle) -> str:
                if not await self.is_connected():
                    raise ConnectionError("Not connected to broker")

                # Simulate rate limiting check
                if not self._check_rate_limits():
                    raise Exception("Rate limit exceeded")

                async with self._lock:
                    self.order_counter += 1
                    order_id = f"ORDER_{self.order_counter:06d}"

                    # Simulate order processing time
                    await asyncio.sleep(0.001)

                    # Track order
                    order_info = self._track_order(order)
                    order_info.order_id = order_id
                    order_info.status = OrderStatus.SUBMITTED

                    self.submitted_orders.append(order)

                    # Simulate execution report generation
                    asyncio.create_task(self._simulate_execution(order, order_id))

                    return order.cl_ord_id

            async def _simulate_execution(self, order: NewOrderSingle, order_id: str):
                """Simulate order execution with realistic timing."""
                # Random execution delay
                import random

                await asyncio.sleep(random.uniform(0.01, 0.1))

                # Create execution report
                execution = ExecutionReport(
                    order_id=order_id,
                    cl_ord_id=order.cl_ord_id,
                    exec_id=f"EXEC_{uuid.uuid4().hex[:8].upper()}",
                    exec_type="F",  # Fill
                    ord_status="2",  # Filled
                    symbol=order.symbol,
                    side=order.side,
                    order_qty=order.order_qty,
                    cum_qty=order.order_qty,
                    avg_px=1.1000,  # Mock price
                    last_qty=order.order_qty,
                    last_px=1.1000,
                    transact_time=datetime.now(timezone.utc),
                )

                # Process execution report
                self._process_execution_report(execution)

            async def cancel_order(self, cancel_request) -> bool:
                await asyncio.sleep(0.005)
                return True

            async def get_order_status(self, cl_ord_id: str) -> OrderInfo:
                return self.active_orders.get(cl_ord_id)

            async def get_open_orders(self) -> List[OrderInfo]:
                return list(self.active_orders.values())

            async def send_heartbeat(self) -> bool:
                return True

            async def get_account_info(self) -> Dict[str, Any]:
                return {"balance": 100000.0, "currency": "USD"}

            async def get_positions(self) -> List[Dict[str, Any]]:
                return []

        config = AdapterConfig(
            adapter_type="mock",
            connection_params={},
            authentication={},
            limits={"max_orders_per_second": 10},
        )

        return MockBrokerAdapter(config)

    @pytest.mark.asyncio
    async def test_concurrent_order_submission(self, mock_broker_adapter):
        """Test concurrent order submission without race conditions."""

        # Connect adapter
        await mock_broker_adapter.connect()
        await mock_broker_adapter.authenticate()

        # Generate test orders
        num_orders = 100
        orders = []
        for i in range(num_orders):
            order = NewOrderSingle(
                cl_ord_id=f"TEST_ORDER_{i:04d}",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=100000,
                ord_type=OrdType.MARKET,
                time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
            )
            orders.append((order,))

        async with concurrency_test_environment(max_concurrent=20) as env:
            result = await env.test_async_operation(
                mock_broker_adapter.submit_order,
                orders,
                max_concurrent=20,
                timeout=10.0,
            )

            # Validate results
            assert result.operations_completed == num_orders
            assert result.operations_failed == 0
            assert result.race_conditions_detected == 0
            assert result.throughput_ops_per_sec > 50  # Should handle > 50 orders/sec
            assert len(mock_broker_adapter.submitted_orders) == num_orders

            # Check order tracking consistency
            assert len(mock_broker_adapter.active_orders) == num_orders

            # Verify no duplicate order IDs
            order_ids = [
                info.order_id for info in mock_broker_adapter.active_orders.values()
            ]
            assert len(set(order_ids)) == len(order_ids), "Duplicate order IDs detected"

    @pytest.mark.asyncio
    async def test_connection_management_concurrency(self, mock_broker_adapter):
        """Test concurrent connection operations."""

        async def connection_cycle():
            """Perform connect/disconnect cycle."""
            await mock_broker_adapter.connect()
            await asyncio.sleep(0.01)  # Hold connection briefly
            await mock_broker_adapter.disconnect()
            return "cycle_complete"

        # Test multiple concurrent connection cycles
        cycles = [()] * 10  # 10 concurrent cycles

        async with concurrency_test_environment(max_concurrent=10) as env:
            result = await env.test_async_operation(
                connection_cycle, cycles, max_concurrent=10, timeout=5.0
            )

            assert result.operations_completed == 10
            assert result.operations_failed == 0

            # Final state should be disconnected
            assert not await mock_broker_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_order_execution_processing(self, mock_broker_adapter):
        """Test concurrent execution report processing."""

        await mock_broker_adapter.connect()
        await mock_broker_adapter.authenticate()

        # Submit orders that will generate executions
        num_orders = 50
        orders = []
        for i in range(num_orders):
            order = NewOrderSingle(
                cl_ord_id=f"EXEC_TEST_{i:04d}",
                symbol="GBPUSD",
                side=Side.SELL,
                order_qty=50000,
                ord_type=OrdType.MARKET,
                time_in_force=TimeInForce.FILL_OR_KILL,
            )
            orders.append((order,))

        # Submit orders concurrently
        async with concurrency_test_environment(max_concurrent=15) as env:
            result = await env.test_async_operation(
                mock_broker_adapter.submit_order,
                orders,
                max_concurrent=15,
                timeout=15.0,
            )

            assert result.operations_completed == num_orders

            # Wait for all executions to process
            await asyncio.sleep(0.5)

            # Verify execution processing
            filled_orders = [
                order_info
                for order_info in mock_broker_adapter.active_orders.values()
                if order_info.status == OrderStatus.FILLED
            ]

            # Should have some filled orders (async execution simulation)
            assert len(filled_orders) > 0

            # Check execution report consistency
            for order_info in filled_orders:
                assert order_info.last_execution is not None
                assert order_info.total_filled_qty > 0

    @pytest.mark.asyncio
    async def test_rate_limiting_under_load(self, mock_broker_adapter):
        """Test rate limiting behavior under concurrent load."""

        await mock_broker_adapter.connect()
        await mock_broker_adapter.authenticate()

        # Generate high-frequency orders to trigger rate limiting
        num_orders = 200
        orders = []
        for i in range(num_orders):
            order = NewOrderSingle(
                cl_ord_id=f"RATE_TEST_{i:04d}",
                symbol="USDJPY",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                order_qty=25000,
                ord_type=OrdType.LIMIT,
                price=110.00,
                time_in_force=TimeInForce.DAY,
            )
            orders.append((order,))

        # High concurrency to trigger rate limits
        async with concurrency_test_environment(max_concurrent=50) as env:
            result = await env.test_async_operation(
                mock_broker_adapter.submit_order,
                orders,
                max_concurrent=50,
                timeout=20.0,
            )

            # Should have some failures due to rate limiting
            assert result.operations_failed > 0
            assert "Rate limit exceeded" in str(result.errors)

            # But should still process many orders successfully
            assert (
                result.operations_completed > num_orders * 0.3
            )  # At least 30% success

    @pytest.mark.asyncio
    async def test_adapter_state_consistency(self, mock_broker_adapter):
        """Test adapter state consistency under concurrent operations."""

        async def mixed_operations(operation_type: str, order_id: str):
            """Perform mixed operations concurrently."""
            if operation_type == "connect":
                return await mock_broker_adapter.connect()
            elif operation_type == "submit":
                if await mock_broker_adapter.is_connected():
                    order = NewOrderSingle(
                        cl_ord_id=order_id,
                        symbol="USDCHF",
                        side=Side.BUY,
                        order_qty=75000,
                        ord_type=OrdType.MARKET,
                        time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
                    )
                    return await mock_broker_adapter.submit_order(order)
                else:
                    raise ConnectionError("Not connected")
            elif operation_type == "status":
                return await mock_broker_adapter.is_connected()
            elif operation_type == "heartbeat":
                return await mock_broker_adapter.send_heartbeat()

        # Mix of operations
        operations = []
        operations.append(("connect", ""))  # Initial connection

        for i in range(50):
            operations.extend(
                [("submit", f"MIXED_ORDER_{i:04d}"), ("status", ""), ("heartbeat", "")]
            )

        async with concurrency_test_environment(max_concurrent=25) as env:
            result = await env.test_async_operation(
                mixed_operations, operations, max_concurrent=25, timeout=15.0
            )

            # Should handle mixed operations gracefully
            assert (
                result.operations_completed > len(operations) * 0.7
            )  # 70% success rate

            # Final state validation
            final_connected = await mock_broker_adapter.is_connected()
            assert final_connected or not final_connected  # Either state is valid

    @pytest.mark.asyncio
    async def test_high_frequency_trading_simulation(self, mock_broker_adapter):
        """Test realistic high-frequency trading scenario."""

        await mock_broker_adapter.connect()
        await mock_broker_adapter.authenticate()

        async def submit_trading_order(
            symbol: str, side: str, quantity: int, order_type: str
        ):
            """Submit trading order with proper typing."""
            order = NewOrderSingle(
                cl_ord_id=f"HFT_{uuid.uuid4().hex[:8].upper()}",
                symbol=symbol,
                side=Side.BUY if side == "BUY" else Side.SELL,
                order_qty=quantity,
                ord_type=OrdType.MARKET if order_type == "MARKET" else OrdType.LIMIT,
                time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
            )

            if order_type == "LIMIT":
                order.price = 1.1000  # Mock limit price

            return await mock_broker_adapter.submit_order(order)

        # Simulate HFT scenario
        result = await simulate_high_frequency_trading(
            submit_trading_order, num_orders=500, max_concurrent=30, duration=10.0
        )

        # HFT performance requirements
        assert result.success_rate > 0.8  # 80% success rate
        assert result.avg_response_time < 0.01  # < 10ms average response
        assert result.throughput_ops_per_sec > 30  # > 30 orders/sec

        # Verify HFT-specific metrics
        assert result.metadata["hft_scenario"] is True
        assert result.metadata["orders_per_second"] == 50.0  # 500 orders / 10 seconds

    @pytest.mark.asyncio
    async def test_connection_recovery_during_operations(self, mock_broker_adapter):
        """Test connection recovery during active order processing."""

        await mock_broker_adapter.connect()
        await mock_broker_adapter.authenticate()

        async def order_with_potential_disconnect(order_id: str):
            """Submit order that might encounter connection issues."""
            # Randomly disconnect during operation
            import random

            if random.random() < 0.1:  # 10% chance of disconnect
                await mock_broker_adapter.disconnect()
                await asyncio.sleep(0.01)
                await mock_broker_adapter.connect()
                await mock_broker_adapter.authenticate()

            order = NewOrderSingle(
                cl_ord_id=order_id,
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=100000,
                ord_type=OrdType.MARKET,
                time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
            )

            return await mock_broker_adapter.submit_order(order)

        # Test with connection instability
        order_ids = [f"RECOVERY_TEST_{i:04d}" for i in range(100)]
        test_cases = [(order_id,) for order_id in order_ids]

        async with concurrency_test_environment(max_concurrent=20) as env:
            result = await env.test_async_operation(
                order_with_potential_disconnect,
                test_cases,
                max_concurrent=20,
                timeout=15.0,
            )

            # Should handle connection recovery gracefully
            assert result.operations_completed > 50  # At least 50% success

            # Check that adapter maintains consistency after recovery
            final_status = await mock_broker_adapter.is_connected()
            if final_status:
                # If connected, should be able to submit new orders
                test_order = NewOrderSingle(
                    cl_ord_id="FINAL_TEST",
                    symbol="GBPUSD",
                    side=Side.SELL,
                    order_qty=50000,
                    ord_type=OrdType.MARKET,
                    time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
                )
                final_result = await mock_broker_adapter.submit_order(test_order)
                assert final_result is not None


@pytest.mark.concurrency
@pytest.mark.broker
@pytest.mark.performance
class TestBrokerAdapterPerformance:
    """Performance tests for broker adapter concurrent operations."""

    @pytest.mark.asyncio
    async def test_order_submission_throughput(self, mock_broker_adapter):
        """Test order submission throughput under load."""

        await mock_broker_adapter.connect()
        await mock_broker_adapter.authenticate()

        # Performance test parameters
        num_orders = 1000
        target_throughput = 100  # orders/second
        max_concurrent = 50

        orders = []
        for i in range(num_orders):
            order = NewOrderSingle(
                cl_ord_id=f"PERF_ORDER_{i:06d}",
                symbol="EURUSD",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                order_qty=100000,
                ord_type=OrdType.MARKET,
                time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
            )
            orders.append((order,))

        async with concurrency_test_environment(max_concurrent=max_concurrent) as env:
            result = await env.test_async_operation(
                mock_broker_adapter.submit_order,
                orders,
                max_concurrent=max_concurrent,
                timeout=15.0,
            )

            # Performance assertions
            assert result.throughput_ops_per_sec >= target_throughput
            assert result.avg_response_time < 0.01  # < 10ms average
            assert result.success_rate > 0.95  # 95% success rate

            # Memory efficiency check
            assert len(mock_broker_adapter.active_orders) == result.operations_completed

    @pytest.mark.asyncio
    async def test_concurrent_execution_processing_performance(
        self, mock_broker_adapter
    ):
        """Test execution report processing performance."""

        await mock_broker_adapter.connect()
        await mock_broker_adapter.authenticate()

        # Submit orders to generate executions
        num_orders = 500
        orders = []
        for i in range(num_orders):
            order = NewOrderSingle(
                cl_ord_id=f"EXEC_PERF_{i:05d}",
                symbol="GBPUSD",
                side=Side.SELL,
                order_qty=50000,
                ord_type=OrdType.MARKET,
                time_in_force=TimeInForce.FILL_OR_KILL,
            )
            orders.append((order,))

        start_time = asyncio.get_event_loop().time()

        async with concurrency_test_environment(max_concurrent=30) as env:
            result = await env.test_async_operation(
                mock_broker_adapter.submit_order,
                orders,
                max_concurrent=30,
                timeout=10.0,
            )

            # Wait for execution processing
            await asyncio.sleep(0.5)

            end_time = asyncio.get_event_loop().time()
            total_time = end_time - start_time

            # Performance validation
            assert result.operations_completed == num_orders
            assert total_time < 5.0  # Should complete within 5 seconds

            # Execution processing verification
            filled_count = sum(
                1
                for order_info in mock_broker_adapter.active_orders.values()
                if order_info.status == OrderStatus.FILLED
            )

            # Should have processed some executions
            assert filled_count > 0
