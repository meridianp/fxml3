"""Risk Check Implementations.

This module provides concrete implementations of various risk checks
for the broker abstraction system.
"""

import hashlib
import logging
from datetime import datetime, time
from typing import Dict, Optional, Set

from ...fix.messages.base import OrdType, Side
from ...fix.messages.orders import NewOrderSingle
from .base import (
    RiskCheck,
    RiskCheckResult,
    RiskCheckType,
    RiskLimits,
    RiskMetrics,
    RiskViolation,
)

logger = logging.getLogger(__name__)


class PositionLimitCheck(RiskCheck):
    """Check position limits for symbols."""

    def __init__(self):
        super().__init__(RiskCheckType.POSITION_LIMIT)

    async def check(
        self, order: NewOrderSingle, limits: RiskLimits, metrics: RiskMetrics
    ) -> Optional[RiskViolation]:
        """Check if order would exceed position limits."""
        symbol = order.symbol
        current_position = metrics.positions.get(symbol)
        current_qty = current_position.quantity if current_position else 0

        # Calculate new position after order
        order_qty = order.order_qty if order.side == Side.BUY else -order.order_qty
        new_position = current_qty + order_qty

        # Check symbol-specific limit
        if symbol in limits.max_position_size:
            limit = limits.max_position_size[symbol]
            if abs(new_position) > limit:
                return RiskViolation(
                    check_type=self.check_type,
                    result=RiskCheckResult.FAIL,
                    message=f"Position limit exceeded for {symbol}",
                    current_value=abs(new_position),
                    limit_value=limit,
                    can_override=True,
                    override_level="risk_manager",
                )

        # Check notional limit
        price = order.price if hasattr(order, "price") and order.price else 0
        if price > 0:
            new_notional = abs(new_position * price)
            if new_notional > limits.max_single_position_notional:
                return RiskViolation(
                    check_type=self.check_type,
                    result=RiskCheckResult.FAIL,
                    message=f"Position notional limit exceeded for {symbol}",
                    current_value=new_notional,
                    limit_value=limits.max_single_position_notional,
                    can_override=True,
                    override_level="senior_trader",
                )

        return None


class OrderSizeLimitCheck(RiskCheck):
    """Check order size limits."""

    def __init__(self):
        super().__init__(RiskCheckType.ORDER_SIZE_LIMIT)

    async def check(
        self, order: NewOrderSingle, limits: RiskLimits, metrics: RiskMetrics
    ) -> Optional[RiskViolation]:
        """Check if order size is within limits."""
        symbol = order.symbol
        order_qty = order.order_qty

        # Check minimum order size
        if order_qty < limits.min_order_size:
            return RiskViolation(
                check_type=self.check_type,
                result=RiskCheckResult.FAIL,
                message=f"Order size below minimum for {symbol}",
                current_value=order_qty,
                limit_value=limits.min_order_size,
                can_override=False,
            )

        # Check symbol-specific maximum
        if symbol in limits.max_order_size:
            max_size = limits.max_order_size[symbol]
            if order_qty > max_size:
                return RiskViolation(
                    check_type=self.check_type,
                    result=RiskCheckResult.FAIL,
                    message=f"Order size exceeds maximum for {symbol}",
                    current_value=order_qty,
                    limit_value=max_size,
                    can_override=True,
                    override_level="risk_manager",
                )

        # Check notional limit
        price = order.price if hasattr(order, "price") and order.price else 0
        if price > 0:
            order_notional = order_qty * price
            if order_notional > limits.max_order_notional:
                return RiskViolation(
                    check_type=self.check_type,
                    result=RiskCheckResult.FAIL,
                    message=f"Order notional exceeds limit",
                    current_value=order_notional,
                    limit_value=limits.max_order_notional,
                    can_override=True,
                    override_level="senior_trader",
                )

        return None


