"""
Risk Limit Enforcement System for FXML4.

This module provides comprehensive real-time risk limit enforcement with position
and exposure monitoring, automatic limit enforcement, and risk management alerts.
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fxml4.api.auth.audit_logger import AuditEventType, auth_audit_logger
from fxml4.api.auth.database import get_db
from fxml4.api.auth.models import User
from fxml4.config import get_config
from fxml4.core.logging import get_logger
from fxml4.risk_management import RiskLimits, RiskMetrics, RiskViolation
from fxml4.trading.models import ExecutionReport, Position, Trade


class LimitType(Enum):
    """Types of risk limits."""

    POSITION_SIZE = "position_size"  # Maximum position size per instrument
    PORTFOLIO_EXPOSURE = "portfolio_exposure"  # Maximum total portfolio exposure
    DAILY_LOSS = "daily_loss"  # Maximum daily loss
    DRAWDOWN = "drawdown"  # Maximum drawdown from peak
    LEVERAGE = "leverage"  # Maximum leverage ratio
    CONCENTRATION = "concentration"  # Maximum concentration per instrument
    CURRENCY_EXPOSURE = "currency_exposure"  # Maximum exposure per currency
    CORRELATION_LIMIT = "correlation_limit"  # Maximum correlated position limit
    VAR_LIMIT = "var_limit"  # Value at Risk limit
    POSITION_COUNT = "position_count"  # Maximum number of open positions


class ViolationSeverity(Enum):
    """Risk violation severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EnforcementAction(Enum):
    """Enforcement actions for limit violations."""

    ALERT_ONLY = "alert_only"  # Generate alert, no automatic action
    BLOCK_NEW_TRADES = "block_new_trades"  # Prevent new trades in same direction
    REDUCE_POSITION = "reduce_position"  # Automatically reduce position
    CLOSE_POSITION = "close_position"  # Automatically close position
    EMERGENCY_STOP = "emergency_stop"  # Stop all trading activity


@dataclass
class RiskLimit:
    """Risk limit definition."""

    limit_id: str
    limit_type: LimitType
    threshold: float
    warning_threshold: Optional[float] = None  # Warning level (e.g., 80% of limit)
    currency: str = "USD"
    scope: str = "global"  # "global", "account", "user", "instrument"
    scope_value: Optional[str] = (
        None  # Specific value for scope (e.g., user_id, symbol)
    )
    enforcement_action: EnforcementAction = EnforcementAction.ALERT_ONLY
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
        if self.warning_threshold is None:
            self.warning_threshold = self.threshold * 0.8  # Default 80% warning


@dataclass
class PositionExposure:
    """Position exposure calculation."""

    symbol: str
    side: str  # "long" or "short"
    quantity: float
    avg_price: float
    current_price: float
    market_value: float  # quantity * current_price
    unrealized_pnl: float
    currency: str = "USD"
    account_id: Optional[str] = None
    user_id: Optional[str] = None

    @property
    def exposure_value(self) -> float:
        """Get absolute exposure value."""
        return abs(self.market_value)


@dataclass
class RiskExposure:
    """Comprehensive risk exposure snapshot."""

    timestamp: datetime
    total_exposure: float
    net_exposure: float  # Long exposure - Short exposure
    long_exposure: float
    short_exposure: float
    leverage: float
    daily_pnl: float
    unrealized_pnl: float
    position_count: int
    positions_by_symbol: Dict[str, PositionExposure]
    positions_by_currency: Dict[str, float]
    correlation_exposure: Dict[str, float]  # Exposure by correlation groups

    def get_concentration_ratio(self, symbol: str) -> float:
        """Get concentration ratio for a specific symbol."""
        if self.total_exposure == 0:
            return 0.0
        symbol_exposure = self.positions_by_symbol.get(
            symbol,
            PositionExposure(
                symbol=symbol,
                side="",
                quantity=0,
                avg_price=0,
                current_price=0,
                market_value=0,
                unrealized_pnl=0,
            ),
        ).exposure_value
        return symbol_exposure / self.total_exposure


