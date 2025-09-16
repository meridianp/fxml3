"""Concurrency testing utilities for FXML4.

This module provides comprehensive utilities for testing concurrent operations,
race conditions, deadlock detection, and async performance in financial trading systems.
"""

import asyncio
import logging
import queue
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class ConcurrencyTestResult:
    """Results from concurrency testing."""

    test_name: str
    duration: float
    operations_completed: int
    operations_failed: int
    race_conditions_detected: int
    deadlocks_detected: int
    max_concurrent: int
    avg_response_time: float
    throughput_ops_per_sec: float
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.operations_completed + self.operations_failed
        return self.operations_completed / total if total > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        return 1.0 - self.success_rate


class RaceConditionDetector:
    """Detect race conditions in concurrent operations."""

    def __init__(self):
        self.shared_state = {}
        self.access_log = []
        self.lock = threading.Lock()
        self.race_conditions = []

    def access_shared_resource(
        self, resource_id: str, operation: str, value: Any = None
    ):
        """Log access to shared resource."""
        timestamp = time.perf_counter()
        thread_id = threading.get_ident()

        with self.lock:
            self.access_log.append(
                {
                    "timestamp": timestamp,
                    "thread_id": thread_id,
                    "resource_id": resource_id,
                    "operation": operation,
                    "value": value,
                }
            )

            # Update shared state
            if operation == "write":
                old_value = self.shared_state.get(resource_id)
                self.shared_state[resource_id] = value

                # Check for potential race condition
                self._check_race_condition(
                    resource_id, old_value, value, timestamp, thread_id
                )

    def _check_race_condition(
        self,
        resource_id: str,
        old_value: Any,
        new_value: Any,
        timestamp: float,
        thread_id: int,
    ):
        """Check for race condition patterns."""
        # Look for concurrent writes within a small time window
        time_window = 0.001  # 1ms window

        recent_writes = [
            entry
            for entry in self.access_log
            if (
                entry["resource_id"] == resource_id
                and entry["operation"] == "write"
                and abs(entry["timestamp"] - timestamp) < time_window
                and entry["thread_id"] != thread_id
            )
        ]

        if recent_writes:
            race_condition = {
                "resource_id": resource_id,
                "timestamp": timestamp,
                "competing_threads": [entry["thread_id"] for entry in recent_writes]
                + [thread_id],
                "values": [entry["value"] for entry in recent_writes] + [new_value],
            }
            self.race_conditions.append(race_condition)

    def get_race_conditions(self) -> List[Dict[str, Any]]:
        """Get detected race conditions."""
        with self.lock:
            return self.race_conditions.copy()

    def reset(self):
        """Reset detector state."""
        with self.lock:
            self.shared_state.clear()
            self.access_log.clear()
            self.race_conditions.clear()


class DeadlockDetector:
    """Detect potential deadlocks in async and threaded operations."""

    def __init__(self):
        self.lock_graph = {}  # resource -> waiting_threads
        self.thread_locks = {}  # thread -> held_locks
        self.lock = threading.Lock()
        self.deadlocks = []

    def acquire_lock(self, thread_id: str, resource_id: str):
        """Record lock acquisition."""
        with self.lock:
            if thread_id not in self.thread_locks:
                self.thread_locks[thread_id] = set()

            # Check for potential deadlock before acquiring
            if self._would_create_deadlock(thread_id, resource_id):
                deadlock_info = {
                    "timestamp": time.perf_counter(),
                    "thread_id": thread_id,
                    "requested_resource": resource_id,
                    "held_locks": self.thread_locks[thread_id].copy(),
                    "lock_graph": self.lock_graph.copy(),
                }
                self.deadlocks.append(deadlock_info)

            self.thread_locks[thread_id].add(resource_id)
            if resource_id not in self.lock_graph:
                self.lock_graph[resource_id] = set()

    def release_lock(self, thread_id: str, resource_id: str):
        """Record lock release."""
        with self.lock:
            if thread_id in self.thread_locks:
                self.thread_locks[thread_id].discard(resource_id)
                if not self.thread_locks[thread_id]:
                    del self.thread_locks[thread_id]

            if resource_id in self.lock_graph:
                self.lock_graph[resource_id].discard(thread_id)
                if not self.lock_graph[resource_id]:
                    del self.lock_graph[resource_id]

    def _would_create_deadlock(self, thread_id: str, resource_id: str) -> bool:
        """Check if acquiring this lock would create a deadlock."""
        # Simple cycle detection in lock graph
        held_locks = self.thread_locks.get(thread_id, set())

        for held_lock in held_locks:
            if self._has_path(resource_id, held_lock):
                return True

        return False

    def _has_path(self, start: str, end: str, visited: Optional[set] = None) -> bool:
        """Check if there's a path from start to end in lock graph."""
        if visited is None:
            visited = set()

        if start == end:
            return True

        if start in visited:
            return False

        visited.add(start)

        for next_resource in self.lock_graph.get(start, []):
            if self._has_path(next_resource, end, visited):
                return True

        return False

    def get_deadlocks(self) -> List[Dict[str, Any]]:
        """Get detected potential deadlocks."""
        with self.lock:
            return self.deadlocks.copy()


