"""Live Trading Risk Manager Implementation.

This module provides risk management specifically designed for live trading environments.
It focuses on real-time risk monitoring and circuit breaker functionality.
"""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

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


class LiveRiskManager(BaseRiskManager):
    """Risk manager optimized for live trading environments."""

    def __init__(
        self, limits: Optional[RiskLimits] = None, circuit_breaker_enabled: bool = True
    ):
        """Initialize live risk manager.

        Args:
            limits: Risk limits configuration.
            circuit_breaker_enabled: Whether to enable circuit breaker functionality.
        """
        super().__init__(limits)
        self.circuit_breaker_enabled = circuit_breaker_enabled
        self.circuit_breaker_triggered = False
        self.circuit_breaker_trigger_time: Optional[datetime] = None
        self.circuit_breaker_reset_time: Optional[datetime] = None

        # Real-time monitoring
        self.order_history: deque = deque(maxlen=1000)
        self.pnl_history: deque = deque(maxlen=1000)
        self.violation_counts: Dict[RiskCheckType, int] = defaultdict(int)

        # Time-based limits
        self.daily_trade_count = 0
        self.hourly_trade_count = 0
        self.last_trade_time: Optional[datetime] = None
        self.trading_start_time = datetime.now().replace(
            hour=9, minute=0, second=0, microsecond=0
        )

        # Emergency settings
        self.max_daily_trades = 100
        self.max_hourly_trades = 20
        self.emergency_stop_loss = 0.10  # 10% portfolio loss triggers emergency stop

    def validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        account_balance: float,
        current_positions: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, List[RiskViolation]]:
        """Validate an order for live trading with real-time checks.

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
        violations = []

        # Check circuit breaker first
        if self.circuit_breaker_triggered:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.DAILY_LOSS_LIMIT,
                    result=RiskCheckResult.FAIL,
                    message="Circuit breaker triggered - trading suspended",
                    current_value=True,
                    limit_value=False,
                    severity="high",
                )
            )
            return False, violations

        # Check trading hours (example: 9 AM to 5 PM)
        current_time = datetime.now()
        if not self._is_trading_hours(current_time):
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.TIME_RESTRICTION,
                    result=RiskCheckResult.FAIL,
                    message=f"Trading outside allowed hours: {current_time.strftime('%H:%M')}",
                    current_value=current_time.hour,
                    limit_value=(9, 17),
                    severity="medium",
                )
            )

        # Check daily trade limit
        if self.daily_trade_count >= self.max_daily_trades:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.ORDER_SIZE_LIMIT,
                    result=RiskCheckResult.FAIL,
                    message=f"Daily trade limit reached: {self.daily_trade_count}/{self.max_daily_trades}",
                    current_value=self.daily_trade_count,
                    limit_value=self.max_daily_trades,
                    severity="high",
                )
            )

        # Check hourly trade limit
        if self.hourly_trade_count >= self.max_hourly_trades:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.ORDER_SIZE_LIMIT,
                    result=RiskCheckResult.FAIL,
                    message=f"Hourly trade limit reached: {self.hourly_trade_count}/{self.max_hourly_trades}",
                    current_value=self.hourly_trade_count,
                    limit_value=self.max_hourly_trades,
                    severity="high",
                )
            )

        # Check position size limit
        position_value = abs(quantity * price)
        max_position_size = self.get_position_size_limit(symbol, account_balance)

        if position_value > max_position_size:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.POSITION_LIMIT,
                    result=RiskCheckResult.FAIL,
                    message=f"Position size {position_value:.2f} exceeds limit {max_position_size:.2f}",
                    current_value=position_value,
                    limit_value=max_position_size,
                    severity="high",
                )
            )

        # Check for duplicate orders (rapid fire protection)
        if self._is_duplicate_order(symbol, side, quantity, price):
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.DUPLICATE_ORDER,
                    result=RiskCheckResult.FAIL,
                    message=f"Duplicate order detected within time window",
                    current_value=True,
                    limit_value=False,
                    severity="high",
                )
            )

        # Check price deviation from market
        price_deviation = self._check_price_deviation(symbol, price)
        if price_deviation > self.limits.max_price_deviation:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.PRICE_DEVIATION,
                    result=RiskCheckResult.FAIL,
                    message=f"Price deviation {price_deviation:.2%} exceeds limit {self.limits.max_price_deviation:.2%}",
                    current_value=price_deviation,
                    limit_value=self.limits.max_price_deviation,
                    severity="high",
                )
            )

        # Check emergency stop loss
        if self._check_emergency_stop_loss(account_balance):
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.DAILY_LOSS_LIMIT,
                    result=RiskCheckResult.FAIL,
                    message="Emergency stop loss triggered",
                    current_value=account_balance,
                    limit_value=self.emergency_stop_loss,
                    severity="high",
                )
            )
            self._trigger_circuit_breaker("Emergency stop loss")

        # Check drawdown limit
        drawdown_violation = self.check_drawdown_limit(account_balance)
        if drawdown_violation:
            violations.append(drawdown_violation)

        # Check margin requirements
        if not self._check_margin_requirements(
            symbol, side, quantity, price, account_balance
        ):
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.MARGIN_REQUIREMENT,
                    result=RiskCheckResult.FAIL,
                    message=f"Insufficient margin for position",
                    current_value=account_balance,
                    limit_value=position_value,
                    severity="high",
                )
            )

        # Log violations and update counters
        for violation in violations:
            self.add_violation(violation)
            self.violation_counts[violation.check_type] += 1

            if violation.result == RiskCheckResult.FAIL:
                logger.error(f"LIVE TRADING RISK VIOLATION: {violation.message}")
            else:
                logger.warning(f"Live trading risk warning: {violation.message}")

        # Order is valid if no FAIL violations
        is_valid = not any(v.result == RiskCheckResult.FAIL for v in violations)

        if is_valid:
            self._record_order_attempt(symbol, side, quantity, price, True)
        else:
            self._record_order_attempt(symbol, side, quantity, price, False)

        return is_valid, violations

    def update_position(self, position: Position) -> None:
        """Update position in live risk manager.

        Args:
            position: Position to update.
        """
        old_position = self.positions.get(position.symbol)
        self.positions[position.symbol] = position

        # Update real-time metrics
        self._update_real_time_metrics(position, old_position)

        # Check for emergency conditions
        self._check_emergency_conditions()

        # Update peak portfolio value
        total_value = sum(pos.market_value for pos in self.positions.values())
        if total_value > self.peak_portfolio_value:
            self.peak_portfolio_value = total_value

        self.current_portfolio_value = total_value

    def calculate_risk_metrics(self) -> RiskMetrics:
        """Calculate real-time risk metrics.

        Returns:
            Risk metrics object.
        """
        positions = list(self.positions.values())

        if not positions:
            return RiskMetrics()

        # Calculate real-time metrics
        total_exposure = sum(pos.notional_value for pos in positions)
        unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)

        # Calculate current drawdown
        current_drawdown = 0.0
        if self.peak_portfolio_value > 0:
            current_drawdown = (
                self.peak_portfolio_value - self.current_portfolio_value
            ) / self.peak_portfolio_value

        return RiskMetrics(
            total_exposure=total_exposure,
            daily_pnl=(
                sum(list(self.pnl_history)[-24:]) if self.pnl_history else 0.0
            ),  # Last 24 hours
            unrealized_pnl=unrealized_pnl,
            current_drawdown=current_drawdown,
            portfolio_value=self.current_portfolio_value,
        )

    def _is_trading_hours(self, current_time: datetime) -> bool:
        """Check if current time is within trading hours.

        Args:
            current_time: Current datetime.

        Returns:
            True if within trading hours.
        """
        # Simple example: 9 AM to 5 PM weekdays
        if current_time.weekday() >= 5:  # Weekend
            return False

        hour = current_time.hour
        return 9 <= hour < 17

    def _is_duplicate_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> bool:
        """Check if order is a duplicate within time window.

        Args:
            symbol: Trading symbol.
            side: Order side.
            quantity: Order quantity.
            price: Order price.

        Returns:
            True if duplicate order detected.
        """
        current_time = datetime.now()
        duplicate_window = timedelta(seconds=5)  # 5-second window

        for order in self.order_history:
            if (current_time - order["timestamp"]) < duplicate_window:
                if (
                    order["symbol"] == symbol
                    and order["side"] == side
                    and abs(order["quantity"] - quantity) < 0.01
                    and abs(order["price"] - price) < 0.001
                ):
                    return True

        return False

    def _check_price_deviation(self, symbol: str, price: float) -> float:
        """Check price deviation from market.

        Args:
            symbol: Trading symbol.
            price: Order price.

        Returns:
            Price deviation as percentage.
        """
        # Simplified - would need real market data feed
        # For now, assume reasonable deviation
        return 0.01  # 1% deviation

    def _check_emergency_stop_loss(self, account_balance: float) -> bool:
        """Check if emergency stop loss should be triggered.

        Args:
            account_balance: Current account balance.

        Returns:
            True if emergency stop loss should be triggered.
        """
        if self.peak_portfolio_value == 0:
            return False

        loss_percentage = (
            self.peak_portfolio_value - account_balance
        ) / self.peak_portfolio_value
        return loss_percentage >= self.emergency_stop_loss

    def _check_margin_requirements(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        account_balance: float,
    ) -> bool:
        """Check if sufficient margin for position.

        Args:
            symbol: Trading symbol.
            side: Order side.
            quantity: Order quantity.
            price: Order price.
            account_balance: Current account balance.

        Returns:
            True if sufficient margin.
        """
        # Simplified margin calculation
        position_value = abs(quantity * price)
        required_margin = position_value / self.limits.max_leverage

        return account_balance >= required_margin

    def _record_order_attempt(
        self, symbol: str, side: str, quantity: float, price: float, approved: bool
    ) -> None:
        """Record order attempt for tracking.

        Args:
            symbol: Trading symbol.
            side: Order side.
            quantity: Order quantity.
            price: Order price.
            approved: Whether order was approved.
        """
        order_record = {
            "timestamp": datetime.now(),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "approved": approved,
        }

        self.order_history.append(order_record)

        if approved:
            self.daily_trade_count += 1
            self.hourly_trade_count += 1
            self.last_trade_time = datetime.now()

    def _update_real_time_metrics(
        self, new_position: Position, old_position: Optional[Position]
    ) -> None:
        """Update real-time metrics.

        Args:
            new_position: New position data.
            old_position: Previous position data.
        """
        # Update P&L history
        if old_position:
            pnl_change = new_position.unrealized_pnl - old_position.unrealized_pnl
            self.pnl_history.append(pnl_change)

    def _check_emergency_conditions(self) -> None:
        """Check for emergency conditions that require immediate action."""
        # Check if too many violations in short time
        recent_violations = [
            v
            for v in self.violations
            if (datetime.utcnow() - v.timestamp).total_seconds() < 300
        ]  # 5 minutes

        if len(recent_violations) >= 10:  # 10 violations in 5 minutes
            self._trigger_circuit_breaker("Too many violations")

    def _trigger_circuit_breaker(self, reason: str) -> None:
        """Trigger circuit breaker to stop trading.

        Args:
            reason: Reason for triggering circuit breaker.
        """
        if self.circuit_breaker_enabled and not self.circuit_breaker_triggered:
            self.circuit_breaker_triggered = True
            self.circuit_breaker_trigger_time = datetime.now()
            self.circuit_breaker_reset_time = datetime.now() + timedelta(
                minutes=30
            )  # 30-minute cooldown

            logger.critical(f"CIRCUIT BREAKER TRIGGERED: {reason}")

    def reset_circuit_breaker(self) -> bool:
        """Reset circuit breaker if cooldown period has passed.

        Returns:
            True if circuit breaker was reset.
        """
        if (
            self.circuit_breaker_triggered
            and self.circuit_breaker_reset_time
            and datetime.now() >= self.circuit_breaker_reset_time
        ):

            self.circuit_breaker_triggered = False
            self.circuit_breaker_trigger_time = None
            self.circuit_breaker_reset_time = None

            logger.info("Circuit breaker reset")
            return True

        return False

    def reset_daily_counters(self) -> None:
        """Reset daily counters at start of new trading day."""
        self.daily_trade_count = 0
        self.violation_counts.clear()
        logger.info("Daily counters reset")

    def reset_hourly_counters(self) -> None:
        """Reset hourly counters at start of new hour."""
        self.hourly_trade_count = 0
        logger.info("Hourly counters reset")

    def get_real_time_status(self) -> Dict[str, Any]:
        """Get real-time risk management status.

        Returns:
            Status dictionary.
        """
        return {
            "circuit_breaker_triggered": self.circuit_breaker_triggered,
            "circuit_breaker_trigger_time": self.circuit_breaker_trigger_time,
            "circuit_breaker_reset_time": self.circuit_breaker_reset_time,
            "daily_trade_count": self.daily_trade_count,
            "hourly_trade_count": self.hourly_trade_count,
            "max_daily_trades": self.max_daily_trades,
            "max_hourly_trades": self.max_hourly_trades,
            "violation_counts": dict(self.violation_counts),
            "total_violations": len(self.violations),
            "last_trade_time": self.last_trade_time,
            "current_portfolio_value": self.current_portfolio_value,
            "peak_portfolio_value": self.peak_portfolio_value,
            "positions_count": len(self.positions),
        }
