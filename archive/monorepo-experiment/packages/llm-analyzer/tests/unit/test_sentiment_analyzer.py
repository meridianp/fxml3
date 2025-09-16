"""Tests for SentimentAnalyzer class."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from fxml4_llm.sentiment import SentimentAnalyzer
from fxml4_llm.client import LLMClient


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = Mock(spec=LLMClient)
    client.complete = AsyncMock()
    return client


@pytest.fixture
def sentiment_analyzer(mock_llm_client):
    """Create SentimentAnalyzer instance with mock LLM client."""
    return SentimentAnalyzer(mock_llm_client)


@pytest.fixture
def sample_news_items():
    """Sample news items for testing."""
    return [
        {
            "title": "EUR/USD rises on positive ECB comments",
            "content": "The Euro strengthened against the US Dollar following hawkish remarks from ECB officials.",
            "source": "Reuters",
            "timestamp": "2024-01-15T10:00:00Z"
        },
        {
            "title": "Dollar weakens amid inflation concerns",
            "content": "US Dollar faces pressure as inflation data comes in below expectations.",
            "source": "Bloomberg",
            "timestamp": "2024-01-15T11:00:00Z"
        },
        {
            "title": "Technical analysis: EUR/USD testing resistance",
            "content": "The currency pair approaches key resistance level at 1.0900.",
            "source": "FXStreet",
            "timestamp": "2024-01-15T12:00:00Z"
        }
    ]


@pytest.fixture
def sample_social_data():
    """Sample social media data for testing."""
    return [
        {
            "text": "Bullish on EUR/USD! Target 1.10 #forex #trading",
            "source": "twitter",
            "author": "fx_trader_123",
            "likes": 45,
            "timestamp": "2024-01-15T09:00:00Z"
        },
        {
            "text": "Euro looking weak, expecting further decline",
            "source": "reddit",
            "author": "bearish_trader",
            "upvotes": 23,
            "timestamp": "2024-01-15T09:30:00Z"
        }
    ]


class TestSentimentAnalyzer:
    """Test SentimentAnalyzer class."""
    
    def test_initialization(self, sentiment_analyzer, mock_llm_client):
        """Test SentimentAnalyzer initialization."""
        assert sentiment_analyzer.llm == mock_llm_client
        assert sentiment_analyzer.sentiment_cache == {}
    
    @pytest.mark.asyncio
    async def test_analyze_text_basic(self, sentiment_analyzer, mock_llm_client):
        """Test basic text sentiment analysis."""
        # Mock LLM response
        mock_response = """
        Sentiment Score: 0.7
        Confidence: High
        Key Factors: Positive ECB comments, Euro strength
        Market Impact: Bullish for EUR/USD
        """
        mock_llm_client.complete.return_value = mock_response
        
        # Mock the parsing method
        sentiment_analyzer._parse_sentiment_response = Mock(return_value={
            "sentiment_score": 0.7,
            "confidence": "high",
            "key_factors": ["Positive ECB comments", "Euro strength"],
            "market_impact": "bullish",
            "original_text": "Test text"
        })
        
        result = await sentiment_analyzer.analyze_text(
            text="EUR/USD rises on positive ECB comments",
            context="news",
            asset="EURUSD"
        )
        
        # Verify LLM was called
        mock_llm_client.complete.assert_called_once()
        call_args = mock_llm_client.complete.call_args
        
        # Check prompt construction
        prompt = call_args[0][0]
        assert "EUR/USD rises on positive ECB comments" in prompt
        
        # Verify result
        assert result["sentiment_score"] == 0.7
        assert result["confidence"] == "high"
        assert "Positive ECB comments" in result["key_factors"]
    
    @pytest.mark.asyncio
    async def test_analyze_text_with_cache(self, sentiment_analyzer, mock_llm_client):
        """Test that sentiment analysis uses cache."""
        # First call
        mock_llm_client.complete.return_value = "Sentiment: Positive"
        sentiment_analyzer._parse_sentiment_response = Mock(return_value={
            "sentiment_score": 0.5,
            "original_text": "Test text"
        })
        
        text = "This is a test news article about forex markets"
        result1 = await sentiment_analyzer.analyze_text(text)
        
        # Second call with same text
        result2 = await sentiment_analyzer.analyze_text(text)
        
        # LLM should only be called once due to caching
        assert mock_llm_client.complete.call_count == 1
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_analyze_news_batch_empty(self, sentiment_analyzer):
        """Test analyzing empty news batch."""
        result = await sentiment_analyzer.analyze_news_batch([])
        
        assert result["overall_sentiment"] == 0
        assert result["sentiment_distribution"] == {"positive": 0, "neutral": 0, "negative": 0}
        assert result["high_impact_items"] == []
        assert result["summary"] == "No news items to analyze"
    
    @pytest.mark.asyncio
    async def test_analyze_news_batch(self, sentiment_analyzer, mock_llm_client, sample_news_items):
        """Test analyzing batch of news items."""
        # Mock individual sentiment results
        sentiment_results = [
            {"sentiment_score": 0.8, "confidence": "high", "impact": "high"},
            {"sentiment_score": -0.3, "confidence": "medium", "impact": "medium"},
            {"sentiment_score": 0.1, "confidence": "low", "impact": "low"}
        ]
        
        # Setup analyze_text to return different results
        sentiment_analyzer.analyze_text = AsyncMock(side_effect=sentiment_results)
        
        # Mock aggregation
        sentiment_analyzer._aggregate_sentiment_results = Mock(return_value={
            "overall_sentiment": 0.2,
            "sentiment_distribution": {"positive": 1, "neutral": 1, "negative": 1},
            "high_impact_items": [sample_news_items[0]],
            "summary": "Mixed sentiment with positive bias"
        })
        
        result = await sentiment_analyzer.analyze_news_batch(sample_news_items, asset="EURUSD")
        
        # Verify all items were analyzed
        assert sentiment_analyzer.analyze_text.call_count == 3
        
        # Verify aggregation was called
        sentiment_analyzer._aggregate_sentiment_results.assert_called_once()
        
        # Check result
        assert result["overall_sentiment"] == 0.2
        assert result["sentiment_distribution"]["positive"] == 1
    
    @pytest.mark.asyncio
    async def test_analyze_market_mood(self, sentiment_analyzer, mock_llm_client, 
                                      sample_social_data, sample_news_items):
        """Test analyzing overall market mood."""
        # Mock the preparation method
        sentiment_analyzer._prepare_market_mood_text = Mock(
            return_value="Combined market data text"
        )
        
        # Mock LLM response
        mock_llm_client.complete.return_value = """
        1. Overall market sentiment score: 0.65
        2. Key themes: ECB policy, Dollar weakness, Technical resistance
        3. Sentiment trend: Improving
        4. Risk factors: Resistance at 1.09, Inflation uncertainty
        5. Contrarian indicators: High retail bullishness
        """
        
        result = await sentiment_analyzer.analyze_market_mood(
            social_data=sample_social_data,
            news_data=sample_news_items,
            asset="EURUSD"
        )
        
        # Verify preparation was called
        sentiment_analyzer._prepare_market_mood_text.assert_called_once_with(
            sample_social_data, sample_news_items
        )
        
        # Verify LLM was called with proper prompt
        mock_llm_client.complete.assert_called_once()
        call_args = mock_llm_client.complete.call_args
        prompt = call_args[0][0]
        
        assert "EURUSD" in prompt
        assert "Overall market sentiment score" in prompt
        assert "Key themes" in prompt
        assert "Risk factors" in prompt
    
    def test_build_sentiment_prompt(self, sentiment_analyzer):
        """Test sentiment prompt building."""
        # Access the private method for testing
        prompt = sentiment_analyzer._build_sentiment_prompt(
            text="EUR strengthens on ECB decision",
            context="news_headline",
            asset="EURUSD"
        )
        
        # Should include the text and structured analysis request
        assert "EUR strengthens on ECB decision" in prompt
        assert "sentiment" in prompt.lower()
        
        # With asset context
        prompt_with_asset = sentiment_analyzer._build_sentiment_prompt(
            text="Market analysis text",
            context="analysis",
            asset="GBPUSD"
        )
        assert "GBPUSD" in prompt_with_asset or "GBP/USD" in prompt_with_asset
    
    def test_parse_sentiment_response(self, sentiment_analyzer):
        """Test parsing sentiment response from LLM."""
        # Test various response formats
        response1 = """
        Sentiment Score: 0.75
        Confidence: High
        Analysis: Positive market outlook
        """
        
        sentiment_analyzer._parse_sentiment_response = Mock(return_value={
            "sentiment_score": 0.75,
            "confidence": "high",
            "analysis": "Positive market outlook"
        })
        
        result = sentiment_analyzer._parse_sentiment_response(response1, "original text")
        assert result["sentiment_score"] == 0.75
        assert result["confidence"] == "high"
    
    def test_aggregate_sentiment_results(self, sentiment_analyzer):
        """Test aggregating multiple sentiment results."""
        results = [
            {"sentiment_score": 0.8, "confidence": "high", "impact": "high"},
            {"sentiment_score": 0.2, "confidence": "medium", "impact": "low"},
            {"sentiment_score": -0.5, "confidence": "high", "impact": "medium"},
            {"sentiment_score": 0.0, "confidence": "low", "impact": "low"}
        ]
        
        news_items = [
            {"title": "News 1", "impact": "high"},
            {"title": "News 2", "impact": "low"},
            {"title": "News 3", "impact": "medium"},
            {"title": "News 4", "impact": "low"}
        ]
        
        # Mock the aggregation method
        sentiment_analyzer._aggregate_sentiment_results = Mock(return_value={
            "overall_sentiment": 0.125,  # Average
            "sentiment_distribution": {
                "positive": 2,
                "neutral": 1,
                "negative": 1
            },
            "high_impact_items": [news_items[0]],
            "confidence_weighted_sentiment": 0.2,
            "summary": "Mixed sentiment with slight positive bias"
        })
        
        result = sentiment_analyzer._aggregate_sentiment_results(results, news_items)
        
        assert result["overall_sentiment"] == 0.125
        assert result["sentiment_distribution"]["positive"] == 2
        assert len(result["high_impact_items"]) == 1
    
    def test_prepare_market_mood_text(self, sentiment_analyzer, 
                                     sample_social_data, sample_news_items):
        """Test preparing combined text for market mood analysis."""
        sentiment_analyzer._prepare_market_mood_text = Mock(
            return_value="News: EUR/USD rises... Social: Bullish sentiment..."
        )
        
        result = sentiment_analyzer._prepare_market_mood_text(
            sample_social_data, sample_news_items
        )
        
        assert "News:" in result
        assert "Social:" in result
    
    @pytest.mark.asyncio
    async def test_error_handling(self, sentiment_analyzer, mock_llm_client):
        """Test error handling in sentiment analysis."""
        # Make LLM raise an error
        mock_llm_client.complete.side_effect = Exception("LLM API Error")
        
        with pytest.raises(Exception, match="LLM API Error"):
            await sentiment_analyzer.analyze_text("Test text")
    
    @pytest.mark.asyncio
    async def test_concurrent_analysis(self, sentiment_analyzer, mock_llm_client):
        """Test concurrent sentiment analysis."""
        # Setup different responses for concurrent calls
        responses = [
            "Sentiment: Positive (0.7)",
            "Sentiment: Negative (-0.5)",
            "Sentiment: Neutral (0.0)"
        ]
        
        mock_llm_client.complete.side_effect = responses
        
        # Mock parsing to return different results
        parse_results = [
            {"sentiment_score": 0.7},
            {"sentiment_score": -0.5},
            {"sentiment_score": 0.0}
        ]
        sentiment_analyzer._parse_sentiment_response = Mock(side_effect=parse_results)
        
        # Create concurrent tasks
        texts = ["Text 1", "Text 2", "Text 3"]
        tasks = [sentiment_analyzer.analyze_text(text) for text in texts]
        
        # Execute concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify all were processed
        assert len(results) == 3
        assert results[0]["sentiment_score"] == 0.7
        assert results[1]["sentiment_score"] == -0.5
        assert results[2]["sentiment_score"] == 0.0
    
    @pytest.mark.asyncio
    async def test_analyze_with_different_contexts(self, sentiment_analyzer, mock_llm_client):
        """Test sentiment analysis with different contexts."""
        contexts = ["news", "social_media", "technical_analysis", "fundamental_analysis"]
        
        mock_llm_client.complete.return_value = "Sentiment: Positive"
        sentiment_analyzer._parse_sentiment_response = Mock(
            return_value={"sentiment_score": 0.5}
        )
        
        for context in contexts:
            result = await sentiment_analyzer.analyze_text(
                text="Market analysis text",
                context=context,
                asset="EURUSD"
            )
            
            # Verify context affects the prompt
            call_args = mock_llm_client.complete.call_args
            prompt = call_args[0][0]
            
            # Context should influence how the prompt is structured
            assert "Market analysis text" in prompt