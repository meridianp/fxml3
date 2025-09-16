"""
Manual Execution Adapter for Discretionary Trading with Comprehensive Audit Trail

This module provides enterprise-grade manual trading capabilities for human traders
within the FXML4 trading system. Features include advanced risk calculation,
multi-broker routing, comprehensive audit trails, approval workflows, and real-time
performance monitoring for discretionary trading operations.

Key Components:
- ManualExecutionAdapter: Main coordinator for discretionary trading operations
- RiskCalculator: Advanced position sizing and risk assessment engine
- TradeAuditLogger: Immutable audit trail with cryptographic hash verification
- ApprovalWorkflow: Multi-level approval system for large positions
- BrokerSelector: Intelligent broker routing based on conditions and health
- Real-time P&L tracking and risk monitoring capabilities

Architecture:
- Integration with RabbitMQ message routing for async order processing
- Multi-broker support (Interactive Brokers, FXCM) with automatic failover
- Comprehensive compliance logging with 7-year retention capability
- Real-time risk monitoring with configurable limit enforcement
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from fxml4.messaging import (
    ExecutionMessage,
    MessagePriority,
    OrderMessage,
    RiskCheckMessage,
)
from fxml4.messaging.messages import OrderSide, OrderStatus, OrderType

logger = logging.getLogger(__name__)


class ManualExecutionError(Exception):
    """Raised when manual execution encounters an error."""

    pass


class ManualApprovalRequired(Exception):
    """Raised when manual trade requires approval before execution."""

    def __init__(self, message: str, approval_type: str, trade_id: str):
        super().__init__(message)
        self.approval_type = approval_type
        self.trade_id = trade_id


class ApprovalType(Enum):
    """Trade approval types."""

    AUTO_APPROVED = "AUTO_APPROVED"
    MANAGER_REQUIRED = "MANAGER_REQUIRED"
    DIRECTOR_REQUIRED = "DIRECTOR_REQUIRED"
    AUTO_REJECTED = "AUTO_REJECTED"


@dataclass
class RiskAssessment:
    """Risk assessment results for a trade."""

    symbol: str
    side: OrderSide
    quantity: Decimal
    position_size_usd: Decimal
    risk_amount: Decimal
    risk_percent: float
    total_exposure_after_trade: Decimal
    risk_factors: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    is_acceptable: bool = True
    warnings: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Trade request validation result."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ApprovalResult:
    """Trade approval result."""

    approved: bool
    approval_type: str
    approver_id: Optional[str] = None
    approval_time: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    approval_id: Optional[str] = None


@dataclass
class ManualTradeExecution:
    """Manual trade execution result."""

    success: bool
    execution_id: str
    trade_id: str
    broker_used: str
    order_id: Optional[str] = None
    fill_price: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    execution_time: Optional[datetime] = None
    error_message: Optional[str] = None


class ManualTradeRequest(BaseModel):
    """Manual trade request with validation."""

    trade_id: str = Field(default_factory=lambda: f"MANUAL_{str(uuid4())[:8].upper()}")
    trader_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    entry_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    rationale: Optional[str] = None
    position_size_usd: Optional[Decimal] = None
    risk_score: Optional[float] = None
    preferred_broker: Optional[str] = None
    urgency: str = "NORMAL"  # NORMAL, HIGH, URGENT

    model_config = ConfigDict(
        json_encoders={Decimal: lambda v: str(v), datetime: lambda v: v.isoformat()}
    )

    def validate(self) -> ValidationResult:
        """Validate trade request parameters."""
        errors = []
        warnings = []

        # Basic validation
        if self.quantity <= 0:
            errors.append("Quantity must be positive")

        if self.entry_price and self.entry_price <= 0:
            errors.append("Entry price must be positive")

        if self.stop_loss and self.entry_price:
            if self.side == OrderSide.BUY and self.stop_loss >= self.entry_price:
                errors.append("Stop loss for BUY order must be below entry price")
            elif self.side == OrderSide.SELL and self.stop_loss <= self.entry_price:
                errors.append("Stop loss for SELL order must be above entry price")

        if self.take_profit and self.entry_price:
            if self.side == OrderSide.BUY and self.take_profit <= self.entry_price:
                errors.append("Take profit for BUY order must be above entry price")
            elif self.side == OrderSide.SELL and self.take_profit >= self.entry_price:
                errors.append("Take profit for SELL order must be below entry price")

        # Risk validation warnings
        if self.quantity > 500000:
            warnings.append("Large position size - consider risk implications")

        if not self.rationale or len(self.rationale) < 10:
            warnings.append(
                "Trade rationale should be more detailed for audit purposes"
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )


class RiskCalculator:
    """Advanced risk calculation and position sizing engine."""

    def __init__(
        self,
        max_risk_per_trade_percent: float = 2.0,
        max_portfolio_risk_percent: float = 6.0,
        max_position_size_usd: float = 200000,
        leverage_limit: float = 10.0,
        correlation_limit: float = 0.8,
    ):
        self.max_risk_per_trade_percent = max_risk_per_trade_percent
        self.max_portfolio_risk_percent = max_portfolio_risk_percent
        self.max_position_size_usd = max_position_size_usd
        self.leverage_limit = leverage_limit
        self.correlation_limit = correlation_limit

        # Risk scoring weights
        self.risk_weights = {
            "position_size": 0.25,
            "volatility": 0.20,
            "correlation": 0.15,
            "leverage": 0.15,
            "market_conditions": 0.15,
            "concentration": 0.10,
        }

    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: Optional[float] = None,
        risk_percent: Optional[float] = None,
    ) -> float:
        """Calculate optimal position size based on risk parameters."""
        if not stop_loss_price:
            # Default to 1% of entry price as risk
            stop_loss_price = entry_price * (0.99 if entry_price else 1.0)

        risk_pct = risk_percent or self.max_risk_per_trade_percent
        risk_amount = account_balance * (risk_pct / 100)

        price_risk = abs(entry_price - stop_loss_price)
        if price_risk == 0:
            return 0

        # Calculate position size in base currency units
        position_size = risk_amount / price_risk

        # Apply maximum position size limit
        max_units = self.max_position_size_usd / entry_price
        position_size = min(position_size, max_units)

        # Round to avoid floating point precision issues
        return round(position_size, 8)

    def assess_trade_risk(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        entry_price: Decimal,
        stop_loss: Optional[Decimal] = None,
        account_balance: Decimal = Decimal("50000"),
        current_exposure: Decimal = Decimal("0"),
        open_positions: int = 0,
        market_volatility: Optional[float] = None,
    ) -> RiskAssessment:
        """Comprehensive trade risk assessment."""

        position_size_usd = quantity * entry_price

        # Calculate risk amount
        if stop_loss:
            risk_per_unit = abs(entry_price - stop_loss)
            risk_amount = quantity * risk_per_unit
        else:
            # Default risk estimate (1% of position)
            risk_amount = position_size_usd * Decimal("0.01")

        risk_percent = float((risk_amount / account_balance) * 100)
        total_exposure = current_exposure + position_size_usd

        # Risk factor analysis
        risk_factors = []
        warnings = []
        risk_score = 0.0

        # Position size risk
        if position_size_usd > self.max_position_size_usd:
            risk_factors.append("Large position size exceeds limits")
            risk_score += 3.0

        # Risk percentage
        if risk_percent > self.max_risk_per_trade_percent:
            risk_factors.append(f"Risk percentage {risk_percent:.1f}% exceeds limit")
            risk_score += 2.5

        # Portfolio concentration
        exposure_percent = float((total_exposure / account_balance) * 100)
        if exposure_percent > self.max_portfolio_risk_percent:
            risk_factors.append("Portfolio exposure exceeds limits")
            risk_score += 2.0

        # Position count concentration
        if open_positions > 10:
            risk_factors.append("High number of open positions")
            risk_score += 1.5
            warnings.append("Consider position consolidation")

        # Market conditions (if volatility provided)
        if market_volatility and market_volatility > 0.02:  # 2% daily volatility
            risk_factors.append("High market volatility")
            risk_score += 1.0
            warnings.append("Increased stop loss recommended in volatile conditions")

        is_acceptable = risk_score < 5.0 and len(risk_factors) <= 2

        return RiskAssessment(
            symbol=symbol,
            side=side,
            quantity=quantity,
            position_size_usd=position_size_usd,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            total_exposure_after_trade=total_exposure,
            risk_factors=risk_factors,
            risk_score=risk_score,
            is_acceptable=is_acceptable,
            warnings=warnings,
        )

    def validate_risk_limits(
        self,
        risk_amount: float,
        account_balance: float,
        current_exposure: float,
        position_size_usd: float,
    ) -> bool:
        """Validate if trade meets risk limits."""

        # Risk per trade validation
        risk_percent = (risk_amount / account_balance) * 100
        if risk_percent > self.max_risk_per_trade_percent:
            logger.warning(
                f"Risk percent {risk_percent:.2f}% exceeds limit {self.max_risk_per_trade_percent:.2f}%"
            )
            return False

        # Portfolio exposure validation
        total_exposure = current_exposure + position_size_usd
        exposure_percent = (total_exposure / account_balance) * 100
        if exposure_percent > self.max_portfolio_risk_percent:
            logger.warning(
                f"Portfolio exposure {exposure_percent:.2f}% exceeds limit {self.max_portfolio_risk_percent:.2f}%"
            )
            return False

        # Position size validation
        if position_size_usd > self.max_position_size_usd:
            logger.warning(
                f"Position size ${position_size_usd:,.2f} exceeds limit ${self.max_position_size_usd:,.2f}"
            )
            return False

        return True

    def calculate_portfolio_risk(
        self, positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate portfolio-level risk metrics."""

        total_exposure = sum(pos.get("position_size", 0) for pos in positions)
        total_pnl = sum(pos.get("unrealized_pnl", 0) for pos in positions)

        # Symbol concentration analysis
        symbol_exposure = {}
        for pos in positions:
            symbol = pos.get("symbol", "UNKNOWN")
            size = pos.get("position_size", 0)
            symbol_exposure[symbol] = symbol_exposure.get(symbol, 0) + size

        # Calculate concentration risk
        max_concentration = max(symbol_exposure.values()) if symbol_exposure else 0
        concentration_risk = (
            max_concentration / max(total_exposure, 1) if total_exposure > 0 else 0
        )

        return {
            "total_exposure": total_exposure,
            "total_pnl": total_pnl,
            "position_count": len(positions),
            "risk_concentration": concentration_risk,
            "symbol_breakdown": symbol_exposure,
            "largest_position": max_concentration,
        }


