"""FIX Protocol Utilities.

This module consolidates all FIX protocol utility functions including
session management, message validation, building, and parsing.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union

from .messages.admin import Heartbeat, Logon, Logout, Reject, TestRequest
from .messages.base import (
    FIXField,
    FIXMessage,
    FIXMessageType,
    OrdType,
    Side,
    TimeInForce,
)
from .messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest

logger = logging.getLogger(__name__)


# ==============================================================================
# Session Management Utilities
# ==============================================================================


class FIXSession:
    """Lightweight FIX session utility class.

    Note: This is a simplified version for utilities.
    The main session management is in fxml4.fix.session_manager.
    """

    def __init__(self, session_id: str):
        """Initialize FIX session utility.

        Args:
            session_id: Session identifier.
        """
        self.session_id = session_id
        self.properties: Dict[str, Any] = {}
        self.created_time = datetime.utcnow()

    def set_property(self, key: str, value: Any) -> None:
        """Set session property.

        Args:
            key: Property key.
            value: Property value.
        """
        self.properties[key] = value

    def get_property(self, key: str, default: Any = None) -> Any:
        """Get session property.

        Args:
            key: Property key.
            default: Default value if key not found.

        Returns:
            Property value or default.
        """
        return self.properties.get(key, default)

    def __repr__(self) -> str:
        return f"FIXSession(id={self.session_id}, created={self.created_time})"


def create_session_id(sender_comp_id: str, target_comp_id: str) -> str:
    """Create a FIX session ID.

    Args:
        sender_comp_id: Sender component ID.
        target_comp_id: Target component ID.

    Returns:
        Session ID string.
    """
    return f"{sender_comp_id}_{target_comp_id}"


def parse_session_id(session_id: str) -> Tuple[str, str]:
    """Parse a FIX session ID.

    Args:
        session_id: Session ID to parse.

    Returns:
        Tuple of (sender_comp_id, target_comp_id).
    """
    parts = session_id.split("_", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid session ID format: {session_id}")
    return parts[0], parts[1]


# ==============================================================================
# Message Validation Utilities
# ==============================================================================


class FIXValidationError(Exception):
    """Exception raised for FIX message validation errors."""

    pass


class FIXValidator:
    """Validates FIX messages for correctness and completeness."""

    # Required fields for each message type
    REQUIRED_FIELDS = {
        FIXMessageType.NEW_ORDER_SINGLE: {
            "cl_ord_id",
            "symbol",
            "side",
            "order_qty",
            "ord_type",
        },
        FIXMessageType.ORDER_CANCEL_REQUEST: {
            "cl_ord_id",
            "orig_cl_ord_id",
            "symbol",
            "side",
        },
        FIXMessageType.EXECUTION_REPORT: {
            "order_id",
            "cl_ord_id",
            "exec_id",
            "exec_type",
            "ord_status",
            "symbol",
            "side",
            "order_qty",
            "cum_qty",
            "leaves_qty",
            "avg_px",
        },
    }

    # Valid symbol patterns (basic FX pairs)
    VALID_SYMBOLS = {
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "AUD/USD",
        "USD/CAD",
        "USD/CHF",
        "NZD/USD",
        "EUR/GBP",
        "EUR/JPY",
        "GBP/JPY",
        "AUD/JPY",
        "EUR/AUD",
        "EUR/CAD",
        "EUR/CHF",
        "GBP/CAD",
        "GBP/CHF",
        "CAD/JPY",
        "CHF/JPY",
    }

    def __init__(self, strict_mode: bool = True):
        """Initialize validator.

        Args:
            strict_mode: Whether to enforce strict validation rules.
        """
        self.strict_mode = strict_mode

    def validate_message(self, message: FIXMessage) -> None:
        """Validate a FIX message.

        Args:
            message: FIX message to validate.

        Raises:
            FIXValidationError: If validation fails.
        """
        # Check required fields
        self._check_required_fields(message)

        # Check field values
        self._check_field_values(message)

        # Check business rules
        self._check_business_rules(message)

    def _check_required_fields(self, message: FIXMessage) -> None:
        """Check if all required fields are present."""
        msg_type = message.get_field("msg_type")
        if msg_type in self.REQUIRED_FIELDS:
            required = self.REQUIRED_FIELDS[msg_type]
            for field_name in required:
                if not message.has_field(field_name):
                    raise FIXValidationError(f"Missing required field: {field_name}")

    def _check_field_values(self, message: FIXMessage) -> None:
        """Check if field values are valid."""
        # Check symbol format
        if message.has_field("symbol"):
            symbol = message.get_field("symbol")
            if self.strict_mode and symbol not in self.VALID_SYMBOLS:
                raise FIXValidationError(f"Invalid symbol: {symbol}")

        # Check side
        if message.has_field("side"):
            side = message.get_field("side")
            if side not in [Side.BUY, Side.SELL]:
                raise FIXValidationError(f"Invalid side: {side}")

        # Check order quantity
        if message.has_field("order_qty"):
            qty = message.get_field("order_qty")
            if qty <= 0:
                raise FIXValidationError(f"Invalid order quantity: {qty}")

        # Check price (if present)
        if message.has_field("price"):
            price = message.get_field("price")
            if price <= 0:
                raise FIXValidationError(f"Invalid price: {price}")

    def _check_business_rules(self, message: FIXMessage) -> None:
        """Check business-specific validation rules."""
        msg_type = message.get_field("msg_type")

        # Market orders shouldn't have price
        if msg_type == FIXMessageType.NEW_ORDER_SINGLE:
            ord_type = message.get_field("ord_type")
            if ord_type == OrdType.MARKET and message.has_field("price"):
                if self.strict_mode:
                    raise FIXValidationError("Market orders should not have price")

        # Limit orders should have price
        if msg_type == FIXMessageType.NEW_ORDER_SINGLE:
            ord_type = message.get_field("ord_type")
            if ord_type == OrdType.LIMIT and not message.has_field("price"):
                raise FIXValidationError("Limit orders must have price")


# ==============================================================================
# Message Building Utilities
# ==============================================================================


class FIXBuilder:
    """Builder for constructing FIX protocol messages."""

    def __init__(self, sender_comp_id: str = "FXML4", default_target: str = ""):
        """Initialize FIX builder.

        Args:
            sender_comp_id: Default sender comp ID for messages.
            default_target: Default target comp ID for messages.
        """
        self.sender_comp_id = sender_comp_id
        self.default_target = default_target
        self.sequence_number = 1
        self.soh = chr(1)  # Start of Header delimiter

    def build_fix_string(
        self,
        msg_type: str,
        body_fields: Dict[int, Any],
        target_comp_id: Optional[str] = None,
        sender_comp_id: Optional[str] = None,
        seq_num: Optional[int] = None,
        sending_time: Optional[datetime] = None,
    ) -> str:
        """Build FIX protocol string from components.

        Args:
            msg_type: FIX message type (tag 35).
            body_fields: Dictionary of body field tags and values.
            target_comp_id: Target comp ID (overrides default).
            sender_comp_id: Sender comp ID (overrides default).
            seq_num: Sequence number (uses auto-increment if None).
            sending_time: Sending time (uses current time if None).

        Returns:
            Complete FIX protocol string.
        """
        # Use defaults or provided values
        target = target_comp_id or self.default_target
        sender = sender_comp_id or self.sender_comp_id
        seq = seq_num or self.sequence_number
        time = sending_time or datetime.utcnow()

        # Build header fields
        header_fields = {
            8: "FIX.4.2",  # BeginString
            35: msg_type,  # MsgType
            49: sender,  # SenderCompID
            56: target,  # TargetCompID
            34: seq,  # MsgSeqNum
            52: time.strftime("%Y%m%d-%H:%M:%S"),  # SendingTime
        }

        # Combine header and body
        all_fields = {**header_fields, **body_fields}

        # Sort fields by tag number (except BeginString which is first)
        sorted_fields = [(8, all_fields[8])]  # BeginString first
        sorted_fields.extend(sorted((k, v) for k, v in all_fields.items() if k != 8))

        # Build message string
        message_parts = []
        for tag, value in sorted_fields:
            if tag == 9:  # Skip BodyLength, we'll calculate it
                continue
            message_parts.append(f"{tag}={value}")

        # Calculate body length (everything after BeginString and BodyLength)
        body_start_idx = 2  # Skip BeginString and BodyLength
        body_length = sum(
            len(f"{tag}={value}") + 1 for tag, value in sorted_fields[body_start_idx:]
        )

        # Insert BodyLength at position 1
        final_parts = [message_parts[0]]  # BeginString
        final_parts.append(f"9={body_length}")  # BodyLength
        final_parts.extend(message_parts[1:])  # Rest of message

        # Calculate checksum
        message_without_checksum = self.soh.join(final_parts) + self.soh
        checksum = sum(ord(c) for c in message_without_checksum) % 256

        # Add checksum
        final_parts.append(f"10={checksum:03d}")

        # Auto-increment sequence number
        self.sequence_number += 1

        return self.soh.join(final_parts) + self.soh

    def build_new_order_single(
        self,
        cl_ord_id: str,
        symbol: str,
        side: Side,
        order_qty: float,
        ord_type: OrdType,
        price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        **kwargs,
    ) -> str:
        """Build a New Order Single message.

        Args:
            cl_ord_id: Client order ID.
            symbol: Trading symbol.
            side: Order side (buy/sell).
            order_qty: Order quantity.
            ord_type: Order type.
            price: Order price (required for limit orders).
            time_in_force: Time in force.
            **kwargs: Additional fields.

        Returns:
            FIX protocol string.
        """
        fields = {
            11: cl_ord_id,  # ClOrdID
            55: symbol,  # Symbol
            54: side.value,  # Side
            38: order_qty,  # OrderQty
            40: ord_type.value,  # OrdType
            59: time_in_force.value,  # TimeInForce
        }

        if price is not None:
            fields[44] = price  # Price

        fields.update(kwargs)

        return self.build_fix_string(FIXMessageType.NEW_ORDER_SINGLE, fields)

    def build_order_cancel_request(
        self, cl_ord_id: str, orig_cl_ord_id: str, symbol: str, side: Side, **kwargs
    ) -> str:
        """Build an Order Cancel Request message.

        Args:
            cl_ord_id: Client order ID.
            orig_cl_ord_id: Original client order ID.
            symbol: Trading symbol.
            side: Order side.
            **kwargs: Additional fields.

        Returns:
            FIX protocol string.
        """
        fields = {
            11: cl_ord_id,  # ClOrdID
            41: orig_cl_ord_id,  # OrigClOrdID
            55: symbol,  # Symbol
            54: side.value,  # Side
        }

        fields.update(kwargs)

        return self.build_fix_string(FIXMessageType.ORDER_CANCEL_REQUEST, fields)


# ==============================================================================
# Message Parsing Utilities
# ==============================================================================


class FIXParseError(Exception):
    """Exception raised when FIX message parsing fails."""

    pass


class FIXParser:
    """Parser for FIX protocol messages."""

    # Message type to class mapping
    MESSAGE_CLASSES = {
        FIXMessageType.LOGON: Logon,
        FIXMessageType.LOGOUT: Logout,
        FIXMessageType.HEARTBEAT: Heartbeat,
        FIXMessageType.TEST_REQUEST: TestRequest,
        FIXMessageType.REJECT: Reject,
        FIXMessageType.NEW_ORDER_SINGLE: NewOrderSingle,
        FIXMessageType.EXECUTION_REPORT: ExecutionReport,
        FIXMessageType.ORDER_CANCEL_REQUEST: OrderCancelRequest,
    }

    def __init__(self, strict_validation: bool = True):
        """Initialize FIX parser.

        Args:
            strict_validation: Whether to enforce strict FIX protocol validation.
        """
        self.strict_validation = strict_validation
        self.soh = chr(1)  # Start of Header delimiter

    def parse(self, fix_string: str) -> FIXMessage:
        """Parse FIX string into message object.

        Args:
            fix_string: Raw FIX protocol string.

        Returns:
            Parsed FIX message object.

        Raises:
            FIXParseError: If parsing fails.
        """
        try:
            # Parse fields from string
            fields = self._parse_fields(fix_string)

            # Validate basic structure
            self._validate_structure(fields)

            # Validate checksum
            if self.strict_validation:
                self._validate_checksum(fix_string, fields)

            # Create message object
            msg_type = fields.get(35)  # MsgType
            if msg_type in self.MESSAGE_CLASSES:
                message_class = self.MESSAGE_CLASSES[msg_type]
                return message_class.from_fields(fields)
            else:
                # Create generic message
                return FIXMessage.from_fields(fields)

        except Exception as e:
            raise FIXParseError(f"Failed to parse FIX message: {e}")

    def _parse_fields(self, fix_string: str) -> Dict[int, Any]:
        """Parse field/value pairs from FIX string.

        Args:
            fix_string: Raw FIX string.

        Returns:
            Dictionary of field tag to value mappings.
        """
        fields = {}

        # Split by SOH delimiter
        parts = fix_string.split(self.soh)

        for part in parts:
            if not part:
                continue

            # Split tag=value
            if "=" not in part:
                continue

            tag_str, value = part.split("=", 1)

            try:
                tag = int(tag_str)
                fields[tag] = self._convert_value(tag, value)
            except ValueError:
                if self.strict_validation:
                    raise FIXParseError(f"Invalid field tag: {tag_str}")

        return fields

    def _convert_value(self, tag: int, value: str) -> Any:
        """Convert string value to appropriate type based on field tag.

        Args:
            tag: Field tag.
            value: String value.

        Returns:
            Converted value.
        """
        # Numeric fields
        if tag in [
            9,
            10,
            34,
            38,
            44,
            58,
            59,
        ]:  # BodyLength, CheckSum, MsgSeqNum, OrderQty, Price, etc.
            try:
                if "." in value:
                    return float(value)
                else:
                    return int(value)
            except ValueError:
                pass

        # Boolean fields
        if tag in [108, 141]:  # HeartBtInt, ResetSeqNumFlag
            return value.upper() in ["Y", "YES", "TRUE", "1"]

        # Default to string
        return value

    def _validate_structure(self, fields: Dict[int, Any]) -> None:
        """Validate basic FIX message structure.

        Args:
            fields: Parsed fields.

        Raises:
            FIXParseError: If structure is invalid.
        """
        # Check required header fields
        required_header_fields = [
            8,
            35,
            49,
            56,
            34,
            52,
        ]  # BeginString, MsgType, SenderCompID, TargetCompID, MsgSeqNum, SendingTime

        for tag in required_header_fields:
            if tag not in fields:
                raise FIXParseError(f"Missing required header field: {tag}")

        # Check BeginString
        if fields[8] != "FIX.4.2":
            if self.strict_validation:
                raise FIXParseError(f"Unsupported FIX version: {fields[8]}")

    def _validate_checksum(self, fix_string: str, fields: Dict[int, Any]) -> None:
        """Validate message checksum.

        Args:
            fix_string: Original FIX string.
            fields: Parsed fields.

        Raises:
            FIXParseError: If checksum is invalid.
        """
        if 10 not in fields:
            raise FIXParseError("Missing checksum field")

        # Calculate checksum (sum of all bytes except checksum field)
        checksum_idx = fix_string.rfind(f"{self.soh}10=")
        if checksum_idx == -1:
            raise FIXParseError("Checksum field not found")

        message_without_checksum = fix_string[: checksum_idx + 1]
        calculated_checksum = sum(ord(c) for c in message_without_checksum) % 256

        provided_checksum = fields[10]
        if calculated_checksum != provided_checksum:
            raise FIXParseError(
                f"Checksum mismatch: calculated={calculated_checksum}, provided={provided_checksum}"
            )

    def parse_fields_only(self, fix_string: str) -> Dict[int, Any]:
        """Parse only the fields from a FIX string without validation.

        Args:
            fix_string: Raw FIX string.

        Returns:
            Dictionary of field tag to value mappings.
        """
        return self._parse_fields(fix_string)


# ==============================================================================
# Utility Functions
# ==============================================================================


def format_fix_time(dt: datetime) -> str:
    """Format datetime for FIX protocol.

    Args:
        dt: Datetime to format.

    Returns:
        FIX-formatted time string.
    """
    return dt.strftime("%Y%m%d-%H:%M:%S")


def parse_fix_time(time_str: str) -> datetime:
    """Parse FIX-formatted time string.

    Args:
        time_str: FIX time string.

    Returns:
        Parsed datetime.
    """
    return datetime.strptime(time_str, "%Y%m%d-%H:%M:%S")


def generate_client_order_id() -> str:
    """Generate a unique client order ID.

    Returns:
        Unique client order ID.
    """
    import uuid

    return str(uuid.uuid4())


def is_valid_symbol(symbol: str) -> bool:
    """Check if symbol is a valid FX pair.

    Args:
        symbol: Trading symbol.

    Returns:
        True if valid, False otherwise.
    """
    return symbol in FIXValidator.VALID_SYMBOLS


__all__ = [
    # Session utilities
    "FIXSession",
    "create_session_id",
    "parse_session_id",
    # Validation
    "FIXValidator",
    "FIXValidationError",
    # Building
    "FIXBuilder",
    # Parsing
    "FIXParser",
    "FIXParseError",
    # Utility functions
    "format_fix_time",
    "parse_fix_time",
    "generate_client_order_id",
    "is_valid_symbol",
]
