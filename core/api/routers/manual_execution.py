"""Manual Execution API Router.

This module provides REST and WebSocket endpoints for the manual
order approval interface.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# Import manual adapter (will be initialized by main app)
from ...brokers.adapters.manual_rabbitmq_adapter import ManualRabbitMQAdapter

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/manual",
    tags=["manual-execution"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not found"},
    },
)

# Security
security = HTTPBearer()

# Global adapter reference (set by main app)
manual_adapter: Optional[ManualRabbitMQAdapter] = None


# Pydantic models
class OrderApprovalRequest(BaseModel):
    """Order approval request."""

    cl_ord_id: str = Field(..., description="Client order ID")
    reviewer: str = Field(..., description="Username of approver")
    notes: Optional[str] = Field(None, description="Approval notes")
    modifications: Optional[Dict[str, Any]] = Field(
        None, description="Order modifications"
    )
    risk_overrides: Optional[Dict[str, Any]] = Field(
        None, description="Risk limit overrides"
    )


class OrderRejectionRequest(BaseModel):
    """Order rejection request."""

    cl_ord_id: str = Field(..., description="Client order ID")
    reviewer: str = Field(..., description="Username of reviewer")
    reason: str = Field(..., description="Rejection reason")
    notes: Optional[str] = Field(None, description="Additional notes")


class OrderStatusResponse(BaseModel):
    """Order status response."""

    order_id: str
    cl_ord_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    price: Optional[float]
    stop_price: Optional[float]
    time_in_force: str
    received_time: str
    approval_status: str
    reviewer: Optional[str]
    review_time: Optional[str]
    notes: Optional[str]
    time_remaining: float


class PendingOrdersResponse(BaseModel):
    """Pending orders response."""

    orders: List[Dict[str, Any]]
    total: int
    timestamp: str


class OrderHistoryResponse(BaseModel):
    """Order history response."""

    orders: List[Dict[str, Any]]
    total: int
    limit: int
    timestamp: str


class AdapterStatusResponse(BaseModel):
    """Adapter status response."""

    status: str
    connected: bool
    pending_orders: int
    total_orders: int
    websocket_clients: int
    auto_reject_timeout: int
    timestamp: str


# Helper functions
def get_adapter() -> ManualRabbitMQAdapter:
    """Get manual adapter instance."""
    if not manual_adapter:
        raise HTTPException(status_code=500, detail="Manual adapter not initialized")
    return manual_adapter


async def verify_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Verify authentication token.

    Args:
        credentials: Bearer token credentials.

    Returns:
        Username extracted from token.

    Raises:
        HTTPException: If authentication fails.
    """
    # TODO: Implement proper JWT validation
    # For now, just extract username from token
    try:
        # Mock validation - in production use proper JWT
        if credentials.credentials.startswith("valid_"):
            username = credentials.credentials.replace("valid_", "")
            return username
        else:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication token")


