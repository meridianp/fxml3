"""
Comprehensive Load Testing Framework

High-performance load testing specifically designed for trading systems:
- Realistic trading workload simulation
- Concurrent user simulation with trading patterns
- Real-time performance monitoring during tests
- Automated pass/fail criteria based on trading SLAs
- Detailed reporting with performance analytics
"""

import asyncio
import json
import logging
import random
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, NamedTuple, Optional

import aiohttp

from ...performance.latency_monitor import LatencyMonitor


class LoadTestType(Enum):
    """Load test type enumeration"""

    BASELINE = "baseline"
    LOAD = "load"
    STRESS = "stress"
    SPIKE = "spike"
    VOLUME = "volume"
    ENDURANCE = "endurance"


class TradingOperation(Enum):
    """Trading operation types for testing"""

    GET_MARKET_DATA = "get_market_data"
    PLACE_ORDER = "place_order"
    CANCEL_ORDER = "cancel_order"
    GET_POSITIONS = "get_positions"
    GET_ACCOUNT = "get_account"
    STREAM_PRICES = "stream_prices"
    RUN_BACKTEST = "run_backtest"
    GET_SIGNALS = "get_signals"


@dataclass
class LoadTestConfig:
    """Load test configuration"""

    name: str
    test_type: LoadTestType
    base_url: str

    # Load parameters
    concurrent_users: int = 100
    requests_per_user: int = 100
    ramp_up_seconds: float = 30.0
    test_duration_seconds: float = 300.0  # 5 minutes
    ramp_down_seconds: float = 30.0

    # Trading-specific parameters
    operation_weights: Dict[TradingOperation, float] = field(
        default_factory=lambda: {
            TradingOperation.GET_MARKET_DATA: 0.4,
            TradingOperation.PLACE_ORDER: 0.2,
            TradingOperation.CANCEL_ORDER: 0.1,
            TradingOperation.GET_POSITIONS: 0.15,
            TradingOperation.GET_ACCOUNT: 0.1,
            TradingOperation.GET_SIGNALS: 0.05,
        }
    )

    # Performance thresholds
    max_response_time_ms: float = 100.0
    max_p95_response_time_ms: float = 200.0
    max_error_rate_percent: float = 1.0
    min_throughput_rps: float = 1000.0

    # Authentication
    auth_token: Optional[str] = None
    auth_headers: Dict[str, str] = field(default_factory=dict)

    # Request configuration
    timeout_seconds: float = 30.0
    connection_pool_size: int = 100

    # Reporting
    enable_detailed_logging: bool = True
    enable_real_time_monitoring: bool = True


@dataclass
class RequestResult:
    """Individual request result"""

    operation: TradingOperation
    start_time: float
    end_time: float
    response_time_ms: float
    status_code: int
    success: bool
    error_message: Optional[str] = None
    response_size: int = 0

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000


@dataclass
class LoadTestResult:
    """Complete load test results"""

    config: LoadTestConfig
    start_time: float
    end_time: float
    total_duration_seconds: float

    # Request statistics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Performance metrics
    average_response_time_ms: float = 0.0
    min_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    p50_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0

    # Throughput metrics
    requests_per_second: float = 0.0
    peak_rps: float = 0.0

    # Error analysis
    error_rate_percent: float = 0.0
    errors_by_type: Dict[str, int] = field(default_factory=dict)

    # Per-operation breakdown
    operation_stats: Dict[TradingOperation, Dict[str, Any]] = field(
        default_factory=dict
    )

    # Test verdict
    passed: bool = False
    failure_reasons: List[str] = field(default_factory=list)

    @property
    def success_rate_percent(self) -> float:
        return (
            (self.successful_requests / self.total_requests * 100.0)
            if self.total_requests > 0
            else 0.0
        )


