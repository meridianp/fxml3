"""
Risk Limit Enforcement API Router for FXML4.

This module provides REST API endpoints for managing risk limit enforcement,
including real-time monitoring, limit configuration, and violation management.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator

from fxml4.api.auth.audit_logger import AuditEventType, auth_audit_logger
from fxml4.api.auth.auth import get_current_user
from fxml4.api.auth.models import User
from fxml4.api.auth.permissions import (
    check_admin_access,
    check_risk_manager_access,
    require_permission,
)
from fxml4.compliance.risk.limit_enforcement import (
    EnforcementAction,
    LimitType,
    LimitViolation,
    RiskLimit,
    ViolationSeverity,
    risk_limit_enforcer,
)
from fxml4.core.logging import get_logger

router = APIRouter(prefix="/risk-enforcement", tags=["risk-enforcement"])
logger = get_logger(__name__)


# Pydantic models for API
class RiskLimitRequest(BaseModel):
    """Request model for creating/updating a risk limit."""

    limit_id: str = Field(..., description="Unique limit identifier")
    limit_type: str = Field(..., description="Type of risk limit")
    threshold: float = Field(..., description="Risk limit threshold")
    warning_threshold: Optional[float] = Field(
        None, description="Warning threshold (default 80% of limit)"
    )
    currency: str = Field("USD", description="Currency for the limit")
    scope: str = Field(
        "global", description="Scope of the limit (global, account, user, instrument)"
    )
    scope_value: Optional[str] = Field(
        None, description="Specific value for scoped limits"
    )
    enforcement_action: str = Field(
        "alert_only", description="Enforcement action when limit exceeded"
    )
    is_active: bool = Field(True, description="Whether the limit is active")

    @validator("limit_type")
    def validate_limit_type(cls, v):
        valid_types = [t.value for t in LimitType]
        if v not in valid_types:
            raise ValueError(f"limit_type must be one of: {valid_types}")
        return v

    @validator("enforcement_action")
    def validate_enforcement_action(cls, v):
        valid_actions = [a.value for a in EnforcementAction]
        if v not in valid_actions:
            raise ValueError(f"enforcement_action must be one of: {valid_actions}")
        return v


class RiskLimitResponse(BaseModel):
    """Response model for risk limits."""

    limit_id: str
    limit_type: str
    threshold: float
    warning_threshold: Optional[float]
    currency: str
    scope: str
    scope_value: Optional[str]
    enforcement_action: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PositionExposureResponse(BaseModel):
    """Response model for position exposure."""

    symbol: str
    side: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    currency: str
    account_id: Optional[str] = None
    user_id: Optional[str] = None


class RiskExposureResponse(BaseModel):
    """Response model for risk exposure."""

    timestamp: datetime
    total_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    leverage: float
    daily_pnl: float
    unrealized_pnl: float
    position_count: int
    positions_by_symbol: Dict[str, PositionExposureResponse]
    positions_by_currency: Dict[str, float]
    correlation_exposure: Dict[str, float]


class LimitViolationResponse(BaseModel):
    """Response model for limit violations."""

    violation_id: str
    limit_id: str
    limit_type: str
    current_value: float
    threshold: float
    severity: str
    violation_time: datetime
    description: str
    enforcement_action_taken: Optional[str] = None
    is_resolved: bool
    resolution_time: Optional[datetime] = None


class RiskStatusResponse(BaseModel):
    """Response model for overall risk status."""

    timestamp: datetime
    monitoring_active: bool
    total_exposure: float
    leverage: float
    position_count: int
    daily_pnl: float
    unrealized_pnl: float
    active_violations: int
    active_limits: int
    violation_history_count: int
    violations: List[Dict[str, Any]]


@router.get("/status", response_model=RiskStatusResponse)
@require_permission("risk.read")
async def get_risk_status(current_user: User = Depends(check_risk_manager_access)):
    """
    Get current risk enforcement status and metrics.

    Requires: risk.read permission (risk manager or admin)
    """

    try:
        status_data = await risk_limit_enforcer.get_current_risk_status()

        return RiskStatusResponse(
            timestamp=datetime.fromisoformat(status_data["timestamp"]),
            monitoring_active=status_data["monitoring_active"],
            total_exposure=status_data["total_exposure"],
            leverage=status_data["leverage"],
            position_count=status_data["position_count"],
            daily_pnl=status_data["daily_pnl"],
            unrealized_pnl=status_data["unrealized_pnl"],
            active_violations=status_data["active_violations"],
            active_limits=status_data["active_limits"],
            violation_history_count=status_data["violation_history_count"],
            violations=status_data["violations"],
        )

    except Exception as e:
        logger.error(f"Error getting risk status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve risk status",
        )


@router.get("/exposure", response_model=RiskExposureResponse)
@require_permission("risk.read")
async def get_current_exposure(
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    current_user: User = Depends(check_risk_manager_access),
):
    """
    Get current risk exposure details.

    Requires: risk.read permission (risk manager or admin)
    """

    try:
        risk_exposure = await risk_limit_enforcer.risk_monitor.calculate_risk_exposure(
            account_id
        )

        # Convert positions to response format
        positions_response = {}
        for symbol, position in risk_exposure.positions_by_symbol.items():
            positions_response[symbol] = PositionExposureResponse(
                symbol=position.symbol,
                side=position.side,
                quantity=position.quantity,
                avg_price=position.avg_price,
                current_price=position.current_price,
                market_value=position.market_value,
                unrealized_pnl=position.unrealized_pnl,
                currency=position.currency,
                account_id=position.account_id,
                user_id=position.user_id,
            )

        return RiskExposureResponse(
            timestamp=risk_exposure.timestamp,
            total_exposure=risk_exposure.total_exposure,
            net_exposure=risk_exposure.net_exposure,
            long_exposure=risk_exposure.long_exposure,
            short_exposure=risk_exposure.short_exposure,
            leverage=risk_exposure.leverage,
            daily_pnl=risk_exposure.daily_pnl,
            unrealized_pnl=risk_exposure.unrealized_pnl,
            position_count=risk_exposure.position_count,
            positions_by_symbol=positions_response,
            positions_by_currency=risk_exposure.positions_by_currency,
            correlation_exposure=risk_exposure.correlation_exposure,
        )

    except Exception as e:
        logger.error(f"Error getting risk exposure: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve risk exposure",
        )


@router.get("/limits", response_model=List[RiskLimitResponse])
@require_permission("risk.read")
async def list_risk_limits(
    active_only: bool = Query(True, description="Show only active limits"),
    limit_type: Optional[str] = Query(None, description="Filter by limit type"),
    current_user: User = Depends(check_risk_manager_access),
):
    """
    List all configured risk limits.

    Requires: risk.read permission (risk manager or admin)
    """

    try:
        limits = []

        for limit in risk_limit_enforcer.active_limits.values():
            # Apply filters
            if active_only and not limit.is_active:
                continue
            if limit_type and limit.limit_type.value != limit_type:
                continue

            limits.append(
                RiskLimitResponse(
                    limit_id=limit.limit_id,
                    limit_type=limit.limit_type.value,
                    threshold=limit.threshold,
                    warning_threshold=limit.warning_threshold,
                    currency=limit.currency,
                    scope=limit.scope,
                    scope_value=limit.scope_value,
                    enforcement_action=limit.enforcement_action.value,
                    is_active=limit.is_active,
                    created_at=limit.created_at,
                    updated_at=limit.updated_at,
                )
            )

        # Sort by limit_id for consistent ordering
        limits.sort(key=lambda x: x.limit_id)

        return limits

    except Exception as e:
        logger.error(f"Error listing risk limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list risk limits",
        )


@router.post("/limits", response_model=RiskLimitResponse)
@require_permission("risk.update")
async def create_risk_limit(
    limit_request: RiskLimitRequest, current_user: User = Depends(check_admin_access)
):
    """
    Create or update a risk limit.

    Requires: risk.update permission (admin only)
    """

    try:
        # Create RiskLimit object
        risk_limit = RiskLimit(
            limit_id=limit_request.limit_id,
            limit_type=LimitType(limit_request.limit_type),
            threshold=limit_request.threshold,
            warning_threshold=limit_request.warning_threshold,
            currency=limit_request.currency,
            scope=limit_request.scope,
            scope_value=limit_request.scope_value,
            enforcement_action=EnforcementAction(limit_request.enforcement_action),
            is_active=limit_request.is_active,
        )

        # Add to risk enforcer
        await risk_limit_enforcer.add_risk_limit(risk_limit)

        # Log limit creation
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username=current_user.username,
            details={
                "action": "create_risk_limit",
                "limit_id": risk_limit.limit_id,
                "limit_type": risk_limit.limit_type.value,
                "threshold": risk_limit.threshold,
                "enforcement_action": risk_limit.enforcement_action.value,
            },
        )

        return RiskLimitResponse(
            limit_id=risk_limit.limit_id,
            limit_type=risk_limit.limit_type.value,
            threshold=risk_limit.threshold,
            warning_threshold=risk_limit.warning_threshold,
            currency=risk_limit.currency,
            scope=risk_limit.scope,
            scope_value=risk_limit.scope_value,
            enforcement_action=risk_limit.enforcement_action.value,
            is_active=risk_limit.is_active,
            created_at=risk_limit.created_at,
            updated_at=risk_limit.updated_at,
        )

    except Exception as e:
        logger.error(f"Error creating risk limit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create risk limit",
        )


@router.put("/limits/{limit_id}", response_model=RiskLimitResponse)
@require_permission("risk.update")
async def update_risk_limit(
    limit_id: str,
    limit_request: RiskLimitRequest,
    current_user: User = Depends(check_admin_access),
):
    """
    Update an existing risk limit.

    Requires: risk.update permission (admin only)
    """

    try:
        # Check if limit exists
        if limit_id not in risk_limit_enforcer.active_limits:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Risk limit not found: {limit_id}",
            )

        # Update the limit
        limit_request.limit_id = limit_id  # Ensure ID matches

        risk_limit = RiskLimit(
            limit_id=limit_request.limit_id,
            limit_type=LimitType(limit_request.limit_type),
            threshold=limit_request.threshold,
            warning_threshold=limit_request.warning_threshold,
            currency=limit_request.currency,
            scope=limit_request.scope,
            scope_value=limit_request.scope_value,
            enforcement_action=EnforcementAction(limit_request.enforcement_action),
            is_active=limit_request.is_active,
            created_at=risk_limit_enforcer.active_limits[
                limit_id
            ].created_at,  # Keep original
            updated_at=datetime.now(timezone.utc),
        )

        await risk_limit_enforcer.add_risk_limit(risk_limit)

        # Log limit update
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username=current_user.username,
            details={
                "action": "update_risk_limit",
                "limit_id": risk_limit.limit_id,
                "limit_type": risk_limit.limit_type.value,
                "threshold": risk_limit.threshold,
                "enforcement_action": risk_limit.enforcement_action.value,
            },
        )

        return RiskLimitResponse(
            limit_id=risk_limit.limit_id,
            limit_type=risk_limit.limit_type.value,
            threshold=risk_limit.threshold,
            warning_threshold=risk_limit.warning_threshold,
            currency=risk_limit.currency,
            scope=risk_limit.scope,
            scope_value=risk_limit.scope_value,
            enforcement_action=risk_limit.enforcement_action.value,
            is_active=risk_limit.is_active,
            created_at=risk_limit.created_at,
            updated_at=risk_limit.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating risk limit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update risk limit",
        )


@router.delete("/limits/{limit_id}")
@require_permission("risk.update")
async def delete_risk_limit(
    limit_id: str, current_user: User = Depends(check_admin_access)
):
    """
    Delete a risk limit.

    Requires: risk.update permission (admin only)
    """

    try:
        if limit_id not in risk_limit_enforcer.active_limits:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Risk limit not found: {limit_id}",
            )

        await risk_limit_enforcer.remove_risk_limit(limit_id)

        # Log limit deletion
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username=current_user.username,
            details={"action": "delete_risk_limit", "limit_id": limit_id},
        )

        return {"message": f"Risk limit {limit_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting risk limit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete risk limit",
        )


@router.get("/violations", response_model=List[LimitViolationResponse])
@require_permission("risk.read")
async def list_violations(
    active_only: bool = Query(True, description="Show only active violations"),
    limit_type: Optional[str] = Query(None, description="Filter by limit type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(check_risk_manager_access),
):
    """
    List risk limit violations.

    Requires: risk.read permission (risk manager or admin)
    """

    try:
        # Get violations based on filters
        if active_only:
            violations = list(risk_limit_enforcer.active_violations.values())
        else:
            violations = risk_limit_enforcer.violation_history

        # Apply additional filters
        filtered_violations = []
        for violation in violations:
            if limit_type and violation.limit.limit_type.value != limit_type:
                continue
            if severity and violation.severity.value != severity:
                continue
            filtered_violations.append(violation)

        # Sort by violation time (newest first)
        filtered_violations.sort(key=lambda v: v.violation_time, reverse=True)

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_violations = filtered_violations[start_idx:end_idx]

        # Convert to response format
        violation_responses = []
        for violation in paginated_violations:
            violation_responses.append(
                LimitViolationResponse(
                    violation_id=violation.violation_id,
                    limit_id=violation.limit.limit_id,
                    limit_type=violation.limit.limit_type.value,
                    current_value=violation.current_value,
                    threshold=violation.threshold,
                    severity=violation.severity.value,
                    violation_time=violation.violation_time,
                    description=violation.description,
                    enforcement_action_taken=(
                        violation.enforcement_action_taken.value
                        if violation.enforcement_action_taken
                        else None
                    ),
                    is_resolved=violation.is_resolved,
                    resolution_time=violation.resolution_time,
                )
            )

        return violation_responses

    except Exception as e:
        logger.error(f"Error listing violations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list violations",
        )


@router.post("/violations/{violation_id}/resolve")
@require_permission("risk.update")
async def resolve_violation(
    violation_id: str, current_user: User = Depends(check_risk_manager_access)
):
    """
    Mark a violation as manually resolved.

    Requires: risk.update permission (risk manager or admin)
    """

    try:
        if violation_id not in risk_limit_enforcer.active_violations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Active violation not found: {violation_id}",
            )

        await risk_limit_enforcer.resolve_violation(violation_id)

        # Log violation resolution
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username=current_user.username,
            details={"action": "resolve_violation", "violation_id": violation_id},
        )

        return {"message": f"Violation {violation_id} resolved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving violation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve violation",
        )


@router.post("/monitoring/start")
@require_permission("risk.update")
async def start_monitoring(current_user: User = Depends(check_admin_access)):
    """
    Start real-time risk monitoring.

    Requires: risk.update permission (admin only)
    """

    try:
        await risk_limit_enforcer.start_monitoring()

        # Log monitoring start
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username=current_user.username,
            details={"action": "start_risk_monitoring"},
        )

        return {"message": "Real-time risk monitoring started successfully"}

    except Exception as e:
        logger.error(f"Error starting risk monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start risk monitoring",
        )


@router.post("/monitoring/stop")
@require_permission("risk.update")
async def stop_monitoring(current_user: User = Depends(check_admin_access)):
    """
    Stop real-time risk monitoring.

    Requires: risk.update permission (admin only)
    """

    try:
        await risk_limit_enforcer.stop_monitoring()

        # Log monitoring stop
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username=current_user.username,
            details={"action": "stop_risk_monitoring"},
        )

        return {"message": "Real-time risk monitoring stopped successfully"}

    except Exception as e:
        logger.error(f"Error stopping risk monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop risk monitoring",
        )


@router.get("/limit-types")
async def get_available_limit_types():
    """
    Get available risk limit types and enforcement actions.

    Public endpoint - no authentication required.
    """

    limit_types = [
        {
            "value": lt.value,
            "name": lt.value.replace("_", " ").title(),
            "description": f"Monitor and enforce {lt.value.replace('_', ' ')} limits",
        }
        for lt in LimitType
    ]

    enforcement_actions = [
        {
            "value": ea.value,
            "name": ea.value.replace("_", " ").title(),
            "description": f"Action: {ea.value.replace('_', ' ')}",
        }
        for ea in EnforcementAction
    ]

    violation_severities = [
        {
            "value": vs.value,
            "name": vs.value.title(),
            "description": f"Severity level: {vs.value}",
        }
        for vs in ViolationSeverity
    ]

    return {
        "limit_types": limit_types,
        "enforcement_actions": enforcement_actions,
        "violation_severities": violation_severities,
    }


@router.get("/health")
async def risk_enforcement_health():
    """
    Health check endpoint for risk enforcement system.

    Public endpoint - no authentication required.
    """

    try:
        status_data = await risk_limit_enforcer.get_current_risk_status()

        # Simple health indicators
        is_healthy = (
            status_data["active_limits"] > 0
            and status_data["active_violations"] < 10  # Arbitrary threshold
        )

        return {
            "status": "healthy" if is_healthy else "degraded",
            "monitoring_active": status_data["monitoring_active"],
            "active_limits": status_data["active_limits"],
            "active_violations": status_data["active_violations"],
            "total_exposure": status_data["total_exposure"],
            "leverage": status_data["leverage"],
        }

    except Exception as e:
        logger.error(f"Error checking risk enforcement health: {e}")
        return {"status": "unhealthy", "error": str(e)}
