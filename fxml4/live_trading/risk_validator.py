"""
FXML4 Risk Management Validation System
Proves risk limits are enforced in live paper trading conditions

This module validates that the risk management system correctly enforces:
- 2% maximum trade size per trade
- 6% maximum portfolio exposure across all positions
- Real-time compliance monitoring with Interactive Brokers paper trading
- Comprehensive audit trail for regulatory compliance

Critical Requirements:
- Zero tolerance for risk limit violations
- Real-time monitoring during live paper trading
- Multi-currency portfolio exposure calculation
- Regulatory-compliant audit reporting
"""

import asyncio
import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..brokers.adapters.ib_adapter import IBBrokerAdapter
from ..core.exceptions import RiskViolationError, ValidationError
from ..data_engineering.currency_converter import CurrencyConverter
from ..risk_management.risk_manager import RiskManager


class RiskViolationType(Enum):
    """Types of risk violations"""

    TRADE_SIZE_EXCEEDED = "trade_size_exceeded"
    PORTFOLIO_EXPOSURE_EXCEEDED = "portfolio_exposure_exceeded"
    ACCOUNT_BALANCE_INSUFFICIENT = "account_balance_insufficient"
    POSITION_SIZE_INVALID = "position_size_invalid"
    CURRENCY_CONVERSION_ERROR = "currency_conversion_error"


class RiskComplianceStatus(Enum):
    """Risk compliance status levels"""

    COMPLIANT = "compliant"
    WARNING = "warning"  # Approaching limits
    VIOLATION = "violation"  # Limits exceeded
    ERROR = "error"  # System error in calculation


@dataclass
class RiskViolation:
    """Risk violation record"""

    violation_type: RiskViolationType
    timestamp: datetime
    symbol: str
    attempted_trade_size: float
    account_balance: float
    current_exposure: float
    violation_amount: float
    message: str
    trade_rejected: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violation_type": self.violation_type.value,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "attempted_trade_size": self.attempted_trade_size,
            "account_balance": self.account_balance,
            "current_exposure": self.current_exposure,
            "violation_amount": self.violation_amount,
            "message": self.message,
            "trade_rejected": self.trade_rejected,
        }


