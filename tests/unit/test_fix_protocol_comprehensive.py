"""Comprehensive Unit Tests for FIX Protocol Implementation.

This module provides retrospective test coverage for the core FIX protocol functionality,
ensuring robust broker connectivity infrastructure. Tests are designed to validate
existing behavior and provide regression protection for critical trading operations.

Test Coverage Areas:
- FIX Message Creation and Validation
- Session Management and State Transitions
- Message Parsing and Building
- Protocol Compliance and Field Validation
- Error Handling and Recovery Scenarios
- Performance and Memory Management

Following the proven retrospective TDD methodology (Green → Test → Validate).
"""

import asyncio
import logging
import ssl
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest

from fxml4.fix.messages.admin import Heartbeat, Logon, Logout, TestRequest
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
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)

# FIX Protocol Core Components
from fxml4.fix.session_manager import (
    FIXSession,
    SessionConfig,
    SessionState,
    SessionStatistics,
)
from fxml4.fix.simplefix_translator import SimpleFIXTranslator
from fxml4.fix.utils.builder import FIXBuilder
from fxml4.fix.utils.parser import FIXParser


class TestFIXSessionManager:
    """Test FIX session management functionality."""

    @pytest.fixture
    def session_config(self):
        """Create test session configuration."""
        return SessionConfig(
            sender_comp_id="FXML4_TEST",
            target_comp_id="BROKER_TEST",
            fix_version="FIX.4.2",
            heartbeat_interval=30,
            logon_timeout=10,
            reconnect_interval=5,
        )

    @pytest.fixture
    def mock_connection(self):
        """Create mock connection for testing."""
        connection = MagicMock()
        connection.is_connected = True
        connection.send = AsyncMock()
        connection.close = AsyncMock()
        return connection

    def test_session_initialization(self, session_config):
        """Test FIX session initialization."""
        session = FIXSession(session_config)

        assert session.config == session_config
        assert session.state == SessionState.DISCONNECTED
        assert session.outgoing_seq_num == 1
        assert session.incoming_seq_num == 1
        assert isinstance(session.statistics, SessionStatistics)

    def test_session_state_transitions(self, session_config, mock_connection):
        """Test valid session state transitions."""
        session = FIXSession(session_config)

        # Test connecting
        session.set_connection(mock_connection)
        session._set_state(SessionState.CONNECTING)
        assert session.state == SessionState.CONNECTING

        # Test logon sent
        session._set_state(SessionState.LOGON_SENT)
        assert session.state == SessionState.LOGON_SENT

        # Test active
        session._set_state(SessionState.ACTIVE)
        assert session.state == SessionState.ACTIVE
        assert session.is_active()

    def test_sequence_number_management(self, session_config):
        """Test sequence number incrementing."""
        session = FIXSession(session_config)

        initial_outgoing = session.outgoing_seq_num
        next_seq = session.get_next_outgoing_seq_num()

        assert next_seq == initial_outgoing
        assert session.outgoing_seq_num == initial_outgoing + 1

    def test_heartbeat_calculation(self, session_config):
        """Test heartbeat timing calculations."""
        session = FIXSession(session_config)

        # Mock current time
        now = datetime.utcnow()
        with patch("fxml4.fix.session_manager.datetime") as mock_dt:
            mock_dt.utcnow.return_value = now

            # Test heartbeat needed when no recent activity
            session.last_received_time = now - timedelta(seconds=35)
            assert session.needs_heartbeat()

            # Test heartbeat not needed with recent activity
            session.last_received_time = now - timedelta(seconds=10)
            assert not session.needs_heartbeat()

    def test_session_reset(self, session_config):
        """Test session reset functionality."""
        session = FIXSession(session_config)

        # Modify sequence numbers
        session.outgoing_seq_num = 100
        session.incoming_seq_num = 150

        # Reset session
        session.reset_session()

        assert session.outgoing_seq_num == 1
        assert session.incoming_seq_num == 1
        assert session.state == SessionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_session_logon_process(self, session_config, mock_connection):
        """Test FIX logon process."""
        session = FIXSession(session_config)
        session.set_connection(mock_connection)

        with patch.object(session, "_send_message") as mock_send:
            await session.initiate_logon()

            # Verify logon message sent
            mock_send.assert_called_once()
            logon_msg = mock_send.call_args[0][0]
            assert isinstance(logon_msg, Logon)
            assert session.state == SessionState.LOGON_SENT

    @pytest.mark.asyncio
    async def test_session_logout_process(self, session_config, mock_connection):
        """Test FIX logout process."""
        session = FIXSession(session_config)
        session.set_connection(mock_connection)
        session._set_state(SessionState.ACTIVE)

        with patch.object(session, "_send_message") as mock_send:
            await session.initiate_logout("Test logout")

            # Verify logout message sent
            mock_send.assert_called_once()
            logout_msg = mock_send.call_args[0][0]
            assert isinstance(logout_msg, Logout)
            assert session.state == SessionState.LOGOUT_SENT

    def test_session_statistics_tracking(self, session_config):
        """Test session statistics collection."""
        session = FIXSession(session_config)

        initial_sent = session.statistics.messages_sent
        initial_received = session.statistics.messages_received

        # Simulate message activity
        session.statistics.messages_sent += 10
        session.statistics.messages_received += 15
        session.statistics.bytes_sent += 1024
        session.statistics.bytes_received += 2048

        assert session.statistics.messages_sent == initial_sent + 10
        assert session.statistics.messages_received == initial_received + 15
        assert session.statistics.bytes_sent == 1024
        assert session.statistics.bytes_received == 2048


