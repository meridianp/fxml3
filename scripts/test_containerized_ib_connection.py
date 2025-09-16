#!/usr/bin/env python3
"""Test script for containerized IB Gateway connection.

This script tests the connection to the containerized Interactive Brokers Gateway
and validates that all components are working properly.

Usage:
    python scripts/test_containerized_ib_connection.py
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fxml4.data_engineering.data_feeds.robust_ib_client import RobustIBClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_ib_config():
    """Get IB configuration from environment variables or defaults."""
    return {
        "host": os.getenv("IB_HOST", "127.0.0.1"),
        "port": int(os.getenv("IB_PORT", "8888")),  # Containerized gateway default
        "client_id": int(os.getenv("IB_CLIENT_ID", "0")),
        "reconnect_attempts": 5,
        "reconnect_delay": 3,
        "request_timeout": 30,
        "rate_limit_rps": 10,
        "circuit_breaker_threshold": 3,
        "health_check_interval": 30,
    }


def test_containerized_connection():
    """Test connection to containerized IB Gateway."""
    logger.info("Testing containerized IB Gateway connection...")

    # Get configuration
    config = get_ib_config()
    logger.info(
        f"Connection config: {config['host']}:{config['port']} (client_id: {config['client_id']})"
    )

    # Test connection
    try:
        client = RobustIBClient(config)

        logger.info("Attempting to connect to containerized IB Gateway...")
        success = client.connect()

        if success:
            logger.info("✅ Successfully connected to containerized IB Gateway!")

            # Test basic functionality
            logger.info("Testing contract creation...")
            time.sleep(2)  # Allow connection to stabilize

            # Test GBP/USD contract (primary trading pair)
            logger.info("Creating GBP/USD contract...")
            gbpusd_contract = create_gbpusd_contract()
            logger.info(
                f"✅ Contract created: {gbpusd_contract.symbol} {gbpusd_contract.currency}"
            )

            # Test disconnection
            logger.info("Testing disconnection...")
            client.disconnect()
            logger.info("✅ Disconnected successfully")

            return True

        else:
            logger.error("❌ Failed to connect to containerized IB Gateway")
            logger.error("Make sure the IB Gateway container is running:")
            logger.error("  docker-compose up ib-gateway")
            return False

    except Exception as e:
        logger.error(f"❌ Connection test failed: {str(e)}")
        logger.error("Troubleshooting steps:")
        logger.error("1. Check if IB Gateway container is running: docker-compose ps")
        logger.error("2. Check container logs: docker-compose logs ib-gateway")
        logger.error("3. Verify port 8888 is accessible: curl http://localhost:8888")
        return False


def create_gbpusd_contract():
    """Create a GBP/USD forex contract for testing."""
    try:
        from ibapi.contract import Contract
    except ImportError:
        logger.error("IB API not available. Install with: pip install ibapi")
        raise

    contract = Contract()
    contract.symbol = "GBP"
    contract.secType = "CASH"
    contract.currency = "USD"
    contract.exchange = "IDEALPRO"
    return contract


def check_container_status():
    """Check if IB Gateway container is running."""
    logger.info("Checking IB Gateway container status...")

    import subprocess

    try:
        # Check if container is running
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=ib-gateway", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            logger.info(f"✅ IB Gateway container status: {result.stdout.strip()}")
            return True
        else:
            logger.warning("❌ IB Gateway container not running")
            logger.info("Start with: docker-compose up -d ib-gateway")
            return False

    except subprocess.TimeoutExpired:
        logger.error("❌ Docker command timed out")
        return False
    except FileNotFoundError:
        logger.error("❌ Docker not found. Is Docker installed?")
        return False
    except Exception as e:
        logger.error(f"❌ Error checking container status: {str(e)}")
        return False


def main():
    """Main test function."""
    print("=" * 60)
    print("FXML4 Containerized IB Gateway Connection Test")
    print("=" * 60)

    # Check Docker container status first
    container_running = check_container_status()

    if not container_running:
        print("\n⚠️  IB Gateway container not running. Please start it first:")
        print("   docker-compose up -d ib-gateway")
        print("   Then wait 30-60 seconds for initialization")
        return False

    # Test connection
    print("\n🔍 Testing IB Gateway connection...")
    success = test_containerized_connection()

    print("\n" + "=" * 60)
    if success:
        print("✅ CONTAINERIZED IB GATEWAY CONNECTION TEST PASSED")
        print("✅ Ready for automated trading with FXML4")
    else:
        print("❌ CONTAINERIZED IB GATEWAY CONNECTION TEST FAILED")
        print("❌ Check troubleshooting steps above")
    print("=" * 60)

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
