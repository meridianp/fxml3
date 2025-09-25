"""
Unit tests for Alpha Vantage Data Feed
=====================================

Test suite for AlphaVantageDataFeed with mocked API responses.
Follows TDD methodology with comprehensive coverage.
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from core.data_feeds.alpha_vantage_feed import AlphaVantageDataFeed
from core.data_feeds.base_feed import DataFeedStatus, MarketDataCandle, MarketDataTick


class TestAlphaVantageDataFeed:
    """Test suite for Alpha Vantage data feed implementation."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for Alpha Vantage feed."""
        return {
            "api_key": "test_api_key_12345",  # pragma: allowlist secret
            "rate_limit": 5,
            "polling_interval": 60,
            "health_check_interval": 30,
        }

    @pytest.fixture
    def alpha_vantage_feed(self, mock_config):
        """Create Alpha Vantage feed instance for testing."""
        return AlphaVantageDataFeed(mock_config)

    @pytest.fixture
    def mock_fx_intraday_response(self):
        """Mock successful FX_INTRADAY API response."""
        return {
            "Meta Data": {
                "1. Information": "FX Intraday (1min) Time Series",
                "2. From Symbol": "EUR",
                "3. To Symbol": "USD",
                "4. Last Refreshed": "2024-01-15 22:00:00",
                "5. Interval": "1min",
                "6. Output Size": "Compact",
                "7. Time Zone": "UTC",
            },
            "Time Series FX (1min)": {
                "2024-01-15 22:00:00": {
                    "1. open": "1.09450",
                    "2. high": "1.09470",
                    "3. low": "1.09440",
                    "4. close": "1.09460",
                },
                "2024-01-15 21:59:00": {
                    "1. open": "1.09430",
                    "2. high": "1.09455",
                    "3. low": "1.09425",
                    "4. close": "1.09450",
                },
            },
        }

    @pytest.fixture
    def mock_fx_daily_response(self):
        """Mock successful FX_DAILY API response."""
        return {
            "Meta Data": {
                "1. Information": "Forex Daily Prices (open, high, low, close)",
                "2. From Symbol": "EUR",
                "3. To Symbol": "USD",
                "4. Output Size": "Full size",
                "5. Last Refreshed": "2024-01-15",
                "6. Time Zone": "UTC",
            },
            "Time Series FX (Daily)": {
                "2024-01-15": {
                    "1. open": "1.09200",
                    "2. high": "1.09580",
                    "3. low": "1.09180",
                    "4. close": "1.09460",
                },
                "2024-01-14": {
                    "1. open": "1.09100",
                    "2. high": "1.09250",
                    "3. low": "1.09050",
                    "4. close": "1.09200",
                },
            },
        }

    @pytest.mark.asyncio
    async def test_initialization(self, mock_config):
        """RED: Test Alpha Vantage feed initialization."""
        feed = AlphaVantageDataFeed(mock_config)

        assert feed.api_key == "test_api_key_12345"
        assert feed.base_url == "https://www.alphavantage.co/query"
        assert feed.status == DataFeedStatus.DISCONNECTED
        assert feed.session is None
        assert "EURUSD" in feed.supported_forex_pairs
        assert len(feed.supported_forex_pairs) > 20

    @pytest.mark.asyncio
    async def test_initialization_without_api_key(self):
        """RED: Test initialization without API key should log error."""
        config = {"rate_limit": 5}

        with patch("core.data_feeds.alpha_vantage_feed.logger") as mock_logger:
            feed = AlphaVantageDataFeed(config)
            mock_logger.error.assert_called_with("❌ Alpha Vantage API key is required")
            assert feed.api_key is None

    @pytest.mark.asyncio
    async def test_connect_success(self, alpha_vantage_feed, mock_fx_intraday_response):
        """GREEN: Test successful connection establishment."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_fx_intraday_response
        mock_session.get.return_value.__aenter__.return_value = mock_response

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await alpha_vantage_feed.connect()

        assert result is True
        assert alpha_vantage_feed.session is not None

    @pytest.mark.asyncio
    async def test_connect_failure_no_api_key(self, mock_config):
        """RED: Test connection failure when API key is missing."""
        config = mock_config.copy()
        config.pop("api_key")
        feed = AlphaVantageDataFeed(config)

        result = await feed.connect()

        assert result is False
        assert feed.session is None

    @pytest.mark.asyncio
    async def test_connect_failure_api_error(self, alpha_vantage_feed):
        """RED: Test connection failure when API test fails."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"Error Message": "Invalid API call"}
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.close = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await alpha_vantage_feed.connect()

        assert result is False
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, alpha_vantage_feed):
        """GREEN: Test disconnect closes session properly."""
        mock_session = AsyncMock()
        alpha_vantage_feed.session = mock_session

        await alpha_vantage_feed.disconnect()

        mock_session.close.assert_called_once()
        assert alpha_vantage_feed.session is None

    @pytest.mark.asyncio
    async def test_get_real_time_quote_success(
        self, alpha_vantage_feed, mock_fx_intraday_response
    ):
        """GREEN: Test successful real-time quote retrieval."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_fx_intraday_response
        mock_session.get.return_value.__aenter__.return_value = mock_response

        alpha_vantage_feed.session = mock_session
        alpha_vantage_feed.rate_limiter.acquire = AsyncMock(return_value=True)

        result = await alpha_vantage_feed.get_real_time_quote("EURUSD")

        assert result is not None
        assert isinstance(result, MarketDataTick)
        assert result.symbol == "EURUSD"
        assert result.last == 1.09460
        assert result.source == "alpha_vantage"
        assert result.metadata["open"] == 1.09450

    @pytest.mark.asyncio
    async def test_get_real_time_quote_not_connected(self, alpha_vantage_feed):
        """RED: Test quote retrieval when not connected."""
        result = await alpha_vantage_feed.get_real_time_quote("EURUSD")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_real_time_quote_invalid_symbol(self, alpha_vantage_feed):
        """RED: Test quote retrieval with invalid symbol."""
        alpha_vantage_feed.session = AsyncMock()

        result = await alpha_vantage_feed.get_real_time_quote("INVALID")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_real_time_quote_api_error(self, alpha_vantage_feed):
        """RED: Test quote retrieval with API error response."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"Error Message": "Invalid API call"}
        mock_session.get.return_value.__aenter__.return_value = mock_response

        alpha_vantage_feed.session = mock_session
        alpha_vantage_feed.rate_limiter.acquire = AsyncMock(return_value=True)

        result = await alpha_vantage_feed.get_real_time_quote("EURUSD")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_real_time_quote_rate_limit(self, alpha_vantage_feed):
        """RED: Test quote retrieval with rate limit response."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "Note": "Thank you for using Alpha Vantage! Rate limit reached."
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response

        alpha_vantage_feed.session = mock_session
        alpha_vantage_feed.rate_limiter.acquire = AsyncMock(return_value=True)

        result = await alpha_vantage_feed.get_real_time_quote("EURUSD")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_historical_data_intraday_success(
        self, alpha_vantage_feed, mock_fx_intraday_response
    ):
        """GREEN: Test successful historical intraday data retrieval."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_fx_intraday_response
        mock_session.get.return_value.__aenter__.return_value = mock_response

        alpha_vantage_feed.session = mock_session
        alpha_vantage_feed.rate_limiter.wait_for_slot = AsyncMock()

        result = await alpha_vantage_feed.get_historical_data("EURUSD", "1m", limit=10)

        assert len(result) > 0
        assert isinstance(result[0], MarketDataCandle)
        assert result[0].symbol == "EURUSD"
        assert result[0].timeframe == "1m"
        assert result[0].source == "alpha_vantage"
        # Should be sorted newest first
        assert result[0].timestamp > result[-1].timestamp

    @pytest.mark.asyncio
    async def test_get_historical_data_daily_success(
        self, alpha_vantage_feed, mock_fx_daily_response
    ):
        """GREEN: Test successful historical daily data retrieval."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_fx_daily_response
        mock_session.get.return_value.__aenter__.return_value = mock_response

        alpha_vantage_feed.session = mock_session
        alpha_vantage_feed.rate_limiter.wait_for_slot = AsyncMock()

        result = await alpha_vantage_feed.get_historical_data("EURUSD", "1d", limit=10)

        assert len(result) > 0
        assert isinstance(result[0], MarketDataCandle)
        assert result[0].symbol == "EURUSD"
        assert result[0].timeframe == "1d"
        assert result[0].source == "alpha_vantage"

    @pytest.mark.asyncio
    async def test_get_historical_data_not_connected(self, alpha_vantage_feed):
        """RED: Test historical data retrieval when not connected."""
        result = await alpha_vantage_feed.get_historical_data("EURUSD", "1m")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_historical_data_invalid_symbol(self, alpha_vantage_feed):
        """RED: Test historical data retrieval with invalid symbol."""
        alpha_vantage_feed.session = AsyncMock()

        result = await alpha_vantage_feed.get_historical_data("INVALID", "1m")

        assert result == []

    @pytest.mark.asyncio
    async def test_subscribe_real_time_success(self, alpha_vantage_feed):
        """GREEN: Test successful real-time subscription setup."""
        callback = AsyncMock()
        symbols = ["EURUSD", "GBPUSD"]

        with patch("asyncio.create_task") as mock_create_task:
            result = await alpha_vantage_feed.subscribe_real_time(symbols, callback)

        assert result is True
        assert mock_create_task.call_count == 2  # One task per symbol

    @pytest.mark.asyncio
    async def test_unsubscribe_real_time_success(self, alpha_vantage_feed):
        """GREEN: Test successful real-time unsubscription."""
        symbols = ["EURUSD", "GBPUSD"]

        result = await alpha_vantage_feed.unsubscribe_real_time(symbols)

        assert result is True

    def test_validate_symbol_valid(self, alpha_vantage_feed):
        """GREEN: Test symbol validation with valid forex pairs."""
        assert alpha_vantage_feed.validate_symbol("EURUSD") is True
        assert alpha_vantage_feed.validate_symbol("GBPUSD") is True
        assert alpha_vantage_feed.validate_symbol("USDJPY") is True

    def test_validate_symbol_invalid(self, alpha_vantage_feed):
        """RED: Test symbol validation with invalid symbols."""
        assert alpha_vantage_feed.validate_symbol("INVALID") is False
        assert alpha_vantage_feed.validate_symbol("BTC") is False
        assert alpha_vantage_feed.validate_symbol("") is False

    def test_normalize_timeframe(self, alpha_vantage_feed):
        """GREEN: Test timeframe normalization."""
        assert alpha_vantage_feed.normalize_timeframe("1m") == "1min"
        assert alpha_vantage_feed.normalize_timeframe("5m") == "5min"
        assert alpha_vantage_feed.normalize_timeframe("1h") == "60min"
        assert alpha_vantage_feed.normalize_timeframe("1d") == "daily"

    def test_get_supported_symbols(self, alpha_vantage_feed):
        """GREEN: Test getting supported symbols."""
        symbols = alpha_vantage_feed.get_supported_symbols()

        assert isinstance(symbols, list)
        assert "EURUSD" in symbols
        assert "GBPUSD" in symbols
        assert len(symbols) > 20

    def test_get_supported_timeframes(self, alpha_vantage_feed):
        """GREEN: Test getting supported timeframes."""
        timeframes = alpha_vantage_feed.get_supported_timeframes()

        assert isinstance(timeframes, list)
        assert "1m" in timeframes
        assert "1h" in timeframes
        assert "1d" in timeframes

    @pytest.mark.asyncio
    async def test_health_check_success(
        self, alpha_vantage_feed, mock_fx_intraday_response
    ):
        """GREEN: Test successful health check."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_fx_intraday_response
        mock_session.get.return_value.__aenter__.return_value = mock_response

        alpha_vantage_feed.session = mock_session
        alpha_vantage_feed.rate_limiter.acquire = AsyncMock(return_value=True)

        result = await alpha_vantage_feed._perform_health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, alpha_vantage_feed):
        """RED: Test health check failure."""
        alpha_vantage_feed.session = AsyncMock()
        alpha_vantage_feed.get_real_time_quote = AsyncMock(return_value=None)

        result = await alpha_vantage_feed._perform_health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, alpha_vantage_feed):
        """REFACTOR: Test request statistics tracking."""
        # Track successful request
        await alpha_vantage_feed._track_request(True)

        # Track failed request
        await alpha_vantage_feed._track_request(False)

        stats = alpha_vantage_feed.get_statistics()

        assert stats["total_requests"] == 2
        assert stats["successful_requests"] == 1
        assert stats["failed_requests"] == 1
        assert stats["success_rate_percent"] == 50.0
        assert stats["last_request_time"] is not None

    @pytest.mark.asyncio
    async def test_polling_loop_with_callback(
        self, alpha_vantage_feed, mock_fx_intraday_response
    ):
        """REFACTOR: Test polling loop calls callback correctly."""
        callback = AsyncMock()
        alpha_vantage_feed._is_running = True

        # Mock get_real_time_quote to return a quote once, then stop
        call_count = 0

        async def mock_get_quote(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                alpha_vantage_feed._is_running = False  # Stop after first call
                return MarketDataTick(
                    timestamp=datetime.now(timezone.utc),
                    symbol="EURUSD",
                    last=1.0950,
                    source="alpha_vantage",
                )
            return None

        alpha_vantage_feed.get_real_time_quote = mock_get_quote

        # Set short polling interval for testing
        alpha_vantage_feed.config["polling_interval"] = 0.01

        await alpha_vantage_feed._polling_loop("EURUSD", callback)

        # Verify callback was called
        callback.assert_called_once()
        args = callback.call_args[0]
        assert isinstance(args[0], MarketDataTick)
        assert args[0].symbol == "EURUSD"


@pytest.mark.integration
class TestAlphaVantageDataFeedIntegration:
    """Integration tests for Alpha Vantage data feed (require API key)."""

    @pytest.fixture
    def real_config(self):
        """Real configuration for integration testing (requires API key)."""
        import os

        api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            pytest.skip(
                "ALPHA_VANTAGE_API_KEY environment variable required for integration tests"
            )

        return {"api_key": api_key, "rate_limit": 5, "polling_interval": 60}

    @pytest.mark.asyncio
    async def test_real_api_connection(self, real_config):
        """Integration test with real Alpha Vantage API."""
        feed = AlphaVantageDataFeed(real_config)

        try:
            # Test connection
            connected = await feed.connect()
            assert connected is True

            # Test real-time quote
            quote = await feed.get_real_time_quote("EURUSD")
            assert quote is not None
            assert quote.symbol == "EURUSD"
            assert quote.last is not None

            # Test historical data
            candles = await feed.get_historical_data("EURUSD", "1d", limit=5)
            assert len(candles) > 0
            assert candles[0].symbol == "EURUSD"

        finally:
            await feed.disconnect()
