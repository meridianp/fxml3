"""Compliance Engine for Real-time Compliance Monitoring.

This module provides a comprehensive compliance engine that monitors
trading activities and enforces regulatory requirements.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from ...fix.messages.base import OrdType, Side
from ...fix.messages.orders import ExecutionReport, NewOrderSingle
from .audit_logger import AuditCategory, AuditEvent, AuditLogger, AuditSeverity

logger = logging.getLogger(__name__)


class ComplianceResult(Enum):
    """Compliance check results."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"


class ViolationSeverity(Enum):
    """Compliance violation severity levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ComplianceViolation:
    """Details of a compliance violation."""

    rule_id: str
    rule_name: str
    violation_type: str
    severity: ViolationSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    # Context
    cl_ord_id: Optional[str] = None
    symbol: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Remediation
    suggested_action: Optional[str] = None
    requires_manual_review: bool = False
    auto_block: bool = False

    # References
    regulatory_reference: Optional[str] = None
    documentation_link: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "violation_type": self.violation_type,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "cl_ord_id": self.cl_ord_id,
            "symbol": self.symbol,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "suggested_action": self.suggested_action,
            "requires_manual_review": self.requires_manual_review,
            "auto_block": self.auto_block,
            "regulatory_reference": self.regulatory_reference,
            "documentation_link": self.documentation_link,
        }


class ComplianceRule(ABC):
    """Base class for compliance rules."""

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        description: str,
        enabled: bool = True,
        severity: ViolationSeverity = ViolationSeverity.MEDIUM,
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.description = description
        self.enabled = enabled
        self.severity = severity

        # Statistics
        self.checks_performed = 0
        self.violations_found = 0
        self.last_check_time: Optional[datetime] = None

    @abstractmethod
    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check order for compliance violations.

        Args:
            order: Order to check.
            context: Additional context (positions, history, etc.).

        Returns:
            Compliance violation if found, None otherwise.
        """
        pass

    async def check_execution(
        self, execution: ExecutionReport, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check execution for compliance violations.

        Args:
            execution: Execution report to check.
            context: Additional context.

        Returns:
            Compliance violation if found, None otherwise.
        """
        # Default implementation - override if needed
        return None

    def _create_violation(
        self,
        violation_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cl_ord_id: Optional[str] = None,
        symbol: Optional[str] = None,
        user_id: Optional[str] = None,
        suggested_action: Optional[str] = None,
        requires_manual_review: bool = False,
        auto_block: bool = False,
    ) -> ComplianceViolation:
        """Create a compliance violation."""
        return ComplianceViolation(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            violation_type=violation_type,
            severity=self.severity,
            message=message,
            details=details or {},
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            user_id=user_id,
            suggested_action=suggested_action,
            requires_manual_review=requires_manual_review,
            auto_block=auto_block,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get rule statistics."""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "enabled": self.enabled,
            "checks_performed": self.checks_performed,
            "violations_found": self.violations_found,
            "violation_rate": (
                self.violations_found / self.checks_performed * 100
                if self.checks_performed > 0
                else 0
            ),
            "last_check_time": (
                self.last_check_time.isoformat() if self.last_check_time else None
            ),
        }


class PositionLimitRule(ComplianceRule):
    """Rule to check position size limits."""

    def __init__(
        self,
        position_limits: Dict[str, float],
        severity: ViolationSeverity = ViolationSeverity.HIGH,
    ):
        super().__init__(
            rule_id="POS_LIMIT_001",
            rule_name="Position Size Limit",
            description="Monitors position sizes against configured limits",
            severity=severity,
        )
        self.position_limits = position_limits

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check order against position limits."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Get current position
        positions = context.get("positions", {})
        current_position = positions.get(order.symbol, 0)

        # Calculate new position
        order_qty = order.order_qty if order.side == Side.BUY else -order.order_qty
        new_position = abs(current_position + order_qty)

        # Check against limit
        symbol_limit = self.position_limits.get(order.symbol)
        if symbol_limit and new_position > symbol_limit:
            self.violations_found += 1

            return self._create_violation(
                violation_type="POSITION_LIMIT_EXCEEDED",
                message=f"Position limit exceeded for {order.symbol}",
                details={
                    "current_position": current_position,
                    "order_quantity": order_qty,
                    "new_position": new_position,
                    "position_limit": symbol_limit,
                    "excess_amount": new_position - symbol_limit,
                },
                cl_ord_id=order.cl_ord_id,
                symbol=order.symbol,
                suggested_action="Reduce order size or close existing positions",
                auto_block=True,
            )

        return None


