"""Risk Management Integration with Broker Adapters.

This module provides integration between the risk management system
and the broker adapter framework.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..adapters.base import BrokerAdapter
from .base import RiskCheckResult, RiskLimits, RiskViolation
from .manager import FXRiskManager

# from ..adapters.manager import BrokerAdapterManager  # Avoiding pika dependency
# from ..messaging.router import MessageRouter  # Avoiding pika dependency

# Type aliases for forward references
BrokerAdapterManager = Any  # Will be imported when pika is available
MessageRouter = Any  # Will be imported when pika is available
from ...fix.messages.orders import ExecutionReport, NewOrderSingle

logger = logging.getLogger(__name__)


class RiskAwareBrokerManager:
    """Broker manager with integrated risk management."""

    def __init__(
        self,
        adapter_manager: BrokerAdapterManager,
        risk_manager: FXRiskManager,
        router: Optional[MessageRouter] = None,
    ):
        """Initialize risk-aware broker manager.

        Args:
            adapter_manager: Broker adapter manager.
            risk_manager: Risk management system.
            router: Message router for broker selection.
        """
        self.adapter_manager = adapter_manager
        self.risk_manager = risk_manager
        self.router = router

        # Track risk-rejected orders
        self.rejected_orders: Dict[str, List[RiskViolation]] = {}

        logger.info("Initialized Risk-Aware Broker Manager")

    async def submit_order(
        self, order: NewOrderSingle, preferred_broker: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit order with risk checks.

        Args:
            order: Order to submit.
            preferred_broker: Preferred broker for routing.

        Returns:
            Dictionary with submission result.
        """
        result = {
            "cl_ord_id": order.cl_ord_id,
            "status": "pending",
            "risk_check": None,
            "broker": None,
            "order_id": None,
            "violations": [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Determine target broker
            if self.router and not preferred_broker:
                routing_decision = await self.router.route_order(order)
                target_broker = routing_decision.adapter_id
            else:
                target_broker = preferred_broker or self._get_default_broker()

            result["broker"] = target_broker

            # Run risk checks
            passes, violations = await self.risk_manager.check_order(
                order, broker=target_broker
            )

            result["risk_check"] = "pass" if passes else "fail"
            result["violations"] = [self._violation_to_dict(v) for v in violations]

            if not passes:
                # Order rejected by risk
                result["status"] = "risk_rejected"
                self.rejected_orders[order.cl_ord_id] = violations

                logger.warning(
                    f"Order {order.cl_ord_id} rejected by risk management: "
                    f"{len(violations)} violations"
                )

                # Check if any violations can be overridden
                overridable = any(v.can_override for v in violations)
                if overridable:
                    result["can_override"] = True
                    result["override_levels"] = list(
                        set(v.override_level for v in violations if v.can_override)
                    )

                return result

            # Get adapter
            adapter = self.adapter_manager.get_adapter(target_broker)
            if not adapter:
                result["status"] = "error"
                result["error"] = f"Broker adapter '{target_broker}' not found"
                return result

            # Check adapter is ready
            if not adapter.is_ready():
                result["status"] = "error"
                result["error"] = f"Broker adapter '{target_broker}' not ready"
                return result

            # Submit order
            order_id = await adapter.submit_order(order)

            result["status"] = "submitted"
            result["order_id"] = order_id

            logger.info(
                f"Order {order.cl_ord_id} submitted to {target_broker}: {order_id}"
            )

        except Exception as e:
            logger.error(f"Error submitting order {order.cl_ord_id}: {e}")
            result["status"] = "error"
            result["error"] = str(e)

        return result

    async def submit_order_with_override(
        self,
        order: NewOrderSingle,
        override_user: str,
        override_level: str,
        override_reason: str,
        preferred_broker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit order with risk override.

        Args:
            order: Order to submit.
            override_user: User performing override.
            override_level: User's override authority level.
            override_reason: Reason for override.
            preferred_broker: Preferred broker for routing.

        Returns:
            Dictionary with submission result.
        """
        # Add override to risk manager
        self.risk_manager.add_override(
            order.cl_ord_id, override_user, override_level, override_reason
        )

        # Submit with override in place
        result = await self.submit_order(order, preferred_broker)

        # Add override info to result
        if result["status"] == "submitted":
            result["override"] = {
                "user": override_user,
                "level": override_level,
                "reason": override_reason,
            }

        return result

    async def handle_execution_report(self, report: ExecutionReport) -> None:
        """Handle execution report with risk updates.

        Args:
            report: Execution report from broker.
        """
        # Update risk manager
        await self.risk_manager.handle_execution(report)

        # Additional processing can be added here
        logger.info(
            f"Processed execution report: {report.cl_ord_id} - "
            f"{report.ord_status.name}"
        )

    def get_rejected_order_info(self, cl_ord_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a risk-rejected order.

        Args:
            cl_ord_id: Client order ID.

        Returns:
            Rejection information or None.
        """
        violations = self.rejected_orders.get(cl_ord_id)
        if not violations:
            return None

        return {
            "cl_ord_id": cl_ord_id,
            "violations": [self._violation_to_dict(v) for v in violations],
            "can_override": any(v.can_override for v in violations),
            "override_levels": list(
                set(v.override_level for v in violations if v.can_override)
            ),
        }

    def update_market_prices(self, prices: Dict[str, float]) -> None:
        """Update market prices for risk checks.

        Args:
            prices: Dictionary of symbol to price.
        """
        for symbol, price in prices.items():
            self.risk_manager.update_market_price(symbol, price)

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk summary.

        Returns:
            Risk metrics and limits.
        """
        return self.risk_manager.get_risk_summary()

    def _get_default_broker(self) -> str:
        """Get default broker for orders."""
        # Get first available adapter
        adapters = self.adapter_manager.get_all_adapters()
        for adapter_id, adapter in adapters.items():
            if adapter.is_ready():
                return adapter_id
        return "unknown"

    def _violation_to_dict(self, violation: RiskViolation) -> Dict[str, Any]:
        """Convert violation to dictionary."""
        return {
            "check_type": violation.check_type.value,
            "result": violation.result.value,
            "message": violation.message,
            "current_value": str(violation.current_value),
            "limit_value": str(violation.limit_value),
            "can_override": violation.can_override,
            "override_level": violation.override_level,
        }


class RiskManagementMiddleware:
    """Middleware for integrating risk checks into order flow."""

    def __init__(self, risk_manager: FXRiskManager):
        """Initialize middleware.

        Args:
            risk_manager: Risk management system.
        """
        self.risk_manager = risk_manager

    async def pre_submit_check(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> bool:
        """Pre-submission risk check.

        Args:
            order: Order to check.
            context: Order context (broker, etc).

        Returns:
            True if order can proceed.
        """
        broker = context.get("broker")
        passes, violations = await self.risk_manager.check_order(order, broker)

        # Store violations in context
        context["risk_violations"] = violations
        context["risk_check_passed"] = passes

        return passes

    async def post_execution_update(
        self, report: ExecutionReport, context: Dict[str, Any]
    ) -> None:
        """Post-execution risk update.

        Args:
            report: Execution report.
            context: Execution context.
        """
        await self.risk_manager.handle_execution(report)

        # Update context with risk metrics
        context["risk_metrics"] = self.risk_manager.get_risk_summary()


def create_risk_limits_from_config(config: Dict[str, Any]) -> RiskLimits:
    """Create risk limits from configuration dictionary.

    Args:
        config: Risk configuration.

    Returns:
        RiskLimits instance.
    """
    limits = RiskLimits()

    # Position limits
    if "position_limits" in config:
        pos_config = config["position_limits"]
        limits.max_portfolio_notional = pos_config.get(
            "max_portfolio_notional", limits.max_portfolio_notional
        )
        limits.max_single_position_notional = pos_config.get(
            "max_single_position_notional", limits.max_single_position_notional
        )
        limits.max_position_size = pos_config.get("max_position_size", {})

    # Order limits
    if "order_limits" in config:
        ord_config = config["order_limits"]
        limits.max_order_notional = ord_config.get(
            "max_order_notional", limits.max_order_notional
        )
        limits.min_order_size = ord_config.get("min_order_size", limits.min_order_size)
        limits.max_order_size = ord_config.get("max_order_size", {})

    # Loss limits
    if "loss_limits" in config:
        loss_config = config["loss_limits"]
        limits.max_daily_loss = loss_config.get("max_daily_loss", limits.max_daily_loss)
        limits.max_weekly_loss = loss_config.get(
            "max_weekly_loss", limits.max_weekly_loss
        )
        limits.max_monthly_loss = loss_config.get(
            "max_monthly_loss", limits.max_monthly_loss
        )

    # Price limits
    if "price_limits" in config:
        price_config = config["price_limits"]
        limits.max_price_deviation_pct = price_config.get(
            "max_price_deviation_pct", limits.max_price_deviation_pct
        )

    # Symbol restrictions
    if "symbol_restrictions" in config:
        sym_config = config["symbol_restrictions"]
        limits.allowed_symbols = sym_config.get("allowed_symbols")
        limits.blocked_symbols = sym_config.get("blocked_symbols", [])

    # Time restrictions
    if "time_restrictions" in config:
        time_config = config["time_restrictions"]
        restricted = time_config.get("restricted_hours", [])
        limits.restricted_hours = [(r["start"], r["end"]) for r in restricted]

    # Counterparty limits
    if "counterparty_limits" in config:
        cp_config = config["counterparty_limits"]
        limits.max_orders_per_broker = cp_config.get("max_orders_per_broker", {})
        limits.max_notional_per_broker = cp_config.get("max_notional_per_broker", {})

    return limits
