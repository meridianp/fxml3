"""FIX Order Modification Messages.

This module implements FIX messages for order modification and cancellation,
including OrderCancelReplaceRequest and related messages.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

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


class CxlRejReason(Enum):
    """Order Cancel Reject Reason Values (Tag 102)."""

    TOO_LATE_TO_CANCEL = "0"
    UNKNOWN_ORDER = "1"
    BROKER_CREDIT_ISSUE = "2"
    ORDER_ALREADY_IN_PENDING_CANCEL_OR_PENDING_REPLACE_STATUS = "3"
    UNABLE_TO_PROCESS_ORDER_MASS_CANCEL_REQUEST = "4"
    ORIGORDMODTIME_DID_NOT_MATCH_LAST_ORDMODTIME_OF_ORDER = "5"
    DUPLICATE_CLORDID_RECEIVED = "6"
    INVALID_PRICE_INCREMENT = "18"
    OTHER = "99"


class CxlRejResponseTo(Enum):
    """Cancel Reject Response To Values (Tag 434)."""

    ORDER_CANCEL_REQUEST = "1"
    ORDER_CANCEL_REPLACE_REQUEST = "2"


@dataclass
class OrderCancelReplaceRequest(FIXMessage):
    """Order Cancel/Replace Request (35=G) - Modify an existing order.

    This message is used to change the parameters of an existing order.
    A replace request is treated as a cancel of the original order and
    a resubmission of a new order with the modified parameters.
    """

    # Order identification
    orig_cl_ord_id: str = ""  # Original client order ID to modify
    cl_ord_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )  # New client order ID
    order_id: Optional[str] = None  # Broker order ID (if known)

    # Order details (must match or modify original order)
    symbol: str = ""
    side: Side = Side.BUY
    transact_time: datetime = field(default_factory=datetime.utcnow)
    ord_type: OrdType = OrdType.LIMIT

    # Modified order parameters
    order_qty: Optional[float] = None  # New order quantity
    price: Optional[float] = None  # New price (for limit orders)
    stop_px: Optional[float] = None  # New stop price (for stop orders)
    time_in_force: TimeInForce = TimeInForce.DAY

    # Optional fields
    account: Optional[str] = None
    text: Optional[str] = None
    currency: str = "USD"

    # Handling instructions
    handl_inst: Optional[str] = None  # Handling instructions

    def __post_init__(self):
        """Initialize OrderCancelReplaceRequest message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.ORDER_CANCEL_REPLACE_REQUEST

        # Validate required fields
        if not self.orig_cl_ord_id:
            raise ValueError(
                "Original Client Order ID is required for OrderCancelReplaceRequest"
            )
        if not self.symbol:
            raise ValueError("Symbol is required for OrderCancelReplaceRequest")
        if self.order_qty is None:
            raise ValueError("Order quantity is required for OrderCancelReplaceRequest")

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
            41: self.orig_cl_ord_id,  # OrigClOrdID tag
            FIXField.CL_ORD_ID.value: self.cl_ord_id,
            FIXField.SYMBOL.value: self.symbol,
            FIXField.SIDE.value: self.side.value,
            FIXField.TRANSACT_TIME.value: self.transact_time.strftime(
                "%Y%m%d-%H:%M:%S"
            ),
            FIXField.ORD_TYPE.value: self.ord_type.value,
            FIXField.TIME_IN_FORCE.value: self.time_in_force.value,
        }

        # Add quantity
        if self.order_qty is not None:
            fields[FIXField.ORDER_QTY.value] = str(self.order_qty)

        # Add price if specified
        if self.price is not None:
            fields[FIXField.PRICE.value] = str(self.price)

        # Add stop price if specified
        if self.stop_px is not None:
            fields[FIXField.STOP_PX.value] = str(self.stop_px)

        # Add optional fields
        if self.order_id:
            fields[FIXField.ORDER_ID.value] = self.order_id
        if self.account:
            fields[1] = self.account  # Account tag
        if self.text:
            fields[FIXField.TEXT.value] = self.text
        if self.currency:
            fields[15] = self.currency  # Currency tag
        if self.handl_inst:
            fields[21] = self.handl_inst  # HandlInst tag

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "OrderCancelReplaceRequest":
        """Parse FIX string into OrderCancelReplaceRequest message."""
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
            ord_type=OrdType(fields.get(FIXField.ORD_TYPE.value, "2")),
            time_in_force=TimeInForce(fields.get(FIXField.TIME_IN_FORCE.value, "0")),
        )

        # Parse optional fields
        if FIXField.ORDER_QTY.value in fields:
            msg.order_qty = float(fields[FIXField.ORDER_QTY.value])
        if FIXField.PRICE.value in fields:
            msg.price = float(fields[FIXField.PRICE.value])
        if FIXField.STOP_PX.value in fields:
            msg.stop_px = float(fields[FIXField.STOP_PX.value])
        if FIXField.ORDER_ID.value in fields:
            msg.order_id = fields[FIXField.ORDER_ID.value]
        if 1 in fields:
            msg.account = fields[1]
        if FIXField.TEXT.value in fields:
            msg.text = fields[FIXField.TEXT.value]
        if 15 in fields:
            msg.currency = fields[15]
        if 21 in fields:
            msg.handl_inst = fields[21]

        return msg


