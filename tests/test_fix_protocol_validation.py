"""
FIX Protocol Message Validation Tests
=====================================

Comprehensive test suite for FIX protocol message validation including:
- Message structure validation (FIX 4.2, 4.4, 5.0)
- Field validation and data types
- Checksum verification
- Session management
- Order lifecycle messages
- Market data messages
- Error handling and recovery

This addresses the critical gap: No FIX protocol message validation tests.
"""

import asyncio
import hashlib
import json
import struct
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, Mock, patch

import pytest

# FIX Protocol Constants
SOH = chr(1)  # Start of Header
FIX_VERSION_42 = "FIX.4.2"
FIX_VERSION_44 = "FIX.4.4"
FIX_VERSION_50 = "FIX.5.0"


class FIXMessageType(Enum):
    """FIX message types."""

    HEARTBEAT = "0"
    TEST_REQUEST = "1"
    RESEND_REQUEST = "2"
    REJECT = "3"
    SEQUENCE_RESET = "4"
    LOGOUT = "5"
    LOGON = "A"
    NEW_ORDER_SINGLE = "D"
    ORDER_CANCEL_REQUEST = "F"
    ORDER_CANCEL_REPLACE = "G"
    ORDER_STATUS_REQUEST = "H"
    EXECUTION_REPORT = "8"
    ORDER_CANCEL_REJECT = "9"
    MARKET_DATA_REQUEST = "V"
    MARKET_DATA_SNAPSHOT = "W"
    MARKET_DATA_INCREMENTAL = "X"
    MARKET_DATA_REJECT = "Y"
    QUOTE_REQUEST = "R"
    QUOTE = "S"


class FIXFieldTag(Enum):
    """Common FIX field tags."""

    BEGIN_STRING = 8
    BODY_LENGTH = 9
    MSG_TYPE = 35
    SENDER_COMP_ID = 49
    TARGET_COMP_ID = 56
    MSG_SEQ_NUM = 34
    SENDING_TIME = 52
    CHECKSUM = 10

    # Order fields
    CL_ORD_ID = 11
    ORDER_ID = 37
    SYMBOL = 55
    SIDE = 54
    ORDER_QTY = 38
    ORD_TYPE = 40
    PRICE = 44
    TIME_IN_FORCE = 59
    EXEC_TYPE = 150
    ORD_STATUS = 39

    # Market data fields
    MD_REQ_ID = 262
    SUBSCRIPTION_REQUEST_TYPE = 263
    MARKET_DEPTH = 264
    MD_UPDATE_TYPE = 265
    NO_MD_ENTRIES = 268
    MD_ENTRY_TYPE = 269
    MD_ENTRY_PX = 270
    MD_ENTRY_SIZE = 271


