"""
FXML4 System Health Monitor

This module implements system health monitoring for the comprehensive
monitoring and alerting system (Phase 10: Production Deployment & Operations).

Key Features:
- System resource monitoring (CPU, memory, disk, network)
- Health threshold evaluation and alerting
- Historical health data tracking
- System health status reporting
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import psutil

from .monitoring_manager import Alert, AlertSeverity, RuntimeMonitoringConfig


class SystemHealthMonitor:
    """System health monitoring component."""

    def __init__(self, config: Optional[RuntimeMonitoringConfig] = None):
        """Initialize system health monitor."""
        self.config = config or RuntimeMonitoringConfig()
        self.logger = logging.getLogger(__name__)
        self.health_history: List[Dict[str, Any]] = []

    async def initialize(self):
        """Initialize health monitor."""
        self.logger.info("Initializing SystemHealthMonitor...")

    async def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        try:
            cpu_metrics = await self.collect_cpu_metrics()
            memory_metrics = await self.collect_memory_metrics()
            disk_metrics = await self.collect_disk_metrics()
            network_metrics = await self.collect_network_metrics()

            # Evaluate overall system health
            cpu_healthy = (
                cpu_metrics["cpu_percent"] < self.config.cpu_critical_threshold
            )
            memory_healthy = (
                memory_metrics["memory_percent"] < self.config.memory_critical_threshold
            )
            disk_healthy = (
                disk_metrics["disk_usage_percent"] < self.config.disk_critical_threshold
            )
            network_healthy = (
                network_metrics.get("network_connections_active", 0) < 1000
            )

            overall_healthy = all(
                [cpu_healthy, memory_healthy, disk_healthy, network_healthy]
            )

            health_status = {
                "healthy": overall_healthy,
                "cpu_healthy": cpu_healthy,
                "memory_healthy": memory_healthy,
                "disk_healthy": disk_healthy,
                "network_healthy": network_healthy,
                "metrics": {
                    "cpu": cpu_metrics,
                    "memory": memory_metrics,
                    "disk": disk_metrics,
                    "network": network_metrics,
                },
                "check_timestamp": datetime.utcnow(),
            }

            # Store in health history
            self.health_history.append(health_status)
            if len(self.health_history) > 1000:
                self.health_history = self.health_history[-1000:]

            return health_status

        except Exception as e:
            self.logger.error(f"System health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "check_timestamp": datetime.utcnow(),
            }

    async def collect_cpu_metrics(self) -> Dict[str, Any]:
        """Collect CPU utilization metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = (
                psutil.getloadavg() if hasattr(psutil, "getloadavg") else [0, 0, 0]
            )

            return {
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count,
                "load_average": list(load_avg),
                "timestamp": datetime.utcnow(),
            }
        except Exception as e:
            self.logger.error(f"CPU metrics collection failed: {e}")
            return {"cpu_percent": 0, "error": str(e), "timestamp": datetime.utcnow()}

    async def collect_memory_metrics(self) -> Dict[str, Any]:
        """Collect memory utilization metrics."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                "memory_percent": memory.percent,
                "memory_available": memory.available,
                "memory_used": memory.used,
                "memory_total": memory.total,
                "swap_percent": swap.percent,
                "swap_used": swap.used,
                "timestamp": datetime.utcnow(),
            }
        except Exception as e:
            self.logger.error(f"Memory metrics collection failed: {e}")
            return {
                "memory_percent": 0,
                "error": str(e),
                "timestamp": datetime.utcnow(),
            }

    async def collect_disk_metrics(self) -> Dict[str, Any]:
        """Collect disk utilization metrics."""
        try:
            disk_usage = psutil.disk_usage("/")
            disk_io = psutil.disk_io_counters()

            return {
                "disk_usage_percent": (disk_usage.used / disk_usage.total) * 100,
                "disk_free_gb": disk_usage.free / (1024**3),
                "disk_used_gb": disk_usage.used / (1024**3),
                "disk_total_gb": disk_usage.total / (1024**3),
                "disk_io_read_bytes": disk_io.read_bytes if disk_io else 0,
                "disk_io_write_bytes": disk_io.write_bytes if disk_io else 0,
                "disk_io_read_time": disk_io.read_time if disk_io else 0,
                "disk_io_write_time": disk_io.write_time if disk_io else 0,
                "timestamp": datetime.utcnow(),
            }
        except Exception as e:
            self.logger.error(f"Disk metrics collection failed: {e}")
            return {
                "disk_usage_percent": 0,
                "error": str(e),
                "timestamp": datetime.utcnow(),
            }

    async def collect_network_metrics(self) -> Dict[str, Any]:
        """Collect network connectivity and bandwidth metrics."""
        try:
            network_io = psutil.net_io_counters()
            connections = psutil.net_connections()

            return {
                "network_bytes_sent": network_io.bytes_sent if network_io else 0,
                "network_bytes_recv": network_io.bytes_recv if network_io else 0,
                "network_packets_sent": network_io.packets_sent if network_io else 0,
                "network_packets_recv": network_io.packets_recv if network_io else 0,
                "network_connections_active": len(
                    [c for c in connections if c.status == "ESTABLISHED"]
                ),
                "timestamp": datetime.utcnow(),
            }
        except Exception as e:
            self.logger.error(f"Network metrics collection failed: {e}")
            return {
                "network_connections_active": 0,
                "error": str(e),
                "timestamp": datetime.utcnow(),
            }

    async def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive system metrics."""
        cpu_metrics = await self.collect_cpu_metrics()
        memory_metrics = await self.collect_memory_metrics()
        disk_metrics = await self.collect_disk_metrics()
        network_metrics = await self.collect_network_metrics()

        return {
            "cpu_metrics": cpu_metrics,
            "memory_metrics": memory_metrics,
            "disk_metrics": disk_metrics,
            "network_metrics": network_metrics,
            "collection_timestamp": datetime.utcnow(),
        }

    async def evaluate_system_thresholds(self) -> Dict[str, Any]:
        """Evaluate system-level thresholds."""
        alerts = []

        # Get latest system metrics
        system_metrics = await self.collect_system_metrics()
        cpu_metrics = system_metrics["cpu_metrics"]
        memory_metrics = system_metrics["memory_metrics"]
        disk_metrics = system_metrics["disk_metrics"]

        # Evaluate CPU threshold
        cpu_percent = cpu_metrics["cpu_percent"]
        if cpu_percent > self.config.cpu_critical_threshold:
            alerts.append(
                {
                    "alert_type": "high_cpu_utilization",
                    "severity": "critical",
                    "message": f"CPU utilization is {cpu_percent}% (threshold: {self.config.cpu_critical_threshold}%)",
                }
            )
        elif cpu_percent > self.config.cpu_warning_threshold:
            alerts.append(
                {
                    "alert_type": "high_cpu_utilization",
                    "severity": "warning",
                    "message": f"CPU utilization is {cpu_percent}% (threshold: {self.config.cpu_warning_threshold}%)",
                }
            )

        # Evaluate memory threshold
        memory_percent = memory_metrics["memory_percent"]
        if memory_percent > self.config.memory_critical_threshold:
            alerts.append(
                {
                    "alert_type": "high_memory_utilization",
                    "severity": "critical",
                    "message": f"Memory utilization is {memory_percent}% (threshold: {self.config.memory_critical_threshold}%)",
                }
            )

        # Evaluate disk threshold
        disk_percent = disk_metrics["disk_usage_percent"]
        if disk_percent > self.config.disk_critical_threshold:
            alerts.append(
                {
                    "alert_type": "high_disk_usage",
                    "severity": "critical",
                    "message": f"Disk usage is {disk_percent}% (threshold: {self.config.disk_critical_threshold}%)",
                }
            )

        return {"alerts": alerts, "evaluation_timestamp": datetime.utcnow()}

    async def shutdown(self):
        """Shutdown health monitor."""
        self.logger.info("SystemHealthMonitor shutdown completed")
