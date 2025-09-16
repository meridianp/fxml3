"""
FXML4 Market Session Validation Tests

Comprehensive test suite for market session management, following strict TDD methodology.
Tests define expected behavior for:
- Market Session Manager
- Session Calendar
- Session Validator
- Weekend Holiday Handler

This test suite validates that FXML4 correctly handles:
- London/New York session transitions and overlap periods
- Weekend closures (Friday 22:00 GMT - Sunday 22:00 GMT)
- Holiday impact assessment
- Real-time market status monitoring
"""

import asyncio
from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytz

from fxml4.market_sessions import (
    ClosureType,
    HolidaySchedule,
    HolidayType,
    MarketHoliday,
    MarketSession,
    MarketSessionManager,
    MarketState,
    SessionCalendar,
    SessionOverlap,
    SessionStatus,
    SessionTransition,
    SessionType,
    SessionValidationResult,
    SessionValidator,
    TradingSession,
    ValidationLevel,
    ValidationRule,
    WeekendHolidayHandler,
    WeekendSchedule,
)


@pytest.fixture
def market_session_manager():
    """Market session manager fixture"""
    return MarketSessionManager(update_interval=30)


@pytest.fixture
def session_calendar():
    """Session calendar fixture"""
    return SessionCalendar()


@pytest.fixture
def session_validator():
    """Session validator fixture"""
    calendar = SessionCalendar()
    return SessionValidator(calendar)


@pytest.fixture
def weekend_holiday_handler():
    """Weekend holiday handler fixture"""
    calendar = SessionCalendar()
    return WeekendHolidayHandler(calendar)


