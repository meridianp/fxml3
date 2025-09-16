"""Interactive Brokers Adapter Implementation.

This module provides an adapter for Interactive Brokers that conforms to the
FIX-based broker abstraction interface, enabling seamless integration with
the FXML4 trading system through RabbitMQ message queues.
"""

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

import pika

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.execution import Execution
from ibapi.order import Order
from ibapi.order_state import OrderState
from ibapi.wrapper import EWrapper

from ...fix.messages.admin import Heartbeat, Logon, Logout, TestRequest
from ...fix.messages.orders import (
    ExecType,
    ExecutionReport,
    NewOrderSingle,
    OrderCancelRequest,
    OrdStatus,
    OrdType,
    Side,
    TimeInForce,
)
from ...fix.utils.builder import FIXBuilder
from ...fix.utils.parser import FIXParser
from ..messaging.publisher import BrokerMessagePublisher
from .base import (
    AdapterConfig,
    BrokerAdapter,
    BrokerConnection,
    ConnectionStatus,
    OrderInfo,
    OrderStatus,
)

logger = logging.getLogger(__name__)


class IBWrapper(EWrapper):
    """IB API wrapper for handling callbacks."""

    def __init__(self, adapter: "IBBrokerAdapter"):
        super().__init__()
        self.adapter = adapter

    def nextValidId(self, orderId: int):
        """Callback for next valid order ID."""
        self.adapter.next_order_id = orderId
        logger.info("IB: Next valid order ID: %d", orderId)

    def connectAck(self):
        """Callback for connection acknowledgment."""
        logger.info("IB: Connected to Gateway/TWS")
        self.adapter._update_connection_status(ConnectionStatus.CONNECTED)

    def connectionClosed(self):
        """Callback for connection closed."""
        logger.info("IB: Connection closed")
        self.adapter._update_connection_status(ConnectionStatus.DISCONNECTED)

    def error(self, reqId: int, errorCode: int, errorString: str):
        """Callback for errors."""
        error_msg = f"IB Error {errorCode}: {errorString} (reqId: {reqId})"

        if errorCode in [502, 504]:  # Cannot connect to TWS
            logger.error(error_msg)
            self.adapter._update_connection_status(ConnectionStatus.ERROR, error_msg)
        elif errorCode == 200:  # No security definition found
            logger.warning(error_msg)
            # Handle order rejection
            if reqId in self.adapter.pending_orders:
                self.adapter._handle_order_rejection(reqId, errorCode, errorString)
        else:
            logger.warning(error_msg)

    def openOrder(
        self, orderId: int, contract: Contract, order: Order, orderState: OrderState
    ):
        """Callback for open order."""
        logger.debug(
            "IB: Open order %d: %s %s @ %s",
            orderId,
            order.action,
            contract.symbol,
            order.lmtPrice if order.orderType == "LMT" else "MKT",
        )
        self.adapter._handle_open_order(orderId, contract, order, orderState)

    def orderStatus(
        self,
        orderId: int,
        status: str,
        filled: Decimal,
        remaining: Decimal,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float,
    ):
        """Callback for order status."""
        logger.debug(
            "IB: Order status %d: %s (filled: %s, remaining: %s)",
            orderId,
            status,
            filled,
            remaining,
        )
        self.adapter._handle_order_status(
            orderId, status, filled, remaining, avgFillPrice
        )

    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        """Callback for execution details."""
        logger.info(
            "IB: Execution %s: %s %s %s @ %s",
            execution.execId,
            execution.side,
            execution.shares,
            contract.symbol,
            execution.price,
        )
        self.adapter._handle_execution(reqId, contract, execution)

    def accountSummary(
        self, reqId: int, account: str, tag: str, value: str, currency: str
    ):
        """Callback for account summary."""
        self.adapter._handle_account_summary(reqId, account, tag, value, currency)

    def position(
        self, account: str, contract: Contract, position: Decimal, avgCost: float
    ):
        """Callback for position."""
        self.adapter._handle_position(account, contract, position, avgCost)

    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """Callback for tick price."""
        self.adapter._handle_tick_price(reqId, tickType, price)

    def tickSize(self, reqId: int, tickType: int, size: Decimal):
        """Callback for tick size."""
        self.adapter._handle_tick_size(reqId, tickType, size)


