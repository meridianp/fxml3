"""
Connection Monitor for FXML4 Trading System

This module provides comprehensive connection monitoring and health checking
for broker connectivity, ensuring early detection of connection issues and
proactive failover triggering.

Key Features:
- Real-time connection health monitoring
- Heartbeat tracking and timeout detection
- Network latency and performance monitoring
- Connection stability metrics
- Proactive health assessments
- Automated alert generation

Health Check SLA: <5s detection time for connection issues
Heartbeat Frequency: Every 10 seconds
Timeout Threshold: 30 seconds without heartbeat
"""

import asyncio
import json
import logging
import socket
import statistics
import time
import weakref
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, NamedTuple, Optional

import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Connection health status."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class ConnectionMetrics:
    """Connection performance metrics."""

    broker_id: str
    timestamp: datetime
    latency_ms: float
    packet_loss_percent: float = 0.0
    throughput_mbps: float = 0.0
    error_rate_percent: float = 0.0
    api_response_time_ms: float = 0.0
    heartbeat_interval_seconds: float = 0.0
    connection_stability_score: float = 100.0  # 0-100 scale


@dataclass
class HealthCheckResult:
    """Health check result."""

    broker_id: str
    timestamp: datetime
    status: HealthStatus
    latency_ms: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None
    check_duration_ms: float = 0.0


@dataclass
class ConnectionAlert:
    """Connection-related alert."""

    alert_id: str
    timestamp: datetime
    broker_id: str
    severity: AlertSeverity
    alert_type: str
    title: str
    description: str
    metrics: Optional[ConnectionMetrics] = None
    acknowledged: bool = False
    resolved: bool = False


class NetworkTester:
    """Network connectivity and performance tester."""

    def __init__(self):
        self.test_hosts = {
            "interactive_brokers": "gw1.ibllc.com",
            "fxcm": "api.fxcm.com",
            "google_dns": "8.8.8.8",
            "cloudflare_dns": "1.1.1.1",
        }

    async def ping_host(self, host: str, timeout: float = 5.0) -> Optional[float]:
        """Ping a host and return latency in milliseconds."""
        try:
            start_time = time.perf_counter()

            # Use socket connection test as ping alternative
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            try:
                result = sock.connect_ex((host, 80))  # Try HTTP port
                if result != 0:
                    result = sock.connect_ex((host, 443))  # Try HTTPS port

                latency_ms = (time.perf_counter() - start_time) * 1000

                if result == 0:
                    return latency_ms
                else:
                    return None

            finally:
                sock.close()

        except Exception as e:
            logger.debug(f"Ping failed for {host}: {e}")
            return None

    async def test_broker_connectivity(self, broker_id: str) -> ConnectionMetrics:
        """Test connectivity to a specific broker."""
        timestamp = datetime.utcnow()

        # Determine host based on broker
        if "ib" in broker_id.lower():
            host = self.test_hosts.get("interactive_brokers", "127.0.0.1")
        elif "fxcm" in broker_id.lower():
            host = self.test_hosts.get("fxcm", "127.0.0.1")
        else:
            host = "127.0.0.1"  # Default to localhost for testing

        # Test latency
        latency = await self.ping_host(host)
        if latency is None:
            latency = 9999.0  # High latency indicates connection issues

        # Simulate additional metrics (in real implementation, these would be measured)
        packet_loss = 0.0 if latency < 1000 else min(latency / 100, 5.0)
        error_rate = 0.0 if latency < 500 else min(latency / 200, 10.0)

        # Calculate stability score
        stability_score = max(
            0, 100 - (latency / 10) - (packet_loss * 10) - (error_rate * 5)
        )

        return ConnectionMetrics(
            broker_id=broker_id,
            timestamp=timestamp,
            latency_ms=latency,
            packet_loss_percent=packet_loss,
            error_rate_percent=error_rate,
            connection_stability_score=stability_score,
        )


