#!/usr/bin/env python3
"""
Enhanced Test Suite Runner for FXML4

This script provides a comprehensive test execution environment with:
- Environment setup and validation
- Intelligent test selection by markers
- Performance monitoring
- Detailed reporting
- Test isolation and cleanup
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import paths handled by PYTHONPATH wrapper
project_root = Path(__file__).parent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("test_execution.log")],
)
logger = logging.getLogger(__name__)


class TestEnvironmentManager:
    """Manages test environment setup and teardown."""

    def __init__(self):
        self.venv_activated = False
        self.temp_files = []

    def setup_environment(self) -> bool:
        """Setup test environment."""
        try:
            # Check virtual environment
            if "VIRTUAL_ENV" not in os.environ:
                logger.warning("Virtual environment not activated")
                # Try to activate if venv exists
                venv_path = project_root / "venv"
                if venv_path.exists():
                    activate_script = venv_path / "bin" / "activate"
                    if activate_script.exists():
                        logger.info("Activating virtual environment...")
                        # Note: In production, proper venv activation requires shell integration

            # Set test environment variables
            test_env_vars = {
                "FXML4_JWT_SECRET_KEY": "test-secret-key-for-testing-only",
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

            for key, value in test_env_vars.items():
                os.environ[key] = value
                logger.debug(f"Set {key}={value}")

            logger.info("Test environment variables configured")
            return True

        except Exception as e:
            logger.error(f"Failed to setup test environment: {e}")
            return False

    def validate_environment(self) -> bool:
        """Validate test environment is properly configured."""
        try:
            # Check required dependencies
            required_packages = ["pytest", "asyncio", "sqlalchemy", "fastapi"]
            for package in required_packages:
                try:
                    __import__(package)
                    logger.debug(f"✓ {package} available")
                except ImportError:
                    logger.error(f"✗ {package} not available")
                    return False

            # Check pytest configuration
            pytest_ini = project_root / "pytest.ini"
            if not pytest_ini.exists():
                logger.error("pytest.ini not found")
                return False

            # Check test directory
            tests_dir = project_root / "tests"
            if not tests_dir.exists():
                logger.error("tests/ directory not found")
                return False

            logger.info("Environment validation passed")
            return True

        except Exception as e:
            logger.error(f"Environment validation failed: {e}")
            return False

    def cleanup(self):
        """Cleanup temporary test resources."""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.debug(f"Cleaned up {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {temp_file}: {e}")


class TestSuiteRunner:
    """Main test suite runner with intelligent test selection."""

    def __init__(self):
        self.env_manager = TestEnvironmentManager()
        self.start_time = None
        self.results = {}

    def run_tests(
        self,
        markers: Optional[List[str]] = None,
        paths: Optional[List[str]] = None,
        coverage: bool = True,
        parallel: bool = False,
        verbose: bool = True,
        fail_fast: bool = False,
    ) -> Dict[str, Any]:
        """
        Run test suite with specified options.

        Args:
            markers: Test markers to include/exclude
            paths: Specific test paths to run
            coverage: Enable coverage reporting
            parallel: Run tests in parallel
            verbose: Verbose output
            fail_fast: Stop on first failure

        Returns:
            Test execution results
        """
        self.start_time = time.time()

        try:
            # Setup environment
            if not self.env_manager.setup_environment():
                raise RuntimeError("Failed to setup test environment")

            if not self.env_manager.validate_environment():
                raise RuntimeError("Test environment validation failed")

            # Build pytest command
            cmd = self._build_pytest_command(
                markers=markers,
                paths=paths,
                coverage=coverage,
                parallel=parallel,
                verbose=verbose,
                fail_fast=fail_fast,
            )

            logger.info(f"Running command: {' '.join(cmd)}")

            # Execute tests
            result = self._execute_tests(cmd)

            # Process results
            self.results = self._process_results(result)

            return self.results

        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return {"error": str(e), "success": False}

        finally:
            self.env_manager.cleanup()

    def _build_pytest_command(self, **kwargs) -> List[str]:
        """Build pytest command with options."""
        cmd = ["python", "-m", "pytest"]

        # Base options from pytest.ini are automatically included

        # Markers
        if kwargs.get("markers"):
            marker_expr = " and ".join(kwargs["markers"])
            cmd.extend(["-m", marker_expr])

        # Paths
        if kwargs.get("paths"):
            cmd.extend(kwargs["paths"])
        else:
            cmd.append("tests/")

        # Coverage
        if kwargs.get("coverage", True):
            cmd.extend(
                ["--cov=fxml4", "--cov-report=term-missing", "--cov-report=html"]
            )

        # Parallel execution
        if kwargs.get("parallel"):
            cmd.extend(["-n", "auto"])

        # Verbose output
        if kwargs.get("verbose", True):
            cmd.append("-v")

        # Fail fast
        if kwargs.get("fail_fast"):
            cmd.append("-x")

        # Output options
        cmd.extend(
            ["--tb=short", "--durations=10", "--strict-markers", "--strict-config"]
        )

        return cmd

    def _execute_tests(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Execute pytest command."""
        logger.info("Starting test execution...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout
                cwd=project_root,
            )

            logger.info(
                f"Test execution completed with return code: {result.returncode}"
            )
            return result

        except subprocess.TimeoutExpired:
            logger.error("Test execution timed out")
            raise
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            raise

    def _process_results(self, result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Process test execution results."""
        execution_time = time.time() - self.start_time

        # Parse pytest output for summary
        output_lines = result.stdout.split("\n")

        summary = {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "execution_time": round(execution_time, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

        # Extract test counts from pytest output
        for line in output_lines:
            if "passed" in line and "failed" in line:
                summary["test_summary"] = line.strip()
                break

        # Log summary
        logger.info(f"Test execution summary:")
        logger.info(f"  Success: {summary['success']}")
        logger.info(f"  Execution time: {summary['execution_time']}s")
        if "test_summary" in summary:
            logger.info(f"  Results: {summary['test_summary']}")

        return summary


def create_test_presets() -> Dict[str, Dict[str, Any]]:
    """Create predefined test execution presets."""
    return {
        "fast": {
            "markers": ["not slow", "not requires_ib", "not requires_db"],
            "description": "Fast unit tests only",
        },
        "unit": {"markers": ["unit"], "description": "Unit tests only"},
        "integration": {
            "markers": ["integration"],
            "description": "Integration tests only",
        },
        "security": {"markers": ["security"], "description": "Security tests only"},
        "performance": {
            "markers": ["performance"],
            "description": "Performance tests only",
        },
        "api": {"markers": ["api"], "description": "API tests only"},
        "ml": {"markers": ["ml"], "description": "Machine learning tests only"},
        "comprehensive": {
            "markers": ["not requires_ib"],  # Exclude IB tests
            "coverage": True,
            "description": "Comprehensive test suite (excluding IB)",
        },
        "smoke": {
            "markers": ["fast"],
            "fail_fast": True,
            "description": "Smoke tests for quick validation",
        },
    }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="FXML4 Test Suite Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_test_suite.py --preset fast           # Run fast tests only
  python run_test_suite.py --preset integration    # Run integration tests
  python run_test_suite.py --markers "unit and not slow"  # Custom markers
  python run_test_suite.py --path tests/unit/      # Specific path
  python run_test_suite.py --coverage --parallel   # Full run with coverage and parallel execution
        """,
    )

    presets = create_test_presets()

    # Preset options
    parser.add_argument(
        "--preset", choices=presets.keys(), help="Use predefined test preset"
    )

    # Custom options
    parser.add_argument(
        "--markers",
        nargs="+",
        help='Test markers to include (e.g., "unit and not slow")',
    )
    parser.add_argument(
        "--path", dest="paths", action="append", help="Specific test paths to run"
    )
    parser.add_argument(
        "--no-coverage", action="store_true", help="Disable coverage reporting"
    )
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument(
        "--fail-fast", action="store_true", help="Stop on first failure"
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")

    # Info options
    parser.add_argument(
        "--list-presets", action="store_true", help="List available test presets"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running",
    )

    args = parser.parse_args()

    # List presets
    if args.list_presets:
        print("Available test presets:")
        for name, config in presets.items():
            print(f"  {name:12} - {config.get('description', 'No description')}")
        return 0

    # Prepare test configuration
    config = {}

    if args.preset:
        config.update(presets[args.preset])
        logger.info(f"Using preset: {args.preset}")

    # Override with CLI arguments
    if args.markers:
        config["markers"] = args.markers
    if args.paths:
        config["paths"] = args.paths
    if args.no_coverage:
        config["coverage"] = False
    if args.parallel:
        config["parallel"] = True
    if args.fail_fast:
        config["fail_fast"] = True
    if args.quiet:
        config["verbose"] = False

    # Dry run
    if args.dry_run:
        runner = TestSuiteRunner()
        cmd = runner._build_pytest_command(**config)
        print(f"Would execute: {' '.join(cmd)}")
        return 0

    # Execute tests
    runner = TestSuiteRunner()
    results = runner.run_tests(**config)

    # Save results
    results_file = project_root / "test_execution_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Results saved to: {results_file}")

    # Return appropriate exit code
    return 0 if results.get("success", False) else 1


if __name__ == "__main__":
    sys.exit(main())
