#!/usr/bin/env python3
"""
FXML4 Infrastructure Health Monitor
Comprehensive monitoring system for data quality, broker connectivity, and system health.
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import pika
import psutil
import redis

import docker

# Add FXML4 to path
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/infrastructure_health.log"),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health status for a service."""

    service: str
    status: str  # healthy, degraded, unhealthy
    response_time_ms: float
    last_check: datetime
    details: Dict[str, Any]
    alerts: List[str]


@dataclass
class DataQualityReport:
    """Data quality assessment report."""

    symbol: str
    latest_data_age_hours: float
    data_gap_count: int
    price_anomaly_count: int
    volume_anomaly_count: int
    completeness_score: float  # 0-1
    quality_score: float  # 0-1


class InfrastructureHealthMonitor:
    """Comprehensive infrastructure health monitoring."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize health monitor."""
        self.config = config or {
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

        self.docker_client = docker.from_env()
        logger.info("Infrastructure Health Monitor initialized")

    async def check_redis_health(self) -> HealthStatus:
        """Check Redis connectivity and performance."""
        start_time = datetime.utcnow()
        alerts = []

        try:
            r = redis.Redis(
                host=self.config["redis_host"],
                port=self.config["redis_port"],
                decode_responses=True,
                socket_connect_timeout=5,
            )

            # Test basic operations
            test_key = f"health_check_{int(datetime.utcnow().timestamp())}"
            r.set(test_key, "test", ex=60)
            result = r.get(test_key)
            r.delete(test_key)

            # Get Redis info
            info = r.info()

            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            details = {
                "version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }

            # Check for performance issues
            if (
                response_time
                > self.config["alert_thresholds"]["response_time_threshold_ms"]
            ):
                alerts.append(f"High Redis response time: {response_time:.1f}ms")

            status = "healthy" if not alerts else "degraded"

        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            alerts.append(f"Redis connection error: {e}")
            status = "unhealthy"
            details = {"error": str(e)}

        return HealthStatus(
            service="redis",
            status=status,
            response_time_ms=response_time,
            last_check=datetime.utcnow(),
            details=details,
            alerts=alerts,
        )

    async def check_rabbitmq_health(self) -> HealthStatus:
        """Check RabbitMQ connectivity and queues."""
        start_time = datetime.utcnow()
        alerts = []

        try:
            # Test connection
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.config["rabbitmq_host"],
                    port=self.config["rabbitmq_port"],
                    credentials=pika.PlainCredentials(
                        self.config["rabbitmq_username"],
                        self.config["rabbitmq_password"],
                    ),
                    connection_attempts=3,
                    retry_delay=1,
                )
            )

            channel = connection.channel()

            # Get queue information (basic)
            method = channel.queue_declare(
                queue="health_check", passive=False, durable=False, auto_delete=True
            )
            channel.queue_delete(queue="health_check")

            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            details = {"connection_state": "open", "channel_state": "open"}

            connection.close()

            if (
                response_time
                > self.config["alert_thresholds"]["response_time_threshold_ms"]
            ):
                alerts.append(f"High RabbitMQ response time: {response_time:.1f}ms")

            status = "healthy" if not alerts else "degraded"

        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            alerts.append(f"RabbitMQ connection error: {e}")
            status = "unhealthy"
            details = {"error": str(e)}

        return HealthStatus(
            service="rabbitmq",
            status=status,
            response_time_ms=response_time,
            last_check=datetime.utcnow(),
            details=details,
            alerts=alerts,
        )

    def check_docker_containers(self) -> HealthStatus:
        """Check Docker container health."""
        start_time = datetime.utcnow()
        alerts = []
        container_details = {}

        try:
            containers = self.docker_client.containers.list(all=True)

            for container in containers:
                if any(
                    name in container.name.lower()
                    for name in ["fxml4", "rabbitmq", "redis", "fxcm"]
                ):
                    status = container.status
                    health = getattr(container.attrs.get("State", {}), "Health", {})
                    health_status = (
                        health.get("Status", "unknown") if health else "no_healthcheck"
                    )

                    container_details[container.name] = {
                        "status": status,
                        "health": health_status,
                        "created": container.attrs["Created"],
                        "image": container.attrs["Config"]["Image"],
                    }

                    if status != "running":
                        alerts.append(f"Container {container.name} is {status}")
                    elif health_status == "unhealthy":
                        alerts.append(f"Container {container.name} is unhealthy")

            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            status = (
                "healthy"
                if not alerts
                else ("degraded" if len(alerts) <= 2 else "unhealthy")
            )

        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            alerts.append(f"Docker API error: {e}")
            status = "unhealthy"
            container_details = {"error": str(e)}

        return HealthStatus(
            service="docker",
            status=status,
            response_time_ms=response_time,
            last_check=datetime.utcnow(),
            details=container_details,
            alerts=alerts,
        )

    def check_system_resources(self) -> HealthStatus:
        """Check system resource usage."""
        start_time = datetime.utcnow()
        alerts = []

        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent / 100

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent / 100

            # Network stats
            network = psutil.net_io_counters()

            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk_percent,
                "disk_free_gb": disk.free / (1024**3),
                "network_bytes_sent": network.bytes_sent,
                "network_bytes_recv": network.bytes_recv,
            }

            # Check thresholds
            if (
                memory_percent
                > self.config["alert_thresholds"]["memory_usage_threshold"]
            ):
                alerts.append(f"High memory usage: {memory_percent:.1%}")

            if disk_percent > self.config["alert_thresholds"]["disk_usage_threshold"]:
                alerts.append(f"High disk usage: {disk_percent:.1%}")

            if cpu_percent > 90:
                alerts.append(f"High CPU usage: {cpu_percent:.1f}%")

            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            status = (
                "healthy"
                if not alerts
                else ("degraded" if len(alerts) <= 1 else "unhealthy")
            )

        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            alerts.append(f"System monitoring error: {e}")
            status = "unhealthy"
            details = {"error": str(e)}

        return HealthStatus(
            service="system",
            status=status,
            response_time_ms=response_time,
            last_check=datetime.utcnow(),
            details=details,
            alerts=alerts,
        )

    def assess_data_quality(self, symbol: str) -> DataQualityReport:
        """Assess data quality for a specific symbol."""
        data_path = Path(self.config["data_path"]) / f"C_{symbol}"

        if not data_path.exists():
            return DataQualityReport(
                symbol=symbol,
                latest_data_age_hours=999999,
                data_gap_count=999,
                price_anomaly_count=0,
                volume_anomaly_count=0,
                completeness_score=0.0,
                quality_score=0.0,
            )

        try:
            # Find latest data
            latest_date = None
            total_files = 0
            missing_files = 0

            current_date = date.today() - timedelta(days=30)  # Check last 30 days
            end_date = date.today()

            while current_date <= end_date:
                expected_file = (
                    data_path
                    / f"year={current_date.year}"
                    / f"month={current_date.month}"
                    / f"day={current_date.day}"
                    / "data.parquet.gz"
                )

                total_files += 1
                if expected_file.exists():
                    latest_date = current_date
                else:
                    missing_files += 1

                current_date += timedelta(days=1)

            # Calculate metrics
            if latest_date:
                age_hours = (
                    datetime.now() - datetime.combine(latest_date, datetime.min.time())
                ).total_seconds() / 3600
            else:
                age_hours = 999999

            completeness_score = max(0, 1 - (missing_files / total_files))
            quality_score = max(0, 1 - (age_hours / (24 * 7)))  # Degrade over a week

            return DataQualityReport(
                symbol=symbol,
                latest_data_age_hours=age_hours,
                data_gap_count=missing_files,
                price_anomaly_count=0,  # TODO: Implement price anomaly detection
                volume_anomaly_count=0,  # TODO: Implement volume anomaly detection
                completeness_score=completeness_score,
                quality_score=quality_score,
            )

        except Exception as e:
            logger.error(f"Data quality assessment error for {symbol}: {e}")
            return DataQualityReport(
                symbol=symbol,
                latest_data_age_hours=999999,
                data_gap_count=999,
                price_anomaly_count=0,
                volume_anomaly_count=0,
                completeness_score=0.0,
                quality_score=0.0,
            )

    async def run_comprehensive_health_check(self) -> Dict[str, Any]:
        """Run complete infrastructure health check."""
        logger.info("Starting comprehensive health check...")

        # Run all health checks in parallel
        redis_check = asyncio.create_task(self.check_redis_health())
        rabbitmq_check = asyncio.create_task(self.check_rabbitmq_health())

        # Synchronous checks
        docker_status = self.check_docker_containers()
        system_status = self.check_system_resources()

        # Wait for async checks
        redis_status = await redis_check
        rabbitmq_status = await rabbitmq_check

        # Data quality checks for major pairs
        major_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD"]
        data_quality = {}

        for symbol in major_pairs:
            data_quality[symbol] = self.assess_data_quality(symbol)

        # Compile overall health
        all_statuses = [redis_status, rabbitmq_status, docker_status, system_status]

        healthy_count = sum(1 for s in all_statuses if s.status == "healthy")
        degraded_count = sum(1 for s in all_statuses if s.status == "degraded")

        if healthy_count == len(all_statuses):
            overall_status = "healthy"
        elif degraded_count + healthy_count == len(all_statuses):
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"

        # Collect all alerts
        all_alerts = []
        for status in all_statuses:
            all_alerts.extend(status.alerts)

        # Add data quality alerts
        for symbol, quality in data_quality.items():
            if (
                quality.latest_data_age_hours
                > self.config["alert_thresholds"]["data_staleness_hours"]
            ):
                all_alerts.append(
                    f"Stale data for {symbol}: {quality.latest_data_age_hours:.1f} hours old"
                )

            if quality.quality_score < 0.7:
                all_alerts.append(
                    f"Poor data quality for {symbol}: {quality.quality_score:.2f}"
                )

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": overall_status,
            "services": {
                "redis": redis_status.__dict__,
                "rabbitmq": rabbitmq_status.__dict__,
                "docker": docker_status.__dict__,
                "system": system_status.__dict__,
            },
            "data_quality": {
                symbol: quality.__dict__ for symbol, quality in data_quality.items()
            },
            "alerts": all_alerts,
            "summary": {
                "services_healthy": healthy_count,
                "services_degraded": degraded_count,
                "services_unhealthy": len(all_statuses)
                - healthy_count
                - degraded_count,
                "total_alerts": len(all_alerts),
            },
        }

        logger.info(
            f"Health check completed: {overall_status} status, {len(all_alerts)} alerts"
        )
        return report

    def save_health_report(
        self, report: Dict[str, Any], output_file: Optional[str] = None
    ):
        """Save health report to file."""
        if not output_file:
            output_file = (
                f"/tmp/health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Health report saved to {output_file}")
        return output_file


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="FXML4 Infrastructure Health Monitor")
    parser.add_argument("--output", "-o", help="Output file for health report")
    parser.add_argument(
        "--watch", action="store_true", help="Continuous monitoring mode"
    )
    parser.add_argument(
        "--interval", type=int, default=300, help="Monitoring interval in seconds"
    )

    args = parser.parse_args()

    monitor = InfrastructureHealthMonitor()

    if args.watch:
        logger.info(f"Starting continuous monitoring (interval: {args.interval}s)")
        while True:
            try:
                report = await monitor.run_comprehensive_health_check()
                output_file = monitor.save_health_report(report, args.output)

                # Print summary
                print(f"\\n{'='*60}")
                print(
                    f"Health Check Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                print(f"{'='*60}")
                print(f"Overall Status: {report['overall_status'].upper()}")
                print(f"Services Healthy: {report['summary']['services_healthy']}")
                print(f"Services Degraded: {report['summary']['services_degraded']}")
                print(f"Services Unhealthy: {report['summary']['services_unhealthy']}")
                print(f"Total Alerts: {report['summary']['total_alerts']}")

                if report["alerts"]:
                    print("\\nActive Alerts:")
                    for alert in report["alerts"][:5]:  # Show first 5 alerts
                        print(f"  🚨 {alert}")
                    if len(report["alerts"]) > 5:
                        print(f"  ... and {len(report['alerts']) - 5} more")

                print(f"\\nReport saved: {output_file}")
                print(f"Next check in {args.interval} seconds...")

                await asyncio.sleep(args.interval)

            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(args.interval)
    else:
        # Single check
        report = await monitor.run_comprehensive_health_check()
        output_file = monitor.save_health_report(report, args.output)

        # Print formatted output
        print(json.dumps(report, indent=2, default=str))
        print(f"\\nReport saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
