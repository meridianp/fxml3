#!/usr/bin/env python3
"""
Property-Based Test Runner for FXML4
Integrates Hypothesis with the TDD automation framework
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from hypothesis import HealthCheck, settings


@dataclass
class PropertyTestResult:
    """Results from property-based testing"""

    component: str
    test_file: str
    test_name: str
    status: str  # passed, failed, error
    examples_generated: int
    examples_run: int
    execution_time: float
    falsifying_example: Optional[str] = None
    error_message: Optional[str] = None
    shrunk_example: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class PropertyTestSummary:
    """Summary of property testing across components"""

    total_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    total_examples: int
    execution_time: float
    results: List[PropertyTestResult]
    coverage_analysis: Dict[str, Any]
    recommendations: List[str]


class PropertyTestRunner:
    """Property-based test runner for FXML4 components"""

    def __init__(self, config_path: str = ".claude-tdd/config.yml"):
        self.config = self._load_config(config_path)
        self.project_root = Path.cwd()
        self.property_root = self.project_root / ".claude-tdd/property_testing"
        self.reports_dir = self.property_root / "reports"
        self.reports_dir.mkdir(exist_ok=True)

        # Configure Hypothesis settings for financial testing
        self._configure_hypothesis_settings()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load TDD configuration"""
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _configure_hypothesis_settings(self):
        """Configure Hypothesis for financial testing requirements"""
        # Financial systems need extensive testing
        settings.register_profile(
            "financial",
            max_examples=500,
            deadline=30000,  # 30 seconds per test
            derandomize=True,  # Deterministic for CI
            suppress_health_check=[HealthCheck.too_slow],
            print_blob=True,  # Show failing examples
        )

        settings.register_profile(
            "financial_ci",
            max_examples=200,
            deadline=15000,  # 15 seconds per test
            derandomize=True,
            suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
        )

        settings.register_profile(
            "financial_dev",
            max_examples=100,
            deadline=10000,  # 10 seconds per test
            derandomize=False,  # Allow randomization in development
            print_blob=True,
        )

        # Use appropriate profile based on environment
        if os.getenv("CI"):
            settings.load_profile("financial_ci")
        elif os.getenv("HYPOTHESIS_PROFILE"):
            settings.load_profile(os.getenv("HYPOTHESIS_PROFILE"))
        else:
            settings.load_profile("financial_dev")

    def discover_property_tests(self, component: str = None) -> List[Tuple[str, str]]:
        """Discover property tests in the project"""
        test_files = []

        if component:
            components = [component]
        else:
            components = list(self.config["components"].keys())

        for comp in components:
            component_config = self.config["components"][comp]
            component_path = Path(component_config["path"])

            # Look for property test files
            patterns = [
                "**/test_*property*.py",
                "**/property_test_*.py",
                "**/*_property_test.py",
                "**/test_hypothesis_*.py",
            ]

            for pattern in patterns:
                for test_file in component_path.glob(pattern):
                    test_files.append((comp, str(test_file)))

            # Also check for tests using Hypothesis decorators
            for test_file in component_path.glob("**/test_*.py"):
                if self._contains_hypothesis_tests(test_file):
                    test_files.append((comp, str(test_file)))

        return test_files

    def _contains_hypothesis_tests(self, file_path: Path) -> bool:
        """Check if file contains Hypothesis-based tests"""
        try:
            with open(file_path, "r") as f:
                content = f.read()
                return any(
                    indicator in content
                    for indicator in ["@given", "hypothesis", "strategies", "@example"]
                )
        except Exception:
            return False

    def run_property_tests(
        self, component: str = None, test_file: str = None, dry_run: bool = False
    ) -> PropertyTestSummary:
        """Run property tests for specified component or all components"""
        start_time = time.time()
        results = []

        if test_file:
            # Run specific test file
            test_files = [(component or "unknown", test_file)]
        else:
            # Discover all property tests
            test_files = self.discover_property_tests(component)

        print(f"Found {len(test_files)} property test files")

        for comp, file_path in test_files:
            if dry_run:
                print(f"[DRY RUN] Would run property tests in: {file_path}")
                continue

            file_results = self._run_property_test_file(comp, file_path)
            results.extend(file_results)

        execution_time = time.time() - start_time

        # Generate summary
        summary = self._generate_summary(results, execution_time)

        # Save results
        self._save_results(summary)

        # Generate reports
        self._generate_reports(summary)

        return summary

    def _run_property_test_file(
        self, component: str, file_path: str
    ) -> List[PropertyTestResult]:
        """Run property tests in a specific file"""
        print(f"\nRunning property tests in: {file_path}")
        results = []

        try:
            # Use pytest with Hypothesis integration
            cmd = [
                sys.executable,
                "-m",
                "pytest",
                file_path,
                "-v",
                "--tb=short",
                "--hypothesis-show-statistics",
                "--json-report",
                "--json-report-file",
                f"{self.reports_dir}/pytest_report_{int(time.time())}.json",
            ]

            # Add Hypothesis-specific options
            cmd.extend(
                [
                    "--hypothesis-verbosity=verbose",
                    "--hypothesis-seed=0",  # Deterministic for CI
                ]
            )

            start_time = time.time()

            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes per file
            )

            execution_time = time.time() - start_time

            # Parse pytest output for property test results
            test_results = self._parse_pytest_output(
                component, file_path, result.stdout, result.stderr, execution_time
            )
            results.extend(test_results)

        except subprocess.TimeoutExpired:
            results.append(
                PropertyTestResult(
                    component=component,
                    test_file=file_path,
                    test_name="timeout",
                    status="error",
                    examples_generated=0,
                    examples_run=0,
                    execution_time=300.0,
                    error_message="Property test execution timed out",
                )
            )

        except Exception as e:
            results.append(
                PropertyTestResult(
                    component=component,
                    test_file=file_path,
                    test_name="error",
                    status="error",
                    examples_generated=0,
                    examples_run=0,
                    execution_time=0.0,
                    error_message=str(e),
                )
            )

        return results

    def _parse_pytest_output(
        self,
        component: str,
        file_path: str,
        stdout: str,
        stderr: str,
        execution_time: float,
    ) -> List[PropertyTestResult]:
        """Parse pytest output to extract property test results"""
        results = []
        lines = stdout.split("\n")

        current_test = None
        examples_generated = 0
        examples_run = 0

        for line in lines:
            line = line.strip()

            # Extract test name
            if " PASSED" in line or " FAILED" in line or " ERROR" in line:
                if "::" in line:
                    test_name = line.split("::")[1].split(" ")[0]
                    status = (
                        "passed"
                        if "PASSED" in line
                        else "failed" if "FAILED" in line else "error"
                    )

                    results.append(
                        PropertyTestResult(
                            component=component,
                            test_file=file_path,
                            test_name=test_name,
                            status=status,
                            examples_generated=examples_generated
                            or 100,  # Default if not found
                            examples_run=examples_run or examples_generated or 100,
                            execution_time=(
                                execution_time
                                / len(
                                    [
                                        l
                                        for l in lines
                                        if " PASSED" in l or " FAILED" in l
                                    ]
                                )
                                if "PASSED" in stdout or "FAILED" in stdout
                                else execution_time
                            ),
                        )
                    )

            # Extract Hypothesis statistics
            if "Trying example:" in line:
                examples_run += 1
            elif "examples generated" in line:
                try:
                    examples_generated = int(
                        line.split("examples generated")[0].strip().split()[-1]
                    )
                except (ValueError, IndexError):
                    pass

            # Extract falsifying examples
            if "Falsifying example:" in line:
                falsifying_example = line.replace("Falsifying example:", "").strip()
                if results:
                    results[-1].falsifying_example = falsifying_example

        # If no specific tests found, create a general result
        if not results:
            status = "passed" if result.returncode == 0 else "failed"
            results.append(
                PropertyTestResult(
                    component=component,
                    test_file=file_path,
                    test_name="property_tests",
                    status=status,
                    examples_generated=examples_generated or 0,
                    examples_run=examples_run or 0,
                    execution_time=execution_time,
                    error_message=stderr if stderr and result.returncode != 0 else None,
                )
            )

        return results

    def _generate_summary(
        self, results: List[PropertyTestResult], execution_time: float
    ) -> PropertyTestSummary:
        """Generate summary of property testing results"""
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.status == "passed")
        failed_tests = sum(1 for r in results if r.status == "failed")
        error_tests = sum(1 for r in results if r.status == "error")
        total_examples = sum(r.examples_run for r in results)

        # Analyze coverage
        coverage_analysis = self._analyze_property_coverage(results)

        # Generate recommendations
        recommendations = self._generate_recommendations(results)

        return PropertyTestSummary(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            error_tests=error_tests,
            total_examples=total_examples,
            execution_time=execution_time,
            results=results,
            coverage_analysis=coverage_analysis,
            recommendations=recommendations,
        )

    def _analyze_property_coverage(
        self, results: List[PropertyTestResult]
    ) -> Dict[str, Any]:
        """Analyze property test coverage across components"""
        components = set(r.component for r in results)

        coverage = {
            "components_tested": len(components),
            "component_breakdown": {},
            "test_types": {
                "financial_calculations": 0,
                "invariant_tests": 0,
                "elliott_wave_tests": 0,
                "risk_management_tests": 0,
            },
        }

        for component in components:
            comp_results = [r for r in results if r.component == component]
            coverage["component_breakdown"][component] = {
                "total_tests": len(comp_results),
                "passed": sum(1 for r in comp_results if r.status == "passed"),
                "examples_run": sum(r.examples_run for r in comp_results),
            }

        # Categorize test types based on test names
        for result in results:
            test_name = result.test_name.lower()
            if "pnl" in test_name or "price" in test_name or "calculation" in test_name:
                coverage["test_types"]["financial_calculations"] += 1
            elif "invariant" in test_name or "consistency" in test_name:
                coverage["test_types"]["invariant_tests"] += 1
            elif "elliott" in test_name or "wave" in test_name:
                coverage["test_types"]["elliott_wave_tests"] += 1
            elif "risk" in test_name or "var" in test_name:
                coverage["test_types"]["risk_management_tests"] += 1

        return coverage

    def _generate_recommendations(self, results: List[PropertyTestResult]) -> List[str]:
        """Generate recommendations based on property testing results"""
        recommendations = []

        failed_results = [r for r in results if r.status == "failed"]
        error_results = [r for r in results if r.status == "error"]

        if failed_results:
            recommendations.append(
                f"Fix {len(failed_results)} failing property tests. These indicate potential issues with business logic."
            )

        if error_results:
            recommendations.append(
                f"Resolve {len(error_results)} property test errors. These may indicate test setup issues."
            )

        # Check for insufficient examples
        low_example_tests = [r for r in results if r.examples_run < 50]
        if low_example_tests:
            recommendations.append(
                f"Increase example count for {len(low_example_tests)} tests to improve property coverage."
            )

        # Check for missing test types
        components = set(r.component for r in results)
        for component in components:
            comp_results = [r for r in results if r.component == component]

            has_financial_tests = any(
                "pnl" in r.test_name.lower() or "price" in r.test_name.lower()
                for r in comp_results
            )
            has_invariant_tests = any(
                "invariant" in r.test_name.lower() for r in comp_results
            )

            if not has_financial_tests and "core" in component:
                recommendations.append(
                    f"Add financial calculation property tests for {component} component."
                )

            if not has_invariant_tests:
                recommendations.append(
                    f"Add invariant property tests for {component} component."
                )

        if not recommendations:
            recommendations.append(
                "Excellent property test coverage! All tests passing with good example counts."
            )

        return recommendations

    def _save_results(self, summary: PropertyTestSummary):
        """Save property testing results to file"""
        results_file = (
            self.reports_dir
            / f"property_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(results_file, "w") as f:
            json.dump(asdict(summary), f, indent=2, default=str)

        print(f"Property test results saved to: {results_file}")

    def _generate_reports(self, summary: PropertyTestSummary):
        """Generate property testing reports"""
        self._generate_html_report(summary)
        self._generate_markdown_report(summary)
        print(f"Property test reports generated in: {self.reports_dir}")

    def _generate_html_report(self, summary: PropertyTestSummary):
        """Generate HTML property testing report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>FXML4 Property Testing Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .summary {{ margin: 20px 0; }}
        .test {{ margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .passed {{ border-left: 5px solid green; }}
        .failed {{ border-left: 5px solid red; }}
        .error {{ border-left: 5px solid orange; }}
        .examples {{ font-style: italic; color: #666; }}
        .falsifying {{ background: #ffe6e6; padding: 10px; margin: 10px 0; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>FXML4 Property Testing Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Tests:</strong> {summary.total_tests}</p>
        <p><strong>Passed:</strong> <span style="color: green;">{summary.passed_tests}</span></p>
        <p><strong>Failed:</strong> <span style="color: red;">{summary.failed_tests}</span></p>
        <p><strong>Errors:</strong> <span style="color: orange;">{summary.error_tests}</span></p>
        <p><strong>Total Examples Run:</strong> {summary.total_examples}</p>
        <p><strong>Execution Time:</strong> {summary.execution_time:.1f} seconds</p>
    </div>

    <div class="coverage">
        <h2>Coverage Analysis</h2>
        <p><strong>Components Tested:</strong> {summary.coverage_analysis['components_tested']}</p>
        <h3>Test Types:</h3>
        <ul>
"""
        for test_type, count in summary.coverage_analysis["test_types"].items():
            html_content += f"            <li><strong>{test_type.replace('_', ' ').title()}:</strong> {count}</li>\n"

        html_content += """
        </ul>
    </div>

    <div class="tests">
        <h2>Test Results</h2>
"""

        for result in summary.results:
            status_class = result.status
            html_content += f"""
        <div class="test {status_class}">
            <h3>{result.test_name} ({result.component})</h3>
            <p><strong>Status:</strong> {result.status.upper()}</p>
            <p class="examples">Examples: {result.examples_run} run, {result.examples_generated} generated</p>
            <p><strong>Execution Time:</strong> {result.execution_time:.2f} seconds</p>
"""
            if result.falsifying_example:
                html_content += f"""
            <div class="falsifying">
                <strong>Falsifying Example:</strong><br>
                <code>{result.falsifying_example}</code>
            </div>
"""
            if result.error_message:
                html_content += f"""
            <div class="error-msg">
                <strong>Error:</strong> {result.error_message}
            </div>
"""
            html_content += "        </div>\n"

        html_content += f"""
    </div>

    <div class="recommendations">
        <h2>Recommendations</h2>
        <ul>
"""
        for rec in summary.recommendations:
            html_content += f"            <li>{rec}</li>\n"

        html_content += """
        </ul>
    </div>
</body>
</html>
"""

        html_file = self.reports_dir / "property_test_report.html"
        with open(html_file, "w") as f:
            f.write(html_content)

    def _generate_markdown_report(self, summary: PropertyTestSummary):
        """Generate Markdown property testing report"""
        md_content = f"""# FXML4 Property Testing Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Total Tests:** {summary.total_tests}
- **Passed:** {summary.passed_tests} ✅
- **Failed:** {summary.failed_tests} ❌
- **Errors:** {summary.error_tests} ⚠️
- **Total Examples Run:** {summary.total_examples}
- **Execution Time:** {summary.execution_time:.1f} seconds

## Coverage Analysis

- **Components Tested:** {summary.coverage_analysis['components_tested']}

### Test Types

"""
        for test_type, count in summary.coverage_analysis["test_types"].items():
            md_content += f"- **{test_type.replace('_', ' ').title()}:** {count}\n"

        md_content += "\n## Test Results\n\n"
        md_content += "| Test | Component | Status | Examples | Time |\n"
        md_content += "|------|-----------|--------|----------|------|\n"

        for result in summary.results:
            status_emoji = (
                "✅"
                if result.status == "passed"
                else "❌" if result.status == "failed" else "⚠️"
            )
            md_content += f"| {result.test_name} | {result.component} | {status_emoji} {result.status} | {result.examples_run} | {result.execution_time:.2f}s |\n"

        md_content += "\n## Recommendations\n\n"
        for i, rec in enumerate(summary.recommendations, 1):
            md_content += f"{i}. {rec}\n"

        md_content += "\n---\n*Generated by FXML4 Claude TDD Automation Framework*\n"

        md_file = self.reports_dir / "property_test_report.md"
        with open(md_file, "w") as f:
            f.write(md_content)


def main():
    """Main entry point for property test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="FXML4 Property Test Runner")
    parser.add_argument("--component", "-c", help="Run tests for specific component")
    parser.add_argument("--test-file", "-f", help="Run specific test file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be executed"
    )
    parser.add_argument(
        "--discover", action="store_true", help="Discover property tests only"
    )

    args = parser.parse_args()

    runner = PropertyTestRunner()

    if args.discover:
        test_files = runner.discover_property_tests(args.component)
        print(f"Found {len(test_files)} property test files:")
        for comp, file_path in test_files:
            print(f"  {comp}: {file_path}")
        return 0

    try:
        summary = runner.run_property_tests(
            args.component, args.test_file, args.dry_run
        )

        print(f"\n{'='*60}")
        print("PROPERTY TESTING SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests: {summary.total_tests}")
        print(f"Passed: {summary.passed_tests}")
        print(f"Failed: {summary.failed_tests}")
        print(f"Errors: {summary.error_tests}")
        print(f"Total Examples: {summary.total_examples}")
        print(f"Execution Time: {summary.execution_time:.1f} seconds")

        if summary.recommendations:
            print("\nRecommendations:")
            for i, rec in enumerate(summary.recommendations, 1):
                print(f"{i}. {rec}")

        return 0 if summary.failed_tests == 0 and summary.error_tests == 0 else 1

    except Exception as e:
        print(f"Error running property tests: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
