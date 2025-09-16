#!/usr/bin/env python3
"""
Integrated Test Pipeline Runner for FXML4
=========================================

Comprehensive test orchestration that runs all test types in the correct order,
with support for both local and containerized execution.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# ANSI color codes for output
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
MAGENTA = "\033[0;35m"
CYAN = "\033[0;36m"
NC = "\033[0m"  # No Color


@dataclass
class TestResult:
    """Test execution result."""

    name: str
    status: str  # 'passed', 'failed', 'skipped'
    duration: float
    output: str
    coverage: Optional[float] = None


class IntegratedTestPipeline:
    """Orchestrates the complete test pipeline."""

    def __init__(self, verbose: bool = False, parallel: bool = False):
        self.verbose = verbose
        self.parallel = parallel
        self.results: List[TestResult] = []
        self.start_time = None
        self.test_results_dir = Path("test-results")
        self.test_results_dir.mkdir(exist_ok=True)

    def print_header(self, title: str, color: str = BLUE):
        """Print a formatted header."""
        print(f"\n{color}{'=' * 60}")
        print(f"{title:^60}")
        print(f"{'=' * 60}{NC}\n")

    def print_status(self, message: str, status: str = "INFO"):
        """Print a status message."""
        colors = {
            "INFO": CYAN,
            "SUCCESS": GREEN,
            "WARNING": YELLOW,
            "ERROR": RED,
            "RUNNING": MAGENTA,
        }
        color = colors.get(status, NC)
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {color}[{status}]{NC} {message}")

    def run_command(self, command: str, description: str) -> Tuple[int, str]:
        """Run a shell command and capture output."""
        self.print_status(f"Running: {description}", "RUNNING")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if self.verbose:
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)

            return result.returncode, result.stdout + result.stderr

        except subprocess.TimeoutExpired:
            self.print_status(f"Command timed out: {description}", "ERROR")
            return 1, "Command timed out"
        except Exception as e:
            self.print_status(f"Command failed: {e}", "ERROR")
            return 1, str(e)

    def run_unit_tests(self) -> TestResult:
        """Run unit tests."""
        start = time.time()

        command = (
            "pytest tests/ "
            "-m 'unit and not slow and not requires_ib and not requires_fxcm' "
            "-v --tb=short "
            f"--junit-xml={self.test_results_dir}/unit-results.xml "
            "--cov=fxml4 --cov-report=xml:test-results/unit-coverage.xml"
        )

        returncode, output = self.run_command(command, "Unit Tests")

        # Extract coverage if available
        coverage = None
        if "TOTAL" in output:
            for line in output.split("\n"):
                if "TOTAL" in line and "%" in line:
                    parts = line.split()
                    for part in parts:
                        if part.endswith("%"):
                            try:
                                coverage = float(part[:-1])
                                break
                            except ValueError:
                                pass

        result = TestResult(
            name="Unit Tests",
            status="passed" if returncode == 0 else "failed",
            duration=time.time() - start,
            output=output,
            coverage=coverage,
        )

        self.results.append(result)
        return result

    def run_integration_tests(self) -> TestResult:
        """Run integration tests."""
        start = time.time()

        command = (
            "pytest tests/ "
            "-m 'integration and not requires_ib and not requires_fxcm' "
            "-v --tb=short "
            f"--junit-xml={self.test_results_dir}/integration-results.xml"
        )

        returncode, output = self.run_command(command, "Integration Tests")

        result = TestResult(
            name="Integration Tests",
            status="passed" if returncode == 0 else "failed",
            duration=time.time() - start,
            output=output,
        )

        self.results.append(result)
        return result

    def run_security_tests(self) -> TestResult:
        """Run security tests including authentication."""
        start = time.time()

        # Run security-specific tests
        command = (
            "pytest tests/ "
            "-m 'security or auth' "
            "-v --tb=short "
            f"--junit-xml={self.test_results_dir}/security-results.xml"
        )

        returncode, output = self.run_command(command, "Security Tests")

        # Also run security validation script
        validation_cmd = "python scripts/validate_security.py"
        val_returncode, val_output = self.run_command(
            validation_cmd, "Security Validation"
        )

        combined_status = (
            "passed" if (returncode == 0 and val_returncode == 0) else "failed"
        )
        combined_output = output + "\n" + val_output

        result = TestResult(
            name="Security Tests",
            status=combined_status,
            duration=time.time() - start,
            output=combined_output,
        )

        self.results.append(result)
        return result

    def run_e2e_tests(self) -> TestResult:
        """Run containerized E2E tests."""
        start = time.time()

        # Check if Docker is available
        docker_check = subprocess.run(
            "docker --version", shell=True, capture_output=True
        )

        if docker_check.returncode != 0:
            self.print_status("Docker not available, skipping E2E tests", "WARNING")
            result = TestResult(
                name="E2E Tests",
                status="skipped",
                duration=0,
                output="Docker not available",
            )
            self.results.append(result)
            return result

        # Run containerized E2E tests
        command = "./scripts/run_e2e_auth_tests.sh run"
        returncode, output = self.run_command(command, "E2E Authentication Tests")

        result = TestResult(
            name="E2E Tests",
            status="passed" if returncode == 0 else "failed",
            duration=time.time() - start,
            output=output,
        )

        self.results.append(result)
        return result

    def run_performance_tests(self) -> TestResult:
        """Run performance tests."""
        start = time.time()

        command = (
            "pytest tests/ "
            "-m 'performance or slow' "
            "-v --tb=short --durations=10 "
            f"--junit-xml={self.test_results_dir}/performance-results.xml"
        )

        returncode, output = self.run_command(command, "Performance Tests")

        result = TestResult(
            name="Performance Tests",
            status="passed" if returncode == 0 else "failed",
            duration=time.time() - start,
            output=output,
        )

        self.results.append(result)
        return result

    def run_linters(self) -> TestResult:
        """Run code quality checks."""
        start = time.time()

        linters = [
            ("black --check .", "Black formatting"),
            ("isort --check-only .", "Import sorting"),
            ("flake8 .", "Flake8 linting"),
            ("mypy fxml4 --ignore-missing-imports", "Type checking"),
        ]

        all_passed = True
        all_output = []

        for command, description in linters:
            returncode, output = self.run_command(command, description)
            if returncode != 0:
                all_passed = False
            all_output.append(f"{description}:\n{output}\n")

        result = TestResult(
            name="Code Quality",
            status="passed" if all_passed else "failed",
            duration=time.time() - start,
            output="\n".join(all_output),
        )

        self.results.append(result)
        return result

    def generate_report(self):
        """Generate a comprehensive test report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_duration": (time.time() - self.start_time if self.start_time else 0),
            "test_results": [],
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.status == "passed"),
                "failed": sum(1 for r in self.results if r.status == "failed"),
                "skipped": sum(1 for r in self.results if r.status == "skipped"),
            },
        }

        for result in self.results:
            report["test_results"].append(
                {
                    "name": result.name,
                    "status": result.status,
                    "duration": result.duration,
                    "coverage": result.coverage,
                }
            )

        # Save JSON report
        report_path = self.test_results_dir / "pipeline-report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        # Generate text summary
        self.print_header("TEST PIPELINE SUMMARY")

        print(f"Total Duration: {report['total_duration']:.2f} seconds")
        print(f"Tests Run: {report['summary']['total']}")
        print(f"{GREEN}Passed: {report['summary']['passed']}{NC}")
        print(f"{RED}Failed: {report['summary']['failed']}{NC}")
        print(f"{YELLOW}Skipped: {report['summary']['skipped']}{NC}")

        print("\nDetailed Results:")
        print("-" * 50)

        for result in self.results:
            status_color = (
                GREEN
                if result.status == "passed"
                else RED if result.status == "failed" else YELLOW
            )
            status_icon = (
                "✓"
                if result.status == "passed"
                else "✗" if result.status == "failed" else "○"
            )

            print(
                f"{status_color}{status_icon} {result.name:<30} "
                f"[{result.duration:.2f}s]{NC}"
            )
            if result.coverage:
                print(f"  Coverage: {result.coverage:.1f}%")

        print("-" * 50)

        # Overall status
        if report["summary"]["failed"] == 0:
            self.print_status("All tests passed!", "SUCCESS")
            return 0
        else:
            self.print_status(f"{report['summary']['failed']} tests failed", "ERROR")
            return 1

    async def run_parallel_tests(self):
        """Run tests in parallel where possible."""
        self.print_header("PARALLEL TEST EXECUTION", MAGENTA)

        # Tests that can run in parallel
        parallel_tasks = [
            self.run_unit_tests,
            self.run_security_tests,
            self.run_linters,
        ]

        # Run parallel tests
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, task) for task in parallel_tasks]
        await asyncio.gather(*tasks)

        # Sequential tests (depend on environment)
        self.run_integration_tests()
        self.run_e2e_tests()
        self.run_performance_tests()

    def run_pipeline(self, test_types: List[str] = None):
        """Run the complete test pipeline."""
        self.start_time = time.time()

        self.print_header("FXML4 INTEGRATED TEST PIPELINE", BLUE)
        self.print_status(
            f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO"
        )

        if not test_types:
            test_types = [
                "lint",
                "unit",
                "integration",
                "security",
                "e2e",
                "performance",
            ]

        test_map = {
            "lint": self.run_linters,
            "unit": self.run_unit_tests,
            "integration": self.run_integration_tests,
            "security": self.run_security_tests,
            "e2e": self.run_e2e_tests,
            "performance": self.run_performance_tests,
        }

        if self.parallel and "parallel" in test_types:
            # Run parallel execution
            asyncio.run(self.run_parallel_tests())
        else:
            # Sequential execution
            for test_type in test_types:
                if test_type in test_map:
                    result = test_map[test_type]()
                    if result.status == "failed" and not self.verbose:
                        self.print_status(
                            f"{result.name} failed. Use --verbose for " "details.",
                            "ERROR",
                        )

        return self.generate_report()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="FXML4 Integrated Test Pipeline Runner"
    )

    parser.add_argument(
        "tests",
        nargs="*",
        choices=[
            "lint",
            "unit",
            "integration",
            "security",
            "e2e",
            "performance",
            "all",
        ],
        default=["all"],
        help="Test types to run (default: all)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )

    parser.add_argument(
        "--parallel",
        "-p",
        action="store_true",
        help="Run tests in parallel where possible",
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: unit and integration tests only",
    )

    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: all tests with strict error checking",
    )

    args = parser.parse_args()

    # Determine which tests to run
    if "all" in args.tests or args.ci:
        test_types = ["lint", "unit", "integration", "security", "e2e", "performance"]
    elif args.quick:
        test_types = ["lint", "unit", "integration"]
    else:
        test_types = args.tests

    # Create and run pipeline
    pipeline = IntegratedTestPipeline(verbose=args.verbose, parallel=args.parallel)

    exit_code = pipeline.run_pipeline(test_types)

    if args.ci and exit_code != 0:
        print(f"\n{RED}CI Pipeline Failed!{NC}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
