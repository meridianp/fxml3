#!/usr/bin/env python
"""Debug GBPUSD aggregation to understand missing historical data."""

import gzip
import io
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

# Find all GBPUSD files
gbpusd_dir = Path("/home/cnross/code/fxml4/input/C_GBPUSD")
all_files = list(gbpusd_dir.glob("**/*.parquet.gz"))

print(f"Total files: {len(all_files)}")

# Group by year and check first/last dates
year_data = {}

for file in all_files:
    # Extract year from path
    year_match = str(file).split("/year=")[1].split("/")[0]
    year = int(year_match)

    if year not in year_data:
        year_data[year] = {
            "files": 0,
            "min_date": None,
            "max_date": None,
            "total_rows": 0,
        }

    year_data[year]["files"] += 1

# Sample a few files from each year to get date ranges
for year in sorted(year_data.keys()):
    print(f"\nChecking year {year}...")
    year_files = [f for f in all_files if f"/year={year}/" in str(f)]

    # Sample first and last files
    sample_files = (
        year_files[:2] + year_files[-2:] if len(year_files) > 4 else year_files
    )

    min_date = None
    max_date = None
    total_rows = 0

    for file in sample_files:
        try:
            with gzip.open(file, "rb") as f:
                parquet_data = f.read()
                buffer = io.BytesIO(parquet_data)
                table = pq.read_table(buffer)
                df = table.to_pandas()

            if len(df) > 0:
                if min_date is None or df.index.min() < min_date:
                    min_date = df.index.min()
                if max_date is None or df.index.max() > max_date:
                    max_date = df.index.max()
                total_rows += len(df)
        except Exception as e:
            continue

    year_data[year]["min_date"] = min_date
    year_data[year]["max_date"] = max_date
    year_data[year]["sample_rows"] = total_rows

# Print summary
print("\n=== GBPUSD Data Summary by Year ===")
print(f"{'Year':<6} {'Files':<8} {'Min Date':<25} {'Max Date':<25} {'Sample Rows':<12}")
print("-" * 80)

for year in sorted(year_data.keys()):
    data = year_data[year]
    print(
        f"{year:<6} {data['files']:<8} {str(data['min_date']):<25} {str(data['max_date']):<25} {data['sample_rows']:<12}"
    )

# Check if reading all files at once causes issues
print("\n=== Testing batch reading ===")
test_files = [f for f in all_files if "/year=2014/" in str(f)][:10]
print(f"Reading {len(test_files)} files from 2014...")

dfs = []
for file in test_files:
    try:
        with gzip.open(file, "rb") as f:
            parquet_data = f.read()
            buffer = io.BytesIO(parquet_data)
            table = pq.read_table(buffer)
            df = table.to_pandas()
            dfs.append(df)
    except Exception as e:
        print(f"Error reading {file}: {e}")

if dfs:
    combined = pd.concat(dfs, ignore_index=False)
    print(f"Combined shape: {combined.shape}")
    print(f"Combined date range: {combined.index.min()} to {combined.index.max()}")
    print(f"Index is datetime: {isinstance(combined.index, pd.DatetimeIndex)}")
