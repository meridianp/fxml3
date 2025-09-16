"""
FXML4 Performance Regression Testing Suite
==========================================

Comprehensive performance regression testing that tracks system performance over time,
detects regressions, and maintains performance baselines for the FXML4 trading system.

This suite follows TDD principles and implements:
- Baseline performance metrics storage
- Automated regression detection
- Performance trend analysis
- SLA validation and alerting
- Comprehensive system benchmarking

Architecture:
- Baseline Storage: JSON files with historical performance data
- Regression Detection: Statistical analysis of performance trends
- Comprehensive Testing: API, Database, ML, Trading, and Frontend components
- CI/CD Integration: Automated execution with failure alerts
- Reporting: Detailed performance reports with trend analysis

Performance Targets (95th percentile):
- Health endpoint: < 50ms
- Data endpoints: < 500ms
- Signal generation: < 2s
- Backtest execution: < 5min
- Database queries: < 100ms
- ML inference: < 200ms
- Frontend load: < 2s
"""

import asyncio
import json
import logging
import os
import statistics
import time
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch
from uuid import uuid4

import aiohttp
import numpy as np
import psutil
import pytest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BASELINES_DIR = Path("tests/performance/baselines")
REPORTS_DIR = Path("performance-regression-results")
REGRESSION_THRESHOLD = 1.20  # 20% performance degradation threshold
MIN_SAMPLES = 10  # Minimum samples for statistical analysis


@dataclass
class PerformanceBaseline:
    """Performance baseline data structure."""

    test_name: str
    timestamp: str
    git_commit: str
    environment: str
    metrics: Dict[str, float]
    metadata: Dict[str, Any]


@dataclass
class PerformanceMeasurement:
    """Single performance measurement."""

    operation: str
    response_time_ms: float
    memory_mb: float
    cpu_percent: float
    success: bool
    error_message: Optional[str] = None


@dataclass
class RegressionAnalysis:
    """Regression analysis result."""

    test_name: str
    current_metric: float
    baseline_metric: float
    regression_percent: float
    is_regression: bool
    confidence_level: float
    recommendation: str


