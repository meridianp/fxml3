"""
FIX Message Builder for FXML4.

This module provides building functionality for FIX protocol messages,
converting structured data into FIX message strings.

CRITICAL MODULE: Essential for FIX protocol communication with brokers.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Union

from ..messages.base import FIXMessage

logger = logging.getLogger(__name__)


class FIXBuildError(Exception):
    """Exception raised when FIX message building fails."""

    pass


class FIXBuilder:
    """Builder for FIX protocol messages.

    Converts structured message objects into FIX message strings
    for transmission to broker systems.
    """

    def __init__(self, field_separator: str = "\x01"):
        """Initialize FIX builder.

        Args:
            field_separator: FIX field separator character (SOH)
        """
        self.field_separator = field_separator

        # Field tag mappings (inverse of parser)
        self.FIELD_TAGS = {
            "begin_string": 8,  # BeginString
            "body_length": 9,  # BodyLength
            "msg_type": 35,  # MsgType
            "sender_comp_id": 49,  # SenderCompID
            "target_comp_id": 56,  # TargetCompID
            "msg_seq_num": 34,  # MsgSeqNum
            "sending_time": 52,  # SendingTime
            "check_sum": 10,  # CheckSum
            # Order fields
            "cl_ord_id": 11,  # ClOrdID
            "order_id": 37,  # OrderID
            "exec_id": 17,  # ExecID
            "exec_trans_type": 20,  # ExecTransType
            "ord_status": 39,  # OrdStatus
            "exec_type": 150,  # ExecType
            "side": 54,  # Side
            "order_qty": 38,  # OrderQty
            "ord_type": 40,  # OrdType
            "price": 44,  # Price
            "symbol": 55,  # Symbol
            "last_px": 31,  # LastPx
            "last_qty": 32,  # LastQty
            "leaves_qty": 151,  # LeavesQty
            "cum_qty": 14,  # CumQty
            "avg_px": 6,  # AvgPx
            # Market data fields
            "md_req_id": 262,  # MDReqID
            "subscription_request_type": 263,  # SubscriptionRequestType
            "market_depth": 264,  # MarketDepth
            "no_md_entry_types": 267,  # NoMDEntryTypes
            "md_entry_type": 269,  # MDEntryType
            "no_md_entries": 268,  # NoMDEntries
            "md_entry_px": 270,  # MDEntryPx
            "md_entry_size": 271,  # MDEntrySize
            # Admin fields
            "test_req_id": 112,  # TestReqID
            "text": 58,  # Text
        }

    def build(self, message: FIXMessage) -> str:
        """Build a FIX message string from a message object.

        Args:
            message: FIX message object to convert

        Returns:
            FIX message string

        Raises:
            FIXBuildError: If message building fails
        """
        try:
            # Extract fields from message object
            fields = self._extract_fields(message)

            # Validate required fields
            self._validate_required_fields(fields)

            # Build message string
            fix_string = self._build_message_string(fields)

            # Calculate and append checksum
            fix_string = self._append_checksum(fix_string)

            logger.debug(f"Built FIX message: {fix_string[:100]}...")
            return fix_string

        except Exception as e:
            logger.error(f"Failed to build FIX message: {e}")
            raise FIXBuildError(f"Build error: {str(e)}") from e

    def _extract_fields(self, message: FIXMessage) -> Dict[int, str]:
        """Extract fields from message object into tag-value pairs.

        Args:
            message: Message object to extract from

        Returns:
            Dictionary of field tags to values
        """
        fields = {}

        # Iterate through message attributes
        for field_name in dir(message):
            if field_name.startswith("_") or callable(getattr(message, field_name)):
                continue

            value = getattr(message, field_name)
            if value is None:
                continue

            # Get field tag
            tag = self.FIELD_TAGS.get(field_name)
            if tag is None:
                # Handle unknown fields (assume tag_N format)
                if field_name.startswith("tag_"):
                    try:
                        tag = int(field_name[4:])
                    except ValueError:
                        logger.warning(f"Unknown field: {field_name}")
                        continue
                else:
                    logger.warning(f"Unknown field: {field_name}")
                    continue

            # Convert value to string
            str_value = self._format_field_value(field_name, value)
            fields[tag] = str_value

        return fields

    def _format_field_value(self, field_name: str, value: Any) -> str:
        """Format field value for FIX message.

        Args:
            field_name: Name of the field
            value: Value to format

        Returns:
            Formatted string value
        """
        if isinstance(value, datetime):
            # Format datetime for FIX
            return value.strftime("%Y%m%d-%H:%M:%S")
        elif isinstance(value, (int, float)):
            # Format numeric values
            if field_name in ["price", "last_px", "avg_px", "md_entry_px"]:
                return f"{float(value):.5f}"
            else:
                return str(value)
        else:
            return str(value)

    def _validate_required_fields(self, fields: Dict[int, str]) -> None:
        """Validate that required FIX fields are present.

        Args:
            fields: Field dictionary to validate

        Raises:
            FIXBuildError: If required fields are missing
        """
        required_tags = [
            8,
            35,
            49,
            56,
        ]  # BeginString, MsgType, SenderCompID, TargetCompID

        missing_tags = [tag for tag in required_tags if tag not in fields]

        if missing_tags:
            raise FIXBuildError(f"Missing required field tags: {missing_tags}")

    def _build_message_string(self, fields: Dict[int, str]) -> str:
        """Build FIX message string from fields.

        Args:
            fields: Dictionary of field tags to values

        Returns:
            FIX message string (without checksum)
        """
        # Sort fields by tag (FIX standard order)
        sorted_tags = sorted(fields.keys())

        # Build field=value pairs
        field_pairs = []
        for tag in sorted_tags:
            if tag == 10:  # Skip checksum, will be calculated
                continue
            field_pairs.append(f"{tag}={fields[tag]}")

        # Join with field separator
        message_body = self.field_separator.join(field_pairs)

        # Calculate body length (excluding BeginString and BodyLength fields)
        body_start_pos = message_body.find(
            "35="
        )  # Start after BeginString and BodyLength
        if body_start_pos != -1:
            body_length = len(message_body[body_start_pos:]) + len(self.field_separator)

            # Insert body length after BeginString
            begin_string_part = f"8={fields.get(8, 'FIX.4.2')}{self.field_separator}"
            body_length_part = f"9={body_length}{self.field_separator}"
            remaining_part = message_body[message_body.find("35=") :]

            message_string = begin_string_part + body_length_part + remaining_part
        else:
            message_string = message_body

        return message_string

    def _append_checksum(self, message_string: str) -> str:
        """Calculate and append checksum to message.

        Args:
            message_string: Message string without checksum

        Returns:
            Complete FIX message with checksum
        """
        # Calculate checksum
        checksum = (
            sum(ord(c) for c in message_string + f"{self.field_separator}10=") % 256
        )

        # Append checksum field
        return f"{message_string}{self.field_separator}10={checksum:03d}{self.field_separator}"

    def build_from_dict(self, message_dict: Dict[str, Any]) -> str:
        """Build FIX message from dictionary.

        Args:
            message_dict: Dictionary with field names and values

        Returns:
            FIX message string
        """

        # Create temporary message object
        class TempMessage:
            pass

        message = TempMessage()

        # Set attributes from dictionary
        for field_name, value in message_dict.items():
            setattr(message, field_name, value)

        return self.build(message)

    def build_heartbeat(
        self, sender_comp_id: str, target_comp_id: str, msg_seq_num: int
    ) -> str:
        """Build a heartbeat message.

        Args:
            sender_comp_id: Sender company ID
            target_comp_id: Target company ID
            msg_seq_num: Message sequence number

        Returns:
            Heartbeat FIX message string
        """
        message_dict = {
            "begin_string": "FIX.4.2",
            "msg_type": "0",  # Heartbeat
            "sender_comp_id": sender_comp_id,
            "target_comp_id": target_comp_id,
            "msg_seq_num": msg_seq_num,
            "sending_time": datetime.utcnow(),
        }

        return self.build_from_dict(message_dict)

    def build_test_request(
        self,
        sender_comp_id: str,
        target_comp_id: str,
        msg_seq_num: int,
        test_req_id: str,
    ) -> str:
        """Build a test request message.

        Args:
            sender_comp_id: Sender company ID
            target_comp_id: Target company ID
            msg_seq_num: Message sequence number
            test_req_id: Test request ID

        Returns:
            Test request FIX message string
        """
        message_dict = {
            "begin_string": "FIX.4.2",
            "msg_type": "1",  # Test Request
            "sender_comp_id": sender_comp_id,
            "target_comp_id": target_comp_id,
            "msg_seq_num": msg_seq_num,
            "sending_time": datetime.utcnow(),
            "test_req_id": test_req_id,
        }

        return self.build_from_dict(message_dict)


# Alias for backward compatibility
FIXMessageBuilder = FIXBuilder


# Convenience functions
def build_fix_message(message: FIXMessage) -> str:
    """Build a single FIX message.

    Args:
        message: FIX message object

    Returns:
        FIX message string
    """
    builder = FIXBuilder()
    return builder.build(message)


def build_fix_from_dict(message_dict: Dict[str, Any]) -> str:
    """Build FIX message from dictionary.

    Args:
        message_dict: Dictionary with field names and values

    Returns:
        FIX message string
    """
    builder = FIXBuilder()
    return builder.build_from_dict(message_dict)
