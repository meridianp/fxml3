"""
Trade Size Validation System for FXML4 (Phase 12)
Implements absolute dollar limits for trading compliance.

Requirements:
- Prevent any single trade >$10,000 equivalent
- Prevent daily exposure >$50,000 equivalent
- Multi-currency support with real-time USD conversion
- Integration with existing percentage-based risk management
- Comprehensive audit trail and compliance reporting

Key Features:
- Real-time currency conversion for accurate USD limits
- Daily exposure tracking with midnight reset
- Violation audit trail for regulatory compliance
- Integration with Interactive Brokers paper trading
- Warning thresholds at 80% of limits
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.exceptions import RiskError, ValidationError


class TradeSizeViolationType(Enum):
    """Types of trade size violations."""

    SINGLE_TRADE_EXCEEDED = "single_trade_exceeded"
    DAILY_EXPOSURE_EXCEEDED = "daily_exposure_exceeded"
    INVALID_TRADE_SIZE = "invalid_trade_size"
    CURRENCY_CONVERSION_ERROR = "currency_conversion_error"


class TradeSizeComplianceStatus(Enum):
    """Trade size compliance status levels."""

    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    ERROR = "error"


@dataclass
class TradeSizeViolation:
    """Trade size violation record."""

    violation_type: TradeSizeViolationType
    timestamp: datetime
    symbol: str
    attempted_trade_size: float
    trade_value_usd: float
    current_daily_exposure: float
    limit_exceeded: float
    violation_amount: float
    message: str
    trade_rejected: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert violation to dictionary for JSON serialization."""
        return {
            "violation_type": self.violation_type.value,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "attempted_trade_size": self.attempted_trade_size,
            "trade_value_usd": self.trade_value_usd,
            "current_daily_exposure": self.current_daily_exposure,
            "limit_exceeded": self.limit_exceeded,
            "violation_amount": self.violation_amount,
            "message": self.message,
            "trade_rejected": self.trade_rejected,
        }


