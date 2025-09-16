"""
Test backup and disaster recovery system.

This module tests the backup system including full/incremental backups,
encryption, compression, and recovery procedures.
"""

import asyncio
import gzip
import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.infrastructure.backup_recovery import (
    BackupMetadata,
    BackupPolicy,
    BackupRecoverySystem,
    BackupStatus,
    BackupType,
    RecoveryPoint,
)


@pytest.fixture
async def temp_backup_dir():
    """Create temporary backup directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
async def backup_system(temp_backup_dir):
    """Create backup system instance."""
    policy = BackupPolicy(
        local_path=temp_backup_dir,
        full_backup_interval=timedelta(days=1),
        incremental_interval=timedelta(hours=1),
        retention_days=7,
        compression_enabled=True,
        encryption_enabled=False,  # Disable for testing
        verify_after_backup=True,
    )

    system = BackupRecoverySystem(policy)
    yield system

    if system.is_running:
        await system.stop()


class TestBackupPolicy:
    """Test backup policy configuration."""

    def test_default_policy(self):
        """Test default policy settings."""
        policy = BackupPolicy()

        assert policy.full_backup_interval == timedelta(days=1)
        assert policy.incremental_interval == timedelta(hours=1)
        assert policy.retention_days == 30
        assert policy.compression_enabled is True
        assert policy.encryption_enabled is True
        assert policy.verify_after_backup is True

    def test_custom_policy(self):
        """Test custom policy configuration."""
        policy = BackupPolicy(
            full_backup_interval=timedelta(hours=12),
            incremental_interval=timedelta(minutes=30),
            retention_days=14,
            compression_enabled=False,
            s3_bucket="my-backup-bucket",
            s3_prefix="fxml4/backups",
        )

        assert policy.full_backup_interval == timedelta(hours=12)
        assert policy.incremental_interval == timedelta(minutes=30)
        assert policy.retention_days == 14
        assert policy.compression_enabled is False
        assert policy.s3_bucket == "my-backup-bucket"
        assert policy.s3_prefix == "fxml4/backups"


class TestBackupCreation:
    """Test backup creation functionality."""

    @pytest.mark.asyncio
    async def test_create_full_backup(self, backup_system, temp_backup_dir):
        """Test creating a full backup."""
        # Mock backup methods
        backup_system._backup_database = AsyncMock(return_value=1000000)
        backup_system._backup_configs = AsyncMock(return_value=50000)
        backup_system._backup_logs = AsyncMock(return_value=200000)
        backup_system._backup_models = AsyncMock(return_value=500000)

        # Create backup
        backup = await backup_system.create_backup(BackupType.FULL)

        assert backup.backup_type == BackupType.FULL
        assert backup.status == BackupStatus.COMPLETED
        assert backup.size_bytes == 1750000  # Sum of all components
        assert len(backup.components) == 4
        assert backup.location.startswith(str(temp_backup_dir))
        assert backup.checksum != ""

        # Verify all components backed up
        assert backup_system._backup_database.called
        assert backup_system._backup_configs.called
        assert backup_system._backup_logs.called
        assert backup_system._backup_models.called

    @pytest.mark.asyncio
    async def test_create_incremental_backup(self, backup_system):
        """Test creating an incremental backup."""
        # Add a previous full backup to history
        full_backup = BackupMetadata(
            backup_id="backup_20240101_120000_full",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
            size_bytes=1000000,
            duration_seconds=60,
            status=BackupStatus.COMPLETED,
            components=["database"],
            location="/backups/full",
            checksum="abc123",
        )
        backup_system.backup_history.append(full_backup)

        # Mock backup methods
        backup_system._backup_database = AsyncMock(return_value=100000)
        backup_system._backup_configs = AsyncMock(return_value=5000)

        # Create incremental backup
        backup = await backup_system.create_backup(
            BackupType.INCREMENTAL, components=["database", "configs"]
        )

        assert backup.backup_type == BackupType.INCREMENTAL
        assert backup.parent_backup_id == full_backup.backup_id
        assert backup.size_bytes == 105000
        assert len(backup.components) == 2

    @pytest.mark.asyncio
    async def test_backup_failure_handling(self, backup_system):
        """Test handling of backup failures."""
        # Mock database backup to fail
        backup_system._backup_database = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        backup_system._backup_configs = AsyncMock(return_value=5000)

        # Attempt backup
        with pytest.raises(Exception):
            await backup_system.create_backup(
                BackupType.FULL, components=["database", "configs"]
            )

        # Check backup marked as failed
        assert len(backup_system.backup_history) == 1
        failed_backup = backup_system.backup_history[0]
        assert failed_backup.status == BackupStatus.FAILED
        assert "Database connection failed" in failed_backup.error_message

    @pytest.mark.asyncio
    async def test_backup_with_encryption(self):
        """Test backup with encryption enabled."""
        policy = BackupPolicy(encryption_enabled=True, compression_enabled=False)

        with patch("fxml4.infrastructure.backup_recovery.Fernet") as mock_fernet:
            mock_cipher = Mock()
            mock_cipher.encrypt.return_value = b"encrypted_data"
            mock_fernet.return_value = mock_cipher

            system = BackupRecoverySystem(policy)
            system._backup_database = AsyncMock(return_value=1000)

            # Create backup
            backup = await system.create_backup(
                BackupType.FULL, components=["database"]
            )

            assert backup.encrypted is True
            assert mock_cipher.encrypt.called


class TestBackupComponents:
    """Test individual component backup methods."""

    @pytest.mark.asyncio
    async def test_backup_database(self, backup_system, temp_backup_dir):
        """Test database backup process."""
        backup = BackupMetadata(
            backup_id="test_db_backup",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc),
            size_bytes=0,
            duration_seconds=0,
            status=BackupStatus.IN_PROGRESS,
            components=["database"],
            location=str(temp_backup_dir / "test_db_backup"),
            checksum="",
        )

        # Create backup directory
        Path(backup.location).mkdir(parents=True)

        # Mock pg_dump subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"-- PostgreSQL database dump", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            size = await backup_system._backup_database(backup)

            assert size > 0

            # Check backup file created
            backup_file = Path(backup.location) / "database.sql.gz"
            assert backup_file.exists()

    @pytest.mark.asyncio
    async def test_backup_configs(self, backup_system, temp_backup_dir):
        """Test configuration backup."""
        # Create test config files
        config_dir = Path("config")
        config_dir.mkdir(exist_ok=True)

        test_config = config_dir / "test.yaml"
        test_config.write_text("test: config")

        backup = BackupMetadata(
            backup_id="test_config_backup",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc),
            size_bytes=0,
            duration_seconds=0,
            status=BackupStatus.IN_PROGRESS,
            components=["configs"],
            location=str(temp_backup_dir / "test_config_backup"),
            checksum="",
        )

        Path(backup.location).mkdir(parents=True)

        try:
            size = await backup_system._backup_configs(backup)

            assert size > 0

            # Check config backed up
            backup_config = Path(backup.location) / "configs" / "test.yaml"
            assert backup_config.exists()

        finally:
            # Cleanup
            test_config.unlink()
            config_dir.rmdir()

    @pytest.mark.asyncio
    async def test_backup_logs_incremental(self, backup_system, temp_backup_dir):
        """Test incremental log backup."""
        # Create test log files
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        old_log = logs_dir / "old.log"
        old_log.write_text("old log data")
        old_log_time = datetime.now() - timedelta(days=2)
        os.utime(old_log, (old_log_time.timestamp(), old_log_time.timestamp()))

        new_log = logs_dir / "new.log"
        new_log.write_text("new log data")

        backup = BackupMetadata(
            backup_id="test_log_backup",
            backup_type=BackupType.INCREMENTAL,
            timestamp=datetime.now(timezone.utc),
            size_bytes=0,
            duration_seconds=0,
            status=BackupStatus.IN_PROGRESS,
            components=["logs"],
            location=str(temp_backup_dir / "test_log_backup"),
            checksum="",
        )

        Path(backup.location).mkdir(parents=True)

        # Mock tar subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")

        try:
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                # Create empty tar file for test
                tar_file = Path(backup.location) / "logs" / "logs.tar.gz"
                tar_file.parent.mkdir(parents=True)
                tar_file.write_bytes(gzip.compress(b"test"))

                size = await backup_system._backup_logs(backup)

                assert size > 0

        finally:
            # Cleanup
            old_log.unlink()
            new_log.unlink()
            logs_dir.rmdir()


class TestBackupVerification:
    """Test backup verification functionality."""

    @pytest.mark.asyncio
    async def test_verify_backup_success(self, backup_system, temp_backup_dir):
        """Test successful backup verification."""
        # Create test backup
        backup_dir = temp_backup_dir / "test_backup"
        backup_dir.mkdir()

        test_file = backup_dir / "test.txt"
        test_file.write_text("test data")

        backup = BackupMetadata(
            backup_id="test_backup",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc),
            size_bytes=100,
            duration_seconds=1,
            status=BackupStatus.COMPLETED,
            components=["configs"],
            location=str(backup_dir),
            checksum="",
        )

        # Calculate correct checksum
        backup.checksum = await backup_system._calculate_backup_checksum(backup)

        # Verify
        result = await backup_system.verify_backup(backup)

        assert result is True
        assert backup.status == BackupStatus.VERIFIED
        assert backup.verification_result["checksum_valid"] is True
        assert backup.verification_result["files_readable"] is True

    @pytest.mark.asyncio
    async def test_verify_backup_checksum_mismatch(
        self, backup_system, temp_backup_dir
    ):
        """Test backup verification with checksum mismatch."""
        backup_dir = temp_backup_dir / "test_backup"
        backup_dir.mkdir()

        test_file = backup_dir / "test.txt"
        test_file.write_text("test data")

        backup = BackupMetadata(
            backup_id="test_backup",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc),
            size_bytes=100,
            duration_seconds=1,
            status=BackupStatus.COMPLETED,
            components=["configs"],
            location=str(backup_dir),
            checksum="wrong_checksum",
        )

        result = await backup_system.verify_backup(backup)

        assert result is False
        assert backup.verification_result["checksum_valid"] is False
        assert "Checksum mismatch" in backup.verification_result["errors"]


class TestBackupRestore:
    """Test backup restoration functionality."""

    @pytest.mark.asyncio
    async def test_restore_full_backup(self, backup_system, temp_backup_dir):
        """Test restoring from full backup."""
        # Create test backup
        backup = BackupMetadata(
            backup_id="test_restore",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc),
            size_bytes=1000,
            duration_seconds=10,
            status=BackupStatus.VERIFIED,
            components=["configs"],
            location=str(temp_backup_dir / "test_restore"),
            checksum="abc123",
        )

        backup_system.backup_history.append(backup)

        # Mock restore methods
        backup_system._restore_database = AsyncMock()
        backup_system._restore_configs = AsyncMock()
        backup_system._restore_models = AsyncMock()

        # Perform restore
        results = await backup_system.restore_backup(
            "test_restore", components=["configs"]
        )

        assert results["success"] is True
        assert results["backup_id"] == "test_restore"
        assert "configs" in results["restored_components"]
        assert len(results["errors"]) == 0

        # Verify correct method called
        assert backup_system._restore_configs.called
        assert not backup_system._restore_database.called

    @pytest.mark.asyncio
    async def test_restore_with_s3_download(self, backup_system):
        """Test restore requiring S3 download."""
        backup_system.policy.s3_bucket = "test-bucket"

        backup = BackupMetadata(
            backup_id="s3_backup",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc),
            size_bytes=1000,
            duration_seconds=10,
            status=BackupStatus.COMPLETED,
            components=["database"],
            location="/non/existent/path",
            checksum="abc123",
        )

        backup_system.backup_history.append(backup)

        # Mock S3 operations
        mock_s3_client = AsyncMock()
        mock_response = {"Body": AsyncMock()}
        mock_response["Body"].read.return_value = b"backup data"
        mock_s3_client.get_object.return_value = mock_response

        backup_system.s3_client = mock_s3_client
        backup_system._download_from_s3 = AsyncMock()
        backup_system._restore_database = AsyncMock()

        # Attempt restore
        results = await backup_system.restore_backup("s3_backup")

        # Should download from S3 first
        assert backup_system._download_from_s3.called

    @pytest.mark.asyncio
    async def test_point_in_time_recovery(self, backup_system):
        """Test point-in-time recovery."""
        backup = BackupMetadata(
            backup_id="pitr_backup",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=6),
            size_bytes=1000,
            duration_seconds=10,
            status=BackupStatus.VERIFIED,
            components=["database"],
            location="/backup/path",
            checksum="abc123",
        )

        backup_system.backup_history.append(backup)
        backup_system._restore_database = AsyncMock()

        # Restore to specific time
        target_time = datetime.now(timezone.utc) - timedelta(hours=3)

        results = await backup_system.restore_backup(
            "pitr_backup", target_time=target_time
        )

        # Verify restore called with target time
        backup_system._restore_database.assert_called_once()
        call_args = backup_system._restore_database.call_args
        assert call_args[0][1] == target_time


class TestBackupScheduling:
    """Test automatic backup scheduling."""

    @pytest.mark.asyncio
    async def test_backup_scheduler(self, backup_system):
        """Test backup scheduler logic."""
        # Mock backup creation
        backup_system.create_backup = AsyncMock()

        # Start system
        await backup_system.start()

        # Manually trigger scheduler logic
        with patch.object(backup_system, "_get_last_backup_time") as mock_last_backup:
            # No previous backups - should trigger full backup
            mock_last_backup.return_value = None

            # Run one iteration of scheduler
            await backup_system._backup_scheduler()

            # Should create full backup
            backup_system.create_backup.assert_called_with(BackupType.FULL)

    @pytest.mark.asyncio
    async def test_incremental_backup_scheduling(self, backup_system):
        """Test incremental backup scheduling."""
        backup_system.create_backup = AsyncMock()

        with patch.object(backup_system, "_get_last_backup_time") as mock_last_backup:
            # Full backup was 2 hours ago
            mock_last_backup.side_effect = [
                datetime.now(timezone.utc) - timedelta(hours=2),  # Last full
                datetime.now(timezone.utc) - timedelta(hours=2),  # Last any
            ]

            # Run scheduler
            await backup_system._backup_scheduler()

            # Should create incremental backup
            backup_system.create_backup.assert_called_with(BackupType.INCREMENTAL)


class TestBackupCleanup:
    """Test old backup cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_old_backups(self, backup_system, temp_backup_dir):
        """Test removal of old backups."""
        # Create old backup
        old_backup_dir = temp_backup_dir / "old_backup"
        old_backup_dir.mkdir()

        old_backup = BackupMetadata(
            backup_id="old_backup",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc) - timedelta(days=10),
            size_bytes=1000,
            duration_seconds=10,
            status=BackupStatus.COMPLETED,
            components=["database"],
            location=str(old_backup_dir),
            checksum="abc123",
        )

        # Create recent backup
        recent_backup = BackupMetadata(
            backup_id="recent_backup",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
            size_bytes=1000,
            duration_seconds=10,
            status=BackupStatus.COMPLETED,
            components=["database"],
            location=str(temp_backup_dir / "recent_backup"),
            checksum="def456",
        )

        backup_system.backup_history = [old_backup, recent_backup]

        # Run cleanup
        await backup_system._cleanup_old_backups()

        # Old backup should be removed
        assert len(backup_system.backup_history) == 1
        assert backup_system.backup_history[0].backup_id == "recent_backup"
        assert not old_backup_dir.exists()

    @pytest.mark.asyncio
    async def test_cleanup_with_s3(self, backup_system):
        """Test cleanup of S3 backups."""
        backup_system.policy.s3_bucket = "test-bucket"

        mock_s3_client = AsyncMock()
        backup_system.s3_client = mock_s3_client

        old_backup = BackupMetadata(
            backup_id="s3_old_backup",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc) - timedelta(days=40),
            size_bytes=1000,
            duration_seconds=10,
            status=BackupStatus.COMPLETED,
            components=["database"],
            location="/tmp/gone",
            checksum="abc123",
        )

        backup_system.backup_history = [old_backup]

        # Run cleanup
        await backup_system._cleanup_old_backups()

        # Should delete from S3
        mock_s3_client.delete_object.assert_called_once()
        call_args = mock_s3_client.delete_object.call_args
        assert call_args[1]["Key"] == "backups/s3_old_backup.tar.gz"


