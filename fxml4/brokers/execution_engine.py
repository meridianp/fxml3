"""Trade Execution Engine for FXML4.

This module provides the central trade execution engine that coordinates
order routing, execution, and lifecycle management across multiple broker
adapters with intelligent routing, risk management, and compliance checks.

CRITICAL MODULE: Core execution orchestrator for all trading operations.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from ..api.auth.trading_audit_logger import (
    TradingAuditContext,
    TradingEventType,
    audit_compliance_violation,
    audit_order_filled,
    audit_order_rejected,
    audit_order_submitted,
    audit_risk_violation,
    get_trading_audit_logger,
)
from ..core.exceptions import FXMLError
from ..core.logging import get_logger
from ..fix.messages.base import FIXMessage, OrdType, Side, TimeInForce
from ..fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest
from ..monitoring.metrics import performance_timer, track_execution_engine
from .adapters.base import BrokerAdapter, OrderInfo
from .adapters.base import OrderStatus as AdapterOrderStatus
from .adapters.manager import BrokerAdapterManager, get_manager
from .compliance.compliance_engine import ComplianceEngine
from .messaging.router import BrokerMetrics, MessageRouter, RoutingStrategy
from .risk.manager import RiskManager

logger = get_logger(__name__)


class ExecutionStatus(Enum):
    """Order execution status."""

    PENDING = "pending"
    ROUTING = "routing"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    WORKING = "working"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class ExecutionPriority(Enum):
    """Order execution priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ExecutionRequest:
    """Trade execution request."""

    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cl_ord_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order: NewOrderSingle = None
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    routing_strategy: RoutingStrategy = RoutingStrategy.BEST_EXECUTION
    preferred_brokers: Optional[List[str]] = None
    excluded_brokers: Optional[List[str]] = None
    max_retry_attempts: int = 3
    timeout_seconds: int = 300
    compliance_override: bool = False
    risk_override: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Trade execution result."""

    request_id: str
    order_id: str
    cl_ord_id: str
    status: ExecutionStatus
    broker_used: Optional[str] = None
    execution_reports: List[ExecutionReport] = field(default_factory=list)
    fill_quantity: float = 0.0
    avg_fill_price: Optional[float] = None
    commission: float = 0.0
    error_message: Optional[str] = None
    routing_attempts: int = 0
    execution_latency_ms: Optional[float] = None
    compliance_checks: Dict[str, bool] = field(default_factory=dict)
    risk_checks: Dict[str, bool] = field(default_factory=dict)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionStats:
    """Execution engine statistics."""

    total_orders: int = 0
    successful_orders: int = 0
    failed_orders: int = 0
    cancelled_orders: int = 0
    avg_latency_ms: float = 0.0
    fill_rate_percent: float = 0.0
    broker_distribution: Dict[str, int] = field(default_factory=dict)
    daily_volume: float = 0.0
    last_reset: datetime = field(default_factory=datetime.utcnow)


class TradeExecutionEngine:
    """Central trade execution engine for multi-broker routing.

    Coordinates order execution across multiple broker adapters with
    intelligent routing, risk management, and compliance validation.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize trade execution engine.

        Args:
            config: Engine configuration parameters.
        """
        self.config = config or {}

        # Core components
        self.adapter_manager: Optional[BrokerAdapterManager] = None
        self.message_router: Optional[MessageRouter] = None
        self.risk_manager: Optional[RiskManager] = None
        self.compliance_engine: Optional[ComplianceEngine] = None
        self.trading_audit_logger = get_trading_audit_logger()

        # Execution tracking
        self.pending_executions: Dict[str, ExecutionRequest] = {}
        self.active_executions: Dict[str, ExecutionResult] = {}
        self.completed_executions: List[ExecutionResult] = []
        self.execution_history: Dict[str, ExecutionResult] = {}

        # Performance tracking
        self.stats = ExecutionStats()
        self.broker_metrics: Dict[str, BrokerMetrics] = {}

        # Engine state
        self.is_running = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None

        # Configuration
        self.max_concurrent_executions = self.config.get(
            "max_concurrent_executions", 100
        )
        self.default_timeout = self.config.get("default_timeout_seconds", 300)
        self.enable_risk_checks = self.config.get("enable_risk_checks", True)
        self.enable_compliance_checks = self.config.get(
            "enable_compliance_checks", True
        )
        self.enable_performance_tracking = self.config.get(
            "enable_performance_tracking", True
        )
        self.history_retention_days = self.config.get("history_retention_days", 30)

        logger.info("Trade execution engine initialized")

    async def initialize(self) -> None:
        """Initialize the execution engine."""
        try:
            logger.info("Starting trade execution engine initialization")

            # Initialize adapter manager
            self.adapter_manager = await get_manager()

            # Initialize message router
            router_config = self.config.get("routing", {})
            self.message_router = MessageRouter(router_config)
            await self.message_router.initialize()

            # Initialize risk manager if enabled
            if self.enable_risk_checks:
                risk_config = self.config.get("risk_management", {})
                self.risk_manager = RiskManager(risk_config)
                await self.risk_manager.initialize()

            # Initialize compliance engine if enabled
            if self.enable_compliance_checks:
                compliance_config = self.config.get("compliance", {})
                self.compliance_engine = ComplianceEngine(compliance_config)
                await self.compliance_engine.initialize()

            # Start monitoring tasks
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())

            self.is_running = True

            # Audit log system startup
            context = TradingAuditContext(
                component="execution_engine",
                environment=self.config.get("environment", "production"),
                version=self.config.get("version", "1.0.0"),
            )

            asyncio.create_task(
                self.trading_audit_logger.log_system_event(
                    TradingEventType.SYSTEM_STARTUP,
                    "execution_engine",
                    "Trade execution engine initialized successfully",
                    details={
                        "max_concurrent_executions": self.max_concurrent_executions,
                        "enable_risk_checks": self.enable_risk_checks,
                        "enable_compliance_checks": self.enable_compliance_checks,
                        "default_timeout": self.default_timeout,
                    },
                    context=context,
                )
            )

            logger.info("Trade execution engine initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize trade execution engine: {e}")
            raise FXMLError(f"Execution engine initialization failed: {e}") from e

    async def shutdown(self) -> None:
        """Shutdown the execution engine."""
        try:
            logger.info("Shutting down trade execution engine")

            self.is_running = False

            # Cancel pending executions
            for request in self.pending_executions.values():
                await self._cancel_execution(request.order_id, "Engine shutdown")

            # Stop monitoring tasks
            if self.monitoring_task:
                self.monitoring_task.cancel()
            if self.cleanup_task:
                self.cleanup_task.cancel()

            # Wait for tasks to complete
            tasks = [t for t in [self.monitoring_task, self.cleanup_task] if t]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            # Shutdown components
            if self.message_router:
                await self.message_router.shutdown()
            if self.risk_manager:
                await self.risk_manager.shutdown()
            if self.compliance_engine:
                await self.compliance_engine.shutdown()

            # Audit log system shutdown
            context = TradingAuditContext(
                component="execution_engine",
                environment=self.config.get("environment", "production"),
                version=self.config.get("version", "1.0.0"),
            )

            asyncio.create_task(
                self.trading_audit_logger.log_system_event(
                    TradingEventType.SYSTEM_SHUTDOWN,
                    "execution_engine",
                    "Trade execution engine shutdown complete",
                    details={
                        "total_orders_processed": self.stats.total_orders,
                        "successful_orders": self.stats.successful_orders,
                        "failed_orders": self.stats.failed_orders,
                        "uptime_seconds": (
                            datetime.utcnow() - self.stats.last_reset
                        ).total_seconds(),
                    },
                    context=context,
                )
            )

            # Shutdown trading audit logger
            await self.trading_audit_logger.shutdown()

            logger.info("Trade execution engine shutdown complete")

        except Exception as e:
            logger.error(f"Error during execution engine shutdown: {e}")

    @track_execution_engine("submit_order")
    async def submit_order(
        self, execution_request: ExecutionRequest
    ) -> ExecutionResult:
        """Submit order for execution.

        Args:
            execution_request: Order execution request.

        Returns:
            ExecutionResult with initial status.
        """
        if not self.is_running:
            raise FXMLError("Execution engine is not running")

        # Validate request
        if not execution_request.order:
            raise FXMLError("Order is required in execution request")

        # Check concurrency limits
        if len(self.active_executions) >= self.max_concurrent_executions:
            raise FXMLError("Maximum concurrent executions reached")

        start_time = datetime.utcnow()

        try:
            with performance_timer("order_submission"):
                # Create execution result
                result = ExecutionResult(
                    request_id=execution_request.order_id,
                    order_id=execution_request.order_id,
                    cl_ord_id=execution_request.cl_ord_id,
                    status=ExecutionStatus.PENDING,
                    metadata=execution_request.metadata.copy(),
                )

                # Add to tracking
                self.pending_executions[execution_request.order_id] = execution_request
                self.active_executions[execution_request.order_id] = result

                # Log order submission audit event
                context = TradingAuditContext(
                    component="execution_engine",
                    user_id=execution_request.metadata.get("user_id"),
                    session_id=execution_request.metadata.get("session_id"),
                    strategy_id=execution_request.metadata.get("strategy_id"),
                    account_id=execution_request.metadata.get("account_id"),
                    environment=self.config.get("environment", "production"),
                )

                # Start execution process
                asyncio.create_task(self._execute_order(execution_request, result))

                # Audit log the order submission
                asyncio.create_task(
                    self.trading_audit_logger.log_order_event(
                        TradingEventType.ORDER_SUBMITTED,
                        execution_request.order,
                        broker_id=None,  # Not yet selected
                        context=context,
                    )
                )

                logger.info(
                    f"Order submitted for execution: {execution_request.order_id}"
                )
                return result

        except Exception as e:
            logger.error(f"Failed to submit order {execution_request.order_id}: {e}")
            raise FXMLError(f"Order submission failed: {e}") from e

    async def cancel_order(self, order_id: str, reason: str = "User requested") -> bool:
        """Cancel pending or active order.

        Args:
            order_id: Order ID to cancel.
            reason: Cancellation reason.

        Returns:
            True if cancellation initiated successfully.
        """
        try:
            return await self._cancel_execution(order_id, reason)
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_order_status(self, order_id: str) -> Optional[ExecutionResult]:
        """Get current order status.

        Args:
            order_id: Order ID to query.

        Returns:
            ExecutionResult or None if not found.
        """
        # Check active executions
        if order_id in self.active_executions:
            return self.active_executions[order_id]

        # Check execution history
        if order_id in self.execution_history:
            return self.execution_history[order_id]

        return None

    async def get_active_orders(self) -> List[ExecutionResult]:
        """Get all active orders.

        Returns:
            List of active execution results.
        """
        return list(self.active_executions.values())

    async def get_execution_stats(self) -> ExecutionStats:
        """Get execution engine statistics.

        Returns:
            Current execution statistics.
        """
        return self.stats

    async def _execute_order(
        self, request: ExecutionRequest, result: ExecutionResult
    ) -> None:
        """Execute order through routing and broker selection.

        Args:
            request: Execution request.
            result: Execution result to update.
        """
        start_time = datetime.utcnow()

        try:
            # Update status
            result.status = ExecutionStatus.ROUTING

            # Pre-execution checks
            if not await self._validate_execution_request(request, result):
                return

            # Risk management checks
            if self.enable_risk_checks and not await self._perform_risk_checks(
                request, result
            ):
                return

            # Compliance checks
            if (
                self.enable_compliance_checks
                and not await self._perform_compliance_checks(request, result)
            ):
                return

            # Route order to best broker
            selected_broker = await self._route_order(request, result)
            if not selected_broker:
                result.status = ExecutionStatus.FAILED
                result.error_message = "No suitable broker found"
                await self._complete_execution(request.order_id, result)
                return

            result.broker_used = selected_broker
            result.status = ExecutionStatus.SUBMITTED

            # Execute order
            success = await self._submit_to_broker(selected_broker, request, result)
            if not success:
                # Try failover brokers
                await self._attempt_failover(request, result)

        except Exception as e:
            logger.error(f"Error executing order {request.order_id}: {e}")
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            await self._complete_execution(request.order_id, result)

        # Calculate execution latency
        result.execution_latency_ms = (
            datetime.utcnow() - start_time
        ).total_seconds() * 1000

    async def _validate_execution_request(
        self, request: ExecutionRequest, result: ExecutionResult
    ) -> bool:
        """Validate execution request.

        Args:
            request: Execution request to validate.
            result: Execution result to update.

        Returns:
            True if valid, False otherwise.
        """
        try:
            order = request.order

            # Basic validation
            if not order.symbol or not order.side or not order.order_qty:
                result.status = ExecutionStatus.REJECTED
                result.error_message = "Missing required order fields"
                await self._complete_execution(request.order_id, result)
                return False

            # Quantity validation
            if order.order_qty <= 0:
                result.status = ExecutionStatus.REJECTED
                result.error_message = "Order quantity must be positive"
                await self._complete_execution(request.order_id, result)
                return False

            # Price validation for limit orders
            if order.ord_type == OrdType.LIMIT and (
                not order.price or order.price <= 0
            ):
                result.status = ExecutionStatus.REJECTED
                result.error_message = "Limit orders require positive price"
                await self._complete_execution(request.order_id, result)
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating execution request {request.order_id}: {e}")
            result.status = ExecutionStatus.FAILED
            result.error_message = f"Validation error: {e}"
            await self._complete_execution(request.order_id, result)
            return False

    async def _perform_risk_checks(
        self, request: ExecutionRequest, result: ExecutionResult
    ) -> bool:
        """Perform risk management checks.

        Args:
            request: Execution request.
            result: Execution result to update.

        Returns:
            True if checks pass, False otherwise.
        """
        if not self.risk_manager:
            return True

        try:
            # Perform risk checks
            risk_result = await self.risk_manager.check_order_risk(request.order)
            result.risk_checks = risk_result.checks

            if not risk_result.approved and not request.risk_override:
                result.status = ExecutionStatus.REJECTED
                result.error_message = f"Risk check failed: {risk_result.reason}"

                # Audit log risk violation
                context = TradingAuditContext(
                    component="risk_manager",
                    user_id=request.metadata.get("user_id"),
                    account_id=request.metadata.get("account_id"),
                    strategy_id=request.metadata.get("strategy_id"),
                    environment=self.config.get("environment", "production"),
                )

                asyncio.create_task(
                    audit_risk_violation(
                        risk_level=(
                            risk_result.risk_level
                            if hasattr(risk_result, "risk_level")
                            else "HIGH"
                        ),
                        violation_details={
                            "reason": risk_result.reason,
                            "checks": risk_result.checks,
                            "order_id": request.order_id,
                            "symbol": request.order.symbol,
                            "quantity": request.order.order_qty,
                            "order_type": (
                                request.order.ord_type.value
                                if request.order.ord_type
                                else None
                            ),
                        },
                        context=context,
                    )
                )

                await self._complete_execution(request.order_id, result)
                return False

            return True

        except Exception as e:
            logger.error(f"Error performing risk checks for {request.order_id}: {e}")
            if not request.risk_override:
                result.status = ExecutionStatus.FAILED
                result.error_message = f"Risk check error: {e}"
                await self._complete_execution(request.order_id, result)
                return False
            return True

    async def _perform_compliance_checks(
        self, request: ExecutionRequest, result: ExecutionResult
    ) -> bool:
        """Perform compliance checks.

        Args:
            request: Execution request.
            result: Execution result to update.

        Returns:
            True if checks pass, False otherwise.
        """
        if not self.compliance_engine:
            return True

        try:
            # Perform compliance checks
            compliance_result = await self.compliance_engine.validate_order(
                request.order
            )
            result.compliance_checks = compliance_result.checks

            if not compliance_result.approved and not request.compliance_override:
                result.status = ExecutionStatus.REJECTED
                result.error_message = (
                    f"Compliance check failed: {compliance_result.reason}"
                )

                # Audit log compliance violation
                context = TradingAuditContext(
                    component="compliance_engine",
                    user_id=request.metadata.get("user_id"),
                    account_id=request.metadata.get("account_id"),
                    strategy_id=request.metadata.get("strategy_id"),
                    environment=self.config.get("environment", "production"),
                )

                asyncio.create_task(
                    audit_compliance_violation(
                        compliance_flags=getattr(
                            compliance_result, "flags", ["COMPLIANCE_VIOLATION"]
                        ),
                        violation_details={
                            "reason": compliance_result.reason,
                            "checks": compliance_result.checks,
                            "order_id": request.order_id,
                            "symbol": request.order.symbol,
                            "quantity": request.order.order_qty,
                            "order_type": (
                                request.order.ord_type.value
                                if request.order.ord_type
                                else None
                            ),
                            "regulatory_framework": "MiFID II, ESMA",
                        },
                        context=context,
                    )
                )

                await self._complete_execution(request.order_id, result)
                return False

            return True

        except Exception as e:
            logger.error(
                f"Error performing compliance checks for {request.order_id}: {e}"
            )
            if not request.compliance_override:
                result.status = ExecutionStatus.FAILED
                result.error_message = f"Compliance check error: {e}"
                await self._complete_execution(request.order_id, result)
                return False
            return True

    async def _route_order(
        self, request: ExecutionRequest, result: ExecutionResult
    ) -> Optional[str]:
        """Route order to best available broker.

        Args:
            request: Execution request.
            result: Execution result to update.

        Returns:
            Selected broker name or None if no suitable broker found.
        """
        try:
            if not self.message_router:
                return None

            # Get available brokers
            available_brokers = await self.adapter_manager.list_active_adapters()
            if not available_brokers:
                return None

            # Apply broker preferences and exclusions
            eligible_brokers = self._filter_eligible_brokers(
                available_brokers, request.preferred_brokers, request.excluded_brokers
            )

            if not eligible_brokers:
                return None

            # Route using strategy
            selected_broker = await self.message_router.route_order(
                request.order, eligible_brokers, request.routing_strategy
            )

            result.routing_attempts += 1
            return selected_broker

        except Exception as e:
            logger.error(f"Error routing order {request.order_id}: {e}")
            return None

    def _filter_eligible_brokers(
        self,
        available_brokers: List[str],
        preferred: Optional[List[str]],
        excluded: Optional[List[str]],
    ) -> List[str]:
        """Filter brokers based on preferences and exclusions.

        Args:
            available_brokers: List of available broker names.
            preferred: Preferred brokers list (None for no preference).
            excluded: Excluded brokers list (None for no exclusions).

        Returns:
            Filtered list of eligible brokers.
        """
        eligible = available_brokers.copy()

        # Apply exclusions
        if excluded:
            eligible = [b for b in eligible if b not in excluded]

        # Apply preferences (if specified, only use preferred brokers)
        if preferred:
            eligible = [b for b in eligible if b in preferred]

        return eligible

    async def _submit_to_broker(
        self, broker_name: str, request: ExecutionRequest, result: ExecutionResult
    ) -> bool:
        """Submit order to selected broker.

        Args:
            broker_name: Name of broker to submit to.
            request: Execution request.
            result: Execution result to update.

        Returns:
            True if submission successful, False otherwise.
        """
        try:
            # Get broker adapter
            adapter = await self.adapter_manager.get_adapter(broker_name)
            if not adapter:
                return False

            # Submit order
            cl_ord_id = await adapter.submit_order(request.order)
            result.cl_ord_id = cl_ord_id
            result.status = ExecutionStatus.ACKNOWLEDGED

            # Audit log broker selection and order acknowledgment
            context = TradingAuditContext(
                component="broker_adapter",
                user_id=request.metadata.get("user_id"),
                account_id=request.metadata.get("account_id"),
                strategy_id=request.metadata.get("strategy_id"),
                environment=self.config.get("environment", "production"),
            )

            # Log broker selection
            asyncio.create_task(
                self.trading_audit_logger.log_broker_event(
                    TradingEventType.BROKER_SELECTED,
                    broker_name,
                    {
                        "order_id": request.order_id,
                        "symbol": request.order.symbol,
                        "routing_attempts": result.routing_attempts,
                        "routing_strategy": (
                            request.routing_strategy.value
                            if request.routing_strategy
                            else None
                        ),
                    },
                    order_id=request.order_id,
                    context=context,
                )
            )

            # Log order acknowledgment
            asyncio.create_task(
                self.trading_audit_logger.log_order_event(
                    TradingEventType.ORDER_ACKNOWLEDGED,
                    request.order,
                    broker_name,
                    context=context,
                )
            )

            # Set up execution monitoring
            asyncio.create_task(self._monitor_execution(broker_name, request, result))

            return True

        except Exception as e:
            logger.error(f"Error submitting order to broker {broker_name}: {e}")
            return False

    async def _monitor_execution(
        self, broker_name: str, request: ExecutionRequest, result: ExecutionResult
    ) -> None:
        """Monitor order execution on broker.

        Args:
            broker_name: Broker name.
            request: Execution request.
            result: Execution result to update.
        """
        try:
            adapter = await self.adapter_manager.get_adapter(broker_name)
            if not adapter:
                return

            timeout_time = datetime.utcnow() + timedelta(
                seconds=request.timeout_seconds
            )

            while datetime.utcnow() < timeout_time and result.status not in [
                ExecutionStatus.FILLED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.REJECTED,
                ExecutionStatus.FAILED,
            ]:
                # Check order status
                order_info = await adapter.get_order_status(result.cl_ord_id)
                if order_info:
                    await self._update_execution_status(order_info, result)

                await asyncio.sleep(1)  # Check every second

            # Handle timeout
            if result.status not in [
                ExecutionStatus.FILLED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.REJECTED,
                ExecutionStatus.FAILED,
            ]:
                result.status = ExecutionStatus.EXPIRED
                result.error_message = "Execution timeout"
                await self._complete_execution(request.order_id, result)

        except Exception as e:
            logger.error(f"Error monitoring execution for {request.order_id}: {e}")
            result.status = ExecutionStatus.FAILED
            result.error_message = f"Monitoring error: {e}"
            await self._complete_execution(request.order_id, result)

    async def _update_execution_status(
        self, order_info: OrderInfo, result: ExecutionResult
    ) -> None:
        """Update execution result based on broker order info.

        Args:
            order_info: Order information from broker.
            result: Execution result to update.
        """
        try:
            # Map adapter status to execution status
            status_mapping = {
                AdapterOrderStatus.WORKING: ExecutionStatus.WORKING,
                AdapterOrderStatus.PARTIALLY_FILLED: ExecutionStatus.PARTIALLY_FILLED,
                AdapterOrderStatus.FILLED: ExecutionStatus.FILLED,
                AdapterOrderStatus.CANCELLED: ExecutionStatus.CANCELLED,
                AdapterOrderStatus.REJECTED: ExecutionStatus.REJECTED,
                AdapterOrderStatus.EXPIRED: ExecutionStatus.EXPIRED,
            }

            if order_info.status in status_mapping:
                result.status = status_mapping[order_info.status]

            # Update fill information
            result.fill_quantity = order_info.total_filled_qty
            result.avg_fill_price = order_info.avg_fill_price

            # Add execution reports
            if order_info.last_execution:
                result.execution_reports.append(order_info.last_execution)

            # Audit log execution status updates
            context = TradingAuditContext(
                component="execution_monitor",
                environment=self.config.get("environment", "production"),
            )

            # Get the original request for context
            request = self.pending_executions.get(result.order_id)
            if request:
                context.user_id = request.metadata.get("user_id")
                context.account_id = request.metadata.get("account_id")
                context.strategy_id = request.metadata.get("strategy_id")

                # Create dummy order for audit logging (since we only have OrderInfo)
                dummy_order = NewOrderSingle(
                    cl_ord_id=result.cl_ord_id,
                    symbol=result.metadata.get("symbol") or "UNKNOWN",
                    side=Side.BUY,  # Would need to be stored in result metadata
                    order_qty=(
                        order_info.total_qty if hasattr(order_info, "total_qty") else 0
                    ),
                    ord_type=OrdType.MARKET,  # Default, should be from original order
                )

                # Map execution status to trading event type
                event_type_mapping = {
                    ExecutionStatus.WORKING: TradingEventType.ORDER_WORKING,
                    ExecutionStatus.PARTIALLY_FILLED: TradingEventType.ORDER_PARTIALLY_FILLED,
                    ExecutionStatus.FILLED: TradingEventType.ORDER_FILLED,
                    ExecutionStatus.CANCELLED: TradingEventType.ORDER_CANCELLED,
                    ExecutionStatus.REJECTED: TradingEventType.ORDER_REJECTED,
                    ExecutionStatus.EXPIRED: TradingEventType.ORDER_EXPIRED,
                }

                if result.status in event_type_mapping:
                    # Create execution report if we have fill information
                    exec_report = None
                    if order_info.last_execution:
                        exec_report = order_info.last_execution

                    asyncio.create_task(
                        self.trading_audit_logger.log_order_event(
                            event_type_mapping[result.status],
                            dummy_order,
                            broker_id=result.broker_used,
                            execution_report=exec_report,
                            context=context,
                        )
                    )

            # Complete execution if final status
            if result.status in [
                ExecutionStatus.FILLED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.REJECTED,
                ExecutionStatus.EXPIRED,
            ]:
                await self._complete_execution(result.order_id, result)

        except Exception as e:
            logger.error(f"Error updating execution status: {e}")

    async def _attempt_failover(
        self, request: ExecutionRequest, result: ExecutionResult
    ) -> None:
        """Attempt execution on failover brokers.

        Args:
            request: Execution request.
            result: Execution result to update.
        """
        try:
            max_attempts = request.max_retry_attempts

            while result.routing_attempts < max_attempts:
                # Try routing to different broker
                selected_broker = await self._route_order(request, result)
                if not selected_broker or selected_broker == result.broker_used:
                    break

                result.broker_used = selected_broker
                success = await self._submit_to_broker(selected_broker, request, result)
                if success:
                    return

                await asyncio.sleep(1)  # Brief delay between attempts

            # All attempts failed
            result.status = ExecutionStatus.FAILED
            result.error_message = "All broker attempts failed"
            await self._complete_execution(request.order_id, result)

        except Exception as e:
            logger.error(f"Error during failover for {request.order_id}: {e}")
            result.status = ExecutionStatus.FAILED
            result.error_message = f"Failover error: {e}"
            await self._complete_execution(request.order_id, result)

    async def _cancel_execution(self, order_id: str, reason: str) -> bool:
        """Cancel order execution.

        Args:
            order_id: Order ID to cancel.
            reason: Cancellation reason.

        Returns:
            True if cancellation successful.
        """
        try:
            # Remove from pending if not yet started
            if order_id in self.pending_executions:
                request = self.pending_executions.pop(order_id)

                if order_id in self.active_executions:
                    result = self.active_executions[order_id]
                    result.status = ExecutionStatus.CANCELLED
                    result.error_message = reason
                    await self._complete_execution(order_id, result)

                return True

            # Cancel active execution
            if order_id in self.active_executions:
                result = self.active_executions[order_id]

                # Send cancellation to broker if submitted
                if result.broker_used and result.cl_ord_id:
                    adapter = await self.adapter_manager.get_adapter(result.broker_used)
                    if adapter:
                        cancel_request = OrderCancelRequest(
                            cl_ord_id=result.cl_ord_id, orig_cl_ord_id=result.cl_ord_id
                        )
                        await adapter.cancel_order(cancel_request)

                result.status = ExecutionStatus.CANCELLED
                result.error_message = reason
                await self._complete_execution(order_id, result)

                return True

            return False

        except Exception as e:
            logger.error(f"Error cancelling execution {order_id}: {e}")
            return False

    async def _complete_execution(self, order_id: str, result: ExecutionResult) -> None:
        """Complete order execution and update statistics.

        Args:
            order_id: Order ID.
            result: Final execution result.
        """
        try:
            # Remove from active tracking
            if order_id in self.pending_executions:
                self.pending_executions.pop(order_id)

            if order_id in self.active_executions:
                self.active_executions.pop(order_id)

            # Set completion time
            result.completed_at = datetime.utcnow()

            # Add to history
            self.execution_history[order_id] = result
            self.completed_executions.append(result)

            # Update statistics
            await self._update_stats(result)

            logger.info(f"Execution completed: {order_id} -> {result.status.value}")

        except Exception as e:
            logger.error(f"Error completing execution {order_id}: {e}")

    async def _update_stats(self, result: ExecutionResult) -> None:
        """Update execution engine statistics.

        Args:
            result: Completed execution result.
        """
        try:
            self.stats.total_orders += 1

            if result.status == ExecutionStatus.FILLED:
                self.stats.successful_orders += 1
                if result.fill_quantity > 0:
                    self.stats.daily_volume += result.fill_quantity
            elif result.status == ExecutionStatus.CANCELLED:
                self.stats.cancelled_orders += 1
            else:
                self.stats.failed_orders += 1

            # Update broker distribution
            if result.broker_used:
                if result.broker_used not in self.stats.broker_distribution:
                    self.stats.broker_distribution[result.broker_used] = 0
                self.stats.broker_distribution[result.broker_used] += 1

            # Update latency
            if result.execution_latency_ms:
                current_avg = self.stats.avg_latency_ms
                total_orders = self.stats.total_orders
                self.stats.avg_latency_ms = (
                    current_avg * (total_orders - 1) + result.execution_latency_ms
                ) / total_orders

            # Update fill rate
            if self.stats.total_orders > 0:
                self.stats.fill_rate_percent = (
                    self.stats.successful_orders / self.stats.total_orders * 100
                )

        except Exception as e:
            logger.error(f"Error updating statistics: {e}")

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self.is_running:
            try:
                await self._update_broker_metrics()
                await self._check_execution_health()
                await asyncio.sleep(30)  # Monitor every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self.is_running:
            try:
                await self._cleanup_old_executions()
                await asyncio.sleep(3600)  # Cleanup every hour

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(3600)

    async def _update_broker_metrics(self) -> None:
        """Update broker performance metrics."""
        try:
            if not self.adapter_manager:
                return

            adapters = await self.adapter_manager.list_adapters()
            for adapter_name in adapters:
                adapter_info = await self.adapter_manager.get_adapter_info(adapter_name)
                if adapter_info:
                    # Update metrics from adapter info
                    # This would be implemented based on adapter interface
                    pass

        except Exception as e:
            logger.error(f"Error updating broker metrics: {e}")

    async def _check_execution_health(self) -> None:
        """Check execution engine health."""
        try:
            # Check for stuck executions
            stuck_threshold = timedelta(minutes=30)
            current_time = datetime.utcnow()

            for order_id, result in self.active_executions.items():
                if (
                    current_time - result.metadata.get("created_at", current_time)
                    > stuck_threshold
                ):
                    logger.warning(f"Potentially stuck execution detected: {order_id}")
                    # Could trigger alerts or automatic handling here

        except Exception as e:
            logger.error(f"Error checking execution health: {e}")

    async def _cleanup_old_executions(self) -> None:
        """Cleanup old execution records."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(
                days=self.history_retention_days
            )

            # Clean up completed executions
            self.completed_executions = [
                exec_result
                for exec_result in self.completed_executions
                if exec_result.completed_at and exec_result.completed_at > cutoff_time
            ]

            # Clean up execution history
            to_remove = [
                order_id
                for order_id, result in self.execution_history.items()
                if result.completed_at and result.completed_at < cutoff_time
            ]

            for order_id in to_remove:
                self.execution_history.pop(order_id, None)

            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} old execution records")

        except Exception as e:
            logger.error(f"Error cleaning up old executions: {e}")


# Global execution engine instance
_execution_engine: Optional[TradeExecutionEngine] = None


async def get_execution_engine(config: Dict[str, Any] = None) -> TradeExecutionEngine:
    """Get global trade execution engine instance.

    Args:
        config: Engine configuration (used only on first call).

    Returns:
        TradeExecutionEngine instance.
    """
    global _execution_engine

    if _execution_engine is None:
        _execution_engine = TradeExecutionEngine(config)
        await _execution_engine.initialize()

    return _execution_engine


async def shutdown_execution_engine() -> None:
    """Shutdown global trade execution engine."""
    global _execution_engine

    if _execution_engine is not None:
        await _execution_engine.shutdown()
        _execution_engine = None


@asynccontextmanager
async def execution_engine_context(config: Dict[str, Any] = None):
    """Async context manager for trade execution engine.

    Args:
        config: Engine configuration.

    Yields:
        TradeExecutionEngine instance.
    """
    engine = None
    try:
        engine = TradeExecutionEngine(config)
        await engine.initialize()
        yield engine
    finally:
        if engine:
            await engine.shutdown()