@dataclass
class LimitViolation:
    """Risk limit violation record."""

    violation_id: str
    limit: RiskLimit
    current_value: float
    threshold: float
    severity: ViolationSeverity
    violation_time: datetime
    description: str
    risk_exposure: RiskExposure
    enforcement_action_taken: Optional[EnforcementAction] = None
    is_resolved: bool = False
    resolution_time: Optional[datetime] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RealTimeRiskMonitor:
    """
    Real-time risk monitoring and position exposure calculator.

    Continuously monitors positions and calculates various risk metrics
    in real-time for immediate limit enforcement.
    """

    def __init__(self):
        """Initialize real-time risk monitor."""
        self.config = get_config()
        self.logger = get_logger(__name__)

        # Current exposure state
        self.current_positions: Dict[str, PositionExposure] = {}
        self.current_exposure: Optional[RiskExposure] = None
        self.last_update_time: Optional[datetime] = None

        # Market data cache for pricing
        self.market_prices: Dict[str, float] = {}
        self.price_update_time: Dict[str, datetime] = {}

        # Performance tracking
        self.daily_high_water_mark: float = 0.0
        self.daily_pnl: float = 0.0
        self.session_start_time: datetime = datetime.now(timezone.utc)

        self.logger.info("RealTimeRiskMonitor initialized successfully")

    async def update_position(
        self, execution_report: ExecutionReport
    ) -> PositionExposure:
        """
        Update position from execution report.

        Args:
            execution_report: Trade execution report

        Returns:
            Updated position exposure
        """

        symbol = execution_report.symbol
        side = execution_report.side.lower()

        # Get current position or create new one
        position_key = f"{symbol}_{execution_report.account_id or 'default'}"
        current_pos = self.current_positions.get(position_key)

        if not current_pos:
            # New position
            current_pos = PositionExposure(
                symbol=symbol,
                side=side,
                quantity=0.0,
                avg_price=0.0,
                current_price=execution_report.price,
                market_value=0.0,
                unrealized_pnl=0.0,
                account_id=execution_report.account_id,
                user_id=execution_report.trader_id,
            )

        # Update position based on trade
        if execution_report.exec_type == "FILL":
            trade_qty = execution_report.quantity
            trade_price = execution_report.price

            if side == "buy":
                # Long position
                if current_pos.side == "short":
                    # Closing short position
                    if trade_qty >= abs(current_pos.quantity):
                        # Full close + potential reversal
                        remaining_qty = trade_qty - abs(current_pos.quantity)
                        current_pos.quantity = remaining_qty
                        current_pos.side = "long" if remaining_qty > 0 else ""
                        current_pos.avg_price = trade_price if remaining_qty > 0 else 0
                    else:
                        # Partial close
                        current_pos.quantity += trade_qty  # Reduces negative quantity
                        # Keep same avg_price for short position
                else:
                    # Adding to long or opening long
                    if current_pos.quantity == 0:
                        current_pos.quantity = trade_qty
                        current_pos.avg_price = trade_price
                        current_pos.side = "long"
                    else:
                        # Average price calculation
                        total_cost = (current_pos.quantity * current_pos.avg_price) + (
                            trade_qty * trade_price
                        )
                        current_pos.quantity += trade_qty
                        current_pos.avg_price = total_cost / current_pos.quantity

            elif side == "sell":
                # Short position or closing long
                if current_pos.side == "long":
                    # Closing long position
                    if trade_qty >= current_pos.quantity:
                        # Full close + potential reversal
                        remaining_qty = trade_qty - current_pos.quantity
                        current_pos.quantity = (
                            -remaining_qty if remaining_qty > 0 else 0
                        )
                        current_pos.side = "short" if remaining_qty > 0 else ""
                        current_pos.avg_price = trade_price if remaining_qty > 0 else 0
                    else:
                        # Partial close
                        current_pos.quantity -= trade_qty
                        # Keep same avg_price for long position
                else:
                    # Adding to short or opening short
                    if current_pos.quantity == 0:
                        current_pos.quantity = -trade_qty
                        current_pos.avg_price = trade_price
                        current_pos.side = "short"
                    else:
                        # Average price calculation for short
                        total_cost = (
                            abs(current_pos.quantity) * current_pos.avg_price
                        ) + (trade_qty * trade_price)
                        current_pos.quantity -= trade_qty
                        current_pos.avg_price = total_cost / abs(current_pos.quantity)

        # Update market value and P&L
        current_price = self.market_prices.get(symbol, execution_report.price)
        current_pos.current_price = current_price
        current_pos.market_value = current_pos.quantity * current_price

        # Calculate unrealized P&L
        if current_pos.quantity != 0:
            if current_pos.side == "long":
                current_pos.unrealized_pnl = (
                    current_price - current_pos.avg_price
                ) * current_pos.quantity
            else:  # short
                current_pos.unrealized_pnl = (
                    current_pos.avg_price - current_price
                ) * abs(current_pos.quantity)
        else:
            current_pos.unrealized_pnl = 0.0

        # Update positions cache
        if current_pos.quantity == 0:
            # Remove zero positions
            if position_key in self.current_positions:
                del self.current_positions[position_key]
        else:
            self.current_positions[position_key] = current_pos

        self.last_update_time = datetime.now(timezone.utc)

        self.logger.debug(
            f"Updated position for {symbol}: {current_pos.quantity} @ {current_pos.avg_price}"
        )
        return current_pos

    async def update_market_price(self, symbol: str, price: float):
        """Update market price for a symbol."""
        self.market_prices[symbol] = price
        self.price_update_time[symbol] = datetime.now(timezone.utc)

        # Recalculate P&L for positions in this symbol
        for pos_key, position in self.current_positions.items():
            if position.symbol == symbol:
                position.current_price = price
                position.market_value = position.quantity * price

                # Recalculate unrealized P&L
                if position.quantity != 0:
                    if position.side == "long":
                        position.unrealized_pnl = (
                            price - position.avg_price
                        ) * position.quantity
                    else:  # short
                        position.unrealized_pnl = (position.avg_price - price) * abs(
                            position.quantity
                        )

    async def calculate_risk_exposure(
        self, account_id: Optional[str] = None
    ) -> RiskExposure:
        """
        Calculate comprehensive risk exposure.

        Args:
            account_id: Optional account filter

        Returns:
            Complete risk exposure snapshot
        """

        # Filter positions by account if specified
        positions = self.current_positions
        if account_id:
            positions = {
                k: v for k, v in positions.items() if v.account_id == account_id
            }

        # Calculate aggregate exposures
        total_exposure = 0.0
        long_exposure = 0.0
        short_exposure = 0.0
        total_unrealized_pnl = 0.0

        positions_by_symbol = {}
        positions_by_currency = defaultdict(float)

        for position in positions.values():
            exposure_value = position.exposure_value
            total_exposure += exposure_value
            total_unrealized_pnl += position.unrealized_pnl

            if position.side == "long":
                long_exposure += exposure_value
            else:
                short_exposure += exposure_value

            # Group by symbol (sum if multiple accounts)
            if position.symbol in positions_by_symbol:
                existing = positions_by_symbol[position.symbol]
                # Combine positions for same symbol
                total_qty = existing.quantity + position.quantity
                if total_qty != 0:
                    combined_avg = (
                        (existing.quantity * existing.avg_price)
                        + (position.quantity * position.avg_price)
                    ) / total_qty
                    positions_by_symbol[position.symbol] = PositionExposure(
                        symbol=position.symbol,
                        side="long" if total_qty > 0 else "short",
                        quantity=total_qty,
                        avg_price=combined_avg,
                        current_price=position.current_price,
                        market_value=total_qty * position.current_price,
                        unrealized_pnl=existing.unrealized_pnl
                        + position.unrealized_pnl,
                        currency=position.currency,
                    )
                else:
                    # Net zero position
                    del positions_by_symbol[position.symbol]
            else:
                positions_by_symbol[position.symbol] = position

            # Group by currency
            positions_by_currency[position.currency] += exposure_value

        # Calculate net exposure and leverage
        net_exposure = long_exposure - short_exposure

        # Simple leverage calculation (could be enhanced with equity data)
        assumed_equity = 100000.0  # Default assumption, should be from account data
        leverage = total_exposure / assumed_equity if assumed_equity > 0 else 0.0

        # Calculate correlation exposure (simplified - would need correlation matrix)
        correlation_exposure = {}
        major_pairs = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        for group in ["major_pairs", "cross_pairs"]:
            group_exposure = 0.0
            for symbol, position in positions_by_symbol.items():
                if group == "major_pairs" and symbol in major_pairs:
                    group_exposure += position.exposure_value
                elif group == "cross_pairs" and symbol not in major_pairs:
                    group_exposure += position.exposure_value
            correlation_exposure[group] = group_exposure

        # Create risk exposure snapshot
        risk_exposure = RiskExposure(
            timestamp=datetime.now(timezone.utc),
            total_exposure=total_exposure,
            net_exposure=net_exposure,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            leverage=leverage,
            daily_pnl=self.daily_pnl,  # Would be calculated from daily trades
            unrealized_pnl=total_unrealized_pnl,
            position_count=len(positions_by_symbol),
            positions_by_symbol=positions_by_symbol,
            positions_by_currency=dict(positions_by_currency),
            correlation_exposure=correlation_exposure,
        )

        self.current_exposure = risk_exposure
        return risk_exposure


