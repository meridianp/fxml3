#!/usr/bin/env python3
"""
Test suite for infrastructure health monitoring system.
Retrospective tests for existing production infrastructure.
"""

import asyncio
import json

# Import the module under test
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import docker.errors
import pika.exceptions
import pytest
import redis.exceptions

sys.path.append(str(Path(__file__).parent.parent.parent / "scripts"))
from infrastructure_health_monitor import (
    DataQualityReport,
    HealthStatus,
    InfrastructureHealthMonitor,
)


class TestHealthStatusDataClass:
    """Test HealthStatus dataclass behavior."""

    def test_health_status_creation(self):
        """Test HealthStatus creation with all fields."""
        # Given: Valid health status data
        status = HealthStatus(
            service="redis",
            status="healthy",
            response_time_ms=150.5,
            last_check=datetime.utcnow(),
            details={"version": "6.2.7", "connected_clients": 2},
            alerts=["Test alert"],
        )

        # When: Accessing fields
        # Then: All fields are correctly stored
        assert status.service == "redis"
        assert status.status == "healthy"
        assert status.response_time_ms == 150.5
        assert isinstance(status.last_check, datetime)
        assert status.details["version"] == "6.2.7"
        assert status.alerts == ["Test alert"]


class TestDataQualityReportDataClass:
    """Test DataQualityReport dataclass behavior."""

    def test_data_quality_report_creation(self):
        """Test DataQualityReport creation with all metrics."""
        # Given: Valid data quality metrics
        report = DataQualityReport(
            symbol="EURUSD",
            latest_data_age_hours=2.5,
            data_gap_count=3,
            price_anomaly_count=1,
            volume_anomaly_count=0,
            completeness_score=0.95,
            quality_score=0.85,
        )

        # When: Accessing fields
        # Then: All metrics are correctly stored
        assert report.symbol == "EURUSD"
        assert report.latest_data_age_hours == 2.5
        assert report.data_gap_count == 3
        assert report.price_anomaly_count == 1
        assert report.volume_anomaly_count == 0
        assert report.completeness_score == 0.95
        assert report.quality_score == 0.85


class TestInfrastructureHealthMonitorInitialization:
    """Test monitor initialization and configuration."""

    def test_initialization_with_default_config(self):
        """Test monitor initialization with default configuration."""
        # Given: No custom config
        # When: Creating monitor
        monitor = InfrastructureHealthMonitor()

        # Then: Default config is applied
        assert monitor.config["redis_host"] == "localhost"
        assert monitor.config["redis_port"] == 6379
        assert monitor.config["rabbitmq_host"] == "localhost"
        assert monitor.config["rabbitmq_username"] == "fxml4"
        assert monitor.config["alert_thresholds"]["data_staleness_hours"] == 24
        assert hasattr(monitor, "docker_client")

    def test_initialization_with_custom_config(self):
        """Test monitor initialization with custom configuration."""
        # Given: Custom configuration
        custom_config = {
            "redis_host": "test-redis",
            "redis_port": 6380,
            "alert_thresholds": {
                "data_staleness_hours": 12,
                "response_time_threshold_ms": 500,
            },
        }

        # When: Creating monitor with custom config
        monitor = InfrastructureHealthMonitor(config=custom_config)

        # Then: Custom config is applied
        assert monitor.config["redis_host"] == "test-redis"
        assert monitor.config["redis_port"] == 6380
        assert monitor.config["alert_thresholds"]["data_staleness_hours"] == 12
        assert monitor.config["alert_thresholds"]["response_time_threshold_ms"] == 500


