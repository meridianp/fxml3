#!/usr/bin/env python3
"""
FXML4 Unified Test Runner

Provides a unified interface for running different test categories
with environment-specific configurations and reporting.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# Color codes for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_colored(message: str, color: str = Colors.WHITE):
    """Print colored message to terminal."""
    print(f"{color}{message}{Colors.RESET}")


def print_header(title: str):
    """Print formatted header."""
    print_colored("=" * 80, Colors.CYAN)
    print_colored(f" {title}", Colors.CYAN + Colors.BOLD)
    print_colored("=" * 80, Colors.CYAN)


def run_command(cmd: List[str], description: str) -> bool:
    """Run a command and return success status."""
    print_colored(f"\n🚀 {description}", Colors.BLUE)
    print_colored(f"Command: {' '.join(cmd)}", Colors.WHITE)

    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print_colored(f"✅ {description} - PASSED", Colors.GREEN)
        return True
    except subprocess.CalledProcessError as e:
        print_colored(
            f"❌ {description} - FAILED (exit code: {e.returncode})", Colors.RED
        )
        return False
    except FileNotFoundError:
        print_colored(f"❌ {description} - COMMAND NOT FOUND", Colors.RED)
        return False


class TestRunner:
    """Unified test runner for FXML4."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.core_path = project_root / "core"
        self.tests_path = project_root / "tests"
        self.core_tests_path = project_root / "core" / "tests"

    def _get_base_pytest_cmd(self) -> List[str]:
        """Get base pytest command with common options."""
        return [
            "python",
            "-m",
            "pytest",
            "--verbose",
            "--tb=short",
            "--durations=10",
            "--strict-markers",
        ]

    def run_unit_tests(self, fast_only: bool = False, coverage: bool = True) -> bool:
        """Run unit tests."""
        cmd = self._get_base_pytest_cmd()

        # Add test paths
        if self.core_tests_path.exists():
            cmd.extend([str(self.core_tests_path / "unit")])
        if self.tests_path.exists():
            cmd.extend([str(self.tests_path / "unit")])

        # Add markers
        if fast_only:
            cmd.extend(["-m", "fast and not slow"])
        else:
            cmd.extend(["-m", "unit"])

        # Add coverage
        if coverage:
            cmd.extend(
                [
                    "--cov=core",
                    "--cov-report=term-missing",
                    "--cov-report=html:htmlcov",
                    "--cov-fail-under=80",
                ]
            )

        return run_command(cmd, "Unit Tests")

    def run_integration_tests(self, coverage: bool = False) -> bool:
        """Run integration tests."""
        cmd = self._get_base_pytest_cmd()

        # Add test paths
        if self.core_tests_path.exists():
            cmd.extend([str(self.core_tests_path / "integration")])
        if self.tests_path.exists():
            cmd.extend([str(self.tests_path / "integration")])

        cmd.extend(["-m", "integration"])

        if coverage:
            cmd.extend(["--cov=core", "--cov-append"])

        return run_command(cmd, "Integration Tests")

    def run_e2e_tests(self) -> bool:
        """Run end-to-end tests."""
        cmd = self._get_base_pytest_cmd()

        # Add test paths
        cmd.extend(["-m", "e2e or functional"])

        return run_command(cmd, "End-to-End Tests")

    def run_performance_tests(self) -> bool:
        """Run performance tests."""
        cmd = self._get_base_pytest_cmd()

        # Add test paths
        if self.core_tests_path.exists():
            cmd.extend([str(self.core_tests_path / "performance")])

        cmd.extend(["-m", "performance"])

        return run_command(cmd, "Performance Tests")

    def run_security_tests(self) -> bool:
        """Run security tests."""
        cmd = self._get_base_pytest_cmd()

        cmd.extend(["-m", "security or auth"])

        return run_command(cmd, "Security Tests")

    def run_compliance_tests(self) -> bool:
        """Run compliance tests."""
        cmd = self._get_base_pytest_cmd()

        # Add test paths
        if self.core_tests_path.exists():
            cmd.extend([str(self.core_tests_path / "compliance")])

        cmd.extend(["-m", "compliance"])

        return run_command(cmd, "Compliance Tests")

    def run_critical_tests(self) -> bool:
        """Run critical deployment tests."""
        cmd = self._get_base_pytest_cmd()

        cmd.extend(["-m", "critical or mandatory"])
        cmd.extend(["--maxfail=1"])  # Fail fast for critical tests

        return run_command(cmd, "Critical Tests")

    def run_fast_tests(self) -> bool:
        """Run fast tests only (for development)."""
        return self.run_unit_tests(fast_only=True, coverage=False)

    def run_all_tests(self, stop_on_failure: bool = False) -> bool:
        """Run all test categories."""
        print_header("FXML4 Complete Test Suite")

        test_results = {}

        # Run test categories in order
        test_categories = [
            ("Critical Tests", self.run_critical_tests),
            ("Unit Tests", lambda: self.run_unit_tests(coverage=True)),
            ("Integration Tests", lambda: self.run_integration_tests(coverage=True)),
            ("Security Tests", self.run_security_tests),
            ("Compliance Tests", self.run_compliance_tests),
            ("Performance Tests", self.run_performance_tests),
        ]

        for category_name, test_func in test_categories:
            result = test_func()
            test_results[category_name] = result

            if not result and stop_on_failure:
                print_colored(
                    f"\n🛑 Stopping test execution due to failure in {category_name}",
                    Colors.RED,
                )
                break

        # Print summary
        self._print_test_summary(test_results)

        return all(test_results.values())

    def run_tdd_workflow(self, test_file: Optional[str] = None) -> bool:
        """Run TDD workflow tests."""
        cmd = self._get_base_pytest_cmd()

        if test_file:
            if not Path(test_file).exists():
                print_colored(f"❌ Test file not found: {test_file}", Colors.RED)
                return False
            cmd.append(test_file)

        cmd.extend(["-m", "tdd"])
        cmd.extend(["-x"])  # Stop on first failure for TDD

        return run_command(cmd, f"TDD Workflow{f' - {test_file}' if test_file else ''}")

    def _print_test_summary(self, results: Dict[str, bool]):
        """Print test execution summary."""
        print_header("Test Execution Summary")

        passed = sum(1 for result in results.values() if result)
        total = len(results)

        for category, result in results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            color = Colors.GREEN if result else Colors.RED
            print_colored(f"  {category:20} {status}", color)

        print_colored(
            f"\n📊 Overall: {passed}/{total} test categories passed", Colors.CYAN
        )

        if passed == total:
            print_colored(
                "🎉 All tests passed! Ready for deployment.", Colors.GREEN + Colors.BOLD
            )
        else:
            print_colored(
                "⚠️  Some tests failed. Please review and fix before deployment.",
                Colors.YELLOW + Colors.BOLD,
            )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="FXML4 Unified Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_runner.py unit                    # Run unit tests only
  python test_runner.py integration             # Run integration tests
  python test_runner.py all                     # Run all test categories
  python test_runner.py critical                # Run critical tests only
  python test_runner.py fast                    # Run fast tests for development
  python test_runner.py tdd tests/test_new.py   # Run specific TDD test
  python test_runner.py all --stop-on-failure   # Stop on first category failure
        """,
    )

    parser.add_argument(
        "category",
        choices=[
            "unit",
            "integration",
            "e2e",
            "performance",
            "security",
            "compliance",
            "critical",
            "fast",
            "all",
            "tdd",
        ],
        help="Test category to run",
    )

    parser.add_argument(
        "test_file", nargs="?", help="Specific test file (for TDD workflow)"
    )

    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop execution on first test category failure",
    )

    parser.add_argument(
        "--no-coverage", action="store_true", help="Skip coverage reporting"
    )

    args = parser.parse_args()

    # Find project root
    current_dir = Path.cwd()
    project_root = current_dir

    # Look for project indicators
    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "pytest.ini").exists() or (parent / "core").is_dir():
            project_root = parent
            break

    print_colored(f"🏠 Project root: {project_root}", Colors.CYAN)

    runner = TestRunner(project_root)

    # Run the specified test category
    success = False

    if args.category == "unit":
        success = runner.run_unit_tests(coverage=not args.no_coverage)
    elif args.category == "integration":
        success = runner.run_integration_tests(coverage=not args.no_coverage)
    elif args.category == "e2e":
        success = runner.run_e2e_tests()
    elif args.category == "performance":
        success = runner.run_performance_tests()
    elif args.category == "security":
        success = runner.run_security_tests()
    elif args.category == "compliance":
        success = runner.run_compliance_tests()
    elif args.category == "critical":
        success = runner.run_critical_tests()
    elif args.category == "fast":
        success = runner.run_fast_tests()
    elif args.category == "all":
        success = runner.run_all_tests(stop_on_failure=args.stop_on_failure)
    elif args.category == "tdd":
        success = runner.run_tdd_workflow(args.test_file)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
