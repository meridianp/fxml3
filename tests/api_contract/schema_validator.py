"""
Schema Validation Implementation
===============================

Comprehensive schema validation for API request/response data including
JSON Schema validation, Pydantic model validation, and custom business rules.
"""

import json
import logging
import re
from datetime import date, datetime
from datetime import time as dt_time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Type, Union
from uuid import UUID

from .contract_models import FieldSchema, SchemaContract, ValidationResult

logger = logging.getLogger(__name__)


class SchemaValidator:
    """
    Schema validation engine for API contracts.

    Validates data against defined schemas with support for:
    - Basic type validation
    - Format validation (email, date, uuid, etc.)
    - Range and length constraints
    - Custom validation rules
    - Business logic validation
    """

    def __init__(self):
        """Initialize schema validator."""
        self.custom_validators = {}
        self.format_validators = self._build_format_validators()

    def register_custom_validator(self, field_name: str, validator_func):
        """Register custom validation function for specific field."""
        self.custom_validators[field_name] = validator_func

    def validate_schema(
        self, schema: SchemaContract, data: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate data against schema contract.

        Args:
            schema: Schema contract defining validation rules
            data: Data to validate

        Returns:
            ValidationResult with validation status and details
        """
        start_time = datetime.utcnow()
        result = ValidationResult()

        try:
            # Basic schema validation
            schema_result = schema.validate_data(data)
            result = result.merge(schema_result)

            # Additional custom validations
            custom_result = self._apply_custom_validations(schema, data)
            result = result.merge(custom_result)

            # Business rule validations
            business_result = self._apply_business_rules(schema, data)
            result = result.merge(business_result)

        except Exception as e:
            logger.error(f"Schema validation error: {e}")
            result.add_error(f"Validation exception: {str(e)}")

        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        result.execution_time_ms = execution_time

        return result

    def _build_format_validators(self) -> Dict[str, callable]:
        """Build format validation functions."""
        return {
            "email": self._validate_email,
            "date": self._validate_date,
            "date-time": self._validate_datetime,
            "time": self._validate_time,
            "uuid": self._validate_uuid,
            "uri": self._validate_uri,
            "currency": self._validate_currency,
            "decimal": self._validate_decimal,
            "percentage": self._validate_percentage,
            "trading_symbol": self._validate_trading_symbol,
            "trade_side": self._validate_trade_side,
            "order_type": self._validate_order_type,
            "account_id": self._validate_account_id,
            "phone": self._validate_phone,
            "country_code": self._validate_country_code,
            "timezone": self._validate_timezone,
        }

    def _apply_custom_validations(
        self, schema: SchemaContract, data: Dict[str, Any]
    ) -> ValidationResult:
        """Apply custom field validations."""
        result = ValidationResult()

        for field in schema.fields:
            if field.name not in data:
                continue

            value = data[field.name]

            # Format validation
            if field.format and field.format in self.format_validators:
                if not self.format_validators[field.format](value):
                    result.add_error(
                        f"Field '{field.name}' has invalid format '{field.format}': {value}"
                    )

            # Pattern validation
            if field.pattern and isinstance(value, str):
                if not re.match(field.pattern, value):
                    result.add_error(
                        f"Field '{field.name}' does not match pattern '{field.pattern}': {value}"
                    )

            # Custom validator
            if field.name in self.custom_validators:
                try:
                    is_valid, error_msg = self.custom_validators[field.name](value)
                    if not is_valid:
                        result.add_error(
                            f"Custom validation failed for '{field.name}': {error_msg}"
                        )
                except Exception as e:
                    result.add_error(
                        f"Custom validator error for '{field.name}': {str(e)}"
                    )

        return result

    def _apply_business_rules(
        self, schema: SchemaContract, data: Dict[str, Any]
    ) -> ValidationResult:
        """Apply business logic validation rules."""
        result = ValidationResult()

        # Trading-specific business rules
        if "trade" in schema.name.lower():
            result = result.merge(self._validate_trade_rules(data))

        if "order" in schema.name.lower():
            result = result.merge(self._validate_order_rules(data))

        if "account" in schema.name.lower():
            result = result.merge(self._validate_account_rules(data))

        if "user" in schema.name.lower():
            result = result.merge(self._validate_user_rules(data))

        return result

    def _validate_trade_rules(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate trading-specific business rules."""
        result = ValidationResult()

        # Entry/exit price relationship
        if "entry_price" in data and "exit_price" in data:
            try:
                entry = Decimal(str(data["entry_price"]))
                exit = Decimal(str(data["exit_price"]))
                side = data.get("side", "").upper()

                # Validate price relationship for profitability
                if side == "LONG" and exit < entry:
                    result.add_warning(
                        "LONG trade with exit price below entry price indicates loss"
                    )
                elif side == "SHORT" and exit > entry:
                    result.add_warning(
                        "SHORT trade with exit price above entry price indicates loss"
                    )

            except (ValueError, InvalidOperation):
                result.add_error("Invalid price format in trade data")

        # Quantity validation
        if "quantity" in data:
            try:
                quantity = Decimal(str(data["quantity"]))
                if quantity <= 0:
                    result.add_error("Trade quantity must be positive")
                if quantity > Decimal("1000"):  # Reasonable upper limit
                    result.add_warning("Very large trade quantity detected")
            except (ValueError, InvalidOperation):
                result.add_error("Invalid quantity format")

        # P&L validation
        if "gross_pnl" in data and "net_pnl" in data and "commission" in data:
            try:
                gross_pnl = Decimal(str(data["gross_pnl"]))
                net_pnl = Decimal(str(data["net_pnl"]))
                commission = Decimal(str(data["commission"]))

                expected_net = gross_pnl - commission
                if "swap" in data:
                    expected_net -= Decimal(str(data["swap"]))

                if abs(net_pnl - expected_net) > Decimal("0.01"):
                    result.add_error(
                        f"P&L calculation mismatch: net_pnl={net_pnl}, expected={expected_net}"
                    )

            except (ValueError, InvalidOperation):
                result.add_error("Invalid P&L format")

        return result

    def _validate_order_rules(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate order-specific business rules."""
        result = ValidationResult()

        # Order type and price consistency
        order_type = data.get("order_type", "").upper()
        price = data.get("price")

        if order_type == "MARKET" and price is not None:
            result.add_warning("Market order should not have a price specified")
        elif order_type in ["LIMIT", "STOP", "STOP_LIMIT"] and price is None:
            result.add_error(f"{order_type} order requires a price")

        # Quantity limits
        if "quantity" in data:
            try:
                quantity = Decimal(str(data["quantity"]))
                if quantity <= 0:
                    result.add_error("Order quantity must be positive")
                # Check minimum trade size (e.g., 0.01 lots for forex)
                if quantity < Decimal("0.01"):
                    result.add_error("Order quantity below minimum trade size (0.01)")
            except (ValueError, InvalidOperation):
                result.add_error("Invalid order quantity format")

        return result

    def _validate_account_rules(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate account-specific business rules."""
        result = ValidationResult()

        # Balance and equity relationship
        if "balance" in data and "equity" in data:
            try:
                balance = Decimal(str(data["balance"]))
                equity = Decimal(str(data["equity"]))

                if balance < 0:
                    result.add_error("Account balance cannot be negative")
                if equity < balance:
                    result.add_warning(
                        "Equity below balance indicates unrealized losses"
                    )

            except (ValueError, InvalidOperation):
                result.add_error("Invalid balance/equity format")

        # Leverage limits
        if "leverage" in data:
            try:
                leverage = int(data["leverage"])
                if leverage < 1:
                    result.add_error("Leverage must be at least 1:1")
                if leverage > 500:
                    result.add_warning("Very high leverage detected (>500:1)")
            except (ValueError, TypeError):
                result.add_error("Invalid leverage format")

        return result

    def _validate_user_rules(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate user-specific business rules."""
        result = ValidationResult()

        # Age validation for trading
        if "birth_date" in data:
            try:
                birth_date = datetime.fromisoformat(
                    data["birth_date"].replace("Z", "+00:00")
                )
                age = (datetime.utcnow() - birth_date).days / 365.25

                if age < 18:
                    result.add_error("User must be at least 18 years old for trading")
                elif age > 120:
                    result.add_warning("Unusual age detected")

            except ValueError:
                result.add_error("Invalid birth date format")

        # Trading permissions
        if "trading_enabled" in data and data["trading_enabled"]:
            required_fields = ["kyc_verified", "aml_status"]
            for field in required_fields:
                if field not in data:
                    result.add_error(
                        f"Trading enabled but missing required field: {field}"
                    )
                elif field == "kyc_verified" and not data[field]:
                    result.add_error("Trading enabled but KYC not verified")

        return result

    # Format validation functions
    def _validate_email(self, value: Any) -> bool:
        """Validate email format."""
        if not isinstance(value, str):
            return False
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(email_pattern, value) is not None

    def _validate_date(self, value: Any) -> bool:
        """Validate date format."""
        if not isinstance(value, str):
            return False
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False

    def _validate_datetime(self, value: Any) -> bool:
        """Validate datetime format."""
        return self._validate_date(value)

    def _validate_time(self, value: Any) -> bool:
        """Validate time format."""
        if not isinstance(value, str):
            return False
        try:
            dt_time.fromisoformat(value)
            return True
        except ValueError:
            return False

    def _validate_uuid(self, value: Any) -> bool:
        """Validate UUID format."""
        if not isinstance(value, str):
            return False
        try:
            UUID(value)
            return True
        except ValueError:
            return False

    def _validate_uri(self, value: Any) -> bool:
        """Validate URI format."""
        if not isinstance(value, str):
            return False
        uri_pattern = r"^https?://[\w\-\.]+\w+(:\d+)?(/[\w\-\.~!$&\'()*+,;=:@%]*)*(\?[\w\-\.~!$&\'()*+,;=:@%]*)?$"
        return re.match(uri_pattern, value) is not None

    def _validate_currency(self, value: Any) -> bool:
        """Validate currency code format."""
        if not isinstance(value, str):
            return False
        return len(value) == 3 and value.isalpha() and value.isupper()

    def _validate_decimal(self, value: Any) -> bool:
        """Validate decimal format."""
        try:
            Decimal(str(value))
            return True
        except (ValueError, InvalidOperation):
            return False

    def _validate_percentage(self, value: Any) -> bool:
        """Validate percentage format."""
        try:
            pct = float(value)
            return -100.0 <= pct <= 1000.0  # Allow up to 1000% gain, 100% loss
        except (ValueError, TypeError):
            return False

    def _validate_trading_symbol(self, value: Any) -> bool:
        """Validate trading symbol format."""
        if not isinstance(value, str):
            return False
        # Common forex pairs and symbols
        forex_pattern = r"^[A-Z]{6}$"  # e.g., EURUSD
        crypto_pattern = r"^[A-Z]{3,10}$"  # e.g., BTC, ETH
        return (
            re.match(forex_pattern, value) is not None
            or re.match(crypto_pattern, value) is not None
        )

    def _validate_trade_side(self, value: Any) -> bool:
        """Validate trade side."""
        if not isinstance(value, str):
            return False
        return value.upper() in ["BUY", "SELL", "LONG", "SHORT"]

    def _validate_order_type(self, value: Any) -> bool:
        """Validate order type."""
        if not isinstance(value, str):
            return False
        return value.upper() in [
            "MARKET",
            "LIMIT",
            "STOP",
            "STOP_LIMIT",
            "TRAILING_STOP",
        ]

    def _validate_account_id(self, value: Any) -> bool:
        """Validate account ID format."""
        if not isinstance(value, str):
            return False
        # Common patterns: ACC12345678, DU123456, etc.
        account_patterns = [r"^ACC\d{8}$", r"^DU\d{6}$", r"^[A-Z]{2,4}\d{6,8}$"]
        return any(re.match(pattern, value) for pattern in account_patterns)

    def _validate_phone(self, value: Any) -> bool:
        """Validate phone number format."""
        if not isinstance(value, str):
            return False
        # Simple international phone validation
        phone_pattern = r"^\+?[\d\s\-\(\)]{10,15}$"
        return re.match(phone_pattern, value) is not None

    def _validate_country_code(self, value: Any) -> bool:
        """Validate country code format."""
        if not isinstance(value, str):
            return False
        return len(value) == 2 and value.isalpha() and value.isupper()

    def _validate_timezone(self, value: Any) -> bool:
        """Validate timezone format."""
        if not isinstance(value, str):
            return False
        # Common timezone patterns
        timezone_patterns = [
            r"^UTC[+-]\d{2}:\d{2}$",
            r"^[A-Za-z]+/[A-Za-z_]+$",  # e.g., America/New_York
            r"^[A-Z]{3,4}$",  # e.g., EST, GMT
        ]
        return any(re.match(pattern, value) for pattern in timezone_patterns)


class BusinessRuleValidator:
    """
    Advanced business rule validator for complex validation scenarios.
    """

    def __init__(self):
        """Initialize business rule validator."""
        self.rules = {}

    def register_rule(self, rule_name: str, rule_func):
        """Register business rule function."""
        self.rules[rule_name] = rule_func

    def validate_trading_business_rules(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate comprehensive trading business rules."""
        result = ValidationResult()

        # Portfolio risk rules
        if "positions" in data and isinstance(data["positions"], list):
            result = result.merge(self._validate_portfolio_risk(data["positions"]))

        # Margin requirements
        if "margin_used" in data and "margin_available" in data:
            result = result.merge(self._validate_margin_requirements(data))

        # Trading hours
        if "trade_time" in data:
            result = result.merge(
                self._validate_trading_hours(data["trade_time"], data.get("symbol"))
            )

        return result

    def _validate_portfolio_risk(
        self, positions: List[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate portfolio-level risk rules."""
        result = ValidationResult()

        if not positions:
            return result

        try:
            # Calculate total exposure
            total_exposure = sum(
                abs(float(pos.get("quantity", 0)) * float(pos.get("current_price", 0)))
                for pos in positions
            )

            # Check concentration risk
            exposures = {}
            for pos in positions:
                symbol = pos.get("symbol", "UNKNOWN")
                exposure = abs(
                    float(pos.get("quantity", 0)) * float(pos.get("current_price", 0))
                )
                exposures[symbol] = exposures.get(symbol, 0) + exposure

            # Check single position concentration
            for symbol, exposure in exposures.items():
                concentration = (
                    (exposure / total_exposure) * 100 if total_exposure > 0 else 0
                )
                if concentration > 50:
                    result.add_warning(
                        f"High concentration in {symbol}: {concentration:.1f}%"
                    )
                elif concentration > 25:
                    result.add_warning(
                        f"Moderate concentration in {symbol}: {concentration:.1f}%"
                    )

            # Check correlation risk (simplified)
            symbols = list(exposures.keys())
            correlated_pairs = [
                ("EURUSD", "GBPUSD"),
                ("USDJPY", "USDCHF"),
                ("AUDUSD", "NZDUSD"),
                ("EURGBP", "EURUSD"),
            ]

            for pair in correlated_pairs:
                if pair[0] in symbols and pair[1] in symbols:
                    combined_exposure = exposures[pair[0]] + exposures[pair[1]]
                    combined_concentration = (
                        (combined_exposure / total_exposure) * 100
                        if total_exposure > 0
                        else 0
                    )
                    if combined_concentration > 60:
                        result.add_warning(
                            f"High correlated exposure in {pair[0]}/{pair[1]}: {combined_concentration:.1f}%"
                        )

        except (ValueError, TypeError, KeyError) as e:
            result.add_error(f"Error validating portfolio risk: {e}")

        return result

    def _validate_margin_requirements(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate margin requirements."""
        result = ValidationResult()

        try:
            margin_used = float(data["margin_used"])
            margin_available = float(data["margin_available"])
            total_margin = margin_used + margin_available

            if total_margin <= 0:
                result.add_error("Total margin must be positive")
                return result

            margin_utilization = (margin_used / total_margin) * 100

            if margin_utilization > 90:
                result.add_error(
                    f"Margin utilization too high: {margin_utilization:.1f}%"
                )
            elif margin_utilization > 75:
                result.add_warning(
                    f"High margin utilization: {margin_utilization:.1f}%"
                )
            elif margin_utilization > 50:
                result.add_warning(
                    f"Moderate margin utilization: {margin_utilization:.1f}%"
                )

        except (ValueError, TypeError, KeyError) as e:
            result.add_error(f"Error validating margin requirements: {e}")

        return result

    def _validate_trading_hours(
        self, trade_time: str, symbol: Optional[str] = None
    ) -> ValidationResult:
        """Validate trading hours for different markets."""
        result = ValidationResult()

        try:
            trade_dt = datetime.fromisoformat(trade_time.replace("Z", "+00:00"))

            # Weekend check
            if trade_dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
                result.add_warning("Trade executed on weekend - limited liquidity")

            # Holiday check (simplified)
            current_date = trade_dt.date()
            if self._is_market_holiday(current_date):
                result.add_warning("Trade executed on market holiday")

            # Symbol-specific hours (simplified)
            if symbol and symbol.startswith("USD"):
                # US market hours consideration
                if trade_dt.hour < 8 or trade_dt.hour > 17:
                    result.add_warning("Trade outside typical US market hours")

        except ValueError as e:
            result.add_error(f"Invalid trade time format: {e}")

        return result

    def _is_market_holiday(self, trade_date: date) -> bool:
        """Check if date is a market holiday (simplified)."""
        # This would typically check against a comprehensive holiday calendar
        # For now, just check for obvious holidays

        # New Year's Day
        if trade_date.month == 1 and trade_date.day == 1:
            return True

        # Christmas
        if trade_date.month == 12 and trade_date.day == 25:
            return True

        return False
