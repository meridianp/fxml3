#!/usr/bin/env python3
"""
FXML4 Frontend Test Runner Integration
Integrates frontend testing with the main Claude TDD framework
"""

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from nextjs_integration import FrontendTestResult, NextJSIntegration


@dataclass
class FrontendTDDCycle:
    """Represents a TDD cycle for frontend development"""

    component_name: str
    cycle_number: int
    red_phase_tests: List[str] = field(default_factory=list)
    green_phase_tests: List[str] = field(default_factory=list)
    refactor_phase_tests: List[str] = field(default_factory=list)
    results: Dict[str, FrontendTestResult] = field(default_factory=dict)


class FrontendTestRunner:
    """Integrates frontend testing with Claude TDD automation"""

    def __init__(self, project_path: str = "fxml4-ui/"):
        self.project_path = Path(project_path)
        self.nextjs_integration = NextJSIntegration(project_path)
        self.tdd_cycles = []
        self.current_cycle: Optional[FrontendTDDCycle] = None

    async def start_frontend_tdd_cycle(
        self, component_name: str, test_patterns: List[str] = None
    ) -> FrontendTDDCycle:
        """Start a new TDD cycle for a frontend component"""
        cycle_number = len(self.tdd_cycles) + 1

        cycle = FrontendTDDCycle(
            component_name=component_name,
            cycle_number=cycle_number,
        )

        # Define test patterns for each phase
        if test_patterns:
            cycle.red_phase_tests = test_patterns
        else:
            cycle.red_phase_tests = [
                f"src/components/{component_name}/**/*.test.{ext}"
                for ext in ["ts", "tsx"]
            ]

        cycle.green_phase_tests = cycle.red_phase_tests.copy()
        cycle.refactor_phase_tests = [
            *cycle.red_phase_tests,
            *[
                f"src/components/{component_name}/**/*.spec.{ext}"
                for ext in ["ts", "tsx"]
            ],
        ]

        self.current_cycle = cycle
        self.tdd_cycles.append(cycle)

        print(f"Started TDD cycle {cycle_number} for component: {component_name}")
        return cycle

    async def execute_red_phase(self) -> bool:
        """Execute the RED phase - failing tests"""
        if not self.current_cycle:
            raise ValueError("No active TDD cycle")

        print(f"🔴 RED PHASE - Component: {self.current_cycle.component_name}")

        # Run tests expecting them to fail
        result = await self._run_targeted_tests(
            self.current_cycle.red_phase_tests, expect_failure=True
        )

        self.current_cycle.results["red"] = result

        # RED phase succeeds if tests fail as expected
        success = not result.success
        print(
            f"Red phase {'✓' if success else '✗'}: Tests {'failed as expected' if success else 'unexpectedly passed'}"
        )

        return success

    async def execute_green_phase(self) -> bool:
        """Execute the GREEN phase - make tests pass"""
        if not self.current_cycle:
            raise ValueError("No active TDD cycle")

        print(f"🟢 GREEN PHASE - Component: {self.current_cycle.component_name}")

        # Run tests expecting them to pass
        result = await self._run_targeted_tests(
            self.current_cycle.green_phase_tests, expect_failure=False
        )

        self.current_cycle.results["green"] = result

        success = result.success
        print(
            f"Green phase {'✓' if success else '✗'}: Tests {'passed' if success else 'still failing'}"
        )

        return success

    async def execute_refactor_phase(self) -> bool:
        """Execute the REFACTOR phase - improve code while keeping tests green"""
        if not self.current_cycle:
            raise ValueError("No active TDD cycle")

        print(f"🔵 REFACTOR PHASE - Component: {self.current_cycle.component_name}")

        # Run full test suite including additional quality checks
        result = await self._run_comprehensive_tests(
            self.current_cycle.refactor_phase_tests
        )

        self.current_cycle.results["refactor"] = result

        success = result.success
        print(
            f"Refactor phase {'✓' if success else '✗'}: All tests {'passed' if success else 'failed'}"
        )

        return success

    async def _run_targeted_tests(
        self, test_patterns: List[str], expect_failure: bool = False
    ) -> FrontendTestResult:
        """Run specific test patterns"""
        try:
            # Build Jest command for targeted tests
            cmd = ["npm", "run", "test", "--"]
            cmd.extend(["--testPathPattern", "|".join(test_patterns)])
            cmd.extend(["--watchAll=false", "--passWithNoTests"])

            if expect_failure:
                # Add flag to continue on failures
                cmd.append("--verbose")

            start_time = time.time()
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minutes for targeted tests
            )
            execution_time = time.time() - start_time

            success = result.returncode == 0
            coverage = self._extract_coverage(result.stdout)
            failed_tests = self._extract_failed_tests(result.stdout)

            return FrontendTestResult(
                test_type="targeted",
                success=success,
                execution_time=execution_time,
                coverage_percentage=coverage,
                failed_tests=failed_tests,
                error_message=result.stderr if not success else None,
            )

        except subprocess.TimeoutExpired:
            return FrontendTestResult(
                test_type="targeted",
                success=False,
                execution_time=120,
                error_message="Test execution timeout",
            )
        except Exception as e:
            return FrontendTestResult(
                test_type="targeted",
                success=False,
                execution_time=0,
                error_message=str(e),
            )

    async def _run_comprehensive_tests(
        self, test_patterns: List[str]
    ) -> FrontendTestResult:
        """Run comprehensive test suite including quality checks"""
        try:
            # Run unit tests with coverage
            unit_result = await self._run_targeted_tests(test_patterns)

            # Run linting
            lint_result = await self._run_linting()

            # Run type checking
            type_result = await self._run_type_checking()

            # Combine results
            all_success = all(
                [
                    unit_result.success,
                    lint_result.success,
                    type_result.success,
                ]
            )

            error_messages = []
            if not unit_result.success:
                error_messages.append(f"Unit tests: {unit_result.error_message}")
            if not lint_result.success:
                error_messages.append(f"Linting: {lint_result.error_message}")
            if not type_result.success:
                error_messages.append(f"Type checking: {type_result.error_message}")

            return FrontendTestResult(
                test_type="comprehensive",
                success=all_success,
                execution_time=unit_result.execution_time,
                coverage_percentage=unit_result.coverage_percentage,
                failed_tests=unit_result.failed_tests,
                error_message="; ".join(error_messages) if error_messages else None,
            )

        except Exception as e:
            return FrontendTestResult(
                test_type="comprehensive",
                success=False,
                execution_time=0,
                error_message=str(e),
            )

    async def _run_linting(self) -> FrontendTestResult:
        """Run ESLint on the project"""
        try:
            cmd = ["npm", "run", "lint"]
            start_time = time.time()
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            execution_time = time.time() - start_time

            return FrontendTestResult(
                test_type="lint",
                success=result.returncode == 0,
                execution_time=execution_time,
                error_message=result.stderr if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return FrontendTestResult(
                test_type="lint",
                success=False,
                execution_time=60,
                error_message="Linting timeout",
            )
        except Exception as e:
            return FrontendTestResult(
                test_type="lint",
                success=False,
                execution_time=0,
                error_message=str(e),
            )

    async def _run_type_checking(self) -> FrontendTestResult:
        """Run TypeScript type checking"""
        try:
            cmd = ["npx", "tsc", "--noEmit"]
            start_time = time.time()
            result = subprocess.run(
                cmd,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            execution_time = time.time() - start_time

            return FrontendTestResult(
                test_type="typecheck",
                success=result.returncode == 0,
                execution_time=execution_time,
                error_message=result.stderr if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return FrontendTestResult(
                test_type="typecheck",
                success=False,
                execution_time=60,
                error_message="Type checking timeout",
            )
        except Exception as e:
            return FrontendTestResult(
                test_type="typecheck",
                success=False,
                execution_time=0,
                error_message=str(e),
            )

    def _extract_coverage(self, output: str) -> Optional[float]:
        """Extract test coverage from Jest output"""
        return self.nextjs_integration._extract_coverage_from_output(output)

    def _extract_failed_tests(self, output: str) -> List[str]:
        """Extract failed test names from output"""
        failed_tests = []
        lines = output.split("\n")

        for line in lines:
            if "FAIL" in line or "✕" in line:
                # Extract test file or test name
                if ".test." in line or ".spec." in line:
                    failed_tests.append(line.strip())

        return failed_tests

    async def run_full_tdd_cycle(
        self, component_name: str, test_patterns: List[str] = None
    ) -> Dict[str, bool]:
        """Run a complete TDD cycle for a component"""
        print(f"🚀 Starting full TDD cycle for: {component_name}")

        # Start cycle
        cycle = await self.start_frontend_tdd_cycle(component_name, test_patterns)

        results = {}

        # RED phase
        results["red"] = await self.execute_red_phase()

        if not results["red"]:
            print("❌ RED phase failed - tests did not fail as expected")
            return results

        # GREEN phase
        results["green"] = await self.execute_green_phase()

        if not results["green"]:
            print("❌ GREEN phase failed - could not make tests pass")
            return results

        # REFACTOR phase
        results["refactor"] = await self.execute_refactor_phase()

        if not results["refactor"]:
            print("❌ REFACTOR phase failed - broke existing functionality")
            return results

        print(f"✅ TDD cycle completed successfully for: {component_name}")
        return results

    def generate_tdd_cycle_report(self) -> str:
        """Generate a report of TDD cycles"""
        if not self.tdd_cycles:
            return "No TDD cycles have been executed."

        report = []
        report.append("FXML4 Frontend TDD Cycles Report")
        report.append("=" * 40)
        report.append("")

        for cycle in self.tdd_cycles:
            report.append(f"CYCLE #{cycle.cycle_number}: {cycle.component_name}")
            report.append("-" * 30)

            for phase, result in cycle.results.items():
                status = "✓ PASS" if result.success else "✗ FAIL"
                report.append(
                    f"  {phase.upper()}: {status} ({result.execution_time:.2f}s)"
                )

                if result.coverage_percentage:
                    report.append(f"    Coverage: {result.coverage_percentage:.1f}%")

                if result.failed_tests:
                    report.append(f"    Failed: {len(result.failed_tests)} tests")

                if result.error_message:
                    report.append(f"    Error: {result.error_message}")

            # Cycle success rate
            phase_successes = sum(1 for r in cycle.results.values() if r.success)
            total_phases = len(cycle.results)
            success_rate = phase_successes / total_phases if total_phases > 0 else 0

            report.append(f"  Overall: {success_rate:.1%} success rate")
            report.append("")

        return "\n".join(report)

    async def run_trading_component_tests(self) -> Dict[str, Any]:
        """Run tests specifically for trading UI components"""
        print("Running FXML4 trading component tests...")

        # Define trading-specific components to test
        trading_components = [
            "TradingDashboard",
            "OrderEntry",
            "PortfolioOverview",
            "MarketData",
            "ChartAnalysis",
            "SignalDisplay",
            "RiskMeter",
        ]

        results = {}

        for component in trading_components:
            if self._component_exists(component):
                print(f"Testing trading component: {component}")
                cycle_results = await self.run_full_tdd_cycle(component)
                results[component] = cycle_results
            else:
                print(f"Component {component} not found, skipping...")

        return results

    def _component_exists(self, component_name: str) -> bool:
        """Check if a component exists in the project"""
        component_paths = [
            self.project_path / "src" / "components" / component_name,
            self.project_path / "src" / "components" / "trading" / component_name,
            self.project_path / "src" / "pages" / component_name,
        ]

        return any(
            path.exists() and any(path.glob("*.{ts,tsx}")) for path in component_paths
        )


async def main():
    """Demo usage of frontend test runner"""
    runner = FrontendTestRunner()

    # Setup testing environment
    setup_success = runner.nextjs_integration.setup_frontend_testing()
    if not setup_success:
        print("Failed to set up frontend testing environment")
        return

    # Run trading component tests if frontend exists
    if runner.project_path.exists():
        results = await runner.run_trading_component_tests()

        # Generate and display report
        report = runner.generate_tdd_cycle_report()
        print("\n" + report)

        # Save report
        os.makedirs(".claude-tdd/reports", exist_ok=True)
        with open(".claude-tdd/reports/frontend_tdd_cycles.txt", "w") as f:
            f.write(report)

        print(
            f"\nFrontend TDD report saved to: .claude-tdd/reports/frontend_tdd_cycles.txt"
        )
    else:
        print(f"Frontend directory {runner.project_path} not found")


if __name__ == "__main__":
    asyncio.run(main())
