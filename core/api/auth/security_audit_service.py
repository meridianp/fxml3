"""
Security audit logging and monitoring service.

Provides comprehensive security event logging, threat detection, and monitoring
capabilities that integrate with the existing immutable audit trail system.
"""

import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import Request
from pydantic import BaseModel, Field

# from fxml4.compliance.audit.immutable_trail import ImmutableAuditTrail, AuditEntry
# Using simplified audit integration to avoid SQLAlchemy conflicts

logger = logging.getLogger(__name__)


class SimpleAuditEntry:
    """Simplified audit entry for security events."""

    def __init__(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        action: str,
        timestamp: datetime,
        user_id: str,
        details: Dict[str, Any],
        correlation_id: Optional[str] = None,
        compliance_tags: Optional[List[str]] = None,
        retention_years: int = 7,
    ):
        self.event_type = event_type
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.action = action
        self.timestamp = timestamp
        self.user_id = user_id
        self.details = details
        self.correlation_id = correlation_id
        self.compliance_tags = compliance_tags or []
        self.retention_years = retention_years


class SimpleAuditTrail:
    """Simplified audit trail for security events."""

    def __init__(self):
        self.entries: List[SimpleAuditEntry] = []

    async def add_entry(self, entry: SimpleAuditEntry):
        """Add an entry to the audit trail."""
        self.entries.append(entry)
        logger.info(f"Audit entry added: {entry.action} for {entry.entity_id}")

    async def get_entries(
        self, correlation_id: Optional[str] = None
    ) -> List[SimpleAuditEntry]:
        """Get audit entries, optionally filtered by correlation ID."""
        if correlation_id:
            return [e for e in self.entries if e.correlation_id == correlation_id]
        return self.entries.copy()


class SecurityEventType(str, Enum):
    """Types of security events that can be logged."""

    # Authentication Events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_TIMEOUT = "session_timeout"
    ACCOUNT_LOCKOUT = "account_lockout"
    PASSWORD_CHANGE = "password_change"  # pragma: allowlist secret
    PASSWORD_RESET_REQUEST = "password_reset_request"  # pragma: allowlist secret
    PASSWORD_RESET_COMPLETE = "password_reset_complete"  # pragma: allowlist secret
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    MFA_SUCCESS = "mfa_success"
    MFA_FAILURE = "mfa_failure"

    # JWT Events (with backwards compatibility)
    JWT_TOKEN_ISSUED = "jwt_token_issued"
    TOKEN_CREATED = "jwt_token_issued"  # Alias for tests
    JWT_TOKEN_REFRESHED = "jwt_token_refreshed"
    TOKEN_REFRESHED = "jwt_token_refreshed"  # Alias for tests
    JWT_TOKEN_REVOKED = "jwt_token_revoked"
    TOKEN_REVOKED = "jwt_token_revoked"  # Alias for tests
    JWT_TOKEN_EXPIRED = "jwt_token_expired"
    JWT_TOKEN_INVALID = "jwt_token_invalid"
    JWT_KEY_ROTATION = "jwt_key_rotation"

    # Authorization Events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    UNAUTHORIZED_ACCESS_ATTEMPT = "unauthorized_access_attempt"

    # Security Violations
    BRUTE_FORCE_ATTACK = "brute_force_attack"
    SUSPICIOUS_LOGIN_PATTERN = "suspicious_login_pattern"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    SECURITY_POLICY_VIOLATION = "security_policy_violation"
    DATA_BREACH_ATTEMPT = "data_breach_attempt"


class ThreatLevel(str, Enum):
    """Threat severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEvent(BaseModel):
    """Security event data model."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: SecurityEventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    username: Optional[str] = None
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    threat_level: Optional[ThreatLevel] = None
    resolved: bool = False
    resolution_notes: Optional[str] = None


class SecurityViolation(BaseModel):
    """Security violation data model."""

    violation_id: str = Field(default_factory=lambda: str(uuid4()))
    violation_type: str
    description: str
    severity: ThreatLevel
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    username: Optional[str] = None
    ip_address: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    correlation_id: Optional[str] = None


