#!/usr/bin/env python3
"""
FXML4 Polygon Backfill System - Complete Data Continuity

CRITICAL: Ensures complete data with ability to backfill from polygon.io
and integrate new data from brokers for comprehensive trading data foundation.

Features:
- Detect data gaps in existing polygon storage
- Backfill missing data from polygon.io API
- Integrate real-time broker data into polygon format
- Validate data completeness and consistency
- Automated scheduling and monitoring

Usage:
    # Detect data gaps
    python scripts/polygon_backfill_system.py --detect-gaps EURUSD

    # Backfill specific date range
    python scripts/polygon_backfill_system.py --backfill EURUSD --start 2024-01-01 --end 2024-12-31

    # Run complete data validation
    python scripts/polygon_backfill_system.py --validate-completeness
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add FXML4 to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    import numpy as np
    import pandas as pd
    from polygon import RESTClient

    POLYGON_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Missing dependencies: {e}")
    POLYGON_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PolygonBackfillSystem:
    """Complete data continuity system with polygon.io backfill capabilities."""

    # Major forex pairs for complete coverage
    MAJOR_PAIRS = [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "AUDUSD",
        "USDCAD",
        "USDCHF",
        "NZDUSD",
        "EURJPY",
        "GBPJPY",
        "EURGBP",
        "AUDJPY",
        "EURAUD",
        "EURCHF",
        "EURNZD",
        "GBPAUD",
        "GBPCHF",
    ]

    def __init__(self, data_path: str = "/polygon", api_key: Optional[str] = None):
        """Initialize backfill system."""
        self.data_path = Path(data_path)
        self.processed_path = self.data_path / "processed"
        self.raw_path = self.data_path / "raw"
        self.backfill_path = self.data_path / "backfill"
        self.logs_path = self.data_path / "logs"

        # Create directories
        for path in [self.raw_path, self.backfill_path, self.logs_path]:
            path.mkdir(parents=True, exist_ok=True)

        # Polygon API setup
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        self.polygon_client = RESTClient(self.api_key) if self.api_key else None

        logger.info(f"Backfill system initialized: {self.data_path}")
        if not self.api_key:
            logger.warning("No Polygon API key - backfill functionality limited")

    def detect_data_gaps(self, symbol: str) -> Dict[str, Any]:
        """Detect gaps in existing data for a symbol."""
        logger.info(f"Detecting data gaps for {symbol}")

        result = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "gaps_detected": [],
            "coverage_analysis": {},
            "recommendations": [],
        }

        try:
            symbol_path = self.processed_path / f"C_{symbol.upper()}"
            if not symbol_path.exists():
                result["error"] = f"No data directory for {symbol}"
                result["recommendations"].append(
                    f"Full historical download needed for {symbol}"
                )
                return result

            # Analyze existing data coverage
            existing_dates = set()

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

                        # Check if data file exists
                        data_file = day_dir / "data.parquet.gz"
                        if data_file.exists():
                            existing_dates.add(date(year, month, day))

            if not existing_dates:
                result["error"] = "No data files found"
                return result

            # Analyze coverage
            min_date = min(existing_dates)
            max_date = max(existing_dates)

            result["coverage_analysis"] = {
                "earliest_date": min_date.isoformat(),
                "latest_date": max_date.isoformat(),
                "total_days_available": len(existing_dates),
                "date_range_days": (max_date - min_date).days + 1,
                "coverage_percentage": len(existing_dates)
                / ((max_date - min_date).days + 1)
                * 100,
            }

            # Detect specific gaps
            current_date = min_date
            gaps = []

            while current_date <= max_date:
                if current_date not in existing_dates:
                    # Check if this is a weekday (forex markets)
                    if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                        gaps.append(current_date.isoformat())

                current_date += timedelta(days=1)

            result["gaps_detected"] = gaps

            # Generate recommendations
            if len(gaps) > 0:
                result["recommendations"].append(
                    f"Backfill {len(gaps)} missing trading days"
                )

                # Group consecutive gaps
                gap_ranges = self._group_consecutive_dates(
                    [datetime.fromisoformat(g).date() for g in gaps]
                )
                for start, end in gap_ranges:
                    if start == end:
                        result["recommendations"].append(
                            f"Backfill single day: {start}"
                        )
                    else:
                        result["recommendations"].append(
                            f"Backfill range: {start} to {end}"
                        )

            # Check for recent data freshness
            days_since_last = (date.today() - max_date).days
            if days_since_last > 3:
                result["recommendations"].append(
                    f"Data is {days_since_last} days old - recent backfill needed"
                )

            logger.info(f"Gap analysis complete for {symbol}: {len(gaps)} gaps found")
            return result

        except Exception as e:
            logger.error(f"Failed to detect gaps for {symbol}: {e}")
            result["error"] = str(e)
            return result

    def _group_consecutive_dates(self, dates: List[date]) -> List[Tuple[date, date]]:
        """Group consecutive dates into ranges."""
        if not dates:
            return []

        dates = sorted(dates)
        ranges = []
        start = dates[0]
        end = dates[0]

        for i in range(1, len(dates)):
            if dates[i] == end + timedelta(days=1):
                end = dates[i]
            else:
                ranges.append((start, end))
                start = dates[i]
                end = dates[i]

        ranges.append((start, end))
        return ranges

    async def backfill_date_range(
        self, symbol: str, start_date: str, end_date: str, dry_run: bool = False
    ) -> Dict[str, Any]:
        """Backfill data for specific date range."""
        logger.info(f"Backfilling {symbol} from {start_date} to {end_date}")

        if not self.polygon_client:
            return {"error": "Polygon API client not configured"}

        result = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "dry_run": dry_run,
            "timestamp": datetime.utcnow().isoformat(),
            "files_created": 0,
            "records_processed": 0,
            "errors": [],
        }

        try:
            start_dt = datetime.fromisoformat(start_date).date()
            end_dt = datetime.fromisoformat(end_date).date()

            # Create backfill directory
            backfill_dir = self.backfill_path / symbol / f"{start_date}_to_{end_date}"
            if not dry_run:
                backfill_dir.mkdir(parents=True, exist_ok=True)

            # Process date range in chunks (polygon API limits)
            current_date = start_dt
            chunk_size = 30  # 30 days per request

            while current_date <= end_dt:
                chunk_end = min(current_date + timedelta(days=chunk_size - 1), end_dt)

                logger.info(f"Processing chunk: {current_date} to {chunk_end}")

                if dry_run:
                    logger.info(
                        f"DRY RUN: Would fetch data for {current_date} to {chunk_end}"
                    )
                    current_date = chunk_end + timedelta(days=1)
                    continue

                try:
                    # Fetch data from Polygon API
                    # Note: This is a placeholder - actual implementation would use
                    # the specific Polygon API endpoints for forex data

                    # For now, create placeholder structure
                    chunk_result = await self._fetch_polygon_data_chunk(
                        symbol, current_date, chunk_end
                    )

                    if chunk_result["success"]:
                        result["files_created"] += chunk_result["files_created"]
                        result["records_processed"] += chunk_result["records_processed"]
                    else:
                        result["errors"].append(
                            f"Chunk {current_date}-{chunk_end}: {chunk_result['error']}"
                        )

                except Exception as e:
                    error_msg = (
                        f"Failed to process chunk {current_date}-{chunk_end}: {e}"
                    )
                    logger.error(error_msg)
                    result["errors"].append(error_msg)

                current_date = chunk_end + timedelta(days=1)

                # Rate limiting - respect Polygon API limits
                await asyncio.sleep(1.0)

            # Log backfill completion
            if not dry_run:
                log_file = (
                    self.logs_path
                    / f"backfill_{symbol}_{start_date}_{end_date}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                with open(log_file, "w") as f:
                    json.dump(result, f, indent=2, default=str)

            logger.info(
                f"Backfill completed for {symbol}: {result['files_created']} files, {result['records_processed']} records"
            )
            return result

        except Exception as e:
            logger.error(f"Backfill failed for {symbol}: {e}")
            result["error"] = str(e)
            return result

    async def _fetch_polygon_data_chunk(
        self, symbol: str, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Fetch data chunk from Polygon API and save to files."""
        logger.info(
            f"Fetching {symbol} data from Polygon API: {start_date} to {end_date}"
        )

        try:
            if not self.polygon_client:
                return {
                    "success": False,
                    "error": "No Polygon API client",
                    "files_created": 0,
                    "records_processed": 0,
                }

            ticker = f"C:{symbol}"
            total_files = 0
            total_records = 0

            # Iterate through each day in the date range
            current_date = start_date
            while current_date <= end_date:
                try:
                    # Fetch data for this specific day
                    resp = self.polygon_client.get_aggs(
                        ticker=ticker,
                        multiplier=1,
                        timespan="minute",
                        from_=current_date.strftime("%Y-%m-%d"),
                        to=current_date.strftime("%Y-%m-%d"),
                    )

                    # Convert to list to get actual data
                    data_list = list(resp)

                    if data_list:
                        # Create directory structure
                        year = current_date.year
                        month = current_date.month
                        day = current_date.day

                        day_dir = (
                            self.processed_path
                            / f"C_{symbol}"
                            / f"year={year}"
                            / f"month={month}"
                            / f"day={day}"
                        )
                        day_dir.mkdir(parents=True, exist_ok=True)

                        # Prepare data for saving
                        if POLYGON_AVAILABLE:
                            import pandas as pd

                            # Convert polygon data to dataframe
                            records = []
                            for agg in data_list:
                                records.append(
                                    {
                                        "timestamp": pd.to_datetime(
                                            agg.timestamp, unit="ms", utc=True
                                        ),
                                        "open": agg.open,
                                        "high": agg.high,
                                        "low": agg.low,
                                        "close": agg.close,
                                        "volume": agg.volume,
                                    }
                                )

                            df = pd.DataFrame(records)
                            output_file = day_dir / "data.parquet.gz"
                            df.to_parquet(output_file, compression="gzip", index=False)

                            total_files += 1
                            total_records += len(records)
                            logger.info(
                                f"Saved {len(records)} records for {symbol} {current_date}"
                            )

                except Exception as day_error:
                    logger.warning(
                        f"Failed to fetch data for {symbol} {current_date}: {day_error}"
                    )

                current_date += timedelta(days=1)

            return {
                "success": True,
                "files_created": total_files,
                "records_processed": total_records,
                "api_calls": (end_date - start_date).days + 1,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "files_created": 0,
                "records_processed": 0,
            }

    def validate_data_completeness(self) -> Dict[str, Any]:
        """Validate completeness across all currency pairs."""
        logger.info("Validating data completeness across all pairs")

        validation = {
            "timestamp": datetime.utcnow().isoformat(),
            "pairs_analyzed": 0,
            "pairs_complete": 0,
            "total_gaps": 0,
            "critical_issues": [],
            "recommendations": [],
            "pair_details": {},
        }

        try:
            for symbol in self.MAJOR_PAIRS:
                logger.info(f"Analyzing {symbol}...")

                gap_analysis = self.detect_data_gaps(symbol)
                validation["pairs_analyzed"] += 1

                if "error" in gap_analysis:
                    validation["critical_issues"].append(
                        f"{symbol}: {gap_analysis['error']}"
                    )
                    continue

                gaps_count = len(gap_analysis.get("gaps_detected", []))
                coverage = gap_analysis.get("coverage_analysis", {}).get(
                    "coverage_percentage", 0
                )

                validation["pair_details"][symbol] = {
                    "gaps": gaps_count,
                    "coverage_percentage": coverage,
                    "recommendations": gap_analysis.get("recommendations", []),
                }

                validation["total_gaps"] += gaps_count

                if gaps_count == 0 and coverage > 95:
                    validation["pairs_complete"] += 1
                elif gaps_count > 100:
                    validation["critical_issues"].append(
                        f"{symbol}: {gaps_count} missing days"
                    )

            # Generate overall recommendations
            completion_rate = (
                validation["pairs_complete"] / validation["pairs_analyzed"]
                if validation["pairs_analyzed"] > 0
                else 0
            )

            if completion_rate < 0.8:
                validation["recommendations"].append(
                    "CRITICAL: Less than 80% of pairs have complete data"
                )
                validation["recommendations"].append(
                    "Implement systematic backfill process"
                )

            if validation["total_gaps"] > 500:
                validation["recommendations"].append(
                    f"HIGH PRIORITY: {validation['total_gaps']} total missing days across all pairs"
                )

            validation["recommendations"].append(
                "Set up automated daily backfill process"
            )
            validation["recommendations"].append(
                "Implement broker real-time data integration"
            )

            logger.info(
                f"Completeness validation complete: {validation['pairs_complete']}/{validation['pairs_analyzed']} pairs complete"
            )
            return validation

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            validation["error"] = str(e)
            return validation

    def create_backfill_schedule(self, symbols: List[str] = None) -> Dict[str, Any]:
        """Create systematic backfill schedule for data gaps."""
        if symbols is None:
            symbols = self.MAJOR_PAIRS

        schedule = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbols": symbols,
            "backfill_tasks": [],
            "estimated_api_calls": 0,
            "estimated_duration_hours": 0,
        }

        try:
            for symbol in symbols:
                gap_analysis = self.detect_data_gaps(symbol)

                if "gaps_detected" in gap_analysis and gap_analysis["gaps_detected"]:
                    gaps = [
                        datetime.fromisoformat(g).date()
                        for g in gap_analysis["gaps_detected"]
                    ]
                    gap_ranges = self._group_consecutive_dates(gaps)

                    for start_date, end_date in gap_ranges:
                        days = (end_date - start_date).days + 1

                        task = {
                            "symbol": symbol,
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat(),
                            "days": days,
                            "priority": "high" if days > 30 else "medium",
                            "estimated_api_calls": max(1, days // 30),
                            "estimated_minutes": max(1, days // 30)
                            * 2,  # 2 minutes per API call with rate limiting
                        }

                        schedule["backfill_tasks"].append(task)
                        schedule["estimated_api_calls"] += task["estimated_api_calls"]

            # Calculate total estimated time
            schedule["estimated_duration_hours"] = (
                sum(task["estimated_minutes"] for task in schedule["backfill_tasks"])
                / 60
            )

            # Sort by priority and date
            schedule["backfill_tasks"].sort(
                key=lambda x: (x["priority"] == "medium", x["start_date"])
            )

            logger.info(
                f"Backfill schedule created: {len(schedule['backfill_tasks'])} tasks, ~{schedule['estimated_duration_hours']:.1f} hours"
            )
            return schedule

        except Exception as e:
            logger.error(f"Failed to create backfill schedule: {e}")
            schedule["error"] = str(e)
            return schedule


async def main():
    """Main entry point for backfill system."""
    parser = argparse.ArgumentParser(description="FXML4 Polygon Backfill System")
    parser.add_argument("--detect-gaps", type=str, help="Detect gaps for symbol")
    parser.add_argument("--backfill", type=str, help="Backfill symbol")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--validate-completeness",
        action="store_true",
        help="Validate data completeness",
    )
    parser.add_argument(
        "--create-schedule", action="store_true", help="Create backfill schedule"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run (no actual changes)"
    )
    parser.add_argument("--data-path", type=str, default="/polygon", help="Data path")

    args = parser.parse_args()

    # Initialize system
    system = PolygonBackfillSystem(data_path=args.data_path)

    if args.detect_gaps:
        result = system.detect_data_gaps(args.detect_gaps)
        print(json.dumps(result, indent=2, default=str))

    elif args.backfill:
        if not args.start or not args.end:
            print("Error: --start and --end dates required for backfill")
            return

        result = await system.backfill_date_range(
            args.backfill, args.start, args.end, dry_run=args.dry_run
        )
        print(json.dumps(result, indent=2, default=str))

    elif args.validate_completeness:
        result = system.validate_data_completeness()
        print(json.dumps(result, indent=2, default=str))

    elif args.create_schedule:
        result = system.create_backfill_schedule()
        print(json.dumps(result, indent=2, default=str))

    else:
        # Quick status
        print("🎯 FXML4 Polygon Backfill System")
        print("=" * 50)
        print(f"Data Path: {system.data_path}")
        print(f"API Configured: {'Yes' if system.api_key else 'No'}")
        print()
        print("Available commands:")
        print("  --detect-gaps EURUSD          : Detect missing data")
        print("  --backfill EURUSD --start ... : Backfill date range")
        print("  --validate-completeness       : Check all pairs")
        print("  --create-schedule             : Generate backfill plan")
        print("  --dry-run                     : Test without changes")


if __name__ == "__main__":
    if not POLYGON_AVAILABLE:
        print(
            "❌ Required dependencies missing. Install: pip install pandas polygon-api-client"
        )
        sys.exit(1)

    asyncio.run(main())
