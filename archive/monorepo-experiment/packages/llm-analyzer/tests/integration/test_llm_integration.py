"""Integration tests for LLM analyzer components."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import os

from fxml4_llm.client import LLMClient, LLMProvider, LLMConfig
from fxml4_llm.sentiment import SentimentAnalyzer
from fxml4_llm.market_analyzer import MarketAnalyzer


@pytest.fixture
def integration_config():
    """Configuration for integration tests."""
    return LLMConfig(
        openai_api_key=os.environ.get("TEST_OPENAI_API_KEY", "test_key"),
        anthropic_api_key=os.environ.get("TEST_ANTHROPIC_API_KEY", "test_key"),
        default_provider=LLMProvider.OPENAI,
        default_model="gpt-3.5-turbo",
        max_tokens=500,
        temperature=0.5
    )


@pytest.fixture
def sample_market_data():
    """Generate realistic market data for integration tests."""
    # Generate 7 days of hourly data
    dates = pd.date_range(start='2024-01-08', end='2024-01-15', freq='h')
    np.random.seed(42)
    
    # Simulate realistic price movement
    base_price = 1.0850
    trend = 0.0001  # Slight uptrend
    prices = []
    
    for i, date in enumerate(dates):
        # Add daily seasonality
        hour = date.hour
        daily_factor = np.sin(2 * np.pi * hour / 24) * 0.0003
        
        # Add trend and noise
        base_price += trend + np.random.randn() * 0.0002 + daily_factor
        
        # Generate OHLC
        open_price = base_price + np.random.randn() * 0.0001
        high = base_price + abs(np.random.randn() * 0.0003)
        low = base_price - abs(np.random.randn() * 0.0003)
        close = base_price + np.random.randn() * 0.0001
        
        # Ensure OHLC relationships are valid
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        
        volume = np.random.randint(5000, 20000) * (1 + abs(np.random.randn() * 0.5))
        
        prices.append({
            'timestamp': date,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': int(volume)
        })
    
    df = pd.DataFrame(prices)
    df.set_index('timestamp', inplace=True)
    
    # Add technical indicators
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['sma_200'] = df['close'].rolling(window=200).mean().fillna(base_price)
    
    # RSI calculation (simplified)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))
    df['rsi_14'].fillna(50, inplace=True)
    
    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # ATR
    df['tr'] = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    df['atr_14'] = df['tr'].rolling(window=14).mean()
    
    # ADX (simplified)
    df['adx'] = 25 + np.sin(np.arange(len(df)) * 0.1) * 10
    
    return df


@pytest.fixture
def comprehensive_news_data():
    """Generate comprehensive news data for testing."""
    base_time = datetime.now() - timedelta(hours=24)
    
    news_items = []
    sentiments = ['positive', 'negative', 'neutral', 'mixed']
    impacts = ['high', 'medium', 'low']
    
    headlines = [
        "ECB Signals More Rate Hikes Ahead",
        "US Dollar Weakens on Fed Pivot Hopes",
        "EUR/USD Technical Analysis: Key Resistance at 1.09",
        "European Economic Data Beats Expectations",
        "Geopolitical Tensions Weigh on Risk Sentiment",
        "Major Bank Upgrades EUR/USD Forecast",
        "Options Market Shows Bullish EUR Positioning",
        "US Inflation Data Due Tomorrow",
        "ECB Minutes Reveal Hawkish Tilt",
        "Technical Breakout Imminent for EUR/USD"
    ]
    
    for i, headline in enumerate(headlines):
        news_items.append({
            "id": f"news_{i}",
            "title": headline,
            "content": f"Detailed analysis: {headline}. Market implications are significant.",
            "source": ["Reuters", "Bloomberg", "FXStreet", "MarketWatch"][i % 4],
            "sentiment": sentiments[i % 4],
            "impact": impacts[i % 3],
            "timestamp": (base_time + timedelta(hours=i*2)).isoformat(),
            "symbols": ["EURUSD", "USD", "EUR"]
        })
    
    return news_items


@pytest.mark.integration
class TestLLMClientIntegration:
    """Integration tests for LLM client with multiple providers."""
    
    @pytest.mark.asyncio
    async def test_openai_client_integration(self, integration_config):
        """Test OpenAI client integration."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            # Mock the client
            client_instance = Mock()
            mock_openai.return_value = client_instance
            
            # Mock completion
            completion = Mock()
            completion.choices = [Mock(message=Mock(content="OpenAI response: Bullish sentiment"))]
            client_instance.chat.completions.create = AsyncMock(return_value=completion)
            
            # Create client
            llm = LLMClient(provider=LLMProvider.OPENAI, config=integration_config)
            
            # Test completion
            result = await llm.complete(
                prompt="Analyze EUR/USD sentiment",
                system="You are a forex analyst"
            )
            
            assert "OpenAI response" in result
            assert "Bullish sentiment" in result
    
    @pytest.mark.asyncio
    async def test_anthropic_client_integration(self, integration_config):
        """Test Anthropic client integration."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            # Mock the client
            client_instance = Mock()
            mock_anthropic.return_value = client_instance
            
            # Mock message
            message = Mock()
            message.content = [Mock(text="Anthropic response: Market analysis complete")]
            client_instance.messages.create = AsyncMock(return_value=message)
            
            # Create client
            config = integration_config
            config.default_provider = LLMProvider.ANTHROPIC
            llm = LLMClient(provider=LLMProvider.ANTHROPIC, config=config)
            
            # Test completion
            result = await llm.complete(
                prompt="Provide market analysis",
                max_tokens=200
            )
            
            assert "Anthropic response" in result
            assert "Market analysis complete" in result
    
    @pytest.mark.asyncio
    async def test_provider_switching(self, integration_config):
        """Test switching between providers."""
        with patch('openai.AsyncOpenAI') as mock_openai, \
             patch('anthropic.AsyncAnthropic') as mock_anthropic:
            
            # Setup mocks
            openai_instance = Mock()
            openai_completion = Mock()
            openai_completion.choices = [Mock(message=Mock(content="OpenAI analysis"))]
            openai_instance.chat.completions.create = AsyncMock(return_value=openai_completion)
            mock_openai.return_value = openai_instance
            
            anthropic_instance = Mock()
            anthropic_message = Mock()
            anthropic_message.content = [Mock(text="Anthropic analysis")]
            anthropic_instance.messages.create = AsyncMock(return_value=anthropic_message)
            mock_anthropic.return_value = anthropic_instance
            
            # Test with OpenAI
            llm_openai = LLMClient(provider="openai", config=integration_config)
            result1 = await llm_openai.complete("Test prompt")
            assert "OpenAI analysis" in result1
            
            # Test with Anthropic
            llm_anthropic = LLMClient(provider="anthropic", config=integration_config)
            result2 = await llm_anthropic.complete("Test prompt")
            assert "Anthropic analysis" in result2


@pytest.mark.integration
class TestSentimentAnalyzerIntegration:
    """Integration tests for sentiment analysis with LLM."""
    
    @pytest.mark.asyncio
    async def test_news_sentiment_analysis_flow(self, integration_config, comprehensive_news_data):
        """Test complete news sentiment analysis flow."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            # Setup mock
            client_instance = Mock()
            mock_openai.return_value = client_instance
            
            # Mock different responses for different news items
            responses = []
            for i, news in enumerate(comprehensive_news_data):
                sentiment_score = 0.8 if news['sentiment'] == 'positive' else -0.5 if news['sentiment'] == 'negative' else 0.0
                response = f"""
                Sentiment Score: {sentiment_score}
                Confidence: High
                Key Factors: {news['title']}
                Market Impact: {news['impact']}
                """
                completion = Mock()
                completion.choices = [Mock(message=Mock(content=response))]
                responses.append(completion)
            
            client_instance.chat.completions.create = AsyncMock(side_effect=responses)
            
            # Create analyzer
            llm = LLMClient(config=integration_config)
            analyzer = SentimentAnalyzer(llm)
            
            # Mock parsing
            def mock_parse(response, text):
                score_line = [l for l in response.split('\n') if 'Sentiment Score:' in l][0]
                score = float(score_line.split(':')[1].strip())
                return {
                    "sentiment_score": score,
                    "confidence": "high",
                    "original_text": text
                }
            
            analyzer._parse_sentiment_response = mock_parse
            
            # Analyze batch
            result = await analyzer.analyze_news_batch(
                comprehensive_news_data[:5],  # First 5 items
                asset="EURUSD"
            )
            
            # Verify batch analysis
            assert "overall_sentiment" in result
            assert "sentiment_distribution" in result
            assert isinstance(result["overall_sentiment"], (int, float))
    
    @pytest.mark.asyncio
    async def test_market_mood_integration(self, integration_config, 
                                         comprehensive_news_data):
        """Test market mood analysis integration."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            # Setup mock
            client_instance = Mock()
            mock_openai.return_value = client_instance
            
            mood_response = """
            1. Overall market sentiment score: 0.45
            2. Key themes: ECB hawkishness, Dollar weakness, Technical resistance
            3. Sentiment trend: Improving
            4. Risk factors: Geopolitical tensions, Upcoming data
            5. Contrarian indicators: Extreme bullish positioning in options
            """
            
            completion = Mock()
            completion.choices = [Mock(message=Mock(content=mood_response))]
            client_instance.chat.completions.create = AsyncMock(return_value=completion)
            
            # Create analyzer
            llm = LLMClient(config=integration_config)
            analyzer = SentimentAnalyzer(llm)
            
            # Prepare data
            social_data = [
                {"text": "Bullish EUR/USD setup!", "source": "twitter"},
                {"text": "Selling USD on weakness", "source": "reddit"}
            ]
            
            # Analyze mood
            result = await analyzer.analyze_market_mood(
                social_data=social_data,
                news_data=comprehensive_news_data[:3],
                asset="EURUSD"
            )
            
            # Verify the complete prompt was built
            call_args = client_instance.chat.completions.create.call_args
            messages = call_args.kwargs['messages']
            user_message = messages[-1]['content']
            
            assert "EURUSD" in user_message
            assert "Overall market sentiment score" in user_message


@pytest.mark.integration
class TestMarketAnalyzerIntegration:
    """Integration tests for market analysis with LLM."""
    
    @pytest.mark.asyncio
    async def test_comprehensive_market_analysis(self, integration_config, 
                                               sample_market_data, 
                                               comprehensive_news_data):
        """Test comprehensive market analysis flow."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            # Setup mock
            client_instance = Mock()
            mock_openai.return_value = client_instance
            
            analysis_response = """
            Market Analysis for EUR/USD:
            
            Current Trend: Bullish momentum building
            Key Levels: Support at 1.0820, Resistance at 1.0950
            
            Technical Indicators:
            - RSI showing overbought conditions (70+)
            - MACD bullish crossover confirmed
            - Price above all major moving averages
            
            Elliott Wave Count:
            - Likely in Wave 3 of larger degree impulse
            - Target: 1.0980-1.1020
            
            Risk Assessment:
            - Primary risk: Overbought conditions
            - Stop loss recommended below 1.0820
            
            Trade Recommendation:
            - Wait for pullback to 1.0870-1.0880
            - Long entry with stop at 1.0820
            - Target 1.0950 initially
            """
            
            completion = Mock()
            completion.choices = [Mock(message=Mock(content=analysis_response))]
            client_instance.chat.completions.create = AsyncMock(return_value=completion)
            
            # Create analyzer
            llm = LLMClient(config=integration_config)
            llm.analyze_market = AsyncMock(return_value={
                "analysis": analysis_response,
                "timestamp": sample_market_data.index[-1],
                "symbol": "EURUSD"
            })
            
            analyzer = MarketAnalyzer(llm)
            
            # Perform analysis
            result = await analyzer.analyze_market(
                symbol="EURUSD",
                timeframe="1h",
                technical_data=sample_market_data,
                news_data=comprehensive_news_data[:3],
                analysis_depth="standard"
            )
            
            # Verify comprehensive analysis
            assert result["type"] == "standard"
            assert "analysis" in result
            assert "EUR/USD" in result["analysis"]
            assert "Elliott Wave" in result["analysis"]
            assert "Risk Assessment" in result["analysis"]
    
    @pytest.mark.asyncio
    async def test_elliott_wave_focused_analysis(self, integration_config, 
                                               sample_market_data):
        """Test Elliott Wave focused analysis integration."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            # Setup mock
            client_instance = Mock()
            mock_openai.return_value = client_instance
            
            wave_response = """
            Elliott Wave Analysis Validation:
            
            Current Count: Wave 3 of (3) - CONFIRMED
            - Wave proportions follow Fibonacci relationships
            - Wave 3 extending beyond 1.618x Wave 1
            
            Price Targets:
            - Wave 3 completion: 1.0965 (161.8% extension)
            - Wave 4 pullback: 1.0900-1.0920
            - Wave 5 projection: 1.1020-1.1050
            
            Key Fibonacci Levels:
            - 1.0965: 161.8% of Wave 1
            - 1.1025: 261.8% of Wave 1
            - 1.0920: 38.2% retracement for Wave 4
            
            Confidence: 80% - Strong impulsive structure
            
            Alternative Count:
            - Could be completing Wave C of larger ABC
            - Invalidation: Break below 1.0780
            """
            
            completion = Mock()
            completion.choices = [Mock(message=Mock(content=wave_response))]
            client_instance.chat.completions.create = AsyncMock(return_value=completion)
            
            # Create analyzer
            llm = LLMClient(config=integration_config)
            analyzer = MarketAnalyzer(llm)
            
            # Wave data
            wave_data = {
                "wave_type": "Impulse",
                "current_wave": "Wave 3 of (3)",
                "degree": "Intermediate",
                "completion": 65.0
            }
            
            # Analyze
            result = await analyzer.analyze_elliott_wave(
                symbol="EURUSD",
                price_data=sample_market_data,
                wave_data=wave_data
            )
            
            # Verify Elliott Wave specific analysis
            assert "wave_analysis" in result
            assert "Wave 3" in result["wave_analysis"]
            assert "Fibonacci" in result["wave_analysis"]
            assert "1.0965" in result["wave_analysis"]
    
    @pytest.mark.asyncio
    async def test_regime_assessment_integration(self, integration_config, 
                                               sample_market_data):
        """Test market regime assessment integration."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            # Setup mock
            client_instance = Mock()
            mock_openai.return_value = client_instance
            
            regime_response = """
            Market Regime Classification: TRENDING (Bullish)
            Regime Strength: 8/10
            
            Analysis:
            - Strong directional movement confirmed by ADX > 25
            - Series of higher highs and higher lows intact
            - Low volatility relative to trend strength
            - Volume supporting the upward movement
            
            Recommended Trading Approach:
            1. Trend-following strategies optimal
            2. Buy dips to moving averages (20 SMA, 50 SMA)
            3. Use trailing stops to capture trend
            4. Avoid counter-trend trades
            5. Scale in on pullbacks
            
            Key Levels for Regime Change:
            - Bearish regime shift below 1.0780 (breaks market structure)
            - Acceleration above 1.0980 (potential parabolic move)
            - Consolidation likely between 1.0850-1.0950
            
            Timeframe for reassessment: 48-72 hours
            """
            
            completion = Mock()
            completion.choices = [Mock(message=Mock(content=regime_response))]
            client_instance.chat.completions.create = AsyncMock(return_value=completion)
            
            # Create analyzer
            llm = LLMClient(config=integration_config)
            analyzer = MarketAnalyzer(llm)
            
            # Assess regime
            result = await analyzer.assess_market_regime(
                symbol="EURUSD",
                data=sample_market_data,
                lookback_days=14
            )
            
            # Verify regime assessment
            assert "regime_assessment" in result
            assert "metrics" in result
            assert "TRENDING" in result["regime_assessment"]
            assert "8/10" in result["regime_assessment"]
            
            # Verify metrics were calculated
            metrics = result["metrics"]
            assert metrics["trend_strength"] in ["Strong", "Weak"]
            assert 0 <= metrics["atr_percentile"] <= 100
    
    @pytest.mark.asyncio
    async def test_trade_narrative_generation(self, integration_config):
        """Test trade narrative generation integration."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            # Setup mock
            client_instance = Mock()
            mock_openai.return_value = client_instance
            
            narrative_response = """
            EUR/USD Long Position - Risk/Reward 2.5:1
            
            This setup capitalizes on a textbook bull flag pattern forming at a key support level. 
            The daily trend remains firmly bullish, and we're seeing a healthy pullback to the 
            50-period moving average on the 4-hour chart.
            
            Technical Confluence:
            - Bull flag pattern completion at 1.0850
            - 50 SMA support on 4H timeframe
            - Previous resistance turned support
            - RSI showing oversold bounce from 35
            
            Entry: 1.0850 (limit order at flag support)
            Stop Loss: 1.0820 (below flag low and psychological level)
            Take Profit: 1.0925 (measured move target)
            
            Risk Management:
            - 30 pip stop for 75 pip target
            - Risk 1% of account on this trade
            - Move stop to breakeven at +30 pips
            
            Trade Invalidation:
            - Break below 1.0820 negates the bull flag
            - Loss of 4H 50 SMA support
            - RSI failure to hold above 40
            """
            
            completion = Mock()
            completion.choices = [Mock(message=Mock(content=narrative_response))]
            client_instance.chat.completions.create = AsyncMock(return_value=completion)
            
            # Create analyzer
            llm = LLMClient(config=integration_config)
            analyzer = MarketAnalyzer(llm)
            
            # Trade setup
            trade_setup = {
                "symbol": "EURUSD",
                "direction": "LONG",
                "entry_price": 1.0850,
                "stop_loss": 1.0820,
                "take_profit": 1.0925,
                "risk_reward_ratio": 2.5,
                "technical_factors": {
                    "pattern": "Bull flag",
                    "support": "50 SMA",
                    "rsi": 35
                }
            }
            
            # Generate narrative
            narrative = await analyzer.generate_trade_narrative(trade_setup)
            
            # Verify narrative quality
            assert "EUR/USD Long Position" in narrative
            assert "1.0850" in narrative
            assert "Bull flag" in narrative
            assert "Risk Management" in narrative
            assert "Trade Invalidation" in narrative