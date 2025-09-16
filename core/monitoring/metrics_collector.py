"""
System metrics collection and monitoring infrastructure.

This module provides comprehensive metrics collection for:
- Application performance metrics
- System resource utilization
- Database and cache performance
- Message queue statistics
- Trading-specific metrics
"""

import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import aiohttp
import psutil
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
)

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricDefinition:
    """Definition of a metric."""

    name: str
    type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None  # For histograms
    unit: Optional[str] = None


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    component: str
    status: str  # healthy, degraded, unhealthy
    message: Optional[str] = None
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    Comprehensive metrics collection system.
    """

    def __init__(
        self,
        app_name: str = "fxml4",
        enable_prometheus: bool = True,
        enable_system_metrics: bool = True,
    ):
        """
        Initialize metrics collector.

        Args:
            app_name: Application name for metric prefixes
            enable_prometheus: Enable Prometheus metrics export
            enable_system_metrics: Enable system resource metrics
        """
        self.app_name = app_name
        self.enable_prometheus = enable_prometheus
        self.enable_system_metrics = enable_system_metrics

        # Prometheus registry
        self.registry = CollectorRegistry() if enable_prometheus else None

        # Metric storage
        self.metrics: Dict[str, Any] = {}
        self.metric_definitions: Dict[str, MetricDefinition] = {}

        # Health checks
        self.health_checks: Dict[str, Callable] = {}
        self.health_status: Dict[str, HealthCheckResult] = {}

        # Time series storage (for internal use)
        self.time_series: Dict[str, deque] = defaultdict(lambda: deque(maxlen=3600))

        # Background tasks
        self.collection_task: Optional[asyncio.Task] = None
        self.is_running = False

        # Initialize standard metrics
        self._initialize_standard_metrics()

    def _initialize_standard_metrics(self):
        """Initialize standard application metrics."""
        # API metrics
        self.define_metric(
            "api_requests_total",
            MetricType.COUNTER,
            "Total API requests",
            labels=["method", "endpoint", "status"],
        )

        self.define_metric(
            "api_request_duration_seconds",
            MetricType.HISTOGRAM,
            "API request duration",
            labels=["method", "endpoint"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        )

        # Trading metrics
        self.define_metric(
            "orders_submitted_total",
            MetricType.COUNTER,
            "Total orders submitted",
            labels=["symbol", "side", "order_type"],
        )

        self.define_metric(
            "orders_filled_total",
            MetricType.COUNTER,
            "Total orders filled",
            labels=["symbol", "side"],
        )

        self.define_metric(
            "position_value",
            MetricType.GAUGE,
            "Current position value",
            labels=["symbol"],
            unit="USD",
        )

        self.define_metric(
            "portfolio_value", MetricType.GAUGE, "Total portfolio value", unit="USD"
        )

        self.define_metric(
            "daily_pnl", MetricType.GAUGE, "Daily profit and loss", unit="USD"
        )

        # System metrics
        if self.enable_system_metrics:
            self.define_metric(
                "system_cpu_usage_percent", MetricType.GAUGE, "CPU usage percentage"
            )

            self.define_metric(
                "system_memory_usage_percent",
                MetricType.GAUGE,
                "Memory usage percentage",
            )

            self.define_metric(
                "system_disk_usage_percent",
                MetricType.GAUGE,
                "Disk usage percentage",
                labels=["mount_point"],
            )

        # Database metrics
        self.define_metric(
            "database_connections_active",
            MetricType.GAUGE,
            "Active database connections",
        )

        self.define_metric(
            "database_query_duration_seconds",
            MetricType.HISTOGRAM,
            "Database query duration",
            labels=["query_type"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
        )

        # Message queue metrics
        self.define_metric(
            "mq_messages_sent_total",
            MetricType.COUNTER,
            "Total messages sent",
            labels=["queue"],
        )

        self.define_metric(
            "mq_messages_received_total",
            MetricType.COUNTER,
            "Total messages received",
            labels=["queue"],
        )

        self.define_metric(
            "mq_queue_depth", MetricType.GAUGE, "Current queue depth", labels=["queue"]
        )

    def define_metric(
        self,
        name: str,
        metric_type: MetricType,
        description: str,
        labels: List[str] = None,
        buckets: List[float] = None,
        unit: str = None,
    ):
        """Define a new metric."""
        full_name = f"{self.app_name}_{name}"

        definition = MetricDefinition(
            name=full_name,
            type=metric_type,
            description=description,
            labels=labels or [],
            buckets=buckets,
            unit=unit,
        )

        self.metric_definitions[name] = definition

        # Create Prometheus metric
        if self.enable_prometheus and self.registry:
            if metric_type == MetricType.COUNTER:
                metric = Counter(
                    full_name,
                    description,
                    labelnames=labels or [],
                    registry=self.registry,
                )
            elif metric_type == MetricType.GAUGE:
                metric = Gauge(
                    full_name,
                    description,
                    labelnames=labels or [],
                    registry=self.registry,
                )
            elif metric_type == MetricType.HISTOGRAM:
                metric = Histogram(
                    full_name,
                    description,
                    labelnames=labels or [],
                    buckets=buckets or Histogram.DEFAULT_BUCKETS,
                    registry=self.registry,
                )
            elif metric_type == MetricType.SUMMARY:
                metric = Summary(
                    full_name,
                    description,
                    labelnames=labels or [],
                    registry=self.registry,
                )

            self.metrics[name] = metric

    def increment_counter(
        self, name: str, value: float = 1, labels: Dict[str, str] = None
    ):
        """Increment a counter metric."""
        if name not in self.metrics:
            logger.warning(f"Metric {name} not defined")
            return

        metric = self.metrics[name]
        if labels:
            metric.labels(**labels).inc(value)
        else:
            metric.inc(value)

        # Store in time series
        self._record_time_series(name, value, labels)

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric value."""
        if name not in self.metrics:
            logger.warning(f"Metric {name} not defined")
            return

        metric = self.metrics[name]
        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)

        # Store in time series
        self._record_time_series(name, value, labels)

    def observe_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Observe a value for histogram metric."""
        if name not in self.metrics:
            logger.warning(f"Metric {name} not defined")
            return

        metric = self.metrics[name]
        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)

        # Store in time series
        self._record_time_series(name, value, labels)

    def time_function(self, metric_name: str, labels: Dict[str, str] = None):
        """Decorator to time function execution."""

        def decorator(func):
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    self.observe_histogram(metric_name, duration, labels)

            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    self.observe_histogram(metric_name, duration, labels)

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator

    def _record_time_series(
        self, name: str, value: float, labels: Dict[str, str] = None
    ):
        """Record value in time series storage."""
        key = name
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            key = f"{name}{{{label_str}}}"

        self.time_series[key].append(
            {"timestamp": datetime.now(timezone.utc), "value": value}
        )

    async def start(self):
        """Start metrics collection."""
        self.is_running = True

        # Start collection tasks
        if self.enable_system_metrics:
            self.collection_task = asyncio.create_task(self._collect_system_metrics())

        # Start health check task
        asyncio.create_task(self._run_health_checks())

        logger.info("Metrics collector started")

    async def stop(self):
        """Stop metrics collection."""
        self.is_running = False

        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass

        logger.info("Metrics collector stopped")

    async def _collect_system_metrics(self):
        """Collect system resource metrics."""
        while self.is_running:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.set_gauge("system_cpu_usage_percent", cpu_percent)

                # Memory usage
                memory = psutil.virtual_memory()
                self.set_gauge("system_memory_usage_percent", memory.percent)

                # Disk usage
                for partition in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        self.set_gauge(
                            "system_disk_usage_percent",
                            usage.percent,
                            {"mount_point": partition.mountpoint},
                        )
                    except PermissionError:
                        continue

                await asyncio.sleep(10)  # Collect every 10 seconds

            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(10)

    def register_health_check(self, component: str, check_func: Callable):
        """Register a health check function."""
        self.health_checks[component] = check_func

    async def _run_health_checks(self):
        """Run all registered health checks."""
        while self.is_running:
            try:
                for component, check_func in self.health_checks.items():
                    try:
                        start_time = time.time()

                        if asyncio.iscoroutinefunction(check_func):
                            result = await check_func()
                        else:
                            result = check_func()

                        latency_ms = (time.time() - start_time) * 1000

                        if isinstance(result, HealthCheckResult):
                            result.latency_ms = latency_ms
                            self.health_status[component] = result
                        else:
                            # Simple boolean result
                            self.health_status[component] = HealthCheckResult(
                                component=component,
                                status="healthy" if result else "unhealthy",
                                latency_ms=latency_ms,
                            )

                    except Exception as e:
                        self.health_status[component] = HealthCheckResult(
                            component=component, status="unhealthy", message=str(e)
                        )

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error running health checks: {e}")
                await asyncio.sleep(30)

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        statuses = list(self.health_status.values())

        # Determine overall status
        if not statuses:
            overall_status = "unknown"
        elif all(s.status == "healthy" for s in statuses):
            overall_status = "healthy"
        elif any(s.status == "unhealthy" for s in statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"

        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                component: {
                    "status": result.status,
                    "message": result.message,
                    "latency_ms": result.latency_ms,
                    "metadata": result.metadata,
                }
                for component, result in self.health_status.items()
            },
        }

    def get_prometheus_metrics(self) -> bytes:
        """Get metrics in Prometheus format."""
        if not self.enable_prometheus or not self.registry:
            return b""

        return generate_latest(self.registry)

    def get_time_series(
        self,
        metric_name: str,
        duration_minutes: int = 60,
        labels: Dict[str, str] = None,
    ) -> List[Dict[str, Any]]:
        """Get time series data for a metric."""
        key = metric_name
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            key = f"{metric_name}{{{label_str}}}"

        if key not in self.time_series:
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=duration_minutes)

        return [
            {"timestamp": point["timestamp"].isoformat(), "value": point["value"]}
            for point in self.time_series[key]
            if point["timestamp"] > cutoff_time
        ]

    def create_alert_rule(
        self,
        name: str,
        condition: str,
        threshold: float,
        duration_seconds: int = 60,
        labels: Dict[str, str] = None,
    ):
        """Create an alert rule (placeholder for integration with alerting system)."""
        # This would integrate with Prometheus AlertManager or similar
        logger.info(f"Alert rule created: {name} - {condition} > {threshold}")

    async def export_to_remote(self, endpoint: str, api_key: str):
        """Export metrics to remote monitoring service."""
        metrics_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "app_name": self.app_name,
            "metrics": {},
        }

        # Collect all current metric values
        for name, series in self.time_series.items():
            if series:
                latest = series[-1]
                metrics_data["metrics"][name] = latest["value"]

        # Add health status
        metrics_data["health"] = self.get_health_status()

        # Send to remote endpoint
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    endpoint, json=metrics_data, headers=headers
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to export metrics: {resp.status}")
            except Exception as e:
                logger.error(f"Error exporting metrics: {e}")
