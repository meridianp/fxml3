"""
Compliance and Audit Factory Definitions
========================================

Factory Boy factories for creating compliance events, audit logs, regulatory
reports, and trade reporting data for testing compliance systems.
"""

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import factory
import factory.fuzzy
from faker import Faker

fake = Faker()


class ComplianceEventFactory(factory.Factory):
    """
    Factory for creating compliance events and violations.

    Generates compliance monitoring events including violations, warnings,
    and regulatory breach notifications with proper audit trails.
    """

    class Meta:
        model = dict

    # Event identification
    event_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    account_id = factory.Sequence(lambda n: f"ACC{n:08d}")
    user_id = factory.Sequence(lambda n: f"user_{n:06d}")

    # Event classification
    event_type = factory.fuzzy.FuzzyChoice(
        [
            "position_limit_breach",
            "leverage_violation",
            "concentration_limit",
            "daily_loss_limit",
            "suspicious_activity",
            "unusual_trading_pattern",
            "kyc_violation",
            "aml_alert",
            "regulatory_breach",
            "internal_control",
        ]
    )

    severity = factory.fuzzy.FuzzyChoice(["low", "medium", "high", "critical"])
    category = factory.fuzzy.FuzzyChoice(
        [
            "risk_management",
            "market_conduct",
            "customer_protection",
            "anti_money_laundering",
            "know_your_customer",
            "market_abuse",
            "operational_risk",
            "regulatory_reporting",
        ]
    )

    # Event details
    event_title = factory.LazyAttribute(
        lambda obj: {
            "position_limit_breach": "Position Size Limit Exceeded",
            "leverage_violation": "Maximum Leverage Violation",
            "daily_loss_limit": "Daily Loss Limit Breach",
            "suspicious_activity": "Suspicious Trading Activity Detected",
            "kyc_violation": "KYC Documentation Incomplete",
            "aml_alert": "Anti-Money Laundering Alert",
        }.get(obj.event_type, f"Compliance Event: {obj.event_type.title()}")
    )

    event_description = factory.Faker("sentence", nb_words=15)

    # Regulatory context
    regulation_source = factory.fuzzy.FuzzyChoice(
        ["MiFID II", "EMIR", "MAR", "CFTC", "SEC", "FCA", "ESMA", "Internal Policy"]
    )
    regulation_reference = factory.LazyAttribute(
        lambda obj: f"{obj.regulation_source}-{fake.random_int(100, 999)}"
    )

    # Financial impact
    monetary_amount = factory.LazyAttribute(
        lambda obj: (
            {
                "position_limit_breach": fake.random.uniform(10000, 500000),
                "leverage_violation": fake.random.uniform(50000, 1000000),
                "daily_loss_limit": fake.random.uniform(5000, 50000),
                "suspicious_activity": fake.random.uniform(10000, 1000000),
            }.get(obj.event_type, fake.random.uniform(1000, 100000))
            if fake.random.random() > 0.3
            else None
        )
    )

    currency = (
        factory.fuzzy.FuzzyChoice(["USD", "EUR", "GBP"])
        if fake.random.random() > 0.3
        else None
    )

    # Event timeline
    detected_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="now")
    )
    event_start_time = factory.LazyAttribute(
        lambda obj: obj.detected_at - timedelta(minutes=fake.random_int(5, 60))
    )
    event_end_time = factory.LazyAttribute(
        lambda obj: (
            obj.event_start_time + timedelta(minutes=fake.random_int(1, 120))
            if fake.random.random() > 0.4
            else None
        )  # 40% still ongoing
    )

    # Response and resolution
    status = factory.fuzzy.FuzzyChoice(
        ["open", "investigating", "resolved", "closed", "escalated"]
    )
    assigned_to = factory.fuzzy.FuzzyChoice(
        ["compliance_officer", "risk_manager", "legal_team", "operations_team"]
    )

    # Actions taken
    immediate_actions = factory.LazyFunction(
        lambda: fake.random_elements(
            [
                "position_reduced",
                "account_restricted",
                "trading_halted",
                "manager_notified",
                "documentation_requested",
                "investigation_initiated",
            ],
            length=fake.random_int(1, 3),
        )
    )

    remediation_plan = factory.Faker("sentence", nb_words=20)

    # Reporting requirements
    requires_regulatory_reporting = factory.LazyAttribute(
        lambda obj: obj.severity in ["high", "critical"]
        and obj.category in ["market_conduct", "anti_money_laundering", "market_abuse"]
    )

    reported_to_regulator = factory.LazyAttribute(
        lambda obj: obj.requires_regulatory_reporting and fake.random.random() > 0.3
    )

    reporting_deadline = factory.LazyAttribute(
        lambda obj: (
            obj.detected_at + timedelta(days=fake.random_int(1, 30))
            if obj.requires_regulatory_reporting
            else None
        )
    )

    # Investigation details
    investigation_notes = factory.Faker("text", max_nb_chars=500)
    evidence_collected = factory.LazyFunction(
        lambda: fake.random_elements(
            [
                "trade_records",
                "communication_logs",
                "system_logs",
                "client_documentation",
                "market_data",
                "position_reports",
            ],
            length=fake.random_int(2, 4),
        )
    )

    # Recurrence tracking
    is_repeat_violation = factory.fuzzy.FuzzyChoice([True, False])
    previous_violations_count = factory.LazyAttribute(
        lambda obj: fake.random_int(1, 5) if obj.is_repeat_violation else 0
    )

    # Risk scoring
    compliance_score = factory.fuzzy.FuzzyDecimal(0.1, 1.0, 2)
    risk_score = factory.LazyAttribute(
        lambda obj: {
            "low": fake.random.uniform(0.1, 0.3),
            "medium": fake.random.uniform(0.3, 0.6),
            "high": fake.random.uniform(0.6, 0.8),
            "critical": fake.random.uniform(0.8, 1.0),
        }.get(obj.severity, 0.5)
    )

    class Params:
        # Traits for different violation scenarios
        high_severity = factory.Trait(
            severity="critical",
            requires_regulatory_reporting=True,
            immediate_actions=[
                "trading_halted",
                "manager_notified",
                "investigation_initiated",
            ],
            status="investigating",
        )

        aml_violation = factory.Trait(
            event_type="aml_alert",
            category="anti_money_laundering",
            regulation_source="AML Directive",
            requires_regulatory_reporting=True,
            severity=factory.fuzzy.FuzzyChoice(["high", "critical"]),
        )

        resolved_event = factory.Trait(
            status="resolved",
            event_end_time=factory.LazyAttribute(
                lambda obj: obj.detected_at + timedelta(hours=fake.random_int(1, 48))
            ),
            remediation_plan="Violation resolved through position adjustment and policy reminder.",
        )


