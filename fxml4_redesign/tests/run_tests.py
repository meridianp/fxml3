#!/usr/bin/env python3
"""Test runner for FXML4 microservices tests."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class TestRunner:
    """Run tests with various configurations."""

    def __init__(self, test_dir: Path):
        self.test_dir = test_dir
        self.results = {
            "start_time": datetime.utcnow().isoformat(),
            "tests": {},
            "summary": {},
        }

    def run_unit_tests(self, service: str = None, verbose: bool = False):
        """Run unit tests."""
        print("\n" + "=" * 60)
        print("Running Unit Tests")
        print("=" * 60)

        cmd = ["pytest", "unit/"]

        if service:
            cmd.append(f"unit/test_{service}.py")

        if verbose:
            cmd.append("-vv")
        else:
            cmd.append("-v")

        # Add coverage
        cmd.extend(
            ["--cov=../services", "--cov=../shared", "--cov-report=term-missing"]
        )

        # Add markers
        cmd.extend(["-m", "not integration"])

        result = self._run_command(cmd)
        self.results["tests"]["unit"] = result
        return result["success"]

    def run_integration_tests(self, verbose: bool = False):
        """Run integration tests."""
        print("\n" + "=" * 60)
        print("Running Integration Tests")
        print("=" * 60)

        cmd = ["pytest", "integration/", "-v"]

        if verbose:
            cmd.append("-v")

        # Integration tests are slower
        cmd.extend(["--timeout=300"])

        # Mark as integration
        cmd.extend(["-m", "integration"])

        result = self._run_command(cmd)
        self.results["tests"]["integration"] = result
        return result["success"]

    def run_performance_tests(self):
        """Run performance benchmark tests."""
        print("\n" + "=" * 60)
        print("Running Performance Tests")
        print("=" * 60)

        cmd = [
            "pytest",
            "-v",
            "-m",
            "benchmark",
            "--benchmark-enable",
            "--benchmark-only",
            "--benchmark-autosave",
        ]

        result = self._run_command(cmd)
        self.results["tests"]["performance"] = result
        return result["success"]

    def run_specific_test(self, test_path: str, verbose: bool = False):
        """Run a specific test file or test case."""
        print(f"\nRunning specific test: {test_path}")

        cmd = ["pytest", test_path]

        if verbose:
            cmd.extend(["-vv", "-s"])

        result = self._run_command(cmd)
        self.results["tests"]["specific"] = result
        return result["success"]

    def run_with_markers(self, markers: list, verbose: bool = False):
        """Run tests with specific markers."""
        print(f"\nRunning tests with markers: {', '.join(markers)}")

        cmd = ["pytest", "-v"]

        if verbose:
            cmd.append("-v")

        # Add marker expression
        marker_expr = " and ".join(markers)
        cmd.extend(["-m", marker_expr])

        result = self._run_command(cmd)
        self.results["tests"]["markers"] = result
        return result["success"]

    def run_coverage_report(self):
        """Generate detailed coverage report."""
        print("\n" + "=" * 60)
        print("Generating Coverage Report")
        print("=" * 60)

        cmd = [
            "pytest",
            "--cov=../services",
            "--cov=../shared",
            "--cov-report=html:htmlcov",
            "--cov-report=xml",
            "--cov-report=term-missing:skip-covered",
            "--quiet",
        ]

        result = self._run_command(cmd)

        if result["success"]:
            print(
                f"\nHTML coverage report generated in: {self.test_dir}/htmlcov/index.html"
            )

        return result["success"]

    def run_all_tests(self, skip_slow: bool = False):
        """Run all test suites."""
        print("\n" + "=" * 60)
        print("Running All Tests")
        print("=" * 60)

        success = True

        # Unit tests
        if not self.run_unit_tests():
            success = False

        # Integration tests (unless skipping slow)
        if not skip_slow:
            if not self.run_integration_tests():
                success = False

        # Coverage report
        self.run_coverage_report()

        # Summary
        self._print_summary()

        return success

    def _run_command(self, cmd: list) -> dict:
        """Run a command and capture output."""
        start_time = datetime.utcnow()

        # Change to test directory
        original_dir = os.getcwd()
        os.chdir(self.test_dir)

        try:
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True)

            duration = (datetime.utcnow() - start_time).total_seconds()

            return {
                "command": " ".join(cmd),
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        finally:
            os.chdir(original_dir)

    def _print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)

        total_duration = 0
        passed = 0
        failed = 0

        for suite, result in self.results["tests"].items():
            status = "PASSED" if result["success"] else "FAILED"
            print(f"{suite.upper()}: {status} (took {result['duration']:.2f}s)")

            total_duration += result["duration"]
            if result["success"]:
                passed += 1
            else:
                failed += 1

        print(f"\nTotal: {passed} passed, {failed} failed")
        print(f"Total duration: {total_duration:.2f}s")

        self.results["summary"] = {
            "total_duration": total_duration,
            "passed": passed,
            "failed": failed,
            "end_time": datetime.utcnow().isoformat(),
        }

    def save_results(self, output_file: str = "test_results.json"):
        """Save test results to file."""
        output_path = self.test_dir / output_file

        with open(output_path, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\nTest results saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run FXML4 tests")

    parser.add_argument(
        "command",
        choices=["all", "unit", "integration", "performance", "coverage", "specific"],
        help="Which tests to run",
    )

    parser.add_argument("--service", help="Specific service to test (for unit tests)")

    parser.add_argument("--test", help="Specific test file or test case to run")

    parser.add_argument("--markers", nargs="+", help="Run tests with specific markers")

    parser.add_argument(
        "--skip-slow",
        action="store_true",
        help="Skip slow tests (integration, performance)",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    parser.add_argument(
        "--save-results", action="store_true", help="Save test results to JSON file"
    )

    args = parser.parse_args()

    # Get test directory
    test_dir = Path(__file__).parent

    # Create runner
    runner = TestRunner(test_dir)

    # Run requested tests
    success = True

    if args.command == "all":
        success = runner.run_all_tests(skip_slow=args.skip_slow)

    elif args.command == "unit":
        success = runner.run_unit_tests(service=args.service, verbose=args.verbose)

    elif args.command == "integration":
        success = runner.run_integration_tests(verbose=args.verbose)

    elif args.command == "performance":
        success = runner.run_performance_tests()

    elif args.command == "coverage":
        success = runner.run_coverage_report()

    elif args.command == "specific":
        if not args.test:
            print("Error: --test argument required for specific command")
            sys.exit(1)
        success = runner.run_specific_test(args.test, verbose=args.verbose)

    # Run with markers if specified
    if args.markers:
        success = runner.run_with_markers(args.markers, verbose=args.verbose)

    # Save results if requested
    if args.save_results:
        runner.save_results()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
