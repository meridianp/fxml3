"""
Comprehensive TDD test suite for enhanced audit logging system.

This module tests the production-ready audit logging system including:
- Trading activity logging with 7-year retention requirements
- Structured logging with correlation IDs and context
- Performance optimization for high-frequency trading
- Integration with JWT authentication and rate limiting
- Regulatory compliance logging (MiFID II, EMIR, Dodd-Frank)
- Audit trail integrity and immutability features
- Log aggregation and search capabilities
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
import pytest_asyncio

from fxml4.api.auth.enhanced_audit_logger import (
    AuditEventType,
    AuditLogConfig,
    AuditLogEntry,
    EnhancedAuditLogger,
    LogLevel,
    RetentionPolicy,
    TradingContext,
)


@pytest.mark.auth
@pytest.mark.compliance
class TestAuditLogConfig:
    """Test audit logging configuration management."""

    def test_audit_log_config_default_values(self):
        """Test default audit logging configuration."""
        config = AuditLogConfig()

        # Verify retention requirements
        assert config.retention_years == 7
        assert config.retention_days == 7 * 365  # 7 years in days

        # Verify performance settings
        assert config.batch_size == 100
        assert config.batch_timeout_seconds == 5
        assert config.max_queue_size == 10000

        # Verify compliance settings
        assert config.enable_integrity_checks is True
        assert config.enable_encryption is True
        assert config.correlation_id_required is True

        # Verify log levels
        assert LogLevel.INFO in config.enabled_levels
        assert LogLevel.WARNING in config.enabled_levels
        assert LogLevel.ERROR in config.enabled_levels

    def test_audit_log_config_custom_values(self):
        """Test custom audit logging configuration."""
        config = AuditLogConfig(
            retention_years=10,
            batch_size=50,
            batch_timeout_seconds=3,
            enable_integrity_checks=False,
            enabled_levels=[LogLevel.ERROR, LogLevel.CRITICAL],
        )

        assert config.retention_years == 10
        assert config.retention_days == 10 * 365
        assert config.batch_size == 50
        assert config.batch_timeout_seconds == 3
        assert config.enable_integrity_checks is False
        assert config.enabled_levels == [LogLevel.ERROR, LogLevel.CRITICAL]

    def test_audit_log_config_validation(self):
        """Test audit log configuration validation."""
        # Test invalid retention period
        with pytest.raises(ValueError, match="retention_years must be at least 7"):
            AuditLogConfig(retention_years=5)

        # Test invalid batch size
        with pytest.raises(ValueError, match="batch_size must be positive"):
            AuditLogConfig(batch_size=0)

        # Test invalid timeout
        with pytest.raises(ValueError, match="batch_timeout_seconds must be positive"):
            AuditLogConfig(batch_timeout_seconds=-1)


@pytest.mark.auth
@pytest.mark.compliance
class TestAuditLogEntry:
    """Test audit log entry structures."""

    def test_audit_log_entry_creation(self):
        """Test audit log entry creation."""
        timestamp = datetime.now(timezone.utc)
        trading_context = TradingContext(
            user_id="trader-123",
            session_id="session-456",
            correlation_id="corr-789",
            symbol="GBPUSD",
            order_id="order-101112",
        )

        entry = AuditLogEntry(
            timestamp=timestamp,
            event_type=AuditEventType.TRADE_EXECUTED,
            level=LogLevel.INFO,
            message="Trade executed successfully",
            trading_context=trading_context,
            event_data={"quantity": 100000, "price": 1.2345},
        )

        assert entry.timestamp == timestamp
        assert entry.event_type == AuditEventType.TRADE_EXECUTED
        assert entry.level == LogLevel.INFO
        assert entry.message == "Trade executed successfully"
        assert entry.trading_context.user_id == "trader-123"
        assert entry.event_data["quantity"] == 100000

    def test_audit_log_entry_serialization(self):
        """Test audit log entry JSON serialization."""
        timestamp = datetime.now(timezone.utc)
        trading_context = TradingContext(
            user_id="trader-456", session_id="session-789", correlation_id="corr-012"
        )

        entry = AuditLogEntry(
            timestamp=timestamp,
            event_type=AuditEventType.ORDER_CREATED,
            level=LogLevel.INFO,
            message="Order created",
            trading_context=trading_context,
            event_data={"symbol": "EURUSD", "side": "BUY"},
        )

        json_data = entry.to_json()
        parsed_data = json.loads(json_data)

        assert parsed_data["event_type"] == "ORDER_CREATED"
        assert parsed_data["level"] == "INFO"
        assert parsed_data["message"] == "Order created"
        assert parsed_data["trading_context"]["user_id"] == "trader-456"
        assert parsed_data["event_data"]["symbol"] == "EURUSD"

    def test_audit_log_entry_integrity_hash(self):
        """Test audit log entry integrity hash generation."""
        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=AuditEventType.USER_LOGIN,
            level=LogLevel.INFO,
            message="User login successful",
            trading_context=TradingContext(user_id="user-123"),
            event_data={"ip_address": "192.168.1.100"},
        )

        hash1 = entry.calculate_integrity_hash()
        hash2 = entry.calculate_integrity_hash()

        # Same entry should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest length

        # Modified entry should produce different hash
        entry.message = "Modified message"
        hash3 = entry.calculate_integrity_hash()
        assert hash1 != hash3


@pytest.mark.auth
@pytest.mark.compliance
class TestTradingContext:
    """Test trading context management."""

    def test_trading_context_creation(self):
        """Test trading context creation and validation."""
        context = TradingContext(
            user_id="trader-789",
            session_id="session-012",
            correlation_id="corr-345",
            symbol="USDJPY",
            order_id="order-678",
            strategy_id="gbpusd-ml-v1",
            account_id="account-901",
        )

        assert context.user_id == "trader-789"
        assert context.session_id == "session-012"
        assert context.correlation_id == "corr-345"
        assert context.symbol == "USDJPY"
        assert context.order_id == "order-678"
        assert context.strategy_id == "gbpusd-ml-v1"
        assert context.account_id == "account-901"

    def test_trading_context_to_dict(self):
        """Test trading context dictionary conversion."""
        context = TradingContext(user_id="trader-123", correlation_id="corr-456")

        context_dict = context.to_dict()

        assert context_dict["user_id"] == "trader-123"
        assert context_dict["correlation_id"] == "corr-456"
        assert "session_id" not in context_dict  # Should exclude None values

    def test_trading_context_from_request(self):
        """Test trading context extraction from request."""
        mock_request = Mock()
        mock_request.headers = {
            "X-Correlation-ID": "corr-789",
            "X-Session-ID": "session-012",
        }
        mock_request.client.host = "192.168.1.100"

        mock_user = Mock()
        mock_user.id = "trader-456"

        context = TradingContext.from_request(mock_request, mock_user)

        assert context.user_id == "trader-456"
        assert context.correlation_id == "corr-789"
        assert context.session_id == "session-012"
        assert context.client_ip == "192.168.1.100"


@pytest.mark.auth
@pytest.mark.compliance
class TestEnhancedAuditLogger:
    """Test enhanced audit logger functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def audit_config(self):
        """Create audit logger configuration."""
        return AuditLogConfig(
            batch_size=10, batch_timeout_seconds=1, max_queue_size=100
        )

    @pytest_asyncio.fixture
    async def audit_logger(self, mock_db, audit_config):
        """Create enhanced audit logger."""
        logger = EnhancedAuditLogger(config=audit_config, test_mode=True)
        await logger.initialize(mock_db)
        return logger

    @pytest.mark.asyncio
    async def test_audit_logger_initialization(self, mock_db):
        """Test audit logger initialization."""
        config = AuditLogConfig()
        logger = EnhancedAuditLogger(config=config, test_mode=True)

        await logger.initialize(mock_db)

        assert logger.db == mock_db
        assert logger.config == config
        assert logger._log_queue is not None
        # In test mode, batch processor task should not be started
        assert logger.test_mode is True

    @pytest.mark.asyncio
    async def test_log_trading_activity(self, audit_logger):
        """Test logging trading activities."""
        trading_context = TradingContext(
            user_id="trader-123",
            correlation_id="corr-456",
            symbol="GBPUSD",
            order_id="order-789",
        )

        await audit_logger.log_trading_activity(
            event_type=AuditEventType.ORDER_CREATED,
            message="Order created successfully",
            trading_context=trading_context,
            event_data={
                "symbol": "GBPUSD",
                "side": "BUY",
                "quantity": 100000,
                "price": 1.2345,
            },
        )

        # In test mode, logs are processed immediately, so verify database was called
        assert audit_logger.db.execute.called

        # Verify the correct data was logged
        call_args = audit_logger.db.execute.call_args
        logged_data = call_args[0][1]  # Get the data dict from execute call
        assert logged_data["event_type"] == "ORDER_CREATED"
        assert logged_data["message"] == "Order created successfully"
        assert logged_data["user_id"] == "trader-123"
        assert logged_data["correlation_id"] == "corr-456"
        assert logged_data["symbol"] == "GBPUSD"
        assert logged_data["order_id"] == "order-789"
        assert "integrity_hash" in logged_data

    @pytest.mark.asyncio
    async def test_log_authentication_event(self, audit_logger):
        """Test logging authentication events."""
        await audit_logger.log_authentication_event(
            user_id="user-123",
            event_type=AuditEventType.USER_LOGIN,
            success=True,
            ip_address="192.168.1.100",
            user_agent="FXML4-Client/1.0",
            additional_data={"2fa_enabled": True},
        )

        # Verify authentication event was logged
        assert audit_logger._log_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_log_security_event(self, audit_logger):
        """Test logging security events."""
        await audit_logger.log_security_event(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            severity=LogLevel.WARNING,
            user_id="user-456",
            ip_address="192.168.1.200",
            details={"limit_type": "user", "current_count": 150, "limit": 100},
        )

        # Verify security event was logged
        assert audit_logger._log_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_log_system_event(self, audit_logger):
        """Test logging system events."""
        await audit_logger.log_system_event(
            event_type=AuditEventType.SYSTEM_STARTUP,
            level=LogLevel.INFO,
            message="FXML4 trading system started",
            component="api-server",
            details={
                "version": "1.0.0",
                "environment": "production",
                "startup_time_ms": 2500,
            },
        )

        # Verify system event was logged
        assert audit_logger._log_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_log_compliance_event(self, audit_logger):
        """Test logging compliance events."""
        await audit_logger.log_compliance_event(
            regulation="MiFID II",
            event_type=AuditEventType.COMPLIANCE_CHECK,
            result="PASS",
            trading_context=TradingContext(user_id="trader-789", symbol="EURUSD"),
            details={
                "check_type": "position_limit",
                "current_position": 500000,
                "limit": 1000000,
            },
        )

        # Verify compliance event was logged
        assert audit_logger._log_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_batch_processing(self, audit_logger, mock_db):
        """Test batch processing of log entries."""
        trading_context = TradingContext(user_id="trader-batch")

        # Add multiple log entries
        for i in range(15):  # Exceeds batch_size of 10
            await audit_logger.log_trading_activity(
                event_type=AuditEventType.ORDER_CREATED,
                message=f"Order {i} created",
                trading_context=trading_context,
            )

        # Wait for batch processing
        await asyncio.sleep(0.1)

        # Verify database inserts were called
        assert mock_db.execute.call_count >= 1
        assert mock_db.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_log_level_filtering(self, mock_db):
        """Test log level filtering."""
        config = AuditLogConfig(enabled_levels=[LogLevel.ERROR, LogLevel.CRITICAL])
        logger = EnhancedAuditLogger(config=config, test_mode=True)
        await logger.initialize(mock_db)

        # Try to log INFO level event (should be filtered)
        await logger.log_system_event(
            event_type=AuditEventType.SYSTEM_STARTUP,
            level=LogLevel.INFO,
            message="Info message",
        )

        # Try to log ERROR level event (should be logged)
        await logger.log_system_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            level=LogLevel.ERROR,
            message="Error message",
        )

        # Only ERROR event should be queued
        assert logger._log_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_correlation_id_generation(self, audit_logger):
        """Test automatic correlation ID generation."""
        # Log without correlation ID
        await audit_logger.log_trading_activity(
            event_type=AuditEventType.ORDER_CREATED,
            message="Order created",
            trading_context=TradingContext(user_id="trader-123"),
        )

        # Verify correlation ID was generated
        assert audit_logger._log_queue.qsize() == 1
        log_entry = audit_logger._log_queue.get_nowait()
        assert log_entry.trading_context.correlation_id is not None
        assert len(log_entry.trading_context.correlation_id) > 0

    @pytest.mark.asyncio
    async def test_log_queue_overflow_handling(self, mock_db):
        """Test handling of log queue overflow."""
        config = AuditLogConfig(max_queue_size=5)
        logger = EnhancedAuditLogger(config=config, test_mode=True)
        await logger.initialize(mock_db)

        # Fill queue beyond capacity
        for i in range(10):
            await logger.log_system_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                level=LogLevel.ERROR,
                message=f"Error {i}",
            )

        # Queue size should not exceed max_queue_size
        assert logger._log_queue.qsize() <= config.max_queue_size

    @pytest.mark.asyncio
    async def test_performance_metrics(self, audit_logger):
        """Test performance metrics collection."""
        # Generate some log entries
        for i in range(5):
            await audit_logger.log_trading_activity(
                event_type=AuditEventType.ORDER_CREATED,
                message=f"Order {i}",
                trading_context=TradingContext(user_id=f"trader-{i}"),
            )

        metrics = audit_logger.get_performance_metrics()

        assert "total_logs_processed" in metrics
        assert "average_processing_time_ms" in metrics
        assert "queue_size" in metrics
        assert "batch_processing_rate" in metrics