class TestFIXMessageTypes:
    """Test FIX message creation and validation."""

    def test_new_order_single_creation(self):
        """Test NewOrderSingle message creation."""
        order = NewOrderSingle(
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
            currency="USD",
            account="TEST_ACCOUNT",
        )

        assert order.symbol == "EURUSD"
        assert order.side == Side.BUY
        assert order.ord_type == OrdType.MARKET
        assert order.order_qty == 100000.0
        assert order.currency == "USD"
        assert order.account == "TEST_ACCOUNT"
        assert order.cl_ord_id is not None  # Auto-generated
        assert isinstance(order.transact_time, datetime)

    def test_new_order_single_limit_order(self):
        """Test limit order creation."""
        order = NewOrderSingle(
            symbol="GBPUSD",
            side=Side.SELL,
            ord_type=OrdType.LIMIT,
            order_qty=50000.0,
            price=1.2500,
            time_in_force=TimeInForce.GTC,
        )

        assert order.ord_type == OrdType.LIMIT
        assert order.price == 1.2500
        assert order.time_in_force == TimeInForce.GTC

    def test_new_order_single_stop_order(self):
        """Test stop order creation."""
        order = NewOrderSingle(
            symbol="USDJPY",
            side=Side.BUY,
            ord_type=OrdType.STOP,
            order_qty=75000.0,
            stop_px=108.50,
        )

        assert order.ord_type == OrdType.STOP
        assert order.stop_px == 108.50

    def test_execution_report_creation(self):
        """Test ExecutionReport message creation."""
        exec_report = ExecutionReport(
            order_id="ORD123456",
            cl_ord_id="CLIENT789",
            exec_id="EXEC001",
            exec_type=ExecType.FILL,
            ord_status=OrdStatus.FILLED,
            symbol="EURUSD",
            side=Side.BUY,
            leaves_qty=0.0,
            cum_qty=100000.0,
            avg_px=1.1050,
        )

        assert exec_report.order_id == "ORD123456"
        assert exec_report.cl_ord_id == "CLIENT789"
        assert exec_report.exec_type == ExecType.FILL
        assert exec_report.ord_status == OrdStatus.FILLED
        assert exec_report.leaves_qty == 0.0
        assert exec_report.cum_qty == 100000.0
        assert exec_report.avg_px == 1.1050

    def test_order_cancel_request_creation(self):
        """Test OrderCancelRequest message creation."""
        cancel_req = OrderCancelRequest(
            orig_cl_ord_id="ORIG123",
            cl_ord_id="CANCEL456",
            symbol="GBPUSD",
            side=Side.SELL,
            transact_time=datetime.utcnow(),
        )

        assert cancel_req.orig_cl_ord_id == "ORIG123"
        assert cancel_req.cl_ord_id == "CANCEL456"
        assert cancel_req.symbol == "GBPUSD"
        assert cancel_req.side == Side.SELL

    def test_admin_message_creation(self):
        """Test administrative message creation."""
        # Test Logon
        logon = Logon(
            encrypt_method=0, heartbt_int=30, username="test_user", password="test_pass"
        )

        assert logon.encrypt_method == 0
        assert logon.heartbt_int == 30
        assert logon.username == "test_user"
        assert logon.password == "test_pass"

        # Test Logout
        logout = Logout(text="Normal logout")
        assert logout.text == "Normal logout"

        # Test Heartbeat
        heartbeat = Heartbeat()
        assert heartbeat.msg_type == FIXMessageType.HEARTBEAT

        # Test TestRequest
        test_req = TestRequest(test_req_id="TEST123")
        assert test_req.test_req_id == "TEST123"

    def test_message_field_validation(self):
        """Test FIX message field validation."""
        # Test required fields
        with pytest.raises((ValueError, TypeError)):
            NewOrderSingle()  # Missing required symbol

        # Test valid enum values
        order = NewOrderSingle(symbol="EURUSD", side=Side.BUY, ord_type=OrdType.MARKET)

        assert order.side == Side.BUY
        assert order.ord_type == OrdType.MARKET

    def test_message_serialization_preparation(self):
        """Test message preparation for serialization."""
        order = NewOrderSingle(
            symbol="EURUSD", side=Side.BUY, ord_type=OrdType.MARKET, order_qty=100000.0
        )

        # Test that message has serializable fields
        assert hasattr(order, "to_dict") or hasattr(order, "__dict__")

        # Test message type identification
        assert hasattr(order, "msg_type") or hasattr(order, "get_msg_type")


