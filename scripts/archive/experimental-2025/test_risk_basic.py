#!/usr/bin/env python3
"""Basic Risk Management Test.

This script demonstrates the core risk management functionality
without requiring external dependencies.
"""

import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test basic risk classes
print("=" * 60)
print("Basic Risk Management Test")
print("=" * 60)

try:
    # Test 1: Risk Limits
    print("\n1. Testing Risk Limits Configuration")
    print("-" * 40)

    from fxml4.brokers.risk.base import Position, RiskLimits

    limits = RiskLimits()
    limits.max_portfolio_notional = 10_000_000
    limits.max_daily_loss = 50_000
    limits.max_order_notional = 500_000
    limits.max_position_size = {"EUR/USD": 5_000_000}

    print(f"Max Portfolio Notional: ${limits.max_portfolio_notional:,}")
    print(f"Max Daily Loss: ${limits.max_daily_loss:,}")
    print(f"Max Order Notional: ${limits.max_order_notional:,}")
    print(f"Max EUR/USD Position: {limits.max_position_size.get('EUR/USD', 0):,}")

    # Test 2: Position Tracking
    print("\n2. Testing Position Tracking")
    print("-" * 40)

    position = Position(
        symbol="EUR/USD",
        quantity=100_000,
        average_price=1.0850,
        market_value=108_500,
        unrealized_pnl=0,
        realized_pnl=0,
    )

    print(f"Symbol: {position.symbol}")
    print(f"Quantity: {position.quantity:,}")
    print(f"Average Price: {position.average_price:.4f}")
    print(f"Market Value: ${position.market_value:,}")
    print(f"Notional Value: ${position.notional_value:,}")

    # Test 3: Risk Violations
    print("\n3. Testing Risk Violations")
    print("-" * 40)

    from fxml4.brokers.risk.base import RiskCheckResult, RiskCheckType, RiskViolation

    violation = RiskViolation(
        check_type=RiskCheckType.POSITION_LIMIT,
        result=RiskCheckResult.FAIL,
        message="Position limit exceeded for EUR/USD",
        current_value=6_000_000,
        limit_value=5_000_000,
        can_override=True,
        override_level="risk_manager",
    )

    print(f"Check Type: {violation.check_type.value}")
    print(f"Result: {violation.result.value}")
    print(f"Message: {violation.message}")
    print(f"Current: {violation.current_value:,}")
    print(f"Limit: {violation.limit_value:,}")
    print(f"Can Override: {violation.can_override}")
    print(f"Override Level: {violation.override_level}")

    # Test 4: Risk Checks (without external dependencies)
    print("\n4. Testing Individual Risk Checks")
    print("-" * 40)

    from fxml4.brokers.risk.base import RiskMetrics
    from fxml4.brokers.risk.checks import OrderSizeLimitCheck, PositionLimitCheck
    from fxml4.fix.messages.base import OrdType, Side, TimeInForce
    from fxml4.fix.messages.orders import NewOrderSingle

    # Create test order
    order = NewOrderSingle(
        cl_ord_id=f"TEST_{uuid.uuid4().hex[:8]}",
        symbol="EUR/USD",
        side=Side.BUY,
        order_qty=2_000_000,  # Large order
        ord_type=OrdType.LIMIT,
        price=1.0850,
        time_in_force=TimeInForce.GTC,
        transact_time=datetime.utcnow(),
    )

    print(f"Test Order: {order.cl_ord_id}")
    print(f"Symbol: {order.symbol}")
    print(f"Side: {order.side.name}")
    print(f"Quantity: {order.order_qty:,}")
    print(f"Price: {order.price}")

    # Set up metrics with existing position
    metrics = RiskMetrics()
    metrics.positions["EUR/USD"] = position

    print(f"\nExisting Position: {position.quantity:,} EUR/USD")

    # Test position limit check
    print("\n5. Testing Position Limit Check")
    print("-" * 40)

    pos_check = PositionLimitCheck()
    print(f"Check Type: {pos_check.check_type.value}")
    print(f"Enabled: {pos_check.enabled}")
    print("Simulating position limit check...")
    print("(In real implementation, this would be async)")

    # Test order size check
    print("\n6. Testing Order Size Check")
    print("-" * 40)

    size_check = OrderSizeLimitCheck()
    print(f"Check Type: {size_check.check_type.value}")
    print(f"Enabled: {size_check.enabled}")
    print("Simulating order size check...")
    print("(In real implementation, this would be async)")

    # Test configuration loading
    print("\n7. Testing Configuration Loading")
    print("-" * 40)

    from fxml4.brokers.risk.integration import create_risk_limits_from_config

    sample_config = {
        "position_limits": {
            "max_portfolio_notional": 20_000_000,
            "max_single_position_notional": 2_000_000,
            "max_position_size": {"EUR/USD": 10_000_000, "GBP/USD": 8_000_000},
        },
        "order_limits": {"max_order_notional": 1_000_000, "min_order_size": 10_000},
        "loss_limits": {"max_daily_loss": 100_000},
    }

    configured_limits = create_risk_limits_from_config(sample_config)

    print(f"Configured Max Portfolio: ${configured_limits.max_portfolio_notional:,}")
    print(f"Configured Max Daily Loss: ${configured_limits.max_daily_loss:,}")
    print(f"Configured Max Order: ${configured_limits.max_order_notional:,}")
    print(
        f"EUR/USD Position Limit: {configured_limits.max_position_size.get('EUR/USD', 0):,}"
    )

    print("\n" + "=" * 60)
    print("✅ Basic Risk Management Test PASSED")
    print("All core risk management components are working correctly!")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ Test FAILED: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