class TestBackupHistory:
    """Test backup history management."""

    @pytest.mark.asyncio
    async def test_save_and_load_history(self, backup_system, temp_backup_dir):
        """Test saving and loading backup history."""
        # Add backups to history
        backup1 = BackupMetadata(
            backup_id="backup1",
            backup_type=BackupType.FULL,
            timestamp=datetime.now(timezone.utc),
            size_bytes=1000,
            duration_seconds=10,
            status=BackupStatus.COMPLETED,
            components=["database"],
            location=str(temp_backup_dir / "backup1"),
            checksum="abc123",
        )

        backup2 = BackupMetadata(
            backup_id="backup2",
            backup_type=BackupType.INCREMENTAL,
            timestamp=datetime.now(timezone.utc),
            size_bytes=500,
            duration_seconds=5,
            status=BackupStatus.VERIFIED,
            components=["configs"],
            location=str(temp_backup_dir / "backup2"),
            checksum="def456",
            parent_backup_id="backup1",
        )

        backup_system.backup_history = [backup1, backup2]

        # Save history
        await backup_system._save_backup_history()

        # Clear and reload
        backup_system.backup_history = []
        await backup_system._load_backup_history()

        # Verify loaded correctly
        assert len(backup_system.backup_history) == 2
        assert backup_system.backup_history[0].backup_id == "backup1"
        assert backup_system.backup_history[1].backup_id == "backup2"
        assert backup_system.backup_history[1].parent_backup_id == "backup1"

    def test_get_backup_status(self, backup_system):
        """Test backup status reporting."""
        # Add some backups
        backup_system.backup_history = [
            BackupMetadata(
                backup_id=f"backup_{i}",
                backup_type=BackupType.FULL if i % 2 == 0 else BackupType.INCREMENTAL,
                timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
                size_bytes=1000000 * (i + 1),
                duration_seconds=60,
                status=BackupStatus.COMPLETED if i < 3 else BackupStatus.FAILED,
                components=["database"],
                location=f"/backup_{i}",
                checksum=f"hash_{i}",
            )
            for i in range(5)
        ]

        status = backup_system.get_backup_status()

        assert status["is_running"] is False
        assert status["total_backups"] == 5
        assert status["failed_backups"] == 2
        assert len(status["recent_backups"]) == 5
        assert status["policy"]["retention_days"] == 7
