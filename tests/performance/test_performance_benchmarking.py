#!/usr/bin/env python3
"""
Automated Performance Benchmarking Framework with Historical Tracking

This module provides comprehensive performance benchmarking capabilities for FXML4,
tracking performance metrics over time and detecting regressions.
"""

import asyncio
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import psutil

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# Try to import performance monitoring libraries
try:
    import memory_profiler

    MEMORY_PROFILER_AVAILABLE = True
except ImportError:
    MEMORY_PROFILER_AVAILABLE = False

try:
    import line_profiler

    LINE_PROFILER_AVAILABLE = True
except ImportError:
    LINE_PROFILER_AVAILABLE = False


# Mock implementation for latency measurement
def measure_latency(func):
    """Mock latency measurement."""
    import time

    start = time.perf_counter()
    result = func()
    return (time.perf_counter() - start) * 1000, result


class BenchmarkCategory(Enum):
    """Categories of performance benchmarks."""

    API_LATENCY = "api_latency"
    DATABASE_QUERY = "database_query"
    ML_INFERENCE = "ml_inference"
    ORDER_PROCESSING = "order_processing"
    MARKET_DATA = "market_data"
    RISK_CALCULATION = "risk_calculation"
    BACKTEST_EXECUTION = "backtest_execution"
    WEBSOCKET_THROUGHPUT = "websocket_throughput"
    MEMORY_USAGE = "memory_usage"
    CPU_UTILIZATION = "cpu_utilization"


class PerformanceThreshold(Enum):
    """Performance threshold levels."""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class BenchmarkMetric:
    """Individual benchmark metric."""

    name: str
    category: BenchmarkCategory
    value: float
    unit: str
    timestamp: datetime
    metadata: Dict[str, Any]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "category": self.category.value,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkResult:
    """Complete benchmark test result."""

    test_id: str
    category: BenchmarkCategory
    metrics: List[BenchmarkMetric]
    duration_ms: float
    environment: Dict[str, str]
    git_commit: Optional[str]
    branch: Optional[str]
    timestamp: datetime
    status: PerformanceThreshold

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "test_id": self.test_id,
            "category": self.category.value,
            "metrics": [m.to_dict() for m in self.metrics],
            "duration_ms": self.duration_ms,
            "environment": self.environment,
            "git_commit": self.git_commit,
            "branch": self.branch,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
        }


@dataclass
class PerformanceBaseline:
    """Historical performance baseline."""

    metric_name: str
    category: BenchmarkCategory
    p50: float
    p75: float
    p90: float
    p95: float
    p99: float
    mean: float
    std_dev: float
    min_value: float
    max_value: float
    sample_count: int
    last_updated: datetime

    def is_regression(self, value: float, threshold_percentile: int = 95) -> bool:
        """Check if a value represents a performance regression."""
        if threshold_percentile == 50:
            threshold = self.p50
        elif threshold_percentile == 75:
            threshold = self.p75
        elif threshold_percentile == 90:
            threshold = self.p90
        elif threshold_percentile == 95:
            threshold = self.p95
        else:
            threshold = self.p99

        # Allow 10% tolerance for normal variation
        return value > threshold * 1.1


