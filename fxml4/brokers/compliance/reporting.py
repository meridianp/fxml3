"""Compliance and Audit Reporting.

This module provides comprehensive reporting capabilities for compliance
monitoring, audit trails, and regulatory reporting requirements.
"""

import asyncio
import csv
import io
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from .audit_logger import AuditCategory, AuditEvent, AuditLogger, AuditSeverity
from .compliance_engine import ComplianceEngine, ComplianceViolation
from .transaction_monitor import SuspiciousActivity, TransactionMonitor

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Types of compliance reports."""

    DAILY_COMPLIANCE = "DAILY_COMPLIANCE"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    AUDIT_TRAIL = "AUDIT_TRAIL"
    REGULATORY_SUMMARY = "REGULATORY_SUMMARY"
    RISK_VIOLATIONS = "RISK_VIOLATIONS"
    TRANSACTION_ANALYSIS = "TRANSACTION_ANALYSIS"
    POSITION_REPORTING = "POSITION_REPORTING"
    BEST_EXECUTION = "BEST_EXECUTION"


class ReportFormat(Enum):
    """Report output formats."""

    JSON = "json"
    CSV = "csv"
    HTML = "html"
    PDF = "pdf"
    EXCEL = "xlsx"


@dataclass
class ReportConfig:
    """Report configuration."""

    report_type: ReportType
    format: ReportFormat
    start_date: datetime
    end_date: datetime

    # Filters
    client_ids: Optional[List[str]] = None
    symbols: Optional[List[str]] = None
    risk_levels: Optional[List[str]] = None
    severities: Optional[List[str]] = None

    # Options
    include_details: bool = True
    aggregate_data: bool = False
    anonymize_data: bool = False

    # Output
    output_path: Optional[str] = None
    email_recipients: Optional[List[str]] = None


class ComplianceReporter:
    """Compliance reporting system."""

    def __init__(
        self,
        compliance_engine: ComplianceEngine,
        transaction_monitor: TransactionMonitor,
        audit_logger: AuditLogger,
        output_dir: Union[str, Path] = "reports/compliance",
    ):
        """Initialize compliance reporter.

        Args:
            compliance_engine: Compliance engine instance.
            transaction_monitor: Transaction monitor instance.
            audit_logger: Audit logger instance.
            output_dir: Output directory for reports.
        """
        self.compliance_engine = compliance_engine
        self.transaction_monitor = transaction_monitor
        self.audit_logger = audit_logger
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Compliance reporter initialized with output dir: {self.output_dir}"
        )

    async def generate_report(self, config: ReportConfig) -> Dict[str, Any]:
        """Generate a compliance report.

        Args:
            config: Report configuration.

        Returns:
            Report data and metadata.
        """
        logger.info(f"Generating {config.report_type.value} report")

        try:
            # Generate report data based on type
            if config.report_type == ReportType.DAILY_COMPLIANCE:
                data = await self._generate_daily_compliance_report(config)
            elif config.report_type == ReportType.SUSPICIOUS_ACTIVITY:
                data = await self._generate_suspicious_activity_report(config)
            elif config.report_type == ReportType.AUDIT_TRAIL:
                data = await self._generate_audit_trail_report(config)
            elif config.report_type == ReportType.REGULATORY_SUMMARY:
                data = await self._generate_regulatory_summary_report(config)
            elif config.report_type == ReportType.RISK_VIOLATIONS:
                data = await self._generate_risk_violations_report(config)
            elif config.report_type == ReportType.TRANSACTION_ANALYSIS:
                data = await self._generate_transaction_analysis_report(config)
            else:
                raise ValueError(f"Unsupported report type: {config.report_type}")

            # Format and save report
            report_metadata = await self._format_and_save_report(data, config)

            # Log report generation
            await self.audit_logger.log_compliance_event(
                event_type="COMPLIANCE_REPORT_GENERATED",
                message=f"Generated {config.report_type.value} report",
                compliance_flags=["REPORTING"],
                details={
                    "report_type": config.report_type.value,
                    "format": config.format.value,
                    "start_date": config.start_date.isoformat(),
                    "end_date": config.end_date.isoformat(),
                    "record_count": len(data.get("records", [])),
                    "output_file": report_metadata.get("output_file"),
                },
            )

            return {
                "status": "success",
                "report_type": config.report_type.value,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
                **report_metadata,
            }

        except Exception as e:
            logger.error(f"Error generating report: {e}")

            # Log error
            await self.audit_logger.log_compliance_event(
                event_type="COMPLIANCE_REPORT_ERROR",
                message=f"Error generating {config.report_type.value} report: {str(e)}",
                compliance_flags=["REPORTING", "ERROR"],
                severity=AuditSeverity.ERROR,
            )

            raise

    async def _generate_daily_compliance_report(
        self, config: ReportConfig
    ) -> Dict[str, Any]:
        """Generate daily compliance summary report."""

        # Get compliance statistics
        compliance_stats = self.compliance_engine.get_compliance_stats()

        # Get transaction monitoring stats
        monitoring_stats = self.transaction_monitor.get_monitoring_stats()

        # Get active alerts
        active_alerts = self.transaction_monitor.get_active_alerts()

        # Get recent violations
        all_violations = self.compliance_engine.violations
        period_violations = [
            v
            for v in all_violations
            if config.start_date <= v.timestamp <= config.end_date
        ]

        # Summary data
        summary = {
            "period": {
                "start_date": config.start_date.isoformat(),
                "end_date": config.end_date.isoformat(),
                "duration_hours": (config.end_date - config.start_date).total_seconds()
                / 3600,
            },
            "compliance": {
                "total_checks": compliance_stats["total_checks"],
                "violations": compliance_stats["total_violations"],
                "blocked_orders": compliance_stats["total_blocked"],
                "violation_rate": compliance_stats["violation_rate"],
                "active_rules": compliance_stats["active_rules"],
            },
            "monitoring": {
                "transactions_monitored": monitoring_stats[
                    "total_transactions_monitored"
                ],
                "suspicious_activities": monitoring_stats["alerts_generated"],
                "active_alerts": monitoring_stats["active_alerts"],
                "false_positive_rate": monitoring_stats["false_positive_rate"],
            },
            "alerts": {
                "total_active": len(active_alerts),
                "high_risk": len(
                    [a for a in active_alerts if a.risk_level.value == "HIGH"]
                ),
                "critical_risk": len(
                    [a for a in active_alerts if a.risk_level.value == "CRITICAL"]
                ),
            },
        }

        # Detailed records
        records = []

        # Add violation records
        for violation in period_violations:
            records.append(
                {
                    "type": "compliance_violation",
                    "timestamp": violation.timestamp.isoformat(),
                    "rule_id": violation.rule_id,
                    "rule_name": violation.rule_name,
                    "severity": violation.severity.value,
                    "message": violation.message,
                    "client_id": getattr(violation, "user_id", None),
                    "symbol": violation.symbol,
                    "order_id": violation.cl_ord_id,
                }
            )

        # Add suspicious activity records
        for alert in active_alerts:
            if config.start_date <= alert.detected_at <= config.end_date:
                records.append(
                    {
                        "type": "suspicious_activity",
                        "timestamp": alert.detected_at.isoformat(),
                        "activity_type": alert.activity_type.value,
                        "risk_level": alert.risk_level.value,
                        "confidence": alert.confidence_score,
                        "description": alert.description,
                        "client_id": alert.client_id,
                        "status": alert.status,
                    }
                )

        return {
            "summary": summary,
            "records": records,
            "rule_performance": compliance_stats["rules"],
            "alert_breakdown": monitoring_stats["alert_types"],
        }

    async def _generate_suspicious_activity_report(
        self, config: ReportConfig
    ) -> Dict[str, Any]:
        """Generate suspicious activity report."""

        # Get all alerts in the period
        all_alerts = (
            list(self.transaction_monitor.active_alerts.values())
            + self.transaction_monitor.alert_history
        )

        period_alerts = [
            alert
            for alert in all_alerts
            if config.start_date <= alert.detected_at <= config.end_date
        ]

        # Apply filters
        if config.client_ids:
            period_alerts = [
                a for a in period_alerts if a.client_id in config.client_ids
            ]

        if config.risk_levels:
            period_alerts = [
                a for a in period_alerts if a.risk_level.value in config.risk_levels
            ]

        # Summary statistics
        summary = {
            "total_alerts": len(period_alerts),
            "unique_clients": len(set(a.client_id for a in period_alerts)),
            "avg_confidence": (
                sum(a.confidence_score for a in period_alerts) / len(period_alerts)
                if period_alerts
                else 0
            ),
            "status_breakdown": {},
            "risk_breakdown": {},
            "activity_breakdown": {},
        }

        # Calculate breakdowns
        for alert in period_alerts:
            # Status breakdown
            status = alert.status
            summary["status_breakdown"][status] = (
                summary["status_breakdown"].get(status, 0) + 1
            )

            # Risk breakdown
            risk = alert.risk_level.value
            summary["risk_breakdown"][risk] = summary["risk_breakdown"].get(risk, 0) + 1

            # Activity type breakdown
            activity = alert.activity_type.value
            summary["activity_breakdown"][activity] = (
                summary["activity_breakdown"].get(activity, 0) + 1
            )

        # Detailed records
        records = []
        for alert in period_alerts:
            record = alert.to_dict()

            # Anonymize if requested
            if config.anonymize_data:
                record["client_id"] = f"CLIENT_{hash(record['client_id']) % 10000:04d}"

            records.append(record)

        return {
            "summary": summary,
            "records": records,
            "period": {
                "start_date": config.start_date.isoformat(),
                "end_date": config.end_date.isoformat(),
            },
        }

    async def _generate_audit_trail_report(
        self, config: ReportConfig
    ) -> Dict[str, Any]:
        """Generate audit trail report."""

        # Note: This is a simplified implementation
        # In a real system, you would query the audit log files

        records = []

        # Get audit statistics
        audit_stats = self.audit_logger.get_audit_stats()

        summary = {
            "audit_categories": len(audit_stats.get("category_files", {})),
            "total_log_size": sum(audit_stats.get("category_files", {}).values()),
            "buffer_size": audit_stats.get("buffer_size", 0),
            "period": {
                "start_date": config.start_date.isoformat(),
                "end_date": config.end_date.isoformat(),
            },
        }

        # Add file information
        for category, size in audit_stats.get("category_files", {}).items():
            records.append(
                {
                    "type": "audit_file",
                    "category": category,
                    "file_size_bytes": size,
                    "last_modified": datetime.now(timezone.utc).isoformat(),
                }
            )

        return {"summary": summary, "records": records}

    async def _generate_regulatory_summary_report(
        self, config: ReportConfig
    ) -> Dict[str, Any]:
        """Generate regulatory compliance summary."""

        # Get compliance rule statistics
        compliance_stats = self.compliance_engine.get_compliance_stats()

        # Group by regulatory framework
        regulatory_rules = {}
        for rule_id, rule_stats in compliance_stats["rules"].items():
            # Extract regulatory framework from rule ID
            if rule_id.startswith("SEC_"):
                framework = "SEC"
            elif rule_id.startswith("MIFID_"):
                framework = "MiFID II"
            elif rule_id.startswith("FISCA_"):
                framework = "FISCA"
            else:
                framework = "INTERNAL"

            if framework not in regulatory_rules:
                regulatory_rules[framework] = {
                    "rules": [],
                    "total_checks": 0,
                    "total_violations": 0,
                }

            regulatory_rules[framework]["rules"].append(rule_stats)
            regulatory_rules[framework]["total_checks"] += rule_stats[
                "checks_performed"
            ]
            regulatory_rules[framework]["total_violations"] += rule_stats[
                "violations_found"
            ]

        # Calculate compliance rates by framework
        for framework, data in regulatory_rules.items():
            data["compliance_rate"] = (
                (data["total_checks"] - data["total_violations"])
                / data["total_checks"]
                * 100
                if data["total_checks"] > 0
                else 100
            )

        summary = {
            "regulatory_frameworks": len(regulatory_rules),
            "overall_compliance_rate": compliance_stats["violation_rate"],
            "total_regulatory_checks": sum(
                f["total_checks"] for f in regulatory_rules.values()
            ),
            "framework_compliance": regulatory_rules,
        }

        return {"summary": summary, "records": list(regulatory_rules.items())}

    async def _generate_risk_violations_report(
        self, config: ReportConfig
    ) -> Dict[str, Any]:
        """Generate risk violations report."""

        # Get violations from compliance engine
        all_violations = self.compliance_engine.violations

        # Filter by period
        period_violations = [
            v
            for v in all_violations
            if config.start_date <= v.timestamp <= config.end_date
        ]

        # Apply filters
        if config.severities:
            period_violations = [
                v for v in period_violations if v.severity.value in config.severities
            ]

        # Summary statistics
        summary = {
            "total_violations": len(period_violations),
            "unique_rules": len(set(v.rule_id for v in period_violations)),
            "auto_blocked": len([v for v in period_violations if v.auto_block]),
            "manual_review_required": len(
                [v for v in period_violations if v.requires_manual_review]
            ),
            "severity_breakdown": {},
            "rule_breakdown": {},
        }

        # Calculate breakdowns
        for violation in period_violations:
            # Severity breakdown
            severity = violation.severity.value
            summary["severity_breakdown"][severity] = (
                summary["severity_breakdown"].get(severity, 0) + 1
            )

            # Rule breakdown
            rule = violation.rule_name
            summary["rule_breakdown"][rule] = summary["rule_breakdown"].get(rule, 0) + 1

        # Detailed records
        records = []
        for violation in period_violations:
            record = violation.to_dict()

            # Anonymize if requested
            if config.anonymize_data and record.get("user_id"):
                record["user_id"] = f"USER_{hash(record['user_id']) % 10000:04d}"

            records.append(record)

        return {"summary": summary, "records": records}

    async def _generate_transaction_analysis_report(
        self, config: ReportConfig
    ) -> Dict[str, Any]:
        """Generate transaction analysis report."""

        # Get transaction data from monitor
        transaction_data = self.transaction_monitor.transaction_history

        # Filter by period
        period_transactions = [
            t
            for t in transaction_data
            if config.start_date <= t["timestamp"] <= config.end_date
        ]

        # Apply filters
        if config.client_ids:
            period_transactions = [
                t
                for t in period_transactions
                if t.get("client_id") in config.client_ids
            ]

        if config.symbols:
            period_transactions = [
                t for t in period_transactions if t.get("symbol") in config.symbols
            ]

        # Calculate statistics
        if period_transactions:
            volumes = [
                t.get("quantity", 0) * t.get("price", 0) for t in period_transactions
            ]
            total_volume = sum(volumes)
            avg_transaction_size = total_volume / len(period_transactions)
            unique_clients = len(
                set(
                    t.get("client_id")
                    for t in period_transactions
                    if t.get("client_id")
                )
            )
            unique_symbols = len(
                set(t.get("symbol") for t in period_transactions if t.get("symbol"))
            )
        else:
            total_volume = avg_transaction_size = unique_clients = unique_symbols = 0

        summary = {
            "total_transactions": len(period_transactions),
            "total_volume": total_volume,
            "average_transaction_size": avg_transaction_size,
            "unique_clients": unique_clients,
            "unique_symbols": unique_symbols,
            "period": {
                "start_date": config.start_date.isoformat(),
                "end_date": config.end_date.isoformat(),
                "duration_hours": (config.end_date - config.start_date).total_seconds()
                / 3600,
            },
        }

        # Aggregate data if requested
        records = period_transactions
        if config.aggregate_data:
            # Group by client and symbol
            aggregated = {}
            for t in period_transactions:
                key = (t.get("client_id"), t.get("symbol"))
                if key not in aggregated:
                    aggregated[key] = {
                        "client_id": t.get("client_id"),
                        "symbol": t.get("symbol"),
                        "transaction_count": 0,
                        "total_volume": 0,
                        "avg_price": 0,
                    }

                aggregated[key]["transaction_count"] += 1
                aggregated[key]["total_volume"] += t.get("quantity", 0) * t.get(
                    "price", 0
                )

            records = list(aggregated.values())

        # Anonymize if requested
        if config.anonymize_data:
            for record in records:
                if "client_id" in record and record["client_id"]:
                    record["client_id"] = (
                        f"CLIENT_{hash(record['client_id']) % 10000:04d}"
                    )

        return {"summary": summary, "records": records}

    async def _format_and_save_report(
        self, data: Dict[str, Any], config: ReportConfig
    ) -> Dict[str, Any]:
        """Format and save report to file."""

        # Generate filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = (
            f"{config.report_type.value.lower()}_{timestamp}.{config.format.value}"
        )

        output_path = config.output_path or str(self.output_dir / filename)

        # Format based on requested format
        if config.format == ReportFormat.JSON:
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2, default=str)

        elif config.format == ReportFormat.CSV:
            # Convert records to CSV
            if data.get("records"):
                df = pd.DataFrame(data["records"])
                df.to_csv(output_path, index=False)
            else:
                # Empty CSV
                with open(output_path, "w") as f:
                    f.write("No records found for the specified criteria\n")

        elif config.format == ReportFormat.HTML:
            html_content = self._generate_html_report(data, config)
            with open(output_path, "w") as f:
                f.write(html_content)

        elif config.format == ReportFormat.EXCEL:
            # Create Excel file with multiple sheets
            with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
                # Summary sheet
                if data.get("summary"):
                    summary_df = pd.DataFrame([data["summary"]])
                    summary_df.to_excel(writer, sheet_name="Summary", index=False)

                # Records sheet
                if data.get("records"):
                    records_df = pd.DataFrame(data["records"])
                    records_df.to_excel(writer, sheet_name="Records", index=False)

        else:
            raise ValueError(f"Unsupported format: {config.format}")

        file_size = Path(output_path).stat().st_size

        return {
            "output_file": output_path,
            "file_size_bytes": file_size,
            "format": config.format.value,
            "record_count": len(data.get("records", [])),
        }

    def _generate_html_report(self, data: Dict[str, Any], config: ReportConfig) -> str:
        """Generate HTML report."""

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{config.report_type.value} Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #2c3e50; }}
                h2 {{ color: #34495e; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .summary {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background: #e9ecef; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <h1>{config.report_type.value} Report</h1>
            <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
            <p>Period: {config.start_date.strftime('%Y-%m-%d')} to {config.end_date.strftime('%Y-%m-%d')}</p>
        """

        # Add summary section
        if data.get("summary"):
            html += "<h2>Summary</h2><div class='summary'>"
            for key, value in data["summary"].items():
                if isinstance(value, dict):
                    html += f"<h3>{key.replace('_', ' ').title()}</h3>"
                    for k, v in value.items():
                        html += f"<div class='metric'><strong>{k.replace('_', ' ').title()}:</strong> {v}</div>"
                else:
                    html += f"<div class='metric'><strong>{key.replace('_', ' ').title()}:</strong> {value}</div>"
            html += "</div>"

        # Add records table
        if data.get("records"):
            html += "<h2>Records</h2>"
            if data["records"]:
                html += "<table><thead><tr>"

                # Headers
                for key in data["records"][0].keys():
                    html += f"<th>{key.replace('_', ' ').title()}</th>"
                html += "</tr></thead><tbody>"

                # Rows (limit to first 1000 for HTML)
                for record in data["records"][:1000]:
                    html += "<tr>"
                    for value in record.values():
                        html += f"<td>{value}</td>"
                    html += "</tr>"

                html += "</tbody></table>"

                if len(data["records"]) > 1000:
                    html += f"<p><em>Showing first 1000 of {len(data['records'])} records</em></p>"
            else:
                html += "<p>No records found.</p>"

        html += "</body></html>"
        return html


