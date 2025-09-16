#!/usr/bin/env python
"""Alpha Vantage News Sentiment API implementation."""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import pandas as pd
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class AlphaVantageNewsAPI:
    """Implementation of Alpha Vantage NEWS_SENTIMENT API for forex trading."""
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    # Forex ticker mapping
    FOREX_TICKERS = {
        'USD': 'FOREX:USD',
        'EUR': 'FOREX:EUR',
        'GBP': 'FOREX:GBP',
        'JPY': 'FOREX:JPY',
        'CHF': 'FOREX:CHF',
        'AUD': 'FOREX:AUD',
        'NZD': 'FOREX:NZD',
        'CAD': 'FOREX:CAD'
    }
    
    # Topics relevant to forex trading
    FOREX_TOPICS = [
        'economy_fiscal',
        'economy_monetary',
        'economy_macro',
        'financial_markets',
        'finance',
        'earnings'
    ]
    
    def __init__(self, api_key: Optional[str] = None, cache_duration: int = 3600):
        """Initialize the News API client.
        
        Args:
            api_key: Alpha Vantage API key
            cache_duration: Cache duration in seconds (default 1 hour)
        """
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY')
        if not self.api_key:
            logger.warning("No Alpha Vantage API key found")
        
        self.cache_duration = cache_duration
        self._cache = {}
        self._rate_limiter = RateLimiter(calls_per_minute=75)  # Premium tier
    
    def get_forex_sentiment(
        self,
        symbol: str,
        time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None,
        limit: int = 50,
        use_cache: bool = True
    ) -> Dict:
        """Get news sentiment for a forex pair.
        
        Args:
            symbol: Forex pair symbol (e.g., 'EURUSD')
            time_from: Start time for news (default: 24 hours ago)
            time_to: End time for news (default: now)
            limit: Number of articles to retrieve (max 1000)
            use_cache: Whether to use cached results
            
        Returns:
            Dictionary containing sentiment analysis results
        """
        if not self.api_key:
            return self._empty_response()
        
        # Parse symbol to get currencies
        currencies = self._parse_forex_symbol(symbol)
        if not currencies:
            logger.warning(f"Invalid forex symbol: {symbol}")
            return self._empty_response()
        
        # Check cache
        cache_key = f"{symbol}_{time_from}_{time_to}_{limit}"
        if use_cache and cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self.cache_duration:
                logger.debug(f"Using cached news sentiment for {symbol}")
                return cached_data
        
        # Build API request
        params = self._build_request_params(currencies, time_from, time_to, limit)
        
        try:
            # Make API request with rate limiting
            self._rate_limiter.wait_if_needed()
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Process the response
            processed_data = self._process_news_data(data, symbol)
            
            # Cache the result
            if use_cache:
                self._cache[cache_key] = (processed_data, time.time())
            
            return processed_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching news sentiment: {e}")
            return self._empty_response()
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing API response: {e}")
            return self._empty_response()
    
    def get_market_sentiment(
        self,
        symbols: List[str],
        time_window_hours: int = 24
    ) -> Dict[str, Dict]:
        """Get aggregated market sentiment for multiple forex pairs.
        
        Args:
            symbols: List of forex symbols
            time_window_hours: Time window in hours
            
        Returns:
            Dictionary mapping symbols to sentiment data
        """
        results = {}
        time_from = datetime.now() - timedelta(hours=time_window_hours)
        
        for symbol in symbols:
            sentiment = self.get_forex_sentiment(
                symbol=symbol,
                time_from=time_from,
                limit=100
            )
            results[symbol] = sentiment
        
        return results
    
    def _parse_forex_symbol(self, symbol: str) -> List[str]:
        """Parse forex symbol to extract currencies.
        
        Args:
            symbol: Forex pair (e.g., 'EURUSD')
            
        Returns:
            List of currency codes
        """
        if len(symbol) != 6:
            return []
        
        base = symbol[:3]
        quote = symbol[3:]
        
        if base in self.FOREX_TICKERS and quote in self.FOREX_TICKERS:
            return [base, quote]
        
        return []
    
    def _build_request_params(
        self,
        currencies: List[str],
        time_from: Optional[datetime],
        time_to: Optional[datetime],
        limit: int
    ) -> Dict:
        """Build API request parameters.
        
        Args:
            currencies: List of currency codes
            time_from: Start time
            time_to: End time
            limit: Number of articles
            
        Returns:
            Request parameters dictionary
        """
        # Build tickers list
        tickers = ','.join([self.FOREX_TICKERS[curr] for curr in currencies])
        
        params = {
            'function': 'NEWS_SENTIMENT',
            'tickers': tickers,
            'apikey': self.api_key,
            'limit': min(limit, 1000),  # API max is 1000
            'sort': 'LATEST'
        }
        
        # Note: topics parameter doesn't seem to filter results effectively
        # We'll filter in post-processing instead
        
        # Add time filters
        if time_from:
            params['time_from'] = time_from.strftime('%Y%m%dT%H%M')
        
        if time_to:
            params['time_to'] = time_to.strftime('%Y%m%dT%H%M')
        
        return params
    
    def _process_news_data(self, raw_data: Dict, symbol: str) -> Dict:
        """Process raw news data from API.
        
        Args:
            raw_data: Raw API response
            symbol: Original forex symbol
            
        Returns:
            Processed sentiment data
        """
        # Check for API errors
        if 'Error Message' in raw_data:
            logger.error(f"API Error: {raw_data['Error Message']}")
            return self._empty_response()
        
        if 'Information' in raw_data:
            logger.warning(f"API Info: {raw_data['Information']}")
            return self._empty_response()
        
        # Extract feed data
        feed = raw_data.get('feed', [])
        if not feed:
            return self._empty_response()
        
        # Get the currencies we're looking for
        currencies = self._parse_forex_symbol(symbol)
        target_tickers = set([self.FOREX_TICKERS[curr] for curr in currencies])
        
        # Calculate aggregate sentiment
        sentiments = []
        relevances = []
        article_details = []
        processed_articles = set()  # Track processed articles to avoid duplicates
        
        for article in feed:
            # Extract ticker sentiment for our currencies
            ticker_sentiments = article.get('ticker_sentiment', [])
            
            # Check if this article mentions any of our target tickers
            relevant_sentiments = []
            for ts in ticker_sentiments:
                ticker = ts.get('ticker', '')
                if ticker in target_tickers:
                    sentiment_score = float(ts.get('ticker_sentiment_score', 0))
                    relevance_score = float(ts.get('relevance_score', 0))
                    relevant_sentiments.append({
                        'ticker': ticker,
                        'sentiment': sentiment_score,
                        'relevance': relevance_score
                    })
            
            # If article mentions our currencies, process it
            if relevant_sentiments and article['title'] not in processed_articles:
                processed_articles.add(article['title'])
                
                # Average sentiment across mentioned currencies
                avg_sentiment = sum(s['sentiment'] for s in relevant_sentiments) / len(relevant_sentiments)
                avg_relevance = sum(s['relevance'] for s in relevant_sentiments) / len(relevant_sentiments)
                
                sentiments.append(avg_sentiment)
                relevances.append(avg_relevance)
                
                # Store article details
                article_details.append({
                    'title': article.get('title', ''),
                    'url': article.get('url', ''),
                    'time_published': article.get('time_published', ''),
                    'summary': article.get('summary', '')[:200] + '...' if len(article.get('summary', '')) > 200 else article.get('summary', ''),
                    'source': article.get('source', ''),
                    'sentiment_score': avg_sentiment,
                    'relevance_score': avg_relevance,
                    'overall_sentiment_label': article.get('overall_sentiment_label', ''),
                    'tickers_mentioned': [s['ticker'] for s in relevant_sentiments]
                })
        
        # Calculate aggregated metrics
        if sentiments:
            avg_sentiment = sum(sentiments) / len(sentiments)
            avg_relevance = sum(relevances) / len(relevances)
            
            # Weight sentiment by relevance
            weighted_sentiments = [s * r for s, r in zip(sentiments, relevances)]
            weighted_avg = sum(weighted_sentiments) / sum(relevances) if sum(relevances) > 0 else 0
            
            # Count sentiment distribution
            bullish_count = sum(1 for s in sentiments if s > 0.1)
            bearish_count = sum(1 for s in sentiments if s < -0.1)
            neutral_count = len(sentiments) - bullish_count - bearish_count
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'overall_sentiment': weighted_avg,
                'sentiment_score': avg_sentiment,
                'relevance_score': avg_relevance,
                'article_count': len(sentiments),
                'bullish_count': bullish_count,
                'bearish_count': bearish_count,
                'neutral_count': neutral_count,
                'sentiment_label': self._get_sentiment_label(weighted_avg),
                'articles': article_details[:10],  # Top 10 most relevant
                'raw_sentiments': sentiments,
                'raw_relevances': relevances
            }
        else:
            return self._empty_response()
    
    def _get_sentiment_label(self, score: float) -> str:
        """Convert sentiment score to label.
        
        Args:
            score: Sentiment score (-1 to 1)
            
        Returns:
            Sentiment label
        """
        if score >= 0.15:
            return 'Bullish'
        elif score <= -0.15:
            return 'Bearish'
        else:
            return 'Neutral'
    
    def _empty_response(self) -> Dict:
        """Return empty response structure."""
        return {
            'overall_sentiment': 0.0,
            'sentiment_score': 0.0,
            'relevance_score': 0.0,
            'article_count': 0,
            'bullish_count': 0,
            'bearish_count': 0,
            'neutral_count': 0,
            'sentiment_label': 'Neutral',
            'articles': []
        }


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls_per_minute: int):
        """Initialize rate limiter.
        
        Args:
            calls_per_minute: Maximum calls per minute
        """
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call_time = 0
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        
        if time_since_last_call < self.min_interval:
            sleep_time = self.min_interval - time_since_last_call
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()