class RiskLimitEnforcer:
    """
    Risk limit enforcement engine with real-time monitoring and automatic actions.

    Features:
    - Real-time limit monitoring
    - Configurable enforcement actions
    - Multi-level alerting system
    - Automatic position management
    - Comprehensive violation tracking
    """

    def __init__(self):
        """Initialize risk limit enforcer."""
        self.config = get_config()
        self.logger = get_logger(__name__)

        # Risk monitor instance
        self.risk_monitor = RealTimeRiskMonitor()

        # Risk limits configuration
        self.active_limits: Dict[str, RiskLimit] = {}
        self.violation_history: List[LimitViolation] = []
        self.active_violations: Dict[str, LimitViolation] = {}

        # Alert callbacks
        self.alert_callbacks: List[Callable[[LimitViolation], None]] = []

        # Configuration
        self.enable_automatic_enforcement = self.config.get(
            "risk.enforcement.automatic_enabled", False
        )
        self.max_violations_per_session = self.config.get(
            "risk.enforcement.max_violations", 10
        )

        # Monitoring state
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None

        # Initialize default limits
        self._initialize_default_limits()

        self.logger.info("RiskLimitEnforcer initialized successfully")

    def _initialize_default_limits(self):
        """Initialize default risk limits."""

        default_limits = [
            RiskLimit(
                limit_id="global_position_size",
                limit_type=LimitType.POSITION_SIZE,
                threshold=500000.0,  # $500k max position size
                warning_threshold=400000.0,
                scope="global",
                enforcement_action=EnforcementAction.BLOCK_NEW_TRADES,
            ),
            RiskLimit(
                limit_id="global_portfolio_exposure",
                limit_type=LimitType.PORTFOLIO_EXPOSURE,
                threshold=2000000.0,  # $2M max portfolio exposure
                warning_threshold=1600000.0,
                scope="global",
                enforcement_action=EnforcementAction.BLOCK_NEW_TRADES,
            ),
            RiskLimit(
                limit_id="global_daily_loss",
                limit_type=LimitType.DAILY_LOSS,
                threshold=-20000.0,  # $20k max daily loss
                warning_threshold=-15000.0,
                scope="global",
                enforcement_action=EnforcementAction.CLOSE_POSITION,
            ),
            RiskLimit(
                limit_id="global_drawdown",
                limit_type=LimitType.DRAWDOWN,
                threshold=-50000.0,  # $50k max drawdown
                warning_threshold=-40000.0,
                scope="global",
                enforcement_action=EnforcementAction.REDUCE_POSITION,
            ),
            RiskLimit(
                limit_id="global_leverage",
                limit_type=LimitType.LEVERAGE,
                threshold=10.0,  # 10:1 max leverage
                warning_threshold=8.0,
                scope="global",
                enforcement_action=EnforcementAction.BLOCK_NEW_TRADES,
            ),
            RiskLimit(
                limit_id="global_concentration",
                limit_type=LimitType.CONCENTRATION,
                threshold=0.25,  # 25% max concentration per symbol
                warning_threshold=0.20,
                scope="global",
                enforcement_action=EnforcementAction.BLOCK_NEW_TRADES,
            ),
            RiskLimit(
                limit_id="global_position_count",
                limit_type=LimitType.POSITION_COUNT,
                threshold=20,  # Max 20 open positions
                warning_threshold=15,
                scope="global",
                enforcement_action=EnforcementAction.BLOCK_NEW_TRADES,
            ),
        ]

        for limit in default_limits:
            self.active_limits[limit.limit_id] = limit

        self.logger.info(f"Initialized {len(default_limits)} default risk limits")

    async def add_risk_limit(self, limit: RiskLimit):
        """Add or update a risk limit."""
        self.active_limits[limit.limit_id] = limit
        self.logger.info(
            f"Added risk limit: {limit.limit_id} ({limit.limit_type.value})"
        )

        # Log limit addition for audit
        auth_audit_logger.log_event(
            event_type=AuditEventType.SYSTEM_EVENT,
            username="system",
            details={
                "action": "add_risk_limit",
                "limit_id": limit.limit_id,
                "limit_type": limit.limit_type.value,
                "threshold": limit.threshold,
                "scope": limit.scope,
                "enforcement_action": limit.enforcement_action.value,
            },
        )

    async def remove_risk_limit(self, limit_id: str):
        """Remove a risk limit."""
        if limit_id in self.active_limits:
            del self.active_limits[limit_id]
            self.logger.info(f"Removed risk limit: {limit_id}")

            # Remove any active violations for this limit
            violations_to_remove = [
                v_id
                for v_id, violation in self.active_violations.items()
                if violation.limit.limit_id == limit_id
            ]
            for v_id in violations_to_remove:
                del self.active_violations[v_id]

    async def process_execution_report(self, execution_report: ExecutionReport):
        """
        Process execution report and check for limit violations.

        Args:
            execution_report: Trade execution report
        """

        # Update position in risk monitor
        position = await self.risk_monitor.update_position(execution_report)

        # Calculate updated risk exposure
        risk_exposure = await self.risk_monitor.calculate_risk_exposure()

        # Check all active limits
        violations = await self._check_all_limits(risk_exposure)

        # Process any violations
        for violation in violations:
            await self._handle_violation(violation)

        self.logger.debug(
            f"Processed execution report for {execution_report.symbol}: "
            f"{len(violations)} violations detected"
        )

    async def _check_all_limits(
        self, risk_exposure: RiskExposure
    ) -> List[LimitViolation]:
        """
        Check all active limits against current risk exposure.

        Args:
            risk_exposure: Current risk exposure snapshot

        Returns:
            List of limit violations
        """

        violations = []

        for limit in self.active_limits.values():
            if not limit.is_active:
                continue

            violation = await self._check_limit(limit, risk_exposure)
            if violation:
                violations.append(violation)

        return violations

    async def _check_limit(
        self, limit: RiskLimit, risk_exposure: RiskExposure
    ) -> Optional[LimitViolation]:
        """
        Check a specific limit against risk exposure.

        Args:
            limit: Risk limit to check
            risk_exposure: Current risk exposure

        Returns:
            Limit violation if threshold exceeded, None otherwise
        """

        current_value = None
        is_violated = False
        is_warning = False

        # Calculate current value based on limit type
        if limit.limit_type == LimitType.PORTFOLIO_EXPOSURE:
            current_value = risk_exposure.total_exposure
            is_violated = current_value > limit.threshold
            is_warning = (
                limit.warning_threshold and current_value > limit.warning_threshold
            )

        elif limit.limit_type == LimitType.POSITION_SIZE:
            # Check maximum individual position size
            max_position_size = 0.0
            for position in risk_exposure.positions_by_symbol.values():
                max_position_size = max(max_position_size, position.exposure_value)
            current_value = max_position_size
            is_violated = current_value > limit.threshold
            is_warning = (
                limit.warning_threshold and current_value > limit.warning_threshold
            )

        elif limit.limit_type == LimitType.DAILY_LOSS:
            current_value = risk_exposure.daily_pnl
            is_violated = current_value < limit.threshold  # Negative threshold for loss
            is_warning = (
                limit.warning_threshold and current_value < limit.warning_threshold
            )

        elif limit.limit_type == LimitType.LEVERAGE:
            current_value = risk_exposure.leverage
            is_violated = current_value > limit.threshold
            is_warning = (
                limit.warning_threshold and current_value > limit.warning_threshold
            )

        elif limit.limit_type == LimitType.CONCENTRATION:
            # Check maximum concentration per symbol
            max_concentration = 0.0
            for symbol in risk_exposure.positions_by_symbol:
                concentration = risk_exposure.get_concentration_ratio(symbol)
                max_concentration = max(max_concentration, concentration)
            current_value = max_concentration
            is_violated = current_value > limit.threshold
            is_warning = (
                limit.warning_threshold and current_value > limit.warning_threshold
            )

        elif limit.limit_type == LimitType.POSITION_COUNT:
            current_value = float(risk_exposure.position_count)
            is_violated = current_value > limit.threshold
            is_warning = (
                limit.warning_threshold and current_value > limit.warning_threshold
            )

        elif limit.limit_type == LimitType.CURRENCY_EXPOSURE:
            # Check exposure per currency (if scope specifies currency)
            if limit.scope == "currency" and limit.scope_value:
                current_value = risk_exposure.positions_by_currency.get(
                    limit.scope_value, 0.0
                )
                is_violated = current_value > limit.threshold
                is_warning = (
                    limit.warning_threshold and current_value > limit.warning_threshold
                )

        # Create violation if limit exceeded
        if is_violated or (is_warning and not is_violated):
            # Determine severity
            if is_violated:
                if current_value > limit.threshold * 1.5:  # 50% over limit
                    severity = ViolationSeverity.CRITICAL
                elif current_value > limit.threshold * 1.2:  # 20% over limit
                    severity = ViolationSeverity.HIGH
                else:
                    severity = ViolationSeverity.MEDIUM
            else:  # Warning level
                severity = ViolationSeverity.LOW

            violation_id = (
                f"{limit.limit_id}_{int(risk_exposure.timestamp.timestamp())}"
            )

            # Check if this violation already exists and is active
            if violation_id in self.active_violations:
                return None  # Don't create duplicate violation

            violation = LimitViolation(
                violation_id=violation_id,
                limit=limit,
                current_value=current_value,
                threshold=limit.threshold,
                severity=severity,
                violation_time=risk_exposure.timestamp,
                description=f"{limit.limit_type.value} limit {'exceeded' if is_violated else 'warning'}: "
                f"{current_value} {'>' if is_violated else 'approaching'} {limit.threshold}",
                risk_exposure=risk_exposure,
            )

            return violation

        return None

    async def _handle_violation(self, violation: LimitViolation):
        """
        Handle a limit violation with appropriate enforcement actions.

        Args:
            violation: Limit violation to handle
        """

        # Add to active violations
        self.active_violations[violation.violation_id] = violation
        self.violation_history.append(violation)

        # Log violation
        self.logger.warning(f"Risk limit violation: {violation.description}")

        # Generate alert
        await self._generate_violation_alert(violation)

        # Execute enforcement action if enabled
        if self.enable_automatic_enforcement and violation.severity in [
            ViolationSeverity.HIGH,
            ViolationSeverity.CRITICAL,
        ]:
            enforcement_action = await self._execute_enforcement_action(violation)
            violation.enforcement_action_taken = enforcement_action

        # Audit log violation
        auth_audit_logger.log_event(
            event_type=AuditEventType.RISK_VIOLATION,
            username="system",
            details={
                "violation_id": violation.violation_id,
                "limit_type": violation.limit.limit_type.value,
                "limit_id": violation.limit.limit_id,
                "current_value": violation.current_value,
                "threshold": violation.threshold,
                "severity": violation.severity.value,
                "description": violation.description,
                "enforcement_action": (
                    violation.enforcement_action_taken.value
                    if violation.enforcement_action_taken
                    else None
                ),
            },
        )

    async def _generate_violation_alert(self, violation: LimitViolation):
        """Generate alert for limit violation."""

        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                await callback(violation)
            except Exception as e:
                self.logger.error(f"Error in violation alert callback: {e}")

        self.logger.info(f"Generated alert for violation: {violation.violation_id}")

    async def _execute_enforcement_action(
        self, violation: LimitViolation
    ) -> EnforcementAction:
        """
        Execute enforcement action for violation.

        Args:
            violation: Limit violation

        Returns:
            Enforcement action taken
        """

        action = violation.limit.enforcement_action

        if action == EnforcementAction.ALERT_ONLY:
            # Already handled by alert generation
            pass

        elif action == EnforcementAction.BLOCK_NEW_TRADES:
            # Would integrate with order management system to block new orders
            self.logger.warning(
                f"ENFORCEMENT: Blocking new trades due to {violation.limit.limit_type.value} violation"
            )
            # TODO: Implement order blocking logic

        elif action == EnforcementAction.REDUCE_POSITION:
            # Automatically reduce positions
            self.logger.warning(
                f"ENFORCEMENT: Reducing positions due to {violation.limit.limit_type.value} violation"
            )
            await self._auto_reduce_positions(violation)

        elif action == EnforcementAction.CLOSE_POSITION:
            # Automatically close positions
            self.logger.warning(
                f"ENFORCEMENT: Closing positions due to {violation.limit.limit_type.value} violation"
            )
            await self._auto_close_positions(violation)

        elif action == EnforcementAction.EMERGENCY_STOP:
            # Emergency stop all trading
            self.logger.critical(
                f"ENFORCEMENT: EMERGENCY STOP triggered by {violation.limit.limit_type.value} violation"
            )
            await self._emergency_stop()

        return action

    async def _auto_reduce_positions(self, violation: LimitViolation):
        """Automatically reduce positions to address violation."""

        # This would integrate with the execution engine to send reduce orders
        # For now, log the action that would be taken
        risk_exposure = violation.risk_exposure

        if violation.limit.limit_type == LimitType.POSITION_SIZE:
            # Reduce largest position
            largest_position = max(
                risk_exposure.positions_by_symbol.values(),
                key=lambda p: p.exposure_value,
                default=None,
            )
            if largest_position:
                reduce_amount = largest_position.exposure_value - violation.threshold
                self.logger.info(
                    f"Would reduce {largest_position.symbol} position by ${reduce_amount:,.2f}"
                )

        elif violation.limit.limit_type == LimitType.PORTFOLIO_EXPOSURE:
            # Reduce all positions proportionally
            total_reduction = violation.current_value - violation.threshold
            for symbol, position in risk_exposure.positions_by_symbol.items():
                proportion = position.exposure_value / risk_exposure.total_exposure
                reduce_amount = total_reduction * proportion
                self.logger.info(
                    f"Would reduce {symbol} position by ${reduce_amount:,.2f}"
                )

    async def _auto_close_positions(self, violation: LimitViolation):
        """Automatically close positions to address violation."""

        if violation.limit.limit_type == LimitType.DAILY_LOSS:
            # Close losing positions first
            risk_exposure = violation.risk_exposure
            losing_positions = [
                pos
                for pos in risk_exposure.positions_by_symbol.values()
                if pos.unrealized_pnl < 0
            ]

            # Sort by largest loss first
            losing_positions.sort(key=lambda p: p.unrealized_pnl)

            for position in losing_positions:
                self.logger.info(
                    f"Would close losing position {position.symbol}: "
                    f"${position.unrealized_pnl:,.2f} P&L"
                )

    async def _emergency_stop(self):
        """Execute emergency stop procedure."""

        # This would:
        # 1. Stop all trading algorithms
        # 2. Cancel all pending orders
        # 3. Close all positions (market orders)
        # 4. Disable new order entry
        # 5. Alert risk management team

        self.logger.critical("EMERGENCY STOP: All trading activity suspended")

        # Send emergency alert
        auth_audit_logger.log_event(
            event_type=AuditEventType.EMERGENCY_STOP,
            username="system",
            details={
                "action": "emergency_stop_triggered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "Risk limit violation with EMERGENCY_STOP enforcement",
            },
        )

    async def resolve_violation(self, violation_id: str):
        """Mark a violation as resolved."""

        if violation_id in self.active_violations:
            violation = self.active_violations[violation_id]
            violation.is_resolved = True
            violation.resolution_time = datetime.now(timezone.utc)

            del self.active_violations[violation_id]

            self.logger.info(f"Resolved violation: {violation_id}")

    async def start_monitoring(self):
        """Start real-time risk monitoring."""

        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        self.logger.info("Started real-time risk monitoring")

    async def stop_monitoring(self):
        """Stop real-time risk monitoring."""

        self.is_monitoring = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Stopped real-time risk monitoring")

    async def _monitoring_loop(self):
        """Main monitoring loop for continuous risk checking."""

        while self.is_monitoring:
            try:
                # Calculate current risk exposure
                risk_exposure = await self.risk_monitor.calculate_risk_exposure()

                # Check all limits
                violations = await self._check_all_limits(risk_exposure)

                # Process new violations
                for violation in violations:
                    if violation.violation_id not in self.active_violations:
                        await self._handle_violation(violation)

                # Check for resolved violations
                resolved_violations = []
                for v_id, violation in self.active_violations.items():
                    # Re-check if violation still exists
                    current_violation = await self._check_limit(
                        violation.limit, risk_exposure
                    )
                    if not current_violation:
                        resolved_violations.append(v_id)

                # Mark resolved violations
                for v_id in resolved_violations:
                    await self.resolve_violation(v_id)

                # Sleep for monitoring interval
                await asyncio.sleep(5)  # Check every 5 seconds

            except Exception as e:
                self.logger.error(f"Error in risk monitoring loop: {e}")
                await asyncio.sleep(10)  # Wait longer on error

    async def get_current_risk_status(self) -> Dict[str, Any]:
        """Get current risk status summary."""

        current_exposure = await self.risk_monitor.calculate_risk_exposure()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "monitoring_active": self.is_monitoring,
            "total_exposure": current_exposure.total_exposure,
            "leverage": current_exposure.leverage,
            "position_count": current_exposure.position_count,
            "daily_pnl": current_exposure.daily_pnl,
            "unrealized_pnl": current_exposure.unrealized_pnl,
            "active_violations": len(self.active_violations),
            "active_limits": len(
                [l for l in self.active_limits.values() if l.is_active]
            ),
            "violation_history_count": len(self.violation_history),
            "violations": [
                {
                    "violation_id": v.violation_id,
                    "limit_type": v.limit.limit_type.value,
                    "severity": v.severity.value,
                    "current_value": v.current_value,
                    "threshold": v.threshold,
                    "violation_time": v.violation_time.isoformat(),
                }
                for v in self.active_violations.values()
            ],
        }

    def add_alert_callback(self, callback: Callable[[LimitViolation], None]):
        """Add callback function for violation alerts."""
        self.alert_callbacks.append(callback)


# Global risk limit enforcer instance
risk_limit_enforcer = RiskLimitEnforcer()


async def get_risk_limit_enforcer() -> RiskLimitEnforcer:
    """Get the global risk limit enforcer instance."""
    return risk_limit_enforcer