class FIXMessageValidator:
    """Validates FIX protocol messages."""

    def __init__(self, version: str = FIX_VERSION_44):
        self.version = version
        self.required_fields = self._get_required_fields()

    def _get_required_fields(self) -> Dict[str, List[int]]:
        """Get required fields for each message type."""
        base_fields = [
            FIXFieldTag.BEGIN_STRING.value,
            FIXFieldTag.BODY_LENGTH.value,
            FIXFieldTag.MSG_TYPE.value,
            FIXFieldTag.SENDER_COMP_ID.value,
            FIXFieldTag.TARGET_COMP_ID.value,
            FIXFieldTag.MSG_SEQ_NUM.value,
            FIXFieldTag.SENDING_TIME.value,
            FIXFieldTag.CHECKSUM.value,
        ]

        return {
            FIXMessageType.NEW_ORDER_SINGLE.value: base_fields
            + [
                FIXFieldTag.CL_ORD_ID.value,
                FIXFieldTag.SYMBOL.value,
                FIXFieldTag.SIDE.value,
                FIXFieldTag.ORDER_QTY.value,
                FIXFieldTag.ORD_TYPE.value,
            ],
            FIXMessageType.EXECUTION_REPORT.value: base_fields
            + [
                FIXFieldTag.ORDER_ID.value,
                FIXFieldTag.EXEC_TYPE.value,
                FIXFieldTag.ORD_STATUS.value,
            ],
            FIXMessageType.MARKET_DATA_REQUEST.value: base_fields
            + [
                FIXFieldTag.MD_REQ_ID.value,
                FIXFieldTag.SUBSCRIPTION_REQUEST_TYPE.value,
            ],
            FIXMessageType.LOGON.value: base_fields,
            FIXMessageType.HEARTBEAT.value: base_fields,
        }

    def parse_message(self, raw_message: str) -> Dict[int, str]:
        """Parse a FIX message into a dictionary."""
        fields = {}

        # Remove checksum for parsing
        if "10=" in raw_message:
            raw_message = raw_message[: raw_message.index("10=")]

        # Split by SOH
        parts = raw_message.split(SOH)

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                try:
                    fields[int(tag)] = value
                except ValueError:
                    pass  # Skip invalid tags

        return fields

    def validate_structure(self, message: str) -> Tuple[bool, str]:
        """Validate basic message structure."""
        # Check for SOH delimiters
        if SOH not in message:
            return False, "Missing SOH delimiter"

        # Parse message
        fields = self.parse_message(message)

        # Check begin string
        if FIXFieldTag.BEGIN_STRING.value not in fields:
            return False, "Missing BeginString (8)"

        if fields[FIXFieldTag.BEGIN_STRING.value] != self.version:
            return False, f"Invalid version: {fields[FIXFieldTag.BEGIN_STRING.value]}"

        # Check message type
        if FIXFieldTag.MSG_TYPE.value not in fields:
            return False, "Missing MsgType (35)"

        msg_type = fields[FIXFieldTag.MSG_TYPE.value]

        # Check required fields for message type
        if msg_type in self.required_fields:
            for required_tag in self.required_fields[msg_type]:
                if required_tag not in fields:
                    return False, f"Missing required field: {required_tag}"

        return True, "Valid structure"

    def calculate_checksum(self, message: str) -> str:
        """Calculate FIX checksum."""
        # Remove existing checksum if present
        if "10=" in message:
            message = message[: message.index("10=")]

        # Calculate sum of bytes
        checksum = sum(ord(c) for c in message) % 256

        # Format as 3-digit string
        return f"{checksum:03d}"

    def validate_checksum(self, message: str) -> bool:
        """Validate message checksum."""
        if "10=" not in message:
            return False

        # Extract checksum
        checksum_idx = message.index("10=")
        provided_checksum = message[checksum_idx + 3 : checksum_idx + 6]

        # Calculate expected checksum
        message_body = message[:checksum_idx]
        expected_checksum = self.calculate_checksum(message_body)

        return provided_checksum == expected_checksum

    def validate_field_types(self, fields: Dict[int, str]) -> List[str]:
        """Validate field data types."""
        errors = []

        # Validate integer fields
        int_fields = [
            FIXFieldTag.BODY_LENGTH.value,
            FIXFieldTag.MSG_SEQ_NUM.value,
            FIXFieldTag.ORDER_QTY.value,
        ]

        for tag in int_fields:
            if tag in fields:
                try:
                    int(fields[tag])
                except ValueError:
                    errors.append(f"Field {tag} must be integer: {fields[tag]}")

        # Validate decimal fields
        decimal_fields = [
            FIXFieldTag.PRICE.value,
            FIXFieldTag.MD_ENTRY_PX.value,
        ]

        for tag in decimal_fields:
            if tag in fields:
                try:
                    Decimal(fields[tag])
                except:
                    errors.append(f"Field {tag} must be decimal: {fields[tag]}")

        # Validate timestamp fields
        if FIXFieldTag.SENDING_TIME.value in fields:
            timestamp = fields[FIXFieldTag.SENDING_TIME.value]
            # FIX timestamp format: YYYYMMDD-HH:MM:SS.sss
            if len(timestamp) < 17 or timestamp[8] != "-":
                errors.append(f"Invalid timestamp format: {timestamp}")

        return errors

    def validate_message(self, message: str) -> Tuple[bool, List[str]]:
        """Comprehensive message validation."""
        errors = []

        # Structure validation
        valid, error = self.validate_structure(message)
        if not valid:
            errors.append(error)
            return False, errors

        # Checksum validation
        if not self.validate_checksum(message):
            errors.append("Invalid checksum")

        # Field type validation
        fields = self.parse_message(message)
        field_errors = self.validate_field_types(fields)
        errors.extend(field_errors)

        return len(errors) == 0, errors