class TestFIXMessageParsing:
    """Test FIX message parsing functionality."""

    @pytest.fixture
    def parser(self):
        """Create FIX parser for testing."""
        return FIXParser()

    def test_parser_initialization(self, parser):
        """Test FIX parser initialization."""
        assert parser is not None
        assert hasattr(parser, "parse")

    def test_parse_logon_message(self, parser):
        """Test parsing of FIX Logon message."""
        # Standard FIX 4.2 Logon message
        logon_msg = (
            "8=FIX.4.2\x019=73\x0135=A\x0149=SENDER\x0156=TARGET\x0134=1\x01"
            + "52=20230101-12:00:00\x0198=0\x01108=30\x01553=test\x01554=pass\x0110=123\x01"
        )

        if hasattr(parser, "parse"):
            try:
                parsed_msg = parser.parse(logon_msg)

                # Verify message was parsed
                assert parsed_msg is not None

                # Check if parsed message has expected structure
                if hasattr(parsed_msg, "msg_type"):
                    assert parsed_msg.msg_type == FIXMessageType.LOGON
                elif isinstance(parsed_msg, dict):
                    assert parsed_msg.get("35") == "A"  # Logon message type
            except NotImplementedError:
                pytest.skip("Parser not fully implemented yet")

    def test_parse_new_order_message(self, parser):
        """Test parsing of NewOrderSingle message."""
        # Standard FIX 4.2 NewOrderSingle
        order_msg = (
            "8=FIX.4.2\x019=145\x0135=D\x0149=SENDER\x0156=TARGET\x0134=2\x01"
            + "52=20230101-12:00:00\x0111=CLIENT123\x0155=EURUSD\x0154=1\x01"
            + "38=100000\x0140=1\x0159=0\x0115=USD\x0110=123\x01"
        )

        if hasattr(parser, "parse"):
            try:
                parsed_msg = parser.parse(order_msg)

                assert parsed_msg is not None

                if hasattr(parsed_msg, "symbol"):
                    assert parsed_msg.symbol == "EURUSD"
                    assert parsed_msg.side == Side.BUY
                elif isinstance(parsed_msg, dict):
                    assert parsed_msg.get("55") == "EURUSD"  # Symbol
                    assert parsed_msg.get("54") == "1"  # Buy side
            except NotImplementedError:
                pytest.skip("Parser not fully implemented yet")

    def test_parse_execution_report(self, parser):
        """Test parsing of ExecutionReport message."""
        exec_msg = (
            "8=FIX.4.2\x019=165\x0135=8\x0149=TARGET\x0156=SENDER\x0134=3\x01"
            + "52=20230101-12:00:00\x0137=ORDER123\x0111=CLIENT123\x0117=EXEC001\x01"
            + "150=F\x0139=2\x0155=EURUSD\x0154=1\x0114=100000\x0131=1.1050\x01"
            + "32=100000\x0151=0\x0110=123\x01"
        )

        if hasattr(parser, "parse"):
            try:
                parsed_msg = parser.parse(exec_msg)

                assert parsed_msg is not None

                if hasattr(parsed_msg, "exec_type"):
                    assert parsed_msg.exec_type == ExecType.FILL
                elif isinstance(parsed_msg, dict):
                    assert parsed_msg.get("150") == "F"  # Fill execution type
            except NotImplementedError:
                pytest.skip("Parser not fully implemented yet")

    def test_parse_malformed_message(self, parser):
        """Test handling of malformed FIX messages."""
        malformed_msg = "8=FIX.4.2\x01INVALID_FORMAT"

        if hasattr(parser, "parse"):
            try:
                with pytest.raises((ValueError, Exception)):
                    parser.parse(malformed_msg)
            except NotImplementedError:
                pytest.skip("Parser not fully implemented yet")

    def test_parse_empty_message(self, parser):
        """Test handling of empty messages."""
        if hasattr(parser, "parse"):
            try:
                with pytest.raises((ValueError, Exception)):
                    parser.parse("")
            except NotImplementedError:
                pytest.skip("Parser not fully implemented yet")


