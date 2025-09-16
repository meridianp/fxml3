"""IB Adapter with RabbitMQ Integration.

This module extends the base IB adapter to integrate with RabbitMQ
for message queue based communication.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import pika

from ...fix.messages.base import FIXMessage
from ...fix.messages.orders import ExecutionReport
from ...fix.utils.parser import FIXParser
from ..messaging.consumer import BrokerMessageConsumer, MessageHandler
from ..messaging.publisher import BrokerMessagePublisher
from .base import AdapterConfig
from .ib_adapter import IBBrokerAdapter

logger = logging.getLogger(__name__)


class IBMessageHandler(MessageHandler):
    """Message handler for IB adapter."""

    def __init__(self, adapter: "IBRabbitMQAdapter"):
        self.adapter = adapter

    def handle_execution_report(
        self, message: FIXMessage, envelope: Dict[str, Any]
    ) -> bool:
        """Handle execution report - not used for IB adapter."""
        # IB adapter sends execution reports, doesn't receive them
        return True

    def handle_admin_response(
        self, response: Dict[str, Any], envelope: Dict[str, Any]
    ) -> bool:
        """Handle administrative command."""
        try:
            command_type = response.get("command", "unknown")

            if command_type == "connect":
                asyncio.create_task(self.adapter.connect())
            elif command_type == "disconnect":
                asyncio.create_task(self.adapter.disconnect())
            elif command_type == "status":
                asyncio.create_task(self.adapter._send_status_update())
            elif command_type == "subscribe_market_data":
                symbols = response.get("symbols", [])
                asyncio.create_task(self.adapter.subscribe_market_data(symbols))
            elif command_type == "unsubscribe_market_data":
                symbols = response.get("symbols", [])
                asyncio.create_task(self.adapter.unsubscribe_market_data(symbols))
            else:
                logger.warning("Unknown admin command: %s", command_type)
                return False

            return True

        except Exception as e:
            logger.error("Error handling admin command: %s", e)
            return False

    def handle_market_data(
        self, data: Dict[str, Any], envelope: Dict[str, Any]
    ) -> bool:
        """Handle market data - not used for IB adapter."""
        # IB adapter publishes market data, doesn't consume it
        return True


class IBRabbitMQAdapter(IBBrokerAdapter):
    """IB Adapter with RabbitMQ integration.

    This adapter extends the base IB adapter to handle:
    - Consuming orders from RabbitMQ queues
    - Publishing execution reports to RabbitMQ
    - Handling administrative commands via message queue
    """

    def __init__(self, config: AdapterConfig):
        """Initialize IB RabbitMQ adapter.

        Args:
            config: Adapter configuration with RabbitMQ settings.
        """
        super().__init__(config)

        # RabbitMQ configuration
        rabbitmq_config = config.connection_params.get("rabbitmq", {})
        self.rabbitmq_host = rabbitmq_config.get("host", "rabbitmq")
        self.rabbitmq_port = rabbitmq_config.get("port", 5672)
        self.rabbitmq_user = rabbitmq_config.get("username", "guest")
        self.rabbitmq_pass = rabbitmq_config.get("password", "guest")

        # Message queue components
        self.publisher: Optional[BrokerMessagePublisher] = None
        self.consumer: Optional[BrokerMessageConsumer] = None
        self.fix_parser = FIXParser()

        # Queue names
        self.order_queue = f"orders.{self.adapter_type}.inbound"
        self.admin_queue = f"admin.{self.adapter_type}.commands"

        # Processing state
        self.is_processing = False
        self.order_processing_task: Optional[asyncio.Task] = None

        logger.info("Initialized IB RabbitMQ adapter")

    async def connect(self) -> bool:
        """Connect to both IB and RabbitMQ."""
        try:
            # Connect to IB first
            ib_connected = await super().connect()
            if not ib_connected:
                return False

            # Connect to RabbitMQ
            await self._connect_rabbitmq()

            # Start consuming messages
            await self._start_consuming()

            # Send initial status
            await self._send_status_update()

            logger.info("IB RabbitMQ adapter fully connected")
            return True

        except Exception as e:
            logger.error("Failed to connect IB RabbitMQ adapter: %s", e)
            return False

    async def disconnect(self) -> None:
        """Disconnect from both IB and RabbitMQ."""
        try:
            # Stop consuming
            await self._stop_consuming()

            # Disconnect from RabbitMQ
            await self._disconnect_rabbitmq()

            # Disconnect from IB
            await super().disconnect()

            logger.info("IB RabbitMQ adapter disconnected")

        except Exception as e:
            logger.error("Error disconnecting IB RabbitMQ adapter: %s", e)

    async def _connect_rabbitmq(self) -> None:
        """Connect to RabbitMQ."""
        # Create connection parameters
        connection_params = pika.ConnectionParameters(
            host=self.rabbitmq_host,
            port=self.rabbitmq_port,
            credentials=pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_pass),
            heartbeat=600,
            blocked_connection_timeout=300,
        )

        # Create publisher
        self.publisher = BrokerMessagePublisher(connection_params)
        self.publisher.connect()

        # Create consumer with message handler
        message_handler = IBMessageHandler(self)
        self.consumer = BrokerMessageConsumer(connection_params, message_handler)
        self.consumer.connect()

        logger.info(
            "Connected to RabbitMQ at %s:%d", self.rabbitmq_host, self.rabbitmq_port
        )

    async def _disconnect_rabbitmq(self) -> None:
        """Disconnect from RabbitMQ."""
        if self.publisher:
            self.publisher.disconnect()
            self.publisher = None

        if self.consumer:
            self.consumer.disconnect()
            self.consumer = None

        logger.info("Disconnected from RabbitMQ")

    async def _start_consuming(self) -> None:
        """Start consuming messages from RabbitMQ."""
        if not self.consumer:
            return

        # Start consuming from order queue
        self.consumer.channel.basic_consume(
            queue=self.order_queue,
            on_message_callback=self._handle_order_message,
            auto_ack=False,
        )

        # Start consuming from admin queue
        self.consumer.channel.basic_consume(
            queue=self.admin_queue,
            on_message_callback=self._handle_admin_message,
            auto_ack=False,
        )

        # Start consumer thread
        self.consumer.run_async()

        # Start order processing task
        self.is_processing = True
        self.order_processing_task = asyncio.create_task(self._process_orders())

        logger.info(
            "Started consuming from queues: %s, %s", self.order_queue, self.admin_queue
        )

    async def _stop_consuming(self) -> None:
        """Stop consuming messages from RabbitMQ."""
        self.is_processing = False

        if self.order_processing_task:
            self.order_processing_task.cancel()
            try:
                await self.order_processing_task
            except asyncio.CancelledError:
                pass

        if self.consumer:
            self.consumer.stop_consuming()

        logger.info("Stopped consuming messages")

    def _handle_order_message(self, channel, method, properties, body):
        """Handle order message from RabbitMQ."""
        try:
            # Parse message envelope
            envelope = json.loads(body)
            fix_message = envelope.get("fix_message", "")

            if not fix_message:
                logger.error("No FIX message in envelope")
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return

            # Parse FIX message
            order = self.fix_parser.parse(fix_message)

            # Add to processing queue
            asyncio.create_task(self._process_order_async(order, method.delivery_tag))

        except Exception as e:
            logger.error("Error handling order message: %s", e)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def _handle_admin_message(self, channel, method, properties, body):
        """Handle admin message from RabbitMQ."""
        try:
            # Let the message handler process it
            self.consumer._handle_admin_message(channel, method, properties, body)

        except Exception as e:
            logger.error("Error handling admin message: %s", e)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    async def _process_order_async(self, order: FIXMessage, delivery_tag: int) -> None:
        """Process order asynchronously."""
        try:
            # Submit order to IB
            await self.submit_order(order)

            # Acknowledge message
            if self.consumer and self.consumer.channel:
                self.consumer.channel.basic_ack(delivery_tag=delivery_tag)

        except Exception as e:
            logger.error("Failed to process order: %s", e)
            # Reject message and send to DLQ
            if self.consumer and self.consumer.channel:
                self.consumer.channel.basic_nack(
                    delivery_tag=delivery_tag, requeue=False
                )

    async def _process_orders(self) -> None:
        """Main order processing loop."""
        # This is handled by callbacks, so just keep the task alive
        while self.is_processing:
            await asyncio.sleep(1)

    def _process_execution_report(self, exec_report: ExecutionReport) -> None:
        """Process and publish execution report."""
        if not self.publisher:
            logger.warning("Cannot publish execution report - no publisher")
            return

        try:
            # Publish to executions exchange
            self.publisher.publish_fix_message(
                message=exec_report,
                broker_type=self.adapter_type,
                routing_key_suffix="execution",
                correlation_id=exec_report.cl_ord_id,
                headers={
                    "order_status": exec_report.ord_status.value,
                    "exec_type": exec_report.exec_type.value,
                    "symbol": exec_report.symbol,
                },
            )

            logger.debug("Published execution report: %s", exec_report.cl_ord_id)

        except Exception as e:
            logger.error("Failed to publish execution report: %s", e)

    async def _send_status_update(self) -> None:
        """Send adapter status update."""
        if not self.publisher:
            return

        try:
            status = {
                "adapter_type": self.adapter_type,
                "status": self.connection.status.value,
                "connected": self.connection.is_connected(),
                "authenticated": self.connection.is_ready(),
                "account_id": self.account_id,
                "active_orders": len(self.active_orders),
                "timestamp": datetime.utcnow().isoformat(),
                "connection_info": {
                    "ib_host": self.ib_host,
                    "ib_port": self.ib_port,
                    "client_id": self.client_id,
                    "next_order_id": self.next_order_id,
                },
            }

            # Publish to admin status exchange
            self.publisher.publish_admin_command(
                command={
                    "type": "status_update",
                    "adapter": self.adapter_type,
                    "data": status,
                },
                broker_type=self.adapter_type,
            )

        except Exception as e:
            logger.error("Failed to send status update: %s", e)

    def _handle_market_data_update(self, symbol: str, data: Dict[str, Any]) -> None:
        """Handle and publish market data update."""
        if not self.publisher:
            return

        try:
            # Create market data message
            market_data = {
                "symbol": symbol,
                "timestamp": datetime.utcnow().isoformat(),
                "broker": self.adapter_type,
                "data": data,
            }

            # Publish to market data feed
            self.publisher.channel.basic_publish(
                exchange="market.data.feed",
                routing_key=f"market.{self.adapter_type}.{symbol}",
                body=json.dumps(market_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                    timestamp=int(datetime.utcnow().timestamp()),
                ),
            )

        except Exception as e:
            logger.error("Failed to publish market data: %s", e)
