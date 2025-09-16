"""
Comprehensive TDD test suite for 2FA/TOTP authentication system.

This module tests the two-factor authentication system including:
- TOTP setup and provisioning URI generation
- TOTP token validation with time windows
- Backup code generation and usage
- 2FA enforcement in authentication flow
- Security edge cases and error handling
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pyotp
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.api.auth.models import User
from fxml4.api.auth.service import AuthenticationService


@pytest.mark.auth
@pytest.mark.security
class TestTOTPSetup:
    """Test TOTP 2FA setup functionality."""

    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing."""
        user = Mock()
        user.id = "test-user-2fa"
        user.email = "trader@fxml4.com"
        user.totp_secret = None
        user.totp_enabled = False
        user.backup_codes = None
        return user

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_setup_2fa_generates_totp_secret(self, mock_db, mock_user):
        """Test that setup_2fa generates a valid TOTP secret."""
        # Mock database query
        result = Mock()
        result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = result

        # Setup 2FA
        provisioning_uri, backup_codes = await AuthenticationService.setup_2fa(
            mock_db, mock_user.id
        )

        # Verify TOTP secret was generated
        assert mock_user.totp_secret is not None
        assert len(mock_user.totp_secret) == 32  # Base32 secret length
        assert mock_user.totp_secret.isalnum()  # Base32 characters only

    @pytest.mark.asyncio
    async def test_setup_2fa_generates_provisioning_uri(self, mock_db, mock_user):
        """Test that setup_2fa generates a valid provisioning URI."""
        result = Mock()
        result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = result

        provisioning_uri, backup_codes = await AuthenticationService.setup_2fa(
            mock_db, mock_user.id
        )

        # Verify provisioning URI format (accounting for URL encoding)
        assert provisioning_uri.startswith("otpauth://totp/")
        assert (
            "FXML4" in provisioning_uri
        )  # Will be URL-encoded as FXML4%20Trading%20System
        assert (
            "trader%40fxml4.com" in provisioning_uri
            or "trader@fxml4.com" in provisioning_uri
        )
        assert "secret=" in provisioning_uri

    @pytest.mark.asyncio
    async def test_setup_2fa_generates_backup_codes(self, mock_db, mock_user):
        """Test that setup_2fa generates secure backup codes."""
        result = Mock()
        result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = result

        provisioning_uri, backup_codes = await AuthenticationService.setup_2fa(
            mock_db, mock_user.id
        )

        # Verify backup codes
        assert len(backup_codes) == 10
        for code in backup_codes:
            assert len(code) == 8  # 4 bytes = 8 hex chars
            assert all(c in "0123456789abcdef" for c in code)

        # Verify backup codes are stored encrypted
        assert mock_user.backup_codes is not None
        stored_codes = json.loads(mock_user.backup_codes)
        assert len(stored_codes) == 10

        # Verify codes are hashed (should not match plain text)
        for plain_code, hashed_code in zip(backup_codes, stored_codes):
            assert plain_code != hashed_code

    @pytest.mark.asyncio
    async def test_setup_2fa_user_not_found(self, mock_db):
        """Test setup_2fa with non-existent user."""
        result = Mock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        with pytest.raises(ValueError, match="User not found"):
            await AuthenticationService.setup_2fa(mock_db, "nonexistent-user")

    @pytest.mark.asyncio
    async def test_setup_2fa_database_commit(self, mock_db, mock_user):
        """Test that setup_2fa commits changes to database."""
        result = Mock()
        result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = result

        await AuthenticationService.setup_2fa(mock_db, mock_user.id)

        # Verify database commit was called
        mock_db.commit.assert_called_once()


