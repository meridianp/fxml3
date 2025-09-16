"""Real-time market analysis using LLMs for enhanced trading decisions."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
import numpy as np

from .llm_client import LLMClient
from .sentiment_analysis import MarketSentimentAnalyzer
from .rag import FXML4RAG

logger = logging.getLogger(__name__)


class RealtimeMarketAnalyst:
    """Real-time market analysis using multiple LLM-powered components."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the real-time market analyst.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Initialize LLM components
        self.llm_client = LLMClient()
        self.sentiment_analyzer = MarketSentimentAnalyzer()
        self.rag_system = FXML4RAG()
        
        # Analysis cache
        self.analysis_cache = {}
        self.cache_duration = timedelta(minutes=5)
        
        # Market context window
        self.price_history = deque(maxlen=100)
        self.volume_history = deque(maxlen=100)
        self.sentiment_history = deque(maxlen=50)
        
        # Analysis parameters
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
        self.update_interval = config.get('update_interval', 60)  # seconds
        
    async def analyze_market_conditions(self, 
                                      symbol: str,
                                      price_data: Dict[str, Any],
                                      timeframe: str = '4h') -> Dict[str, Any]:
        """Perform comprehensive market analysis using LLMs.
        
        Args:
            symbol: Trading symbol (e.g., 'GBPUSD')
            price_data: Recent price data including OHLCV
            timeframe: Analysis timeframe
            
        Returns:
            Comprehensive market analysis
        """
        # Check cache first
        cache_key = f"{symbol}_{timeframe}_{datetime.now().hour}"
        if cache_key in self.analysis_cache:
            cached_analysis = self.analysis_cache[cache_key]
            if datetime.now() - cached_analysis['timestamp'] < self.cache_duration:
                return cached_analysis['analysis']
        
        # Gather all analysis components
        analysis_tasks = [
            self._analyze_market_structure(symbol, price_data),
            self._analyze_sentiment(symbol),
            self._analyze_technical_patterns(symbol, price_data),
            self._analyze_fundamental_context(symbol),
            self._generate_trade_recommendation(symbol, price_data)
        ]
        
        # Run analyses in parallel
        results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        
        # Combine results
        market_analysis = {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.now(),
            'market_structure': results[0] if not isinstance(results[0], Exception) else None,
            'sentiment': results[1] if not isinstance(results[1], Exception) else None,
            'technical_patterns': results[2] if not isinstance(results[2], Exception) else None,
            'fundamental_context': results[3] if not isinstance(results[3], Exception) else None,
            'trade_recommendation': results[4] if not isinstance(results[4], Exception) else None,
        }
        
        # Calculate overall confidence
        confidence_scores = []
        for component in ['market_structure', 'sentiment', 'technical_patterns']:
            if market_analysis[component] and 'confidence' in market_analysis[component]:
                confidence_scores.append(market_analysis[component]['confidence'])
        
        market_analysis['overall_confidence'] = np.mean(confidence_scores) if confidence_scores else 0.5
        
        # Cache the analysis
        self.analysis_cache[cache_key] = {
            'timestamp': datetime.now(),
            'analysis': market_analysis
        }
        
        return market_analysis
    
    async def _analyze_market_structure(self, symbol: str, price_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market structure using LLM."""
        try:
            # Prepare price data summary
            prices = price_data.get('close', [])
            if len(prices) < 20:
                return {'error': 'Insufficient price data'}
            
            # Calculate key levels
            recent_high = max(prices[-20:])
            recent_low = min(prices[-20:])
            current_price = prices[-1]
            sma_20 = np.mean(prices[-20:])
            sma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else sma_20
            
            prompt = f"""Analyze the market structure for {symbol}:

Current Price: {current_price:.5f}
20-Period High: {recent_high:.5f}
20-Period Low: {recent_low:.5f}
20-SMA: {sma_20:.5f}
50-SMA: {sma_50:.5f}

Recent price action shows {'upward' if prices[-1] > prices[-5] else 'downward'} movement.

Provide a JSON response with:
1. trend: "bullish", "bearish", or "ranging"
2. strength: 0-1 score
3. key_levels: list of important price levels
4. market_phase: "accumulation", "markup", "distribution", or "markdown"
5. confidence: 0-1 score
6. reasoning: brief explanation"""

            response = await self.llm_client.generate_text_async(prompt)
            
            # Parse JSON response
            try:
                analysis = json.loads(response)
                return analysis
            except json.JSONDecodeError:
                # Fallback to rule-based analysis
                trend = "bullish" if current_price > sma_20 > sma_50 else "bearish"
                return {
                    'trend': trend,
                    'strength': 0.6,
                    'key_levels': [recent_high, sma_20, recent_low],
                    'market_phase': 'markup' if trend == 'bullish' else 'markdown',
                    'confidence': 0.5,
                    'reasoning': 'Rule-based analysis fallback'
                }
                
        except Exception as e:
            logger.error(f"Error in market structure analysis: {e}")
            return {'error': str(e)}
    
    async def _analyze_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Get real-time sentiment analysis."""
        try:
            # Get sentiment from news
            sentiment_data = self.sentiment_analyzer.get_market_sentiment(
                symbol, 
                lookback_hours=24
            )
            
            # Enhance with LLM interpretation
            if sentiment_data['articles']:
                recent_headlines = [article['title'] for article in sentiment_data['articles'][:5]]
                
                prompt = f"""Analyze the market sentiment for {symbol} based on recent news:

Headlines:
{chr(10).join(f"- {headline}" for headline in recent_headlines)}

Current sentiment score: {sentiment_data['sentiment_score']:.2f}

Provide a JSON response with:
1. sentiment: "bullish", "bearish", or "neutral"
2. strength: 0-1 score
3. key_themes: list of main market themes
4. risk_factors: list of potential risks
5. confidence: 0-1 score"""

                response = await self.llm_client.generate_text_async(prompt)
                
                try:
                    llm_sentiment = json.loads(response)
                    # Combine with quantitative sentiment
                    llm_sentiment['quantitative_score'] = sentiment_data['sentiment_score']
                    return llm_sentiment
                except json.JSONDecodeError:
                    pass
            
            # Fallback to quantitative sentiment
            return {
                'sentiment': 'bullish' if sentiment_data['sentiment_score'] > 0.2 else 
                           ('bearish' if sentiment_data['sentiment_score'] < -0.2 else 'neutral'),
                'strength': abs(sentiment_data['sentiment_score']),
                'confidence': 0.6,
                'source': 'quantitative_analysis'
            }
            
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return {'error': str(e)}
    
    async def _analyze_technical_patterns(self, symbol: str, price_data: Dict[str, Any]) -> Dict[str, Any]:
        """Identify technical patterns using LLM and algorithms."""
        try:
            # Use RAG to find similar historical patterns
            prices = price_data.get('close', [])
            if len(prices) < 50:
                return {'patterns': [], 'confidence': 0.3}
            
            # Create price description for RAG
            price_movement = self._describe_price_movement(prices)
            
            # Query RAG for similar patterns
            rag_results = self.rag_system.query(
                f"Technical patterns similar to: {price_movement}",
                k=3
            )
            
            # Prepare context for LLM
            historical_patterns = "\n".join([doc.page_content for doc in rag_results])
            
            prompt = f"""Analyze technical patterns for {symbol}:

Recent price movement: {price_movement}

Historical similar patterns:
{historical_patterns}

Current indicators:
- RSI: {self._calculate_rsi(prices):.1f}
- MACD: {'bullish' if self._calculate_macd_signal(prices) > 0 else 'bearish'}
- Volume trend: {'increasing' if len(price_data.get('volume', [])) > 0 and price_data['volume'][-1] > np.mean(price_data['volume'][-10:]) else 'decreasing'}

Identify patterns and provide JSON response:
1. patterns: list of identified patterns with confidence scores
2. primary_pattern: most likely pattern
3. target_levels: potential price targets
4. invalidation_level: where pattern fails
5. confidence: overall confidence score"""

            response = await self.llm_client.generate_text_async(prompt)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {
                    'patterns': ['Unable to parse LLM response'],
                    'confidence': 0.4
                }
                
        except Exception as e:
            logger.error(f"Error in pattern analysis: {e}")
            return {'error': str(e)}
    
    async def _analyze_fundamental_context(self, symbol: str) -> Dict[str, Any]:
        """Analyze fundamental market context."""
        try:
            base_currency = symbol[:3]
            quote_currency = symbol[3:6]
            
            prompt = f"""Provide fundamental analysis context for {symbol}:

Consider:
1. Central bank policies for {base_currency} and {quote_currency}
2. Recent economic data releases
3. Geopolitical factors
4. Market risk sentiment

Provide JSON response with:
1. fundamental_bias: "bullish", "bearish", or "neutral"
2. key_drivers: list of main fundamental factors
3. upcoming_events: list of important upcoming events
4. risk_assessment: current risk level (low/medium/high)
5. confidence: 0-1 score"""

            response = await self.llm_client.generate_text_async(prompt)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {
                    'fundamental_bias': 'neutral',
                    'confidence': 0.3,
                    'note': 'Unable to parse fundamental analysis'
                }
                
        except Exception as e:
            logger.error(f"Error in fundamental analysis: {e}")
            return {'error': str(e)}
    
    async def _generate_trade_recommendation(self, symbol: str, price_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive trade recommendation."""
        try:
            # Gather all analysis results (from cache)
            cache_key = f"{symbol}_4h_{datetime.now().hour}"
            cached = self.analysis_cache.get(cache_key, {}).get('analysis', {})
            
            market_structure = cached.get('market_structure', {})
            sentiment = cached.get('sentiment', {})
            patterns = cached.get('technical_patterns', {})
            fundamentals = cached.get('fundamental_context', {})
            
            current_price = price_data.get('close', [])[-1] if price_data.get('close') else 0
            
            prompt = f"""Generate trading recommendation for {symbol}:

Current Price: {current_price:.5f}

Market Analysis Summary:
- Trend: {market_structure.get('trend', 'unknown')}
- Sentiment: {sentiment.get('sentiment', 'unknown')} ({sentiment.get('strength', 0):.1%} strength)
- Primary Pattern: {patterns.get('primary_pattern', 'none identified')}
- Fundamental Bias: {fundamentals.get('fundamental_bias', 'neutral')}

Provide a specific trading recommendation in JSON format:
1. action: "buy", "sell", or "hold"
2. confidence: 0-1 score
3. entry_price: suggested entry price
4. stop_loss: stop loss level
5. take_profit: take profit level
6. position_size: "small", "medium", or "large"
7. rationale: brief explanation
8. risks: list of key risks
9. timeframe: holding period expectation"""

            response = await self.llm_client.generate_text_async(prompt)
            
            try:
                recommendation = json.loads(response)
                # Validate recommendation
                if recommendation.get('action') in ['buy', 'sell']:
                    # Ensure stop loss and take profit are reasonable
                    if recommendation.get('stop_loss'):
                        sl_distance = abs(current_price - recommendation['stop_loss'])
                        tp_distance = abs(recommendation.get('take_profit', current_price) - current_price)
                        
                        # Ensure minimum 1:1 risk-reward
                        if tp_distance < sl_distance:
                            recommendation['take_profit'] = current_price + (2 * sl_distance * 
                                                                           (1 if recommendation['action'] == 'buy' else -1))
                
                return recommendation
                
            except json.JSONDecodeError:
                return {
                    'action': 'hold',
                    'confidence': 0.3,
                    'rationale': 'Unable to generate clear recommendation'
                }
                
        except Exception as e:
            logger.error(f"Error generating recommendation: {e}")
            return {'error': str(e)}
    
    def _describe_price_movement(self, prices: List[float]) -> str:
        """Create a textual description of price movement."""
        if len(prices) < 10:
            return "Insufficient data"
        
        # Calculate changes
        pct_change = (prices[-1] - prices[-10]) / prices[-10] * 100
        volatility = np.std(prices[-10:]) / np.mean(prices[-10:]) * 100
        
        # Identify trend
        if pct_change > 2:
            trend = "strong upward"
        elif pct_change > 0.5:
            trend = "mild upward"
        elif pct_change < -2:
            trend = "strong downward"
        elif pct_change < -0.5:
            trend = "mild downward"
        else:
            trend = "sideways"
        
        return f"{trend} movement with {pct_change:.1f}% change and {volatility:.1f}% volatility"
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI indicator."""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices[-period-1:])
        gains = deltas[deltas > 0].sum() / period
        losses = -deltas[deltas < 0].sum() / period
        
        if losses == 0:
            return 100.0
        
        rs = gains / losses
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd_signal(self, prices: List[float]) -> float:
        """Calculate MACD signal (simplified)."""
        if len(prices) < 26:
            return 0.0
        
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        
        return ema_12 - ema_26
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA."""
        if len(prices) < period:
            return prices[-1]
        
        multiplier = 2 / (period + 1)
        ema = prices[-period]
        
        for price in prices[-period+1:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    async def stream_analysis(self, symbol: str, callback: callable):
        """Stream real-time analysis updates.
        
        Args:
            symbol: Trading symbol
            callback: Function to call with analysis updates
        """
        while True:
            try:
                # Get latest price data (placeholder - would come from real feed)
                price_data = {
                    'close': list(self.price_history),
                    'volume': list(self.volume_history)
                }
                
                # Perform analysis
                analysis = await self.analyze_market_conditions(symbol, price_data)
                
                # Call callback with results
                await callback(analysis)
                
                # Wait for next update
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in analysis stream: {e}")
                await asyncio.sleep(10)  # Wait before retrying