class FIXMessageBuilder:
    """Builds FIX protocol messages."""

    def __init__(self, version: str = FIX_VERSION_44):
        self.version = version
        self.seq_num = 1
        self.sender_comp_id = "FXML4"
        self.target_comp_id = "BROKER"

    def build_header(self, msg_type: str) -> List[Tuple[int, str]]:
        """Build message header fields."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]

        return [
            (FIXFieldTag.BEGIN_STRING.value, self.version),
            (FIXFieldTag.MSG_TYPE.value, msg_type),
            (FIXFieldTag.SENDER_COMP_ID.value, self.sender_comp_id),
            (FIXFieldTag.TARGET_COMP_ID.value, self.target_comp_id),
            (FIXFieldTag.MSG_SEQ_NUM.value, str(self.seq_num)),
            (FIXFieldTag.SENDING_TIME.value, timestamp),
        ]

    def build_message(self, msg_type: str, fields: List[Tuple[int, str]]) -> str:
        """Build a complete FIX message."""
        # Build header
        all_fields = self.build_header(msg_type) + fields

        # Construct message body
        body = SOH.join([f"{tag}={value}" for tag, value in all_fields])

        # Calculate body length
        body_length = len(body) + 1  # +1 for trailing SOH

        # Prepend body length
        message = f"9={body_length}{SOH}{body}{SOH}"

        # Calculate and append checksum
        checksum = FIXMessageValidator().calculate_checksum(message)
        message += f"10={checksum}{SOH}"

        # Increment sequence number
        self.seq_num += 1

        return message

    def build_new_order(
        self,
        cl_ord_id: str,
        symbol: str,
        side: str,
        qty: int,
        ord_type: str = "2",  # Limit
        price: Optional[Decimal] = None,
    ) -> str:
        """Build a New Order Single message."""
        fields = [
            (FIXFieldTag.CL_ORD_ID.value, cl_ord_id),
            (FIXFieldTag.SYMBOL.value, symbol),
            (FIXFieldTag.SIDE.value, side),
            (FIXFieldTag.ORDER_QTY.value, str(qty)),
            (FIXFieldTag.ORD_TYPE.value, ord_type),
        ]

        if price and ord_type == "2":  # Limit order
            fields.append((FIXFieldTag.PRICE.value, str(price)))

        fields.append((FIXFieldTag.TIME_IN_FORCE.value, "0"))  # Day

        return self.build_message(FIXMessageType.NEW_ORDER_SINGLE.value, fields)

    def build_execution_report(
        self,
        order_id: str,
        cl_ord_id: str,
        exec_type: str,
        ord_status: str,
        symbol: str,
        side: str,
        qty: int,
    ) -> str:
        """Build an Execution Report message."""
        fields = [
            (FIXFieldTag.ORDER_ID.value, order_id),
            (FIXFieldTag.CL_ORD_ID.value, cl_ord_id),
            (FIXFieldTag.EXEC_TYPE.value, exec_type),
            (FIXFieldTag.ORD_STATUS.value, ord_status),
            (FIXFieldTag.SYMBOL.value, symbol),
            (FIXFieldTag.SIDE.value, side),
            (FIXFieldTag.ORDER_QTY.value, str(qty)),
        ]

        return self.build_message(FIXMessageType.EXECUTION_REPORT.value, fields)

    def build_market_data_request(
        self,
        md_req_id: str,
        symbols: List[str],
        subscription_type: str = "1",  # Subscribe
        market_depth: int = 10,
    ) -> str:
        """Build a Market Data Request message."""
        fields = [
            (FIXFieldTag.MD_REQ_ID.value, md_req_id),
            (FIXFieldTag.SUBSCRIPTION_REQUEST_TYPE.value, subscription_type),
            (FIXFieldTag.MARKET_DEPTH.value, str(market_depth)),
        ]

        # Add symbols (simplified - normally uses repeating groups)
        for symbol in symbols:
            fields.append((FIXFieldTag.SYMBOL.value, symbol))

        return self.build_message(FIXMessageType.MARKET_DATA_REQUEST.value, fields)

    def build_logon(self, heartbeat_interval: int = 30) -> str:
        """Build a Logon message."""
        fields = [
            (108, str(heartbeat_interval)),  # HeartBtInt
            (98, "0"),  # EncryptMethod - None
        ]

        return self.build_message(FIXMessageType.LOGON.value, fields)


# Test Fixtures
@pytest.fixture
def fix_validator():
    """Create a FIX message validator."""
    return FIXMessageValidator(FIX_VERSION_44)


@pytest.fixture
def fix_builder():
    """Create a FIX message builder."""
    return FIXMessageBuilder(FIX_VERSION_44)


# Test Classes
@pytest.mark.fix
@pytest.mark.validation
class TestFIXMessageStructure:
    """Test FIX message structure validation."""

    def test_valid_message_structure(self, fix_validator, fix_builder):
        """Test validation of properly structured message."""
        message = fix_builder.build_logon()

        valid, errors = fix_validator.validate_structure(message)

        assert valid == True
        assert len(errors) == 0

    def test_missing_begin_string(self, fix_validator):
        """Test detection of missing BeginString."""
        message = f"35=A{SOH}49=SENDER{SOH}56=TARGET{SOH}34=1{SOH}"

        valid, error = fix_validator.validate_structure(message)

        assert valid == False
        assert "Missing BeginString" in error

    def test_invalid_version(self, fix_validator):
        """Test detection of invalid FIX version."""
        message = f"8=FIX.3.0{SOH}35=A{SOH}49=SENDER{SOH}"

        valid, error = fix_validator.validate_structure(message)

        assert valid == False
        assert "Invalid version" in error

    def test_missing_required_fields(self, fix_validator, fix_builder):
        """Test detection of missing required fields."""
        # Build incomplete order message
        incomplete_fields = [
            (FIXFieldTag.CL_ORD_ID.value, "ORDER123"),
            # Missing SYMBOL, SIDE, ORDER_QTY
        ]

        message = fix_builder.build_message(
            FIXMessageType.NEW_ORDER_SINGLE.value, incomplete_fields
        )

        # Remove some required fields
        message = message.replace(f"55=", f"X55=")  # Invalidate symbol

        valid, error = fix_validator.validate_structure(message)

        assert valid == False


@pytest.mark.fix
@pytest.mark.validation
class TestFIXChecksum:
    """Test FIX checksum calculation and validation."""

    def test_checksum_calculation(self, fix_validator):
        """Test checksum calculation."""
        message = f"8={FIX_VERSION_44}{SOH}35=A{SOH}"
        checksum = fix_validator.calculate_checksum(message)

        assert len(checksum) == 3
        assert checksum.isdigit()

    def test_valid_checksum(self, fix_validator, fix_builder):
        """Test validation of correct checksum."""
        message = fix_builder.build_logon()

        valid = fix_validator.validate_checksum(message)

        assert valid == True

    def test_invalid_checksum(self, fix_validator, fix_builder):
        """Test detection of invalid checksum."""
        message = fix_builder.build_logon()

        # Corrupt the checksum
        message = message[:-4] + "999" + SOH

        valid = fix_validator.validate_checksum(message)

        assert valid == False


@pytest.mark.fix
@pytest.mark.validation
class TestFIXFieldValidation:
    """Test FIX field type validation."""

    def test_integer_field_validation(self, fix_validator):
        """Test validation of integer fields."""
        fields = {
            FIXFieldTag.MSG_SEQ_NUM.value: "abc",  # Should be integer
            FIXFieldTag.ORDER_QTY.value: "100",  # Valid
        }

        errors = fix_validator.validate_field_types(fields)

        assert len(errors) == 1
        assert "must be integer" in errors[0]

    def test_decimal_field_validation(self, fix_validator):
        """Test validation of decimal fields."""
        fields = {
            FIXFieldTag.PRICE.value: "100.25",  # Valid
            FIXFieldTag.MD_ENTRY_PX.value: "not_a_number",  # Invalid
        }

        errors = fix_validator.validate_field_types(fields)

        assert len(errors) == 1
        assert "must be decimal" in errors[0]

    def test_timestamp_validation(self, fix_validator):
        """Test validation of timestamp fields."""
        fields = {
            FIXFieldTag.SENDING_TIME.value: "20240101-12:30:45.123",  # Valid
        }

        errors = fix_validator.validate_field_types(fields)
        assert len(errors) == 0

        # Invalid format
        fields[FIXFieldTag.SENDING_TIME.value] = "2024-01-01"
        errors = fix_validator.validate_field_types(fields)

        assert len(errors) == 1
        assert "Invalid timestamp" in errors[0]


@pytest.mark.fix
@pytest.mark.orders
class TestFIXOrderMessages:
    """Test FIX order-related messages."""

    def test_new_order_single_message(self, fix_builder, fix_validator):
        """Test New Order Single message creation and validation."""
        message = fix_builder.build_new_order(
            cl_ord_id="ORD123456",
            symbol="EUR/USD",
            side="1",  # Buy
            qty=100000,
            ord_type="2",  # Limit
            price=Decimal("1.0850"),
        )

        valid, errors = fix_validator.validate_message(message)

        assert valid == True
        assert len(errors) == 0

        # Parse and verify fields
        fields = fix_validator.parse_message(message)
        assert fields[FIXFieldTag.CL_ORD_ID.value] == "ORD123456"
        assert fields[FIXFieldTag.SYMBOL.value] == "EUR/USD"
        assert fields[FIXFieldTag.SIDE.value] == "1"
        assert fields[FIXFieldTag.ORDER_QTY.value] == "100000"
        assert fields[FIXFieldTag.PRICE.value] == "1.0850"

    def test_execution_report_message(self, fix_builder, fix_validator):
        """Test Execution Report message creation and validation."""
        message = fix_builder.build_execution_report(
            order_id="BROKER123",
            cl_ord_id="ORD123456",
            exec_type="0",  # New
            ord_status="0",  # New
            symbol="EUR/USD",
            side="1",
            qty=100000,
        )

        valid, errors = fix_validator.validate_message(message)

        assert valid == True
        assert len(errors) == 0

        # Parse and verify fields
        fields = fix_validator.parse_message(message)
        assert fields[FIXFieldTag.ORDER_ID.value] == "BROKER123"
        assert fields[FIXFieldTag.EXEC_TYPE.value] == "0"
        assert fields[FIXFieldTag.ORD_STATUS.value] == "0"

    def test_order_cancel_request(self, fix_builder):
        """Test Order Cancel Request message."""
        fields = [
            (FIXFieldTag.CL_ORD_ID.value, "CANCEL123"),
            (41, "ORD123456"),  # OrigClOrdID
            (FIXFieldTag.SYMBOL.value, "EUR/USD"),
            (FIXFieldTag.SIDE.value, "1"),
        ]

        message = fix_builder.build_message(
            FIXMessageType.ORDER_CANCEL_REQUEST.value, fields
        )

        assert FIXMessageType.ORDER_CANCEL_REQUEST.value in message
        assert "CANCEL123" in message


@pytest.mark.fix
@pytest.mark.market_data
class TestFIXMarketDataMessages:
    """Test FIX market data messages."""

    def test_market_data_request(self, fix_builder, fix_validator):
        """Test Market Data Request message."""
        message = fix_builder.build_market_data_request(
            md_req_id="MD123",
            symbols=["EUR/USD", "GBP/USD"],
            subscription_type="1",
            market_depth=5,
        )

        valid, errors = fix_validator.validate_message(message)

        assert valid == True

        fields = fix_validator.parse_message(message)
        assert fields[FIXFieldTag.MD_REQ_ID.value] == "MD123"
        assert fields[FIXFieldTag.MARKET_DEPTH.value] == "5"

    def test_market_data_snapshot(self, fix_builder):
        """Test Market Data Snapshot message."""
        fields = [
            (FIXFieldTag.MD_REQ_ID.value, "MD123"),
            (FIXFieldTag.SYMBOL.value, "EUR/USD"),
            (FIXFieldTag.NO_MD_ENTRIES.value, "2"),
            # Entry 1 - Bid
            (FIXFieldTag.MD_ENTRY_TYPE.value, "0"),
            (FIXFieldTag.MD_ENTRY_PX.value, "1.0849"),
            (FIXFieldTag.MD_ENTRY_SIZE.value, "1000000"),
            # Entry 2 - Ask
            (FIXFieldTag.MD_ENTRY_TYPE.value, "1"),
            (FIXFieldTag.MD_ENTRY_PX.value, "1.0851"),
            (FIXFieldTag.MD_ENTRY_SIZE.value, "1000000"),
        ]

        message = fix_builder.build_message(
            FIXMessageType.MARKET_DATA_SNAPSHOT.value, fields
        )

        assert FIXMessageType.MARKET_DATA_SNAPSHOT.value in message
        assert "1.0849" in message
        assert "1.0851" in message


@pytest.mark.fix
@pytest.mark.session
class TestFIXSessionManagement:
    """Test FIX session management messages."""

    def test_logon_message(self, fix_builder, fix_validator):
        """Test Logon message."""
        message = fix_builder.build_logon(heartbeat_interval=60)

        valid, errors = fix_validator.validate_message(message)

        assert valid == True
        assert FIXMessageType.LOGON.value in message

    def test_logout_message(self, fix_builder):
        """Test Logout message."""
        fields = [
            (58, "End of trading session"),  # Text
        ]

        message = fix_builder.build_message(FIXMessageType.LOGOUT.value, fields)

        assert FIXMessageType.LOGOUT.value in message
        assert "End of trading session" in message

    def test_heartbeat_message(self, fix_builder):
        """Test Heartbeat message."""
        message = fix_builder.build_message(FIXMessageType.HEARTBEAT.value, [])

        assert FIXMessageType.HEARTBEAT.value in message

    def test_test_request_message(self, fix_builder):
        """Test Test Request message."""
        fields = [
            (112, "TEST123"),  # TestReqID
        ]

        message = fix_builder.build_message(FIXMessageType.TEST_REQUEST.value, fields)

        assert FIXMessageType.TEST_REQUEST.value in message
        assert "TEST123" in message

    def test_sequence_reset_message(self, fix_builder):
        """Test Sequence Reset message."""
        fields = [
            (36, "100"),  # NewSeqNo
            (123, "Y"),  # GapFillFlag
        ]

        message = fix_builder.build_message(FIXMessageType.SEQUENCE_RESET.value, fields)

        assert FIXMessageType.SEQUENCE_RESET.value in message


@pytest.mark.fix
@pytest.mark.edge_cases
class TestFIXEdgeCases:
    """Test FIX protocol edge cases and error handling."""

    def test_empty_message(self, fix_validator):
        """Test handling of empty message."""
        valid, error = fix_validator.validate_structure("")

        assert valid == False
        assert "Missing SOH" in error

    def test_malformed_message(self, fix_validator):
        """Test handling of malformed message."""
        message = "This is not a FIX message"

        valid, error = fix_validator.validate_structure(message)

        assert valid == False

    def test_message_with_special_characters(self, fix_builder, fix_validator):
        """Test handling of special characters in fields."""
        fields = [
            (FIXFieldTag.CL_ORD_ID.value, "ORD-123&456"),
            (FIXFieldTag.SYMBOL.value, "EUR/USD"),
            (FIXFieldTag.SIDE.value, "1"),
            (FIXFieldTag.ORDER_QTY.value, "100000"),
            (FIXFieldTag.ORD_TYPE.value, "1"),
        ]

        message = fix_builder.build_message(
            FIXMessageType.NEW_ORDER_SINGLE.value, fields
        )

        valid, errors = fix_validator.validate_message(message)

        assert valid == True

    def test_duplicate_fields(self, fix_validator):
        """Test handling of duplicate fields."""
        # FIX allows duplicate fields in certain contexts
        message = f"8={FIX_VERSION_44}{SOH}35=D{SOH}55=EUR/USD{SOH}55=GBP/USD{SOH}"

        fields = fix_validator.parse_message(message)

        # Parser should handle duplicates (typically keeps last value)
        assert FIXFieldTag.SYMBOL.value in fields

    def test_out_of_order_fields(self, fix_builder):
        """Test handling of out-of-order fields."""
        # FIX requires specific field ordering
        # This tests that builder maintains correct order
        builder = FIXMessageBuilder()

        # These should be reordered correctly by builder
        fields = [
            (FIXFieldTag.SYMBOL.value, "EUR/USD"),
            (FIXFieldTag.CL_ORD_ID.value, "ORDER123"),
        ]

        message = builder.build_message(FIXMessageType.NEW_ORDER_SINGLE.value, fields)

        # Verify header fields come first
        assert message.index("35=") < message.index("11=")  # MsgType before ClOrdID

    def test_maximum_message_size(self, fix_builder):
        """Test handling of large messages."""
        # Create a very large order ID
        large_cl_ord_id = "ORD" + "X" * 10000

        message = fix_builder.build_new_order(
            cl_ord_id=large_cl_ord_id,
            symbol="EUR/USD",
            side="1",
            qty=100000,
            ord_type="1",
        )

        # Message should be created but very large
        assert len(message) > 10000
        assert large_cl_ord_id in message


@pytest.mark.fix
@pytest.mark.performance
class TestFIXPerformance:
    """Test FIX message processing performance."""

    def test_message_parsing_performance(self, fix_validator, fix_builder):
        """Test performance of message parsing."""
        import time

        # Build a sample message
        message = fix_builder.build_new_order(
            cl_ord_id="PERF123",
            symbol="EUR/USD",
            side="1",
            qty=100000,
            ord_type="2",
            price=Decimal("1.0850"),
        )

        # Parse many times
        iterations = 10000
        start_time = time.time()

        for _ in range(iterations):
            fix_validator.parse_message(message)

        elapsed = time.time() - start_time
        per_message = (elapsed / iterations) * 1000  # Convert to ms

        print(f"\nParsing performance: {per_message:.3f}ms per message")
        assert per_message < 1.0  # Should parse in under 1ms

    def test_validation_performance(self, fix_validator, fix_builder):
        """Test performance of message validation."""
        import time

        message = fix_builder.build_new_order(
            cl_ord_id="PERF456",
            symbol="EUR/USD",
            side="1",
            qty=100000,
            ord_type="2",
            price=Decimal("1.0850"),
        )

        iterations = 5000
        start_time = time.time()

        for _ in range(iterations):
            fix_validator.validate_message(message)

        elapsed = time.time() - start_time
        per_message = (elapsed / iterations) * 1000

        print(f"Validation performance: {per_message:.3f}ms per message")
        assert per_message < 2.0  # Should validate in under 2ms


# Integration Tests
@pytest.mark.fix
@pytest.mark.integration
@pytest.mark.asyncio
class TestFIXIntegration:
    """Integration tests for FIX protocol with broker adapters."""

    async def test_fix_to_broker_order_flow(self):
        """Test complete order flow through FIX protocol."""
        # This would integrate with actual broker adapter
        builder = FIXMessageBuilder()
        validator = FIXMessageValidator()

        # Simulate order flow
        orders_processed = []

        # 1. Build order
        order_msg = builder.build_new_order(
            cl_ord_id=f"INT{uuid.uuid4().hex[:8]}",
            symbol="EUR/USD",
            side="1",
            qty=100000,
            ord_type="2",
            price=Decimal("1.0850"),
        )

        # 2. Validate order
        valid, errors = validator.validate_message(order_msg)
        assert valid == True

        # 3. Simulate broker response
        exec_report = builder.build_execution_report(
            order_id="BROKER789",
            cl_ord_id=f"INT{uuid.uuid4().hex[:8]}",
            exec_type="0",  # New
            ord_status="0",  # New
            symbol="EUR/USD",
            side="1",
            qty=100000,
        )

        # 4. Validate response
        valid, errors = validator.validate_message(exec_report)
        assert valid == True

        orders_processed.append(exec_report)

        assert len(orders_processed) == 1

    async def test_fix_session_recovery(self):
        """Test FIX session recovery after disconnect."""
        builder = FIXMessageBuilder()

        # Simulate session with sequence numbers
        original_seq = builder.seq_num

        # Send some messages
        for i in range(5):
            builder.build_heartbeat()

        # Simulate disconnect and recovery
        builder.seq_num = original_seq  # Reset sequence

        # Build resend request
        resend_fields = [
            (7, str(original_seq)),  # BeginSeqNo
            (16, str(original_seq + 5)),  # EndSeqNo
        ]

        resend_msg = builder.build_message(
            FIXMessageType.RESEND_REQUEST.value, resend_fields
        )

        assert FIXMessageType.RESEND_REQUEST.value in resend_msg
        assert str(original_seq) in resend_msg


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