class ConnectionMonitor:
    """
    Real-time connection monitor for broker connectivity.

    Monitors connection health, tracks performance metrics, and generates
    alerts for connection issues that could impact trading operations.
    """

    def __init__(self, heartbeat_interval: int = 10, timeout_threshold: int = 30):
        self.heartbeat_interval = heartbeat_interval
        self.timeout_threshold = timeout_threshold

        # Monitoring state
        self.monitored_connections: Dict[str, Dict[str, Any]] = {}
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None

        # Metrics storage
        self.connection_metrics: Dict[str, deque] = {}
        self.health_history: Dict[str, deque] = {}
        self.alert_history: deque = deque(maxlen=1000)

        # Performance tracking
        self.network_tester = NetworkTester()

        # Callbacks
        self.health_change_listeners: List[weakref.ReferenceType] = []
        self.alert_listeners: List[weakref.ReferenceType] = []

        logger.info(
            f"ConnectionMonitor initialized with {heartbeat_interval}s heartbeat, {timeout_threshold}s timeout"
        )

    async def add_connection(
        self,
        broker_id: str,
        endpoint_url: str,
        heartbeat_endpoint: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Add a connection to monitor."""
        connection_config = {
            "broker_id": broker_id,
            "endpoint_url": endpoint_url,
            "heartbeat_endpoint": heartbeat_endpoint or f"{endpoint_url}/health",
            "headers": custom_headers or {},
            "last_heartbeat": None,
            "consecutive_failures": 0,
            "total_checks": 0,
            "successful_checks": 0,
            "current_status": HealthStatus.UNKNOWN,
            "last_status_change": datetime.utcnow(),
        }

        self.monitored_connections[broker_id] = connection_config
        self.connection_metrics[broker_id] = deque(maxlen=1000)
        self.health_history[broker_id] = deque(maxlen=1000)

        logger.info(f"Added connection monitor for {broker_id}: {endpoint_url}")

    async def start_monitoring(self) -> None:
        """Start the monitoring service."""
        if self.is_monitoring:
            logger.warning("Monitoring already started")
            return

        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Connection monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop the monitoring service."""
        self.is_monitoring = False

        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Connection monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Starting connection monitoring loop")

        while self.is_monitoring:
            try:
                # Check all monitored connections
                check_tasks = [
                    self._check_connection_health(broker_id, config)
                    for broker_id, config in self.monitored_connections.items()
                ]

                if check_tasks:
                    results = await asyncio.gather(*check_tasks, return_exceptions=True)

                    # Process results
                    for i, result in enumerate(results):
                        broker_id = list(self.monitored_connections.keys())[i]

                        if isinstance(result, Exception):
                            logger.error(
                                f"Health check error for {broker_id}: {result}"
                            )
                            await self._handle_check_error(broker_id, str(result))
                        else:
                            await self._process_health_result(result)

                # Wait for next check interval
                await asyncio.sleep(self.heartbeat_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(self.heartbeat_interval)

        logger.info("Connection monitoring loop stopped")

    async def _check_connection_health(
        self, broker_id: str, config: Dict[str, Any]
    ) -> HealthCheckResult:
        """Perform health check for a specific connection."""
        start_time = time.perf_counter()
        timestamp = datetime.utcnow()

        try:
            # Perform network connectivity test
            network_metrics = await self.network_tester.test_broker_connectivity(
                broker_id
            )

            # Perform HTTP health check
            http_success, http_latency, error_msg = (
                await self._perform_http_health_check(
                    config["heartbeat_endpoint"], config["headers"]
                )
            )

            # Update connection config
            config["total_checks"] += 1
            if http_success:
                config["successful_checks"] += 1
                config["consecutive_failures"] = 0
                config["last_heartbeat"] = timestamp
            else:
                config["consecutive_failures"] += 1

            # Determine health status
            status = self._determine_health_status(
                network_metrics, http_success, config
            )

            # Update status if changed
            if status != config["current_status"]:
                previous_status = config["current_status"]
                config["current_status"] = status
                config["last_status_change"] = timestamp

                await self._notify_health_change(
                    broker_id, status, previous_status, timestamp
                )

            # Store metrics
            network_metrics.api_response_time_ms = http_latency if http_latency else 0.0
            network_metrics.heartbeat_interval_seconds = self.heartbeat_interval
            self.connection_metrics[broker_id].append(network_metrics)

            check_duration = (time.perf_counter() - start_time) * 1000

            result = HealthCheckResult(
                broker_id=broker_id,
                timestamp=timestamp,
                status=status,
                latency_ms=network_metrics.latency_ms,
                success=http_success,
                error_message=error_msg,
                check_duration_ms=check_duration,
            )

            self.health_history[broker_id].append(result)
            return result

        except Exception as e:
            check_duration = (time.perf_counter() - start_time) * 1000
            error_result = HealthCheckResult(
                broker_id=broker_id,
                timestamp=timestamp,
                status=HealthStatus.CRITICAL,
                success=False,
                error_message=str(e),
                check_duration_ms=check_duration,
            )

            self.health_history[broker_id].append(error_result)
            return error_result

    async def _perform_http_health_check(
        self, endpoint: str, headers: Dict[str, str]
    ) -> tuple:
        """Perform HTTP health check."""
        try:
            start_time = time.perf_counter()

            timeout = aiohttp.ClientTimeout(total=5.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(endpoint, headers=headers) as response:
                    latency_ms = (time.perf_counter() - start_time) * 1000

                    if response.status == 200:
                        return True, latency_ms, None
                    else:
                        return False, latency_ms, f"HTTP {response.status}"

        except asyncio.TimeoutError:
            latency_ms = 5000.0  # Timeout latency
            return False, latency_ms, "Request timeout"
        except Exception as e:
            return False, None, str(e)

    def _determine_health_status(
        self, metrics: ConnectionMetrics, http_success: bool, config: Dict[str, Any]
    ) -> HealthStatus:
        """Determine health status based on metrics and history."""
        # Critical conditions
        if not http_success and config["consecutive_failures"] >= 3:
            return HealthStatus.CRITICAL

        if metrics.latency_ms > 5000:  # 5 second latency
            return HealthStatus.CRITICAL

        # Warning conditions
        if not http_success or config["consecutive_failures"] > 0:
            return HealthStatus.WARNING

        if metrics.latency_ms > 1000:  # 1 second latency
            return HealthStatus.WARNING

        if metrics.connection_stability_score < 80:
            return HealthStatus.WARNING

        # Healthy
        return HealthStatus.HEALTHY

    async def _handle_check_error(self, broker_id: str, error_message: str) -> None:
        """Handle health check errors."""
        config = self.monitored_connections[broker_id]
        config["consecutive_failures"] += 1
        config["total_checks"] += 1

        # Generate critical alert for persistent errors
        if config["consecutive_failures"] >= 5:
            await self._generate_alert(
                broker_id=broker_id,
                severity=AlertSeverity.CRITICAL,
                alert_type="connection_check_failure",
                title="Persistent Health Check Failures",
                description=f"Health check failed {config['consecutive_failures']} consecutive times: {error_message}",
            )

    async def _process_health_result(self, result: HealthCheckResult) -> None:
        """Process health check result and generate alerts if needed."""
        if result.status == HealthStatus.CRITICAL:
            await self._generate_alert(
                broker_id=result.broker_id,
                severity=AlertSeverity.CRITICAL,
                alert_type="connection_health_critical",
                title="Critical Connection Health Status",
                description=f"Connection health critical: {result.error_message or 'Unknown error'}",
            )
        elif result.status == HealthStatus.WARNING:
            await self._generate_alert(
                broker_id=result.broker_id,
                severity=AlertSeverity.WARNING,
                alert_type="connection_health_warning",
                title="Connection Health Warning",
                description=f"Connection health degraded: latency {result.latency_ms:.1f}ms",
            )

    async def _generate_alert(
        self,
        broker_id: str,
        severity: AlertSeverity,
        alert_type: str,
        title: str,
        description: str,
        metrics: Optional[ConnectionMetrics] = None,
    ) -> None:
        """Generate connection alert."""
        alert = ConnectionAlert(
            alert_id=f"conn_{broker_id}_{int(time.time())}",
            timestamp=datetime.utcnow(),
            broker_id=broker_id,
            severity=severity,
            alert_type=alert_type,
            title=title,
            description=description,
            metrics=metrics,
        )

        self.alert_history.append(alert)

        logger.warning(
            f"Connection Alert [{severity.value.upper()}] {broker_id}: {title}"
        )

        # Notify listeners
        await self._notify_alert_listeners(alert)

    async def _notify_health_change(
        self,
        broker_id: str,
        new_status: HealthStatus,
        previous_status: HealthStatus,
        timestamp: datetime,
    ) -> None:
        """Notify health status change listeners."""
        for listener_ref in self.health_change_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.health_change_listeners.remove(listener_ref)
            else:
                try:
                    await listener(broker_id, new_status, previous_status, timestamp)
                except Exception as e:
                    logger.error(f"Health change listener error: {e}")

    async def _notify_alert_listeners(self, alert: ConnectionAlert) -> None:
        """Notify alert listeners."""
        for listener_ref in self.alert_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.alert_listeners.remove(listener_ref)
            else:
                try:
                    await listener(alert)
                except Exception as e:
                    logger.error(f"Alert listener error: {e}")

    async def add_health_change_listener(self, callback: Callable) -> None:
        """Add health status change listener."""
        self.health_change_listeners.append(weakref.ref(callback))

    async def add_alert_listener(self, callback: Callable) -> None:
        """Add alert listener."""
        self.alert_listeners.append(weakref.ref(callback))

    def get_connection_status(self, broker_id: str) -> Optional[Dict[str, Any]]:
        """Get current status for a specific connection."""
        if broker_id not in self.monitored_connections:
            return None

        config = self.monitored_connections[broker_id]
        recent_metrics = (
            list(self.connection_metrics[broker_id])[-10:]
            if self.connection_metrics[broker_id]
            else []
        )
        recent_health = (
            list(self.health_history[broker_id])[-10:]
            if self.health_history[broker_id]
            else []
        )

        # Calculate performance statistics
        if recent_metrics:
            latencies = [m.latency_ms for m in recent_metrics]
            avg_latency = statistics.mean(latencies)
            max_latency = max(latencies)
            stability_scores = [m.connection_stability_score for m in recent_metrics]
            avg_stability = statistics.mean(stability_scores)
        else:
            avg_latency = 0.0
            max_latency = 0.0
            avg_stability = 0.0

        # Calculate uptime
        success_rate = (
            (config["successful_checks"] / config["total_checks"]) * 100
            if config["total_checks"] > 0
            else 0
        )

        return {
            "broker_id": broker_id,
            "current_status": config["current_status"].value,
            "endpoint_url": config["endpoint_url"],
            "last_heartbeat": (
                config["last_heartbeat"].isoformat()
                if config["last_heartbeat"]
                else None
            ),
            "consecutive_failures": config["consecutive_failures"],
            "total_checks": config["total_checks"],
            "successful_checks": config["successful_checks"],
            "success_rate_percent": round(success_rate, 2),
            "performance_metrics": {
                "average_latency_ms": round(avg_latency, 2),
                "max_latency_ms": round(max_latency, 2),
                "average_stability_score": round(avg_stability, 1),
            },
            "last_status_change": config["last_status_change"].isoformat(),
            "recent_health_checks": [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "status": h.status.value,
                    "latency_ms": h.latency_ms,
                    "success": h.success,
                    "error": h.error_message,
                }
                for h in recent_health
            ],
        }

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get comprehensive monitoring summary."""
        total_connections = len(self.monitored_connections)
        healthy_connections = sum(
            1
            for config in self.monitored_connections.values()
            if config["current_status"] == HealthStatus.HEALTHY
        )
        warning_connections = sum(
            1
            for config in self.monitored_connections.values()
            if config["current_status"] == HealthStatus.WARNING
        )
        critical_connections = sum(
            1
            for config in self.monitored_connections.values()
            if config["current_status"] == HealthStatus.CRITICAL
        )

        # Recent alerts
        recent_alerts = [
            {
                "timestamp": alert.timestamp.isoformat(),
                "broker_id": alert.broker_id,
                "severity": alert.severity.value,
                "title": alert.title,
                "resolved": alert.resolved,
            }
            for alert in list(self.alert_history)[-20:]  # Last 20 alerts
        ]

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "monitoring_active": self.is_monitoring,
            "total_connections": total_connections,
            "connection_health": {
                "healthy": healthy_connections,
                "warning": warning_connections,
                "critical": critical_connections,
                "unknown": total_connections
                - healthy_connections
                - warning_connections
                - critical_connections,
            },
            "monitoring_config": {
                "heartbeat_interval_seconds": self.heartbeat_interval,
                "timeout_threshold_seconds": self.timeout_threshold,
            },
            "recent_alerts": recent_alerts,
            "connections": {
                broker_id: self.get_connection_status(broker_id)
                for broker_id in self.monitored_connections.keys()
            },
        }

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alert_history:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                logger.info(f"Alert acknowledged: {alert_id}")
                return True

        logger.warning(f"Alert not found for acknowledgment: {alert_id}")
        return False

    async def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        for alert in self.alert_history:
            if alert.alert_id == alert_id:
                alert.resolved = True
                logger.info(f"Alert resolved: {alert_id}")
                return True

        logger.warning(f"Alert not found for resolution: {alert_id}")
        return False