# REST Endpoints
@router.get("/status", response_model=AdapterStatusResponse)
async def get_adapter_status(username: str = Depends(verify_auth)):
    """Get manual adapter status.

    Returns:
        Current adapter status.
    """
    adapter = get_adapter()

    return AdapterStatusResponse(
        status=adapter.connection.status.value,
        connected=adapter.connection.is_connected(),
        pending_orders=len(adapter.pending_orders),
        total_orders=len(adapter.order_history),
        websocket_clients=len(adapter.websocket_clients),
        auto_reject_timeout=adapter.auto_reject_timeout,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/orders/pending", response_model=PendingOrdersResponse)
async def get_pending_orders(username: str = Depends(verify_auth)):
    """Get all pending orders awaiting approval.

    Returns:
        List of pending orders.
    """
    adapter = get_adapter()
    orders = await adapter.get_pending_orders()

    return PendingOrdersResponse(
        orders=orders, total=len(orders), timestamp=datetime.utcnow().isoformat()
    )


@router.get("/orders/history", response_model=OrderHistoryResponse)
async def get_order_history(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of orders"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    username: str = Depends(verify_auth),
):
    """Get order history.

    Args:
        limit: Maximum number of orders to return.
        start_date: Optional start date filter.
        end_date: Optional end date filter.

    Returns:
        Historical orders.
    """
    adapter = get_adapter()
    orders = await adapter.get_order_history(
        limit=limit, start_date=start_date, end_date=end_date
    )

    return OrderHistoryResponse(
        orders=orders,
        total=len(orders),
        limit=limit,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/orders/{cl_ord_id}", response_model=OrderStatusResponse)
async def get_order_status(cl_ord_id: str, username: str = Depends(verify_auth)):
    """Get specific order status.

    Args:
        cl_ord_id: Client order ID.

    Returns:
        Order status details.

    Raises:
        HTTPException: If order not found.
    """
    adapter = get_adapter()

    # Check pending orders
    if cl_ord_id in adapter.pending_orders:
        order = adapter.pending_orders[cl_ord_id]

        return OrderStatusResponse(
            order_id=order.order_id,
            cl_ord_id=order.cl_ord_id,
            symbol=order.order.symbol,
            side=order.order.side.name,
            quantity=order.order.order_qty,
            order_type=order.order.ord_type.name,
            price=getattr(order.order, "price", None),
            stop_price=getattr(order.order, "stop_px", None),
            time_in_force=order.order.time_in_force.name,
            received_time=order.received_time.isoformat(),
            approval_status=order.approval_status.value,
            reviewer=order.reviewer,
            review_time=order.review_time.isoformat() if order.review_time else None,
            notes=order.notes,
            time_remaining=max(
                0,
                adapter.auto_reject_timeout
                - (datetime.utcnow() - order.received_time).total_seconds(),
            ),
        )

    # Check history
    for order in adapter.order_history:
        if order.cl_ord_id == cl_ord_id:
            return OrderStatusResponse(
                order_id=order.order_id,
                cl_ord_id=order.cl_ord_id,
                symbol=order.order.symbol,
                side=order.order.side.name,
                quantity=order.order.order_qty,
                order_type=order.order.ord_type.name,
                price=getattr(order.order, "price", None),
                stop_price=getattr(order.order, "stop_px", None),
                time_in_force=order.order.time_in_force.name,
                received_time=order.received_time.isoformat(),
                approval_status=order.approval_status.value,
                reviewer=order.reviewer,
                review_time=(
                    order.review_time.isoformat() if order.review_time else None
                ),
                notes=order.notes,
                time_remaining=0,
            )

    raise HTTPException(status_code=404, detail=f"Order not found: {cl_ord_id}")


@router.post("/orders/{cl_ord_id}/approve")
async def approve_order(
    cl_ord_id: str, request: OrderApprovalRequest, username: str = Depends(verify_auth)
):
    """Approve pending order.

    Args:
        cl_ord_id: Client order ID.
        request: Approval details.

    Returns:
        Success response.

    Raises:
        HTTPException: If approval fails.
    """
    if cl_ord_id != request.cl_ord_id:
        raise HTTPException(status_code=400, detail="Order ID mismatch")

    adapter = get_adapter()

    # Use authenticated username as reviewer
    success = await adapter.approve_order(
        cl_ord_id=cl_ord_id,
        reviewer=username,  # Use authenticated user
        notes=request.notes,
        modifications=request.modifications,
        risk_overrides=request.risk_overrides,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to approve order")

    return {
        "status": "approved",
        "cl_ord_id": cl_ord_id,
        "reviewer": username,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/orders/{cl_ord_id}/reject")
async def reject_order(
    cl_ord_id: str, request: OrderRejectionRequest, username: str = Depends(verify_auth)
):
    """Reject pending order.

    Args:
        cl_ord_id: Client order ID.
        request: Rejection details.

    Returns:
        Success response.

    Raises:
        HTTPException: If rejection fails.
    """
    if cl_ord_id != request.cl_ord_id:
        raise HTTPException(status_code=400, detail="Order ID mismatch")

    adapter = get_adapter()

    # Use authenticated username as reviewer
    success = await adapter.reject_order(
        cl_ord_id=cl_ord_id,
        reviewer=username,  # Use authenticated user
        reason=request.reason,
        notes=request.notes,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to reject order")

    return {
        "status": "rejected",
        "cl_ord_id": cl_ord_id,
        "reviewer": username,
        "reason": request.reason,
        "timestamp": datetime.utcnow().isoformat(),
    }


# WebSocket Endpoints
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time order updates.

    Clients connect to this endpoint to receive:
    - New order notifications
    - Order status updates
    - Approval/rejection notifications

    Args:
        websocket: WebSocket connection.
    """
    adapter = get_adapter()

    # Accept connection
    await websocket.accept()

    # Register with adapter
    await adapter.register_websocket(websocket)

    try:
        # Send initial status
        await websocket.send_json(
            {
                "type": "connected",
                "timestamp": datetime.utcnow().isoformat(),
                "pending_orders": len(adapter.pending_orders),
            }
        )

        # Keep connection alive and handle incoming messages
        while True:
            # Wait for client messages (ping/pong, commands, etc.)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Handle client messages
                try:
                    message = json.loads(data)

                    if message.get("type") == "ping":
                        await websocket.send_json(
                            {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                        )
                    elif message.get("type") == "get_pending":
                        # Send current pending orders
                        orders = await adapter.get_pending_orders()
                        await websocket.send_json(
                            {
                                "type": "pending_orders",
                                "orders": orders,
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        )
                    else:
                        logger.warning(
                            f"Unknown WebSocket message type: {message.get('type')}"
                        )

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {data}")

            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json(
                        {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
                    )
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Unregister from adapter
        await adapter.unregister_websocket(websocket)


# Utility endpoints
@router.get("/config")
async def get_configuration(username: str = Depends(verify_auth)):
    """Get manual execution configuration.

    Returns:
        Configuration details.
    """
    adapter = get_adapter()

    return {
        "auto_reject_timeout": adapter.auto_reject_timeout,
        "require_two_factor": adapter.require_two_factor,
        "allow_risk_override": adapter.allow_risk_override,
        "max_override_amount": adapter.max_override_amount,
        "approval_levels": adapter.approval_levels,
        "simulate_execution": adapter.simulate_execution,
        "simulated_fill_delay": adapter.simulated_fill_delay,
    }


@router.get("/stats")
async def get_statistics(username: str = Depends(verify_auth)):
    """Get approval statistics.

    Returns:
        Approval statistics.
    """
    adapter = get_adapter()

    # Calculate statistics
    total_orders = len(adapter.order_history)
    approved = sum(
        1 for o in adapter.order_history if o.approval_status.value == "APPROVED"
    )
    rejected = sum(
        1 for o in adapter.order_history if o.approval_status.value == "REJECTED"
    )
    expired = sum(
        1 for o in adapter.order_history if o.approval_status.value == "EXPIRED"
    )

    # Get reviewer statistics
    reviewer_stats = {}
    for order in adapter.order_history:
        if order.reviewer and order.reviewer != "SYSTEM":
            if order.reviewer not in reviewer_stats:
                reviewer_stats[order.reviewer] = {
                    "approved": 0,
                    "rejected": 0,
                    "total": 0,
                }
            reviewer_stats[order.reviewer]["total"] += 1
            if order.approval_status.value == "APPROVED":
                reviewer_stats[order.reviewer]["approved"] += 1
            elif order.approval_status.value == "REJECTED":
                reviewer_stats[order.reviewer]["rejected"] += 1

    return {
        "total_orders": total_orders,
        "approved": approved,
        "rejected": rejected,
        "expired": expired,
        "pending": len(adapter.pending_orders),
        "approval_rate": (approved / total_orders * 100) if total_orders > 0 else 0,
        "reviewer_stats": reviewer_stats,
        "timestamp": datetime.utcnow().isoformat(),
    }


# Health check
@router.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Health status.
    """
    adapter = get_adapter()

    return {
        "status": "healthy" if adapter.connection.is_connected() else "unhealthy",
        "adapter_status": adapter.connection.status.value,
        "pending_orders": len(adapter.pending_orders),
        "timestamp": datetime.utcnow().isoformat(),
    }
