"""Multi-source sentiment aggregation for comprehensive market sentiment analysis."""

import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import feedparser
from bs4 import BeautifulSoup

from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class MultiSourceSentimentAggregator:
    """Aggregate sentiment from multiple news and social media sources."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the sentiment aggregator.

        Args:
            config: Configuration with API keys and settings
        """
        self.config = config or {}
        self.llm_client = LLMClient()

        # API configurations
        self.news_api_key = os.getenv("NEWS_API_KEY")
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.finnhub_key = os.getenv("FINNHUB_API_KEY")

        # Source weights for aggregation
        self.source_weights = {
            "reuters": 0.25,
            "bloomberg": 0.25,
            "yahoo_finance": 0.15,
            "marketwatch": 0.15,
            "forex_factory": 0.10,
            "dailyfx": 0.10,
        }

        # Cache for API responses
        self.cache = {}
        self.cache_duration = timedelta(minutes=15)

    async def get_aggregated_sentiment(
        self, symbol: str, lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """Get aggregated sentiment from all sources.

        Args:
            symbol: Trading symbol (e.g., 'GBPUSD')
            lookback_hours: Hours to look back for news

        Returns:
            Aggregated sentiment analysis
        """
        # Collect from all sources concurrently
        sources_tasks = [
            self._get_reuters_sentiment(symbol, lookback_hours),
            self._get_yahoo_finance_sentiment(symbol, lookback_hours),
            self._get_marketwatch_sentiment(symbol, lookback_hours),
            self._get_forex_factory_sentiment(symbol),
            self._get_dailyfx_sentiment(symbol),
            (
                self._get_alpha_vantage_sentiment(symbol)
                if self.alpha_vantage_key
                else None
            ),
            self._get_finnhub_sentiment(symbol) if self.finnhub_key else None,
        ]

        # Filter out None tasks
        sources_tasks = [task for task in sources_tasks if task is not None]

        # Gather results
        results = await asyncio.gather(*sources_tasks, return_exceptions=True)

        # Process results
        sentiment_scores = []
        source_sentiments = {}
        all_articles = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error getting sentiment from source {i}: {result}")
                continue

            if result and "sentiment_score" in result:
                source_name = result.get("source", f"source_{i}")
                source_sentiments[source_name] = result

                # Weight the sentiment score
                weight = self.source_weights.get(source_name, 0.1)
                sentiment_scores.append(
                    {
                        "score": result["sentiment_score"],
                        "weight": weight,
                        "confidence": result.get("confidence", 0.5),
                    }
                )

                # Collect articles
                if "articles" in result:
                    all_articles.extend(result["articles"])

        # Calculate weighted sentiment
        if sentiment_scores:
            total_weight = sum(s["weight"] * s["confidence"] for s in sentiment_scores)
            weighted_sentiment = (
                sum(
                    s["score"] * s["weight"] * s["confidence"] for s in sentiment_scores
                )
                / total_weight
                if total_weight > 0
                else 0
            )
        else:
            weighted_sentiment = 0

        # Get LLM consensus
        llm_consensus = await self._get_llm_consensus(source_sentiments, symbol)

        # Determine sentiment category
        if weighted_sentiment > 0.3:
            sentiment_category = "bullish"
        elif weighted_sentiment < -0.3:
            sentiment_category = "bearish"
        else:
            sentiment_category = "neutral"

        return {
            "symbol": symbol,
            "timestamp": datetime.now(),
            "aggregated_sentiment_score": weighted_sentiment,
            "sentiment_category": sentiment_category,
            "confidence": (
                np.mean([s["confidence"] for s in sentiment_scores])
                if sentiment_scores
                else 0.3
            ),
            "source_sentiments": source_sentiments,
            "llm_consensus": llm_consensus,
            "total_articles": len(all_articles),
            "recent_headlines": [
                a["title"]
                for a in sorted(
                    all_articles,
                    key=lambda x: x.get("timestamp", datetime.now()),
                    reverse=True,
                )[:10]
            ],
            "sentiment_distribution": self._calculate_distribution(sentiment_scores),
        }

    async def _get_reuters_sentiment(
        self, symbol: str, lookback_hours: int
    ) -> Dict[str, Any]:
        """Get sentiment from Reuters RSS feeds."""
        try:
            # Reuters RSS feeds
            feeds = [
                "https://www.reutersagency.com/feed/?best-topics=forex&post_type=best",
                "https://www.reutersagency.com/feed/?best-topics=economic-indicators&post_type=best",
            ]

            articles = []
            for feed_url in feeds:
                feed = await self._fetch_rss_feed(feed_url)
                if feed and feed.entries:
                    for entry in feed.entries[:10]:
                        # Check if relevant to symbol
                        if self._is_relevant_to_symbol(
                            entry.title + entry.get("summary", ""), symbol
                        ):
                            articles.append(
                                {
                                    "title": entry.title,
                                    "summary": entry.get("summary", ""),
                                    "url": entry.link,
                                    "timestamp": datetime.fromtimestamp(
                                        entry.published_parsed
                                    ),
                                    "source": "reuters",
                                }
                            )

            # Analyze sentiment
            if articles:
                sentiment_score = await self._analyze_articles_sentiment(
                    articles, symbol
                )
                return {
                    "source": "reuters",
                    "sentiment_score": sentiment_score,
                    "confidence": 0.8,
                    "articles": articles,
                }

            return None

        except Exception as e:
            logger.error(f"Error getting Reuters sentiment: {e}")
            return None

    async def _get_yahoo_finance_sentiment(
        self, symbol: str, lookback_hours: int
    ) -> Dict[str, Any]:
        """Get sentiment from Yahoo Finance."""
        try:
            # Convert forex symbol to Yahoo format
            yahoo_symbol = f"{symbol[:3]}{symbol[3:]}=X"

            url = f"https://finance.yahoo.com/quote/{yahoo_symbol}/news"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")

                        articles = []
                        # Parse news items (simplified - would need proper selectors)
                        news_items = soup.find_all("div", {"class": "news-item"})[:10]

                        for item in news_items:
                            title = item.find("h3")
                            if title:
                                articles.append(
                                    {"title": title.text, "source": "yahoo_finance"}
                                )

                        if articles:
                            sentiment_score = await self._analyze_articles_sentiment(
                                articles, symbol
                            )
                            return {
                                "source": "yahoo_finance",
                                "sentiment_score": sentiment_score,
                                "confidence": 0.7,
                                "articles": articles,
                            }

            return None

        except Exception as e:
            logger.error(f"Error getting Yahoo Finance sentiment: {e}")
            return None

    async def _get_marketwatch_sentiment(
        self, symbol: str, lookback_hours: int
    ) -> Dict[str, Any]:
        """Get sentiment from MarketWatch."""
        try:
            # MarketWatch RSS for currencies
            feed_url = "https://feeds.marketwatch.com/marketwatch/marketpulse/"

            feed = await self._fetch_rss_feed(feed_url)
            if feed and feed.entries:
                articles = []
                for entry in feed.entries[:15]:
                    if self._is_relevant_to_symbol(
                        entry.title + entry.get("summary", ""), symbol
                    ):
                        articles.append(
                            {
                                "title": entry.title,
                                "summary": entry.get("summary", ""),
                                "source": "marketwatch",
                            }
                        )

                if articles:
                    sentiment_score = await self._analyze_articles_sentiment(
                        articles, symbol
                    )
                    return {
                        "source": "marketwatch",
                        "sentiment_score": sentiment_score,
                        "confidence": 0.7,
                        "articles": articles,
                    }

            return None

        except Exception as e:
            logger.error(f"Error getting MarketWatch sentiment: {e}")
            return None

    async def _get_forex_factory_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Get sentiment from Forex Factory calendar and analysis."""
        try:
            # This would require web scraping or API access
            # For now, return placeholder
            base_currency = symbol[:3]
            quote_currency = symbol[3:6]

            # Simulate getting economic calendar sentiment
            prompt = f"""Based on current economic calendar and central bank stance,
            what is the sentiment for {base_currency} vs {quote_currency}?

            Consider recent economic data, central bank policies, and market positioning.

            Respond with a JSON object containing:
            - sentiment_score: -1 to 1
            - key_factors: list of main drivers
            - confidence: 0-1"""

            response = await self.llm_client.generate_text_async(prompt)

            try:
                analysis = json.loads(response)
                return {
                    "source": "forex_factory",
                    "sentiment_score": analysis.get("sentiment_score", 0),
                    "confidence": analysis.get("confidence", 0.5),
                    "key_factors": analysis.get("key_factors", []),
                }
            except:
                return None

        except Exception as e:
            logger.error(f"Error getting Forex Factory sentiment: {e}")
            return None

    async def _get_dailyfx_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Get sentiment from DailyFX analysis."""
        try:
            # DailyFX RSS feed
            feed_url = "https://www.dailyfx.com/feeds/market-news"

            feed = await self._fetch_rss_feed(feed_url)
            if feed and feed.entries:
                articles = []
                for entry in feed.entries[:10]:
                    if self._is_relevant_to_symbol(entry.title, symbol):
                        articles.append(
                            {
                                "title": entry.title,
                                "url": entry.link,
                                "source": "dailyfx",
                            }
                        )

                if articles:
                    sentiment_score = await self._analyze_articles_sentiment(
                        articles, symbol
                    )
                    return {
                        "source": "dailyfx",
                        "sentiment_score": sentiment_score,
                        "confidence": 0.7,
                        "articles": articles,
                    }

            return None

        except Exception as e:
            logger.error(f"Error getting DailyFX sentiment: {e}")
            return None

    async def _get_alpha_vantage_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Get sentiment from Alpha Vantage News Sentiment API."""
        if not self.alpha_vantage_key:
            return None

        try:
            # Convert symbol format
            tickers = f"{symbol[:3]},{symbol[3:6]}"

            url = f"https://www.alphavantage.co/query"
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": tickers,
                "apikey": self.alpha_vantage_key,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if "feed" in data:
                            articles = []
                            sentiment_scores = []

                            for item in data["feed"][:10]:
                                articles.append(
                                    {
                                        "title": item.get("title"),
                                        "source": "alpha_vantage",
                                    }
                                )

                                # Get ticker sentiment
                                for ticker_sentiment in item.get(
                                    "ticker_sentiment", []
                                ):
                                    if ticker_sentiment["ticker"] in tickers:
                                        score = float(
                                            ticker_sentiment.get(
                                                "ticker_sentiment_score", 0
                                            )
                                        )
                                        sentiment_scores.append(score)

                            if sentiment_scores:
                                avg_sentiment = np.mean(sentiment_scores)
                                return {
                                    "source": "alpha_vantage",
                                    "sentiment_score": avg_sentiment,
                                    "confidence": 0.8,
                                    "articles": articles,
                                }

            return None

        except Exception as e:
            logger.error(f"Error getting Alpha Vantage sentiment: {e}")
            return None

    async def _get_finnhub_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Get sentiment from Finnhub News API."""
        if not self.finnhub_key:
            return None

        try:
            # Finnhub uses different symbol format
            finnhub_symbol = f"OANDA:{symbol[:3]}_{symbol[3:6]}"

            url = "https://finnhub.io/api/v1/news"
            params = {"category": "forex", "token": self.finnhub_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        news_items = await response.json()

                        articles = []
                        for item in news_items[:10]:
                            if self._is_relevant_to_symbol(
                                item.get("headline", ""), symbol
                            ):
                                articles.append(
                                    {
                                        "title": item.get("headline"),
                                        "summary": item.get("summary"),
                                        "source": "finnhub",
                                        "url": item.get("url"),
                                    }
                                )

                        if articles:
                            sentiment_score = await self._analyze_articles_sentiment(
                                articles, symbol
                            )
                            return {
                                "source": "finnhub",
                                "sentiment_score": sentiment_score,
                                "confidence": 0.7,
                                "articles": articles,
                            }

            return None

        except Exception as e:
            logger.error(f"Error getting Finnhub sentiment: {e}")
            return None

    async def _fetch_rss_feed(self, url: str) -> Optional[Any]:
        """Fetch and parse RSS feed."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        return feedparser.parse(content)
            return None
        except Exception as e:
            logger.error(f"Error fetching RSS feed {url}: {e}")
            return None

    def _is_relevant_to_symbol(self, text: str, symbol: str) -> bool:
        """Check if text is relevant to the trading symbol."""
        text_lower = text.lower()

        # Currency names
        currency_names = {
            "EUR": ["euro", "eur", "european", "ecb"],
            "USD": ["dollar", "usd", "federal reserve", "fed", "fomc"],
            "GBP": ["pound", "gbp", "sterling", "bank of england", "boe"],
            "JPY": ["yen", "jpy", "bank of japan", "boj"],
            "CHF": ["franc", "chf", "swiss", "snb"],
            "AUD": ["aussie", "aud", "australian dollar", "rba"],
            "CAD": ["canadian", "cad", "loonie", "bank of canada"],
            "NZD": ["kiwi", "nzd", "new zealand", "rbnz"],
        }

        base_currency = symbol[:3]
        quote_currency = symbol[3:6]

        # Check for currency mentions
        base_keywords = currency_names.get(base_currency, [base_currency.lower()])
        quote_keywords = currency_names.get(quote_currency, [quote_currency.lower()])

        base_mentioned = any(keyword in text_lower for keyword in base_keywords)
        quote_mentioned = any(keyword in text_lower for keyword in quote_keywords)

        # Also check for the pair itself
        pair_mentioned = (
            symbol.lower() in text_lower
            or f"{base_currency}/{quote_currency}".lower() in text_lower
        )

        return pair_mentioned or (base_mentioned and quote_mentioned) or base_mentioned

    async def _analyze_articles_sentiment(
        self, articles: List[Dict], symbol: str
    ) -> float:
        """Analyze sentiment of articles using LLM."""
        if not articles:
            return 0.0

        # Prepare article text
        article_text = "\n".join(
            [
                f"- {article['title']}: {article.get('summary', '')}"
                for article in articles[:10]
            ]
        )

        prompt = f"""Analyze the sentiment of these news articles for {symbol} trading:

{article_text}

Rate the overall sentiment on a scale from -1 (very bearish) to +1 (very bullish).
Consider both direct mentions and implied impact on the currency pair.

Respond with just a number between -1 and 1."""

        try:
            response = await self.llm_client.generate_text_async(prompt)
            sentiment = float(response.strip())
            return max(-1, min(1, sentiment))  # Ensure within bounds
        except:
            return 0.0

    async def _get_llm_consensus(
        self, source_sentiments: Dict[str, Any], symbol: str
    ) -> Dict[str, Any]:
        """Get LLM consensus analysis of all sources."""
        if not source_sentiments:
            return {"consensus": "insufficient_data", "confidence": 0.0}

        # Prepare source summary
        source_summary = "\n".join(
            [
                f"{source}: {data.get('sentiment_score', 0):.2f} "
                f"(confidence: {data.get('confidence', 0):.1%})"
                for source, data in source_sentiments.items()
            ]
        )

        prompt = f"""Analyze the sentiment consensus for {symbol} from multiple sources:

{source_summary}

Key headlines from various sources indicate market themes.

Provide a JSON response with:
1. consensus_sentiment: "bullish", "bearish", or "mixed"
2. confidence_level: 0-1 score
3. key_divergences: list of any major disagreements between sources
4. market_narrative: brief summary of overall market story
5. trading_implication: specific implication for {symbol} trading"""

        try:
            response = await self.llm_client.generate_text_async(prompt)
            return json.loads(response)
        except:
            return {
                "consensus_sentiment": "mixed",
                "confidence_level": 0.5,
                "error": "Failed to generate consensus",
            }

    def _calculate_distribution(self, sentiment_scores: List[Dict]) -> Dict[str, float]:
        """Calculate sentiment distribution."""
        if not sentiment_scores:
            return {"bullish": 0.33, "neutral": 0.34, "bearish": 0.33}

        bullish = sum(1 for s in sentiment_scores if s["score"] > 0.3)
        bearish = sum(1 for s in sentiment_scores if s["score"] < -0.3)
        neutral = len(sentiment_scores) - bullish - bearish

        total = len(sentiment_scores)

        return {
            "bullish": bullish / total,
            "neutral": neutral / total,
            "bearish": bearish / total,
        }


# Add numpy import at the top
import numpy as np
