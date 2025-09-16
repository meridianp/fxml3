"""
FIX Message Parser for FXML4.

This module provides parsing functionality for FIX protocol messages,
converting raw FIX strings into structured message objects.

CRITICAL MODULE: Essential for FIX protocol communication with brokers.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional, Union

from ..messages.admin import Heartbeat, Logout, TestRequest
from ..messages.base import FIXMessage
from ..messages.market_data import MarketDataRequest, MarketDataSnapshot
from ..messages.orders import ExecutionReport, NewOrderSingle

logger = logging.getLogger(__name__)


class FIXParseError(Exception):
    """Exception raised when FIX message parsing fails."""

    pass


class FIXParser:
    """Parser for FIX protocol messages.

    Converts raw FIX message strings into structured message objects
    for easier handling in the trading system.
    """

    # FIX field definitions (tag -> field name mapping)
    FIELD_MAP = {
        8: "begin_string",  # BeginString
        9: "body_length",  # BodyLength
        35: "msg_type",  # MsgType
        49: "sender_comp_id",  # SenderCompID
        56: "target_comp_id",  # TargetCompID
        34: "msg_seq_num",  # MsgSeqNum
        52: "sending_time",  # SendingTime
        10: "check_sum",  # CheckSum
        # Order fields
        11: "cl_ord_id",  # ClOrdID
        37: "order_id",  # OrderID
        17: "exec_id",  # ExecID
        20: "exec_trans_type",  # ExecTransType
        39: "ord_status",  # OrdStatus
        150: "exec_type",  # ExecType
        54: "side",  # Side
        38: "order_qty",  # OrderQty
        40: "ord_type",  # OrdType
        44: "price",  # Price
        55: "symbol",  # Symbol
        31: "last_px",  # LastPx
        32: "last_qty",  # LastQty
        151: "leaves_qty",  # LeavesQty
        14: "cum_qty",  # CumQty
        6: "avg_px",  # AvgPx
        # Market data fields
        262: "md_req_id",  # MDReqID
        263: "subscription_request_type",  # SubscriptionRequestType
        264: "market_depth",  # MarketDepth
        267: "no_md_entry_types",  # NoMDEntryTypes
        269: "md_entry_type",  # MDEntryType
        268: "no_md_entries",  # NoMDEntries
        270: "md_entry_px",  # MDEntryPx
        271: "md_entry_size",  # MDEntrySize
        # Admin fields
        112: "test_req_id",  # TestReqID
        58: "text",  # Text
    }

    # Message type mappings
    MESSAGE_TYPES = {
        "D": NewOrderSingle,  # New Order Single
        "8": ExecutionReport,  # Execution Report
        "0": Heartbeat,  # Heartbeat
        "1": TestRequest,  # Test Request
        "5": Logout,  # Logout
        "V": MarketDataRequest,  # Market Data Request
        "W": MarketDataSnapshot,  # Market Data Snapshot
    }

    def __init__(self, field_separator: str = "\x01"):
        """Initialize FIX parser.

        Args:
            field_separator: FIX field separator character (SOH)
        """
        self.field_separator = field_separator

    def parse(self, fix_string: str) -> FIXMessage:
        """Parse a FIX message string into a message object.

        Args:
            fix_string: Raw FIX message string

        Returns:
            Parsed FIX message object

        Raises:
            FIXParseError: If message parsing fails
        """
        try:
            # Clean and validate the message
            fix_string = fix_string.strip()
            if not fix_string:
                raise FIXParseError("Empty FIX message")

            # Parse fields from the message
            fields = self._parse_fields(fix_string)

            # Validate required fields
            self._validate_required_fields(fields)

            # Determine message type and create appropriate object
            msg_type = fields.get("msg_type")
            if not msg_type:
                raise FIXParseError("Missing message type (tag 35)")

            # Create message object
            message_class = self.MESSAGE_TYPES.get(msg_type, FIXMessage)
            message = message_class()

            # Populate message fields
            for field_name, value in fields.items():
                setattr(message, field_name, value)

            # Set original raw message
            message._raw_message = fix_string

            # Convert certain fields to appropriate types
            self._convert_field_types(message)

            logger.debug(f"Parsed {msg_type} message with {len(fields)} fields")
            return message

        except Exception as e:
            logger.error(f"Failed to parse FIX message: {e}")
            logger.debug(f"Raw message: {fix_string[:200]}...")
            raise FIXParseError(f"Parse error: {str(e)}") from e

    def _parse_fields(self, fix_string: str) -> Dict[str, Any]:
        """Parse FIX message into field dictionary.

        Args:
            fix_string: Raw FIX message string

        Returns:
            Dictionary of field names to values
        """
        fields = {}

        # Split message into tag=value pairs
        pairs = fix_string.split(self.field_separator)

        for pair in pairs:
            if not pair:
                continue

            if "=" not in pair:
                logger.warning(f"Invalid FIX field (no =): {pair}")
                continue

            try:
                tag_str, value = pair.split("=", 1)
                tag = int(tag_str)

                # Map tag to field name
                field_name = self.FIELD_MAP.get(tag, f"tag_{tag}")
                fields[field_name] = value

            except ValueError as e:
                logger.warning(f"Invalid FIX field format: {pair} - {e}")
                continue

        return fields

    def _validate_required_fields(self, fields: Dict[str, Any]) -> None:
        """Validate that required FIX fields are present.

        Args:
            fields: Parsed field dictionary

        Raises:
            FIXParseError: If required fields are missing
        """
        required_fields = [
            "begin_string",
            "msg_type",
            "sender_comp_id",
            "target_comp_id",
        ]

        missing_fields = [field for field in required_fields if field not in fields]

        if missing_fields:
            raise FIXParseError(f"Missing required fields: {missing_fields}")

    def _convert_field_types(self, message: FIXMessage) -> None:
        """Convert field values to appropriate Python types.

        Args:
            message: Message object to update
        """
        # Numeric fields
        numeric_fields = [
            "body_length",
            "msg_seq_num",
            "order_qty",
            "price",
            "last_px",
            "last_qty",
            "leaves_qty",
            "cum_qty",
            "avg_px",
            "market_depth",
            "no_md_entry_types",
            "no_md_entries",
            "md_entry_px",
            "md_entry_size",
        ]

        for field in numeric_fields:
            if hasattr(message, field):
                value = getattr(message, field)
                if value is not None and value != "":
                    try:
                        # Try int first, then float
                        if "." in str(value):
                            setattr(message, field, float(value))
                        else:
                            setattr(message, field, int(value))
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert {field}={value} to number")

        # Datetime fields
        datetime_fields = ["sending_time"]

        for field in datetime_fields:
            if hasattr(message, field):
                value = getattr(message, field)
                if value is not None and value != "":
                    try:
                        # Parse FIX timestamp format
                        dt = self._parse_fix_timestamp(value)
                        setattr(message, field, dt)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert {field}={value} to datetime")

    def _parse_fix_timestamp(self, timestamp_str: str) -> datetime:
        """Parse FIX timestamp string to datetime object.

        Args:
            timestamp_str: FIX timestamp string

        Returns:
            Parsed datetime object
        """
        # Common FIX timestamp formats
        formats = [
            "%Y%m%d-%H:%M:%S",  # YYYYMMDD-HH:MM:SS
            "%Y%m%d-%H:%M:%S.%f",  # YYYYMMDD-HH:MM:SS.sss
            "%Y-%m-%d %H:%M:%S",  # YYYY-MM-DD HH:MM:SS
            "%Y-%m-%dT%H:%M:%S",  # ISO format
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO with microseconds
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        # If no format matches, try to parse as epoch timestamp
        try:
            return datetime.fromtimestamp(float(timestamp_str))
        except (ValueError, TypeError):
            pass

        raise ValueError(f"Could not parse timestamp: {timestamp_str}")

    def parse_multiple(self, fix_messages: str) -> list:
        """Parse multiple FIX messages from a string.

        Args:
            fix_messages: String containing multiple FIX messages

        Returns:
            List of parsed message objects
        """
        messages = []

        # Split on message boundaries (8=FIX)
        message_parts = re.split(r"(?=8=FIX)", fix_messages)

        for part in message_parts:
            part = part.strip()
            if not part:
                continue

            try:
                message = self.parse(part)
                messages.append(message)
            except FIXParseError as e:
                logger.warning(f"Failed to parse message part: {e}")
                continue

        return messages

    def validate_checksum(self, fix_string: str) -> bool:
        """Validate FIX message checksum.

        Args:
            fix_string: Raw FIX message string

        Returns:
            True if checksum is valid
        """
        try:
            # Find checksum field
            if "10=" not in fix_string:
                logger.warning("No checksum field found")
                return False

            # Split message and checksum
            message_part, checksum_part = fix_string.rsplit("10=", 1)
            expected_checksum = checksum_part.split(self.field_separator)[0]

            # Calculate checksum
            calculated_checksum = sum(ord(c) for c in message_part + "10=") % 256

            return f"{calculated_checksum:03d}" == expected_checksum

        except Exception as e:
            logger.warning(f"Checksum validation failed: {e}")
            return False

    def get_message_info(self, fix_string: str) -> Dict[str, str]:
        """Extract basic message information without full parsing.

        Args:
            fix_string: Raw FIX message string

        Returns:
            Dictionary with basic message info
        """
        info = {}

        try:
            # Extract key fields using regex
            patterns = {
                "begin_string": r"8=([^" + self.field_separator + "]+)",
                "msg_type": r"35=([^" + self.field_separator + "]+)",
                "sender_comp_id": r"49=([^" + self.field_separator + "]+)",
                "target_comp_id": r"56=([^" + self.field_separator + "]+)",
                "msg_seq_num": r"34=([^" + self.field_separator + "]+)",
            }

            for field, pattern in patterns.items():
                match = re.search(pattern, fix_string)
                if match:
                    info[field] = match.group(1)

        except Exception as e:
            logger.warning(f"Failed to extract message info: {e}")

        return info


# Convenience functions
def parse_fix_message(fix_string: str) -> FIXMessage:
    """Parse a single FIX message string.

    Args:
        fix_string: Raw FIX message string

    Returns:
        Parsed FIX message object
    """
    parser = FIXParser()
    return parser.parse(fix_string)


def parse_fix_messages(fix_messages: str) -> list:
    """Parse multiple FIX messages from a string.

    Args:
        fix_messages: String containing multiple FIX messages

    Returns:
        List of parsed message objects
    """
    parser = FIXParser()
    return parser.parse_multiple(fix_messages)
