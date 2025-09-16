#!/usr/bin/env python3
"""
Integration tests for real market data providers.

This test suite follows TDD principles to ensure real market data connections work correctly.
Tests are designed to fail first (Red), then pass with minimal implementation (Green),
then be refactored for production quality.

RED → GREEN → REFACTOR TDD CYCLE
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from fxml4.data_engineering.data_feeds.alpha_vantage_feed import AlphaVantageDataFeed
from fxml4.data_engineering.data_feeds.base_feed import DataFeedFactory
from fxml4.data_engineering.data_feeds.ib_data_feed import IBDataFeed


class TestRealMarketDataProviders:
    """
    TDD Test Suite for Real Market Data Provider Connections

    Following TDD methodology:
    1. RED: Write failing tests first
    2. GREEN: Make tests pass with minimal code
    3. REFACTOR: Improve implementation quality
    """

    # TEST CATEGORIES
    # 1. Connection and Authentication Tests
    # 2. Data Retrieval Tests
    # 3. Real-Time Streaming Tests
    # 4. Error Handling and Resilience Tests
    # 5. Performance and Rate Limiting Tests

    # ============================================================================
    # 1. CONNECTION AND AUTHENTICATION TESTS (TDD Phase: RED)
    # ============================================================================

    def test_polygon_real_connection_should_authenticate_with_api_key(self):
        """
        RED: Test should fail initially - Polygon feed doesn't exist yet
        GOAL: Connect to Polygon.io with real API key and authenticate
        """
        from fxml4.data_engineering.data_feeds.polygon_feed import PolygonDataFeed

        config = {
            "api_key": "6VNaiPLmpdAft7A36nsKQptPEdsFDs2p",  # Real key from .env
            "base_url": "https://api.polygon.io/v2",
            "timeout": 30,
        }

        # This should fail initially - PolygonDataFeed doesn't exist
        feed = PolygonDataFeed(config)

        # Test authentication by making a simple API call
        is_authenticated = feed.test_connection()
        assert is_authenticated, "Should authenticate with real Polygon API key"

        # Verify we can get available symbols
        symbols = feed.get_available_symbols()
        assert len(symbols) > 0, "Should return available forex symbols"
        assert (
            "C:EURUSD" in symbols or "EURUSD" in symbols
        ), "Should include major forex pairs"

    def test_alpha_vantage_real_connection_should_handle_demo_limitations(self):
        """
        GREEN: Test should pass - Alpha Vantage feed exists but needs enhancement
        GOAL: Connect with demo key and handle rate limiting gracefully
        """
        config = {
            "api_key": "demo",
            "calls_per_minute": 5,
            "retry_delay": 12,  # 12 seconds between calls for demo
        }

        feed = AlphaVantageDataFeed(config)

        # Test connection with demo limitations
        is_connected = feed.test_connection()
        assert is_connected, "Should connect with demo API key"

        # Should handle rate limiting gracefully
        start_time = time.time()
        symbols = feed.get_available_symbols()
        elapsed = time.time() - start_time

        # Demo key should implement respectful rate limiting
        assert elapsed >= 1, "Should implement rate limiting for demo key"
        assert len(symbols) > 0, "Should return some symbols even with demo key"

    def test_interactive_brokers_paper_trading_connection(self):
        """
        RED: Test should fail initially - needs IB connection management
        GOAL: Connect to IB paper trading account for real-time data
        """
        from fxml4.data_engineering.data_feeds.enhanced_ib_feed import (
            EnhancedIBDataFeed,
        )

        config = {
            "host": "127.0.0.1",
            "port": 8888,  # Paper trading port
            "client_id": 1,
            "timeout": 10,
            "paper_trading": True,
        }

        # This should fail initially - EnhancedIBDataFeed doesn't exist
        feed = EnhancedIBDataFeed(config)

        # Test connection to paper trading
        is_connected = feed.connect()
        assert is_connected, "Should connect to IB paper trading"

        # Verify we can get account info
        account_info = feed.get_account_info()
        assert account_info is not None, "Should retrieve paper trading account info"
        assert (
            account_info.get("account_type") == "paper"
        ), "Should be paper trading account"

    # ============================================================================
    # 2. DATA RETRIEVAL TESTS (TDD Phase: RED → GREEN)
    # ============================================================================

    def test_polygon_historical_forex_data_retrieval(self):
        """
        RED: Test will fail initially
        GOAL: Retrieve real historical forex data from Polygon
        """
        from fxml4.data_engineering.data_feeds.polygon_feed import PolygonDataFeed

        config = {"api_key": "6VNaiPLmpdAft7A36nsKQptPEdsFDs2p"}
        feed = PolygonDataFeed(config)

        # Test historical data retrieval
        data = feed.fetch_data(
            symbol="EURUSD",
            timeframe="1h",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )

        # Validate data structure
        assert isinstance(data, pd.DataFrame), "Should return pandas DataFrame"
        assert not data.empty, "Should return actual historical data"

        # Validate required columns
        required_columns = ["open", "high", "low", "close", "volume", "timestamp"]
        for col in required_columns:
            assert col in data.columns, f"Should include {col} column"

        # Validate data quality
        assert data["high"].ge(data["low"]).all(), "High should be >= Low"
        assert (
            data["high"].ge(data["open"]).all() or data["low"].le(data["open"]).all()
        ), "OHLC should be consistent"

        # Validate time series ordering
        assert (
            data.index.is_monotonic_increasing
        ), "Data should be chronologically ordered"

    def test_alpha_vantage_forex_data_with_rate_limiting(self):
        """
        GREEN: Should pass with existing implementation, enhance for robustness
        GOAL: Retrieve forex data while respecting API rate limits
        """
        config = {
            "api_key": "demo",
            "calls_per_minute": 5,
            "cache_duration": 300,  # 5 minutes cache
        }

        feed = AlphaVantageDataFeed(config)

        # Test data retrieval with caching
        start_time = time.time()

        # First call - should hit API
        data1 = feed.fetch_data(symbol="EURUSD", timeframe="1d", limit=100)
        first_call_time = time.time() - start_time

        # Second call - should use cache
        start_time = time.time()
        data2 = feed.fetch_data(symbol="EURUSD", timeframe="1d", limit=100)
        second_call_time = time.time() - start_time

        # Validate caching behavior
        assert (
            second_call_time < first_call_time
        ), "Second call should be faster (cached)"
        assert data1.equals(data2), "Cached data should match original"

        # Validate data structure
        assert not data1.empty, "Should return historical data"
        assert "close" in data1.columns, "Should include price data"

    def test_multiple_provider_data_consistency(self):
        """
        RED: Test will fail initially - requires data normalization
        GOAL: Ensure data from different providers is consistently formatted
        """
        from fxml4.data_engineering.data_feeds.data_normalizer import DataNormalizer

        # Get data from multiple providers
        alpha_vantage_config = {"api_key": "demo"}
        av_feed = AlphaVantageDataFeed(alpha_vantage_config)

        polygon_config = {"api_key": "6VNaiPLmpdAft7A36nsKQptPEdsFDs2p"}
        polygon_feed = PolygonDataFeed(polygon_config)

        # This should fail initially - DataNormalizer doesn't exist
        normalizer = DataNormalizer()

        # Retrieve same data from both providers
        av_data = av_feed.fetch_data("EURUSD", "1d", limit=10)
        polygon_data = polygon_feed.fetch_data("EURUSD", "1d", limit=10)

        # Normalize data format
        av_normalized = normalizer.normalize(av_data, provider="alpha_vantage")
        polygon_normalized = normalizer.normalize(polygon_data, provider="polygon")

        # Validate consistency
        assert av_normalized.columns.equals(
            polygon_normalized.columns
        ), "Columns should be consistent"
        assert (
            av_normalized.index.dtype == polygon_normalized.index.dtype
        ), "Index types should match"

        # Price data should be reasonably close (within 0.1% for same day)
        if len(av_normalized) > 0 and len(polygon_normalized) > 0:
            latest_av = av_normalized.iloc[-1]["close"]
            latest_polygon = polygon_normalized.iloc[-1]["close"]
            price_diff = abs(latest_av - latest_polygon) / latest_av
            assert (
                price_diff < 0.001
            ), "Price data should be consistent across providers"

    # ============================================================================
    # 3. REAL-TIME STREAMING TESTS (TDD Phase: RED)
    # ============================================================================

    @pytest.mark.asyncio
    async def test_real_time_forex_price_streaming(self):
        """
        RED: Test will fail initially - real-time streaming not implemented
        GOAL: Stream live forex prices from multiple providers
        """
        from fxml4.data_engineering.data_feeds.real_time_aggregator import (
            RealTimeDataAggregator,
        )

        # This should fail initially - RealTimeDataAggregator doesn't exist
        aggregator = RealTimeDataAggregator()

        # Configure multiple real-time sources
        sources = [
            {
                "provider": "polygon",
                "config": {"api_key": "6VNaiPLmpdAft7A36nsKQptPEdsFDs2p"},
            },
            {"provider": "alpha_vantage", "config": {"api_key": "demo"}},
        ]

        await aggregator.configure_sources(sources)

        # Start streaming major forex pairs
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        stream = aggregator.start_streaming(symbols)

        # Collect real-time data for 30 seconds
        prices_received = []
        start_time = time.time()

        async for price_update in stream:
            prices_received.append(price_update)
            if time.time() - start_time > 30:  # 30 seconds of data
                break

        # Validate real-time data
        assert len(prices_received) > 0, "Should receive real-time price updates"

        # Verify data structure
        for update in prices_received[:5]:  # Check first 5 updates
            assert "symbol" in update, "Should include symbol"
            assert "bid" in update or "close" in update, "Should include price"
            assert "timestamp" in update, "Should include timestamp"
            assert isinstance(
                update["timestamp"], datetime
            ), "Timestamp should be datetime object"

    @pytest.mark.asyncio
    async def test_websocket_price_streaming_resilience(self):
        """
        RED: Test will fail initially - WebSocket implementation needed
        GOAL: Test WebSocket connection resilience and reconnection
        """
        from fxml4.data_engineering.data_feeds.websocket_feed import WebSocketFeed

        # This should fail initially - WebSocketFeed doesn't exist
        config = {
            "providers": ["polygon", "alpha_vantage"],
            "reconnect_attempts": 3,
            "reconnect_delay": 5,
            "heartbeat_interval": 30,
        }

        ws_feed = WebSocketFeed(config)

        # Test connection resilience
        await ws_feed.connect()
        assert ws_feed.is_connected(), "Should establish WebSocket connection"

        # Simulate connection drop and test reconnection
        await ws_feed.simulate_disconnect()
        await asyncio.sleep(6)  # Wait for reconnection

        assert ws_feed.is_connected(), "Should automatically reconnect"
        assert ws_feed.reconnection_count > 0, "Should track reconnection attempts"

    # ============================================================================
    # 4. ERROR HANDLING AND RESILIENCE TESTS (TDD Phase: RED → GREEN)
    # ============================================================================

    def test_api_rate_limit_handling(self):
        """
        RED: Will fail initially - sophisticated rate limiting not implemented
        GOAL: Gracefully handle API rate limits with backoff strategies
        """
        from fxml4.data_engineering.data_feeds.rate_limiter import AdaptiveRateLimiter

        # This should fail initially - AdaptiveRateLimiter doesn't exist
        config = {
            "initial_delay": 1,
            "max_delay": 60,
            "backoff_factor": 2,
            "jitter": True,
        }

        rate_limiter = AdaptiveRateLimiter(config)

        # Simulate API rate limit responses
        with patch("requests.get") as mock_get:
            # First call succeeds
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"data": "success"}

            result1 = rate_limiter.make_request("https://api.test.com/data")
            assert result1["data"] == "success", "Should handle successful requests"

            # Second call hits rate limit
            mock_get.return_value.status_code = 429
            mock_get.return_value.headers = {"Retry-After": "60"}

            start_time = time.time()
            result2 = rate_limiter.make_request("https://api.test.com/data")
            elapsed = time.time() - start_time

            assert elapsed >= 1, "Should implement backoff delay"
            assert (
                rate_limiter.current_delay > config["initial_delay"]
            ), "Should increase delay after rate limit"

    def test_connection_failure_recovery(self):
        """
        GREEN: Should enhance existing error handling
        GOAL: Recover gracefully from network failures and API errors
        """
        from fxml4.data_engineering.data_feeds.resilient_feed import ResilientDataFeed

        # This should fail initially - ResilientDataFeed doesn't exist
        config = {
            "max_retries": 3,
            "retry_delays": [1, 2, 4],  # Exponential backoff
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout": 60,
        }

        feed = ResilientDataFeed(config)

        # Test retry mechanism
        with patch.object(feed, "_make_api_call") as mock_call:
            # First two calls fail, third succeeds
            mock_call.side_effect = [
                ConnectionError("Network error"),
                TimeoutError("Request timeout"),
                {"data": "success"},
            ]

            result = feed.fetch_data_with_retry("EURUSD", "1h")

            assert result["data"] == "success", "Should succeed after retries"
            assert mock_call.call_count == 3, "Should retry failed requests"

        # Test circuit breaker
        with patch.object(feed, "_make_api_call") as mock_call:
            mock_call.side_effect = ConnectionError("Persistent failure")

            # Trigger circuit breaker
            for _ in range(6):  # Exceed threshold
                try:
                    feed.fetch_data_with_retry("EURUSD", "1h")
                except:
                    pass

            assert feed.is_circuit_open(), "Should open circuit after repeated failures"

    # ============================================================================
    # 5. PERFORMANCE AND OPTIMIZATION TESTS (TDD Phase: GREEN → REFACTOR)
    # ============================================================================

    def test_concurrent_data_fetching_performance(self):
        """
        RED: Will fail initially - concurrent fetching not optimized
        GOAL: Efficiently fetch data from multiple providers concurrently
        """
        import asyncio

        from fxml4.data_engineering.data_feeds.concurrent_fetcher import (
            ConcurrentDataFetcher,
        )

        # This should fail initially - ConcurrentDataFetcher doesn't exist
        fetcher = ConcurrentDataFetcher()

        # Configure multiple data sources
        requests = [
            {"provider": "alpha_vantage", "symbol": "EURUSD", "timeframe": "1h"},
            {"provider": "polygon", "symbol": "GBPUSD", "timeframe": "1h"},
            {"provider": "alpha_vantage", "symbol": "USDJPY", "timeframe": "1h"},
            {"provider": "polygon", "symbol": "USDCHF", "timeframe": "1h"},
        ]

        # Test concurrent fetching performance
        start_time = time.time()
        results = asyncio.run(fetcher.fetch_concurrent(requests))
        concurrent_time = time.time() - start_time

        # Test sequential fetching for comparison
        start_time = time.time()
        sequential_results = fetcher.fetch_sequential(requests)
        sequential_time = time.time() - start_time

        # Validate performance improvement
        assert len(results) == len(requests), "Should return all requested data"
        assert (
            concurrent_time < sequential_time
        ), "Concurrent should be faster than sequential"
        assert concurrent_time < sequential_time * 0.7, "Should be at least 30% faster"

        # Validate data integrity
        for result in results:
            assert result is not None, "All requests should return data"
            assert isinstance(result, pd.DataFrame), "Should return DataFrame"

    def test_data_caching_and_compression_performance(self):
        """
        GREEN: Should enhance existing caching
        GOAL: Optimize data storage and retrieval with compression
        """
        from fxml4.data_engineering.data_feeds.optimized_cache import OptimizedDataCache

        # This should fail initially - OptimizedDataCache doesn't exist
        cache = OptimizedDataCache(
            {
                "compression": "lz4",  # Fast compression
                "cache_size_mb": 100,
                "ttl_seconds": 300,
            }
        )

        # Create test data
        large_data = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10000, freq="1min"),
                "open": 1.0 + (pd.Series(range(10000)) * 0.0001),
                "high": 1.0 + (pd.Series(range(10000)) * 0.0001) + 0.001,
                "low": 1.0 + (pd.Series(range(10000)) * 0.0001) - 0.001,
                "close": 1.0 + (pd.Series(range(10000)) * 0.0001) + 0.0005,
                "volume": 1000 + pd.Series(range(10000)),
            }
        )

        # Test caching performance
        cache_key = "EURUSD_1m_test"

        # Store data
        start_time = time.time()
        cache.set(cache_key, large_data)
        store_time = time.time() - start_time

        # Retrieve data
        start_time = time.time()
        cached_data = cache.get(cache_key)
        retrieve_time = time.time() - start_time

        # Validate performance
        assert store_time < 1.0, "Should cache large dataset quickly"
        assert retrieve_time < 0.1, "Should retrieve cached data very quickly"
        assert cached_data.equals(large_data), "Cached data should match original"

        # Validate compression effectiveness
        memory_usage_original = large_data.memory_usage(deep=True).sum()
        memory_usage_cached = cache.get_memory_usage(cache_key)
        compression_ratio = memory_usage_cached / memory_usage_original

        assert compression_ratio < 0.5, "Should achieve at least 50% compression"

    # ============================================================================
    # INTEGRATION TEST FIXTURES AND UTILITIES
    # ============================================================================

    @pytest.fixture
    def real_api_keys(self):
        """Fixture providing real API keys for integration tests."""
        return {
            "polygon": "6VNaiPLmpdAft7A36nsKQptPEdsFDs2p",
            "alpha_vantage": "demo",  # Demo key for testing
            "ib_paper": {"host": "127.0.0.1", "port": 8888, "client_id": 1},
        }

    @pytest.fixture
    def test_symbols(self):
        """Fixture providing test symbols for validation."""
        return {
            "major_pairs": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"],
            "minor_pairs": ["EURGBP", "EURJPY", "GBPJPY"],
            "exotic_pairs": ["USDTRY", "USDZAR"],
        }

    def assert_valid_ohlcv_data(self, data: pd.DataFrame, symbol: str):
        """Utility to validate OHLCV data structure and quality."""
        # Structure validation
        required_columns = ["open", "high", "low", "close", "volume"]
        for col in required_columns:
            assert col in data.columns, f"Missing required column: {col}"

        # Data quality validation
        assert not data.empty, f"No data returned for {symbol}"
        assert (
            data["high"].ge(data["low"]).all()
        ), f"Invalid OHLC data for {symbol}: High < Low"
        assert (
            data["high"].ge(data["open"]).all() or data["low"].le(data["open"]).all()
        ), f"Invalid OHLC data for {symbol}: Open outside High-Low range"
        assert (
            data["high"].ge(data["close"]).all() or data["low"].le(data["close"]).all()
        ), f"Invalid OHLC data for {symbol}: Close outside High-Low range"

        # Time series validation
        if hasattr(data.index, "is_monotonic_increasing"):
            assert (
                data.index.is_monotonic_increasing
            ), f"Data not chronologically ordered for {symbol}"


# Mark tests that require real API connections
pytestmark = pytest.mark.integration


if __name__ == "__main__":
    """
    Run TDD tests for real market data providers.

    Expected initial result: Most tests should FAIL (RED phase)
    This is correct TDD behavior - tests define requirements before implementation.
    """
    print("🔴 TDD RED PHASE: Running tests that should initially FAIL")
    print("This is expected TDD behavior - defining requirements before implementation")
    print("=" * 70)

    # Run with verbose output to see detailed failure information
    pytest.main([__file__, "-v", "--tb=short"])
