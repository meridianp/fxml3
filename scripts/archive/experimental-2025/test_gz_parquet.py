#!/usr/bin/env python
"""Test reading gzipped parquet files."""

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

# Test file
test_file = Path(
    "/home/cnross/code/fxml4/input/C_EURUSD/year=2016/month=7/day=13/data.parquet.gz"
)

print(f"Testing file: {test_file}")
print(f"File exists: {test_file.exists()}")
print(f"File size: {test_file.stat().st_size} bytes")

# Try different methods
print("\n1. Testing pd.read_parquet with pyarrow engine:")
try:
    df = pd.read_parquet(test_file, engine="pyarrow")
    print(f"Success! Shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    print(f"First few rows:\n{df.head()}")
except Exception as e:
    print(f"Failed: {e}")

print("\n2. Testing pd.read_parquet with fastparquet engine:")
try:
    df = pd.read_parquet(test_file, engine="fastparquet")
    print(f"Success! Shape: {df.shape}")
except Exception as e:
    print(f"Failed: {e}")

print("\n3. Testing pyarrow.parquet.read_table:")
try:
    table = pq.read_table(test_file)
    df = table.to_pandas()
    print(f"Success! Shape: {df.shape}")
except Exception as e:
    print(f"Failed: {e}")

print("\n4. Testing with compression='gzip':")
try:
    df = pd.read_parquet(test_file, engine="pyarrow", compression="gzip")
    print(f"Success! Shape: {df.shape}")
except Exception as e:
    print(f"Failed: {e}")
