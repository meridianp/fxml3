#!/usr/bin/env python3
"""
Basic Test Runner for FXML4

Quick and simple test execution for development workflow.
Focuses on fast feedback and essential test coverage.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Project root path for reference (no sys.path manipulation needed with wrapper)
project_root = Path(__file__).parent.parent.parent

# Get Python executable (prefer virtual environment)
if os.environ.get("VIRTUAL_ENV"):
    PYTHON_EXEC = os.path.join(os.environ["VIRTUAL_ENV"], "bin", "python")
elif (project_root / "venv" / "bin" / "python").exists():
    PYTHON_EXEC = str(project_root / "venv" / "bin" / "python")
else:
    PYTHON_EXEC = "python"


def setup_test_environment():
    """Setup minimal test environment."""
    test_env = {
        "FXML4_JWT_SECRET_KEY": "test-secret-key",
        "FXML4_JWT_TOKEN_EXPIRE_MINUTES": "60",
        "FXML4_DB_HOST": "localhost",
        "FXML4_DB_PORT": "5433",
        "FXML4_DB_NAME": "fxml4_test",
        "FXML4_DB_USER": "test_user",
        "FXML4_DB_PASSWORD": "test_password",
        "ALPHA_VANTAGE_API_KEY": "test-key",
        "POLYGON_API_KEY": "test-key",
        "OPENAI_API_KEY": "test-key",
        "ANTHROPIC_API_KEY": "test-key",
        "PYTHONPATH": str(project_root),
        "TESTING": "1",
    }

    for key, value in test_env.items():
        os.environ[key] = value

    print("✓ Test environment configured")


def run_fast_tests():
    """Run fast unit tests for quick feedback."""
    print("🚀 Running fast tests...")

    cmd = [
        PYTHON_EXEC,
        "-m",
        "pytest",
        "tests/",
        "-m",
        "not slow and not requires_ib and not requires_db",
        "-v",
        "--tb=short",
        "--durations=5",
        "--disable-warnings",
    ]

    start_time = time.time()
    result = subprocess.run(cmd, cwd=project_root)
    execution_time = time.time() - start_time

    print(f"\n⏱️  Execution time: {execution_time:.2f}s")
    return result.returncode == 0


def run_unit_tests():
    """Run all unit tests."""
    print("🧪 Running unit tests...")

    cmd = [
        PYTHON_EXEC,
        "-m",
        "pytest",
        "tests/unit/",
        "-v",
        "--tb=short",
        "--durations=10",
    ]

    start_time = time.time()
    result = subprocess.run(cmd, cwd=project_root)
    execution_time = time.time() - start_time

    print(f"\n⏱️  Execution time: {execution_time:.2f}s")
    return result.returncode == 0


def run_security_tests():
    """Run security tests."""
    print("🔒 Running security tests...")

    cmd = [PYTHON_EXEC, "-m", "pytest", "tests/", "-m", "security", "-v", "--tb=short"]

    start_time = time.time()
    result = subprocess.run(cmd, cwd=project_root)
    execution_time = time.time() - start_time

    print(f"\n⏱️  Execution time: {execution_time:.2f}s")
    return result.returncode == 0


def run_api_tests():
    """Run API tests."""
    print("🌐 Running API tests...")

    cmd = [PYTHON_EXEC, "-m", "pytest", "tests/", "-m", "api", "-v", "--tb=short"]

    start_time = time.time()
    result = subprocess.run(cmd, cwd=project_root)
    execution_time = time.time() - start_time

    print(f"\n⏱️  Execution time: {execution_time:.2f}s")
    return result.returncode == 0


def run_smoke_tests():
    """Run minimal smoke tests for basic validation."""
    print("💨 Running smoke tests...")

    cmd = [
        PYTHON_EXEC,
        "-m",
        "pytest",
        "tests/",
        "-m",
        "fast or unit",
        "-x",  # Stop on first failure
        "--tb=line",
        "--disable-warnings",
        "--durations=3",
    ]

    start_time = time.time()
    result = subprocess.run(cmd, cwd=project_root)
    execution_time = time.time() - start_time

    print(f"\n⏱️  Execution time: {execution_time:.2f}s")
    return result.returncode == 0


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(
            """
FXML4 Basic Test Runner

Usage:
  python run_basic_tests.py <command>

Commands:
  fast      - Run fast tests (no DB, no IB, no slow tests)
  unit      - Run all unit tests
  security  - Run security tests
  api       - Run API tests
  smoke     - Run smoke tests (minimal validation)

Examples:
  python run_basic_tests.py fast
  python run_basic_tests.py unit
  python run_basic_tests.py smoke
        """
        )
        return 1

    command = sys.argv[1].lower()

    # Setup environment
    setup_test_environment()

    # Route to appropriate test runner
    if command == "fast":
        success = run_fast_tests()
    elif command == "unit":
        success = run_unit_tests()
    elif command == "security":
        success = run_security_tests()
    elif command == "api":
        success = run_api_tests()
    elif command == "smoke":
        success = run_smoke_tests()
    else:
        print(f"❌ Unknown command: {command}")
        return 1

    if success:
        print("✅ Tests passed!")
        return 0
    else:
        print("❌ Tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
