"""
FXML4 Disaster Recovery System
Comprehensive disaster recovery capabilities for external database failures.

Phase 12 Requirements:
- Full system recovery from external database failure within 4 hours
- Automated backup and restore procedures
- System health validation post-recovery
- Critical data integrity verification
- Trading system functionality validation

Key Components:
- DisasterRecoveryManager: Main orchestration engine
- DatabaseFailureSimulator: Test failure scenarios
- SystemHealthValidator: Post-recovery validation
- RecoveryMetrics: Performance and SLA tracking
"""

from .recovery_manager import (
    DatabaseFailureSimulator,
    DisasterRecoveryManager,
    RecoveryMetrics,
    RecoveryResult,
    RecoveryStatus,
    RecoveryType,
    SystemHealthValidator,
)

__all__ = [
    "DisasterRecoveryManager",
    "RecoveryStatus",
    "RecoveryResult",
    "RecoveryType",
    "RecoveryMetrics",
    "DatabaseFailureSimulator",
    "SystemHealthValidator",
]
