"""FIX Market Data Messages.

This module implements FIX messages for market data subscription and distribution,
including market data requests and responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .base import FIXField, FIXMessage, FIXMessageType


class MDEntryType(Enum):
    """Market Data Entry Type Values (Tag 269)."""

    BID = "0"
    OFFER = "1"
    TRADE = "2"
    INDEX_VALUE = "3"
    OPENING_PRICE = "4"
    CLOSING_PRICE = "5"
    SETTLEMENT_PRICE = "6"
    TRADING_SESSION_HIGH_PRICE = "7"
    TRADING_SESSION_LOW_PRICE = "8"
    TRADING_SESSION_VWAP_PRICE = "9"
    IMBALANCE = "A"
    TRADE_VOLUME = "B"
    OPEN_INTEREST = "C"


class SubscriptionRequestType(Enum):
    """Subscription Request Type Values (Tag 263)."""

    SNAPSHOT = "0"
    SNAPSHOT_PLUS_UPDATES = "1"
    DISABLE_PREVIOUS = "2"


class MDUpdateType(Enum):
    """Market Data Update Type Values (Tag 265)."""

    FULL_REFRESH = "0"
    INCREMENTAL_REFRESH = "1"


@dataclass
class MarketDataRequest(FIXMessage):
    """Market Data Request (35=V) - Subscribe to market data.

    This message is used to request market data for one or more instruments.
    """

    # Required fields
    md_req_id: str = field(
        default_factory=lambda: f"MDR_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    )
    subscription_request_type: SubscriptionRequestType = (
        SubscriptionRequestType.SNAPSHOT_PLUS_UPDATES
    )
    market_depth: int = 1  # Number of market depth entries

    # Market data entry types requested
    md_entry_types: List[MDEntryType] = field(
        default_factory=lambda: [MDEntryType.BID, MDEntryType.OFFER]
    )

    # Instruments (symbols) to subscribe to
    symbols: List[str] = field(default_factory=list)

    # Optional fields
    md_update_type: Optional[MDUpdateType] = None
    aggregated_book: Optional[bool] = None

    def __post_init__(self):
        """Initialize MarketDataRequest message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.MARKET_DATA_REQUEST

        # Validate required fields
        if not self.symbols:
            raise ValueError("At least one symbol is required for MarketDataRequest")
        if not self.md_entry_types:
            raise ValueError(
                "At least one MDEntryType is required for MarketDataRequest"
            )

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            262: self.md_req_id,  # MDReqID tag
            263: self.subscription_request_type.value,  # SubscriptionRequestType tag
            264: str(self.market_depth),  # MarketDepth tag
        }

        # Add MDEntryType group
        fields[267] = str(len(self.md_entry_types))  # NoMDEntryTypes tag
        for i, entry_type in enumerate(self.md_entry_types):
            fields[269] = entry_type.value  # MDEntryType tag (repeating group)

        # Add Related Symbol group
        fields[146] = str(len(self.symbols))  # NoRelatedSym tag
        for i, symbol in enumerate(self.symbols):
            fields[FIXField.SYMBOL.value] = symbol  # Symbol tag (repeating group)

        # Add optional fields
        if self.md_update_type:
            fields[265] = self.md_update_type.value  # MDUpdateType tag
        if self.aggregated_book is not None:
            fields[266] = "Y" if self.aggregated_book else "N"  # AggregatedBook tag

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "MarketDataRequest":
        """Parse FIX string into MarketDataRequest message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Extract required fields
        msg = cls(
            md_req_id=fields.get(
                262, f"MDR_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            ),
            subscription_request_type=SubscriptionRequestType(fields.get(263, "1")),
            market_depth=int(fields.get(264, 1)),
        )

        # Parse repeating groups (simplified - real implementation would handle properly)
        if FIXField.SYMBOL.value in fields:
            msg.symbols = [fields[FIXField.SYMBOL.value]]
        if 269 in fields:
            msg.md_entry_types = [MDEntryType(fields[269])]

        # Parse optional fields
        if 265 in fields:
            msg.md_update_type = MDUpdateType(fields[265])
        if 266 in fields:
            msg.aggregated_book = fields[266] == "Y"

        return msg


@dataclass
class MarketDataEntry:
    """Market data entry within a snapshot."""

    entry_type: MDEntryType
    price: Optional[float] = None
    size: Optional[float] = None
    entry_date: Optional[datetime] = None
    entry_time: Optional[datetime] = None


@dataclass
class MarketDataSnapshot(FIXMessage):
    """Market Data Snapshot (35=W) - Full market data refresh.

    This message provides a full refresh of market data for an instrument.
    """

    # Identification fields
    md_req_id: Optional[str] = None  # Original request ID
    symbol: str = ""

    # Market data entries
    entries: List[MarketDataEntry] = field(default_factory=list)

    def __post_init__(self):
        """Initialize MarketDataSnapshot message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.MARKET_DATA_SNAPSHOT_FULL_REFRESH

        # Validate required fields
        if not self.symbol:
            raise ValueError("Symbol is required for MarketDataSnapshot")

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            FIXField.SYMBOL.value: self.symbol,
            268: str(len(self.entries)),  # NoMDEntries tag
        }

        # Add optional request ID
        if self.md_req_id:
            fields[262] = self.md_req_id  # MDReqID tag

        # Add market data entries (simplified - real implementation would handle repeating groups)
        for i, entry in enumerate(self.entries):
            # In a real implementation, each entry would have its own set of tags
            if entry.entry_type:
                fields[269] = entry.entry_type.value  # MDEntryType tag
            if entry.price is not None:
                fields[270] = str(entry.price)  # MDEntryPx tag
            if entry.size is not None:
                fields[271] = str(entry.size)  # MDEntrySize tag

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "MarketDataSnapshot":
        """Parse FIX string into MarketDataSnapshot message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Extract required fields
        msg = cls(
            symbol=fields.get(FIXField.SYMBOL.value, ""), md_req_id=fields.get(262)
        )

        # Parse market data entries (simplified)
        if 269 in fields:  # MDEntryType
            entry = MarketDataEntry(entry_type=MDEntryType(fields[269]))
            if 270 in fields:  # MDEntryPx
                entry.price = float(fields[270])
            if 271 in fields:  # MDEntrySize
                entry.size = float(fields[271])
            msg.entries.append(entry)

        return msg


@dataclass
class MarketDataIncrementalRefresh(FIXMessage):
    """Market Data Incremental Refresh (35=X) - Incremental market data update.

    This message provides incremental updates to market data.
    """

    # Identification fields
    md_req_id: Optional[str] = None

    # Market data entries
    entries: List[MarketDataEntry] = field(default_factory=list)

    def __post_init__(self):
        """Initialize MarketDataIncrementalRefresh message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.MARKET_DATA_INCREMENTAL_REFRESH

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            268: str(len(self.entries)),  # NoMDEntries tag
        }

        # Add optional request ID
        if self.md_req_id:
            fields[262] = self.md_req_id  # MDReqID tag

        # Add market data entries (simplified)
        for entry in self.entries:
            if entry.entry_type:
                fields[269] = entry.entry_type.value  # MDEntryType tag
            if entry.price is not None:
                fields[270] = str(entry.price)  # MDEntryPx tag
            if entry.size is not None:
                fields[271] = str(entry.size)  # MDEntrySize tag

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "MarketDataIncrementalRefresh":
        """Parse FIX string into MarketDataIncrementalRefresh message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Create message
        msg = cls(md_req_id=fields.get(262))

        # Parse market data entries (simplified)
        if 269 in fields:  # MDEntryType
            entry = MarketDataEntry(entry_type=MDEntryType(fields[269]))
            if 270 in fields:  # MDEntryPx
                entry.price = float(fields[270])
            if 271 in fields:  # MDEntrySize
                entry.size = float(fields[271])
            msg.entries.append(entry)

        return msg


@dataclass
class MarketDataRequestReject(FIXMessage):
    """Market Data Request Reject (35=Y) - Reject market data request.

    This message is used to reject a market data request.
    """

    # Required fields
    md_req_id: str = ""
    md_req_rej_reason: Optional[int] = None
    text: Optional[str] = None

    def __post_init__(self):
        """Initialize MarketDataRequestReject message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.MARKET_DATA_REQUEST_REJECT

        # Validate required fields
        if not self.md_req_id:
            raise ValueError("MDReqID is required for MarketDataRequestReject")

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            262: self.md_req_id,  # MDReqID tag
        }

        # Add optional fields
        if self.md_req_rej_reason is not None:
            fields[281] = str(self.md_req_rej_reason)  # MDReqRejReason tag
        if self.text:
            fields[FIXField.TEXT.value] = self.text

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "MarketDataRequestReject":
        """Parse FIX string into MarketDataRequestReject message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Extract required fields
        msg = cls(md_req_id=fields.get(262, ""))

        # Parse optional fields
        if 281 in fields:
            msg.md_req_rej_reason = int(fields[281])
        if FIXField.TEXT.value in fields:
            msg.text = fields[FIXField.TEXT.value]

        return msg


# Market data reject reason codes
class MDReqRejReason:
    """Market data request reject reason codes."""

    UNKNOWN_SYMBOL = 0
    DUPLICATE_MD_REQ_ID = 1
    INSUFFICIENT_BANDWIDTH = 2
    INSUFFICIENT_PERMISSIONS = 3
    UNSUPPORTED_SUBSCRIPTION_REQUEST_TYPE = 4
    UNSUPPORTED_MARKET_DEPTH = 5
    UNSUPPORTED_MD_UPDATE_TYPE = 6
    UNSUPPORTED_MD_ENTRY_TYPE = 7
    UNSUPPORTED_TRADING_SESSION_ID = 8
    UNSUPPORTED_SCOPE = 9
    UNSUPPORTED_OPEN_CLOSE_SETTLE_FLAG = 10
    UNSUPPORTED_MD_IMPL_IND = 11
    INSUFFICIENT_CREDIT = 12


# Helper functions for creating market data messages
def create_market_data_request(
    symbols: List[str],
    entry_types: Optional[List[MDEntryType]] = None,
    subscription_type: SubscriptionRequestType = SubscriptionRequestType.SNAPSHOT_PLUS_UPDATES,
    market_depth: int = 1,
) -> MarketDataRequest:
    """Create a market data request."""
    if entry_types is None:
        entry_types = [MDEntryType.BID, MDEntryType.OFFER, MDEntryType.TRADE]

    return MarketDataRequest(
        symbols=symbols,
        md_entry_types=entry_types,
        subscription_request_type=subscription_type,
        market_depth=market_depth,
    )


def create_market_data_snapshot(
    symbol: str,
    bid_price: Optional[float] = None,
    bid_size: Optional[float] = None,
    offer_price: Optional[float] = None,
    offer_size: Optional[float] = None,
    md_req_id: Optional[str] = None,
) -> MarketDataSnapshot:
    """Create a market data snapshot with bid/offer."""
    entries = []

    if bid_price is not None:
        entries.append(
            MarketDataEntry(entry_type=MDEntryType.BID, price=bid_price, size=bid_size)
        )

    if offer_price is not None:
        entries.append(
            MarketDataEntry(
                entry_type=MDEntryType.OFFER, price=offer_price, size=offer_size
            )
        )

    return MarketDataSnapshot(symbol=symbol, entries=entries, md_req_id=md_req_id)


def create_market_data_reject(
    md_req_id: str, reason_code: int, description: str
) -> MarketDataRequestReject:
    """Create a market data request rejection."""
    return MarketDataRequestReject(
        md_req_id=md_req_id, md_req_rej_reason=reason_code, text=description
    )
