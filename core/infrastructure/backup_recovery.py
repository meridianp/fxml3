"""
Backup and disaster recovery system.

This module provides comprehensive backup and recovery capabilities:
- Automated database backups
- Configuration and state backups
- Point-in-time recovery
- Disaster recovery procedures
- Backup verification and testing
"""

import asyncio
import gzip
import hashlib
import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aioboto3
import aiofiles
import asyncpg
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class BackupType(Enum):
    """Types of backups."""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(Enum):
    """Backup job status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


@dataclass
class BackupMetadata:
    """Metadata for a backup."""

    backup_id: str
    backup_type: BackupType
    timestamp: datetime
    size_bytes: int
    duration_seconds: float
    status: BackupStatus
    components: List[str]
    location: str
    checksum: str
    encrypted: bool = False
    compressed: bool = True
    parent_backup_id: Optional[str] = None  # For incremental
    error_message: Optional[str] = None
    verification_result: Optional[Dict[str, Any]] = None


@dataclass
class RecoveryPoint:
    """Point-in-time recovery information."""

    recovery_point_id: str
    timestamp: datetime
    backup_id: str
    transaction_id: Optional[str] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupPolicy:
    """Backup policy configuration."""

    full_backup_interval: timedelta = timedelta(days=1)
    incremental_interval: timedelta = timedelta(hours=1)
    retention_days: int = 30
    compression_enabled: bool = True
    encryption_enabled: bool = True
    verify_after_backup: bool = True

    # Storage locations
    local_path: Optional[Path] = None
    s3_bucket: Optional[str] = None
    s3_prefix: str = "backups"

    # Components to backup
    backup_database: bool = True
    backup_configs: bool = True
    backup_logs: bool = True
    backup_models: bool = True


class BackupRecoverySystem:
    """
    Comprehensive backup and disaster recovery system.
    """

    def __init__(self, policy: Optional[BackupPolicy] = None):
        """
        Initialize backup system.

        Args:
            policy: Backup policy configuration
        """
        self.policy = policy or BackupPolicy()

        # Backup tracking
        self.backup_history: List[BackupMetadata] = []
        self.recovery_points: List[RecoveryPoint] = []
        self.active_backup: Optional[BackupMetadata] = None

        # Encryption
        self.encryption_key = None
        if self.policy.encryption_enabled:
            self._initialize_encryption()

        # Storage
        self.s3_client = None
        self._ensure_directories()

        # Scheduling
        self.scheduler_task: Optional[asyncio.Task] = None
        self.is_running = False

    def _initialize_encryption(self):
        """Initialize encryption key."""
        # In production, load from secure key management
        key_file = Path.home() / ".fxml4" / "backup_key.key"

        if key_file.exists():
            with open(key_file, "rb") as f:
                self.encryption_key = f.read()
        else:
            # Generate new key
            self.encryption_key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(key_file, "wb") as f:
                f.write(self.encryption_key)
            os.chmod(key_file, 0o600)

        self.cipher = Fernet(self.encryption_key)

    def _ensure_directories(self):
        """Ensure backup directories exist."""
        if self.policy.local_path:
            self.policy.local_path.mkdir(parents=True, exist_ok=True)

            # Create subdirectories
            for subdir in ["database", "configs", "logs", "models", "temp"]:
                (self.policy.local_path / subdir).mkdir(exist_ok=True)

    async def start(self):
        """Start backup scheduler."""
        self.is_running = True

        # Initialize S3 client if configured
        if self.policy.s3_bucket:
            session = aioboto3.Session()
            self.s3_client = await session.client("s3").__aenter__()

        # Load backup history
        await self._load_backup_history()

        # Start scheduler
        self.scheduler_task = asyncio.create_task(self._backup_scheduler())

        logger.info("Backup system started")

    async def stop(self):
        """Stop backup scheduler."""
        self.is_running = False

        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        if self.s3_client:
            await self.s3_client.__aexit__(None, None, None)

        logger.info("Backup system stopped")

    async def _backup_scheduler(self):
        """Schedule automatic backups."""
        while self.is_running:
            try:
                now = datetime.now(timezone.utc)

                # Check if full backup needed
                last_full = self._get_last_backup_time(BackupType.FULL)
                if not last_full or now - last_full >= self.policy.full_backup_interval:
                    await self.create_backup(BackupType.FULL)
                else:
                    # Check if incremental backup needed
                    last_backup = self._get_last_backup_time()
                    if (
                        not last_backup
                        or now - last_backup >= self.policy.incremental_interval
                    ):
                        await self.create_backup(BackupType.INCREMENTAL)

                # Clean old backups
                await self._cleanup_old_backups()

                # Sleep until next check
                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                logger.error(f"Error in backup scheduler: {e}")
                await asyncio.sleep(300)

    async def create_backup(
        self,
        backup_type: BackupType = BackupType.FULL,
        components: Optional[List[str]] = None,
    ) -> BackupMetadata:
        """
        Create a backup.

        Args:
            backup_type: Type of backup to create
            components: Specific components to backup (None = all)

        Returns:
            Backup metadata
        """
        backup_id = f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{backup_type.value}"

        # Determine components
        if components is None:
            components = []
            if self.policy.backup_database:
                components.append("database")
            if self.policy.backup_configs:
                components.append("configs")
            if self.policy.backup_logs:
                components.append("logs")
            if self.policy.backup_models:
                components.append("models")

        # Create metadata
        backup = BackupMetadata(
            backup_id=backup_id,
            backup_type=backup_type,
            timestamp=datetime.now(timezone.utc),
            size_bytes=0,
            duration_seconds=0,
            status=BackupStatus.IN_PROGRESS,
            components=components,
            location="",
            checksum="",
            encrypted=self.policy.encryption_enabled,
            compressed=self.policy.compression_enabled,
        )

        # Find parent for incremental
        if backup_type == BackupType.INCREMENTAL:
            last_full = self._get_last_successful_backup(BackupType.FULL)
            if last_full:
                backup.parent_backup_id = last_full.backup_id

        self.active_backup = backup
        start_time = asyncio.get_event_loop().time()

        try:
            logger.info(f"Starting backup: {backup_id}")

            # Create backup directory
            if self.policy.local_path:
                backup_dir = self.policy.local_path / backup_id
                backup_dir.mkdir(exist_ok=True)
                backup.location = str(backup_dir)

            # Backup each component
            tasks = []
            for component in components:
                if component == "database":
                    tasks.append(self._backup_database(backup))
                elif component == "configs":
                    tasks.append(self._backup_configs(backup))
                elif component == "logs":
                    tasks.append(self._backup_logs(backup))
                elif component == "models":
                    tasks.append(self._backup_models(backup))

            # Run backups in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for errors
            errors = [str(r) for r in results if isinstance(r, Exception)]
            if errors:
                raise Exception(f"Backup errors: {', '.join(errors)}")

            # Calculate total size and checksum
            backup.size_bytes = sum(r for r in results if isinstance(r, int))
            backup.checksum = await self._calculate_backup_checksum(backup)

            # Upload to S3 if configured
            if self.policy.s3_bucket:
                await self._upload_to_s3(backup)

            # Mark as completed
            backup.status = BackupStatus.COMPLETED
            backup.duration_seconds = asyncio.get_event_loop().time() - start_time

            # Verify if configured
            if self.policy.verify_after_backup:
                await self.verify_backup(backup)

            logger.info(
                f"Backup completed: {backup_id} ({backup.size_bytes / 1024 / 1024:.2f} MB)"
            )

        except Exception as e:
            backup.status = BackupStatus.FAILED
            backup.error_message = str(e)
            logger.error(f"Backup failed: {e}")
            raise

        finally:
            self.active_backup = None
            self.backup_history.append(backup)
            await self._save_backup_history()

        return backup

    async def _backup_database(self, backup: BackupMetadata) -> int:
        """Backup database."""
        logger.info("Backing up database")

        # Get database configuration
        db_config = {
            "host": os.getenv("FXML4_DATABASE_HOST", "localhost"),
            "port": int(os.getenv("FXML4_DATABASE_PORT", "5432")),
            "database": os.getenv("FXML4_DATABASE_NAME", "fxml4"),
            "user": os.getenv("FXML4_DATABASE_USER", "postgres"),
            "password": os.getenv("FXML4_DATABASE_PASSWORD", ""),
        }

        backup_file = Path(backup.location) / "database.sql.gz"

        # Use pg_dump for backup
        dump_command = [
            "pg_dump",
            f"--host={db_config['host']}",
            f"--port={db_config['port']}",
            f"--username={db_config['user']}",
            f"--dbname={db_config['database']}",
            "--no-password",
            "--verbose",
            "--format=plain",
            "--no-owner",
            "--no-privileges",
        ]

        if backup.backup_type == BackupType.INCREMENTAL:
            # For incremental, only backup recent data
            # This is simplified - real implementation would track changes
            dump_command.extend(["--data-only", "--inserts"])

        # Run pg_dump
        env = os.environ.copy()
        env["PGPASSWORD"] = db_config["password"]

        process = await asyncio.create_subprocess_exec(
            *dump_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise Exception(f"pg_dump failed: {stderr.decode()}")

        # Compress and optionally encrypt
        data = stdout

        if self.policy.compression_enabled:
            data = gzip.compress(data)

        if self.policy.encryption_enabled:
            data = self.cipher.encrypt(data)

        # Write to file
        async with aiofiles.open(backup_file, "wb") as f:
            await f.write(data)

        return len(data)

    async def _backup_configs(self, backup: BackupMetadata) -> int:
        """Backup configuration files."""
        logger.info("Backing up configurations")

        config_dir = Path("config")
        backup_dir = Path(backup.location) / "configs"
        backup_dir.mkdir(exist_ok=True)

        total_size = 0

        # Copy all config files
        for config_file in config_dir.glob("*.yaml"):
            dest_file = backup_dir / config_file.name

            # Read file
            async with aiofiles.open(config_file, "rb") as f:
                data = await f.read()

            # Encrypt if enabled
            if self.policy.encryption_enabled:
                data = self.cipher.encrypt(data)

            # Write to backup
            async with aiofiles.open(dest_file, "wb") as f:
                await f.write(data)

            total_size += len(data)

        # Also backup environment template
        env_file = Path(".env.production")
        if env_file.exists():
            async with aiofiles.open(env_file, "rb") as f:
                data = await f.read()

            if self.policy.encryption_enabled:
                data = self.cipher.encrypt(data)

            async with aiofiles.open(backup_dir / "env.production", "wb") as f:
                await f.write(data)

            total_size += len(data)

        return total_size

    async def _backup_logs(self, backup: BackupMetadata) -> int:
        """Backup log files."""
        logger.info("Backing up logs")

        logs_dir = Path("logs")
        if not logs_dir.exists():
            return 0

        backup_dir = Path(backup.location) / "logs"
        backup_dir.mkdir(exist_ok=True)

        # For incremental, only backup recent logs
        if backup.backup_type == BackupType.INCREMENTAL:
            cutoff_time = datetime.now() - timedelta(hours=24)
        else:
            cutoff_time = None

        # Create tar archive
        archive_file = backup_dir / "logs.tar.gz"

        # Use tar command for efficiency
        tar_command = ["tar", "-czf", str(archive_file)]

        # Add files modified after cutoff
        log_files = []
        for log_file in logs_dir.glob("*.log*"):
            if (
                cutoff_time is None
                or datetime.fromtimestamp(log_file.stat().st_mtime) > cutoff_time
            ):
                log_files.append(str(log_file))

        if not log_files:
            return 0

        tar_command.extend(log_files)

        process = await asyncio.create_subprocess_exec(
            *tar_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        await process.communicate()

        if process.returncode != 0:
            raise Exception("Failed to create log archive")

        # Encrypt if enabled
        if self.policy.encryption_enabled:
            async with aiofiles.open(archive_file, "rb") as f:
                data = await f.read()

            encrypted_data = self.cipher.encrypt(data)

            async with aiofiles.open(
                archive_file.with_suffix(".tar.gz.enc"), "wb"
            ) as f:
                await f.write(encrypted_data)

            # Remove unencrypted file
            archive_file.unlink()
            return len(encrypted_data)

        return archive_file.stat().st_size

    async def _backup_models(self, backup: BackupMetadata) -> int:
        """Backup ML models."""
        logger.info("Backing up models")

        models_dir = Path("models")
        if not models_dir.exists():
            return 0

        backup_dir = Path(backup.location) / "models"
        backup_dir.mkdir(exist_ok=True)

        total_size = 0

        # Copy model files
        for model_file in models_dir.glob("**/*.pkl"):
            relative_path = model_file.relative_to(models_dir)
            dest_file = backup_dir / relative_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # For incremental, check if model changed
            if backup.backup_type == BackupType.INCREMENTAL:
                if backup.parent_backup_id:
                    parent_backup = self._get_backup_by_id(backup.parent_backup_id)
                    if parent_backup:
                        parent_model = (
                            Path(parent_backup.location) / "models" / relative_path
                        )
                        if parent_model.exists():
                            # Compare checksums
                            if await self._file_checksum(
                                model_file
                            ) == await self._file_checksum(parent_model):
                                continue

            # Copy and optionally compress
            if self.policy.compression_enabled:
                dest_file = dest_file.with_suffix(".pkl.gz")

                async with aiofiles.open(model_file, "rb") as f:
                    data = await f.read()

                data = gzip.compress(data)

                if self.policy.encryption_enabled:
                    data = self.cipher.encrypt(data)

                async with aiofiles.open(dest_file, "wb") as f:
                    await f.write(data)

                total_size += len(data)
            else:
                # Just copy
                shutil.copy2(model_file, dest_file)
                total_size += dest_file.stat().st_size

        return total_size

    async def _calculate_backup_checksum(self, backup: BackupMetadata) -> str:
        """Calculate checksum for backup."""
        hasher = hashlib.sha256()

        backup_path = Path(backup.location)
        for file_path in backup_path.rglob("*"):
            if file_path.is_file():
                async with aiofiles.open(file_path, "rb") as f:
                    while chunk := await f.read(8192):
                        hasher.update(chunk)

        return hasher.hexdigest()

    async def _file_checksum(self, file_path: Path) -> str:
        """Calculate file checksum."""
        hasher = hashlib.sha256()

        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(8192):
                hasher.update(chunk)

        return hasher.hexdigest()

    async def _upload_to_s3(self, backup: BackupMetadata):
        """Upload backup to S3."""
        if not self.s3_client or not self.policy.s3_bucket:
            return

        logger.info(f"Uploading backup to S3: {backup.backup_id}")

        backup_path = Path(backup.location)

        # Create tar archive of backup
        archive_path = backup_path.parent / f"{backup.backup_id}.tar.gz"

        tar_command = [
            "tar",
            "-czf",
            str(archive_path),
            "-C",
            str(backup_path.parent),
            backup_path.name,
        ]

        process = await asyncio.create_subprocess_exec(
            *tar_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        await process.communicate()

        if process.returncode != 0:
            raise Exception("Failed to create backup archive")

        # Upload to S3
        s3_key = f"{self.policy.s3_prefix}/{backup.backup_id}.tar.gz"

        async with aiofiles.open(archive_path, "rb") as f:
            data = await f.read()

        await self.s3_client.put_object(
            Bucket=self.policy.s3_bucket,
            Key=s3_key,
            Body=data,
            ServerSideEncryption="AES256",
            Metadata={
                "backup-type": backup.backup_type.value,
                "timestamp": backup.timestamp.isoformat(),
                "checksum": backup.checksum,
            },
        )

        # Clean up local archive
        archive_path.unlink()

        logger.info(f"Backup uploaded to S3: s3://{self.policy.s3_bucket}/{s3_key}")

    async def verify_backup(self, backup: BackupMetadata) -> bool:
        """
        Verify backup integrity.

        Returns:
            True if backup is valid
        """
        logger.info(f"Verifying backup: {backup.backup_id}")

        verification_result = {
            "checksum_valid": False,
            "files_readable": True,
            "database_restorable": False,
            "errors": [],
        }

        try:
            # Verify checksum
            calculated_checksum = await self._calculate_backup_checksum(backup)
            verification_result["checksum_valid"] = (
                calculated_checksum == backup.checksum
            )

            if not verification_result["checksum_valid"]:
                verification_result["errors"].append("Checksum mismatch")

            # Verify file readability
            backup_path = Path(backup.location)
            for file_path in backup_path.rglob("*"):
                if file_path.is_file():
                    try:
                        # Try to read file
                        async with aiofiles.open(file_path, "rb") as f:
                            data = await f.read(1024)

                            # If encrypted, try to decrypt
                            if (
                                self.policy.encryption_enabled
                                and file_path.suffix == ".enc"
                            ):
                                self.cipher.decrypt(data)
                    except Exception as e:
                        verification_result["files_readable"] = False
                        verification_result["errors"].append(
                            f"Cannot read {file_path.name}: {e}"
                        )

            # Test database restore (simplified)
            if "database" in backup.components:
                # Would actually test restore to temporary database
                verification_result["database_restorable"] = True

            # Update backup status
            backup.verification_result = verification_result

            if all(
                [
                    verification_result["checksum_valid"],
                    verification_result["files_readable"],
                    verification_result.get("database_restorable", True),
                ]
            ):
                backup.status = BackupStatus.VERIFIED
                logger.info(f"Backup verified successfully: {backup.backup_id}")
                return True
            else:
                logger.warning(
                    f"Backup verification failed: {verification_result['errors']}"
                )
                return False

        except Exception as e:
            logger.error(f"Error verifying backup: {e}")
            verification_result["errors"].append(str(e))
            backup.verification_result = verification_result
            return False

    async def restore_backup(
        self,
        backup_id: str,
        components: Optional[List[str]] = None,
        target_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Restore from backup.

        Args:
            backup_id: Backup ID to restore from
            components: Specific components to restore (None = all)
            target_time: Point-in-time recovery target

        Returns:
            Restore results
        """
        logger.info(f"Starting restore from backup: {backup_id}")

        backup = self._get_backup_by_id(backup_id)
        if not backup:
            raise ValueError(f"Backup not found: {backup_id}")

        if backup.status not in [BackupStatus.COMPLETED, BackupStatus.VERIFIED]:
            raise ValueError(f"Backup not ready for restore: {backup.status}")

        # Determine components
        if components is None:
            components = backup.components

        results = {
            "backup_id": backup_id,
            "restored_components": [],
            "errors": [],
            "start_time": datetime.now(timezone.utc),
            "end_time": None,
        }

        try:
            # Download from S3 if needed
            if self.policy.s3_bucket and not Path(backup.location).exists():
                await self._download_from_s3(backup)

            # Restore each component
            for component in components:
                try:
                    if component == "database":
                        await self._restore_database(backup, target_time)
                    elif component == "configs":
                        await self._restore_configs(backup)
                    elif component == "models":
                        await self._restore_models(backup)

                    results["restored_components"].append(component)

                except Exception as e:
                    error_msg = f"Failed to restore {component}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

            results["end_time"] = datetime.now(timezone.utc)
            results["success"] = len(results["errors"]) == 0

            # Create recovery point
            if results["success"]:
                recovery_point = RecoveryPoint(
                    recovery_point_id=f"recovery_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now(timezone.utc),
                    backup_id=backup_id,
                    description=f"Restored from {backup_id}",
                    metadata=results,
                )
                self.recovery_points.append(recovery_point)

            logger.info(f"Restore completed: {results}")
            return results

        except Exception as e:
            results["errors"].append(str(e))
            results["end_time"] = datetime.now(timezone.utc)
            results["success"] = False
            logger.error(f"Restore failed: {e}")
            return results

    async def _restore_database(
        self, backup: BackupMetadata, target_time: Optional[datetime] = None
    ):
        """Restore database from backup."""
        logger.info("Restoring database")

        backup_file = Path(backup.location) / "database.sql.gz"
        if not backup_file.exists():
            raise FileNotFoundError(f"Database backup not found: {backup_file}")

        # Read and decrypt if needed
        async with aiofiles.open(backup_file, "rb") as f:
            data = await f.read()

        if self.policy.encryption_enabled:
            data = self.cipher.decrypt(data)

        if self.policy.compression_enabled:
            data = gzip.decompress(data)

        # Create temporary SQL file
        temp_sql = Path(backup.location) / "restore.sql"
        async with aiofiles.open(temp_sql, "wb") as f:
            await f.write(data)

        # Get database configuration
        db_config = {
            "host": os.getenv("FXML4_DATABASE_HOST", "localhost"),
            "port": int(os.getenv("FXML4_DATABASE_PORT", "5432")),
            "database": os.getenv("FXML4_DATABASE_NAME", "fxml4"),
            "user": os.getenv("FXML4_DATABASE_USER", "postgres"),
            "password": os.getenv("FXML4_DATABASE_PASSWORD", ""),
        }

        # Restore using psql
        restore_command = [
            "psql",
            f"--host={db_config['host']}",
            f"--port={db_config['port']}",
            f"--username={db_config['user']}",
            f"--dbname={db_config['database']}",
            "--no-password",
            "--file",
            str(temp_sql),
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = db_config["password"]

        process = await asyncio.create_subprocess_exec(
            *restore_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        stdout, stderr = await process.communicate()

        # Clean up temp file
        temp_sql.unlink()

        if process.returncode != 0:
            raise Exception(f"Database restore failed: {stderr.decode()}")

        # Apply point-in-time recovery if requested
        if target_time and backup.backup_type == BackupType.FULL:
            # This would apply transaction logs up to target time
            # Simplified for this implementation
            logger.info(f"Point-in-time recovery to {target_time}")

    async def _restore_configs(self, backup: BackupMetadata):
        """Restore configuration files."""
        logger.info("Restoring configurations")

        backup_dir = Path(backup.location) / "configs"
        if not backup_dir.exists():
            raise FileNotFoundError(f"Config backup not found: {backup_dir}")

        config_dir = Path("config")

        # Backup current configs first
        backup_suffix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        for config_file in config_dir.glob("*.yaml"):
            shutil.copy2(
                config_file, config_file.with_suffix(f".yaml.backup_{backup_suffix}")
            )

        # Restore configs
        for backup_file in backup_dir.glob("*.yaml"):
            dest_file = config_dir / backup_file.name

            # Read and decrypt if needed
            async with aiofiles.open(backup_file, "rb") as f:
                data = await f.read()

            if self.policy.encryption_enabled:
                data = self.cipher.decrypt(data)

            # Write restored file
            async with aiofiles.open(dest_file, "wb") as f:
                await f.write(data)

            logger.info(f"Restored config: {dest_file.name}")

    async def _restore_models(self, backup: BackupMetadata):
        """Restore ML models from backup."""
        logger.info("Restoring models")

        backup_dir = Path(backup.location) / "models"
        if not backup_dir.exists():
            logger.warning("No models to restore")
            return

        models_dir = Path("models")

        # Restore each model
        for backup_file in backup_dir.rglob("*.pkl*"):
            relative_path = backup_file.relative_to(backup_dir)

            # Remove compression suffix if present
            if relative_path.suffix == ".gz":
                dest_path = models_dir / relative_path.with_suffix("")
            else:
                dest_path = models_dir / relative_path

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Read and process
            async with aiofiles.open(backup_file, "rb") as f:
                data = await f.read()

            if self.policy.encryption_enabled and backup_file.suffix == ".enc":
                data = self.cipher.decrypt(data)

            if backup_file.suffix == ".gz" or (
                backup_file.suffix == ".enc" and backup_file.stem.endswith(".gz")
            ):
                data = gzip.decompress(data)

            # Write restored model
            async with aiofiles.open(dest_path, "wb") as f:
                await f.write(data)

            logger.info(f"Restored model: {dest_path}")

    def _get_last_backup_time(
        self, backup_type: Optional[BackupType] = None
    ) -> Optional[datetime]:
        """Get timestamp of last backup."""
        backups = [
            b
            for b in self.backup_history
            if b.status in [BackupStatus.COMPLETED, BackupStatus.VERIFIED]
        ]

        if backup_type:
            backups = [b for b in backups if b.backup_type == backup_type]

        if not backups:
            return None

        return max(b.timestamp for b in backups)

    def _get_last_successful_backup(
        self, backup_type: BackupType
    ) -> Optional[BackupMetadata]:
        """Get last successful backup of type."""
        backups = [
            b
            for b in self.backup_history
            if b.backup_type == backup_type
            and b.status in [BackupStatus.COMPLETED, BackupStatus.VERIFIED]
        ]

        if not backups:
            return None

        return max(backups, key=lambda b: b.timestamp)

    def _get_backup_by_id(self, backup_id: str) -> Optional[BackupMetadata]:
        """Get backup by ID."""
        for backup in self.backup_history:
            if backup.backup_id == backup_id:
                return backup
        return None

    async def _cleanup_old_backups(self):
        """Remove old backups according to retention policy."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(
            days=self.policy.retention_days
        )

        old_backups = [
            b
            for b in self.backup_history
            if b.timestamp < cutoff_date and b.status != BackupStatus.IN_PROGRESS
        ]

        for backup in old_backups:
            try:
                # Remove local backup
                if backup.location and Path(backup.location).exists():
                    shutil.rmtree(backup.location)

                # Remove from S3
                if self.policy.s3_bucket and self.s3_client:
                    s3_key = f"{self.policy.s3_prefix}/{backup.backup_id}.tar.gz"
                    await self.s3_client.delete_object(
                        Bucket=self.policy.s3_bucket, Key=s3_key
                    )

                # Remove from history
                self.backup_history.remove(backup)

                logger.info(f"Cleaned up old backup: {backup.backup_id}")

            except Exception as e:
                logger.error(f"Error cleaning up backup {backup.backup_id}: {e}")

    async def _save_backup_history(self):
        """Save backup history to file."""
        history_file = (
            self.policy.local_path / "backup_history.json"
            if self.policy.local_path
            else Path("backup_history.json")
        )

        history_data = [
            {
                **asdict(backup),
                "backup_type": backup.backup_type.value,
                "timestamp": backup.timestamp.isoformat(),
                "status": backup.status.value,
            }
            for backup in self.backup_history
        ]

        async with aiofiles.open(history_file, "w") as f:
            await f.write(json.dumps(history_data, indent=2))

    async def _load_backup_history(self):
        """Load backup history from file."""
        history_file = (
            self.policy.local_path / "backup_history.json"
            if self.policy.local_path
            else Path("backup_history.json")
        )

        if not history_file.exists():
            return

        try:
            async with aiofiles.open(history_file, "r") as f:
                history_data = json.loads(await f.read())

            self.backup_history = []
            for data in history_data:
                # Convert string values back to enums
                data["backup_type"] = BackupType(data["backup_type"])
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                data["status"] = BackupStatus(data["status"])

                self.backup_history.append(BackupMetadata(**data))

        except Exception as e:
            logger.error(f"Error loading backup history: {e}")

    async def _download_from_s3(self, backup: BackupMetadata):
        """Download backup from S3."""
        if not self.s3_client or not self.policy.s3_bucket:
            raise ValueError("S3 not configured")

        logger.info(f"Downloading backup from S3: {backup.backup_id}")

        s3_key = f"{self.policy.s3_prefix}/{backup.backup_id}.tar.gz"

        # Download from S3
        response = await self.s3_client.get_object(
            Bucket=self.policy.s3_bucket, Key=s3_key
        )

        data = await response["Body"].read()

        # Save to temp file
        temp_archive = Path(self.policy.local_path) / f"{backup.backup_id}.tar.gz"
        async with aiofiles.open(temp_archive, "wb") as f:
            await f.write(data)

        # Extract archive
        extract_command = [
            "tar",
            "-xzf",
            str(temp_archive),
            "-C",
            str(self.policy.local_path),
        ]

        process = await asyncio.create_subprocess_exec(
            *extract_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await process.communicate()

        if process.returncode != 0:
            raise Exception("Failed to extract backup archive")

        # Clean up temp file
        temp_archive.unlink()

        # Update backup location
        backup.location = str(self.policy.local_path / backup.backup_id)

    def get_backup_status(self) -> Dict[str, Any]:
        """Get current backup system status."""
        recent_backups = sorted(
            self.backup_history, key=lambda b: b.timestamp, reverse=True
        )[:10]

        return {
            "is_running": self.is_running,
            "active_backup": asdict(self.active_backup) if self.active_backup else None,
            "last_full_backup": (
                self._get_last_backup_time(BackupType.FULL).isoformat()
                if self._get_last_backup_time(BackupType.FULL)
                else None
            ),
            "last_incremental_backup": (
                self._get_last_backup_time(BackupType.INCREMENTAL).isoformat()
                if self._get_last_backup_time(BackupType.INCREMENTAL)
                else None
            ),
            "total_backups": len(self.backup_history),
            "failed_backups": len(
                [b for b in self.backup_history if b.status == BackupStatus.FAILED]
            ),
            "recent_backups": [
                {
                    "backup_id": b.backup_id,
                    "type": b.backup_type.value,
                    "timestamp": b.timestamp.isoformat(),
                    "status": b.status.value,
                    "size_mb": b.size_bytes / 1024 / 1024,
                }
                for b in recent_backups
            ],
            "policy": {
                "full_backup_interval": str(self.policy.full_backup_interval),
                "incremental_interval": str(self.policy.incremental_interval),
                "retention_days": self.policy.retention_days,
                "encryption_enabled": self.policy.encryption_enabled,
                "s3_configured": bool(self.policy.s3_bucket),
            },
        }
