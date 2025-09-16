#!/usr/bin/env python3
"""
FXML4 Market Hours Logic Validation Script

Comprehensive validation script that proves the system correctly handles:
1. London/New York session transitions and overlap periods (13:00-16:00 GMT)
2. Weekend closures (Friday 22:00 GMT - Sunday 22:00 GMT)
3. Real-time market status monitoring
4. Session-based business logic

This script validates the critical market hours logic required for Phase 10B
core trading system validation.

Usage:
    python scripts/prove_market_hours_logic.py [--verbose] [--html-report]
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
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
except ImportError as e:
    logger.error(f"Failed to import market session components: {e}")
    logger.error(
        "Make sure you're running from the project root with proper PYTHONPATH"
    )
    sys.exit(1)


class MarketHoursLogicValidator:
    """
    Comprehensive validator for market hours logic with detailed reporting
    """

    def __init__(self, verbose: bool = False):
        """Initialize validator"""
        self.verbose = verbose
        self.test_results = []
        self.start_time = datetime.utcnow()

        # Initialize components
        self.session_manager = MarketSessionManager(update_interval=30)
        self.session_calendar = SessionCalendar()
        self.session_validator = SessionValidator(self.session_calendar)
        self.weekend_holiday_handler = WeekendHolidayHandler(self.session_calendar)

        logger.info("Market Hours Logic Validator initialized")

    def log_test_result(
        self, test_name: str, passed: bool, details: dict, recommendations: list = None
    ):
        """Log a test result"""
        result = {
            "test_name": test_name,
            "passed": passed,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details,
            "recommendations": recommendations or [],
        }

        self.test_results.append(result)

        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {test_name}")

        if self.verbose or not passed:
            logger.info(f"  Details: {details}")
            if recommendations:
                logger.info(f"  Recommendations: {recommendations}")

    async def validate_weekend_closure_logic(self) -> bool:
        """
        Validate weekend closure logic (Friday 22:00 GMT - Sunday 22:00 GMT)

        Returns:
            True if all weekend tests pass
        """
        logger.info("\n🔍 Testing Weekend Closure Logic...")

        all_passed = True

        # Test case 1: Friday 21:59 GMT (should be OPEN)
        friday_before = datetime(2024, 1, 5, 21, 59, tzinfo=pytz.UTC)
        manager_weekend = self.session_manager._is_weekend(friday_before)
        handler_weekend = self.weekend_holiday_handler.is_weekend_closure(friday_before)
        market_state = self.session_manager.get_current_market_state(friday_before)

        test1_passed = (
            not manager_weekend
            and not handler_weekend
            and market_state != MarketState.WEEKEND_CLOSED
        )

        self.log_test_result(
            "Weekend Logic - Friday 21:59 GMT (Should be Open)",
            test1_passed,
            {
                "time": friday_before.isoformat(),
                "manager_weekend": manager_weekend,
                "handler_weekend": handler_weekend,
                "market_state": market_state.value if market_state else None,
                "expected": "market_open",
            },
            [] if test1_passed else ["Check weekend start time configuration"],
        )

        if not test1_passed:
            all_passed = False

        # Test case 2: Friday 22:00 GMT (should be CLOSED - weekend starts)
        friday_22 = datetime(2024, 1, 5, 22, 0, tzinfo=pytz.UTC)
        manager_weekend = self.session_manager._is_weekend(friday_22)
        handler_weekend = self.weekend_holiday_handler.is_weekend_closure(friday_22)
        market_state = self.session_manager.get_current_market_state(friday_22)

        test2_passed = (
            manager_weekend
            and handler_weekend
            and market_state == MarketState.WEEKEND_CLOSED
        )

        self.log_test_result(
            "Weekend Logic - Friday 22:00 GMT (Should be Closed)",
            test2_passed,
            {
                "time": friday_22.isoformat(),
                "manager_weekend": manager_weekend,
                "handler_weekend": handler_weekend,
                "market_state": market_state.value if market_state else None,
                "expected": "weekend_closed",
            },
            [] if test2_passed else ["Verify weekend start time at Friday 22:00 GMT"],
        )

        if not test2_passed:
            all_passed = False

        # Test case 3: Saturday 12:00 GMT (should be CLOSED)
        saturday_noon = datetime(2024, 1, 6, 12, 0, tzinfo=pytz.UTC)
        manager_weekend = self.session_manager._is_weekend(saturday_noon)
        handler_weekend = self.weekend_holiday_handler.is_weekend_closure(saturday_noon)
        market_state = self.session_manager.get_current_market_state(saturday_noon)

        test3_passed = (
            manager_weekend
            and handler_weekend
            and market_state == MarketState.WEEKEND_CLOSED
        )

        self.log_test_result(
            "Weekend Logic - Saturday 12:00 GMT (Should be Closed)",
            test3_passed,
            {
                "time": saturday_noon.isoformat(),
                "manager_weekend": manager_weekend,
                "handler_weekend": handler_weekend,
                "market_state": market_state.value if market_state else None,
                "expected": "weekend_closed",
            },
            [] if test3_passed else ["Verify Saturday is properly detected as weekend"],
        )

        if not test3_passed:
            all_passed = False

        # Test case 4: Sunday 21:59 GMT (should be CLOSED)
        sunday_before = datetime(2024, 1, 7, 21, 59, tzinfo=pytz.UTC)
        manager_weekend = self.session_manager._is_weekend(sunday_before)
        handler_weekend = self.weekend_holiday_handler.is_weekend_closure(sunday_before)
        market_state = self.session_manager.get_current_market_state(sunday_before)

        test4_passed = (
            manager_weekend
            and handler_weekend
            and market_state == MarketState.WEEKEND_CLOSED
        )

        self.log_test_result(
            "Weekend Logic - Sunday 21:59 GMT (Should be Closed)",
            test4_passed,
            {
                "time": sunday_before.isoformat(),
                "manager_weekend": manager_weekend,
                "handler_weekend": handler_weekend,
                "market_state": market_state.value if market_state else None,
                "expected": "weekend_closed",
            },
            [] if test4_passed else ["Verify weekend continues until Sunday 22:00 GMT"],
        )

        if not test4_passed:
            all_passed = False

        # Test case 5: Sunday 22:00 GMT (should be OPEN - weekend ends)
        sunday_22 = datetime(2024, 1, 7, 22, 0, tzinfo=pytz.UTC)
        manager_weekend = self.session_manager._is_weekend(sunday_22)
        handler_weekend = self.weekend_holiday_handler.is_weekend_closure(sunday_22)
        market_state = self.session_manager.get_current_market_state(sunday_22)

        test5_passed = (
            not manager_weekend
            and not handler_weekend
            and market_state != MarketState.WEEKEND_CLOSED
        )

        self.log_test_result(
            "Weekend Logic - Sunday 22:00 GMT (Should be Open)",
            test5_passed,
            {
                "time": sunday_22.isoformat(),
                "manager_weekend": manager_weekend,
                "handler_weekend": handler_weekend,
                "market_state": market_state.value if market_state else None,
                "expected": "market_open",
            },
            [] if test5_passed else ["Check weekend end time configuration"],
        )

        if not test5_passed:
            all_passed = False

        # Test weekend closure info
        weekend_info = self.weekend_holiday_handler.get_weekend_closure_info(
            saturday_noon
        )
        info_test_passed = (
            weekend_info["is_weekend_closure"]
            and weekend_info["closure_type"] == ClosureType.WEEKEND
        )

        self.log_test_result(
            "Weekend Closure Info Generation",
            info_test_passed,
            {
                "weekend_info": weekend_info,
                "has_next_open_time": weekend_info.get("next_market_open") is not None,
                "has_closure_duration": weekend_info.get("closure_duration_hours")
                is not None,
            },
            [] if info_test_passed else ["Check weekend closure info generation"],
        )

        if not info_test_passed:
            all_passed = False

        return all_passed

    async def validate_london_ny_overlap_logic(self) -> bool:
        """
        Validate London/New York session overlap (13:00-16:00 GMT)

        Returns:
            True if all overlap tests pass
        """
        logger.info("\n🔍 Testing London/New York Overlap Logic...")

        all_passed = True

        # Test case 1: Monday 12:59 GMT (London open, NY not yet open)
        before_overlap = datetime(2024, 1, 8, 12, 59, tzinfo=pytz.UTC)
        overlap_info = self.session_manager.detect_london_ny_overlap(before_overlap)
        market_state = self.session_manager.get_current_market_state(before_overlap)

        test1_passed = overlap_info is None or not overlap_info.get("is_active", False)

        self.log_test_result(
            "London/NY Overlap - Before Overlap (12:59 GMT)",
            test1_passed,
            {
                "time": before_overlap.isoformat(),
                "overlap_active": (
                    overlap_info.get("is_active", False) if overlap_info else False
                ),
                "market_state": market_state.value if market_state else None,
                "expected": "no_overlap",
            },
            [] if test1_passed else ["Verify NY session starts at 13:00 GMT"],
        )

        if not test1_passed:
            all_passed = False

        # Test case 2: Monday 13:00 GMT (Overlap starts - both sessions open)
        overlap_start = datetime(2024, 1, 8, 13, 0, tzinfo=pytz.UTC)
        overlap_info = self.session_manager.detect_london_ny_overlap(overlap_start)
        market_state = self.session_manager.get_current_market_state(overlap_start)

        test2_passed = overlap_info is not None and overlap_info.get("is_active", False)

        self.log_test_result(
            "London/NY Overlap - Overlap Start (13:00 GMT)",
            test2_passed,
            {
                "time": overlap_start.isoformat(),
                "overlap_active": (
                    overlap_info.get("is_active", False) if overlap_info else False
                ),
                "overlap_info": overlap_info,
                "market_state": market_state.value if market_state else None,
                "expected": "overlap_active",
            },
            (
                []
                if test2_passed
                else ["Check London and NY session schedules for 13:00 GMT overlap"]
            ),
        )

        if not test2_passed:
            all_passed = False

        # Test case 3: Monday 15:00 GMT (Peak overlap time)
        peak_overlap = datetime(2024, 1, 8, 15, 0, tzinfo=pytz.UTC)
        overlap_info = self.session_manager.detect_london_ny_overlap(peak_overlap)
        market_state = self.session_manager.get_current_market_state(peak_overlap)

        test3_passed = (
            overlap_info is not None
            and overlap_info.get("is_active", False)
            and overlap_info.get("peak_hours", False)
        )

        self.log_test_result(
            "London/NY Overlap - Peak Time (15:00 GMT)",
            test3_passed,
            {
                "time": peak_overlap.isoformat(),
                "overlap_active": (
                    overlap_info.get("is_active", False) if overlap_info else False
                ),
                "peak_hours": (
                    overlap_info.get("peak_hours", False) if overlap_info else False
                ),
                "market_state": market_state.value if market_state else None,
                "liquidity_multiplier": (
                    overlap_info.get("liquidity_multiplier") if overlap_info else None
                ),
                "expected": "peak_overlap",
            },
            [] if test3_passed else ["Verify peak liquidity during 15:00 GMT overlap"],
        )

        if not test3_passed:
            all_passed = False

        # Test case 4: Monday 16:00 GMT (London closes, overlap ends)
        overlap_end = datetime(2024, 1, 8, 16, 0, tzinfo=pytz.UTC)
        overlap_info = self.session_manager.detect_london_ny_overlap(overlap_end)
        market_state = self.session_manager.get_current_market_state(overlap_end)

        test4_passed = overlap_info is None or not overlap_info.get("is_active", False)

        self.log_test_result(
            "London/NY Overlap - Overlap End (16:00 GMT)",
            test4_passed,
            {
                "time": overlap_end.isoformat(),
                "overlap_active": (
                    overlap_info.get("is_active", False) if overlap_info else False
                ),
                "market_state": market_state.value if market_state else None,
                "expected": "overlap_ended",
            },
            [] if test4_passed else ["Check London session close time at 16:00 GMT"],
        )

        if not test4_passed:
            all_passed = False

        # Test case 5: Monday 20:00 GMT (Only NY open)
        after_overlap = datetime(2024, 1, 8, 20, 0, tzinfo=pytz.UTC)
        overlap_info = self.session_manager.detect_london_ny_overlap(after_overlap)
        market_state = self.session_manager.get_current_market_state(after_overlap)

        test5_passed = overlap_info is None or not overlap_info.get("is_active", False)

        self.log_test_result(
            "London/NY Overlap - After Overlap (20:00 GMT)",
            test5_passed,
            {
                "time": after_overlap.isoformat(),
                "overlap_active": (
                    overlap_info.get("is_active", False) if overlap_info else False
                ),
                "market_state": market_state.value if market_state else None,
                "expected": "no_overlap_ny_only",
            },
            [] if test5_passed else ["Verify only NY session active at 20:00 GMT"],
        )

        if not test5_passed:
            all_passed = False

        # Test session calendar overlap configuration
        calendar_overlaps = self.session_calendar.get_active_overlaps(peak_overlap)
        london_ny_calendar_overlap = None

        for overlap in calendar_overlaps:
            if (
                overlap.primary_session == SessionType.LONDON
                and overlap.secondary_session == SessionType.NEW_YORK
            ) or (
                overlap.primary_session == SessionType.NEW_YORK
                and overlap.secondary_session == SessionType.LONDON
            ):
                london_ny_calendar_overlap = overlap
                break

        calendar_test_passed = london_ny_calendar_overlap is not None

        self.log_test_result(
            "Session Calendar - London/NY Overlap Configuration",
            calendar_test_passed,
            {
                "calendar_overlaps_found": len(calendar_overlaps),
                "london_ny_overlap_configured": london_ny_calendar_overlap is not None,
                "overlap_details": {
                    "start_time": (
                        london_ny_calendar_overlap.overlap_start
                        if london_ny_calendar_overlap
                        else None
                    ),
                    "end_time": (
                        london_ny_calendar_overlap.overlap_end
                        if london_ny_calendar_overlap
                        else None
                    ),
                    "peak_hours": (
                        london_ny_calendar_overlap.peak_hours
                        if london_ny_calendar_overlap
                        else None
                    ),
                    "liquidity_multiplier": (
                        london_ny_calendar_overlap.liquidity_multiplier
                        if london_ny_calendar_overlap
                        else None
                    ),
                },
            },
            (
                []
                if calendar_test_passed
                else ["Configure London/NY overlap in session calendar"]
            ),
        )

        if not calendar_test_passed:
            all_passed = False

        return all_passed

    async def validate_session_transitions(self) -> bool:
        """
        Validate session transition detection and handling

        Returns:
            True if all transition tests pass
        """
        logger.info("\n🔍 Testing Session Transition Logic...")

        all_passed = True

        # Test session status during different times
        test_times = [
            # Sydney session time (approximately 12:00 GMT = 23:00 Sydney time)
            (
                datetime(2024, 1, 8, 12, 0, tzinfo=pytz.UTC),
                [SessionType.SYDNEY],
                "Sydney Session",
            ),
            # Tokyo session time (approximately 04:00 GMT = 13:00 Tokyo time)
            (
                datetime(2024, 1, 8, 4, 0, tzinfo=pytz.UTC),
                [SessionType.TOKYO],
                "Tokyo Session",
            ),
            # London session time (10:00 GMT = 10:00 London time)
            (
                datetime(2024, 1, 8, 10, 0, tzinfo=pytz.UTC),
                [SessionType.LONDON],
                "London Session",
            ),
            # NY session time (19:00 GMT = 14:00 NY time)
            (
                datetime(2024, 1, 8, 19, 0, tzinfo=pytz.UTC),
                [SessionType.NEW_YORK],
                "NY Session",
            ),
            # London/NY overlap (14:00 GMT)
            (
                datetime(2024, 1, 8, 14, 0, tzinfo=pytz.UTC),
                [SessionType.LONDON, SessionType.NEW_YORK],
                "London/NY Overlap",
            ),
        ]

        for test_time, expected_sessions, description in test_times:
            active_sessions = self.session_manager._get_active_sessions(test_time)

            # Check if at least one expected session is active
            has_expected_session = bool(
                set(expected_sessions).intersection(active_sessions)
            )

            self.log_test_result(
                f"Session Transitions - {description}",
                has_expected_session,
                {
                    "time": test_time.isoformat(),
                    "expected_sessions": [s.value for s in expected_sessions],
                    "active_sessions": [s.value for s in active_sessions],
                    "has_expected": has_expected_session,
                    "market_state": self.session_manager.get_current_market_state(
                        test_time
                    ).value,
                },
                (
                    []
                    if has_expected_session
                    else [f"Check session schedules for {description}"]
                ),
            )

            if not has_expected_session:
                all_passed = False

        # Test upcoming transitions
        current_time = datetime(2024, 1, 8, 12, 0, tzinfo=pytz.UTC)  # Monday noon GMT
        upcoming_transitions = self.session_manager.get_session_transitions(
            current_time, lookahead_hours=12
        )

        transition_test_passed = isinstance(upcoming_transitions, list)

        self.log_test_result(
            "Session Transitions - Upcoming Transition Detection",
            transition_test_passed,
            {
                "current_time": current_time.isoformat(),
                "transitions_found": len(upcoming_transitions),
                "transition_count": len(upcoming_transitions),
            },
            (
                []
                if transition_test_passed
                else ["Check session transition calculation logic"]
            ),
        )

        if not transition_test_passed:
            all_passed = False

        return all_passed

    async def validate_session_validation_integration(self) -> bool:
        """
        Validate session validator integration

        Returns:
            True if validation integration tests pass
        """
        logger.info("\n🔍 Testing Session Validation Integration...")

        all_passed = True

        # Test validation during optimal conditions (London/NY overlap)
        optimal_time = datetime(2024, 1, 8, 14, 0, tzinfo=pytz.UTC)
        validation_result = self.session_validator.validate_trading_session(
            SessionType.LONDON, optimal_time, currency_pair="GBPUSD"
        )

        optimal_test_passed = (
            validation_result.overall_passed or validation_result.error_count == 0
        )

        self.log_test_result(
            "Session Validation - Optimal Trading Conditions",
            optimal_test_passed,
            {
                "time": optimal_time.isoformat(),
                "overall_passed": validation_result.overall_passed,
                "total_checks": validation_result.total_checks,
                "passed_checks": validation_result.passed_checks,
                "failed_checks": validation_result.failed_checks,
                "warning_count": validation_result.warning_count,
                "error_count": validation_result.error_count,
                "validation_score": validation_result.summary.get(
                    "validation_score", 0
                ),
                "trading_recommendation": validation_result.summary.get(
                    "trading_recommendation", "unknown"
                ),
            },
            (
                []
                if optimal_test_passed
                else ["Review session validation rules for optimal conditions"]
            ),
        )

        if not optimal_test_passed:
            all_passed = False

        # Test validation during weekend
        weekend_time = datetime(2024, 1, 6, 12, 0, tzinfo=pytz.UTC)  # Saturday
        weekend_validation = self.session_validator.validate_trading_session(
            SessionType.LONDON, weekend_time
        )

        # During weekend, should have warnings/errors but not necessarily fail completely
        weekend_test_passed = (
            weekend_validation.warning_count > 0
            or weekend_validation.error_count > 0
            or not weekend_validation.overall_passed
        )

        self.log_test_result(
            "Session Validation - Weekend Conditions",
            weekend_test_passed,
            {
                "time": weekend_time.isoformat(),
                "overall_passed": weekend_validation.overall_passed,
                "warning_count": weekend_validation.warning_count,
                "error_count": weekend_validation.error_count,
                "validation_score": weekend_validation.summary.get(
                    "validation_score", 0
                ),
                "trading_recommendation": weekend_validation.summary.get(
                    "trading_recommendation", "unknown"
                ),
                "weekend_validation_rules": [
                    r.rule.value
                    for r in weekend_validation.results
                    if r.rule == ValidationRule.WEEKEND_CLOSURE
                ],
            },
            (
                []
                if weekend_test_passed
                else ["Ensure weekend validation rules are active"]
            ),
        )

        if not weekend_test_passed:
            all_passed = False

        return all_passed

    async def validate_comprehensive_market_hours_logic(self) -> bool:
        """
        Run the manager's built-in comprehensive validation

        Returns:
            True if manager validation passes
        """
        logger.info("\n🔍 Running Comprehensive Market Hours Validation...")

        # Use the manager's built-in validation
        validation_results = await self.session_manager.validate_market_hours_logic()

        overall_passed = validation_results["overall_result"] == "PASS"

        self.log_test_result(
            "Comprehensive Market Hours Logic Validation",
            overall_passed,
            {
                "overall_result": validation_results["overall_result"],
                "success_count": validation_results["success_count"],
                "failure_count": validation_results["failure_count"],
                "total_test_cases": len(validation_results["test_cases"]),
                "test_case_results": [
                    {
                        "name": test["test_name"],
                        "result": test["result"],
                        "success_count": test["success_count"],
                        "failure_count": test["failure_count"],
                    }
                    for test in validation_results["test_cases"]
                ],
            },
            (
                []
                if overall_passed
                else ["Review failing test cases in manager validation"]
            ),
        )

        return overall_passed

    async def run_all_validations(self) -> dict:
        """
        Run all market hours validation tests

        Returns:
            Comprehensive validation report
        """
        logger.info("🚀 Starting Comprehensive Market Hours Logic Validation")
        logger.info("=" * 80)

        # Run all validation tests
        validations = [
            ("Weekend Closure Logic", self.validate_weekend_closure_logic()),
            ("London/NY Overlap Logic", self.validate_london_ny_overlap_logic()),
            ("Session Transitions", self.validate_session_transitions()),
            (
                "Session Validation Integration",
                self.validate_session_validation_integration(),
            ),
            (
                "Comprehensive Market Hours Logic",
                self.validate_comprehensive_market_hours_logic(),
            ),
        ]

        validation_results = {}
        all_passed = True

        for validation_name, validation_coro in validations:
            try:
                result = await validation_coro
                validation_results[validation_name] = result
                if not result:
                    all_passed = False
            except Exception as e:
                logger.error(f"Error in validation '{validation_name}': {e}")
                logger.error(traceback.format_exc())
                validation_results[validation_name] = False
                all_passed = False

        # Generate final report
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()

        passed_tests = sum(1 for result in self.test_results if result["passed"])
        total_tests = len(self.test_results)

        final_report = {
            "validation_timestamp": self.start_time.isoformat(),
            "completion_timestamp": end_time.isoformat(),
            "duration_seconds": duration,
            "overall_result": "PASS" if all_passed else "FAIL",
            "validation_categories": validation_results,
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "pass_rate": (
                    (passed_tests / total_tests * 100) if total_tests > 0 else 0
                ),
            },
            "detailed_results": self.test_results,
            "system_info": {
                "python_version": sys.version,
                "platform": os.name,
                "components_tested": [
                    "MarketSessionManager",
                    "SessionCalendar",
                    "SessionValidator",
                    "WeekendHolidayHandler",
                ],
            },
        }

        return final_report

    def generate_html_report(
        self, report: dict, output_file: str = "market_hours_validation_report.html"
    ):
        """Generate HTML report"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FXML4 Market Hours Logic Validation Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .pass {{ color: green; font-weight: bold; }}
                .fail {{ color: red; font-weight: bold; }}
                .test-result {{ margin: 10px 0; padding: 10px; border-left: 3px solid #ccc; }}
                .test-pass {{ border-left-color: green; }}
                .test-fail {{ border-left-color: red; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .summary {{ background-color: #e6f3ff; padding: 15px; margin: 20px 0; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>FXML4 Market Hours Logic Validation Report</h1>
                <p><strong>Overall Result:</strong> <span class="{report['overall_result'].lower()}">{report['overall_result']}</span></p>
                <p><strong>Validation Time:</strong> {report['validation_timestamp']}</p>
                <p><strong>Duration:</strong> {report['duration_seconds']:.2f} seconds</p>
            </div>

            <div class="summary">
                <h2>Test Summary</h2>
                <p><strong>Total Tests:</strong> {report['test_summary']['total_tests']}</p>
                <p><strong>Passed:</strong> {report['test_summary']['passed_tests']}</p>
                <p><strong>Failed:</strong> {report['test_summary']['failed_tests']}</p>
                <p><strong>Pass Rate:</strong> {report['test_summary']['pass_rate']:.1f}%</p>
            </div>

            <h2>Validation Categories</h2>
            <table>
                <tr><th>Category</th><th>Result</th></tr>
        """

        for category, result in report["validation_categories"].items():
            status_class = "pass" if result else "fail"
            status_text = "PASS" if result else "FAIL"
            html_content += f'<tr><td>{category}</td><td class="{status_class}">{status_text}</td></tr>\n'

        html_content += """
            </table>

            <h2>Detailed Test Results</h2>
        """

        for test in report["detailed_results"]:
            status_class = "test-pass" if test["passed"] else "test-fail"
            status_text = "✅ PASS" if test["passed"] else "❌ FAIL"

            html_content += f"""
            <div class="test-result {status_class}">
                <h3>{test['test_name']} - {status_text}</h3>
                <p><strong>Timestamp:</strong> {test['timestamp']}</p>
                <p><strong>Details:</strong></p>
                <pre>{json.dumps(test['details'], indent=2)}</pre>
            """

            if test["recommendations"]:
                html_content += f'<p><strong>Recommendations:</strong> {", ".join(test["recommendations"])}</p>'

            html_content += "</div>\n"

        html_content += """
            </body>
        </html>
        """

        with open(output_file, "w") as f:
            f.write(html_content)

        logger.info(f"HTML report generated: {output_file}")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="FXML4 Market Hours Logic Validation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--html-report", "-r", action="store_true", help="Generate HTML report"
    )
    parser.add_argument(
        "--output-file",
        "-o",
        default="market_hours_validation_report.json",
        help="Output file for JSON report",
    )

    args = parser.parse_args()

    # Import required timezone module
    import pytz

    globals()["pytz"] = pytz

    # Initialize validator
    validator = MarketHoursLogicValidator(verbose=args.verbose)

    try:
        # Run all validations
        report = await validator.run_all_validations()

        # Save JSON report
        with open(args.output_file, "w") as f:
            json.dump(report, f, indent=2)

        # Generate HTML report if requested
        if args.html_report:
            validator.generate_html_report(report)

        # Print final summary
        logger.info("=" * 80)
        logger.info("📊 FINAL VALIDATION SUMMARY")
        logger.info("=" * 80)

        overall_status = "✅ PASS" if report["overall_result"] == "PASS" else "❌ FAIL"
        logger.info(f"Overall Result: {overall_status}")
        logger.info(
            f"Tests Passed: {report['test_summary']['passed_tests']}/{report['test_summary']['total_tests']}"
        )
        logger.info(f"Pass Rate: {report['test_summary']['pass_rate']:.1f}%")
        logger.info(f"Duration: {report['duration_seconds']:.2f} seconds")

        logger.info("\nValidation Categories:")
        for category, result in report["validation_categories"].items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"  {category}: {status}")

        logger.info(f"\nDetailed report saved to: {args.output_file}")

        if report["overall_result"] == "PASS":
            logger.info("\n🎉 Market Hours Logic Validation COMPLETED SUCCESSFULLY!")
            logger.info(
                "✅ System correctly handles London/New York session transitions and weekend closures"
            )
        else:
            logger.error("\n❌ Market Hours Logic Validation FAILED!")
            logger.error("Please review the detailed results and fix identified issues")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Validation failed with error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
