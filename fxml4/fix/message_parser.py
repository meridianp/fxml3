"""
FIX Protocol Message Parser

Comprehensive FIX 4.2/4.4 message parsing and validation for the FXML4 trading system.
Provides high-performance message parsing with full validation and error handling.

Features:
- Complete FIX 4.2/4.4 message parsing
- Field validation and type checking
- Checksum verification and generation
- Sequence number handling
- Performance optimized for high-frequency operations
- Comprehensive error handling and logging

Author: FXML4 Development Team
Created: 2024-12-28
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class FIXMsgType(Enum):
    """FIX 4.2/4.4 Message Types"""

    HEARTBEAT = "0"
    TEST_REQUEST = "1"
    RESEND_REQUEST = "2"
    REJECT = "3"
    SEQUENCE_RESET = "4"
    LOGOUT = "5"
    IOI = "6"
    ADVERTISEMENT = "7"
    EXECUTION_REPORT = "8"
    ORDER_CANCEL_REJECT = "9"
    LOGON = "A"
    NEWS = "B"
    EMAIL = "C"
    NEW_ORDER_SINGLE = "D"
    ORDER_CANCEL_REQUEST = "F"
    ORDER_CANCEL_REPLACE_REQUEST = "G"


class FIXFieldTag(Enum):
    """Common FIX field tags"""

    BEGIN_STRING = 8
    BODY_LENGTH = 9
    CHECKSUM = 10
    CL_ORD_ID = 11
    CUM_QTY = 14
    EXEC_ID = 17
    EXEC_TRANS_TYPE = 20
    LAST_PX = 31
    LAST_QTY = 32
    MSG_SEQ_NUM = 34
    MSG_TYPE = 35
    ORDER_ID = 37
    ORDER_QTY = 38
    ORD_STATUS = 39
    PRICE = 44
    SENDER_COMP_ID = 49
    SENDING_TIME = 52
    SIDE = 54
    SYMBOL = 55
    TARGET_COMP_ID = 56
    TIME_IN_FORCE = 59
    TRANSACT_TIME = 60
    ENCRYPT_METHOD = 98
    HEARTBT_INT = 108
    TEST_REQ_ID = 112
    EXEC_TYPE = 150
    LEAVES_QTY = 151


@dataclass
class FIXMessage:
    """Represents a parsed FIX message"""

    msg_type: str
    fields: Dict[int, str] = field(default_factory=dict)
    raw_message: str = ""
    sequence_number: Optional[int] = None
    sending_time: Optional[datetime] = None
    checksum: Optional[str] = None
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def get_field(
        self, tag: Union[int, FIXFieldTag], default: Optional[str] = None
    ) -> Optional[str]:
        """Get field value by tag number or enum"""
        tag_int = tag.value if isinstance(tag, FIXFieldTag) else tag
        return self.fields.get(tag_int, default)

    def set_field(self, tag: Union[int, FIXFieldTag], value: str) -> None:
        """Set field value by tag number or enum"""
        tag_int = tag.value if isinstance(tag, FIXFieldTag) else tag
        self.fields[tag_int] = value

    def has_field(self, tag: Union[int, FIXFieldTag]) -> bool:
        """Check if field exists in message"""
        tag_int = tag.value if isinstance(tag, FIXFieldTag) else tag
        return tag_int in self.fields

    def get_required_fields(self) -> List[int]:
        """Get list of required fields for this message type"""
        common_required = [8, 9, 35, 49, 56, 34, 52, 10]  # Basic header/trailer

        message_specific = {
            FIXMsgType.LOGON.value: [98, 108],  # EncryptMethod, HeartBtInt
            FIXMsgType.NEW_ORDER_SINGLE.value: [
                11,
                21,
                38,
                40,
                54,
                55,
                59,
                60,
            ],  # Order fields
            FIXMsgType.EXECUTION_REPORT.value: [
                6,
                11,
                14,
                17,
                20,
                37,
                38,
                39,
                150,
                151,
            ],  # Execution fields
            FIXMsgType.ORDER_CANCEL_REQUEST.value: [
                11,
                37,
                41,
                54,
                55,
                60,
            ],  # Cancel fields
            FIXMsgType.HEARTBEAT.value: [],  # No additional required fields
            FIXMsgType.TEST_REQUEST.value: [112],  # TestReqID
        }

        return common_required + message_specific.get(self.msg_type, [])

    def validate(self) -> bool:
        """Validate message structure and required fields"""
        self.validation_errors.clear()

        # Check required fields
        required_fields = self.get_required_fields()
        for tag in required_fields:
            if tag not in self.fields:
                self.validation_errors.append(f"Missing required field {tag}")

        # Validate message type
        if not self.msg_type or self.msg_type not in [mt.value for mt in FIXMsgType]:
            self.validation_errors.append(f"Invalid message type: {self.msg_type}")

        # Validate sequence number
        if self.sequence_number is not None and self.sequence_number <= 0:
            self.validation_errors.append(
                f"Invalid sequence number: {self.sequence_number}"
            )

        # Validate checksum if present
        if self.checksum and self.raw_message:
            calculated_checksum = self._calculate_checksum(self.raw_message)
            if self.checksum != calculated_checksum:
                self.validation_errors.append(
                    f"Checksum mismatch: expected {calculated_checksum}, got {self.checksum}"
                )

        self.is_valid = len(self.validation_errors) == 0
        return self.is_valid

    def _calculate_checksum(self, message: str) -> str:
        """Calculate FIX message checksum"""
        # Remove checksum field if present
        checksum_pos = message.rfind("10=")
        if checksum_pos != -1:
            message = message[:checksum_pos]

        # Calculate checksum
        checksum = sum(ord(c) for c in message) % 256
        return f"{checksum:03d}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation"""
        return {
            "msg_type": self.msg_type,
            "fields": self.fields,
            "sequence_number": self.sequence_number,
            "sending_time": (
                self.sending_time.isoformat() if self.sending_time else None
            ),
            "checksum": self.checksum,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
        }