@dataclass
class OrderCancelReject(FIXMessage):
    """Order Cancel Reject (35=9) - Reject order cancel or cancel/replace request.

    This message is used to reject an order cancel or cancel/replace request.
    """

    # Order identification
    order_id: str = ""
    cl_ord_id: str = ""
    orig_cl_ord_id: str = ""

    # Rejection details
    ord_status: OrdStatus = OrdStatus.REJECTED
    cxl_rej_reason: Optional[CxlRejReason] = None
    cxl_rej_response_to: CxlRejResponseTo = CxlRejResponseTo.ORDER_CANCEL_REQUEST

    # Order details
    symbol: Optional[str] = None
    side: Optional[Side] = None

    # Timestamps
    transact_time: datetime = field(default_factory=datetime.utcnow)

    # Additional information
    text: Optional[str] = None
    account: Optional[str] = None

    def __post_init__(self):
        """Initialize OrderCancelReject message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.ORDER_CANCEL_REJECT

        # Validate required fields
        if not self.cl_ord_id:
            raise ValueError("Client Order ID is required for OrderCancelReject")
        if not self.orig_cl_ord_id:
            raise ValueError(
                "Original Client Order ID is required for OrderCancelReject"
            )

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            FIXField.ORDER_ID.value: self.order_id,
            FIXField.CL_ORD_ID.value: self.cl_ord_id,
            41: self.orig_cl_ord_id,  # OrigClOrdID tag
            FIXField.ORD_STATUS.value: self.ord_status.value,
            434: self.cxl_rej_response_to.value,  # CxlRejResponseTo tag
            FIXField.TRANSACT_TIME.value: self.transact_time.strftime(
                "%Y%m%d-%H:%M:%S"
            ),
        }

        # Add optional fields
        if self.cxl_rej_reason:
            fields[102] = self.cxl_rej_reason.value  # CxlRejReason tag
        if self.symbol:
            fields[FIXField.SYMBOL.value] = self.symbol
        if self.side:
            fields[FIXField.SIDE.value] = self.side.value
        if self.text:
            fields[FIXField.TEXT.value] = self.text
        if self.account:
            fields[1] = self.account  # Account tag

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "OrderCancelReject":
        """Parse FIX string into OrderCancelReject message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Extract required fields
        msg = cls(
            order_id=fields.get(FIXField.ORDER_ID.value, ""),
            cl_ord_id=fields.get(FIXField.CL_ORD_ID.value, ""),
            orig_cl_ord_id=fields.get(41, ""),
            ord_status=OrdStatus(fields.get(FIXField.ORD_STATUS.value, "8")),
            cxl_rej_response_to=CxlRejResponseTo(fields.get(434, "1")),
        )

        # Parse optional fields
        if 102 in fields:
            msg.cxl_rej_reason = CxlRejReason(fields[102])
        if FIXField.SYMBOL.value in fields:
            msg.symbol = fields[FIXField.SYMBOL.value]
        if FIXField.SIDE.value in fields:
            msg.side = Side(fields[FIXField.SIDE.value])
        if FIXField.TEXT.value in fields:
            msg.text = fields[FIXField.TEXT.value]
        if 1 in fields:
            msg.account = fields[1]

        return msg


