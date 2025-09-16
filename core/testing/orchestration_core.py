"""Test execution orchestration and dependency management."""

import asyncio
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TestNode:
    """Represents a test with its dependencies."""

    name: str
    dependencies: List[str]
    resources: List[str]
    estimated_duration: float = 1.0
    priority: int = 0


@dataclass
class ExecutionBatch:
    """Represents a batch of tests that can run in parallel."""

    tests: List[str]
    resources_needed: Set[str]
    estimated_duration: float


@dataclass
class ExecutionPlan:
    """Complete execution plan with batches."""

    batches: List[ExecutionBatch]
    total_estimated_duration: float
    resource_usage: Dict[str, int]


class DependencyAwareTestRunner:
    """Executes tests based on dependency relationships."""

    def __init__(self):
        self.tests: Dict[str, TestNode] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}

    def register_test(
        self,
        test_name: str,
        dependencies: List[str] = None,
        resources: List[str] = None,
        estimated_duration: float = 1.0,
    ):
        """Register a test with its dependencies."""
        dependencies = dependencies or []
        resources = resources or []

        self.tests[test_name] = TestNode(
            name=test_name,
            dependencies=dependencies,
            resources=resources,
            estimated_duration=estimated_duration,
        )

        # Build dependency graph
        self.dependency_graph[test_name] = set(dependencies)

    def get_execution_order(self) -> List[str]:
        """Get topologically sorted execution order."""
        # Kahn's algorithm for topological sorting
        in_degree = {test: 0 for test in self.tests}

        # Calculate in-degrees
        for test, deps in self.dependency_graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[test] += 1

        # Start with tests that have no dependencies
        queue = [test for test, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            # Reduce in-degree for dependent tests
            for test, deps in self.dependency_graph.items():
                if current in deps:
                    in_degree[test] -= 1
                    if in_degree[test] == 0:
                        queue.append(test)

        if len(result) != len(self.tests):
            raise ValueError("Circular dependency detected in tests")

        return result

    def validate_dependencies(self) -> List[str]:
        """Validate that all dependencies exist."""
        errors = []

        for test_name, test_node in self.tests.items():
            for dep in test_node.dependencies:
                if dep not in self.tests:
                    errors.append(
                        f"Test '{test_name}' depends on non-existent test '{dep}'"
                    )

        return errors


class ParallelTestExecutor:
    """Executes tests in parallel with resource management."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.tests: Dict[str, TestNode] = {}
        self.resource_constraints: Dict[str, int] = {}
        self.active_resources: Dict[str, int] = {}

    def register_test(
        self,
        test_name: str,
        resources: List[str] = None,
        estimated_duration: float = 1.0,
        priority: int = 0,
    ):
        """Register a test with its resource requirements."""
        resources = resources or []

        self.tests[test_name] = TestNode(
            name=test_name,
            dependencies=[],
            resources=resources,
            estimated_duration=estimated_duration,
            priority=priority,
        )

    def register_resource_constraint(self, resource_name: str, max_concurrent: int):
        """Register a constraint on concurrent resource usage."""
        self.resource_constraints[resource_name] = max_concurrent
        self.active_resources[resource_name] = 0

    def create_execution_plan(self) -> ExecutionPlan:
        """Create an execution plan respecting resource constraints."""
        tests = sorted(
            self.tests.values(), key=lambda x: (-x.priority, x.estimated_duration)
        )
        batches = []
        remaining_tests = tests.copy()

        while remaining_tests:
            batch_tests = []
            batch_resources = set()
            resource_usage = dict(self.active_resources)

            # Try to add tests to current batch
            for test in remaining_tests.copy():
                can_add = True

                # Check resource constraints
                for resource in test.resources:
                    current_usage = resource_usage.get(resource, 0)
                    max_allowed = self.resource_constraints.get(resource, float("inf"))

                    if current_usage >= max_allowed:
                        can_add = False
                        break

                if can_add:
                    batch_tests.append(test.name)
                    batch_resources.update(test.resources)

                    # Update resource usage
                    for resource in test.resources:
                        resource_usage[resource] = resource_usage.get(resource, 0) + 1

                    remaining_tests.remove(test)

            # Create batch
            if batch_tests:
                batch_duration = max(
                    self.tests[test_name].estimated_duration
                    for test_name in batch_tests
                )

                batches.append(
                    ExecutionBatch(
                        tests=batch_tests,
                        resources_needed=batch_resources,
                        estimated_duration=batch_duration,
                    )
                )
            else:
                # Deadlock prevention: force at least one test into batch
                if remaining_tests:
                    forced_test = remaining_tests.pop(0)
                    batches.append(
                        ExecutionBatch(
                            tests=[forced_test.name],
                            resources_needed=set(forced_test.resources),
                            estimated_duration=forced_test.estimated_duration,
                        )
                    )

        total_duration = sum(batch.estimated_duration for batch in batches)
        max_resource_usage = {}

        for resource in self.resource_constraints:
            max_usage = (
                max(
                    len(
                        [
                            test
                            for test in batch.tests
                            if resource in self.tests[test].resources
                        ]
                    )
                    for batch in batches
                )
                if batches
                else 0
            )
            max_resource_usage[resource] = max_usage

        return ExecutionPlan(
            batches=batches,
            total_estimated_duration=total_duration,
            resource_usage=max_resource_usage,
        )

    async def execute_batch(self, batch: ExecutionBatch) -> Dict[str, Any]:
        """Execute a batch of tests in parallel."""
        results = {}

        async def execute_test(test_name: str) -> Tuple[str, Any]:
            # Mock test execution
            test = self.tests[test_name]
            await asyncio.sleep(test.estimated_duration / 10)  # Scaled for demo
            return test_name, {"status": "passed", "duration": test.estimated_duration}

        # Execute tests in parallel
        tasks = [execute_test(test_name) for test_name in batch.tests]
        completed = await asyncio.gather(*tasks)

        for test_name, result in completed:
            results[test_name] = result

        return results
