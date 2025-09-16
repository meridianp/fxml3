# Polygon.io Data Storage Plan

## Available Storage
- **Device**: /dev/vdb
- **Size**: 40GB
- **Status**: Unformatted/unmounted

## Storage Requirements Analysis

### Polygon.io Forex Data Sizes (from documentation)
- 2024: 4.13 GB (partial year)
- 2023: ~4-5 GB (estimated)
- 2022: ~4-5 GB (estimated)
- Total for 3 years: ~15 GB

### Our Storage Plan
With 40GB available, we can store:
- 8-10 years of forex minute data
- Multiple currency pairs
- Room for processed/resampled data

## Disk Setup Steps

### 1. Partition and Format (requires sudo)
```bash
# Create partition
sudo fdisk /dev/vdb
# Type: n (new partition)
# Type: p (primary)
# Partition number: 1
# First sector: (default)
# Last sector: (default)
# Type: w (write)

# Format as ext4
sudo mkfs.ext4 /dev/vdb1

# Create mount point
sudo mkdir -p /mnt/polygon-data
```

### 2. Mount the Volume
```bash
# Mount temporarily
sudo mount /dev/vdb1 /mnt/polygon-data

# Add to fstab for permanent mounting
echo "/dev/vdb1 /mnt/polygon-data ext4 defaults 0 0" | sudo tee -a /etc/fstab

# Set permissions
sudo chown -R $USER:$USER /mnt/polygon-data
```

### 3. Create Directory Structure
```bash
/mnt/polygon-data/
├── raw/                    # Original Polygon CSV files
│   ├── forex/
│   │   ├── 2024/
│   │   ├── 2023/
│   │   └── 2022/
│   └── download_logs/
├── processed/              # Converted parquet files
│   ├── C_EURUSD/
│   ├── C_GBPUSD/
│   ├── C_USDJPY/
│   └── C_AUDUSD/
└── cache/                  # Temporary processing files
```

## Data Management Script

```python
#!/usr/bin/env python
"""Polygon.io data manager for FXML4."""

import os
import boto3
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

class PolygonDataManager:
    def __init__(self, base_path="/mnt/polygon-data"):
        self.base_path = Path(base_path)
        self.raw_path = self.base_path / "raw" / "forex"
        self.processed_path = self.base_path / "processed"
        
        # Create directories
        self.raw_path.mkdir(parents=True, exist_ok=True)
        self.processed_path.mkdir(parents=True, exist_ok=True)
        
        # S3 client setup
        self.s3 = boto3.client(
            's3',
            endpoint_url='https://files.polygon.io',
            aws_access_key_id=os.getenv('POLYGON_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('POLYGON_SECRET_KEY')
        )
    
    def download_year(self, year: int):
        """Download forex data for a specific year."""
        key = f'global_forex/minute_aggs_v1/{year}/data.csv'
        local_file = self.raw_path / f"{year}" / "forex_minutes.csv"
        local_file.parent.mkdir(exist_ok=True)
        
        print(f"Downloading {year} data to {local_file}...")
        self.s3.download_file('flatfiles', key, str(local_file))
        
        # Log download
        log_file = self.base_path / "download_logs" / f"{year}_download.log"
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, 'w') as f:
            f.write(f"Downloaded: {datetime.now()}\n")
            f.write(f"File: {local_file}\n")
            f.write(f"Size: {local_file.stat().st_size / 1e9:.2f} GB\n")
        
        return local_file
    
    def process_to_parquet(self, csv_file: Path, symbols: list):
        """Convert Polygon CSV to our parquet format."""
        print(f"Processing {csv_file}...")
        
        # Read in chunks for memory efficiency
        chunk_size = 1_000_000
        
        for chunk in pd.read_csv(csv_file, chunksize=chunk_size):
            # Convert timestamp
            chunk['timestamp'] = pd.to_datetime(chunk['window_start'], unit='ns')
            
            # Process each symbol
            for symbol in symbols:
                ticker = f"C:{symbol.replace('_', '')}"
                symbol_data = chunk[chunk['ticker'] == ticker]
                
                if symbol_data.empty:
                    continue
                
                # Group by date
                for date, day_data in symbol_data.groupby(symbol_data['timestamp'].dt.date):
                    self._save_daily_parquet(day_data, symbol, date)
    
    def _save_daily_parquet(self, day_data: pd.DataFrame, symbol: str, date):
        """Save daily data in our format."""
        # Prepare dataframe
        output_df = pd.DataFrame({
            'timestamp': day_data['timestamp'],
            'open': day_data['open'],
            'high': day_data['high'],
            'low': day_data['low'],
            'close': day_data['close'],
            'volume': day_data['volume']
        })
        
        # Create path
        year = date.year
        month = date.month
        day = date.day
        
        output_path = (self.processed_path / symbol / 
                      f"year={year}" / f"month={month}" / f"day={day}")
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save as parquet
        output_file = output_path / "data.parquet.gz"
        output_df.to_parquet(output_file, compression='gzip', index=False)
    
    def get_storage_stats(self):
        """Get storage usage statistics."""
        total_size = sum(f.stat().st_size for f in self.base_path.rglob('*') if f.is_file())
        
        stats = {
            'total_used_gb': total_size / 1e9,
            'available_gb': 40 - (total_size / 1e9),
            'raw_files': len(list(self.raw_path.rglob('*.csv'))),
            'processed_symbols': len(list(self.processed_path.iterdir()))
        }
        
        return stats
```

## Migration Plan

### Phase 1: Setup (Day 1)
1. Format and mount /dev/vdb
2. Create directory structure
3. Set up Polygon.io credentials

### Phase 2: Download (Day 2-3)
1. Download 2024 data (current year)
2. Download 2023 data
3. Download 2022 data
4. Verify data integrity

### Phase 3: Process (Day 4-5)
1. Convert major pairs: EURUSD, GBPUSD, USDJPY, AUDUSD
2. Create symlinks from current input directory
3. Test with backtesting system

### Phase 4: Validation (Day 6)
1. Run Elliott Wave detection on real data
2. Compare backtest results
3. Document improvements

## Benefits

1. **40GB dedicated storage** - Won't impact main filesystem
2. **Organized structure** - Separate raw and processed data
3. **Scalable** - Room for 8-10 years of data
4. **Performance** - Dedicated disk for I/O operations
5. **Backup-friendly** - Easy to backup/snapshot entire volume

## Next Steps

1. Get sudo access to format and mount the disk
2. Obtain Polygon.io API credentials
3. Implement the data manager script
4. Start downloading recent forex data
5. Replace synthetic data with real market data