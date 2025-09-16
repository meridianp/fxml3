#!/usr/bin/env python3
"""Setup script for Polygon.io demo - adds API key to .env file."""

import os
from pathlib import Path


def setup_polygon_demo():
    """Add Polygon API key to .env file."""
    env_file = Path(".env")

    # Check if POLYGON_API_KEY already exists
    if env_file.exists():
        with open(env_file, "r") as f:
            content = f.read()
            if "POLYGON_API_KEY" in content:
                print("POLYGON_API_KEY already exists in .env file")
                return

    # Add Polygon API key
    polygon_key = input(
        "Enter your Polygon.io API key (or press Enter to skip): "
    ).strip()

    if not polygon_key:
        print("\nTo use the LLM backtesting feature, you need a Polygon.io API key.")
        print("You can get a free API key at: https://polygon.io/")
        print("\nOnce you have a key, add it to your .env file:")
        print("POLYGON_API_KEY=your_key_here")
        return

    # Append to .env file
    with open(env_file, "a") as f:
        f.write(f"\n# Polygon.io API key for historical data\n")
        f.write(f"POLYGON_API_KEY={polygon_key}\n")

    print(f"✅ Added POLYGON_API_KEY to {env_file}")
    print("\nYou can now run the LLM backtest with:")
    print("python scripts/test_llm_backtest.py")


if __name__ == "__main__":
    setup_polygon_demo()
