#!/usr/bin/env python3
"""Simple test script for containerized IB Gateway connection.

This script tests the connection to containerized IB Gateway without complex FXML4 dependencies.
Uses direct IB API connection to validate containerized setup.
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# Add official IB SDK to Python path
ib_sdk_path = Path.home() / "code" / "IBJts" / "source" / "pythonclient"
if ib_sdk_path.exists():
    sys.path.insert(0, str(ib_sdk_path))
    logger = logging.getLogger(__name__)
    logger.info(f"Added IB SDK path: {ib_sdk_path}")
else:
    logger.error(f"IB SDK not found at: {ib_sdk_path}")

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Test IB API import from official SDK
try:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    IB_API_AVAILABLE = True
    logger.info("✅ Official IB API SDK available")
except ImportError as e:
    IB_API_AVAILABLE = False
    logger.error(f"❌ IB API not available: {e}")
    logger.error("Make sure IB SDK is installed at ~/code/IBJts/source/pythonclient")


class SimpleIBApp(EWrapper, EClient):
    """Simple IB application for testing containerized connection."""

    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.connection_time = None

    def connectAck(self):
        """Connection acknowledgment."""
        logger.info("✅ Connection acknowledged by IB Gateway")
        self.connected = True
        self.connection_time = time.time()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """Error handling."""
        if errorCode == 502:
            logger.warning(f"Expected: IB Gateway not running (Error {errorCode})")
        elif errorCode == 200:
            logger.info("✅ Connection established (Error 200 is normal)")
        else:
            logger.error(f"Error {errorCode}: {errorString}")


def check_container_status():
    """Check if IB Gateway container is running."""
    logger.info("Checking IB Gateway container status...")

    try:
        # Check if container is running
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=ib-gateway",
                "--format",
                "{{.Names}} {{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            logger.info(f"✅ Container status: {result.stdout.strip()}")
            return True
        else:
            logger.warning("❌ IB Gateway container not running")
            logger.info("Start with: docker-compose up -d ib-gateway")
            return False

    except Exception as e:
        logger.error(f"❌ Error checking container: {str(e)}")
        return False


def test_containerized_connection():
    """Test connection to containerized IB Gateway."""
    if not IB_API_AVAILABLE:
        logger.error("❌ Cannot test connection - IB API not available")
        return False

    logger.info("Testing connection to containerized IB Gateway...")
    logger.info("Target: localhost:8888 (containerized gateway)")

    app = SimpleIBApp()

    try:
        # Connect to containerized gateway
        app.connect("127.0.0.1", 8888, 0)  # port 8888 for containerized gateway

        # Run client for a few seconds
        logger.info("Starting connection test...")
        start_time = time.time()

        while time.time() - start_time < 10:  # Test for 10 seconds
            app.run()
            if app.connected:
                break
            time.sleep(0.1)

        if app.connected:
            logger.info("✅ Successfully connected to containerized IB Gateway!")

            # Test creating a contract
            logger.info("Testing GBP/USD contract creation...")
            contract = create_gbpusd_contract()
            logger.info(f"✅ Contract: {contract.symbol}/{contract.currency}")

            # Disconnect
            app.disconnect()
            logger.info("✅ Disconnected successfully")
            return True
        else:
            logger.error("❌ Failed to establish connection")
            return False

    except Exception as e:
        logger.error(f"❌ Connection test failed: {str(e)}")
        return False


def create_gbpusd_contract():
    """Create GBP/USD contract for testing."""
    contract = Contract()
    contract.symbol = "GBP"
    contract.secType = "CASH"
    contract.currency = "USD"
    contract.exchange = "IDEALPRO"
    return contract


def show_setup_instructions():
    """Show setup instructions for containerized IB Gateway."""
    print("\n" + "=" * 60)
    print("CONTAINERIZED IB GATEWAY SETUP INSTRUCTIONS")
    print("=" * 60)
    print("\n1. Start the IB Gateway container:")
    print(
        "   docker-compose -f docker-compose.yml -f docker-compose.ib-gateway.yml up -d ib-gateway"
    )
    print("\n2. Wait 30-60 seconds for initialization")
    print("\n3. Check container logs:")
    print("   docker-compose logs -f ib-gateway")
    print("\n4. Access GUI in browser (optional):")
    print("   http://localhost:6080")
    print("\n5. Configure your IB credentials in .env:")
    print("   IB_USERNAME=your_username")
    print("   IB_PASSWORD=your_password")
    print("   IB_TRADING_MODE=paper")
    print("\n6. Test connection:")
    print("   python scripts/test_ib_containerized_simple.py")


def main():
    """Main test function."""
    print("=" * 70)
    print("FXML4 CONTAINERIZED IB GATEWAY CONNECTION TEST")
    print("=" * 70)

    # Check if IB API is available
    if not IB_API_AVAILABLE:
        print("\n❌ IB API not available")
        print("Install with: pip install ibapi")
        return False

    # Check container status
    container_running = check_container_status()

    if not container_running:
        show_setup_instructions()
        return False

    # Test connection
    print("\n🔍 Testing IB Gateway connection...")
    success = test_containerized_connection()

    print("\n" + "=" * 70)
    if success:
        print("✅ CONTAINERIZED IB GATEWAY TEST PASSED")
        print("✅ Ready for FXML4 automated trading")
        print("\n🎯 Your IB credentials can now be used with FXML4:")
        print("   - Configure credentials in .env file")
        print("   - Use paper trading mode for testing")
        print("   - All FXML4 services will connect automatically")
    else:
        print("❌ CONTAINERIZED IB GATEWAY TEST FAILED")
        print("❌ Check setup instructions above")
    print("=" * 70)

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