class AuditLogFactory(factory.Factory):
    """
    Factory for creating comprehensive audit log entries.
    """

    class Meta:
        model = dict

    # Log identification
    log_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    session_id = factory.LazyFunction(lambda: str(uuid.uuid4())[:8])
    correlation_id = factory.LazyFunction(lambda: str(uuid.uuid4())[:12])

    # User context
    user_id = factory.Sequence(lambda n: f"user_{n:06d}")
    username = factory.Sequence(lambda n: f"trader_{n}")
    user_role = factory.fuzzy.FuzzyChoice(
        ["trader", "manager", "admin", "compliance_officer"]
    )

    # Action details
    action_type = factory.fuzzy.FuzzyChoice(
        [
            "login",
            "logout",
            "trade_executed",
            "order_placed",
            "order_cancelled",
            "position_opened",
            "position_closed",
            "balance_updated",
            "settings_changed",
            "report_generated",
            "data_exported",
            "password_changed",
            "account_accessed",
        ]
    )

    action_description = factory.LazyAttribute(
        lambda obj: {
            "login": f"User {obj.username} logged in from {fake.ipv4()}",
            "trade_executed": f'Trade executed for {fake.random_element(["EURUSD", "GBPUSD", "USDJPY"])}',
            "order_placed": f'Order placed: {fake.random_element(["BUY", "SELL"])} {fake.random.uniform(0.01, 10.0):.2f} lots',
            "position_closed": f"Position closed with P&L: ${fake.random.uniform(-1000, 2000):.2f}",
            "settings_changed": f'Account settings modified: {fake.random_element(["risk_limits", "notifications", "preferences"])}',
            "data_exported": f'Data export requested: {fake.random_element(["trade_history", "account_statements", "tax_reports"])}',
        }.get(obj.action_type, f"Action performed: {obj.action_type}")
    )

    # Technical context
    ip_address = factory.Faker("ipv4")
    user_agent = factory.Faker("user_agent")
    device_type = factory.fuzzy.FuzzyChoice(["desktop", "mobile", "tablet", "api"])
    platform = factory.fuzzy.FuzzyChoice(["web", "mobile_app", "api", "terminal"])

    # Geographic context
    country = factory.Faker("country_code")
    city = factory.Faker("city")
    timezone = factory.fuzzy.FuzzyChoice(
        ["America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney"]
    )

    # Request/Response data
    request_method = factory.fuzzy.FuzzyChoice(
        ["GET", "POST", "PUT", "DELETE", "PATCH"]
    )
    request_url = factory.LazyAttribute(
        lambda obj: f"/api/{obj.action_type}/{fake.uuid4()[:8]}"
    )
    response_status = factory.fuzzy.FuzzyChoice(
        [200, 201, 204, 400, 401, 403, 404, 500]
    )
    response_time_ms = factory.fuzzy.FuzzyInteger(10, 2000)

    # Financial data (if applicable)
    financial_impact = factory.LazyAttribute(
        lambda obj: (
            {
                "trade_executed": fake.random.uniform(1000, 50000),
                "position_closed": fake.random.uniform(-5000, 10000),
                "balance_updated": fake.random.uniform(100, 100000),
            }.get(obj.action_type, None)
            if fake.random.random() > 0.7
            else None
        )
    )

    # Security context
    authentication_method = factory.fuzzy.FuzzyChoice(
        ["password", "two_factor", "api_key", "sso"]
    )
    security_level = factory.fuzzy.FuzzyChoice(["low", "medium", "high"])
    risk_assessment = factory.fuzzy.FuzzyChoice(["normal", "elevated", "high_risk"])

    # Timestamps
    timestamp = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )
    processing_time_ms = factory.fuzzy.FuzzyInteger(1, 500)

    # Data integrity
    checksum = factory.LazyFunction(lambda: fake.sha256())
    is_tamper_proof = True
    log_level = factory.fuzzy.FuzzyChoice(["INFO", "WARN", "ERROR", "DEBUG"])

    # Compliance flags
    requires_retention = factory.LazyAttribute(
        lambda obj: obj.action_type
        in ["trade_executed", "position_closed", "balance_updated"]
    )
    retention_years = factory.LazyAttribute(
        lambda obj: fake.random_int(3, 7) if obj.requires_retention else 1
    )
    is_regulatory_relevant = factory.LazyAttribute(
        lambda obj: obj.action_type
        in ["trade_executed", "order_placed", "position_closed"]
    )

    class Params:
        # Traits for different log scenarios
        trading_activity = factory.Trait(
            action_type=factory.fuzzy.FuzzyChoice(
                ["trade_executed", "order_placed", "position_closed"]
            ),
            security_level="high",
            requires_retention=True,
            is_regulatory_relevant=True,
        )

        security_event = factory.Trait(
            action_type=factory.fuzzy.FuzzyChoice(
                ["login", "password_changed", "account_accessed"]
            ),
            risk_assessment=factory.fuzzy.FuzzyChoice(["elevated", "high_risk"]),
            security_level="high",
        )

        error_event = factory.Trait(
            log_level="ERROR",
            response_status=factory.fuzzy.FuzzyChoice([400, 401, 403, 404, 500]),
            risk_assessment="elevated",
        )


