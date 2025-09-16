"""
Core metrics collection system for FXML4.

Provides high-performance metrics collection for trading operations,
API performance, and system monitoring.
"""

import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricPoint:
    """Represents a single metric measurement."""

    def __init__(
        self,
        name: str,
        value: float,
        timestamp: float = None,
        labels: Dict[str, str] = None,
    ):
        self.name = name
        self.value = value
        self.timestamp = timestamp or time.time()
        self.labels = labels or {}


class MetricsCollector:
    """High-performance metrics collector for FXML4 trading system."""

    def __init__(self, max_history: int = 10000):
        """Initialize metrics collector.

        Args:
            max_history: Maximum number of metric points to keep in memory
        """
        self.max_history = max_history
        self._lock = threading.RLock()

        # Metric storage
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        self._timers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))

        # Labels for metrics
        self._metric_labels: Dict[str, Dict[str, str]] = defaultdict(dict)

        # System start time
        self._start_time = time.time()

        logger.info(f"MetricsCollector initialized with max_history={max_history}")

    def increment_counter(
        self, name: str, value: float = 1.0, labels: Dict[str, str] = None
    ):
        """Increment a counter metric."""
        with self._lock:
            key = self._make_key(name, labels)
            self._counters[key] += value
            if labels:
                self._metric_labels[key] = labels

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric value."""
        with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value
            if labels:
                self._metric_labels[key] = labels

    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram value."""
        with self._lock:
            key = self._make_key(name, labels)
            self._histograms[key].append((time.time(), value))
            if labels:
                self._metric_labels[key] = labels

    def record_timer(self, name: str, duration: float, labels: Dict[str, str] = None):
        """Record a timer measurement."""
        with self._lock:
            key = self._make_key(name, labels)
            self._timers[key].append((time.time(), duration))
            if labels:
                self._metric_labels[key] = labels

    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Create a unique key for metric with labels."""
        if not labels:
            return name

        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"

    @contextmanager
    def timer(self, name: str, labels: Dict[str, str] = None):
        """Context manager for timing operations."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_timer(name, duration, labels)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        with self._lock:
            now = time.time()

            # Calculate histogram statistics
            histogram_stats = {}
            for name, values in self._histograms.items():
                if values:
                    recent_values = [
                        v for t, v in values if now - t < 300
                    ]  # Last 5 minutes
                    if recent_values:
                        histogram_stats[name] = {
                            "count": len(recent_values),
                            "sum": sum(recent_values),
                            "avg": sum(recent_values) / len(recent_values),
                            "min": min(recent_values),
                            "max": max(recent_values),
                        }

            # Calculate timer statistics
            timer_stats = {}
            for name, values in self._timers.items():
                if values:
                    recent_values = [
                        v for t, v in values if now - t < 300
                    ]  # Last 5 minutes
                    if recent_values:
                        timer_stats[name] = {
                            "count": len(recent_values),
                            "total_time": sum(recent_values),
                            "avg_time": sum(recent_values) / len(recent_values),
                            "min_time": min(recent_values),
                            "max_time": max(recent_values),
                        }

            return {
                "system": {
                    "uptime_seconds": now - self._start_time,
                    "metrics_collected": len(self._counters)
                    + len(self._gauges)
                    + len(self._histograms)
                    + len(self._timers),
                },
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": histogram_stats,
                "timers": timer_stats,
                "timestamp": now,
            }

    def get_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        with self._lock:
            lines = []

            # Counters
            for name, value in self._counters.items():
                lines.append(f"# TYPE {self._clean_name(name)} counter")
                lines.append(f"{self._clean_name(name)} {value}")

            # Gauges
            for name, value in self._gauges.items():
                lines.append(f"# TYPE {self._clean_name(name)} gauge")
                lines.append(f"{self._clean_name(name)} {value}")

            # Histograms (simplified)
            now = time.time()
            for name, values in self._histograms.items():
                if values:
                    recent_values = [v for t, v in values if now - t < 300]
                    if recent_values:
                        lines.append(f"# TYPE {self._clean_name(name)} histogram")
                        lines.append(
                            f"{self._clean_name(name)}_count {len(recent_values)}"
                        )
                        lines.append(
                            f"{self._clean_name(name)}_sum {sum(recent_values)}"
                        )

            return "\n".join(lines)

    def _clean_name(self, name: str) -> str:
        """Clean metric name for Prometheus format."""
        # Remove labels from name
        base_name = name.split("[")[0]
        # Replace invalid characters
        return base_name.lower().replace("-", "_").replace(".", "_").replace("/", "_")

    def reset_metrics(self):
        """Reset all metrics (use with caution)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            self._metric_labels.clear()
            logger.info("All metrics reset")


# Global metrics collector instance
_global_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return _global_collector


# Convenience functions for common metrics operations
def increment_counter(name: str, value: float = 1.0, labels: Dict[str, str] = None):
    """Increment a counter metric."""
    _global_collector.increment_counter(name, value, labels)


def set_gauge(name: str, value: float, labels: Dict[str, str] = None):
    """Set a gauge metric value."""
    _global_collector.set_gauge(name, value, labels)


def record_histogram(name: str, value: float, labels: Dict[str, str] = None):
    """Record a histogram value."""
    _global_collector.record_histogram(name, value, labels)


def record_timer(name: str, duration: float, labels: Dict[str, str] = None):
    """Record a timer measurement."""
    _global_collector.record_timer(name, duration, labels)


@contextmanager
def performance_timer(name: str, labels: Dict[str, str] = None):
    """Context manager for timing performance-critical operations."""
    with _global_collector.timer(name, labels):
        yield


def performance_monitor(metric_name: str = None, labels: Dict[str, str] = None):
    """Decorator to monitor function performance."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = metric_name or f"function_{func.__module__}.{func.__name__}"
            with performance_timer(name, labels):
                result = func(*args, **kwargs)
            return result

        return wrapper

    return decorator