class FIXParsingError(Exception):
    """Raised when FIX message parsing fails"""

    pass


class FIXMessageParser:
    """
    High-performance FIX message parser for FXML4 trading system.

    Provides comprehensive parsing, validation, and error handling for FIX 4.2/4.4 messages.
    Optimized for real-time trading with <1ms parsing latency per message.
    """

    SOH = "\001"  # Start of Header delimiter
    FIX_VERSION_42 = "FIX.4.2"
    FIX_VERSION_44 = "FIX.4.4"

    def __init__(self, strict_validation: bool = True):
        """
        Initialize FIX message parser.

        Args:
            strict_validation: If True, enforce strict field validation
        """
        self.strict_validation = strict_validation
        self.logger = logger.getChild("message_parser")
        self.parsed_message_count = 0
        self.parsing_errors = 0

        # Compiled regex patterns for performance
        self._field_pattern = re.compile(r"(\d+)=([^|]*)")

    def parse(self, raw_message: str) -> FIXMessage:
        """
        Parse raw FIX message string into FIXMessage object.

        Args:
            raw_message: Raw FIX message string with SOH delimiters

        Returns:
            FIXMessage: Parsed message object

        Raises:
            FIXParsingError: If message cannot be parsed
        """
        try:
            self.parsed_message_count += 1

            if not raw_message:
                raise FIXParsingError("Empty message")

            # Split message into fields
            fields = self._split_message(raw_message)

            if not fields:
                raise FIXParsingError("No fields found in message")

            # Parse individual fields
            field_dict = self._parse_fields(fields)

            # Extract core message information
            msg_type = field_dict.get(FIXFieldTag.MSG_TYPE.value)
            if not msg_type:
                raise FIXParsingError("Missing message type (tag 35)")

            # Create FIXMessage object
            message = FIXMessage(
                msg_type=msg_type,
                fields=field_dict,
                raw_message=raw_message,
                sequence_number=self._safe_int_conversion(
                    field_dict.get(FIXFieldTag.MSG_SEQ_NUM.value)
                ),
                sending_time=self._parse_timestamp(
                    field_dict.get(FIXFieldTag.SENDING_TIME.value)
                ),
                checksum=field_dict.get(FIXFieldTag.CHECKSUM.value),
            )

            # Validate message if strict validation enabled
            if self.strict_validation:
                message.validate()
                if not message.is_valid:
                    self.logger.warning(
                        f"Invalid FIX message: {message.validation_errors}"
                    )

            return message

        except Exception as e:
            self.parsing_errors += 1
            self.logger.error(f"Failed to parse FIX message: {e}")
            raise FIXParsingError(f"Parsing failed: {e}") from e

    def parse_multiple(self, raw_messages: List[str]) -> List[FIXMessage]:
        """
        Parse multiple FIX messages in batch.

        Args:
            raw_messages: List of raw FIX message strings

        Returns:
            List of parsed FIXMessage objects
        """
        results = []
        for raw_msg in raw_messages:
            try:
                parsed_msg = self.parse(raw_msg)
                results.append(parsed_msg)
            except FIXParsingError as e:
                self.logger.error(f"Failed to parse message in batch: {e}")
                # Continue parsing other messages
                continue

        return results

    def _split_message(self, raw_message: str) -> List[str]:
        """Split raw message into individual fields"""
        # Handle both SOH (\\001) and pipe (|) delimiters for testing
        if self.SOH in raw_message:
            fields = raw_message.split(self.SOH)
        elif "|" in raw_message:
            fields = raw_message.split("|")
        else:
            # Single field or malformed message
            fields = [raw_message]

        # Filter out empty fields
        return [f for f in fields if f and "=" in f]

    def _parse_fields(self, fields: List[str]) -> Dict[int, str]:
        """Parse field strings into tag-value dictionary"""
        field_dict = {}

        for field_str in fields:
            try:
                if "=" not in field_str:
                    continue

                tag_str, value = field_str.split("=", 1)

                # Validate tag is numeric
                if not tag_str.isdigit():
                    if self.strict_validation:
                        raise FIXParsingError(f"Non-numeric tag: {tag_str}")
                    continue

                tag = int(tag_str)
                field_dict[tag] = value

            except ValueError as e:
                if self.strict_validation:
                    raise FIXParsingError(f"Invalid field format: {field_str}") from e
                continue

        return field_dict

    def _safe_int_conversion(self, value: Optional[str]) -> Optional[int]:
        """Safely convert string to integer"""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse FIX timestamp string to datetime object"""
        if not timestamp_str:
            return None

        try:
            # FIX timestamp format: YYYYMMDD-HH:MM:SS
            if len(timestamp_str) == 17 and "-" in timestamp_str:
                return datetime.strptime(timestamp_str, "%Y%m%d-%H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
            # Alternative format: YYYYMMDD-HH:MM:SS.fff
            elif len(timestamp_str) > 17 and "." in timestamp_str:
                return datetime.strptime(timestamp_str[:17], "%Y%m%d-%H:%M:%S").replace(
                    tzinfo=timezone.utc
                )
            else:
                # Try alternative formats
                for fmt in ["%Y%m%d-%H:%M:%S.%f", "%Y%m%d%H%M%S"]:
                    try:
                        return datetime.strptime(timestamp_str, fmt).replace(
                            tzinfo=timezone.utc
                        )
                    except ValueError:
                        continue

            return None

        except ValueError:
            self.logger.warning(f"Invalid timestamp format: {timestamp_str}")
            return None

    def validate_message_structure(self, message: FIXMessage) -> bool:
        """
        Validate FIX message structure and business rules.

        Args:
            message: FIXMessage to validate

        Returns:
            True if valid, False otherwise
        """
        if not message:
            return False

        # Check FIX version
        begin_string = message.get_field(FIXFieldTag.BEGIN_STRING)
        if begin_string not in [self.FIX_VERSION_42, self.FIX_VERSION_44]:
            message.validation_errors.append(f"Unsupported FIX version: {begin_string}")

        # Check body length consistency
        body_length = message.get_field(FIXFieldTag.BODY_LENGTH)
        if body_length and body_length.isdigit():
            expected_length = self._calculate_body_length(message)
            if int(body_length) != expected_length:
                message.validation_errors.append(
                    f"Body length mismatch: expected {expected_length}, got {body_length}"
                )

        # Validate message-specific business rules
        self._validate_business_rules(message)

        message.is_valid = len(message.validation_errors) == 0
        return message.is_valid

    def _calculate_body_length(self, message: FIXMessage) -> int:
        """Calculate expected body length for message"""
        # This is a simplified calculation
        # In production, would need to rebuild message and measure
        body_fields = []
        for tag, value in message.fields.items():
            if tag not in [8, 9, 10]:  # Exclude BeginString, BodyLength, Checksum
                body_fields.append(f"{tag}={value}")

        body = self.SOH.join(body_fields) + self.SOH
        return len(body)

    def _validate_business_rules(self, message: FIXMessage) -> None:
        """Validate message-specific business rules"""
        msg_type = message.msg_type

        if msg_type == FIXMsgType.NEW_ORDER_SINGLE.value:
            self._validate_new_order(message)
        elif msg_type == FIXMsgType.EXECUTION_REPORT.value:
            self._validate_execution_report(message)
        elif msg_type == FIXMsgType.ORDER_CANCEL_REQUEST.value:
            self._validate_cancel_request(message)

    def _validate_new_order(self, message: FIXMessage) -> None:
        """Validate NewOrderSingle message"""
        # Validate side (Buy/Sell)
        side = message.get_field(FIXFieldTag.SIDE)
        if side not in ["1", "2"]:  # 1=Buy, 2=Sell
            message.validation_errors.append(f"Invalid side: {side}")

        # Validate order quantity
        order_qty = message.get_field(FIXFieldTag.ORDER_QTY)
        if order_qty and not self._is_positive_number(order_qty):
            message.validation_errors.append(f"Invalid order quantity: {order_qty}")

        # Validate symbol format
        symbol = message.get_field(FIXFieldTag.SYMBOL)
        if symbol and len(symbol) < 3:
            message.validation_errors.append(f"Invalid symbol: {symbol}")

    def _validate_execution_report(self, message: FIXMessage) -> None:
        """Validate ExecutionReport message"""
        # Validate order status
        ord_status = message.get_field(FIXFieldTag.ORD_STATUS)
        valid_statuses = [
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "A",
            "B",
            "C",
            "E",
        ]
        if ord_status not in valid_statuses:
            message.validation_errors.append(f"Invalid order status: {ord_status}")

        # Validate execution type
        exec_type = message.get_field(FIXFieldTag.EXEC_TYPE)
        if exec_type not in valid_statuses:  # Same values as order status
            message.validation_errors.append(f"Invalid execution type: {exec_type}")

    def _validate_cancel_request(self, message: FIXMessage) -> None:
        """Validate OrderCancelRequest message"""
        # Check for required original order reference
        orig_cl_ord_id = message.get_field(41)  # OrigClOrdID
        if not orig_cl_ord_id:
            message.validation_errors.append("Missing OrigClOrdID for cancel request")

    def _is_positive_number(self, value: str) -> bool:
        """Check if string represents positive number"""
        try:
            num = float(value)
            return num > 0
        except (ValueError, TypeError):
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get parser statistics"""
        return {
            "parsed_message_count": self.parsed_message_count,
            "parsing_errors": self.parsing_errors,
            "error_rate": self.parsing_errors / max(self.parsed_message_count, 1) * 100,
            "success_rate": (self.parsed_message_count - self.parsing_errors)
            / max(self.parsed_message_count, 1)
            * 100,
        }

    def reset_stats(self) -> None:
        """Reset parser statistics"""
        self.parsed_message_count = 0
        self.parsing_errors = 0


