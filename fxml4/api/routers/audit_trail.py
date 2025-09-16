"""
Immutable Audit Trail API Router for FXML4.

This module provides REST API endpoints for managing and querying the
immutable audit trail system with cryptographic integrity verification.
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
from fxml4.compliance.audit.immutable_trail import (
    AuditEventCategory,
    IntegrityLevel,
    immutable_audit_trail,
    log_system_event,
)
from fxml4.core.logging import get_logger

router = APIRouter(prefix="/audit-trail", tags=["audit-trail"])
logger = get_logger(__name__)


# Pydantic models for API
class AuditEventRequest(BaseModel):
    """Request model for logging an audit event."""

    category: str = Field(..., description="Event category")
    event_type: str = Field(..., description="Specific event type")
    resource_type: Optional[str] = Field(None, description="Type of resource affected")
    resource_id: Optional[str] = Field(None, description="Specific resource identifier")
    action: Optional[str] = Field(None, description="Action performed")
    details: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Event details"
    )
    before_state: Optional[Dict[str, Any]] = Field(
        None, description="State before change"
    )
    after_state: Optional[Dict[str, Any]] = Field(
        None, description="State after change"
    )
    outcome: str = Field("success", description="Event outcome")
    error_message: Optional[str] = Field(
        None, description="Error details if outcome != success"
    )
    correlation_id: Optional[str] = Field(
        None, description="Correlation ID for related events"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @validator("category")
    def validate_category(cls, v):
        valid_categories = [c.value for c in AuditEventCategory]
        if v not in valid_categories:
            raise ValueError(f"category must be one of: {valid_categories}")
        return v


class AuditEventResponse(BaseModel):
    """Response model for audit events."""

    record_id: str
    sequence_number: int
    timestamp: datetime
    category: str
    event_type: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    details: Dict[str, Any]
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    outcome: str
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None
    block_id: Optional[str] = None
    block_sequence: Optional[int] = None
    metadata: Dict[str, Any]


class IntegrityVerificationResponse(BaseModel):
    """Response model for integrity verification."""

    record_id: Optional[str] = None
    valid: bool
    checks: Dict[str, bool] = Field(default_factory=dict)
    error: Optional[str] = None
    total_records: Optional[int] = None
    verified_records: Optional[int] = None
    broken_chains: List[Dict[str, Any]] = Field(default_factory=list)
    invalid_signatures: List[Dict[str, Any]] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class AuditStatisticsResponse(BaseModel):
    """Response model for audit trail statistics."""

    total_records: int
    records_by_category: Dict[str, int]
    records_by_outcome: Dict[str, int]
    recent_records_24h: int
    blocks_created: int
    pending_records: int
    integrity_violations: int
    last_block_time: Optional[str] = None
    integrity_level: str
    is_running: bool


@router.post("/events", response_model=Dict[str, str])
@require_permission("system.admin")
async def log_audit_event(
    event_request: AuditEventRequest,
    request_info: Dict[str, str] = None,
    current_user: User = Depends(check_admin_access),
):
    """
    Log an audit event to the immutable trail.

    Requires: system.admin permission (admin only)
    """

    try:
        # Extract request information (would come from FastAPI request context)
        session_id = None  # Would extract from JWT token
        source_ip = None  # Would extract from request headers
        user_agent = None  # Would extract from request headers

        # Log the audit event
        record_id = await immutable_audit_trail.log_audit_event(
            category=AuditEventCategory(event_request.category),
            event_type=event_request.event_type,
            user_id=current_user.username,
            session_id=session_id,
            source_ip=source_ip,
            user_agent=user_agent,
            resource_type=event_request.resource_type,
            resource_id=event_request.resource_id,
            action=event_request.action,
            details=event_request.details,
            before_state=event_request.before_state,
            after_state=event_request.after_state,
            outcome=event_request.outcome,
            error_message=event_request.error_message,
            correlation_id=event_request.correlation_id,
            metadata=event_request.metadata,
        )

        return {"record_id": record_id, "message": "Audit event logged successfully"}

    except Exception as e:
        logger.error(f"Error logging audit event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log audit event",
        )


@router.get("/events", response_model=List[AuditEventResponse])
@require_permission("system.monitoring")
async def search_audit_events(
    category: Optional[str] = Query(None, description="Filter by event category"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    outcome: Optional[str] = Query(None, description="Filter by outcome"),
    correlation_id: Optional[str] = Query(None, description="Filter by correlation ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(check_risk_manager_access),
):
    """
    Search audit events with various filters.

    Requires: system.monitoring permission (risk manager or admin)
    """

    try:
        # Convert category string to enum if provided
        category_enum = None
        if category:
            try:
                category_enum = AuditEventCategory(category)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid category: {category}",
                )

        # Search audit records
        records = await immutable_audit_trail.search_audit_records(
            category=category_enum,
            event_type=event_type,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            start_date=start_date,
            end_date=end_date,
            outcome=outcome,
            correlation_id=correlation_id,
            limit=limit,
            offset=offset,
        )

        # Convert to response format
        audit_responses = []
        for record in records:
            audit_responses.append(
                AuditEventResponse(
                    record_id=record["record_id"],
                    sequence_number=record["sequence_number"],
                    timestamp=datetime.fromisoformat(record["timestamp"]),
                    category=record["category"],
                    event_type=record["event_type"],
                    user_id=record["user_id"],
                    session_id=record["session_id"],
                    source_ip=record["source_ip"],
                    user_agent=record["user_agent"],
                    resource_type=record["resource_type"],
                    resource_id=record["resource_id"],
                    action=record["action"],
                    details=record["details"],
                    before_state=record["before_state"],
                    after_state=record["after_state"],
                    outcome=record["outcome"],
                    error_message=record["error_message"],
                    correlation_id=record["correlation_id"],
                    block_id=record["block_id"],
                    block_sequence=record["block_sequence"],
                    metadata=record["metadata"],
                )
            )

        return audit_responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching audit events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search audit events",
        )


@router.get("/events/{record_id}/verify", response_model=IntegrityVerificationResponse)
@require_permission("system.monitoring")
async def verify_record_integrity(
    record_id: str, current_user: User = Depends(check_risk_manager_access)
):
    """
    Verify the integrity of a specific audit record.

    Requires: system.monitoring permission (risk manager or admin)
    """

    try:
        verification_result = await immutable_audit_trail.verify_record_integrity(
            record_id
        )

        return IntegrityVerificationResponse(
            record_id=verification_result.get("record_id"),
            valid=verification_result["valid"],
            checks=verification_result.get("checks", {}),
            error=verification_result.get("error"),
        )

    except Exception as e:
        logger.error(f"Error verifying record integrity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify record integrity",
        )


@router.get("/integrity/verify", response_model=IntegrityVerificationResponse)
@require_permission("system.monitoring")
async def verify_chain_integrity(
    start_date: Optional[datetime] = Query(
        None, description="Start date for verification"
    ),
    end_date: Optional[datetime] = Query(None, description="End date for verification"),
    current_user: User = Depends(check_admin_access),
):
    """
    Verify the integrity of the audit trail chain within a date range.

    Requires: system.monitoring permission (admin only for chain verification)
    """

    try:
        verification_result = await immutable_audit_trail.verify_chain_integrity(
            start_date=start_date, end_date=end_date
        )

        return IntegrityVerificationResponse(
            valid=verification_result["valid"],
            total_records=verification_result.get("total_records"),
            verified_records=verification_result.get("verified_records"),
            broken_chains=verification_result.get("broken_chains", []),
            invalid_signatures=verification_result.get("invalid_signatures", []),
            start_date=verification_result.get("start_date"),
            end_date=verification_result.get("end_date"),
            error=verification_result.get("error"),
        )

    except Exception as e:
        logger.error(f"Error verifying chain integrity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify chain integrity",
        )


@router.get("/statistics", response_model=AuditStatisticsResponse)
@require_permission("system.monitoring")
async def get_audit_statistics(current_user: User = Depends(check_risk_manager_access)):
    """
    Get comprehensive audit trail statistics.

    Requires: system.monitoring permission (risk manager or admin)
    """

    try:
        stats = await immutable_audit_trail.get_audit_statistics()

        if "error" in stats:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve statistics: {stats['error']}",
            )

        return AuditStatisticsResponse(
            total_records=stats["total_records"],
            records_by_category=stats["records_by_category"],
            records_by_outcome=stats["records_by_outcome"],
            recent_records_24h=stats["recent_records_24h"],
            blocks_created=stats["blocks_created"],
            pending_records=stats["pending_records"],
            integrity_violations=stats["integrity_violations"],
            last_block_time=stats["last_block_time"],
            integrity_level=stats["integrity_level"],
            is_running=stats["is_running"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting audit statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit statistics",
        )


@router.post("/services/start")
@require_permission("system.admin")
async def start_audit_services(current_user: User = Depends(check_admin_access)):
    """
    Start audit trail background services.

    Requires: system.admin permission (admin only)
    """

    try:
        await immutable_audit_trail.start_background_services()

        # Log service start
        await log_system_event(
            event_type="audit_services_started",
            details={
                "started_by": current_user.username,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {"message": "Audit trail background services started successfully"}

    except Exception as e:
        logger.error(f"Error starting audit services: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start audit services",
        )


@router.post("/services/stop")
@require_permission("system.admin")
async def stop_audit_services(current_user: User = Depends(check_admin_access)):
    """
    Stop audit trail background services.

    Requires: system.admin permission (admin only)
    """

    try:
        await immutable_audit_trail.stop_background_services()

        # Log service stop
        await log_system_event(
            event_type="audit_services_stopped",
            details={
                "stopped_by": current_user.username,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {"message": "Audit trail background services stopped successfully"}

    except Exception as e:
        logger.error(f"Error stopping audit services: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop audit services",
        )


@router.get("/categories")
async def get_audit_categories():
    """
    Get available audit event categories.

    Public endpoint - no authentication required.
    """

    categories = [
        {
            "value": category.value,
            "name": category.value.replace("_", " ").title(),
            "description": f"Audit events related to {category.value.replace('_', ' ')}",
        }
        for category in AuditEventCategory
    ]

    integrity_levels = [
        {
            "value": level.value,
            "name": level.value.title(),
            "description": f"Integrity level: {level.value}",
        }
        for level in IntegrityLevel
    ]

    return {"categories": categories, "integrity_levels": integrity_levels}


@router.post("/export")
@require_permission("system.admin")
async def export_audit_records(
    start_date: datetime = Query(..., description="Export start date"),
    end_date: datetime = Query(..., description="Export end date"),
    category: Optional[str] = Query(None, description="Filter by category"),
    format: str = Query("json", description="Export format (json, csv)"),
    current_user: User = Depends(check_admin_access),
):
    """
    Export audit records for compliance reporting.

    Requires: system.admin permission (admin only)
    """

    try:
        # Validate date range
        if end_date <= start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be after start date",
            )

        # Validate date range is not too large (prevent abuse)
        max_days = 90
        if (end_date - start_date).days > max_days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Date range cannot exceed {max_days} days",
            )

        # Convert category if provided
        category_enum = None
        if category:
            try:
                category_enum = AuditEventCategory(category)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid category: {category}",
                )

        # Search records for export
        records = await immutable_audit_trail.search_audit_records(
            category=category_enum,
            start_date=start_date,
            end_date=end_date,
            limit=10000,  # Large limit for export
        )

        # Log export event
        await log_system_event(
            event_type="audit_export",
            details={
                "exported_by": current_user.username,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "category": category,
                "format": format,
                "record_count": len(records),
            },
        )

        if format.lower() == "csv":
            # Return CSV data (in practice, would generate a file download)
            return {
                "format": "csv",
                "record_count": len(records),
                "message": "CSV export prepared (implementation would return file)",
                "records": records[:10],  # Sample records
            }
        else:
            # Return JSON data
            return {
                "format": "json",
                "record_count": len(records),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "category": category,
                "records": records,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting audit records: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export audit records",
        )


@router.get("/health")
async def audit_trail_health():
    """
    Health check endpoint for the audit trail system.

    Public endpoint - no authentication required.
    """

    try:
        stats = await immutable_audit_trail.get_audit_statistics()

        if "error" in stats:
            return {"status": "unhealthy", "error": stats["error"]}

        # Simple health indicators
        is_healthy = (
            stats["is_running"]
            and stats["integrity_violations"] == 0
            and stats["pending_records"] < 1000  # Arbitrary threshold
        )

        return {
            "status": "healthy" if is_healthy else "degraded",
            "is_running": stats["is_running"],
            "total_records": stats["total_records"],
            "integrity_violations": stats["integrity_violations"],
            "pending_records": stats["pending_records"],
            "blocks_created": stats["blocks_created"],
            "integrity_level": stats["integrity_level"],
        }

    except Exception as e:
        logger.error(f"Error checking audit trail health: {e}")
        return {"status": "unhealthy", "error": str(e)}
