#!/usr/bin/env python3
"""Test Script for Risk Management Integration.

This script demonstrates the risk management system integrated with
the broker abstraction layer.
"""

import asyncio
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.brokers.adapters.base import AdapterConfig
from fxml4.brokers.adapters.manager import BrokerAdapterManager
from fxml4.brokers.risk import (
    FXRiskManager,
    RiskAwareBrokerManager,
    RiskLimits,
    create_risk_limits_from_config,
)
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import NewOrderSingle

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def load_risk_config() -> RiskLimits:
    """Load risk limits from configuration file."""
    config_path = Path(__file__).parent.parent / "config" / "risk_limits.yaml"

    if config_path.exists():
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return create_risk_limits_from_config(config)
    else:
        logger.warning("Risk config not found, using defaults")
        return RiskLimits()


async def create_test_order(
    symbol: str = "EUR/USD",
    side: Side = Side.BUY,
    quantity: float = 100000,
    order_type: OrdType = OrdType.LIMIT,
    price: float = 1.0850,
) -> NewOrderSingle:
    """Create a test order."""
    return NewOrderSingle(
        cl_ord_id=f"TEST_{uuid.uuid4().hex[:8]}",
        symbol=symbol,
        side=side,
        order_qty=quantity,
        ord_type=order_type,
        price=price if order_type == OrdType.LIMIT else None,
        time_in_force=TimeInForce.GTC,
        transact_time=datetime.utcnow(),
    )


async def test_risk_checks():
    """Test various risk check scenarios."""
    print("\n" + "=" * 60)
    print("Risk Management Integration Test")
    print("=" * 60)

    # Load configuration
    limits = await load_risk_config()

    # Create risk manager
    risk_manager = FXRiskManager(limits, enable_all_checks=True)

    # Create adapter manager with mock adapter
    adapter_manager = BrokerAdapterManager()

    # Add a mock adapter
    mock_config = AdapterConfig(
        adapter_id="mock",
        broker_type="manual",
        broker_name="Mock Broker",
        connection_params={},
        features={"mock": True},
        enabled=True,
    )

    # Note: We'll use the manual adapter as a mock for this test
    from fxml4.brokers.adapters.manual_adapter import ManualBrokerAdapter

    mock_adapter = ManualBrokerAdapter(mock_config)
    await mock_adapter.connect()
    adapter_manager.add_adapter("mock", mock_adapter)

    # Create risk-aware broker manager
    risk_broker = RiskAwareBrokerManager(adapter_manager, risk_manager)

    # Update market prices for deviation checks
    risk_broker.update_market_prices(
        {"EUR/USD": 1.0850, "GBP/USD": 1.2650, "USD/JPY": 110.50}
    )

    print("\n1. Testing Normal Order (Should Pass)")
    print("-" * 40)

    order1 = await create_test_order(
        symbol="EUR/USD", side=Side.BUY, quantity=100000, price=1.0850
    )

    result1 = await risk_broker.submit_order(order1, preferred_broker="mock")
    print(f"Order: {order1.cl_ord_id}")
    print(f"Result: {result1['status']}")
    print(f"Risk Check: {result1['risk_check']}")
    if result1["violations"]:
        print("Violations:")
        for v in result1["violations"]:
            print(f"  - {v['check_type']}: {v['message']}")

    print("\n2. Testing Oversized Order (Should Fail)")
    print("-" * 40)

    order2 = await create_test_order(
        symbol="EUR/USD",
        side=Side.BUY,
        quantity=10000000,  # 10M - exceeds limits
        price=1.0850,
    )

    result2 = await risk_broker.submit_order(order2, preferred_broker="mock")
    print(f"Order: {order2.cl_ord_id}")
    print(f"Result: {result2['status']}")
    print(f"Risk Check: {result2['risk_check']}")
    if result2["violations"]:
        print("Violations:")
        for v in result2["violations"]:
            print(f"  - {v['check_type']}: {v['message']}")
            if v["can_override"]:
                print(f"    Can override: Yes (Level: {v['override_level']})")

    print("\n3. Testing Price Deviation (Should Warn)")
    print("-" * 40)

    order3 = await create_test_order(
        symbol="EUR/USD",
        side=Side.BUY,
        quantity=100000,
        price=1.1200,  # ~3.3% above market
    )

    result3 = await risk_broker.submit_order(order3, preferred_broker="mock")
    print(f"Order: {order3.cl_ord_id}")
    print(f"Result: {result3['status']}")
    print(f"Risk Check: {result3['risk_check']}")
    if result3["violations"]:
        print("Violations:")
        for v in result3["violations"]:
            print(f"  - {v['check_type']}: {v['message']} ({v['result']})")

    print("\n4. Testing Blocked Symbol (Should Fail)")
    print("-" * 40)

    order4 = await create_test_order(
        symbol="TRY/USD",  # Blocked in config
        side=Side.BUY,
        quantity=100000,
        price=8.5000,
    )

    result4 = await risk_broker.submit_order(order4, preferred_broker="mock")
    print(f"Order: {order4.cl_ord_id}")
    print(f"Result: {result4['status']}")
    print(f"Risk Check: {result4['risk_check']}")
    if result4["violations"]:
        print("Violations:")
        for v in result4["violations"]:
            print(f"  - {v['check_type']}: {v['message']}")

    print("\n5. Testing Duplicate Order (Should Warn)")
    print("-" * 40)

    order5a = await create_test_order(
        symbol="GBP/USD", side=Side.SELL, quantity=50000, price=1.2650
    )

    # Submit first order
    result5a = await risk_broker.submit_order(order5a, preferred_broker="mock")
    print(f"First order: {order5a.cl_ord_id} - {result5a['status']}")

    # Create identical order
    order5b = await create_test_order(
        symbol="GBP/USD", side=Side.SELL, quantity=50000, price=1.2650
    )

    # Submit duplicate
    result5b = await risk_broker.submit_order(order5b, preferred_broker="mock")
    print(f"Duplicate order: {order5b.cl_ord_id}")
    print(f"Result: {result5b['status']}")
    if result5b["violations"]:
        print("Violations:")
        for v in result5b["violations"]:
            print(f"  - {v['check_type']}: {v['message']} ({v['result']})")

    print("\n6. Testing Order with Override")
    print("-" * 40)

    # Use the oversized order from test 2
    oversized_order = await create_test_order(
        symbol="EUR/USD", side=Side.BUY, quantity=10000000, price=1.0850
    )

    print("Submitting oversized order with senior trader override...")
    result6 = await risk_broker.submit_order_with_override(
        oversized_order,
        override_user="senior_trader_1",
        override_level="senior_trader",
        override_reason="Large institutional client order",
        preferred_broker="mock",
    )

    print(f"Order: {oversized_order.cl_ord_id}")
    print(f"Result: {result6['status']}")
    print(f"Risk Check: {result6['risk_check']}")
    if result6.get("override"):
        print(
            f"Override: {result6['override']['user']} - {result6['override']['reason']}"
        )

    print("\n7. Risk Summary")
    print("-" * 40)

    summary = risk_broker.get_risk_summary()
    print("Risk Metrics:")
    print(f"  Total Notional: ${summary['metrics']['total_notional']:,.2f}")
    print(f"  Daily P&L: ${summary['metrics']['daily_pnl']:,.2f}")
    print(f"  Open Orders: {summary['metrics']['open_orders']}")
    print(f"  Position Count: {summary['metrics']['position_count']}")

    print("\nRisk Limits:")
    print(
        f"  Max Portfolio Notional: ${summary['limits']['max_portfolio_notional']:,.2f}"
    )
    print(f"  Max Daily Loss: ${summary['limits']['max_daily_loss']:,.2f}")
    print(f"  Max Order Notional: ${summary['limits']['max_order_notional']:,.2f}")

    print("\nEnabled Risk Checks:")
    for check in summary["enabled_checks"]:
        print(f"  - {check}")

    # Cleanup
    await adapter_manager.disconnect_all()

    print("\n" + "=" * 60)
    print("Risk Integration Test Complete")
    print("=" * 60)