class DailyLossLimitCheck(RiskCheck):
    """Check daily loss limits."""

    def __init__(self):
        super().__init__(RiskCheckType.DAILY_LOSS_LIMIT)

    async def check(
        self, order: NewOrderSingle, limits: RiskLimits, metrics: RiskMetrics
    ) -> Optional[RiskViolation]:
        """Check if daily loss limit would be exceeded."""
        current_daily_pnl = metrics.daily_pnl

        # Only check if we're already in a loss
        if current_daily_pnl < 0:
            daily_loss = abs(current_daily_pnl)

            # Warn at 80% of limit
            if daily_loss > limits.max_daily_loss * 0.8:
                if daily_loss >= limits.max_daily_loss:
                    return RiskViolation(
                        check_type=self.check_type,
                        result=RiskCheckResult.FAIL,
                        message="Daily loss limit reached",
                        current_value=daily_loss,
                        limit_value=limits.max_daily_loss,
                        can_override=True,
                        override_level="senior_trader",
                    )
                else:
                    return RiskViolation(
                        check_type=self.check_type,
                        result=RiskCheckResult.WARN,
                        message="Approaching daily loss limit",
                        current_value=daily_loss,
                        limit_value=limits.max_daily_loss,
                        can_override=False,
                    )

        return None


class PriceDeviationCheck(RiskCheck):
    """Check for excessive price deviation from market."""

    def __init__(self, market_prices: Optional[Dict[str, float]] = None):
        super().__init__(RiskCheckType.PRICE_DEVIATION)
        self.market_prices = market_prices or {}

    def update_market_price(self, symbol: str, price: float):
        """Update market price for symbol."""
        self.market_prices[symbol] = price

    async def check(
        self, order: NewOrderSingle, limits: RiskLimits, metrics: RiskMetrics
    ) -> Optional[RiskViolation]:
        """Check if order price deviates too much from market."""
        # Only check limit orders
        if order.ord_type != OrdType.LIMIT:
            return None

        symbol = order.symbol
        order_price = order.price if hasattr(order, "price") else None

        if not order_price or symbol not in self.market_prices:
            return None

        market_price = self.market_prices[symbol]
        deviation_pct = abs((order_price - market_price) / market_price) * 100

        if deviation_pct > limits.max_price_deviation_pct:
            return RiskViolation(
                check_type=self.check_type,
                result=RiskCheckResult.WARN,
                message=f"Order price deviates {deviation_pct:.2f}% from market",
                current_value=deviation_pct,
                limit_value=limits.max_price_deviation_pct,
                can_override=True,
                override_level="risk_manager",
            )

        return None


class SymbolRestrictionCheck(RiskCheck):
    """Check symbol trading restrictions."""

    def __init__(self):
        super().__init__(RiskCheckType.SYMBOL_RESTRICTION)

    async def check(
        self, order: NewOrderSingle, limits: RiskLimits, metrics: RiskMetrics
    ) -> Optional[RiskViolation]:
        """Check if symbol is allowed for trading."""
        symbol = order.symbol

        # Check blocked symbols
        if symbol in limits.blocked_symbols:
            return RiskViolation(
                check_type=self.check_type,
                result=RiskCheckResult.FAIL,
                message=f"Symbol {symbol} is blocked for trading",
                current_value=symbol,
                limit_value="blocked_list",
                can_override=True,
                override_level="compliance",
            )

        # Check allowed symbols list if specified
        if limits.allowed_symbols and symbol not in limits.allowed_symbols:
            return RiskViolation(
                check_type=self.check_type,
                result=RiskCheckResult.FAIL,
                message=f"Symbol {symbol} not in allowed list",
                current_value=symbol,
                limit_value="allowed_list",
                can_override=True,
                override_level="compliance",
            )

        return None


class TimeRestrictionCheck(RiskCheck):
    """Check time-based trading restrictions."""

    def __init__(self):
        super().__init__(RiskCheckType.TIME_RESTRICTION)

    async def check(
        self, order: NewOrderSingle, limits: RiskLimits, metrics: RiskMetrics
    ) -> Optional[RiskViolation]:
        """Check if trading is allowed at current time."""
        current_time = datetime.utcnow().time()
        current_hour = current_time.hour

        # Check restricted hours
        for start_hour, end_hour in limits.restricted_hours:
            if start_hour <= current_hour < end_hour:
                return RiskViolation(
                    check_type=self.check_type,
                    result=RiskCheckResult.FAIL,
                    message=f"Trading restricted between {start_hour}:00-{end_hour}:00 UTC",
                    current_value=f"{current_hour}:00",
                    limit_value=f"{start_hour}:00-{end_hour}:00",
                    can_override=True,
                    override_level="senior_trader",
                )

        return None


