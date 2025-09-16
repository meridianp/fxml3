"""
Regulatory Reporting API Router for FXML4.

This module provides REST API endpoints for managing regulatory reporting,
including report generation, status monitoring, and compliance management.
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
from fxml4.compliance.reporting.regulatory_engine import (
    RegulatoryJurisdiction,
    ReportFormat,
    ReportPriority,
    ReportStatus,
    ReportType,
    regulatory_reporting_engine,
)
from fxml4.core.logging import get_logger

router = APIRouter(prefix="/regulatory-reporting", tags=["regulatory-reporting"])
logger = get_logger(__name__)


# Pydantic models for API
class ReportGenerationRequest(BaseModel):
    """Request model for generating a regulatory report."""

    report_type: str = Field(..., description="Type of report to generate")
    start_time: datetime = Field(..., description="Report period start time")
    end_time: datetime = Field(..., description="Report period end time")
    priority: Optional[str] = Field("normal", description="Report generation priority")
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional parameters"
    )

    @validator("end_time")
    def end_time_must_be_after_start_time(cls, v, values):
        if "start_time" in values and v <= values["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v

    @validator("priority")
    def validate_priority(cls, v):
        valid_priorities = [p.value for p in ReportPriority]
        if v not in valid_priorities:
            raise ValueError(f"priority must be one of: {valid_priorities}")
        return v


class ReportGenerationResponse(BaseModel):
    """Response model for report generation request."""

    task_id: str = Field(..., description="Unique task identifier")
    message: str = Field(..., description="Status message")
    estimated_completion_time: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )


class ReportStatusResponse(BaseModel):
    """Response model for report status."""

    task_id: str
    report_type: str
    jurisdiction: str
    status: str
    created_at: datetime
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class ReportListResponse(BaseModel):
    """Response model for report listing."""

    reports: List[ReportStatusResponse]
    total_count: int
    page: int
    page_size: int


class ReportingStatisticsResponse(BaseModel):
    """Response model for reporting statistics."""

    total_reports_generated: int
    total_reports_failed: int
    total_reports_submitted: int
    active_tasks: int
    background_tasks_running: int
    last_report_generation: Optional[datetime] = None
    reports_by_status: Dict[str, int]
    reports_by_type: Dict[str, int]
    report_specifications: int
    submission_queue_size: int


@router.post("/generate", response_model=ReportGenerationResponse)
@require_permission("reports.create")
async def generate_regulatory_report(
    request: ReportGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a regulatory report.

    Requires: reports.create permission
    """

    try:
        # Convert string priority to enum
        priority = ReportPriority(request.priority)

        # Generate report
        task_id = await regulatory_reporting_engine.generate_report(
            report_type=request.report_type,
            start_time=request.start_time,
            end_time=request.end_time,
            parameters=request.parameters,
            priority=priority,
        )

        # Log report generation request
        auth_audit_logger.log_event(
            event_type=AuditEventType.REGULATORY_REPORT_REQUESTED,
            username=current_user.username,
            details={
                "task_id": task_id,
                "report_type": request.report_type,
                "start_time": request.start_time.isoformat(),
                "end_time": request.end_time.isoformat(),
                "priority": request.priority,
            },
        )

        # Estimate completion time based on priority
        completion_estimate = datetime.now(timezone.utc)
        if priority == ReportPriority.CRITICAL:
            completion_estimate += timedelta(minutes=5)
        elif priority == ReportPriority.HIGH:
            completion_estimate += timedelta(minutes=15)
        elif priority == ReportPriority.NORMAL:
            completion_estimate += timedelta(hours=1)
        else:
            completion_estimate += timedelta(hours=4)

        return ReportGenerationResponse(
            task_id=task_id,
            message="Report generation scheduled successfully",
            estimated_completion_time=completion_estimate,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request parameters: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error generating regulatory report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule report generation",
        )


@router.get("/status/{task_id}", response_model=ReportStatusResponse)
@require_permission("reports.read")
async def get_report_status(
    task_id: str, current_user: User = Depends(get_current_user)
):
    """
    Get the status of a specific report generation task.

    Requires: reports.read permission
    """

    try:
        status_info = await regulatory_reporting_engine.get_report_status(task_id)

        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report task not found: {task_id}",
            )

        return ReportStatusResponse(**status_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting report status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve report status",
        )


@router.get("/list", response_model=ReportListResponse)
@require_permission("reports.read")
async def list_regulatory_reports(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_user),
):
    """
    List regulatory reports with optional filters.

    Requires: reports.read permission
    """

    try:
        # Validate status filter
        if status_filter:
            try:
                ReportStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter: {status_filter}",
                )

        # Get reports with filters
        reports = await regulatory_reporting_engine.list_reports(
            start_date=start_date,
            end_date=end_date,
            status=ReportStatus(status_filter) if status_filter else None,
        )

        # Apply pagination
        total_count = len(reports)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_reports = reports[start_idx:end_idx]

        # Convert to response models
        report_responses = []
        for report_info in paginated_reports:
            report_responses.append(
                ReportStatusResponse(
                    task_id=report_info["task_id"],
                    report_type=report_info["report_type"],
                    jurisdiction=report_info["jurisdiction"],
                    status=report_info["status"],
                    created_at=datetime.fromisoformat(report_info["created_at"]),
                    output_path=report_info.get("output_path"),
                    error_message=report_info.get("error_message"),
                    retry_count=report_info.get("retry_count", 0),
                )
            )

        return ReportListResponse(
            reports=report_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing regulatory reports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list reports",
        )