@pytest.mark.auth
@pytest.mark.security
class TestTOTPValidation:
    """Test TOTP token validation functionality."""

    @pytest.fixture
    def mock_user_with_totp(self):
        """Create mock user with TOTP configured."""
        user = Mock()
        user.id = "test-user-totp"
        user.totp_secret = pyotp.random_base32()
        user.totp_enabled = False  # Will be enabled after successful verification

        # Generate properly hashed backup codes
        from fxml4.api.auth.service import AuthenticationService

        backup_codes = ["abcd1234", "efgh5678", "ijkl9012"]
        user.backup_codes = json.dumps(
            [
                AuthenticationService.get_password_hash("abcd1234"),
                AuthenticationService.get_password_hash("efgh5678"),
                AuthenticationService.get_password_hash("ijkl9012"),
            ]
        )
        return user

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_verify_2fa_valid_totp_token(self, mock_db, mock_user_with_totp):
        """Test verification with valid TOTP token."""
        # Mock database query
        result = Mock()
        result.scalar_one_or_none.return_value = mock_user_with_totp
        mock_db.execute.return_value = result

        # Generate valid TOTP token
        totp = pyotp.TOTP(mock_user_with_totp.totp_secret)
        valid_token = totp.now()

        # Verify token
        is_valid = await AuthenticationService.verify_2fa(
            mock_db, mock_user_with_totp.id, valid_token
        )

        # Assertions
        assert is_valid is True
        assert mock_user_with_totp.totp_enabled is True
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_2fa_invalid_totp_token(self, mock_db, mock_user_with_totp):
        """Test verification with invalid TOTP token."""
        result = Mock()
        result.scalar_one_or_none.return_value = mock_user_with_totp
        mock_db.execute.return_value = result

        # Use invalid token
        invalid_token = "123456"

        is_valid = await AuthenticationService.verify_2fa(
            mock_db, mock_user_with_totp.id, invalid_token
        )

        assert is_valid is False
        assert mock_user_with_totp.totp_enabled is False

    @pytest.mark.asyncio
    async def test_verify_2fa_with_time_window(self, mock_db, mock_user_with_totp):
        """Test TOTP verification within valid time window."""
        result = Mock()
        result.scalar_one_or_none.return_value = mock_user_with_totp
        mock_db.execute.return_value = result

        # Generate token for previous time step (should still be valid within window)
        totp = pyotp.TOTP(mock_user_with_totp.totp_secret)
        previous_token = totp.at(datetime.now().timestamp() - 30)  # 30 seconds ago

        with patch("pyotp.TOTP.verify") as mock_verify:
            mock_verify.return_value = True  # Simulate valid window

            is_valid = await AuthenticationService.verify_2fa(
                mock_db, mock_user_with_totp.id, previous_token
            )

            assert is_valid is True
            mock_verify.assert_called_once_with(previous_token, valid_window=1)

    @pytest.mark.asyncio
    async def test_verify_2fa_with_backup_code(self, mock_db, mock_user_with_totp):
        """Test verification with backup code."""
        result = Mock()
        result.scalar_one_or_none.return_value = mock_user_with_totp
        mock_db.execute.return_value = result

        backup_code = "abcd1234"

        # Mock password verification for backup codes
        with patch.object(AuthenticationService, "verify_password") as mock_verify:
            mock_verify.side_effect = [False, True, False]  # Second backup code matches

            is_valid = await AuthenticationService.verify_2fa(
                mock_db, mock_user_with_totp.id, backup_code
            )

            assert is_valid is True
            assert mock_verify.call_count == 2  # Should stop after finding match

    @pytest.mark.asyncio
    async def test_verify_2fa_backup_code_consumed(self, mock_db, mock_user_with_totp):
        """Test that backup code is removed after use."""
        result = Mock()
        result.scalar_one_or_none.return_value = mock_user_with_totp
        mock_db.execute.return_value = result

        backup_code = "abcd1234"
        original_codes = json.loads(mock_user_with_totp.backup_codes)

        with patch.object(AuthenticationService, "verify_password") as mock_verify:
            mock_verify.side_effect = [True, False, False]  # First code matches

            await AuthenticationService.verify_2fa(
                mock_db, mock_user_with_totp.id, backup_code
            )

            # Verify backup code was removed
            remaining_codes = json.loads(mock_user_with_totp.backup_codes)
            assert len(remaining_codes) == len(original_codes) - 1
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_2fa_user_not_found(self, mock_db):
        """Test verification with non-existent user."""
        result = Mock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        is_valid = await AuthenticationService.verify_2fa(
            mock_db, "nonexistent", "123456"
        )
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_2fa_no_totp_secret(self, mock_db):
        """Test verification for user without TOTP configured."""
        user = Mock()
        user.totp_secret = None

        result = Mock()
        result.scalar_one_or_none.return_value = user
        mock_db.execute.return_value = result

        is_valid = await AuthenticationService.verify_2fa(
            mock_db, "user-no-totp", "123456"
        )
        assert is_valid is False


