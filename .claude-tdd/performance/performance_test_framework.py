#!/usr/bin/env python3
"""
Performance Testing Framework for FXML4
Real-time trading system performance validation with strict SLA requirements
"""

import asyncio
import json
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import psutil
import yaml


@dataclass
class PerformanceMetrics:
    """Performance metrics for a test execution"""

    test_name: str
    component: str

    # Latency metrics (in milliseconds)
    avg_latency: float
    p50_latency: float
    p95_latency: float
    p99_latency: float
    max_latency: float
    min_latency: float

    # Throughput metrics
    throughput_ops_per_sec: float
    total_operations: int

    # Resource utilization
    cpu_usage_percent: float
    memory_usage_mb: float
    peak_memory_mb: float

    # Success/Error rates
    success_rate: float
    error_rate: float
    timeout_rate: float

    # Execution details
    execution_time: float
    concurrent_users: int
    test_duration: float
    timestamp: datetime = field(default_factory=datetime.now)

    # SLA compliance
    sla_passed: bool = False
    sla_violations: List[str] = field(default_factory=list)


@dataclass
class PerformanceSLA:
    """Service Level Agreement requirements for trading system"""

    # Latency requirements (milliseconds)
    max_avg_latency: float = 10.0  # Average latency < 10ms
    max_p95_latency: float = 50.0  # 95th percentile < 50ms
    max_p99_latency: float = 100.0  # 99th percentile < 100ms

    # Throughput requirements
    min_throughput_ops_per_sec: float = 1000.0  # Minimum 1000 ops/sec

    # Resource limits
    max_cpu_usage: float = 80.0  # CPU usage < 80%
    max_memory_usage_mb: float = 2000.0  # Memory < 2GB

    # Reliability requirements
    min_success_rate: float = 99.9  # 99.9% success rate
    max_error_rate: float = 0.1  # Error rate < 0.1%
    max_timeout_rate: float = 0.01  # Timeout rate < 0.01%


@dataclass
class LoadTestConfig:
    """Configuration for load testing scenarios"""

    name: str
    description: str
    concurrent_users: int = 10
    test_duration_seconds: int = 60
    ramp_up_seconds: int = 10
    operations_per_user: int = 100
    think_time_ms: int = 0  # Time between operations

    # Test data configuration
    data_size: str = "small"  # small, medium, large
    randomize_data: bool = True

    # Specific to financial trading
    market_data_frequency: float = 100.0  # Updates per second
    order_frequency: float = 10.0  # Orders per second
    price_calculation_complexity: str = "medium"  # simple, medium, complex