@dataclass
class OrderStatusRequest(FIXMessage):
    """Order Status Request (35=H) - Request status of an order.

    This message is used to request the current status of an order.
    """

    # Order identification
    cl_ord_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: Optional[str] = None  # Broker order ID (if known)

    # Order details for identification
    symbol: str = ""
    side: Side = Side.BUY

    # Optional fields
    account: Optional[str] = None

    def __post_init__(self):
        """Initialize OrderStatusRequest message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.ORDER_STATUS_REQUEST

        # Validate required fields
        if not self.symbol:
            raise ValueError("Symbol is required for OrderStatusRequest")

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            FIXField.CL_ORD_ID.value: self.cl_ord_id,
            FIXField.SYMBOL.value: self.symbol,
            FIXField.SIDE.value: self.side.value,
        }

        # Add optional fields
        if self.order_id:
            fields[FIXField.ORDER_ID.value] = self.order_id
        if self.account:
            fields[1] = self.account  # Account tag

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "OrderStatusRequest":
        """Parse FIX string into OrderStatusRequest message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Extract required fields
        msg = cls(
            cl_ord_id=fields.get(FIXField.CL_ORD_ID.value, str(uuid.uuid4())),
            symbol=fields.get(FIXField.SYMBOL.value, ""),
            side=Side(fields.get(FIXField.SIDE.value, "1")),
        )

        # Parse optional fields
        if FIXField.ORDER_ID.value in fields:
            msg.order_id = fields[FIXField.ORDER_ID.value]
        if 1 in fields:
            msg.account = fields[1]

        return msg


# Helper functions for creating order modification messages
def create_order_cancel_replace_request(
    orig_cl_ord_id: str,
    symbol: str,
    side: Side,
    new_quantity: float,
    new_price: Optional[float] = None,
    new_stop_price: Optional[float] = None,
    ord_type: OrdType = OrdType.LIMIT,
    time_in_force: TimeInForce = TimeInForce.DAY,
    account: Optional[str] = None,
    text: Optional[str] = None,
) -> OrderCancelReplaceRequest:
    """Create an order cancel/replace request."""
    return OrderCancelReplaceRequest(
        orig_cl_ord_id=orig_cl_ord_id,
        symbol=symbol,
        side=side,
        order_qty=new_quantity,
        price=new_price,
        stop_px=new_stop_price,
        ord_type=ord_type,
        time_in_force=time_in_force,
        account=account,
        text=text,
    )


def create_order_cancel_reject(
    cl_ord_id: str,
    orig_cl_ord_id: str,
    order_id: str,
    reason: CxlRejReason,
    response_to: CxlRejResponseTo,
    description: str,
    symbol: Optional[str] = None,
    side: Optional[Side] = None,
) -> OrderCancelReject:
    """Create an order cancel reject."""
    return OrderCancelReject(
        cl_ord_id=cl_ord_id,
        orig_cl_ord_id=orig_cl_ord_id,
        order_id=order_id,
        cxl_rej_reason=reason,
        cxl_rej_response_to=response_to,
        text=description,
        symbol=symbol,
        side=side,
    )


def create_order_status_request(
    cl_ord_id: str,
    symbol: str,
    side: Side,
    order_id: Optional[str] = None,
    account: Optional[str] = None,
) -> OrderStatusRequest:
    """Create an order status request."""
    return OrderStatusRequest(
        cl_ord_id=cl_ord_id,
        symbol=symbol,
        side=side,
        order_id=order_id,
        account=account,
    )
