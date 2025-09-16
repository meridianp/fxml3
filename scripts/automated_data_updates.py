#!/usr/bin/env python3
"""
FXML4 Automated Data Updates - Daily Backfill System

Maintains data freshness by automatically backfilling recent data gaps
and integrating real-time broker feeds for complete data continuity.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import schedule

# Add FXML4 to path
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/automated_updates.log"),
    ],
)
logger = logging.getLogger(__name__)


class AutomatedDataUpdater:
    """Automated data update system for maintaining freshness."""

    def __init__(self, data_path: str = "/polygon"):
        """Initialize automated updater."""
        self.data_path = Path(data_path)
        self.processed_path = self.data_path / "processed"
        self.logs_path = self.data_path / "logs" / "automated_updates"
        self.logs_path.mkdir(parents=True, exist_ok=True)

        # Major currency pairs to maintain
        self.major_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD"]

        # API configuration
        self.polygon_api_key = os.getenv("POLYGON_API_KEY")

        logger.info("Automated Data Updater initialized")

    def detect_staleness(self) -> Dict[str, Any]:
        """Detect data staleness across all major pairs."""
        logger.info("Detecting data staleness...")

        current_date = date.today()
        staleness_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "current_date": current_date.isoformat(),
            "pairs_analyzed": 0,
            "stale_pairs": [],
            "fresh_pairs": [],
            "update_needed": False,
        }

        for symbol in self.major_pairs:
            symbol_path = self.processed_path / f"C_{symbol}"

            if not symbol_path.exists():
                logger.warning(f"No data path for {symbol}")
                continue

            staleness_report["pairs_analyzed"] += 1

            # Find latest data date
            latest_date = None
            for year_dir in symbol_path.iterdir():
                if not year_dir.name.startswith("year="):
                    continue

                year = int(year_dir.name.split("=")[1])

                for month_dir in year_dir.iterdir():
                    if not month_dir.name.startswith("month="):
                        continue

                    month = int(month_dir.name.split("=")[1])

                    for day_dir in month_dir.iterdir():
                        if not day_dir.name.startswith("day="):
                            continue

                        day = int(day_dir.name.split("=")[1])
                        data_file = day_dir / "data.parquet.gz"

                        if data_file.exists():
                            file_date = date(year, month, day)
                            if latest_date is None or file_date > latest_date:
                                latest_date = file_date

            if latest_date:
                days_stale = (current_date - latest_date).days

                pair_info = {
                    "symbol": symbol,
                    "latest_date": latest_date.isoformat(),
                    "days_stale": days_stale,
                }

                if days_stale > 1:  # More than 1 day stale
                    staleness_report["stale_pairs"].append(pair_info)
                    staleness_report["update_needed"] = True
                    logger.info(f"{symbol}: {days_stale} days stale")
                else:
                    staleness_report["fresh_pairs"].append(pair_info)
                    logger.info(f"{symbol}: Fresh ({days_stale} days)")

        logger.info(
            f"Staleness analysis: {len(staleness_report['stale_pairs'])} stale, {len(staleness_report['fresh_pairs'])} fresh"
        )
        return staleness_report

    async def update_stale_data(self) -> Dict[str, Any]:
        """Update all stale data to current date."""
        logger.info("Starting automated data update...")

        # Check staleness
        staleness = self.detect_staleness()

        if not staleness["update_needed"]:
            logger.info("All data is fresh - no updates needed")
            return {
                "status": "success",
                "message": "No updates needed",
                "pairs_updated": 0,
            }

        if not self.polygon_api_key:
            logger.error("No Polygon API key configured - cannot update data")
            return {
                "status": "error",
                "message": "No Polygon API key",
                "pairs_updated": 0,
            }

        update_results = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "pairs_updated": 0,
            "total_records_added": 0,
            "pair_results": [],
        }

        # Update each stale pair
        for pair_info in staleness["stale_pairs"]:
            symbol = pair_info["symbol"]
            latest_date = pair_info["latest_date"]

            # Calculate date range to backfill (from day after latest to today)
            start_date = datetime.fromisoformat(latest_date).date() + timedelta(days=1)
            end_date = date.today() - timedelta(
                days=1
            )  # Don't include today (may be incomplete)

            if start_date <= end_date:
                logger.info(f"Updating {symbol} from {start_date} to {end_date}")

                # Run backfill using our existing system
                import subprocess

                cmd = [
                    "python",
                    "scripts/polygon_backfill_system.py",
                    "--backfill",
                    symbol,
                    "--start",
                    start_date.isoformat(),
                    "--end",
                    end_date.isoformat(),
                ]

                try:
                    env = os.environ.copy()
                    env["POLYGON_API_KEY"] = self.polygon_api_key

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        env=env,
                        timeout=300,  # 5 minute timeout
                    )

                    if result.returncode == 0:
                        # Parse the JSON output
                        try:
                            output_lines = result.stdout.strip().split("\n")
                            json_line = output_lines[0]  # First line should be JSON
                            backfill_result = json.loads(json_line)

                            pair_result = {
                                "symbol": symbol,
                                "status": "success",
                                "files_created": backfill_result.get(
                                    "files_created", 0
                                ),
                                "records_processed": backfill_result.get(
                                    "records_processed", 0
                                ),
                                "start_date": start_date.isoformat(),
                                "end_date": end_date.isoformat(),
                            }

                            update_results["pairs_updated"] += 1
                            update_results[
                                "total_records_added"
                            ] += backfill_result.get("records_processed", 0)

                            logger.info(
                                f"✅ {symbol}: {backfill_result.get('records_processed', 0)} records added"
                            )

                        except json.JSONDecodeError:
                            pair_result = {
                                "symbol": symbol,
                                "status": "success_no_details",
                                "message": "Backfill completed but couldn't parse details",
                            }
                            update_results["pairs_updated"] += 1
                    else:
                        pair_result = {
                            "symbol": symbol,
                            "status": "error",
                            "error": result.stderr,
                        }
                        logger.error(f"❌ {symbol}: {result.stderr}")

                except subprocess.TimeoutExpired:
                    pair_result = {
                        "symbol": symbol,
                        "status": "timeout",
                        "error": "Backfill timed out after 5 minutes",
                    }
                    logger.error(f"❌ {symbol}: Backfill timed out")

                update_results["pair_results"].append(pair_result)
            else:
                logger.info(f"{symbol}: Already up to date")

        # Save update log
        log_file = (
            self.logs_path / f"update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(log_file, "w") as f:
            json.dump(update_results, f, indent=2)

        logger.info(
            f"Update completed: {update_results['pairs_updated']} pairs, {update_results['total_records_added']} records"
        )
        return update_results

    def run_daily_update(self):
        """Run daily update job."""
        logger.info("🔄 Starting daily automated update...")

        try:
            result = asyncio.run(self.update_stale_data())

            if result["status"] == "success":
                logger.info(
                    f"✅ Daily update completed successfully: {result['pairs_updated']} pairs updated"
                )
            else:
                logger.error(
                    f"❌ Daily update failed: {result.get('message', 'Unknown error')}"
                )

        except Exception as e:
            logger.error(f"💥 Daily update crashed: {e}")
            import traceback

            traceback.print_exc()

    def start_scheduler(self):
        """Start the automated scheduler."""
        logger.info("🚀 Starting automated data update scheduler...")

        # Schedule daily updates at 6 AM UTC (after market close)
        schedule.every().day.at("06:00").do(self.run_daily_update)

        # Schedule freshness checks every 4 hours
        schedule.every(4).hours.do(self.detect_staleness)

        logger.info("📅 Scheduled jobs:")
        logger.info("   - Daily updates: 06:00 UTC")
        logger.info("   - Freshness checks: Every 4 hours")

        # Run initial freshness check
        logger.info("🔍 Running initial freshness check...")
        self.detect_staleness()

        # Main scheduler loop
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="FXML4 Automated Data Updates")
    parser.add_argument(
        "--check-staleness", action="store_true", help="Check data staleness"
    )
    parser.add_argument(
        "--update-now", action="store_true", help="Run update immediately"
    )
    parser.add_argument(
        "--start-scheduler", action="store_true", help="Start automated scheduler"
    )

    args = parser.parse_args()

    updater = AutomatedDataUpdater()

    if args.check_staleness:
        staleness = updater.detect_staleness()
        print(json.dumps(staleness, indent=2))

    elif args.update_now:
        result = asyncio.run(updater.update_stale_data())
        print(json.dumps(result, indent=2))

    elif args.start_scheduler:
        updater.start_scheduler()

    else:
        print("FXML4 Automated Data Updates")
        print("============================")
        print("Maintains data freshness with automated backfill")
        print()
        print("Commands:")
        print("  --check-staleness : Check current data staleness")
        print("  --update-now     : Run updates immediately")
        print("  --start-scheduler: Start automated daily scheduler")


if __name__ == "__main__":
    main()