class TradingWorkloadGenerator:
    """Generates realistic trading workloads"""

    def __init__(self, base_url: str, auth_headers: Dict[str, str] = None):
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers or {}

        # Sample trading data
        self.symbols = [
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "AUDUSD",
            "USDCAD",
            "NZDUSD",
            "USDCHF",
            "EURGBP",
            "EURJPY",
            "GBPJPY",
        ]
        self.order_types = ["market", "limit", "stop"]
        self.sides = ["buy", "sell"]

    def generate_request(self, operation: TradingOperation) -> Dict[str, Any]:
        """Generate request for specific trading operation"""

        if operation == TradingOperation.GET_MARKET_DATA:
            return {
                "method": "GET",
                "url": f"{self.base_url}/api/v1/market-data/{random.choice(self.symbols)}",
                "headers": self.auth_headers,
            }

        elif operation == TradingOperation.PLACE_ORDER:
            return {
                "method": "POST",
                "url": f"{self.base_url}/api/v1/orders",
                "headers": {**self.auth_headers, "Content-Type": "application/json"},
                "json": {
                    "symbol": random.choice(self.symbols),
                    "side": random.choice(self.sides),
                    "type": random.choice(self.order_types),
                    "quantity": random.randint(1000, 100000),
                    "price": (
                        round(random.uniform(1.0, 2.0), 5)
                        if random.choice(self.order_types) != "market"
                        else None
                    ),
                },
            }

        elif operation == TradingOperation.CANCEL_ORDER:
            return {
                "method": "DELETE",
                "url": f"{self.base_url}/api/v1/orders/{random.randint(1, 1000)}",
                "headers": self.auth_headers,
            }

        elif operation == TradingOperation.GET_POSITIONS:
            return {
                "method": "GET",
                "url": f"{self.base_url}/api/v1/positions",
                "headers": self.auth_headers,
            }

        elif operation == TradingOperation.GET_ACCOUNT:
            return {
                "method": "GET",
                "url": f"{self.base_url}/api/v1/account",
                "headers": self.auth_headers,
            }

        elif operation == TradingOperation.GET_SIGNALS:
            return {
                "method": "POST",
                "url": f"{self.base_url}/api/v1/signals",
                "headers": {**self.auth_headers, "Content-Type": "application/json"},
                "json": {
                    "symbol": random.choice(self.symbols),
                    "timeframe": random.choice(["1m", "5m", "15m", "1h"]),
                    "strategy": "ml_ensemble",
                },
            }

        elif operation == TradingOperation.RUN_BACKTEST:
            return {
                "method": "POST",
                "url": f"{self.base_url}/api/v1/backtest",
                "headers": {**self.auth_headers, "Content-Type": "application/json"},
                "json": {
                    "symbol": random.choice(self.symbols),
                    "strategy": "ml_ensemble",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "initial_capital": 100000,
                },
            }

        else:
            # Default to market data request
            return {
                "method": "GET",
                "url": f"{self.base_url}/api/v1/health",
                "headers": self.auth_headers,
            }