class ConcentrationRule(ComplianceRule):
    """Rule to check portfolio concentration limits."""

    def __init__(
        self,
        max_concentration_pct: float = 25.0,
        severity: ViolationSeverity = ViolationSeverity.MEDIUM,
    ):
        super().__init__(
            rule_id="CONC_001",
            rule_name="Portfolio Concentration",
            description="Monitors portfolio concentration by symbol",
            severity=severity,
        )
        self.max_concentration_pct = max_concentration_pct

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check order against concentration limits."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Get portfolio value
        total_portfolio_value = context.get("total_portfolio_value", 0)
        if total_portfolio_value <= 0:
            return None

        # Calculate order notional
        if not hasattr(order, "price") or not order.price:
            return None  # Can't calculate for market orders without price

        order_notional = order.order_qty * order.price

        # Get current symbol exposure
        positions = context.get("positions", {})
        current_exposure = positions.get(order.symbol, 0) * context.get(
            "prices", {}
        ).get(order.symbol, order.price)

        # Calculate new exposure
        new_exposure = abs(current_exposure + order_notional)
        concentration_pct = (new_exposure / total_portfolio_value) * 100

        if concentration_pct > self.max_concentration_pct:
            self.violations_found += 1

            return self._create_violation(
                violation_type="CONCENTRATION_LIMIT_EXCEEDED",
                message=f"Portfolio concentration limit exceeded for {order.symbol}",
                details={
                    "current_exposure": current_exposure,
                    "order_notional": order_notional,
                    "new_exposure": new_exposure,
                    "total_portfolio_value": total_portfolio_value,
                    "concentration_pct": concentration_pct,
                    "max_concentration_pct": self.max_concentration_pct,
                },
                cl_ord_id=order.cl_ord_id,
                symbol=order.symbol,
                suggested_action="Reduce order size or diversify portfolio",
                requires_manual_review=True,
            )

        return None


class TradingHoursRule(ComplianceRule):
    """Rule to check trading hours compliance."""

    def __init__(
        self,
        allowed_hours: Dict[
            str, List[tuple]
        ],  # symbol -> [(start_hour, end_hour), ...]
        timezone_name: str = "UTC",
        severity: ViolationSeverity = ViolationSeverity.LOW,
    ):
        super().__init__(
            rule_id="HOURS_001",
            rule_name="Trading Hours Compliance",
            description="Ensures trading only occurs during allowed hours",
            severity=severity,
        )
        self.allowed_hours = allowed_hours
        self.timezone_name = timezone_name

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check order against trading hours."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Get current time
        current_time = datetime.now(timezone.utc)
        current_hour = current_time.hour

        # Check if symbol has specific hours
        symbol_hours = self.allowed_hours.get(order.symbol)
        if not symbol_hours:
            # No restrictions for this symbol
            return None

        # Check if current time is within allowed hours
        for start_hour, end_hour in symbol_hours:
            if start_hour <= current_hour < end_hour:
                return None  # Within allowed hours

        self.violations_found += 1

        return self._create_violation(
            violation_type="TRADING_HOURS_VIOLATION",
            message=f"Trading outside allowed hours for {order.symbol}",
            details={
                "current_hour": current_hour,
                "allowed_hours": symbol_hours,
                "timezone": self.timezone_name,
            },
            cl_ord_id=order.cl_ord_id,
            symbol=order.symbol,
            suggested_action="Wait for market hours or use appropriate session",
            auto_block=True,
        )


