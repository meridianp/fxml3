"""Audit Logger for Comprehensive Trade and System Auditing.

This module provides structured audit logging capabilities for compliance
and regulatory requirements.
"""

import asyncio
import hashlib
import json
import logging
import logging.handlers
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class AuditSeverity(Enum):
    """Audit event severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    COMPLIANCE = "COMPLIANCE"


class AuditCategory(Enum):
    """Audit event categories."""

    SYSTEM = "SYSTEM"
    TRADING = "TRADING"
    RISK = "RISK"
    COMPLIANCE = "COMPLIANCE"
    SECURITY = "SECURITY"
    CONFIGURATION = "CONFIGURATION"
    USER_ACTION = "USER_ACTION"
    EXTERNAL_API = "EXTERNAL_API"


@dataclass
class AuditEvent:
    """Structured audit event."""

    # Core identification
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Event classification
    category: AuditCategory = AuditCategory.SYSTEM
    severity: AuditSeverity = AuditSeverity.INFO
    event_type: str = "UNKNOWN"

    # Content
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    # Context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    component: Optional[str] = None
    module: Optional[str] = None

    # Trade-specific fields
    cl_ord_id: Optional[str] = None
    broker_id: Optional[str] = None
    symbol: Optional[str] = None

    # Risk and compliance
    risk_level: Optional[str] = None
    compliance_flags: List[str] = field(default_factory=list)

    # Technical context
    system_state: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None

    # Hash for integrity verification
    _hash: Optional[str] = field(default=None, init=False)

    def __post_init__(self):
        """Calculate integrity hash after initialization."""
        self._calculate_hash()

    def _calculate_hash(self):
        """Calculate SHA-256 hash for integrity verification."""
        # Create a copy without the hash field for calculation
        data = asdict(self)
        data.pop("_hash", None)

        # Convert to JSON string for consistent hashing
        json_str = json.dumps(data, sort_keys=True, default=str)
        self._hash = hashlib.sha256(json_str.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify event integrity using stored hash."""
        current_hash = self._hash
        self._calculate_hash()
        is_valid = current_hash == self._hash
        self._hash = current_hash  # Restore original hash
        return is_valid

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str, indent=2)


