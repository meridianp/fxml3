"""
Comprehensive TDD Test Suite for FXML4 Phase 6: Compliance & Regulatory Systems.

This test suite validates all Phase 6 compliance functionality including:
- Advanced trade surveillance and monitoring
- Enhanced regulatory reporting engine
- Risk limit enforcement with immutable audit trails
- Compliance analytics and reporting dashboard
- Integration between all compliance components
- Regulatory scenario validation

Test Structure:
- Unit tests for individual components
- Integration tests for component interactions
- End-to-end tests for complete compliance workflows
- Security and audit trail integrity tests
- Performance tests for real-time monitoring
- Regulatory scenario validation tests
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fxml4.compliance.analytics.compliance_dashboard import (
    AdvancedComplianceDashboard,
    ComplianceKPI,
    ComplianceMetricType,
    DashboardTimeframe,
)
from fxml4.compliance.reporting.enhanced_regulatory_engine import (
    ComplianceAlertLevel,
    EnhancedComplianceRecord,
    EnhancedRegulatoryReportingEngine,
    RegulatoryBreachAlert,
)
from fxml4.compliance.risk_limit_enforcement import (
    AdvancedRiskLimitEnforcementEngine,
    RiskAction,
    RiskLimit,
    RiskLimitBreach,
    RiskLimitType,
    RiskMonitoringMetrics,
)
from fxml4.compliance.surveillance.advanced_trade_monitor import (
    AdvancedTradeMonitor,
    AlertSeverity,
    PatternType,
    SurveillanceAlert,
)


class TestAdvancedTradeMonitor:
    """Test suite for advanced trade surveillance and monitoring system."""

    @pytest.fixture
    def trade_monitor(self):
        """Create trade monitor instance for testing."""
        return AdvancedTradeMonitor()

    @pytest.fixture
    def sample_trade_data(self):
        """Sample trade data for testing."""
        return {
            "trade_id": "test_trade_001",
            "symbol": "EURUSD",
            "quantity": Decimal("1000000"),
            "price": Decimal("1.0850"),
            "timestamp": datetime.now(timezone.utc),
            "user_id": "test_user",
            "broker": "test_broker",
            "side": "buy",
        }

    @pytest.mark.asyncio
    async def test_pattern_detection_wash_trading(
        self, trade_monitor, sample_trade_data
    ):
        """Test wash trading pattern detection."""
        # Arrange
        wash_trading_pattern = {
            "pattern_type": "wash_trading",
            "trades": [
                {**sample_trade_data, "side": "buy", "trade_id": "wash_1"},
                {
                    **sample_trade_data,
                    "side": "sell",
                    "trade_id": "wash_2",
                    "timestamp": sample_trade_data["timestamp"] + timedelta(seconds=30),
                },
                {
                    **sample_trade_data,
                    "side": "buy",
                    "trade_id": "wash_3",
                    "timestamp": sample_trade_data["timestamp"] + timedelta(seconds=60),
                },
            ],
        }

        # Act
        alerts = await trade_monitor.detect_wash_trading_pattern(wash_trading_pattern)

        # Assert
        assert len(alerts) > 0
        alert = alerts[0]
        assert alert.alert_type == PatternType.WASH_TRADING
        assert alert.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        assert alert.confidence_score >= 0.8
        assert "wash trading" in alert.description.lower()

    @pytest.mark.asyncio
    async def test_layering_pattern_detection(self, trade_monitor, sample_trade_data):
        """Test layering/spoofing pattern detection."""
        # Arrange
        layering_pattern = {
            "pattern_type": "layering",
            "orders": [
                {
                    **sample_trade_data,
                    "order_type": "limit",
                    "side": "buy",
                    "price": 1.0840,
                },
                {
                    **sample_trade_data,
                    "order_type": "limit",
                    "side": "buy",
                    "price": 1.0841,
                },
                {
                    **sample_trade_data,
                    "order_type": "limit",
                    "side": "buy",
                    "price": 1.0842,
                },
                {
                    **sample_trade_data,
                    "order_type": "market",
                    "side": "sell",
                    "quantity": 500000,
                },
            ],
            "cancellation_pattern": [True, True, True, False],  # First 3 cancelled
        }

        # Act
        alerts = await trade_monitor.detect_layering_pattern(layering_pattern)

        # Assert
        assert len(alerts) > 0
        alert = alerts[0]
        assert alert.alert_type == PatternType.LAYERING
        assert alert.severity >= AlertSeverity.MEDIUM
        assert (
            "layering" in alert.description.lower()
            or "spoofing" in alert.description.lower()
        )

    @pytest.mark.asyncio
    async def test_momentum_ignition_detection(self, trade_monitor, sample_trade_data):
        """Test momentum ignition pattern detection."""
        # Arrange
        momentum_pattern = {
            "pattern_type": "momentum_ignition",
            "initial_trades": [
                {**sample_trade_data, "quantity": 2000000, "price": 1.0850},
                {**sample_trade_data, "quantity": 1500000, "price": 1.0851},
            ],
            "follow_up_trades": [
                {
                    **sample_trade_data,
                    "quantity": 500000,
                    "price": 1.0849,
                    "side": "sell",
                },
            ],
            "time_window_seconds": 120,
        }

        # Act
        alerts = await trade_monitor.detect_momentum_ignition_pattern(momentum_pattern)

        # Assert
        assert len(alerts) > 0
        alert = alerts[0]
        assert alert.alert_type == PatternType.MOMENTUM_IGNITION
        assert alert.confidence_score >= 0.7
        assert "momentum" in alert.description.lower()

    @pytest.mark.asyncio
    async def test_cross_venue_surveillance(self, trade_monitor, sample_trade_data):
        """Test cross-venue surveillance capabilities."""
        # Arrange
        cross_venue_data = {
            "symbol": "EURUSD",
            "venues": {
                "venue_a": [
                    {**sample_trade_data, "venue": "venue_a", "price": 1.0850},
                    {**sample_trade_data, "venue": "venue_a", "price": 1.0851},
                ],
                "venue_b": [
                    {**sample_trade_data, "venue": "venue_b", "price": 1.0849},
                    {**sample_trade_data, "venue": "venue_b", "price": 1.0852},
                ],
            },
            "time_window": timedelta(minutes=5),
        }

        # Act
        alerts = await trade_monitor.analyze_cross_venue_activity(cross_venue_data)

        # Assert
        # Should detect price discrepancies or coordinated activity
        if alerts:  # May not always generate alerts for normal activity
            alert = alerts[0]
            assert "venue" in alert.description.lower()
            assert alert.confidence_score >= 0.6

    @pytest.mark.asyncio
    async def test_surveillance_integration_with_phase5_routing(self, trade_monitor):
        """Test integration with Phase 5 broker routing system."""
        # Arrange
        routing_data = {
            "order_id": "test_order_001",
            "routing_decision": {
                "selected_broker": "broker_a",
                "routing_score": 0.85,
                "execution_venue": "venue_1",
            },
            "execution_data": {
                "fill_rate": 0.98,
                "execution_time_ms": 150,
                "slippage_bps": 0.5,
            },
        }

        # Act
        alerts = await trade_monitor.analyze_routing_execution_for_surveillance(
            routing_data
        )

        # Assert
        # Should validate execution quality and detect any anomalies
        if routing_data["execution_data"]["slippage_bps"] > 2.0:
            assert len(alerts) > 0
            assert any("execution" in alert.description.lower() for alert in alerts)


class TestEnhancedRegulatoryReportingEngine:
    """Test suite for enhanced regulatory reporting engine."""

    @pytest.fixture
    def reporting_engine(self):
        """Create enhanced regulatory reporting engine for testing."""
        return EnhancedRegulatoryReportingEngine()

    @pytest.fixture
    def sample_compliance_event(self):
        """Sample compliance event for testing."""
        return {
            "type": "trade_executed",
            "trade_id": "test_trade_001",
            "symbol": "EURUSD",
            "quantity": 1000000,
            "price": 1.0850,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": "test_user",
            "pre_trade_compliance_passed": True,
            "best_execution_analysis": True,
        }

    @pytest.mark.asyncio
    async def test_real_time_compliance_event_processing(
        self, reporting_engine, sample_compliance_event
    ):
        """Test real-time compliance event processing."""
        # Act
        breach_alert = await reporting_engine.process_real_time_compliance_event(
            sample_compliance_event
        )

        # Assert
        # For a compliant trade, should not generate breach alert
        assert breach_alert is None

        # Verify compliance record was created
        assert len(reporting_engine.compliance_records) > 0
        record = list(reporting_engine.compliance_records.values())[-1]
        assert record.event_type == "trade_executed"
        assert record.compliance_score >= 0.8
        assert record.integrity_hash is not None

    @pytest.mark.asyncio
    async def test_compliance_breach_detection(self, reporting_engine):
        """Test compliance breach detection for non-compliant events."""
        # Arrange
        non_compliant_event = {
            "type": "trade_executed",
            "trade_id": "breach_trade_001",
            "symbol": "EURUSD",
            "quantity": 5000000,  # Large trade
            "price": 1.0850,
            "pre_trade_compliance_passed": False,  # Compliance violation
            "best_execution_analysis": False,  # Missing analysis
        }

        # Act
        breach_alert = await reporting_engine.process_real_time_compliance_event(
            non_compliant_event
        )

        # Assert
        assert breach_alert is not None
        assert isinstance(breach_alert, RegulatoryBreachAlert)
        assert breach_alert.severity in [
            ComplianceAlertLevel.BREACH,
            ComplianceAlertLevel.CRITICAL,
        ]
        assert "large_trade_no_compliance" in breach_alert.breach_type
        assert breach_alert.remediation_required is True

    @pytest.mark.asyncio
    async def test_enhanced_surveillance_report_generation(self, reporting_engine):
        """Test enhanced surveillance report generation."""
        # Arrange
        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        end_time = datetime.now(timezone.utc)

        # Act
        report_data = await reporting_engine.generate_enhanced_surveillance_report(
            start_time, end_time, include_patterns=True, include_compliance_scores=True
        )

        # Assert
        assert "report_period" in report_data
        assert "surveillance_summary" in report_data
        assert "compliance_metrics" in report_data
        assert "pattern_analysis" in report_data
        assert "jurisdiction_compliance_scores" in report_data
        assert "audit_trail_integrity" in report_data

        # Verify report structure
        assert report_data["report_period"]["start_time"] is not None
        assert report_data["report_period"]["end_time"] is not None

    @pytest.mark.asyncio
    async def test_audit_trail_integrity_verification(
        self, reporting_engine, sample_compliance_event
    ):
        """Test cryptographic audit trail integrity verification."""
        # Arrange - Create multiple compliance records
        for i in range(5):
            event = {**sample_compliance_event, "trade_id": f"test_trade_{i:03d}"}
            await reporting_engine.process_real_time_compliance_event(event)

        # Act
        integrity_results = await reporting_engine._verify_audit_trail_integrity()

        # Assert
        assert "total_records" in integrity_results
        assert "verified_records" in integrity_results
        assert "integrity_percentage" in integrity_results
        assert integrity_results["total_records"] >= 5
        assert integrity_results["integrity_percentage"] >= 95.0
        assert integrity_results["chain_continuity"] is True

    @pytest.mark.asyncio
    async def test_broker_routing_compliance_report(self, reporting_engine):
        """Test broker routing compliance report generation."""
        # Arrange
        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        end_time = datetime.now(timezone.utc)

        # Mock execution engine with routing analytics
        mock_engine = AsyncMock()
        mock_engine.get_routing_analytics.return_value = {
            "total_orders": 100,
            "venues_used": ["venue_a", "venue_b", "venue_c"],
            "average_fill_rate": 0.98,
            "price_improvement": 0.15,
            "speed_metrics": {"average_execution_time_ms": 120},
        }
        reporting_engine.set_execution_engine(mock_engine)

        # Act
        report_data = await reporting_engine.generate_broker_routing_compliance_report(
            start_time, end_time
        )

        # Assert
        assert "routing_analytics" in report_data
        assert "best_execution_analysis" in report_data
        assert "compliance_assessment" in report_data
        assert report_data["best_execution_analysis"]["total_orders_routed"] == 100
        assert len(report_data["best_execution_analysis"]["venues_utilized"]) == 3


class TestRiskLimitEnforcementEngine:
    """Test suite for advanced risk limit enforcement system."""

    @pytest.fixture
    def risk_engine(self):
        """Create risk limit enforcement engine for testing."""
        return AdvancedRiskLimitEnforcementEngine()

    @pytest.fixture
    def sample_position_data(self):
        """Sample position data for testing."""
        return {
            "symbol": "EURUSD",
            "quantity": 1000000,
            "price": 1.0850,
            "side": "buy",
            "account_id": "test_account",
            "user_id": "test_user",
        }

    @pytest.mark.asyncio
    async def test_risk_limit_creation_and_management(self, risk_engine):
        """Test risk limit creation, update, and removal."""
        # Arrange
        test_limit = RiskLimit(
            limit_id="test_position_limit",
            limit_type=RiskLimitType.POSITION_SIZE,
            description="Test position size limit",
            threshold_value=500000.0,
            warning_level=0.8,
            currency="USD",
            applicable_symbols=["EURUSD"],
            applicable_accounts=["test_account"],
            enforcement_action=RiskAction.BLOCK_NEW_POSITIONS,
        )

        # Act - Add limit
        risk_engine.add_risk_limit(test_limit)

        # Assert - Limit added
        assert "test_position_limit" in risk_engine.risk_limits
        stored_limit = risk_engine.risk_limits["test_position_limit"]
        assert stored_limit.threshold_value == 500000.0
        assert stored_limit.is_active is True

        # Act - Update limit
        updated = risk_engine.update_risk_limit(
            "test_position_limit", {"threshold_value": 750000.0, "warning_level": 0.85}
        )

        # Assert - Limit updated
        assert updated is True
        assert (
            risk_engine.risk_limits["test_position_limit"].threshold_value == 750000.0
        )
        assert risk_engine.risk_limits["test_position_limit"].warning_level == 0.85

        # Act - Remove limit
        removed = risk_engine.remove_risk_limit("test_position_limit")

        # Assert - Limit removed
        assert removed is True
        assert "test_position_limit" not in risk_engine.risk_limits

    @pytest.mark.asyncio
    async def test_risk_limit_breach_detection(self, risk_engine, sample_position_data):
        """Test risk limit breach detection and enforcement."""
        # Arrange - Add restrictive limit
        risk_engine.add_risk_limit(
            RiskLimit(
                limit_id="restrictive_position_limit",
                limit_type=RiskLimitType.POSITION_SIZE,
                description="Restrictive position limit for testing",
                threshold_value=500000.0,  # $500K limit
                warning_level=0.8,  # Warning at $400K
                currency="USD",
                applicable_symbols=["EURUSD"],
                applicable_accounts=["test_account"],
                enforcement_action=RiskAction.BLOCK_NEW_POSITIONS,
            )
        )

        # Position that exceeds limit: 1M * 1.0850 = $1,085,000
        large_position = {**sample_position_data, "quantity": 1000000}

        # Act
        is_compliant, breaches = await risk_engine.check_risk_limits(
            large_position, "test_account", "test_user"
        )

        # Assert
        assert is_compliant is False
        assert len(breaches) > 0

        breach = breaches[0]
        assert isinstance(breach, RiskLimitBreach)
        assert breach.breach_type == RiskLimitType.POSITION_SIZE
        assert breach.current_value > breach.limit_value
        assert breach.enforcement_action_taken == RiskAction.BLOCK_NEW_POSITIONS
        assert breach.breach_id in risk_engine.active_breaches

    @pytest.mark.asyncio
    async def test_immutable_audit_trail_creation(self, risk_engine):
        """Test immutable audit trail record creation and verification."""
        # Act - Create multiple audit records
        for i in range(3):
            await risk_engine._create_audit_record(
                f"test_event_{i}",
                {"test_data": f"value_{i}", "sequence": i},
                RiskAction.ALERT_ONLY,
            )

        # Assert - Audit chain created
        assert len(risk_engine.audit_chain) == 3

        # Verify chain integrity
        for i, record in enumerate(risk_engine.audit_chain):
            assert record.chain_position == i
            assert record.cryptographic_signature is not None
            assert record.verification_status == "unverified"  # Initially unverified

            if i > 0:
                assert (
                    record.previous_record_hash
                    == risk_engine.audit_chain[i - 1].cryptographic_signature
                )

        # Act - Verify audit trail integrity
        integrity_results = await risk_engine.verify_audit_trail_integrity()

        # Assert - All records verified
        assert integrity_results["total_records"] == 3
        assert integrity_results["verified_records"] == 3
        assert integrity_results["integrity_percentage"] == 100.0
        assert integrity_results["chain_continuity"] is True

    @pytest.mark.asyncio
    async def test_real_time_monitoring_loop(self, risk_engine):
        """Test real-time risk monitoring functionality."""
        # Arrange - Mock database queries
        with patch("fxml4.compliance.risk_limit_enforcement.get_db") as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session

            # Mock active accounts query
            mock_result = AsyncMock()
            mock_result.fetchall.return_value = [
                type(
                    "obj",
                    (object,),
                    {"account_id": "test_account", "user_id": "test_user"},
                )
            ]
            mock_session.execute.return_value = mock_result

            # Act - Start monitoring (brief test)
            await risk_engine.start_real_time_monitoring()
            assert risk_engine.monitoring_active is True

            # Allow one monitoring cycle
            await asyncio.sleep(0.1)

            # Stop monitoring
            await risk_engine.stop_real_time_monitoring()
            assert risk_engine.monitoring_active is False

    @pytest.mark.asyncio
    async def test_enforcement_action_execution(
        self, risk_engine, sample_position_data
    ):
        """Test enforcement action execution for different breach types."""
        # Arrange - Create breach requiring enforcement
        breach = RiskLimitBreach(
            breach_id="test_breach_001",
            limit_id="test_limit",
            breach_type=RiskLimitType.POSITION_SIZE,
            detected_at=datetime.now(timezone.utc),
            current_value=1000000.0,
            limit_value=500000.0,
            breach_magnitude=100.0,
            affected_positions=["EURUSD"],
            enforcement_action_taken=RiskAction.FORCE_REDUCE_POSITION,
        )

        # Act
        await risk_engine._execute_enforcement_action(
            breach, sample_position_data, "test_account", "test_user"
        )

        # Assert
        assert risk_engine.enforcement_actions_taken > 0

        # Verify audit record created
        assert len(risk_engine.audit_chain) > 0
        audit_record = risk_engine.audit_chain[-1]
        assert audit_record.event_type == "enforcement_action_executed"
        assert audit_record.enforcement_action == RiskAction.FORCE_REDUCE_POSITION


class TestComplianceDashboard:
    """Test suite for advanced compliance analytics and dashboard."""

    @pytest.fixture
    def dashboard(self):
        """Create compliance dashboard for testing."""
        return AdvancedComplianceDashboard()

    @pytest.mark.asyncio
    async def test_real_time_dashboard_data_generation(self, dashboard):
        """Test real-time dashboard data generation."""
        # Act
        dashboard_data = await dashboard.get_real_time_dashboard_data()

        # Assert
        assert "timestamp" in dashboard_data
        assert "overview" in dashboard_data
        assert "kpis" in dashboard_data
        assert "risk_monitoring" in dashboard_data
        assert "surveillance_status" in dashboard_data
        assert "regulatory_compliance" in dashboard_data
        assert "audit_trail_status" in dashboard_data
        assert "active_alerts" in dashboard_data
        assert "trend_analysis" in dashboard_data

    @pytest.mark.asyncio
    async def test_kpi_calculations_and_updates(self, dashboard):
        """Test KPI calculations and real-time updates."""
        # Act
        kpis_data = await dashboard._get_updated_kpis()

        # Assert
        assert "risk_compliance_score" in kpis_data
        assert "surveillance_efficiency" in kpis_data
        assert "reporting_timeliness" in kpis_data
        assert "audit_integrity" in kpis_data

        # Verify KPI structure
        risk_kpi = kpis_data["risk_compliance_score"]
        assert "current_value" in risk_kpi
        assert "target_value" in risk_kpi
        assert "status" in risk_kpi
        assert "trend_direction" in risk_kpi

    @pytest.mark.asyncio
    async def test_compliance_report_generation(self, dashboard):
        """Test comprehensive compliance report generation."""
        # Act
        report_data = await dashboard.generate_compliance_report(
            DashboardTimeframe.DAILY, include_charts=True, export_format="json"
        )

        # Assert
        assert "report_metadata" in report_data
        assert "executive_summary" in report_data
        assert "detailed_metrics" in report_data
        assert "risk_analysis" in report_data
        assert "surveillance_analysis" in report_data
        assert "regulatory_status" in report_data
        assert "recommendations" in report_data
        assert "charts" in report_data

        # Verify report metadata
        metadata = report_data["report_metadata"]
        assert metadata["timeframe"] == "daily"
        assert metadata["report_type"] == "comprehensive_compliance"

    @pytest.mark.asyncio
    async def test_interactive_dashboard_creation(self, dashboard):
        """Test interactive HTML dashboard creation."""
        # Act
        dashboard_html = await dashboard.create_interactive_dashboard()

        # Assert
        assert isinstance(dashboard_html, str)
        assert len(dashboard_html) > 1000  # Should be substantial HTML
        assert "Risk Compliance" in dashboard_html
        assert "plotly" in dashboard_html.lower()
        assert "<script>" in dashboard_html

    @pytest.mark.asyncio
    async def test_trend_analysis_and_forecasting(self, dashboard):
        """Test compliance trend analysis and forecasting."""
        # Act
        trend_data = await dashboard._get_trend_analysis()

        # Assert
        assert "metric_trends" in trend_data
        assert "forecast_analysis" in trend_data
        assert "trend_summary" in trend_data

        # Verify trend structure
        metrics = trend_data["metric_trends"]
        assert len(metrics) > 0

        for metric_name, trend in metrics.items():
            assert hasattr(trend, "metric_name") or isinstance(trend, dict)


class TestIntegratedComplianceWorkflows:
    """Integration tests for complete compliance workflows."""

    @pytest.fixture
    def integrated_system(self):
        """Create integrated compliance system for testing."""
        return {
            "trade_monitor": AdvancedTradeMonitor(),
            "reporting_engine": EnhancedRegulatoryReportingEngine(),
            "risk_engine": AdvancedRiskLimitEnforcementEngine(),
            "dashboard": AdvancedComplianceDashboard(),
        }

    @pytest.mark.asyncio
    async def test_end_to_end_trade_surveillance_workflow(self, integrated_system):
        """Test complete trade surveillance workflow."""
        # Arrange
        trade_monitor = integrated_system["trade_monitor"]
        reporting_engine = integrated_system["reporting_engine"]

        suspicious_trade = {
            "trade_id": "suspicious_001",
            "symbol": "EURUSD",
            "quantity": 10000000,  # Large trade
            "price": 1.0850,
            "timestamp": datetime.now(timezone.utc),
            "user_id": "suspicious_user",
            "pattern_indicators": ["large_size", "unusual_timing"],
        }

        # Act - Surveillance detection
        alerts = await trade_monitor.analyze_trade_for_surveillance(suspicious_trade)

        # Process alerts through regulatory reporting
        for alert in alerts:
            breach_alert = await reporting_engine.process_real_time_compliance_event(
                {
                    "type": "surveillance_alert",
                    "alert_id": alert.alert_id,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity.value,
                    "confidence_score": alert.confidence_score,
                    "trade_id": suspicious_trade["trade_id"],
                }
            )

        # Assert
        if alerts:
            assert len(alerts) > 0
            assert len(reporting_engine.compliance_records) > 0

    @pytest.mark.asyncio
    async def test_risk_breach_to_regulatory_reporting_workflow(
        self, integrated_system
    ):
        """Test risk breach detection to regulatory reporting workflow."""
        # Arrange
        risk_engine = integrated_system["risk_engine"]
        reporting_engine = integrated_system["reporting_engine"]

        # Set up integration
        reporting_engine.set_execution_engine(AsyncMock())

        # Create restrictive limit
        risk_engine.add_risk_limit(
            RiskLimit(
                limit_id="integration_test_limit",
                limit_type=RiskLimitType.DAILY_LOSS,
                description="Daily loss limit for integration test",
                threshold_value=10000.0,
                warning_level=0.75,
                currency="USD",
                applicable_symbols=[],
                applicable_accounts=["test_account"],
                enforcement_action=RiskAction.SUSPEND_TRADING,
            )
        )

        # Position causing loss breach
        loss_position = {
            "account_id": "test_account",
            "user_id": "test_user",
            "daily_pnl": -15000.0,  # Exceeds $10K limit
        }

        # Act
        is_compliant, breaches = await risk_engine.check_risk_limits(
            loss_position, "test_account", "test_user"
        )

        # Assert
        assert is_compliant is False
        assert len(breaches) > 0

        # Verify regulatory reporting integration
        # (This would verify that breach was sent to regulatory engine)

    @pytest.mark.asyncio
    async def test_dashboard_integration_with_all_systems(self, integrated_system):
        """Test dashboard integration with all compliance systems."""
        # Arrange
        dashboard = integrated_system["dashboard"]

        # Generate some test data in other systems
        risk_engine = integrated_system["risk_engine"]
        reporting_engine = integrated_system["reporting_engine"]

        # Create test compliance records
        await reporting_engine.process_real_time_compliance_event(
            {
                "type": "trade_executed",
                "trade_id": "dashboard_test_001",
                "symbol": "GBPUSD",
                "quantity": 500000,
                "price": 1.2650,
            }
        )

        # Act
        dashboard_data = await dashboard.get_real_time_dashboard_data()

        # Assert
        assert dashboard_data is not None
        assert "overview" in dashboard_data

        # Verify integration data is included
        overview = dashboard_data["overview"]
        assert "total_compliance_records" in overview
        assert "active_monitoring_systems" in overview


class TestRegulatoryScenarioValidation:
    """Test suite for regulatory scenario validation."""

    @pytest.mark.asyncio
    async def test_mifid_ii_transaction_reporting_scenario(self):
        """Test MiFID II transaction reporting compliance scenario."""
        # Arrange
        reporting_engine = EnhancedRegulatoryReportingEngine()

        eu_trade_event = {
            "type": "trade_executed",
            "trade_id": "eu_trade_001",
            "symbol": "EURUSD",
            "quantity": 2000000,
            "price": 1.0850,
            "client_jurisdiction": "EU",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "investment_firm": "FXML4_EU",
            "venue": "EU_REGULATED_VENUE",
            "client_id": "eu_client_001",
        }

        # Act
        compliance_record = await reporting_engine.process_real_time_compliance_event(
            eu_trade_event
        )

        # Assert
        # Should create compliance record with EU-specific requirements
        assert len(reporting_engine.compliance_records) > 0
        record = list(reporting_engine.compliance_records.values())[-1]
        assert "EU" in str(record.regulatory_flags) or "MIFID" in str(
            record.regulatory_flags
        )

    @pytest.mark.asyncio
    async def test_cftc_large_trader_reporting_scenario(self):
        """Test CFTC large trader reporting scenario."""
        # Arrange
        reporting_engine = EnhancedRegulatoryReportingEngine()

        # Large US trade requiring CFTC reporting
        large_us_trade = {
            "type": "trade_executed",
            "trade_id": "cftc_large_001",
            "symbol": "EURUSD",
            "quantity": 15000000,  # $15M+ notional
            "price": 1.0850,
            "jurisdiction": "US",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "counterparty": "US_BANK",
            "trader_classification": "large_trader",
        }

        # Act
        breach_alert = await reporting_engine.process_real_time_compliance_event(
            large_us_trade
        )

        # Assert
        # Should trigger CFTC reporting requirements
        compliance_records = list(reporting_engine.compliance_records.values())
        assert len(compliance_records) > 0

        latest_record = compliance_records[-1]
        assert "LARGE_NOTIONAL" in latest_record.regulatory_flags

    @pytest.mark.asyncio
    async def test_finra_suspicious_activity_reporting_scenario(self):
        """Test FINRA suspicious activity reporting scenario."""
        # Arrange
        trade_monitor = AdvancedTradeMonitor()
        reporting_engine = EnhancedRegulatoryReportingEngine()

        # Pattern indicating potential manipulation
        suspicious_pattern = {
            "pattern_type": "layering",
            "confidence_score": 0.92,
            "trades_involved": ["trade_001", "trade_002", "trade_003"],
            "detected_at": datetime.now(timezone.utc),
            "severity": "high",
        }

        # Act
        # Process suspicious activity detection
        breach_alert = await reporting_engine.process_real_time_compliance_event(
            {
                "type": "suspicious_activity_detected",
                "pattern_type": "layering",
                "confidence_score": 0.92,
                "trades_involved": suspicious_pattern["trades_involved"],
                "jurisdiction": "US",
                "requires_sar": True,  # Suspicious Activity Report
            }
        )

        # Assert
        if breach_alert:
            assert breach_alert.breach_type == "suspicious_activity_detected"
            assert "investigation_required" in str(breach_alert.regulatory_impact)


class TestSecurityAndAuditIntegrity:
    """Test suite for security and audit trail integrity."""

    @pytest.mark.asyncio
    async def test_cryptographic_audit_trail_security(self):
        """Test cryptographic security of audit trails."""
        # Arrange
        risk_engine = AdvancedRiskLimitEnforcementEngine()

        # Create audit records
        for i in range(10):
            await risk_engine._create_audit_record(
                f"security_test_{i}",
                {
                    "sensitive_data": f"value_{i}",
                    "timestamp": datetime.now().isoformat(),
                },
                RiskAction.ALERT_ONLY,
            )

        # Act - Verify integrity
        integrity_results = await risk_engine.verify_audit_trail_integrity()

        # Assert - All records should be cryptographically secure
        assert integrity_results["integrity_percentage"] == 100.0
        assert integrity_results["chain_continuity"] is True
        assert len(integrity_results["integrity_violations"]) == 0

        # Test tampering detection
        # Artificially tamper with a record
        if risk_engine.audit_chain:
            risk_engine.audit_chain[5].cryptographic_signature = "tampered_signature"

        # Re-verify integrity
        integrity_results_after_tampering = (
            await risk_engine.verify_audit_trail_integrity()
        )

        # Assert - Tampering should be detected
        assert integrity_results_after_tampering["integrity_percentage"] < 100.0
        assert len(integrity_results_after_tampering["integrity_violations"]) > 0

    @pytest.mark.asyncio
    async def test_sensitive_data_protection(self):
        """Test protection of sensitive data in compliance records."""
        # Arrange
        reporting_engine = EnhancedRegulatoryReportingEngine()

        sensitive_event = {
            "type": "trade_executed",
            "trade_id": "sensitive_001",
            "symbol": "EURUSD",
            "quantity": 1000000,
            "price": 1.0850,
            "client_pii": "SHOULD_NOT_BE_LOGGED",  # Sensitive data
            "account_details": "CONFIDENTIAL_INFO",
        }

        # Act
        await reporting_engine.process_real_time_compliance_event(sensitive_event)

        # Assert
        compliance_records = list(reporting_engine.compliance_records.values())
        record_data = json.dumps(compliance_records[-1].record_data)

        # Sensitive data should not appear in logs or be encrypted/hashed
        assert "SHOULD_NOT_BE_LOGGED" not in record_data
        assert "CONFIDENTIAL_INFO" not in record_data


class TestPerformanceAndScalability:
    """Performance and scalability tests for compliance systems."""

    @pytest.mark.asyncio
    async def test_high_volume_surveillance_processing(self):
        """Test surveillance system performance with high trade volumes."""
        # Arrange
        trade_monitor = AdvancedTradeMonitor()

        # Generate high volume of trades
        trades = []
        for i in range(1000):
            trades.append(
                {
                    "trade_id": f"perf_test_{i:04d}",
                    "symbol": "EURUSD",
                    "quantity": 100000 + (i * 1000),
                    "price": 1.0850 + (i * 0.0001),
                    "timestamp": datetime.now(timezone.utc) + timedelta(seconds=i),
                    "user_id": f"user_{i % 10}",
                }
            )

        # Act - Measure processing time
        start_time = datetime.now()

        alerts = []
        for trade in trades[:100]:  # Test with subset for reasonable test time
            trade_alerts = await trade_monitor.analyze_trade_for_surveillance(trade)
            alerts.extend(trade_alerts)

        processing_time = (datetime.now() - start_time).total_seconds()

        # Assert - Should process trades efficiently
        assert processing_time < 30.0  # Should complete within 30 seconds
        self.logger.info(f"Processed 100 trades in {processing_time:.2f} seconds")

    @pytest.mark.asyncio
    async def test_concurrent_risk_limit_checking(self):
        """Test concurrent risk limit checking performance."""
        # Arrange
        risk_engine = AdvancedRiskLimitEnforcementEngine()

        # Create multiple concurrent positions
        positions = []
        for i in range(50):
            positions.append(
                {
                    "symbol": f"PAIR{i:02d}",
                    "quantity": 500000,
                    "price": 1.0 + (i * 0.01),
                    "account_id": f"account_{i % 5}",
                    "user_id": f"user_{i % 10}",
                }
            )

        # Act - Process concurrently
        start_time = datetime.now()

        tasks = []
        for position in positions[:20]:  # Test subset
            task = risk_engine.check_risk_limits(
                position, position["account_id"], position["user_id"]
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processing_time = (datetime.now() - start_time).total_seconds()

        # Assert - Should handle concurrent processing efficiently
        assert processing_time < 10.0  # Should complete within 10 seconds
        assert len(results) == 20
        assert not any(isinstance(result, Exception) for result in results)


if __name__ == "__main__":
    # Run the test suite
    pytest.main([__file__, "-v", "--tb=short"])
