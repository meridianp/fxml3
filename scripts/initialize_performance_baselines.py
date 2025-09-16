#!/usr/bin/env python3
"""
Performance Baseline Initialization Script
==========================================

This script initializes performance baselines for the FXML4 system by running
comprehensive performance tests and storing the results as baseline metrics.

The baselines are used by the performance regression testing suite to detect
performance degradation over time.

Usage:
    python scripts/initialize_performance_baselines.py
    python scripts/initialize_performance_baselines.py --force  # Overwrite existing baselines
    python scripts/initialize_performance_baselines.py --environment production
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import aiohttp
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.performance.test_performance_regression_suite import (
    PerformanceBaseline,
    PerformanceRegressionSuite,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
BASELINES_DIR = Path("tests/performance/baselines")
DEFAULT_API_URL = "http://localhost:8001"


class BaselineInitializer:
    """Initialize performance baselines for FXML4 system."""

    def __init__(self, api_url: str = DEFAULT_API_URL, force: bool = False):
        self.api_url = api_url
        self.force = force
        self.environment = os.getenv("FXML4_ENV", "development")
        self.git_commit = os.getenv("GIT_COMMIT", self._get_git_commit())

        # Ensure baselines directory exists
        BASELINES_DIR.mkdir(parents=True, exist_ok=True)

    def _get_git_commit(self) -> str:
        """Get current git commit hash."""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )
            if result.returncode == 0:
                return result.stdout.strip()[:8]
        except Exception:
            pass
        return "unknown"

    def _baseline_exists(self, test_name: str) -> bool:
        """Check if baseline already exists."""
        baseline_file = BASELINES_DIR / f"{test_name}.json"
        return baseline_file.exists()

    async def _wait_for_api(self, timeout: int = 60):
        """Wait for API to be available."""
        logger.info(f"Waiting for API at {self.api_url} to be available...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.api_url}/health") as response:
                        if response.status == 200:
                            logger.info("✅ API is available")
                            return True
            except Exception:
                pass

            await asyncio.sleep(2)

        logger.error(f"❌ API not available after {timeout}s")
        return False

    async def _measure_baseline_performance(
        self, test_name: str, test_function
    ) -> Dict[str, float]:
        """Measure baseline performance for a specific test."""
        logger.info(f"📊 Measuring baseline performance for {test_name}")

        # Run the test multiple times for more accurate baseline
        iterations = 3
        all_metrics = {}

        for iteration in range(iterations):
            logger.info(f"  Iteration {iteration + 1}/{iterations}")

            async with PerformanceRegressionSuite(self.api_url) as suite:
                # Run the specific test
                try:
                    await test_function(suite)

                    # Extract performance metrics from measurements
                    if suite.measurements:
                        response_times = [
                            m.response_time_ms for m in suite.measurements if m.success
                        ]
                        memory_usage = [m.memory_mb for m in suite.measurements]
                        cpu_usage = [m.cpu_percent for m in suite.measurements]

                        if response_times:
                            iteration_metrics = {
                                f"p95_response_time_ms": np.percentile(
                                    response_times, 95
                                ),
                                f"mean_response_time_ms": np.mean(response_times),
                                f"max_response_time_ms": np.max(response_times),
                                f"min_response_time_ms": np.min(response_times),
                                f"mean_memory_mb": (
                                    np.mean(memory_usage) if memory_usage else 0
                                ),
                                f"mean_cpu_percent": (
                                    np.mean(cpu_usage) if cpu_usage else 0
                                ),
                                f"success_rate": len(
                                    [m for m in suite.measurements if m.success]
                                )
                                / len(suite.measurements)
                                * 100,
                            }

                            # Aggregate metrics across iterations
                            for metric_name, value in iteration_metrics.items():
                                if metric_name not in all_metrics:
                                    all_metrics[metric_name] = []
                                all_metrics[metric_name].append(value)

                    # Clear measurements for next iteration
                    suite.measurements = []

                except Exception as e:
                    logger.warning(f"  Iteration {iteration + 1} failed: {e}")

                # Small delay between iterations
                await asyncio.sleep(5)

        # Calculate final baseline metrics (average across iterations)
        baseline_metrics = {}
        for metric_name, values in all_metrics.items():
            if values:
                baseline_metrics[metric_name] = float(np.mean(values))

        if not baseline_metrics:
            logger.warning(f"No valid metrics collected for {test_name}")
            baseline_metrics = {
                "p95_response_time_ms": 1000.0,  # Default conservative values
                "mean_response_time_ms": 500.0,
                "success_rate": 100.0,
            }

        return baseline_metrics

    def _save_baseline(self, test_name: str, metrics: Dict[str, float]):
        """Save baseline to storage."""
        baseline = PerformanceBaseline(
            test_name=test_name,
            timestamp=datetime.now().isoformat(),
            git_commit=self.git_commit,
            environment=self.environment,
            metrics=metrics,
            metadata={
                "api_url": self.api_url,
                "created_by": "baseline_initializer",
                "python_version": sys.version,
                "platform": sys.platform,
            },
        )

        baseline_file = BASELINES_DIR / f"{test_name}.json"

        with open(baseline_file, "w") as f:
            json.dump(baseline.__dict__, f, indent=2)

        logger.info(f"✅ Baseline saved: {baseline_file}")

    async def initialize_api_baseline(self):
        """Initialize API endpoint performance baseline."""
        test_name = "api_endpoint_performance"

        if self._baseline_exists(test_name) and not self.force:
            logger.info(
                f"⏭️  Baseline exists for {test_name}, skipping (use --force to overwrite)"
            )
            return

        async def test_function(suite):
            await suite.test_api_endpoint_performance_regression()

        metrics = await self._measure_baseline_performance(test_name, test_function)
        self._save_baseline(test_name, metrics)

    async def initialize_database_baseline(self):
        """Initialize database performance baseline."""
        test_name = "database_performance"

        if self._baseline_exists(test_name) and not self.force:
            logger.info(
                f"⏭️  Baseline exists for {test_name}, skipping (use --force to overwrite)"
            )
            return

        async def test_function(suite):
            await suite.test_database_performance_regression()

        metrics = await self._measure_baseline_performance(test_name, test_function)
        self._save_baseline(test_name, metrics)

    async def initialize_ml_baseline(self):
        """Initialize ML inference performance baseline."""
        test_name = "ml_inference_performance"

        if self._baseline_exists(test_name) and not self.force:
            logger.info(
                f"⏭️  Baseline exists for {test_name}, skipping (use --force to overwrite)"
            )
            return

        async def test_function(suite):
            await suite.test_ml_inference_performance_regression()

        metrics = await self._measure_baseline_performance(test_name, test_function)
        self._save_baseline(test_name, metrics)

    async def initialize_load_baseline(self):
        """Initialize concurrent load performance baseline."""
        test_name = "concurrent_load_performance"

        if self._baseline_exists(test_name) and not self.force:
            logger.info(
                f"⏭️  Baseline exists for {test_name}, skipping (use --force to overwrite)"
            )
            return

        async def test_function(suite):
            await suite.test_concurrent_load_performance_regression()

        metrics = await self._measure_baseline_performance(test_name, test_function)
        self._save_baseline(test_name, metrics)

    async def initialize_all_baselines(self):
        """Initialize all performance baselines."""
        logger.info("🚀 Starting performance baseline initialization")
        logger.info(f"Environment: {self.environment}")
        logger.info(f"Git Commit: {self.git_commit}")
        logger.info(f"API URL: {self.api_url}")

        # Wait for API to be available
        if not await self._wait_for_api():
            logger.error("❌ Cannot initialize baselines - API not available")
            return False

        # Initialize all baselines
        baseline_functions = [
            self.initialize_api_baseline,
            self.initialize_database_baseline,
            self.initialize_ml_baseline,
            self.initialize_load_baseline,
        ]

        success_count = 0
        total_count = len(baseline_functions)

        for baseline_function in baseline_functions:
            try:
                await baseline_function()
                success_count += 1
            except Exception as e:
                logger.error(
                    f"❌ Failed to initialize {baseline_function.__name__}: {e}"
                )

        logger.info(
            f"📊 Baseline initialization complete: {success_count}/{total_count} successful"
        )

        if success_count == total_count:
            logger.info("✅ All baselines initialized successfully")
            return True
        else:
            logger.warning(
                f"⚠️  Only {success_count}/{total_count} baselines initialized"
            )
            return False

    def list_baselines(self):
        """List existing baselines."""
        logger.info("📋 Existing performance baselines:")

        baseline_files = list(BASELINES_DIR.glob("*.json"))

        if not baseline_files:
            logger.info("  No baselines found")
            return

        for baseline_file in sorted(baseline_files):
            try:
                with open(baseline_file, "r") as f:
                    data = json.load(f)

                test_name = data.get("test_name", baseline_file.stem)
                timestamp = data.get("timestamp", "unknown")
                commit = data.get("git_commit", "unknown")
                env = data.get("environment", "unknown")

                logger.info(
                    f"  {test_name}: {timestamp} (commit: {commit}, env: {env})"
                )

            except Exception as e:
                logger.warning(f"  {baseline_file.name}: Error reading file - {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Initialize FXML4 performance baselines"
    )

    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing baselines"
    )

    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"API URL (default: {DEFAULT_API_URL})",
    )

    parser.add_argument(
        "--environment",
        help="Environment name (default: from FXML4_ENV or 'development')",
    )

    parser.add_argument("--list", action="store_true", help="List existing baselines")

    args = parser.parse_args()

    if args.environment:
        os.environ["FXML4_ENV"] = args.environment

    initializer = BaselineInitializer(api_url=args.api_url, force=args.force)

    if args.list:
        initializer.list_baselines()
        return

    # Run baseline initialization
    success = asyncio.run(initializer.initialize_all_baselines())

    if success:
        logger.info("🎉 Performance baseline initialization completed successfully")
        sys.exit(0)
    else:
        logger.error("💥 Performance baseline initialization failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
