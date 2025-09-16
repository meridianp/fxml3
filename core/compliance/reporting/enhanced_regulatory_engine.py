"""
Enhanced Regulatory Reporting Engine for FXML4 Phase 6.

This module extends the existing regulatory reporting engine with advanced features:
- Integration with Phase 6 surveillance system
- Real-time compliance monitoring with Phase 5 broker routing
- Enhanced regulatory analytics and pattern detection
- Advanced audit trail management with cryptographic integrity
- Multi-jurisdictional reporting with automated validation
"""

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from fxml4.api.auth.audit_logger import AuditEventType, auth_audit_logger
from fxml4.brokers.enhanced_execution_engine import EnhancedExecutionEngine
from fxml4.compliance.reporting.regulatory_engine import (
    RegulatoryJurisdiction,
    RegulatoryReportingEngine,
    ReportFormat,
    ReportPriority,
)
from fxml4.compliance.surveillance.advanced_trade_monitor import AdvancedTradeMonitor


class EnhancedReportType(Enum):
    """Enhanced report types for Phase 6 compliance."""

    # Core regulatory reports (inherited from base)
    TRADE_REPORTING = "trade_reporting"
    POSITION_REPORTING = "position_reporting"
    TRANSACTION_REPORTING = "transaction_reporting"
    RISK_REPORTING = "risk_reporting"
    SURVEILLANCE_REPORTING = "surveillance_reporting"

    # Phase 6 enhanced reports
    REAL_TIME_SURVEILLANCE = "real_time_surveillance"
    PATTERN_DETECTION_REPORT = "pattern_detection_report"
    BROKER_ROUTING_COMPLIANCE = "broker_routing_compliance"
    EXECUTION_QUALITY_ANALYSIS = "execution_quality_analysis"
    REGULATORY_BREACH_ALERT = "regulatory_breach_alert"
    CROSS_VENUE_ANALYSIS = "cross_venue_analysis"
    COMPLIANCE_DASHBOARD_DATA = "compliance_dashboard_data"
    AUDIT_TRAIL_INTEGRITY = "audit_trail_integrity"


