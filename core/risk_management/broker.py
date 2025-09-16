"""Broker Risk Manager Implementation.

This module provides risk management specifically designed for broker integration
with FIX protocol support and real-time order validation.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from ..fix.messages.base import ExecType, OrdStatus, Side
from ..fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest
from .base import (
    BaseRiskManager,
    Position,
    RiskCheckResult,
    RiskCheckType,
    RiskLimits,
    RiskMetrics,
    RiskViolation,
)

logger = logging.getLogger(__name__)


class BrokerRiskManager(BaseRiskManager):
    """Risk manager optimized for broker integration with FIX protocol."""

    def __init__(
        self,
        limits: Optional[RiskLimits] = None,
        broker_id: str = "default",
        enable_pre_trade_checks: bool = True,
        enable_post_trade_checks: bool = True,
    ):
        """Initialize broker risk manager.

        Args:
            limits: Risk limits configuration.
            broker_id: Broker identifier.
            enable_pre_trade_checks: Enable pre-trade risk checks.
            enable_post_trade_checks: Enable post-trade risk checks.
        """
        super().__init__(limits)
        self.broker_id = broker_id
        self.enable_pre_trade_checks = enable_pre_trade_checks
        self.enable_post_trade_checks = enable_post_trade_checks

        # FIX protocol specific tracking
        self.pending_orders: Dict[str, NewOrderSingle] = {}
        self.execution_reports: Dict[str, List[ExecutionReport]] = {}
        self.order_statuses: Dict[str, OrdStatus] = {}

        # Broker-specific limits
        self.symbol_restrictions: Set[str] = set()
        self.counterparty_limits: Dict[str, float] = {}
        self.price_bands: Dict[str, Tuple[float, float]] = {}

        # Performance tracking
        self.fill_rates: Dict[str, float] = {}
        self.slippage_tracking: Dict[str, List[float]] = {}

    def validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        account_balance: float,
        current_positions: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, List[RiskViolation]]:
        """Validate an order for broker execution.

        Args:
            symbol: Trading symbol.
            side: Order side ('buy' or 'sell').
            quantity: Order quantity.
            price: Order price.
            account_balance: Current account balance.
            current_positions: Current positions dictionary.

        Returns:
            Tuple of (is_valid, violations).
        """
        if not self.enable_pre_trade_checks:
            return True, []

        violations = []

        # Check symbol restrictions
        if symbol in self.symbol_restrictions:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.SYMBOL_RESTRICTION,
                    result=RiskCheckResult.FAIL,
                    message=f"Symbol {symbol} is restricted for trading",
                    current_value=symbol,
                    limit_value=self.symbol_restrictions,
                    severity="high",
                )
            )

        # Check price bands
        if symbol in self.price_bands:
            min_price, max_price = self.price_bands[symbol]
            if not (min_price <= price <= max_price):
                violations.append(
                    RiskViolation(
                        check_type=RiskCheckType.PRICE_DEVIATION,
                        result=RiskCheckResult.FAIL,
                        message=f"Price {price} outside allowed band [{min_price}, {max_price}]",
                        current_value=price,
                        limit_value=(min_price, max_price),
                        severity="high",
                    )
                )

        # Check order size limits
        notional_value = abs(quantity * price)
        max_order_size = account_balance * self.limits.max_order_size

        if notional_value > max_order_size:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.ORDER_SIZE_LIMIT,
                    result=RiskCheckResult.FAIL,
                    message=f"Order size {notional_value:.2f} exceeds limit {max_order_size:.2f}",
                    current_value=notional_value,
                    limit_value=max_order_size,
                    severity="high",
                )
            )

        # Check position limits
        position_value = abs(quantity * price)
        max_position_size = self.get_position_size_limit(symbol, account_balance)

        # Consider existing position
        existing_position = self.positions.get(symbol)
        if existing_position:
            combined_value = existing_position.notional_value + position_value
            if combined_value > max_position_size:
                violations.append(
                    RiskViolation(
                        check_type=RiskCheckType.POSITION_LIMIT,
                        result=RiskCheckResult.FAIL,
                        message=f"Combined position {combined_value:.2f} exceeds limit {max_position_size:.2f}",
                        current_value=combined_value,
                        limit_value=max_position_size,
                        severity="high",
                    )
                )

        # Check counterparty limits
        if self.broker_id in self.counterparty_limits:
            broker_limit = self.counterparty_limits[self.broker_id]
            broker_exposure = sum(pos.notional_value for pos in self.positions.values())

            if broker_exposure + position_value > broker_limit:
                violations.append(
                    RiskViolation(
                        check_type=RiskCheckType.COUNTERPARTY_LIMIT,
                        result=RiskCheckResult.FAIL,
                        message=f"Broker exposure {broker_exposure + position_value:.2f} exceeds limit {broker_limit:.2f}",
                        current_value=broker_exposure + position_value,
                        limit_value=broker_limit,
                        severity="high",
                    )
                )

        # Check margin requirements
        if not self._check_margin_requirements(
            symbol, side, quantity, price, account_balance
        ):
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.MARGIN_REQUIREMENT,
                    result=RiskCheckResult.FAIL,
                    message=f"Insufficient margin for {symbol} position",
                    current_value=account_balance,
                    limit_value=position_value / self.limits.max_leverage,
                    severity="high",
                )
            )

        # Log violations
        for violation in violations:
            self.add_violation(violation)
            logger.warning(f"Broker risk violation: {violation.message}")

        # Order is valid if no FAIL violations
        is_valid = not any(v.result == RiskCheckResult.FAIL for v in violations)

        return is_valid, violations

    def validate_fix_order(
        self, order: NewOrderSingle
    ) -> Tuple[bool, List[RiskViolation]]:
        """Validate a FIX order message.

        Args:
            order: FIX NewOrderSingle message.

        Returns:
            Tuple of (is_valid, violations).
        """
        violations = []

        # Extract order details
        symbol = order.symbol
        side = "buy" if order.side == Side.BUY else "sell"
        quantity = float(order.order_qty)
        price = float(order.price) if order.price else 0.0

        # Get current account balance (would come from broker adapter)
        account_balance = 100000.0  # Placeholder

        # Validate using standard order validation
        is_valid, standard_violations = self.validate_order(
            symbol, side, quantity, price, account_balance
        )
        violations.extend(standard_violations)

        # Additional FIX-specific checks
        if order.time_in_force not in ["DAY", "IOC", "FOK"]:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.TIME_RESTRICTION,
                    result=RiskCheckResult.WARN,
                    message=f"Unusual time in force: {order.time_in_force}",
                    current_value=order.time_in_force,
                    limit_value=["DAY", "IOC", "FOK"],
                    severity="low",
                )
            )

        # Check order type
        if order.ord_type not in ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.ORDER_SIZE_LIMIT,
                    result=RiskCheckResult.WARN,
                    message=f"Unusual order type: {order.ord_type}",
                    current_value=order.ord_type,
                    limit_value=["MARKET", "LIMIT", "STOP", "STOP_LIMIT"],
                    severity="low",
                )
            )

        # Store pending order for tracking
        if is_valid:
            self.pending_orders[order.cl_ord_id] = order

        return is_valid, violations

    def process_execution_report(self, exec_report: ExecutionReport) -> None:
        """Process an execution report from the broker.

        Args:
            exec_report: FIX ExecutionReport message.
        """
        order_id = exec_report.cl_ord_id

        # Store execution report
        if order_id not in self.execution_reports:
            self.execution_reports[order_id] = []
        self.execution_reports[order_id].append(exec_report)

        # Update order status
        self.order_statuses[order_id] = exec_report.ord_status

        # Process different execution types
        if exec_report.exec_type == ExecType.TRADE:
            self._process_trade_execution(exec_report)
        elif exec_report.exec_type == ExecType.CANCELLED:
            self._process_order_cancellation(exec_report)
        elif exec_report.exec_type == ExecType.REJECTED:
            self._process_order_rejection(exec_report)

        # Post-trade checks
        if self.enable_post_trade_checks:
            self._perform_post_trade_checks(exec_report)

    def _process_trade_execution(self, exec_report: ExecutionReport) -> None:
        """Process a trade execution.

        Args:
            exec_report: Execution report for the trade.
        """
        symbol = exec_report.symbol
        side = "buy" if exec_report.side == Side.BUY else "sell"
        fill_qty = float(exec_report.last_qty or 0)
        fill_price = float(exec_report.last_px or 0)

        # Update position
        if symbol in self.positions:
            position = self.positions[symbol]

            # Calculate new position
            if position.side == side:
                # Adding to existing position
                new_qty = position.quantity + fill_qty
                new_avg_price = (
                    (position.quantity * position.entry_price) + (fill_qty * fill_price)
                ) / new_qty
                position.quantity = new_qty
                position.entry_price = new_avg_price
            else:
                # Reducing existing position
                position.quantity = max(0, position.quantity - fill_qty)
                if position.quantity == 0:
                    # Position closed
                    del self.positions[symbol]
                    return
        else:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                side=side,
                quantity=fill_qty,
                entry_price=fill_price,
                current_price=fill_price,
                unrealized_pnl=0.0,
            )

        # Track fill rate
        order_id = exec_report.cl_ord_id
        if order_id in self.pending_orders:
            original_order = self.pending_orders[order_id]
            original_qty = float(original_order.order_qty)
            self.fill_rates[order_id] = fill_qty / original_qty

        # Track slippage
        if order_id in self.pending_orders:
            original_order = self.pending_orders[order_id]
            if original_order.price:
                original_price = float(original_order.price)
                slippage = abs(fill_price - original_price) / original_price
                if symbol not in self.slippage_tracking:
                    self.slippage_tracking[symbol] = []
                self.slippage_tracking[symbol].append(slippage)

    def _process_order_cancellation(self, exec_report: ExecutionReport) -> None:
        """Process order cancellation.

        Args:
            exec_report: Execution report for the cancellation.
        """
        order_id = exec_report.cl_ord_id

        # Remove from pending orders
        if order_id in self.pending_orders:
            del self.pending_orders[order_id]

        logger.info(f"Order {order_id} cancelled")

    def _process_order_rejection(self, exec_report: ExecutionReport) -> None:
        """Process order rejection.

        Args:
            exec_report: Execution report for the rejection.
        """
        order_id = exec_report.cl_ord_id

        # Remove from pending orders
        if order_id in self.pending_orders:
            del self.pending_orders[order_id]

        # Log rejection reason
        rejection_reason = exec_report.text or "No reason provided"
        logger.warning(f"Order {order_id} rejected: {rejection_reason}")

        # Create violation for rejection
        violation = RiskViolation(
            check_type=RiskCheckType.ORDER_SIZE_LIMIT,
            result=RiskCheckResult.FAIL,
            message=f"Order rejected by broker: {rejection_reason}",
            current_value=order_id,
            limit_value="accepted",
            severity="high",
        )
        self.add_violation(violation)

    def _perform_post_trade_checks(self, exec_report: ExecutionReport) -> None:
        """Perform post-trade risk checks.

        Args:
            exec_report: Execution report to check.
        """
        # Check for unusual fill prices
        if exec_report.last_px:
            fill_price = float(exec_report.last_px)
            order_id = exec_report.cl_ord_id

            if order_id in self.pending_orders:
                original_order = self.pending_orders[order_id]
                if original_order.price:
                    original_price = float(original_order.price)
                    price_diff = abs(fill_price - original_price) / original_price

                    if price_diff > 0.05:  # 5% price difference
                        violation = RiskViolation(
                            check_type=RiskCheckType.PRICE_DEVIATION,
                            result=RiskCheckResult.WARN,
                            message=f"Large price deviation on fill: {price_diff:.2%}",
                            current_value=price_diff,
                            limit_value=0.05,
                            severity="medium",
                        )
                        self.add_violation(violation)

    def update_position(self, position: Position) -> None:
        """Update position in broker risk manager.

        Args:
            position: Position to update.
        """
        self.positions[position.symbol] = position

        # Update peak portfolio value
        total_value = sum(pos.market_value for pos in self.positions.values())
        if total_value > self.peak_portfolio_value:
            self.peak_portfolio_value = total_value

        self.current_portfolio_value = total_value

    def calculate_risk_metrics(self) -> RiskMetrics:
        """Calculate broker-specific risk metrics.

        Returns:
            Risk metrics object.
        """
        positions = list(self.positions.values())

        if not positions:
            return RiskMetrics()

        # Calculate basic metrics
        total_exposure = sum(pos.notional_value for pos in positions)
        unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)

        # Calculate average fill rate
        avg_fill_rate = (
            np.mean(list(self.fill_rates.values())) if self.fill_rates else 0.0
        )

        # Calculate average slippage
        all_slippage = []
        for symbol_slippage in self.slippage_tracking.values():
            all_slippage.extend(symbol_slippage)
        avg_slippage = np.mean(all_slippage) if all_slippage else 0.0

        return RiskMetrics(
            total_exposure=total_exposure,
            unrealized_pnl=unrealized_pnl,
            portfolio_value=self.current_portfolio_value,
        )

    def _check_margin_requirements(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        account_balance: float,
    ) -> bool:
        """Check margin requirements for position.

        Args:
            symbol: Trading symbol.
            side: Position side.
            quantity: Position quantity.
            price: Position price.
            account_balance: Current account balance.

        Returns:
            True if margin requirements are met.
        """
        # Simplified margin calculation
        notional_value = abs(quantity * price)
        required_margin = notional_value / self.limits.max_leverage

        return account_balance >= required_margin

    def add_symbol_restriction(self, symbol: str) -> None:
        """Add a symbol to the restriction list.

        Args:
            symbol: Symbol to restrict.
        """
        self.symbol_restrictions.add(symbol)
        logger.info(f"Symbol {symbol} added to restrictions")

    def remove_symbol_restriction(self, symbol: str) -> None:
        """Remove a symbol from the restriction list.

        Args:
            symbol: Symbol to unrestrict.
        """
        self.symbol_restrictions.discard(symbol)
        logger.info(f"Symbol {symbol} removed from restrictions")

    def set_price_band(self, symbol: str, min_price: float, max_price: float) -> None:
        """Set price band for a symbol.

        Args:
            symbol: Trading symbol.
            min_price: Minimum allowed price.
            max_price: Maximum allowed price.
        """
        self.price_bands[symbol] = (min_price, max_price)
        logger.info(f"Price band set for {symbol}: [{min_price}, {max_price}]")

    def get_broker_status(self) -> Dict[str, Any]:
        """Get broker-specific status information.

        Returns:
            Status dictionary.
        """
        return {
            "broker_id": self.broker_id,
            "pending_orders": len(self.pending_orders),
            "active_positions": len(self.positions),
            "symbol_restrictions": list(self.symbol_restrictions),
            "price_bands": self.price_bands,
            "counterparty_limits": self.counterparty_limits,
            "avg_fill_rate": (
                np.mean(list(self.fill_rates.values())) if self.fill_rates else 0.0
            ),
            "avg_slippage": (
                np.mean(
                    [np.mean(slippage) for slippage in self.slippage_tracking.values()]
                )
                if self.slippage_tracking
                else 0.0
            ),
            "total_violations": len(self.violations),
            "pre_trade_checks_enabled": self.enable_pre_trade_checks,
            "post_trade_checks_enabled": self.enable_post_trade_checks,
        }