class AuditReporter:
    """Audit trail reporting system."""

    def __init__(
        self, audit_logger: AuditLogger, output_dir: Union[str, Path] = "reports/audit"
    ):
        """Initialize audit reporter.

        Args:
            audit_logger: Audit logger instance.
            output_dir: Output directory for reports.
        """
        self.audit_logger = audit_logger
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Audit reporter initialized with output dir: {self.output_dir}")

    async def generate_audit_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        categories: Optional[List[AuditCategory]] = None,
    ) -> Dict[str, Any]:
        """Generate audit summary report."""

        # Get audit statistics
        stats = self.audit_logger.get_audit_stats()

        summary = {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "audit_system": {
                "categories_monitored": len(stats.get("category_files", {})),
                "total_log_size_bytes": sum(stats.get("category_files", {}).values()),
                "buffer_size": stats.get("buffer_size", 0),
            },
            "file_breakdown": stats.get("category_files", {}),
        }

        return summary

    def export_audit_logs(
        self,
        start_date: datetime,
        end_date: datetime,
        categories: Optional[List[AuditCategory]] = None,
        format: ReportFormat = ReportFormat.JSON,
    ) -> str:
        """Export audit logs for the specified period."""

        # Note: This is a simplified implementation
        # In a real system, you would parse the actual log files

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"audit_export_{timestamp}.{format.value}"
        output_path = str(self.output_dir / filename)

        # Create placeholder export
        export_data = {
            "export_info": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "categories": [c.value for c in categories] if categories else "ALL",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "audit_entries": [
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "category": "SYSTEM",
                    "event_type": "AUDIT_EXPORT",
                    "message": "Audit log export requested",
                    "user_id": "SYSTEM",
                }
            ],
        }

        if format == ReportFormat.JSON:
            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2)
        elif format == ReportFormat.CSV:
            df = pd.DataFrame(export_data["audit_entries"])
            df.to_csv(output_path, index=False)

        return output_path
