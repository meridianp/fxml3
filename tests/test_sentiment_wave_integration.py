"""Tests for the sentiment-enhanced Elliott Wave validator.

This module tests the integration between sentiment analysis and Elliott Wave pattern validation.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.wave_analysis.elliott_wave import (
    ElliottWaveAnalyzer,
    ElliottWavePattern,
    WaveType,
)
from fxml4.wave_analysis.sentiment_wave_validator import SentimentWaveValidator


class MockSentimentAnalyzer:
    """Mock sentiment analyzer for testing."""

    def analyze_sentiment(self, news_data):
        """Return a mock sentiment score."""
        return 0.7  # Bullish sentiment


class MockRagSystem:
    """Mock RAG system for testing."""

    def query(self, query_text):
        """Return a mock response."""
        return """
        After analyzing this pattern, I can confirm it appears to be a valid Elliott Wave structure.

        1. The pattern adheres to Elliott Wave rules with good proportions between waves.
        2. The current bullish sentiment aligns well with what we'd expect at this position.
        3. My confidence in this being a valid pattern is high.

        Confidence: 0.82
        """


@pytest.fixture
def wave_analyzer():
    """Create Elliott Wave analyzer for testing."""
    return ElliottWaveAnalyzer()


@pytest.fixture
def sentiment_analyzer():
    """Create mock sentiment analyzer for testing."""
    return MockSentimentAnalyzer()


@pytest.fixture
def rag_system():
    """Create mock RAG system for testing."""
    return MockRagSystem()


@pytest.fixture
def validator(wave_analyzer, sentiment_analyzer, rag_system):
    """Create sentiment wave validator for testing."""
    return SentimentWaveValidator(
        wave_analyzer=wave_analyzer,
        sentiment_analyzer=sentiment_analyzer,
        rag=rag_system,
    )


@pytest.fixture
def sample_data():
    """Create sample price data with impulse wave pattern."""
    dates = pd.date_range(start="2025-01-01", periods=100, freq="H")
    data = pd.DataFrame(
        {
            "open": np.zeros(100),
            "high": np.zeros(100),
            "low": np.zeros(100),
            "close": np.zeros(100),
            "volume": np.random.randint(100, 1000, 100),
        },
        index=dates,
    )

    # Create impulse wave pattern
    # Wave 1: Bullish move
    data.loc[dates[0:20], "close"] = np.linspace(100, 110, 20)
    # Wave 2: Correction (not exceeding start of wave 1)
    data.loc[dates[20:30], "close"] = np.linspace(110, 103, 10)
    # Wave 3: Strong bullish move (longest)
    data.loc[dates[30:60], "close"] = np.linspace(103, 125, 30)
    # Wave 4: Correction (not overlapping with wave 1)
    data.loc[dates[60:70], "close"] = np.linspace(125, 118, 10)
    # Wave 5: Final bullish move
    data.loc[dates[70:100], "close"] = np.linspace(118, 130, 30)

    # Set open, high, low based on close for simplicity
    data["open"] = data["close"] - 0.5
    data["high"] = data["close"] + 0.5
    data["low"] = data["close"] - 0.8

    # Add some technical indicators
    data["rsi"] = 60  # Slightly bullish RSI

    return data


@pytest.fixture
def sample_pattern():
    """Create sample Elliott Wave pattern for testing."""
    return ElliottWavePattern(
        wave_type=WaveType.IMPULSE, start_idx=0, end_idx=99, confidence=0.75
    )


@pytest.fixture
def news_data():
    """Create mock news data for testing."""
    return pd.DataFrame(
        {
            "date": pd.date_range(start="2025-01-01", periods=5),
            "headline": ["Positive news"] * 5,
            "content": ["Bullish market outlook"] * 5,
        }
    )


class TestSentimentWaveIntegration:
    """Test cases for sentiment-enhanced wave validation."""

    def test_sentiment_from_price(self, validator, sample_data):
        """Test sentiment extraction from price data."""
        sentiment = validator._get_sentiment_from_price(sample_data)

        # Verify sentiment is calculated and in range
        assert sentiment is not None
        assert -1.0 <= sentiment <= 1.0

    def test_rag_validation(self, validator, sample_pattern, sample_data):
        """Test RAG-based validation."""
        confidence = validator._get_rag_validation(
            pattern=sample_pattern, price_data=sample_data, sentiment_score=0.6
        )

        # Verify confidence is calculated and in range
        assert confidence is not None
        assert 0.0 <= confidence <= 1.0
        # Check that it extracted the confidence from the mock response
        assert abs(confidence - 0.82) < 0.01

    def test_pattern_validation(self, validator, sample_pattern, sample_data):
        """Test pattern validation with sentiment."""
        # Validate pattern
        is_valid, confidence, details = validator.validate_wave_pattern(
            pattern=sample_pattern, price_data=sample_data, pattern_position="END"
        )

        # Verify results
        assert is_valid is True
        assert 0.0 <= confidence <= 1.0
        assert "sentiment_score" in details
        assert "wave_confidence" in details
        assert "sentiment_confidence" in details
        assert "rag_confidence" in details

    def test_analyze_with_sentiment(
        self, validator, wave_analyzer, sample_data, sample_pattern
    ):
        """Test full sentiment-enhanced analysis."""
        # Patch the analyze method to return a predetermined wave count
        with patch.object(wave_analyzer, "analyze") as mock_analyze:
            # Create mock wave count
            mock_wave_count = MagicMock()
            mock_wave_count.waves = [sample_pattern]
            mock_analyze.return_value = mock_wave_count

            # Perform analysis
            results = validator.analyze_with_sentiment(sample_data)

            # Verify results
            assert "patterns" in results
            assert "validation" in results
            assert "combined_score" in results
            assert len(results["patterns"]) > 0
            assert len(results["validation"]) > 0
            assert 0.0 <= results["combined_score"] <= 1.0

            # Verify validation details
            validation = results["validation"][0]
            assert validation["is_valid"] is True
            assert "pattern" in validation
            assert "confidence" in validation
            assert "details" in validation

    def test_analyze_with_news_sentiment(
        self, validator, wave_analyzer, sample_data, sample_pattern, news_data
    ):
        """Test analysis with news sentiment data."""
        # Patch the analyze method
        with patch.object(wave_analyzer, "analyze") as mock_analyze:
            # Create mock wave count
            mock_wave_count = MagicMock()
            mock_wave_count.waves = [sample_pattern]
            mock_analyze.return_value = mock_wave_count

            # Perform analysis with news data
            results = validator.analyze_with_sentiment(
                price_data=sample_data, news_data=news_data
            )

            # Verify results incorporate sentiment
            assert "sentiment_score" in results
            # Should be the mock sentiment analyzer's score (0.7)
            assert results["sentiment_score"] == 0.7
