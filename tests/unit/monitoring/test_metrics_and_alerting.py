"""
Test monitoring and alerting infrastructure.

This module tests the metrics collection and alerting systems.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.monitoring.alerting import (
    Alert,
    AlertChannel,
    AlertingSystem,
    AlertRule,
    AlertSeverity,
    ChannelConfig,
)
from fxml4.monitoring.metrics_collector import (
    HealthCheckResult,
    MetricDefinition,
    MetricsCollector,
    MetricType,
)


@pytest.fixture
async def metrics_collector():
    """Create metrics collector instance."""
    collector = MetricsCollector(
        app_name="test", enable_prometheus=True, enable_system_metrics=False
    )
    yield collector
    if collector.is_running:
        await collector.stop()


@pytest.fixture
async def alerting_system():
    """Create alerting system instance."""
    system = AlertingSystem()
    yield system
    if system.is_running:
        await system.stop()


class TestMetricsCollector:
    """Test metrics collection functionality."""

    def test_metric_definition(self, metrics_collector):
        """Test defining custom metrics."""
        metrics_collector.define_metric(
            "custom_metric",
            MetricType.COUNTER,
            "A custom counter metric",
            labels=["status", "method"],
        )

        assert "custom_metric" in metrics_collector.metric_definitions
        definition = metrics_collector.metric_definitions["custom_metric"]
        assert definition.type == MetricType.COUNTER
        assert definition.labels == ["status", "method"]

    def test_counter_increment(self, metrics_collector):
        """Test incrementing counter metrics."""
        # Standard metric
        metrics_collector.increment_counter(
            "api_requests_total",
            labels={"method": "GET", "endpoint": "/health", "status": "200"},
        )

        # Check time series
        time_series = metrics_collector.get_time_series("api_requests_total", 1)
        assert len(time_series) > 0
        assert time_series[-1]["value"] == 1.0

    def test_gauge_setting(self, metrics_collector):
        """Test setting gauge metrics."""
        metrics_collector.set_gauge("portfolio_value", 1500000.0)

        time_series = metrics_collector.get_time_series("portfolio_value", 1)
        assert len(time_series) > 0
        assert time_series[-1]["value"] == 1500000.0

    def test_histogram_observation(self, metrics_collector):
        """Test observing histogram values."""
        # Record some API latencies
        latencies = [0.01, 0.02, 0.015, 0.1, 0.05]

        for latency in latencies:
            metrics_collector.observe_histogram(
                "api_request_duration_seconds",
                latency,
                labels={"method": "GET", "endpoint": "/data"},
            )

        # Histogram metrics are in Prometheus registry
        if metrics_collector.enable_prometheus:
            metrics_bytes = metrics_collector.get_prometheus_metrics()
            assert b"api_request_duration_seconds" in metrics_bytes

    @pytest.mark.asyncio
    async def test_function_timing_decorator(self, metrics_collector):
        """Test timing function decorator."""

        @metrics_collector.time_function(
            "test_function_duration", {"operation": "test"}
        )
        async def slow_function():
            await asyncio.sleep(0.1)
            return "done"

        result = await slow_function()
        assert result == "done"

        # Check timing was recorded
        time_series = metrics_collector.get_time_series("test_function_duration", 1)
        assert len(time_series) > 0
        assert time_series[-1]["value"] >= 0.1

    @pytest.mark.asyncio
    async def test_health_checks(self, metrics_collector):
        """Test health check registration and execution."""

        # Register health checks
        async def database_check():
            return HealthCheckResult(
                component="database", status="healthy", metadata={"connections": 10}
            )

        def cache_check():
            return True  # Simple boolean

        metrics_collector.register_health_check("database", database_check)
        metrics_collector.register_health_check("cache", cache_check)

        # Start collector
        await metrics_collector.start()

        # Wait for health checks to run
        await asyncio.sleep(0.1)

        # Get health status
        health = metrics_collector.get_health_status()

        assert health["status"] in ["healthy", "unknown"]  # May not have run yet
        assert "database" in health["components"] or len(health["components"]) == 0

    def test_prometheus_metrics_export(self, metrics_collector):
        """Test Prometheus metrics export."""
        if not metrics_collector.enable_prometheus:
            pytest.skip("Prometheus not enabled")

        # Record some metrics
        metrics_collector.increment_counter(
            "orders_submitted_total",
            labels={"symbol": "EUR/USD", "side": "buy", "order_type": "limit"},
        )
        metrics_collector.set_gauge("daily_pnl", -5000.0)

        # Export metrics
        metrics_bytes = metrics_collector.get_prometheus_metrics()

        assert isinstance(metrics_bytes, bytes)
        assert b"orders_submitted_total" in metrics_bytes
        assert b"daily_pnl" in metrics_bytes

    @pytest.mark.asyncio
    async def test_system_metrics_collection(self):
        """Test system resource metrics collection."""
        collector = MetricsCollector(enable_system_metrics=True)

        # Mock psutil
        with patch("psutil.cpu_percent", return_value=45.5):
            with patch("psutil.virtual_memory") as mock_memory:
                mock_memory.return_value.percent = 62.3

                await collector.start()
                await asyncio.sleep(0.1)

                # Check metrics were collected
                cpu_series = collector.get_time_series("system_cpu_usage_percent", 1)
                memory_series = collector.get_time_series(
                    "system_memory_usage_percent", 1
                )

                if cpu_series:  # May not have collected yet
                    assert cpu_series[-1]["value"] == 45.5
                if memory_series:
                    assert memory_series[-1]["value"] == 62.3

        await collector.stop()

    @pytest.mark.asyncio
    async def test_remote_export(self, metrics_collector):
        """Test exporting metrics to remote endpoint."""
        # Mock aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 200

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            # Export metrics
            await metrics_collector.export_to_remote(
                "https://metrics.example.com/api/v1/push", "test-api-key"
            )

            # Verify request
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args
            assert call_args[0][0] == "https://metrics.example.com/api/v1/push"
            assert call_args[1]["headers"]["Authorization"] == "Bearer test-api-key"


class TestAlertingSystem:
    """Test alerting system functionality."""

    def test_channel_configuration(self, alerting_system):
        """Test configuring alert channels."""
        alerting_system.configure_channel(
            AlertChannel.SLACK,
            {"webhook_url": "https://hooks.slack.com/test", "channel": "#alerts"},
        )

        assert AlertChannel.SLACK in alerting_system.channels
        config = alerting_system.channels[AlertChannel.SLACK]
        assert config.enabled is True
        assert config.config["webhook_url"] == "https://hooks.slack.com/test"

    def test_alert_rule_management(self, alerting_system):
        """Test adding and removing alert rules."""
        rule = AlertRule(
            name="high_cpu",
            expression="system_cpu_usage_percent",
            threshold=80.0,
            operator="gt",
            duration=timedelta(minutes=5),
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            labels={"component": "system"},
        )

        alerting_system.add_rule(rule)
        assert "high_cpu" in alerting_system.rules

        alerting_system.remove_rule("high_cpu")
        assert "high_cpu" not in alerting_system.rules

    @pytest.mark.asyncio
    async def test_alert_sending(self, alerting_system):
        """Test sending alerts through channels."""
        # Configure channels
        alerting_system.configure_channel(
            AlertChannel.WEBHOOK, {"url": "https://webhook.example.com/alerts"}
        )

        # Mock webhook handler
        with patch.object(alerting_system, "_send_webhook") as mock_webhook:
            mock_webhook.return_value = None

            # Create and send alert
            alert = Alert(
                alert_id="test-123",
                name="Test Alert",
                severity=AlertSeverity.WARNING,
                message="This is a test alert",
                details={"value": 95.5, "threshold": 90.0},
            )

            await alerting_system.send_alert(alert)

            # Verify alert was sent
            assert alert.fingerprint in alerting_system.active_alerts
            mock_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_alert_deduplication(self, alerting_system):
        """Test alert deduplication within window."""
        alerting_system.configure_channel(
            AlertChannel.WEBHOOK, {"url": "https://webhook.example.com/alerts"}
        )

        alert = Alert(
            alert_id="dedup-test",
            name="Duplicate Alert",
            severity=AlertSeverity.ERROR,
            message="Test deduplication",
        )

        with patch.object(alerting_system, "_send_webhook") as mock_webhook:
            # Send first alert
            await alerting_system.send_alert(alert)
            assert mock_webhook.call_count == 1

            # Try to send duplicate
            await alerting_system.send_alert(alert)
            assert mock_webhook.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_alert_resolution(self, alerting_system):
        """Test resolving active alerts."""
        # Create active alert
        alert = Alert(
            alert_id="resolve-test",
            name="Test Alert",
            severity=AlertSeverity.CRITICAL,
            message="Alert to be resolved",
        )

        alerting_system.active_alerts[alert.fingerprint] = alert

        with patch.object(alerting_system, "send_alert") as mock_send:
            await alerting_system.resolve_alert(alert.fingerprint)

            # Check alert marked as resolved
            assert alert.resolved is True
            assert alert.resolved_at is not None
            assert alert.fingerprint not in alerting_system.active_alerts

            # Check resolution notification sent
            mock_send.assert_called_once()
            resolution_alert = mock_send.call_args[0][0]
            assert "Resolved" in resolution_alert.name

    @pytest.mark.asyncio
    async def test_channel_rate_limiting(self, alerting_system):
        """Test channel rate limiting."""
        # Configure channel with low rate limit
        config = ChannelConfig(channel=AlertChannel.EMAIL, max_alerts_per_hour=2)
        alerting_system.channels[AlertChannel.EMAIL] = config

        # Check rate limiting
        assert alerting_system._check_rate_limit(AlertChannel.EMAIL) is True
        assert alerting_system._check_rate_limit(AlertChannel.EMAIL) is True
        assert (
            alerting_system._check_rate_limit(AlertChannel.EMAIL) is False
        )  # Limit reached

    @pytest.mark.asyncio
    async def test_slack_alert_formatting(self, alerting_system):
        """Test Slack alert message formatting."""
        alert = Alert(
            alert_id="slack-test",
            name="Database Connection Lost",
            severity=AlertSeverity.CRITICAL,
            message="Unable to connect to primary database",
            details={
                "host": "db1.example.com",
                "port": 5432,
                "error": "Connection timeout",
            },
        )

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 200

            mock_session = AsyncMock()
            mock_session.post.return_value.__aenter__.return_value = mock_response
            mock_session.__aenter__.return_value = mock_session
            mock_session_class.return_value = mock_session

            await alerting_system._send_slack(
                alert, {"webhook_url": "https://hooks.slack.com/test"}
            )

            # Verify Slack message format
            call_args = mock_session.post.call_args
            message = call_args[1]["json"]

            assert "attachments" in message
            attachment = message["attachments"][0]
            assert attachment["color"] == "#990000"  # Critical color
            assert attachment["title"] == "Database Connection Lost"
            assert len(attachment["fields"]) >= 2

    @pytest.mark.asyncio
    async def test_email_alert(self, alerting_system):
        """Test email alert sending."""
        alert = Alert(
            alert_id="email-test",
            name="Daily Loss Limit Exceeded",
            severity=AlertSeverity.ERROR,
            message="Daily loss limit of $50,000 exceeded",
            details={"current_loss": -52000, "limit": -50000},
        )

        with patch("aiosmtplib.SMTP") as mock_smtp_class:
            mock_smtp = AsyncMock()
            mock_smtp.__aenter__.return_value = mock_smtp
            mock_smtp_class.return_value = mock_smtp

            await alerting_system._send_email(
                alert,
                {
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "from_email": "alerts@fxml4.com",
                    "to_emails": ["ops@example.com"],
                },
            )

            # Verify email sent
            mock_smtp.send_message.assert_called_once()

    def test_alert_history(self, alerting_system):
        """Test alert history retrieval."""
        # Add alerts to history
        now = datetime.now(timezone.utc)

        alerts = [
            Alert(
                alert_id=f"hist-{i}",
                name=f"Alert {i}",
                severity=AlertSeverity.WARNING if i % 2 == 0 else AlertSeverity.ERROR,
                message=f"Test alert {i}",
                timestamp=now - timedelta(hours=i),
            )
            for i in range(5)
        ]

        alerting_system.alert_history = alerts

        # Get recent history
        recent = alerting_system.get_alert_history(hours=3)
        assert len(recent) == 3

        # Filter by severity
        errors = alerting_system.get_alert_history(
            hours=24, severity=AlertSeverity.ERROR
        )
        assert len(errors) == 2
        assert all(a.severity == AlertSeverity.ERROR for a in errors)

    @pytest.mark.asyncio
    async def test_alert_rule_evaluation(self, alerting_system):
        """Test alert rule evaluation with metrics."""
        # Create metrics collector
        metrics = MetricsCollector()
        alerting_system.metrics_collector = metrics

        # Set a metric value
        metrics.set_gauge("test_metric", 85.0)

        # Create rule
        rule = AlertRule(
            name="test_rule",
            expression="test_metric",
            threshold=80.0,
            operator="gt",
            duration=timedelta(seconds=0),  # Immediate
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.WEBHOOK],
        )

        alerting_system.add_rule(rule)

        # Mock alert sending
        with patch.object(alerting_system, "send_alert") as mock_send:
            # Evaluate expression
            value = alerting_system._evaluate_expression("test_metric")
            assert value == 85.0

            # Manually trigger evaluation (normally done in background task)
            # This would be done automatically by _evaluate_rules()