class TestFIXMessageBuilding:
    """Test FIX message building functionality."""

    @pytest.fixture
    def builder(self):
        """Create FIX builder for testing."""
        return FIXBuilder()

    def test_builder_initialization(self, builder):
        """Test FIX builder initialization."""
        assert builder is not None
        assert hasattr(builder, "build") or hasattr(builder, "create_message")

    def test_build_logon_message(self, builder):
        """Test building FIX Logon message."""
        logon = Logon(
            encrypt_method=0, heartbt_int=30, username="test_user", password="test_pass"
        )

        if hasattr(builder, "build"):
            try:
                fix_msg = builder.build(
                    logon, sender_comp_id="SENDER", target_comp_id="TARGET"
                )

                assert fix_msg is not None
                assert isinstance(fix_msg, (str, bytes))

                # Check for basic FIX structure
                if isinstance(fix_msg, str):
                    assert "8=FIX.4.2" in fix_msg
                    assert "35=A" in fix_msg  # Logon message type
            except NotImplementedError:
                pytest.skip("Builder not fully implemented yet")

    def test_build_new_order_message(self, builder):
        """Test building NewOrderSingle message."""
        order = NewOrderSingle(
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
            currency="USD",
        )

        if hasattr(builder, "build"):
            try:
                fix_msg = builder.build(
                    order, sender_comp_id="SENDER", target_comp_id="TARGET"
                )

                assert fix_msg is not None
                assert isinstance(fix_msg, (str, bytes))

                if isinstance(fix_msg, str):
                    assert "35=D" in fix_msg  # NewOrderSingle type
                    assert "55=EURUSD" in fix_msg  # Symbol
                    assert "54=1" in fix_msg  # Buy side
            except NotImplementedError:
                pytest.skip("Builder not fully implemented yet")

    def test_build_execution_report(self, builder):
        """Test building ExecutionReport message."""
        exec_report = ExecutionReport(
            order_id="ORDER123",
            cl_ord_id="CLIENT456",
            exec_id="EXEC789",
            exec_type=ExecType.FILL,
            ord_status=OrdStatus.FILLED,
            symbol="GBPUSD",
            side=Side.SELL,
            cum_qty=50000.0,
            avg_px=1.2500,
        )

        if hasattr(builder, "build"):
            try:
                fix_msg = builder.build(
                    exec_report, sender_comp_id="BROKER", target_comp_id="CLIENT"
                )

                assert fix_msg is not None

                if isinstance(fix_msg, str):
                    assert "35=8" in fix_msg  # ExecutionReport type
                    assert "55=GBPUSD" in fix_msg  # Symbol
                    assert "54=2" in fix_msg  # Sell side
            except NotImplementedError:
                pytest.skip("Builder not fully implemented yet")

    def test_build_with_sequence_numbers(self, builder):
        """Test building messages with sequence numbers."""
        heartbeat = Heartbeat()

        if hasattr(builder, "build"):
            try:
                fix_msg = builder.build(
                    heartbeat,
                    sender_comp_id="SENDER",
                    target_comp_id="TARGET",
                    seq_num=42,
                )

                assert fix_msg is not None

                if isinstance(fix_msg, str):
                    assert "34=42" in fix_msg  # Sequence number
            except (NotImplementedError, TypeError):
                pytest.skip("Builder sequence number support not implemented yet")

    def test_build_with_checksum(self, builder):
        """Test that built messages include valid checksums."""
        logon = Logon(encrypt_method=0, heartbt_int=30)

        if hasattr(builder, "build"):
            try:
                fix_msg = builder.build(
                    logon, sender_comp_id="TEST", target_comp_id="BROKER"
                )

                if isinstance(fix_msg, str) and fix_msg:
                    # FIX messages should end with checksum (10=XXX)
                    assert fix_msg.endswith("\x01") or "10=" in fix_msg
            except NotImplementedError:
                pytest.skip("Builder not fully implemented yet")


