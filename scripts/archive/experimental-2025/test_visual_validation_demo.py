#!/usr/bin/env python3
"""Demo test of visual validation with guaranteed signals."""

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

# Import only the chart validator
from fxml4.llm_integration.multimodal_chart_validator import MultiModalChartValidator


async def demo_visual_validation():
    """Demo visual validation with synthetic signals."""
    logger.info("\n" + "=" * 60)
    logger.info("VISUAL VALIDATION DEMO")
    logger.info("=" * 60)

    # Create chart validator
    chart_validator = MultiModalChartValidator(config={})

    # Load some real data
    symbol = "GBPUSD"
    data_path = "data/processed/4h/GBPUSD_4H_features_complete.parquet"

    if not Path(data_path).exists():
        logger.error(f"Data file not found: {data_path}")
        return

    df = pd.read_parquet(data_path)

    # Get recent data
    recent_data = df.tail(200).copy()
    logger.info(f"Loaded {len(recent_data)} bars of {symbol} data")

    # Calculate indicators
    indicators = {
        "sma_20": recent_data["close"].rolling(20).mean(),
        "sma_50": recent_data["close"].rolling(50).mean(),
        "ema_9": recent_data["close"].ewm(span=9).mean(),
        "support_levels": [],
        "resistance_levels": [],
    }

    # Calculate RSI
    delta = recent_data["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    indicators["rsi"] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    bb_sma = recent_data["close"].rolling(20).mean()
    bb_std = recent_data["close"].rolling(20).std()
    indicators["bb_upper"] = bb_sma + (bb_std * 2)
    indicators["bb_middle"] = bb_sma
    indicators["bb_lower"] = bb_sma - (bb_std * 2)

    # Create 3 synthetic signals for testing
    test_signals = [
        {
            "symbol": symbol,
            "direction": "BUY",
            "confidence": 0.75,
            "entry_price": recent_data["close"].iloc[-50],
            "stop_loss": recent_data["close"].iloc[-50] - 0.0040,
            "take_profit": recent_data["close"].iloc[-50] + 0.0080,
            "timeframe": "4H",
            "timestamp": recent_data.index[-50],
            "reason": "Price bounce from support",
        },
        {
            "symbol": symbol,
            "direction": "SELL",
            "confidence": 0.68,
            "entry_price": recent_data["close"].iloc[-30],
            "stop_loss": recent_data["close"].iloc[-30] + 0.0040,
            "take_profit": recent_data["close"].iloc[-30] - 0.0080,
            "timeframe": "4H",
            "timestamp": recent_data.index[-30],
            "reason": "Resistance rejection",
        },
        {
            "symbol": symbol,
            "direction": "BUY",
            "confidence": 0.82,
            "entry_price": recent_data["close"].iloc[-10],
            "stop_loss": recent_data["close"].iloc[-10] - 0.0040,
            "take_profit": recent_data["close"].iloc[-10] + 0.0080,
            "timeframe": "4H",
            "timestamp": recent_data.index[-10],
            "reason": "Bullish breakout",
        },
    ]

    # Test each signal
    for i, signal in enumerate(test_signals):
        logger.info(f"\n{'='*60}")
        logger.info(f"TESTING SIGNAL {i+1}/{len(test_signals)}")
        logger.info(f"{'='*60}")
        logger.info(f"Direction: {signal['direction']}")
        logger.info(f"ML Confidence: {signal['confidence']:.1%}")
        logger.info(f"Reason: {signal['reason']}")

        # Get data window for the signal
        signal_idx = recent_data.index.get_loc(signal["timestamp"])
        window_start = max(0, signal_idx - 100)
        window_end = signal_idx + 1

        window_data = recent_data.iloc[window_start:window_end].copy()
        window_indicators = {
            k: v.iloc[window_start:window_end] if hasattr(v, "iloc") else v
            for k, v in indicators.items()
        }

        try:
            # Validate with visual LLM
            logger.info("\nGenerating technical analysis chart...")
            validation = await chart_validator.validate_trading_signal(
                signal, window_data, window_indicators
            )

            logger.info("\n--- VALIDATION RESULTS ---")
            logger.info(f"Valid: {'✅ YES' if validation.get('valid') else '❌ NO'}")
            logger.info(f"LLM Confidence: {validation.get('llm_confidence', 0):.1%}")
            logger.info(f"Pattern Clarity: {validation.get('pattern_clarity', 0):.1%}")
            logger.info(
                f"Enhanced Confidence: {validation.get('enhanced_confidence', 0):.1%}"
            )

            if validation.get("visual_patterns"):
                logger.info(
                    f"\nVisual Patterns: {', '.join(validation['visual_patterns'])}"
                )

            if validation.get("key_observations"):
                logger.info("\nKey Observations:")
                for obs in validation["key_observations"]:
                    logger.info(f"  - {obs}")

            if validation.get("concerns"):
                logger.info("\nConcerns:")
                for concern in validation["concerns"]:
                    logger.info(f"  ⚠️ {concern}")

            if validation.get("overall_assessment"):
                logger.info(f"\nOverall Assessment: {validation['overall_assessment']}")

            # Save validation result
            result_file = f'output/visual_validation_demo_{i+1}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(result_file, "w") as f:
                json.dump(
                    {"signal": signal, "validation": validation},
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
    logger.info("DEMO COMPLETE")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(demo_visual_validation())