class TestMarketSessionManager:
    """Test cases for Market Session Manager"""

    def test_initialization(self, market_session_manager):
        """Test manager initializes correctly"""
        manager = market_session_manager

        # Should initialize with standard sessions
        assert len(manager.sessions) == 4
        assert SessionType.LONDON in manager.sessions
        assert SessionType.NEW_YORK in manager.sessions
        assert SessionType.TOKYO in manager.sessions
        assert SessionType.SYDNEY in manager.sessions

        # Should start with weekend closed state
        assert manager.current_state == MarketState.WEEKEND_CLOSED
        assert not manager.is_monitoring
        assert len(manager.active_sessions) == 0

    def test_weekend_detection(self, market_session_manager):
        """Test weekend closure detection (Friday 22:00 GMT - Sunday 22:00 GMT)"""
        manager = market_session_manager

        # Test cases for weekend detection
        test_cases = [
            # Friday 21:59 GMT - should be open
            (datetime(2024, 1, 5, 21, 59, tzinfo=pytz.UTC), False),
            # Friday 22:00 GMT - should be closed (weekend starts)
            (datetime(2024, 1, 5, 22, 0, tzinfo=pytz.UTC), True),
            # Saturday 12:00 GMT - should be closed
            (datetime(2024, 1, 6, 12, 0, tzinfo=pytz.UTC), True),
            # Sunday 21:59 GMT - should be closed
            (datetime(2024, 1, 7, 21, 59, tzinfo=pytz.UTC), True),
            # Sunday 22:00 GMT - should be open (weekend ends)
            (datetime(2024, 1, 7, 22, 0, tzinfo=pytz.UTC), False),
        ]

        for test_time, expected_weekend in test_cases:
            is_weekend = manager._is_weekend(test_time)
            assert (
                is_weekend == expected_weekend
            ), f"Failed for {test_time}: expected {expected_weekend}, got {is_weekend}"

    def test_london_ny_overlap_detection(self, market_session_manager):
        """Test London/New York session overlap detection (13:00-16:00 GMT)"""
        manager = market_session_manager

        # Test cases for London/NY overlap
        test_cases = [
            # Monday 12:59 GMT - London open, NY not yet open
            (datetime(2024, 1, 8, 12, 59, tzinfo=pytz.UTC), False),
            # Monday 13:00 GMT - Both London and NY open (overlap starts)
            (datetime(2024, 1, 8, 13, 0, tzinfo=pytz.UTC), True),
            # Monday 15:00 GMT - Peak overlap time
            (datetime(2024, 1, 8, 15, 0, tzinfo=pytz.UTC), True),
            # Monday 16:00 GMT - London closes, overlap ends
            (datetime(2024, 1, 8, 16, 0, tzinfo=pytz.UTC), False),
            # Monday 20:00 GMT - Only NY open
            (datetime(2024, 1, 8, 20, 0, tzinfo=pytz.UTC), False),
        ]

        for test_time, expected_overlap in test_cases:
            overlap_info = manager.detect_london_ny_overlap(test_time)
            is_overlapping = overlap_info is not None and overlap_info.get(
                "is_active", False
            )

            assert (
                is_overlapping == expected_overlap
            ), f"Failed for {test_time}: expected {expected_overlap}, got {is_overlapping}"

            if expected_overlap:
                assert overlap_info["peak_hours"] is True
                assert "liquidity_multiplier" in overlap_info
                assert "affected_pairs" in overlap_info

    def test_market_state_detection(self, market_session_manager):
        """Test market state classification"""
        manager = market_session_manager

        # Weekend - should be WEEKEND_CLOSED
        weekend_time = datetime(2024, 1, 6, 12, 0, tzinfo=pytz.UTC)  # Saturday
        state = manager.get_current_market_state(weekend_time)
        assert state == MarketState.WEEKEND_CLOSED

        # London/NY overlap - should be PEAK_LIQUIDITY
        overlap_time = datetime(2024, 1, 8, 14, 0, tzinfo=pytz.UTC)  # Monday 14:00 GMT
        with patch.object(manager, "_get_active_sessions") as mock_sessions:
            mock_sessions.return_value = {SessionType.LONDON, SessionType.NEW_YORK}
            state = manager.get_current_market_state(overlap_time)
            assert state == MarketState.PEAK_LIQUIDITY

        # Only London active - should be HIGH_LIQUIDITY
        london_only_time = datetime(
            2024, 1, 8, 10, 0, tzinfo=pytz.UTC
        )  # Monday 10:00 GMT
        with patch.object(manager, "_get_active_sessions") as mock_sessions:
            mock_sessions.return_value = {SessionType.LONDON}
            state = manager.get_current_market_state(london_only_time)
            assert state == MarketState.HIGH_LIQUIDITY

        # Only Tokyo active - should be MODERATE_LIQUIDITY
        tokyo_only_time = datetime(
            2024, 1, 8, 4, 0, tzinfo=pytz.UTC
        )  # Monday 04:00 GMT
        with patch.object(manager, "_get_active_sessions") as mock_sessions:
            mock_sessions.return_value = {SessionType.TOKYO}
            state = manager.get_current_market_state(tokyo_only_time)
            assert state == MarketState.MODERATE_LIQUIDITY

    def test_session_summary(self, market_session_manager):
        """Test comprehensive session summary"""
        manager = market_session_manager

        test_time = datetime(2024, 1, 8, 14, 0, tzinfo=pytz.UTC)  # Monday 14:00 GMT

        with patch.object(manager, "_get_active_sessions") as mock_sessions:
            mock_sessions.return_value = {SessionType.LONDON, SessionType.NEW_YORK}

            summary = manager.get_session_summary(test_time)

            assert "timestamp" in summary
            assert "market_state" in summary
            assert "is_weekend" in summary
            assert "active_sessions" in summary
            assert "london_ny_overlap" in summary
            assert "session_details" in summary

            # Should detect overlap
            assert summary["london_ny_overlap"] is not None
            assert summary["london_ny_overlap"]["is_active"] is True

    @pytest.mark.asyncio
    async def test_real_time_monitoring(self, market_session_manager):
        """Test real-time monitoring capabilities"""
        manager = market_session_manager

        # Test starting monitoring
        await manager.start_real_time_monitoring()
        assert manager.is_monitoring is True
        assert manager.monitoring_task is not None

        # Test stopping monitoring
        await manager.stop_real_time_monitoring()
        assert manager.is_monitoring is False

    @pytest.mark.asyncio
    async def test_market_hours_validation(self, market_session_manager):
        """Test comprehensive market hours logic validation"""
        manager = market_session_manager

        # Run validation
        validation_results = await manager.validate_market_hours_logic()

        assert "timestamp" in validation_results
        assert "test_cases" in validation_results
        assert "success_count" in validation_results
        assert "failure_count" in validation_results
        assert "overall_result" in validation_results

        # Should have multiple test cases
        assert len(validation_results["test_cases"]) >= 3

        # Should include weekend closure, overlap, and transition tests
        test_names = [test["test_name"] for test in validation_results["test_cases"]]
        assert "Weekend Closure Detection" in test_names
        assert "London/NY Overlap Detection" in test_names
        assert "Session Transition Detection" in test_names


