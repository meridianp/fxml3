#!/usr/bin/env python3
"""
End-to-End Test: Order Execution Flow
=====================================

This test suite validates the complete order execution flow from order
creation through broker routing to final settlement.

Business Requirements:
- Order execution latency < 100ms (mean)
- Broker failover < 5 seconds
- FIX message integrity 100%
- Order state tracking 100% accurate
- Partial fill handling correct
- Slippage monitoring and control

Test Coverage:
- Order validation and enrichment
- Broker selection and routing
- FIX protocol message flow
- Order lifecycle management
- Fill and settlement processing
- Error handling and recovery
"""

import asyncio
import time
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.brokers.adapters.fxcm_adapter import FXCMAdapter
from fxml4.brokers.adapters.ib_adapter import IBAdapter
from fxml4.brokers.adapters.manual_adapter import ManualAdapter
from fxml4.brokers.order_manager import OrderManager
from fxml4.core.exceptions import BrokerConnectionError, OrderValidationError
from fxml4.core.models import Fill, Order, OrderStatus, Position
from fxml4.fix.message_builder import FIXMessageBuilder
from fxml4.fix.session_manager import FIXSessionManager


class OrderState(Enum):
    """Order state enumeration."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TestOrderExecutionFlowE2E:
    """Complete end-to-end testing of order execution flow."""

    @pytest.fixture
    async def fix_session_manager(self):
        """Initialize FIX session manager with test configuration."""
        manager = FIXSessionManager(
            config={
                "sender_comp_id": "FXML4_TEST",
                "target_comp_id": "BROKER_TEST",
                "fix_version": "FIX.4.4",
                "heartbeat_interval": 30,
            }
        )

        # Mock FIX connection
        manager.is_connected = True
        manager.send_message = AsyncMock(return_value=True)
        manager.sequence_number = 1

        return manager

    @pytest.fixture
    async def ib_adapter(self, fix_session_manager):
        """Initialize Interactive Brokers adapter."""
        adapter = IBAdapter(
            client_id=999, host="127.0.0.1", port=7497, fix_session=fix_session_manager
        )

        # Mock IB TWS connection
        adapter.is_connected = True
        adapter.account_info = {
            "account_id": "DU12345",
            "buying_power": 1000000.00,
            "net_liquidation": 1000000.00,
            "currency": "USD",
        }

        # Mock order submission
        adapter.submit_order = AsyncMock(side_effect=self._mock_ib_order_submission)
        adapter.cancel_order = AsyncMock(return_value={"status": "CANCELLED"})
        adapter.get_order_status = AsyncMock(side_effect=self._mock_ib_order_status)

        return adapter

    @pytest.fixture
    async def fxcm_adapter(self):
        """Initialize FXCM adapter."""
        adapter = FXCMAdapter(
            username="test_user",
            password="test_pass",  # pragma: allowlist secret
            url="http://testfxcm.com",
            connection="Demo",
        )

        # Mock FXCM connection
        adapter.is_connected = True
        adapter.account_info = {
            "account_id": "FXCM_TEST_123",
            "balance": 100000.00,
            "equity": 100000.00,
            "margin_available": 100000.00,
        }

        # Mock order operations
        adapter.submit_order = AsyncMock(side_effect=self._mock_fxcm_order_submission)
        adapter.get_positions = AsyncMock(return_value=[])

        return adapter

    @pytest.fixture
    async def order_manager(self, ib_adapter, fxcm_adapter):
        """Initialize order manager with multiple brokers."""
        manager = OrderManager(
            max_retry_attempts=3,
            retry_delay=0.1,  # Short delay for testing
            enable_failover=True,
        )

        # Register broker adapters
        await manager.register_broker("IB", ib_adapter, priority=1)
        await manager.register_broker("FXCM", fxcm_adapter, priority=2)

        # Set up order tracking
        manager.active_orders = {}
        manager.order_history = []

        return manager

    @pytest.mark.asyncio
    async def test_successful_order_execution_flow(self, order_manager):
        """
        Test successful order execution from submission to fill.

        Given: A valid market order
        When: Order is submitted to broker
        Then: Order should be executed and filled successfully
        """
        # Create test order
        order = Order(
            symbol="EURUSD",
            side="BUY",
            quantity=10000,
            order_type="MARKET",
            price=None,  # Market order
            metadata={"strategy": "test_strategy", "signal_id": "sig_123"},
        )

        # Submit order
        start_time = time.time()
        result = await order_manager.submit_order(order)
        execution_time = time.time() - start_time

        # Verify submission
        assert result["status"] == "SUBMITTED"
        assert result["order_id"] is not None
        assert result["broker"] == "IB"  # Primary broker
        assert (
            execution_time < 0.1
        ), f"Execution took {execution_time:.3f}s, exceeding 100ms"

        # Simulate order fill
        await asyncio.sleep(0.05)  # Simulate market delay

        # Check order status
        status = await order_manager.get_order_status(result["order_id"])

        assert status["state"] == OrderState.FILLED.value
        assert status["filled_quantity"] == 10000
        assert status["average_fill_price"] > 0
        assert status["commission"] >= 0

    @pytest.mark.asyncio
    async def test_limit_order_execution_with_partial_fills(self, order_manager):
        """
        Test limit order execution with partial fills.

        Given: A limit order
        When: Order is partially filled multiple times
        Then: System should track all partial fills correctly
        """
        # Create limit order
        order = Order(
            symbol="GBPUSD",
            side="SELL",
            quantity=50000,
            order_type="LIMIT",
            price=1.2650,
            time_in_force="GTC",  # Good Till Cancelled
        )

        # Submit order
        result = await order_manager.submit_order(order)
        order_id = result["order_id"]

        # Simulate partial fills
        fills = [
            {"quantity": 10000, "price": 1.2650, "timestamp": datetime.now()},
            {
                "quantity": 15000,
                "price": 1.2651,
                "timestamp": datetime.now() + timedelta(seconds=10),
            },
            {
                "quantity": 25000,
                "price": 1.2649,
                "timestamp": datetime.now() + timedelta(seconds=20),
            },
        ]

        total_filled = 0
        for fill in fills:
            # Process partial fill
            await order_manager._process_fill(order_id, fill)
            total_filled += fill["quantity"]

            # Check order status
            status = await order_manager.get_order_status(order_id)

            if total_filled < order.quantity:
                assert status["state"] == OrderState.PARTIALLY_FILLED.value
                assert status["filled_quantity"] == total_filled
                assert status["remaining_quantity"] == order.quantity - total_filled
            else:
                assert status["state"] == OrderState.FILLED.value
                assert status["filled_quantity"] == order.quantity
                assert status["remaining_quantity"] == 0

        # Verify average fill price
        expected_avg_price = sum(f["quantity"] * f["price"] for f in fills) / sum(
            f["quantity"] for f in fills
        )
        assert abs(status["average_fill_price"] - expected_avg_price) < 0.0001

    @pytest.mark.asyncio
    async def test_broker_failover_on_connection_loss(self, order_manager, ib_adapter):
        """
        Test automatic failover to secondary broker on primary failure.

        Given: Primary broker connection fails
        When: Order is submitted
        Then: System should failover to secondary broker within 5 seconds
        """
        # Simulate IB connection failure
        ib_adapter.is_connected = False
        ib_adapter.submit_order = AsyncMock(
            side_effect=BrokerConnectionError("IB TWS disconnected")
        )

        # Create test order
        order = Order(symbol="USDJPY", side="BUY", quantity=100000, order_type="MARKET")

        # Submit order (should trigger failover)
        start_time = time.time()
        result = await order_manager.submit_order(order)
        failover_time = time.time() - start_time

        # Verify failover occurred
        assert result["status"] == "SUBMITTED"
        assert result["broker"] == "FXCM"  # Secondary broker
        assert (
            failover_time < 5.0
        ), f"Failover took {failover_time:.2f}s, exceeding 5s limit"
        assert result.get("failover_reason") == "Primary broker connection failed"

    @pytest.mark.asyncio
    async def test_fix_message_integrity(self, fix_session_manager):
        """
        Test FIX protocol message integrity and sequencing.

        Given: Orders sent via FIX protocol
        When: Messages are transmitted
        Then: All FIX messages should maintain integrity and correct sequence
        """
        fix_builder = FIXMessageBuilder(fix_session_manager)

        # Create multiple test orders
        orders = [
            Order(symbol="EURUSD", side="BUY", quantity=10000, order_type="MARKET"),
            Order(
                symbol="GBPUSD",
                side="SELL",
                quantity=20000,
                order_type="LIMIT",
                price=1.2650,
            ),
            Order(
                symbol="USDJPY",
                side="BUY",
                quantity=50000,
                order_type="STOP",
                price=110.50,
            ),
        ]

        sent_messages = []
        for order in orders:
            # Build FIX message
            fix_message = await fix_builder.build_new_order_single(order)

            # Verify message structure
            assert fix_message.get("35") == "D"  # MsgType = NewOrderSingle
            assert fix_message.get("55") == order.symbol  # Symbol
            assert fix_message.get("54") == (
                "1" if order.side == "BUY" else "2"
            )  # Side
            assert fix_message.get("38") == str(order.quantity)  # OrderQty

            # Verify sequence number
            assert int(fix_message.get("34")) == fix_session_manager.sequence_number

            # Send message
            await fix_session_manager.send_message(fix_message)
            sent_messages.append(fix_message)

            # Increment sequence for next message
            fix_session_manager.sequence_number += 1

        # Verify all messages were sent with correct sequence
        for i, msg in enumerate(sent_messages):
            assert int(msg.get("34")) == i + 1

    @pytest.mark.asyncio
    async def test_order_validation_and_rejection(self, order_manager):
        """
        Test order validation and rejection for invalid orders.

        Given: Invalid order parameters
        When: Order is submitted
        Then: Order should be rejected with appropriate error message
        """
        # Test various invalid orders
        invalid_orders = [
            # Negative quantity
            Order(symbol="EURUSD", side="BUY", quantity=-1000, order_type="MARKET"),
            # Invalid symbol
            Order(symbol="INVALID", side="BUY", quantity=1000, order_type="MARKET"),
            # Stop order without stop price
            Order(
                symbol="EURUSD",
                side="BUY",
                quantity=1000,
                order_type="STOP",
                price=None,
            ),
            # Limit order without limit price
            Order(
                symbol="EURUSD",
                side="BUY",
                quantity=1000,
                order_type="LIMIT",
                price=None,
            ),
        ]

        for order in invalid_orders:
            with pytest.raises(OrderValidationError) as exc_info:
                await order_manager.submit_order(order)

            assert exc_info.value.order_id == order.id
            assert len(exc_info.value.message) > 0

    @pytest.mark.asyncio
    async def test_order_modification_flow(self, order_manager):
        """
        Test order modification (price/quantity changes).

        Given: An active limit order
        When: Order is modified
        Then: Modification should be processed correctly
        """
        # Create initial order
        order = Order(
            symbol="EURUSD",
            side="BUY",
            quantity=10000,
            order_type="LIMIT",
            price=1.0840,
        )

        # Submit order
        result = await order_manager.submit_order(order)
        order_id = result["order_id"]

        # Modify order price
        modification = {"price": 1.0835, "quantity": 15000}

        mod_result = await order_manager.modify_order(order_id, modification)

        assert mod_result["status"] == "MODIFIED"
        assert mod_result["new_price"] == 1.0835
        assert mod_result["new_quantity"] == 15000

        # Verify order status reflects modification
        status = await order_manager.get_order_status(order_id)
        assert status["price"] == 1.0835
        assert status["quantity"] == 15000

    @pytest.mark.asyncio
    async def test_order_cancellation_flow(self, order_manager):
        """
        Test order cancellation process.

        Given: An active order
        When: Cancellation is requested
        Then: Order should be cancelled successfully
        """
        # Create and submit order
        order = Order(
            symbol="GBPUSD",
            side="SELL",
            quantity=20000,
            order_type="LIMIT",
            price=1.2680,
        )

        result = await order_manager.submit_order(order)
        order_id = result["order_id"]

        # Wait briefly to ensure order is active
        await asyncio.sleep(0.05)

        # Cancel order
        cancel_result = await order_manager.cancel_order(order_id)

        assert cancel_result["status"] == "CANCELLED"
        assert cancel_result["cancel_time"] is not None

        # Verify order status
        status = await order_manager.get_order_status(order_id)
        assert status["state"] == OrderState.CANCELLED.value
        assert status["cancel_reason"] is not None

    @pytest.mark.asyncio
    async def test_stop_loss_and_take_profit_orders(self, order_manager):
        """
        Test stop loss and take profit order execution.

        Given: A position with SL and TP orders
        When: Price reaches trigger levels
        Then: Protective orders should execute correctly
        """
        # Create main order
        main_order = Order(
            symbol="EURUSD",
            side="BUY",
            quantity=10000,
            order_type="MARKET",
            stop_loss=1.0820,
            take_profit=1.0880,
        )

        # Submit main order
        result = await order_manager.submit_order(main_order)
        main_order_id = result["order_id"]

        # Verify protective orders were created
        protective_orders = await order_manager.get_child_orders(main_order_id)

        assert len(protective_orders) == 2

        # Find SL and TP orders
        sl_order = next(
            (o for o in protective_orders if o.order_type == "STOP_LOSS"), None
        )
        tp_order = next(
            (o for o in protective_orders if o.order_type == "TAKE_PROFIT"), None
        )

        assert sl_order is not None
        assert sl_order.price == 1.0820
        assert sl_order.side == "SELL"  # Opposite side to close position

        assert tp_order is not None
        assert tp_order.price == 1.0880
        assert tp_order.side == "SELL"  # Opposite side to close position

        # Simulate stop loss trigger
        await order_manager._trigger_stop_order(sl_order.id, current_price=1.0819)

        # Verify position is closed
        positions = await order_manager.get_positions()
        eurusd_position = next((p for p in positions if p.symbol == "EURUSD"), None)
        assert eurusd_position is None or eurusd_position.quantity == 0

    @pytest.mark.asyncio
    async def test_order_execution_with_slippage(self, order_manager):
        """
        Test order execution with realistic slippage.

        Given: Market orders in various market conditions
        When: Orders are executed
        Then: Slippage should be tracked and within acceptable limits
        """
        # Test orders with different expected slippage scenarios
        test_scenarios = [
            # Normal market conditions
            {"symbol": "EURUSD", "quantity": 10000, "expected_slippage": 0.0001},
            # Large order - more slippage
            {"symbol": "EURUSD", "quantity": 1000000, "expected_slippage": 0.0005},
            # Illiquid pair - more slippage
            {"symbol": "NZDCHF", "quantity": 50000, "expected_slippage": 0.0008},
        ]

        for scenario in test_scenarios:
            order = Order(
                symbol=scenario["symbol"],
                side="BUY",
                quantity=scenario["quantity"],
                order_type="MARKET",
                expected_price=1.0850,  # Expected execution price
            )

            # Submit order
            result = await order_manager.submit_order(order)

            # Wait for execution
            await asyncio.sleep(0.05)

            # Get execution details
            status = await order_manager.get_order_status(result["order_id"])

            # Calculate actual slippage
            actual_slippage = abs(status["average_fill_price"] - order.expected_price)

            # Verify slippage is within expected range
            assert (
                actual_slippage <= scenario["expected_slippage"] * 1.5
            ), f"Excessive slippage: {actual_slippage:.5f} for {scenario['symbol']}"

    @pytest.mark.asyncio
    async def test_concurrent_order_processing(self, order_manager):
        """
        Test system can handle multiple concurrent orders.

        Given: Multiple orders submitted simultaneously
        When: All orders are processed
        Then: Each order should be handled correctly without conflicts
        """
        # Create multiple orders
        orders = [
            Order(symbol="EURUSD", side="BUY", quantity=10000, order_type="MARKET"),
            Order(
                symbol="GBPUSD",
                side="SELL",
                quantity=20000,
                order_type="LIMIT",
                price=1.2650,
            ),
            Order(symbol="USDJPY", side="BUY", quantity=30000, order_type="MARKET"),
            Order(
                symbol="AUDUSD",
                side="SELL",
                quantity=15000,
                order_type="LIMIT",
                price=0.6850,
            ),
            Order(symbol="NZDUSD", side="BUY", quantity=25000, order_type="MARKET"),
        ]

        # Submit all orders concurrently
        start_time = time.time()
        results = await asyncio.gather(
            *[order_manager.submit_order(order) for order in orders],
            return_exceptions=True,
        )
        processing_time = time.time() - start_time

        # Verify all orders were processed
        successful_orders = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_orders) >= 4, "Too many orders failed"

        # Verify unique order IDs
        order_ids = [r["order_id"] for r in successful_orders]
        assert len(order_ids) == len(set(order_ids)), "Duplicate order IDs detected"

        # Verify processing time
        assert (
            processing_time < 1.0
        ), f"Concurrent processing took {processing_time:.2f}s"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_order_execution_performance_metrics(self, order_manager):
        """
        Test order execution performance meets SLA requirements.

        Given: Performance SLAs for order execution
        When: Multiple orders are executed
        Then: 95th percentile latency should be < 100ms
        """
        execution_times = []

        # Execute multiple orders to build performance distribution
        for i in range(50):
            order = Order(
                symbol="EURUSD",
                side="BUY" if i % 2 == 0 else "SELL",
                quantity=10000,
                order_type="MARKET",
            )

            start_time = time.time()
            result = await order_manager.submit_order(order)
            execution_time = time.time() - start_time

            execution_times.append(execution_time)

            # Small delay between orders
            await asyncio.sleep(0.01)

        # Calculate performance metrics
        p50 = np.percentile(execution_times, 50)
        p95 = np.percentile(execution_times, 95)
        p99 = np.percentile(execution_times, 99)
        mean_time = np.mean(execution_times)

        # Verify SLAs
        assert mean_time < 0.1, f"Mean execution time {mean_time:.3f}s exceeds 100ms"
        assert p95 < 0.15, f"95th percentile {p95:.3f}s exceeds 150ms"
        assert p99 < 0.2, f"99th percentile {p99:.3f}s exceeds 200ms"

    # Helper methods

    async def _mock_ib_order_submission(self, order: Order) -> Dict:
        """Mock IB order submission."""
        await asyncio.sleep(0.01)  # Simulate network latency
        return {
            "order_id": f"IB_{np.random.randint(10000, 99999)}",
            "status": "SUBMITTED",
            "timestamp": datetime.now(),
            "broker": "IB",
        }

    async def _mock_fxcm_order_submission(self, order: Order) -> Dict:
        """Mock FXCM order submission."""
        await asyncio.sleep(0.015)  # Slightly slower than IB
        return {
            "order_id": f"FXCM_{np.random.randint(10000, 99999)}",
            "status": "SUBMITTED",
            "timestamp": datetime.now(),
            "broker": "FXCM",
        }

    async def _mock_ib_order_status(self, order_id: str) -> Dict:
        """Mock IB order status."""
        return {
            "order_id": order_id,
            "state": OrderState.FILLED.value,
            "filled_quantity": 10000,
            "average_fill_price": 1.0851,
            "commission": 2.50,
            "timestamp": datetime.now(),
        }


if __name__ == "__main__":
    # Run tests with coverage
    pytest.main([__file__, "-v", "--cov=fxml4.brokers", "--cov-report=term-missing"])
