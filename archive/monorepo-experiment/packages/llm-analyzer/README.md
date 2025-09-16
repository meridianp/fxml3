# FXML4 LLM Analyzer

Large Language Model integration for advanced market analysis.

## Features

- Multi-provider LLM support (OpenAI, Anthropic)
- Elliott Wave pattern analysis with LLM
- Market sentiment analysis
- Technical analysis narrative generation
- RAG system for trading knowledge
- Async API support

## Installation

```bash
poetry install
```

## Configuration

Set the following environment variables:

```bash
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
PINECONE_API_KEY=your_pinecone_key
PINECONE_ENVIRONMENT=your_pinecone_env
```

## Usage

```python
from fxml4_llm import LLMClient, MarketAnalyzer, SentimentAnalyzer

# Create LLM client
llm = LLMClient(provider="openai", model="gpt-4")

# Analyze market conditions
analyzer = MarketAnalyzer(llm)
analysis = await analyzer.analyze_market(
    symbol="EURUSD",
    timeframe="4H",
    technical_data=technical_indicators,
    news_data=recent_news
)

# Analyze sentiment
sentiment = SentimentAnalyzer(llm)
sentiment_score = await sentiment.analyze_text(news_article)
```

## Components

### LLM Client
- Unified interface for multiple LLM providers
- Automatic retry and rate limiting
- Token counting and cost tracking

### Market Analyzer
- Technical analysis interpretation
- Elliott Wave pattern description
- Market condition assessment
- Trade recommendation generation

### Sentiment Analyzer
- News sentiment scoring
- Social media analysis
- Market mood detection
- Event impact assessment

### RAG System
- Trading knowledge base
- Pattern matching with context
- Historical precedent retrieval

## Development

```bash
# Run tests
poetry run pytest

# Format code
poetry run black src tests
poetry run isort src tests

# Type checking
poetry run mypy src
```