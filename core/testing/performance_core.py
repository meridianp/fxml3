"""Performance monitoring and optimization for tests."""

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class TestPerformanceMonitor:
    """Monitors test execution performance."""

    def __init__(self):
        self.metrics = {}

    @contextmanager
    def measure_test(self, test_name: str):
        """Context manager to measure test performance."""
        start_time = time.perf_counter()
        start_memory = self._get_memory_usage()
        db_queries_start = self._get_db_query_count()

        try:
            yield
        finally:
            end_time = time.perf_counter()
            end_memory = self._get_memory_usage()
            db_queries_end = self._get_db_query_count()

            self.metrics[test_name] = {
                "execution_time": end_time - start_time,
                "memory_usage": end_memory - start_memory,
                "database_queries": db_queries_end - db_queries_start,
            }

    def get_metrics(self, test_name: str) -> Dict[str, Any]:
        """Get performance metrics for a test."""
        return self.metrics.get(test_name, {})

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0

    def _get_db_query_count(self) -> int:
        """Get current database query count."""
        # Mock implementation
        return getattr(threading.current_thread(), "db_query_count", 0)


class SlowTestDetector:
    """Detects and provides suggestions for slow tests."""

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold
        self.test_times = {}

    @contextmanager
    def monitor(self, test_name: str):
        """Monitor test execution time."""
        start_time = time.perf_counter()
        try:
            yield
        finally:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            self.test_times[test_name] = execution_time

    def is_slow(self, test_name: str) -> bool:
        """Check if a test is considered slow."""
        return self.test_times.get(test_name, 0) > self.threshold

    def get_optimization_suggestions(self, test_name: str) -> List[str]:
        """Get optimization suggestions for a slow test."""
        suggestions = []

        execution_time = self.test_times.get(test_name, 0)
        if execution_time > self.threshold:
            suggestions.append(
                "Consider using database mocking instead of real database"
            )
            suggestions.append("Review test for unnecessary network calls")
            suggestions.append("Check for inefficient loops or algorithms")

            if execution_time > 10 * self.threshold:
                suggestions.append("Consider breaking test into smaller unit tests")
                suggestions.append("Use fixtures with shared setup/teardown")

        return suggestions


class ResourceOptimizer:
    """Optimizes resource allocation based on test type."""

    def __init__(self):
        self.configurations = {
            "unit": {
                "database_pool_size": 1,
                "enable_caching": False,
                "timeout": 5.0,
                "enable_metrics": False,
                "parallel_execution": False,
            },
            "integration": {
                "database_pool_size": 3,
                "enable_caching": True,
                "timeout": 30.0,
                "enable_metrics": True,
                "parallel_execution": True,
            },
            "performance": {
                "database_pool_size": 10,
                "enable_caching": True,
                "timeout": 60.0,
                "enable_metrics": True,
                "parallel_execution": True,
                "detailed_profiling": True,
            },
            "load": {
                "database_pool_size": 20,
                "enable_caching": True,
                "timeout": 120.0,
                "enable_metrics": True,
                "parallel_execution": True,
                "resource_monitoring": True,
            },
        }

    def get_optimal_config(self, test_type: str) -> Dict[str, Any]:
        """Get optimal configuration for test type."""
        return self.configurations.get(test_type, self.configurations["unit"]).copy()
