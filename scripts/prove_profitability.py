#!/usr/bin/env python3
"""
FXML4 Profitability Validation Script

This script orchestrates comprehensive profitability validation campaigns to prove
that the FXML4 trading system can achieve >15% annual return with <10% maximum
drawdown over 30-day live paper trading periods.

Usage Examples:
    # Start 30-day profitability validation campaign
    python scripts/prove_profitability.py

    # Start with custom parameters
    python scripts/prove_profitability.py --duration 15 --target-return 12.0 --max-drawdown 8.0

    # Monitor existing campaign
    python scripts/prove_profitability.py --monitor-only

    # Generate report from existing data
    python scripts/prove_profitability.py --report-only

    # Stress test with accelerated trading
    python scripts/prove_profitability.py --accelerated --trades-per-day 10

Author: FXML4 Development Team
"""

import argparse
import asyncio
import json
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from fxml4.core.config import get_config
    from fxml4.core.logger import get_logger
    from fxml4.live_trading.live_performance_tracker import (
        LivePerformanceTracker,
        PerformanceConfig,
        PerformanceSnapshot,
    )
    from fxml4.live_trading.profitability_validator import (
        ProfitabilityValidator,
        ValidationConfig,
        ValidationError,
        ValidationResult,
    )
    from fxml4.live_trading.trading_performance_monitor import (
        MonitoringConfig,
        TradingPerformanceMonitor,
    )
except ImportError as e:
    print(f"Warning: Could not import FXML4 modules: {e}")
    print("Creating mock classes for demonstration...")

    # Mock classes for demonstration
    class ValidationConfig:
        def __init__(self, **kwargs):
            self.campaign_duration_days = kwargs.get("campaign_duration_days", 30)
            self.target_annual_return_pct = kwargs.get("target_annual_return_pct", 15.0)
            self.max_drawdown_pct = kwargs.get("max_drawdown_pct", 10.0)
            self.trades_per_day = kwargs.get("trades_per_day", 5)

    class ValidationResult:
        def __init__(self):
            self.success = False
            self.annual_return = 0.0
            self.max_drawdown = 0.0
            self.summary = "Mock result"

    class ProfitabilityValidator:
        async def start_trading_campaign(self):
            return ValidationResult()

        async def get_current_status(self):
            return {"status": "mock"}

        async def generate_report(self):
            return "Mock report"

    class LivePerformanceTracker:
        async def get_current_snapshot(self):
            return {"performance": "mock"}

    class TradingPerformanceMonitor:
        async def get_monitoring_summary(self):
            return {"monitoring": "mock"}

    def get_logger(name):
        import logging

        return logging.getLogger(name)

    def get_config():
        return {}