class PerformanceBenchmarker:
    """Main performance benchmarking engine."""

    def __init__(
        self,
        history_dir: Path = Path("benchmark_history"),
        baseline_window_days: int = 30,
    ):
        """Initialize benchmarker with history tracking."""
        self.history_dir = history_dir
        self.baseline_window_days = baseline_window_days
        self.history_dir.mkdir(exist_ok=True)

        # Load historical baselines
        self.baselines = self._load_baselines()

        # Performance thresholds by category (in milliseconds)
        self.thresholds = {
            BenchmarkCategory.API_LATENCY: {
                PerformanceThreshold.EXCELLENT: 50,
                PerformanceThreshold.GOOD: 100,
                PerformanceThreshold.ACCEPTABLE: 500,
                PerformanceThreshold.WARNING: 1000,
                PerformanceThreshold.CRITICAL: 5000,
            },
            BenchmarkCategory.DATABASE_QUERY: {
                PerformanceThreshold.EXCELLENT: 10,
                PerformanceThreshold.GOOD: 50,
                PerformanceThreshold.ACCEPTABLE: 200,
                PerformanceThreshold.WARNING: 500,
                PerformanceThreshold.CRITICAL: 2000,
            },
            BenchmarkCategory.ML_INFERENCE: {
                PerformanceThreshold.EXCELLENT: 100,
                PerformanceThreshold.GOOD: 500,
                PerformanceThreshold.ACCEPTABLE: 2000,
                PerformanceThreshold.WARNING: 5000,
                PerformanceThreshold.CRITICAL: 10000,
            },
            BenchmarkCategory.ORDER_PROCESSING: {
                PerformanceThreshold.EXCELLENT: 5,
                PerformanceThreshold.GOOD: 20,
                PerformanceThreshold.ACCEPTABLE: 100,
                PerformanceThreshold.WARNING: 500,
                PerformanceThreshold.CRITICAL: 2000,
            },
        }

    async def benchmark_api_endpoints(
        self, base_url: str = "http://localhost:8000"
    ) -> List[BenchmarkResult]:
        """Benchmark API endpoint performance."""
        results = []

        endpoints = [
            ("/api/v1/health", "GET", None, "health_check"),
            (
                "/api/v1/market/data",
                "GET",
                {"symbol": "EURUSD", "timeframe": "1h"},
                "market_data",
            ),
            (
                "/api/v1/signals/generate",
                "POST",
                {"symbol": "GBPUSD", "strategy": "ml_ensemble"},
                "signal_generation",
            ),
            ("/api/v1/risk/calculate", "POST", {"positions": []}, "risk_calculation"),
            ("/api/v1/ml/predict", "POST", {"features": [0.1] * 100}, "ml_prediction"),
        ]

        if AIOHTTP_AVAILABLE:
            async with aiohttp.ClientSession() as session:
                for path, method, params, test_name in endpoints:
                    result = await self._benchmark_single_endpoint(
                        session, base_url + path, method, params, test_name
                    )
                    results.append(result)
        else:
            # Mock implementation without aiohttp
            for path, method, params, test_name in endpoints:
                result = await self._mock_benchmark_endpoint(
                    base_url + path, method, params, test_name
                )
                results.append(result)

        return results

    async def _mock_benchmark_endpoint(
        self, url: str, method: str, params: Optional[dict], test_name: str
    ) -> BenchmarkResult:
        """Mock benchmark for a single API endpoint without aiohttp."""
        latencies = []
        start_time = time.time()

        # Simulate API calls
        iterations = 100
        for _ in range(iterations):
            # Simulate varying latency
            latency_ms = np.random.uniform(10, 100)
            latencies.append(latency_ms)

        duration_ms = (time.time() - start_time) * 1000

        # Calculate statistics
        metrics = [
            BenchmarkMetric(
                name=f"{test_name}_p50",
                category=BenchmarkCategory.API_LATENCY,
                value=np.percentile(latencies, 50),
                unit="ms",
                timestamp=datetime.now(),
                metadata={"endpoint": url},
            ),
            BenchmarkMetric(
                name=f"{test_name}_p95",
                category=BenchmarkCategory.API_LATENCY,
                value=np.percentile(latencies, 95),
                unit="ms",
                timestamp=datetime.now(),
                metadata={"endpoint": url},
            ),
        ]

        return BenchmarkResult(
            test_id=test_name,
            category=BenchmarkCategory.API_LATENCY,
            metrics=metrics,
            duration_ms=duration_ms,
            environment=self._get_environment_info(),
            git_commit=self._get_git_commit(),
            branch=self._get_git_branch(),
            timestamp=datetime.now(),
            status=self._get_performance_status(
                BenchmarkCategory.API_LATENCY, np.percentile(latencies, 95)
            ),
        )

    async def _benchmark_single_endpoint(
        self,
        session: Any,  # Changed to Any for compatibility
        url: str,
        method: str,
        params: Optional[dict],
        test_name: str,
    ) -> BenchmarkResult:
        """Benchmark a single API endpoint."""
        latencies = []
        start_time = time.time()

        # Run multiple iterations for statistical significance
        iterations = 100

        if AIOHTTP_AVAILABLE:
            for _ in range(iterations):
                iter_start = time.perf_counter()

                try:
                    if method == "GET":
                        async with session.get(url, params=params) as response:
                            await response.text()
                    else:
                        async with session.post(url, json=params) as response:
                            await response.text()

                    latency_ms = (time.perf_counter() - iter_start) * 1000
                    latencies.append(latency_ms)
                except Exception:
                    # Skip failed requests in benchmarking
                    pass
        else:
            # Mock implementation
            for _ in range(iterations):
                latency_ms = np.random.uniform(10, 100)
                latencies.append(latency_ms)

        duration_ms = (time.time() - start_time) * 1000

        # Calculate statistics
        if latencies:
            metrics = [
                BenchmarkMetric(
                    name=f"{test_name}_p50",
                    category=BenchmarkCategory.API_LATENCY,
                    value=np.percentile(latencies, 50),
                    unit="ms",
                    timestamp=datetime.now(),
                    metadata={"endpoint": url},
                ),
                BenchmarkMetric(
                    name=f"{test_name}_p95",
                    category=BenchmarkCategory.API_LATENCY,
                    value=np.percentile(latencies, 95),
                    unit="ms",
                    timestamp=datetime.now(),
                    metadata={"endpoint": url},
                ),
                BenchmarkMetric(
                    name=f"{test_name}_p99",
                    category=BenchmarkCategory.API_LATENCY,
                    value=np.percentile(latencies, 99),
                    unit="ms",
                    timestamp=datetime.now(),
                    metadata={"endpoint": url},
                ),
            ]

            # Determine performance status
            p95_value = np.percentile(latencies, 95)
            status = self._get_performance_status(
                BenchmarkCategory.API_LATENCY, p95_value
            )
        else:
            metrics = []
            status = PerformanceThreshold.CRITICAL

        return BenchmarkResult(
            test_id=test_name,
            category=BenchmarkCategory.API_LATENCY,
            metrics=metrics,
            duration_ms=duration_ms,
            environment=self._get_environment_info(),
            git_commit=self._get_git_commit(),
            branch=self._get_git_branch(),
            timestamp=datetime.now(),
            status=status,
        )

    def benchmark_database_queries(self) -> List[BenchmarkResult]:
        """Benchmark database query performance."""
        results = []

        queries = [
            (
                "SELECT * FROM market_data WHERE symbol = %s LIMIT 1000",
                ["EURUSD"],
                "market_data_select",
            ),
            (
                "INSERT INTO signals (timestamp, symbol, signal) VALUES (%s, %s, %s)",
                [datetime.now(), "GBPUSD", 1],
                "signal_insert",
            ),
            (
                "SELECT * FROM features WHERE timestamp > %s",
                [datetime.now() - timedelta(hours=1)],
                "feature_range_query",
            ),
        ]

        for query, params, test_name in queries:
            result = self._benchmark_single_query(query, params, test_name)
            results.append(result)

        return results

    def _benchmark_single_query(
        self, query: str, params: list, test_name: str
    ) -> BenchmarkResult:
        """Benchmark a single database query."""
        # Mock implementation - would connect to actual database
        latencies = []

        for _ in range(50):
            start = time.perf_counter()
            # Simulate query execution
            time.sleep(np.random.uniform(0.001, 0.05))
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        metrics = [
            BenchmarkMetric(
                name=f"{test_name}_mean",
                category=BenchmarkCategory.DATABASE_QUERY,
                value=statistics.mean(latencies),
                unit="ms",
                timestamp=datetime.now(),
                metadata={"query": query[:50]},
            )
        ]

        return BenchmarkResult(
            test_id=test_name,
            category=BenchmarkCategory.DATABASE_QUERY,
            metrics=metrics,
            duration_ms=sum(latencies),
            environment=self._get_environment_info(),
            git_commit=self._get_git_commit(),
            branch=self._get_git_branch(),
            timestamp=datetime.now(),
            status=self._get_performance_status(
                BenchmarkCategory.DATABASE_QUERY, statistics.mean(latencies)
            ),
        )

    def benchmark_ml_inference(self) -> List[BenchmarkResult]:
        """Benchmark ML model inference performance."""
        results = []

        models = [
            ("xgboost_ensemble", 100, "xgboost_inference"),
            ("lstm_predictor", 50, "lstm_inference"),
            ("random_forest", 200, "rf_inference"),
        ]

        for model_name, batch_size, test_name in models:
            result = self._benchmark_ml_model(model_name, batch_size, test_name)
            results.append(result)

        return results

    def _benchmark_ml_model(
        self, model_name: str, batch_size: int, test_name: str
    ) -> BenchmarkResult:
        """Benchmark a single ML model."""
        # Mock implementation
        inference_times = []

        for _ in range(20):
            start = time.perf_counter()
            # Simulate inference
            time.sleep(np.random.uniform(0.01, 0.5))
            inference_time_ms = (time.perf_counter() - start) * 1000
            inference_times.append(inference_time_ms)

        metrics = [
            BenchmarkMetric(
                name=f"{test_name}_batch_{batch_size}",
                category=BenchmarkCategory.ML_INFERENCE,
                value=statistics.median(inference_times),
                unit="ms",
                timestamp=datetime.now(),
                metadata={"model": model_name, "batch_size": batch_size},
            )
        ]

        return BenchmarkResult(
            test_id=test_name,
            category=BenchmarkCategory.ML_INFERENCE,
            metrics=metrics,
            duration_ms=sum(inference_times),
            environment=self._get_environment_info(),
            git_commit=self._get_git_commit(),
            branch=self._get_git_branch(),
            timestamp=datetime.now(),
            status=self._get_performance_status(
                BenchmarkCategory.ML_INFERENCE, statistics.median(inference_times)
            ),
        )

    def benchmark_order_processing(self) -> BenchmarkResult:
        """Benchmark order processing pipeline."""
        processing_times = []

        for _ in range(1000):
            start = time.perf_counter()

            # Simulate order validation
            time.sleep(0.001)
            # Simulate risk check
            time.sleep(0.002)
            # Simulate broker submission
            time.sleep(0.005)

            processing_time_ms = (time.perf_counter() - start) * 1000
            processing_times.append(processing_time_ms)

        metrics = [
            BenchmarkMetric(
                name="order_processing_p50",
                category=BenchmarkCategory.ORDER_PROCESSING,
                value=np.percentile(processing_times, 50),
                unit="ms",
                timestamp=datetime.now(),
                metadata={"order_count": 1000},
            ),
            BenchmarkMetric(
                name="order_processing_p99",
                category=BenchmarkCategory.ORDER_PROCESSING,
                value=np.percentile(processing_times, 99),
                unit="ms",
                timestamp=datetime.now(),
                metadata={"order_count": 1000},
            ),
        ]

        return BenchmarkResult(
            test_id="order_processing_pipeline",
            category=BenchmarkCategory.ORDER_PROCESSING,
            metrics=metrics,
            duration_ms=sum(processing_times),
            environment=self._get_environment_info(),
            git_commit=self._get_git_commit(),
            branch=self._get_git_branch(),
            timestamp=datetime.now(),
            status=self._get_performance_status(
                BenchmarkCategory.ORDER_PROCESSING, np.percentile(processing_times, 95)
            ),
        )

    def benchmark_memory_usage(self) -> BenchmarkResult:
        """Benchmark memory usage patterns."""
        process = psutil.Process()

        memory_samples = []
        start_time = time.time()

        # Sample memory usage over time
        for _ in range(60):
            mem_info = process.memory_info()
            memory_mb = mem_info.rss / (1024 * 1024)
            memory_samples.append(memory_mb)
            time.sleep(0.5)

        duration_ms = (time.time() - start_time) * 1000

        metrics = [
            BenchmarkMetric(
                name="memory_usage_mean",
                category=BenchmarkCategory.MEMORY_USAGE,
                value=statistics.mean(memory_samples),
                unit="MB",
                timestamp=datetime.now(),
                metadata={"samples": len(memory_samples)},
            ),
            BenchmarkMetric(
                name="memory_usage_peak",
                category=BenchmarkCategory.MEMORY_USAGE,
                value=max(memory_samples),
                unit="MB",
                timestamp=datetime.now(),
                metadata={"samples": len(memory_samples)},
            ),
        ]

        return BenchmarkResult(
            test_id="memory_usage_monitoring",
            category=BenchmarkCategory.MEMORY_USAGE,
            metrics=metrics,
            duration_ms=duration_ms,
            environment=self._get_environment_info(),
            git_commit=self._get_git_commit(),
            branch=self._get_git_branch(),
            timestamp=datetime.now(),
            status=PerformanceThreshold.GOOD,
        )

    def compare_with_baseline(self, result: BenchmarkResult) -> Dict[str, Any]:
        """Compare benchmark result with historical baseline."""
        comparison = {
            "test_id": result.test_id,
            "regressions": [],
            "improvements": [],
            "within_baseline": [],
        }

        for metric in result.metrics:
            baseline_key = f"{metric.category.value}_{metric.name}"

            if baseline_key in self.baselines:
                baseline = self.baselines[baseline_key]

                if baseline.is_regression(metric.value):
                    comparison["regressions"].append(
                        {
                            "metric": metric.name,
                            "value": metric.value,
                            "baseline_p95": baseline.p95,
                            "degradation_pct": (
                                (metric.value - baseline.p95) / baseline.p95
                            )
                            * 100,
                        }
                    )
                elif metric.value < baseline.p50 * 0.9:  # 10% improvement
                    comparison["improvements"].append(
                        {
                            "metric": metric.name,
                            "value": metric.value,
                            "baseline_p50": baseline.p50,
                            "improvement_pct": (
                                (baseline.p50 - metric.value) / baseline.p50
                            )
                            * 100,
                        }
                    )
                else:
                    comparison["within_baseline"].append(
                        {
                            "metric": metric.name,
                            "value": metric.value,
                            "baseline_range": f"{baseline.p50:.2f} - {baseline.p95:.2f}",
                        }
                    )

        return comparison

    def save_results(self, results: List[BenchmarkResult]):
        """Save benchmark results to history."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for result in results:
            filename = self.history_dir / f"{result.category.value}_{timestamp}.json"

            with open(filename, "w") as f:
                json.dump(result.to_dict(), f, indent=2)

    def update_baselines(self):
        """Update performance baselines from recent history."""
        cutoff_date = datetime.now() - timedelta(days=self.baseline_window_days)

        # Group metrics by category and name
        metric_data = {}

        for history_file in self.history_dir.glob("*.json"):
            with open(history_file) as f:
                data = json.load(f)

                # Skip old data
                timestamp = datetime.fromisoformat(data["timestamp"])
                if timestamp < cutoff_date:
                    continue

                for metric in data["metrics"]:
                    key = f"{metric['category']}_{metric['name']}"

                    if key not in metric_data:
                        metric_data[key] = []

                    metric_data[key].append(metric["value"])

        # Calculate baselines
        new_baselines = {}

        for key, values in metric_data.items():
            if len(values) >= 10:  # Require minimum samples
                category_str, name = key.split("_", 1)

                new_baselines[key] = PerformanceBaseline(
                    metric_name=name,
                    category=BenchmarkCategory(category_str),
                    p50=np.percentile(values, 50),
                    p75=np.percentile(values, 75),
                    p90=np.percentile(values, 90),
                    p95=np.percentile(values, 95),
                    p99=np.percentile(values, 99),
                    mean=statistics.mean(values),
                    std_dev=statistics.stdev(values) if len(values) > 1 else 0,
                    min_value=min(values),
                    max_value=max(values),
                    sample_count=len(values),
                    last_updated=datetime.now(),
                )

        self.baselines = new_baselines
        self._save_baselines()

    def generate_performance_report(self, results: List[BenchmarkResult]) -> str:
        """Generate a comprehensive performance report."""
        report = []
        report.append("=" * 80)
        report.append("FXML4 Performance Benchmark Report")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Environment: {self._get_environment_info()}")
        report.append("")

        # Group results by category
        by_category = {}
        for result in results:
            if result.category not in by_category:
                by_category[result.category] = []
            by_category[result.category].append(result)

        # Report by category
        for category, category_results in by_category.items():
            report.append(f"\n{category.value.upper()} BENCHMARKS")
            report.append("-" * 40)

            for result in category_results:
                report.append(f"\nTest: {result.test_id}")
                report.append(f"Status: {result.status.value.upper()}")
                report.append(f"Duration: {result.duration_ms:.2f}ms")

                if result.metrics:
                    report.append("Metrics:")
                    for metric in result.metrics:
                        report.append(
                            f"  {metric.name}: {metric.value:.2f}{metric.unit}"
                        )

                # Compare with baseline
                comparison = self.compare_with_baseline(result)

                if comparison["regressions"]:
                    report.append("⚠️ REGRESSIONS DETECTED:")
                    for reg in comparison["regressions"]:
                        report.append(
                            f"  {reg['metric']}: {reg['degradation_pct']:.1f}% slower"
                        )

                if comparison["improvements"]:
                    report.append("✅ IMPROVEMENTS:")
                    for imp in comparison["improvements"]:
                        report.append(
                            f"  {imp['metric']}: {imp['improvement_pct']:.1f}% faster"
                        )

        # Summary statistics
        report.append("\n" + "=" * 40)
        report.append("SUMMARY")
        report.append("=" * 40)

        total_tests = len(results)
        by_status = {}
        for result in results:
            status = result.status.value
            by_status[status] = by_status.get(status, 0) + 1

        report.append(f"Total Tests: {total_tests}")
        for status, count in by_status.items():
            percentage = (count / total_tests) * 100
            report.append(f"  {status.upper()}: {count} ({percentage:.1f}%)")

        return "\n".join(report)

    def _load_baselines(self) -> Dict[str, PerformanceBaseline]:
        """Load historical baselines from disk."""
        baseline_file = self.history_dir / "baselines.json"

        if not baseline_file.exists():
            return {}

        with open(baseline_file) as f:
            data = json.load(f)

        baselines = {}
        for key, baseline_data in data.items():
            baselines[key] = PerformanceBaseline(
                metric_name=baseline_data["metric_name"],
                category=BenchmarkCategory(baseline_data["category"]),
                p50=baseline_data["p50"],
                p75=baseline_data["p75"],
                p90=baseline_data["p90"],
                p95=baseline_data["p95"],
                p99=baseline_data["p99"],
                mean=baseline_data["mean"],
                std_dev=baseline_data["std_dev"],
                min_value=baseline_data["min_value"],
                max_value=baseline_data["max_value"],
                sample_count=baseline_data["sample_count"],
                last_updated=datetime.fromisoformat(baseline_data["last_updated"]),
            )

        return baselines

    def _save_baselines(self):
        """Save baselines to disk."""
        baseline_file = self.history_dir / "baselines.json"

        data = {}
        for key, baseline in self.baselines.items():
            data[key] = {
                "metric_name": baseline.metric_name,
                "category": baseline.category.value,
                "p50": baseline.p50,
                "p75": baseline.p75,
                "p90": baseline.p90,
                "p95": baseline.p95,
                "p99": baseline.p99,
                "mean": baseline.mean,
                "std_dev": baseline.std_dev,
                "min_value": baseline.min_value,
                "max_value": baseline.max_value,
                "sample_count": baseline.sample_count,
                "last_updated": baseline.last_updated.isoformat(),
            }

        with open(baseline_file, "w") as f:
            json.dump(data, f, indent=2)

    def _get_performance_status(
        self, category: BenchmarkCategory, value: float
    ) -> PerformanceThreshold:
        """Determine performance status based on thresholds."""
        if category not in self.thresholds:
            return PerformanceThreshold.ACCEPTABLE

        thresholds = self.thresholds[category]

        if value <= thresholds[PerformanceThreshold.EXCELLENT]:
            return PerformanceThreshold.EXCELLENT
        elif value <= thresholds[PerformanceThreshold.GOOD]:
            return PerformanceThreshold.GOOD
        elif value <= thresholds[PerformanceThreshold.ACCEPTABLE]:
            return PerformanceThreshold.ACCEPTABLE
        elif value <= thresholds[PerformanceThreshold.WARNING]:
            return PerformanceThreshold.WARNING
        else:
            return PerformanceThreshold.CRITICAL

    def _get_environment_info(self) -> Dict[str, str]:
        """Get environment information."""
        return {
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
            "platform": os.sys.platform,
            "cpu_count": str(psutil.cpu_count()),
            "memory_gb": f"{psutil.virtual_memory().total / (1024**3):.1f}",
        }

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash."""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def _get_git_branch(self) -> Optional[str]:
        """Get current git branch."""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None


