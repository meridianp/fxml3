"""
Broker Health Monitoring for FXML4 Trading System.
Continuously monitors broker connections for failover detection.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class BrokerHealthMetrics:
    """Broker health metrics."""

    broker_id: str
    status: HealthStatus
    response_time: float
    last_heartbeat: datetime
    error_count: int = 0
    uptime_percentage: float = 100.0
    last_error: Optional[str] = None


class BrokerHealthMonitor:
    """
    Monitors broker health with configurable thresholds and callbacks.
    Designed for high-frequency health checks with minimal overhead.
    """

    def __init__(
        self,
        broker_manager,
        health_check_interval: float = 5.0,
        heartbeat_timeout: float = 30.0,
        response_timeout: float = 10.0,
    ):
        """Initialize health monitor."""
        self.broker_manager = broker_manager
        self.health_check_interval = health_check_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.response_timeout = response_timeout

        # Monitoring state
        self.monitoring = False
        self.monitor_tasks = {}
        self.health_metrics = {}
        self.health_history = {}

        # Callbacks
        self.health_change_callbacks = []
        self.failure_callbacks = []
        self.recovery_callbacks = []

        # Statistics
        self.total_health_checks = 0
        self.failed_health_checks = 0

    def add_health_change_callback(self, callback: Callable):
        """Add callback for health status changes."""
        self.health_change_callbacks.append(callback)

    def add_failure_callback(self, callback: Callable):
        """Add callback for broker failures."""
        self.failure_callbacks.append(callback)

    def add_recovery_callback(self, callback: Callable):
        """Add callback for broker recoveries."""
        self.recovery_callbacks.append(callback)

    async def start_monitoring(self):
        """Start health monitoring for all brokers."""
        if self.monitoring:
            logger.warning("Health monitoring already started")
            return

        self.monitoring = True
        logger.info("Starting broker health monitoring")

        # Start monitoring each broker
        for broker_id in self.broker_manager.adapters.keys():
            await self._start_broker_monitoring(broker_id)

        logger.info(f"Health monitoring started for {len(self.monitor_tasks)} brokers")

    async def stop_monitoring(self):
        """Stop health monitoring."""
        if not self.monitoring:
            return

        self.monitoring = False
        logger.info("Stopping broker health monitoring")

        # Cancel monitoring tasks
        for task in self.monitor_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.monitor_tasks.clear()
        logger.info("Broker health monitoring stopped")

    async def _start_broker_monitoring(self, broker_id: str):
        """Start monitoring specific broker."""
        if broker_id in self.monitor_tasks:
            return

        task = asyncio.create_task(self._monitor_broker_loop(broker_id))
        self.monitor_tasks[broker_id] = task

        # Initialize health metrics
        self.health_metrics[broker_id] = BrokerHealthMetrics(
            broker_id=broker_id,
            status=HealthStatus.UNKNOWN,
            response_time=0.0,
            last_heartbeat=datetime.utcnow(),
        )

        self.health_history[broker_id] = []

        logger.debug(f"Started monitoring broker: {broker_id}")

    async def _monitor_broker_loop(self, broker_id: str):
        """Continuous monitoring loop for specific broker."""
        consecutive_failures = 0

        while self.monitoring:
            try:
                # Perform health check
                health_result = await self._perform_health_check(broker_id)
                previous_metrics = self.health_metrics.get(broker_id)

                # Update metrics
                self.health_metrics[broker_id] = health_result
                self.health_history[broker_id].append(
                    {
                        "timestamp": datetime.utcnow(),
                        "status": health_result.status,
                        "response_time": health_result.response_time,
                        "error_count": health_result.error_count,
                    }
                )

                # Keep history manageable (last 1000 checks)
                if len(self.health_history[broker_id]) > 1000:
                    self.health_history[broker_id] = self.health_history[broker_id][
                        -500:
                    ]

                # Detect status changes
                if previous_metrics and previous_metrics.status != health_result.status:
                    await self._handle_status_change(
                        broker_id, previous_metrics.status, health_result.status
                    )

                # Reset consecutive failures on success
                if health_result.status == HealthStatus.HEALTHY:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1

                # Update statistics
                self.total_health_checks += 1
                if health_result.status != HealthStatus.HEALTHY:
                    self.failed_health_checks += 1

                await asyncio.sleep(self.health_check_interval)

            except asyncio.CancelledError:
                logger.debug(f"Health monitoring cancelled for {broker_id}")
                break
            except Exception as e:
                logger.error(f"Health monitoring error for {broker_id}: {e}")
                consecutive_failures += 1
                await asyncio.sleep(self.health_check_interval)

    async def _perform_health_check(self, broker_id: str) -> BrokerHealthMetrics:
        """Perform comprehensive health check for broker."""
        start_time = time.perf_counter()

        try:
            adapter = self.broker_manager.get_adapter(broker_id)

            # Check basic connectivity
            if not hasattr(adapter, "is_connected") or not adapter.is_connected:
                return BrokerHealthMetrics(
                    broker_id=broker_id,
                    status=HealthStatus.UNHEALTHY,
                    response_time=0.0,
                    last_heartbeat=datetime.utcnow(),
                    error_count=self.health_metrics.get(
                        broker_id,
                        BrokerHealthMetrics(
                            broker_id, HealthStatus.UNKNOWN, 0.0, datetime.utcnow()
                        ),
                    ).error_count
                    + 1,
                    last_error="Not connected",
                )

            # Check heartbeat timing
            current_time = datetime.utcnow()
            if hasattr(adapter, "last_heartbeat"):
                heartbeat_age = (current_time - adapter.last_heartbeat).total_seconds()
                if heartbeat_age > self.heartbeat_timeout:
                    return BrokerHealthMetrics(
                        broker_id=broker_id,
                        status=HealthStatus.UNHEALTHY,
                        response_time=time.perf_counter() - start_time,
                        last_heartbeat=adapter.last_heartbeat,
                        error_count=self.health_metrics.get(
                            broker_id,
                            BrokerHealthMetrics(
                                broker_id, HealthStatus.UNKNOWN, 0.0, datetime.utcnow()
                            ),
                        ).error_count
                        + 1,
                        last_error=f"Stale heartbeat: {heartbeat_age:.1f}s",
                    )

            # Perform lightweight operation to test responsiveness
            try:
                # This would be a lightweight operation like getting connection status
                # For now, simulate with a small delay
                await asyncio.sleep(0.001)

                response_time = time.perf_counter() - start_time

                # Determine status based on response time
                if response_time < 1.0:
                    status = HealthStatus.HEALTHY
                elif response_time < 5.0:
                    status = HealthStatus.DEGRADED
                else:
                    status = HealthStatus.UNHEALTHY

                # Calculate uptime percentage
                current_metrics = self.health_metrics.get(broker_id)
                if current_metrics:
                    recent_history = self.health_history.get(broker_id, [])[
                        -100:
                    ]  # Last 100 checks
                    if recent_history:
                        healthy_count = sum(
                            1
                            for h in recent_history
                            if h["status"] == HealthStatus.HEALTHY
                        )
                        uptime_percentage = (healthy_count / len(recent_history)) * 100
                    else:
                        uptime_percentage = (
                            100.0 if status == HealthStatus.HEALTHY else 0.0
                        )
                else:
                    uptime_percentage = 100.0 if status == HealthStatus.HEALTHY else 0.0

                return BrokerHealthMetrics(
                    broker_id=broker_id,
                    status=status,
                    response_time=response_time,
                    last_heartbeat=getattr(adapter, "last_heartbeat", current_time),
                    error_count=(
                        0
                        if status == HealthStatus.HEALTHY
                        else (current_metrics.error_count if current_metrics else 0)
                    ),
                    uptime_percentage=uptime_percentage,
                    last_error=(
                        None if status == HealthStatus.HEALTHY else "Slow response"
                    ),
                )

            except asyncio.TimeoutError:
                return BrokerHealthMetrics(
                    broker_id=broker_id,
                    status=HealthStatus.UNHEALTHY,
                    response_time=self.response_timeout,
                    last_heartbeat=getattr(adapter, "last_heartbeat", current_time),
                    error_count=self.health_metrics.get(
                        broker_id,
                        BrokerHealthMetrics(
                            broker_id, HealthStatus.UNKNOWN, 0.0, datetime.utcnow()
                        ),
                    ).error_count
                    + 1,
                    last_error="Health check timeout",
                )

        except Exception as e:
            return BrokerHealthMetrics(
                broker_id=broker_id,
                status=HealthStatus.UNHEALTHY,
                response_time=time.perf_counter() - start_time,
                last_heartbeat=datetime.utcnow(),
                error_count=self.health_metrics.get(
                    broker_id,
                    BrokerHealthMetrics(
                        broker_id, HealthStatus.UNKNOWN, 0.0, datetime.utcnow()
                    ),
                ).error_count
                + 1,
                last_error=str(e),
            )

    async def _handle_status_change(
        self, broker_id: str, old_status: HealthStatus, new_status: HealthStatus
    ):
        """Handle broker status changes."""
        logger.info(
            f"Broker {broker_id} status changed: {old_status.value} → {new_status.value}"
        )

        # Trigger callbacks
        for callback in self.health_change_callbacks:
            try:
                await callback(broker_id, old_status, new_status)
            except Exception as e:
                logger.error(f"Health change callback error: {e}")

        # Handle specific transitions
        if old_status == HealthStatus.HEALTHY and new_status != HealthStatus.HEALTHY:
            # Broker failure
            for callback in self.failure_callbacks:
                try:
                    await callback(broker_id, new_status)
                except Exception as e:
                    logger.error(f"Failure callback error: {e}")

        elif old_status != HealthStatus.HEALTHY and new_status == HealthStatus.HEALTHY:
            # Broker recovery
            for callback in self.recovery_callbacks:
                try:
                    await callback(broker_id)
                except Exception as e:
                    logger.error(f"Recovery callback error: {e}")

    def get_broker_health(self, broker_id: str) -> Optional[BrokerHealthMetrics]:
        """Get current health metrics for broker."""
        return self.health_metrics.get(broker_id)

    def get_all_broker_health(self) -> Dict[str, BrokerHealthMetrics]:
        """Get health metrics for all brokers."""
        return self.health_metrics.copy()

    def get_health_history(
        self, broker_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get health history for broker."""
        history = self.health_history.get(broker_id, [])
        return history[-limit:] if history else []

    def get_monitoring_statistics(self) -> Dict[str, Any]:
        """Get health monitoring statistics."""
        healthy_brokers = sum(
            1
            for metrics in self.health_metrics.values()
            if metrics.status == HealthStatus.HEALTHY
        )

        return {
            "monitoring_active": self.monitoring,
            "monitored_brokers": len(self.health_metrics),
            "healthy_brokers": healthy_brokers,
            "total_health_checks": self.total_health_checks,
            "failed_health_checks": self.failed_health_checks,
            "success_rate": (
                (
                    (self.total_health_checks - self.failed_health_checks)
                    / self.total_health_checks
                    * 100
                )
                if self.total_health_checks > 0
                else 0
            ),
            "health_check_interval": self.health_check_interval,
            "heartbeat_timeout": self.heartbeat_timeout,
            "response_timeout": self.response_timeout,
        }
