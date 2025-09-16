"""
Trading Engine routes for FXML4 API.

This module provides endpoints for controlling and monitoring the core trading engine.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from fxml4.api.auth.auth import User, get_current_active_user
from fxml4.api.services.trading_engine import (
    TradingEngineState,
    TradingMode,
    trading_engine_service,
)

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)


class StartEngineRequest(BaseModel):
    """Request model for starting the trading engine."""

    symbols: Optional[List[str]] = None
    trading_mode: Optional[TradingMode] = None
    min_confidence: Optional[float] = None


class UpdateConfigRequest(BaseModel):
    """Request model for updating trading engine configuration."""

    trading_mode: Optional[TradingMode] = None
    enabled_symbols: Optional[List[str]] = None
    min_signal_confidence: Optional[float] = None
    auto_execute_confidence: Optional[float] = None
    max_position_size: Optional[float] = None
    position_size_multiplier: Optional[float] = None


@router.get("/trading/status", response_model=Dict[str, Any], tags=["trading"])
async def get_trading_engine_status(
    current_user: User = Depends(get_current_active_user),
):
    """Get current trading engine status and metrics."""
    try:
        status_data = trading_engine_service.get_status()

        return {"status": status_data, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.exception("Error getting trading engine status: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/trading/positions", response_model=Dict[str, Any], tags=["trading"])
async def get_trading_positions(current_user: User = Depends(get_current_active_user)):
    """Get current trading positions."""
    try:
        positions = trading_engine_service.get_positions()

        # Calculate summary metrics
        active_positions = {k: v for k, v in positions.items() if v["quantity"] != 0}
        total_pnl = sum(
            (pos.get("unrealized_pnl", 0.0) or 0.0) + pos.get("realized_pnl", 0.0)
            for pos in positions.values()
        )

        return {
            "positions": positions,
            "summary": {
                "total_positions": len(positions),
                "active_positions": len(active_positions),
                "total_pnl": total_pnl,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Error getting trading positions: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/trading/account", response_model=Dict[str, Any], tags=["trading"])
async def get_account_info(current_user: User = Depends(get_current_active_user)):
    """Get current account information including balance, equity, and margin."""
    try:
        # Get account information from trading engine service
        account_info = trading_engine_service.get_account_info()

        # Get positions to calculate unrealized P&L for equity
        positions = trading_engine_service.get_positions()

        # Calculate total unrealized P&L
        total_unrealized_pnl = sum(
            pos.get("unrealized_pnl", 0.0) or 0.0 for pos in positions.values()
        )

        # Calculate total realized P&L
        total_realized_pnl = sum(
            pos.get("realized_pnl", 0.0) or 0.0 for pos in positions.values()
        )

        # Base account balance (from broker or default for demo)
        base_balance = account_info.get("balance", 100000.0)  # Default demo balance

        # Equity = Balance + Unrealized P&L
        equity = base_balance + total_unrealized_pnl + total_realized_pnl

        # Calculate margin information
        margin_used = account_info.get("margin_used", 0.0)
        margin_available = max(0, equity - margin_used)
        margin_level = (equity / margin_used * 100) if margin_used > 0 else 0

        # Return account info in format expected by frontend Account interface
        return {
            "id": account_info.get("id", "demo_account"),
            "account_number": account_info.get("account_number", "DEMO001"),
            "currency": account_info.get("currency", "USD"),
            "balance": base_balance,
            "equity": equity,
            "margin_used": margin_used,
            "margin_available": margin_available,
            "margin_level": margin_level,
            "unrealized_pnl": total_unrealized_pnl,
            "realized_pnl": total_realized_pnl,
            "total_positions": len(
                [p for p in positions.values() if p.get("quantity", 0) != 0]
            ),
            "total_orders": account_info.get("total_orders", 0),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Error getting account info: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/trading/start", response_model=Dict[str, Any], tags=["trading"])
async def start_trading_engine(
    request: StartEngineRequest, current_user: User = Depends(get_current_active_user)
):
    """Start the trading engine."""
    try:
        logger.info(f"Starting trading engine with symbols: {request.symbols}")

        # Update configuration if provided
        if request.trading_mode:
            trading_engine_service.set_trading_mode(request.trading_mode)

        if request.min_confidence is not None:
            trading_engine_service.set_confidence_threshold(request.min_confidence)

        if request.symbols:
            trading_engine_service.set_enabled_symbols(request.symbols)

        # Start the engine
        await trading_engine_service.start(symbols=request.symbols)

        return {
            "message": "Trading engine started successfully",
            "status": trading_engine_service.get_status(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Error starting trading engine: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/trading/stop", response_model=Dict[str, Any], tags=["trading"])
async def stop_trading_engine(current_user: User = Depends(get_current_active_user)):
    """Stop the trading engine."""
    try:
        logger.info("Stopping trading engine")

        await trading_engine_service.stop()

        return {
            "message": "Trading engine stopped successfully",
            "status": trading_engine_service.get_status(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Error stopping trading engine: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/trading/pause", response_model=Dict[str, Any], tags=["trading"])
async def pause_trading_engine(current_user: User = Depends(get_current_active_user)):
    """Pause the trading engine (stop creating new orders)."""
    try:
        logger.info("Pausing trading engine")

        await trading_engine_service.pause()

        return {
            "message": "Trading engine paused successfully",
            "status": trading_engine_service.get_status(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Error pausing trading engine: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/trading/resume", response_model=Dict[str, Any], tags=["trading"])
async def resume_trading_engine(current_user: User = Depends(get_current_active_user)):
    """Resume the trading engine."""
    try:
        logger.info("Resuming trading engine")

        await trading_engine_service.resume()

        return {
            "message": "Trading engine resumed successfully",
            "status": trading_engine_service.get_status(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Error resuming trading engine: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/trading/config", response_model=Dict[str, Any], tags=["trading"])
async def update_trading_config(
    request: UpdateConfigRequest, current_user: User = Depends(get_current_active_user)
):
    """Update trading engine configuration."""
    try:
        logger.info(f"Updating trading engine configuration: {request}")

        # Update configuration
        if request.trading_mode:
            trading_engine_service.set_trading_mode(request.trading_mode)

        if request.enabled_symbols:
            trading_engine_service.set_enabled_symbols(request.enabled_symbols)

        if request.min_signal_confidence is not None:
            trading_engine_service.set_confidence_threshold(
                request.min_signal_confidence
            )

        if request.auto_execute_confidence is not None:
            trading_engine_service.config.auto_execute_confidence = (
                request.auto_execute_confidence
            )

        if request.max_position_size is not None:
            trading_engine_service.config.max_position_size = request.max_position_size

        if request.position_size_multiplier is not None:
            trading_engine_service.config.position_size_multiplier = (
                request.position_size_multiplier
            )

        return {
            "message": "Trading engine configuration updated successfully",
            "config": {
                "trading_mode": trading_engine_service.config.trading_mode.value,
                "enabled_symbols": list(trading_engine_service.config.enabled_symbols),
                "min_signal_confidence": trading_engine_service.config.min_signal_confidence,
                "auto_execute_confidence": trading_engine_service.config.auto_execute_confidence,
                "max_position_size": trading_engine_service.config.max_position_size,
                "position_size_multiplier": trading_engine_service.config.position_size_multiplier,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Error updating trading configuration: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/trading/metrics", response_model=Dict[str, Any], tags=["trading"])
async def get_trading_metrics(current_user: User = Depends(get_current_active_user)):
    """Get detailed trading metrics."""
    try:
        status_data = trading_engine_service.get_status()
        positions = trading_engine_service.get_positions()

        # Calculate additional metrics
        active_positions = [p for p in positions.values() if p["quantity"] != 0]
        long_positions = [p for p in active_positions if p["quantity"] > 0]
        short_positions = [p for p in active_positions if p["quantity"] < 0]

        total_unrealized_pnl = sum(
            p.get("unrealized_pnl", 0) or 0 for p in positions.values()
        )
        total_realized_pnl = sum(p.get("realized_pnl", 0) for p in positions.values())

        return {
            "engine_metrics": status_data["metrics"],
            "position_metrics": {
                "total_positions": len(positions),
                "active_positions": len(active_positions),
                "long_positions": len(long_positions),
                "short_positions": len(short_positions),
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_realized_pnl": total_realized_pnl,
                "total_pnl": total_unrealized_pnl + total_realized_pnl,
            },
            "state": status_data["state"],
            "uptime_hours": status_data["metrics"]["uptime_seconds"] / 3600.0,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Error getting trading metrics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/trading/health", response_model=Dict[str, Any], tags=["trading"])
async def get_trading_health(current_user: User = Depends(get_current_active_user)):
    """Get trading engine health status."""
    try:
        status_data = trading_engine_service.get_status()

        # Determine health status
        is_healthy = (
            status_data["state"] in ["active", "paused"]
            and status_data.get("error_message") is None
            and status_data["metrics"]["uptime_seconds"] > 0
        )

        health_issues = []

        if status_data["state"] == "error":
            health_issues.append("Engine in error state")

        if status_data.get("error_message"):
            health_issues.append(f"Error: {status_data['error_message']}")

        if status_data["metrics"]["uptime_seconds"] == 0:
            health_issues.append("Engine not started")

        return {
            "healthy": is_healthy,
            "status": status_data["state"],
            "issues": health_issues,
            "last_signal_time": status_data["metrics"].get("last_signal_time"),
            "last_trade_time": status_data["metrics"].get("last_trade_time"),
            "uptime_seconds": status_data["metrics"]["uptime_seconds"],
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Error getting trading health: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/trading/config", response_model=Dict[str, Any], tags=["trading"])
async def get_trading_config(current_user: User = Depends(get_current_active_user)):
    """Get current trading engine configuration."""
    try:
        config = trading_engine_service.config

        return {
            "trading_mode": config.trading_mode.value,
            "enabled_symbols": list(config.enabled_symbols),
            "signal_config": {
                "min_signal_confidence": config.min_signal_confidence,
                "signal_timeout_minutes": config.signal_timeout_minutes,
                "auto_execute_confidence": config.auto_execute_confidence,
            },
            "risk_config": {
                "max_position_size": config.max_position_size,
                "max_daily_volume": config.max_daily_volume,
                "max_orders_per_hour": config.max_orders_per_hour,
                "position_size_multiplier": config.position_size_multiplier,
            },
            "system_config": {
                "max_concurrent_orders": config.max_concurrent_orders,
                "order_timeout_minutes": config.order_timeout_minutes,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Error getting trading configuration: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# Startup event to initialize trading engine
@router.on_event("startup")
async def startup_trading_engine():
    """Initialize the trading engine on startup."""
    try:
        await trading_engine_service.initialize()
        logger.info("Trading engine initialized")
    except Exception as e:
        logger.error(f"Failed to initialize trading engine: {e}")


# Shutdown event to cleanup trading engine
@router.on_event("shutdown")
async def shutdown_trading_engine():
    """Cleanup the trading engine on shutdown."""
    try:
        await trading_engine_service.close()
        logger.info("Trading engine closed")
    except Exception as e:
        logger.error(f"Error closing trading engine: {e}")
