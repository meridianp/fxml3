"""Sentiment-based signal generator.

This module provides a signal generator that uses market sentiment analysis
to generate trading signals.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from fxml4.config import get_config
from fxml4.strategy.integrated_strategy import Signal, SignalGenerator, SignalSource, SignalType

logger = logging.getLogger(__name__)


class SentimentSignalGenerator(SignalGenerator):
    """Signal generator using market sentiment analysis."""
    
    def __init__(
        self,
        sentiment_analyzer: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the sentiment signal generator.
        
        Args:
            sentiment_analyzer: Sentiment analyzer component.
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.sentiment_analyzer = sentiment_analyzer
        
        # Signal configuration
        self.threshold = self.config.get("threshold", 0.6)
        self.lookback_days = self.config.get("lookback_days", 3)
        self.news_limit = self.config.get("news_limit", 50)
        
        # Sentiment scoring
        self.use_weighted_sentiment = self.config.get("use_weighted_sentiment", True)
        self.recency_weight = self.config.get("recency_weight", 0.6)
        self.relevance_weight = self.config.get("relevance_weight", 0.4)
        
        # News sources configuration
        self.news_sources = self.config.get("news_sources", ["yahoo", "reuters", "bloomberg"])
        
        # Cache settings
        self.use_cache = self.config.get("use_cache", True)
        self.cache_expiry = self.config.get("cache_expiry", 6)  # hours
        self._sentiment_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Initialized sentiment signal generator")
    
    def get_market_sentiment(
        self,
        symbol: str,
        timeframe: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Get market sentiment for a specific symbol.
        
        Args:
            symbol: Trading symbol.
            timeframe: Timeframe.
            **kwargs: Additional arguments.
            
        Returns:
            Dictionary with sentiment analysis results.
        """
        # Check cache first
        cache_key = f"{symbol}_{timeframe}_{self.lookback_days}d"
        current_time = datetime.now()
        
        if (self.use_cache and 
            cache_key in self._sentiment_cache and 
            (current_time - self._sentiment_cache[cache_key]["timestamp"]).total_seconds() < self.cache_expiry * 3600):
            return self._sentiment_cache[cache_key]["data"]
        
        try:
            # Get sentiment from analyzer
            sentiment = self.sentiment_analyzer.analyze_sentiment(
                symbol=symbol,
                lookback_days=self.lookback_days,
                limit=self.news_limit,
                sources=self.news_sources,
                **kwargs
            )
            
            # Store in cache
            if self.use_cache:
                self._sentiment_cache[cache_key] = {
                    "timestamp": current_time,
                    "data": sentiment
                }
            
            return sentiment
            
        except Exception as e:
            logger.exception("Error getting market sentiment: %s", e)
            return {
                "overall_sentiment": 0.0,
                "bullish_articles": 0,
                "bearish_articles": 0,
                "neutral_articles": 0,
                "total_articles": 0,
                "news_items": []
            }
    
    def calculate_signal_strength(
        self,
        sentiment_data: Dict[str, Any]
    ) -> float:
        """Calculate signal strength from sentiment data.
        
        Args:
            sentiment_data: Sentiment analysis results.
            
        Returns:
            Signal strength (0 to 1).
        """
        # Get overall sentiment score (-1 to 1)
        raw_sentiment = sentiment_data.get("overall_sentiment", 0.0)
        
        # For weighted sentiment, account for recency and relevance
        if self.use_weighted_sentiment and "news_items" in sentiment_data:
            news_items = sentiment_data["news_items"]
            
            if not news_items:
                return max(0, min(1, (raw_sentiment + 1) / 2))
            
            # Calculate weighted sentiment
            weighted_sentiments = []
            weights = []
            
            for item in news_items:
                # Get item sentiment
                item_sentiment = item.get("sentiment", 0.0)
                
                # Get recency factor (newer = higher weight)
                published_time = item.get("published_time")
                if published_time:
                    try:
                        if isinstance(published_time, str):
                            published_time = datetime.fromisoformat(published_time.replace('Z', '+00:00'))
                        
                        hours_ago = (datetime.now(published_time.tzinfo) - published_time).total_seconds() / 3600
                        recency_factor = max(0.1, 1 - (hours_ago / (self.lookback_days * 24)))
                    except Exception:
                        recency_factor = 0.5
                else:
                    recency_factor = 0.5
                
                # Get relevance factor
                relevance = item.get("relevance", 0.5)
                
                # Calculate weight
                weight = (
                    recency_factor * self.recency_weight + 
                    relevance * self.relevance_weight
                )
                
                weighted_sentiments.append(item_sentiment * weight)
                weights.append(weight)
            
            # Calculate weighted average
            if sum(weights) > 0:
                weighted_sentiment = sum(weighted_sentiments) / sum(weights)
            else:
                weighted_sentiment = raw_sentiment
            
            # Map from -1..1 to 0..1
            signal_strength = (weighted_sentiment + 1) / 2
        else:
            # Map from -1..1 to 0..1
            signal_strength = (raw_sentiment + 1) / 2
        
        # Ensure range is 0 to 1
        return max(0, min(1, signal_strength))
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> List[Signal]:
        """Generate trading signals using sentiment analysis.
        
        Args:
            data: Market data.
            **kwargs: Additional arguments.
            
        Returns:
            List of generated signals.
        """
        signals = []
        
        # Extract metadata
        symbol = kwargs.get("symbol", data.get("symbol", ["unknown"])[0] 
                            if "symbol" in data.columns else "unknown")
        timeframe = kwargs.get("timeframe", data.get("timeframe", ["unknown"])[0] 
                              if "timeframe" in data.columns else "unknown")
        
        # Get the latest timestamp
        latest_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else pd.Timestamp.now()
        
        try:
            # Get sentiment data
            sentiment_data = self.get_market_sentiment(symbol, timeframe, **kwargs)
            
            if not sentiment_data:
                logger.warning("No sentiment data available for %s", symbol)
                return signals
            
            # Calculate signal strength
            signal_strength = self.calculate_signal_strength(sentiment_data)
            
            # Check for strong bullish sentiment
            if signal_strength >= self.threshold:
                # Create bullish signal
                signal = Signal(
                    signal_type=SignalType.ENTRY_LONG,
                    strength=signal_strength,
                    source=SignalSource.SENTIMENT,
                    timestamp=latest_timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "overall_sentiment": sentiment_data.get("overall_sentiment", 0.0),
                        "bullish_articles": sentiment_data.get("bullish_articles", 0),
                        "bearish_articles": sentiment_data.get("bearish_articles", 0),
                        "neutral_articles": sentiment_data.get("neutral_articles", 0),
                        "total_articles": sentiment_data.get("total_articles", 0),
                        "lookback_days": self.lookback_days,
                    },
                )
                signals.append(signal)
            
            # Check for strong bearish sentiment
            elif signal_strength <= (1 - self.threshold):
                # Create bearish signal
                signal = Signal(
                    signal_type=SignalType.ENTRY_SHORT,
                    strength=1 - signal_strength,
                    source=SignalSource.SENTIMENT,
                    timestamp=latest_timestamp,
                    symbol=symbol,
                    timeframe=timeframe,
                    metadata={
                        "overall_sentiment": sentiment_data.get("overall_sentiment", 0.0),
                        "bullish_articles": sentiment_data.get("bullish_articles", 0),
                        "bearish_articles": sentiment_data.get("bearish_articles", 0),
                        "neutral_articles": sentiment_data.get("neutral_articles", 0),
                        "total_articles": sentiment_data.get("total_articles", 0),
                        "lookback_days": self.lookback_days,
                    },
                )
                signals.append(signal)
            
        except Exception as e:
            logger.exception("Error generating sentiment signals: %s", e)
        
        return signals