@router.get("/statistics", response_model=ReportingStatisticsResponse)
@require_permission("system.monitoring")
async def get_reporting_statistics(
    current_user: User = Depends(check_risk_manager_access),
):
    """
    Get comprehensive regulatory reporting statistics.

    Requires: system.monitoring permission (risk manager or admin)
    """

    try:
        stats = await regulatory_reporting_engine.get_reporting_statistics()

        # Convert datetime strings back to datetime objects
        last_report_generation = None
        if stats.get("last_report_generation"):
            last_report_generation = datetime.fromisoformat(
                stats["last_report_generation"]
            )

        return ReportingStatisticsResponse(
            total_reports_generated=stats["total_reports_generated"],
            total_reports_failed=stats["total_reports_failed"],
            total_reports_submitted=stats["total_reports_submitted"],
            active_tasks=stats["active_tasks"],
            background_tasks_running=stats["background_tasks_running"],
            last_report_generation=last_report_generation,
            reports_by_status=stats["reports_by_status"],
            reports_by_type=stats["reports_by_type"],
            report_specifications=stats["report_specifications"],
            submission_queue_size=stats["submission_queue_size"],
        )

    except Exception as e:
        logger.error(f"Error getting reporting statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve reporting statistics",
        )


@router.get("/types")
@require_permission("reports.read")
async def get_available_report_types(current_user: User = Depends(get_current_user)):
    """
    Get list of available regulatory report types and specifications.

    Requires: reports.read permission
    """

    try:
        # Get available report types from the engine
        report_specs = regulatory_reporting_engine.report_specifications

        available_types = []
        for spec_name, spec in report_specs.items():
            available_types.append(
                {
                    "name": spec_name,
                    "type": spec.report_type.value,
                    "jurisdiction": spec.jurisdiction.value,
                    "format": spec.format.value,
                    "frequency": spec.frequency,
                    "is_mandatory": spec.is_mandatory,
                    "deadline_minutes": spec.deadline_minutes,
                    "description": f"{spec.report_type.value.replace('_', ' ').title()} report for {spec.jurisdiction.value.replace('_', ' ').title()}",
                }
            )

        return {"available_types": available_types, "total_count": len(available_types)}

    except Exception as e:
        logger.error(f"Error getting available report types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available report types",
        )


@router.post("/process-event")
@require_permission("system.admin")
async def process_real_time_event(
    event_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(check_admin_access),
):
    """
    Process a real-time trading event for immediate reporting if required.

    Requires: system.admin permission (admin only)
    """

    try:
        # Process the event in the background
        background_tasks.add_task(
            regulatory_reporting_engine.process_real_time_events, event_data
        )

        # Log event processing
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username=current_user.username,
            details={
                "action": "process_real_time_event",
                "event_type": event_data.get("type", "unknown"),
                "event_data": event_data,
            },
        )

        return {
            "message": "Real-time event scheduled for processing",
            "event_type": event_data.get("type", "unknown"),
        }

    except Exception as e:
        logger.error(f"Error processing real-time event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process real-time event",
        )


@router.post("/start-services")
@require_permission("system.admin")
async def start_reporting_services(current_user: User = Depends(check_admin_access)):
    """
    Start background reporting services (periodic reports, cleanup, etc.).

    Requires: system.admin permission (admin only)
    """

    try:
        await regulatory_reporting_engine.start_background_services()

        # Log service start
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username=current_user.username,
            details={"action": "start_reporting_services", "status": "success"},
        )

        return {
            "message": "Regulatory reporting background services started successfully"
        }

    except Exception as e:
        logger.error(f"Error starting reporting services: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start reporting services",
        )


@router.post("/stop-services")
@require_permission("system.admin")
async def stop_reporting_services(current_user: User = Depends(check_admin_access)):
    """
    Stop background reporting services.

    Requires: system.admin permission (admin only)
    """

    try:
        await regulatory_reporting_engine.stop_background_services()

        # Log service stop
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username=current_user.username,
            details={"action": "stop_reporting_services", "status": "success"},
        )

        return {
            "message": "Regulatory reporting background services stopped successfully"
        }

    except Exception as e:
        logger.error(f"Error stopping reporting services: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop reporting services",
        )


@router.post("/cleanup")
@require_permission("system.admin")
async def cleanup_old_reports(current_user: User = Depends(check_admin_access)):
    """
    Manually trigger cleanup of old report files.

    Requires: system.admin permission (admin only)
    """

    try:
        await regulatory_reporting_engine.cleanup_old_reports()

        # Log cleanup execution
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username=current_user.username,
            details={"action": "cleanup_old_reports", "status": "success"},
        )

        return {"message": "Report cleanup completed successfully"}

    except Exception as e:
        logger.error(f"Error during report cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup old reports",
        )


@router.get("/health")
async def reporting_engine_health():
    """
    Health check endpoint for the regulatory reporting engine.

    Public endpoint - no authentication required
    """

    try:
        stats = await regulatory_reporting_engine.get_reporting_statistics()

        # Simple health indicators
        is_healthy = (
            stats["background_tasks_running"] >= 0
            and stats["submission_queue_size"] < 1000  # Arbitrary threshold
        )

        return {
            "status": "healthy" if is_healthy else "degraded",
            "active_tasks": stats["active_tasks"],
            "background_tasks": stats["background_tasks_running"],
            "queue_size": stats["submission_queue_size"],
            "last_report": stats.get("last_report_generation"),
        }

    except Exception as e:
        logger.error(f"Error checking reporting engine health: {e}")
        return {"status": "unhealthy", "error": str(e)}
