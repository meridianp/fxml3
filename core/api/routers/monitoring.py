"""Monitoring Dashboard API Router.

This module provides REST API endpoints for monitoring the broker
abstraction system, including adapter status, performance metrics,
and system health.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ...brokers.adapters.base import ConnectionStatus
from ...brokers.adapters.manager import BrokerAdapterManager
from ...brokers.risk import FXRiskManager
from ...brokers.risk.integration import RiskAwareBrokerManager
from ..dependencies import (
    get_adapter_manager,
    get_risk_broker_manager,
    get_risk_manager,
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


# Pydantic models
class SystemHealthResponse(BaseModel):
    """System health check response."""

    status: str
    timestamp: datetime
    components: Dict[str, Dict[str, Any]]


class AdapterStatusResponse(BaseModel):
    """Adapter status response."""

    adapter_id: str
    broker_type: str
    broker_name: str
    status: str
    connected: bool
    ready: bool
    last_heartbeat: Optional[datetime]
    metrics: Dict[str, Any]
    error_message: Optional[str]


@router.get("/health")
async def get_system_health(
    adapter_manager: BrokerAdapterManager = Depends(get_adapter_manager),
    risk_manager: FXRiskManager = Depends(get_risk_manager),
) -> SystemHealthResponse:
    """Get overall system health status."""
    try:
        components = {}
        overall_status = "healthy"

        # Check adapters
        adapters = adapter_manager.get_all_adapters()
        adapter_statuses = []

        for adapter_id, adapter in adapters.items():
            adapter_healthy = adapter.is_connected() and adapter.is_ready()
            adapter_statuses.append(adapter_healthy)

            components[f"adapter_{adapter_id}"] = {
                "type": "broker_adapter",
                "status": "healthy" if adapter_healthy else "unhealthy",
                "connected": adapter.is_connected(),
                "ready": adapter.is_ready(),
                "last_check": datetime.utcnow().isoformat(),
            }

        # Determine adapter component health
        if adapters:
            healthy_adapters = sum(adapter_statuses)
            adapter_health_pct = healthy_adapters / len(adapters)

            if adapter_health_pct < 0.5:
                overall_status = "critical"
                components["adapters_overall"] = {
                    "type": "service",
                    "status": "critical",
                    "healthy_count": healthy_adapters,
                    "total_count": len(adapters),
                    "health_percentage": adapter_health_pct * 100,
                }
            elif adapter_health_pct < 1.0:
                overall_status = "degraded"
                components["adapters_overall"] = {
                    "type": "service",
                    "status": "degraded",
                    "healthy_count": healthy_adapters,
                    "total_count": len(adapters),
                    "health_percentage": adapter_health_pct * 100,
                }
            else:
                components["adapters_overall"] = {
                    "type": "service",
                    "status": "healthy",
                    "healthy_count": healthy_adapters,
                    "total_count": len(adapters),
                    "health_percentage": 100,
                }
        else:
            overall_status = "critical"
            components["adapters_overall"] = {
                "type": "service",
                "status": "critical",
                "message": "No adapters configured",
            }

        # Check risk manager
        try:
            risk_summary = risk_manager.get_risk_summary()
            components["risk_manager"] = {
                "type": "service",
                "status": "healthy",
                "enabled_checks": len(risk_summary["enabled_checks"]),
                "total_notional": risk_summary["metrics"]["total_notional"],
                "open_orders": risk_summary["metrics"]["open_orders"],
            }
        except Exception as e:
            overall_status = "degraded"
            components["risk_manager"] = {
                "type": "service",
                "status": "unhealthy",
                "error": str(e),
            }

        return SystemHealthResponse(
            status=overall_status, timestamp=datetime.utcnow(), components=components
        )

    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/adapters")
async def get_adapter_status(
    adapter_manager: BrokerAdapterManager = Depends(get_adapter_manager),
) -> Dict[str, Any]:
    """Get status of all broker adapters."""
    try:
        adapters = adapter_manager.get_all_adapters()
        adapter_statuses = []

        for adapter_id, adapter in adapters.items():
            status_info = {
                "adapter_id": adapter_id,
                "broker_type": adapter.config.broker_type,
                "broker_name": adapter.config.broker_name,
                "status": adapter.adapter_connection.status.value,
                "connected": adapter.adapter_connection.is_connected(),
                "ready": adapter.adapter_connection.is_ready(),
                "enabled": adapter.config.enabled,
                "last_heartbeat": (
                    adapter.metrics.last_connect_time.isoformat()
                    if adapter.metrics.last_connect_time
                    else None
                ),
                "metrics": {
                    "total_orders": adapter.metrics.total_orders,
                    "filled_orders": adapter.metrics.filled_orders,
                    "rejected_orders": adapter.metrics.rejected_orders,
                    "cancelled_orders": adapter.metrics.cancelled_orders,
                    "failed_orders": adapter.metrics.failed_orders,
                    "uptime_seconds": (
                        (datetime.utcnow() - adapter.metrics.start_time).total_seconds()
                        if adapter.metrics.start_time
                        else 0
                    ),
                },
                "error_message": adapter.adapter_connection.error,
                "features": adapter.config.features,
            }
            adapter_statuses.append(status_info)

        return {
            "status": "success",
            "data": {
                "adapters": adapter_statuses,
                "total_count": len(adapter_statuses),
                "connected_count": sum(1 for a in adapter_statuses if a["connected"]),
                "ready_count": sum(1 for a in adapter_statuses if a["ready"]),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting adapter status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/adapters/{adapter_id}")
async def get_adapter_details(
    adapter_id: str,
    adapter_manager: BrokerAdapterManager = Depends(get_adapter_manager),
) -> Dict[str, Any]:
    """Get detailed information about a specific adapter."""
    try:
        adapter = adapter_manager.get_adapter(adapter_id)
        if not adapter:
            raise HTTPException(
                status_code=404, detail=f"Adapter {adapter_id} not found"
            )

        # Get detailed metrics
        details = {
            "adapter_id": adapter_id,
            "config": {
                "broker_type": adapter.config.broker_type,
                "broker_name": adapter.config.broker_name,
                "enabled": adapter.config.enabled,
                "features": adapter.config.features,
            },
            "connection": {
                "status": adapter.adapter_connection.status.value,
                "connected": adapter.adapter_connection.is_connected(),
                "ready": adapter.adapter_connection.is_ready(),
                "authenticated": adapter.adapter_connection._authenticated,
                "error": adapter.adapter_connection.error,
                "last_error_time": (
                    adapter.adapter_connection.last_error_time.isoformat()
                    if adapter.adapter_connection.last_error_time
                    else None
                ),
            },
            "metrics": {
                "start_time": (
                    adapter.metrics.start_time.isoformat()
                    if adapter.metrics.start_time
                    else None
                ),
                "last_connect_time": (
                    adapter.metrics.last_connect_time.isoformat()
                    if adapter.metrics.last_connect_time
                    else None
                ),
                "last_disconnect_time": (
                    adapter.metrics.last_disconnect_time.isoformat()
                    if adapter.metrics.last_disconnect_time
                    else None
                ),
                "total_orders": adapter.metrics.total_orders,
                "filled_orders": adapter.metrics.filled_orders,
                "rejected_orders": adapter.metrics.rejected_orders,
                "cancelled_orders": adapter.metrics.cancelled_orders,
                "failed_orders": adapter.metrics.failed_orders,
                "connection_attempts": adapter.metrics.connection_attempts,
                "reconnection_count": adapter.metrics.reconnection_count,
            },
        }

        # Add adapter-specific information
        if hasattr(adapter, "session") and adapter.session:
            details["session"] = {
                "state": (
                    adapter.session.state.value
                    if hasattr(adapter.session, "state")
                    else "unknown"
                ),
                "messages_sent": (
                    getattr(adapter.session.stats, "messages_sent", 0)
                    if hasattr(adapter.session, "stats")
                    else 0
                ),
                "messages_received": (
                    getattr(adapter.session.stats, "messages_received", 0)
                    if hasattr(adapter.session, "stats")
                    else 0
                ),
            }

        return {
            "status": "success",
            "data": details,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting adapter details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/adapters/{adapter_id}/restart")
async def restart_adapter(
    adapter_id: str,
    adapter_manager: BrokerAdapterManager = Depends(get_adapter_manager),
) -> Dict[str, Any]:
    """Restart a specific adapter."""
    try:
        adapter = adapter_manager.get_adapter(adapter_id)
        if not adapter:
            raise HTTPException(
                status_code=404, detail=f"Adapter {adapter_id} not found"
            )

        # Disconnect and reconnect
        await adapter.disconnect()
        await asyncio.sleep(1)  # Brief pause
        success = await adapter.connect()

        return {
            "status": "success" if success else "failed",
            "message": f"Adapter {adapter_id} restart {'successful' if success else 'failed'}",
            "data": {
                "adapter_id": adapter_id,
                "connected": adapter.adapter_connection.is_connected(),
                "ready": adapter.adapter_connection.is_ready(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restarting adapter {adapter_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/summary")
async def get_metrics_summary(
    adapter_manager: BrokerAdapterManager = Depends(get_adapter_manager),
    risk_manager: FXRiskManager = Depends(get_risk_manager),
) -> Dict[str, Any]:
    """Get aggregated metrics summary."""
    try:
        # Aggregate adapter metrics
        total_orders = 0
        total_filled = 0
        total_rejected = 0
        total_cancelled = 0
        total_failed = 0

        adapters = adapter_manager.get_all_adapters()
        for adapter in adapters.values():
            total_orders += adapter.metrics.total_orders
            total_filled += adapter.metrics.filled_orders
            total_rejected += adapter.metrics.rejected_orders
            total_cancelled += adapter.metrics.cancelled_orders
            total_failed += adapter.metrics.failed_orders

        # Get risk metrics
        risk_summary = risk_manager.get_risk_summary()

        return {
            "status": "success",
            "data": {
                "orders": {
                    "total": total_orders,
                    "filled": total_filled,
                    "rejected": total_rejected,
                    "cancelled": total_cancelled,
                    "failed": total_failed,
                    "success_rate": (
                        (total_filled / total_orders * 100) if total_orders > 0 else 0
                    ),
                },
                "risk": {
                    "total_notional": risk_summary["metrics"]["total_notional"],
                    "daily_pnl": risk_summary["metrics"]["daily_pnl"],
                    "open_orders": risk_summary["metrics"]["open_orders"],
                    "position_count": risk_summary["metrics"]["position_count"],
                },
                "adapters": {
                    "total": len(adapters),
                    "connected": sum(
                        1
                        for a in adapters.values()
                        if a.adapter_connection.is_connected()
                    ),
                    "ready": sum(
                        1 for a in adapters.values() if a.adapter_connection.is_ready()
                    ),
                },
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/performance")
async def get_performance_metrics(
    adapter_manager: BrokerAdapterManager = Depends(get_adapter_manager),
) -> Dict[str, Any]:
    """Get performance metrics for all adapters."""
    try:
        performance_data = {}

        adapters = adapter_manager.get_all_adapters()
        for adapter_id, adapter in adapters.items():
            uptime = 0
            if adapter.metrics.start_time:
                uptime = (
                    datetime.utcnow() - adapter.metrics.start_time
                ).total_seconds()

            performance_data[adapter_id] = {
                "uptime_seconds": uptime,
                "uptime_hours": uptime / 3600,
                "orders_per_hour": (
                    (adapter.metrics.total_orders / (uptime / 3600))
                    if uptime > 0
                    else 0
                ),
                "connection_attempts": adapter.metrics.connection_attempts,
                "reconnection_count": adapter.metrics.reconnection_count,
                "stability_score": max(
                    0, 100 - (adapter.metrics.reconnection_count * 10)
                ),  # Simple stability metric
            }

        return {
            "status": "success",
            "data": {
                "performance": performance_data,
                "summary": {
                    "avg_uptime_hours": (
                        sum(p["uptime_hours"] for p in performance_data.values())
                        / len(performance_data)
                        if performance_data
                        else 0
                    ),
                    "total_reconnections": sum(
                        p["reconnection_count"] for p in performance_data.values()
                    ),
                    "avg_stability_score": (
                        sum(p["stability_score"] for p in performance_data.values())
                        / len(performance_data)
                        if performance_data
                        else 0
                    ),
                },
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time monitoring updates."""
    await manager.connect(websocket)

    try:
        while True:
            # Send periodic updates every 5 seconds
            await asyncio.sleep(5)

            # Get current system status
            try:
                # This is a simplified version - in production, you'd want to optimize this
                health_response = await get_system_health()

                update = {
                    "type": "health_update",
                    "data": health_response.dict(),
                    "timestamp": datetime.utcnow().isoformat(),
                }

                await manager.send_personal_message(str(update), websocket)

            except Exception as e:
                logger.error(f"Error sending WebSocket update: {e}")
                break

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.get("/logs/recent")
async def get_recent_logs(lines: int = 100, level: str = "INFO") -> Dict[str, Any]:
    """Get recent log entries (simplified implementation)."""
    try:
        # This is a placeholder - in production, you'd read from actual log files
        # or a centralized logging system

        sample_logs = [
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                "level": "INFO",
                "logger": "fxml4.brokers.adapters.ib_adapter",
                "message": "Order submitted successfully: ORD_12345678",
            },
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=3)).isoformat(),
                "level": "WARNING",
                "logger": "fxml4.brokers.risk.manager",
                "message": "Position limit approaching for EUR/USD",
            },
            {
                "timestamp": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
                "level": "INFO",
                "logger": "fxml4.brokers.adapters.fix_adapter",
                "message": "Heartbeat sent to FIX session",
            },
        ]

        # Filter by level if specified
        filtered_logs = [
            log for log in sample_logs if log["level"] == level or level == "ALL"
        ]

        return {
            "status": "success",
            "data": {
                "logs": filtered_logs[-lines:],  # Return last N lines
                "total_count": len(filtered_logs),
                "level_filter": level,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting recent logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
