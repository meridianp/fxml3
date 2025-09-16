"""Manual Adapter with RabbitMQ Integration.

This module extends the manual adapter to integrate with RabbitMQ
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
from .manual_adapter import ManualBrokerAdapter, PendingOrder

logger = logging.getLogger(__name__)


class ManualMessageHandler(MessageHandler):
    """Message handler for manual adapter."""

    def __init__(self, adapter: "ManualRabbitMQAdapter"):
        self.adapter = adapter

    def handle_execution_report(
        self, message: FIXMessage, envelope: Dict[str, Any]
    ) -> bool:
        """Handle execution report - not used for manual adapter."""
        # Manual adapter sends execution reports, doesn't receive them
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
            elif command_type == "get_pending_orders":
                asyncio.create_task(self.adapter._send_pending_orders())
            elif command_type == "get_order_history":
                limit = response.get("limit", 100)
                asyncio.create_task(self.adapter._send_order_history(limit))
            elif command_type == "approve_order":
                asyncio.create_task(self.adapter._handle_approval_command(response))
            elif command_type == "reject_order":
                asyncio.create_task(self.adapter._handle_rejection_command(response))
            else:
                logger.warning(f"Unknown admin command: {command_type}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error handling admin command: {e}")
            return False

    def handle_market_data(
        self, data: Dict[str, Any], envelope: Dict[str, Any]
    ) -> bool:
        """Handle market data - not used for manual adapter."""
        return True


class ManualRabbitMQAdapter(ManualBrokerAdapter):
    """Manual Adapter with RabbitMQ integration.

    This adapter extends the base manual adapter to handle:
    - Consuming orders from RabbitMQ queues
    - Publishing execution reports to RabbitMQ
    - Handling administrative commands via message queue
    - Broadcasting approval requests
    """

    def __init__(self, config: AdapterConfig):
        """Initialize manual RabbitMQ adapter.

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
        self.approval_queue = f"manual.approval.requests"

        # Processing state
        self.is_processing = False
        self.order_processing_task: Optional[asyncio.Task] = None

        logger.info("Initialized manual RabbitMQ adapter")

    async def connect(self) -> bool:
        """Connect to both manual interface and RabbitMQ."""
        try:
            # Connect base manual adapter
            connected = await super().connect()
            if not connected:
                return False

            # Connect to RabbitMQ
            await self._connect_rabbitmq()

            # Start consuming messages
            await self._start_consuming()

            # Send initial status
            await self._send_status_update()

            logger.info("Manual RabbitMQ adapter fully connected")
            return True

        except Exception as e:
            logger.error(f"Failed to connect manual RabbitMQ adapter: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from both manual interface and RabbitMQ."""
        try:
            # Stop consuming
            await self._stop_consuming()

            # Disconnect from RabbitMQ
            await self._disconnect_rabbitmq()

            # Disconnect base adapter
            await super().disconnect()

            logger.info("Manual RabbitMQ adapter disconnected")

        except Exception as e:
            logger.error(f"Error disconnecting manual RabbitMQ adapter: {e}")

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

        # Create approval queue
        self.publisher.channel.queue_declare(
            queue=self.approval_queue,
            durable=True,
            arguments={"x-message-ttl": 600000},  # 10 minute TTL
        )

        # Create consumer with message handler
        message_handler = ManualMessageHandler(self)
        self.consumer = BrokerMessageConsumer(connection_params, message_handler)
        self.consumer.connect()

        logger.info(
            f"Connected to RabbitMQ at {self.rabbitmq_host}:{self.rabbitmq_port}"
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
            f"Started consuming from queues: {self.order_queue}, {self.admin_queue}"
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
            logger.error(f"Error handling order message: {e}")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def _handle_admin_message(self, channel, method, properties, body):
        """Handle admin message from RabbitMQ."""
        try:
            # Let the message handler process it
            self.consumer._handle_admin_message(channel, method, properties, body)

        except Exception as e:
            logger.error(f"Error handling admin message: {e}")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    async def _process_order_async(self, order: FIXMessage, delivery_tag: int) -> None:
        """Process order asynchronously."""
        try:
            # Submit order for manual approval
            order_id = await self.submit_order(order)

            # Publish approval request
            await self._publish_approval_request(order, order_id)

            # Acknowledge message
            if self.consumer and self.consumer.channel:
                self.consumer.channel.basic_ack(delivery_tag=delivery_tag)

        except Exception as e:
            logger.error(f"Failed to process order: {e}")
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

    async def _send_execution_report(
        self,
        pending_order: PendingOrder,
        ord_status,
        exec_type,
        text: Optional[str] = None,
        filled_qty: float = 0,
        avg_px: float = 0,
    ) -> None:
        """Override to publish execution report to RabbitMQ."""
        # Call parent implementation
        await super()._send_execution_report(
            pending_order, ord_status, exec_type, text, filled_qty, avg_px
        )

        if not self.publisher:
            return

        try:
            # Create execution report
            exec_report = ExecutionReport(
                order_id=pending_order.order_id,
                cl_ord_id=pending_order.cl_ord_id,
                exec_id=f"{pending_order.order_id}_{datetime.utcnow().timestamp()}",
                exec_type=exec_type,
                ord_status=ord_status,
                symbol=pending_order.order.symbol,
                side=pending_order.order.side,
                order_qty=pending_order.order.order_qty,
                price=getattr(pending_order.order, "price", 0),
                cum_qty=filled_qty,
                leaves_qty=pending_order.order.order_qty - filled_qty,
                avg_px=avg_px,
                transact_time=datetime.utcnow(),
                text=text,
            )

            # Add audit info
            if pending_order.reviewer:
                exec_report.text = f"{text} - Reviewed by: {pending_order.reviewer}"

            # Publish to executions exchange
            self.publisher.publish_fix_message(
                message=exec_report,
                broker_type=self.adapter_type,
                routing_key_suffix="execution",
                correlation_id=pending_order.cl_ord_id,
                headers={
                    "order_status": ord_status.value,
                    "exec_type": exec_type.value,
                    "symbol": pending_order.order.symbol,
                    "reviewer": pending_order.reviewer or "SYSTEM",
                },
            )

            logger.debug(f"Published execution report: {pending_order.cl_ord_id}")

        except Exception as e:
            logger.error(f"Failed to publish execution report: {e}")

    async def _publish_approval_request(self, order: FIXMessage, order_id: str) -> None:
        """Publish order approval request.

        Args:
            order: Original order.
            order_id: Assigned order ID.
        """
        if not self.publisher:
            return

        try:
            # Create approval request message
            approval_request = {
                "order_id": order_id,
                "cl_ord_id": order.cl_ord_id,
                "symbol": order.symbol,
                "side": order.side.name,
                "quantity": order.order_qty,
                "order_type": order.ord_type.name,
                "price": getattr(order, "price", None),
                "stop_price": getattr(order, "stop_px", None),
                "time_in_force": order.time_in_force.name,
                "timestamp": datetime.utcnow().isoformat(),
                "timeout": self.auto_reject_timeout,
                "approval_level": self._get_required_approval_level(
                    order.order_qty * (getattr(order, "price", 1.0) or 1.0)
                ),
            }

            # Publish to approval queue
            self.publisher.channel.basic_publish(
                exchange="",
                routing_key=self.approval_queue,
                body=json.dumps(approval_request),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                    expiration=str(self.auto_reject_timeout * 1000),  # milliseconds
                ),
            )

            logger.info(f"Published approval request for order: {order_id}")

        except Exception as e:
            logger.error(f"Failed to publish approval request: {e}")

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
                "pending_orders": len(self.pending_orders),
                "total_orders": len(self.order_history),
                "websocket_clients": len(self.websocket_clients),
                "auto_reject_timeout": self.auto_reject_timeout,
                "timestamp": datetime.utcnow().isoformat(),
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
            logger.error(f"Failed to send status update: {e}")

    async def _send_pending_orders(self) -> None:
        """Send list of pending orders."""
        if not self.publisher:
            return

        try:
            pending_orders = await self.get_pending_orders()

            # Publish to admin response
            self.publisher.publish_admin_command(
                command={
                    "type": "pending_orders_response",
                    "adapter": self.adapter_type,
                    "data": {
                        "orders": pending_orders,
                        "count": len(pending_orders),
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                },
                broker_type=self.adapter_type,
            )

        except Exception as e:
            logger.error(f"Failed to send pending orders: {e}")

    async def _send_order_history(self, limit: int) -> None:
        """Send order history."""
        if not self.publisher:
            return

        try:
            history = await self.get_order_history(limit=limit)

            # Publish to admin response
            self.publisher.publish_admin_command(
                command={
                    "type": "order_history_response",
                    "adapter": self.adapter_type,
                    "data": {
                        "orders": history,
                        "count": len(history),
                        "limit": limit,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                },
                broker_type=self.adapter_type,
            )

        except Exception as e:
            logger.error(f"Failed to send order history: {e}")

    async def _handle_approval_command(self, command: Dict[str, Any]) -> None:
        """Handle order approval command.

        Args:
            command: Approval command details.
        """
        cl_ord_id = command.get("cl_ord_id")
        reviewer = command.get("reviewer", "UNKNOWN")
        notes = command.get("notes")
        modifications = command.get("modifications")
        risk_overrides = command.get("risk_overrides")

        if not cl_ord_id:
            logger.error("No cl_ord_id in approval command")
            return

        success = await self.approve_order(
            cl_ord_id=cl_ord_id,
            reviewer=reviewer,
            notes=notes,
            modifications=modifications,
            risk_overrides=risk_overrides,
        )

        # Send response
        if self.publisher:
            self.publisher.publish_admin_command(
                command={
                    "type": "approval_response",
                    "adapter": self.adapter_type,
                    "data": {
                        "cl_ord_id": cl_ord_id,
                        "success": success,
                        "reviewer": reviewer,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                },
                broker_type=self.adapter_type,
            )

    async def _handle_rejection_command(self, command: Dict[str, Any]) -> None:
        """Handle order rejection command.

        Args:
            command: Rejection command details.
        """
        cl_ord_id = command.get("cl_ord_id")
        reviewer = command.get("reviewer", "UNKNOWN")
        reason = command.get("reason", "No reason provided")
        notes = command.get("notes")

        if not cl_ord_id:
            logger.error("No cl_ord_id in rejection command")
            return

        success = await self.reject_order(
            cl_ord_id=cl_ord_id, reviewer=reviewer, reason=reason, notes=notes
        )

        # Send response
        if self.publisher:
            self.publisher.publish_admin_command(
                command={
                    "type": "rejection_response",
                    "adapter": self.adapter_type,
                    "data": {
                        "cl_ord_id": cl_ord_id,
                        "success": success,
                        "reviewer": reviewer,
                        "reason": reason,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                },
                broker_type=self.adapter_type,
            )
