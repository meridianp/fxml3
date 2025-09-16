"""
Trading Activity Audit Logger for FXML4.

This module integrates the comprehensive audit logging system with all trading activities
for complete compliance and regulatory audit trails.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fxml4.api.auth.audit_logger import AuditEventType, auth_audit_logger
from fxml4.brokers.compliance.audit_logger import (
    AuditCategory,
    AuditEvent,
    AuditLogger,
    AuditSeverity,
    get_audit_logger,
)
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)


class TradingEventType(Enum):
    """Trading-specific audit event types."""

    ORDER_SUBMITTED = "order_submitted"
    ORDER_ACKNOWLEDGED = "order_acknowledged"
    ORDER_WORKING = "order_working"
    ORDER_FILLED = "order_filled"
    ORDER_PARTIALLY_FILLED = "order_partially_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    ORDER_EXPIRED = "order_expired"
    ORDER_FAILED = "order_failed"

    # Risk Management Events
    RISK_CHECK_PASSED = "risk_check_passed"
    RISK_CHECK_FAILED = "risk_check_failed"
    RISK_OVERRIDE_APPLIED = "risk_override_applied"
    POSITION_LIMIT_EXCEEDED = "position_limit_exceeded"
    EXPOSURE_LIMIT_EXCEEDED = "exposure_limit_exceeded"

    # Compliance Events
    COMPLIANCE_CHECK_PASSED = "compliance_check_passed"
    COMPLIANCE_CHECK_FAILED = "compliance_check_failed"
    COMPLIANCE_OVERRIDE_APPLIED = "compliance_override_applied"
    REGULATORY_VIOLATION = "regulatory_violation"
    SUSPICIOUS_ACTIVITY_DETECTED = "suspicious_activity_detected"

    # Broker Events
    BROKER_SELECTED = "broker_selected"
    BROKER_CONNECTION_ESTABLISHED = "broker_connection_established"
    BROKER_CONNECTION_LOST = "broker_connection_lost"
    BROKER_FAILOVER = "broker_failover"
    BROKER_RESPONSE_TIMEOUT = "broker_response_timeout"

    # Market Data Events
    MARKET_DATA_RECEIVED = "market_data_received"
    MARKET_DATA_STALE = "market_data_stale"
    MARKET_DATA_CONNECTION_LOST = "market_data_connection_lost"

    # Signal Generation Events
    SIGNAL_GENERATED = "signal_generated"
    STRATEGY_TRIGGERED = "strategy_triggered"
    MODEL_PREDICTION = "model_prediction"

    # System Events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    COMPONENT_FAILURE = "component_failure"
    CONFIGURATION_CHANGED = "configuration_changed"


@dataclass
class TradingAuditContext:
    """Context information for trading audit events."""

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    strategy_id: Optional[str] = None
    account_id: Optional[str] = None
    portfolio_id: Optional[str] = None

    # Market context
    market_session: Optional[str] = None
    volatility_level: Optional[str] = None
    liquidity_level: Optional[str] = None

    # System context
    component: Optional[str] = None
    version: Optional[str] = None
    environment: Optional[str] = None


class TradingAuditLogger:
    """Comprehensive trading activity audit logger."""

    def __init__(self):
        """Initialize trading audit logger."""
        self.audit_logger = get_audit_logger()
        self.auth_audit_logger = auth_audit_logger

        # Configuration
        self.enable_real_time_alerts = True
        self.enable_compliance_monitoring = True
        self.enable_risk_monitoring = True

        # Event buffer for batch processing
        self._event_buffer = []
        self._buffer_lock = asyncio.Lock()

    async def log_order_event(
        self,
        event_type: TradingEventType,
        order: NewOrderSingle,
        broker_id: Optional[str] = None,
        execution_report: Optional[ExecutionReport] = None,
        error_message: Optional[str] = None,
        context: Optional[TradingAuditContext] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ):
        """Log order-related audit events.

        Args:
            event_type: Type of trading event
            order: Order details
            broker_id: Broker handling the order
            execution_report: Execution details if available
            error_message: Error message if applicable
            context: Additional context information
            severity: Event severity level
        """
        try:
            details = {
                "symbol": order.symbol,
                "side": order.side.value if order.side else None,
                "order_qty": order.order_qty,
                "order_type": order.ord_type.value if order.ord_type else None,
                "time_in_force": (
                    order.time_in_force.value if order.time_in_force else None
                ),
                "price": order.price,
                "broker_id": broker_id,
            }

            # Add execution details if available
            if execution_report:
                details.update(
                    {
                        "exec_id": execution_report.exec_id,
                        "exec_type": (
                            execution_report.exec_type.value
                            if execution_report.exec_type
                            else None
                        ),
                        "ord_status": (
                            execution_report.ord_status.value
                            if execution_report.ord_status
                            else None
                        ),
                        "last_qty": execution_report.last_qty,
                        "last_px": execution_report.last_px,
                        "cum_qty": execution_report.cum_qty,
                        "avg_px": execution_report.avg_px,
                        "commission": getattr(execution_report, "commission", None),
                    }
                )

            # Add error details if applicable
            if error_message:
                details["error_message"] = error_message
                details["error_timestamp"] = datetime.now(timezone.utc).isoformat()

            # Add context information
            if context:
                details.update(
                    {
                        "user_id": context.user_id,
                        "session_id": context.session_id,
                        "strategy_id": context.strategy_id,
                        "account_id": context.account_id,
                        "portfolio_id": context.portfolio_id,
                        "market_session": context.market_session,
                        "volatility_level": context.volatility_level,
                        "component": context.component,
                        "environment": context.environment,
                    }
                )

            # Create audit event
            event = AuditEvent(
                category=AuditCategory.TRADING,
                severity=severity,
                event_type=event_type.value,
                message=f"Order {event_type.value}: {order.symbol} {order.side.value if order.side else 'UNKNOWN'} {order.order_qty}",
                cl_ord_id=order.cl_ord_id,
                broker_id=broker_id,
                symbol=order.symbol,
                user_id=context.user_id if context else None,
                session_id=context.session_id if context else None,
                component=context.component if context else "trading_engine",
                details=details,
            )

            await self.audit_logger.log_event(event)

            # Send alerts for critical events
            if (
                severity in [AuditSeverity.CRITICAL, AuditSeverity.ERROR]
                and self.enable_real_time_alerts
            ):
                await self._send_real_time_alert(event)

        except Exception as e:
            # Log to standard logger if audit logging fails
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log trading audit event: {e}")

    async def log_risk_event(
        self,
        event_type: TradingEventType,
        risk_level: str,
        details: Dict[str, Any],
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        context: Optional[TradingAuditContext] = None,
        severity: AuditSeverity = AuditSeverity.WARNING,
    ):
        """Log risk management audit events.

        Args:
            event_type: Type of risk event
            risk_level: Risk level (HIGH, MEDIUM, LOW)
            details: Risk-specific details
            order_id: Related order ID if applicable
            symbol: Symbol if applicable
            context: Additional context information
            severity: Event severity level
        """
        try:
            risk_details = {
                "risk_level": risk_level,
                "risk_check_timestamp": datetime.now(timezone.utc).isoformat(),
                **details,
            }

            if context:
                risk_details.update(
                    {
                        "user_id": context.user_id,
                        "account_id": context.account_id,
                        "portfolio_id": context.portfolio_id,
                        "strategy_id": context.strategy_id,
                    }
                )

            event = AuditEvent(
                category=AuditCategory.RISK,
                severity=severity,
                event_type=event_type.value,
                message=f"Risk event: {event_type.value} - {risk_level}",
                cl_ord_id=order_id,
                symbol=symbol,
                risk_level=risk_level,
                user_id=context.user_id if context else None,
                component=context.component if context else "risk_manager",
                details=risk_details,
            )

            await self.audit_logger.log_event(event)

            # Enable automatic risk monitoring
            if self.enable_risk_monitoring:
                await self._monitor_risk_escalation(event, risk_details)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log risk audit event: {e}")

    async def log_compliance_event(
        self,
        event_type: TradingEventType,
        compliance_flags: List[str],
        details: Dict[str, Any],
        order_id: Optional[str] = None,
        symbol: Optional[str] = None,
        context: Optional[TradingAuditContext] = None,
        severity: AuditSeverity = AuditSeverity.COMPLIANCE,
    ):
        """Log compliance-related audit events.

        Args:
            event_type: Type of compliance event
            compliance_flags: List of compliance flags triggered
            details: Compliance-specific details
            order_id: Related order ID if applicable
            symbol: Symbol if applicable
            context: Additional context information
            severity: Event severity level
        """
        try:
            compliance_details = {
                "compliance_check_timestamp": datetime.now(timezone.utc).isoformat(),
                "regulatory_framework": "MiFID II, ESMA",  # Can be configured
                "jurisdiction": "EU",  # Can be configured
                **details,
            }

            if context:
                compliance_details.update(
                    {
                        "user_id": context.user_id,
                        "account_id": context.account_id,
                        "strategy_id": context.strategy_id,
                    }
                )

            event = AuditEvent(
                category=AuditCategory.COMPLIANCE,
                severity=severity,
                event_type=event_type.value,
                message=f"Compliance event: {event_type.value} - Flags: {', '.join(compliance_flags)}",
                cl_ord_id=order_id,
                symbol=symbol,
                compliance_flags=compliance_flags,
                user_id=context.user_id if context else None,
                component=context.component if context else "compliance_engine",
                details=compliance_details,
            )

            await self.audit_logger.log_event(event)

            # Enable automatic compliance monitoring
            if self.enable_compliance_monitoring:
                await self._monitor_compliance_violations(event, compliance_flags)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log compliance audit event: {e}")

    async def log_broker_event(
        self,
        event_type: TradingEventType,
        broker_id: str,
        details: Dict[str, Any],
        order_id: Optional[str] = None,
        context: Optional[TradingAuditContext] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ):
        """Log broker-related audit events.

        Args:
            event_type: Type of broker event
            broker_id: Broker identifier
            details: Broker-specific details
            order_id: Related order ID if applicable
            context: Additional context information
            severity: Event severity level
        """
        try:
            broker_details = {
                "broker_id": broker_id,
                "event_timestamp": datetime.now(timezone.utc).isoformat(),
                **details,
            }

            event = AuditEvent(
                category=AuditCategory.EXTERNAL_API,
                severity=severity,
                event_type=event_type.value,
                message=f"Broker event: {event_type.value} - {broker_id}",
                cl_ord_id=order_id,
                broker_id=broker_id,
                user_id=context.user_id if context else None,
                component=context.component if context else "broker_adapter",
                details=broker_details,
            )

            await self.audit_logger.log_event(event)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log broker audit event: {e}")

    async def log_system_event(
        self,
        event_type: TradingEventType,
        component: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        context: Optional[TradingAuditContext] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ):
        """Log system-related audit events.

        Args:
            event_type: Type of system event
            component: Component generating the event
            message: Event message
            details: Additional event details
            context: Additional context information
            severity: Event severity level
        """
        try:
            system_details = {
                "event_timestamp": datetime.now(timezone.utc).isoformat(),
                "component": component,
                **(details or {}),
            }

            if context:
                system_details.update(
                    {"version": context.version, "environment": context.environment}
                )

            event = AuditEvent(
                category=AuditCategory.SYSTEM,
                severity=severity,
                event_type=event_type.value,
                message=message,
                component=component,
                user_id=context.user_id if context else None,
                details=system_details,
            )

            await self.audit_logger.log_event(event)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log system audit event: {e}")

    async def log_user_trading_action(
        self,
        user_id: str,
        action: str,
        details: Dict[str, Any],
        session_id: Optional[str] = None,
        order_id: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ):
        """Log user trading actions.

        Args:
            user_id: User ID performing the action
            action: Action performed
            details: Action details
            session_id: Session ID
            order_id: Related order ID if applicable
            severity: Event severity level
        """
        try:
            # Log to both trading audit and authentication audit
            await self.audit_logger.log_user_action(
                action=action,
                user_id=user_id,
                session_id=session_id,
                details=details,
                severity=severity,
            )

            # Also log to authentication audit logger for cross-referencing
            self.auth_audit_logger.log_api_access(
                username=details.get("username", "unknown"),
                endpoint=f"/trading/{action}",
                method="POST",
                status_code=200,
                details={"order_id": order_id, "trading_action": action, **details},
            )

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log user trading action: {e}")

    async def _send_real_time_alert(self, event: AuditEvent):
        """Send real-time alert for critical events.

        Args:
            event: Critical audit event
        """
        try:
            # This could integrate with alerting systems like:
            # - Email notifications
            # - Slack/Teams webhooks
            # - SMS alerts
            # - Monitoring systems (Prometheus, Grafana)
            # - SIEM systems

            alert_data = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "severity": event.severity.value,
                "timestamp": event.timestamp.isoformat(),
                "message": event.message,
                "symbol": event.symbol,
                "broker_id": event.broker_id,
                "user_id": event.user_id,
                "details": event.details,
            }

            # For now, log as high-priority alert
            import logging

            alert_logger = logging.getLogger("trading.alerts")
            alert_logger.critical(f"TRADING_ALERT: {json.dumps(alert_data)}")

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send real-time alert: {e}")

    async def _monitor_risk_escalation(
        self, event: AuditEvent, risk_details: Dict[str, Any]
    ):
        """Monitor risk event escalation.

        Args:
            event: Risk audit event
            risk_details: Risk event details
        """
        try:
            # Implement risk escalation logic
            # - Track repeated risk violations
            # - Escalate to risk managers
            # - Trigger automatic position closures
            # - Update risk limits dynamically

            if event.risk_level == "HIGH":
                # High-risk events require immediate attention
                await self._send_real_time_alert(event)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to monitor risk escalation: {e}")

    async def _monitor_compliance_violations(
        self, event: AuditEvent, compliance_flags: List[str]
    ):
        """Monitor compliance violations.

        Args:
            event: Compliance audit event
            compliance_flags: Compliance flags triggered
        """
        try:
            # Implement compliance monitoring logic
            # - Track regulatory violations
            # - Generate regulatory reports
            # - Escalate to compliance officers
            # - Block problematic activities

            # Check for serious violations
            serious_violations = [
                "MARKET_MANIPULATION",
                "INSIDER_TRADING",
                "WASH_TRADING",
            ]
            if any(flag in serious_violations for flag in compliance_flags):
                await self._send_real_time_alert(event)
                # Could also trigger automatic trade blocking here

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to monitor compliance violations: {e}")

    async def get_audit_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get audit summary for a time period.

        Args:
            start_date: Start date for summary
            end_date: End date for summary
            filters: Additional filters (symbol, user_id, etc.)

        Returns:
            Audit summary statistics
        """
        try:
            # This would query the audit logs and generate summary statistics
            # In a full implementation, this would integrate with a database or search system

            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "summary": {
                    "total_events": 0,  # Would be populated from actual data
                    "trading_events": 0,
                    "risk_events": 0,
                    "compliance_events": 0,
                    "system_events": 0,
                },
                "risk_analysis": {
                    "high_risk_events": 0,
                    "risk_violations": 0,
                    "escalations": 0,
                },
                "compliance_analysis": {
                    "violations": 0,
                    "flags_triggered": [],
                    "regulatory_issues": 0,
                },
                "filters_applied": filters or {},
            }

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to generate audit summary: {e}")
            return {"error": str(e)}

    async def shutdown(self):
        """Shutdown trading audit logger."""
        try:
            # Flush any remaining events
            if self.audit_logger:
                await self.audit_logger.shutdown()

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error shutting down trading audit logger: {e}")


