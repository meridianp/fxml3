#!/usr/bin/env python3
"""
FXML4 Cross-Component Dependency Testing Coordinator
Manages and coordinates testing across component boundaries
"""

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import yaml
from components.component_loader import ComponentConfigLoader


class DependencyType(Enum):
    """Types of dependencies between components"""

    API_CALL = "api_call"
    DATA_FLOW = "data_flow"
    EVENT_SUBSCRIPTION = "event_subscription"
    SHARED_RESOURCE = "shared_resource"
    CONFIGURATION = "configuration"


class TestScope(Enum):
    """Scope of dependency testing"""

    UNIT = "unit"  # Single component
    INTEGRATION = "integration"  # Two components
    END_TO_END = "end_to_end"  # Full system
    CONTRACT = "contract"  # API contracts


@dataclass
class ComponentDependency:
    """Represents a dependency between two components"""

    source: str
    target: str
    dependency_type: DependencyType
    description: str
    test_scope: TestScope
    required_markers: List[str] = field(default_factory=list)
    test_data_requirements: Dict[str, Any] = field(default_factory=dict)
    performance_requirements: Dict[str, float] = field(default_factory=dict)


@dataclass
class DependencyTestResult:
    """Result of a dependency test execution"""

    dependency: ComponentDependency
    success: bool
    execution_time: float
    error_message: Optional[str] = None
    test_output: str = ""
    performance_metrics: Dict[str, float] = field(default_factory=dict)