class SecurityMetrics(BaseModel):
    """Security metrics data model."""

    total_events: int = 0
    failed_logins: int = 0
    successful_logins: int = 0
    blocked_attempts: int = 0
    security_violations: int = 0
    active_sessions: int = 0
    threat_level_counts: Dict[str, int] = Field(default_factory=dict)
    event_type_counts: Dict[str, int] = Field(default_factory=dict)
    top_source_ips: List[Tuple[str, int]] = Field(default_factory=list)
    collection_period: timedelta = Field(default_factory=lambda: timedelta(hours=24))
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class AnomalyDetectionResult(BaseModel):
    """Result of anomaly detection analysis."""

    is_anomaly: bool = False
    anomaly_score: float = 0.0
    details: Dict[str, Any] = Field(default_factory=dict)
    threat_level: Optional[ThreatLevel] = None
    recommended_action: Optional[str] = None


class ThreatDetectionResult(BaseModel):
    """Result of threat detection analysis."""

    is_threat: bool = False
    threat_level: ThreatLevel = ThreatLevel.LOW
    threat_type: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    recommended_actions: List[str] = Field(default_factory=list)


class SecurityAuditService:
    """
    Security audit logging and monitoring service.

    Provides comprehensive security event logging, threat detection, and monitoring
    capabilities that integrate with the existing immutable audit trail system.
    """

    def __init__(
        self,
        audit_trail: Optional[SimpleAuditTrail] = None,
        threat_detection_enabled: bool = True,
        brute_force_threshold: int = 5,
        brute_force_window_minutes: int = 15,
        anomaly_threshold: float = 0.8,
        max_login_attempts: int = 5,
        lockout_duration_minutes: int = 15,
    ):
        """Initialize the security audit service."""
        self.audit_trail = audit_trail or SimpleAuditTrail()
        self.security_events: List[SecurityEvent] = []
        self.security_violations: List[SecurityViolation] = []

        # Configuration
        self.threat_detection_enabled = threat_detection_enabled
        self.brute_force_threshold = brute_force_threshold
        self.brute_force_window_minutes = brute_force_window_minutes
        self.suspicious_pattern_threshold = 10
        self.anomaly_threshold = anomaly_threshold
        self.max_login_attempts = max_login_attempts
        self.lockout_duration_minutes = lockout_duration_minutes

        # In-memory caches for performance
        self._failed_login_attempts = defaultdict(deque)  # ip -> deque of timestamps
        self._user_sessions = defaultdict(set)  # user -> set of session_ids
        self._ip_event_history = defaultdict(deque)  # ip -> deque of events
        self._user_behavior_patterns = defaultdict(list)  # user -> list of behaviors

        logger.info("SecurityAuditService initialized")

    async def log_authentication_event(
        self,
        event_type: SecurityEventType,
        username: Optional[str] = None,
        user_id: Optional[str] = None,
        user: Optional[Any] = None,  # Support User object from tests
        request: Optional[Request] = None,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        threat_level: Optional[ThreatLevel] = None,
    ) -> str:
        """Log an authentication-related security event."""

        # Handle user object if provided
        if user:
            username = username or getattr(user, "username", None)
            user_id = (
                user_id
                or getattr(user, "user_id", None)
                or str(getattr(user, "id", None))
            )

        # Extract request information
        ip_address = None
        user_agent = None
        if request:
            ip_address = self._extract_ip_address(request)
            user_agent = request.headers.get("User-Agent")

        # Create security event
        # Set default threat level if not provided
        if threat_level is None:
            threat_level = (
                ThreatLevel.LOW
                if event_type == SecurityEventType.LOGIN_SUCCESS
                else None
            )

        event = SecurityEvent(
            event_type=event_type,
            username=username,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            details=details or {},
            correlation_id=correlation_id or str(uuid4()),
            threat_level=threat_level,
        )

        # Store event
        self.security_events.append(event)

        # Update tracking caches
        await self._update_tracking_caches(event)

        # Log to immutable audit trail
        await self._log_to_audit_trail(event)

        # Check for threats
        await self._check_for_threats(event)

        logger.info(f"Logged authentication event: {event_type} for user {username}")
        return event.event_id

    async def log_jwt_event(
        self,
        event_type: SecurityEventType,
        username: Optional[str] = None,
        user: Optional[Any] = None,
        token_id: Optional[str] = None,
        token_type: Optional[str] = None,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Log a JWT-related security event."""

        # Handle user object if provided
        if user:
            username = username or getattr(user, "username", None)

        # Extract request information
        ip_address = None
        user_agent = None
        if request:
            ip_address = self._extract_ip_address(request)
            user_agent = request.headers.get("User-Agent")

        # Create security event
        event_details = {**(details or {})}
        if token_id:
            event_details["token_id"] = token_id
        if token_type:
            event_details["token_type"] = token_type

        event = SecurityEvent(
            event_type=event_type,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details=event_details,
            correlation_id=correlation_id or str(uuid4()),
        )

        # Store event
        self.security_events.append(event)

        # Update tracking caches
        await self._update_tracking_caches(event)

        # Log to immutable audit trail
        await self._log_to_audit_trail(event)

        # Check for threats
        await self._check_for_threats(event)

        logger.info(f"Logged JWT event: {event_type} for user {username}")
        return event.event_id

    async def log_password_event(
        self,
        event_type: SecurityEventType,
        username: Optional[str] = None,
        user: Optional[Any] = None,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Log a password-related security event."""

        # Handle user object if provided
        if user:
            username = username or getattr(user, "username", None)

        # Extract request information
        ip_address = None
        user_agent = None
        if request:
            ip_address = self._extract_ip_address(request)
            user_agent = request.headers.get("User-Agent")

        # Create security event
        event = SecurityEvent(
            event_type=event_type,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            correlation_id=correlation_id or str(uuid4()),
        )

        # Store event
        self.security_events.append(event)

        # Update tracking caches
        await self._update_tracking_caches(event)

        # Log to immutable audit trail
        await self._log_to_audit_trail(event)

        logger.info(f"Logged password event: {event_type} for user {username}")
        return event.event_id

    async def detect_brute_force_attack(
        self, username: str, ip_address: str, time_window_minutes: int = 15
    ) -> ThreatDetectionResult:
        """Detect brute force login attempts."""

        # Check failed login attempts from this IP
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        failed_attempts = [
            timestamp
            for timestamp in self._failed_login_attempts[ip_address]
            if timestamp > cutoff_time
        ]

        is_threat = len(failed_attempts) >= self.brute_force_threshold
        threat_level = ThreatLevel.HIGH if is_threat else ThreatLevel.LOW

        result = ThreatDetectionResult(
            is_threat=is_threat,
            threat_level=threat_level,
            threat_type="brute_force_attack",
            details={
                "failed_attempts": len(failed_attempts),
                "threshold": self.brute_force_threshold,
                "time_window_minutes": time_window_minutes,
                "username": username,
                "ip_address": ip_address,
            },
            recommended_actions=(
                [
                    "Block IP address temporarily",
                    "Require additional authentication",
                    "Notify security team",
                ]
                if is_threat
                else []
            ),
        )

        # Log security violation if threat detected
        if is_threat:
            await self._create_security_violation(
                violation_type="brute_force_attack",
                description=(
                    f"Brute force attack detected from {ip_address} "
                    f"targeting {username}"
                ),
                severity=ThreatLevel.HIGH,
                username=username,
                ip_address=ip_address,
                details=result.details,
            )

        return result

    async def detect_suspicious_login_pattern(
        self, username: str, current_ip: str, time_window_hours: int = 24
    ) -> ThreatDetectionResult:
        """Detect suspicious login patterns for a user."""

        # Get recent login events for the user
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        recent_logins = [
            event
            for event in self.security_events
            if (
                event.username == username
                and event.event_type == SecurityEventType.LOGIN_SUCCESS
                and event.timestamp > cutoff_time
            )
        ]

        # Analyze patterns
        unique_ips = set(
            event.ip_address for event in recent_logins if event.ip_address
        )
        login_times = [event.timestamp for event in recent_logins]

        # Calculate suspicious indicators
        multiple_ips = len(unique_ips) > 3
        rapid_succession = False
        if len(login_times) > 1:
            time_diffs = [
                (login_times[i] - login_times[i - 1]).total_seconds()
                for i in range(1, len(login_times))
            ]
            rapid_succession = any(diff < 300 for diff in time_diffs)  # 5 minutes

        is_threat = multiple_ips or rapid_succession
        threat_level = ThreatLevel.MEDIUM if is_threat else ThreatLevel.LOW

        result = ThreatDetectionResult(
            is_threat=is_threat,
            threat_level=threat_level,
            threat_type="suspicious_login_pattern",
            details={
                "unique_ips": len(unique_ips),
                "total_logins": len(recent_logins),
                "multiple_ips": multiple_ips,
                "rapid_succession": rapid_succession,
                "time_window_hours": time_window_hours,
            },
            recommended_actions=(
                [
                    "Require additional verification",
                    "Monitor user activity closely",
                    "Consider temporary restrictions",
                ]
                if is_threat
                else []
            ),
        )

        return result

    async def detect_anomalous_behavior(
        self, username: str, current_behavior: Dict[str, Any]
    ) -> AnomalyDetectionResult:
        """Detect anomalous user behavior patterns."""

        # Get historical behavior patterns for the user
        historical_patterns = self._user_behavior_patterns.get(username, [])

        if not historical_patterns:
            # No historical data - not an anomaly yet
            return AnomalyDetectionResult(
                is_anomaly=False,
                anomaly_score=0.0,
                details={"reason": "No historical data available"},
            )

        # Simple anomaly detection based on behavioral deviations
        anomaly_score = self._calculate_behavior_anomaly_score(
            current_behavior, historical_patterns
        )

        is_anomaly = anomaly_score > self.anomaly_threshold
        threat_level = None
        if is_anomaly:
            if anomaly_score > 0.9:
                threat_level = ThreatLevel.HIGH
            elif anomaly_score > 0.8:
                threat_level = ThreatLevel.MEDIUM
            else:
                threat_level = ThreatLevel.LOW

        return AnomalyDetectionResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            details={
                "current_behavior": current_behavior,
                "anomaly_score": anomaly_score,
                "threshold": self.anomaly_threshold,
            },
            threat_level=threat_level,
            recommended_action="Monitor closely" if is_anomaly else None,
        )

    async def detect_token_abuse(
        self, token_id: str, usage_patterns: Dict[str, Any]
    ) -> ThreatDetectionResult:
        """Detect JWT token abuse patterns."""

        # Analyze token usage patterns
        rapid_requests = usage_patterns.get("requests_per_minute", 0) > 100
        multiple_ips = len(usage_patterns.get("source_ips", [])) > 5
        unusual_endpoints = len(usage_patterns.get("accessed_endpoints", [])) > 20

        is_threat = rapid_requests or multiple_ips or unusual_endpoints

        if is_threat:
            threat_level = ThreatLevel.HIGH if rapid_requests else ThreatLevel.MEDIUM
        else:
            threat_level = ThreatLevel.LOW

        return ThreatDetectionResult(
            is_threat=is_threat,
            threat_level=threat_level,
            threat_type="token_abuse",
            details={
                "token_id": token_id,
                "rapid_requests": rapid_requests,
                "multiple_ips": multiple_ips,
                "unusual_endpoints": unusual_endpoints,
                **usage_patterns,
            },
            recommended_actions=(
                [
                    "Revoke token immediately",
                    "Investigate user account",
                    "Review access logs",
                ]
                if is_threat
                else []
            ),
        )

    async def detect_privilege_escalation(
        self, username: str, old_role: str, new_role: str, context: Dict[str, Any]
    ) -> ThreatDetectionResult:
        """Detect potential privilege escalation attempts."""

        # Define role hierarchy (higher number = more privileges)
        role_levels = {
            "user": 1,
            "trader": 2,
            "analyst": 3,
            "manager": 4,
            "admin": 5,
            "superadmin": 6,
        }

        old_level = role_levels.get(old_role.lower(), 0)
        new_level = role_levels.get(new_role.lower(), 0)

        # Check for suspicious escalation
        level_jump = new_level - old_level
        is_threat = level_jump > 2  # Jumping more than 2 levels is suspicious

        threat_level = ThreatLevel.HIGH if is_threat else ThreatLevel.LOW

        result = ThreatDetectionResult(
            is_threat=is_threat,
            threat_level=threat_level,
            threat_type="privilege_escalation",
            details={
                "username": username,
                "old_role": old_role,
                "new_role": new_role,
                "level_jump": level_jump,
                **context,
            },
            recommended_actions=(
                [
                    "Verify authorization for role change",
                    "Audit recent administrative actions",
                    "Temporarily restrict elevated privileges",
                ]
                if is_threat
                else []
            ),
        )

        return result

    async def get_security_metrics(
        self, time_window_hours: int = 24
    ) -> SecurityMetrics:
        """Get comprehensive security metrics for the specified time window."""

        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        recent_events = [
            event for event in self.security_events if event.timestamp > cutoff_time
        ]

        # Count events by type
        event_type_counts = defaultdict(int)
        threat_level_counts = defaultdict(int)
        ip_counts = defaultdict(int)

        failed_logins = 0
        successful_logins = 0
        active_sessions = set()

        for event in recent_events:
            event_type_counts[event.event_type] += 1

            if event.threat_level:
                threat_level_counts[event.threat_level] += 1

            if event.ip_address:
                ip_counts[event.ip_address] += 1

            if event.event_type == SecurityEventType.LOGIN_FAILURE:
                failed_logins += 1
            elif event.event_type == SecurityEventType.LOGIN_SUCCESS:
                successful_logins += 1
                if event.session_id:
                    active_sessions.add(event.session_id)

        # Count security violations
        recent_violations = [
            violation
            for violation in self.security_violations
            if violation.detected_at > cutoff_time
        ]

        # Top source IPs
        top_source_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[
            :10
        ]

        return SecurityMetrics(
            total_events=len(recent_events),
            failed_logins=failed_logins,
            successful_logins=successful_logins,
            blocked_attempts=event_type_counts.get(SecurityEventType.ACCESS_DENIED, 0),
            security_violations=len(recent_violations),
            active_sessions=len(active_sessions),
            threat_level_counts=dict(threat_level_counts),
            event_type_counts={k: v for k, v in event_type_counts.items()},
            top_source_ips=top_source_ips,
            collection_period=timedelta(hours=time_window_hours),
        )

    async def get_security_violations(
        self,
        resolved: Optional[bool] = None,
        severity: Optional[ThreatLevel] = None,
        time_window_hours: Optional[int] = None,
    ) -> List[SecurityViolation]:
        """Get security violations based on filters."""

        violations = self.security_violations.copy()

        # Apply filters
        if resolved is not None:
            violations = [v for v in violations if v.resolved == resolved]

        if severity:
            violations = [v for v in violations if v.severity == severity]

        if time_window_hours:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
            violations = [v for v in violations if v.detected_at > cutoff_time]

        return violations

    async def resolve_security_violation(
        self, violation_id: str, resolution_notes: str
    ) -> bool:
        """Mark a security violation as resolved."""

        for violation in self.security_violations:
            if violation.violation_id == violation_id:
                violation.resolved = True
                violation.resolved_at = datetime.utcnow()
                violation.resolution_notes = resolution_notes

                # Log to audit trail
                await self._log_to_audit_trail(
                    SecurityEvent(
                        event_type=SecurityEventType.SECURITY_POLICY_VIOLATION,
                        details={
                            "action": "violation_resolved",
                            "violation_id": violation_id,
                            "resolution_notes": resolution_notes,
                        },
                    )
                )

                logger.info(f"Security violation {violation_id} resolved")
                return True

        return False

    async def get_events_by_correlation_id(
        self, correlation_id: str
    ) -> List[SecurityEvent]:
        """Get all security events with the specified correlation ID."""

        return [
            event
            for event in self.security_events
            if event.correlation_id == correlation_id
        ]

    async def get_security_events(
        self,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        event_type: Optional[SecurityEventType] = None,
        limit: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[SecurityEvent]:
        """Get security events based on filters."""

        events = self.security_events.copy()

        # Apply filters
        if user_id:
            events = [e for e in events if e.user_id == user_id]

        if username:
            events = [e for e in events if e.username == username]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        # Sort by timestamp (most recent first)
        events.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply limit
        if limit:
            events = events[:limit]

        return events

    def _extract_ip_address(self, request: Request) -> Optional[str]:
        """Extract the real IP address from the request."""

        # Check for forwarded headers first (case insensitive)
        forwarded_for = request.headers.get("x-forwarded-for") or request.headers.get(
            "X-Forwarded-For"
        )
        if forwarded_for:
            # Take the first IP in case of multiple proxies
            return forwarded_for.split(",")[0].strip()

        # Check other common headers (case insensitive)
        real_ip = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to client host
        if hasattr(request, "client") and request.client:
            return request.client.host

        return None

    async def _update_tracking_caches(self, event: SecurityEvent):
        """Update in-memory tracking caches for performance."""

        # Track failed login attempts by IP
        if event.event_type == SecurityEventType.LOGIN_FAILURE and event.ip_address:
            self._failed_login_attempts[event.ip_address].append(event.timestamp)

            # Keep only recent attempts (sliding window)
            cutoff_time = datetime.utcnow() - timedelta(
                minutes=self.brute_force_window_minutes
            )
            while (
                self._failed_login_attempts[event.ip_address]
                and self._failed_login_attempts[event.ip_address][0] < cutoff_time
            ):
                self._failed_login_attempts[event.ip_address].popleft()

        # Track user sessions
        if event.session_id and event.username:
            if event.event_type == SecurityEventType.LOGIN_SUCCESS:
                self._user_sessions[event.username].add(event.session_id)
            elif event.event_type in [
                SecurityEventType.LOGOUT,
                SecurityEventType.SESSION_TIMEOUT,
            ]:
                self._user_sessions[event.username].discard(event.session_id)

        # Track IP event history
        if event.ip_address:
            self._ip_event_history[event.ip_address].append(event)
            # Keep only recent events (last 1000)
            if len(self._ip_event_history[event.ip_address]) > 1000:
                self._ip_event_history[event.ip_address].popleft()

        # Track user behavior patterns
        if event.username:
            behavior = {
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
            }
            self._user_behavior_patterns[event.username].append(behavior)
            # Keep only recent patterns (last 100)
            if len(self._user_behavior_patterns[event.username]) > 100:
                self._user_behavior_patterns[event.username].pop(0)

    async def _log_to_audit_trail(self, event: SecurityEvent):
        """Log security event to the audit trail."""

        try:
            audit_entry = SimpleAuditEntry(
                event_type="security_event",
                entity_type="authentication",
                entity_id=event.username or "unknown",
                action=event.event_type,
                timestamp=event.timestamp,
                user_id=event.username or "system",
                details={
                    "event_id": event.event_id,
                    "ip_address": event.ip_address,
                    "user_agent": event.user_agent,
                    "session_id": event.session_id,
                    "correlation_id": event.correlation_id,
                    **event.details,
                },
                correlation_id=event.correlation_id,
                compliance_tags=["security", "authentication"],
                retention_years=7,
            )

            await self.audit_trail.add_entry(audit_entry)

        except Exception as e:
            logger.error(f"Failed to log security event to audit trail: {e}")
            # Don't raise - audit trail failure shouldn't break security logging

    async def _check_for_threats(self, event: SecurityEvent):
        """Check for threats based on the security event."""

        # Check for brute force attacks on failed logins
        if (
            event.event_type == SecurityEventType.LOGIN_FAILURE
            and event.username
            and event.ip_address
        ):

            threat_result = await self.detect_brute_force_attack(
                username=event.username, ip_address=event.ip_address
            )

            if threat_result.is_threat:
                logger.warning(f"Brute force attack detected: {threat_result.details}")

    async def _create_security_violation(
        self,
        violation_type: str,
        description: str,
        severity: ThreatLevel,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> SecurityViolation:
        """Create and store a security violation."""

        violation = SecurityViolation(
            violation_type=violation_type,
            description=description,
            severity=severity,
            username=username,
            ip_address=ip_address,
            details=details or {},
            correlation_id=correlation_id or str(uuid4()),
        )

        self.security_violations.append(violation)

        # Log violation as security event
        await self.log_authentication_event(
            event_type=SecurityEventType.SECURITY_POLICY_VIOLATION,
            username=username,
            details={
                "violation_id": violation.violation_id,
                "violation_type": violation_type,
                "severity": severity,
                **violation.details,
            },
            correlation_id=violation.correlation_id,
        )

        logger.warning(f"Security violation created: {violation_type} - {description}")
        return violation

    def _calculate_behavior_anomaly_score(
        self,
        current_behavior: Dict[str, Any],
        historical_patterns: List[Dict[str, Any]],
    ) -> float:
        """Calculate anomaly score for user behavior (simplified implementation)."""

        if not historical_patterns:
            return 0.0

        # Simple scoring based on behavioral deviations
        score = 0.0
        total_checks = 0

        # Check IP address patterns
        current_ip = current_behavior.get("ip_address")
        if current_ip:
            historical_ips = set(
                p.get("ip_address") for p in historical_patterns if p.get("ip_address")
            )
            if historical_ips and current_ip not in historical_ips:
                score += 0.3
            total_checks += 1

        # Check time patterns
        current_hour = current_behavior.get("timestamp", datetime.utcnow()).hour
        historical_hours = [
            p.get("timestamp", datetime.utcnow()).hour for p in historical_patterns
        ]
        if historical_hours:
            avg_hour = sum(historical_hours) / len(historical_hours)
            hour_deviation = abs(current_hour - avg_hour)
            if hour_deviation > 6:  # More than 6 hours difference
                score += 0.2
        total_checks += 1

        # Check user agent patterns
        current_ua = current_behavior.get("user_agent")
        if current_ua:
            historical_uas = set(
                p.get("user_agent") for p in historical_patterns if p.get("user_agent")
            )
            if historical_uas and current_ua not in historical_uas:
                score += 0.2
            total_checks += 1

        return min(score, 1.0) if total_checks > 0 else 0.0
