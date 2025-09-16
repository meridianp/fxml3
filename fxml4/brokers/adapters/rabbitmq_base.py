"""Base RabbitMQ Broker Adapter.

This module provides a base class for broker adapters that use RabbitMQ
for message publishing, eliminating code duplication across adapters.
"""

import asyncio
import json
import logging
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ...fix.messages.base import ExecType, OrdStatus
from ...fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest
from ..messaging.connection_manager import (
    RabbitMQConfig,
    RabbitMQConnectionManager,
    create_rabbitmq_manager,
)
from ..messaging.router import MessageRouter
from .base import AdapterConfig, AdapterMetrics, BrokerAdapter, ConnectionStatus

logger = logging.getLogger(__name__)


# Custom exceptions for RabbitMQ operations
class RabbitMQError(Exception):
    """Base exception for RabbitMQ-related errors."""

    pass


class MessageSerializationError(RabbitMQError):
    """Error that occurs during message serialization/deserialization."""

    pass


class QueueManager:
    """Manages RabbitMQ queue operations."""

    def __init__(self, connection_manager: RabbitMQConnectionManager):
        self.connection_manager = connection_manager
        self._queues: Dict[str, Any] = {}

    async def declare_queue(self, queue_name: str, durable: bool = True) -> bool:
        """Declare a queue."""
        try:
            # Implementation would depend on the actual RabbitMQ setup
            self._queues[queue_name] = {"durable": durable, "declared": True}
            return True
        except Exception as e:
            logger.error(f"Failed to declare queue {queue_name}: {e}")
            raise RabbitMQError(f"Queue declaration failed: {e}")

    async def delete_queue(self, queue_name: str) -> bool:
        """Delete a queue."""
        try:
            if queue_name in self._queues:
                del self._queues[queue_name]
            return True
        except Exception as e:
            logger.error(f"Failed to delete queue {queue_name}: {e}")
            raise RabbitMQError(f"Queue deletion failed: {e}")


class ConnectionPool:
    """Manages a pool of RabbitMQ connections."""

    def __init__(self, config: RabbitMQConfig, pool_size: int = 5):
        self.config = config
        self.pool_size = pool_size
        self._connections: List[RabbitMQConnectionManager] = []
        self._available: asyncio.Queue = asyncio.Queue()

    async def initialize(self):
        """Initialize the connection pool."""
        for i in range(self.pool_size):
            manager = RabbitMQConnectionManager(self.config, f"pool_conn_{i}")
            self._connections.append(manager)
            await self._available.put(manager)

    async def get_connection(self) -> RabbitMQConnectionManager:
        """Get an available connection from the pool."""
        return await self._available.get()

    async def return_connection(self, connection: RabbitMQConnectionManager):
        """Return a connection to the pool."""
        await self._available.put(connection)

    async def close_all(self):
        """Close all connections in the pool."""
        while not self._available.empty():
            conn = await self._available.get()
            await conn.disconnect()


