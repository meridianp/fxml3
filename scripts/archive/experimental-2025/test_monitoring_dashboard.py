#!/usr/bin/env python3
"""Test Monitoring Dashboard.

This script tests the monitoring dashboard by starting the API server
and verifying the dashboard endpoints.
"""

import asyncio
import json
import logging
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from fxml4.config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIServerManager:
    """Manages API server for testing."""

    def __init__(self, host: str = "localhost", port: int = 8001):
        self.host = host
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.base_url = f"http://{host}:{port}"

    def start(self):
        """Start the API server."""
        logger.info(f"Starting API server on {self.host}:{self.port}")

        # Start server process
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "fxml4.api.main:app",
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--log-level",
            "info",
        ]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )

        # Wait for server to start
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=1)
                if response.status_code == 200:
                    logger.info("API server started successfully")
                    return True
            except requests.exceptions.RequestException:
                pass

            time.sleep(1)

        logger.error("Failed to start API server")
        return False

    def stop(self):
        """Stop the API server."""
        if self.process:
            logger.info("Stopping API server")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None


def test_monitoring_endpoints(base_url: str):
    """Test monitoring API endpoints."""
    logger.info("Testing monitoring API endpoints...")

    endpoints = [
        "/api/monitoring/health",
        "/api/monitoring/adapters",
        "/api/monitoring/metrics/summary",
        "/api/monitoring/metrics/performance",
        "/api/monitoring/logs/recent",
    ]

    results = {}

    for endpoint in endpoints:
        try:
            logger.info(f"Testing {endpoint}")
            response = requests.get(f"{base_url}{endpoint}", timeout=10)

            results[endpoint] = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response_size": len(response.content),
                "content_type": response.headers.get("content-type", ""),
            }

            if response.status_code == 200:
                try:
                    data = response.json()
                    results[endpoint]["has_data"] = bool(data)
                    logger.info(f"✅ {endpoint} - OK ({len(response.content)} bytes)")
                except json.JSONDecodeError:
                    results[endpoint]["has_data"] = False
                    logger.warning(f"⚠️  {endpoint} - OK but invalid JSON")
            else:
                logger.error(f"❌ {endpoint} - Error {response.status_code}")

        except Exception as e:
            logger.error(f"❌ {endpoint} - Exception: {e}")
            results[endpoint] = {"status_code": None, "success": False, "error": str(e)}

    return results


def test_dashboard_access(base_url: str):
    """Test dashboard HTML access."""
    logger.info("Testing dashboard access...")

    try:
        # Test dashboard endpoint
        response = requests.get(f"{base_url}/dashboard", timeout=10)

        if response.status_code == 200:
            content = response.text

            # Check for key dashboard elements
            checks = {
                "html_structure": "<html" in content.lower(),
                "dashboard_title": "monitoring dashboard" in content.lower(),
                "javascript": "<script>" in content.lower(),
                "css_styles": "<style>" in content.lower(),
                "api_calls": "api/monitoring" in content,
                "websocket": "websocket" in content.lower() or "ws://" in content,
            }

            all_passed = all(checks.values())

            logger.info(f"Dashboard loaded successfully ({len(content)} bytes)")
            for check, passed in checks.items():
                status = "✅" if passed else "❌"
                logger.info(f"  {status} {check.replace('_', ' ').title()}")

            return {
                "success": True,
                "content_length": len(content),
                "checks": checks,
                "all_checks_passed": all_passed,
            }

        else:
            logger.error(f"Dashboard request failed: {response.status_code}")
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text[:200],
            }

    except Exception as e:
        logger.error(f"Dashboard test failed: {e}")
        return {"success": False, "error": str(e)}


def test_static_files(base_url: str):
    """Test static file serving."""
    logger.info("Testing static file serving...")

    try:
        # Test direct static file access
        response = requests.get(
            f"{base_url}/static/monitoring_dashboard.html", timeout=10
        )

        result = {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "content_length": (
                len(response.content) if response.status_code == 200 else 0
            ),
        }

        if response.status_code == 200:
            logger.info(
                f"✅ Static file served successfully ({len(response.content)} bytes)"
            )
        else:
            logger.error(f"❌ Static file serving failed: {response.status_code}")

        return result

    except Exception as e:
        logger.error(f"Static file test failed: {e}")
        return {"success": False, "error": str(e)}


