#!/usr/bin/env python3
"""Test script for IB adapter functionality.

This script tests the IB adapter with mock IB connection and real RabbitMQ.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pika

from fxml4.brokers.adapters.base import AdapterConfig
from fxml4.brokers.adapters.ib_rabbitmq_adapter import IBRabbitMQAdapter
from fxml4.brokers.messaging.topology import BrokerMessageTopology
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import NewOrderSingle
from fxml4.fix.utils.builder import FIXMessageBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_rabbitmq_topology():
    """Set up RabbitMQ topology for testing."""
    try:
        params = pika.ConnectionParameters(
            host='rabbitmq',
            port=5672,
            credentials=pika.PlainCredentials('guest', 'guest')
        )
        connection = pika.BlockingConnection(params)

        topology = BrokerMessageTopology(connection)
        topology.setup_exchanges()
        topology.setup_ib_queues()

        logger.info("RabbitMQ topology setup complete")
        connection.close()
        return True

    except Exception as e:
        logger.error(f"Failed to setup RabbitMQ topology: {e}")
        return False


async def test_ib_adapter():
    """Test IB adapter functionality."""
    # Setup RabbitMQ first
    if not setup_rabbitmq_topology():
        logger.error("Failed to setup RabbitMQ topology")
        return

    # Create adapter configuration
    config = AdapterConfig(
        adapter_type="ib",
        connection_params={
            "host": "localhost",
            "port": 7497,  # Paper trading port
            "client_id": 1,
            "rabbitmq": {
                "host": "rabbitmq",
                "port": 5672,
                "username": "guest",
                "password": "guest"
            }
        },
        features={
            "market_data": True,
            "order_modification": True,
            "historical_data": True
        },
        limits={
            "max_orders_per_second": 10,
            "max_daily_volume": 10000000
        }
    )

    # Create adapter
    adapter = IBRabbitMQAdapter(config)

    try:
        # Connect to IB and RabbitMQ
        logger.info("Connecting to IB Gateway and RabbitMQ...")
        connected = await adapter.connect()

        if not connected:
            logger.error("Failed to connect to IB Gateway")
            logger.info("Make sure IB Gateway/TWS is running on localhost:7497")
            return

        logger.info("Successfully connected!")
        logger.info(f"Connection status: {adapter.connection.status.value}")
        logger.info(f"Account ID: {adapter.account_id}")
        logger.info(f"Next order ID: {adapter.next_order_id}")

        # Test order submission (if connected to real IB)
        if adapter.connection.is_ready():
            logger.info("\nTesting order submission...")

            # Create a test order
            order = NewOrderSingle(
                cl_ord_id="TEST_IB_001",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=25000,  # Small size for testing
                ord_type=OrdType.LIMIT,
                price=1.0500,  # Far from market to avoid fill
                time_in_force=TimeInForce.DAY
            )

            logger.info(f"Submitting test order: {order.cl_ord_id}")
            order_id = await adapter.submit_order(order)
            logger.info(f"Order submitted with IB ID: {order_id}")

            # Wait for order status
            await asyncio.sleep(2)

            # Check order status
            if order.cl_ord_id in adapter.active_orders:
                order_info = adapter.active_orders[order.cl_ord_id]
                logger.info(f"Order status: {order_info.get('status', 'Unknown')}")

                # Cancel the order
                logger.info("Cancelling test order...")
                from fxml4.fix.messages.orders import OrderCancelRequest
                cancel_req = OrderCancelRequest(
                    orig_cl_ord_id="TEST_IB_001",
                    cl_ord_id="CANCEL_001"
                )

                cancelled = await adapter.cancel_order(cancel_req)
                logger.info(f"Cancel result: {cancelled}")

                # Wait for cancellation
                await asyncio.sleep(2)

        # Test market data subscription
        logger.info("\nTesting market data subscription...")
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        success = await adapter.subscribe_market_data(symbols)
        logger.info(f"Market data subscription result: {success}")

        if success:
            logger.info("Waiting for market data updates...")
            await asyncio.sleep(5)

        # Send status update
        logger.info("\nSending status update...")
        await adapter._send_status_update()

    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)

    finally:
        # Disconnect
        logger.info("\nDisconnecting...")
        await adapter.disconnect()
        logger.info("Test complete!")


def test_fix_translation():
    """Test FIX message translation."""
    logger.info("\nTesting FIX message translation...")

    from fxml4.brokers.adapters.ib_fix_translator import IBFIXTranslator

    # Test order translation
    order = NewOrderSingle(
        cl_ord_id="TRANS_TEST_001",
        symbol="EURUSD",
        side=Side.BUY,
        order_qty=100000,
        ord_type=OrdType.LIMIT,
        price=1.1000,
        time_in_force=TimeInForce.GOOD_TILL_CANCEL
    )

    # Convert to IB contract
    ib_contract = IBFIXTranslator.fix_to_ib_contract(order)
    logger.info(f"IB Contract: {ib_contract.symbol} {ib_contract.secType} {ib_contract.currency}")

    # Convert to IB order
    ib_order = IBFIXTranslator.fix_to_ib_order(order, account="DU123456")
    logger.info(f"IB Order: {ib_order.action} {ib_order.totalQuantity} @ {ib_order.lmtPrice}")

    # Test status mapping
    ib_statuses = ["PendingSubmit", "Submitted", "Filled", "Cancelled", "Rejected"]
    for status in ib_statuses:
        fix_status = IBFIXTranslator.ib_status_to_fix(status)
        logger.info(f"IB Status '{status}' -> FIX Status '{fix_status.name}'")

    logger.info("FIX translation test complete!")


async def main():
    """Main test function."""
    logger.info("Starting IB adapter tests...\n")

    # Test FIX translation
    test_fix_translation()

    # Test adapter
    await test_ib_adapter()


if __name__ == "__main__":
    asyncio.run(main())