class TestSessionCalendar:
    """Test cases for Session Calendar"""

    def test_initialization(self, session_calendar):
        """Test calendar initializes with standard sessions"""
        calendar = session_calendar

        # Should have 4 standard sessions
        assert len(calendar.sessions) == 4
        assert SessionType.LONDON in calendar.sessions
        assert SessionType.NEW_YORK in calendar.sessions
        assert SessionType.TOKYO in calendar.sessions
        assert SessionType.SYDNEY in calendar.sessions

        # Should have session overlaps
        assert len(calendar.overlaps) >= 3

        # Should have holidays for current and next year
        current_year = str(datetime.now().year)
        assert current_year in calendar.holidays
        assert len(calendar.holidays[current_year]) > 0

    def test_standard_sessions_configuration(self, session_calendar):
        """Test standard forex sessions are configured correctly"""
        calendar = session_calendar

        # London session - 08:00-16:00 GMT with DST
        london = calendar.sessions[SessionType.LONDON]
        assert london.name == "London Session"
        assert london.timezone == "Europe/London"
        assert london.open_time == "08:00"
        assert london.close_time == "16:00"
        assert london.dst_aware is True
        assert "GBPUSD" in london.major_currency_pairs

        # New York session - 13:00-21:00 EST with DST
        ny = calendar.sessions[SessionType.NEW_YORK]
        assert ny.name == "New York Session"
        assert ny.timezone == "America/New_York"
        assert ny.open_time == "13:00"
        assert ny.close_time == "21:00"
        assert ny.dst_aware is True
        assert "GBPUSD" in ny.major_currency_pairs

        # Tokyo session - 09:00-17:00 JST (no DST)
        tokyo = calendar.sessions[SessionType.TOKYO]
        assert tokyo.name == "Tokyo Session"
        assert tokyo.timezone == "Asia/Tokyo"
        assert tokyo.open_time == "09:00"
        assert tokyo.close_time == "17:00"
        assert tokyo.dst_aware is False
        assert "USDJPY" in tokyo.major_currency_pairs

        # Sydney session - 22:00-06:00 AEDT
        sydney = calendar.sessions[SessionType.SYDNEY]
        assert sydney.name == "Sydney Session"
        assert sydney.timezone == "Australia/Sydney"
        assert sydney.open_time == "22:00"
        assert sydney.close_time == "06:00"
        assert sydney.dst_aware is True
        assert "AUDUSD" in sydney.major_currency_pairs

    def test_london_ny_overlap_configuration(self, session_calendar):
        """Test London/NY overlap is configured correctly"""
        calendar = session_calendar

        # Find London/NY overlap
        london_ny_overlap = None
        for overlap in calendar.overlaps:
            if (
                overlap.primary_session == SessionType.LONDON
                and overlap.secondary_session == SessionType.NEW_YORK
            ) or (
                overlap.primary_session == SessionType.NEW_YORK
                and overlap.secondary_session == SessionType.LONDON
            ):
                london_ny_overlap = overlap
                break

        assert london_ny_overlap is not None
        assert london_ny_overlap.overlap_start == "13:00"  # NY opens
        assert london_ny_overlap.overlap_end == "16:00"  # London closes
        assert london_ny_overlap.timezone == "UTC"
        assert london_ny_overlap.peak_hours is True
        assert london_ny_overlap.liquidity_multiplier >= 1.5

    def test_trading_day_validation(self, session_calendar):
        """Test trading day validation"""
        calendar = session_calendar

        # Monday should be trading day for all sessions
        monday = date(2024, 1, 8)  # A Monday
        for session_type in [
            SessionType.LONDON,
            SessionType.NEW_YORK,
            SessionType.TOKYO,
            SessionType.SYDNEY,
        ]:
            assert calendar.is_trading_day(monday, session_type) is True

        # Saturday should not be trading day
        saturday = date(2024, 1, 6)  # A Saturday
        for session_type in [
            SessionType.LONDON,
            SessionType.NEW_YORK,
            SessionType.TOKYO,
            SessionType.SYDNEY,
        ]:
            assert calendar.is_trading_day(saturday, session_type) is False

        # Sunday should not be trading day
        sunday = date(2024, 1, 7)  # A Sunday
        for session_type in [
            SessionType.LONDON,
            SessionType.NEW_YORK,
            SessionType.TOKYO,
            SessionType.SYDNEY,
        ]:
            assert calendar.is_trading_day(sunday, session_type) is False

    def test_holiday_detection(self, session_calendar):
        """Test holiday detection and impact"""
        calendar = session_calendar

        # Christmas Day should affect multiple sessions
        christmas = date(2024, 12, 25)

        # Should not be trading day for major sessions
        assert calendar.is_trading_day(christmas, SessionType.LONDON) is False
        assert calendar.is_trading_day(christmas, SessionType.NEW_YORK) is False
        assert calendar.is_trading_day(christmas, SessionType.SYDNEY) is False

        # Should have session hours as None (closed)
        london_hours = calendar.get_session_hours(SessionType.LONDON, christmas)
        assert london_hours is None

        ny_hours = calendar.get_session_hours(SessionType.NEW_YORK, christmas)
        assert ny_hours is None

    def test_liquidity_and_volatility_factors(self, session_calendar):
        """Test liquidity and volatility factor calculations"""
        calendar = session_calendar

        # London session during peak hours should have high liquidity
        london_peak_time = datetime(
            2024, 1, 8, 14, 0, tzinfo=pytz.UTC
        )  # 2 PM GMT, overlap time
        london_liquidity = calendar.get_liquidity_factor(
            SessionType.LONDON, london_peak_time
        )

        assert london_liquidity > 1.0  # Should be above normal

        # Tokyo session liquidity should be moderate
        tokyo_time = datetime(2024, 1, 8, 4, 0, tzinfo=pytz.UTC)  # Tokyo session time
        tokyo_liquidity = calendar.get_liquidity_factor(SessionType.TOKYO, tokyo_time)

        assert tokyo_liquidity > 0.0

        # Volatility factors should also be reasonable
        london_volatility = calendar.get_volatility_factor(
            SessionType.LONDON, london_peak_time
        )
        assert london_volatility > 0.0

    def test_calendar_summary(self, session_calendar):
        """Test calendar summary functionality"""
        calendar = session_calendar

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        summary = calendar.get_calendar_summary(start_date, end_date)

        assert "period" in summary
        assert "trading_days_by_session" in summary
        assert "holidays" in summary
        assert "session_overlaps" in summary
        assert "peak_liquidity_days" in summary

        # Should have trading days for each session
        for session_type in [
            SessionType.LONDON,
            SessionType.NEW_YORK,
            SessionType.TOKYO,
            SessionType.SYDNEY,
        ]:
            assert session_type.value in summary["trading_days_by_session"]
            session_data = summary["trading_days_by_session"][session_type.value]
            assert "count" in session_data
            assert "dates" in session_data
            assert session_data["count"] > 0  # Should have some trading days in January