class TestRedisHealthCheck:
    """Test Redis connectivity and health checks."""

    @pytest.mark.asyncio
    @patch("redis.Redis")
    async def test_redis_health_check_success(self, mock_redis_class):
        """Test successful Redis health check."""
        # Given: Mock Redis client that works correctly
        mock_redis = Mock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = "test"
        mock_redis.delete.return_value = 1
        mock_redis.info.return_value = {
            "redis_version": "6.2.7",
            "connected_clients": 2,
            "used_memory_human": "1.2M",
            "uptime_in_seconds": 3600,
            "keyspace_hits": 100,
            "keyspace_misses": 10,
        }
        mock_redis_class.return_value = mock_redis

        monitor = InfrastructureHealthMonitor()

        # When: Checking Redis health
        result = await monitor.check_redis_health()

        # Then: Health check passes with expected results
        assert result.service == "redis"
        assert result.status == "healthy"
        assert result.response_time_ms > 0
        assert result.details["version"] == "6.2.7"
        assert result.details["connected_clients"] == 2
        assert result.alerts == []

    @pytest.mark.asyncio
    @patch("redis.Redis")
    async def test_redis_health_check_slow_response(self, mock_redis_class):
        """Test Redis health check with slow response time."""
        # Given: Mock Redis with slow response
        mock_redis = Mock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = "test"
        mock_redis.delete.return_value = 1
        mock_redis.info.return_value = {"redis_version": "6.2.7"}
        mock_redis_class.return_value = mock_redis

        # Simulate slow response by patching datetime
        with patch("scripts.infrastructure_health_monitor.datetime") as mock_datetime:
            start_time = datetime(2023, 1, 1, 12, 0, 0)
            end_time = datetime(2023, 1, 1, 12, 0, 2)  # 2 second delay = 2000ms
            mock_datetime.utcnow.side_effect = [
                start_time,
                end_time,
                end_time,
                end_time,
            ]

            monitor = InfrastructureHealthMonitor()

            # When: Checking Redis health
            result = await monitor.check_redis_health()

            # Then: Status is degraded due to slow response
            assert result.service == "redis"
            assert result.status == "degraded"
            assert result.response_time_ms == 2000.0
            assert len(result.alerts) == 1
            assert "High Redis response time" in result.alerts[0]

    @pytest.mark.asyncio
    @patch("redis.Redis")
    async def test_redis_health_check_connection_failure(self, mock_redis_class):
        """Test Redis health check with connection failure."""
        # Given: Mock Redis that raises connection error
        mock_redis_class.side_effect = redis.exceptions.ConnectionError(
            "Connection refused"
        )

        monitor = InfrastructureHealthMonitor()

        # When: Checking Redis health
        result = await monitor.check_redis_health()

        # Then: Status is unhealthy with error details
        assert result.service == "redis"
        assert result.status == "unhealthy"
        assert result.response_time_ms > 0
        assert result.details == {"error": "Connection refused"}
        assert len(result.alerts) == 1
        assert "Redis connection error" in result.alerts[0]


class TestRabbitMQHealthCheck:
    """Test RabbitMQ connectivity and health checks."""

    @pytest.mark.asyncio
    @patch("pika.BlockingConnection")
    async def test_rabbitmq_health_check_success(self, mock_connection_class):
        """Test successful RabbitMQ health check."""
        # Given: Mock RabbitMQ connection that works correctly
        mock_connection = Mock()
        mock_channel = Mock()
        mock_channel.queue_declare.return_value = Mock()
        mock_channel.queue_delete.return_value = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection_class.return_value = mock_connection

        monitor = InfrastructureHealthMonitor()

        # When: Checking RabbitMQ health
        result = await monitor.check_rabbitmq_health()

        # Then: Health check passes
        assert result.service == "rabbitmq"
        assert result.status == "healthy"
        assert result.response_time_ms > 0
        assert result.details["connection_state"] == "open"
        assert result.details["channel_state"] == "open"
        assert result.alerts == []
        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("pika.BlockingConnection")
    async def test_rabbitmq_health_check_connection_failure(
        self, mock_connection_class
    ):
        """Test RabbitMQ health check with connection failure."""
        # Given: Mock RabbitMQ that raises connection error
        mock_connection_class.side_effect = pika.exceptions.AMQPConnectionError(
            "Authentication failed"
        )

        monitor = InfrastructureHealthMonitor()

        # When: Checking RabbitMQ health
        result = await monitor.check_rabbitmq_health()

        # Then: Status is unhealthy with error details
        assert result.service == "rabbitmq"
        assert result.status == "unhealthy"
        assert result.response_time_ms > 0
        assert result.details == {"error": "Authentication failed"}
        assert len(result.alerts) == 1
        assert "RabbitMQ connection error" in result.alerts[0]


