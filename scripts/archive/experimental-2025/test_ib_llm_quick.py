#!/usr/bin/env python3
"""Quick test of IB data with LLM validation."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from fxml4.data.ib_mtf_data_fetcher import IBDataManager
from fxml4.llm_integration.multimodal_mtf_validator import MultiTimeframeChartValidator


async def quick_test():
    """Quick test with minimal data."""
    logger.info("Starting quick IB + LLM test...")

    # Connect to IB
    ib_manager = IBDataManager(port=4002)

    # Fetch just 2 timeframes for speed
    timeframes = ["4H", "D"]
    symbol = "GBPUSD"

    logger.info(f"Fetching {symbol} data for timeframes: {timeframes}")
    price_data = ib_manager.get_multi_timeframe_data(
        symbol, timeframes, use_cache=False
    )

    if not price_data:
        logger.error("No data received from IB")
        return

    # Log what we got
    for tf, df in price_data.items():
        logger.info(f"{tf}: {len(df)} bars, latest close: {df['close'].iloc[-1]:.5f}")

    # Create simple signal
    signal = {
        "symbol": symbol,
        "direction": "BUY",
        "confidence": 0.75,
        "entry_price": price_data["4H"]["close"].iloc[-1],
        "stop_loss": price_data["4H"]["close"].iloc[-1] - 0.0050,
        "take_profit": price_data["4H"]["close"].iloc[-1] + 0.0100,
        "timeframe": "4H",
        "timestamp": price_data["4H"].index[-1],
        "reason": "IB real-time data test",
    }

    logger.info(f"\nTest signal: {signal['direction']} at {signal['entry_price']:.5f}")

    # Initialize validator with minimal config
    validator = MultiTimeframeChartValidator(
        config={"timeframes": timeframes, "candles_per_timeframe": {"4H": 50, "D": 20}}
    )

    # Calculate minimal indicators
    indicators = {}
    for tf, df in price_data.items():
        indicators[tf] = {
            "sma_20": df["close"].rolling(20).mean(),
            "sma_50": (
                df["close"].rolling(50).mean()
                if len(df) >= 50
                else df["close"].rolling(20).mean()
            ),
        }

    logger.info("\nGenerating chart and validating with LLM...")

    try:
        # Validate
        validation = await validator.validate_trading_signal_mtf(
            signal, price_data, indicators
        )

        logger.info(
            f"\nValidation result: {'✅ VALID' if validation.get('valid') else '❌ INVALID'}"
        )
        logger.info(f"LLM Confidence: {validation.get('llm_confidence', 0):.1%}")

        if validation.get("error"):
            logger.error(f"Error: {validation['error']}")

    except Exception as e:
        logger.error(f"Validation error: {e}")
        import traceback

        traceback.print_exc()

    # Disconnect
    ib_manager.fetcher.disconnect()
    logger.info("\nTest complete!")


if __name__ == "__main__":
    asyncio.run(quick_test())
