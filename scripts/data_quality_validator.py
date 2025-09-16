#!/usr/bin/env python3
"""
FXML4 Data Quality Validator
Advanced validation system for detecting data anomalies, gaps, and quality issues.
"""

import asyncio
import json
import logging
import os
import sys
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Add FXML4 to path
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/tmp/data_quality.log")],
)
logger = logging.getLogger(__name__)


@dataclass
class DataGap:
    """Represents a missing data gap."""

    symbol: str
    start_date: date
    end_date: date
    duration_days: int
    severity: str  # minor, major, critical


@dataclass
class PriceAnomaly:
    """Represents a price data anomaly."""

    symbol: str
    timestamp: datetime
    anomaly_type: str  # spike, gap, invalid_ohlc, etc.
    severity: str
    details: Dict[str, Any]


@dataclass
class QualityMetrics:
    """Data quality metrics for a symbol."""

    symbol: str
    total_records: int
    date_range: Tuple[date, date]
    completeness_score: float  # 0-1
    accuracy_score: float  # 0-1
    consistency_score: float  # 0-1
    freshness_score: float  # 0-1
    overall_quality: float  # 0-1
    gaps: List[DataGap]
    anomalies: List[PriceAnomaly]


class DataQualityValidator:
    """Comprehensive data quality validation system."""

    def __init__(self, data_path: str = "/polygon/processed"):
        """Initialize validator."""
        self.data_path = Path(data_path)
        self.major_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD"]

        # Quality thresholds
        self.thresholds = {
            "price_spike_factor": 0.01,  # 1% price spike threshold
            "volume_anomaly_factor": 10.0,  # 10x volume anomaly
            "missing_data_minor": 0.05,  # 5% missing = minor
            "missing_data_major": 0.15,  # 15% missing = major
            "missing_data_critical": 0.30,  # 30% missing = critical
            "freshness_hours_good": 24,  # < 24h = good
            "freshness_hours_stale": 72,  # > 72h = stale
        }

        logger.info("Data Quality Validator initialized")

    def detect_data_gaps(
        self, symbol: str, start_date: date, end_date: date
    ) -> List[DataGap]:
        """Detect gaps in data for a symbol."""
        logger.info(f"Detecting data gaps for {symbol} from {start_date} to {end_date}")

        symbol_path = self.data_path / f"C_{symbol}"
        if not symbol_path.exists():
            return [
                DataGap(
                    symbol,
                    start_date,
                    end_date,
                    (end_date - start_date).days,
                    "critical",
                )
            ]

        gaps = []
        current_date = start_date
        gap_start = None

        while current_date <= end_date:
            file_path = (
                symbol_path
                / f"year={current_date.year}"
                / f"month={current_date.month}"
                / f"day={current_date.day}"
                / "data.parquet.gz"
            )

            file_exists = file_path.exists()

            # Check if file has data
            has_data = False
            if file_exists:
                try:
                    import pyarrow.parquet as pq

                    table = pq.read_table(file_path)
                    has_data = len(table) > 0
                except Exception as e:
                    logger.warning(f"Error reading {file_path}: {e}")
                    has_data = False

            if not has_data:
                if gap_start is None:
                    gap_start = current_date
            else:
                if gap_start is not None:
                    # End of gap
                    gap_duration = (current_date - gap_start).days
                    severity = self._classify_gap_severity(gap_duration)
                    gaps.append(
                        DataGap(
                            symbol,
                            gap_start,
                            current_date - timedelta(days=1),
                            gap_duration,
                            severity,
                        )
                    )
                    gap_start = None

            current_date += timedelta(days=1)

        # Handle gap extending to end
        if gap_start is not None:
            gap_duration = (end_date - gap_start).days + 1
            severity = self._classify_gap_severity(gap_duration)
            gaps.append(DataGap(symbol, gap_start, end_date, gap_duration, severity))

        logger.info(f"Found {len(gaps)} data gaps for {symbol}")
        return gaps

    def _classify_gap_severity(self, duration_days: int) -> str:
        """Classify gap severity based on duration."""
        if duration_days <= 1:
            return "minor"
        elif duration_days <= 7:
            return "major"
        else:
            return "critical"

    def analyze_price_data(self, df: pd.DataFrame, symbol: str) -> List[PriceAnomaly]:
        """Analyze price data for anomalies."""
        anomalies = []

        if df is None or len(df) == 0:
            return anomalies

        try:
            # Ensure we have required columns
            required_cols = ["open", "high", "low", "close"]
            if not all(col in df.columns for col in required_cols):
                return anomalies

            # 1. OHLC consistency check
            invalid_ohlc = (
                (df["high"] < df["open"])
                | (df["high"] < df["close"])
                | (df["low"] > df["open"])
                | (df["low"] > df["close"])
                | (df["high"] < df["low"])
            )

            for idx in df[invalid_ohlc].index:
                anomalies.append(
                    PriceAnomaly(
                        symbol=symbol,
                        timestamp=idx,
                        anomaly_type="invalid_ohlc",
                        severity="major",
                        details={
                            "open": df.loc[idx, "open"],
                            "high": df.loc[idx, "high"],
                            "low": df.loc[idx, "low"],
                            "close": df.loc[idx, "close"],
                        },
                    )
                )

            # 2. Price spike detection
            df["returns"] = df["close"].pct_change()
            spike_threshold = self.thresholds["price_spike_factor"]

            price_spikes = np.abs(df["returns"]) > spike_threshold
            for idx in df[price_spikes].index:
                if pd.notna(df.loc[idx, "returns"]):
                    anomalies.append(
                        PriceAnomaly(
                            symbol=symbol,
                            timestamp=idx,
                            anomaly_type="price_spike",
                            severity=(
                                "major"
                                if abs(df.loc[idx, "returns"]) > spike_threshold * 2
                                else "minor"
                            ),
                            details={
                                "return": df.loc[idx, "returns"],
                                "threshold": spike_threshold,
                                "price": df.loc[idx, "close"],
                            },
                        )
                    )

            # 3. Price gap detection (difference between close and next open)
            if len(df) > 1:
                df["price_gap"] = df["open"] - df["close"].shift(1)
                df["gap_percentage"] = df["price_gap"] / df["close"].shift(1)

                significant_gaps = np.abs(df["gap_percentage"]) > spike_threshold / 2
                for idx in df[significant_gaps].index:
                    if pd.notna(df.loc[idx, "gap_percentage"]):
                        anomalies.append(
                            PriceAnomaly(
                                symbol=symbol,
                                timestamp=idx,
                                anomaly_type="price_gap",
                                severity="minor",
                                details={
                                    "gap_percentage": df.loc[idx, "gap_percentage"],
                                    "gap_amount": df.loc[idx, "price_gap"],
                                },
                            )
                        )

            # 4. Volume anomaly detection
            if "volume" in df.columns:
                volume_median = df["volume"].median()
                volume_threshold = self.thresholds["volume_anomaly_factor"]

                volume_anomalies = df["volume"] > (volume_median * volume_threshold)
                for idx in df[volume_anomalies].index:
                    anomalies.append(
                        PriceAnomaly(
                            symbol=symbol,
                            timestamp=idx,
                            anomaly_type="volume_spike",
                            severity="minor",
                            details={
                                "volume": df.loc[idx, "volume"],
                                "median_volume": volume_median,
                                "multiple": df.loc[idx, "volume"] / volume_median,
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Error analyzing price data for {symbol}: {e}")

        return anomalies

    def calculate_quality_scores(
        self,
        symbol: str,
        total_records: int,
        date_range: Tuple[date, date],
        gaps: List[DataGap],
        anomalies: List[PriceAnomaly],
    ) -> Dict[str, float]:
        """Calculate various quality scores."""

        # Completeness score (based on gaps)
        total_expected_days = (date_range[1] - date_range[0]).days + 1
        missing_days = sum(gap.duration_days for gap in gaps)
        completeness_score = max(0, 1 - (missing_days / total_expected_days))

        # Accuracy score (based on anomalies)
        major_anomalies = len([a for a in anomalies if a.severity == "major"])
        critical_anomalies = len([a for a in anomalies if a.severity == "critical"])

        if total_records > 0:
            anomaly_rate = (
                len(anomalies) + major_anomalies * 2 + critical_anomalies * 5
            ) / total_records
            accuracy_score = max(0, 1 - min(anomaly_rate, 1.0))
        else:
            accuracy_score = 0.0

        # Consistency score (based on critical gaps and anomalies)
        critical_issues = (
            len([g for g in gaps if g.severity == "critical"]) + critical_anomalies
        )
        consistency_score = max(
            0, 1 - (critical_issues * 0.2)
        )  # Each critical issue reduces by 20%

        # Freshness score (based on latest data age)
        if date_range[1]:
            days_since_latest = (date.today() - date_range[1]).days
            if days_since_latest <= 1:
                freshness_score = 1.0
            elif days_since_latest <= 7:
                freshness_score = 0.8
            elif days_since_latest <= 30:
                freshness_score = 0.5
            else:
                freshness_score = 0.2
        else:
            freshness_score = 0.0

        # Overall quality (weighted average)
        overall_quality = (
            completeness_score * 0.3
            + accuracy_score * 0.3
            + consistency_score * 0.2
            + freshness_score * 0.2
        )

        return {
            "completeness_score": completeness_score,
            "accuracy_score": accuracy_score,
            "consistency_score": consistency_score,
            "freshness_score": freshness_score,
            "overall_quality": overall_quality,
        }

    async def validate_symbol(self, symbol: str, days_back: int = 30) -> QualityMetrics:
        """Comprehensive validation for a single symbol."""
        logger.info(f"Validating data quality for {symbol}")

        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)

        # Detect data gaps
        gaps = self.detect_data_gaps(symbol, start_date, end_date)

        # Load and analyze data
        anomalies = []
        total_records = 0
        earliest_date = None
        latest_date = None

        symbol_path = self.data_path / f"C_{symbol}"
        if symbol_path.exists():
            current_date = start_date
            all_data = []

            while current_date <= end_date:
                file_path = (
                    symbol_path
                    / f"year={current_date.year}"
                    / f"month={current_date.month}"
                    / f"day={current_date.day}"
                    / "data.parquet.gz"
                )

                if file_path.exists():
                    try:
                        import pyarrow.parquet as pq

                        table = pq.read_table(file_path)
                        df_day = table.to_pandas()

                        if len(df_day) > 0:
                            # Set timestamp as index if it's a column
                            if "timestamp" in df_day.columns:
                                df_day["timestamp"] = pd.to_datetime(
                                    df_day["timestamp"]
                                )
                                df_day.set_index("timestamp", inplace=True)

                            all_data.append(df_day)
                            total_records += len(df_day)

                            if earliest_date is None:
                                earliest_date = current_date
                            latest_date = current_date

                    except Exception as e:
                        logger.warning(f"Error loading {file_path}: {e}")

                current_date += timedelta(days=1)

            # Analyze combined data for anomalies
            if all_data:
                combined_df = pd.concat(all_data).sort_index()
                # Sample data for anomaly detection (too much data can be slow)
                if len(combined_df) > 10000:
                    combined_df = combined_df.sample(n=10000).sort_index()

                anomalies = self.analyze_price_data(combined_df, symbol)

        # Calculate quality scores
        date_range = (earliest_date or start_date, latest_date or start_date)
        scores = self.calculate_quality_scores(
            symbol, total_records, date_range, gaps, anomalies
        )

        return QualityMetrics(
            symbol=symbol,
            total_records=total_records,
            date_range=date_range,
            gaps=gaps,
            anomalies=anomalies,
            **scores,
        )

    async def run_comprehensive_validation(
        self, symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run comprehensive validation for multiple symbols."""
        if symbols is None:
            symbols = self.major_pairs

        logger.info(f"Running comprehensive validation for {len(symbols)} symbols")

        # Validate each symbol
        validation_tasks = [self.validate_symbol(symbol) for symbol in symbols]
        results = await asyncio.gather(*validation_tasks)

        # Compile overall report
        symbol_metrics = {result.symbol: result for result in results}

        # Summary statistics
        overall_quality_scores = [metrics.overall_quality for metrics in results]
        total_gaps = sum(len(metrics.gaps) for metrics in results)
        total_anomalies = sum(len(metrics.anomalies) for metrics in results)

        # Classification
        high_quality_symbols = [
            s for s, m in symbol_metrics.items() if m.overall_quality >= 0.8
        ]
        medium_quality_symbols = [
            s for s, m in symbol_metrics.items() if 0.5 <= m.overall_quality < 0.8
        ]
        low_quality_symbols = [
            s for s, m in symbol_metrics.items() if m.overall_quality < 0.5
        ]

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbols_analyzed": len(symbols),
            "symbol_metrics": {
                symbol: {
                    "total_records": metrics.total_records,
                    "date_range": [
                        metrics.date_range[0].isoformat(),
                        metrics.date_range[1].isoformat(),
                    ],
                    "completeness_score": metrics.completeness_score,
                    "accuracy_score": metrics.accuracy_score,
                    "consistency_score": metrics.consistency_score,
                    "freshness_score": metrics.freshness_score,
                    "overall_quality": metrics.overall_quality,
                    "gaps_count": len(metrics.gaps),
                    "anomalies_count": len(metrics.anomalies),
                    "gaps": [
                        {
                            "start": gap.start_date.isoformat(),
                            "end": gap.end_date.isoformat(),
                            "duration": gap.duration_days,
                            "severity": gap.severity,
                        }
                        for gap in metrics.gaps[:10]
                    ],  # Limit to 10
                    "anomalies": [
                        {
                            "timestamp": (
                                anomaly.timestamp.isoformat()
                                if hasattr(anomaly.timestamp, "isoformat")
                                else str(anomaly.timestamp)
                            ),
                            "type": anomaly.anomaly_type,
                            "severity": anomaly.severity,
                        }
                        for anomaly in metrics.anomalies[:10]
                    ],  # Limit to 10
                }
                for symbol, metrics in symbol_metrics.items()
            },
            "summary": {
                "average_quality_score": (
                    np.mean(overall_quality_scores) if overall_quality_scores else 0
                ),
                "total_gaps": total_gaps,
                "total_anomalies": total_anomalies,
                "high_quality_symbols": high_quality_symbols,
                "medium_quality_symbols": medium_quality_symbols,
                "low_quality_symbols": low_quality_symbols,
            },
            "recommendations": self._generate_recommendations(symbol_metrics),
        }

        logger.info(
            f"Validation completed: {len(high_quality_symbols)} high quality, "
            f"{len(medium_quality_symbols)} medium quality, {len(low_quality_symbols)} low quality"
        )

        return report

    def _generate_recommendations(
        self, symbol_metrics: Dict[str, QualityMetrics]
    ) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        for symbol, metrics in symbol_metrics.items():
            # Data freshness recommendations
            if metrics.freshness_score < 0.5:
                recommendations.append(f"Update data for {symbol} - data is stale")

            # Gap recommendations
            critical_gaps = [g for g in metrics.gaps if g.severity == "critical"]
            if critical_gaps:
                recommendations.append(
                    f"Fix critical data gaps for {symbol} - {len(critical_gaps)} gaps found"
                )

            # Quality recommendations
            if metrics.overall_quality < 0.5:
                recommendations.append(
                    f"Investigate data quality issues for {symbol} - score: {metrics.overall_quality:.2f}"
                )

            # Anomaly recommendations
            major_anomalies = [
                a for a in metrics.anomalies if a.severity in ["major", "critical"]
            ]
            if len(major_anomalies) > 10:
                recommendations.append(
                    f"Review price anomalies for {symbol} - {len(major_anomalies)} significant anomalies"
                )

        # Global recommendations
        all_quality_scores = [m.overall_quality for m in symbol_metrics.values()]
        if all_quality_scores and np.mean(all_quality_scores) < 0.7:
            recommendations.append(
                "Overall data quality is below acceptable threshold - consider comprehensive data refresh"
            )

        return recommendations


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="FXML4 Data Quality Validator")
    parser.add_argument("--symbols", nargs="+", help="Symbols to validate")
    parser.add_argument("--days", type=int, default=30, help="Days back to analyze")
    parser.add_argument("--output", "-o", help="Output file for validation report")

    args = parser.parse_args()

    async def run_validation():
        validator = DataQualityValidator()
        report = await validator.run_comprehensive_validation(args.symbols)

        # Save report
        if args.output:
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"Report saved to {args.output}")

        # Print summary
        print(json.dumps(report, indent=2, default=str))

    asyncio.run(run_validation())


if __name__ == "__main__":
    main()
