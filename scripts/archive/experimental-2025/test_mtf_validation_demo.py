#!/usr/bin/env python3
"""Demo test of multi-timeframe visual validation."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from fxml4.data.mtf_data_fetcher import MultiTimeframeDataFetcher

# Import our modules
from fxml4.llm_integration.multimodal_mtf_validator import MultiTimeframeChartValidator
from fxml4.utils.timeframe_aggregator import TimeframeAggregator


async def demo_mtf_validation():
    """Demo multi-timeframe validation with real data."""
    logger.info("\n" + "=" * 60)
    logger.info("MULTI-TIMEFRAME VISUAL VALIDATION DEMO")
    logger.info("=" * 60)

    # Initialize components
    timeframes_to_analyze = ["D", "4H", "1H", "15m"]  # Multiple timeframes

    aggregator = TimeframeAggregator()
    data_fetcher = MultiTimeframeDataFetcher(source="yfinance")

    # Symbol to analyze
    symbol = "GBPUSD"

    # Fetch multi-timeframe data
    logger.info(f"\nFetching multi-timeframe data for {symbol}...")
    logger.info("This may take a moment as we download from Yahoo Finance...")

    try:
        price_data_dict = await data_fetcher.fetch_multi_timeframe_data(
            symbol=symbol, timeframes=timeframes_to_analyze, lookback_days=30
        )

        # Check if we got any data
        if not price_data_dict or all(df.empty for df in price_data_dict.values()):
            logger.warning("No data received from API, falling back to local data...")
            raise ValueError("No data from API")

    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        logger.info("\nFalling back to local data...")

        # Fallback to local data if available
        base_data_path = "data/processed/4h/GBPUSD_4H_features_complete.parquet"
        if Path(base_data_path).exists():
            base_data = pd.read_parquet(base_data_path)
            recent_data = base_data.tail(500).copy()

            # Create a simple dict with just 4H data
            price_data_dict = {
                "4H": recent_data,
                "D": aggregator.aggregate_to_timeframes(recent_data, "4H", ["D"]).get(
                    "D", pd.DataFrame()
                ),
            }
            timeframes_to_analyze = ["D", "4H"]  # Reduced set
        else:
            logger.error("No data available")
            return

    # Log aggregation results
    for tf, data in price_data_dict.items():
        logger.info(f"  {tf}: {len(data)} bars")

    # Update timeframes based on what we actually have
    timeframes_to_analyze = list(price_data_dict.keys())

    # Initialize validator with actual timeframes
    mtf_validator = MultiTimeframeChartValidator(
        config={
            "timeframes": timeframes_to_analyze,
            "candles_per_timeframe": {
                "D": 30,  # 30 daily candles
                "4H": 60,  # 60 4-hour candles
                "1H": 100,  # 100 1-hour candles
                "15m": 100,  # 100 15-minute candles
            },
        }
    )

    # Calculate indicators for each timeframe
    logger.info("\nCalculating indicators for each timeframe...")
    indicators_dict = aggregator.calculate_mtf_indicators(price_data_dict)

    # Create test signals at different points
    # Use the primary timeframe data (usually 4H or the first available)
    primary_tf = "4H" if "4H" in price_data_dict else list(price_data_dict.keys())[0]
    primary_data = price_data_dict[primary_tf]

    # Create signals at different points in time
    signal_indices = [-30, -15, -5]  # Different points in history
    test_signals = []

    for idx, offset in enumerate(signal_indices):
        if len(primary_data) > abs(offset):
            price = primary_data["close"].iloc[offset]
            timestamp = primary_data.index[offset]

            # Alternate between buy and sell signals
            direction = "BUY" if idx % 2 == 0 else "SELL"

            signal = {
                "symbol": symbol,
                "direction": direction,
                "confidence": 0.65 + (idx * 0.05),  # Increasing confidence
                "entry_price": price,
                "stop_loss": price - 0.0050 if direction == "BUY" else price + 0.0050,
                "take_profit": price + 0.0100 if direction == "BUY" else price - 0.0100,
                "timeframe": primary_tf,
                "timestamp": timestamp,
                "reason": [
                    "Multi-timeframe trend alignment",
                    "Divergence across timeframes",
                    "Strong support bounce on multiple timeframes",
                ][idx],
            }

            test_signals.append(signal)

    # Test each signal with multi-timeframe validation
    for i, signal in enumerate(test_signals):
        logger.info(f"\n{'='*60}")
        logger.info(f"TESTING SIGNAL {i+1}/{len(test_signals)}")
        logger.info(f"{'='*60}")
        logger.info(f"Direction: {signal['direction']}")
        logger.info(f"ML Confidence: {signal['confidence']:.1%}")
        logger.info(f"Reason: {signal['reason']}")
        logger.info(f"Primary Timeframe: {signal['timeframe']}")

        # Align data to signal timestamp
        aligned_data = aggregator.align_timeframe_data(
            price_data_dict, reference_time=signal["timestamp"]
        )

        # Get aligned indicators
        aligned_indicators = {}
        for tf in aligned_data.keys():
            tf_indicators = {}
            if tf in indicators_dict:
                for ind_name, ind_data in indicators_dict[tf].items():
                    if isinstance(ind_data, pd.Series) and hasattr(ind_data, "index"):
                        # Align series data
                        tf_indicators[ind_name] = ind_data[
                            ind_data.index <= signal["timestamp"]
                        ]
                    elif isinstance(ind_data, list):
                        # Keep lists as is (e.g., support/resistance levels)
                        tf_indicators[ind_name] = ind_data
                    else:
                        # Keep other data as is
                        tf_indicators[ind_name] = ind_data
                aligned_indicators[tf] = tf_indicators

        try:
            # Validate with multi-timeframe analysis
            logger.info("\nGenerating multi-timeframe technical analysis chart...")
            validation = await mtf_validator.validate_trading_signal_mtf(
                signal, aligned_data, aligned_indicators
            )

            logger.info("\n--- MULTI-TIMEFRAME VALIDATION RESULTS ---")
            logger.info(f"Valid: {'✅ YES' if validation.get('valid') else '❌ NO'}")
            logger.info(f"LLM Confidence: {validation.get('llm_confidence', 0):.1%}")
            logger.info(
                f"Timeframe Alignment: {validation.get('timeframe_alignment', 0):.1%}"
            )
            logger.info(f"Pattern Clarity: {validation.get('pattern_clarity', 0):.1%}")
            logger.info(
                f"Enhanced Confidence: {validation.get('enhanced_confidence', 0):.1%}"
            )

            if validation.get("visual_patterns"):
                logger.info(
                    f"\nVisual Patterns: {', '.join(validation['visual_patterns'])}"
                )

            if validation.get("optimal_entry_timeframe"):
                logger.info(
                    f"Optimal Entry Timeframe: {validation['optimal_entry_timeframe']}"
                )

            if validation.get("key_observations"):
                logger.info("\nKey Multi-Timeframe Observations:")
                for obs in validation["key_observations"]:
                    logger.info(f"  - {obs}")

            if validation.get("concerns"):
                logger.info("\nConcerns:")
                for concern in validation["concerns"]:
                    logger.info(f"  ⚠️ {concern}")

            if validation.get("overall_assessment"):
                logger.info(f"\nOverall Assessment: {validation['overall_assessment']}")

            # Save validation result
            result_file = f'output/mtf_validation_demo_{i+1}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(result_file, "w") as f:
                json.dump(
                    {
                        "signal": signal,
                        "validation": validation,
                        "timeframes_analyzed": list(aligned_data.keys()),
                    },
                    f,
                    indent=2,
                    default=str,
                )
            logger.info(f"\nSaved result to: {result_file}")

        except Exception as e:
            logger.error(f"Error in validation: {e}")
            import traceback

            traceback.print_exc()

        # Small delay between tests
        await asyncio.sleep(2)

    logger.info(f"\n{'='*60}")
    logger.info("MULTI-TIMEFRAME DEMO COMPLETE")
    logger.info(f"{'='*60}")
    logger.info("\nKey Benefits of Multi-Timeframe Analysis:")
    logger.info("1. Higher timeframe trend confirmation")
    logger.info("2. Better entry timing on lower timeframes")
    logger.info("3. Multiple confluence points for validation")
    logger.info("4. Reduced false signals through alignment")
    logger.info("5. More comprehensive risk assessment")


if __name__ == "__main__":
    asyncio.run(demo_mtf_validation())
