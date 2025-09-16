#!/usr/bin/env python3
"""Validate FIX Broker Abstraction Architecture.

This script validates that all components of the broker abstraction
system are properly implemented and working together.
"""

import asyncio
import importlib
import inspect
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ArchitectureValidator:
    """Validates the broker abstraction architecture."""

    def __init__(self):
        self.results = {}
        self.issues = []

    def check_component(self, name: str, checks: List[Tuple[str, callable]]) -> bool:
        """Run checks for a component."""
        logger.info(f"\nChecking {name}...")

        all_passed = True
        component_results = []

        for check_name, check_func in checks:
            try:
                result = check_func()
                passed = result is True
                component_results.append((check_name, passed, result))

                if passed:
                    logger.info(f"  ✓ {check_name}")
                else:
                    logger.warning(f"  ✗ {check_name}: {result}")
                    all_passed = False
                    self.issues.append(f"{name}: {check_name} - {result}")

            except Exception as e:
                logger.error(f"  ✗ {check_name}: {str(e)}")
                component_results.append((check_name, False, str(e)))
                all_passed = False
                self.issues.append(f"{name}: {check_name} - {str(e)}")

        self.results[name] = (all_passed, component_results)
        return all_passed

    def validate_core_infrastructure(self):
        """Validate core infrastructure components."""

        def check_fix_messages():
            """Check FIX message implementation."""
            from fxml4.fix.messages.base import FIXMessage, OrdType, Side
            from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle

            # Check classes exist
            assert issubclass(NewOrderSingle, FIXMessage)
            assert issubclass(ExecutionReport, FIXMessage)

            # Check enums
            assert Side.BUY.value == "1"
            assert OrdType.MARKET.value == "1"

            return True

        def check_fix_utils():
            """Check FIX utilities."""
            from fxml4.fix.utils.builder import FIXMessageBuilder
            from fxml4.fix.utils.parser import FIXParser

            # Check builder
            builder = FIXMessageBuilder()
            assert hasattr(builder, "build_header")

            # Check parser
            parser = FIXParser()
            assert hasattr(parser, "parse")

            return True

        def check_messaging_system():
            """Check RabbitMQ messaging components."""
            from fxml4.brokers.messaging.consumer import BrokerMessageConsumer
            from fxml4.brokers.messaging.publisher import BrokerMessagePublisher
            from fxml4.brokers.messaging.topology import QueueTopology

            # Check topology
            topology = QueueTopology()
            assert hasattr(topology, "setup_broker_queues")

            return True

        def check_base_framework():
            """Check base adapter framework."""
            from fxml4.brokers.adapters.base import AdapterConfig, BrokerAdapter
            from fxml4.brokers.adapters.manager import AdapterManager
            from fxml4.brokers.adapters.registry import BrokerRegistry

            # Check abstract base
            assert inspect.isabstract(BrokerAdapter)

            # Check registry
            assert hasattr(BrokerRegistry, "register")
            assert hasattr(BrokerRegistry, "get_adapter_class")

            return True

        def check_routing_system():
            """Check message routing system."""
            from fxml4.brokers.messaging.router import MessageRouter, RoutingRule

            router = MessageRouter()
            assert hasattr(router, "route_order")
            assert hasattr(router, "add_rule")

            return True

        checks = [
            ("FIX Message Classes", check_fix_messages),
            ("FIX Utilities", check_fix_utils),
            ("Messaging System", check_messaging_system),
            ("Base Framework", check_base_framework),
            ("Routing System", check_routing_system),
        ]

        return self.check_component("Core Infrastructure", checks)

    def validate_broker_adapters(self):
        """Validate broker adapter implementations."""

        def check_ib_adapter():
            """Check IB adapter implementation."""
            try:
                import fxml4.brokers.adapters.ib
                from fxml4.brokers.adapters.registry import BrokerRegistry

                # Check registration
                adapter_class = BrokerRegistry.get_adapter_class("ib")
                assert adapter_class is not None

                # Check adapter structure
                from fxml4.brokers.adapters.ib_adapter import IBBrokerAdapter

                assert hasattr(IBBrokerAdapter, "submit_order")
                assert hasattr(IBBrokerAdapter, "cancel_order")

                return True
            except Exception as e:
                return f"IB adapter error: {e}"

        def check_manual_adapter():
            """Check manual adapter implementation."""
            try:
                import fxml4.brokers.adapters.manual
                from fxml4.brokers.adapters.registry import BrokerRegistry

                # Check registration
                adapter_class = BrokerRegistry.get_adapter_class("manual")
                assert adapter_class is not None

                # Check manual-specific features
                from fxml4.brokers.adapters.manual_adapter import ManualBrokerAdapter

                assert hasattr(ManualBrokerAdapter, "approve_order")
                assert hasattr(ManualBrokerAdapter, "reject_order")

                return True
            except Exception as e:
                return f"Manual adapter error: {e}"

        def check_fxcm_adapter():
            """Check FXCM adapter implementation."""
            try:
                import fxml4.brokers.adapters.fxcm
                from fxml4.brokers.adapters.registry import BrokerRegistry

                # Check registration
                adapter_class = BrokerRegistry.get_adapter_class("fxcm")
                assert adapter_class is not None

                return True
            except Exception as e:
                return f"FXCM adapter error: {e}"

        def check_adapter_features():
            """Check adapter feature completeness."""
            from fxml4.brokers.adapters.registry import BrokerRegistry

            required_methods = [
                "connect",
                "disconnect",
                "submit_order",
                "cancel_order",
                "get_order_status",
            ]

            issues = []
            for broker_type in ["ib", "manual"]:
                adapter_class = BrokerRegistry.get_adapter_class(broker_type)
                if adapter_class:
                    for method in required_methods:
                        if not hasattr(adapter_class, method):
                            issues.append(f"{broker_type} missing {method}")

            return True if not issues else f"Missing methods: {issues}"

        checks = [
            ("IB Adapter", check_ib_adapter),
            ("Manual Adapter", check_manual_adapter),
            ("FXCM Adapter", check_fxcm_adapter),
            ("Adapter Features", check_adapter_features),
        ]

        return self.check_component("Broker Adapters", checks)

    def validate_api_integration(self):
        """Validate API integration components."""

        def check_manual_api():
            """Check manual execution API."""
            try:
                from fxml4.api.routers.manual_execution import router

                # Check endpoints
                routes = [r.path for r in router.routes]
                required_endpoints = [
                    "/status",
                    "/orders/pending",
                    "/orders/history",
                    "/orders/{cl_ord_id}/approve",
                    "/orders/{cl_ord_id}/reject",
                ]

                missing = [
                    ep
                    for ep in required_endpoints
                    if not any(ep in route for route in routes)
                ]

                return True if not missing else f"Missing endpoints: {missing}"
            except Exception as e:
                return f"API error: {e}"

        def check_websocket_support():
            """Check WebSocket implementation."""
            try:
                from fxml4.api.routers.manual_execution import router

                # Check for WebSocket endpoint
                routes = [r.path for r in router.routes]
                has_ws = any("/ws" in route for route in routes)

                return True if has_ws else "No WebSocket endpoint found"
            except Exception as e:
                return f"WebSocket error: {e}"

        checks = [
            ("Manual Execution API", check_manual_api),
            ("WebSocket Support", check_websocket_support),
        ]

        return self.check_component("API Integration", checks)

    def validate_configuration(self):
        """Validate configuration files."""

        def check_broker_config():
            """Check broker configuration."""
            config_path = Path(__file__).parent.parent / "config" / "brokers.yaml"

            if not config_path.exists():
                return f"Config file not found: {config_path}"

            try:
                import yaml

                with open(config_path) as f:
                    config = yaml.safe_load(f)

                # Check required brokers
                brokers = config.get("brokers", {})
                required = ["ib", "manual", "fxcm"]
                missing = [b for b in required if b not in brokers]

                return True if not missing else f"Missing brokers: {missing}"
            except Exception as e:
                return f"Config error: {e}"

        def check_routing_rules():
            """Check routing rules configuration."""
            try:
                config_path = Path(__file__).parent.parent / "config" / "brokers.yaml"

                import yaml

                with open(config_path) as f:
                    config = yaml.safe_load(f)

                rules = config.get("routing_rules", [])
                return True if rules else "No routing rules defined"
            except Exception as e:
                return f"Routing rules error: {e}"

        checks = [
            ("Broker Configuration", check_broker_config),
            ("Routing Rules", check_routing_rules),
        ]

        return self.check_component("Configuration", checks)

    def validate_testing(self):
        """Validate testing components."""

        def check_test_scripts():
            """Check test scripts exist."""
            scripts_dir = Path(__file__).parent
            required_scripts = [
                "test_ib_adapter.py",
                "test_manual_adapter.py",
                "test_fxcm_adapter.py",
                "test_integration.py",
                "test_multi_adapter_routing.py",
            ]

            missing = []
            for script in required_scripts:
                if not (scripts_dir / script).exists():
                    missing.append(script)

            return True if not missing else f"Missing scripts: {missing}"

        def check_integration_tests():
            """Check integration test files."""
            tests_dir = Path(__file__).parent.parent / "tests" / "integration"

            if not tests_dir.exists():
                return "Integration tests directory not found"

            test_files = list(tests_dir.glob("test_*.py"))

            return True if test_files else "No integration tests found"

        checks = [
            ("Test Scripts", check_test_scripts),
            ("Integration Tests", check_integration_tests),
        ]

        return self.check_component("Testing", checks)

    def print_summary(self):
        """Print validation summary."""
        logger.info("\n" + "=" * 60)
        logger.info("ARCHITECTURE VALIDATION SUMMARY")
        logger.info("=" * 60)

        total_components = len(self.results)
        passed_components = sum(1 for passed, _ in self.results.values() if passed)

        logger.info(f"\nComponents validated: {total_components}")
        logger.info(f"Passed: {passed_components}")
        logger.info(f"Failed: {total_components - passed_components}")

        if self.issues:
            logger.warning(f"\nIssues found ({len(self.issues)}):")
            for issue in self.issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info("\n✓ All architecture components validated successfully!")

        # Detailed results
        logger.info("\nDetailed Results:")
        for component, (passed, checks) in self.results.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            logger.info(f"\n{component}: {status}")

            for check_name, check_passed, result in checks:
                if not check_passed:
                    logger.info(f"  - {check_name}: {result}")


async def main():
    """Main validation execution."""
    logger.info("FIX Broker Abstraction - Architecture Validation")
    logger.info("=" * 50)

    validator = ArchitectureValidator()

    # Run all validations
    validator.validate_core_infrastructure()
    validator.validate_broker_adapters()
    validator.validate_api_integration()
    validator.validate_configuration()
    validator.validate_testing()

    # Print summary
    validator.print_summary()

    # Return exit code based on results
    all_passed = all(passed for passed, _ in validator.results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
