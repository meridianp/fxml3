"""Tests for MarketAnalyzer class."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import json

from fxml4_llm.market_analyzer import MarketAnalyzer
from fxml4_llm.client import LLMClient


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = Mock(spec=LLMClient)
    client.complete = AsyncMock()
    client.analyze_market = AsyncMock()
    return client


@pytest.fixture
def market_analyzer(mock_llm_client):
    """Create MarketAnalyzer instance with mock LLM client."""
    return MarketAnalyzer(mock_llm_client)


@pytest.fixture
def sample_price_data():
    """Create sample price data DataFrame."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='h')
    np.random.seed(42)
    
    base_price = 1.0850
    prices = []
    
    for i in range(100):
        change = np.random.randn() * 0.0005
        base_price += change
        
        high = base_price + abs(np.random.randn() * 0.0002)
        low = base_price - abs(np.random.randn() * 0.0002)
        open_price = base_price + np.random.randn() * 0.0001
        
        prices.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': base_price,
            'volume': np.random.randint(1000, 10000)
        })
    
    df = pd.DataFrame(prices, index=dates)
    
    # Add technical indicators
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['sma_200'] = df['close'].rolling(window=200).mean().fillna(base_price)
    df['rsi_14'] = 50 + np.random.randn(100) * 10  # Simplified RSI
    df['macd'] = np.random.randn(100) * 0.0001
    df['atr_14'] = df['high'].subtract(df['low']).rolling(window=14).mean()
    df['adx'] = 25 + np.random.randn(100) * 5
    
    return df


@pytest.fixture
def sample_news_data():
    """Create sample news data."""
    return [
        {
            "title": "ECB Maintains Hawkish Stance on Inflation",
            "content": "European Central Bank officials reiterated their commitment to fighting inflation.",
            "sentiment": "hawkish",
            "impact": "high",
            "timestamp": "2024-01-15T10:00:00Z"
        },
        {
            "title": "US Dollar Weakens on Soft Economic Data",
            "content": "Dollar index falls as latest economic indicators disappoint.",
            "sentiment": "bearish_usd",
            "impact": "medium",
            "timestamp": "2024-01-15T11:00:00Z"
        },
        {
            "title": "Technical Analysis: EUR/USD Tests Key Resistance",
            "content": "The pair approaches significant resistance at 1.0900.",
            "sentiment": "neutral",
            "impact": "low",
            "timestamp": "2024-01-15T12:00:00Z"
        }
    ]


@pytest.fixture
def sample_wave_data():
    """Create sample Elliott Wave data."""
    return {
        "wave_type": "Impulse",
        "current_wave": "Wave 3",
        "degree": "Minor",
        "completion": 75.5,
        "target": 1.0950,
        "invalidation": 1.0750
    }


@pytest.fixture
def sample_trade_setup():
    """Create sample trade setup."""
    return {
        "symbol": "EURUSD",
        "direction": "LONG",
        "entry_price": 1.0850,
        "stop_loss": 1.0820,
        "take_profit": 1.0920,
        "risk_reward_ratio": 2.33,
        "technical_factors": {
            "support_bounce": True,
            "trend_alignment": "Bullish",
            "rsi_oversold": False,
            "pattern": "Bull flag"
        },
        "market_context": "Uptrend on daily, pullback to support on 4H"
    }


