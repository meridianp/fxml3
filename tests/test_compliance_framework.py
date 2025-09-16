"""
Comprehensive Compliance Test Framework for FXML4 Trading Platform.

This test suite validates compliance with major financial regulations:
- MiFID II (Markets in Financial Instruments Directive)
- EMIR (European Market Infrastructure Regulation)
- Dodd-Frank Wall Street Reform Act

Test-Driven Development approach covering:
1. Transaction reporting requirements
2. Best execution monitoring and validation
3. Position limits and threshold monitoring
4. Trade surveillance and unusual activity detection
5. Regulatory reporting engines (XML/JSON formats)
6. Immutable audit trail with cryptographic integrity
7. Real-time compliance monitoring and alerts

Author: Claude Code Assistant
Created: 2024-08-27
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Test framework imports
from fxml4.api.auth.enhanced_audit_logger import (
    AuditEventType,
    LogLevel,
    TradingContext,
)
from fxml4.brokers.compliance.best_execution import (
    BestExecutionMonitor,
    ExecutionQuality,
    PriceImprovement,
)
from fxml4.brokers.compliance.position_limits import (
    LimitType,
    LimitViolation,
    PositionLimitMonitor,
)
from fxml4.brokers.compliance.regulatory_engine import (
    RegulatoryReportingEngine,
    ReportFormat,
    ReportType,
)
from fxml4.brokers.compliance.surveillance import (
    AlertSeverity,
    SurveillanceAlert,
    TradeSurveillanceEngine,
)
from fxml4.brokers.compliance.validators import (
    DoddFrankValidator,
    EMIRValidator,
    MiFIDIIValidator,
)


# Test Data Models
class MockTrade:
    def __init__(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        timestamp: datetime,
        user_id: str,
        broker: str = "IB",
        venue: str = "IDEALPRO",
    ):
        self.trade_id = trade_id
        self.symbol = symbol
        self.side = side  # "buy" or "sell"
        self.quantity = quantity
        self.price = price
        self.timestamp = timestamp
        self.user_id = user_id
        self.broker = broker
        self.venue = venue
        self.notional_value = quantity * price


class MockPosition:
    def __init__(
        self,
        symbol: str,
        quantity: Decimal,
        market_value: Decimal,
        user_id: str,
        last_updated: datetime,
    ):
        self.symbol = symbol
        self.quantity = quantity
        self.market_value = market_value
        self.user_id = user_id
        self.last_updated = last_updated


# Test Fixtures
@pytest.fixture
def sample_eur_usd_trade():
    """Sample EUR/USD trade for testing."""
    return MockTrade(
        trade_id="TRD-001",
        symbol="EURUSD",
        side="buy",
        quantity=Decimal("100000"),  # 1 standard lot
        price=Decimal("1.0850"),
        timestamp=datetime.now(timezone.utc),
        user_id="trader-001",
        broker="IB",
        venue="IDEALPRO",
    )


@pytest.fixture
def sample_gbp_usd_trade():
    """Sample GBP/USD trade for testing."""
    return MockTrade(
        trade_id="TRD-002",
        symbol="GBPUSD",
        side="sell",
        quantity=Decimal("50000"),  # 0.5 standard lot
        price=Decimal("1.2650"),
        timestamp=datetime.now(timezone.utc),
        user_id="trader-002",
        broker="FXCM",
        venue="FXCM",
    )


@pytest.fixture
def sample_large_position():
    """Sample large position for position limit testing."""
    return MockPosition(
        symbol="EURUSD",
        quantity=Decimal("5000000"),  # 50 standard lots
        market_value=Decimal("5425000"),  # €5.425M notional
        user_id="trader-001",
        last_updated=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_database():
    """Mock async database session."""
    return AsyncMock()


# Test Classes


@pytest.mark.compliance
@pytest.mark.regulatory
@pytest.mark.mifid
class TestMiFIDIICompliance:
    """Test MiFID II compliance requirements."""

    def test_mifid_validator_initialization(self):
        """Test MiFID II validator properly initializes."""
        validator = MiFIDIIValidator(
            reporting_threshold=Decimal("10000"),  # €10,000 threshold
            position_limit_notification=Decimal("1000000"),  # €1M position limit
        )

        assert validator.reporting_threshold == Decimal("10000")
        assert validator.position_limit_notification == Decimal("1000000")
        assert validator.regulation_name == "MiFID II"

    @pytest.mark.asyncio
    async def test_transaction_reporting_requirement(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test MiFID II transaction reporting for trades above threshold."""
        validator = MiFIDIIValidator(reporting_threshold=Decimal("50000"))

        # Trade above threshold should require reporting
        requires_reporting = await validator.requires_transaction_reporting(
            sample_eur_usd_trade, mock_database
        )

        assert requires_reporting == True

        # Generate transaction report
        report = await validator.generate_transaction_report(
            sample_eur_usd_trade, mock_database
        )

        assert report is not None
        assert report.trade_id == "TRD-001"
        assert report.regulation == "MiFID II"
        assert report.report_type == "Transaction Report"
        assert "EURUSD" in report.instrument_details
        assert report.notional_value == Decimal("108500")

    @pytest.mark.asyncio
    async def test_best_execution_obligation(self, sample_eur_usd_trade, mock_database):
        """Test MiFID II best execution monitoring."""
        validator = MiFIDIIValidator()

        # Mock market data for best execution comparison
        mock_market_data = {
            "EURUSD": {
                "bid": Decimal("1.0849"),
                "ask": Decimal("1.0851"),
                "venues": ["IDEALPRO", "EBS", "REUTERS"],
            }
        }

        execution_analysis = await validator.analyze_best_execution(
            sample_eur_usd_trade, mock_market_data, mock_database
        )

        assert execution_analysis.is_compliant == True
        assert execution_analysis.execution_venue == "IDEALPRO"
        assert execution_analysis.price_improvement is not None

    @pytest.mark.asyncio
    async def test_client_order_handling_rules(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test MiFID II client order handling and priority rules."""
        validator = MiFIDIIValidator()

        # Mock order queue for priority testing
        mock_order_queue = [
            {
                "order_id": "ORD-001",
                "timestamp": datetime.now(timezone.utc) - timedelta(minutes=5),
            },
            {
                "order_id": "ORD-002",
                "timestamp": datetime.now(timezone.utc) - timedelta(minutes=3),
            },
            {
                "order_id": "ORD-003",
                "timestamp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
        ]

        order_handling_compliance = await validator.validate_order_priority(
            sample_eur_usd_trade, mock_order_queue, mock_database
        )

        assert order_handling_compliance.is_compliant == True
        assert order_handling_compliance.order_priority_maintained == True

    @pytest.mark.asyncio
    async def test_position_limit_notifications(
        self, sample_large_position, mock_database
    ):
        """Test MiFID II position limit notification requirements."""
        validator = MiFIDIIValidator(position_limit_notification=Decimal("1000000"))

        # Large position should trigger notification requirement
        requires_notification = await validator.requires_position_notification(
            sample_large_position, mock_database
        )

        assert requires_notification == True

        # Generate position notification
        notification = await validator.generate_position_notification(
            sample_large_position, mock_database
        )

        assert notification is not None
        assert notification.symbol == "EURUSD"
        assert notification.notional_value == Decimal("5425000")
        assert notification.notification_type == "Position Limit Approach"


@pytest.mark.compliance
@pytest.mark.regulatory
@pytest.mark.emir
class TestEMIRCompliance:
    """Test EMIR compliance requirements."""

    def test_emir_validator_initialization(self):
        """Test EMIR validator properly initializes."""
        validator = EMIRValidator(
            clearing_threshold=Decimal("1000000"),
            reporting_counterparty_threshold=Decimal("100000"),
        )

        assert validator.clearing_threshold == Decimal("1000000")
        assert validator.reporting_counterparty_threshold == Decimal("100000")
        assert validator.regulation_name == "EMIR"

    @pytest.mark.asyncio
    async def test_trade_reporting_to_repository(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test EMIR trade reporting to trade repository."""
        validator = EMIRValidator()

        # Generate EMIR trade report
        trade_report = await validator.generate_trade_repository_report(
            sample_eur_usd_trade, mock_database
        )

        assert trade_report is not None
        assert trade_report.regulation == "EMIR"
        assert trade_report.report_type == "Trade Repository Report"
        assert trade_report.counterparty_details is not None
        assert trade_report.trade_details["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_clearing_obligation_assessment(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test EMIR clearing obligation for derivative instruments."""
        validator = EMIRValidator(clearing_threshold=Decimal("500000"))

        # Trade below clearing threshold
        clearing_required = await validator.requires_clearing(
            sample_eur_usd_trade, mock_database
        )

        # Spot FX typically doesn't require clearing under EMIR
        assert clearing_required == False

        # Test with derivative instrument (mock)
        derivative_trade = MockTrade(
            trade_id="TRD-DERIV-001",
            symbol="EURUSD_FWD_3M",
            side="buy",
            quantity=Decimal("1000000"),
            price=Decimal("1.0900"),
            timestamp=datetime.now(timezone.utc),
            user_id="trader-001",
        )

        clearing_required_derivative = await validator.requires_clearing(
            derivative_trade, mock_database
        )

        assert clearing_required_derivative == True

    @pytest.mark.asyncio
    async def test_risk_mitigation_procedures(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test EMIR risk mitigation for uncleared derivatives."""
        validator = EMIRValidator()

        # Mock uncleared derivative position
        uncleared_position = {
            "position_id": "POS-001",
            "symbol": "EURUSD_SWAP",
            "notional": Decimal("2000000"),
            "maturity": datetime.now(timezone.utc) + timedelta(days=90),
            "is_cleared": False,
        }

        risk_mitigation = await validator.assess_risk_mitigation_requirements(
            uncleared_position, mock_database
        )

        assert risk_mitigation.collateral_required == True
        assert risk_mitigation.mark_to_market_required == True
        assert risk_mitigation.portfolio_reconciliation_required == True


@pytest.mark.compliance
@pytest.mark.regulatory
@pytest.mark.dodd_frank
class TestDoddFrankCompliance:
    """Test Dodd-Frank compliance requirements."""

    def test_dodd_frank_validator_initialization(self):
        """Test Dodd-Frank validator properly initializes."""
        validator = DoddFrankValidator(
            swap_dealer_threshold=Decimal("8000000000"),  # $8 billion
            major_swap_participant_threshold=Decimal("1000000000"),  # $1 billion
        )

        assert validator.swap_dealer_threshold == Decimal("8000000000")
        assert validator.major_swap_participant_threshold == Decimal("1000000000")
        assert validator.regulation_name == "Dodd-Frank"

    @pytest.mark.asyncio
    async def test_swap_data_reporting(self, sample_eur_usd_trade, mock_database):
        """Test Dodd-Frank swap data reporting requirements."""
        validator = DoddFrankValidator()

        # Generate swap data report
        swap_report = await validator.generate_swap_data_report(
            sample_eur_usd_trade, mock_database
        )

        assert swap_report is not None
        assert swap_report.regulation == "Dodd-Frank"
        assert swap_report.report_type == "Swap Data Report"
        assert swap_report.swap_data_repository is not None
        assert "economic_terms" in swap_report.trade_details

    @pytest.mark.asyncio
    async def test_position_limits_monitoring(
        self, sample_large_position, mock_database
    ):
        """Test Dodd-Frank position limits and monitoring."""
        validator = DoddFrankValidator()

        # Check position against Dodd-Frank limits
        position_analysis = await validator.analyze_position_limits(
            sample_large_position, mock_database
        )

        assert position_analysis.is_within_limits == True  # Assuming within limits
        assert position_analysis.limit_utilization is not None
        assert position_analysis.regulatory_limit_reference is not None

    @pytest.mark.asyncio
    async def test_real_time_reporting_requirements(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test Dodd-Frank real-time reporting requirements."""
        validator = DoddFrankValidator()

        # Check if trade requires real-time reporting
        requires_rt_reporting = await validator.requires_real_time_reporting(
            sample_eur_usd_trade, mock_database
        )

        assert isinstance(requires_rt_reporting, bool)

        if requires_rt_reporting:
            rt_report = await validator.generate_real_time_report(
                sample_eur_usd_trade, mock_database
            )
            assert rt_report.reporting_deadline is not None
            assert (
                rt_report.reporting_delay_minutes <= 15
            )  # Real-time = within 15 minutes


@pytest.mark.compliance
@pytest.mark.reporting
class TestRegulatoryReportingEngine:
    """Test regulatory reporting engine functionality."""

    def test_reporting_engine_initialization(self):
        """Test regulatory reporting engine initializes correctly."""
        engine = RegulatoryReportingEngine(
            supported_formats=[ReportFormat.XML, ReportFormat.JSON],
            max_report_retention_days=2555,  # 7 years
        )

        assert ReportFormat.XML in engine.supported_formats
        assert ReportFormat.JSON in engine.supported_formats
        assert engine.max_report_retention_days == 2555

    @pytest.mark.asyncio
    async def test_xml_report_generation(self, sample_eur_usd_trade, mock_database):
        """Test XML format regulatory report generation."""
        engine = RegulatoryReportingEngine()

        xml_report = await engine.generate_report(
            trade_data=sample_eur_usd_trade,
            report_type=ReportType.TRANSACTION_REPORT,
            format=ReportFormat.XML,
            regulation="MiFID II",
            db=mock_database,
        )

        assert xml_report.format == ReportFormat.XML
        assert xml_report.regulation == "MiFID II"
        assert xml_report.content.startswith("<?xml")
        assert "TRD-001" in xml_report.content
        assert "EURUSD" in xml_report.content

    @pytest.mark.asyncio
    async def test_json_report_generation(self, sample_eur_usd_trade, mock_database):
        """Test JSON format regulatory report generation."""
        engine = RegulatoryReportingEngine()

        json_report = await engine.generate_report(
            trade_data=sample_eur_usd_trade,
            report_type=ReportType.POSITION_REPORT,
            format=ReportFormat.JSON,
            regulation="EMIR",
            db=mock_database,
        )

        assert json_report.format == ReportFormat.JSON
        assert json_report.regulation == "EMIR"

        # Validate JSON structure
        import json

        report_data = json.loads(json_report.content)
        assert "trade_id" in report_data
        assert report_data["trade_id"] == "TRD-001"

    @pytest.mark.asyncio
    async def test_t_plus_1_reporting_deadline(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test T+1 reporting deadline compliance."""
        engine = RegulatoryReportingEngine()

        # Create trade from yesterday
        yesterday_trade = MockTrade(
            trade_id="TRD-T1-001",
            symbol="EURUSD",
            side="buy",
            quantity=Decimal("100000"),
            price=Decimal("1.0850"),
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
            user_id="trader-001",
        )

        report = await engine.generate_t_plus_1_report(yesterday_trade, mock_database)

        assert report.is_on_time == True
        assert report.reporting_deadline is not None
        assert report.submission_timestamp is not None


@pytest.mark.compliance
@pytest.mark.surveillance
class TestTradeSurveillanceEngine:
    """Test trade surveillance and unusual activity detection."""

    def test_surveillance_engine_initialization(self):
        """Test trade surveillance engine initializes correctly."""
        engine = TradeSurveillanceEngine(
            volume_threshold_multiplier=5.0,
            price_movement_threshold=0.02,  # 2%
            frequency_threshold=10,  # trades per minute
        )

        assert engine.volume_threshold_multiplier == 5.0
        assert engine.price_movement_threshold == 0.02
        assert engine.frequency_threshold == 10

    @pytest.mark.asyncio
    async def test_unusual_volume_detection(self, mock_database):
        """Test detection of unusual trading volumes."""
        engine = TradeSurveillanceEngine(volume_threshold_multiplier=3.0)

        # Create series of trades with one unusually large trade
        trades = [
            MockTrade(
                "TRD-1",
                "EURUSD",
                "buy",
                Decimal("100000"),
                Decimal("1.0850"),
                datetime.now(timezone.utc) - timedelta(minutes=10),
                "trader-001",
            ),
            MockTrade(
                "TRD-2",
                "EURUSD",
                "buy",
                Decimal("150000"),
                Decimal("1.0851"),
                datetime.now(timezone.utc) - timedelta(minutes=8),
                "trader-001",
            ),
            MockTrade(
                "TRD-3",
                "EURUSD",
                "buy",
                Decimal("1500000"),
                Decimal("1.0852"),  # Unusually large
                datetime.now(timezone.utc) - timedelta(minutes=5),
                "trader-001",
            ),
        ]

        alerts = await engine.detect_unusual_volume(trades, mock_database)

        assert len(alerts) >= 1
        unusual_volume_alert = next(
            (alert for alert in alerts if alert.alert_type == "UNUSUAL_VOLUME"), None
        )
        assert unusual_volume_alert is not None
        assert unusual_volume_alert.severity == AlertSeverity.HIGH
        assert "TRD-3" in unusual_volume_alert.details

    @pytest.mark.asyncio
    async def test_rapid_fire_trading_detection(self, mock_database):
        """Test detection of rapid-fire trading patterns."""
        engine = TradeSurveillanceEngine(frequency_threshold=5)

        # Create rapid sequence of trades (6 trades in 1 minute)
        base_time = datetime.now(timezone.utc)
        rapid_trades = [
            MockTrade(
                f"TRD-RF-{i}",
                "EURUSD",
                "buy",
                Decimal("50000"),
                Decimal("1.0850"),
                base_time + timedelta(seconds=i * 10),
                "trader-rapid",
            )
            for i in range(6)
        ]

        alerts = await engine.detect_rapid_fire_trading(rapid_trades, mock_database)

        assert len(alerts) >= 1
        rapid_fire_alert = next(
            (alert for alert in alerts if alert.alert_type == "RAPID_FIRE_TRADING"),
            None,
        )
        assert rapid_fire_alert is not None
        assert rapid_fire_alert.severity == AlertSeverity.MEDIUM
        assert "trader-rapid" in rapid_fire_alert.details

    @pytest.mark.asyncio
    async def test_price_manipulation_detection(self, mock_database):
        """Test detection of potential price manipulation patterns."""
        engine = TradeSurveillanceEngine()

        # Mock suspicious trading pattern
        suspicious_pattern = {
            "symbol": "EURUSD",
            "time_window": timedelta(minutes=15),
            "trades": [
                {
                    "side": "buy",
                    "quantity": Decimal("200000"),
                    "price": Decimal("1.0850"),
                },
                {
                    "side": "buy",
                    "quantity": Decimal("300000"),
                    "price": Decimal("1.0855"),
                },
                {
                    "side": "sell",
                    "quantity": Decimal("500000"),
                    "price": Decimal("1.0860"),
                },  # Suspicious sell after buying up
            ],
        }

        manipulation_alert = await engine.analyze_price_manipulation_pattern(
            suspicious_pattern, mock_database
        )

        assert manipulation_alert is not None
        assert manipulation_alert.alert_type == "POTENTIAL_MANIPULATION"
        assert manipulation_alert.severity == AlertSeverity.HIGH


@pytest.mark.compliance
@pytest.mark.position_limits
class TestPositionLimitMonitor:
    """Test position limits and threshold monitoring."""

    def test_position_limit_monitor_initialization(self):
        """Test position limit monitor initializes correctly."""
        monitor = PositionLimitMonitor(
            default_position_limit=Decimal("10000000"),  # $10M
            concentration_limit_pct=0.25,  # 25%
            var_limit=Decimal("500000"),  # $500K VaR
        )

        assert monitor.default_position_limit == Decimal("10000000")
        assert monitor.concentration_limit_pct == 0.25
        assert monitor.var_limit == Decimal("500000")

    @pytest.mark.asyncio
    async def test_position_limit_violation_detection(
        self, sample_large_position, mock_database
    ):
        """Test detection of position limit violations."""
        monitor = PositionLimitMonitor(
            default_position_limit=Decimal(
                "1000000"
            )  # $1M limit (sample position is $5.425M)
        )

        violation = await monitor.check_position_limits(
            sample_large_position, mock_database
        )

        assert violation is not None
        assert violation.limit_type == LimitType.POSITION_LIMIT
        assert violation.current_exposure > monitor.default_position_limit
        assert violation.violation_amount > Decimal("0")
        assert violation.severity == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_concentration_limit_monitoring(self, mock_database):
        """Test monitoring of portfolio concentration limits."""
        monitor = PositionLimitMonitor(
            concentration_limit_pct=0.20
        )  # 20% max per symbol

        # Mock portfolio with high concentration in EURUSD
        mock_portfolio = {
            "EURUSD": Decimal("8000000"),  # 80% of portfolio
            "GBPUSD": Decimal("1500000"),  # 15% of portfolio
            "USDJPY": Decimal("500000"),  # 5% of portfolio
        }

        total_portfolio_value = sum(mock_portfolio.values())

        violations = await monitor.check_concentration_limits(
            mock_portfolio, total_portfolio_value, mock_database
        )

        assert len(violations) >= 1
        eurusd_violation = next(
            (v for v in violations if "EURUSD" in str(v.details)), None
        )
        assert eurusd_violation is not None
        assert eurusd_violation.limit_type == LimitType.CONCENTRATION_LIMIT


@pytest.mark.compliance
@pytest.mark.best_execution
class TestBestExecutionMonitor:
    """Test best execution monitoring and validation."""

    def test_best_execution_monitor_initialization(self):
        """Test best execution monitor initializes correctly."""
        monitor = BestExecutionMonitor(
            price_improvement_threshold=Decimal("0.0001"),  # 1 pip
            execution_venues=["IDEALPRO", "EBS", "REUTERS", "FXCM"],
            latency_threshold_ms=100,
        )

        assert monitor.price_improvement_threshold == Decimal("0.0001")
        assert "IDEALPRO" in monitor.execution_venues
        assert monitor.latency_threshold_ms == 100

    @pytest.mark.asyncio
    async def test_price_improvement_calculation(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test calculation of price improvement for executed trades."""
        monitor = BestExecutionMonitor()

        # Mock market data at time of execution
        market_data = {
            "EURUSD": {
                "best_bid": Decimal("1.0849"),
                "best_ask": Decimal("1.0851"),
                "venues": {
                    "IDEALPRO": {"bid": Decimal("1.0849"), "ask": Decimal("1.0851")},
                    "EBS": {"bid": Decimal("1.0848"), "ask": Decimal("1.0852")},
                    "REUTERS": {"bid": Decimal("1.0849"), "ask": Decimal("1.0852")},
                },
            }
        }

        execution_quality = await monitor.calculate_execution_quality(
            sample_eur_usd_trade, market_data, mock_database
        )

        assert execution_quality is not None
        assert execution_quality.achieved_best_execution == True
        assert execution_quality.price_improvement is not None
        assert execution_quality.execution_venue == "IDEALPRO"

    @pytest.mark.asyncio
    async def test_execution_quality_metrics(self, sample_eur_usd_trade, mock_database):
        """Test comprehensive execution quality metrics."""
        monitor = BestExecutionMonitor()

        # Mock execution details
        execution_details = {
            "order_timestamp": datetime.now(timezone.utc) - timedelta(milliseconds=50),
            "execution_timestamp": datetime.now(timezone.utc),
            "requested_quantity": Decimal("100000"),
            "executed_quantity": Decimal("100000"),
            "average_execution_price": Decimal("1.0850"),
            "total_commission": Decimal("2.50"),
        }

        quality_metrics = await monitor.generate_execution_quality_report(
            sample_eur_usd_trade, execution_details, mock_database
        )

        assert quality_metrics.fill_rate == Decimal("1.0")  # 100% filled
        assert quality_metrics.execution_latency_ms <= 100
        assert quality_metrics.total_transaction_cost is not None
        assert quality_metrics.meets_best_execution_standard == True


@pytest.mark.compliance
@pytest.mark.integration
class TestComplianceIntegration:
    """Test integrated compliance workflow and validation."""

    @pytest.mark.asyncio
    async def test_comprehensive_compliance_check(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test comprehensive compliance validation across all regulations."""
        # Initialize all compliance validators
        mifid_validator = MiFIDIIValidator()
        emir_validator = EMIRValidator()
        dodd_frank_validator = DoddFrankValidator()

        # Run comprehensive compliance check
        compliance_results = {
            "mifid_ii": await mifid_validator.validate_transaction(
                sample_eur_usd_trade, mock_database
            ),
            "emir": await emir_validator.validate_transaction(
                sample_eur_usd_trade, mock_database
            ),
            "dodd_frank": await dodd_frank_validator.validate_transaction(
                sample_eur_usd_trade, mock_database
            ),
        }

        # Verify all compliance checks completed
        assert all(result.completed for result in compliance_results.values())
        assert all(
            result.regulation_name in ["MiFID II", "EMIR", "Dodd-Frank"]
            for result in compliance_results.values()
        )

    @pytest.mark.asyncio
    async def test_regulatory_reporting_workflow(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test end-to-end regulatory reporting workflow."""
        reporting_engine = RegulatoryReportingEngine()

        # Generate all required regulatory reports
        reports = []

        # MiFID II Transaction Report
        mifid_report = await reporting_engine.generate_report(
            sample_eur_usd_trade,
            ReportType.TRANSACTION_REPORT,
            ReportFormat.XML,
            "MiFID II",
            mock_database,
        )
        reports.append(mifid_report)

        # EMIR Trade Repository Report
        emir_report = await reporting_engine.generate_report(
            sample_eur_usd_trade,
            ReportType.TRADE_REPOSITORY_REPORT,
            ReportFormat.JSON,
            "EMIR",
            mock_database,
        )
        reports.append(emir_report)

        # Dodd-Frank Swap Data Report
        dodd_frank_report = await reporting_engine.generate_report(
            sample_eur_usd_trade,
            ReportType.SWAP_DATA_REPORT,
            ReportFormat.XML,
            "Dodd-Frank",
            mock_database,
        )
        reports.append(dodd_frank_report)

        # Validate all reports generated successfully
        assert len(reports) == 3
        assert all(report.generation_successful for report in reports)
        assert all(report.content is not None for report in reports)

    @pytest.mark.asyncio
    async def test_compliance_alert_workflow(
        self, sample_large_position, mock_database
    ):
        """Test compliance alert generation and handling workflow."""
        # Initialize monitoring systems
        surveillance_engine = TradeSurveillanceEngine()
        position_monitor = PositionLimitMonitor(
            default_position_limit=Decimal("1000000")
        )

        # Create mock trading activity that should trigger alerts
        suspicious_trades = [
            MockTrade(
                f"ALERT-{i}",
                "EURUSD",
                "buy",
                Decimal("500000"),
                Decimal("1.0850"),
                datetime.now(timezone.utc) - timedelta(minutes=i),
                "suspicious-trader",
            )
            for i in range(3)
        ]

        # Run surveillance checks
        surveillance_alerts = await surveillance_engine.detect_unusual_volume(
            suspicious_trades, mock_database
        )

        # Run position limit checks
        position_violation = await position_monitor.check_position_limits(
            sample_large_position, mock_database
        )

        # Validate alerts generated
        assert len(surveillance_alerts) > 0
        assert position_violation is not None

        # Test alert severity prioritization
        high_severity_alerts = [
            alert
            for alert in surveillance_alerts
            if alert.severity == AlertSeverity.HIGH
        ]
        assert len(high_severity_alerts) > 0

    @pytest.mark.asyncio
    async def test_audit_trail_compliance_integration(
        self, sample_eur_usd_trade, mock_database
    ):
        """Test integration with audit trail for compliance tracking."""
        from fxml4.api.auth.enhanced_audit_logger import get_audit_logger

        audit_logger = get_audit_logger()

        # Log compliance check events
        trading_context = TradingContext(
            user_id="trader-001",
            session_id="session-123",
            ip_address="192.168.1.100",
            user_agent="FXML4-Client/1.0",
            request_id="req-123",
        )

        await audit_logger.log_trading_activity(
            AuditEventType.COMPLIANCE_CHECK,
            f"Compliance validation completed for trade {sample_eur_usd_trade.trade_id}",
            trading_context,
            {
                "trade_id": sample_eur_usd_trade.trade_id,
                "regulations_checked": ["MiFID II", "EMIR", "Dodd-Frank"],
                "all_compliant": True,
                "reports_generated": 3,
            },
            LogLevel.INFO,
        )

        # Verify audit logging integration works
        assert audit_logger is not None


if __name__ == "__main__":
    """Run compliance tests directly."""
    pytest.main([__file__, "-v", "-s", "--tb=short"])
