#!/usr/bin/env python3
"""Test script for FXCM adapter functionality.

This script tests the FXCM adapter with the Docker bridge service.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import aiohttp

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pika

from fxml4.brokers.adapters.base import AdapterConfig
from fxml4.brokers.adapters.fxcm_rabbitmq_adapter import FXCMRabbitMQAdapter
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

        # Setup FXCM queues
        channel = connection.channel()

        # Order queue
        channel.queue_declare(
            queue='orders.fxcm.inbound',
            durable=True,
            arguments={'x-message-ttl': 3600000}
        )
        channel.queue_bind(
            exchange='order.routing',
            queue='orders.fxcm.inbound',
            routing_key='order.fxcm.*'
        )

        # Admin queue
        channel.queue_declare(
            queue='admin.fxcm.commands',
            durable=True
        )
        channel.queue_bind(
            exchange='admin.control',
            queue='admin.fxcm.commands',
            routing_key='admin.fxcm.*'
        )

        logger.info("RabbitMQ topology setup complete")
        connection.close()
        return True

    except Exception as e:
        logger.error(f"Failed to setup RabbitMQ topology: {e}")
        return False


async def test_bridge_connection():
    """Test direct connection to FXCM bridge service."""
    logger.info("\nTesting FXCM bridge service connection...")

    bridge_url = "http://localhost:9090"  # Adjust if needed

    try:
        async with aiohttp.ClientSession() as session:
            # Test health endpoint
            async with session.get(f"{bridge_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    logger.info(f"Bridge health: {health_data}")
                else:
                    logger.error(f"Bridge health check failed: {response.status}")
                    return False

            # Test status endpoint (may require API key)
            try:
                headers = {}
                # Add API key if configured
                # headers['X-API-Key'] = 'your-api-key'

                async with session.get(f"{bridge_url}/status", headers=headers) as response:
                    if response.status == 200:
                        status_data = await response.json()
                        logger.info(f"Bridge status: {json.dumps(status_data, indent=2)}")
                    else:
                        logger.warning(f"Bridge status check failed: {response.status}")
            except Exception as e:
                logger.warning(f"Could not get bridge status (may need API key): {e}")

        return True

    except Exception as e:
        logger.error(f"Failed to connect to bridge service: {e}")
        logger.info("Make sure the FXCM bridge Docker container is running:")
        logger.info("  cd docker && docker-compose -f docker-compose.fxcm.yml up -d")
        return False


async def test_fxcm_adapter():
    """Test FXCM adapter functionality."""
    # Test bridge first
    if not await test_bridge_connection():
        logger.error("Bridge service not available - cannot proceed with adapter test")
        return

    # Setup RabbitMQ
    if not setup_rabbitmq_topology():
        logger.error("Failed to setup RabbitMQ topology")
        return

    # Create adapter configuration
    config = AdapterConfig(
        adapter_type="fxcm",
        connection_params={
            "bridge_url": "http://localhost:9090",  # Adjust if using Docker network
            # "api_key": "your-api-key",  # Add if configured
            "rabbitmq": {
                "host": "rabbitmq",
                "port": 5672,
                "username": "guest",
                "password": "guest"
            }
        },
        features={
            "market_data": True,
            "fx_instruments": True
        },
        limits={
            "max_orders_per_second": 20,
            "max_daily_volume": 100000000
        }
    )

    # Create adapter
    adapter = FXCMRabbitMQAdapter(config)

    try:
        # Connect to bridge and RabbitMQ
        logger.info("\nConnecting to FXCM bridge and RabbitMQ...")
        connected = await adapter.connect()

        if not connected:
            logger.error("Failed to connect FXCM adapter")
            return

        logger.info("Successfully connected!")
        logger.info(f"Connection status: {adapter.connection.status.value}")
        logger.info(f"Bridge connected to FXCM: {adapter.bridge_connected}")
        logger.info(f"Account ID: {adapter.account_id}")

        # Test order submission (if bridge is connected to FXCM)
        if adapter.bridge_connected:
            logger.info("\nTesting order submission...")

            # Create a test order
            order = NewOrderSingle(
                cl_ord_id="TEST_FXCM_001",
                symbol="EURUSD",  # Will be converted to EUR/USD
                side=Side.BUY,
                order_qty=10000,  # 10 micro lots
                ord_type=OrdType.LIMIT,
                price=1.0500,  # Far from market to avoid fill
                time_in_force=TimeInForce.DAY
            )

            logger.info(f"Submitting test order: {order.cl_ord_id}")

            try:
                order_id = await adapter.submit_order(order)
                logger.info(f"Order submitted with bridge ID: {order_id}")

                # Wait for status
                await asyncio.sleep(2)

                # Check order status
                status = await adapter.get_order_status(order.cl_ord_id)
                if status:
                    logger.info(f"Order status: {status.ord_status.name}")

                # Cancel the order
                logger.info("Cancelling test order...")
                from fxml4.fix.messages.orders import OrderCancelRequest
                cancel_req = OrderCancelRequest(
                    orig_cl_ord_id="TEST_FXCM_001",
                    cl_ord_id="CANCEL_001"
                )

                cancelled = await adapter.cancel_order(cancel_req)
                logger.info(f"Cancel result: {cancelled}")

            except Exception as e:
                logger.error(f"Error during order test: {e}")
        else:
            logger.warning("Bridge not connected to FXCM - skipping order test")

        # Test market data subscription
        logger.info("\nTesting market data subscription...")
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        success = await adapter.subscribe_market_data(symbols)
        logger.info(f"Market data subscription result: {success}")

        # Send status update
        logger.info("\nSending status update...")
        await adapter._send_status_update()

        # Wait a bit to see any incoming messages
        logger.info("\nWaiting for messages...")
        await asyncio.sleep(5)

    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)

    finally:
        # Disconnect
        logger.info("\nDisconnecting...")
        await adapter.disconnect()
        logger.info("Test complete!")


def test_fix_translation():
    """Test FIX message translation for FXCM."""
    logger.info("\nTesting FIX-ForexConnect translation...")

    from docker.fxcm.fix_translator import FXCMFIXTranslator

    # Test symbol normalization
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    for symbol in symbols:
        fc_symbol = FXCMFIXTranslator._normalize_symbol(symbol)
        logger.info(f"FIX '{symbol}' -> ForexConnect '{fc_symbol}'")

    # Test order translation
    fix_message = "8=FIX.4.4|35=D|49=TEST|56=FXCM|11=TEST001|55=EURUSD|54=1|38=100000|40=2|44=1.1000|59=1|"

    fix_fields = FXCMFIXTranslator.parse_fix_order(fix_message)
    fc_order = FXCMFIXTranslator.fix_to_forexconnect_order(fix_fields)

    logger.info(f"\nFIX Order Fields: {fix_fields}")
    logger.info(f"ForexConnect Order: {json.dumps(fc_order, indent=2)}")

    # Test execution report creation
    fc_trade = {
        "order_id": "FC123456",
        "trade_id": "FC123456",
        "status": "Executing",
        "instrument": "EUR/USD",
        "side": "B",
        "amount": 100,  # lots
        "rate": 1.0995,
        "filled_amount": 0,
        "avg_rate": 0
    }

    exec_report = FXCMFIXTranslator.forexconnect_to_fix_execution_report(
        fc_order,
        fc_trade,
        "TEST001"
    )

    logger.info(f"\nFIX Execution Report:\n{exec_report}")

    logger.info("\nFIX translation test complete!")


async def main():
    """Main test function."""
    logger.info("Starting FXCM adapter tests...\n")

    # Note: Comment out translation test if running outside Docker
    # (fix_translator module is in Docker container)
    # test_fix_translation()

    # Test adapter
    await test_fxcm_adapter()


if __name__ == "__main__":
    asyncio.run(main())