@dataclass
class TradeSizeValidationResult:
    """Result of trade size validation check."""

    status: TradeSizeComplianceStatus
    symbol: str
    trade_size: float
    trade_value_usd: float
    current_daily_exposure: float
    daily_exposure_percentage: float
    single_trade_percentage: float
    violations: List[TradeSizeViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_compliant(self) -> bool:
        """Check if trade is compliant (no violations)."""
        return self.status in [
            TradeSizeComplianceStatus.COMPLIANT,
            TradeSizeComplianceStatus.WARNING,
        ]

    @property
    def has_violations(self) -> bool:
        """Check if there are any violations."""
        return len(self.violations) > 0


@dataclass
class TradeSizeComplianceReport:
    """Comprehensive trade size compliance report."""

    start_date: datetime
    end_date: datetime
    total_validations: int
    total_violations: int
    single_trade_violations: int
    daily_exposure_violations: int
    compliance_rate: float
    max_single_trade_usd: float
    max_daily_exposure_usd: float
    violations: List[TradeSizeViolation] = field(default_factory=list)

    @property
    def is_fully_compliant(self) -> bool:
        """Check if system is fully compliant (no violations)."""
        return self.total_violations == 0 and self.compliance_rate == 100.0


class DailyExposureTracker:
    """Tracks daily exposure with automatic midnight reset."""

    def __init__(self):
        self.daily_exposures: Dict[date, float] = {}
        self.current_date = datetime.now().date()

    def add_exposure(self, trade_value_usd: float) -> None:
        """Add exposure for current day."""
        today = datetime.now().date()

        # Reset if new day
        if today != self.current_date:
            self.current_date = today

        if today not in self.daily_exposures:
            self.daily_exposures[today] = 0.0

        self.daily_exposures[today] += trade_value_usd

    def get_current_daily_exposure(self) -> float:
        """Get current day's total exposure."""
        today = datetime.now().date()
        return self.daily_exposures.get(today, 0.0)

    def get_exposure_history(self, days: int = 30) -> Dict[date, float]:
        """Get exposure history for specified number of days."""
        cutoff_date = datetime.now().date() - timedelta(days=days)
        return {
            date: exposure
            for date, exposure in self.daily_exposures.items()
            if date >= cutoff_date
        }

    def reset_daily_exposure(self, target_date: Optional[date] = None) -> None:
        """Reset daily exposure for specified date (or today)."""
        reset_date = target_date or datetime.now().date()
        if reset_date in self.daily_exposures:
            del self.daily_exposures[reset_date]


class TradeSizeValidator:
    """
    Trade Size Validation System

    Validates individual trades and daily exposure against absolute USD limits:
    - Single trade limit: $10,000
    - Daily exposure limit: $50,000
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize trade size validator."""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Limit configuration
        self.max_single_trade_usd = self.config.get("max_single_trade_usd", 10000.0)
        self.max_daily_exposure_usd = self.config.get("max_daily_exposure_usd", 50000.0)
        self.warning_threshold_pct = self.config.get(
            "warning_threshold_percentage", 80.0
        )

        # System components (will be injected)
        self.currency_converter = None
        self.ib_adapter = None

        # Tracking and audit
        self.daily_tracker = DailyExposureTracker()
        self.violations: List[TradeSizeViolation] = []
        self.validation_results: List[TradeSizeValidationResult] = []

        # Audit file
        self.audit_file = Path("trade_size_compliance_audit.json")

        self.logger.info(
            f"Initialized TradeSizeValidator: ${self.max_single_trade_usd:,.0f} single trade, ${self.max_daily_exposure_usd:,.0f} daily exposure"
        )

    async def initialize(self) -> None:
        """Initialize validator components."""
        try:
            self.logger.info("Initializing trade size validator...")

            # Load existing audit trail
            await self._load_audit_trail()

            self.logger.info("✅ Trade size validator initialized successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize trade size validator: {e}")
            raise ValidationError(f"Trade size validator initialization failed: {e}")

    async def validate_single_trade(
        self, symbol: str, trade_size: float, side: str
    ) -> TradeSizeValidationResult:
        """
        Validate single trade against $10,000 limit.

        Args:
            symbol: Currency pair (e.g., "GBPUSD")
            trade_size: Trade size in base currency units
            side: Trade side ("BUY" or "SELL")

        Returns:
            TradeSizeValidationResult with compliance status
        """
        self.logger.debug(f"Validating single trade: {side} {trade_size} {symbol}")

        try:
            # Validate inputs
            if trade_size < 0:
                raise ValidationError("Trade size cannot be negative")

            if trade_size == 0:
                return TradeSizeValidationResult(
                    status=TradeSizeComplianceStatus.COMPLIANT,
                    symbol=symbol,
                    trade_size=trade_size,
                    trade_value_usd=0.0,
                    current_daily_exposure=self.daily_tracker.get_current_daily_exposure(),
                    daily_exposure_percentage=0.0,
                    single_trade_percentage=0.0,
                    message="Zero trade size approved",
                )

            # Calculate USD value of trade
            trade_value_usd = await self._calculate_trade_value_usd(symbol, trade_size)

            # Calculate percentages for reporting
            single_trade_pct = (trade_value_usd / self.max_single_trade_usd) * 100
            current_daily_exposure = self.daily_tracker.get_current_daily_exposure()
            daily_exposure_pct = (
                current_daily_exposure / self.max_daily_exposure_usd
            ) * 100

            # Initialize result
            result = TradeSizeValidationResult(
                status=TradeSizeComplianceStatus.COMPLIANT,
                symbol=symbol,
                trade_size=trade_size,
                trade_value_usd=trade_value_usd,
                current_daily_exposure=current_daily_exposure,
                daily_exposure_percentage=daily_exposure_pct,
                single_trade_percentage=single_trade_pct,
                message="Trade approved",
            )

            # Check single trade limit violation
            if trade_value_usd > self.max_single_trade_usd:
                violation = TradeSizeViolation(
                    violation_type=TradeSizeViolationType.SINGLE_TRADE_EXCEEDED,
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    attempted_trade_size=trade_size,
                    trade_value_usd=trade_value_usd,
                    current_daily_exposure=current_daily_exposure,
                    limit_exceeded=self.max_single_trade_usd,
                    violation_amount=trade_value_usd - self.max_single_trade_usd,
                    message=f"Single trade ${trade_value_usd:,.2f} exceeds maximum ${self.max_single_trade_usd:,.0f}",
                )

                result.violations.append(violation)
                result.status = TradeSizeComplianceStatus.VIOLATION
                result.message = violation.message

                # Store violation
                self.violations.append(violation)
                self.logger.error(f"❌ TRADE SIZE VIOLATION: {violation.message}")

            # Check warning threshold (only warn if approaching but not at limit)
            elif (
                trade_value_usd
                > (self.max_single_trade_usd * self.warning_threshold_pct / 100)
                and trade_value_usd < self.max_single_trade_usd
            ):
                result.status = TradeSizeComplianceStatus.WARNING
                warning_msg = f"Single trade ${trade_value_usd:,.2f} approaching limit of ${self.max_single_trade_usd:,.0f}"
                result.warnings.append(warning_msg)
                result.message = f"Trade approved with warning: {warning_msg}"
                self.logger.warning(f"⚠️ TRADE SIZE WARNING: {warning_msg}")

            # Store result
            self.validation_results.append(result)

            if result.is_compliant:
                self.logger.debug(
                    f"✅ Single trade validation PASSED: ${trade_value_usd:,.2f}"
                )

            return result

        except Exception as e:
            self.logger.error(f"Single trade validation error: {e}")
            raise ValidationError(f"Single trade validation failed: {e}")

    async def validate_trade_with_daily_exposure(
        self, symbol: str, trade_size: float, side: str
    ) -> TradeSizeValidationResult:
        """
        Validate trade including daily exposure accumulation.

        Args:
            symbol: Currency pair
            trade_size: Trade size in base currency units
            side: Trade side

        Returns:
            TradeSizeValidationResult with daily exposure compliance
        """
        self.logger.debug(
            f"Validating trade with daily exposure: {side} {trade_size} {symbol}"
        )

        try:
            # First validate single trade
            result = await self.validate_single_trade(symbol, trade_size, side)

            if result.trade_value_usd == 0:
                return result  # Zero trades don't affect daily exposure

            # Calculate new daily exposure if trade executes
            current_daily_exposure = self.daily_tracker.get_current_daily_exposure()
            new_daily_exposure = current_daily_exposure + result.trade_value_usd

            # Update result with new exposure calculations
            result.current_daily_exposure = new_daily_exposure  # Show what the daily exposure would be after this trade
            result.daily_exposure_percentage = (
                new_daily_exposure / self.max_daily_exposure_usd
            ) * 100

            # Check daily exposure violation
            if new_daily_exposure > self.max_daily_exposure_usd:
                violation = TradeSizeViolation(
                    violation_type=TradeSizeViolationType.DAILY_EXPOSURE_EXCEEDED,
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    attempted_trade_size=trade_size,
                    trade_value_usd=result.trade_value_usd,
                    current_daily_exposure=new_daily_exposure,
                    limit_exceeded=self.max_daily_exposure_usd,
                    violation_amount=new_daily_exposure - self.max_daily_exposure_usd,
                    message=f"Daily exposure ${new_daily_exposure:,.2f} would exceed maximum ${self.max_daily_exposure_usd:,.0f}",
                )

                result.violations.append(violation)
                result.status = TradeSizeComplianceStatus.VIOLATION
                result.message = violation.message

                # Store violation
                self.violations.append(violation)
                self.logger.error(f"❌ DAILY EXPOSURE VIOLATION: {violation.message}")

            # Check daily exposure warning threshold (only warn if approaching but not at limit)
            elif (
                new_daily_exposure
                > (self.max_daily_exposure_usd * self.warning_threshold_pct / 100)
                and new_daily_exposure < self.max_daily_exposure_usd
                and result.status != TradeSizeComplianceStatus.VIOLATION
            ):
                result.status = TradeSizeComplianceStatus.WARNING
                warning_msg = f"Daily exposure approaching limit: ${new_daily_exposure:,.2f} / ${self.max_daily_exposure_usd:,.0f}"
                result.warnings.append(warning_msg)
                result.message = f"Trade approved with warning: {warning_msg}"
                self.logger.warning(f"⚠️ DAILY EXPOSURE WARNING: {warning_msg}")

            # If compliant, record the exposure
            if result.is_compliant:
                self.daily_tracker.add_exposure(result.trade_value_usd)
                self.logger.debug(
                    f"✅ Trade validation with daily exposure PASSED: ${result.trade_value_usd:,.2f}, daily total: ${new_daily_exposure:,.2f}"
                )

            return result

        except Exception as e:
            self.logger.error(f"Trade validation with daily exposure error: {e}")
            raise ValidationError(f"Trade validation with daily exposure failed: {e}")

    async def validate_complete_trade_compliance(
        self, symbol: str, trade_size: float, side: str
    ) -> TradeSizeValidationResult:
        """
        Complete trade compliance validation against both single trade and daily exposure limits.

        Args:
            symbol: Currency pair
            trade_size: Trade size in base currency units
            side: Trade side

        Returns:
            TradeSizeValidationResult with complete compliance check
        """
        self.logger.info(
            f"Complete trade compliance validation: {side} {trade_size} {symbol}"
        )

        try:
            # Validate both single trade and daily exposure
            result = await self.validate_trade_with_daily_exposure(
                symbol, trade_size, side
            )

            # Update audit trail
            await self._update_audit_trail(result)

            if result.is_compliant:
                self.logger.info(
                    f"✅ Complete trade compliance PASSED: {symbol} ${result.trade_value_usd:,.2f}"
                )
            else:
                self.logger.error(
                    f"❌ Complete trade compliance FAILED: {len(result.violations)} violations"
                )

            return result

        except Exception as e:
            self.logger.error(f"Complete trade compliance validation error: {e}")
            raise ValidationError(f"Complete trade compliance validation failed: {e}")

    async def _calculate_trade_value_usd(self, symbol: str, trade_size: float) -> float:
        """Calculate USD value of trade with currency conversion."""
        try:
            # Get market price
            if not self.ib_adapter:
                raise ValidationError("IB adapter not initialized")

            market_data = await self.ib_adapter.get_market_data(symbol)
            price = float(market_data.get("price", 0))

            if price <= 0:
                raise ValidationError(f"Invalid market price for {symbol}: {price}")

            # For direct USD pairs (xxxUSD), price is already in USD per base currency
            if symbol.endswith("USD"):
                trade_value_usd = abs(trade_size * price)
            else:
                # For inverse USD pairs (USDxxx), need special handling
                if symbol.startswith("USD"):
                    # USDxxx pairs: price is how many xxx per USD
                    # So 1 xxx = 1/price USD
                    base_currency = self._get_quote_currency(
                        symbol
                    )  # e.g., JPY from USDJPY
                    if not self.currency_converter:
                        raise ValidationError("Currency converter not initialized")

                    # Convert using the base currency rate
                    trade_value_usd = await self.currency_converter.convert_to_usd(
                        abs(trade_size), base_currency
                    )
                else:
                    # Cross-currency pairs (xxxyyy where neither is USD)
                    base_currency = self._get_base_currency(symbol)
                    trade_value = abs(trade_size * price)

                    if not self.currency_converter:
                        raise ValidationError("Currency converter not initialized")

                    trade_value_usd = await self.currency_converter.convert_to_usd(
                        trade_value, base_currency
                    )

            return trade_value_usd

        except Exception as e:
            self.logger.error(f"Error calculating trade value for {symbol}: {e}")
            raise ValidationError(f"Trade value calculation failed: {e}")

    def _get_base_currency(self, symbol: str) -> str:
        """Extract base currency from symbol."""
        if len(symbol) < 6:
            raise ValidationError(f"Invalid currency pair format: {symbol}")
        return symbol[:3]

    def _get_quote_currency(self, symbol: str) -> str:
        """Extract quote currency from symbol."""
        if len(symbol) < 6:
            raise ValidationError(f"Invalid currency pair format: {symbol}")
        return symbol[3:6]

    async def get_violations_history(self, days: int = 30) -> List[TradeSizeViolation]:
        """Get violation history for specified number of days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return [v for v in self.violations if v.timestamp >= cutoff_date]

    async def get_real_time_compliance_status(self) -> Dict[str, Any]:
        """Get real-time compliance status."""
        current_daily_exposure = self.daily_tracker.get_current_daily_exposure()
        violations_today = len(
            [v for v in self.violations if v.timestamp.date() == datetime.now().date()]
        )

        # Determine overall status
        if violations_today > 0:
            status = "VIOLATION"
        elif current_daily_exposure > (
            self.max_daily_exposure_usd * self.warning_threshold_pct / 100
        ):
            status = "WARNING"
        else:
            status = "COMPLIANT"

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "compliance_status": status,
            "current_daily_exposure": current_daily_exposure,
            "max_daily_exposure": self.max_daily_exposure_usd,
            "daily_exposure_percentage": (
                current_daily_exposure / self.max_daily_exposure_usd
            )
            * 100,
            "violations_today": violations_today,
            "single_trade_limit": self.max_single_trade_usd,
            "remaining_daily_capacity": max(
                0, self.max_daily_exposure_usd - current_daily_exposure
            ),
        }

    async def generate_compliance_report(self) -> TradeSizeComplianceReport:
        """Generate comprehensive compliance report."""
        total_validations = len(self.validation_results)
        total_violations = len(self.violations)

        single_trade_violations = len(
            [
                v
                for v in self.violations
                if v.violation_type == TradeSizeViolationType.SINGLE_TRADE_EXCEEDED
            ]
        )
        daily_exposure_violations = len(
            [
                v
                for v in self.violations
                if v.violation_type == TradeSizeViolationType.DAILY_EXPOSURE_EXCEEDED
            ]
        )

        compliance_rate = (
            ((total_validations - total_violations) / total_validations * 100)
            if total_validations > 0
            else 100.0
        )

        # Calculate maximum values
        max_single_trade = max(
            [r.trade_value_usd for r in self.validation_results], default=0.0
        )
        max_daily_exposure = max(
            [r.current_daily_exposure for r in self.validation_results], default=0.0
        )

        # Date range
        if self.validation_results:
            start_date = min(r.timestamp for r in self.validation_results)
            end_date = max(r.timestamp for r in self.validation_results)
        else:
            start_date = end_date = datetime.utcnow()

        return TradeSizeComplianceReport(
            start_date=start_date,
            end_date=end_date,
            total_validations=total_validations,
            total_violations=total_violations,
            single_trade_violations=single_trade_violations,
            daily_exposure_violations=daily_exposure_violations,
            compliance_rate=compliance_rate,
            max_single_trade_usd=max_single_trade,
            max_daily_exposure_usd=max_daily_exposure,
            violations=self.violations.copy(),
        )

    async def _load_audit_trail(self) -> None:
        """Load existing audit trail from file."""
        try:
            if self.audit_file.exists():
                with open(self.audit_file, "r") as f:
                    data = json.load(f)

                    # Reconstruct violations
                    for violation_data in data.get("violations", []):
                        violation = TradeSizeViolation(
                            violation_type=TradeSizeViolationType(
                                violation_data["violation_type"]
                            ),
                            timestamp=datetime.fromisoformat(
                                violation_data["timestamp"]
                            ),
                            symbol=violation_data["symbol"],
                            attempted_trade_size=violation_data["attempted_trade_size"],
                            trade_value_usd=violation_data["trade_value_usd"],
                            current_daily_exposure=violation_data[
                                "current_daily_exposure"
                            ],
                            limit_exceeded=violation_data["limit_exceeded"],
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

    async def _update_audit_trail(self, result: TradeSizeValidationResult) -> None:
        """Update audit trail with validation result."""
        try:
            audit_data = {
                "last_updated": datetime.utcnow().isoformat(),
                "total_validations": len(self.validation_results),
                "total_violations": len(self.violations),
                "single_trade_limit": self.max_single_trade_usd,
                "daily_exposure_limit": self.max_daily_exposure_usd,
                "violations": [v.to_dict() for v in self.violations],
            }

            with open(self.audit_file, "w") as f:
                json.dump(audit_data, f, indent=2, default=str)

        except Exception as e:
            self.logger.error(f"Failed to update audit trail: {e}")

    async def cleanup(self) -> None:
        """Cleanup validator resources."""
        try:
            # Final audit trail update
            if self.validation_results:
                await self._update_audit_trail(self.validation_results[-1])

            self.logger.info("🧹 Trade size validator cleanup completed")

        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")


# Validation Runner for Direct Testing
async def main():
    """Main validation runner for testing."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    config = {
        "max_single_trade_usd": 10000.0,
        "max_daily_exposure_usd": 50000.0,
        "warning_threshold_percentage": 80.0,
    }

    validator = TradeSizeValidator(config)

    try:
        await validator.initialize()

        logger.info("🔄 Testing trade size validation...")

        # Note: This would need mock adapters for actual testing
        # Real testing should use the pytest test suite

        logger.info("✅ Trade size validator ready for integration")

    except Exception as e:
        logger.error(f"Trade size validation test failed: {e}")
        raise
    finally:
        await validator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