class AsyncConcurrencyTester:
    """Test async operations under concurrent load."""

    def __init__(self, max_concurrent: int = 100):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.results = []

    async def test_async_function(
        self,
        async_func: Callable[..., Awaitable],
        test_cases: List[tuple],
        max_concurrent: Optional[int] = None,
        timeout: float = 30.0,
    ) -> ConcurrencyTestResult:
        """Test async function under concurrent load."""
        max_concurrent = max_concurrent or self.max_concurrent
        start_time = time.perf_counter()

        completed = 0
        failed = 0
        response_times = []
        errors = []

        async def run_test_case(args):
            nonlocal completed, failed

            try:
                async with asyncio.timeout(timeout):
                    case_start = time.perf_counter()
                    result = await async_func(*args)
                    case_end = time.perf_counter()

                    response_times.append(case_end - case_start)
                    completed += 1
                    return result
            except Exception as e:
                failed += 1
                errors.append(str(e))
                raise

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def limited_test_case(args):
            async with semaphore:
                return await run_test_case(args)

        # Execute all test cases concurrently
        tasks = [limited_test_case(args) for args in test_cases]

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Concurrency test failed: {e}")

        end_time = time.perf_counter()
        duration = end_time - start_time

        return ConcurrencyTestResult(
            test_name=async_func.__name__,
            duration=duration,
            operations_completed=completed,
            operations_failed=failed,
            race_conditions_detected=0,  # To be set by caller if race detector used
            deadlocks_detected=0,  # To be set by caller if deadlock detector used
            max_concurrent=max_concurrent,
            avg_response_time=(
                sum(response_times) / len(response_times) if response_times else 0
            ),
            throughput_ops_per_sec=len(test_cases) / duration if duration > 0 else 0,
            errors=errors[:10],  # Limit error list size
        )

    async def test_database_concurrency(
        self,
        db_operation: Callable[..., Awaitable],
        operation_args: List[tuple],
        max_concurrent: int = 50,
    ) -> ConcurrencyTestResult:
        """Test database operations under concurrent load."""
        race_detector = RaceConditionDetector()

        async def monitored_operation(args):
            resource_id = f"db_operation_{id(args)}"
            race_detector.access_shared_resource(resource_id, "write", args)
            return await db_operation(*args)

        result = await self.test_async_function(
            monitored_operation, operation_args, max_concurrent
        )

        result.race_conditions_detected = len(race_detector.get_race_conditions())
        return result

    async def test_broker_order_concurrency(
        self,
        submit_order_func: Callable[..., Awaitable],
        orders: List[tuple],
        max_concurrent: int = 20,
    ) -> ConcurrencyTestResult:
        """Test broker order submission under concurrent load."""

        # Simulate realistic order timing
        async def timed_order_submission(order_args):
            # Add small random delay to simulate realistic conditions
            await asyncio.sleep(random.uniform(0.001, 0.01))
            return await submit_order_func(*order_args)

        return await self.test_async_function(
            timed_order_submission, orders, max_concurrent
        )


