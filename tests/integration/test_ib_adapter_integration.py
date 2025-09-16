"""Integration tests for IB adapter with RabbitMQ.

These tests verify the IB adapter works correctly with real RabbitMQ
connections (but mock IB connections).
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pika
import pytest

from fxml4.brokers.adapters.base import AdapterConfig, ConnectionStatus
from fxml4.brokers.adapters.ib_rabbitmq_adapter import IBRabbitMQAdapter
from fxml4.brokers.messaging.topology import BrokerMessageTopology
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle
from fxml4.fix.utils.builder import FIXMessageBuilder


@pytest.mark.integration
@pytest.mark.requires_rabbitmq
class TestIBAdapterIntegration:
    """Integration tests for IB adapter with RabbitMQ."""

    @pytest.fixture
    def rabbitmq_connection(self):
        """Create RabbitMQ connection for testing."""
        try:
            params = pika.ConnectionParameters(
                host="rabbitmq",
                port=5672,
                credentials=pika.PlainCredentials("guest", "guest"),
                connection_attempts=3,
                retry_delay=1,
            )
            connection = pika.BlockingConnection(params)
            yield connection
            connection.close()
        except Exception as e:
            pytest.skip(f"RabbitMQ not available: {e}")

    @pytest.fixture
    def setup_topology(self, rabbitmq_connection):
        """Set up RabbitMQ topology for testing."""
        topology = BrokerMessageTopology(rabbitmq_connection)
        topology.setup_exchanges()
        topology.setup_ib_queues()
        yield topology
        # Cleanup
        channel = rabbitmq_connection.channel()
        try:
            channel.queue_delete("orders.ib.inbound")
            channel.queue_delete("admin.ib.commands")
            channel.queue_delete("orders.dlq")
        except:
            pass

    @pytest.fixture
    def adapter_config(self):
        """Create test adapter configuration."""
        return AdapterConfig(
            adapter_type="ib",
            connection_params={
                "host": "localhost",
                "port": 7497,
                "client_id": 1,
                "account_id": "DU123456",
                "rabbitmq": {
                    "host": "rabbitmq",
                    "port": 5672,
                    "username": "guest",
                    "password": "guest",
                },
            },
            features={"market_data": True},
            limits={"max_orders_per_second": 10},
        )

    @pytest.fixture
    def mock_ib_client(self):
        """Mock IB client to avoid real IB connections."""
        with patch("fxml4.brokers.adapters.ib_adapter.EClient") as mock_client:
            instance = Mock()
            instance.connect = Mock()
            instance.disconnect = Mock()
            instance.isConnected = Mock(return_value=True)
            instance.placeOrder = Mock()
            instance.cancelOrder = Mock()
            instance.reqMktData = Mock()
            mock_client.return_value = instance
            yield instance

    @pytest.fixture
    async def adapter(self, adapter_config, mock_ib_client, setup_topology):
        """Create and connect IB adapter."""
        adapter = IBRabbitMQAdapter(adapter_config)

        # Mock IB connection methods
        async def mock_ib_connect():
            adapter.connection.status = ConnectionStatus.READY
            adapter.next_order_id = 1000
            return True

        with patch.object(adapter, "_connect_ib", new=mock_ib_connect):
            # Trigger nextValidId callback after connection
            async def trigger_next_valid():
                await asyncio.sleep(0.1)
                adapter.nextValidId(1000)

            connect_task = asyncio.create_task(adapter.connect())
            valid_id_task = asyncio.create_task(trigger_next_valid())

            connected = await connect_task
            await valid_id_task

            assert connected == True

            yield adapter

            await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_order_flow_end_to_end(self, adapter, rabbitmq_connection):
        """Test complete order flow from RabbitMQ to IB and back."""
        # Create order
        order = NewOrderSingle(
            cl_ord_id="INT_TEST_001",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.LIMIT,
            price=1.1000,
            time_in_force=TimeInForce.DAY,
        )

        # Build FIX message
        builder = FIXMessageBuilder()
        fix_message = builder.build(order)

        # Publish order to RabbitMQ
        channel = rabbitmq_connection.channel()
        envelope = {
            "fix_message": fix_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "test_client",
            "correlation_id": "INT_TEST_001",
        }

        channel.basic_publish(
            exchange="order.routing",
            routing_key="order.ib.new",
            body=json.dumps(envelope),
            properties=pika.BasicProperties(
                content_type="application/json", delivery_mode=2
            ),
        )

        # Wait for order to be processed
        await asyncio.sleep(0.5)

        # Verify order was submitted to IB
        assert "INT_TEST_001" in adapter.active_orders
        order_info = adapter.active_orders["INT_TEST_001"]
        assert order_info["ib_order_id"] == 1000

        # Simulate IB order status callback
        adapter.orderStatus(
            orderId=1000,
            status="Submitted",
            filled=0,
            remaining=100000,
            avgFillPrice=0,
            permId=0,
            parentId=0,
            lastFillPrice=0,
            clientId=1,
            whyHeld="",
            mktCapPrice=0,
        )

        # Wait for execution report to be published
        await asyncio.sleep(0.2)

        # Consume execution report from queue
        exec_queue = "executions.monitoring"
        channel.queue_declare(queue=exec_queue, durable=True)
        channel.queue_bind(
            exchange="order.executions", queue=exec_queue, routing_key="execution.ib.*"
        )

        method, properties, body = channel.basic_get(queue=exec_queue)
        assert method is not None

        # Verify execution report
        exec_envelope = json.loads(body)
        assert exec_envelope["broker_type"] == "ib"
        assert "fix_message" in exec_envelope

        # Cleanup
        channel.basic_ack(delivery_tag=method.delivery_tag)
        channel.queue_delete(exec_queue)

    @pytest.mark.asyncio
    async def test_admin_command_flow(self, adapter, rabbitmq_connection):
        """Test admin command flow through RabbitMQ."""
        # Send status command
        channel = rabbitmq_connection.channel()
        command = {
            "command": "status",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        channel.basic_publish(
            exchange="admin.control",
            routing_key="admin.ib.command",
            body=json.dumps(command),
            properties=pika.BasicProperties(
                content_type="application/json", delivery_mode=2
            ),
        )

        # Wait for processing
        await asyncio.sleep(0.5)

        # Check for status update in admin status queue
        status_queue = "admin.status.monitor"
        channel.queue_declare(queue=status_queue, durable=True)
        channel.queue_bind(
            exchange="admin.status", queue=status_queue, routing_key="status.ib.*"
        )

        method, properties, body = channel.basic_get(queue=status_queue)
        assert method is not None

        # Verify status update
        status_msg = json.loads(body)
        assert status_msg["type"] == "status_update"
        assert status_msg["adapter"] == "ib"
        assert status_msg["data"]["adapter_type"] == "ib"
        assert status_msg["data"]["connected"] == True

        # Cleanup
        channel.basic_ack(delivery_tag=method.delivery_tag)
        channel.queue_delete(status_queue)

    @pytest.mark.asyncio
    async def test_order_rejection_flow(self, adapter, rabbitmq_connection):
        """Test order rejection flow."""
        # Create invalid order
        order = NewOrderSingle(
            cl_ord_id="INT_TEST_002",
            symbol="INVALID",
            side=Side.BUY,
            order_qty=0,  # Invalid quantity
            ord_type=OrdType.MARKET,
        )

        # Build and publish order
        builder = FIXMessageBuilder()
        fix_message = builder.build(order)

        channel = rabbitmq_connection.channel()
        envelope = {
            "fix_message": fix_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "test_client",
        }

        channel.basic_publish(
            exchange="order.routing",
            routing_key="order.ib.new",
            body=json.dumps(envelope),
            properties=pika.BasicProperties(
                content_type="application/json", delivery_mode=2
            ),
        )

        # Wait for processing
        await asyncio.sleep(0.5)

        # Simulate IB error callback
        if "INT_TEST_002" in adapter.active_orders:
            order_info = adapter.active_orders["INT_TEST_002"]
            adapter.error(
                reqId=order_info["ib_order_id"],
                errorCode=201,
                errorString="Order rejected - invalid symbol",
            )

        # Wait for rejection report
        await asyncio.sleep(0.2)

        # Check rejection report
        exec_queue = "executions.monitoring"
        channel.queue_declare(queue=exec_queue, durable=True)
        channel.queue_bind(
            exchange="order.executions", queue=exec_queue, routing_key="execution.ib.*"
        )

        # Look for rejection
        rejected = False
        for _ in range(5):
            method, properties, body = channel.basic_get(queue=exec_queue)
            if method:
                exec_envelope = json.loads(body)
                if "fix_message" in exec_envelope:
                    # Parse FIX message to check status
                    fix_msg = exec_envelope["fix_message"]
                    if "39=8" in fix_msg:  # OrdStatus=REJECTED
                        rejected = True
                        channel.basic_ack(delivery_tag=method.delivery_tag)
                        break
                channel.basic_ack(delivery_tag=method.delivery_tag)

        assert rejected, "Order rejection not received"

        # Cleanup
        channel.queue_delete(exec_queue)

    @pytest.mark.asyncio
    async def test_market_data_flow(self, adapter, rabbitmq_connection):
        """Test market data subscription and publishing."""
        # Subscribe to market data via admin command
        channel = rabbitmq_connection.channel()
        command = {
            "command": "subscribe_market_data",
            "symbols": ["EURUSD", "GBPUSD"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        channel.basic_publish(
            exchange="admin.control",
            routing_key="admin.ib.command",
            body=json.dumps(command),
            properties=pika.BasicProperties(
                content_type="application/json", delivery_mode=2
            ),
        )

        # Wait for subscription
        await asyncio.sleep(0.5)

        # Verify subscriptions created
        assert "EURUSD" in adapter.market_data_subscriptions
        assert "GBPUSD" in adapter.market_data_subscriptions

        # Set up market data consumer
        mkt_queue = "market.data.test"
        channel.queue_declare(queue=mkt_queue, durable=False, auto_delete=True)
        channel.queue_bind(
            exchange="market.data.feed", queue=mkt_queue, routing_key="market.ib.*"
        )

        # Simulate market data update
        adapter._handle_market_data_update(
            "EURUSD", {"bid": 1.0994, "ask": 1.0996, "last": 1.0995, "volume": 1500000}
        )

        # Consume market data
        await asyncio.sleep(0.2)
        method, properties, body = channel.basic_get(queue=mkt_queue)
        assert method is not None

        # Verify market data
        mkt_data = json.loads(body)
        assert mkt_data["symbol"] == "EURUSD"
        assert mkt_data["broker"] == "ib"
        assert mkt_data["data"]["bid"] == 1.0994
        assert mkt_data["data"]["ask"] == 1.0996

        # Cleanup
        channel.basic_ack(delivery_tag=method.delivery_tag)
        channel.queue_delete(mkt_queue)

    @pytest.mark.asyncio
    async def test_connection_recovery(self, adapter, rabbitmq_connection):
        """Test adapter behavior during connection loss and recovery."""
        # Simulate IB connection loss
        adapter.connection.status = ConnectionStatus.ERROR
        adapter.connection.error = "Connection lost"

        # Trigger error callback
        adapter.error(reqId=-1, errorCode=1100, errorString="Connectivity lost")

        # Send status command to check state
        channel = rabbitmq_connection.channel()
        command = {"command": "status"}

        channel.basic_publish(
            exchange="admin.control",
            routing_key="admin.ib.command",
            body=json.dumps(command),
        )

        await asyncio.sleep(0.5)

        # Check status shows disconnected
        status_queue = "admin.status.monitor"
        channel.queue_declare(queue=status_queue, durable=True)
        channel.queue_bind(
            exchange="admin.status", queue=status_queue, routing_key="status.ib.*"
        )

        method, properties, body = channel.basic_get(queue=status_queue)
        if method:
            status_msg = json.loads(body)
            assert status_msg["data"]["status"] == "ERROR"
            channel.basic_ack(delivery_tag=method.delivery_tag)

        # Simulate reconnection
        adapter.connection.status = ConnectionStatus.READY
        adapter.connection.error = None
        adapter.error(reqId=-1, errorCode=1102, errorString="Connectivity restored")

        # Send another status command
        channel.basic_publish(
            exchange="admin.control",
            routing_key="admin.ib.command",
            body=json.dumps(command),
        )

        await asyncio.sleep(0.5)

        # Check status shows connected
        method, properties, body = channel.basic_get(queue=status_queue)
        if method:
            status_msg = json.loads(body)
            assert status_msg["data"]["status"] == "READY"
            channel.basic_ack(delivery_tag=method.delivery_tag)

        # Cleanup
        channel.queue_delete(status_queue)
