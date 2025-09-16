"""FIX Protocol RabbitMQ Broker Adapter.

This adapter provides FIX protocol connectivity with RabbitMQ messaging integration,
allowing FIX orders to be submitted via message queues and execution reports to be
published for downstream consumption.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...fix.messages.base import ExecType, OrdStatus, OrdType, Side
from ...fix.messages.market_data import MarketDataRequest
from ...fix.messages.order_modify import OrderCancelReplaceRequest
from ...fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest
from .base import AdapterConfig, ConnectionStatus
from .fix_adapter import FixBrokerAdapter
from .rabbitmq_base import RabbitMQBrokerAdapter

logger = logging.getLogger(__name__)


class FixRabbitMQAdapter(RabbitMQBrokerAdapter):
    """FIX Protocol broker adapter with RabbitMQ integration."""

    def __init__(self, config: AdapterConfig):
        """Initialize FIX RabbitMQ adapter.

        Args:
            config: Adapter configuration containing FIX and RabbitMQ settings.
        """
        # Initialize RabbitMQ base with adapter ID
        super().__init__(config, "fix")

        # Initialize FIX adapter
        self.fix_adapter = FixBrokerAdapter(config)

        # Message processing
        self._message_handlers = {
            "new_order": self._handle_new_order_message,
            "cancel_order": self._handle_cancel_order_message,
            "modify_order": self._handle_modify_order_message,
            "market_data_request": self._handle_market_data_request,
            "order_status_request": self._handle_order_status_request,
        }

        # Track orders for RabbitMQ correlation
        self.order_tracking: Dict[str, Dict[str, Any]] = {}

        # Market data subscriptions
        self.market_data_subscriptions: Dict[str, MarketDataRequest] = {}

        logger.info("Initialized FIX RabbitMQ adapter")

    async def _connect_to_broker(self) -> bool:
        """Connect to FIX server."""
        try:
            success = await self.fix_adapter.connect()
            if success:
                # Start message consumption from RabbitMQ
                await self._start_message_consumption()

                # Set up execution report forwarding
                self.fix_adapter.execution_callback = self._handle_execution_report
                self.fix_adapter.market_data_callback = self._handle_market_data_update

                logger.info("Connected to FIX broker via RabbitMQ adapter")
            return success

        except Exception as e:
            logger.error(f"Failed to connect FIX RabbitMQ adapter: {e}")
            return False

    async def _disconnect_from_broker(self):
        """Disconnect from FIX server."""
        try:
            await self.fix_adapter.disconnect()
            logger.info("Disconnected from FIX broker")
        except Exception as e:
            logger.error(f"Error disconnecting FIX adapter: {e}")

    async def _submit_order_to_broker(self, order: NewOrderSingle) -> str:
        """Submit order to FIX broker.

        Args:
            order: Order to submit.

        Returns:
            Execution ID for tracking.
        """
        try:
            execution_id = await self.fix_adapter.submit_order(order)

            # Track order for correlation
            self.order_tracking[order.cl_ord_id] = {
                "execution_id": execution_id,
                "order": order,
                "submit_time": datetime.now(timezone.utc),
                "status": "submitted",
            }

            return execution_id

        except Exception as e:
            logger.error(f"Failed to submit order to FIX broker: {e}")
            raise

    async def _cancel_order_with_broker(self, cl_ord_id: str) -> bool:
        """Cancel order with FIX broker.

        Args:
            cl_ord_id: Client order ID to cancel.

        Returns:
            True if cancel request sent successfully.
        """
        try:
            # Get original order info
            order_info = self.order_tracking.get(cl_ord_id)
            if not order_info:
                logger.warning(f"Order {cl_ord_id} not found for cancellation")
                return False

            original_order = order_info["order"]

            # Create cancel request
            cancel_request = OrderCancelRequest(
                orig_cl_ord_id=cl_ord_id,
                cl_ord_id=f"CANCEL_{uuid.uuid4().hex[:8].upper()}",
                symbol=original_order.symbol,
                side=original_order.side,
            )

            success = await self.fix_adapter.cancel_order(cancel_request)

            if success:
                # Update tracking
                order_info["status"] = "cancel_requested"
                order_info["cancel_time"] = datetime.now(timezone.utc)

            return success

        except Exception as e:
            logger.error(f"Failed to cancel order {cl_ord_id}: {e}")
            return False

    async def _get_order_status_from_broker(
        self, cl_ord_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get order status from tracking.

        Args:
            cl_ord_id: Client order ID.

        Returns:
            Order status data or None.
        """
        order_info = self.order_tracking.get(cl_ord_id)
        if not order_info:
            return None

        return {
            "cl_ord_id": cl_ord_id,
            "execution_id": order_info["execution_id"],
            "status": order_info["status"],
            "submit_time": order_info["submit_time"].isoformat(),
            "cancel_time": (
                order_info.get("cancel_time", {}).isoformat()
                if order_info.get("cancel_time")
                else None
            ),
            "last_update": order_info.get(
                "last_update", datetime.now(timezone.utc)
            ).isoformat(),
        }

    async def _get_open_orders_from_broker(self) -> List[Dict[str, Any]]:
        """Get open orders from tracking.

        Returns:
            List of open order data.
        """
        open_orders = []

        for cl_ord_id, order_info in self.order_tracking.items():
            status = order_info.get("status", "unknown")
            if status not in ["filled", "cancelled", "rejected"]:
                order_data = await self._get_order_status_from_broker(cl_ord_id)
                if order_data:
                    open_orders.append(order_data)

        return open_orders

    async def _get_positions_from_broker(self) -> List[Dict[str, Any]]:
        """Get positions (FIX doesn't maintain positions directly).

        Returns:
            Empty list (positions tracked separately).
        """
        # FIX protocol doesn't maintain positions directly
        # This would need to be calculated from execution reports
        return []

    async def _get_account_info_from_broker(self) -> Dict[str, Any]:
        """Get account information from FIX adapter.

        Returns:
            Account information.
        """
        return {
            "adapter_type": "fix",
            "session_id": (
                self.fix_adapter.session.session_id
                if self.fix_adapter.session
                else None
            ),
            "connected": self.fix_adapter._is_ready(),
            "total_orders": len(self.order_tracking),
            "open_orders": len(await self._get_open_orders_from_broker()),
            "session_stats": (
                self.fix_adapter.session.stats.to_dict()
                if self.fix_adapter.session
                else {}
            ),
        }

    # Message handling methods
    async def _start_message_consumption(self):
        """Start consuming messages from RabbitMQ queues."""
        try:
            # Set up message handlers with RabbitMQ manager
            for message_type, handler in self._message_handlers.items():
                await self.rabbitmq_manager.register_handler(message_type, handler)

            logger.info("Started FIX message consumption from RabbitMQ")

        except Exception as e:
            logger.error(f"Failed to start message consumption: {e}")
            raise

    async def _handle_new_order_message(
        self, message: Dict[str, Any], delivery_tag: str
    ):
        """Handle new order message from RabbitMQ.

        Args:
            message: Order message data.
            delivery_tag: RabbitMQ delivery tag for acknowledgment.
        """
        try:
            # Parse order data
            order_data = message.get("order", {})

            # Create NewOrderSingle
            order = NewOrderSingle(
                cl_ord_id=order_data.get(
                    "cl_ord_id", f"FIX_{uuid.uuid4().hex[:8].upper()}"
                ),
                symbol=order_data["symbol"],
                side=Side(order_data["side"]),
                order_qty=float(order_data["quantity"]),
                ord_type=OrdType(order_data.get("order_type", "MARKET")),
            )

            # Add optional fields
            if "price" in order_data:
                order.price = float(order_data["price"])
            if "time_in_force" in order_data:
                order.time_in_force = order_data["time_in_force"]

            # Submit order
            execution_id = await self.submit_order(order)

            # Acknowledge message
            await self.rabbitmq_manager.ack_message(delivery_tag)

            logger.info(
                f"Processed new order message: {order.cl_ord_id} -> {execution_id}"
            )

        except Exception as e:
            logger.error(f"Error processing new order message: {e}")
            # Reject message
            await self.rabbitmq_manager.reject_message(delivery_tag, requeue=False)

    async def _handle_cancel_order_message(
        self, message: Dict[str, Any], delivery_tag: str
    ):
        """Handle cancel order message from RabbitMQ."""
        try:
            cl_ord_id = message.get("cl_ord_id")
            if not cl_ord_id:
                raise ValueError("Missing cl_ord_id in cancel message")

            success = await self.cancel_order(cl_ord_id)

            # Acknowledge message
            await self.rabbitmq_manager.ack_message(delivery_tag)

            logger.info(
                f"Processed cancel order message: {cl_ord_id}, success: {success}"
            )

        except Exception as e:
            logger.error(f"Error processing cancel order message: {e}")
            await self.rabbitmq_manager.reject_message(delivery_tag, requeue=False)

    async def _handle_modify_order_message(
        self, message: Dict[str, Any], delivery_tag: str
    ):
        """Handle modify order message from RabbitMQ."""
        try:
            # Get modification data
            orig_cl_ord_id = message.get("orig_cl_ord_id")
            if not orig_cl_ord_id:
                raise ValueError("Missing orig_cl_ord_id in modify message")

            # Get original order
            order_info = self.order_tracking.get(orig_cl_ord_id)
            if not order_info:
                raise ValueError(f"Original order {orig_cl_ord_id} not found")

            original_order = order_info["order"]

            # Create modify request
            modify_request = OrderCancelReplaceRequest(
                orig_cl_ord_id=orig_cl_ord_id,
                cl_ord_id=f"MOD_{uuid.uuid4().hex[:8].upper()}",
                symbol=original_order.symbol,
                side=original_order.side,
                order_qty=float(message.get("quantity", original_order.order_qty)),
                ord_type=OrdType(message.get("order_type", original_order.ord_type)),
            )

            # Add modified fields
            if "price" in message:
                modify_request.price = float(message["price"])
            if "time_in_force" in message:
                modify_request.time_in_force = message["time_in_force"]

            # Submit modification
            success = await self.fix_adapter.modify_order(modify_request)

            if success:
                # Update tracking
                order_info["status"] = "modify_requested"
                order_info["modify_time"] = datetime.now(timezone.utc)

            # Acknowledge message
            await self.rabbitmq_manager.ack_message(delivery_tag)

            logger.info(
                f"Processed modify order message: {orig_cl_ord_id}, success: {success}"
            )

        except Exception as e:
            logger.error(f"Error processing modify order message: {e}")
            await self.rabbitmq_manager.reject_message(delivery_tag, requeue=False)

    async def _handle_market_data_request(
        self, message: Dict[str, Any], delivery_tag: str
    ):
        """Handle market data request from RabbitMQ."""
        try:
            # Parse market data request
            symbols = message.get("symbols", [])
            md_req_id = message.get("md_req_id", f"MD_{uuid.uuid4().hex[:8].upper()}")
            subscription_type = message.get(
                "subscription_type", "1"
            )  # 1=Snapshot+Updates

            # Create market data request
            md_request = MarketDataRequest(
                md_req_id=md_req_id,
                subscription_request_type=subscription_type,
                market_depth=int(message.get("market_depth", 1)),
                symbols=symbols,
            )

            # Submit request
            success = await self.fix_adapter.request_market_data(md_request)

            if success:
                # Track subscription
                self.market_data_subscriptions[md_req_id] = md_request

            # Acknowledge message
            await self.rabbitmq_manager.ack_message(delivery_tag)

            logger.info(
                f"Processed market data request: {md_req_id}, symbols: {symbols}"
            )

        except Exception as e:
            logger.error(f"Error processing market data request: {e}")
            await self.rabbitmq_manager.reject_message(delivery_tag, requeue=False)

    async def _handle_order_status_request(
        self, message: Dict[str, Any], delivery_tag: str
    ):
        """Handle order status request from RabbitMQ."""
        try:
            cl_ord_id = message.get("cl_ord_id")
            if not cl_ord_id:
                raise ValueError("Missing cl_ord_id in status request")

            # Get status
            status = await self.get_order_status(cl_ord_id)

            # Publish status response
            await self._publish_order_event(
                "status_response", {"cl_ord_id": cl_ord_id, "status": status}
            )

            # Acknowledge message
            await self.rabbitmq_manager.ack_message(delivery_tag)

            logger.info(f"Processed order status request: {cl_ord_id}")

        except Exception as e:
            logger.error(f"Error processing order status request: {e}")
            await self.rabbitmq_manager.reject_message(delivery_tag, requeue=False)

    # Callback methods for FIX adapter
    async def _handle_execution_report(self, execution: ExecutionReport):
        """Handle execution report from FIX adapter.

        Args:
            execution: Execution report from FIX.
        """
        try:
            # Update order tracking
            if execution.cl_ord_id in self.order_tracking:
                order_info = self.order_tracking[execution.cl_ord_id]
                order_info["status"] = execution.ord_status.value
                order_info["last_update"] = datetime.now(timezone.utc)

                # Add execution details
                if not "executions" in order_info:
                    order_info["executions"] = []

                order_info["executions"].append(
                    {
                        "exec_id": execution.exec_id,
                        "exec_type": execution.exec_type.value,
                        "ord_status": execution.ord_status.value,
                        "last_qty": getattr(execution, "last_qty", 0),
                        "last_px": getattr(execution, "last_px", 0),
                        "cum_qty": getattr(execution, "cum_qty", 0),
                        "leaves_qty": getattr(execution, "leaves_qty", 0),
                        "avg_px": getattr(execution, "avg_px", 0),
                        "transact_time": getattr(
                            execution, "transact_time", datetime.now(timezone.utc)
                        ).isoformat(),
                    }
                )

            # Publish execution report via RabbitMQ
            await self._publish_execution_report(execution)

            logger.info(
                f"Processed execution report: {execution.cl_ord_id} - {execution.ord_status.name}"
            )

        except Exception as e:
            logger.error(f"Error handling execution report: {e}")

    async def _handle_market_data_update(self, md_update: Dict[str, Any]):
        """Handle market data update from FIX adapter.

        Args:
            md_update: Market data update.
        """
        try:
            # Publish market data via RabbitMQ
            await self.rabbitmq_manager.publish_market_data(md_update)

            logger.debug(
                f"Published market data update: {md_update.get('symbol', 'unknown')}"
            )

        except Exception as e:
            logger.error(f"Error handling market data update: {e}")

    # Additional administrative methods
    async def modify_order(self, modify_request: OrderCancelReplaceRequest) -> bool:
        """Modify existing order.

        Args:
            modify_request: Order modification request.

        Returns:
            True if modification sent successfully.
        """
        try:
            success = await self.fix_adapter.modify_order(modify_request)

            # Publish modify event
            await self._publish_order_event(
                "modify_requested",
                {
                    "orig_cl_ord_id": modify_request.orig_cl_ord_id,
                    "new_cl_ord_id": modify_request.cl_ord_id,
                    "success": success,
                },
            )

            return success

        except Exception as e:
            logger.error(f"Failed to modify order: {e}")
            await self._publish_order_event(
                "modify_error",
                {"orig_cl_ord_id": modify_request.orig_cl_ord_id, "error": str(e)},
            )
            return False

    async def request_market_data(self, md_request: MarketDataRequest) -> bool:
        """Request market data subscription.

        Args:
            md_request: Market data request.

        Returns:
            True if request sent successfully.
        """
        try:
            success = await self.fix_adapter.request_market_data(md_request)

            if success:
                self.market_data_subscriptions[md_request.md_req_id] = md_request

            # Publish market data event
            await self._publish_order_event(
                "market_data_requested",
                {
                    "md_req_id": md_request.md_req_id,
                    "symbols": md_request.symbols,
                    "success": success,
                },
            )

            return success

        except Exception as e:
            logger.error(f"Failed to request market data: {e}")
            return False

    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive adapter metrics.

        Returns:
            Adapter metrics including FIX and RabbitMQ stats.
        """
        base_metrics = await self._get_health_status()

        # Add FIX-specific metrics
        fix_metrics = {}
        if self.fix_adapter.session:
            fix_metrics = {
                "session_stats": self.fix_adapter.session.stats.to_dict(),
                "sequence_numbers": {
                    "sent": self.fix_adapter.session.sent_seq_num,
                    "received": self.fix_adapter.session.received_seq_num,
                },
            }

        # Add order tracking metrics
        order_metrics = {
            "total_orders_tracked": len(self.order_tracking),
            "market_data_subscriptions": len(self.market_data_subscriptions),
            "order_status_breakdown": {},
        }

        # Count orders by status
        status_counts = {}
        for order_info in self.order_tracking.values():
            status = order_info.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        order_metrics["order_status_breakdown"] = status_counts

        return {
            **base_metrics,
            "fix_metrics": fix_metrics,
            "order_metrics": order_metrics,
        }
