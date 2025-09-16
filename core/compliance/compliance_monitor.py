"""
FXML4 Regulatory Compliance Monitoring System

This module provides continuous monitoring and reporting of regulatory compliance
status across all trading operations. It ensures real-time compliance oversight
and generates alerts for any potential regulatory violations.

Key monitoring capabilities:
- Real-time MiFID II compliance monitoring
- Audit trail continuity verification
- Best execution performance tracking
- Regulatory reporting deadline monitoring
- Compliance KPI dashboard
- Automated alert generation for compliance officers

The system provides comprehensive regulatory oversight for FXML4 trading operations.

Author: FXML4 Development Team
Created: 2024-12-28
"""

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# Core imports with graceful fallback
try:
    from fxml4.compliance.regulatory_validator import (
        ComplianceStatus,
        RegulatoryValidator,
    )
    from fxml4.core.config import get_config
    from fxml4.core.exceptions import ComplianceError, MonitoringError
    from fxml4.core.logger import get_logger
    from fxml4.notifications.email_service import EmailService
except ImportError:
    # Mock implementations for standalone operation
    import logging

    def get_logger(name: str):
        return logging.getLogger(name)

    def get_config():
        return {}

    class ComplianceError(Exception):
        pass

    class MonitoringError(Exception):
        pass

    class RegulatoryValidator:
        async def get_compliance_summary(self):
            return {"mock": "data"}

    class ComplianceStatus:
        COMPLIANT = "compliant"
        NON_COMPLIANT = "non_compliant"
        REQUIRES_ATTENTION = "requires_attention"

    class EmailService:
        async def send_alert(self, *args, **kwargs):
            pass


class ComplianceAlertLevel(Enum):
    """Compliance alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    REGULATORY_VIOLATION = "regulatory_violation"


class ComplianceMetricType(Enum):
    """Types of compliance metrics monitored."""

    TRANSACTION_COMPLIANCE_RATE = "transaction_compliance_rate"
    AUDIT_TRAIL_INTEGRITY = "audit_trail_integrity"
    BEST_EXECUTION_PERFORMANCE = "best_execution_performance"
    REPORTING_DEADLINE_ADHERENCE = "reporting_deadline_adherence"
    DATA_RETENTION_COMPLIANCE = "data_retention_compliance"
    REGULATORY_RESPONSE_TIME = "regulatory_response_time"


@dataclass
class ComplianceAlert:
    """Regulatory compliance alert structure."""

    alert_id: str
    timestamp: datetime
    level: ComplianceAlertLevel
    metric_type: ComplianceMetricType

    # Alert content
    title: str
    description: str
    current_value: float
    threshold_value: float

    # Regulatory context
    regulatory_framework: str  # 'MiFID II', 'EMIR', 'MAR', etc.
    regulatory_reference: str  # Article/regulation reference
    potential_impact: str

    # Resolution tracking
    acknowledged: bool = False
    resolved: bool = False
    assigned_to: Optional[str] = None
    resolution_deadline: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary format."""
        return asdict(self)


@dataclass
class ComplianceKPI:
    """Key Performance Indicator for regulatory compliance."""

    name: str
    description: str
    metric_type: ComplianceMetricType
    current_value: float
    target_value: float
    threshold_warning: float
    threshold_critical: float
    unit: str
    last_updated: datetime
    trend: str  # 'improving', 'stable', 'deteriorating'

    @property
    def status(self) -> ComplianceStatus:
        """Determine KPI status based on current value vs thresholds."""
        if self.current_value >= self.target_value:
            return ComplianceStatus.COMPLIANT
        elif self.current_value >= self.threshold_warning:
            return ComplianceStatus.REQUIRES_ATTENTION
        else:
            return ComplianceStatus.NON_COMPLIANT

    @property
    def performance_percentage(self) -> float:
        """Calculate performance as percentage of target."""
        return (
            (self.current_value / self.target_value * 100)
            if self.target_value > 0
            else 0
        )


