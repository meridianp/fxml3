"""
FXML4 Session Calendar

Manages trading hours, holiday schedules, and special market conditions
for comprehensive forex market session management.
"""

import logging
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import pytz

# Configure logging
logger = logging.getLogger(__name__)


class SessionType(Enum):
    """Trading session types"""

    SYDNEY = "sydney"
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"


class HolidayType(Enum):
    """Holiday classification types"""

    BANK_HOLIDAY = "bank_holiday"
    NATIONAL_HOLIDAY = "national_holiday"
    MARKET_CLOSURE = "market_closure"
    EARLY_CLOSE = "early_close"
    LATE_OPEN = "late_open"


@dataclass
class TradingSession:
    """Detailed trading session configuration"""

    session_type: SessionType
    name: str
    timezone: str
    open_time: str  # Format: "HH:MM"
    close_time: str  # Format: "HH:MM"
    trading_days: Set[int] = field(default_factory=lambda: {0, 1, 2, 3, 4})  # Mon-Fri
    dst_aware: bool = True
    liquidity_profile: Dict[str, float] = field(default_factory=dict)
    volatility_profile: Dict[str, float] = field(default_factory=dict)
    major_currency_pairs: Set[str] = field(default_factory=set)


@dataclass
class SessionOverlap:
    """Represents overlapping trading sessions"""

    primary_session: SessionType
    secondary_session: SessionType
    overlap_start: str  # Format: "HH:MM"
    overlap_end: str  # Format: "HH:MM"
    timezone: str
    liquidity_multiplier: float
    volatility_multiplier: float
    peak_hours: bool = False


@dataclass
class MarketHoliday:
    """Market holiday definition"""

    name: str
    date: date
    holiday_type: HolidayType
    affected_sessions: Set[SessionType]
    description: str = ""
    early_close_time: Optional[str] = None  # Format: "HH:MM"
    late_open_time: Optional[str] = None  # Format: "HH:MM"
    trading_impact: str = (
        "full_closure"  # full_closure, early_close, late_open, reduced_hours
    )