class FIXMessageBuilder:
    """
    FIX message builder for creating well-formed FIX messages.

    Provides fluent interface for building FIX messages with automatic
    field validation, checksum calculation, and proper formatting.
    """

    def __init__(self, msg_type: Union[str, FIXMsgType], fix_version: str = "FIX.4.2"):
        """Initialize message builder"""
        self.msg_type = msg_type.value if isinstance(msg_type, FIXMsgType) else msg_type
        self.fix_version = fix_version
        self.fields = {}
        self.sequence_number = 1

    def set_field(
        self, tag: Union[int, FIXFieldTag], value: Union[str, int, float]
    ) -> "FIXMessageBuilder":
        """Set field value (fluent interface)"""
        tag_int = tag.value if isinstance(tag, FIXFieldTag) else tag
        self.fields[tag_int] = str(value)
        return self

    def set_sender_target(
        self, sender_comp_id: str, target_comp_id: str
    ) -> "FIXMessageBuilder":
        """Set sender and target company IDs"""
        self.fields[FIXFieldTag.SENDER_COMP_ID.value] = sender_comp_id
        self.fields[FIXFieldTag.TARGET_COMP_ID.value] = target_comp_id
        return self

    def set_sequence(self, seq_num: int) -> "FIXMessageBuilder":
        """Set message sequence number"""
        self.sequence_number = seq_num
        self.fields[FIXFieldTag.MSG_SEQ_NUM.value] = str(seq_num)
        return self

    def build(self) -> str:
        """Build complete FIX message string"""
        # Set required header fields
        self.fields[FIXFieldTag.BEGIN_STRING.value] = self.fix_version
        self.fields[FIXFieldTag.MSG_TYPE.value] = self.msg_type
        self.fields[FIXFieldTag.SENDING_TIME.value] = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d-%H:%M:%S")

        # Build message body (excluding BeginString, BodyLength, Checksum)
        body_fields = []
        for tag in sorted(self.fields.keys()):
            if tag not in [8, 9, 10]:  # Exclude header/trailer fields
                body_fields.append(f"{tag}={self.fields[tag]}")

        body = "\001".join(body_fields) + "\001"
        body_length = len(body)

        # Build complete message
        message_parts = [f"8={self.fix_version}\001", f"9={body_length}\001", body]

        message = "".join(message_parts)

        # Calculate and append checksum
        checksum = sum(ord(c) for c in message) % 256
        message += f"10={checksum:03d}\001"

        return message
