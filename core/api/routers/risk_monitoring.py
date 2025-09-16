"""
Risk monitoring API endpoints.

This module provides REST API endpoints for real-time risk monitoring,
alerts, and dashboard data.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from fxml4.api.auth.auth_enhanced import get_current_user, require_role
from fxml4.api.auth.models import User
from fxml4.brokers.risk.monitoring import (
    AlertSeverity,
    MetricSnapshot,
    MetricType,
    RiskAlert,
    RiskMonitor,
)

router = APIRouter(
    prefix="/api/v1/risk/monitoring",
    tags=["risk-monitoring"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)


# Global risk monitor instance (would be dependency injected in production)
risk_monitor = RiskMonitor()


# Pydantic models
class AlertResponse(BaseModel):
    """Risk alert response model."""

    alert_id: str
    timestamp: datetime
    severity: str
    metric_type: str
    message: str
    details: Dict[str, Any]
    acknowledged: bool
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


class MetricResponse(BaseModel):
    """Metric snapshot response model."""

    timestamp: datetime
    metric_type: str
    value: float
    threshold: Optional[float] = None
    status: str


class MonitoringStatusResponse(BaseModel):
    """Monitoring system status response."""

    is_running: bool
    active_alerts: int
    critical_alerts: int
    metric_counts: Dict[str, int]
    last_update: str


class AcknowledgeAlertRequest(BaseModel):
    """Request to acknowledge an alert."""

    alert_id: str = Field(..., description="ID of alert to acknowledge")


class MetricSubscriptionRequest(BaseModel):
    """Request to subscribe to metric updates."""

    metric_types: List[str] = Field(
        ..., description="List of metric types to subscribe to"
    )


class DashboardDataResponse(BaseModel):
    """Dashboard data response."""

    positions: Dict[str, Any]
    portfolio_metrics: Dict[str, Any]
    recent_alerts: List[AlertResponse]
    metric_summaries: Dict[str, Dict[str, Any]]
    system_health: Dict[str, Any]


# Endpoints


@router.get("/status", response_model=MonitoringStatusResponse)
async def get_monitoring_status(current_user: User = Depends(get_current_user)):
    """Get current monitoring system status."""
    return MonitoringStatusResponse(**risk_monitor.get_monitoring_status())


@router.get("/alerts", response_model=List[AlertResponse])
async def get_active_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
):
    """Get active risk alerts."""
    severity_enum = None
    if severity:
        try:
            severity_enum = AlertSeverity[severity.upper()]
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid severity. Must be one of: {[s.name for s in AlertSeverity]}",
            )

    alerts = risk_monitor.get_active_alerts(severity=severity_enum)

    # Convert to response model
    return [
        AlertResponse(
            alert_id=alert.alert_id,
            timestamp=alert.timestamp,
            severity=alert.severity.name,
            metric_type=alert.metric_type.value,
            message=alert.message,
            details=alert.details,
            acknowledged=alert.acknowledged,
            acknowledged_by=alert.acknowledged_by,
            acknowledged_at=alert.acknowledged_at,
        )
        for alert in alerts[:limit]
    ]


@router.post("/alerts/acknowledge", status_code=204)
async def acknowledge_alert(
    request: AcknowledgeAlertRequest,
    current_user: User = Depends(require_role("risk_manager")),
):
    """Acknowledge a risk alert."""
    success = risk_monitor.acknowledge_alert(request.alert_id, current_user.username)

    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")


@router.get("/metrics/{metric_type}", response_model=List[MetricResponse])
async def get_metric_history(
    metric_type: str,
    hours: int = Query(1, ge=1, le=24, description="Hours of history"),
    current_user: User = Depends(get_current_user),
):
    """Get metric history."""
    try:
        metric_enum = MetricType[metric_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric type. Must be one of: {[m.value for m in MetricType]}",
        )

    snapshots = risk_monitor.get_metric_history(metric_enum, hours=hours)

    return [
        MetricResponse(
            timestamp=s.timestamp,
            metric_type=s.metric_type.value,
            value=s.value,
            threshold=s.threshold,
            status=s.status,
        )
        for s in snapshots
    ]


@router.get("/metrics/{metric_type}/export")
async def export_metrics(
    metric_type: str,
    format: str = Query("json", regex="^(json|csv)$"),
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user),
):
    """Export metric data."""
    try:
        metric_enum = MetricType[metric_type.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid metric type")

    # Get data
    data = risk_monitor.export_metrics(metric_enum, format=format)

    # Return appropriate response
    if format == "csv":
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=risk_metrics_{metric_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            },
        )
    else:
        return StreamingResponse(
            iter([data]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=risk_metrics_{metric_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            },
        )


@router.get("/dashboard", response_model=DashboardDataResponse)
async def get_dashboard_data(current_user: User = Depends(get_current_user)):
    """Get comprehensive dashboard data."""
    # This would integrate with the risk manager
    # For now, return mock data structure

    # Get recent alerts
    recent_alerts = risk_monitor.get_active_alerts()[:10]

    # Get metric summaries
    metric_summaries = {}
    for metric_type in MetricType:
        history = risk_monitor.get_metric_history(metric_type, hours=1)
        if history:
            latest = history[-1]
            metric_summaries[metric_type.value] = {
                "current_value": latest.value,
                "threshold": latest.threshold,
                "status": latest.status,
                "trend": _calculate_trend(history),
            }

    return DashboardDataResponse(
        positions={},  # Would come from risk manager
        portfolio_metrics={},  # Would come from risk manager
        recent_alerts=[
            AlertResponse(
                alert_id=alert.alert_id,
                timestamp=alert.timestamp,
                severity=alert.severity.name,
                metric_type=alert.metric_type.value,
                message=alert.message,
                details=alert.details,
                acknowledged=alert.acknowledged,
                acknowledged_by=alert.acknowledged_by,
                acknowledged_at=alert.acknowledged_at,
            )
            for alert in recent_alerts
        ],
        metric_summaries=metric_summaries,
        system_health=risk_monitor.get_monitoring_status(),
    )


@router.websocket("/stream")
async def websocket_risk_stream(
    websocket: WebSocket, token: str = Query(..., description="Authentication token")
):
    """WebSocket endpoint for real-time risk updates."""
    # Validate token (simplified - in production use proper auth)
    # For now, just check if token exists
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    await websocket.accept()

    # Queue for updates
    update_queue = asyncio.Queue()

    # Subscribe to updates
    def metric_callback(snapshot: MetricSnapshot):
        asyncio.create_task(
            update_queue.put(
                {
                    "type": "metric_update",
                    "data": {
                        "timestamp": snapshot.timestamp.isoformat(),
                        "metric_type": snapshot.metric_type.value,
                        "value": snapshot.value,
                        "status": snapshot.status,
                    },
                }
            )
        )

    def alert_callback(alert: RiskAlert):
        asyncio.create_task(
            update_queue.put(
                {
                    "type": "alert",
                    "data": {
                        "alert_id": alert.alert_id,
                        "severity": alert.severity.name,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                    },
                }
            )
        )

    # Subscribe to all metrics
    for metric_type in MetricType:
        risk_monitor.subscribe_to_metric(metric_type, metric_callback)

    risk_monitor.subscribe_to_alerts(alert_callback)

    try:
        # Send initial status
        await websocket.send_json(
            {"type": "status", "data": risk_monitor.get_monitoring_status()}
        )

        # Stream updates
        while True:
            # Wait for update or heartbeat
            try:
                update = await asyncio.wait_for(update_queue.get(), timeout=30.0)
                await websocket.send_json(update)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))


@router.post("/test/alert")
async def create_test_alert(
    severity: str = Query(..., description="Alert severity"),
    message: str = Query(..., description="Alert message"),
    current_user: User = Depends(require_role("admin")),
):
    """Create a test alert (admin only)."""
    try:
        severity_enum = AlertSeverity[severity.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid severity")

    # Create test alert
    risk_monitor._create_alert(
        severity=severity_enum,
        metric_type=MetricType.SYSTEM_HEALTH,
        message=f"[TEST] {message}",
        details={"test": True, "created_by": current_user.username},
    )

    return {"message": "Test alert created"}


# Helper functions


def _calculate_trend(history: List[MetricSnapshot]) -> str:
    """Calculate trend from metric history."""
    if len(history) < 2:
        return "stable"

    # Simple trend calculation
    recent_values = [s.value for s in history[-10:]]
    if len(recent_values) < 2:
        return "stable"

    # Calculate average change
    changes = [
        recent_values[i] - recent_values[i - 1] for i in range(1, len(recent_values))
    ]
    avg_change = sum(changes) / len(changes)

    # Determine trend
    if abs(avg_change) < 0.01:
        return "stable"
    elif avg_change > 0:
        return "increasing"
    else:
        return "decreasing"
