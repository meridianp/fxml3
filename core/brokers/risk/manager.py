"""Risk Manager Implementation.

This module provides the main risk management system that integrates
with the broker abstraction layer.

WARNING: This module is deprecated and will be removed in a future version.
Please migrate to the unified risk management system:
- Use BrokerRiskManager from fxml4.risk_management.broker
"""

import asyncio
import json
import logging
import warnings
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

# Issue deprecation warning when this module is imported
warnings.warn(
    "fxml4.brokers.risk.manager is deprecated. "
    "Please migrate to BrokerRiskManager from fxml4.risk_management.broker",
    DeprecationWarning,
    stacklevel=2,
)

from ...fix.messages.base import ExecType, OrdStatus, Side
from ...fix.messages.orders import ExecutionReport, NewOrderSingle
from .base import (
    Position,
    RiskCheckResult,
    RiskCheckType,
    RiskLimits,
    RiskManager,
    RiskMetrics,
    RiskViolation,
)
from .checks import (
    CounterpartyLimitCheck,
    DailyLossLimitCheck,
    DuplicateOrderCheck,
    OrderSizeLimitCheck,
    PositionLimitCheck,
    PriceDeviationCheck,
    SymbolRestrictionCheck,
    TimeRestrictionCheck,
)

# from ..messaging.publisher import MessagePublisher  # Avoiding pika dependency for now

logger = logging.getLogger(__name__)


