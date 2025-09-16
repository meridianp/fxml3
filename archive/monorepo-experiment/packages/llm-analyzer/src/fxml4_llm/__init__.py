"""
FXML4 LLM Integration.

This package provides LLM capabilities for advanced market analysis.
"""

from fxml4_llm.client import LLMClient, LLMProvider
from fxml4_llm.market_analyzer import MarketAnalyzer
from fxml4_llm.sentiment import SentimentAnalyzer

__version__ = "0.1.0"
__all__ = ["LLMClient", "LLMProvider", "MarketAnalyzer", "SentimentAnalyzer"]