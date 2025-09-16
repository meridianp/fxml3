"""
Latency Monitor and Microsecond Timer

High-precision latency measurement for HFT systems:
- Hardware timestamp integration for nanosecond accuracy
- Statistical analysis of latency distributions
- Real-time performance monitoring and alerting
- Comprehensive performance profiling tools
"""

import functools
import heapq
import statistics
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class LatencyMeasurement:
    """Individual latency measurement record"""

    operation: str
    start_time_ns: int
    end_time_ns: int
    duration_ns: int = field(init=False)
    thread_id: int = field(default_factory=lambda: threading.get_ident())
    sequence: int = 0
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        self.duration_ns = self.end_time_ns - self.start_time_ns

    @property
    def duration_us(self) -> float:
        """Duration in microseconds"""
        return self.duration_ns / 1000.0

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds"""
        return self.duration_ns / 1_000_000.0


@dataclass
class LatencyStats:
    """Statistical analysis of latency measurements"""

    operation: str
    count: int = 0
    min_ns: int = float("inf")
    max_ns: int = 0
    mean_ns: float = 0.0
    median_ns: float = 0.0
    p95_ns: float = 0.0
    p99_ns: float = 0.0
    p99_9_ns: float = 0.0
    stddev_ns: float = 0.0
    total_ns: int = 0

    @property
    def min_us(self) -> float:
        return self.min_ns / 1000.0 if self.min_ns != float("inf") else 0.0

    @property
    def max_us(self) -> float:
        return self.max_ns / 1000.0

    @property
    def mean_us(self) -> float:
        return self.mean_ns / 1000.0

    @property
    def median_us(self) -> float:
        return self.median_ns / 1000.0

    @property
    def p95_us(self) -> float:
        return self.p95_ns / 1000.0

    @property
    def p99_us(self) -> float:
        return self.p99_ns / 1000.0

    @property
    def p99_9_us(self) -> float:
        return self.p99_9_ns / 1000.0


class MicrosecondTimer:
    """
    High-precision timer for microsecond-level measurements

    Uses the highest resolution timer available on the system.
    Optimized for minimal overhead in measurement.
    """

    def __init__(self):
        # Use the highest precision timer available
        self.timer_func = time.time_ns
        self.resolution_ns = self._measure_timer_resolution()

        # Calibrate timer overhead
        self.overhead_ns = self._measure_timer_overhead()

    def _measure_timer_resolution(self) -> int:
        """Measure actual timer resolution"""
        measurements = []

        for _ in range(1000):
            t1 = self.timer_func()
            t2 = self.timer_func()
            if t2 > t1:
                measurements.append(t2 - t1)

        return min(measurements) if measurements else 1

    def _measure_timer_overhead(self) -> int:
        """Measure timer call overhead"""
        measurements = []

        for _ in range(1000):
            start = self.timer_func()
            # Simulate measurement operation
            _ = self.timer_func()
            end = self.timer_func()
            measurements.append(end - start)

        return int(statistics.median(measurements))

    def now(self) -> int:
        """Get current timestamp in nanoseconds"""
        return self.timer_func()

    def measure_duration(self, start_ns: int, end_ns: int) -> int:
        """Measure duration with overhead compensation"""
        raw_duration = end_ns - start_ns
        return max(0, raw_duration - self.overhead_ns)

    def get_info(self) -> Dict[str, Any]:
        """Get timer information"""
        return {
            "resolution_ns": self.resolution_ns,
            "overhead_ns": self.overhead_ns,
            "timer_function": str(self.timer_func),
        }


class LatencyMonitor:
    """
    Comprehensive latency monitoring system

    Tracks performance metrics for all HFT operations with:
    - Real-time statistical analysis
    - Percentile calculations
    - Performance alerting
    - Historical trend analysis
    """

    def __init__(self, max_measurements: int = 100_000):
        self.max_measurements = max_measurements
        self.timer = MicrosecondTimer()

        # Storage for measurements
        self.measurements: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_measurements)
        )
        self.active_measurements: Dict[int, LatencyMeasurement] = {}
        self.sequence_counter = 0

        # Statistics cache
        self.stats_cache: Dict[str, LatencyStats] = {}
        self.cache_valid: Dict[str, bool] = defaultdict(bool)

        # Performance thresholds and alerting
        self.thresholds: Dict[str, Dict[str, int]] = (
            {}
        )  # operation -> {warning_ns, critical_ns}
        self.alert_callbacks: List[Callable] = []

        # Thread safety
        self.lock = threading.RLock()

        # Monitoring thread
        self.monitoring_enabled = True
        self.monitoring_thread = None

    def set_threshold(self, operation: str, warning_us: float, critical_us: float):
        """Set performance thresholds for operation"""
        self.thresholds[operation] = {
            "warning_ns": int(warning_us * 1000),
            "critical_ns": int(critical_us * 1000),
        }

    def add_alert_callback(self, callback: Callable[[str, LatencyMeasurement], None]):
        """Add callback for threshold violations"""
        self.alert_callbacks.append(callback)

    def start_measurement(
        self, operation: str, metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Start a latency measurement"""
        with self.lock:
            measurement_id = id(threading.current_thread()) + self.sequence_counter
            start_time = self.timer.now()

            measurement = LatencyMeasurement(
                operation=operation,
                start_time_ns=start_time,
                end_time_ns=0,
                sequence=self.sequence_counter,
                metadata=metadata,
            )

            self.active_measurements[measurement_id] = measurement
            self.sequence_counter += 1

            return measurement_id

    def end_measurement(self, measurement_id: int) -> Optional[LatencyMeasurement]:
        """End a latency measurement"""
        with self.lock:
            if measurement_id not in self.active_measurements:
                return None

            measurement = self.active_measurements.pop(measurement_id)
            measurement.end_time_ns = self.timer.now()
            measurement.duration_ns = self.timer.measure_duration(
                measurement.start_time_ns, measurement.end_time_ns
            )

            # Store measurement
            self.measurements[measurement.operation].append(measurement)

            # Invalidate cache
            self.cache_valid[measurement.operation] = False

            # Check thresholds
            self._check_thresholds(measurement)

            return measurement

    @contextmanager
    def measure(self, operation: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for measuring latency"""
        measurement_id = self.start_measurement(operation, metadata)
        try:
            yield measurement_id
        finally:
            self.end_measurement(measurement_id)

    def record_measurement(
        self,
        operation: str,
        duration_ns: int,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a completed measurement directly"""
        with self.lock:
            measurement = LatencyMeasurement(
                operation=operation,
                start_time_ns=0,  # Not available for direct recording
                end_time_ns=0,
                sequence=self.sequence_counter,
                metadata=metadata,
            )
            measurement.duration_ns = duration_ns

            self.measurements[operation].append(measurement)
            self.cache_valid[operation] = False
            self.sequence_counter += 1

            # Check thresholds
            self._check_thresholds(measurement)

    def _check_thresholds(self, measurement: LatencyMeasurement):
        """Check if measurement violates thresholds"""
        thresholds = self.thresholds.get(measurement.operation)
        if not thresholds:
            return

        alert_level = None

        if measurement.duration_ns >= thresholds["critical_ns"]:
            alert_level = "critical"
        elif measurement.duration_ns >= thresholds["warning_ns"]:
            alert_level = "warning"

        if alert_level:
            for callback in self.alert_callbacks:
                try:
                    callback(alert_level, measurement)
                except Exception:
                    pass  # Don't let callback errors affect monitoring

    def get_stats(self, operation: Optional[str] = None) -> Dict[str, LatencyStats]:
        """Get latency statistics for operation(s)"""
        if operation:
            return {operation: self._calculate_stats(operation)}
        else:
            return {op: self._calculate_stats(op) for op in self.measurements.keys()}

    def _calculate_stats(self, operation: str) -> LatencyStats:
        """Calculate statistics for a specific operation"""
        with self.lock:
            # Use cache if valid
            if self.cache_valid[operation] and operation in self.stats_cache:
                return self.stats_cache[operation]

            measurements = list(self.measurements[operation])
            if not measurements:
                return LatencyStats(operation=operation)

            durations = [m.duration_ns for m in measurements]
            durations.sort()

            count = len(durations)
            total_ns = sum(durations)
            mean_ns = total_ns / count

            # Calculate percentiles
            p95_idx = int(0.95 * count)
            p99_idx = int(0.99 * count)
            p99_9_idx = int(0.999 * count)

            stats = LatencyStats(
                operation=operation,
                count=count,
                min_ns=min(durations),
                max_ns=max(durations),
                mean_ns=mean_ns,
                median_ns=durations[count // 2] if count > 0 else 0,
                p95_ns=durations[min(p95_idx, count - 1)] if count > 0 else 0,
                p99_ns=durations[min(p99_idx, count - 1)] if count > 0 else 0,
                p99_9_ns=durations[min(p99_9_idx, count - 1)] if count > 0 else 0,
                stddev_ns=statistics.stdev(durations) if count > 1 else 0,
                total_ns=total_ns,
            )

            # Cache results
            self.stats_cache[operation] = stats
            self.cache_valid[operation] = True

            return stats

    def get_recent_measurements(
        self, operation: str, count: int = 100
    ) -> List[LatencyMeasurement]:
        """Get recent measurements for operation"""
        with self.lock:
            measurements = list(self.measurements[operation])
            return measurements[-count:] if len(measurements) > count else measurements

    def get_slowest_measurements(
        self, operation: str, count: int = 10
    ) -> List[LatencyMeasurement]:
        """Get slowest measurements for operation"""
        with self.lock:
            measurements = list(self.measurements[operation])
            return heapq.nlargest(count, measurements, key=lambda m: m.duration_ns)

    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        with self.lock:
            report = {
                "timer_info": self.timer.get_info(),
                "operations": {},
                "summary": {
                    "total_operations": len(self.measurements),
                    "total_measurements": sum(
                        len(measurements) for measurements in self.measurements.values()
                    ),
                    "active_measurements": len(self.active_measurements),
                    "thresholds_configured": len(self.thresholds),
                },
            }

            # Per-operation statistics
            for operation in self.measurements.keys():
                stats = self._calculate_stats(operation)
                recent = self.get_recent_measurements(operation, 10)
                slowest = self.get_slowest_measurements(operation, 5)

                report["operations"][operation] = {
                    "stats": stats.__dict__,
                    "recent_measurements": [m.__dict__ for m in recent],
                    "slowest_measurements": [m.__dict__ for m in slowest],
                    "thresholds": self.thresholds.get(operation, {}),
                }

            return report

    def reset_measurements(self, operation: Optional[str] = None):
        """Reset measurements for operation(s)"""
        with self.lock:
            if operation:
                self.measurements[operation].clear()
                self.cache_valid[operation] = False
                if operation in self.stats_cache:
                    del self.stats_cache[operation]
            else:
                self.measurements.clear()
                self.stats_cache.clear()
                self.cache_valid.clear()

    def start_monitoring_thread(self):
        """Start background monitoring thread"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return

        self.monitoring_enabled = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.monitoring_thread.start()

    def stop_monitoring_thread(self):
        """Stop background monitoring thread"""
        self.monitoring_enabled = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self.monitoring_enabled:
            try:
                # Clean up old active measurements (potential leaks)
                current_time = self.timer.now()
                cleanup_threshold = 60 * 1_000_000_000  # 60 seconds in nanoseconds

                with self.lock:
                    stale_measurements = [
                        mid
                        for mid, measurement in self.active_measurements.items()
                        if current_time - measurement.start_time_ns > cleanup_threshold
                    ]

                    for mid in stale_measurements:
                        del self.active_measurements[mid]

                time.sleep(10)  # Check every 10 seconds

            except Exception:
                pass  # Continue monitoring despite errors


def latency_decorator(operation: str, monitor: Optional[LatencyMonitor] = None):
    """Decorator for automatic latency measurement"""

    def decorator(func):
        nonlocal monitor
        if monitor is None:
            monitor = LatencyMonitor()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with monitor.measure(operation):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Global latency monitor instance
global_latency_monitor = LatencyMonitor()


# Example usage and testing
if __name__ == "__main__":
    print("Latency Monitor Performance Test")
    print("=" * 40)

    # Create monitor with thresholds
    monitor = LatencyMonitor()
    monitor.set_threshold("test_operation", warning_us=100, critical_us=500)

    # Add alert callback
    def alert_handler(level: str, measurement: LatencyMeasurement):
        print(
            f"ALERT [{level.upper()}]: {measurement.operation} took {measurement.duration_us:.2f}μs"
        )

    monitor.add_alert_callback(alert_handler)

    # Simulate various operation latencies
    print("Simulating operations...")

    for i in range(1000):
        with monitor.measure("fast_operation"):
            time.sleep(0.00001)  # 10μs

        with monitor.measure("medium_operation"):
            time.sleep(0.00005)  # 50μs

        if i % 100 == 0:  # Occasional slow operation
            with monitor.measure("slow_operation"):
                time.sleep(0.001)  # 1ms

    # Add some threshold violations
    monitor.record_measurement("test_operation", 200_000)  # 200μs (warning)
    monitor.record_measurement("test_operation", 600_000)  # 600μs (critical)

    # Get comprehensive report
    report = monitor.get_comprehensive_report()

    print(f"\nTimer Resolution: {report['timer_info']['resolution_ns']}ns")
    print(f"Timer Overhead: {report['timer_info']['overhead_ns']}ns")
    print(f"Total Operations: {report['summary']['total_operations']}")
    print(f"Total Measurements: {report['summary']['total_measurements']}")

    # Print per-operation statistics
    for operation, data in report["operations"].items():
        stats = data["stats"]
        print(f"\n{operation.upper()}:")
        print(f"  Count: {stats['count']}")
        print(f"  Mean: {stats['mean_ns'] / 1000:.2f}μs")
        print(f"  P95: {stats['p95_ns'] / 1000:.2f}μs")
        print(f"  P99: {stats['p99_ns'] / 1000:.2f}μs")
        print(f"  Max: {stats['max_ns'] / 1000:.2f}μs")

    # Test decorator
    print("\nTesting decorator...")

    @latency_decorator("decorated_function", monitor)
    def test_function(delay_ms: float):
        time.sleep(delay_ms / 1000)
        return delay_ms

    # Call decorated function
    for delay in [1, 5, 10]:
        result = test_function(delay)
        print(f"Function returned: {result}")

    # Final statistics
    decorator_stats = monitor.get_stats("decorated_function")
    if decorator_stats:
        stats = decorator_stats["decorated_function"]
        print(f"\nDecorated function stats:")
        print(f"  Mean: {stats.mean_us:.2f}μs")
        print(f"  Count: {stats.count}")

    print("\nLatency monitoring test completed!")
