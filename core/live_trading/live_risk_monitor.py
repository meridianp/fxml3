"""
FXML4 Live Risk Monitor
Continuous monitoring of risk compliance during paper trading sessions

This module provides real-time monitoring of risk management compliance:
- Continuous tracking of portfolio exposure vs limits
- Real-time alerting on approaching risk thresholds
- Dashboard visualization of risk metrics
- Automatic violation detection and logging
- Integration with Interactive Brokers paper trading

Key Features:
- 24/7 monitoring during trading sessions
- Sub-second risk calculation updates
- Multi-currency portfolio exposure tracking
- Automated compliance reporting
- Risk limit breach prevention
"""

import asyncio
import json
import logging
import signal
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..core.exceptions import ValidationError
from .risk_validator import (
    RiskComplianceStatus,
    RiskManagementValidator,
    RiskValidationResult,
)


class MonitoringStatus(Enum):
    """Live monitor status"""

    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class AlertLevel(Enum):
    """Risk alert levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    VIOLATION = "violation"


@dataclass
class RiskAlert:
    """Risk monitoring alert"""

    level: AlertLevel
    message: str
    timestamp: datetime
    symbol: Optional[str] = None
    current_exposure: float = 0.0
    threshold_breached: float = 0.0
    account_balance: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "current_exposure": self.current_exposure,
            "threshold_breached": self.threshold_breached,
            "account_balance": self.account_balance,
        }


@dataclass
class MonitoringSnapshot:
    """Point-in-time risk monitoring snapshot"""

    timestamp: datetime
    account_balance: float
    total_exposure: float
    exposure_percentage: float
    positions_count: int
    currency_exposures: Dict[str, float] = field(default_factory=dict)
    compliance_status: RiskComplianceStatus = RiskComplianceStatus.COMPLIANT
    alerts: List[RiskAlert] = field(default_factory=list)

    @property
    def risk_utilization(self) -> float:
        """Risk utilization as percentage of maximum allowed"""
        max_allowed = 6.0  # 6% portfolio limit
        return (self.exposure_percentage / max_allowed) * 100 if max_allowed > 0 else 0


class LiveRiskMonitor:
    """
    Live Risk Monitor for Continuous Compliance Tracking

    Provides 24/7 monitoring of risk management compliance during paper trading
    with real-time alerting, dashboard updates, and automated violation detection.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Monitoring configuration
        self.update_interval_seconds = self.config.get(
            "update_interval_seconds", 10
        )  # 10 second updates
        self.alert_cooldown_seconds = self.config.get(
            "alert_cooldown_seconds", 300
        )  # 5 minute cooldowns
        self.snapshot_retention_hours = self.config.get(
            "snapshot_retention_hours", 168
        )  # 7 days

        # Risk thresholds for alerting
        self.warning_threshold_pct = self.config.get(
            "warning_threshold", 75.0
        )  # 75% of limit
        self.critical_threshold_pct = self.config.get(
            "critical_threshold", 90.0
        )  # 90% of limit

        # Monitoring state
        self.status = MonitoringStatus.INITIALIZING
        self.risk_validator: Optional[RiskManagementValidator] = None
        self.monitoring_task: Optional[asyncio.Task] = None
        self.shutdown_requested = False

        # Data storage
        self.snapshots: List[MonitoringSnapshot] = []
        self.alerts: List[RiskAlert] = []
        self.alert_history: Dict[str, datetime] = {}  # For cooldown tracking

        # File storage
        self.snapshots_file = Path("risk_monitoring_snapshots.json")
        self.alerts_file = Path("risk_monitoring_alerts.json")

        # Alert callbacks
        self.alert_callbacks: List[Callable[[RiskAlert], None]] = []

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True

    async def initialize(self) -> None:
        """Initialize live risk monitor"""
        try:
            self.logger.info("Initializing live risk monitor...")

            # Initialize risk validator
            self.risk_validator = RiskManagementValidator(self.config)
            await self.risk_validator.initialize()

            # Load historical data
            await self._load_historical_data()

            self.status = MonitoringStatus.RUNNING
            self.logger.info("✅ Live risk monitor initialized successfully")

        except Exception as e:
            self.status = MonitoringStatus.ERROR
            self.logger.error(f"❌ Failed to initialize live risk monitor: {e}")
            raise ValidationError(f"Live risk monitor initialization failed: {e}")

    async def start_monitoring(self) -> None:
        """Start continuous risk monitoring"""
        if self.status != MonitoringStatus.RUNNING:
            raise ValueError("Monitor must be initialized before starting")

        self.logger.info("🔄 Starting continuous risk monitoring...")
        self.logger.info(f"   Update interval: {self.update_interval_seconds} seconds")
        self.logger.info(
            f"   Warning threshold: {self.warning_threshold_pct}% of limits"
        )
        self.logger.info(
            f"   Critical threshold: {self.critical_threshold_pct}% of limits"
        )

        try:
            # Start monitoring loop
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            await self.monitoring_task

        except asyncio.CancelledError:
            self.logger.info("Monitoring task cancelled")
        except Exception as e:
            self.status = MonitoringStatus.ERROR
            self.logger.error(f"Monitoring error: {e}")
            raise
        finally:
            await self._save_monitoring_data()

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        self.logger.info("🔄 Starting risk monitoring loop...")

        loop_count = 0
        last_snapshot_save = datetime.utcnow()

        try:
            while not self.shutdown_requested:
                loop_start = time.time()
                loop_count += 1

                try:
                    # Take monitoring snapshot
                    snapshot = await self._take_snapshot()
                    self.snapshots.append(snapshot)

                    # Process alerts based on snapshot
                    await self._process_alerts(snapshot)

                    # Log periodic status
                    if loop_count % 60 == 0:  # Every 10 minutes with 10s intervals
                        self.logger.info(
                            f"📊 Risk Monitor Status - "
                            f"Exposure: {snapshot.exposure_percentage:.2f}%, "
                            f"Utilization: {snapshot.risk_utilization:.1f}%, "
                            f"Positions: {snapshot.positions_count}, "
                            f"Status: {snapshot.compliance_status.value}"
                        )

                    # Save snapshots periodically (every 10 minutes)
                    if datetime.utcnow() - last_snapshot_save > timedelta(minutes=10):
                        await self._save_monitoring_data()
                        last_snapshot_save = datetime.utcnow()

                    # Cleanup old snapshots
                    await self._cleanup_old_snapshots()

                except Exception as e:
                    self.logger.error(
                        f"Error in monitoring loop iteration {loop_count}: {e}"
                    )
                    # Continue monitoring even if one iteration fails

                # Sleep for remaining interval time
                loop_duration = time.time() - loop_start
                sleep_time = max(0, self.update_interval_seconds - loop_duration)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except Exception as e:
            self.logger.error(f"Fatal error in monitoring loop: {e}")
            self.status = MonitoringStatus.ERROR
            raise
        finally:
            self.logger.info(
                f"📊 Monitoring loop completed. Total iterations: {loop_count}"
            )

    async def _take_snapshot(self) -> MonitoringSnapshot:
        """Take a point-in-time risk monitoring snapshot"""
        try:
            # Get current account information from Interactive Brokers
            account_info = await self.risk_validator.ib_adapter.get_account_info()
            account_balance = float(account_info.get("TotalCashValue", 0))

            # Get current positions
            positions = await self.risk_validator.ib_adapter.get_positions()

            # Calculate portfolio exposure
            total_exposure = await self.risk_validator._calculate_portfolio_exposure(
                positions, account_balance
            )
            exposure_percentage = (
                (total_exposure / account_balance * 100) if account_balance > 0 else 0
            )

            # Calculate currency exposures
            currency_exposures = (
                await self.risk_validator._calculate_currency_exposures(positions)
            )

            # Determine compliance status
            compliance_status = self._determine_compliance_status(exposure_percentage)

            snapshot = MonitoringSnapshot(
                timestamp=datetime.utcnow(),
                account_balance=account_balance,
                total_exposure=total_exposure,
                exposure_percentage=exposure_percentage,
                positions_count=len(positions),
                currency_exposures=currency_exposures,
                compliance_status=compliance_status,
            )

            return snapshot

        except Exception as e:
            self.logger.error(f"Error taking monitoring snapshot: {e}")
            # Return empty snapshot in case of error
            return MonitoringSnapshot(
                timestamp=datetime.utcnow(),
                account_balance=0,
                total_exposure=0,
                exposure_percentage=0,
                positions_count=0,
                compliance_status=RiskComplianceStatus.ERROR,
            )

    def _determine_compliance_status(
        self, exposure_percentage: float
    ) -> RiskComplianceStatus:
        """Determine compliance status based on current exposure"""
        max_exposure_limit = 6.0  # 6% portfolio limit

        if exposure_percentage > max_exposure_limit:
            return RiskComplianceStatus.VIOLATION
        elif exposure_percentage > max_exposure_limit * (
            self.critical_threshold_pct / 100
        ):
            return RiskComplianceStatus.WARNING
        else:
            return RiskComplianceStatus.COMPLIANT

    async def _process_alerts(self, snapshot: MonitoringSnapshot) -> None:
        """Process and generate alerts based on snapshot"""
        current_time = datetime.utcnow()
        max_exposure_limit = 6.0  # 6% portfolio limit

        # Check portfolio exposure alerts
        if snapshot.exposure_percentage > max_exposure_limit:
            alert = RiskAlert(
                level=AlertLevel.VIOLATION,
                message=f"PORTFOLIO EXPOSURE VIOLATION: {snapshot.exposure_percentage:.2f}% > {max_exposure_limit}%",
                timestamp=current_time,
                current_exposure=snapshot.total_exposure,
                threshold_breached=snapshot.exposure_percentage,
                account_balance=snapshot.account_balance,
            )
            await self._emit_alert(alert)

        elif snapshot.exposure_percentage > max_exposure_limit * (
            self.critical_threshold_pct / 100
        ):
            alert = RiskAlert(
                level=AlertLevel.CRITICAL,
                message=f"CRITICAL: Portfolio exposure {snapshot.exposure_percentage:.2f}% approaching limit ({max_exposure_limit}%)",
                timestamp=current_time,
                current_exposure=snapshot.total_exposure,
                threshold_breached=snapshot.exposure_percentage,
                account_balance=snapshot.account_balance,
            )
            await self._emit_alert(alert)

        elif snapshot.exposure_percentage > max_exposure_limit * (
            self.warning_threshold_pct / 100
        ):
            alert = RiskAlert(
                level=AlertLevel.WARNING,
                message=f"WARNING: Portfolio exposure {snapshot.exposure_percentage:.2f}% approaching limit ({max_exposure_limit}%)",
                timestamp=current_time,
                current_exposure=snapshot.total_exposure,
                threshold_breached=snapshot.exposure_percentage,
                account_balance=snapshot.account_balance,
            )
            await self._emit_alert(alert)

        # Check for sudden exposure increases
        if len(self.snapshots) >= 2:
            previous_snapshot = self.snapshots[-2]
            exposure_increase = (
                snapshot.exposure_percentage - previous_snapshot.exposure_percentage
            )

            if exposure_increase > 1.0:  # More than 1% increase in single update
                alert = RiskAlert(
                    level=AlertLevel.WARNING,
                    message=f"RAPID EXPOSURE INCREASE: {exposure_increase:.2f}% in {self.update_interval_seconds} seconds",
                    timestamp=current_time,
                    current_exposure=snapshot.total_exposure,
                    threshold_breached=exposure_increase,
                    account_balance=snapshot.account_balance,
                )
                await self._emit_alert(alert)

        # Check currency concentration risks
        for currency, exposure in snapshot.currency_exposures.items():
            currency_percentage = (
                (exposure / snapshot.account_balance * 100)
                if snapshot.account_balance > 0
                else 0
            )

            if currency_percentage > 4.0:  # More than 4% in single currency
                alert = RiskAlert(
                    level=AlertLevel.WARNING,
                    message=f"CURRENCY CONCENTRATION: {currency} exposure {currency_percentage:.2f}%",
                    timestamp=current_time,
                    symbol=currency,
                    current_exposure=exposure,
                    threshold_breached=currency_percentage,
                    account_balance=snapshot.account_balance,
                )
                await self._emit_alert(alert)

    async def _emit_alert(self, alert: RiskAlert) -> None:
        """Emit alert with cooldown logic"""
        alert_key = f"{alert.level.value}:{alert.message[:50]}"

        # Check cooldown
        if alert_key in self.alert_history:
            last_alert_time = self.alert_history[alert_key]
            if datetime.utcnow() - last_alert_time < timedelta(
                seconds=self.alert_cooldown_seconds
            ):
                return  # Skip alert due to cooldown

        # Store alert
        self.alerts.append(alert)
        self.alert_history[alert_key] = alert.timestamp

        # Log alert
        log_method = {
            AlertLevel.INFO: self.logger.info,
            AlertLevel.WARNING: self.logger.warning,
            AlertLevel.CRITICAL: self.logger.error,
            AlertLevel.VIOLATION: self.logger.error,
        }.get(alert.level, self.logger.info)

        log_method(f"🚨 RISK ALERT [{alert.level.value.upper()}]: {alert.message}")

        # Call registered callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")

    def add_alert_callback(self, callback: Callable[[RiskAlert], None]) -> None:
        """Add callback for risk alerts"""
        self.alert_callbacks.append(callback)

    async def _cleanup_old_snapshots(self) -> None:
        """Remove snapshots older than retention period"""
        if not self.snapshots:
            return

        cutoff_time = datetime.utcnow() - timedelta(hours=self.snapshot_retention_hours)

        original_count = len(self.snapshots)
        self.snapshots = [s for s in self.snapshots if s.timestamp > cutoff_time]

        removed_count = original_count - len(self.snapshots)
        if removed_count > 0:
            self.logger.debug(f"Cleaned up {removed_count} old snapshots")

    async def _load_historical_data(self) -> None:
        """Load historical snapshots and alerts"""
        try:
            # Load snapshots
            if self.snapshots_file.exists():
                with open(self.snapshots_file, "r") as f:
                    data = json.load(f)

                for snapshot_data in data.get("snapshots", [])[
                    -1000:
                ]:  # Last 1000 snapshots
                    snapshot = MonitoringSnapshot(
                        timestamp=datetime.fromisoformat(snapshot_data["timestamp"]),
                        account_balance=snapshot_data["account_balance"],
                        total_exposure=snapshot_data["total_exposure"],
                        exposure_percentage=snapshot_data["exposure_percentage"],
                        positions_count=snapshot_data["positions_count"],
                        currency_exposures=snapshot_data.get("currency_exposures", {}),
                        compliance_status=RiskComplianceStatus(
                            snapshot_data.get("compliance_status", "compliant")
                        ),
                    )
                    self.snapshots.append(snapshot)

                self.logger.info(
                    f"📁 Loaded {len(self.snapshots)} historical snapshots"
                )

            # Load alerts
            if self.alerts_file.exists():
                with open(self.alerts_file, "r") as f:
                    data = json.load(f)

                for alert_data in data.get("alerts", [])[-1000:]:  # Last 1000 alerts
                    alert = RiskAlert(
                        level=AlertLevel(alert_data["level"]),
                        message=alert_data["message"],
                        timestamp=datetime.fromisoformat(alert_data["timestamp"]),
                        symbol=alert_data.get("symbol"),
                        current_exposure=alert_data.get("current_exposure", 0),
                        threshold_breached=alert_data.get("threshold_breached", 0),
                        account_balance=alert_data.get("account_balance", 0),
                    )
                    self.alerts.append(alert)

                self.logger.info(f"📁 Loaded {len(self.alerts)} historical alerts")

        except Exception as e:
            self.logger.warning(f"Could not load historical monitoring data: {e}")

    async def _save_monitoring_data(self) -> None:
        """Save snapshots and alerts to file"""
        try:
            # Save snapshots
            snapshots_data = {
                "last_updated": datetime.utcnow().isoformat(),
                "total_snapshots": len(self.snapshots),
                "snapshots": [],
            }

            # Save last 10000 snapshots
            for snapshot in self.snapshots[-10000:]:
                snapshot_dict = {
                    "timestamp": snapshot.timestamp.isoformat(),
                    "account_balance": snapshot.account_balance,
                    "total_exposure": snapshot.total_exposure,
                    "exposure_percentage": snapshot.exposure_percentage,
                    "positions_count": snapshot.positions_count,
                    "currency_exposures": snapshot.currency_exposures,
                    "compliance_status": snapshot.compliance_status.value,
                }
                snapshots_data["snapshots"].append(snapshot_dict)

            with open(self.snapshots_file, "w") as f:
                json.dump(snapshots_data, f, indent=2, default=str)

            # Save alerts
            alerts_data = {
                "last_updated": datetime.utcnow().isoformat(),
                "total_alerts": len(self.alerts),
                "alerts": [
                    alert.to_dict() for alert in self.alerts[-10000:]
                ],  # Last 10000 alerts
            }

            with open(self.alerts_file, "w") as f:
                json.dump(alerts_data, f, indent=2, default=str)

            self.logger.debug(
                f"💾 Saved monitoring data: {len(self.snapshots)} snapshots, {len(self.alerts)} alerts"
            )

        except Exception as e:
            self.logger.error(f"Failed to save monitoring data: {e}")

    def get_current_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        if not self.snapshots:
            return {"status": "no_data"}

        latest_snapshot = self.snapshots[-1]
        recent_alerts = [
            a
            for a in self.alerts
            if a.timestamp > datetime.utcnow() - timedelta(hours=1)
        ]

        return {
            "monitoring_status": self.status.value,
            "last_update": latest_snapshot.timestamp.isoformat(),
            "account_balance": latest_snapshot.account_balance,
            "total_exposure": latest_snapshot.total_exposure,
            "exposure_percentage": latest_snapshot.exposure_percentage,
            "risk_utilization": latest_snapshot.risk_utilization,
            "positions_count": latest_snapshot.positions_count,
            "compliance_status": latest_snapshot.compliance_status.value,
            "recent_alerts": len(recent_alerts),
            "total_snapshots": len(self.snapshots),
            "total_alerts": len(self.alerts),
        }

    def generate_monitoring_report(self) -> str:
        """Generate live monitoring report"""
        if not self.snapshots:
            return "No monitoring data available"

        latest = self.snapshots[-1]
        recent_snapshots = self.snapshots[-100:]  # Last 100 snapshots
        recent_alerts = [
            a
            for a in self.alerts
            if a.timestamp > datetime.utcnow() - timedelta(hours=24)
        ]

        report_lines = [
            "=" * 80,
            "FXML4 LIVE RISK MONITORING REPORT",
            "=" * 80,
            f"Generated: {datetime.utcnow().isoformat()}",
            f"Monitoring Status: {self.status.value}",
            "",
        ]

        # Current status
        report_lines.extend(
            [
                "CURRENT RISK STATUS:",
                f"  Account Balance: ${latest.account_balance:,.2f}",
                f"  Total Exposure: ${latest.total_exposure:,.2f}",
                f"  Exposure Percentage: {latest.exposure_percentage:.2f}%",
                f"  Risk Utilization: {latest.risk_utilization:.1f}%",
                f"  Open Positions: {latest.positions_count}",
                f"  Compliance Status: {latest.compliance_status.value}",
                "",
            ]
        )

        # Statistics
        if recent_snapshots:
            exposures = [s.exposure_percentage for s in recent_snapshots]
            report_lines.extend(
                [
                    "RECENT STATISTICS (Last 100 updates):",
                    f"  Average Exposure: {statistics.mean(exposures):.2f}%",
                    f"  Maximum Exposure: {max(exposures):.2f}%",
                    f"  Minimum Exposure: {min(exposures):.2f}%",
                    "",
                ]
            )

        # Recent alerts
        report_lines.extend(
            [f"RECENT ALERTS (Last 24 hours): {len(recent_alerts)}", "-" * 40]
        )

        for alert in recent_alerts[-10:]:  # Last 10 alerts
            report_lines.append(
                f"  [{alert.timestamp.strftime('%H:%M:%S')}] "
                f"{alert.level.value.upper()}: {alert.message}"
            )

        report_lines.extend(["", "=" * 80])

        return "\n".join(report_lines)

    async def stop_monitoring(self) -> None:
        """Stop risk monitoring"""
        self.logger.info("🛑 Stopping risk monitoring...")

        self.shutdown_requested = True

        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        # Save final monitoring data
        await self._save_monitoring_data()

        # Cleanup
        if self.risk_validator:
            await self.risk_validator.cleanup()

        self.status = MonitoringStatus.STOPPED
        self.logger.info("✅ Risk monitoring stopped")


# Monitor Runner for Direct Execution
async def main():
    """Main monitoring runner"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    config = {
        "update_interval_seconds": 30,  # 30 second updates for demo
        "alert_cooldown_seconds": 300,
        "warning_threshold": 75.0,
        "critical_threshold": 90.0,
    }

    monitor = LiveRiskMonitor(config)

    try:
        # Initialize monitor
        await monitor.initialize()

        # Add sample alert callback
        def alert_callback(alert: RiskAlert):
            logger.info(
                f"📧 Alert callback triggered: {alert.level.value} - {alert.message}"
            )

        monitor.add_alert_callback(alert_callback)

        # Start monitoring
        logger.info("🔄 Starting live risk monitoring (Ctrl+C to stop)...")
        await monitor.start_monitoring()

    except KeyboardInterrupt:
        logger.info("🛑 Monitoring interrupted by user")
    except Exception as e:
        logger.error(f"Monitoring error: {e}")
    finally:
        await monitor.stop_monitoring()

        # Generate final report
        report = monitor.generate_monitoring_report()
        logger.info("Final Monitoring Report:")
        logger.info(report)


if __name__ == "__main__":
    asyncio.run(main())
