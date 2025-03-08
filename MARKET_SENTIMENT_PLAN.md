# Market Sentiment Analysis Subsystem Plan

## Overview

The market sentiment analysis subsystem will extract and analyze news and social media data to generate sentiment signals that can be integrated with Elliott Wave analysis. This will provide additional context and validation for wave patterns by correlating them with market sentiment.

## Architecture

The market sentiment analysis subsystem will follow these components:

1. **Data Collection Layer**:
   - Yahoo Finance News API integration
   - Interactive Brokers (IBKR) News API integration
   - Alternative data sources (Twitter/X, Reddit, Financial blogs)

2. **Data Processing Layer**:
   - Text extraction and cleaning
   - Entity recognition (companies, currencies, economic indicators)
   - Temporal analysis (connecting news to specific timeframes)

3. **Sentiment Analysis Layer**:
   - LLM-based sentiment scoring
   - Named entity sentiment extraction
   - Visualization of sentiment trends

4. **Integration Layer**:
   - Correlation with Elliott Wave patterns
   - Sentiment-based pattern validation
   - Enhanced trading signals

## Implementation Details

### 1. News Data Collection

#### Yahoo Finance Integration
- Use Yahoo Finance API to fetch news articles related to specific currencies/pairs
- Implement rate limiting and caching to avoid API throttling
- Extract article metadata (publication date, source, title, summary)

```python
def fetch_yahoo_finance_news(symbol: str, days_back: int = 7) -> List[Dict]:
    """Fetch news for a given symbol from Yahoo Finance.
    
    Args:
        symbol: The currency pair or ticker symbol
        days_back: Number of days to look back
        
    Returns:
        List of news articles with metadata
    """
    # Implementation details will follow Yahoo Finance API requirements
```

#### Interactive Brokers Integration
- Connect to IBKR API using the ib_insync library
- Request news bulletins and articles for relevant currency pairs
- Store news data with proper timestamps for historical analysis

```python
def fetch_ibkr_news(symbol: str, days_back: int = 7) -> List[Dict]:
    """Fetch news for a given symbol from Interactive Brokers.
    
    Args:
        symbol: The currency pair or ticker symbol
        days_back: Number of days to look back
        
    Returns:
        List of news articles with metadata
    """
    # Implementation will use ib_insync library to connect to IBKR API
```

### 2. Sentiment Analysis Engine

#### Preprocessing Pipeline
- Clean and normalize text data
- Remove HTML, special characters, and formatting
- Segment articles into meaningful chunks for analysis

#### LLM-Based Sentiment Analysis
- Use OpenAI API to extract sentiment from news articles
- Create custom prompts to analyze financial news specifically for:
  - Overall sentiment (bullish, bearish, neutral)
  - Sentiment intensity (1-10 scale)
  - Temporal orientation (short-term vs. long-term impact)
  - Relevance to specific wave patterns

```python
def analyze_sentiment(text: str, currency_pair: str) -> Dict:
    """Analyze sentiment of news text for a currency pair.
    
    Args:
        text: News article text
        currency_pair: The currency pair (e.g., "EURUSD")
        
    Returns:
        Dictionary with sentiment analysis results
    """
    prompt = f"""
    Analyze the sentiment of this news article related to {currency_pair}:
    
    {text}
    
    Provide the following:
    1. Overall sentiment: bullish, bearish, or neutral
    2. Sentiment intensity (1-10 scale)
    3. Temporal relevance: immediate, short-term, medium-term, long-term
    4. Key factors driving sentiment
    5. Potential impact on {currency_pair} price movement
    
    Format your response as JSON.
    """
    
    # Use LLM client to get sentiment analysis
    analysis_json = llm_client.generate_text(prompt=prompt, temperature=0.1)
    return json.loads(analysis_json)
```

### 3. Time Series Sentiment Aggregation

- Aggregate sentiment scores over time to create sentiment trends
- Apply weighting based on source reputation and recency
- Create sentiment indicators for different timeframes