class TestMarketAnalyzer:
    """Test MarketAnalyzer class."""
    
    def test_initialization(self, market_analyzer, mock_llm_client):
        """Test MarketAnalyzer initialization."""
        assert market_analyzer.llm == mock_llm_client
        assert market_analyzer.analysis_cache == {}
    
    @pytest.mark.asyncio
    async def test_analyze_market_standard(self, market_analyzer, mock_llm_client, 
                                          sample_price_data, sample_news_data):
        """Test standard market analysis."""
        # Mock LLM response
        mock_llm_client.analyze_market.return_value = {
            "analysis": "Market shows bullish momentum",
            "timestamp": sample_price_data.index[-1],
            "symbol": "EURUSD",
            "type": "comprehensive"
        }
        
        result = await market_analyzer.analyze_market(
            symbol="EURUSD",
            timeframe="1h",
            technical_data=sample_price_data,
            news_data=sample_news_data,
            analysis_depth="standard"
        )
        
        # Verify result
        assert result["type"] == "standard"
        assert "timestamp" in result
        assert result["analysis"] == "Market shows bullish momentum"
        
        # Verify caching
        cache_key = f"EURUSD_1h_{datetime.now().strftime('%Y%m%d_%H')}"
        assert cache_key in market_analyzer.analysis_cache
    
    @pytest.mark.asyncio
    async def test_analyze_market_detailed(self, market_analyzer, mock_llm_client,
                                         sample_price_data):
        """Test detailed market analysis."""
        # Mock multiple LLM responses
        mock_llm_client.analyze_market.side_effect = [
            {"analysis": "Technical analysis result", "type": "comprehensive"},
            {"analysis": "Risk assessment result", "type": "risk_assessment"}
        ]
        
        result = await market_analyzer.analyze_market(
            symbol="GBPUSD",
            timeframe="4h",
            technical_data=sample_price_data,
            analysis_depth="detailed"
        )
        
        # Verify multiple analyses were performed
        assert result["type"] == "detailed"
        assert "technical_analysis" in result
        assert "risk_assessment" in result
        assert mock_llm_client.analyze_market.call_count == 2
    
    @pytest.mark.asyncio
    async def test_analyze_elliott_wave(self, market_analyzer, mock_llm_client,
                                       sample_price_data, sample_wave_data):
        """Test Elliott Wave analysis."""
        # Mock LLM response
        mock_response = """
        Wave Count Validation:
        - The current wave count appears correct as Wave 3 of Minor degree
        - No immediate corrections needed
        
        Expected Price Targets:
        - Wave 3 target: 1.0950-1.0980
        - Wave 4 pullback: 1.0880-1.0900
        - Wave 5 target: 1.1020-1.1050
        
        Key Fibonacci Levels:
        - 161.8% extension: 1.0965
        - 261.8% extension: 1.1025
        
        Probability: 75% confidence in current count
        
        Alternative Count: Could be Wave C of a larger correction
        """
        
        mock_llm_client.complete.return_value = mock_response
        
        result = await market_analyzer.analyze_elliott_wave(
            symbol="EURUSD",
            price_data=sample_price_data,
            wave_data=sample_wave_data
        )
        
        # Verify result structure
        assert result["symbol"] == "EURUSD"
        assert "wave_analysis" in result
        assert "timestamp" in result
        assert result["current_price"] == sample_price_data['close'].iloc[-1]
        assert result["price_data_points"] == len(sample_price_data)
        
        # Verify prompt construction
        call_args = mock_llm_client.complete.call_args
        prompt = call_args[0][0]
        assert "EURUSD" in prompt
        assert "Elliott Wave pattern" in prompt
        assert "Wave 3" in prompt
        assert "Minor" in prompt
    
    @pytest.mark.asyncio
    async def test_generate_trade_narrative(self, market_analyzer, mock_llm_client,
                                          sample_trade_setup):
        """Test trade narrative generation."""
        mock_narrative = """
        This EUR/USD long position capitalizes on a bullish flag pattern forming at key support.
        
        The setup offers excellent risk/reward at 2.33:1, with a tight stop below recent lows.
        
        Technical confluences include daily uptrend alignment and 4H support bounce.
        
        The trade would be invalidated by a break below 1.0820, suggesting bearish momentum.
        """
        
        mock_llm_client.complete.return_value = mock_narrative
        
        result = await market_analyzer.generate_trade_narrative(sample_trade_setup)
        
        # Verify narrative
        assert "EUR/USD long position" in result
        assert "2.33:1" in result
        assert "1.0820" in result
        
        # Verify prompt included all setup details
        call_args = mock_llm_client.complete.call_args
        prompt = call_args[0][0]
        assert "EURUSD" in prompt
        assert "LONG" in prompt
        assert "1.0850" in prompt
        assert "Bull flag" in prompt
    
    @pytest.mark.asyncio
    async def test_assess_market_regime(self, market_analyzer, mock_llm_client,
                                       sample_price_data):
        """Test market regime assessment."""
        mock_assessment = """
        Regime Classification: Trending (Bullish)
        Strength: 7/10
        
        Recommended Trading Approach:
        - Follow trend with pullback entries
        - Use wider stops to accommodate trend volatility
        - Scale in on dips to moving averages
        
        Key Levels for Regime Change:
        - Break below 1.0800 would signal trend weakness
        - Move above 1.0950 confirms trend continuation
        """
        
        mock_llm_client.complete.return_value = mock_assessment
        
        result = await market_analyzer.assess_market_regime(
            symbol="EURUSD",
            data=sample_price_data,
            lookback_days=30
        )
        
        # Verify result structure
        assert result["symbol"] == "EURUSD"
        assert "regime_assessment" in result
        assert "metrics" in result
        assert result["lookback_days"] == 30
        
        # Verify metrics calculation
        metrics = result["metrics"]
        assert "atr_current" in metrics
        assert "atr_percentile" in metrics
        assert "realized_vol" in metrics
        assert "adx" in metrics
        assert "trend_strength" in metrics
        assert "market_structure" in metrics
    
    def test_prepare_market_data(self, market_analyzer, sample_price_data):
        """Test market data preparation."""
        result = market_analyzer._prepare_market_data(
            symbol="EURUSD",
            timeframe="1h",
            technical_data=sample_price_data
        )
        
        # Verify structure
        assert result["symbol"] == "EURUSD"
        assert result["timeframe"] == "1h"
        assert "timestamp" in result
        assert "close" in result
        assert "rsi" in result
        assert "macd" in result
        assert "sma_50" in result
        assert "sma_200" in result
        
        # Verify values
        latest = sample_price_data.iloc[-1]
        assert result["close"] == latest["close"]
        assert result["rsi"] == latest["rsi_14"]
    
    def test_calculate_change(self, market_analyzer, sample_price_data):
        """Test 24h change calculation."""
        change = market_analyzer._calculate_change(sample_price_data)
        
        # Manual calculation
        current = sample_price_data['close'].iloc[-1]
        previous = sample_price_data['close'].iloc[-24]
        expected = ((current - previous) / previous) * 100
        
        assert abs(change - expected) < 0.0001
    
    def test_calculate_change_insufficient_data(self, market_analyzer):
        """Test change calculation with insufficient data."""
        small_df = pd.DataFrame({
            'close': [1.0850, 1.0851, 1.0852]
        })
        
        change = market_analyzer._calculate_change(small_df)
        assert change == 0
    
    def test_summarize_news(self, market_analyzer, sample_news_data):
        """Test news summarization."""
        summary = market_analyzer._summarize_news(sample_news_data)
        
        assert "Recent news:" in summary
        assert "ECB Maintains Hawkish Stance" in summary
        assert "hawkish" in summary
        assert "1." in summary
        assert "2." in summary
        assert "3." in summary
    
    def test_summarize_news_empty(self, market_analyzer):
        """Test news summarization with no news."""
        summary = market_analyzer._summarize_news([])
        assert summary == "No recent news available."
    
    def test_identify_swings(self, market_analyzer, sample_price_data):
        """Test swing point identification."""
        swings = market_analyzer._identify_swings(sample_price_data)
        
        # Should identify some swing points
        assert "High:" in swings or "Low:" in swings or swings == "No clear swings identified"
    
    def test_calculate_regime_indicators(self, market_analyzer, sample_price_data):
        """Test regime indicator calculation."""
        indicators = market_analyzer._calculate_regime_indicators(
            sample_price_data,
            lookback_days=10
        )
        
        # Verify all indicators are calculated
        assert "atr_current" in indicators
        assert "atr_percentile" in indicators
        assert "realized_vol" in indicators
        assert "adx" in indicators
        assert "trend_strength" in indicators
        assert "price_vs_ma200" in indicators
        assert "market_structure" in indicators
        assert "volume_profile" in indicators
        
        # Verify indicator values make sense
        assert 0 <= indicators["atr_percentile"] <= 100
        assert indicators["realized_vol"] > 0
        assert indicators["trend_strength"] in ["Strong", "Weak"]
        assert indicators["market_structure"] in ["Uptrend", "Downtrend"]
    
    @pytest.mark.asyncio
    async def test_elliott_wave_analysis_depth(self, market_analyzer, mock_llm_client,
                                              sample_price_data):
        """Test Elliott Wave analysis depth option."""
        mock_llm_client.analyze_market.return_value = {
            "analysis": "Elliott Wave focused analysis",
            "type": "elliott_wave"
        }
        
        result = await market_analyzer.analyze_market(
            symbol="EURUSD",
            timeframe="4h",
            technical_data=sample_price_data,
            analysis_depth="elliott_wave"
        )
        
        assert result["type"] == "elliott_wave"
        
        # Verify correct analysis method was called
        mock_llm_client.analyze_market.assert_called_once()
        call_args = mock_llm_client.analyze_market.call_args
        assert call_args[0][1] == "elliott_wave"
    
    @pytest.mark.asyncio
    async def test_concurrent_analyses(self, market_analyzer, mock_llm_client,
                                     sample_price_data):
        """Test concurrent analysis requests."""
        # Setup different responses
        responses = [
            {"analysis": f"Analysis for {symbol}", "type": "comprehensive"}
            for symbol in ["EURUSD", "GBPUSD", "USDJPY"]
        ]
        
        mock_llm_client.analyze_market.side_effect = responses
        
        # Create concurrent tasks
        tasks = []
        for symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
            task = market_analyzer.analyze_market(
                symbol=symbol,
                timeframe="1h",
                technical_data=sample_price_data
            )
            tasks.append(task)
        
        # Execute concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify all completed
        assert len(results) == 3
        for i, result in enumerate(results):
            assert "analysis" in result
            assert f"Analysis for {['EURUSD', 'GBPUSD', 'USDJPY'][i]}" in str(result)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, market_analyzer, mock_llm_client,
                                sample_price_data):
        """Test error handling in analysis."""
        # Make LLM raise an error
        mock_llm_client.analyze_market.side_effect = Exception("LLM API Error")
        
        with pytest.raises(Exception, match="LLM API Error"):
            await market_analyzer.analyze_market(
                symbol="EURUSD",
                timeframe="1h",
                technical_data=sample_price_data
            )
    
    @pytest.mark.asyncio
    async def test_analyze_elliott_wave_without_wave_data(self, market_analyzer, 
                                                        mock_llm_client, sample_price_data):
        """Test Elliott Wave analysis without pre-detected wave data."""
        mock_llm_client.complete.return_value = "Wave analysis without prior detection"
        
        result = await market_analyzer.analyze_elliott_wave(
            symbol="EURUSD",
            price_data=sample_price_data,
            wave_data=None
        )
        
        # Verify prompt doesn't include wave data section
        call_args = mock_llm_client.complete.call_args
        prompt = call_args[0][0]
        assert "Detected Wave Pattern:" not in prompt
        assert "Wave Type:" not in prompt