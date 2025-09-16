"""
Comprehensive test suite for FXML4 Database Operations System.

This test suite follows strict Test-Driven Development (TDD) methodology for
Phase 10: Production Deployment & Operations - Database Operations.

Tests cover:
- Database schema migrations and versioning
- Automated backup procedures and scheduling
- Data recovery and point-in-time recovery
- Zero-downtime migration strategies
- Backup validation and integrity checking
- Disaster recovery procedures
- Database connection management
- TimescaleDB-specific operations (hypertables, compression, retention)
- Migration rollback capabilities
- Production safety checks and validation
"""

import asyncio
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest


# Test fixtures for database operations system components
@pytest.fixture
def database_manager():
    """Create DatabaseManager instance for testing."""
    from fxml4.deployment.database_manager import DatabaseManager

    return DatabaseManager()


@pytest.fixture
def migration_manager():
    """Create MigrationManager instance for testing."""
    from fxml4.deployment.migration_manager import MigrationManager

    return MigrationManager()


@pytest.fixture
def backup_manager():
    """Create BackupManager instance for testing."""
    from fxml4.deployment.backup_manager import BackupManager

    return BackupManager()


@pytest.fixture
def recovery_manager():
    """Create RecoveryManager instance for testing."""
    from fxml4.deployment.recovery_manager import RecoveryManager

    return RecoveryManager()


