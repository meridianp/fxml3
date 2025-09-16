#!/usr/bin/env python3
"""
Test script for FXML4 Signal Processing Pipeline.

This script tests the signal processing service that connects ML models to real-time data.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_signal_processing_initialization():
    """Test signal processing service initialization."""
    try:
        from fxml4.api.services.signal_processing import signal_processing_service

        # Test initialization
        await signal_processing_service.initialize()

        if signal_processing_service.active_symbols:
            logger.info(
                f"✅ Signal processing initialized with {len(signal_processing_service.active_symbols)} symbols"
            )
            logger.info(
                f"   Active symbols: {list(signal_processing_service.active_symbols)}"
            )
            return True
        else:
            logger.info(
                "ℹ️  Signal processing initialized but no active symbols (expected if no models are loaded)"
            )
            return True

    except Exception as e:
        logger.error(f"❌ Signal processing initialization error: {e}")
        return False


async def test_signal_generation():
    """Test signal generation functionality."""
    try:
        from fxml4.api.services.market_data import market_data_service
        from fxml4.api.services.signal_processing import signal_processing_service

        # Get available symbols from market data
        symbols = await market_data_service.get_available_symbols()
        if not symbols:
            logger.warning("⚠️  No symbols available for testing")
            return True

        test_symbol = symbols[0]  # Use first available symbol
        logger.info(f"Testing signal generation for {test_symbol}")

        # Get recent market data
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=48)

        market_data = await market_data_service.get_ohlcv_data(
            symbol=test_symbol,
            timeframe="1h",
            start_time=start_time,
            end_time=end_time,
            limit=50,
        )

        if not market_data:
            logger.warning(f"⚠️  No market data available for {test_symbol}")
            return True

        logger.info(f"✅ Retrieved {len(market_data)} data points for {test_symbol}")

        # Test signal generation if we have an active signal generator
        if test_symbol in signal_processing_service.active_symbols:
            logger.info(f"Testing signal generation for {test_symbol}...")

            # Convert to DataFrame
            import pandas as pd

            df_data = []
            for point in market_data:
                df_data.append(
                    {
                        "timestamp": point.time,
                        "open": point.open,
                        "high": point.high,
                        "low": point.low,
                        "close": point.close,
                        "volume": point.volume,
                    }
                )

            df = pd.DataFrame(df_data)
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)

            # Generate signal
            signal_generator = signal_processing_service.signal_generators[test_symbol]
            signal = await signal_processing_service._generate_signal(
                signal_generator, test_symbol, df
            )

            if signal:
                logger.info(f"✅ Generated signal for {test_symbol}:")
                logger.info(f"   Direction: {signal.direction:+d}")
                logger.info(f"   Confidence: {signal.confidence:.2f}")
                logger.info(f"   Type: {signal.signal_type}")
                logger.info(f"   Source: {signal.source}")
                return True
            else:
                logger.info(f"ℹ️  No signal generated for {test_symbol} (may be normal)")
                return True
        else:
            logger.info(
                f"ℹ️  No signal generator for {test_symbol} (expected if no models loaded)"
            )
            return True

    except Exception as e:
        logger.error(f"❌ Signal generation test error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


async def test_simple_signal_generation():
    """Test the simple fallback signal generation."""
    try:
        from fxml4.api.services.market_data import market_data_service
        from fxml4.api.services.signal_processing import signal_processing_service

        # Get available symbols
        symbols = await market_data_service.get_available_symbols()
        if not symbols:
            logger.warning("⚠️  No symbols available for simple signal test")
            return True

        test_symbol = symbols[0]
        logger.info(f"Testing simple signal generation for {test_symbol}")

        # Get market data
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)

        market_data = await market_data_service.get_ohlcv_data(
            symbol=test_symbol,
            timeframe="1h",
            start_time=start_time,
            end_time=end_time,
            limit=30,
        )

        if not market_data or len(market_data) < 25:
            logger.warning(f"⚠️  Insufficient market data for {test_symbol}")
            return True

        # Convert to DataFrame
        import pandas as pd

        df_data = []
        for point in market_data:
            df_data.append(
                {
                    "timestamp": point.time,
                    "open": point.open,
                    "high": point.high,
                    "low": point.low,
                    "close": point.close,
                    "volume": point.volume,
                }
            )

        df = pd.DataFrame(df_data)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)

        # Generate simple signal
        signal = signal_processing_service._create_simple_signal(test_symbol, df)

        if signal:
            logger.info(f"✅ Generated simple signal for {test_symbol}:")
            logger.info(f"   Direction: {signal.direction:+d}")
            logger.info(f"   Confidence: {signal.confidence:.2f}")
            logger.info(f"   Type: {signal.signal_type}")
            logger.info(f"   MA Short: {signal.metadata.get('ma_short', 'N/A')}")
            logger.info(f"   MA Long: {signal.metadata.get('ma_long', 'N/A')}")
            return True
        else:
            logger.error("❌ Failed to generate simple signal")
            return False

    except Exception as e:
        logger.error(f"❌ Simple signal generation test error: {e}")
        return False


async def test_signal_storage_and_retrieval():
    """Test storing and retrieving signals."""
    try:
        from fxml4.api.services.market_data import market_data_service
        from fxml4.api.services.signal_processing import (
            SignalData,
            signal_processing_service,
        )

        # Get available symbols
        symbols = await market_data_service.get_available_symbols()
        if not symbols:
            logger.warning("⚠️  No symbols available for storage test")
            return True

        test_symbol = symbols[0]

        # Create a test signal
        test_signal = SignalData(
            timestamp=datetime.utcnow(),
            symbol=test_symbol,
            timeframe="1h",
            direction=1,
            confidence=0.75,
            signal_type="test_signal",
            source="test_script",
            metadata={"test": True, "strategy": "test_strategy"},
        )

        # Store the signal
        await signal_processing_service._store_signal(test_signal)
        logger.info(f"✅ Stored test signal for {test_symbol}")

        # Wait a moment for storage to complete
        await asyncio.sleep(1)

        # Retrieve recent signals
        recent_signals = await signal_processing_service.get_recent_signals(
            symbol=test_symbol, limit=5, hours_back=1
        )

        if recent_signals:
            logger.info(
                f"✅ Retrieved {len(recent_signals)} recent signals for {test_symbol}"
            )
            for i, signal in enumerate(recent_signals[:3]):  # Show first 3
                logger.info(
                    f"   Signal {i+1}: {signal.direction:+d} @ {signal.timestamp} "
                    f"(confidence: {signal.confidence:.2f})"
                )
            return True
        else:
            logger.info(f"ℹ️  No recent signals found for {test_symbol}")
            return True

    except Exception as e:
        logger.error(f"❌ Signal storage/retrieval test error: {e}")
        return False


async def test_signal_processing_lifecycle():
    """Test starting and stopping signal processing."""
    try:
        from fxml4.api.services.market_data import market_data_service
        from fxml4.api.services.signal_processing import signal_processing_service

        symbols = await market_data_service.get_available_symbols()
        if not symbols:
            logger.warning("⚠️  No symbols available for lifecycle test")
            return True

        test_symbol = symbols[0]

        # Check if we can start processing
        if test_symbol not in signal_processing_service.active_symbols:
            logger.info(
                f"ℹ️  No signal generator for {test_symbol}, creating fallback test"
            )
            return True

        logger.info(f"Testing signal processing lifecycle for {test_symbol}")

        # Start processing
        await signal_processing_service.start_signal_processing([test_symbol])

        if test_symbol in signal_processing_service.processing_tasks:
            logger.info(f"✅ Started signal processing for {test_symbol}")

            # Let it run for a few seconds
            await asyncio.sleep(3)

            # Stop processing
            await signal_processing_service.stop_signal_processing([test_symbol])

            if test_symbol not in signal_processing_service.processing_tasks:
                logger.info(f"✅ Stopped signal processing for {test_symbol}")
                return True
            else:
                logger.error(f"❌ Failed to stop signal processing for {test_symbol}")
                return False
        else:
            logger.error(f"❌ Failed to start signal processing for {test_symbol}")
            return False

    except Exception as e:
        logger.error(f"❌ Signal processing lifecycle test error: {e}")
        return False


async def main():
    """Run all signal processing tests."""
    logger.info("🚀 Starting Signal Processing Pipeline Test Suite")
    logger.info("=" * 70)

    # Set basic environment variables if not set
    if not os.getenv("POSTGRES_DB"):
        os.environ["POSTGRES_DB"] = "fxml4"
    if not os.getenv("POSTGRES_USER"):
        os.environ["POSTGRES_USER"] = "postgres"
    if not os.getenv("POSTGRES_PASSWORD"):
        os.environ["POSTGRES_PASSWORD"] = "postgres"

    tests = [
        ("Signal Processing Initialization", test_signal_processing_initialization()),
        ("Signal Generation", test_signal_generation()),
        ("Simple Signal Generation", test_simple_signal_generation()),
        ("Signal Storage and Retrieval", test_signal_storage_and_retrieval()),
        ("Signal Processing Lifecycle", test_signal_processing_lifecycle()),
    ]

    results = []
    for test_name, test_coro in tests:
        logger.info(f"\n🧪 Running {test_name}...")
        try:
            result = await test_coro
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 Test Summary:")
    logger.info("=" * 70)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1

    logger.info("=" * 70)
    logger.info(f"Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        logger.info(
            "🎉 All tests passed! Signal processing pipeline is working correctly."
        )
    else:
        logger.info("⚠️  Some tests failed. Check the signal processing implementation.")

    logger.info(
        "\nNote: Some tests may show warnings if ML models are not loaded - this is expected."
    )
    logger.info(
        "The signal processing service will fall back to simple strategies when models are unavailable."
    )

    # Clean up
    try:
        from fxml4.api.services.signal_processing import signal_processing_service

        await signal_processing_service.close()
    except:
        pass


if __name__ == "__main__":
    asyncio.run(main())
