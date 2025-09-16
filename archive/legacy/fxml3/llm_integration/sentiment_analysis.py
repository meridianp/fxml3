"""Market sentiment analysis for Elliott Wave trading.

This module provides sentiment analysis capabilities for forex markets
by extracting and analyzing news from various sources, including Yahoo Finance
and Interactive Brokers. It integrates with the Elliott Wave analysis system
to provide additional context and validation for wave patterns.
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from dotenv import load_dotenv

from fxml3.llm_integration.llm_client import LLMClient


class NewsFetcher:
    """Base class for fetching financial news from various sources."""
    
    def __init__(self):
        """Initialize the news fetcher."""
        # Load environment variables
        load_dotenv()
        
    def fetch_news(
        self,
        symbol: str,
        days_back: int = 7,
        limit: int = 50,
    ) -> List[Dict]:
        """Fetch news for a symbol or currency pair.
        
        Args:
            symbol: Symbol or currency pair (e.g., "EURUSD")
            days_back: Number of days to look back
            limit: Maximum number of news items to return
            
        Returns:
            List of news items with metadata
        """
        raise NotImplementedError("Subclasses must implement fetch_news")


class YahooFinanceNewsFetcher(NewsFetcher):
    """Fetch news from Yahoo Finance API."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize the Yahoo Finance news fetcher.
        
        Args:
            cache_dir: Directory to cache news data (if None, no caching)
        """
        super().__init__()
        self.cache_dir = cache_dir
        
        # Create cache directory if it doesn't exist
        if self.cache_dir and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def fetch_news(
        self,
        symbol: str,
        days_back: int = 7,
        limit: int = 50,
    ) -> List[Dict]:
        """Fetch news for a symbol from Yahoo Finance.
        
        Args:
            symbol: Stock or forex pair symbol (e.g., "EURUSD=X" for EUR/USD)
            days_back: Number of days to look back
            limit: Maximum number of news items to return
            
        Returns:
            List of news items with metadata
        """
        # Check cache first if enabled
        if self.cache_dir:
            cache_file = os.path.join(
                self.cache_dir,
                f"yahoo_news_{symbol}_{days_back}d_{limit}.json"
            )
            
            # If cache exists and is recent (less than 6 hours old), use it
            if os.path.exists(cache_file):
                file_age = time.time() - os.path.getmtime(cache_file)
                if file_age < 6 * 3600:  # 6 hours
                    try:
                        with open(cache_file, 'r') as f:
                            return json.load(f)
                    except Exception:
                        # If cache read fails, continue to fetch new data
                        pass
        
        try:
            # Import yfinance here to avoid dependency issues
            import yfinance as yf
            
            # Ensure proper symbol format for forex
            if '/' in symbol:
                # Convert EUR/USD to EURUSD=X
                formatted_symbol = symbol.replace('/', '') + '=X'
            elif len(symbol) == 6 and symbol.isalpha():
                # EURUSD to EURUSD=X
                formatted_symbol = symbol + '=X'
            else:
                formatted_symbol = symbol
                
            # Get ticker object
            ticker = yf.Ticker(formatted_symbol)
            
            # Get news
            news_items = ticker.news
            
            # Process and format news
            processed_news = []
            for item in news_items[:limit]:
                # Convert timestamp to datetime
                timestamp = item.get('providerPublishTime', 0)
                pub_date = datetime.fromtimestamp(timestamp)
                
                # Skip news older than days_back
                if pub_date < datetime.now() - timedelta(days=days_back):
                    continue
                
                # Format news item
                processed_item = {
                    'title': item.get('title', ''),
                    'summary': item.get('summary', ''),
                    'publisher': item.get('publisher', ''),
                    'publish_date': pub_date.isoformat(),
                    'url': item.get('link', ''),
                    'source': 'Yahoo Finance',
                    'thumbnail': item.get('thumbnail', {}).get('resolutions', [{}])[0].get('url', '')
                }
                
                processed_news.append(processed_item)
            
            # Cache results if enabled
            if self.cache_dir:
                try:
                    with open(cache_file, 'w') as f:
                        json.dump(processed_news, f)
                except Exception:
                    # Ignore cache write errors
                    pass
                    
            return processed_news
            
        except ImportError:
            raise ImportError(
                "yfinance package not installed. "
                "Install it with: pip install yfinance"
            )
        except Exception as e:
            raise Exception(f"Error fetching news from Yahoo Finance: {str(e)}")


class IBKRNewsFetcher(NewsFetcher):
    """Fetch news from Interactive Brokers API."""
    
    def __init__(
        self,
        client_id: Optional[int] = None,
        host: str = '127.0.0.1',
        port: int = 7496,
        cache_dir: Optional[str] = None,
    ):
        """Initialize the IBKR news fetcher.
        
        Args:
            client_id: Client ID for IBKR connection
            host: Host address for TWS or IB Gateway
            port: Port for TWS or IB Gateway
            cache_dir: Directory to cache news data
        """
        super().__init__()
        self.client_id = client_id or int(os.environ.get('IBKR_CLIENT_ID', 1))
        self.host = host
        self.port = port
        self.cache_dir = cache_dir
        
        # Create cache directory if it doesn't exist
        if self.cache_dir and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def fetch_news(
        self,
        symbol: str,
        days_back: int = 7,
        limit: int = 50,
    ) -> List[Dict]:
        """Fetch news for a symbol from Interactive Brokers.
        
        Args:
            symbol: Stock or forex pair symbol (e.g., "EUR.USD" for EUR/USD)
            days_back: Number of days to look back
            limit: Maximum number of news items to return
            
        Returns:
            List of news items with metadata
        """
        # Check cache first if enabled
        if self.cache_dir:
            cache_file = os.path.join(
                self.cache_dir,
                f"ibkr_news_{symbol}_{days_back}d_{limit}.json"
            )
            
            # If cache exists and is recent (less than 6 hours old), use it
            if os.path.exists(cache_file):
                file_age = time.time() - os.path.getmtime(cache_file)
                if file_age < 6 * 3600:  # 6 hours
                    try:
                        with open(cache_file, 'r') as f:
                            return json.load(f)
                    except Exception:
                        # If cache read fails, continue to fetch new data
                        pass
        
        try:
            # Import ib_insync here to avoid dependency issues
            from ib_insync import IB, Contract, util
            
            # Format symbol for forex
            if '/' in symbol:
                # Convert EUR/USD to EUR.USD
                formatted_symbol = symbol.replace('/', '.')
            elif len(symbol) == 6 and symbol.isalpha():
                # EURUSD to EUR.USD
                formatted_symbol = f"{symbol[:3]}.{symbol[3:]}"
            else:
                formatted_symbol = symbol
            
            # Connect to IB
            ib = IB()
            ib.connect(self.host, self.port, clientId=self.client_id)
            
            # Create contract
            if '.' in formatted_symbol:  # Forex pair
                base, quote = formatted_symbol.split('.')
                contract = Contract(secType='CASH', symbol=base, currency=quote, exchange='IDEALPRO')
            else:  # Stock
                contract = Contract(secType='STK', symbol=formatted_symbol, currency='USD', exchange='SMART')
            
            # Request contract details to get conId
            details = ib.reqContractDetails(contract)
            if not details:
                ib.disconnect()
                return []
            
            contract = details[0].contract
            
            # Request historical news headlines
            end_date = datetime.now().strftime('%Y%m%d-%H:%M:%S')
            start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d-%H:%M:%S')
            
            headlines = ib.reqHistoricalNews(
                contract.conId, 
                ['BZ', 'DJNL'], # News providers
                start_date, 
                end_date, 
                limit
            )
            
            # Process headlines
            processed_news = []
            for headline in headlines:
                # Format news item
                processed_item = {
                    'title': headline.headline,
                    'summary': '',  # Need to request article body separately
                    'publisher': headline.provider,
                    'publish_date': headline.time.isoformat(),
                    'url': '',  # IB doesn't provide direct URLs
                    'source': 'Interactive Brokers',
                    'article_id': headline.articleId
                }
                
                # Request article text if available
                if hasattr(headline, 'articleId'):
                    try:
                        article = ib.reqNewsArticle(headline.provider, headline.articleId)
                        processed_item['summary'] = article.articleText
                    except Exception:
                        # If article text request fails, continue with empty summary
                        pass
                
                processed_news.append(processed_item)
            
            # Disconnect from IB
            ib.disconnect()
            
            # Cache results if enabled
            if self.cache_dir:
                try:
                    with open(cache_file, 'w') as f:
                        json.dump(processed_news, f)
                except Exception:
                    # Ignore cache write errors
                    pass
                    
            return processed_news
            
        except ImportError:
            raise ImportError(
                "ib_insync package not installed. "
                "Install it with: pip install ib_insync"
            )
        except Exception as e:
            raise Exception(f"Error fetching news from Interactive Brokers: {str(e)}")


class SentimentAnalyzer:
    """Analyze sentiment of news articles."""
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        cache_dir: Optional[str] = None,
    ):
        """Initialize the sentiment analyzer.
        
        Args:
            llm_client: LLM client for sentiment analysis
            cache_dir: Directory to cache sentiment analysis results
        """
        self.llm_client = llm_client or LLMClient()
        self.cache_dir = cache_dir
        
        # Create cache directory if it doesn't exist
        if self.cache_dir and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def analyze_sentiment(
        self,
        text: str,
        currency_pair: str,
        use_cache: bool = True,
    ) -> Dict:
        """Analyze sentiment of a news article.
        
        Args:
            text: News article text
            currency_pair: Currency pair to analyze sentiment for
            use_cache: Whether to use cached results if available
            
        Returns:
            Dictionary with sentiment analysis results
        """
        # Skip empty text
        if not text or len(text.strip()) < 20:
            return {
                "sentiment": "neutral",
                "intensity": 5,
                "relevance": 0,
                "temporal_impact": "none",
                "key_factors": [],
                "confidence": 0
            }
        
        # Create cache key from text hash
        import hashlib
        cache_key = hashlib.md5(text.encode('utf-8')).hexdigest()
        
        # Check cache if enabled
        if use_cache and self.cache_dir:
            cache_file = os.path.join(self.cache_dir, f"sentiment_{cache_key}.json")
            
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        return json.load(f)
                except Exception:
                    # If cache read fails, continue to analyze
                    pass
        
        # Truncate long texts
        if len(text) > 8000:
            text = text[:8000] + "..."
        
        # Create analysis prompt
        prompt = f"""
        Analyze the sentiment of this news article related to {currency_pair}:
        
        {text}
        
        Extract the following:
        1. Overall sentiment: bullish, bearish, or neutral
        2. Sentiment intensity (1-10 scale, where 1 is extremely bearish and 10 is extremely bullish)
        3. Relevance to {currency_pair} (0-10 scale)
        4. Temporal impact: immediate (hours), short-term (days), medium-term (weeks), long-term (months)
        5. Key factors driving sentiment (list up to 3)
        6. Confidence in analysis (0-10 scale)
        
        Format your response as JSON with these exact keys: sentiment, intensity, relevance, temporal_impact, key_factors, confidence.
        """
        
        # Get sentiment analysis from LLM
        try:
            analysis_json = self.llm_client.generate_text(
                prompt=prompt,
                system_prompt="You are a financial sentiment analysis expert. Extract sentiment from news articles related to currency pairs. Respond only with JSON.",
                temperature=0.1,
            )
            
            # Parse JSON response
            try:
                analysis = json.loads(analysis_json)
            except json.JSONDecodeError:
                # Handle case where response is not valid JSON
                # Extract JSON from the text if possible
                import re
                json_match = re.search(r'\{.*\}', analysis_json, re.DOTALL)
                
                if json_match:
                    try:
                        analysis = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        # If still not valid JSON, return default values
                        analysis = {
                            "sentiment": "neutral",
                            "intensity": 5,
                            "relevance": 5,
                            "temporal_impact": "short-term",
                            "key_factors": ["uncertain"],
                            "confidence": 5
                        }
                else:
                    # If no JSON found, return default values
                    analysis = {
                        "sentiment": "neutral",
                        "intensity": 5,
                        "relevance": 5,
                        "temporal_impact": "short-term",
                        "key_factors": ["uncertain"],
                        "confidence": 5
                    }
            
            # Normalize output
            if "sentiment" not in analysis:
                analysis["sentiment"] = "neutral"
                
            analysis["sentiment"] = analysis["sentiment"].lower()
            
            # Ensure values are in expected ranges
            analysis["intensity"] = max(1, min(10, int(analysis.get("intensity", 5))))
            analysis["relevance"] = max(0, min(10, int(analysis.get("relevance", 5))))
            analysis["confidence"] = max(0, min(10, int(analysis.get("confidence", 5))))
            
            # Ensure key_factors is a list
            if not isinstance(analysis.get("key_factors", []), list):
                analysis["key_factors"] = [str(analysis.get("key_factors", ""))]
                
            # Cache results if enabled
            if self.cache_dir:
                try:
                    with open(os.path.join(self.cache_dir, f"sentiment_{cache_key}.json"), 'w') as f:
                        json.dump(analysis, f)
                except Exception:
                    # Ignore cache write errors
                    pass
                    
            return analysis
            
        except Exception as e:
            # Return default values on error
            return {
                "sentiment": "neutral",
                "intensity": 5,
                "relevance": 5,
                "temporal_impact": "short-term",
                "key_factors": [f"Analysis error: {str(e)}"],
                "confidence": 0
            }
    
    def analyze_news_batch(
        self,
        news_items: List[Dict],
        currency_pair: str,
        min_relevance: int = 3,
    ) -> List[Dict]:
        """Analyze sentiment for a batch of news items.
        
        Args:
            news_items: List of news items with title and summary
            currency_pair: Currency pair to analyze sentiment for
            min_relevance: Minimum relevance score (0-10) to include
            
        Returns:
            List of news items with sentiment analysis
        """
        results = []
        
        for item in news_items:
            # Combine title and summary
            text = f"{item.get('title', '')} {item.get('summary', '')}".strip()
            
            # Skip empty items
            if not text:
                continue
                
            # Analyze sentiment
            sentiment = self.analyze_sentiment(text, currency_pair)
            
            # Skip items with low relevance
            if sentiment.get("relevance", 0) < min_relevance:
                continue
                
            # Add sentiment analysis to item
            item_with_sentiment = {
                **item,
                "sentiment_analysis": sentiment,
            }
            
            results.append(item_with_sentiment)
            
        return results


class SentimentAggregator:
    """Aggregate sentiment data over time."""
    
    def __init__(self):
        """Initialize the sentiment aggregator."""
        pass
    
    def create_sentiment_timeseries(
        self,
        sentiment_data: List[Dict],
        timeframe: str = "daily",
    ) -> pd.DataFrame:
        """Create a time series of sentiment data.
        
        Args:
            sentiment_data: List of sentiment analysis results with timestamps
            timeframe: Timeframe for aggregation (hourly, daily, weekly)
            
        Returns:
            DataFrame with sentiment aggregated by timeframe
        """
        if not sentiment_data:
            return pd.DataFrame()
            
        # Extract datetime and sentiment info
        data = []
        for item in sentiment_data:
            sentiment_analysis = item.get("sentiment_analysis", {})
            
            # Skip items without sentiment
            if not sentiment_analysis:
                continue
                
            # Convert timestamp string to datetime
            try:
                timestamp = datetime.fromisoformat(item.get("publish_date", ""))
            except (ValueError, TypeError):
                # Skip items with invalid timestamps
                continue
            
            # Map sentiment to numeric value
            sentiment_value = {
                "bullish": 1,
                "neutral": 0,
                "bearish": -1,
            }.get(sentiment_analysis.get("sentiment", "neutral"), 0)
            
            # Calculate weighted sentiment
            intensity = sentiment_analysis.get("intensity", 5)
            relevance = sentiment_analysis.get("relevance", 5)
            confidence = sentiment_analysis.get("confidence", 5)
            
            # Normalize intensity to -10 to 10 scale based on sentiment
            if sentiment_value == 0:  # neutral
                normalized_intensity = 0
            elif sentiment_value == 1:  # bullish
                normalized_intensity = intensity
            else:  # bearish
                normalized_intensity = -intensity
            
            # Calculate weighted sentiment (relevance and confidence as weights)
            weighted_sentiment = normalized_intensity * (relevance / 10) * (confidence / 10)
            
            data.append({
                "timestamp": timestamp,
                "sentiment": sentiment_value,
                "intensity": intensity,
                "relevance": relevance,
                "confidence": confidence,
                "weighted_sentiment": weighted_sentiment,
                "source": item.get("source", "Unknown"),
                "title": item.get("title", ""),
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        if df.empty:
            return df
            
        # Set timestamp as index
        df.set_index("timestamp", inplace=True)
        
        # Resample by timeframe
        if timeframe == "hourly":
            freq = "H"
        elif timeframe == "daily":
            freq = "D"
        elif timeframe == "weekly":
            freq = "W"
        else:
            freq = "D"  # Default to daily
            
        # Group by timeframe and calculate aggregates
        agg_df = df.resample(freq).agg({
            "sentiment": "mean",
            "intensity": "mean",
            "relevance": "mean",
            "confidence": "mean",
            "weighted_sentiment": "mean",
            "source": "count",  # Count sources
        })
        
        # Rename source column to news_count
        agg_df.rename(columns={"source": "news_count"}, inplace=True)
        
        return agg_df
    
    def calculate_sentiment_indicators(
        self,
        sentiment_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate sentiment indicators from aggregated data.
        
        Args:
            sentiment_df: DataFrame with aggregated sentiment data
            
        Returns:
            DataFrame with sentiment indicators
        """
        if sentiment_df.empty:
            return pd.DataFrame()
            
        # Create copy to avoid modifying original
        df = sentiment_df.copy()
        
        # Calculate moving averages
        df["sentiment_ma5"] = df["weighted_sentiment"].rolling(5).mean()
        df["sentiment_ma10"] = df["weighted_sentiment"].rolling(10).mean()
        
        # Calculate sentiment momentum (rate of change)
        df["sentiment_momentum"] = df["weighted_sentiment"].diff()
        
        # Calculate sentiment volatility
        df["sentiment_volatility"] = df["weighted_sentiment"].rolling(5).std()
        
        # Calculate sentiment divergence (difference between short and long MA)
        df["sentiment_divergence"] = df["sentiment_ma5"] - df["sentiment_ma10"]
        
        return df


