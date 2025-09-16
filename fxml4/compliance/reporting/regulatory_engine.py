"""
Regulatory Reporting Engine for FXML4.

This module provides comprehensive regulatory reporting capabilities for trading activities,
including real-time and batch reporting, multiple jurisdiction support, and automated
report generation for compliance with financial regulations.
"""

import asyncio
import csv
import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Union

from sqlalchemy import and_, asc, desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fxml4.api.auth.audit_logger import AuditEventType, auth_audit_logger
from fxml4.api.auth.database import get_db
from fxml4.api.auth.models import User
from fxml4.compliance.surveillance.trade_monitor import TradeSurveillanceEngine
from fxml4.config import get_config
from fxml4.core.logging import get_logger

# Import trading models (these would be defined elsewhere)
from fxml4.trading.models import ExecutionReport, Position, Trade


class ReportType(Enum):
    """Types of regulatory reports."""

    TRADE_REPORTING = "trade_reporting"
    POSITION_REPORTING = "position_reporting"
    TRANSACTION_REPORTING = "transaction_reporting"
    RISK_REPORTING = "risk_reporting"
    SURVEILLANCE_REPORTING = "surveillance_reporting"
    DAILY_SUMMARY = "daily_summary"
    MONTHLY_SUMMARY = "monthly_summary"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    LARGE_TRADER = "large_trader"
    SWAP_DATA_REPOSITORY = "swap_data_repository"


class ReportFormat(Enum):
    """Supported report formats."""

    CSV = "csv"
    XML = "xml"
    JSON = "json"
    FIX = "fix"
    REGULATORY_XML = "regulatory_xml"


class RegulatoryJurisdiction(Enum):
    """Regulatory jurisdictions and authorities."""

    US_CFTC = "us_cftc"  # Commodity Futures Trading Commission
    US_FINRA = "us_finra"  # Financial Industry Regulatory Authority
    EU_MIFID = "eu_mifid"  # Markets in Financial Instruments Directive
    UK_FCA = "uk_fca"  # Financial Conduct Authority
    SINGAPORE_MAS = "singapore_mas"  # Monetary Authority of Singapore
    HONG_KONG_SFC = "hong_kong_sfc"  # Securities and Futures Commission
    JAPAN_FSA = "japan_fsa"  # Financial Services Agency


class ReportPriority(Enum):
    """Report generation priorities."""

    CRITICAL = "critical"  # Real-time/immediate reporting
    HIGH = "high"  # Within 15 minutes
    NORMAL = "normal"  # Within 1 hour
    LOW = "low"  # End of day


