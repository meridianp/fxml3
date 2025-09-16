#!/usr/bin/env python3
"""Test script for manual broker adapter.

This script demonstrates the manual adapter functionality including:
- Order submission for manual approval
- Approval/rejection workflow
- WebSocket notifications
- RabbitMQ integration
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.brokers.adapters.base import AdapterConfig
from fxml4.brokers.adapters.manual_adapter import ManualBrokerAdapter
from fxml4.brokers.adapters.manual_rabbitmq_adapter import ManualRabbitMQAdapter
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import NewOrderSingle, OrderCancelRequest
from fxml4.fix.utils.builder import FIXMessageBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_basic_manual_adapter():
    """Test basic manual adapter functionality."""
    logger.info("Testing basic manual adapter...")

    # Create adapter configuration
    config = AdapterConfig(
        broker_type="manual",
        adapter_type="manual",
        connection_params={},
        features={
            "auto_reject_timeout": 60,  # 1 minute for testing
            "simulate_execution": True,
            "simulated_fill_delay": 2,
            "approval_levels": {"standard": 0, "senior": 100000, "executive": 1000000},
        },
        limits={"max_override_amount": 5000000},
    )

    # Create adapter
    adapter = ManualBrokerAdapter(config)

    # Connect adapter
    connected = await adapter.connect()
    assert connected, "Failed to connect manual adapter"
    logger.info("✓ Manual adapter connected")

    # Create test order
    builder = FIXMessageBuilder()
    order = NewOrderSingle(
        cl_ord_id=f"TEST_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        symbol="EUR/USD",
        side=Side.BUY,
        order_qty=100000,
        ord_type=OrdType.LIMIT,
        price=1.0850,
        time_in_force=TimeInForce.DAY,
        transact_time=datetime.utcnow(),
    )

    # Submit order
    order_id = await adapter.submit_order(order)
    logger.info(f"✓ Order submitted: {order.cl_ord_id} -> {order_id}")

    # Get pending orders
    pending = await adapter.get_pending_orders()
    assert len(pending) == 1, "Expected 1 pending order"
    logger.info(f"✓ Pending orders: {len(pending)}")

    # Simulate approval after 3 seconds
    await asyncio.sleep(3)

    # Approve order
    approved = await adapter.approve_order(
        cl_ord_id=order.cl_ord_id, reviewer="test_user", notes="Test approval"
    )
    assert approved, "Failed to approve order"
    logger.info("✓ Order approved")

    # Wait for simulated execution
    await asyncio.sleep(3)

    # Check order history
    history = await adapter.get_order_history(limit=10)
    assert len(history) >= 1, "Expected order in history"
    logger.info(f"✓ Order history: {len(history)} orders")

    # Test order cancellation
    order2 = NewOrderSingle(
        cl_ord_id=f"CANCEL_TEST_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        symbol="GBP/USD",
        side=Side.SELL,
        order_qty=50000,
        ord_type=OrdType.MARKET,
        time_in_force=TimeInForce.IOC,
        transact_time=datetime.utcnow(),
    )

    order_id2 = await adapter.submit_order(order2)
    logger.info(f"✓ Second order submitted: {order2.cl_ord_id}")

    # Cancel order
    cancel_request = OrderCancelRequest(
        orig_cl_ord_id=order2.cl_ord_id,
        cl_ord_id=f"CANCEL_{order2.cl_ord_id}",
        symbol=order2.symbol,
        side=order2.side,
        transact_time=datetime.utcnow(),
    )

    cancelled = await adapter.cancel_order(cancel_request)
    assert cancelled, "Failed to cancel order"
    logger.info("✓ Order cancelled")

    # Test rejection
    order3 = NewOrderSingle(
        cl_ord_id=f"REJECT_TEST_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        symbol="USD/JPY",
        side=Side.BUY,
        order_qty=1000000,
        ord_type=OrdType.STOP,
        stop_px=110.50,
        time_in_force=TimeInForce.GTC,
        transact_time=datetime.utcnow(),
    )

    order_id3 = await adapter.submit_order(order3)
    logger.info(f"✓ Third order submitted: {order3.cl_ord_id}")

    # Reject order
    rejected = await adapter.reject_order(
        cl_ord_id=order3.cl_ord_id,
        reviewer="risk_manager",
        reason="Exceeds risk limits",
        notes="Position size too large",
    )
    assert rejected, "Failed to reject order"
    logger.info("✓ Order rejected")

    # Disconnect
    await adapter.disconnect()
    logger.info("✓ Manual adapter disconnected")

    logger.info("\n✅ Basic manual adapter test completed successfully!")


async def test_rabbitmq_manual_adapter():
    """Test manual adapter with RabbitMQ integration."""
    logger.info("\nTesting manual adapter with RabbitMQ...")

    # Create adapter configuration
    config = AdapterConfig(
        broker_type="manual",
        adapter_type="manual_rabbitmq",
        connection_params={
            "rabbitmq": {
                "host": "localhost",
                "port": 5672,
                "username": "guest",
                "password": "guest",
            }
        },
        features={
            "auto_reject_timeout": 30,  # 30 seconds for testing
            "simulate_execution": True,
            "simulated_fill_delay": 1,
        },
        limits={},
    )

    # Create RabbitMQ adapter
    adapter = ManualRabbitMQAdapter(config)

    try:
        # Connect adapter
        connected = await adapter.connect()
        if not connected:
            logger.warning("Failed to connect to RabbitMQ - is RabbitMQ running?")
            return

        logger.info("✓ Manual RabbitMQ adapter connected")

        # The adapter will now consume from RabbitMQ queues
        # In a real scenario, orders would come through the message queue

        logger.info("Adapter is listening for orders on RabbitMQ queues:")
        logger.info(f"  - Order queue: {adapter.order_queue}")
        logger.info(f"  - Admin queue: {adapter.admin_queue}")
        logger.info(f"  - Approval queue: {adapter.approval_queue}")

        # Keep adapter running for 10 seconds to receive messages
        logger.info("\nWaiting for messages (10 seconds)...")
        await asyncio.sleep(10)

        # Disconnect
        await adapter.disconnect()
        logger.info("✓ Manual RabbitMQ adapter disconnected")

        logger.info("\n✅ RabbitMQ manual adapter test completed!")

    except Exception as e:
        logger.error(f"RabbitMQ test failed: {e}")
        logger.info("Make sure RabbitMQ is running: docker-compose up -d rabbitmq")


async def test_approval_timeout():
    """Test automatic rejection on timeout."""
    logger.info("\nTesting automatic rejection timeout...")

    # Create adapter with short timeout
    config = AdapterConfig(
        broker_type="manual",
        adapter_type="manual",
        connection_params={},
        features={"auto_reject_timeout": 5, "simulate_execution": False},  # 5 seconds
        limits={},
    )

    adapter = ManualBrokerAdapter(config)
    await adapter.connect()

    # Submit order
    order = NewOrderSingle(
        cl_ord_id=f"TIMEOUT_TEST_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        symbol="AUD/USD",
        side=Side.SELL,
        order_qty=75000,
        ord_type=OrdType.LIMIT,
        price=0.7250,
        time_in_force=TimeInForce.DAY,
        transact_time=datetime.utcnow(),
    )

    order_id = await adapter.submit_order(order)
    logger.info(f"✓ Order submitted: {order.cl_ord_id}")

    # Wait for timeout
    logger.info("Waiting for auto-rejection timeout (5 seconds)...")
    await asyncio.sleep(6)

    # Check that order was auto-rejected
    pending = await adapter.get_pending_orders()
    assert len(pending) == 0, "Order should have been auto-rejected"

    history = await adapter.get_order_history(limit=10)
    rejected_order = None
    for h in history:
        if h["cl_ord_id"] == order.cl_ord_id:
            rejected_order = h
            break

    assert rejected_order is not None, "Order not found in history"
    assert rejected_order["approval_status"] == "REJECTED", "Order should be rejected"
    assert rejected_order["reviewer"] == "SYSTEM", "Order should be rejected by SYSTEM"

    logger.info("✓ Order auto-rejected after timeout")

    await adapter.disconnect()
    logger.info("\n✅ Timeout test completed successfully!")


async def main():
    """Run all tests."""
    try:
        # Test basic functionality
        await test_basic_manual_adapter()

        # Test timeout functionality
        await test_approval_timeout()

        # Test RabbitMQ integration (optional)
        await test_rabbitmq_manual_adapter()

        logger.info("\n🎉 All manual adapter tests completed successfully!")

    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
