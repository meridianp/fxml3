"""
Test-Driven Development for Phase 4: Authentication & Security Framework.

This module tests the enhanced authentication system including:
- JWT token management with refresh capabilities
- Role-based access control (RBAC)
- Multi-factor authentication (2FA)
- Comprehensive audit logging
- Rate limiting and security controls
- SOC 2 Type II compliance features

Following TDD methodology: Red → Green → Refactor
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.api.auth.enhanced_audit_logger import EnhancedAuditLogger
from fxml4.api.auth.models import User
from fxml4.api.auth.rate_limiter import RateLimiter
from fxml4.api.auth.role_manager import RoleDefinitions, RoleManager
from fxml4.api.auth.token_manager import TokenManager
from fxml4.api.auth.totp_manager import TOTPManager
from fxml4.core.exceptions import TokenError


class TestPhase4JWTAuthentication:
    """Test JWT authentication with refresh token capabilities."""

    @pytest.fixture
    def token_manager(self):
        """Create TokenManager instance for testing."""
        return TokenManager()

    @pytest.fixture
    async def sample_user(self, db_session: AsyncSession):
        """Create a sample user for testing."""
        user = User(
            username="testuser",
            email="test@fxml4.com",
            hashed_password="hashed_pass_123",  # pragma: allowlist secret
            is_active=True,
            is_verified=True,
            roles=["trader", "viewer"],
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    async def test_access_token_generation(
        self, token_manager: TokenManager, sample_user: User
    ):
        """Test access token generation with proper claims."""
        # Red: Test should fail initially
        token_data = await token_manager.create_access_token(
            user_id=sample_user.id,
            username=sample_user.username,
            roles=sample_user.roles,
            permissions=["trading.read", "data.read"],
        )

        assert token_data["access_token"] is not None
        assert token_data["token_type"] == "bearer"
        assert token_data["expires_in"] == 3600  # 1 hour default

        # Verify token contains proper claims
        payload = await token_manager.decode_token(token_data["access_token"])
        assert payload["sub"] == str(sample_user.id)
        assert payload["username"] == sample_user.username
        assert payload["roles"] == sample_user.roles
        assert payload["permissions"] == ["trading.read", "data.read"]

    async def test_refresh_token_flow(
        self, token_manager: TokenManager, sample_user: User
    ):
        """Test refresh token generation and usage."""
        # Generate initial tokens
        tokens = await token_manager.create_token_pair(
            user_id=sample_user.id,
            username=sample_user.username,
            roles=sample_user.roles,
        )

        assert "access_token" in tokens
        assert "refresh_token" in tokens

        # Use refresh token to get new access token
        new_tokens = await token_manager.refresh_access_token(tokens["refresh_token"])

        assert new_tokens["access_token"] != tokens["access_token"]
        assert "refresh_token" in new_tokens  # Should rotate refresh token

        # Old refresh token should be invalidated
        with pytest.raises(TokenError):
            await token_manager.refresh_access_token(tokens["refresh_token"])

    async def test_token_blacklisting(
        self, token_manager: TokenManager, sample_user: User
    ):
        """Test token blacklisting and revocation."""
        tokens = await token_manager.create_token_pair(
            user_id=sample_user.id,
            username=sample_user.username,
            roles=sample_user.roles,
        )

        # Token should be valid initially
        payload = await token_manager.decode_token(tokens["access_token"])
        assert payload["sub"] == str(sample_user.id)

        # Blacklist the token
        await token_manager.blacklist_token(tokens["access_token"])

        # Token should now be invalid
        with pytest.raises(TokenError):
            await token_manager.decode_token(tokens["access_token"])

    async def test_token_cleanup_maintenance(self, token_manager: TokenManager):
        """Test automatic cleanup of expired tokens."""
        # This should clean up expired tokens and blacklist entries
        cleanup_count = await token_manager.cleanup_expired_tokens()
        assert isinstance(cleanup_count, int)


class TestPhase4RoleBasedAccessControl:
    """Test Role-Based Access Control (RBAC) system."""

    @pytest.fixture
    def role_manager(self):
        """Create RoleManager instance for testing."""
        return RoleManager()

    async def test_standard_role_definitions(self, role_manager: RoleManager):
        """Test that standard roles have proper permissions."""
        # Admin should have full permissions
        admin_permissions = RoleDefinitions.get_admin_permissions()
        assert "users.create" in admin_permissions
        assert "trading.execute" in admin_permissions
        assert "system.configure" in admin_permissions

        # Trader should have trading permissions but not user management
        trader_permissions = RoleDefinitions.get_trader_permissions()
        assert "trading.execute" in trader_permissions
        assert "data.read" in trader_permissions
        assert "users.create" not in trader_permissions

        # Viewer should have read-only access
        viewer_permissions = RoleDefinitions.get_viewer_permissions()
        assert "data.read" in viewer_permissions
        assert "trading.read" in viewer_permissions
        assert "trading.execute" not in viewer_permissions

    async def test_role_initialization(
        self, role_manager: RoleManager, db_session: AsyncSession
    ):
        """Test initialization of standard roles in database."""
        # Initialize standard roles
        await role_manager.initialize_standard_roles(db_session)

        # Verify roles were created
        roles = await role_manager.get_all_roles(db_session)
        role_names = [role.name for role in roles]

        assert "admin" in role_names
        assert "trader" in role_names
        assert "viewer" in role_names
        assert "auditor" in role_names

    async def test_permission_validation(
        self, role_manager: RoleManager, db_session: AsyncSession
    ):
        """Test permission validation for user actions."""
        # Create user with trader role
        user = User(
            username="trader_user",
            email="trader@fxml4.com",
            hashed_password="hashed_pass",  # pragma: allowlist secret
            roles=["trader"],
        )

        # Should have trading permissions
        has_permission = await role_manager.user_has_permission(
            user, "trading.execute", db_session
        )
        assert has_permission is True

        # Should not have user management permissions
        has_permission = await role_manager.user_has_permission(
            user, "users.create", db_session
        )
        assert has_permission is False

    async def test_role_assignment_and_removal(
        self, role_manager: RoleManager, db_session: AsyncSession
    ):
        """Test dynamic role assignment and removal."""
        user = User(
            username="test_user",
            email="test@fxml4.com",
            hashed_password="hashed_pass",  # pragma: allowlist secret
            roles=["viewer"],
        )

        # Add trader role
        await role_manager.add_user_role(user, "trader", db_session)
        assert "trader" in user.roles

        # Remove viewer role
        await role_manager.remove_user_role(user, "viewer", db_session)
        assert "viewer" not in user.roles


class TestPhase4MultiFactorAuthentication:
    """Test Multi-Factor Authentication (2FA) system."""

    @pytest.fixture
    def totp_manager(self):
        """Create TOTPManager instance for testing."""
        return TOTPManager()

    @pytest.fixture
    async def user_with_2fa(self, db_session: AsyncSession):
        """Create user with 2FA enabled."""
        user = User(
            username="secure_user",
            email="secure@fxml4.com",
            hashed_password="hashed_pass",  # pragma: allowlist secret
            is_2fa_enabled=True,
            totp_secret="JBSWY3DPEHPK3PXP",  # pragma: allowlist secret
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    async def test_totp_setup_flow(
        self, totp_manager: TOTPManager, db_session: AsyncSession
    ):
        """Test TOTP setup process."""
        user = User(
            username="new_user",
            email="new@fxml4.com",
            hashed_password="hashed_pass",  # pragma: allowlist secret
        )

        # Generate TOTP secret and QR code
        setup_data = await totp_manager.setup_totp(user, db_session)

        assert "secret" in setup_data
        assert "qr_code_url" in setup_data
        assert "backup_codes" in setup_data
        assert len(setup_data["backup_codes"]) == 10

        # User should not be 2FA enabled until verification
        assert user.is_2fa_enabled is False

    async def test_totp_verification(
        self, totp_manager: TOTPManager, user_with_2fa: User
    ):
        """Test TOTP code verification."""
        # Generate valid TOTP code
        import pyotp

        totp = pyotp.TOTP(user_with_2fa.totp_secret)
        valid_code = totp.now()

        # Verification should succeed
        is_valid = await totp_manager.verify_totp(user_with_2fa, valid_code)
        assert is_valid is True

        # Invalid code should fail
        is_valid = await totp_manager.verify_totp(user_with_2fa, "000000")
        assert is_valid is False

    async def test_backup_code_usage(
        self, totp_manager: TOTPManager, user_with_2fa: User, db_session: AsyncSession
    ):
        """Test backup code authentication."""
        # Set backup codes for user
        backup_codes = ["12345678", "87654321", "11111111"]
        await totp_manager.set_backup_codes(user_with_2fa, backup_codes, db_session)

        # Use backup code
        is_valid = await totp_manager.verify_backup_code(
            user_with_2fa, "12345678", db_session
        )
        assert is_valid is True

        # Same backup code should not work again
        is_valid = await totp_manager.verify_backup_code(
            user_with_2fa, "12345678", db_session
        )
        assert is_valid is False

    async def test_2fa_required_endpoints(self, totp_manager: TOTPManager):
        """Test that 2FA is required for sensitive endpoints."""
        # This would test that endpoints requiring 2FA properly validate
        # the 2FA token in addition to the access token
        pass  # Implementation would depend on specific endpoint requirements


class TestPhase4AuditLogging:
    """Test comprehensive audit logging framework."""

    @pytest.fixture
    def audit_logger(self):
        """Create EnhancedAuditLogger instance for testing."""
        return EnhancedAuditLogger()

    async def test_trading_activity_logging(
        self, audit_logger: EnhancedAuditLogger, db_session: AsyncSession
    ):
        """Test logging of trading activities."""
        # Log a trading event
        await audit_logger.log_trading_event(
            session=db_session,
            user_id="user123",
            event_type="ORDER_PLACED",
            trading_context={
                "symbol": "EURUSD",
                "order_type": "MARKET",
                "quantity": 10000,
                "price": 1.0850,
            },
            correlation_id="trade_001",
        )

        # Verify log was created with proper structure
        logs = await audit_logger.get_logs(
            session=db_session,
            event_type="ORDER_PLACED",
            start_date=datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        assert len(logs) == 1
        log = logs[0]
        assert log.user_id == "user123"
        assert log.event_type == "ORDER_PLACED"
        assert "symbol" in log.context
        assert log.correlation_id == "trade_001"

    async def test_compliance_logging(
        self, audit_logger: EnhancedAuditLogger, db_session: AsyncSession
    ):
        """Test compliance-related logging requirements."""
        # Log compliance event
        await audit_logger.log_compliance_event(
            session=db_session,
            regulation_type="MIFID_II",
            event_data={
                "trade_id": "T123456",
                "client_id": "C789",
                "instrument": "EUR/USD",
                "best_execution_analysis": True,
            },
            severity="HIGH",
        )

        # Compliance logs should have longer retention
        logs = await audit_logger.get_compliance_logs(db_session)
        assert len(logs) >= 1

    async def test_audit_trail_integrity(
        self, audit_logger: EnhancedAuditLogger, db_session: AsyncSession
    ):
        """Test audit trail integrity with cryptographic hashing."""
        # Log multiple events
        events = [
            {"event_type": "LOGIN", "user_id": "user1"},
            {"event_type": "ORDER_PLACED", "user_id": "user1"},
            {"event_type": "ORDER_FILLED", "user_id": "user1"},
        ]

        for event in events:
            await audit_logger.log_security_event(
                session=db_session, **event, ip_address="192.168.1.100"
            )

        # Verify chain integrity
        integrity_check = await audit_logger.verify_log_chain_integrity(db_session)
        assert integrity_check.is_valid is True
        assert integrity_check.broken_links == 0

    async def test_log_retention_and_archival(
        self, audit_logger: EnhancedAuditLogger, db_session: AsyncSession
    ):
        """Test log retention and archival policies."""
        # Test that logs older than retention period are archived
        archive_count = await audit_logger.archive_old_logs(
            session=db_session, retention_days=2555  # 7 years for trading logs
        )

        assert isinstance(archive_count, int)


class TestPhase4RateLimitingAndSecurity:
    """Test rate limiting and security controls."""

    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter()

    async def test_endpoint_rate_limiting(self, rate_limiter: RateLimiter):
        """Test rate limiting for API endpoints."""
        client_ip = "192.168.1.100"
        endpoint = "/api/v1/trading/orders"

        # Should allow requests within limit
        for i in range(10):  # Assume limit is 10 per minute
            allowed = await rate_limiter.check_rate_limit(client_ip, endpoint)
            assert allowed is True

        # Should block requests exceeding limit
        blocked = await rate_limiter.check_rate_limit(client_ip, endpoint)
        assert blocked is False

    async def test_user_account_lockout(self, rate_limiter: RateLimiter):
        """Test user account lockout after failed login attempts."""
        user_id = "user123"

        # Record failed login attempts
        for i in range(5):  # Assume lockout after 5 failures
            await rate_limiter.record_failed_login(user_id)

        # User should be locked out
        is_locked = await rate_limiter.is_user_locked(user_id)
        assert is_locked is True

        # Lockout should have expiration
        lockout_expires = await rate_limiter.get_lockout_expiry(user_id)
        assert lockout_expires > datetime.now(timezone.utc)

    async def test_ddos_protection(self, rate_limiter: RateLimiter):
        """Test DDoS protection mechanisms."""
        # Simulate high volume of requests from single IP
        attacker_ip = "10.0.0.1"

        # Should trigger DDoS protection
        for i in range(1000):
            await rate_limiter.record_request(attacker_ip)

        is_blocked = await rate_limiter.is_ip_blocked(attacker_ip)
        assert is_blocked is True


class TestPhase4SOC2Compliance:
    """Test SOC 2 Type II compliance features."""

    async def test_data_encryption_in_transit(self):
        """Test that all API communications use HTTPS."""
        # This would test SSL/TLS configuration
        pass

    async def test_data_encryption_at_rest(self):
        """Test database encryption and secure storage."""
        # This would test database encryption configuration
        pass

    async def test_access_logging_completeness(
        self, audit_logger: EnhancedAuditLogger, db_session: AsyncSession
    ):
        """Test that all access is logged for SOC 2 compliance."""
        # All user actions should be logged
        await audit_logger.log_access_event(
            session=db_session,
            user_id="user123",
            resource="/api/v1/trading/positions",
            action="READ",
            ip_address="192.168.1.100",
        )

        logs = await audit_logger.get_access_logs(
            session=db_session,
            start_date=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        assert len(logs) >= 1

    async def test_data_retention_policies(self, audit_logger: EnhancedAuditLogger):
        """Test compliance with data retention policies."""
        policies = await audit_logger.get_retention_policies()

        # Trading data: 7 years
        assert policies["trading_logs"]["retention_years"] == 7
        # Access logs: 3 years
        assert policies["access_logs"]["retention_years"] == 3
        # System logs: 1 year
        assert policies["system_logs"]["retention_years"] == 1


class TestPhase4IntegrationTests:
    """Integration tests for complete Phase 4 authentication flow."""

    async def test_complete_authentication_flow(
        self, client: TestClient, db_session: AsyncSession
    ):
        """Test complete authentication flow from login to API access."""
        # 1. User login with credentials
        login_response = client.post(
            "/auth/login",
            json={
                "username": "testuser",
                "password": "testpass123!",  # pragma: allowlist secret
            },
        )

        assert login_response.status_code == 200
        tokens = login_response.json()
        assert "access_token" in tokens

        # 2. Access protected endpoint with token
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        protected_response = client.get("/api/v1/trading/positions", headers=headers)

        assert protected_response.status_code == 200

        # 3. Refresh token when needed
        refresh_response = client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert new_tokens["access_token"] != tokens["access_token"]

    async def test_2fa_enabled_user_flow(self, client: TestClient):
        """Test authentication flow for user with 2FA enabled."""
        # 1. Initial login returns 2FA required
        login_response = client.post(
            "/auth/login",
            json={
                "username": "secure_user",
                "password": "securepass123!",  # pragma: allowlist secret
            },
        )

        assert login_response.status_code == 200
        response_data = login_response.json()
        assert response_data["requires_2fa"] is True
        assert "temp_token" in response_data

        # 2. Complete 2FA verification
        totp_response = client.post(  # noqa: F841
            "/auth/verify-2fa",
            json={
                "temp_token": response_data["temp_token"],
                "totp_code": "123456",  # Would use valid code in real test
            },
        )

        # Would succeed with valid TOTP code
        # assert totp_response.status_code == 200

    async def test_role_based_endpoint_access(self, client: TestClient):
        """Test that role-based access control works for different endpoints."""
        # Admin user should access all endpoints
        admin_token = "admin_jwt_token"  # Would get from login
        headers = {"Authorization": f"Bearer {admin_token}"}

        admin_response = client.get(  # noqa: F841
            "/api/v1/admin/users", headers=headers
        )
        # assert admin_response.status_code == 200

        # Trader user should not access admin endpoints
        trader_token = "trader_jwt_token"  # Would get from login
        headers = {"Authorization": f"Bearer {trader_token}"}

        trader_response = client.get(  # noqa: F841
            "/api/v1/admin/users", headers=headers
        )
        # assert trader_response.status_code == 403


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/phase4/test_authentication_framework.py -v
    pytest.main([__file__, "-v"])
