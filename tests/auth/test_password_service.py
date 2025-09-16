"""
Test-Driven Development for Password Hashing and Validation Service
==================================================================

RED → GREEN → REFACTOR cycle for implementing secure password management
with bcrypt hashing, complexity validation, and breach checking.

Phase 4A: Core Authentication System - Password Management
"""

import re
from unittest.mock import MagicMock, Mock, patch

import pytest

# Test-driven imports - these will guide implementation
from fxml4.api.auth.password_service import (
    PasswordExpiredError,
    PasswordReuseError,
    PasswordService,
    PasswordValidationResult,
    WeakPasswordError,
)


@pytest.fixture
def password_service():
    """Create password service instance for testing."""
    return PasswordService(
        min_length=8,
        require_uppercase=True,
        require_lowercase=True,
        require_digits=True,
        require_special_chars=True,
        max_password_age_days=90,
        password_history_count=5,
        enable_breach_checking=False,  # Disable for testing
    )


class TestPasswordServiceInitialization:
    """Test password service initialization and configuration."""

    def test_password_service_creation(self):
        """Test password service can be created with valid configuration."""
        service = PasswordService(
            min_length=12,
            require_uppercase=True,
            require_lowercase=True,
            require_digits=True,
            require_special_chars=True,
        )

        assert service.min_length == 12
        assert service.require_uppercase is True
        assert service.require_lowercase is True
        assert service.require_digits is True
        assert service.require_special_chars is True

    def test_password_service_with_defaults(self):
        """Test password service uses sensible defaults."""
        service = PasswordService()

        assert service.min_length >= 8
        assert service.require_uppercase is True
        assert service.require_lowercase is True
        assert service.require_digits is True
        assert service.require_special_chars is True
        assert service.max_password_age_days == 90
        assert service.password_history_count == 5


class TestPasswordHashing:
    """Test password hashing functionality."""

    def test_hash_password(self, password_service):
        """Test password hashing generates unique hashes."""
        password = "SecurePass123!"  # pragma: allowlist secret

        hash1 = password_service.hash_password(password)
        hash2 = password_service.hash_password(password)

        # Hashes should be different due to salt
        assert hash1 != hash2
        assert len(hash1) > 50  # bcrypt hashes are long
        assert hash1.startswith("$2b$")  # bcrypt format

    def test_hash_password_with_rounds(self, password_service):
        """Test password hashing with different round counts."""
        password = "SecurePass123!"  # pragma: allowlist secret

        hash_fast = password_service.hash_password(password, rounds=4)
        hash_secure = password_service.hash_password(password, rounds=12)

        assert hash_fast != hash_secure
        assert "$2b$04$" in hash_fast  # 4 rounds
        assert "$2b$12$" in hash_secure  # 12 rounds

    def test_hash_empty_password_fails(self, password_service):
        """Test hashing empty password raises error."""
        with pytest.raises(ValueError) as exc_info:
            password_service.hash_password("")

        assert "Password cannot be empty" in str(exc_info.value)


class TestPasswordVerification:
    """Test password verification functionality."""

    def test_verify_correct_password(self, password_service):
        """Test verifying correct password succeeds."""
        password = "SecurePass123!"  # pragma: allowlist secret
        password_hash = password_service.hash_password(password)

        result = password_service.verify_password(password, password_hash)

        assert result is True

    def test_verify_incorrect_password(self, password_service):
        """Test verifying incorrect password fails."""
        password = "SecurePass123!"  # pragma: allowlist secret
        wrong_password = "WrongPass456@"  # pragma: allowlist secret
        password_hash = password_service.hash_password(password)

        result = password_service.verify_password(wrong_password, password_hash)

        assert result is False

    def test_verify_with_malformed_hash(self, password_service):
        """Test verifying with malformed hash raises error."""
        password = "SecurePass123!"  # pragma: allowlist secret
        malformed_hash = "not-a-valid-hash"

        with pytest.raises(ValueError) as exc_info:
            password_service.verify_password(password, malformed_hash)

        assert "Invalid hash format" in str(exc_info.value)


