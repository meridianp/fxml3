#!/usr/bin/env python3
"""
FXML4 Comprehensive Test Suite - 23 Category Testing Framework

This script provides complete test orchestration across all 23 test categories
defined in the FXML4 testing methodology, ensuring comprehensive validation
of the entire trading system.

Categories Covered (23 Total):
1. unit - Unit tests (fast, isolated)
2. integration - Integration tests (slower, require services)
3. slow - Slow tests (may take several seconds)
4. fast - Fast tests (complete in milliseconds)
5. requires_ib - Tests requiring Interactive Brokers connection
6. requires_db - Tests requiring database connection
7. requires_api - Tests requiring API server
8. requires_network - Tests requiring network access
9. security - Security-related tests
10. performance - Performance and benchmarking tests
11. auth - Authentication and authorization tests
12. database - Database-related tests
13. ml - Machine learning tests
14. wave - Elliott Wave analysis tests
15. backtesting - Backtesting framework tests
16. api - API endpoint tests
17. stress - Stress tests (high resource usage)
18. compliance - Compliance and regulatory tests
19. fix_protocol - FIX protocol specific tests
20. concurrency - Concurrency and thread safety tests
21. functional - End-to-end functional tests
22. infrastructure - Infrastructure and deployment tests
23. ui - User interface and frontend tests

Usage:
    python scripts/comprehensive_test_suite.py --category all
    python scripts/comprehensive_test_suite.py --category security
    python scripts/comprehensive_test_suite.py --validate-coverage
    python scripts/comprehensive_test_suite.py --generate-report
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TestCategoryResult:
    """Results for a single test category."""

    category: str
    description: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    execution_time: float = 0.0
    success: bool = False
    coverage: float = 0.0
    details: str = ""


@dataclass
class ComprehensiveTestResults:
    """Complete test suite results."""

    total_categories: int = 23
    executed_categories: int = 0
    successful_categories: int = 0
    total_tests: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_errors: int = 0
    overall_coverage: float = 0.0
    execution_time: float = 0.0
    success_rate: float = 0.0
    timestamp: str = ""
    category_results: List[TestCategoryResult] = None

    def __post_init__(self):
        if self.category_results is None:
            self.category_results = []


class ComprehensiveTestSuite:
    """Main comprehensive test suite orchestrator."""

    def __init__(self):
        self.test_categories = self._define_test_categories()
        self.results = ComprehensiveTestResults()
        self.start_time = None

    def _define_test_categories(self) -> Dict[str, Dict[str, Any]]:
        """Define all 23 test categories with their configurations."""
        return {
            # Core Test Categories
            "unit": {
                "description": "Unit tests (fast, isolated)",
                "markers": ["unit"],
                "priority": 1,
                "max_time": 300,  # 5 minutes
                "coverage_target": 85,
            },
            "integration": {
                "description": "Integration tests (slower, require services)",
                "markers": ["integration"],
                "priority": 2,
                "max_time": 900,  # 15 minutes
                "coverage_target": 70,
            },
            "fast": {
                "description": "Fast tests (complete in milliseconds)",
                "markers": ["fast"],
                "priority": 1,
                "max_time": 60,  # 1 minute
                "coverage_target": 90,
            },
            "slow": {
                "description": "Slow tests (may take several seconds)",
                "markers": ["slow"],
                "priority": 3,
                "max_time": 1800,  # 30 minutes
                "coverage_target": 60,
            },
            # Infrastructure Categories
            "requires_ib": {
                "description": "Tests requiring Interactive Brokers connection",
                "markers": ["requires_ib"],
                "priority": 4,
                "max_time": 600,
                "coverage_target": 50,
                "optional": True,
            },
            "requires_db": {
                "description": "Tests requiring database connection",
                "markers": ["requires_db"],
                "priority": 2,
                "max_time": 600,
                "coverage_target": 70,
            },
            "requires_api": {
                "description": "Tests requiring API server",
                "markers": ["requires_api"],
                "priority": 2,
                "max_time": 600,
                "coverage_target": 75,
            },
            "requires_network": {
                "description": "Tests requiring network access",
                "markers": ["requires_network"],
                "priority": 3,
                "max_time": 900,
                "coverage_target": 60,
                "optional": True,
            },
            # Security & Compliance Categories
            "security": {
                "description": "Security-related tests",
                "markers": ["security"],
                "priority": 1,
                "max_time": 600,
                "coverage_target": 95,
            },
            "auth": {
                "description": "Authentication and authorization tests",
                "markers": ["auth"],
                "priority": 1,
                "max_time": 300,
                "coverage_target": 90,
            },
            "compliance": {
                "description": "Compliance and regulatory tests",
                "markers": ["compliance"],
                "priority": 1,
                "max_time": 600,
                "coverage_target": 85,
            },
            # Performance Categories
            "performance": {
                "description": "Performance and benchmarking tests",
                "markers": ["performance"],
                "priority": 2,
                "max_time": 1200,  # 20 minutes
                "coverage_target": 70,
            },
            "stress": {
                "description": "Stress tests (high resource usage)",
                "markers": ["stress"],
                "priority": 3,
                "max_time": 1800,
                "coverage_target": 60,
            },
            "concurrency": {
                "description": "Concurrency and thread safety tests",
                "markers": ["concurrency"],
                "priority": 2,
                "max_time": 900,
                "coverage_target": 75,
            },
            # Functional Categories
            "api": {
                "description": "API endpoint tests",
                "markers": ["api"],
                "priority": 1,
                "max_time": 600,
                "coverage_target": 80,
            },
            "database": {
                "description": "Database-related tests",
                "markers": ["database"],
                "priority": 2,
                "max_time": 600,
                "coverage_target": 75,
            },
            "functional": {
                "description": "End-to-end functional tests",
                "markers": ["functional"],
                "priority": 2,
                "max_time": 1200,
                "coverage_target": 70,
            },
            "ui": {
                "description": "User interface and frontend tests",
                "markers": ["ui"],
                "priority": 2,
                "max_time": 900,
                "coverage_target": 65,
            },
            # Domain-Specific Categories
            "ml": {
                "description": "Machine learning tests",
                "markers": ["ml"],
                "priority": 2,
                "max_time": 1200,
                "coverage_target": 70,
            },
            "wave": {
                "description": "Elliott Wave analysis tests",
                "markers": ["wave"],
                "priority": 2,
                "max_time": 600,
                "coverage_target": 70,
            },
            "backtesting": {
                "description": "Backtesting framework tests",
                "markers": ["backtesting"],
                "priority": 2,
                "max_time": 900,
                "coverage_target": 75,
            },
            "fix_protocol": {
                "description": "FIX protocol specific tests",
                "markers": ["fix_protocol"],
                "priority": 2,
                "max_time": 600,
                "coverage_target": 80,
            },
            # Infrastructure & Deployment
            "infrastructure": {
                "description": "Infrastructure and deployment tests",
                "markers": ["infrastructure"],
                "priority": 3,
                "max_time": 900,
                "coverage_target": 60,
            },
        }

    def setup_test_environment(self) -> bool:
        """Setup comprehensive test environment."""
        try:
            env_vars = {
                "FXML4_JWT_SECRET_KEY": "comprehensive-test-secret-key",
                "FXML4_JWT_TOKEN_EXPIRE_MINUTES": "60",
                "FXML4_DATABASE_URL": "sqlite:///:memory:",
                "FXML4_DATABASE_PASSWORD": "test",
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
                "PYTEST_COMPREHENSIVE": "1",
            }

            for key, value in env_vars.items():
                os.environ[key] = value

            logger.info("✓ Comprehensive test environment configured")
            return True

        except Exception as e:
            logger.error(f"Failed to setup test environment: {e}")
            return False

    def validate_test_infrastructure(self) -> bool:
        """Validate that test infrastructure is ready."""
        try:
            # Check pytest configuration
            pytest_ini = project_root / "pytest.ini"
            if not pytest_ini.exists():
                logger.error("pytest.ini not found")
                return False

            # Check test directories exist
            required_dirs = ["tests", "tests/unit", "tests/integration", "tests/api"]
            for dir_name in required_dirs:
                test_dir = project_root / dir_name
                if not test_dir.exists():
                    logger.warning(f"Test directory {dir_name} not found")

            # Check Python executable
            python_exe = self._get_python_executable()
            if not python_exe:
                logger.error("Python executable not found")
                return False

            logger.info("✓ Test infrastructure validation passed")
            return True

        except Exception as e:
            logger.error(f"Test infrastructure validation failed: {e}")
            return False

    def _get_python_executable(self) -> Optional[str]:
        """Get the appropriate Python executable."""
        if os.environ.get("VIRTUAL_ENV"):
            return os.path.join(os.environ["VIRTUAL_ENV"], "bin", "python")
        elif (project_root / "venv" / "bin" / "python").exists():
            return str(project_root / "venv" / "bin" / "python")
        else:
            return "python"

    def run_category(self, category: str) -> TestCategoryResult:
        """Run tests for a specific category."""
        if category not in self.test_categories:
            raise ValueError(f"Unknown test category: {category}")

        config = self.test_categories[category]
        result = TestCategoryResult(
            category=category, description=config["description"]
        )

        logger.info(f"Running {category} tests: {config['description']}")
        start_time = time.time()

        try:
            # Build pytest command
            cmd = self._build_pytest_command(
                markers=config["markers"], max_time=config["max_time"], coverage=True
            )

            # Execute tests
            process_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config["max_time"],
                cwd=project_root,
            )

            result.execution_time = time.time() - start_time
            result.success = process_result.returncode == 0
            result.details = process_result.stdout

            # Parse test results from output
            self._parse_pytest_output(process_result.stdout, result)

            if result.success:
                logger.info(f"✓ {category} tests passed ({result.passed} passed)")
            else:
                logger.warning(
                    f"✗ {category} tests failed ({result.failed} failed, {result.passed} passed)"
                )

        except subprocess.TimeoutExpired:
            result.execution_time = time.time() - start_time
            result.success = False
            result.details = f"Tests timed out after {config['max_time']}s"
            logger.error(f"✗ {category} tests timed out")

        except Exception as e:
            result.execution_time = time.time() - start_time
            result.success = False
            result.details = str(e)
            logger.error(f"✗ {category} tests error: {e}")

        return result

    def _build_pytest_command(
        self, markers: List[str], max_time: int, coverage: bool = True
    ) -> List[str]:
        """Build pytest command for category execution."""
        python_exe = self._get_python_executable()
        cmd = [python_exe, "-m", "pytest"]

        # Add markers
        if markers:
            marker_expr = " and ".join(markers)
            cmd.extend(["-m", marker_expr])

        # Add paths
        cmd.append("tests/")

        # Add coverage if requested
        if coverage:
            cmd.extend(["--cov=fxml4", "--cov-report=term-missing"])

        # Add output options
        cmd.extend(
            [
                "-v",
                "--tb=short",
                "--durations=10",
                "--strict-markers",
                "--strict-config",
                "--disable-warnings",
            ]
        )

        return cmd

    def _parse_pytest_output(self, output: str, result: TestCategoryResult):
        """Parse pytest output to extract test counts."""
        lines = output.split("\n")

        for line in lines:
            line = line.strip()

            # Look for test summary line
            if "passed" in line and (
                "failed" in line or "error" in line or "skipped" in line
            ):
                # Parse counts from summary
                import re

                passed_match = re.search(r"(\d+) passed", line)
                if passed_match:
                    result.passed = int(passed_match.group(1))

                failed_match = re.search(r"(\d+) failed", line)
                if failed_match:
                    result.failed = int(failed_match.group(1))

                skipped_match = re.search(r"(\d+) skipped", line)
                if skipped_match:
                    result.skipped = int(skipped_match.group(1))

                error_match = re.search(r"(\d+) error", line)
                if error_match:
                    result.error = int(error_match.group(1))

                break

    def run_comprehensive_suite(
        self, categories: Optional[List[str]] = None, exclude_optional: bool = True
    ) -> ComprehensiveTestResults:
        """Run the complete comprehensive test suite."""
        self.start_time = time.time()

        if not self.setup_test_environment():
            raise RuntimeError("Failed to setup test environment")

        if not self.validate_test_infrastructure():
            raise RuntimeError("Test infrastructure validation failed")

        # Determine which categories to run
        if categories is None:
            categories = list(self.test_categories.keys())

        if exclude_optional:
            categories = [
                cat
                for cat in categories
                if not self.test_categories[cat].get("optional", False)
            ]

        logger.info(
            f"Running comprehensive test suite with {len(categories)} categories"
        )

        # Execute tests by priority
        sorted_categories = sorted(
            categories, key=lambda x: self.test_categories[x]["priority"]
        )

        for category in sorted_categories:
            try:
                result = self.run_category(category)
                self.results.category_results.append(result)

                if result.success:
                    self.results.successful_categories += 1

                self.results.executed_categories += 1
                self.results.total_tests += (
                    result.passed + result.failed + result.skipped + result.error
                )
                self.results.total_passed += result.passed
                self.results.total_failed += result.failed
                self.results.total_skipped += result.skipped
                self.results.total_errors += result.error

            except Exception as e:
                logger.error(f"Failed to run category {category}: {e}")

                # Add failed result
                failed_result = TestCategoryResult(
                    category=category,
                    description=self.test_categories[category]["description"],
                    success=False,
                    details=str(e),
                )
                self.results.category_results.append(failed_result)
                self.results.executed_categories += 1

        # Calculate final metrics
        self.results.execution_time = time.time() - self.start_time
        if self.results.executed_categories > 0:
            self.results.success_rate = (
                self.results.successful_categories / self.results.executed_categories
            ) * 100

        self.results.timestamp = datetime.now().isoformat()

        return self.results

    def generate_report(
        self, results: ComprehensiveTestResults, output_file: Optional[str] = None
    ) -> str:
        """Generate comprehensive test report."""
        report_lines = []

        # Header
        report_lines.extend(
            [
                "=" * 80,
                "FXML4 COMPREHENSIVE TEST SUITE REPORT",
                "=" * 80,
                f"Timestamp: {results.timestamp}",
                f"Execution Time: {results.execution_time:.2f}s",
                f"Categories Executed: {results.executed_categories}/{results.total_categories}",
                f"Success Rate: {results.success_rate:.1f}%",
                "",
            ]
        )

        # Overall Summary
        report_lines.extend(
            [
                "OVERALL SUMMARY",
                "-" * 40,
                f"Total Tests: {results.total_tests}",
                f"Passed: {results.total_passed}",
                f"Failed: {results.total_failed}",
                f"Skipped: {results.total_skipped}",
                f"Errors: {results.total_errors}",
                f"Successful Categories: {results.successful_categories}/{results.executed_categories}",
                "",
            ]
        )

        # Category Details
        report_lines.extend(["CATEGORY RESULTS", "-" * 40])

        for result in results.category_results:
            status = "✓ PASS" if result.success else "✗ FAIL"
            report_lines.extend(
                [
                    f"{result.category:15} | {status} | {result.passed}P {result.failed}F {result.skipped}S | {result.execution_time:.1f}s",
                    f"                | {result.description}",
                ]
            )

            if not result.success and result.details:
                # Add truncated error details
                details = (
                    result.details[:200] + "..."
                    if len(result.details) > 200
                    else result.details
                )
                report_lines.append(f"                | ERROR: {details}")

            report_lines.append("")

        # Coverage Analysis
        report_lines.extend(
            [
                "COVERAGE ANALYSIS",
                "-" * 40,
            ]
        )

        all_categories = set(self.test_categories.keys())
        executed_categories = {r.category for r in results.category_results}
        missing_categories = all_categories - executed_categories

        if missing_categories:
            report_lines.extend(
                [
                    f"Missing Categories ({len(missing_categories)}):",
                    *[
                        f"  - {cat}: {self.test_categories[cat]['description']}"
                        for cat in missing_categories
                    ],
                    "",
                ]
            )
        else:
            report_lines.extend(["✓ All 23 test categories executed", ""])

        # Recommendations
        report_lines.extend(["RECOMMENDATIONS", "-" * 40])

        if results.success_rate == 100:
            report_lines.append(
                "🎉 Excellent! All test categories passed successfully."
            )
        elif results.success_rate >= 90:
            report_lines.append(
                "🎯 Great! Most test categories passed. Address failing categories."
            )
        elif results.success_rate >= 70:
            report_lines.append("⚠️  Good coverage but some categories need attention.")
        else:
            report_lines.append(
                "🚨 Multiple test categories failing. Immediate attention required."
            )

        report_lines.extend(["", "=" * 80])

        report = "\n".join(report_lines)

        # Save to file if specified
        if output_file:
            with open(output_file, "w") as f:
                f.write(report)
            logger.info(f"Report saved to {output_file}")

        return report


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="FXML4 Comprehensive Test Suite - 23 Category Testing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python comprehensive_test_suite.py --category all
  python comprehensive_test_suite.py --category security --category auth
  python comprehensive_test_suite.py --category unit --fast-only
  python comprehensive_test_suite.py --validate-coverage
  python comprehensive_test_suite.py --generate-report --output-file report.txt
        """,
    )

    # Main options
    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Test categories to run (can be used multiple times)",
    )
    parser.add_argument(
        "--all-categories", action="store_true", help="Run all 23 test categories"
    )
    parser.add_argument(
        "--exclude-optional",
        action="store_true",
        default=True,
        help="Exclude optional categories (requires_ib, requires_network)",
    )
    parser.add_argument(
        "--include-optional",
        action="store_false",
        dest="exclude_optional",
        help="Include optional categories",
    )

    # Filtering options
    parser.add_argument(
        "--fast-only",
        action="store_true",
        help="Only run fast test categories (priority 1)",
    )
    parser.add_argument(
        "--core-only",
        action="store_true",
        help="Only run core categories (unit, integration, security, auth)",
    )

    # Output options
    parser.add_argument(
        "--generate-report",
        action="store_true",
        help="Generate comprehensive test report",
    )
    parser.add_argument(
        "--output-file",
        help="Output file for report (default: comprehensive_test_report.txt)",
    )
    parser.add_argument("--json-output", help="Save results as JSON to specified file")

    # Analysis options
    parser.add_argument(
        "--validate-coverage",
        action="store_true",
        help="Validate that all 23 categories are covered",
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List all available test categories",
    )

    args = parser.parse_args()

    # Initialize test suite
    suite = ComprehensiveTestSuite()

    # List categories
    if args.list_categories:
        print("FXML4 Comprehensive Test Categories (23 Total):")
        print("-" * 50)
        for i, (name, config) in enumerate(suite.test_categories.items(), 1):
            priority = config["priority"]
            optional = " (optional)" if config.get("optional") else ""
            print(
                f"{i:2d}. {name:15} - {config['description']}{optional} [Priority: {priority}]"
            )
        return 0

    # Validate coverage
    if args.validate_coverage:
        all_categories = set(suite.test_categories.keys())
        print(
            f"✓ All {len(all_categories)} test categories are defined in the framework"
        )
        print("Categories:", ", ".join(sorted(all_categories)))
        return 0

    # Determine categories to run
    categories = None
    if args.all_categories or (args.categories and "all" in args.categories):
        categories = list(suite.test_categories.keys())
    elif args.categories:
        categories = args.categories
        # Validate categories
        invalid = set(categories) - set(suite.test_categories.keys())
        if invalid:
            print(f"Error: Unknown categories: {', '.join(invalid)}")
            print("Use --list-categories to see available options")
            return 1
    elif args.fast_only:
        categories = [
            name
            for name, config in suite.test_categories.items()
            if config["priority"] == 1
        ]
    elif args.core_only:
        categories = ["unit", "integration", "security", "auth", "api"]
    else:
        # Default to essential categories
        categories = ["unit", "fast", "security", "auth", "api"]
        print(
            "Running default essential categories. Use --all-categories for complete suite."
        )

    try:
        # Run comprehensive test suite
        print(f"🚀 Starting FXML4 Comprehensive Test Suite")
        print(f"Categories to execute: {len(categories)}")
        print(f"Exclude optional: {args.exclude_optional}")

        results = suite.run_comprehensive_suite(
            categories=categories, exclude_optional=args.exclude_optional
        )

        # Generate report
        if args.generate_report or args.output_file:
            output_file = args.output_file or "comprehensive_test_report.txt"
            report = suite.generate_report(results, output_file)
            print(f"\n📊 Report generated: {output_file}")
        else:
            # Print summary
            print(f"\n" + "=" * 60)
            print(f"🎯 COMPREHENSIVE TEST SUITE SUMMARY")
            print(f"=" * 60)
            print(
                f"Categories Executed: {results.executed_categories}/{results.total_categories}"
            )
            print(f"Success Rate: {results.success_rate:.1f}%")
            print(f"Total Tests: {results.total_tests}")
            print(f"Passed: {results.total_passed}")
            print(f"Failed: {results.total_failed}")
            print(f"Execution Time: {results.execution_time:.1f}s")

        # Save JSON results
        if args.json_output:
            with open(args.json_output, "w") as f:
                json.dump(asdict(results), f, indent=2, default=str)
            print(f"📄 JSON results saved: {args.json_output}")

        # Determine exit code
        if results.success_rate == 100:
            print(f"\n🎉 ALL TESTS PASSED! FXML4 system is fully validated.")
            return 0
        elif results.success_rate >= 90:
            print(
                f"\n🎯 Most tests passed. Address {results.executed_categories - results.successful_categories} failing categories."
            )
            return 1
        else:
            print(
                f"\n🚨 {results.executed_categories - results.successful_categories} categories failed. Immediate attention required."
            )
            return 1

    except Exception as e:
        logger.error(f"Comprehensive test suite execution failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
