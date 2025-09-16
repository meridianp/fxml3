"""Unit tests for IB RabbitMQ adapter.

This module tests the IB adapter's RabbitMQ integration including:
- Message consumption from queues
- Execution report publishing
- Admin command handling
- Connection management
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pika
import pytest

from fxml4.brokers.adapters.base import AdapterConfig, ConnectionStatus
from fxml4.brokers.adapters.ib_rabbitmq_adapter import (
    IBMessageHandler,
    IBRabbitMQAdapter,
)
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle


class TestIBMessageHandler:
    """Test IB message handler."""

    @pytest.fixture
    def mock_adapter(self):
        """Create mock IB RabbitMQ adapter."""
        adapter = MagicMock()
        adapter.connect = AsyncMock()
        adapter.disconnect = AsyncMock()
        adapter._send_status_update = AsyncMock()
        adapter.subscribe_market_data = AsyncMock()
        adapter.unsubscribe_market_data = AsyncMock()
        return adapter

    @pytest.fixture
    def handler(self, mock_adapter):
        """Create message handler."""
        return IBMessageHandler(mock_adapter)

    def test_handle_admin_connect(self, handler, mock_adapter):
        """Test handling admin connect command."""
        response = {"command": "connect"}
        envelope = {"timestamp": datetime.now(timezone.utc).isoformat()}

        success = handler.handle_admin_response(response, envelope)

        assert success == True
        # Verify async task created (can't directly check task creation)

    def test_handle_admin_disconnect(self, handler, mock_adapter):
        """Test handling admin disconnect command."""
        response = {"command": "disconnect"}
        envelope = {"timestamp": datetime.now(timezone.utc).isoformat()}

        success = handler.handle_admin_response(response, envelope)

        assert success == True

    def test_handle_admin_status(self, handler, mock_adapter):
        """Test handling admin status command."""
        response = {"command": "status"}
        envelope = {"timestamp": datetime.now(timezone.utc).isoformat()}

        success = handler.handle_admin_response(response, envelope)

        assert success == True

    def test_handle_admin_subscribe_market_data(self, handler, mock_adapter):
        """Test handling market data subscription."""
        response = {"command": "subscribe_market_data", "symbols": ["EURUSD", "GBPUSD"]}
        envelope = {"timestamp": datetime.now(timezone.utc).isoformat()}

        success = handler.handle_admin_response(response, envelope)

        assert success == True

    def test_handle_admin_unknown_command(self, handler, mock_adapter):
        """Test handling unknown admin command."""
        response = {"command": "unknown_command"}
        envelope = {"timestamp": datetime.now(timezone.utc).isoformat()}

        success = handler.handle_admin_response(response, envelope)

        assert success == False

    def test_handle_admin_error(self, handler, mock_adapter):
        """Test handling admin command error."""
        mock_adapter.connect.side_effect = Exception("Connection error")
        response = {"command": "connect"}
        envelope = {"timestamp": datetime.now(timezone.utc).isoformat()}

        success = handler.handle_admin_response(response, envelope)

        assert success == False


class TestIBRabbitMQAdapter:
    """Test IB RabbitMQ adapter."""

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
            features={"market_data": True, "order_modification": True},
            limits={"max_orders_per_second": 10},
        )

    @pytest.fixture
    def mock_publisher(self):
        """Create mock message publisher."""
        with patch(
            "fxml4.brokers.adapters.ib_rabbitmq_adapter.BrokerMessagePublisher"
        ) as mock:
            instance = MagicMock()
            instance.connect = MagicMock()
            instance.disconnect = MagicMock()
            instance.publish_fix_message = MagicMock()
            instance.publish_admin_command = MagicMock()
            instance.channel = MagicMock()
            mock.return_value = instance
            yield instance

    @pytest.fixture
    def mock_consumer(self):
        """Create mock message consumer."""
        with patch(
            "fxml4.brokers.adapters.ib_rabbitmq_adapter.BrokerMessageConsumer"
        ) as mock:
            instance = MagicMock()
            instance.connect = MagicMock()
            instance.disconnect = MagicMock()
            instance.run_async = MagicMock()
            instance.stop_consuming = MagicMock()
            instance.channel = MagicMock()
            mock.return_value = instance
            yield instance

    @pytest.fixture
    def adapter(self, adapter_config, mock_publisher, mock_consumer):
        """Create IB RabbitMQ adapter instance."""
        with patch("fxml4.brokers.adapters.ib_rabbitmq_adapter.EClient"):
            adapter = IBRabbitMQAdapter(adapter_config)
            # Set up mocks after creation
            adapter.publisher = mock_publisher
            adapter.consumer = mock_consumer
            return adapter

    @pytest.mark.asyncio
    async def test_connect_full(self, adapter, mock_publisher, mock_consumer):
        """Test full connection to IB and RabbitMQ."""
        # Mock successful IB connection
        with patch.object(IBRabbitMQAdapter, "connect", return_value=True):
            # Override to test our connect method
            adapter.connection.status = ConnectionStatus.DISCONNECTED

            # Mock connection methods
            adapter._connect_rabbitmq = AsyncMock()
            adapter._start_consuming = AsyncMock()
            adapter._send_status_update = AsyncMock()

            # Mock parent connect
            async def mock_parent_connect():
                adapter.connection.status = ConnectionStatus.READY
                return True

            with patch(
                "fxml4.brokers.adapters.ib_adapter.IBBrokerAdapter.connect",
                new=mock_parent_connect,
            ):
                connected = await adapter.connect()

            assert connected == True
            adapter._connect_rabbitmq.assert_called_once()
            adapter._start_consuming.assert_called_once()
            adapter._send_status_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_rabbitmq(self, adapter):
        """Test RabbitMQ connection setup."""
        # Reset mocks
        adapter.publisher = None
        adapter.consumer = None

        with patch(
            "fxml4.brokers.adapters.ib_rabbitmq_adapter.BrokerMessagePublisher"
        ) as mock_pub:
            with patch(
                "fxml4.brokers.adapters.ib_rabbitmq_adapter.BrokerMessageConsumer"
            ) as mock_cons:
                mock_pub_instance = MagicMock()
                mock_cons_instance = MagicMock()
                mock_pub.return_value = mock_pub_instance
                mock_cons.return_value = mock_cons_instance

                await adapter._connect_rabbitmq()

                # Verify connection parameters
                connection_call = mock_pub.call_args[0][0]
                assert isinstance(connection_call, pika.ConnectionParameters)
                assert connection_call.host == "rabbitmq"
                assert connection_call.port == 5672

                # Verify publisher and consumer created
                assert adapter.publisher == mock_pub_instance
                assert adapter.consumer == mock_cons_instance
                mock_pub_instance.connect.assert_called_once()
                mock_cons_instance.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_consuming(self, adapter, mock_consumer):
        """Test starting message consumption."""
        adapter.is_processing = False

        await adapter._start_consuming()

        # Verify queue consumption setup
        assert mock_consumer.channel.basic_consume.call_count == 2

        # Check order queue consumption
        order_call = mock_consumer.channel.basic_consume.call_args_list[0]
        assert order_call[1]["queue"] == "orders.ib.inbound"
        assert order_call[1]["auto_ack"] == False

        # Check admin queue consumption
        admin_call = mock_consumer.channel.basic_consume.call_args_list[1]
        assert admin_call[1]["queue"] == "admin.ib.commands"
        assert admin_call[1]["auto_ack"] == False

        # Verify consumer started
        mock_consumer.run_async.assert_called_once()

        # Verify processing started
        assert adapter.is_processing == True
        assert adapter.order_processing_task is not None

    @pytest.mark.asyncio
    async def test_stop_consuming(self, adapter, mock_consumer):
        """Test stopping message consumption."""
        adapter.is_processing = True
        adapter.order_processing_task = asyncio.create_task(asyncio.sleep(10))

        await adapter._stop_consuming()

        assert adapter.is_processing == False
        assert adapter.order_processing_task.cancelled()
        mock_consumer.stop_consuming.assert_called_once()

    def test_handle_order_message_success(self, adapter):
        """Test successful order message handling."""
        # Create test FIX message
        fix_message = "8=FIX.4.4|35=D|49=TEST|56=IB|34=1|52=20231215-10:00:00|11=TEST200|55=EURUSD|54=1|38=100000|40=2|44=1.1000|59=0|"
        envelope = {
            "fix_message": fix_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "client",
        }

        # Mock channel and method
        channel = MagicMock()
        method = MagicMock()
        method.delivery_tag = 12345
        properties = {}
        body = json.dumps(envelope).encode()

        # Mock FIX parser
        mock_order = NewOrderSingle(
            cl_ord_id="TEST200",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.LIMIT,
            price=1.1000,
        )

        with patch.object(adapter.fix_parser, "parse", return_value=mock_order):
            with patch("asyncio.create_task") as mock_create_task:
                adapter._handle_order_message(channel, method, properties, body)

                # Verify FIX message parsed
                adapter.fix_parser.parse.assert_called_once_with(fix_message)

                # Verify async task created
                mock_create_task.assert_called_once()

    def test_handle_order_message_no_fix(self, adapter):
        """Test handling order message without FIX content."""
        envelope = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "client",
        }

        channel = MagicMock()
        method = MagicMock()
        method.delivery_tag = 12346
        properties = {}
        body = json.dumps(envelope).encode()

        adapter._handle_order_message(channel, method, properties, body)

        # Should reject message
        channel.basic_nack.assert_called_once_with(delivery_tag=12346, requeue=False)

    def test_handle_order_message_parse_error(self, adapter):
        """Test handling order message with parse error."""
        envelope = {
            "fix_message": "invalid fix message",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        channel = MagicMock()
        method = MagicMock()
        method.delivery_tag = 12347
        properties = {}
        body = json.dumps(envelope).encode()

        with patch.object(
            adapter.fix_parser, "parse", side_effect=Exception("Parse error")
        ):
            adapter._handle_order_message(channel, method, properties, body)

            # Should reject message
            channel.basic_nack.assert_called_once_with(
                delivery_tag=12347, requeue=False
            )

    @pytest.mark.asyncio
    async def test_process_order_async_success(self, adapter):
        """Test successful async order processing."""
        order = NewOrderSingle(
            cl_ord_id="TEST201",
            symbol="GBPUSD",
            side=Side.SELL,
            order_qty=50000,
            ord_type=OrdType.MARKET,
        )
        delivery_tag = 12348

        # Mock submit_order
        adapter.submit_order = AsyncMock(return_value="3000")
        adapter.consumer.channel = MagicMock()

        await adapter._process_order_async(order, delivery_tag)

        # Verify order submitted
        adapter.submit_order.assert_called_once_with(order)

        # Verify message acknowledged
        adapter.consumer.channel.basic_ack.assert_called_once_with(
            delivery_tag=delivery_tag
        )

    @pytest.mark.asyncio
    async def test_process_order_async_failure(self, adapter):
        """Test failed async order processing."""
        order = NewOrderSingle(
            cl_ord_id="TEST202",
            symbol="USDJPY",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.LIMIT,
            price=110.00,
        )
        delivery_tag = 12349

        # Mock submit_order failure
        adapter.submit_order = AsyncMock(
            side_effect=Exception("Order submission failed")
        )
        adapter.consumer.channel = MagicMock()

        await adapter._process_order_async(order, delivery_tag)

        # Verify message rejected
        adapter.consumer.channel.basic_nack.assert_called_once_with(
            delivery_tag=delivery_tag, requeue=False
        )

    def test_process_execution_report(self, adapter, mock_publisher):
        """Test processing and publishing execution report."""
        exec_report = ExecutionReport(
            order_id="3001",
            cl_ord_id="TEST203",
            exec_id="EXEC3001",
            exec_type=ExecType.TRADE,
            ord_status=OrdStatus.FILLED,
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            cum_qty=100000,
            leaves_qty=0,
            avg_px=1.0995,
        )
        exec_report.cl_ord_id = "TEST203"  # Ensure cl_ord_id is set
        exec_report.ord_status = OrdStatus.FILLED
        exec_report.exec_type = ExecType.TRADE
        exec_report.symbol = "EURUSD"

        adapter._process_execution_report(exec_report)

        # Verify execution report published
        mock_publisher.publish_fix_message.assert_called_once()
        call_args = mock_publisher.publish_fix_message.call_args
        assert call_args[1]["message"] == exec_report
        assert call_args[1]["broker_type"] == "ib"
        assert call_args[1]["routing_key_suffix"] == "execution"
        assert call_args[1]["correlation_id"] == "TEST203"
        assert call_args[1]["headers"]["order_status"] == "4"  # FILLED
        assert call_args[1]["headers"]["exec_type"] == "F"  # TRADE
        assert call_args[1]["headers"]["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_send_status_update(self, adapter, mock_publisher):
        """Test sending adapter status update."""
        adapter.connection.status = ConnectionStatus.READY
        adapter.connection._connected = True
        adapter.connection._authenticated = True
        adapter.account_id = "DU123456"
        adapter.active_orders = {"TEST204": {}, "TEST205": {}}
        adapter.ib_host = "localhost"
        adapter.ib_port = 7497
        adapter.client_id = 1
        adapter.next_order_id = 3002

        await adapter._send_status_update()

        # Verify status published
        mock_publisher.publish_admin_command.assert_called_once()
        call_args = mock_publisher.publish_admin_command.call_args
        command = call_args[1]["command"]

        assert command["type"] == "status_update"
        assert command["adapter"] == "ib"
        assert command["data"]["adapter_type"] == "ib"
        assert command["data"]["status"] == "READY"
        assert command["data"]["connected"] == True
        assert command["data"]["authenticated"] == True
        assert command["data"]["account_id"] == "DU123456"
        assert command["data"]["active_orders"] == 2
        assert command["data"]["connection_info"]["next_order_id"] == 3002

    def test_handle_market_data_update(self, adapter, mock_publisher):
        """Test handling and publishing market data update."""
        symbol = "EURUSD"
        data = {
            "bid": 1.0994,
            "ask": 1.0996,
            "last": 1.0995,
            "volume": 1000000,
            "bid_size": 500000,
            "ask_size": 750000,
        }

        # Need to access channel directly
        adapter.publisher.channel = MagicMock()

        adapter._handle_market_data_update(symbol, data)

        # Verify market data published
        adapter.publisher.channel.basic_publish.assert_called_once()
        call_args = adapter.publisher.channel.basic_publish.call_args

        assert call_args[1]["exchange"] == "market.data.feed"
        assert call_args[1]["routing_key"] == "market.ib.EURUSD"

        # Parse published body
        published_data = json.loads(call_args[1]["body"])
        assert published_data["symbol"] == "EURUSD"
        assert published_data["broker"] == "ib"
        assert published_data["data"] == data

    @pytest.mark.asyncio
    async def test_disconnect_full(self, adapter, mock_publisher, mock_consumer):
        """Test full disconnection from IB and RabbitMQ."""
        adapter.is_processing = True
        adapter.order_processing_task = asyncio.create_task(asyncio.sleep(10))

        # Mock parent disconnect
        with patch(
            "fxml4.brokers.adapters.ib_adapter.IBBrokerAdapter.disconnect"
        ) as mock_parent:
            await adapter.disconnect()

            # Verify stopped consuming
            assert adapter.is_processing == False
            mock_consumer.stop_consuming.assert_called_once()

            # Verify RabbitMQ disconnected
            mock_publisher.disconnect.assert_called_once()
            mock_consumer.disconnect.assert_called_once()

            # Verify parent disconnect called
            mock_parent.assert_called_once()
