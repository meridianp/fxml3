"""
Advanced Risk Limit Enforcement System for FXML4 Phase 6.

This module provides comprehensive risk limit enforcement with immutable audit trails,
real-time monitoring, and integration with the Phase 6 compliance framework.

Features:
- Real-time risk limit monitoring and enforcement
- Immutable audit trail with cryptographic integrity
- Integration with Phase 5 broker routing and Phase 6 surveillance
- Multi-jurisdictional risk compliance
- Automated breach detection and remediation
- Position-level and portfolio-level risk controls
"""

import asyncio
import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from fxml4.api.auth.audit_logger import AuditEventType, auth_audit_logger
from fxml4.api.auth.database import get_db
from fxml4.brokers.enhanced_execution_engine import EnhancedExecutionEngine
from fxml4.compliance.reporting.enhanced_regulatory_engine import (
    enhanced_regulatory_reporting_engine,
)
from fxml4.config import get_config
from fxml4.core.logging import get_logger
from fxml4.risk_management.base import BaseRiskManager


class RiskLimitType(Enum):
    """Types of risk limits."""

    POSITION_SIZE = "position_size"
    PORTFOLIO_NOTIONAL = "portfolio_notional"
    DAILY_LOSS = "daily_loss"
    DRAWDOWN = "drawdown"
    CONCENTRATION = "concentration"
    LEVERAGE = "leverage"
    VAR = "value_at_risk"
    STRESS_TEST = "stress_test"
    LIQUIDITY = "liquidity"
    COUNTERPARTY = "counterparty"


class RiskLimitStatus(Enum):
    """Risk limit enforcement status."""

    COMPLIANT = "compliant"
    WARNING = "warning"  # Approaching limit
    BREACHED = "breached"  # Limit exceeded
    SUSPENDED = "suspended"  # Trading suspended due to breach


class RiskAction(Enum):
    """Actions taken when risk limits are breached."""

    ALERT_ONLY = "alert_only"
    BLOCK_NEW_POSITIONS = "block_new_positions"
    FORCE_REDUCE_POSITION = "force_reduce_position"
    SUSPEND_TRADING = "suspend_trading"
    EMERGENCY_LIQUIDATION = "emergency_liquidation"


@dataclass
class RiskLimit:
    """Risk limit configuration."""

    limit_id: str
    limit_type: RiskLimitType
    description: str
    threshold_value: float
    warning_level: float  # Percentage of threshold for warnings (0.0 to 1.0)
    currency: str
    applicable_symbols: List[str]  # Empty list means applies to all
    applicable_accounts: List[str]  # Empty list means applies to all
    enforcement_action: RiskAction
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)


@dataclass
class RiskLimitBreach:
    """Record of a risk limit breach."""

    breach_id: str
    limit_id: str
    breach_type: RiskLimitType
    detected_at: datetime
    current_value: float
    limit_value: float
    breach_magnitude: float  # How much over the limit (percentage)
    affected_positions: List[str]
    enforcement_action_taken: RiskAction
    remediation_deadline: Optional[datetime] = None
    remediation_completed: bool = False
    audit_trail_id: str = None

    def __post_init__(self):
        if self.audit_trail_id is None:
            self.audit_trail_id = str(uuid.uuid4())


@dataclass
class ImmutableAuditRecord:
    """Immutable audit record for risk enforcement actions."""

    record_id: str
    timestamp: datetime
    event_type: str
    risk_data: Dict[str, Any]
    enforcement_action: RiskAction
    system_state_hash: str
    previous_record_hash: Optional[str]
    cryptographic_signature: str
    chain_position: int
    verification_status: str = "unverified"

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class RiskMonitoringMetrics:
    """Real-time risk monitoring metrics."""

    total_portfolio_value: float
    total_notional_exposure: float
    daily_pnl: float
    unrealized_pnl: float
    max_drawdown: float
    current_var: float
    leverage_ratio: float
    concentration_risk_score: float
    liquidity_risk_score: float
    overall_risk_score: float
    last_updated: datetime