@pytest.mark.auth
@pytest.mark.compliance
class TestAuditLogRetention:
    """Test audit log retention and cleanup."""

    @pytest.fixture
    def retention_policy(self):
        """Create retention policy."""
        return RetentionPolicy(
            retention_days=2555,  # 7 years
            cleanup_interval_days=1,
            archive_before_delete=True,
        )

    @pytest_asyncio.fixture
    async def audit_logger_with_retention(self, mock_db):
        """Create audit logger with retention policy."""
        config = AuditLogConfig(retention_years=7)
        logger = EnhancedAuditLogger(config=config, test_mode=True)
        await logger.initialize(mock_db)
        return logger

    @pytest.mark.asyncio
    async def test_retention_policy_cleanup(self, audit_logger_with_retention, mock_db):
        """Test retention policy cleanup execution."""
        # Mock old log entries
        cutoff_date = datetime.now(timezone.utc) - timedelta(
            days=2556
        )  # Older than 7 years

        await audit_logger_with_retention.cleanup_old_logs(cutoff_date)

        # Verify cleanup queries were executed
        mock_db.execute.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_log_archiving(self, audit_logger_with_retention):
        """Test log archiving before deletion."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=2556)

        with patch.object(audit_logger_with_retention, "_archive_logs") as mock_archive:
            await audit_logger_with_retention.cleanup_old_logs(cutoff_date)

            # Verify archiving was called before deletion
            mock_archive.assert_called_once()

    @pytest.mark.asyncio
    async def test_retention_compliance_validation(self, audit_logger_with_retention):
        """Test retention compliance validation."""
        # Test that 7-year retention is enforced
        result = audit_logger_with_retention.validate_retention_compliance()

        assert result["compliant"] is True
        assert result["retention_years"] == 7
        assert "MiFID II" in result["regulations"]
        assert "EMIR" in result["regulations"]


@pytest.mark.auth
@pytest.mark.compliance
class TestAuditLogIntegration:
    """Test audit logging integration scenarios."""

    @pytest.mark.asyncio
    async def test_jwt_authentication_integration(self):
        """Test integration with JWT authentication events."""
        mock_db = AsyncMock()
        config = AuditLogConfig()
        logger = EnhancedAuditLogger(config=config, test_mode=True)
        await logger.initialize(mock_db)

        # Simulate JWT token creation event
        await logger.log_authentication_event(
            user_id="trader-123",
            event_type=AuditEventType.TOKEN_CREATED,
            success=True,
            additional_data={
                "token_type": "access",
                "expires_in": 1800,
                "scopes": ["trading", "view_data"],
            },
        )

        # Simulate token refresh event
        await logger.log_authentication_event(
            user_id="trader-123",
            event_type=AuditEventType.TOKEN_REFRESHED,
            success=True,
            additional_data={
                "old_token_jti": "old-jti-123",
                "new_token_jti": "new-jti-456",
            },
        )

        # Verify events were logged
        assert logger._log_queue.qsize() == 2

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self):
        """Test integration with rate limiting events."""
        mock_db = AsyncMock()
        logger = EnhancedAuditLogger(config=AuditLogConfig())
        await logger.initialize(mock_db)

        # Simulate rate limit exceeded event
        await logger.log_security_event(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            severity=LogLevel.WARNING,
            user_id="trader-456",
            ip_address="192.168.1.100",
            details={
                "limit_type": "user",
                "requests_per_minute": 150,
                "limit": 100,
                "retry_after": 60,
            },
        )

        # Verify security event was logged
        assert logger._log_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_trading_workflow_integration(self):
        """Test integration with complete trading workflow."""
        mock_db = AsyncMock()
        logger = EnhancedAuditLogger(config=AuditLogConfig())
        await logger.initialize(mock_db)

        correlation_id = "workflow-corr-123"
        trading_context = TradingContext(
            user_id="trader-789", correlation_id=correlation_id, symbol="GBPUSD"
        )

        # Simulate complete trading workflow
        workflow_events = [
            (
                AuditEventType.ORDER_CREATED,
                "Order created",
                {"side": "BUY", "quantity": 100000},
            ),
            (AuditEventType.ORDER_VALIDATED, "Order validated", {"risk_check": "PASS"}),
            (
                AuditEventType.ORDER_SUBMITTED,
                "Order submitted to broker",
                {"broker": "IB"},
            ),
            (
                AuditEventType.ORDER_FILLED,
                "Order filled",
                {"fill_price": 1.2345, "fill_quantity": 100000},
            ),
            (AuditEventType.TRADE_EXECUTED, "Trade executed", {"profit_loss": 250.00}),
        ]

        for event_type, message, data in workflow_events:
            await logger.log_trading_activity(
                event_type=event_type,
                message=message,
                trading_context=trading_context,
                event_data=data,
            )

        # Verify all workflow events were logged with same correlation ID
        assert logger._log_queue.qsize() == 5


@pytest.mark.auth
@pytest.mark.compliance
class TestAuditLogSearch:
    """Test audit log search and query capabilities."""

    @pytest_asyncio.fixture
    async def audit_logger_with_search(self, mock_db):
        """Create audit logger with search capabilities."""
        config = AuditLogConfig()
        logger = EnhancedAuditLogger(config=config, test_mode=True)
        await logger.initialize(mock_db)
        return logger

    @pytest.mark.asyncio
    async def test_search_by_user_id(self, audit_logger_with_search, mock_db):
        """Test searching audit logs by user ID."""
        # Mock search results
        mock_results = [
            {"event_type": "ORDER_CREATED", "user_id": "trader-123"},
            {"event_type": "TRADE_EXECUTED", "user_id": "trader-123"},
        ]
        mock_db.execute.return_value.fetchall.return_value = mock_results

        results = await audit_logger_with_search.search_logs(
            user_id="trader-123",
            start_date=datetime.now(timezone.utc) - timedelta(days=1),
            end_date=datetime.now(timezone.utc),
        )

        assert len(results) == 2
        assert all(result["user_id"] == "trader-123" for result in results)

    @pytest.mark.asyncio
    async def test_search_by_correlation_id(self, audit_logger_with_search, mock_db):
        """Test searching audit logs by correlation ID."""
        correlation_id = "search-corr-456"

        results = await audit_logger_with_search.search_logs(
            correlation_id=correlation_id,
            start_date=datetime.now(timezone.utc) - timedelta(hours=1),
            end_date=datetime.now(timezone.utc),
        )

        # Verify search query was executed with correlation ID
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_search_by_event_type(self, audit_logger_with_search, mock_db):
        """Test searching audit logs by event type."""
        results = await audit_logger_with_search.search_logs(
            event_types=[AuditEventType.TRADE_EXECUTED, AuditEventType.ORDER_FILLED],
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
        )

        # Verify search was executed
        mock_db.execute.assert_called()


@pytest.mark.auth
@pytest.mark.compliance
class TestAuditLogCompliance:
    """Test audit logging regulatory compliance features."""

    @pytest.mark.asyncio
    async def test_mifid_ii_compliance_logging(self):
        """Test MiFID II compliance logging requirements."""
        mock_db = AsyncMock()
        logger = EnhancedAuditLogger(config=AuditLogConfig())
        await logger.initialize(mock_db)

        # MiFID II requires comprehensive trade reporting
        await logger.log_compliance_event(
            regulation="MiFID II",
            event_type=AuditEventType.TRADE_EXECUTED,
            result="COMPLIANT",
            trading_context=TradingContext(
                user_id="trader-mifid", symbol="EURUSD", order_id="mifid-order-123"
            ),
            details={
                "trade_time": datetime.now(timezone.utc).isoformat(),
                "instrument_id": "EURUSD",
                "quantity": 100000,
                "price": 1.0850,
                "venue": "FXML4-IB",
                "client_classification": "professional",
            },
        )

        assert logger._log_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_emir_compliance_logging(self):
        """Test EMIR compliance logging requirements."""
        mock_db = AsyncMock()
        logger = EnhancedAuditLogger(config=AuditLogConfig())
        await logger.initialize(mock_db)

        # EMIR requires derivative trade reporting
        await logger.log_compliance_event(
            regulation="EMIR",
            event_type=AuditEventType.DERIVATIVE_TRADE,
            result="REPORTED",
            trading_context=TradingContext(
                user_id="trader-emir", symbol="EURUSD", order_id="emir-order-456"
            ),
            details={
                "reporting_counterparty": "FXML4-LEI",
                "other_counterparty": "CLIENT-LEI",
                "trade_date": datetime.now(timezone.utc).date().isoformat(),
                "notional_amount": 100000,
                "currency": "EUR",
            },
        )

        assert logger._log_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_dodd_frank_compliance_logging(self):
        """Test Dodd-Frank compliance logging requirements."""
        mock_db = AsyncMock()
        logger = EnhancedAuditLogger(config=AuditLogConfig())
        await logger.initialize(mock_db)

        # Dodd-Frank requires swap data reporting
        await logger.log_compliance_event(
            regulation="Dodd-Frank",
            event_type=AuditEventType.SWAP_REPORTING,
            result="SUBMITTED",
            trading_context=TradingContext(user_id="trader-dodd", symbol="USDJPY"),
            details={
                "swap_dealer_id": "FXML4-SD",
                "unique_swap_identifier": "USI-789",
                "reporting_side": "Sell",
                "effective_date": datetime.now(timezone.utc).date().isoformat(),
            },
        )

        assert logger._log_queue.qsize() == 1
