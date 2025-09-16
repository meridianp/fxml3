"""
Market Session Manager for FXML4 Trading System

This module manages forex market sessions, including London, New York, Tokyo,
and Sydney sessions. It handles session transitions, weekend closures, and
provides real-time market status monitoring to ensure trading operations
only occur during appropriate market hours.

Key Features:
- Real-time market session tracking
- Session transition detection and handling
- Weekend and holiday closure management
- Multi-timezone session coordination
- Liquidity period identification
- Automatic trading suspension during closures

Major Sessions:
- London: 08:00-17:00 GMT (most liquid for EUR/GBP pairs)
- New York: 13:00-22:00 GMT (most liquid for USD pairs)
- Tokyo: 00:00-09:00 GMT (most liquid for JPY pairs)
- Sydney: 22:00-07:00 GMT (start of trading week)

Session Overlaps:
- London/New York: 13:00-17:00 GMT (highest liquidity)
- Tokyo/London: 08:00-09:00 GMT (moderate liquidity)
- Sydney/Tokyo: 00:00-07:00 GMT (lower liquidity)
"""

import asyncio
import json
import logging
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set

import pytz

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Market session status."""

    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    OPEN = "open"
    POST_MARKET = "post_market"
    HOLIDAY = "holiday"
    WEEKEND = "weekend"


class MarketState(Enum):
    """Overall market state."""

    CLOSED = "closed"  # All major sessions closed
    LOW_LIQUIDITY = "low"  # One session open
    MODERATE_LIQUIDITY = "moderate"  # Session transition period
    HIGH_LIQUIDITY = "high"  # Multiple sessions open
    PEAK_LIQUIDITY = "peak"  # London/NY overlap


class SessionType(Enum):
    """Major forex trading sessions."""

    SYDNEY = "sydney"
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"


@dataclass
class MarketSession:
    """Market session definition."""

    session_type: SessionType
    name: str
    timezone: str
    open_time: time  # Local session time
    close_time: time  # Local session time
    currencies: Set[str] = field(default_factory=set)
    is_major: bool = True
    liquidity_weight: float = 1.0

    @property
    def session_id(self) -> str:
        """Get unique session identifier."""
        return f"{self.session_type.value}_{self.timezone.replace('/', '_')}"

    def get_timezone(self) -> pytz.BaseTzInfo:
        """Get timezone object."""
        return pytz.timezone(self.timezone)

    def is_open_at(self, dt: datetime) -> bool:
        """Check if session is open at given datetime."""
        session_tz = self.get_timezone()
        local_time = dt.astimezone(session_tz).time()

        # Handle sessions that cross midnight
        if self.open_time <= self.close_time:
            return self.open_time <= local_time <= self.close_time
        else:
            return local_time >= self.open_time or local_time <= self.close_time


@dataclass
class SessionTransition:
    """Session transition event."""

    timestamp: datetime
    session_type: SessionType
    previous_status: SessionStatus
    new_status: SessionStatus
    market_state: MarketState
    liquidity_change: float
    affected_currencies: Set[str] = field(default_factory=set)


class MarketSessionManager:
    """
    Manages forex market sessions and trading hours.

    Provides real-time monitoring of market sessions, handles transitions,
    and ensures trading operations only occur during appropriate hours.
    """

    def __init__(self):
        self.sessions: Dict[SessionType, MarketSession] = {}
        self.session_status: Dict[SessionType, SessionStatus] = {}
        self.current_market_state = MarketState.CLOSED

        # Transition tracking
        self.transition_history: deque = deque(maxlen=1000)
        self.last_status_check: Optional[datetime] = None

        # Monitoring
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.check_interval_seconds = 30

        # Event handlers
        self.transition_listeners: List[weakref.ReferenceType] = []
        self.state_change_listeners: List[weakref.ReferenceType] = []

        # Weekend and holiday handling
        self.weekend_start_day = 5  # Friday (0=Monday)
        self.weekend_start_hour = 22  # 22:00 GMT Friday
        self.weekend_end_day = 6  # Sunday
        self.weekend_end_hour = 22  # 22:00 GMT Sunday

        # Initialize standard sessions
        self._initialize_standard_sessions()

        logger.info("MarketSessionManager initialized")

    def _initialize_standard_sessions(self) -> None:
        """Initialize standard forex trading sessions."""
        # Sydney Session
        self.sessions[SessionType.SYDNEY] = MarketSession(
            session_type=SessionType.SYDNEY,
            name="Sydney Session",
            timezone="Australia/Sydney",
            open_time=time(7, 0),  # 7:00 AM AEST
            close_time=time(16, 0),  # 4:00 PM AEST
            currencies={"AUD", "NZD"},
            liquidity_weight=0.6,
        )

        # Tokyo Session
        self.sessions[SessionType.TOKYO] = MarketSession(
            session_type=SessionType.TOKYO,
            name="Tokyo Session",
            timezone="Asia/Tokyo",
            open_time=time(9, 0),  # 9:00 AM JST
            close_time=time(18, 0),  # 6:00 PM JST
            currencies={"JPY"},
            liquidity_weight=0.8,
        )

        # London Session
        self.sessions[SessionType.LONDON] = MarketSession(
            session_type=SessionType.LONDON,
            name="London Session",
            timezone="Europe/London",
            open_time=time(8, 0),  # 8:00 AM GMT/BST
            close_time=time(17, 0),  # 5:00 PM GMT/BST
            currencies={"GBP", "EUR", "CHF"},
            liquidity_weight=1.0,
        )

        # New York Session
        self.sessions[SessionType.NEW_YORK] = MarketSession(
            session_type=SessionType.NEW_YORK,
            name="New York Session",
            timezone="America/New_York",
            open_time=time(8, 0),  # 8:00 AM EST/EDT
            close_time=time(17, 0),  # 5:00 PM EST/EDT
            currencies={"USD", "CAD"},
            liquidity_weight=1.0,
        )

        # Initialize all sessions as closed
        for session_type in self.sessions:
            self.session_status[session_type] = SessionStatus.CLOSED

    async def start_monitoring(self) -> None:
        """Start market session monitoring."""
        if self.is_monitoring:
            logger.warning("Market session monitoring already started")
            return

        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())

        # Perform initial status check
        await self._check_all_sessions()

        logger.info("Market session monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop market session monitoring."""
        self.is_monitoring = False

        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Market session monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Starting market session monitoring loop")

        while self.is_monitoring:
            try:
                await self._check_all_sessions()
                await asyncio.sleep(self.check_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session monitoring loop: {e}")
                await asyncio.sleep(self.check_interval_seconds)

        logger.info("Market session monitoring loop stopped")

    async def _check_all_sessions(self) -> None:
        """Check status of all market sessions."""
        current_time = datetime.now(pytz.UTC)
        self.last_status_check = current_time

        # Check if it's weekend
        if self._is_weekend(current_time):
            await self._handle_weekend_closure()
            return

        # Check individual sessions
        transitions = []
        for session_type, session in self.sessions.items():
            new_status = self._get_session_status(session, current_time)
            previous_status = self.session_status[session_type]

            if new_status != previous_status:
                # Create transition event
                transition = SessionTransition(
                    timestamp=current_time,
                    session_type=session_type,
                    previous_status=previous_status,
                    new_status=new_status,
                    market_state=MarketState.CLOSED,  # Will be updated below
                    liquidity_change=0.0,  # Will be calculated below
                    affected_currencies=session.currencies,
                )

                transitions.append(transition)
                self.session_status[session_type] = new_status

                logger.info(
                    f"{session.name}: {previous_status.value} -> {new_status.value}"
                )

        # Update overall market state
        previous_market_state = self.current_market_state
        self.current_market_state = self._calculate_market_state()

        # Update transitions with market state
        for transition in transitions:
            transition.market_state = self.current_market_state
            transition.liquidity_change = self._calculate_liquidity_change(
                transition.session_type,
                transition.previous_status,
                transition.new_status,
            )

            # Record transition
            self.transition_history.append(transition)

            # Notify listeners
            await self._notify_transition_listeners(transition)

        # Notify state change if market state changed
        if self.current_market_state != previous_market_state:
            logger.info(
                f"Market state: {previous_market_state.value} -> {self.current_market_state.value}"
            )
            await self._notify_state_change_listeners()

    def _is_weekend(self, dt: datetime) -> bool:
        """Check if current time is during forex weekend closure."""
        utc_time = dt.astimezone(pytz.UTC)
        weekday = utc_time.weekday()  # 0=Monday, 6=Sunday
        hour = utc_time.hour

        # Weekend starts Friday 22:00 GMT
        if weekday == self.weekend_start_day and hour >= self.weekend_start_hour:
            return True

        # Saturday is always weekend
        if weekday == 6:  # Saturday
            return True

        # Weekend ends Sunday 22:00 GMT
        if weekday == self.weekend_end_day and hour < self.weekend_end_hour:
            return True

        return False

    async def _handle_weekend_closure(self) -> None:
        """Handle weekend market closure."""
        weekend_status = SessionStatus.WEEKEND

        # Set all sessions to weekend status
        for session_type in self.sessions:
            if self.session_status[session_type] != weekend_status:
                previous_status = self.session_status[session_type]
                self.session_status[session_type] = weekend_status

                # Create transition
                transition = SessionTransition(
                    timestamp=datetime.now(pytz.UTC),
                    session_type=session_type,
                    previous_status=previous_status,
                    new_status=weekend_status,
                    market_state=MarketState.CLOSED,
                    liquidity_change=-1.0,  # Complete liquidity loss
                    affected_currencies=self.sessions[session_type].currencies,
                )

                self.transition_history.append(transition)
                await self._notify_transition_listeners(transition)

        # Update market state
        if self.current_market_state != MarketState.CLOSED:
            self.current_market_state = MarketState.CLOSED
            await self._notify_state_change_listeners()

    def _get_session_status(
        self, session: MarketSession, dt: datetime
    ) -> SessionStatus:
        """Get current status for a specific session."""
        if self._is_weekend(dt):
            return SessionStatus.WEEKEND

        # TODO: Add holiday checking here
        # if self._is_holiday(session, dt):
        #     return SessionStatus.HOLIDAY

        # Check if session is open
        if session.is_open_at(dt):
            return SessionStatus.OPEN
        else:
            return SessionStatus.CLOSED

    def _calculate_market_state(self) -> MarketState:
        """Calculate overall market state based on open sessions."""
        open_sessions = [
            session_type
            for session_type, status in self.session_status.items()
            if status == SessionStatus.OPEN
        ]

        if not open_sessions:
            return MarketState.CLOSED

        # Check for London/NY overlap (highest liquidity)
        if (
            SessionType.LONDON in open_sessions
            and SessionType.NEW_YORK in open_sessions
        ):
            return MarketState.PEAK_LIQUIDITY

        # Multiple major sessions open
        major_sessions = [s for s in open_sessions if self.sessions[s].is_major]
        if len(major_sessions) >= 2:
            return MarketState.HIGH_LIQUIDITY
        elif len(major_sessions) == 1:
            # Single major session
            if major_sessions[0] in [SessionType.LONDON, SessionType.NEW_YORK]:
                return MarketState.HIGH_LIQUIDITY
            else:
                return MarketState.MODERATE_LIQUIDITY
        else:
            return MarketState.LOW_LIQUIDITY

    def _calculate_liquidity_change(
        self,
        session_type: SessionType,
        previous_status: SessionStatus,
        new_status: SessionStatus,
    ) -> float:
        """Calculate liquidity change for session transition."""
        session = self.sessions[session_type]
        base_liquidity = session.liquidity_weight

        if previous_status == SessionStatus.CLOSED and new_status == SessionStatus.OPEN:
            return base_liquidity  # Liquidity increase
        elif (
            previous_status == SessionStatus.OPEN and new_status == SessionStatus.CLOSED
        ):
            return -base_liquidity  # Liquidity decrease
        else:
            return 0.0  # No significant change

    def is_market_open(self) -> bool:
        """Check if any major market session is currently open."""
        return self.current_market_state not in [MarketState.CLOSED]

    def is_trading_allowed(self) -> bool:
        """Check if trading should be allowed in current market conditions."""
        return self.current_market_state in [
            MarketState.MODERATE_LIQUIDITY,
            MarketState.HIGH_LIQUIDITY,
            MarketState.PEAK_LIQUIDITY,
        ]

    def get_open_sessions(self) -> List[SessionType]:
        """Get list of currently open sessions."""
        return [
            session_type
            for session_type, status in self.session_status.items()
            if status == SessionStatus.OPEN
        ]

    def get_session_overlap_info(self) -> Dict[str, Any]:
        """Get information about current session overlaps."""
        open_sessions = self.get_open_sessions()

        if not open_sessions:
            return {"overlap": False, "sessions": [], "liquidity_level": "none"}

        overlap_info = {
            "overlap": len(open_sessions) > 1,
            "sessions": [session.value for session in open_sessions],
            "session_count": len(open_sessions),
        }

        # Determine liquidity level
        if (
            SessionType.LONDON in open_sessions
            and SessionType.NEW_YORK in open_sessions
        ):
            overlap_info["liquidity_level"] = "peak"
            overlap_info["overlap_name"] = "London/New York"
        elif len(open_sessions) >= 2:
            overlap_info["liquidity_level"] = "high"
            overlap_info["overlap_name"] = (
                f"{'/'.join([s.value.title() for s in open_sessions])}"
            )
        elif len(open_sessions) == 1:
            overlap_info["liquidity_level"] = "moderate"
            overlap_info["overlap_name"] = open_sessions[0].value.title()
        else:
            overlap_info["liquidity_level"] = "low"

        return overlap_info

    def get_next_session_event(self) -> Optional[Dict[str, Any]]:
        """Get information about the next session opening/closing."""
        current_time = datetime.now(pytz.UTC)
        next_events = []

        # Check next 24 hours for session events
        for hour_offset in range(24):
            check_time = current_time + timedelta(hours=hour_offset)

            # Skip if weekend
            if self._is_weekend(check_time):
                continue

            for session_type, session in self.sessions.items():
                current_status = self._get_session_status(session, current_time)
                future_status = self._get_session_status(session, check_time)

                if current_status != future_status:
                    next_events.append(
                        {
                            "time": check_time,
                            "session": session_type.value,
                            "session_name": session.name,
                            "event_type": (
                                "opening"
                                if future_status == SessionStatus.OPEN
                                else "closing"
                            ),
                            "status_change": f"{current_status.value} -> {future_status.value}",
                            "hours_from_now": hour_offset,
                        }
                    )

        if next_events:
            # Return the earliest event
            next_events.sort(key=lambda x: x["time"])
            return next_events[0]

        return None

    def get_session_status_summary(self) -> Dict[str, Any]:
        """Get comprehensive session status summary."""
        current_time = datetime.now(pytz.UTC)

        session_details = {}
        for session_type, session in self.sessions.items():
            status = self.session_status[session_type]

            session_details[session_type.value] = {
                "name": session.name,
                "status": status.value,
                "timezone": session.timezone,
                "currencies": list(session.currencies),
                "liquidity_weight": session.liquidity_weight,
                "is_major": session.is_major,
            }

        overlap_info = self.get_session_overlap_info()
        next_event = self.get_next_session_event()

        return {
            "timestamp": current_time.isoformat(),
            "market_state": self.current_market_state.value,
            "market_open": self.is_market_open(),
            "trading_allowed": self.is_trading_allowed(),
            "is_weekend": self._is_weekend(current_time),
            "sessions": session_details,
            "overlap_info": overlap_info,
            "next_session_event": next_event,
            "monitoring_active": self.is_monitoring,
            "last_status_check": (
                self.last_status_check.isoformat() if self.last_status_check else None
            ),
        }

    def get_transition_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent session transition history."""
        recent_transitions = list(self.transition_history)[-limit:]

        return [
            {
                "timestamp": transition.timestamp.isoformat(),
                "session": transition.session_type.value,
                "previous_status": transition.previous_status.value,
                "new_status": transition.new_status.value,
                "market_state": transition.market_state.value,
                "liquidity_change": transition.liquidity_change,
                "affected_currencies": list(transition.affected_currencies),
            }
            for transition in recent_transitions
        ]

    async def add_transition_listener(self, callback: Callable) -> None:
        """Add session transition listener."""
        self.transition_listeners.append(weakref.ref(callback))

    async def add_state_change_listener(self, callback: Callable) -> None:
        """Add market state change listener."""
        self.state_change_listeners.append(weakref.ref(callback))

    async def _notify_transition_listeners(self, transition: SessionTransition) -> None:
        """Notify transition listeners."""
        for listener_ref in self.transition_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.transition_listeners.remove(listener_ref)
            else:
                try:
                    await listener(transition)
                except Exception as e:
                    logger.error(f"Transition listener error: {e}")

    async def _notify_state_change_listeners(self) -> None:
        """Notify state change listeners."""
        for listener_ref in self.state_change_listeners[:]:
            listener = listener_ref()
            if listener is None:
                self.state_change_listeners.remove(listener_ref)
            else:
                try:
                    await listener(self.current_market_state)
                except Exception as e:
                    logger.error(f"State change listener error: {e}")

    def force_session_status_check(self) -> Dict[str, Any]:
        """Force an immediate session status check."""
        logger.info("Forcing session status check")

        # Use asyncio.create_task to run async function in sync context
        async def _check():
            await self._check_all_sessions()
            return self.get_session_status_summary()

        # This is a bit of a hack, but needed for sync interface
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If there's already a running loop, we can't use run_until_complete
                asyncio.create_task(_check())
                return self.get_session_status_summary()
            else:
                return loop.run_until_complete(_check())
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(_check())