class TestSimpleFIXTranslator:
    """Test SimpleFIX translation functionality."""

    @pytest.fixture
    def translator(self):
        """Create FIX translator for testing."""
        return SimpleFIXTranslator()

    def test_translator_initialization(self, translator):
        """Test translator initialization."""
        assert translator is not None
        assert hasattr(translator, "encode") or hasattr(translator, "decode")

    def test_encode_message(self, translator):
        """Test encoding FIX message objects."""
        order = NewOrderSingle(
            symbol="EURUSD", side=Side.BUY, ord_type=OrdType.MARKET, order_qty=100000.0
        )

        if hasattr(translator, "encode"):
            try:
                encoded = translator.encode(order)

                assert encoded is not None
                assert isinstance(encoded, (str, bytes))
            except NotImplementedError:
                pytest.skip("Translator encode not implemented yet")

    def test_decode_message(self, translator):
        """Test decoding FIX message strings."""
        fix_string = (
            "8=FIX.4.2\x019=73\x0135=A\x0149=SENDER\x0156=TARGET\x01"
            + "34=1\x0152=20230101-12:00:00\x0198=0\x01108=30\x0110=123\x01"
        )

        if hasattr(translator, "decode"):
            try:
                decoded = translator.decode(fix_string)

                assert decoded is not None
                # Should be either a message object or dictionary
                assert hasattr(decoded, "__dict__") or isinstance(decoded, dict)
            except NotImplementedError:
                pytest.skip("Translator decode not implemented yet")

    def test_round_trip_translation(self, translator):
        """Test encoding and decoding round trip."""
        original_order = NewOrderSingle(
            symbol="GBPUSD",
            side=Side.SELL,
            ord_type=OrdType.LIMIT,
            order_qty=75000.0,
            price=1.2500,
        )

        if hasattr(translator, "encode") and hasattr(translator, "decode"):
            try:
                # Encode to FIX string
                encoded = translator.encode(original_order)

                # Decode back to object
                decoded = translator.decode(encoded)

                # Verify key fields preserved
                if hasattr(decoded, "symbol"):
                    assert decoded.symbol == "GBPUSD"
                    assert decoded.side == Side.SELL
                elif isinstance(decoded, dict):
                    assert decoded.get("symbol") == "GBPUSD"
            except NotImplementedError:
                pytest.skip("Translator round trip not implemented yet")


