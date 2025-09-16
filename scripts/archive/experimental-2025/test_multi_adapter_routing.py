#!/usr/bin/env python3
"""Test Multi-Adapter Routing Scenarios.

This script demonstrates and tests various routing scenarios
with multiple broker adapters.
"""

import asyncio
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.brokers.adapters.base import AdapterConfig
from fxml4.brokers.adapters.manager import AdapterManager
from fxml4.brokers.messaging.router import MessageRouter, RoutingRule
from fxml4.fix.messages.base import OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import NewOrderSingle

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RoutingTestScenarios:
    """Collection of routing test scenarios."""

    def __init__(self, router: MessageRouter, manager: AdapterManager):
        self.router = router
        self.manager = manager
        self.results = []

    async def test_size_based_routing(self):
        """Test routing based on order size."""
        logger.info("\n=== Testing Size-Based Routing ===")

        test_orders = [
            # Small order - should go to IB
            {"name": "Small Order", "qty": 10000, "expected": "ib"},
            # Medium order - should go to IB
            {"name": "Medium Order", "qty": 500000, "expected": "ib"},
            # Large order - should go to manual
            {"name": "Large Order", "qty": 2000000, "expected": "manual"},
            # Very large order - should go to manual
            {"name": "Very Large Order", "qty": 10000000, "expected": "manual"},
        ]

        for test in test_orders:
            order = NewOrderSingle(
                cl_ord_id=f"SIZE_TEST_{uuid.uuid4().hex[:8]}",
                symbol="EUR/USD",
                side=Side.BUY,
                order_qty=test["qty"],
                ord_type=OrdType.MARKET,
                time_in_force=TimeInForce.IOC,
                transact_time=datetime.utcnow(),
            )

            # Route order
            selected_broker = self.router.route_order(order)

            # Log result
            passed = selected_broker == test["expected"]
            logger.info(
                f"  {test['name']} ({test['qty']:,}): "
                f"Routed to {selected_broker} "
                f"{'✓' if passed else '✗ (expected ' + test['expected'] + ')'}"
            )

            self.results.append(("size_based", test["name"], passed))

    async def test_symbol_based_routing(self):
        """Test routing based on symbol."""
        logger.info("\n=== Testing Symbol-Based Routing ===")

        # Add symbol-specific rule
        self.router.add_rule(
            RoutingRule(
                name="fx_majors_to_ib",
                priority=2,
                conditions={"symbols": ["EUR/USD", "GBP/USD", "USD/JPY"]},
                target_brokers=["ib"],
                fallback_brokers=["manual"],
            )
        )

        test_orders = [
            # FX major - should go to IB
            {"symbol": "EUR/USD", "expected": "ib"},
            # Another FX major
            {"symbol": "GBP/USD", "expected": "ib"},
            # Exotic pair - should use default routing
            {"symbol": "USD/TRY", "expected": "ib"},  # Default route
        ]

        for test in test_orders:
            order = NewOrderSingle(
                cl_ord_id=f"SYMBOL_TEST_{uuid.uuid4().hex[:8]}",
                symbol=test["symbol"],
                side=Side.BUY,
                order_qty=100000,
                ord_type=OrdType.MARKET,
                time_in_force=TimeInForce.IOC,
                transact_time=datetime.utcnow(),
            )

            selected_broker = self.router.route_order(order)

            passed = selected_broker == test["expected"]
            logger.info(
                f"  {test['symbol']}: Routed to {selected_broker} "
                f"{'✓' if passed else '✗ (expected ' + test['expected'] + ')'}"
            )

            self.results.append(("symbol_based", test["symbol"], passed))

    async def test_failover_routing(self):
        """Test failover routing when primary broker unavailable."""
        logger.info("\n=== Testing Failover Routing ===")

        # Get available brokers before disconnection
        available_before = [
            b for b, a in self.manager.adapters.items() if a.connection.is_connected()
        ]
        logger.info(f"  Available brokers: {available_before}")

        # Disconnect IB adapter
        ib_adapter = self.manager.adapters.get("ib")
        if ib_adapter:
            await ib_adapter.disconnect()
            logger.info("  Disconnected IB adapter")

        # Update available brokers list
        available_after = [
            b for b, a in self.manager.adapters.items() if a.connection.is_connected()
        ]
        logger.info(f"  Available brokers now: {available_after}")

        # Create order that would normally go to IB
        order = NewOrderSingle(
            cl_ord_id=f"FAILOVER_TEST_{uuid.uuid4().hex[:8]}",
            symbol="EUR/USD",
            side=Side.BUY,
            order_qty=50000,  # Small order
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IOC,
            transact_time=datetime.utcnow(),
        )

        # Route with failover
        selected_broker = self.router.route_order(order, available_after)

        # Should failover to manual
        passed = selected_broker == "manual"
        logger.info(
            f"  Order routed to {selected_broker} "
            f"{'✓ (failover worked)' if passed else '✗'}"
        )

        self.results.append(("failover", "ib_to_manual", passed))

        # Reconnect IB
        if ib_adapter:
            await ib_adapter.connect()
            logger.info("  Reconnected IB adapter")

    async def test_complex_routing_rules(self):
        """Test complex routing with multiple conditions."""
        logger.info("\n=== Testing Complex Routing Rules ===")

        # Add complex rule
        self.router.add_rule(
            RoutingRule(
                name="large_fx_majors_manual",
                priority=1,
                conditions={
                    "symbols": ["EUR/USD", "GBP/USD"],
                    "min_quantity": 500000,
                    "order_types": ["LIMIT", "STOP"],
                },
                target_brokers=["manual"],
                fallback_brokers=["ib"],
            )
        )

        test_cases = [
            # Matches all conditions
            {
                "name": "Large EUR/USD Limit",
                "symbol": "EUR/USD",
                "qty": 1000000,
                "type": OrdType.LIMIT,
                "expected": "manual",
            },
            # Doesn't match quantity
            {
                "name": "Small EUR/USD Limit",
                "symbol": "EUR/USD",
                "qty": 10000,
                "type": OrdType.LIMIT,
                "expected": "ib",
            },
            # Doesn't match order type
            {
                "name": "Large EUR/USD Market",
                "symbol": "EUR/USD",
                "qty": 1000000,
                "type": OrdType.MARKET,
                "expected": "manual",  # Size rule still applies
            },
        ]

        for test in test_cases:
            order = NewOrderSingle(
                cl_ord_id=f"COMPLEX_TEST_{uuid.uuid4().hex[:8]}",
                symbol=test["symbol"],
                side=Side.BUY,
                order_qty=test["qty"],
                ord_type=test["type"],
                price=1.0850 if test["type"] == OrdType.LIMIT else None,
                time_in_force=TimeInForce.DAY,
                transact_time=datetime.utcnow(),
            )

            selected_broker = self.router.route_order(order)

            passed = selected_broker == test["expected"]
            logger.info(
                f"  {test['name']}: Routed to {selected_broker} "
                f"{'✓' if passed else '✗ (expected ' + test['expected'] + ')'}"
            )

            self.results.append(("complex", test["name"], passed))

    async def test_load_distribution(self):
        """Test load distribution across brokers."""
        logger.info("\n=== Testing Load Distribution ===")

        # Submit multiple orders and track distribution
        order_count = 20
        distribution = {"ib": 0, "manual": 0}

        for i in range(order_count):
            # Vary order size to get different routing
            qty = 10000 + (i * 50000)

            order = NewOrderSingle(
                cl_ord_id=f"LOAD_TEST_{i}_{uuid.uuid4().hex[:8]}",
                symbol="USD/JPY",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                order_qty=qty,
                ord_type=OrdType.LIMIT,
                price=110.00 + (i * 0.01),
                time_in_force=TimeInForce.DAY,
                transact_time=datetime.utcnow(),
            )

            selected_broker = self.router.route_order(order)
            distribution[selected_broker] = distribution.get(selected_broker, 0) + 1

        logger.info(f"  Order distribution: {distribution}")
        logger.info(f"  IB: {distribution.get('ib', 0)/order_count*100:.1f}%")
        logger.info(f"  Manual: {distribution.get('manual', 0)/order_count*100:.1f}%")

        # Check if distribution is reasonable
        passed = distribution.get("ib", 0) > 0 and distribution.get("manual", 0) > 0
        self.results.append(("load_distribution", "balanced", passed))

    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "=" * 60)
        logger.info("ROUTING TEST SUMMARY")
        logger.info("=" * 60)

        total_tests = len(self.results)
        passed_tests = sum(1 for _, _, passed in self.results if passed)

        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {total_tests - passed_tests}")
        logger.info(f"Success rate: {passed_tests/total_tests*100:.1f}%")

        if total_tests > passed_tests:
            logger.info("\nFailed tests:")
            for category, test, passed in self.results:
                if not passed:
                    logger.info(f"  - {category}: {test}")


