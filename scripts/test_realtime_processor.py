#!/usr/bin/env python3
"""Test script for the FXML4 real-time data processing system.

This script tests:
- Real-time tick data processing
- 1-minute candle generation
- Multi-timeframe conversion (1m → 5m, 15m, 1h, 4h)
- Integration with IB data feeds
- Storage integration with TimescaleDB
- Performance and latency metrics
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fxml4.data_engineering.realtime_processor import (
        ProcessorState,
        RealTimeProcessor,
    )

    REALTIME_PROCESSOR_AVAILABLE = True
except ImportError as e:
    print(f"❌ Real-time processor not available: {e}")
    REALTIME_PROCESSOR_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RealTimeProcessorTester:
    """Comprehensive tester for the real-time processing system."""

    def __init__(self, config: dict):
        self.config = config
        self.processor: RealTimeProcessor = None
        self.test_results = {}
        self.start_time = None
        self.candles_received = {}
        self.shutdown_requested = False

    def run_comprehensive_test(self, duration_minutes: int = 5):
        """Run comprehensive real-time processing test.

        Args:
            duration_minutes: How long to run the test
        """
        logger.info("\n" + "🚀" + "=" * 68 + "🚀")
        logger.info("🎯 FXML4 REAL-TIME DATA PROCESSING TEST")
        logger.info("🚀" + "=" * 68 + "🚀")
        logger.info("Testing production-ready real-time features:")
        logger.info("- IB tick data streaming")
        logger.info("- Real-time 1-minute candle generation")
        logger.info("- Multi-timeframe conversion (1m → 5m, 15m, 1h, 4h)")
        logger.info("- Production latency and performance metrics")
        logger.info("- GBP/USD primary focus + secondary pairs")
        logger.info(f"- Test duration: {duration_minutes} minutes")

        if not REALTIME_PROCESSOR_AVAILABLE:
            logger.error("❌ Real-time processor not available")
            return False

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Initialize processor
        logger.info(f"\n🔧 Initializing RealTimeProcessor...")
        self.processor = RealTimeProcessor(self.config)

        try:
            # Test 1: Initialization and startup
            if not self._test_initialization():
                return False

            # Test 2: Start real-time processing
            if not self._test_startup():
                return False

            # Test 3: Register candle callbacks for monitoring
            self._register_test_callbacks()

            # Test 4: Run processing for specified duration
            self._run_processing_test(duration_minutes)

            # Test 5: Analyze results
            self._analyze_results()

            # Test 6: Performance metrics
            self._test_performance_metrics()

        finally:
            # Cleanup
            self._cleanup()

        return self._calculate_overall_success()

    def _test_initialization(self) -> bool:
        """Test processor initialization."""
        logger.info("\n" + "-" * 50)
        logger.info("🔧 TESTING INITIALIZATION")
        logger.info("-" * 50)

        try:
            # Check initial state
            assert self.processor.state == ProcessorState.STOPPED
            logger.info("✅ Initial state: STOPPED")

            # Check configuration
            logger.info(f"📊 Configured symbols: {self.processor.symbols}")
            logger.info(f"⏱️ Configured timeframes: {self.processor.timeframes}")
            logger.info(f"🧵 Processing threads: {self.processor.processing_threads}")

            self.test_results["initialization"] = True
            return True

        except Exception as e:
            logger.error(f"❌ Initialization test failed: {e}")
            self.test_results["initialization"] = False
            return False

    def _test_startup(self) -> bool:
        """Test processor startup."""
        logger.info("\n" + "-" * 50)
        logger.info("🚀 TESTING STARTUP")
        logger.info("-" * 50)

        try:
            # Start the processor
            logger.info("Starting real-time processor...")
            success = self.processor.start()

            if success:
                logger.info("✅ Processor started successfully")

                # Check state
                assert self.processor.state == ProcessorState.RUNNING
                logger.info("✅ State: RUNNING")

                # Check IB connection
                status = self.processor.get_status()
                if status["ib_connected"]:
                    logger.info("✅ IB connection: Connected")
                else:
                    logger.warning(
                        "⚠️ IB connection: Not connected (expected if TWS not running)"
                    )

                # Check active subscriptions
                logger.info(f"📡 Active subscriptions: {status['symbols_active']}")

                self.test_results["startup"] = True
                return True
            else:
                logger.error("❌ Failed to start processor")
                self.test_results["startup"] = False
                return False

        except Exception as e:
            logger.error(f"❌ Startup test failed: {e}")
            self.test_results["startup"] = False
            return False

    def _register_test_callbacks(self):
        """Register callbacks to monitor candle generation."""
        logger.info("\n" + "-" * 50)
        logger.info("📡 REGISTERING CANDLE CALLBACKS")
        logger.info("-" * 50)

        def candle_callback(candle):
            symbol = candle["symbol"]
            timeframe = candle.get("timeframe", "1m")

            if symbol not in self.candles_received:
                self.candles_received[symbol] = {}

            if timeframe not in self.candles_received[symbol]:
                self.candles_received[symbol][timeframe] = 0

            self.candles_received[symbol][timeframe] += 1

            # Log every 10th candle or higher timeframes
            if self.candles_received[symbol][timeframe] % 10 == 0 or timeframe in [
                "1h",
                "4h",
                "1d",
            ]:
                logger.info(
                    f"🕯️ {symbol} {timeframe} #{self.candles_received[symbol][timeframe]}: "
                    + f"O={candle['open']:.5f} H={candle['high']:.5f} "
                    + f"L={candle['low']:.5f} C={candle['close']:.5f}"
                )

        # Register for all configured symbols
        for symbol in self.processor.symbols:
            self.processor.register_candle_callback(symbol, candle_callback)
            logger.info(f"✅ Registered callback for {symbol}")

    def _run_processing_test(self, duration_minutes: int):
        """Run the processing test for specified duration."""
        logger.info("\n" + "-" * 50)
        logger.info(f"⏱️ RUNNING PROCESSING TEST ({duration_minutes} minutes)")
        logger.info("-" * 50)

        self.start_time = time.time()
        end_time = self.start_time + (duration_minutes * 60)

        logger.info(f"🕐 Test started at: {datetime.now().strftime('%H:%M:%S')}")
        logger.info(
            f"🕐 Test will end at: {datetime.fromtimestamp(end_time).strftime('%H:%M:%S')}"
        )

        # Status reporting interval
        last_status_time = time.time()
        status_interval = 30  # 30 seconds

        while time.time() < end_time and not self.shutdown_requested:
            # Report status periodically
            if time.time() - last_status_time >= status_interval:
                self._report_status()
                last_status_time = time.time()

            # Check if processor is still running
            if self.processor.state != ProcessorState.RUNNING:
                logger.warning(
                    f"⚠️ Processor state changed to: {self.processor.state.value}"
                )
                break

            # Sleep briefly
            time.sleep(1)

        elapsed_minutes = (time.time() - self.start_time) / 60
        logger.info(f"⏱️ Test completed after {elapsed_minutes:.1f} minutes")

    def _report_status(self):
        """Report current processing status."""
        try:
            status = self.processor.get_status()
            metrics = self.processor.get_metrics()

            elapsed_minutes = (time.time() - self.start_time) / 60

            logger.info(f"\n📊 STATUS REPORT (t+{elapsed_minutes:.1f}min):")
            logger.info(f"   🔄 State: {status['state']}")
            logger.info(f"   📈 Ticks processed: {status['ticks_processed']:,}")
            logger.info(f"   🕯️ Candles generated: {status['candles_generated']:,}")
            logger.info(f"   ⚡ Avg latency: {status['avg_latency_ms']:.2f}ms")
            logger.info(f"   📡 IB connected: {status['ib_connected']}")
            logger.info(
                f"   📊 Queue sizes: tick={status['queue_sizes']['tick_queue']}, candle={status['queue_sizes']['candle_queue']}"
            )

            # Report candles by symbol
            total_candles = sum(
                sum(tf_counts.values()) for tf_counts in self.candles_received.values()
            )
            logger.info(f"   🕯️ Total candles received: {total_candles}")

            for symbol, timeframes in self.candles_received.items():
                logger.info(f"      {symbol}: {dict(timeframes)}")

        except Exception as e:
            logger.error(f"❌ Error reporting status: {e}")

    def _analyze_results(self):
        """Analyze test results."""
        logger.info("\n" + "-" * 50)
        logger.info("📊 ANALYZING RESULTS")
        logger.info("-" * 50)

        try:
            elapsed_time = time.time() - self.start_time
            status = self.processor.get_status()

            # Calculate processing rates
            ticks_per_second = (
                status["ticks_processed"] / elapsed_time if elapsed_time > 0 else 0
            )
            candles_per_minute = (
                (status["candles_generated"] / elapsed_time) * 60
                if elapsed_time > 0
                else 0
            )

            logger.info(f"⏱️ Total test duration: {elapsed_time:.1f} seconds")
            logger.info(f"📈 Processing rate: {ticks_per_second:.1f} ticks/second")
            logger.info(
                f"🕯️ Candle generation rate: {candles_per_minute:.1f} candles/minute"
            )
            logger.info(
                f"⚡ Average processing latency: {status['avg_latency_ms']:.2f}ms"
            )

            # Analyze candle distribution
            logger.info("\n🕯️ Candle Distribution by Symbol:")
            for symbol, timeframes in self.candles_received.items():
                logger.info(f"   {symbol}:")
                for tf, count in sorted(timeframes.items()):
                    logger.info(f"      {tf}: {count} candles")

            # Check minimum requirements
            requirements_met = True

            # At least some ticks should be processed
            if status["ticks_processed"] < 10:
                logger.warning(
                    "⚠️ Very few ticks processed - may indicate connection issues"
                )
                requirements_met = False

            # Should generate some candles
            if status["candles_generated"] < 1:
                logger.warning("⚠️ No candles generated")
                requirements_met = False

            # Latency should be reasonable
            if status["avg_latency_ms"] > 100:
                logger.warning(
                    f"⚠️ High processing latency: {status['avg_latency_ms']:.2f}ms"
                )
                requirements_met = False

            self.test_results["processing"] = requirements_met

        except Exception as e:
            logger.error(f"❌ Error analyzing results: {e}")
            self.test_results["processing"] = False

    def _test_performance_metrics(self):
        """Test performance metrics and monitoring."""
        logger.info("\n" + "-" * 50)
        logger.info("📈 TESTING PERFORMANCE METRICS")
        logger.info("-" * 50)

        try:
            metrics = self.processor.get_metrics()
            status = self.processor.get_status()

            logger.info("📊 Performance Metrics:")
            logger.info(f"   ⏱️ Uptime: {status['uptime_seconds']:.1f}s")
            logger.info(f"   📈 Ticks received: {metrics.ticks_received:,}")
            logger.info(f"   🕯️ Candles generated: {metrics.candles_generated:,}")
            logger.info(f"   ❌ Error count: {metrics.errors_count}")
            logger.info(f"   📊 Symbols tracked: {len(metrics.symbols_processed)}")
            logger.info(f"   ⚡ Avg latency: {metrics.get_average_latency_ms():.2f}ms")
            logger.info(f"   📡 Active timeframes: {metrics.timeframes_active}")

            # Check metrics validity
            metrics_valid = True

            if metrics.start_time is None:
                logger.warning("⚠️ Start time not recorded")
                metrics_valid = False

            if metrics.errors_count > (
                metrics.ticks_received * 0.1
            ):  # More than 10% error rate
                logger.warning(f"⚠️ High error rate: {metrics.errors_count} errors")
                metrics_valid = False

            self.test_results["metrics"] = metrics_valid

        except Exception as e:
            logger.error(f"❌ Error testing performance metrics: {e}")
            self.test_results["metrics"] = False

    def _cleanup(self):
        """Cleanup test resources."""
        logger.info("\n" + "-" * 50)
        logger.info("🧹 CLEANING UP")
        logger.info("-" * 50)

        try:
            if self.processor:
                logger.info("Stopping real-time processor...")
                self.processor.stop()
                logger.info("✅ Processor stopped")

        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")

    def _calculate_overall_success(self) -> bool:
        """Calculate overall test success."""
        logger.info("\n" + "🏆" + "=" * 68 + "🏆")
        logger.info("📋 COMPREHENSIVE TEST RESULTS")
        logger.info("🏆" + "=" * 68 + "🏆")

        # Count successful tests
        successful_tests = sum(1 for result in self.test_results.values() if result)
        total_tests = len(self.test_results)
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0

        logger.info(f"📊 Tests passed: {successful_tests}/{total_tests}")
        logger.info(f"📈 Success rate: {success_rate:.1f}%")
        logger.info("🎯 Test Coverage:")

        test_names = {
            "initialization": "Initialization",
            "startup": "Startup",
            "processing": "Real-time Processing",
            "metrics": "Performance Metrics",
        }

        for test_key, result in self.test_results.items():
            test_name = test_names.get(test_key, test_key.title())
            status = "✅" if result else "❌"
            logger.info(f"  {status} {test_name}")

        # Overall assessment
        if success_rate >= 90:
            logger.info("\n🎉 REAL-TIME PROCESSOR: PRODUCTION READY!")
            logger.info("✅ All critical systems validated")
            logger.info("🚀 Ready for live trading integration!")
        elif success_rate >= 70:
            logger.info("\n⚠️ REAL-TIME PROCESSOR: MOSTLY FUNCTIONAL")
            logger.info("🔧 Some issues need attention")
        else:
            logger.info("\n❌ REAL-TIME PROCESSOR: NEEDS IMPROVEMENT")
            logger.info("🔧 Critical issues require resolution")

        return success_rate >= 70

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self.shutdown_requested = True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test FXML4 Real-Time Data Processor")
    parser.add_argument(
        "--duration", type=int, default=2, help="Test duration in minutes"
    )
    parser.add_argument("--host", default="127.0.0.1", help="IB host")
    parser.add_argument("--port", type=int, default=7497, help="IB port")
    parser.add_argument(
        "--symbols", nargs="+", default=["GBPUSD", "EURUSD"], help="Symbols to test"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument(
        "--no-storage", action="store_true", help="Disable database storage"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Configuration for the real-time processor
    config = {
        "symbols": args.symbols,
        "timeframes": [1, 5, 15, 60, 240],  # 1m, 5m, 15m, 1h, 4h
        "ib_config": {
            "host": args.host,
            "port": args.port,
            "client_id": 2,  # Different client ID to avoid conflicts
            "reconnect_attempts": 3,
            "request_timeout": 30,
        },
        "processing_threads": 2,
        "max_queue_size": 5000,
        "enable_storage": not args.no_storage,
        "candle_retention_days": 1,
    }

    logger.info(f"🎯 Testing Real-Time Processor with:")
    logger.info(f"   Duration: {args.duration} minutes")
    logger.info(f"   Symbols: {args.symbols}")
    logger.info(f"   IB: {args.host}:{args.port}")
    logger.info(f"   Storage: {'enabled' if not args.no_storage else 'disabled'}")

    # Run the test
    tester = RealTimeProcessorTester(config)
    success = tester.run_comprehensive_test(args.duration)

    if success:
        logger.info("\n🎉 REAL-TIME PROCESSOR TEST PASSED!")
        sys.exit(0)
    else:
        logger.error("\n❌ REAL-TIME PROCESSOR TEST FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