class TestDockerHealthCheck:
    """Test Docker container health monitoring."""

    @patch("docker.from_env")
    def test_docker_health_check_success(self, mock_docker):
        """Test successful Docker container health check."""
        # Given: Mock Docker client with healthy containers
        mock_container1 = Mock()
        mock_container1.name = "fxml4-api"
        mock_container1.status = "running"
        mock_container1.attrs = {
            "State": {"Health": {"Status": "healthy"}},
            "Created": "2023-01-01T12:00:00Z",
            "Config": {"Image": "fxml4:latest"},
        }

        mock_container2 = Mock()
        mock_container2.name = "fxml4-forex-rabbitmq"
        mock_container2.status = "running"
        mock_container2.attrs = {
            "State": {},
            "Created": "2023-01-01T12:00:00Z",
            "Config": {"Image": "rabbitmq:3.8-management"},
        }

        mock_client = Mock()
        mock_client.containers.list.return_value = [mock_container1, mock_container2]
        mock_docker.return_value = mock_client

        monitor = InfrastructureHealthMonitor()

        # When: Checking Docker health
        result = monitor.check_docker_containers()

        # Then: Health check passes
        assert result.service == "docker"
        assert result.status == "healthy"
        assert result.response_time_ms > 0
        assert "fxml4-api" in result.details
        assert "fxml4-forex-rabbitmq" in result.details
        assert result.details["fxml4-api"]["status"] == "running"
        assert result.details["fxml4-api"]["health"] == "healthy"
        assert result.alerts == []

    @patch("docker.from_env")
    def test_docker_health_check_unhealthy_container(self, mock_docker):
        """Test Docker health check with unhealthy container."""
        # Given: Mock Docker client with unhealthy container
        mock_container = Mock()
        mock_container.name = "fxml4-api"
        mock_container.status = "exited"
        mock_container.attrs = {
            "State": {"Health": {"Status": "unhealthy"}},
            "Created": "2023-01-01T12:00:00Z",
            "Config": {"Image": "fxml4:latest"},
        }

        mock_client = Mock()
        mock_client.containers.list.return_value = [mock_container]
        mock_docker.return_value = mock_client

        monitor = InfrastructureHealthMonitor()

        # When: Checking Docker health
        result = monitor.check_docker_containers()

        # Then: Status is degraded or unhealthy
        assert result.service == "docker"
        assert result.status in ["degraded", "unhealthy"]
        assert len(result.alerts) >= 1
        assert any("fxml4-api is exited" in alert for alert in result.alerts)

    @patch("docker.from_env")
    def test_docker_health_check_api_error(self, mock_docker):
        """Test Docker health check with API error."""
        # Given: Mock Docker client that raises API error
        mock_docker.side_effect = docker.errors.APIError("Docker daemon not running")

        monitor = InfrastructureHealthMonitor()

        # When: Checking Docker health
        result = monitor.check_docker_containers()

        # Then: Status is unhealthy with error details
        assert result.service == "docker"
        assert result.status == "unhealthy"
        assert result.details == {"error": "Docker daemon not running"}
        assert len(result.alerts) == 1
        assert "Docker API error" in result.alerts[0]


class TestSystemResourcesCheck:
    """Test system resource monitoring."""

    @patch("psutil.cpu_percent")
    @patch("psutil.virtual_memory")
    @patch("psutil.disk_usage")
    @patch("psutil.net_io_counters")
    def test_system_resources_healthy(self, mock_net, mock_disk, mock_memory, mock_cpu):
        """Test system resource check with healthy metrics."""
        # Given: Mock system metrics that are healthy
        mock_cpu.return_value = 45.0  # 45% CPU usage

        mock_memory_stats = Mock()
        mock_memory_stats.percent = 60.0  # 60% memory usage
        mock_memory_stats.available = 4 * (1024**3)  # 4GB available
        mock_memory.return_value = mock_memory_stats

        mock_disk_stats = Mock()
        mock_disk_stats.percent = 70.0  # 70% disk usage
        mock_disk_stats.free = 100 * (1024**3)  # 100GB free
        mock_disk.return_value = mock_disk_stats

        mock_net_stats = Mock()
        mock_net_stats.bytes_sent = 1024 * 1024
        mock_net_stats.bytes_recv = 2048 * 1024
        mock_net.return_value = mock_net_stats

        monitor = InfrastructureHealthMonitor()

        # When: Checking system resources
        result = monitor.check_system_resources()

        # Then: All metrics are healthy
        assert result.service == "system"
        assert result.status == "healthy"
        assert result.details["cpu_percent"] == 45.0
        assert result.details["memory_percent"] == 0.6
        assert result.details["disk_percent"] == 0.7
        assert result.alerts == []

    @patch("psutil.cpu_percent")
    @patch("psutil.virtual_memory")
    @patch("psutil.disk_usage")
    @patch("psutil.net_io_counters")
    def test_system_resources_alerts(self, mock_net, mock_disk, mock_memory, mock_cpu):
        """Test system resource check with alert conditions."""
        # Given: Mock system metrics that trigger alerts
        mock_cpu.return_value = 95.0  # High CPU usage

        mock_memory_stats = Mock()
        mock_memory_stats.percent = 85.0  # High memory usage (85% > 80% threshold)
        mock_memory_stats.available = 1 * (1024**3)  # 1GB available
        mock_memory.return_value = mock_memory_stats

        mock_disk_stats = Mock()
        mock_disk_stats.percent = 90.0  # High disk usage (90% > 85% threshold)
        mock_disk_stats.free = 10 * (1024**3)  # 10GB free
        mock_disk.return_value = mock_disk_stats

        mock_net_stats = Mock()
        mock_net_stats.bytes_sent = 1024 * 1024
        mock_net_stats.bytes_recv = 2048 * 1024
        mock_net.return_value = mock_net_stats

        monitor = InfrastructureHealthMonitor()

        # When: Checking system resources
        result = monitor.check_system_resources()

        # Then: Alerts are generated and status is degraded/unhealthy
        assert result.service == "system"
        assert result.status in ["degraded", "unhealthy"]
        assert len(result.alerts) == 3  # CPU, memory, disk alerts
        assert any("High CPU usage" in alert for alert in result.alerts)
        assert any("High memory usage" in alert for alert in result.alerts)
        assert any("High disk usage" in alert for alert in result.alerts)


