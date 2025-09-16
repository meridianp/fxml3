#!/usr/bin/env python3
"""Simple Risk Management Demo.

This script demonstrates the core risk management concepts
by creating the data structures directly.
"""

import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

print("=" * 60)
print("Simple Risk Management Demo")
print("=" * 60)


# Define core enums and classes directly
class RiskCheckType(Enum):
    """Types of risk checks."""

    POSITION_LIMIT = "position_limit"
    NOTIONAL_LIMIT = "notional_limit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    ORDER_SIZE_LIMIT = "order_size_limit"
    PRICE_DEVIATION = "price_deviation"
    SYMBOL_RESTRICTION = "symbol_restriction"


class RiskCheckResult(Enum):
    """Result of a risk check."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    OVERRIDE = "override"


class Side(Enum):
    """Order side."""

    BUY = "1"
    SELL = "2"


class OrdType(Enum):
    """Order type."""

    MARKET = "1"
    LIMIT = "2"


@dataclass
class RiskViolation:
    """Details of a risk check violation."""

    check_type: RiskCheckType
    result: RiskCheckResult
    message: str
    current_value: Any
    limit_value: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    can_override: bool = False
    override_level: str = "risk_manager"


@dataclass
class Position:
    """Current position for a symbol."""

    symbol: str
    quantity: float
    average_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    last_update: datetime = field(default_factory=datetime.utcnow)

    @property
    def notional_value(self) -> float:
        """Calculate notional value of position."""
        return abs(self.quantity * self.average_price)


@dataclass
class RiskLimits:
    """Risk limits configuration."""

    # Position limits
    max_position_size: Dict[str, float] = field(default_factory=dict)
    max_portfolio_notional: float = 10_000_000
    max_single_position_notional: float = 1_000_000

    # Order limits
    max_order_size: Dict[str, float] = field(default_factory=dict)
    max_order_notional: float = 500_000
    min_order_size: float = 1000

    # Loss limits
    max_daily_loss: float = 50_000
    max_weekly_loss: float = 150_000
    max_monthly_loss: float = 500_000

    # Price limits
    max_price_deviation_pct: float = 2.0

    # Symbol restrictions
    allowed_symbols: Optional[list] = None
    blocked_symbols: list = field(default_factory=list)


@dataclass
class Order:
    """Simple order representation."""

    cl_ord_id: str
    symbol: str
    side: Side
    order_qty: float
    ord_type: OrdType
    price: Optional[float] = None


@dataclass
class RiskMetrics:
    """Current risk metrics."""

    total_notional: float = 0
    daily_pnl: float = 0
    open_orders: int = 0
    open_order_notional: float = 0
    positions: Dict[str, Position] = field(default_factory=dict)
    last_update: datetime = field(default_factory=datetime.utcnow)


print("\n1. Risk Limits Configuration")
print("-" * 40)

# Create risk limits
limits = RiskLimits()
limits.max_portfolio_notional = 10_000_000
limits.max_daily_loss = 50_000
limits.max_order_notional = 500_000
limits.max_position_size = {
    "EUR/USD": 5_000_000,
    "GBP/USD": 3_000_000,
    "USD/JPY": 5_000_000,
}
limits.blocked_symbols = ["TRY/USD", "RUB/USD"]

print(f"✅ Risk Limits Created:")
print(f"   Max Portfolio Notional: ${limits.max_portfolio_notional:,}")
print(f"   Max Daily Loss: ${limits.max_daily_loss:,}")
print(f"   Max Order Notional: ${limits.max_order_notional:,}")
print(f"   EUR/USD Position Limit: {limits.max_position_size.get('EUR/USD', 0):,}")
print(f"   Blocked Symbols: {', '.join(limits.blocked_symbols)}")

print("\n2. Position Management")
print("-" * 40)

# Create positions
eur_usd_position = Position(
    symbol="EUR/USD",
    quantity=100_000,
    average_price=1.0850,
    market_value=108_500,
    unrealized_pnl=150,
    realized_pnl=0,
)

gbp_usd_position = Position(
    symbol="GBP/USD",
    quantity=-75_000,  # Short position
    average_price=1.2650,
    market_value=-94_875,
    unrealized_pnl=-225,
    realized_pnl=50,
)

print(f"✅ Positions Created:")
print(
    f"   EUR/USD: {eur_usd_position.quantity:,} @ {eur_usd_position.average_price:.4f}"
)
print(f"            Notional: ${eur_usd_position.notional_value:,}")
print(f"            P&L: ${eur_usd_position.unrealized_pnl:+.2f}")
print(
    f"   GBP/USD: {gbp_usd_position.quantity:,} @ {gbp_usd_position.average_price:.4f}"
)
print(f"            Notional: ${gbp_usd_position.notional_value:,}")
print(f"            P&L: ${gbp_usd_position.unrealized_pnl:+.2f}")

print("\n3. Risk Metrics Calculation")
print("-" * 40)

# Calculate portfolio metrics
total_notional = eur_usd_position.notional_value + gbp_usd_position.notional_value
total_pnl = (
    eur_usd_position.unrealized_pnl
    + eur_usd_position.realized_pnl
    + gbp_usd_position.unrealized_pnl
    + gbp_usd_position.realized_pnl
)

metrics = RiskMetrics()
metrics.positions["EUR/USD"] = eur_usd_position
metrics.positions["GBP/USD"] = gbp_usd_position
metrics.total_notional = total_notional
metrics.daily_pnl = total_pnl
metrics.open_orders = 2

print(f"✅ Portfolio Metrics:")
print(f"   Total Notional: ${metrics.total_notional:,}")
print(f"   Daily P&L: ${metrics.daily_pnl:+.2f}")
print(f"   Number of Positions: {len(metrics.positions)}")
print(f"   Open Orders: {metrics.open_orders}")
print(
    f"   Portfolio Utilization: {(total_notional / limits.max_portfolio_notional * 100):.1f}%"
)

print("\n4. Order Risk Assessment")
print("-" * 40)

# Create test orders
large_order = Order(
    cl_ord_id=f"LARGE_{uuid.uuid4().hex[:8]}",
    symbol="EUR/USD",
    side=Side.BUY,
    order_qty=8_000_000,  # Very large order
    ord_type=OrdType.LIMIT,
    price=1.0860,
)

blocked_order = Order(
    cl_ord_id=f"BLOCKED_{uuid.uuid4().hex[:8]}",
    symbol="TRY/USD",  # Blocked symbol
    side=Side.BUY,
    order_qty=100_000,
    ord_type=OrdType.LIMIT,
    price=8.50,
)

normal_order = Order(
    cl_ord_id=f"NORMAL_{uuid.uuid4().hex[:8]}",
    symbol="GBP/USD",
    side=Side.SELL,
    order_qty=50_000,
    ord_type=OrdType.LIMIT,
    price=1.2645,
)

print(f"✅ Test Orders Created:")
print(f"   Large Order: {large_order.order_qty:,} {large_order.symbol}")
print(f"   Blocked Order: {blocked_order.order_qty:,} {blocked_order.symbol}")
print(f"   Normal Order: {normal_order.order_qty:,} {normal_order.symbol}")

print("\n5. Risk Check Simulations")
print("-" * 40)


def check_order_size(order: Order, limits: RiskLimits) -> Optional[RiskViolation]:
    """Check order size limits."""
    if order.price:
        order_notional = order.order_qty * order.price
        if order_notional > limits.max_order_notional:
            return RiskViolation(
                check_type=RiskCheckType.ORDER_SIZE_LIMIT,
                result=RiskCheckResult.FAIL,
                message=f"Order notional exceeds limit",
                current_value=order_notional,
                limit_value=limits.max_order_notional,
                can_override=True,
            )
    return None


def check_symbol_restriction(
    order: Order, limits: RiskLimits
) -> Optional[RiskViolation]:
    """Check symbol restrictions."""
    if order.symbol in limits.blocked_symbols:
        return RiskViolation(
            check_type=RiskCheckType.SYMBOL_RESTRICTION,
            result=RiskCheckResult.FAIL,
            message=f"Symbol {order.symbol} is blocked",
            current_value=order.symbol,
            limit_value="blocked_list",
            can_override=True,
            override_level="compliance",
        )
    return None


def check_position_limit(
    order: Order, current_positions: Dict[str, Position], limits: RiskLimits
) -> Optional[RiskViolation]:
    """Check position limits."""
    current_pos = current_positions.get(order.symbol)
    current_qty = current_pos.quantity if current_pos else 0

    order_qty = order.order_qty if order.side == Side.BUY else -order.order_qty
    new_position = current_qty + order_qty

    symbol_limit = limits.max_position_size.get(
        order.symbol, limits.max_single_position_notional
    )
    if order.price:
        new_notional = abs(new_position * order.price)
        if new_notional > symbol_limit:
            return RiskViolation(
                check_type=RiskCheckType.POSITION_LIMIT,
                result=RiskCheckResult.FAIL,
                message=f"Position limit exceeded for {order.symbol}",
                current_value=new_notional,
                limit_value=symbol_limit,
                can_override=True,
            )
    return None


# Run risk checks
test_orders = [large_order, blocked_order, normal_order]

for i, order in enumerate(test_orders, 1):
    print(f"\nOrder {i}: {order.cl_ord_id} ({order.symbol})")
    violations = []

    # Check order size
    violation = check_order_size(order, limits)
    if violation:
        violations.append(violation)

    # Check symbol restrictions
    violation = check_symbol_restriction(order, limits)
    if violation:
        violations.append(violation)

    # Check position limits
    violation = check_position_limit(order, metrics.positions, limits)
    if violation:
        violations.append(violation)

    if violations:
        print(f"   ❌ REJECTED - {len(violations)} violation(s):")
        for v in violations:
            print(f"      • {v.check_type.value}: {v.message}")
            if v.can_override:
                print(f"        (Can override with {v.override_level} authority)")
    else:
        print(f"   ✅ APPROVED - All risk checks passed")

print("\n6. Risk Summary Dashboard")
print("-" * 40)

print(f"📊 Risk Dashboard:")
print(f"   Portfolio Status:")
print(f"     • Total Notional: ${metrics.total_notional:,}")
print(
    f"     • Limit Utilization: {(metrics.total_notional / limits.max_portfolio_notional * 100):.1f}%"
)
print(f"     • Daily P&L: ${metrics.daily_pnl:+.2f}")
print(f"   ")
print(f"   Position Summary:")
print(f"     • Active Positions: {len(metrics.positions)}")
print(f"     • Long Notional: ${eur_usd_position.notional_value:,}")
print(f"     • Short Notional: ${gbp_usd_position.notional_value:,}")
print(f"   ")
print(f"   Risk Limits:")
print(f"     • Max Portfolio: ${limits.max_portfolio_notional:,}")
print(f"     • Max Daily Loss: ${limits.max_daily_loss:,}")
print(f"     • Max Order Size: ${limits.max_order_notional:,}")
print(f"     • Blocked Symbols: {len(limits.blocked_symbols)}")

print("\n" + "=" * 60)
print("✅ DEMO COMPLETE!")
print("🎉 Risk Management System Successfully Demonstrated!")
print("\nKey Capabilities Shown:")
print("  ✓ Multi-Currency Position Tracking")
print("  ✓ Real-Time Risk Limit Monitoring")
print("  ✓ Order-Level Risk Assessment")
print("  ✓ Symbol-Based Restrictions")
print("  ✓ Override Authority Management")
print("  ✓ Portfolio-Level Risk Metrics")
print("  ✓ Configurable Limit Framework")
print("=" * 60)