class TestSessionValidator:
    """Test cases for Session Validator"""

    def test_initialization(self, session_validator):
        """Test validator initializes correctly"""
        validator = session_validator

        # Should have validation rules enabled
        assert len(validator.validation_rules) > 0
        assert validator.validation_rules[ValidationRule.WEEKEND_CLOSURE] is True
        assert validator.validation_rules[ValidationRule.HOLIDAY_CLOSURE] is True
        assert validator.validation_rules[ValidationRule.TRADING_HOURS] is True

        # Should have reasonable thresholds
        assert "minimum" in validator.liquidity_thresholds
        assert "peak" in validator.liquidity_thresholds
        assert (
            validator.liquidity_thresholds["minimum"]
            < validator.liquidity_thresholds["peak"]
        )

    def test_weekend_closure_validation(self, session_validator):
        """Test weekend closure validation"""
        validator = session_validator

        # Weekend time - should fail validation
        weekend_time = datetime(2024, 1, 6, 12, 0, tzinfo=pytz.UTC)  # Saturday
        result = validator.validate_trading_session(SessionType.LONDON, weekend_time)

        assert isinstance(result, SessionValidationResult)
        assert result.session_type == SessionType.LONDON
        assert result.total_checks > 0

        # Should have weekend closure validation result
        weekend_results = [
            r for r in result.results if r.rule == ValidationRule.WEEKEND_CLOSURE
        ]
        assert len(weekend_results) > 0

        weekend_result = weekend_results[0]
        assert weekend_result.level in [ValidationLevel.INFO, ValidationLevel.WARNING]

    def test_trading_hours_validation(self, session_validator):
        """Test trading hours validation"""
        validator = session_validator

        # During London session hours - should pass
        london_active_time = datetime(
            2024, 1, 8, 10, 0, tzinfo=pytz.UTC
        )  # Monday 10:00 GMT
        result = validator.validate_trading_session(
            SessionType.LONDON, london_active_time
        )

        # Should have trading hours validation
        trading_hours_results = [
            r for r in result.results if r.rule == ValidationRule.TRADING_HOURS
        ]
        assert len(trading_hours_results) > 0

        # Outside trading hours - should warn
        london_inactive_time = datetime(
            2024, 1, 8, 6, 0, tzinfo=pytz.UTC
        )  # Monday 06:00 GMT
        result = validator.validate_trading_session(
            SessionType.LONDON, london_inactive_time
        )

        trading_hours_results = [
            r for r in result.results if r.rule == ValidationRule.TRADING_HOURS
        ]
        assert len(trading_hours_results) > 0

    def test_liquidity_threshold_validation(self, session_validator):
        """Test liquidity threshold validation"""
        validator = session_validator

        # Set low liquidity threshold for testing
        validator.set_liquidity_thresholds({"minimum": 0.8})

        # Test during normal session time
        normal_time = datetime(2024, 1, 8, 14, 0, tzinfo=pytz.UTC)  # Monday 14:00 GMT
        result = validator.validate_trading_session(SessionType.LONDON, normal_time)

        # Should have liquidity validation
        liquidity_results = [
            r for r in result.results if r.rule == ValidationRule.LIQUIDITY_THRESHOLD
        ]
        assert len(liquidity_results) > 0

        liquidity_result = liquidity_results[0]
        assert "liquidity_factor" in liquidity_result.details

    def test_currency_pair_session_validation(self, session_validator):
        """Test currency pair session suitability validation"""
        validator = session_validator

        # GBPUSD should be optimal for London session
        london_time = datetime(2024, 1, 8, 10, 0, tzinfo=pytz.UTC)
        result = validator.validate_trading_session(
            SessionType.LONDON, london_time, currency_pair="GBPUSD"
        )

        # Should have currency pair validation
        pair_results = [
            r for r in result.results if r.rule == ValidationRule.CURRENCY_PAIR_SESSION
        ]
        assert len(pair_results) > 0

        pair_result = pair_results[0]
        assert pair_result.details["currency_pair"] == "GBPUSD"
        assert pair_result.details["session_preference"] in ["primary", "secondary"]

    def test_validation_summary(self, session_validator):
        """Test validation summary generation"""
        validator = session_validator

        # Run validation during good conditions
        good_time = datetime(2024, 1, 8, 14, 0, tzinfo=pytz.UTC)  # Monday 14:00 GMT
        result = validator.validate_trading_session(
            SessionType.LONDON, good_time, currency_pair="GBPUSD"
        )

        assert "summary" in result.__dict__
        assert "validation_score" in result.summary
        assert "risk_level" in result.summary
        assert "trading_recommendation" in result.summary

        # Validation score should be reasonable
        assert 0 <= result.summary["validation_score"] <= 100

        # Risk level should be one of expected values
        assert result.summary["risk_level"] in [
            "minimal",
            "low",
            "medium",
            "high",
            "critical",
        ]

    def test_rule_enable_disable(self, session_validator):
        """Test enabling and disabling validation rules"""
        validator = session_validator

        # Disable weekend closure rule
        validator.disable_rule(ValidationRule.WEEKEND_CLOSURE)
        assert validator.validation_rules[ValidationRule.WEEKEND_CLOSURE] is False

        # Re-enable weekend closure rule
        validator.enable_rule(ValidationRule.WEEKEND_CLOSURE)
        assert validator.validation_rules[ValidationRule.WEEKEND_CLOSURE] is True


