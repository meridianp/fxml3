#!/usr/bin/env python3
"""
Test for sentiment analysis integration.

This module tests the integration of sentiment analysis components from FXML3
into FXML4, ensuring that the core functionality works correctly.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# Import the sentiment analysis components
from fxml4.llm_integration.llm_client import LLMClient
from fxml4.llm_integration.sentiment_analysis import (
    MarketSentimentAnalyzer,
    SentimentAgent,
    SentimentAnalyzer,
    YahooFinanceNewsFetcher,
)


@pytest.fixture
def llm_client():
    """Create LLMClient for testing."""
    return LLMClient()


@pytest.fixture
def mock_news():
    """Create mock news data for testing."""
    return [
        {
            "title": "Test News Item",
            "summary": "This is a test news item",
            "publisher": "Test Publisher",
            "providerPublishTime": 1616176800,  # Example timestamp
            "link": "https://example.com/news",
            "thumbnail": {"resolutions": [{"url": "https://example.com/image.jpg"}]},
        }
    ]


@pytest.fixture
def analyzed_news(mock_news):
    """Create analyzed news data for testing."""
    return [
        {
            **mock_news[0],
            "sentiment_analysis": {
                "sentiment": "bullish",
                "intensity": 8,
                "relevance": 9,
                "temporal_impact": "short-term",
                "key_factors": ["test factor"],
                "confidence": 7,
            },
        }
    ]


class TestSentimentIntegration:
    """Test sentiment analysis integration."""

    def test_llm_client_initialization(self):
        """Test that LLMClient can be initialized."""
        # Test with default parameters
        client = LLMClient()
        assert client.provider == "openai"
        assert client.model is not None

        # Test with custom parameters
        client = LLMClient(provider="anthropic", model="claude-3-sonnet")
        assert client.provider == "anthropic"
        assert client.model == "claude-3-sonnet"

    @patch("fxml4.llm_integration.llm_client.LLMClient.generate_text")
    def test_sentiment_analyzer(self, mock_generate_text, llm_client):
        """Test that SentimentAnalyzer can analyze sentiment."""
        # Mock the LLM response
        mock_generate_text.return_value = '{"sentiment": "bullish", "intensity": 8, "relevance": 9, "temporal_impact": "short-term", "key_factors": ["strong economic data", "central bank policy"], "confidence": 7}'

        # Create a SentimentAnalyzer with a mock LLM client
        analyzer = SentimentAnalyzer(llm_client=llm_client)

        # Analyze sentiment
        result = analyzer.analyze_sentiment("Sample news text", "EUR/USD")

        # Check that the result is a dictionary with expected keys
        assert isinstance(result, dict)
        assert result["sentiment"] == "bullish"
        assert result["intensity"] == 8
        assert result["relevance"] == 9
        assert result["temporal_impact"] == "short-term"
        assert isinstance(result["key_factors"], list)
        assert result["confidence"] == 7

        # Verify that generate_text was called
        mock_generate_text.assert_called_once()

    @patch("yfinance.Ticker")
    def test_yahoo_fetcher(self, mock_ticker, mock_news):
        """Test that YahooFinanceNewsFetcher can fetch news."""
        # Set up the mock
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.news = mock_news
        mock_ticker.return_value = mock_ticker_instance

        # Create a news fetcher
        fetcher = YahooFinanceNewsFetcher()

        # Fetch news
        result = fetcher.fetch_news("EURUSD")

        # Check that the result is a list of dictionaries
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["title"] == "Test News Item"
        assert result[0]["publisher"] == "Test Publisher"

        # Verify that Ticker was called with the correct symbol
        mock_ticker.assert_called_once_with("EURUSD=X")

    @patch(
        "fxml4.llm_integration.sentiment_analysis.YahooFinanceNewsFetcher.fetch_news"
    )
    @patch(
        "fxml4.llm_integration.sentiment_analysis.SentimentAnalyzer.analyze_news_batch"
    )
    def test_market_sentiment_analyzer(
        self, mock_analyze_news_batch, mock_fetch_news, mock_news, analyzed_news
    ):
        """Test that MarketSentimentAnalyzer can analyze market sentiment."""
        # Mock news items and analyzed news
        formatted_mock_news = [
            {
                "title": "Test News Item",
                "summary": "This is a test news item",
                "publisher": "Test Publisher",
                "publish_date": "2023-04-01T12:00:00",
                "url": "https://example.com/news",
                "source": "Yahoo Finance",
            }
        ]

        # Set up the mocks
        mock_fetch_news.return_value = formatted_mock_news
        mock_analyze_news_batch.return_value = analyzed_news

        # Create a market sentiment analyzer
        analyzer = MarketSentimentAnalyzer()

        # Analyze market sentiment
        result = analyzer.analyze_market_sentiment("EURUSD")

        # Check that the result is a dictionary with expected keys
        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "data" in result
        assert "sentiment_summary" in result["data"]

        # Verify that fetch_news and analyze_news_batch were called
        mock_fetch_news.assert_called_once()
        mock_analyze_news_batch.assert_called_once()

    def test_sentiment_agent(self):
        """Test that SentimentAgent can be initialized."""
        # Test with default parameters
        agent = SentimentAgent()
        assert agent.analyzer is not None
