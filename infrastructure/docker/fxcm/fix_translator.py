"""FIX to ForexConnect message translation for FXCM.

This module handles translation between FIX protocol messages
and ForexConnect API calls/responses.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Tuple

# Note: In actual implementation, these would come from forexconnect
# For now, we'll define the expected structures

logger = logging.getLogger(__name__)


class ForexConnectOrderType:
    """ForexConnect order types."""

    MARKET = "M"
    LIMIT = "L"
    STOP = "S"
    STOP_LIMIT = "SL"
    CLOSE = "C"
    CLOSE_LIMIT = "CL"


class ForexConnectSide:
    """ForexConnect buy/sell sides."""

    BUY = "B"
    SELL = "S"


class ForexConnectTimeInForce:
    """ForexConnect time in force values."""

    IOC = "IOC"  # Immediate or Cancel
    GTC = "GTC"  # Good Till Cancelled
    FOK = "FOK"  # Fill or Kill
    DAY = "DAY"  # Day order


class FXCMFIXTranslator:
    """Translator between FIX messages and ForexConnect API."""

    # Map FIX order types to ForexConnect
    ORDER_TYPE_MAP = {
        "1": ForexConnectOrderType.MARKET,  # Market
        "2": ForexConnectOrderType.LIMIT,  # Limit
        "3": ForexConnectOrderType.STOP,  # Stop
        "4": ForexConnectOrderType.STOP_LIMIT,  # Stop Limit
    }

    # Map FIX side to ForexConnect
    SIDE_MAP = {
        "1": ForexConnectSide.BUY,  # Buy
        "2": ForexConnectSide.SELL,  # Sell
    }

    # Map FIX TimeInForce to ForexConnect
    TIF_MAP = {
        "0": ForexConnectTimeInForce.DAY,  # Day
        "1": ForexConnectTimeInForce.GTC,  # Good Till Cancel
        "3": ForexConnectTimeInForce.IOC,  # Immediate or Cancel
        "4": ForexConnectTimeInForce.FOK,  # Fill or Kill
    }

    # Map ForexConnect status to FIX OrdStatus
    STATUS_TO_FIX = {
        "Waiting": "A",  # Pending New
        "InProcess": "A",  # Pending New
        "Executing": "0",  # New
        "Executed": "2",  # Filled
        "Canceled": "4",  # Canceled
        "Rejected": "8",  # Rejected
        "Expired": "C",  # Expired
    }

    # Map ForexConnect status to FIX ExecType
    STATUS_TO_EXEC_TYPE = {
        "Waiting": "A",  # Pending New
        "InProcess": "A",  # Pending New
        "Executing": "0",  # New
        "Executed": "F",  # Trade
        "Canceled": "4",  # Canceled
        "Rejected": "8",  # Rejected
        "Expired": "C",  # Expired
    }

    @staticmethod
    def parse_fix_order(fix_message: str) -> Dict[str, Any]:
        """Parse FIX message into order parameters.

        Args:
            fix_message: FIX format message string.

        Returns:
            Dictionary with parsed order fields.
        """
        fields = {}

        # Parse FIX message (simplified - in production use proper FIX parser)
        for field in fix_message.split("|"):
            if "=" in field:
                tag, value = field.split("=", 1)
                fields[tag] = value

        return fields

    @staticmethod
    def fix_to_forexconnect_order(fix_fields: Dict[str, str]) -> Dict[str, Any]:
        """Convert FIX order to ForexConnect parameters.

        Args:
            fix_fields: Parsed FIX message fields.

        Returns:
            ForexConnect order parameters.
        """
        # Extract FIX fields
        symbol = fix_fields.get("55", "")  # Symbol
        side = fix_fields.get("54", "")  # Side
        qty = float(fix_fields.get("38", "0"))  # OrderQty
        ord_type = fix_fields.get("40", "")  # OrdType
        price = float(fix_fields.get("44", "0"))  # Price
        stop_px = float(fix_fields.get("99", "0"))  # StopPx
        tif = fix_fields.get("59", "0")  # TimeInForce
        cl_ord_id = fix_fields.get("11", "")  # ClOrdID

        # Map to ForexConnect format
        fc_order = {
            "instrument": FXCMFIXTranslator._normalize_symbol(symbol),
            "side": FXCMFIXTranslator.SIDE_MAP.get(side, ForexConnectSide.BUY),
            "order_type": FXCMFIXTranslator.ORDER_TYPE_MAP.get(
                ord_type, ForexConnectOrderType.MARKET
            ),
            "amount": int(qty / 1000),  # ForexConnect uses lots (1000 units)
            "time_in_force": FXCMFIXTranslator.TIF_MAP.get(
                tif, ForexConnectTimeInForce.GTC
            ),
            "custom_id": cl_ord_id,
        }

        # Add price for limit orders
        if ord_type in ["2", "4"]:  # Limit or Stop Limit
            fc_order["rate"] = price

        # Add stop price for stop orders
        if ord_type in ["3", "4"]:  # Stop or Stop Limit
            fc_order["stop"] = stop_px

        return fc_order

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize symbol for ForexConnect.

        Args:
            symbol: FIX symbol (e.g., EURUSD).

        Returns:
            ForexConnect symbol format (e.g., EUR/USD).
        """
        if len(symbol) == 6:
            # Forex pair - add slash
            return f"{symbol[:3]}/{symbol[3:]}"
        return symbol

    @staticmethod
    def forexconnect_to_fix_execution_report(
        fc_order: Dict[str, Any], fc_trade: Dict[str, Any], cl_ord_id: str
    ) -> str:
        """Convert ForexConnect trade to FIX ExecutionReport.

        Args:
            fc_order: ForexConnect order data.
            fc_trade: ForexConnect trade/execution data.
            cl_ord_id: Client order ID.

        Returns:
            FIX execution report message.
        """
        # Extract data
        order_id = fc_trade.get("order_id", "")
        trade_id = fc_trade.get("trade_id", "")
        status = fc_trade.get("status", "Executing")
        symbol = fc_trade.get("instrument", "").replace("/", "")
        side = "1" if fc_trade.get("side", "") == ForexConnectSide.BUY else "2"
        qty = fc_trade.get("amount", 0) * 1000  # Convert lots to units
        price = fc_trade.get("rate", 0)
        filled_qty = fc_trade.get("filled_amount", 0) * 1000
        avg_px = fc_trade.get("avg_rate", price)

        # Get FIX status codes
        ord_status = FXCMFIXTranslator.STATUS_TO_FIX.get(status, "0")
        exec_type = FXCMFIXTranslator.STATUS_TO_EXEC_TYPE.get(status, "0")

        # Build FIX message
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]

        fix_fields = [
            "8=FIX.4.4",
            "35=8",  # ExecutionReport
            "49=FXCM",
            "56=FXML4",
            f"34=1",
            f"52={timestamp}",
            f"37={order_id}",  # OrderID
            f"17={trade_id}",  # ExecID
            f"150={exec_type}",  # ExecType
            f"39={ord_status}",  # OrdStatus
            f"55={symbol}",  # Symbol
            f"54={side}",  # Side
            f"38={qty}",  # OrderQty
            f"44={price}",  # Price
            f"6={avg_px}",  # AvgPx
            f"14={filled_qty}",  # CumQty
            f"151={qty - filled_qty}",  # LeavesQty
            f"11={cl_ord_id}",  # ClOrdID
            f"60={timestamp}",  # TransactTime
        ]

        # Add rejection reason if rejected
        if status == "Rejected":
            reason = fc_trade.get("reject_reason", "Unknown")
            fix_fields.append(f"58={reason}")  # Text

        # Calculate checksum (simplified)
        body = "|".join(fix_fields) + "|"
        checksum = sum(ord(c) for c in body) % 256
        fix_fields.append(f"10={checksum:03d}")

        return "|".join(fix_fields)

    @staticmethod
    def forexconnect_to_fix_market_data(fc_data: Dict[str, Any]) -> str:
        """Convert ForexConnect market data to FIX format.

        Args:
            fc_data: ForexConnect market data.

        Returns:
            FIX market data snapshot message.
        """
        symbol = fc_data.get("instrument", "").replace("/", "")
        bid = fc_data.get("bid", 0)
        ask = fc_data.get("ask", 0)
        bid_size = fc_data.get("bid_size", 0) * 1000
        ask_size = fc_data.get("ask_size", 0) * 1000

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]

        fix_fields = [
            "8=FIX.4.4",
            "35=W",  # MarketDataSnapshotFullRefresh
            "49=FXCM",
            "56=FXML4",
            f"34=1",
            f"52={timestamp}",
            f"55={symbol}",  # Symbol
            f"262=FXCM_{symbol}",  # MDReqID
            "268=2",  # NoMDEntries
            # Bid entry
            "269=0",  # MDEntryType (Bid)
            f"270={bid}",  # MDEntryPx
            f"271={bid_size}",  # MDEntrySize
            # Ask entry
            "269=1",  # MDEntryType (Offer)
            f"270={ask}",  # MDEntryPx
            f"271={ask_size}",  # MDEntrySize
        ]

        body = "|".join(fix_fields) + "|"
        checksum = sum(ord(c) for c in body) % 256
        fix_fields.append(f"10={checksum:03d}")

        return "|".join(fix_fields)

    @staticmethod
    def parse_forexconnect_error(error: Any) -> Tuple[int, str]:
        """Parse ForexConnect error into code and message.

        Args:
            error: ForexConnect error object or string.

        Returns:
            Tuple of (error_code, error_message).
        """
        if isinstance(error, str):
            return 0, error

        # Handle ForexConnect error object
        error_code = getattr(error, "code", 0)
        error_msg = str(error)

        return error_code, error_msg

    @staticmethod
    def normalize_forexconnect_symbol(fc_symbol: str) -> str:
        """Normalize ForexConnect symbol to FIX format.

        Args:
            fc_symbol: ForexConnect symbol (e.g., EUR/USD).

        Returns:
            FIX symbol format (e.g., EURUSD).
        """
        return fc_symbol.replace("/", "")