class RabbitMQBrokerAdapter(BrokerAdapter):
    """Base class for broker adapters that use RabbitMQ messaging."""

    def __init__(self, config: AdapterConfig, adapter_id: str):
        """Initialize RabbitMQ broker adapter.

        Args:
            config: Adapter configuration.
            adapter_id: Unique identifier for this adapter.
        """
        super().__init__(config)

        self.adapter_id = adapter_id

        # Initialize RabbitMQ connection manager
        self.rabbitmq_manager = create_rabbitmq_manager(
            config.connection_params, adapter_id
        )

        # Set up connection callbacks
        self.rabbitmq_manager.on_connection_open = self._on_rabbitmq_connected
        self.rabbitmq_manager.on_connection_closed = self._on_rabbitmq_disconnected
        self.rabbitmq_manager.on_connection_error = self._on_rabbitmq_error

        # Admin command queue for remote management
        self._admin_command_queue: asyncio.Queue = asyncio.Queue()
        self._admin_task: Optional[asyncio.Task] = None

        # Message publishing metrics
        self.messages_published = 0
        self.publish_errors = 0

        logger.info(f"Initialized RabbitMQ adapter: {adapter_id}")

    async def connect(self) -> bool:
        """Connect to both broker and RabbitMQ."""
        try:
            # Connect to RabbitMQ first
            rabbitmq_connected = await self.rabbitmq_manager.connect()
            if not rabbitmq_connected:
                logger.error(f"Failed to connect {self.adapter_id} to RabbitMQ")
                return False

            # Connect to the actual broker (implemented by subclass)
            broker_connected = await self._connect_to_broker()
            if not broker_connected:
                logger.error(f"Failed to connect {self.adapter_id} to broker")
                await self.rabbitmq_manager.disconnect()
                return False

            # Start admin command processor
            self._admin_task = asyncio.create_task(self._process_admin_commands())

            # Update connection status
            self.connection.status = ConnectionStatus.CONNECTED
            self.connection.connected_at = datetime.now(timezone.utc)

            # Publish initial status
            await self._publish_status_update("connected")

            logger.info(f"Successfully connected {self.adapter_id}")
            return True

        except Exception as e:
            logger.error(f"Error connecting {self.adapter_id}: {e}")
            self.connection.status = ConnectionStatus.ERROR
            self.connection.error_message = str(e)
            return False

    async def disconnect(self):
        """Disconnect from broker and RabbitMQ."""
        try:
            # Publish disconnection status
            await self._publish_status_update("disconnecting")

            # Stop admin command processor
            if self._admin_task:
                self._admin_task.cancel()
                try:
                    await self._admin_task
                except asyncio.CancelledError:
                    pass

            # Disconnect from broker
            await self._disconnect_from_broker()

            # Disconnect from RabbitMQ
            await self.rabbitmq_manager.disconnect()

            # Update connection status
            self.connection.status = ConnectionStatus.DISCONNECTED
            self.connection.connected_at = None

            logger.info(f"Disconnected {self.adapter_id}")

        except Exception as e:
            logger.error(f"Error disconnecting {self.adapter_id}: {e}")

    async def submit_order(self, order: NewOrderSingle) -> str:
        """Submit order and publish event."""
        try:
            # Submit order to broker (implemented by subclass)
            execution_id = await self._submit_order_to_broker(order)

            # Publish order submitted event
            await self._publish_order_event(
                "submitted",
                {
                    "cl_ord_id": order.cl_ord_id,
                    "symbol": order.symbol,
                    "side": (
                        order.side.value
                        if hasattr(order.side, "value")
                        else str(order.side)
                    ),
                    "quantity": order.order_qty,
                    "order_type": (
                        order.ord_type.value
                        if hasattr(order.ord_type, "value")
                        else str(order.ord_type)
                    ),
                    "execution_id": execution_id,
                },
            )

            return execution_id

        except Exception as e:
            # Publish order error event
            await self._publish_order_event(
                "error", {"cl_ord_id": order.cl_ord_id, "error": str(e)}
            )
            raise

    async def cancel_order(self, cl_ord_id: str) -> bool:
        """Cancel order and publish event."""
        try:
            # Cancel order with broker (implemented by subclass)
            success = await self._cancel_order_with_broker(cl_ord_id)

            # Publish cancel event
            await self._publish_order_event(
                "cancel_requested", {"cl_ord_id": cl_ord_id, "success": success}
            )

            return success

        except Exception as e:
            await self._publish_order_event(
                "cancel_error", {"cl_ord_id": cl_ord_id, "error": str(e)}
            )
            raise

    async def get_order_status(self, cl_ord_id: str) -> Optional[Dict[str, Any]]:
        """Get order status (implemented by subclass)."""
        return await self._get_order_status_from_broker(cl_ord_id)

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get open orders (implemented by subclass)."""
        return await self._get_open_orders_from_broker()

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get positions (implemented by subclass)."""
        return await self._get_positions_from_broker()

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information (implemented by subclass)."""
        return await self._get_account_info_from_broker()

    # RabbitMQ event publishing methods
    async def _publish_status_update(
        self, status: str, additional_data: Optional[Dict[str, Any]] = None
    ):
        """Publish adapter status update."""
        status_data = {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "connection_status": self.connection.status.value,
            "metrics": self.metrics.to_dict() if self.metrics else {},
            **(additional_data or {}),
        }

        success = await self.rabbitmq_manager.publish_status_update(status_data)
        if success:
            self.messages_published += 1
        else:
            self.publish_errors += 1

    async def _publish_order_event(self, event_type: str, order_data: Dict[str, Any]):
        """Publish order-related event."""
        success = await self.rabbitmq_manager.publish_order_event(
            event_type, order_data
        )
        if success:
            self.messages_published += 1
        else:
            self.publish_errors += 1

    async def _publish_execution_report(self, execution: ExecutionReport):
        """Publish execution report."""
        execution_data = {
            "cl_ord_id": execution.cl_ord_id,
            "exec_id": execution.exec_id,
            "ord_status": (
                execution.ord_status.value
                if hasattr(execution.ord_status, "value")
                else str(execution.ord_status)
            ),
            "exec_type": (
                execution.exec_type.value
                if hasattr(execution.exec_type, "value")
                else str(execution.exec_type)
            ),
            "symbol": execution.symbol,
            "side": (
                execution.side.value
                if hasattr(execution.side, "value")
                else str(execution.side)
            ),
            "last_qty": getattr(execution, "last_qty", 0),
            "last_px": getattr(execution, "last_px", 0),
            "leaves_qty": getattr(execution, "leaves_qty", 0),
            "cum_qty": getattr(execution, "cum_qty", 0),
            "avg_px": getattr(execution, "avg_px", 0),
            "transact_time": datetime.now(timezone.utc).isoformat(),
        }

        success = await self.rabbitmq_manager.publish_execution_report(execution_data)
        if success:
            self.messages_published += 1
        else:
            self.publish_errors += 1

    # Admin command processing
    async def _process_admin_commands(self):
        """Process administrative commands from RabbitMQ."""
        logger.info(f"Started admin command processor for {self.adapter_id}")

        try:
            while True:
                try:
                    # Wait for admin command (with timeout)
                    command = await asyncio.wait_for(
                        self._admin_command_queue.get(), timeout=30.0
                    )

                    await self._handle_admin_command(command)

                except asyncio.TimeoutError:
                    # Periodic status update
                    await self._publish_status_update("heartbeat")

                except Exception as e:
                    logger.error(
                        f"Error processing admin command for {self.adapter_id}: {e}"
                    )

        except asyncio.CancelledError:
            logger.info(f"Admin command processor stopped for {self.adapter_id}")

    async def _handle_admin_command(self, command: Dict[str, Any]):
        """Handle administrative command."""
        cmd_type = command.get("type")

        try:
            if cmd_type == "status":
                await self._publish_status_update("status_requested")

            elif cmd_type == "reconnect":
                logger.info(f"Reconnect requested for {self.adapter_id}")
                await self.disconnect()
                await asyncio.sleep(1)
                await self.connect()

            elif cmd_type == "cancel_all":
                logger.info(f"Cancel all orders requested for {self.adapter_id}")
                await self._cancel_all_orders()

            elif cmd_type == "health_check":
                health_data = await self._get_health_status()
                await self._publish_status_update("health_check", health_data)

            else:
                logger.warning(
                    f"Unknown admin command for {self.adapter_id}: {cmd_type}"
                )

        except Exception as e:
            logger.error(
                f"Error handling admin command '{cmd_type}' for {self.adapter_id}: {e}"
            )

    async def _cancel_all_orders(self):
        """Cancel all open orders."""
        try:
            open_orders = await self.get_open_orders()
            for order in open_orders:
                cl_ord_id = order.get("cl_ord_id")
                if cl_ord_id:
                    await self.cancel_order(cl_ord_id)

            await self._publish_status_update(
                "all_orders_cancelled", {"cancelled_count": len(open_orders)}
            )

        except Exception as e:
            logger.error(f"Error cancelling all orders for {self.adapter_id}: {e}")

    async def _get_health_status(self) -> Dict[str, Any]:
        """Get adapter health status."""
        return {
            "adapter_id": self.adapter_id,
            "broker_connected": self.connection.is_connected(),
            "rabbitmq_connected": self.rabbitmq_manager.connected,
            "messages_published": self.messages_published,
            "publish_errors": self.publish_errors,
            "publish_success_rate": (
                (
                    self.messages_published
                    / (self.messages_published + self.publish_errors)
                )
                * 100
                if (self.messages_published + self.publish_errors) > 0
                else 100
            ),
            "uptime_seconds": (
                (
                    datetime.now(timezone.utc) - self.connection.connected_at
                ).total_seconds()
                if self.connection.connected_at
                else 0
            ),
        }

    # RabbitMQ connection callbacks
    async def _on_rabbitmq_connected(self):
        """Called when RabbitMQ connection is established."""
        logger.info(f"RabbitMQ connected for {self.adapter_id}")

    async def _on_rabbitmq_disconnected(self):
        """Called when RabbitMQ connection is closed."""
        logger.warning(f"RabbitMQ disconnected for {self.adapter_id}")

    async def _on_rabbitmq_error(self, error: Exception):
        """Called when RabbitMQ connection error occurs."""
        logger.error(f"RabbitMQ error for {self.adapter_id}: {error}")

    # Abstract methods to be implemented by subclasses
    @abstractmethod
    async def _connect_to_broker(self) -> bool:
        """Connect to the actual broker (implemented by subclass)."""
        pass

    @abstractmethod
    async def _disconnect_from_broker(self):
        """Disconnect from the broker (implemented by subclass)."""
        pass

    @abstractmethod
    async def _submit_order_to_broker(self, order: NewOrderSingle) -> str:
        """Submit order to broker (implemented by subclass)."""
        pass

    @abstractmethod
    async def _cancel_order_with_broker(self, cl_ord_id: str) -> bool:
        """Cancel order with broker (implemented by subclass)."""
        pass

    @abstractmethod
    async def _get_order_status_from_broker(
        self, cl_ord_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get order status from broker (implemented by subclass)."""
        pass

    @abstractmethod
    async def _get_open_orders_from_broker(self) -> List[Dict[str, Any]]:
        """Get open orders from broker (implemented by subclass)."""
        pass

    @abstractmethod
    async def _get_positions_from_broker(self) -> List[Dict[str, Any]]:
        """Get positions from broker (implemented by subclass)."""
        pass

    @abstractmethod
    async def _get_account_info_from_broker(self) -> Dict[str, Any]:
        """Get account info from broker (implemented by subclass)."""
        pass
