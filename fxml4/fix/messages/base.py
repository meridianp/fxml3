"""Base FIX Message Classes and Enumerations.

This module provides the foundation for FIX message handling with
standardized field definitions and message structure.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union


class FIXMessageType(Enum):
    """FIX Message Types (Tag 35)."""

    HEARTBEAT = "0"
    TEST_REQUEST = "1"
    RESEND_REQUEST = "2"
    REJECT = "3"
    SEQUENCE_RESET = "4"
    LOGOUT = "5"
    LOGON = "A"
    NEWS = "B"
    EMAIL = "C"
    NEW_ORDER_SINGLE = "D"
    NEW_ORDER_LIST = "E"
    ORDER_CANCEL_REQUEST = "F"
    ORDER_CANCEL_REPLACE_REQUEST = "G"
    ORDER_STATUS_REQUEST = "H"
    ALLOCATION_INSTRUCTION = "J"
    LIST_CANCEL_REQUEST = "K"
    LIST_EXECUTE = "L"
    LIST_STATUS_REQUEST = "M"
    LIST_STATUS = "N"
    ALLOCATION_INSTRUCTION_ACK = "P"
    DONT_KNOW_TRADE = "Q"
    QUOTE_REQUEST = "R"
    QUOTE = "S"
    SETTLEMENT_INSTRUCTIONS = "T"
    MARKET_DATA_REQUEST = "V"
    MARKET_DATA_SNAPSHOT_FULL_REFRESH = "W"
    MARKET_DATA_INCREMENTAL_REFRESH = "X"
    MARKET_DATA_REQUEST_REJECT = "Y"
    QUOTE_CANCEL = "Z"
    QUOTE_STATUS_REQUEST = "a"
    MASS_QUOTE_ACKNOWLEDGEMENT = "b"
    SECURITY_DEFINITION_REQUEST = "c"
    SECURITY_DEFINITION = "d"
    SECURITY_STATUS_REQUEST = "e"
    SECURITY_STATUS = "f"
    TRADING_SESSION_STATUS_REQUEST = "g"
    TRADING_SESSION_STATUS = "h"
    MASS_QUOTE = "i"
    BUSINESS_MESSAGE_REJECT = "j"
    BID_REQUEST = "k"
    BID_RESPONSE = "l"
    LIST_STRIKE_PRICE = "m"
    EXECUTION_REPORT = "8"
    ORDER_CANCEL_REJECT = "9"


class FIXField(Enum):
    """Common FIX Field Tags."""

    # Standard Header Fields
    BEGIN_STRING = 8
    BODY_LENGTH = 9
    MSG_TYPE = 35
    SENDER_COMP_ID = 49
    TARGET_COMP_ID = 56
    MSG_SEQ_NUM = 34
    SENDING_TIME = 52
    CHECKSUM = 10

    # Order Fields
    CL_ORD_ID = 11  # Client Order ID
    ORDER_ID = 37  # Order ID
    EXEC_ID = 17  # Execution ID
    EXEC_TYPE = 150  # Execution Type
    ORD_STATUS = 39  # Order Status
    SYMBOL = 55  # Symbol
    SIDE = 54  # Side (Buy/Sell)
    ORDER_QTY = 38  # Order Quantity
    ORD_TYPE = 40  # Order Type
    PRICE = 44  # Price
    STOP_PX = 99  # Stop Price
    TIME_IN_FORCE = 59  # Time in Force

    # Execution Fields
    LAST_QTY = 32  # Last Quantity
    LAST_PX = 31  # Last Price
    LEAVES_QTY = 151  # Leaves Quantity
    CUM_QTY = 14  # Cumulative Quantity
    AVG_PX = 6  # Average Price

    # Administrative
    HEARTBT_INT = 108  # Heartbeat Interval
    TEST_REQ_ID = 112  # Test Request ID

    # Timestamps
    TRANSACT_TIME = 60  # Transaction Time

    # Rejection
    ORD_REJ_REASON = 103  # Order Reject Reason
    TEXT = 58  # Text


class OrdStatus(Enum):
    """Order Status Values (Tag 39)."""

    NEW = "0"
    PARTIALLY_FILLED = "1"
    FILLED = "2"
    DONE_FOR_DAY = "3"
    CANCELED = "4"
    REPLACED = "5"
    PENDING_CANCEL = "6"
    STOPPED = "7"
    REJECTED = "8"
    SUSPENDED = "9"
    PENDING_NEW = "A"
    CALCULATED = "B"
    EXPIRED = "C"
    ACCEPTED_FOR_BIDDING = "D"
    PENDING_REPLACE = "E"


class ExecType(Enum):
    """Execution Type Values (Tag 150)."""

    NEW = "0"
    PARTIAL_FILL = "1"
    FILL = "2"
    DONE_FOR_DAY = "3"
    CANCELED = "4"
    REPLACED = "5"
    PENDING_CANCEL = "6"
    STOPPED = "7"
    REJECTED = "8"
    SUSPENDED = "9"
    PENDING_NEW = "A"
    CALCULATED = "B"
    EXPIRED = "C"
    RESTATED = "D"
    PENDING_REPLACE = "E"
    TRADE = "F"
    TRADE_CORRECT = "G"
    TRADE_CANCEL = "H"
    ORDER_STATUS = "I"


class Side(Enum):
    """Side Values (Tag 54)."""

    BUY = "1"
    SELL = "2"
    BUY_MINUS = "3"
    SELL_PLUS = "4"
    SELL_SHORT = "5"
    SELL_SHORT_EXEMPT = "6"
    UNDISCLOSED = "7"
    CROSS = "8"
    CROSS_SHORT = "9"


class OrdType(Enum):
    """Order Type Values (Tag 40)."""

    MARKET = "1"
    LIMIT = "2"
    STOP = "3"
    STOP_LIMIT = "4"
    MARKET_ON_CLOSE = "5"
    WITH_OR_WITHOUT = "6"
    LIMIT_OR_BETTER = "7"
    LIMIT_WITH_OR_WITHOUT = "8"
    ON_BASIS = "9"
    ON_CLOSE = "A"
    LIMIT_ON_CLOSE = "B"
    FOREX_MARKET = "C"
    PREVIOUSLY_QUOTED = "D"
    PREVIOUSLY_INDICATED = "E"
    FOREX_LIMIT = "F"
    FOREX_SWAP = "G"
    FOREX_PREVIOUSLY_QUOTED = "H"
    FUNARI = "I"
    MARKET_IF_TOUCHED = "J"
    MARKET_WITH_LEFT_OVER_AS_LIMIT = "K"
    PREVIOUS_FUND_VALUATION_POINT = "L"
    NEXT_FUND_VALUATION_POINT = "M"
    PEGGED = "P"


class TimeInForce(Enum):
    """Time in Force Values (Tag 59)."""

    DAY = "0"
    GOOD_TILL_CANCEL = "1"
    GTC = "1"  # Alias for GOOD_TILL_CANCEL
    AT_THE_OPENING = "2"
    IMMEDIATE_OR_CANCEL = "3"
    IOC = "3"  # Alias for IMMEDIATE_OR_CANCEL
    FILL_OR_KILL = "4"
    FOK = "4"  # Alias for FILL_OR_KILL
    GOOD_TILL_CROSSING = "5"
    GOOD_TILL_DATE = "6"
    GTD = "6"  # Alias for GOOD_TILL_DATE
    AT_THE_CLOSE = "7"


@dataclass
class FIXMessage(ABC):
    """Base class for all FIX messages."""

    # Required header fields
    sender_comp_id: str = "FXML4"
    target_comp_id: str = ""
    msg_seq_num: int = 0
    sending_time: Optional[datetime] = None
    msg_type: Optional[FIXMessageType] = None

    # Message body fields (populated by subclasses)
    fields: Dict[int, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize message after creation."""
        if self.sending_time is None:
            self.sending_time = datetime.utcnow()

    @abstractmethod
    def get_body_fields(self) -> Dict[int, Any]:
        """Get message-specific body fields.

        Returns:
            Dictionary mapping FIX tags to values.
        """
        pass

    def to_fix_string(self) -> str:
        """Convert message to FIX protocol string format.

        Returns:
            FIX protocol string representation.
        """
        # Start with header
        fix_string = f"8=FIX.4.2{chr(1)}"  # Begin String

        # Add message type
        fix_string += f"35={self.msg_type.value}{chr(1)}"

        # Add sender/target
        fix_string += f"49={self.sender_comp_id}{chr(1)}"
        fix_string += f"56={self.target_comp_id}{chr(1)}"

        # Add sequence number
        fix_string += f"34={self.msg_seq_num}{chr(1)}"

        # Add sending time
        time_str = self.sending_time.strftime("%Y%m%d-%H:%M:%S")
        fix_string += f"52={time_str}{chr(1)}"

        # Add body fields
        body_fields = self.get_body_fields()
        for tag, value in sorted(body_fields.items()):
            if value is not None:
                fix_string += f"{tag}={value}{chr(1)}"

        # Calculate body length (everything after tag 8 and 9, before tag 10)
        body_start = fix_string.find("35=")
        body_length = len(fix_string[body_start:]) - 1  # Exclude final SOH

        # Insert body length after begin string
        fix_string = fix_string[:12] + f"9={body_length}{chr(1)}" + fix_string[12:]

        # Calculate checksum
        checksum = sum(ord(c) for c in fix_string) % 256
        fix_string += f"10={checksum:03d}{chr(1)}"

        return fix_string

    @classmethod
    @abstractmethod
    def from_fix_string(cls, fix_string: str) -> "FIXMessage":
        """Parse FIX string into message object.

        Args:
            fix_string: FIX protocol string.

        Returns:
            Parsed FIX message object.
        """
        pass

    def get_field(self, tag: Union[int, FIXField], default: Any = None) -> Any:
        """Get field value by tag.

        Args:
            tag: Field tag number or FIXField enum.
            default: Default value if field not found.

        Returns:
            Field value or default.
        """
        tag_num = tag.value if isinstance(tag, FIXField) else tag
        return self.fields.get(tag_num, default)

    def set_field(self, tag: Union[int, FIXField], value: Any) -> None:
        """Set field value by tag.

        Args:
            tag: Field tag number or FIXField enum.
            value: Value to set.
        """
        tag_num = tag.value if isinstance(tag, FIXField) else tag
        self.fields[tag_num] = value
