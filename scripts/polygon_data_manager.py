#!/usr/bin/env python
"""Polygon.io data manager for FXML4."""

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import gzip
import logging
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import boto3
import click
import numpy as np
import pandas as pd

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PolygonDataManager:
    """Manages Polygon.io forex data download and processing."""

    # Major forex pairs to process
    MAJOR_PAIRS = [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "AUDUSD",
        "USDCAD",
        "USDCHF",
        "NZDUSD",
        "EURGBP",
    ]

    def __init__(
        self,
        base_path: str = "/mnt/polygon-data",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """Initialize the data manager.

        Args:
            base_path: Base directory for data storage
            access_key: Polygon S3 access key (or from env)
            secret_key: Polygon S3 secret key (or from env)
        """
        self.base_path = Path(base_path)
        self.raw_path = self.base_path / "raw" / "forex"
        self.processed_path = self.base_path / "processed"
        self.cache_path = self.base_path / "cache"
        self.log_path = self.base_path / "download_logs"

        # Create directories
        for path in [
            self.raw_path,
            self.processed_path,
            self.cache_path,
            self.log_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)

        # S3 client setup
        self.access_key = access_key or os.getenv("POLYGON_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("POLYGON_SECRET_KEY")

        # Also check for regular API key
        self.api_key = os.getenv("POLYGON_API_KEY")

        if self.access_key and self.secret_key:
            self.s3 = boto3.client(
                "s3",
                endpoint_url="https://files.polygon.io",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )
            logger.info("S3 client initialized with access/secret keys")
        else:
            self.s3 = None
            if self.api_key:
                logger.info(f"Found POLYGON_API_KEY: {self.api_key[:10]}...")
                logger.warning(
                    "Note: Flat Files access requires S3 credentials (access key & secret key) from Polygon dashboard"
                )
                logger.warning("The API key is for REST API access, not S3 flat files")
            else:
                logger.warning(
                    "No Polygon credentials found. Set POLYGON_ACCESS_KEY and POLYGON_SECRET_KEY for S3 access"
                )

    def download_year(self, year: int, force: bool = False) -> Optional[Path]:
        """Download forex data for a specific year.

        Args:
            year: Year to download (2009-2024)
            force: Force re-download even if file exists

        Returns:
            Path to downloaded file or None if failed
        """
        if not self.s3:
            logger.error("S3 client not initialized. Check credentials.")
            return None

        # Check if already downloaded
        year_dir = self.raw_path / str(year)
        year_dir.mkdir(exist_ok=True)
        local_file = year_dir / "forex_minutes.csv"

        if local_file.exists() and not force:
            logger.info(f"File already exists: {local_file}")
            return local_file

        # S3 key
        key = f"global_forex/minute_aggs_v1/{year}/data.csv"

        try:
            logger.info(f"Downloading {year} forex data...")
            logger.info(f"S3 Key: {key}")
            logger.info(f"Local path: {local_file}")

            # Download with progress callback
            def download_callback(bytes_transferred):
                mb_transferred = bytes_transferred / 1024 / 1024
                print(f"\rDownloaded: {mb_transferred:.1f} MB", end="", flush=True)

            self.s3.download_file(
                "flatfiles", key, str(local_file), Callback=download_callback
            )
            print()  # New line after progress

            # Log download
            self._log_download(year, local_file)

            logger.info(f"Successfully downloaded {year} data")
            return local_file

        except Exception as e:
            logger.error(f"Failed to download {year} data: {e}")
            if local_file.exists():
                local_file.unlink()  # Remove partial download
            return None

    def process_to_parquet(
        self,
        csv_file: Path,
        symbols: Optional[List[str]] = None,
        chunk_size: int = 1_000_000,
    ) -> Dict[str, int]:
        """Convert Polygon CSV to our parquet format.

        Args:
            csv_file: Path to CSV file
            symbols: List of symbols to process (default: MAJOR_PAIRS)
            chunk_size: Rows to process at once

        Returns:
            Dictionary of symbol: number of days processed
        """
        if symbols is None:
            symbols = self.MAJOR_PAIRS

        logger.info(f"Processing {csv_file.name} for symbols: {symbols}")

        processed_stats = {symbol: 0 for symbol in symbols}

        # Read in chunks for memory efficiency
        try:
            for chunk_num, chunk in enumerate(
                pd.read_csv(csv_file, chunksize=chunk_size)
            ):
                if chunk_num % 10 == 0:
                    logger.info(f"Processing chunk {chunk_num + 1}...")

                # Convert timestamp from nanoseconds to datetime
                chunk["timestamp"] = pd.to_datetime(
                    chunk["window_start"], unit="ns", utc=True
                )

                # Process each symbol
                for symbol in symbols:
                    # Polygon uses C:EURUSD format
                    ticker = f"C:{symbol}"
                    symbol_data = chunk[chunk["ticker"] == ticker]

                    if symbol_data.empty:
                        continue

                    # Group by date and save
                    for date, day_data in symbol_data.groupby(
                        symbol_data["timestamp"].dt.date
                    ):
                        self._save_daily_parquet(day_data, f"C_{symbol}", date)
                        processed_stats[symbol] += 1

        except Exception as e:
            logger.error(f"Error processing CSV: {e}")
            raise

        # Log processing stats
        for symbol, days in processed_stats.items():
            if days > 0:
                logger.info(f"  {symbol}: {days} days processed")

        return processed_stats

    def _save_daily_parquet(self, day_data: pd.DataFrame, symbol: str, date) -> None:
        """Save daily data in our standard format.

        Args:
            day_data: DataFrame with day's data
            symbol: Symbol name (e.g., C_EURUSD)
            date: Date object
        """
        # Prepare dataframe in our format
        output_df = pd.DataFrame(
            {
                "timestamp": day_data["timestamp"],
                "open": day_data["open"].astype(float),
                "high": day_data["high"].astype(float),
                "low": day_data["low"].astype(float),
                "close": day_data["close"].astype(float),
                "volume": day_data["volume"].astype(float),
            }
        )

        # Sort by timestamp
        output_df = output_df.sort_values("timestamp")

        # Create path structure
        output_path = (
            self.processed_path
            / symbol
            / f"year={date.year}"
            / f"month={date.month}"
            / f"day={date.day}"
        )
        output_path.mkdir(parents=True, exist_ok=True)

        # Save as gzipped parquet
        output_file = output_path / "data.parquet.gz"
        output_df.to_parquet(output_file, compression="gzip", index=False)

    def _log_download(self, year: int, file_path: Path) -> None:
        """Log download information."""
        log_file = self.log_path / f"download_{year}.log"

        with open(log_file, "a") as f:
            f.write(f"{'='*60}\n")
            f.write(f"Downloaded at: {datetime.now().isoformat()}\n")
            f.write(f"Year: {year}\n")
            f.write(f"File: {file_path}\n")
            f.write(f"Size: {file_path.stat().st_size / 1e9:.2f} GB\n")
            f.write(f"{'='*60}\n\n")

    def get_storage_stats(self) -> Dict[str, float]:
        """Get storage usage statistics.

        Returns:
            Dictionary with storage statistics
        """
        # Calculate sizes
        raw_size = sum(
            f.stat().st_size for f in self.raw_path.rglob("*") if f.is_file()
        )
        processed_size = sum(
            f.stat().st_size for f in self.processed_path.rglob("*") if f.is_file()
        )
        total_size = raw_size + processed_size

        # Count files
        raw_files = len(list(self.raw_path.rglob("*.csv")))
        processed_days = len(list(self.processed_path.rglob("*.parquet.gz")))
        symbols = set(d.name for d in self.processed_path.iterdir() if d.is_dir())

        stats = {
            "total_used_gb": total_size / 1e9,
            "raw_size_gb": raw_size / 1e9,
            "processed_size_gb": processed_size / 1e9,
            "available_gb": 40 - (total_size / 1e9),
            "raw_files": raw_files,
            "processed_days": processed_days,
            "symbols": len(symbols),
            "symbol_list": sorted(list(symbols)),
        }

        return stats

    def create_symlinks(self, target_dir: str = "input") -> None:
        """Create symbolic links from processed data to input directory.

        Args:
            target_dir: Target directory for symlinks
        """
        target_path = Path(target_dir)

        for symbol_dir in self.processed_path.iterdir():
            if symbol_dir.is_dir():
                link_path = target_path / symbol_dir.name

                # Remove existing link or directory
                if link_path.exists() or link_path.is_symlink():
                    logger.info(f"Removing existing: {link_path}")
                    if link_path.is_symlink():
                        link_path.unlink()
                    else:
                        shutil.rmtree(link_path)

                # Create symlink
                link_path.symlink_to(symbol_dir)
                logger.info(f"Created symlink: {link_path} -> {symbol_dir}")


@click.group()
def cli():
    """Polygon.io Data Manager for FXML4."""
    pass


@cli.command()
@click.option("--year", type=int, required=True, help="Year to download (2009-2024)")
@click.option("--force", is_flag=True, help="Force re-download")
def download(year: int, force: bool):
    """Download forex data for a specific year."""
    manager = PolygonDataManager()

    if year < 2009 or year > 2024:
        click.echo(f"Error: Year must be between 2009 and 2024")
        return

    result = manager.download_year(year, force)
    if result:
        click.echo(f"✅ Downloaded to: {result}")
    else:
        click.echo(f"❌ Download failed")


@cli.command()
@click.option("--year", type=int, required=True, help="Year to process")
@click.option(
    "--symbols", multiple=True, help="Symbols to process (default: major pairs)"
)
def process(year: int, symbols):
    """Process downloaded CSV to parquet format."""
    manager = PolygonDataManager()

    csv_file = manager.raw_path / str(year) / "forex_minutes.csv"
    if not csv_file.exists():
        click.echo(f"Error: CSV file not found: {csv_file}")
        click.echo(f"Run 'download --year {year}' first")
        return

    symbols_list = list(symbols) if symbols else None
    stats = manager.process_to_parquet(csv_file, symbols_list)

    click.echo("\n✅ Processing complete!")
    click.echo(f"Processed days per symbol:")
    for symbol, days in stats.items():
        if days > 0:
            click.echo(f"  {symbol}: {days} days")


@cli.command()
def stats():
    """Show storage statistics."""
    manager = PolygonDataManager()
    stats = manager.get_storage_stats()

    click.echo("\n📊 Storage Statistics")
    click.echo("=" * 40)
    click.echo(f"Total used: {stats['total_used_gb']:.2f} GB")
    click.echo(
        f"  Raw data: {stats['raw_size_gb']:.2f} GB ({stats['raw_files']} files)"
    )
    click.echo(
        f"  Processed: {stats['processed_size_gb']:.2f} GB ({stats['processed_days']} days)"
    )
    click.echo(f"Available: {stats['available_gb']:.2f} GB")
    click.echo(f"\nSymbols processed: {stats['symbols']}")
    if stats["symbol_list"]:
        click.echo(f"  {', '.join(stats['symbol_list'])}")


@cli.command()
@click.option("--target", default="input", help="Target directory for symlinks")
def symlinks(target: str):
    """Create symbolic links to processed data."""
    manager = PolygonDataManager()
    manager.create_symlinks(target)
    click.echo("✅ Symlinks created")


@cli.command()
@click.option("--years", default="2023,2024", help="Comma-separated years to download")
def quickstart(years: str):
    """Quick setup: download and process recent data."""
    manager = PolygonDataManager()

    year_list = [int(y.strip()) for y in years.split(",")]

    click.echo(f"🚀 Quick start for years: {year_list}")

    for year in year_list:
        click.echo(f"\n📥 Downloading {year}...")
        csv_file = manager.download_year(year)

        if csv_file:
            click.echo(f"\n⚙️  Processing {year}...")
            stats = manager.process_to_parquet(csv_file)

            total_days = sum(stats.values())
            click.echo(
                f"✅ Processed {total_days} total days across {len(stats)} symbols"
            )

    click.echo(f"\n🔗 Creating symlinks...")
    manager.create_symlinks()

    click.echo(f"\n✅ Quick start complete!")
    stats = manager.get_storage_stats()
    click.echo(f"Total data: {stats['total_used_gb']:.2f} GB")


if __name__ == "__main__":
    cli()
