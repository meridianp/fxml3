"""Authentication audit logging for FXML4.

This module provides comprehensive audit logging for authentication and authorization events.
"""

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import Request

from fxml4.config import get_config

# Configure audit logger with separate handler
audit_logger = logging.getLogger("fxml4.auth.audit")
audit_logger.setLevel(logging.INFO)

# Prevent propagation to avoid duplicate logs
audit_logger.propagate = False

# Create audit-specific formatter
audit_formatter = logging.Formatter("%(asctime)s - AUDIT - %(levelname)s - %(message)s")

# Create console handler for audit logs
audit_console_handler = logging.StreamHandler()
audit_console_handler.setFormatter(audit_formatter)
audit_logger.addHandler(audit_console_handler)

# Create file handler for audit logs if configured
config = get_config()
audit_log_file = config.get("logging.audit_file", "logs/audit.log")
try:
    import os

    os.makedirs(os.path.dirname(audit_log_file), exist_ok=True)
    audit_file_handler = logging.FileHandler(audit_log_file)
    audit_file_handler.setFormatter(audit_formatter)
    audit_logger.addHandler(audit_file_handler)
except Exception:
    # Fallback to console only if file logging fails
    pass


class AuditEventType(Enum):
    """Audit event types."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGIN_ATTEMPT = "login_attempt"
    LOGOUT = "logout"
    TOKEN_CREATED = "token_created"
    TOKEN_VALIDATED = "token_validated"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    TOKEN_REFRESHED = "token_refreshed"
    TOKEN_REVOKED = "token_revoked"
    ALL_TOKENS_REVOKED = "all_tokens_revoked"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    PASSWORD_CHANGED = "password_changed"
    PRIVILEGE_ESCALATION_ATTEMPT = "privilege_escalation_attempt"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    API_ACCESS = "api_access"
    SECURITY_VIOLATION = "security_violation"


class RiskLevel(Enum):
    """Risk level classifications."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event data structure."""

    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    user_id: Optional[str]
    username: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_id: Optional[str]
    session_id: Optional[str]
    endpoint: Optional[str]
    method: Optional[str]
    success: bool
    risk_level: RiskLevel
    details: Dict[str, Any]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["risk_level"] = self.risk_level.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """Convert audit event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuthAuditLogger:
    """Authentication audit logger."""

    def __init__(self):
        """Initialize audit logger."""
        self.config = get_config()
        self.enable_detailed_logging = self.config.get("api.auth.audit.detailed", True)
        self.log_successful_logins = self.config.get("api.auth.audit.log_success", True)
        self.log_token_validation = self.config.get(
            "api.auth.audit.log_token_validation", False
        )

    def _extract_request_info(
        self, request: Optional[Request] = None
    ) -> Dict[str, Any]:
        """Extract request information for audit logging.

        Args:
            request: FastAPI request object

        Returns:
            Dictionary with request information
        """
        if not request:
            return {
                "ip_address": None,
                "user_agent": None,
                "request_id": None,
                "endpoint": None,
                "method": None,
            }

        # Get client IP (handle proxy headers)
        ip_address = request.client.host if request.client else None
        if "x-forwarded-for" in request.headers:
            ip_address = request.headers["x-forwarded-for"].split(",")[0].strip()
        elif "x-real-ip" in request.headers:
            ip_address = request.headers["x-real-ip"]

        # Generate request ID if not present
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))

        return {
            "ip_address": ip_address,
            "user_agent": request.headers.get("user-agent"),
            "request_id": request_id,
            "endpoint": str(request.url.path),
            "method": request.method,
        }

    def _hash_sensitive_data(self, data: str) -> str:
        """Hash sensitive data for logging.

        Args:
            data: Sensitive data to hash

        Returns:
            SHA256 hash of the data
        """
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _create_session_id(self, username: str, ip_address: str) -> str:
        """Create a session ID for tracking.

        Args:
            username: Username
            ip_address: IP address

        Returns:
            Session ID
        """
        session_data = f"{username}:{ip_address}:{datetime.utcnow().date()}"
        return self._hash_sensitive_data(session_data)

    def log_login_attempt(
        self,
        username: str,
        success: bool,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log login attempt.

        Args:
            username: Username attempting to log in
            success: Whether login was successful
            request: FastAPI request object
            details: Additional details
        """
        request_info = self._extract_request_info(request)

        # Determine event type and risk level
        if success:
            event_type = AuditEventType.LOGIN_SUCCESS
            risk_level = RiskLevel.LOW
        else:
            event_type = AuditEventType.LOGIN_FAILURE
            risk_level = RiskLevel.MEDIUM

        # Skip logging successful logins if disabled
        if success and not self.log_successful_logins:
            return

        session_id = self._create_session_id(
            username, request_info["ip_address"] or "unknown"
        )

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=None,  # Could be enhanced to include user ID
            username=username,
            ip_address=request_info["ip_address"],
            user_agent=request_info["user_agent"],
            request_id=request_info["request_id"],
            session_id=session_id,
            endpoint=request_info["endpoint"],
            method=request_info["method"],
            success=success,
            risk_level=risk_level,
            details=details or {},
            metadata={
                "auth_method": "password",
                "timestamp_utc": datetime.utcnow().isoformat(),
            },
        )

        self._log_event(event)

    def log_token_operation(
        self,
        event_type: AuditEventType,
        username: str,
        success: bool,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log token-related operations.

        Args:
            event_type: Type of token operation
            username: Username associated with token
            success: Whether operation was successful
            request: FastAPI request object
            details: Additional details
        """
        # Skip token validation logging if disabled
        if (
            event_type == AuditEventType.TOKEN_VALIDATED
            and not self.log_token_validation
        ):
            return

        request_info = self._extract_request_info(request)

        # Determine risk level
        if event_type in [AuditEventType.TOKEN_INVALID, AuditEventType.TOKEN_EXPIRED]:
            risk_level = RiskLevel.MEDIUM
        elif not success:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.LOW

        session_id = self._create_session_id(
            username, request_info["ip_address"] or "unknown"
        )

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=None,
            username=username,
            ip_address=request_info["ip_address"],
            user_agent=request_info["user_agent"],
            request_id=request_info["request_id"],
            session_id=session_id,
            endpoint=request_info["endpoint"],
            method=request_info["method"],
            success=success,
            risk_level=risk_level,
            details=details or {},
            metadata={
                "operation": "token_management",
                "timestamp_utc": datetime.utcnow().isoformat(),
            },
        )

        self._log_event(event)

    def log_permission_check(
        self,
        username: str,
        required_scopes: list,
        user_scopes: list,
        success: bool,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log permission/authorization checks.

        Args:
            username: Username
            required_scopes: Required scopes for access
            user_scopes: User's actual scopes
            success: Whether authorization was successful
            request: FastAPI request object
            details: Additional details
        """
        request_info = self._extract_request_info(request)

        event_type = (
            AuditEventType.PERMISSION_GRANTED
            if success
            else AuditEventType.PERMISSION_DENIED
        )
        risk_level = RiskLevel.LOW if success else RiskLevel.HIGH

        # Check for privilege escalation attempts
        if not success and any(
            scope in ["admin", "write"] for scope in required_scopes
        ):
            risk_level = RiskLevel.CRITICAL
            event_type = AuditEventType.PRIVILEGE_ESCALATION_ATTEMPT

        session_id = self._create_session_id(
            username, request_info["ip_address"] or "unknown"
        )

        event_details = {
            "required_scopes": required_scopes,
            "user_scopes": user_scopes,
            "missing_scopes": list(set(required_scopes) - set(user_scopes)),
            **(details or {}),
        }

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=None,
            username=username,
            ip_address=request_info["ip_address"],
            user_agent=request_info["user_agent"],
            request_id=request_info["request_id"],
            session_id=session_id,
            endpoint=request_info["endpoint"],
            method=request_info["method"],
            success=success,
            risk_level=risk_level,
            details=event_details,
            metadata={
                "operation": "authorization_check",
                "timestamp_utc": datetime.utcnow().isoformat(),
            },
        )

        self._log_event(event)

    def log_security_violation(
        self,
        username: Optional[str],
        violation_type: str,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log security violations.

        Args:
            username: Username (if known)
            violation_type: Type of security violation
            request: FastAPI request object
            details: Additional details
        """
        request_info = self._extract_request_info(request)

        session_id = None
        if username:
            session_id = self._create_session_id(
                username, request_info["ip_address"] or "unknown"
            )

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.SECURITY_VIOLATION,
            timestamp=datetime.utcnow(),
            user_id=None,
            username=username,
            ip_address=request_info["ip_address"],
            user_agent=request_info["user_agent"],
            request_id=request_info["request_id"],
            session_id=session_id,
            endpoint=request_info["endpoint"],
            method=request_info["method"],
            success=False,
            risk_level=RiskLevel.CRITICAL,
            details={"violation_type": violation_type, **(details or {})},
            metadata={
                "operation": "security_monitoring",
                "timestamp_utc": datetime.utcnow().isoformat(),
            },
        )

        self._log_event(event)

    def log_api_access(
        self,
        username: str,
        endpoint: str,
        method: str,
        status_code: int,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log API access events.

        Args:
            username: Username accessing the API
            endpoint: API endpoint accessed
            method: HTTP method
            status_code: Response status code
            request: FastAPI request object
            details: Additional details
        """
        request_info = self._extract_request_info(request)

        success = 200 <= status_code < 400

        # Determine risk level based on status code and endpoint
        if status_code >= 500:
            risk_level = RiskLevel.HIGH
        elif status_code >= 400:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        session_id = self._create_session_id(
            username, request_info["ip_address"] or "unknown"
        )

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.API_ACCESS,
            timestamp=datetime.utcnow(),
            user_id=None,
            username=username,
            ip_address=request_info["ip_address"],
            user_agent=request_info["user_agent"],
            request_id=request_info["request_id"],
            session_id=session_id,
            endpoint=endpoint,
            method=method,
            success=success,
            risk_level=risk_level,
            details={"status_code": status_code, **(details or {})},
            metadata={
                "operation": "api_access",
                "timestamp_utc": datetime.utcnow().isoformat(),
            },
        )

        self._log_event(event)

    async def log_event(
        self,
        db=None,  # Database session (not used in current implementation)
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        event_type: AuditEventType = None,
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Async log event method for token manager compatibility.

        Args:
            db: Database session (for future use)
            user_id: User ID
            username: Username
            event_type: Type of audit event
            success: Whether the event was successful
            ip_address: Client IP address
            user_agent: Client user agent
            details: Additional event details
        """
        # Determine risk level based on event type and success
        if not success:
            risk_level = RiskLevel.HIGH
        elif event_type in [AuditEventType.TOKEN_INVALID, AuditEventType.TOKEN_EXPIRED]:
            risk_level = RiskLevel.MEDIUM
        elif event_type == AuditEventType.ALL_TOKENS_REVOKED:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # Create session ID if we have username and IP
        session_id = None
        if username and ip_address:
            session_id = self._create_session_id(username, ip_address)

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=str(uuid.uuid4()),
            session_id=session_id,
            endpoint=None,
            method=None,
            success=success,
            risk_level=risk_level,
            details=details or {},
            metadata={
                "operation": "token_management",
                "timestamp_utc": datetime.utcnow().isoformat(),
            },
        )

        self._log_event(event)

    def _log_event(self, event: AuditEvent):
        """Log audit event.

        Args:
            event: Audit event to log
        """
        if self.enable_detailed_logging:
            audit_logger.info(f"AUDIT_EVENT: {event.to_json()}")
        else:
            # Simplified logging
            audit_logger.info(
                f"EVENT: {event.event_type.value} | "
                f"USER: {event.username or 'unknown'} | "
                f"IP: {event.ip_address or 'unknown'} | "
                f"SUCCESS: {event.success} | "
                f"RISK: {event.risk_level.value}"
            )

        # Log high/critical risk events to security channel
        if event.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            security_logger = logging.getLogger("fxml4.security")
            security_logger.warning(
                f"HIGH_RISK_AUTH_EVENT: {event.event_type.value} | "
                f"USER: {event.username or 'unknown'} | "
                f"IP: {event.ip_address or 'unknown'} | "
                f"DETAILS: {json.dumps(event.details)}"
            )


# Global audit logger instance
auth_audit_logger = AuthAuditLogger()


def log_auth_event(
    event_type: AuditEventType,
    username: str,
    success: bool,
    request: Optional[Request] = None,
    **kwargs,
):
    """Convenience function for logging authentication events.

    Args:
        event_type: Type of authentication event
        username: Username
        success: Whether the event was successful
        request: FastAPI request object
        **kwargs: Additional details
    """
    if event_type in [AuditEventType.LOGIN_SUCCESS, AuditEventType.LOGIN_FAILURE]:
        auth_audit_logger.log_login_attempt(username, success, request, kwargs)
    elif event_type in [
        AuditEventType.TOKEN_CREATED,
        AuditEventType.TOKEN_VALIDATED,
        AuditEventType.TOKEN_EXPIRED,
        AuditEventType.TOKEN_INVALID,
        AuditEventType.TOKEN_REFRESHED,
        AuditEventType.TOKEN_REVOKED,
        AuditEventType.ALL_TOKENS_REVOKED,
    ]:
        auth_audit_logger.log_token_operation(
            event_type, username, success, request, kwargs
        )
    elif event_type in [
        AuditEventType.PERMISSION_GRANTED,
        AuditEventType.PERMISSION_DENIED,
    ]:
        auth_audit_logger.log_permission_check(
            username,
            kwargs.get("required_scopes", []),
            kwargs.get("user_scopes", []),
            success,
            request,
            kwargs,
        )
    else:
        # Generic event logging
        auth_audit_logger._log_event(
            AuditEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                timestamp=datetime.utcnow(),
                user_id=None,
                username=username,
                ip_address=None,
                user_agent=None,
                request_id=None,
                session_id=None,
                endpoint=None,
                method=None,
                success=success,
                risk_level=RiskLevel.MEDIUM,
                details=kwargs,
                metadata={"timestamp_utc": datetime.utcnow().isoformat()},
            )
        )
