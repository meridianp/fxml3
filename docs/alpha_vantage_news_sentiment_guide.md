# Alpha Vantage NEWS_SENTIMENT API Integration Guide

## Overview

This guide documents the implementation of Alpha Vantage's NEWS_SENTIMENT API for forex trading sentiment analysis. The integration provides real-time news sentiment data to enhance trading decisions by incorporating market sentiment into signal generation.

## Features

### 1. Real-Time News Sentiment Analysis
- Fetches news articles mentioning specific forex currencies
- Analyzes sentiment scores for each currency pair
- Weights sentiment by article relevance
- Provides bullish/bearish/neutral classifications

### 2. Multi-Currency Support
- Supports all major forex pairs (EUR, USD, GBP, JPY, CHF, AUD, NZD, CAD)
- Filters news by specific currency mentions
- Aggregates sentiment across multiple sources

### 3. Intelligent Caching
- Reduces API calls with smart caching
- Configurable cache duration (default: 1 hour)
- Automatic cache invalidation

### 4. Rate Limiting
- Built-in rate limiter for API compliance
- Supports both free (5 calls/min) and premium (75 calls/min) tiers
- Automatic request throttling

## Installation

### Prerequisites
```bash
# Required packages
pip install requests pandas python-dotenv

# Environment variable
export ALPHA_VANTAGE_API_KEY="your_api_key_here"
```

### File Structure
```
fxml4/
├── fxml4/
│   └── data_engineering/
│       └── data_feeds/
│           └── alpha_vantage_news.py  # Main implementation
├── scripts/
│   ├── enhanced_production_system_v2.py  # Updated to use real API
│   └── test_news_sentiment_integration.py  # Integration tests
└── tests/
    └── unit/
        └── test_alpha_vantage_news.py  # Unit tests
```

## Configuration

### Basic Setup
```python
from fxml4.data_engineering.data_feeds.alpha_vantage_news import AlphaVantageNewsAPI

# Initialize with API key
api = AlphaVantageNewsAPI(api_key='your_key')

# Or use environment variable
api = AlphaVantageNewsAPI()  # Uses ALPHA_VANTAGE_API_KEY env var
```

### Cache Configuration
```python
# Custom cache duration (in seconds)
api = AlphaVantageNewsAPI(
    api_key='your_key',
    cache_duration=7200  # 2 hours
)
```

## Usage Examples

### 1. Single Currency Pair Analysis
```python
from fxml4.data_engineering.data_feeds.alpha_vantage_news import get_forex_news_sentiment

# Get sentiment for EURUSD over last 24 hours
sentiment = get_forex_news_sentiment('EURUSD', hours_back=24)

print(f"Overall Sentiment: {sentiment['overall_sentiment']:.3f}")
print(f"Sentiment Label: {sentiment['sentiment_label']}")
print(f"Article Count: {sentiment['article_count']}")
print(f"Bullish: {sentiment['bullish_count']}, Bearish: {sentiment['bearish_count']}")
```

### 2. Multiple Currency Pairs
```python
from fxml4.data_engineering.data_feeds.alpha_vantage_news import analyze_market_sentiment

# Analyze multiple pairs
symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD']
df = analyze_market_sentiment(symbols)

# Display results
print(df)
# Output:
#    symbol  sentiment  relevance  articles       label
# 0  EURUSD      0.250      0.750        15     Bullish
# 1  GBPUSD     -0.150      0.800        12     Neutral
# 2  USDJPY      0.100      0.650         8     Neutral
# 3  AUDUSD     -0.300      0.700        10     Bearish
```

### 3. Time Window Analysis
```python
from datetime import datetime, timedelta
from fxml4.data_engineering.data_feeds.alpha_vantage_news import AlphaVantageNewsAPI

api = AlphaVantageNewsAPI()

# Get sentiment for specific time window
time_from = datetime.now() - timedelta(hours=6)
time_to = datetime.now()

sentiment = api.get_forex_sentiment(
    symbol='EURUSD',
    time_from=time_from,
    time_to=time_to,
    limit=50
)

# Access detailed article information
for article in sentiment['articles'][:5]:
    print(f"Title: {article['title']}")
    print(f"Sentiment: {article['sentiment_score']:.3f}")
    print(f"Source: {article['source']}")
    print("---")
```

### 4. Integration with Trading System
```python
# In enhanced_production_system_v2.py
def get_news_sentiment(self, symbol: str, timestamp: pd.Timestamp) -> Dict:
    """Get news sentiment for a symbol."""
    if not self.enabled:
        return {'sentiment': 0.0, 'relevance': 0.0}

    # Uses real Alpha Vantage NEWS_SENTIMENT API
    from fxml4.data_engineering.data_feeds.alpha_vantage_news import AlphaVantageNewsAPI

    news_api = AlphaVantageNewsAPI(self.api_key)
    sentiment = news_api.get_forex_sentiment(
        symbol=symbol,
        time_from=timestamp - timedelta(hours=24),
        time_to=timestamp,
        limit=50,
        use_cache=True
    )

    return sentiment
```

## API Response Format