class FXRiskManager(RiskManager):
    """FX-specific risk manager implementation."""

    def __init__(
        self,
        limits: RiskLimits,
        publisher: Optional[Any] = None,  # MessagePublisher = None,
        enable_all_checks: bool = True,
    ):
        """Initialize FX risk manager.

        Args:
            limits: Risk limits configuration.
            publisher: Message publisher for risk events.
            enable_all_checks: Whether to enable all risk checks by default.
        """
        super().__init__(limits)
        self.publisher = publisher

        # Initialize standard risk checks
        if enable_all_checks:
            self._initialize_checks()

        # Tracking data
        self._pending_orders: Dict[str, NewOrderSingle] = {}
        self._order_brokers: Dict[str, str] = {}
        self._daily_pnl_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Override tracking
        self._overrides: Dict[str, Dict[str, Any]] = {}

        logger.info("Initialized FX Risk Manager")

    def _initialize_checks(self):
        """Initialize all standard risk checks."""
        self.add_check(PositionLimitCheck())
        self.add_check(OrderSizeLimitCheck())
        self.add_check(DailyLossLimitCheck())
        self.add_check(PriceDeviationCheck())
        self.add_check(SymbolRestrictionCheck())
        self.add_check(TimeRestrictionCheck())
        self.add_check(DuplicateOrderCheck())
        self.add_check(CounterpartyLimitCheck())

    async def check_order(
        self, order: NewOrderSingle, broker: Optional[str] = None
    ) -> Tuple[bool, List[RiskViolation]]:
        """Check if order passes risk controls.

        Args:
            order: Order to check.
            broker: Target broker for the order.

        Returns:
            Tuple of (passes_checks, list_of_violations).
        """
        violations = []

        # Store broker info for counterparty check
        if broker:
            order._target_broker = broker

        # Update metrics before checking
        await self.update_metrics()

        # Run all enabled checks
        for check in self.checks:
            if not check.enabled:
                continue

            try:
                violation = await check.check(order, self.limits, self.metrics)
                if violation:
                    violations.append(violation)

                    # Log violation
                    logger.warning(
                        f"Risk check {check.check_type.value} violation: "
                        f"{violation.message}"
                    )

            except Exception as e:
                logger.error(f"Error in risk check {check.check_type.value}: {e}")
                # Create error violation
                violations.append(
                    RiskViolation(
                        check_type=check.check_type,
                        result=RiskCheckResult.FAIL,
                        message=f"Risk check error: {str(e)}",
                        current_value="error",
                        limit_value="N/A",
                        can_override=False,
                    )
                )

        # Check for overrides
        if violations and order.cl_ord_id in self._overrides:
            override = self._overrides[order.cl_ord_id]
            override_violations = []

            for violation in violations:
                if violation.can_override and self._check_override_authority(
                    override.get("level"), violation.override_level
                ):
                    # Log override
                    logger.info(
                        f"Risk violation overridden for {order.cl_ord_id}: "
                        f"{violation.check_type.value} by {override.get('user')}"
                    )
                    violation.result = RiskCheckResult.OVERRIDE
                else:
                    override_violations.append(violation)

            violations = override_violations

        # Determine if order passes
        fail_violations = [v for v in violations if v.result == RiskCheckResult.FAIL]
        passes = len(fail_violations) == 0

        # Store order if passes initial checks
        if passes:
            self._pending_orders[order.cl_ord_id] = order
            if broker:
                self._order_brokers[order.cl_ord_id] = broker

        # Publish risk check result
        if self.publisher:
            await self._publish_risk_event(
                "risk_check",
                {
                    "cl_ord_id": order.cl_ord_id,
                    "symbol": order.symbol,
                    "passes": passes,
                    "violations": [self._violation_to_dict(v) for v in violations],
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        return passes, violations

    async def update_position(self, symbol: str, quantity: float, price: float) -> None:
        """Update position after trade with atomic operations.

        CRITICAL FIX: Ensures atomic position updates and proper capital calculations
        to prevent race conditions in concurrent trading scenarios.

        Args:
            symbol: Symbol traded.
            quantity: Quantity traded (positive for buy, negative for sell).
            price: Execution price.
        """
        # Input validation
        if not symbol or price <= 0:
            logger.error(
                f"Invalid position update parameters: symbol={symbol}, price={price}"
            )
            return

        if abs(quantity) < 1e-8:  # Effectively zero quantity
            logger.warning(
                f"Ignoring position update with negligible quantity: {quantity}"
            )
            return

        # Acquire lock for symbol with proper timeout handling
        if not await self.lock_symbol(symbol):
            logger.error(
                f"Failed to acquire lock for {symbol} - skipping position update"
            )
            return

        try:
            # Create atomic snapshot of current position
            current_position = self.metrics.positions.get(symbol)

            if current_position:
                # CRITICAL FIX: Calculate all values atomically before updating
                old_quantity = current_position.quantity
                old_avg_price = current_position.average_price
                old_realized_pnl = current_position.realized_pnl

                new_quantity = old_quantity + quantity

                # Handle position closure (near-zero quantity)
                if abs(new_quantity) < 1e-8:
                    # Position closed - calculate final realized P&L
                    if old_quantity != 0:
                        # Calculate P&L for the closing quantity
                        closing_pnl = -old_quantity * (price - old_avg_price)
                        final_realized_pnl = old_realized_pnl + closing_pnl

                        logger.info(
                            f"Position closed for {symbol}: PnL={closing_pnl:.4f}, Total Realized={final_realized_pnl:.4f}"
                        )

                    # Atomically remove position
                    del self.metrics.positions[symbol]

                elif (new_quantity > 0) == (old_quantity > 0) or old_quantity == 0:
                    # Same direction trade or new position
                    if old_quantity == 0:
                        # New position
                        new_avg_price = price
                        new_realized_pnl = 0
                    else:
                        # Position increased in same direction - update average price
                        total_cost = old_quantity * old_avg_price + quantity * price
                        new_avg_price = (
                            total_cost / new_quantity if new_quantity != 0 else price
                        )
                        new_realized_pnl = old_realized_pnl

                    # Atomically update position
                    current_position.quantity = new_quantity
                    current_position.average_price = new_avg_price
                    current_position.market_value = new_quantity * price
                    current_position.realized_pnl = new_realized_pnl
                    current_position.last_update = datetime.utcnow()

                else:
                    # Opposite direction trade - partial close with realized P&L
                    if abs(quantity) <= abs(old_quantity):
                        # Partial close - calculate realized P&L on closed portion
                        closed_quantity = -quantity  # Opposite sign
                        realized_pnl_on_close = closed_quantity * (
                            price - old_avg_price
                        )

                        # Update position
                        current_position.quantity = new_quantity
                        current_position.average_price = (
                            old_avg_price  # Keep same avg price
                        )
                        current_position.market_value = new_quantity * price
                        current_position.realized_pnl = (
                            old_realized_pnl + realized_pnl_on_close
                        )
                        current_position.last_update = datetime.utcnow()

                        logger.info(
                            f"Partial close for {symbol}: Realized PnL={realized_pnl_on_close:.4f}"
                        )

            else:
                # New position - create atomically
                new_position = Position(
                    symbol=symbol,
                    quantity=quantity,
                    average_price=price,
                    market_value=quantity * price,
                    unrealized_pnl=0,
                    realized_pnl=0,
                    last_update=datetime.utcnow(),
                )

                # Atomically add new position
                self.metrics.positions[symbol] = new_position
                logger.info(
                    f"New position created for {symbol}: qty={quantity}, price={price}"
                )

            # Update aggregate metrics after position change
            await self.update_metrics()

        except Exception as e:
            logger.error(f"Error updating position for {symbol}: {e}")
            raise

        finally:
            await self.unlock_symbol(symbol)

    async def update_metrics(self) -> None:
        """Update risk metrics from current positions."""
        # Calculate total notional
        self.metrics.total_notional = sum(
            pos.notional_value for pos in self.metrics.positions.values()
        )

        # Calculate P&L
        total_unrealized = sum(
            pos.unrealized_pnl for pos in self.metrics.positions.values()
        )
        total_realized = sum(
            pos.realized_pnl for pos in self.metrics.positions.values()
        )

        # Update daily P&L (would need historical data for accurate calculation)
        self.metrics.daily_pnl = total_unrealized + total_realized

        # Count open orders
        self.metrics.open_orders = len(self._pending_orders)

        # Calculate open order notional
        open_notional = 0
        for order in self._pending_orders.values():
            if hasattr(order, "price") and order.price:
                open_notional += order.order_qty * order.price
        self.metrics.open_order_notional = open_notional

        # Update broker exposure
        broker_exposure = defaultdict(float)
        for cl_ord_id, broker in self._order_brokers.items():
            if cl_ord_id in self._pending_orders:
                order = self._pending_orders[cl_ord_id]
                if hasattr(order, "price") and order.price:
                    broker_exposure[broker] += order.order_qty * order.price
        self.metrics.broker_exposure = dict(broker_exposure)

        self.metrics.last_update = datetime.utcnow()

    async def handle_execution(self, execution: ExecutionReport) -> None:
        """Handle execution report for risk tracking.

        Args:
            execution: Execution report from broker.
        """
        cl_ord_id = execution.cl_ord_id

        # Handle based on execution type
        if execution.exec_type == ExecType.TRADE:
            # Update position
            side_multiplier = 1 if execution.side == Side.BUY else -1
            await self.update_position(
                execution.symbol,
                execution.last_qty * side_multiplier,
                execution.last_px,
            )

        # Remove from pending if terminal state
        if execution.ord_status in [
            OrdStatus.FILLED,
            OrdStatus.CANCELED,
            OrdStatus.REJECTED,
        ]:
            self._pending_orders.pop(cl_ord_id, None)
            self._order_brokers.pop(cl_ord_id, None)

            # Update broker counts for counterparty check
            for check in self.checks:
                if isinstance(check, CounterpartyLimitCheck):
                    broker = self._order_brokers.get(cl_ord_id)
                    if broker:
                        check.decrement_broker_count(broker)

        # Publish execution risk event
        if self.publisher:
            await self._publish_risk_event(
                "execution",
                {
                    "cl_ord_id": cl_ord_id,
                    "symbol": execution.symbol,
                    "side": execution.side.name,
                    "exec_type": execution.exec_type.name,
                    "ord_status": execution.ord_status.name,
                    "last_qty": execution.last_qty,
                    "last_px": execution.last_px,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

    def add_override(self, cl_ord_id: str, user: str, level: str, reason: str) -> None:
        """Add risk override for an order.

        Args:
            cl_ord_id: Client order ID.
            user: User adding override.
            level: Override authority level.
            reason: Reason for override.
        """
        self._overrides[cl_ord_id] = {
            "user": user,
            "level": level,
            "reason": reason,
            "timestamp": datetime.utcnow(),
        }

        logger.info(
            f"Risk override added for {cl_ord_id} by {user} "
            f"(level: {level}): {reason}"
        )

    def update_market_price(self, symbol: str, price: float) -> None:
        """Update market price for price deviation checks.

        Args:
            symbol: Symbol to update.
            price: Current market price.
        """
        for check in self.checks:
            if isinstance(check, PriceDeviationCheck):
                check.update_market_price(symbol, price)

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk summary.

        Returns:
            Dictionary with risk metrics and limits.
        """
        return {
            "metrics": {
                "total_notional": self.metrics.total_notional,
                "daily_pnl": self.metrics.daily_pnl,
                "open_orders": self.metrics.open_orders,
                "open_order_notional": self.metrics.open_order_notional,
                "position_count": len(self.metrics.positions),
                "last_update": self.metrics.last_update.isoformat(),
            },
            "limits": {
                "max_portfolio_notional": self.limits.max_portfolio_notional,
                "max_daily_loss": self.limits.max_daily_loss,
                "max_order_notional": self.limits.max_order_notional,
            },
            "positions": {
                symbol: {
                    "quantity": pos.quantity,
                    "average_price": pos.average_price,
                    "market_value": pos.market_value,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                }
                for symbol, pos in self.metrics.positions.items()
            },
            "enabled_checks": [
                check.check_type.value for check in self.checks if check.enabled
            ],
        }

    def _check_override_authority(
        self, user_level: Optional[str], required_level: str
    ) -> bool:
        """Check if user has authority to override.

        Args:
            user_level: User's authority level.
            required_level: Required authority level.

        Returns:
            True if user has sufficient authority.
        """
        hierarchy = {"risk_manager": 1, "senior_trader": 2, "compliance": 3}

        if not user_level or user_level not in hierarchy:
            return False

        return hierarchy.get(user_level, 0) >= hierarchy.get(required_level, 999)

    def _violation_to_dict(self, violation: RiskViolation) -> Dict[str, Any]:
        """Convert violation to dictionary for serialization."""
        return {
            "check_type": violation.check_type.value,
            "result": violation.result.value,
            "message": violation.message,
            "current_value": str(violation.current_value),
            "limit_value": str(violation.limit_value),
            "timestamp": violation.timestamp.isoformat(),
            "can_override": violation.can_override,
            "override_level": violation.override_level,
        }

    async def _publish_risk_event(self, event_type: str, data: Dict[str, Any]):
        """Publish risk management event.

        Args:
            event_type: Type of risk event.
            data: Event data.
        """
        if not self.publisher:
            return

        try:
            await self.publisher.publish_message(
                exchange="risk.events",
                routing_key=f"risk.{event_type}",
                message=data,
                properties={"content_type": "application/json", "type": event_type},
            )
        except Exception as e:
            logger.error(f"Failed to publish risk event: {e}")