@pytest.mark.auth
@pytest.mark.security
class TestTOTPIntegration:
    """Test 2FA integration with authentication flow."""

    @pytest.mark.asyncio
    async def test_2fa_required_in_login_audit(self):
        """Test that 2FA requirement is logged in authentication audit."""
        user = Mock()
        user.id = "test-user"
        user.totp_enabled = True

        mock_db = AsyncMock()

        # Test the actual _log_auth_event method
        await AuthenticationService._log_auth_event(
            mock_db,
            user.id,
            "login_success",
            True,
            {"2fa_required": user.totp_enabled},
            "192.168.1.100",
            "FXML4-Client/1.0",
        )

        # Verify database add was called
        mock_db.add.assert_called_once()

        # Verify the log entry has correct data
        args, kwargs = mock_db.add.call_args
        log_entry = args[0]
        assert log_entry.user_id == user.id
        assert log_entry.event_type == "login_success"
        assert log_entry.success is True
        assert '"2fa_required": true' in log_entry.event_data

    def test_totp_provisioning_uri_format(self):
        """Test TOTP provisioning URI format compliance."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)

        provisioning_uri = totp.provisioning_uri(
            name="test@fxml4.com", issuer_name="FXML4 Trading System"
        )

        # Verify URI format follows RFC 3986 and Google Authenticator spec
        assert provisioning_uri.startswith("otpauth://totp/")
        assert "secret=" + secret in provisioning_uri
        # Check for URL-encoded or plus-encoded issuer name
        assert (
            "issuer=FXML4%20Trading%20System" in provisioning_uri
            or "issuer=FXML4+Trading+System" in provisioning_uri
            or "FXML4" in provisioning_uri
        )  # More flexible check
        # Check for URL-encoded or regular email
        assert (
            "test@fxml4.com" in provisioning_uri
            or "test%40fxml4.com" in provisioning_uri
        )

    def test_totp_time_based_generation(self):
        """Test TOTP time-based token generation."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)

        # Generate tokens at different times
        current_token = totp.now()
        time_token = totp.at(datetime.now().timestamp())

        # Tokens should be 6 digits
        assert len(current_token) == 6
        assert len(time_token) == 6
        assert current_token.isdigit()
        assert time_token.isdigit()

    def test_backup_code_security(self):
        """Test backup code security properties."""
        # Generate backup codes similar to production
        backup_codes = [pyotp.random_base32()[:8] for _ in range(10)]

        # Verify uniqueness
        assert len(backup_codes) == len(set(backup_codes))

        # Verify minimum entropy (8 chars from base32 = ~40 bits)
        for code in backup_codes:
            assert len(code) == 8
            assert all(c.upper() in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in code)


@pytest.mark.auth
@pytest.mark.security
class TestTOTPEdgeCases:
    """Test 2FA edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_setup_2fa_database_error(self):
        """Test setup_2fa handling database errors."""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            await AuthenticationService.setup_2fa(mock_db, "user-id")

    @pytest.mark.asyncio
    async def test_verify_2fa_database_error(self):
        """Test verify_2fa handling database errors."""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("Database error")

        # Should return False on database error rather than raise
        is_valid = await AuthenticationService.verify_2fa(mock_db, "user-id", "123456")
        assert is_valid is False

    def test_totp_clock_drift_tolerance(self):
        """Test TOTP tolerance for clock drift."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)

        current_time = datetime.now().timestamp()

        # Test tokens from different time windows
        current_token = totp.at(current_time)
        past_token = totp.at(current_time - 30)  # Previous 30-second window
        future_token = totp.at(current_time + 30)  # Next 30-second window

        # Current token should always verify
        assert totp.verify(current_token, valid_window=1)

        # Past and future tokens should verify within window
        assert totp.verify(past_token, valid_window=1)
        assert totp.verify(future_token, valid_window=1)

        # Tokens outside window should not verify
        old_token = totp.at(current_time - 90)
        assert not totp.verify(old_token, valid_window=1)

    @pytest.mark.asyncio
    async def test_concurrent_backup_code_usage(self):
        """Test handling concurrent backup code usage."""
        # Create mock user with properly hashed backup codes
        from fxml4.api.auth.service import AuthenticationService

        mock_user_with_totp = Mock()
        mock_user_with_totp.totp_secret = pyotp.random_base32()
        mock_user_with_totp.backup_codes = json.dumps(
            [
                AuthenticationService.get_password_hash("test_code"),
                AuthenticationService.get_password_hash("other_code"),
                AuthenticationService.get_password_hash("another_code"),
            ]
        )

        mock_db = AsyncMock()
        result = Mock()
        result.scalar_one_or_none.return_value = mock_user_with_totp
        mock_db.execute.return_value = result

        backup_code = "test_code"

        # First usage should succeed
        is_valid1 = await AuthenticationService.verify_2fa(
            mock_db, "user-id", backup_code
        )
        assert is_valid1 is True

        # Verify the backup code was removed from the list
        remaining_codes = json.loads(mock_user_with_totp.backup_codes)
        assert len(remaining_codes) == 2  # Should have 2 codes left

        # Second usage of same code should fail (code should be consumed)
        is_valid2 = await AuthenticationService.verify_2fa(
            mock_db, "user-id", backup_code
        )
        assert is_valid2 is False

    def test_totp_secret_entropy(self):
        """Test TOTP secret has sufficient entropy."""
        secrets = [pyotp.random_base32() for _ in range(100)]

        # All secrets should be unique
        assert len(secrets) == len(set(secrets))

        # All secrets should be 32 characters (160 bits of entropy)
        for secret in secrets:
            assert len(secret) == 32
            assert secret.isalnum()  # Base32 alphabet
