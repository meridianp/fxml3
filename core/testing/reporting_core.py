"""Comprehensive test result aggregation and reporting."""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Individual test result."""

    name: str
    status: str  # passed, failed, skipped
    duration: float
    category: str
    memory_usage: float = 0.0
    error_message: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0


@dataclass
class CategoryStats:
    """Statistics for a test category."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration: float = 0.0
    memory_usage: float = 0.0


@dataclass
class ComprehensiveReport:
    """Complete test execution report."""

    total_tests: int
    passed: int
    failed: int
    skipped: int
    total_duration: float
    categories: Dict[str, CategoryStats]
    performance_metrics: Dict[str, Any]
    resource_usage: Dict[str, Any]
    slow_tests: List[str]
    failed_tests: List[Dict[str, Any]]
    summary: str


class ComprehensiveTestReporter:
    """Comprehensive test result reporter."""

    def __init__(self):
        self.test_results: List[TestResult] = []
        self.active_tests: Dict[str, float] = {}
        self.start_time: float = 0.0
        self.collecting = False

    def start_collection(self):
        """Start collecting test results."""
        self.collecting = True
        self.start_time = time.perf_counter()
        self.test_results.clear()
        self.active_tests.clear()
        logger.info("Started test result collection")

    def record_test_start(self, test_name: str, category: str = "unit"):
        """Record test start."""
        if not self.collecting:
            return

        start_time = time.perf_counter()
        self.active_tests[test_name] = start_time

        logger.debug(f"Test started: {test_name} (category: {category})")

    def record_test_end(
        self,
        test_name: str,
        status: str,
        memory_usage: float = 0.0,
        error: Optional[str] = None,
        category: str = "unit",
    ):
        """Record test completion."""
        if not self.collecting:
            return

        end_time = time.perf_counter()
        start_time = self.active_tests.pop(test_name, end_time)
        duration = end_time - start_time

        result = TestResult(
            name=test_name,
            status=status,
            duration=duration,
            category=category,
            memory_usage=memory_usage,
            error_message=error,
            start_time=start_time,
            end_time=end_time,
        )

        self.test_results.append(result)
        logger.debug(f"Test completed: {test_name} ({status}) in {duration:.3f}s")

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        if not self.test_results:
            return {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "summary": "No tests recorded",
            }

        # Calculate overall stats
        total_tests = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.status == "passed")
        failed = sum(1 for r in self.test_results if r.status == "failed")
        skipped = sum(1 for r in self.test_results if r.status == "skipped")
        total_duration = sum(r.duration for r in self.test_results)

        # Calculate category stats
        categories = defaultdict(lambda: CategoryStats())
        for result in self.test_results:
            cat_stats = categories[result.category]
            cat_stats.total += 1
            cat_stats.duration += result.duration
            cat_stats.memory_usage += result.memory_usage

            if result.status == "passed":
                cat_stats.passed += 1
            elif result.status == "failed":
                cat_stats.failed += 1
            elif result.status == "skipped":
                cat_stats.skipped += 1

        # Performance metrics
        durations = [r.duration for r in self.test_results]
        memory_usage = [r.memory_usage for r in self.test_results if r.memory_usage > 0]

        performance_metrics = {
            "average_test_duration": (
                sum(durations) / len(durations) if durations else 0
            ),
            "slowest_test_duration": max(durations) if durations else 0,
            "fastest_test_duration": min(durations) if durations else 0,
            "total_memory_usage": sum(memory_usage),
            "average_memory_usage": (
                sum(memory_usage) / len(memory_usage) if memory_usage else 0
            ),
            "tests_per_second": (
                total_tests / total_duration if total_duration > 0 else 0
            ),
        }

        # Resource usage
        resource_usage = {
            "cpu_time": total_duration,
            "wall_time": time.perf_counter() - self.start_time,
            "memory_peak": max(memory_usage) if memory_usage else 0,
            "parallel_efficiency": (
                (total_duration / (time.perf_counter() - self.start_time))
                if (time.perf_counter() - self.start_time) > 0
                else 0
            ),
        }

        # Identify slow tests (top 10% by duration)
        sorted_by_duration = sorted(
            self.test_results, key=lambda x: x.duration, reverse=True
        )
        slow_test_count = max(1, len(sorted_by_duration) // 10)
        slow_tests = [r.name for r in sorted_by_duration[:slow_test_count]]

        # Failed test details
        failed_tests = [
            {
                "name": r.name,
                "category": r.category,
                "duration": r.duration,
                "error": r.error_message,
            }
            for r in self.test_results
            if r.status == "failed"
        ]

        # Generate summary
        pass_rate = (passed / total_tests) * 100 if total_tests > 0 else 0
        summary = f"{total_tests} tests, {passed} passed, {failed} failed, {skipped} skipped ({pass_rate:.1f}% pass rate)"

        return {
            "total_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total_duration": total_duration,
            "categories": dict(categories),
            "performance_metrics": performance_metrics,
            "resource_usage": resource_usage,
            "slow_tests": slow_tests,
            "failed_tests": failed_tests,
            "summary": summary,
            "pass_rate": pass_rate,
            "generated_at": time.time(),
        }

    def get_category_breakdown(self) -> Dict[str, CategoryStats]:
        """Get detailed breakdown by test category."""
        categories = defaultdict(lambda: CategoryStats())

        for result in self.test_results:
            cat_stats = categories[result.category]
            cat_stats.total += 1
            cat_stats.duration += result.duration
            cat_stats.memory_usage += result.memory_usage

            if result.status == "passed":
                cat_stats.passed += 1
            elif result.status == "failed":
                cat_stats.failed += 1
            elif result.status == "skipped":
                cat_stats.skipped += 1

        return dict(categories)

    def export_detailed_report(self, format_type: str = "json") -> str:
        """Export detailed report in specified format."""
        report = self.generate_report()

        if format_type == "json":
            import json

            return json.dumps(report, indent=2, default=str)
        elif format_type == "yaml":
            try:
                import yaml

                return yaml.dump(report, default_flow_style=False)
            except ImportError:
                logger.warning("PyYAML not available, falling back to JSON")
                import json

                return json.dumps(report, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def get_performance_insights(self) -> List[str]:
        """Get performance insights and recommendations."""
        if not self.test_results:
            return ["No test results available for analysis"]

        insights = []
        durations = [r.duration for r in self.test_results]
        avg_duration = sum(durations) / len(durations)

        # Identify performance issues
        slow_tests = [r for r in self.test_results if r.duration > avg_duration * 3]
        if slow_tests:
            insights.append(
                f"Found {len(slow_tests)} tests that are significantly slower than average"
            )

        memory_usage = [r.memory_usage for r in self.test_results if r.memory_usage > 0]
        if memory_usage:
            high_memory_tests = [
                r for r in self.test_results if r.memory_usage > 50.0
            ]  # 50MB
            if high_memory_tests:
                insights.append(
                    f"Found {len(high_memory_tests)} tests with high memory usage"
                )

        # Category analysis
        categories = self.get_category_breakdown()
        for cat_name, stats in categories.items():
            if stats.failed > stats.passed:
                insights.append(
                    f"Category '{cat_name}' has more failures than passes - review needed"
                )

        if not insights:
            insights.append(
                "Test performance looks good - no significant issues detected"
            )

        return insights
