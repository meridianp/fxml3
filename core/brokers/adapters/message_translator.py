"""Message Translation Layer for FXML4-ForexConnect Integration.

This module handles bidirectional message translation between:
- FXML4 FIX-based messages
- ForexConnect RabbitMQ middleware messages

Ensures seamless communication while handling format conversions,
symbol mapping, quantity conversions, and status translations.
"""

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator

from ...core.logging import get_logger
from ...fix.messages.base import ExecType, OrdType, Side, TimeInForce
from ...fix.messages.orders import ExecutionReport as FIXExecutionReport
from ...fix.messages.orders import NewOrderSingle

logger = get_logger(__name__)


class SymbolMapper:
    """Handle symbol format conversion between FIX and ForexConnect formats."""

    # Major forex pairs mapping
    FIX_TO_FOREX = {
        "EURUSD": "EUR/USD",
        "GBPUSD": "GBP/USD",
        "USDJPY": "USD/JPY",
        "USDCHF": "USD/CHF",
        "AUDUSD": "AUD/USD",
        "USDCAD": "USD/CAD",
        "NZDUSD": "NZD/USD",
        "EURGBP": "EUR/GBP",
        "EURJPY": "EUR/JPY",
        "GBPJPY": "GBP/JPY",
        "EURCHF": "EUR/CHF",
        "EURAUD": "EUR/AUD",
        "EURCAD": "EUR/CAD",
        "GBPCHF": "GBP/CHF",
        "GBPAUD": "GBP/AUD",
        "AUDCAD": "AUD/CAD",
        "AUDJPY": "AUD/JPY",
        "AUDCHF": "AUD/CHF",
        "AUDNZD": "AUD/NZD",
        "CADCHF": "CAD/CHF",
        "CADJPY": "CAD/JPY",
        "CHFJPY": "CHF/JPY",
        "EURNZD": "EUR/NZD",
        "GBPNZD": "GBP/NZD",
        "NZDCAD": "NZD/CAD",
        "NZDCHF": "NZD/CHF",
        "NZDJPY": "NZD/JPY",
    }

    # Reverse mapping
    FOREX_TO_FIX = {v: k for k, v in FIX_TO_FOREX.items()}

    @classmethod
    def fix_to_forex(cls, fix_symbol: str) -> str:
        """Convert FIX symbol to ForexConnect format.

        Args:
            fix_symbol: FIX format symbol (e.g., 'EURUSD')

        Returns:
            ForexConnect format symbol (e.g., 'EUR/USD')
        """
        # Direct mapping
        if fix_symbol in cls.FIX_TO_FOREX:
            return cls.FIX_TO_FOREX[fix_symbol]

        # Auto-conversion for 6-character symbols
        if len(fix_symbol) == 6 and fix_symbol.isalpha():
            return f"{fix_symbol[:3]}/{fix_symbol[3:]}"

        # Return as-is for unknown formats
        logger.warning(f"Unknown FIX symbol format: {fix_symbol}")
        return fix_symbol

    @classmethod
    def forex_to_fix(cls, forex_symbol: str) -> str:
        """Convert ForexConnect symbol to FIX format.

        Args:
            forex_symbol: ForexConnect format symbol (e.g., 'EUR/USD')

        Returns:
            FIX format symbol (e.g., 'EURUSD')
        """
        # Direct mapping
        if forex_symbol in cls.FOREX_TO_FIX:
            return cls.FOREX_TO_FIX[forex_symbol]

        # Auto-conversion for slash-separated symbols
        if "/" in forex_symbol:
            return forex_symbol.replace("/", "")

        # Return as-is for unknown formats
        logger.warning(f"Unknown ForexConnect symbol format: {forex_symbol}")
        return forex_symbol


class QuantityConverter:
    """Handle quantity conversion between units and lots."""

    # Standard lot sizes for major pairs
    LOT_SIZES = {
        "EURUSD": 100000,
        "GBPUSD": 100000,
        "USDJPY": 100000,
        "USDCHF": 100000,
        "AUDUSD": 100000,
        "USDCAD": 100000,
        "NZDUSD": 100000,
        "EURGBP": 100000,
        "EURJPY": 100000,
        "GBPJPY": 100000,
        "EURCHF": 100000,
        "EURAUD": 100000,
        "EURCAD": 100000,
    }

    DEFAULT_LOT_SIZE = 100000

    @classmethod
    def units_to_lots(cls, units: Union[int, float], symbol: str = None) -> int:
        """Convert units to lots.

        Args:
            units: Amount in units
            symbol: Trading symbol (for lot size lookup)

        Returns:
            Amount in lots
        """
        lot_size = (
            cls.LOT_SIZES.get(symbol, cls.DEFAULT_LOT_SIZE)
            if symbol
            else cls.DEFAULT_LOT_SIZE
        )
        lots = int(units / lot_size)

        if lots * lot_size != units:
            logger.warning(
                f"Unit conversion not exact: {units} units = {lots} lots "
                f"({lots * lot_size} units with lot size {lot_size})"
            )

        return max(1, lots)  # Minimum 1 lot

    @classmethod
    def lots_to_units(cls, lots: Union[int, float], symbol: str = None) -> int:
        """Convert lots to units.

        Args:
            lots: Amount in lots
            symbol: Trading symbol (for lot size lookup)

        Returns:
            Amount in units
        """
        lot_size = (
            cls.LOT_SIZES.get(symbol, cls.DEFAULT_LOT_SIZE)
            if symbol
            else cls.DEFAULT_LOT_SIZE
        )
        return int(lots * lot_size)