class MarketSentimentAnalyzer:
    """Main class for market sentiment analysis."""
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        use_yahoo: bool = True,
        use_ibkr: bool = False,
        llm_client: Optional[LLMClient] = None,
    ):
        """Initialize the market sentiment analyzer.
        
        Args:
            cache_dir: Directory to cache data (if None, use default)
            use_yahoo: Whether to use Yahoo Finance
            use_ibkr: Whether to use Interactive Brokers
            llm_client: LLM client for sentiment analysis
        """
        # Set cache directory
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            # Default to ~/.fxml3/cache/sentiment
            home_dir = os.path.expanduser("~")
            self.cache_dir = os.path.join(home_dir, ".fxml3", "cache", "sentiment")
            os.makedirs(self.cache_dir, exist_ok=True)
            
        # Set up news sources
        self.news_sources = []
        
        if use_yahoo:
            yahoo_cache_dir = os.path.join(self.cache_dir, "yahoo")
            self.news_sources.append(
                YahooFinanceNewsFetcher(cache_dir=yahoo_cache_dir)
            )
            
        if use_ibkr:
            ibkr_cache_dir = os.path.join(self.cache_dir, "ibkr")
            self.news_sources.append(
                IBKRNewsFetcher(cache_dir=ibkr_cache_dir)
            )
            
        # Set up LLM client
        self.llm_client = llm_client or LLMClient()
        
        # Set up sentiment analyzer
        sentiment_cache_dir = os.path.join(self.cache_dir, "sentiment")
        self.sentiment_analyzer = SentimentAnalyzer(
            llm_client=self.llm_client,
            cache_dir=sentiment_cache_dir,
        )
        
        # Set up sentiment aggregator
        self.sentiment_aggregator = SentimentAggregator()
    
    def analyze_market_sentiment(
        self,
        symbol: str,
        days_back: int = 7,
        min_relevance: int = 3,
        timeframe: str = "daily",
    ) -> Dict:
        """Analyze market sentiment for a symbol.
        
        Args:
            symbol: Symbol or currency pair (e.g., "EURUSD")
            days_back: Number of days to look back
            min_relevance: Minimum relevance score to include
            timeframe: Timeframe for aggregation
            
        Returns:
            Dictionary with sentiment analysis results
        """
        # Format symbol for currency pairs
        if len(symbol) == 6 and symbol.isalpha():
            currency_pair = f"{symbol[:3]}/{symbol[3:]}"
        else:
            currency_pair = symbol
        
        # Fetch news from all sources
        all_news = []
        for source in self.news_sources:
            try:
                news = source.fetch_news(symbol, days_back=days_back)
                all_news.extend(news)
            except Exception as e:
                print(f"Error fetching news from {source.__class__.__name__}: {str(e)}")
                
        # If no news, return empty result
        if not all_news:
            return {
                "status": "error",
                "message": "No news found for symbol",
                "data": {
                    "sentiment_summary": {
                        "overall": "neutral",
                        "weighted_score": 0,
                        "confidence": 0,
                    },
                    "news_count": 0,
                    "timeframe": timeframe,
                    "timeseries": None,
                }
            }
            
        # Analyze sentiment for all news
        news_with_sentiment = self.sentiment_analyzer.analyze_news_batch(
            all_news,
            currency_pair,
            min_relevance=min_relevance,
        )
        
        # Create time series
        sentiment_df = self.sentiment_aggregator.create_sentiment_timeseries(
            news_with_sentiment,
            timeframe=timeframe,
        )
        
        # Calculate indicators
        indicators_df = self.sentiment_aggregator.calculate_sentiment_indicators(
            sentiment_df
        )
        
        # Calculate overall sentiment metrics
        # Convert to list to handle numpy numeric types that are not JSON serializable
        sentiment_summary = {
            "overall": "neutral",
            "weighted_score": 0,
            "confidence": 0,
        }
        
        if not indicators_df.empty:
            # Get latest values
            latest = indicators_df.iloc[-1]
            
            # Calculate overall sentiment
            score = latest.get("weighted_sentiment", 0)
            
            if -0.5 <= score <= 0.5:
                sentiment = "neutral"
            elif score > 0.5:
                sentiment = "bullish"
            else:
                sentiment = "bearish"
            
            confidence = latest.get("confidence", 0)
            
            sentiment_summary = {
                "overall": sentiment,
                "weighted_score": float(score),
                "confidence": float(confidence),
                "momentum": float(latest.get("sentiment_momentum", 0)),
                "divergence": float(latest.get("sentiment_divergence", 0)),
                "volatility": float(latest.get("sentiment_volatility", 0)),
            }
            
        # Create result dictionary
        result = {
            "status": "success",
            "data": {
                "symbol": symbol,
                "currency_pair": currency_pair,
                "days_back": days_back,
                "sentiment_summary": sentiment_summary,
                "news_count": len(news_with_sentiment),
                "top_news": news_with_sentiment[:5] if news_with_sentiment else [],
                "timeframe": timeframe,
                "timeseries": indicators_df.reset_index().to_dict(orient="records") if not indicators_df.empty else [],
            }
        }
        
        return result
    
    def validate_wave_with_sentiment(
        self,
        wave_pattern: Dict,
        sentiment_data: Dict,
    ) -> Dict:
        """Validate a wave pattern using sentiment data.
        
        Args:
            wave_pattern: Dictionary containing Elliott Wave pattern data
            sentiment_data: Dictionary with sentiment analysis results
            
        Returns:
            Dictionary with validation results
        """
        # Extract wave pattern info
        pattern_type = wave_pattern.get("type", "unknown")
        wave_count = wave_pattern.get("wave_count", 0)
        
        # Extract sentiment info
        sentiment_summary = sentiment_data.get("data", {}).get("sentiment_summary", {})
        overall_sentiment = sentiment_summary.get("overall", "neutral")
        sentiment_score = sentiment_summary.get("weighted_score", 0)
        sentiment_momentum = sentiment_summary.get("momentum", 0)
        
        # Initialize validation result
        validation = {
            "sentiment_aligned": False,
            "confidence": 0,
            "explanation": "",
        }
        
        # Validate impulse waves
        if pattern_type == "impulse":
            # Map wave count to expected sentiment
            expected_sentiment = {
                1: "bullish",  # Wave 1: Bullish sentiment starting
                2: "bearish",  # Wave 2: Correction, bearish sentiment
                3: "strongly bullish",  # Wave 3: Strong bullish sentiment
                4: "neutral",  # Wave 4: Correction, mixed sentiment
                5: "bullish",  # Wave 5: Final bullish move, but often with divergence
            }.get(wave_count, "unknown")
            
            # Check for alignment with expected sentiment
            if wave_count in [1, 3, 5] and overall_sentiment == "bullish":
                validation["sentiment_aligned"] = True
                validation["confidence"] = sentiment_summary.get("confidence", 0)
                
                # Special case for wave 3
                if wave_count == 3 and sentiment_score > 3:
                    validation["confidence"] = min(10, validation["confidence"] + 2)
                    
            elif wave_count == 2 and overall_sentiment == "bearish":
                validation["sentiment_aligned"] = True
                validation["confidence"] = sentiment_summary.get("confidence", 0)
                
            elif wave_count == 4 and overall_sentiment == "neutral":
                validation["sentiment_aligned"] = True
                validation["confidence"] = sentiment_summary.get("confidence", 0)
                
            # Generate explanation
            validation["explanation"] = f"Wave {wave_count} ({pattern_type}) typically shows {expected_sentiment} sentiment. Current sentiment is {overall_sentiment} with score {sentiment_score:.2f}."
                
        # Validate corrective waves
        elif pattern_type == "corrective":
            # Map wave count to expected sentiment
            expected_sentiment = {
                1: "bearish",  # Wave A: Bearish sentiment
                2: "slightly bullish",  # Wave B: Temporary bullish sentiment
                3: "strongly bearish",  # Wave C: Strong bearish sentiment
            }.get(wave_count, "unknown")
            
            # Check for alignment with expected sentiment
            if wave_count == 1 and overall_sentiment == "bearish":
                validation["sentiment_aligned"] = True
                validation["confidence"] = sentiment_summary.get("confidence", 0)
                
            elif wave_count == 2 and overall_sentiment in ["neutral", "bullish"]:
                validation["sentiment_aligned"] = True
                validation["confidence"] = sentiment_summary.get("confidence", 0)
                
            elif wave_count == 3 and overall_sentiment == "bearish":
                validation["sentiment_aligned"] = True
                validation["confidence"] = sentiment_summary.get("confidence", 0)
                
                # Stronger bearish sentiment for wave C
                if sentiment_score < -3:
                    validation["confidence"] = min(10, validation["confidence"] + 2)
                    
            # Generate explanation
            validation["explanation"] = f"Wave {wave_count} ({pattern_type}) typically shows {expected_sentiment} sentiment. Current sentiment is {overall_sentiment} with score {sentiment_score:.2f}."
                
        return validation