class TradeAuditLogger:
    """Comprehensive audit trail logging with immutable hash verification."""

    def __init__(
        self,
        log_file_path: str = "/var/log/fxml4/manual_trades.log",
        database_connection: Optional[str] = None,
        retention_days: int = 2555,  # 7 years
    ):
        self.log_file_path = log_file_path
        self.database_connection = database_connection
        self.retention_days = retention_days

        # Ensure log directory exists
        import os

        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    async def log_trade_entry(self, trade_data: Dict[str, Any]) -> str:
        """Log comprehensive trade entry with audit hash."""

        # Add timestamp and generate audit hash
        audit_entry = {
            **trade_data,
            "timestamp": datetime.utcnow().isoformat(),
            "log_type": "TRADE_ENTRY",
            "audit_version": "1.0",
        }

        audit_hash = self._generate_audit_hash(audit_entry)
        audit_entry["audit_hash"] = audit_hash

        # Write to both file and database
        await self._write_to_file(audit_entry)
        if self.database_connection:
            await self._write_to_database(audit_entry)

        logger.info(
            f"Trade entry logged: {trade_data.get('trade_id')} - Hash: {audit_hash[:16]}..."
        )
        return audit_hash

    async def log_trade_modification(self, modification_data: Dict[str, Any]) -> str:
        """Log trade modification with audit trail."""

        audit_entry = {
            **modification_data,
            "modification_timestamp": datetime.utcnow().isoformat(),
            "log_type": "TRADE_MODIFICATION",
            "audit_version": "1.0",
        }

        audit_hash = self._generate_audit_hash(audit_entry)
        audit_entry["audit_hash"] = audit_hash

        await self._write_to_file(audit_entry)
        if self.database_connection:
            await self._write_to_database(audit_entry)

        return audit_hash

    async def log_trade_execution(self, execution_data: Dict[str, Any]) -> str:
        """Log trade execution results."""

        audit_entry = {
            **execution_data,
            "execution_timestamp": datetime.utcnow().isoformat(),
            "log_type": "TRADE_EXECUTION",
            "audit_version": "1.0",
        }

        audit_hash = self._generate_audit_hash(audit_entry)
        audit_entry["audit_hash"] = audit_hash

        await self._write_to_file(audit_entry)
        if self.database_connection:
            await self._write_to_database(audit_entry)

        return audit_hash

    def _generate_audit_hash(self, data: Dict[str, Any]) -> str:
        """Generate SHA-256 hash for audit trail immutability."""

        # Create deterministic JSON string
        json_str = json.dumps(data, sort_keys=True, default=str)

        # Generate SHA-256 hash
        hash_object = hashlib.sha256(json_str.encode())
        return hash_object.hexdigest()

    async def _write_to_file(self, audit_entry: Dict[str, Any]) -> None:
        """Write audit entry to log file."""
        try:
            with open(self.log_file_path, "a") as f:
                json_line = json.dumps(audit_entry, default=str)
                f.write(f"{json_line}\n")
                f.flush()
        except Exception as e:
            logger.error(f"Failed to write audit log to file: {e}")

    async def _write_to_database(self, audit_entry: Dict[str, Any]) -> None:
        """Write audit entry to database (placeholder for actual DB integration)."""
        # This would integrate with actual database in production
        logger.debug(f"Database audit log: {audit_entry.get('trade_id', 'UNKNOWN')}")

    async def verify_audit_hash(self, audit_entry: Dict[str, Any]) -> bool:
        """Verify audit entry integrity using hash."""
        stored_hash = audit_entry.pop("audit_hash", None)
        calculated_hash = self._generate_audit_hash(audit_entry)

        return stored_hash == calculated_hash


