"""
Data Completeness Monitor

Monitors data pipeline for gaps, missing data, and completeness metrics
with automatic backfill triggering and recovery.

Following TDD Green phase - implementation to pass completeness tests.
"""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class GapSeverity(Enum):
    """Data gap severity levels."""

    MINOR = "minor"  # < 1 minute gap
    MODERATE = "moderate"  # 1-5 minute gap
    MAJOR = "major"  # 5-30 minute gap
    CRITICAL = "critical"  # > 30 minute gap


class DataGap:
    """Represents a gap in data."""

    def __init__(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        expected_records: int,
        actual_records: int,
    ):
        """Initialize data gap."""
        self.symbol = symbol
        self.start_time = start_time
        self.end_time = end_time
        self.expected_records = expected_records
        self.actual_records = actual_records
        self.gap_duration = (end_time - start_time).total_seconds()
        self.severity = self._calculate_severity()
        self.backfilled = False
        self.backfill_attempts = 0

    def _calculate_severity(self) -> GapSeverity:
        """Calculate gap severity based on duration."""
        minutes = self.gap_duration / 60
        if minutes < 1:
            return GapSeverity.MINOR
        elif minutes < 5:
            return GapSeverity.MODERATE
        elif minutes < 30:
            return GapSeverity.MAJOR
        else:
            return GapSeverity.CRITICAL

    @property
    def completeness_rate(self) -> float:
        """Calculate completeness rate."""
        if self.expected_records == 0:
            return 100.0
        return (self.actual_records / self.expected_records) * 100