### Successful Response
```json
{
    "symbol": "EURUSD",
    "timestamp": "2024-01-15T10:30:00",
    "overall_sentiment": 0.25,
    "sentiment_score": 0.22,
    "relevance_score": 0.75,
    "article_count": 15,
    "bullish_count": 8,
    "bearish_count": 3,
    "neutral_count": 4,
    "sentiment_label": "Bullish",
    "articles": [
        {
            "title": "Fed Signals Potential Rate Cut in 2024",
            "url": "https://example.com/article1",
            "time_published": "20240115T103000",
            "summary": "Federal Reserve officials...",
            "source": "Financial Times",
            "sentiment_score": 0.35,
            "relevance_score": 0.85,
            "overall_sentiment_label": "Bullish"
        }
    ]
}
```

### Empty/Error Response
```json
{
    "overall_sentiment": 0.0,
    "sentiment_score": 0.0,
    "relevance_score": 0.0,
    "article_count": 0,
    "bullish_count": 0,
    "bearish_count": 0,
    "neutral_count": 0,
    "sentiment_label": "Neutral",
    "articles": []
}
```

## Sentiment Interpretation

### Sentiment Scores
- **Range**: -1.0 to 1.0
- **Bullish**: > 0.15
- **Bearish**: < -0.15
- **Neutral**: -0.15 to 0.15

### Trading Integration
```python
# Example: Adjusting signals based on news sentiment
if signal['action'] == 'LONG':
    if news_sentiment['overall_sentiment'] > 0.2:
        # Aligned sentiment - increase confidence
        signal['confidence'] *= 1.2
    elif news_sentiment['overall_sentiment'] < -0.2:
        # Contrary sentiment - block trade
        return None
    else:
        # Neutral sentiment - reduce position size
        signal['position_size'] *= 0.8
```

## Performance Optimization

### 1. Caching Strategy
- Cache duration: 1 hour default (configurable)
- Cache key: `symbol_date_news`
- Automatic cache expiration

### 2. Rate Limiting
- Free tier: 5 calls/minute
- Premium tier: 75 calls/minute
- Automatic throttling to prevent exceeding limits

### 3. Batch Processing
```python
# Efficient multi-symbol processing
api = AlphaVantageNewsAPI()
symbols = ['EURUSD', 'GBPUSD', 'USDJPY']

# Single loop with caching
results = api.get_market_sentiment(symbols, time_window_hours=24)
```

## Error Handling

### Common Errors and Solutions

1. **Invalid API Key**
```python
# Error: {"Error Message": "Invalid API key"}
# Solution: Verify API key is correct and active
```

2. **Rate Limit Exceeded**
```python
# Error: {"Information": "Thank you for using Alpha Vantage..."}
# Solution: Implement rate limiting or upgrade to premium
```

3. **Invalid Symbol**
```python
# Returns empty response with article_count = 0
# Solution: Verify symbol format (6 characters, valid currencies)
```

4. **Network Errors**
```python
# Handled gracefully with empty response
# Solution: Check internet connection, retry with exponential backoff
```

## Testing

### Unit Tests
```bash
# Run unit tests
python -m pytest tests/unit/test_alpha_vantage_news.py -v
```

### Integration Tests
```bash
# Run integration tests (requires API key)
python scripts/test_news_sentiment_integration.py
```

### Test Coverage
- API response parsing
- Error handling
- Caching functionality
- Rate limiting
- Symbol validation
- Sentiment calculation

## Best Practices

### 1. API Key Management
- Store in environment variables
- Never commit to version control
- Use `.env` file for local development

### 2. Error Handling
- Always check for empty responses
- Implement fallback mechanisms
- Log errors for debugging

### 3. Performance
- Use caching to reduce API calls
- Batch requests when possible
- Monitor rate limit usage

### 4. Data Quality
- Filter by relevance score (> 0.5 recommended)
- Consider article count for reliability
- Weight sentiment by relevance

## Troubleshooting

### No Data Returned
1. Check API key is valid
2. Verify symbol format (EURUSD, not EUR/USD)
3. Check time window (max historical data varies)
4. Ensure topics include forex-related terms

### Inconsistent Results
1. News sentiment changes rapidly
2. Use longer time windows for stability
3. Consider averaging multiple time periods
4. Weight by article relevance

### Rate Limiting Issues
1. Implement proper rate limiting
2. Use caching effectively
3. Consider premium tier for production
4. Batch requests efficiently

## Production Deployment

### Environment Setup
```bash
# Production environment variables
export ALPHA_VANTAGE_API_KEY="your_production_key"
export NEWS_CACHE_DURATION=3600  # 1 hour
export NEWS_API_TIER="premium"   # or "free"
```

### Monitoring
- Track API usage against limits
- Monitor cache hit rates
- Log sentiment trends
- Alert on API errors

### Scaling Considerations
- Use Redis for distributed caching
- Implement request queuing
- Consider data persistence
- Plan for API downtime

## Conclusion

The Alpha Vantage NEWS_SENTIMENT API integration provides valuable market sentiment data that enhances trading decisions. By combining technical analysis with news sentiment, the system can make more informed trading decisions and better manage risk during significant market events.

Key benefits:
- Real-time market sentiment analysis
- Currency-specific news filtering
- Intelligent caching and rate limiting
- Seamless integration with existing systems
- Comprehensive error handling

The implementation is production-ready with proper testing, documentation, and error handling in place.
