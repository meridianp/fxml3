"""
TDD Tests for Maximum Drawdown Monitor - RED Phase
Comprehensive drawdown tracking and risk monitoring
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List
from unittest.mock import Mock, patch

import pytest

# Import the monitor we're testing (will be created in GREEN phase)
from core.risk_management.drawdown_monitor import DrawdownMonitor


class TestDrawdownMonitor:
    """
    TDD tests for Maximum Drawdown Monitor following Red-Green-Refactor.
    Critical component for tracking portfolio performance degradation.
    """

    # ========== RED PHASE: Write Failing Tests First ==========

    def test_tracks_running_drawdown(self):
        """
        RED: Track running drawdown from peak equity
        Requirement: Monitor current drawdown at all times
        """
        # Arrange
        monitor = DrawdownMonitor(
            initial_balance=100000,
            drawdown_warning_threshold=10.0,  # 10% warning
            drawdown_critical_threshold=20.0,  # 20% critical
        )

        # Simulate equity changes
        equity_changes = [
            {"timestamp": datetime(2025, 1, 1, 9, 0), "equity": 105000},  # New peak
            {
                "timestamp": datetime(2025, 1, 1, 10, 0),
                "equity": 98000,
            },  # Drawdown starts
            {
                "timestamp": datetime(2025, 1, 1, 11, 0),
                "equity": 95000,
            },  # Deeper drawdown
        ]

        # Act
        for change in equity_changes:
            monitor.update_equity(change["equity"], change["timestamp"])

        current_drawdown = monitor.get_current_drawdown()

        # Assert
        assert current_drawdown["peak_equity"] == 105000
        assert current_drawdown["current_equity"] == 95000
        assert current_drawdown["drawdown_amount"] == 10000  # 105000 - 95000
        assert current_drawdown["drawdown_percentage"] == pytest.approx(
            9.52, abs=0.01
        )  # 10000/105000
        assert current_drawdown["in_drawdown"] == True

    def test_calculates_maximum_drawdown(self):
        """
        RED: Calculate maximum historical drawdown
        Requirement: Track worst drawdown period ever experienced
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # Simulate major drawdown period
        equity_history = [
            100000,
            110000,
            120000,  # Growth to peak
            115000,
            105000,
            95000,  # First drawdown (25k from peak)
            100000,
            108000,  # Recovery
            102000,
            85000,  # Second drawdown (23k from local peak)
            90000,
            95000,  # Recovery
        ]

        # Act
        for i, equity in enumerate(equity_history):
            timestamp = datetime(2025, 1, 1) + timedelta(hours=i)
            monitor.update_equity(equity, timestamp)

        max_drawdown = monitor.get_maximum_drawdown()

        # Assert
        assert max_drawdown["max_drawdown_amount"] == 25000  # 120000 - 95000
        assert max_drawdown["max_drawdown_percentage"] == pytest.approx(
            20.83, abs=0.01
        )  # 25000/120000
        assert max_drawdown["peak_equity"] == 120000
        assert max_drawdown["trough_equity"] == 95000

    def test_detects_drawdown_recovery(self):
        """
        RED: Detect when drawdown recovers to new high
        Requirement: Track recovery periods and duration
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # Simulate drawdown and recovery
        equity_sequence = [
            {"equity": 105000, "time": datetime(2025, 1, 1, 9, 0)},  # Peak
            {"equity": 95000, "time": datetime(2025, 1, 1, 10, 0)},  # Drawdown
            {"equity": 90000, "time": datetime(2025, 1, 1, 11, 0)},  # Deeper
            {"equity": 100000, "time": datetime(2025, 1, 1, 14, 0)},  # Partial recovery
            {"equity": 106000, "time": datetime(2025, 1, 1, 15, 0)},  # New high
        ]

        # Act
        for seq in equity_sequence:
            monitor.update_equity(seq["equity"], seq["time"])

        recovery_info = monitor.get_recovery_info()

        # Assert
        assert recovery_info["recovered"] == True
        assert recovery_info["recovery_time_hours"] == 6  # 9am to 3pm
        assert recovery_info["max_drawdown_during_period"] == 15000  # 105000 - 90000
        assert recovery_info["new_peak"] == 106000

    def test_calculates_drawdown_duration(self):
        """
        RED: Calculate duration of drawdown periods
        Requirement: Track how long drawdowns last
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # Start drawdown
        monitor.update_equity(110000, datetime(2025, 1, 1, 9, 0))  # Peak
        monitor.update_equity(95000, datetime(2025, 1, 1, 10, 0))  # Start DD
        monitor.update_equity(90000, datetime(2025, 1, 1, 12, 0))  # Continue DD

        # Check duration while in drawdown
        current_time = datetime(2025, 1, 1, 14, 0)
        duration = monitor.get_drawdown_duration(current_time)

        # Assert
        assert duration["hours"] == 4  # 10am to 2pm
        assert duration["days"] == pytest.approx(0.17, abs=0.01)  # 4/24
        assert duration["still_in_drawdown"] == True

    def test_identifies_underwater_periods(self):
        """
        RED: Identify periods below previous highs
        Requirement: Track time spent below peak performance
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # Simulate extended underwater period
        start_time = datetime(2025, 1, 1, 9, 0)
        equity_points = [
            (110000, 0),  # Peak at 9am
            (105000, 1),  # 10am - underwater starts
            (102000, 2),  # 11am - still underwater
            (108000, 3),  # 12pm - still underwater (below 110k)
            (112000, 4),  # 1pm - new high, underwater ends
        ]

        # Act
        for equity, hour_offset in equity_points:
            timestamp = start_time + timedelta(hours=hour_offset)
            monitor.update_equity(equity, timestamp)

        underwater_stats = monitor.get_underwater_analysis()

        # Assert
        assert underwater_stats["total_underwater_time_hours"] == 3  # 10am to 1pm
        assert underwater_stats["underwater_percentage"] == pytest.approx(
            75.0, abs=0.1
        )  # 3/4 hours
        assert underwater_stats["longest_underwater_period_hours"] == 3

    def test_tracks_consecutive_losses(self):
        """
        RED: Track consecutive losing periods
        Requirement: Monitor losing streaks for risk assessment
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # Simulate daily equity changes
        daily_equities = [
            100000,  # Day 0 (starting)
            98000,  # Day 1 (loss)
            96000,  # Day 2 (loss)
            94000,  # Day 3 (loss)
            97000,  # Day 4 (gain - breaks streak)
            95000,  # Day 5 (loss)
            93000,  # Day 6 (loss)
        ]

        # Act
        for i, equity in enumerate(daily_equities):
            date = datetime(2025, 1, 1) + timedelta(days=i)
            monitor.update_equity(equity, date)
            if i > 0:  # Skip first entry
                monitor.record_daily_result(equity - daily_equities[i - 1])

        streak_info = monitor.get_losing_streak_info()

        # Assert
        assert streak_info["current_consecutive_losses"] == 2  # Days 5-6
        assert streak_info["max_consecutive_losses"] == 3  # Days 1-3
        assert streak_info["total_losing_days"] == 5

    def test_calculates_recovery_factor(self):
        """
        RED: Calculate recovery factor (gain/loss ratio)
        Requirement: Measure recovery strength after drawdowns
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # Simulate major drawdown and recovery
        recovery_scenario = [
            (100000, datetime(2025, 1, 1)),  # Start
            (120000, datetime(2025, 1, 5)),  # Peak (+20k)
            (90000, datetime(2025, 1, 10)),  # Trough (-30k from peak)
            (115000, datetime(2025, 1, 15)),  # Recovery (+25k from trough)
        ]

        # Act
        for equity, timestamp in recovery_scenario:
            monitor.update_equity(equity, timestamp)

        recovery_factor = monitor.calculate_recovery_factor()

        # Assert
        # Recovery factor = Recovery amount / Drawdown amount = 25000 / 30000
        assert recovery_factor["factor"] == pytest.approx(0.83, abs=0.01)
        assert recovery_factor["drawdown_amount"] == 30000
        assert recovery_factor["recovery_amount"] == 25000
        assert recovery_factor["recovery_strength"] == "partial"  # < 1.0

    def test_monitors_daily_drawdown_limits(self):
        """
        RED: Monitor daily loss limits
        Requirement: Alert when daily losses exceed thresholds
        """
        # Arrange
        monitor = DrawdownMonitor(
            initial_balance=100000,
            daily_loss_limit=3000,  # $3k daily limit
            daily_loss_warning=2000,  # $2k warning threshold
        )

        start_equity = 100000
        monitor.update_equity(start_equity, datetime(2025, 1, 1, 9, 0))

        # Act - Simulate large daily loss
        end_equity = 96500  # $3,500 loss
        monitor.update_equity(end_equity, datetime(2025, 1, 1, 16, 0))

        daily_check = monitor.check_daily_limits()

        # Assert
        assert daily_check["daily_loss"] == 3500
        assert daily_check["limit_exceeded"] == True
        assert daily_check["warning_triggered"] == True
        assert daily_check["severity"] == "critical"

    def test_calculates_pain_index(self):
        """
        RED: Calculate pain index (measure of sustained losses)
        Requirement: Quantify psychological impact of drawdowns
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # Simulate prolonged drawdown period
        equity_data = [
            (100000, 0),  # Starting point
            (95000, 1),  # 5% down
            (92000, 2),  # 8% down
            (88000, 3),  # 12% down
            (90000, 4),  # 10% down (slight recovery)
            (85000, 5),  # 15% down (deeper)
        ]

        # Act
        start_time = datetime(2025, 1, 1)
        for equity, day_offset in equity_data:
            timestamp = start_time + timedelta(days=day_offset)
            monitor.update_equity(equity, timestamp)

        pain_index = monitor.calculate_pain_index()

        # Assert
        assert pain_index["pain_index"] > 0
        assert pain_index["average_drawdown_percentage"] > 5.0
        assert pain_index["pain_severity"] in ["moderate", "high", "severe"]

    def test_tracks_volatility_adjusted_drawdown(self):
        """
        RED: Adjust drawdown analysis for volatility
        Requirement: Account for market volatility in drawdown assessment
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # High volatility period with drawdown
        volatile_equity = [100000, 105000, 98000, 102000, 94000, 99000, 88000, 95000]

        # Act
        for i, equity in enumerate(volatile_equity):
            timestamp = datetime(2025, 1, 1) + timedelta(hours=i)
            monitor.update_equity(equity, timestamp)

        volatility_adjusted = monitor.get_volatility_adjusted_drawdown()

        # Assert
        assert volatility_adjusted["raw_max_drawdown"] > 0
        assert volatility_adjusted["volatility"] > 0
        assert volatility_adjusted["adjusted_drawdown"] > 0
        assert volatility_adjusted["risk_adjusted_ratio"] > 0

    def test_generates_drawdown_alerts(self):
        """
        RED: Generate alerts based on drawdown thresholds
        Requirement: Alert system for risk management
        """
        # Arrange
        monitor = DrawdownMonitor(
            initial_balance=100000,
            drawdown_warning_threshold=5.0,  # 5% warning
            drawdown_critical_threshold=10.0,  # 10% critical
            drawdown_emergency_threshold=15.0,  # 15% emergency
        )

        # Act - Simulate progressive drawdown
        monitor.update_equity(100000, datetime(2025, 1, 1, 9, 0))  # Start
        monitor.update_equity(94000, datetime(2025, 1, 1, 10, 0))  # 6% drawdown

        alerts = monitor.get_active_alerts()

        # Assert
        assert len(alerts) >= 1
        assert any(alert["type"] == "drawdown_warning" for alert in alerts)
        assert any(alert["severity"] == "warning" for alert in alerts)

    def test_calculates_calmar_ratio(self):
        """
        RED: Calculate Calmar ratio (return/max drawdown)
        Requirement: Risk-adjusted performance measurement
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # Simulate one year of performance
        annual_performance = [
            (100000, datetime(2024, 1, 1)),  # Start of year
            (120000, datetime(2024, 6, 1)),  # Mid-year peak
            (95000, datetime(2024, 8, 1)),  # Summer drawdown
            (115000, datetime(2024, 12, 31)),  # End of year
        ]

        # Act
        for equity, timestamp in annual_performance:
            monitor.update_equity(equity, timestamp)

        calmar_ratio = monitor.calculate_calmar_ratio()

        # Assert
        # Annual return = 15%, Max drawdown = 20.83% (25k/120k)
        assert calmar_ratio["annual_return_percentage"] == 15.0
        assert calmar_ratio["max_drawdown_percentage"] > 20.0
        assert calmar_ratio["calmar_ratio"] > 0
        assert calmar_ratio["ratio"] < 1.0  # Return < Max DD

    def test_tracks_drawdown_frequency(self):
        """
        RED: Track frequency of drawdown occurrences
        Requirement: Analyze drawdown patterns
        """
        # Arrange
        monitor = DrawdownMonitor(
            initial_balance=100000,
            drawdown_threshold=1000,  # $1k minimum to count as drawdown
        )

        # Simulate multiple small drawdowns
        equity_sequence = [
            100000,
            101000,
            99500,  # DD #1
            102000,
            100500,  # DD #2
            103000,
            101800,  # DD #3
            105000,  # Recovery
        ]

        # Act
        for i, equity in enumerate(equity_sequence):
            timestamp = datetime(2025, 1, 1) + timedelta(hours=i)
            monitor.update_equity(equity, timestamp)

        frequency_stats = monitor.get_drawdown_frequency()

        # Assert
        assert frequency_stats["total_drawdowns"] == 3
        assert frequency_stats["average_drawdown_amount"] > 1000
        assert frequency_stats["drawdowns_per_day"] > 0

    def test_identifies_recovery_patterns(self):
        """
        RED: Identify patterns in drawdown recovery
        Requirement: Analyze recovery characteristics
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # Multiple drawdown-recovery cycles
        cycles = [
            # Cycle 1: Quick recovery
            [(100000, 0), (95000, 1), (101000, 3)],
            # Cycle 2: Slow recovery
            [(101000, 3), (92000, 4), (103000, 10)],
            # Cycle 3: Partial recovery
            [(103000, 10), (89000, 11), (98000, 15)],
        ]

        # Act
        start_time = datetime(2025, 1, 1)
        for cycle in cycles:
            for equity, hour_offset in cycle:
                timestamp = start_time + timedelta(hours=hour_offset)
                monitor.update_equity(equity, timestamp)

        recovery_patterns = monitor.analyze_recovery_patterns()

        # Assert
        assert recovery_patterns["total_recovery_cycles"] >= 2
        assert recovery_patterns["average_recovery_time_hours"] > 0
        assert recovery_patterns["recovery_success_rate"] >= 0
        assert "fastest_recovery_hours" in recovery_patterns

    def test_calculates_sterling_ratio(self):
        """
        RED: Calculate Sterling ratio (return/average drawdown)
        Requirement: Alternative risk-adjusted return metric
        """
        # Arrange
        monitor = DrawdownMonitor(initial_balance=100000)

        # Simulate performance with multiple drawdowns
        performance_data = [
            100000,
            110000,
            105000,  # First peak and DD
            115000,
            108000,  # Second peak and DD
            120000,
            112000,  # Third peak and DD
            125000,  # Final value
        ]

        # Act
        for i, equity in enumerate(performance_data):
            timestamp = datetime(2025, 1, 1) + timedelta(days=i * 30)  # Monthly
            monitor.update_equity(equity, timestamp)

        sterling_ratio = monitor.calculate_sterling_ratio()

        # Assert
        assert sterling_ratio["total_return_percentage"] == 25.0  # 125k/100k - 1
        assert sterling_ratio["average_drawdown_percentage"] > 0
        assert sterling_ratio["sterling_ratio"] > 0


class TestDrawdownMonitorEdgeCases:
    """Test edge cases and error handling"""

    def test_handles_no_drawdown_scenario(self):
        """Handle continuous growth with no drawdowns"""
        monitor = DrawdownMonitor(initial_balance=100000)

        # Only upward equity movement
        for equity in [100000, 105000, 110000, 115000]:
            monitor.update_equity(equity, datetime.now())

        drawdown_info = monitor.get_current_drawdown()

        assert drawdown_info["drawdown_amount"] == 0
        assert drawdown_info["in_drawdown"] == False

    def test_handles_single_equity_point(self):
        """Handle case with only one equity data point"""
        monitor = DrawdownMonitor(initial_balance=100000)

        monitor.update_equity(105000, datetime.now())

        max_drawdown = monitor.get_maximum_drawdown()
        assert max_drawdown["max_drawdown_amount"] == 0

    def test_validates_equity_inputs(self):
        """Validate equity input parameters"""
        monitor = DrawdownMonitor(initial_balance=100000)

        # Test negative equity
        with pytest.raises(ValueError, match="Equity cannot be negative"):
            monitor.update_equity(-1000, datetime.now())

        # Test invalid timestamp
        with pytest.raises(ValueError, match="Invalid timestamp"):
            monitor.update_equity(100000, None)


class TestDrawdownMonitorPerformance:
    """Performance tests for drawdown monitoring"""

    @pytest.mark.performance
    def test_handles_large_equity_history(self):
        """Test performance with large equity history"""
        import time

        monitor = DrawdownMonitor(initial_balance=100000)

        # Simulate 10,000 equity updates
        start_time = time.perf_counter()

        base_time = datetime(2025, 1, 1)
        for i in range(10000):
            # Simulate realistic equity fluctuations
            equity = 100000 + (i % 1000) - 500  # Fluctuating around 100k
            timestamp = base_time + timedelta(minutes=i)
            monitor.update_equity(equity, timestamp)

        duration = (time.perf_counter() - start_time) * 1000  # ms

        # Should handle 10k updates in under 1 second
        assert duration < 1000, f"Performance test took {duration:.2f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=core.risk_management.drawdown_monitor"])