class SessionCalendar:
    """
    Comprehensive session calendar managing trading hours,
    holidays, and special market conditions
    """

    def __init__(self):
        """Initialize session calendar with standard configurations"""
        self.sessions: Dict[SessionType, TradingSession] = {}
        self.overlaps: List[SessionOverlap] = []
        self.holidays: Dict[str, List[MarketHoliday]] = {}  # year -> holidays

        # Initialize standard sessions
        self._initialize_standard_sessions()
        self._initialize_session_overlaps()
        self._initialize_standard_holidays()

        logger.info("Session Calendar initialized with standard configurations")

    def _initialize_standard_sessions(self) -> None:
        """Initialize standard forex trading sessions with detailed configurations"""

        # Sydney Session (22:00-06:00 AEDT)
        self.sessions[SessionType.SYDNEY] = TradingSession(
            session_type=SessionType.SYDNEY,
            name="Sydney Session",
            timezone="Australia/Sydney",
            open_time="22:00",
            close_time="06:00",
            trading_days={0, 1, 2, 3, 4},  # Monday-Friday
            dst_aware=True,
            liquidity_profile={
                "22:00": 0.4,
                "23:00": 0.5,
                "00:00": 0.6,
                "01:00": 0.7,
                "02:00": 0.6,
                "03:00": 0.5,
                "04:00": 0.4,
                "05:00": 0.3,
            },
            volatility_profile={
                "22:00": 0.6,
                "23:00": 0.7,
                "00:00": 0.8,
                "01:00": 0.9,
                "02:00": 0.8,
                "03:00": 0.7,
                "04:00": 0.6,
                "05:00": 0.5,
            },
            major_currency_pairs={"AUDUSD", "NZDUSD", "AUDJPY", "AUDCAD"},
        )

        # Tokyo Session (09:00-17:00 JST)
        self.sessions[SessionType.TOKYO] = TradingSession(
            session_type=SessionType.TOKYO,
            name="Tokyo Session",
            timezone="Asia/Tokyo",
            open_time="09:00",
            close_time="17:00",
            trading_days={0, 1, 2, 3, 4},  # Monday-Friday
            dst_aware=False,  # Japan doesn't observe DST
            liquidity_profile={
                "09:00": 0.7,
                "10:00": 0.8,
                "11:00": 0.9,
                "12:00": 0.8,
                "13:00": 0.9,
                "14:00": 1.0,
                "15:00": 0.9,
                "16:00": 0.8,
            },
            volatility_profile={
                "09:00": 0.8,
                "10:00": 0.9,
                "11:00": 1.0,
                "12:00": 0.8,
                "13:00": 0.9,
                "14:00": 1.1,
                "15:00": 1.0,
                "16:00": 0.9,
            },
            major_currency_pairs={"USDJPY", "AUDJPY", "GBPJPY", "EURJPY"},
        )

        # London Session (08:00-16:00 GMT/BST)
        self.sessions[SessionType.LONDON] = TradingSession(
            session_type=SessionType.LONDON,
            name="London Session",
            timezone="Europe/London",
            open_time="08:00",
            close_time="16:00",
            trading_days={0, 1, 2, 3, 4},  # Monday-Friday
            dst_aware=True,
            liquidity_profile={
                "08:00": 1.0,
                "09:00": 1.2,
                "10:00": 1.3,
                "11:00": 1.4,
                "12:00": 1.3,
                "13:00": 1.5,
                "14:00": 1.6,
                "15:00": 1.4,
            },
            volatility_profile={
                "08:00": 1.0,
                "09:00": 1.1,
                "10:00": 1.2,
                "11:00": 1.3,
                "12:00": 1.2,
                "13:00": 1.4,
                "14:00": 1.5,
                "15:00": 1.3,
            },
            major_currency_pairs={"GBPUSD", "EURUSD", "EURGBP", "GBPJPY"},
        )

        # New York Session (13:00-21:00 EST/EDT)
        self.sessions[SessionType.NEW_YORK] = TradingSession(
            session_type=SessionType.NEW_YORK,
            name="New York Session",
            timezone="America/New_York",
            open_time="13:00",
            close_time="21:00",
            trading_days={0, 1, 2, 3, 4},  # Monday-Friday
            dst_aware=True,
            liquidity_profile={
                "13:00": 1.0,
                "14:00": 1.3,
                "15:00": 1.4,
                "16:00": 1.2,
                "17:00": 1.1,
                "18:00": 1.0,
                "19:00": 0.9,
                "20:00": 0.8,
            },
            volatility_profile={
                "13:00": 1.0,
                "14:00": 1.2,
                "15:00": 1.3,
                "16:00": 1.1,
                "17:00": 1.0,
                "18:00": 0.9,
                "19:00": 0.8,
                "20:00": 0.7,
            },
            major_currency_pairs={"GBPUSD", "EURUSD", "USDCAD", "USDJPY"},
        )

        logger.info("Standard trading sessions initialized")

    def _initialize_session_overlaps(self) -> None:
        """Initialize standard session overlaps"""

        # Sydney-Tokyo Overlap
        self.overlaps.append(
            SessionOverlap(
                primary_session=SessionType.SYDNEY,
                secondary_session=SessionType.TOKYO,
                overlap_start="09:00",  # Tokyo time
                overlap_end="06:00",  # Sydney time (next day)
                timezone="Asia/Tokyo",
                liquidity_multiplier=1.3,
                volatility_multiplier=1.2,
                peak_hours=False,
            )
        )

        # Tokyo-London Overlap
        self.overlaps.append(
            SessionOverlap(
                primary_session=SessionType.TOKYO,
                secondary_session=SessionType.LONDON,
                overlap_start="08:00",  # London time
                overlap_end="17:00",  # Tokyo time
                timezone="Europe/London",
                liquidity_multiplier=1.4,
                volatility_multiplier=1.3,
                peak_hours=False,
            )
        )

        # London-New York Overlap (PEAK LIQUIDITY)
        self.overlaps.append(
            SessionOverlap(
                primary_session=SessionType.LONDON,
                secondary_session=SessionType.NEW_YORK,
                overlap_start="13:00",  # GMT (NY opens)
                overlap_end="16:00",  # GMT (London closes)
                timezone="UTC",
                liquidity_multiplier=2.0,
                volatility_multiplier=1.8,
                peak_hours=True,
            )
        )

        logger.info("Session overlaps initialized")

    def _initialize_standard_holidays(self) -> None:
        """Initialize standard market holidays for major financial centers"""

        # Initialize holidays for current and next year
        current_year = datetime.now().year
        for year in [current_year, current_year + 1]:
            self.holidays[str(year)] = self._get_holidays_for_year(year)

        logger.info(
            f"Standard holidays initialized for years {current_year}-{current_year + 1}"
        )

    def _get_holidays_for_year(self, year: int) -> List[MarketHoliday]:
        """Get standard market holidays for a specific year"""
        holidays = []

        # New Year's Day
        holidays.append(
            MarketHoliday(
                name="New Year's Day",
                date=date(year, 1, 1),
                holiday_type=HolidayType.NATIONAL_HOLIDAY,
                affected_sessions={
                    SessionType.LONDON,
                    SessionType.NEW_YORK,
                    SessionType.SYDNEY,
                },
                description="Global market closure for New Year's Day",
            )
        )

        # Good Friday (calculated)
        good_friday = self._calculate_good_friday(year)
        holidays.append(
            MarketHoliday(
                name="Good Friday",
                date=good_friday,
                holiday_type=HolidayType.BANK_HOLIDAY,
                affected_sessions={
                    SessionType.LONDON,
                    SessionType.NEW_YORK,
                    SessionType.SYDNEY,
                },
                description="Christian holiday - market closure",
            )
        )

        # Easter Monday (day after Easter Sunday)
        easter_monday = good_friday + timedelta(days=3)
        holidays.append(
            MarketHoliday(
                name="Easter Monday",
                date=easter_monday,
                holiday_type=HolidayType.BANK_HOLIDAY,
                affected_sessions={SessionType.LONDON, SessionType.SYDNEY},
                description="Bank holiday in UK and Australia",
            )
        )

        # US Independence Day
        holidays.append(
            MarketHoliday(
                name="Independence Day",
                date=date(year, 7, 4),
                holiday_type=HolidayType.NATIONAL_HOLIDAY,
                affected_sessions={SessionType.NEW_YORK},
                description="US national holiday",
            )
        )

        # Christmas Day
        holidays.append(
            MarketHoliday(
                name="Christmas Day",
                date=date(year, 12, 25),
                holiday_type=HolidayType.NATIONAL_HOLIDAY,
                affected_sessions={
                    SessionType.LONDON,
                    SessionType.NEW_YORK,
                    SessionType.SYDNEY,
                },
                description="Global market closure for Christmas",
            )
        )

        # Boxing Day
        holidays.append(
            MarketHoliday(
                name="Boxing Day",
                date=date(year, 12, 26),
                holiday_type=HolidayType.BANK_HOLIDAY,
                affected_sessions={SessionType.LONDON, SessionType.SYDNEY},
                description="Bank holiday in UK and Australia",
            )
        )

        # Thanksgiving (4th Thursday in November)
        thanksgiving = self._calculate_thanksgiving(year)
        holidays.append(
            MarketHoliday(
                name="Thanksgiving Day",
                date=thanksgiving,
                holiday_type=HolidayType.NATIONAL_HOLIDAY,
                affected_sessions={SessionType.NEW_YORK},
                description="US national holiday",
                early_close_time="18:00",  # Early close at 1 PM ET
            )
        )

        # Day after Thanksgiving (Black Friday)
        black_friday = thanksgiving + timedelta(days=1)
        holidays.append(
            MarketHoliday(
                name="Day after Thanksgiving",
                date=black_friday,
                holiday_type=HolidayType.EARLY_CLOSE,
                affected_sessions={SessionType.NEW_YORK},
                description="Early close in US markets",
                early_close_time="18:00",  # Early close at 1 PM ET
            )
        )

        return holidays

    def _calculate_good_friday(self, year: int) -> date:
        """Calculate Good Friday date for a given year"""
        # Easter calculation using anonymous Gregorian algorithm
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1

        easter_sunday = date(year, month, day)
        good_friday = easter_sunday - timedelta(days=2)
        return good_friday

    def _calculate_thanksgiving(self, year: int) -> date:
        """Calculate Thanksgiving date (4th Thursday in November)"""
        # First day of November
        first_nov = date(year, 11, 1)
        # Find first Thursday
        days_to_thursday = (3 - first_nov.weekday()) % 7
        first_thursday = first_nov + timedelta(days=days_to_thursday)
        # Fourth Thursday
        fourth_thursday = first_thursday + timedelta(weeks=3)
        return fourth_thursday

    def is_trading_day(self, check_date: date, session_type: SessionType) -> bool:
        """
        Check if a specific date is a trading day for a session

        Args:
            check_date: Date to check
            session_type: Session type to check

        Returns:
            True if it's a trading day
        """
        if session_type not in self.sessions:
            return False

        session = self.sessions[session_type]

        # Check if it's a regular trading day (Monday-Friday typically)
        if check_date.weekday() not in session.trading_days:
            return False

        # Check for holidays
        year_str = str(check_date.year)
        if year_str in self.holidays:
            for holiday in self.holidays[year_str]:
                if (
                    holiday.date == check_date
                    and session_type in holiday.affected_sessions
                ):
                    return False

        return True

    def get_session_hours(
        self, session_type: SessionType, check_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        Get trading hours for a specific session and date

        Args:
            session_type: Session type
            check_date: Date to get hours for

        Returns:
            Session hours information or None if closed
        """
        if not self.is_trading_day(check_date, session_type):
            return None

        if session_type not in self.sessions:
            return None

        session = self.sessions[session_type]

        # Check for holiday modifications
        modified_hours = self._get_holiday_modified_hours(session_type, check_date)
        if modified_hours:
            return modified_hours

        # Standard hours
        return {
            "session_type": session_type.value,
            "open_time": session.open_time,
            "close_time": session.close_time,
            "timezone": session.timezone,
            "is_standard": True,
            "modifications": None,
        }

    def _get_holiday_modified_hours(
        self, session_type: SessionType, check_date: date
    ) -> Optional[Dict[str, Any]]:
        """Get holiday-modified trading hours"""
        year_str = str(check_date.year)
        if year_str not in self.holidays:
            return None

        for holiday in self.holidays[year_str]:
            if (
                holiday.date == check_date
                and session_type in holiday.affected_sessions
                and holiday.trading_impact != "full_closure"
            ):

                session = self.sessions[session_type]

                return {
                    "session_type": session_type.value,
                    "open_time": holiday.late_open_time or session.open_time,
                    "close_time": holiday.early_close_time or session.close_time,
                    "timezone": session.timezone,
                    "is_standard": False,
                    "modifications": {
                        "holiday_name": holiday.name,
                        "modification_type": holiday.trading_impact,
                        "early_close": holiday.early_close_time,
                        "late_open": holiday.late_open_time,
                    },
                }

        return None

    def get_active_overlaps(self, current_time: datetime) -> List[SessionOverlap]:
        """
        Get currently active session overlaps

        Args:
            current_time: Current time to check

        Returns:
            List of active session overlaps
        """
        active_overlaps = []

        for overlap in self.overlaps:
            if self._is_overlap_active(overlap, current_time):
                active_overlaps.append(overlap)

        return active_overlaps

    def _is_overlap_active(
        self, overlap: SessionOverlap, current_time: datetime
    ) -> bool:
        """Check if a specific overlap is currently active"""
        # Convert current time to overlap timezone
        overlap_tz = pytz.timezone(overlap.timezone)
        local_time = current_time.astimezone(overlap_tz)

        # Check if both sessions are active
        primary_active = self._is_session_active_at_time(
            overlap.primary_session, current_time
        )
        secondary_active = self._is_session_active_at_time(
            overlap.secondary_session, current_time
        )

        return primary_active and secondary_active

    def _is_session_active_at_time(
        self, session_type: SessionType, current_time: datetime
    ) -> bool:
        """Check if a session is active at a specific time"""
        if session_type not in self.sessions:
            return False

        session = self.sessions[session_type]
        session_tz = pytz.timezone(session.timezone)
        local_time = current_time.astimezone(session_tz)

        # Check if it's a trading day
        if not self.is_trading_day(local_time.date(), session_type):
            return False

        # Check session hours
        current_hour_minute = local_time.strftime("%H:%M")
        session_hours = self.get_session_hours(session_type, local_time.date())

        if not session_hours:
            return False

        open_time = session_hours["open_time"]
        close_time = session_hours["close_time"]

        # Handle overnight sessions
        if open_time > close_time:
            return current_hour_minute >= open_time or current_hour_minute <= close_time
        else:
            return open_time <= current_hour_minute <= close_time

    def get_liquidity_factor(
        self, session_type: SessionType, current_time: datetime
    ) -> float:
        """
        Get liquidity factor for a session at current time

        Args:
            session_type: Session type
            current_time: Current time

        Returns:
            Liquidity factor (1.0 = normal)
        """
        if session_type not in self.sessions:
            return 0.0

        session = self.sessions[session_type]
        session_tz = pytz.timezone(session.timezone)
        local_time = current_time.astimezone(session_tz)

        hour_key = local_time.strftime("%H:00")

        # Get base liquidity from session profile
        base_liquidity = session.liquidity_profile.get(hour_key, 1.0)

        # Apply overlap multipliers
        active_overlaps = self.get_active_overlaps(current_time)
        overlap_multiplier = 1.0

        for overlap in active_overlaps:
            if (
                overlap.primary_session == session_type
                or overlap.secondary_session == session_type
            ):
                overlap_multiplier *= overlap.liquidity_multiplier

        return base_liquidity * overlap_multiplier

    def get_volatility_factor(
        self, session_type: SessionType, current_time: datetime
    ) -> float:
        """
        Get volatility factor for a session at current time

        Args:
            session_type: Session type
            current_time: Current time

        Returns:
            Volatility factor (1.0 = normal)
        """
        if session_type not in self.sessions:
            return 0.0

        session = self.sessions[session_type]
        session_tz = pytz.timezone(session.timezone)
        local_time = current_time.astimezone(session_tz)

        hour_key = local_time.strftime("%H:00")

        # Get base volatility from session profile
        base_volatility = session.volatility_profile.get(hour_key, 1.0)

        # Apply overlap multipliers
        active_overlaps = self.get_active_overlaps(current_time)
        overlap_multiplier = 1.0

        for overlap in active_overlaps:
            if (
                overlap.primary_session == session_type
                or overlap.secondary_session == session_type
            ):
                overlap_multiplier *= overlap.volatility_multiplier

        return base_volatility * overlap_multiplier

    def get_calendar_summary(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Get comprehensive calendar summary for date range

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Calendar summary with trading days, holidays, and sessions
        """
        summary = {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_days": (end_date - start_date).days + 1,
            },
            "trading_days_by_session": {},
            "holidays": [],
            "session_overlaps": len(self.overlaps),
            "peak_liquidity_days": 0,
        }

        # Analyze each session
        for session_type in self.sessions.keys():
            trading_days = []
            current_date = start_date

            while current_date <= end_date:
                if self.is_trading_day(current_date, session_type):
                    trading_days.append(current_date.isoformat())
                current_date += timedelta(days=1)

            summary["trading_days_by_session"][session_type.value] = {
                "count": len(trading_days),
                "dates": trading_days,
            }

        # Get holidays in date range
        current_date = start_date
        while current_date <= end_date:
            year_str = str(current_date.year)
            if year_str in self.holidays:
                for holiday in self.holidays[year_str]:
                    if start_date <= holiday.date <= end_date:
                        summary["holidays"].append(
                            {
                                "name": holiday.name,
                                "date": holiday.date.isoformat(),
                                "type": holiday.holiday_type.value,
                                "affected_sessions": [
                                    s.value for s in holiday.affected_sessions
                                ],
                                "trading_impact": holiday.trading_impact,
                            }
                        )
            current_date += timedelta(days=1)

        # Count peak liquidity periods (London/NY overlap days)
        current_date = start_date
        while current_date <= end_date:
            if self.is_trading_day(
                current_date, SessionType.LONDON
            ) and self.is_trading_day(current_date, SessionType.NEW_YORK):
                summary["peak_liquidity_days"] += 1
            current_date += timedelta(days=1)

        return summary

    def add_custom_holiday(self, holiday: MarketHoliday) -> None:
        """Add a custom holiday to the calendar"""
        year_str = str(holiday.date.year)

        if year_str not in self.holidays:
            self.holidays[year_str] = []

        self.holidays[year_str].append(holiday)
        logger.info(f"Added custom holiday: {holiday.name} on {holiday.date}")

    def remove_holiday(self, holiday_date: date, holiday_name: str) -> bool:
        """Remove a holiday from the calendar"""
        year_str = str(holiday_date.year)

        if year_str not in self.holidays:
            return False

        for i, holiday in enumerate(self.holidays[year_str]):
            if holiday.date == holiday_date and holiday.name == holiday_name:
                del self.holidays[year_str][i]
                logger.info(f"Removed holiday: {holiday_name} on {holiday_date}")
                return True

        return False

    def get_next_trading_day(
        self, current_date: date, session_type: SessionType
    ) -> Optional[date]:
        """
        Get next trading day for a specific session

        Args:
            current_date: Starting date
            session_type: Session type

        Returns:
            Next trading day or None if not found within 30 days
        """
        check_date = current_date + timedelta(days=1)
        max_check_date = current_date + timedelta(days=30)

        while check_date <= max_check_date:
            if self.is_trading_day(check_date, session_type):
                return check_date
            check_date += timedelta(days=1)

        return None

    def get_previous_trading_day(
        self, current_date: date, session_type: SessionType
    ) -> Optional[date]:
        """
        Get previous trading day for a specific session

        Args:
            current_date: Starting date
            session_type: Session type

        Returns:
            Previous trading day or None if not found within 30 days
        """
        check_date = current_date - timedelta(days=1)
        min_check_date = current_date - timedelta(days=30)

        while check_date >= min_check_date:
            if self.is_trading_day(check_date, session_type):
                return check_date
            check_date -= timedelta(days=1)

        return None
