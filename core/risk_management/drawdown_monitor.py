"""
Maximum Drawdown Monitor - TDD Implementation (GREEN Phase)
Minimal implementation to make tests pass
"""

import math
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


class DrawdownMonitor:
    """
    Monitor and analyze portfolio drawdown metrics.
    GREEN phase: Minimal implementation to pass tests.
    """

    def __init__(
        self,
        initial_balance: float = 100000,
        drawdown_warning_threshold: float = 10.0,
        drawdown_critical_threshold: float = 20.0,
        drawdown_emergency_threshold: float = 15.0,
        daily_loss_limit: float = 5000,
        daily_loss_warning: float = 3000,
        drawdown_threshold: float = 1000,
    ):
        """Initialize drawdown monitor."""
        self.initial_balance = initial_balance
        self.drawdown_warning_threshold = drawdown_warning_threshold
        self.drawdown_critical_threshold = drawdown_critical_threshold
        self.drawdown_emergency_threshold = drawdown_emergency_threshold
        self.daily_loss_limit = daily_loss_limit
        self.daily_loss_warning = daily_loss_warning
        self.drawdown_threshold = drawdown_threshold

        # Equity tracking
        self.equity_history = []
        self.peak_equity = initial_balance
        self.peak_timestamp = None
        self.current_equity = initial_balance
        self.current_timestamp = None

        # Drawdown tracking
        self.max_drawdown_amount = 0
        self.max_drawdown_percentage = 0
        self.max_drawdown_peak = initial_balance
        self.max_drawdown_trough = initial_balance
        self.max_drawdown_peak_time = None
        self.max_drawdown_trough_time = None

        # Recovery tracking
        self.drawdown_start_time = None
        self.in_drawdown = False
        self.last_recovery_time = None
        self.recovery_cycles = []

        # Daily tracking
        self.daily_results = []
        self.losing_streak = 0
        self.max_losing_streak = 0
        self.total_losing_days = 0

        # Alert system
        self.active_alerts = []

    def update_equity(self, equity: float, timestamp: datetime) -> None:
        """Update equity and recalculate drawdown metrics."""
        # Validation
        if equity < 0:
            raise ValueError("Equity cannot be negative")
        if timestamp is None:
            raise ValueError("Invalid timestamp")

        # Store equity point
        self.equity_history.append({"equity": equity, "timestamp": timestamp})
        self.current_equity = equity
        self.current_timestamp = timestamp

        # Update peak if new high
        if equity > self.peak_equity:
            # Check if recovering from drawdown
            if self.in_drawdown:
                self._record_recovery()

            self.peak_equity = equity
            self.peak_timestamp = timestamp
            self.in_drawdown = False
            self.drawdown_start_time = None
        else:
            # Calculate current drawdown from current peak
            drawdown_amount = self.peak_equity - equity
            drawdown_percentage = (drawdown_amount / self.peak_equity) * 100

            # Start tracking drawdown if significant
            if drawdown_amount > 0:
                if not self.in_drawdown:
                    self.in_drawdown = True
                    self.drawdown_start_time = timestamp

        # Always recalculate maximum drawdown from all historical peaks
        self._recalculate_max_drawdown()

        # Generate alerts
        self._update_alerts()

    def get_current_drawdown(self) -> Dict[str, Any]:
        """Get current drawdown information."""
        if not self.equity_history:
            return {
                "peak_equity": self.initial_balance,
                "current_equity": self.initial_balance,
                "drawdown_amount": 0,
                "drawdown_percentage": 0,
                "in_drawdown": False,
            }

        drawdown_amount = max(0, self.peak_equity - self.current_equity)
        drawdown_percentage = (
            (drawdown_amount / self.peak_equity) * 100 if self.peak_equity > 0 else 0
        )

        return {
            "peak_equity": self.peak_equity,
            "current_equity": self.current_equity,
            "drawdown_amount": drawdown_amount,
            "drawdown_percentage": drawdown_percentage,
            "in_drawdown": self.in_drawdown,
        }

    def get_maximum_drawdown(self) -> Dict[str, Any]:
        """Get maximum historical drawdown."""
        return {
            "max_drawdown_amount": self.max_drawdown_amount,
            "max_drawdown_percentage": self.max_drawdown_percentage,
            "peak_equity": self.max_drawdown_peak,
            "trough_equity": self.max_drawdown_trough,
            "peak_time": self.max_drawdown_peak_time,
            "trough_time": self.max_drawdown_trough_time,
        }

    def get_recovery_info(self) -> Dict[str, Any]:
        """Get information about drawdown recovery."""
        if not self.recovery_cycles:
            return {
                "recovered": False,
                "recovery_time_hours": 0,
                "max_drawdown_during_period": 0,
                "new_peak": self.peak_equity,
            }

        last_cycle = self.recovery_cycles[-1]
        return {
            "recovered": True,
            "recovery_time_hours": last_cycle["recovery_time_hours"],
            "max_drawdown_during_period": last_cycle["max_drawdown_amount"],
            "new_peak": last_cycle["recovery_peak"],
        }

    def get_drawdown_duration(self, current_time: datetime) -> Dict[str, Any]:
        """Get duration of current drawdown."""
        if not self.in_drawdown or not self.drawdown_start_time:
            return {
                "hours": 0,
                "days": 0,
                "still_in_drawdown": False,
            }

        duration = current_time - self.drawdown_start_time
        hours = duration.total_seconds() / 3600
        days = hours / 24

        return {
            "hours": int(hours),
            "days": days,
            "still_in_drawdown": self.in_drawdown,
        }

    def get_underwater_analysis(self) -> Dict[str, Any]:
        """Analyze time spent underwater (below previous highs)."""
        if len(self.equity_history) < 2:
            return {
                "total_underwater_time_hours": 0,
                "underwater_percentage": 0,
                "longest_underwater_period_hours": 0,
            }

        underwater_periods = []
        underwater_start = None
        running_peak = self.initial_balance

        for point in self.equity_history:
            equity = point["equity"]
            timestamp = point["timestamp"]

            if equity > running_peak:
                # New high - end underwater period if active
                if underwater_start:
                    duration = (timestamp - underwater_start).total_seconds() / 3600
                    underwater_periods.append(duration)
                    underwater_start = None
                running_peak = equity
            else:
                # Below peak - start underwater period if not already started
                if not underwater_start:
                    underwater_start = timestamp

        # Handle ongoing underwater period
        if underwater_start and self.current_timestamp:
            duration = (
                self.current_timestamp - underwater_start
            ).total_seconds() / 3600
            underwater_periods.append(duration)

        total_time = (
            (
                self.current_timestamp - self.equity_history[0]["timestamp"]
            ).total_seconds()
            / 3600
            if self.current_timestamp and self.equity_history
            else 0
        )

        total_underwater = sum(underwater_periods)
        underwater_percentage = (
            (total_underwater / total_time * 100) if total_time > 0 else 0
        )
        longest_period = max(underwater_periods) if underwater_periods else 0

        return {
            "total_underwater_time_hours": int(total_underwater),
            "underwater_percentage": underwater_percentage,
            "longest_underwater_period_hours": int(longest_period),
        }

    def record_daily_result(self, daily_pnl: float) -> None:
        """Record daily P&L result."""
        self.daily_results.append(daily_pnl)

        if daily_pnl < 0:
            self.losing_streak += 1
            self.total_losing_days += 1
            self.max_losing_streak = max(self.max_losing_streak, self.losing_streak)
        else:
            self.losing_streak = 0

    def get_losing_streak_info(self) -> Dict[str, Any]:
        """Get losing streak information."""
        return {
            "current_consecutive_losses": self.losing_streak,
            "max_consecutive_losses": self.max_losing_streak,
            "total_losing_days": self.total_losing_days,
        }

    def calculate_recovery_factor(self) -> Dict[str, Any]:
        """Calculate recovery factor after drawdowns."""
        if not self.recovery_cycles or self.max_drawdown_amount == 0:
            return {
                "factor": 0,
                "drawdown_amount": 0,
                "recovery_amount": 0,
                "recovery_strength": "none",
            }

        # Use the largest drawdown-recovery cycle
        max_cycle = max(self.recovery_cycles, key=lambda x: x["max_drawdown_amount"])
        drawdown_amount = max_cycle["max_drawdown_amount"]
        recovery_amount = max_cycle["recovery_amount"]

        factor = recovery_amount / drawdown_amount if drawdown_amount > 0 else 0

        if factor >= 1.0:
            strength = "full"
        elif factor >= 0.8:
            strength = "strong"
        elif factor >= 0.5:
            strength = "partial"
        else:
            strength = "weak"

        return {
            "factor": factor,
            "drawdown_amount": drawdown_amount,
            "recovery_amount": recovery_amount,
            "recovery_strength": strength,
        }

    def check_daily_limits(self) -> Dict[str, Any]:
        """Check daily loss limits."""
        if not self.equity_history or len(self.equity_history) < 2:
            return {
                "daily_loss": 0,
                "limit_exceeded": False,
                "warning_triggered": False,
                "severity": "normal",
            }

        # Get today's start and current equity
        start_equity = self.equity_history[0][
            "equity"
        ]  # Simplified - should be start of day
        current_equity = self.current_equity
        daily_loss = max(0, start_equity - current_equity)

        limit_exceeded = daily_loss > self.daily_loss_limit
        warning_triggered = daily_loss > self.daily_loss_warning

        if limit_exceeded:
            severity = "critical"
        elif warning_triggered:
            severity = "warning"
        else:
            severity = "normal"

        return {
            "daily_loss": daily_loss,
            "limit_exceeded": limit_exceeded,
            "warning_triggered": warning_triggered,
            "severity": severity,
        }

    def calculate_pain_index(self) -> Dict[str, Any]:
        """Calculate pain index for drawdown periods."""
        if len(self.equity_history) < 2:
            return {
                "pain_index": 0,
                "average_drawdown_percentage": 0,
                "pain_severity": "none",
            }

        # Calculate drawdown percentages for each point
        drawdown_percentages = []
        running_peak = self.initial_balance

        for point in self.equity_history:
            equity = point["equity"]
            if equity > running_peak:
                running_peak = equity

            drawdown_pct = (
                ((running_peak - equity) / running_peak) * 100
                if running_peak > 0
                else 0
            )
            drawdown_percentages.append(drawdown_pct)

        # Pain index is average of all drawdown percentages
        pain_index = (
            sum(drawdown_percentages) / len(drawdown_percentages)
            if drawdown_percentages
            else 0
        )
        avg_drawdown = pain_index

        if pain_index > 15:
            severity = "severe"
        elif pain_index > 10:
            severity = "high"
        elif pain_index > 5:
            severity = "moderate"
        else:
            severity = "low"

        return {
            "pain_index": pain_index,
            "average_drawdown_percentage": avg_drawdown,
            "pain_severity": severity,
        }

    def get_volatility_adjusted_drawdown(self) -> Dict[str, Any]:
        """Get volatility-adjusted drawdown metrics."""
        if len(self.equity_history) < 3:
            return {
                "raw_max_drawdown": 0,
                "volatility": 0,
                "adjusted_drawdown": 0,
                "risk_adjusted_ratio": 0,
            }

        # Calculate equity volatility
        equity_values = [point["equity"] for point in self.equity_history]
        returns = []
        for i in range(1, len(equity_values)):
            ret = (equity_values[i] - equity_values[i - 1]) / equity_values[i - 1]
            returns.append(ret)

        volatility = statistics.stdev(returns) if len(returns) > 1 else 0
        volatility_pct = volatility * 100

        # Adjust drawdown for volatility
        raw_drawdown = self.max_drawdown_percentage
        adjusted_drawdown = raw_drawdown / max(
            volatility_pct, 1.0
        )  # Avoid division by zero
        risk_adjusted_ratio = (
            adjusted_drawdown / raw_drawdown if raw_drawdown > 0 else 0
        )

        return {
            "raw_max_drawdown": raw_drawdown,
            "volatility": volatility_pct,
            "adjusted_drawdown": adjusted_drawdown,
            "risk_adjusted_ratio": risk_adjusted_ratio,
        }

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active drawdown alerts."""
        return self.active_alerts.copy()

    def calculate_calmar_ratio(self) -> Dict[str, Any]:
        """Calculate Calmar ratio (annual return / max drawdown)."""
        if not self.equity_history or len(self.equity_history) < 2:
            return {
                "annual_return_percentage": 0,
                "max_drawdown_percentage": 0,
                "calmar_ratio": 0,
                "ratio": 0,
            }

        # Calculate annual return
        start_equity = self.equity_history[0]["equity"]
        end_equity = self.current_equity
        total_return_pct = ((end_equity - start_equity) / start_equity) * 100

        # Assume this represents annual performance for simplicity
        annual_return_pct = total_return_pct

        max_dd_pct = (
            self.max_drawdown_percentage if self.max_drawdown_percentage > 0 else 0.01
        )

        calmar_ratio = annual_return_pct / max_dd_pct if max_dd_pct > 0 else 0

        return {
            "annual_return_percentage": annual_return_pct,
            "max_drawdown_percentage": max_dd_pct,
            "calmar_ratio": calmar_ratio,
            "ratio": calmar_ratio,
        }

    def get_drawdown_frequency(self) -> Dict[str, Any]:
        """Get drawdown frequency statistics."""
        if len(self.equity_history) < 2:
            return {
                "total_drawdowns": 0,
                "average_drawdown_amount": 0,
                "drawdowns_per_day": 0,
            }

        # Count drawdowns above threshold
        drawdowns = []
        running_peak = self.initial_balance
        in_dd = False
        dd_start_peak = 0

        for point in self.equity_history:
            equity = point["equity"]

            if equity > running_peak:
                # New peak - end drawdown if active
                if in_dd and running_peak - equity >= self.drawdown_threshold:
                    drawdowns.append(dd_start_peak - equity)
                running_peak = equity
                dd_start_peak = equity
                in_dd = False
            else:
                # Potential drawdown
                if not in_dd:
                    in_dd = True

        # Handle ongoing drawdown
        if in_dd and dd_start_peak - self.current_equity >= self.drawdown_threshold:
            drawdowns.append(dd_start_peak - self.current_equity)

        total_drawdowns = len(drawdowns)
        avg_drawdown = sum(drawdowns) / total_drawdowns if drawdowns else 0

        # Calculate per-day frequency
        if self.equity_history:
            total_time = (
                self.current_timestamp - self.equity_history[0]["timestamp"]
            ).total_seconds() / (
                24 * 3600
            )  # days
            drawdowns_per_day = total_drawdowns / max(total_time, 1)
        else:
            drawdowns_per_day = 0

        return {
            "total_drawdowns": total_drawdowns,
            "average_drawdown_amount": avg_drawdown,
            "drawdowns_per_day": drawdowns_per_day,
        }

    def analyze_recovery_patterns(self) -> Dict[str, Any]:
        """Analyze drawdown recovery patterns."""
        if len(self.recovery_cycles) < 1:
            return {
                "total_recovery_cycles": 0,
                "average_recovery_time_hours": 0,
                "recovery_success_rate": 0,
                "fastest_recovery_hours": 0,
            }

        recovery_times = [
            cycle["recovery_time_hours"] for cycle in self.recovery_cycles
        ]
        successful_recoveries = len(
            [c for c in self.recovery_cycles if c["recovery_amount"] > 0]
        )

        return {
            "total_recovery_cycles": len(self.recovery_cycles),
            "average_recovery_time_hours": sum(recovery_times) / len(recovery_times),
            "recovery_success_rate": successful_recoveries / len(self.recovery_cycles),
            "fastest_recovery_hours": min(recovery_times) if recovery_times else 0,
        }

    def calculate_sterling_ratio(self) -> Dict[str, Any]:
        """Calculate Sterling ratio (return / average drawdown)."""
        if not self.equity_history or len(self.equity_history) < 2:
            return {
                "total_return_percentage": 0,
                "average_drawdown_percentage": 0,
                "sterling_ratio": 0,
            }

        # Calculate total return
        start_equity = self.equity_history[0]["equity"]
        end_equity = self.current_equity
        total_return_pct = ((end_equity - start_equity) / start_equity) * 100

        # Calculate average drawdown
        pain_index = self.calculate_pain_index()
        avg_drawdown_pct = pain_index["average_drawdown_percentage"]

        sterling_ratio = (
            total_return_pct / max(avg_drawdown_pct, 0.01)
            if avg_drawdown_pct > 0
            else 0
        )

        return {
            "total_return_percentage": total_return_pct,
            "average_drawdown_percentage": avg_drawdown_pct,
            "sterling_ratio": sterling_ratio,
        }

    def _record_recovery(self) -> None:
        """Record a recovery event."""
        if not self.drawdown_start_time or not self.current_timestamp:
            return

        recovery_time = (
            self.current_timestamp - self.drawdown_start_time
        ).total_seconds() / 3600

        # Find max drawdown during this period
        max_dd_in_period = 0
        start_peak = self.peak_equity

        for point in self.equity_history:
            if point["timestamp"] >= self.drawdown_start_time:
                dd = start_peak - point["equity"]
                max_dd_in_period = max(max_dd_in_period, dd)

        recovery_amount = self.current_equity - (start_peak - max_dd_in_period)

        self.recovery_cycles.append(
            {
                "recovery_time_hours": recovery_time,
                "max_drawdown_amount": max_dd_in_period,
                "recovery_amount": recovery_amount,
                "recovery_peak": self.current_equity,
                "start_time": self.drawdown_start_time,
                "end_time": self.current_timestamp,
            }
        )

        self.last_recovery_time = self.current_timestamp

    def _update_alerts(self) -> None:
        """Update active alerts based on current conditions."""
        self.active_alerts = []  # Clear existing alerts

        current_dd = self.get_current_drawdown()
        dd_pct = current_dd["drawdown_percentage"]

        if dd_pct >= self.drawdown_emergency_threshold:
            self.active_alerts.append(
                {
                    "type": "drawdown_emergency",
                    "severity": "emergency",
                    "message": f"Emergency drawdown threshold breached: {dd_pct:.1f}%",
                    "timestamp": self.current_timestamp,
                }
            )
        elif dd_pct >= self.drawdown_critical_threshold:
            self.active_alerts.append(
                {
                    "type": "drawdown_critical",
                    "severity": "critical",
                    "message": f"Critical drawdown threshold breached: {dd_pct:.1f}%",
                    "timestamp": self.current_timestamp,
                }
            )
        elif dd_pct >= self.drawdown_warning_threshold:
            self.active_alerts.append(
                {
                    "type": "drawdown_warning",
                    "severity": "warning",
                    "message": f"Warning drawdown threshold breached: {dd_pct:.1f}%",
                    "timestamp": self.current_timestamp,
                }
            )

        # Check daily limits
        daily_check = self.check_daily_limits()
        if daily_check["limit_exceeded"]:
            self.active_alerts.append(
                {
                    "type": "daily_loss_limit",
                    "severity": "critical",
                    "message": f"Daily loss limit exceeded: ${daily_check['daily_loss']:,.0f}",
                    "timestamp": self.current_timestamp,
                }
            )

    def _recalculate_max_drawdown(self) -> None:
        """Recalculate maximum drawdown from all historical data."""
        if len(self.equity_history) < 2:
            return

        max_dd = 0
        max_dd_pct = 0
        peak_equity = self.initial_balance
        peak_time = None
        trough_equity = self.initial_balance
        trough_time = None

        # Track running peak and calculate drawdowns
        running_peak = self.initial_balance
        running_peak_time = None

        for point in self.equity_history:
            equity = point["equity"]
            timestamp = point["timestamp"]

            if equity > running_peak:
                running_peak = equity
                running_peak_time = timestamp
            else:
                # Calculate drawdown from current running peak
                dd_amount = running_peak - equity
                dd_pct = (dd_amount / running_peak) * 100 if running_peak > 0 else 0

                if dd_amount > max_dd:
                    max_dd = dd_amount
                    max_dd_pct = dd_pct
                    peak_equity = running_peak
                    peak_time = running_peak_time
                    trough_equity = equity
                    trough_time = timestamp

        # Update maximum drawdown if we found a larger one
        if max_dd > self.max_drawdown_amount:
            self.max_drawdown_amount = max_dd
            self.max_drawdown_percentage = max_dd_pct
            self.max_drawdown_peak = peak_equity
            self.max_drawdown_trough = trough_equity
            self.max_drawdown_peak_time = peak_time
            self.max_drawdown_trough_time = trough_time
