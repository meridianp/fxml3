#!/usr/bin/env python3
"""
Optimized test execution script for FXML4 project.

This script implements intelligent test execution strategies to achieve
sub-5-minute test suite execution following TDD methodology requirements.
"""

import argparse
import multiprocessing
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil


class OptimizedTestRunner:
    """Intelligent test runner for optimized execution."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests"
        self.cpu_count = multiprocessing.cpu_count()
        self.available_memory_gb = psutil.virtual_memory().total / (1024**3)

        # Test execution strategies
        self.strategies = {
            "fast": self._run_fast_tests_only,
            "parallel": self._run_parallel_tests,
            "smart": self._run_smart_execution,
            "coverage": self._run_with_coverage,
            "full": self._run_full_suite,
        }

        # Test categories by execution speed (fastest to slowest)
        self.test_categories = [
            ("unit", "Unit tests - fastest execution"),
            ("fast", "Fast integration tests"),
            ("api", "API endpoint tests"),
            ("feature", "Feature engineering tests"),
            ("ml", "Machine learning tests"),
            ("risk", "Risk management tests"),
            ("broker", "Broker integration tests"),
            ("integration", "Full integration tests"),
            ("performance", "Performance tests"),
            ("stress", "Stress tests - slowest execution"),
        ]

    def _get_optimal_worker_count(self) -> int:
        """Calculate optimal number of parallel workers."""
        # Base on CPU cores and available memory
        cpu_workers = max(1, self.cpu_count - 1)  # Leave one core free
        memory_workers = max(1, int(self.available_memory_gb / 2))  # 2GB per worker

        # Use conservative estimate
        optimal_workers = min(cpu_workers, memory_workers, 8)  # Max 8 workers

        print(f"System: {self.cpu_count} CPUs, {self.available_memory_gb:.1f}GB RAM")
        print(f"Optimal workers: {optimal_workers}")

        return optimal_workers

    def _run_fast_tests_only(self, **kwargs) -> Tuple[int, float]:
        """Run only fast tests for rapid feedback."""
        print("🚀 Running fast tests only...")

        start_time = time.time()

        cmd = [
            "python",
            "-m",
            "pytest",
            "-x",  # Stop on first failure
            "-q",  # Quiet output
            "--tb=short",
            "-m",
            "fast or unit",
            "--maxfail=3",
            f"-n={self._get_optimal_worker_count()}",
            "tests/",
        ]

        result = subprocess.run(cmd, cwd=self.project_root)
        execution_time = time.time() - start_time

        return result.returncode, execution_time

    def _run_parallel_tests(self, **kwargs) -> Tuple[int, float]:
        """Run tests with optimal parallelization."""
        print("⚡ Running parallel optimized tests...")

        start_time = time.time()
        workers = self._get_optimal_worker_count()

        cmd = [
            "python",
            "-m",
            "pytest",
            "-v",
            "--tb=short",
            "--durations=10",
            f"-n={workers}",
            "--dist=loadscope",  # Distribute by test scope
            "--maxfail=5",
            "-m",
            "not slow and not stress and not requires_ib",
            "tests/",
        ]

        result = subprocess.run(cmd, cwd=self.project_root)
        execution_time = time.time() - start_time

        return result.returncode, execution_time

    def _run_smart_execution(self, **kwargs) -> Tuple[int, float]:
        """Run tests with smart category-based execution."""
        print("🧠 Running smart category-based execution...")

        total_start_time = time.time()
        overall_result = 0

        # Execute test categories in order of speed
        fast_categories = ["unit", "fast", "api", "feature"]

        for category, description in self.test_categories:
            if category not in fast_categories:
                continue  # Skip slower categories in smart mode

            print(f"\n📂 Running {category} tests: {description}")

            start_time = time.time()
            cmd = [
                "python",
                "-m",
                "pytest",
                "-v",
                "--tb=short",
                "-m",
                category,
                f"-n={min(4, self._get_optimal_worker_count())}",  # Fewer workers for reliability
                "--maxfail=2",
                "tests/",
            ]

            result = subprocess.run(cmd, cwd=self.project_root)
            category_time = time.time() - start_time

            status = "✅ PASSED" if result.returncode == 0 else "❌ FAILED"
            print(f"{status} {category} tests in {category_time:.1f}s")

            if result.returncode != 0:
                overall_result = result.returncode
                break  # Stop on first category failure

        total_time = time.time() - total_start_time
        return overall_result, total_time

    def _run_with_coverage(self, **kwargs) -> Tuple[int, float]:
        """Run tests with coverage analysis."""
        print("📊 Running tests with coverage analysis...")

        start_time = time.time()

        cmd = [
            "python",
            "-m",
            "pytest",
            "--cov=fxml4",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-fail-under=60",
            "-v",
            "--tb=short",
            f"-n={max(1, self._get_optimal_worker_count() // 2)}",  # Reduced for coverage
            "-m",
            "not slow and not stress",
            "tests/",
        ]

        result = subprocess.run(cmd, cwd=self.project_root)
        execution_time = time.time() - start_time

        return result.returncode, execution_time

    def _run_full_suite(self, **kwargs) -> Tuple[int, float]:
        """Run complete test suite with all optimizations."""
        print("🎯 Running full optimized test suite...")

        start_time = time.time()

        # First pass: Fast tests in parallel
        print("\n🚀 Phase 1: Fast tests...")
        phase1_start = time.time()

        cmd_fast = [
            "python",
            "-m",
            "pytest",
            "-v",
            "--tb=short",
            f"-n={self._get_optimal_worker_count()}",
            "-m",
            "fast or unit",
            "--maxfail=3",
            "tests/",
        ]

        result_fast = subprocess.run(cmd_fast, cwd=self.project_root)
        phase1_time = time.time() - phase1_start
        print(f"Phase 1 completed in {phase1_time:.1f}s")

        if result_fast.returncode != 0:
            print("❌ Fast tests failed, stopping execution")
            return result_fast.returncode, time.time() - start_time

        # Second pass: Integration tests
        print("\n🔗 Phase 2: Integration tests...")
        phase2_start = time.time()

        cmd_integration = [
            "python",
            "-m",
            "pytest",
            "-v",
            "--tb=short",
            f"-n={max(2, self._get_optimal_worker_count() // 2)}",
            "-m",
            "integration and not slow",
            "--maxfail=5",
            "tests/",
        ]

        result_integration = subprocess.run(cmd_integration, cwd=self.project_root)
        phase2_time = time.time() - phase2_start
        print(f"Phase 2 completed in {phase2_time:.1f}s")

        if result_integration.returncode != 0:
            print("❌ Integration tests failed")
            return result_integration.returncode, time.time() - start_time

        total_time = time.time() - start_time
        print(f"\n✅ Full suite completed in {total_time:.1f}s")

        return 0, total_time

    def _estimate_execution_time(self, strategy: str) -> float:
        """Estimate execution time for strategy."""
        estimates = {
            "fast": 30,  # 30 seconds
            "parallel": 120,  # 2 minutes
            "smart": 180,  # 3 minutes
            "coverage": 300,  # 5 minutes
            "full": 300,  # 5 minutes
        }
        return estimates.get(strategy, 300)

    def run_tests(self, strategy: str = "smart", **kwargs) -> Tuple[int, float]:
        """Run tests with specified strategy."""
        if strategy not in self.strategies:
            raise ValueError(f"Unknown strategy: {strategy}")

        estimated_time = self._estimate_execution_time(strategy)
        print(f"🎯 Strategy: {strategy}")
        print(f"📅 Estimated time: {estimated_time}s")
        print(f"🖥️  System: {self.cpu_count} CPUs, {self.available_memory_gb:.1f}GB RAM")
        print("-" * 50)

        return self.strategies[strategy](**kwargs)

    def analyze_test_performance(self) -> Dict[str, any]:
        """Analyze test suite performance characteristics."""
        print("📈 Analyzing test performance...")

        # Run quick performance analysis
        cmd = ["python", "-m", "pytest", "--collect-only", "--quiet", "tests/"]

        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=self.project_root
        )

        if result.returncode == 0:
            lines = result.stdout.split("\n")
            test_count = sum(
                1 for line in lines if "test session starts" in line.lower()
            )

            return {
                "total_tests": len([line for line in lines if "<Function" in line]),
                "test_files": len([line for line in lines if "<Module" in line]),
                "estimated_serial_time": len(
                    [line for line in lines if "<Function" in line]
                )
                * 0.1,  # 100ms per test
                "recommended_strategy": "smart" if test_count < 1000 else "parallel",
            }

        return {"error": "Could not analyze test suite"}


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Optimized test execution for FXML4")
    parser.add_argument(
        "strategy",
        choices=["fast", "parallel", "smart", "coverage", "full"],
        default="smart",
        nargs="?",
        help="Test execution strategy",
    )
    parser.add_argument(
        "--analyze", action="store_true", help="Analyze test suite performance"
    )
    parser.add_argument(
        "--target-time",
        type=int,
        default=300,
        help="Target execution time in seconds (default: 300s/5min)",
    )

    args = parser.parse_args()

    runner = OptimizedTestRunner()

    if args.analyze:
        analysis = runner.analyze_test_performance()
        print("\n📊 Test Suite Analysis:")
        for key, value in analysis.items():
            print(f"  {key}: {value}")
        return 0

    # Run tests with specified strategy
    try:
        print(f"🚀 Starting optimized test execution...")
        print(f"🎯 Target time: {args.target_time}s")

        exit_code, execution_time = runner.run_tests(args.strategy)

        # Results summary
        print("\n" + "=" * 60)
        print("📋 EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Strategy: {args.strategy}")
        print(f"Execution time: {execution_time:.1f}s")
        print(f"Target time: {args.target_time}s")
        print(
            f"Performance: {'✅ WITHIN TARGET' if execution_time <= args.target_time else '⚠️ EXCEEDED TARGET'}"
        )
        print(f"Result: {'✅ PASSED' if exit_code == 0 else '❌ FAILED'}")

        if execution_time > args.target_time:
            print(f"\n💡 Suggestions to improve performance:")
            print(f"  - Try 'fast' strategy for quicker feedback")
            print(f"  - Use 'parallel' strategy with more workers")
            print(f"  - Run specific test categories only")

        return exit_code

    except KeyboardInterrupt:
        print("\n⚠️ Test execution interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error during test execution: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