class OrderTypeConverter:
    """Handle order type conversion between FIX and ForexConnect."""

    FIX_TO_FOREX = {
        OrdType.MARKET: "market",
        OrdType.LIMIT: "limit",
        OrdType.STOP: "stop",
        OrdType.STOP_LIMIT: "stop_limit",
    }

    FOREX_TO_FIX = {v: k for k, v in FIX_TO_FOREX.items()}

    @classmethod
    def fix_to_forex(cls, fix_type: OrdType) -> str:
        """Convert FIX order type to ForexConnect format."""
        return cls.FIX_TO_FOREX.get(fix_type, "market")

    @classmethod
    def forex_to_fix(cls, forex_type: str) -> OrdType:
        """Convert ForexConnect order type to FIX format."""
        return cls.FOREX_TO_FIX.get(forex_type.lower(), OrdType.MARKET)


class StatusConverter:
    """Handle status conversion between FIX and ForexConnect."""

    FOREX_TO_FIX = {
        "waiting": ExecType.PENDING_NEW,
        "inprocess": ExecType.PENDING_NEW,
        "executing": ExecType.NEW,
        "executed": ExecType.TRADE,
        "partially_filled": ExecType.PARTIAL_FILL,
        "canceled": ExecType.CANCELED,
        "cancelled": ExecType.CANCELED,  # Alternative spelling
        "rejected": ExecType.REJECTED,
        "expired": ExecType.EXPIRED,
    }

    FIX_TO_FOREX = {v: k for k, v in FOREX_TO_FIX.items()}

    @classmethod
    def forex_to_fix(cls, forex_status: str) -> ExecType:
        """Convert ForexConnect status to FIX execution type."""
        return cls.FOREX_TO_FIX.get(forex_status.lower(), ExecType.REJECTED)

    @classmethod
    def fix_to_forex(cls, fix_status: ExecType) -> str:
        """Convert FIX execution type to ForexConnect status."""
        return cls.FIX_TO_FOREX.get(fix_status, "rejected")


class TimeInForceConverter:
    """Handle time-in-force conversion."""

    FIX_TO_FOREX = {
        TimeInForce.DAY: "DAY",
        TimeInForce.GTC: "GTC",
        TimeInForce.IOC: "IOC",
        TimeInForce.FOK: "FOK",
    }

    FOREX_TO_FIX = {v: k for k, v in FIX_TO_FOREX.items()}

    @classmethod
    def fix_to_forex(cls, fix_tif: TimeInForce) -> str:
        """Convert FIX time in force to ForexConnect format."""
        return cls.FIX_TO_FOREX.get(fix_tif, "IOC")

    @classmethod
    def forex_to_fix(cls, forex_tif: str) -> TimeInForce:
        """Convert ForexConnect time in force to FIX format."""
        return cls.FOREX_TO_FIX.get(forex_tif.upper(), TimeInForce.IOC)


