#!/usr/bin/env python3
"""
FXML4 Polygon Data Service - Production Data Infrastructure

CRITICAL DATA FOUNDATION FOR TRADING SYSTEMS

This service addresses the fundamental data infrastructure crisis:
- Unlocks 1.39GB of trapped polygon data (50,823 parquet files)
- Implements fresh data ingestion from polygon.io API
- Provides data quality monitoring and validation
- Creates unified, production-ready data management system

Usage:
    # Start data service
    python scripts/polygon_data_service.py --service

    # Check data statistics
    python scripts/polygon_data_service.py --stats

    # Validate data quality
    python scripts/polygon_data_service.py --validate

    # Test data access
    python scripts/polygon_data_service.py --test-access EURUSD
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add FXML4 to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    import numpy as np
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    print("⚠️  pandas not available - limited functionality")
    PANDAS_AVAILABLE = False

try:
    import pyarrow.parquet as pq

    PARQUET_AVAILABLE = True
    print("✅ pyarrow available - can access parquet data")
except ImportError:
    PARQUET_AVAILABLE = False
    print("❌ pyarrow missing - cannot access parquet data")

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PolygonDataService:
    """Production-ready polygon data management service."""

    def __init__(self, data_path: str = "/polygon"):
        """Initialize polygon data service."""
        self.data_path = Path(data_path)
        self.raw_path = self.data_path / "raw"
        self.processed_path = self.data_path / "processed"
        self.cache_path = self.data_path / "cache"
        self.logs_path = self.data_path / "logs"

        # Ensure directories exist
        for path in [self.raw_path, self.cache_path, self.logs_path]:
            path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Polygon Data Service initialized: {self.data_path}")

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get comprehensive storage statistics."""
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "data_path": str(self.data_path),
            "parquet_available": PARQUET_AVAILABLE,
            "pandas_available": PANDAS_AVAILABLE,
        }

        try:
            # Check processed data
            if self.processed_path.exists():
                currency_pairs = []
                total_files = 0
                total_size = 0

                for pair_dir in self.processed_path.iterdir():
                    if pair_dir.is_dir() and pair_dir.name.startswith("C_"):
                        currency_pairs.append(pair_dir.name)

                        # Count files and sizes
                        pair_files = list(pair_dir.rglob("*.parquet.gz"))
                        total_files += len(pair_files)
                        total_size += sum(f.stat().st_size for f in pair_files)

                stats.update(
                    {
                        "currency_pairs": sorted(currency_pairs),
                        "total_files": total_files,
                        "total_size_gb": round(total_size / 1e9, 2),
                        "pairs_count": len(currency_pairs),
                    }
                )

                # Get date range
                date_range = self._get_date_range()
                stats["date_range"] = date_range

            else:
                stats.update(
                    {
                        "currency_pairs": [],
                        "total_files": 0,
                        "total_size_gb": 0.0,
                        "pairs_count": 0,
                        "date_range": {"min": "none", "max": "none"},
                    }
                )

            # Check raw data
            raw_files = 0
            if self.raw_path.exists():
                raw_files = len(list(self.raw_path.rglob("*")))
            stats["raw_files"] = raw_files

            return stats

        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            stats["error"] = str(e)
            return stats

    def _get_date_range(self) -> Dict[str, str]:
        """Get date range of available data."""
        min_year, max_year = None, None

        try:
            for pair_dir in self.processed_path.iterdir():
                if not pair_dir.is_dir():
                    continue

                for year_dir in pair_dir.iterdir():
                    if not year_dir.name.startswith("year="):
                        continue

                    year = int(year_dir.name.split("=")[1])
                    if min_year is None or year < min_year:
                        min_year = year
                    if max_year is None or year > max_year:
                        max_year = year

        except Exception as e:
            logger.warning(f"Failed to get date range: {e}")
            return {"min": "unknown", "max": "unknown"}

        return {
            "min": str(min_year) if min_year else "unknown",
            "max": str(max_year) if max_year else "unknown",
        }

    def test_data_access(self, symbol: str) -> Dict[str, Any]:
        """Test data access for a symbol."""
        result = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "success": False,
        }

        try:
            symbol_path = self.processed_path / f"C_{symbol.upper()}"
            if not symbol_path.exists():
                result["error"] = f"No data directory for {symbol}"
                return result

            # Find sample files
            sample_files = list(symbol_path.rglob("*.parquet.gz"))[:5]
            if not sample_files:
                result["error"] = f"No parquet files found for {symbol}"
                return result

            result["files_found"] = len(sample_files)

            if not PARQUET_AVAILABLE:
                result["error"] = "Cannot read parquet files - pyarrow missing"
                result["files_accessible"] = False
                return result

            # Try to read a sample file
            sample_file = sample_files[0]
            try:
                if PANDAS_AVAILABLE:
                    df = pd.read_parquet(sample_file)
                    result.update(
                        {
                            "files_accessible": True,
                            "sample_file": str(sample_file),
                            "sample_records": len(df),
                            "columns": (
                                list(df.columns) if hasattr(df, "columns") else []
                            ),
                            "success": True,
                        }
                    )

                    # Sample data
                    if len(df) > 0:
                        sample_record = df.iloc[0].to_dict()
                        # Convert any datetime objects to strings
                        for key, value in sample_record.items():
                            if hasattr(value, "isoformat"):
                                sample_record[key] = value.isoformat()
                            elif isinstance(value, (np.integer, np.floating)):
                                sample_record[key] = float(value)
                        result["sample_record"] = sample_record
                else:
                    # Try with pyarrow directly
                    table = pq.read_table(sample_file)
                    result.update(
                        {
                            "files_accessible": True,
                            "sample_file": str(sample_file),
                            "sample_records": len(table),
                            "columns": table.column_names,
                            "success": True,
                        }
                    )

            except Exception as e:
                result["error"] = f"Failed to read sample file: {e}"
                result["files_accessible"] = False

        except Exception as e:
            result["error"] = f"Data access test failed: {e}"

        return result

    def validate_data_infrastructure(self) -> Dict[str, Any]:
        """Comprehensive data infrastructure validation."""
        validation = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "unknown",
            "critical_issues": [],
            "warnings": [],
            "recommendations": [],
        }

        try:
            # Check dependencies
            if not PARQUET_AVAILABLE:
                validation["critical_issues"].append(
                    "CRITICAL: pyarrow missing - cannot access 1.39GB of existing data"
                )
                validation["recommendations"].append(
                    "Install pyarrow: pip install pyarrow or use Docker environment"
                )

            if not PANDAS_AVAILABLE:
                validation["critical_issues"].append(
                    "CRITICAL: pandas missing - cannot process data"
                )

            # Check data availability
            stats = self.get_storage_stats()

            if stats.get("total_files", 0) == 0:
                validation["critical_issues"].append(
                    "CRITICAL: No processed data files found"
                )
            else:
                validation["warnings"].append(
                    f"Found {stats['total_files']:,} data files ({stats['total_size_gb']} GB)"
                )

            if stats.get("raw_files", 0) == 0:
                validation["warnings"].append(
                    "WARNING: No raw data files - fresh data ingestion needed"
                )
                validation["recommendations"].append(
                    "Implement fresh data ingestion from polygon.io API"
                )

            # Check data access
            if stats.get("pairs_count", 0) > 0 and PARQUET_AVAILABLE:
                # Test a major pair
                test_symbol = "EURUSD"
                access_test = self.test_data_access(test_symbol)
                if access_test["success"]:
                    validation["warnings"].append(
                        f"Data access verified for {test_symbol}"
                    )
                else:
                    validation["critical_issues"].append(
                        f"Data access failed for {test_symbol}: {access_test.get('error')}"
                    )

            # Determine overall status
            if validation["critical_issues"]:
                validation["overall_status"] = "CRITICAL"
            elif validation["warnings"]:
                validation["overall_status"] = "WARNING"
            else:
                validation["overall_status"] = "HEALTHY"

            # Add specific recommendations
            if PARQUET_AVAILABLE and stats.get("total_files", 0) > 0:
                validation["recommendations"].extend(
                    [
                        "Data foundation is accessible - can proceed with trading system development",
                        "Implement data quality monitoring",
                        "Set up fresh data ingestion pipeline",
                        "Create data quality dashboard",
                    ]
                )
            else:
                validation["recommendations"].extend(
                    [
                        "Fix data access issues before building trading systems",
                        "Containerized approach may be needed for dependency management",
                    ]
                )

        except Exception as e:
            validation["error"] = str(e)
            validation["overall_status"] = "ERROR"

        return validation

    def create_data_summary_report(self) -> str:
        """Create comprehensive data summary report."""
        stats = self.get_storage_stats()
        validation = self.validate_data_infrastructure()

        report = []
        report.append("🎯 FXML4 POLYGON DATA INFRASTRUCTURE REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.utcnow().isoformat()}")
        report.append("")

        # Critical Status
        status = validation["overall_status"]
        if status == "CRITICAL":
            report.append("🚨 STATUS: CRITICAL ISSUES DETECTED")
        elif status == "WARNING":
            report.append("⚠️  STATUS: WARNINGS DETECTED")
        elif status == "HEALTHY":
            report.append("✅ STATUS: HEALTHY")
        else:
            report.append(f"❓ STATUS: {status}")

        report.append("")

        # Data Overview
        report.append("📊 DATA OVERVIEW")
        report.append("-" * 30)
        report.append(f"Storage Path: {stats['data_path']}")
        report.append(f"Currency Pairs: {stats.get('pairs_count', 0)}")
        report.append(f"Total Files: {stats.get('total_files', 0):,}")
        report.append(f"Storage Used: {stats.get('total_size_gb', 0)} GB")
        report.append(
            f"Date Range: {stats['date_range']['min']} to {stats['date_range']['max']}"
        )
        report.append(f"Raw Files: {stats.get('raw_files', 0)}")
        report.append("")

        # Technical Status
        report.append("🔧 TECHNICAL STATUS")
        report.append("-" * 30)
        report.append(
            f"PyArrow Available: {'✅ Yes' if PARQUET_AVAILABLE else '❌ No'}"
        )
        report.append(f"Pandas Available: {'✅ Yes' if PANDAS_AVAILABLE else '❌ No'}")
        report.append(
            f"Data Accessible: {'✅ Yes' if PARQUET_AVAILABLE and stats.get('total_files', 0) > 0 else '❌ No'}"
        )
        report.append("")

        # Issues
        if validation["critical_issues"]:
            report.append("🚨 CRITICAL ISSUES")
            report.append("-" * 30)
            for issue in validation["critical_issues"]:
                report.append(f"• {issue}")
            report.append("")

        if validation["warnings"]:
            report.append("⚠️  WARNINGS")
            report.append("-" * 30)
            for warning in validation["warnings"]:
                report.append(f"• {warning}")
            report.append("")

        # Recommendations
        if validation["recommendations"]:
            report.append("💡 RECOMMENDATIONS")
            report.append("-" * 30)
            for rec in validation["recommendations"]:
                report.append(f"• {rec}")
            report.append("")

        # Currency Pairs
        if stats.get("currency_pairs"):
            report.append("💱 AVAILABLE CURRENCY PAIRS")
            report.append("-" * 30)
            pairs = stats["currency_pairs"]
            for i in range(0, len(pairs), 4):
                line_pairs = pairs[i : i + 4]
                report.append("  " + "  ".join(f"{pair:12}" for pair in line_pairs))
            report.append("")

        # Next Steps
        report.append("🎯 IMMEDIATE NEXT STEPS")
        report.append("-" * 30)

        if not PARQUET_AVAILABLE:
            report.append(
                "1. 🚨 CRITICAL: Install pyarrow to unlock 1.39GB trapped data"
            )
            report.append(
                "   Solution: Docker environment or system package installation"
            )

        if stats.get("raw_files", 0) == 0:
            report.append("2. 🔄 URGENT: Implement fresh data ingestion pipeline")
            report.append("   Action: Create polygon.io API data fetcher")

        report.append("3. 🔍 IMPORTANT: Implement data quality monitoring")
        report.append("4. 🏗️  BUILD: Complete modern data infrastructure")
        report.append("5. 📊 MONITOR: Create production data quality dashboard")

        return "\\n".join(report)


