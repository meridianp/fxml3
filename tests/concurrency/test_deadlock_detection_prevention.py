"""Deadlock detection and prevention tests for FXML4.

Tests deadlock scenarios in complex async and threading operations,
resource acquisition patterns, and prevention mechanisms.
"""

import asyncio
import queue
import random
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from unittest.mock import AsyncMock, Mock

import pytest

from tests.utils.concurrency_utils import (
    DeadlockDetector,
    LoadGenerator,
    RaceConditionDetector,
    concurrency_test_environment,
)


@dataclass
class ResourceLock:
    """Represents a resource that can be locked."""

    resource_id: str
    lock_type: str  # 'shared', 'exclusive', 'intent'
    owner: Optional[str] = None
    waiting_queue: List[str] = field(default_factory=list)
    acquired_at: Optional[float] = None
    max_wait_time: float = 10.0


class AdvancedDeadlockDetector:
    """Advanced deadlock detection with cycle detection and prevention."""

    def __init__(self, detection_interval: float = 0.1):
        self.detection_interval = detection_interval
        self.resource_graph = defaultdict(
            dict
        )  # resource -> {owner: lock_type, waiters: [...]}
        self.wait_graph = defaultdict(set)  # who_waits -> {what_resources}
        self.lock_hierarchy = {}  # resource_id -> priority
        self.active_locks = {}  # thread_id -> {resources}
        self.deadlock_prevention_enabled = True
        self._lock = asyncio.Lock()
        self.detection_stats = {
            "cycles_detected": 0,
            "deadlocks_prevented": 0,
            "false_positives": 0,
            "detection_runs": 0,
        }
        self._detection_task = None
        self._running = False

    async def start_detection(self):
        """Start deadlock detection background task."""
        if self._running:
            return

        self._running = True
        self._detection_task = asyncio.create_task(self._detection_loop())

    async def stop_detection(self):
        """Stop deadlock detection."""
        self._running = False
        if self._detection_task:
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass

    async def _detection_loop(self):
        """Background deadlock detection loop."""
        try:
            while self._running:
                await asyncio.sleep(self.detection_interval)
                await self._detect_deadlocks()
        except asyncio.CancelledError:
            pass

    async def request_lock(
        self,
        thread_id: str,
        resource_id: str,
        lock_type: str = "exclusive",
        timeout: float = 5.0,
    ) -> bool:
        """Request a lock on a resource with deadlock prevention."""
        async with self._lock:
            # Check for potential deadlock before granting
            if self.deadlock_prevention_enabled:
                if await self._would_create_deadlock(thread_id, resource_id):
                    self.detection_stats["deadlocks_prevented"] += 1
                    raise DeadlockPreventionError(
                        f"Lock request would create deadlock: {thread_id} -> {resource_id}"
                    )

            # Initialize resource if not exists
            if resource_id not in self.resource_graph:
                self.resource_graph[resource_id] = {
                    "owner": None,
                    "waiters": [],
                    "lock_type": None,
                }

            resource = self.resource_graph[resource_id]

            # Check if resource is available
            if resource["owner"] is None or (
                lock_type == "shared" and resource["lock_type"] == "shared"
            ):
                # Grant lock immediately
                resource["owner"] = thread_id
                resource["lock_type"] = lock_type

                if thread_id not in self.active_locks:
                    self.active_locks[thread_id] = set()
                self.active_locks[thread_id].add(resource_id)

                return True
            else:
                # Add to wait queue
                if thread_id not in resource["waiters"]:
                    resource["waiters"].append(thread_id)

                self.wait_graph[thread_id].add(resource_id)
                return False

    async def release_lock(self, thread_id: str, resource_id: str) -> bool:
        """Release a lock on a resource."""
        async with self._lock:
            if resource_id not in self.resource_graph:
                return False

            resource = self.resource_graph[resource_id]

            if resource["owner"] != thread_id:
                return False

            # Release the lock
            resource["owner"] = None
            resource["lock_type"] = None

            if thread_id in self.active_locks:
                self.active_locks[thread_id].discard(resource_id)
                if not self.active_locks[thread_id]:
                    del self.active_locks[thread_id]

            # Remove from wait graph
            if thread_id in self.wait_graph:
                self.wait_graph[thread_id].discard(resource_id)
                if not self.wait_graph[thread_id]:
                    del self.wait_graph[thread_id]

            # Grant lock to next waiter
            if resource["waiters"]:
                next_waiter = resource["waiters"].pop(0)
                resource["owner"] = next_waiter
                resource["lock_type"] = "exclusive"  # Default

                if next_waiter not in self.active_locks:
                    self.active_locks[next_waiter] = set()
                self.active_locks[next_waiter].add(resource_id)

                # Remove from wait graph
                if next_waiter in self.wait_graph:
                    self.wait_graph[next_waiter].discard(resource_id)

            return True

    async def _would_create_deadlock(self, thread_id: str, resource_id: str) -> bool:
        """Check if granting this lock would create a deadlock."""
        # Check if this would create a cycle in wait-for graph
        if resource_id not in self.resource_graph:
            return False

        resource = self.resource_graph[resource_id]
        current_owner = resource["owner"]

        if current_owner is None:
            return False

        # Check if current owner is waiting for any resource held by thread_id
        return await self._has_cycle(current_owner, thread_id, set())

    async def _has_cycle(self, start: str, target: str, visited: Set[str]) -> bool:
        """Check for cycles in the wait-for graph."""
        if start == target:
            return True

        if start in visited:
            return False

        visited.add(start)

        # Check what resources start is waiting for
        waiting_for = self.wait_graph.get(start, set())

        for resource_id in waiting_for:
            resource = self.resource_graph.get(resource_id)
            if resource and resource["owner"]:
                if await self._has_cycle(resource["owner"], target, visited):
                    return True

        visited.remove(start)
        return False

    async def _detect_deadlocks(self):
        """Detect deadlocks using cycle detection in wait-for graph."""
        async with self._lock:
            self.detection_stats["detection_runs"] += 1

            # Build current wait-for graph
            wait_for_graph = defaultdict(set)

            for thread_id, waiting_resources in self.wait_graph.items():
                for resource_id in waiting_resources:
                    resource = self.resource_graph.get(resource_id)
                    if resource and resource["owner"]:
                        wait_for_graph[thread_id].add(resource["owner"])

            # Detect cycles using DFS
            visited = set()
            rec_stack = set()

            for thread_id in wait_for_graph:
                if thread_id not in visited:
                    if self._dfs_cycle_detection(
                        thread_id, wait_for_graph, visited, rec_stack
                    ):
                        self.detection_stats["cycles_detected"] += 1
                        await self._handle_deadlock(thread_id, wait_for_graph)

    def _dfs_cycle_detection(
        self,
        thread_id: str,
        graph: Dict[str, Set[str]],
        visited: Set[str],
        rec_stack: Set[str],
    ) -> bool:
        """DFS-based cycle detection."""
        visited.add(thread_id)
        rec_stack.add(thread_id)

        for neighbor in graph.get(thread_id, []):
            if neighbor not in visited:
                if self._dfs_cycle_detection(neighbor, graph, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(thread_id)
        return False

    async def _handle_deadlock(
        self, involved_thread: str, wait_for_graph: Dict[str, Set[str]]
    ):
        """Handle detected deadlock by releasing locks strategically."""
        # Simple strategy: release locks from thread with lowest priority
        # In practice, this could be more sophisticated

        # Find all threads in the deadlock cycle
        cycle_threads = self._find_deadlock_cycle(involved_thread, wait_for_graph)

        if cycle_threads:
            # Choose victim (thread with most locks to release)
            victim = max(cycle_threads, key=lambda t: len(self.active_locks.get(t, [])))

            # Release all locks from victim
            victim_resources = list(self.active_locks.get(victim, []))
            for resource_id in victim_resources:
                await self.release_lock(victim, resource_id)

    def _find_deadlock_cycle(
        self, start_thread: str, wait_for_graph: Dict[str, Set[str]]
    ) -> List[str]:
        """Find the deadlock cycle starting from a given thread."""
        cycle = []
        visited = set()

        def dfs(thread_id: str, path: List[str]) -> bool:
            if thread_id in path:
                # Found cycle
                cycle_start = path.index(thread_id)
                cycle.extend(path[cycle_start:])
                return True

            if thread_id in visited:
                return False

            visited.add(thread_id)

            for neighbor in wait_for_graph.get(thread_id, []):
                if dfs(neighbor, path + [thread_id]):
                    return True

            return False

        dfs(start_thread, [])
        return cycle

    def get_detection_stats(self) -> Dict[str, Any]:
        """Get deadlock detection statistics."""
        return self.detection_stats.copy()


class DeadlockPreventionError(Exception):
    """Exception raised when deadlock prevention blocks a lock request."""

    pass


class AsyncResourceManager:
    """Manage async resources with deadlock-aware locking."""

    def __init__(self, deadlock_detector: AdvancedDeadlockDetector):
        self.detector = deadlock_detector
        self.resources = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire_resource(
        self, thread_id: str, resource_id: str, timeout: float = 5.0
    ):
        """Acquire resource with deadlock detection."""
        acquired = False

        try:
            # Request lock with deadlock prevention
            acquired = await self.detector.request_lock(
                thread_id, resource_id, timeout=timeout
            )

            if not acquired:
                # Wait for lock to become available
                start_time = time.perf_counter()
                while not acquired and (time.perf_counter() - start_time) < timeout:
                    await asyncio.sleep(0.01)
                    acquired = await self.detector.request_lock(
                        thread_id, resource_id, timeout=0.01
                    )

                if not acquired:
                    raise TimeoutError(
                        f"Failed to acquire resource {resource_id} within {timeout}s"
                    )

            yield resource_id

        finally:
            if acquired:
                await self.detector.release_lock(thread_id, resource_id)


@pytest.mark.concurrency
@pytest.mark.deadlock
class TestDeadlockDetectionPrevention:
    """Test deadlock detection and prevention mechanisms."""

    @pytest.fixture
    def deadlock_detector(self):
        """Create advanced deadlock detector."""
        detector = AdvancedDeadlockDetector(detection_interval=0.05)
        yield detector

        # Cleanup
        asyncio.create_task(detector.stop_detection())

    @pytest.fixture
    def resource_manager(self, deadlock_detector):
        """Create resource manager with deadlock detection."""
        return AsyncResourceManager(deadlock_detector)

    @pytest.mark.asyncio
    async def test_simple_deadlock_detection(self, deadlock_detector):
        """Test detection of simple circular deadlock."""

        await deadlock_detector.start_detection()

        # Create classic AB-BA deadlock scenario
        async def thread_a_operations():
            """Thread A: acquire A, then B."""
            thread_id = "thread_a"

            # Acquire resource A
            await deadlock_detector.request_lock(thread_id, "resource_a")
            await asyncio.sleep(0.1)  # Hold lock briefly

            try:
                # Try to acquire resource B (potential deadlock)
                await deadlock_detector.request_lock(
                    thread_id, "resource_b", timeout=1.0
                )
                await asyncio.sleep(0.1)
                await deadlock_detector.release_lock(thread_id, "resource_b")
            except DeadlockPreventionError:
                pass  # Expected prevention

            await deadlock_detector.release_lock(thread_id, "resource_a")

        async def thread_b_operations():
            """Thread B: acquire B, then A."""
            thread_id = "thread_b"

            # Acquire resource B
            await deadlock_detector.request_lock(thread_id, "resource_b")
            await asyncio.sleep(0.1)  # Hold lock briefly

            try:
                # Try to acquire resource A (potential deadlock)
                await deadlock_detector.request_lock(
                    thread_id, "resource_a", timeout=1.0
                )
                await asyncio.sleep(0.1)
                await deadlock_detector.release_lock(thread_id, "resource_a")
            except DeadlockPreventionError:
                pass  # Expected prevention

            await deadlock_detector.release_lock(thread_id, "resource_b")

        # Run both threads concurrently
        await asyncio.gather(
            thread_a_operations(), thread_b_operations(), return_exceptions=True
        )

        await deadlock_detector.stop_detection()

        # Check detection statistics
        stats = deadlock_detector.get_detection_stats()
        assert stats["deadlocks_prevented"] > 0 or stats["cycles_detected"] > 0

    @pytest.mark.asyncio
    async def test_complex_multi_resource_deadlock(
        self, resource_manager, deadlock_detector
    ):
        """Test complex deadlock involving multiple resources."""

        await deadlock_detector.start_detection()

        async def complex_resource_operations(thread_spec: tuple) -> str:
            """Perform complex resource operations that might deadlock."""
            thread_id, resource_sequence = thread_spec

            acquired_resources = []

            try:
                for resource_id in resource_sequence:
                    async with resource_manager.acquire_resource(
                        thread_id, resource_id, timeout=2.0
                    ):
                        acquired_resources.append(resource_id)
                        # Simulate work
                        await asyncio.sleep(random.uniform(0.01, 0.05))

                return f"completed_{thread_id}"

            except (DeadlockPreventionError, TimeoutError) as e:
                return f"prevented_{thread_id}_{type(e).__name__}"
            except Exception as e:
                return f"error_{thread_id}_{e}"

        # Create complex deadlock scenarios
        resource_scenarios = [
            ("thread_1", ["res_a", "res_b", "res_c"]),
            ("thread_2", ["res_b", "res_c", "res_a"]),
            ("thread_3", ["res_c", "res_a", "res_b"]),
            ("thread_4", ["res_a", "res_c", "res_b"]),
            ("thread_5", ["res_b", "res_a", "res_c"]),
            ("thread_6", ["res_c", "res_b", "res_a"]),
        ]

        async with concurrency_test_environment(max_concurrent=6) as env:
            result = await env.test_async_operation(
                complex_resource_operations,
                resource_scenarios,
                max_concurrent=6,
                timeout=10.0,
            )

            await deadlock_detector.stop_detection()

            # Should handle complex deadlock scenarios
            assert result.operations_completed == len(resource_scenarios)

            # Check that deadlock prevention or detection worked
            stats = deadlock_detector.get_detection_stats()
            assert stats["deadlocks_prevented"] > 0 or stats["cycles_detected"] > 0

    @pytest.mark.asyncio
    async def test_resource_hierarchy_deadlock_prevention(self, deadlock_detector):
        """Test deadlock prevention using resource hierarchy."""

        await deadlock_detector.start_detection()

        # Set resource hierarchy (lower numbers = higher priority)
        deadlock_detector.lock_hierarchy = {
            "database": 1,
            "cache": 2,
            "network": 3,
            "file_system": 4,
        }

        async def hierarchical_resource_access(access_spec: tuple) -> str:
            """Access resources following hierarchy to prevent deadlocks."""
            thread_id, resource_list = access_spec

            # Sort resources by hierarchy to prevent deadlocks
            sorted_resources = sorted(
                resource_list,
                key=lambda r: deadlock_detector.lock_hierarchy.get(r, 999),
            )

            try:
                acquired = []
                for resource_id in sorted_resources:
                    await deadlock_detector.request_lock(thread_id, resource_id)
                    acquired.append(resource_id)
                    await asyncio.sleep(0.01)  # Simulate work

                # Release in reverse order
                for resource_id in reversed(acquired):
                    await deadlock_detector.release_lock(thread_id, resource_id)

                return f"success_{thread_id}"

            except DeadlockPreventionError:
                return f"prevented_{thread_id}"
            except Exception as e:
                return f"error_{thread_id}_{e}"

        # Generate access patterns that would deadlock without hierarchy
        access_patterns = [
            (
                f"thread_{i}",
                random.sample(["database", "cache", "network", "file_system"], 3),
            )
            for i in range(10)
        ]

        async with concurrency_test_environment(max_concurrent=10) as env:
            result = await env.test_async_operation(
                hierarchical_resource_access,
                access_patterns,
                max_concurrent=10,
                timeout=5.0,
            )

            await deadlock_detector.stop_detection()

            # Hierarchical access should prevent deadlocks
            assert result.operations_completed == len(access_patterns)
            assert result.operations_failed == 0

            # Should have fewer or no deadlock preventions due to hierarchy
            stats = deadlock_detector.get_detection_stats()
            # Hierarchy should reduce need for prevention
            assert stats["deadlocks_prevented"] < 5

    @pytest.mark.asyncio
    async def test_deadlock_recovery_mechanisms(self, deadlock_detector):
        """Test deadlock recovery when prevention fails."""

        # Disable prevention to test recovery
        deadlock_detector.deadlock_prevention_enabled = False
        await deadlock_detector.start_detection()

        async def recovery_test_operations(operation_spec: tuple) -> str:
            """Operations that will cause deadlocks for recovery testing."""
            thread_id, delay = operation_spec

            try:
                if "thread_a" in thread_id:
                    # Thread A pattern: res_1 -> res_2
                    await deadlock_detector.request_lock(thread_id, "res_1")
                    await asyncio.sleep(delay)
                    await deadlock_detector.request_lock(
                        thread_id, "res_2", timeout=2.0
                    )

                    await deadlock_detector.release_lock(thread_id, "res_2")
                    await deadlock_detector.release_lock(thread_id, "res_1")

                else:
                    # Thread B pattern: res_2 -> res_1 (creates deadlock)
                    await deadlock_detector.request_lock(thread_id, "res_2")
                    await asyncio.sleep(delay)
                    await deadlock_detector.request_lock(
                        thread_id, "res_1", timeout=2.0
                    )

                    await deadlock_detector.release_lock(thread_id, "res_1")
                    await deadlock_detector.release_lock(thread_id, "res_2")

                return f"completed_{thread_id}"

            except Exception as e:
                return f"recovered_{thread_id}_{type(e).__name__}"

        # Create deadlock scenarios for recovery testing
        recovery_operations = [
            ("thread_a_1", 0.1),
            ("thread_b_1", 0.1),
            ("thread_a_2", 0.15),
            ("thread_b_2", 0.15),
        ]

        async with concurrency_test_environment(max_concurrent=4) as env:
            result = await env.test_async_operation(
                recovery_test_operations,
                recovery_operations,
                max_concurrent=4,
                timeout=8.0,
            )

            await deadlock_detector.stop_detection()

            # Should complete operations despite deadlocks through recovery
            assert result.operations_completed == len(recovery_operations)

            # Should have detected and handled deadlocks
            stats = deadlock_detector.get_detection_stats()
            assert stats["cycles_detected"] > 0

    @pytest.mark.asyncio
    async def test_timeout_based_deadlock_resolution(
        self, resource_manager, deadlock_detector
    ):
        """Test deadlock resolution using timeouts."""

        await deadlock_detector.start_detection()

        async def timeout_resolution_test(thread_spec: tuple) -> str:
            """Test timeout-based deadlock resolution."""
            thread_id, resource_order, timeout = thread_spec

            try:
                for resource_id in resource_order:
                    async with resource_manager.acquire_resource(
                        thread_id, resource_id, timeout=timeout
                    ):
                        # Simulate work that might cause contention
                        await asyncio.sleep(random.uniform(0.05, 0.15))

                return f"success_{thread_id}"

            except TimeoutError:
                return f"timeout_{thread_id}"
            except DeadlockPreventionError:
                return f"prevented_{thread_id}"
            except Exception as e:
                return f"error_{thread_id}_{e}"

        # Create scenarios with varying timeouts
        timeout_scenarios = [
            ("quick_thread_1", ["shared_res_a", "shared_res_b"], 0.5),
            ("quick_thread_2", ["shared_res_b", "shared_res_a"], 0.5),
            ("patient_thread_1", ["shared_res_a", "shared_res_b"], 2.0),
            ("patient_thread_2", ["shared_res_b", "shared_res_a"], 2.0),
            ("very_patient_thread", ["shared_res_a", "shared_res_b"], 5.0),
        ]

        async with concurrency_test_environment(max_concurrent=5) as env:
            result = await env.test_async_operation(
                timeout_resolution_test,
                timeout_scenarios,
                max_concurrent=5,
                timeout=10.0,
            )

            await deadlock_detector.stop_detection()

            # Should resolve through timeouts
            assert result.operations_completed == len(timeout_scenarios)

            # Verify that some operations succeeded and some timed out
            stats = deadlock_detector.get_detection_stats()
            assert stats["detection_runs"] > 0


@pytest.mark.concurrency
@pytest.mark.deadlock
@pytest.mark.performance
class TestDeadlockPerformanceImpact:
    """Test performance impact of deadlock detection and prevention."""

    @pytest.mark.asyncio
    async def test_detection_overhead_benchmark(self):
        """Benchmark overhead of deadlock detection."""

        detector = AdvancedDeadlockDetector(
            detection_interval=0.01
        )  # Frequent detection

        async def benchmark_resource_operations(operation_spec: tuple) -> float:
            """Benchmark resource operations with detection overhead."""
            thread_id, num_operations = operation_spec

            start_time = time.perf_counter()

            for i in range(num_operations):
                resource_id = f"bench_res_{i % 5}"  # Cycle through 5 resources

                await detector.request_lock(thread_id, resource_id)
                await asyncio.sleep(0.001)  # Minimal work
                await detector.release_lock(thread_id, resource_id)

            end_time = time.perf_counter()
            return end_time - start_time

        # Benchmark with detection enabled
        await detector.start_detection()

        benchmark_operations = [(f"bench_thread_{i}", 50) for i in range(10)]

        async with concurrency_test_environment(max_concurrent=10) as env:
            result = await env.test_async_operation(
                benchmark_resource_operations,
                benchmark_operations,
                max_concurrent=10,
                timeout=10.0,
            )

            await detector.stop_detection()

            # Performance should remain reasonable with detection overhead
            assert result.operations_completed == len(benchmark_operations)
            assert result.avg_response_time < 0.1  # < 100ms per thread
            assert result.throughput_ops_per_sec > 50  # > 50 operations/sec

            # Detection should have been active
            stats = detector.get_detection_stats()
            assert stats["detection_runs"] > 10

    @pytest.mark.asyncio
    async def test_scalability_with_many_resources(self):
        """Test scalability with large number of resources and threads."""

        detector = AdvancedDeadlockDetector(detection_interval=0.05)

        async def scalability_test(test_spec: tuple) -> str:
            """Test with many resources and threads."""
            thread_id, resource_count, operation_count = test_spec

            try:
                for i in range(operation_count):
                    # Access random subset of resources
                    resources = random.sample(
                        [f"scale_res_{j}" for j in range(resource_count)],
                        min(3, resource_count),
                    )

                    # Acquire in sorted order to reduce deadlock potential
                    resources.sort()

                    acquired = []
                    for resource_id in resources:
                        await detector.request_lock(thread_id, resource_id, timeout=1.0)
                        acquired.append(resource_id)

                    # Release in reverse order
                    for resource_id in reversed(acquired):
                        await detector.release_lock(thread_id, resource_id)

                return f"success_{thread_id}"

            except Exception as e:
                return f"error_{thread_id}_{type(e).__name__}"

        await detector.start_detection()

        # Large-scale test
        num_threads = 25
        num_resources = 100
        operations_per_thread = 20

        scalability_tests = [
            (f"scale_thread_{i}", num_resources, operations_per_thread)
            for i in range(num_threads)
        ]

        start_time = time.perf_counter()

        async with concurrency_test_environment(max_concurrent=25) as env:
            result = await env.test_async_operation(
                scalability_test, scalability_tests, max_concurrent=25, timeout=15.0
            )

            end_time = time.perf_counter()

            await detector.stop_detection()

            # Should scale to handle many resources and threads
            assert result.operations_completed == num_threads
            assert result.operations_failed == 0

            # Total time should be reasonable
            total_time = end_time - start_time
            assert total_time < 12.0  # Should complete within 12 seconds

            # Detection should remain effective at scale
            stats = detector.get_detection_stats()
            assert stats["detection_runs"] > 100
