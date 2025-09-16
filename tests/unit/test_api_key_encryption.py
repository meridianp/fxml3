"""
Unit tests for API Key Encryption.

Tests comprehensive API key security functionality including:
- Key encryption and decryption
- Key generation and rotation
- Secure storage mechanisms
- Access logging and audit trails
- Key derivation and stretching
- Multiple encryption algorithms
- Hardware security module integration
- Key versioning and migration
"""

import base64
import hashlib
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from core.authentication.api_key_encryption import APIKeyEncryption
from core.exceptions import AuthenticationError, ConfigurationError, InvalidTokenError


class TestAPIKeyEncryption:
    """Test suite for API key encryption and management."""

    @pytest.fixture
    def encryption_config(self):
        """Configuration for API key encryption."""
        return {
            "master_key": "test_master_key_32_characters!!!",  # pragma: allowlist secret
            "algorithm": "AES-256-GCM",
            "key_derivation": "PBKDF2",
            "salt_length": 32,
            "iterations": 100000,
            "key_rotation_days": 90,
            "audit_enabled": True,
            "hsm_enabled": False,
            "backup_keys": 3,
        }

    @pytest.fixture
    def api_key_manager(self, encryption_config):
        """Create API key encryption manager for testing."""
        return APIKeyEncryption(encryption_config)

    @pytest.fixture
    def sample_api_key(self):
        """Sample API key for testing."""
        return "ak_test_1234567890abcdef_live_trading_key"  # pragma: allowlist secret

    def test_encrypts_api_key(self, api_key_manager, sample_api_key):
        """Test API key encryption with proper algorithm."""
        encrypted = api_key_manager.encrypt_api_key(sample_api_key, "user123")

        # Verify encryption structure
        assert "encrypted_data" in encrypted
        assert "salt" in encrypted
        assert "iv" in encrypted
        assert "tag" in encrypted  # GCM authentication tag
        assert "algorithm" in encrypted
        assert "version" in encrypted
        assert "user_id" in encrypted
        assert "created_at" in encrypted

        # Verify encrypted data is different from original
        assert encrypted["encrypted_data"] != sample_api_key
        assert len(encrypted["encrypted_data"]) > len(sample_api_key)

    def test_decrypts_api_key(self, api_key_manager, sample_api_key):
        """Test API key decryption recovers original key."""
        # Encrypt the key
        encrypted = api_key_manager.encrypt_api_key(sample_api_key, "user123")

        # Decrypt it back
        decrypted = api_key_manager.decrypt_api_key(encrypted)

        assert decrypted == sample_api_key

    def test_generates_secure_api_key(self, api_key_manager):
        """Test generation of cryptographically secure API keys."""
        api_key = api_key_manager.generate_api_key("user123", "live")

        # Verify key format
        assert api_key.startswith("ak_")
        assert "_live_" in api_key
        assert len(api_key) >= 64  # Sufficient entropy

        # Verify uniqueness
        api_key2 = api_key_manager.generate_api_key("user123", "live")
        assert api_key != api_key2

    def test_validates_api_key_format(self, api_key_manager):
        """Test API key format validation."""
        valid_key = (
            "ak_test_1234567890abcdef_live_trading_key"  # pragma: allowlist secret
        )
        invalid_keys = [
            "invalid_key",
            "sk_test_key",  # Wrong prefix
            "ak_test",  # Too short
            "ak_test_key_with_invalid_chars!@#",
        ]

        # Valid key should pass
        assert api_key_manager.validate_key_format(valid_key) is True

        # Invalid keys should fail
        for invalid_key in invalid_keys:
            assert api_key_manager.validate_key_format(invalid_key) is False

    def test_rotates_encryption_keys(self, api_key_manager, sample_api_key):
        """Test encryption key rotation functionality."""
        # Encrypt with current key
        encrypted_v1 = api_key_manager.encrypt_api_key(sample_api_key, "user123")
        assert encrypted_v1["version"] == 1

        # Rotate keys
        api_key_manager.rotate_master_key()

        # New encryption should use new version
        encrypted_v2 = api_key_manager.encrypt_api_key(sample_api_key, "user123")
        assert encrypted_v2["version"] == 2

        # Should still be able to decrypt old version
        decrypted_v1 = api_key_manager.decrypt_api_key(encrypted_v1)
        assert decrypted_v1 == sample_api_key

        # New version should also decrypt correctly
        decrypted_v2 = api_key_manager.decrypt_api_key(encrypted_v2)
        assert decrypted_v2 == sample_api_key

    def test_enforces_key_expiration(self, api_key_manager):
        """Test API key expiration enforcement."""
        with freeze_time("2025-01-01 12:00:00"):
            # Generate key with expiration
            key_data = api_key_manager.generate_api_key_with_expiry(
                "user123", "live", expires_days=30
            )

        # Key should be valid within expiration period
        with freeze_time("2025-01-15 12:00:00"):
            assert api_key_manager.is_key_expired(key_data) is False

        # Key should be expired after expiration period
        with freeze_time("2025-02-15 12:00:00"):
            assert api_key_manager.is_key_expired(key_data) is True

    def test_logs_api_key_access(self, api_key_manager, sample_api_key):
        """Test audit logging of API key access."""
        # Mock the audit logger
        with patch.object(api_key_manager, "_audit_logger") as mock_logger:
            # Encrypt and decrypt operations
            encrypted = api_key_manager.encrypt_api_key(sample_api_key, "user123")
            api_key_manager.decrypt_api_key(encrypted)

            # Verify audit logs were created
            assert mock_logger.log_key_access.call_count >= 2

            # Verify log content
            encrypt_call = mock_logger.log_key_access.call_args_list[0][1]
            assert encrypt_call["operation"] == "encrypt"
            assert encrypt_call["user_id"] == "user123"

            decrypt_call = mock_logger.log_key_access.call_args_list[1][1]
            assert decrypt_call["operation"] == "decrypt"

    def test_prevents_key_reuse_attacks(self, api_key_manager, sample_api_key):
        """Test prevention of key reuse and replay attacks."""
        # Generate multiple encrypted versions of same key
        encrypted1 = api_key_manager.encrypt_api_key(sample_api_key, "user123")
        encrypted2 = api_key_manager.encrypt_api_key(sample_api_key, "user123")

        # Each encryption should produce different ciphertext (due to random IV)
        assert encrypted1["encrypted_data"] != encrypted2["encrypted_data"]
        assert encrypted1["iv"] != encrypted2["iv"]
        assert encrypted1["salt"] != encrypted2["salt"]

        # But both should decrypt to same plaintext
        assert api_key_manager.decrypt_api_key(encrypted1) == sample_api_key
        assert api_key_manager.decrypt_api_key(encrypted2) == sample_api_key

    def test_handles_multiple_algorithms(self, api_key_manager, sample_api_key):
        """Test support for multiple encryption algorithms."""
        algorithms = ["AES-256-GCM", "AES-256-CBC", "ChaCha20-Poly1305"]

        for algorithm in algorithms:
            # Update algorithm
            api_key_manager.set_algorithm(algorithm)

            # Test encryption/decryption
            encrypted = api_key_manager.encrypt_api_key(sample_api_key, "user123")
            decrypted = api_key_manager.decrypt_api_key(encrypted)

            assert encrypted["algorithm"] == algorithm
            assert decrypted == sample_api_key

    def test_derives_keys_from_password(self, api_key_manager):
        """Test key derivation from master password."""
        password = "secure_master_password_123!"  # pragma: allowlist secret
        salt = os.urandom(32)

        # Derive key using PBKDF2
        derived_key1 = api_key_manager.derive_key_pbkdf2(password, salt, 100000)
        derived_key2 = api_key_manager.derive_key_pbkdf2(password, salt, 100000)

        # Same input should produce same key
        assert derived_key1 == derived_key2
        assert len(derived_key1) == 32  # 256 bits

        # Different salt should produce different key
        different_salt = os.urandom(32)
        derived_key3 = api_key_manager.derive_key_pbkdf2(
            password, different_salt, 100000
        )
        assert derived_key1 != derived_key3

    def test_manages_key_versions(self, api_key_manager, sample_api_key):
        """Test key version management and migration."""
        # Encrypt with version 1
        encrypted_v1 = api_key_manager.encrypt_api_key(sample_api_key, "user123")

        # Rotate to version 2
        api_key_manager.rotate_master_key()
        encrypted_v2 = api_key_manager.encrypt_api_key(sample_api_key, "user123")

        # Rotate to version 3
        api_key_manager.rotate_master_key()
        encrypted_v3 = api_key_manager.encrypt_api_key(sample_api_key, "user123")

        # Should be able to decrypt all versions
        assert api_key_manager.decrypt_api_key(encrypted_v1) == sample_api_key
        assert api_key_manager.decrypt_api_key(encrypted_v2) == sample_api_key
        assert api_key_manager.decrypt_api_key(encrypted_v3) == sample_api_key

        # Migrate old version to new
        migrated = api_key_manager.migrate_key_version(encrypted_v1, target_version=3)
        assert migrated["version"] == 3
        assert api_key_manager.decrypt_api_key(migrated) == sample_api_key

    def test_validates_encrypted_data_integrity(self, api_key_manager, sample_api_key):
        """Test validation of encrypted data integrity."""
        encrypted = api_key_manager.encrypt_api_key(sample_api_key, "user123")

        # Valid data should pass integrity check
        assert api_key_manager.verify_integrity(encrypted) is True

        # Corrupted data should fail
        corrupted = encrypted.copy()
        corrupted["encrypted_data"] = corrupted["encrypted_data"][:-1] + "X"

        assert api_key_manager.verify_integrity(corrupted) is False

        # Should raise error on decryption
        with pytest.raises(AuthenticationError) as exc_info:
            api_key_manager.decrypt_api_key(corrupted)

        assert "integrity check failed" in str(exc_info.value).lower()

    def test_implements_rate_limiting(self, api_key_manager, sample_api_key):
        """Test rate limiting for encryption/decryption operations."""
        # Set aggressive rate limit
        api_key_manager.set_rate_limit(operations_per_minute=5)

        # Should allow operations within limit
        for i in range(5):
            encrypted = api_key_manager.encrypt_api_key(
                f"{sample_api_key}_{i}", "user123"
            )
            assert encrypted is not None

        # Should block operations beyond limit
        with pytest.raises(AuthenticationError) as exc_info:
            api_key_manager.encrypt_api_key(sample_api_key, "user123")

        assert "rate limit exceeded" in str(exc_info.value).lower()

    @patch("core.authentication.api_key_encryption.HSMClient")
    def test_integrates_with_hsm(
        self, mock_hsm_client, api_key_manager, sample_api_key
    ):
        """Test Hardware Security Module integration."""
        # Mock HSM operations
        mock_hsm = MagicMock()
        mock_hsm_client.return_value = mock_hsm
        mock_hsm.encrypt.return_value = b"hsm_encrypted_data"
        mock_hsm.decrypt.return_value = sample_api_key.encode()

        # Enable HSM mode with mock client
        api_key_manager.enable_hsm(mock_hsm)

        # Test encryption with HSM
        encrypted = api_key_manager.encrypt_api_key(sample_api_key, "user123")

        # Verify HSM was called
        mock_hsm.encrypt.assert_called_once()
        assert encrypted["hsm_enabled"] is True

        # Test decryption with HSM
        decrypted = api_key_manager.decrypt_api_key(encrypted)
        assert decrypted == sample_api_key

    def test_creates_key_backup(self, api_key_manager, sample_api_key):
        """Test encrypted key backup functionality."""
        # Encrypt key and create backup
        encrypted = api_key_manager.encrypt_api_key(sample_api_key, "user123")
        backup_data = api_key_manager.create_key_backup(encrypted)

        # Backup should contain encrypted master keys
        assert "backup_keys" in backup_data
        assert "backup_metadata" in backup_data
        assert len(backup_data["backup_keys"]) > 0

        # Should be able to restore from backup
        restored = api_key_manager.restore_from_backup(backup_data, encrypted)
        decrypted = api_key_manager.decrypt_api_key(restored)
        assert decrypted == sample_api_key

    def test_enforces_security_policies(self, api_key_manager):
        """Test enforcement of security policies."""
        # Test weak key rejection
        weak_keys = [
            "ak_weak_key",
            "ak_123456789012345_test_weak",
            "ak_repeated_repeated_repeated_test",
        ]

        for weak_key in weak_keys:
            with pytest.raises(ConfigurationError) as exc_info:
                api_key_manager.validate_key_strength(weak_key)

            assert "insufficient entropy" in str(exc_info.value).lower()

    def test_handles_concurrent_access(self, api_key_manager, sample_api_key):
        """Test thread-safe concurrent key operations."""
        import threading
        import time

        results = []
        errors = []

        def encrypt_decrypt_worker():
            try:
                encrypted = api_key_manager.encrypt_api_key(
                    sample_api_key, f"user_{threading.current_thread().ident}"
                )
                time.sleep(0.01)  # Small delay to increase chance of race conditions
                decrypted = api_key_manager.decrypt_api_key(encrypted)
                results.append(decrypted)
            except Exception as e:
                errors.append(e)

        # Run multiple threads concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(target=encrypt_decrypt_worker)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no errors and all results correct
        assert len(errors) == 0
        assert len(results) == 10
        assert all(result == sample_api_key for result in results)

    def test_exports_encrypted_keys(self, api_key_manager, sample_api_key):
        """Test secure export of encrypted keys."""
        # Create multiple encrypted keys
        keys = []
        for i in range(3):
            encrypted = api_key_manager.encrypt_api_key(
                f"{sample_api_key}_{i}", f"user_{i}"
            )
            keys.append(encrypted)

        # Export keys securely
        export_data = api_key_manager.export_keys(
            keys, export_password="export_pass_123!"  # pragma: allowlist secret
        )

        # Export should be encrypted
        assert "encrypted_keys" in export_data
        assert "export_metadata" in export_data
        assert export_data["encrypted_keys"] != keys  # Should be encrypted

        # Should be able to import back
        imported_keys = api_key_manager.import_keys(
            export_data, import_password="export_pass_123!"  # pragma: allowlist secret
        )

        # Verify imported keys can be decrypted
        for i, imported_key in enumerate(imported_keys):
            decrypted = api_key_manager.decrypt_api_key(imported_key)
            assert decrypted == f"{sample_api_key}_{i}"