# Specialized tracking functions for FXML4 components
def track_api_request(method: str, endpoint: str, status_code: int, duration: float):
    """Track API request metrics."""
    labels = {"method": method, "endpoint": endpoint, "status_code": str(status_code)}
    increment_counter("api_requests_total", labels=labels)
    record_timer("api_request_duration_seconds", duration, labels)

    if status_code >= 400:
        increment_counter("api_request_errors_total", labels=labels)


def track_order_execution(
    symbol: str, side: str, quantity: float, execution_time: float, success: bool
):
    """Track order execution metrics."""
    labels = {"symbol": symbol, "side": side, "success": str(success)}
    increment_counter("orders_executed_total", labels=labels)
    record_histogram("order_quantity", quantity, labels)
    record_timer("order_execution_time_seconds", execution_time, labels)

    if not success:
        increment_counter("order_execution_errors_total", labels=labels)


def track_fix_message(msg_type: str, direction: str, processing_time: float):
    """Track FIX message processing metrics."""
    labels = {"msg_type": msg_type, "direction": direction}  # 'inbound' or 'outbound'
    increment_counter("fix_messages_total", labels=labels)
    record_timer("fix_message_processing_time_seconds", processing_time, labels)


def track_ml_inference(
    model_name: str, symbol: str, inference_time: float, success: bool
):
    """Track ML model inference metrics."""
    labels = {"model": model_name, "symbol": symbol, "success": str(success)}
    increment_counter("ml_inferences_total", labels=labels)
    record_timer("ml_inference_time_seconds", inference_time, labels)

    if not success:
        increment_counter("ml_inference_errors_total", labels=labels)


def track_backtest_performance(
    strategy: str, symbol: str, timeframe: str, execution_time: float
):
    """Track backtesting performance metrics."""
    labels = {"strategy": strategy, "symbol": symbol, "timeframe": timeframe}
    increment_counter("backtests_completed_total", labels=labels)
    record_timer("backtest_execution_time_seconds", execution_time, labels)


def track_broker_adapter(
    adapter_name: str, operation: str, success: bool, duration: float
):
    """Track broker adapter performance."""
    labels = {"adapter": adapter_name, "operation": operation, "success": str(success)}
    increment_counter("broker_operations_total", labels=labels)
    record_timer("broker_operation_duration_seconds", duration, labels)

    if not success:
        increment_counter("broker_operation_errors_total", labels=labels)