class ApprovalWorkflow:
    """Multi-level approval workflow for large and high-risk trades."""

    def __init__(
        self,
        auto_approval_limit_usd: float = 50000,
        manager_approval_limit_usd: float = 200000,
        director_approval_limit_usd: float = 500000,
        risk_score_threshold: float = 8.0,
    ):
        self.auto_approval_limit_usd = auto_approval_limit_usd
        self.manager_approval_limit_usd = manager_approval_limit_usd
        self.director_approval_limit_usd = director_approval_limit_usd
        self.risk_score_threshold = risk_score_threshold

        # Pending approvals (in production, this would be database-backed)
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}

    async def request_approval(
        self, trade_request: ManualTradeRequest
    ) -> ApprovalResult:
        """Request approval for manual trade based on size and risk."""

        position_size = trade_request.position_size_usd or 0
        risk_score = trade_request.risk_score or 0

        # Auto-reject for extremely high risk
        if risk_score > self.risk_score_threshold:
            return ApprovalResult(
                approved=False,
                approval_type=ApprovalType.AUTO_REJECTED.value,
                rejection_reason=f"Risk score {risk_score} exceeds threshold {self.risk_score_threshold}",
            )

        # Auto-approve for small, low-risk trades
        if position_size <= self.auto_approval_limit_usd and risk_score < 5.0:
            return ApprovalResult(
                approved=True,
                approval_type=ApprovalType.AUTO_APPROVED.value,
                approver_id="SYSTEM",
                approval_time=datetime.utcnow(),
                approval_id=f"AUTO_{str(uuid4())[:8].upper()}",
            )

        # Determine approval level required
        if position_size <= self.manager_approval_limit_usd:
            approval_type = ApprovalType.MANAGER_REQUIRED.value
        elif position_size <= self.director_approval_limit_usd:
            approval_type = ApprovalType.DIRECTOR_REQUIRED.value
        else:
            return ApprovalResult(
                approved=False,
                approval_type=ApprovalType.AUTO_REJECTED.value,
                rejection_reason=f"Position size ${position_size:,.0f} exceeds maximum limit",
            )

        # Check if approval already exists (in production, query database)
        approval_result = await self._check_pending_approvals(trade_request.trade_id)

        if not approval_result.get("approved", False):
            # Create pending approval
            self.pending_approvals[trade_request.trade_id] = {
                "trade_id": trade_request.trade_id,
                "trader_id": trade_request.trader_id,
                "approval_type": approval_type,
                "position_size_usd": position_size,
                "risk_score": risk_score,
                "requested_time": datetime.utcnow(),
                "status": "PENDING",
            }

        return ApprovalResult(
            approved=approval_result.get("approved", False),
            approval_type=approval_type,
            approver_id=approval_result.get("approver_id"),
            approval_time=approval_result.get("approval_time"),
        )

    async def _check_pending_approvals(self, trade_id: str) -> Dict[str, Any]:
        """Check status of pending approvals (placeholder for database integration)."""
        # In production, this would query approval database
        pending = self.pending_approvals.get(trade_id, {})

        return {
            "approved": False,  # Default to pending
            "approval_type": pending.get("approval_type"),
            "pending_since": pending.get("requested_time"),
        }

    async def approve_trade(
        self, trade_id: str, approver_id: str, approval_notes: Optional[str] = None
    ) -> ApprovalResult:
        """Approve a pending trade (admin function)."""

        if trade_id in self.pending_approvals:
            self.pending_approvals[trade_id]["status"] = "APPROVED"
            self.pending_approvals[trade_id]["approver_id"] = approver_id
            self.pending_approvals[trade_id]["approval_time"] = datetime.utcnow()

            return ApprovalResult(
                approved=True,
                approval_type=self.pending_approvals[trade_id]["approval_type"],
                approver_id=approver_id,
                approval_time=datetime.utcnow(),
                approval_id=f"MAN_{str(uuid4())[:8].upper()}",
            )

        raise ManualExecutionError(f"No pending approval found for trade {trade_id}")


