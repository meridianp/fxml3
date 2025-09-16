"""
Alerting system for monitoring infrastructure.

This module provides a flexible alerting system that can:
- Send alerts via multiple channels (email, SMS, Slack, PagerDuty)
- Implement alert routing and escalation
- Support alert suppression and deduplication
- Integrate with monitoring metrics
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import aiohttp
import aiosmtplib

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class AlertChannel(Enum):
    """Alert notification channels."""

    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"


@dataclass
class Alert:
    """Alert data structure."""

    alert_id: str
    name: str
    severity: AlertSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fingerprint: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def __post_init__(self):
        """Generate fingerprint if not provided."""
        if not self.fingerprint:
            # Create fingerprint from name and labels
            data = f"{self.name}:{json.dumps(self.labels, sort_keys=True)}"
            self.fingerprint = hashlib.md5(data.encode()).hexdigest()


@dataclass
class AlertRule:
    """Alert rule configuration."""

    name: str
    expression: str  # Metric expression
    threshold: float
    operator: str  # gt, lt, eq, ne
    duration: timedelta
    severity: AlertSeverity
    channels: List[AlertChannel]
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    # Escalation
    escalation_delay: Optional[timedelta] = None
    escalation_severity: Optional[AlertSeverity] = None
    escalation_channels: List[AlertChannel] = field(default_factory=list)


@dataclass
class ChannelConfig:
    """Configuration for an alert channel."""

    channel: AlertChannel
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)

    # Rate limiting
    max_alerts_per_hour: int = 100

    # Filtering
    min_severity: AlertSeverity = AlertSeverity.INFO
    label_filters: Dict[str, str] = field(default_factory=dict)


class AlertingSystem:
    """
    Comprehensive alerting system for monitoring.
    """

    def __init__(self):
        """Initialize alerting system."""
        self.rules: Dict[str, AlertRule] = {}
        self.channels: Dict[AlertChannel, ChannelConfig] = {}
        self.active_alerts: Dict[str, Alert] = {}

        # Alert history
        self.alert_history: List[Alert] = []
        self.max_history_size = 10000

        # Deduplication
        self.recent_alerts: Dict[str, datetime] = {}
        self.dedup_window = timedelta(minutes=5)

        # Rate limiting
        self.channel_counters: Dict[str, List[datetime]] = {}

        # Notification handlers
        self.notification_handlers: Dict[AlertChannel, Callable] = {
            AlertChannel.EMAIL: self._send_email,
            AlertChannel.SMS: self._send_sms,
            AlertChannel.SLACK: self._send_slack,
            AlertChannel.PAGERDUTY: self._send_pagerduty,
            AlertChannel.WEBHOOK: self._send_webhook,
        }

        # Background tasks
        self.evaluation_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False

        # Metrics collector reference
        self.metrics_collector = None

    def configure_channel(
        self, channel: AlertChannel, config: Dict[str, Any], enabled: bool = True
    ):
        """Configure an alert channel."""
        self.channels[channel] = ChannelConfig(
            channel=channel, enabled=enabled, config=config
        )
        logger.info(f"Configured alert channel: {channel.value}")

    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")

    def remove_rule(self, rule_name: str):
        """Remove an alert rule."""
        if rule_name in self.rules:
            del self.rules[rule_name]
            logger.info(f"Removed alert rule: {rule_name}")

    async def start(self):
        """Start the alerting system."""
        self.is_running = True

        # Start evaluation task
        self.evaluation_task = asyncio.create_task(self._evaluate_rules())
        self.cleanup_task = asyncio.create_task(self._cleanup_old_alerts())

        logger.info("Alerting system started")

    async def stop(self):
        """Stop the alerting system."""
        self.is_running = False

        # Cancel tasks
        for task in [self.evaluation_task, self.cleanup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("Alerting system stopped")

    async def send_alert(self, alert: Alert):
        """Send an alert through configured channels."""
        # Check deduplication
        if self._is_duplicate(alert):
            logger.info(f"Alert deduplicated: {alert.fingerprint}")
            return

        # Record alert
        self.active_alerts[alert.fingerprint] = alert
        self.alert_history.append(alert)
        self.recent_alerts[alert.fingerprint] = alert.timestamp

        # Trim history if needed
        if len(self.alert_history) > self.max_history_size:
            self.alert_history = self.alert_history[-self.max_history_size :]

        # Determine channels based on severity
        channels_to_use = self._get_channels_for_alert(alert)

        # Send through each channel
        tasks = []
        for channel in channels_to_use:
            if self._check_rate_limit(channel):
                task = asyncio.create_task(self._send_to_channel(channel, alert))
                tasks.append(task)
            else:
                logger.warning(f"Rate limit exceeded for channel: {channel.value}")

        # Wait for all notifications
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def resolve_alert(self, fingerprint: str):
        """Mark an alert as resolved."""
        if fingerprint in self.active_alerts:
            alert = self.active_alerts[fingerprint]
            alert.resolved = True
            alert.resolved_at = datetime.now(timezone.utc)

            # Send resolution notification
            resolution_alert = Alert(
                alert_id=f"{alert.alert_id}_resolved",
                name=f"{alert.name} - Resolved",
                severity=AlertSeverity.INFO,
                message=f"Alert resolved: {alert.message}",
                details=alert.details,
                labels=alert.labels,
                fingerprint=fingerprint,
            )

            await self.send_alert(resolution_alert)

            # Remove from active alerts
            del self.active_alerts[fingerprint]

    def _is_duplicate(self, alert: Alert) -> bool:
        """Check if alert is a duplicate within dedup window."""
        if alert.fingerprint in self.recent_alerts:
            last_sent = self.recent_alerts[alert.fingerprint]
            if datetime.now(timezone.utc) - last_sent < self.dedup_window:
                return True
        return False

    def _get_channels_for_alert(self, alert: Alert) -> List[AlertChannel]:
        """Determine which channels to use for an alert."""
        channels = []

        for channel, config in self.channels.items():
            if not config.enabled:
                continue

            # Check severity threshold
            if alert.severity.value < config.min_severity.value:
                continue

            # Check label filters
            if config.label_filters:
                match = all(
                    alert.labels.get(k) == v for k, v in config.label_filters.items()
                )
                if not match:
                    continue

            channels.append(channel)

        return channels

    def _check_rate_limit(self, channel: AlertChannel) -> bool:
        """Check if channel rate limit allows sending."""
        config = self.channels.get(channel)
        if not config:
            return False

        key = channel.value
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)

        # Clean old entries
        if key in self.channel_counters:
            self.channel_counters[key] = [
                ts for ts in self.channel_counters[key] if ts > hour_ago
            ]
        else:
            self.channel_counters[key] = []

        # Check limit
        if len(self.channel_counters[key]) >= config.max_alerts_per_hour:
            return False

        # Record this alert
        self.channel_counters[key].append(now)
        return True

    async def _send_to_channel(self, channel: AlertChannel, alert: Alert):
        """Send alert to specific channel."""
        try:
            handler = self.notification_handlers.get(channel)
            if handler:
                config = self.channels.get(channel, {}).config
                await handler(alert, config)
                logger.info(f"Alert sent via {channel.value}: {alert.name}")
            else:
                logger.warning(f"No handler for channel: {channel.value}")
        except Exception as e:
            logger.error(f"Error sending alert via {channel.value}: {e}")

    async def _send_email(self, alert: Alert, config: Dict[str, Any]):
        """Send email alert."""
        smtp_host = config.get("smtp_host", "localhost")
        smtp_port = config.get("smtp_port", 587)
        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        from_email = config.get("from_email", "alerts@fxml4.com")
        to_emails = config.get("to_emails", [])

        if not to_emails:
            logger.warning("No email recipients configured")
            return

        # Create message
        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = ", ".join(to_emails)
        msg["Subject"] = f"[{alert.severity.name}] {alert.name}"

        # Body
        body = f"""
