"""
FXML4 Performance Monitoring and Metrics Collection.

This module provides comprehensive performance monitoring for the FXML4 trading system,
including API metrics, trading performance, infrastructure monitoring, and business metrics.
"""

from .dashboard import MetricsDashboard, create_dashboard_router
from .metrics import (
    MetricsCollector,
    increment_counter,
    performance_timer,
    record_histogram,
    set_gauge,
    track_api_request,
    track_fix_message,
    track_order_execution,
)
from .middleware import PerformanceMiddleware, PrometheusMiddleware

__all__ = [
    # Core metrics functionality
    "MetricsCollector",
    "performance_timer",
    "track_api_request",
    "track_order_execution",
    "track_fix_message",
    "increment_counter",
    "record_histogram",
    "set_gauge",
    # Middleware
    "PrometheusMiddleware",
    "PerformanceMiddleware",
    # Dashboard
    "MetricsDashboard",
    "create_dashboard_router",
]
