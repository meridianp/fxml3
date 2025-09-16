"""
Order Management routes for FXML4 API.

This module handles order creation, execution, and management.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from fxml4.api.auth.auth import User, get_current_active_user
from fxml4.api.services.order_management import (
    OrderData,
    OrderExecution,
    OrderSide,
    OrderType,
    TimeInForce,
    order_management_service,
)
from fxml4.api.services.signal_processing import signal_processing_service

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)


class CreateOrderRequest(BaseModel):
    """Request model for creating orders."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY


class CreateOrderFromSignalRequest(BaseModel):
    """Request model for creating orders from signals."""

    symbol: str
    quantity: float
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None
    auto_execute: bool = False


@router.post("/orders", response_model=Dict[str, Any], tags=["orders"])
async def create_order(
    request: CreateOrderRequest, current_user: User = Depends(get_current_active_user)
):
    """Create a new order manually."""
    try:
        logger.info(
            f"Creating manual order: {request.side.value} {request.quantity} {request.symbol}"
        )

        order = await order_management_service.create_manual_order(
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price,
            time_in_force=request.time_in_force,
        )

        return {
            "order_id": order.id,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
            "risk_approved": order.risk_approved,
            "compliance_checked": order.compliance_checked,
            "message": f"Order created successfully",
        }

    except Exception as e:
        logger.exception("Error creating order: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/orders/from-signal", response_model=Dict[str, Any], tags=["orders"])
