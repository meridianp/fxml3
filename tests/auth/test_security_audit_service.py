"""
Test-Driven Development for Security Audit Service
=================================================

RED → GREEN → REFACTOR cycle for implementing comprehensive security
audit logging and monitoring with real-time threat detection.

Phase 4B: Security Audit Logging & Monitoring
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.api.auth.models import User, UserRole

# Test-driven imports - these will guide implementation
from fxml4.api.auth.security_audit_service import (
    AnomalyDetectionResult,
    SecurityAuditService,
    SecurityEvent,
    SecurityEventType,
    SecurityMetrics,
    SecurityViolation,
    ThreatLevel,
)

# from fxml4.compliance.audit.immutable_trail import AuditEventCategory
# Using local enum to avoid SQLAlchemy conflicts


# Simple test enum to replace AuditEventCategory
class TestAuditEventCategory:
    AUTHENTICATION = "authentication"


@pytest.fixture
def security_audit_service():
    """Create security audit service instance for testing."""
    return SecurityAuditService()


@pytest.fixture
def sample_user():
    """Create sample user for testing."""
    return User(
        user_id="test-user-123",
        username="test_trader",
        email="trader@test.com",
        role=UserRole.TRADER,
        is_active=True,
        is_verified=True,
    )


@pytest.fixture
def mock_request():
    """Create mock FastAPI request."""
    request = Mock()
    request.client.host = "192.168.1.100"
    request.headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-forwarded-for": "203.0.113.195",
        "x-real-ip": "203.0.113.195",
    }
    request.url.path = "/api/auth/login"
    request.method = "POST"
    request.session = {"session_id": "session-123"}
    return request


class TestSecurityAuditServiceInitialization:
    """Test security audit service initialization and configuration."""

    def test_security_audit_service_creation(self):
        """Test security audit service can be created with valid configuration."""
        service = SecurityAuditService(
            threat_detection_enabled=True,
            anomaly_threshold=0.7,
            max_login_attempts=5,
            lockout_duration_minutes=15,
        )

        assert service.threat_detection_enabled is True
        assert service.anomaly_threshold == 0.7
        assert service.max_login_attempts == 5
        assert service.lockout_duration_minutes == 15

    def test_security_audit_service_with_defaults(self):
        """Test security audit service uses sensible defaults."""
        service = SecurityAuditService()

        assert service.threat_detection_enabled is True
        assert service.anomaly_threshold == 0.8
        assert service.max_login_attempts == 3
        assert service.lockout_duration_minutes == 30
        assert service.session_timeout_minutes == 480  # 8 hours


class TestSecurityEventLogging:
    """Test security event logging functionality."""

    @pytest.mark.asyncio
    async def test_log_authentication_success(
        self, security_audit_service, sample_user, mock_request
    ):
        """Test logging successful authentication events."""
        event_id = await security_audit_service.log_authentication_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user=sample_user,
            request=mock_request,
            details={"login_method": "username_password", "session_duration": "8h"},
        )

        assert isinstance(event_id, str)
        assert len(event_id) > 0

        # Verify event was logged
        events = await security_audit_service.get_security_events(
            user_id=sample_user.user_id, limit=1
        )

        assert len(events) == 1
        event = events[0]
        assert event.event_type == SecurityEventType.LOGIN_SUCCESS
        assert event.user_id == sample_user.user_id
        assert event.ip_address == "203.0.113.195"  # X-Real-IP header
        assert event.threat_level == ThreatLevel.LOW

    @pytest.mark.asyncio
    async def test_log_authentication_failure(
        self, security_audit_service, mock_request
    ):
        """Test logging failed authentication attempts."""
        event_id = await security_audit_service.log_authentication_event(
            event_type=SecurityEventType.LOGIN_FAILURE,
            username="invalid_user",
            request=mock_request,
            threat_level=ThreatLevel.MEDIUM,
            details={"failure_reason": "invalid_credentials", "attempt_number": 2},
        )

        assert isinstance(event_id, str)

        # Verify event was logged with correct threat level
        events = await security_audit_service.get_security_events(
            event_type=SecurityEventType.LOGIN_FAILURE, limit=1
        )

        assert len(events) == 1
        event = events[0]
        assert event.event_type == SecurityEventType.LOGIN_FAILURE
        assert event.threat_level == ThreatLevel.MEDIUM
        assert event.username == "invalid_user"

    @pytest.mark.asyncio
    async def test_log_jwt_token_events(self, security_audit_service, sample_user):
        """Test logging JWT token-related events."""
        # Test token creation
        create_event_id = await security_audit_service.log_jwt_event(
            event_type=SecurityEventType.TOKEN_CREATED,
            user=sample_user,
            token_type="access",
            details={"expires_in": 900, "algorithm": "HS256"},
        )

        assert isinstance(create_event_id, str)

        # Test token validation
        validate_event_id = await security_audit_service.log_jwt_event(
            event_type=SecurityEventType.TOKEN_VALIDATED,
            user=sample_user,
            token_type="access",
            details={"validation_result": "success", "remaining_ttl": 450},
        )

        assert isinstance(validate_event_id, str)

        # Verify both events were logged
        events = await security_audit_service.get_security_events(
            user_id=sample_user.user_id, limit=2
        )

        assert len(events) == 2
        event_types = {event.event_type for event in events}
        assert SecurityEventType.TOKEN_CREATED in event_types
        assert SecurityEventType.TOKEN_VALIDATED in event_types

    @pytest.mark.asyncio
    async def test_log_password_events(self, security_audit_service, sample_user):
        """Test logging password-related security events."""
        # Test password change
        change_event_id = await security_audit_service.log_password_event(
            event_type=SecurityEventType.PASSWORD_CHANGED,
            user=sample_user,
            details={"password_strength": 4, "change_reason": "voluntary"},
        )

        assert isinstance(change_event_id, str)

        # Test password validation failure
        failure_event_id = await security_audit_service.log_password_event(
            event_type=SecurityEventType.PASSWORD_VALIDATION_FAILED,
            user=sample_user,
            threat_level=ThreatLevel.MEDIUM,
            details={
                "validation_errors": ["too_common", "found_in_breach"],
                "attempt_count": 3,
            },
        )

        assert isinstance(failure_event_id, str)

        # Verify events were logged
        events = await security_audit_service.get_security_events(
            user_id=sample_user.user_id, limit=2
        )

        assert len(events) == 2


class TestThreatDetection:
    """Test threat detection and anomaly detection functionality."""

    @pytest.mark.asyncio
    async def test_detect_brute_force_attack(
        self, security_audit_service, mock_request
    ):
        """Test detection of brute force login attempts."""
        username = "target_user"

        # Simulate multiple failed login attempts
        for i in range(5):
            await security_audit_service.log_authentication_event(
                event_type=SecurityEventType.LOGIN_FAILURE,
                username=username,
                request=mock_request,
                details={"attempt_number": i + 1},
            )

        # Check for brute force detection
        threat_result = await security_audit_service.detect_brute_force_attack(
            username=username, ip_address="203.0.113.195", time_window_minutes=15
        )

        assert threat_result.is_threat is True
        assert threat_result.threat_level == ThreatLevel.HIGH
        assert threat_result.details["failed_attempts"] >= 5
        assert "brute_force" in threat_result.details["threat_type"]

    @pytest.mark.asyncio
    async def test_detect_suspicious_login_patterns(
        self, security_audit_service, sample_user
    ):
        """Test detection of suspicious login patterns."""
        # Simulate logins from different geographic locations within short time
        locations = [
            {"ip": "1.2.3.4", "country": "US", "city": "New York"},
            {"ip": "5.6.7.8", "country": "RU", "city": "Moscow"},  # Different country
            {"ip": "9.10.11.12", "country": "CN", "city": "Beijing"},  # Another country
        ]

        for i, location in enumerate(locations):
            mock_req = Mock()
            mock_req.client.host = location["ip"]
            mock_req.headers = {"x-real-ip": location["ip"]}

            await security_audit_service.log_authentication_event(
                event_type=SecurityEventType.LOGIN_SUCCESS,
                user=sample_user,
                request=mock_req,
                details={
                    "location": location,
                    "time_offset": f"{i * 5}min",  # 5 minutes apart
                },
            )

        # Detect suspicious pattern
        anomaly_result = await security_audit_service.detect_anomalous_behavior(
            user_id=sample_user.user_id, analysis_window_hours=1
        )

        assert anomaly_result.is_anomalous is True
        assert anomaly_result.anomaly_score >= 0.8
        assert "geographic_impossibility" in anomaly_result.anomaly_types

    @pytest.mark.asyncio
    async def test_detect_token_abuse(self, security_audit_service, sample_user):
        """Test detection of JWT token abuse patterns."""
        # Simulate excessive token refresh attempts
        for i in range(20):
            await security_audit_service.log_jwt_event(
                event_type=SecurityEventType.TOKEN_REFRESH_ATTEMPT,
                user=sample_user,
                token_type="refresh",
                details={
                    "attempt_number": i + 1,
                    "interval_seconds": 30,  # Very frequent refreshes
                },
            )

        # Detect token abuse
        abuse_result = await security_audit_service.detect_token_abuse(
            user_id=sample_user.user_id, time_window_minutes=10
        )

        assert abuse_result.is_abuse is True
        assert abuse_result.abuse_type == "excessive_refresh"
        assert abuse_result.threat_level == ThreatLevel.MEDIUM
        assert abuse_result.details["refresh_count"] >= 20

    @pytest.mark.asyncio
    async def test_detect_privilege_escalation(
        self, security_audit_service, sample_user
    ):
        """Test detection of privilege escalation attempts."""
        # Simulate failed permission checks for elevated actions
        restricted_actions = [
            "user:delete",
            "system:config",
            "audit:view",
            "compliance:report",
        ]

        for action in restricted_actions:
            await security_audit_service.log_security_event(
                event_type=SecurityEventType.PERMISSION_DENIED,
                user=sample_user,
                details={
                    "attempted_permission": action,
                    "user_role": sample_user.role.value,
                    "required_role": "admin",
                },
            )

        # Detect privilege escalation attempts
        escalation_result = await security_audit_service.detect_privilege_escalation(
            user_id=sample_user.user_id, time_window_minutes=5
        )

        assert escalation_result.is_escalation_attempt is True
        assert escalation_result.threat_level == ThreatLevel.HIGH
        assert escalation_result.details["denied_permissions"] == restricted_actions


class TestSecurityMetrics:
    """Test security metrics collection and analysis."""

    @pytest.mark.asyncio
    async def test_get_authentication_metrics(
        self, security_audit_service, sample_user
    ):
        """Test collection of authentication metrics."""
        # Generate test data
        success_count = 10
        failure_count = 3

        for i in range(success_count):
            await security_audit_service.log_authentication_event(
                event_type=SecurityEventType.LOGIN_SUCCESS,
                user=sample_user,
                request=Mock(),
                details={"session_id": f"session-{i}"},
            )

        for i in range(failure_count):
            await security_audit_service.log_authentication_event(
                event_type=SecurityEventType.LOGIN_FAILURE,
                username="failed_user",
                request=Mock(),
                details={"attempt": i + 1},
            )

        # Get metrics
        metrics = await security_audit_service.get_authentication_metrics(
            time_period_hours=1
        )

        assert isinstance(metrics, SecurityMetrics)
        assert metrics.total_login_attempts >= success_count + failure_count
        assert metrics.successful_logins >= success_count
        assert metrics.failed_logins >= failure_count
        assert 0 <= metrics.success_rate <= 1.0

    @pytest.mark.asyncio
    async def test_get_threat_level_distribution(self, security_audit_service):
        """Test threat level distribution metrics."""
        # Generate events with different threat levels
        threat_events = [
            (SecurityEventType.LOGIN_SUCCESS, ThreatLevel.LOW, 15),
            (SecurityEventType.LOGIN_FAILURE, ThreatLevel.MEDIUM, 5),
            (SecurityEventType.SUSPICIOUS_ACTIVITY, ThreatLevel.HIGH, 2),
            (SecurityEventType.SECURITY_VIOLATION, ThreatLevel.CRITICAL, 1),
        ]

        for event_type, threat_level, count in threat_events:
            for _ in range(count):
                await security_audit_service.log_security_event(
                    event_type=event_type,
                    threat_level=threat_level,
                    details={"test": True},
                )

        # Get threat distribution
        distribution = await security_audit_service.get_threat_level_distribution(
            time_period_hours=1
        )

        assert isinstance(distribution, dict)
        assert ThreatLevel.LOW in distribution
        assert ThreatLevel.MEDIUM in distribution
        assert ThreatLevel.HIGH in distribution
        assert ThreatLevel.CRITICAL in distribution
        assert distribution[ThreatLevel.LOW] >= 15
        assert distribution[ThreatLevel.CRITICAL] >= 1

    @pytest.mark.asyncio
    async def test_get_active_sessions_count(self, security_audit_service, sample_user):
        """Test active sessions counting."""
        # Create multiple login events
        session_ids = [f"session-{i}" for i in range(5)]

        for session_id in session_ids:
            await security_audit_service.log_authentication_event(
                event_type=SecurityEventType.LOGIN_SUCCESS,
                user=sample_user,
                request=Mock(),
                details={"session_id": session_id},
            )

        # Get active sessions count
        active_count = await security_audit_service.get_active_sessions_count()

        assert isinstance(active_count, int)
        assert active_count >= len(session_ids)

    @pytest.mark.asyncio
    async def test_get_geographic_login_distribution(self, security_audit_service):
        """Test geographic distribution of logins."""
        # Simulate logins from different countries
        countries = ["US", "UK", "DE", "JP", "AU"]

        for country in countries:
            mock_req = Mock()
            mock_req.headers = {"cf-ipcountry": country}

            for _ in range(2):  # 2 logins per country
                await security_audit_service.log_authentication_event(
                    event_type=SecurityEventType.LOGIN_SUCCESS,
                    user=Mock(user_id=f"user-{country}"),
                    request=mock_req,
                    details={"country": country},
                )

        # Get geographic distribution
        geo_distribution = (
            await security_audit_service.get_geographic_login_distribution(
                time_period_hours=1
            )
        )

        assert isinstance(geo_distribution, dict)
        assert len(geo_distribution) >= len(countries)
        for country in countries:
            assert country in geo_distribution
            assert geo_distribution[country] >= 2


class TestSecurityViolations:
    """Test security violation detection and handling."""

    @pytest.mark.asyncio
    async def test_create_security_violation(self, security_audit_service, sample_user):
        """Test creation of security violations."""
        violation = await security_audit_service.create_security_violation(
            violation_type="brute_force_attack",
            user_id=sample_user.user_id,
            ip_address="192.168.1.100",
            description="Multiple failed login attempts detected",
            severity=ThreatLevel.HIGH,
            evidence={
                "failed_attempts": 10,
                "time_window": "5 minutes",
                "source_ips": ["192.168.1.100", "192.168.1.101"],
            },
        )

        assert isinstance(violation, SecurityViolation)
        assert violation.violation_type == "brute_force_attack"
        assert violation.user_id == sample_user.user_id
        assert violation.severity == ThreatLevel.HIGH
        assert violation.status == "open"
        assert violation.evidence["failed_attempts"] == 10

    @pytest.mark.asyncio
    async def test_get_security_violations(self, security_audit_service):
        """Test retrieval of security violations."""
        # Create test violations
        violation_types = ["brute_force", "token_abuse", "privilege_escalation"]

        for violation_type in violation_types:
            await security_audit_service.create_security_violation(
                violation_type=violation_type,
                user_id="test-user",
                description=f"Test {violation_type} violation",
                severity=ThreatLevel.MEDIUM,
            )

        # Retrieve violations
        violations = await security_audit_service.get_security_violations(
            status="open", limit=10
        )

        assert isinstance(violations, list)
        assert len(violations) >= len(violation_types)

        violation_types_found = {v.violation_type for v in violations}
        assert "brute_force" in violation_types_found

    @pytest.mark.asyncio
    async def test_resolve_security_violation(self, security_audit_service):
        """Test resolution of security violations."""
        # Create violation
        violation = await security_audit_service.create_security_violation(
            violation_type="test_violation",
            user_id="test-user",
            description="Test violation for resolution",
            severity=ThreatLevel.LOW,
        )

        assert violation.status == "open"

        # Resolve violation
        resolved_violation = await security_audit_service.resolve_security_violation(
            violation_id=violation.violation_id,
            resolution="False positive - legitimate user behavior",
            resolved_by="admin-user",
        )

        assert resolved_violation.status == "resolved"
        assert (
            resolved_violation.resolution == "False positive - legitimate user behavior"
        )
        assert resolved_violation.resolved_by == "admin-user"
        assert resolved_violation.resolved_at is not None


class TestSecurityAuditIntegration:
    """Test integration with immutable audit trail and other services."""

    @pytest.mark.asyncio
    @patch(
        "fxml4.compliance.audit.immutable_trail.immutable_audit_trail.log_audit_event"
    )
    async def test_integration_with_immutable_audit_trail(
        self, mock_log_audit, security_audit_service, sample_user
    ):
        """Test integration with immutable audit trail."""
        mock_log_audit.return_value = "audit-record-123"

        # Log security event
        event_id = await security_audit_service.log_authentication_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user=sample_user,
            request=Mock(),
            details={"test": True},
        )

        # Verify immutable audit trail was called
        mock_log_audit.assert_called_once()
        call_args = mock_log_audit.call_args

        # Check the SimpleAuditEntry structure
        audit_entry = call_args[0][0]  # First positional argument
        assert audit_entry.entity_type == "authentication"
        assert audit_entry.action == SecurityEventType.LOGIN_SUCCESS
        assert audit_entry.user_id == sample_user.user_id

    @pytest.mark.asyncio
    async def test_correlation_id_tracking(self, security_audit_service, sample_user):
        """Test correlation ID tracking across related events."""
        correlation_id = str(uuid.uuid4())

        # Log related events with same correlation ID
        events = [
            SecurityEventType.LOGIN_ATTEMPT,
            SecurityEventType.PASSWORD_VALIDATED,
            SecurityEventType.LOGIN_SUCCESS,
            SecurityEventType.TOKEN_CREATED,
        ]

        event_ids = []
        for event_type in events:
            event_id = await security_audit_service.log_authentication_event(
                event_type=event_type,
                user=sample_user,
                request=Mock(),
                correlation_id=correlation_id,
                details={"step": event_type.value},
            )
            event_ids.append(event_id)

        # Retrieve events by correlation ID
        correlated_events = await security_audit_service.get_correlated_events(
            correlation_id=correlation_id
        )

        assert len(correlated_events) == len(events)
        correlated_event_types = {event.event_type for event in correlated_events}

        for expected_type in events:
            assert expected_type in correlated_event_types


if __name__ == "__main__":
    """
    Run security audit service tests with pytest.

    Usage:
        python -m pytest tests/auth/test_security_audit_service.py -v
    """
    pytest.main([__file__, "-v", "--tb=short"])