class TestDataQualityAssessment:
    """Test data quality assessment functionality."""

    def test_data_quality_assessment_no_data(self, tmp_path):
        """Test data quality assessment when no data exists."""
        # Given: Monitor with non-existent data path
        config = {"data_path": str(tmp_path / "nonexistent")}
        monitor = InfrastructureHealthMonitor(config=config)

        # When: Assessing data quality
        result = monitor.assess_data_quality("EURUSD")

        # Then: Report indicates no data
        assert result.symbol == "EURUSD"
        assert result.latest_data_age_hours == 999999
        assert result.data_gap_count == 999
        assert result.completeness_score == 0.0
        assert result.quality_score == 0.0

    def test_data_quality_assessment_with_data(self, tmp_path):
        """Test data quality assessment with existing data files."""
        # Given: Temporary directory with some data files
        symbol_path = tmp_path / "C_EURUSD"
        symbol_path.mkdir(parents=True)

        # Create some data files for recent dates
        today = date.today()
        for i in range(5):  # Create 5 days of data
            day = today - timedelta(days=i)
            day_path = (
                symbol_path
                / f"year={day.year}"
                / f"month={day.month}"
                / f"day={day.day}"
            )
            day_path.mkdir(parents=True, exist_ok=True)
            (day_path / "data.parquet.gz").touch()

        # Skip some days to create gaps
        for i in range(10, 15):  # Skip days 10-15
            day = today - timedelta(days=i)
            day_path = (
                symbol_path
                / f"year={day.year}"
                / f"month={day.month}"
                / f"day={day.day}"
            )
            day_path.mkdir(parents=True, exist_ok=True)
            # Don't create data.parquet.gz file (gap)

        config = {"data_path": str(tmp_path)}
        monitor = InfrastructureHealthMonitor(config=config)

        # When: Assessing data quality
        result = monitor.assess_data_quality("EURUSD")

        # Then: Report shows realistic metrics
        assert result.symbol == "EURUSD"
        assert result.latest_data_age_hours < 48  # Within last 2 days
        assert result.data_gap_count > 0  # We created gaps
        assert 0 <= result.completeness_score <= 1
        assert 0 <= result.quality_score <= 1