class ThreadConcurrencyTester:
    """Test threaded operations under concurrent load."""

    def __init__(self, max_workers: int = 50):
        self.max_workers = max_workers

    def test_threaded_function(
        self,
        func: Callable,
        test_cases: List[tuple],
        max_workers: Optional[int] = None,
        timeout: float = 30.0,
    ) -> ConcurrencyTestResult:
        """Test function with multiple threads."""
        max_workers = max_workers or self.max_workers
        start_time = time.perf_counter()

        completed = 0
        failed = 0
        response_times = []
        errors = []

        def run_test_case(args):
            nonlocal completed, failed

            try:
                case_start = time.perf_counter()
                result = func(*args)
                case_end = time.perf_counter()

                response_times.append(case_end - case_start)
                completed += 1
                return result
            except Exception as e:
                failed += 1
                errors.append(str(e))
                raise

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_test_case, args) for args in test_cases]

            for future in as_completed(futures, timeout=timeout):
                try:
                    future.result()
                except Exception:
                    pass  # Already counted in run_test_case

        end_time = time.perf_counter()
        duration = end_time - start_time

        return ConcurrencyTestResult(
            test_name=func.__name__,
            duration=duration,
            operations_completed=completed,
            operations_failed=failed,
            race_conditions_detected=0,
            deadlocks_detected=0,
            max_concurrent=max_workers,
            avg_response_time=(
                sum(response_times) / len(response_times) if response_times else 0
            ),
            throughput_ops_per_sec=len(test_cases) / duration if duration > 0 else 0,
            errors=errors[:10],
        )


class LoadGenerator:
    """Generate realistic load patterns for concurrency testing."""

    @staticmethod
    def generate_trading_load(
        num_orders: int = 1000, symbols: List[str] = None, order_types: List[str] = None
    ) -> List[tuple]:
        """Generate realistic trading order load."""
        symbols = symbols or ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        order_types = order_types or ["MARKET", "LIMIT", "STOP"]

        orders = []
        for i in range(num_orders):
            symbol = random.choice(symbols)
            side = random.choice(["BUY", "SELL"])
            quantity = random.randint(10000, 1000000)  # Lot sizes
            order_type = random.choice(order_types)

            order_args = (symbol, side, quantity, order_type)
            orders.append(order_args)

        return orders

    @staticmethod
    def generate_database_load(
        num_operations: int = 1000, operation_types: List[str] = None
    ) -> List[tuple]:
        """Generate database operation load."""
        operation_types = operation_types or [
            "insert_tick",
            "insert_candle",
            "query_data",
        ]

        operations = []
        for i in range(num_operations):
            op_type = random.choice(operation_types)

            if op_type == "insert_tick":
                args = (
                    f"EURUSD",
                    datetime.now(),
                    1.1000 + random.uniform(-0.01, 0.01),
                    random.randint(1000, 10000),
                )
            elif op_type == "insert_candle":
                base_price = 1.1000 + random.uniform(-0.01, 0.01)
                args = (
                    f"EURUSD",
                    datetime.now(),
                    base_price,
                    base_price + random.uniform(0, 0.001),
                    base_price - random.uniform(0, 0.001),
                    base_price + random.uniform(-0.0005, 0.0005),
                    random.randint(10000, 100000),
                )
            else:  # query_data
                args = (f"EURUSD", datetime.now() - timedelta(hours=1), datetime.now())

            operations.append(args)

        return operations

    @staticmethod
    def generate_burst_load(
        base_load: List[tuple], burst_factor: float = 3.0, burst_duration: float = 0.1
    ) -> List[tuple]:
        """Generate burst load pattern."""
        burst_size = int(len(base_load) * burst_factor)

        # Create burst by repeating operations with timestamps
        burst_load = []
        for i, operation in enumerate(base_load[:burst_size]):
            # Add timestamp to simulate burst timing
            timed_operation = operation + (
                time.time() + i * burst_duration / burst_size,
            )
            burst_load.append(timed_operation)

        return burst_load