# Convenience functions
def get_forex_news_sentiment(
    symbol: str,
    api_key: Optional[str] = None,
    hours_back: int = 24
) -> Dict:
    """Get news sentiment for a forex pair.
    
    Args:
        symbol: Forex pair (e.g., 'EURUSD')
        api_key: Alpha Vantage API key
        hours_back: Number of hours to look back
        
    Returns:
        Sentiment analysis results
    """
    api = AlphaVantageNewsAPI(api_key)
    time_from = datetime.now() - timedelta(hours=hours_back)
    
    return api.get_forex_sentiment(
        symbol=symbol,
        time_from=time_from,
        limit=100
    )


def analyze_market_sentiment(
    symbols: List[str],
    api_key: Optional[str] = None
) -> pd.DataFrame:
    """Analyze market sentiment across multiple forex pairs.
    
    Args:
        symbols: List of forex symbols
        api_key: Alpha Vantage API key
        
    Returns:
        DataFrame with sentiment analysis
    """
    api = AlphaVantageNewsAPI(api_key)
    results = api.get_market_sentiment(symbols)
    
    # Convert to DataFrame
    data = []
    for symbol, sentiment in results.items():
        data.append({
            'symbol': symbol,
            'sentiment': sentiment['overall_sentiment'],
            'relevance': sentiment['relevance_score'],
            'articles': sentiment['article_count'],
            'label': sentiment['sentiment_label']
        })
    
    return pd.DataFrame(data)