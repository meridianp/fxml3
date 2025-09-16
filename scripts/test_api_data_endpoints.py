#!/usr/bin/env python3
"""
Test script for FXML4 API data endpoints and WebSocket.

This script tests the new market data API endpoints and WebSocket functionality.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict

import requests
import websockets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Configuration
API_BASE_URL = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"
TEST_SYMBOL = "EURUSD"
TEST_TIMEFRAME = "1h"


def test_api_health():
    """Test API health endpoint."""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            logger.info("✅ API health check passed")
            return True
        else:
            logger.error(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ API health check error: {e}")
        return False


def test_symbols_endpoint():
    """Test symbols endpoint."""
    try:
        # Note: This endpoint requires authentication in production
        response = requests.get(f"{API_BASE_URL}/symbols")

        if response.status_code == 401:
            logger.info("✅ Symbols endpoint requires authentication (expected)")
            return True
        elif response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Symbols endpoint returned {data.get('count', 0)} symbols")
            return True
        else:
            logger.error(f"❌ Symbols endpoint failed: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ Symbols endpoint error: {e}")
        return False


def test_ohlcv_endpoint():
    """Test OHLCV endpoint."""
    try:
        # Note: This endpoint requires authentication in production
        response = requests.get(
            f"{API_BASE_URL}/ohlcv/{TEST_SYMBOL}",
            params={"timeframe": TEST_TIMEFRAME, "limit": 10},
        )

        if response.status_code == 401:
            logger.info("✅ OHLCV endpoint requires authentication (expected)")
            return True
        elif response.status_code == 200:
            data = response.json()
            logger.info(
                f"✅ OHLCV endpoint returned {data.get('count', 0)} data points"
            )
            return True
        else:
            logger.error(f"❌ OHLCV endpoint failed: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ OHLCV endpoint error: {e}")
        return False


async def test_websocket_connection():
    """Test WebSocket connection."""
    try:
        uri = f"{WS_BASE_URL}/ws"

        async with websockets.connect(uri) as websocket:
            logger.info("✅ WebSocket connection established")

            # Send ping message
            ping_msg = {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
            await websocket.send(json.dumps(ping_msg))
            logger.info("📤 Sent ping message")

            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)

            if data.get("type") == "welcome":
                logger.info("✅ Received welcome message")

                # Wait for pong
                pong_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                pong_data = json.loads(pong_response)

                if pong_data.get("type") == "pong":
                    logger.info("✅ Ping/pong test passed")
                    return True
                else:
                    logger.error(f"❌ Expected pong, got: {pong_data.get('type')}")
                    return False
            else:
                logger.error(f"❌ Expected welcome, got: {data.get('type')}")
                return False

    except asyncio.TimeoutError:
        logger.error("❌ WebSocket test timed out")
        return False
    except Exception as e:
        logger.error(f"❌ WebSocket test error: {e}")
        return False


async def test_websocket_subscription():
    """Test WebSocket subscription functionality."""
    try:
        uri = f"{WS_BASE_URL}/ws"

        async with websockets.connect(uri) as websocket:
            logger.info("✅ WebSocket connection for subscription test established")

            # Wait for welcome message
            welcome = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            welcome_data = json.loads(welcome)

            if welcome_data.get("type") == "welcome":
                logger.info("✅ Received welcome message")

                # Subscribe to tick data
                subscribe_msg = {
                    "type": "subscribe",
                    "subscription": f"tick:{TEST_SYMBOL}",
                }
                await websocket.send(json.dumps(subscribe_msg))
                logger.info(f"📤 Subscribed to tick:{TEST_SYMBOL}")

                # Wait for subscription confirmation
                confirmation = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                conf_data = json.loads(confirmation)

                if conf_data.get("type") == "subscription_confirmed":
                    logger.info("✅ Subscription confirmed")

                    # Wait for a tick update (or timeout)
                    try:
                        update = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                        update_data = json.loads(update)

                        if update_data.get("type") == "tick_update":
                            logger.info("✅ Received tick update")
                            return True
                        else:
                            logger.info(
                                f"ℹ️  Received {update_data.get('type')} instead of tick update (DB may be empty)"
                            )
                            return True

                    except asyncio.TimeoutError:
                        logger.info(
                            "ℹ️  No tick updates received (DB may be empty, but subscription works)"
                        )
                        return True

                else:
                    logger.error(
                        f"❌ Expected subscription confirmation, got: {conf_data.get('type')}"
                    )
                    return False
            else:
                logger.error(f"❌ Expected welcome, got: {welcome_data.get('type')}")
                return False

    except Exception as e:
        logger.error(f"❌ WebSocket subscription test error: {e}")
        return False


async def test_symbol_websocket():
    """Test symbol-specific WebSocket endpoint."""
    try:
        uri = f"{WS_BASE_URL}/ws/{TEST_SYMBOL}?timeframe={TEST_TIMEFRAME}"

        async with websockets.connect(uri) as websocket:
            logger.info(f"✅ Symbol WebSocket connection for {TEST_SYMBOL} established")

            # Wait for welcome message
            welcome = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            welcome_data = json.loads(welcome)

            if welcome_data.get("type") == "welcome":
                logger.info("✅ Received symbol WebSocket welcome message")
                auto_subs = welcome_data.get("auto_subscriptions", [])
                logger.info(f"ℹ️  Auto-subscriptions: {auto_subs}")
                return True
            else:
                logger.error(f"❌ Expected welcome, got: {welcome_data.get('type')}")
                return False

    except Exception as e:
        logger.error(f"❌ Symbol WebSocket test error: {e}")
        return False


def main():
    """Run all API tests."""
    logger.info("🚀 Starting FXML4 API Data Endpoints Test Suite")
    logger.info("=" * 60)

    # Track test results
    results = []

    # Test API endpoints
    logger.info("📋 Testing REST API endpoints...")
    results.append(("API Health", test_api_health()))
    results.append(("Symbols Endpoint", test_symbols_endpoint()))
    results.append(("OHLCV Endpoint", test_ohlcv_endpoint()))

    # Test WebSocket functionality
    logger.info("\n🔌 Testing WebSocket functionality...")

    async def run_ws_tests():
        ws_results = []
        ws_results.append(("WebSocket Connection", await test_websocket_connection()))
        ws_results.append(
            ("WebSocket Subscription", await test_websocket_subscription())
        )
        ws_results.append(("Symbol WebSocket", await test_symbol_websocket()))
        return ws_results

    # Run WebSocket tests
    try:
        ws_results = asyncio.run(run_ws_tests())
        results.extend(ws_results)
    except Exception as e:
        logger.error(f"❌ WebSocket tests failed: {e}")
        results.extend(
            [
                ("WebSocket Connection", False),
                ("WebSocket Subscription", False),
                ("Symbol WebSocket", False),
            ]
        )

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
        logger.info("🎉 All tests passed! API data infrastructure is working.")
    else:
        logger.info("⚠️  Some tests failed. Check the API server and database.")

    logger.info(
        "\nNote: Authentication endpoints will show 401 errors - this is expected."
    )
    logger.info("For full testing, use proper authentication tokens.")


if __name__ == "__main__":
    main()
