#!/usr/bin/env python3
"""Test LLM-enhanced backtesting with Polygon.io historical data."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import our modules
from fxml4.backtesting.llm_enhanced_backtester import LLMEnhancedBacktester
from fxml4.strategy.ml_signal_generator import MLSignalGenerator


class SimpleMLSignalGenerator:
    """Simple ML signal generator for testing."""

    def __init__(self, symbol: str = "GBPUSD"):
        self.symbol = symbol
        self.signal_count = 0

    def generate_signal(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Generate a simple signal based on technical indicators."""
        if len(data) < 50:
            return None

        # Calculate simple indicators
        sma_20 = data["close"].rolling(20).mean()
        sma_50 = data["close"].rolling(50).mean()
        rsi = self._calculate_rsi(data["close"])

        current_price = data["close"].iloc[-1]
        prev_price = data["close"].iloc[-2]

        # Simple signal logic
        signal = None

        # Bullish signal
        if (
            sma_20.iloc[-1] > sma_50.iloc[-1]
            and sma_20.iloc[-2] <= sma_50.iloc[-2]
            and rsi.iloc[-1] < 70
        ):

            signal = {
                "direction": "BUY",
                "confidence": 0.65
                + (70 - rsi.iloc[-1]) / 100,  # Higher confidence if RSI lower
                "entry_price": current_price,
                "stop_loss": current_price - 0.0050,
                "take_profit": current_price + 0.0100,
                "timeframe": "4H",
                "reason": "Golden cross with RSI confirmation",
            }

        # Bearish signal
        elif (
            sma_20.iloc[-1] < sma_50.iloc[-1]
            and sma_20.iloc[-2] >= sma_50.iloc[-2]
            and rsi.iloc[-1] > 30
        ):

            signal = {
                "direction": "SELL",
                "confidence": 0.65
                + (rsi.iloc[-1] - 30) / 100,  # Higher confidence if RSI higher
                "entry_price": current_price,
                "stop_loss": current_price + 0.0050,
                "take_profit": current_price - 0.0100,
                "timeframe": "4H",
                "reason": "Death cross with RSI confirmation",
            }

        # Limit signal frequency
        if signal and self.signal_count < 20:  # Max 20 signals for demo
            self.signal_count += 1
            return signal

        return None

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))


