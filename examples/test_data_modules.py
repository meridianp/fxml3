#!/usr/bin/env python3
"""Example usage of the new data modules."""

import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fxml4.data.data_loader import DataLoader, DataLoaderManager
from fxml4.data.market_data import (
    Bar,
    MarketDataFrame,
    MarketDataValidator,
    Quote,
    Tick,
    TimeFrame,
)


async def main():
    """Demonstrate data module functionality."""

    print("=== FXML4 Data Modules Demo ===\n")

    # 1. Working with market data structures
    print("1. Market Data Structures:")

    # Create a Bar
    bar = Bar(
        timestamp=datetime.now(),
        open=1.2500,
        high=1.2550,
        low=1.2480,
        close=1.2520,
        volume=10000,
        timeframe=TimeFrame.M15,
        symbol="GBPUSD",
        tick_count=150,
    )
    print(f"   Bar: {bar.symbol} {bar.timeframe.value}")
    print(f"   - Range: {bar.range:.4f}")
    print(f"   - Body: {bar.body:.4f}")
    print(f"   - Bullish: {bar.is_bullish}")

    # Create a Quote
    quote = Quote(
        timestamp=datetime.now(),
        bid=1.2519,
        ask=1.2521,
        bid_size=1000000,
        ask_size=1500000,
        symbol="GBPUSD",
    )
    print(f"\n   Quote: {quote.symbol}")
    print(f"   - Spread: {quote.spread:.4f} ({quote.spread_bps:.1f} bps)")
    print(f"   - Mid: {quote.mid:.4f}")

    # 2. Data loading (if API key available)
    print("\n2. Data Loading:")

    config = {
        "polygon_api_key": os.getenv("POLYGON_API_KEY"),
        "cache_dir": "data/demo_cache",
    }

    if config["polygon_api_key"]:
        async with DataLoaderManager(config) as loader:
            # Load recent data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)

            print(
                f"   Loading GBPUSD data from {start_date.date()} to {end_date.date()}"
            )

            data = await loader.load_data(
                symbol="GBPUSD",
                timeframes=["15m", "1h", "4h"],
                start_date=start_date,
                end_date=end_date,
                source="polygon",
            )

            for tf, df in data.items():
                print(f"   - {tf}: {len(df)} bars")

            # Create MarketDataFrame
            if "1h" in data:
                mdf = MarketDataFrame(data["1h"], "GBPUSD", TimeFrame.H1)
                print(f"\n   MarketDataFrame created: {mdf}")

                # Add indicators
                mdf.add_technical_indicators(["sma_20", "rsi", "atr"])
                print("   - Added technical indicators")

                # Add market features
                mdf.add_market_features()
                print("   - Added market microstructure features")

                # Validate data
                issues = MarketDataValidator.validate_ohlcv(mdf.data)
                if issues:
                    print(f"   - Validation issues: {issues}")
                else:
                    print("   - Data validation passed!")

                # Get quality metrics
                quality = MarketDataValidator.check_data_quality(mdf.data)
                print(
                    f"   - Data quality: {quality['total_rows']} rows, "
                    f"missing values: {len(quality['missing_values'])}"
                )
    else:
        print("   No POLYGON_API_KEY found - skipping live data demo")
        print("   Set POLYGON_API_KEY environment variable to test data loading")

        # Create demo data
        import numpy as np
        import pandas as pd

        # Generate sample data
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
        prices = 1.2500 + np.cumsum(np.random.randn(100) * 0.0005)

        df = pd.DataFrame(
            {
                "open": prices + np.random.randn(100) * 0.0002,
                "high": prices + np.abs(np.random.randn(100) * 0.0003),
                "low": prices - np.abs(np.random.randn(100) * 0.0003),
                "close": prices,
                "volume": np.random.randint(1000, 10000, 100),
            },
            index=dates,
        )

        # Ensure OHLC consistency
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

        mdf = MarketDataFrame(df, "GBPUSD", TimeFrame.H1)
        print(f"\n   Created demo MarketDataFrame: {mdf}")

        # Add features
        mdf.add_technical_indicators().add_market_features()
        print("   - Added indicators and features")

        # Show some statistics
        print(f"   - Latest close: {mdf.data['close'].iloc[-1]:.4f}")
        print(f"   - RSI: {mdf.data['rsi'].iloc[-1]:.1f}")
        print(f"   - ATR: {mdf.data['atr'].iloc[-1]:.4f}")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