class TestPasswordValidation:
    """Test password complexity validation."""

    def test_validate_strong_password(self, password_service):
        """Test validating strong password passes."""
        strong_passwords = [
            "SecurePass123!",  # pragma: allowlist secret
            "MyP@ssw0rd2024",  # pragma: allowlist secret
            "Tr@d3rS3cur3P@ss",  # pragma: allowlist secret
            "C0mpl3x!P@ssw0rd",  # pragma: allowlist secret
        ]

        for password in strong_passwords:
            result = password_service.validate_password(password)

            assert isinstance(result, PasswordValidationResult)
            assert result.is_valid is True
            assert result.errors == []

    def test_validate_weak_passwords(self, password_service):
        """Test validating weak passwords fails with specific errors."""
        weak_passwords = [
            ("short", ["Password must be at least 8 characters long"]),
            ("nouppercase123!", ["Password must contain uppercase letters"]),
            ("NOLOWERCASE123!", ["Password must contain lowercase letters"]),
            ("NoDigitsHere!", ["Password must contain digits"]),
            ("NoSpecialChars123", ["Password must contain special characters"]),
            (
                "pwd",
                [
                    "Password must be at least 8 characters long",
                    "Password must contain uppercase letters",
                    "Password must contain digits",
                    "Password must contain special characters",
                ],
            ),
        ]

        for password, expected_errors in weak_passwords:
            result = password_service.validate_password(password)

            assert result.is_valid is False
            for expected_error in expected_errors:
                assert any(expected_error in error for error in result.errors)

    def test_validate_common_passwords(self, password_service):
        """Test validation rejects common passwords."""
        # Test passwords that are explicitly in our COMMON_PASSWORDS set
        definitely_common_passwords = [
            "password",
            "123456",
            "admin",
            "letmein",
        ]

        for password in definitely_common_passwords:
            result = password_service.validate_password(password)

            assert result.is_valid is False
            # Should contain error about being common/guessable
            error_messages = " ".join(result.errors).lower()
            assert "common" in error_messages or "guessable" in error_messages

    @pytest.mark.parametrize("special_char", ["!", "@", "#", "$", "%", "^", "&", "*"])
    def test_validate_special_characters(self, password_service, special_char):
        """Test different special characters are accepted."""
        password = f"SecurePass123{special_char}"

        result = password_service.validate_password(password)

        assert result.is_valid is True


class TestPasswordHistory:
    """Test password history and reuse prevention."""

    def test_check_password_reuse(self, password_service):
        """Test password reuse checking."""
        user_id = "test-user-123"
        password = "SecurePass123!"  # pragma: allowlist secret
        password_hash = password_service.hash_password(password)

        # Add password to history
        password_service.add_to_password_history(user_id, password_hash)

        # Check reuse
        is_reused = password_service.is_password_reused(user_id, password)

        assert is_reused is True

    def test_password_history_limit(self, password_service):
        """Test password history respects configured limit."""
        user_id = "test-user-123"
        passwords = [f"SecurePass{i}!" for i in range(10)]  # pragma: allowlist secret

        # Add passwords to history (more than limit)
        for password in passwords:
            password_hash = password_service.hash_password(password)
            password_service.add_to_password_history(user_id, password_hash)

        # Only recent passwords should be in history
        history = password_service.get_password_history(user_id)
        assert len(history) <= password_service.password_history_count

        # Oldest password should not trigger reuse check
        oldest_password = passwords[0]
        is_reused = password_service.is_password_reused(user_id, oldest_password)
        assert is_reused is False

    def test_clear_password_history(self, password_service):
        """Test clearing password history for user."""
        user_id = "test-user-123"
        password = "SecurePass123!"  # pragma: allowlist secret
        password_hash = password_service.hash_password(password)

        # Add password and clear history
        password_service.add_to_password_history(user_id, password_hash)
        password_service.clear_password_history(user_id)

        # History should be empty
        history = password_service.get_password_history(user_id)
        assert len(history) == 0


class TestPasswordExpiry:
    """Test password expiry functionality."""

    def test_check_password_expired(self, password_service):
        """Test password expiry checking."""
        from datetime import datetime, timedelta

        user_id = "test-user-123"

        # Password set long ago
        old_password_date = datetime.utcnow() - timedelta(days=100)
        is_expired = password_service.is_password_expired(user_id, old_password_date)

        assert is_expired is True

        # Recent password
        recent_password_date = datetime.utcnow() - timedelta(days=30)
        is_expired = password_service.is_password_expired(user_id, recent_password_date)

        assert is_expired is False

    def test_days_until_expiry(self, password_service):
        """Test calculating days until password expires."""
        from datetime import datetime, timedelta

        user_id = "test-user-123"

        # Password set 30 days ago
        password_date = datetime.utcnow() - timedelta(days=30)
        days_left = password_service.days_until_expiry(user_id, password_date)

        # Should have ~60 days left (90 - 30)
        assert 55 <= days_left <= 65


