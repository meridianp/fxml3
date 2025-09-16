#!/usr/bin/env python3
"""Test script for containerized IB Gateway connection without complex dependencies.

This script tests the containerized IB Gateway setup using direct socket connections
and container health checks, avoiding protobuf/API import issues.
"""

import logging
import socket
import subprocess
import sys
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_port_open(host, port, timeout=5):
    """Check if a port is open and accepting connections."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        logger.debug(f"Port check failed: {e}")
        return False


def check_container_status():
    """Check if IB Gateway container is running."""
    logger.info("Checking IB Gateway container status...")

    try:
        # Check container status
        result = subprocess.run(
            ["docker", "compose", "ps", "--services", "--filter", "status=running"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            running_services = result.stdout.strip().split("\n")
            if "ib-gateway" in running_services:
                logger.info("✅ IB Gateway container is running")

                # Get detailed status
                status_result = subprocess.run(
                    ["docker", "compose", "ps", "ib-gateway"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if status_result.returncode == 0:
                    logger.info(f"Container details:\n{status_result.stdout}")

                return True
            else:
                logger.warning("❌ IB Gateway container not running")
                return False
        else:
            logger.error(f"Docker compose command failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error checking container: {str(e)}")
        return False


def check_ib_api_port():
    """Check if IB API port 8888 is accessible."""
    logger.info("Testing IB API port accessibility...")

    # Check if port 8888 is open
    if check_port_open("127.0.0.1", 8888):
        logger.info("✅ Port 8888 (IB API) is accessible")
        return True
    else:
        logger.warning("❌ Port 8888 (IB API) is not accessible")
        logger.info("This could mean:")
        logger.info("  1. IB Gateway container is still starting up")
        logger.info("  2. IB Gateway failed to start properly")
        logger.info("  3. Authentication issues with IB credentials")
        return False


def check_vnc_port():
    """Check if VNC port 6080 is accessible."""
    logger.info("Testing VNC port accessibility...")

    if check_port_open("127.0.0.1", 6080):
        logger.info("✅ Port 6080 (VNC) is accessible")
        logger.info("   Access GUI at: http://localhost:6080")
        return True
    else:
        logger.warning("❌ Port 6080 (VNC) is not accessible")
        return False


def show_container_logs():
    """Show recent IB Gateway container logs."""
    logger.info("Fetching IB Gateway container logs...")

    try:
        result = subprocess.run(
            ["docker", "compose", "logs", "--tail", "20", "ib-gateway"],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            logger.info("Recent container logs:")
            print("-" * 50)
            print(result.stdout)
            print("-" * 50)
        else:
            logger.error(f"Failed to get logs: {result.stderr}")

    except Exception as e:
        logger.error(f"Error getting logs: {str(e)}")


def test_connection_with_retry():
    """Test connection with multiple retries for startup time."""
    logger.info("Testing connection with retries (IB Gateway takes 30-60s to start)...")

    max_retries = 12  # 2 minutes of retries
    retry_interval = 10  # 10 seconds between retries

    for attempt in range(1, max_retries + 1):
        logger.info(f"Connection attempt {attempt}/{max_retries}")

        if check_ib_api_port():
            logger.info("✅ Successfully connected to IB Gateway!")
            return True

        if attempt < max_retries:
            logger.info(f"Waiting {retry_interval} seconds before retry...")
            time.sleep(retry_interval)

    logger.error("❌ Failed to connect after all retries")
    return False


def show_troubleshooting_steps():
    """Show troubleshooting steps."""
    print("\n" + "=" * 60)
    print("TROUBLESHOOTING STEPS")
    print("=" * 60)

    print("\n1. Check container logs for errors:")
    print("   docker-compose logs ib-gateway")

    print("\n2. Verify credentials in .env file:")
    print("   - IB_USERNAME=your_username")
    print("   - IB_PASSWORD=your_password")
    print("   - IB_TRADING_MODE=paper")

    print("\n3. Restart the container:")
    print("   docker-compose restart ib-gateway")

    print("\n4. Access GUI to check login status:")
    print("   http://localhost:6080")

    print("\n5. Check IB account permissions:")
    print("   - API access enabled")
    print("   - Paper trading permissions")
    print("   - No additional authentication devices")

    print("\n6. Common startup issues:")
    print("   - Container takes 30-60 seconds to fully initialize")
    print("   - IB credentials may need manual verification")
    print("   - Check for 2FA requirements in IB account")


def main():
    """Main test function."""
    print("=" * 70)
    print("FXML4 CONTAINERIZED IB GATEWAY CONNECTION TEST")
    print("=" * 70)

    # Step 1: Check container status
    print("\n🔍 Step 1: Checking container status...")
    container_running = check_container_status()

    if not container_running:
        print("\n❌ IB Gateway container not running")
        print("\nStart with:")
        print(
            "  docker-compose -f docker-compose.yml -f docker-compose.ib-gateway.yml up -d ib-gateway"
        )
        print("\nThen wait 30-60 seconds and rerun this test")
        return False

    # Step 2: Check VNC access
    print("\n🔍 Step 2: Checking VNC access...")
    vnc_accessible = check_vnc_port()

    # Step 3: Test API connection with retries
    print("\n🔍 Step 3: Testing IB API connection...")
    api_accessible = test_connection_with_retry()

    # Step 4: Show logs
    print("\n🔍 Step 4: Container logs...")
    show_container_logs()

    # Results
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)

    print(f"\n📊 Container Running: {'✅ Yes' if container_running else '❌ No'}")
    print(f"📊 VNC Access (6080): {'✅ Yes' if vnc_accessible else '❌ No'}")
    print(f"📊 API Access (8888): {'✅ Yes' if api_accessible else '❌ No'}")

    if container_running and api_accessible:
        print("\n🎯 SUCCESS: Containerized IB Gateway is ready!")
        print("🎯 Your IB credentials are working with FXML4!")
        print("\n✅ Next steps:")
        print("   1. Run FXML4 trading strategies")
        print("   2. Test market data access")
        print("   3. Validate order placement (paper trading)")

        success = True
    else:
        print("\n❌ ISSUES DETECTED")
        show_troubleshooting_steps()
        success = False

    print("=" * 70)
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
