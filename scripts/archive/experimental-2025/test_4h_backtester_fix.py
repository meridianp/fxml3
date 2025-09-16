#!/usr/bin/env python
"""Test the fixed 4-hour backtester."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import os

from scripts.create_optimized_4h_backtester import Optimized4HBacktester


def main():
    """Test the fixed backtester with a short period."""

    # Set environment variables
    os.environ["FOREX_MIN_POSITION_SIZE_4H"] = "10000"
    os.environ["FOREX_MAX_POSITIONS_4H"] = "10"

    # Test with one symbol and a short period
    symbols = ["EURUSD"]

    # Test period - just one month
    start_date = "2024-01-01"
    end_date = "2024-01-31"

    print("Testing fixed 4H backtester...")
    print(f"Symbol: {symbols}")
    print(f"Period: {start_date} to {end_date}")

    try:
        # Run backtest
        backtester = Optimized4HBacktester(symbols, initial_capital=100000)
        backtester.run_backtest(start_date, end_date)
        print("\n✅ Backtester executed successfully!")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
