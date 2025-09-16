"""FIX Session Manager.

This module provides lightweight session management for FIX connections,
handling sequence numbers, heartbeats, and session state.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional

from .messages.base import FIXMessage, FIXMessageType
from .simplefix_translator import SimpleFIXTranslator

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """FIX session states."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    LOGON_SENT = "LOGON_SENT"
    ACTIVE = "ACTIVE"
    LOGOUT_SENT = "LOGOUT_SENT"
    RESETTING = "RESETTING"
    ERROR = "ERROR"


@dataclass
class SessionConfig:
    """FIX session configuration."""

    sender_comp_id: str
    target_comp_id: str
    fix_version: str = "FIX.4.2"
    heartbeat_interval: int = 30  # seconds
    logon_timeout: int = 10  # seconds
    reconnect_interval: int = 5  # seconds
    reset_on_logon: bool = True
    persist_messages: bool = False
    max_messages_in_memory: int = 10000


@dataclass
class SessionStatistics:
    """Session performance statistics."""

    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_sent_time: Optional[datetime] = None
    last_received_time: Optional[datetime] = None
    logon_time: Optional[datetime] = None
    heartbeats_sent: int = 0
    heartbeats_received: int = 0
    resend_requests: int = 0
    sequence_resets: int = 0
    rejects: int = 0


