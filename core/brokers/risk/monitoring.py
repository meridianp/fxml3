"""
Real-time risk monitoring system.

This module provides real-time monitoring of risk metrics, alerts,
and dashboards for the trading system.
"""

import asyncio
import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from fxml4.brokers.risk.models import (
    PortfolioRiskMetrics,
    PositionRiskMetrics,
    RiskLimits,
    RiskViolationType,
)

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = 1
    WARNING = 2
    CRITICAL = 3
    EMERGENCY = 4


class MetricType(Enum):
    """Types of metrics to monitor."""

    POSITION_SIZE = "position_size"
    PORTFOLIO_VALUE = "portfolio_value"
    DAILY_PNL = "daily_pnl"
    LOSS_LIMIT = "loss_limit"
    ORDER_RATE = "order_rate"
    PRICE_DEVIATION = "price_deviation"
    MARKET_VOLATILITY = "market_volatility"
    SYSTEM_HEALTH = "system_health"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"


@dataclass
class RiskAlert:
    """Risk alert data structure."""

    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    metric_type: MetricType
    message: str
    details: Dict[str, Any]
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


@dataclass
class MetricSnapshot:
    """Point-in-time metric snapshot."""

    timestamp: datetime
    metric_type: MetricType
    value: float
    threshold: Optional[float] = None
    status: str = "normal"  # normal, warning, critical


@dataclass
class MonitoringConfig:
    """Configuration for risk monitoring."""

    # Monitoring intervals
    position_check_interval_seconds: int = 5
    portfolio_check_interval_seconds: int = 10
    system_health_check_interval_seconds: int = 30

    # Alert thresholds
    position_warning_pct: float = 80.0  # % of limit
    position_critical_pct: float = 95.0
    loss_warning_pct: float = 70.0
    loss_critical_pct: float = 90.0

    # Data retention
    metric_history_hours: int = 24
    alert_history_days: int = 7

    # Notification settings
    alert_cooldown_minutes: int = 15  # Prevent spam
    batch_alerts: bool = True
    max_alerts_per_batch: int = 10