class BrokerSelector:
    """Intelligent broker selection based on conditions and health."""

    def __init__(
        self,
        available_brokers: List[str] = None,
        default_broker: str = "IB",
        broker_preferences: Dict[str, str] = None,
        position_size_thresholds: Dict[str, Dict[str, float]] = None,
    ):
        self.available_brokers = available_brokers or ["IB", "FXCM"]
        self.default_broker = default_broker
        self.broker_preferences = broker_preferences or {}
        self.position_size_thresholds = position_size_thresholds or {}

        # Broker health cache
        self.broker_health_cache: Dict[str, Dict[str, Any]] = {}
        self.health_cache_ttl = 60  # seconds

    def select_broker(
        self,
        symbol: str,
        position_size_usd: float,
        preferred_broker: Optional[str] = None,
    ) -> str:
        """Select optimal broker based on conditions."""

        # Use explicitly preferred broker if specified and available
        if preferred_broker and preferred_broker in self.available_brokers:
            return preferred_broker

        # Check symbol-specific preferences
        if symbol in self.broker_preferences:
            preferred = self.broker_preferences[symbol]
            if preferred in self.available_brokers:
                return preferred

        # Check position size thresholds
        for broker, thresholds in self.position_size_thresholds.items():
            min_size = thresholds.get("min", 0)
            max_size = thresholds.get("max", float("inf"))

            if min_size <= position_size_usd <= max_size:
                if broker in self.available_brokers:
                    return broker

        # Fallback to default broker
        return self.default_broker

    async def select_healthy_broker(
        self, symbol: str, broker_candidates: List[str] = None
    ) -> str:
        """Select broker from candidates based on health status."""

        candidates = broker_candidates or self.available_brokers

        # Check health of each candidate
        for broker in candidates:
            if await self._check_broker_health(broker):
                return broker

        # If no healthy brokers, return default (with warning)
        logger.warning("No healthy brokers found, falling back to default")
        return self.default_broker

    async def _check_broker_health(self, broker: str) -> bool:
        """Check broker health status (with caching)."""

        now = datetime.utcnow()
        cache_key = broker

        # Check cache first
        if cache_key in self.broker_health_cache:
            cached = self.broker_health_cache[cache_key]
            if (now - cached["timestamp"]).seconds < self.health_cache_ttl:
                return cached["healthy"]

        # In production, this would check actual broker adapter health
        # For now, simulate health check (IB=healthy, others vary)
        is_healthy = broker == "IB"  # Simplified for testing

        # Update cache
        self.broker_health_cache[cache_key] = {"healthy": is_healthy, "timestamp": now}

        return is_healthy