class FIXSession:
    """Individual FIX session handler."""

    def __init__(
        self,
        session_id: str,
        config: SessionConfig,
        message_callback: Optional[Callable[[FIXMessage], None]] = None,
    ):
        """Initialize FIX session.

        Args:
            session_id: Unique session identifier.
            config: Session configuration.
            message_callback: Callback for received messages.
        """
        self.session_id = session_id
        self.config = config
        self.message_callback = message_callback

        # Session state
        self.state = SessionState.DISCONNECTED
        self.next_sender_seq_num = 1
        self.next_target_seq_num = 1
        self.last_heartbeat_sent = datetime.utcnow()
        self.last_heartbeat_received = datetime.utcnow()

        # Message storage
        self.sent_messages: Dict[int, FIXMessage] = {}
        self.received_messages: Dict[int, FIXMessage] = {}

        # Statistics
        self.stats = SessionStatistics()

        # Translator
        self.translator = SimpleFIXTranslator(
            sender_comp_id=config.sender_comp_id, target_comp_id=config.target_comp_id
        )

        # Tasks
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.monitor_task: Optional[asyncio.Task] = None

    def start(self):
        """Start session activities."""
        if self.state != SessionState.ACTIVE:
            return

        # Start heartbeat task
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Start monitor task
        if self.monitor_task:
            self.monitor_task.cancel()
        self.monitor_task = asyncio.create_task(self._monitor_loop())

    def stop(self):
        """Stop session activities."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

        if self.monitor_task:
            self.monitor_task.cancel()
            self.monitor_task = None

    def activate(self):
        """Activate session after successful logon."""
        self.state = SessionState.ACTIVE
        self.stats.logon_time = datetime.utcnow()
        self.start()
        logger.info(f"Session {self.session_id} activated")

    def deactivate(self):
        """Deactivate session."""
        self.stop()
        self.state = SessionState.DISCONNECTED
        logger.info(f"Session {self.session_id} deactivated")

    def get_next_seq_num(self) -> int:
        """Get next outgoing sequence number."""
        seq_num = self.next_sender_seq_num
        self.next_sender_seq_num += 1
        return seq_num

    def reset_sequence_numbers(self):
        """Reset sequence numbers."""
        self.next_sender_seq_num = 1
        self.next_target_seq_num = 1
        self.sent_messages.clear()
        self.received_messages.clear()
        logger.info(f"Session {self.session_id} sequence numbers reset")

    def validate_seq_num(self, seq_num: int) -> bool:
        """Validate incoming sequence number.

        Args:
            seq_num: Received sequence number.

        Returns:
            True if valid, False if gap detected.
        """
        if seq_num == self.next_target_seq_num:
            self.next_target_seq_num += 1
            return True
        elif seq_num < self.next_target_seq_num:
            # Duplicate or out of order
            logger.warning(
                f"Duplicate/old message: expected {self.next_target_seq_num}, got {seq_num}"
            )
            return False
        else:
            # Gap detected
            logger.warning(
                f"Sequence gap: expected {self.next_target_seq_num}, got {seq_num}"
            )
            return False

    def store_sent_message(self, seq_num: int, message: FIXMessage):
        """Store sent message for potential resend."""
        if self.config.persist_messages:
            self.sent_messages[seq_num] = message

            # Limit memory usage
            if len(self.sent_messages) > self.config.max_messages_in_memory:
                # Remove oldest messages
                oldest_seq = min(self.sent_messages.keys())
                del self.sent_messages[oldest_seq]

    def store_received_message(self, seq_num: int, message: FIXMessage):
        """Store received message."""
        if self.config.persist_messages:
            self.received_messages[seq_num] = message

            # Limit memory usage
            if len(self.received_messages) > self.config.max_messages_in_memory:
                oldest_seq = min(self.received_messages.keys())
                del self.received_messages[oldest_seq]

    def update_heartbeat_sent(self):
        """Update last heartbeat sent time."""
        self.last_heartbeat_sent = datetime.utcnow()
        self.stats.heartbeats_sent += 1

    def update_heartbeat_received(self):
        """Update last heartbeat received time."""
        self.last_heartbeat_received = datetime.utcnow()
        self.stats.heartbeats_received += 1

    def is_heartbeat_required(self) -> bool:
        """Check if heartbeat needs to be sent."""
        if self.state != SessionState.ACTIVE:
            return False

        elapsed = (datetime.utcnow() - self.last_heartbeat_sent).total_seconds()
        return elapsed >= self.config.heartbeat_interval

    def is_connection_alive(self) -> bool:
        """Check if connection is still alive based on heartbeats."""
        if self.state != SessionState.ACTIVE:
            return False

        # Allow 2.5x heartbeat interval before considering connection dead
        timeout = self.config.heartbeat_interval * 2.5
        elapsed = (datetime.utcnow() - self.last_heartbeat_received).total_seconds()
        return elapsed < timeout

    async def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        while self.state == SessionState.ACTIVE:
            try:
                if self.is_heartbeat_required():
                    # Note: Actual heartbeat sending handled by adapter
                    self.update_heartbeat_sent()

                await asyncio.sleep(1)  # Check every second

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")

    async def _monitor_loop(self):
        """Monitor connection health."""
        while self.state == SessionState.ACTIVE:
            try:
                if not self.is_connection_alive():
                    logger.warning(f"Session {self.session_id} heartbeat timeout")
                    self.state = SessionState.ERROR
                    # Trigger reconnection in adapter

                await asyncio.sleep(5)  # Check every 5 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")


class FIXSessionManager:
    """Manages multiple FIX sessions."""

    def __init__(self):
        """Initialize session manager."""
        self.sessions: Dict[str, FIXSession] = {}

    def create_session(
        self,
        session_id: str,
        config: SessionConfig,
        message_callback: Optional[Callable[[FIXMessage], None]] = None,
    ) -> FIXSession:
        """Create new FIX session.

        Args:
            session_id: Unique session identifier.
            config: Session configuration.
            message_callback: Callback for received messages.

        Returns:
            Created FIX session.
        """
        if session_id in self.sessions:
            raise ValueError(f"Session {session_id} already exists")

        session = FIXSession(session_id, config, message_callback)
        self.sessions[session_id] = session

        logger.info(f"Created FIX session: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[FIXSession]:
        """Get session by ID."""
        return self.sessions.get(session_id)

    def remove_session(self, session_id: str):
        """Remove session."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.stop()
            del self.sessions[session_id]
            logger.info(f"Removed FIX session: {session_id}")

    def get_active_sessions(self) -> Dict[str, FIXSession]:
        """Get all active sessions."""
        return {
            sid: session
            for sid, session in self.sessions.items()
            if session.state == SessionState.ACTIVE
        }

    def shutdown(self):
        """Shutdown all sessions."""
        for session in self.sessions.values():
            session.stop()
            session.deactivate()
        self.sessions.clear()
        logger.info("Session manager shutdown complete")
