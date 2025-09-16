#!/usr/bin/env python
"""Comprehensive data quality check across all symbols."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import random
from collections import defaultdict

import numpy as np
import pandas as pd


def check_data_quality_for_file(file_path):
    """Check data quality for a single file."""
    try:
        df = pd.read_parquet(file_path)

        # Calculate statistics
        stats = {
            "rows": len(df),
            "unique_open": df["open"].nunique(),
            "unique_high": df["high"].nunique(),
            "unique_low": df["low"].nunique(),
            "unique_close": df["close"].nunique(),
            "open_std": df["open"].std(),
            "high_std": df["high"].std(),
            "low_std": df["low"].std(),
            "close_std": df["close"].std(),
            "price_range": df["high"].max() - df["low"].min(),
            "volume_sum": df["volume"].sum(),
            "is_flat": df["high"].nunique() == 1 and df["low"].nunique() == 1,
        }

        return stats
    except Exception as e:
        return {"error": str(e)}


def sample_symbol_data(symbol_dir, num_samples=10):
    """Sample random files from a symbol directory."""
    symbol_path = Path(f"input/{symbol_dir}")
    if not symbol_path.exists():
        return []

    # Find all parquet files
    all_files = list(symbol_path.rglob("*.parquet.gz"))

    # Sample random files
    if len(all_files) <= num_samples:
        sampled_files = all_files
    else:
        sampled_files = random.sample(all_files, num_samples)

    results = []
    for file_path in sampled_files:
        stats = check_data_quality_for_file(file_path)
        stats["file"] = str(file_path.relative_to(symbol_path))
        results.append(stats)

    return results


def main():
    """Run comprehensive data quality check."""
    print("Comprehensive Data Quality Check")
    print("=" * 80)

    # Check all symbols (excluding _REAL which is our generated data)
    symbols = ["C_EURUSD", "C_GBPUSD", "C_USDJPY", "C_USDCHF"]

    all_results = {}

    for symbol in symbols:
        print(f"\n\nChecking {symbol}...")
        print("-" * 60)

        results = sample_symbol_data(symbol, num_samples=10)
        all_results[symbol] = results

        if not results:
            print(f"No data found for {symbol}")
            continue

        # Analyze results
        flat_count = sum(1 for r in results if r.get("is_flat", False))
        error_count = sum(1 for r in results if "error" in r)

        print(f"Files sampled: {len(results)}")
        print(f"Flat data files: {flat_count} ({flat_count/len(results)*100:.1f}%)")
        print(f"Error files: {error_count}")

        # Show sample details
        print("\nSample file details:")
        for i, result in enumerate(results[:5]):  # Show first 5
            if "error" in result:
                print(f"  {i+1}. {result['file']}: ERROR - {result['error']}")
            else:
                print(f"  {i+1}. {result['file']}:")
                print(
                    f"     Unique values: open={result['unique_open']}, high={result['unique_high']}, "
                    f"low={result['unique_low']}, close={result['unique_close']}"
                )
                print(
                    f"     Std devs: open={result['open_std']:.6f}, high={result['high_std']:.6f}"
                )
                print(f"     Price range: {result['price_range']:.5f}")
                print(f"     Is flat: {result['is_flat']}")

    # Summary statistics
    print("\n\n" + "=" * 80)
    print("SUMMARY ACROSS ALL SYMBOLS")
    print("=" * 80)

    total_files = 0
    total_flat = 0

    for symbol, results in all_results.items():
        valid_results = [r for r in results if "error" not in r]
        flat_files = sum(1 for r in valid_results if r["is_flat"])

        total_files += len(valid_results)
        total_flat += flat_files

        if valid_results:
            avg_unique_high = np.mean([r["unique_high"] for r in valid_results])
            avg_price_range = np.mean([r["price_range"] for r in valid_results])

            print(f"\n{symbol}:")
            print(f"  Total files checked: {len(valid_results)}")
            print(
                f"  Flat data files: {flat_files} ({flat_files/len(valid_results)*100:.1f}%)"
            )
            print(f"  Average unique high values: {avg_unique_high:.1f}")
            print(f"  Average price range: {avg_price_range:.5f}")

    if total_files > 0:
        print(f"\n\nOVERALL:")
        print(f"  Total files analyzed: {total_files}")
        print(
            f"  Total flat data files: {total_flat} ({total_flat/total_files*100:.1f}%)"
        )

        if total_flat == total_files:
            print("\n⚠️ WARNING: ALL sampled data appears to be synthetic/flat!")
            print("This data is not suitable for backtesting or Elliott Wave analysis.")
        elif total_flat > total_files * 0.8:
            print("\n⚠️ WARNING: Most data appears to be synthetic/flat!")
            print("This data quality issue will severely impact backtesting results.")

    # Check specific date ranges
    print("\n\n" + "=" * 80)
    print("DATE RANGE ANALYSIS")
    print("=" * 80)

    for symbol in ["C_EURUSD", "C_GBPUSD"]:
        print(f"\n{symbol} date ranges:")
        symbol_path = Path(f"input/{symbol}")

        years = sorted(
            [
                d
                for d in symbol_path.iterdir()
                if d.is_dir() and d.name.startswith("year=")
            ]
        )

        for year_dir in years[:3]:  # Check first 3 years
            year = year_dir.name.split("=")[1]
            months = sorted(
                [
                    d
                    for d in year_dir.iterdir()
                    if d.is_dir() and d.name.startswith("month=")
                ]
            )

            if months:
                first_month = months[0].name.split("=")[1]
                last_month = months[-1].name.split("=")[1]
                print(
                    f"  {year}: months {first_month}-{last_month} ({len(months)} months)"
                )

                # Sample one file from this year
                sample_month = months[0]
                days = list(sample_month.iterdir())
                if days:
                    sample_file = days[0] / "data.parquet.gz"
                    if sample_file.exists():
                        stats = check_data_quality_for_file(sample_file)
                        if "is_flat" in stats:
                            print(
                                f"    Sample from {year}-{first_month}: {'FLAT' if stats['is_flat'] else 'DYNAMIC'}"
                            )


if __name__ == "__main__":
    # Set random seed for reproducibility
    random.seed(42)
    main()