class RegulatoryReportFactory(factory.Factory):
    """
    Factory for creating regulatory reports and submissions.
    """

    class Meta:
        model = dict

    # Report identification
    report_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    report_name = factory.fuzzy.FuzzyChoice(
        [
            "MiFID II Transaction Report",
            "EMIR Trade Report",
            "Large Exposure Report",
            "Liquidity Coverage Ratio",
            "Market Risk Report",
            "Operational Risk Report",
            "Anti-Money Laundering Report",
            "Suspicious Activity Report",
        ]
    )

    # Regulatory context
    regulation = factory.LazyAttribute(
        lambda obj: {
            "MiFID II Transaction Report": "MiFID II",
            "EMIR Trade Report": "EMIR",
            "Large Exposure Report": "CRR",
            "Anti-Money Laundering Report": "AML Directive",
        }.get(obj.report_name, "Internal Regulation")
    )

    regulator = factory.LazyAttribute(
        lambda obj: {
            "MiFID II": "ESMA",
            "EMIR": "ESMA",
            "CRR": "EBA",
            "AML Directive": "National AML Authority",
        }.get(obj.regulation, "Internal")
    )

    # Reporting period
    reporting_period_start = factory.LazyFunction(
        lambda: fake.date_between(start_date="-90d", end_date="-30d")
    )
    reporting_period_end = factory.LazyAttribute(
        lambda obj: obj.reporting_period_start + timedelta(days=30)
    )

    # Report generation
    generated_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-7d", end_date="now")
    )
    generated_by = factory.fuzzy.FuzzyChoice(
        ["compliance_system", "compliance_officer", "risk_manager"]
    )
    report_version = factory.Sequence(lambda n: f"v{n}.0")

    # Report content
    total_records = factory.fuzzy.FuzzyInteger(100, 10000)
    data_sources = factory.LazyFunction(
        lambda: fake.random_elements(
            [
                "trading_system",
                "order_management",
                "risk_system",
                "client_database",
                "market_data",
                "position_keeping",
            ],
            length=fake.random_int(2, 4),
        )
    )

    # File information
    file_format = factory.fuzzy.FuzzyChoice(["XML", "CSV", "JSON", "PDF"])
    file_size_mb = factory.fuzzy.FuzzyDecimal(1.0, 500.0, 1)
    file_checksum = factory.LazyFunction(lambda: fake.sha256())

    # Submission details
    submission_status = factory.fuzzy.FuzzyChoice(
        ["pending", "submitted", "acknowledged", "rejected", "resubmitted"]
    )
    submission_deadline = factory.LazyAttribute(
        lambda obj: obj.reporting_period_end + timedelta(days=fake.random_int(1, 30))
    )
    submitted_at = factory.LazyAttribute(
        lambda obj: (
            obj.generated_at + timedelta(hours=fake.random_int(1, 48))
            if obj.submission_status != "pending"
            else None
        )
    )

    # Validation and quality
    validation_errors = factory.fuzzy.FuzzyInteger(0, 10)
    validation_warnings = factory.fuzzy.FuzzyInteger(0, 25)
    quality_score = factory.LazyAttribute(
        lambda obj: max(
            0.5, 1.0 - (obj.validation_errors * 0.1) - (obj.validation_warnings * 0.02)
        )
    )

    # Acknowledgment from regulator
    regulator_reference = factory.LazyAttribute(
        lambda obj: (
            f"{obj.regulator}-{fake.random_int(1000000, 9999999)}"
            if obj.submission_status == "acknowledged"
            else None
        )
    )
    acknowledgment_date = factory.LazyAttribute(
        lambda obj: (
            obj.submitted_at + timedelta(days=fake.random_int(1, 5))
            if obj.submission_status == "acknowledged"
            else None
        )
    )