async def run_llm_backtest():
    """Run a backtest with LLM validation."""
    logger.info("\n" + "=" * 60)
    logger.info("LLM-ENHANCED BACKTESTING DEMO")
    logger.info("=" * 60)

    # Check for Polygon API key
    polygon_api_key = os.getenv("POLYGON_API_KEY")
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY not found in environment")
        logger.info("Please set POLYGON_API_KEY in your .env file")
        logger.info("Get a free API key at: https://polygon.io/")
        return

    # Backtest parameters
    symbol = "GBPUSD"
    polygon_symbol = "C:GBPUSD"  # Forex format for Polygon
    start_date = datetime(2024, 10, 1)
    end_date = datetime(2024, 10, 31)

    logger.info(f"\nBacktest Configuration:")
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Period: {start_date.date()} to {end_date.date()}")
    logger.info(f"Timeframes: 15m, 1H, 4H, D")

    # Initialize backtester
    backtester = LLMEnhancedBacktester(
        initial_capital=100000,
        commission=0.0002,
        polygon_api_key=polygon_api_key,
        timeframes_to_validate=["15m", "1H", "4H", "D"],
        llm_validation_threshold=0.7,
    )

    # Load or fetch primary data
    primary_data_file = Path(f"data/polygon_cache/{symbol}_4H_primary.pkl")

    if primary_data_file.exists():
        logger.info("\nLoading cached primary data...")
        primary_data = pd.read_pickle(primary_data_file)
    else:
        logger.info("\nFetching primary 4H data from Polygon.io...")
        from fxml4.data.polygon_official_fetcher import PolygonOfficialDataFetcher

        fetcher = PolygonOfficialDataFetcher(polygon_api_key)
        data_dict = fetcher.fetch_multi_timeframe_data(
            polygon_symbol,
            ["4H"],
            start_date - timedelta(days=30),  # Extra for indicators
            end_date,
        )

        if "4H" not in data_dict or data_dict["4H"].empty:
            logger.error("Failed to fetch primary data")
            return

        primary_data = data_dict["4H"]
        primary_data_file.parent.mkdir(parents=True, exist_ok=True)
        primary_data.to_pickle(primary_data_file)

    logger.info(f"Primary data: {len(primary_data)} bars")

    # Initialize signal generator
    signal_generator = SimpleMLSignalGenerator(symbol)

    # Run backtest
    logger.info("\nRunning backtest with LLM validation...")
    logger.info("This will validate each signal with multi-timeframe charts...")

    try:
        results = await backtester.run_backtest_with_llm(
            symbol=symbol,
            primary_data=primary_data,
            signal_generator=signal_generator,
            start_date=start_date,
            end_date=end_date,
            polygon_symbol=polygon_symbol,
        )

        # Display results
        logger.info("\n" + "=" * 60)
        logger.info("BACKTEST RESULTS")
        logger.info("=" * 60)

        # Performance metrics
        logger.info("\nPerformance Metrics:")
        logger.info(f"Total Return: {results.get('total_return', 0):.2%}")
        logger.info(f"Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
        logger.info(f"Max Drawdown: {results.get('max_drawdown', 0):.2%}")
        logger.info(f"Win Rate: {results.get('win_rate', 0):.2%}")

        # LLM validation metrics
        llm_stats = results.get("llm_validation", {})
        logger.info("\nLLM Validation Statistics:")
        logger.info(f"Total Signals: {llm_stats.get('total_signals', 0)}")
        logger.info(
            f"Accepted: {llm_stats.get('accepted_signals', 0)} ({llm_stats.get('acceptance_rate', 0):.1%})"
        )
        logger.info(f"Rejected: {llm_stats.get('rejected_signals', 0)}")
        logger.info(f"Avg LLM Confidence: {llm_stats.get('avg_llm_confidence', 0):.1%}")
        logger.info(
            f"Avg Timeframe Alignment: {llm_stats.get('avg_timeframe_alignment', 0):.1%}"
        )
        logger.info(
            f"Avg Pattern Clarity: {llm_stats.get('avg_pattern_clarity', 0):.1%}"
        )

        # Performance by confidence level
        perf_by_conf = results.get("performance_by_confidence", {})
        if perf_by_conf:
            logger.info("\nPerformance by LLM Confidence Level:")
            for level, stats in perf_by_conf.items():
                logger.info(f"\n{level.upper()} Confidence:")
                logger.info(f"  Count: {stats.get('count', 0)}")
                logger.info(f"  Win Rate: {stats.get('win_rate', 0):.1%}")
                logger.info(f"  Avg PnL: ${stats.get('avg_pnl', 0):.2f}")
                logger.info(f"  Total PnL: ${stats.get('total_pnl', 0):.2f}")

        # Save results
        output_dir = Path("output/llm_backtest")
        output_dir.mkdir(parents=True, exist_ok=True)

        results_file = (
            output_dir
            / f'backtest_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        # Save validation report
        report_file = (
            output_dir
            / f'validation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        backtester.save_validation_report(str(report_file))

        logger.info(f"\nResults saved to: {results_file}")
        logger.info(f"Validation report: {report_file}")

        # Key insights
        logger.info("\n" + "=" * 60)
        logger.info("KEY INSIGHTS")
        logger.info("=" * 60)

        if llm_stats.get("acceptance_rate", 0) < 0.5:
            logger.info(
                "⚠️  Low signal acceptance rate - LLM is filtering out many signals"
            )
            logger.info("   Consider adjusting ML model or LLM threshold")

        if perf_by_conf.get("high", {}).get("win_rate", 0) > perf_by_conf.get(
            "low", {}
        ).get("win_rate", 0):
            logger.info("✅ Higher LLM confidence correlates with better performance")
            logger.info("   The visual validation is adding value")
        else:
            logger.info("⚠️  LLM confidence doesn't strongly correlate with performance")
            logger.info("   Consider refining the validation prompts")

        if llm_stats.get("avg_timeframe_alignment", 0) > 0.7:
            logger.info("✅ Good multi-timeframe alignment in accepted signals")
        else:
            logger.info("⚠️  Low timeframe alignment - signals may be noisy")

    except Exception as e:
        logger.error(f"Backtest error: {e}")
        import traceback

        traceback.print_exc()

    logger.info("\n" + "=" * 60)
    logger.info("BACKTEST COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_llm_backtest())