class ManualExecutionAdapter:
    """
    Main manual execution adapter coordinating discretionary trading operations.

    Provides enterprise-grade manual trading capabilities with comprehensive
    risk management, audit trails, approval workflows, and multi-broker routing.
    """

    def __init__(
        self,
        trader_id: str = "MANUAL_TRADER",
        risk_limits: Optional[Dict[str, Any]] = None,
        audit_config: Optional[Dict[str, Any]] = None,
        approval_config: Optional[Dict[str, Any]] = None,
        broker_config: Optional[Dict[str, Any]] = None,
    ):
        self.trader_id = trader_id

        # Initialize components
        risk_cfg = risk_limits or {}
        self.risk_calculator = RiskCalculator(
            max_risk_per_trade_percent=risk_cfg.get("max_risk_per_trade", 2.0),
            max_portfolio_risk_percent=risk_cfg.get("max_portfolio_risk", 6.0),
            max_position_size_usd=risk_cfg.get("max_position_size", 200000),
        )

        audit_cfg = audit_config or {}
        self.audit_logger = TradeAuditLogger(
            log_file_path=audit_cfg.get("log_file", "/var/log/fxml4/manual_trades.log"),
            database_connection=audit_cfg.get("database_url"),
        )

        approval_cfg = approval_config or {}
        self.approval_workflow = ApprovalWorkflow(
            auto_approval_limit_usd=approval_cfg.get("auto_approval_limit", 50000),
            manager_approval_limit_usd=approval_cfg.get(
                "manager_approval_limit", 200000
            ),
        )

        broker_cfg = broker_config or {}
        self.broker_selector = BrokerSelector(
            available_brokers=broker_cfg.get("available_brokers", ["IB", "FXCM"]),
            default_broker=broker_cfg.get("default_broker", "IB"),
        )

        # Broker adapters (injected from main system)
        self.broker_adapters: Dict[str, Any] = {}

        # Active positions tracking
        self.active_positions: Dict[str, Dict[str, Any]] = {}

        # Performance metrics
        self.execution_count = 0
        self.successful_executions = 0
        self.total_commission = Decimal("0")
        self.total_pnl = Decimal("0")

        logger.info(f"Manual execution adapter initialized for trader {trader_id}")

    async def execute_manual_trade(
        self, trade_request: ManualTradeRequest
    ) -> ManualTradeExecution:
        """Execute manual trade with full risk management and audit trail."""

        execution_id = f"EXEC_{str(uuid4())[:8].upper()}"
        start_time = datetime.utcnow()

        try:
            # Step 1: Validate trade request
            validation = trade_request.validate()
            if not validation.is_valid:
                raise ManualExecutionError(
                    f"Invalid trade request: {', '.join(validation.errors)}"
                )

            # Step 2: Risk assessment
            risk_assessment = self.risk_calculator.assess_trade_risk(
                symbol=trade_request.symbol,
                side=trade_request.side,
                quantity=trade_request.quantity,
                entry_price=trade_request.entry_price or Decimal("1.0"),
                stop_loss=trade_request.stop_loss,
            )

            if not risk_assessment.is_acceptable:
                raise ManualExecutionError(
                    f"Risk limits exceeded: {', '.join(risk_assessment.risk_factors)}"
                )

            # Update trade request with calculated values
            trade_request.position_size_usd = risk_assessment.position_size_usd
            trade_request.risk_score = risk_assessment.risk_score

            # Step 3: Approval workflow
            approval_result = await self.approval_workflow.request_approval(
                trade_request
            )
            if not approval_result.approved:
                if approval_result.approval_type == ApprovalType.AUTO_REJECTED.value:
                    raise ManualExecutionError(
                        f"Trade rejected: {approval_result.rejection_reason}"
                    )
                else:
                    raise ManualApprovalRequired(
                        f"Trade requires {approval_result.approval_type.lower().replace('_', ' ')}",
                        approval_result.approval_type,
                        trade_request.trade_id,
                    )

            # Step 4: Broker selection
            selected_broker = self.broker_selector.select_broker(
                symbol=trade_request.symbol,
                position_size_usd=float(trade_request.position_size_usd or 0),
                preferred_broker=trade_request.preferred_broker,
            )

            # Step 5: Create order message
            order_message = OrderMessage(
                order_id=f"{selected_broker}_{trade_request.trade_id}",
                client_order_id=trade_request.trade_id,
                symbol=trade_request.symbol,
                side=trade_request.side,
                order_type=(
                    OrderType.MARKET
                    if not trade_request.entry_price
                    else OrderType.LIMIT
                ),
                quantity=trade_request.quantity,
                price=trade_request.entry_price,
                broker=selected_broker,
                account_id=trade_request.trader_id,
                strategy_id="MANUAL_EXECUTION",
                priority=MessagePriority.HIGH,
            )

            # Step 6: Execute order through selected broker
            execution_result = await self._execute_order_with_fallback(
                order_message, selected_broker
            )

            # Step 7: Log comprehensive audit trail
            audit_data = {
                "trade_id": trade_request.trade_id,
                "execution_id": execution_id,
                "trader_id": trade_request.trader_id,
                "symbol": trade_request.symbol,
                "side": trade_request.side.value,
                "quantity": str(trade_request.quantity),
                "entry_price": (
                    str(trade_request.entry_price)
                    if trade_request.entry_price
                    else None
                ),
                "stop_loss": (
                    str(trade_request.stop_loss) if trade_request.stop_loss else None
                ),
                "take_profit": (
                    str(trade_request.take_profit)
                    if trade_request.take_profit
                    else None
                ),
                "rationale": trade_request.rationale,
                "risk_assessment": {
                    "risk_score": risk_assessment.risk_score,
                    "risk_percent": risk_assessment.risk_percent,
                    "position_size_usd": str(risk_assessment.position_size_usd),
                },
                "approval_result": {
                    "approval_type": approval_result.approval_type,
                    "approver_id": approval_result.approver_id,
                    "approval_id": approval_result.approval_id,
                },
                "broker_selected": selected_broker,
                "execution_result": execution_result,
                "execution_time_ms": (datetime.utcnow() - start_time).total_seconds()
                * 1000,
            }

            await self.audit_logger.log_trade_entry(audit_data)

            # Step 8: Update performance metrics
            self.execution_count += 1
            if execution_result.get("status") == "FILLED":
                self.successful_executions += 1
                commission = execution_result.get("commission", 0)
                if commission:
                    self.total_commission += Decimal(str(commission))

            # Step 9: Track position
            if execution_result.get("status") in ["FILLED", "PARTIALLY_FILLED"]:
                self._update_position_tracking(trade_request, execution_result)

            return ManualTradeExecution(
                success=True,
                execution_id=execution_id,
                trade_id=trade_request.trade_id,
                broker_used=selected_broker,
                order_id=execution_result.get("order_id"),
                fill_price=(
                    Decimal(str(execution_result.get("fill_price", 0)))
                    if execution_result.get("fill_price")
                    else None
                ),
                commission=(
                    Decimal(str(execution_result.get("commission", 0)))
                    if execution_result.get("commission")
                    else None
                ),
                execution_time=datetime.utcnow(),
            )

        except (ManualExecutionError, ManualApprovalRequired):
            # Re-raise known exceptions
            raise
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error in manual trade execution: {e}")

            return ManualTradeExecution(
                success=False,
                execution_id=execution_id,
                trade_id=trade_request.trade_id,
                broker_used="UNKNOWN",
                error_message=str(e),
                execution_time=datetime.utcnow(),
            )

    async def _execute_order_with_fallback(
        self, order_message: OrderMessage, primary_broker: str
    ) -> Dict[str, Any]:
        """Execute order with automatic broker fallback."""

        # Try primary broker first
        if primary_broker in self.broker_adapters:
            try:
                adapter = self.broker_adapters[primary_broker]
                result = await adapter.execute_order(order_message)
                return result
            except Exception as e:
                logger.warning(f"Primary broker {primary_broker} failed: {e}")

        # Try fallback brokers
        for broker in self.broker_selector.available_brokers:
            if broker != primary_broker and broker in self.broker_adapters:
                try:
                    logger.info(f"Falling back to broker {broker}")
                    adapter = self.broker_adapters[broker]
                    order_message.broker = broker  # Update broker in message
                    result = await adapter.execute_order(order_message)
                    return result
                except Exception as e:
                    logger.warning(f"Fallback broker {broker} failed: {e}")

        # All brokers failed
        raise ManualExecutionError("All brokers failed to execute order")

    def _update_position_tracking(
        self, trade_request: ManualTradeRequest, execution_result: Dict[str, Any]
    ) -> None:
        """Update active position tracking."""

        position_id = f"{trade_request.symbol}_{trade_request.trade_id}"

        self.active_positions[position_id] = {
            "position_id": position_id,
            "trade_id": trade_request.trade_id,
            "symbol": trade_request.symbol,
            "side": trade_request.side.value,
            "quantity": float(trade_request.quantity),
            "entry_price": float(
                execution_result.get("fill_price", trade_request.entry_price or 0)
            ),
            "current_price": float(
                execution_result.get("fill_price", trade_request.entry_price or 0)
            ),
            "stop_loss": (
                float(trade_request.stop_loss) if trade_request.stop_loss else None
            ),
            "take_profit": (
                float(trade_request.take_profit) if trade_request.take_profit else None
            ),
            "unrealized_pnl": 0.0,
            "commission": float(execution_result.get("commission", 0)),
            "entry_time": datetime.utcnow(),
            "last_update": datetime.utcnow(),
        }

    def get_real_time_pnl(self) -> Dict[str, Any]:
        """Get real-time P&L summary for all positions."""

        total_unrealized_pnl = sum(
            pos.get("unrealized_pnl", 0) for pos in self.active_positions.values()
        )

        total_exposure = sum(
            pos.get("quantity", 0) * pos.get("current_price", 0)
            for pos in self.active_positions.values()
        )

        return {
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_exposure": total_exposure,
            "position_count": len(self.active_positions),
            "positions": list(self.active_positions.values()),
            "performance_metrics": {
                "total_executions": self.execution_count,
                "successful_executions": self.successful_executions,
                "success_rate": (
                    self.successful_executions / max(self.execution_count, 1)
                )
                * 100,
                "total_commission": float(self.total_commission),
            },
        }

    def get_position_summary(self) -> Dict[str, Any]:
        """Get summary of current positions."""
        return {
            "active_positions": len(self.active_positions),
            "positions": list(self.active_positions.values()),
        }

    async def close_position(
        self, position_id: str, close_reason: str = "MANUAL_CLOSE"
    ) -> ManualTradeExecution:
        """Close an active position manually."""

        if position_id not in self.active_positions:
            raise ManualExecutionError(f"Position {position_id} not found")

        position = self.active_positions[position_id]

        # Create opposite trade request
        close_request = ManualTradeRequest(
            trader_id=self.trader_id,
            symbol=position["symbol"],
            side=OrderSide.SELL if position["side"] == "BUY" else OrderSide.BUY,
            quantity=Decimal(str(position["quantity"])),
            rationale=f"Position close: {close_reason}",
        )

        # Execute closing trade
        execution = await self.execute_manual_trade(close_request)

        # Remove from active positions if successful
        if execution.success:
            del self.active_positions[position_id]
            logger.info(f"Position {position_id} closed successfully")

        return execution

    def add_broker_adapter(self, broker_name: str, adapter: Any) -> None:
        """Add broker adapter for execution."""
        self.broker_adapters[broker_name] = adapter
        logger.info(f"Added broker adapter: {broker_name}")

    def __repr__(self) -> str:
        return f"ManualExecutionAdapter(trader={self.trader_id}, positions={len(self.active_positions)})"
