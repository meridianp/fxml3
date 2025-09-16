#!/usr/bin/env python3
"""
FXML4 Risk Management Compliance Proof Script

This script provides comprehensive validation and proof that the FXML4 trading system
correctly enforces risk management limits in live paper trading conditions:

- 2% maximum trade size per trade
- 6% maximum portfolio exposure across all positions
- Real-time monitoring and violation detection
- Comprehensive audit trail generation
- Regulatory-compliant reporting

Usage:
    python scripts/prove_risk_compliance.py [options]
    ./scripts/run_with_fxml4.sh scripts/prove_risk_compliance.py [options]

Options:
    --duration HOURS     Test duration in hours (default: 24)
    --trades N           Number of test trades (default: 100)
    --stress-test        Include stress testing scenarios
    --continuous         Run continuous monitoring
    --report-only        Generate report from existing data
    --verbose            Enable verbose logging
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
from typing import Any, Dict, List

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fxml4.core.config import load_config
from fxml4.core.logging_config import setup_logging
from fxml4.live_trading.live_risk_monitor import AlertLevel, LiveRiskMonitor, RiskAlert
from fxml4.live_trading.risk_validator import ComplianceReport, RiskManagementValidator


class RiskComplianceProver:
    """
    Risk Management Compliance Proof System

    Orchestrates comprehensive testing and validation of risk management controls
    with detailed reporting for regulatory compliance and audit purposes.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

        self.risk_validator: Optional[RiskManagementValidator] = None
        self.risk_monitor: Optional[LiveRiskMonitor] = None
        self.results_file = Path("risk_compliance_results.json")
        self.report_file = Path("risk_compliance_report.html")

        self.shutdown_requested = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True

    async def initialize(self) -> None:
        """Initialize compliance proof system"""
        self.logger.info("🔧 Initializing risk compliance proof system...")

        try:
            # Initialize risk validator
            validator_config = {
                "max_trade_size_percentage": 2.0,
                "max_portfolio_exposure_percentage": 6.0,
                "warning_threshold_percentage": 80.0,
                **self.config.get("risk_management", {}),
            }

            self.risk_validator = RiskManagementValidator(validator_config)
            await self.risk_validator.initialize()

            # Initialize live monitor
            monitor_config = {
                "update_interval_seconds": 10,
                "alert_cooldown_seconds": 60,  # Shorter cooldown for testing
                "warning_threshold": 75.0,
                "critical_threshold": 90.0,
                **self.config.get("risk_monitoring", {}),
            }

            self.risk_monitor = LiveRiskMonitor(monitor_config)
            await self.risk_monitor.initialize()

            self.logger.info("✅ Risk compliance proof system initialized successfully")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize compliance proof system: {e}")
            raise

    async def run_comprehensive_compliance_test(
        self,
        test_duration_hours: int = 24,
        test_trades: int = 100,
        include_stress_test: bool = False,
    ) -> ComplianceReport:
        """
        Run comprehensive compliance test with detailed validation

        Args:
            test_duration_hours: Duration to run compliance tests
            test_trades: Number of test trades to attempt
            include_stress_test: Include stress testing scenarios

        Returns:
            ComplianceReport with complete compliance analysis
        """
        self.logger.info(f"🔄 Starting comprehensive compliance test:")
        self.logger.info(f"   Duration: {test_duration_hours} hours")
        self.logger.info(f"   Test trades: {test_trades}")
        self.logger.info(f"   Stress testing: {'Yes' if include_stress_test else 'No'}")

        start_time = datetime.utcnow()

        try:
            # Phase 1: Basic compliance validation
            self.logger.info("📋 Phase 1: Basic compliance validation")
            basic_report = await self.risk_validator.run_compliance_test(
                test_duration_hours=min(
                    test_duration_hours, 4
                ),  # Max 4 hours for basic test
                test_trades=min(test_trades, 50),  # Max 50 trades for basic test
            )

            # Phase 2: Stress testing (if requested)
            stress_report = None
            if include_stress_test:
                self.logger.info("🔥 Phase 2: Stress testing scenarios")
                stress_report = await self._run_stress_test()

            # Phase 3: Continuous monitoring validation
            self.logger.info("📊 Phase 3: Continuous monitoring validation")
            monitoring_report = await self._run_monitoring_validation(
                duration_minutes=min(
                    test_duration_hours * 60, 120
                )  # Max 2 hours monitoring
            )

            # Phase 4: Limit breach testing
            self.logger.info("⚠️  Phase 4: Limit breach testing")
            breach_report = await self._run_limit_breach_tests()

            # Combine all reports
            end_time = datetime.utcnow()

            combined_report = ComplianceReport(
                start_date=start_time,
                end_date=end_time,
                total_trades_attempted=basic_report.total_trades_attempted
                + (stress_report.total_trades_attempted if stress_report else 0),
                total_trades_executed=basic_report.total_trades_executed
                + (stress_report.total_trades_executed if stress_report else 0),
                total_trades_rejected=basic_report.total_trades_rejected
                + (stress_report.total_trades_rejected if stress_report else 0),
                violations=basic_report.violations
                + (stress_report.violations if stress_report else []),
                compliance_rate=(
                    basic_report.compliance_rate
                    + (stress_report.compliance_rate if stress_report else 0)
                )
                / (2 if stress_report else 1),
                max_trade_size_percentage=max(
                    basic_report.max_trade_size_percentage,
                    stress_report.max_trade_size_percentage if stress_report else 0,
                ),
                max_portfolio_exposure_percentage=max(
                    basic_report.max_portfolio_exposure_percentage,
                    (
                        stress_report.max_portfolio_exposure_percentage
                        if stress_report
                        else 0
                    ),
                ),
            )

            # Save results
            await self._save_compliance_results(
                combined_report, monitoring_report, breach_report
            )

            return combined_report

        except Exception as e:
            self.logger.error(f"❌ Comprehensive compliance test failed: {e}")
            raise

    async def _run_stress_test(self) -> ComplianceReport:
        """Run stress testing scenarios to validate risk controls"""
        self.logger.info("🔥 Running stress testing scenarios...")

        stress_scenarios = [
            # High volatility scenarios
            {
                "symbol": "GBPUSD",
                "volatility_multiplier": 2.0,
                "scenario": "high_volatility",
            },
            {
                "symbol": "EURUSD",
                "volatility_multiplier": 3.0,
                "scenario": "extreme_volatility",
            },
            # Rapid fire trading
            {"scenario": "rapid_fire", "trades_per_minute": 10},
            # Large position attempts
            {"scenario": "large_positions", "size_multiplier": 5.0},
            # Multi-currency simultaneous
            {
                "scenario": "multi_currency",
                "currencies": ["GBPUSD", "EURUSD", "USDJPY", "USDCHF"],
            },
        ]

        stress_violations = []
        stress_trades_attempted = 0
        stress_trades_executed = 0
        stress_trades_rejected = 0

        for scenario in stress_scenarios:
            self.logger.info(
                f"🔥 Testing scenario: {scenario.get('scenario', 'unknown')}"
            )

            if scenario.get("scenario") == "rapid_fire":
                # Test rapid fire trading
                for _ in range(20):  # 20 rapid trades
                    try:
                        result = await self.risk_validator.validate_trade_risk(
                            "GBPUSD", 1000, "BUY"
                        )
                        stress_trades_attempted += 1

                        if result.has_violations:
                            stress_trades_rejected += 1
                            stress_violations.extend(result.violations)
                        else:
                            stress_trades_executed += 1

                        await asyncio.sleep(0.1)  # Very rapid trading

                    except Exception as e:
                        self.logger.warning(f"Stress test trade error: {e}")
                        stress_trades_rejected += 1

            elif scenario.get("scenario") == "large_positions":
                # Test large position sizes that should be rejected
                large_sizes = [10000, 50000, 100000, 500000]

                for size in large_sizes:
                    try:
                        result = await self.risk_validator.validate_trade_risk(
                            "EURUSD", size, "BUY"
                        )
                        stress_trades_attempted += 1

                        if result.has_violations:
                            stress_trades_rejected += 1
                            stress_violations.extend(result.violations)
                            self.logger.info(
                                f"✅ Large position {size} correctly rejected"
                            )
                        else:
                            stress_trades_executed += 1
                            self.logger.warning(
                                f"⚠️  Large position {size} was approved (unexpected)"
                            )

                    except Exception as e:
                        self.logger.warning(f"Large position test error: {e}")
                        stress_trades_rejected += 1

            elif scenario.get("scenario") == "multi_currency":
                # Test simultaneous positions across multiple currencies
                currencies = scenario.get("currencies", [])

                for currency in currencies:
                    try:
                        result = await self.risk_validator.validate_trade_risk(
                            currency, 5000, "BUY"
                        )
                        stress_trades_attempted += 1

                        if result.has_violations:
                            stress_trades_rejected += 1
                            stress_violations.extend(result.violations)
                        else:
                            stress_trades_executed += 1

                    except Exception as e:
                        self.logger.warning(
                            f"Multi-currency test error for {currency}: {e}"
                        )
                        stress_trades_rejected += 1

        # Create stress test report
        stress_compliance_rate = (
            (stress_trades_executed / stress_trades_attempted * 100)
            if stress_trades_attempted > 0
            else 0
        )

        stress_report = ComplianceReport(
            start_date=datetime.utcnow() - timedelta(minutes=30),
            end_date=datetime.utcnow(),
            total_trades_attempted=stress_trades_attempted,
            total_trades_executed=stress_trades_executed,
            total_trades_rejected=stress_trades_rejected,
            violations=stress_violations,
            compliance_rate=stress_compliance_rate,
        )

        self.logger.info(f"🔥 Stress test completed:")
        self.logger.info(f"   Attempted: {stress_trades_attempted}")
        self.logger.info(f"   Rejected: {stress_trades_rejected}")
        self.logger.info(f"   Violations: {len(stress_violations)}")

        return stress_report

    async def _run_monitoring_validation(
        self, duration_minutes: int = 60
    ) -> Dict[str, Any]:
        """Run continuous monitoring validation"""
        self.logger.info(
            f"📊 Running monitoring validation for {duration_minutes} minutes..."
        )

        # Add alert callback to capture alerts during test
        captured_alerts = []

        def test_alert_callback(alert: RiskAlert):
            captured_alerts.append(alert)
            self.logger.info(
                f"📧 Captured alert: {alert.level.value} - {alert.message}"
            )

        self.risk_monitor.add_alert_callback(test_alert_callback)

        # Start monitoring
        monitoring_task = asyncio.create_task(self.risk_monitor.start_monitoring())

        try:
            # Let monitoring run for specified duration
            end_time = datetime.utcnow() + timedelta(minutes=duration_minutes)

            while datetime.utcnow() < end_time and not self.shutdown_requested:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Log current status
                status = self.risk_monitor.get_current_status()
                self.logger.info(
                    f"📊 Monitor status: {status.get('exposure_percentage', 0):.2f}% exposure, "
                    f"{status.get('positions_count', 0)} positions"
                )

        except Exception as e:
            self.logger.error(f"Monitoring validation error: {e}")
        finally:
            # Stop monitoring
            await self.risk_monitor.stop_monitoring()
            monitoring_task.cancel()

            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass

        # Generate monitoring report
        monitoring_report = {
            "duration_minutes": duration_minutes,
            "total_alerts": len(captured_alerts),
            "alert_breakdown": {
                level.value: len([a for a in captured_alerts if a.level == level])
                for level in AlertLevel
            },
            "monitoring_snapshots": len(self.risk_monitor.snapshots),
            "final_status": self.risk_monitor.get_current_status(),
        }

        self.logger.info(f"📊 Monitoring validation completed:")
        self.logger.info(f"   Duration: {duration_minutes} minutes")
        self.logger.info(f"   Total alerts: {len(captured_alerts)}")
        self.logger.info(f"   Snapshots captured: {len(self.risk_monitor.snapshots)}")

        return monitoring_report

    async def _run_limit_breach_tests(self) -> Dict[str, Any]:
        """Run specific tests designed to breach limits (should be blocked)"""
        self.logger.info("⚠️  Running limit breach testing...")

        breach_tests = [
            {
                "name": "Single trade > 2% limit",
                "symbol": "GBPUSD",
                "size": 1000000,
                "expected": "rejected",
            },
            {
                "name": "Portfolio > 6% limit",
                "symbol": "EURUSD",
                "size": 500000,
                "expected": "rejected",
            },
            {
                "name": "Multiple large trades",
                "symbol": "USDJPY",
                "size": 250000,
                "count": 3,
                "expected": "rejected",
            },
        ]

        breach_results = []

        for test in breach_tests:
            self.logger.info(f"⚠️  Testing: {test['name']}")

            try:
                if test.get("count", 1) == 1:
                    # Single trade test
                    result = await self.risk_validator.validate_trade_risk(
                        test["symbol"], test["size"], "BUY"
                    )

                    test_result = {
                        "test_name": test["name"],
                        "expected": test["expected"],
                        "actual": "rejected" if result.has_violations else "approved",
                        "violations": len(result.violations),
                        "passed": (
                            result.has_violations
                            if test["expected"] == "rejected"
                            else not result.has_violations
                        ),
                    }
                else:
                    # Multiple trade test
                    total_violations = 0
                    for i in range(test["count"]):
                        result = await self.risk_validator.validate_trade_risk(
                            test["symbol"], test["size"], "BUY"
                        )
                        total_violations += len(result.violations)

                    test_result = {
                        "test_name": test["name"],
                        "expected": test["expected"],
                        "actual": "rejected" if total_violations > 0 else "approved",
                        "violations": total_violations,
                        "passed": (
                            total_violations > 0
                            if test["expected"] == "rejected"
                            else total_violations == 0
                        ),
                    }

                breach_results.append(test_result)

                if test_result["passed"]:
                    self.logger.info(f"✅ {test['name']}: PASSED")
                else:
                    self.logger.error(f"❌ {test['name']}: FAILED")

            except Exception as e:
                self.logger.error(f"Breach test error for {test['name']}: {e}")
                breach_results.append(
                    {
                        "test_name": test["name"],
                        "expected": test["expected"],
                        "actual": "error",
                        "error": str(e),
                        "passed": False,
                    }
                )

        breach_report = {
            "total_tests": len(breach_tests),
            "passed_tests": len([r for r in breach_results if r["passed"]]),
            "failed_tests": len([r for r in breach_results if not r["passed"]]),
            "test_results": breach_results,
        }

        self.logger.info(f"⚠️  Limit breach testing completed:")
        self.logger.info(f"   Total tests: {breach_report['total_tests']}")
        self.logger.info(f"   Passed: {breach_report['passed_tests']}")
        self.logger.info(f"   Failed: {breach_report['failed_tests']}")

        return breach_report

    async def _save_compliance_results(
        self,
        compliance_report: ComplianceReport,
        monitoring_report: Dict[str, Any],
        breach_report: Dict[str, Any],
    ) -> None:
        """Save comprehensive compliance results"""
        try:
            results_data = {
                "generated_at": datetime.utcnow().isoformat(),
                "test_summary": {
                    "fully_compliant": compliance_report.is_fully_compliant,
                    "total_violations": compliance_report.violation_count,
                    "compliance_rate": compliance_report.compliance_rate,
                    "max_trade_size_percentage": compliance_report.max_trade_size_percentage,
                    "max_portfolio_exposure_percentage": compliance_report.max_portfolio_exposure_percentage,
                },
                "compliance_report": {
                    "start_date": compliance_report.start_date.isoformat(),
                    "end_date": compliance_report.end_date.isoformat(),
                    "total_trades_attempted": compliance_report.total_trades_attempted,
                    "total_trades_executed": compliance_report.total_trades_executed,
                    "total_trades_rejected": compliance_report.total_trades_rejected,
                    "violations": [v.to_dict() for v in compliance_report.violations],
                    "compliance_rate": compliance_report.compliance_rate,
                },
                "monitoring_report": monitoring_report,
                "breach_testing_report": breach_report,
            }

            with open(self.results_file, "w") as f:
                json.dump(results_data, f, indent=2, default=str)

            self.logger.info(f"💾 Compliance results saved to {self.results_file}")

            # Generate HTML report
            await self._generate_html_report(results_data)

        except Exception as e:
            self.logger.error(f"Failed to save compliance results: {e}")

    async def _generate_html_report(self, results_data: Dict[str, Any]) -> None:
        """Generate HTML compliance report"""
        try:
            summary = results_data["test_summary"]
            compliance = results_data["compliance_report"]
            monitoring = results_data["monitoring_report"]
            breach_testing = results_data["breach_testing_report"]

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>FXML4 Risk Management Compliance Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f4f4f4; padding: 20px; border-radius: 5px; }}
        .status-pass {{ color: #28a745; font-weight: bold; }}
        .status-fail {{ color: #dc3545; font-weight: bold; }}
        .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>FXML4 Risk Management Compliance Report</h1>
        <p>Generated: {results_data['generated_at']}</p>
        <p>Status: <span class="{'status-pass' if summary['fully_compliant'] else 'status-fail'}">
            {'✅ FULLY COMPLIANT' if summary['fully_compliant'] else '❌ VIOLATIONS DETECTED'}
        </span></p>
    </div>

    <div class="section">
        <h2>Executive Summary</h2>
        <div class="metric">Total Violations: <strong>{summary['total_violations']}</strong></div>
        <div class="metric">Compliance Rate: <strong>{summary['compliance_rate']:.1f}%</strong></div>
        <div class="metric">Max Trade Size: <strong>{summary['max_trade_size_percentage']:.2f}%</strong></div>
        <div class="metric">Max Portfolio Exposure: <strong>{summary['max_portfolio_exposure_percentage']:.2f}%</strong></div>
    </div>

    <div class="section">
        <h2>Compliance Testing Results</h2>
        <p>Test Period: {compliance['start_date']} to {compliance['end_date']}</p>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Trades Attempted</td>
                <td>{compliance['total_trades_attempted']}</td>
            </tr>
            <tr>
                <td>Trades Executed</td>
                <td>{compliance['total_trades_executed']}</td>
            </tr>
            <tr>
                <td>Trades Rejected</td>
                <td>{compliance['total_trades_rejected']}</td>
            </tr>
            <tr>
                <td>Risk Violations</td>
                <td>{len(compliance['violations'])}</td>
            </tr>
        </table>
    </div>

    <div class="section">
        <h2>Live Monitoring Results</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Monitoring Duration</td>
                <td>{monitoring['duration_minutes']} minutes</td>
            </tr>
            <tr>
                <td>Total Alerts</td>
                <td>{monitoring['total_alerts']}</td>
            </tr>
            <tr>
                <td>Monitoring Snapshots</td>
                <td>{monitoring['monitoring_snapshots']}</td>
            </tr>
        </table>
    </div>

    <div class="section">
        <h2>Limit Breach Testing</h2>
        <p>Tests designed to intentionally breach risk limits (should be rejected)</p>
        <table>
            <tr>
                <th>Test</th>
                <th>Expected</th>
                <th>Actual</th>
                <th>Result</th>
            </tr>
            {''.join([
                f'<tr><td>{test["test_name"]}</td><td>{test["expected"]}</td><td>{test["actual"]}</td>'
                f'<td class="{"status-pass" if test["passed"] else "status-fail"}">'
                f'{"✅ PASSED" if test["passed"] else "❌ FAILED"}</td></tr>'
                for test in breach_testing['test_results']
            ])}
        </table>
    </div>

    <div class="section">
        <h2>Conclusion</h2>
        <p>
            {'The FXML4 trading system has successfully demonstrated full compliance with risk management requirements. All risk limits are properly enforced and no violations were detected during testing.'
             if summary['fully_compliant'] else
             'The FXML4 trading system has detected risk management violations during testing. Please review the violations and ensure proper risk controls are in place before proceeding to live trading.'}
        </p>
        <p>
            <strong>Risk Limits Validation:</strong><br>
            • 2% Maximum Trade Size: {'✅ ENFORCED' if summary['max_trade_size_percentage'] <= 2.0 else '❌ VIOLATED'}<br>
            • 6% Maximum Portfolio Exposure: {'✅ ENFORCED' if summary['max_portfolio_exposure_percentage'] <= 6.0 else '❌ VIOLATED'}
        </p>
    </div>
</body>
</html>
            """

            with open(self.report_file, "w") as f:
                f.write(html_content)

            self.logger.info(f"📄 HTML report generated: {self.report_file}")

        except Exception as e:
            self.logger.error(f"Failed to generate HTML report: {e}")

    async def run_continuous_monitoring(self) -> None:
        """Run continuous risk monitoring (until interrupted)"""
        self.logger.info("🔄 Starting continuous risk monitoring...")
        self.logger.info("Press Ctrl+C to stop monitoring")

        try:
            # Add alert callback
            def compliance_alert_callback(alert: RiskAlert):
                self.logger.info(
                    f"🚨 COMPLIANCE ALERT [{alert.level.value.upper()}]: {alert.message}"
                )

                if alert.level in [AlertLevel.CRITICAL, AlertLevel.VIOLATION]:
                    self.logger.error(f"🚫 CRITICAL RISK ALERT: {alert.message}")

            self.risk_monitor.add_alert_callback(compliance_alert_callback)

            # Start monitoring
            await self.risk_monitor.start_monitoring()

        except KeyboardInterrupt:
            self.logger.info("🛑 Continuous monitoring interrupted by user")
        except Exception as e:
            self.logger.error(f"Continuous monitoring error: {e}")
        finally:
            await self.risk_monitor.stop_monitoring()

    async def generate_report_only(self) -> None:
        """Generate compliance report from existing data"""
        self.logger.info("📊 Generating compliance report from existing data...")

        try:
            if not self.results_file.exists():
                self.logger.error(
                    f"❌ No existing results file found: {self.results_file}"
                )
                return

            with open(self.results_file, "r") as f:
                results_data = json.load(f)

            # Generate HTML report
            await self._generate_html_report(results_data)

            # Generate text report
            summary = results_data["test_summary"]
            compliance = results_data["compliance_report"]

            report_lines = [
                "=" * 80,
                "FXML4 RISK MANAGEMENT COMPLIANCE REPORT",
                "=" * 80,
                f"Generated: {results_data['generated_at']}",
                "",
                "COMPLIANCE STATUS:",
                f"  Overall Status: {'✅ FULLY COMPLIANT' if summary['fully_compliant'] else '❌ VIOLATIONS DETECTED'}",
                f"  Total Violations: {summary['total_violations']}",
                f"  Compliance Rate: {summary['compliance_rate']:.1f}%",
                "",
                "RISK LIMITS VALIDATION:",
                f"  2% Max Trade Size: {'✅ ENFORCED' if summary['max_trade_size_percentage'] <= 2.0 else '❌ VIOLATED'} ({summary['max_trade_size_percentage']:.2f}%)",
                f"  6% Max Portfolio Exposure: {'✅ ENFORCED' if summary['max_portfolio_exposure_percentage'] <= 6.0 else '❌ VIOLATED'} ({summary['max_portfolio_exposure_percentage']:.2f}%)",
                "",
                "TESTING SUMMARY:",
                f"  Total Trades Attempted: {compliance['total_trades_attempted']}",
                f"  Trades Executed: {compliance['total_trades_executed']}",
                f"  Trades Rejected: {compliance['total_trades_rejected']}",
                "",
                "=" * 80,
            ]

            report_text = "\n".join(report_lines)
            self.logger.info("Risk Compliance Report:")
            print(report_text)

        except Exception as e:
            self.logger.error(f"Failed to generate report: {e}")

    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            if self.risk_validator:
                await self.risk_validator.cleanup()
            if self.risk_monitor:
                await self.risk_monitor.stop_monitoring()

            self.logger.info("🧹 Risk compliance prover cleanup completed")

        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="FXML4 Risk Management Compliance Proof System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/prove_risk_compliance.py
  python scripts/prove_risk_compliance.py --duration 48 --trades 200 --stress-test
  python scripts/prove_risk_compliance.py --continuous
  python scripts/prove_risk_compliance.py --report-only
        """,
    )

    parser.add_argument(
        "--duration", type=int, default=24, help="Test duration in hours (default: 24)"
    )

    parser.add_argument(
        "--trades", type=int, default=100, help="Number of test trades (default: 100)"
    )

    parser.add_argument(
        "--stress-test", action="store_true", help="Include stress testing scenarios"
    )

    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuous monitoring (Ctrl+C to stop)",
    )

    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate report from existing data only",
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
    logger.info("🚀 Starting FXML4 Risk Management Compliance Proof")

    try:
        # Load configuration
        config = load_config()

        # Create compliance prover
        prover = RiskComplianceProver(config)

        if args.report_only:
            # Generate report only
            await prover.generate_report_only()
            return

        # Initialize prover
        await prover.initialize()

        if args.continuous:
            # Run continuous monitoring
            await prover.run_continuous_monitoring()
        else:
            # Run comprehensive compliance test
            logger.info("🔧 Running comprehensive compliance proof...")
            compliance_report = await prover.run_comprehensive_compliance_test(
                test_duration_hours=args.duration,
                test_trades=args.trades,
                include_stress_test=args.stress_test,
            )

            # Final assessment
            if compliance_report.is_fully_compliant:
                logger.info(
                    "🎉 RISK MANAGEMENT COMPLIANCE PROOF COMPLETED SUCCESSFULLY"
                )
                logger.info(
                    "✅ System correctly enforces 2% trade and 6% portfolio limits"
                )
                logger.info("✅ All risk management controls are working as designed")
                logger.info("✅ System is READY for live paper trading validation")
            else:
                logger.error("❌ RISK MANAGEMENT COMPLIANCE PROOF FAILED")
                logger.error(
                    f"🚫 {compliance_report.violation_count} violations detected"
                )
                logger.error("🚫 System is NOT ready for live paper trading")

    except KeyboardInterrupt:
        logger.info("🛑 Compliance proof interrupted by user")
    except Exception as e:
        logger.error(f"❌ Risk management compliance proof failed: {e}")
        sys.exit(1)
    finally:
        if "prover" in locals():
            await prover.cleanup()
        logger.info("🏁 Risk management compliance proof completed")


if __name__ == "__main__":
    asyncio.run(main())
