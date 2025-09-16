"""
FXML4 Weekend Holiday Handler

Specialized handler for non-trading periods including weekends,
holidays, and other market closures.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import pytz

from .session_calendar import HolidayType, MarketHoliday, SessionCalendar, SessionType

# Configure logging
logger = logging.getLogger(__name__)


class ClosureType(Enum):
    """Types of market closures"""

    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"
    EARLY_CLOSE = "early_close"
    LATE_OPEN = "late_open"


@dataclass
class WeekendSchedule:
    """Weekend closure schedule configuration"""

    start_day: int  # 4 = Friday
    start_hour: int  # 22 = 22:00
    end_day: int  # 6 = Sunday
    end_hour: int  # 22 = 22:00
    start_minute: int = 0
    end_minute: int = 0
    timezone: str = "UTC"
    description: str = "Standard forex weekend closure"


@dataclass
class HolidaySchedule:
    """Holiday schedule with impact assessment"""

    holiday: MarketHoliday
    pre_holiday_impact: bool = False
    post_holiday_impact: bool = False
    liquidity_impact_factor: float = 1.0  # Multiplier for liquidity
    volatility_impact_factor: float = 1.0  # Multiplier for volatility
    trading_volume_impact: float = 1.0  # Expected volume impact


class WeekendHolidayHandler:
    """
    Comprehensive handler for weekend and holiday market closures
    with impact assessment and business continuity planning
    """

    def __init__(self, session_calendar: Optional[SessionCalendar] = None):
        """
        Initialize weekend holiday handler

        Args:
            session_calendar: Session calendar instance
        """
        self.session_calendar = session_calendar or SessionCalendar()

        # Weekend configuration
        self.weekend_schedule = WeekendSchedule(
            start_day=4,  # Friday
            start_hour=22,  # 22:00 GMT
            start_minute=0,
            end_day=6,  # Sunday
            end_hour=22,  # 22:00 GMT
            end_minute=0,
            timezone="UTC",
            description="Standard forex weekend closure (Friday 22:00 GMT - Sunday 22:00 GMT)",
        )

        # Emergency closures tracking
        self.emergency_closures: List[Dict[str, Any]] = []
        self.maintenance_windows: List[Dict[str, Any]] = []

        # Impact assessment cache
        self._impact_cache: Dict[str, Any] = {}
        self._cache_expiry: Optional[datetime] = None

        logger.info("Weekend Holiday Handler initialized")

    def is_weekend_closure(self, check_time: datetime) -> bool:
        """
        Check if given time falls within weekend closure period

        Args:
            check_time: Time to check

        Returns:
            True if within weekend closure
        """
        # Convert to configured timezone
        tz = pytz.timezone(self.weekend_schedule.timezone)
        local_time = check_time.astimezone(tz)

        weekday = local_time.weekday()
        hour = local_time.hour
        minute = local_time.minute

        # Weekend starts Friday at configured time
        if weekday == self.weekend_schedule.start_day and (
            hour > self.weekend_schedule.start_hour
            or (
                hour == self.weekend_schedule.start_hour
                and minute >= self.weekend_schedule.start_minute
            )
        ):
            return True

        # All of Saturday
        if weekday == 5:  # Saturday
            return True

        # Sunday until configured end time
        if weekday == self.weekend_schedule.end_day and (
            hour < self.weekend_schedule.end_hour
            or (
                hour == self.weekend_schedule.end_hour
                and minute < self.weekend_schedule.end_minute
            )
        ):
            return True

        return False

    def get_weekend_closure_info(self, check_time: datetime) -> Dict[str, Any]:
        """
        Get detailed weekend closure information

        Args:
            check_time: Time to check

        Returns:
            Weekend closure details
        """
        is_weekend = self.is_weekend_closure(check_time)

        if is_weekend:
            next_open = self.get_next_market_open(check_time)
            closure_duration = next_open - check_time if next_open else None

            return {
                "is_weekend_closure": True,
                "closure_type": ClosureType.WEEKEND,
                "current_time": check_time.isoformat(),
                "next_market_open": next_open.isoformat() if next_open else None,
                "closure_duration_hours": (
                    closure_duration.total_seconds() / 3600
                    if closure_duration
                    else None
                ),
                "weekend_schedule": {
                    "start": f"{self.weekend_schedule.start_day} {self.weekend_schedule.start_hour:02d}:{self.weekend_schedule.start_minute:02d}",
                    "end": f"{self.weekend_schedule.end_day} {self.weekend_schedule.end_hour:02d}:{self.weekend_schedule.end_minute:02d}",
                    "timezone": self.weekend_schedule.timezone,
                },
            }
        else:
            return {
                "is_weekend_closure": False,
                "current_time": check_time.isoformat(),
                "next_weekend_start": self.get_next_weekend_start(
                    check_time
                ).isoformat(),
            }

    def get_next_market_open(self, current_time: datetime) -> Optional[datetime]:
        """
        Get next market opening time after current time

        Args:
            current_time: Current time

        Returns:
            Next market opening datetime or None
        """
        # If it's weekend, calculate Sunday 22:00 GMT
        if self.is_weekend_closure(current_time):
            tz = pytz.timezone(self.weekend_schedule.timezone)
            local_time = current_time.astimezone(tz)

            # Find next Sunday
            days_until_sunday = (6 - local_time.weekday()) % 7
            if (
                days_until_sunday == 0
                and local_time.hour >= self.weekend_schedule.end_hour
            ):
                days_until_sunday = 7  # Next Sunday

            next_sunday = local_time.date() + timedelta(days=days_until_sunday)

            # Market opens Sunday at configured time
            market_open = datetime.combine(
                next_sunday,
                time(self.weekend_schedule.end_hour, self.weekend_schedule.end_minute),
            ).replace(tzinfo=tz)

            return market_open.astimezone(pytz.UTC)

        # Check for holiday closures
        current_date = current_time.date()

        # Look ahead for next trading day
        for days_ahead in range(1, 8):  # Check next 7 days
            check_date = current_date + timedelta(days=days_ahead)

            # Skip weekends
            if check_date.weekday() >= 5:
                continue

            # Check if any major session is trading
            for session_type in [
                SessionType.LONDON,
                SessionType.NEW_YORK,
                SessionType.TOKYO,
            ]:
                if self.session_calendar.is_trading_day(check_date, session_type):
                    session_hours = self.session_calendar.get_session_hours(
                        session_type, check_date
                    )
                    if session_hours:
                        # Return session open time
                        session_tz = pytz.timezone(session_hours["timezone"])
                        open_time_parts = session_hours["open_time"].split(":")
                        open_time = datetime.combine(
                            check_date,
                            time(int(open_time_parts[0]), int(open_time_parts[1])),
                        ).replace(tzinfo=session_tz)

                        return open_time.astimezone(pytz.UTC)

        return None

    def get_next_weekend_start(self, current_time: datetime) -> datetime:
        """
        Get next weekend start time

        Args:
            current_time: Current time

        Returns:
            Next weekend start datetime
        """
        tz = pytz.timezone(self.weekend_schedule.timezone)
        local_time = current_time.astimezone(tz)

        # Find next Friday
        days_until_friday = (4 - local_time.weekday()) % 7
        if days_until_friday == 0:  # Today is Friday
            if local_time.hour < self.weekend_schedule.start_hour or (
                local_time.hour == self.weekend_schedule.start_hour
                and local_time.minute < self.weekend_schedule.start_minute
            ):
                # Weekend hasn't started yet today
                next_friday = local_time.date()
            else:
                # Weekend already started, get next Friday
                next_friday = local_time.date() + timedelta(days=7)
        elif days_until_friday == 0:
            days_until_friday = 7  # Next Friday
        else:
            next_friday = local_time.date() + timedelta(days=days_until_friday)

        weekend_start = datetime.combine(
            next_friday,
            time(self.weekend_schedule.start_hour, self.weekend_schedule.start_minute),
        ).replace(tzinfo=tz)

        return weekend_start.astimezone(pytz.UTC)

    def is_holiday_closure(
        self, check_time: datetime, session_type: SessionType
    ) -> bool:
        """
        Check if given time is during holiday closure for session

        Args:
            check_time: Time to check
            session_type: Session to check

        Returns:
            True if during holiday closure
        """
        return not self.session_calendar.is_trading_day(check_time.date(), session_type)

    def get_holiday_impact_assessment(
        self, check_date: date, session_type: SessionType
    ) -> Dict[str, Any]:
        """
        Assess holiday impact on trading for specific date and session

        Args:
            check_date: Date to assess
            session_type: Session type

        Returns:
            Holiday impact assessment
        """
        cache_key = f"{check_date.isoformat()}_{session_type.value}"

        # Check cache
        if (
            self._cache_expiry
            and datetime.utcnow() < self._cache_expiry
            and cache_key in self._impact_cache
        ):
            return self._impact_cache[cache_key]

        # Get holidays for date
        year_str = str(check_date.year)
        holidays_on_date = []

        if year_str in self.session_calendar.holidays:
            for holiday in self.session_calendar.holidays[year_str]:
                if (
                    holiday.date == check_date
                    and session_type in holiday.affected_sessions
                ):
                    holidays_on_date.append(holiday)

        # Assess impact
        assessment = {
            "date": check_date.isoformat(),
            "session_type": session_type.value,
            "has_holiday_impact": len(holidays_on_date) > 0,
            "holidays": [],
            "overall_impact": "none",
            "liquidity_impact": 1.0,
            "volatility_impact": 1.0,
            "volume_impact": 1.0,
            "trading_recommendation": "normal",
        }

        if holidays_on_date:
            total_liquidity_impact = 1.0
            total_volatility_impact = 1.0
            total_volume_impact = 1.0
            max_impact_level = "low"

            for holiday in holidays_on_date:
                # Create holiday schedule for detailed impact
                holiday_schedule = self._create_holiday_schedule(holiday)

                assessment["holidays"].append(
                    {
                        "name": holiday.name,
                        "type": holiday.holiday_type.value,
                        "trading_impact": holiday.trading_impact,
                        "liquidity_impact": holiday_schedule.liquidity_impact_factor,
                        "volatility_impact": holiday_schedule.volatility_impact_factor,
                        "volume_impact": holiday_schedule.trading_volume_impact,
                    }
                )

                # Aggregate impacts
                total_liquidity_impact *= holiday_schedule.liquidity_impact_factor
                total_volatility_impact *= holiday_schedule.volatility_impact_factor
                total_volume_impact *= holiday_schedule.trading_volume_impact

                # Determine max impact level
                if holiday.holiday_type in [HolidayType.NATIONAL_HOLIDAY]:
                    max_impact_level = "high"
                elif holiday.holiday_type in [HolidayType.BANK_HOLIDAY]:
                    max_impact_level = max(max_impact_level, "medium")

            assessment.update(
                {
                    "overall_impact": max_impact_level,
                    "liquidity_impact": total_liquidity_impact,
                    "volatility_impact": total_volatility_impact,
                    "volume_impact": total_volume_impact,
                    "trading_recommendation": self._get_holiday_trading_recommendation(
                        max_impact_level,
                        total_liquidity_impact,
                        total_volatility_impact,
                    ),
                }
            )

        # Cache result
        self._impact_cache[cache_key] = assessment
        self._cache_expiry = datetime.utcnow() + timedelta(hours=1)

        return assessment

    def _create_holiday_schedule(self, holiday: MarketHoliday) -> HolidaySchedule:
        """Create holiday schedule with impact factors"""

        # Default impact factors based on holiday type
        if holiday.holiday_type == HolidayType.NATIONAL_HOLIDAY:
            liquidity_factor = 0.2  # Very low liquidity
            volatility_factor = 0.5  # Reduced volatility
            volume_factor = 0.1  # Very low volume
        elif holiday.holiday_type == HolidayType.BANK_HOLIDAY:
            liquidity_factor = 0.4  # Low liquidity
            volatility_factor = 0.7  # Somewhat reduced volatility
            volume_factor = 0.3  # Low volume
        elif holiday.holiday_type == HolidayType.EARLY_CLOSE:
            liquidity_factor = 0.6  # Moderate liquidity
            volatility_factor = 0.8  # Slight volatility impact
            volume_factor = 0.5  # Moderate volume
        else:
            liquidity_factor = 0.8  # Minor impact
            volatility_factor = 0.9  # Minimal volatility impact
            volume_factor = 0.7  # Slight volume impact

        return HolidaySchedule(
            holiday=holiday,
            pre_holiday_impact=holiday.holiday_type
            in [HolidayType.NATIONAL_HOLIDAY, HolidayType.BANK_HOLIDAY],
            post_holiday_impact=holiday.holiday_type == HolidayType.NATIONAL_HOLIDAY,
            liquidity_impact_factor=liquidity_factor,
            volatility_impact_factor=volatility_factor,
            trading_volume_impact=volume_factor,
        )

    def _get_holiday_trading_recommendation(
        self, impact_level: str, liquidity_impact: float, volatility_impact: float
    ) -> str:
        """Get trading recommendation based on holiday impact"""

        if impact_level == "high" or liquidity_impact < 0.3:
            return "suspend_trading"
        elif impact_level == "medium" or liquidity_impact < 0.5:
            return "reduce_exposure"
        elif liquidity_impact < 0.8 or volatility_impact < 0.7:
            return "proceed_with_caution"
        else:
            return "monitor_closely"

    def get_pre_post_holiday_impact(
        self,
        target_date: date,
        session_type: SessionType,
        days_before: int = 1,
        days_after: int = 1,
    ) -> Dict[str, Any]:
        """
        Assess pre and post holiday impacts

        Args:
            target_date: Date to check around
            session_type: Session type
            days_before: Days before to check
            days_after: Days after to check

        Returns:
            Pre/post holiday impact assessment
        """
        impact_analysis = {
            "target_date": target_date.isoformat(),
            "session_type": session_type.value,
            "pre_holiday_impacts": [],
            "post_holiday_impacts": [],
            "overall_recommendation": "normal",
        }

        # Check days before
        for days_back in range(1, days_before + 1):
            check_date = target_date - timedelta(days=days_back)
            holiday_impact = self.get_holiday_impact_assessment(
                check_date, session_type
            )

            if holiday_impact["has_holiday_impact"]:
                impact_analysis["pre_holiday_impacts"].append(
                    {
                        "date": check_date.isoformat(),
                        "days_before": days_back,
                        "impact": holiday_impact,
                    }
                )

        # Check days after
        for days_forward in range(1, days_after + 1):
            check_date = target_date + timedelta(days=days_forward)
            holiday_impact = self.get_holiday_impact_assessment(
                check_date, session_type
            )

            if holiday_impact["has_holiday_impact"]:
                impact_analysis["post_holiday_impacts"].append(
                    {
                        "date": check_date.isoformat(),
                        "days_after": days_forward,
                        "impact": holiday_impact,
                    }
                )

        # Determine overall recommendation
        if (
            impact_analysis["pre_holiday_impacts"]
            or impact_analysis["post_holiday_impacts"]
        ):
            # Find most severe impact
            all_impacts = (
                impact_analysis["pre_holiday_impacts"]
                + impact_analysis["post_holiday_impacts"]
            )
            max_impact = "low"

            for impact_entry in all_impacts:
                impact_level = impact_entry["impact"]["overall_impact"]
                if impact_level == "high":
                    max_impact = "high"
                elif impact_level == "medium" and max_impact != "high":
                    max_impact = "medium"

            if max_impact == "high":
                impact_analysis["overall_recommendation"] = "reduce_exposure"
            elif max_impact == "medium":
                impact_analysis["overall_recommendation"] = "proceed_with_caution"
            else:
                impact_analysis["overall_recommendation"] = "monitor_closely"

        return impact_analysis

    def add_emergency_closure(
        self,
        start_time: datetime,
        end_time: datetime,
        reason: str,
        affected_sessions: Set[SessionType],
    ) -> str:
        """
        Add emergency market closure

        Args:
            start_time: Closure start time
            end_time: Closure end time
            reason: Reason for closure
            affected_sessions: Affected sessions

        Returns:
            Closure ID
        """
        closure_id = f"emergency_{start_time.strftime('%Y%m%d_%H%M%S')}"

        emergency_closure = {
            "id": closure_id,
            "closure_type": ClosureType.EMERGENCY,
            "start_time": start_time,
            "end_time": end_time,
            "reason": reason,
            "affected_sessions": affected_sessions,
            "created_at": datetime.utcnow(),
            "is_active": True,
        }

        self.emergency_closures.append(emergency_closure)

        # Clear impact cache
        self._impact_cache.clear()

        logger.warning(f"Emergency closure added: {closure_id} - {reason}")
        return closure_id

    def remove_emergency_closure(self, closure_id: str) -> bool:
        """Remove emergency closure"""
        for i, closure in enumerate(self.emergency_closures):
            if closure["id"] == closure_id:
                self.emergency_closures[i]["is_active"] = False
                logger.info(f"Emergency closure deactivated: {closure_id}")
                return True

        return False

    def is_emergency_closure(
        self, check_time: datetime, session_type: SessionType
    ) -> Optional[Dict[str, Any]]:
        """
        Check for active emergency closures

        Args:
            check_time: Time to check
            session_type: Session type

        Returns:
            Emergency closure info if active, None otherwise
        """
        for closure in self.emergency_closures:
            if (
                closure["is_active"]
                and closure["start_time"] <= check_time <= closure["end_time"]
                and session_type in closure["affected_sessions"]
            ):

                return {
                    "id": closure["id"],
                    "type": closure["closure_type"],
                    "reason": closure["reason"],
                    "start_time": closure["start_time"].isoformat(),
                    "end_time": closure["end_time"].isoformat(),
                    "remaining_duration": (
                        closure["end_time"] - check_time
                    ).total_seconds()
                    / 3600,
                }

        return None

    def get_comprehensive_closure_status(
        self, check_time: datetime, session_type: SessionType
    ) -> Dict[str, Any]:
        """
        Get comprehensive closure status including all types

        Args:
            check_time: Time to check
            session_type: Session type

        Returns:
            Comprehensive closure status
        """
        status = {
            "timestamp": check_time.isoformat(),
            "session_type": session_type.value,
            "is_closed": False,
            "closure_reasons": [],
            "next_open_time": None,
            "impact_assessment": {},
        }

        # Check weekend closure
        if self.is_weekend_closure(check_time):
            status["is_closed"] = True
            status["closure_reasons"].append(
                {
                    "type": ClosureType.WEEKEND.value,
                    "description": "Weekend market closure",
                }
            )

        # Check holiday closure
        if self.is_holiday_closure(check_time, session_type):
            holiday_impact = self.get_holiday_impact_assessment(
                check_time.date(), session_type
            )
            status["is_closed"] = True
            status["closure_reasons"].append(
                {
                    "type": ClosureType.HOLIDAY.value,
                    "description": "Holiday market closure",
                    "impact": holiday_impact,
                }
            )

        # Check emergency closure
        emergency_closure = self.is_emergency_closure(check_time, session_type)
        if emergency_closure:
            status["is_closed"] = True
            status["closure_reasons"].append(
                {
                    "type": ClosureType.EMERGENCY.value,
                    "description": emergency_closure["reason"],
                    "details": emergency_closure,
                }
            )

        # Get next open time if closed
        if status["is_closed"]:
            status["next_open_time"] = self.get_next_market_open(check_time)
            if status["next_open_time"]:
                status["next_open_time"] = status["next_open_time"].isoformat()

        return status

    def set_weekend_schedule(self, weekend_schedule: WeekendSchedule) -> None:
        """Update weekend schedule configuration"""
        self.weekend_schedule = weekend_schedule
        logger.info("Weekend schedule updated")

    def clear_impact_cache(self) -> None:
        """Clear impact assessment cache"""
        self._impact_cache.clear()
        self._cache_expiry = None
        logger.info("Impact cache cleared")
