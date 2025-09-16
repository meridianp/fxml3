"""FIX Order Management Messages.

This module implements concrete FIX messages for order lifecycle management,
including order creation, execution reports, and cancellation requests.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Union

from .base import (
    ExecType,
    FIXField,
    FIXMessage,
    FIXMessageType,
    OrdStatus,
    OrdType,
    Side,
    TimeInForce,
)


@dataclass
class NewOrderSingle(FIXMessage):
    """New Order Single (35=D) - Submit a new order.

    This message is used to submit a single order to a broker.
    """

    # Required order fields
    cl_ord_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    side: Side = Side.BUY
    transact_time: datetime = field(default_factory=datetime.utcnow)
    ord_type: OrdType = OrdType.MARKET

    # Optional order fields
    order_qty: Optional[float] = None
    price: Optional[float] = None
    stop_px: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    currency: str = "USD"

    # Order routing
    account: Optional[str] = None
    exec_broker: Optional[str] = None

    # Risk management
    max_floor: Optional[float] = None

    # Text description
    text: Optional[str] = None

    def __post_init__(self):
        """Initialize NewOrderSingle message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.NEW_ORDER_SINGLE

        # Validate required fields
        if not self.symbol:
            raise ValueError("Symbol is required for NewOrderSingle")
        if self.order_qty is None:
            raise ValueError("Order quantity is required for NewOrderSingle")

        # Validate price fields based on order type
        if self.ord_type in [OrdType.LIMIT, OrdType.STOP_LIMIT, OrdType.FOREX_LIMIT]:
            if self.price is None:
                raise ValueError(f"Price is required for {self.ord_type.value} orders")

        if self.ord_type in [OrdType.STOP, OrdType.STOP_LIMIT]:
            if self.stop_px is None:
                raise ValueError(
                    f"Stop price is required for {self.ord_type.value} orders"
                )

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            FIXField.CL_ORD_ID.value: self.cl_ord_id,
            FIXField.SYMBOL.value: self.symbol,
            FIXField.SIDE.value: self.side.value,
            FIXField.TRANSACT_TIME.value: self.transact_time.strftime(
                "%Y%m%d-%H:%M:%S"
            ),
            FIXField.ORD_TYPE.value: self.ord_type.value,
            FIXField.TIME_IN_FORCE.value: self.time_in_force.value,
        }

        # Add quantity if specified
        if self.order_qty is not None:
            fields[FIXField.ORDER_QTY.value] = str(self.order_qty)

        # Add price if specified
        if self.price is not None:
            fields[FIXField.PRICE.value] = str(self.price)

        # Add stop price if specified
        if self.stop_px is not None:
            fields[FIXField.STOP_PX.value] = str(self.stop_px)

        # Add optional fields
        if self.account:
            fields[1] = self.account  # Account tag
        if self.text:
            fields[FIXField.TEXT.value] = self.text

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "NewOrderSingle":
        """Parse FIX string into NewOrderSingle message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Parse all fields first
        parsed_fields = {}
        parsed_fields["cl_ord_id"] = fields.get(
            FIXField.CL_ORD_ID.value, str(uuid.uuid4())
        )
        parsed_fields["symbol"] = fields.get(FIXField.SYMBOL.value, "")
        parsed_fields["side"] = Side(fields.get(FIXField.SIDE.value, "1"))
        parsed_fields["ord_type"] = OrdType(fields.get(FIXField.ORD_TYPE.value, "1"))
        parsed_fields["time_in_force"] = TimeInForce(
            fields.get(FIXField.TIME_IN_FORCE.value, "0")
        )
        parsed_fields["order_qty"] = (
            float(fields.get(FIXField.ORDER_QTY.value, 1))
            if FIXField.ORDER_QTY.value in fields
            else 1
        )

        # Add optional fields that might be required based on order type
        if FIXField.PRICE.value in fields:
            parsed_fields["price"] = float(fields[FIXField.PRICE.value])
        if FIXField.STOP_PX.value in fields:
            parsed_fields["stop_px"] = float(fields[FIXField.STOP_PX.value])
        if FIXField.TEXT.value in fields:
            parsed_fields["text"] = fields[FIXField.TEXT.value]

        # Create the message with all relevant fields
        msg = cls(**parsed_fields)

        return msg


@dataclass
class ExecutionReport(FIXMessage):
    """Execution Report (35=8) - Report order status and fills.

    This message reports the status of an order, including partial fills,
    complete fills, rejections, and cancellations.
    """

    # Order identification
    order_id: str = ""
    cl_ord_id: str = ""
    orig_cl_ord_id: Optional[str] = None
    exec_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Execution details
    exec_type: ExecType = ExecType.NEW
    ord_status: OrdStatus = OrdStatus.NEW

    # Order details
    symbol: str = ""
    side: Side = Side.BUY
    order_qty: float = 0.0
    ord_type: OrdType = OrdType.MARKET

    # Execution quantities and prices
    last_qty: Optional[float] = None  # Quantity of this fill
    last_px: Optional[float] = None  # Price of this fill
    leaves_qty: Optional[float] = None  # Remaining quantity
    cum_qty: Optional[float] = None  # Total filled quantity
    avg_px: Optional[float] = None  # Average fill price

    # Order prices
    price: Optional[float] = None
    stop_px: Optional[float] = None

    # Timestamps
    transact_time: datetime = field(default_factory=datetime.utcnow)

    # Rejection/cancellation
    ord_rej_reason: Optional[int] = None
    text: Optional[str] = None

    # Account information
    account: Optional[str] = None

    def __post_init__(self):
        """Initialize ExecutionReport message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.EXECUTION_REPORT

        # Validate required fields
        if not self.order_id:
            self.order_id = str(uuid.uuid4())
        if not self.cl_ord_id:
            raise ValueError("Client Order ID is required for ExecutionReport")
        if not self.symbol:
            raise ValueError("Symbol is required for ExecutionReport")

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            FIXField.ORDER_ID.value: self.order_id,
            FIXField.CL_ORD_ID.value: self.cl_ord_id,
            FIXField.EXEC_ID.value: self.exec_id,
            FIXField.EXEC_TYPE.value: self.exec_type.value,
            FIXField.ORD_STATUS.value: self.ord_status.value,
            FIXField.SYMBOL.value: self.symbol,
            FIXField.SIDE.value: self.side.value,
            FIXField.ORDER_QTY.value: str(self.order_qty),
            FIXField.ORD_TYPE.value: self.ord_type.value,
            FIXField.TRANSACT_TIME.value: self.transact_time.strftime(
                "%Y%m%d-%H:%M:%S"
            ),
        }

        # Add execution quantities and prices
        if self.last_qty is not None:
            fields[FIXField.LAST_QTY.value] = str(self.last_qty)
        if self.last_px is not None:
            fields[FIXField.LAST_PX.value] = str(self.last_px)
        if self.leaves_qty is not None:
            fields[FIXField.LEAVES_QTY.value] = str(self.leaves_qty)
        if self.cum_qty is not None:
            fields[FIXField.CUM_QTY.value] = str(self.cum_qty)
        if self.avg_px is not None:
            fields[FIXField.AVG_PX.value] = str(self.avg_px)

        # Add order prices
        if self.price is not None:
            fields[FIXField.PRICE.value] = str(self.price)
        if self.stop_px is not None:
            fields[FIXField.STOP_PX.value] = str(self.stop_px)

        # Add optional fields
        if self.orig_cl_ord_id:
            fields[41] = self.orig_cl_ord_id  # OrigClOrdID tag
        if self.ord_rej_reason is not None:
            fields[FIXField.ORD_REJ_REASON.value] = str(self.ord_rej_reason)
        if self.text:
            fields[FIXField.TEXT.value] = self.text
        if self.account:
            fields[1] = self.account  # Account tag

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "ExecutionReport":
        """Parse FIX string into ExecutionReport message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Extract required fields
        msg = cls(
            order_id=fields.get(FIXField.ORDER_ID.value, str(uuid.uuid4())),
            cl_ord_id=fields.get(FIXField.CL_ORD_ID.value, ""),
            exec_id=fields.get(FIXField.EXEC_ID.value, str(uuid.uuid4())),
            exec_type=ExecType(fields.get(FIXField.EXEC_TYPE.value, "0")),
            ord_status=OrdStatus(fields.get(FIXField.ORD_STATUS.value, "0")),
            symbol=fields.get(FIXField.SYMBOL.value, ""),
            side=Side(fields.get(FIXField.SIDE.value, "1")),
            order_qty=float(fields.get(FIXField.ORDER_QTY.value, 0)),
            ord_type=OrdType(fields.get(FIXField.ORD_TYPE.value, "1")),
        )

        # Parse optional numeric fields
        if FIXField.LAST_QTY.value in fields:
            msg.last_qty = float(fields[FIXField.LAST_QTY.value])
        if FIXField.LAST_PX.value in fields:
            msg.last_px = float(fields[FIXField.LAST_PX.value])
        if FIXField.LEAVES_QTY.value in fields:
            msg.leaves_qty = float(fields[FIXField.LEAVES_QTY.value])
        if FIXField.CUM_QTY.value in fields:
            msg.cum_qty = float(fields[FIXField.CUM_QTY.value])
        if FIXField.AVG_PX.value in fields:
            msg.avg_px = float(fields[FIXField.AVG_PX.value])
        if FIXField.PRICE.value in fields:
            msg.price = float(fields[FIXField.PRICE.value])
        if FIXField.STOP_PX.value in fields:
            msg.stop_px = float(fields[FIXField.STOP_PX.value])

        # Parse text fields
        if 41 in fields:
            msg.orig_cl_ord_id = fields[41]
        if FIXField.TEXT.value in fields:
            msg.text = fields[FIXField.TEXT.value]
        if 1 in fields:
            msg.account = fields[1]

        return msg


@dataclass
class OrderCancelRequest(FIXMessage):
    """Order Cancel Request (35=F) - Request cancellation of an order.

    This message is used to request the cancellation of an existing order.
    """

    # Order identification
    orig_cl_ord_id: str = ""  # Original client order ID to cancel
    cl_ord_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )  # New client order ID
    order_id: Optional[str] = None  # Broker order ID (if known)

    # Order details (must match original order)
    symbol: str = ""
    side: Side = Side.BUY
    transact_time: datetime = field(default_factory=datetime.utcnow)

    # Optional fields
    order_qty: Optional[float] = None  # Original order quantity
    account: Optional[str] = None
    text: Optional[str] = None

    def __post_init__(self):
        """Initialize OrderCancelRequest message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.ORDER_CANCEL_REQUEST

        # Validate required fields
        if not self.orig_cl_ord_id:
            raise ValueError(
                "Original Client Order ID is required for OrderCancelRequest"
            )
        if not self.symbol:
            raise ValueError("Symbol is required for OrderCancelRequest")

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            41: self.orig_cl_ord_id,  # OrigClOrdID tag
            FIXField.CL_ORD_ID.value: self.cl_ord_id,
            FIXField.SYMBOL.value: self.symbol,
            FIXField.SIDE.value: self.side.value,
            FIXField.TRANSACT_TIME.value: self.transact_time.strftime(
                "%Y%m%d-%H:%M:%S"
            ),
        }

        # Add optional fields
        if self.order_id:
            fields[FIXField.ORDER_ID.value] = self.order_id
        if self.order_qty is not None:
            fields[FIXField.ORDER_QTY.value] = str(self.order_qty)
        if self.account:
            fields[1] = self.account  # Account tag
        if self.text:
            fields[FIXField.TEXT.value] = self.text

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "OrderCancelRequest":
        """Parse FIX string into OrderCancelRequest message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Extract required fields
        msg = cls(
            orig_cl_ord_id=fields.get(41, ""),
            cl_ord_id=fields.get(FIXField.CL_ORD_ID.value, str(uuid.uuid4())),
            symbol=fields.get(FIXField.SYMBOL.value, ""),
            side=Side(fields.get(FIXField.SIDE.value, "1")),
        )

        # Parse optional fields
        if FIXField.ORDER_ID.value in fields:
            msg.order_id = fields[FIXField.ORDER_ID.value]
        if FIXField.ORDER_QTY.value in fields:
            msg.order_qty = float(fields[FIXField.ORDER_QTY.value])
        if 1 in fields:
            msg.account = fields[1]
        if FIXField.TEXT.value in fields:
            msg.text = fields[FIXField.TEXT.value]

        return msg


# Helper functions for creating common orders
def create_market_order(
    symbol: str,
    side: Side,
    quantity: float,
    account: Optional[str] = None,
    text: Optional[str] = None,
) -> NewOrderSingle:
    """Create a market order."""
    return NewOrderSingle(
        symbol=symbol,
        side=side,
        order_qty=quantity,
        ord_type=OrdType.MARKET,
        time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
        account=account,
        text=text,
    )


def create_limit_order(
    symbol: str,
    side: Side,
    quantity: float,
    price: float,
    time_in_force: TimeInForce = TimeInForce.DAY,
    account: Optional[str] = None,
    text: Optional[str] = None,
) -> NewOrderSingle:
    """Create a limit order."""
    return NewOrderSingle(
        symbol=symbol,
        side=side,
        order_qty=quantity,
        ord_type=OrdType.LIMIT,
        price=price,
        time_in_force=time_in_force,
        account=account,
        text=text,
    )


def create_stop_order(
    symbol: str,
    side: Side,
    quantity: float,
    stop_price: float,
    time_in_force: TimeInForce = TimeInForce.DAY,
    account: Optional[str] = None,
    text: Optional[str] = None,
) -> NewOrderSingle:
    """Create a stop order."""
    return NewOrderSingle(
        symbol=symbol,
        side=side,
        order_qty=quantity,
        ord_type=OrdType.STOP,
        stop_px=stop_price,
        time_in_force=time_in_force,
        account=account,
        text=text,
    )


def create_stop_limit_order(
    symbol: str,
    side: Side,
    quantity: float,
    stop_price: float,
    limit_price: float,
    time_in_force: TimeInForce = TimeInForce.DAY,
    account: Optional[str] = None,
    text: Optional[str] = None,
) -> NewOrderSingle:
    """Create a stop-limit order."""
    return NewOrderSingle(
        symbol=symbol,
        side=side,
        order_qty=quantity,
        ord_type=OrdType.STOP_LIMIT,
        stop_px=stop_price,
        price=limit_price,
        time_in_force=time_in_force,
        account=account,
        text=text,
    )