class VelocityRule(ComplianceRule):
    """Rule to check order velocity (rate limiting)."""

    def __init__(
        self,
        max_orders_per_minute: int = 60,
        max_orders_per_hour: int = 1000,
        severity: ViolationSeverity = ViolationSeverity.MEDIUM,
    ):
        super().__init__(
            rule_id="VEL_001",
            rule_name="Order Velocity Check",
            description="Monitors order submission rate",
            severity=severity,
        )
        self.max_orders_per_minute = max_orders_per_minute
        self.max_orders_per_hour = max_orders_per_hour

        # Track order history
        self.order_history: List[datetime] = []

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check order velocity."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        current_time = datetime.now(timezone.utc)

        # Clean old entries
        one_hour_ago = current_time - timedelta(hours=1)
        one_minute_ago = current_time - timedelta(minutes=1)

        self.order_history = [t for t in self.order_history if t > one_hour_ago]

        # Count recent orders
        orders_last_minute = sum(1 for t in self.order_history if t > one_minute_ago)
        orders_last_hour = len(self.order_history)

        # Add current order to history
        self.order_history.append(current_time)

        # Check limits
        if orders_last_minute >= self.max_orders_per_minute:
            self.violations_found += 1

            return self._create_violation(
                violation_type="ORDER_VELOCITY_EXCEEDED",
                message="Order submission rate too high (per minute)",
                details={
                    "orders_last_minute": orders_last_minute,
                    "max_orders_per_minute": self.max_orders_per_minute,
                    "orders_last_hour": orders_last_hour,
                },
                cl_ord_id=order.cl_ord_id,
                suggested_action="Reduce order submission rate",
                auto_block=True,
            )

        if orders_last_hour >= self.max_orders_per_hour:
            self.violations_found += 1

            return self._create_violation(
                violation_type="ORDER_VELOCITY_EXCEEDED",
                message="Order submission rate too high (per hour)",
                details={
                    "orders_last_hour": orders_last_hour,
                    "max_orders_per_hour": self.max_orders_per_hour,
                },
                cl_ord_id=order.cl_ord_id,
                suggested_action="Wait before submitting more orders",
                requires_manual_review=True,
            )

        return None