Alert: {alert.name}
Severity: {alert.severity.name}
Time: {alert.timestamp.isoformat()}

Message: {alert.message}

Details:
{json.dumps(alert.details, indent=2)}

Labels:
{json.dumps(alert.labels, indent=2)}
"""

        msg.attach(MIMEText(body, "plain"))

        # Send email
        async with aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port) as server:
            if smtp_user and smtp_password:
                await server.login(smtp_user, smtp_password)
            await server.send_message(msg)

    async def _send_slack(self, alert: Alert, config: Dict[str, Any]):
        """Send Slack alert."""
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            logger.warning("No Slack webhook URL configured")
            return

        # Color based on severity
        colors = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9900",
            AlertSeverity.ERROR: "#ff0000",
            AlertSeverity.CRITICAL: "#990000",
        }

        # Create Slack message
        message = {
            "attachments": [
                {
                    "color": colors.get(alert.severity, "#000000"),
                    "title": alert.name,
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert.severity.name,
                            "short": True,
                        },
                        {
                            "title": "Time",
                            "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                            "short": True,
                        },
                    ],
                    "footer": "FXML4 Alerting System",
                    "ts": int(alert.timestamp.timestamp()),
                }
            ]
        }

        # Add details as fields
        for key, value in alert.details.items():
            message["attachments"][0]["fields"].append(
                {"title": key, "value": str(value), "short": True}
            )

        # Send to Slack
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to send Slack alert: {resp.status}")

    async def _send_sms(self, alert: Alert, config: Dict[str, Any]):
        """Send SMS alert (placeholder - integrate with SMS provider)."""
        # This would integrate with Twilio, AWS SNS, etc.
        logger.info(f"SMS alert (not implemented): {alert.name}")

    async def _send_pagerduty(self, alert: Alert, config: Dict[str, Any]):
        """Send PagerDuty alert."""
        api_key = config.get("api_key")
        if not api_key:
            logger.warning("No PagerDuty API key configured")
            return

        # PagerDuty event
        event = {
            "routing_key": api_key,
            "event_action": "trigger" if not alert.resolved else "resolve",
            "dedup_key": alert.fingerprint,
            "payload": {
                "summary": alert.message,
                "severity": alert.severity.name.lower(),
                "source": "fxml4",
                "timestamp": alert.timestamp.isoformat(),
                "custom_details": alert.details,
            },
        }

        # Send to PagerDuty
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://events.pagerduty.com/v2/enqueue", json=event
            ) as resp:
                if resp.status not in [200, 202]:
                    logger.error(f"Failed to send PagerDuty alert: {resp.status}")

    async def _send_webhook(self, alert: Alert, config: Dict[str, Any]):
        """Send webhook alert."""
        url = config.get("url")
        if not url:
            logger.warning("No webhook URL configured")
            return

        # Prepare payload
        payload = {
            "alert_id": alert.alert_id,
            "name": alert.name,
            "severity": alert.severity.name,
            "message": alert.message,
            "details": alert.details,
            "labels": alert.labels,
            "timestamp": alert.timestamp.isoformat(),
            "fingerprint": alert.fingerprint,
            "resolved": alert.resolved,
        }

        # Add auth if configured
        headers = {}
        if "auth_header" in config and "auth_value" in config:
            headers[config["auth_header"]] = config["auth_value"]

        # Send webhook
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status not in [200, 201, 202]:
                    logger.error(f"Failed to send webhook alert: {resp.status}")

    async def _evaluate_rules(self):
        """Continuously evaluate alert rules."""
        while self.is_running:
            try:
                if not self.metrics_collector:
                    await asyncio.sleep(10)
                    continue

                for rule_name, rule in self.rules.items():
                    if not rule.enabled:
                        continue

                    try:
                        # Evaluate rule expression
                        # This is simplified - in production, use a proper expression evaluator
                        value = self._evaluate_expression(rule.expression)

                        # Check threshold
                        triggered = False
                        if rule.operator == "gt" and value > rule.threshold:
                            triggered = True
                        elif rule.operator == "lt" and value < rule.threshold:
                            triggered = True
                        elif rule.operator == "eq" and value == rule.threshold:
                            triggered = True
                        elif rule.operator == "ne" and value != rule.threshold:
                            triggered = True

                        if triggered:
                            # Check duration
                            key = f"{rule_name}:{rule.expression}"
                            if key not in self._rule_triggers:
                                self._rule_triggers[key] = datetime.now(timezone.utc)

                            trigger_duration = (
                                datetime.now(timezone.utc) - self._rule_triggers[key]
                            )

                            if trigger_duration >= rule.duration:
                                # Create alert
                                alert = Alert(
                                    alert_id=f"rule_{rule_name}_{int(datetime.now(timezone.utc).timestamp())}",
                                    name=rule.name,
                                    severity=rule.severity,
                                    message=rule.annotations.get(
                                        "summary",
                                        f"{rule.expression} {rule.operator} {rule.threshold}",
                                    ),
                                    details={
                                        "expression": rule.expression,
                                        "value": value,
                                        "threshold": rule.threshold,
                                        "operator": rule.operator,
                                    },
                                    labels=rule.labels,
                                )

                                await self.send_alert(alert)

                                # Reset trigger time
                                del self._rule_triggers[key]
                        else:
                            # Rule not triggered, check if we need to resolve
                            fingerprint = hashlib.md5(
                                f"{rule_name}:{json.dumps(rule.labels, sort_keys=True)}".encode()
                            ).hexdigest()

                            if fingerprint in self.active_alerts:
                                await self.resolve_alert(fingerprint)

                    except Exception as e:
                        logger.error(f"Error evaluating rule {rule_name}: {e}")

                await asyncio.sleep(10)  # Evaluate every 10 seconds

            except Exception as e:
                logger.error(f"Error in rule evaluation: {e}")
                await asyncio.sleep(10)

    # Rule trigger tracking
    _rule_triggers: Dict[str, datetime] = {}

    def _evaluate_expression(self, expression: str) -> float:
        """Evaluate a metric expression (simplified)."""
        # In production, use a proper expression parser
        # For now, just get the latest value from metrics
        if self.metrics_collector:
            # Extract metric name from expression
            metric_name = expression.split("[")[0].strip()
            time_series = self.metrics_collector.get_time_series(metric_name, 1)
            if time_series:
                return time_series[-1]["value"]
        return 0.0

    async def _cleanup_old_alerts(self):
        """Clean up old alerts and tracking data."""
        while self.is_running:
            try:
                now = datetime.now(timezone.utc)

                # Clean recent alerts cache
                expired_fingerprints = [
                    fp
                    for fp, ts in self.recent_alerts.items()
                    if now - ts > self.dedup_window
                ]
                for fp in expired_fingerprints:
                    del self.recent_alerts[fp]

                # Clean channel counters
                hour_ago = now - timedelta(hours=1)
                for channel in self.channel_counters:
                    self.channel_counters[channel] = [
                        ts for ts in self.channel_counters[channel] if ts > hour_ago
                    ]

                await asyncio.sleep(300)  # Clean every 5 minutes

            except Exception as e:
                logger.error(f"Error in cleanup: {e}")
                await asyncio.sleep(300)

    def get_alert_history(
        self, hours: int = 24, severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """Get alert history."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        alerts = [alert for alert in self.alert_history if alert.timestamp > cutoff]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_active_alerts(self) -> List[Alert]:
        """Get currently active alerts."""
        return list(self.active_alerts.values())