@asynccontextmanager
async def concurrency_test_environment(
    max_concurrent: int = 100,
    enable_race_detection: bool = True,
    enable_deadlock_detection: bool = True,
):
    """Provide complete concurrency testing environment."""

    race_detector = RaceConditionDetector() if enable_race_detection else None
    deadlock_detector = DeadlockDetector() if enable_deadlock_detection else None
    async_tester = AsyncConcurrencyTester(max_concurrent)
    thread_tester = ThreadConcurrencyTester(max_concurrent)

    class ConcurrencyTestContext:
        def __init__(self):
            self.race_detector = race_detector
            self.deadlock_detector = deadlock_detector
            self.async_tester = async_tester
            self.thread_tester = thread_tester
            self.load_generator = LoadGenerator()

        async def test_async_operation(self, func, test_cases, **kwargs):
            """Test async operation with monitoring."""
            result = await self.async_tester.test_async_function(
                func, test_cases, **kwargs
            )

            if self.race_detector:
                result.race_conditions_detected = len(
                    self.race_detector.get_race_conditions()
                )

            if self.deadlock_detector:
                result.deadlocks_detected = len(self.deadlock_detector.get_deadlocks())

            return result

        def test_threaded_operation(self, func, test_cases, **kwargs):
            """Test threaded operation with monitoring."""
            return self.thread_tester.test_threaded_function(func, test_cases, **kwargs)

        def get_concurrency_report(self) -> Dict[str, Any]:
            """Get comprehensive concurrency test report."""
            report = {
                "timestamp": datetime.now().isoformat(),
                "max_concurrent": max_concurrent,
                "race_conditions": [],
                "deadlocks": [],
                "summary": {},
            }

            if self.race_detector:
                report["race_conditions"] = self.race_detector.get_race_conditions()

            if self.deadlock_detector:
                report["deadlocks"] = self.deadlock_detector.get_deadlocks()

            report["summary"] = {
                "total_race_conditions": len(report["race_conditions"]),
                "total_deadlocks": len(report["deadlocks"]),
                "safety_status": (
                    "SAFE"
                    if not report["race_conditions"] and not report["deadlocks"]
                    else "UNSAFE"
                ),
            }

            return report

    context = ConcurrencyTestContext()

    try:
        yield context
    finally:
        # Cleanup
        if race_detector:
            race_detector.reset()


# Utility functions for common testing patterns
async def simulate_high_frequency_trading(
    order_submission_func: Callable,
    num_orders: int = 1000,
    max_concurrent: int = 50,
    duration: float = 10.0,
) -> ConcurrencyTestResult:
    """Simulate high-frequency trading scenario."""

    orders = LoadGenerator.generate_trading_load(num_orders)

    async with concurrency_test_environment(max_concurrent) as env:
        result = await env.test_async_operation(
            order_submission_func,
            orders,
            max_concurrent=max_concurrent,
            timeout=duration,
        )

        # Add HFT-specific metrics
        result.metadata.update(
            {
                "hft_scenario": True,
                "orders_per_second": num_orders / duration,
                "concurrent_limit": max_concurrent,
                "trading_symbols": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"],
            }
        )

        return result


async def test_database_connection_pool(
    pool_operation_func: Callable, num_operations: int = 500, max_concurrent: int = 100
) -> ConcurrencyTestResult:
    """Test database connection pool under load."""

    operations = LoadGenerator.generate_database_load(num_operations)

    async with concurrency_test_environment(max_concurrent) as env:
        result = await env.async_tester.test_database_concurrency(
            pool_operation_func, operations, max_concurrent
        )

        result.metadata.update(
            {
                "pool_test": True,
                "connection_pool_size": max_concurrent,
                "operation_mix": ["insert_tick", "insert_candle", "query_data"],
            }
        )

        return result


def stress_test_threading_locks(
    lock_operation_func: Callable, num_operations: int = 1000, max_workers: int = 50
) -> ConcurrencyTestResult:
    """Stress test threading locks."""

    # Generate operations that compete for shared resources
    operations = [
        (f"resource_{i % 10}", f"operation_{i}") for i in range(num_operations)
    ]

    tester = ThreadConcurrencyTester(max_workers)
    result = tester.test_threaded_function(lock_operation_func, operations)

    result.metadata.update(
        {
            "lock_stress_test": True,
            "shared_resources": 10,
            "operations_per_resource": num_operations // 10,
        }
    )

    return result
