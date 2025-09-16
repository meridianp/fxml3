#!/usr/bin/env python
"""Debug GBPUSD data to understand why old data is not being included."""

import gzip
import io
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

# Check files from different years
years_to_check = [2014, 2020, 2024]

for year in years_to_check:
    print(f"\n=== Year {year} ===")

    # Find first file from that year
    year_dir = Path(f"/home/cnross/code/fxml4/input/C_GBPUSD/year={year}")
    if not year_dir.exists():
        print(f"No data for year {year}")
        continue

    # Get first file
    sample_file = next(year_dir.glob("**/data.parquet.gz"), None)

    if sample_file:
        print(f"Sample file: {sample_file}")

        try:
            # Read the file
            with gzip.open(sample_file, "rb") as f:
                parquet_data = f.read()
                buffer = io.BytesIO(parquet_data)
                table = pq.read_table(buffer)
                df = table.to_pandas()

            print(f"Shape: {df.shape}")
            print(f"Index type: {type(df.index)}")
            print(f"Index name: {df.index.name}")

            if len(df) > 0:
                print(f"First timestamp: {df.index[0]}")
                print(f"Last timestamp: {df.index[-1]}")
                print(f"Columns: {df.columns.tolist()}")
        except Exception as e:
            print(f"Error reading file: {e}")

# Check total file count by year
print("\n=== File count by year ===")
import subprocess

result = subprocess.run(
    "find /home/cnross/code/fxml4/input/C_GBPUSD -name '*.parquet.gz' | grep -o 'year=[0-9]*' | sort | uniq -c",
    shell=True,
    capture_output=True,
    text=True,
)
print(result.stdout)