@pytest.fixture
def temp_backup_dir():
    """Create temporary directory for backup testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestDatabaseMigrations:
    """Test database migration functionality."""

    @pytest.mark.asyncio
    async def test_migration_version_tracking(self, migration_manager):
        """Test migration version tracking and management."""
        await migration_manager.initialize()

        # Test initial version state
        current_version = await migration_manager.get_current_version()
        assert current_version >= 0
        assert isinstance(current_version, int)

        # Test version history
        version_history = await migration_manager.get_migration_history()
        assert isinstance(version_history, list)

        for entry in version_history:
            assert "version" in entry
            assert "applied_at" in entry
            assert "migration_name" in entry
            assert "success" in entry

    @pytest.mark.asyncio
    async def test_migration_file_discovery(self, migration_manager):
        """Test discovery and validation of migration files."""
        await migration_manager.initialize()

        # Test migration discovery
        available_migrations = await migration_manager.discover_migrations()
        assert isinstance(available_migrations, list)

        for migration in available_migrations:
            assert "version" in migration
            assert "name" in migration
            assert "file_path" in migration
            assert "up_sql" in migration or "down_sql" in migration

    @pytest.mark.asyncio
    async def test_migration_validation(self, migration_manager):
        """Test migration validation and safety checks."""
        await migration_manager.initialize()

        # Test migration syntax validation
        test_migration = {
            "version": 1001,
            "name": "test_migration",
            "up_sql": "CREATE TABLE test_table (id SERIAL PRIMARY KEY, name VARCHAR(100));",
            "down_sql": "DROP TABLE IF EXISTS test_table;",
        }

        validation_result = await migration_manager.validate_migration(test_migration)
        assert validation_result["valid"] == True
        assert validation_result["syntax_valid"] == True
        assert "validation_errors" in validation_result
        assert len(validation_result["validation_errors"]) == 0

    @pytest.mark.asyncio
    async def test_dry_run_migration(self, migration_manager):
        """Test dry-run migration execution."""
        await migration_manager.initialize()

        test_migration = {
            "version": 1002,
            "name": "test_dry_run_migration",
            "up_sql": "ALTER TABLE market_data ADD COLUMN test_column INTEGER;",
            "down_sql": "ALTER TABLE market_data DROP COLUMN IF EXISTS test_column;",
        }

        dry_run_result = await migration_manager.execute_dry_run(test_migration)
        assert dry_run_result["dry_run_successful"] == True
        assert "execution_plan" in dry_run_result
        assert "estimated_duration" in dry_run_result
        assert "safety_checks" in dry_run_result
        assert dry_run_result["safety_checks"]["destructive_operations"] == False

    @pytest.mark.asyncio
    async def test_migration_execution(self, migration_manager):
        """Test actual migration execution with rollback capability."""
        await migration_manager.initialize()

        migration_config = {
            "version": 1003,
            "name": "test_execution_migration",
            "up_sql": "CREATE TABLE migration_test (id SERIAL PRIMARY KEY, created_at TIMESTAMP DEFAULT NOW());",
            "down_sql": "DROP TABLE IF EXISTS migration_test;",
            "timeout_seconds": 30,
            "backup_before_migration": True,
        }

        execution_result = await migration_manager.execute_migration(migration_config)
        assert execution_result["migration_successful"] == True
        assert execution_result["version"] == migration_config["version"]
        assert execution_result["backup_created"] == True
        assert "execution_time_seconds" in execution_result
        assert (
            execution_result["execution_time_seconds"]
            < migration_config["timeout_seconds"]
        )

    @pytest.mark.asyncio
    async def test_zero_downtime_migration(self, migration_manager):
        """Test zero-downtime migration strategies."""
        await migration_manager.initialize()

        zero_downtime_config = {
            "strategy": "online_schema_change",
            "migration": {
                "version": 1004,
                "name": "zero_downtime_test",
                "up_sql": "ALTER TABLE trades ADD COLUMN trade_notes TEXT;",
                "down_sql": "ALTER TABLE trades DROP COLUMN IF EXISTS trade_notes;",
            },
            "batch_size": 1000,
            "throttle_ms": 100,
        }

        zero_downtime_result = await migration_manager.execute_zero_downtime_migration(
            zero_downtime_config
        )
        assert zero_downtime_result["migration_successful"] == True
        assert (
            zero_downtime_result["downtime_seconds"] < 1.0
        )  # Less than 1 second downtime
        assert zero_downtime_result["strategy"] == "online_schema_change"

    @pytest.mark.asyncio
    async def test_migration_rollback(self, migration_manager):
        """Test migration rollback functionality."""
        await migration_manager.initialize()

        # First apply a migration
        rollback_migration = {
            "version": 1005,
            "name": "test_rollback_migration",
            "up_sql": "CREATE TABLE rollback_test (id SERIAL PRIMARY KEY);",
            "down_sql": "DROP TABLE IF EXISTS rollback_test;",
        }

        # Execute migration
        await migration_manager.execute_migration(rollback_migration)

        # Test rollback
        rollback_result = await migration_manager.rollback_migration(
            rollback_migration["version"]
        )
        assert rollback_result["rollback_successful"] == True
        assert rollback_result["version_rolled_back"] == rollback_migration["version"]
        assert "rollback_duration_seconds" in rollback_result


class TestDatabaseBackup:
    """Test database backup functionality."""

    @pytest.mark.asyncio
    async def test_full_database_backup(self, backup_manager, temp_backup_dir):
        """Test full database backup creation."""
        await backup_manager.initialize()

        backup_config = {
            "backup_type": "full",
            "backup_location": str(temp_backup_dir),
            "compression": True,
            "include_schema": True,
            "include_data": True,
            "parallel_jobs": 2,
        }

        backup_result = await backup_manager.create_backup(backup_config)
        assert backup_result["backup_successful"] == True
        assert backup_result["backup_type"] == "full"
        assert backup_result["compressed"] == True
        assert "backup_file_path" in backup_result
        assert "backup_size_mb" in backup_result
        assert "backup_duration_seconds" in backup_result

        # Verify backup file exists
        backup_file = Path(backup_result["backup_file_path"])
        assert backup_file.exists()
        assert backup_file.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_incremental_backup(self, backup_manager, temp_backup_dir):
        """Test incremental backup functionality."""
        await backup_manager.initialize()

        # First create a full backup
        full_backup_config = {
            "backup_type": "full",
            "backup_location": str(temp_backup_dir),
        }
        await backup_manager.create_backup(full_backup_config)

        # Then create incremental backup
        incremental_config = {
            "backup_type": "incremental",
            "backup_location": str(temp_backup_dir),
            "base_backup_timestamp": datetime.utcnow() - timedelta(hours=1),
        }

        incremental_result = await backup_manager.create_backup(incremental_config)
        assert incremental_result["backup_successful"] == True
        assert incremental_result["backup_type"] == "incremental"
        assert "base_backup_path" in incremental_result
        assert (
            incremental_result["backup_size_mb"] < 100
        )  # Incremental should be smaller

    @pytest.mark.asyncio
    async def test_backup_validation(self, backup_manager, temp_backup_dir):
        """Test backup validation and integrity checking."""
        await backup_manager.initialize()

        # Create a backup
        backup_config = {
            "backup_type": "full",
            "backup_location": str(temp_backup_dir),
            "include_checksum": True,
        }
        backup_result = await backup_manager.create_backup(backup_config)

        # Validate the backup
        validation_config = {
            "backup_file_path": backup_result["backup_file_path"],
            "verify_checksum": True,
            "test_restore": True,
        }

        validation_result = await backup_manager.validate_backup(validation_config)
        assert validation_result["validation_successful"] == True
        assert validation_result["checksum_valid"] == True
        assert validation_result["file_integrity_valid"] == True
        assert validation_result["test_restore_successful"] == True

    @pytest.mark.asyncio
    async def test_automated_backup_scheduling(self, backup_manager):
        """Test automated backup scheduling system."""
        await backup_manager.initialize()

        schedule_config = {
            "full_backup_schedule": "0 2 * * 0",  # Weekly on Sunday at 2 AM
            "incremental_backup_schedule": "0 2 * * 1-6",  # Daily at 2 AM (Mon-Sat)
            "retention_days": 30,
            "backup_location": "/var/backups/fxml4",
            "notification_channels": ["email", "slack"],
        }

        scheduling_result = await backup_manager.configure_automated_backups(
            schedule_config
        )
        assert scheduling_result["scheduling_configured"] == True
        assert (
            scheduling_result["full_backup_schedule"]
            == schedule_config["full_backup_schedule"]
        )
        assert (
            scheduling_result["incremental_backup_schedule"]
            == schedule_config["incremental_backup_schedule"]
        )
        assert scheduling_result["retention_policy_configured"] == True

    @pytest.mark.asyncio
    async def test_backup_retention_management(self, backup_manager, temp_backup_dir):
        """Test backup retention and cleanup policies."""
        await backup_manager.initialize()

        # Create multiple old backups (simulated)
        old_backups = []
        for i in range(10):
            backup_metadata = {
                "backup_file": f"backup_{i}.sql.gz",
                "created_at": datetime.utcnow() - timedelta(days=35 + i),
                "backup_type": "full",
                "size_mb": 500,
            }
            old_backups.append(backup_metadata)

        retention_config = {
            "retention_days": 30,
            "min_backups_to_keep": 3,
            "backup_location": str(temp_backup_dir),
        }

        cleanup_result = await backup_manager.cleanup_old_backups(retention_config)
        assert cleanup_result["cleanup_successful"] == True
        assert cleanup_result["backups_deleted"] > 0
        assert (
            cleanup_result["backups_retained"]
            >= retention_config["min_backups_to_keep"]
        )
        assert "space_freed_mb" in cleanup_result


class TestDatabaseRecovery:
    """Test database recovery functionality."""

    @pytest.mark.asyncio
    async def test_full_database_restore(
        self, recovery_manager, backup_manager, temp_backup_dir
    ):
        """Test full database restoration from backup."""
        await recovery_manager.initialize()
        await backup_manager.initialize()

        # First create a backup
        backup_config = {"backup_type": "full", "backup_location": str(temp_backup_dir)}
        backup_result = await backup_manager.create_backup(backup_config)

        # Test restoration
        restore_config = {
            "backup_file_path": backup_result["backup_file_path"],
            "restore_type": "full",
            "target_database": "fxml4_test_restore",
            "pre_restore_validation": True,
        }

        restore_result = await recovery_manager.restore_database(restore_config)
        assert restore_result["restore_successful"] == True
        assert restore_result["restore_type"] == "full"
        assert "restore_duration_seconds" in restore_result
        assert restore_result["validation_passed"] == True

    @pytest.mark.asyncio
    async def test_point_in_time_recovery(self, recovery_manager):
        """Test point-in-time recovery functionality."""
        await recovery_manager.initialize()

        recovery_config = {
            "recovery_type": "point_in_time",
            "target_time": datetime.utcnow() - timedelta(hours=2),
            "base_backup_path": "/path/to/base/backup.sql",
            "wal_archives_path": "/var/lib/postgresql/archives",
            "target_database": "fxml4_pitr_test",
        }

        pitr_result = await recovery_manager.execute_point_in_time_recovery(
            recovery_config
        )
        assert pitr_result["recovery_successful"] == True
        assert pitr_result["recovery_type"] == "point_in_time"
        assert "target_time_achieved" in pitr_result
        assert "wal_files_processed" in pitr_result

    @pytest.mark.asyncio
    async def test_selective_table_recovery(self, recovery_manager):
        """Test selective table recovery functionality."""
        await recovery_manager.initialize()

        selective_config = {
            "recovery_type": "selective",
            "backup_file_path": "/path/to/backup.sql",
            "tables_to_recover": ["trades", "positions", "market_data"],
            "target_database": "fxml4_selective_test",
            "conflict_resolution": "overwrite",
        }

        selective_result = await recovery_manager.execute_selective_recovery(
            selective_config
        )
        assert selective_result["recovery_successful"] == True
        assert selective_result["recovery_type"] == "selective"
        assert selective_result["tables_recovered"] == len(
            selective_config["tables_to_recover"]
        )
        assert "data_conflicts_resolved" in selective_result

    @pytest.mark.asyncio
    async def test_disaster_recovery_procedure(self, recovery_manager):
        """Test complete disaster recovery procedure."""
        await recovery_manager.initialize()

        disaster_scenario = {
            "scenario_type": "complete_data_loss",
            "recovery_priority": "critical",
            "rto_minutes": 240,  # Recovery Time Objective: 4 hours
            "rpo_minutes": 15,  # Recovery Point Objective: 15 minutes
        }

        disaster_config = {
            "primary_backup_location": "/backups/primary",
            "secondary_backup_location": "/backups/offsite",
            "target_environment": "disaster_recovery",
            "notification_channels": ["email", "sms", "pagerduty"],
        }

        disaster_result = await recovery_manager.execute_disaster_recovery(
            disaster_scenario, disaster_config
        )
        assert disaster_result["recovery_successful"] == True
        assert disaster_result["rto_met"] == True
        assert disaster_result["rpo_met"] == True
        assert (
            disaster_result["recovery_time_minutes"] <= disaster_scenario["rto_minutes"]
        )
        assert "services_restored" in disaster_result

    @pytest.mark.asyncio
    async def test_recovery_validation(self, recovery_manager):
        """Test recovery validation and integrity checking."""
        await recovery_manager.initialize()

        validation_config = {
            "restored_database": "fxml4_restored",
            "reference_database": "fxml4_production",
            "validation_checks": [
                "schema_comparison",
                "data_integrity",
                "constraint_validation",
                "index_validation",
                "function_validation",
            ],
        }

        validation_result = await recovery_manager.validate_recovery(validation_config)
        assert validation_result["validation_successful"] == True
        assert validation_result["schema_match"] == True
        assert validation_result["data_integrity_valid"] == True
        assert validation_result["constraints_valid"] == True
        assert len(validation_result["validation_errors"]) == 0


class TestTimescaleDBOperations:
    """Test TimescaleDB-specific operations."""

    @pytest.mark.asyncio
    async def test_hypertable_management(self, database_manager):
        """Test hypertable creation and management."""
        await database_manager.initialize()

        hypertable_config = {
            "table_name": "test_timeseries",
            "time_column": "timestamp",
            "partitioning_interval": "1 day",
            "chunk_time_interval": "1 hour",
            "compression_enabled": True,
        }

        hypertable_result = await database_manager.create_hypertable(hypertable_config)
        assert hypertable_result["hypertable_created"] == True
        assert hypertable_result["table_name"] == hypertable_config["table_name"]
        assert hypertable_result["partitioning_configured"] == True
        assert hypertable_result["compression_enabled"] == True

    @pytest.mark.asyncio
    async def test_compression_policy_management(self, database_manager):
        """Test compression policy configuration."""
        await database_manager.initialize()

        compression_config = {
            "hypertable_name": "market_data",
            "compress_after": "7 days",
            "compression_algorithm": "timescaledb",
            "segment_by": "symbol",
            "order_by": "timestamp DESC",
        }

        compression_result = await database_manager.configure_compression_policy(
            compression_config
        )
        assert compression_result["policy_configured"] == True
        assert compression_result["compression_enabled"] == True
        assert (
            compression_result["compress_after"] == compression_config["compress_after"]
        )

    @pytest.mark.asyncio
    async def test_retention_policy_management(self, database_manager):
        """Test data retention policy configuration."""
        await database_manager.initialize()

        retention_config = {
            "hypertable_name": "audit_logs",
            "retention_period": "2 years",
            "drop_chunks_policy": True,
            "schedule_interval": "1 week",
        }

        retention_result = await database_manager.configure_retention_policy(
            retention_config
        )
        assert retention_result["policy_configured"] == True
        assert (
            retention_result["retention_period"] == retention_config["retention_period"]
        )
        assert retention_result["automated_cleanup"] == True

    @pytest.mark.asyncio
    async def test_continuous_aggregates(self, database_manager):
        """Test continuous aggregates creation and management."""
        await database_manager.initialize()

        cagg_config = {
            "view_name": "hourly_trade_summary",
            "source_table": "trades",
            "time_bucket_size": "1 hour",
            "refresh_policy": "real_time",
            "aggregation_query": """
                SELECT
                    time_bucket('1 hour', executed_at) as hour,
                    symbol,
                    COUNT(*) as trade_count,
                    AVG(price) as avg_price,
                    SUM(quantity) as total_volume
                FROM trades
                GROUP BY hour, symbol
            """,
        }

        cagg_result = await database_manager.create_continuous_aggregate(cagg_config)
        assert cagg_result["cagg_created"] == True
        assert cagg_result["view_name"] == cagg_config["view_name"]
        assert cagg_result["refresh_policy_configured"] == True


class TestDatabaseSafety:
    """Test database safety and validation procedures."""

    @pytest.mark.asyncio
    async def test_pre_migration_safety_checks(self, migration_manager):
        """Test comprehensive pre-migration safety validation."""
        await migration_manager.initialize()

        safety_config = {
            "migration_version": 1006,
            "check_disk_space": True,
            "check_connections": True,
            "check_locks": True,
            "check_replication": True,
            "required_free_space_mb": 1000,
        }

        safety_result = await migration_manager.execute_safety_checks(safety_config)
        assert safety_result["safety_checks_passed"] == True
        assert safety_result["sufficient_disk_space"] == True
        assert safety_result["connection_count_acceptable"] == True
        assert safety_result["no_blocking_locks"] == True
        assert len(safety_result["safety_warnings"]) == 0

    @pytest.mark.asyncio
    async def test_backup_before_migration(self, migration_manager, backup_manager):
        """Test automatic backup creation before migrations."""
        await migration_manager.initialize()
        await backup_manager.initialize()

        migration_with_backup = {
            "version": 1007,
            "name": "test_backup_before_migration",
            "up_sql": "ALTER TABLE positions ADD COLUMN risk_level VARCHAR(20);",
            "down_sql": "ALTER TABLE positions DROP COLUMN IF EXISTS risk_level;",
            "backup_before_migration": True,
            "backup_retention_days": 7,
        }

        migration_result = await migration_manager.execute_migration(
            migration_with_backup
        )
        assert migration_result["migration_successful"] == True
        assert migration_result["backup_created"] == True
        assert "backup_file_path" in migration_result
        assert migration_result["backup_verified"] == True

    @pytest.mark.asyncio
    async def test_connection_management(self, database_manager):
        """Test database connection management and pooling."""
        await database_manager.initialize()

        connection_config = {
            "max_connections": 100,
            "connection_timeout": 30,
            "idle_timeout": 300,
            "health_check_interval": 60,
        }

        connection_result = await database_manager.configure_connection_pool(
            connection_config
        )
        assert connection_result["pool_configured"] == True
        assert (
            connection_result["max_connections"] == connection_config["max_connections"]
        )
        assert connection_result["health_checks_enabled"] == True

    @pytest.mark.asyncio
    async def test_database_health_monitoring(self, database_manager):
        """Test database health monitoring and alerting."""
        await database_manager.initialize()

        health_result = await database_manager.check_database_health()
        assert health_result["database_healthy"] == True
        assert "connection_count" in health_result
        assert "active_queries" in health_result
        assert "disk_usage_percent" in health_result
        assert "replication_lag_seconds" in health_result
        assert health_result["disk_usage_percent"] < 90  # Should be under 90%


# Integration tests for complete database operations workflow
class TestDatabaseOperationsIntegration:
    """Test complete database operations workflow integration."""

    @pytest.mark.asyncio
    async def test_complete_migration_workflow(
        self, database_manager, migration_manager, backup_manager
    ):
        """Test complete migration workflow with backup and validation."""
        await database_manager.initialize()
        await migration_manager.initialize()
        await backup_manager.initialize()

        workflow_config = {
            "migration": {
                "version": 1008,
                "name": "complete_workflow_test",
                "up_sql": "CREATE INDEX CONCURRENTLY idx_trades_symbol_date ON trades(symbol, DATE(executed_at));",
                "down_sql": "DROP INDEX IF EXISTS idx_trades_symbol_date;",
            },
            "backup_before": True,
            "dry_run_first": True,
            "safety_checks": True,
            "rollback_on_failure": True,
        }

        workflow_result = await database_manager.execute_migration_workflow(
            workflow_config
        )
        assert workflow_result["workflow_successful"] == True
        assert workflow_result["dry_run_successful"] == True
        assert workflow_result["safety_checks_passed"] == True
        assert workflow_result["backup_created"] == True
        assert workflow_result["migration_successful"] == True

    @pytest.mark.asyncio
    async def test_disaster_recovery_workflow(
        self, recovery_manager, backup_manager, database_manager
    ):
        """Test complete disaster recovery workflow."""
        await recovery_manager.initialize()
        await backup_manager.initialize()
        await database_manager.initialize()

        disaster_workflow = {
            "scenario": "primary_database_failure",
            "recovery_steps": [
                "assess_damage",
                "locate_latest_backup",
                "validate_backup_integrity",
                "restore_to_temporary_location",
                "validate_restored_data",
                "switch_application_traffic",
                "verify_system_functionality",
            ],
        }

        disaster_result = await recovery_manager.execute_disaster_recovery_workflow(
            disaster_workflow
        )
        assert disaster_result["workflow_successful"] == True
        assert disaster_result["steps_completed"] == len(
            disaster_workflow["recovery_steps"]
        )
        assert disaster_result["data_loss_minimal"] == True
        assert disaster_result["system_operational"] == True

    @pytest.mark.asyncio
    async def test_backup_restore_validation_cycle(
        self, backup_manager, recovery_manager
    ):
        """Test complete backup-restore-validation cycle."""
        await backup_manager.initialize()
        await recovery_manager.initialize()

        cycle_config = {
            "backup_type": "full",
            "backup_compression": True,
            "restore_validation": True,
            "data_integrity_check": True,
            "performance_test": True,
        }

        cycle_result = await backup_manager.execute_backup_restore_cycle(cycle_config)
        assert cycle_result["cycle_successful"] == True
        assert cycle_result["backup_created"] == True
        assert cycle_result["restore_successful"] == True
        assert cycle_result["validation_passed"] == True
        assert cycle_result["performance_acceptable"] == True


# Performance and stress tests for database operations
@pytest.mark.performance
class TestDatabaseOperationsPerformance:
    """Test database operations performance under load."""

    @pytest.mark.asyncio
    async def test_large_migration_performance(self, migration_manager):
        """Test performance of large migrations."""
        await migration_manager.initialize()

        large_migration = {
            "version": 2001,
            "name": "large_data_migration",
            "up_sql": "ALTER TABLE market_data ADD COLUMN processed_indicator BOOLEAN DEFAULT FALSE;",
            "estimated_rows_affected": 10000000,
            "batch_size": 10000,
            "performance_monitoring": True,
        }

        performance_result = await migration_manager.execute_migration(large_migration)
        assert performance_result["migration_successful"] == True
        assert (
            performance_result["execution_time_seconds"] < 3600
        )  # Should complete within 1 hour
        assert "rows_processed_per_second" in performance_result
        assert (
            performance_result["rows_processed_per_second"] > 1000
        )  # At least 1000 rows/second

    @pytest.mark.asyncio
    async def test_backup_performance_large_database(
        self, backup_manager, temp_backup_dir
    ):
        """Test backup performance with large database."""
        await backup_manager.initialize()

        large_backup_config = {
            "backup_type": "full",
            "backup_location": str(temp_backup_dir),
            "compression": True,
            "parallel_jobs": 4,
            "estimated_size_gb": 50,
            "performance_monitoring": True,
        }

        performance_result = await backup_manager.create_backup(large_backup_config)
        assert performance_result["backup_successful"] == True
        assert (
            performance_result["backup_duration_seconds"] < 1800
        )  # Should complete within 30 minutes
        assert "backup_speed_mbps" in performance_result
        assert performance_result["backup_speed_mbps"] > 10  # At least 10 MB/s

    @pytest.mark.asyncio
    async def test_concurrent_operations_performance(self, database_manager):
        """Test performance under concurrent database operations."""
        await database_manager.initialize()

        concurrent_config = {
            "concurrent_connections": 50,
            "operations_per_connection": 100,
            "operation_types": ["select", "insert", "update"],
            "duration_seconds": 60,
        }

        concurrent_result = await database_manager.test_concurrent_performance(
            concurrent_config
        )
        assert concurrent_result["test_successful"] == True
        assert concurrent_result["average_response_time_ms"] < 100
        assert concurrent_result["operations_per_second"] > 1000
        assert concurrent_result["error_rate_percent"] < 1.0
