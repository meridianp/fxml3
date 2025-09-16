#!/usr/bin/env python3
"""Demo test of multi-timeframe visual validation using Interactive Brokers real-time data."""

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

from fxml4.data.ib_mtf_data_fetcher import IBDataManager, IBMultiTimeframeDataFetcher

# Import our modules
from fxml4.llm_integration.multimodal_mtf_validator import MultiTimeframeChartValidator
from fxml4.utils.timeframe_aggregator import TimeframeAggregator


async def demo_mtf_validation_with_ib():
    """Demo multi-timeframe validation with real-time IB data."""
    logger.info("\n" + "=" * 60)
    logger.info("MULTI-TIMEFRAME VISUAL VALIDATION DEMO - IB REAL-TIME DATA")
    logger.info("=" * 60)

    # Initialize components
    timeframes_to_analyze = ["D", "4H", "1H", "15m"]  # Multiple timeframes

    aggregator = TimeframeAggregator()

    # Initialize IB data manager - connect to paper trading port
    logger.info("\nConnecting to Interactive Brokers TWS API on port 4002...")
    ib_manager = IBDataManager(host="127.0.0.1", port=4002)

    # Symbol to analyze
    symbol = "GBPUSD"

    # Fetch multi-timeframe data from IB
    logger.info(
        f"\nFetching real-time multi-timeframe data for {symbol} from Interactive Brokers..."
    )
    logger.info("Timeframes: " + ", ".join(timeframes_to_analyze))

    try:
        # Use the high-level data manager which includes caching
        price_data_dict = ib_manager.get_multi_timeframe_data(
            symbol=symbol,
            timeframes=timeframes_to_analyze,
            use_cache=False,  # Get fresh data for demo
        )

        # Check if we got any data
        if not price_data_dict or all(df.empty for df in price_data_dict.values()):
            logger.error("No data received from Interactive Brokers")
            logger.info("Make sure TWS/Gateway is running and connected")
            return

    except Exception as e:
        logger.error(f"Error fetching IB data: {e}")
        logger.info("\nTroubleshooting tips:")
        logger.info("1. Ensure TWS or IB Gateway is running")
        logger.info("2. Check that API connections are enabled in TWS")
        logger.info("3. Verify port 4002 is correct (paper trading)")
        logger.info("4. Make sure you're logged into your paper account")
        return

    # Log data received
    logger.info("\nReceived data from Interactive Brokers:")
    for tf, data in price_data_dict.items():
        if not data.empty:
            logger.info(f"  {tf}: {len(data)} bars (latest: {data.index[-1]})")
        else:
            logger.info(f"  {tf}: No data")

    # Update timeframes based on what we actually received
    timeframes_to_analyze = [
        tf
        for tf in timeframes_to_analyze
        if tf in price_data_dict and not price_data_dict[tf].empty
    ]

    if not timeframes_to_analyze:
        logger.error("No valid timeframes with data")
        return

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
    logger.info("\nCalculating technical indicators for each timeframe...")

    # Use IB manager's built-in indicator calculation
    indicators_dict = {}
    for tf, data in price_data_dict.items():
        if not data.empty:
            # Calculate indicators using the IB manager
            data_with_indicators = ib_manager.calculate_indicators(data)

            # Extract indicators into separate dict
            indicators = {}
            for col in data_with_indicators.columns:
                if col not in ["open", "high", "low", "close", "volume"]:
                    indicators[col] = data_with_indicators[col]

            # Add support/resistance levels
            indicators["support_levels"] = aggregator._find_support_resistance(
                data, "support"
            )
            indicators["resistance_levels"] = aggregator._find_support_resistance(
                data, "resistance"
            )

            indicators_dict[tf] = indicators

    # Create test signals at different points
    # Use the primary timeframe data (usually 4H or the first available)
    primary_tf = "4H" if "4H" in price_data_dict else list(price_data_dict.keys())[0]
    primary_data = price_data_dict[primary_tf]

    # Create signals at recent points in time
    signal_indices = [-10, -5, -2]  # More recent points for real-time data
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
                "confidence": 0.70 + (idx * 0.05),  # Higher confidence
                "entry_price": price,
                "stop_loss": price - 0.0050 if direction == "BUY" else price + 0.0050,
                "take_profit": price + 0.0100 if direction == "BUY" else price - 0.0100,
                "timeframe": primary_tf,
                "timestamp": timestamp,
                "data_source": "Interactive Brokers",
                "reason": [
                    "Multi-timeframe trend alignment with real-time data",
                    "Live market divergence signals",
                    "Real-time support/resistance confirmation",
                ][idx],
            }

            test_signals.append(signal)

    logger.info(f"\nCreated {len(test_signals)} test signals from IB real-time data")

    # Test each signal with multi-timeframe validation
    for i, signal in enumerate(test_signals):
        logger.info(f"\n{'='*60}")
        logger.info(f"TESTING SIGNAL {i+1}/{len(test_signals)} - REAL-TIME IB DATA")
        logger.info(f"{'='*60}")
        logger.info(f"Direction: {signal['direction']}")
        logger.info(f"ML Confidence: {signal['confidence']:.1%}")
        logger.info(f"Reason: {signal['reason']}")
        logger.info(f"Primary Timeframe: {signal['timeframe']}")
        logger.info(f"Signal Time: {signal['timestamp']}")
        logger.info(f"Data Source: {signal['data_source']}")

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
            logger.info(
                "\nGenerating multi-timeframe technical analysis chart with IB data..."
            )
            validation = await mtf_validator.validate_trading_signal_mtf(
                signal, aligned_data, aligned_indicators
            )

            logger.info("\n--- MULTI-TIMEFRAME VALIDATION RESULTS (IB REAL-TIME) ---")
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
            result_file = f'output/mtf_validation_ib_demo_{i+1}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            Path("output").mkdir(exist_ok=True)

            with open(result_file, "w") as f:
                json.dump(
                    {
                        "signal": signal,
                        "validation": validation,
                        "timeframes_analyzed": list(aligned_data.keys()),
                        "data_source": "Interactive Brokers TWS API",
                        "timestamp": datetime.now().isoformat(),
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
    logger.info("IB MULTI-TIMEFRAME DEMO COMPLETE")
    logger.info(f"{'='*60}")
    logger.info("\nKey Advantages of IB Real-Time Data:")
    logger.info("1. No delay - real-time market prices")
    logger.info("2. Accurate bid/ask spreads")
    logger.info("3. True intraday data (not synthetic)")
    logger.info("4. Reliable volume information")
    logger.info("5. Professional-grade data quality")

    # Disconnect from IB
    logger.info("\nDisconnecting from Interactive Brokers...")
    ib_manager.fetcher.disconnect()


if __name__ == "__main__":
    # Run the demo
    asyncio.run(demo_mtf_validation_with_ib())
