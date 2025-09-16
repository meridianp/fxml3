#!/usr/bin/env python
"""Unit tests for Alpha Vantage News Sentiment API."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from fxml4.data_engineering.data_feeds.alpha_vantage_news import (
    AlphaVantageNewsAPI,
    RateLimiter,
    analyze_market_sentiment,
    get_forex_news_sentiment,
)


class TestAlphaVantageNewsAPI:
    """Test cases for AlphaVantageNewsAPI class."""

    @pytest.fixture
    def mock_response(self):
        """Create mock API response."""
        return {
            "items": "50",
            "sentiment_score_definition": "x <= -0.35: Bearish; -0.35 < x <= -0.15: Somewhat-Bearish; -0.15 < x < 0.15: Neutral; 0.15 <= x < 0.35: Somewhat-Bullish; x >= 0.35: Bullish",
            "relevance_score_definition": "0 < x <= 1, with a higher score indicating higher relevance.",
            "feed": [
                {
                    "title": "Fed Signals Potential Rate Cut in 2024",
                    "url": "https://example.com/article1",
                    "time_published": "20240115T103000",
                    "authors": ["John Doe"],
                    "summary": "Federal Reserve officials hinted at potential rate cuts...",
                    "banner_image": None,
                    "source": "Financial Times",
                    "category_within_source": "Markets",
                    "source_domain": "ft.com",
                    "topics": [
                        {"topic": "Economy - Monetary", "relevance_score": "0.95"},
                        {"topic": "Financial Markets", "relevance_score": "0.85"},
                    ],
                    "overall_sentiment_score": 0.2543,
                    "overall_sentiment_label": "Somewhat-Bullish",
                    "ticker_sentiment": [
                        {
                            "ticker": "FOREX:USD",
                            "relevance_score": "0.8",
                            "ticker_sentiment_score": "-0.15",
                            "ticker_sentiment_label": "Neutral",
                        },
                        {
                            "ticker": "FOREX:EUR",
                            "relevance_score": "0.6",
                            "ticker_sentiment_score": "0.25",
                            "ticker_sentiment_label": "Somewhat-Bullish",
                        },
                    ],
                },
                {
                    "title": "ECB Maintains Hawkish Stance on Inflation",
                    "url": "https://example.com/article2",
                    "time_published": "20240115T093000",
                    "authors": ["Jane Smith"],
                    "summary": "European Central Bank remains committed to fighting inflation...",
                    "source": "Reuters",
                    "overall_sentiment_score": -0.1234,
                    "overall_sentiment_label": "Neutral",
                    "ticker_sentiment": [
                        {
                            "ticker": "FOREX:EUR",
                            "relevance_score": "0.9",
                            "ticker_sentiment_score": "-0.3",
                            "ticker_sentiment_label": "Somewhat-Bearish",
                        }
                    ],
                },
            ],
        }

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        with patch.dict("os.environ", {}, clear=True):
            api = AlphaVantageNewsAPI()
            assert api.api_key is None

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        api = AlphaVantageNewsAPI(api_key="test_key")
        assert api.api_key == "test_key"
        assert api.cache_duration == 3600

    def test_parse_forex_symbol_valid(self):
        """Test parsing valid forex symbols."""
        api = AlphaVantageNewsAPI()

        # Valid symbols
        assert api._parse_forex_symbol("EURUSD") == ["EUR", "USD"]
        assert api._parse_forex_symbol("GBPUSD") == ["GBP", "USD"]
        assert api._parse_forex_symbol("USDJPY") == ["USD", "JPY"]

    def test_parse_forex_symbol_invalid(self):
        """Test parsing invalid forex symbols."""
        api = AlphaVantageNewsAPI()

        # Invalid symbols
        assert api._parse_forex_symbol("EUR") == []
        assert api._parse_forex_symbol("EURUSDX") == []
        assert api._parse_forex_symbol("XXXYYY") == []

    def test_build_request_params(self):
        """Test building API request parameters."""
        api = AlphaVantageNewsAPI(api_key="test_key")

        time_from = datetime(2024, 1, 15, 10, 0)
        time_to = datetime(2024, 1, 15, 12, 0)

        params = api._build_request_params(
            currencies=["EUR", "USD"], time_from=time_from, time_to=time_to, limit=50
        )

        assert params["function"] == "NEWS_SENTIMENT"
        assert params["tickers"] == "FOREX:EUR,FOREX:USD"
        assert params["apikey"] == "test_key"
        assert params["limit"] == 50
        assert params["time_from"] == "20240115T1000"
        assert params["time_to"] == "20240115T1200"
        assert "topics" in params

    @patch("requests.get")
    def test_get_forex_sentiment_success(self, mock_get, mock_response):
        """Test successful forex sentiment retrieval."""
        # Setup mock
        mock_resp = Mock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        api = AlphaVantageNewsAPI(api_key="test_key")
        result = api.get_forex_sentiment("EURUSD", limit=50)

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        assert "function=NEWS_SENTIMENT" in call_args
        assert "tickers=FOREX:EUR,FOREX:USD" in call_args

        # Verify result
        assert result["symbol"] == "EURUSD"
        assert result["article_count"] == 3  # Total ticker sentiments
        assert result["overall_sentiment"] != 0  # Should have calculated sentiment
        assert len(result["articles"]) > 0

    @patch("requests.get")
    def test_get_forex_sentiment_api_error(self, mock_get):
        """Test handling API error response."""
        # Setup mock with error
        mock_resp = Mock()
        mock_resp.json.return_value = {"Error Message": "Invalid API key"}
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        api = AlphaVantageNewsAPI(api_key="invalid_key")
        result = api.get_forex_sentiment("EURUSD")

        # Should return empty response
        assert result["overall_sentiment"] == 0.0
        assert result["article_count"] == 0

    @patch("requests.get")
    def test_get_forex_sentiment_network_error(self, mock_get):
        """Test handling network errors."""
        # Setup mock to raise exception
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        api = AlphaVantageNewsAPI(api_key="test_key")
        result = api.get_forex_sentiment("EURUSD")

        # Should return empty response
        assert result["overall_sentiment"] == 0.0
        assert result["article_count"] == 0

    def test_process_news_data(self, mock_response):
        """Test processing raw news data."""
        api = AlphaVantageNewsAPI()
        result = api._process_news_data(mock_response, "EURUSD")

        assert result["symbol"] == "EURUSD"
        assert result["article_count"] == 3  # Total ticker sentiments
        assert "overall_sentiment" in result
        assert "articles" in result
        assert len(result["articles"]) > 0

        # Check article details
        first_article = result["articles"][0]
        assert "title" in first_article
        assert "sentiment_score" in first_article
        assert "relevance_score" in first_article

    def test_get_sentiment_label(self):
        """Test sentiment label conversion."""
        api = AlphaVantageNewsAPI()

        assert api._get_sentiment_label(0.5) == "Bullish"
        assert api._get_sentiment_label(0.2) == "Bullish"
        assert api._get_sentiment_label(0.1) == "Neutral"
        assert api._get_sentiment_label(0.0) == "Neutral"
        assert api._get_sentiment_label(-0.1) == "Neutral"
        assert api._get_sentiment_label(-0.2) == "Bearish"
        assert api._get_sentiment_label(-0.5) == "Bearish"

    @patch("requests.get")
    def test_caching(self, mock_get, mock_response):
        """Test caching functionality."""
        # Setup mock
        mock_resp = Mock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        api = AlphaVantageNewsAPI(api_key="test_key", cache_duration=3600)

        # First call - should hit API
        result1 = api.get_forex_sentiment("EURUSD", use_cache=True)
        assert mock_get.call_count == 1

        # Second call - should use cache
        result2 = api.get_forex_sentiment("EURUSD", use_cache=True)
        assert mock_get.call_count == 1  # No additional call

        # Results should be the same
        assert result1["overall_sentiment"] == result2["overall_sentiment"]

    @patch("requests.get")
    def test_get_market_sentiment(self, mock_get, mock_response):
        """Test getting sentiment for multiple symbols."""
        # Setup mock
        mock_resp = Mock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        api = AlphaVantageNewsAPI(api_key="test_key")
        symbols = ["EURUSD", "GBPUSD"]

        results = api.get_market_sentiment(symbols, time_window_hours=24)

        assert len(results) == 2
        assert "EURUSD" in results
        assert "GBPUSD" in results
        assert mock_get.call_count == 2  # One call per symbol


class TestRateLimiter:
    """Test cases for RateLimiter class."""

    def test_rate_limiter_init(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(calls_per_minute=60)
        assert limiter.calls_per_minute == 60
        assert limiter.min_interval == 1.0  # 60 calls/min = 1 call/sec

    @patch("time.sleep")
    @patch("time.time")
    def test_rate_limiter_wait(self, mock_time, mock_sleep):
        """Test rate limiter waiting."""
        # Setup time sequence
        mock_time.side_effect = [
            0,
            0.5,
            0.5,
            1.5,
        ]  # last_call, current, current, new_time

        limiter = RateLimiter(calls_per_minute=60)  # 1 call per second

        # First call - no wait
        limiter.wait_if_needed()
        mock_sleep.assert_not_called()

        # Second call after 0.5s - should wait 0.5s
        limiter.wait_if_needed()
        mock_sleep.assert_called_with(0.5)


class TestConvenienceFunctions:
    """Test convenience functions."""

    @patch(
        "fxml4.data_engineering.data_feeds.alpha_vantage_news.AlphaVantageNewsAPI.get_forex_sentiment"
    )
    def test_get_forex_news_sentiment(self, mock_get_sentiment):
        """Test get_forex_news_sentiment function."""
        mock_get_sentiment.return_value = {
            "overall_sentiment": 0.25,
            "article_count": 10,
        }

        result = get_forex_news_sentiment("EURUSD", hours_back=12)

        mock_get_sentiment.assert_called_once()
        call_args = mock_get_sentiment.call_args
        assert call_args[1]["symbol"] == "EURUSD"
        assert call_args[1]["limit"] == 100
        assert result["overall_sentiment"] == 0.25

    @patch(
        "fxml4.data_engineering.data_feeds.alpha_vantage_news.AlphaVantageNewsAPI.get_market_sentiment"
    )
    def test_analyze_market_sentiment(self, mock_get_market):
        """Test analyze_market_sentiment function."""
        mock_get_market.return_value = {
            "EURUSD": {
                "overall_sentiment": 0.25,
                "relevance_score": 0.8,
                "article_count": 10,
                "sentiment_label": "Bullish",
            },
            "GBPUSD": {
                "overall_sentiment": -0.15,
                "relevance_score": 0.7,
                "article_count": 5,
                "sentiment_label": "Neutral",
            },
        }

        df = analyze_market_sentiment(["EURUSD", "GBPUSD"])

        assert len(df) == 2
        assert "symbol" in df.columns
        assert "sentiment" in df.columns
        assert df.loc[df["symbol"] == "EURUSD", "sentiment"].values[0] == 0.25
        assert df.loc[df["symbol"] == "GBPUSD", "label"].values[0] == "Neutral"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