async def main():
    """Main test execution."""
    logger.info("Multi-Adapter Routing Test Suite")
    logger.info("================================")

    # Create adapter manager
    manager = AdapterManager()

    # Initialize test adapters
    adapter_configs = {
        "ib": AdapterConfig(
            broker_type="ib",
            adapter_type="ib",
            connection_params={"mock": True},
            features={"market_data": True},
            limits={"max_orders_per_second": 50},
        ),
        "manual": AdapterConfig(
            broker_type="manual",
            adapter_type="manual",
            connection_params={},
            features={"auto_reject_timeout": 300, "simulate_execution": True},
            limits={},
        ),
    }

    # Initialize adapters
    for broker_type, config in adapter_configs.items():
        try:
            await manager.initialize_adapter(broker_type, config)
            logger.info(f"✓ Initialized {broker_type} adapter")
        except Exception as e:
            logger.error(f"✗ Failed to initialize {broker_type}: {e}")

    # Create router with basic rules
    router = MessageRouter()

    # Add base routing rules
    router.add_rule(
        RoutingRule(
            name="large_to_manual",
            priority=10,
            conditions={"min_quantity": 1000000},
            target_brokers=["manual"],
            fallback_brokers=["ib"],
        )
    )

    router.add_rule(
        RoutingRule(
            name="default_to_ib",
            priority=100,
            conditions={},
            target_brokers=["ib"],
            fallback_brokers=["manual"],
        )
    )

    # Run test scenarios
    tester = RoutingTestScenarios(router, manager)

    try:
        await tester.test_size_based_routing()
        await tester.test_symbol_based_routing()
        await tester.test_failover_routing()
        await tester.test_complex_routing_rules()
        await tester.test_load_distribution()

        # Print summary
        tester.print_summary()

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Cleanup
        await manager.shutdown()
        logger.info("\nTest suite completed")


if __name__ == "__main__":
    asyncio.run(main())
