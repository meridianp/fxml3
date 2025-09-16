#!/usr/bin/env python3
"""Test FXCM Docker Integration.

Tests the containerized FXCM demo bridge integration with FXML4
using the provided credentials in a Docker environment.
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import datetime

import aiohttp
import websockets


class FXCMDockerIntegrationTest:
    """Test FXCM Docker integration."""

    def __init__(self):
        """Initialize test suite."""
        self.setup_logging()

        # Service URLs
        self.fxcm_bridge_url = "http://localhost:8080"
        self.fxcm_ws_url = "ws://localhost:8081"
        self.fxml4_api_url = "http://localhost:8000"

        # Test state
        self.test_results = []
        self.websocket_messages = []

        self.logger.info("FXCM Docker Integration Test initialized")

    def setup_logging(self):
        """Setup logging."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("fxcm_docker_test.log"),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def log_test_result(
        self, test_name: str, success: bool, message: str = "", duration: float = 0
    ):
        """Log test result."""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.test_results.append(result)

        status = "✅ PASS" if success else "❌ FAIL"
        self.logger.info(f"{status} - {test_name}: {message} ({duration:.2f}s)")

    async def wait_for_service(self, url: str, max_attempts: int = 30) -> bool:
        """Wait for service to be ready."""
        self.logger.info(f"Waiting for service: {url}")

        for attempt in range(max_attempts):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{url}/health", timeout=5) as response:
                        if response.status == 200:
                            self.logger.info(f"Service ready: {url}")
                            return True
            except Exception:
                pass

            await asyncio.sleep(2)
            self.logger.info(
                f"Waiting for service... attempt {attempt + 1}/{max_attempts}"
            )

        self.logger.error(f"Service not ready after {max_attempts} attempts: {url}")
        return False

    async def test_docker_containers_running(self) -> bool:
        """Test that Docker containers are running."""
        start_time = time.time()

        try:
            # Check containers
            result = subprocess.run(
                ["docker-compose", "-f", "docker-compose.fxcm-demo.yml", "ps"],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self.log_test_result(
                    "docker_containers_running",
                    False,
                    f"Docker compose ps failed: {result.stderr}",
                    time.time() - start_time,
                )
                return False

            # Check for required containers
            required_containers = ["fxcm-demo-bridge", "rabbitmq", "redis"]
            output = result.stdout

            for container in required_containers:
                if container not in output:
                    self.log_test_result(
                        "docker_containers_running",
                        False,
                        f"Container {container} not found in docker-compose ps output",
                        time.time() - start_time,
                    )
                    return False

            self.log_test_result(
                "docker_containers_running",
                True,
                "All required containers are running",
                time.time() - start_time,
            )
            return True

        except Exception as e:
            self.log_test_result(
                "docker_containers_running",
                False,
                f"Error checking containers: {e}",
                time.time() - start_time,
            )
            return False

    async def test_fxcm_bridge_health(self) -> bool:
        """Test FXCM bridge health endpoint."""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.fxcm_bridge_url}/health") as response:
                    data = await response.json()

                    success = (
                        response.status == 200
                        and data.get("status") == "healthy"
                        and data.get("fxcm_connected") is True
                    )

                    message = f"Health status: {data.get('status')}, FXCM connected: {data.get('fxcm_connected')}"

                    self.log_test_result(
                        "fxcm_bridge_health", success, message, time.time() - start_time
                    )
                    return success

        except Exception as e:
            self.log_test_result(
                "fxcm_bridge_health",
                False,
                f"Health check failed: {e}",
                time.time() - start_time,
            )
            return False

    async def test_fxcm_bridge_status(self) -> bool:
        """Test FXCM bridge status endpoint."""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.fxcm_bridge_url}/status") as response:
                    data = await response.json()

                    success = (
                        response.status == 200
                        and data.get("connections", {}).get("fxcm", {}).get("connected")
                        is True
                        and data.get("connections", {})
                        .get("rabbitmq", {})
                        .get("connected")
                        is True
                        and data.get("service") == "FXCM Demo Bridge"
                    )

                    fxcm_account = (
                        data.get("connections", {}).get("fxcm", {}).get("account", "")
                    )
                    message = f"Service: {data.get('service')}, Account: {fxcm_account}"

                    self.log_test_result(
                        "fxcm_bridge_status", success, message, time.time() - start_time
                    )
                    return success

        except Exception as e:
            self.log_test_result(
                "fxcm_bridge_status",
                False,
                f"Status check failed: {e}",
                time.time() - start_time,
            )
            return False

    async def test_account_information(self) -> bool:
        """Test account information retrieval."""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.fxcm_bridge_url}/account") as response:
                    data = await response.json()

                    required_fields = [
                        "account_id",
                        "balance",
                        "equity",
                        "currency",
                        "connected",
                    ]
                    success = (
                        response.status == 200
                        and all(field in data for field in required_fields)
                        and data.get("connected") is True
                        and isinstance(data.get("balance"), (int, float))
                        and data.get("balance") > 0
                    )

                    message = f"Balance: ${data.get('balance', 0):,.2f}, Currency: {data.get('currency', 'N/A')}"

                    self.log_test_result(
                        "account_information",
                        success,
                        message,
                        time.time() - start_time,
                    )
                    return success

        except Exception as e:
            self.log_test_result(
                "account_information",
                False,
                f"Account info failed: {e}",
                time.time() - start_time,
            )
            return False

    async def test_market_data_retrieval(self) -> bool:
        """Test market data retrieval."""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.fxcm_bridge_url}/prices") as response:
                    data = await response.json()

                    success = (
                        response.status == 200
                        and isinstance(data, dict)
                        and len(data) > 0
                    )

                    # Check price data structure
                    if success:
                        for symbol, prices in data.items():
                            if not all(
                                key in prices for key in ["bid", "ask", "timestamp"]
                            ):
                                success = False
                                break
                            if prices["ask"] <= prices["bid"]:
                                success = False
                                break

                    symbols = list(data.keys()) if isinstance(data, dict) else []
                    message = f"Retrieved prices for {len(symbols)} symbols: {', '.join(symbols[:3])}"

                    self.log_test_result(
                        "market_data_retrieval",
                        success,
                        message,
                        time.time() - start_time,
                    )
                    return success

        except Exception as e:
            self.log_test_result(
                "market_data_retrieval",
                False,
                f"Market data retrieval failed: {e}",
                time.time() - start_time,
            )
            return False

    async def test_websocket_connection(self) -> bool:
        """Test WebSocket connection and real-time data."""
        start_time = time.time()

        try:
            async with websockets.connect(self.fxcm_ws_url) as websocket:
                # Send subscription message
                subscribe_msg = {"type": "subscribe", "symbols": ["EURUSD", "GBPUSD"]}
                await websocket.send(json.dumps(subscribe_msg))

                # Wait for messages
                messages_received = 0
                welcome_received = False
                market_data_received = False

                try:
                    for _ in range(10):  # Wait for up to 10 messages or 10 seconds
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        messages_received += 1

                        if data.get("type") == "welcome":
                            welcome_received = True
                        elif data.get("type") == "market_data":
                            market_data_received = True

                        self.websocket_messages.append(data)

                except asyncio.TimeoutError:
                    pass  # Expected after waiting

                success = welcome_received and messages_received > 0
                message = f"Received {messages_received} messages, Welcome: {welcome_received}, Market data: {market_data_received}"

                self.log_test_result(
                    "websocket_connection", success, message, time.time() - start_time
                )
                return success

        except Exception as e:
            self.log_test_result(
                "websocket_connection",
                False,
                f"WebSocket connection failed: {e}",
                time.time() - start_time,
            )
            return False

    async def test_order_placement(self) -> bool:
        """Test order placement."""
        start_time = time.time()

        try:
            order_data = {
                "symbol": "EURUSD",
                "side": "buy",
                "quantity": 10000,  # Mini lot
                "order_type": "market",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.fxcm_bridge_url}/orders", json=order_data
                ) as response:
                    data = await response.json()

                    success = (
                        response.status == 200
                        and data.get("status") == "FILLED"
                        and data.get("symbol") == "EURUSD"
                        and data.get("quantity") == 10000
                    )

                    message = f"Order: {data.get('order_id')}, Status: {data.get('status')}, Price: {data.get('fill_price')}"

                    self.log_test_result(
                        "order_placement", success, message, time.time() - start_time
                    )

                    # Store order ID for position tests
                    if success:
                        self.test_order_id = data.get("order_id")

                    return success

        except Exception as e:
            self.log_test_result(
                "order_placement",
                False,
                f"Order placement failed: {e}",
                time.time() - start_time,
            )
            return False

    async def test_position_retrieval(self) -> bool:
        """Test position retrieval."""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.fxcm_bridge_url}/positions") as response:
                    data = await response.json()

                    success = (
                        response.status == 200
                        and isinstance(data, list)
                        and len(data) > 0
                    )

                    # Check position data structure
                    if success and data:
                        position = data[0]
                        required_fields = [
                            "position_id",
                            "symbol",
                            "side",
                            "quantity",
                            "open_price",
                            "unrealized_pl",
                        ]
                        if not all(field in position for field in required_fields):
                            success = False

                    message = f"Retrieved {len(data) if isinstance(data, list) else 0} positions"

                    self.log_test_result(
                        "position_retrieval", success, message, time.time() - start_time
                    )
                    return success

        except Exception as e:
            self.log_test_result(
                "position_retrieval",
                False,
                f"Position retrieval failed: {e}",
                time.time() - start_time,
            )
            return False

    async def test_position_closure(self) -> bool:
        """Test position closure."""
        start_time = time.time()

        if not hasattr(self, "test_order_id"):
            self.log_test_result(
                "position_closure",
                False,
                "No test order ID available from previous test",
                time.time() - start_time,
            )
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.fxcm_bridge_url}/positions/{self.test_order_id}"
                ) as response:
                    data = await response.json()

                    success = (
                        response.status == 200
                        and data.get("position_id") == self.test_order_id
                        and "realized_pl" in data
                        and "close_price" in data
                    )

                    message = f"Closed position: {data.get('position_id')}, P&L: ${data.get('realized_pl', 0):.2f}"

                    self.log_test_result(
                        "position_closure", success, message, time.time() - start_time
                    )
                    return success

        except Exception as e:
            self.log_test_result(
                "position_closure",
                False,
                f"Position closure failed: {e}",
                time.time() - start_time,
            )
            return False

    async def test_rabbitmq_integration(self) -> bool:
        """Test RabbitMQ integration by checking bridge status."""
        start_time = time.time()

        try:
            # Check if RabbitMQ management is accessible
            async with aiohttp.ClientSession() as session:
                # Check bridge status for RabbitMQ connectivity
                async with session.get(f"{self.fxcm_bridge_url}/status") as response:
                    data = await response.json()

                    rabbitmq_connected = (
                        data.get("connections", {}).get("rabbitmq", {}).get("connected")
                    )

                    success = rabbitmq_connected is True
                    message = f"RabbitMQ connected: {rabbitmq_connected}"

                    self.log_test_result(
                        "rabbitmq_integration",
                        success,
                        message,
                        time.time() - start_time,
                    )
                    return success

        except Exception as e:
            self.log_test_result(
                "rabbitmq_integration",
                False,
                f"RabbitMQ integration test failed: {e}",
                time.time() - start_time,
            )
            return False

    def generate_test_report(self):
        """Generate comprehensive test report."""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["success"]])
        failed_tests = total_tests - passed_tests

        print("\n" + "=" * 80)
        print("🐳 FXCM Docker Integration Test Report")
        print("=" * 80)

        print(f"\n📊 Test Summary:")
        print(f"  Total Tests: {total_tests}")
        print(f"  ✅ Passed: {passed_tests}")
        print(f"  ❌ Failed: {failed_tests}")
        print(
            f"  📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%"
            if total_tests > 0
            else "  📈 Success Rate: 0%"
        )

        print(f"\n📋 Test Results:")
        for result in self.test_results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(
                f"  {status} {result['test']}: {result['message']} ({result['duration']:.2f}s)"
            )

        if failed_tests > 0:
            print(f"\n❌ Failed Tests Details:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['message']}")

        if self.websocket_messages:
            print(f"\n📡 WebSocket Messages Received: {len(self.websocket_messages)}")
            for i, msg in enumerate(self.websocket_messages[:3]):
                print(f"  {i+1}. {msg.get('type', 'unknown')}: {str(msg)[:100]}...")

        print(f"\n🎯 Integration Status:")
        if passed_tests == total_tests:
            print("  🚀 FXCM Docker Integration: FULLY OPERATIONAL")
            print("  ✅ Ready for paper trading with provided credentials")
        else:
            print("  ⚠️  FXCM Docker Integration: PARTIAL SUCCESS")
            print(f"  🔧 {failed_tests} test(s) need attention")

        print("=" * 80)

        return passed_tests == total_tests

    async def run_all_tests(self) -> bool:
        """Run all integration tests."""
        self.logger.info("Starting FXCM Docker Integration Tests...")

        print("🐳 FXCM Docker Integration Test Suite")
        print("=" * 50)
        print("📧 Account: 0x0c9@quatumchain.com")
        print("🖥️  Server: FXCM-USDDemo1")
        print("🐳 Environment: Docker Containers")
        print()

        # Wait for services to be ready
        print("⏳ Waiting for services to start...")
        if not await self.wait_for_service(self.fxcm_bridge_url):
            print("❌ FXCM Bridge service not ready")
            return False

        print("🚀 Services ready, starting tests...\n")

        # Run tests in sequence
        test_functions = [
            self.test_docker_containers_running,
            self.test_fxcm_bridge_health,
            self.test_fxcm_bridge_status,
            self.test_account_information,
            self.test_market_data_retrieval,
            self.test_websocket_connection,
            self.test_order_placement,
            self.test_position_retrieval,
            self.test_position_closure,
            self.test_rabbitmq_integration,
        ]

        for test_func in test_functions:
            try:
                await test_func()
            except Exception as e:
                self.logger.error(
                    f"Test {test_func.__name__} failed with exception: {e}"
                )
                self.log_test_result(test_func.__name__, False, f"Exception: {e}")

        # Generate final report
        return self.generate_test_report()


async def main():
    """Main entry point."""
    print("Starting FXCM Docker Integration Test Suite...")

    tester = FXCMDockerIntegrationTest()
    success = await tester.run_all_tests()

    if success:
        print("\n🎉 All tests passed! FXCM Docker integration is working correctly.")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed. Check the logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test suite failed: {e}")
        sys.exit(1)