class ReportStatus(Enum):
    """Report status tracking."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class ReportSpecification:
    """Regulatory report specification."""

    report_type: ReportType
    jurisdiction: RegulatoryJurisdiction
    format: ReportFormat
    frequency: str  # "real_time", "hourly", "daily", "weekly", "monthly"
    fields: List[str]
    filters: Dict[str, Any]
    deadline_minutes: int  # Minutes from event to submission deadline
    is_mandatory: bool
    template_path: Optional[str] = None
    validation_rules: Dict[str, Any] = None


@dataclass
class ReportGenerationTask:
    """Task for generating a regulatory report."""

    task_id: str
    report_spec: ReportSpecification
    start_time: datetime
    end_time: datetime
    priority: ReportPriority
    status: ReportStatus
    created_at: datetime
    parameters: Dict[str, Any]
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class TradeReportRecord:
    """Standard trade report record structure."""

    trade_id: str
    timestamp: datetime
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    price: float
    counterparty: str
    trader_id: str
    account_id: str
    execution_venue: str
    order_id: str
    settlement_date: datetime
    trade_type: str
    currency: str
    commission: float
    regulatory_status: str
    unique_trade_identifier: str  # UTI for regulatory purposes


class RegulatoryReportingEngine:
    """
    Comprehensive regulatory reporting engine for forex trading compliance.

    Features:
    - Multi-jurisdiction support with different regulatory requirements
    - Real-time and batch report generation
    - Multiple export formats (CSV, XML, JSON, FIX)
    - Automated report scheduling and submission
    - Report validation and error handling
    - Audit trail and compliance tracking
    """

    def __init__(self):
        """Initialize the regulatory reporting engine."""
        self.config = get_config()
        self.logger = get_logger(__name__)

        # Configuration
        self.enable_real_time_reporting = self.config.get(
            "compliance.reporting.real_time_enabled", True
        )
        self.report_storage_path = Path(
            self.config.get("compliance.reporting.storage_path", "./reports")
        )
        self.max_concurrent_reports = self.config.get(
            "compliance.reporting.max_concurrent", 10
        )
        self.report_retention_days = self.config.get(
            "compliance.reporting.retention_days", 2555
        )  # 7 years

        # State management
        self.active_tasks: Dict[str, ReportGenerationTask] = {}
        self.report_specifications: Dict[str, ReportSpecification] = {}
        self.submission_queue: asyncio.Queue = asyncio.Queue()

        # Ensure report storage directory exists
        self.report_storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize default report specifications
        self._initialize_default_specifications()

        # Metrics tracking
        self.reports_generated = 0
        self.reports_failed = 0
        self.reports_submitted = 0
        self.last_report_generation = None

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()

        self.logger.info("RegulatoryReportingEngine initialized successfully")

    def _initialize_default_specifications(self):
        """Initialize default regulatory report specifications."""

        # US CFTC Trade Reporting
        self.report_specifications["us_cftc_trade_report"] = ReportSpecification(
            report_type=ReportType.TRADE_REPORTING,
            jurisdiction=RegulatoryJurisdiction.US_CFTC,
            format=ReportFormat.XML,
            frequency="real_time",
            fields=[
                "trade_id",
                "timestamp",
                "symbol",
                "side",
                "quantity",
                "price",
                "counterparty",
                "trader_id",
                "execution_venue",
                "settlement_date",
            ],
            filters={"min_notional": 1000000},  # $1M minimum notional
            deadline_minutes=15,  # 15-minute reporting deadline
            is_mandatory=True,
            validation_rules={
                "required_fields": [
                    "trade_id",
                    "timestamp",
                    "symbol",
                    "quantity",
                    "price",
                ],
                "price_precision": 5,
                "quantity_min": 0.01,
            },
        )

        # EU MiFID II Transaction Reporting
        self.report_specifications["eu_mifid_transaction_report"] = ReportSpecification(
            report_type=ReportType.TRANSACTION_REPORTING,
            jurisdiction=RegulatoryJurisdiction.EU_MIFID,
            format=ReportFormat.REGULATORY_XML,
            frequency="daily",
            fields=[
                "trade_id",
                "timestamp",
                "symbol",
                "side",
                "quantity",
                "price",
                "client_id",
                "investment_decision_maker",
                "execution_decision_maker",
            ],
            filters={"eu_clients_only": True},
            deadline_minutes=1440,  # T+1 reporting
            is_mandatory=True,
        )

        # US FINRA Large Trader Reporting
        self.report_specifications["us_finra_large_trader"] = ReportSpecification(
            report_type=ReportType.LARGE_TRADER,
            jurisdiction=RegulatoryJurisdiction.US_FINRA,
            format=ReportFormat.CSV,
            frequency="monthly",
            fields=[
                "trader_id",
                "account_id",
                "monthly_volume",
                "average_daily_volume",
                "largest_single_trade",
                "trading_days_active",
            ],
            filters={"min_monthly_volume": 50000000},  # $50M monthly volume threshold
            deadline_minutes=43200,  # Monthly deadline (30 days)
            is_mandatory=True,
        )

        # Suspicious Activity Reporting
        self.report_specifications["suspicious_activity_report"] = ReportSpecification(
            report_type=ReportType.SUSPICIOUS_ACTIVITY,
            jurisdiction=RegulatoryJurisdiction.US_FINRA,
            format=ReportFormat.JSON,
            frequency="real_time",
            fields=[
                "alert_id",
                "trader_id",
                "pattern_type",
                "detection_time",
                "trades_involved",
                "risk_score",
                "description",
            ],
            filters={"min_risk_score": 0.7},
            deadline_minutes=30,  # 30-minute alert reporting
            is_mandatory=True,
        )

        self.logger.info(
            f"Initialized {len(self.report_specifications)} default report specifications"
        )

    async def generate_report(
        self,
        report_type: str,
        start_time: datetime,
        end_time: datetime,
        parameters: Optional[Dict[str, Any]] = None,
        priority: ReportPriority = ReportPriority.NORMAL,
    ) -> str:
        """
        Generate a regulatory report.

        Args:
            report_type: Type of report to generate
            start_time: Report period start time
            end_time: Report period end time
            parameters: Additional report parameters
            priority: Report generation priority

        Returns:
            Task ID for tracking report generation
        """

        if report_type not in self.report_specifications:
            raise ValueError(f"Unknown report type: {report_type}")

        report_spec = self.report_specifications[report_type]
        task_id = f"{report_type}_{int(datetime.now().timestamp())}"

        task = ReportGenerationTask(
            task_id=task_id,
            report_spec=report_spec,
            start_time=start_time,
            end_time=end_time,
            priority=priority,
            status=ReportStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            parameters=parameters or {},
        )

        self.active_tasks[task_id] = task

        # Schedule report generation
        background_task = asyncio.create_task(self._process_report_task(task))
        self._background_tasks.add(background_task)
        background_task.add_done_callback(self._background_tasks.discard)

        self.logger.info(f"Scheduled report generation: {task_id} ({report_type})")
        return task_id

    async def _process_report_task(self, task: ReportGenerationTask):
        """Process a report generation task."""

        try:
            task.status = ReportStatus.GENERATING
            self.logger.info(f"Starting report generation: {task.task_id}")

            # Generate report data based on type
            if task.report_spec.report_type == ReportType.TRADE_REPORTING:
                report_data = await self._generate_trade_report(task)
            elif task.report_spec.report_type == ReportType.SUSPICIOUS_ACTIVITY:
                report_data = await self._generate_suspicious_activity_report(task)
            elif task.report_spec.report_type == ReportType.LARGE_TRADER:
                report_data = await self._generate_large_trader_report(task)
            elif task.report_spec.report_type == ReportType.DAILY_SUMMARY:
                report_data = await self._generate_daily_summary_report(task)
            else:
                raise ValueError(
                    f"Unsupported report type: {task.report_spec.report_type}"
                )

            # Format and save report
            output_path = await self._format_and_save_report(task, report_data)
            task.output_path = str(output_path)
            task.status = ReportStatus.COMPLETED

            self.reports_generated += 1
            self.last_report_generation = datetime.now(timezone.utc)

            # Add to submission queue if required
            if task.report_spec.is_mandatory:
                await self.submission_queue.put(task)

            self.logger.info(f"Report generated successfully: {task.task_id}")

        except Exception as e:
            task.status = ReportStatus.FAILED
            task.error_message = str(e)
            self.reports_failed += 1

            self.logger.error(f"Report generation failed: {task.task_id} - {e}")

            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                self.logger.info(
                    f"Retrying report generation: {task.task_id} (attempt {task.retry_count})"
                )

                # Exponential backoff
                retry_delay = 2**task.retry_count * 60  # 2, 4, 8 minutes
                await asyncio.sleep(retry_delay)

                background_task = asyncio.create_task(self._process_report_task(task))
                self._background_tasks.add(background_task)
                background_task.add_done_callback(self._background_tasks.discard)

    async def _generate_trade_report(
        self, task: ReportGenerationTask
    ) -> List[TradeReportRecord]:
        """Generate trade reporting data."""

        async with get_db() as db:
            # Query trades within the specified time range
            query = (
                select(Trade)
                .where(
                    and_(
                        Trade.timestamp >= task.start_time,
                        Trade.timestamp <= task.end_time,
                    )
                )
                .options(selectinload(Trade.user))
            )

            # Apply filters from report specification
            filters = task.report_spec.filters
            if "min_notional" in filters:
                query = query.where(
                    Trade.quantity * Trade.price >= filters["min_notional"]
                )

            result = await db.execute(query)
            trades = result.scalars().all()

            # Convert to report records
            report_records = []
            for trade in trades:
                record = TradeReportRecord(
                    trade_id=trade.id,
                    timestamp=trade.timestamp,
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                    price=trade.price,
                    counterparty=trade.counterparty or "BROKER",
                    trader_id=trade.user.username if trade.user else "UNKNOWN",
                    account_id=trade.account_id or "DEFAULT",
                    execution_venue=trade.execution_venue or "OTC",
                    order_id=trade.order_id,
                    settlement_date=trade.settlement_date
                    or (trade.timestamp + timedelta(days=2)),
                    trade_type="SPOT",
                    currency="USD",
                    commission=trade.commission or 0.0,
                    regulatory_status="NORMAL",
                    unique_trade_identifier=f"FXML4_{trade.id}_{int(trade.timestamp.timestamp())}",
                )
                report_records.append(record)

            self.logger.info(
                f"Generated trade report with {len(report_records)} records"
            )
            return report_records

    async def _generate_suspicious_activity_report(
        self, task: ReportGenerationTask
    ) -> List[Dict[str, Any]]:
        """Generate suspicious activity report using surveillance data."""

        # This would integrate with the TradeSurveillanceEngine
        surveillance_engine = TradeSurveillanceEngine()

        # Get alerts from surveillance system
        alerts = surveillance_engine.get_alerts_by_time_range(
            task.start_time, task.end_time
        )

        # Filter alerts by risk score threshold
        min_risk_score = task.report_spec.filters.get("min_risk_score", 0.5)
        high_risk_alerts = [
            alert for alert in alerts if alert.risk_score >= min_risk_score
        ]

        report_data = []
        for alert in high_risk_alerts:
            report_data.append(
                {
                    "alert_id": alert.alert_id,
                    "trader_id": alert.user_id,
                    "pattern_type": alert.alert_type.value,
                    "detection_time": alert.created_at.isoformat(),
                    "trades_involved": len(alert.related_trades),
                    "risk_score": alert.risk_score,
                    "description": alert.description,
                    "severity": alert.severity.value,
                    "status": alert.status,
                }
            )

        self.logger.info(
            f"Generated suspicious activity report with {len(report_data)} alerts"
        )
        return report_data

    async def _generate_large_trader_report(
        self, task: ReportGenerationTask
    ) -> List[Dict[str, Any]]:
        """Generate large trader report."""

        async with get_db() as db:
            # Calculate monthly trading volumes by trader
            query = text(
                """
                SELECT
                    u.username as trader_id,
                    t.account_id,
                    SUM(t.quantity * t.price) as monthly_volume,
                    AVG(t.quantity * t.price) as average_daily_volume,
                    MAX(t.quantity * t.price) as largest_single_trade,
                    COUNT(DISTINCT DATE(t.timestamp)) as trading_days_active
                FROM trades t
                JOIN users u ON t.user_id = u.id
                WHERE t.timestamp >= :start_time
                    AND t.timestamp <= :end_time
                GROUP BY u.username, t.account_id
                HAVING SUM(t.quantity * t.price) >= :min_volume
            """
            )

            min_monthly_volume = task.report_spec.filters.get(
                "min_monthly_volume", 50000000
            )

            result = await db.execute(
                query,
                {
                    "start_time": task.start_time,
                    "end_time": task.end_time,
                    "min_volume": min_monthly_volume,
                },
            )

            report_data = []
            for row in result:
                report_data.append(
                    {
                        "trader_id": row.trader_id,
                        "account_id": row.account_id,
                        "monthly_volume": float(row.monthly_volume),
                        "average_daily_volume": float(row.average_daily_volume),
                        "largest_single_trade": float(row.largest_single_trade),
                        "trading_days_active": int(row.trading_days_active),
                    }
                )

            self.logger.info(
                f"Generated large trader report with {len(report_data)} traders"
            )
            return report_data

    async def _generate_daily_summary_report(
        self, task: ReportGenerationTask
    ) -> Dict[str, Any]:
        """Generate daily trading summary report."""

        async with get_db() as db:
            # Summary statistics query
            summary_query = text(
                """
                SELECT
                    COUNT(*) as total_trades,
                    SUM(quantity * price) as total_volume,
                    AVG(quantity * price) as average_trade_size,
                    COUNT(DISTINCT symbol) as symbols_traded,
                    COUNT(DISTINCT user_id) as active_traders,
                    MIN(timestamp) as first_trade_time,
                    MAX(timestamp) as last_trade_time
                FROM trades
                WHERE DATE(timestamp) = DATE(:report_date)
            """
            )

            report_date = task.start_time.date()
            result = await db.execute(summary_query, {"report_date": report_date})
            summary = result.fetchone()

            # Symbol breakdown
            symbol_query = text(
                """
                SELECT
                    symbol,
                    COUNT(*) as trade_count,
                    SUM(quantity * price) as volume
                FROM trades
                WHERE DATE(timestamp) = DATE(:report_date)
                GROUP BY symbol
                ORDER BY volume DESC
            """
            )

            symbol_result = await db.execute(symbol_query, {"report_date": report_date})
            symbol_breakdown = [
                {
                    "symbol": row.symbol,
                    "trade_count": row.trade_count,
                    "volume": float(row.volume),
                }
                for row in symbol_result
            ]

            report_data = {
                "report_date": report_date.isoformat(),
                "summary": {
                    "total_trades": summary.total_trades,
                    "total_volume": float(summary.total_volume or 0),
                    "average_trade_size": float(summary.average_trade_size or 0),
                    "symbols_traded": summary.symbols_traded,
                    "active_traders": summary.active_traders,
                    "first_trade_time": (
                        summary.first_trade_time.isoformat()
                        if summary.first_trade_time
                        else None
                    ),
                    "last_trade_time": (
                        summary.last_trade_time.isoformat()
                        if summary.last_trade_time
                        else None
                    ),
                },
                "symbol_breakdown": symbol_breakdown,
            }

            self.logger.info(f"Generated daily summary report for {report_date}")
            return report_data

    async def _format_and_save_report(
        self, task: ReportGenerationTask, report_data: Any
    ) -> Path:
        """Format report data and save to file."""

        # Create output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{task.report_spec.report_type.value}_{task.report_spec.jurisdiction.value}_{timestamp}"

        if task.report_spec.format == ReportFormat.CSV:
            filename += ".csv"
            output_path = self.report_storage_path / filename

            if isinstance(report_data, list) and report_data:
                # Convert to CSV
                with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                    if isinstance(report_data[0], TradeReportRecord):
                        fieldnames = list(asdict(report_data[0]).keys())
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        for record in report_data:
                            writer.writerow(asdict(record))
                    else:
                        fieldnames = list(report_data[0].keys())
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(report_data)

        elif task.report_spec.format == ReportFormat.JSON:
            filename += ".json"
            output_path = self.report_storage_path / filename

            # Convert TradeReportRecord objects to dicts
            if (
                isinstance(report_data, list)
                and report_data
                and isinstance(report_data[0], TradeReportRecord)
            ):
                json_data = [asdict(record) for record in report_data]
            else:
                json_data = report_data

            with open(output_path, "w", encoding="utf-8") as jsonfile:
                json.dump(json_data, jsonfile, indent=2, default=str)

        elif task.report_spec.format == ReportFormat.XML:
            filename += ".xml"
            output_path = self.report_storage_path / filename

            # Generate XML format
            await self._generate_xml_report(output_path, task, report_data)

        else:
            raise ValueError(f"Unsupported report format: {task.report_spec.format}")

        self.logger.info(f"Report saved to: {output_path}")
        return output_path

    async def _generate_xml_report(
        self, output_path: Path, task: ReportGenerationTask, report_data: Any
    ):
        """Generate XML format report."""

        root = ET.Element("RegulatoryReport")
        root.set("type", task.report_spec.report_type.value)
        root.set("jurisdiction", task.report_spec.jurisdiction.value)
        root.set("generated", datetime.now().isoformat())

        # Add report metadata
        metadata = ET.SubElement(root, "Metadata")
        ET.SubElement(metadata, "StartTime").text = task.start_time.isoformat()
        ET.SubElement(metadata, "EndTime").text = task.end_time.isoformat()
        ET.SubElement(metadata, "TaskId").text = task.task_id

        # Add data section
        data_section = ET.SubElement(root, "Data")

        if isinstance(report_data, list):
            for i, record in enumerate(report_data):
                record_elem = ET.SubElement(data_section, "Record")
                record_elem.set("index", str(i))

                if isinstance(record, TradeReportRecord):
                    record_dict = asdict(record)
                else:
                    record_dict = record

                for key, value in record_dict.items():
                    elem = ET.SubElement(record_elem, key)
                    elem.text = str(value) if value is not None else ""

        # Write XML to file
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

    async def get_report_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a report generation task."""

        if task_id not in self.active_tasks:
            return None

        task = self.active_tasks[task_id]
        return {
            "task_id": task.task_id,
            "report_type": task.report_spec.report_type.value,
            "jurisdiction": task.report_spec.jurisdiction.value,
            "status": task.status.value,
            "created_at": task.created_at.isoformat(),
            "output_path": task.output_path,
            "error_message": task.error_message,
            "retry_count": task.retry_count,
        }

    async def list_reports(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[ReportStatus] = None,
    ) -> List[Dict[str, Any]]:
        """List generated reports with optional filters."""

        reports = []
        for task in self.active_tasks.values():
            # Apply filters
            if start_date and task.created_at < start_date:
                continue
            if end_date and task.created_at > end_date:
                continue
            if status and task.status != status:
                continue

            reports.append(
                {
                    "task_id": task.task_id,
                    "report_type": task.report_spec.report_type.value,
                    "jurisdiction": task.report_spec.jurisdiction.value,
                    "status": task.status.value,
                    "created_at": task.created_at.isoformat(),
                    "output_path": task.output_path,
                    "priority": task.priority.value,
                }
            )

        # Sort by creation time (newest first)
        reports.sort(key=lambda x: x["created_at"], reverse=True)
        return reports

    async def schedule_periodic_reports(self):
        """Schedule periodic regulatory reports."""

        self.logger.info("Starting periodic report scheduler")

        while True:
            try:
                current_time = datetime.now(timezone.utc)

                # Check for daily reports (run at 6 AM UTC)
                if current_time.hour == 6 and current_time.minute < 15:
                    yesterday = current_time - timedelta(days=1)
                    start_of_day = yesterday.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    end_of_day = yesterday.replace(
                        hour=23, minute=59, second=59, microsecond=999999
                    )

                    # Generate daily reports
                    await self.generate_report(
                        "eu_mifid_transaction_report",
                        start_of_day,
                        end_of_day,
                        priority=ReportPriority.HIGH,
                    )

                # Check for monthly reports (run on 1st day of month)
                if (
                    current_time.day == 1
                    and current_time.hour == 8
                    and current_time.minute < 15
                ):
                    last_month_start = (
                        current_time.replace(day=1) - timedelta(days=1)
                    ).replace(day=1)
                    last_month_end = current_time.replace(day=1) - timedelta(days=1)

                    # Generate monthly reports
                    await self.generate_report(
                        "us_finra_large_trader",
                        last_month_start,
                        last_month_end,
                        priority=ReportPriority.NORMAL,
                    )

                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                self.logger.error(f"Error in periodic report scheduler: {e}")
                await asyncio.sleep(600)  # Wait 10 minutes on error

    async def process_real_time_events(self, event_data: Dict[str, Any]):
        """Process real-time trading events for immediate reporting."""

        if not self.enable_real_time_reporting:
            return

        event_type = event_data.get("type")

        # Check if event requires immediate reporting
        if event_type == "trade_executed":
            trade_value = event_data.get("quantity", 0) * event_data.get("price", 0)

            # US CFTC large notional trade reporting
            if trade_value >= 1000000:  # $1M threshold
                current_time = datetime.now(timezone.utc)
                await self.generate_report(
                    "us_cftc_trade_report",
                    current_time - timedelta(minutes=1),
                    current_time,
                    parameters={"trade_id": event_data.get("trade_id")},
                    priority=ReportPriority.CRITICAL,
                )

        elif event_type == "suspicious_activity_detected":
            # Immediate suspicious activity reporting
            current_time = datetime.now(timezone.utc)
            await self.generate_report(
                "suspicious_activity_report",
                current_time - timedelta(hours=1),
                current_time,
                parameters={"alert_id": event_data.get("alert_id")},
                priority=ReportPriority.CRITICAL,
            )

    async def cleanup_old_reports(self):
        """Clean up old report files based on retention policy."""

        self.logger.info("Starting report cleanup process")

        cutoff_date = datetime.now() - timedelta(days=self.report_retention_days)

        # Clean up completed tasks older than retention period
        tasks_to_remove = []
        for task_id, task in self.active_tasks.items():
            if task.created_at < cutoff_date and task.status in [
                ReportStatus.COMPLETED,
                ReportStatus.FAILED,
            ]:
                tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            task = self.active_tasks[task_id]

            # Remove file if it exists
            if task.output_path and Path(task.output_path).exists():
                Path(task.output_path).unlink()
                self.logger.info(f"Deleted old report file: {task.output_path}")

            del self.active_tasks[task_id]

        self.logger.info(f"Cleaned up {len(tasks_to_remove)} old report tasks")

    async def get_reporting_statistics(self) -> Dict[str, Any]:
        """Get comprehensive reporting engine statistics."""

        # Count tasks by status
        status_counts = {}
        for status in ReportStatus:
            status_counts[status.value] = sum(
                1 for task in self.active_tasks.values() if task.status == status
            )

        # Count reports by type
        type_counts = {}
        for task in self.active_tasks.values():
            report_type = task.report_spec.report_type.value
            type_counts[report_type] = type_counts.get(report_type, 0) + 1

        return {
            "total_reports_generated": self.reports_generated,
            "total_reports_failed": self.reports_failed,
            "total_reports_submitted": self.reports_submitted,
            "active_tasks": len(self.active_tasks),
            "background_tasks_running": len(self._background_tasks),
            "last_report_generation": (
                self.last_report_generation.isoformat()
                if self.last_report_generation
                else None
            ),
            "reports_by_status": status_counts,
            "reports_by_type": type_counts,
            "report_specifications": len(self.report_specifications),
            "submission_queue_size": self.submission_queue.qsize(),
        }

    async def start_background_services(self):
        """Start background services for the reporting engine."""

        self.logger.info("Starting regulatory reporting background services")

        # Start periodic report scheduler
        scheduler_task = asyncio.create_task(self.schedule_periodic_reports())
        self._background_tasks.add(scheduler_task)
        scheduler_task.add_done_callback(self._background_tasks.discard)

        # Start cleanup service (runs daily at 2 AM)
        async def cleanup_scheduler():
            while True:
                try:
                    now = datetime.now()
                    if now.hour == 2 and now.minute < 15:  # Run at 2 AM
                        await self.cleanup_old_reports()
                    await asyncio.sleep(900)  # Check every 15 minutes
                except Exception as e:
                    self.logger.error(f"Cleanup scheduler error: {e}")
                    await asyncio.sleep(3600)  # Wait 1 hour on error

        cleanup_task = asyncio.create_task(cleanup_scheduler())
        self._background_tasks.add(cleanup_task)
        cleanup_task.add_done_callback(self._background_tasks.discard)

        self.logger.info("All background services started successfully")

    async def stop_background_services(self):
        """Stop all background services."""

        self.logger.info("Stopping regulatory reporting background services")

        # Cancel all background tasks
        for task in self._background_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()
        self.logger.info("All background services stopped")


# Global reporting engine instance
regulatory_reporting_engine = RegulatoryReportingEngine()


async def get_regulatory_reporting_engine() -> RegulatoryReportingEngine:
    """Get the global regulatory reporting engine instance."""
    return regulatory_reporting_engine
