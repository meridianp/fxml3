"""Manual Execution Broker Adapter.

This adapter provides human-in-the-loop order approval and execution,
allowing manual review and override of automated trading decisions.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ...fix.messages.base import ExecType, FIXMessage, OrdStatus
from ...fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest
from ...fix.utils.builder import FIXMessageBuilder
from .base import AdapterConfig, AdapterMetrics, BrokerAdapter, ConnectionStatus

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Order approval status."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"
    EXPIRED = "EXPIRED"


@dataclass
class PendingOrder:
    """Represents an order pending manual approval."""

    order_id: str
    cl_ord_id: str
    order: NewOrderSingle
    received_time: datetime
    approval_status: ApprovalStatus
    reviewer: Optional[str] = None
    review_time: Optional[datetime] = None
    notes: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None
    risk_overrides: Optional[Dict[str, Any]] = None


class ManualBrokerAdapter(BrokerAdapter):
    """Manual execution broker adapter implementation.

    This adapter queues orders for human review and approval through
    a web interface, providing compliance and risk management capabilities.
    """

    def __init__(self, config: AdapterConfig):
        """Initialize manual adapter.

        Args:
            config: Adapter configuration.
        """
        super().__init__(config)

        # Pending orders queue
        self.pending_orders: Dict[str, PendingOrder] = {}
        self.order_history: List[PendingOrder] = []

        # WebSocket connections for real-time updates
        self.websocket_clients: Set[Any] = set()

        # Approval settings
        self.auto_reject_timeout = config.features.get(
            "auto_reject_timeout", 300
        )  # 5 minutes
        self.require_two_factor = config.features.get("require_two_factor", False)
        self.approval_levels = config.features.get("approval_levels", {})

        # Risk override capabilities
        self.allow_risk_override = config.features.get("allow_risk_override", True)
        self.max_override_amount = config.limits.get("max_override_amount", 10000000)

        # Audit trail
        self.audit_enabled = config.features.get("audit_trail", True)

        # Mock execution simulator
        self.simulate_execution = config.features.get("simulate_execution", True)
        self.simulated_fill_delay = config.features.get("simulated_fill_delay", 2)

        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(
            f"Initialized manual adapter with auto-reject timeout: {self.auto_reject_timeout}s"
        )

    async def connect(self) -> bool:
        """Connect manual adapter (always available).

        Returns:
            True since manual adapter is always ready.
        """
        try:
            logger.info("Connecting manual adapter...")

            # Manual adapter is always connected
            self.connection.status = ConnectionStatus.READY
            self.connection._connected = True
            self.connection._authenticated = True

            # Start cleanup task for expired orders
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_orders())

            # Update metrics
            self.metrics.last_connect_time = datetime.utcnow()

            logger.info("Manual adapter connected and ready")
            return True

        except Exception as e:
            logger.error(f"Failed to connect manual adapter: {e}")
            self.connection.status = ConnectionStatus.ERROR
            self.connection.error = str(e)
            return False

    async def disconnect(self) -> None:
        """Disconnect manual adapter."""
        try:
            logger.info("Disconnecting manual adapter...")

            # Cancel cleanup task
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass

            # Clear pending orders
            self.pending_orders.clear()
            self.websocket_clients.clear()

            # Update connection status
            self.connection.status = ConnectionStatus.DISCONNECTED
            self.connection._connected = False
            self.connection._authenticated = False

            # Update metrics
            self.metrics.last_disconnect_time = datetime.utcnow()

            logger.info("Manual adapter disconnected")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def submit_order(self, order: NewOrderSingle) -> str:
        """Submit order for manual approval.

        Args:
            order: FIX NewOrderSingle message.

        Returns:
            Order ID for tracking.
        """
        try:
            # Generate unique order ID
            order_id = f"MANUAL_{uuid.uuid4().hex[:8].upper()}"

            # Create pending order
            pending_order = PendingOrder(
                order_id=order_id,
                cl_ord_id=order.cl_ord_id,
                order=order,
                received_time=datetime.utcnow(),
                approval_status=ApprovalStatus.PENDING,
            )

            # Add to pending queue
            self.pending_orders[order.cl_ord_id] = pending_order

            # Send initial pending execution report
            await self._send_execution_report(
                pending_order,
                OrdStatus.PENDING_NEW,
                ExecType.PENDING_NEW,
                text="Order pending manual approval",
            )

            # Notify WebSocket clients
            await self._notify_websocket_clients(
                {
                    "type": "new_order",
                    "order_id": order_id,
                    "cl_ord_id": order.cl_ord_id,
                    "symbol": order.symbol,
                    "side": order.side.name,
                    "quantity": order.order_qty,
                    "order_type": order.ord_type.name,
                    "price": getattr(order, "price", None),
                    "timestamp": pending_order.received_time.isoformat(),
                }
            )

            # Update metrics
            self.metrics.total_orders += 1

            logger.info(
                f"Order submitted for manual approval: {order.cl_ord_id} -> {order_id}"
            )
            return order_id

        except Exception as e:
            logger.error(f"Error submitting order for manual approval: {e}")
            self.metrics.failed_orders += 1
            raise

    async def cancel_order(self, cancel_request: OrderCancelRequest) -> bool:
        """Cancel pending order.

        Args:
            cancel_request: FIX OrderCancelRequest message.

        Returns:
            True if cancellation successful.
        """
        try:
            orig_cl_ord_id = cancel_request.orig_cl_ord_id

            if orig_cl_ord_id not in self.pending_orders:
                logger.warning(f"Order not found for cancellation: {orig_cl_ord_id}")
                return False

            pending_order = self.pending_orders[orig_cl_ord_id]

            # Can only cancel pending orders
            if pending_order.approval_status != ApprovalStatus.PENDING:
                logger.warning(
                    f"Cannot cancel order in status: {pending_order.approval_status}"
                )
                return False

            # Mark as rejected
            pending_order.approval_status = ApprovalStatus.REJECTED
            pending_order.review_time = datetime.utcnow()
            pending_order.reviewer = "SYSTEM"
            pending_order.notes = "Cancelled by client"

            # Move to history
            self.order_history.append(pending_order)
            del self.pending_orders[orig_cl_ord_id]

            # Send cancelled execution report
            await self._send_execution_report(
                pending_order,
                OrdStatus.CANCELED,
                ExecType.CANCELED,
                text="Order cancelled",
            )

            # Notify WebSocket clients
            await self._notify_websocket_clients(
                {
                    "type": "order_cancelled",
                    "order_id": pending_order.order_id,
                    "cl_ord_id": orig_cl_ord_id,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            self.metrics.cancelled_orders += 1
            logger.info(f"Order cancelled: {orig_cl_ord_id}")
            return True

        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    async def modify_order(self, modify_request: FIXMessage) -> bool:
        """Modify pending order (not implemented).

        Args:
            modify_request: Order modification request.

        Returns:
            False as modifications go through approval flow.
        """
        logger.warning("Order modifications must go through manual approval flow")
        return False

    async def get_order_status(self, cl_ord_id: str) -> Optional[ExecutionReport]:
        """Get current order status.

        Args:
            cl_ord_id: Client order ID.

        Returns:
            ExecutionReport with current status.
        """
        # Check pending orders
        if cl_ord_id in self.pending_orders:
            pending_order = self.pending_orders[cl_ord_id]
            return await self._create_status_report(pending_order)

        # Check history
        for order in reversed(self.order_history):
            if order.cl_ord_id == cl_ord_id:
                return await self._create_status_report(order)

        return None

    async def approve_order(
        self,
        cl_ord_id: str,
        reviewer: str,
        notes: Optional[str] = None,
        modifications: Optional[Dict[str, Any]] = None,
        risk_overrides: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Approve pending order.

        Args:
            cl_ord_id: Client order ID.
            reviewer: Username of approver.
            notes: Approval notes.
            modifications: Any order modifications.
            risk_overrides: Risk limit overrides.

        Returns:
            True if approval successful.
        """
        if cl_ord_id not in self.pending_orders:
            logger.warning(f"Order not found for approval: {cl_ord_id}")
            return False

        pending_order = self.pending_orders[cl_ord_id]

        if pending_order.approval_status != ApprovalStatus.PENDING:
            logger.warning(
                f"Order not in pending status: {pending_order.approval_status}"
            )
            return False

        # Update approval info
        pending_order.approval_status = ApprovalStatus.APPROVED
        pending_order.reviewer = reviewer
        pending_order.review_time = datetime.utcnow()
        pending_order.notes = notes
        pending_order.modifications = modifications
        pending_order.risk_overrides = risk_overrides

        # Apply modifications if any
        if modifications:
            self._apply_modifications(pending_order.order, modifications)

        # Send approved execution report
        await self._send_execution_report(
            pending_order,
            OrdStatus.NEW,
            ExecType.NEW,
            text=f"Order approved by {reviewer}",
        )

        # Simulate execution if enabled
        if self.simulate_execution:
            asyncio.create_task(self._simulate_order_execution(pending_order))
        else:
            # Move to history as approved
            self.order_history.append(pending_order)
            del self.pending_orders[cl_ord_id]

        # Notify WebSocket clients
        await self._notify_websocket_clients(
            {
                "type": "order_approved",
                "order_id": pending_order.order_id,
                "cl_ord_id": cl_ord_id,
                "reviewer": reviewer,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        logger.info(f"Order approved: {cl_ord_id} by {reviewer}")
        return True

    async def reject_order(
        self, cl_ord_id: str, reviewer: str, reason: str, notes: Optional[str] = None
    ) -> bool:
        """Reject pending order.

        Args:
            cl_ord_id: Client order ID.
            reviewer: Username of reviewer.
            reason: Rejection reason.
            notes: Additional notes.

        Returns:
            True if rejection successful.
        """
        if cl_ord_id not in self.pending_orders:
            logger.warning(f"Order not found for rejection: {cl_ord_id}")
            return False

        pending_order = self.pending_orders[cl_ord_id]

        if pending_order.approval_status != ApprovalStatus.PENDING:
            logger.warning(
                f"Order not in pending status: {pending_order.approval_status}"
            )
            return False

        # Update rejection info
        pending_order.approval_status = ApprovalStatus.REJECTED
        pending_order.reviewer = reviewer
        pending_order.review_time = datetime.utcnow()
        pending_order.notes = f"Rejected: {reason}"
        if notes:
            pending_order.notes += f" - {notes}"

        # Move to history
        self.order_history.append(pending_order)
        del self.pending_orders[cl_ord_id]

        # Send rejected execution report
        await self._send_execution_report(
            pending_order,
            OrdStatus.REJECTED,
            ExecType.REJECTED,
            text=f"Order rejected by {reviewer}: {reason}",
        )

        # Notify WebSocket clients
        await self._notify_websocket_clients(
            {
                "type": "order_rejected",
                "order_id": pending_order.order_id,
                "cl_ord_id": cl_ord_id,
                "reviewer": reviewer,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        self.metrics.rejected_orders += 1
        logger.info(f"Order rejected: {cl_ord_id} by {reviewer} - {reason}")
        return True

    async def get_pending_orders(self) -> List[Dict[str, Any]]:
        """Get all pending orders.

        Returns:
            List of pending order details.
        """
        orders = []

        for pending_order in self.pending_orders.values():
            order_dict = {
                "order_id": pending_order.order_id,
                "cl_ord_id": pending_order.cl_ord_id,
                "symbol": pending_order.order.symbol,
                "side": pending_order.order.side.name,
                "quantity": pending_order.order.order_qty,
                "order_type": pending_order.order.ord_type.name,
                "price": getattr(pending_order.order, "price", None),
                "stop_price": getattr(pending_order.order, "stop_px", None),
                "time_in_force": pending_order.order.time_in_force.name,
                "received_time": pending_order.received_time.isoformat(),
                "approval_status": pending_order.approval_status.value,
                "time_remaining": max(
                    0,
                    self.auto_reject_timeout
                    - (datetime.utcnow() - pending_order.received_time).total_seconds(),
                ),
            }

            # Add approval level requirement
            order_value = pending_order.order.order_qty * (order_dict["price"] or 1.0)
            order_dict["approval_level"] = self._get_required_approval_level(
                order_value
            )

            orders.append(order_dict)

        return orders

    async def get_order_history(
        self,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get order history.

        Args:
            limit: Maximum number of orders to return.
            start_date: Filter by start date.
            end_date: Filter by end date.

        Returns:
            List of historical order details.
        """
        history = []

        for order in reversed(self.order_history[-limit:]):
            if start_date and order.received_time < start_date:
                continue
            if end_date and order.received_time > end_date:
                continue

            order_dict = {
                "order_id": order.order_id,
                "cl_ord_id": order.cl_ord_id,
                "symbol": order.order.symbol,
                "side": order.order.side.name,
                "quantity": order.order.order_qty,
                "order_type": order.order.ord_type.name,
                "price": getattr(order.order, "price", None),
                "received_time": order.received_time.isoformat(),
                "approval_status": order.approval_status.value,
                "reviewer": order.reviewer,
                "review_time": (
                    order.review_time.isoformat() if order.review_time else None
                ),
                "notes": order.notes,
            }

            history.append(order_dict)

        return history

    async def register_websocket(self, websocket: Any) -> None:
        """Register WebSocket client for real-time updates.

        Args:
            websocket: WebSocket connection.
        """
        self.websocket_clients.add(websocket)
        logger.info(
            f"WebSocket client registered. Total clients: {len(self.websocket_clients)}"
        )

    async def unregister_websocket(self, websocket: Any) -> None:
        """Unregister WebSocket client.

        Args:
            websocket: WebSocket connection.
        """
        self.websocket_clients.discard(websocket)
        logger.info(
            f"WebSocket client unregistered. Total clients: {len(self.websocket_clients)}"
        )

    async def _send_execution_report(
        self,
        pending_order: PendingOrder,
        ord_status: OrdStatus,
        exec_type: ExecType,
        text: Optional[str] = None,
        filled_qty: float = 0,
        avg_px: float = 0,
    ) -> None:
        """Send execution report.

        Args:
            pending_order: Pending order.
            ord_status: Order status.
            exec_type: Execution type.
            text: Optional text.
            filled_qty: Filled quantity.
            avg_px: Average price.
        """
        # This would normally publish to RabbitMQ
        # For now, just log it
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

        logger.info(f"Execution report: {exec_report.cl_ord_id} - {ord_status.name}")

    async def _create_status_report(
        self, pending_order: PendingOrder
    ) -> ExecutionReport:
        """Create status execution report.

        Args:
            pending_order: Pending order.

        Returns:
            ExecutionReport with current status.
        """
        # Map approval status to FIX status
        status_map = {
            ApprovalStatus.PENDING: (OrdStatus.PENDING_NEW, ExecType.PENDING_NEW),
            ApprovalStatus.APPROVED: (OrdStatus.NEW, ExecType.NEW),
            ApprovalStatus.REJECTED: (OrdStatus.REJECTED, ExecType.REJECTED),
            ApprovalStatus.EXPIRED: (OrdStatus.EXPIRED, ExecType.EXPIRED),
        }

        ord_status, exec_type = status_map.get(
            pending_order.approval_status, (OrdStatus.NEW, ExecType.ORDER_STATUS)
        )

        return ExecutionReport(
            order_id=pending_order.order_id,
            cl_ord_id=pending_order.cl_ord_id,
            exec_id=f"STATUS_{pending_order.order_id}",
            exec_type=exec_type,
            ord_status=ord_status,
            symbol=pending_order.order.symbol,
            side=pending_order.order.side,
            order_qty=pending_order.order.order_qty,
            transact_time=datetime.utcnow(),
        )

    async def _notify_websocket_clients(self, message: Dict[str, Any]) -> None:
        """Notify all WebSocket clients.

        Args:
            message: Message to send.
        """
        if not self.websocket_clients:
            return

        disconnected = []

        for websocket in self.websocket_clients:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket client: {e}")
                disconnected.append(websocket)

        # Clean up disconnected clients
        for websocket in disconnected:
            self.websocket_clients.discard(websocket)

    def _apply_modifications(
        self, order: NewOrderSingle, modifications: Dict[str, Any]
    ) -> None:
        """Apply modifications to order.

        Args:
            order: Original order.
            modifications: Modifications to apply.
        """
        for field, value in modifications.items():
            if hasattr(order, field):
                setattr(order, field, value)
                logger.info(f"Modified order field {field} to {value}")

    def _get_required_approval_level(self, order_value: float) -> str:
        """Get required approval level based on order value.

        Args:
            order_value: Total order value.

        Returns:
            Required approval level.
        """
        for level, threshold in sorted(
            self.approval_levels.items(), key=lambda x: x[1], reverse=True
        ):
            if order_value >= threshold:
                return level
        return "standard"

    async def _simulate_order_execution(self, pending_order: PendingOrder) -> None:
        """Simulate order execution.

        Args:
            pending_order: Approved order to simulate.
        """
        try:
            # Wait for simulated fill
            await asyncio.sleep(self.simulated_fill_delay)

            # Simulate fill
            fill_price = getattr(pending_order.order, "price", 1.0)
            if fill_price == 0:  # Market order
                # Simulate market price
                fill_price = 1.0 + (
                    0.0001 * (1 if pending_order.order.side.value == "1" else -1)
                )

            # Send filled execution report
            await self._send_execution_report(
                pending_order,
                OrdStatus.FILLED,
                ExecType.TRADE,
                text="Order filled (simulated)",
                filled_qty=pending_order.order.order_qty,
                avg_px=fill_price,
            )

            # Move to history
            if pending_order.cl_ord_id in self.pending_orders:
                self.order_history.append(pending_order)
                del self.pending_orders[pending_order.cl_ord_id]

            # Notify WebSocket clients
            await self._notify_websocket_clients(
                {
                    "type": "order_filled",
                    "order_id": pending_order.order_id,
                    "cl_ord_id": pending_order.cl_ord_id,
                    "fill_price": fill_price,
                    "quantity": pending_order.order.order_qty,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            self.metrics.filled_orders += 1
            logger.info(
                f"Order filled (simulated): {pending_order.cl_ord_id} @ {fill_price}"
            )

        except Exception as e:
            logger.error(f"Error simulating order execution: {e}")

    async def _cleanup_expired_orders(self) -> None:
        """Cleanup expired pending orders."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                expired = []
                now = datetime.utcnow()

                for cl_ord_id, pending_order in self.pending_orders.items():
                    if pending_order.approval_status == ApprovalStatus.PENDING:
                        age = (now - pending_order.received_time).total_seconds()
                        if age > self.auto_reject_timeout:
                            expired.append(cl_ord_id)

                # Auto-reject expired orders
                for cl_ord_id in expired:
                    await self.reject_order(
                        cl_ord_id=cl_ord_id,
                        reviewer="SYSTEM",
                        reason="Order expired - no action taken",
                        notes=f"Auto-rejected after {self.auto_reject_timeout}s",
                    )

                if expired:
                    logger.info(f"Auto-rejected {len(expired)} expired orders")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)
