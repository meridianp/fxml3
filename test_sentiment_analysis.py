#!/usr/bin/env python3
"""Test script for market sentiment analysis module."""

import os
import sys
import json
from pprint import pprint

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fxml3.llm_integration.sentiment_analysis import (
    SentimentAgent, YahooFinanceNewsFetcher, SentimentAnalyzer
)
from fxml3.llm_integration.llm_client import LLMClient


def test_yahoo_news_fetcher():
    """Test the Yahoo Finance news fetcher."""
    print("\n--- Testing Yahoo Finance News Fetcher ---")
    
    # Create news fetcher
    fetcher = YahooFinanceNewsFetcher()
    
    # Test with a currency pair
    symbol = "EURUSD"
    print(f"Fetching news for {symbol}...")
    
    try:
        news = fetcher.fetch_news(symbol, days_back=7, limit=5)
        
        print(f"Found {len(news)} news items.")
        
        if news:
            print("\nSample news item:")
            pprint(news[0])
    except ImportError as e:
        print(f"Import error: {str(e)}")
    except Exception as e:
        print(f"Error: {str(e)}")


def test_sentiment_analyzer():
    """Test the sentiment analyzer."""
    print("\n--- Testing Sentiment Analyzer ---")
    
    # Create sentiment analyzer
    analyzer = SentimentAnalyzer()
    
    # Test with sample news text
    sample_text = """
    The Euro strengthened against the US Dollar on Wednesday after the Federal Reserve
    announced its decision to keep interest rates unchanged. Fed Chair Jerome Powell
    signaled that the central bank is likely to cut rates in the coming months,
    given the cooling inflation data. The EUR/USD pair rose 0.7% to 1.0920, its highest
    level in three weeks. Analysts expect the pair to test the 1.10 level if upcoming 
    economic data from the Eurozone shows improvement.
    """
    
    print("Analyzing sentiment of sample news text...")
    
    try:
        sentiment = analyzer.analyze_sentiment(sample_text, "EUR/USD")
        
        print("\nSentiment analysis results:")
        pprint(sentiment)
    except Exception as e:
        print(f"Error: {str(e)}")


def test_sentiment_agent():
    """Test the sentiment agent."""
    print("\n--- Testing Sentiment Agent ---")
    
    # Create sentiment agent with cache
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "sentiment")
    os.makedirs(cache_dir, exist_ok=True)
    
    agent = SentimentAgent(cache_dir=cache_dir)
    
    # Test with a currency pair
    symbol = "EURUSD"
    print(f"Analyzing market sentiment for {symbol}...")
    
    try:
        sentiment_data = agent.get_market_sentiment(symbol, days_back=3)
        
        print("\nMarket sentiment summary:")
        if sentiment_data.get("status") == "success":
            summary = sentiment_data.get("data", {}).get("sentiment_summary", {})
            pprint(summary)
            
            print(f"\nAnalyzed {sentiment_data.get('data', {}).get('news_count', 0)} news items.")
            
            # Test wave validation
            print("\nValidating sample wave pattern:")
            wave_pattern = {
                "type": "impulse",
                "wave_count": 3,
                "wave1_start": 1.0550,
                "wave1_end": 1.0650,
                "wave2_start": 1.0650,
                "wave2_end": 1.0580,
                "wave3_start": 1.0580,
                "wave3_current": 1.0750,
                "confidence": 0.75,
                "current_price": 1.0750,
            }
            
            validation = agent.validate_wave(wave_pattern, symbol)
            
            print("\nWave validation results:")
            pprint(validation.get("validation", {}))
            
        else:
            print(f"Error: {sentiment_data.get('message', 'Unknown error')}")
    except ImportError as e:
        print(f"Import error: {str(e)}")
    except Exception as e:
        print(f"Error: {str(e)}")


def main():
    """Run the test script."""
    # Test each component
    test_yahoo_news_fetcher()
    test_sentiment_analyzer()
    test_sentiment_agent()


if __name__ == "__main__":
    main()