# Global trading audit logger instance
_trading_audit_logger: Optional[TradingAuditLogger] = None


def get_trading_audit_logger() -> TradingAuditLogger:
    """Get the global trading audit logger instance."""
    global _trading_audit_logger
    if _trading_audit_logger is None:
        _trading_audit_logger = TradingAuditLogger()
    return _trading_audit_logger


# Convenience functions for quick trading audit logging
async def audit_order_submitted(
    order: NewOrderSingle, broker_id: str, context: TradingAuditContext = None
):
    """Quick audit log for order submission."""
    logger = get_trading_audit_logger()
    await logger.log_order_event(
        TradingEventType.ORDER_SUBMITTED,
        order,
        broker_id,
        context=context,
        severity=AuditSeverity.INFO,
    )


async def audit_order_filled(
    order: NewOrderSingle,
    execution_report: ExecutionReport,
    broker_id: str,
    context: TradingAuditContext = None,
):
    """Quick audit log for order fill."""
    logger = get_trading_audit_logger()
    await logger.log_order_event(
        TradingEventType.ORDER_FILLED,
        order,
        broker_id,
        execution_report=execution_report,
        context=context,
        severity=AuditSeverity.INFO,
    )


async def audit_order_rejected(
    order: NewOrderSingle,
    error_message: str,
    broker_id: str,
    context: TradingAuditContext = None,
):
    """Quick audit log for order rejection."""
    logger = get_trading_audit_logger()
    await logger.log_order_event(
        TradingEventType.ORDER_REJECTED,
        order,
        broker_id,
        error_message=error_message,
        context=context,
        severity=AuditSeverity.ERROR,
    )


async def audit_risk_violation(
    risk_level: str,
    violation_details: Dict[str, Any],
    context: TradingAuditContext = None,
):
    """Quick audit log for risk violations."""
    logger = get_trading_audit_logger()
    await logger.log_risk_event(
        TradingEventType.RISK_CHECK_FAILED,
        risk_level,
        violation_details,
        context=context,
        severity=(
            AuditSeverity.WARNING if risk_level == "MEDIUM" else AuditSeverity.CRITICAL
        ),
    )


async def audit_compliance_violation(
    compliance_flags: List[str],
    violation_details: Dict[str, Any],
    context: TradingAuditContext = None,
):
    """Quick audit log for compliance violations."""
    logger = get_trading_audit_logger()
    await logger.log_compliance_event(
        TradingEventType.COMPLIANCE_CHECK_FAILED,
        compliance_flags,
        violation_details,
        context=context,
        severity=AuditSeverity.COMPLIANCE,
    )
