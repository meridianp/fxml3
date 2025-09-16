"""
pytest tests for FXML4 AdvancedComplianceDashboard and related classes.

Targets:
- Classes: DashboardTimeframe, ComplianceMetricType, ComplianceKPI, ComplianceTrend, RegulatorySnapshot
- Core methods: data aggregation, scoring, alerts, caching, report generation, HTML dashboard

Notes:
- External engines and monitors are mocked (risk engine, regulatory engine, surveillance monitor)
- Async methods are tested with pytest.mark.asyncio
- Includes positive, negative, and boundary cases
- Machine-learning-like metrics (precision/recall trends) are validated where exposed
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.compliance.analytics.compliance_dashboard import (
    AdvancedComplianceDashboard,
    ComplianceKPI,
    ComplianceMetricType,
    ComplianceTrend,
    DashboardTimeframe,
    RegulatorySnapshot,
    compliance_dashboard,
    get_compliance_dashboard,
)

pytestmark = [pytest.mark.unit, pytest.mark.machine_learning, pytest.mark.compliance]


# ----------------------
# Fixtures and test data
# ----------------------


@pytest.fixture
def risk_stats_base() -> Dict[str, Any]:
    """Base risk statistics used across tests."""
    return {
        "monitoring_status": {"is_active": True},
        "enforcement_metrics": {
            "total_breaches_detected": 0,
            "active_breaches": 0,
        },
        "risk_limits": {"active_limits": 10},
        "current_metrics": {"portfolio_var": 0.12},
    }


@pytest.fixture
def regulatory_stats_base() -> Dict[str, Any]:
    """Base regulatory statistics used across tests."""
    return {
        "compliance_records_total": 100,
        "compliance_violations_total": 2,
        "audit_trail_integrity": {"integrity_percentage": 99.5},
    }


@pytest.fixture
def surveillance_stats_base() -> Dict[str, Any]:
    """Base surveillance statistics used across tests."""
    return {
        "total_alerts_generated": 5,
        "high_confidence_alerts": 1,
    }


@pytest.fixture
def mock_dependencies(risk_stats_base, regulatory_stats_base, surveillance_stats_base):
    """Patch external dependencies used by the dashboard and yield patchers."""
    with (
        patch(
            "fxml4.compliance.analytics.compliance_dashboard.get_config",
            return_value={
                "compliance.dashboard.real_time_enabled": True,
                "compliance.dashboard.refresh_interval": 1,
                "compliance.dashboard.cache_duration": 5,
            },
        ) as p_cfg,
        patch(
            "fxml4.compliance.analytics.compliance_dashboard.get_logger",
            return_value=MagicMock(),
        ) as p_logger,
        patch(
            "fxml4.compliance.analytics.compliance_dashboard.AdvancedTradeMonitor"
        ) as p_monitor,
        patch(
            "fxml4.compliance.analytics.compliance_dashboard.risk_limit_enforcement_engine"
        ) as p_risk,
        patch(
            "fxml4.compliance.analytics.compliance_dashboard.enhanced_regulatory_reporting_engine"
        ) as p_reg,
    ):
        # Configure surveillance monitor mock
        monitor_instance = MagicMock()
        monitor_instance.get_surveillance_statistics = AsyncMock(
            return_value=surveillance_stats_base
        )
        monitor_instance.get_recent_alerts = AsyncMock(return_value=[])
        p_monitor.return_value = monitor_instance

        # Configure risk engine mocks
        p_risk.get_risk_enforcement_statistics = AsyncMock(return_value=risk_stats_base)
        p_risk.verify_audit_trail_integrity = AsyncMock(
            return_value={"integrity_percentage": 100.0}
        )
        p_risk.active_breaches = {}

        # Configure regulatory engine mocks
        p_reg.get_enhanced_compliance_statistics = AsyncMock(
            return_value=regulatory_stats_base
        )
        p_reg._verify_audit_trail_integrity = AsyncMock(
            return_value={"integrity_percentage": 99.0}
        )
        p_reg.regulatory_breaches = {}

        yield {
            "cfg": p_cfg,
            "logger": p_logger,
            "monitor": p_monitor,
            "risk": p_risk,
            "reg": p_reg,
        }


@pytest.fixture
def dashboard(mock_dependencies) -> AdvancedComplianceDashboard:
    """Provision a dashboard instance with all external services mocked."""
    return AdvancedComplianceDashboard()


# ----------------------
# Enum and dataclass tests
# ----------------------


def test_dashboard_timeframe_enum_values():
    """Validate DashboardTimeframe enum contains expected values."""
    assert DashboardTimeframe.REAL_TIME.value == "real_time"
    assert DashboardTimeframe.HOURLY.value == "hourly"
    assert DashboardTimeframe.DAILY.value == "daily"
    assert DashboardTimeframe.WEEKLY.value == "weekly"
    assert DashboardTimeframe.MONTHLY.value == "monthly"
    assert DashboardTimeframe.QUARTERLY.value == "quarterly"


def test_compliance_metric_type_enum_values():
    """Validate ComplianceMetricType enum contains expected values."""
    assert ComplianceMetricType.RISK_COMPLIANCE.value == "risk_compliance"
    assert ComplianceMetricType.SURVEILLANCE_ALERTS.value == "surveillance_alerts"
    assert ComplianceMetricType.REPORTING_TIMELINESS.value == "reporting_timeliness"
    assert ComplianceMetricType.AUDIT_INTEGRITY.value == "audit_integrity"


def test_compliance_kpi_dataclass_properties():
    """Create a ComplianceKPI and validate fields are set correctly."""
    now = datetime.now(timezone.utc)
    kpi = ComplianceKPI(
        kpi_id="k1",
        name="Test KPI",
        current_value=0.5,
        target_value=0.9,
        threshold_warning=0.7,
        threshold_critical=0.6,
        unit="percentage",
        trend_direction="up",
        last_updated=now,
        status="critical",
        description="Testing",
    )
    assert kpi.kpi_id == "k1"
    assert kpi.current_value == 0.5
    assert kpi.status == "critical"
    assert kpi.last_updated == now


def test_compliance_trend_dataclass_properties():
    """Create a ComplianceTrend and validate fields are set correctly."""
    pts = [(datetime.now(timezone.utc), 0.9)]
    trend = ComplianceTrend(
        metric_name="risk_compliance",
        timeframe=DashboardTimeframe.DAILY,
        data_points=pts,
        trend_analysis={"direction": "up"},
    )
    assert trend.metric_name == "risk_compliance"
    assert trend.timeframe is DashboardTimeframe.DAILY
    assert trend.data_points == pts
    assert trend.trend_analysis["direction"] == "up"


def test_regulatory_snapshot_dataclass_properties():
    """Create a RegulatorySnapshot and validate fields are set correctly."""
    snap = RegulatorySnapshot(
        jurisdiction="US_CFTC",
        overall_score=0.97,
        active_requirements=10,
        compliant_requirements=10,
        pending_reports=0,
        overdue_reports=0,
        recent_breaches=0,
        risk_level="low",
        last_assessment=datetime.now(timezone.utc),
    )
    assert snap.jurisdiction == "US_CFTC"
    assert 0.0 <= snap.overall_score <= 1.0
    assert snap.risk_level == "low"


# ----------------------
# Core logic and helpers
# ----------------------


@pytest.mark.asyncio
async def test_get_real_time_dashboard_data_caching(dashboard):
    """Ensure dashboard data is cached and reused within cache duration."""
    # Patch internals to controlled values
    with (
        patch.object(
            dashboard, "_get_compliance_overview", AsyncMock(return_value={"ok": True})
        ) as p1,
        patch.object(
            dashboard,
            "_get_updated_kpis",
            AsyncMock(return_value={"k": {"current_value": 1.0}}),
        ) as p2,
        patch.object(
            dashboard, "_get_risk_monitoring_data", AsyncMock(return_value={"risk": 1})
        ) as p3,
        patch.object(
            dashboard, "_get_surveillance_status", AsyncMock(return_value={"surv": 1})
        ) as p4,
        patch.object(
            dashboard,
            "_get_regulatory_compliance_status",
            AsyncMock(return_value={"reg": 1}),
        ) as p5,
        patch.object(
            dashboard, "_get_audit_trail_status", AsyncMock(return_value={"audit": 1})
        ) as p6,
        patch.object(
            dashboard, "_get_active_alerts", AsyncMock(return_value=[{"a": 1}])
        ) as p7,
        patch.object(
            dashboard, "_get_recent_breaches", AsyncMock(return_value=[{"b": 1}])
        ) as p8,
        patch.object(
            dashboard, "_get_trend_analysis", AsyncMock(return_value={"trend": 1})
        ) as p9,
    ):
        first = await dashboard.get_real_time_dashboard_data()
        # Change mocks to raise if called again
        p1.side_effect = AssertionError("_get_compliance_overview called despite cache")
        p2.side_effect = AssertionError("_get_updated_kpis called despite cache")
        p3.side_effect = AssertionError(
            "_get_risk_monitoring_data called despite cache"
        )
        p4.side_effect = AssertionError("_get_surveillance_status called despite cache")
        p5.side_effect = AssertionError(
            "_get_regulatory_compliance_status called despite cache"
        )
        p6.side_effect = AssertionError("_get_audit_trail_status called despite cache")
        p7.side_effect = AssertionError("_get_active_alerts called despite cache")
        p8.side_effect = AssertionError("_get_recent_breaches called despite cache")
        p9.side_effect = AssertionError("_get_trend_analysis called despite cache")

        second = await dashboard.get_real_time_dashboard_data()
        assert second == first


def test_calculate_overall_compliance_score_no_breaches(
    dashboard, risk_stats_base, regulatory_stats_base, surveillance_stats_base
):
    """When there are no breaches, risk component contributes full score."""
    score = dashboard._calculate_overall_compliance_score(
        risk_stats_base, regulatory_stats_base, surveillance_stats_base
    )
    assert 0.0 <= score <= 1.0
    # Expect score to be relatively high given minimal violations
    assert score > 0.8


def test_calculate_overall_compliance_score_zero_limits_boundary(
    dashboard, risk_stats_base, regulatory_stats_base, surveillance_stats_base
):
    """Boundary: active_limits=0 with breaches should not divide by zero and clamp to [0,1]."""
    risk_stats = dict(risk_stats_base)
    risk_stats["enforcement_metrics"] = {
        "total_breaches_detected": 5,
        "active_breaches": 5,
    }
    risk_stats["risk_limits"] = {"active_limits": 0}
    score = dashboard._calculate_overall_compliance_score(
        risk_stats, regulatory_stats_base, surveillance_stats_base
    )
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_get_risk_monitoring_data_aggregates_expected_fields(
    dashboard, mock_dependencies, risk_stats_base
):
    """Risk monitoring returns expected sections including utilization and trend data."""
    with (
        patch.object(
            dashboard,
            "_calculate_limit_utilization",
            AsyncMock(return_value={"portfolio_notional": 0.75}),
        ),
        patch.object(
            dashboard,
            "_get_risk_trend_data",
            AsyncMock(return_value=[{"timestamp": "t", "risk_score": 0.95}]),
        ),
    ):
        data = await dashboard._get_risk_monitoring_data()
    assert (
        "monitoring_status" in data and data["monitoring_status"]["is_active"] is True
    )
    assert (
        "limit_utilization" in data
        and data["limit_utilization"]["portfolio_notional"] == 0.75
    )
    assert "risk_trend_data" in data and len(data["risk_trend_data"]) == 1


def test_determine_alert_severity_mapping_and_default(dashboard):
    """Severity is mapped from enforcement action value; unknown maps to medium."""
    critical = SimpleNamespace(value="suspend_trading")
    low = SimpleNamespace(value="alert_only")
    unknown = SimpleNamespace(value="something_else")
    assert dashboard._determine_alert_severity(critical) == "critical"
    assert dashboard._determine_alert_severity(low) == "low"
    assert dashboard._determine_alert_severity(unknown) == "medium"


def test_get_severity_priority_ordering(dashboard):
    """Priority ordering maps critical>high>medium>low properly."""
    assert dashboard._get_severity_priority(
        "critical"
    ) > dashboard._get_severity_priority("high")
    assert dashboard._get_severity_priority("high") > dashboard._get_severity_priority(
        "medium"
    )
    assert dashboard._get_severity_priority(
        "medium"
    ) > dashboard._get_severity_priority("low")


@pytest.mark.asyncio
async def test_get_active_alerts_merges_risk_and_regulatory_sorted(
    dashboard, mock_dependencies
):
    """Active alerts include risk breaches and regulatory breaches, sorted by severity/time."""
    risk = mock_dependencies["risk"]
    reg = mock_dependencies["reg"]

    # Create breaches with varying severities and timestamps
    now = datetime.now(timezone.utc)
    Breach = SimpleNamespace  # simple holder for attributes

    risk_breach_high = SimpleNamespace(
        breach_id="RB1",
        enforcement_action_taken=SimpleNamespace(value="force_reduce_position"),
        breach_type=SimpleNamespace(value="POSITION_LIMIT"),
        detected_at=now - timedelta(minutes=10),
        remediation_completed=False,
        breach_magnitude=12.3,
        affected_positions=["A"],
        enforcement_action_taken_value="force_reduce_position",
    )

    risk.active_breaches = {"RB1": risk_breach_high}

    regulatory_breach_critical = SimpleNamespace(
        alert_id="REG1",
        severity=SimpleNamespace(value="critical"),
        description="Late report",
        detected_at=now - timedelta(minutes=5),
        remediation_required=True,
        deadline=now + timedelta(days=1),
    )
    reg.regulatory_breaches = {"REG1": regulatory_breach_critical}

    alerts = await dashboard._get_active_alerts()
    assert any(a["type"] == "risk_limit_breach" for a in alerts)
    assert any(a["type"] == "regulatory_breach" for a in alerts)
    # First should be critical regulatory given sort by severity then time
    assert alerts[0]["severity"] in ("critical", "high")


@pytest.mark.asyncio
async def test_get_recent_breaches_summarizes_active_breaches(
    dashboard, mock_dependencies
):
    """Recent breaches summarization returns last entries from active risk breaches."""
    risk = mock_dependencies["risk"]
    now = datetime.now(timezone.utc)
    breach = SimpleNamespace(
        breach_id="RB2",
        breach_type=SimpleNamespace(value="LEVERAGE_LIMIT"),
        breach_magnitude=7.8,
        detected_at=now,
        remediation_completed=False,
        enforcement_action_taken=SimpleNamespace(value="block_new_positions"),
        affected_positions=["X"],
    )
    risk.active_breaches = {"RB2": breach}
    breaches = await dashboard._get_recent_breaches()
    assert len(breaches) == 1
    assert breaches[0]["type"] == "risk_limit"
    assert breaches[0]["enforcement_action"] == "block_new_positions"


def test_calculate_combined_integrity_score_with_and_without_regulatory(dashboard):
    """Combined integrity returns risk-only when regulatory not available, else averages."""
    risk_only = {"integrity_percentage": 98.0}
    regulatory_na = {"status": "not_available"}
    combined = dashboard._calculate_combined_integrity_score(risk_only, regulatory_na)
    assert combined == pytest.approx(0.98)

    regulatory = {"integrity_percentage": 96.0}
    combined2 = dashboard._calculate_combined_integrity_score(risk_only, regulatory)
    assert combined2 == pytest.approx((0.98 + 0.96) / 2)


@pytest.mark.asyncio
async def test_calculate_metric_trend_returns_expected_shape(dashboard):
    """Trend calculation returns 24 data points and stable direction."""
    trend = await dashboard._calculate_metric_trend(
        ComplianceMetricType.RISK_COMPLIANCE, DashboardTimeframe.WEEKLY
    )
    assert isinstance(trend, ComplianceTrend)
    assert len(trend.data_points) == 24
    assert trend.trend_analysis.get("direction") == "stable"


@pytest.mark.asyncio
async def test_generate_compliance_report_structure(dashboard):
    """Compliance report contains required sections and optional charts flag works."""
    # Speed up by stubbing nested calls used in report
    with (
        patch.object(
            dashboard,
            "_generate_executive_summary",
            AsyncMock(return_value={"summary": "ok"}),
        ),
        patch.object(
            dashboard, "_get_detailed_metrics", AsyncMock(return_value={"details": 1})
        ),
        patch.object(
            dashboard, "_get_risk_analysis", AsyncMock(return_value={"risk": 1})
        ),
        patch.object(
            dashboard, "_get_surveillance_analysis", AsyncMock(return_value={"surv": 1})
        ),
        patch.object(
            dashboard, "_get_regulatory_status", AsyncMock(return_value={"reg": 1})
        ),
        patch.object(
            dashboard, "_generate_recommendations", AsyncMock(return_value=[{"rec": 1}])
        ),
        patch.object(
            dashboard,
            "_generate_compliance_charts",
            AsyncMock(return_value={"chart": "x"}),
        ),
    ):
        rep_no_charts = await dashboard.generate_compliance_report(
            DashboardTimeframe.DAILY, include_charts=False
        )
        assert "charts" not in rep_no_charts
        rep_charts = await dashboard.generate_compliance_report(
            DashboardTimeframe.DAILY, include_charts=True
        )
        assert "charts" in rep_charts
        assert (
            rep_charts["report_metadata"]["timeframe"] == DashboardTimeframe.DAILY.value
        )


@pytest.mark.asyncio
async def test_create_interactive_dashboard_returns_enhanced_html(dashboard):
    """Interactive dashboard returns HTML with injected real-time update script."""
    with (
        patch.object(
            dashboard,
            "get_real_time_dashboard_data",
            AsyncMock(
                return_value={
                    "kpis": {"risk_compliance_score": {"current_value": 0.99}}
                }
            ),
        ),
        patch(
            "fxml4.compliance.analytics.compliance_dashboard.make_subplots"
        ) as p_make,
    ):
        mock_fig = MagicMock()
        mock_fig.to_html.return_value = "<html><body></body></html>"
        p_make.return_value = mock_fig
        html = await dashboard.create_interactive_dashboard()
        assert "<script>" in html and "Dashboard update check" in html


@pytest.mark.asyncio
async def test_start_and_stop_real_time_updates_lifecycle(dashboard):
    """Real-time update task is created and then cancelled on stop."""
    mock_task = MagicMock()

    with patch(
        "fxml4.compliance.analytics.compliance_dashboard.asyncio.create_task",
        return_value=mock_task,
    ) as p_ct:
        await dashboard.start_real_time_updates()
        assert dashboard._update_task is mock_task
        mock_task.cancel.assert_not_called()

        await dashboard.stop_real_time_updates()
        mock_task.cancel.assert_called_once()
        assert dashboard._update_task is None


@pytest.mark.asyncio
async def test_get_compliance_dashboard_returns_global_instance():
    """Accessor returns the same global dashboard instance."""
    inst = await get_compliance_dashboard()
    assert inst is compliance_dashboard