class RiskMonitor:
    """Real-time risk monitoring system."""

    def __init__(self, config: Optional[MonitoringConfig] = None):
        """Initialize risk monitor."""
        self.config = config or MonitoringConfig()
        self.is_running = False

        # Metric storage
        self.metrics: Dict[MetricType, deque] = {
            metric_type: deque(maxlen=self._calculate_max_snapshots())
            for metric_type in MetricType
        }

        # Alert management
        self.active_alerts: Dict[str, RiskAlert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.alert_cooldowns: Dict[str, datetime] = {}

        # Subscribers
        self.metric_subscribers: Dict[MetricType, List[Callable]] = defaultdict(list)
        self.alert_subscribers: List[Callable] = []

        # Monitoring tasks
        self.monitoring_tasks: List[asyncio.Task] = []

        # Risk manager reference (set by risk manager)
        self.risk_manager = None

    def _calculate_max_snapshots(self) -> int:
        """Calculate max snapshots to keep based on retention."""
        # Assume 1 snapshot per second worst case
        return self.config.metric_history_hours * 3600

    async def start(self):
        """Start monitoring system."""
        if self.is_running:
            logger.warning("Risk monitor already running")
            return

        self.is_running = True
        logger.info("Starting risk monitoring system")

        # Start monitoring tasks
        self.monitoring_tasks = [
            asyncio.create_task(self._monitor_positions()),
            asyncio.create_task(self._monitor_portfolio()),
            asyncio.create_task(self._monitor_system_health()),
            asyncio.create_task(self._process_alerts()),
            asyncio.create_task(self._cleanup_old_data()),
        ]

        # Wait for all tasks
        try:
            await asyncio.gather(*self.monitoring_tasks)
        except asyncio.CancelledError:
            logger.info("Risk monitoring stopped")

    async def stop(self):
        """Stop monitoring system."""
        self.is_running = False

        # Cancel all tasks
        for task in self.monitoring_tasks:
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)

        logger.info("Risk monitoring system stopped")

    async def _monitor_positions(self):
        """Monitor individual position metrics."""
        while self.is_running:
            try:
                if self.risk_manager:
                    for symbol, position in self.risk_manager.positions.items():
                        # Check position size
                        metrics = self._calculate_position_metrics(position)

                        # Record metrics
                        self._record_metric(
                            MetricType.POSITION_SIZE,
                            metrics.notional,
                            threshold=self.risk_manager.limits.max_single_position_notional,
                        )

                        # Check for alerts
                        self._check_position_alerts(symbol, metrics)

                await asyncio.sleep(self.config.position_check_interval_seconds)

            except Exception as e:
                logger.error(f"Error monitoring positions: {e}")
                await asyncio.sleep(1)

    async def _monitor_portfolio(self):
        """Monitor portfolio-wide metrics."""
        while self.is_running:
            try:
                if self.risk_manager:
                    # Get portfolio metrics
                    metrics = self.risk_manager.get_portfolio_metrics()

                    # Record metrics
                    self._record_metric(
                        MetricType.PORTFOLIO_VALUE,
                        metrics.total_notional,
                        threshold=self.risk_manager.limits.max_portfolio_notional,
                    )

                    self._record_metric(
                        MetricType.DAILY_PNL,
                        self.risk_manager.loss_tracker.daily_loss,
                        threshold=-self.risk_manager.limits.max_daily_loss,
                    )

                    # Check for alerts
                    self._check_portfolio_alerts(metrics)

                await asyncio.sleep(self.config.portfolio_check_interval_seconds)

            except Exception as e:
                logger.error(f"Error monitoring portfolio: {e}")
                await asyncio.sleep(1)

    async def _monitor_system_health(self):
        """Monitor system health metrics."""
        while self.is_running:
            try:
                # Collect system metrics
                health_metrics = await self._collect_system_health()

                # Record metrics
                for metric_name, value in health_metrics.items():
                    if metric_name == "latency_ms":
                        self._record_metric(MetricType.LATENCY, value, threshold=100)
                    elif metric_name == "error_rate":
                        self._record_metric(
                            MetricType.ERROR_RATE, value, threshold=0.05
                        )
                    elif metric_name == "system_health_score":
                        self._record_metric(
                            MetricType.SYSTEM_HEALTH, value, threshold=0.8
                        )

                await asyncio.sleep(self.config.system_health_check_interval_seconds)

            except Exception as e:
                logger.error(f"Error monitoring system health: {e}")
                await asyncio.sleep(5)

    def _calculate_position_metrics(self, position) -> PositionRiskMetrics:
        """Calculate risk metrics for a position."""
        return PositionRiskMetrics(
            symbol=position.symbol,
            notional=abs(position.notional),
            unrealized_pnl=position.unrealized_pnl,
            var_95=position.notional * 0.02,  # Simplified VaR
            concentration_pct=(
                (
                    abs(position.notional)
                    / self.risk_manager.get_portfolio_metrics().total_notional
                    * 100
                )
                if self.risk_manager
                else 0
            ),
        )

    def _record_metric(
        self, metric_type: MetricType, value: float, threshold: Optional[float] = None
    ):
        """Record a metric snapshot."""
        # Determine status
        status = "normal"
        if threshold is not None:
            if metric_type in [MetricType.DAILY_PNL]:  # Negative is bad
                if value < threshold * self.config.loss_warning_pct / 100:
                    status = "warning"
                if value < threshold * self.config.loss_critical_pct / 100:
                    status = "critical"
            else:  # Positive threshold
                if value > threshold * self.config.position_warning_pct / 100:
                    status = "warning"
                if value > threshold * self.config.position_critical_pct / 100:
                    status = "critical"

        snapshot = MetricSnapshot(
            timestamp=datetime.now(timezone.utc),
            metric_type=metric_type,
            value=value,
            threshold=threshold,
            status=status,
        )

        self.metrics[metric_type].append(snapshot)

        # Notify subscribers
        for subscriber in self.metric_subscribers[metric_type]:
            try:
                subscriber(snapshot)
            except Exception as e:
                logger.error(f"Error notifying metric subscriber: {e}")

    def _check_position_alerts(self, symbol: str, metrics: PositionRiskMetrics):
        """Check if position metrics warrant alerts."""
        if not self.risk_manager:
            return

        # Position size alerts
        limit = self.risk_manager.limits.max_single_position_notional
        utilization = metrics.notional / limit * 100

        if utilization >= self.config.position_critical_pct:
            self._create_alert(
                severity=AlertSeverity.CRITICAL,
                metric_type=MetricType.POSITION_SIZE,
                message=f"Position {symbol} at {utilization:.1f}% of limit",
                details={
                    "symbol": symbol,
                    "notional": metrics.notional,
                    "limit": limit,
                    "utilization_pct": utilization,
                },
            )
        elif utilization >= self.config.position_warning_pct:
            self._create_alert(
                severity=AlertSeverity.WARNING,
                metric_type=MetricType.POSITION_SIZE,
                message=f"Position {symbol} approaching limit ({utilization:.1f}%)",
                details={
                    "symbol": symbol,
                    "notional": metrics.notional,
                    "limit": limit,
                    "utilization_pct": utilization,
                },
            )

    def _check_portfolio_alerts(self, metrics: PortfolioRiskMetrics):
        """Check if portfolio metrics warrant alerts."""
        if not self.risk_manager:
            return

        # Portfolio size alerts
        portfolio_limit = self.risk_manager.limits.max_portfolio_notional
        portfolio_utilization = metrics.total_notional / portfolio_limit * 100

        if portfolio_utilization >= self.config.position_critical_pct:
            self._create_alert(
                severity=AlertSeverity.CRITICAL,
                metric_type=MetricType.PORTFOLIO_VALUE,
                message=f"Portfolio at {portfolio_utilization:.1f}% of limit",
                details={
                    "total_notional": metrics.total_notional,
                    "limit": portfolio_limit,
                    "position_count": metrics.position_count,
                },
            )

        # Loss limit alerts
        daily_loss_limit = self.risk_manager.limits.max_daily_loss
        daily_loss = abs(self.risk_manager.loss_tracker.daily_loss)
        loss_utilization = (
            daily_loss / daily_loss_limit * 100 if daily_loss_limit > 0 else 0
        )

        if loss_utilization >= self.config.loss_critical_pct:
            self._create_alert(
                severity=AlertSeverity.EMERGENCY,
                metric_type=MetricType.LOSS_LIMIT,
                message=f"Daily loss at {loss_utilization:.1f}% of limit!",
                details={
                    "daily_loss": -daily_loss,
                    "limit": daily_loss_limit,
                    "remaining": daily_loss_limit - daily_loss,
                },
            )

    def _create_alert(
        self,
        severity: AlertSeverity,
        metric_type: MetricType,
        message: str,
        details: Dict[str, Any],
    ):
        """Create and dispatch an alert."""
        # Check cooldown
        cooldown_key = f"{metric_type}:{severity}:{message[:50]}"
        if cooldown_key in self.alert_cooldowns:
            if datetime.now(timezone.utc) < self.alert_cooldowns[cooldown_key]:
                return  # Skip due to cooldown

        # Create alert
        alert = RiskAlert(
            alert_id=f"ALERT_{datetime.now(timezone.utc).timestamp()}",
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            metric_type=metric_type,
            message=message,
            details=details,
        )

        # Store alert
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)

        # Set cooldown
        self.alert_cooldowns[cooldown_key] = datetime.now(timezone.utc) + timedelta(
            minutes=self.config.alert_cooldown_minutes
        )

        # Notify subscribers
        for subscriber in self.alert_subscribers:
            try:
                subscriber(alert)
            except Exception as e:
                logger.error(f"Error notifying alert subscriber: {e}")

        logger.warning(f"Risk alert: {severity.name} - {message}")

    async def _collect_system_health(self) -> Dict[str, float]:
        """Collect system health metrics."""
        metrics = {}

        try:
            # API latency
            if hasattr(self.risk_manager, "get_api_latency"):
                metrics["latency_ms"] = await self.risk_manager.get_api_latency()

            # Error rate
            if hasattr(self.risk_manager, "get_error_rate"):
                metrics["error_rate"] = self.risk_manager.get_error_rate()

            # Overall health score
            metrics["system_health_score"] = self._calculate_health_score(metrics)

        except Exception as e:
            logger.error(f"Error collecting system health: {e}")
            metrics["system_health_score"] = 0.5  # Degraded

        return metrics

    def _calculate_health_score(self, metrics: Dict[str, float]) -> float:
        """Calculate overall system health score (0-1)."""
        score = 1.0

        # Deduct for high latency
        if "latency_ms" in metrics:
            if metrics["latency_ms"] > 200:
                score -= 0.3
            elif metrics["latency_ms"] > 100:
                score -= 0.1

        # Deduct for errors
        if "error_rate" in metrics:
            score -= metrics["error_rate"] * 5  # 20% error rate = -1.0

        return max(0.0, min(1.0, score))

    async def _process_alerts(self):
        """Process and batch alerts."""
        while self.is_running:
            try:
                if self.config.batch_alerts:
                    # Collect alerts for batching
                    await asyncio.sleep(5)  # Batch window

                    # Process batched alerts
                    pending_alerts = [
                        alert
                        for alert in self.active_alerts.values()
                        if not alert.acknowledged
                    ]

                    if pending_alerts:
                        # Group by severity
                        by_severity = defaultdict(list)
                        for alert in pending_alerts:
                            by_severity[alert.severity].append(alert)

                        # Send batched notifications
                        for severity, alerts in by_severity.items():
                            if len(alerts) > self.config.max_alerts_per_batch:
                                alerts = alerts[: self.config.max_alerts_per_batch]

                            await self._send_batch_notification(severity, alerts)
                else:
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error processing alerts: {e}")
                await asyncio.sleep(1)

    async def _send_batch_notification(
        self, severity: AlertSeverity, alerts: List[RiskAlert]
    ):
        """Send batched alert notifications."""
        # Implementation would integrate with notification systems
        logger.info(f"Sending {len(alerts)} {severity.name} alerts")

    async def _cleanup_old_data(self):
        """Clean up old metrics and alerts."""
        while self.is_running:
            try:
                now = datetime.now(timezone.utc)

                # Clean old alerts
                cutoff_time = now - timedelta(days=self.config.alert_history_days)
                self.active_alerts = {
                    alert_id: alert
                    for alert_id, alert in self.active_alerts.items()
                    if alert.timestamp > cutoff_time
                }

                # Clean expired cooldowns
                self.alert_cooldowns = {
                    key: expiry
                    for key, expiry in self.alert_cooldowns.items()
                    if expiry > now
                }

                # Sleep for an hour
                await asyncio.sleep(3600)

            except Exception as e:
                logger.error(f"Error cleaning up old data: {e}")
                await asyncio.sleep(300)

    # Public API methods

    def subscribe_to_metric(self, metric_type: MetricType, callback: Callable):
        """Subscribe to metric updates."""
        self.metric_subscribers[metric_type].append(callback)

    def subscribe_to_alerts(self, callback: Callable):
        """Subscribe to risk alerts."""
        self.alert_subscribers.append(callback)

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Acknowledge an alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now(timezone.utc)
            return True
        return False

    def get_active_alerts(
        self, severity: Optional[AlertSeverity] = None
    ) -> List[RiskAlert]:
        """Get active alerts, optionally filtered by severity."""
        alerts = list(self.active_alerts.values())

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_metric_history(
        self, metric_type: MetricType, hours: Optional[int] = None
    ) -> List[MetricSnapshot]:
        """Get metric history."""
        snapshots = list(self.metrics[metric_type])

        if hours:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            snapshots = [s for s in snapshots if s.timestamp > cutoff]

        return snapshots

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring system status."""
        return {
            "is_running": self.is_running,
            "active_alerts": len(self.active_alerts),
            "critical_alerts": len(
                [
                    a
                    for a in self.active_alerts.values()
                    if a.severity >= AlertSeverity.CRITICAL
                ]
            ),
            "metric_counts": {
                metric_type.value: len(self.metrics[metric_type])
                for metric_type in MetricType
            },
            "last_update": datetime.now(timezone.utc).isoformat(),
        }

    def export_metrics(self, metric_type: MetricType, format: str = "json") -> str:
        """Export metrics for analysis."""
        snapshots = self.get_metric_history(metric_type)

        if format == "json":
            data = [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "value": s.value,
                    "threshold": s.threshold,
                    "status": s.status,
                }
                for s in snapshots
            ]
            return json.dumps(data, indent=2)

        elif format == "csv":
            lines = ["timestamp,value,threshold,status"]
            for s in snapshots:
                lines.append(
                    f"{s.timestamp.isoformat()},{s.value},{s.threshold},{s.status}"
                )
            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported format: {format}")