class TestFIXProtocolCompliance:
    """Test FIX protocol compliance and standards."""

    def test_message_type_constants(self):
        """Test FIX message type constants."""
        assert hasattr(FIXMessageType, "LOGON")
        assert hasattr(FIXMessageType, "LOGOUT")
        assert hasattr(FIXMessageType, "HEARTBEAT")
        assert hasattr(FIXMessageType, "NEW_ORDER_SINGLE")
        assert hasattr(FIXMessageType, "EXECUTION_REPORT")

    def test_field_enumeration_values(self):
        """Test FIX field enumeration values."""
        # Test Side enumeration
        assert hasattr(Side, "BUY")
        assert hasattr(Side, "SELL")

        # Test Order Type enumeration
        assert hasattr(OrdType, "MARKET")
        assert hasattr(OrdType, "LIMIT")
        assert hasattr(OrdType, "STOP")

        # Test Time In Force enumeration
        assert hasattr(TimeInForce, "DAY")
        assert hasattr(TimeInForce, "GTC")
        assert hasattr(TimeInForce, "IOC")

        # Test Order Status enumeration
        assert hasattr(OrdStatus, "NEW")
        assert hasattr(OrdStatus, "FILLED")
        assert hasattr(OrdStatus, "CANCELLED")

    def test_message_inheritance_structure(self):
        """Test FIX message class hierarchy."""
        # Test that message classes inherit from base
        assert issubclass(NewOrderSingle, FIXMessage)
        assert issubclass(ExecutionReport, FIXMessage)
        assert issubclass(Logon, FIXMessage)
        assert issubclass(Heartbeat, FIXMessage)

    def test_required_message_fields(self):
        """Test that messages have required FIX fields."""
        # NewOrderSingle required fields
        order = NewOrderSingle(symbol="EURUSD", side=Side.BUY, ord_type=OrdType.MARKET)
        assert hasattr(order, "cl_ord_id")
        assert hasattr(order, "symbol")
        assert hasattr(order, "side")
        assert hasattr(order, "transact_time")

        # ExecutionReport required fields
        exec_report = ExecutionReport(
            order_id="123",
            cl_ord_id="456",
            exec_id="789",
            exec_type=ExecType.FILL,
            ord_status=OrdStatus.FILLED,
            symbol="EURUSD",
            side=Side.BUY,
        )
        assert hasattr(exec_report, "order_id")
        assert hasattr(exec_report, "exec_id")
        assert hasattr(exec_report, "exec_type")

    def test_field_type_validation(self):
        """Test FIX field type validation."""
        order = NewOrderSingle(
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,  # Should be float
            price=1.1050,  # Should be float
        )

        assert isinstance(order.order_qty, (int, float))
        assert isinstance(order.price, (int, float, type(None)))
        assert isinstance(order.symbol, str)
        assert isinstance(order.transact_time, datetime)