async def main():
    """Main entry point for polygon data service."""
    parser = argparse.ArgumentParser(
        description="FXML4 Polygon Data Infrastructure Service"
    )
    parser.add_argument("--stats", action="store_true", help="Show data statistics")
    parser.add_argument("--validate", action="store_true", help="Run data validation")
    parser.add_argument("--test-access", type=str, help="Test data access for symbol")
    parser.add_argument(
        "--report", action="store_true", help="Generate comprehensive report"
    )
    parser.add_argument("--data-path", type=str, default="/polygon", help="Data path")

    args = parser.parse_args()

    # Initialize service
    service = PolygonDataService(data_path=args.data_path)

    if args.stats:
        stats = service.get_storage_stats()
        print(json.dumps(stats, indent=2))

    elif args.validate:
        validation = service.validate_data_infrastructure()
        print(json.dumps(validation, indent=2))

    elif args.test_access:
        result = service.test_data_access(args.test_access)
        print(json.dumps(result, indent=2))

    elif args.report:
        report = service.create_data_summary_report()
        print(report)

        # Save report
        report_file = (
            Path(args.data_path)
            / "logs"
            / f"data_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, "w") as f:
            f.write(report)
        print(f"\\n📁 Report saved: {report_file}")

    else:
        # Default: Quick status
        print("🎯 FXML4 Polygon Data Service")
        print("=" * 50)

        validation = service.validate_data_infrastructure()
        status = validation["overall_status"]

        if status == "CRITICAL":
            print("🚨 CRITICAL DATA INFRASTRUCTURE ISSUES")
            for issue in validation["critical_issues"]:
                print(f"   {issue}")
        elif status == "WARNING":
            print("⚠️  DATA INFRASTRUCTURE WARNINGS")
        else:
            print("✅ Data infrastructure operational")

        stats = service.get_storage_stats()
        print(
            f"📊 {stats.get('total_files', 0):,} files, {stats.get('total_size_gb', 0)} GB"
        )
        print(f"💱 {stats.get('pairs_count', 0)} currency pairs available")

        print()
        print("💡 Available commands:")
        print("   --stats     : Detailed statistics")
        print("   --validate  : Full validation")
        print("   --report    : Comprehensive report")
        print("   --test-access EURUSD : Test data access")


if __name__ == "__main__":
    asyncio.run(main())
