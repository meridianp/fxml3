#!/usr/bin/env python3
"""
FXML4 End-to-End Trading Workflow Validation Script

This script runs comprehensive end-to-end validation of the FXML4 trading system:
- ML signal → risk check → order → IB execution → position tracking within 30-second SLA
- Real Interactive Brokers TWS connection
- Real GBP/USD market data
- Complete workflow validation with performance monitoring

Usage:
    python scripts/run_end_to_end_validation.py [options]
    ./scripts/run_with_fxml4.sh scripts/run_end_to_end_validation.py [options]

Options:
    --workflows N     Number of workflows to validate (default: 10)
    --symbol SYMBOL   Currency pair to test (default: GBPUSD)
    --report-only     Generate report from existing results
    --continuous      Run continuous validation (Ctrl+C to stop)
    --verbose         Enable verbose logging
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fxml4.core.config import load_config
from fxml4.core.logging_config import setup_logging
from fxml4.live_trading.end_to_end_validator import EndToEndValidator, SLAViolationError


class ValidationRunner:
    """
    End-to-End Validation Runner

    Orchestrates comprehensive trading workflow validation with:
    - Single and multiple workflow testing
    - Continuous monitoring mode
    - Performance reporting and analysis
    - SLA compliance verification
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.validator: EndToEndValidator = None
        self.results_file = Path("validation_results.json")
        self.shutdown_requested = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True

    async def initialize(self) -> None:
        """Initialize validation components"""
        self.logger.info("Initializing end-to-end validation runner...")

        try:
            # Create validator with configuration
            validator_config = {
                "orchestrator": self.config.get("live_trading", {}),
                "ml": self.config.get("ml", {}),
                "risk_management": self.config.get("risk_management", {}),
                "ib_adapter": self.config.get("brokers", {}).get(
                    "interactive_brokers", {}
                ),
                "market_data": self.config.get("market_data", {}),
                "performance": self.config.get("performance_tracking", {}),
            }

            self.validator = EndToEndValidator(validator_config)
            await self.validator.initialize_components()

            self.logger.info("✅ Validation runner initialized successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize validation runner: {e}")
            raise

    async def run_single_validation(self, symbol: str = "GBPUSD") -> Dict[str, Any]:
        """Run single workflow validation"""
        self.logger.info(f"🔄 Running single workflow validation for {symbol}")

        try:
            result = await self.validator.validate_single_workflow(symbol)

            if result.sla_compliant:
                self.logger.info(f"✅ Single workflow validation PASSED")
                self.logger.info(f"   Duration: {result.total_duration_seconds:.2f}s")
                self.logger.info(f"   SLA Margin: {result.sla_margin_seconds:.2f}s")
            else:
                self.logger.error(f"❌ Single workflow validation FAILED")
                self.logger.error(
                    f"   Duration: {result.total_duration_seconds:.2f}s (exceeded 30s SLA)"
                )
                for error in result.errors:
                    self.logger.error(f"   Error: {error}")

            return {
                "success": result.sla_compliant,
                "duration_seconds": result.total_duration_seconds,
                "errors": result.errors,
                "warnings": result.warnings,
            }

        except Exception as e:
            self.logger.error(f"❌ Single validation failed with exception: {e}")
            return {"success": False, "error": str(e)}

    async def run_multiple_validations(
        self, count: int = 10, symbol: str = "GBPUSD"
    ) -> Dict[str, Any]:
        """Run multiple workflow validations"""
        self.logger.info(f"🔄 Running {count} workflow validations for {symbol}")

        try:
            results = await self.validator.validate_multiple_workflows(count, symbol)

            compliance_rate = results["validation_summary"]["sla_compliance_rate"]
            avg_duration = results["performance_metrics"]["duration_statistics"][
                "mean_seconds"
            ]

            if compliance_rate >= 0.8:  # 80% compliance threshold
                self.logger.info(f"✅ Multiple workflow validation PASSED")
                self.logger.info(f"   SLA Compliance: {compliance_rate:.1%}")
                self.logger.info(f"   Average Duration: {avg_duration:.2f}s")
            else:
                self.logger.error(f"❌ Multiple workflow validation FAILED")
                self.logger.error(
                    f"   SLA Compliance: {compliance_rate:.1%} (below 80% threshold)"
                )
                self.logger.error(f"   Average Duration: {avg_duration:.2f}s")

            # Save results to file
            await self._save_results(results)

            return results

        except Exception as e:
            self.logger.error(f"❌ Multiple validations failed with exception: {e}")
            return {"success": False, "error": str(e)}

    async def run_continuous_validation(
        self, interval_minutes: int = 5, symbol: str = "GBPUSD"
    ):
        """Run continuous validation monitoring"""
        self.logger.info(
            f"🔄 Starting continuous validation for {symbol} (every {interval_minutes} minutes)"
        )
        self.logger.info("Press Ctrl+C to stop continuous validation")

        validation_count = 0

        try:
            while not self.shutdown_requested:
                validation_count += 1
                self.logger.info(f"🔄 Running validation #{validation_count}")

                try:
                    # Run single validation
                    result = await self.run_single_validation(symbol)

                    if result["success"]:
                        self.logger.info(f"✅ Validation #{validation_count} passed")
                    else:
                        self.logger.error(f"❌ Validation #{validation_count} failed")

                except Exception as e:
                    self.logger.error(
                        f"❌ Validation #{validation_count} exception: {e}"
                    )

                # Wait for next validation
                self.logger.info(
                    f"⏳ Waiting {interval_minutes} minutes for next validation..."
                )

                for _ in range(
                    interval_minutes * 60
                ):  # Wait in 1-second intervals for responsive shutdown
                    if self.shutdown_requested:
                        break
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("🛑 Continuous validation interrupted by user")
        finally:
            self.logger.info(
                f"📊 Continuous validation completed. Total validations: {validation_count}"
            )

    async def generate_report(self) -> str:
        """Generate comprehensive validation report"""
        try:
            if self.validator and self.validator.validation_results:
                report = await self.validator.generate_validation_report()
            else:
                # Try to load results from file
                if self.results_file.exists():
                    with open(self.results_file, "r") as f:
                        data = json.load(f)
                    report = self._generate_report_from_file(data)
                else:
                    report = "No validation results available for reporting"

            return report

        except Exception as e:
            self.logger.error(f"Failed to generate report: {e}")
            return f"Report generation failed: {e}"

    def _generate_report_from_file(self, data: Dict[str, Any]) -> str:
        """Generate report from saved results file"""
        lines = [
            "=" * 80,
            "FXML4 END-TO-END TRADING WORKFLOW VALIDATION REPORT",
            "=" * 80,
            f"Generated: {datetime.utcnow().isoformat()}",
            f"Data Source: {self.results_file}",
            "",
        ]

        if "validation_summary" in data:
            summary = data["validation_summary"]
            lines.extend(
                [
                    "VALIDATION SUMMARY:",
                    f"  Total Workflows: {summary.get('total_workflows', 'N/A')}",
                    f"  Successful Workflows: {summary.get('successful_workflows', 'N/A')}",
                    f"  SLA Compliant: {summary.get('sla_compliant_workflows', 'N/A')}",
                    f"  Compliance Rate: {summary.get('sla_compliance_rate', 0):.1%}",
                    "",
                ]
            )

        if "performance_metrics" in data:
            perf = data["performance_metrics"]
            if "duration_statistics" in perf:
                duration_stats = perf["duration_statistics"]
                lines.extend(
                    [
                        "PERFORMANCE STATISTICS:",
                        f"  Average Duration: {duration_stats.get('mean_seconds', 0):.2f} seconds",
                        f"  Median Duration: {duration_stats.get('median_seconds', 0):.2f} seconds",
                        f"  Fastest: {duration_stats.get('min_seconds', 0):.2f} seconds",
                        f"  Slowest: {duration_stats.get('max_seconds', 0):.2f} seconds",
                        "",
                    ]
                )

        lines.extend(["=" * 80])

        return "\n".join(lines)

    async def _save_results(self, results: Dict[str, Any]) -> None:
        """Save validation results to file"""
        try:
            # Add timestamp to results
            results["saved_at"] = datetime.utcnow().isoformat()

            with open(self.results_file, "w") as f:
                json.dump(results, f, indent=2, default=str)

            self.logger.info(f"📁 Results saved to {self.results_file}")

        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")

    async def cleanup(self) -> None:
        """Cleanup validation resources"""
        try:
            if self.validator:
                await self.validator.cleanup()
            self.logger.info("🧹 Validation runner cleanup completed")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="FXML4 End-to-End Trading Workflow Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_end_to_end_validation.py
  python scripts/run_end_to_end_validation.py --workflows 20 --symbol EURUSD
  python scripts/run_end_to_end_validation.py --continuous
  python scripts/run_end_to_end_validation.py --report-only
        """,
    )

    parser.add_argument(
        "--workflows",
        type=int,
        default=10,
        help="Number of workflows to validate (default: 10)",
    )

    parser.add_argument(
        "--symbol",
        type=str,
        default="GBPUSD",
        help="Currency pair to test (default: GBPUSD)",
    )

    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate report from existing results only",
    )

    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuous validation (Ctrl+C to stop)",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Interval in minutes for continuous validation (default: 5)",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    return parser.parse_args()


async def main():
    """Main execution function"""
    args = parse_arguments()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)

    logger = logging.getLogger(__name__)
    logger.info("🚀 Starting FXML4 End-to-End Trading Workflow Validation")

    try:
        # Load configuration
        config = load_config()

        # Create validation runner
        runner = ValidationRunner(config)

        if args.report_only:
            # Generate report only
            logger.info("📊 Generating validation report...")
            report = await runner.generate_report()
            print(report)
            return

        # Initialize runner
        await runner.initialize()

        if args.continuous:
            # Run continuous validation
            await runner.run_continuous_validation(args.interval, args.symbol)
        else:
            # Run single validation first
            logger.info("🔧 Running single workflow validation...")
            single_result = await runner.run_single_validation(args.symbol)

            if single_result["success"]:
                logger.info(
                    "✅ Single workflow validation passed, proceeding to multiple validations"
                )

                # Run multiple validations
                logger.info(f"🔧 Running {args.workflows} workflow validations...")
                multi_results = await runner.run_multiple_validations(
                    args.workflows, args.symbol
                )

                # Generate final report
                logger.info("📊 Generating final validation report...")
                report = await runner.generate_report()
                print("\n" + report + "\n")

                # Summary
                if (
                    multi_results.get("validation_summary", {}).get(
                        "sla_compliance_rate", 0
                    )
                    >= 0.8
                ):
                    logger.info("🎉 END-TO-END VALIDATION COMPLETED SUCCESSFULLY")
                    logger.info("✅ System ready for production deployment")
                else:
                    logger.error("❌ END-TO-END VALIDATION FAILED")
                    logger.error(
                        "🚫 System NOT ready for production - SLA compliance below threshold"
                    )
            else:
                logger.error("❌ Single workflow validation failed")
                logger.error("🚫 System NOT ready for multiple validations")

    except KeyboardInterrupt:
        logger.info("🛑 Validation interrupted by user")
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        sys.exit(1)
    finally:
        if "runner" in locals():
            await runner.cleanup()
        logger.info("🏁 End-to-end validation completed")


if __name__ == "__main__":
    asyncio.run(main())