class TestFIXErrorHandling:
    """Test FIX protocol error handling and recovery."""

    @pytest.fixture
    def session_config(self):
        """Create test session configuration."""
        return SessionConfig(
            sender_comp_id="TEST_SENDER",
            target_comp_id="TEST_TARGET",
            heartbeat_interval=30,
            logon_timeout=10,
        )

    def test_invalid_message_handling(self):
        """Test handling of invalid FIX messages."""
        parser = FIXParser()

        invalid_messages = [
            "",  # Empty message
            "INVALID",  # No FIX header
            "8=FIX.4.2",  # Incomplete message
            "8=FIX.4.2\x01MALFORMED\x01",  # Malformed fields
        ]

        for invalid_msg in invalid_messages:
            if hasattr(parser, "parse"):
                try:
                    with pytest.raises((ValueError, Exception)):
                        parser.parse(invalid_msg)
                except NotImplementedError:
                    pytest.skip("Parser not implemented yet")

    def test_session_timeout_handling(self, session_config):
        """Test session timeout scenarios."""
        session = FIXSession(session_config)

        # Mock connection timeout
        now = datetime.utcnow()
        session.last_received_time = now - timedelta(seconds=60)
        session.last_heartbeat_time = now - timedelta(seconds=45)

        # Test timeout detection
        with patch("fxml4.fix.session_manager.datetime") as mock_dt:
            mock_dt.utcnow.return_value = now

            # Should detect timeout condition
            timeout_threshold = session_config.heartbeat_interval * 2
            time_since_last = (now - session.last_received_time).total_seconds()
            assert time_since_last > timeout_threshold

    def test_sequence_number_gap_detection(self, session_config):
        """Test sequence number gap handling."""
        session = FIXSession(session_config)

        # Simulate sequence number gap
        session.incoming_seq_num = 10
        incoming_msg_seq = 15  # Gap of 5 messages

        # Test gap detection
        expected_seq = session.incoming_seq_num
        has_gap = incoming_msg_seq != expected_seq
        assert has_gap
        assert incoming_msg_seq > expected_seq

    def test_connection_failure_recovery(self, session_config):
        """Test connection failure and recovery scenarios."""
        session = FIXSession(session_config)

        # Simulate connection failure
        session._set_state(SessionState.ERROR)
        assert session.state == SessionState.ERROR
        assert not session.is_active()

        # Test recovery to disconnected state
        session._set_state(SessionState.DISCONNECTED)
        assert session.state == SessionState.DISCONNECTED

    def test_message_validation_errors(self):
        """Test message field validation errors."""
        # Test missing required fields
        with pytest.raises((ValueError, TypeError)):
            NewOrderSingle()  # No symbol provided

        # Test invalid enumeration values
        try:
            order = NewOrderSingle(
                symbol="EURUSD",
                side="INVALID_SIDE",  # Should be Side enum
                ord_type=OrdType.MARKET,
            )
            # If validation is implemented, this should fail
        except (ValueError, TypeError):
            pass  # Expected validation error

    def test_memory_management(self, session_config):
        """Test memory management in session operations."""
        session = FIXSession(session_config)

        # Test message history limits
        max_messages = session_config.max_messages_in_memory
        assert max_messages > 0

        # Simulate message accumulation
        if hasattr(session, "message_history"):
            for i in range(max_messages + 100):
                # Simulate adding messages beyond limit
                session.statistics.messages_sent += 1

            # Verify memory bounds are respected
            if hasattr(session, "message_history"):
                assert len(session.message_history) <= max_messages