class FXMLToForexTranslator:
    """Translate FXML4 messages to ForexConnect format."""

    def __init__(self):
        self.symbol_mapper = SymbolMapper()
        self.quantity_converter = QuantityConverter()
        self.order_type_converter = OrderTypeConverter()
        self.tif_converter = TimeInForceConverter()

    def translate_new_order(self, fix_order: NewOrderSingle) -> Dict[str, Any]:
        """Translate FIX NewOrderSingle to ForexConnect order request.

        Args:
            fix_order: FIX order message

        Returns:
            ForexConnect order dictionary
        """
        try:
            # Convert symbol
            forex_symbol = self.symbol_mapper.fix_to_forex(fix_order.symbol)

            # Convert quantities
            forex_amount = int(fix_order.order_qty)  # Keep in units for now

            # Convert order type
            forex_order_type = self.order_type_converter.fix_to_forex(
                fix_order.ord_type
            )

            # Convert side
            forex_side = "buy" if fix_order.side == Side.BUY else "sell"

            # Convert time in force
            forex_tif = self.tif_converter.fix_to_forex(
                getattr(fix_order, "time_in_force", TimeInForce.IOC)
            )

            # Build ForexConnect order
            forex_order = {
                "type": "order_request",
                "request_id": str(uuid.uuid4()),
                "correlation_id": fix_order.cl_ord_id,
                "order_type": forex_order_type,
                "instrument": forex_symbol,
                "side": forex_side,
                "amount": forex_amount,
                "time_in_force": forex_tif,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Add price for limit/stop orders
            if hasattr(fix_order, "price") and fix_order.price:
                forex_order["rate"] = float(fix_order.price)

            # Add stop price for stop orders
            if hasattr(fix_order, "stop_px") and fix_order.stop_px:
                forex_order["stop_rate"] = float(fix_order.stop_px)

            # Add account if specified
            if hasattr(fix_order, "account") and fix_order.account:
                forex_order["account_id"] = fix_order.account

            logger.debug(
                f"Translated FIX order {fix_order.cl_ord_id} to ForexConnect format"
            )
            return forex_order

        except Exception as e:
            logger.error(f"Failed to translate FIX order: {e}")
            raise ValueError(f"Order translation failed: {e}")

    def translate_cancel_request(
        self, order_id: str, orig_cl_ord_id: str
    ) -> Dict[str, Any]:
        """Translate FIX cancel request to ForexConnect format.

        Args:
            order_id: Order ID to cancel
            orig_cl_ord_id: Original client order ID

        Returns:
            ForexConnect cancel request dictionary
        """
        return {
            "type": "cancel_request",
            "request_id": str(uuid.uuid4()),
            "correlation_id": str(uuid.uuid4()),
            "order_id": order_id,
            "original_cl_ord_id": orig_cl_ord_id,
            "timestamp": datetime.utcnow().isoformat(),
        }


class ForexToFXMLTranslator:
    """Translate ForexConnect messages to FXML4 format."""

    def __init__(self):
        self.symbol_mapper = SymbolMapper()
        self.quantity_converter = QuantityConverter()
        self.status_converter = StatusConverter()

    def translate_execution_report(
        self,
        forex_response: Dict[str, Any],
        original_order: Optional[NewOrderSingle] = None,
    ) -> Dict[str, Any]:
        """Translate ForexConnect response to FIX execution report.

        Args:
            forex_response: ForexConnect response message
            original_order: Original FIX order for reference

        Returns:
            FIX execution report dictionary
        """
        try:
            # Extract key fields
            correlation_id = forex_response.get("correlation_id", "")
            forex_status = forex_response.get("status", "rejected")
            forex_symbol = forex_response.get("instrument", "")

            # Convert symbol back to FIX format
            fix_symbol = self.symbol_mapper.forex_to_fix(forex_symbol)

            # Convert status
            exec_type = self.status_converter.forex_to_fix(forex_status)
            ord_status = exec_type  # In most cases, these are the same

            # Handle quantities
            executed_amount = forex_response.get("amount", 0) or 0
            order_qty = original_order.order_qty if original_order else executed_amount
            cum_qty = executed_amount
            leaves_qty = max(0, order_qty - cum_qty)

            # Handle prices
            exec_price = forex_response.get("rate", 0.0) or 0.0

            # Build execution report
            exec_report = {
                "order_id": forex_response.get("order_id", ""),
                "cl_ord_id": correlation_id,
                "exec_id": str(uuid.uuid4()),
                "exec_type": exec_type,
                "ord_status": ord_status,
                "symbol": fix_symbol,
                "side": original_order.side if original_order else Side.BUY,
                "order_qty": order_qty,
                "cum_qty": cum_qty,
                "leaves_qty": leaves_qty,
                "avg_px": exec_price,
                "last_px": exec_price,
                "last_qty": executed_amount,
                "transact_time": forex_response.get(
                    "timestamp", datetime.utcnow().isoformat()
                ),
                "text": forex_response.get("message", ""),
            }

            # Add error information if present
            if forex_response.get("error"):
                exec_report["text"] = forex_response["error"]
                exec_report["ord_status"] = ExecType.REJECTED
                exec_report["exec_type"] = ExecType.REJECTED

            logger.debug(
                f"Translated ForexConnect response to FIX execution report: {correlation_id}"
            )
            return exec_report

        except Exception as e:
            logger.error(f"Failed to translate ForexConnect response: {e}")
            raise ValueError(f"Response translation failed: {e}")

    def translate_market_data(self, forex_data: Dict[str, Any]) -> Dict[str, Any]:
        """Translate ForexConnect market data to FXML4 format.

        Args:
            forex_data: ForexConnect market data message

        Returns:
            FXML4 market data dictionary
        """
        try:
            # Convert symbol
            forex_symbol = forex_data.get("instrument", "")
            fix_symbol = self.symbol_mapper.forex_to_fix(forex_symbol)

            # Build market data update
            market_data = {
                "symbol": fix_symbol,
                "bid_price": forex_data.get("bid", 0.0),
                "ask_price": forex_data.get("ask", 0.0),
                "timestamp": forex_data.get("timestamp", datetime.utcnow().isoformat()),
                "source": "fxcm_forexconnect",
            }

            # Add optional fields
            if "digits" in forex_data:
                market_data["precision"] = forex_data["digits"]

            if "spread" in forex_data:
                market_data["spread"] = forex_data["spread"]

            logger.debug(f"Translated ForexConnect market data for {fix_symbol}")
            return market_data

        except Exception as e:
            logger.error(f"Failed to translate market data: {e}")
            raise ValueError(f"Market data translation failed: {e}")


class MessageTranslator:
    """Main translator class combining both directions."""

    def __init__(self):
        self.fxml_to_forex = FXMLToForexTranslator()
        self.forex_to_fxml = ForexToFXMLTranslator()

        logger.info("Message translator initialized")

    def translate_order_to_forex(self, fix_order: NewOrderSingle) -> Dict[str, Any]:
        """Translate FXML4 order to ForexConnect format."""
        return self.fxml_to_forex.translate_new_order(fix_order)

    def translate_cancel_to_forex(
        self, order_id: str, orig_cl_ord_id: str
    ) -> Dict[str, Any]:
        """Translate FXML4 cancel to ForexConnect format."""
        return self.fxml_to_forex.translate_cancel_request(order_id, orig_cl_ord_id)

    def translate_response_to_fxml(
        self,
        forex_response: Dict[str, Any],
        original_order: Optional[NewOrderSingle] = None,
    ) -> Dict[str, Any]:
        """Translate ForexConnect response to FXML4 format."""
        return self.forex_to_fxml.translate_execution_report(
            forex_response, original_order
        )

    def translate_market_data_to_fxml(
        self, forex_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Translate ForexConnect market data to FXML4 format."""
        return self.forex_to_fxml.translate_market_data(forex_data)

    def validate_translation(
        self, original: Dict[str, Any], translated: Dict[str, Any], direction: str
    ) -> bool:
        """Validate translation accuracy.

        Args:
            original: Original message
            translated: Translated message
            direction: Translation direction ('fxml_to_forex' or 'forex_to_fxml')

        Returns:
            True if translation is valid
        """
        try:
            if direction == "fxml_to_forex":
                # Validate key fields are preserved
                required_fields = ["correlation_id", "instrument", "side", "amount"]
                return all(field in translated for field in required_fields)

            elif direction == "forex_to_fxml":
                # Validate execution report fields
                required_fields = ["cl_ord_id", "exec_type", "ord_status", "symbol"]
                return all(field in translated for field in required_fields)

            return False

        except Exception as e:
            logger.error(f"Translation validation failed: {e}")
            return False


# Singleton instance
_translator = None


def get_message_translator() -> MessageTranslator:
    """Get singleton message translator instance."""
    global _translator
    if _translator is None:
        _translator = MessageTranslator()
    return _translator


if __name__ == "__main__":
    """Test translation functions."""

    # Test symbol mapping
    print("Symbol Mapping Tests:")
    print(f"EURUSD -> {SymbolMapper.fix_to_forex('EURUSD')}")
    print(f"EUR/USD -> {SymbolMapper.forex_to_fix('EUR/USD')}")

    # Test quantity conversion
    print("\nQuantity Conversion Tests:")
    print(f"100000 units -> {QuantityConverter.units_to_lots(100000)} lots")
    print(f"1 lot -> {QuantityConverter.lots_to_units(1)} units")

    # Test message translation
    print("\nMessage Translation Tests:")
    translator = get_message_translator()

    # Create sample FIX order
    sample_order = NewOrderSingle(
        cl_ord_id="TEST001",
        symbol="EURUSD",
        side=Side.BUY,
        order_qty=100000,
        ord_type=OrdType.MARKET,
    )

    # Translate to ForexConnect
    forex_order = translator.translate_order_to_forex(sample_order)
    print(f"FIX -> ForexConnect: {json.dumps(forex_order, indent=2)}")

    # Create sample ForexConnect response
    forex_response = {
        "type": "order_response",
        "correlation_id": "TEST001",
        "status": "executed",
        "instrument": "EUR/USD",
        "amount": 100000,
        "rate": 1.1234,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Translate to FXML4
    fxml_report = translator.translate_response_to_fxml(forex_response, sample_order)
    print(f"\nForexConnect -> FXML4: {json.dumps(fxml_report, indent=2, default=str)}")
