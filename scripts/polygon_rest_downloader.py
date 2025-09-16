#!/usr/bin/env python
"""Download forex data using Polygon.io REST API."""

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import click
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PolygonRESTDownloader:
    """Download forex data using Polygon REST API."""

    BASE_URL = "https://api.polygon.io"

    # Major forex pairs
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

    def __init__(self, api_key: Optional[str] = None, output_dir: str = "input"):
        """Initialize the downloader.

        Args:
            api_key: Polygon API key (or from env)
            output_dir: Output directory for data
        """
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        if not self.api_key:
            raise ValueError("POLYGON_API_KEY not found in environment")

        self.output_dir = Path(output_dir)
        logger.info(f"Using API key: {self.api_key[:10]}...")

    def get_forex_aggregates(
        self, ticker: str, date: datetime, timespan: str = "minute"
    ) -> Optional[pd.DataFrame]:
        """Get forex aggregates for a specific date.

        Args:
            ticker: Forex ticker (e.g., 'EURUSD')
            date: Date to fetch
            timespan: Timespan (minute, hour, day)

        Returns:
            DataFrame with OHLCV data or None
        """
        # Format ticker for Polygon (C:EURUSD)
        polygon_ticker = f"C:{ticker}"

        # Format date strings
        from_date = date.strftime("%Y-%m-%d")
        to_date = date.strftime("%Y-%m-%d")

        # API endpoint
        url = f"{self.BASE_URL}/v2/aggs/ticker/{polygon_ticker}/range/1/{timespan}/{from_date}/{to_date}"

        params = {
            "apiKey": self.api_key,
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,  # Max limit
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data["status"] != "OK" or "results" not in data:
                logger.warning(f"No data for {ticker} on {date}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(data["results"])

            # Convert timestamp to datetime
            df["timestamp"] = pd.to_datetime(df["t"], unit="ms", utc=True)

            # Rename columns
            df = df.rename(
                columns={
                    "o": "open",
                    "h": "high",
                    "l": "low",
                    "c": "close",
                    "v": "volume",
                    "n": "transactions",
                }
            )

            # Select columns
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]

            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {ticker} on {date}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing data for {ticker} on {date}: {e}")
            return None

    def save_daily_data(self, df: pd.DataFrame, symbol: str, date: datetime) -> Path:
        """Save daily data in standard format.

        Args:
            df: DataFrame with OHLCV data
            symbol: Symbol name (e.g., 'EURUSD')
            date: Date of the data

        Returns:
            Path to saved file
        """
        # Create directory structure
        symbol_dir = f"C_{symbol}"
        output_path = (
            self.output_dir
            / symbol_dir
            / f"year={date.year}"
            / f"month={date.month}"
            / f"day={date.day}"
        )
        output_path.mkdir(parents=True, exist_ok=True)

        # Save as parquet
        output_file = output_path / "data.parquet.gz"
        df.to_parquet(output_file, compression="gzip", index=False)

        return output_file

    def download_date_range(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        skip_weekends: bool = True,
    ) -> List[Path]:
        """Download data for a date range.

        Args:
            symbol: Forex symbol
            start_date: Start date
            end_date: End date
            skip_weekends: Skip Saturday and Sunday

        Returns:
            List of saved file paths
        """
        saved_files = []
        current_date = start_date

        logger.info(
            f"Downloading {symbol} from {start_date.date()} to {end_date.date()}"
        )

        while current_date <= end_date:
            # Skip weekends if requested
            if skip_weekends and current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            # Check if file already exists
            symbol_dir = f"C_{symbol}"
            output_file = (
                self.output_dir
                / symbol_dir
                / f"year={current_date.year}"
                / f"month={current_date.month}"
                / f"day={current_date.day}"
                / "data.parquet.gz"
            )

            if output_file.exists():
                logger.info(f"  {current_date.date()}: Already exists")
                saved_files.append(output_file)
                current_date += timedelta(days=1)
                continue

            # Download data
            df = self.get_forex_aggregates(symbol, current_date)

            if df is not None and len(df) > 0:
                output_file = self.save_daily_data(df, symbol, current_date)
                saved_files.append(output_file)
                logger.info(f"  {current_date.date()}: Saved {len(df)} bars")
            else:
                logger.warning(f"  {current_date.date()}: No data")

            # Rate limiting (5 requests per minute for free tier)
            time.sleep(12)  # 5 requests per minute = 12 seconds between requests

            current_date += timedelta(days=1)

        return saved_files

    def validate_downloaded_data(
        self, symbol: str, start_date: datetime, end_date: datetime
    ) -> Dict:
        """Validate downloaded data quality.

        Args:
            symbol: Forex symbol
            start_date: Start date
            end_date: End date

        Returns:
            Validation statistics
        """
        symbol_dir = f"C_{symbol}"
        symbol_path = self.output_dir / symbol_dir

        stats = {
            "symbol": symbol,
            "date_range": f"{start_date.date()} to {end_date.date()}",
            "files_found": 0,
            "total_bars": 0,
            "avg_daily_bars": 0,
            "price_range": None,
            "is_real_data": False,
        }

        all_data = []
        current_date = start_date

        while current_date <= end_date:
            if current_date.weekday() < 5:  # Weekday
                file_path = (
                    symbol_path
                    / f"year={current_date.year}"
                    / f"month={current_date.month}"
                    / f"day={current_date.day}"
                    / "data.parquet.gz"
                )

                if file_path.exists():
                    try:
                        df = pd.read_parquet(file_path)
                        all_data.append(df)
                        stats["files_found"] += 1
                    except:
                        pass

            current_date += timedelta(days=1)

        if all_data:
            combined = pd.concat(all_data)
            stats["total_bars"] = len(combined)
            stats["avg_daily_bars"] = (
                stats["total_bars"] / stats["files_found"]
                if stats["files_found"] > 0
                else 0
            )
            stats["price_range"] = (
                f"{combined['low'].min():.5f} to {combined['high'].max():.5f}"
            )

            # Check if real data (multiple unique values)
            unique_highs = combined["high"].nunique()
            stats["is_real_data"] = unique_highs > 100
            stats["unique_prices"] = unique_highs

        return stats


@click.group()
def cli():
    """Polygon.io REST API Downloader for FXML4."""
    pass


@cli.command()
@click.option("--symbol", default="EURUSD", help="Forex symbol to download")
@click.option("--days", default=30, help="Number of days to download")
@click.option("--end-date", help="End date (YYYY-MM-DD), default: yesterday")
def download(symbol: str, days: int, end_date: Optional[str]):
    """Download forex data for a symbol."""
    downloader = PolygonRESTDownloader()

    # Determine date range
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end = datetime.now() - timedelta(days=1)  # Yesterday

    start = end - timedelta(days=days - 1)

    # Download data
    saved_files = downloader.download_date_range(symbol, start, end)

    click.echo(f"\n✅ Downloaded {len(saved_files)} files for {symbol}")

    # Validate
    stats = downloader.validate_downloaded_data(symbol, start, end)

    click.echo(f"\n📊 Validation Results:")
    click.echo(f"  Files found: {stats['files_found']}")
    click.echo(f"  Total bars: {stats['total_bars']}")
    click.echo(f"  Avg bars/day: {stats['avg_daily_bars']:.0f}")
    if stats["price_range"]:
        click.echo(f"  Price range: {stats['price_range']}")
        click.echo(f"  Unique prices: {stats['unique_prices']}")
        click.echo(f"  Real data: {'✅ Yes' if stats['is_real_data'] else '❌ No'}")


@cli.command()
@click.option(
    "--symbols", default="EURUSD,GBPUSD,USDJPY", help="Comma-separated symbols"
)
@click.option("--days", default=7, help="Number of days per symbol")
def quickstart(symbols: str, days: int):
    """Quick download of recent data for multiple symbols."""
    downloader = PolygonRESTDownloader()

    symbol_list = [s.strip() for s in symbols.split(",")]
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)

    click.echo(f"🚀 Quick start downloading {days} days for: {', '.join(symbol_list)}")

    all_stats = []

    for symbol in symbol_list:
        click.echo(f"\n📥 Downloading {symbol}...")
        saved_files = downloader.download_date_range(symbol, start_date, end_date)

        # Validate
        stats = downloader.validate_downloaded_data(symbol, start_date, end_date)
        all_stats.append(stats)

        click.echo(f"  Downloaded: {len(saved_files)} files")
        click.echo(f"  Total bars: {stats['total_bars']}")
        if stats["is_real_data"]:
            click.echo(f"  ✅ Real market data confirmed")
        else:
            click.echo(f"  ⚠️ Data quality issue detected")

    # Summary
    click.echo("\n" + "=" * 60)
    click.echo("📈 SUMMARY")
    click.echo("=" * 60)

    for stats in all_stats:
        real_status = "✅" if stats["is_real_data"] else "❌"
        click.echo(
            f"{stats['symbol']}: {stats['files_found']} files, "
            f"{stats['total_bars']} bars, {real_status} real data"
        )


@cli.command()
@click.option("--symbol", default="EURUSD", help="Symbol to test")
def test(symbol: str):
    """Test API connection with a single day download."""
    downloader = PolygonRESTDownloader()

    test_date = datetime.now() - timedelta(days=5)  # 5 days ago

    click.echo(f"🧪 Testing API with {symbol} for {test_date.date()}")

    df = downloader.get_forex_aggregates(symbol, test_date)

    if df is not None:
        click.echo(f"\n✅ API connection successful!")
        click.echo(f"  Received {len(df)} bars")
        click.echo(f"  Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        click.echo(f"  Price range: {df['low'].min():.5f} to {df['high'].max():.5f}")

        # Show sample data
        click.echo(f"\n  Sample data (first 5 rows):")
        click.echo(df.head().to_string(index=False))
    else:
        click.echo(f"\n❌ API test failed. Check your API key and internet connection.")


if __name__ == "__main__":
    cli()
