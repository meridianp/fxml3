"""
FXML4 Session Validator

Provides comprehensive validation logic for market sessions, trading rules,
and session-based business logic validation.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import pytz

from .session_calendar import SessionCalendar, SessionType

# Configure logging
logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationRule(Enum):
    """Pre-defined validation rules"""

    WEEKEND_CLOSURE = "weekend_closure"
    HOLIDAY_CLOSURE = "holiday_closure"
    SESSION_OVERLAP = "session_overlap"
    LIQUIDITY_THRESHOLD = "liquidity_threshold"
    VOLATILITY_THRESHOLD = "volatility_threshold"
    TRADING_HOURS = "trading_hours"
    SESSION_TRANSITION = "session_transition"
    MARKET_STATE = "market_state"
    CURRENCY_PAIR_SESSION = "currency_pair_session"
    RISK_MANAGEMENT = "risk_management"


@dataclass
class ValidationResult:
    """Result of a validation check"""

    rule: ValidationRule
    level: ValidationLevel
    passed: bool
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class SessionValidationResult:
    """Comprehensive session validation result"""

    session_type: Optional[SessionType]
    validation_timestamp: datetime
    overall_passed: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    warning_count: int
    error_count: int
    critical_count: int
    results: List[ValidationResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


class SessionValidator:
    """
    Comprehensive session validation engine with configurable rules
    and business logic validation
    """

    def __init__(self, session_calendar: Optional[SessionCalendar] = None):
        """
        Initialize session validator

        Args:
            session_calendar: Session calendar instance (creates new if None)
        """
        self.session_calendar = session_calendar or SessionCalendar()
        self.validation_rules: Dict[ValidationRule, bool] = {}
        self.custom_validators: Dict[str, Callable] = {}

        # Thresholds and limits
        self.liquidity_thresholds = {
            "minimum": 0.3,
            "low": 0.6,
            "normal": 1.0,
            "high": 1.5,
            "peak": 2.0,
        }

        self.volatility_thresholds = {
            "minimum": 0.2,
            "low": 0.5,
            "normal": 1.0,
            "high": 1.5,
            "extreme": 2.0,
        }

        # Session-specific currency pair mappings
        self.session_currency_preferences = {
            SessionType.LONDON: {
                "primary": {"GBPUSD", "EURUSD", "EURGBP"},
                "secondary": {"GBPJPY", "EURJPY", "GBPCHF"},
                "avoid": set(),
            },
            SessionType.NEW_YORK: {
                "primary": {"GBPUSD", "EURUSD", "USDCAD"},
                "secondary": {"USDJPY", "USDCHF", "AUDUSD"},
                "avoid": set(),
            },
            SessionType.TOKYO: {
                "primary": {"USDJPY", "AUDJPY", "GBPJPY"},
                "secondary": {"EURJPY", "CADJPY", "CHFJPY"},
                "avoid": set(),
            },
            SessionType.SYDNEY: {
                "primary": {"AUDUSD", "NZDUSD", "AUDJPY"},
                "secondary": {"AUDCAD", "AUDCHF", "NZDJPY"},
                "avoid": set(),
            },
        }

        # Initialize default validation rules
        self._initialize_default_rules()

        logger.info("Session Validator initialized with default rules")

    def _initialize_default_rules(self) -> None:
        """Initialize default validation rules"""
        # Enable all default rules
        for rule in ValidationRule:
            self.validation_rules[rule] = True

    def enable_rule(self, rule: ValidationRule) -> None:
        """Enable a specific validation rule"""
        self.validation_rules[rule] = True
        logger.debug(f"Enabled validation rule: {rule.value}")

    def disable_rule(self, rule: ValidationRule) -> None:
        """Disable a specific validation rule"""
        self.validation_rules[rule] = False
        logger.debug(f"Disabled validation rule: {rule.value}")

    def set_liquidity_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Update liquidity thresholds"""
        self.liquidity_thresholds.update(thresholds)
        logger.info("Updated liquidity thresholds")

    def set_volatility_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Update volatility thresholds"""
        self.volatility_thresholds.update(thresholds)
        logger.info("Updated volatility thresholds")

    def validate_trading_session(
        self,
        session_type: SessionType,
        current_time: Optional[datetime] = None,
        currency_pair: Optional[str] = None,
    ) -> SessionValidationResult:
        """
        Comprehensive validation of a trading session

        Args:
            session_type: Session to validate
            current_time: Time to validate (defaults to current time)
            currency_pair: Specific currency pair to validate

        Returns:
            Comprehensive validation result
        """
        if current_time is None:
            current_time = datetime.utcnow()

        logger.info(f"Starting validation for {session_type.value} session")

        # Initialize result
        result = SessionValidationResult(
            session_type=session_type,
            validation_timestamp=current_time,
            overall_passed=True,
            total_checks=0,
            passed_checks=0,
            failed_checks=0,
            warning_count=0,
            error_count=0,
            critical_count=0,
        )

        # Run validation checks
        validation_checks = [
            self._validate_weekend_closure,
            self._validate_holiday_closure,
            self._validate_trading_hours,
            self._validate_session_overlap,
            self._validate_liquidity_threshold,
            self._validate_volatility_threshold,
            self._validate_currency_pair_session,
            self._validate_market_state,
        ]

        for check in validation_checks:
            try:
                check_result = check(session_type, current_time, currency_pair)
                if check_result:
                    result.results.append(check_result)
                    result.total_checks += 1

                    if check_result.passed:
                        result.passed_checks += 1
                    else:
                        result.failed_checks += 1
                        result.overall_passed = False

                    # Count by severity
                    if check_result.level == ValidationLevel.WARNING:
                        result.warning_count += 1
                    elif check_result.level == ValidationLevel.ERROR:
                        result.error_count += 1
                    elif check_result.level == ValidationLevel.CRITICAL:
                        result.critical_count += 1

            except Exception as e:
                logger.error(f"Error in validation check {check.__name__}: {e}")
                error_result = ValidationResult(
                    rule=ValidationRule.MARKET_STATE,
                    level=ValidationLevel.ERROR,
                    passed=False,
                    message=f"Validation check failed: {e}",
                    details={"error": str(e)},
                )
                result.results.append(error_result)
                result.total_checks += 1
                result.failed_checks += 1
                result.error_count += 1
                result.overall_passed = False

        # Generate summary
        result.summary = self._generate_validation_summary(result)

        logger.info(
            f"Validation completed: {result.passed_checks}/{result.total_checks} checks passed"
        )
        return result

    def _validate_weekend_closure(
        self,
        session_type: SessionType,
        current_time: datetime,
        currency_pair: Optional[str],
    ) -> Optional[ValidationResult]:
        """Validate weekend closure rules"""
        if not self.validation_rules.get(ValidationRule.WEEKEND_CLOSURE, False):
            return None

        current_date = current_time.date()
        is_trading_day = self.session_calendar.is_trading_day(
            current_date, session_type
        )
        is_weekend_day = current_time.weekday() >= 5  # Saturday = 5, Sunday = 6

        if is_weekend_day and is_trading_day:
            return ValidationResult(
                rule=ValidationRule.WEEKEND_CLOSURE,
                level=ValidationLevel.WARNING,
                passed=False,
                message=f"Weekend trading detected for {session_type.value} session",
                details={
                    "current_time": current_time.isoformat(),
                    "weekday": current_time.strftime("%A"),
                    "is_trading_day": is_trading_day,
                },
                recommendations=[
                    "Verify weekend trading permissions",
                    "Check holiday calendar",
                ],
            )
        elif is_weekend_day and not is_trading_day:
            return ValidationResult(
                rule=ValidationRule.WEEKEND_CLOSURE,
                level=ValidationLevel.INFO,
                passed=True,
                message=f"Weekend closure correctly observed for {session_type.value}",
                details={"weekday": current_time.strftime("%A")},
            )
        else:
            return ValidationResult(
                rule=ValidationRule.WEEKEND_CLOSURE,
                level=ValidationLevel.INFO,
                passed=True,
                message=f"Weekday trading validation passed for {session_type.value}",
                details={"weekday": current_time.strftime("%A")},
            )

    def _validate_holiday_closure(
        self,
        session_type: SessionType,
        current_time: datetime,
        currency_pair: Optional[str],
    ) -> Optional[ValidationResult]:
        """Validate holiday closure rules"""
        if not self.validation_rules.get(ValidationRule.HOLIDAY_CLOSURE, False):
            return None

        current_date = current_time.date()
        is_trading_day = self.session_calendar.is_trading_day(
            current_date, session_type
        )
        session_hours = self.session_calendar.get_session_hours(
            session_type, current_date
        )

        # Check for holiday modifications
        year_str = str(current_date.year)
        holidays_today = []

        if year_str in self.session_calendar.holidays:
            for holiday in self.session_calendar.holidays[year_str]:
                if (
                    holiday.date == current_date
                    and session_type in holiday.affected_sessions
                ):
                    holidays_today.append(holiday)

        if holidays_today:
            holiday = holidays_today[0]  # Take first holiday

            if holiday.trading_impact == "full_closure" and is_trading_day:
                return ValidationResult(
                    rule=ValidationRule.HOLIDAY_CLOSURE,
                    level=ValidationLevel.ERROR,
                    passed=False,
                    message=f"Trading on {holiday.name} holiday - should be closed",
                    details={
                        "holiday_name": holiday.name,
                        "holiday_type": holiday.holiday_type.value,
                        "trading_impact": holiday.trading_impact,
                    },
                    recommendations=[
                        "Suspend trading for holiday",
                        "Update holiday calendar",
                    ],
                )
            elif holiday.trading_impact in ["early_close", "late_open"]:
                return ValidationResult(
                    rule=ValidationRule.HOLIDAY_CLOSURE,
                    level=ValidationLevel.WARNING,
                    passed=True,
                    message=f"Modified hours for {holiday.name}",
                    details={
                        "holiday_name": holiday.name,
                        "modification_type": holiday.trading_impact,
                        "session_hours": session_hours,
                    },
                    recommendations=[
                        "Verify modified trading hours",
                        "Adjust trading strategies",
                    ],
                )

        return ValidationResult(
            rule=ValidationRule.HOLIDAY_CLOSURE,
            level=ValidationLevel.INFO,
            passed=True,
            message="No holiday conflicts detected",
            details={"current_date": current_date.isoformat()},
        )

    def _validate_trading_hours(
        self,
        session_type: SessionType,
        current_time: datetime,
        currency_pair: Optional[str],
    ) -> Optional[ValidationResult]:
        """Validate current time is within trading hours"""
        if not self.validation_rules.get(ValidationRule.TRADING_HOURS, False):
            return None

        current_date = current_time.date()
        session_hours = self.session_calendar.get_session_hours(
            session_type, current_date
        )

        if not session_hours:
            return ValidationResult(
                rule=ValidationRule.TRADING_HOURS,
                level=ValidationLevel.WARNING,
                passed=False,
                message=f"{session_type.value} session is closed today",
                details={"current_date": current_date.isoformat()},
                recommendations=["Check next trading day", "Verify holiday calendar"],
            )

        # Check if current time is within trading hours
        is_active = self.session_calendar._is_session_active_at_time(
            session_type, current_time
        )

        if is_active:
            return ValidationResult(
                rule=ValidationRule.TRADING_HOURS,
                level=ValidationLevel.INFO,
                passed=True,
                message=f"{session_type.value} session is currently active",
                details={
                    "session_hours": session_hours,
                    "current_time": current_time.isoformat(),
                },
            )
        else:
            return ValidationResult(
                rule=ValidationRule.TRADING_HOURS,
                level=ValidationLevel.WARNING,
                passed=False,
                message=f"{session_type.value} session is currently closed",
                details={
                    "session_hours": session_hours,
                    "current_time": current_time.isoformat(),
                },
                recommendations=[
                    "Wait for session open",
                    "Consider other active sessions",
                ],
            )

    def _validate_session_overlap(
        self,
        session_type: SessionType,
        current_time: datetime,
        currency_pair: Optional[str],
    ) -> Optional[ValidationResult]:
        """Validate session overlap conditions"""
        if not self.validation_rules.get(ValidationRule.SESSION_OVERLAP, False):
            return None

        active_overlaps = self.session_calendar.get_active_overlaps(current_time)

        # Check if current session is in any active overlap
        session_overlaps = [
            overlap
            for overlap in active_overlaps
            if (
                overlap.primary_session == session_type
                or overlap.secondary_session == session_type
            )
        ]

        if session_overlaps:
            overlap = session_overlaps[0]  # Take first overlap

            return ValidationResult(
                rule=ValidationRule.SESSION_OVERLAP,
                level=ValidationLevel.INFO,
                passed=True,
                message=f"{session_type.value} is in overlap period with enhanced liquidity",
                details={
                    "overlap_with": (
                        overlap.secondary_session.value
                        if overlap.primary_session == session_type
                        else overlap.primary_session.value
                    ),
                    "liquidity_multiplier": overlap.liquidity_multiplier,
                    "volatility_multiplier": overlap.volatility_multiplier,
                    "peak_hours": overlap.peak_hours,
                },
                recommendations=[
                    "Leverage increased liquidity",
                    "Monitor volatility closely",
                ],
            )
        else:
            return ValidationResult(
                rule=ValidationRule.SESSION_OVERLAP,
                level=ValidationLevel.INFO,
                passed=True,
                message=f"{session_type.value} is not in overlap period",
                details={"active_overlaps": len(active_overlaps)},
            )

    def _validate_liquidity_threshold(
        self,
        session_type: SessionType,
        current_time: datetime,
        currency_pair: Optional[str],
    ) -> Optional[ValidationResult]:
        """Validate liquidity meets minimum thresholds"""
        if not self.validation_rules.get(ValidationRule.LIQUIDITY_THRESHOLD, False):
            return None

        liquidity_factor = self.session_calendar.get_liquidity_factor(
            session_type, current_time
        )
        min_threshold = self.liquidity_thresholds["minimum"]

        if liquidity_factor < min_threshold:
            return ValidationResult(
                rule=ValidationRule.LIQUIDITY_THRESHOLD,
                level=ValidationLevel.WARNING,
                passed=False,
                message=f"Low liquidity detected: {liquidity_factor:.2f} < {min_threshold:.2f}",
                details={
                    "liquidity_factor": liquidity_factor,
                    "minimum_threshold": min_threshold,
                    "liquidity_level": self._classify_liquidity(liquidity_factor),
                },
                recommendations=[
                    "Consider reducing position sizes",
                    "Increase spread tolerance",
                    "Monitor price impact closely",
                ],
            )
        else:
            liquidity_level = self._classify_liquidity(liquidity_factor)

            return ValidationResult(
                rule=ValidationRule.LIQUIDITY_THRESHOLD,
                level=ValidationLevel.INFO,
                passed=True,
                message=f"Adequate liquidity: {liquidity_factor:.2f} ({liquidity_level})",
                details={
                    "liquidity_factor": liquidity_factor,
                    "liquidity_level": liquidity_level,
                },
            )

    def _validate_volatility_threshold(
        self,
        session_type: SessionType,
        current_time: datetime,
        currency_pair: Optional[str],
    ) -> Optional[ValidationResult]:
        """Validate volatility is within acceptable ranges"""
        if not self.validation_rules.get(ValidationRule.VOLATILITY_THRESHOLD, False):
            return None

        volatility_factor = self.session_calendar.get_volatility_factor(
            session_type, current_time
        )
        max_threshold = self.volatility_thresholds["extreme"]

        if volatility_factor > max_threshold:
            return ValidationResult(
                rule=ValidationRule.VOLATILITY_THRESHOLD,
                level=ValidationLevel.WARNING,
                passed=False,
                message=f"High volatility detected: {volatility_factor:.2f} > {max_threshold:.2f}",
                details={
                    "volatility_factor": volatility_factor,
                    "maximum_threshold": max_threshold,
                    "volatility_level": self._classify_volatility(volatility_factor),
                },
                recommendations=[
                    "Reduce position sizes",
                    "Tighten stop losses",
                    "Monitor for news events",
                    "Consider volatility-based adjustments",
                ],
            )
        else:
            volatility_level = self._classify_volatility(volatility_factor)

            return ValidationResult(
                rule=ValidationRule.VOLATILITY_THRESHOLD,
                level=ValidationLevel.INFO,
                passed=True,
                message=f"Normal volatility: {volatility_factor:.2f} ({volatility_level})",
                details={
                    "volatility_factor": volatility_factor,
                    "volatility_level": volatility_level,
                },
            )

    def _validate_currency_pair_session(
        self,
        session_type: SessionType,
        current_time: datetime,
        currency_pair: Optional[str],
    ) -> Optional[ValidationResult]:
        """Validate currency pair suitability for session"""
        if (
            not self.validation_rules.get(ValidationRule.CURRENCY_PAIR_SESSION, False)
            or not currency_pair
        ):
            return None

        session_prefs = self.session_currency_preferences.get(session_type, {})
        primary_pairs = session_prefs.get("primary", set())
        secondary_pairs = session_prefs.get("secondary", set())
        avoid_pairs = session_prefs.get("avoid", set())

        if currency_pair in avoid_pairs:
            return ValidationResult(
                rule=ValidationRule.CURRENCY_PAIR_SESSION,
                level=ValidationLevel.ERROR,
                passed=False,
                message=f"{currency_pair} should be avoided during {session_type.value} session",
                details={"currency_pair": currency_pair, "session_preference": "avoid"},
                recommendations=[
                    "Switch to preferred currency pairs",
                    "Wait for more suitable session",
                ],
            )
        elif currency_pair in primary_pairs:
            return ValidationResult(
                rule=ValidationRule.CURRENCY_PAIR_SESSION,
                level=ValidationLevel.INFO,
                passed=True,
                message=f"{currency_pair} is optimal for {session_type.value} session",
                details={
                    "currency_pair": currency_pair,
                    "session_preference": "primary",
                },
            )
        elif currency_pair in secondary_pairs:
            return ValidationResult(
                rule=ValidationRule.CURRENCY_PAIR_SESSION,
                level=ValidationLevel.INFO,
                passed=True,
                message=f"{currency_pair} is suitable for {session_type.value} session",
                details={
                    "currency_pair": currency_pair,
                    "session_preference": "secondary",
                },
            )
        else:
            return ValidationResult(
                rule=ValidationRule.CURRENCY_PAIR_SESSION,
                level=ValidationLevel.WARNING,
                passed=False,
                message=f"{currency_pair} has no specific preference for {session_type.value}",
                details={
                    "currency_pair": currency_pair,
                    "session_preference": "neutral",
                },
                recommendations=[
                    "Monitor performance closely",
                    "Consider preferred pairs",
                ],
            )

    def _validate_market_state(
        self,
        session_type: SessionType,
        current_time: datetime,
        currency_pair: Optional[str],
    ) -> Optional[ValidationResult]:
        """Validate overall market state"""
        if not self.validation_rules.get(ValidationRule.MARKET_STATE, False):
            return None

        # This would integrate with the MarketSessionManager's market state
        # For now, provide a basic validation
        current_date = current_time.date()
        is_trading_day = self.session_calendar.is_trading_day(
            current_date, session_type
        )
        is_active = self.session_calendar._is_session_active_at_time(
            session_type, current_time
        )

        if not is_trading_day:
            market_state = "closed"
            level = ValidationLevel.INFO
            passed = True
            message = "Market is closed as expected"
        elif is_active:
            market_state = "active"
            level = ValidationLevel.INFO
            passed = True
            message = "Market is active and operational"
        else:
            market_state = "pre_post_market"
            level = ValidationLevel.WARNING
            passed = False
            message = "Market is in pre/post-market hours"

        return ValidationResult(
            rule=ValidationRule.MARKET_STATE,
            level=level,
            passed=passed,
            message=message,
            details={
                "market_state": market_state,
                "is_trading_day": is_trading_day,
                "is_session_active": is_active,
            },
        )

    def _classify_liquidity(self, liquidity_factor: float) -> str:
        """Classify liquidity level"""
        thresholds = self.liquidity_thresholds

        if liquidity_factor >= thresholds["peak"]:
            return "peak"
        elif liquidity_factor >= thresholds["high"]:
            return "high"
        elif liquidity_factor >= thresholds["normal"]:
            return "normal"
        elif liquidity_factor >= thresholds["low"]:
            return "low"
        else:
            return "minimum"

    def _classify_volatility(self, volatility_factor: float) -> str:
        """Classify volatility level"""
        thresholds = self.volatility_thresholds

        if volatility_factor >= thresholds["extreme"]:
            return "extreme"
        elif volatility_factor >= thresholds["high"]:
            return "high"
        elif volatility_factor >= thresholds["normal"]:
            return "normal"
        elif volatility_factor >= thresholds["low"]:
            return "low"
        else:
            return "minimum"

    def _generate_validation_summary(
        self, result: SessionValidationResult
    ) -> Dict[str, Any]:
        """Generate validation summary"""
        return {
            "validation_score": (
                (result.passed_checks / result.total_checks * 100)
                if result.total_checks > 0
                else 0
            ),
            "risk_level": self._determine_risk_level(result),
            "critical_issues": result.critical_count,
            "trading_recommendation": self._get_trading_recommendation(result),
            "key_concerns": [
                r.message
                for r in result.results
                if r.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL]
            ],
            "optimization_suggestions": self._get_optimization_suggestions(result),
        }

    def _determine_risk_level(self, result: SessionValidationResult) -> str:
        """Determine overall risk level"""
        if result.critical_count > 0:
            return "critical"
        elif result.error_count > 0:
            return "high"
        elif result.warning_count > 2:
            return "medium"
        elif result.warning_count > 0:
            return "low"
        else:
            return "minimal"

    def _get_trading_recommendation(self, result: SessionValidationResult) -> str:
        """Get trading recommendation based on validation results"""
        if result.critical_count > 0:
            return "suspend_trading"
        elif result.error_count > 0:
            return "reduce_exposure"
        elif result.warning_count > 2:
            return "proceed_with_caution"
        elif result.warning_count > 0:
            return "monitor_closely"
        else:
            return "proceed_normally"

    def _get_optimization_suggestions(
        self, result: SessionValidationResult
    ) -> List[str]:
        """Get optimization suggestions"""
        suggestions = []

        for validation_result in result.results:
            suggestions.extend(validation_result.recommendations)

        # Remove duplicates
        return list(set(suggestions))

    def add_custom_validator(self, name: str, validator_func: Callable) -> None:
        """Add a custom validation function"""
        self.custom_validators[name] = validator_func
        logger.info(f"Added custom validator: {name}")

    def validate_with_custom_rules(
        self,
        session_type: SessionType,
        current_time: Optional[datetime] = None,
        **kwargs,
    ) -> List[ValidationResult]:
        """Run custom validation rules"""
        results = []

        for name, validator in self.custom_validators.items():
            try:
                result = validator(
                    session_type, current_time or datetime.utcnow(), **kwargs
                )
                if isinstance(result, ValidationResult):
                    results.append(result)
                elif isinstance(result, list):
                    results.extend(result)
            except Exception as e:
                logger.error(f"Error in custom validator {name}: {e}")
                results.append(
                    ValidationResult(
                        rule=ValidationRule.MARKET_STATE,
                        level=ValidationLevel.ERROR,
                        passed=False,
                        message=f"Custom validator {name} failed: {e}",
                        details={"error": str(e)},
                    )
                )

        return results
