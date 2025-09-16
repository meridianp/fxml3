"""
Comprehensive test suite for FXML4 monitoring and alerting system.

This test suite follows strict Test-Driven Development (TDD) methodology for
Phase 10: Production Deployment & Operations - Monitoring & Alerting Systems.

Tests cover:
- System health monitoring (CPU, memory, disk, network)
- Application performance monitoring (API response times, error rates)
- Database monitoring (query performance, connection pools)
- Business metrics monitoring (trade execution, signal generation)
- Multi-channel alerting (email, SMS, Slack, webhook)
- Alert severity levels and escalation policies
- Integration with Prometheus, Grafana, and AlertManager
- Kubernetes container health monitoring
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest


# Test fixtures for monitoring and alerting system components
@pytest.fixture
def monitoring_manager():
    """Create MonitoringManager instance for testing."""
    from fxml4.deployment.monitoring_manager import MonitoringManager

    return MonitoringManager()


@pytest.fixture
def alerting_manager():
    """Create AlertingManager instance for testing."""
    from fxml4.deployment.alerting_manager import AlertingManager

    return AlertingManager()


@pytest.fixture
def health_monitor():
    """Create SystemHealthMonitor instance for testing."""
    from fxml4.deployment.health_monitor import SystemHealthMonitor

    return SystemHealthMonitor()


@pytest.fixture
def metrics_collector():
    """Create MetricsCollector instance for testing."""
    from fxml4.deployment.metrics_collector import MetricsCollector

    return MetricsCollector()


@pytest.fixture
def dashboard_manager():
    """Create DashboardManager instance for testing."""
    from fxml4.deployment.dashboard_manager import DashboardManager

    return DashboardManager()


class TestSystemHealthMonitoring:
    """Test system health monitoring functionality."""

    @pytest.mark.asyncio
    async def test_cpu_utilization_monitoring(self, health_monitor):
        """Test CPU utilization monitoring and threshold detection."""
        await health_monitor.initialize()

        # Simulate normal CPU usage
        cpu_metrics = await health_monitor.collect_cpu_metrics()
        assert cpu_metrics["cpu_percent"] >= 0.0
        assert cpu_metrics["cpu_percent"] <= 100.0
        assert "cpu_count" in cpu_metrics
        assert "load_average" in cpu_metrics
        assert cpu_metrics["timestamp"] is not None

        # Test CPU threshold detection
        high_cpu_metrics = {
            "cpu_percent": 85.0,  # Above threshold
            "cpu_count": 8,
            "load_average": [4.2, 3.8, 3.5],
            "timestamp": datetime.utcnow(),
        }

        alert_triggered = await health_monitor.evaluate_cpu_thresholds(high_cpu_metrics)
        assert alert_triggered == True
        assert health_monitor.get_last_alert()["alert_type"] == "high_cpu_utilization"
        assert health_monitor.get_last_alert()["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_memory_utilization_monitoring(self, health_monitor):
        """Test memory utilization monitoring and leak detection."""
        await health_monitor.initialize()

        memory_metrics = await health_monitor.collect_memory_metrics()
        assert "memory_percent" in memory_metrics
        assert "memory_available" in memory_metrics
        assert "memory_used" in memory_metrics
        assert "swap_percent" in memory_metrics
        assert memory_metrics["memory_percent"] <= 100.0

        # Test memory leak detection
        memory_history = [
            {
                "memory_percent": 60.0,
                "timestamp": datetime.utcnow() - timedelta(minutes=10),
            },
            {
                "memory_percent": 65.0,
                "timestamp": datetime.utcnow() - timedelta(minutes=8),
            },
            {
                "memory_percent": 70.0,
                "timestamp": datetime.utcnow() - timedelta(minutes=6),
            },
            {
                "memory_percent": 75.0,
                "timestamp": datetime.utcnow() - timedelta(minutes=4),
            },
            {
                "memory_percent": 80.0,
                "timestamp": datetime.utcnow() - timedelta(minutes=2),
            },
            {"memory_percent": 85.0, "timestamp": datetime.utcnow()},
        ]

        leak_detected = await health_monitor.detect_memory_leak(memory_history)
        assert leak_detected == True
        assert health_monitor.get_memory_trend() == "increasing"
        assert health_monitor.get_memory_growth_rate() > 2.0  # 2% per minute

    @pytest.mark.asyncio
    async def test_disk_utilization_monitoring(self, health_monitor):
        """Test disk utilization and I/O monitoring."""
        await health_monitor.initialize()

        disk_metrics = await health_monitor.collect_disk_metrics()
        assert "disk_usage_percent" in disk_metrics
        assert "disk_free_gb" in disk_metrics
        assert "disk_io_read_bytes" in disk_metrics
        assert "disk_io_write_bytes" in disk_metrics
        assert "disk_io_read_time" in disk_metrics
        assert "disk_io_write_time" in disk_metrics

        # Test disk space alert thresholds
        high_disk_usage = {
            "disk_usage_percent": 92.0,  # Above 90% threshold
            "disk_free_gb": 2.5,
            "partition": "/var/lib/postgresql",
        }

        alert_triggered = await health_monitor.evaluate_disk_thresholds(high_disk_usage)
        assert alert_triggered == True
        assert health_monitor.get_last_alert()["alert_type"] == "high_disk_usage"
        assert health_monitor.get_last_alert()["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_network_monitoring(self, health_monitor):
        """Test network connectivity and bandwidth monitoring."""
        await health_monitor.initialize()

        network_metrics = await health_monitor.collect_network_metrics()
        assert "network_bytes_sent" in network_metrics
        assert "network_bytes_recv" in network_metrics
        assert "network_packets_sent" in network_metrics
        assert "network_packets_recv" in network_metrics
        assert "network_connections_active" in network_metrics

        # Test connectivity checks
        connectivity_results = await health_monitor.check_external_connectivity(
            [
                "polygon.io:443",
                "www.interactivebrokers.com:443",
                "tradingapi.fxcm.com:443",
            ]
        )

        for result in connectivity_results:
            assert "host" in result
            assert "port" in result
            assert "status" in result
            assert "response_time_ms" in result
            assert result["status"] in ["connected", "failed", "timeout"]


class TestApplicationPerformanceMonitoring:
    """Test application performance monitoring functionality."""

    @pytest.mark.asyncio
    async def test_api_response_time_monitoring(self, monitoring_manager):
        """Test API endpoint response time monitoring."""
        await monitoring_manager.initialize()

        # Simulate API endpoint monitoring
        api_metrics = await monitoring_manager.collect_api_metrics()

        expected_endpoints = [
            "/health",
            "/data",
            "/signals",
            "/backtest",
            "/trades",
            "/positions",
            "/orders",
        ]

        for endpoint in expected_endpoints:
            assert endpoint in api_metrics["endpoints"]
            endpoint_metrics = api_metrics["endpoints"][endpoint]
            assert "response_time_p95" in endpoint_metrics
            assert "response_time_p99" in endpoint_metrics
            assert "request_count" in endpoint_metrics
            assert "error_rate" in endpoint_metrics
            assert "throughput_rps" in endpoint_metrics

    @pytest.mark.asyncio
    async def test_error_rate_monitoring(self, monitoring_manager):
        """Test API error rate monitoring and threshold detection."""
        await monitoring_manager.initialize()

        # Simulate high error rate scenario
        error_metrics = {
            "total_requests": 1000,
            "error_4xx": 45,  # 4.5% error rate
            "error_5xx": 25,  # 2.5% error rate
            "total_errors": 70,
            "error_rate_percent": 7.0,  # Above 5% threshold
            "timeframe": "5m",
        }

        alert_triggered = await monitoring_manager.evaluate_error_rate_thresholds(
            error_metrics
        )
        assert alert_triggered == True
        assert monitoring_manager.get_last_alert()["alert_type"] == "high_error_rate"
        assert monitoring_manager.get_last_alert()["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_application_thread_monitoring(self, monitoring_manager):
        """Test application thread and process monitoring."""
        await monitoring_manager.initialize()

        thread_metrics = await monitoring_manager.collect_thread_metrics()
        assert "thread_count_active" in thread_metrics
        assert "thread_count_daemon" in thread_metrics
        assert "process_count" in thread_metrics
        assert "file_descriptors_used" in thread_metrics
        assert "file_descriptors_limit" in thread_metrics

        # Test thread pool health
        thread_pool_health = await monitoring_manager.evaluate_thread_pool_health()
        assert thread_pool_health["status"] in ["healthy", "warning", "critical"]
        assert "active_threads" in thread_pool_health
        assert "queue_size" in thread_pool_health


class TestDatabaseMonitoring:
    """Test database monitoring functionality."""

    @pytest.mark.asyncio
    async def test_database_connection_monitoring(self, monitoring_manager):
        """Test database connection pool monitoring."""
        await monitoring_manager.initialize()

        db_metrics = await monitoring_manager.collect_database_metrics()
        assert "connection_pool_size" in db_metrics
        assert "connections_active" in db_metrics
        assert "connections_idle" in db_metrics
        assert "connections_waiting" in db_metrics
        assert "query_response_time_avg" in db_metrics
        assert "slow_queries_count" in db_metrics

        # Test connection pool exhaustion detection
        connection_exhaustion_metrics = {
            "connection_pool_size": 20,
            "connections_active": 19,
            "connections_waiting": 8,  # High wait queue
            "utilization_percent": 95.0,
        }

        alert_triggered = await monitoring_manager.evaluate_db_connection_thresholds(
            connection_exhaustion_metrics
        )
        assert alert_triggered == True
        assert (
            monitoring_manager.get_last_alert()["alert_type"]
            == "db_connection_exhaustion"
        )

    @pytest.mark.asyncio
    async def test_query_performance_monitoring(self, monitoring_manager):
        """Test database query performance monitoring."""
        await monitoring_manager.initialize()

        # Test slow query detection
        slow_query_metrics = {
            "query_duration_ms": 2500,  # Above 2000ms threshold
            "query_type": "SELECT",
            "table_name": "market_data",
            "rows_examined": 1500000,
            "rows_returned": 1000,
            "query_hash": "abc123def456",
        }

        alert_triggered = await monitoring_manager.evaluate_query_performance(
            slow_query_metrics
        )
        assert alert_triggered == True
        assert (
            monitoring_manager.get_last_alert()["alert_type"] == "slow_database_query"
        )

        # Test database lock monitoring
        lock_metrics = await monitoring_manager.collect_database_lock_metrics()
        assert "deadlocks_count" in lock_metrics
        assert "lock_waits_count" in lock_metrics
        assert "lock_wait_time_avg" in lock_metrics


class TestBusinessMetricsMonitoring:
    """Test business metrics monitoring functionality."""

    @pytest.mark.asyncio
    async def test_trading_system_metrics(self, monitoring_manager):
        """Test trading system business metrics monitoring."""
        await monitoring_manager.initialize()

        trading_metrics = await monitoring_manager.collect_trading_metrics()
        assert "signals_generated_count" in trading_metrics
        assert "signals_generated_per_minute" in trading_metrics
        assert "trades_executed_count" in trading_metrics
        assert "trade_execution_latency_ms" in trading_metrics
        assert "order_fill_rate_percent" in trading_metrics
        assert "broker_connection_status" in trading_metrics

        # Test signal generation rate monitoring
        signal_rate_alert = await monitoring_manager.evaluate_signal_generation_rate(
            {
                "signals_per_minute": 0.2,  # Below expected 0.5/min threshold
                "timeframe": "15m",
            }
        )
        assert signal_rate_alert == True
        assert (
            monitoring_manager.get_last_alert()["alert_type"]
            == "low_signal_generation_rate"
        )

    @pytest.mark.asyncio
    async def test_market_data_monitoring(self, monitoring_manager):
        """Test market data feed monitoring."""
        await monitoring_manager.initialize()

        market_data_metrics = await monitoring_manager.collect_market_data_metrics()
        assert "price_updates_per_second" in market_data_metrics
        assert "data_latency_ms" in market_data_metrics
        assert "missing_ticks_count" in market_data_metrics
        assert "data_feed_status" in market_data_metrics

        # Test market data stale detection
        stale_data_metrics = {
            "last_update_timestamp": datetime.utcnow() - timedelta(minutes=8),
            "expected_update_interval_minutes": 1,
            "symbol": "GBPUSD",
        }

        alert_triggered = await monitoring_manager.evaluate_market_data_freshness(
            stale_data_metrics
        )
        assert alert_triggered == True
        assert monitoring_manager.get_last_alert()["alert_type"] == "stale_market_data"


class TestAlertingSystem:
    """Test alerting system functionality."""

    @pytest.mark.asyncio
    async def test_multi_channel_alerting(self, alerting_manager):
        """Test multi-channel alert delivery."""
        await alerting_manager.initialize()

        test_alert = {
            "alert_id": "test_alert_001",
            "alert_type": "high_cpu_utilization",
            "severity": "warning",
            "message": "CPU utilization is 85% (threshold: 80%)",
            "source": "health_monitor",
            "timestamp": datetime.utcnow(),
            "metadata": {"cpu_percent": 85.0, "hostname": "api-server-1"},
        }

        # Test email alert delivery
        email_result = await alerting_manager.send_email_alert(test_alert)
        assert email_result["sent"] == True
        assert email_result["channel"] == "email"
        assert "message_id" in email_result

        # Test SMS alert delivery
        sms_result = await alerting_manager.send_sms_alert(test_alert)
        assert sms_result["sent"] == True
        assert sms_result["channel"] == "sms"

        # Test Slack alert delivery
        slack_result = await alerting_manager.send_slack_alert(test_alert)
        assert slack_result["sent"] == True
        assert slack_result["channel"] == "slack"
        assert "slack_timestamp" in slack_result

    @pytest.mark.asyncio
    async def test_alert_severity_escalation(self, alerting_manager):
        """Test alert severity levels and escalation policies."""
        await alerting_manager.initialize()

        # Test escalation policy configuration
        escalation_config = {
            "info": {"channels": ["slack"], "delay_seconds": 0},
            "warning": {"channels": ["email", "slack"], "delay_seconds": 300},
            "critical": {
                "channels": ["email", "sms", "slack", "webhook"],
                "delay_seconds": 60,
            },
        }

        await alerting_manager.configure_escalation_policies(escalation_config)

        # Test critical alert escalation
        critical_alert = {
            "alert_type": "db_connection_failure",
            "severity": "critical",
            "message": "Database connection pool exhausted - trading halted",
            "source": "db_monitor",
        }

        escalation_result = await alerting_manager.execute_alert_escalation(
            critical_alert
        )
        assert len(escalation_result["channels_notified"]) == 4
        assert "email" in escalation_result["channels_notified"]
        assert "sms" in escalation_result["channels_notified"]
        assert "slack" in escalation_result["channels_notified"]
        assert "webhook" in escalation_result["channels_notified"]

    @pytest.mark.asyncio
    async def test_alert_suppression_and_correlation(self, alerting_manager):
        """Test alert suppression and correlation functionality."""
        await alerting_manager.initialize()

        # Test duplicate alert suppression
        duplicate_alerts = [
            {
                "alert_type": "high_memory_usage",
                "severity": "warning",
                "source": "server-1",
            },
            {
                "alert_type": "high_memory_usage",
                "severity": "warning",
                "source": "server-1",
            },
            {
                "alert_type": "high_memory_usage",
                "severity": "warning",
                "source": "server-1",
            },
        ]

        suppression_result = await alerting_manager.apply_alert_suppression(
            duplicate_alerts
        )
        assert suppression_result["alerts_sent"] == 1
        assert suppression_result["alerts_suppressed"] == 2
        assert "suppression_window_seconds" in suppression_result

        # Test alert correlation
        correlated_alerts = [
            {
                "alert_type": "high_cpu_utilization",
                "source": "server-1",
                "timestamp": datetime.utcnow(),
            },
            {
                "alert_type": "high_memory_usage",
                "source": "server-1",
                "timestamp": datetime.utcnow(),
            },
            {
                "alert_type": "slow_api_response",
                "source": "api-server-1",
                "timestamp": datetime.utcnow(),
            },
        ]

        correlation_result = await alerting_manager.correlate_alerts(correlated_alerts)
        assert correlation_result["correlation_found"] == True
        assert correlation_result["correlation_type"] == "resource_exhaustion"
        assert "root_cause_hypothesis" in correlation_result


class TestPrometheusIntegration:
    """Test Prometheus metrics integration."""

    @pytest.mark.asyncio
    async def test_prometheus_metrics_export(self, metrics_collector):
        """Test Prometheus metrics collection and export."""
        await metrics_collector.initialize()

        # Test custom metrics registration
        custom_metrics = [
            {
                "name": "fxml4_signals_generated_total",
                "type": "counter",
                "help": "Total signals generated",
            },
            {
                "name": "fxml4_trade_execution_duration_seconds",
                "type": "histogram",
                "help": "Trade execution duration",
            },
            {
                "name": "fxml4_active_positions",
                "type": "gauge",
                "help": "Current active positions",
            },
            {
                "name": "fxml4_api_requests_total",
                "type": "counter",
                "help": "Total API requests",
            },
        ]

        registration_result = await metrics_collector.register_custom_metrics(
            custom_metrics
        )
        assert registration_result["metrics_registered"] == len(custom_metrics)
        assert registration_result["registration_successful"] == True

        # Test metrics export
        prometheus_metrics = await metrics_collector.export_prometheus_metrics()
        assert len(prometheus_metrics) > 0

        for metric in prometheus_metrics:
            assert "name" in metric
            assert "value" in metric
            assert "labels" in metric
            assert "timestamp" in metric

    @pytest.mark.asyncio
    async def test_prometheus_alerting_rules(self, metrics_collector):
        """Test Prometheus alerting rules configuration."""
        await metrics_collector.initialize()

        alerting_rules = [
            {
                "alert": "FXML4HighErrorRate",
                "expr": 'rate(fxml4_api_requests_total{status=~"5.."}[5m]) > 0.05',
                "for": "2m",
                "labels": {"severity": "critical"},
                "annotations": {"summary": "FXML4 API error rate is above 5%"},
            },
            {
                "alert": "FXML4LowSignalGeneration",
                "expr": "rate(fxml4_signals_generated_total[15m]) < 0.008",  # <0.5/min
                "for": "5m",
                "labels": {"severity": "warning"},
                "annotations": {
                    "summary": "FXML4 signal generation rate is below expected threshold"
                },
            },
        ]

        rules_result = await metrics_collector.configure_alerting_rules(alerting_rules)
        assert rules_result["rules_configured"] == len(alerting_rules)
        assert rules_result["configuration_successful"] == True


class TestGrafanaDashboards:
    """Test Grafana dashboard integration."""

    @pytest.mark.asyncio
    async def test_dashboard_provisioning(self, dashboard_manager):
        """Test Grafana dashboard provisioning and configuration."""
        await dashboard_manager.initialize()

        # Test dashboard creation
        trading_dashboard_config = {
            "title": "FXML4 Trading System Overview",
            "panels": [
                {
                    "title": "Signal Generation Rate",
                    "type": "graph",
                    "metric": "fxml4_signals_generated_total",
                },
                {
                    "title": "Trade Execution Latency",
                    "type": "histogram",
                    "metric": "fxml4_trade_execution_duration_seconds",
                },
                {
                    "title": "Active Positions",
                    "type": "stat",
                    "metric": "fxml4_active_positions",
                },
                {
                    "title": "API Response Times",
                    "type": "graph",
                    "metric": "fxml4_api_response_duration_seconds",
                },
                {
                    "title": "System Resources",
                    "type": "graph",
                    "metric": "system_cpu_percent",
                },
            ],
        }

        dashboard_result = await dashboard_manager.create_dashboard(
            trading_dashboard_config
        )
        assert dashboard_result["dashboard_created"] == True
        assert "dashboard_url" in dashboard_result
        assert dashboard_result["panels_configured"] == len(
            trading_dashboard_config["panels"]
        )

    @pytest.mark.asyncio
    async def test_dashboard_automation(self, dashboard_manager):
        """Test automated dashboard updates and data source configuration."""
        await dashboard_manager.initialize()

        # Test data source configuration
        datasource_config = {
            "name": "FXML4-Prometheus",
            "type": "prometheus",
            "url": "http://prometheus:9090",
            "access": "proxy",
            "basicAuth": False,
        }

        datasource_result = await dashboard_manager.configure_datasource(
            datasource_config
        )
        assert datasource_result["datasource_configured"] == True
        assert datasource_result["connection_tested"] == True

        # Test automated dashboard refresh
        refresh_result = await dashboard_manager.refresh_dashboards()
        assert refresh_result["dashboards_refreshed"] > 0
        assert refresh_result["refresh_successful"] == True


class TestKubernetesIntegration:
    """Test Kubernetes monitoring integration."""

    @pytest.mark.asyncio
    async def test_pod_health_monitoring(self, monitoring_manager):
        """Test Kubernetes pod health monitoring."""
        await monitoring_manager.initialize()

        pod_metrics = await monitoring_manager.collect_kubernetes_pod_metrics()
        assert "pods_running" in pod_metrics
        assert "pods_pending" in pod_metrics
        assert "pods_failed" in pod_metrics
        assert "containers_ready" in pod_metrics
        assert "containers_restarts" in pod_metrics

        # Test pod restart detection
        restart_alert_result = await monitoring_manager.evaluate_pod_restart_thresholds(
            {
                "pod_name": "fxml4-api-deployment-abc123",
                "restart_count": 3,  # Above threshold
                "timeframe_minutes": 10,
            }
        )

        assert restart_alert_result == True
        assert monitoring_manager.get_last_alert()["alert_type"] == "pod_restart_loop"

    @pytest.mark.asyncio
    async def test_kubernetes_events_monitoring(self, monitoring_manager):
        """Test Kubernetes events monitoring and alerting."""
        await monitoring_manager.initialize()

        k8s_events = await monitoring_manager.collect_kubernetes_events()
        assert isinstance(k8s_events, list)

        # Test critical event detection
        critical_events = [
            {"type": "Warning", "reason": "Failed", "message": "Pod failed to start"},
            {
                "type": "Warning",
                "reason": "FailedScheduling",
                "message": "Insufficient CPU",
            },
            {
                "type": "Normal",
                "reason": "Scheduled",
                "message": "Pod scheduled successfully",
            },
        ]

        critical_event_result = await monitoring_manager.evaluate_kubernetes_events(
            critical_events
        )
        assert critical_event_result["critical_events_found"] == 2
        assert critical_event_result["alert_triggered"] == True


# Integration tests for complete monitoring and alerting workflow
class TestMonitoringAlertingIntegration:
    """Test complete monitoring and alerting system integration."""

    @pytest.mark.asyncio
    async def test_complete_monitoring_workflow(
        self, monitoring_manager, alerting_manager
    ):
        """Test complete monitoring and alerting workflow integration."""
        await monitoring_manager.initialize()
        await alerting_manager.initialize()

        # Simulate complete monitoring cycle
        monitoring_cycle_result = await monitoring_manager.execute_monitoring_cycle()

        assert monitoring_cycle_result["health_check_completed"] == True
        assert monitoring_cycle_result["metrics_collected"] == True
        assert monitoring_cycle_result["alerts_evaluated"] == True
        assert "monitoring_duration_seconds" in monitoring_cycle_result
        assert (
            monitoring_cycle_result["monitoring_duration_seconds"] < 30.0
        )  # Should complete quickly

        # Test alert delivery integration
        if monitoring_cycle_result["alerts_triggered"] > 0:
            alert_delivery_result = await alerting_manager.process_triggered_alerts()
            assert (
                alert_delivery_result["alerts_processed"]
                == monitoring_cycle_result["alerts_triggered"]
            )
            assert alert_delivery_result["delivery_successful"] == True

    @pytest.mark.asyncio
    async def test_monitoring_system_resilience(self, monitoring_manager):
        """Test monitoring system resilience and fault tolerance."""
        await monitoring_manager.initialize()

        # Test monitoring system behavior during external dependency failures
        failure_scenarios = [
            "prometheus_unavailable",
            "grafana_unavailable",
            "database_connection_failure",
            "kubernetes_api_unavailable",
        ]

        for scenario in failure_scenarios:
            resilience_result = await monitoring_manager.test_failure_scenario(scenario)
            assert resilience_result["monitoring_continued"] == True
            assert resilience_result["graceful_degradation"] == True
            assert "fallback_mechanism_activated" in resilience_result

    @pytest.mark.asyncio
    async def test_monitoring_performance_impact(self, monitoring_manager):
        """Test monitoring system performance impact on main application."""
        await monitoring_manager.initialize()

        # Measure monitoring overhead
        performance_impact = await monitoring_manager.measure_performance_impact()

        assert (
            performance_impact["cpu_overhead_percent"] < 5.0
        )  # Less than 5% CPU overhead
        assert (
            performance_impact["memory_overhead_mb"] < 100.0
        )  # Less than 100MB memory overhead
        assert (
            performance_impact["monitoring_latency_ms"] < 50.0
        )  # Less than 50ms latency
        assert performance_impact["impact_acceptable"] == True


# Performance and stress tests for monitoring system
@pytest.mark.performance
class TestMonitoringPerformance:
    """Test monitoring system performance under load."""

    @pytest.mark.asyncio
    async def test_high_volume_metrics_collection(self, metrics_collector):
        """Test metrics collection under high volume load."""
        await metrics_collector.initialize()

        # Simulate high volume metrics collection
        high_volume_result = await metrics_collector.simulate_high_volume_collection(
            metrics_per_second=1000, duration_seconds=60
        )

        assert (
            high_volume_result["metrics_collected"] >= 55000
        )  # Allow for some variance
        assert high_volume_result["collection_successful"] == True
        assert high_volume_result["average_collection_latency_ms"] < 10.0
        assert high_volume_result["memory_leak_detected"] == False

    @pytest.mark.asyncio
    async def test_concurrent_monitoring_operations(self, monitoring_manager):
        """Test concurrent monitoring operations performance."""
        await monitoring_manager.initialize()

        # Simulate concurrent monitoring operations
        concurrent_tasks = [
            monitoring_manager.collect_system_metrics(),
            monitoring_manager.collect_application_metrics(),
            monitoring_manager.collect_database_metrics(),
            monitoring_manager.collect_business_metrics(),
            monitoring_manager.evaluate_all_thresholds(),
        ]

        concurrent_results = await asyncio.gather(*concurrent_tasks)

        for result in concurrent_results:
            assert result["operation_successful"] == True
            assert result["execution_time_seconds"] < 5.0  # Each operation under 5s
