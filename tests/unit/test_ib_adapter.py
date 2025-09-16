"""Unit tests for Interactive Brokers adapter.

This module tests the IB adapter implementation including:
- FIX message translation
- Order submission and execution
- Connection management
- Error handling
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from fxml4.brokers.adapters.base import AdapterConfig, ConnectionStatus
from fxml4.brokers.adapters.ib_adapter import IBBrokerAdapter
from fxml4.brokers.adapters.ib_fix_translator import IBFIXTranslator
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from fxml4.fix.messages.orders import (
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
)
from ibapi.contract import Contract
from ibapi.execution import Execution
from ibapi.order import Order


class TestIBFIXTranslator:
    """Test FIX to IB message translation."""

    def test_fix_to_ib_contract_forex(self):
        """Test converting FIX order to IB forex contract."""
        order = NewOrderSingle(
            cl_ord_id="TEST123",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
        )

        contract = IBFIXTranslator.fix_to_ib_contract(order)

        assert contract.symbol == "EUR"
        assert contract.secType == "CASH"
        assert contract.currency == "USD"
        assert contract.exchange == "IDEALPRO"

    def test_fix_to_ib_contract_stock(self):
        """Test converting FIX order to IB stock contract."""
        order = NewOrderSingle(
            cl_ord_id="TEST124",
            symbol="AAPL",
            side=Side.BUY,
            order_qty=100,
            ord_type=OrdType.LIMIT,
            price=150.50,
        )
        order.currency = "USD"

        contract = IBFIXTranslator.fix_to_ib_contract(order)

        assert contract.symbol == "AAPL"
        assert contract.secType == "STK"
        assert contract.currency == "USD"
        assert contract.exchange == "SMART"

    def test_fix_to_ib_order_market(self):
        """Test converting FIX market order to IB order."""
        order = NewOrderSingle(
            cl_ord_id="TEST125",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.MARKET,
            time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
        )

        ib_order = IBFIXTranslator.fix_to_ib_order(order, account="DU123456")

        assert ib_order.action == "BUY"
        assert ib_order.totalQuantity == 100000
        assert ib_order.orderType == "MKT"
        assert ib_order.tif == "IOC"
        assert ib_order.account == "DU123456"

    def test_fix_to_ib_order_limit(self):
        """Test converting FIX limit order to IB order."""
        order = NewOrderSingle(
            cl_ord_id="TEST126",
            symbol="AAPL",
            side=Side.SELL,
            order_qty=200,
            ord_type=OrdType.LIMIT,
            price=151.25,
            time_in_force=TimeInForce.DAY,
        )

        ib_order = IBFIXTranslator.fix_to_ib_order(order)

        assert ib_order.action == "SELL"
        assert ib_order.totalQuantity == 200
        assert ib_order.orderType == "LMT"
        assert ib_order.lmtPrice == 151.25
        assert ib_order.tif == "DAY"

    def test_fix_to_ib_order_stop_limit(self):
        """Test converting FIX stop limit order to IB order."""
        order = NewOrderSingle(
            cl_ord_id="TEST127",
            symbol="GBPUSD",
            side=Side.SELL,
            order_qty=50000,
            ord_type=OrdType.STOP_LIMIT,
            price=1.2500,
            stop_px=1.2520,
            time_in_force=TimeInForce.GOOD_TILL_CANCEL,
        )

        ib_order = IBFIXTranslator.fix_to_ib_order(order)

        assert ib_order.action == "SELL"
        assert ib_order.totalQuantity == 50000
        assert ib_order.orderType == "STP LMT"
        assert ib_order.lmtPrice == 1.2500
        assert ib_order.auxPrice == 1.2520
        assert ib_order.tif == "GTC"

    def test_ib_status_to_fix(self):
        """Test IB status to FIX status mapping."""
        status_map = {
            "PendingSubmit": OrdStatus.PENDING_NEW,
            "Submitted": OrdStatus.NEW,
            "Filled": OrdStatus.FILLED,
            "PartiallyFilled": OrdStatus.PARTIALLY_FILLED,
            "Cancelled": OrdStatus.CANCELED,
            "Inactive": OrdStatus.REJECTED,
        }

        for ib_status, expected_fix_status in status_map.items():
            fix_status = IBFIXTranslator.ib_status_to_fix(ib_status)
            assert fix_status == expected_fix_status

    def test_ib_status_to_exec_type(self):
        """Test IB status to FIX execution type mapping."""
        exec_type_map = {
            "PendingSubmit": ExecType.PENDING_NEW,
            "Submitted": ExecType.NEW,
            "Filled": ExecType.TRADE,
            "PartiallyFilled": ExecType.TRADE,
            "Cancelled": ExecType.CANCELED,
            "Inactive": ExecType.REJECTED,
        }

        for ib_status, expected_exec_type in exec_type_map.items():
            exec_type = IBFIXTranslator.ib_status_to_exec_type(ib_status)
            assert exec_type == expected_exec_type

    def test_create_execution_report(self):
        """Test creating FIX execution report from IB data."""
        ib_contract = Contract()
        ib_contract.symbol = "EUR"
        ib_contract.secType = "CASH"
        ib_contract.currency = "USD"

        ib_order = Order()
        ib_order.action = "BUY"
        ib_order.totalQuantity = 100000
        ib_order.orderType = "LMT"
        ib_order.lmtPrice = 1.1000

        exec_report = IBFIXTranslator.create_execution_report(
            ib_order_id=12345,
            client_order_id="TEST128",
            ib_contract=ib_contract,
            ib_order=ib_order,
            ib_status="PartiallyFilled",
            filled=50000,
            remaining=50000,
            avg_fill_price=1.0995,
            last_fill_qty=25000,
            last_fill_price=1.0998,
        )

        assert exec_report.order_id == "12345"
        assert exec_report.cl_ord_id == "TEST128"
        assert exec_report.symbol == "EURUSD"
        assert exec_report.side == Side.BUY
        assert exec_report.ord_status == OrdStatus.PARTIALLY_FILLED
        assert exec_report.exec_type == ExecType.TRADE
        assert exec_report.cum_qty == 50000
        assert exec_report.leaves_qty == 50000
        assert exec_report.avg_px == 1.0995
        assert exec_report.last_qty == 25000
        assert exec_report.last_px == 1.0998
        assert exec_report.price == 1.1000

    def test_create_rejection_report(self):
        """Test creating FIX rejection report."""
        ib_contract = Contract()
        ib_contract.symbol = "AAPL"
        ib_contract.secType = "STK"

        ib_order = Order()
        ib_order.action = "BUY"
        ib_order.totalQuantity = 1000
        ib_order.orderType = "MKT"

        exec_report = IBFIXTranslator.create_execution_report(
            ib_order_id=12346,
            client_order_id="TEST129",
            ib_contract=ib_contract,
            ib_order=ib_order,
            ib_status="Inactive",
            error_code=201,
            error_msg="Order rejected - insufficient margin",
        )

        assert exec_report.ord_status == OrdStatus.REJECTED
        assert exec_report.exec_type == ExecType.REJECTED
        assert exec_report.ord_rej_reason == 201
        assert exec_report.text == "Order rejected - insufficient margin"

    def test_parse_ib_error(self):
        """Test parsing IB error codes."""
        # Test connection error
        error_info = IBFIXTranslator.parse_ib_error(
            1100, "Connectivity between IB and TWS has been lost"
        )
        assert error_info["type"] == "connection_lost"
        assert error_info["is_critical"] == True
        assert error_info["is_rejection"] == False

        # Test order rejection
        error_info = IBFIXTranslator.parse_ib_error(
            110, "The price does not conform to the minimum price variation"
        )
        assert error_info["type"] == "price_violates_constraints"
        assert error_info["is_critical"] == False
        assert error_info["is_rejection"] == True

        # Test warning
        error_info = IBFIXTranslator.parse_ib_error(
            2104, "Market data farm connection is OK"
        )
        assert error_info["type"] == "unknown_error"
        assert error_info["is_critical"] == False
        assert error_info["is_rejection"] == False
        assert error_info["is_warning"] == True


class TestIBBrokerAdapter:
    """Test IB broker adapter."""

    @pytest.fixture
    def adapter_config(self):
        """Create test adapter configuration."""
        return AdapterConfig(
            adapter_type="ib",
            connection_params={
                "host": "localhost",
                "port": 7497,
                "client_id": 1,
                "account_id": "DU123456",
            },
            features={"market_data": True, "order_modification": True},
            limits={"max_orders_per_second": 10},
        )

    @pytest.fixture
    def mock_ib_client(self):
        """Create mock IB client."""
        with patch("fxml4.brokers.adapters.ib_adapter.EClient") as mock_client:
            instance = MagicMock()
            mock_client.return_value = instance
            yield instance

    @pytest.fixture
    def adapter(self, adapter_config, mock_ib_client):
        """Create IB adapter instance."""
        return IBBrokerAdapter(adapter_config)

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter, mock_ib_client):
        """Test successful connection to IB."""
        # Mock successful connection
        mock_ib_client.connect.return_value = None
        mock_ib_client.isConnected.return_value = True

        # Mock nextValidId callback
        async def trigger_next_valid_id():
            await asyncio.sleep(0.1)
            adapter.nextValidId(1000)

        asyncio.create_task(trigger_next_valid_id())

        connected = await adapter.connect()

        assert connected == True
        assert adapter.connection.status == ConnectionStatus.READY
        assert adapter.next_order_id == 1000
        mock_ib_client.connect.assert_called_once_with("localhost", 7497, 1)

    @pytest.mark.asyncio
    async def test_connect_failure(self, adapter, mock_ib_client):
        """Test connection failure to IB."""
        # Mock connection failure
        mock_ib_client.connect.side_effect = Exception("Connection refused")

        connected = await adapter.connect()

        assert connected == False
        assert adapter.connection.status == ConnectionStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_submit_order(self, adapter, mock_ib_client):
        """Test order submission."""
        # Setup adapter state
        adapter.connection.status = ConnectionStatus.READY
        adapter.next_order_id = 1000
        adapter.account_id = "DU123456"

        # Create test order
        order = NewOrderSingle(
            cl_ord_id="TEST130",
            symbol="EURUSD",
            side=Side.BUY,
            order_qty=100000,
            ord_type=OrdType.LIMIT,
            price=1.1000,
            time_in_force=TimeInForce.DAY,
        )

        # Submit order
        order_id = await adapter.submit_order(order)

        assert order_id == "1000"
        assert "TEST130" in adapter.active_orders
        assert adapter.active_orders["TEST130"]["ib_order_id"] == 1000
        assert adapter.next_order_id == 1001

        # Verify IB client calls
        mock_ib_client.placeOrder.assert_called_once()
        call_args = mock_ib_client.placeOrder.call_args[0]
        assert call_args[0] == 1000  # order ID
        assert isinstance(call_args[1], Contract)
        assert isinstance(call_args[2], Order)

    @pytest.mark.asyncio
    async def test_cancel_order(self, adapter, mock_ib_client):
        """Test order cancellation."""
        # Setup adapter state
        adapter.connection.status = ConnectionStatus.READY
        adapter.active_orders["TEST131"] = {"ib_order_id": 1001, "status": "Submitted"}

        # Create cancel request
        cancel_request = OrderCancelRequest(
            orig_cl_ord_id="TEST131", cl_ord_id="CANCEL131"
        )

        # Cancel order
        success = await adapter.cancel_order(cancel_request)

        assert success == True
        mock_ib_client.cancelOrder.assert_called_once_with(1001)

    @pytest.mark.asyncio
    async def test_order_status_callback(self, adapter):
        """Test order status callback handling."""
        # Setup order tracking
        adapter.active_orders["TEST132"] = {
            "ib_order_id": 1002,
            "status": "PendingSubmit",
            "ib_order": Order(),
            "ib_contract": Contract(),
        }

        # Mock fix translator
        with patch.object(adapter, "fix_translator") as mock_translator:
            mock_exec_report = ExecutionReport(
                order_id="1002",
                cl_ord_id="TEST132",
                exec_type=ExecType.NEW,
                ord_status=OrdStatus.NEW,
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=100000,
            )
            mock_translator.create_execution_report.return_value = mock_exec_report

            # Trigger order status callback
            adapter.orderStatus(
                orderId=1002,
                status="Submitted",
                filled=0,
                remaining=100000,
                avgFillPrice=0,
                permId=0,
                parentId=0,
                lastFillPrice=0,
                clientId=1,
                whyHeld="",
                mktCapPrice=0,
            )

            # Verify order state updated
            assert adapter.active_orders["TEST132"]["status"] == "Submitted"

            # Verify execution report created
            mock_translator.create_execution_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_callback(self, adapter):
        """Test execution callback handling."""
        # Setup order tracking
        adapter.active_orders["TEST133"] = {
            "ib_order_id": 1003,
            "status": "Submitted",
            "filled": 0,
            "ib_order": Order(),
            "ib_contract": Contract(),
        }

        # Create mock execution
        execution = Execution()
        execution.orderId = 1003
        execution.execId = "EXEC123"
        execution.shares = 50000
        execution.price = 1.0995
        execution.side = "BOT"
        execution.time = "20231215  10:30:00"

        # Mock fix translator
        with patch.object(adapter, "fix_translator") as mock_translator:
            mock_exec_report = ExecutionReport(
                order_id="1003",
                cl_ord_id="TEST133",
                exec_id="EXEC123",
                exec_type=ExecType.TRADE,
                ord_status=OrdStatus.PARTIALLY_FILLED,
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=100000,
                last_qty=50000,
                last_px=1.0995,
                cum_qty=50000,
                leaves_qty=50000,
            )
            mock_translator.create_execution_report_from_ib_execution.return_value = (
                mock_exec_report
            )

            # Trigger execution callback
            adapter.execDetails(reqId=0, contract=Contract(), execution=execution)

            # Verify order state updated
            assert adapter.active_orders["TEST133"]["filled"] == 50000

            # Verify execution report created
            mock_translator.create_execution_report_from_ib_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_callback_order_rejection(self, adapter):
        """Test error callback for order rejection."""
        # Setup order tracking
        adapter.active_orders["TEST134"] = {
            "ib_order_id": 1004,
            "status": "PendingSubmit",
            "ib_order": Order(),
            "ib_contract": Contract(),
        }

        # Mock fix translator
        with patch.object(adapter, "fix_translator") as mock_translator:
            mock_translator.parse_ib_error.return_value = {
                "code": 201,
                "message": "Order rejected",
                "type": "order_rejected",
                "is_critical": False,
                "is_rejection": True,
                "is_warning": False,
            }

            mock_exec_report = ExecutionReport(
                order_id="1004",
                cl_ord_id="TEST134",
                exec_type=ExecType.REJECTED,
                ord_status=OrdStatus.REJECTED,
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=100000,
                ord_rej_reason=201,
                text="Order rejected",
            )
            mock_translator.create_execution_report.return_value = mock_exec_report

            # Trigger error callback
            adapter.error(reqId=1004, errorCode=201, errorString="Order rejected")

            # Verify order removed from active
            assert "TEST134" not in adapter.active_orders

            # Verify rejection report created
            mock_translator.create_execution_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_lost_callback(self, adapter):
        """Test connection lost callback."""
        adapter.connection.status = ConnectionStatus.READY

        # Trigger connection lost
        adapter.error(reqId=-1, errorCode=1100, errorString="Connectivity lost")

        assert adapter.connection.status == ConnectionStatus.ERROR
        assert adapter.connection.error == "Connectivity lost"

    @pytest.mark.asyncio
    async def test_rate_limiting(self, adapter):
        """Test order rate limiting."""
        adapter.connection.status = ConnectionStatus.READY
        adapter.next_order_id = 2000
        adapter.config.limits["max_orders_per_second"] = 2

        # Submit multiple orders rapidly
        orders = []
        for i in range(5):
            order = NewOrderSingle(
                cl_ord_id=f"TEST{135+i}",
                symbol="EURUSD",
                side=Side.BUY,
                order_qty=10000,
                ord_type=OrdType.MARKET,
            )
            orders.append(order)

        # Time the submissions
        start_time = asyncio.get_event_loop().time()

        tasks = [adapter.submit_order(order) for order in orders]
        results = await asyncio.gather(*tasks)

        end_time = asyncio.get_event_loop().time()
        elapsed = end_time - start_time

        # Should take at least 2 seconds for 5 orders at 2 orders/sec
        assert elapsed >= 2.0
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_market_data_subscription(self, adapter, mock_ib_client):
        """Test market data subscription."""
        adapter.connection.status = ConnectionStatus.READY
        adapter.next_req_id = 1000

        # Subscribe to market data
        success = await adapter.subscribe_market_data(["EURUSD", "GBPUSD"])

        assert success == True
        assert "EURUSD" in adapter.market_data_subscriptions
        assert "GBPUSD" in adapter.market_data_subscriptions

        # Verify IB client calls
        assert mock_ib_client.reqMktData.call_count == 2

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter, mock_ib_client):
        """Test adapter disconnection."""
        adapter.connection.status = ConnectionStatus.READY
        adapter.active_orders = {"TEST140": {"ib_order_id": 2000}}

        await adapter.disconnect()

        assert adapter.connection.status == ConnectionStatus.DISCONNECTED
        assert len(adapter.active_orders) == 0
        mock_ib_client.disconnect.assert_called_once()