class AdvancedRiskLimitEnforcementEngine:
    """
    Advanced risk limit enforcement engine with immutable audit trails.

    Provides comprehensive risk monitoring, limit enforcement, and regulatory
    compliance with cryptographic audit trail integrity.
    """

    def __init__(self):
        """Initialize the advanced risk limit enforcement engine."""
        self.config = get_config()
        self.logger = get_logger(__name__)

        # Risk enforcement configuration
        self.enable_real_time_monitoring = self.config.get(
            "risk.enforcement.real_time_enabled", True
        )
        self.enable_immutable_audit = self.config.get(
            "risk.enforcement.immutable_audit", True
        )
        self.auto_enforcement_enabled = self.config.get(
            "risk.enforcement.auto_enforcement", True
        )

        # Cryptographic keys for audit trail
        self.audit_key = self.config.get(
            "risk.enforcement.audit_key", "default_audit_key_change_in_production"
        ).encode()

        # State management
        self.risk_limits: Dict[str, RiskLimit] = {}
        self.active_breaches: Dict[str, RiskLimitBreach] = {}
        self.audit_chain: List[ImmutableAuditRecord] = []
        self.current_metrics: Optional[RiskMonitoringMetrics] = None

        # Monitoring state
        self.monitoring_active = False
        self.last_monitoring_update = None
        self.enforcement_actions_taken = 0
        self.total_breaches_detected = 0

        # Integration with other systems
        self.execution_engine: Optional[EnhancedExecutionEngine] = None
        self.base_risk_manager: Optional[BaseRiskManager] = None

        # Initialize default risk limits from configuration
        self._initialize_default_risk_limits()

        # Background monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None

        self.logger.info("AdvancedRiskLimitEnforcementEngine initialized successfully")

    def _initialize_default_risk_limits(self):
        """Initialize default risk limits from configuration."""

        # Load risk limits from config/risk_limits.yaml
        risk_config = self.config.get("risk_limits", {})

        # Position limits
        position_limits = risk_config.get("position_limits", {})
        if position_limits:
            self.add_risk_limit(
                RiskLimit(
                    limit_id="max_portfolio_notional",
                    limit_type=RiskLimitType.PORTFOLIO_NOTIONAL,
                    description="Maximum total portfolio notional value",
                    threshold_value=float(
                        position_limits.get("max_portfolio_notional", 10000000)
                    ),
                    warning_level=0.85,
                    currency="USD",
                    applicable_symbols=[],
                    applicable_accounts=[],
                    enforcement_action=RiskAction.BLOCK_NEW_POSITIONS,
                )
            )

            self.add_risk_limit(
                RiskLimit(
                    limit_id="max_single_position",
                    limit_type=RiskLimitType.POSITION_SIZE,
                    description="Maximum single position notional value",
                    threshold_value=float(
                        position_limits.get("max_single_position_notional", 1000000)
                    ),
                    warning_level=0.90,
                    currency="USD",
                    applicable_symbols=[],
                    applicable_accounts=[],
                    enforcement_action=RiskAction.BLOCK_NEW_POSITIONS,
                )
            )

        # Loss limits
        loss_limits = risk_config.get("loss_limits", {})
        if loss_limits:
            self.add_risk_limit(
                RiskLimit(
                    limit_id="max_daily_loss",
                    limit_type=RiskLimitType.DAILY_LOSS,
                    description="Maximum daily loss limit",
                    threshold_value=float(loss_limits.get("max_daily_loss", 50000)),
                    warning_level=0.75,
                    currency="USD",
                    applicable_symbols=[],
                    applicable_accounts=[],
                    enforcement_action=RiskAction.SUSPEND_TRADING,
                )
            )

        # Create risk limits for major currency pairs
        major_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
        for pair in major_pairs:
            max_size = position_limits.get("max_position_size", {}).get(pair, 1000000)
            self.add_risk_limit(
                RiskLimit(
                    limit_id=f"max_position_{pair.lower()}",
                    limit_type=RiskLimitType.POSITION_SIZE,
                    description=f"Maximum position size for {pair}",
                    threshold_value=float(max_size),
                    warning_level=0.85,
                    currency="USD",
                    applicable_symbols=[pair],
                    applicable_accounts=[],
                    enforcement_action=RiskAction.BLOCK_NEW_POSITIONS,
                )
            )

        self.logger.info(f"Initialized {len(self.risk_limits)} default risk limits")

    def add_risk_limit(self, risk_limit: RiskLimit):
        """Add a new risk limit to the enforcement engine."""

        risk_limit.updated_at = datetime.now(timezone.utc)
        self.risk_limits[risk_limit.limit_id] = risk_limit

        # Create audit record for limit addition
        asyncio.create_task(
            self._create_audit_record(
                "risk_limit_added",
                {"limit_id": risk_limit.limit_id, "limit_config": asdict(risk_limit)},
                RiskAction.ALERT_ONLY,
            )
        )

        self.logger.info(f"Added risk limit: {risk_limit.limit_id}")

    def update_risk_limit(self, limit_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing risk limit."""

        if limit_id not in self.risk_limits:
            self.logger.warning(f"Risk limit not found: {limit_id}")
            return False

        risk_limit = self.risk_limits[limit_id]
        old_config = asdict(risk_limit)

        # Apply updates
        for key, value in updates.items():
            if hasattr(risk_limit, key):
                setattr(risk_limit, key, value)

        risk_limit.updated_at = datetime.now(timezone.utc)

        # Create audit record for limit update
        asyncio.create_task(
            self._create_audit_record(
                "risk_limit_updated",
                {
                    "limit_id": limit_id,
                    "old_config": old_config,
                    "new_config": asdict(risk_limit),
                    "updates_applied": updates,
                },
                RiskAction.ALERT_ONLY,
            )
        )

        self.logger.info(f"Updated risk limit: {limit_id}")
        return True

    def remove_risk_limit(self, limit_id: str) -> bool:
        """Remove a risk limit from the enforcement engine."""

        if limit_id not in self.risk_limits:
            self.logger.warning(f"Risk limit not found: {limit_id}")
            return False

        risk_limit = self.risk_limits[limit_id]
        del self.risk_limits[limit_id]

        # Create audit record for limit removal
        asyncio.create_task(
            self._create_audit_record(
                "risk_limit_removed",
                {"limit_id": limit_id, "removed_config": asdict(risk_limit)},
                RiskAction.ALERT_ONLY,
            )
        )

        self.logger.info(f"Removed risk limit: {limit_id}")
        return True

    async def check_risk_limits(
        self,
        position_data: Dict[str, Any],
        account_id: str,
        user_id: str,
    ) -> Tuple[bool, List[RiskLimitBreach]]:
        """
        Comprehensive risk limit check for a proposed trade or position change.

        Returns:
            Tuple of (is_compliant, list_of_breaches)
        """

        breaches = []

        # Calculate current risk metrics
        current_metrics = await self._calculate_risk_metrics(
            position_data, account_id, user_id
        )

        # Check each applicable risk limit
        for limit_id, risk_limit in self.risk_limits.items():
            if not risk_limit.is_active:
                continue

            # Check if limit applies to this account/symbol
            if not self._limit_applies_to_position(
                risk_limit, position_data, account_id
            ):
                continue

            # Perform specific limit checks
            breach = await self._check_specific_limit(
                risk_limit, current_metrics, position_data, account_id, user_id
            )

            if breach:
                breaches.append(breach)
                self.active_breaches[breach.breach_id] = breach
                self.total_breaches_detected += 1

                # Create audit record for breach detection
                await self._create_audit_record(
                    "risk_limit_breach_detected",
                    {
                        "breach_id": breach.breach_id,
                        "limit_id": limit_id,
                        "breach_details": asdict(breach),
                        "current_metrics": asdict(current_metrics),
                    },
                    breach.enforcement_action_taken,
                )

                # Execute enforcement action if auto-enforcement is enabled
                if self.auto_enforcement_enabled:
                    await self._execute_enforcement_action(
                        breach, position_data, account_id, user_id
                    )

        # Update current metrics
        self.current_metrics = current_metrics
        self.last_monitoring_update = datetime.now(timezone.utc)

        # Send to regulatory reporting if breaches detected
        if breaches:
            await self._report_breaches_to_regulatory_engine(breaches)

        is_compliant = len(breaches) == 0
        return is_compliant, breaches

    async def _calculate_risk_metrics(
        self,
        position_data: Dict[str, Any],
        account_id: str,
        user_id: str,
    ) -> RiskMonitoringMetrics:
        """Calculate comprehensive risk metrics for current positions."""

        # Get current positions from database
        async with get_db() as db:
            # Query current positions
            positions_query = text(
                """
                SELECT symbol, SUM(quantity) as net_quantity, AVG(entry_price) as avg_price
                FROM positions
                WHERE account_id = :account_id AND user_id = :user_id
                GROUP BY symbol
            """
            )

            positions_result = await db.execute(
                positions_query, {"account_id": account_id, "user_id": user_id}
            )
            positions = positions_result.fetchall()

            # Calculate daily P&L
            daily_pnl_query = text(
                """
                SELECT SUM(pnl) as daily_pnl
                FROM trades
                WHERE user_id = :user_id AND DATE(timestamp) = CURRENT_DATE
            """
            )

            pnl_result = await db.execute(daily_pnl_query, {"user_id": user_id})
            daily_pnl = pnl_result.scalar() or 0.0

        # Calculate portfolio metrics
        total_notional = 0.0
        total_portfolio_value = 100000.0  # Default account value
        concentration_scores = []

        for pos in positions:
            notional_value = abs(pos.net_quantity) * pos.avg_price
            total_notional += notional_value

            # Calculate concentration as percentage of portfolio
            concentration = (
                notional_value / total_portfolio_value
                if total_portfolio_value > 0
                else 0
            )
            concentration_scores.append(concentration)

        # Include new position in calculations
        if position_data:
            new_notional = position_data.get("quantity", 0) * position_data.get(
                "price", 0
            )
            total_notional += abs(new_notional)

        # Calculate risk scores
        leverage_ratio = (
            total_notional / total_portfolio_value if total_portfolio_value > 0 else 0
        )
        concentration_risk = max(concentration_scores) if concentration_scores else 0

        # Simplified VaR calculation (would be more sophisticated in production)
        var_estimate = total_notional * 0.015  # 1.5% daily VaR estimate

        # Overall risk score (0-1 scale)
        risk_factors = [
            min(leverage_ratio / 5.0, 1.0),  # Normalize leverage
            concentration_risk,
            min(abs(daily_pnl) / 10000.0, 1.0),  # Normalize daily P&L impact
        ]
        overall_risk_score = sum(risk_factors) / len(risk_factors)

        return RiskMonitoringMetrics(
            total_portfolio_value=total_portfolio_value,
            total_notional_exposure=total_notional,
            daily_pnl=daily_pnl,
            unrealized_pnl=0.0,  # Would calculate from current market prices
            max_drawdown=0.0,  # Would calculate from historical data
            current_var=var_estimate,
            leverage_ratio=leverage_ratio,
            concentration_risk_score=concentration_risk,
            liquidity_risk_score=0.1,  # Simplified - would analyze order book depth
            overall_risk_score=overall_risk_score,
            last_updated=datetime.now(timezone.utc),
        )

    def _limit_applies_to_position(
        self, risk_limit: RiskLimit, position_data: Dict[str, Any], account_id: str
    ) -> bool:
        """Check if a risk limit applies to the given position/account."""

        # Check account applicability
        if (
            risk_limit.applicable_accounts
            and account_id not in risk_limit.applicable_accounts
        ):
            return False

        # Check symbol applicability
        symbol = position_data.get("symbol", "")
        if (
            risk_limit.applicable_symbols
            and symbol not in risk_limit.applicable_symbols
        ):
            return False

        return True

    async def _check_specific_limit(
        self,
        risk_limit: RiskLimit,
        metrics: RiskMonitoringMetrics,
        position_data: Dict[str, Any],
        account_id: str,
        user_id: str,
    ) -> Optional[RiskLimitBreach]:
        """Check a specific risk limit against current metrics."""

        current_value = 0.0
        affected_positions = []

        # Get current value based on limit type
        if risk_limit.limit_type == RiskLimitType.PORTFOLIO_NOTIONAL:
            current_value = metrics.total_notional_exposure
            affected_positions = ["PORTFOLIO"]

        elif risk_limit.limit_type == RiskLimitType.POSITION_SIZE:
            # Check individual position sizes
            symbol = position_data.get("symbol", "")
            quantity = position_data.get("quantity", 0)
            price = position_data.get("price", 0)
            current_value = abs(quantity * price)
            affected_positions = [symbol] if symbol else []

        elif risk_limit.limit_type == RiskLimitType.DAILY_LOSS:
            current_value = abs(min(metrics.daily_pnl, 0))  # Only count losses
            affected_positions = ["DAILY_PNL"]

        elif risk_limit.limit_type == RiskLimitType.LEVERAGE:
            current_value = metrics.leverage_ratio
            affected_positions = ["PORTFOLIO"]

        elif risk_limit.limit_type == RiskLimitType.CONCENTRATION:
            current_value = metrics.concentration_risk_score
            affected_positions = ["CONCENTRATION"]

        elif risk_limit.limit_type == RiskLimitType.VAR:
            current_value = metrics.current_var
            affected_positions = ["VAR"]

        else:
            # For other limit types, return no breach for now
            return None

        # Check if limit is breached
        threshold = risk_limit.threshold_value
        warning_threshold = threshold * risk_limit.warning_level

        if current_value > threshold:
            # Limit breached
            breach_magnitude = ((current_value - threshold) / threshold) * 100

            breach = RiskLimitBreach(
                breach_id=f"breach_{int(datetime.now().timestamp()*1000)}",
                limit_id=risk_limit.limit_id,
                breach_type=risk_limit.limit_type,
                detected_at=datetime.now(timezone.utc),
                current_value=current_value,
                limit_value=threshold,
                breach_magnitude=breach_magnitude,
                affected_positions=affected_positions,
                enforcement_action_taken=risk_limit.enforcement_action,
                remediation_deadline=datetime.now(timezone.utc) + timedelta(hours=4),
            )

            return breach

        elif current_value > warning_threshold:
            # Warning level - create informational breach
            warning_magnitude = (
                (current_value - warning_threshold) / warning_threshold
            ) * 100

            breach = RiskLimitBreach(
                breach_id=f"warning_{int(datetime.now().timestamp()*1000)}",
                limit_id=risk_limit.limit_id,
                breach_type=risk_limit.limit_type,
                detected_at=datetime.now(timezone.utc),
                current_value=current_value,
                limit_value=warning_threshold,
                breach_magnitude=warning_magnitude,
                affected_positions=affected_positions,
                enforcement_action_taken=RiskAction.ALERT_ONLY,
                remediation_deadline=datetime.now(timezone.utc) + timedelta(hours=24),
            )

            return breach

        return None

    async def _execute_enforcement_action(
        self,
        breach: RiskLimitBreach,
        position_data: Dict[str, Any],
        account_id: str,
        user_id: str,
    ):
        """Execute the enforcement action for a risk limit breach."""

        action_taken = breach.enforcement_action_taken
        self.enforcement_actions_taken += 1

        # Create detailed action record
        action_details = {
            "breach_id": breach.breach_id,
            "action_type": action_taken.value,
            "position_data": position_data,
            "account_id": account_id,
            "user_id": user_id,
            "enforcement_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if action_taken == RiskAction.ALERT_ONLY:
            # Send alert to compliance and risk teams
            await self._send_risk_alert(breach, action_details)

        elif action_taken == RiskAction.BLOCK_NEW_POSITIONS:
            # Block new positions for this account/symbol
            await self._block_new_positions(breach, account_id, user_id)

        elif action_taken == RiskAction.FORCE_REDUCE_POSITION:
            # Initiate position reduction
            await self._initiate_position_reduction(
                breach, position_data, account_id, user_id
            )

        elif action_taken == RiskAction.SUSPEND_TRADING:
            # Suspend all trading for this account
            await self._suspend_account_trading(breach, account_id, user_id)

        elif action_taken == RiskAction.EMERGENCY_LIQUIDATION:
            # Emergency liquidation of positions
            await self._initiate_emergency_liquidation(breach, account_id, user_id)

        # Create immutable audit record for enforcement action
        await self._create_audit_record(
            "enforcement_action_executed", action_details, action_taken
        )

        self.logger.info(
            f"Executed enforcement action {action_taken.value} for breach {breach.breach_id}"
        )

    async def _create_audit_record(
        self,
        event_type: str,
        risk_data: Dict[str, Any],
        enforcement_action: RiskAction,
    ) -> ImmutableAuditRecord:
        """Create an immutable audit record for risk enforcement actions."""

        if not self.enable_immutable_audit:
            return None

        record_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        # Calculate system state hash
        system_state = {
            "active_limits": len(
                [limit for limit in self.risk_limits.values() if limit.is_active]
            ),
            "active_breaches": len(self.active_breaches),
            "total_enforcement_actions": self.enforcement_actions_taken,
            "monitoring_status": self.monitoring_active,
        }
        system_state_hash = hashlib.sha256(
            json.dumps(system_state, sort_keys=True).encode()
        ).hexdigest()

        # Get previous record hash for chaining
        previous_hash = None
        if self.audit_chain:
            previous_hash = self.audit_chain[-1].cryptographic_signature

        # Create cryptographic signature
        signature_data = {
            "record_id": record_id,
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
            "risk_data": risk_data,
            "system_state_hash": system_state_hash,
            "previous_hash": previous_hash,
            "chain_position": len(self.audit_chain),
        }

        signature_string = json.dumps(signature_data, sort_keys=True)
        cryptographic_signature = hmac.new(
            self.audit_key, signature_string.encode(), hashlib.sha512
        ).hexdigest()

        # Create audit record
        audit_record = ImmutableAuditRecord(
            record_id=record_id,
            timestamp=timestamp,
            event_type=event_type,
            risk_data=risk_data,
            enforcement_action=enforcement_action,
            system_state_hash=system_state_hash,
            previous_record_hash=previous_hash,
            cryptographic_signature=cryptographic_signature,
            chain_position=len(self.audit_chain),
        )

        # Add to audit chain
        self.audit_chain.append(audit_record)

        # Log to external audit system
        await auth_audit_logger.log_event(
            AuditEventType.RISK_ENFORCEMENT,
            user_id="system",
            details={
                "audit_record_id": record_id,
                "event_type": event_type,
                "enforcement_action": enforcement_action.value,
                "cryptographic_signature": cryptographic_signature,
                "chain_position": audit_record.chain_position,
            },
        )

        self.logger.info(f"Created immutable audit record: {record_id}")
        return audit_record

    async def verify_audit_trail_integrity(self) -> Dict[str, Any]:
        """Verify the cryptographic integrity of the audit trail."""

        if not self.enable_immutable_audit or not self.audit_chain:
            return {
                "status": "disabled_or_empty",
                "total_records": len(self.audit_chain),
                "verification_performed": False,
            }

        verification_results = {
            "total_records": len(self.audit_chain),
            "verified_records": 0,
            "integrity_violations": [],
            "chain_continuity": True,
            "last_verification": datetime.now(timezone.utc).isoformat(),
        }

        previous_signature = None

        for i, record in enumerate(self.audit_chain):
            # Verify chain continuity
            if record.previous_record_hash != previous_signature:
                verification_results["integrity_violations"].append(
                    {
                        "record_id": record.record_id,
                        "violation_type": "chain_discontinuity",
                        "expected_previous_hash": previous_signature,
                        "actual_previous_hash": record.previous_record_hash,
                    }
                )
                verification_results["chain_continuity"] = False

            # Verify signature
            signature_data = {
                "record_id": record.record_id,
                "timestamp": record.timestamp.isoformat(),
                "event_type": record.event_type,
                "risk_data": record.risk_data,
                "system_state_hash": record.system_state_hash,
                "previous_hash": record.previous_record_hash,
                "chain_position": record.chain_position,
            }

            signature_string = json.dumps(signature_data, sort_keys=True)
            expected_signature = hmac.new(
                self.audit_key, signature_string.encode(), hashlib.sha512
            ).hexdigest()

            if expected_signature == record.cryptographic_signature:
                verification_results["verified_records"] += 1
                record.verification_status = "verified"
            else:
                verification_results["integrity_violations"].append(
                    {
                        "record_id": record.record_id,
                        "violation_type": "signature_mismatch",
                        "expected_signature": expected_signature,
                        "actual_signature": record.cryptographic_signature,
                    }
                )
                record.verification_status = "compromised"

            previous_signature = record.cryptographic_signature

        # Calculate integrity percentage
        verification_results["integrity_percentage"] = (
            verification_results["verified_records"]
            / verification_results["total_records"]
            * 100
            if verification_results["total_records"] > 0
            else 100
        )

        self.logger.info(
            f"Audit trail verification complete: {verification_results['integrity_percentage']:.1f}% integrity"
        )

        return verification_results

    async def start_real_time_monitoring(self):
        """Start real-time risk monitoring."""

        if self.monitoring_active:
            self.logger.warning("Real-time monitoring is already active")
            return

        if not self.enable_real_time_monitoring:
            self.logger.info("Real-time monitoring is disabled in configuration")
            return

        self.monitoring_active = True

        # Start background monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        await self._create_audit_record(
            "monitoring_started",
            {
                "monitoring_enabled": True,
                "start_time": datetime.now(timezone.utc).isoformat(),
            },
            RiskAction.ALERT_ONLY,
        )

        self.logger.info("Real-time risk monitoring started")

    async def stop_real_time_monitoring(self):
        """Stop real-time risk monitoring."""

        self.monitoring_active = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

        await self._create_audit_record(
            "monitoring_stopped",
            {
                "monitoring_enabled": False,
                "stop_time": datetime.now(timezone.utc).isoformat(),
            },
            RiskAction.ALERT_ONLY,
        )

        self.logger.info("Real-time risk monitoring stopped")

    async def _monitoring_loop(self):
        """Main real-time monitoring loop."""

        while self.monitoring_active:
            try:
                # Check all active accounts for risk limit compliance
                async with get_db() as db:
                    # Get active accounts
                    accounts_query = text(
                        """
                        SELECT DISTINCT account_id, user_id
                        FROM positions
                        WHERE quantity != 0
                    """
                    )

                    accounts_result = await db.execute(accounts_query)
                    active_accounts = accounts_result.fetchall()

                # Monitor each active account
                for account in active_accounts:
                    try:
                        # Get current position data for account
                        position_data = await self._get_current_position_data(
                            account.account_id, account.user_id
                        )

                        # Check risk limits
                        is_compliant, breaches = await self.check_risk_limits(
                            position_data, account.account_id, account.user_id
                        )

                        if not is_compliant:
                            self.logger.warning(
                                f"Risk limit breaches detected for account {account.account_id}: "
                                f"{len(breaches)} breaches"
                            )

                    except Exception as e:
                        self.logger.error(
                            f"Error monitoring account {account.account_id}: {e}"
                        )

                # Update monitoring timestamp
                self.last_monitoring_update = datetime.now(timezone.utc)

                # Wait before next check (default: 30 seconds)
                monitoring_interval = self.config.get(
                    "risk.enforcement.monitoring_interval_seconds", 30
                )
                await asyncio.sleep(monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def get_risk_enforcement_statistics(self) -> Dict[str, Any]:
        """Get comprehensive risk enforcement statistics."""

        # Active limits breakdown
        active_limits = [
            limit for limit in self.risk_limits.values() if limit.is_active
        ]
        limits_by_type = {}
        for limit in active_limits:
            limit_type = limit.limit_type.value
            limits_by_type[limit_type] = limits_by_type.get(limit_type, 0) + 1

        # Breaches breakdown
        breaches_by_type = {}
        for breach in self.active_breaches.values():
            breach_type = breach.breach_type.value
            breaches_by_type[breach_type] = breaches_by_type.get(breach_type, 0) + 1

        return {
            "monitoring_status": {
                "is_active": self.monitoring_active,
                "last_update": (
                    self.last_monitoring_update.isoformat()
                    if self.last_monitoring_update
                    else None
                ),
                "auto_enforcement_enabled": self.auto_enforcement_enabled,
            },
            "risk_limits": {
                "total_limits": len(self.risk_limits),
                "active_limits": len(active_limits),
                "limits_by_type": limits_by_type,
            },
            "enforcement_metrics": {
                "total_breaches_detected": self.total_breaches_detected,
                "active_breaches": len(self.active_breaches),
                "enforcement_actions_taken": self.enforcement_actions_taken,
                "breaches_by_type": breaches_by_type,
            },
            "audit_trail": {
                "total_records": len(self.audit_chain),
                "immutable_audit_enabled": self.enable_immutable_audit,
                "last_audit_record": (
                    self.audit_chain[-1].timestamp.isoformat()
                    if self.audit_chain
                    else None
                ),
            },
            "current_metrics": (
                asdict(self.current_metrics) if self.current_metrics else None
            ),
        }

    # Integration methods
    def set_execution_engine(self, execution_engine: EnhancedExecutionEngine):
        """Set the execution engine for enforcement actions."""
        self.execution_engine = execution_engine
        self.logger.info("Execution engine set for risk enforcement actions")

    def set_base_risk_manager(self, risk_manager: BaseRiskManager):
        """Set the base risk manager for integration."""
        self.base_risk_manager = risk_manager
        self.logger.info("Base risk manager set for enhanced integration")

    # Placeholder enforcement action methods (would be implemented in production)
    async def _send_risk_alert(
        self, breach: RiskLimitBreach, action_details: Dict[str, Any]
    ):
        """Send risk alert to compliance team."""
        self.logger.warning(
            f"RISK ALERT: {breach.breach_type.value} breach detected - {breach.breach_id}"
        )

    async def _block_new_positions(
        self, breach: RiskLimitBreach, account_id: str, user_id: str
    ):
        """Block new position opening for account."""
        self.logger.warning(
            f"BLOCKING NEW POSITIONS: Account {account_id} due to breach {breach.breach_id}"
        )

    async def _initiate_position_reduction(
        self,
        breach: RiskLimitBreach,
        position_data: Dict[str, Any],
        account_id: str,
        user_id: str,
    ):
        """Initiate position reduction."""
        self.logger.warning(
            f"INITIATING POSITION REDUCTION: Account {account_id} due to breach {breach.breach_id}"
        )

    async def _suspend_account_trading(
        self, breach: RiskLimitBreach, account_id: str, user_id: str
    ):
        """Suspend all trading for account."""
        self.logger.critical(
            f"SUSPENDING TRADING: Account {account_id} due to breach {breach.breach_id}"
        )

    async def _initiate_emergency_liquidation(
        self, breach: RiskLimitBreach, account_id: str, user_id: str
    ):
        """Initiate emergency liquidation."""
        self.logger.critical(
            f"EMERGENCY LIQUIDATION: Account {account_id} due to breach {breach.breach_id}"
        )

    async def _get_current_position_data(
        self, account_id: str, user_id: str
    ) -> Dict[str, Any]:
        """Get current position data for monitoring."""
        # Simplified implementation - would get real position data
        return {
            "account_id": account_id,
            "user_id": user_id,
            "total_positions": 1,
            "symbols": ["EURUSD"],
        }

    async def _report_breaches_to_regulatory_engine(
        self, breaches: List[RiskLimitBreach]
    ):
        """Report risk limit breaches to regulatory reporting engine."""

        for breach in breaches:
            # Create regulatory compliance event
            compliance_event = {
                "type": "risk_limit_breach",
                "breach_id": breach.breach_id,
                "breach_type": breach.breach_type.value,
                "severity": (
                    "high"
                    if breach.enforcement_action_taken != RiskAction.ALERT_ONLY
                    else "medium"
                ),
                "timestamp": breach.detected_at.isoformat(),
                "enforcement_action": breach.enforcement_action_taken.value,
                "affected_positions": breach.affected_positions,
                "breach_magnitude": breach.breach_magnitude,
            }

            # Send to enhanced regulatory reporting engine
            breach_alert = await enhanced_regulatory_reporting_engine.process_real_time_compliance_event(
                compliance_event
            )

            if breach_alert:
                self.logger.info(
                    f"Regulatory breach alert generated: {breach_alert.alert_id} for risk breach {breach.breach_id}"
                )


# Global risk limit enforcement engine instance
risk_limit_enforcement_engine = AdvancedRiskLimitEnforcementEngine()


async def get_risk_limit_enforcement_engine() -> AdvancedRiskLimitEnforcementEngine:
    """Get the global risk limit enforcement engine instance."""
    return risk_limit_enforcement_engine