class IBClient(EClient):
    """IB API client for sending requests."""

    def __init__(self, wrapper: IBWrapper):
        super().__init__(wrapper)


class IBBrokerAdapter(BrokerAdapter):
    """Interactive Brokers adapter implementation.

    This adapter provides integration with Interactive Brokers TWS/Gateway
    using the FIX protocol abstraction layer over RabbitMQ.
    """

    def __init__(self, config: AdapterConfig):
        """Initialize IB broker adapter.

        Args:
            config: Adapter configuration containing IB connection details.
        """
        super().__init__(config)

        # IB-specific configuration
        self.ib_host = config.connection_params.get("host", "localhost")
        self.ib_port = config.connection_params.get("port", 7497)  # 7497 for paper
        self.client_id = config.connection_params.get("client_id", 1)
        self.account_id = config.connection_params.get("account_id", "")

        # IB API components
        self.wrapper = IBWrapper(self)
        self.client = IBClient(self.wrapper)
        self.api_thread = None
        self.next_order_id = None

        # Order tracking
        self.ib_to_client_orders: Dict[int, str] = {}  # IB orderId -> client order ID
        self.client_to_ib_orders: Dict[str, int] = {}  # client order ID -> IB orderId
        self.pending_orders: Dict[int, OrderInfo] = {}  # IB orderId -> OrderInfo

        # Market data subscriptions
        self.market_data_reqs: Dict[str, int] = {}  # symbol -> reqId
        self.req_id_counter = 10000  # Start high to avoid conflicts

        # Account data
        self.account_values: Dict[str, Dict[str, Any]] = {}
        self.positions: Dict[str, Dict[str, Any]] = {}

        logger.info("Initialized IB adapter for %s:%d", self.ib_host, self.ib_port)

    async def connect(self) -> bool:
        """Establish connection to IB Gateway/TWS.

        Returns:
            True if connection successful.
        """
        try:
            logger.info(
                "Connecting to IB Gateway/TWS at %s:%d", self.ib_host, self.ib_port
            )

            # Connect to IB
            self.client.connect(self.ib_host, self.ib_port, self.client_id)

            # Start API thread
            self.api_thread = threading.Thread(target=self._run_api_thread, daemon=True)
            self.api_thread.start()

            # Wait for connection
            await self._wait_for_connection(timeout=10)

            if self.connection.is_connected():
                logger.info("Successfully connected to IB Gateway/TWS")

                # Request initial data
                self._request_initial_data()

                return True
            else:
                logger.error("Failed to connect to IB Gateway/TWS")
                return False

        except Exception as e:
            logger.error("Error connecting to IB: %s", e)
            self._handle_error(e)
            return False

    async def disconnect(self) -> None:
        """Disconnect from IB Gateway/TWS."""
        try:
            if self.client.isConnected():
                self.client.disconnect()
                logger.info("Disconnected from IB Gateway/TWS")

            self._update_connection_status(ConnectionStatus.DISCONNECTED)

        except Exception as e:
            logger.error("Error disconnecting from IB: %s", e)

    async def authenticate(self) -> bool:
        """Authenticate with IB (handled by Gateway/TWS).

        Returns:
            True if authenticated.
        """
        # IB authentication is handled by the Gateway/TWS application
        if self.connection.is_connected():
            self._update_connection_status(ConnectionStatus.AUTHENTICATED)
            return True
        return False

    async def submit_order(self, order: NewOrderSingle) -> str:
        """Submit new order to IB.

        Args:
            order: FIX new order single message.

        Returns:
            Client order ID for tracking.
        """
        try:
            # Check connection
            if not self.connection.is_ready():
                raise ConnectionError("IB adapter not ready")

            # Check rate limits
            if not self._check_rate_limits("orders"):
                raise RuntimeError("Order rate limit exceeded")

            # Get next IB order ID
            ib_order_id = self._get_next_order_id()

            # Create IB contract
            contract = self._create_ib_contract(order)

            # Create IB order
            ib_order = self._create_ib_order(order)

            # Track order
            order_info = self._track_order(order)
            self.ib_to_client_orders[ib_order_id] = order.cl_ord_id
            self.client_to_ib_orders[order.cl_ord_id] = ib_order_id
            self.pending_orders[ib_order_id] = order_info

            # Submit to IB
            self.client.placeOrder(ib_order_id, contract, ib_order)

            logger.info("Submitted order to IB: %s -> %d", order.cl_ord_id, ib_order_id)

            return order.cl_ord_id

        except Exception as e:
            logger.error("Failed to submit order to IB: %s", e)
            self._handle_error(e)
            raise

    async def cancel_order(self, cancel_request: OrderCancelRequest) -> bool:
        """Cancel order in IB.

        Args:
            cancel_request: Order cancellation request.

        Returns:
            True if cancellation request accepted.
        """
        try:
            # Get IB order ID
            ib_order_id = self.client_to_ib_orders.get(cancel_request.orig_cl_ord_id)
            if ib_order_id is None:
                logger.warning(
                    "Order not found for cancellation: %s",
                    cancel_request.orig_cl_ord_id,
                )
                return False

            # Cancel with IB
            self.client.cancelOrder(ib_order_id)

            logger.info(
                "Cancelled order in IB: %s -> %d",
                cancel_request.orig_cl_ord_id,
                ib_order_id,
            )

            return True

        except Exception as e:
            logger.error("Failed to cancel order in IB: %s", e)
            self._handle_error(e)
            return False

    async def get_order_status(self, cl_ord_id: str) -> Optional[OrderInfo]:
        """Get status of specific order.

        Args:
            cl_ord_id: Client order ID.

        Returns:
            Order information or None if not found.
        """
        return self.active_orders.get(cl_ord_id)

    async def get_open_orders(self) -> List[OrderInfo]:
        """Get all open orders.

        Returns:
            List of open order information.
        """
        open_orders = []
        for order_info in self.active_orders.values():
            if order_info.status in [
                OrderStatus.PENDING,
                OrderStatus.SUBMITTED,
                OrderStatus.ACKNOWLEDGED,
                OrderStatus.WORKING,
                OrderStatus.PARTIALLY_FILLED,
            ]:
                open_orders.append(order_info)
        return open_orders

    async def send_heartbeat(self) -> bool:
        """Send heartbeat to maintain session.

        Returns:
            True if heartbeat sent successfully.
        """
        # IB connection is maintained automatically
        # Check if still connected
        if self.client.isConnected():
            self.last_heartbeat_sent = datetime.utcnow()
            return True
        return False

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information.

        Returns:
            Account information dictionary.
        """
        if not self.account_id:
            # Request account list
            self.client.reqManagedAccts()
            await asyncio.sleep(1)  # Wait for response

        # Request account summary
        req_id = self._get_next_req_id()
        self.client.reqAccountSummary(
            req_id,
            "All",
            "NetLiquidation,TotalCashValue,BuyingPower,GrossPositionValue",
        )

        # Wait for data
        await asyncio.sleep(2)

        return self.account_values.copy()

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions.

        Returns:
            List of position dictionaries.
        """
        # Request positions
        self.client.reqPositions()

        # Wait for data
        await asyncio.sleep(2)

        return list(self.positions.values())

    async def subscribe_market_data(self, symbols: List[str]) -> bool:
        """Subscribe to market data for symbols.

        Args:
            symbols: List of symbols to subscribe to.

        Returns:
            True if subscription successful.
        """
        try:
            for symbol in symbols:
                if symbol not in self.market_data_reqs:
                    req_id = self._get_next_req_id()
                    contract = self._create_contract_for_symbol(symbol)

                    # Request market data
                    self.client.reqMktData(req_id, contract, "", False, False, [])

                    self.market_data_reqs[symbol] = req_id
                    logger.info(
                        "Subscribed to market data for %s (reqId: %d)", symbol, req_id
                    )

            return True

        except Exception as e:
            logger.error("Failed to subscribe to market data: %s", e)
            return False

    async def unsubscribe_market_data(self, symbols: List[str]) -> bool:
        """Unsubscribe from market data.

        Args:
            symbols: List of symbols to unsubscribe from.

        Returns:
            True if unsubscription successful.
        """
        try:
            for symbol in symbols:
                req_id = self.market_data_reqs.get(symbol)
                if req_id:
                    self.client.cancelMktData(req_id)
                    del self.market_data_reqs[symbol]
                    logger.info("Unsubscribed from market data for %s", symbol)

            return True

        except Exception as e:
            logger.error("Failed to unsubscribe from market data: %s", e)
            return False

    # Helper methods

    def _run_api_thread(self) -> None:
        """Run IB API client thread."""
        try:
            self.client.run()
        except Exception as e:
            logger.error("Error in IB API thread: %s", e)
            self._handle_error(e)

    async def _wait_for_connection(self, timeout: int = 10) -> None:
        """Wait for connection to be established."""
        start_time = datetime.utcnow()
        while (datetime.utcnow() - start_time).seconds < timeout:
            if self.connection.status == ConnectionStatus.CONNECTED:
                return
            await asyncio.sleep(0.1)

    def _request_initial_data(self) -> None:
        """Request initial data after connection."""
        # Request managed accounts
        self.client.reqManagedAccts()

        # Request open orders
        self.client.reqOpenOrders()

        # Request positions
        self.client.reqPositions()

    def _get_next_order_id(self) -> int:
        """Get next valid order ID."""
        if self.next_order_id is None:
            raise RuntimeError("No valid order ID available")

        order_id = self.next_order_id
        self.next_order_id += 1
        return order_id

    def _get_next_req_id(self) -> int:
        """Get next request ID."""
        req_id = self.req_id_counter
        self.req_id_counter += 1
        return req_id

    def _create_ib_contract(self, order: NewOrderSingle) -> Contract:
        """Create IB contract from FIX order."""
        contract = Contract()

        # Parse symbol (assuming format like EURUSD)
        if len(order.symbol) == 6:
            # Forex pair
            contract.symbol = order.symbol[:3]
            contract.secType = "CASH"
            contract.currency = order.symbol[3:6]
            contract.exchange = "IDEALPRO"
        else:
            # Stock
            contract.symbol = order.symbol
            contract.secType = "STK"
            contract.currency = order.currency or "USD"
            contract.exchange = "SMART"

        return contract

    def _create_ib_order(self, order: NewOrderSingle) -> Order:
        """Create IB order from FIX order."""
        ib_order = Order()

        # Map side
        ib_order.action = "BUY" if order.side == Side.BUY else "SELL"

        # Map quantity
        ib_order.totalQuantity = int(order.order_qty) if order.order_qty else 0

        # Map order type
        if order.ord_type == OrdType.MARKET:
            ib_order.orderType = "MKT"
        elif order.ord_type == OrdType.LIMIT:
            ib_order.orderType = "LMT"
            ib_order.lmtPrice = float(order.price) if order.price else 0.0
        elif order.ord_type == OrdType.STOP:
            ib_order.orderType = "STP"
            ib_order.auxPrice = float(order.stop_px) if order.stop_px else 0.0
        elif order.ord_type == OrdType.STOP_LIMIT:
            ib_order.orderType = "STP LMT"
            ib_order.lmtPrice = float(order.price) if order.price else 0.0
            ib_order.auxPrice = float(order.stop_px) if order.stop_px else 0.0

        # Map time in force
        if order.time_in_force == TimeInForce.DAY:
            ib_order.tif = "DAY"
        elif order.time_in_force == TimeInForce.GOOD_TILL_CANCEL:
            ib_order.tif = "GTC"
        elif order.time_in_force == TimeInForce.IMMEDIATE_OR_CANCEL:
            ib_order.tif = "IOC"
        elif order.time_in_force == TimeInForce.FILL_OR_KILL:
            ib_order.tif = "FOK"

        # Set account if specified
        if self.account_id:
            ib_order.account = self.account_id

        return ib_order

    def _create_contract_for_symbol(self, symbol: str) -> Contract:
        """Create contract for market data subscription."""
        contract = Contract()

        if len(symbol) == 6 and symbol.isalpha():
            # Forex pair
            contract.symbol = symbol[:3]
            contract.secType = "CASH"
            contract.currency = symbol[3:6]
            contract.exchange = "IDEALPRO"
        else:
            # Stock
            contract.symbol = symbol
            contract.secType = "STK"
            contract.currency = "USD"
            contract.exchange = "SMART"

        return contract

    def _handle_open_order(
        self, orderId: int, contract: Contract, order: Order, orderState: OrderState
    ) -> None:
        """Handle open order callback."""
        client_order_id = self.ib_to_client_orders.get(orderId)
        if client_order_id:
            order_info = self.active_orders.get(client_order_id)
            if order_info:
                order_info.order_id = str(orderId)
                order_info.updated_at = datetime.utcnow()

    def _handle_order_status(
        self,
        orderId: int,
        status: str,
        filled: Decimal,
        remaining: Decimal,
        avgFillPrice: float,
    ) -> None:
        """Handle order status callback."""
        client_order_id = self.ib_to_client_orders.get(orderId)
        if not client_order_id:
            return

        order_info = self.active_orders.get(client_order_id)
        if not order_info:
            return

        # Map IB status to our status
        status_map = {
            "Submitted": OrderStatus.SUBMITTED,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "PendingSubmit": OrderStatus.PENDING,
            "PreSubmitted": OrderStatus.PENDING,
            "Inactive": OrderStatus.REJECTED,
        }

        new_status = status_map.get(status, OrderStatus.WORKING)
        order_info.status = new_status
        order_info.total_filled_qty = float(filled)
        order_info.remaining_qty = float(remaining)
        order_info.avg_fill_price = avgFillPrice
        order_info.updated_at = datetime.utcnow()

        # Create execution report
        self._create_execution_report(orderId, order_info, status, filled, avgFillPrice)

    def _handle_execution(
        self, reqId: int, contract: Contract, execution: Execution
    ) -> None:
        """Handle execution details callback."""
        client_order_id = self.ib_to_client_orders.get(execution.orderId)
        if not client_order_id:
            return

        order_info = self.active_orders.get(client_order_id)
        if not order_info:
            return

        # Create fill execution report
        exec_report = ExecutionReport(
            order_id=str(execution.orderId),
            cl_ord_id=client_order_id,
            exec_id=execution.execId,
            exec_type=ExecType.TRADE,
            ord_status=(
                OrdStatus.PARTIALLY_FILLED
                if order_info.remaining_qty > 0
                else OrdStatus.FILLED
            ),
            symbol=(
                order_info.original_order.symbol if order_info.original_order else ""
            ),
            side=(
                order_info.original_order.side
                if order_info.original_order
                else Side.BUY
            ),
            order_qty=(
                order_info.original_order.order_qty if order_info.original_order else 0
            ),
            last_qty=float(execution.shares),
            last_px=execution.price,
            leaves_qty=order_info.remaining_qty,
            cum_qty=order_info.total_filled_qty,
            avg_px=order_info.avg_fill_price,
            transact_time=datetime.utcnow(),
        )

        # Store and process
        order_info.fills.append(exec_report)
        order_info.last_execution = exec_report
        self._process_execution_report(exec_report)

    def _handle_order_rejection(
        self, reqId: int, errorCode: int, errorString: str
    ) -> None:
        """Handle order rejection."""
        order_info = self.pending_orders.get(reqId)
        if order_info:
            order_info.status = OrderStatus.REJECTED
            order_info.error_message = f"Error {errorCode}: {errorString}"

            # Create rejection execution report
            if order_info.original_order:
                exec_report = ExecutionReport(
                    order_id=str(reqId),
                    cl_ord_id=order_info.cl_ord_id,
                    exec_id=str(uuid.uuid4()),
                    exec_type=ExecType.REJECTED,
                    ord_status=OrdStatus.REJECTED,
                    symbol=order_info.original_order.symbol,
                    side=order_info.original_order.side,
                    order_qty=order_info.original_order.order_qty or 0,
                    ord_rej_reason=errorCode,
                    text=errorString,
                    transact_time=datetime.utcnow(),
                )

                self._process_execution_report(exec_report)

    def _create_execution_report(
        self,
        orderId: int,
        order_info: OrderInfo,
        status: str,
        filled: Decimal,
        avgFillPrice: float,
    ) -> None:
        """Create and send execution report."""
        if not order_info.original_order:
            return

        # Map status to execution type
        exec_type_map = {
            "Submitted": ExecType.NEW,
            "Filled": ExecType.TRADE,
            "Cancelled": ExecType.CANCELED,
            "PendingSubmit": ExecType.PENDING_NEW,
            "PreSubmitted": ExecType.PENDING_NEW,
        }

        exec_type = exec_type_map.get(status, ExecType.ORDER_STATUS)

        # Map status to order status
        ord_status_map = {
            "Submitted": OrdStatus.NEW,
            "Filled": OrdStatus.FILLED,
            "Cancelled": OrdStatus.CANCELED,
            "PendingSubmit": OrdStatus.PENDING_NEW,
            "PreSubmitted": OrdStatus.PENDING_NEW,
            "Inactive": OrdStatus.REJECTED,
        }

        ord_status = ord_status_map.get(status, OrdStatus.NEW)

        # Create execution report
        exec_report = ExecutionReport(
            order_id=str(orderId),
            cl_ord_id=order_info.cl_ord_id,
            exec_id=str(uuid.uuid4()),
            exec_type=exec_type,
            ord_status=ord_status,
            symbol=order_info.original_order.symbol,
            side=order_info.original_order.side,
            order_qty=order_info.original_order.order_qty or 0,
            last_qty=float(filled) if exec_type == ExecType.TRADE else None,
            last_px=avgFillPrice if exec_type == ExecType.TRADE else None,
            leaves_qty=order_info.remaining_qty,
            cum_qty=order_info.total_filled_qty,
            avg_px=avgFillPrice if avgFillPrice > 0 else None,
            transact_time=datetime.utcnow(),
        )

        # Store and process
        order_info.last_execution = exec_report
        self._process_execution_report(exec_report)

    def _handle_account_summary(
        self, reqId: int, account: str, tag: str, value: str, currency: str
    ) -> None:
        """Handle account summary callback."""
        if account not in self.account_values:
            self.account_values[account] = {}

        self.account_values[account][tag] = {"value": value, "currency": currency}

        # Update account ID if not set
        if not self.account_id:
            self.account_id = account

    def _handle_position(
        self, account: str, contract: Contract, position: Decimal, avgCost: float
    ) -> None:
        """Handle position callback."""
        symbol = (
            f"{contract.symbol}{contract.currency}"
            if contract.secType == "CASH"
            else contract.symbol
        )

        self.positions[symbol] = {
            "account": account,
            "symbol": symbol,
            "position": float(position),
            "avgCost": avgCost,
            "contract": contract,
        }

    def _handle_tick_price(self, reqId: int, tickType: int, price: float) -> None:
        """Handle tick price callback."""
        # Find symbol for this reqId
        symbol = None
        for sym, req_id in self.market_data_reqs.items():
            if req_id == reqId:
                symbol = sym
                break

        if symbol:
            # Process market data tick
            # tickType: 1=bid, 2=ask, 4=last
            logger.debug("Market data for %s: tick %d = %f", symbol, tickType, price)

    def _handle_tick_size(self, reqId: int, tickType: int, size: Decimal) -> None:
        """Handle tick size callback."""
        # Find symbol for this reqId
        symbol = None
        for sym, req_id in self.market_data_reqs.items():
            if req_id == reqId:
                symbol = sym
                break

        if symbol:
            # Process market data size
            # tickType: 0=bid size, 3=ask size, 5=last size
            logger.debug("Market size for %s: tick %d = %s", symbol, tickType, size)