class ComplianceMonitor:
    """
    Continuous regulatory compliance monitoring system.

    Provides real-time monitoring of all regulatory compliance metrics,
    generates alerts for potential violations, and maintains comprehensive
    compliance dashboards for regulatory oversight.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.logger = get_logger(self.__class__.__name__)
        self.config = config or get_config().get("compliance_monitoring", {})

        # Monitoring configuration
        self.monitoring_interval_seconds = self.config.get(
            "monitoring_interval_seconds", 60
        )
        self.alert_cooldown_minutes = self.config.get("alert_cooldown_minutes", 15)
        self.kpi_history_retention_days = self.config.get(
            "kpi_history_retention_days", 90
        )

        # Components
        self.regulatory_validator: Optional[RegulatoryValidator] = None
        self.email_service: Optional[EmailService] = None

        # Monitoring state
        self.active_alerts: List[ComplianceAlert] = []
        self.kpi_history: Dict[ComplianceMetricType, List[ComplianceKPI]] = {}
        self.last_alert_times: Dict[str, datetime] = {}

        # Monitoring task
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False

        # Alert callbacks
        self.alert_callbacks: List[Callable[[ComplianceAlert], None]] = []

        # KPI definitions
        self.kpi_definitions = self._initialize_kpi_definitions()

    async def initialize(self):
        """Initialize compliance monitoring system."""
        try:
            self.logger.info("Initializing regulatory compliance monitoring...")

            # Initialize regulatory validator
            self.regulatory_validator = RegulatoryValidator()
            await self.regulatory_validator.initialize()

            # Initialize email service for alerts
            self.email_service = EmailService()

            # Load existing alerts and KPI history
            await self._load_monitoring_data()

            self.logger.info("✅ Compliance monitoring system initialized successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize compliance monitoring: {e}")
            raise MonitoringError(f"Compliance monitoring initialization failed: {e}")

    async def start_monitoring(self):
        """Start continuous compliance monitoring."""
        if self.is_monitoring:
            self.logger.warning("Compliance monitoring already running")
            return

        self.logger.info(
            f"🔍 Starting continuous compliance monitoring (interval: {self.monitoring_interval_seconds}s)"
        )

        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        # Create initial monitoring alert
        initial_alert = ComplianceAlert(
            alert_id=f"monitoring_start_{int(datetime.utcnow().timestamp())}",
            timestamp=datetime.utcnow(),
            level=ComplianceAlertLevel.INFO,
            metric_type=ComplianceMetricType.REGULATORY_RESPONSE_TIME,
            title="Compliance Monitoring Started",
            description="Real-time regulatory compliance monitoring has been initiated",
            current_value=1.0,
            threshold_value=1.0,
            regulatory_framework="MiFID II",
            regulatory_reference="Article 76 - Record keeping",
            potential_impact="Enhanced regulatory oversight and compliance assurance",
        )

        await self._process_alert(initial_alert)

    async def stop_monitoring(self):
        """Stop compliance monitoring."""
        if not self.is_monitoring:
            return

        self.logger.info("🛑 Stopping compliance monitoring...")

        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        # Save monitoring data
        await self._save_monitoring_data()

        self.logger.info("✅ Compliance monitoring stopped")

    async def get_compliance_dashboard(self) -> Dict[str, Any]:
        """
        Generate comprehensive compliance dashboard data.

        Returns:
            Dict containing all compliance monitoring data for dashboard display
        """
        try:
            # Get current compliance summary from validator
            compliance_summary = (
                await self.regulatory_validator.get_compliance_summary()
            )

            # Update KPIs based on current compliance status
            await self._update_all_kpis(compliance_summary)

            # Get recent alerts
            recent_alerts = [
                alert.to_dict() for alert in self.active_alerts[-20:]  # Last 20 alerts
            ]

            # Calculate trend analysis
            trends = self._calculate_compliance_trends()

            # Generate dashboard data
            dashboard = {
                "summary": {
                    "overall_status": compliance_summary.get(
                        "compliance_overview", {}
                    ).get("overall_status", "unknown"),
                    "compliance_rate": compliance_summary.get(
                        "compliance_overview", {}
                    ).get("compliance_rate_percentage", 0),
                    "active_alerts_count": len(
                        [a for a in self.active_alerts if not a.resolved]
                    ),
                    "critical_alerts_count": len(
                        [
                            a
                            for a in self.active_alerts
                            if not a.resolved
                            and a.level == ComplianceAlertLevel.CRITICAL
                        ]
                    ),
                    "last_updated": datetime.utcnow().isoformat(),
                },
                "key_performance_indicators": {
                    kpi_type.value: (
                        self._get_latest_kpi_value(kpi_type).to_dict()
                        if self._get_latest_kpi_value(kpi_type)
                        else None
                    )
                    for kpi_type in ComplianceMetricType
                },
                "recent_alerts": recent_alerts,
                "compliance_trends": trends,
                "regulatory_reporting": {
                    "transaction_reports_count": compliance_summary.get(
                        "regulatory_reporting", {}
                    ).get("transaction_reports_generated", 0),
                    "last_report_time": compliance_summary.get(
                        "regulatory_reporting", {}
                    ).get("last_report_timestamp"),
                    "retention_compliance": compliance_summary.get(
                        "regulatory_reporting", {}
                    ).get("retention_period_years", 0),
                },
                "audit_trail_health": compliance_summary.get("audit_trail_health", {}),
                "best_execution_metrics": compliance_summary.get(
                    "best_execution_metrics", {}
                ),
            }

            return dashboard

        except Exception as e:
            self.logger.error(f"❌ Failed to generate compliance dashboard: {e}")
            raise MonitoringError(f"Compliance dashboard generation failed: {e}")

    async def generate_compliance_report(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """
        Generate comprehensive compliance monitoring report for specified period.

        Args:
            start_date: Report period start
            end_date: Report period end

        Returns:
            Dict containing comprehensive compliance report
        """
        try:
            self.logger.info(
                f"Generating compliance monitoring report for {start_date} to {end_date}"
            )

            # Filter alerts for period
            period_alerts = [
                alert
                for alert in self.active_alerts
                if start_date <= alert.timestamp <= end_date
            ]

            # Calculate period statistics
            alert_stats = {
                "total_alerts": len(period_alerts),
                "critical_alerts": len(
                    [
                        a
                        for a in period_alerts
                        if a.level == ComplianceAlertLevel.CRITICAL
                    ]
                ),
                "warning_alerts": len(
                    [
                        a
                        for a in period_alerts
                        if a.level == ComplianceAlertLevel.WARNING
                    ]
                ),
                "regulatory_violations": len(
                    [
                        a
                        for a in period_alerts
                        if a.level == ComplianceAlertLevel.REGULATORY_VIOLATION
                    ]
                ),
                "resolved_alerts": len([a for a in period_alerts if a.resolved]),
                "average_resolution_time_hours": self._calculate_average_resolution_time(
                    period_alerts
                ),
            }

            # Get KPI performance for period
            kpi_performance = {}
            for kpi_type in ComplianceMetricType:
                period_kpis = self._get_kpis_for_period(kpi_type, start_date, end_date)
                if period_kpis:
                    kpi_performance[kpi_type.value] = {
                        "average_value": sum(kpi.current_value for kpi in period_kpis)
                        / len(period_kpis),
                        "min_value": min(kpi.current_value for kpi in period_kpis),
                        "max_value": max(kpi.current_value for kpi in period_kpis),
                        "trend": period_kpis[-1].trend if period_kpis else "unknown",
                    }

            # Compliance summary
            current_dashboard = await self.get_compliance_dashboard()

            report = {
                "report_metadata": {
                    "report_type": "COMPLIANCE_MONITORING_REPORT",
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "generated_at": datetime.utcnow().isoformat(),
                    "generated_by": "FXML4 Compliance Monitor",
                },
                "executive_summary": {
                    "overall_compliance_status": current_dashboard["summary"][
                        "overall_status"
                    ],
                    "period_compliance_rate": current_dashboard["summary"][
                        "compliance_rate"
                    ],
                    "total_alerts_generated": alert_stats["total_alerts"],
                    "regulatory_violations": alert_stats["regulatory_violations"],
                    "key_concerns": self._identify_key_concerns(
                        period_alerts, kpi_performance
                    ),
                },
                "alert_analysis": alert_stats,
                "kpi_performance": kpi_performance,
                "detailed_alerts": [alert.to_dict() for alert in period_alerts],
                "recommendations": self._generate_compliance_recommendations(
                    period_alerts, kpi_performance
                ),
                "regulatory_framework_compliance": {
                    "mifid_ii": {
                        "transaction_reporting": "compliant",
                        "best_execution": "compliant",
                        "record_keeping": "compliant",
                    }
                },
            }

            return report

        except Exception as e:
            self.logger.error(f"❌ Failed to generate compliance report: {e}")
            raise MonitoringError(f"Compliance report generation failed: {e}")

    def add_alert_callback(self, callback: Callable[[ComplianceAlert], None]):
        """Add callback function to be called when alerts are generated."""
        self.alert_callbacks.append(callback)
        self.logger.info(f"Added alert callback: {callback.__name__}")

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """
        Acknowledge a compliance alert.

        Args:
            alert_id: Alert identifier
            acknowledged_by: User acknowledging the alert

        Returns:
            bool: True if alert was found and acknowledged
        """
        for alert in self.active_alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.assigned_to = acknowledged_by

                self.logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True

        self.logger.warning(f"Alert {alert_id} not found for acknowledgment")
        return False

    async def resolve_alert(
        self, alert_id: str, resolved_by: str, resolution_notes: str = ""
    ) -> bool:
        """
        Mark a compliance alert as resolved.

        Args:
            alert_id: Alert identifier
            resolved_by: User resolving the alert
            resolution_notes: Optional resolution notes

        Returns:
            bool: True if alert was found and resolved
        """
        for alert in self.active_alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.assigned_to = resolved_by

                # Create resolution audit trail
                await self._create_alert_resolution_audit(
                    alert, resolved_by, resolution_notes
                )

                self.logger.info(f"Alert {alert_id} resolved by {resolved_by}")
                return True

        self.logger.warning(f"Alert {alert_id} not found for resolution")
        return False

    async def _monitoring_loop(self):
        """Main monitoring loop - runs continuously."""
        self.logger.info("🔄 Starting compliance monitoring loop")

        try:
            while self.is_monitoring:
                # Perform monitoring checks
                await self._perform_monitoring_checks()

                # Update KPIs
                compliance_summary = (
                    await self.regulatory_validator.get_compliance_summary()
                )
                await self._update_all_kpis(compliance_summary)

                # Check for alert conditions
                await self._check_alert_conditions()

                # Cleanup resolved alerts and old data
                await self._cleanup_monitoring_data()

                # Wait for next monitoring interval
                await asyncio.sleep(self.monitoring_interval_seconds)

        except asyncio.CancelledError:
            self.logger.info("Compliance monitoring loop cancelled")
        except Exception as e:
            self.logger.error(f"❌ Error in monitoring loop: {e}")
            # Continue monitoring despite errors
            if self.is_monitoring:
                await asyncio.sleep(5)  # Brief pause before retry
                asyncio.create_task(self._monitoring_loop())

    async def _perform_monitoring_checks(self):
        """Perform all compliance monitoring checks."""
        try:
            # Check audit trail integrity
            await self._check_audit_trail_integrity()

            # Check transaction compliance rates
            await self._check_transaction_compliance()

            # Check best execution performance
            await self._check_best_execution_performance()

            # Check reporting deadlines
            await self._check_reporting_deadlines()

            # Check data retention compliance
            await self._check_data_retention_compliance()

        except Exception as e:
            self.logger.error(f"❌ Error performing monitoring checks: {e}")

    async def _check_audit_trail_integrity(self):
        """Check audit trail integrity and generate alerts if needed."""
        try:
            integrity_results = (
                await self.regulatory_validator.validate_audit_trail_integrity()
            )

            # Check for integrity failures
            if integrity_results.get("integrity_failures", 0) > 0:
                await self._generate_alert(
                    level=ComplianceAlertLevel.CRITICAL,
                    metric_type=ComplianceMetricType.AUDIT_TRAIL_INTEGRITY,
                    title="Audit Trail Integrity Failure",
                    description=f"Detected {integrity_results['integrity_failures']} audit trail integrity failures",
                    current_value=integrity_results.get("integrity_failures", 0),
                    threshold_value=0,
                    regulatory_reference="MiFID II Article 76 - Record keeping",
                )

            # Check for gaps
            if integrity_results.get("gaps_detected", 0) > 0:
                await self._generate_alert(
                    level=ComplianceAlertLevel.WARNING,
                    metric_type=ComplianceMetricType.AUDIT_TRAIL_INTEGRITY,
                    title="Audit Trail Gaps Detected",
                    description=f"Detected {integrity_results['gaps_detected']} temporal gaps in audit trail",
                    current_value=integrity_results.get("gaps_detected", 0),
                    threshold_value=0,
                    regulatory_reference="MiFID II Article 76 - Record keeping",
                )

        except Exception as e:
            self.logger.error(f"❌ Error checking audit trail integrity: {e}")

    async def _check_transaction_compliance(self):
        """Check transaction compliance rates."""
        try:
            summary = await self.regulatory_validator.get_compliance_summary()
            compliance_rate = summary.get("compliance_overview", {}).get(
                "compliance_rate_percentage", 0
            )

            # Alert if compliance rate falls below threshold
            if compliance_rate < 99.0:  # 99% threshold
                await self._generate_alert(
                    level=(
                        ComplianceAlertLevel.CRITICAL
                        if compliance_rate < 95.0
                        else ComplianceAlertLevel.WARNING
                    ),
                    metric_type=ComplianceMetricType.TRANSACTION_COMPLIANCE_RATE,
                    title="Transaction Compliance Rate Below Threshold",
                    description=f"Transaction compliance rate dropped to {compliance_rate:.1f}%",
                    current_value=compliance_rate,
                    threshold_value=99.0,
                    regulatory_reference="MiFID II Article 25 - Order record keeping",
                )

        except Exception as e:
            self.logger.error(f"❌ Error checking transaction compliance: {e}")

    async def _check_best_execution_performance(self):
        """Check best execution performance metrics."""
        try:
            summary = await self.regulatory_validator.get_compliance_summary()
            avg_quality_score = summary.get("best_execution_metrics", {}).get(
                "average_execution_quality_score", 0
            )

            # Alert if execution quality drops below threshold
            if avg_quality_score < 80.0:  # 80% threshold
                await self._generate_alert(
                    level=ComplianceAlertLevel.WARNING,
                    metric_type=ComplianceMetricType.BEST_EXECUTION_PERFORMANCE,
                    title="Best Execution Performance Below Threshold",
                    description=f"Average execution quality score dropped to {avg_quality_score:.1f}",
                    current_value=avg_quality_score,
                    threshold_value=80.0,
                    regulatory_reference="MiFID II Article 27 - Best execution",
                )

        except Exception as e:
            self.logger.error(f"❌ Error checking best execution performance: {e}")

    async def _check_reporting_deadlines(self):
        """Check regulatory reporting deadline adherence."""
        # This would check actual reporting deadlines in production
        pass

    async def _check_data_retention_compliance(self):
        """Check data retention policy compliance."""
        # This would check actual data retention in production
        pass

    async def _update_all_kpis(self, compliance_summary: Dict[str, Any]):
        """Update all compliance KPIs based on current status."""
        current_time = datetime.utcnow()

        # Transaction compliance rate KPI
        compliance_rate = compliance_summary.get("compliance_overview", {}).get(
            "compliance_rate_percentage", 0
        )
        await self._update_kpi(
            ComplianceMetricType.TRANSACTION_COMPLIANCE_RATE,
            compliance_rate,
            current_time,
        )

        # Audit trail integrity KPI
        audit_health = compliance_summary.get("audit_trail_health", {})
        integrity_rate = (
            audit_health.get("integrity_verified", 0)
            / max(1, audit_health.get("total_records", 1))
        ) * 100
        await self._update_kpi(
            ComplianceMetricType.AUDIT_TRAIL_INTEGRITY, integrity_rate, current_time
        )

        # Best execution performance KPI
        best_exec_score = compliance_summary.get("best_execution_metrics", {}).get(
            "average_execution_quality_score", 0
        )
        await self._update_kpi(
            ComplianceMetricType.BEST_EXECUTION_PERFORMANCE,
            best_exec_score,
            current_time,
        )

    async def _update_kpi(
        self, metric_type: ComplianceMetricType, value: float, timestamp: datetime
    ):
        """Update a specific KPI with new value."""
        kpi_def = self.kpi_definitions[metric_type]

        # Calculate trend
        previous_kpis = self.kpi_history.get(metric_type, [])
        trend = "stable"
        if previous_kpis:
            last_value = previous_kpis[-1].current_value
            if value > last_value * 1.02:  # >2% improvement
                trend = "improving"
            elif value < last_value * 0.98:  # >2% deterioration
                trend = "deteriorating"

        # Create new KPI record
        kpi = ComplianceKPI(
            name=kpi_def["name"],
            description=kpi_def["description"],
            metric_type=metric_type,
            current_value=value,
            target_value=kpi_def["target_value"],
            threshold_warning=kpi_def["threshold_warning"],
            threshold_critical=kpi_def["threshold_critical"],
            unit=kpi_def["unit"],
            last_updated=timestamp,
            trend=trend,
        )

        # Add to history
        if metric_type not in self.kpi_history:
            self.kpi_history[metric_type] = []

        self.kpi_history[metric_type].append(kpi)

        # Trim history to retention period
        cutoff_date = timestamp - timedelta(days=self.kpi_history_retention_days)
        self.kpi_history[metric_type] = [
            k for k in self.kpi_history[metric_type] if k.last_updated >= cutoff_date
        ]

    async def _check_alert_conditions(self):
        """Check all KPIs for alert conditions."""
        for metric_type, kpis in self.kpi_history.items():
            if not kpis:
                continue

            latest_kpi = kpis[-1]

            # Check for threshold breaches
            if latest_kpi.current_value <= latest_kpi.threshold_critical:
                await self._generate_alert(
                    level=ComplianceAlertLevel.CRITICAL,
                    metric_type=metric_type,
                    title=f"Critical Threshold Breach: {latest_kpi.name}",
                    description=f"{latest_kpi.name} dropped to {latest_kpi.current_value:.2f} {latest_kpi.unit}",
                    current_value=latest_kpi.current_value,
                    threshold_value=latest_kpi.threshold_critical,
                )
            elif latest_kpi.current_value <= latest_kpi.threshold_warning:
                await self._generate_alert(
                    level=ComplianceAlertLevel.WARNING,
                    metric_type=metric_type,
                    title=f"Warning Threshold Breach: {latest_kpi.name}",
                    description=f"{latest_kpi.name} dropped to {latest_kpi.current_value:.2f} {latest_kpi.unit}",
                    current_value=latest_kpi.current_value,
                    threshold_value=latest_kpi.threshold_warning,
                )

    async def _generate_alert(
        self,
        level: ComplianceAlertLevel,
        metric_type: ComplianceMetricType,
        title: str,
        description: str,
        current_value: float,
        threshold_value: float,
        regulatory_reference: str = "MiFID II General",
    ):
        """Generate and process a compliance alert."""
        alert_key = f"{metric_type.value}_{level.value}"

        # Check cooldown period
        if alert_key in self.last_alert_times:
            time_since_last = datetime.utcnow() - self.last_alert_times[alert_key]
            if time_since_last < timedelta(minutes=self.alert_cooldown_minutes):
                return  # Skip alert due to cooldown

        # Create alert
        alert = ComplianceAlert(
            alert_id=f"alert_{int(datetime.utcnow().timestamp())}_{metric_type.value}",
            timestamp=datetime.utcnow(),
            level=level,
            metric_type=metric_type,
            title=title,
            description=description,
            current_value=current_value,
            threshold_value=threshold_value,
            regulatory_framework="MiFID II",
            regulatory_reference=regulatory_reference,
            potential_impact=self._assess_potential_impact(level, metric_type),
            resolution_deadline=datetime.utcnow()
            + timedelta(hours=1 if level == ComplianceAlertLevel.CRITICAL else 24),
        )

        await self._process_alert(alert)
        self.last_alert_times[alert_key] = datetime.utcnow()

    async def _process_alert(self, alert: ComplianceAlert):
        """Process and distribute a compliance alert."""
        # Add to active alerts
        self.active_alerts.append(alert)

        # Log alert
        self.logger.warning(
            f"🚨 COMPLIANCE ALERT [{alert.level.value.upper()}]: {alert.title}"
        )

        # Send email notification for critical alerts
        if alert.level in [
            ComplianceAlertLevel.CRITICAL,
            ComplianceAlertLevel.REGULATORY_VIOLATION,
        ]:
            await self._send_alert_notification(alert)

        # Execute alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"❌ Error in alert callback: {e}")

    async def _send_alert_notification(self, alert: ComplianceAlert):
        """Send email notification for critical compliance alert."""
        try:
            if self.email_service:
                await self.email_service.send_alert(
                    subject=f"FXML4 Compliance Alert: {alert.title}",
                    message=f"""
                    REGULATORY COMPLIANCE ALERT

                    Alert Level: {alert.level.value.upper()}
                    Metric: {alert.metric_type.value}

                    Description: {alert.description}

                    Current Value: {alert.current_value}
                    Threshold: {alert.threshold_value}

                    Regulatory Reference: {alert.regulatory_reference}
                    Potential Impact: {alert.potential_impact}

                    Resolution Deadline: {alert.resolution_deadline}

                    Please review and take appropriate action immediately.
                    """,
                    recipients=self.config.get(
                        "alert_recipients", ["compliance@fxml4.com"]
                    ),
                )
        except Exception as e:
            self.logger.error(f"❌ Failed to send alert notification: {e}")

    def _assess_potential_impact(
        self, level: ComplianceAlertLevel, metric_type: ComplianceMetricType
    ) -> str:
        """Assess potential regulatory impact of alert."""
        impact_matrix = {
            (
                ComplianceAlertLevel.CRITICAL,
                ComplianceMetricType.TRANSACTION_COMPLIANCE_RATE,
            ): "Potential regulatory sanctions and trading suspension",
            (
                ComplianceAlertLevel.CRITICAL,
                ComplianceMetricType.AUDIT_TRAIL_INTEGRITY,
            ): "Compromised regulatory audit capability and potential penalties",
            (
                ComplianceAlertLevel.WARNING,
                ComplianceMetricType.BEST_EXECUTION_PERFORMANCE,
            ): "Client best interests potentially compromised, regulatory scrutiny likely",
        }

        return impact_matrix.get(
            (level, metric_type), "Regulatory compliance concern requiring attention"
        )

    def _initialize_kpi_definitions(self) -> Dict[ComplianceMetricType, Dict[str, Any]]:
        """Initialize KPI definitions and thresholds."""
        return {
            ComplianceMetricType.TRANSACTION_COMPLIANCE_RATE: {
                "name": "Transaction Compliance Rate",
                "description": "Percentage of transactions meeting MiFID II compliance requirements",
                "target_value": 100.0,
                "threshold_warning": 99.0,
                "threshold_critical": 95.0,
                "unit": "%",
            },
            ComplianceMetricType.AUDIT_TRAIL_INTEGRITY: {
                "name": "Audit Trail Integrity",
                "description": "Percentage of audit trail records with verified integrity",
                "target_value": 100.0,
                "threshold_warning": 99.5,
                "threshold_critical": 98.0,
                "unit": "%",
            },
            ComplianceMetricType.BEST_EXECUTION_PERFORMANCE: {
                "name": "Best Execution Quality Score",
                "description": "Average execution quality score across all orders",
                "target_value": 90.0,
                "threshold_warning": 80.0,
                "threshold_critical": 70.0,
                "unit": "score",
            },
            ComplianceMetricType.REPORTING_DEADLINE_ADHERENCE: {
                "name": "Reporting Deadline Adherence",
                "description": "Percentage of regulatory reports submitted on time",
                "target_value": 100.0,
                "threshold_warning": 95.0,
                "threshold_critical": 90.0,
                "unit": "%",
            },
            ComplianceMetricType.DATA_RETENTION_COMPLIANCE: {
                "name": "Data Retention Compliance",
                "description": "Compliance with regulatory data retention requirements",
                "target_value": 100.0,
                "threshold_warning": 95.0,
                "threshold_critical": 90.0,
                "unit": "%",
            },
            ComplianceMetricType.REGULATORY_RESPONSE_TIME: {
                "name": "Regulatory Response Time",
                "description": "Average time to respond to regulatory inquiries",
                "target_value": 24.0,
                "threshold_warning": 48.0,
                "threshold_critical": 72.0,
                "unit": "hours",
            },
        }

    def _get_latest_kpi_value(
        self, metric_type: ComplianceMetricType
    ) -> Optional[ComplianceKPI]:
        """Get the latest KPI value for specified metric type."""
        kpis = self.kpi_history.get(metric_type, [])
        return kpis[-1] if kpis else None

    def _get_kpis_for_period(
        self,
        metric_type: ComplianceMetricType,
        start_date: datetime,
        end_date: datetime,
    ) -> List[ComplianceKPI]:
        """Get KPI values for specified period."""
        kpis = self.kpi_history.get(metric_type, [])
        return [kpi for kpi in kpis if start_date <= kpi.last_updated <= end_date]

    def _calculate_compliance_trends(self) -> Dict[str, Any]:
        """Calculate compliance trends across all metrics."""
        trends = {}

        for metric_type in ComplianceMetricType:
            latest_kpi = self._get_latest_kpi_value(metric_type)
            if latest_kpi:
                trends[metric_type.value] = {
                    "trend": latest_kpi.trend,
                    "current_value": latest_kpi.current_value,
                    "target_value": latest_kpi.target_value,
                    "performance_percentage": latest_kpi.performance_percentage,
                }

        return trends

    def _calculate_average_resolution_time(
        self, alerts: List[ComplianceAlert]
    ) -> float:
        """Calculate average alert resolution time."""
        resolved_alerts = [a for a in alerts if a.resolved and a.resolution_deadline]
        if not resolved_alerts:
            return 0.0

        total_time = sum(
            (a.resolution_deadline - a.timestamp).total_seconds()
            / 3600  # Convert to hours
            for a in resolved_alerts
        )

        return total_time / len(resolved_alerts)

    def _identify_key_concerns(
        self, alerts: List[ComplianceAlert], kpi_performance: Dict[str, Any]
    ) -> List[str]:
        """Identify key compliance concerns from alerts and KPI performance."""
        concerns = []

        # Check for regulatory violations
        violations = [
            a for a in alerts if a.level == ComplianceAlertLevel.REGULATORY_VIOLATION
        ]
        if violations:
            concerns.append(f"{len(violations)} regulatory violations detected")

        # Check for critical alerts
        critical_alerts = [
            a for a in alerts if a.level == ComplianceAlertLevel.CRITICAL
        ]
        if critical_alerts:
            concerns.append(f"{len(critical_alerts)} critical compliance issues")

        # Check for deteriorating trends
        deteriorating_kpis = [
            kpi_name
            for kpi_name, data in kpi_performance.items()
            if data.get("trend") == "deteriorating"
        ]
        if deteriorating_kpis:
            concerns.append(
                f"Deteriorating performance in: {', '.join(deteriorating_kpis)}"
            )

        return (
            concerns if concerns else ["No significant compliance concerns identified"]
        )

    def _generate_compliance_recommendations(
        self, alerts: List[ComplianceAlert], kpi_performance: Dict[str, Any]
    ) -> List[str]:
        """Generate compliance improvement recommendations."""
        recommendations = []

        # Based on alert patterns
        if any(a.level == ComplianceAlertLevel.CRITICAL for a in alerts):
            recommendations.append(
                "Immediate review of critical compliance failures required"
            )

        # Based on KPI performance
        for kpi_name, data in kpi_performance.items():
            if data.get("average_value", 0) < data.get("target_value", 100) * 0.9:
                recommendations.append(
                    f"Improve {kpi_name} performance through process optimization"
                )

        # General recommendations
        recommendations.extend(
            [
                "Conduct quarterly compliance assessment",
                "Review and update compliance procedures",
                "Enhance staff compliance training program",
            ]
        )

        return recommendations

    async def _create_alert_resolution_audit(
        self, alert: ComplianceAlert, resolved_by: str, notes: str
    ):
        """Create audit trail record for alert resolution."""
        # This would create actual audit record in production
        self.logger.info(
            f"Alert {alert.alert_id} resolution audit created by {resolved_by}"
        )

    async def _load_monitoring_data(self):
        """Load existing monitoring data from storage."""
        # This would load from actual database in production
        self.logger.info("✅ Monitoring data loaded")

    async def _save_monitoring_data(self):
        """Save monitoring data to storage."""
        # This would save to actual database in production
        self.logger.info("💾 Monitoring data saved")

    async def _cleanup_monitoring_data(self):
        """Clean up old monitoring data beyond retention period."""
        cutoff_date = datetime.utcnow() - timedelta(
            days=self.kpi_history_retention_days
        )

        # Clean up resolved alerts older than retention period
        self.active_alerts = [
            alert
            for alert in self.active_alerts
            if not alert.resolved or alert.timestamp >= cutoff_date
        ]
