#!/usr/bin/env python3
"""
FXML4 Comprehensive API Performance Testing Framework

Tests API endpoint performance against Phase 11 SLA requirements:
- /health: < 50ms (95th percentile)
- /data: < 500ms (95th percentile)
- /signals: < 2s (95th percentile)
- /backtest: < 5min (95th percentile)

Provides detailed performance analysis with load testing capabilities.

Usage:
    python scripts/test_api_performance_comprehensive.py [--load-level light|normal|stress]
"""

import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# HTTP testing
import aiohttp
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for API endpoint testing"""

    endpoint: str
    method: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate: float
    response_times: List[float]
    mean_response_time: float
    median_response_time: float
    p95_response_time: float
    p99_response_time: float
    min_response_time: float
    max_response_time: float
    requests_per_second: float
    sla_target: float
    sla_passed: bool
    test_duration: float
    timestamp: str


@dataclass
class LoadTestConfig:
    """Load testing configuration"""

    concurrent_requests: int
    total_requests: int
    ramp_up_time: int  # seconds
    description: str


class APIPerformanceTester:
    """
    Comprehensive API performance testing framework with SLA validation
    """

    def __init__(
        self, base_url: str = "http://localhost:8001", auth_token: Optional[str] = None
    ):
        """
        Initialize performance tester

        Args:
            base_url: API base URL
            auth_token: Optional authentication token
        """
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.session = None
        self.results: List[PerformanceMetrics] = []

        # SLA targets in seconds
        self.sla_targets = {
            "/health": 0.050,  # 50ms
            "/data": 0.500,  # 500ms
            "/signals": 2.000,  # 2s
            "/backtest": 300.000,  # 5min
        }

        # Load test configurations
        self.load_configs = {
            "light": LoadTestConfig(
                concurrent_requests=5,
                total_requests=50,
                ramp_up_time=10,
                description="Light load testing (5 concurrent, 50 total)",
            ),
            "normal": LoadTestConfig(
                concurrent_requests=20,
                total_requests=200,
                ramp_up_time=30,
                description="Normal load testing (20 concurrent, 200 total)",
            ),
            "stress": LoadTestConfig(
                concurrent_requests=100,
                total_requests=1000,
                ramp_up_time=60,
                description="Stress load testing (100 concurrent, 1000 total)",
            ),
        }

        logger.info(f"Initialized API Performance Tester for {base_url}")

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=600),  # 10min timeout for backtest
            headers=self._get_headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FXML4-Performance-Tester/1.0",
        }

        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        return headers

    async def test_health_endpoint(
        self, load_config: LoadTestConfig
    ) -> PerformanceMetrics:
        """
        Test /health endpoint performance

        Args:
            load_config: Load testing configuration

        Returns:
            Performance metrics
        """
        logger.info(f"Testing /health endpoint - {load_config.description}")

        endpoint = "/health"
        url = f"{self.base_url}{endpoint}"

        start_time = time.perf_counter()
        response_times = []
        successful_requests = 0
        failed_requests = 0

        # Execute load test
        async def single_request():
            nonlocal successful_requests, failed_requests
            try:
                req_start = time.perf_counter()
                async with self.session.get(url) as response:
                    await response.text()  # Consume response
                    req_end = time.perf_counter()

                    response_time = req_end - req_start
                    response_times.append(response_time)

                    if response.status == 200:
                        successful_requests += 1
                    else:
                        failed_requests += 1
                        logger.warning(
                            f"Health endpoint returned status {response.status}"
                        )

            except Exception as e:
                failed_requests += 1
                logger.error(f"Health endpoint request failed: {e}")

        # Run concurrent requests
        await self._run_load_test(single_request, load_config)

        end_time = time.perf_counter()
        test_duration = end_time - start_time

        return self._calculate_metrics(
            endpoint=endpoint,
            method="GET",
            response_times=response_times,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            test_duration=test_duration,
            sla_target=self.sla_targets[endpoint],
        )

    async def test_data_endpoint(
        self, load_config: LoadTestConfig
    ) -> PerformanceMetrics:
        """
        Test /data endpoint performance with realistic market data requests

        Args:
            load_config: Load testing configuration

        Returns:
            Performance metrics
        """
        logger.info(f"Testing /data endpoint - {load_config.description}")

        endpoint = "/data"
        url = f"{self.base_url}{endpoint}"

        # Realistic data request payload
        payload = {
            "symbol": "GBPUSD",
            "timeframe": "1h",
            "start_date": (datetime.utcnow() - timedelta(days=7)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "limit": 168,  # 1 week of hourly data
        }

        start_time = time.perf_counter()
        response_times = []
        successful_requests = 0
        failed_requests = 0

        async def single_request():
            nonlocal successful_requests, failed_requests
            try:
                req_start = time.perf_counter()
                async with self.session.post(url, json=payload) as response:
                    result = await response.json()
                    req_end = time.perf_counter()

                    response_time = req_end - req_start
                    response_times.append(response_time)

                    if response.status == 200 and "data" in result:
                        successful_requests += 1
                    else:
                        failed_requests += 1
                        logger.warning(
                            f"Data endpoint returned status {response.status}: {result}"
                        )

            except Exception as e:
                failed_requests += 1
                logger.error(f"Data endpoint request failed: {e}")

        # Run load test
        await self._run_load_test(single_request, load_config)

        end_time = time.perf_counter()
        test_duration = end_time - start_time

        return self._calculate_metrics(
            endpoint=endpoint,
            method="POST",
            response_times=response_times,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            test_duration=test_duration,
            sla_target=self.sla_targets[endpoint],
        )

    async def test_signals_endpoint(
        self, load_config: LoadTestConfig
    ) -> PerformanceMetrics:
        """
        Test /signals endpoint performance with realistic signal generation requests

        Args:
            load_config: Load testing configuration

        Returns:
            Performance metrics
        """
        logger.info(f"Testing /signals endpoint - {load_config.description}")

        endpoint = "/signals"
        url = f"{self.base_url}{endpoint}"

        # Realistic signal request payload
        payload = {"symbol": "GBPUSD", "timeframe": "1h", "strategy": "ml_strategy"}

        start_time = time.perf_counter()
        response_times = []
        successful_requests = 0
        failed_requests = 0

        async def single_request():
            nonlocal successful_requests, failed_requests
            try:
                req_start = time.perf_counter()
                async with self.session.post(url, json=payload) as response:
                    result = await response.json()
                    req_end = time.perf_counter()

                    response_time = req_end - req_start
                    response_times.append(response_time)

                    if response.status == 200 and "signal" in result:
                        successful_requests += 1
                    else:
                        failed_requests += 1
                        logger.warning(
                            f"Signals endpoint returned status {response.status}: {result}"
                        )

            except Exception as e:
                failed_requests += 1
                logger.error(f"Signals endpoint request failed: {e}")

        # Run load test with reduced concurrency for signals (more CPU intensive)
        signals_config = LoadTestConfig(
            concurrent_requests=min(load_config.concurrent_requests, 10),
            total_requests=min(load_config.total_requests, 50),
            ramp_up_time=load_config.ramp_up_time,
            description=f"Signals {load_config.description} (reduced for ML processing)",
        )

        await self._run_load_test(single_request, signals_config)

        end_time = time.perf_counter()
        test_duration = end_time - start_time

        return self._calculate_metrics(
            endpoint=endpoint,
            method="POST",
            response_times=response_times,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            test_duration=test_duration,
            sla_target=self.sla_targets[endpoint],
        )

    async def test_backtest_endpoint(
        self, load_config: LoadTestConfig
    ) -> PerformanceMetrics:
        """
        Test /backtest endpoint performance with realistic backtesting requests

        Args:
            load_config: Load testing configuration

        Returns:
            Performance metrics
        """
        logger.info(f"Testing /backtest endpoint - {load_config.description}")

        endpoint = "/backtest"
        url = f"{self.base_url}{endpoint}"

        # Realistic backtest request payload
        payload = {
            "symbol": "GBPUSD",
            "timeframe": "1h",
            "start_date": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "strategy": "integrated_strategy",
            "initial_capital": 10000,
        }

        start_time = time.perf_counter()
        response_times = []
        successful_requests = 0
        failed_requests = 0

        async def single_request():
            nonlocal successful_requests, failed_requests
            try:
                req_start = time.perf_counter()
                async with self.session.post(url, json=payload) as response:
                    result = await response.json()
                    req_end = time.perf_counter()

                    response_time = req_end - req_start
                    response_times.append(response_time)

                    if response.status == 200 and "results" in result:
                        successful_requests += 1
                    else:
                        failed_requests += 1
                        logger.warning(
                            f"Backtest endpoint returned status {response.status}: {result}"
                        )

            except Exception as e:
                failed_requests += 1
                logger.error(f"Backtest endpoint request failed: {e}")

        # Run load test with very limited concurrency for backtest (resource intensive)
        backtest_config = LoadTestConfig(
            concurrent_requests=min(load_config.concurrent_requests // 10, 3),
            total_requests=min(load_config.total_requests // 10, 10),
            ramp_up_time=load_config.ramp_up_time,
            description=f"Backtest {load_config.description} (heavily reduced for resource intensity)",
        )

        await self._run_load_test(single_request, backtest_config)

        end_time = time.perf_counter()
        test_duration = end_time - start_time

        return self._calculate_metrics(
            endpoint=endpoint,
            method="POST",
            response_times=response_times,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            test_duration=test_duration,
            sla_target=self.sla_targets[endpoint],
        )

    async def _run_load_test(self, request_func, load_config: LoadTestConfig):
        """
        Execute load test with specified concurrency and ramp-up

        Args:
            request_func: Async function to execute single request
            load_config: Load testing configuration
        """
        semaphore = asyncio.Semaphore(load_config.concurrent_requests)

        async def throttled_request():
            async with semaphore:
                await request_func()

        # Create all tasks
        tasks = [throttled_request() for _ in range(load_config.total_requests)]

        # Execute with progress logging
        completed = 0
        batch_size = max(load_config.concurrent_requests, 10)

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            await asyncio.gather(*batch, return_exceptions=True)
            completed += len(batch)

            if completed % (load_config.total_requests // 10 or 1) == 0:
                progress = (completed / load_config.total_requests) * 100
                logger.info(
                    f"Load test progress: {progress:.1f}% ({completed}/{load_config.total_requests})"
                )

            # Brief pause between batches for ramp-up
            if i < len(tasks) - batch_size:
                await asyncio.sleep(
                    load_config.ramp_up_time / (len(tasks) / batch_size)
                )

    def _calculate_metrics(
        self,
        endpoint: str,
        method: str,
        response_times: List[float],
        successful_requests: int,
        failed_requests: int,
        test_duration: float,
        sla_target: float,
    ) -> PerformanceMetrics:
        """
        Calculate performance metrics from test results

        Args:
            endpoint: API endpoint path
            method: HTTP method
            response_times: List of response times in seconds
            successful_requests: Number of successful requests
            failed_requests: Number of failed requests
            test_duration: Total test duration in seconds
            sla_target: SLA target in seconds

        Returns:
            Performance metrics
        """
        total_requests = successful_requests + failed_requests
        error_rate = (
            (failed_requests / total_requests * 100) if total_requests > 0 else 0
        )

        if response_times:
            mean_time = statistics.mean(response_times)
            median_time = statistics.median(response_times)
            p95_time = self._percentile(response_times, 95)
            p99_time = self._percentile(response_times, 99)
            min_time = min(response_times)
            max_time = max(response_times)
            sla_passed = p95_time <= sla_target
        else:
            mean_time = median_time = p95_time = p99_time = min_time = max_time = 0
            sla_passed = False

        rps = total_requests / test_duration if test_duration > 0 else 0

        return PerformanceMetrics(
            endpoint=endpoint,
            method=method,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            error_rate=error_rate,
            response_times=response_times[:100],  # Limit stored times for memory
            mean_response_time=mean_time,
            median_response_time=median_time,
            p95_response_time=p95_time,
            p99_response_time=p99_time,
            min_response_time=min_time,
            max_response_time=max_time,
            requests_per_second=rps,
            sla_target=sla_target,
            sla_passed=sla_passed,
            test_duration=test_duration,
            timestamp=datetime.utcnow().isoformat(),
        )

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile from data list"""
        if not data:
            return 0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * percentile / 100
        f = int(k)
        c = k - f
        if f == len(sorted_data) - 1:
            return sorted_data[f]
        return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])

    async def run_comprehensive_performance_test(
        self, load_level: str = "normal"
    ) -> List[PerformanceMetrics]:
        """
        Run comprehensive performance testing across all endpoints

        Args:
            load_level: Load testing level (light, normal, stress)

        Returns:
            List of performance metrics for all endpoints
        """
        if load_level not in self.load_configs:
            raise ValueError(
                f"Invalid load level: {load_level}. Options: {list(self.load_configs.keys())}"
            )

        load_config = self.load_configs[load_level]
        logger.info(
            f"Starting comprehensive performance test - {load_config.description}"
        )

        self.results = []

        # Test each endpoint
        test_methods = [
            self.test_health_endpoint,
            self.test_data_endpoint,
            self.test_signals_endpoint,
            self.test_backtest_endpoint,
        ]

        for test_method in test_methods:
            try:
                result = await test_method(load_config)
                self.results.append(result)

                # Log immediate results
                status = "✅ PASS" if result.sla_passed else "❌ FAIL"
                logger.info(
                    f"{status} - {result.endpoint} - P95: {result.p95_response_time:.3f}s (Target: {result.sla_target:.3f}s)"
                )

            except Exception as e:
                logger.error(f"Failed to test {test_method.__name__}: {e}")

        return self.results

    def generate_performance_report(
        self, output_file: str = "api_performance_report.json"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive performance report

        Args:
            output_file: Output file path for JSON report

        Returns:
            Performance report dictionary
        """
        if not self.results:
            raise ValueError("No performance results available. Run tests first.")

        # Calculate overall statistics
        total_requests = sum(r.total_requests for r in self.results)
        successful_requests = sum(r.successful_requests for r in self.results)
        total_test_time = sum(r.test_duration for r in self.results)

        passed_slas = sum(1 for r in self.results if r.sla_passed)
        total_slas = len(self.results)
        sla_pass_rate = (passed_slas / total_slas * 100) if total_slas > 0 else 0

        report = {
            "test_summary": {
                "timestamp": datetime.utcnow().isoformat(),
                "total_endpoints_tested": total_slas,
                "sla_pass_rate": sla_pass_rate,
                "overall_result": "PASS" if sla_pass_rate == 100 else "FAIL",
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "overall_success_rate": (
                    (successful_requests / total_requests * 100)
                    if total_requests > 0
                    else 0
                ),
                "total_test_duration": total_test_time,
            },
            "endpoint_results": [asdict(result) for result in self.results],
            "sla_targets": self.sla_targets,
            "recommendations": self._generate_recommendations(),
        }

        # Save JSON report
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Performance report saved to: {output_file}")
        return report

    def _generate_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations based on results"""
        recommendations = []

        for result in self.results:
            if not result.sla_passed:
                if result.endpoint == "/health":
                    recommendations.append(
                        f"Health endpoint is slow ({result.p95_response_time:.3f}s). Consider removing unnecessary processing."
                    )
                elif result.endpoint == "/data":
                    recommendations.append(
                        f"Data endpoint is slow ({result.p95_response_time:.3f}s). Consider implementing Redis caching for market data."
                    )
                elif result.endpoint == "/signals":
                    recommendations.append(
                        f"Signals endpoint is slow ({result.p95_response_time:.3f}s). Consider ML model optimization or async processing."
                    )
                elif result.endpoint == "/backtest":
                    recommendations.append(
                        f"Backtest endpoint is slow ({result.p95_response_time:.3f}s). Consider implementing background job processing."
                    )

            if result.error_rate > 5:
                recommendations.append(
                    f"{result.endpoint} has high error rate ({result.error_rate:.1f}%). Investigate error causes."
                )

        if not recommendations:
            recommendations.append(
                "All endpoints meeting SLA targets. Consider stress testing or optimizations for better performance."
            )

        return recommendations

    def print_summary_report(self):
        """Print a formatted summary report to console"""
        if not self.results:
            print("No performance results available.")
            return

        print("\n" + "=" * 80)
        print("📊 FXML4 API PERFORMANCE TEST RESULTS")
        print("=" * 80)

        # Overall summary
        passed_slas = sum(1 for r in self.results if r.sla_passed)
        total_slas = len(self.results)
        overall_status = "✅ PASS" if passed_slas == total_slas else "❌ FAIL"

        print(
            f"Overall SLA Compliance: {overall_status} ({passed_slas}/{total_slas} endpoints)"
        )
        print()

        # Endpoint details
        print("📈 ENDPOINT PERFORMANCE DETAILS")
        print("-" * 80)
        print(
            f"{'Endpoint':<12} {'Method':<6} {'P95 Time':<10} {'Target':<10} {'Status':<8} {'RPS':<8} {'Error%':<8}"
        )
        print("-" * 80)

        for result in self.results:
            status = "✅ PASS" if result.sla_passed else "❌ FAIL"
            print(
                f"{result.endpoint:<12} {result.method:<6} {result.p95_response_time:<10.3f}s {result.sla_target:<10.3f}s {status:<8} {result.requests_per_second:<8.1f} {result.error_rate:<8.1f}%"
            )

        print()

        # Recommendations
        recommendations = self._generate_recommendations()
        if recommendations:
            print("💡 PERFORMANCE RECOMMENDATIONS")
            print("-" * 40)
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec}")

        print("\n" + "=" * 80)


