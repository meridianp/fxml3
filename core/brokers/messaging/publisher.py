"""Message Publisher for Broker Communication.

This module provides publishing capabilities for sending FIX messages
through RabbitMQ to broker adapters.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Union

import pika
from pika.exceptions import ChannelClosed, ConnectionClosed

from ...fix.messages.base import FIXMessage
from ...fix.utils.builder import FIXBuilder
from .topology import MessagePriority

logger = logging.getLogger(__name__)


class PublishError(Exception):
    """Exception raised when message publishing fails."""

    pass


class BrokerMessagePublisher:
    """Publisher for sending messages to broker adapters via RabbitMQ.

    This class handles the publishing of FIX messages to broker-specific
    queues through the defined RabbitMQ topology.
    """

    def __init__(
        self,
        connection_params: pika.ConnectionParameters,
        fix_builder: Optional[FIXBuilder] = None,
    ):
        """Initialize message publisher.

        Args:
            connection_params: RabbitMQ connection parameters.
            fix_builder: FIX message builder (creates default if None).
        """
        self.connection_params = connection_params
        self.connection = None
        self.channel = None
        self.fix_builder = fix_builder or FIXBuilder()

        # Publishing configuration
        self.default_exchange = "orders.outbound"
        self.confirm_delivery = True
        self.mandatory = True
        self.immediate = False

        # Message properties
        self.default_properties = pika.BasicProperties(
            delivery_mode=2,  # Persistent message
            content_type="application/json",
            content_encoding="utf-8",
            timestamp=int(datetime.utcnow().timestamp()),
            app_id="FXML4",
            message_id=None,  # Set per message
            correlation_id=None,  # Set per message
            reply_to=None,  # Set if response expected
            expiration=None,  # Set based on message type
            priority=MessagePriority.NORMAL.value,
            headers={},
        )

    def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        try:
            self.connection = pika.BlockingConnection(self.connection_params)
            self.channel = self.connection.channel()

            # Enable publisher confirms for reliability
            if self.confirm_delivery:
                self.channel.confirm_delivery()

            logger.info("Publisher connected to RabbitMQ")

        except Exception as e:
            logger.error("Failed to connect publisher to RabbitMQ: %s", e)
            raise PublishError(f"Connection failed: {e}") from e

    def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Publisher disconnected from RabbitMQ")
        except Exception as e:
            logger.warning("Error during publisher disconnect: %s", e)

    def publish_fix_message(
        self,
        message: FIXMessage,
        broker_type: str,
        routing_key_suffix: str = "",
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        expiration_ms: Optional[int] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Publish FIX message to broker adapter.

        Args:
            message: FIX message to publish.
            broker_type: Target broker type (ib, manual, fxcm, fix).
            routing_key_suffix: Optional suffix for routing key.
            priority: Message priority level.
            correlation_id: Correlation ID for request/response tracking.
            reply_to: Queue name for responses.
            expiration_ms: Message expiration in milliseconds.
            headers: Additional message headers.

        Returns:
            True if message was published successfully.

        Raises:
            PublishError: If publishing fails.
        """
        if not self.channel:
            raise PublishError("Must connect before publishing")

        try:
            # Build FIX string
            fix_string = self.fix_builder.build_from_message(message)

            # Create message envelope
            envelope = self._create_message_envelope(
                fix_message=fix_string,
                message_type=message.msg_type.value,
                broker_type=broker_type,
                correlation_id=correlation_id,
                headers=headers,
            )

            # Determine routing key
            routing_key = self._build_routing_key(broker_type, routing_key_suffix)

            # Create message properties
            properties = self._create_message_properties(
                priority=priority,
                correlation_id=correlation_id,
                reply_to=reply_to,
                expiration_ms=expiration_ms,
                headers=headers,
                message_id=getattr(message, "cl_ord_id", None),
            )

            # Publish message
            success = self.channel.basic_publish(
                exchange=self.default_exchange,
                routing_key=routing_key,
                body=json.dumps(envelope),
                properties=properties,
                mandatory=self.mandatory,
                immediate=self.immediate,
            )

            if self.confirm_delivery and not success:
                raise PublishError("Message delivery not confirmed")

            logger.info(
                "Published FIX message: type=%s, broker=%s, routing_key=%s",
                message.msg_type.value,
                broker_type,
                routing_key,
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to publish FIX message: type=%s, broker=%s, error=%s",
                message.msg_type.value if message else "unknown",
                broker_type,
                e,
            )
            raise PublishError(f"Failed to publish message: {e}") from e

    def publish_order(
        self,
        order_message: FIXMessage,
        broker_type: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None,
        timeout_ms: int = 300000,  # 5 minutes default
    ) -> bool:
        """Publish order message to broker.

        Args:
            order_message: Order FIX message (NewOrderSingle, etc.).
            broker_type: Target broker type.
            priority: Message priority.
            correlation_id: Correlation ID for tracking.
            timeout_ms: Order timeout in milliseconds.

        Returns:
            True if order was published successfully.
        """
        return self.publish_fix_message(
            message=order_message,
            broker_type=broker_type,
            routing_key_suffix="order",
            priority=priority,
            correlation_id=correlation_id,
            expiration_ms=timeout_ms,
            headers={
                "message_category": "order",
                "order_type": order_message.get_field(40, "unknown"),
                "symbol": order_message.get_field(55, "unknown"),
            },
        )

    def publish_cancel_request(
        self,
        cancel_message: FIXMessage,
        broker_type: str,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Publish order cancellation request.

        Args:
            cancel_message: Order cancel request message.
            broker_type: Target broker type.
            correlation_id: Correlation ID for tracking.

        Returns:
            True if cancellation was published successfully.
        """
        return self.publish_fix_message(
            message=cancel_message,
            broker_type=broker_type,
            routing_key_suffix="cancel",
            priority=MessagePriority.HIGH,
            correlation_id=correlation_id,
            expiration_ms=60000,  # 1 minute for cancellations
            headers={
                "message_category": "cancel",
                "orig_cl_ord_id": cancel_message.get_field(41, "unknown"),
            },
        )

    def publish_admin_command(
        self,
        command: Dict[str, Any],
        broker_type: str,
        priority: MessagePriority = MessagePriority.HIGH,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Publish administrative command to broker.

        Args:
            command: Administrative command dictionary.
            broker_type: Target broker type.
            priority: Message priority.
            correlation_id: Correlation ID for tracking.

        Returns:
            True if command was published successfully.
        """
        if not self.channel:
            raise PublishError("Must connect before publishing")

        try:
            # Create message properties
            properties = self._create_message_properties(
                priority=priority,
                correlation_id=correlation_id,
                expiration_ms=60000,  # 1 minute for admin commands
                headers={
                    "message_category": "admin",
                    "command_type": command.get("type", "unknown"),
                },
            )

            # Publish to admin exchange
            success = self.channel.basic_publish(
                exchange="admin.commands",
                routing_key=broker_type,
                body=json.dumps(command),
                properties=properties,
                mandatory=True,
            )

            if self.confirm_delivery and not success:
                raise PublishError("Admin command delivery not confirmed")

            logger.info(
                "Published admin command: type=%s, broker=%s",
                command.get("type", "unknown"),
                broker_type,
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to publish admin command: broker=%s, error=%s", broker_type, e
            )
            raise PublishError(f"Failed to publish admin command: {e}") from e

    def publish_urgent_message(
        self,
        message: Union[FIXMessage, Dict[str, Any]],
        message_type: str,  # "orders" or "admin"
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Publish urgent message to priority queue.

        Args:
            message: Urgent message to publish.
            message_type: Type of urgent message ("orders" or "admin").
            correlation_id: Correlation ID for tracking.

        Returns:
            True if urgent message was published successfully.
        """
        if not self.channel:
            raise PublishError("Must connect before publishing")

        try:
            # Prepare message body
            if isinstance(message, FIXMessage):
                body = json.dumps(
                    self._create_message_envelope(
                        fix_message=self.fix_builder.build_from_message(message),
                        message_type=message.msg_type.value,
                        broker_type="urgent",
                        correlation_id=correlation_id,
                    )
                )
            else:
                body = json.dumps(message)

            # Create urgent properties
            properties = self._create_message_properties(
                priority=MessagePriority.URGENT,
                correlation_id=correlation_id,
                expiration_ms=30000,  # 30 seconds for urgent messages
                headers={"message_category": "urgent", "urgent_type": message_type},
            )

            # Publish to priority exchange
            success = self.channel.basic_publish(
                exchange="priority.urgent",
                routing_key=message_type,
                body=body,
                properties=properties,
                mandatory=True,
            )

            if self.confirm_delivery and not success:
                raise PublishError("Urgent message delivery not confirmed")

            logger.warning(
                "Published URGENT message: type=%s, correlation_id=%s",
                message_type,
                correlation_id,
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to publish urgent message: type=%s, error=%s", message_type, e
            )
            raise PublishError(f"Failed to publish urgent message: {e}") from e

    def _create_message_envelope(
        self,
        fix_message: str,
        message_type: str,
        broker_type: str,
        correlation_id: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create message envelope for FIX message.

        Args:
            fix_message: FIX protocol string.
            message_type: FIX message type.
            broker_type: Target broker type.
            correlation_id: Correlation ID.
            headers: Additional headers.

        Returns:
            Message envelope dictionary.
        """
        envelope = {
            "format": "FIX.4.2",
            "message_type": message_type,
            "broker_type": broker_type,
            "timestamp": datetime.utcnow().isoformat(),
            "fix_message": fix_message,
            "sender": "FXML4",
            "version": "1.0",
        }

        if correlation_id:
            envelope["correlation_id"] = correlation_id

        if headers:
            envelope["headers"] = headers

        return envelope

    def _create_message_properties(
        self,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        expiration_ms: Optional[int] = None,
        headers: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None,
    ) -> pika.BasicProperties:
        """Create message properties for publishing.

        Args:
            priority: Message priority level.
            correlation_id: Correlation ID.
            reply_to: Reply queue name.
            expiration_ms: Message expiration in milliseconds.
            headers: Additional headers.
            message_id: Message ID.

        Returns:
            AMQP basic properties.
        """
        properties = pika.BasicProperties(
            delivery_mode=2,  # Persistent
            content_type="application/json",
            content_encoding="utf-8",
            timestamp=int(datetime.utcnow().timestamp()),
            app_id="FXML4",
            priority=priority.value,
            headers=headers or {},
        )

        if correlation_id:
            properties.correlation_id = correlation_id
        if reply_to:
            properties.reply_to = reply_to
        if expiration_ms:
            properties.expiration = str(expiration_ms)
        if message_id:
            properties.message_id = message_id

        return properties

    def _build_routing_key(self, broker_type: str, suffix: str = "") -> str:
        """Build routing key for message.

        Args:
            broker_type: Target broker type.
            suffix: Optional routing key suffix.

        Returns:
            Complete routing key.
        """
        base_key = f"orders.{broker_type}"
        if suffix:
            return f"{base_key}.{suffix}"
        return base_key

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