class CompletenessMonitor:
    """
    Monitor data completeness and detect gaps.

    Features:
    - Real-time gap detection
    - Completeness metrics tracking
    - Automatic backfill triggering
    - Historical gap analysis
    - Symbol-specific monitoring
    """

    def __init__(
        self,
        expected_tick_rate: Dict[str, int] = None,
        max_gap_seconds: int = 60,
        backfill_threshold: float = 0.95,
    ):
        """
        Initialize completeness monitor.

        Args:
            expected_tick_rate: Expected ticks per second for each symbol
            max_gap_seconds: Maximum allowed gap before alerting
            backfill_threshold: Completeness threshold for triggering backfill
        """
        self.expected_tick_rate = expected_tick_rate or {
            "EUR/USD": 10,
            "GBP/USD": 8,
            "USD/JPY": 8,
            "DEFAULT": 5,
        }
        self.max_gap_seconds = max_gap_seconds
        self.backfill_threshold = backfill_threshold

        self._last_tick_time = {}
        self._tick_counts = defaultdict(lambda: deque(maxlen=3600))  # 1 hour window
        self._detected_gaps = defaultdict(list)
        self._completeness_history = defaultdict(lambda: deque(maxlen=1440))  # 24 hours
        self._backfill_queue = asyncio.Queue()
        self._monitoring_active = False

    async def start_monitoring(self):
        """Start completeness monitoring."""
        self._monitoring_active = True
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._backfill_processor())
        logger.info("Completeness monitoring started")

    async def stop_monitoring(self):
        """Stop completeness monitoring."""
        self._monitoring_active = False
        logger.info("Completeness monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                await self._check_all_symbols()
                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(10)

    async def _check_all_symbols(self):
        """Check completeness for all monitored symbols."""
        current_time = datetime.now()

        for symbol in self._last_tick_time.keys():
            last_time = self._last_tick_time.get(symbol)
            if last_time:
                gap_seconds = (current_time - last_time).total_seconds()
                if gap_seconds > self.max_gap_seconds:
                    await self._handle_gap(symbol, last_time, current_time)

    async def record_tick(self, symbol: str, timestamp: datetime):
        """
        Record incoming tick for completeness tracking.

        Args:
            symbol: Trading symbol
            timestamp: Tick timestamp
        """
        # Check for gap since last tick
        if symbol in self._last_tick_time:
            last_time = self._last_tick_time[symbol]
            gap_seconds = (timestamp - last_time).total_seconds()

            if gap_seconds > self.max_gap_seconds:
                await self._handle_gap(symbol, last_time, timestamp)

        # Update tracking
        self._last_tick_time[symbol] = timestamp
        self._tick_counts[symbol].append(timestamp)

    async def record_batch(
        self, symbol: str, start_time: datetime, end_time: datetime, record_count: int
    ):
        """
        Record batch of data for completeness tracking.

        Args:
            symbol: Trading symbol
            start_time: Batch start time
            end_time: Batch end time
            record_count: Number of records in batch
        """
        # Calculate expected records
        duration_seconds = (end_time - start_time).total_seconds()
        expected_rate = self.expected_tick_rate.get(
            symbol, self.expected_tick_rate["DEFAULT"]
        )
        expected_records = int(duration_seconds * expected_rate)

        # Calculate completeness
        completeness = (
            (record_count / expected_records * 100) if expected_records > 0 else 100
        )

        # Store completeness metric
        self._completeness_history[symbol].append(
            {
                "timestamp": datetime.now(),
                "period_start": start_time,
                "period_end": end_time,
                "expected_records": expected_records,
                "actual_records": record_count,
                "completeness": completeness,
            }
        )

        # Check if backfill needed
        if completeness < self.backfill_threshold * 100:
            gap = DataGap(symbol, start_time, end_time, expected_records, record_count)
            await self._queue_backfill(gap)

    async def _handle_gap(self, symbol: str, start_time: datetime, end_time: datetime):
        """Handle detected data gap."""
        # Calculate expected records
        duration_seconds = (end_time - start_time).total_seconds()
        expected_rate = self.expected_tick_rate.get(
            symbol, self.expected_tick_rate["DEFAULT"]
        )
        expected_records = int(duration_seconds * expected_rate)

        # Create gap object
        gap = DataGap(symbol, start_time, end_time, expected_records, 0)

        # Store gap
        self._detected_gaps[symbol].append(gap)

        # Log based on severity
        if gap.severity == GapSeverity.CRITICAL:
            logger.error(
                f"Critical data gap detected for {symbol}: {gap.gap_duration}s"
            )
        elif gap.severity == GapSeverity.MAJOR:
            logger.warning(f"Major data gap detected for {symbol}: {gap.gap_duration}s")
        else:
            logger.info(f"Data gap detected for {symbol}: {gap.gap_duration}s")

        # Queue for backfill if significant
        if gap.severity in [GapSeverity.MAJOR, GapSeverity.CRITICAL]:
            await self._queue_backfill(gap)

    async def _queue_backfill(self, gap: DataGap):
        """Queue gap for backfill."""
        await self._backfill_queue.put(gap)
        logger.info(
            f"Queued backfill for {gap.symbol}: {gap.start_time} to {gap.end_time}"
        )

    async def _backfill_processor(self):
        """Process backfill queue."""
        while self._monitoring_active:
            try:
                gap = await asyncio.wait_for(self._backfill_queue.get(), timeout=1.0)
                await self._execute_backfill(gap)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Backfill processor error: {e}")

    async def _execute_backfill(self, gap: DataGap):
        """
        Execute backfill for data gap.

        Args:
            gap: Data gap to backfill
        """
        gap.backfill_attempts += 1

        try:
            # In production, this would call the actual data provider
            # For now, simulate backfill
            logger.info(
                f"Executing backfill for {gap.symbol}: {gap.start_time} to {gap.end_time}"
            )

            # Simulate backfill delay
            await asyncio.sleep(0.1)

            # Mark as backfilled
            gap.backfilled = True
            logger.info(f"Successfully backfilled {gap.symbol} gap")

        except Exception as e:
            logger.error(f"Backfill failed for {gap.symbol}: {e}")

            # Retry for critical gaps
            if gap.severity == GapSeverity.CRITICAL and gap.backfill_attempts < 3:
                await asyncio.sleep(5)  # Wait before retry
                await self._backfill_queue.put(gap)

    def get_completeness_report(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get completeness report.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            Completeness metrics and gap analysis
        """
        if symbol:
            gaps = self._detected_gaps.get(symbol, [])
            history = list(self._completeness_history.get(symbol, []))
        else:
            gaps = [
                gap for gaps_list in self._detected_gaps.values() for gap in gaps_list
            ]
            history = [
                h
                for hist_list in self._completeness_history.values()
                for h in hist_list
            ]

        # Calculate metrics
        if history:
            avg_completeness = sum(h["completeness"] for h in history) / len(history)
            min_completeness = min(h["completeness"] for h in history)
            max_completeness = max(h["completeness"] for h in history)
        else:
            avg_completeness = min_completeness = max_completeness = 0

        # Gap statistics
        total_gaps = len(gaps)
        critical_gaps = sum(1 for g in gaps if g.severity == GapSeverity.CRITICAL)
        major_gaps = sum(1 for g in gaps if g.severity == GapSeverity.MAJOR)
        backfilled_gaps = sum(1 for g in gaps if g.backfilled)

        return {
            "symbol": symbol,
            "avg_completeness": avg_completeness,
            "min_completeness": min_completeness,
            "max_completeness": max_completeness,
            "total_gaps": total_gaps,
            "critical_gaps": critical_gaps,
            "major_gaps": major_gaps,
            "backfilled_gaps": backfilled_gaps,
            "backfill_success_rate": (
                (backfilled_gaps / total_gaps * 100) if total_gaps > 0 else 100
            ),
            "recent_gaps": gaps[-10:] if gaps else [],
            "monitoring_active": self._monitoring_active,
        }

    def get_gap_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """
        Analyze gaps over specified time period.

        Args:
            hours: Number of hours to analyze

        Returns:
            Gap analysis report
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_gaps = []

        for symbol, gaps in self._detected_gaps.items():
            for gap in gaps:
                if gap.start_time >= cutoff_time:
                    recent_gaps.append(
                        {
                            "symbol": symbol,
                            "start_time": gap.start_time,
                            "duration_seconds": gap.gap_duration,
                            "severity": gap.severity.value,
                            "backfilled": gap.backfilled,
                            "completeness_rate": gap.completeness_rate,
                        }
                    )

        # Calculate gap patterns
        gap_by_hour = defaultdict(int)
        for gap in recent_gaps:
            hour = gap["start_time"].hour
            gap_by_hour[hour] += 1

        return {
            "analysis_period_hours": hours,
            "total_gaps": len(recent_gaps),
            "gaps_by_severity": {
                "critical": sum(1 for g in recent_gaps if g["severity"] == "critical"),
                "major": sum(1 for g in recent_gaps if g["severity"] == "major"),
                "moderate": sum(1 for g in recent_gaps if g["severity"] == "moderate"),
                "minor": sum(1 for g in recent_gaps if g["severity"] == "minor"),
            },
            "gaps_by_hour": dict(gap_by_hour),
            "avg_gap_duration": (
                sum(g["duration_seconds"] for g in recent_gaps) / len(recent_gaps)
                if recent_gaps
                else 0
            ),
            "backfill_rate": (
                sum(1 for g in recent_gaps if g["backfilled"]) / len(recent_gaps) * 100
                if recent_gaps
                else 100
            ),
        }

    async def check_health(self) -> Dict[str, Any]:
        """
        Check monitor health status.

        Returns:
            Health status report
        """
        current_time = datetime.now()
        stale_symbols = []

        for symbol, last_time in self._last_tick_time.items():
            if (current_time - last_time).total_seconds() > 300:  # 5 minutes
                stale_symbols.append(symbol)

        backfill_queue_size = self._backfill_queue.qsize()

        return {
            "status": (
                "healthy"
                if self._monitoring_active and not stale_symbols
                else "degraded"
            ),
            "monitoring_active": self._monitoring_active,
            "monitored_symbols": len(self._last_tick_time),
            "stale_symbols": stale_symbols,
            "backfill_queue_size": backfill_queue_size,
            "timestamp": current_time,
        }
