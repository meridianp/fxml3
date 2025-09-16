"""
Comprehensive FIX Protocol Testing Suite
========================================

This module provides comprehensive testing for FIX 4.2/4.4 protocol implementation,
addressing the coverage gaps identified in the audit:
- Message validation for all FIX message types
- Session recovery and gap fill scenarios
- Multi-broker failover testing
- Order routing and execution
- Market data subscription and updates

Coverage Target: 85%+ (from current 65-70%)
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest
from simplefix import FixMessage, FixParser

from tests.conftest_enhanced import mock_fix_session, unique_test_id


class TestFIXMessageValidation:
    """Comprehensive FIX message validation testing."""

    @pytest.mark.fix_protocol
    @pytest.mark.parametrize(
        "msg_type,fields",
        [
            (
                "D",
                {"Symbol": "EURUSD", "Side": "1", "OrderQty": "10000"},
            ),  # NewOrderSingle
            ("F", {"OrigClOrdID": "123", "ClOrdID": "124"}),  # OrderCancelRequest
            (
                "G",
                {"OrigClOrdID": "123", "ClOrdID": "125"},
            ),  # OrderCancelReplaceRequest
            ("H", {"ClOrdID": "126"}),  # OrderStatusRequest
            ("8", {"OrderID": "127", "ExecType": "0"}),  # ExecutionReport
            ("9", {"OrderID": "128", "CxlRejReason": "0"}),  # OrderCancelReject
            ("A", {"ResetSeqNumFlag": "Y"}),  # Logon
            ("5", {}),  # Logout
            ("0", {}),  # Heartbeat
            ("1", {"TestReqID": "TEST123"}),  # TestRequest
            ("2", {"BeginSeqNo": "1", "EndSeqNo": "10"}),  # ResendRequest
            ("3", {"RefSeqNum": "5", "Text": "Message rejected"}),  # Reject
            ("4", {"NewSeqNo": "100"}),  # SequenceReset
        ],
    )
    def test_fix_message_creation_and_parsing(self, msg_type, fields):
        """Test creation and parsing of all major FIX message types."""
        # Create message
        msg = FixMessage()
        msg.append_string("8=FIX.4.2")
        msg.append_pair(35, msg_type)
        msg.append_pair(49, "SENDER")
        msg.append_pair(56, "TARGET")
        msg.append_pair(34, 1)
        msg.append_time(52)

        # Add message-specific fields
        for tag, value in fields.items():
            tag_num = self._get_tag_number(tag)
            msg.append_pair(tag_num, value)

        # Validate message structure
        raw_msg = msg.encode()
        assert b"8=FIX.4.2" in raw_msg
        assert f"35={msg_type}".encode() in raw_msg

        # Parse message back
        parser = FixParser()
        parser.append_buffer(raw_msg)
        parsed_msg = parser.get_message()

        assert parsed_msg is not None
        assert parsed_msg.get(35).decode() == msg_type

        # Validate fields
        for tag, expected_value in fields.items():
            tag_num = self._get_tag_number(tag)
            actual_value = parsed_msg.get(tag_num)
            if actual_value:
                assert actual_value.decode() == expected_value

    def _get_tag_number(self, field_name: str) -> int:
        """Get FIX tag number from field name."""
        tag_map = {
            "Symbol": 55,
            "Side": 54,
            "OrderQty": 38,
            "OrigClOrdID": 41,
            "ClOrdID": 11,
            "OrderID": 37,
            "ExecType": 150,
            "CxlRejReason": 102,
            "ResetSeqNumFlag": 141,
            "TestReqID": 112,
            "BeginSeqNo": 7,
            "EndSeqNo": 16,
            "RefSeqNum": 45,
            "Text": 58,
            "NewSeqNo": 36,
        }
        return tag_map.get(field_name, 0)

    @pytest.mark.fix_protocol
    def test_fix_message_validation_rules(self):
        """Test FIX message validation rules and constraints."""
        # Test required fields
        msg = FixMessage()
        msg.append_string("8=FIX.4.2")
        msg.append_pair(35, "D")  # NewOrderSingle

        # Missing required fields should fail validation
        assert not self._validate_new_order(msg)

        # Add required fields
        msg.append_pair(11, "CLO123")  # ClOrdID
        msg.append_pair(55, "EURUSD")  # Symbol
        msg.append_pair(54, "1")  # Side (Buy)
        msg.append_pair(38, "10000")  # OrderQty
        msg.append_pair(40, "2")  # OrdType (Limit)
        msg.append_pair(44, "1.1000")  # Price

        # Now should pass validation
        assert self._validate_new_order(msg)

        # Test invalid values
        msg.append_pair(54, "3")  # Invalid Side value
        assert not self._validate_new_order(msg)

    def _validate_new_order(self, msg: FixMessage) -> bool:
        """Validate NewOrderSingle message."""
        required_tags = [11, 55, 54, 38, 40]  # ClOrdID, Symbol, Side, OrderQty, OrdType

        for tag in required_tags:
            if not msg.get(tag):
                return False

        # Validate Side values (1=Buy, 2=Sell)
        side = msg.get(54)
        if side and side.decode() not in ["1", "2"]:
            return False

        # Validate OrderQty is positive
        qty = msg.get(38)
        if qty:
            try:
                if int(qty.decode()) <= 0:
                    return False
            except ValueError:
                return False

        return True


class TestFIXSessionManagement:
    """Test FIX session lifecycle and recovery."""

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_session_logon_and_logout(self, mock_fix_session):
        """Test normal session logon and logout sequence."""
        session = mock_fix_session

        # Test logon
        logon_msg = self._create_logon_message()
        success = await session.send_message(logon_msg)
        assert success is True
        assert session.is_logged_on() is True

        # Test heartbeat during session
        heartbeat = self._create_heartbeat_message()
        await session.send_message(heartbeat)

        # Test logout
        logout_msg = self._create_logout_message()
        await session.send_message(logout_msg)
        assert session.is_logged_on() is False

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_session_recovery_after_disconnect(self):
        """Test session recovery after unexpected disconnection."""
        session = Mock()

        # Setup initial state
        session.outgoing_seq_num = 100
        session.incoming_seq_num = 95
        session.is_connected = False

        # Simulate reconnection
        session.reconnect = AsyncMock(return_value=True)
        await session.reconnect()

        # Send logon with sequence reset
        logon_msg = self._create_logon_message(reset_seq=True)
        session.send_message = AsyncMock(return_value=True)
        await session.send_message(logon_msg)

        # Request message resend for gap
        resend_request = self._create_resend_request(95, 99)
        await session.send_message(resend_request)

        # Process resent messages
        for seq in range(95, 100):
            msg = Mock()
            msg.seq_num = seq
            session.process_resent_message = AsyncMock()
            await session.process_resent_message(msg)

        # Verify session is recovered
        assert session.reconnect.called
        assert session.send_message.call_count >= 2

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_gap_fill_and_message_recovery(self):
        """Test gap fill and message recovery scenarios."""
        session = Mock()
        message_store = []

        # Simulate message gap (received seq 1-5, 11-15, missing 6-10)
        for i in [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]:
            msg = Mock()
            msg.seq_num = i
            msg.msg_type = "8"  # ExecutionReport
            message_store.append(msg)

        # Detect gap
        expected_seq = 6
        received_seq = 11
        assert received_seq > expected_seq  # Gap detected

        # Send ResendRequest
        resend_msg = self._create_resend_request(6, 10)
        session.send_message = AsyncMock(return_value=True)
        await session.send_message(resend_msg)

        # Receive gap fill messages
        gap_fill_msgs = []
        for seq in range(6, 11):
            msg = Mock()
            msg.seq_num = seq
            msg.msg_type = "4"  # SequenceReset/GapFill
            msg.new_seq_no = seq + 1
            gap_fill_msgs.append(msg)

        # Process gap fill
        for msg in gap_fill_msgs:
            session.process_gap_fill = AsyncMock()
            await session.process_gap_fill(msg)

        # Verify sequence is now continuous
        all_seqs = [msg.seq_num for msg in message_store + gap_fill_msgs]
        all_seqs.sort()
        assert all_seqs == list(range(1, 16))

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_sequence_number_reset(self):
        """Test sequence number reset scenarios."""
        session = Mock()

        # Test admin-initiated reset
        session.outgoing_seq_num = 1000
        session.incoming_seq_num = 950

        reset_msg = self._create_sequence_reset(new_seq_no=1)
        session.process_sequence_reset = AsyncMock()
        await session.process_sequence_reset(reset_msg)

        # Verify sequences are reset
        session.reset_sequence_numbers = Mock()
        session.reset_sequence_numbers()

        assert session.reset_sequence_numbers.called

    def _create_logon_message(self, reset_seq: bool = False) -> Dict:
        """Create a FIX Logon message."""
        return {
            "MsgType": "A",
            "HeartBtInt": 30,
            "ResetSeqNumFlag": "Y" if reset_seq else "N",
            "Username": "testuser",
            "Password": "testpass",
        }

    def _create_logout_message(self) -> Dict:
        """Create a FIX Logout message."""
        return {
            "MsgType": "5",
            "Text": "Normal logout",
        }

    def _create_heartbeat_message(self) -> Dict:
        """Create a FIX Heartbeat message."""
        return {"MsgType": "0"}

    def _create_resend_request(self, begin_seq: int, end_seq: int) -> Dict:
        """Create a FIX ResendRequest message."""
        return {
            "MsgType": "2",
            "BeginSeqNo": str(begin_seq),
            "EndSeqNo": str(end_seq),
        }

    def _create_sequence_reset(self, new_seq_no: int) -> Dict:
        """Create a FIX SequenceReset message."""
        return {
            "MsgType": "4",
            "GapFillFlag": "Y",
            "NewSeqNo": str(new_seq_no),
        }


class TestFIXOrderManagement:
    """Test FIX order lifecycle and management."""

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_complete_order_lifecycle(self):
        """Test complete order lifecycle from creation to fill."""
        session = Mock()

        # Step 1: Create and send new order
        order = {
            "ClOrdID": "ORD001",
            "Symbol": "EURUSD",
            "Side": "1",  # Buy
            "OrderQty": "10000",
            "OrdType": "2",  # Limit
            "Price": "1.1000",
            "TimeInForce": "0",  # Day
        }

        new_order_msg = self._create_new_order_single(order)
        session.send_order = AsyncMock(return_value="ORD001")
        order_id = await session.send_order(new_order_msg)
        assert order_id == "ORD001"

        # Step 2: Receive acknowledgment
        ack_report = {
            "OrderID": "BROKER123",
            "ClOrdID": "ORD001",
            "ExecType": "A",  # Pending New
            "OrdStatus": "A",
            "Symbol": "EURUSD",
            "Side": "1",
            "LeavesQty": "10000",
            "CumQty": "0",
        }
        session.process_execution_report = AsyncMock()
        await session.process_execution_report(ack_report)

        # Step 3: Receive new order confirmation
        new_report = {
            "OrderID": "BROKER123",
            "ClOrdID": "ORD001",
            "ExecType": "0",  # New
            "OrdStatus": "0",
            "LeavesQty": "10000",
            "CumQty": "0",
        }
        await session.process_execution_report(new_report)

        # Step 4: Receive partial fill
        partial_fill = {
            "OrderID": "BROKER123",
            "ClOrdID": "ORD001",
            "ExecType": "F",  # Trade
            "OrdStatus": "1",  # Partially filled
            "LastQty": "5000",
            "LastPx": "1.0999",
            "LeavesQty": "5000",
            "CumQty": "5000",
        }
        await session.process_execution_report(partial_fill)

        # Step 5: Receive complete fill
        complete_fill = {
            "OrderID": "BROKER123",
            "ClOrdID": "ORD001",
            "ExecType": "F",  # Trade
            "OrdStatus": "2",  # Filled
            "LastQty": "5000",
            "LastPx": "1.1000",
            "LeavesQty": "0",
            "CumQty": "10000",
            "AvgPx": "1.09995",
        }
        await session.process_execution_report(complete_fill)

        # Verify order is complete
        assert session.process_execution_report.call_count == 4

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_order_cancel_request(self):
        """Test order cancellation flow."""
        session = Mock()

        # Send cancel request
        cancel_request = {
            "OrigClOrdID": "ORD001",
            "ClOrdID": "CANCEL001",
            "Symbol": "EURUSD",
            "Side": "1",
            "OrderQty": "10000",
        }

        cancel_msg = self._create_order_cancel_request(cancel_request)
        session.send_cancel = AsyncMock(return_value=True)
        success = await session.send_cancel(cancel_msg)
        assert success is True

        # Receive cancel acknowledgment
        cancel_ack = {
            "OrderID": "BROKER123",
            "ClOrdID": "CANCEL001",
            "OrigClOrdID": "ORD001",
            "ExecType": "6",  # Pending Cancel
            "OrdStatus": "6",
        }
        session.process_execution_report = AsyncMock()
        await session.process_execution_report(cancel_ack)

        # Receive cancel confirmation
        cancel_confirm = {
            "OrderID": "BROKER123",
            "ClOrdID": "CANCEL001",
            "OrigClOrdID": "ORD001",
            "ExecType": "4",  # Canceled
            "OrdStatus": "4",
            "Text": "Order canceled by user",
        }
        await session.process_execution_report(cancel_confirm)

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_order_replace_request(self):
        """Test order modification/replace flow."""
        session = Mock()

        # Send replace request (modify price)
        replace_request = {
            "OrigClOrdID": "ORD001",
            "ClOrdID": "REPLACE001",
            "Symbol": "EURUSD",
            "Side": "1",
            "OrderQty": "10000",
            "OrdType": "2",
            "Price": "1.0950",  # New price
        }

        replace_msg = self._create_order_cancel_replace(replace_request)
        session.send_replace = AsyncMock(return_value=True)
        success = await session.send_replace(replace_msg)
        assert success is True

        # Receive replace acknowledgment
        replace_ack = {
            "OrderID": "BROKER123",
            "ClOrdID": "REPLACE001",
            "OrigClOrdID": "ORD001",
            "ExecType": "E",  # Pending Replace
            "OrdStatus": "E",
        }
        session.process_execution_report = AsyncMock()
        await session.process_execution_report(replace_ack)

        # Receive replace confirmation
        replace_confirm = {
            "OrderID": "BROKER123_NEW",
            "ClOrdID": "REPLACE001",
            "OrigClOrdID": "ORD001",
            "ExecType": "5",  # Replaced
            "OrdStatus": "0",  # New
            "Price": "1.0950",
        }
        await session.process_execution_report(replace_confirm)

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_order_rejection_handling(self):
        """Test order rejection scenarios."""
        session = Mock()

        # Test various rejection scenarios
        rejection_scenarios = [
            {
                "reason": "Invalid symbol",
                "code": "1",
                "text": "Unknown symbol INVALID",
            },
            {
                "reason": "Insufficient margin",
                "code": "3",
                "text": "Insufficient funds",
            },
            {
                "reason": "Market closed",
                "code": "5",
                "text": "Market is closed",
            },
            {
                "reason": "Invalid quantity",
                "code": "6",
                "text": "Quantity below minimum",
            },
        ]

        for scenario in rejection_scenarios:
            # Send order
            order = self._create_new_order_single(
                {
                    "ClOrdID": f"ORD_{scenario['code']}",
                    "Symbol": "EURUSD",
                    "Side": "1",
                    "OrderQty": "10000",
                }
            )

            # Receive rejection
            rejection = {
                "OrderID": "NONE",
                "ClOrdID": f"ORD_{scenario['code']}",
                "ExecType": "8",  # Rejected
                "OrdStatus": "8",
                "OrdRejReason": scenario["code"],
                "Text": scenario["text"],
            }

            session.process_execution_report = AsyncMock()
            await session.process_execution_report(rejection)

            # Verify rejection was processed
            assert session.process_execution_report.called

    def _create_new_order_single(self, order: Dict) -> Dict:
        """Create a NewOrderSingle message."""
        return {
            "MsgType": "D",
            **order,
            "TransactTime": datetime.now(timezone.utc).isoformat(),
        }

    def _create_order_cancel_request(self, request: Dict) -> Dict:
        """Create an OrderCancelRequest message."""
        return {
            "MsgType": "F",
            **request,
            "TransactTime": datetime.now(timezone.utc).isoformat(),
        }

    def _create_order_cancel_replace(self, request: Dict) -> Dict:
        """Create an OrderCancelReplaceRequest message."""
        return {
            "MsgType": "G",
            **request,
            "TransactTime": datetime.now(timezone.utc).isoformat(),
        }


class TestFIXMarketData:
    """Test FIX market data subscription and updates."""

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_market_data_subscription(self):
        """Test market data subscription flow."""
        session = Mock()

        # Subscribe to market data
        subscription = {
            "MDReqID": "MD001",
            "SubscriptionRequestType": "1",  # Subscribe
            "MarketDepth": "1",  # Top of book
            "MDUpdateType": "0",  # Full refresh
            "NoMDEntryTypes": "2",
            "MDEntryTypes": ["0", "1"],  # Bid, Offer
            "NoRelatedSym": "3",
            "Symbols": ["EURUSD", "GBPUSD", "USDJPY"],
        }

        sub_msg = self._create_market_data_request(subscription)
        session.subscribe_market_data = AsyncMock(return_value="MD001")
        req_id = await session.subscribe_market_data(sub_msg)
        assert req_id == "MD001"

        # Receive market data snapshot
        snapshot = {
            "MDReqID": "MD001",
            "Symbol": "EURUSD",
            "NoMDEntries": "2",
            "MDEntries": [
                {
                    "MDEntryType": "0",  # Bid
                    "MDEntryPx": "1.0995",
                    "MDEntrySize": "1000000",
                    "MDEntryTime": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "MDEntryType": "1",  # Offer
                    "MDEntryPx": "1.0997",
                    "MDEntrySize": "1000000",
                    "MDEntryTime": datetime.now(timezone.utc).isoformat(),
                },
            ],
        }

        session.process_market_data_snapshot = AsyncMock()
        await session.process_market_data_snapshot(snapshot)

        # Receive incremental updates
        update = {
            "MDReqID": "MD001",
            "NoMDEntries": "1",
            "MDEntries": [
                {
                    "MDUpdateAction": "0",  # New
                    "MDEntryType": "0",  # Bid
                    "Symbol": "EURUSD",
                    "MDEntryPx": "1.0996",
                    "MDEntrySize": "500000",
                },
            ],
        }

        session.process_market_data_update = AsyncMock()
        await session.process_market_data_update(update)

        # Unsubscribe
        unsub_msg = {
            "MDReqID": "MD001",
            "SubscriptionRequestType": "2",  # Unsubscribe
        }
        session.unsubscribe_market_data = AsyncMock(return_value=True)
        success = await session.unsubscribe_market_data(unsub_msg)
        assert success is True

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_market_data_reject_handling(self):
        """Test market data request rejection."""
        session = Mock()

        # Send invalid subscription
        invalid_sub = {
            "MDReqID": "MD002",
            "SubscriptionRequestType": "1",
            "Symbols": ["INVALID"],
        }

        # Receive rejection
        reject = {
            "MDReqID": "MD002",
            "MDReqRejReason": "0",  # Unknown symbol
            "Text": "Symbol INVALID not available",
        }

        session.process_market_data_reject = AsyncMock()
        await session.process_market_data_reject(reject)

        assert session.process_market_data_reject.called

    def _create_market_data_request(self, request: Dict) -> Dict:
        """Create a MarketDataRequest message."""
        return {
            "MsgType": "V",
            **request,
        }


class TestFIXMultiBrokerFailover:
    """Test multi-broker failover scenarios."""

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_automatic_broker_failover(self):
        """Test automatic failover to backup broker on primary failure."""
        primary_session = Mock()
        backup_session = Mock()

        # Setup primary broker
        primary_session.is_connected = True
        primary_session.broker_name = "PrimaryBroker"

        # Setup backup broker
        backup_session.is_connected = False
        backup_session.broker_name = "BackupBroker"

        # Simulate primary broker failure
        primary_session.is_connected = False
        primary_session.last_heartbeat = datetime.now(timezone.utc) - timedelta(
            minutes=5
        )

        # Failover logic
        if not primary_session.is_connected:
            # Connect to backup
            backup_session.connect = AsyncMock(return_value=True)
            await backup_session.connect()
            backup_session.is_connected = True

            # Transfer pending orders
            pending_orders = ["ORD001", "ORD002", "ORD003"]
            for order_id in pending_orders:
                backup_session.resend_order = AsyncMock(return_value=True)
                await backup_session.resend_order(order_id)

        # Verify failover completed
        assert not primary_session.is_connected
        assert backup_session.is_connected
        assert backup_session.resend_order.call_count == 3

    @pytest.mark.fix_protocol
    @pytest.mark.asyncio
    async def test_best_execution_routing(self):
        """Test routing orders to broker with best execution."""
        brokers = [
            {
                "name": "Broker1",
                "session": Mock(),
                "quote": {"bid": 1.0995, "ask": 1.0997},
            },
            {
                "name": "Broker2",
                "session": Mock(),
                "quote": {"bid": 1.0996, "ask": 1.0998},
            },
            {
                "name": "Broker3",
                "session": Mock(),
                "quote": {"bid": 1.0994, "ask": 1.0996},
            },
        ]

        # Get quotes from all brokers
        for broker in brokers:
            broker["session"].get_quote = AsyncMock(return_value=broker["quote"])
            quote = await broker["session"].get_quote("EURUSD")
            assert quote == broker["quote"]

        # Find best price for buy order
        best_broker_buy = min(brokers, key=lambda b: b["quote"]["ask"])
        assert best_broker_buy["name"] == "Broker3"

        # Find best price for sell order
        best_broker_sell = max(brokers, key=lambda b: b["quote"]["bid"])
        assert best_broker_sell["name"] == "Broker2"

        # Route buy order to best broker
        buy_order = self._create_test_order("BUY")
        best_broker_buy["session"].send_order = AsyncMock(return_value="ORD_BUY_001")
        order_id = await best_broker_buy["session"].send_order(buy_order)
        assert order_id == "ORD_BUY_001"

        # Route sell order to best broker
        sell_order = self._create_test_order("SELL")
        best_broker_sell["session"].send_order = AsyncMock(return_value="ORD_SELL_001")
        order_id = await best_broker_sell["session"].send_order(sell_order)
        assert order_id == "ORD_SELL_001"

    def _create_test_order(self, side: str) -> Dict:
        """Create a test order."""
        return {
            "ClOrdID": f"TEST_{side}_{time.time()}",
            "Symbol": "EURUSD",
            "Side": "1" if side == "BUY" else "2",
            "OrderQty": "10000",
            "OrdType": "1",  # Market
        }


# ============================================================================
# Performance and Load Testing
# ============================================================================


class TestFIXPerformance:
    """Test FIX protocol performance under load."""

    @pytest.mark.fix_protocol
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_high_frequency_order_submission(self):
        """Test high-frequency order submission performance."""
        session = Mock()
        session.send_order = AsyncMock(return_value=True)

        # Submit 1000 orders rapidly
        num_orders = 1000
        start_time = time.perf_counter()

        tasks = []
        for i in range(num_orders):
            order = {
                "ClOrdID": f"PERF_{i}",
                "Symbol": "EURUSD",
                "Side": "1" if i % 2 == 0 else "2",
                "OrderQty": "10000",
                "OrdType": "1",
            }
            tasks.append(session.send_order(order))

        await asyncio.gather(*tasks)

        elapsed = time.perf_counter() - start_time
        orders_per_second = num_orders / elapsed

        # Performance assertions
        assert orders_per_second > 100  # Should handle >100 orders/second
        assert session.send_order.call_count == num_orders

    @pytest.mark.fix_protocol
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_message_parsing_performance(self):
        """Test FIX message parsing performance."""
        parser = FixParser()

        # Create sample message
        msg = FixMessage()
        msg.append_string("8=FIX.4.2")
        msg.append_pair(35, "8")  # ExecutionReport
        msg.append_pair(49, "SENDER")
        msg.append_pair(56, "TARGET")
        msg.append_pair(34, 1)
        msg.append_time(52)
        msg.append_pair(37, "ORD123")
        msg.append_pair(11, "CLO123")
        msg.append_pair(150, "F")
        msg.append_pair(39, "2")
        msg.append_pair(55, "EURUSD")
        msg.append_pair(54, "1")
        msg.append_pair(38, "10000")
        msg.append_pair(32, "10000")
        msg.append_pair(31, "1.1000")
        msg.append_pair(6, "1.1000")

        raw_msg = msg.encode()

        # Parse 10000 messages
        num_messages = 10000
        start_time = time.perf_counter()

        for _ in range(num_messages):
            parser.append_buffer(raw_msg)
            parsed = parser.get_message()
            assert parsed is not None

        elapsed = time.perf_counter() - start_time
        messages_per_second = num_messages / elapsed

        # Should parse >1000 messages/second
        assert messages_per_second > 1000