class LoadTestFramework:
    """
    Comprehensive load testing framework for FXML4 trading system

    Features:
    - Concurrent user simulation with realistic trading patterns
    - Real-time performance monitoring during tests
    - Detailed analytics and reporting
    - Automated pass/fail criteria
    - Integration with CI/CD pipelines
    """

    def __init__(self):
        self.latency_monitor = LatencyMonitor()
        self.logger = logging.getLogger("LoadTestFramework")

        # Test state
        self.running = False
        self.current_users = 0
        self.request_results: deque = deque(maxlen=100_000)

        # Real-time metrics
        self.metrics_lock = threading.Lock()
        self.current_rps = 0.0
        self.current_error_rate = 0.0
        self.current_avg_latency = 0.0

        # Performance tracking
        self.rps_history: deque = deque(maxlen=300)  # 5 minutes at 1-second intervals
        self.latency_history: deque = deque(maxlen=300)
        self.error_rate_history: deque = deque(maxlen=300)

    async def run_load_test(self, config: LoadTestConfig) -> LoadTestResult:
        """Run complete load test"""
        self.logger.info(f"Starting load test: {config.name}")

        # Initialize test
        result = LoadTestResult(
            config=config, start_time=time.time(), end_time=0, total_duration_seconds=0
        )

        # Clear previous results
        self.request_results.clear()

        try:
            # Start monitoring
            monitoring_task = asyncio.create_task(self._monitoring_loop(config))

            # Execute test phases
            await self._execute_test_phases(config)

            # Stop monitoring
            monitoring_task.cancel()

            # Analyze results
            result = self._analyze_results(config, result)

            self.logger.info(f"Load test completed: {config.name}")

        except Exception as e:
            self.logger.error(f"Load test failed: {e}")
            result.failure_reasons.append(f"Test execution error: {str(e)}")

        finally:
            result.end_time = time.time()
            result.total_duration_seconds = result.end_time - result.start_time

        return result

    async def _execute_test_phases(self, config: LoadTestConfig):
        """Execute test phases: ramp-up, steady state, ramp-down"""

        # Phase 1: Ramp-up
        self.logger.info("Phase 1: Ramp-up")
        await self._ramp_up_phase(config)

        # Phase 2: Steady state load
        self.logger.info("Phase 2: Steady state")
        await self._steady_state_phase(config)

        # Phase 3: Ramp-down
        self.logger.info("Phase 3: Ramp-down")
        await self._ramp_down_phase(config)

    async def _ramp_up_phase(self, config: LoadTestConfig):
        """Gradually increase load to target level"""
        self.running = True

        user_increment = config.concurrent_users / (
            config.ramp_up_seconds / 5.0
        )  # Add users every 5 seconds
        current_users = 0

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=config.timeout_seconds),
            connector=aiohttp.TCPConnector(limit=config.connection_pool_size),
        ) as session:

            while current_users < config.concurrent_users and self.running:
                # Add more users
                users_to_add = min(
                    int(user_increment), config.concurrent_users - current_users
                )

                for _ in range(users_to_add):
                    asyncio.create_task(self._user_session(config, session))

                current_users += users_to_add
                self.current_users = current_users

                self.logger.debug(
                    f"Ramping up: {current_users}/{config.concurrent_users} users"
                )
                await asyncio.sleep(5.0)

    async def _steady_state_phase(self, config: LoadTestConfig):
        """Maintain steady load"""
        self.logger.info(f"Maintaining {config.concurrent_users} concurrent users")
        await asyncio.sleep(config.test_duration_seconds)

    async def _ramp_down_phase(self, config: LoadTestConfig):
        """Gradually decrease load"""
        self.running = False

        self.logger.info("Ramping down load")
        await asyncio.sleep(config.ramp_down_seconds)

    async def _user_session(
        self, config: LoadTestConfig, session: aiohttp.ClientSession
    ):
        """Simulate individual user session"""
        workload_generator = TradingWorkloadGenerator(
            config.base_url, config.auth_headers
        )

        requests_sent = 0

        while self.running and requests_sent < config.requests_per_user:
            try:
                # Select operation based on weights
                operation = self._select_weighted_operation(config.operation_weights)

                # Generate request
                request_config = workload_generator.generate_request(operation)

                # Execute request with timing
                start_time = time.time()

                async with session.request(**request_config) as response:
                    await response.text()  # Read response body

                    end_time = time.time()
                    response_time_ms = (end_time - start_time) * 1000

                    # Record result
                    result = RequestResult(
                        operation=operation,
                        start_time=start_time,
                        end_time=end_time,
                        response_time_ms=response_time_ms,
                        status_code=response.status,
                        success=response.status < 400,
                        response_size=(
                            len(await response.text()) if response.content_length else 0
                        ),
                    )

                    self.request_results.append(result)
                    requests_sent += 1

                    # Small delay between requests (realistic user behavior)
                    await asyncio.sleep(random.uniform(0.1, 2.0))

            except Exception as e:
                # Record failed request
                end_time = time.time()
                result = RequestResult(
                    operation=operation,
                    start_time=start_time,
                    end_time=end_time,
                    response_time_ms=(end_time - start_time) * 1000,
                    status_code=0,
                    success=False,
                    error_message=str(e),
                )

                self.request_results.append(result)
                requests_sent += 1

    def _select_weighted_operation(
        self, weights: Dict[TradingOperation, float]
    ) -> TradingOperation:
        """Select operation based on weights"""
        operations = list(weights.keys())
        operation_weights = list(weights.values())

        # Normalize weights
        total_weight = sum(operation_weights)
        normalized_weights = [w / total_weight for w in operation_weights]

        # Select based on random choice
        return random.choices(operations, weights=normalized_weights)[0]

    async def _monitoring_loop(self, config: LoadTestConfig):
        """Real-time performance monitoring during test"""

        while True:
            try:
                await asyncio.sleep(1.0)  # Update every second

                # Calculate current metrics
                current_time = time.time()
                recent_results = [
                    r for r in self.request_results if current_time - r.end_time <= 10.0
                ]  # Last 10 seconds

                if recent_results:
                    with self.metrics_lock:
                        # Calculate RPS
                        self.current_rps = len(recent_results) / 10.0

                        # Calculate error rate
                        failed_requests = sum(
                            1 for r in recent_results if not r.success
                        )
                        self.current_error_rate = (
                            failed_requests / len(recent_results)
                        ) * 100

                        # Calculate average latency
                        self.current_avg_latency = statistics.mean(
                            r.response_time_ms for r in recent_results
                        )

                        # Store history
                        self.rps_history.append(self.current_rps)
                        self.error_rate_history.append(self.current_error_rate)
                        self.latency_history.append(self.current_avg_latency)

                    # Log current status
                    if config.enable_real_time_monitoring:
                        self.logger.info(
                            f"Users: {self.current_users}, "
                            f"RPS: {self.current_rps:.1f}, "
                            f"Avg Latency: {self.current_avg_latency:.1f}ms, "
                            f"Error Rate: {self.current_error_rate:.1f}%"
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")

    def _analyze_results(
        self, config: LoadTestConfig, result: LoadTestResult
    ) -> LoadTestResult:
        """Analyze test results and generate comprehensive report"""

        if not self.request_results:
            result.failure_reasons.append("No requests completed")
            return result

        results_list = list(self.request_results)

        # Basic statistics
        result.total_requests = len(results_list)
        result.successful_requests = sum(1 for r in results_list if r.success)
        result.failed_requests = result.total_requests - result.successful_requests

        # Performance metrics
        response_times = [r.response_time_ms for r in results_list if r.success]

        if response_times:
            result.average_response_time_ms = statistics.mean(response_times)
            result.min_response_time_ms = min(response_times)
            result.max_response_time_ms = max(response_times)
            result.p50_response_time_ms = self._percentile(response_times, 0.50)
            result.p95_response_time_ms = self._percentile(response_times, 0.95)
            result.p99_response_time_ms = self._percentile(response_times, 0.99)

        # Throughput metrics
        if result.total_duration_seconds > 0:
            result.requests_per_second = (
                result.total_requests / result.total_duration_seconds
            )
            result.peak_rps = max(self.rps_history) if self.rps_history else 0

        # Error analysis
        result.error_rate_percent = (
            (result.failed_requests / result.total_requests * 100)
            if result.total_requests > 0
            else 0
        )

        # Collect error types
        for r in results_list:
            if not r.success:
                error_key = r.error_message or f"HTTP_{r.status_code}"
                result.errors_by_type[error_key] = (
                    result.errors_by_type.get(error_key, 0) + 1
                )

        # Per-operation analysis
        operation_results = defaultdict(list)
        for r in results_list:
            operation_results[r.operation].append(r)

        for operation, op_results in operation_results.items():
            successful_ops = [r for r in op_results if r.success]

            if successful_ops:
                response_times = [r.response_time_ms for r in successful_ops]

                result.operation_stats[operation] = {
                    "total_requests": len(op_results),
                    "successful_requests": len(successful_ops),
                    "error_rate_percent": (
                        (len(op_results) - len(successful_ops)) / len(op_results)
                    )
                    * 100,
                    "average_response_time_ms": statistics.mean(response_times),
                    "p95_response_time_ms": self._percentile(response_times, 0.95),
                    "requests_per_second": len(op_results)
                    / result.total_duration_seconds,
                }

        # Apply pass/fail criteria
        result.passed = self._evaluate_test_criteria(config, result)

        return result

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data"""
        sorted_data = sorted(data)
        index = int(percentile * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _evaluate_test_criteria(
        self, config: LoadTestConfig, result: LoadTestResult
    ) -> bool:
        """Evaluate pass/fail criteria"""
        passed = True

        # Check response time criteria
        if result.average_response_time_ms > config.max_response_time_ms:
            result.failure_reasons.append(
                f"Average response time {result.average_response_time_ms:.1f}ms exceeds limit {config.max_response_time_ms}ms"
            )
            passed = False

        if result.p95_response_time_ms > config.max_p95_response_time_ms:
            result.failure_reasons.append(
                f"P95 response time {result.p95_response_time_ms:.1f}ms exceeds limit {config.max_p95_response_time_ms}ms"
            )
            passed = False

        # Check error rate criteria
        if result.error_rate_percent > config.max_error_rate_percent:
            result.failure_reasons.append(
                f"Error rate {result.error_rate_percent:.1f}% exceeds limit {config.max_error_rate_percent}%"
            )
            passed = False

        # Check throughput criteria
        if result.requests_per_second < config.min_throughput_rps:
            result.failure_reasons.append(
                f"Throughput {result.requests_per_second:.1f} RPS below minimum {config.min_throughput_rps} RPS"
            )
            passed = False

        return passed

    def generate_report(self, result: LoadTestResult) -> Dict[str, Any]:
        """Generate comprehensive test report"""

        return {
            "test_summary": {
                "name": result.config.name,
                "test_type": result.config.test_type.value,
                "passed": result.passed,
                "duration_seconds": result.total_duration_seconds,
                "concurrent_users": result.config.concurrent_users,
            },
            "performance_metrics": {
                "total_requests": result.total_requests,
                "successful_requests": result.successful_requests,
                "failed_requests": result.failed_requests,
                "success_rate_percent": result.success_rate_percent,
                "error_rate_percent": result.error_rate_percent,
                "requests_per_second": result.requests_per_second,
                "peak_rps": result.peak_rps,
            },
            "response_time_metrics": {
                "average_ms": result.average_response_time_ms,
                "min_ms": result.min_response_time_ms,
                "max_ms": result.max_response_time_ms,
                "p50_ms": result.p50_response_time_ms,
                "p95_ms": result.p95_response_time_ms,
                "p99_ms": result.p99_response_time_ms,
            },
            "operation_breakdown": {
                op.value: stats for op, stats in result.operation_stats.items()
            },
            "error_analysis": result.errors_by_type,
            "failure_reasons": result.failure_reasons,
            "test_configuration": {
                "concurrent_users": result.config.concurrent_users,
                "requests_per_user": result.config.requests_per_user,
                "test_duration_seconds": result.config.test_duration_seconds,
                "max_response_time_ms": result.config.max_response_time_ms,
                "max_error_rate_percent": result.config.max_error_rate_percent,
                "min_throughput_rps": result.config.min_throughput_rps,
            },
        }


# Example usage and testing
if __name__ == "__main__":
    import asyncio

    async def main():
        print("FXML4 Load Testing Framework Demo")
        print("=" * 50)

        # Create load test framework
        framework = LoadTestFramework()

        # Configure load test
        config = LoadTestConfig(
            name="API Load Test",
            test_type=LoadTestType.LOAD,
            base_url="http://localhost:8001",
            concurrent_users=50,
            requests_per_user=20,
            ramp_up_seconds=10.0,
            test_duration_seconds=60.0,
            ramp_down_seconds=10.0,
            max_response_time_ms=100.0,
            max_error_rate_percent=5.0,
            min_throughput_rps=100.0,
            enable_real_time_monitoring=True,
        )

        # Run load test
        try:
            result = await framework.run_load_test(config)

            # Generate report
            report = framework.generate_report(result)

            print(f"\nLoad Test Results:")
            print(f"Test Name: {report['test_summary']['name']}")
            print(f"Test Type: {report['test_summary']['test_type']}")
            print(f"Passed: {report['test_summary']['passed']}")
            print(f"Duration: {report['test_summary']['duration_seconds']:.1f}s")
            print(f"Concurrent Users: {report['test_summary']['concurrent_users']}")

            print(f"\nPerformance Metrics:")
            perf = report["performance_metrics"]
            print(f"Total Requests: {perf['total_requests']:,}")
            print(f"Success Rate: {perf['success_rate_percent']:.1f}%")
            print(f"Requests/Second: {perf['requests_per_second']:.1f}")
            print(f"Peak RPS: {perf['peak_rps']:.1f}")

            print(f"\nResponse Time Metrics:")
            resp = report["response_time_metrics"]
            print(f"Average: {resp['average_ms']:.1f}ms")
            print(f"P50: {resp['p50_ms']:.1f}ms")
            print(f"P95: {resp['p95_ms']:.1f}ms")
            print(f"P99: {resp['p99_ms']:.1f}ms")
            print(f"Max: {resp['max_ms']:.1f}ms")

            if result.failure_reasons:
                print(f"\nFailure Reasons:")
                for reason in result.failure_reasons:
                    print(f"  - {reason}")

            print(f"\nOperation Breakdown:")
            for operation, stats in report["operation_breakdown"].items():
                print(f"  {operation}:")
                print(f"    Requests: {stats['total_requests']}")
                print(f"    Success Rate: {100 - stats['error_rate_percent']:.1f}%")
                print(f"    Avg Response: {stats['average_response_time_ms']:.1f}ms")

        except Exception as e:
            print(f"Load test failed: {e}")

    # Run the demo
    asyncio.run(main())