class TestComprehensiveHealthCheck:
    """Test comprehensive health check orchestration."""

    @pytest.mark.asyncio
    @patch(
        "scripts.infrastructure_health_monitor.InfrastructureHealthMonitor.check_redis_health"
    )
    @patch(
        "scripts.infrastructure_health_monitor.InfrastructureHealthMonitor.check_rabbitmq_health"
    )
    @patch(
        "scripts.infrastructure_health_monitor.InfrastructureHealthMonitor.check_docker_containers"
    )
    @patch(
        "scripts.infrastructure_health_monitor.InfrastructureHealthMonitor.check_system_resources"
    )
    @patch(
        "scripts.infrastructure_health_monitor.InfrastructureHealthMonitor.assess_data_quality"
    )
    async def test_comprehensive_health_check_all_healthy(
        self, mock_data_quality, mock_system, mock_docker, mock_rabbitmq, mock_redis
    ):
        """Test comprehensive health check when all services are healthy."""
        # Given: All mock services return healthy status
        healthy_status = HealthStatus(
            service="test",
            status="healthy",
            response_time_ms=100.0,
            last_check=datetime.utcnow(),
            details={},
            alerts=[],
        )

        mock_redis.return_value = healthy_status._replace(service="redis")
        mock_rabbitmq.return_value = healthy_status._replace(service="rabbitmq")
        mock_docker.return_value = healthy_status._replace(service="docker")
        mock_system.return_value = healthy_status._replace(service="system")

        # Mock data quality
        quality_report = DataQualityReport(
            symbol="EURUSD",
            latest_data_age_hours=2.0,
            data_gap_count=0,
            price_anomaly_count=0,
            volume_anomaly_count=0,
            completeness_score=1.0,
            quality_score=0.9,
        )
        mock_data_quality.return_value = quality_report

        monitor = InfrastructureHealthMonitor()

        # When: Running comprehensive health check
        result = await monitor.run_comprehensive_health_check()

        # Then: Overall status is healthy
        assert result["overall_status"] == "healthy"
        assert result["summary"]["services_healthy"] == 4
        assert result["summary"]["services_degraded"] == 0
        assert result["summary"]["services_unhealthy"] == 0
        assert len(result["alerts"]) == 0
        assert "services" in result
        assert "data_quality" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    @patch(
        "scripts.infrastructure_health_monitor.InfrastructureHealthMonitor.check_redis_health"
    )
    @patch(
        "scripts.infrastructure_health_monitor.InfrastructureHealthMonitor.check_rabbitmq_health"
    )
    @patch(
        "scripts.infrastructure_health_monitor.InfrastructureHealthMonitor.check_docker_containers"
    )
    @patch(
        "scripts.infrastructure_health_monitor.InfrastructureHealthMonitor.check_system_resources"
    )
    @patch(
        "scripts.infrastructure_health_monitor.InfrastructureHealthMonitor.assess_data_quality"
    )
    async def test_comprehensive_health_check_mixed_status(
        self, mock_data_quality, mock_system, mock_docker, mock_rabbitmq, mock_redis
    ):
        """Test comprehensive health check with mixed service statuses."""
        # Given: Mixed service statuses
        mock_redis.return_value = HealthStatus(
            service="redis",
            status="healthy",
            response_time_ms=100.0,
            last_check=datetime.utcnow(),
            details={},
            alerts=[],
        )

        mock_rabbitmq.return_value = HealthStatus(
            service="rabbitmq",
            status="degraded",
            response_time_ms=150.0,
            last_check=datetime.utcnow(),
            details={},
            alerts=["Slow response"],
        )

        mock_docker.return_value = HealthStatus(
            service="docker",
            status="unhealthy",
            response_time_ms=200.0,
            last_check=datetime.utcnow(),
            details={},
            alerts=["Container down"],
        )

        mock_system.return_value = HealthStatus(
            service="system",
            status="healthy",
            response_time_ms=50.0,
            last_check=datetime.utcnow(),
            details={},
            alerts=[],
        )

        # Mock stale data quality
        stale_quality = DataQualityReport(
            symbol="EURUSD",
            latest_data_age_hours=30.0,  # Older than 24h threshold
            data_gap_count=5,
            price_anomaly_count=0,
            volume_anomaly_count=0,
            completeness_score=0.8,
            quality_score=0.6,  # Below 0.7 threshold
        )
        mock_data_quality.return_value = stale_quality

        monitor = InfrastructureHealthMonitor()

        # When: Running comprehensive health check
        result = await monitor.run_comprehensive_health_check()

        # Then: Overall status reflects mixed conditions
        assert result["overall_status"] == "unhealthy"  # Due to Docker being unhealthy
        assert result["summary"]["services_healthy"] == 2
        assert result["summary"]["services_degraded"] == 1
        assert result["summary"]["services_unhealthy"] == 1
        assert len(result["alerts"]) >= 3  # Service alerts + data quality alerts