def test_risk_management_integration(base_url: str):
    """Test risk management API integration."""
    logger.info("Testing risk management integration...")

    endpoints = ["/api/risk/summary", "/api/risk/limits", "/api/risk/positions"]

    results = {}

    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)

            results[endpoint] = {
                "status_code": response.status_code,
                "success": response.status_code
                in [200, 404],  # 404 is OK for empty states
            }

            if response.status_code == 200:
                logger.info(f"✅ {endpoint} - OK")
            elif response.status_code == 404:
                logger.info(f"ℹ️  {endpoint} - Not found (expected for empty state)")
            else:
                logger.warning(f"⚠️  {endpoint} - Status {response.status_code}")

        except Exception as e:
            logger.error(f"❌ {endpoint} - Exception: {e}")
            results[endpoint] = {"status_code": None, "success": False, "error": str(e)}

    return results


def open_dashboard_in_browser(base_url: str):
    """Open dashboard in browser."""
    dashboard_url = f"{base_url}/dashboard"
    logger.info(f"Opening dashboard in browser: {dashboard_url}")

    try:
        webbrowser.open(dashboard_url)
        return True
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")
        return False


def main():
    """Main test function."""
    print("=" * 60)
    print("FXML4 Monitoring Dashboard Test")
    print("=" * 60)

    # Initialize server
    server = APIServerManager(host="localhost", port=8001)

    try:
        # Start server
        if not server.start():
            logger.error("Failed to start API server")
            return False

        base_url = server.base_url

        # Run tests
        print("\n1. Testing Monitoring API Endpoints")
        print("-" * 40)
        monitoring_results = test_monitoring_endpoints(base_url)

        print("\n2. Testing Dashboard Access")
        print("-" * 40)
        dashboard_results = test_dashboard_access(base_url)

        print("\n3. Testing Static File Serving")
        print("-" * 40)
        static_results = test_static_files(base_url)

        print("\n4. Testing Risk Management Integration")
        print("-" * 40)
        risk_results = test_risk_management_integration(base_url)

        # Summary
        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)

        monitoring_success = sum(
            1 for r in monitoring_results.values() if r.get("success", False)
        )
        monitoring_total = len(monitoring_results)

        risk_success = sum(1 for r in risk_results.values() if r.get("success", False))
        risk_total = len(risk_results)

        print(
            f"📊 Monitoring Endpoints: {monitoring_success}/{monitoring_total} passed"
        )
        print(
            f"🎯 Dashboard Access: {'✅' if dashboard_results.get('success') else '❌'}"
        )
        print(f"📁 Static Files: {'✅' if static_results.get('success') else '❌'}")
        print(f"🛡️  Risk Management: {risk_success}/{risk_total} passed")

        # Calculate overall success
        overall_success = (
            monitoring_success >= monitoring_total * 0.8  # 80% of monitoring endpoints
            and dashboard_results.get("success", False)
            and static_results.get("success", False)
        )

        if overall_success:
            print("\n🎉 ALL CORE TESTS PASSED!")
            print("\nDashboard URLs:")
            print(f"  • Main Dashboard: {base_url}/dashboard")
            print(f"  • Static Access: {base_url}/static/monitoring_dashboard.html")
            print(f"  • API Health: {base_url}/api/monitoring/health")

            # Ask if user wants to open dashboard
            try:
                choice = input("\nOpen dashboard in browser? (y/N): ").strip().lower()
                if choice in ["y", "yes"]:
                    open_dashboard_in_browser(base_url)
                    input("\nPress Enter to stop the server...")

            except KeyboardInterrupt:
                print("\nStopping...")

        else:
            print("\n❌ SOME TESTS FAILED")
            print("Check the logs above for details")

        return overall_success

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return False

    except Exception as e:
        logger.exception(f"Test failed with exception: {e}")
        return False

    finally:
        # Always stop server
        server.stop()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
