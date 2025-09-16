"""
Performance Contract Validator
=============================

Validates API performance contracts including response times, throughput,
resource usage, and SLA compliance for trading system APIs.
"""

import logging
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .contract_models import PerformanceContract, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance measurement results."""

    response_times_ms: List[float]
    throughput_rps: float
    error_rate_percent: float
    total_requests: int
    successful_requests: int
    failed_requests: int

    @property
    def avg_response_time_ms(self) -> float:
        """Average response time."""
        return (
            statistics.mean(self.response_times_ms) if self.response_times_ms else 0.0
        )

    @property
    def median_response_time_ms(self) -> float:
        """Median response time."""
        return (
            statistics.median(self.response_times_ms) if self.response_times_ms else 0.0
        )

    @property
    def p95_response_time_ms(self) -> float:
        """95th percentile response time."""
        if not self.response_times_ms:
            return 0.0
        sorted_times = sorted(self.response_times_ms)
        index = int(len(sorted_times) * 0.95)
        return sorted_times[min(index, len(sorted_times) - 1)]

    @property
    def p99_response_time_ms(self) -> float:
        """99th percentile response time."""
        if not self.response_times_ms:
            return 0.0
        sorted_times = sorted(self.response_times_ms)
        index = int(len(sorted_times) * 0.99)
        return sorted_times[min(index, len(sorted_times) - 1)]

    @property
    def min_response_time_ms(self) -> float:
        """Minimum response time."""
        return min(self.response_times_ms) if self.response_times_ms else 0.0

    @property
    def max_response_time_ms(self) -> float:
        """Maximum response time."""
        return max(self.response_times_ms) if self.response_times_ms else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate_percent": self.error_rate_percent,
            "throughput_rps": self.throughput_rps,
            "avg_response_time_ms": self.avg_response_time_ms,
            "median_response_time_ms": self.median_response_time_ms,
            "min_response_time_ms": self.min_response_time_ms,
            "max_response_time_ms": self.max_response_time_ms,
            "p95_response_time_ms": self.p95_response_time_ms,
            "p99_response_time_ms": self.p99_response_time_ms,
        }


class PerformanceValidator:
    """
    Performance validation engine for API contracts.

    Validates performance contracts by measuring:
    - Response times under various loads
    - Throughput and concurrency handling
    - Resource usage patterns
    - SLA compliance
    - Performance degradation under stress
    """

    def __init__(self):
        """Initialize performance validator."""
        self.baseline_metrics = {}
        self.performance_history = {}

    def validate_response_time(
        self, contract: PerformanceContract, actual_response_time_ms: float
    ) -> ValidationResult:
        """Validate single response time against contract."""
        result = ValidationResult()

        if actual_response_time_ms > contract.max_response_time_ms:
            result.add_error(
                f"Response time ({actual_response_time_ms:.2f}ms) exceeds "
                f"maximum allowed ({contract.max_response_time_ms}ms)"
            )
        elif actual_response_time_ms > contract.max_response_time_ms * 0.8:
            result.add_warning(
                f"Response time ({actual_response_time_ms:.2f}ms) approaching "
                f"maximum limit ({contract.max_response_time_ms}ms)"
            )

        result.details = {
            "actual_response_time_ms": actual_response_time_ms,
            "max_allowed_ms": contract.max_response_time_ms,
            "utilization_percent": (
                actual_response_time_ms / contract.max_response_time_ms
            )
            * 100,
        }

        return result

    def validate_throughput(
        self, contract: PerformanceContract, actual_throughput_rps: float
    ) -> ValidationResult:
        """Validate throughput against contract."""
        result = ValidationResult()

        if contract.min_throughput_rps is None:
            return result

        if actual_throughput_rps < contract.min_throughput_rps:
            result.add_error(
                f"Throughput ({actual_throughput_rps:.2f} RPS) below "
                f"minimum required ({contract.min_throughput_rps:.2f} RPS)"
            )
        elif actual_throughput_rps < contract.min_throughput_rps * 1.2:
            result.add_warning(
                f"Throughput ({actual_throughput_rps:.2f} RPS) close to "
                f"minimum threshold ({contract.min_throughput_rps:.2f} RPS)"
            )

        result.details = {
            "actual_throughput_rps": actual_throughput_rps,
            "min_required_rps": contract.min_throughput_rps,
            "performance_ratio": (
                actual_throughput_rps / contract.min_throughput_rps
                if contract.min_throughput_rps > 0
                else 0
            ),
        }

        return result

    def validate_performance_contract(
        self, contract: PerformanceContract, metrics: PerformanceMetrics
    ) -> ValidationResult:
        """Validate complete performance contract against measured metrics."""
        result = ValidationResult()

        # Validate response time (using P95)
        response_time_result = self.validate_response_time(
            contract, metrics.p95_response_time_ms
        )
        result = result.merge(response_time_result)

        # Validate throughput
        if contract.min_throughput_rps is not None:
            throughput_result = self.validate_throughput(
                contract, metrics.throughput_rps
            )
            result = result.merge(throughput_result)

        # Validate error rate
        error_rate_result = self._validate_error_rate(metrics.error_rate_percent)
        result = result.merge(error_rate_result)

        # Add comprehensive details
        result.details.update(
            {
                "performance_metrics": metrics.to_dict(),
                "contract_requirements": {
                    "max_response_time_ms": contract.max_response_time_ms,
                    "min_throughput_rps": contract.min_throughput_rps,
                    "max_response_size_bytes": contract.max_response_size_bytes,
                    "max_memory_usage_mb": contract.max_memory_usage_mb,
                    "max_cpu_usage_percent": contract.max_cpu_usage_percent,
                },
            }
        )

        return result

    def _validate_error_rate(self, error_rate_percent: float) -> ValidationResult:
        """Validate error rate."""
        result = ValidationResult()

        if error_rate_percent > 5.0:
            result.add_error(
                f"High error rate: {error_rate_percent:.2f}% (threshold: 5%)"
            )
        elif error_rate_percent > 1.0:
            result.add_warning(f"Elevated error rate: {error_rate_percent:.2f}%")

        return result

    def measure_endpoint_performance(
        self,
        request_func,
        num_requests: int = 100,
        concurrent_users: int = 10,
        ramp_up_time_seconds: int = 5,
    ) -> PerformanceMetrics:
        """
        Measure endpoint performance under load.

        Args:
            request_func: Function that makes HTTP request and returns (success: bool, response_time_ms: float)
            num_requests: Total number of requests to make
            concurrent_users: Number of concurrent users
            ramp_up_time_seconds: Time to ramp up to full load

        Returns:
            PerformanceMetrics with measurement results
        """
        logger.info(
            f"Starting performance test: {num_requests} requests, {concurrent_users} concurrent users"
        )

        response_times = []
        successful_requests = 0
        failed_requests = 0

        start_time = time.time()

        def make_request_with_timing():
            """Make request and return timing information."""
            request_start = time.time()
            try:
                success, response_time_ms = request_func()
                return success, response_time_ms
            except Exception as e:
                request_time = (time.time() - request_start) * 1000
                logger.error(f"Request failed: {e}")
                return False, request_time

        # Execute requests with controlled concurrency
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            # Submit all requests
            futures = []
            for i in range(num_requests):
                # Implement ramp-up delay
                if ramp_up_time_seconds > 0 and i < num_requests:
                    delay = (ramp_up_time_seconds * i) / num_requests
                    time.sleep(delay / concurrent_users)  # Distribute delay

                future = executor.submit(make_request_with_timing)
                futures.append(future)

            # Collect results
            for future in as_completed(futures):
                try:
                    success, response_time_ms = future.result(timeout=30)
                    response_times.append(response_time_ms)

                    if success:
                        successful_requests += 1
                    else:
                        failed_requests += 1

                except Exception as e:
                    logger.error(f"Future result error: {e}")
                    failed_requests += 1
                    response_times.append(30000)  # Timeout value

        end_time = time.time()
        total_time_seconds = end_time - start_time

        # Calculate metrics
        throughput_rps = (
            num_requests / total_time_seconds if total_time_seconds > 0 else 0
        )
        error_rate_percent = (
            (failed_requests / num_requests) * 100 if num_requests > 0 else 0
        )

        metrics = PerformanceMetrics(
            response_times_ms=response_times,
            throughput_rps=throughput_rps,
            error_rate_percent=error_rate_percent,
            total_requests=num_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
        )

        logger.info(
            f"Performance test completed: {throughput_rps:.2f} RPS, "
            f"{error_rate_percent:.2f}% error rate, "
            f"P95: {metrics.p95_response_time_ms:.2f}ms"
        )

        return metrics

    def run_load_test(
        self, request_func, load_profile: Dict[str, Any], contract: PerformanceContract
    ) -> ValidationResult:
        """
        Run comprehensive load test with multiple phases.

        Args:
            request_func: Function to make HTTP requests
            load_profile: Load testing configuration
            contract: Performance contract to validate against

        Returns:
            ValidationResult with load test results
        """
        result = ValidationResult()

        # Default load profile
        default_profile = {
            "baseline": {"users": 1, "duration_seconds": 30, "requests_per_second": 1},
            "normal_load": {
                "users": 5,
                "duration_seconds": 60,
                "requests_per_second": 10,
            },
            "peak_load": {
                "users": 20,
                "duration_seconds": 120,
                "requests_per_second": 50,
            },
            "stress_load": {
                "users": 50,
                "duration_seconds": 60,
                "requests_per_second": 100,
            },
        }

        load_profile = {**default_profile, **load_profile}

        for phase_name, phase_config in load_profile.items():
            logger.info(f"Starting load test phase: {phase_name}")

            try:
                # Calculate number of requests for this phase
                num_requests = (
                    phase_config["requests_per_second"]
                    * phase_config["duration_seconds"]
                )

                # Measure performance
                metrics = self.measure_endpoint_performance(
                    request_func=request_func,
                    num_requests=num_requests,
                    concurrent_users=phase_config["users"],
                )

                # Validate against contract
                phase_result = self.validate_performance_contract(contract, metrics)
                phase_result.details["phase"] = phase_name
                phase_result.details["phase_config"] = phase_config

                result = result.merge(phase_result)

                # Store metrics for trend analysis
                self.performance_history[phase_name] = metrics

                logger.info(
                    f"Phase {phase_name} completed: "
                    f"{metrics.throughput_rps:.2f} RPS, "
                    f"P95: {metrics.p95_response_time_ms:.2f}ms"
                )

            except Exception as e:
                logger.error(f"Load test phase {phase_name} failed: {e}")
                result.add_error(f"Load test phase {phase_name} failed: {str(e)}")

        return result

    def analyze_performance_trend(
        self, endpoint_name: str, time_window_hours: int = 24
    ) -> ValidationResult:
        """Analyze performance trends over time."""
        result = ValidationResult()

        # This would typically query a time-series database
        # For now, analyze stored metrics

        if endpoint_name not in self.performance_history:
            result.add_warning(f"No performance history found for {endpoint_name}")
            return result

        # Simplified trend analysis
        metrics_list = self.performance_history[endpoint_name]
        if not isinstance(metrics_list, list):
            metrics_list = [metrics_list]

        if len(metrics_list) < 2:
            result.add_warning("Insufficient data for trend analysis")
            return result

        # Analyze response time trend
        response_times = [m.avg_response_time_ms for m in metrics_list]
        if len(response_times) >= 2:
            recent_avg = statistics.mean(response_times[-3:])  # Last 3 measurements
            historical_avg = (
                statistics.mean(response_times[:-3])
                if len(response_times) > 3
                else response_times[0]
            )

            trend_change_percent = (
                ((recent_avg - historical_avg) / historical_avg) * 100
                if historical_avg > 0
                else 0
            )

            if trend_change_percent > 20:
                result.add_warning(
                    f"Response time increasing trend: {trend_change_percent:.1f}%"
                )
            elif trend_change_percent < -10:
                result.details["improvement"] = (
                    f"Response time improvement: {abs(trend_change_percent):.1f}%"
                )

        # Analyze throughput trend
        throughputs = [m.throughput_rps for m in metrics_list]
        if len(throughputs) >= 2:
            recent_throughput = statistics.mean(throughputs[-3:])
            historical_throughput = (
                statistics.mean(throughputs[:-3])
                if len(throughputs) > 3
                else throughputs[0]
            )

            throughput_change_percent = (
                ((recent_throughput - historical_throughput) / historical_throughput)
                * 100
                if historical_throughput > 0
                else 0
            )

            if throughput_change_percent < -15:
                result.add_warning(
                    f"Throughput decreasing trend: {abs(throughput_change_percent):.1f}%"
                )

        result.details.update(
            {
                "trend_analysis": {
                    "response_time_trend_percent": (
                        trend_change_percent
                        if "trend_change_percent" in locals()
                        else None
                    ),
                    "throughput_trend_percent": (
                        throughput_change_percent
                        if "throughput_change_percent" in locals()
                        else None
                    ),
                    "data_points": len(metrics_list),
                }
            }
        )

        return result

    def benchmark_against_baseline(
        self,
        current_metrics: PerformanceMetrics,
        baseline_metrics: PerformanceMetrics,
        tolerance_percent: float = 10.0,
    ) -> ValidationResult:
        """Compare current performance against established baseline."""
        result = ValidationResult()

        # Response time comparison
        response_time_change = (
            (
                current_metrics.avg_response_time_ms
                - baseline_metrics.avg_response_time_ms
            )
            / baseline_metrics.avg_response_time_ms
        ) * 100

        if response_time_change > tolerance_percent:
            result.add_error(
                f"Response time degraded by {response_time_change:.1f}% vs baseline"
            )
        elif response_time_change > tolerance_percent / 2:
            result.add_warning(
                f"Response time increased by {response_time_change:.1f}% vs baseline"
            )

        # Throughput comparison
        throughput_change = (
            (current_metrics.throughput_rps - baseline_metrics.throughput_rps)
            / baseline_metrics.throughput_rps
        ) * 100

        if throughput_change < -tolerance_percent:
            result.add_error(
                f"Throughput degraded by {abs(throughput_change):.1f}% vs baseline"
            )
        elif throughput_change < -tolerance_percent / 2:
            result.add_warning(
                f"Throughput decreased by {abs(throughput_change):.1f}% vs baseline"
            )

        # Error rate comparison
        error_rate_change = (
            current_metrics.error_rate_percent - baseline_metrics.error_rate_percent
        )

        if error_rate_change > 2.0:
            result.add_error(
                f"Error rate increased by {error_rate_change:.1f}% vs baseline"
            )
        elif error_rate_change > 1.0:
            result.add_warning(
                f"Error rate increased by {error_rate_change:.1f}% vs baseline"
            )

        result.details = {
            "baseline_comparison": {
                "response_time_change_percent": response_time_change,
                "throughput_change_percent": throughput_change,
                "error_rate_change_percent": error_rate_change,
                "current_metrics": current_metrics.to_dict(),
                "baseline_metrics": baseline_metrics.to_dict(),
            }
        }

        return result


class PerformanceBenchmark:
    """
    Performance benchmarking utilities for API contracts.
    """

    def __init__(self):
        """Initialize performance benchmark."""
        self.benchmarks = {}

    def establish_baseline(
        self, endpoint_name: str, request_func, iterations: int = 50
    ) -> PerformanceMetrics:
        """Establish performance baseline for an endpoint."""
        validator = PerformanceValidator()

        # Run multiple small tests to establish consistent baseline
        all_metrics = []
        for i in range(5):  # 5 separate runs
            metrics = validator.measure_endpoint_performance(
                request_func=request_func,
                num_requests=iterations // 5,
                concurrent_users=1,  # Single user for baseline
            )
            all_metrics.append(metrics)

        # Combine metrics
        combined_response_times = []
        total_requests = 0
        total_successful = 0
        total_failed = 0

        for metrics in all_metrics:
            combined_response_times.extend(metrics.response_times_ms)
            total_requests += metrics.total_requests
            total_successful += metrics.successful_requests
            total_failed += metrics.failed_requests

        baseline_metrics = PerformanceMetrics(
            response_times_ms=combined_response_times,
            throughput_rps=statistics.mean([m.throughput_rps for m in all_metrics]),
            error_rate_percent=(
                (total_failed / total_requests) * 100 if total_requests > 0 else 0
            ),
            total_requests=total_requests,
            successful_requests=total_successful,
            failed_requests=total_failed,
        )

        # Store baseline
        self.benchmarks[endpoint_name] = baseline_metrics

        logger.info(
            f"Established baseline for {endpoint_name}: "
            f"Avg: {baseline_metrics.avg_response_time_ms:.2f}ms, "
            f"P95: {baseline_metrics.p95_response_time_ms:.2f}ms"
        )

        return baseline_metrics

    def get_baseline(self, endpoint_name: str) -> Optional[PerformanceMetrics]:
        """Get stored baseline for endpoint."""
        return self.benchmarks.get(endpoint_name)

    def compare_to_industry_standards(
        self, metrics: PerformanceMetrics, api_type: str = "financial"
    ) -> ValidationResult:
        """Compare metrics against industry standards."""
        result = ValidationResult()

        # Industry standards for financial APIs
        standards = {
            "financial": {
                "max_response_time_ms": 500,
                "max_p95_response_time_ms": 1000,
                "min_throughput_rps": 100,
                "max_error_rate_percent": 0.1,
            },
            "trading": {
                "max_response_time_ms": 100,
                "max_p95_response_time_ms": 200,
                "min_throughput_rps": 500,
                "max_error_rate_percent": 0.01,
            },
            "general": {
                "max_response_time_ms": 1000,
                "max_p95_response_time_ms": 2000,
                "min_throughput_rps": 50,
                "max_error_rate_percent": 1.0,
            },
        }

        standard = standards.get(api_type, standards["general"])

        # Compare against standards
        if metrics.avg_response_time_ms > standard["max_response_time_ms"]:
            result.add_warning(
                f"Average response time ({metrics.avg_response_time_ms:.2f}ms) "
                f"above industry standard ({standard['max_response_time_ms']}ms)"
            )

        if metrics.p95_response_time_ms > standard["max_p95_response_time_ms"]:
            result.add_warning(
                f"P95 response time ({metrics.p95_response_time_ms:.2f}ms) "
                f"above industry standard ({standard['max_p95_response_time_ms']}ms)"
            )

        if metrics.throughput_rps < standard["min_throughput_rps"]:
            result.add_warning(
                f"Throughput ({metrics.throughput_rps:.2f} RPS) "
                f"below industry standard ({standard['min_throughput_rps']} RPS)"
            )

        if metrics.error_rate_percent > standard["max_error_rate_percent"]:
            result.add_error(
                f"Error rate ({metrics.error_rate_percent:.3f}%) "
                f"above industry standard ({standard['max_error_rate_percent']}%)"
            )

        result.details["industry_comparison"] = {
            "api_type": api_type,
            "standards": standard,
            "metrics": metrics.to_dict(),
        }

        return result