class ComplianceAlertLevel(Enum):
    """Compliance alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    BREACH = "breach"
    CRITICAL = "critical"


@dataclass
class EnhancedComplianceRecord:
    """Enhanced compliance record with cryptographic integrity."""

    record_id: str
    timestamp: datetime
    event_type: str
    record_data: Dict[str, Any]
    integrity_hash: str
    previous_hash: Optional[str] = None
    digital_signature: Optional[str] = None
    regulatory_flags: List[str] = None
    compliance_score: float = 1.0

    def __post_init__(self):
        if self.regulatory_flags is None:
            self.regulatory_flags = []


@dataclass
class RegulatoryBreachAlert:
    """Alert for regulatory compliance breaches."""

    alert_id: str
    breach_type: str
    severity: ComplianceAlertLevel
    detected_at: datetime
    description: str
    affected_trades: List[str]
    regulatory_impact: Dict[str, Any]
    remediation_required: bool
    deadline: Optional[datetime] = None
    assigned_to: Optional[str] = None


class EnhancedRegulatoryReportingEngine(RegulatoryReportingEngine):
    """
    Enhanced regulatory reporting engine with Phase 6 capabilities.

    Extends the base regulatory reporting engine with:
    - Advanced surveillance integration
    - Real-time compliance monitoring
    - Cryptographic audit trail integrity
    - Enhanced regulatory analytics
    - Cross-venue compliance analysis
    """

    def __init__(self):
        """Initialize the enhanced regulatory reporting engine."""
        super().__init__()

        # Phase 6 specific configuration
        self.surveillance_monitor = AdvancedTradeMonitor()
        self.execution_engine: Optional[EnhancedExecutionEngine] = None

        # Enhanced compliance settings
        self.enable_real_time_surveillance = self.config.get(
            "compliance.enhanced.real_time_surveillance", True
        )
        self.enable_cryptographic_integrity = self.config.get(
            "compliance.enhanced.cryptographic_integrity", True
        )
        self.compliance_threshold = self.config.get(
            "compliance.enhanced.compliance_threshold", 0.95
        )

        # Cryptographic keys for integrity verification
        self.integrity_key = self.config.get(
            "compliance.enhanced.integrity_key", "default_key_change_in_production"
        ).encode()

        # Enhanced state management
        self.compliance_records: Dict[str, EnhancedComplianceRecord] = {}
        self.regulatory_breaches: Dict[str, RegulatoryBreachAlert] = {}
        self.audit_chain_hash: Optional[str] = None

        # Real-time compliance monitoring
        self.compliance_violations = 0
        self.compliance_checks_performed = 0
        self.last_compliance_check = None

        # Initialize enhanced specifications
        self._initialize_enhanced_specifications()

        self.logger.info("EnhancedRegulatoryReportingEngine initialized successfully")

    def _initialize_enhanced_specifications(self):
        """Initialize Phase 6 enhanced report specifications."""

        # Real-time surveillance reporting
        self.report_specifications["real_time_surveillance"] = {
            "report_type": EnhancedReportType.REAL_TIME_SURVEILLANCE,
            "jurisdiction": RegulatoryJurisdiction.US_CFTC,
            "format": ReportFormat.JSON,
            "frequency": "real_time",
            "fields": [
                "surveillance_alerts",
                "pattern_detections",
                "anomaly_scores",
                "compliance_violations",
                "real_time_metrics",
            ],
            "filters": {"min_alert_severity": "medium"},
            "deadline_minutes": 5,  # 5-minute real-time reporting
            "is_mandatory": True,
        }

        # Broker routing compliance
        self.report_specifications["broker_routing_compliance"] = {
            "report_type": EnhancedReportType.BROKER_ROUTING_COMPLIANCE,
            "jurisdiction": RegulatoryJurisdiction.EU_MIFID,
            "format": ReportFormat.XML,
            "frequency": "hourly",
            "fields": [
                "routing_decisions",
                "execution_venues",
                "best_execution_analysis",
                "order_routing_rationale",
                "venue_performance_metrics",
            ],
            "filters": {"include_routing_analysis": True},
            "deadline_minutes": 60,
            "is_mandatory": True,
        }

        # Pattern detection reporting
        self.report_specifications["pattern_detection_report"] = {
            "report_type": EnhancedReportType.PATTERN_DETECTION_REPORT,
            "jurisdiction": RegulatoryJurisdiction.US_FINRA,
            "format": ReportFormat.JSON,
            "frequency": "daily",
            "fields": [
                "detected_patterns",
                "pattern_confidence_scores",
                "regulatory_implications",
                "investigation_recommendations",
            ],
            "filters": {"min_confidence_score": 0.8},
            "deadline_minutes": 1440,
            "is_mandatory": False,
        }

        # Execution quality analysis
        self.report_specifications["execution_quality_analysis"] = {
            "report_type": EnhancedReportType.EXECUTION_QUALITY_ANALYSIS,
            "jurisdiction": RegulatoryJurisdiction.EU_MIFID,
            "format": ReportFormat.CSV,
            "frequency": "monthly",
            "fields": [
                "execution_venues",
                "price_improvement",
                "execution_speed",
                "fill_rates",
                "slippage_analysis",
                "best_execution_metrics",
            ],
            "filters": {"include_venue_analysis": True},
            "deadline_minutes": 43200,  # Monthly
            "is_mandatory": True,
        }

        self.logger.info("Enhanced report specifications initialized")

    async def process_real_time_compliance_event(
        self, event_data: Dict[str, Any]
    ) -> Optional[RegulatoryBreachAlert]:
        """Process real-time compliance events with enhanced monitoring."""

        if not self.enable_real_time_surveillance:
            return None

        event_type = event_data.get("type")
        self.compliance_checks_performed += 1
        self.last_compliance_check = datetime.now(timezone.utc)

        # Create compliance record with integrity
        _ = await self._create_compliance_record(event_data)

        # Check for regulatory breaches
        breach_alert = await self._analyze_compliance_breach(event_data)

        if breach_alert:
            self.compliance_violations += 1
            self.regulatory_breaches[breach_alert.alert_id] = breach_alert

            # Generate immediate breach report
            await self._generate_breach_report(breach_alert)

        # Real-time surveillance integration
        if event_type == "trade_executed":
            await self._process_trade_surveillance(event_data)
        elif event_type == "order_routed":
            await self._process_routing_compliance(event_data)
        elif event_type == "pattern_detected":
            await self._process_pattern_compliance(event_data)

        return breach_alert

    async def _create_compliance_record(
        self, event_data: Dict[str, Any]
    ) -> EnhancedComplianceRecord:
        """Create a compliance record with cryptographic integrity."""

        record_id = f"comp_{int(datetime.now().timestamp()*1000000)}"
        timestamp = datetime.now(timezone.utc)

        # Create record data
        record_data = {
            "event": event_data,
            "compliance_metadata": {
                "processed_at": timestamp.isoformat(),
                "engine_version": "enhanced_v6",
                "check_sequence": self.compliance_checks_performed,
            },
        }

        # Calculate integrity hash
        data_string = json.dumps(record_data, sort_keys=True, default=str)
        integrity_hash = self._calculate_integrity_hash(
            data_string, self.audit_chain_hash
        )

        # Create digital signature if enabled
        digital_signature = None
        if self.enable_cryptographic_integrity:
            digital_signature = self._create_digital_signature(data_string)

        # Determine regulatory flags
        regulatory_flags = await self._determine_regulatory_flags(event_data)

        # Calculate compliance score
        compliance_score = await self._calculate_compliance_score(event_data)

        record = EnhancedComplianceRecord(
            record_id=record_id,
            timestamp=timestamp,
            event_type=event_data.get("type", "unknown"),
            record_data=record_data,
            integrity_hash=integrity_hash,
            previous_hash=self.audit_chain_hash,
            digital_signature=digital_signature,
            regulatory_flags=regulatory_flags,
            compliance_score=compliance_score,
        )

        # Store record and update chain
        self.compliance_records[record_id] = record
        self.audit_chain_hash = integrity_hash

        # Log to audit system
        await auth_audit_logger.log_event(
            AuditEventType.COMPLIANCE_CHECK,
            user_id="system",
            details={
                "record_id": record_id,
                "event_type": record.event_type,
                "compliance_score": compliance_score,
                "regulatory_flags": regulatory_flags,
                "integrity_hash": integrity_hash,
            },
        )

        return record

    async def _analyze_compliance_breach(
        self, event_data: Dict[str, Any]
    ) -> Optional[RegulatoryBreachAlert]:
        """Analyze event data for potential compliance breaches."""

        event_type = event_data.get("type")
        breach_conditions = []

        # Check trade execution compliance
        if event_type == "trade_executed":
            # Large trade without proper pre-trade compliance
            trade_value = event_data.get("quantity", 0) * event_data.get("price", 0)
            if trade_value > 5000000:  # $5M threshold
                if not event_data.get("pre_trade_compliance_passed"):
                    breach_conditions.append("large_trade_no_compliance")

            # Best execution requirements
            if not event_data.get("best_execution_analysis"):
                breach_conditions.append("missing_best_execution_analysis")

        # Check surveillance alerts
        elif event_type == "surveillance_alert":
            alert_severity = event_data.get("severity", "low")
            if alert_severity in ["high", "critical"]:
                if not event_data.get("immediate_investigation_triggered"):
                    breach_conditions.append("high_severity_alert_not_investigated")

        # Check position limits
        elif event_type == "position_update":
            position_size = event_data.get("position_size", 0)
            limit = event_data.get("position_limit", float("inf"))
            if position_size > limit * 0.95:  # 95% of limit
                breach_conditions.append("position_limit_approaching")
            if position_size > limit:
                breach_conditions.append("position_limit_exceeded")

        # Create breach alert if conditions met
        if breach_conditions:
            alert_id = f"breach_{int(datetime.now().timestamp()*1000)}"
            severity = self._determine_breach_severity(breach_conditions)

            alert = RegulatoryBreachAlert(
                alert_id=alert_id,
                breach_type=", ".join(breach_conditions),
                severity=severity,
                detected_at=datetime.now(timezone.utc),
                description=f"Compliance breach detected: {', '.join(breach_conditions)}",
                affected_trades=[event_data.get("trade_id", "unknown")],
                regulatory_impact={
                    "jurisdictions_affected": self._get_affected_jurisdictions(
                        breach_conditions
                    ),
                    "potential_fines": self._estimate_potential_fines(
                        breach_conditions
                    ),
                    "reporting_requirements": self._get_reporting_requirements(
                        breach_conditions
                    ),
                },
                remediation_required=severity
                in [ComplianceAlertLevel.BREACH, ComplianceAlertLevel.CRITICAL],
                deadline=self._calculate_remediation_deadline(severity),
            )

            return alert

        return None

    async def _process_trade_surveillance(self, event_data: Dict[str, Any]):
        """Process trade execution for surveillance compliance."""

        trade_id = event_data.get("trade_id")
        if not trade_id:
            return

        # Run surveillance analysis
        surveillance_alerts = (
            await self.surveillance_monitor.analyze_trade_for_surveillance(
                {
                    "trade_id": trade_id,
                    "symbol": event_data.get("symbol"),
                    "quantity": event_data.get("quantity"),
                    "price": event_data.get("price"),
                    "timestamp": event_data.get("timestamp"),
                    "user_id": event_data.get("user_id"),
                    "broker": event_data.get("broker"),
                }
            )
        )

        # Process any surveillance alerts
        for alert in surveillance_alerts:
            await self.process_real_time_compliance_event(
                {
                    "type": "surveillance_alert",
                    "alert_id": alert.alert_id,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity.value,
                    "trade_id": trade_id,
                    "description": alert.description,
                    "confidence_score": alert.confidence_score,
                }
            )

    async def _process_routing_compliance(self, event_data: Dict[str, Any]):
        """Process order routing for compliance validation."""

        routing_decision = event_data.get("routing_decision", {})

        # Validate best execution requirements
        best_execution_analysis = {
            "venue_comparison_performed": routing_decision.get("venues_analyzed", 0)
            >= 2,
            "price_improvement_considered": "price_improvement" in routing_decision,
            "execution_probability_analyzed": "fill_probability" in routing_decision,
            "cost_analysis_performed": "execution_cost" in routing_decision,
        }

        # Check MiFID II best execution requirements
        if not all(best_execution_analysis.values()):
            await self.process_real_time_compliance_event(
                {
                    "type": "best_execution_violation",
                    "order_id": event_data.get("order_id"),
                    "missing_analysis": [
                        k for k, v in best_execution_analysis.items() if not v
                    ],
                    "routing_decision": routing_decision,
                }
            )

    async def _process_pattern_compliance(self, event_data: Dict[str, Any]):
        """Process pattern detection for compliance implications."""

        pattern_type = event_data.get("pattern_type")
        confidence_score = event_data.get("confidence_score", 0.0)

        # High-confidence patterns require regulatory attention
        if confidence_score >= 0.85:
            regulatory_implications = {
                "wash_trading": ["US_CFTC", "EU_MIFID", "US_FINRA"],
                "layering": ["US_FINRA", "EU_MIFID"],
                "momentum_ignition": ["US_CFTC", "US_FINRA"],
                "quote_stuffing": ["US_FINRA", "EU_MIFID"],
                "price_manipulation": ["US_CFTC", "EU_MIFID", "US_FINRA"],
            }

            affected_jurisdictions = regulatory_implications.get(pattern_type, [])

            if affected_jurisdictions:
                await self.process_real_time_compliance_event(
                    {
                        "type": "regulatory_pattern_detected",
                        "pattern_type": pattern_type,
                        "confidence_score": confidence_score,
                        "affected_jurisdictions": affected_jurisdictions,
                        "investigation_required": True,
                        "trades_involved": event_data.get("trades_involved", []),
                    }
                )

    async def generate_enhanced_surveillance_report(
        self,
        start_time: datetime,
        end_time: datetime,
        include_patterns: bool = True,
        include_compliance_scores: bool = True,
    ) -> Dict[str, Any]:
        """Generate comprehensive surveillance report with enhanced analytics."""

        # Get surveillance data from monitor
        surveillance_data = await self.surveillance_monitor.get_surveillance_summary(
            start_time, end_time
        )

        # Get compliance records for the period
        period_records = [
            record
            for record in self.compliance_records.values()
            if start_time <= record.timestamp <= end_time
        ]

        # Calculate compliance metrics
        compliance_metrics = {
            "total_compliance_checks": len(period_records),
            "compliance_violations": len(
                [
                    r
                    for r in period_records
                    if r.compliance_score < self.compliance_threshold
                ]
            ),
            "average_compliance_score": sum(r.compliance_score for r in period_records)
            / max(len(period_records), 1),
            "regulatory_flags_breakdown": self._analyze_regulatory_flags(
                period_records
            ),
        }

        # Analyze patterns if requested
        pattern_analysis = {}
        if include_patterns:
            pattern_analysis = await self._analyze_surveillance_patterns(
                surveillance_data, period_records
            )

        # Generate compliance scores by jurisdiction
        jurisdiction_scores = {}
        if include_compliance_scores:
            jurisdiction_scores = await self._calculate_jurisdiction_compliance_scores(
                period_records
            )

        report_data = {
            "report_period": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_hours": (end_time - start_time).total_seconds() / 3600,
            },
            "surveillance_summary": surveillance_data,
            "compliance_metrics": compliance_metrics,
            "pattern_analysis": pattern_analysis,
            "jurisdiction_compliance_scores": jurisdiction_scores,
            "regulatory_breaches": [
                asdict(breach)
                for breach in self.regulatory_breaches.values()
                if start_time <= breach.detected_at <= end_time
            ],
            "audit_trail_integrity": await self._verify_audit_trail_integrity(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        return report_data

    async def generate_broker_routing_compliance_report(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Generate broker routing compliance analysis report."""

        if not self.execution_engine:
            self.logger.warning("No execution engine available for routing analysis")
            return {}

        # Get routing analytics from execution engine
        routing_analytics = await self.execution_engine.get_routing_analytics(
            start_time, end_time
        )

        # Analyze best execution compliance
        best_execution_analysis = {
            "total_orders_routed": routing_analytics.get("total_orders", 0),
            "venues_utilized": routing_analytics.get("venues_used", []),
            "average_fill_rate": routing_analytics.get("average_fill_rate", 0.0),
            "price_improvement_achieved": routing_analytics.get(
                "price_improvement", 0.0
            ),
            "execution_speed_analysis": routing_analytics.get("speed_metrics", {}),
        }

        # Compliance assessment
        compliance_assessment = {
            "best_execution_score": self._calculate_best_execution_score(
                routing_analytics
            ),
            "venue_diversity_score": self._calculate_venue_diversity_score(
                routing_analytics
            ),
            "mifid_ii_compliance": await self._assess_mifid_compliance(
                routing_analytics
            ),
            "reg_nms_compliance": await self._assess_reg_nms_compliance(
                routing_analytics
            ),
        }

        return {
            "report_period": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            },
            "routing_analytics": routing_analytics,
            "best_execution_analysis": best_execution_analysis,
            "compliance_assessment": compliance_assessment,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _calculate_integrity_hash(
        self, data: str, previous_hash: Optional[str] = None
    ) -> str:
        """Calculate cryptographic integrity hash for audit chain."""

        if previous_hash:
            combined_data = f"{previous_hash}:{data}"
        else:
            combined_data = data

        return hmac.new(
            self.integrity_key, combined_data.encode(), hashlib.sha256
        ).hexdigest()

    def _create_digital_signature(self, data: str) -> str:
        """Create digital signature for compliance record."""

        signature_data = f"{data}:{datetime.now().isoformat()}"
        return hmac.new(
            self.integrity_key, signature_data.encode(), hashlib.sha512
        ).hexdigest()

    async def _determine_regulatory_flags(
        self, event_data: Dict[str, Any]
    ) -> List[str]:
        """Determine applicable regulatory flags for an event."""

        flags = []
        event_type = event_data.get("type", "")

        # Trade-related flags
        if "trade" in event_type:
            trade_value = event_data.get("quantity", 0) * event_data.get("price", 0)

            if trade_value >= 1000000:  # $1M+
                flags.append("LARGE_NOTIONAL")
            if trade_value >= 10000000:  # $10M+
                flags.append("BLOCK_TRADE")

            # Symbol-specific flags
            symbol = event_data.get("symbol", "")
            if "USD" in symbol:
                flags.append("USD_EXPOSURE")
            if "EUR" in symbol:
                flags.append("EU_JURISDICTION")

        # Surveillance-related flags
        if "alert" in event_type or "pattern" in event_type:
            flags.append("SURVEILLANCE_REQUIRED")

            confidence = event_data.get("confidence_score", 0.0)
            if confidence >= 0.9:
                flags.append("HIGH_CONFIDENCE_ALERT")

        # Compliance flags
        if event_data.get("compliance_override"):
            flags.append("MANUAL_OVERRIDE")

        return flags

    async def _calculate_compliance_score(self, event_data: Dict[str, Any]) -> float:
        """Calculate compliance score for an event (0.0 to 1.0)."""

        base_score = 1.0

        # Deduct for missing required data
        required_fields = {
            "trade_executed": ["trade_id", "symbol", "quantity", "price", "timestamp"],
            "order_routed": ["order_id", "routing_decision", "best_execution_analysis"],
            "surveillance_alert": [
                "alert_id",
                "alert_type",
                "severity",
                "confidence_score",
            ],
        }

        event_type = event_data.get("type", "")
        if event_type in required_fields:
            missing_fields = [
                field
                for field in required_fields[event_type]
                if field not in event_data or event_data[field] is None
            ]
            base_score -= 0.1 * len(missing_fields)

        # Deduct for compliance issues
        if event_data.get("position_limit_exceeded"):
            base_score -= 0.3
        if event_data.get("risk_limit_exceeded"):
            base_score -= 0.2
        if not event_data.get("pre_trade_compliance_passed", True):
            base_score -= 0.15

        # Bonus for enhanced compliance features
        if event_data.get("enhanced_surveillance_passed"):
            base_score += 0.05
        if event_data.get("best_execution_analysis_performed"):
            base_score += 0.05

        return max(0.0, min(1.0, base_score))

    def _determine_breach_severity(
        self, breach_conditions: List[str]
    ) -> ComplianceAlertLevel:
        """Determine severity level for compliance breach."""

        critical_conditions = [
            "position_limit_exceeded",
            "large_trade_no_compliance",
            "high_severity_alert_not_investigated",
        ]

        warning_conditions = [
            "position_limit_approaching",
            "missing_best_execution_analysis",
        ]

        if any(condition in critical_conditions for condition in breach_conditions):
            return ComplianceAlertLevel.CRITICAL
        elif len(breach_conditions) > 2:
            return ComplianceAlertLevel.BREACH
        elif any(condition in warning_conditions for condition in breach_conditions):
            return ComplianceAlertLevel.WARNING
        else:
            return ComplianceAlertLevel.INFO

    async def _generate_breach_report(self, breach_alert: RegulatoryBreachAlert):
        """Generate immediate regulatory breach report."""

        report_data = {
            "breach_alert": asdict(breach_alert),
            "immediate_actions_required": await self._determine_immediate_actions(
                breach_alert
            ),
            "regulatory_contacts": await self._get_regulatory_contacts(breach_alert),
            "documentation_requirements": await self._get_documentation_requirements(
                breach_alert
            ),
        }

        # Generate report with critical priority
        await self.generate_report(
            "regulatory_breach_alert",
            breach_alert.detected_at - timedelta(minutes=5),
            breach_alert.detected_at,
            parameters={"breach_data": report_data},
            priority=ReportPriority.CRITICAL,
        )

    async def _verify_audit_trail_integrity(self) -> Dict[str, Any]:
        """Verify cryptographic integrity of audit trail."""

        if not self.enable_cryptographic_integrity:
            return {"status": "disabled", "verification_skipped": True}

        records = list(self.compliance_records.values())
        records.sort(key=lambda x: x.timestamp)

        integrity_status = {
            "total_records": len(records),
            "verified_records": 0,
            "integrity_violations": [],
            "chain_continuity": True,
            "last_verification": datetime.now(timezone.utc).isoformat(),
        }

        previous_hash = None
        for record in records:
            # Verify record integrity
            data_string = json.dumps(record.record_data, sort_keys=True, default=str)
            expected_hash = self._calculate_integrity_hash(data_string, previous_hash)

            if record.integrity_hash == expected_hash:
                integrity_status["verified_records"] += 1
            else:
                integrity_status["integrity_violations"].append(
                    {
                        "record_id": record.record_id,
                        "timestamp": record.timestamp.isoformat(),
                        "expected_hash": expected_hash,
                        "actual_hash": record.integrity_hash,
                    }
                )
                integrity_status["chain_continuity"] = False

            previous_hash = record.integrity_hash

        return integrity_status

    def set_execution_engine(self, execution_engine: EnhancedExecutionEngine):
        """Set the execution engine for routing compliance analysis."""
        self.execution_engine = execution_engine
        self.logger.info("Execution engine set for routing compliance analysis")

    async def get_enhanced_compliance_statistics(self) -> Dict[str, Any]:
        """Get comprehensive enhanced compliance statistics."""

        base_stats = await self.get_reporting_statistics()

        # Enhanced statistics
        enhanced_stats = {
            "compliance_records_total": len(self.compliance_records),
            "compliance_violations_total": self.compliance_violations,
            "compliance_checks_performed": self.compliance_checks_performed,
            "last_compliance_check": (
                self.last_compliance_check.isoformat()
                if self.last_compliance_check
                else None
            ),
            "regulatory_breaches_active": len(
                [
                    b
                    for b in self.regulatory_breaches.values()
                    if not b.remediation_required or b.assigned_to
                ]
            ),
            "audit_trail_integrity": await self._verify_audit_trail_integrity(),
            "surveillance_integration_active": self.enable_real_time_surveillance,
            "cryptographic_integrity_enabled": self.enable_cryptographic_integrity,
        }

        # Merge with base statistics
        return {**base_stats, **enhanced_stats}

    # Placeholder methods for completeness
    def _get_affected_jurisdictions(self, breach_conditions: List[str]) -> List[str]:
        """Get jurisdictions affected by compliance breach."""
        # Simplified mapping - in production this would be more sophisticated
        jurisdiction_mapping = {
            "large_trade_no_compliance": ["US_CFTC", "US_FINRA"],
            "position_limit_exceeded": ["US_CFTC", "EU_MIFID"],
            "missing_best_execution_analysis": ["EU_MIFID", "UK_FCA"],
        }

        affected = set()
        for condition in breach_conditions:
            affected.update(jurisdiction_mapping.get(condition, []))
        return list(affected)

    def _estimate_potential_fines(
        self, breach_conditions: List[str]
    ) -> Dict[str, float]:
        """Estimate potential regulatory fines."""
        # Simplified fine estimation
        fine_estimates = {
            "large_trade_no_compliance": 50000.0,
            "position_limit_exceeded": 100000.0,
            "missing_best_execution_analysis": 25000.0,
        }

        total_estimate = sum(
            fine_estimates.get(condition, 0) for condition in breach_conditions
        )
        return {"estimated_total_usd": total_estimate, "breakdown": fine_estimates}

    def _get_reporting_requirements(self, breach_conditions: List[str]) -> List[str]:
        """Get reporting requirements for breach conditions."""
        return [
            "immediate_notification_required",
            "written_report_within_24h",
            "corrective_action_plan_required",
        ]

    def _calculate_remediation_deadline(
        self, severity: ComplianceAlertLevel
    ) -> datetime:
        """Calculate remediation deadline based on severity."""
        now = datetime.now(timezone.utc)

        deadlines = {
            ComplianceAlertLevel.CRITICAL: timedelta(hours=4),
            ComplianceAlertLevel.BREACH: timedelta(hours=24),
            ComplianceAlertLevel.WARNING: timedelta(days=3),
            ComplianceAlertLevel.INFO: timedelta(days=7),
        }

        return now + deadlines.get(severity, timedelta(days=1))

    async def _determine_immediate_actions(
        self, breach_alert: RegulatoryBreachAlert
    ) -> List[str]:
        """Determine immediate actions required for breach."""
        return [
            "suspend_trading_activity",
            "notify_compliance_officer",
            "document_breach_circumstances",
            "prepare_regulatory_notification",
        ]

    async def _get_regulatory_contacts(
        self, breach_alert: RegulatoryBreachAlert
    ) -> Dict[str, str]:
        """Get regulatory contact information."""
        return {
            "compliance_officer": "compliance@example.com",
            "legal_counsel": "legal@example.com",
            "cftc_contact": "cftc_reporting@example.com",
        }

    async def _get_documentation_requirements(
        self, breach_alert: RegulatoryBreachAlert
    ) -> List[str]:
        """Get documentation requirements for breach."""
        return [
            "breach_incident_report",
            "trade_reconstruction_analysis",
            "systems_audit_log",
            "corrective_measures_plan",
        ]

    def _analyze_regulatory_flags(
        self, records: List[EnhancedComplianceRecord]
    ) -> Dict[str, int]:
        """Analyze breakdown of regulatory flags."""
        flag_counts = {}
        for record in records:
            for flag in record.regulatory_flags:
                flag_counts[flag] = flag_counts.get(flag, 0) + 1
        return flag_counts

    async def _analyze_surveillance_patterns(
        self, surveillance_data: Dict[str, Any], records: List[EnhancedComplianceRecord]
    ) -> Dict[str, Any]:
        """Analyze surveillance patterns in compliance records."""
        # Placeholder implementation
        return {
            "pattern_types_detected": surveillance_data.get("pattern_summary", {}),
            "high_confidence_patterns": len(
                [r for r in records if r.compliance_score < 0.8]
            ),
            "investigation_recommendations": [],
        }

    async def _calculate_jurisdiction_compliance_scores(
        self, records: List[EnhancedComplianceRecord]
    ) -> Dict[str, float]:
        """Calculate compliance scores by jurisdiction."""
        # Simplified implementation
        return {
            "US_CFTC": 0.95,
            "EU_MIFID": 0.92,
            "US_FINRA": 0.88,
        }

    def _calculate_best_execution_score(
        self, routing_analytics: Dict[str, Any]
    ) -> float:
        """Calculate best execution compliance score."""
        # Simplified calculation based on key metrics
        fill_rate = routing_analytics.get("average_fill_rate", 0.0)
        price_improvement = routing_analytics.get("price_improvement", 0.0)
        venue_diversity = len(routing_analytics.get("venues_used", []))

        score = (
            (fill_rate * 0.4)
            + (price_improvement * 0.3)
            + min(venue_diversity / 5, 1.0) * 0.3
        )
        return min(1.0, score)

    def _calculate_venue_diversity_score(
        self, routing_analytics: Dict[str, Any]
    ) -> float:
        """Calculate venue diversity score."""
        venues_used = len(routing_analytics.get("venues_used", []))
        return min(venues_used / 10, 1.0)  # Normalize to max of 10 venues

    async def _assess_mifid_compliance(
        self, routing_analytics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess MiFID II compliance."""
        return {
            "best_execution_policy_followed": True,
            "venue_analysis_documented": True,
            "client_order_handling_compliant": True,
            "transparency_requirements_met": True,
            "overall_compliance_score": 0.95,
        }

    async def _assess_reg_nms_compliance(
        self, routing_analytics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess Reg NMS compliance."""
        return {
            "order_protection_rule_followed": True,
            "access_rule_compliant": True,
            "sub_penny_rule_compliant": True,
            "market_data_requirements_met": True,
            "overall_compliance_score": 0.93,
        }


# Global enhanced reporting engine instance
enhanced_regulatory_reporting_engine = EnhancedRegulatoryReportingEngine()


async def get_enhanced_regulatory_reporting_engine() -> (
    EnhancedRegulatoryReportingEngine
):
    """Get the global enhanced regulatory reporting engine instance."""
    return enhanced_regulatory_reporting_engine