```python
def create_sentiment_timeseries(
    sentiment_data: List[Dict],
    timeframe: str = "daily"
) -> pd.DataFrame:
    """Create a time series of sentiment data.
    
    Args:
        sentiment_data: List of sentiment analysis results with timestamps
        timeframe: Timeframe for aggregation (hourly, daily, weekly)
        
    Returns:
        DataFrame with sentiment aggregated by timeframe
    """
    # Implementation details for time series aggregation
```

### 4. Elliott Wave Integration

- Correlate sentiment shifts with wave patterns
- Use sentiment to validate wave counts and potential reversal points
- Create sentiment-augmented Elliott Wave predictions

```python
def validate_wave_with_sentiment(
    wave_pattern: Dict,
    sentiment_data: pd.DataFrame
) -> Dict:
    """Validate an Elliott Wave pattern using sentiment data.
    
    Args:
        wave_pattern: Dictionary containing Elliott Wave pattern data
        sentiment_data: Time series sentiment data
        
    Returns:
        Dictionary with validation results and confidence scores
    """
    # Implementation for sentiment-based validation
```

## Integration with Agent Framework

The sentiment analysis will integrate with the existing multi-agent framework as follows:

1. **SentimentAgent Class**:
   - Create a new agent type that specializes in sentiment analysis
   - Implement methods for retrieving and analyzing news sentiment
   - Enable integration with WaveDetectionAgent for pattern validation

2. **Agent Coordination**:
   - Update AgentCoordinator to incorporate sentiment data in workflows
   - Create parallel tasks for sentiment analysis alongside wave detection
   - Use sentiment to adjust confidence scores for wave patterns

3. **RAG Enhancement**:
   - Add sentiment-related knowledge to the RAG system
   - Enable context augmentation with recent sentiment data
   - Create prompts that incorporate both Elliott Wave principles and sentiment signals

## Implementation Timeline

1. **Week 1**: Data collection infrastructure
   - Implement Yahoo Finance API integration
   - Set up IBKR connection
   - Create data storage and caching mechanism

2. **Week 2**: Sentiment analysis engine
   - Develop text preprocessing pipeline
   - Create LLM-based sentiment extraction
   - Build sentiment aggregation module

3. **Week 3**: Elliott Wave integration
   - Develop sentiment-wave correlation methods
   - Create validation enhancement using sentiment
   - Build visualization for sentiment-augmented waves

4. **Week 4**: Multi-agent integration
   - Implement SentimentAgent class
   - Update agent coordination workflows
   - Create test suite for sentiment-enhanced analysis

## Technical Requirements

1. **Dependencies**:
   - `yfinance` for Yahoo Finance API integration
   - `ib_insync` for Interactive Brokers API
   - `pandas` for time series analysis
   - `plotly` for sentiment visualization

2. **API Configuration**:
   - Yahoo Finance API (free tier usage)
   - IBKR API (requires valid account credentials)
   - OpenAI API for sentiment analysis

3. **Performance Considerations**:
   - Implement proper caching for news data
   - Batch sentiment analysis requests to minimize API costs
   - Optimize storage for long-term sentiment trends

## Validation Strategy

1. **Unit Tests**:
   - Test data fetching mechanisms with mock responses
   - Validate sentiment analysis functions with known test cases
   - Ensure time series aggregation logic is correct

2. **Integration Tests**:
   - Verify sentiment data flows correctly to wave detection
   - Test end-to-end workflow with sample market data
   - Validate visualizations and reports

3. **Benchmark Cases**:
   - Use historical events with known sentiment impacts
   - Compare automated analysis with manual sentiment assessment
   - Measure correlation with actual market movements

## Future Enhancements

1. **Additional Data Sources**:
   - Integration with social media APIs (Twitter/X, Reddit)
   - Financial blogs and analyst reports
   - Economic calendar events

2. **Advanced Sentiment Analysis**:
   - Fine-tuned models for financial sentiment
   - Entity-specific sentiment (e.g., central banks, specific countries)
   - Comparative sentiment across markets

3. **Predictive Analytics**:
   - Building sentiment-based predictive models
   - Correlation with Elliott Wave success rates
   - Reinforcement learning integration