class TestPasswordGeneration:
    """Test secure password generation."""

    def test_generate_password(self, password_service):
        """Test password generation creates valid passwords."""
        password = password_service.generate_password()

        assert isinstance(password, str)
        assert len(password) >= password_service.min_length

        # Generated password should pass validation
        result = password_service.validate_password(password)
        assert result.is_valid is True

    def test_generate_password_with_length(self, password_service):
        """Test password generation with specific length."""
        for length in [12, 16, 20, 32]:
            password = password_service.generate_password(length=length)

            assert len(password) == length

            # Should still pass validation
            result = password_service.validate_password(password)
            assert result.is_valid is True

    def test_generate_multiple_passwords_unique(self, password_service):
        """Test multiple generated passwords are unique."""
        passwords = [password_service.generate_password() for _ in range(10)]

        # All passwords should be unique
        assert len(set(passwords)) == len(passwords)


class TestPasswordStrengthScoring:
    """Test password strength scoring functionality."""

    def test_calculate_password_strength(self, password_service):
        """Test password strength calculation."""
        test_cases = [
            ("weak", 0),  # Very weak (too short)
            ("password", 0),  # Common password (penalized)
            ("Password123", 0),  # Common pattern (penalized)
            ("SecurePass123!", 4),  # Strong  # pragma: allowlist secret
            ("C0mpl3x!P@ssw0rd2024$", 4),  # Very strong  # pragma: allowlist secret
            (
                "MyStr0ngP@ss",
                4,
            ),  # Strong non-common password  # pragma: allowlist secret
        ]

        for password, expected_strength in test_cases:
            strength = password_service.calculate_password_strength(password)

            assert isinstance(strength, int)
            assert 0 <= strength <= 4
            assert strength == expected_strength

    def test_password_strength_factors(self, password_service):
        """Test password strength considers various factors."""
        # Test length factor
        short_pass = "Aa1!"
        long_pass = "Aa1!" * 5

        short_strength = password_service.calculate_password_strength(short_pass)
        long_strength = password_service.calculate_password_strength(long_pass)

        assert long_strength > short_strength


class TestSecurityFeatures:
    """Test additional security features."""

    @patch("fxml4.api.auth.password_service.requests.get")
    def test_check_password_breach(self, mock_get, password_service):
        """Test password breach checking using HaveIBeenPwned API."""
        # Mock API response for breached password
        # password123 has SHA-1: CBFDAC6008F9CAB4083784CBD1874F76618D2A97
        # Prefix: CBFDA, Suffix: C6008F9CAB4083784CBD1874F76618D2A97
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "C6008F9CAB4083784CBD1874F76618D2A97:1234\nOTHER_HASH:5\n"
        mock_get.return_value = mock_response

        password = "password123"  # pragma: allowlist secret
        is_breached = password_service.check_password_breach(password)

        # Should detect breach
        assert is_breached is True

    @patch("fxml4.api.auth.password_service.requests.get")
    def test_check_password_not_breached(self, mock_get, password_service):
        """Test password not in breach database."""
        # Mock API response for non-breached password
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OTHER_HASH:1\nANOTHER_HASH:2\n"  # Different hashes
        mock_get.return_value = mock_response

        password = "VeryUniquePassword123!"  # pragma: allowlist secret
        is_breached = password_service.check_password_breach(password)

        # Should not detect breach
        assert is_breached is False

    def test_timing_safe_comparison(self, password_service):
        """Test password verification is timing-safe."""
        import time

        password = "SecurePass123!"  # pragma: allowlist secret
        password_hash = password_service.hash_password(password)

        # Measure time for correct password
        start = time.time()
        result1 = password_service.verify_password(password, password_hash)
        time1 = time.time() - start

        # Measure time for incorrect password
        start = time.time()
        result2 = password_service.verify_password("wrong", password_hash)
        time2 = time.time() - start

        assert result1 is True
        assert result2 is False

        # Times should be relatively similar (within 50ms for timing safety)
        time_diff = abs(time1 - time2)
        assert time_diff < 0.05  # 50ms threshold


if __name__ == "__main__":
    """
    Run password service tests with pytest.

    Usage:
        python -m pytest tests/auth/test_password_service.py -v
    """
    pytest.main([__file__, "-v", "--tb=short"])