class TradeReportFactory(factory.Factory):
    """
    Factory for creating individual trade reports for regulatory submission.
    """

    class Meta:
        model = dict

    # Report identification
    trade_report_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    trade_id = factory.Sequence(lambda n: f"TRD{n:010d}")
    regulatory_report_id = factory.LazyFunction(
        lambda: RegulatoryReportFactory().report_id
    )

    # Trade details
    symbol = factory.fuzzy.FuzzyChoice(["EURUSD", "GBPUSD", "USDJPY", "USDCHF"])
    side = factory.fuzzy.FuzzyChoice(["BUY", "SELL"])
    quantity = factory.fuzzy.FuzzyDecimal(0.01, 100.0, 2)
    price = factory.fuzzy.FuzzyDecimal(1.0000, 1.5000, 4)

    # Execution details
    execution_timestamp = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-30d", end_date="now")
    )
    execution_venue = factory.fuzzy.FuzzyChoice(
        ["IB", "FXCM", "EBS", "Reuters", "Currenex"]
    )
    counterparty = factory.fuzzy.FuzzyChoice(
        ["BANK_A", "BANK_B", "ECN_LIQUIDITY", "PRIME_BROKER"]
    )

    # Client information (anonymized for reporting)
    client_id = factory.Sequence(lambda n: f"CLIENT_{n:08d}")
    client_classification = factory.fuzzy.FuzzyChoice(
        ["retail", "professional", "eligible_counterparty"]
    )
    client_country = factory.Faker("country_code")

    # Regulatory fields
    transaction_reference = factory.LazyFunction(lambda: str(uuid.uuid4()))
    reporting_flag = factory.fuzzy.FuzzyChoice(["new", "modify", "cancel", "correct"])
    lifecycle_event = factory.fuzzy.FuzzyChoice(
        ["trade", "novation", "exercise", "maturity"]
    )

    # MiFID II specific fields
    commodity_derivative_indicator = factory.fuzzy.FuzzyChoice([True, False])
    securities_financing_transaction = False  # Not applicable for FX
    transmission_of_order_indicator = factory.fuzzy.FuzzyChoice([True, False])

    # Risk and valuation
    notional_amount = factory.LazyAttribute(
        lambda obj: obj.quantity * obj.price * Decimal("100000")
    )
    mark_to_market = factory.LazyAttribute(
        lambda obj: obj.notional_amount + Decimal(str(fake.random.uniform(-1000, 1000)))
    )

    # Reporting metadata
    reported_at = factory.LazyFunction(
        lambda: fake.date_time_between(start_date="-1d", end_date="now")
    )
    report_version = factory.Sequence(lambda n: n)
    is_correction = factory.fuzzy.FuzzyChoice([True, False])
    original_report_id = factory.LazyAttribute(
        lambda obj: str(uuid.uuid4()) if obj.is_correction else None
    )

    class Params:
        # Traits for different report types
        large_trade = factory.Trait(
            quantity=factory.fuzzy.FuzzyDecimal(50.0, 500.0, 2),
            client_classification="professional",
            commodity_derivative_indicator=False,
        )

        retail_trade = factory.Trait(
            quantity=factory.fuzzy.FuzzyDecimal(0.01, 5.0, 2),
            client_classification="retail",
            transmission_of_order_indicator=True,
        )

        correction_report = factory.Trait(
            is_correction=True,
            reporting_flag="correct",
            report_version=factory.Sequence(lambda n: n + 1),
        )
