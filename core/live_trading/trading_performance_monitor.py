"""
FXML4 Trading Performance Monitor
Continuous monitoring and alerting for profitability validation campaign

This module provides real-time monitoring of trading performance with:
- Progress tracking toward profitability targets
- Early warning system for performance deviations
- Automated daily reporting and stakeholder notifications
- Dashboard integration with live performance metrics
- Risk threshold monitoring and breach detection

Key Features:
- Real-time progress tracking vs 15% annual return target
- Drawdown monitoring with 10% breach detection
- Statistical trend analysis and forecasting
- Automated stakeholder reporting
- Integration with existing monitoring systems
"""

import asyncio
import json
import logging
import math
import smtplib
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..core.exceptions import MonitoringError
from .live_performance_tracker import (
    LivePerformanceTracker,
    PerformanceSnapshot,
    PerformanceStatus,
)
from .profitability_validator import (
    CampaignStatus,
    ProfitabilityValidator,
    ValidationResult,
)


class AlertPriority(Enum):
    """Alert priority levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MonitoringMetric(Enum):
    """Performance metrics to monitor"""

    ANNUALIZED_RETURN = "annualized_return"
    MAX_DRAWDOWN = "max_drawdown"
    CURRENT_DRAWDOWN = "current_drawdown"
    WIN_RATE = "win_rate"
    SHARPE_RATIO = "sharpe_ratio"
    DAILY_RETURN = "daily_return"
    TRADE_COUNT = "trade_count"


@dataclass
class PerformanceAlert:
    """Performance monitoring alert"""

    alert_id: str
    priority: AlertPriority
    metric: MonitoringMetric
    current_value: float
    threshold_value: float
    message: str
    timestamp: datetime
    campaign_id: str
    days_into_campaign: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "priority": self.priority.value,
            "metric": self.metric.value,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "campaign_id": self.campaign_id,
            "days_into_campaign": self.days_into_campaign,
        }


@dataclass
class ProgressForecast:
    """Performance progress forecast"""

    projected_30day_return: float
    projected_final_return: float
    probability_target_achievement: float
    expected_max_drawdown: float
    confidence_level: float
    forecast_accuracy: float

    @property
    def target_likelihood(self) -> str:
        """Human-readable target likelihood"""
        if self.probability_target_achievement >= 80:
            return "Very Likely"
        elif self.probability_target_achievement >= 60:
            return "Likely"
        elif self.probability_target_achievement >= 40:
            return "Possible"
        elif self.probability_target_achievement >= 20:
            return "Unlikely"
        else:
            return "Very Unlikely"


@dataclass
class DailyPerformanceReport:
    """Daily performance report"""

    date: datetime
    campaign_day: int
    account_value: float
    daily_return: float
    cumulative_return: float
    annualized_return: float
    current_drawdown: float
    max_drawdown: float
    trade_count: int
    win_rate: float
    progress_to_target: float
    forecast: ProgressForecast
    alerts: List[PerformanceAlert] = field(default_factory=list)

    @property
    def days_remaining(self) -> int:
        return max(0, 30 - self.campaign_day)

    @property
    def target_status(self) -> str:
        """Current target achievement status"""
        if self.annualized_return >= 15.0:
            return "✅ TARGET MET"
        elif self.progress_to_target >= 80:
            return "🟡 ON TRACK"
        elif self.progress_to_target >= 50:
            return "⚠️ BEHIND SCHEDULE"
        else:
            return "🚨 SIGNIFICANT DEFICIT"


class TradingPerformanceMonitor:
    """
    Trading Performance Monitor for Campaign Tracking

    Provides continuous monitoring and alerting for profitability validation campaigns
    with real-time progress tracking, forecasting, and stakeholder communication.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Monitoring configuration
        self.target_annual_return = self.config.get("target_annual_return", 15.0)
        self.max_drawdown_limit = self.config.get("max_drawdown_limit", 10.0)
        self.campaign_duration = self.config.get("campaign_duration_days", 30)

        # Alert thresholds
        self.alert_thresholds = {
            MonitoringMetric.ANNUALIZED_RETURN: {
                "warning": 10.0,  # Below 10% annual return
                "critical": 5.0,  # Below 5% annual return
            },
            MonitoringMetric.MAX_DRAWDOWN: {
                "warning": 8.0,  # Above 8% drawdown
                "critical": 10.0,  # Above 10% drawdown (limit)
            },
            MonitoringMetric.CURRENT_DRAWDOWN: {
                "warning": 6.0,  # Above 6% current drawdown
                "critical": 8.0,  # Above 8% current drawdown
            },
            MonitoringMetric.WIN_RATE: {
                "warning": 40.0,  # Below 40% win rate
                "critical": 30.0,  # Below 30% win rate
            },
        }

        # Monitoring state
        self.campaign_id: Optional[str] = None
        self.campaign_start: Optional[datetime] = None
        self.performance_tracker: Optional[LivePerformanceTracker] = None

        # Alert tracking
        self.active_alerts: List[PerformanceAlert] = []
        self.alert_history: List[PerformanceAlert] = []
        self.alert_cooldowns: Dict[str, datetime] = {}

        # Daily reports
        self.daily_reports: List[DailyPerformanceReport] = []

        # Notification configuration
        self.email_config = self.config.get("email", {})
        self.notification_callbacks: List[Callable[[PerformanceAlert], None]] = []

        # File storage
        self.reports_dir = Path("performance_monitoring_reports")
        self.reports_dir.mkdir(exist_ok=True)
        self.alerts_file = Path("performance_alerts.json")

    async def start_monitoring(
        self,
        campaign_id: str,
        performance_tracker: LivePerformanceTracker,
        campaign_start: datetime,
    ) -> None:
        """Start monitoring a profitability validation campaign"""
        try:
            self.logger.info(
                f"🔄 Starting performance monitoring for campaign: {campaign_id}"
            )

            self.campaign_id = campaign_id
            self.campaign_start = campaign_start
            self.performance_tracker = performance_tracker

            # Load historical alerts if available
            await self._load_historical_alerts()

            self.logger.info("✅ Performance monitoring started")

        except Exception as e:
            self.logger.error(f"❌ Failed to start performance monitoring: {e}")
            raise MonitoringError(f"Performance monitoring startup failed: {e}")

    async def update_monitoring(
        self, snapshot: PerformanceSnapshot
    ) -> List[PerformanceAlert]:
        """Update monitoring with new performance snapshot"""
        try:
            # Calculate campaign day
            campaign_day = (snapshot.timestamp - self.campaign_start).days + 1

            # Check for alerts
            new_alerts = await self._check_performance_alerts(snapshot, campaign_day)

            # Update active alerts
            self.active_alerts.extend(new_alerts)
            self.alert_history.extend(new_alerts)

            # Process alerts (send notifications, etc.)
            for alert in new_alerts:
                await self._process_alert(alert)

            # Generate daily report if it's a new day
            if self._is_new_trading_day(snapshot.timestamp):
                daily_report = await self._generate_daily_report(snapshot, campaign_day)
                self.daily_reports.append(daily_report)
                await self._send_daily_report(daily_report)

            # Save alerts periodically
            if len(new_alerts) > 0:
                await self._save_alerts()

            return new_alerts

        except Exception as e:
            self.logger.error(f"Error updating performance monitoring: {e}")
            return []

    async def _check_performance_alerts(
        self, snapshot: PerformanceSnapshot, campaign_day: int
    ) -> List[PerformanceAlert]:
        """Check performance snapshot against alert thresholds"""
        new_alerts = []

        # Check annualized return
        if (
            snapshot.annualized_return
            < self.alert_thresholds[MonitoringMetric.ANNUALIZED_RETURN]["critical"]
        ):
            alert = await self._create_alert(
                MonitoringMetric.ANNUALIZED_RETURN,
                AlertPriority.CRITICAL,
                snapshot.annualized_return,
                self.alert_thresholds[MonitoringMetric.ANNUALIZED_RETURN]["critical"],
                f"Annualized return critically low: {snapshot.annualized_return:.1f}% (target: {self.target_annual_return}%)",
                campaign_day,
            )
            if alert:
                new_alerts.append(alert)
        elif (
            snapshot.annualized_return
            < self.alert_thresholds[MonitoringMetric.ANNUALIZED_RETURN]["warning"]
        ):
            alert = await self._create_alert(
                MonitoringMetric.ANNUALIZED_RETURN,
                AlertPriority.HIGH,
                snapshot.annualized_return,
                self.alert_thresholds[MonitoringMetric.ANNUALIZED_RETURN]["warning"],
                f"Annualized return below warning threshold: {snapshot.annualized_return:.1f}% (target: {self.target_annual_return}%)",
                campaign_day,
            )
            if alert:
                new_alerts.append(alert)

        # Check maximum drawdown
        if (
            snapshot.max_drawdown
            >= self.alert_thresholds[MonitoringMetric.MAX_DRAWDOWN]["critical"]
        ):
            alert = await self._create_alert(
                MonitoringMetric.MAX_DRAWDOWN,
                AlertPriority.CRITICAL,
                snapshot.max_drawdown,
                self.alert_thresholds[MonitoringMetric.MAX_DRAWDOWN]["critical"],
                f"DRAWDOWN LIMIT BREACH: {snapshot.max_drawdown:.1f}% ≥ {self.max_drawdown_limit}%",
                campaign_day,
            )
            if alert:
                new_alerts.append(alert)
        elif (
            snapshot.max_drawdown
            >= self.alert_thresholds[MonitoringMetric.MAX_DRAWDOWN]["warning"]
        ):
            alert = await self._create_alert(
                MonitoringMetric.MAX_DRAWDOWN,
                AlertPriority.HIGH,
                snapshot.max_drawdown,
                self.alert_thresholds[MonitoringMetric.MAX_DRAWDOWN]["warning"],
                f"Maximum drawdown approaching limit: {snapshot.max_drawdown:.1f}% (limit: {self.max_drawdown_limit}%)",
                campaign_day,
            )
            if alert:
                new_alerts.append(alert)

        # Check current drawdown
        if (
            snapshot.current_drawdown
            >= self.alert_thresholds[MonitoringMetric.CURRENT_DRAWDOWN]["critical"]
        ):
            alert = await self._create_alert(
                MonitoringMetric.CURRENT_DRAWDOWN,
                AlertPriority.HIGH,
                snapshot.current_drawdown,
                self.alert_thresholds[MonitoringMetric.CURRENT_DRAWDOWN]["critical"],
                f"Current drawdown high: {snapshot.current_drawdown:.1f}%",
                campaign_day,
            )
            if alert:
                new_alerts.append(alert)

        # Check win rate (if we have enough trades)
        if snapshot.total_trades >= 10:
            if (
                snapshot.win_rate
                < self.alert_thresholds[MonitoringMetric.WIN_RATE]["critical"]
            ):
                alert = await self._create_alert(
                    MonitoringMetric.WIN_RATE,
                    AlertPriority.HIGH,
                    snapshot.win_rate,
                    self.alert_thresholds[MonitoringMetric.WIN_RATE]["critical"],
                    f"Win rate critically low: {snapshot.win_rate:.1f}% (trades: {snapshot.total_trades})",
                    campaign_day,
                )
                if alert:
                    new_alerts.append(alert)

        # Check for progress milestones
        if campaign_day in [7, 14, 21, 28, 30]:
            milestone_alert = await self._create_milestone_alert(snapshot, campaign_day)
            if milestone_alert:
                new_alerts.append(milestone_alert)

        return new_alerts

    async def _create_alert(
        self,
        metric: MonitoringMetric,
        priority: AlertPriority,
        current_value: float,
        threshold_value: float,
        message: str,
        campaign_day: int,
    ) -> Optional[PerformanceAlert]:
        """Create alert with cooldown logic"""

        # Create alert key for cooldown tracking
        alert_key = f"{metric.value}_{priority.value}"

        # Check cooldown (prevent spam)
        cooldown_minutes = {
            AlertPriority.LOW: 60,  # 1 hour
            AlertPriority.MEDIUM: 30,  # 30 minutes
            AlertPriority.HIGH: 15,  # 15 minutes
            AlertPriority.CRITICAL: 5,  # 5 minutes
        }.get(priority, 30)

        if alert_key in self.alert_cooldowns:
            last_alert = self.alert_cooldowns[alert_key]
            if datetime.utcnow() - last_alert < timedelta(minutes=cooldown_minutes):
                return None  # Skip due to cooldown

        # Create alert
        alert_id = f"{self.campaign_id}_{metric.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        alert = PerformanceAlert(
            alert_id=alert_id,
            priority=priority,
            metric=metric,
            current_value=current_value,
            threshold_value=threshold_value,
            message=message,
            timestamp=datetime.utcnow(),
            campaign_id=self.campaign_id,
            days_into_campaign=campaign_day,
        )

        # Update cooldown
        self.alert_cooldowns[alert_key] = datetime.utcnow()

        return alert

    async def _create_milestone_alert(
        self, snapshot: PerformanceSnapshot, campaign_day: int
    ) -> Optional[PerformanceAlert]:
        """Create milestone progress alert"""

        # Calculate progress metrics
        progress_to_target = (
            snapshot.annualized_return / self.target_annual_return
        ) * 100

        # Determine milestone status
        if campaign_day == 7:
            expected_min_return = 3.0  # Minimum expected after 1 week
        elif campaign_day == 14:
            expected_min_return = 6.0  # Minimum expected after 2 weeks
        elif campaign_day == 21:
            expected_min_return = 10.0  # Minimum expected after 3 weeks
        elif campaign_day == 28:
            expected_min_return = 13.0  # Minimum expected after 4 weeks
        else:  # campaign_day == 30
            expected_min_return = 15.0  # Final target

        # Create milestone alert
        if snapshot.annualized_return >= expected_min_return:
            priority = AlertPriority.LOW
            message = f"✅ Day {campaign_day} milestone: ON TRACK ({snapshot.annualized_return:.1f}% annualized return)"
        else:
            priority = AlertPriority.MEDIUM
            message = f"⚠️ Day {campaign_day} milestone: BEHIND TARGET ({snapshot.annualized_return:.1f}% vs {expected_min_return:.1f}% expected)"

        alert_id = f"{self.campaign_id}_milestone_day_{campaign_day}"

        return PerformanceAlert(
            alert_id=alert_id,
            priority=priority,
            metric=MonitoringMetric.ANNUALIZED_RETURN,
            current_value=snapshot.annualized_return,
            threshold_value=expected_min_return,
            message=message,
            timestamp=datetime.utcnow(),
            campaign_id=self.campaign_id,
            days_into_campaign=campaign_day,
        )

    async def _process_alert(self, alert: PerformanceAlert) -> None:
        """Process alert (log, notify, etc.)"""

        # Log alert
        log_method = {
            AlertPriority.LOW: self.logger.info,
            AlertPriority.MEDIUM: self.logger.warning,
            AlertPriority.HIGH: self.logger.error,
            AlertPriority.CRITICAL: self.logger.critical,
        }.get(alert.priority, self.logger.info)

        log_method(
            f"🚨 PERFORMANCE ALERT [{alert.priority.value.upper()}]: {alert.message}"
        )

        # Send notifications
        await self._send_alert_notifications(alert)

        # Call registered callbacks
        for callback in self.notification_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"Error in notification callback: {e}")

    async def _send_alert_notifications(self, alert: PerformanceAlert) -> None:
        """Send alert notifications via email/other channels"""
        try:
            if self.email_config.get("enabled", False):
                await self._send_email_alert(alert)
        except Exception as e:
            self.logger.error(f"Failed to send alert notifications: {e}")

    async def _send_email_alert(self, alert: PerformanceAlert) -> None:
        """Send alert via email"""
        try:
            if not self.email_config.get("smtp_server") or not self.email_config.get(
                "recipients"
            ):
                return

            # Create email message
            msg = MIMEMultipart()
            msg["From"] = self.email_config.get("sender", "fxml4@trading.system")
            msg["To"] = ", ".join(self.email_config["recipients"])
            msg["Subject"] = f"FXML4 Performance Alert: {alert.priority.value.upper()}"

            # Email body
            body = f"""
FXML4 Trading Performance Alert

Campaign: {alert.campaign_id}
Alert Priority: {alert.priority.value.upper()}
Day: {alert.days_into_campaign}/30

Alert Details:
{alert.message}

Metric: {alert.metric.value}
Current Value: {alert.current_value:.2f}
Threshold: {alert.threshold_value:.2f}

Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

This is an automated alert from the FXML4 trading system.
            """

            msg.attach(MIMEText(body, "plain"))

            # Send email
            server = smtplib.SMTP(
                self.email_config["smtp_server"],
                self.email_config.get("smtp_port", 587),
            )
            if self.email_config.get("use_tls", True):
                server.starttls()

            if self.email_config.get("username"):
                server.login(
                    self.email_config["username"], self.email_config["password"]
                )

            server.send_message(msg)
            server.quit()

            self.logger.info(f"📧 Email alert sent for {alert.alert_id}")

        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")

    def _is_new_trading_day(self, timestamp: datetime) -> bool:
        """Check if this is a new trading day"""
        if not self.daily_reports:
            return True

        last_report_date = self.daily_reports[-1].date.date()
        current_date = timestamp.date()

        return current_date > last_report_date

    async def _generate_daily_report(
        self, snapshot: PerformanceSnapshot, campaign_day: int
    ) -> DailyPerformanceReport:
        """Generate comprehensive daily performance report"""

        # Calculate progress to target
        progress_to_target = (
            snapshot.annualized_return / self.target_annual_return
        ) * 100

        # Generate forecast
        forecast = await self._generate_performance_forecast(snapshot, campaign_day)

        # Get today's alerts
        today_alerts = [
            a
            for a in self.active_alerts
            if a.timestamp.date() == snapshot.timestamp.date()
        ]

        return DailyPerformanceReport(
            date=snapshot.timestamp,
            campaign_day=campaign_day,
            account_value=snapshot.account_value,
            daily_return=snapshot.daily_return,
            cumulative_return=snapshot.cumulative_return,
            annualized_return=snapshot.annualized_return,
            current_drawdown=snapshot.current_drawdown,
            max_drawdown=snapshot.max_drawdown,
            trade_count=snapshot.total_trades,
            win_rate=snapshot.win_rate,
            progress_to_target=progress_to_target,
            forecast=forecast,
            alerts=today_alerts,
        )

    async def _generate_performance_forecast(
        self, snapshot: PerformanceSnapshot, campaign_day: int
    ) -> ProgressForecast:
        """Generate performance forecast based on current trajectory"""

        # Get recent performance data
        if (
            not self.performance_tracker
            or len(self.performance_tracker.daily_returns) < 3
        ):
            # Insufficient data for forecast
            return ProgressForecast(
                projected_30day_return=snapshot.annualized_return,
                projected_final_return=snapshot.annualized_return,
                probability_target_achievement=50.0,
                expected_max_drawdown=snapshot.max_drawdown,
                confidence_level=0.0,
                forecast_accuracy=0.0,
            )

        # Calculate trend metrics
        recent_returns = self.performance_tracker.daily_returns[
            -min(7, len(self.performance_tracker.daily_returns)) :
        ]
        avg_daily_return = statistics.mean(recent_returns)
        daily_volatility = (
            statistics.stdev(recent_returns) if len(recent_returns) > 1 else 0.01
        )

        # Project forward
        days_remaining = 30 - campaign_day

        # Simple projection based on recent trend
        projected_total_return = snapshot.cumulative_return + (
            avg_daily_return * days_remaining
        )
        projected_30day_return = (projected_total_return / 30) * 365  # Annualize
        projected_final_return = projected_30day_return

        # Calculate probability of target achievement (simplified)
        returns_needed = self.target_annual_return - snapshot.annualized_return
        daily_return_needed = (
            returns_needed / 365 * (days_remaining if days_remaining > 0 else 1)
        )

        if daily_volatility > 0:
            # Z-score calculation for probability
            z_score = (avg_daily_return - daily_return_needed) / daily_volatility
            # Convert to probability (simplified normal distribution approximation)
            probability = max(0, min(100, 50 + (z_score * 20)))
        else:
            probability = 50.0

        # Estimate maximum drawdown
        expected_max_dd = snapshot.max_drawdown + (
            daily_volatility * math.sqrt(days_remaining) * 2
        )
        expected_max_dd = min(expected_max_dd, 20.0)  # Cap at 20%

        # Confidence level based on data quality
        confidence = min(100, max(10, campaign_day * 3))

        # Forecast accuracy (simplified)
        accuracy = min(90, max(30, 100 - (daily_volatility * 100)))

        return ProgressForecast(
            projected_30day_return=projected_30day_return,
            projected_final_return=projected_final_return,
            probability_target_achievement=probability,
            expected_max_drawdown=expected_max_dd,
            confidence_level=confidence,
            forecast_accuracy=accuracy,
        )

    async def _send_daily_report(self, report: DailyPerformanceReport) -> None:
        """Send daily performance report"""
        try:
            # Generate report text
            report_text = await self._format_daily_report(report)

            # Save to file
            report_file = (
                self.reports_dir
                / f"daily_report_{report.date.strftime('%Y-%m-%d')}.txt"
            )
            with open(report_file, "w") as f:
                f.write(report_text)

            self.logger.info(f"📊 Daily report generated: {report_file}")

            # Send email if configured
            if self.email_config.get("enabled", False) and self.email_config.get(
                "daily_reports", True
            ):
                await self._send_daily_email_report(report, report_text)

        except Exception as e:
            self.logger.error(f"Failed to send daily report: {e}")

    async def _format_daily_report(self, report: DailyPerformanceReport) -> str:
        """Format daily report as text"""

        lines = [
            "=" * 80,
            f"FXML4 PROFITABILITY CAMPAIGN - DAILY REPORT",
            "=" * 80,
            f"Date: {report.date.strftime('%Y-%m-%d')}",
            f"Campaign Day: {report.campaign_day}/30 ({report.days_remaining} days remaining)",
            f"Campaign: {self.campaign_id}",
            "",
            "PERFORMANCE SUMMARY:",
            f"  Account Value: ${report.account_value:,.2f}",
            f"  Daily Return: {report.daily_return:+.2f}%",
            f"  Cumulative Return: {report.cumulative_return:+.2f}%",
            f"  Annualized Return: {report.annualized_return:.1f}% (Target: ≥15.0%)",
            f"  Status: {report.target_status}",
            "",
            "RISK METRICS:",
            f"  Current Drawdown: {report.current_drawdown:.1f}%",
            f"  Maximum Drawdown: {report.max_drawdown:.1f}% (Limit: ≤10.0%)",
            f"  Drawdown Status: {'✅ COMPLIANT' if report.max_drawdown <= 10.0 else '🚨 BREACH'}",
            "",
            "TRADING STATISTICS:",
            f"  Total Trades: {report.trade_count}",
            f"  Win Rate: {report.win_rate:.1f}%",
            f"  Progress to Target: {report.progress_to_target:.1f}%",
            "",
            "PERFORMANCE FORECAST:",
            f"  Projected 30-Day Return: {report.forecast.projected_30day_return:.1f}%",
            f"  Target Achievement Probability: {report.forecast.probability_target_achievement:.0f}% ({report.forecast.target_likelihood})",
            f"  Expected Max Drawdown: {report.forecast.expected_max_drawdown:.1f}%",
            f"  Forecast Confidence: {report.forecast.confidence_level:.0f}%",
            "",
        ]

        # Add alerts
        if report.alerts:
            lines.extend([f"TODAY'S ALERTS ({len(report.alerts)}):", "-" * 40])
            for alert in report.alerts:
                priority_emoji = {
                    AlertPriority.LOW: "ℹ️",
                    AlertPriority.MEDIUM: "⚠️",
                    AlertPriority.HIGH: "🚨",
                    AlertPriority.CRITICAL: "🔥",
                }.get(alert.priority, "📌")

                lines.append(
                    f"  {priority_emoji} [{alert.priority.value.upper()}] {alert.message}"
                )
            lines.append("")
        else:
            lines.extend(["TODAY'S ALERTS: None", ""])

        lines.extend(["=" * 80])

        return "\n".join(lines)

    async def _send_daily_email_report(
        self, report: DailyPerformanceReport, report_text: str
    ) -> None:
        """Send daily report via email"""
        try:
            if not self.email_config.get("smtp_server") or not self.email_config.get(
                "recipients"
            ):
                return

            # Create email message
            msg = MIMEMultipart()
            msg["From"] = self.email_config.get("sender", "fxml4@trading.system")
            msg["To"] = ", ".join(self.email_config["recipients"])
            msg["Subject"] = (
                f"FXML4 Daily Report - Day {report.campaign_day} - {report.target_status}"
            )

            msg.attach(MIMEText(report_text, "plain"))

            # Send email
            server = smtplib.SMTP(
                self.email_config["smtp_server"],
                self.email_config.get("smtp_port", 587),
            )
            if self.email_config.get("use_tls", True):
                server.starttls()

            if self.email_config.get("username"):
                server.login(
                    self.email_config["username"], self.email_config["password"]
                )

            server.send_message(msg)
            server.quit()

            self.logger.info(
                f"📧 Daily email report sent for day {report.campaign_day}"
            )

        except Exception as e:
            self.logger.error(f"Failed to send daily email report: {e}")

    async def _save_alerts(self) -> None:
        """Save alert history to file"""
        try:
            alerts_data = {
                "last_updated": datetime.utcnow().isoformat(),
                "campaign_id": self.campaign_id,
                "total_alerts": len(self.alert_history),
                "active_alerts": len(self.active_alerts),
                "alerts": [alert.to_dict() for alert in self.alert_history],
            }

            with open(self.alerts_file, "w") as f:
                json.dump(alerts_data, f, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Failed to save alerts: {e}")

    async def _load_historical_alerts(self) -> None:
        """Load historical alerts from file"""
        try:
            if not self.alerts_file.exists():
                return

            with open(self.alerts_file, "r") as f:
                data = json.load(f)

            for alert_data in data.get("alerts", []):
                alert = PerformanceAlert(
                    alert_id=alert_data["alert_id"],
                    priority=AlertPriority(alert_data["priority"]),
                    metric=MonitoringMetric(alert_data["metric"]),
                    current_value=alert_data["current_value"],
                    threshold_value=alert_data["threshold_value"],
                    message=alert_data["message"],
                    timestamp=datetime.fromisoformat(alert_data["timestamp"]),
                    campaign_id=alert_data["campaign_id"],
                    days_into_campaign=alert_data["days_into_campaign"],
                )
                self.alert_history.append(alert)

            self.logger.info(f"📁 Loaded {len(self.alert_history)} historical alerts")

        except Exception as e:
            self.logger.warning(f"Could not load historical alerts: {e}")

    def add_notification_callback(
        self, callback: Callable[[PerformanceAlert], None]
    ) -> None:
        """Add notification callback for alerts"""
        self.notification_callbacks.append(callback)

    def get_campaign_summary(self) -> Dict[str, Any]:
        """Get current campaign summary"""
        if not self.daily_reports:
            return {}

        latest_report = self.daily_reports[-1]

        return {
            "campaign_id": self.campaign_id,
            "campaign_day": latest_report.campaign_day,
            "days_remaining": latest_report.days_remaining,
            "annualized_return": latest_report.annualized_return,
            "target_status": latest_report.target_status,
            "max_drawdown": latest_report.max_drawdown,
            "progress_to_target": latest_report.progress_to_target,
            "total_alerts": len(self.alert_history),
            "active_alerts": len(self.active_alerts),
            "forecast_probability": latest_report.forecast.probability_target_achievement,
        }


# Performance Monitor Runner for Direct Execution
async def main():
    """Main performance monitor runner for testing"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    config = {
        "target_annual_return": 15.0,
        "max_drawdown_limit": 10.0,
        "email": {"enabled": False},  # Disable email for testing
    }

    monitor = TradingPerformanceMonitor(config)

    try:
        # Add notification callback
        def alert_callback(alert: PerformanceAlert):
            logger.info(f"📧 Alert callback: {alert.priority.value} - {alert.message}")

        monitor.add_notification_callback(alert_callback)

        # Simulate campaign monitoring
        campaign_id = "test_campaign_001"
        campaign_start = datetime.utcnow() - timedelta(days=5)  # 5 days in

        # Create mock performance tracker
        from .live_performance_tracker import LivePerformanceTracker

        perf_tracker = LivePerformanceTracker({"initial_capital": 100000})
        await perf_tracker.initialize()

        # Start monitoring
        await monitor.start_monitoring(campaign_id, perf_tracker, campaign_start)

        # Simulate performance updates
        for day in range(1, 6):  # 5 days of data
            # Create mock snapshot
            from .live_performance_tracker import PerformanceSnapshot

            snapshot = PerformanceSnapshot(
                timestamp=campaign_start + timedelta(days=day),
                account_value=100000 + (day * 500),  # Gradual growth
                daily_return=0.5,  # 0.5% daily return
                cumulative_return=day * 0.5,
                annualized_return=12.0 + day,  # Improving performance
                max_drawdown=2.0 + (day * 0.3),
                current_drawdown=1.0,
                sharpe_ratio=1.2,
                sortino_ratio=1.5,
                win_rate=60.0,
                profit_factor=1.4,
                total_trades=day * 2,
                winning_trades=day * 1,
                losing_trades=day * 1,
                average_win=150.0,
                average_loss=100.0,
                largest_win=300.0,
                largest_loss=200.0,
                consecutive_wins=2,
                consecutive_losses=1,
                days_trading=day,
                volatility=15.0,
            )

            # Update monitoring
            alerts = await monitor.update_monitoring(snapshot)

            logger.info(
                f"Day {day}: {snapshot.annualized_return:.1f}% return, "
                f"{snapshot.max_drawdown:.1f}% max DD, {len(alerts)} new alerts"
            )

        # Generate summary
        summary = monitor.get_campaign_summary()
        logger.info(f"📊 Campaign Summary: {summary}")

        logger.info("✅ Performance monitoring test completed")

    except Exception as e:
        logger.error(f"Performance monitoring test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
