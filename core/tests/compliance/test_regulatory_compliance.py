"""
TDD Tests for Regulatory Compliance and Audit

Comprehensive test suite for regulatory compliance features including
audit trails, reporting requirements, and regulatory limits.
"""

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest


@pytest.mark.tdd
@pytest.mark.compliance
class TestRegulatoryCompliance:
    """
    Test suite for regulatory compliance and audit requirements.

    Tests audit trail generation, regulatory reporting, compliance validation,
    and data retention requirements for financial trading systems.
    """

    @pytest.fixture
    def compliance_config(self):
        """Regulatory compliance configuration."""
        return {
            "jurisdictions": ["US", "EU", "UK"],
            "reporting_thresholds": {
                "position_size_usd": 1000000,  # $1M position reporting
                "daily_volume_usd": 5000000,  # $5M daily volume reporting
                "leverage_ratio": 30,  # 30:1 leverage reporting
                "concentration_limit": 0.10,  # 10% concentration limit
            },
            "audit_requirements": {
                "retention_period_days": 2555,  # 7 years
                "audit_trail_completeness": True,
                "transaction_integrity": True,
                "user_access_logging": True,
            },
            "mifid_ii_requirements": {
                "best_execution": True,
                "transaction_reporting": True,
                "clock_synchronization": True,
                "record_keeping": True,
            },
            "dodd_frank_requirements": {
                "swap_reporting": True,
                "margin_requirements": True,
                "position_limits": True,
                "risk_management": True,
            },
        }

    @pytest.fixture
    def sample_trading_data(self):
        """Sample trading data for compliance testing."""
        return {
            "trades": [
                {
                    "trade_id": "TRD_001",
                    "symbol": "EUR/USD",
                    "side": "BUY",
                    "quantity": 1500000,
                    "price": 1.0850,
                    "timestamp": datetime(2024, 1, 15, 10, 30, 45, 123456),
                    "user_id": "TRADER_001",
                    "strategy": "MOMENTUM_v2.1",
                    "venue": "IB_IDEALPRO",
                },
                {
                    "trade_id": "TRD_002",
                    "symbol": "GBP/USD",
                    "side": "SELL",
                    "quantity": 2000000,
                    "price": 1.2500,
                    "timestamp": datetime(2024, 1, 15, 14, 45, 12, 987654),
                    "user_id": "TRADER_002",
                    "strategy": "ARBITRAGE_v1.5",
                    "venue": "IB_IDEALPRO",
                },
            ],
            "positions": [
                {
                    "position_id": "POS_001",
                    "symbol": "EUR/USD",
                    "quantity": 5000000,
                    "avg_price": 1.0845,
                    "market_value": 5422500,
                    "unrealized_pnl": 25000,
                    "open_date": datetime(2024, 1, 10),
                }
            ],
            "orders": [
                {
                    "order_id": "ORD_001",
                    "symbol": "USD/JPY",
                    "side": "BUY",
                    "quantity": 3000000,
                    "order_type": "LIMIT",
                    "limit_price": 110.50,
                    "status": "PENDING",
                    "timestamp": datetime(2024, 1, 15, 16, 20, 30),
                }
            ],
        }

    @pytest.fixture
    def compliance_engine(self, compliance_config):
        """Create compliance engine instance."""
        from core.compliance.compliance_engine import ComplianceEngine

        return ComplianceEngine(config=compliance_config)

    # -------------------------------------------------------------------------
    # Audit Trail Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_comprehensive_audit_trail_generation(
        self, compliance_engine, sample_trading_data
    ):
        """RED: Test comprehensive audit trail generation for all activities."""
        trade = sample_trading_data["trades"][0]

        # Generate audit events for trade lifecycle
        audit_events = [
            {
                "event_type": "SIGNAL_GENERATED",
                "timestamp": trade["timestamp"] - timedelta(seconds=5),
                "details": {"signal_strength": 0.85, "strategy": trade["strategy"]},
            },
            {
                "event_type": "RISK_VALIDATION",
                "timestamp": trade["timestamp"] - timedelta(seconds=3),
                "details": {"risk_score": 0.25, "approved": True},
            },
            {
                "event_type": "ORDER_SUBMITTED",
                "timestamp": trade["timestamp"] - timedelta(seconds=1),
                "details": {"order_id": "ORD_001", "quantity": trade["quantity"]},
            },
            {
                "event_type": "TRADE_EXECUTED",
                "timestamp": trade["timestamp"],
                "details": trade,
            },
        ]

        # Record audit trail
        audit_trail_id = compliance_engine.create_audit_trail(
            trade_id=trade["trade_id"], events=audit_events, user_id=trade["user_id"]
        )

        # Verify audit trail completeness
        retrieved_trail = compliance_engine.get_audit_trail(audit_trail_id)

        assert len(retrieved_trail["events"]) == 4
        assert all(
            event["event_type"]
            in [
                "SIGNAL_GENERATED",
                "RISK_VALIDATION",
                "ORDER_SUBMITTED",
                "TRADE_EXECUTED",
            ]
            for event in retrieved_trail["events"]
        )

        # Verify audit trail integrity
        assert retrieved_trail["integrity_hash"] is not None
        assert retrieved_trail["chain_verified"] is True

        # Verify chronological order
        timestamps = [event["timestamp"] for event in retrieved_trail["events"]]
        assert timestamps == sorted(timestamps)

    @pytest.mark.red
    def test_audit_trail_integrity_validation(self, compliance_engine):
        """RED: Test audit trail integrity and tamper detection."""
        original_events = [
            {
                "event_type": "ORDER_SUBMITTED",
                "timestamp": datetime.now(),
                "details": {"order_id": "TEST_001", "quantity": 100000},
                "user_id": "TRADER_001",
            },
            {
                "event_type": "TRADE_EXECUTED",
                "timestamp": datetime.now(),
                "details": {"trade_id": "TRD_TEST_001", "price": 1.0850},
                "user_id": "TRADER_001",
            },
        ]

        # Create audit trail with integrity protection
        trail_id = compliance_engine.create_audit_trail(
            trade_id="TRD_TEST_001", events=original_events, user_id="TRADER_001"
        )

        # Verify original integrity
        original_trail = compliance_engine.get_audit_trail(trail_id)
        assert compliance_engine.verify_audit_trail_integrity(trail_id) is True

        # Simulate tampering attempt
        tampered_events = original_events.copy()
        tampered_events[1]["details"]["price"] = 1.0900  # Altered price

        # Attempt to update with tampered data should fail
        with pytest.raises(ValueError, match="Audit trail integrity violation"):
            compliance_engine.update_audit_trail(trail_id, tampered_events)

        # Verify original trail remains intact
        assert compliance_engine.verify_audit_trail_integrity(trail_id) is True

    @pytest.mark.red
    def test_audit_trail_search_and_filtering(
        self, compliance_engine, sample_trading_data
    ):
        """RED: Test audit trail search and filtering capabilities."""
        # Create multiple audit trails
        for i, trade in enumerate(sample_trading_data["trades"]):
            events = [
                {
                    "event_type": "TRADE_EXECUTED",
                    "timestamp": trade["timestamp"],
                    "details": trade,
                    "user_id": trade["user_id"],
                }
            ]

            compliance_engine.create_audit_trail(
                trade_id=trade["trade_id"], events=events, user_id=trade["user_id"]
            )

        # Search by user
        user_trails = compliance_engine.search_audit_trails(
            filters={"user_id": "TRADER_001"}
        )
        assert len(user_trails) >= 1
        assert all(trail["user_id"] == "TRADER_001" for trail in user_trails)

        # Search by date range
        date_trails = compliance_engine.search_audit_trails(
            filters={
                "start_date": datetime(2024, 1, 15),
                "end_date": datetime(2024, 1, 16),
            }
        )
        assert len(date_trails) >= 2

        # Search by symbol
        symbol_trails = compliance_engine.search_audit_trails(
            filters={"symbol": "EUR/USD"}
        )
        assert len(symbol_trails) >= 1

        # Complex search with multiple filters
        complex_trails = compliance_engine.search_audit_trails(
            filters={
                "user_id": "TRADER_001",
                "symbol": "EUR/USD",
                "event_type": "TRADE_EXECUTED",
            }
        )
        assert len(complex_trails) >= 1

    # -------------------------------------------------------------------------
    # Regulatory Reporting Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_large_position_reporting(self, compliance_engine, sample_trading_data):
        """RED: Test large position reporting requirements."""
        large_position = sample_trading_data["positions"][0]  # $5.4M position

        # Check if position requires reporting
        reporting_required = compliance_engine.check_position_reporting_requirement(
            position=large_position, jurisdiction="US"
        )

        assert reporting_required["required"] is True
        assert reporting_required["reason"] == "POSITION_SIZE_THRESHOLD_EXCEEDED"
        assert reporting_required["threshold_exceeded"] == "position_size_usd"

        # Generate regulatory report
        report = compliance_engine.generate_position_report(
            position=large_position, jurisdiction="US", report_type="LARGE_POSITION"
        )

        assert report["report_id"] is not None
        assert report["jurisdiction"] == "US"
        assert report["position_size_usd"] == 5422500
        assert report["reporting_entity"] is not None
        assert report["submission_deadline"] is not None

        # Verify report data integrity
        assert report["data_hash"] is not None
        calculated_hash = compliance_engine.calculate_position_report_hash(
            large_position
        )
        assert report["data_hash"] == calculated_hash

    @pytest.mark.red
    def test_daily_volume_reporting(self, compliance_engine, sample_trading_data):
        """RED: Test daily trading volume reporting."""
        # Simulate high daily volume
        daily_trades = []
        total_volume = 0

        for i in range(10):
            trade_volume = 800000  # $800k per trade
            total_volume += trade_volume

            daily_trades.append(
                {
                    "trade_id": f"HIGH_VOL_{i:03d}",
                    "symbol": "EUR/USD",
                    "quantity": trade_volume,
                    "price": 1.0850,
                    "notional_usd": trade_volume * 1.0850,
                    "timestamp": datetime(2024, 1, 15, 9 + i, 0, 0),
                }
            )

        # Check daily volume reporting requirement
        volume_report_required = compliance_engine.check_daily_volume_reporting(
            trades=daily_trades, date=datetime(2024, 1, 15).date(), jurisdiction="EU"
        )

        assert volume_report_required["required"] is True
        assert (
            volume_report_required["total_volume_usd"] > 5000000
        )  # Above $5M threshold

        # Generate daily volume report
        volume_report = compliance_engine.generate_daily_volume_report(
            trades=daily_trades, date=datetime(2024, 1, 15).date(), jurisdiction="EU"
        )

        assert volume_report["report_type"] == "DAILY_VOLUME"
        assert volume_report["total_trades"] == 10
        assert volume_report["total_volume_usd"] > 5000000
        assert volume_report["jurisdiction"] == "EU"

    @pytest.mark.red
    def test_mifid_ii_transaction_reporting(
        self, compliance_engine, sample_trading_data
    ):
        """RED: Test MiFID II transaction reporting requirements."""
        trade = sample_trading_data["trades"][0]

        # Check MiFID II reporting requirement
        mifid_required = compliance_engine.check_mifid_ii_requirement(
            trade=trade, jurisdiction="EU"
        )

        assert mifid_required["required"] is True
        assert mifid_required["regulation"] == "MIFID_II"

        # Generate MiFID II transaction report
        mifid_report = compliance_engine.generate_mifid_ii_report(
            trade=trade,
            additional_data={
                "trading_venue": "IB_IDEALPRO",
                "counterparty": "INTERACTIVE_BROKERS",
                "execution_algo": "NONE",
                "liquidity_provision": False,
            },
        )

        # Verify required MiFID II fields
        required_fields = [
            "trading_venue",
            "instrument_id",
            "price",
            "quantity",
            "currency",
            "trading_date",
            "trading_time",
            "buyer_id",
            "seller_id",
            "transaction_type",
            "publication_date",
        ]

        for field in required_fields:
            assert field in mifid_report["transaction_details"]

        # Verify timing requirements (T+1 reporting)
        trade_date = trade["timestamp"].date()
        expected_deadline = trade_date + timedelta(days=1)
        assert mifid_report["submission_deadline"].date() <= expected_deadline

    @pytest.mark.red
    def test_dodd_frank_swap_reporting(self, compliance_engine):
        """RED: Test Dodd-Frank swap reporting for applicable instruments."""
        # Create swap-like instrument trade
        swap_trade = {
            "trade_id": "SWAP_001",
            "instrument_type": "FX_SWAP",
            "symbol": "EUR/USD",
            "notional_amount": 10000000,  # $10M notional
            "maturity_date": datetime(2024, 7, 15),
            "counterparty": "BANK_COUNTERPARTY",
            "timestamp": datetime(2024, 1, 15),
            "jurisdiction": "US",
        }

        # Check Dodd-Frank reporting requirement
        dodd_frank_required = compliance_engine.check_dodd_frank_requirement(
            trade=swap_trade
        )

        assert dodd_frank_required["required"] is True
        assert dodd_frank_required["regulation"] == "DODD_FRANK"
        assert dodd_frank_required["reporting_party"] == "DEALER"

        # Generate Dodd-Frank swap report
        swap_report = compliance_engine.generate_dodd_frank_report(
            trade=swap_trade, reporting_counterparty="SELF"
        )

        # Verify required Dodd-Frank fields
        required_swap_fields = [
            "unique_swap_identifier",
            "original_dissemination_id",
            "counterparty_id",
            "notional_amount",
            "maturity_date",
            "effective_date",
            "trade_date",
            "asset_class",
        ]

        for field in required_swap_fields:
            assert field in swap_report["swap_details"]

        # Verify real-time reporting requirement (15 minutes)
        execution_time = swap_trade["timestamp"]
        submission_deadline = swap_report["submission_deadline"]
        time_diff = submission_deadline - execution_time
        assert time_diff <= timedelta(minutes=15)

    # -------------------------------------------------------------------------
    # Compliance Validation Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_position_limit_compliance(self, compliance_engine, sample_trading_data):
        """RED: Test position limit compliance validation."""
        # Define position limits
        position_limits = {
            "EUR/USD": {"max_position": 3000000, "max_concentration": 0.15},
            "GBP/USD": {"max_position": 2500000, "max_concentration": 0.12},
            "USD/JPY": {"max_position": 2000000, "max_concentration": 0.10},
        }

        compliance_engine.set_position_limits(position_limits)

        # Test compliant position
        compliant_position = {
            "symbol": "EUR/USD",
            "quantity": 2000000,  # Below 3M limit
            "portfolio_value": 20000000,  # 10% concentration
        }

        compliance_result = compliance_engine.validate_position_compliance(
            position=compliant_position
        )

        assert compliance_result["compliant"] is True
        assert len(compliance_result["violations"]) == 0

        # Test non-compliant position (size)
        oversized_position = {
            "symbol": "EUR/USD",
            "quantity": 4000000,  # Above 3M limit
            "portfolio_value": 20000000,
        }

        size_violation = compliance_engine.validate_position_compliance(
            position=oversized_position
        )

        assert size_violation["compliant"] is False
        assert any(
            v["type"] == "POSITION_SIZE_LIMIT" for v in size_violation["violations"]
        )

        # Test non-compliant position (concentration)
        concentrated_position = {
            "symbol": "EUR/USD",
            "quantity": 2500000,
            "portfolio_value": 10000000,  # 25% concentration - above 15% limit
        }

        concentration_violation = compliance_engine.validate_position_compliance(
            position=concentrated_position
        )

        assert concentration_violation["compliant"] is False
        assert any(
            v["type"] == "CONCENTRATION_LIMIT"
            for v in concentration_violation["violations"]
        )

    @pytest.mark.red
    def test_leverage_compliance_validation(self, compliance_engine):
        """RED: Test leverage ratio compliance validation."""
        # Set leverage limits
        leverage_limits = {
            "retail": {"max_leverage": 30, "margin_requirement": 0.033},
            "professional": {"max_leverage": 100, "margin_requirement": 0.01},
            "institutional": {"max_leverage": 500, "margin_requirement": 0.002},
        }

        compliance_engine.set_leverage_limits(leverage_limits)

        # Test compliant leverage (retail)
        retail_account = {
            "account_type": "retail",
            "account_equity": 10000,
            "position_value": 250000,  # 25:1 leverage
            "used_margin": 8333,
        }

        retail_compliance = compliance_engine.validate_leverage_compliance(
            account=retail_account
        )

        assert retail_compliance["compliant"] is True
        assert retail_compliance["effective_leverage"] == 25.0

        # Test non-compliant leverage (retail)
        excessive_retail = {
            "account_type": "retail",
            "account_equity": 10000,
            "position_value": 400000,  # 40:1 leverage - exceeds 30:1 limit
            "used_margin": 13333,
        }

        leverage_violation = compliance_engine.validate_leverage_compliance(
            account=excessive_retail
        )

        assert leverage_violation["compliant"] is False
        assert leverage_violation["effective_leverage"] == 40.0
        assert any(
            v["type"] == "LEVERAGE_LIMIT" for v in leverage_violation["violations"]
        )

    @pytest.mark.red
    def test_best_execution_compliance(self, compliance_engine, sample_trading_data):
        """RED: Test best execution compliance monitoring."""
        trade = sample_trading_data["trades"][0]

        # Add execution quality data
        execution_data = {
            "trade": trade,
            "market_data": {
                "bid": 1.0848,
                "ask": 1.0852,
                "mid": 1.0850,
                "timestamp": trade["timestamp"],
            },
            "execution_price": 1.0850,
            "venues_checked": ["IB_IDEALPRO", "EBS", "REUTERS"],
            "venue_quotes": {
                "IB_IDEALPRO": {"bid": 1.0848, "ask": 1.0852},
                "EBS": {"bid": 1.0847, "ask": 1.0853},
                "REUTERS": {"bid": 1.0849, "ask": 1.0851},
            },
            "execution_venue": "IB_IDEALPRO",
        }

        # Validate best execution
        best_execution_result = compliance_engine.validate_best_execution(
            execution_data=execution_data
        )

        assert "execution_quality_score" in best_execution_result
        assert "venue_comparison" in best_execution_result
        assert "compliance_status" in best_execution_result

        # Should pass if executed at best available price
        if execution_data["execution_price"] <= min(
            venue["ask"] for venue in execution_data["venue_quotes"].values()
        ):
            assert best_execution_result["compliance_status"] == "COMPLIANT"

    # -------------------------------------------------------------------------
    # Data Retention and Privacy Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_data_retention_policy_compliance(
        self, compliance_engine, sample_trading_data
    ):
        """RED: Test data retention policy compliance."""
        # Set retention policies
        retention_policies = {
            "trade_data": {"retention_years": 7, "archive_after_years": 2},
            "audit_trails": {"retention_years": 7, "archive_after_years": 1},
            "client_data": {"retention_years": 5, "archive_after_years": 1},
            "risk_data": {"retention_years": 3, "archive_after_years": 1},
        }

        compliance_engine.set_retention_policies(retention_policies)

        # Test recent data (should be active)
        recent_trade = {
            "trade_id": "RECENT_001",
            "timestamp": datetime.now() - timedelta(days=30),
            "data_type": "trade_data",
        }

        retention_status = compliance_engine.check_retention_status(recent_trade)

        assert retention_status["status"] == "ACTIVE"
        assert retention_status["archive_required"] is False
        assert retention_status["deletion_allowed"] is False

        # Test old data (should be archived)
        old_trade = {
            "trade_id": "OLD_001",
            "timestamp": datetime.now() - timedelta(days=800),  # ~2.2 years
            "data_type": "trade_data",
        }

        old_retention_status = compliance_engine.check_retention_status(old_trade)

        assert old_retention_status["status"] == "ARCHIVE_REQUIRED"
        assert old_retention_status["archive_required"] is True
        assert old_retention_status["deletion_allowed"] is False

        # Test expired data (should be deletable)
        expired_trade = {
            "trade_id": "EXPIRED_001",
            "timestamp": datetime.now() - timedelta(days=2800),  # ~7.7 years
            "data_type": "trade_data",
        }

        expired_retention_status = compliance_engine.check_retention_status(
            expired_trade
        )

        assert expired_retention_status["status"] == "EXPIRED"
        assert expired_retention_status["deletion_allowed"] is True

    @pytest.mark.red
    def test_gdpr_privacy_compliance(self, compliance_engine):
        """RED: Test GDPR privacy compliance features."""
        # Client data with PII
        client_data = {
            "client_id": "CLIENT_001",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "+1-555-123-4567",
            "address": "123 Main St, New York, NY",
            "account_data": {"balance": 50000, "positions": ["EUR/USD", "GBP/USD"]},
            "created_date": datetime(2023, 6, 1),
        }

        # Test PII detection
        pii_fields = compliance_engine.identify_pii_fields(client_data)

        expected_pii = ["name", "email", "phone", "address"]
        assert all(field in pii_fields for field in expected_pii)

        # Test data anonymization
        anonymized_data = compliance_engine.anonymize_client_data(client_data)

        assert (
            anonymized_data["client_id"] != client_data["client_id"]
        )  # Should be hashed
        assert anonymized_data["name"] != client_data["name"]  # Should be masked
        assert anonymized_data["email"] != client_data["email"]  # Should be masked
        assert (
            anonymized_data["account_data"]["balance"]
            == client_data["account_data"]["balance"]
        )  # Non-PII preserved

        # Test right to be forgotten
        deletion_request = {
            "client_id": "CLIENT_001",
            "request_type": "RIGHT_TO_BE_FORGOTTEN",
            "verification_provided": True,
            "request_date": datetime.now(),
        }

        deletion_result = compliance_engine.process_deletion_request(deletion_request)

        assert deletion_result["request_approved"] is True
        assert deletion_result["data_purged"] is True
        assert deletion_result["confirmation_id"] is not None

    # -------------------------------------------------------------------------
    # Compliance Monitoring and Alerting Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_real_time_compliance_monitoring(
        self, compliance_engine, sample_trading_data
    ):
        """RED: Test real-time compliance monitoring and alerting."""
        # Set up compliance monitors
        compliance_rules = [
            {
                "rule_id": "POSITION_LIMIT_MONITOR",
                "rule_type": "POSITION_LIMIT",
                "threshold": 2000000,
                "severity": "HIGH",
            },
            {
                "rule_id": "LEVERAGE_MONITOR",
                "rule_type": "LEVERAGE_LIMIT",
                "threshold": 30,
                "severity": "CRITICAL",
            },
            {
                "rule_id": "CONCENTRATION_MONITOR",
                "rule_type": "CONCENTRATION_LIMIT",
                "threshold": 0.15,
                "severity": "MEDIUM",
            },
        ]

        compliance_engine.set_compliance_rules(compliance_rules)

        # Simulate trading activity that triggers alerts
        violating_trade = {
            "trade_id": "VIOLATION_001",
            "symbol": "EUR/USD",
            "quantity": 2500000,  # Exceeds position limit
            "price": 1.0850,
            "timestamp": datetime.now(),
            "user_id": "TRADER_001",
        }

        # Process trade through compliance monitoring
        compliance_alerts = compliance_engine.monitor_trade_compliance(violating_trade)

        # Verify alert generation
        assert len(compliance_alerts) > 0
        position_alert = next(
            (
                alert
                for alert in compliance_alerts
                if alert["rule_type"] == "POSITION_LIMIT"
            ),
            None,
        )
        assert position_alert is not None
        assert position_alert["severity"] == "HIGH"
        assert position_alert["violation_amount"] == 500000  # Excess over limit

        # Test alert escalation
        escalated_alerts = compliance_engine.escalate_critical_alerts(compliance_alerts)

        critical_alerts = [
            alert for alert in escalated_alerts if alert["severity"] == "CRITICAL"
        ]
        if critical_alerts:
            assert all(alert["escalated"] is True for alert in critical_alerts)
            assert all(alert["notification_sent"] is True for alert in critical_alerts)

    @pytest.mark.red
    def test_compliance_reporting_dashboard(
        self, compliance_engine, sample_trading_data
    ):
        """RED: Test compliance reporting dashboard functionality."""
        # Generate compliance report data
        report_period = {
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 1, 31),
        }

        # Create sample compliance events
        compliance_events = [
            {
                "event_type": "POSITION_LIMIT_EXCEEDED",
                "timestamp": datetime(2024, 1, 15),
                "severity": "HIGH",
                "resolved": True,
            },
            {
                "event_type": "LEVERAGE_WARNING",
                "timestamp": datetime(2024, 1, 20),
                "severity": "MEDIUM",
                "resolved": True,
            },
            {
                "event_type": "REPORTING_THRESHOLD_CROSSED",
                "timestamp": datetime(2024, 1, 25),
                "severity": "LOW",
                "resolved": False,
            },
        ]

        # Generate compliance dashboard
        dashboard_data = compliance_engine.generate_compliance_dashboard(
            period=report_period, events=compliance_events
        )

        # Verify dashboard components
        assert "summary_metrics" in dashboard_data
        assert "violation_trends" in dashboard_data
        assert "outstanding_issues" in dashboard_data
        assert "regulatory_deadlines" in dashboard_data

        # Verify summary metrics
        summary = dashboard_data["summary_metrics"]
        assert summary["total_violations"] == 3
        assert summary["resolved_violations"] == 2
        assert summary["pending_violations"] == 1
        assert summary["compliance_score"] > 0

        # Verify outstanding issues tracking
        outstanding = dashboard_data["outstanding_issues"]
        assert len(outstanding) == 1
        assert outstanding[0]["event_type"] == "REPORTING_THRESHOLD_CROSSED"
        assert outstanding[0]["resolved"] is False
