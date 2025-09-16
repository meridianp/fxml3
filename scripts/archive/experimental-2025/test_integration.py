#!/usr/bin/env python3
"""Integration Test Runner for FIX Broker Abstraction.

This script runs integration tests for the broker abstraction system,
testing multiple adapters working together.
"""

import asyncio
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_rabbitmq():
    """Check if RabbitMQ is running."""
    try:
        # Try to connect to RabbitMQ management API
        import requests

        response = requests.get(
            "http://localhost:15672/api/overview", auth=("guest", "guest"), timeout=2
        )
        if response.status_code == 200:
            logger.info("✓ RabbitMQ is running")
            return True
    except:
        pass

    # Try docker-compose
    try:
        result = subprocess.run(
            ["docker-compose", "ps", "rabbitmq"],
            capture_output=True,
            text=True,
            check=False,
        )
        if "Up" in result.stdout:
            logger.info("✓ RabbitMQ is running (via docker-compose)")
            return True
    except:
        pass

    logger.warning("✗ RabbitMQ is not running")
    logger.info("  Start with: docker-compose up -d rabbitmq")
    return False


def check_adapters():
    """Check if adapters are properly registered."""
    from fxml4.brokers.adapters.registry import BrokerRegistry

    # Import adapter packages to trigger registration
    try:
        import fxml4.brokers.adapters.fxcm
        import fxml4.brokers.adapters.ib
        import fxml4.brokers.adapters.manual
    except ImportError as e:
        logger.warning(f"Failed to import adapter: {e}")

    registered = BrokerRegistry.list_adapters()
    logger.info(f"Registered adapters: {list(registered.keys())}")

    required_adapters = ["ib", "manual"]
    missing = [a for a in required_adapters if a not in registered]

    if missing:
        logger.error(f"Missing required adapters: {missing}")
        return False

    return True


async def run_integration_tests():
    """Run integration tests."""
    logger.info("=" * 60)
    logger.info("FIX Broker Abstraction - Integration Test Suite")
    logger.info("=" * 60)

    # Check prerequisites
    logger.info("\n1. Checking prerequisites...")

    rabbitmq_available = check_rabbitmq()
    adapters_ready = check_adapters()

    if not adapters_ready:
        logger.error("Adapters not properly registered. Exiting.")
        return False

    # Run tests
    logger.info("\n2. Running integration tests...")

    test_modules = [
        "tests.integration.test_multi_adapter_integration",
        "tests.integration.test_end_to_end",
    ]

    all_passed = True

    for module in test_modules:
        logger.info(f"\n--- Testing {module} ---")

        try:
            # Run pytest for the module
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-xvs",
                    f'{module.replace(".", "/")+".py"}',
                    "--tb=short",
                    "-p",
                    "no:warnings",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                logger.info(f"✓ {module} passed")
                # Show summary from output
                output_lines = result.stdout.split("\n")
                for line in output_lines:
                    if "passed" in line and "failed" in line:
                        logger.info(f"  {line.strip()}")
            else:
                logger.error(f"✗ {module} failed")
                all_passed = False

                # Show failures
                if result.stdout:
                    logger.error("Test output:")
                    for line in result.stdout.split("\n")[-20:]:  # Last 20 lines
                        if line.strip():
                            logger.error(f"  {line}")

        except Exception as e:
            logger.error(f"Error running {module}: {e}")
            all_passed = False

    # Summary
    logger.info("\n" + "=" * 60)
    if all_passed:
        logger.info("✓ All integration tests passed!")
    else:
        logger.error("✗ Some tests failed.")

    return all_passed


async def run_performance_tests():
    """Run performance benchmarks."""
    logger.info("\n3. Running performance benchmarks...")

    try:
        from tests.integration.test_end_to_end import TestPerformanceMetrics
        from tests.integration.test_multi_adapter_integration import (
            TestPerformanceAndLoad,
        )

        # Run performance tests
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-xvs",
                "tests/integration/",
                "-k",
                "performance",
                "-m",
                "slow",
                "--tb=short",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            logger.info("✓ Performance tests passed")
        else:
            logger.warning("✗ Performance tests had issues")

    except Exception as e:
        logger.error(f"Error running performance tests: {e}")


async def test_specific_scenario(scenario: str):
    """Test a specific integration scenario."""
    scenarios = {
        "routing": "test_order_routing_by_size",
        "failover": "test_failover_routing",
        "concurrent": "test_concurrent_order_submission",
        "lifecycle": "test_order_lifecycle_tracking",
        "recovery": "test_error_handling_and_recovery",
    }

    if scenario not in scenarios:
        logger.error(f"Unknown scenario: {scenario}")
        logger.info(f"Available scenarios: {list(scenarios.keys())}")
        return False

    test_name = scenarios[scenario]
    logger.info(f"\nTesting specific scenario: {scenario} ({test_name})")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-xvs",
            "tests/integration/",
            "-k",
            test_name,
            "--tb=short",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run integration tests")
    parser.add_argument("--scenario", help="Test specific scenario")
    parser.add_argument(
        "--performance", action="store_true", help="Include performance tests"
    )
    parser.add_argument(
        "--no-rabbitmq",
        action="store_true",
        help="Run without RabbitMQ (limited tests)",
    )

    args = parser.parse_args()

    try:
        if args.scenario:
            # Test specific scenario
            success = asyncio.run(test_specific_scenario(args.scenario))
        else:
            # Run full test suite
            success = asyncio.run(run_integration_tests())

            if success and args.performance:
                asyncio.run(run_performance_tests())

    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
