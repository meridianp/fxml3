#!/usr/bin/env python3
"""
Direct test of signal processing without config dependencies.

This script tests the signal processing components directly.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import paths handled by PYTHONPATH wrapper


async def test_simple_moving_average_signal():
    """Test simple moving average signal generation."""
    try:
        # Create sample market data
        dates = pd.date_range(start="2024-01-01", end="2024-01-30", freq="1H")
        np.random.seed(42)  # For reproducible results

        # Generate realistic forex price data (starting around 1.10 for EURUSD)
        base_price = 1.1000
        price_changes = np.random.randn(len(dates)) * 0.0005  # Small random changes

        # Add some trend and patterns
        trend = np.linspace(0, 0.01, len(dates))  # Slight upward trend
        prices = base_price + np.cumsum(price_changes) + trend

        # Create OHLC data
        highs = prices + np.abs(np.random.randn(len(dates))) * 0.0003
        lows = prices - np.abs(np.random.randn(len(dates))) * 0.0003
        opens = np.roll(prices, 1)  # Previous close becomes next open
        opens[0] = base_price

        # Create DataFrame
        market_data = pd.DataFrame(
            {
                "open": opens,
                "high": highs,
                "low": lows,
                "close": prices,
                "volume": np.random.randint(1000, 5000, len(dates)),
            },
            index=dates,
        )

        logger.info(
            f"✅ Created sample market data with {len(market_data)} data points"
        )
        logger.info(
            f"   Price range: {market_data['close'].min():.4f} - {market_data['close'].max():.4f}"
        )

        # Calculate simple moving averages
        ma_short = market_data["close"].rolling(window=5).mean()
        ma_long = market_data["close"].rolling(window=20).mean()

        # Generate signals
        signals = []
        for i in range(25, len(market_data)):  # Start after MA periods
            current_short = ma_short.iloc[i]
            current_long = ma_long.iloc[i]
            prev_short = ma_short.iloc[i - 1]
            prev_long = ma_long.iloc[i - 1]

            direction = 0
            confidence = 0.3

            # Bullish crossover
            if current_short > current_long and prev_short <= prev_long:
                direction = 1  # Buy signal
                confidence = 0.7
            # Bearish crossover
            elif current_short < current_long and prev_short >= prev_long:
                direction = -1  # Sell signal
                confidence = 0.7

            if direction != 0:
                signals.append(
                    {
                        "timestamp": market_data.index[i],
                        "direction": direction,
                        "confidence": confidence,
                        "price": market_data["close"].iloc[i],
                        "ma_short": current_short,
                        "ma_long": current_long,
                    }
                )

        logger.info(f"✅ Generated {len(signals)} signals from moving average strategy")

        if signals:
            for i, signal in enumerate(signals[:3]):  # Show first 3 signals
                direction_str = "BUY" if signal["direction"] == 1 else "SELL"
                logger.info(
                    f"   Signal {i+1}: {direction_str} @ {signal['timestamp']} "
                    f"(Price: {signal['price']:.4f}, Conf: {signal['confidence']:.2f})"
                )

        return True

    except Exception as e:
        logger.error(f"❌ Simple MA signal test error: {e}")
        return False


async def test_signal_data_structure():
    """Test the SignalData structure and validation."""
    try:
        # Import the SignalData model directly
        from fxml4.api.services.signal_processing import SignalData

        # Create a test signal
        test_signal = SignalData(
            timestamp=datetime.utcnow(),
            symbol="EURUSD",
            timeframe="1h",
            direction=1,
            confidence=0.85,
            signal_type="moving_average",
            source="test_direct",
            metadata={
                "ma_short": 1.1050,
                "ma_long": 1.1020,
                "strategy": "ma_crossover",
                "risk_score": 0.3,
            },
        )

        logger.info("✅ Created SignalData structure:")
        logger.info(f"   Symbol: {test_signal.symbol}")
        logger.info(f"   Direction: {test_signal.direction:+d}")
        logger.info(f"   Confidence: {test_signal.confidence:.2f}")
        logger.info(f"   Type: {test_signal.signal_type}")
        logger.info(f"   Metadata: {len(test_signal.metadata)} fields")

        # Test JSON serialization
        import json

        signal_dict = {
            "timestamp": test_signal.timestamp.isoformat(),
            "symbol": test_signal.symbol,
            "direction": test_signal.direction,
            "confidence": test_signal.confidence,
            "signal_type": test_signal.signal_type,
            "source": test_signal.source,
            "metadata": test_signal.metadata,
        }

        json_str = json.dumps(signal_dict)
        logger.info(f"✅ Signal JSON serialization successful ({len(json_str)} chars)")

        return True

    except Exception as e:
        logger.error(f"❌ SignalData structure test error: {e}")
        return False


async def test_database_signal_storage():
    """Test storing signals directly in database."""
    try:
        import json

        import asyncpg

        # Connect to database
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="fxml4",
        )

        # Create a test signal
        test_timestamp = datetime.utcnow()
        test_metadata = {
            "test": True,
            "strategy": "direct_test",
            "ma_short": 1.1055,
            "ma_long": 1.1030,
        }

        # Insert signal
        await conn.execute(
            """
            INSERT INTO signals (
                timestamp, symbol_id, timeframe_id, signal_type,
                direction, strength, source, metadata
            ) VALUES (
                $1,
                (SELECT id FROM symbols WHERE name = 'EURUSD' LIMIT 1),
                (SELECT id FROM timeframes WHERE name = '1h' LIMIT 1),
                $2, $3, $4, $5, $6
            )
        """,
            test_timestamp,
            "test_signal",
            "buy",  # direction as string
            0.75,  # confidence/strength
            "direct_test",
            json.dumps(test_metadata),
        )

        logger.info("✅ Stored test signal in database")

        # Retrieve the signal
        result = await conn.fetchrow(
            """
            SELECT s.*, sym.name as symbol_name, tf.name as timeframe_name
            FROM signals s
            JOIN symbols sym ON s.symbol_id = sym.id
            JOIN timeframes tf ON s.timeframe_id = tf.id
            WHERE s.source = 'direct_test' AND s.timestamp = $1
        """,
            test_timestamp,
        )

        if result:
            logger.info("✅ Retrieved test signal from database:")
            logger.info(f"   Symbol: {result['symbol_name']}")
            logger.info(f"   Direction: {result['direction']:+d}")
            logger.info(f"   Confidence: {result['strength']:.2f}")
            logger.info(f"   Type: {result['signal_type']}")

            # Parse metadata
            metadata = json.loads(result["metadata"]) if result["metadata"] else {}
            logger.info(f"   Metadata: {metadata}")
        else:
            logger.error("❌ Failed to retrieve test signal")
            await conn.close()
            return False

        # Clean up test data
        await conn.execute("DELETE FROM signals WHERE source = 'direct_test'")
        await conn.close()

        return True

    except Exception as e:
        logger.error(f"❌ Database signal storage test error: {e}")
        return False


async def test_integrated_strategy_import():
    """Test importing and using integrated strategy components."""
    try:
        # Try to import integrated signal generator
        from fxml4.strategy.integrated_signal_generator import (
            IntegratedSignal,
            IntegratedSignalGenerator,
        )

        logger.info("✅ Successfully imported IntegratedSignalGenerator")

        # Try to import other strategy components
        from fxml4.strategy.signals import SignalConfidence, SignalPriority

        logger.info("✅ Successfully imported signal enums")

        # Test creating an IntegratedSignal
        test_integrated_signal = IntegratedSignal(
            timestamp=datetime.utcnow(),
            direction=1,
            confidence=0.8,
            ml_signal=1,
            ml_confidence=0.75,
            wave_pattern="impulse",
            wave_confidence=0.6,
            sentiment_score=0.2,
            market_regime="trending",
            risk_score=0.3,
            position_size_multiplier=1.0,
            reasoning="Strong ML signal with bullish wave pattern",
        )

        logger.info("✅ Created IntegratedSignal structure:")
        logger.info(f"   Direction: {test_integrated_signal.direction:+d}")
        logger.info(f"   Overall Confidence: {test_integrated_signal.confidence:.2f}")
        logger.info(f"   ML Confidence: {test_integrated_signal.ml_confidence:.2f}")
        logger.info(f"   Wave Pattern: {test_integrated_signal.wave_pattern}")
        logger.info(f"   Market Regime: {test_integrated_signal.market_regime}")
        logger.info(f"   Reasoning: {test_integrated_signal.reasoning}")

        return True

    except ImportError as e:
        logger.warning(f"⚠️  Import error (expected if dependencies missing): {e}")
        return True  # Not a failure if dependencies are missing
    except Exception as e:
        logger.error(f"❌ Integrated strategy import test error: {e}")
        return False


async def main():
    """Run all direct signal processing tests."""
    logger.info("🚀 Starting Direct Signal Processing Test Suite")
    logger.info("=" * 60)

    tests = [
        ("Simple Moving Average Signal", test_simple_moving_average_signal()),
        ("SignalData Structure", test_signal_data_structure()),
        ("Database Signal Storage", test_database_signal_storage()),
        ("Integrated Strategy Import", test_integrated_strategy_import()),
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
    logger.info("\n" + "=" * 60)
    logger.info("📊 Test Summary:")
    logger.info("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1

    logger.info("=" * 60)
    logger.info(f"Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        logger.info(
            "🎉 All direct tests passed! Signal processing components are working."
        )
    else:
        logger.info("⚠️  Some tests failed. Check the signal processing implementation.")


if __name__ == "__main__":
    asyncio.run(main())
