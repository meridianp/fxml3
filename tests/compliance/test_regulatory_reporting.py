"""
Comprehensive tests for regulatory reporting engine and API endpoints.

Tests cover:
- Report generation for different types and jurisdictions
- Real-time event processing
- Background service management
- API endpoint functionality
- Error handling and edge cases
- Performance and concurrency
"""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.api.auth.models import Role, User
from fxml4.api.routers.regulatory_reporting import router
from fxml4.compliance.reporting.regulatory_engine import (
    RegulatoryJurisdiction,
    RegulatoryReportingEngine,
    ReportFormat,
    ReportGenerationTask,
    ReportPriority,
    ReportSpecification,
    ReportStatus,
    ReportType,
    TradeReportRecord,
    regulatory_reporting_engine,
)
from fxml4.trading.models import Position, Trade


# Test fixtures
@pytest.fixture
def temp_report_dir():
    """Create temporary directory for test reports."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {
        "compliance.reporting.real_time_enabled": True,
        "compliance.reporting.storage_path": "./test_reports",
        "compliance.reporting.max_concurrent": 5,
        "compliance.reporting.retention_days": 7,
    }


@pytest.fixture
def reporting_engine(temp_report_dir, mock_config):
    """Create test regulatory reporting engine."""
    with patch(
        "fxml4.compliance.reporting.regulatory_engine.get_config"
    ) as mock_get_config:
        mock_get_config.return_value = mock_config

        engine = RegulatoryReportingEngine()
        engine.report_storage_path = temp_report_dir

        return engine


@pytest.fixture
def sample_trades():
    """Create sample trade data for testing."""
    base_time = datetime.now(timezone.utc)

    trades = []
    for i in range(10):
        trade = Mock(spec=Trade)
        trade.id = f"trade_{i:03d}"
        trade.timestamp = base_time + timedelta(minutes=i)
        trade.symbol = "GBPUSD"
        trade.side = "buy" if i % 2 == 0 else "sell"
        trade.quantity = 100000.0 + (i * 10000)
        trade.price = 1.3000 + (i * 0.001)
        trade.counterparty = "BROKER_A"
        trade.user = Mock()
        trade.user.username = f"trader_{i % 3}"
        trade.account_id = f"account_{i % 2}"
        trade.execution_venue = "FXALL"
        trade.order_id = f"order_{i:03d}"
        trade.settlement_date = trade.timestamp + timedelta(days=2)
        trade.commission = 10.0
        trades.append(trade)

    return trades


@pytest.fixture
def mock_db_session(sample_trades):
    """Mock database session with sample data."""

    async def mock_execute(query):
        # Mock result for trade queries
        result = Mock()
        result.scalars.return_value.all.return_value = sample_trades
        return result

    session = AsyncMock(spec=AsyncSession)
    session.execute = mock_execute

    return session


@pytest.fixture
def admin_user():
    """Create admin user for testing."""
    user = Mock(spec=User)
    user.id = 1
    user.username = "admin_test"
    user.email = "admin@test.com"
    user.is_active = True

    # Mock admin role
    admin_role = Mock(spec=Role)
    admin_role.name = "admin"
    admin_role.permissions = '["*"]'
    user.roles = [admin_role]

    return user


@pytest.mark.compliance
@pytest.mark.asyncio
class TestRegulatoryReportingEngine:
    """Test suite for RegulatoryReportingEngine core functionality."""

    async def test_engine_initialization(self, reporting_engine):
        """Test regulatory reporting engine initialization."""

        assert reporting_engine is not None
        assert len(reporting_engine.report_specifications) > 0
        assert reporting_engine.enable_real_time_reporting is True
        assert reporting_engine.reports_generated == 0
        assert reporting_engine.reports_failed == 0

    async def test_default_report_specifications(self, reporting_engine):
        """Test default report specifications are properly loaded."""

        specs = reporting_engine.report_specifications

        # Check US CFTC trade reporting specification
        assert "us_cftc_trade_report" in specs
        cftc_spec = specs["us_cftc_trade_report"]
        assert cftc_spec.report_type == ReportType.TRADE_REPORTING
        assert cftc_spec.jurisdiction == RegulatoryJurisdiction.US_CFTC
        assert cftc_spec.format == ReportFormat.XML
        assert cftc_spec.is_mandatory is True
        assert cftc_spec.deadline_minutes == 15

        # Check EU MiFID specification
        assert "eu_mifid_transaction_report" in specs
        mifid_spec = specs["eu_mifid_transaction_report"]
        assert mifid_spec.jurisdiction == RegulatoryJurisdiction.EU_MIFID
        assert mifid_spec.frequency == "daily"

        # Check suspicious activity reporting
        assert "suspicious_activity_report" in specs
        sar_spec = specs["suspicious_activity_report"]
        assert sar_spec.report_type == ReportType.SUSPICIOUS_ACTIVITY
        assert sar_spec.frequency == "real_time"

    async def test_generate_trade_report(self, reporting_engine, mock_db_session):
        """Test trade report generation."""

        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        end_time = datetime.now(timezone.utc)

        with patch(
            "fxml4.compliance.reporting.regulatory_engine.get_db"
        ) as mock_get_db:
            mock_get_db.return_value.__aenter__.return_value = mock_db_session

            task_id = await reporting_engine.generate_report(
                "us_cftc_trade_report",
                start_time,
                end_time,
                priority=ReportPriority.HIGH,
            )

        assert task_id is not None
        assert task_id in reporting_engine.active_tasks

        task = reporting_engine.active_tasks[task_id]
        assert task.report_spec.report_type == ReportType.TRADE_REPORTING
        assert task.priority == ReportPriority.HIGH
        assert task.start_time == start_time
        assert task.end_time == end_time

    async def test_generate_report_invalid_type(self, reporting_engine):
        """Test error handling for invalid report type."""

        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        end_time = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="Unknown report type"):
            await reporting_engine.generate_report(
                "invalid_report_type", start_time, end_time
            )

    async def test_trade_report_data_generation(self, reporting_engine, sample_trades):
        """Test generation of trade report data structures."""

        # Create a mock task
        task = ReportGenerationTask(
            task_id="test_task",
            report_spec=reporting_engine.report_specifications["us_cftc_trade_report"],
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            end_time=datetime.now(timezone.utc),
            priority=ReportPriority.NORMAL,
            status=ReportStatus.GENERATING,
            created_at=datetime.now(timezone.utc),
            parameters={},
        )

        with patch(
            "fxml4.compliance.reporting.regulatory_engine.get_db"
        ) as mock_get_db:
            # Mock database session
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = sample_trades
            mock_session.execute.return_value = mock_result
            mock_get_db.return_value.__aenter__.return_value = mock_session

            # Generate trade report data
            report_data = await reporting_engine._generate_trade_report(task)

        assert isinstance(report_data, list)
        assert len(report_data) == len(sample_trades)
        assert all(isinstance(record, TradeReportRecord) for record in report_data)

        # Check first record
        first_record = report_data[0]
        assert first_record.trade_id == "trade_000"
        assert first_record.symbol == "GBPUSD"
        assert first_record.unique_trade_identifier.startswith("FXML4_")

    async def test_suspicious_activity_report_generation(self, reporting_engine):
        """Test suspicious activity report generation."""

        task = ReportGenerationTask(
            task_id="sar_test",
            report_spec=reporting_engine.report_specifications[
                "suspicious_activity_report"
            ],
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            end_time=datetime.now(timezone.utc),
            priority=ReportPriority.CRITICAL,
            status=ReportStatus.GENERATING,
            created_at=datetime.now(timezone.utc),
            parameters={},
        )

        # Mock surveillance engine
        mock_alerts = [
            Mock(
                alert_id="alert_001",
                user_id="trader_1",
                alert_type=Mock(value="wash_trading"),
                created_at=datetime.now(timezone.utc),
                related_trades=[],
                risk_score=0.85,
                description="Potential wash trading pattern",
                severity=Mock(value="high"),
                status="open",
            )
        ]

        with patch(
            "fxml4.compliance.reporting.regulatory_engine.TradeSurveillanceEngine"
        ) as mock_surveillance:
            mock_instance = Mock()
            mock_instance.get_alerts_by_time_range.return_value = mock_alerts
            mock_surveillance.return_value = mock_instance

            report_data = await reporting_engine._generate_suspicious_activity_report(
                task
            )

        assert isinstance(report_data, list)
        assert len(report_data) == 1

        alert_record = report_data[0]
        assert alert_record["alert_id"] == "alert_001"
        assert alert_record["risk_score"] == 0.85
        assert alert_record["pattern_type"] == "wash_trading"

    async def test_large_trader_report_generation(self, reporting_engine):
        """Test large trader report generation."""

        task = ReportGenerationTask(
            task_id="large_trader_test",
            report_spec=reporting_engine.report_specifications["us_finra_large_trader"],
            start_time=datetime.now(timezone.utc) - timedelta(days=30),
            end_time=datetime.now(timezone.utc),
            priority=ReportPriority.NORMAL,
            status=ReportStatus.GENERATING,
            created_at=datetime.now(timezone.utc),
            parameters={},
        )

        # Mock database query results
        mock_results = [
            Mock(
                trader_id="trader_001",
                account_id="account_001",
                monthly_volume=75000000.0,
                average_daily_volume=2500000.0,
                largest_single_trade=5000000.0,
                trading_days_active=20,
            ),
            Mock(
                trader_id="trader_002",
                account_id="account_002",
                monthly_volume=120000000.0,
                average_daily_volume=4000000.0,
                largest_single_trade=8000000.0,
                trading_days_active=25,
            ),
        ]

        with patch(
            "fxml4.compliance.reporting.regulatory_engine.get_db"
        ) as mock_get_db:
            mock_session = AsyncMock()
            mock_session.execute.return_value.__iter__ = lambda self: iter(mock_results)
            mock_get_db.return_value.__aenter__.return_value = mock_session

            report_data = await reporting_engine._generate_large_trader_report(task)

        assert isinstance(report_data, list)
        assert len(report_data) == 2

        trader_record = report_data[0]
        assert trader_record["trader_id"] == "trader_001"
        assert trader_record["monthly_volume"] == 75000000.0
        assert trader_record["trading_days_active"] == 20

    async def test_daily_summary_report_generation(self, reporting_engine):
        """Test daily summary report generation."""

        task = ReportGenerationTask(
            task_id="daily_summary_test",
            report_spec=ReportSpecification(
                report_type=ReportType.DAILY_SUMMARY,
                jurisdiction=RegulatoryJurisdiction.US_FINRA,
                format=ReportFormat.JSON,
                frequency="daily",
                fields=[],
                filters={},
                deadline_minutes=1440,
                is_mandatory=True,
            ),
            start_time=datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
            end_time=datetime.now(timezone.utc).replace(
                hour=23, minute=59, second=59, microsecond=999999
            ),
            priority=ReportPriority.NORMAL,
            status=ReportStatus.GENERATING,
            created_at=datetime.now(timezone.utc),
            parameters={},
        )

        # Mock summary query result
        summary_result = Mock(
            total_trades=150,
            total_volume=25000000.0,
            average_trade_size=166666.67,
            symbols_traded=5,
            active_traders=8,
            first_trade_time=datetime.now(timezone.utc).replace(hour=9, minute=0),
            last_trade_time=datetime.now(timezone.utc).replace(hour=17, minute=30),
        )

        # Mock symbol breakdown
        symbol_results = [
            Mock(symbol="GBPUSD", trade_count=75, volume=15000000.0),
            Mock(symbol="EURUSD", trade_count=50, volume=8000000.0),
            Mock(symbol="USDJPY", trade_count=25, volume=2000000.0),
        ]

        with patch(
            "fxml4.compliance.reporting.regulatory_engine.get_db"
        ) as mock_get_db:
            mock_session = AsyncMock()

            # Mock first execute call (summary)
            mock_session.execute.side_effect = [
                Mock(fetchone=lambda: summary_result),
                Mock(__iter__=lambda self: iter(symbol_results)),
            ]

            mock_get_db.return_value.__aenter__.return_value = mock_session

            report_data = await reporting_engine._generate_daily_summary_report(task)

        assert isinstance(report_data, dict)
        assert "summary" in report_data
        assert "symbol_breakdown" in report_data

        summary = report_data["summary"]
        assert summary["total_trades"] == 150
        assert summary["total_volume"] == 25000000.0
        assert summary["active_traders"] == 8

        symbols = report_data["symbol_breakdown"]
        assert len(symbols) == 3
        assert symbols[0]["symbol"] == "GBPUSD"
        assert symbols[0]["trade_count"] == 75

    async def test_report_formatting_csv(self, reporting_engine, temp_report_dir):
        """Test CSV report formatting and file output."""

        # Sample trade report data
        report_data = [
            TradeReportRecord(
                trade_id="trade_001",
                timestamp=datetime.now(timezone.utc),
                symbol="GBPUSD",
                side="buy",
                quantity=100000.0,
                price=1.3000,
                counterparty="BROKER",
                trader_id="trader_1",
                account_id="account_1",
                execution_venue="FXALL",
                order_id="order_001",
                settlement_date=datetime.now(timezone.utc) + timedelta(days=2),
                trade_type="SPOT",
                currency="USD",
                commission=10.0,
                regulatory_status="NORMAL",
                unique_trade_identifier="FXML4_trade_001_123456789",
            )
        ]

        task = ReportGenerationTask(
            task_id="csv_test",
            report_spec=ReportSpecification(
                report_type=ReportType.TRADE_REPORTING,
                jurisdiction=RegulatoryJurisdiction.US_CFTC,
                format=ReportFormat.CSV,
                frequency="daily",
                fields=[],
                filters={},
                deadline_minutes=1440,
                is_mandatory=True,
            ),
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            end_time=datetime.now(timezone.utc),
            priority=ReportPriority.NORMAL,
            status=ReportStatus.GENERATING,
            created_at=datetime.now(timezone.utc),
            parameters={},
        )

        reporting_engine.report_storage_path = temp_report_dir

        output_path = await reporting_engine._format_and_save_report(task, report_data)

        assert output_path.exists()
        assert output_path.suffix == ".csv"

        # Verify CSV content
        with open(output_path, "r") as f:
            content = f.read()
            assert "trade_id,timestamp,symbol" in content
            assert "trade_001" in content
            assert "GBPUSD" in content

    async def test_report_formatting_json(self, reporting_engine, temp_report_dir):
        """Test JSON report formatting."""

        report_data = [
            {
                "alert_id": "alert_001",
                "trader_id": "trader_1",
                "pattern_type": "wash_trading",
                "risk_score": 0.85,
            }
        ]

        task = ReportGenerationTask(
            task_id="json_test",
            report_spec=ReportSpecification(
                report_type=ReportType.SUSPICIOUS_ACTIVITY,
                jurisdiction=RegulatoryJurisdiction.US_FINRA,
                format=ReportFormat.JSON,
                frequency="real_time",
                fields=[],
                filters={},
                deadline_minutes=30,
                is_mandatory=True,
            ),
            start_time=datetime.now(timezone.utc) - timedelta(minutes=30),
            end_time=datetime.now(timezone.utc),
            priority=ReportPriority.CRITICAL,
            status=ReportStatus.GENERATING,
            created_at=datetime.now(timezone.utc),
            parameters={},
        )

        reporting_engine.report_storage_path = temp_report_dir

        output_path = await reporting_engine._format_and_save_report(task, report_data)

        assert output_path.exists()
        assert output_path.suffix == ".json"

        # Verify JSON content
        with open(output_path, "r") as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]["alert_id"] == "alert_001"
            assert data[0]["risk_score"] == 0.85

    async def test_report_formatting_xml(self, reporting_engine, temp_report_dir):
        """Test XML report formatting."""

        import xml.etree.ElementTree as ET

        report_data = [
            TradeReportRecord(
                trade_id="trade_xml_001",
                timestamp=datetime.now(timezone.utc),
                symbol="EURUSD",
                side="sell",
                quantity=50000.0,
                price=1.1000,
                counterparty="BANK_A",
                trader_id="trader_xml",
                account_id="account_xml",
                execution_venue="EBS",
                order_id="order_xml_001",
                settlement_date=datetime.now(timezone.utc) + timedelta(days=2),
                trade_type="SPOT",
                currency="USD",
                commission=5.0,
                regulatory_status="NORMAL",
                unique_trade_identifier="FXML4_trade_xml_001_987654321",
            )
        ]

        task = ReportGenerationTask(
            task_id="xml_test",
            report_spec=ReportSpecification(
                report_type=ReportType.TRADE_REPORTING,
                jurisdiction=RegulatoryJurisdiction.EU_MIFID,
                format=ReportFormat.XML,
                frequency="daily",
                fields=[],
                filters={},
                deadline_minutes=1440,
                is_mandatory=True,
            ),
            start_time=datetime.now(timezone.utc) - timedelta(hours=24),
            end_time=datetime.now(timezone.utc),
            priority=ReportPriority.NORMAL,
            status=ReportStatus.GENERATING,
            created_at=datetime.now(timezone.utc),
            parameters={},
        )

        reporting_engine.report_storage_path = temp_report_dir

        output_path = await reporting_engine._format_and_save_report(task, report_data)

        assert output_path.exists()
        assert output_path.suffix == ".xml"

        # Parse and verify XML content
        tree = ET.parse(output_path)
        root = tree.getroot()

        assert root.tag == "RegulatoryReport"
        assert root.get("type") == "trade_reporting"
        assert root.get("jurisdiction") == "eu_mifid"

        # Check data section
        data_section = root.find("Data")
        assert data_section is not None

        records = data_section.findall("Record")
        assert len(records) == 1

        trade_id_elem = records[0].find("trade_id")
        assert trade_id_elem.text == "trade_xml_001"

    async def test_real_time_event_processing(self, reporting_engine):
        """Test real-time event processing for immediate reporting."""

        # Mock large trade event
        large_trade_event = {
            "type": "trade_executed",
            "trade_id": "large_trade_001",
            "quantity": 10000000,
            "price": 1.3000,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with patch.object(reporting_engine, "generate_report") as mock_generate:
            mock_generate.return_value = "task_large_trade_001"

            await reporting_engine.process_real_time_events(large_trade_event)

            # Verify report generation was triggered
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert args[0] == "us_cftc_trade_report"
            assert kwargs["priority"] == ReportPriority.CRITICAL

    async def test_suspicious_activity_event_processing(self, reporting_engine):
        """Test suspicious activity event processing."""

        suspicious_event = {
            "type": "suspicious_activity_detected",
            "alert_id": "suspicious_001",
            "risk_score": 0.95,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with patch.object(reporting_engine, "generate_report") as mock_generate:
            mock_generate.return_value = "task_suspicious_001"

            await reporting_engine.process_real_time_events(suspicious_event)

            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert args[0] == "suspicious_activity_report"
            assert kwargs["priority"] == ReportPriority.CRITICAL

    async def test_report_task_retry_logic(self, reporting_engine):
        """Test report generation retry logic on failure."""

        task = ReportGenerationTask(
            task_id="retry_test",
            report_spec=reporting_engine.report_specifications["us_cftc_trade_report"],
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            end_time=datetime.now(timezone.utc),
            priority=ReportPriority.NORMAL,
            status=ReportStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            parameters={},
            max_retries=2,
        )

        # Mock _generate_trade_report to fail initially
        with patch.object(reporting_engine, "_generate_trade_report") as mock_generate:
            mock_generate.side_effect = [
                Exception("Database error"),  # First attempt fails
                Exception("Still failing"),  # Second attempt fails
                [],  # Third attempt succeeds
            ]

            # Mock format_and_save_report
            with patch.object(
                reporting_engine, "_format_and_save_report"
            ) as mock_format:
                mock_format.return_value = Path("test_report.csv")

                # Process task with retries
                await reporting_engine._process_report_task(task)

        # Task should eventually succeed after retries
        assert task.status == ReportStatus.COMPLETED
        assert task.retry_count == 2
        assert task.output_path == "test_report.csv"
        assert reporting_engine.reports_generated == 1

    async def test_get_report_status(self, reporting_engine):
        """Test report status retrieval."""

        # Create a test task
        task = ReportGenerationTask(
            task_id="status_test_001",
            report_spec=reporting_engine.report_specifications["us_cftc_trade_report"],
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            end_time=datetime.now(timezone.utc),
            priority=ReportPriority.HIGH,
            status=ReportStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            parameters={},
            output_path="/path/to/report.csv",
        )

        reporting_engine.active_tasks[task.task_id] = task

        status_info = await reporting_engine.get_report_status("status_test_001")

        assert status_info is not None
        assert status_info["task_id"] == "status_test_001"
        assert status_info["status"] == "completed"
        assert status_info["output_path"] == "/path/to/report.csv"
        assert status_info["report_type"] == "trade_reporting"

    async def test_list_reports_with_filters(self, reporting_engine):
        """Test report listing with various filters."""

        # Create test tasks with different properties
        base_time = datetime.now(timezone.utc)

        tasks = [
            ReportGenerationTask(
                task_id="list_test_001",
                report_spec=reporting_engine.report_specifications[
                    "us_cftc_trade_report"
                ],
                start_time=base_time - timedelta(hours=2),
                end_time=base_time - timedelta(hours=1),
                priority=ReportPriority.HIGH,
                status=ReportStatus.COMPLETED,
                created_at=base_time - timedelta(hours=1),
                parameters={},
            ),
            ReportGenerationTask(
                task_id="list_test_002",
                report_spec=reporting_engine.report_specifications[
                    "eu_mifid_transaction_report"
                ],
                start_time=base_time - timedelta(hours=1),
                end_time=base_time,
                priority=ReportPriority.NORMAL,
                status=ReportStatus.FAILED,
                created_at=base_time - timedelta(minutes=30),
                parameters={},
            ),
            ReportGenerationTask(
                task_id="list_test_003",
                report_spec=reporting_engine.report_specifications[
                    "suspicious_activity_report"
                ],
                start_time=base_time - timedelta(minutes=30),
                end_time=base_time,
                priority=ReportPriority.CRITICAL,
                status=ReportStatus.GENERATING,
                created_at=base_time - timedelta(minutes=15),
                parameters={},
            ),
        ]

        # Add tasks to engine
        for task in tasks:
            reporting_engine.active_tasks[task.task_id] = task

        # Test listing all reports
        all_reports = await reporting_engine.list_reports()
        assert len(all_reports) == 3

        # Test filtering by status
        completed_reports = await reporting_engine.list_reports(
            status=ReportStatus.COMPLETED
        )
        assert len(completed_reports) == 1
        assert completed_reports[0]["task_id"] == "list_test_001"

        # Test filtering by date range
        recent_reports = await reporting_engine.list_reports(
            start_date=base_time - timedelta(minutes=45), end_date=base_time
        )
        assert len(recent_reports) == 2  # Should exclude the first task

    async def test_reporting_statistics(self, reporting_engine):
        """Test reporting statistics collection."""

        # Set some test metrics
        reporting_engine.reports_generated = 15
        reporting_engine.reports_failed = 2
        reporting_engine.reports_submitted = 12
        reporting_engine.last_report_generation = datetime.now(timezone.utc)

        # Add some test tasks
        base_time = datetime.now(timezone.utc)
        test_tasks = {
            "stats_test_001": ReportGenerationTask(
                task_id="stats_test_001",
                report_spec=reporting_engine.report_specifications[
                    "us_cftc_trade_report"
                ],
                start_time=base_time - timedelta(hours=1),
                end_time=base_time,
                priority=ReportPriority.HIGH,
                status=ReportStatus.COMPLETED,
                created_at=base_time,
                parameters={},
            ),
            "stats_test_002": ReportGenerationTask(
                task_id="stats_test_002",
                report_spec=reporting_engine.report_specifications[
                    "suspicious_activity_report"
                ],
                start_time=base_time - timedelta(minutes=30),
                end_time=base_time,
                priority=ReportPriority.CRITICAL,
                status=ReportStatus.GENERATING,
                created_at=base_time,
                parameters={},
            ),
        }

        reporting_engine.active_tasks.update(test_tasks)

        stats = await reporting_engine.get_reporting_statistics()

        assert stats["total_reports_generated"] == 15
        assert stats["total_reports_failed"] == 2
        assert stats["total_reports_submitted"] == 12
        assert stats["active_tasks"] == 2
        assert stats["reports_by_status"]["completed"] == 1
        assert stats["reports_by_status"]["generating"] == 1
        assert stats["reports_by_type"]["trade_reporting"] == 1
        assert stats["reports_by_type"]["suspicious_activity"] == 1
        assert stats["last_report_generation"] is not None


@pytest.mark.compliance
@pytest.mark.api
class TestRegulatoryReportingAPI:
    """Test suite for regulatory reporting API endpoints."""

    def setup_method(self):
        """Set up test client and mock dependencies."""
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    @patch("fxml4.api.routers.regulatory_reporting.get_current_user")
    @patch("fxml4.api.routers.regulatory_reporting.regulatory_reporting_engine")
    async def test_generate_report_endpoint(
        self, mock_engine, mock_get_user, admin_user
    ):
        """Test report generation API endpoint."""

        mock_get_user.return_value = admin_user
        mock_engine.generate_report.return_value = "test_task_001"

        # Mock permission checker
        with patch(
            "fxml4.api.routers.regulatory_reporting.require_permission"
        ) as mock_require:
            mock_require.return_value = lambda f: f  # Pass-through decorator

            request_data = {
                "report_type": "us_cftc_trade_report",
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T23:59:59Z",
                "priority": "high",
                "parameters": {"test": "value"},
            }

            response = self.client.post(
                "/regulatory-reporting/generate", json=request_data
            )

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["task_id"] == "test_task_001"
        assert "estimated_completion_time" in data
        assert data["message"] == "Report generation scheduled successfully"

    @patch("fxml4.api.routers.regulatory_reporting.get_current_user")
    @patch("fxml4.api.routers.regulatory_reporting.regulatory_reporting_engine")
    async def test_get_report_status_endpoint(
        self, mock_engine, mock_get_user, admin_user
    ):
        """Test report status API endpoint."""

        mock_get_user.return_value = admin_user
        mock_engine.get_report_status.return_value = {
            "task_id": "test_task_001",
            "report_type": "trade_reporting",
            "jurisdiction": "us_cftc",
            "status": "completed",
            "created_at": "2024-01-01T12:00:00Z",
            "output_path": "/reports/test_report.csv",
        }

        with patch(
            "fxml4.api.routers.regulatory_reporting.require_permission"
        ) as mock_require:
            mock_require.return_value = lambda f: f

            response = self.client.get("/regulatory-reporting/status/test_task_001")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["task_id"] == "test_task_001"
        assert data["status"] == "completed"
        assert data["output_path"] == "/reports/test_report.csv"

    @patch("fxml4.api.routers.regulatory_reporting.get_current_user")
    @patch("fxml4.api.routers.regulatory_reporting.regulatory_reporting_engine")
    async def test_list_reports_endpoint(self, mock_engine, mock_get_user, admin_user):
        """Test report listing API endpoint."""

        mock_get_user.return_value = admin_user
        mock_engine.list_reports.return_value = [
            {
                "task_id": "test_task_001",
                "report_type": "trade_reporting",
                "jurisdiction": "us_cftc",
                "status": "completed",
                "created_at": "2024-01-01T12:00:00Z",
                "priority": "high",
            },
            {
                "task_id": "test_task_002",
                "report_type": "suspicious_activity",
                "jurisdiction": "us_finra",
                "status": "generating",
                "created_at": "2024-01-01T13:00:00Z",
                "priority": "critical",
            },
        ]

        with patch(
            "fxml4.api.routers.regulatory_reporting.require_permission"
        ) as mock_require:
            mock_require.return_value = lambda f: f

            response = self.client.get("/regulatory-reporting/list?page=1&page_size=10")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["reports"]) == 2
        assert data["total_count"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 10

    @patch("fxml4.api.routers.regulatory_reporting.check_risk_manager_access")
    @patch("fxml4.api.routers.regulatory_reporting.regulatory_reporting_engine")
    async def test_statistics_endpoint(
        self, mock_engine, mock_check_access, admin_user
    ):
        """Test reporting statistics API endpoint."""

        mock_check_access.return_value = admin_user
        mock_engine.get_reporting_statistics.return_value = {
            "total_reports_generated": 25,
            "total_reports_failed": 3,
            "total_reports_submitted": 20,
            "active_tasks": 5,
            "background_tasks_running": 2,
            "last_report_generation": "2024-01-01T15:30:00Z",
            "reports_by_status": {"completed": 20, "generating": 3, "failed": 2},
            "reports_by_type": {
                "trade_reporting": 15,
                "suspicious_activity": 5,
                "large_trader": 5,
            },
            "report_specifications": 4,
            "submission_queue_size": 2,
        }

        with patch(
            "fxml4.api.routers.regulatory_reporting.require_permission"
        ) as mock_require:
            mock_require.return_value = lambda f: f

            response = self.client.get("/regulatory-reporting/statistics")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["total_reports_generated"] == 25
        assert data["total_reports_failed"] == 3
        assert data["active_tasks"] == 5
        assert len(data["reports_by_status"]) == 3
        assert len(data["reports_by_type"]) == 3

    @patch("fxml4.api.routers.regulatory_reporting.get_current_user")
    @patch("fxml4.api.routers.regulatory_reporting.regulatory_reporting_engine")
    async def test_available_report_types_endpoint(
        self, mock_engine, mock_get_user, admin_user
    ):
        """Test available report types API endpoint."""

        mock_get_user.return_value = admin_user
        mock_engine.report_specifications = {
            "us_cftc_trade_report": Mock(
                report_type=Mock(value="trade_reporting"),
                jurisdiction=Mock(value="us_cftc"),
                format=Mock(value="xml"),
                frequency="real_time",
                is_mandatory=True,
                deadline_minutes=15,
            ),
            "eu_mifid_transaction_report": Mock(
                report_type=Mock(value="transaction_reporting"),
                jurisdiction=Mock(value="eu_mifid"),
                format=Mock(value="regulatory_xml"),
                frequency="daily",
                is_mandatory=True,
                deadline_minutes=1440,
            ),
        }

        with patch(
            "fxml4.api.routers.regulatory_reporting.require_permission"
        ) as mock_require:
            mock_require.return_value = lambda f: f

            response = self.client.get("/regulatory-reporting/types")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "available_types" in data
        assert len(data["available_types"]) == 2
        assert data["total_count"] == 2

        # Check first report type
        first_type = data["available_types"][0]
        assert first_type["name"] == "us_cftc_trade_report"
        assert first_type["type"] == "trade_reporting"
        assert first_type["jurisdiction"] == "us_cftc"
        assert first_type["is_mandatory"] is True

    async def test_health_check_endpoint(self):
        """Test regulatory reporting engine health check."""

        with patch(
            "fxml4.api.routers.regulatory_reporting.regulatory_reporting_engine"
        ) as mock_engine:
            mock_engine.get_reporting_statistics.return_value = {
                "active_tasks": 3,
                "background_tasks_running": 2,
                "submission_queue_size": 5,
                "last_report_generation": "2024-01-01T15:30:00Z",
            }

            response = self.client.get("/regulatory-reporting/health")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["status"] == "healthy"
        assert data["active_tasks"] == 3
        assert data["background_tasks"] == 2
        assert data["queue_size"] == 5


@pytest.mark.compliance
@pytest.mark.performance
@pytest.mark.asyncio
class TestRegulatoryReportingPerformance:
    """Performance and load tests for regulatory reporting system."""

    async def test_concurrent_report_generation(self, reporting_engine):
        """Test concurrent report generation performance."""

        # Create multiple concurrent report generation tasks
        tasks = []
        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        end_time = datetime.now(timezone.utc)

        for i in range(5):
            task = asyncio.create_task(
                reporting_engine.generate_report(
                    "us_cftc_trade_report",
                    start_time,
                    end_time,
                    priority=ReportPriority.NORMAL,
                )
            )
            tasks.append(task)

        # Execute all tasks concurrently
        start_perf = asyncio.get_event_loop().time()
        task_ids = await asyncio.gather(*tasks)
        end_perf = asyncio.get_event_loop().time()

        # Verify all reports were scheduled
        assert len(task_ids) == 5
        assert all(task_id in reporting_engine.active_tasks for task_id in task_ids)

        # Performance assertion (should complete in under 1 second)
        execution_time = end_perf - start_perf
        assert execution_time < 1.0

    async def test_large_dataset_report_generation(self, reporting_engine):
        """Test report generation with large datasets."""

        # Create a large number of mock trades
        large_trade_dataset = []
        for i in range(1000):  # Simulate 1000 trades
            trade = Mock(spec=Trade)
            trade.id = f"large_trade_{i:04d}"
            trade.timestamp = datetime.now(timezone.utc) + timedelta(seconds=i)
            trade.symbol = "GBPUSD"
            trade.side = "buy" if i % 2 == 0 else "sell"
            trade.quantity = 100000.0
            trade.price = 1.3000 + (i * 0.0001)
            trade.user = Mock()
            trade.user.username = f"trader_{i % 10}"
            trade.account_id = f"account_{i % 5}"
            trade.execution_venue = "BROKER"
            trade.order_id = f"order_{i:04d}"
            trade.settlement_date = trade.timestamp + timedelta(days=2)
            trade.commission = 10.0
            large_trade_dataset.append(trade)

        # Mock database session with large dataset
        with patch(
            "fxml4.compliance.reporting.regulatory_engine.get_db"
        ) as mock_get_db:
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = large_trade_dataset
            mock_session.execute.return_value = mock_result
            mock_get_db.return_value.__aenter__.return_value = mock_session

            # Time the report generation
            start_time = datetime.now(timezone.utc) - timedelta(hours=1)
            end_time = datetime.now(timezone.utc)

            start_perf = asyncio.get_event_loop().time()
            task_id = await reporting_engine.generate_report(
                "us_cftc_trade_report",
                start_time,
                end_time,
                priority=ReportPriority.HIGH,
            )

            # Wait for task to complete (with timeout)
            timeout = 30.0  # 30 second timeout
            elapsed = 0.0
            while elapsed < timeout:
                task = reporting_engine.active_tasks.get(task_id)
                if task and task.status in [
                    ReportStatus.COMPLETED,
                    ReportStatus.FAILED,
                ]:
                    break
                await asyncio.sleep(0.1)
                elapsed += 0.1

            end_perf = asyncio.get_event_loop().time()

        # Verify task completed successfully
        task = reporting_engine.active_tasks[task_id]
        assert task.status in [
            ReportStatus.COMPLETED,
            ReportStatus.GENERATING,
        ]  # Allow for async completion

        # Performance assertion (should complete within reasonable time)
        execution_time = end_perf - start_perf
        assert execution_time < 30.0  # Should complete within 30 seconds


@pytest.mark.compliance
@pytest.mark.integration
@pytest.mark.asyncio
class TestRegulatoryReportingIntegration:
    """Integration tests for regulatory reporting system."""

    async def test_end_to_end_report_workflow(
        self, reporting_engine, sample_trades, temp_report_dir
    ):
        """Test complete end-to-end report generation workflow."""

        # Setup
        reporting_engine.report_storage_path = temp_report_dir

        # Mock database integration
        with patch(
            "fxml4.compliance.reporting.regulatory_engine.get_db"
        ) as mock_get_db:
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = sample_trades
            mock_session.execute.return_value = mock_result
            mock_get_db.return_value.__aenter__.return_value = mock_session

            # Generate report
            start_time = datetime.now(timezone.utc) - timedelta(hours=1)
            end_time = datetime.now(timezone.utc)

            task_id = await reporting_engine.generate_report(
                "us_cftc_trade_report",
                start_time,
                end_time,
                priority=ReportPriority.HIGH,
            )

            # Wait for completion
            timeout = 10.0
            elapsed = 0.0
            while elapsed < timeout:
                status_info = await reporting_engine.get_report_status(task_id)
                if status_info["status"] in ["completed", "failed"]:
                    break
                await asyncio.sleep(0.1)
                elapsed += 0.1

            # Verify completion
            final_status = await reporting_engine.get_report_status(task_id)
            assert final_status["status"] == "completed"
            assert final_status["output_path"] is not None

            # Verify file was created
            output_file = Path(final_status["output_path"])
            assert output_file.exists()
            assert output_file.stat().st_size > 0

    async def test_surveillance_integration(self, reporting_engine):
        """Test integration with surveillance system for suspicious activity reporting."""

        # Mock surveillance engine alerts
        mock_alerts = [
            Mock(
                alert_id="integration_alert_001",
                user_id="suspicious_trader",
                alert_type=Mock(value="layering"),
                created_at=datetime.now(timezone.utc),
                related_trades=["trade_001", "trade_002"],
                risk_score=0.92,
                description="Potential layering activity detected",
                severity=Mock(value="high"),
                status="open",
            )
        ]

        with patch(
            "fxml4.compliance.reporting.regulatory_engine.TradeSurveillanceEngine"
        ) as mock_surveillance:
            mock_instance = Mock()
            mock_instance.get_alerts_by_time_range.return_value = mock_alerts
            mock_surveillance.return_value = mock_instance

            # Test real-time event processing
            suspicious_event = {
                "type": "suspicious_activity_detected",
                "alert_id": "integration_alert_001",
                "risk_score": 0.92,
            }

            # Process event - should trigger report generation
            await reporting_engine.process_real_time_events(suspicious_event)

            # Verify report was scheduled
            suspicious_tasks = [
                task
                for task in reporting_engine.active_tasks.values()
                if task.report_spec.report_type == ReportType.SUSPICIOUS_ACTIVITY
            ]

            assert len(suspicious_tasks) == 1
            assert suspicious_tasks[0].priority == ReportPriority.CRITICAL

    async def test_multi_jurisdiction_reporting(self, reporting_engine, sample_trades):
        """Test reporting for multiple regulatory jurisdictions."""

        # Mock database for trade data
        with patch(
            "fxml4.compliance.reporting.regulatory_engine.get_db"
        ) as mock_get_db:
            mock_session = AsyncMock()
            mock_result = Mock()
            mock_result.scalars.return_value.all.return_value = sample_trades
            mock_session.execute.return_value = mock_result
            mock_get_db.return_value.__aenter__.return_value = mock_session

            start_time = datetime.now(timezone.utc) - timedelta(hours=24)
            end_time = datetime.now(timezone.utc)

            # Generate reports for different jurisdictions
            us_task_id = await reporting_engine.generate_report(
                "us_cftc_trade_report",
                start_time,
                end_time,
                priority=ReportPriority.NORMAL,
            )

            eu_task_id = await reporting_engine.generate_report(
                "eu_mifid_transaction_report",
                start_time,
                end_time,
                priority=ReportPriority.NORMAL,
            )

            # Verify both tasks were created
            assert us_task_id in reporting_engine.active_tasks
            assert eu_task_id in reporting_engine.active_tasks

            us_task = reporting_engine.active_tasks[us_task_id]
            eu_task = reporting_engine.active_tasks[eu_task_id]

            # Verify different jurisdictions and formats
            assert us_task.report_spec.jurisdiction == RegulatoryJurisdiction.US_CFTC
            assert us_task.report_spec.format == ReportFormat.XML

            assert eu_task.report_spec.jurisdiction == RegulatoryJurisdiction.EU_MIFID
            assert eu_task.report_spec.format == ReportFormat.REGULATORY_XML