class AuditLogger:
    """Comprehensive audit logging system."""

    def __init__(
        self,
        audit_dir: Union[str, Path] = "logs/audit",
        max_file_size: int = 50 * 1024 * 1024,  # 50MB
        backup_count: int = 10,
        enable_encryption: bool = False,
        compression: bool = True,
    ):
        """Initialize audit logger.

        Args:
            audit_dir: Directory for audit log files.
            max_file_size: Maximum size per log file in bytes.
            backup_count: Number of backup files to keep.
            enable_encryption: Whether to encrypt audit logs.
            compression: Whether to compress rotated logs.
        """
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.enable_encryption = enable_encryption
        self.compression = compression

        # Initialize logger for each category
        self._loggers = {}
        self._setup_loggers()

        # Event buffer for batch processing
        self._event_buffer: List[AuditEvent] = []
        self._buffer_lock = asyncio.Lock()
        self._buffer_flush_interval = 5.0  # seconds

        # Start background tasks
        self._flush_task = None
        self._start_background_tasks()

        logger.info("Audit logger initialized with directory: %s", self.audit_dir)

    def _setup_loggers(self):
        """Set up category-specific loggers."""
        for category in AuditCategory:
            category_logger = logging.getLogger(f"audit.{category.value.lower()}")
            category_logger.setLevel(logging.INFO)

            # Create file handler for this category
            log_file = self.audit_dir / f"{category.value.lower()}.log"
            handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=self.max_file_size, backupCount=self.backup_count
            )

            # Custom formatter for audit logs
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S UTC",
            )
            handler.setFormatter(formatter)

            category_logger.addHandler(handler)
            category_logger.propagate = False

            self._loggers[category] = category_logger

    def _start_background_tasks(self):
        """Start background tasks for log management."""
        try:
            loop = asyncio.get_event_loop()
            self._flush_task = loop.create_task(self._flush_buffer_periodically())
        except RuntimeError:
            # No event loop, will flush synchronously
            logger.warning(
                "No event loop available, audit buffer will flush synchronously"
            )

    async def _flush_buffer_periodically(self):
        """Periodically flush the event buffer."""
        while True:
            try:
                await asyncio.sleep(self._buffer_flush_interval)
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in audit buffer flush: {e}")

    async def _flush_buffer(self):
        """Flush buffered events to log files."""
        async with self._buffer_lock:
            if not self._event_buffer:
                return

            events_to_flush = self._event_buffer.copy()
            self._event_buffer.clear()

        # Write events to appropriate category logs
        for event in events_to_flush:
            self._write_event_to_log(event)

    def _write_event_to_log(self, event: AuditEvent):
        """Write audit event to appropriate log file."""
        category_logger = self._loggers.get(event.category)
        if not category_logger:
            logger.error(f"No logger found for category: {event.category}")
            return

        # Convert to structured log entry
        log_entry = {
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "severity": event.severity.value,
            "event_type": event.event_type,
            "message": event.message,
            "details": event.details,
            "user_id": event.user_id,
            "session_id": event.session_id,
            "component": event.component,
            "module": event.module,
            "cl_ord_id": event.cl_ord_id,
            "broker_id": event.broker_id,
            "symbol": event.symbol,
            "risk_level": event.risk_level,
            "compliance_flags": event.compliance_flags,
            "correlation_id": event.correlation_id,
            "hash": event._hash,
        }

        # Add system state if present
        if event.system_state:
            log_entry["system_state"] = event.system_state

        # Log as JSON
        json_log = json.dumps(log_entry, default=str, separators=(",", ":"))

        # Map severity to log level
        level_map = {
            AuditSeverity.INFO: logging.INFO,
            AuditSeverity.WARNING: logging.WARNING,
            AuditSeverity.ERROR: logging.ERROR,
            AuditSeverity.CRITICAL: logging.CRITICAL,
            AuditSeverity.COMPLIANCE: logging.CRITICAL,
        }

        log_level = level_map.get(event.severity, logging.INFO)
        category_logger.log(log_level, json_log)

    async def log_event(self, event: AuditEvent):
        """Log an audit event (async version)."""
        async with self._buffer_lock:
            self._event_buffer.append(event)

        # For critical events, flush immediately
        if event.severity in [AuditSeverity.CRITICAL, AuditSeverity.COMPLIANCE]:
            await self._flush_buffer()

    def log_event_sync(self, event: AuditEvent):
        """Log an audit event (synchronous version)."""
        self._write_event_to_log(event)

    # Convenience methods for different event types
    async def log_trade_event(
        self,
        event_type: str,
        message: str,
        cl_ord_id: str,
        symbol: str,
        broker_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[str] = None,
    ):
        """Log a trading-related audit event."""
        event = AuditEvent(
            category=AuditCategory.TRADING,
            severity=severity,
            event_type=event_type,
            message=message,
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            broker_id=broker_id,
            details=details or {},
            user_id=user_id,
        )
        await self.log_event(event)

    async def log_risk_event(
        self,
        event_type: str,
        message: str,
        risk_level: str,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.WARNING,
        cl_ord_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Log a risk management audit event."""
        event = AuditEvent(
            category=AuditCategory.RISK,
            severity=severity,
            event_type=event_type,
            message=message,
            risk_level=risk_level,
            details=details or {},
            cl_ord_id=cl_ord_id,
            user_id=user_id,
        )
        await self.log_event(event)

    async def log_compliance_event(
        self,
        event_type: str,
        message: str,
        compliance_flags: List[str],
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.COMPLIANCE,
        user_id: Optional[str] = None,
    ):
        """Log a compliance-related audit event."""
        event = AuditEvent(
            category=AuditCategory.COMPLIANCE,
            severity=severity,
            event_type=event_type,
            message=message,
            compliance_flags=compliance_flags,
            details=details or {},
            user_id=user_id,
        )
        await self.log_event(event)

    async def log_security_event(
        self,
        event_type: str,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ):
        """Log a security-related audit event."""
        event = AuditEvent(
            category=AuditCategory.SECURITY,
            severity=severity,
            event_type=event_type,
            message=message,
            user_id=user_id,
            session_id=session_id,
            details=details or {},
        )
        await self.log_event(event)

    async def log_user_action(
        self,
        action: str,
        user_id: str,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ):
        """Log a user action audit event."""
        event = AuditEvent(
            category=AuditCategory.USER_ACTION,
            severity=severity,
            event_type="USER_ACTION",
            message=f"User action: {action}",
            user_id=user_id,
            session_id=session_id,
            details=details or {},
        )
        await self.log_event(event)

    async def log_system_event(
        self,
        event_type: str,
        message: str,
        component: str,
        module: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ):
        """Log a system-related audit event."""
        event = AuditEvent(
            category=AuditCategory.SYSTEM,
            severity=severity,
            event_type=event_type,
            message=message,
            component=component,
            module=module,
            details=details or {},
        )
        await self.log_event(event)

    def get_audit_stats(self) -> Dict[str, Any]:
        """Get audit logging statistics."""
        stats = {
            "audit_dir": str(self.audit_dir),
            "categories": len(self._loggers),
            "buffer_size": len(self._event_buffer),
            "flush_interval": self._buffer_flush_interval,
            "max_file_size": self.max_file_size,
            "backup_count": self.backup_count,
        }

        # Add file sizes for each category
        stats["category_files"] = {}
        for category in AuditCategory:
            log_file = self.audit_dir / f"{category.value.lower()}.log"
            if log_file.exists():
                stats["category_files"][category.value] = log_file.stat().st_size

        return stats

    async def shutdown(self):
        """Gracefully shutdown audit logger."""
        logger.info("Shutting down audit logger...")

        # Cancel background tasks
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Flush any remaining events
        await self._flush_buffer()

        # Close all handlers
        for category_logger in self._loggers.values():
            for handler in category_logger.handlers:
                handler.close()

        logger.info("Audit logger shutdown complete")


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def init_audit_logger(
    audit_dir: Union[str, Path] = "logs/audit",
    max_file_size: int = 50 * 1024 * 1024,
    backup_count: int = 10,
) -> AuditLogger:
    """Initialize the global audit logger."""
    global _audit_logger
    _audit_logger = AuditLogger(
        audit_dir=audit_dir, max_file_size=max_file_size, backup_count=backup_count
    )
    return _audit_logger
