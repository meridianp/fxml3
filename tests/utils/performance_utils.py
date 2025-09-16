"""Performance testing utilities for FXML4 test suite.

This module provides utilities for performance testing, benchmarking,
and optimization validation.
"""

import asyncio
import functools
import multiprocessing
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from statistics import mean, median, stdev
from typing import Any, Callable, Dict, List, Optional, Union


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""

    name: str
    execution_time: float
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None
    iterations: int = 1
    min_time: Optional[float] = None
    max_time: Optional[float] = None
    avg_time: Optional[float] = None
    median_time: Optional[float] = None
    std_dev: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate derived metrics."""
        if self.iterations > 1 and hasattr(self, "_times"):
            times = getattr(self, "_times", [self.execution_time])
            self.min_time = min(times)
            self.max_time = max(times)
            self.avg_time = mean(times)
            self.median_time = median(times)
            if len(times) > 1:
                self.std_dev = stdev(times)


class PerformanceTimer:
    """High-precision timer for performance measurement."""

    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.times = []

    def start(self):
        """Start the timer."""
        self.start_time = time.perf_counter()
        return self

    def stop(self):
        """Stop the timer and record time."""
        if self.start_time is None:
            raise ValueError("Timer not started")

        self.end_time = time.perf_counter()
        elapsed = self.end_time - self.start_time
        self.times.append(elapsed)
        return elapsed

    def elapsed(self) -> float:
        """Get elapsed time without stopping."""
        if self.start_time is None:
            raise ValueError("Timer not started")

        current_time = self.end_time or time.perf_counter()
        return current_time - self.start_time

    def reset(self):
        """Reset the timer."""
        self.start_time = None
        self.end_time = None
        self.times.clear()

    def get_metrics(self) -> PerformanceMetrics:
        """Get performance metrics."""
        if not self.times:
            raise ValueError("No timing data available")

        metrics = PerformanceMetrics(
            name=self.name, execution_time=self.times[-1], iterations=len(self.times)
        )
        metrics._times = self.times.copy()
        metrics.__post_init__()

        return metrics


@contextmanager
def time_operation(name: str = "operation"):
    """Context manager for timing operations."""
    timer = PerformanceTimer(name)
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()


@asynccontextmanager
async def async_time_operation(name: str = "async_operation"):
    """Async context manager for timing operations."""
    timer = PerformanceTimer(name)
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()


def benchmark(iterations: int = 1, warmup: int = 0):
    """Decorator for benchmarking functions."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Warmup runs
            for _ in range(warmup):
                func(*args, **kwargs)

            # Benchmark runs
            timer = PerformanceTimer(func.__name__)
            for _ in range(iterations):
                timer.start()
                result = func(*args, **kwargs)
                timer.stop()

            # Store metrics on function
            wrapper.performance_metrics = timer.get_metrics()
            return result

        return wrapper

    return decorator


