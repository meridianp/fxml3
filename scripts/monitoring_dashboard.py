#!/usr/bin/env python3
"""
FXML4 Monitoring Dashboard
Comprehensive real-time monitoring dashboard for infrastructure and data quality.
"""

import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add FXML4 to path
sys.path.append(str(Path(__file__).parent.parent))


class MonitoringDashboard:
    """Real-time monitoring dashboard for FXML4 infrastructure."""

    def __init__(self):
        """Initialize monitoring dashboard."""
        self.script_dir = Path(__file__).parent
        self.health_monitor = self.script_dir / "infrastructure_health_monitor.py"
        self.quality_validator = self.script_dir / "data_quality_validator.py"
        self.data_updater = self.script_dir / "automated_data_updates.py"
        self.venv_path = Path(__file__).parent.parent / "venv-monitoring"

    def _run_script(self, script_path: Path, args: List[str] = None) -> Dict[str, Any]:
        """Run a monitoring script and return JSON result."""
        cmd = [f"{self.venv_path}/bin/python", str(script_path)]
        if args:
            cmd.extend(args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env={"POLYGON_API_KEY": "6VNaiPLmpdAft7A36nsKQptPEdsFDs2p"},
            )

            if result.returncode == 0:
                # Try to parse JSON from stdout
                lines = result.stdout.strip().split("\\n")
                for line in lines:
                    if line.startswith("{"):
                        return json.loads(line)
                return {"status": "success", "output": result.stdout}
            else:
                return {"status": "error", "error": result.stderr}

        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "Script timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def get_infrastructure_health(self) -> Dict[str, Any]:
        """Get current infrastructure health status."""
        return self._run_script(self.health_monitor)

    async def get_data_quality(self) -> Dict[str, Any]:
        """Get data quality assessment."""
        return self._run_script(self.quality_validator, ["--days", "7"])

    async def get_data_staleness(self) -> Dict[str, Any]:
        """Get data staleness information."""
        return self._run_script(self.data_updater, ["--check-staleness"])

    def format_service_status(self, services: Dict[str, Any]) -> str:
        """Format service status for display."""
        output = []
        status_symbols = {"healthy": "✅", "degraded": "⚠️ ", "unhealthy": "❌"}

        for service_name, service_data in services.items():
            status = service_data.get("status", "unknown")
            symbol = status_symbols.get(status, "❓")
            response_time = service_data.get("response_time_ms", 0)

            output.append(
                f"  {symbol} {service_name.upper()}: {status} ({response_time:.1f}ms)"
            )

            # Show service details
            details = service_data.get("details", {})
            if service_name == "redis" and "version" in details:
                output.append(
                    f"     Redis {details['version']}, {details['connected_clients']} clients, {details['used_memory']}"
                )
            elif service_name == "system":
                cpu = details.get("cpu_percent", 0)
                mem = details.get("memory_percent", 0) * 100
                disk = details.get("disk_percent", 0) * 100
                output.append(
                    f"     CPU: {cpu:.1f}%, RAM: {mem:.1f}%, Disk: {disk:.1f}%"
                )
            elif service_name == "docker":
                running_containers = len(
                    [
                        c
                        for c in details.values()
                        if isinstance(c, dict) and c.get("status") == "running"
                    ]
                )
                output.append(f"     {running_containers} containers running")

        return "\\n".join(output)

    def format_data_quality(self, quality_data: Dict[str, Any]) -> str:
        """Format data quality information for display."""
        if quality_data.get("status") != "success":
            return f"❌ Data Quality Check Failed: {quality_data.get('error', 'Unknown error')}"

        summary = quality_data.get("summary", {})
        avg_quality = summary.get("average_quality_score", 0)
        total_gaps = summary.get("total_gaps", 0)
        total_anomalies = summary.get("total_anomalies", 0)

        high_quality = len(summary.get("high_quality_symbols", []))
        medium_quality = len(summary.get("medium_quality_symbols", []))
        low_quality = len(summary.get("low_quality_symbols", []))

        output = [
            f"📊 Data Quality Overview:",
            f"  Average Quality Score: {avg_quality:.2f}",
            f"  ✅ High Quality: {high_quality} symbols",
            f"  ⚠️  Medium Quality: {medium_quality} symbols",
            f"  ❌ Low Quality: {low_quality} symbols",
            f"  Data Gaps: {total_gaps}",
            f"  Anomalies: {total_anomalies}",
        ]

        # Show recommendations
        recommendations = quality_data.get("recommendations", [])
        if recommendations:
            output.append("\\n🔧 Recommendations:")
            for rec in recommendations[:3]:  # Show top 3
                output.append(f"  • {rec}")

        return "\\n".join(output)

    def format_data_staleness(self, staleness_data: Dict[str, Any]) -> str:
        """Format data staleness information for display."""
        if staleness_data.get("status") == "error":
            return f"❌ Staleness Check Failed: {staleness_data.get('error', 'Unknown error')}"

        stale_pairs = staleness_data.get("stale_pairs", [])
        fresh_pairs = staleness_data.get("fresh_pairs", [])
        update_needed = staleness_data.get("update_needed", False)

        output = [
            f"📅 Data Freshness Status:",
            f"  Fresh Pairs: {len(fresh_pairs)}",
            f"  Stale Pairs: {len(stale_pairs)}",
            f"  Update Needed: {'Yes' if update_needed else 'No'}",
        ]

        if stale_pairs:
            output.append("\\n⏰ Stale Data:")
            for pair in stale_pairs[:6]:  # Show all major pairs
                symbol = pair["symbol"]
                days = pair["days_stale"]
                latest = pair["latest_date"]
                staleness_icon = "🟡" if days <= 3 else "🔴" if days <= 7 else "🟣"
                output.append(
                    f"  {staleness_icon} {symbol}: {days} days (latest: {latest})"
                )

        return "\\n".join(output)

    async def generate_dashboard(self) -> str:
        """Generate complete monitoring dashboard."""
        print("🔄 Generating monitoring dashboard...")

        # Run all checks in parallel
        health_task = asyncio.create_task(self.get_infrastructure_health())
        quality_task = asyncio.create_task(self.get_data_quality())
        staleness_task = asyncio.create_task(self.get_data_staleness())

        health_data = await health_task
        quality_data = await quality_task
        staleness_data = await staleness_task

        # Build dashboard
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        dashboard = []
        dashboard.append("=" * 80)
        dashboard.append(f"🎯 FXML4 MONITORING DASHBOARD - {current_time}")
        dashboard.append("=" * 80)

        # Overall status
        if health_data.get("status") != "error":
            overall_status = health_data.get("overall_status", "unknown")
            total_alerts = health_data.get("summary", {}).get("total_alerts", 0)

            status_icon = {"healthy": "🟢", "degraded": "🟡", "unhealthy": "🔴"}.get(
                overall_status, "⚪"
            )

            dashboard.append(
                f"\\n{status_icon} OVERALL STATUS: {overall_status.upper()}"
            )
            if total_alerts > 0:
                dashboard.append(f"🚨 Active Alerts: {total_alerts}")
        else:
            dashboard.append("\\n🔴 OVERALL STATUS: MONITORING ERROR")

        dashboard.append("\\n" + "-" * 80)

        # Infrastructure Health
        dashboard.append("\\n🏗️  INFRASTRUCTURE HEALTH")
        dashboard.append("-" * 40)
        if health_data.get("status") != "error":
            services = health_data.get("services", {})
            dashboard.append(self.format_service_status(services))
        else:
            dashboard.append(
                f"❌ Health check failed: {health_data.get('error', 'Unknown error')}"
            )

        # Data Quality
        dashboard.append("\\n" + "-" * 80)
        dashboard.append("\\n" + self.format_data_quality(quality_data))

        # Data Freshness
        dashboard.append("\\n" + "-" * 80)
        dashboard.append("\\n" + self.format_data_staleness(staleness_data))

        # Alerts Summary
        dashboard.append("\\n" + "-" * 80)
        if health_data.get("status") != "error":
            alerts = health_data.get("alerts", [])
            if alerts:
                dashboard.append("\\n🚨 ACTIVE ALERTS:")
                for i, alert in enumerate(alerts[:10], 1):  # Show top 10 alerts
                    dashboard.append(f"  {i:2d}. {alert}")
                if len(alerts) > 10:
                    dashboard.append(f"     ... and {len(alerts) - 10} more alerts")
            else:
                dashboard.append("\\n✅ NO ACTIVE ALERTS")

        # Footer
        dashboard.append("\\n" + "=" * 80)
        dashboard.append("💡 Use individual scripts for detailed analysis:")
        dashboard.append("   • scripts/infrastructure_health_monitor.py")
        dashboard.append("   • scripts/data_quality_validator.py")
        dashboard.append("   • scripts/automated_data_updates.py")
        dashboard.append("=" * 80)

        return "\\n".join(dashboard)

    async def run_continuous_monitoring(self, interval_seconds: int = 300):
        """Run continuous monitoring with dashboard updates."""
        print(f"🚀 Starting continuous monitoring (interval: {interval_seconds}s)")
        print("Press Ctrl+C to stop\\n")

        try:
            while True:
                dashboard = await self.generate_dashboard()

                # Clear screen and show dashboard
                print("\\x1b[2J\\x1b[H")  # Clear screen and move cursor to top
                print(dashboard)

                # Wait for next update
                print(f"\\n⏳ Next update in {interval_seconds} seconds...")
                await asyncio.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\\n\\n👋 Monitoring stopped by user")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="FXML4 Monitoring Dashboard")
    parser.add_argument(
        "--continuous", "-c", action="store_true", help="Run continuous monitoring"
    )
    parser.add_argument(
        "--interval", "-i", type=int, default=300, help="Update interval in seconds"
    )
    parser.add_argument("--save", "-s", help="Save dashboard to file")

    args = parser.parse_args()

    dashboard = MonitoringDashboard()

    if args.continuous:
        await dashboard.run_continuous_monitoring(args.interval)
    else:
        # Single dashboard generation
        dashboard_text = await dashboard.generate_dashboard()
        print(dashboard_text)

        if args.save:
            with open(args.save, "w") as f:
                f.write(dashboard_text)
            print(f"\\n💾 Dashboard saved to {args.save}")


if __name__ == "__main__":
    asyncio.run(main())