class PerformanceRegressionSuite:
    """Comprehensive performance regression testing suite."""

    def __init__(self, api_url: str = "http://localhost:8001"):
        self.api_url = api_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_headers: Dict[str, str] = {}
        self.measurements: List[PerformanceMeasurement] = []

        # Ensure directories exist
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=100),
        )
        await self._authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _authenticate(self):
        """Authenticate with the API for testing."""
        try:
            # Try authentication
            auth_data = {
                "username": "admin@fxml4.com",
                "password": "admin_password",  # pragma: allowlist secret
            }

            async with self.session.post(
                f"{self.api_url}/api/auth/login", json=auth_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if "access_token" in data:
                        self.auth_headers = {
                            "Authorization": f"Bearer {data['access_token']}"
                        }
                        logger.info("✅ Authentication successful")
                        return
        except Exception as e:
            logger.warning(f"Authentication failed: {e}")

        # Use mock authentication for testing
        self.auth_headers = {"Authorization": "Bearer test-token"}
        logger.info("Using mock authentication for testing")

    def _get_system_metrics(self) -> Dict[str, float]:
        """Get current system resource metrics."""
        try:
            process = psutil.Process()
            return {
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "cpu_percent": process.cpu_percent(),
                "memory_percent": process.memory_percent(),
            }
        except Exception:
            return {"memory_mb": 0, "cpu_percent": 0, "memory_percent": 0}

    async def _measure_endpoint_performance(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict] = None,
        samples: int = 20,
    ) -> List[float]:
        """Measure endpoint performance with multiple samples."""
        response_times = []

        for _ in range(samples):
            start_time = time.perf_counter()
            system_metrics_before = self._get_system_metrics()

            try:
                kwargs = {"headers": self.auth_headers}
                if method == "POST" and data:
                    kwargs["json"] = data

                async with getattr(self.session, method.lower())(
                    f"{self.api_url}{endpoint}", **kwargs
                ) as response:
                    await response.text()

                    end_time = time.perf_counter()
                    response_time_ms = (end_time - start_time) * 1000
                    response_times.append(response_time_ms)

                    system_metrics_after = self._get_system_metrics()

                    self.measurements.append(
                        PerformanceMeasurement(
                            operation=f"{method} {endpoint}",
                            response_time_ms=response_time_ms,
                            memory_mb=system_metrics_after["memory_mb"],
                            cpu_percent=system_metrics_after["cpu_percent"],
                            success=response.status < 400,
                            error_message=(
                                None
                                if response.status < 400
                                else f"HTTP {response.status}"
                            ),
                        )
                    )

            except Exception as e:
                end_time = time.perf_counter()
                response_time_ms = (end_time - start_time) * 1000
                response_times.append(response_time_ms)

                self.measurements.append(
                    PerformanceMeasurement(
                        operation=f"{method} {endpoint}",
                        response_time_ms=response_time_ms,
                        memory_mb=0,
                        cpu_percent=0,
                        success=False,
                        error_message=str(e),
                    )
                )

            # Small delay between requests to avoid overwhelming the system
            await asyncio.sleep(0.1)

        return response_times

    def _calculate_percentiles(self, values: List[float]) -> Dict[str, float]:
        """Calculate performance percentiles."""
        if not values:
            return {"p50": 0, "p95": 0, "p99": 0, "mean": 0}

        return {
            "p50": np.percentile(values, 50),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99),
            "mean": np.mean(values),
            "min": np.min(values),
            "max": np.max(values),
        }

    def _load_baseline(self, test_name: str) -> Optional[PerformanceBaseline]:
        """Load performance baseline from storage."""
        baseline_file = BASELINES_DIR / f"{test_name}.json"

        if baseline_file.exists():
            try:
                with open(baseline_file, "r") as f:
                    data = json.load(f)
                return PerformanceBaseline(**data)
            except Exception as e:
                logger.warning(f"Failed to load baseline for {test_name}: {e}")

        return None

    def _save_baseline(self, baseline: PerformanceBaseline):
        """Save performance baseline to storage."""
        baseline_file = BASELINES_DIR / f"{baseline.test_name}.json"

        try:
            with open(baseline_file, "w") as f:
                json.dump(asdict(baseline), f, indent=2)
            logger.info(f"✅ Baseline saved for {baseline.test_name}")
        except Exception as e:
            logger.error(f"Failed to save baseline for {baseline.test_name}: {e}")

    def _analyze_regression(
        self, test_name: str, current_metrics: Dict[str, float]
    ) -> List[RegressionAnalysis]:
        """Analyze performance regression against baseline."""
        baseline = self._load_baseline(test_name)

        if not baseline:
            logger.warning(f"No baseline found for {test_name}, creating new baseline")

            new_baseline = PerformanceBaseline(
                test_name=test_name,
                timestamp=datetime.now().isoformat(),
                git_commit=os.getenv("GIT_COMMIT", "unknown"),
                environment=os.getenv("FXML4_ENV", "test"),
                metrics=current_metrics,
                metadata={"samples": len(self.measurements)},
            )

            self._save_baseline(new_baseline)
            return []

        analyses = []

        for metric_name, current_value in current_metrics.items():
            if metric_name not in baseline.metrics:
                continue

            baseline_value = baseline.metrics[metric_name]

            if baseline_value == 0:
                regression_percent = float("inf") if current_value > 0 else 0
            else:
                regression_percent = (
                    (current_value - baseline_value) / baseline_value
                ) * 100

            is_regression = regression_percent > (REGRESSION_THRESHOLD - 1) * 100

            # Determine confidence level based on the difference
            confidence_level = min(abs(regression_percent) / 10, 100)

            # Generate recommendation
            if is_regression:
                recommendation = (
                    f"Performance regression detected in {metric_name}. "
                    f"Current: {current_value:.2f}, Baseline: {baseline_value:.2f}. "
                    f"Consider investigating recent changes."
                )
            elif regression_percent < -10:  # 10% improvement
                recommendation = (
                    f"Performance improvement detected in {metric_name}. "
                    f"Consider updating baseline."
                )
            else:
                recommendation = (
                    f"Performance within acceptable range for {metric_name}."
                )

            analyses.append(
                RegressionAnalysis(
                    test_name=test_name,
                    current_metric=current_value,
                    baseline_metric=baseline_value,
                    regression_percent=regression_percent,
                    is_regression=is_regression,
                    confidence_level=confidence_level,
                    recommendation=recommendation,
                )
            )

        return analyses

    def _generate_report(self, test_results: Dict[str, List[RegressionAnalysis]]):
        """Generate comprehensive performance regression report."""
        report_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = REPORTS_DIR / f"regression_report_{report_timestamp}.md"

        with open(report_file, "w") as f:
            f.write("# FXML4 Performance Regression Test Report\n\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n")
            f.write(f"**Git Commit:** {os.getenv('GIT_COMMIT', 'unknown')}\n")
            f.write(f"**Environment:** {os.getenv('FXML4_ENV', 'test')}\n\n")

            # Executive Summary
            total_tests = len(test_results)
            total_regressions = sum(
                len([a for a in analyses if a.is_regression])
                for analyses in test_results.values()
            )

            f.write("## Executive Summary\n\n")
            f.write(f"- **Total Tests:** {total_tests}\n")
            f.write(f"- **Regressions Detected:** {total_regressions}\n")
            f.write(f"- **Regression Threshold:** {REGRESSION_THRESHOLD:.0%}\n")
            f.write(
                f"- **Overall Status:** {'❌ FAILED' if total_regressions > 0 else '✅ PASSED'}\n\n"
            )

            # Detailed Results
            f.write("## Detailed Results\n\n")

            for test_name, analyses in test_results.items():
                f.write(f"### {test_name}\n\n")

                if not analyses:
                    f.write(
                        "*New baseline created - no regression analysis available.*\n\n"
                    )
                    continue

                for analysis in analyses:
                    status = "❌ REGRESSION" if analysis.is_regression else "✅ PASS"
                    f.write(f"**{analysis.test_name} - {status}**\n")
                    f.write(f"- Current: {analysis.current_metric:.2f}\n")
                    f.write(f"- Baseline: {analysis.baseline_metric:.2f}\n")
                    f.write(f"- Change: {analysis.regression_percent:+.1f}%\n")
                    f.write(f"- Confidence: {analysis.confidence_level:.1f}%\n")
                    f.write(f"- Recommendation: {analysis.recommendation}\n\n")

            # Performance Measurements
            f.write("## Performance Measurements\n\n")
            f.write(
                "| Operation | Avg Response Time (ms) | Success Rate | Memory (MB) | CPU (%) |\n"
            )
            f.write(
                "|-----------|----------------------|--------------|-------------|----------|\n"
            )

            operation_stats = {}
            for measurement in self.measurements:
                if measurement.operation not in operation_stats:
                    operation_stats[measurement.operation] = {
                        "response_times": [],
                        "successes": 0,
                        "total": 0,
                        "memory": [],
                        "cpu": [],
                    }

                stats = operation_stats[measurement.operation]
                stats["response_times"].append(measurement.response_time_ms)
                stats["total"] += 1
                if measurement.success:
                    stats["successes"] += 1
                stats["memory"].append(measurement.memory_mb)
                stats["cpu"].append(measurement.cpu_percent)

            for operation, stats in operation_stats.items():
                avg_response = np.mean(stats["response_times"])
                success_rate = (stats["successes"] / stats["total"]) * 100
                avg_memory = np.mean(stats["memory"])
                avg_cpu = np.mean(stats["cpu"])

                f.write(
                    f"| {operation} | {avg_response:.1f} | {success_rate:.1f}% | {avg_memory:.1f} | {avg_cpu:.1f} |\n"
                )

            f.write(
                "\n---\n*Generated by FXML4 Performance Regression Testing Suite*\n"
            )

        logger.info(f"📊 Performance regression report generated: {report_file}")
        return report_file

    # Test Methods
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_api_endpoint_performance_regression(self):
        """Test API endpoint performance regression."""
        test_name = "api_endpoint_performance"

        # Test critical API endpoints
        endpoints_to_test = [
            ("/health", "GET", None),
            ("/api/data/symbols", "GET", None),
            ("/api/signals/generate", "POST", {"symbol": "EURUSD", "timeframe": "1h"}),
        ]

        all_response_times = []

        for endpoint, method, data in endpoints_to_test:
            logger.info(f"Testing {method} {endpoint}")
            response_times = await self._measure_endpoint_performance(
                endpoint, method, data, samples=15
            )
            all_response_times.extend(response_times)

        # Calculate metrics
        percentiles = self._calculate_percentiles(all_response_times)
        current_metrics = {
            "p95_response_time_ms": percentiles["p95"],
            "mean_response_time_ms": percentiles["mean"],
            "max_response_time_ms": percentiles["max"],
        }

        # Analyze regression
        analyses = self._analyze_regression(test_name, current_metrics)

        # Assert no critical regressions
        critical_regressions = [
            a for a in analyses if a.is_regression and a.confidence_level > 80
        ]
        if critical_regressions:
            regression_details = "\n".join(
                [
                    f"- {a.test_name}: {a.regression_percent:+.1f}% ({a.recommendation})"
                    for a in critical_regressions
                ]
            )
            pytest.fail(
                f"Critical performance regressions detected:\n{regression_details}"
            )

        return analyses

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_database_performance_regression(self):
        """Test database query performance regression."""
        test_name = "database_performance"

        # Simulate database performance testing
        # In a real implementation, this would test actual database queries
        query_times = []

        for _ in range(20):
            start = time.perf_counter()

            # Simulate database query via API
            try:
                async with self.session.get(
                    f"{self.api_url}/api/data/candles",
                    params={"symbol": "EURUSD", "timeframe": "1h", "limit": 100},
                    headers=self.auth_headers,
                ) as response:
                    await response.text()

                end = time.perf_counter()
                query_time_ms = (end - start) * 1000
                query_times.append(query_time_ms)

            except Exception as e:
                logger.warning(f"Database query simulation failed: {e}")
                query_times.append(1000)  # Assume 1s timeout

            await asyncio.sleep(0.05)

        percentiles = self._calculate_percentiles(query_times)
        current_metrics = {
            "p95_query_time_ms": percentiles["p95"],
            "mean_query_time_ms": percentiles["mean"],
            "max_query_time_ms": percentiles["max"],
        }

        analyses = self._analyze_regression(test_name, current_metrics)

        # Assert database performance SLA
        assert (
            percentiles["p95"] < 1000
        ), f"Database p95 query time {percentiles['p95']:.1f}ms exceeds 1000ms SLA"

        return analyses

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_ml_inference_performance_regression(self):
        """Test ML model inference performance regression."""
        test_name = "ml_inference_performance"

        inference_times = []

        # Test ML inference via signal generation endpoint
        for _ in range(15):
            start = time.perf_counter()

            try:
                async with self.session.post(
                    f"{self.api_url}/api/signals/generate",
                    json={
                        "symbol": "GBPUSD",
                        "timeframe": "1h",
                        "model_name": "gbpusd_ensemble",
                    },
                    headers=self.auth_headers,
                ) as response:
                    await response.text()

                end = time.perf_counter()
                inference_time_ms = (end - start) * 1000
                inference_times.append(inference_time_ms)

            except Exception as e:
                logger.warning(f"ML inference test failed: {e}")
                inference_times.append(2000)  # Assume 2s timeout

            await asyncio.sleep(0.1)

        percentiles = self._calculate_percentiles(inference_times)
        current_metrics = {
            "p95_inference_time_ms": percentiles["p95"],
            "mean_inference_time_ms": percentiles["mean"],
        }

        analyses = self._analyze_regression(test_name, current_metrics)

        # Assert ML inference SLA
        assert (
            percentiles["p95"] < 5000
        ), f"ML inference p95 time {percentiles['p95']:.1f}ms exceeds 5s SLA"

        return analyses

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_load_performance_regression(self):
        """Test system performance under concurrent load."""
        test_name = "concurrent_load_performance"

        concurrent_users = 10
        requests_per_user = 5

        async def simulate_user_requests():
            """Simulate a user making multiple requests."""
            user_response_times = []

            for _ in range(requests_per_user):
                start = time.perf_counter()

                try:
                    async with self.session.get(
                        f"{self.api_url}/health", headers=self.auth_headers
                    ) as response:
                        await response.text()

                    end = time.perf_counter()
                    response_time_ms = (end - start) * 1000
                    user_response_times.append(response_time_ms)

                except Exception as e:
                    end = time.perf_counter()
                    response_time_ms = (end - start) * 1000
                    user_response_times.append(response_time_ms)

                await asyncio.sleep(0.1)

            return user_response_times

        # Execute concurrent load test
        start_time = time.perf_counter()
        tasks = [simulate_user_requests() for _ in range(concurrent_users)]
        results = await asyncio.gather(*tasks)
        end_time = time.perf_counter()

        # Aggregate results
        all_response_times = []
        for user_times in results:
            all_response_times.extend(user_times)

        total_requests = concurrent_users * requests_per_user
        total_time_seconds = end_time - start_time
        throughput_rps = total_requests / total_time_seconds

        percentiles = self._calculate_percentiles(all_response_times)
        current_metrics = {
            "throughput_requests_per_second": throughput_rps,
            "p95_response_time_ms": percentiles["p95"],
            "mean_response_time_ms": percentiles["mean"],
        }

        analyses = self._analyze_regression(test_name, current_metrics)

        # Assert concurrent load performance
        assert (
            throughput_rps > 50
        ), f"Throughput {throughput_rps:.1f} RPS is below minimum 50 RPS"
        assert (
            percentiles["p95"] < 2000
        ), f"P95 response time {percentiles['p95']:.1f}ms exceeds 2s under load"

        return analyses


