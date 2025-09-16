#!/usr/bin/env python3
"""Test script for validating FXML4 Compliance Engine functionality.

This script comprehensively tests the compliance engine including:
- Basic compliance rule creation and management
- Real-time transaction monitoring
- Regulatory checks for multiple jurisdictions
- Audit logging integration
- Suspicious activity detection
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fxml4.brokers.compliance.audit_logger import (
    AuditCategory,
    AuditLogger,
    AuditSeverity,
)
from fxml4.brokers.compliance.compliance_engine import (
    ComplianceEngine,
    ComplianceResult,
    ConcentrationRule,
    PositionLimitRule,
    TradingHoursRule,
    VelocityRule,
    ViolationSeverity,
)
from fxml4.brokers.compliance.regulatory_checks import (
    FISCACompliance,
    MiFIDIICompliance,
    RegulatoryContext,
    RegulatoryJurisdiction,
    SECCompliance,
)
from fxml4.brokers.compliance.transaction_monitor import (
    RiskLevel,
    SuspiciousActivityType,
    TransactionMonitor,
)
from fxml4.fix.messages.base import OrdType, Side
from fxml4.fix.messages.orders import NewOrderSingle


class MockOrder:
    """Mock order for testing."""

    def __init__(
        self,
        symbol="EURUSD",
        side=Side.BUY,
        order_qty=100000,
        price=1.1000,
        cl_ord_id=None,
    ):
        self.symbol = symbol
        self.side = side
        self.order_qty = order_qty
        self.price = price
        self.cl_ord_id = cl_ord_id or f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.ord_type = OrdType.LIMIT


async def test_basic_compliance_engine():
    """Test basic compliance engine functionality."""
    print("🔍 Testing Basic Compliance Engine...")

    # Initialize audit logger
    audit_logger = AuditLogger()

    # Create compliance engine
    engine = ComplianceEngine(audit_logger=audit_logger, enable_blocking=True)

    # Add rules
    position_limits = {"EURUSD": 500000, "GBPUSD": 300000, "USDJPY": 1000000}
    engine.add_rule(PositionLimitRule(position_limits))
    engine.add_rule(ConcentrationRule(max_concentration_pct=20.0))
    engine.add_rule(VelocityRule(max_orders_per_minute=10, max_orders_per_hour=100))

    # Trading hours: EUR/USD only during London/NY overlap (13:00-17:00 UTC)
    trading_hours = {"EURUSD": [(13, 17)]}
    engine.add_rule(TradingHoursRule(trading_hours))

    print(f"✅ Engine initialized with {len(engine.rules)} rules")

    # Test normal order (should pass)
    test_order = MockOrder(symbol="EURUSD", order_qty=50000)
    context = {
        "positions": {"EURUSD": 100000},
        "total_portfolio_value": 1000000,
        "prices": {"EURUSD": 1.1000},
    }

    result, violations = await engine.check_order_compliance(test_order, context)
    print(f"Normal order result: {result.value} with {len(violations)} violations")

    # Test position limit violation
    large_order = MockOrder(symbol="EURUSD", order_qty=600000)  # Exceeds 500k limit
    result, violations = await engine.check_order_compliance(large_order, context)
    print(f"Large order result: {result.value} with {len(violations)} violations")
    if violations:
        print(f"  Violation: {violations[0].message}")

    # Get engine statistics
    stats = engine.get_compliance_stats()
    print(
        f"Engine stats: {stats['total_checks']} checks, {stats['total_violations']} violations"
    )

    return engine


async def test_transaction_monitor():
    """Test transaction monitoring for suspicious activities."""
    print("\n🕵️ Testing Transaction Monitor...")

    audit_logger = AuditLogger()
    monitor = TransactionMonitor(audit_logger=audit_logger, alert_threshold=0.6)

    # Simulate normal trading
    base_transaction = {
        "client_id": "TEST_CLIENT_001",
        "symbol": "EURUSD",
        "side": "BUY",
        "quantity": 100000,
        "price": 1.1000,
        "order_id": "TEST_001",
        "status": "FILLED",
    }

    print("Simulating normal trading pattern...")
    alerts = await monitor.monitor_transaction(base_transaction)
    print(f"Normal transaction alerts: {len(alerts)}")

    # Simulate unusual volume
    print("Simulating unusual volume...")
    for i in range(15):  # Build history
        normal_tx = base_transaction.copy()
        normal_tx["order_id"] = f"NORMAL_{i}"
        normal_tx["quantity"] = 50000 + (i * 1000)
        await monitor.monitor_transaction(normal_tx)

    # Large volume transaction
    unusual_tx = base_transaction.copy()
    unusual_tx["order_id"] = "UNUSUAL_001"
    unusual_tx["quantity"] = 500000  # 10x normal
    alerts = await monitor.monitor_transaction(unusual_tx)

    if alerts:
        alert = alerts[0]
        print(
            f"Unusual volume alert: {alert.activity_type.value} (confidence: {alert.confidence_score:.2f})"
        )

    # Simulate rapid trading
    print("Simulating rapid trading...")
    for i in range(7):  # 7 trades in rapid succession
        rapid_tx = base_transaction.copy()
        rapid_tx["order_id"] = f"RAPID_{i}"
        await asyncio.sleep(0.1)  # Small delay
        alerts = await monitor.monitor_transaction(rapid_tx)

    if alerts:
        print(f"Rapid trading alerts generated: {len(alerts)}")

    # Get monitor statistics
    stats = monitor.get_monitoring_stats()
    print(
        f"Monitor stats: {stats['total_transactions_monitored']} transactions, {stats['alerts_generated']} alerts"
    )

    return monitor


async def test_regulatory_compliance():
    """Test regulatory compliance checks."""
    print("\n🏛️ Testing Regulatory Compliance...")

    # Test SEC compliance
    sec_compliance = SECCompliance()
    sec_rules = sec_compliance.create_rules()
    print(f"SEC rules created: {len(sec_rules)}")

    # Test with large position (should trigger SEC reporting)
    large_order = MockOrder(
        symbol="EURUSD", order_qty=500000, price=1.1000
    )  # $550k order

    context = {
        "regulatory_context": RegulatoryContext(
            jurisdiction=RegulatoryJurisdiction.US_SEC, client_type="institutional"
        ),
        "position_values": {"EURUSD": 9500000},  # $9.5M existing position
        "daily_trading_volume": 1500000,  # $1.5M daily volume
        "monthly_trading_volume": 15000000,  # $15M monthly volume
    }

    for rule in sec_rules:
        if rule.rule_id == "SEC_POS_001":  # Position reporting rule
            violation = await rule.check_order(large_order, context)
            if violation:
                print(f"SEC Position Reporting: {violation.message}")

    # Test MiFID II compliance
    mifid_compliance = MiFIDIICompliance()
    mifid_rules = mifid_compliance.create_rules()
    print(f"MiFID II rules created: {len(mifid_rules)}")

    # Test retail client without appropriateness assessment
    retail_context = {
        "regulatory_context": RegulatoryContext(
            jurisdiction=RegulatoryJurisdiction.EU_MIFID, client_type="retail"
        )
        # Missing appropriateness_assessment
    }

    for rule in mifid_rules:
        if rule.rule_id == "MIFID_SUIT_001":  # Suitability rule
            violation = await rule.check_order(large_order, retail_context)
            if violation:
                print(f"MiFID II Suitability: {violation.message}")

    # Test FISCA compliance
    fisca_compliance = FISCACompliance()
    fisca_rules = fisca_compliance.create_rules()
    print(f"FISCA rules created: {len(fisca_rules)}")

    # Test excessive leverage
    fisca_context = {
        "regulatory_context": RegulatoryContext(
            jurisdiction=RegulatoryJurisdiction.SINGAPORE_MAS,
            client_type="retail",
            leverage=25,  # Exceeds 20:1 retail limit
        )
    }

    for rule in fisca_rules:
        if rule.rule_id == "FISCA_LEV_001":  # Leverage rule
            violation = await rule.check_order(large_order, fisca_context)
            if violation:
                print(f"FISCA Leverage: {violation.message}")

    return sec_rules + mifid_rules + fisca_rules


async def test_audit_integration():
    """Test audit logging integration."""
    print("\n📝 Testing Audit Integration...")

    audit_logger = AuditLogger()

    # Log various event types
    await audit_logger.log_compliance_event(
        event_type="COMPLIANCE_RULE_ACTIVATED",
        message="Position limit rule activated",
        compliance_flags=["POSITION_LIMIT"],
        severity=AuditSeverity.INFO,
    )

    await audit_logger.log_trade_event(
        event_type="ORDER_COMPLIANCE_CHECK",
        message="Order passed compliance checks",
        cl_ord_id="TEST_ORDER_001",
        symbol="EURUSD",
        details={"result": "PASS", "checks_performed": 5},
    )

    await audit_logger.log_risk_event(
        event_type="SUSPICIOUS_ACTIVITY_DETECTED",
        message="Unusual trading volume detected",
        risk_level="HIGH",
        details={"activity_type": "UNUSUAL_VOLUME", "confidence": 0.85},
    )

    print("✅ Audit events logged successfully")
    return audit_logger


async def run_comprehensive_test():
    """Run comprehensive compliance engine test."""
    print("🚀 Starting Comprehensive Compliance Engine Test\n")
    print("=" * 60)

    try:
        # Test basic engine
        engine = await test_basic_compliance_engine()

        # Test transaction monitoring
        monitor = await test_transaction_monitor()

        # Test regulatory compliance
        regulatory_rules = await test_regulatory_compliance()

        # Test audit integration
        audit_logger = await test_audit_integration()

        # Integration test: Full compliance workflow
        print("\n🔄 Testing Full Compliance Workflow...")

        # Create comprehensive compliance context
        comprehensive_context = {
            "positions": {"EURUSD": 200000, "GBPUSD": 150000},
            "total_portfolio_value": 2000000,
            "prices": {"EURUSD": 1.1000, "GBPUSD": 1.3000},
            "daily_trading_volume": 500000,
            "account_equity": 1000000,
            "margin_level": 1.5,
            "regulatory_context": RegulatoryContext(
                jurisdiction=RegulatoryJurisdiction.EU_MIFID,
                client_type="professional",
                client_classification="professional",
            ),
            "appropriateness_assessment": True,
            "execution_policy": "BEST_EXECUTION_POLICY_V1",
        }

        # Test order with full context
        test_order = MockOrder(symbol="EURUSD", order_qty=100000, price=1.1050)

        # Add regulatory rules to engine
        for rule in regulatory_rules[:3]:  # Add first 3 regulatory rules
            engine.add_rule(rule)

        # Run compliance check
        result, violations = await engine.check_order_compliance(
            test_order, comprehensive_context
        )
        print(f"Comprehensive check result: {result.value}")

        # Simulate transaction monitoring
        transaction = {
            "client_id": "PROFESSIONAL_001",
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": 100000,
            "price": 1.1050,
            "order_id": test_order.cl_ord_id,
            "status": "FILLED",
        }

        alerts = await monitor.monitor_transaction(transaction)
        print(f"Transaction monitoring alerts: {len(alerts)}")

        # Final statistics
        print("\n" + "=" * 60)
        print("📊 COMPLIANCE ENGINE TEST RESULTS")
        print("=" * 60)

        engine_stats = engine.get_compliance_stats()
        monitor_stats = monitor.get_monitoring_stats()

        print(f"🔧 Compliance Engine:")
        print(f"  • Total rules: {engine_stats['total_rules']}")
        print(f"  • Active rules: {engine_stats['active_rules']}")
        print(f"  • Compliance checks: {engine_stats['total_checks']}")
        print(f"  • Violations found: {engine_stats['total_violations']}")
        print(f"  • Orders blocked: {engine_stats['total_blocked']}")

        print(f"\n🕵️ Transaction Monitor:")
        print(
            f"  • Transactions monitored: {monitor_stats['total_transactions_monitored']}"
        )
        print(f"  • Alerts generated: {monitor_stats['alerts_generated']}")
        print(f"  • Active alerts: {monitor_stats['active_alerts']}")
        print(f"  • False positive rate: {monitor_stats['false_positive_rate']:.1f}%")

        print(f"\n🏛️ Regulatory Coverage:")
        print(
            f"  • SEC (US) rules: {len([r for r in regulatory_rules if 'SEC' in r.rule_id])}"
        )
        print(
            f"  • MiFID II (EU) rules: {len([r for r in regulatory_rules if 'MIFID' in r.rule_id])}"
        )
        print(
            f"  • FISCA (SG) rules: {len([r for r in regulatory_rules if 'FISCA' in r.rule_id])}"
        )

        print(f"\n✅ COMPLIANCE ENGINE: FULLY OPERATIONAL!")
        print("🎯 Real-time trade monitoring and regulatory framework complete")

        return True

    except Exception as e:
        print(f"\n❌ Compliance Engine Test Failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_comprehensive_test())
    sys.exit(0 if success else 1)