class TestWeekendHolidayHandler:
    """Test cases for Weekend Holiday Handler"""

    def test_initialization(self, weekend_holiday_handler):
        """Test handler initializes correctly"""
        handler = weekend_holiday_handler

        # Should have weekend schedule configured
        assert handler.weekend_schedule.start_day == 4  # Friday
        assert handler.weekend_schedule.start_hour == 22  # 22:00
        assert handler.weekend_schedule.end_day == 6  # Sunday
        assert handler.weekend_schedule.end_hour == 22  # 22:00
        assert handler.weekend_schedule.timezone == "UTC"

        # Should have empty emergency closures initially
        assert len(handler.emergency_closures) == 0

    def test_weekend_closure_detection(self, weekend_holiday_handler):
        """Test weekend closure detection logic"""
        handler = weekend_holiday_handler

        # Test weekend closure detection
        test_cases = [
            # Friday 21:59 GMT - should NOT be weekend closure
            (datetime(2024, 1, 5, 21, 59, tzinfo=pytz.UTC), False),
            # Friday 22:00 GMT - should be weekend closure
            (datetime(2024, 1, 5, 22, 0, tzinfo=pytz.UTC), True),
            # Saturday 12:00 GMT - should be weekend closure
            (datetime(2024, 1, 6, 12, 0, tzinfo=pytz.UTC), True),
            # Sunday 21:59 GMT - should be weekend closure
            (datetime(2024, 1, 7, 21, 59, tzinfo=pytz.UTC), True),
            # Sunday 22:00 GMT - should NOT be weekend closure
            (datetime(2024, 1, 7, 22, 0, tzinfo=pytz.UTC), False),
            # Monday 10:00 GMT - should NOT be weekend closure
            (datetime(2024, 1, 8, 10, 0, tzinfo=pytz.UTC), False),
        ]

        for test_time, expected_weekend in test_cases:
            is_weekend = handler.is_weekend_closure(test_time)
            assert (
                is_weekend == expected_weekend
            ), f"Failed for {test_time}: expected {expected_weekend}, got {is_weekend}"

    def test_weekend_closure_info(self, weekend_holiday_handler):
        """Test weekend closure information"""
        handler = weekend_holiday_handler

        # During weekend - should provide closure info
        weekend_time = datetime(2024, 1, 6, 12, 0, tzinfo=pytz.UTC)  # Saturday
        info = handler.get_weekend_closure_info(weekend_time)

        assert info["is_weekend_closure"] is True
        assert info["closure_type"] == ClosureType.WEEKEND
        assert "current_time" in info
        assert "next_market_open" in info
        assert "closure_duration_hours" in info
        assert "weekend_schedule" in info

        # During weekday - should not be weekend closure
        weekday_time = datetime(2024, 1, 8, 10, 0, tzinfo=pytz.UTC)  # Monday
        info = handler.get_weekend_closure_info(weekday_time)

        assert info["is_weekend_closure"] is False
        assert "next_weekend_start" in info

    def test_next_market_open_calculation(self, weekend_holiday_handler):
        """Test next market open time calculation"""
        handler = weekend_holiday_handler

        # During weekend - should return Sunday 22:00 GMT or next trading day
        weekend_time = datetime(2024, 1, 6, 12, 0, tzinfo=pytz.UTC)  # Saturday
        next_open = handler.get_next_market_open(weekend_time)

        assert next_open is not None
        assert isinstance(next_open, datetime)
        assert next_open > weekend_time

        # Should be Sunday evening or later
        assert next_open.weekday() >= 6 or next_open.weekday() == 0  # Sunday or Monday

    def test_holiday_impact_assessment(self, weekend_holiday_handler):
        """Test holiday impact assessment"""
        handler = weekend_holiday_handler

        # Test Christmas Day impact
        christmas = date(2024, 12, 25)
        impact = handler.get_holiday_impact_assessment(christmas, SessionType.LONDON)

        assert "date" in impact
        assert "session_type" in impact
        assert "has_holiday_impact" in impact
        assert "overall_impact" in impact
        assert "liquidity_impact" in impact
        assert "volatility_impact" in impact
        assert "trading_recommendation" in impact

        # Christmas should have significant impact
        if impact["has_holiday_impact"]:
            assert impact["overall_impact"] in ["medium", "high"]
            assert impact["liquidity_impact"] < 1.0  # Reduced liquidity
            assert impact["trading_recommendation"] in [
                "suspend_trading",
                "reduce_exposure",
                "proceed_with_caution",
            ]

    def test_emergency_closure_management(self, weekend_holiday_handler):
        """Test emergency closure management"""
        handler = weekend_holiday_handler

        # Add emergency closure
        start_time = datetime(2024, 1, 8, 10, 0, tzinfo=pytz.UTC)
        end_time = datetime(2024, 1, 8, 18, 0, tzinfo=pytz.UTC)
        reason = "System maintenance"
        affected_sessions = {SessionType.LONDON, SessionType.NEW_YORK}

        closure_id = handler.add_emergency_closure(
            start_time, end_time, reason, affected_sessions
        )

        assert closure_id is not None
        assert len(handler.emergency_closures) == 1

        # Check if emergency closure is active
        check_time = datetime(2024, 1, 8, 14, 0, tzinfo=pytz.UTC)  # During closure
        emergency_info = handler.is_emergency_closure(check_time, SessionType.LONDON)

        assert emergency_info is not None
        assert emergency_info["id"] == closure_id
        assert emergency_info["reason"] == reason

        # Remove emergency closure
        removed = handler.remove_emergency_closure(closure_id)
        assert removed is True

        # Should no longer be active
        emergency_info = handler.is_emergency_closure(check_time, SessionType.LONDON)
        assert emergency_info is None

    def test_comprehensive_closure_status(self, weekend_holiday_handler):
        """Test comprehensive closure status"""
        handler = weekend_holiday_handler

        # Test during weekend
        weekend_time = datetime(2024, 1, 6, 12, 0, tzinfo=pytz.UTC)  # Saturday
        status = handler.get_comprehensive_closure_status(
            weekend_time, SessionType.LONDON
        )

        assert "timestamp" in status
        assert "session_type" in status
        assert "is_closed" in status
        assert "closure_reasons" in status
        assert "next_open_time" in status

        # Should be closed due to weekend
        assert status["is_closed"] is True
        assert len(status["closure_reasons"]) > 0

        # Should have weekend closure reason
        closure_types = [reason["type"] for reason in status["closure_reasons"]]
        assert ClosureType.WEEKEND.value in closure_types

    def test_pre_post_holiday_impact(self, weekend_holiday_handler):
        """Test pre and post holiday impact assessment"""
        handler = weekend_holiday_handler

        # Test around Christmas
        christmas = date(2024, 12, 25)
        impact = handler.get_pre_post_holiday_impact(
            christmas, SessionType.LONDON, days_before=2, days_after=2
        )

        assert "target_date" in impact
        assert "session_type" in impact
        assert "pre_holiday_impacts" in impact
        assert "post_holiday_impacts" in impact
        assert "overall_recommendation" in impact

        # Should provide reasonable recommendation
        assert impact["overall_recommendation"] in [
            "normal",
            "monitor_closely",
            "proceed_with_caution",
            "reduce_exposure",
        ]


