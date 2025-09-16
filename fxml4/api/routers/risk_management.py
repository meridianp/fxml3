"""Risk Management API Router.

This module provides REST API endpoints for risk management
functionality in the broker abstraction system.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from ...brokers.risk import FXRiskManager, RiskLimits, create_risk_limits_from_config
from ...brokers.risk.integration import RiskAwareBrokerManager
from ...fix.messages.base import OrdType, Side, TimeInForce
from ...fix.messages.orders import NewOrderSingle
from ..dependencies import get_risk_broker_manager, get_risk_manager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/risk", tags=["risk"])


# Pydantic models for API
class RiskCheckRequest(BaseModel):
    """Request model for risk check."""

    cl_ord_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str = "LIMIT"
    price: Optional[float] = None
    time_in_force: str = "GTC"
    broker: Optional[str] = None


class RiskOverrideRequest(BaseModel):
    """Request model for risk override."""

    user: str
    level: str = Field(..., description="Override authority level")
    reason: str = Field(..., min_length=10)


class PositionUpdate(BaseModel):
    """Position update notification."""

    symbol: str
    quantity: float
    price: float
    side: str
    trade_id: Optional[str] = None


class MarketPriceUpdate(BaseModel):
    """Market price update."""

    prices: Dict[str, float]


class RiskLimitUpdate(BaseModel):
    """Risk limit update request."""

    limit_type: str
    limit_name: str
    value: Any


@router.get("/summary")
async def get_risk_summary(
    risk_manager: FXRiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """Get current risk summary including metrics and limits."""
    try:
        summary = risk_manager.get_risk_summary()
        return {
            "status": "success",
            "data": summary,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting risk summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check")
async def check_order_risk(
    request: RiskCheckRequest,
    risk_broker: RiskAwareBrokerManager = Depends(get_risk_broker_manager),
) -> Dict[str, Any]:
    """Check if an order passes risk controls."""
    try:
        # Create order from request
        order = NewOrderSingle(
            cl_ord_id=request.cl_ord_id,
            symbol=request.symbol,
            side=Side[request.side.upper()],
            order_qty=request.quantity,
            ord_type=OrdType[request.order_type.upper()],
            price=request.price,
            time_in_force=TimeInForce[request.time_in_force.upper()],
            transact_time=datetime.utcnow(),
        )

        # Check risk
        passes, violations = await risk_broker.risk_manager.check_order(
            order, broker=request.broker
        )

        return {
            "status": "success",
            "data": {
                "passes": passes,
                "violations": [
                    {
                        "check_type": v.check_type.value,
                        "result": v.result.value,
                        "message": v.message,
                        "current_value": str(v.current_value),
                        "limit_value": str(v.limit_value),
                        "can_override": v.can_override,
                        "override_level": v.override_level,
                    }
                    for v in violations
                ],
                "cl_ord_id": request.cl_ord_id,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error checking order risk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/override/{cl_ord_id}")
async def add_risk_override(
    cl_ord_id: str,
    override: RiskOverrideRequest,
    risk_manager: FXRiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """Add risk override for an order."""
    try:
        risk_manager.add_override(
            cl_ord_id=cl_ord_id,
            user=override.user,
            level=override.level,
            reason=override.reason,
        )

        return {
            "status": "success",
            "message": f"Override added for order {cl_ord_id}",
            "data": {
                "cl_ord_id": cl_ord_id,
                "override_user": override.user,
                "override_level": override.level,
                "reason": override.reason,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error adding override: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions(
    risk_manager: FXRiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """Get current positions."""
    try:
        positions = {}
        for symbol, pos in risk_manager.metrics.positions.items():
            positions[symbol] = {
                "quantity": pos.quantity,
                "average_price": pos.average_price,
                "market_value": pos.market_value,
                "unrealized_pnl": pos.unrealized_pnl,
                "realized_pnl": pos.realized_pnl,
                "notional_value": pos.notional_value,
                "last_update": pos.last_update.isoformat(),
            }

        return {
            "status": "success",
            "data": {
                "positions": positions,
                "total_notional": risk_manager.get_total_notional(),
                "daily_pnl": risk_manager.get_daily_pnl(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/positions/update")
async def update_position(
    update: PositionUpdate, risk_manager: FXRiskManager = Depends(get_risk_manager)
) -> Dict[str, Any]:
    """Update position (for manual trades or adjustments)."""
    try:
        # Convert side to quantity sign
        quantity = update.quantity if update.side.upper() == "BUY" else -update.quantity

        await risk_manager.update_position(
            symbol=update.symbol, quantity=quantity, price=update.price
        )

        # Get updated position
        position = risk_manager.get_position(update.symbol)

        return {
            "status": "success",
            "message": f"Position updated for {update.symbol}",
            "data": {
                "symbol": update.symbol,
                "new_quantity": position.quantity if position else 0,
                "new_notional": position.notional_value if position else 0,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error updating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/market-prices")
async def update_market_prices(
    update: MarketPriceUpdate,
    risk_broker: RiskAwareBrokerManager = Depends(get_risk_broker_manager),
) -> Dict[str, Any]:
    """Update market prices for risk checks."""
    try:
        risk_broker.update_market_prices(update.prices)

        return {
            "status": "success",
            "message": f"Updated prices for {len(update.prices)} symbols",
            "data": {"symbols": list(update.prices.keys())},
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error updating market prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/limits")
async def get_risk_limits(
    risk_manager: FXRiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """Get current risk limits configuration."""
    try:
        limits = risk_manager.limits

        return {
            "status": "success",
            "data": {
                "position_limits": {
                    "max_portfolio_notional": limits.max_portfolio_notional,
                    "max_single_position_notional": limits.max_single_position_notional,
                    "max_position_size": limits.max_position_size,
                },
                "order_limits": {
                    "max_order_notional": limits.max_order_notional,
                    "min_order_size": limits.min_order_size,
                    "max_order_size": limits.max_order_size,
                },
                "loss_limits": {
                    "max_daily_loss": limits.max_daily_loss,
                    "max_weekly_loss": limits.max_weekly_loss,
                    "max_monthly_loss": limits.max_monthly_loss,
                },
                "price_limits": {
                    "max_price_deviation_pct": limits.max_price_deviation_pct
                },
                "symbol_restrictions": {
                    "allowed_symbols": limits.allowed_symbols,
                    "blocked_symbols": limits.blocked_symbols,
                },
                "time_restrictions": {
                    "restricted_hours": [
                        {"start": s, "end": e} for s, e in limits.restricted_hours
                    ]
                },
                "counterparty_limits": {
                    "max_orders_per_broker": limits.max_orders_per_broker,
                    "max_notional_per_broker": limits.max_notional_per_broker,
                },
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting risk limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/limits")
async def update_risk_limit(
    update: RiskLimitUpdate, risk_manager: FXRiskManager = Depends(get_risk_manager)
) -> Dict[str, Any]:
    """Update a specific risk limit (requires authorization)."""
    try:
        # This is a simplified version - in production, add proper authorization
        limits = risk_manager.limits

        # Map limit types to attributes
        limit_map = {
            "position": {
                "max_portfolio_notional": "max_portfolio_notional",
                "max_single_position_notional": "max_single_position_notional",
            },
            "order": {
                "max_order_notional": "max_order_notional",
                "min_order_size": "min_order_size",
            },
            "loss": {
                "max_daily_loss": "max_daily_loss",
                "max_weekly_loss": "max_weekly_loss",
                "max_monthly_loss": "max_monthly_loss",
            },
            "price": {"max_price_deviation_pct": "max_price_deviation_pct"},
        }

        # Update the limit
        if update.limit_type in limit_map:
            if update.limit_name in limit_map[update.limit_type]:
                attr_name = limit_map[update.limit_type][update.limit_name]
                old_value = getattr(limits, attr_name)
                setattr(limits, attr_name, update.value)

                logger.info(
                    f"Risk limit updated: {attr_name} from {old_value} to {update.value}"
                )

                return {
                    "status": "success",
                    "message": f"Risk limit '{update.limit_name}' updated",
                    "data": {
                        "limit_type": update.limit_type,
                        "limit_name": update.limit_name,
                        "old_value": old_value,
                        "new_value": update.value,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }

        raise HTTPException(
            status_code=400,
            detail=f"Invalid limit type or name: {update.limit_type}.{update.limit_name}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating risk limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rejected-orders")
async def get_rejected_orders(
    risk_broker: RiskAwareBrokerManager = Depends(get_risk_broker_manager),
) -> Dict[str, Any]:
    """Get list of orders rejected by risk management."""
    try:
        rejected = []
        for cl_ord_id, violations in risk_broker.rejected_orders.items():
            rejected.append(
                {
                    "cl_ord_id": cl_ord_id,
                    "violations": [
                        {
                            "check_type": v.check_type.value,
                            "message": v.message,
                            "can_override": v.can_override,
                            "override_level": v.override_level,
                        }
                        for v in violations
                    ],
                }
            )

        return {
            "status": "success",
            "data": {"rejected_orders": rejected, "total_count": len(rejected)},
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting rejected orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_risk_metrics(
    risk_manager: FXRiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """Get comprehensive risk metrics for frontend dashboard."""
    try:
        # Get basic risk summary
        summary = risk_manager.get_risk_summary()
        metrics = summary.get("metrics", {})
        positions = summary.get("positions", {})

        # Calculate total portfolio value
        portfolio_value = 100000.0  # TODO: Get actual account balance
        total_position_value = sum(
            pos.get("market_value", 0) for pos in positions.values()
        )
        portfolio_value += total_position_value

        # Calculate exposures
        total_exposure = abs(metrics.get("total_notional", 0))
        net_exposure = metrics.get("total_notional", 0)  # Net = long - short positions
        gross_exposure = total_exposure  # Gross = |long| + |short|

        # Calculate daily P&L
        daily_pnl = metrics.get("daily_pnl", 0)
        daily_pnl_pct = (
            (daily_pnl / portfolio_value) * 100 if portfolio_value > 0 else 0
        )

        # Calculate drawdown (simplified - in production, use historical data)
        max_drawdown = abs(daily_pnl) if daily_pnl < 0 else 0
        max_drawdown_pct = (
            (max_drawdown / portfolio_value) * 100 if portfolio_value > 0 else 0
        )

        # Calculate margin metrics (simplified)
        margin_used = total_exposure * 0.02  # Assuming 2% margin requirement
        margin_available = portfolio_value - margin_used
        margin_utilization = (
            (margin_used / portfolio_value) if portfolio_value > 0 else 0
        )

        # Simplified risk metrics (TODO: Calculate from historical data)
        var_95 = portfolio_value * 0.02  # 2% Value at Risk
        var_99 = portfolio_value * 0.05  # 5% Value at Risk
        sharpe_ratio = 1.2 if daily_pnl > 0 else -0.5  # Simplified
        sortino_ratio = 1.8 if daily_pnl > 0 else -0.3  # Simplified

        # Return metrics in exact format expected by frontend
        risk_metrics = {
            "portfolio_value": round(portfolio_value, 2),
            "total_exposure": round(total_exposure, 2),
            "net_exposure": round(net_exposure, 2),
            "gross_exposure": round(gross_exposure, 2),
            "daily_pnl": round(daily_pnl, 2),
            "daily_pnl_pct": round(daily_pnl_pct, 2),
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "var_95": round(var_95, 2),
            "var_99": round(var_99, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "margin_used": round(margin_used, 2),
            "margin_available": round(margin_available, 2),
            "margin_utilization": round(margin_utilization, 2),
        }

        return risk_metrics

    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checks")
async def get_enabled_checks(
    risk_manager: FXRiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """Get list of enabled risk checks."""
    try:
        checks = []
        for check in risk_manager.checks:
            checks.append(
                {
                    "type": check.check_type.value,
                    "enabled": check.enabled,
                    "class": check.__class__.__name__,
                }
            )

        return {
            "status": "success",
            "data": {
                "checks": checks,
                "total_count": len(checks),
                "enabled_count": sum(1 for c in checks if c["enabled"]),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting risk checks: {e}")
        raise HTTPException(status_code=500, detail=str(e))