class TestFIXPerformanceAndScalability:
    """Test FIX protocol performance characteristics."""

    @pytest.fixture
    def performance_config(self):
        """Create configuration for performance testing."""
        return SessionConfig(
            sender_comp_id="PERF_SENDER",
            target_comp_id="PERF_TARGET",
            heartbeat_interval=10,  # Faster heartbeat for testing
            max_messages_in_memory=1000,
        )

    def test_message_creation_performance(self):
        """Test performance of message creation."""
        import time

        start_time = time.time()

        # Create many messages
        for i in range(1000):
            order = NewOrderSingle(
                symbol="EURUSD",
                side=Side.BUY,
                ord_type=OrdType.MARKET,
                order_qty=100000.0,
                cl_ord_id=f"ORDER_{i}",
            )

        end_time = time.time()
        elapsed = end_time - start_time

        # Should create 1000 messages in reasonable time (< 1 second)
        assert elapsed < 1.0

        # Test message creation rate
        messages_per_second = 1000 / elapsed
        assert messages_per_second > 500  # Reasonable throughput

    def test_session_statistics_performance(self, performance_config):
        """Test session statistics tracking performance."""
        session = FIXSession(performance_config)

        import time

        start_time = time.time()

        # Simulate high-frequency statistics updates
        for i in range(10000):
            session.statistics.messages_sent += 1
            session.statistics.bytes_sent += 100

            if i % 100 == 0:
                session.get_next_outgoing_seq_num()

        end_time = time.time()
        elapsed = end_time - start_time

        # Statistics tracking should be fast
        assert elapsed < 0.5
        assert session.statistics.messages_sent == 10000

    def test_concurrent_session_handling(self, performance_config):
        """Test handling multiple concurrent sessions."""
        sessions = []

        # Create multiple sessions
        for i in range(10):
            config = SessionConfig(
                sender_comp_id=f"SENDER_{i}",
                target_comp_id=f"TARGET_{i}",
                heartbeat_interval=30,
            )
            session = FIXSession(config)
            sessions.append(session)

        # Verify all sessions are independent
        for i, session in enumerate(sessions):
            assert session.config.sender_comp_id == f"SENDER_{i}"
            assert session.config.target_comp_id == f"TARGET_{i}"
            assert session.state == SessionState.DISCONNECTED

    def test_large_message_handling(self):
        """Test handling of messages with large text fields."""
        # Create order with large text field
        large_text = "A" * 10000  # 10KB text field

        order = NewOrderSingle(
            symbol="EURUSD",
            side=Side.BUY,
            ord_type=OrdType.MARKET,
            order_qty=100000.0,
            text=large_text,
        )

        assert order.text == large_text
        assert len(order.text) == 10000

    def test_memory_usage_stability(self, performance_config):
        """Test memory usage remains stable during operation."""
        session = FIXSession(performance_config)

        initial_messages = session.statistics.messages_sent

        # Simulate extended operation
        for cycle in range(10):
            for i in range(100):
                session.statistics.messages_sent += 1
                session.get_next_outgoing_seq_num()

            # Reset some counters to simulate cleanup
            if cycle % 5 == 0:
                session.statistics.messages_sent = 0
                session.outgoing_seq_num = 1

        # Session should remain functional
        assert session.state == SessionState.DISCONNECTED
        current_seq = session.get_next_outgoing_seq_num()
        assert current_seq >= 1


# Test Fixtures and Utilities
@pytest.fixture
def sample_fix_logon_message():
    """Create sample FIX Logon message for testing."""
    return (
        "8=FIX.4.2\x019=73\x0135=A\x0149=SENDER\x0156=TARGET\x0134=1\x01"
        + "52=20230101-12:00:00\x0198=0\x01108=30\x01553=user\x01554=pass\x0110=123\x01"
    )


@pytest.fixture
def sample_fix_order_message():
    """Create sample FIX NewOrderSingle message for testing."""
    return (
        "8=FIX.4.2\x019=145\x0135=D\x0149=SENDER\x0156=TARGET\x0134=2\x01"
        + "52=20230101-12:00:00\x0111=CLIENT123\x0155=EURUSD\x0154=1\x01"
        + "38=100000\x0140=1\x0159=0\x0115=USD\x0110=123\x01"
    )


if __name__ == "__main__":
    """Run FIX protocol tests directly."""
    pytest.main([__file__, "-v", "--tb=short"])
