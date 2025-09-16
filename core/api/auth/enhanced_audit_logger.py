"""
Enhanced audit logging system for FXML4 trading platform.

This module provides comprehensive audit logging functionality including:
- Trading activity logging with 7-year retention requirements
- Structured logging with correlation IDs and trading context
- Performance optimization for high-frequency trading environments
- Integration with JWT authentication and rate limiting systems
- Regulatory compliance logging (MiFID II, EMIR, Dodd-Frank)
- Audit trail integrity with cryptographic hashing
- Log aggregation, search, and retention management
"""

import asyncio
import hashlib
import json
import logging
import secrets
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.config import get_config

# Configure logging
logger = logging.getLogger(__name__)
config = get_config()


class LogLevel(Enum):
    """Audit log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditEventType(Enum):
    """Audit event types for trading activities."""

    # Authentication Events
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    USER_REGISTRATION = "USER_REGISTRATION"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    TOKEN_CREATED = "TOKEN_CREATED"
    TOKEN_REFRESHED = "TOKEN_REFRESHED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    TOTP_SETUP = "TOTP_SETUP"
    TOTP_VERIFIED = "TOTP_VERIFIED"

    # Security Events
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"

    # Trading Events
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_MODIFIED = "ORDER_MODIFIED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_VALIDATED = "ORDER_VALIDATED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    TRADE_EXECUTED = "TRADE_EXECUTED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"

    # Risk Management Events
    RISK_CHECK_PASSED = "RISK_CHECK_PASSED"
    RISK_CHECK_FAILED = "RISK_CHECK_FAILED"
    POSITION_LIMIT_EXCEEDED = "POSITION_LIMIT_EXCEEDED"
    DRAWDOWN_LIMIT_EXCEEDED = "DRAWDOWN_LIMIT_EXCEEDED"

    # System Events
    SYSTEM_STARTUP = "SYSTEM_STARTUP"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    SYSTEM_WARNING = "SYSTEM_WARNING"

    # Compliance Events
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    TRADE_REPORTED = "TRADE_REPORTED"
    DERIVATIVE_TRADE = "DERIVATIVE_TRADE"
    SWAP_REPORTING = "SWAP_REPORTING"
    REGULATORY_ALERT = "REGULATORY_ALERT"

    # Data Events
    DATA_ACCESS = "DATA_ACCESS"
    DATA_EXPORT = "DATA_EXPORT"
    DATA_MODIFICATION = "DATA_MODIFICATION"
    DATA_DELETION = "DATA_DELETION"


@dataclass
class AuditLogConfig:
    """Configuration for enhanced audit logging."""

    # Retention settings (7-year minimum for financial services)
    retention_years: int = 7
    retention_days: int = 7 * 365

    # Performance settings
    batch_size: int = 100
    batch_timeout_seconds: int = 5
    max_queue_size: int = 10000

    # Compliance settings
    enable_integrity_checks: bool = True
    enable_encryption: bool = True
    correlation_id_required: bool = True

    # Log level filtering
    enabled_levels: List[LogLevel] = None

    # Database settings
    table_name: str = "audit_logs"
    index_columns: List[str] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.retention_years < 7:
            raise ValueError(
                "retention_years must be at least 7 for regulatory compliance"
            )

        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")

        if self.batch_timeout_seconds <= 0:
            raise ValueError("batch_timeout_seconds must be positive")

        # Set defaults
        if self.enabled_levels is None:
            self.enabled_levels = [
                LogLevel.INFO,
                LogLevel.WARNING,
                LogLevel.ERROR,
                LogLevel.CRITICAL,
            ]

        if self.index_columns is None:
            self.index_columns = [
                "timestamp",
                "user_id",
                "correlation_id",
                "event_type",
                "symbol",
            ]

        # Update retention_days based on retention_years
        self.retention_days = self.retention_years * 365


@dataclass
class TradingContext:
    """Trading context for audit log entries."""

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    symbol: Optional[str] = None
    order_id: Optional[str] = None
    trade_id: Optional[str] = None
    strategy_id: Optional[str] = None
    account_id: Optional[str] = None
    broker: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_request(cls, request, user=None):
        """Create trading context from FastAPI request."""
        context = cls()

        if user:
            context.user_id = str(user.id)

        if hasattr(request, "headers"):
            context.correlation_id = request.headers.get("X-Correlation-ID")
            context.session_id = request.headers.get("X-Session-ID")
            context.user_agent = request.headers.get("User-Agent")

        if hasattr(request, "client") and request.client:
            context.client_ip = request.client.host

        return context


@dataclass
class AuditLogEntry:
    """Audit log entry structure."""

    timestamp: datetime
    event_type: AuditEventType
    level: LogLevel
    message: str
    trading_context: TradingContext
    event_data: Optional[Dict[str, Any]] = None
    integrity_hash: Optional[str] = None

    def to_json(self) -> str:
        """Convert to JSON string."""
        data = {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "level": self.level.value,
            "message": self.message,
            "trading_context": self.trading_context.to_dict(),
            "event_data": self.event_data or {},
            "integrity_hash": self.integrity_hash,
        }
        return json.dumps(data, default=str)

    def calculate_integrity_hash(self) -> str:
        """Calculate SHA-256 integrity hash for the log entry."""
        # Create hash input from key fields
        hash_input = (
            f"{self.timestamp.isoformat()}"
            f"{self.event_type.value}"
            f"{self.level.value}"
            f"{self.message}"
            f"{json.dumps(self.trading_context.to_dict(), sort_keys=True)}"
            f"{json.dumps(self.event_data or {}, sort_keys=True, default=str)}"
        )

        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


@dataclass
class RetentionPolicy:
    """Audit log retention policy."""

    retention_days: int
    cleanup_interval_days: int = 1
    archive_before_delete: bool = True
    archive_format: str = "json"
    archive_compression: bool = True


class EnhancedAuditLogger:
    """Enhanced audit logger with high-performance async processing."""

    def __init__(
        self, config: Optional[AuditLogConfig] = None, test_mode: bool = False
    ):
        """Initialize enhanced audit logger."""
        self.config = config or AuditLogConfig()
        self.db: Optional[AsyncSession] = None
        self.test_mode = test_mode

        # Performance tracking
        self._total_logs_processed = 0
        self._processing_times = []
        self._batch_count = 0

        # Async processing
        self._log_queue: Optional[asyncio.Queue] = None
        self._batch_processor_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self, db: AsyncSession):
        """Initialize the audit logger with database connection."""
        self.db = db
        self._log_queue = asyncio.Queue(maxsize=self.config.max_queue_size)

        # Only start batch processor in production mode
        if not self.test_mode:
            try:
                self._batch_processor_task = asyncio.create_task(
                    self._batch_processor()
                )
            except RuntimeError:
                # No event loop available (e.g., during testing)
                pass

        logger.info("Enhanced audit logger initialized")

    async def _batch_processor(self):
        """Process log entries in batches for optimal performance."""
        batch = []
        last_batch_time = datetime.now()

        while not self._shutdown_event.is_set():
            try:
                # Wait for log entry or timeout
                timeout = self.config.batch_timeout_seconds
                log_entry = await asyncio.wait_for(
                    self._log_queue.get(), timeout=timeout
                )

                batch.append(log_entry)

                # Process batch if full or timeout reached
                now = datetime.now()
                time_since_last_batch = (now - last_batch_time).total_seconds()

                if (
                    len(batch) >= self.config.batch_size
                    or time_since_last_batch >= self.config.batch_timeout_seconds
                ):

                    await self._process_batch(batch)
                    batch = []
                    last_batch_time = now

            except asyncio.TimeoutError:
                # Process accumulated batch on timeout
                if batch:
                    await self._process_batch(batch)
                    batch = []
                    last_batch_time = datetime.now()

            except asyncio.CancelledError:
                # Process remaining batch before shutdown
                if batch:
                    await self._process_batch(batch)
                break

            except Exception as e:
                logger.error(f"Error in batch processor: {e}")
                try:
                    await asyncio.sleep(1)  # Brief pause before retry
                except RuntimeError:
                    # Event loop closed during shutdown
                    break

    async def _process_batch(self, batch: List[AuditLogEntry]):
        """Process a batch of log entries."""
        if not batch or not self.db:
            return

        start_time = datetime.now()

        try:
            # Prepare batch insert
            insert_data = []
            for entry in batch:
                # Calculate integrity hash if enabled
                if self.config.enable_integrity_checks and not entry.integrity_hash:
                    entry.integrity_hash = entry.calculate_integrity_hash()

                insert_data.append(
                    {
                        "timestamp": entry.timestamp,
                        "event_type": entry.event_type.value,
                        "level": entry.level.value,
                        "message": entry.message,
                        "user_id": entry.trading_context.user_id,
                        "session_id": entry.trading_context.session_id,
                        "correlation_id": entry.trading_context.correlation_id,
                        "symbol": entry.trading_context.symbol,
                        "order_id": entry.trading_context.order_id,
                        "trade_id": entry.trading_context.trade_id,
                        "strategy_id": entry.trading_context.strategy_id,
                        "account_id": entry.trading_context.account_id,
                        "broker": entry.trading_context.broker,
                        "client_ip": entry.trading_context.client_ip,
                        "user_agent": entry.trading_context.user_agent,
                        "event_data": json.dumps(entry.event_data or {}),
                        "integrity_hash": entry.integrity_hash,
                    }
                )

            # Execute batch insert
            insert_sql = text(
                f"""
                INSERT INTO {self.config.table_name} (
                    timestamp, event_type, level, message, user_id, session_id,
                    correlation_id, symbol, order_id, trade_id, strategy_id,
                    account_id, broker, client_ip, user_agent, event_data, integrity_hash
                ) VALUES (
                    :timestamp, :event_type, :level, :message, :user_id, :session_id,
                    :correlation_id, :symbol, :order_id, :trade_id, :strategy_id,
                    :account_id, :broker, :client_ip, :user_agent, :event_data, :integrity_hash
                )
            """
            )

            for data in insert_data:
                await self.db.execute(insert_sql, data)

            await self.db.commit()

            # Update performance metrics
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self._total_logs_processed += len(batch)
            self._processing_times.append(processing_time)
            self._batch_count += 1

            # Keep only recent processing times for metrics
            if len(self._processing_times) > 1000:
                self._processing_times = self._processing_times[-500:]

            logger.debug(
                f"Processed batch of {len(batch)} audit log entries in {processing_time:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Failed to process audit log batch: {e}")
            # Don't re-raise to avoid stopping the processor

    async def _queue_log_entry(self, entry: AuditLogEntry):
        """Queue log entry for batch processing."""
        try:
            # Generate correlation ID if required and missing
            if (
                self.config.correlation_id_required
                and not entry.trading_context.correlation_id
            ):
                entry.trading_context.correlation_id = f"auto-{uuid.uuid4().hex[:8]}"

            # Filter by log level
            if entry.level not in self.config.enabled_levels:
                return

            # In test mode, process immediately
            if self.test_mode:
                await self._process_batch([entry])
            else:
                # Add to queue (non-blocking with overflow handling)
                try:
                    self._log_queue.put_nowait(entry)
                except asyncio.QueueFull:
                    # Drop oldest entry to make room (overflow protection)
                    try:
                        self._log_queue.get_nowait()
                        self._log_queue.put_nowait(entry)
                        logger.warning(
                            "Audit log queue overflow - dropped oldest entry"
                        )
                    except asyncio.QueueEmpty:
                        pass

        except Exception as e:
            logger.error(f"Failed to queue audit log entry: {e}")

    async def log_trading_activity(
        self,
        event_type: AuditEventType,
        message: str,
        trading_context: TradingContext,
        event_data: Optional[Dict[str, Any]] = None,
        level: LogLevel = LogLevel.INFO,
    ):
        """Log trading activity with full context."""
        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            level=level,
            message=message,
            trading_context=trading_context,
            event_data=event_data,
        )

        await self._queue_log_entry(entry)

    async def log_authentication_event(
        self,
        user_id: str,
        event_type: AuditEventType,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        """Log authentication events."""
        trading_context = TradingContext(
            user_id=user_id, client_ip=ip_address, user_agent=user_agent
        )

        event_data = {"success": success}
        if additional_data:
            event_data.update(additional_data)

        level = LogLevel.INFO if success else LogLevel.WARNING
        message = f"Authentication {event_type.value.lower()}: {'success' if success else 'failure'}"

        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            level=level,
            message=message,
            trading_context=trading_context,
            event_data=event_data,
        )

        await self._queue_log_entry(entry)

    async def log_security_event(
        self,
        event_type: AuditEventType,
        severity: LogLevel,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log security events."""
        trading_context = TradingContext(user_id=user_id, client_ip=ip_address)

        message = f"Security event: {event_type.value}"

        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            level=severity,
            message=message,
            trading_context=trading_context,
            event_data=details,
        )

        await self._queue_log_entry(entry)

    async def log_system_event(
        self,
        event_type: AuditEventType,
        level: LogLevel,
        message: str,
        component: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log system events."""
        trading_context = TradingContext()

        event_data = details or {}
        if component:
            event_data["component"] = component

        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            level=level,
            message=message,
            trading_context=trading_context,
            event_data=event_data,
        )

        await self._queue_log_entry(entry)

    async def log_compliance_event(
        self,
        regulation: str,
        event_type: AuditEventType,
        result: str,
        trading_context: TradingContext,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log regulatory compliance events."""
        event_data = {"regulation": regulation, "result": result}
        if details:
            event_data.update(details)

        message = f"Compliance {regulation}: {event_type.value} - {result}"

        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            level=LogLevel.INFO,
            message=message,
            trading_context=trading_context,
            event_data=event_data,
        )

        await self._queue_log_entry(entry)

    async def search_logs(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        event_types: Optional[List[AuditEventType]] = None,
        symbol: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Search audit logs with various filters."""
        if not self.db:
            return []

        # Build dynamic query
        conditions = ["timestamp BETWEEN :start_date AND :end_date"]
        params = {"start_date": start_date, "end_date": end_date}

        if user_id:
            conditions.append("user_id = :user_id")
            params["user_id"] = user_id

        if correlation_id:
            conditions.append("correlation_id = :correlation_id")
            params["correlation_id"] = correlation_id

        if event_types:
            event_type_values = [et.value for et in event_types]
            conditions.append(
                f"event_type IN ({','.join([':et' + str(i) for i in range(len(event_type_values))])})"
            )
            for i, et_value in enumerate(event_type_values):
                params[f"et{i}"] = et_value

        if symbol:
            conditions.append("symbol = :symbol")
            params["symbol"] = symbol

        where_clause = " AND ".join(conditions)

        query = text(
            f"""
            SELECT * FROM {self.config.table_name}
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        )
        params["limit"] = limit

        result = await self.db.execute(query, params)
        return [dict(row._mapping) for row in result.fetchall()]

    async def cleanup_old_logs(self, cutoff_date: datetime):
        """Clean up audit logs older than retention period."""
        if not self.db:
            return

        try:
            # Archive logs before deletion if enabled
            if hasattr(self, "_archive_logs"):
                await self._archive_logs(cutoff_date)

            # Delete old logs
            delete_query = text(
                f"""
                DELETE FROM {self.config.table_name}
                WHERE timestamp < :cutoff_date
            """
            )

            result = await self.db.execute(delete_query, {"cutoff_date": cutoff_date})
            deleted_count = result.rowcount

            await self.db.commit()

            logger.info(
                f"Cleaned up {deleted_count} old audit log entries before {cutoff_date}"
            )

        except Exception as e:
            logger.error(f"Failed to cleanup old audit logs: {e}")
            await self.db.rollback()

    def validate_retention_compliance(self) -> Dict[str, Any]:
        """Validate retention policy compliance."""
        return {
            "compliant": self.config.retention_years >= 7,
            "retention_years": self.config.retention_years,
            "retention_days": self.config.retention_days,
            "regulations": ["MiFID II", "EMIR", "Dodd-Frank", "SOX"],
            "integrity_checks_enabled": self.config.enable_integrity_checks,
            "encryption_enabled": self.config.enable_encryption,
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get audit logger performance metrics."""
        avg_processing_time = (
            sum(self._processing_times) / len(self._processing_times)
            if self._processing_times
            else 0
        )

        return {
            "total_logs_processed": self._total_logs_processed,
            "average_processing_time_ms": round(avg_processing_time, 2),
            "batch_count": self._batch_count,
            "queue_size": self._log_queue.qsize() if self._log_queue else 0,
            "batch_processing_rate": (
                self._total_logs_processed / max(self._batch_count, 1)
            ),
        }

    async def shutdown(self):
        """Graceful shutdown of the audit logger."""
        logger.info("Shutting down enhanced audit logger...")

        # Signal shutdown
        self._shutdown_event.set()

        # Wait for batch processor to finish
        if self._batch_processor_task:
            try:
                await asyncio.wait_for(self._batch_processor_task, timeout=10)
            except asyncio.TimeoutError:
                logger.warning("Batch processor shutdown timeout")
                self._batch_processor_task.cancel()

        logger.info("Enhanced audit logger shutdown complete")


# Global audit logger instance
_audit_logger: Optional[EnhancedAuditLogger] = None


def get_audit_logger() -> EnhancedAuditLogger:
    """Get or create global audit logger instance."""
    global _audit_logger

    if _audit_logger is None:
        _audit_logger = EnhancedAuditLogger()

    return _audit_logger


async def log_trading_event(
    event_type: AuditEventType,
    message: str,
    trading_context: TradingContext,
    event_data: Optional[Dict[str, Any]] = None,
):
    """
    Convenience function for logging trading events.

    Usage:
        await log_trading_event(
            AuditEventType.ORDER_CREATED,
            "Order created successfully",
            TradingContext(user_id="trader-123", symbol="GBPUSD"),
            {"side": "BUY", "quantity": 100000}
        )
    """
    audit_logger = get_audit_logger()
    await audit_logger.log_trading_activity(
        event_type=event_type,
        message=message,
        trading_context=trading_context,
        event_data=event_data,
    )