class TestHealthReportPersistence:
    """Test health report saving and file operations."""

    def test_save_health_report_default_path(self):
        """Test saving health report with default file path."""
        # Given: Sample health report
        monitor = InfrastructureHealthMonitor()
        sample_report = {
            "timestamp": "2023-01-01T12:00:00",
            "overall_status": "healthy",
            "services": {},
            "alerts": [],
        }

        # When: Saving report without specifying path
        with patch("builtins.open", Mock()) as mock_open:
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            output_file = monitor.save_health_report(sample_report)

            # Then: File is saved with timestamp-based name
            assert output_file.startswith("/tmp/health_report_")
            assert output_file.endswith(".json")
            mock_open.assert_called_once()
            mock_file.write.assert_called()

    def test_save_health_report_custom_path(self):
        """Test saving health report with custom file path."""
        # Given: Sample health report and custom path
        monitor = InfrastructureHealthMonitor()
        sample_report = {
            "timestamp": "2023-01-01T12:00:00",
            "overall_status": "healthy",
        }
        custom_path = "/tmp/custom_health_report.json"

        # When: Saving report with custom path
        with patch("builtins.open", Mock()) as mock_open:
            output_file = monitor.save_health_report(sample_report, custom_path)

            # Then: Custom path is used
            assert output_file == custom_path
            mock_open.assert_called_with(custom_path, "w")


class TestProductionBehaviorValidation:
    """Test against known production behavior patterns."""

    @pytest.mark.integration
    def test_monitor_handles_real_config_structure(self):
        """Test monitor works with realistic production configuration."""
        # Given: Production-like configuration
        prod_config = {
            "redis_host": "localhost",
            "redis_port": 6379,
            "rabbitmq_host": "localhost",
            "rabbitmq_port": 5672,
            "rabbitmq_username": "fxml4",
            "rabbitmq_password": "fxml4_pass",
            "data_path": "/polygon/processed",
            "alert_thresholds": {
                "data_staleness_hours": 24,
                "response_time_threshold_ms": 1000,
                "disk_usage_threshold": 0.85,
                "memory_usage_threshold": 0.80,
            },
        }

        # When: Creating monitor with production config
        monitor = InfrastructureHealthMonitor(config=prod_config)

        # Then: Monitor is properly configured
        assert monitor.config["redis_host"] == "localhost"
        assert monitor.config["rabbitmq_username"] == "fxml4"
        assert monitor.config["alert_thresholds"]["data_staleness_hours"] == 24
        assert hasattr(monitor, "docker_client")

    def test_data_quality_major_pairs_structure(self):
        """Test data quality assessment for all major currency pairs."""
        # Given: Monitor and major currency pairs (production pattern)
        monitor = InfrastructureHealthMonitor()
        major_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD"]

        # When: Assessing data quality for all major pairs
        # Then: Each pair can be assessed without errors
        for symbol in major_pairs:
            result = monitor.assess_data_quality(symbol)
            assert isinstance(result, DataQualityReport)
            assert result.symbol == symbol
            assert isinstance(result.latest_data_age_hours, (int, float))
            assert isinstance(result.completeness_score, (int, float))
            assert 0 <= result.completeness_score <= 1
            assert 0 <= result.quality_score <= 1


@pytest.mark.slow
class TestPerformanceBehavior:
    """Test performance characteristics of monitoring system."""

    @pytest.mark.asyncio
    async def test_health_check_performance_timing(self):
        """Test that health checks complete within reasonable time."""
        # Given: Monitor instance
        monitor = InfrastructureHealthMonitor()

        # Mock external dependencies for performance test
        with patch.multiple(
            monitor,
            check_redis_health=AsyncMock(
                return_value=Mock(status="healthy", alerts=[])
            ),
            check_rabbitmq_health=AsyncMock(
                return_value=Mock(status="healthy", alerts=[])
            ),
            check_docker_containers=Mock(
                return_value=Mock(status="healthy", alerts=[])
            ),
            check_system_resources=Mock(return_value=Mock(status="healthy", alerts=[])),
            assess_data_quality=Mock(return_value=Mock(quality_score=0.9)),
        ):
            # When: Running comprehensive health check
            start_time = datetime.utcnow()
            await monitor.run_comprehensive_health_check()
            elapsed = (datetime.utcnow() - start_time).total_seconds()

            # Then: Check completes within reasonable time (< 30 seconds)
            assert elapsed < 30.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