class ProfitabilityProofOrchestrator:
    """Orchestrates profitability validation campaigns and reporting."""

    def __init__(self, config: Optional[ValidationConfig] = None):
        self.logger = get_logger(self.__class__.__name__)
        self.config = config or ValidationConfig()

        # Initialize validation components
        self.validator = None
        self.performance_tracker = None
        self.monitor = None

        # Campaign state
        self.campaign_id = None
        self.campaign_start_time = None
        self.results_dir = Path("results/profitability_validation")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    async def initialize_components(self):
        """Initialize all validation components."""
        try:
            self.logger.info("Initializing profitability validation components...")

            # Initialize validator
            self.validator = ProfitabilityValidator(self.config)
            await self.validator.initialize()

            # Initialize performance tracker
            perf_config = PerformanceConfig(
                target_annual_return=self.config.target_annual_return_pct,
                max_drawdown_threshold=self.config.max_drawdown_pct,
            )
            self.performance_tracker = LivePerformanceTracker(perf_config)
            await self.performance_tracker.initialize()

            # Initialize monitor
            monitor_config = MonitoringConfig(
                monitoring_interval_seconds=30,  # 30-second updates during campaign
                alert_thresholds={
                    "drawdown_warning": 5.0,
                    "drawdown_critical": 8.0,
                    "performance_below_target": 7.0,
                },
            )
            self.monitor = TradingPerformanceMonitor(monitor_config)
            await self.monitor.initialize()

            self.logger.info("✅ All components initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Component initialization failed: {e}")
            self.logger.error(traceback.format_exc())
            return False

    async def start_profitability_campaign(self) -> ValidationResult:
        """Start a new profitability validation campaign."""
        try:
            self.campaign_id = (
                f"profitability_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            )
            self.campaign_start_time = datetime.utcnow()

            self.logger.info(
                f"🚀 Starting profitability validation campaign: {self.campaign_id}"
            )
            self.logger.info(f"📊 Campaign Parameters:")
            self.logger.info(
                f"   - Duration: {self.config.campaign_duration_days} days"
            )
            self.logger.info(
                f"   - Target Annual Return: {self.config.target_annual_return_pct}%"
            )
            self.logger.info(f"   - Maximum Drawdown: {self.config.max_drawdown_pct}%")
            self.logger.info(f"   - Target Trades/Day: {self.config.trades_per_day}")

            # Start monitoring in background
            monitor_task = asyncio.create_task(
                self.monitor.start_monitoring(self.campaign_id)
            )

            try:
                # Run the actual trading campaign
                result = await self.validator.start_trading_campaign()

                # Save campaign results
                await self._save_campaign_results(result)

                # Generate comprehensive report
                await self._generate_final_report(result)

                if result.success:
                    self.logger.info("🎉 PROFITABILITY VALIDATION SUCCESSFUL!")
                    self.logger.info(
                        f"   - Achieved Annual Return: {result.annual_return:.2f}%"
                    )
                    self.logger.info(
                        f"   - Maximum Drawdown: {result.max_drawdown:.2f}%"
                    )
                else:
                    self.logger.warning("⚠️  PROFITABILITY VALIDATION INCOMPLETE")
                    self.logger.warning(
                        f"   - Current Annual Return: {result.annual_return:.2f}%"
                    )
                    self.logger.warning(
                        f"   - Current Drawdown: {result.max_drawdown:.2f}%"
                    )

                return result

            finally:
                # Stop monitoring
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass

        except ValidationError as e:
            self.logger.error(f"❌ Validation error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Unexpected error during campaign: {e}")
            self.logger.error(traceback.format_exc())
            raise

    async def monitor_existing_campaign(self) -> Dict:
        """Monitor an existing profitability campaign."""
        try:
            self.logger.info("📊 Monitoring existing profitability campaign...")

            # Get current campaign status
            status = await self.validator.get_current_status()

            # Get performance snapshot
            snapshot = await self.performance_tracker.get_current_snapshot()

            # Get monitoring summary
            monitoring = await self.monitor.get_monitoring_summary()

            # Display current status
            self._display_campaign_status(status, snapshot, monitoring)

            return {
                "campaign_status": status,
                "performance": snapshot,
                "monitoring": monitoring,
            }

        except Exception as e:
            self.logger.error(f"❌ Error monitoring campaign: {e}")
            raise

    async def generate_report_only(self) -> str:
        """Generate a report from existing campaign data."""
        try:
            self.logger.info("📈 Generating profitability validation report...")

            # Find latest campaign data
            campaign_files = list(self.results_dir.glob("campaign_*.json"))
            if not campaign_files:
                raise ValueError("No campaign data found for report generation")

            latest_file = max(campaign_files, key=lambda f: f.stat().st_mtime)

            # Load campaign data
            with open(latest_file, "r") as f:
                campaign_data = json.load(f)

            # Generate comprehensive report
            report = await self._generate_comprehensive_report(campaign_data)

            # Save report
            report_file = (
                self.results_dir
                / f"profitability_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
            )
            with open(report_file, "w") as f:
                f.write(report)

            self.logger.info(f"📄 Report saved to: {report_file}")
            return str(report_file)

        except Exception as e:
            self.logger.error(f"❌ Error generating report: {e}")
            raise

    def _display_campaign_status(self, status: Dict, snapshot: Dict, monitoring: Dict):
        """Display current campaign status to console."""
        print("\n" + "=" * 80)
        print("🎯 FXML4 PROFITABILITY VALIDATION CAMPAIGN STATUS")
        print("=" * 80)

        # Campaign info
        if "campaign_id" in status:
            print(f"Campaign ID: {status['campaign_id']}")
            print(f"Start Time: {status.get('start_time', 'Unknown')}")
            print(
                f"Duration: {status.get('days_elapsed', 0)}/{status.get('total_days', 30)} days"
            )
            print(f"Status: {status.get('status', 'Unknown')}")

        print(f"\n📊 PERFORMANCE METRICS")
        print(
            f"Current Return: {snapshot.get('annualized_return', 0):.2f}% (Target: {self.config.target_annual_return_pct}%)"
        )
        print(
            f"Max Drawdown: {snapshot.get('max_drawdown', 0):.2f}% (Limit: {self.config.max_drawdown_pct}%)"
        )
        print(f"Sharpe Ratio: {snapshot.get('sharpe_ratio', 0):.2f}")
        print(f"Total Trades: {snapshot.get('total_trades', 0)}")
        print(f"Win Rate: {snapshot.get('win_rate', 0):.1f}%")

        print(f"\n🚨 MONITORING ALERTS")
        alerts = monitoring.get("recent_alerts", [])
        if alerts:
            for alert in alerts[-5:]:  # Show last 5 alerts
                print(f"   - {alert.get('timestamp', '')}: {alert.get('message', '')}")
        else:
            print("   - No recent alerts")

        print(f"\n🎯 VALIDATION STATUS")
        target_met = (
            snapshot.get("annualized_return", 0) >= self.config.target_annual_return_pct
        )
        drawdown_ok = snapshot.get("max_drawdown", 0) <= self.config.max_drawdown_pct

        print(f"   ✅ Return Target: {'MET' if target_met else 'NOT MET'}")
        print(f"   ✅ Drawdown Limit: {'OK' if drawdown_ok else 'EXCEEDED'}")
        print(
            f"   ✅ Overall Status: {'PASSING' if target_met and drawdown_ok else 'FAILING'}"
        )

        print("=" * 80)

    async def _save_campaign_results(self, result: ValidationResult):
        """Save campaign results to file."""
        try:
            results_data = {
                "campaign_id": self.campaign_id,
                "start_time": self.campaign_start_time.isoformat(),
                "end_time": datetime.utcnow().isoformat(),
                "config": {
                    "duration_days": self.config.campaign_duration_days,
                    "target_return_pct": self.config.target_annual_return_pct,
                    "max_drawdown_pct": self.config.max_drawdown_pct,
                    "trades_per_day": self.config.trades_per_day,
                },
                "results": {
                    "success": result.success,
                    "annual_return": result.annual_return,
                    "max_drawdown": result.max_drawdown,
                    "summary": result.summary,
                },
            }

            results_file = self.results_dir / f"campaign_{self.campaign_id}.json"
            with open(results_file, "w") as f:
                json.dump(results_data, f, indent=2)

            self.logger.info(f"💾 Campaign results saved to: {results_file}")

        except Exception as e:
            self.logger.error(f"❌ Error saving results: {e}")

    async def _generate_final_report(self, result: ValidationResult):
        """Generate final campaign report."""
        try:
            report = await self.validator.generate_report()

            report_file = self.results_dir / f"final_report_{self.campaign_id}.html"
            with open(report_file, "w") as f:
                f.write(report)

            self.logger.info(f"📄 Final report generated: {report_file}")

        except Exception as e:
            self.logger.error(f"❌ Error generating final report: {e}")

    async def _generate_comprehensive_report(self, campaign_data: Dict) -> str:
        """Generate comprehensive HTML report from campaign data."""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>FXML4 Profitability Validation Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background: #2c3e50; color: white; padding: 20px; text-align: center; }
                .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
                .success { background: #d4edda; border-color: #c3e6cb; }
                .warning { background: #fff3cd; border-color: #ffeaa7; }
                .error { background: #f8d7da; border-color: #f5c6cb; }
                .metric { display: inline-block; margin: 10px; padding: 10px; background: #f8f9fa; border-radius: 5px; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>FXML4 Profitability Validation Report</h1>
                <p>Campaign: {campaign_id}</p>
                <p>Generated: {report_date}</p>
            </div>

            <div class="section {status_class}">
                <h2>🎯 Validation Results</h2>
                <div class="metric">
                    <strong>Annual Return:</strong> {annual_return:.2f}%<br>
                    <small>Target: {target_return:.1f}%</small>
                </div>
                <div class="metric">
                    <strong>Maximum Drawdown:</strong> {max_drawdown:.2f}%<br>
                    <small>Limit: {max_drawdown_limit:.1f}%</small>
                </div>
                <div class="metric">
                    <strong>Campaign Duration:</strong> {duration} days
                </div>
                <div class="metric">
                    <strong>Overall Status:</strong> {overall_status}
                </div>
            </div>

            <div class="section">
                <h2>📊 Performance Summary</h2>
                <p>{summary}</p>
            </div>

            <div class="section">
                <h2>🔍 Campaign Configuration</h2>
                <table>
                    <tr><th>Parameter</th><th>Value</th></tr>
                    <tr><td>Campaign Duration</td><td>{config_duration} days</td></tr>
                    <tr><td>Target Annual Return</td><td>{config_target}%</td></tr>
                    <tr><td>Maximum Drawdown Limit</td><td>{config_drawdown}%</td></tr>
                    <tr><td>Target Trades per Day</td><td>{config_trades}</td></tr>
                </table>
            </div>

            <div class="section">
                <h2>⏰ Timeline</h2>
                <table>
                    <tr><th>Event</th><th>Timestamp</th></tr>
                    <tr><td>Campaign Start</td><td>{start_time}</td></tr>
                    <tr><td>Campaign End</td><td>{end_time}</td></tr>
                    <tr><td>Report Generated</td><td>{report_date}</td></tr>
                </table>
            </div>
        </body>
        </html>
        """

        # Extract data for template
        config = campaign_data.get("config", {})
        results = campaign_data.get("results", {})

        # Determine status class
        success = results.get("success", False)
        status_class = "success" if success else "error"
        overall_status = "PASSED ✅" if success else "FAILED ❌"

        return html_template.format(
            campaign_id=campaign_data.get("campaign_id", "Unknown"),
            report_date=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            status_class=status_class,
            annual_return=results.get("annual_return", 0),
            target_return=config.get("target_return_pct", 15),
            max_drawdown=results.get("max_drawdown", 0),
            max_drawdown_limit=config.get("max_drawdown_pct", 10),
            duration=config.get("duration_days", 30),
            overall_status=overall_status,
            summary=results.get("summary", "No summary available"),
            config_duration=config.get("duration_days", 30),
            config_target=config.get("target_return_pct", 15),
            config_drawdown=config.get("max_drawdown_pct", 10),
            config_trades=config.get("trades_per_day", 5),
            start_time=campaign_data.get("start_time", "Unknown"),
            end_time=campaign_data.get("end_time", "Unknown"),
        )


async def main():
    """Main script execution."""
    parser = argparse.ArgumentParser(
        description="FXML4 Profitability Validation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/prove_profitability.py                          # Standard 30-day campaign
  python scripts/prove_profitability.py --duration 15           # 15-day campaign
  python scripts/prove_profitability.py --target-return 12.0    # 12% target return
  python scripts/prove_profitability.py --max-drawdown 8.0      # 8% max drawdown
  python scripts/prove_profitability.py --accelerated           # Accelerated testing
  python scripts/prove_profitability.py --monitor-only          # Monitor existing
  python scripts/prove_profitability.py --report-only           # Generate report only
        """,
    )

    # Campaign configuration
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Campaign duration in days (default: 30)",
    )
    parser.add_argument(
        "--target-return",
        type=float,
        default=15.0,
        help="Target annual return percentage (default: 15.0)",
    )
    parser.add_argument(
        "--max-drawdown",
        type=float,
        default=10.0,
        help="Maximum drawdown percentage limit (default: 10.0)",
    )
    parser.add_argument(
        "--trades-per-day",
        type=int,
        default=5,
        help="Target trades per day (default: 5)",
    )

    # Operation modes
    parser.add_argument(
        "--monitor-only",
        action="store_true",
        help="Monitor existing campaign without starting new one",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate report from existing data only",
    )
    parser.add_argument(
        "--accelerated",
        action="store_true",
        help="Run accelerated testing with higher trade frequency",
    )

    # Output options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results/profitability_validation",
        help="Output directory for results (default: results/profitability_validation)",
    )

    args = parser.parse_args()

    # Configure logging
    import logging

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = get_logger("ProfitabilityProof")

    try:
        # Create configuration
        config = ValidationConfig(
            campaign_duration_days=args.duration,
            target_annual_return_pct=args.target_return,
            max_drawdown_pct=args.max_drawdown,
            trades_per_day=args.trades_per_day * (3 if args.accelerated else 1),
        )

        # Initialize orchestrator
        orchestrator = ProfitabilityProofOrchestrator(config)

        if args.report_only:
            # Generate report only
            report_file = await orchestrator.generate_report_only()
            print(f"\n📄 Profitability validation report generated: {report_file}")

        elif args.monitor_only:
            # Monitor existing campaign
            if not await orchestrator.initialize_components():
                logger.error("❌ Failed to initialize components for monitoring")
                return 1

            status_data = await orchestrator.monitor_existing_campaign()
            print(f"\n📊 Monitoring data retrieved successfully")

        else:
            # Start new profitability validation campaign
            logger.info("🚀 Starting FXML4 Profitability Validation Campaign")

            if not await orchestrator.initialize_components():
                logger.error("❌ Failed to initialize components")
                return 1

            # Run the campaign
            result = await orchestrator.start_profitability_campaign()

            if result.success:
                print(f"\n🎉 PROFITABILITY VALIDATION SUCCESSFUL!")
                print(
                    f"   ✅ Target Annual Return: {config.target_annual_return_pct}% - ACHIEVED: {result.annual_return:.2f}%"
                )
                print(
                    f"   ✅ Maximum Drawdown Limit: {config.max_drawdown_pct}% - ACTUAL: {result.max_drawdown:.2f}%"
                )
                print(f"   📈 Campaign Duration: {config.campaign_duration_days} days")
                print(f"   📊 System proven profitable and ready for live trading!")
                return 0
            else:
                print(f"\n⚠️  PROFITABILITY VALIDATION INCOMPLETE")
                print(
                    f"   📊 Current Annual Return: {result.annual_return:.2f}% (Target: {config.target_annual_return_pct}%)"
                )
                print(
                    f"   📉 Current Drawdown: {result.max_drawdown:.2f}% (Limit: {config.max_drawdown_pct}%)"
                )
                print(f"   ⏱️  Campaign may need more time or parameter adjustment")
                return 2

    except KeyboardInterrupt:
        logger.info("🛑 Campaign interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        if args.verbose:
            logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
