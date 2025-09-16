#!/usr/bin/env python3
"""
Test script for the configuration module.

This script tests loading configuration and accessing data feed configuration.
"""

import os
import sys
from pprint import pprint

# Add the project root to the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from fxml4.config import get_data_feed_config, load_config


def test_config():
    """Test configuration loading and access."""
    # Load the full configuration
    config = load_config()

    print("=== Full Configuration ===")
    print(f"Configuration keys: {list(config.keys())}")

    # Get data feed configuration
    ib_config = get_data_feed_config("ib")

    print("\n=== IB Data Feed Configuration ===")
    pprint(ib_config)

    # Test host and port access
    host = ib_config.get("host", "default_host")
    port = ib_config.get("port", 0)

    print(f"\nHost: {host}, Port: {port}")

    # Test symbol list
    symbols = ib_config.get("symbols", [])
    print(f"Symbols: {symbols}")

    # Test real-time updates configuration
    real_time = ib_config.get("real_time_updates", False)
    update_interval = ib_config.get("update_interval", 0)

    print(f"Real-time updates: {real_time}")
    print(f"Update interval: {update_interval}s")


if __name__ == "__main__":
    test_config()