async def test_position_updates():
    """Test position tracking and P&L calculation."""
    print("\n" + "=" * 60)
    print("Position Tracking Test")
    print("=" * 60)

    limits = RiskLimits()
    risk_manager = FXRiskManager(limits, enable_all_checks=False)

    print("\n1. Opening Position")
    print("-" * 40)

    # Buy 100K EUR/USD at 1.0850
    await risk_manager.update_position("EUR/USD", 100000, 1.0850)
    position = risk_manager.get_position("EUR/USD")

    print(f"Symbol: {position.symbol}")
    print(f"Quantity: {position.quantity:,.0f}")
    print(f"Avg Price: {position.average_price:.4f}")
    print(f"Notional: ${position.notional_value:,.2f}")

    print("\n2. Adding to Position")
    print("-" * 40)

    # Buy another 50K at 1.0860
    await risk_manager.update_position("EUR/USD", 50000, 1.0860)
    position = risk_manager.get_position("EUR/USD")

    print(f"New Quantity: {position.quantity:,.0f}")
    print(f"New Avg Price: {position.average_price:.4f}")
    print(f"New Notional: ${position.notional_value:,.2f}")

    print("\n3. Partial Close")
    print("-" * 40)

    # Sell 75K at 1.0870
    await risk_manager.update_position("EUR/USD", -75000, 1.0870)
    position = risk_manager.get_position("EUR/USD")

    print(f"Remaining Quantity: {position.quantity:,.0f}")
    print(f"Realized P&L: ${position.realized_pnl:,.2f}")

    print("\n4. Portfolio Summary")
    print("-" * 40)

    total_notional = risk_manager.get_total_notional()
    daily_pnl = risk_manager.get_daily_pnl()

    print(f"Total Portfolio Notional: ${total_notional:,.2f}")
    print(f"Daily P&L: ${daily_pnl:,.2f}")


async def main():
    """Run all tests."""
    try:
        # Test risk checks
        await test_risk_checks()

        # Test position tracking
        await test_position_updates()

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
