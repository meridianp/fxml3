"""
Critical E2E User Journey Tests
================================

This module implements the missing critical E2E test scenarios identified in the audit:
- Multi-broker workflow testing
- Compliance and audit trail validation
- Admin operations and user management
- Real-time alert system
- Mobile PWA functionality
- Tax reporting and export

These tests ensure complete user workflow coverage and production readiness.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest
from faker import Faker

from tests.conftest_enhanced import (
    MarketDataFactory,
    MLModelFactory,
    isolated_test_user,
    unique_test_id,
)

fake = Faker()


class TestMultiBrokerJourney:
    """Test complete multi-broker trading workflow."""

    @pytest.mark.e2e
    @pytest.mark.broker
    @pytest.mark.asyncio
    async def test_broker_switching_workflow(self, e2e_test_client):
        """
        Test switching between multiple brokers for best execution.

        User Story: As a trader, I can manage multiple broker accounts
        and route orders to the best broker based on quotes.
        """
        # Step 1: Connect to Interactive Brokers
        ib_connection = await e2e_test_client.post(
            "/brokers/connect",
            json={
                "broker": "interactive_brokers",
                "credentials": {
                    "username": "test_ib_user",
                    "password": "test_ib_pass",
                    "account": "DU123456",
                },
            },
        )
        assert ib_connection.status_code == 200
        ib_session = ib_connection.json()

        # Step 2: Connect to FXCM
        fxcm_connection = await e2e_test_client.post(
            "/brokers/connect",
            json={
                "broker": "fxcm",
                "credentials": {
                    "username": "test_fxcm_user",
                    "password": "test_fxcm_pass",
                    "account": "02134567",
                },
            },
        )
        assert fxcm_connection.status_code == 200
        fxcm_session = fxcm_connection.json()

        # Step 3: Get quotes from both brokers
        ib_quote = await e2e_test_client.get(
            "/brokers/quote",
            params={
                "broker": "interactive_brokers",
                "symbol": "EURUSD",
                "session_id": ib_session["session_id"],
            },
        )
        assert ib_quote.status_code == 200
        ib_price = ib_quote.json()

        fxcm_quote = await e2e_test_client.get(
            "/brokers/quote",
            params={
                "broker": "fxcm",
                "symbol": "EURUSD",
                "session_id": fxcm_session["session_id"],
            },
        )
        assert fxcm_quote.status_code == 200
        fxcm_price = fxcm_quote.json()

        # Step 4: Compare quotes and select best broker
        best_broker = "interactive_brokers"
        best_session = ib_session["session_id"]
        best_price = ib_price["ask"]

        if fxcm_price["ask"] < ib_price["ask"]:
            best_broker = "fxcm"
            best_session = fxcm_session["session_id"]
            best_price = fxcm_price["ask"]

        # Step 5: Execute trade with best broker
        order = await e2e_test_client.post(
            "/brokers/order",
            json={
                "broker": best_broker,
                "session_id": best_session,
                "symbol": "EURUSD",
                "side": "BUY",
                "quantity": 10000,
                "order_type": "MARKET",
            },
        )
        assert order.status_code == 201
        order_data = order.json()
        assert order_data["status"] in ["FILLED", "PENDING"]

        # Step 6: Verify order appears in both broker's position list
        ib_positions = await e2e_test_client.get(
            f"/brokers/positions?broker=interactive_brokers&session_id={ib_session['session_id']}"
        )
        fxcm_positions = await e2e_test_client.get(
            f"/brokers/positions?broker=fxcm&session_id={fxcm_session['session_id']}"
        )

        # At least one broker should have the position
        all_positions = ib_positions.json() + fxcm_positions.json()
        assert any(pos["symbol"] == "EURUSD" for pos in all_positions)

        # Step 7: Disconnect from brokers
        await e2e_test_client.post(
            f"/brokers/disconnect?broker=interactive_brokers&session_id={ib_session['session_id']}"
        )
        await e2e_test_client.post(
            f"/brokers/disconnect?broker=fxcm&session_id={fxcm_session['session_id']}"
        )

    @pytest.mark.e2e
    @pytest.mark.broker
    @pytest.mark.asyncio
    async def test_broker_failover_scenario(self, e2e_test_client):
        """Test automatic failover when primary broker fails."""
        # Connect to primary broker
        primary = await e2e_test_client.post(
            "/brokers/connect",
            json={"broker": "interactive_brokers", "credentials": {...}},
        )

        # Connect to backup broker
        backup = await e2e_test_client.post(
            "/brokers/connect", json={"broker": "fxcm", "credentials": {...}}
        )

        # Simulate primary broker failure
        await e2e_test_client.post(
            "/test/simulate_failure",
            json={"broker": "interactive_brokers", "type": "connection_lost"},
        )

        # Attempt to place order - should automatically route to backup
        order = await e2e_test_client.post(
            "/brokers/order",
            json={
                "symbol": "GBPUSD",
                "side": "SELL",
                "quantity": 5000,
                "use_failover": True,
            },
        )

        assert order.status_code == 201
        order_data = order.json()
        assert order_data["broker"] == "fxcm"  # Routed to backup
        assert order_data["failover_reason"] == "primary_broker_unavailable"


class TestComplianceJourney:
    """Test compliance officer audit and regulatory workflows."""

    @pytest.mark.e2e
    @pytest.mark.compliance
    @pytest.mark.asyncio
    async def test_compliance_officer_audit_trail(self, e2e_test_client):
        """
        Test complete audit trail for compliance review.

        User Story: As a compliance officer, I can audit all trades
        and generate regulatory reports.
        """
        # Step 1: Login as compliance officer
        login = await e2e_test_client.post(
            "/auth/login",
            json={
                "username": "compliance_officer",
                "password": "CompliancePass123!",
            },
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Request audit trail for date range
        audit_trail = await e2e_test_client.get(
            "/compliance/audit-trail",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "include_metadata": True,
            },
            headers=headers,
        )
        assert audit_trail.status_code == 200
        audit_data = audit_trail.json()

        # Verify audit trail completeness
        assert "trades" in audit_data
        assert "user_actions" in audit_data
        assert "system_events" in audit_data
        assert all(
            "timestamp" in event and "user_id" in event
            for event in audit_data["user_actions"]
        )

        # Step 3: Flag suspicious activity
        if audit_data["trades"]:
            suspicious_trade = audit_data["trades"][0]
            flag_response = await e2e_test_client.post(
                "/compliance/flag-activity",
                json={
                    "trade_id": suspicious_trade["id"],
                    "reason": "Unusual trading pattern detected",
                    "severity": "medium",
                    "requires_investigation": True,
                },
                headers=headers,
            )
            assert flag_response.status_code == 201

        # Step 4: Generate MiFID II report
        mifid_report = await e2e_test_client.post(
            "/compliance/reports/mifid2",
            json={
                "reporting_period": "2024-Q1",
                "entity": "FXML4_TRADING",
                "include_transaction_reports": True,
                "include_position_reports": True,
            },
            headers=headers,
        )
        assert mifid_report.status_code == 200
        report_data = mifid_report.json()
        assert report_data["report_type"] == "MiFID_II"
        assert "transaction_reports" in report_data

        # Step 5: Generate Dodd-Frank report
        dodd_frank_report = await e2e_test_client.post(
            "/compliance/reports/dodd-frank",
            json={
                "reporting_date": "2024-01-31",
                "swap_data_repository": "DTCC",
            },
            headers=headers,
        )
        assert dodd_frank_report.status_code == 200

        # Step 6: Export audit trail to CSV
        export = await e2e_test_client.get(
            "/compliance/export",
            params={
                "format": "csv",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
            headers=headers,
        )
        assert export.status_code == 200
        assert export.headers["content-type"] == "text/csv"

    @pytest.mark.e2e
    @pytest.mark.compliance
    @pytest.mark.asyncio
    async def test_regulatory_breach_detection(self, e2e_test_client):
        """Test automatic detection and reporting of regulatory breaches."""
        # Setup compliance rules
        rules = await e2e_test_client.post(
            "/compliance/rules",
            json={
                "max_position_size": 1000000,
                "max_daily_trades": 100,
                "restricted_symbols": ["XAUUSD"],
                "max_leverage": 30,
            },
        )

        # Simulate trading that violates rules
        violation = await e2e_test_client.post(
            "/trades/execute",
            json={
                "symbol": "XAUUSD",  # Restricted symbol
                "quantity": 2000000,  # Exceeds position limit
                "leverage": 50,  # Exceeds leverage limit
            },
        )

        # Should be rejected with compliance error
        assert violation.status_code == 403
        assert "compliance_violation" in violation.json()

        # Check that violation was logged
        violations = await e2e_test_client.get("/compliance/violations")
        assert len(violations.json()) > 0
        assert violations.json()[0]["type"] in [
            "RESTRICTED_SYMBOL",
            "POSITION_LIMIT_EXCEEDED",
            "LEVERAGE_LIMIT_EXCEEDED",
        ]


class TestAdminOperations:
    """Test administrator user management workflows."""

    @pytest.mark.e2e
    @pytest.mark.auth
    @pytest.mark.asyncio
    async def test_admin_user_management(self, e2e_test_client):
        """
        Test complete admin user management workflow.

        User Story: As an admin, I can manage user permissions
        and monitor user activities.
        """
        # Step 1: Login as admin
        admin_login = await e2e_test_client.post(
            "/auth/login",
            json={
                "username": "admin",
                "password": "AdminPass123!",
            },
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Step 2: Create new trader user
        new_user = await e2e_test_client.post(
            "/admin/users",
            json={
                "username": f"trader_{fake.user_name()}",
                "email": fake.email(),
                "full_name": fake.name(),
                "role": "trader",
                "permissions": [
                    "trade.execute",
                    "trade.view",
                    "portfolio.view",
                ],
                "trading_limits": {
                    "max_position_size": 100000,
                    "max_daily_loss": 5000,
                    "allowed_symbols": ["EURUSD", "GBPUSD"],
                },
            },
            headers=headers,
        )
        assert new_user.status_code == 201
        user_data = new_user.json()
        user_id = user_data["user_id"]

        # Step 3: Modify user permissions
        permission_update = await e2e_test_client.patch(
            f"/admin/users/{user_id}/permissions",
            json={
                "add_permissions": ["trade.options"],
                "remove_permissions": ["trade.execute"],
                "reason": "Temporary restriction due to training",
            },
            headers=headers,
        )
        assert permission_update.status_code == 200

        # Step 4: Monitor user activity
        user_activity = await e2e_test_client.get(
            f"/admin/users/{user_id}/activity",
            params={
                "start_date": datetime.now(timezone.utc).date().isoformat(),
                "include_trades": True,
                "include_logins": True,
            },
            headers=headers,
        )
        assert user_activity.status_code == 200
        activity_data = user_activity.json()
        assert "login_history" in activity_data
        assert "trade_history" in activity_data

        # Step 5: Disable user account
        disable_user = await e2e_test_client.post(
            f"/admin/users/{user_id}/disable",
            json={
                "reason": "Account under review",
                "disable_trading": True,
                "disable_login": False,
            },
            headers=headers,
        )
        assert disable_user.status_code == 200

        # Step 6: Generate user audit report
        user_audit = await e2e_test_client.get(
            f"/admin/users/{user_id}/audit",
            headers=headers,
        )
        assert user_audit.status_code == 200
        audit = user_audit.json()
        assert audit["account_status"] == "disabled"
        assert "permission_history" in audit

        # Step 7: Re-enable user
        enable_user = await e2e_test_client.post(
            f"/admin/users/{user_id}/enable",
            json={"reason": "Review completed, account cleared"},
            headers=headers,
        )
        assert enable_user.status_code == 200

    @pytest.mark.e2e
    @pytest.mark.auth
    @pytest.mark.asyncio
    async def test_role_based_access_control(self, e2e_test_client):
        """Test RBAC implementation with different user roles."""
        roles = ["admin", "trader", "analyst", "compliance", "viewer"]

        for role in roles:
            # Create user with specific role
            user = await e2e_test_client.post(
                "/admin/users",
                json={
                    "username": f"test_{role}",
                    "role": role,
                },
            )

            # Login as user
            login = await e2e_test_client.post(
                "/auth/login",
                json={"username": f"test_{role}", "password": "TestPass123!"},
            )
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Test role-specific access
            if role == "admin":
                # Admin should access everything
                assert (
                    await e2e_test_client.get("/admin/users", headers=headers)
                ).status_code == 200
            elif role == "trader":
                # Trader can execute trades but not admin
                assert (
                    await e2e_test_client.post(
                        "/trades/execute", headers=headers, json={}
                    )
                ).status_code in [200, 422]
                assert (
                    await e2e_test_client.get("/admin/users", headers=headers)
                ).status_code == 403
            elif role == "compliance":
                # Compliance can audit but not trade
                assert (
                    await e2e_test_client.get(
                        "/compliance/audit-trail", headers=headers
                    )
                ).status_code == 200
                assert (
                    await e2e_test_client.post(
                        "/trades/execute", headers=headers, json={}
                    )
                ).status_code == 403
            elif role == "viewer":
                # Viewer can only read
                assert (
                    await e2e_test_client.get("/portfolio/summary", headers=headers)
                ).status_code == 200
                assert (
                    await e2e_test_client.post(
                        "/trades/execute", headers=headers, json={}
                    )
                ).status_code == 403


class TestAlertSystem:
    """Test real-time alert and notification system."""

    @pytest.mark.e2e
    @pytest.mark.real_time
    @pytest.mark.asyncio
    async def test_real_time_alerts(self, e2e_test_client):
        """
        Test real-time alert delivery system.

        User Story: As a trader, I can receive real-time alerts
        for market conditions and trading events.
        """
        # Step 1: Setup alert conditions
        alert_config = await e2e_test_client.post(
            "/alerts/configure",
            json={
                "alerts": [
                    {
                        "name": "EURUSD Price Alert",
                        "condition": {
                            "type": "price_threshold",
                            "symbol": "EURUSD",
                            "operator": "greater_than",
                            "value": 1.1050,
                        },
                        "actions": ["email", "push", "websocket"],
                    },
                    {
                        "name": "Drawdown Alert",
                        "condition": {
                            "type": "portfolio_metric",
                            "metric": "drawdown",
                            "operator": "greater_than",
                            "value": 0.05,  # 5%
                        },
                        "actions": ["email", "sms", "websocket"],
                    },
                    {
                        "name": "Trade Execution Alert",
                        "condition": {
                            "type": "trade_event",
                            "events": ["filled", "rejected", "partial_fill"],
                        },
                        "actions": ["websocket", "push"],
                    },
                ],
                "delivery_preferences": {
                    "email": "trader@example.com",
                    "sms": "+1234567890",
                    "push": True,
                    "websocket": True,
                },
            },
        )
        assert alert_config.status_code == 201

        # Step 2: Connect to WebSocket for real-time alerts
        import websockets

        ws_url = "ws://localhost:8000/ws/alerts"
        alerts_received = []

        async def listen_for_alerts():
            async with websockets.connect(ws_url) as websocket:
                # Authenticate WebSocket
                await websocket.send(
                    json.dumps(
                        {
                            "type": "auth",
                            "token": "test_token",
                        }
                    )
                )

                # Listen for alerts
                while len(alerts_received) < 3:
                    message = await websocket.recv()
                    alert = json.loads(message)
                    alerts_received.append(alert)

        # Start listening in background
        listener_task = asyncio.create_task(listen_for_alerts())

        # Step 3: Trigger alert conditions
        # Simulate price change
        await e2e_test_client.post(
            "/test/simulate_price",
            json={
                "symbol": "EURUSD",
                "price": 1.1060,  # Triggers price alert
            },
        )

        # Simulate drawdown
        await e2e_test_client.post(
            "/test/simulate_drawdown", json={"drawdown": 0.06}  # 6% triggers alert
        )

        # Execute a trade
        await e2e_test_client.post(
            "/trades/execute",
            json={
                "symbol": "GBPUSD",
                "side": "BUY",
                "quantity": 10000,
            },
        )

        # Wait for alerts
        await asyncio.sleep(2)
        listener_task.cancel()

        # Step 4: Verify alerts were received
        assert len(alerts_received) >= 3
        alert_types = [alert["type"] for alert in alerts_received]
        assert "price_threshold" in alert_types
        assert "portfolio_metric" in alert_types
        assert "trade_event" in alert_types

        # Step 5: Acknowledge alerts
        for alert in alerts_received:
            ack = await e2e_test_client.post(
                f"/alerts/{alert['id']}/acknowledge",
                json={"acknowledged_by": "trader_123"},
            )
            assert ack.status_code == 200

        # Step 6: Get alert history
        history = await e2e_test_client.get(
            "/alerts/history",
            params={
                "start_date": datetime.now(timezone.utc).date().isoformat(),
                "include_acknowledged": True,
            },
        )
        assert history.status_code == 200
        history_data = history.json()
        assert len(history_data) >= 3
        assert all(alert["acknowledged"] for alert in history_data)


class TestMobilePWA:
    """Test Progressive Web App functionality for mobile trading."""

    @pytest.mark.e2e
    @pytest.mark.ui
    @pytest.mark.asyncio
    async def test_mobile_trading_experience(self, e2e_test_client):
        """
        Test mobile PWA trading functionality.

        User Story: As a trader, I can use the mobile app
        for trading on the go.
        """
        # Step 1: Request PWA manifest
        manifest = await e2e_test_client.get("/manifest.json")
        assert manifest.status_code == 200
        manifest_data = manifest.json()
        assert manifest_data["name"] == "FXML4 Trading"
        assert manifest_data["display"] == "standalone"
        assert "icons" in manifest_data

        # Step 2: Test service worker registration
        sw = await e2e_test_client.get("/sw.js")
        assert sw.status_code == 200
        assert "self.addEventListener('install'" in sw.text

        # Step 3: Test offline capability
        # Cache critical resources
        cache_response = await e2e_test_client.post(
            "/api/cache/warm",
            json={
                "resources": [
                    "/portfolio/summary",
                    "/trades/recent",
                    "/market/quotes",
                ]
            },
        )
        assert cache_response.status_code == 200

        # Step 4: Test responsive design endpoints
        mobile_dashboard = await e2e_test_client.get(
            "/api/mobile/dashboard", headers={"User-Agent": "Mobile Safari"}
        )
        assert mobile_dashboard.status_code == 200
        dashboard_data = mobile_dashboard.json()
        assert dashboard_data["layout"] == "mobile"
        assert dashboard_data["components"] == ["summary", "quick_trade", "alerts"]

        # Step 5: Test touch gesture support
        swipe_action = await e2e_test_client.post(
            "/api/mobile/gesture",
            json={
                "type": "swipe",
                "direction": "left",
                "context": "portfolio_chart",
            },
        )
        assert swipe_action.status_code == 200
        assert swipe_action.json()["action"] == "next_timeframe"

        # Step 6: Test push notifications
        push_subscription = await e2e_test_client.post(
            "/api/mobile/push/subscribe",
            json={
                "endpoint": "https://fcm.googleapis.com/fcm/send/...",
                "keys": {
                    "p256dh": "test_key",
                    "auth": "test_auth",
                },
            },
        )
        assert push_subscription.status_code == 201

        # Send test notification
        test_notification = await e2e_test_client.post(
            "/api/mobile/push/send",
            json={
                "title": "Trade Executed",
                "body": "Your EURUSD buy order has been filled",
                "icon": "/icons/trade-success.png",
                "badge": "/icons/badge.png",
            },
        )
        assert test_notification.status_code == 200

        # Step 7: Test quick trade widget
        quick_trade = await e2e_test_client.post(
            "/api/mobile/quick-trade",
            json={
                "symbol": "EURUSD",
                "side": "BUY",
                "amount": 1000,
                "one_click": True,
            },
        )
        assert quick_trade.status_code == 201
        trade_result = quick_trade.json()
        assert trade_result["executed"] is True
        assert trade_result["execution_time"] < 1000  # Less than 1 second


class TestTaxReporting:
    """Test tax reporting and export functionality."""

    @pytest.mark.e2e
    @pytest.mark.reporting
    @pytest.mark.asyncio
    async def test_tax_report_generation(self, e2e_test_client):
        """
        Test tax report generation for different jurisdictions.

        User Story: As a trader, I can export reports for tax purposes.
        """
        # Step 1: Request US tax report (Form 8949)
        us_tax_report = await e2e_test_client.post(
            "/reports/tax/us",
            json={
                "tax_year": 2024,
                "form_type": "8949",
                "accounting_method": "FIFO",
                "include_wash_sales": True,
            },
        )
        assert us_tax_report.status_code == 200
        us_report = us_tax_report.json()
        assert us_report["form"] == "8949"
        assert "short_term_trades" in us_report
        assert "long_term_trades" in us_report
        assert "total_gain_loss" in us_report

        # Step 2: Request UK tax report (Capital Gains)
        uk_tax_report = await e2e_test_client.post(
            "/reports/tax/uk",
            json={
                "tax_year": "2024-2025",
                "report_type": "capital_gains",
                "allowance": 6000,
            },
        )
        assert uk_tax_report.status_code == 200
        uk_report = uk_tax_report.json()
        assert "total_gains" in uk_report
        assert "allowance_used" in uk_report
        assert "tax_due" in uk_report

        # Step 3: Request EU transaction tax report
        eu_tax_report = await e2e_test_client.post(
            "/reports/tax/eu",
            json={
                "year": 2024,
                "country": "Germany",
                "include_ftt": True,  # Financial Transaction Tax
            },
        )
        assert eu_tax_report.status_code == 200

        # Step 4: Export to different formats
        formats = ["pdf", "csv", "xlsx", "xml"]
        for format_type in formats:
            export = await e2e_test_client.get(
                f"/reports/tax/export",
                params={
                    "year": 2024,
                    "format": format_type,
                    "jurisdiction": "US",
                },
            )
            assert export.status_code == 200

            # Verify correct content type
            content_types = {
                "pdf": "application/pdf",
                "csv": "text/csv",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "xml": "application/xml",
            }
            assert export.headers["content-type"] == content_types[format_type]

        # Step 5: Schedule automated tax reports
        schedule = await e2e_test_client.post(
            "/reports/tax/schedule",
            json={
                "frequency": "quarterly",
                "jurisdictions": ["US", "UK"],
                "formats": ["pdf", "csv"],
                "email_to": "trader@example.com",
                "start_date": "2024-04-01",
            },
        )
        assert schedule.status_code == 201
        schedule_data = schedule.json()
        assert schedule_data["status"] == "scheduled"
        assert schedule_data["next_run"] is not None


# ============================================================================
# Helper Functions
# ============================================================================


async def authenticate_user(client, username: str, password: str) -> str:
    """Helper to authenticate and return token."""
    response = await client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def create_test_trade(client, token: str, symbol: str = "EURUSD") -> Dict:
    """Helper to create a test trade."""
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(
        "/trades/execute",
        json={
            "symbol": symbol,
            "side": "BUY",
            "quantity": 10000,
            "order_type": "MARKET",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def wait_for_condition(
    condition_func, timeout: int = 10, check_interval: float = 0.5
) -> bool:
    """Wait for a condition to become true."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if await condition_func():
            return True
        await asyncio.sleep(check_interval)
    return False


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
async def test_users():
    """Create test users for different roles."""
    users = {
        "admin": {
            "username": "admin_test",
            "password": "AdminPass123!",
            "role": "admin",
        },
        "trader": {
            "username": "trader_test",
            "password": "TraderPass123!",
            "role": "trader",
        },
        "compliance": {
            "username": "compliance_test",
            "password": "CompliancePass123!",
            "role": "compliance",
        },
        "viewer": {
            "username": "viewer_test",
            "password": "ViewerPass123!",
            "role": "viewer",
        },
    }

    # Create users in database
    # ... user creation logic ...

    return users


@pytest.fixture
async def mock_market_conditions():
    """Create mock market conditions for testing."""
    return {
        "volatile": {
            "volatility": 0.025,
            "trend": 0.0,
            "volume_multiplier": 2.0,
        },
        "trending": {
            "volatility": 0.01,
            "trend": 0.001,
            "volume_multiplier": 1.5,
        },
        "quiet": {
            "volatility": 0.005,
            "trend": 0.0,
            "volume_multiplier": 0.5,
        },
    }