def async_benchmark(iterations: int = 1, warmup: int = 0):
    """Decorator for benchmarking async functions."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Warmup runs
            for _ in range(warmup):
                await func(*args, **kwargs)

            # Benchmark runs
            timer = PerformanceTimer(func.__name__)
            for _ in range(iterations):
                timer.start()
                result = await func(*args, **kwargs)
                timer.stop()

            # Store metrics on function
            wrapper.performance_metrics = timer.get_metrics()
            return result

        return wrapper

    return decorator


class MemoryProfiler:
    """Memory usage profiler."""

    def __init__(self):
        self.initial_memory = None
        self.peak_memory = None
        self.measurements = []
        self._process = None

    def start(self):
        """Start memory profiling."""
        try:
            import psutil

            self._process = psutil.Process()
            self.initial_memory = self._process.memory_info().rss
            self.peak_memory = self.initial_memory
        except ImportError:
            # Fallback to basic measurement
            self.initial_memory = 0
            self.peak_memory = 0

        return self

    def measure(self, label: str = ""):
        """Take a memory measurement."""
        if self._process:
            current = self._process.memory_info().rss
            self.peak_memory = max(self.peak_memory, current)
            self.measurements.append(
                {
                    "label": label,
                    "memory_bytes": current,
                    "memory_mb": current / 1024 / 1024,
                    "delta_bytes": current - self.initial_memory,
                    "delta_mb": (current - self.initial_memory) / 1024 / 1024,
                }
            )

        return self.measurements[-1] if self.measurements else {}

    def get_summary(self) -> Dict[str, Any]:
        """Get memory usage summary."""
        return {
            "initial_mb": (self.initial_memory or 0) / 1024 / 1024,
            "peak_mb": (self.peak_memory or 0) / 1024 / 1024,
            "delta_mb": ((self.peak_memory or 0) - (self.initial_memory or 0))
            / 1024
            / 1024,
            "measurements": self.measurements,
        }


@contextmanager
def memory_profiler():
    """Context manager for memory profiling."""
    profiler = MemoryProfiler()
    profiler.start()
    try:
        yield profiler
    finally:
        profiler.measure("final")


class ConcurrencyTester:
    """Test concurrent operations performance."""

    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.results = []

    def test_threads(
        self, func: Callable, args_list: List[tuple], max_workers: int = None
    ) -> Dict[str, Any]:
        """Test function with multiple threads."""
        import concurrent.futures

        workers = max_workers or self.max_workers
        start_time = time.perf_counter()

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(func, *args) for args in args_list]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        end_time = time.perf_counter()

        return {
            "execution_time": end_time - start_time,
            "workers": workers,
            "tasks": len(args_list),
            "results": results,
            "tasks_per_second": len(args_list) / (end_time - start_time),
        }

    def test_processes(
        self, func: Callable, args_list: List[tuple], max_workers: int = None
    ) -> Dict[str, Any]:
        """Test function with multiple processes."""
        import concurrent.futures

        workers = max_workers or self.max_workers
        start_time = time.perf_counter()

        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(func, *args) for args in args_list]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        end_time = time.perf_counter()

        return {
            "execution_time": end_time - start_time,
            "workers": workers,
            "tasks": len(args_list),
            "results": results,
            "tasks_per_second": len(args_list) / (end_time - start_time),
        }

    async def test_async_concurrent(
        self, coro_func: Callable, args_list: List[tuple], max_concurrent: int = None
    ) -> Dict[str, Any]:
        """Test async function with concurrent execution."""
        max_concurrent = max_concurrent or self.max_workers
        start_time = time.perf_counter()

        semaphore = asyncio.Semaphore(max_concurrent)

        async def limited_coro(args):
            async with semaphore:
                return await coro_func(*args)

        tasks = [limited_coro(args) for args in args_list]
        results = await asyncio.gather(*tasks)

        end_time = time.perf_counter()

        return {
            "execution_time": end_time - start_time,
            "max_concurrent": max_concurrent,
            "tasks": len(args_list),
            "results": results,
            "tasks_per_second": len(args_list) / (end_time - start_time),
        }


class PerformanceAssertions:
    """Performance-related test assertions."""

    @staticmethod
    def assert_max_execution_time(func: Callable, max_time: float, *args, **kwargs):
        """Assert function executes within max time."""
        timer = PerformanceTimer()
        timer.start()

        result = func(*args, **kwargs)
        elapsed = timer.stop()

        assert (
            elapsed <= max_time
        ), f"Function took {elapsed:.3f}s, expected <= {max_time}s"
        return result

    @staticmethod
    async def assert_max_async_time(
        coro_func: Callable, max_time: float, *args, **kwargs
    ):
        """Assert async function executes within max time."""
        timer = PerformanceTimer()
        timer.start()

        result = await coro_func(*args, **kwargs)
        elapsed = timer.stop()

        assert (
            elapsed <= max_time
        ), f"Async function took {elapsed:.3f}s, expected <= {max_time}s"
        return result

    @staticmethod
    def assert_memory_usage(max_delta_mb: float):
        """Assert memory usage stays within limits."""

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with memory_profiler() as profiler:
                    result = func(*args, **kwargs)

                summary = profiler.get_summary()
                delta_mb = summary["delta_mb"]

                assert (
                    delta_mb <= max_delta_mb
                ), f"Memory usage increased by {delta_mb:.1f}MB, expected <= {max_delta_mb}MB"

                return result

            return wrapper

        return decorator

    @staticmethod
    def assert_throughput(min_ops_per_second: float, iterations: int = 100):
        """Assert function meets minimum throughput."""

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()

                for _ in range(iterations):
                    func(*args, **kwargs)

                end_time = time.perf_counter()
                elapsed = end_time - start_time
                ops_per_second = iterations / elapsed

                assert (
                    ops_per_second >= min_ops_per_second
                ), f"Throughput {ops_per_second:.2f} ops/s, expected >= {min_ops_per_second} ops/s"

                return func(*args, **kwargs)

            return wrapper

        return decorator


class PerformanceReporter:
    """Generate performance reports."""

    def __init__(self):
        self.metrics = []

    def add_metrics(self, metrics: PerformanceMetrics):
        """Add performance metrics."""
        self.metrics.append(metrics)

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        if not self.metrics:
            return {"error": "No metrics available"}

        report = {
            "summary": {
                "total_operations": len(self.metrics),
                "total_time": sum(m.execution_time for m in self.metrics),
                "avg_time": mean([m.execution_time for m in self.metrics]),
                "fastest": min(self.metrics, key=lambda m: m.execution_time),
                "slowest": max(self.metrics, key=lambda m: m.execution_time),
            },
            "details": [],
        }

        for metrics in self.metrics:
            detail = {
                "name": metrics.name,
                "execution_time": metrics.execution_time,
                "iterations": metrics.iterations,
            }

            if metrics.memory_usage:
                detail["memory_usage"] = metrics.memory_usage

            if metrics.avg_time:
                detail.update(
                    {
                        "min_time": metrics.min_time,
                        "max_time": metrics.max_time,
                        "avg_time": metrics.avg_time,
                        "median_time": metrics.median_time,
                        "std_dev": metrics.std_dev,
                    }
                )

            report["details"].append(detail)

        return report

    def save_report(self, filename: str):
        """Save report to file."""
        import json

        report = self.generate_report()

        with open(filename, "w") as f:
            json.dump(report, f, indent=2, default=str)


# Utility functions
def measure_function_performance(
    func: Callable, iterations: int = 1, warmup: int = 0, *args, **kwargs
) -> PerformanceMetrics:
    """Measure performance of a function."""
    # Warmup
    for _ in range(warmup):
        func(*args, **kwargs)

    # Measure
    timer = PerformanceTimer(func.__name__)
    for _ in range(iterations):
        timer.start()
        func(*args, **kwargs)
        timer.stop()

    return timer.get_metrics()


async def measure_async_performance(
    coro_func: Callable, iterations: int = 1, warmup: int = 0, *args, **kwargs
) -> PerformanceMetrics:
    """Measure performance of an async function."""
    # Warmup
    for _ in range(warmup):
        await coro_func(*args, **kwargs)

    # Measure
    timer = PerformanceTimer(coro_func.__name__)
    for _ in range(iterations):
        timer.start()
        await coro_func(*args, **kwargs)
        timer.stop()

    return timer.get_metrics()


def compare_implementations(
    *functions, iterations: int = 100, args: tuple = (), kwargs: dict = None
) -> Dict[str, Any]:
    """Compare performance of multiple function implementations."""
    kwargs = kwargs or {}
    results = {}

    for func in functions:
        metrics = measure_function_performance(func, iterations, 1, *args, **kwargs)
        results[func.__name__] = metrics

    # Find fastest/slowest
    times = {
        name: metrics.avg_time or metrics.execution_time
        for name, metrics in results.items()
    }

    fastest = min(times, key=times.get)
    slowest = max(times, key=times.get)

    return {
        "results": results,
        "fastest": fastest,
        "slowest": slowest,
        "speedup": (
            times[slowest] / times[fastest] if times[fastest] > 0 else float("inf")
        ),
    }