class DependencyCoordinator:
    """Coordinates cross-component dependency testing"""

    def __init__(self, config_path: str = ".claude-tdd/config.yml"):
        self.config = self._load_config(config_path)
        self.component_loader = ComponentConfigLoader()
        self.dependency_graph = nx.DiGraph()
        self.test_results = []
        self._initialize_dependencies()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load TDD configuration"""
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _initialize_dependencies(self):
        """Initialize the component dependency graph"""
        # FXML4 component dependencies based on architecture
        dependencies = [
            # Core → Elliott Wave (ML models, wave analysis)
            ComponentDependency(
                source="core",
                target="elliott_wave",
                dependency_type=DependencyType.API_CALL,
                description="Core system calls Elliott Wave analysis API",
                test_scope=TestScope.INTEGRATION,
                required_markers=["wave", "ml", "integration"],
                performance_requirements={"response_time": 2.0},
            ),
            # Elliott Wave → Core (Signal generation)
            ComponentDependency(
                source="elliott_wave",
                target="core",
                dependency_type=DependencyType.DATA_FLOW,
                description="Elliott Wave sends trading signals to core",
                test_scope=TestScope.INTEGRATION,
                required_markers=["trading", "signal", "integration"],
                performance_requirements={"latency": 0.5},
            ),
            # Core → Frontend (API endpoints)
            ComponentDependency(
                source="core",
                target="frontend",
                dependency_type=DependencyType.API_CALL,
                description="Frontend calls core API endpoints",
                test_scope=TestScope.CONTRACT,
                required_markers=["api", "ui", "integration"],
                performance_requirements={"response_time": 0.5},
            ),
            # Frontend → Core (User actions)
            ComponentDependency(
                source="frontend",
                target="core",
                dependency_type=DependencyType.EVENT_SUBSCRIPTION,
                description="Frontend sends user actions to core",
                test_scope=TestScope.END_TO_END,
                required_markers=["e2e", "critical", "ui"],
                performance_requirements={"user_action_latency": 0.2},
            ),
            # Shared Database Dependencies
            ComponentDependency(
                source="core",
                target="elliott_wave",
                dependency_type=DependencyType.SHARED_RESOURCE,
                description="Shared TimescaleDB database access",
                test_scope=TestScope.INTEGRATION,
                required_markers=["database", "requires_db"],
                performance_requirements={"query_time": 0.1},
            ),
            # Real-time Data Flow
            ComponentDependency(
                source="elliott_wave",
                target="frontend",
                dependency_type=DependencyType.DATA_FLOW,
                description="Real-time wave analysis updates to frontend",
                test_scope=TestScope.END_TO_END,
                required_markers=["real_time", "wave", "ui"],
                performance_requirements={"update_latency": 1.0},
            ),
        ]

        # Add dependencies to graph
        for dep in dependencies:
            self.dependency_graph.add_edge(
                dep.source, dep.target, dependency=dep, weight=1
            )

    def get_component_dependencies(self, component: str) -> List[ComponentDependency]:
        """Get all dependencies for a specific component"""
        dependencies = []

        # Outgoing dependencies (component depends on others)
        for target in self.dependency_graph.successors(component):
            edge_data = self.dependency_graph.get_edge_data(component, target)
            dependencies.append(edge_data["dependency"])

        # Incoming dependencies (others depend on this component)
        for source in self.dependency_graph.predecessors(component):
            edge_data = self.dependency_graph.get_edge_data(source, component)
            dependencies.append(edge_data["dependency"])

        return dependencies

    def get_test_execution_order(self) -> List[str]:
        """Get optimal test execution order based on dependencies"""
        try:
            # Topological sort for dependency order
            return list(nx.topological_sort(self.dependency_graph))
        except nx.NetworkXError:
            # If cycles exist, use a different approach
            print("Warning: Circular dependencies detected, using alternative order")
            return ["core", "elliott_wave", "frontend"]

    async def execute_dependency_tests(
        self, scope: TestScope = TestScope.INTEGRATION
    ) -> List[DependencyTestResult]:
        """Execute dependency tests for specified scope"""
        results = []
        execution_order = self.get_test_execution_order()

        print(f"Executing {scope.value} dependency tests...")
        print(f"Component order: {' → '.join(execution_order)}")

        for component in execution_order:
            component_deps = [
                dep
                for dep in self.get_component_dependencies(component)
                if dep.test_scope == scope
            ]

            for dep in component_deps:
                result = await self._execute_single_dependency_test(dep)
                results.append(result)
                self.test_results.append(result)

        return results

    async def _execute_single_dependency_test(
        self, dependency: ComponentDependency
    ) -> DependencyTestResult:
        """Execute a single dependency test"""
        start_time = time.time()

        try:
            print(
                f"Testing {dependency.source} → {dependency.target} "
                f"({dependency.dependency_type.value})"
            )

            # Build pytest command for dependency test
            test_command = self._build_dependency_test_command(dependency)

            # Execute test
            result = subprocess.run(
                test_command,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            execution_time = time.time() - start_time
            success = result.returncode == 0

            # Extract performance metrics if available
            performance_metrics = self._extract_performance_metrics(result.stdout)

            return DependencyTestResult(
                dependency=dependency,
                success=success,
                execution_time=execution_time,
                error_message=result.stderr if not success else None,
                test_output=result.stdout,
                performance_metrics=performance_metrics,
            )

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return DependencyTestResult(
                dependency=dependency,
                success=False,
                execution_time=execution_time,
                error_message="Test execution timeout",
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return DependencyTestResult(
                dependency=dependency,
                success=False,
                execution_time=execution_time,
                error_message=str(e),
            )

    def _build_dependency_test_command(
        self, dependency: ComponentDependency
    ) -> List[str]:
        """Build pytest command for testing a specific dependency"""
        cmd = ["python", "-m", "pytest"]

        # Add markers for this dependency
        if dependency.required_markers:
            marker_expr = " and ".join(dependency.required_markers)
            cmd.extend(["-m", marker_expr])

        # Add specific test paths based on dependency type
        test_paths = self._get_dependency_test_paths(dependency)
        cmd.extend(test_paths)

        # Add verbosity and output options
        cmd.extend(["-v", "--tb=short"])

        # Add performance testing if required
        if dependency.performance_requirements:
            cmd.extend(["--durations=10"])

        return cmd

    def _get_dependency_test_paths(self, dependency: ComponentDependency) -> List[str]:
        """Get test paths relevant to a specific dependency"""
        test_paths = []

        if dependency.test_scope == TestScope.CONTRACT:
            test_paths.extend(["tests/api_contracts/", "tests/api/"])
        elif dependency.test_scope == TestScope.INTEGRATION:
            test_paths.extend(["tests/integration/", "tests/functional/"])
        elif dependency.test_scope == TestScope.END_TO_END:
            test_paths.extend(["tests/e2e/", "tests/functional/"])

        # Add component-specific paths
        source_paths = self.component_loader.get_component_test_paths(dependency.source)
        target_paths = self.component_loader.get_component_test_paths(dependency.target)

        test_paths.extend(source_paths)
        test_paths.extend(target_paths)

        # Filter for existing paths
        existing_paths = [path for path in test_paths if Path(path).exists()]

        return existing_paths if existing_paths else ["tests/"]

    def _extract_performance_metrics(self, test_output: str) -> Dict[str, float]:
        """Extract performance metrics from test output"""
        metrics = {}

        # Look for duration information
        if "seconds" in test_output.lower():
            lines = test_output.split("\n")
            for line in lines:
                if "duration" in line.lower() or "time" in line.lower():
                    # Simple regex-like parsing for time values
                    words = line.split()
                    for i, word in enumerate(words):
                        if (
                            "s" in word
                            and word.replace(".", "").replace("s", "").isdigit()
                        ):
                            try:
                                duration = float(word.replace("s", ""))
                                metrics["test_duration"] = duration
                            except ValueError:
                                pass

        return metrics

    def analyze_dependency_health(self) -> Dict[str, Any]:
        """Analyze the health of component dependencies"""
        if not self.test_results:
            return {"status": "no_tests_executed"}

        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        failed_tests = total_tests - successful_tests

        # Calculate average execution times by dependency type
        avg_times_by_type = {}
        for dep_type in DependencyType:
            type_results = [
                r for r in self.test_results if r.dependency.dependency_type == dep_type
            ]
            if type_results:
                avg_time = sum(r.execution_time for r in type_results) / len(
                    type_results
                )
                avg_times_by_type[dep_type.value] = avg_time

        # Identify problematic dependencies
        problematic_deps = [
            {
                "source": r.dependency.source,
                "target": r.dependency.target,
                "type": r.dependency.dependency_type.value,
                "error": r.error_message,
            }
            for r in self.test_results
            if not r.success
        ]

        return {
            "total_dependencies_tested": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": successful_tests / total_tests if total_tests > 0 else 0,
            "average_execution_times": avg_times_by_type,
            "problematic_dependencies": problematic_deps,
            "overall_health": (
                "healthy"
                if failed_tests == 0
                else "degraded" if failed_tests < total_tests * 0.2 else "critical"
            ),
        }

    def generate_dependency_report(self, output_file: str = None) -> str:
        """Generate a comprehensive dependency test report"""
        health = self.analyze_dependency_health()

        report = []
        report.append("FXML4 Component Dependency Test Report")
        report.append("=" * 50)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")

        # Summary
        report.append("SUMMARY")
        report.append("-" * 20)
        report.append(
            f"Total Dependencies Tested: {health['total_dependencies_tested']}"
        )
        report.append(f"Successful Tests: {health['successful_tests']}")
        report.append(f"Failed Tests: {health['failed_tests']}")
        report.append(f"Success Rate: {health['success_rate']:.1%}")
        report.append(f"Overall Health: {health['overall_health'].upper()}")
        report.append("")

        # Performance Summary
        if health["average_execution_times"]:
            report.append("PERFORMANCE BY DEPENDENCY TYPE")
            report.append("-" * 35)
            for dep_type, avg_time in health["average_execution_times"].items():
                report.append(f"  {dep_type}: {avg_time:.2f}s average")
            report.append("")

        # Detailed Results
        report.append("DETAILED RESULTS")
        report.append("-" * 20)
        for result in self.test_results:
            status = "✓ PASS" if result.success else "✗ FAIL"
            report.append(
                f"{status} {result.dependency.source} → {result.dependency.target} "
                f"({result.dependency.dependency_type.value}) - {result.execution_time:.2f}s"
            )
            if not result.success and result.error_message:
                report.append(f"      Error: {result.error_message}")

        report_text = "\n".join(report)

        if output_file:
            with open(output_file, "w") as f:
                f.write(report_text)
            print(f"Dependency report saved to: {output_file}")

        return report_text

    async def run_full_dependency_analysis(self) -> Dict[str, Any]:
        """Run complete dependency analysis across all scopes"""
        print("Starting full FXML4 dependency analysis...")

        all_results = {}

        # Test each scope
        for scope in TestScope:
            print(f"\n--- Testing {scope.value.upper()} dependencies ---")
            results = await self.execute_dependency_tests(scope)
            all_results[scope.value] = [
                {
                    "source": r.dependency.source,
                    "target": r.dependency.target,
                    "success": r.success,
                    "execution_time": r.execution_time,
                }
                for r in results
            ]

        # Generate comprehensive report
        health_analysis = self.analyze_dependency_health()
        report = self.generate_dependency_report(
            ".claude-tdd/reports/dependency_analysis.txt"
        )

        return {
            "test_results": all_results,
            "health_analysis": health_analysis,
            "report_location": ".claude-tdd/reports/dependency_analysis.txt",
        }


async def main():
    """Demo usage of dependency coordinator"""
    coordinator = DependencyCoordinator()

    # Run integration tests
    print("Testing component dependencies...")
    results = await coordinator.execute_dependency_tests(TestScope.INTEGRATION)

    # Analyze results
    health = coordinator.analyze_dependency_health()
    print(f"\nDependency Health: {health['overall_health']}")
    print(f"Success Rate: {health['success_rate']:.1%}")

    # Generate report
    report = coordinator.generate_dependency_report()
    print("\n" + report)


if __name__ == "__main__":
    asyncio.run(main())