class LLMSentimentSignalGenerator(SignalGenerator):
    """Signal generator using LLM-based sentiment analysis."""
    
    def __init__(
        self,
        rag: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the LLM-based sentiment signal generator.
        
        Args:
            rag: RAG system for LLM integration.
            config: Configuration dictionary.
        """
        super().__init__(config)
        self.rag = rag
        
        # Signal configuration
        self.threshold = self.config.get("threshold", 0.65)
        self.lookback_days = self.config.get("lookback_days", 3)
        self.news_limit = self.config.get("news_limit", 30)
        
        # LLM query templates
        self.sentiment_template = self.config.get("sentiment_template", """
        Analyze the market sentiment for {symbol} based on the following recent news headlines:
        
        {headlines}
        
        Based on these headlines, determine the overall market sentiment towards {symbol}.
        Rate the sentiment on a scale of -1 (extremely bearish) to +1 (extremely bullish).
        Provide an explanation for your rating, and identify the most impactful news items.
        What is your confidence level (0-1) in this sentiment assessment?
        """)
        
        # News API configuration
        self.news_api = self.config.get("news_api", None)
        self.news_sources = self.config.get("news_sources", ["yahoo", "reuters", "bloomberg"])
        
        # Cache settings
        self.use_cache = self.config.get("use_cache", True)
        self.cache_expiry = self.config.get("cache_expiry", 4)  # hours
        self._sentiment_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Initialized LLM-based sentiment signal generator")
    
    def get_news_headlines(self, symbol: str) -> List[Dict[str, Any]]:
        """Get recent news headlines for a symbol.
        
        Args:
            symbol: Trading symbol.
            
        Returns:
            List of news items.
        """
        news_items = []
        
        if not self.news_api:
            logger.warning("No news API configured")
            return news_items
        
        try:
            # Convert forex symbols to a searchable format
            search_symbol = symbol
            if '_' in symbol:
                search_symbol = symbol.replace('_', '')
            elif len(symbol) == 6 and symbol.isalpha():
                # Likely a forex pair without separator
                search_symbol = symbol[:3] + '/' + symbol[3:]
            
            # Get news from API
            news_data = self.news_api.get_news(
                search_symbol,
                days=self.lookback_days,
                limit=self.news_limit,
                sources=self.news_sources
            )
            
            if isinstance(news_data, list):
                return news_data
            elif isinstance(news_data, dict) and "items" in news_data:
                return news_data["items"]
            else:
                return []
            
        except Exception as e:
            logger.exception("Error getting news headlines: %s", e)
            return []
    
    def format_headlines(self, news_items: List[Dict[str, Any]]) -> str:
        """Format news headlines for LLM query.
        
        Args:
            news_items: List of news items.
            
        Returns:
            Formatted headlines string.
        """
        if not news_items:
            return "No recent news found."
        
        headlines = []
        
        for i, item in enumerate(news_items[:20]):  # Limit to top 20 for context length
            title = item.get("title", "")
            source = item.get("source", "Unknown")
            
            published = item.get("published_time", "")
            if published:
                if isinstance(published, datetime):
                    published_str = published.strftime("%Y-%m-%d %H:%M")
                else:
                    published_str = str(published)
            else:
                published_str = "Unknown date"
            
            headlines.append(f"{i+1}. [{source}] {title} ({published_str})")
        
        return "\n".join(headlines)
    
    def analyze_sentiment_with_llm(
        self,
        symbol: str,
        headlines: str
    ) -> Dict[str, Any]:
        """Analyze sentiment using LLM.
        
        Args:
            symbol: Trading symbol.
            headlines: Formatted headlines.
            
        Returns:
            Sentiment analysis results.
        """
        # Check if we have the RAG system
        if not self.rag:
            logger.error("Missing RAG system for sentiment analysis")
            return {
                "sentiment_score": 0.0,
                "confidence": 0.0,
                "explanation": "No sentiment analysis available - missing RAG system"
            }
        
        # Format query
        query = self.sentiment_template.format(
            symbol=symbol,
            headlines=headlines
        )
        
        # Get response from RAG
        response = self.rag.query(query)
        
        # Parse the response
        sentiment_score = 0.0
        confidence = 0.0
        
        try:
            import re
            
            # Try to extract sentiment score
            score_patterns = [
                r"sentiment[:\s]*([-+]?\d+\.\d+)",  # sentiment: 0.75
                r"sentiment.+?([-+]?\d+\.\d+)",     # sentiment is 0.75
                r"rating[:\s]*([-+]?\d+\.\d+)",     # rating: 0.75
                r"([-+]?\d+\.\d+)[/\s]*[-+]?1"      # 0.75/1 or 0.75 out of 1
            ]
            
            for pattern in score_patterns:
                matches = re.findall(pattern, response.lower())
                if matches:
                    sentiment_score = float(matches[0])
                    break
            
            # Try to extract confidence
            confidence_patterns = [
                r"confidence[:\s]*(\d+\.\d+)",   # confidence: 0.8
                r"confidence.+?(\d+\.\d+)",      # confidence is 0.8
                r"confidence[:\s]*(\d+)%",       # confidence: 80%
                r"confidence.+?(\d+)%"           # confidence is 80%
            ]
            
            for pattern in confidence_patterns:
                matches = re.findall(pattern, response.lower())
                if matches:
                    confidence_value = float(matches[0])
                    if "%" in pattern:
                        confidence = confidence_value / 100.0
                    else:
                        confidence = confidence_value
                    break
            
            # Default confidence if not found
            if confidence == 0.0:
                confidence = 0.7
            
            # Ensure values are in correct ranges
            sentiment_score = max(-1.0, min(1.0, sentiment_score))
            confidence = max(0.0, min(1.0, confidence))
            
        except Exception as e:
            logger.exception("Error parsing sentiment response: %s", e)
        
        return {
            "sentiment_score": sentiment_score,
            "confidence": confidence,
            "explanation": response,
        }
    
    def generate_signals(
        self,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> List[Signal]:
        """Generate trading signals using LLM-based sentiment analysis.
        
        Args:
            data: Market data.
            **kwargs: Additional arguments.
            
        Returns:
            List of generated signals.
        """
        signals = []
        
        # Extract metadata
        symbol = kwargs.get("symbol", data.get("symbol", ["unknown"])[0] 
                            if "symbol" in data.columns else "unknown")
        timeframe = kwargs.get("timeframe", data.get("timeframe", ["unknown"])[0] 
                              if "timeframe" in data.columns else "unknown")
        
        # Get the latest timestamp
        latest_timestamp = data.index[-1] if isinstance(data.index, pd.DatetimeIndex) else pd.Timestamp.now()
        
        # Check cache first
        cache_key = f"{symbol}_{self.lookback_days}d"
        current_time = datetime.now()
        
        if (self.use_cache and 
            cache_key in self._sentiment_cache and 
            (current_time - self._sentiment_cache[cache_key]["timestamp"]).total_seconds() < self.cache_expiry * 3600):
            sentiment_result = self._sentiment_cache[cache_key]["data"]
        else:
            try:
                # Get news headlines
                news_items = self.get_news_headlines(symbol)
                
                # Format headlines for LLM
                headlines = self.format_headlines(news_items)
                
                # Analyze sentiment
                sentiment_result = self.analyze_sentiment_with_llm(symbol, headlines)
                
                # Store in cache
                if self.use_cache:
                    self._sentiment_cache[cache_key] = {
                        "timestamp": current_time,
                        "data": sentiment_result
                    }
                
            except Exception as e:
                logger.exception("Error in LLM sentiment analysis: %s", e)
                return signals
        
        # Extract sentiment score and confidence
        sentiment_score = sentiment_result.get("sentiment_score", 0.0)
        confidence = sentiment_result.get("confidence", 0.0)
        
        # Apply confidence to sentiment score
        adjusted_score = sentiment_score * confidence
        
        # Map from -1..1 to 0..1
        signal_strength = (adjusted_score + 1) / 2
        
        # Generate signals based on sentiment
        if sentiment_score >= 0.3 and signal_strength >= self.threshold:
            # Bullish signal
            signal = Signal(
                signal_type=SignalType.ENTRY_LONG,
                strength=signal_strength,
                source=SignalSource.SENTIMENT,
                timestamp=latest_timestamp,
                symbol=symbol,
                timeframe=timeframe,
                metadata={
                    "sentiment_score": sentiment_score,
                    "confidence": confidence,
                    "explanation": sentiment_result.get("explanation", "")[:500],  # Limit length
                    "lookback_days": self.lookback_days,
                },
            )
            signals.append(signal)
        
        elif sentiment_score <= -0.3 and (1 - signal_strength) >= self.threshold:
            # Bearish signal
            signal = Signal(
                signal_type=SignalType.ENTRY_SHORT,
                strength=1 - signal_strength,
                source=SignalSource.SENTIMENT,
                timestamp=latest_timestamp,
                symbol=symbol,
                timeframe=timeframe,
                metadata={
                    "sentiment_score": sentiment_score,
                    "confidence": confidence,
                    "explanation": sentiment_result.get("explanation", "")[:500],  # Limit length
                    "lookback_days": self.lookback_days,
                },
            )
            signals.append(signal)
        
        return signals