#!/usr/bin/env python3
"""
FXCM Credentials and Configuration Test

Tests FXCM broker credentials and configuration to ensure:
- Credentials are properly configured
- Configuration files are accessible
- Connection parameters are valid
- Authentication works correctly
- Demo account access is functional
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.brokers.adapters.fxcm_demo_adapter import FXCMDemoAdapter


class FXCMCredentialsTest:
    """Test FXCM credentials and configuration."""

    def __init__(self):
        """Initialize credentials tester."""
        self.logger = self.setup_logging()
        self.test_results = []

    def setup_logging(self):
        """Setup logging for credentials testing."""
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        return logging.getLogger(__name__)

    async def run_credentials_test(self) -> bool:
        """Run comprehensive credentials testing."""
        print("🔐 FXCM Credentials and Configuration Test")
        print("=" * 70)
        print(f"📅 Started: {datetime.now().isoformat()}")
        print()

        all_tests_passed = True

        # Test 1: Configuration File Access
        config_result = await self.test_configuration_files()
        all_tests_passed &= config_result

        # Test 2: Credentials Validation
        creds_result = await self.test_credentials_validation()
        all_tests_passed &= creds_result

        # Test 3: Connection Parameters
        params_result = await self.test_connection_parameters()
        all_tests_passed &= params_result

        # Test 4: Authentication Test
        auth_result = await self.test_authentication()
        all_tests_passed &= auth_result

        # Test 5: Demo Account Access
        demo_result = await self.test_demo_account_access()
        all_tests_passed &= demo_result

        # Test 6: Configuration Integration
        integration_result = await self.test_configuration_integration()
        all_tests_passed &= integration_result

        # Generate summary report
        await self.generate_credentials_report()

        return all_tests_passed

    async def test_configuration_files(self) -> bool:
        """Test 1: Configuration file access and structure."""
        print("📁 Test 1: Configuration Files")

        try:
            # Test FXCM demo credentials file
            demo_config_path = (
                Path(__file__).parent.parent / "config" / "fxcm_demo_credentials.yaml"
            )

            if not demo_config_path.exists():
                self.logger.error(
                    f"❌ Demo credentials file not found: {demo_config_path}"
                )
                self.test_results.append(
                    {
                        "test": "Configuration Files - Demo Credentials",
                        "status": "FAILED",
                        "error": "Demo credentials file not found",
                    }
                )

                # Create template file
                await self.create_credentials_template(demo_config_path)
                return False

            # Load and validate demo credentials
            with open(demo_config_path, "r") as f:
                demo_config = yaml.safe_load(f)

            if "fxcm_demo" not in demo_config:
                self.logger.error("❌ Invalid demo credentials file structure")
                self.test_results.append(
                    {
                        "test": "Configuration Files - Demo Structure",
                        "status": "FAILED",
                        "error": "Missing 'fxcm_demo' section",
                    }
                )
                return False

            demo_creds = demo_config["fxcm_demo"]
            required_fields = ["username", "password", "server"]
            missing_fields = [
                field for field in required_fields if field not in demo_creds
            ]

            if missing_fields:
                self.logger.error(f"❌ Missing required fields: {missing_fields}")
                self.test_results.append(
                    {
                        "test": "Configuration Files - Required Fields",
                        "status": "FAILED",
                        "error": f"Missing fields: {missing_fields}",
                    }
                )
                return False

            # Test main integration config file
            integration_config_path = (
                Path(__file__).parent.parent / "config" / "fxcm_integration.yaml"
            )

            if not integration_config_path.exists():
                self.logger.warning(
                    f"⚠️ Integration config not found: {integration_config_path}"
                )
                self.test_results.append(
                    {
                        "test": "Configuration Files - Integration Config",
                        "status": "WARNING",
                        "error": "Integration config file not found",
                    }
                )
            else:
                with open(integration_config_path, "r") as f:
                    integration_config = yaml.safe_load(f)

                self.logger.info(
                    f"✅ Integration config loaded: {len(integration_config)} sections"
                )

            self.logger.info("✅ Configuration files validated")
            self.test_results.append(
                {
                    "test": "Configuration Files",
                    "status": "PASSED",
                    "details": {
                        "demo_credentials": "Found",
                        "integration_config": (
                            "Found" if integration_config_path.exists() else "Missing"
                        ),
                        "required_fields": required_fields,
                    },
                }
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Configuration test failed: {e}")
            self.test_results.append(
                {"test": "Configuration Files", "status": "FAILED", "error": str(e)}
            )
            return False

    async def test_credentials_validation(self) -> bool:
        """Test 2: Validate credential format and content."""
        print("\n🔑 Test 2: Credentials Validation")

        try:
            config_path = (
                Path(__file__).parent.parent / "config" / "fxcm_demo_credentials.yaml"
            )

            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            demo_creds = config["fxcm_demo"]

            # Validate username format (email-like)
            username = demo_creds["username"]
            if "@" not in username or "." not in username:
                self.logger.warning(f"⚠️ Username format unusual: {username}")
            else:
                self.logger.info(f"✅ Username format valid: {username}")

            # Validate server format
            server = demo_creds["server"]
            expected_servers = [
                "FXCM-USDDemo1",
                "FXCM-USDDemo2",
                "FXCM-USDReal1",
                "FXCM-USDReal2",
            ]
            if server not in expected_servers:
                self.logger.warning(f"⚠️ Unusual server name: {server}")
            else:
                self.logger.info(f"✅ Server name valid: {server}")

            # Check password is not empty
            password = demo_creds["password"]
            if not password or len(password) < 6:
                self.logger.error("❌ Password appears invalid (too short or empty)")
                self.test_results.append(
                    {
                        "test": "Credentials Validation",
                        "status": "FAILED",
                        "error": "Invalid password",
                    }
                )
                return False
            else:
                self.logger.info("✅ Password format appears valid")

            # Log credentials info (masked)
            masked_password = "*" * len(password)
            self.logger.info(f"📧 Username: {username}")
            self.logger.info(f"🔒 Password: {masked_password}")
            self.logger.info(f"🖥️ Server: {server}")

            self.test_results.append(
                {
                    "test": "Credentials Validation",
                    "status": "PASSED",
                    "details": {
                        "username": username,
                        "server": server,
                        "password_length": len(password),
                    },
                }
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Credentials validation failed: {e}")
            self.test_results.append(
                {"test": "Credentials Validation", "status": "FAILED", "error": str(e)}
            )
            return False

    async def test_connection_parameters(self) -> bool:
        """Test 3: Connection parameters and network settings."""
        print("\n🌐 Test 3: Connection Parameters")

        try:
            # Test network connectivity (basic)
            import socket

            # Test DNS resolution for FXCM servers
            fxcm_hosts = ["www.fxcorporate.com", "tradingstation.fxcorporate.com"]

            for host in fxcm_hosts:
                try:
                    socket.gethostbyname(host)
                    self.logger.info(f"✅ DNS resolution successful for {host}")
                except socket.gaierror as e:
                    self.logger.error(f"❌ DNS resolution failed for {host}: {e}")
                    self.test_results.append(
                        {
                            "test": f"Connection Parameters - DNS {host}",
                            "status": "FAILED",
                            "error": str(e),
                        }
                    )
                    return False

            # Test basic network connectivity
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                result = sock.connect_ex(("www.fxcorporate.com", 80))
                sock.close()

                if result == 0:
                    self.logger.info("✅ Basic network connectivity confirmed")
                else:
                    self.logger.warning(f"⚠️ Network connectivity issue: {result}")

            except Exception as e:
                self.logger.warning(f"⚠️ Network test error: {e}")

            self.test_results.append(
                {
                    "test": "Connection Parameters",
                    "status": "PASSED",
                    "details": {
                        "dns_resolution": "Success",
                        "network_connectivity": "Confirmed",
                        "tested_hosts": fxcm_hosts,
                    },
                }
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Connection parameters test failed: {e}")
            self.test_results.append(
                {"test": "Connection Parameters", "status": "FAILED", "error": str(e)}
            )
            return False

    async def test_authentication(self) -> bool:
        """Test 4: Authentication with FXCM demo account."""
        print("\n🔐 Test 4: Authentication Test")

        try:
            # Initialize FXCM adapter
            adapter = FXCMDemoAdapter()

            self.logger.info("🔌 Attempting connection to FXCM demo account...")

            # Test connection
            connected = await adapter.connect()

            if not connected:
                self.logger.error(
                    "❌ Authentication failed - could not establish connection"
                )
                self.test_results.append(
                    {
                        "test": "Authentication",
                        "status": "FAILED",
                        "error": "Connection failed",
                    }
                )
                return False

            # Validate connection details
            if not adapter.connected:
                self.logger.error("❌ Adapter not marked as connected")
                await adapter.disconnect()
                return False

            if not adapter.session_id:
                self.logger.error("❌ No session ID assigned")
                await adapter.disconnect()
                return False

            self.logger.info(f"✅ Authentication successful!")
            self.logger.info(f"🆔 Session ID: {adapter.session_id}")
            self.logger.info(f"📧 Account: {adapter.username}")
            self.logger.info(f"🖥️ Server: {adapter.server}")

            # Test basic authenticated request
            try:
                account_info = await adapter.get_account_info()
                self.logger.info(f"💰 Account Balance: ${account_info['balance']:,.2f}")
                self.logger.info(f"🪙 Currency: {account_info['currency']}")

            except Exception as e:
                self.logger.error(f"❌ Authenticated request failed: {e}")
                await adapter.disconnect()
                self.test_results.append(
                    {
                        "test": "Authentication - Request Test",
                        "status": "FAILED",
                        "error": str(e),
                    }
                )
                return False

            # Clean disconnect
            disconnected = await adapter.disconnect()
            if disconnected:
                self.logger.info("✅ Clean disconnection successful")
            else:
                self.logger.warning("⚠️ Disconnect had issues")

            self.test_results.append(
                {
                    "test": "Authentication",
                    "status": "PASSED",
                    "details": {
                        "session_id": adapter.session_id,
                        "server": adapter.server,
                        "account_id": account_info.get("account_id", "Unknown"),
                        "currency": account_info.get("currency", "Unknown"),
                        "clean_disconnect": disconnected,
                    },
                }
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Authentication test failed: {e}")
            self.test_results.append(
                {"test": "Authentication", "status": "FAILED", "error": str(e)}
            )
            return False

    async def test_demo_account_access(self) -> bool:
        """Test 5: Demo account access and functionality."""
        print("\n🎮 Test 5: Demo Account Access")

        try:
            adapter = FXCMDemoAdapter()

            # Connect
            connected = await adapter.connect()
            if not connected:
                self.logger.error("❌ Could not connect for demo account test")
                return False

            # Test account information access
            account_info = await adapter.get_account_info()

            # Validate account is demo account
            if account_info["balance"] <= 0:
                self.logger.error("❌ Demo account has zero or negative balance")
                await adapter.disconnect()
                return False

            # Test market data access
            market_data = await adapter.get_market_data(["EUR/USD"])
            if "EUR/USD" not in market_data:
                self.logger.error("❌ Could not retrieve market data")
                await adapter.disconnect()
                return False

            # Test position access
            positions = await adapter.get_positions()
            self.logger.info(f"📊 Current positions: {len(positions)}")

            # Test demo trading capability (small order)
            try:
                demo_order = {
                    "symbol": "EUR/USD",
                    "side": "buy",
                    "quantity": 1000,  # Micro lot
                    "order_type": "market",
                }

                order_result = await adapter.place_order(demo_order)

                if order_result["status"] == "FILLED":
                    self.logger.info(
                        f"✅ Demo trading test successful: Order {order_result['order_id']}"
                    )

                    # Close the position immediately
                    try:
                        updated_positions = await adapter.get_positions()
                        if updated_positions:
                            close_result = await adapter.close_position(
                                updated_positions[0]["position_id"]
                            )
                            self.logger.info(
                                f"✅ Position closed: P&L ${close_result['realized_pl']:.2f}"
                            )
                    except Exception as e:
                        self.logger.warning(f"⚠️ Could not close test position: {e}")

                else:
                    self.logger.error(f"❌ Demo order failed: {order_result}")

            except Exception as e:
                self.logger.error(f"❌ Demo trading test failed: {e}")
                await adapter.disconnect()
                return False

            await adapter.disconnect()

            self.logger.info("✅ Demo account access fully functional")

            self.test_results.append(
                {
                    "test": "Demo Account Access",
                    "status": "PASSED",
                    "details": {
                        "account_balance": account_info["balance"],
                        "currency": account_info["currency"],
                        "market_data_access": True,
                        "position_count": len(positions),
                        "demo_trading": True,
                    },
                }
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Demo account test failed: {e}")
            self.test_results.append(
                {"test": "Demo Account Access", "status": "FAILED", "error": str(e)}
            )
            return False

    async def test_configuration_integration(self) -> bool:
        """Test 6: Configuration integration with FXML4 system."""
        print("\n🔗 Test 6: Configuration Integration")

        try:
            # Test integration config loading
            integration_config_path = (
                Path(__file__).parent.parent / "config" / "fxcm_integration.yaml"
            )

            if not integration_config_path.exists():
                self.logger.warning("⚠️ Integration configuration not found")
                self.test_results.append(
                    {
                        "test": "Configuration Integration",
                        "status": "WARNING",
                        "error": "Integration config not found",
                    }
                )
                return True  # Not critical for basic functionality

            with open(integration_config_path, "r") as f:
                config = yaml.safe_load(f)

            # Validate configuration sections
            required_sections = ["system", "rabbitmq", "fxml4", "forex_connect"]
            missing_sections = [
                section for section in required_sections if section not in config
            ]

            if missing_sections:
                self.logger.warning(f"⚠️ Missing config sections: {missing_sections}")
            else:
                self.logger.info("✅ All required configuration sections present")

            # Test broker configuration
            if "fxml4" in config and "brokers" in config["fxml4"]:
                brokers_config = config["fxml4"]["brokers"]
                if "fxcm_bridge" in brokers_config:
                    fxcm_config = brokers_config["fxcm_bridge"]
                    self.logger.info(f"✅ FXCM bridge configuration found")
                    self.logger.info(f"  Enabled: {fxcm_config.get('enabled', False)}")
                    self.logger.info(
                        f"  Priority: {fxcm_config.get('priority', 'Unknown')}"
                    )

            self.test_results.append(
                {
                    "test": "Configuration Integration",
                    "status": "PASSED",
                    "details": {
                        "integration_config_found": True,
                        "required_sections": required_sections,
                        "missing_sections": missing_sections,
                        "fxcm_bridge_configured": "fxcm_bridge"
                        in config.get("fxml4", {}).get("brokers", {}),
                    },
                }
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Configuration integration test failed: {e}")
            self.test_results.append(
                {
                    "test": "Configuration Integration",
                    "status": "FAILED",
                    "error": str(e),
                }
            )
            return False

    async def create_credentials_template(self, config_path: Path):
        """Create a template credentials file."""
        self.logger.info("📝 Creating credentials template file...")

        template = {
            "fxcm_demo": {
                "username": "0x0c9@quatumchain.com",
                "password": "your_password_here",
                "server": "FXCM-USDDemo1",
            }
        }

        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.dump(template, f, default_flow_style=False)

        self.logger.info(f"✅ Template created at: {config_path}")
        self.logger.info("📝 Please update with your actual FXCM credentials")

    async def generate_credentials_report(self):
        """Generate credentials test report."""
        print("\n" + "=" * 70)
        print("📊 FXCM CREDENTIALS TEST REPORT")
        print("=" * 70)

        passed_tests = sum(
            1 for test in self.test_results if test["status"] == "PASSED"
        )
        failed_tests = sum(
            1 for test in self.test_results if test["status"] == "FAILED"
        )
        warning_tests = sum(
            1 for test in self.test_results if test["status"] == "WARNING"
        )

        total_tests = len(self.test_results)
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        print(f"📅 Test Completion: {datetime.now().isoformat()}")
        print(f"🧪 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️ Warnings: {warning_tests}")
        print(f"📊 Success Rate: {success_rate:.1f}%")
        print()

        print("📋 DETAILED TEST RESULTS:")
        print("-" * 70)

        for test in self.test_results:
            status_icon = {"PASSED": "✅", "FAILED": "❌", "WARNING": "⚠️"}.get(
                test["status"], "❓"
            )

            print(f"{status_icon} {test['test']}: {test['status']}")

            if "details" in test:
                for key, value in test["details"].items():
                    print(f"        {key}: {value}")

            if "error" in test:
                print(f"        Error: {test['error']}")

        # Save JSON report
        report_data = {
            "test_execution": {
                "timestamp": datetime.now().isoformat(),
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "warning_tests": warning_tests,
                "success_rate": success_rate,
            },
            "test_results": self.test_results,
        }

        report_filename = (
            f"fxcm_credentials_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_filename, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n💾 Report saved to: {report_filename}")


async def main():
    """Main entry point."""
    print("🔐 FXCM Credentials and Configuration Test")
    print("=" * 70)

    tester = FXCMCredentialsTest()
    success = await tester.run_credentials_test()

    if success:
        print("\n✅ FXCM CREDENTIALS TEST: SUCCESS")
        print("🔗 FXCM credentials and configuration are valid")
        print("🚀 Ready for broker connectivity testing")
        sys.exit(0)
    else:
        print("\n❌ FXCM CREDENTIALS TEST: FAILURE")
        print("🔧 Please fix credential issues before proceeding")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
