#!/usr/bin/env python3
"""
Stress Test Runner for FXML4 High-Frequency Trading System

This script provides a command-line interface for running various stress test scenarios
against the FXML4 trading system. It supports different test profiles and generates
detailed performance reports.

Usage:
    python scripts/run_stress_tests.py --profile light
    python scripts/run_stress_tests.py --profile full --output report.json
    python scripts/run_stress_tests.py --custom --orders 500 --ticks 5000
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import stress testing framework
try:
    from tests.stress.test_high_frequency_trading_stress import (
        HighFrequencyStressTester,
        StressTestMetrics,
        SystemResourceMetrics,
    )

    STRESS_TEST_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Stress testing framework not available: {e}")
    STRESS_TEST_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class StressTestRunner:
    """High-level stress test runner with reporting capabilities."""

    def __init__(self):
        self.tester = HighFrequencyStressTester() if STRESS_TEST_AVAILABLE else None
        self.results: Dict[str, StressTestMetrics] = {}

    async def run_light_profile(self) -> Dict[str, StressTestMetrics]:
        """Run light stress test profile (CI-friendly)."""
        if not self.tester:
            raise RuntimeError("Stress testing framework not available")

        logger.info("Running light stress test profile...")

        # Light test parameters
        tests = {
            "order_submission": (100, 5),
            "market_data": (1000, 100),
            "risk_calculations": (100, 10),
            "signal_generation": (10, 2),
        }

        results = {}

        # Order submission stress
        logger.info("Testing order submission...")
        results["order_submission"] = await self.tester.stress_test_order_submission(
            *tests["order_submission"]
        )

        # Market data processing stress
        logger.info("Testing market data processing...")
        results["market_data"] = await self.tester.stress_test_market_data_processing(
            *tests["market_data"]
        )

        # Risk calculation stress
        logger.info("Testing risk calculations...")
        results["risk_calculations"] = await self.tester.stress_test_risk_calculations(
            *tests["risk_calculations"]
        )

        # Signal generation stress
        logger.info("Testing signal generation...")
        results["signal_generation"] = await self.tester.stress_test_signal_generation(
            *tests["signal_generation"]
        )

        self.results.update(results)
        return results

    async def run_full_profile(self) -> Dict[str, StressTestMetrics]:
        """Run full stress test profile (comprehensive)."""
        if not self.tester:
            raise RuntimeError("Stress testing framework not available")

        logger.info("Running full stress test profile...")

        # Full test parameters
        tests = {
            "order_submission": (1000, 10),
            "market_data": (10000, 1000),
            "risk_calculations": (1000, 50),
            "signal_generation": (100, 5),
        }

        results = {}

        # Order submission stress
        logger.info("Testing order submission (full scale)...")
        results["order_submission"] = await self.tester.stress_test_order_submission(
            *tests["order_submission"]
        )

        # Market data processing stress
        logger.info("Testing market data processing (full scale)...")
        results["market_data"] = await self.tester.stress_test_market_data_processing(
            *tests["market_data"]
        )

        # Risk calculation stress
        logger.info("Testing risk calculations (full scale)...")
        results["risk_calculations"] = await self.tester.stress_test_risk_calculations(
            *tests["risk_calculations"]
        )

        # Signal generation stress
        logger.info("Testing signal generation (full scale)...")
        results["signal_generation"] = await self.tester.stress_test_signal_generation(
            *tests["signal_generation"]
        )

        self.results.update(results)
        return results

    async def run_custom_tests(
        self,
        orders: int = 500,
        ticks: int = 5000,
        risk_calcs: int = 500,
        signals: int = 50,
        concurrent_orders: int = 10,
        concurrent_ticks: int = 500,
        concurrent_risk: int = 25,
        concurrent_signals: int = 3,
    ) -> Dict[str, StressTestMetrics]:
        """Run custom stress tests with specified parameters."""
        if not self.tester:
            raise RuntimeError("Stress testing framework not available")

        logger.info("Running custom stress tests...")

        results = {}

        if orders > 0:
            logger.info(
                f"Testing {orders} order submissions with {concurrent_orders} workers..."
            )
            results["order_submission"] = (
                await self.tester.stress_test_order_submission(
                    orders, concurrent_orders
                )
            )

        if ticks > 0:
            logger.info(
                f"Testing {ticks} market data ticks at {concurrent_ticks}/sec..."
            )
            results["market_data"] = (
                await self.tester.stress_test_market_data_processing(
                    ticks, concurrent_ticks
                )
            )

        if risk_calcs > 0:
            logger.info(
                f"Testing {risk_calcs} risk calculations with {concurrent_risk} positions..."
            )
            results["risk_calculations"] = (
                await self.tester.stress_test_risk_calculations(
                    risk_calcs, concurrent_risk
                )
            )

        if signals > 0:
            logger.info(
                f"Testing {signals} signal generations with {concurrent_signals} generators..."
            )
            results["signal_generation"] = (
                await self.tester.stress_test_signal_generation(
                    signals, concurrent_signals
                )
            )

        self.results.update(results)
        return results

    async def run_benchmark_suite(self) -> Dict[str, Any]:
        """Run comprehensive benchmark suite for performance baselines."""
        if not self.tester:
            raise RuntimeError("Stress testing framework not available")

        logger.info("Running benchmark suite...")

        # Benchmark scenarios with increasing load
        benchmark_results = {}

        # Order submission benchmarks
        order_scenarios = [
            (100, 5, "light"),
            (500, 10, "medium"),
            (1000, 15, "heavy"),
            (2000, 20, "extreme"),
        ]

        benchmark_results["order_submission"] = {}
        for orders, workers, scenario in order_scenarios:
            logger.info(
                f"Benchmarking order submission: {scenario} ({orders} orders, {workers} workers)"
            )
            metrics = await self.tester.stress_test_order_submission(orders, workers)
            benchmark_results["order_submission"][scenario] = metrics

        # Market data benchmarks
        data_scenarios = [
            (1000, 100, "light"),
            (5000, 500, "medium"),
            (10000, 1000, "heavy"),
            (20000, 2000, "extreme"),
        ]

        benchmark_results["market_data"] = {}
        for ticks, rate, scenario in data_scenarios:
            logger.info(
                f"Benchmarking market data: {scenario} ({ticks} ticks at {rate}/sec)"
            )
            metrics = await self.tester.stress_test_market_data_processing(ticks, rate)
            benchmark_results["market_data"][scenario] = metrics

        return benchmark_results

    def generate_report(
        self, output_file: Optional[str] = None, format: str = "json"
    ) -> Dict[str, Any]:
        """Generate comprehensive stress test report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "test_summary": {
                "total_tests": len(self.results),
                "test_names": list(self.results.keys()),
            },
            "results": {},
            "performance_analysis": {},
            "recommendations": [],
        }

        # Convert metrics to serializable format
        for test_name, metrics in self.results.items():
            report["results"][test_name] = {
                "total_operations": metrics.total_operations,
                "duration_seconds": metrics.duration_seconds,
                "operations_per_second": metrics.operations_per_second,
                "avg_latency_ms": metrics.avg_latency_ms,
                "p95_latency_ms": metrics.p95_latency_ms,
                "p99_latency_ms": metrics.p99_latency_ms,
                "error_rate": metrics.error_rate,
                "peak_memory_mb": metrics.peak_memory_mb,
                "peak_cpu_percent": metrics.peak_cpu_percent,
                "success_count": metrics.success_count,
                "error_count": metrics.error_count,
            }

        # Performance analysis
        self._analyze_performance(report)

        # Generate recommendations
        self._generate_recommendations(report)

        # Output report
        if output_file:
            if format.lower() == "json":
                with open(output_file, "w") as f:
                    json.dump(report, f, indent=2)
            elif format.lower() == "html":
                self._generate_html_report(report, output_file)

            logger.info(f"Report saved to {output_file}")

        return report

    def _analyze_performance(self, report: Dict[str, Any]):
        """Analyze performance metrics and add insights to report."""
        analysis = {}

        for test_name, results in report["results"].items():
            test_analysis = {}

            # Latency analysis
            if results["avg_latency_ms"] > 0:
                test_analysis["latency_grade"] = self._grade_latency(
                    test_name, results["avg_latency_ms"]
                )

            # Throughput analysis
            if results["operations_per_second"] > 0:
                test_analysis["throughput_grade"] = self._grade_throughput(
                    test_name, results["operations_per_second"]
                )

            # Error rate analysis
            test_analysis["error_grade"] = self._grade_error_rate(results["error_rate"])

            # Resource usage analysis
            test_analysis["resource_grade"] = self._grade_resource_usage(
                results["peak_memory_mb"], results["peak_cpu_percent"]
            )

            analysis[test_name] = test_analysis

        report["performance_analysis"] = analysis

    def _grade_latency(self, test_name: str, avg_latency: float) -> str:
        """Grade latency performance based on test type."""
        thresholds = {
            "order_submission": [50, 100, 200],
            "market_data": [5, 10, 20],
            "risk_calculations": [100, 200, 500],
            "signal_generation": [1000, 2000, 5000],
        }

        test_thresholds = thresholds.get(test_name, [100, 200, 500])

        if avg_latency <= test_thresholds[0]:
            return "A"
        elif avg_latency <= test_thresholds[1]:
            return "B"
        elif avg_latency <= test_thresholds[2]:
            return "C"
        else:
            return "D"

    def _grade_throughput(self, test_name: str, throughput: float) -> str:
        """Grade throughput performance based on test type."""
        thresholds = {
            "order_submission": [200, 100, 50],
            "market_data": [2000, 1000, 500],
            "risk_calculations": [20, 10, 5],
            "signal_generation": [2, 1, 0.5],
        }

        test_thresholds = thresholds.get(test_name, [100, 50, 25])

        if throughput >= test_thresholds[0]:
            return "A"
        elif throughput >= test_thresholds[1]:
            return "B"
        elif throughput >= test_thresholds[2]:
            return "C"
        else:
            return "D"

    def _grade_error_rate(self, error_rate: float) -> str:
        """Grade error rate performance."""
        if error_rate <= 0.001:
            return "A"
        elif error_rate <= 0.01:
            return "B"
        elif error_rate <= 0.05:
            return "C"
        else:
            return "D"

    def _grade_resource_usage(self, memory_mb: float, cpu_percent: float) -> str:
        """Grade resource usage performance."""
        memory_grade = (
            "A"
            if memory_mb < 500
            else "B" if memory_mb < 1000 else "C" if memory_mb < 2000 else "D"
        )
        cpu_grade = (
            "A"
            if cpu_percent < 50
            else "B" if cpu_percent < 70 else "C" if cpu_percent < 85 else "D"
        )

        # Return worst grade
        grades = {"A": 4, "B": 3, "C": 2, "D": 1}
        min_grade = min(grades[memory_grade], grades[cpu_grade])
        return {v: k for k, v in grades.items()}[min_grade]

    def _generate_recommendations(self, report: Dict[str, Any]):
        """Generate performance improvement recommendations."""
        recommendations = []

        for test_name, analysis in report["performance_analysis"].items():
            results = report["results"][test_name]

            # Latency recommendations
            if analysis.get("latency_grade", "A") in ["C", "D"]:
                recommendations.append(
                    f"HIGH: {test_name} latency is high ({results['avg_latency_ms']:.1f}ms). "
                    f"Consider optimizing processing pipeline or adding caching."
                )

            # Throughput recommendations
            if analysis.get("throughput_grade", "A") in ["C", "D"]:
                recommendations.append(
                    f"MEDIUM: {test_name} throughput is low ({results['operations_per_second']:.1f} ops/sec). "
                    f"Consider increasing concurrency or optimizing bottlenecks."
                )

            # Error rate recommendations
            if analysis.get("error_grade", "A") in ["C", "D"]:
                recommendations.append(
                    f"HIGH: {test_name} error rate is high ({results['error_rate']:.3f}). "
                    f"Investigate error causes and improve error handling."
                )

            # Resource recommendations
            if analysis.get("resource_grade", "A") in ["C", "D"]:
                recommendations.append(
                    f"MEDIUM: {test_name} resource usage is high "
                    f"(Memory: {results['peak_memory_mb']:.1f}MB, CPU: {results['peak_cpu_percent']:.1f}%). "
                    f"Consider memory optimization and CPU profiling."
                )

        # General recommendations
        if not recommendations:
            recommendations.append(
                "GOOD: All stress tests passed with acceptable performance!"
            )

        report["recommendations"] = recommendations

    def _generate_html_report(self, report: Dict[str, Any], output_file: str):
        """Generate HTML report (basic implementation)."""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FXML4 Stress Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ color: #333; border-bottom: 2px solid #007acc; }}
                .test-result {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; }}
                .grade-A {{ background-color: #d4edda; }}
                .grade-B {{ background-color: #fff3cd; }}
                .grade-C {{ background-color: #f8d7da; }}
                .grade-D {{ background-color: #f5c6cb; }}
                .recommendations {{ margin: 20px 0; padding: 15px; background-color: #e7f3ff; }}
            </style>
        </head>
        <body>
            <h1 class="header">FXML4 Stress Test Report</h1>
            <p>Generated: {report['timestamp']}</p>
            <p>Total Tests: {report['test_summary']['total_tests']}</p>

            <h2>Test Results</h2>
        """

        for test_name, results in report["results"].items():
            analysis = report["performance_analysis"].get(test_name, {})
            overall_grade = min(
                analysis.get("latency_grade", "A"),
                analysis.get("throughput_grade", "A"),
                analysis.get("error_grade", "A"),
                analysis.get("resource_grade", "A"),
                key=lambda x: {"A": 4, "B": 3, "C": 2, "D": 1}[x],
            )

            html_content += f"""
            <div class="test-result grade-{overall_grade}">
                <h3>{test_name.replace('_', ' ').title()} (Grade: {overall_grade})</h3>
                <ul>
                    <li>Operations: {results['total_operations']}</li>
                    <li>Duration: {results['duration_seconds']:.2f}s</li>
                    <li>Throughput: {results['operations_per_second']:.1f} ops/sec</li>
                    <li>Avg Latency: {results['avg_latency_ms']:.1f}ms</li>
                    <li>P95 Latency: {results['p95_latency_ms']:.1f}ms</li>
                    <li>Error Rate: {results['error_rate']:.3f}</li>
                    <li>Peak Memory: {results['peak_memory_mb']:.1f}MB</li>
                    <li>Peak CPU: {results['peak_cpu_percent']:.1f}%</li>
                </ul>
            </div>
            """

        html_content += f"""
            <h2>Recommendations</h2>
            <div class="recommendations">
                <ul>
        """

        for rec in report["recommendations"]:
            html_content += f"<li>{rec}</li>"

        html_content += """
                </ul>
            </div>
        </body>
        </html>
        """

        with open(output_file, "w") as f:
            f.write(html_content)

    def print_summary(self):
        """Print a summary of test results to console."""
        if not self.results:
            print("No test results available.")
            return

        print("\n" + "=" * 60)
        print("FXML4 STRESS TEST SUMMARY")
        print("=" * 60)

        for test_name, metrics in self.results.items():
            print(f"\n{test_name.replace('_', ' ').title()}:")
            print(f"  Operations:    {metrics.total_operations:,}")
            print(f"  Duration:      {metrics.duration_seconds:.2f}s")
            print(f"  Throughput:    {metrics.operations_per_second:.1f} ops/sec")
            print(f"  Avg Latency:   {metrics.avg_latency_ms:.1f}ms")
            print(f"  P95 Latency:   {metrics.p95_latency_ms:.1f}ms")
            print(f"  Error Rate:    {metrics.error_rate:.3f}")
            print(f"  Peak Memory:   {metrics.peak_memory_mb:.1f}MB")
            print(f"  Peak CPU:      {metrics.peak_cpu_percent:.1f}%")

        print("\n" + "=" * 60)


async def main():
    """Main entry point for stress test runner."""
    parser = argparse.ArgumentParser(
        description="FXML4 High-Frequency Trading Stress Test Runner"
    )

    parser.add_argument(
        "--profile",
        choices=["light", "full", "benchmark"],
        help="Predefined test profile to run",
    )

    parser.add_argument(
        "--custom",
        action="store_true",
        help="Run custom stress tests with specified parameters",
    )

    parser.add_argument(
        "--orders", type=int, default=500, help="Number of orders for custom test"
    )
    parser.add_argument(
        "--ticks", type=int, default=5000, help="Number of ticks for custom test"
    )
    parser.add_argument(
        "--risk-calcs", type=int, default=500, help="Number of risk calculations"
    )
    parser.add_argument(
        "--signals", type=int, default=50, help="Number of signals to generate"
    )

    parser.add_argument(
        "--concurrent-orders", type=int, default=10, help="Concurrent order workers"
    )
    parser.add_argument(
        "--concurrent-ticks", type=int, default=500, help="Ticks per second rate"
    )
    parser.add_argument(
        "--concurrent-risk", type=int, default=25, help="Concurrent risk positions"
    )
    parser.add_argument(
        "--concurrent-signals", type=int, default=3, help="Concurrent signal generators"
    )

    parser.add_argument("--output", help="Output file for detailed report")
    parser.add_argument(
        "--format", choices=["json", "html"], default="json", help="Report format"
    )

    args = parser.parse_args()

    if not STRESS_TEST_AVAILABLE:
        print("Error: Stress testing framework not available. Please check imports.")
        sys.exit(1)

    runner = StressTestRunner()

    try:
        # Run tests based on arguments
        if args.profile == "light":
            await runner.run_light_profile()
        elif args.profile == "full":
            await runner.run_full_profile()
        elif args.profile == "benchmark":
            await runner.run_benchmark_suite()
        elif args.custom:
            await runner.run_custom_tests(
                orders=args.orders,
                ticks=args.ticks,
                risk_calcs=args.risk_calcs,
                signals=args.signals,
                concurrent_orders=args.concurrent_orders,
                concurrent_ticks=args.concurrent_ticks,
                concurrent_risk=args.concurrent_risk,
                concurrent_signals=args.concurrent_signals,
            )
        else:
            print("Please specify --profile or --custom")
            sys.exit(1)

        # Generate and display results
        runner.print_summary()

        if args.output:
            runner.generate_report(args.output, args.format)

    except Exception as e:
        logger.error(f"Stress test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