class ComplianceEngine:
    """Main compliance engine that orchestrates rule checking."""

    def __init__(
        self, audit_logger: Optional[AuditLogger] = None, enable_blocking: bool = True
    ):
        """Initialize compliance engine.

        Args:
            audit_logger: Audit logger instance.
            enable_blocking: Whether to block orders that violate compliance.
        """
        self.audit_logger = audit_logger
        self.enable_blocking = enable_blocking

        # Rules registry
        self.rules: Dict[str, ComplianceRule] = {}

        # Violation history
        self.violations: List[ComplianceViolation] = []
        self.blocked_orders: Set[str] = set()

        # Statistics
        self.total_checks = 0
        self.total_violations = 0
        self.total_blocked = 0

        logger.info("Compliance engine initialized")

    def add_rule(self, rule: ComplianceRule):
        """Add a compliance rule."""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added compliance rule: {rule.rule_name} ({rule.rule_id})")

    def remove_rule(self, rule_id: str):
        """Remove a compliance rule."""
        if rule_id in self.rules:
            rule = self.rules.pop(rule_id)
            logger.info(f"Removed compliance rule: {rule.rule_name} ({rule_id})")

    def enable_rule(self, rule_id: str):
        """Enable a compliance rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            logger.info(f"Enabled compliance rule: {rule_id}")

    def disable_rule(self, rule_id: str):
        """Disable a compliance rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            logger.info(f"Disabled compliance rule: {rule_id}")

    async def check_order_compliance(
        self, order: NewOrderSingle, context: Optional[Dict[str, Any]] = None
    ) -> tuple[ComplianceResult, List[ComplianceViolation]]:
        """Check order against all compliance rules.

        Args:
            order: Order to check.
            context: Additional context for rule evaluation.

        Returns:
            Tuple of (result, violations).
        """
        self.total_checks += 1
        context = context or {}
        violations = []

        # Check each enabled rule
        for rule in self.rules.values():
            if not rule.enabled:
                continue

            try:
                violation = await rule.check_order(order, context)
                if violation:
                    violations.append(violation)
                    self.violations.append(violation)

                    # Log violation
                    if self.audit_logger:
                        await self.audit_logger.log_compliance_event(
                            event_type="COMPLIANCE_VIOLATION",
                            message=f"Compliance violation: {violation.message}",
                            compliance_flags=[violation.rule_id],
                            details=violation.to_dict(),
                            severity=AuditSeverity.COMPLIANCE,
                        )

            except Exception as e:
                logger.error(f"Error in compliance rule {rule.rule_id}: {e}")

                # Log rule error
                if self.audit_logger:
                    await self.audit_logger.log_compliance_event(
                        event_type="COMPLIANCE_RULE_ERROR",
                        message=f"Error in compliance rule {rule.rule_id}: {str(e)}",
                        compliance_flags=[rule.rule_id],
                        severity=AuditSeverity.ERROR,
                    )

        # Determine overall result
        if not violations:
            return ComplianceResult.PASS, violations

        # Check for auto-blocking violations
        auto_block_violations = [v for v in violations if v.auto_block]
        if auto_block_violations and self.enable_blocking:
            self.blocked_orders.add(order.cl_ord_id)
            self.total_blocked += 1
            return ComplianceResult.BLOCKED, violations

        # Check for critical violations
        critical_violations = [
            v for v in violations if v.severity == ViolationSeverity.CRITICAL
        ]
        if critical_violations:
            return ComplianceResult.FAIL, violations

        # Check for manual review requirements
        review_violations = [v for v in violations if v.requires_manual_review]
        if review_violations:
            return ComplianceResult.REQUIRES_APPROVAL, violations

        # Default to warning for any other violations
        self.total_violations += len(violations)
        return ComplianceResult.WARNING, violations

    async def check_execution_compliance(
        self, execution: ExecutionReport, context: Optional[Dict[str, Any]] = None
    ) -> tuple[ComplianceResult, List[ComplianceViolation]]:
        """Check execution against compliance rules.

        Args:
            execution: Execution report to check.
            context: Additional context.

        Returns:
            Tuple of (result, violations).
        """
        context = context or {}
        violations = []

        # Check each enabled rule
        for rule in self.rules.values():
            if not rule.enabled:
                continue

            try:
                violation = await rule.check_execution(execution, context)
                if violation:
                    violations.append(violation)
                    self.violations.append(violation)

            except Exception as e:
                logger.error(f"Error in execution compliance rule {rule.rule_id}: {e}")

        # Determine result
        if not violations:
            return ComplianceResult.PASS, violations

        critical_violations = [
            v for v in violations if v.severity == ViolationSeverity.CRITICAL
        ]
        if critical_violations:
            return ComplianceResult.FAIL, violations

        return ComplianceResult.WARNING, violations

    def get_compliance_stats(self) -> Dict[str, Any]:
        """Get compliance engine statistics."""
        stats = {
            "total_checks": self.total_checks,
            "total_violations": self.total_violations,
            "total_blocked": self.total_blocked,
            "active_rules": len([r for r in self.rules.values() if r.enabled]),
            "total_rules": len(self.rules),
            "violation_rate": (
                self.total_violations / self.total_checks * 100
                if self.total_checks > 0
                else 0
            ),
            "block_rate": (
                self.total_blocked / self.total_checks * 100
                if self.total_checks > 0
                else 0
            ),
        }

        # Add rule-specific stats
        stats["rules"] = {
            rule_id: rule.get_stats() for rule_id, rule in self.rules.items()
        }

        # Add recent violations
        recent_violations = [v.to_dict() for v in self.violations[-10:]]  # Last 10
        stats["recent_violations"] = recent_violations

        return stats

    def get_violations_for_order(self, cl_ord_id: str) -> List[ComplianceViolation]:
        """Get violations for a specific order."""
        return [v for v in self.violations if v.cl_ord_id == cl_ord_id]

    def is_order_blocked(self, cl_ord_id: str) -> bool:
        """Check if an order is blocked by compliance."""
        return cl_ord_id in self.blocked_orders

    def unblock_order(self, cl_ord_id: str, user_id: str, reason: str):
        """Manually unblock an order."""
        if cl_ord_id in self.blocked_orders:
            self.blocked_orders.remove(cl_ord_id)

            # Log unblock action
            if self.audit_logger:
                asyncio.create_task(
                    self.audit_logger.log_compliance_event(
                        event_type="ORDER_UNBLOCKED",
                        message=f"Order {cl_ord_id} unblocked by {user_id}: {reason}",
                        compliance_flags=["MANUAL_OVERRIDE"],
                        details={
                            "cl_ord_id": cl_ord_id,
                            "unblocked_by": user_id,
                            "reason": reason,
                        },
                        user_id=user_id,
                    )
                )

            logger.info(f"Order {cl_ord_id} unblocked by {user_id}: {reason}")
            return True

        return False
