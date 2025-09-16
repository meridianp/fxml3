#!/usr/bin/env python3
"""
Simple FXCM Connection Test

This script tests FXCM broker connectivity without requiring full FXML4 dependencies.
It validates:
- Credentials configuration
- Network connectivity
- Basic connection parameters
- FXCM server accessibility
"""

import asyncio
import json
import logging
import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml


class SimpleFXCMConnectivityTest:
    """Simple FXCM connectivity testing without full dependencies."""

    def __init__(self):
        """Initialize the simple connectivity tester."""
        self.logger = self.setup_logging()
        self.test_results = []
        self.credentials = None

    def setup_logging(self):
        """Setup logging for the test."""
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        return logging.getLogger(__name__)

    async def run_connectivity_test(self) -> bool:
        """Run comprehensive FXCM connectivity test."""
        print("🧪 Simple FXCM Broker Connectivity Test")
        print("=" * 60)
        print(f"📅 Started: {datetime.now().isoformat()}")
        print()

        all_tests_passed = True

        # Test 1: Load and validate credentials
        creds_result = await self.test_credentials_loading()
        all_tests_passed &= creds_result

        # Test 2: Network connectivity
        network_result = await self.test_network_connectivity()
        all_tests_passed &= network_result

        # Test 3: FXCM server accessibility
        server_result = await self.test_fxcm_server_access()
        all_tests_passed &= server_result

        # Test 4: Configuration validation
        config_result = await self.test_configuration_validation()
        all_tests_passed &= config_result

        # Test 5: Demo account simulation
        demo_result = await self.test_demo_simulation()
        all_tests_passed &= demo_result

        # Generate report
        await self.generate_test_report()

        return all_tests_passed

    async def test_credentials_loading(self) -> bool:
        """Test 1: Load and validate FXCM credentials."""
        print("🔐 Test 1: Credentials Loading and Validation")

        try:
            # Load credentials file
            creds_path = (
                Path(__file__).parent.parent / "config" / "fxcm_demo_credentials.yaml"
            )

            if not creds_path.exists():
                self.logger.error(f"❌ Credentials file not found: {creds_path}")
                self.test_results.append(
                    {
                        "test": "Credentials Loading",
                        "status": "FAILED",
                        "error": "Credentials file not found",
                    }
                )
                return False

            with open(creds_path, "r") as f:
                config = yaml.safe_load(f)

            if "fxcm_demo" not in config:
                self.logger.error("❌ Invalid credentials file structure")
                self.test_results.append(
                    {
                        "test": "Credentials Loading",
                        "status": "FAILED",
                        "error": "Missing 'fxcm_demo' section",
                    }
                )
                return False

            self.credentials = config["fxcm_demo"]

            # Validate required fields
            required_fields = ["username", "password", "server"]
            missing = [f for f in required_fields if f not in self.credentials]

            if missing:
                self.logger.error(f"❌ Missing required fields: {missing}")
                self.test_results.append(
                    {
                        "test": "Credentials Loading",
                        "status": "FAILED",
                        "error": f"Missing fields: {missing}",
                    }
                )
                return False

            # Log credential info (masked)
            username = self.credentials["username"]
            password = self.credentials["password"]
            server = self.credentials["server"]

            masked_password = "*" * len(password)

            self.logger.info(f"✅ Credentials loaded successfully")
            self.logger.info(f"📧 Username: {username}")
            self.logger.info(f"🔒 Password: {masked_password}")
            self.logger.info(f"🖥️ Server: {server}")

            # Validate credential format
            if "@" not in username or "." not in username:
                self.logger.warning(f"⚠️ Username format unusual: {username}")

            if len(password) < 6:
                self.logger.warning("⚠️ Password seems short")

            self.test_results.append(
                {
                    "test": "Credentials Loading",
                    "status": "PASSED",
                    "details": {
                        "username": username,
                        "server": server,
                        "password_length": len(password),
                        "account_type": self.credentials.get("account_type", "Unknown"),
                    },
                }
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Credentials test failed: {e}")
            self.test_results.append(
                {"test": "Credentials Loading", "status": "FAILED", "error": str(e)}
            )
            return False

    async def test_network_connectivity(self) -> bool:
        """Test 2: Basic network connectivity."""
        print("\n🌐 Test 2: Network Connectivity")

        try:
            # Test internet connectivity
            test_hosts = [
                ("8.8.8.8", 53),  # Google DNS
                ("1.1.1.1", 53),  # Cloudflare DNS
                ("google.com", 80),  # HTTP
                ("github.com", 443),  # HTTPS
            ]

            connectivity_results = []

            for host, port in test_hosts:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((host, port))
                    sock.close()

                    if result == 0:
                        self.logger.info(f"✅ Connection successful: {host}:{port}")
                        connectivity_results.append(True)
                    else:
                        self.logger.warning(
                            f"⚠️ Connection failed: {host}:{port} (code: {result})"
                        )
                        connectivity_results.append(False)

                except Exception as e:
                    self.logger.error(f"❌ Connection error to {host}:{port}: {e}")
                    connectivity_results.append(False)

            # Test DNS resolution for FXCM-related domains
            fxcm_domains = [
                "www.fxcorporate.com",
                "tradingstation.fxcorporate.com",
                "www.fxcm.com",
            ]

            dns_results = []
            for domain in fxcm_domains:
                try:
                    ip = socket.gethostbyname(domain)
                    self.logger.info(f"✅ DNS resolution successful: {domain} -> {ip}")
                    dns_results.append(True)
                except socket.gaierror as e:
                    self.logger.error(f"❌ DNS resolution failed for {domain}: {e}")
                    dns_results.append(False)

            # Overall network connectivity assessment
            connectivity_score = sum(connectivity_results) / len(connectivity_results)
            dns_score = sum(dns_results) / len(dns_results)

            overall_success = connectivity_score >= 0.75 and dns_score >= 0.5

            self.test_results.append(
                {
                    "test": "Network Connectivity",
                    "status": "PASSED" if overall_success else "FAILED",
                    "details": {
                        "basic_connectivity_score": f"{connectivity_score:.2%}",
                        "dns_resolution_score": f"{dns_score:.2%}",
                        "tested_hosts": len(test_hosts),
                        "tested_domains": len(fxcm_domains),
                    },
                }
            )

            if overall_success:
                self.logger.info("✅ Network connectivity test passed")
            else:
                self.logger.error("❌ Network connectivity issues detected")

            return overall_success

        except Exception as e:
            self.logger.error(f"❌ Network connectivity test failed: {e}")
            self.test_results.append(
                {"test": "Network Connectivity", "status": "FAILED", "error": str(e)}
            )
            return False

    async def test_fxcm_server_access(self) -> bool:
        """Test 3: FXCM server accessibility."""
        print("\n🖥️ Test 3: FXCM Server Access")

        if not self.credentials:
            self.logger.error("❌ No credentials loaded for server test")
            return False

        try:
            server = self.credentials.get("server", "FXCM-USDDemo1")

            # Test connection to FXCM corporate website
            fxcm_endpoints = [
                ("www.fxcorporate.com", 80),
                ("www.fxcorporate.com", 443),
                ("tradingstation.fxcorporate.com", 443),
            ]

            server_results = []
            latencies = []

            for host, port in fxcm_endpoints:
                try:
                    start_time = datetime.now()
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(10)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    end_time = datetime.now()

                    latency_ms = (end_time - start_time).total_seconds() * 1000

                    if result == 0:
                        self.logger.info(
                            f"✅ FXCM server accessible: {host}:{port} ({latency_ms:.0f}ms)"
                        )
                        server_results.append(True)
                        latencies.append(latency_ms)
                    else:
                        self.logger.warning(
                            f"⚠️ FXCM server connection failed: {host}:{port}"
                        )
                        server_results.append(False)

                except Exception as e:
                    self.logger.error(f"❌ FXCM server test error {host}:{port}: {e}")
                    server_results.append(False)

            # Test for known FXCM IP ranges (simulated)
            # In real implementation, this would test actual FXCM trading servers
            # For demo, we'll simulate based on server configuration

            server_score = (
                sum(server_results) / len(server_results) if server_results else 0
            )
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            success = server_score >= 0.5  # At least 50% of endpoints accessible

            # Additional server validation based on server name
            valid_servers = [
                "FXCM-USDDemo1",
                "FXCM-USDDemo2",
                "FXCM-USDReal1",
                "FXCM-USDReal2",
            ]
            server_name_valid = server in valid_servers

            if not server_name_valid:
                self.logger.warning(f"⚠️ Unusual server name: {server}")
            else:
                self.logger.info(f"✅ Server name valid: {server}")

            self.test_results.append(
                {
                    "test": "FXCM Server Access",
                    "status": "PASSED" if success and server_name_valid else "FAILED",
                    "details": {
                        "server_name": server,
                        "server_name_valid": server_name_valid,
                        "accessibility_score": f"{server_score:.2%}",
                        "average_latency_ms": avg_latency,
                        "endpoints_tested": len(fxcm_endpoints),
                    },
                }
            )

            return success and server_name_valid

        except Exception as e:
            self.logger.error(f"❌ FXCM server access test failed: {e}")
            self.test_results.append(
                {"test": "FXCM Server Access", "status": "FAILED", "error": str(e)}
            )
            return False

    async def test_configuration_validation(self) -> bool:
        """Test 4: Configuration validation."""
        print("\n⚙️ Test 4: Configuration Validation")

        try:
            if not self.credentials:
                self.logger.error("❌ No credentials for configuration validation")
                return False

            # Validate trading configuration
            trading_config = self.credentials.get("trading", {})
            market_data_config = self.credentials.get("market_data", {})
            connection_config = self.credentials.get("connection", {})

            # Check trading settings
            default_currency = trading_config.get("default_currency", "USD")
            max_position_size = trading_config.get("max_position_size", 1000000)
            risk_limit = trading_config.get("risk_limit_percentage", 2.0)

            self.logger.info(f"💰 Default currency: {default_currency}")
            self.logger.info(f"📊 Max position size: {max_position_size:,}")
            self.logger.info(f"⚠️ Risk limit: {risk_limit}%")

            # Check market data settings
            symbols = market_data_config.get("symbols", [])
            update_frequency = market_data_config.get("update_frequency", "tick")

            self.logger.info(f"📈 Market data symbols: {len(symbols)} configured")
            self.logger.info(f"🔄 Update frequency: {update_frequency}")

            for symbol in symbols[:3]:  # Show first 3
                self.logger.info(f"  📊 Symbol: {symbol}")

            # Check connection settings
            timeout = connection_config.get("timeout", 30)
            retry_attempts = connection_config.get("retry_attempts", 3)
            heartbeat = connection_config.get("heartbeat_interval", 30)

            self.logger.info(f"⏱️ Connection timeout: {timeout}s")
            self.logger.info(f"🔄 Retry attempts: {retry_attempts}")
            self.logger.info(f"💓 Heartbeat interval: {heartbeat}s")

            # Validate configuration values
            config_valid = True
            validation_issues = []

            if max_position_size <= 0:
                validation_issues.append("Invalid max position size")
                config_valid = False

            if risk_limit <= 0 or risk_limit > 100:
                validation_issues.append("Invalid risk limit percentage")
                config_valid = False

            if timeout <= 0:
                validation_issues.append("Invalid connection timeout")
                config_valid = False

            if not symbols:
                validation_issues.append("No market data symbols configured")
                config_valid = False

            if validation_issues:
                for issue in validation_issues:
                    self.logger.warning(f"⚠️ Configuration issue: {issue}")
            else:
                self.logger.info("✅ All configuration values valid")

            self.test_results.append(
                {
                    "test": "Configuration Validation",
                    "status": "PASSED" if config_valid else "FAILED",
                    "details": {
                        "default_currency": default_currency,
                        "max_position_size": max_position_size,
                        "risk_limit_pct": risk_limit,
                        "symbols_count": len(symbols),
                        "update_frequency": update_frequency,
                        "connection_timeout": timeout,
                        "validation_issues": validation_issues,
                    },
                }
            )

            return config_valid

        except Exception as e:
            self.logger.error(f"❌ Configuration validation failed: {e}")
            self.test_results.append(
                {
                    "test": "Configuration Validation",
                    "status": "FAILED",
                    "error": str(e),
                }
            )
            return False

    async def test_demo_simulation(self) -> bool:
        """Test 5: Demo account simulation."""
        print("\n🎮 Test 5: Demo Account Simulation")

        try:
            if not self.credentials:
                self.logger.error("❌ No credentials for demo simulation")
                return False

            # Simulate demo account behavior
            self.logger.info("🎯 Simulating FXCM demo account connectivity...")

            # Mock account data based on typical demo account
            demo_account = {
                "account_id": "FXCM_DEMO_001",
                "username": self.credentials["username"],
                "server": self.credentials["server"],
                "balance": 50000.00,
                "currency": "USD",
                "account_type": "demo",
                "timestamp": datetime.now().isoformat(),
            }

            self.logger.info(
                f"💰 Demo account balance: ${demo_account['balance']:,.2f}"
            )
            self.logger.info(f"🪙 Account currency: {demo_account['currency']}")
            self.logger.info(f"🎮 Account type: {demo_account['account_type']}")

            # Simulate market data for configured symbols
            symbols = self.credentials.get("market_data", {}).get("symbols", [])
            market_data_simulation = {}

            # Mock realistic forex prices
            base_prices = {
                "EUR/USD": 1.0850,
                "GBP/USD": 1.2720,
                "USD/JPY": 149.85,
                "USD/CHF": 0.8920,
                "AUD/USD": 0.6580,
                "USD/CAD": 1.3650,
                "NZD/USD": 0.6120,
            }

            for symbol in symbols[:5]:  # Simulate first 5 symbols
                if symbol in base_prices:
                    base_price = base_prices[symbol]
                    # Add small random variation
                    import random

                    variation = random.uniform(-0.001, 0.001)
                    bid = base_price + variation
                    ask = bid + 0.0002  # 2 pip spread

                    market_data_simulation[symbol] = {
                        "bid": round(bid, 5),
                        "ask": round(ask, 5),
                        "spread": round(ask - bid, 5),
                        "timestamp": datetime.now().isoformat(),
                    }

                    self.logger.info(
                        f"📈 {symbol}: {bid:.5f}/{ask:.5f} (spread: {ask-bid:.5f})"
                    )

            # Simulate order placement
            demo_order = {
                "symbol": "EUR/USD",
                "side": "buy",
                "quantity": 10000,  # Mini lot
                "order_type": "market",
                "expected_fill": market_data_simulation.get("EUR/USD", {}).get(
                    "ask", 1.0850
                ),
            }

            self.logger.info("📋 Demo order simulation:")
            self.logger.info(f"  Symbol: {demo_order['symbol']}")
            self.logger.info(f"  Side: {demo_order['side']}")
            self.logger.info(f"  Quantity: {demo_order['quantity']:,}")
            self.logger.info(f"  Expected fill: {demo_order['expected_fill']:.5f}")

            # Simulate connection health
            connection_health = {
                "connected": True,
                "session_id": f"FXCM_DEMO_SESSION_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "last_heartbeat": datetime.now().isoformat(),
                "connection_time": 1.250,  # seconds
                "data_flow_active": True,
            }

            self.logger.info("🔗 Connection simulation:")
            self.logger.info(
                f"  Status: {'✅ Connected' if connection_health['connected'] else '❌ Disconnected'}"
            )
            self.logger.info(f"  Session ID: {connection_health['session_id']}")
            self.logger.info(
                f"  Connection time: {connection_health['connection_time']:.3f}s"
            )

            self.test_results.append(
                {
                    "test": "Demo Account Simulation",
                    "status": "PASSED",
                    "details": {
                        "account_balance": demo_account["balance"],
                        "account_currency": demo_account["currency"],
                        "symbols_simulated": len(market_data_simulation),
                        "connection_simulated": connection_health["connected"],
                        "session_id": connection_health["session_id"],
                        "demo_order_symbol": demo_order["symbol"],
                    },
                }
            )

            self.logger.info("✅ Demo simulation completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Demo simulation failed: {e}")
            self.test_results.append(
                {"test": "Demo Account Simulation", "status": "FAILED", "error": str(e)}
            )
            return False

    async def generate_test_report(self):
        """Generate comprehensive test report."""
        print("\n" + "=" * 60)
        print("📊 FXCM CONNECTIVITY TEST REPORT")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(
            1 for test in self.test_results if test["status"] == "PASSED"
        )
        failed_tests = total_tests - passed_tests

        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        print(f"📅 Test completion: {datetime.now().isoformat()}")
        print(f"🧪 Total tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📊 Success rate: {success_rate:.1f}%")
        print()

        print("📋 DETAILED TEST RESULTS:")
        print("-" * 60)

        for i, test in enumerate(self.test_results, 1):
            status_icon = "✅" if test["status"] == "PASSED" else "❌"
            print(f"{i}. {status_icon} {test['test']}: {test['status']}")

            if "details" in test:
                for key, value in test["details"].items():
                    print(f"   {key}: {value}")

            if "error" in test:
                print(f"   Error: {test['error']}")

        # Generate summary and recommendations
        print("\n📝 SUMMARY AND RECOMMENDATIONS:")
        print("-" * 60)

        if self.credentials:
            print(f"🔐 FXCM Demo Account: {self.credentials['username']}")
            print(f"🖥️ Server: {self.credentials['server']}")
            print(
                f"🪙 Currency: {self.credentials.get('trading', {}).get('default_currency', 'USD')}"
            )

        if success_rate >= 80:
            print("✅ OVERALL STATUS: READY FOR FXCM CONNECTIVITY")
            print("✅ All critical components are functional")
            print("🚀 Proceed with full FXCM integration testing")
        elif success_rate >= 60:
            print("⚠️ OVERALL STATUS: MOSTLY READY (MINOR ISSUES)")
            print("⚠️ Some non-critical issues detected")
            print("🔧 Review failed tests and address issues")
        else:
            print("❌ OVERALL STATUS: NOT READY (CRITICAL ISSUES)")
            print("❌ Critical connectivity issues detected")
            print("🛠️ Address all failed tests before proceeding")

        # Save detailed report
        report_data = {
            "test_execution": {
                "timestamp": datetime.now().isoformat(),
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": success_rate,
            },
            "credentials_info": {
                "username": (
                    self.credentials.get("username") if self.credentials else None
                ),
                "server": self.credentials.get("server") if self.credentials else None,
                "account_type": (
                    self.credentials.get("account_type") if self.credentials else None
                ),
            },
            "test_results": self.test_results,
        }

        report_filename = (
            f"fxcm_connectivity_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_filename, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n💾 Detailed report saved to: {report_filename}")

        return success_rate >= 80


async def main():
    """Main entry point."""
    tester = SimpleFXCMConnectivityTest()
    success = await tester.run_connectivity_test()

    if success:
        print("\n🎉 FXCM CONNECTIVITY TEST: SUCCESS")
        print("✅ Ready for full FXCM broker integration")
        sys.exit(0)
    else:
        print("\n💥 FXCM CONNECTIVITY TEST: ISSUES DETECTED")
        print("🔧 Please resolve issues before proceeding")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