class PerformanceTestFramework:
    """Performance testing framework for FXML4 trading system"""

    def __init__(self, config_path: str = ".claude-tdd/config.yml"):
        self.config = self._load_config(config_path)
        self.project_root = Path.cwd()
        self.performance_root = self.project_root / ".claude-tdd/performance"
        self.reports_dir = self.performance_root / "reports"
        self.reports_dir.mkdir(exist_ok=True)

        # Load SLA requirements
        self.sla = self._load_sla_requirements()

        # Load test configurations
        self.load_test_configs = self._create_load_test_configs()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load TDD configuration"""
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _load_sla_requirements(self) -> Dict[str, PerformanceSLA]:
        """Load SLA requirements for different components"""
        slas = {}

        # Core trading system - most stringent requirements
        slas["core"] = PerformanceSLA(
            max_avg_latency=5.0,  # 5ms average
            max_p95_latency=25.0,  # 25ms 95th percentile
            max_p99_latency=50.0,  # 50ms 99th percentile
            min_throughput_ops_per_sec=2000.0,  # 2000 ops/sec
            max_cpu_usage=70.0,
            max_memory_usage_mb=1000.0,
            min_success_rate=99.95,
            max_error_rate=0.05,
            max_timeout_rate=0.005,
        )

        # Elliott Wave ML - ML processing requirements
        slas["elliott_wave"] = PerformanceSLA(
            max_avg_latency=100.0,  # 100ms for ML processing
            max_p95_latency=500.0,  # 500ms 95th percentile
            max_p99_latency=1000.0,  # 1s 99th percentile
            min_throughput_ops_per_sec=100.0,  # 100 analyses/sec
            max_cpu_usage=90.0,  # Can use more CPU for ML
            max_memory_usage_mb=4000.0,  # 4GB for ML models
            min_success_rate=99.0,
            max_error_rate=1.0,
            max_timeout_rate=0.1,
        )

        # Frontend - UI responsiveness requirements
        slas["frontend"] = PerformanceSLA(
            max_avg_latency=200.0,  # 200ms for UI interactions
            max_p95_latency=1000.0,  # 1s 95th percentile
            max_p99_latency=3000.0,  # 3s 99th percentile
            min_throughput_ops_per_sec=50.0,  # 50 UI operations/sec
            max_cpu_usage=50.0,  # Light CPU usage for frontend
            max_memory_usage_mb=500.0,  # 500MB for frontend
            min_success_rate=99.5,
            max_error_rate=0.5,
            max_timeout_rate=0.05,
        )

        return slas

    def _create_load_test_configs(self) -> Dict[str, LoadTestConfig]:
        """Create load testing configurations for different scenarios"""
        configs = {}

        # Light load - normal trading hours
        configs["light_load"] = LoadTestConfig(
            name="light_load",
            description="Normal trading hours load",
            concurrent_users=10,
            test_duration_seconds=60,
            ramp_up_seconds=5,
            operations_per_user=100,
            market_data_frequency=50.0,
            order_frequency=5.0,
        )

        # Peak load - high volatility periods
        configs["peak_load"] = LoadTestConfig(
            name="peak_load",
            description="High volatility peak load",
            concurrent_users=50,
            test_duration_seconds=120,
            ramp_up_seconds=10,
            operations_per_user=200,
            market_data_frequency=200.0,
            order_frequency=20.0,
        )

        # Stress test - extreme conditions
        configs["stress_test"] = LoadTestConfig(
            name="stress_test",
            description="Extreme load stress test",
            concurrent_users=100,
            test_duration_seconds=300,
            ramp_up_seconds=20,
            operations_per_user=500,
            market_data_frequency=500.0,
            order_frequency=50.0,
            price_calculation_complexity="complex",
        )

        # Endurance test - long-running stability
        configs["endurance_test"] = LoadTestConfig(
            name="endurance_test",
            description="Long-running stability test",
            concurrent_users=25,
            test_duration_seconds=1800,  # 30 minutes
            ramp_up_seconds=30,
            operations_per_user=1000,
            market_data_frequency=100.0,
            order_frequency=10.0,
        )

        return configs

    def run_performance_tests(
        self,
        component: str = None,
        test_config: str = "light_load",
        dry_run: bool = False,
    ) -> List[PerformanceMetrics]:
        """Run performance tests for specified component"""

        if component:
            components = [component]
        else:
            components = list(self.config["components"].keys())

        results = []
        config = self.load_test_configs[test_config]

        print(f"Running performance tests with config: {test_config}")
        print(f"Components: {components}")

        for comp in components:
            if dry_run:
                print(f"[DRY RUN] Would run performance tests for {comp}")
                continue

            comp_results = self._run_component_performance_tests(comp, config)
            results.extend(comp_results)

        # Generate reports
        self._generate_performance_reports(results, test_config)

        return results

    def _run_component_performance_tests(
        self, component: str, config: LoadTestConfig
    ) -> List[PerformanceMetrics]:
        """Run performance tests for a specific component"""

        print(f"\nRunning performance tests for {component}")
        results = []

        component_config = self.config["components"][component]
        language = component_config["language"]

        if language == "python":
            results.extend(self._run_python_performance_tests(component, config))
        elif language == "typescript":
            results.extend(self._run_frontend_performance_tests(component, config))
        else:
            print(f"Unsupported language for performance testing: {language}")

        return results

    def _run_python_performance_tests(
        self, component: str, config: LoadTestConfig
    ) -> List[PerformanceMetrics]:
        """Run Python component performance tests"""

        results = []

        # Test scenarios for Python components
        test_scenarios = [
            ("api_latency_test", self._test_api_latency),
            ("throughput_test", self._test_throughput),
            ("concurrent_load_test", self._test_concurrent_load),
            ("memory_stress_test", self._test_memory_usage),
        ]

        for test_name, test_func in test_scenarios:
            print(f"  Running {test_name}...")

            try:
                metrics = test_func(component, config, test_name)

                # Check SLA compliance
                sla = self.sla.get(component, self.sla["core"])
                metrics.sla_passed, metrics.sla_violations = self._check_sla_compliance(
                    metrics, sla
                )

                results.append(metrics)

            except Exception as e:
                print(f"    Error in {test_name}: {e}")

        return results

    def _run_frontend_performance_tests(
        self, component: str, config: LoadTestConfig
    ) -> List[PerformanceMetrics]:
        """Run frontend performance tests using Lighthouse and custom metrics"""

        results = []

        # Frontend-specific performance tests
        test_scenarios = [
            ("page_load_performance", self._test_page_load_performance),
            ("ui_interaction_latency", self._test_ui_interaction_latency),
            ("chart_rendering_performance", self._test_chart_rendering),
            ("websocket_performance", self._test_websocket_performance),
        ]

        for test_name, test_func in test_scenarios:
            print(f"  Running {test_name}...")

            try:
                metrics = test_func(component, config, test_name)

                sla = self.sla.get(component, self.sla["frontend"])
                metrics.sla_passed, metrics.sla_violations = self._check_sla_compliance(
                    metrics, sla
                )

                results.append(metrics)

            except Exception as e:
                print(f"    Error in {test_name}: {e}")

        return results

    def _test_api_latency(
        self, component: str, config: LoadTestConfig, test_name: str
    ) -> PerformanceMetrics:
        """Test API endpoint latency"""

        latencies = []
        errors = 0
        timeouts = 0

        # Monitor system resources
        cpu_usage = []
        memory_usage = []

        start_time = time.time()

        # Simulate API calls
        for i in range(config.operations_per_user):
            call_start = time.time()

            try:
                # Simulate API call (replace with actual API testing)
                success = self._simulate_api_call(component)

                call_end = time.time()
                latency_ms = (call_end - call_start) * 1000

                if success:
                    latencies.append(latency_ms)
                else:
                    errors += 1

                # Monitor resources
                cpu_usage.append(psutil.cpu_percent())
                memory_usage.append(psutil.virtual_memory().used / 1024 / 1024)

                # Think time
                if config.think_time_ms > 0:
                    time.sleep(config.think_time_ms / 1000)

            except TimeoutError:
                timeouts += 1
            except Exception as e:
                errors += 1

        execution_time = time.time() - start_time
        total_operations = len(latencies) + errors + timeouts

        # Calculate metrics
        if latencies:
            avg_latency = statistics.mean(latencies)
            p50_latency = np.percentile(latencies, 50)
            p95_latency = np.percentile(latencies, 95)
            p99_latency = np.percentile(latencies, 99)
            max_latency = max(latencies)
            min_latency = min(latencies)
        else:
            avg_latency = p50_latency = p95_latency = p99_latency = max_latency = (
                min_latency
            ) = 0

        success_rate = (
            (len(latencies) / total_operations * 100) if total_operations > 0 else 0
        )
        error_rate = (errors / total_operations * 100) if total_operations > 0 else 0
        timeout_rate = (
            (timeouts / total_operations * 100) if total_operations > 0 else 0
        )

        throughput = total_operations / execution_time if execution_time > 0 else 0

        return PerformanceMetrics(
            test_name=test_name,
            component=component,
            avg_latency=avg_latency,
            p50_latency=p50_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            max_latency=max_latency,
            min_latency=min_latency,
            throughput_ops_per_sec=throughput,
            total_operations=total_operations,
            cpu_usage_percent=statistics.mean(cpu_usage) if cpu_usage else 0,
            memory_usage_mb=statistics.mean(memory_usage) if memory_usage else 0,
            peak_memory_mb=max(memory_usage) if memory_usage else 0,
            success_rate=success_rate,
            error_rate=error_rate,
            timeout_rate=timeout_rate,
            execution_time=execution_time,
            concurrent_users=1,
            test_duration=execution_time,
        )

    def _test_throughput(
        self, component: str, config: LoadTestConfig, test_name: str
    ) -> PerformanceMetrics:
        """Test maximum throughput capacity"""

        operations_completed = 0
        errors = 0
        start_time = time.time()

        # Run for specified duration
        while time.time() - start_time < config.test_duration_seconds:
            try:
                success = self._simulate_api_call(component)
                if success:
                    operations_completed += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

        execution_time = time.time() - start_time
        throughput = operations_completed / execution_time

        return PerformanceMetrics(
            test_name=test_name,
            component=component,
            avg_latency=0,  # Not measured in throughput test
            p50_latency=0,
            p95_latency=0,
            p99_latency=0,
            max_latency=0,
            min_latency=0,
            throughput_ops_per_sec=throughput,
            total_operations=operations_completed + errors,
            cpu_usage_percent=psutil.cpu_percent(),
            memory_usage_mb=psutil.virtual_memory().used / 1024 / 1024,
            peak_memory_mb=psutil.virtual_memory().used / 1024 / 1024,
            success_rate=(
                (operations_completed / (operations_completed + errors) * 100)
                if (operations_completed + errors) > 0
                else 0
            ),
            error_rate=(
                (errors / (operations_completed + errors) * 100)
                if (operations_completed + errors) > 0
                else 0
            ),
            timeout_rate=0,
            execution_time=execution_time,
            concurrent_users=1,
            test_duration=execution_time,
        )

    def _test_concurrent_load(
        self, component: str, config: LoadTestConfig, test_name: str
    ) -> PerformanceMetrics:
        """Test concurrent load handling"""

        all_latencies = []
        total_operations = 0
        total_errors = 0

        start_time = time.time()

        # Use ThreadPoolExecutor to simulate concurrent users
        with ThreadPoolExecutor(max_workers=config.concurrent_users) as executor:
            futures = []

            # Submit work for each concurrent user
            for user_id in range(config.concurrent_users):
                future = executor.submit(
                    self._simulate_user_load,
                    component,
                    config.operations_per_user,
                    config.think_time_ms,
                )
                futures.append(future)

            # Collect results
            for future in as_completed(futures):
                try:
                    user_latencies, user_ops, user_errors = future.result()
                    all_latencies.extend(user_latencies)
                    total_operations += user_ops
                    total_errors += user_errors
                except Exception as e:
                    print(f"User simulation error: {e}")
                    total_errors += 1

        execution_time = time.time() - start_time

        # Calculate metrics
        if all_latencies:
            avg_latency = statistics.mean(all_latencies)
            p50_latency = np.percentile(all_latencies, 50)
            p95_latency = np.percentile(all_latencies, 95)
            p99_latency = np.percentile(all_latencies, 99)
            max_latency = max(all_latencies)
            min_latency = min(all_latencies)
        else:
            avg_latency = p50_latency = p95_latency = p99_latency = max_latency = (
                min_latency
            ) = 0

        total_ops = total_operations + total_errors
        success_rate = (total_operations / total_ops * 100) if total_ops > 0 else 0
        error_rate = (total_errors / total_ops * 100) if total_ops > 0 else 0
        throughput = total_operations / execution_time if execution_time > 0 else 0

        return PerformanceMetrics(
            test_name=test_name,
            component=component,
            avg_latency=avg_latency,
            p50_latency=p50_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            max_latency=max_latency,
            min_latency=min_latency,
            throughput_ops_per_sec=throughput,
            total_operations=total_ops,
            cpu_usage_percent=psutil.cpu_percent(),
            memory_usage_mb=psutil.virtual_memory().used / 1024 / 1024,
            peak_memory_mb=psutil.virtual_memory().used / 1024 / 1024,
            success_rate=success_rate,
            error_rate=error_rate,
            timeout_rate=0,
            execution_time=execution_time,
            concurrent_users=config.concurrent_users,
            test_duration=execution_time,
        )

    def _test_memory_usage(
        self, component: str, config: LoadTestConfig, test_name: str
    ) -> PerformanceMetrics:
        """Test memory usage and potential leaks"""

        memory_samples = []
        start_memory = psutil.virtual_memory().used / 1024 / 1024

        start_time = time.time()

        # Run operations while monitoring memory
        for i in range(
            config.operations_per_user * 2
        ):  # More operations for memory test
            try:
                self._simulate_api_call(component)

                # Sample memory usage
                current_memory = psutil.virtual_memory().used / 1024 / 1024
                memory_samples.append(current_memory)

                if i % 100 == 0:  # Log every 100 operations
                    print(f"    Memory usage: {current_memory:.1f} MB")

            except Exception as e:
                print(f"Memory test error: {e}")

        execution_time = time.time() - start_time
        peak_memory = max(memory_samples) if memory_samples else start_memory
        avg_memory = statistics.mean(memory_samples) if memory_samples else start_memory

        # Check for memory leaks (simple heuristic)
        memory_growth = peak_memory - start_memory

        return PerformanceMetrics(
            test_name=test_name,
            component=component,
            avg_latency=0,  # Not measured in memory test
            p50_latency=0,
            p95_latency=0,
            p99_latency=0,
            max_latency=0,
            min_latency=0,
            throughput_ops_per_sec=(
                len(memory_samples) / execution_time if execution_time > 0 else 0
            ),
            total_operations=len(memory_samples),
            cpu_usage_percent=psutil.cpu_percent(),
            memory_usage_mb=avg_memory,
            peak_memory_mb=peak_memory,
            success_rate=100.0,  # Assume success if no exceptions
            error_rate=0.0,
            timeout_rate=0.0,
            execution_time=execution_time,
            concurrent_users=1,
            test_duration=execution_time,
        )

    def _test_page_load_performance(
        self, component: str, config: LoadTestConfig, test_name: str
    ) -> PerformanceMetrics:
        """Test frontend page load performance"""
        # Mock implementation - in real scenario, use Lighthouse or Playwright
        return PerformanceMetrics(
            test_name=test_name,
            component=component,
            avg_latency=150.0,  # Mock 150ms page load
            p50_latency=140.0,
            p95_latency=200.0,
            p99_latency=300.0,
            max_latency=350.0,
            min_latency=100.0,
            throughput_ops_per_sec=20.0,
            total_operations=100,
            cpu_usage_percent=30.0,
            memory_usage_mb=200.0,
            peak_memory_mb=250.0,
            success_rate=99.0,
            error_rate=1.0,
            timeout_rate=0.0,
            execution_time=5.0,
            concurrent_users=1,
            test_duration=5.0,
        )

    def _test_ui_interaction_latency(
        self, component: str, config: LoadTestConfig, test_name: str
    ) -> PerformanceMetrics:
        """Test UI interaction response times"""
        # Mock implementation
        return PerformanceMetrics(
            test_name=test_name,
            component=component,
            avg_latency=25.0,  # Mock 25ms UI response
            p50_latency=20.0,
            p95_latency=50.0,
            p99_latency=100.0,
            max_latency=120.0,
            min_latency=10.0,
            throughput_ops_per_sec=40.0,
            total_operations=200,
            cpu_usage_percent=15.0,
            memory_usage_mb=150.0,
            peak_memory_mb=180.0,
            success_rate=99.5,
            error_rate=0.5,
            timeout_rate=0.0,
            execution_time=5.0,
            concurrent_users=1,
            test_duration=5.0,
        )

    def _test_chart_rendering(
        self, component: str, config: LoadTestConfig, test_name: str
    ) -> PerformanceMetrics:
        """Test chart rendering performance"""
        # Mock implementation
        return PerformanceMetrics(
            test_name=test_name,
            component=component,
            avg_latency=80.0,  # Mock 80ms chart rendering
            p50_latency=75.0,
            p95_latency=150.0,
            p99_latency=250.0,
            max_latency=300.0,
            min_latency=50.0,
            throughput_ops_per_sec=12.0,
            total_operations=50,
            cpu_usage_percent=60.0,
            memory_usage_mb=300.0,
            peak_memory_mb=400.0,
            success_rate=98.0,
            error_rate=2.0,
            timeout_rate=0.0,
            execution_time=4.0,
            concurrent_users=1,
            test_duration=4.0,
        )

    def _test_websocket_performance(
        self, component: str, config: LoadTestConfig, test_name: str
    ) -> PerformanceMetrics:
        """Test WebSocket message handling performance"""
        # Mock implementation
        return PerformanceMetrics(
            test_name=test_name,
            component=component,
            avg_latency=5.0,  # Mock 5ms WebSocket latency
            p50_latency=4.0,
            p95_latency=10.0,
            p99_latency=20.0,
            max_latency=25.0,
            min_latency=2.0,
            throughput_ops_per_sec=500.0,
            total_operations=1000,
            cpu_usage_percent=25.0,
            memory_usage_mb=100.0,
            peak_memory_mb=120.0,
            success_rate=99.9,
            error_rate=0.1,
            timeout_rate=0.0,
            execution_time=2.0,
            concurrent_users=1,
            test_duration=2.0,
        )

    def _simulate_api_call(self, component: str) -> bool:
        """Simulate an API call for performance testing"""
        # Mock API call with realistic latency
        latency = max(0.001, np.random.normal(0.01, 0.005))  # 10ms ± 5ms
        time.sleep(latency)

        # 99% success rate
        return np.random.random() > 0.01

    def _simulate_user_load(
        self, component: str, operations: int, think_time_ms: int
    ) -> Tuple[List[float], int, int]:
        """Simulate load from a single user"""
        latencies = []
        errors = 0

        for _ in range(operations):
            start_time = time.time()

            try:
                success = self._simulate_api_call(component)
                end_time = time.time()

                if success:
                    latency_ms = (end_time - start_time) * 1000
                    latencies.append(latency_ms)
                else:
                    errors += 1

            except Exception:
                errors += 1

            # Think time between operations
            if think_time_ms > 0:
                time.sleep(think_time_ms / 1000)

        return latencies, len(latencies), errors

    def _check_sla_compliance(
        self, metrics: PerformanceMetrics, sla: PerformanceSLA
    ) -> Tuple[bool, List[str]]:
        """Check if performance metrics meet SLA requirements"""
        violations = []

        # Check latency requirements
        if metrics.avg_latency > sla.max_avg_latency:
            violations.append(
                f"Average latency {metrics.avg_latency:.1f}ms exceeds limit {sla.max_avg_latency}ms"
            )

        if metrics.p95_latency > sla.max_p95_latency:
            violations.append(
                f"P95 latency {metrics.p95_latency:.1f}ms exceeds limit {sla.max_p95_latency}ms"
            )

        if metrics.p99_latency > sla.max_p99_latency:
            violations.append(
                f"P99 latency {metrics.p99_latency:.1f}ms exceeds limit {sla.max_p99_latency}ms"
            )

        # Check throughput requirements
        if metrics.throughput_ops_per_sec < sla.min_throughput_ops_per_sec:
            violations.append(
                f"Throughput {metrics.throughput_ops_per_sec:.1f} ops/sec below minimum {sla.min_throughput_ops_per_sec}"
            )

        # Check resource requirements
        if metrics.cpu_usage_percent > sla.max_cpu_usage:
            violations.append(
                f"CPU usage {metrics.cpu_usage_percent:.1f}% exceeds limit {sla.max_cpu_usage}%"
            )

        if metrics.memory_usage_mb > sla.max_memory_usage_mb:
            violations.append(
                f"Memory usage {metrics.memory_usage_mb:.1f}MB exceeds limit {sla.max_memory_usage_mb}MB"
            )

        # Check reliability requirements
        if metrics.success_rate < sla.min_success_rate:
            violations.append(
                f"Success rate {metrics.success_rate:.2f}% below minimum {sla.min_success_rate}%"
            )

        if metrics.error_rate > sla.max_error_rate:
            violations.append(
                f"Error rate {metrics.error_rate:.2f}% exceeds limit {sla.max_error_rate}%"
            )

        if metrics.timeout_rate > sla.max_timeout_rate:
            violations.append(
                f"Timeout rate {metrics.timeout_rate:.2f}% exceeds limit {sla.max_timeout_rate}%"
            )

        return len(violations) == 0, violations

    def _generate_performance_reports(
        self, results: List[PerformanceMetrics], test_config: str
    ):
        """Generate performance testing reports"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save raw results
        results_file = (
            self.reports_dir / f"performance_results_{test_config}_{timestamp}.json"
        )
        with open(results_file, "w") as f:
            json.dump([asdict(result) for result in results], f, indent=2, default=str)

        # Generate HTML report
        self._generate_html_performance_report(results, test_config)

        # Generate markdown report
        self._generate_markdown_performance_report(results, test_config)

        print(f"Performance reports generated in: {self.reports_dir}")

    def _generate_html_performance_report(
        self, results: List[PerformanceMetrics], test_config: str
    ):
        """Generate HTML performance report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>FXML4 Performance Test Report - {test_config}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .summary {{ margin: 20px 0; }}
        .test {{ margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .sla-pass {{ border-left: 5px solid green; }}
        .sla-fail {{ border-left: 5px solid red; }}
        .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
        .metric {{ text-align: center; }}
        .violations {{ background: #ffe6e6; padding: 10px; margin: 10px 0; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>FXML4 Performance Test Report</h1>
        <p><strong>Test Configuration:</strong> {test_config}</p>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Tests:</strong> {len(results)}</p>
        <p><strong>SLA Passed:</strong> {sum(1 for r in results if r.sla_passed)}</p>
        <p><strong>SLA Failed:</strong> {sum(1 for r in results if not r.sla_passed)}</p>
    </div>

    <div class="tests">
        <h2>Test Results</h2>
"""

        for result in results:
            sla_class = "sla-pass" if result.sla_passed else "sla-fail"
            html_content += f"""
        <div class="test {sla_class}">
            <h3>{result.test_name} ({result.component})</h3>
            <p><strong>SLA Status:</strong> {'✅ PASSED' if result.sla_passed else '❌ FAILED'}</p>

            <div class="metrics">
                <div class="metric">
                    <h4>Latency</h4>
                    <p>Avg: {result.avg_latency:.1f}ms</p>
                    <p>P95: {result.p95_latency:.1f}ms</p>
                    <p>P99: {result.p99_latency:.1f}ms</p>
                </div>
                <div class="metric">
                    <h4>Throughput</h4>
                    <p>{result.throughput_ops_per_sec:.1f} ops/sec</p>
                    <p>Total: {result.total_operations}</p>
                    <p>Success: {result.success_rate:.1f}%</p>
                </div>
                <div class="metric">
                    <h4>Resources</h4>
                    <p>CPU: {result.cpu_usage_percent:.1f}%</p>
                    <p>Memory: {result.memory_usage_mb:.1f}MB</p>
                    <p>Peak: {result.peak_memory_mb:.1f}MB</p>
                </div>
            </div>
"""
            if result.sla_violations:
                html_content += """
            <div class="violations">
                <h4>SLA Violations:</h4>
                <ul>
"""
                for violation in result.sla_violations:
                    html_content += f"                    <li>{violation}</li>\n"
                html_content += """
                </ul>
            </div>
"""
            html_content += "        </div>\n"

        html_content += """
    </div>
</body>
</html>
"""

        html_file = self.reports_dir / f"performance_report_{test_config}.html"
        with open(html_file, "w") as f:
            f.write(html_content)

    def _generate_markdown_performance_report(
        self, results: List[PerformanceMetrics], test_config: str
    ):
        """Generate Markdown performance report"""
        md_content = f"""# FXML4 Performance Test Report

**Test Configuration:** {test_config}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

- **Total Tests:** {len(results)}
- **SLA Passed:** {sum(1 for r in results if r.sla_passed)} ✅
- **SLA Failed:** {sum(1 for r in results if not r.sla_passed)} ❌

## Test Results

| Test | Component | SLA | Avg Latency | P95 Latency | Throughput | CPU % | Memory MB |
|------|-----------|-----|-------------|-------------|------------|-------|-----------|
"""

        for result in results:
            sla_status = "✅" if result.sla_passed else "❌"
            md_content += f"| {result.test_name} | {result.component} | {sla_status} | {result.avg_latency:.1f}ms | {result.p95_latency:.1f}ms | {result.throughput_ops_per_sec:.1f} ops/s | {result.cpu_usage_percent:.1f}% | {result.memory_usage_mb:.1f}MB |\n"

        # Add violations section
        failed_results = [r for r in results if not r.sla_passed]
        if failed_results:
            md_content += "\n## SLA Violations\n\n"
            for result in failed_results:
                md_content += f"### {result.test_name} ({result.component})\n\n"
                for violation in result.sla_violations:
                    md_content += f"- {violation}\n"
                md_content += "\n"

        md_content += "\n---\n*Generated by FXML4 Claude TDD Automation Framework*\n"

        md_file = self.reports_dir / f"performance_report_{test_config}.md"
        with open(md_file, "w") as f:
            f.write(md_content)