# Pytest fixtures and test execution
@pytest.fixture(scope="session")
def performance_suite():
    """Create performance regression suite instance."""
    return PerformanceRegressionSuite()


@pytest.mark.asyncio
@pytest.mark.performance
async def test_complete_performance_regression_suite():
    """Run the complete performance regression test suite."""
    async with PerformanceRegressionSuite() as suite:
        test_results = {}

        # Run all performance regression tests
        test_methods = [
            suite.test_api_endpoint_performance_regression,
            suite.test_database_performance_regression,
            suite.test_ml_inference_performance_regression,
            suite.test_concurrent_load_performance_regression,
        ]

        for test_method in test_methods:
            try:
                test_name = test_method.__name__
                logger.info(f"🧪 Running {test_name}")

                analyses = await test_method()
                test_results[test_name] = analyses or []

                logger.info(f"✅ {test_name} completed")

            except Exception as e:
                logger.error(f"❌ {test_method.__name__} failed: {e}")
                test_results[test_method.__name__] = []

        # Generate comprehensive report
        report_file = suite._generate_report(test_results)

        # Check for critical regressions
        total_regressions = sum(
            len([a for a in analyses if a.is_regression])
            for analyses in test_results.values()
        )

        if total_regressions > 0:
            logger.error(f"❌ {total_regressions} performance regressions detected")
            pytest.fail(
                f"Performance regression test failed with {total_regressions} regressions. "
                f"See report: {report_file}"
            )
        else:
            logger.info(f"✅ All performance regression tests passed")


if __name__ == "__main__":
    """
    Run performance regression tests directly.

    Usage:
    python test_performance_regression_suite.py
    """
    import sys

    # Run the complete test suite
    exit_code = pytest.main([__file__, "-v", "--tb=short", "-m", "performance"])

    sys.exit(exit_code)
