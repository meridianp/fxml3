"""FIX Administrative Messages.

This module implements FIX administrative messages for session management,
including logon, logout, heartbeats, and test requests.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from .base import FIXField, FIXMessage, FIXMessageType


@dataclass
class Logon(FIXMessage):
    """Logon (35=A) - Initiate FIX session.

    This message is used to initiate a FIX session between two parties.
    """

    # Required fields
    encrypt_method: str = "0"  # No encryption
    heartbt_int: int = 30  # Heartbeat interval in seconds

    # Optional authentication
    username: Optional[str] = None
    password: Optional[str] = None

    # Session management
    reset_seq_num_flag: bool = False
    next_expected_msg_seq_num: Optional[int] = None

    # Version information
    default_appl_ver_id: str = "FIX.4.2"

    def __post_init__(self):
        """Initialize Logon message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.LOGON

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            98: self.encrypt_method,  # EncryptMethod tag
            FIXField.HEARTBT_INT.value: str(self.heartbt_int),
        }

        # Add optional fields
        if self.username:
            fields[553] = self.username  # Username tag
        if self.password:
            fields[554] = self.password  # Password tag
        if self.reset_seq_num_flag:
            fields[141] = "Y"  # ResetSeqNumFlag tag
        if self.next_expected_msg_seq_num is not None:
            fields[789] = str(
                self.next_expected_msg_seq_num
            )  # NextExpectedMsgSeqNum tag

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "Logon":
        """Parse FIX string into Logon message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Extract required fields
        msg = cls(
            encrypt_method=fields.get(98, "0"),
            heartbt_int=int(fields.get(FIXField.HEARTBT_INT.value, 30)),
        )

        # Parse optional fields
        if 553 in fields:
            msg.username = fields[553]
        if 554 in fields:
            msg.password = fields[554]
        if 141 in fields:
            msg.reset_seq_num_flag = fields[141] == "Y"
        if 789 in fields:
            msg.next_expected_msg_seq_num = int(fields[789])

        return msg


@dataclass
class Logout(FIXMessage):
    """Logout (35=5) - Terminate FIX session.

    This message is used to terminate a FIX session.
    """

    # Optional text description
    text: Optional[str] = None
    session_status: Optional[int] = None

    def __post_init__(self):
        """Initialize Logout message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.LOGOUT

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {}

        # Add optional fields
        if self.text:
            fields[FIXField.TEXT.value] = self.text
        if self.session_status is not None:
            fields[1409] = str(self.session_status)  # SessionStatus tag

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "Logout":
        """Parse FIX string into Logout message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Create message
        msg = cls()

        # Parse optional fields
        if FIXField.TEXT.value in fields:
            msg.text = fields[FIXField.TEXT.value]
        if 1409 in fields:
            msg.session_status = int(fields[1409])

        return msg


@dataclass
class Heartbeat(FIXMessage):
    """Heartbeat (35=0) - Keep session alive.

    This message is used to maintain session connectivity when no other
    messages are being transmitted.
    """

    # Optional test request ID (if responding to test request)
    test_req_id: Optional[str] = None

    def __post_init__(self):
        """Initialize Heartbeat message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.HEARTBEAT

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {}

        # Add test request ID if this is a response
        if self.test_req_id:
            fields[FIXField.TEST_REQ_ID.value] = self.test_req_id

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "Heartbeat":
        """Parse FIX string into Heartbeat message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Create message
        msg = cls()

        # Parse optional fields
        if FIXField.TEST_REQ_ID.value in fields:
            msg.test_req_id = fields[FIXField.TEST_REQ_ID.value]

        return msg


@dataclass
class TestRequest(FIXMessage):
    """Test Request (35=1) - Request heartbeat response.

    This message is used to force a heartbeat from the counterparty.
    """

    # Required test request ID
    test_req_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        """Initialize TestRequest message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.TEST_REQUEST

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        return {FIXField.TEST_REQ_ID.value: self.test_req_id}

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "TestRequest":
        """Parse FIX string into TestRequest message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Extract required field
        msg = cls(test_req_id=fields.get(FIXField.TEST_REQ_ID.value, str(uuid.uuid4())))

        return msg


@dataclass
class Reject(FIXMessage):
    """Reject (35=3) - Message-level rejection.

    This message is used to reject a received message due to parsing
    or business rule violations.
    """

    # Required fields
    ref_seq_num: int = 0  # Sequence number of rejected message
    ref_tag_id: Optional[int] = None  # Tag of problematic field
    ref_msg_type: Optional[str] = None  # Message type of rejected message
    session_reject_reason: Optional[int] = None  # Reason code
    text: Optional[str] = None  # Human-readable description

    def __post_init__(self):
        """Initialize Reject message."""
        super().__post_init__()
        self.msg_type = FIXMessageType.REJECT

    def get_body_fields(self) -> Dict[int, Any]:
        """Get message body fields for FIX serialization."""
        fields = {
            45: str(self.ref_seq_num),  # RefSeqNum tag
        }

        # Add optional fields
        if self.ref_tag_id is not None:
            fields[371] = str(self.ref_tag_id)  # RefTagID tag
        if self.ref_msg_type:
            fields[372] = self.ref_msg_type  # RefMsgType tag
        if self.session_reject_reason is not None:
            fields[373] = str(self.session_reject_reason)  # SessionRejectReason tag
        if self.text:
            fields[FIXField.TEXT.value] = self.text

        return fields

    @classmethod
    def from_fix_string(cls, fix_string: str) -> "Reject":
        """Parse FIX string into Reject message."""
        # Parse FIX string into field dictionary
        fields = {}
        parts = fix_string.split("\x01")  # SOH delimiter

        for part in parts:
            if "=" in part:
                tag, value = part.split("=", 1)
                fields[int(tag)] = value

        # Extract required field
        msg = cls(ref_seq_num=int(fields.get(45, 0)))

        # Parse optional fields
        if 371 in fields:
            msg.ref_tag_id = int(fields[371])
        if 372 in fields:
            msg.ref_msg_type = fields[372]
        if 373 in fields:
            msg.session_reject_reason = int(fields[373])
        if FIXField.TEXT.value in fields:
            msg.text = fields[FIXField.TEXT.value]

        return msg


# Session reject reason codes
class SessionRejectReason:
    """Session reject reason codes for Reject messages."""

    INVALID_TAG_NUMBER = 0
    REQUIRED_TAG_MISSING = 1
    TAG_NOT_DEFINED_FOR_MESSAGE = 2
    UNDEFINED_TAG = 3
    TAG_SPECIFIED_WITHOUT_VALUE = 4
    VALUE_IS_INCORRECT = 5
    INCORRECT_DATA_FORMAT = 6
    DECRYPTION_PROBLEM = 7
    SIGNATURE_PROBLEM = 8
    COMPID_PROBLEM = 9
    SENDINGTIME_ACCURACY_PROBLEM = 10
    INVALID_MSGTYPE = 11
    XML_VALIDATION_ERROR = 12
    TAG_APPEARS_MORE_THAN_ONCE = 13
    TAG_SPECIFIED_OUT_OF_ORDER = 14
    REPEATING_GROUP_OUT_OF_ORDER = 15
    INCORRECT_NUM_IN_GROUP = 16
    NON_DATA_VALUE_INCLUDES_FIELD_DELIMITER = 17


# Helper functions for creating common administrative messages
def create_logon_request(
    heartbeat_interval: int = 30,
    username: Optional[str] = None,
    password: Optional[str] = None,
    reset_sequence: bool = False,
) -> Logon:
    """Create a logon request."""
    return Logon(
        heartbt_int=heartbeat_interval,
        username=username,
        password=password,
        reset_seq_num_flag=reset_sequence,
    )


def create_logout_request(reason: Optional[str] = None) -> Logout:
    """Create a logout request."""
    return Logout(text=reason)


def create_heartbeat_response(test_req_id: str) -> Heartbeat:
    """Create a heartbeat response to a test request."""
    return Heartbeat(test_req_id=test_req_id)


def create_test_request() -> TestRequest:
    """Create a test request."""
    return TestRequest()


def create_rejection(
    rejected_seq_num: int,
    reason_code: int,
    description: str,
    problematic_tag: Optional[int] = None,
    rejected_msg_type: Optional[str] = None,
) -> Reject:
    """Create a message rejection."""
    return Reject(
        ref_seq_num=rejected_seq_num,
        session_reject_reason=reason_code,
        text=description,
        ref_tag_id=problematic_tag,
        ref_msg_type=rejected_msg_type,
    )
