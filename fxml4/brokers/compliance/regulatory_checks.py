"""Regulatory Compliance Checks.

This module implements specific regulatory compliance checks for various
jurisdictions and frameworks (SEC, MiFID II, FISCA, etc.).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ...fix.messages.base import OrdType, Side
from ...fix.messages.orders import ExecutionReport, NewOrderSingle
from .compliance_engine import ComplianceRule, ComplianceViolation, ViolationSeverity

logger = logging.getLogger(__name__)


class RegulatoryJurisdiction(Enum):
    """Regulatory jurisdictions."""

    US_SEC = "US_SEC"  # Securities and Exchange Commission
    EU_MIFID = "EU_MIFID"  # Markets in Financial Instruments Directive
    UK_FCA = "UK_FCA"  # Financial Conduct Authority
    SINGAPORE_MAS = "SG_MAS"  # Monetary Authority of Singapore
    HONG_KONG_SFC = "HK_SFC"  # Securities and Futures Commission
    JAPAN_FSA = "JP_FSA"  # Financial Services Agency


@dataclass
class RegulatoryContext:
    """Context for regulatory compliance checks."""

    jurisdiction: RegulatoryJurisdiction
    client_type: str  # "retail", "professional", "institutional"
    client_classification: Optional[str] = None
    client_country: Optional[str] = None
    client_id: Optional[str] = None

    # Account information
    account_type: Optional[str] = None
    account_size: Optional[float] = None
    trading_experience: Optional[str] = None

    # Product information
    product_type: str = "spot_fx"
    leverage: Optional[float] = None
    complex_product: bool = False


class RegulatoryChecker:
    """Base class for regulatory compliance checkers."""

    def __init__(self, jurisdiction: RegulatoryJurisdiction):
        self.jurisdiction = jurisdiction
        self.enabled_rules: Set[str] = set()

    def create_rules(self) -> List[ComplianceRule]:
        """Create regulatory compliance rules for this jurisdiction."""
        return []


class SECCompliance(RegulatoryChecker):
    """SEC (US) compliance rules."""

    def __init__(self):
        super().__init__(RegulatoryJurisdiction.US_SEC)

    def create_rules(self) -> List[ComplianceRule]:
        """Create SEC compliance rules."""
        return [
            SECPositionReportingRule(),
            SECLargeTraderRule(),
            SECPatternDayTradingRule(),
            SECBestExecutionRule(),
        ]


class MiFIDIICompliance(RegulatoryChecker):
    """MiFID II (EU) compliance rules."""

    def __init__(self):
        super().__init__(RegulatoryJurisdiction.EU_MIFID)

    def create_rules(self) -> List[ComplianceRule]:
        """Create MiFID II compliance rules."""
        return [
            MiFIDClientClassificationRule(),
            MiFIDSuitabilityRule(),
            MiFIDRTSTransparencyRule(),
            MiFIDBestExecutionRule(),
            MiFIDProductGovernanceRule(),
        ]


class FISCACompliance(RegulatoryChecker):
    """FISCA (Singapore) compliance rules."""

    def __init__(self):
        super().__init__(RegulatoryJurisdiction.SINGAPORE_MAS)

    def create_rules(self) -> List[ComplianceRule]:
        """Create FISCA compliance rules."""
        return [FISCALeverageRule(), FISCAMarginRule(), FISCAClientMoneyRule()]


# SEC-specific rules


class SECPositionReportingRule(ComplianceRule):
    """SEC position reporting requirements."""

    def __init__(self):
        super().__init__(
            rule_id="SEC_POS_001",
            rule_name="SEC Position Reporting",
            description="Monitors positions for SEC reporting thresholds",
            severity=ViolationSeverity.HIGH,
        )

        # SEC reporting thresholds
        self.position_threshold = 10_000_000  # $10M
        self.ownership_threshold = 0.05  # 5%

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check order for SEC position reporting requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Get regulatory context
        reg_context = context.get("regulatory_context")
        if not reg_context or reg_context.jurisdiction != RegulatoryJurisdiction.US_SEC:
            return None

        # Calculate position value
        if not hasattr(order, "price") or not order.price:
            return None

        order_value = order.order_qty * order.price
        current_position_value = context.get("position_values", {}).get(order.symbol, 0)
        new_position_value = abs(
            current_position_value
            + (order_value if order.side == Side.BUY else -order_value)
        )

        # Check reporting threshold
        if new_position_value > self.position_threshold:
            self.violations_found += 1

            return self._create_violation(
                violation_type="SEC_POSITION_REPORTING_REQUIRED",
                message=f"Position exceeds SEC reporting threshold for {order.symbol}",
                details={
                    "current_position_value": current_position_value,
                    "order_value": order_value,
                    "new_position_value": new_position_value,
                    "reporting_threshold": self.position_threshold,
                    "regulatory_reference": "SEC Rule 13d-1",
                },
                cl_ord_id=order.cl_ord_id,
                symbol=order.symbol,
                suggested_action="File required SEC position reports",
                requires_manual_review=True,
            )

        return None


class SECLargeTraderRule(ComplianceRule):
    """SEC Large Trader reporting rule."""

    def __init__(self):
        super().__init__(
            rule_id="SEC_LT_001",
            rule_name="SEC Large Trader Rule",
            description="Monitors for Large Trader identification requirements",
            severity=ViolationSeverity.MEDIUM,
        )

        self.daily_volume_threshold = 2_000_000  # $2M daily volume
        self.monthly_volume_threshold = 20_000_000  # $20M monthly volume

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check for Large Trader identification requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Get trading volumes
        daily_volume = context.get("daily_trading_volume", 0)
        monthly_volume = context.get("monthly_trading_volume", 0)

        if not hasattr(order, "price") or not order.price:
            return None

        order_value = order.order_qty * order.price

        # Check if this order would trigger Large Trader status
        if (
            daily_volume + order_value > self.daily_volume_threshold
            or monthly_volume + order_value > self.monthly_volume_threshold
        ):

            # Check if Large Trader ID is registered
            large_trader_id = context.get("large_trader_id")
            if not large_trader_id:
                self.violations_found += 1

                return self._create_violation(
                    violation_type="SEC_LARGE_TRADER_ID_REQUIRED",
                    message="Large Trader identification required",
                    details={
                        "daily_volume": daily_volume,
                        "monthly_volume": monthly_volume,
                        "order_value": order_value,
                        "daily_threshold": self.daily_volume_threshold,
                        "monthly_threshold": self.monthly_volume_threshold,
                        "regulatory_reference": "SEC Rule 13h-1",
                    },
                    cl_ord_id=order.cl_ord_id,
                    suggested_action="Register for Large Trader identification",
                    requires_manual_review=True,
                )

        return None


class SECPatternDayTradingRule(ComplianceRule):
    """SEC Pattern Day Trading rule."""

    def __init__(self):
        super().__init__(
            rule_id="SEC_PDT_001",
            rule_name="SEC Pattern Day Trading Rule",
            description="Monitors Pattern Day Trading requirements",
            severity=ViolationSeverity.HIGH,
        )

        self.min_equity_requirement = 25_000  # $25,000 minimum equity
        self.day_trade_threshold = 4  # 4 day trades in 5 business days

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check Pattern Day Trading requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Get account information
        account_equity = context.get("account_equity", 0)
        recent_day_trades = context.get("recent_day_trades", 0)

        # Check if this would be a day trade
        existing_position = context.get("positions", {}).get(order.symbol, 0)
        is_closing_trade = (order.side == Side.SELL and existing_position > 0) or (
            order.side == Side.BUY and existing_position < 0
        )

        if is_closing_trade:
            # This could be a day trade
            if (
                recent_day_trades >= self.day_trade_threshold - 1
            ):  # This would be the 4th
                if account_equity < self.min_equity_requirement:
                    self.violations_found += 1

                    return self._create_violation(
                        violation_type="SEC_PATTERN_DAY_TRADING_VIOLATION",
                        message="Pattern Day Trader minimum equity requirement not met",
                        details={
                            "account_equity": account_equity,
                            "min_equity_requirement": self.min_equity_requirement,
                            "recent_day_trades": recent_day_trades,
                            "regulatory_reference": "FINRA Rule 4210",
                        },
                        cl_ord_id=order.cl_ord_id,
                        symbol=order.symbol,
                        suggested_action="Increase account equity or reduce day trading",
                        auto_block=True,
                    )

        return None


class SECBestExecutionRule(ComplianceRule):
    """SEC Best Execution requirements."""

    def __init__(self):
        super().__init__(
            rule_id="SEC_BE_001",
            rule_name="SEC Best Execution",
            description="Monitors best execution requirements",
            severity=ViolationSeverity.MEDIUM,
        )

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check best execution requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Check if order routing analysis was performed
        routing_analysis = context.get("routing_analysis")
        if not routing_analysis:
            self.violations_found += 1

            return self._create_violation(
                violation_type="SEC_BEST_EXECUTION_ANALYSIS_MISSING",
                message="Best execution analysis not performed",
                details={"regulatory_reference": "SEC Rule 11Ac1-5"},
                cl_ord_id=order.cl_ord_id,
                symbol=order.symbol,
                suggested_action="Perform best execution analysis before routing",
                requires_manual_review=True,
            )

        return None


# MiFID II-specific rules


class MiFIDClientClassificationRule(ComplianceRule):
    """MiFID II client classification requirements."""

    def __init__(self):
        super().__init__(
            rule_id="MIFID_CC_001",
            rule_name="MiFID II Client Classification",
            description="Ensures proper client classification",
            severity=ViolationSeverity.HIGH,
        )

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check client classification requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        reg_context = context.get("regulatory_context")
        if (
            not reg_context
            or reg_context.jurisdiction != RegulatoryJurisdiction.EU_MIFID
        ):
            return None

        # Check if client is properly classified
        if not reg_context.client_classification:
            self.violations_found += 1

            return self._create_violation(
                violation_type="MIFID_CLIENT_CLASSIFICATION_MISSING",
                message="Client classification not determined",
                details={"regulatory_reference": "MiFID II Article 30"},
                cl_ord_id=order.cl_ord_id,
                suggested_action="Complete client classification assessment",
                auto_block=True,
            )

        return None


class MiFIDSuitabilityRule(ComplianceRule):
    """MiFID II suitability and appropriateness checks."""

    def __init__(self):
        super().__init__(
            rule_id="MIFID_SUIT_001",
            rule_name="MiFID II Suitability",
            description="Checks suitability and appropriateness",
            severity=ViolationSeverity.HIGH,
        )

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check suitability requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        reg_context = context.get("regulatory_context")
        if not reg_context:
            return None

        # For retail clients, check appropriateness
        if reg_context.client_type == "retail":
            appropriateness_assessment = context.get("appropriateness_assessment")
            if not appropriateness_assessment:
                self.violations_found += 1

                return self._create_violation(
                    violation_type="MIFID_APPROPRIATENESS_MISSING",
                    message="Appropriateness assessment required for retail client",
                    details={
                        "client_type": reg_context.client_type,
                        "regulatory_reference": "MiFID II Article 25",
                    },
                    cl_ord_id=order.cl_ord_id,
                    symbol=order.symbol,
                    suggested_action="Complete appropriateness assessment",
                    auto_block=True,
                )

        # For complex products, additional checks
        if reg_context.complex_product:
            suitability_assessment = context.get("suitability_assessment")
            if not suitability_assessment:
                self.violations_found += 1

                return self._create_violation(
                    violation_type="MIFID_SUITABILITY_MISSING",
                    message="Suitability assessment required for complex product",
                    details={
                        "product_type": reg_context.product_type,
                        "complex_product": reg_context.complex_product,
                        "regulatory_reference": "MiFID II Article 25",
                    },
                    cl_ord_id=order.cl_ord_id,
                    symbol=order.symbol,
                    suggested_action="Complete suitability assessment",
                    auto_block=True,
                )

        return None


class MiFIDRTSTransparencyRule(ComplianceRule):
    """MiFID II RTS transparency requirements."""

    def __init__(self):
        super().__init__(
            rule_id="MIFID_RTS_001",
            rule_name="MiFID II RTS Transparency",
            description="Regulatory Technical Standards transparency",
            severity=ViolationSeverity.MEDIUM,
        )

        self.large_in_scale_threshold = 2_500_000  # EUR 2.5M

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check RTS transparency requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        if not hasattr(order, "price") or not order.price:
            return None

        order_value = order.order_qty * order.price

        # Check if order is "large in scale"
        if order_value > self.large_in_scale_threshold:
            transparency_waiver = context.get("transparency_waiver")
            if not transparency_waiver:
                self.violations_found += 1

                return self._create_violation(
                    violation_type="MIFID_TRANSPARENCY_WAIVER_REQUIRED",
                    message="Large in scale order requires transparency considerations",
                    details={
                        "order_value": order_value,
                        "lis_threshold": self.large_in_scale_threshold,
                        "regulatory_reference": "MiFID II RTS 1",
                    },
                    cl_ord_id=order.cl_ord_id,
                    symbol=order.symbol,
                    suggested_action="Assess transparency waiver requirements",
                    requires_manual_review=True,
                )

        return None


class MiFIDBestExecutionRule(ComplianceRule):
    """MiFID II best execution requirements."""

    def __init__(self):
        super().__init__(
            rule_id="MIFID_BE_001",
            rule_name="MiFID II Best Execution",
            description="Best execution under MiFID II",
            severity=ViolationSeverity.MEDIUM,
        )

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check MiFID II best execution requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Check execution policy compliance
        execution_policy = context.get("execution_policy")
        if not execution_policy:
            self.violations_found += 1

            return self._create_violation(
                violation_type="MIFID_EXECUTION_POLICY_MISSING",
                message="Execution policy not defined",
                details={"regulatory_reference": "MiFID II Article 27"},
                cl_ord_id=order.cl_ord_id,
                suggested_action="Establish execution policy",
                requires_manual_review=True,
            )

        return None


class MiFIDProductGovernanceRule(ComplianceRule):
    """MiFID II product governance requirements."""

    def __init__(self):
        super().__init__(
            rule_id="MIFID_PG_001",
            rule_name="MiFID II Product Governance",
            description="Product governance requirements",
            severity=ViolationSeverity.MEDIUM,
        )

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check product governance requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Check target market assessment
        target_market = context.get("target_market")
        if not target_market:
            self.violations_found += 1

            return self._create_violation(
                violation_type="MIFID_TARGET_MARKET_MISSING",
                message="Target market not defined for product",
                details={"regulatory_reference": "MiFID II Article 16"},
                cl_ord_id=order.cl_ord_id,
                symbol=order.symbol,
                suggested_action="Define target market for product",
                requires_manual_review=True,
            )

        return None


# FISCA-specific rules


class FISCALeverageRule(ComplianceRule):
    """FISCA leverage limits."""

    def __init__(self):
        super().__init__(
            rule_id="FISCA_LEV_001",
            rule_name="FISCA Leverage Limits",
            description="FISCA leverage restrictions",
            severity=ViolationSeverity.HIGH,
        )

        # FISCA leverage limits by client type
        self.leverage_limits = {
            "retail": 20,  # 20:1 for retail
            "professional": 50,  # 50:1 for professional
            "institutional": 100,  # 100:1 for institutional
        }

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check FISCA leverage limits."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        reg_context = context.get("regulatory_context")
        if (
            not reg_context
            or reg_context.jurisdiction != RegulatoryJurisdiction.SINGAPORE_MAS
        ):
            return None

        # Get current leverage
        current_leverage = reg_context.leverage or context.get("current_leverage", 1)
        max_leverage = self.leverage_limits.get(reg_context.client_type, 1)

        if current_leverage > max_leverage:
            self.violations_found += 1

            return self._create_violation(
                violation_type="FISCA_LEVERAGE_EXCEEDED",
                message=f"Leverage exceeds FISCA limits for {reg_context.client_type} client",
                details={
                    "current_leverage": current_leverage,
                    "max_leverage": max_leverage,
                    "client_type": reg_context.client_type,
                    "regulatory_reference": "FISCA Section 99",
                },
                cl_ord_id=order.cl_ord_id,
                symbol=order.symbol,
                suggested_action="Reduce leverage or close positions",
                auto_block=True,
            )

        return None


class FISCAMarginRule(ComplianceRule):
    """FISCA margin requirements."""

    def __init__(self):
        super().__init__(
            rule_id="FISCA_MAR_001",
            rule_name="FISCA Margin Requirements",
            description="FISCA margin call requirements",
            severity=ViolationSeverity.HIGH,
        )

        self.margin_call_level = 0.5  # 50% margin call level
        self.stop_out_level = 0.2  # 20% stop out level

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check FISCA margin requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Get margin levels
        margin_level = context.get("margin_level", 1.0)

        if margin_level < self.stop_out_level:
            self.violations_found += 1

            return self._create_violation(
                violation_type="FISCA_MARGIN_STOP_OUT",
                message="Account below stop out level",
                details={
                    "margin_level": margin_level,
                    "stop_out_level": self.stop_out_level,
                    "regulatory_reference": "FISCA Margin Rules",
                },
                cl_ord_id=order.cl_ord_id,
                suggested_action="Close positions or add margin",
                auto_block=True,
            )

        elif margin_level < self.margin_call_level:
            self.violations_found += 1

            return self._create_violation(
                violation_type="FISCA_MARGIN_CALL",
                message="Margin call level reached",
                details={
                    "margin_level": margin_level,
                    "margin_call_level": self.margin_call_level,
                    "regulatory_reference": "FISCA Margin Rules",
                },
                cl_ord_id=order.cl_ord_id,
                suggested_action="Add margin or reduce positions",
                requires_manual_review=True,
            )

        return None


class FISCAClientMoneyRule(ComplianceRule):
    """FISCA client money protection."""

    def __init__(self):
        super().__init__(
            rule_id="FISCA_CM_001",
            rule_name="FISCA Client Money Protection",
            description="Client money segregation requirements",
            severity=ViolationSeverity.CRITICAL,
        )

    async def check_order(
        self, order: NewOrderSingle, context: Dict[str, Any]
    ) -> Optional[ComplianceViolation]:
        """Check client money protection requirements."""
        self.checks_performed += 1
        self.last_check_time = datetime.now(timezone.utc)

        # Check segregation status
        segregation_status = context.get("client_money_segregated", False)
        if not segregation_status:
            self.violations_found += 1

            return self._create_violation(
                violation_type="FISCA_CLIENT_MONEY_NOT_SEGREGATED",
                message="Client money not properly segregated",
                details={"regulatory_reference": "FISCA Section 107"},
                cl_ord_id=order.cl_ord_id,
                suggested_action="Ensure client money segregation",
                auto_block=True,
            )

        return None
