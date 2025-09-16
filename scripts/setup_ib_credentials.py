#!/usr/bin/env python3
"""Setup script for Interactive Brokers credentials and containerized gateway.

This script helps configure your IB credentials for use with FXML4's containerized architecture.
"""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Main setup function."""
    print("=" * 70)
    print("FXML4 INTERACTIVE BROKERS SETUP")
    print("=" * 70)

    print("\n🎯 You mentioned you have active IB credentials for paper trading.")
    print("Let's configure them for FXML4's containerized architecture.\n")

    # Check if .env file exists
    env_file = Path(".env")
    env_example = Path(".env.example")

    if not env_file.exists():
        if env_example.exists():
            print("📝 Creating .env file from template...")
            import shutil

            shutil.copy(env_example, env_file)
            print(f"✅ Created {env_file}")
        else:
            print("❌ No .env.example file found")
            return

    print("📋 CONFIGURATION STEPS:")
    print("\n1. Edit your .env file and set your IB credentials:")
    print(f"   vim {env_file}")
    print("\n   Update these lines:")
    print("   IB_USERNAME=your_actual_username")
    print("   IB_PASSWORD=your_actual_password")
    print("   IB_TRADING_MODE=paper")

    print("\n2. Start the containerized IB Gateway:")
    print(
        "   docker-compose -f docker-compose.yml -f docker-compose.ib-gateway.yml up -d ib-gateway"
    )

    print("\n3. Monitor the startup (takes 30-60 seconds):")
    print("   docker-compose logs -f ib-gateway")

    print("\n4. Access IB Gateway GUI in browser (optional):")
    print("   http://localhost:6080")
    print("   - Use this to verify login and enable API access if needed")

    print("\n5. Test the connection:")
    print("   python scripts/test_containerized_connection.py")

    print("\n" + "=" * 70)
    print("CONTAINERIZED IB GATEWAY BENEFITS")
    print("=" * 70)

    print("\n✅ Full Automation:")
    print("   - IBC handles login, 2FA, and session management")
    print("   - Automatic reconnection on connection loss")
    print("   - No manual intervention required")

    print("\n✅ Production Ready:")
    print("   - Integrates with FXML4's Kubernetes deployment")
    print("   - Built-in health checks and monitoring")
    print("   - Scales with your trading infrastructure")

    print("\n✅ Resource Efficient:")
    print("   - Uses IB Gateway (minimal GUI) vs full TWS")
    print("   - Container resource limits and isolation")
    print("   - No desktop environment dependencies")

    print("\n✅ Complete API Access:")
    print("   - Full Interactive Brokers API functionality")
    print("   - Same API features as desktop TWS")
    print("   - FXML4 connects via port 8888")

    print("\n🎯 Next Steps:")
    print("1. Configure your credentials in .env")
    print("2. Start the containerized gateway")
    print("3. Test connection with your real account")
    print("4. Deploy FXML4 trading strategies")

    # Check Docker availability
    print("\n🔍 Checking Docker availability...")
    try:
        result = subprocess.run(
            ["docker", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
        else:
            print("❌ Docker command failed")
    except Exception:
        print("❌ Docker not found - install Docker to proceed")

    # Check Docker Compose
    try:
        result = subprocess.run(
            ["docker-compose", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
        else:
            print("❌ Docker Compose command failed")
    except Exception:
        print("❌ Docker Compose not found - install to proceed")

    print("\n" + "=" * 70)
    print("READY TO USE YOUR IB CREDENTIALS WITH FXML4!")
    print("=" * 70)


if __name__ == "__main__":
    main()
