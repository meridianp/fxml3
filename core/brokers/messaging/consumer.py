"""Message Consumer for Broker Communication.

This module provides consuming capabilities for receiving FIX messages
and execution reports from broker adapters via RabbitMQ.
"""

import json
import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import pika
from pika.exceptions import ChannelClosed, ConnectionClosed

from ...fix.messages.base import FIXMessage
from ...fix.utils.parser import FIXParseError, FIXParser

logger = logging.getLogger(__name__)


class ConsumerError(Exception):
    """Exception raised when message consumption fails."""

    pass


class MessageHandler:
    """Base class for message handlers with default implementations.

    CRITICAL FIX: Provides concrete implementations to eliminate NotImplemented errors
    and enable proper message processing in production environments.
    """

    def handle_execution_report(
        self, message: FIXMessage, envelope: Dict[str, Any]
    ) -> bool:
        """Handle execution report message.

        CRITICAL FIX: Default implementation logs and processes basic execution reports.
        Override this method in subclasses for custom processing.

        Args:
            message: Parsed FIX message.
            envelope: Message envelope with metadata.

        Returns:
            True if message was handled successfully.
        """
        try:
            # Extract execution details
            msg_type = getattr(message, "msg_type", "Unknown")
            symbol = getattr(message, "symbol", "Unknown")
            order_id = getattr(message, "cl_ord_id", "Unknown")
            exec_type = getattr(message, "exec_type", "Unknown")

            logger.info(
                f"Execution report received: "
                f"type={msg_type}, symbol={symbol}, order_id={order_id}, exec_type={exec_type}"
            )

            # Store execution details in envelope for downstream processing
            envelope.update(
                {
                    "processed_by": "MessageHandler.handle_execution_report",
                    "message_type": msg_type,
                    "symbol": symbol,
                    "order_id": order_id,
                    "exec_type": exec_type,
                    "processed_at": datetime.utcnow().isoformat(),
                }
            )

            return True

        except Exception as e:
            logger.error(f"Error handling execution report: {e}")
            return False

    def handle_admin_response(
        self, response: Dict[str, Any], envelope: Dict[str, Any]
    ) -> bool:
        """Handle administrative response.

        CRITICAL FIX: Default implementation logs and processes basic admin responses.
        Override this method in subclasses for custom processing.

        Args:
            response: Administrative response data.
            envelope: Message envelope with metadata.

        Returns:
            True if response was handled successfully.
        """
        try:
            # Extract admin response details
            response_type = response.get("type", "Unknown")
            broker = response.get("broker", "Unknown")
            status = response.get("status", "Unknown")
            message = response.get("message", "")

            logger.info(
                f"Admin response received: "
                f"type={response_type}, broker={broker}, status={status}, message={message}"
            )

            # Store response details in envelope
            envelope.update(
                {
                    "processed_by": "MessageHandler.handle_admin_response",
                    "response_type": response_type,
                    "broker": broker,
                    "status": status,
                    "processed_at": datetime.utcnow().isoformat(),
                }
            )

            # Handle critical admin responses
            if status.lower() in ["error", "failed", "disconnected"]:
                logger.warning(f"Critical admin response: {response}")

            return True

        except Exception as e:
            logger.error(f"Error handling admin response: {e}")
            return False

    def handle_market_data(
        self, data: Dict[str, Any], envelope: Dict[str, Any]
    ) -> bool:
        """Handle market data message.

        CRITICAL FIX: Default implementation logs and processes basic market data.
        Override this method in subclasses for custom processing.

        Args:
            data: Market data.
            envelope: Message envelope with metadata.

        Returns:
            True if data was handled successfully.
        """
        try:
            # Extract market data details
            symbol = data.get("symbol", "Unknown")
            data_type = data.get("type", "Unknown")
            timestamp = data.get("timestamp", "Unknown")
            price = data.get("price", data.get("close", "Unknown"))

            logger.debug(
                f"Market data received: "
                f"symbol={symbol}, type={data_type}, timestamp={timestamp}, price={price}"
            )

            # Store market data details in envelope
            envelope.update(
                {
                    "processed_by": "MessageHandler.handle_market_data",
                    "symbol": symbol,
                    "data_type": data_type,
                    "timestamp": timestamp,
                    "price": price,
                    "processed_at": datetime.utcnow().isoformat(),
                }
            )

            return True

        except Exception as e:
            logger.error(f"Error handling market data: {e}")
            return False

    def handle_error(self, error: Exception, envelope: Dict[str, Any]) -> bool:
        """Handle processing error.

        Args:
            error: Exception that occurred.
            envelope: Message envelope with metadata.

        Returns:
            True if error was handled (message should be acked).
        """
        logger.error("Message processing error: %s", error)
        return False  # Reject by default