class SentimentAgent:
    """Agent for market sentiment analysis."""
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        use_yahoo: bool = True,
        use_ibkr: bool = False,
        llm_client: Optional[LLMClient] = None,
    ):
        """Initialize the sentiment agent.
        
        Args:
            cache_dir: Directory to cache data
            use_yahoo: Whether to use Yahoo Finance
            use_ibkr: Whether to use Interactive Brokers
            llm_client: LLM client for sentiment analysis
        """
        self.analyzer = MarketSentimentAnalyzer(
            cache_dir=cache_dir,
            use_yahoo=use_yahoo,
            use_ibkr=use_ibkr,
            llm_client=llm_client,
        )
    
    def get_market_sentiment(
        self,
        symbol: str,
        days_back: int = 7,
        timeframe: str = "daily",
    ) -> Dict:
        """Get market sentiment for a symbol.
        
        Args:
            symbol: Symbol or currency pair
            days_back: Number of days to look back
            timeframe: Timeframe for aggregation
            
        Returns:
            Dictionary with sentiment analysis results
        """
        return self.analyzer.analyze_market_sentiment(
            symbol=symbol,
            days_back=days_back,
            timeframe=timeframe,
        )
    
    def validate_wave(
        self,
        wave_pattern: Dict,
        symbol: str,
        days_back: int = 7,
    ) -> Dict:
        """Validate a wave pattern using sentiment analysis.
        
        Args:
            wave_pattern: Dictionary containing Elliott Wave pattern data
            symbol: Symbol or currency pair
            days_back: Number of days to look back
            
        Returns:
            Dictionary with validation results
        """
        # Get sentiment data
        sentiment_data = self.analyzer.analyze_market_sentiment(
            symbol=symbol,
            days_back=days_back,
        )
        
        # Validate wave with sentiment
        validation = self.analyzer.validate_wave_with_sentiment(
            wave_pattern=wave_pattern,
            sentiment_data=sentiment_data,
        )
        
        return {
            "wave_pattern": wave_pattern,
            "sentiment_data": sentiment_data,
            "validation": validation,
        }
    
    def get_sentiment_for_period(
        self,
        symbol: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> Dict:
        """Get sentiment for a specific time period.
        
        Args:
            symbol: Symbol or currency pair
            start_date: Start date (ISO format)
            end_date: End date (ISO format), defaults to today
            
        Returns:
            Dictionary with sentiment analysis results
        """
        # Calculate days back from start date
        try:
            start = datetime.fromisoformat(start_date)
            days_back = (datetime.now() - start).days
        except ValueError:
            return {
                "status": "error",
                "message": "Invalid start_date format. Use ISO format (YYYY-MM-DD)."
            }
            
        # Get sentiment data
        sentiment_data = self.analyzer.analyze_market_sentiment(
            symbol=symbol,
            days_back=max(days_back, 1),  # At least 1 day back
        )
        
        # Filter timeseries by date range
        if "timeseries" in sentiment_data.get("data", {}):
            filtered_timeseries = []
            
            for entry in sentiment_data["data"]["timeseries"]:
                # Parse entry timestamp
                try:
                    timestamp = datetime.fromisoformat(entry["timestamp"])
                except (ValueError, KeyError):
                    continue
                    
                # Check if within date range
                if start <= timestamp and (not end_date or timestamp <= datetime.fromisoformat(end_date)):
                    filtered_timeseries.append(entry)
                    
            sentiment_data["data"]["timeseries"] = filtered_timeseries
            
        return sentiment_data