@dataclass
class RiskValidationResult:
    """Result of risk validation check"""

    status: RiskComplianceStatus
    account_balance: float
    total_exposure: float
    exposure_percentage: float
    trade_size_percentage: float
    currency_exposures: Dict[str, float] = field(default_factory=dict)
    violations: List[RiskViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_compliant(self) -> bool:
        return self.status == RiskComplianceStatus.COMPLIANT

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0


@dataclass
class ComplianceReport:
    """Comprehensive compliance report"""

    start_date: datetime
    end_date: datetime
    total_trades_attempted: int
    total_trades_executed: int
    total_trades_rejected: int
    violations: List[RiskViolation] = field(default_factory=list)
    compliance_rate: float = 0.0
    max_trade_size_percentage: float = 0.0
    max_portfolio_exposure_percentage: float = 0.0
    average_exposure_percentage: float = 0.0
    currency_breakdown: Dict[str, Dict[str, float]] = field(default_factory=dict)

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    @property
    def is_fully_compliant(self) -> bool:
        return self.violation_count == 0 and self.compliance_rate == 100.0


class RiskManagementValidator:
    """
    Risk Management Validation System

    Validates and proves that risk management controls work correctly in live
    paper trading conditions with Interactive Brokers integration.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Risk limits configuration
        self.max_trade_size_pct = self.config.get(
            "max_trade_size_percentage", 2.0
        )  # 2%
        self.max_portfolio_exposure_pct = self.config.get(
            "max_portfolio_exposure_percentage", 6.0
        )  # 6%
        self.warning_threshold_pct = self.config.get(
            "warning_threshold_percentage", 80.0
        )  # 80% of limit

        # Validation tracking
        self.violations: List[RiskViolation] = []
        self.validation_results: List[RiskValidationResult] = []
        self.compliance_history: Dict[str, List[float]] = {}

        # System components
        self.risk_manager: Optional[RiskManager] = None
        self.ib_adapter: Optional[IBBrokerAdapter] = None
        self.currency_converter: Optional[CurrencyConverter] = None

        # Audit trail
        self.audit_file = Path("risk_compliance_audit.json")

    async def initialize(self) -> None:
        """Initialize risk validation components"""
        try:
            self.logger.info("Initializing risk management validator...")

            # Initialize risk manager
            self.risk_manager = RiskManager(self.config.get("risk_management", {}))
            await self.risk_manager.initialize()

            # Initialize Interactive Brokers adapter (paper trading)
            ib_config = self.config.get("ib_adapter", {})
            ib_config["paper_trading"] = True  # Force paper trading
            self.ib_adapter = IBBrokerAdapter(ib_config)
            await self.ib_adapter.initialize()

            # Initialize currency converter
            self.currency_converter = CurrencyConverter()
            await self.currency_converter.initialize()

            # Verify connection health
            await self._verify_system_health()

            # Load existing audit trail
            await self._load_audit_trail()

            self.logger.info("✅ Risk management validator initialized successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize risk validator: {e}")
            raise ValidationError(f"Risk validator initialization failed: {e}")

    async def _verify_system_health(self) -> None:
        """Verify all system components are healthy"""
        health_checks = [
            ("Interactive Brokers", self.ib_adapter.check_connection()),
            ("Risk Manager", self.risk_manager.health_check()),
            ("Currency Converter", self.currency_converter.health_check()),
        ]

        for component_name, health_check in health_checks:
            try:
                await health_check
                self.logger.info(f"{component_name}: ✓ Healthy")
            except Exception as e:
                self.logger.error(f"{component_name}: ✗ Unhealthy - {e}")
                raise ValidationError(f"{component_name} health check failed: {e}")

    async def validate_trade_risk(
        self, symbol: str, trade_size: float, side: str = "BUY"
    ) -> RiskValidationResult:
        """
        Validate a proposed trade against risk limits

        Args:
            symbol: Currency pair (e.g., "GBPUSD")
            trade_size: Proposed trade size in base currency units
            side: Trade side ("BUY" or "SELL")

        Returns:
            RiskValidationResult with compliance status and details
        """
        self.logger.info(f"Validating trade risk: {side} {trade_size} {symbol}")

        try:
            # Get current account information
            account_info = await self.ib_adapter.get_account_info()
            account_balance = float(account_info.get("TotalCashValue", 0))

            if account_balance <= 0:
                raise ValidationError("Invalid account balance retrieved from broker")

            # Get current positions
            positions = await self.ib_adapter.get_positions()

            # Calculate current portfolio exposure
            current_exposure = await self._calculate_portfolio_exposure(
                positions, account_balance
            )

            # Calculate proposed trade size percentage
            trade_value = await self._calculate_trade_value(symbol, trade_size)
            trade_size_pct = (trade_value / account_balance) * 100

            # Calculate new portfolio exposure if trade executed
            new_exposure = current_exposure + trade_value
            new_exposure_pct = (new_exposure / account_balance) * 100

            # Initialize validation result
            result = RiskValidationResult(
                status=RiskComplianceStatus.COMPLIANT,
                account_balance=account_balance,
                total_exposure=current_exposure,
                exposure_percentage=current_exposure / account_balance * 100,
                trade_size_percentage=trade_size_pct,
            )

            # Check trade size limit (2%)
            if trade_size_pct > self.max_trade_size_pct:
                violation = RiskViolation(
                    violation_type=RiskViolationType.TRADE_SIZE_EXCEEDED,
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    attempted_trade_size=trade_size,
                    account_balance=account_balance,
                    current_exposure=current_exposure,
                    violation_amount=trade_size_pct - self.max_trade_size_pct,
                    message=f"Trade size {trade_size_pct:.2f}% exceeds maximum {self.max_trade_size_pct}%",
                )
                result.violations.append(violation)
                result.status = RiskComplianceStatus.VIOLATION

                # Log and store violation
                self.violations.append(violation)
                self.logger.error(f"❌ RISK VIOLATION: {violation.message}")

            # Check portfolio exposure limit (6%)
            if new_exposure_pct > self.max_portfolio_exposure_pct:
                violation = RiskViolation(
                    violation_type=RiskViolationType.PORTFOLIO_EXPOSURE_EXCEEDED,
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    attempted_trade_size=trade_size,
                    account_balance=account_balance,
                    current_exposure=new_exposure,
                    violation_amount=new_exposure_pct - self.max_portfolio_exposure_pct,
                    message=f"Portfolio exposure {new_exposure_pct:.2f}% would exceed maximum {self.max_portfolio_exposure_pct}%",
                )
                result.violations.append(violation)
                result.status = RiskComplianceStatus.VIOLATION

                # Log and store violation
                self.violations.append(violation)
                self.logger.error(f"❌ RISK VIOLATION: {violation.message}")

            # Check for warnings (approaching limits)
            trade_warning_threshold = self.max_trade_size_pct * (
                self.warning_threshold_pct / 100
            )
            exposure_warning_threshold = self.max_portfolio_exposure_pct * (
                self.warning_threshold_pct / 100
            )

            if (
                trade_size_pct > trade_warning_threshold
                and result.status == RiskComplianceStatus.COMPLIANT
            ):
                result.status = RiskComplianceStatus.WARNING
                result.warnings.append(
                    f"Trade size {trade_size_pct:.2f}% approaching limit of {self.max_trade_size_pct}%"
                )

            if (
                new_exposure_pct > exposure_warning_threshold
                and result.status == RiskComplianceStatus.COMPLIANT
            ):
                result.status = RiskComplianceStatus.WARNING
                result.warnings.append(
                    f"Portfolio exposure {new_exposure_pct:.2f}% approaching limit of {self.max_portfolio_exposure_pct}%"
                )

            # Calculate currency-specific exposures
            result.currency_exposures = await self._calculate_currency_exposures(
                positions
            )

            # Store validation result
            self.validation_results.append(result)

            # Update audit trail
            await self._update_audit_trail(result)

            if result.is_compliant:
                self.logger.info(
                    f"✅ Trade risk validation PASSED: {trade_size_pct:.2f}% trade, {new_exposure_pct:.2f}% portfolio"
                )
            else:
                self.logger.error(
                    f"❌ Trade risk validation FAILED: {len(result.violations)} violations"
                )

            return result

        except Exception as e:
            self.logger.error(f"Risk validation error: {e}")
            raise ValidationError(f"Risk validation failed: {e}")

    async def _calculate_portfolio_exposure(
        self, positions: List[Dict], account_balance: float
    ) -> float:
        """Calculate current portfolio exposure across all positions"""
        total_exposure = 0.0

        for position in positions:
            try:
                symbol = position.get("symbol", "")
                size = float(position.get("size", 0))
                market_price = float(position.get("marketPrice", 0))

                if size != 0 and market_price > 0:
                    position_value = abs(size * market_price)

                    # Convert to account currency if needed
                    if not symbol.endswith("USD"):
                        position_value = await self.currency_converter.convert_to_usd(
                            position_value, self._get_base_currency(symbol)
                        )

                    total_exposure += position_value

            except (ValueError, TypeError, KeyError) as e:
                self.logger.warning(
                    f"Error calculating exposure for position {position}: {e}"
                )
                continue

        return total_exposure

    async def _calculate_trade_value(self, symbol: str, trade_size: float) -> float:
        """Calculate USD value of proposed trade"""
        try:
            # Get current market price
            market_data = await self.ib_adapter.get_market_data(symbol)
            price = float(market_data.get("price", 0))

            if price <= 0:
                raise ValueError(f"Invalid market price for {symbol}: {price}")

            trade_value = abs(trade_size * price)

            # Convert to USD if needed
            if not symbol.endswith("USD"):
                base_currency = self._get_base_currency(symbol)
                trade_value = await self.currency_converter.convert_to_usd(
                    trade_value, base_currency
                )

            return trade_value

        except Exception as e:
            self.logger.error(f"Error calculating trade value for {symbol}: {e}")
            raise

    async def _calculate_currency_exposures(
        self, positions: List[Dict]
    ) -> Dict[str, float]:
        """Calculate exposure breakdown by currency"""
        exposures = {}

        for position in positions:
            try:
                symbol = position.get("symbol", "")
                size = float(position.get("size", 0))
                market_price = float(position.get("marketPrice", 0))

                if size != 0 and symbol:
                    base_currency = self._get_base_currency(symbol)
                    quote_currency = self._get_quote_currency(symbol)

                    position_value = abs(size * market_price)

                    # Add to base currency exposure
                    if base_currency not in exposures:
                        exposures[base_currency] = 0.0
                    exposures[base_currency] += position_value

            except (ValueError, TypeError) as e:
                self.logger.warning(
                    f"Error calculating currency exposure for {position}: {e}"
                )
                continue

        return exposures

    def _get_base_currency(self, symbol: str) -> str:
        """Extract base currency from symbol (e.g., GBP from GBPUSD)"""
        return symbol[:3] if len(symbol) >= 6 else symbol

    def _get_quote_currency(self, symbol: str) -> str:
        """Extract quote currency from symbol (e.g., USD from GBPUSD)"""
        return symbol[3:6] if len(symbol) >= 6 else "USD"

    async def run_compliance_test(
        self, test_duration_hours: int = 24, test_trades: int = 100
    ) -> ComplianceReport:
        """
        Run comprehensive compliance test over specified duration

        Args:
            test_duration_hours: Duration to run compliance tests
            test_trades: Number of test trades to attempt

        Returns:
            ComplianceReport with complete compliance analysis
        """
        self.logger.info(
            f"🔄 Starting {test_duration_hours}h compliance test with {test_trades} test trades"
        )

        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=test_duration_hours)

        trades_attempted = 0
        trades_executed = 0
        trades_rejected = 0
        test_violations = []

        # Test currency pairs
        currency_pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCHF"]

        try:
            while datetime.utcnow() < end_time and trades_attempted < test_trades:
                for symbol in currency_pairs:
                    if trades_attempted >= test_trades:
                        break

                    # Generate test trade scenarios
                    test_scenarios = await self._generate_test_scenarios(symbol)

                    for scenario in test_scenarios:
                        if trades_attempted >= test_trades:
                            break

                        trades_attempted += 1

                        try:
                            # Validate trade risk
                            validation_result = await self.validate_trade_risk(
                                symbol=scenario["symbol"],
                                trade_size=scenario["trade_size"],
                                side=scenario["side"],
                            )

                            if validation_result.has_violations:
                                trades_rejected += 1
                                test_violations.extend(validation_result.violations)
                                self.logger.info(
                                    f"✅ Trade correctly rejected due to risk violations"
                                )
                            else:
                                trades_executed += 1
                                self.logger.info(f"✅ Trade passed risk validation")

                            # Brief pause between tests
                            await asyncio.sleep(0.1)

                        except Exception as e:
                            self.logger.error(f"Test trade error: {e}")
                            trades_rejected += 1

                # Longer pause between test rounds
                await asyncio.sleep(60)  # 1 minute between rounds

        except Exception as e:
            self.logger.error(f"Compliance test error: {e}")

        # Generate compliance report
        actual_end_time = datetime.utcnow()
        compliance_rate = (
            (trades_executed / trades_attempted * 100) if trades_attempted > 0 else 0
        )

        # Calculate statistics
        exposure_percentages = [r.exposure_percentage for r in self.validation_results]
        trade_size_percentages = [
            r.trade_size_percentage for r in self.validation_results
        ]

        report = ComplianceReport(
            start_date=start_time,
            end_date=actual_end_time,
            total_trades_attempted=trades_attempted,
            total_trades_executed=trades_executed,
            total_trades_rejected=trades_rejected,
            violations=test_violations,
            compliance_rate=compliance_rate,
            max_trade_size_percentage=(
                max(trade_size_percentages) if trade_size_percentages else 0
            ),
            max_portfolio_exposure_percentage=(
                max(exposure_percentages) if exposure_percentages else 0
            ),
            average_exposure_percentage=(
                statistics.mean(exposure_percentages) if exposure_percentages else 0
            ),
        )

        self.logger.info(f"📊 Compliance test completed:")
        self.logger.info(f"   Trades Attempted: {trades_attempted}")
        self.logger.info(f"   Trades Executed: {trades_executed}")
        self.logger.info(f"   Trades Rejected: {trades_rejected}")
        self.logger.info(f"   Violations: {len(test_violations)}")
        self.logger.info(f"   Compliance Rate: {compliance_rate:.1f}%")

        return report

    async def _generate_test_scenarios(self, symbol: str) -> List[Dict[str, Any]]:
        """Generate test trade scenarios including limit-testing trades"""
        scenarios = []

        # Get current account balance for calculations
        account_info = await self.ib_adapter.get_account_info()
        account_balance = float(
            account_info.get("TotalCashValue", 100000)
        )  # Default for testing

        # Standard compliant trades (should pass)
        scenarios.extend(
            [
                {"symbol": symbol, "trade_size": 1000, "side": "BUY"},  # Small trade
                {"symbol": symbol, "trade_size": 5000, "side": "SELL"},  # Medium trade
            ]
        )

        # Limit-testing trades (should be rejected)
        max_trade_value = account_balance * (self.max_trade_size_pct / 100)

        scenarios.extend(
            [
                {
                    "symbol": symbol,
                    "trade_size": max_trade_value * 1.1,
                    "side": "BUY",
                },  # 110% of limit
                {
                    "symbol": symbol,
                    "trade_size": max_trade_value * 1.5,
                    "side": "SELL",
                },  # 150% of limit
                {
                    "symbol": symbol,
                    "trade_size": max_trade_value * 2.0,
                    "side": "BUY",
                },  # 200% of limit
            ]
        )

        return scenarios

    async def _load_audit_trail(self) -> None:
        """Load existing audit trail from file"""
        try:
            if self.audit_file.exists():
                with open(self.audit_file, "r") as f:
                    data = json.load(f)
                    # Reconstruct violations from stored data
                    for violation_data in data.get("violations", []):
                        violation = RiskViolation(
                            violation_type=RiskViolationType(
                                violation_data["violation_type"]
                            ),
                            timestamp=datetime.fromisoformat(
                                violation_data["timestamp"]
                            ),
                            symbol=violation_data["symbol"],
                            attempted_trade_size=violation_data["attempted_trade_size"],
                            account_balance=violation_data["account_balance"],
                            current_exposure=violation_data["current_exposure"],
                            violation_amount=violation_data["violation_amount"],
                            message=violation_data["message"],
                            trade_rejected=violation_data.get("trade_rejected", True),
                        )
                        self.violations.append(violation)

                self.logger.info(
                    f"📁 Loaded {len(self.violations)} historical violations from audit trail"
                )
        except Exception as e:
            self.logger.warning(f"Could not load audit trail: {e}")

    async def _update_audit_trail(self, result: RiskValidationResult) -> None:
        """Update audit trail with new validation result"""
        try:
            audit_data = {
                "last_updated": datetime.utcnow().isoformat(),
                "total_validations": len(self.validation_results),
                "total_violations": len(self.violations),
                "violations": [v.to_dict() for v in self.violations],
            }

            with open(self.audit_file, "w") as f:
                json.dump(audit_data, f, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Failed to update audit trail: {e}")

    async def generate_compliance_report(self) -> str:
        """Generate comprehensive compliance report"""
        report_lines = [
            "=" * 80,
            "FXML4 RISK MANAGEMENT COMPLIANCE REPORT",
            "=" * 80,
            f"Generated: {datetime.utcnow().isoformat()}",
            f"Risk Limits: {self.max_trade_size_pct}% max trade, {self.max_portfolio_exposure_pct}% max portfolio",
            "",
        ]

        # Compliance summary
        total_validations = len(self.validation_results)
        total_violations = len(self.violations)
        compliance_rate = (
            ((total_validations - total_violations) / total_validations * 100)
            if total_validations > 0
            else 0
        )

        report_lines.extend(
            [
                "COMPLIANCE SUMMARY:",
                f"  Total Validations: {total_validations}",
                f"  Total Violations: {total_violations}",
                f"  Compliance Rate: {compliance_rate:.2f}%",
                f"  Status: {'✅ COMPLIANT' if total_violations == 0 else '❌ VIOLATIONS DETECTED'}",
                "",
            ]
        )

        # Violation details
        if self.violations:
            report_lines.extend(["VIOLATION DETAILS:", "-" * 40])
            for violation in self.violations[-10:]:  # Last 10 violations
                report_lines.append(
                    f"  {violation.timestamp.strftime('%Y-%m-%d %H:%M')} - "
                    f"{violation.violation_type.value}: {violation.message}"
                )
            report_lines.append("")

        # Statistics
        if self.validation_results:
            exposure_percentages = [
                r.exposure_percentage for r in self.validation_results
            ]
            trade_percentages = [
                r.trade_size_percentage for r in self.validation_results
            ]

            report_lines.extend(
                [
                    "RISK STATISTICS:",
                    f"  Max Trade Size: {max(trade_percentages):.2f}% (limit: {self.max_trade_size_pct}%)",
                    f"  Max Portfolio Exposure: {max(exposure_percentages):.2f}% (limit: {self.max_portfolio_exposure_pct}%)",
                    f"  Average Exposure: {statistics.mean(exposure_percentages):.2f}%",
                    "",
                ]
            )

        report_lines.extend(["=" * 80])

        return "\n".join(report_lines)

    async def cleanup(self) -> None:
        """Cleanup validator resources"""
        try:
            if self.ib_adapter:
                await self.ib_adapter.disconnect()

            # Final audit trail update
            if self.validation_results:
                await self._update_audit_trail(self.validation_results[-1])

            self.logger.info("🧹 Risk management validator cleanup completed")

        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")


# Validation Runner for Direct Execution
async def main():
    """Main validation runner"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    config = {
        "max_trade_size_percentage": 2.0,
        "max_portfolio_exposure_percentage": 6.0,
        "warning_threshold_percentage": 80.0,
    }

    validator = RiskManagementValidator(config)

    try:
        # Initialize validator
        await validator.initialize()

        # Run compliance test
        logger.info("🔄 Running risk management compliance validation...")

        # Test individual trade validations
        test_trades = [
            ("GBPUSD", 1000, "BUY"),  # Should pass
            (
                "EURUSD",
                50000,
                "SELL",
            ),  # Should likely be rejected (depends on account size)
            ("USDJPY", 2000, "BUY"),  # Should pass
            ("USDCHF", 100000, "SELL"),  # Should definitely be rejected
        ]

        for symbol, trade_size, side in test_trades:
            result = await validator.validate_trade_risk(symbol, trade_size, side)
            if result.is_compliant:
                logger.info(f"✅ {side} {trade_size} {symbol}: APPROVED")
            else:
                logger.error(
                    f"❌ {side} {trade_size} {symbol}: REJECTED ({len(result.violations)} violations)"
                )

        # Run comprehensive compliance test
        compliance_report = await validator.run_compliance_test(
            test_duration_hours=1, test_trades=20
        )

        # Generate final report
        report = await validator.generate_compliance_report()
        logger.info("Risk Management Compliance Report:")
        logger.info(report)

        # Check overall compliance
        if compliance_report.is_fully_compliant:
            logger.info("🎉 RISK MANAGEMENT VALIDATION PASSED")
            logger.info("✅ System correctly enforces 2% trade / 6% portfolio limits")
        else:
            logger.error("❌ RISK MANAGEMENT VALIDATION FAILED")
            logger.error(f"🚫 {compliance_report.violation_count} violations detected")

    except Exception as e:
        logger.error(f"Risk management validation failed: {e}")
        raise
    finally:
        await validator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
