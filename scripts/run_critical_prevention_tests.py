#!/usr/bin/env python3
"""
CRITICAL PREVENTION MEASURES TEST RUNNER
========================================

Ensures all three critical prevention measures are implemented and working:
1. Mandatory Login Test - CI/CD fails if users cannot login
2. End-to-End Validation - Test complete user journey
3. Real Environment Testing - Test against actual deployed services

This script is the single source of truth for validating that our CI/CD
properly prevents the three common deployment failures.

Usage:
    python scripts/run_critical_prevention_tests.py [environment]

Environment options: local, staging, production
"""

import asyncio
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class PreventionTestResult:
    """Result of a critical prevention test"""

    test_name: str
    category: str  # "mandatory_login", "e2e_validation", "real_environment"
    status: str  # "PASSED", "FAILED", "SKIPPED"
    duration_seconds: float
    error_message: Optional[str] = None
    details: Dict[str, Any] = None


class CriticalPreventionTester:
    """Runs all critical prevention measure tests"""

    def __init__(self, environment: str = "local"):
        self.environment = environment.lower()
        self.results: List[PreventionTestResult] = []
        self.config = self._get_environment_config()

    def _get_environment_config(self) -> Dict[str, str]:
        """Get environment-specific configuration"""
        configs = {
            "local": {
                "api_url": os.getenv("API_URL", "http://localhost:8001"),
                "ui_url": os.getenv("UI_URL", "http://localhost:3000"),
                "test_mode": "full",
                "skip_production_only": True,
            },
            "staging": {
                "api_url": os.getenv("STAGING_URL", "http://staging-api.fxml4.com"),
                "ui_url": os.getenv("STAGING_UI_URL", "http://staging-app.fxml4.com"),
                "test_mode": "full",
                "skip_production_only": False,
            },
            "production": {
                "api_url": os.getenv("PRODUCTION_URL", "https://api.fxml4.com"),
                "ui_url": os.getenv("PRODUCTION_UI_URL", "https://app.fxml4.com"),
                "test_mode": "readonly",
                "skip_production_only": False,
            },
        }

        return configs.get(self.environment, configs["local"])

    def run_mandatory_login_test(self) -> PreventionTestResult:
        """Prevention Measure 1: Mandatory Login Test"""
        logger.info("🔐 Running MANDATORY LOGIN TEST")
        start_time = time.time()

        try:
            # Run the mandatory login test
            result = subprocess.run(
                [
                    sys.executable,
                    "tests/critical/test_mandatory_login.py",
                    self.config["api_url"],
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            duration = time.time() - start_time

            if result.returncode == 0:
                logger.info("✅ MANDATORY LOGIN TEST PASSED")
                return PreventionTestResult(
                    test_name="Mandatory Login Test",
                    category="mandatory_login",
                    status="PASSED",
                    duration_seconds=duration,
                    details={"stdout": result.stdout[:500]},  # Truncate for brevity
                )
            else:
                logger.error("❌ MANDATORY LOGIN TEST FAILED")
                logger.error(f"Error output: {result.stderr}")
                return PreventionTestResult(
                    test_name="Mandatory Login Test",
                    category="mandatory_login",
                    status="FAILED",
                    duration_seconds=duration,
                    error_message=result.stderr[:200],
                    details={"returncode": result.returncode},
                )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            logger.error("❌ MANDATORY LOGIN TEST TIMED OUT")
            return PreventionTestResult(
                test_name="Mandatory Login Test",
                category="mandatory_login",
                status="FAILED",
                duration_seconds=duration,
                error_message="Test timed out after 60 seconds",
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ MANDATORY LOGIN TEST ERROR: {e}")
            return PreventionTestResult(
                test_name="Mandatory Login Test",
                category="mandatory_login",
                status="FAILED",
                duration_seconds=duration,
                error_message=str(e),
            )

    async def run_e2e_validation_test(self) -> PreventionTestResult:
        """Prevention Measure 2: End-to-End User Journey Validation"""
        logger.info("🚀 Running END-TO-END VALIDATION TEST")
        start_time = time.time()

        try:
            if self.config["test_mode"] == "readonly":
                # Production - run specific test
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "tests/e2e/test_complete_user_journey.py::test_e2e_production_environment",
                        "-v",
                        "--tb=short",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
            else:
                # Full E2E testing
                result = subprocess.run(
                    [
                        sys.executable,
                        "tests/e2e/test_complete_user_journey.py",
                        self.config["api_url"],
                        self.config["ui_url"],
                    ],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )

            duration = time.time() - start_time

            if result.returncode == 0:
                logger.info("✅ END-TO-END VALIDATION PASSED")
                return PreventionTestResult(
                    test_name="End-to-End User Journey Validation",
                    category="e2e_validation",
                    status="PASSED",
                    duration_seconds=duration,
                    details={"stdout": result.stdout[:500]},
                )
            else:
                logger.error("❌ END-TO-END VALIDATION FAILED")
                logger.error(f"Error output: {result.stderr}")
                return PreventionTestResult(
                    test_name="End-to-End User Journey Validation",
                    category="e2e_validation",
                    status="FAILED",
                    duration_seconds=duration,
                    error_message=result.stderr[:200],
                    details={"returncode": result.returncode},
                )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            logger.error("❌ END-TO-END VALIDATION TIMED OUT")
            return PreventionTestResult(
                test_name="End-to-End User Journey Validation",
                category="e2e_validation",
                status="FAILED",
                duration_seconds=duration,
                error_message="Test timed out after 600 seconds",
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ END-TO-END VALIDATION ERROR: {e}")
            return PreventionTestResult(
                test_name="End-to-End User Journey Validation",
                category="e2e_validation",
                status="FAILED",
                duration_seconds=duration,
                error_message=str(e),
            )

    def run_real_environment_test(self) -> PreventionTestResult:
        """Prevention Measure 3: Real Environment Testing"""
        logger.info("🌍 Running REAL ENVIRONMENT TEST")
        start_time = time.time()

        try:
            # Run real environment test
            result = subprocess.run(
                [
                    sys.executable,
                    "tests/environments/test_real_environment.py",
                    self.environment,
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )

            duration = time.time() - start_time

            if result.returncode == 0:
                logger.info("✅ REAL ENVIRONMENT TEST PASSED")
                return PreventionTestResult(
                    test_name="Real Environment Testing",
                    category="real_environment",
                    status="PASSED",
                    duration_seconds=duration,
                    details={"stdout": result.stdout[:500]},
                )
            else:
                logger.error("❌ REAL ENVIRONMENT TEST FAILED")
                logger.error(f"Error output: {result.stderr}")
                return PreventionTestResult(
                    test_name="Real Environment Testing",
                    category="real_environment",
                    status="FAILED",
                    duration_seconds=duration,
                    error_message=result.stderr[:200],
                    details={"returncode": result.returncode},
                )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            logger.error("❌ REAL ENVIRONMENT TEST TIMED OUT")
            return PreventionTestResult(
                test_name="Real Environment Testing",
                category="real_environment",
                status="FAILED",
                duration_seconds=duration,
                error_message="Test timed out after 300 seconds",
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ REAL ENVIRONMENT TEST ERROR: {e}")
            return PreventionTestResult(
                test_name="Real Environment Testing",
                category="real_environment",
                status="FAILED",
                duration_seconds=duration,
                error_message=str(e),
            )

    def run_pytest_critical_markers(self) -> PreventionTestResult:
        """Run all tests marked as critical via pytest"""
        logger.info("🎯 Running PYTEST CRITICAL MARKERS")
        start_time = time.time()

        try:
            # Run all critical tests
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-m",
                    "critical",
                    "-v",
                    "--tb=short",
                    "--maxfail=3",
                ],
                capture_output=True,
                text=True,
                timeout=900,
            )

            duration = time.time() - start_time

            if result.returncode == 0:
                logger.info("✅ PYTEST CRITICAL TESTS PASSED")
                return PreventionTestResult(
                    test_name="Pytest Critical Tests",
                    category="pytest_critical",
                    status="PASSED",
                    duration_seconds=duration,
                    details={"stdout": result.stdout[:500]},
                )
            else:
                logger.error("❌ PYTEST CRITICAL TESTS FAILED")
                return PreventionTestResult(
                    test_name="Pytest Critical Tests",
                    category="pytest_critical",
                    status="FAILED",
                    duration_seconds=duration,
                    error_message=result.stderr[:200],
                    details={"returncode": result.returncode},
                )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ PYTEST CRITICAL TESTS ERROR: {e}")
            return PreventionTestResult(
                test_name="Pytest Critical Tests",
                category="pytest_critical",
                status="FAILED",
                duration_seconds=duration,
                error_message=str(e),
            )

    async def run_all_prevention_tests(self) -> List[PreventionTestResult]:
        """Execute all critical prevention measures"""
        logger.info(
            f"🛡️  RUNNING ALL CRITICAL PREVENTION MEASURES for {self.environment.upper()}"
        )
        logger.info(f"API URL: {self.config['api_url']}")
        logger.info(f"UI URL: {self.config['ui_url']}")
        logger.info(f"Test Mode: {self.config['test_mode']}")

        # Prevention Measure 1: Mandatory Login Test
        result1 = self.run_mandatory_login_test()
        self.results.append(result1)

        # Prevention Measure 2: End-to-End Validation
        result2 = await self.run_e2e_validation_test()
        self.results.append(result2)

        # Prevention Measure 3: Real Environment Testing
        result3 = self.run_real_environment_test()
        self.results.append(result3)

        # Additional: Pytest Critical Tests
        result4 = self.run_pytest_critical_markers()
        self.results.append(result4)

        # Analyze results
        passed_tests = [r for r in self.results if r.status == "PASSED"]
        failed_tests = [r for r in self.results if r.status == "FAILED"]
        total_duration = sum(r.duration_seconds for r in self.results)

        logger.info(f"📊 CRITICAL PREVENTION MEASURES RESULTS:")
        logger.info(f"  ✅ Passed: {len(passed_tests)}/{len(self.results)}")
        logger.info(f"  ❌ Failed: {len(failed_tests)}")
        logger.info(f"  ⏱️  Total Time: {total_duration:.2f} seconds")

        # Log individual results
        for result in self.results:
            status_emoji = "✅" if result.status == "PASSED" else "❌"
            logger.info(
                f"  {status_emoji} {result.test_name}: {result.status} ({result.duration_seconds:.2f}s)"
            )
            if result.error_message:
                logger.warning(f"    Error: {result.error_message}")

        # Critical validation - all prevention measures must pass
        if failed_tests:
            failed_categories = [r.category for r in failed_tests]
            logger.error(f"💥 CRITICAL PREVENTION MEASURES FAILED")
            logger.error(f"Failed categories: {failed_categories}")
            raise AssertionError(
                f"Critical prevention measures failed: {failed_categories}"
            )

        logger.info("🎉 ALL CRITICAL PREVENTION MEASURES PASSED")
        logger.info(
            "✅ Deployment can proceed safely - all prevention measures validated"
        )

        return self.results

    def generate_report(self) -> str:
        """Generate a summary report"""
        passed = len([r for r in self.results if r.status == "PASSED"])
        total = len(self.results)

        report = f"""
CRITICAL PREVENTION MEASURES VALIDATION REPORT
=============================================

Environment: {self.environment.upper()}
API URL: {self.config['api_url']}
UI URL: {self.config['ui_url']}

PREVENTION MEASURE RESULTS:
"""

        for result in self.results:
            status_symbol = "✅" if result.status == "PASSED" else "❌"
            report += f"\n{status_symbol} {result.test_name}"
            report += f"\n   Status: {result.status}"
            report += f"\n   Duration: {result.duration_seconds:.2f}s"
            if result.error_message:
                report += f"\n   Error: {result.error_message}"
            report += "\n"

        report += f"\nSUMMARY: {passed}/{total} prevention measures passed"

        if passed == total:
            report += "\n\n🎉 ALL PREVENTION MEASURES VALIDATED"
            report += "\n✅ CI/CD pipeline properly prevents deployment failures"
            report += "\n✅ Login functionality verified"
            report += "\n✅ End-to-end user journeys tested"
            report += "\n✅ Real environment connectivity confirmed"
        else:
            report += "\n\n💥 PREVENTION MEASURES FAILED"
            report += "\n❌ CI/CD pipeline has gaps that could allow broken deployments"

        return report


async def main():
    """Main execution function"""
    # Parse command line arguments
    environment = sys.argv[1] if len(sys.argv) > 1 else "local"

    if environment not in ["local", "staging", "production"]:
        print("❌ Invalid environment. Choose: local, staging, production")
        sys.exit(1)

    try:
        # Initialize tester
        tester = CriticalPreventionTester(environment)

        # Run all prevention tests
        results = await tester.run_all_prevention_tests()

        # Generate and display report
        report = tester.generate_report()
        print(report)

        # Save report to file
        report_file = (
            f"reports/critical-prevention-{environment}-{int(time.time())}.txt"
        )
        os.makedirs("reports", exist_ok=True)
        with open(report_file, "w") as f:
            f.write(report)

        print(f"\n📄 Report saved to: {report_file}")

        return 0  # Success

    except Exception as e:
        print(f"💥 CRITICAL PREVENTION TESTING FAILED: {e}")
        return 1  # Failure


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