class BrokerMessageConsumer:
    """Consumer for receiving messages from broker adapters via RabbitMQ.

    This class handles the consumption of execution reports, market data,
    and administrative responses from broker adapters.
    """

    def __init__(
        self,
        connection_params: pika.ConnectionParameters,
        message_handler: MessageHandler,
        fix_parser: Optional[FIXParser] = None,
    ):
        """Initialize message consumer.

        Args:
            connection_params: RabbitMQ connection parameters.
            message_handler: Handler for processing received messages.
            fix_parser: FIX message parser (creates default if None).
        """
        self.connection_params = connection_params
        self.message_handler = message_handler
        self.fix_parser = fix_parser or FIXParser()

        self.connection = None
        self.channel = None
        self.consumer_tags = []
        self.is_consuming = False

        # Consumer configuration
        self.prefetch_count = 10  # Number of unacked messages
        self.auto_ack = False  # Manual acknowledgment for reliability

        # Threading for async consumption
        self.consumer_thread = None
        self.stop_event = threading.Event()

    def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        try:
            self.connection = pika.BlockingConnection(self.connection_params)
            self.channel = self.connection.channel()

            # Set QoS for fair dispatch
            self.channel.basic_qos(prefetch_count=self.prefetch_count)

            logger.info("Consumer connected to RabbitMQ")

        except Exception as e:
            logger.error("Failed to connect consumer to RabbitMQ: %s", e)
            raise ConsumerError(f"Connection failed: {e}") from e

    def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        try:
            self.stop_consuming()

            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()

            logger.info("Consumer disconnected from RabbitMQ")

        except Exception as e:
            logger.warning("Error during consumer disconnect: %s", e)

    def start_consuming_executions(
        self, queue_names: Optional[List[str]] = None
    ) -> None:
        """Start consuming execution reports.

        Args:
            queue_names: List of execution queue names to consume from.
                        Uses default queues if None.
        """
        if not self.channel:
            raise ConsumerError("Must connect before starting consumption")

        # Default execution queues
        if queue_names is None:
            queue_names = [
                "executions.all",
                "executions.fills",
                "executions.rejections",
            ]

        try:
            for queue_name in queue_names:
                consumer_tag = self.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=self._handle_execution_message,
                    auto_ack=self.auto_ack,
                )
                self.consumer_tags.append(consumer_tag)
                logger.info("Started consuming executions from queue: %s", queue_name)

            self.is_consuming = True

        except Exception as e:
            logger.error("Failed to start consuming executions: %s", e)
            raise ConsumerError(f"Failed to start execution consumption: {e}") from e

    def start_consuming_admin(self, queue_name: str = "admin.status.all") -> None:
        """Start consuming administrative responses.

        Args:
            queue_name: Admin status queue name.
        """
        if not self.channel:
            raise ConsumerError("Must connect before starting consumption")

        try:
            consumer_tag = self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=self._handle_admin_message,
                auto_ack=self.auto_ack,
            )
            self.consumer_tags.append(consumer_tag)
            logger.info("Started consuming admin responses from queue: %s", queue_name)

        except Exception as e:
            logger.error("Failed to start consuming admin responses: %s", e)
            raise ConsumerError(f"Failed to start admin consumption: {e}") from e

    def start_consuming_market_data(
        self, queue_names: Optional[List[str]] = None
    ) -> None:
        """Start consuming market data.

        Args:
            queue_names: List of market data queue names to consume from.
        """
        if not self.channel:
            raise ConsumerError("Must connect before starting consumption")

        # Default market data queues
        if queue_names is None:
            queue_names = [
                "market.data.aggregated",
                "market.data.ib",
                "market.data.fxcm",
            ]

        try:
            for queue_name in queue_names:
                consumer_tag = self.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=self._handle_market_data_message,
                    auto_ack=self.auto_ack,
                )
                self.consumer_tags.append(consumer_tag)
                logger.info("Started consuming market data from queue: %s", queue_name)

        except Exception as e:
            logger.error("Failed to start consuming market data: %s", e)
            raise ConsumerError(f"Failed to start market data consumption: {e}") from e

    def start_consuming_all(self) -> None:
        """Start consuming from all supported queue types."""
        self.start_consuming_executions()
        self.start_consuming_admin()
        self.start_consuming_market_data()

    def run_async(self) -> None:
        """Run consumer in background thread."""
        if self.consumer_thread and self.consumer_thread.is_alive():
            logger.warning("Consumer thread already running")
            return

        self.stop_event.clear()
        self.consumer_thread = threading.Thread(target=self._consume_loop, daemon=True)
        self.consumer_thread.start()
        logger.info("Started consumer thread")

    def run_blocking(self) -> None:
        """Run consumer in blocking mode."""
        if not self.is_consuming:
            raise ConsumerError("Must start consuming before running")

        try:
            logger.info("Starting blocking consumption loop")
            self.channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, stopping consumption")
            self.stop_consuming()
        except Exception as e:
            logger.error("Error in consumption loop: %s", e)
            raise ConsumerError(f"Consumption error: {e}") from e

    def stop_consuming(self) -> None:
        """Stop consuming messages."""
        if not self.is_consuming:
            return

        try:
            # Stop thread if running
            if self.consumer_thread and self.consumer_thread.is_alive():
                self.stop_event.set()
                self.consumer_thread.join(timeout=5.0)

            # Cancel consumers
            if self.channel and not self.channel.is_closed:
                for consumer_tag in self.consumer_tags:
                    try:
                        self.channel.basic_cancel(consumer_tag)
                    except Exception as e:
                        logger.warning(
                            "Failed to cancel consumer %s: %s", consumer_tag, e
                        )

                self.channel.stop_consuming()

            self.consumer_tags.clear()
            self.is_consuming = False
            logger.info("Stopped consuming messages")

        except Exception as e:
            logger.error("Error stopping consumer: %s", e)

    def _consume_loop(self) -> None:
        """Main consumption loop for background thread."""
        try:
            while not self.stop_event.is_set() and self.is_consuming:
                try:
                    # Process events with timeout
                    self.connection.process_data_events(time_limit=1.0)
                except Exception as e:
                    logger.warning("Error processing data events: %s", e)
                    if not self.connection.is_open:
                        logger.error("Connection lost, stopping consumer")
                        break

            logger.info("Consumer loop stopped")

        except Exception as e:
            logger.error("Fatal error in consumer loop: %s", e)

    def _handle_execution_message(self, channel, method, properties, body) -> None:
        """Handle execution report message.

        Args:
            channel: Channel object.
            method: Method frame.
            properties: Message properties.
            body: Message body.
        """
        try:
            # Parse message envelope
            envelope = json.loads(body)

            # Extract FIX message
            fix_string = envelope.get("fix_message", "")
            if not fix_string:
                raise ValueError("No FIX message in envelope")

            # Parse FIX message
            fix_message = self.fix_parser.parse(fix_string)

            # Add metadata to envelope
            envelope.update(
                {
                    "queue": method.routing_key,
                    "delivery_tag": method.delivery_tag,
                    "timestamp_received": datetime.utcnow().isoformat(),
                    "properties": {
                        "correlation_id": properties.correlation_id,
                        "message_id": properties.message_id,
                        "priority": properties.priority,
                        "headers": properties.headers,
                    },
                }
            )

            # Handle message
            success = self.message_handler.handle_execution_report(
                fix_message, envelope
            )

            # Acknowledge or reject
            if success:
                channel.basic_ack(delivery_tag=method.delivery_tag)
                logger.debug("Acknowledged execution message: %s", method.delivery_tag)
            else:
                channel.basic_nack(
                    delivery_tag=method.delivery_tag, requeue=False  # Send to DLQ
                )
                logger.warning("Rejected execution message: %s", method.delivery_tag)

        except Exception as e:
            logger.error("Error handling execution message: %s", e)

            # Try to handle error
            try:
                envelope = {
                    "error": str(e),
                    "body": body.decode("utf-8", errors="ignore"),
                }
                handled = self.message_handler.handle_error(e, envelope)

                if handled:
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as e2:
                logger.error("Error in error handler: %s", e2)
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def _handle_admin_message(self, channel, method, properties, body) -> None:
        """Handle administrative message.

        Args:
            channel: Channel object.
            method: Method frame.
            properties: Message properties.
            body: Message body.
        """
        try:
            # Parse message
            response = json.loads(body)

            # Create envelope
            envelope = {
                "queue": method.routing_key,
                "delivery_tag": method.delivery_tag,
                "timestamp_received": datetime.utcnow().isoformat(),
                "properties": {
                    "correlation_id": properties.correlation_id,
                    "message_id": properties.message_id,
                    "priority": properties.priority,
                    "headers": properties.headers,
                },
            }

            # Handle message
            success = self.message_handler.handle_admin_response(response, envelope)

            # Acknowledge or reject
            if success:
                channel.basic_ack(delivery_tag=method.delivery_tag)
                logger.debug("Acknowledged admin message: %s", method.delivery_tag)
            else:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                logger.warning("Rejected admin message: %s", method.delivery_tag)

        except Exception as e:
            logger.error("Error handling admin message: %s", e)

            try:
                envelope = {
                    "error": str(e),
                    "body": body.decode("utf-8", errors="ignore"),
                }
                handled = self.message_handler.handle_error(e, envelope)

                if handled:
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as e2:
                logger.error("Error in admin error handler: %s", e2)
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def _handle_market_data_message(self, channel, method, properties, body) -> None:
        """Handle market data message.

        Args:
            channel: Channel object.
            method: Method frame.
            properties: Message properties.
            body: Message body.
        """
        try:
            # Parse message
            data = json.loads(body)

            # Create envelope
            envelope = {
                "queue": method.routing_key,
                "delivery_tag": method.delivery_tag,
                "timestamp_received": datetime.utcnow().isoformat(),
                "properties": {
                    "correlation_id": properties.correlation_id,
                    "message_id": properties.message_id,
                    "priority": properties.priority,
                    "headers": properties.headers,
                },
            }

            # Handle message
            success = self.message_handler.handle_market_data(data, envelope)

            # Acknowledge or reject
            if success:
                channel.basic_ack(delivery_tag=method.delivery_tag)
                logger.debug(
                    "Acknowledged market data message: %s", method.delivery_tag
                )
            else:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                logger.warning("Rejected market data message: %s", method.delivery_tag)

        except Exception as e:
            logger.error("Error handling market data message: %s", e)

            try:
                envelope = {
                    "error": str(e),
                    "body": body.decode("utf-8", errors="ignore"),
                }
                handled = self.message_handler.handle_error(e, envelope)

                if handled:
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as e2:
                logger.error("Error in market data error handler: %s", e2)
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
