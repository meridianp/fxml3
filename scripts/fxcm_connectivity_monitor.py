#!/usr/bin/env python3
"""
FXCM Real-time Connectivity Monitor

Continuously monitors FXCM broker connectivity and provides:
- Real-time connection status
- Market data flow monitoring
- Latency tracking
- Error detection and alerting
- Performance metrics
- Connection recovery
"""

import asyncio
import json
import logging
import signal
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fxml4.brokers.adapters.fxcm_demo_adapter import FXCMDemoAdapter

# Import paths handled by PYTHONPATH wrapper


@dataclass
class ConnectionHealth:
    """Connection health status."""

    is_connected: bool
    last_successful_request: Optional[datetime]
    consecutive_failures: int
    total_requests: int
    successful_requests: int
    avg_latency_ms: float
    last_error: Optional[str]


@dataclass
class MonitoringAlert:
    """Monitoring alert."""

    timestamp: datetime
    alert_type: str
    severity: str  # INFO, WARNING, ERROR, CRITICAL
    message: str
    details: Dict[str, Any]


class FXCMConnectivityMonitor:
    """Real-time FXCM connectivity monitoring."""

    def __init__(self, config_path: str = None):
        """Initialize the connectivity monitor."""
        self.adapter = None
        self.running = False
        self.start_time = datetime.utcnow()

        # Monitoring configuration
        self.config = {
            "check_interval": 5,  # seconds between checks
            "market_data_symbols": [
                "EUR/USD",
                "GBP/USD",
                "USD/JPY",
                "USD/CHF",
                "AUD/USD",
            ],
            "latency_threshold_ms": 2000,  # Alert if latency > 2 seconds
            "failure_threshold": 5,  # Alert after 5 consecutive failures
            "recovery_attempts": 3,  # Number of reconnection attempts
            "recovery_delay": 10,  # Delay between recovery attempts
            "alert_cooldown": 300,  # 5 minutes between duplicate alerts
        }

        # Monitoring state
        self.health = ConnectionHealth(
            is_connected=False,
            last_successful_request=None,
            consecutive_failures=0,
            total_requests=0,
            successful_requests=0,
            avg_latency_ms=0.0,
            last_error=None,
        )

        # Performance tracking
        self.latency_history = []
        self.error_history = []
        self.alerts_sent = []

        # Market data monitoring
        self.last_market_data_update = {}
        self.market_data_update_count = 0

        # Setup logging
        self.setup_logging()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def setup_logging(self):
        """Setup monitoring logging."""
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(
                    f'fxcm_monitor_{datetime.now().strftime("%Y%m%d")}.log'
                ),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False

    async def start_monitoring(self):
        """Start the connectivity monitoring."""
        self.running = True
        self.logger.info("🚀 Starting FXCM Connectivity Monitor")
        self.logger.info(f"Configuration: {self.config}")

        try:
            # Initial connection
            await self.establish_connection()

            # Start monitoring tasks
            monitoring_tasks = await asyncio.gather(
                self.connection_health_monitor(),
                self.market_data_monitor(),
                self.performance_tracker(),
                self.alert_manager(),
                return_exceptions=True,
            )

        except Exception as e:
            self.logger.error(f"Monitor failed: {e}")
        finally:
            await self.cleanup()

    async def establish_connection(self):
        """Establish initial connection to FXCM."""
        self.logger.info("🔌 Establishing connection to FXCM...")

        try:
            self.adapter = FXCMDemoAdapter()
            connected = await self.adapter.connect()

            if connected:
                self.health.is_connected = True
                self.health.last_successful_request = datetime.utcnow()
                self.health.consecutive_failures = 0
                self.logger.info(f"✅ Connected to FXCM: {self.adapter.server}")
                self.logger.info(f"📧 Account: {self.adapter.username}")

                await self.send_alert(
                    MonitoringAlert(
                        timestamp=datetime.utcnow(),
                        alert_type="connection",
                        severity="INFO",
                        message="Successfully connected to FXCM broker",
                        details={
                            "server": self.adapter.server,
                            "username": self.adapter.username,
                            "session_id": self.adapter.session_id,
                        },
                    )
                )

            else:
                raise Exception("Failed to establish connection")

        except Exception as e:
            self.health.is_connected = False
            self.health.last_error = str(e)
            self.health.consecutive_failures += 1
            self.logger.error(f"❌ Connection failed: {e}")

            await self.send_alert(
                MonitoringAlert(
                    timestamp=datetime.utcnow(),
                    alert_type="connection",
                    severity="ERROR",
                    message=f"Failed to connect to FXCM broker: {e}",
                    details={"error": str(e)},
                )
            )

    async def connection_health_monitor(self):
        """Monitor basic connection health."""
        self.logger.info("🔍 Starting connection health monitoring...")

        while self.running:
            try:
                await self.check_connection_health()
                await asyncio.sleep(self.config["check_interval"])

            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(self.config["check_interval"])

    async def check_connection_health(self):
        """Perform connection health check."""
        if not self.adapter:
            await self.attempt_recovery()
            return

        start_time = time.time()
        self.health.total_requests += 1

        try:
            # Test basic connectivity
            account_info = await self.adapter.get_account_info()

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            self.latency_history.append(latency_ms)

            # Keep only last 100 samples
            if len(self.latency_history) > 100:
                self.latency_history = self.latency_history[-100:]

            # Update health status
            self.health.is_connected = True
            self.health.last_successful_request = datetime.utcnow()
            self.health.consecutive_failures = 0
            self.health.successful_requests += 1
            self.health.avg_latency_ms = statistics.mean(self.latency_history)

            # Check latency threshold
            if latency_ms > self.config["latency_threshold_ms"]:
                await self.send_alert(
                    MonitoringAlert(
                        timestamp=datetime.utcnow(),
                        alert_type="performance",
                        severity="WARNING",
                        message=f"High latency detected: {latency_ms:.2f}ms",
                        details={
                            "current_latency_ms": latency_ms,
                            "threshold_ms": self.config["latency_threshold_ms"],
                            "avg_latency_ms": self.health.avg_latency_ms,
                        },
                    )
                )

            # Log periodic status
            if self.health.total_requests % 50 == 0:
                success_rate = (
                    self.health.successful_requests / self.health.total_requests
                ) * 100
                self.logger.info(
                    f"📊 Health Check #{self.health.total_requests}: "
                    f"Success Rate: {success_rate:.1f}%, "
                    f"Avg Latency: {self.health.avg_latency_ms:.2f}ms"
                )

        except Exception as e:
            # Record failure
            self.health.consecutive_failures += 1
            self.health.last_error = str(e)
            self.error_history.append(
                {
                    "timestamp": datetime.utcnow(),
                    "error": str(e),
                    "request_number": self.health.total_requests,
                }
            )

            self.logger.warning(f"⚠️ Health check failed: {e}")

            # Check failure threshold
            if self.health.consecutive_failures >= self.config["failure_threshold"]:
                self.health.is_connected = False

                await self.send_alert(
                    MonitoringAlert(
                        timestamp=datetime.utcnow(),
                        alert_type="connection",
                        severity="CRITICAL",
                        message=f"Connection lost after {self.health.consecutive_failures} consecutive failures",
                        details={
                            "consecutive_failures": self.health.consecutive_failures,
                            "last_error": str(e),
                            "total_requests": self.health.total_requests,
                            "success_rate": (
                                self.health.successful_requests
                                / self.health.total_requests
                            )
                            * 100,
                        },
                    )
                )

                # Attempt recovery
                await self.attempt_recovery()

    async def market_data_monitor(self):
        """Monitor market data streaming."""
        self.logger.info("📈 Starting market data monitoring...")

        market_data_callback_count = 0
        last_data_time = {}

        async def data_callback(data):
            nonlocal market_data_callback_count
            market_data_callback_count += 1
            self.market_data_update_count = market_data_callback_count

            current_time = datetime.utcnow()

            for symbol, prices in data.items():
                self.last_market_data_update[symbol] = {
                    "timestamp": current_time,
                    "bid": prices.get("bid", 0),
                    "ask": prices.get("ask", 0),
                    "update_number": market_data_callback_count,
                }

                # Check for stale data
                if symbol in last_data_time:
                    time_since_last = (
                        current_time - last_data_time[symbol]
                    ).total_seconds()
                    if time_since_last > 30:  # No update for 30 seconds
                        await self.send_alert(
                            MonitoringAlert(
                                timestamp=current_time,
                                alert_type="market_data",
                                severity="WARNING",
                                message=f"Stale market data for {symbol}",
                                details={
                                    "symbol": symbol,
                                    "seconds_since_last_update": time_since_last,
                                    "last_update": last_data_time[symbol].isoformat(),
                                },
                            )
                        )

                last_data_time[symbol] = current_time

        while self.running:
            try:
                if self.adapter and self.health.is_connected:
                    # Start market data streaming
                    await self.adapter.start_market_data_stream(
                        self.config["market_data_symbols"], data_callback
                    )

                    # Let it stream for a while
                    await asyncio.sleep(30)

                    # Check if we received data
                    if market_data_callback_count == 0:
                        await self.send_alert(
                            MonitoringAlert(
                                timestamp=datetime.utcnow(),
                                alert_type="market_data",
                                severity="ERROR",
                                message="No market data received",
                                details={"symbols": self.config["market_data_symbols"]},
                            )
                        )
                else:
                    await asyncio.sleep(10)

            except Exception as e:
                self.logger.error(f"Market data monitor error: {e}")
                await asyncio.sleep(10)

    async def performance_tracker(self):
        """Track and log performance metrics."""
        self.logger.info("⚡ Starting performance tracking...")

        while self.running:
            try:
                # Calculate current metrics
                uptime = (datetime.utcnow() - self.start_time).total_seconds()
                success_rate = (
                    (self.health.successful_requests / self.health.total_requests * 100)
                    if self.health.total_requests > 0
                    else 0
                )

                # Log performance summary every 5 minutes
                await asyncio.sleep(300)

                self.logger.info("📊 Performance Summary:")
                self.logger.info(f"  Uptime: {uptime:.0f} seconds")
                self.logger.info(
                    f"  Connection Status: {'✅ Connected' if self.health.is_connected else '❌ Disconnected'}"
                )
                self.logger.info(f"  Total Requests: {self.health.total_requests}")
                self.logger.info(f"  Success Rate: {success_rate:.1f}%")
                self.logger.info(
                    f"  Consecutive Failures: {self.health.consecutive_failures}"
                )
                self.logger.info(
                    f"  Average Latency: {self.health.avg_latency_ms:.2f}ms"
                )
                self.logger.info(
                    f"  Market Data Updates: {self.market_data_update_count}"
                )
                self.logger.info(f"  Alerts Sent: {len(self.alerts_sent)}")

                # Generate performance report
                if uptime > 0 and uptime % 3600 == 0:  # Every hour
                    await self.generate_performance_report()

            except Exception as e:
                self.logger.error(f"Performance tracker error: {e}")
                await asyncio.sleep(300)

    async def alert_manager(self):
        """Manage and process alerts."""
        self.logger.info("🚨 Starting alert manager...")

        while self.running:
            try:
                # Process any pending alerts
                await self.process_pending_alerts()
                await asyncio.sleep(10)

            except Exception as e:
                self.logger.error(f"Alert manager error: {e}")
                await asyncio.sleep(10)

    async def send_alert(self, alert: MonitoringAlert):
        """Send monitoring alert."""
        # Check cooldown period
        now = datetime.utcnow()
        recent_similar = [
            a
            for a in self.alerts_sent
            if (
                a.alert_type == alert.alert_type
                and (now - a.timestamp).total_seconds() < self.config["alert_cooldown"]
            )
        ]

        if recent_similar:
            return  # Skip duplicate alert within cooldown period

        # Log alert
        emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}.get(
            alert.severity, "📢"
        )

        self.logger.log(
            getattr(logging, alert.severity),
            f"{emoji} ALERT [{alert.alert_type.upper()}]: {alert.message}",
        )

        # Store alert
        self.alerts_sent.append(alert)

        # Keep only last 1000 alerts
        if len(self.alerts_sent) > 1000:
            self.alerts_sent = self.alerts_sent[-1000:]

    async def process_pending_alerts(self):
        """Process any pending alerts."""
        # This could integrate with external alerting systems
        # For now, just ensure alerts are logged
        pass

    async def attempt_recovery(self):
        """Attempt to recover connection."""
        self.logger.warning("🔧 Attempting connection recovery...")

        for attempt in range(self.config["recovery_attempts"]):
            try:
                self.logger.info(
                    f"Recovery attempt {attempt + 1}/{self.config['recovery_attempts']}"
                )

                # Disconnect if connected
                if self.adapter:
                    await self.adapter.disconnect()

                # Wait before retry
                await asyncio.sleep(self.config["recovery_delay"])

                # Attempt reconnection
                await self.establish_connection()

                if self.health.is_connected:
                    self.logger.info("✅ Connection recovery successful")

                    await self.send_alert(
                        MonitoringAlert(
                            timestamp=datetime.utcnow(),
                            alert_type="recovery",
                            severity="INFO",
                            message=f"Connection recovered after {attempt + 1} attempts",
                            details={
                                "recovery_attempts": attempt + 1,
                                "recovery_time_s": (attempt + 1)
                                * self.config["recovery_delay"],
                            },
                        )
                    )
                    return

            except Exception as e:
                self.logger.error(f"Recovery attempt {attempt + 1} failed: {e}")

        # All recovery attempts failed
        self.logger.error("❌ All recovery attempts failed")
        await self.send_alert(
            MonitoringAlert(
                timestamp=datetime.utcnow(),
                alert_type="recovery",
                severity="CRITICAL",
                message="All connection recovery attempts failed",
                details={
                    "attempts": self.config["recovery_attempts"],
                    "last_error": self.health.last_error,
                },
            )
        )

    async def generate_performance_report(self):
        """Generate hourly performance report."""
        uptime = (datetime.utcnow() - self.start_time).total_seconds()

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": uptime,
            "connection_health": asdict(self.health),
            "performance_metrics": {
                "avg_latency_ms": (
                    statistics.mean(self.latency_history) if self.latency_history else 0
                ),
                "max_latency_ms": (
                    max(self.latency_history) if self.latency_history else 0
                ),
                "min_latency_ms": (
                    min(self.latency_history) if self.latency_history else 0
                ),
                "latency_samples": len(self.latency_history),
                "market_data_updates": self.market_data_update_count,
                "total_alerts": len(self.alerts_sent),
            },
            "alerts_summary": {
                "total": len(self.alerts_sent),
                "by_severity": {
                    "INFO": len([a for a in self.alerts_sent if a.severity == "INFO"]),
                    "WARNING": len(
                        [a for a in self.alerts_sent if a.severity == "WARNING"]
                    ),
                    "ERROR": len(
                        [a for a in self.alerts_sent if a.severity == "ERROR"]
                    ),
                    "CRITICAL": len(
                        [a for a in self.alerts_sent if a.severity == "CRITICAL"]
                    ),
                },
                "by_type": {},
            },
        }

        # Count alerts by type
        for alert in self.alerts_sent:
            alert_type = alert.alert_type
            if alert_type not in report["alerts_summary"]["by_type"]:
                report["alerts_summary"]["by_type"][alert_type] = 0
            report["alerts_summary"]["by_type"][alert_type] += 1

        # Save report
        report_filename = (
            f"fxcm_monitor_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        )
        with open(report_filename, "w") as f:
            json.dump(report, f, indent=2)

        self.logger.info(f"📊 Performance report saved: {report_filename}")

    async def cleanup(self):
        """Cleanup resources."""
        self.logger.info("🧹 Cleaning up resources...")

        if self.adapter:
            try:
                await self.adapter.disconnect()
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")

        # Generate final report
        await self.generate_performance_report()

        self.logger.info("✅ Cleanup completed")

    def get_status_summary(self) -> Dict[str, Any]:
        """Get current status summary."""
        uptime = (datetime.utcnow() - self.start_time).total_seconds()

        return {
            "monitoring_status": "running" if self.running else "stopped",
            "connection_status": (
                "connected" if self.health.is_connected else "disconnected"
            ),
            "uptime_seconds": uptime,
            "total_requests": self.health.total_requests,
            "success_rate": (
                (self.health.successful_requests / self.health.total_requests * 100)
                if self.health.total_requests > 0
                else 0
            ),
            "consecutive_failures": self.health.consecutive_failures,
            "avg_latency_ms": self.health.avg_latency_ms,
            "market_data_updates": self.market_data_update_count,
            "alerts_sent": len(self.alerts_sent),
            "last_successful_request": (
                self.health.last_successful_request.isoformat()
                if self.health.last_successful_request
                else None
            ),
            "last_error": self.health.last_error,
        }


async def main():
    """Main entry point."""
    print("🔍 FXCM Real-time Connectivity Monitor")
    print("=" * 60)
    print("Press Ctrl+C to stop monitoring")
    print()

    monitor = FXCMConnectivityMonitor()

    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        print("\n⏹️ Monitoring stopped by user")
    except Exception as e:
        print(f"\n💥 Monitor crashed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("\n👋 FXCM Connectivity Monitor shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