class DuplicateOrderCheck(RiskCheck):
    """Check for duplicate orders."""

    def __init__(self, lookback_seconds: int = 60):
        super().__init__(RiskCheckType.DUPLICATE_ORDER)
        self.lookback_seconds = lookback_seconds
        self.recent_orders: Dict[str, datetime] = {}

    def _get_order_hash(self, order: NewOrderSingle) -> str:
        """Generate hash for order to detect duplicates."""
        key = f"{order.symbol}:{order.side.value}:{order.order_qty}:{order.ord_type.value}"
        if hasattr(order, "price") and order.price:
            key += f":{order.price}"
        return hashlib.md5(key.encode()).hexdigest()

    async def check(
        self, order: NewOrderSingle, limits: RiskLimits, metrics: RiskMetrics
    ) -> Optional[RiskViolation]:
        """Check if order is a duplicate."""
        order_hash = self._get_order_hash(order)
        now = datetime.utcnow()

        # Clean old entries
        self.recent_orders = {
            h: t
            for h, t in self.recent_orders.items()
            if (now - t).total_seconds() < self.lookback_seconds
        }

        # Check for duplicate
        if order_hash in self.recent_orders:
            last_time = self.recent_orders[order_hash]
            seconds_ago = (now - last_time).total_seconds()

            return RiskViolation(
                check_type=self.check_type,
                result=RiskCheckResult.WARN,
                message=f"Duplicate order detected ({seconds_ago:.1f}s ago)",
                current_value=order_hash,
                limit_value=f"{self.lookback_seconds}s",
                can_override=True,
                override_level="risk_manager",
            )

        # Record this order
        self.recent_orders[order_hash] = now
        return None


class CounterpartyLimitCheck(RiskCheck):
    """Check counterparty/broker exposure limits."""

    def __init__(self):
        super().__init__(RiskCheckType.COUNTERPARTY_LIMIT)
        self.broker_order_counts: Dict[str, int] = {}

    async def check(
        self, order: NewOrderSingle, limits: RiskLimits, metrics: RiskMetrics
    ) -> Optional[RiskViolation]:
        """Check broker exposure limits."""
        # This check requires broker information from the routing decision
        # In practice, this would be passed in or determined by the router
        broker = getattr(order, "_target_broker", None)
        if not broker:
            return None

        # Check order count limit
        if broker in limits.max_orders_per_broker:
            current_count = self.broker_order_counts.get(broker, 0)
            max_count = limits.max_orders_per_broker[broker]

            if current_count >= max_count:
                return RiskViolation(
                    check_type=self.check_type,
                    result=RiskCheckResult.FAIL,
                    message=f"Max orders per broker limit reached for {broker}",
                    current_value=current_count,
                    limit_value=max_count,
                    can_override=True,
                    override_level="risk_manager",
                )

        # Check notional exposure limit
        if broker in limits.max_notional_per_broker:
            current_exposure = metrics.broker_exposure.get(broker, 0)
            max_exposure = limits.max_notional_per_broker[broker]

            price = order.price if hasattr(order, "price") and order.price else 0
            if price > 0:
                order_notional = order.order_qty * price
                new_exposure = current_exposure + order_notional

                if new_exposure > max_exposure:
                    return RiskViolation(
                        check_type=self.check_type,
                        result=RiskCheckResult.FAIL,
                        message=f"Broker notional limit exceeded for {broker}",
                        current_value=new_exposure,
                        limit_value=max_exposure,
                        can_override=True,
                        override_level="senior_trader",
                    )

        return None

    def increment_broker_count(self, broker: str):
        """Increment order count for broker."""
        self.broker_order_counts[broker] = self.broker_order_counts.get(broker, 0) + 1

    def decrement_broker_count(self, broker: str):
        """Decrement order count for broker."""
        if broker in self.broker_order_counts:
            self.broker_order_counts[broker] = max(
                0, self.broker_order_counts[broker] - 1
            )