class TestIntegratedMarketSessionValidation:
    """Integration tests for complete market session validation system"""

    def test_complete_session_validation_workflow(
        self, market_session_manager, session_validator
    ):
        """Test complete validation workflow"""
        manager = market_session_manager
        validator = session_validator

        # Test during optimal trading conditions (London/NY overlap)
        optimal_time = datetime(2024, 1, 8, 14, 0, tzinfo=pytz.UTC)  # Monday 14:00 GMT

        # Get market state from manager
        market_state = manager.get_current_market_state(optimal_time)

        # Get session validation from validator
        validation_result = validator.validate_trading_session(
            SessionType.LONDON, optimal_time, currency_pair="GBPUSD"
        )

        # Results should be consistent
        assert market_state in [MarketState.PEAK_LIQUIDITY, MarketState.HIGH_LIQUIDITY]
        assert (
            validation_result.overall_passed is True
            or validation_result.warning_count <= 2
        )

        # Should detect London/NY overlap
        overlap_info = manager.detect_london_ny_overlap(optimal_time)
        assert overlap_info is not None
        assert overlap_info["is_active"] is True

    def test_weekend_validation_consistency(
        self, market_session_manager, session_validator, weekend_holiday_handler
    ):
        """Test weekend validation consistency across components"""
        weekend_time = datetime(2024, 1, 6, 12, 0, tzinfo=pytz.UTC)  # Saturday

        # All components should agree it's weekend
        manager_weekend = manager._is_weekend(weekend_time)
        handler_weekend = weekend_holiday_handler.is_weekend_closure(weekend_time)

        assert manager_weekend is True
        assert handler_weekend is True

        # Market state should be weekend closed
        market_state = market_session_manager.get_current_market_state(weekend_time)
        assert market_state == MarketState.WEEKEND_CLOSED

        # Validation should reflect weekend closure
        validation_result = session_validator.validate_trading_session(
            SessionType.LONDON, weekend_time
        )
        weekend_validations = [
            r
            for r in validation_result.results
            if r.rule == ValidationRule.WEEKEND_CLOSURE
        ]
        assert len(weekend_validations) > 0

    def test_holiday_validation_consistency(
        self, session_calendar, session_validator, weekend_holiday_handler
    ):
        """Test holiday validation consistency"""
        christmas = date(2024, 12, 25)
        christmas_time = datetime(2024, 12, 25, 12, 0, tzinfo=pytz.UTC)

        # Calendar should show Christmas as non-trading day
        is_trading_day = session_calendar.is_trading_day(christmas, SessionType.LONDON)
        assert is_trading_day is False

        # Holiday handler should assess impact
        impact = weekend_holiday_handler.get_holiday_impact_assessment(
            christmas, SessionType.LONDON
        )
        assert impact["has_holiday_impact"] is True

        # Validator should flag holiday concerns
        validation_result = session_validator.validate_trading_session(
            SessionType.LONDON, christmas_time
        )
        holiday_validations = [
            r
            for r in validation_result.results
            if r.rule == ValidationRule.HOLIDAY_CLOSURE
        ]
        assert len(holiday_validations) > 0

    @pytest.mark.asyncio
    async def test_complete_market_hours_validation(self, market_session_manager):
        """Test complete market hours logic validation from manager"""
        manager = market_session_manager

        # Run comprehensive validation
        validation_results = await manager.validate_market_hours_logic()

        # Should pass all critical tests
        assert validation_results["overall_result"] == "PASS"
        assert validation_results["success_count"] > 0
        assert validation_results["failure_count"] == 0

        # Should test all key scenarios
        test_names = [test["test_name"] for test in validation_results["test_cases"]]
        assert "Weekend Closure Detection" in test_names
        assert "London/NY Overlap Detection" in test_names
        assert "Session Transition Detection" in test_names

        # All test cases should pass
        for test_case in validation_results["test_cases"]:
            assert (
                test_case["result"] == "PASS"
            ), f"Test case failed: {test_case['test_name']}"