async def create_order_from_signal(
    request: CreateOrderFromSignalRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Create an order from the latest signal for a symbol."""
    try:
        # Get the latest signal for the symbol
        signals = await signal_processing_service.get_recent_signals(
            symbol=request.symbol, limit=1, hours_back=24
        )

        if not signals:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No recent signals found for {request.symbol}",
            )

        latest_signal = signals[0]

        # Check if signal is recent enough (within last hour)
        signal_age_hours = (
            datetime.utcnow() - latest_signal.timestamp
        ).total_seconds() / 3600
        if signal_age_hours > 1.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Latest signal is {signal_age_hours:.1f} hours old - too stale for order creation",
            )

        # Create order from signal
        order = await order_management_service.create_order_from_signal(
            signal=latest_signal,
            quantity=request.quantity,
            order_type=request.order_type,
            price=request.price,
            auto_execute=request.auto_execute,
        )

        return {
            "order_id": order.id,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status,
            "signal_confidence": latest_signal.confidence,
            "signal_type": latest_signal.signal_type,
            "created_at": order.created_at.isoformat(),
            "auto_executed": request.auto_execute,
            "message": f"Order created from signal successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creating order from signal: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/orders/{order_id}/execute", response_model=Dict[str, Any], tags=["orders"]
)
async def execute_order(
    order_id: str,
    broker: Optional[str] = Query(
        None, description="Broker to use for execution (default: manual)"
    ),
    current_user: User = Depends(get_current_active_user),
):
    """Execute a pending order."""
    try:
        success = await order_management_service.execute_order(order_id, broker)

        if success:
            order = await order_management_service.get_order(order_id)
            return {
                "order_id": order_id,
                "status": order.status if order else "unknown",
                "executed": True,
                "broker": broker or "manual",
                "message": "Order executed successfully",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Order execution failed",
            )

    except Exception as e:
        logger.exception("Error executing order: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "/orders/{order_id}/cancel", response_model=Dict[str, Any], tags=["orders"]
)
async def cancel_order(
    order_id: str, current_user: User = Depends(get_current_active_user)
):
    """Cancel a pending order."""
    try:
        success = await order_management_service.cancel_order(order_id)

        if success:
            return {
                "order_id": order_id,
                "cancelled": True,
                "message": "Order cancelled successfully",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Order cancellation failed",
            )

    except Exception as e:
        logger.exception("Error cancelling order: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/orders", response_model=Dict[str, Any], tags=["orders"])
async def get_orders(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, description="Number of orders to return", ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
):
    """Get orders with optional filtering."""
    try:
        orders = await order_management_service.get_orders(
            symbol=symbol, status=status, limit=limit
        )

        orders_data = []
        for order in orders:
            orders_data.append(
                {
                    "id": order.id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "order_type": order.order_type.value,
                    "quantity": order.quantity,
                    "price": order.price,
                    "stop_price": order.stop_price,
                    "time_in_force": order.time_in_force.value,
                    "status": order.status,
                    "filled_quantity": order.filled_quantity,
                    "remaining_quantity": order.remaining_quantity,
                    "avg_fill_price": order.avg_fill_price,
                    "created_at": order.created_at.isoformat(),
                    "submitted_at": (
                        order.submitted_at.isoformat() if order.submitted_at else None
                    ),
                    "filled_at": (
                        order.filled_at.isoformat() if order.filled_at else None
                    ),
                    "signal_id": order.signal_id,
                    "strategy_name": order.strategy_name,
                    "risk_approved": order.risk_approved,
                    "compliance_checked": order.compliance_checked,
                }
            )

        return {
            "orders": orders_data,
            "count": len(orders_data),
            "filters": {"symbol": symbol, "status": status, "limit": limit},
        }

    except Exception as e:
        logger.exception("Error getting orders: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/orders/{order_id}", response_model=Dict[str, Any], tags=["orders"])
async def get_order(
    order_id: str, current_user: User = Depends(get_current_active_user)
):
    """Get a specific order by ID."""
    try:
        order = await order_management_service.get_order(order_id)

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )

        # Get executions for this order
        executions = await order_management_service.get_executions(order_id)
        executions_data = []

        for execution in executions:
            executions_data.append(
                {
                    "execution_id": execution.execution_id,
                    "order_id": execution.order_id,
                    "symbol": execution.symbol,
                    "side": execution.side.value,
                    "quantity": execution.quantity,
                    "price": execution.price,
                    "timestamp": execution.timestamp.isoformat(),
                    "commission": execution.commission,
                    "metadata": execution.metadata,
                }
            )

        return {
            "order": {
                "id": order.id,
                "symbol": order.symbol,
                "side": order.side.value,
                "order_type": order.order_type.value,
                "quantity": order.quantity,
                "price": order.price,
                "stop_price": order.stop_price,
                "time_in_force": order.time_in_force.value,
                "status": order.status,
                "filled_quantity": order.filled_quantity,
                "remaining_quantity": order.remaining_quantity,
                "avg_fill_price": order.avg_fill_price,
                "created_at": order.created_at.isoformat(),
                "submitted_at": (
                    order.submitted_at.isoformat() if order.submitted_at else None
                ),
                "filled_at": order.filled_at.isoformat() if order.filled_at else None,
                "signal_id": order.signal_id,
                "strategy_name": order.strategy_name,
                "risk_approved": order.risk_approved,
                "compliance_checked": order.compliance_checked,
                "metadata": order.metadata,
            },
            "executions": executions_data,
            "execution_count": len(executions_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting order: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/orders/{order_id}/executions", response_model=Dict[str, Any], tags=["orders"]
)
async def get_order_executions(
    order_id: str, current_user: User = Depends(get_current_active_user)
):
    """Get executions for a specific order."""
    try:
        executions = await order_management_service.get_executions(order_id)

        executions_data = []
        for execution in executions:
            executions_data.append(
                {
                    "execution_id": execution.execution_id,
                    "order_id": execution.order_id,
                    "symbol": execution.symbol,
                    "side": execution.side.value,
                    "quantity": execution.quantity,
                    "price": execution.price,
                    "timestamp": execution.timestamp.isoformat(),
                    "commission": execution.commission,
                    "metadata": execution.metadata,
                }
            )

        return {
            "order_id": order_id,
            "executions": executions_data,
            "count": len(executions_data),
        }

    except Exception as e:
        logger.exception("Error getting order executions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/orders/status/summary", response_model=Dict[str, Any], tags=["orders"])
async def get_order_status_summary(
    current_user: User = Depends(get_current_active_user),
):
    """Get summary of order statuses."""
    try:
        all_orders = await order_management_service.get_orders(limit=1000)

        # Count by status
        status_counts = {}
        for order in all_orders:
            status_counts[order.status] = status_counts.get(order.status, 0) + 1

        # Count by symbol
        symbol_counts = {}
        for order in all_orders:
            symbol_counts[order.symbol] = symbol_counts.get(order.symbol, 0) + 1

        return {
            "total_orders": len(all_orders),
            "status_counts": status_counts,
            "symbol_counts": symbol_counts,
            "active_orders": len(
                [
                    o
                    for o in all_orders
                    if o.status in ["pending", "submitted", "working"]
                ]
            ),
            "filled_orders": len([o for o in all_orders if o.status == "filled"]),
            "cancelled_orders": len([o for o in all_orders if o.status == "cancelled"]),
        }

    except Exception as e:
        logger.exception("Error getting order status summary: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# Startup event to initialize order management service
@router.on_event("startup")
async def startup_order_management():
    """Initialize the order management service on startup."""
    try:
        await order_management_service.initialize()
        logger.info("Order management service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize order management service: {e}")


# Shutdown event to cleanup order management service
@router.on_event("shutdown")
async def shutdown_order_management():
    """Cleanup the order management service on shutdown."""
    try:
        await order_management_service.close()
        logger.info("Order management service closed")
    except Exception as e:
        logger.error(f"Error closing order management service: {e}")