async def check_api_availability(base_url: str) -> bool:
    """Check if API is available before testing"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}/health", timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return response.status == 200
    except:
        return False


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="FXML4 Comprehensive API Performance Testing"
    )
    parser.add_argument(
        "--base-url", default="http://localhost:8001", help="API base URL"
    )
    parser.add_argument(
        "--load-level",
        choices=["light", "normal", "stress"],
        default="normal",
        help="Load testing level",
    )
    parser.add_argument("--auth-token", help="Authentication token (optional)")
    parser.add_argument(
        "--output", default="api_performance_report.json", help="Output report file"
    )
    parser.add_argument(
        "--skip-availability-check",
        action="store_true",
        help="Skip API availability check",
    )

    args = parser.parse_args()

    # Check API availability
    if not args.skip_availability_check:
        logger.info(f"Checking API availability at {args.base_url}")
        if not await check_api_availability(args.base_url):
            logger.error(
                f"API not available at {args.base_url}. Please start the FXML4 API server."
            )
            sys.exit(1)
        logger.info("✅ API is available")

    # Run performance tests
    try:
        async with APIPerformanceTester(args.base_url, args.auth_token) as tester:
            logger.info(
                f"🚀 Starting comprehensive API performance testing - {args.load_level} load"
            )

            results = await tester.run_comprehensive_performance_test(args.load_level)

            # Generate and display report
            report = tester.generate_performance_report(args.output)
            tester.print_summary_report()

            # Exit with error code if SLAs failed
            if report["test_summary"]["sla_pass_rate"] < 100:
                logger.error("❌ Performance tests FAILED - SLA targets not met")
                sys.exit(1)
            else:
                logger.info("✅ Performance tests PASSED - All SLA targets met")

    except Exception as e:
        logger.error(f"Performance testing failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