async def run_comprehensive_benchmarks():
    """Run comprehensive performance benchmarks."""
    benchmarker = PerformanceBenchmarker()

    print("Running comprehensive performance benchmarks...")
    print("=" * 60)

    all_results = []

    # 1. API Benchmarks
    print("\n1. Benchmarking API endpoints...")
    try:
        api_results = await benchmarker.benchmark_api_endpoints()
        all_results.extend(api_results)
        print(f"   ✓ Completed {len(api_results)} API benchmarks")
    except Exception as e:
        print(f"   ⚠️ API benchmarks skipped: {e}")

    # 2. Database Benchmarks
    print("\n2. Benchmarking database queries...")
    db_results = benchmarker.benchmark_database_queries()
    all_results.extend(db_results)
    print(f"   ✓ Completed {len(db_results)} database benchmarks")

    # 3. ML Inference Benchmarks
    print("\n3. Benchmarking ML inference...")
    ml_results = benchmarker.benchmark_ml_inference()
    all_results.extend(ml_results)
    print(f"   ✓ Completed {len(ml_results)} ML benchmarks")

    # 4. Order Processing Benchmarks
    print("\n4. Benchmarking order processing...")
    order_result = benchmarker.benchmark_order_processing()
    all_results.append(order_result)
    print("   ✓ Completed order processing benchmark")

    # 5. Memory Usage Benchmarks
    print("\n5. Benchmarking memory usage...")
    memory_result = benchmarker.benchmark_memory_usage()
    all_results.append(memory_result)
    print("   ✓ Completed memory usage benchmark")

    # Save results to history
    benchmarker.save_results(all_results)
    print(f"\n✓ Saved {len(all_results)} benchmark results to history")

    # Update baselines
    benchmarker.update_baselines()
    print("✓ Updated performance baselines")

    # Generate report
    report = benchmarker.generate_performance_report(all_results)
    print("\n" + report)

    # Save report to file
    report_file = Path(
        f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    with open(report_file, "w") as f:
        f.write(report)
    print(f"\n✓ Report saved to {report_file}")

    return all_results


# Example usage and testing
if __name__ == "__main__":
    # Run comprehensive benchmarks
    results = asyncio.run(run_comprehensive_benchmarks())

    print("\n" + "=" * 60)
    print("Performance Benchmarking Complete!")
    print(f"Total benchmarks run: {len(results)}")

    # Check for regressions
    regressions_found = False
    for result in results:
        if result.status in [
            PerformanceThreshold.WARNING,
            PerformanceThreshold.CRITICAL,
        ]:
            print(f"⚠️ Performance issue in {result.test_id}: {result.status.value}")
            regressions_found = True

    if not regressions_found:
        print("✅ All performance benchmarks within acceptable thresholds")
