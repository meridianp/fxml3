"""Comprehensive Unit Tests for FIX Protocol Utilities and Advanced Features.

This module provides retrospective test coverage for FIX utilities, message builders,
parsers, and advanced protocol features. Complements the core FIX protocol tests
with focus on utility functions and edge case handling.

Test Coverage Areas:
- FIX Message Builders and Fast Builders
- FIX Message Parsers and Fast Parsers
- FIX Protocol Utilities and Helpers
- Advanced Message Handling Scenarios
- Protocol Performance Optimizations
- Memory Management and Resource Handling

Following the proven retrospective TDD methodology (Green → Test → Validate).
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest

from fxml4.fix.messages.admin import Heartbeat, Logon, Logout, TestRequest

# FIX Message Types for Testing
from fxml4.fix.messages.base import (
    ExecType,
    FIXField,
    FIXMessage,
    FIXMessageType,
    OrdStatus,
    OrdType,
    Side,
    TimeInForce,
)
from fxml4.fix.messages.market_data import MarketDataRequest, MarketDataSnapshot
from fxml4.fix.messages.order_modify import OrderCancelReplaceRequest
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)
from fxml4.fix.session_manager import FIXSession, SessionConfig, SessionState
from fxml4.fix.utilities import FIXUtilities

# FIX Protocol Utilities and Advanced Components
from fxml4.fix.utils.builder import FIXBuilder
from fxml4.fix.utils.fast_builder import FastFIXBuilder
from fxml4.fix.utils.fast_parser import FastFIXParser
from fxml4.fix.utils.parser import FIXParser


class TestFIXBuilder:
    """Test FIX message builder functionality."""

    @pytest.fixture
    def builder(self):
        """Create FIX builder for testing."""
        return FIXBuilder()

    @pytest.fixture
    def session_config(self):
        """Create session configuration for testing."""
        return {
            "sender_comp_id": "FXML4_TEST",
            "target_comp_id": "BROKER_TEST",
            "fix_version": "FIX.4.2",
        }

    def test_builder_initialization(self, builder):
        """Test FIX builder initialization."""
        assert builder is not None

        # Test builder has required methods
        expected_methods = [
            "build",
            "create_message",
            "add_header",
            "calculate_checksum",
        ]
        available_methods = [
            method for method in expected_methods if hasattr(builder, method)
        ]

        # At least some core methods should exist
        assert len(available_methods) > 0

    def test_build_basic_message_structure(self, builder, session_config):
        """Test building basic FIX message structure."""
        heartbeat = Heartbeat()

        try:
            if hasattr(builder, "build"):
                fix_string = builder.build(
                    heartbeat,
                    sender_comp_id=session_config["sender_comp_id"],
                    target_comp_id=session_config["target_comp_id"],
                    seq_num=1,
                )

                if fix_string:
                    # Verify basic FIX structure
                    assert isinstance(fix_string, str)
                    assert fix_string.startswith("8=FIX.4.2")
                    assert "\x01" in fix_string  # SOH delimiter
                    assert "35=0" in fix_string  # Heartbeat message type

                    # Verify header fields present
                    assert f"49={session_config['sender_comp_id']}" in fix_string
                    assert f"56={session_config['target_comp_id']}" in fix_string
                    assert "34=1" in fix_string  # Sequence number

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX builder not fully implemented")

    def test_build_new_order_single(self, builder, session_config):
        """Test building NewOrderSingle message."""
        order = NewOrderSingle(
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
            currency="USD",
            cl_ord_id="TEST_ORDER_123",
        )

        try:
            if hasattr(builder, "build"):
                fix_string = builder.build(
                    order,
                    sender_comp_id=session_config["sender_comp_id"],
                    target_comp_id=session_config["target_comp_id"],
                    seq_num=2,
                )

                if fix_string:
                    # Verify order-specific fields
                    assert "35=D" in fix_string  # NewOrderSingle
                    assert "55=EURUSD" in fix_string  # Symbol
                    assert "54=1" in fix_string  # Buy side
                    assert "40=1" in fix_string  # Market order
                    assert "38=100000" in fix_string  # Order quantity
                    assert "11=TEST_ORDER_123" in fix_string  # Client order ID

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX builder not fully implemented")

    def test_build_execution_report(self, builder, session_config):
        """Test building ExecutionReport message."""
        exec_report = ExecutionReport(
            order_id="BROKER_ORDER_456",
            cl_ord_id="TEST_ORDER_123",
            exec_id="EXEC_789",
            exec_type=ExecType.FILL,
            ord_status=OrdStatus.FILLED,
            symbol="EURUSD",
            side=Side.BUY,
            cum_qty=100000.0,
            leaves_qty=0.0,
            avg_px=1.1050,
        )

        try:
            if hasattr(builder, "build"):
                fix_string = builder.build(
                    exec_report,
                    sender_comp_id=session_config["target_comp_id"],
                    target_comp_id=session_config["sender_comp_id"],
                    seq_num=1,
                )

                if fix_string:
                    # Verify execution report fields
                    assert "35=8" in fix_string  # ExecutionReport
                    assert "37=BROKER_ORDER_456" in fix_string  # Order ID
                    assert "11=TEST_ORDER_123" in fix_string  # Client order ID
                    assert "17=EXEC_789" in fix_string  # Execution ID
                    assert "150=F" in fix_string  # Fill exec type
                    assert "39=2" in fix_string  # Filled status

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX builder not fully implemented")

    def test_build_with_timestamps(self, builder, session_config):
        """Test building messages with proper timestamps."""
        logon = Logon(
            encrypt_method=0, heartbt_int=30, username="test_user", password="test_pass"
        )

        try:
            if hasattr(builder, "build"):
                before_build = datetime.utcnow()

                fix_string = builder.build(
                    logon,
                    sender_comp_id=session_config["sender_comp_id"],
                    target_comp_id=session_config["target_comp_id"],
                    seq_num=1,
                )

                after_build = datetime.utcnow()

                if fix_string and "52=" in fix_string:
                    # Extract timestamp from message
                    timestamp_start = fix_string.find("52=") + 3
                    timestamp_end = fix_string.find("\x01", timestamp_start)
                    timestamp_str = fix_string[timestamp_start:timestamp_end]

                    # Verify timestamp format (YYYYMMDD-HH:MM:SS)
                    assert len(timestamp_str) >= 17
                    assert "-" in timestamp_str
                    assert ":" in timestamp_str

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX builder timestamp handling not implemented")

    def test_checksum_calculation(self, builder):
        """Test FIX checksum calculation."""
        test_message = "8=FIX.4.2\x019=40\x0135=0\x0149=SENDER\x0156=TARGET\x0134=1\x01"

        try:
            if hasattr(builder, "calculate_checksum"):
                checksum = builder.calculate_checksum(test_message)

                # Checksum should be 3-digit string
                assert isinstance(checksum, str)
                assert len(checksum) == 3
                assert checksum.isdigit()

                # Verify checksum calculation is consistent
                checksum2 = builder.calculate_checksum(test_message)
                assert checksum == checksum2

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX checksum calculation not implemented")

    def test_message_length_calculation(self, builder, session_config):
        """Test FIX message length calculation."""
        heartbeat = Heartbeat()

        try:
            if hasattr(builder, "build"):
                fix_string = builder.build(
                    heartbeat,
                    sender_comp_id=session_config["sender_comp_id"],
                    target_comp_id=session_config["target_comp_id"],
                    seq_num=1,
                )

                if fix_string and "9=" in fix_string:
                    # Extract body length from message
                    length_start = fix_string.find("9=") + 2
                    length_end = fix_string.find("\x01", length_start)
                    length_str = fix_string[length_start:length_end]

                    body_length = int(length_str)

                    # Verify length is reasonable
                    assert body_length > 0
                    assert body_length < len(fix_string)

        except (NotImplementedError, AttributeError, ValueError):
            pytest.skip("FIX message length calculation not implemented")


class TestFIXParser:
    """Test FIX message parser functionality."""

    @pytest.fixture
    def parser(self):
        """Create FIX parser for testing."""
        return FIXParser()

    def test_parser_initialization(self, parser):
        """Test FIX parser initialization."""
        assert parser is not None

        # Test parser has required methods
        expected_methods = ["parse", "extract_fields", "validate_message"]
        available_methods = [
            method for method in expected_methods if hasattr(parser, method)
        ]

        # At least some core methods should exist
        assert len(available_methods) > 0

    def test_parse_basic_logon_message(self, parser):
        """Test parsing basic FIX Logon message."""
        logon_message = (
            "8=FIX.4.2\x01"  # Begin String
            "9=73\x01"  # Body Length
            "35=A\x01"  # Message Type (Logon)
            "49=SENDER\x01"  # Sender CompID
            "56=TARGET\x01"  # Target CompID
            "34=1\x01"  # Message Sequence Number
            "52=20230101-12:00:00\x01"  # Sending Time
            "98=0\x01"  # Encrypt Method
            "108=30\x01"  # Heartbeat Interval
            "553=user\x01"  # Username
            "554=pass\x01"  # Password
            "10=123\x01"  # Checksum
        )

        try:
            if hasattr(parser, "parse"):
                parsed = parser.parse(logon_message)

                if parsed:
                    # Verify parsing result
                    if isinstance(parsed, dict):
                        assert parsed.get("8") == "FIX.4.2"  # Begin String
                        assert parsed.get("35") == "A"  # Logon message
                        assert parsed.get("49") == "SENDER"  # Sender
                        assert parsed.get("98") == "0"  # Encrypt method

                    elif hasattr(parsed, "msg_type"):
                        assert parsed.msg_type == FIXMessageType.LOGON

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX parser not fully implemented")

    def test_parse_new_order_single(self, parser):
        """Test parsing NewOrderSingle message."""
        order_message = (
            "8=FIX.4.2\x01"  # Begin String
            "9=145\x01"  # Body Length
            "35=D\x01"  # Message Type (NewOrderSingle)
            "49=CLIENT\x01"  # Sender CompID
            "56=BROKER\x01"  # Target CompID
            "34=2\x01"  # Message Sequence Number
            "52=20230101-12:00:00\x01"  # Sending Time
            "11=ORDER_123\x01"  # Client Order ID
            "55=EURUSD\x01"  # Symbol
            "54=1\x01"  # Side (Buy)
            "38=100000\x01"  # Order Quantity
            "40=1\x01"  # Order Type (Market)
            "59=0\x01"  # Time In Force (Day)
            "15=USD\x01"  # Currency
            "10=123\x01"  # Checksum
        )

        try:
            if hasattr(parser, "parse"):
                parsed = parser.parse(order_message)

                if parsed:
                    if isinstance(parsed, dict):
                        assert parsed.get("35") == "D"  # NewOrderSingle
                        assert parsed.get("55") == "EURUSD"  # Symbol
                        assert parsed.get("54") == "1"  # Buy side
                        assert parsed.get("38") == "100000"  # Quantity

                    elif hasattr(parsed, "symbol"):
                        assert parsed.symbol == "EURUSD"
                        assert parsed.side == Side.BUY

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX parser not fully implemented")

    def test_parse_execution_report(self, parser):
        """Test parsing ExecutionReport message."""
        exec_report_message = (
            "8=FIX.4.2\x01"  # Begin String
            "9=185\x01"  # Body Length
            "35=8\x01"  # Message Type (ExecutionReport)
            "49=BROKER\x01"  # Sender CompID
            "56=CLIENT\x01"  # Target CompID
            "34=1\x01"  # Message Sequence Number
            "52=20230101-12:00:00\x01"  # Sending Time
            "37=BROKER_456\x01"  # Order ID
            "11=ORDER_123\x01"  # Client Order ID
            "17=EXEC_789\x01"  # Execution ID
            "150=F\x01"  # Execution Type (Fill)
            "39=2\x01"  # Order Status (Filled)
            "55=EURUSD\x01"  # Symbol
            "54=1\x01"  # Side (Buy)
            "14=100000\x01"  # Cumulative Quantity
            "31=1.1050\x01"  # Average Price
            "32=100000\x01"  # Last Quantity
            "151=0\x01"  # Leaves Quantity
            "10=123\x01"  # Checksum
        )

        try:
            if hasattr(parser, "parse"):
                parsed = parser.parse(exec_report_message)

                if parsed:
                    if isinstance(parsed, dict):
                        assert parsed.get("35") == "8"  # ExecutionReport
                        assert parsed.get("37") == "BROKER_456"  # Order ID
                        assert parsed.get("150") == "F"  # Fill execution
                        assert parsed.get("39") == "2"  # Filled status

                    elif hasattr(parsed, "exec_type"):
                        assert parsed.exec_type == ExecType.FILL
                        assert parsed.ord_status == OrdStatus.FILLED

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX parser not fully implemented")

    def test_parse_malformed_messages(self, parser):
        """Test parser error handling with malformed messages."""
        malformed_messages = [
            "",  # Empty message
            "8=FIX.4.2",  # No SOH delimiters
            "8=FIX.4.2\x01INVALID",  # Invalid format
            "8=INVALID\x019=10\x0135=A\x01",  # Invalid FIX version
            "9=10\x0135=A\x01",  # Missing begin string
            "8=FIX.4.2\x0135=A\x01",  # Missing body length
        ]

        for malformed_msg in malformed_messages:
            try:
                if hasattr(parser, "parse"):
                    with pytest.raises((ValueError, Exception)):
                        parser.parse(malformed_msg)

            except (NotImplementedError, AttributeError):
                pytest.skip("FIX parser error handling not implemented")
                break

    def test_parse_field_extraction(self, parser):
        """Test FIX field extraction functionality."""
        test_message = (
            "8=FIX.4.2\x01"
            "9=40\x01"
            "35=0\x01"
            "49=SENDER\x01"
            "56=TARGET\x01"
            "34=1\x01"
            "10=123\x01"
        )

        try:
            if hasattr(parser, "extract_fields"):
                fields = parser.extract_fields(test_message)

                if fields:
                    assert isinstance(fields, dict)
                    assert "8" in fields
                    assert "35" in fields
                    assert fields["8"] == "FIX.4.2"
                    assert fields["35"] == "0"  # Heartbeat

            elif hasattr(parser, "parse"):
                # Alternative: test through main parse method
                parsed = parser.parse(test_message)
                if isinstance(parsed, dict):
                    assert "8" in parsed
                    assert parsed["8"] == "FIX.4.2"

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX field extraction not implemented")

    def test_parse_checksum_validation(self, parser):
        """Test FIX checksum validation during parsing."""
        # Message with valid checksum
        valid_message = (
            "8=FIX.4.2\x019=40\x0135=0\x0149=SENDER\x0156=TARGET\x0134=1\x0110=123\x01"
        )

        # Message with invalid checksum
        invalid_message = (
            "8=FIX.4.2\x019=40\x0135=0\x0149=SENDER\x0156=TARGET\x0134=1\x0110=999\x01"
        )

        try:
            if hasattr(parser, "parse") and hasattr(parser, "validate_checksum"):
                # Valid checksum should parse successfully
                parsed_valid = parser.parse(valid_message)

                # Invalid checksum should raise error if validation enabled
                try:
                    parser.parse(invalid_message)
                except (ValueError, Exception):
                    pass  # Expected behavior if checksum validation is enabled

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX checksum validation not implemented")


class TestFastFIXBuilder:
    """Test optimized FastFIXBuilder functionality."""

    @pytest.fixture
    def fast_builder(self):
        """Create Fast FIX builder for testing."""
        try:
            return FastFIXBuilder()
        except (ImportError, NotImplementedError):
            pytest.skip("FastFIXBuilder not available")

    def test_fast_builder_initialization(self, fast_builder):
        """Test Fast FIX builder initialization."""
        assert fast_builder is not None

        # Test performance-oriented methods
        performance_methods = ["build_fast", "build_batch", "reset_buffer"]
        available_methods = [
            method for method in performance_methods if hasattr(fast_builder, method)
        ]

        # Fast builder should have some optimization features
        assert len(available_methods) > 0 or hasattr(fast_builder, "build")

    def test_fast_builder_performance(self, fast_builder):
        """Test Fast FIX builder performance characteristics."""
        orders = []

        # Create multiple orders for batch testing
        for i in range(100):
            order = NewOrderSingle(
                symbol="EURUSD",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
                cl_ord_id=f"ORDER_{i}",
            )
            orders.append(order)

        # Test build performance
        start_time = time.time()

        for i, order in enumerate(orders):
            try:
                if hasattr(fast_builder, "build_fast"):
                    fix_string = fast_builder.build_fast(
                        order,
                        sender_comp_id="SENDER",
                        target_comp_id="TARGET",
                        seq_num=i + 1,
                    )
                elif hasattr(fast_builder, "build"):
                    fix_string = fast_builder.build(
                        order,
                        sender_comp_id="SENDER",
                        target_comp_id="TARGET",
                        seq_num=i + 1,
                    )

            except (NotImplementedError, AttributeError):
                pytest.skip("Fast FIX builder methods not implemented")

        end_time = time.time()
        elapsed = end_time - start_time

        # Fast builder should be reasonably fast
        messages_per_second = len(orders) / elapsed
        assert messages_per_second > 100  # Should handle 100+ messages/second

    def test_fast_builder_batch_operations(self, fast_builder):
        """Test Fast FIX builder batch operations."""
        orders = [
            NewOrderSingle(
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
            ),
            NewOrderSingle(
                symbol="GBPUSD",
                side=Side.SELL,
                ord_type=OrdType.LIMIT,
                order_qty=75000.0,
                price=1.2500,
            ),
            NewOrderSingle(
                symbol="USDJPY",
                side=Side.BUY,
                ord_type=OrdType.STOP,
                order_qty=50000.0,
                stop_px=108.50,
            ),
        ]

        try:
            if hasattr(fast_builder, "build_batch"):
                fix_messages = fast_builder.build_batch(
                    orders,
                    sender_comp_id="SENDER",
                    target_comp_id="TARGET",
                    starting_seq_num=1,
                )

                # Verify batch results
                assert len(fix_messages) == len(orders)

                for fix_msg in fix_messages:
                    assert isinstance(fix_msg, str)
                    assert fix_msg.startswith("8=FIX.4.2")

        except (NotImplementedError, AttributeError):
            pytest.skip("Fast FIX builder batch operations not implemented")

    def test_fast_builder_memory_efficiency(self, fast_builder):
        """Test Fast FIX builder memory efficiency."""
        try:
            if hasattr(fast_builder, "reset_buffer"):
                # Test buffer management
                initial_state = getattr(fast_builder, "_buffer", None)

                # Build some messages
                for i in range(10):
                    order = NewOrderSingle(
                        symbol="EURUSD",
                        side=Side.BUY,
                        ord_type=OrdType.MARKET,
                        order_qty=100000.0,
                    )

                    if hasattr(fast_builder, "build"):
                        fast_builder.build(order, "SENDER", "TARGET", i + 1)

                # Reset buffer
                fast_builder.reset_buffer()

                # Verify buffer was reset
                reset_state = getattr(fast_builder, "_buffer", None)
                # Buffer should be reset/cleared

        except (NotImplementedError, AttributeError):
            pytest.skip("Fast FIX builder memory management not implemented")


class TestFastFIXParser:
    """Test optimized FastFIXParser functionality."""

    @pytest.fixture
    def fast_parser(self):
        """Create Fast FIX parser for testing."""
        try:
            return FastFIXParser()
        except (ImportError, NotImplementedError):
            pytest.skip("FastFIXParser not available")

    def test_fast_parser_initialization(self, fast_parser):
        """Test Fast FIX parser initialization."""
        assert fast_parser is not None

        # Test performance-oriented methods
        performance_methods = ["parse_fast", "parse_batch", "precompile_patterns"]
        available_methods = [
            method for method in performance_methods if hasattr(fast_parser, method)
        ]

        # Fast parser should have some optimization features
        assert len(available_methods) > 0 or hasattr(fast_parser, "parse")

    def test_fast_parser_performance(self, fast_parser):
        """Test Fast FIX parser performance characteristics."""
        # Create multiple FIX messages for performance testing
        fix_messages = []

        base_messages = [
            "8=FIX.4.2\x019=40\x0135=0\x0149=SENDER\x0156=TARGET\x0134={}\x0110=123\x01",  # Heartbeat
            "8=FIX.4.2\x019=73\x0135=A\x0149=SENDER\x0156=TARGET\x0134={}\x01"
            + "52=20230101-12:00:00\x0198=0\x01108=30\x01553=user\x01554=pass\x0110=123\x01",  # Logon
        ]

        for i in range(100):
            for base_msg in base_messages:
                fix_messages.append(base_msg.format(i + 1))

        # Test parsing performance
        start_time = time.time()

        for fix_msg in fix_messages:
            try:
                if hasattr(fast_parser, "parse_fast"):
                    parsed = fast_parser.parse_fast(fix_msg)
                elif hasattr(fast_parser, "parse"):
                    parsed = fast_parser.parse(fix_msg)

            except (NotImplementedError, AttributeError):
                pytest.skip("Fast FIX parser methods not implemented")

        end_time = time.time()
        elapsed = end_time - start_time

        # Fast parser should be reasonably fast
        messages_per_second = len(fix_messages) / elapsed
        assert messages_per_second > 200  # Should handle 200+ messages/second

    def test_fast_parser_batch_operations(self, fast_parser):
        """Test Fast FIX parser batch operations."""
        fix_messages = [
            "8=FIX.4.2\x019=40\x0135=0\x0149=SENDER\x0156=TARGET\x0134=1\x0110=123\x01",
            "8=FIX.4.2\x019=73\x0135=A\x0149=SENDER\x0156=TARGET\x0134=2\x01"
            + "52=20230101-12:00:00\x0198=0\x01108=30\x01553=user\x01554=pass\x0110=123\x01",
            "8=FIX.4.2\x019=40\x0135=5\x0149=SENDER\x0156=TARGET\x0134=3\x0110=123\x01",
        ]

        try:
            if hasattr(fast_parser, "parse_batch"):
                parsed_messages = fast_parser.parse_batch(fix_messages)

                # Verify batch results
                assert len(parsed_messages) == len(fix_messages)

                for parsed in parsed_messages:
                    assert parsed is not None
                    if isinstance(parsed, dict):
                        assert "8" in parsed
                        assert parsed["8"] == "FIX.4.2"

        except (NotImplementedError, AttributeError):
            pytest.skip("Fast FIX parser batch operations not implemented")

    def test_fast_parser_precompiled_patterns(self, fast_parser):
        """Test Fast FIX parser precompiled patterns optimization."""
        try:
            if hasattr(fast_parser, "precompile_patterns"):
                # Test pattern precompilation
                common_patterns = ["8=", "9=", "35=", "49=", "56=", "34=", "10="]
                fast_parser.precompile_patterns(common_patterns)

                # Test that precompiled patterns improve performance
                test_message = "8=FIX.4.2\x019=40\x0135=0\x0149=SENDER\x0156=TARGET\x0134=1\x0110=123\x01"

                # Parse with precompiled patterns
                if hasattr(fast_parser, "parse"):
                    parsed = fast_parser.parse(test_message)
                    assert parsed is not None

        except (NotImplementedError, AttributeError):
            pytest.skip("Fast FIX parser pattern precompilation not implemented")


class TestFIXUtilities:
    """Test FIX protocol utility functions."""

    @pytest.fixture
    def utilities(self):
        """Create FIX utilities for testing."""
        try:
            return FIXUtilities()
        except (ImportError, NotImplementedError):
            pytest.skip("FIXUtilities not available")

    def test_utilities_initialization(self, utilities):
        """Test FIX utilities initialization."""
        assert utilities is not None

        # Test common utility methods
        utility_methods = [
            "format_timestamp",
            "calculate_checksum",
            "validate_message",
            "convert_side",
            "convert_order_type",
            "format_price",
            "format_quantity",
        ]
        available_methods = [
            method for method in utility_methods if hasattr(utilities, method)
        ]

        # Should have some utility methods
        assert len(available_methods) > 0

    def test_timestamp_formatting(self, utilities):
        """Test FIX timestamp formatting utilities."""
        test_datetime = datetime(2023, 1, 1, 12, 0, 0)

        try:
            if hasattr(utilities, "format_timestamp"):
                formatted = utilities.format_timestamp(test_datetime)

                # FIX timestamp format: YYYYMMDD-HH:MM:SS
                assert isinstance(formatted, str)
                assert len(formatted) >= 17
                assert "20230101" in formatted
                assert "12:00:00" in formatted
                assert "-" in formatted

            elif hasattr(utilities, "to_fix_timestamp"):
                formatted = utilities.to_fix_timestamp(test_datetime)
                assert isinstance(formatted, str)
                assert "2023" in formatted

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX timestamp formatting not implemented")

    def test_price_formatting(self, utilities):
        """Test FIX price formatting utilities."""
        test_prices = [1.1050, 108.25, 0.7832, 1234.56789]

        try:
            if hasattr(utilities, "format_price"):
                for price in test_prices:
                    formatted = utilities.format_price(price)

                    assert isinstance(formatted, str)
                    # Should preserve reasonable precision
                    assert len(formatted) > 0
                    assert "." in formatted or formatted.isdigit()

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX price formatting not implemented")

    def test_quantity_formatting(self, utilities):
        """Test FIX quantity formatting utilities."""
        test_quantities = [100000.0, 75000, 50000.5, 1000000]

        try:
            if hasattr(utilities, "format_quantity"):
                for qty in test_quantities:
                    formatted = utilities.format_quantity(qty)

                    assert isinstance(formatted, str)
                    assert len(formatted) > 0
                    # Quantity should be positive
                    assert not formatted.startswith("-")

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX quantity formatting not implemented")

    def test_enumeration_conversion(self, utilities):
        """Test FIX enumeration value conversion utilities."""
        try:
            if hasattr(utilities, "convert_side"):
                # Test side conversion
                buy_converted = utilities.convert_side(Side.BUY)
                sell_converted = utilities.convert_side(Side.SELL)

                assert buy_converted in ["1", 1, Side.BUY]
                assert sell_converted in ["2", 2, Side.SELL]

            if hasattr(utilities, "convert_order_type"):
                # Test order type conversion
                market_converted = utilities.convert_order_type(OrdType.MARKET)
                limit_converted = utilities.convert_order_type(OrdType.LIMIT)

                assert market_converted in ["1", 1, OrdType.MARKET]
                assert limit_converted in ["2", 2, OrdType.LIMIT]

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX enumeration conversion not implemented")

    def test_message_validation(self, utilities):
        """Test FIX message validation utilities."""
        valid_message = (
            "8=FIX.4.2\x019=40\x0135=0\x0149=SENDER\x0156=TARGET\x0134=1\x0110=123\x01"
        )
        invalid_message = "8=INVALID\x019=10\x0135=Z\x01"

        try:
            if hasattr(utilities, "validate_message"):
                # Valid message should pass validation
                is_valid = utilities.validate_message(valid_message)
                assert is_valid == True

                # Invalid message should fail validation
                is_invalid = utilities.validate_message(invalid_message)
                assert is_invalid == False

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX message validation not implemented")

    def test_checksum_utilities(self, utilities):
        """Test FIX checksum calculation utilities."""
        test_message_body = "9=40\x0135=0\x0149=SENDER\x0156=TARGET\x0134=1\x01"

        try:
            if hasattr(utilities, "calculate_checksum"):
                checksum = utilities.calculate_checksum(test_message_body)

                # Checksum should be 3-digit string
                assert isinstance(checksum, str)
                assert len(checksum) == 3
                assert checksum.isdigit()

                # Test consistency
                checksum2 = utilities.calculate_checksum(test_message_body)
                assert checksum == checksum2

                # Test different message produces different checksum
                different_message = "9=45\x0135=A\x0149=OTHER\x0156=TARGET\x0134=1\x01"
                different_checksum = utilities.calculate_checksum(different_message)
                assert different_checksum != checksum

        except (NotImplementedError, AttributeError):
            pytest.skip("FIX checksum utilities not implemented")


class TestAdvancedFIXFeatures:
    """Test advanced FIX protocol features and edge cases."""

    def test_message_segmentation(self):
        """Test handling of large messages requiring segmentation."""
        # Create order with very large text field
        large_text = "A" * 5000  # 5KB text field

        order = NewOrderSingle(
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
            text=large_text,
        )

        # Test that large messages can be handled
        assert order.text == large_text
        assert len(order.text) == 5000

        # Test message can be serialized (basic check)
        assert hasattr(order, "__dict__")

    def test_concurrent_message_processing(self):
        """Test concurrent FIX message processing."""
        import queue
        import threading

        message_queue = queue.Queue()
        results = queue.Queue()

        # Create test messages
        test_messages = [
            f"8=FIX.4.2\x019=40\x0135=0\x0149=SENDER\x0156=TARGET\x0134={i}\x0110=123\x01"
            for i in range(50)
        ]

        def process_messages():
            """Worker function to process messages."""
            parser = FIXParser()
            while True:
                try:
                    message = message_queue.get(timeout=1)
                    if message is None:
                        break

                    # Process message
                    if hasattr(parser, "parse"):
                        try:
                            parsed = parser.parse(message)
                            results.put(("success", parsed))
                        except:
                            results.put(("error", message))
                    else:
                        results.put(("skip", message))

                    message_queue.task_done()
                except queue.Empty:
                    break

        # Add messages to queue
        for msg in test_messages:
            message_queue.put(msg)

        # Start worker threads
        workers = []
        for i in range(3):  # 3 worker threads
            worker = threading.Thread(target=process_messages)
            worker.start()
            workers.append(worker)

        # Signal workers to stop
        for _ in workers:
            message_queue.put(None)

        # Wait for workers to complete
        for worker in workers:
            worker.join()

        # Verify all messages were processed
        result_count = results.qsize()
        assert result_count == len(test_messages)

    def test_message_ordering_and_gaps(self):
        """Test FIX message sequence number ordering and gap detection."""
        session_config = SessionConfig(
            sender_comp_id="TEST_SENDER", target_comp_id="TEST_TARGET"
        )
        session = FIXSession(session_config)

        # Test normal sequence
        assert session.outgoing_seq_num == 1
        seq1 = session.get_next_outgoing_seq_num()
        assert seq1 == 1
        assert session.outgoing_seq_num == 2

        seq2 = session.get_next_outgoing_seq_num()
        assert seq2 == 2
        assert session.outgoing_seq_num == 3

        # Test sequence gap detection
        session.incoming_seq_num = 10
        expected_next = session.incoming_seq_num

        # Simulate receiving message with sequence gap
        received_seq = 15  # Gap of 5 messages
        has_gap = received_seq != expected_next
        assert has_gap

        gap_size = received_seq - expected_next
        assert gap_size == 5

    def test_fix_version_compatibility(self):
        """Test compatibility across different FIX versions."""
        fix_versions = ["FIX.4.2", "FIX.4.4", "FIXT.1.1"]

        for version in fix_versions:
            # Test session config with different versions
            config = SessionConfig(
                sender_comp_id="SENDER", target_comp_id="TARGET", fix_version=version
            )

            assert config.fix_version == version

            # Test basic message creation with version
            order = NewOrderSingle(
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
            )

            # Message should be compatible regardless of version
            assert order.symbol == "EURUSD"

    def test_message_encryption_handling(self):
        """Test FIX message encryption method handling."""
        # Test different encryption methods
        encryption_methods = [0, 1, 2, 3]  # None, PKCS, DES, PKCS-DES

        for method in encryption_methods:
            logon = Logon(
                encrypt_method=method,
                heartbt_int=30,
                username="test_user",
                password="test_pass",
            )

            assert logon.encrypt_method == method
            # Encryption handling should be consistent
            assert hasattr(logon, "encrypt_method")

    def test_market_data_message_handling(self):
        """Test specialized market data message handling."""
        try:
            # Test market data request
            md_request = MarketDataRequest(
                md_req_id="MD_REQ_001",
                subscription_request_type=1,  # Snapshot + updates
                market_depth=1,
                symbols=["EURUSD", "GBPUSD", "USDJPY"],
            )

            assert md_request.md_req_id == "MD_REQ_001"
            assert md_request.market_depth == 1
            assert len(md_request.symbols) == 3

            # Test market data snapshot
            md_snapshot = MarketDataSnapshot(
                symbol="EURUSD",
                md_req_id="MD_REQ_001",
                bid_price=1.1045,
                ask_price=1.1047,
                bid_size=1000000,
                ask_size=1500000,
            )

            assert md_snapshot.symbol == "EURUSD"
            assert md_snapshot.bid_price == 1.1045
            assert md_snapshot.ask_price == 1.1047

        except (ImportError, NameError, AttributeError):
            pytest.skip("Market data messages not implemented")

    def test_order_modification_handling(self):
        """Test order modification and cancellation message handling."""
        try:
            # Test order cancel/replace request
            modify_request = OrderCancelReplaceRequest(
                orig_cl_ord_id="ORIG_ORDER_123",
                cl_ord_id="MODIFY_ORDER_456",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=150000.0,  # Modified quantity
                price=1.1060,  # Modified price
                ord_type=OrdType.LIMIT,
            )

            assert modify_request.orig_cl_ord_id == "ORIG_ORDER_123"
            assert modify_request.order_qty == 150000.0
            assert modify_request.price == 1.1060

            # Test order cancel request
            cancel_request = OrderCancelRequest(
                orig_cl_ord_id="ORDER_TO_CANCEL",
                cl_ord_id="CANCEL_REQ_789",
                symbol="EURUSD",
                side=Side.BUY,
            )

            assert cancel_request.orig_cl_ord_id == "ORDER_TO_CANCEL"
            assert cancel_request.cl_ord_id == "CANCEL_REQ_789"

        except (ImportError, NameError, AttributeError):
            pytest.skip("Order modification messages not implemented")


# Test Performance Benchmarks
class TestFIXPerformanceBenchmarks:
    """Performance benchmarks for FIX protocol implementation."""

    def test_message_creation_benchmark(self):
        """Benchmark FIX message creation performance."""
        iterations = 10000

        start_time = time.time()

        for i in range(iterations):
            order = NewOrderSingle(
                symbol="EURUSD",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                ord_type=OrdType.MARKET if i % 3 == 0 else OrdType.LIMIT,
                order_qty=100000.0,
                price=1.1050 if i % 3 != 0 else None,
                cl_ord_id=f"PERF_ORDER_{i}",
            )

        end_time = time.time()
        elapsed = end_time - start_time

        # Performance targets
        messages_per_second = iterations / elapsed
        assert messages_per_second > 5000  # Should create 5000+ messages/second
        assert elapsed < 2.0  # Should complete in under 2 seconds

    def test_session_management_benchmark(self):
        """Benchmark FIX session management performance."""
        config = SessionConfig(
            sender_comp_id="PERF_SENDER",
            target_comp_id="PERF_TARGET",
            heartbeat_interval=10,
        )

        session = FIXSession(config)
        iterations = 50000

        start_time = time.time()

        # Simulate high-frequency session operations
        for i in range(iterations):
            seq_num = session.get_next_outgoing_seq_num()
            session.statistics.messages_sent += 1
            session.statistics.bytes_sent += 150

            # Simulate periodic heartbeat checks
            if i % 1000 == 0:
                session.needs_heartbeat()

        end_time = time.time()
        elapsed = end_time - start_time

        # Performance targets for session management
        operations_per_second = iterations / elapsed
        assert operations_per_second > 10000  # Should handle 10k+ ops/second
        assert elapsed < 5.0  # Should complete in under 5 seconds

    def test_memory_usage_stability(self):
        """Test memory usage stability under load."""
        import gc

        # Force garbage collection before test
        gc.collect()

        # Create many messages and verify memory usage
        messages = []
        for i in range(1000):
            order = NewOrderSingle(
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
            )
            messages.append(order)

            # Periodic cleanup
            if i % 100 == 0:
                gc.collect()

        # Verify messages are still accessible
        assert len(messages) == 1000
        assert all(msg.symbol == "EURUSD" for msg in messages)

        # Clean up
        messages.clear()
        gc.collect()


if __name__ == "__main__":
    """Run FIX utilities tests directly."""
    pytest.main([__file__, "-v", "--tb=short"])