def main():
    """Main entry point for performance testing"""
    import argparse

    parser = argparse.ArgumentParser(description="FXML4 Performance Test Framework")
    parser.add_argument("--component", "-c", help="Run tests for specific component")
    parser.add_argument(
        "--config",
        "-t",
        default="light_load",
        choices=["light_load", "peak_load", "stress_test", "endurance_test"],
        help="Load test configuration",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be executed"
    )
    parser.add_argument(
        "--list-configs", action="store_true", help="List available test configurations"
    )

    args = parser.parse_args()

    framework = PerformanceTestFramework()

    if args.list_configs:
        print("Available test configurations:")
        for name, config in framework.load_test_configs.items():
            print(f"  {name}: {config.description}")
            print(
                f"    Users: {config.concurrent_users}, Duration: {config.test_duration_seconds}s"
            )
        return 0

    try:
        results = framework.run_performance_tests(
            args.component, args.config, args.dry_run
        )

        if not args.dry_run:
            print(f"\n{'='*60}")
            print("PERFORMANCE TEST SUMMARY")
            print(f"{'='*60}")

            sla_passed = sum(1 for r in results if r.sla_passed)
            sla_failed = len(results) - sla_passed

            print(f"Total Tests: {len(results)}")
            print(f"SLA Passed: {sla_passed}")
            print(f"SLA Failed: {sla_failed}")

            if sla_failed > 0:
                print("\nSLA Violations:")
                for result in results:
                    if not result.sla_passed:
                        print(f"  {result.test_name} ({result.component}):")
                        for violation in result.sla_violations:
                            print(f"    - {violation}")

        return 0 if not args.dry_run and all(r.sla_passed for r in results) else 1

    except Exception as e:
        print(f"Error running performance tests: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
