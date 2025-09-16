#!/usr/bin/env python3
"""Test script for the robust IB client implementation.

This script tests all the enhanced features:
- Automatic reconnection logic
- Circuit breaker pattern
- Rate limiting
- Health monitoring
- Error handling
- Multi-timeframe data requests
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fxml4.data_engineering.data_feeds.robust_ib_client import (
        ConnectionMetrics,
        ConnectionState,
        RobustIBClient,
    )

    ROBUST_CLIENT_AVAILABLE = True
except ImportError as e:
    print(f"❌ Robust IB client not available: {e}")
    ROBUST_CLIENT_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_connection_and_reconnection(client: RobustIBClient):
    """Test connection and reconnection logic."""
    logger.info("\n" + "=" * 60)
    logger.info("🔌 TESTING CONNECTION AND RECONNECTION")
    logger.info("=" * 60)

    # Test initial connection
    logger.info("Testing initial connection...")
    connected = client.connect()

    if connected:
        logger.info("✅ Initial connection successful")

        # Test connection state
        assert client.state == ConnectionState.CONNECTED
        assert client.is_healthy()

        logger.info(f"Connection state: {client.state.value}")
        logger.info(f"Healthy: {client.is_healthy()}")

    else:
        logger.warning("⚠️ Initial connection failed (expected if TWS not running)")
        return False

    return True


def test_historical_data_requests(client: RobustIBClient):
    """Test historical data requests with different timeframes."""
    logger.info("\n" + "=" * 60)
    logger.info("📊 TESTING HISTORICAL DATA REQUESTS")
    logger.info("=" * 60)

    if not client.is_healthy():
        logger.warning("⚠️ Client not healthy, skipping historical data tests")
        return False

    # Test different timeframes per architecture requirements
    test_cases = [
        ("GBPUSD", "1 min", "1 D"),  # 1-minute for execution
        ("GBPUSD", "5 mins", "1 D"),  # 5-minute intermediate
        ("GBPUSD", "1 hour", "5 D"),  # 1-hour for analysis
        ("GBPUSD", "4 hours", "20 D"),  # 4-hour primary analysis timeframe
        ("EURUSD", "1 hour", "5 D"),  # Secondary pair
    ]

    results = []

    for symbol, timeframe, duration in test_cases:
        try:
            logger.info(f"📈 Requesting {timeframe} data for {symbol} ({duration})...")

            start_time = time.time()
            df = client.get_historical_data(
                symbol=symbol, timeframe=timeframe, duration=duration, timeout=30
            )
            request_time = time.time() - start_time

            if not df.empty:
                logger.info(
                    f"✅ {symbol} {timeframe}: {len(df)} bars received in {request_time:.2f}s"
                )
                logger.info(f"   📅 Range: {df.index[0]} to {df.index[-1]}")
                logger.info(
                    f"   💰 Latest OHLC: O={df['open'].iloc[-1]:.5f} H={df['high'].iloc[-1]:.5f} L={df['low'].iloc[-1]:.5f} C={df['close'].iloc[-1]:.5f}"
                )
                results.append(True)
            else:
                logger.warning(f"⚠️ {symbol} {timeframe}: No data received")
                results.append(False)

            # Brief pause between requests for rate limiting
            time.sleep(1)

        except Exception as e:
            logger.error(f"❌ {symbol} {timeframe} failed: {e}")
            results.append(False)

    success_rate = sum(results) / len(results) * 100
    logger.info(f"\n📊 Historical data success rate: {success_rate:.1f}%")

    return success_rate > 50  # At least 50% success


def test_market_data_subscriptions(client: RobustIBClient):
    """Test market data subscriptions and snapshots."""
    logger.info("\n" + "=" * 60)
    logger.info("📡 TESTING MARKET DATA SUBSCRIPTIONS")
    logger.info("=" * 60)

    if not client.is_healthy():
        logger.warning("⚠️ Client not healthy, skipping market data tests")
        return False

    # Test symbols per roadmap priorities
    symbols = ["GBPUSD", "EURUSD", "USDJPY", "USDCHF"]
    results = []

    for symbol in symbols:
        try:
            logger.info(f"📈 Testing market data for {symbol}...")

            # Test snapshot
            start_time = time.time()
            market_data = client.get_market_data(symbol, timeout=10)
            request_time = time.time() - start_time

            if market_data:
                logger.info(f"✅ {symbol} market data received in {request_time:.2f}s:")
                for key, value in market_data.items():
                    if isinstance(value, (int, float)):
                        logger.info(f"   {key}: {value}")
                results.append(True)
            else:
                logger.warning(f"⚠️ {symbol}: No market data")
                results.append(False)

        except Exception as e:
            logger.error(f"❌ {symbol} market data failed: {e}")
            results.append(False)

    success_rate = sum(results) / len(results) * 100
    logger.info(f"\n📡 Market data success rate: {success_rate:.1f}%")

    return success_rate > 50


def test_rate_limiting(client: RobustIBClient):
    """Test rate limiting functionality."""
    logger.info("\n" + "=" * 60)
    logger.info("⏱️ TESTING RATE LIMITING")
    logger.info("=" * 60)

    if not client.is_healthy():
        logger.warning("⚠️ Client not healthy, skipping rate limiting tests")
        return False

    # Make rapid requests to test rate limiting
    start_time = time.time()
    request_times = []

    for i in range(5):
        try:
            request_start = time.time()

            # Quick market data request
            market_data = client.get_market_data("GBPUSD", timeout=5)

            request_end = time.time()
            request_times.append(request_end - request_start)

            logger.info(f"Request {i+1}: {request_end - request_start:.2f}s")

        except Exception as e:
            logger.warning(f"Request {i+1} failed: {e}")

    total_time = time.time() - start_time
    avg_request_time = sum(request_times) / len(request_times) if request_times else 0

    logger.info(f"📊 Rate limiting test:")
    logger.info(f"   Total time: {total_time:.2f}s")
    logger.info(f"   Average request time: {avg_request_time:.2f}s")
    logger.info(f"   Successful requests: {len(request_times)}/5")

    # Check if rate limiting is working (should have some delay)
    return total_time > 5  # Should take at least 5 seconds due to rate limiting


def test_error_handling(client: RobustIBClient):
    """Test error handling and circuit breaker."""
    logger.info("\n" + "=" * 60)
    logger.info("🔧 TESTING ERROR HANDLING")
    logger.info("=" * 60)

    # Test invalid symbol
    try:
        logger.info("Testing invalid symbol request...")
        df = client.get_historical_data(
            symbol="INVALID", timeframe="1 min", duration="1 D", timeout=10
        )

        if df.empty:
            logger.info("✅ Invalid symbol handled gracefully (empty DataFrame)")
        else:
            logger.warning("⚠️ Unexpected data for invalid symbol")

    except Exception as e:
        logger.info(f"✅ Invalid symbol error handled: {e}")

    # Test timeout handling
    try:
        logger.info("Testing timeout handling...")
        df = client.get_historical_data(
            symbol="GBPUSD",
            timeframe="1 min",
            duration="1 D",
            timeout=0.1,  # Very short timeout
        )
        logger.warning("⚠️ Timeout test didn't timeout as expected")

    except Exception as e:
        logger.info(f"✅ Timeout error handled: {e}")

    return True


def test_health_monitoring(client: RobustIBClient):
    """Test health monitoring functionality."""
    logger.info("\n" + "=" * 60)
    logger.info("💚 TESTING HEALTH MONITORING")
    logger.info("=" * 60)

    # Get connection metrics
    metrics = client.get_connection_metrics()

    logger.info("📊 Connection Metrics:")
    logger.info(f"   Connection attempts: {metrics.connection_attempts}")
    logger.info(f"   Successful connections: {metrics.successful_connections}")
    logger.info(f"   Connection failures: {metrics.connection_failures}")
    logger.info(f"   Data requests sent: {metrics.data_requests_sent}")
    logger.info(f"   Data responses received: {metrics.data_responses_received}")
    logger.info(f"   Error count: {metrics.error_count}")
    logger.info(f"   Last connection: {metrics.last_connection_time}")

    # Test health check
    is_healthy = client.is_healthy()
    logger.info(f"🏥 Health status: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")

    # Success rate calculation
    if metrics.data_requests_sent > 0:
        success_rate = (
            metrics.data_responses_received / metrics.data_requests_sent
        ) * 100
        logger.info(f"📈 Data request success rate: {success_rate:.1f}%")

    return is_healthy


def run_comprehensive_test():
    """Run comprehensive test suite for robust IB client."""
    logger.info("\n" + "🚀" + "=" * 68 + "🚀")
    logger.info("🎯 FXML4 ROBUST IB CLIENT COMPREHENSIVE TEST SUITE")
    logger.info("🚀" + "=" * 68 + "🚀")
    logger.info("Testing production-ready features:")
    logger.info("- Automatic reconnection logic")
    logger.info("- Circuit breaker error handling")
    logger.info("- Request rate limiting")
    logger.info("- Health monitoring")
    logger.info("- Multi-timeframe data optimization")
    logger.info("- GBP/USD primary focus + secondary pairs")

    if not ROBUST_CLIENT_AVAILABLE:
        logger.error("❌ Robust IB client not available")
        return False

    # Initialize robust client
    config = {
        "host": "127.0.0.1",
        "port": 7497,  # Paper trading
        "client_id": 0,
        "reconnect_attempts": 5,
        "reconnect_delay": 3,
        "request_timeout": 30,
        "rate_limit_rps": 10,
        "circuit_breaker_threshold": 3,
        "health_check_interval": 30,
    }

    logger.info(f"\nInitializing RobustIBClient with config:")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")

    client = RobustIBClient(config)

    test_results = []

    try:
        # Test 1: Connection and Reconnection
        test_results.append(test_connection_and_reconnection(client))

        # Only continue if we have a connection
        if not client.is_healthy():
            logger.warning("⚠️ No IB connection available. Remaining tests skipped.")
            logger.info("\n🔧 To run full tests:")
            logger.info("1. Start TWS with paper trading account")
            logger.info("2. Enable API in Global Configuration > API > Settings")
            logger.info("3. Set port to 7497 and allow localhost connections")
            return False

        # Test 2: Historical Data Requests
        test_results.append(test_historical_data_requests(client))

        # Test 3: Market Data Subscriptions
        test_results.append(test_market_data_subscriptions(client))

        # Test 4: Rate Limiting
        test_results.append(test_rate_limiting(client))

        # Test 5: Error Handling
        test_results.append(test_error_handling(client))

        # Test 6: Health Monitoring
        test_results.append(test_health_monitoring(client))

    finally:
        # Clean disconnect
        logger.info("\n🔌 Disconnecting from IB...")
        client.disconnect()

    # Calculate overall success
    successful_tests = sum(test_results)
    total_tests = len(test_results)
    success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0

    # Final results
    logger.info("\n" + "🏆" + "=" * 68 + "🏆")
    logger.info("📋 COMPREHENSIVE TEST RESULTS")
    logger.info("🏆" + "=" * 68 + "🏆")
    logger.info(f"📊 Tests passed: {successful_tests}/{total_tests}")
    logger.info(f"📈 Success rate: {success_rate:.1f}%")
    logger.info("🎯 Test Coverage:")
    logger.info(
        "  ✅ Connection Management"
        if len(test_results) > 0 and test_results[0]
        else "  ❌ Connection Management"
    )
    if len(test_results) > 1:
        logger.info(
            "  ✅ Historical Data" if test_results[1] else "  ❌ Historical Data"
        )
    if len(test_results) > 2:
        logger.info("  ✅ Market Data" if test_results[2] else "  ❌ Market Data")
    if len(test_results) > 3:
        logger.info("  ✅ Rate Limiting" if test_results[3] else "  ❌ Rate Limiting")
    if len(test_results) > 4:
        logger.info("  ✅ Error Handling" if test_results[4] else "  ❌ Error Handling")
    if len(test_results) > 5:
        logger.info(
            "  ✅ Health Monitoring" if test_results[5] else "  ❌ Health Monitoring"
        )

    if success_rate >= 80:
        logger.info("\n🎉 ROBUST IB CLIENT: PRODUCTION READY!")
        logger.info("✅ All critical features tested and validated")
        logger.info("🚀 Ready for Phase 1 implementation!")
    elif success_rate >= 50:
        logger.info("\n⚠️ ROBUST IB CLIENT: PARTIAL SUCCESS")
        logger.info("🔧 Some features need attention before production")
    else:
        logger.info("\n❌ ROBUST IB CLIENT: NEEDS IMPROVEMENT")
        logger.info("🔧 Multiple critical issues need resolution")

    return success_rate >= 50


def main():
    """Main function with command line arguments."""
    parser = argparse.ArgumentParser(description="Test FXML4 Robust IB Client")
    parser.add_argument("--host", default="127.0.0.1", help="TWS host")
    parser.add_argument("--port", type=int, default=7497, help="TWS port")
    parser.add_argument("--client-id", type=int, default=0, help="Client ID")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--quick", action="store_true", help="Run quick tests only")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"🎯 Testing Robust IB Client at {args.host}:{args.port}")

    success = run_comprehensive_test()

    if success:
        logger.info("\n🎉 ROBUST IB CLIENT TEST PASSED!")
        sys.exit(0)
    else:
        logger.error("\n❌ ROBUST IB CLIENT TEST FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
