"""FIX to IB Message Translation.

This module provides translation between FIX protocol messages and
Interactive Brokers API objects, handling the mapping of fields,
statuses, and execution types.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from ibapi.contract import Contract
from ibapi.execution import Execution
from ibapi.order import Order

from ...fix.messages.base import ExecType, OrdStatus, OrdType, Side, TimeInForce
from ...fix.messages.orders import ExecutionReport, NewOrderSingle, OrderCancelRequest

logger = logging.getLogger(__name__)


class IBFIXTranslator:
    """Translator between FIX messages and IB API objects."""

    # Symbol mappings for common forex pairs
    FOREX_SYMBOLS = {
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "USDCHF",
        "AUDUSD",
        "USDCAD",
        "NZDUSD",
        "EURJPY",
        "GBPJPY",
        "EURGBP",
    }

    @staticmethod
    def fix_to_ib_contract(order: NewOrderSingle) -> Contract:
        """Convert FIX order to IB contract.

        Args:
            order: FIX new order single message.

        Returns:
            IB Contract object.
        """
        contract = Contract()

        symbol = order.symbol.upper()

        # Determine security type based on symbol
        if symbol in IBFIXTranslator.FOREX_SYMBOLS or len(symbol) == 6:
            # Forex pair
            contract.symbol = symbol[:3]
            contract.secType = "CASH"
            contract.currency = symbol[3:6]
            contract.exchange = "IDEALPRO"
        else:
            # Stock/ETF
            contract.symbol = symbol
            contract.secType = "STK"
            contract.currency = getattr(order, "currency", "USD")
            contract.exchange = "SMART"

            # Check for primary exchange if specified
            if hasattr(order, "exchange"):
                contract.primaryExchange = order.exchange

        logger.debug(
            "Created IB contract: %s %s on %s",
            contract.symbol,
            contract.secType,
            contract.exchange,
        )

        return contract

    @staticmethod
    def fix_to_ib_order(order: NewOrderSingle, account: Optional[str] = None) -> Order:
        """Convert FIX order to IB order.

        Args:
            order: FIX new order single message.
            account: IB account ID if specified.

        Returns:
            IB Order object.
        """
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
        elif order.ord_type == OrdType.MARKET_ON_CLOSE:
            ib_order.orderType = "MOC"
        elif order.ord_type == OrdType.LIMIT_ON_CLOSE:
            ib_order.orderType = "LOC"
            ib_order.lmtPrice = float(order.price) if order.price else 0.0
        else:
            # Default to market
            ib_order.orderType = "MKT"
            logger.warning("Unmapped order type %s, defaulting to MKT", order.ord_type)

        # Map time in force
        tif_map = {
            TimeInForce.DAY: "DAY",
            TimeInForce.GOOD_TILL_CANCEL: "GTC",
            TimeInForce.IMMEDIATE_OR_CANCEL: "IOC",
            TimeInForce.FILL_OR_KILL: "FOK",
            TimeInForce.AT_THE_OPENING: "OPG",
            TimeInForce.GOOD_TILL_DATE: "GTD",
        }

        ib_order.tif = tif_map.get(order.time_in_force, "GTC")

        # Set account if provided
        if account:
            ib_order.account = account

        # Additional order attributes
        if hasattr(order, "min_qty"):
            ib_order.minQty = int(order.min_qty)

        if hasattr(order, "display_qty"):
            ib_order.displaySize = int(order.display_qty)

        # Set good after time if specified
        if hasattr(order, "good_after_time"):
            ib_order.goodAfterTime = order.good_after_time.strftime("%Y%m%d %H:%M:%S")

        # Set good till date if GTD
        if order.time_in_force == TimeInForce.GOOD_TILL_DATE and hasattr(
            order, "expire_time"
        ):
            ib_order.goodTillDate = order.expire_time.strftime("%Y%m%d %H:%M:%S")

        logger.debug(
            "Created IB order: %s %s %s @ %s",
            ib_order.action,
            ib_order.totalQuantity,
            ib_order.orderType,
            ib_order.lmtPrice,
        )

        return ib_order

    @staticmethod
    def ib_status_to_fix(ib_status: str) -> OrdStatus:
        """Convert IB order status to FIX order status.

        Args:
            ib_status: IB order status string.

        Returns:
            FIX order status enum.
        """
        status_map = {
            "PendingSubmit": OrdStatus.PENDING_NEW,
            "PendingCancel": OrdStatus.PENDING_CANCEL,
            "PreSubmitted": OrdStatus.PENDING_NEW,
            "Submitted": OrdStatus.NEW,
            "ApiPending": OrdStatus.PENDING_NEW,
            "ApiCancelled": OrdStatus.CANCELED,
            "Cancelled": OrdStatus.CANCELED,
            "Filled": OrdStatus.FILLED,
            "Inactive": OrdStatus.REJECTED,
            "PartiallyFilled": OrdStatus.PARTIALLY_FILLED,
            "Unknown": OrdStatus.REJECTED,
        }

        return status_map.get(ib_status, OrdStatus.NEW)

    @staticmethod
    def ib_status_to_exec_type(ib_status: str) -> ExecType:
        """Convert IB order status to FIX execution type.

        Args:
            ib_status: IB order status string.

        Returns:
            FIX execution type enum.
        """
        exec_type_map = {
            "PendingSubmit": ExecType.PENDING_NEW,
            "PendingCancel": ExecType.PENDING_CANCEL,
            "PreSubmitted": ExecType.PENDING_NEW,
            "Submitted": ExecType.NEW,
            "ApiPending": ExecType.PENDING_NEW,
            "ApiCancelled": ExecType.CANCELED,
            "Cancelled": ExecType.CANCELED,
            "Filled": ExecType.TRADE,
            "Inactive": ExecType.REJECTED,
            "PartiallyFilled": ExecType.TRADE,
            "Unknown": ExecType.REJECTED,
        }

        return exec_type_map.get(ib_status, ExecType.ORDER_STATUS)

    @staticmethod
    def create_execution_report(
        ib_order_id: int,
        client_order_id: str,
        ib_contract: Contract,
        ib_order: Order,
        ib_status: str,
        filled: float = 0,
        remaining: float = 0,
        avg_fill_price: float = 0,
        last_fill_qty: Optional[float] = None,
        last_fill_price: Optional[float] = None,
        exec_id: Optional[str] = None,
        error_code: Optional[int] = None,
        error_msg: Optional[str] = None,
    ) -> ExecutionReport:
        """Create FIX execution report from IB data.

        Args:
            ib_order_id: IB order ID.
            client_order_id: Client order ID.
            ib_contract: IB contract.
            ib_order: IB order.
            ib_status: IB order status.
            filled: Filled quantity.
            remaining: Remaining quantity.
            avg_fill_price: Average fill price.
            last_fill_qty: Last fill quantity (for trades).
            last_fill_price: Last fill price (for trades).
            exec_id: Execution ID.
            error_code: Error code (for rejections).
            error_msg: Error message (for rejections).

        Returns:
            FIX ExecutionReport message.
        """
        # Reconstruct symbol
        if ib_contract.secType == "CASH":
            symbol = f"{ib_contract.symbol}{ib_contract.currency}"
        else:
            symbol = ib_contract.symbol

        # Map side
        side = Side.BUY if ib_order.action == "BUY" else Side.SELL

        # Map statuses
        ord_status = IBFIXTranslator.ib_status_to_fix(ib_status)
        exec_type = IBFIXTranslator.ib_status_to_exec_type(ib_status)

        # Create execution report
        exec_report = ExecutionReport(
            order_id=str(ib_order_id),
            cl_ord_id=client_order_id,
            exec_id=exec_id or f"IB_{ib_order_id}_{datetime.utcnow().timestamp()}",
            exec_type=exec_type,
            ord_status=ord_status,
            symbol=symbol,
            side=side,
            order_qty=float(ib_order.totalQuantity),
            transact_time=datetime.utcnow(),
        )

        # Add fill information
        if filled > 0:
            exec_report.cum_qty = filled
            exec_report.leaves_qty = remaining

            if avg_fill_price > 0:
                exec_report.avg_px = avg_fill_price

            if last_fill_qty is not None:
                exec_report.last_qty = last_fill_qty

            if last_fill_price is not None:
                exec_report.last_px = last_fill_price

        # Add price information
        if ib_order.orderType in ["LMT", "STP LMT", "LOC"]:
            exec_report.price = ib_order.lmtPrice

        if ib_order.orderType in ["STP", "STP LMT"]:
            exec_report.stop_px = ib_order.auxPrice

        # Add rejection information
        if ord_status == OrdStatus.REJECTED:
            if error_code:
                exec_report.ord_rej_reason = error_code
            if error_msg:
                exec_report.text = error_msg

        return exec_report

    @staticmethod
    def create_execution_report_from_ib_execution(
        execution: Execution,
        ib_contract: Contract,
        ib_order: Order,
        client_order_id: str,
        cum_qty: float,
        leaves_qty: float,
        avg_px: float,
    ) -> ExecutionReport:
        """Create FIX execution report from IB execution details.

        Args:
            execution: IB execution object.
            ib_contract: IB contract.
            ib_order: IB order.
            client_order_id: Client order ID.
            cum_qty: Cumulative quantity filled.
            leaves_qty: Remaining quantity.
            avg_px: Average fill price.

        Returns:
            FIX ExecutionReport message.
        """
        # Reconstruct symbol
        if ib_contract.secType == "CASH":
            symbol = f"{ib_contract.symbol}{ib_contract.currency}"
        else:
            symbol = ib_contract.symbol

        # Map side
        side = Side.BUY if execution.side == "BOT" else Side.SELL

        # Determine order status based on fills
        if leaves_qty == 0:
            ord_status = OrdStatus.FILLED
        else:
            ord_status = OrdStatus.PARTIALLY_FILLED

        # Create execution report
        exec_report = ExecutionReport(
            order_id=str(execution.orderId),
            cl_ord_id=client_order_id,
            exec_id=execution.execId,
            exec_type=ExecType.TRADE,
            ord_status=ord_status,
            symbol=symbol,
            side=side,
            order_qty=float(ib_order.totalQuantity),
            last_qty=float(execution.shares),
            last_px=execution.price,
            cum_qty=cum_qty,
            leaves_qty=leaves_qty,
            avg_px=avg_px,
            transact_time=datetime.utcnow(),
        )

        # Add execution time if available
        if hasattr(execution, "time"):
            try:
                exec_time = datetime.strptime(execution.time, "%Y%m%d  %H:%M:%S")
                exec_report.transact_time = exec_time
            except:
                pass

        return exec_report

    @staticmethod
    def parse_ib_error(error_code: int, error_string: str) -> Dict[str, Any]:
        """Parse IB error into structured format.

        Args:
            error_code: IB error code.
            error_string: IB error message.

        Returns:
            Dictionary with parsed error information.
        """
        # Common IB error codes
        error_types = {
            # Connection errors
            502: "connection_error",
            504: "connection_error",
            1100: "connection_lost",
            1101: "connection_restored",
            1102: "connection_restored",
            # Order errors
            103: "duplicate_order",
            104: "order_filled",
            105: "order_not_found",
            106: "order_cancelled",
            107: "order_not_transmittable",
            110: "price_violates_constraints",
            111: "size_violates_constraints",
            113: "invalid_trigger_price",
            # Market data errors
            200: "no_security_definition",
            201: "order_rejected",
            202: "order_cancelled",
            203: "security_not_available",
            # Account errors
            321: "account_validation_error",
            322: "account_code_mismatch",
            # System errors
            326: "client_id_in_use",
            327: "unable_to_bind_socket",
            # Position/margin errors
            399: "order_size_too_large",
            434: "margin_insufficient",
        }

        error_type = error_types.get(error_code, "unknown_error")

        # Determine if this is a critical error
        critical_errors = {502, 504, 1100, 326, 327}
        is_critical = error_code in critical_errors

        # Determine if this is an order rejection
        rejection_errors = {110, 111, 113, 200, 201, 399, 434}
        is_rejection = error_code in rejection_errors

        return {
            "code": error_code,
            "message": error_string,
            "type": error_type,
            "is_critical": is_critical,
            "is_rejection": is_rejection,
            "is_warning": not is_critical and not is_rejection,
        }

    @staticmethod
    def format_ib_symbol(symbol: str, sec_type: str = "STK") -> str:
        """Format symbol for IB API.

        Args:
            symbol: Input symbol.
            sec_type: Security type.

        Returns:
            Formatted symbol for IB.
        """
        symbol = symbol.upper()

        # Handle forex pairs
        if sec_type == "CASH" or symbol in IBFIXTranslator.FOREX_SYMBOLS:
            if len(symbol) == 6:
                return symbol[:3]  # Return base currency

        return symbol

    @staticmethod
    def calculate_order_commission(
        ib_order: Order,
        ib_contract: Contract,
        fill_price: float,
        exchange: str = "SMART",
    ) -> float:
        """Calculate estimated commission for IB order.

        Args:
            ib_order: IB order object.
            ib_contract: IB contract object.
            fill_price: Fill price.
            exchange: Exchange name.

        Returns:
            Estimated commission amount.
        """
        quantity = ib_order.totalQuantity

        # Simplified commission calculation
        if ib_contract.secType == "STK":
            # US stocks: $0.005 per share, min $1.00
            commission = max(1.00, quantity * 0.005)
        elif ib_contract.secType == "CASH":
            # Forex: 0.00002 * trade value, min $2.00
            trade_value = quantity * fill_price
            commission = max(2.00, trade_value * 0.00002)
        else:
            # Default
            commission = 1.00

        return commission
