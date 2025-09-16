#!/usr/bin/env python
"""Unit tests for general technical analysis LLM."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.general_technical_analysis_llm import (
    GeneralTechnicalAnalysisLLM,
    TechnicalAnalysisSignal,
)


@pytest.fixture
def analyzer():
    """Create analyzer instance."""
    return GeneralTechnicalAnalysisLLM(llm_client=None)


@pytest.fixture
def sample_data():
    """Create sample OHLCV data with technical indicators."""
    bars = 200
    dates = pd.date_range(end=datetime.now(), periods=bars, freq="4h")

    # Generate trending data
    base_price = 1.1000
    trend = np.linspace(0, 0.05, bars)  # 5% uptrend
    noise = np.random.normal(0, 0.001, bars)

    close_prices = base_price + trend + noise

    data = pd.DataFrame(
        {
            "open": close_prices + np.random.uniform(-0.0002, 0.0002, bars),
            "high": close_prices + np.abs(np.random.uniform(0, 0.0005, bars)),
            "low": close_prices - np.abs(np.random.uniform(0, 0.0005, bars)),
            "close": close_prices,
            "volume": np.random.uniform(900000, 1100000, bars),
            "rsi_14": 50 + 20 * np.sin(np.linspace(0, 4 * np.pi, bars)),
            "atr_14": np.full(bars, 0.0015),
        },
        index=dates,
    )

    return data


class TestGeneralTechnicalAnalysisLLM:
    """Test cases for General Technical Analysis LLM."""

    def test_initialization(self):
        """Test analyzer initialization."""
        # Without LLM client
        analyzer1 = GeneralTechnicalAnalysisLLM()
        assert analyzer1.llm_client is None

        # With LLM client
        mock_client = Mock()
        analyzer2 = GeneralTechnicalAnalysisLLM(llm_client=mock_client)
        assert analyzer2.llm_client == mock_client

    def test_prepare_market_summary(self, analyzer, sample_data):
        """Test market summary preparation."""
        summary = analyzer._prepare_market_summary(sample_data)

        # Check all required fields
        required_fields = [
            "current_price",
            "high_20",
            "low_20",
            "high_50",
            "low_50",
            "sma_20",
            "sma_50",
            "sma_200",
            "rsi",
            "atr",
            "volume_ratio",
            "higher_highs",
            "lower_lows",
            "support_levels",
            "resistance_levels",
            "price_position",
        ]

        for field in required_fields:
            assert field in summary

        # Validate values
        assert summary["current_price"] > 0
        assert summary["high_20"] > summary["low_20"]
        assert summary["high_50"] > summary["low_50"]
        assert summary["price_position"] >= 0
        assert summary["price_position"] <= 1
        assert isinstance(summary["support_levels"], list)
        assert isinstance(summary["resistance_levels"], list)

    def test_count_higher_highs(self, analyzer, sample_data):
        """Test higher highs counting."""
        # Uptrending data
        uptrend_data = sample_data.copy()
        highs = analyzer._count_higher_highs(uptrend_data)
        assert highs >= 0
        assert highs <= 10

        # Perfect uptrend
        perfect_uptrend = sample_data.copy()
        perfect_uptrend["high"] = np.linspace(1.10, 1.15, len(perfect_uptrend))
        highs = analyzer._count_higher_highs(perfect_uptrend, lookback=10)
        assert highs == 9  # 9 higher highs in 10 bars

    def test_count_lower_lows(self, analyzer, sample_data):
        """Test lower lows counting."""
        # Normal data
        lows = analyzer._count_lower_lows(sample_data)
        assert lows >= 0
        assert lows <= 10

        # Perfect downtrend
        perfect_downtrend = sample_data.copy()
        perfect_downtrend["low"] = np.linspace(1.10, 1.05, len(perfect_downtrend))
        lows = analyzer._count_lower_lows(perfect_downtrend, lookback=10)
        assert lows == 9  # 9 lower lows in 10 bars

    def test_find_support_levels(self, analyzer, sample_data):
        """Test support level identification."""
        # Create data with clear support
        data = sample_data.copy()
        # Add some local minima
        data.loc[data.index[50], "low"] = 1.095
        data.loc[data.index[100], "low"] = 1.096
        data.loc[data.index[150], "low"] = 1.097

        supports = analyzer._find_support_levels(data)

        assert isinstance(supports, list)
        assert len(supports) > 0
        assert len(supports) <= 5
        # Should be sorted ascending
        assert supports == sorted(supports)

    def test_find_resistance_levels(self, analyzer, sample_data):
        """Test resistance level identification."""
        # Create data with clear resistance
        data = sample_data.copy()
        # Add some local maxima
        data.loc[data.index[50], "high"] = 1.115
        data.loc[data.index[100], "high"] = 1.116
        data.loc[data.index[150], "high"] = 1.117

        resistances = analyzer._find_resistance_levels(data)

        assert isinstance(resistances, list)
        assert len(resistances) > 0
        assert len(resistances) <= 5
        # Should be sorted descending
        assert resistances == sorted(resistances, reverse=True)

    @pytest.mark.parametrize(
        "price,ma,expected_chars",
        [
            (1.11, 1.10, ["+", "above"]),
            (1.09, 1.10, ["-", "below"]),
        ],
    )
    def test_compare_price(self, analyzer, price, ma, expected_chars):
        """Test price comparison formatting."""
        result = analyzer._compare_price(price, ma)
        for char in expected_chars:
            assert char in result

    def test_perform_rule_based_analysis(self, analyzer, sample_data):
        """Test fallback rule-based analysis."""
        summary = analyzer._prepare_market_summary(sample_data)

        # Bullish scenario
        summary["current_price"] = 1.12
        summary["sma_20"] = 1.11
        summary["sma_50"] = 1.10
        summary["higher_highs"] = 3
        summary["lower_lows"] = 0
        summary["rsi"] = 45
        summary["volume_ratio"] = 1.6

        signal = analyzer._perform_rule_based_analysis(sample_data, summary)

        assert signal is not None
        assert signal.bias == "LONG"
        assert signal.confidence > 0.5
        assert isinstance(signal.entry_zones, list)
        assert isinstance(signal.targets, list)
        assert signal.risk_reward > 0
        assert "Price above rising MAs" in signal.technical_confluences

    def test_perform_rule_based_analysis_bearish(self, analyzer, sample_data):
        """Test rule-based analysis for bearish scenario."""
        summary = analyzer._prepare_market_summary(sample_data)

        # Bearish scenario
        summary["current_price"] = 1.08
        summary["sma_20"] = 1.09
        summary["sma_50"] = 1.10
        summary["higher_highs"] = 0
        summary["lower_lows"] = 3
        summary["rsi"] = 65

        signal = analyzer._perform_rule_based_analysis(sample_data, summary)

        assert signal.bias == "SHORT"
        assert isinstance(signal.stop_loss, float)
        assert signal.stop_loss > summary["current_price"]

    def test_perform_rule_based_analysis_neutral(self, analyzer, sample_data):
        """Test rule-based analysis for neutral scenario."""
        summary = analyzer._prepare_market_summary(sample_data)

        # Create truly neutral scenario
        summary["current_price"] = 1.10
        summary["sma_20"] = 1.10  # Price at MA
        summary["sma_50"] = 1.10  # All MAs aligned
        summary["higher_highs"] = 1  # Mixed structure
        summary["lower_lows"] = 1
        summary["rsi"] = 50  # Neutral RSI
        summary["volume_ratio"] = 1.0  # Average volume

        signal = analyzer._perform_rule_based_analysis(sample_data, summary)

        assert signal.bias == "NEUTRAL"
        assert signal.confidence < 0.5

    @patch(
        "scripts.general_technical_analysis_llm.GeneralTechnicalAnalysisLLM._parse_llm_response"
    )
    def test_analyze_market_with_llm(self, mock_parse, sample_data):
        """Test market analysis with LLM client."""
        # Mock LLM client
        mock_llm = Mock()
        mock_llm.generate_text.return_value = '{"bias": "LONG", "confidence": 0.8}'

        # Mock parse response
        mock_signal = TechnicalAnalysisSignal(
            bias="LONG",
            confidence=0.8,
            entry_zones=[1.105, 1.103],
            stop_loss=1.100,
            targets=[1.110, 1.115],
            key_levels={"support": [1.100], "resistance": [1.115]},
            technical_confluences=["Test confluence"],
            market_structure="trending_up",
            risk_reward=2.0,
            time_horizon="swing",
        )
        mock_parse.return_value = mock_signal

        analyzer = GeneralTechnicalAnalysisLLM(llm_client=mock_llm)
        signal = analyzer.analyze_market(sample_data, "EURUSD", "4H")

        assert signal.bias == "LONG"
        assert signal.confidence == 0.8
        mock_llm.generate_text.assert_called_once()

    def test_parse_llm_response_valid(self, analyzer, sample_data):
        """Test parsing valid LLM response."""
        response = """
        Here's my analysis:
        {
            "bias": "SHORT",
            "confidence": 0.7,
            "entry_zones": [1.105, 1.104],
            "stop_loss": 1.108,
            "targets": [1.100, 1.095, 1.090],
            "key_levels": {
                "support": [1.095, 1.090],
                "resistance": [1.110, 1.115]
            },
            "technical_confluences": ["RSI overbought", "Resistance at 1.110"],
            "market_structure": "ranging",
            "risk_reward": 2.5,
            "time_horizon": "intraday"
        }
        """

        signal = analyzer._parse_llm_response(response, sample_data)

        assert signal.bias == "SHORT"
        assert signal.confidence == 0.7
        assert len(signal.entry_zones) == 2
        assert len(signal.targets) == 3
        assert signal.risk_reward == 2.5

    def test_parse_llm_response_invalid(self, analyzer, sample_data):
        """Test parsing invalid LLM response."""
        # Invalid JSON
        response = "This is not valid JSON"

        signal = analyzer._parse_llm_response(response, sample_data)

        # Should return neutral signal
        assert signal.bias == "NEUTRAL"
        assert signal.confidence == 0.0
        assert "Analysis error" in signal.technical_confluences[0]

    def test_create_neutral_signal(self, analyzer, sample_data):
        """Test neutral signal creation."""
        signal = analyzer._create_neutral_signal(sample_data)

        assert signal.bias == "NEUTRAL"
        assert signal.confidence == 0.0
        assert signal.risk_reward == 1.0
        assert signal.time_horizon == "swing"
        assert isinstance(signal.entry_zones, list)
        assert isinstance(signal.targets, list)

    def test_technical_analysis_signal_dataclass(self):
        """Test TechnicalAnalysisSignal dataclass."""
        signal = TechnicalAnalysisSignal(
            bias="LONG",
            confidence=0.85,
            entry_zones=[1.105, 1.103],
            stop_loss=1.100,
            targets=[1.110, 1.115, 1.120],
            key_levels={"support": [1.100, 1.095], "resistance": [1.110, 1.115]},
            technical_confluences=["MA support", "RSI oversold", "Volume spike"],
            market_structure="trending_up",
            risk_reward=2.5,
            time_horizon="swing",
        )

        assert signal.bias == "LONG"
        assert signal.confidence == 0.85
        assert len(signal.entry_zones) == 2
        assert signal.stop_loss == 1.100
        assert len(signal.targets) == 3
        assert len(signal.key_levels["support"]) == 2
        assert len(signal.technical_confluences) == 3
        assert signal.market_structure == "trending_up"
        assert signal.risk_reward == 2.5
        assert signal.time_horizon == "swing"

    def test_create_analysis_prompt(self, analyzer, sample_data):
        """Test prompt creation."""
        summary = analyzer._prepare_market_summary(sample_data)
        prompt = analyzer._create_analysis_prompt(summary, "EURUSD", "4H")

        # Check prompt contains key information
        assert "EURUSD" in prompt
        assert "4H" in prompt
        assert "Current Price:" in prompt
        assert "MOVING AVERAGES:" in prompt
        assert "MOMENTUM & VOLUME:" in prompt
        assert "MARKET STRUCTURE:" in prompt
        assert "KEY LEVELS:" in prompt
        assert "JSON format:" in prompt

    def test_get_system_prompt(self, analyzer):
        """Test system prompt generation."""
        prompt = analyzer._get_system_prompt()

        assert "professional technical analyst" in prompt
        assert "forex markets" in prompt
        assert "JSON format" in prompt
