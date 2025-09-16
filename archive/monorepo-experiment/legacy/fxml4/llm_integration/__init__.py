"""LLM integration package for FXML4.

This package provides integration with Large Language Models (LLMs) for
market analysis, pattern validation, and trading strategy enhancement.

Features:
1. Retrieval-Augmented Generation (RAG) for Elliott Wave analysis
2. Sentiment analysis for news and market data
3. Vector storage for knowledge base management
4. LLM client for interacting with different providers
"""

# Import key components
try:
    from fxml4.llm_integration.sentiment_analysis import SentimentAnalyzer, MarketSentimentAnalyzer
except ImportError:
    pass  # Module might not be available yet