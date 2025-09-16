#!/usr/bin/env python3
"""
Economic and Sentiment Feature Engineering

This module provides functionality to:
1. Fetch economic indicators from FRED
2. Fetch and analyze sentiment data from Alpha Vantage news API
3. Integrate these features with technical indicators for ML model training
4. Provide correlation analysis tools to identify the most important features

This implementation enhances the ML model by incorporating exogenous data sources
beyond just price action, potentially improving prediction accuracy.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Load environment variables for API keys
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EconomicFeatureIntegrator:
    """Integrates economic data from FRED API with trading data."""

    def __init__(
        self,
        fred_api_key: Optional[str] = None,
        use_cache: bool = True,
        cache_expiry: int = 24,  # hours
    ):
        """
        Initialize the economic feature integrator.

        Args:
            fred_api_key: FRED API key (if None, tries to load from FRED_API_KEY env var)
            use_cache: Whether to cache API responses
            cache_expiry: Cache expiry time in hours
        """
        self.fred_api_key = fred_api_key or os.environ.get("FRED_API_KEY")
        self.use_cache = use_cache
        self.cache_expiry = cache_expiry

        # Cache directory setup
        self.cache_dir = os.path.join(
            os.path.expanduser("~"), ".fxml4", "cache", "fred"
        )
        if use_cache and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)

        # Basic FRED indicators that are relevant for forex
        self.default_indicators = {
            "FEDFUNDS": "Fed Funds Rate",
            "UNRATE": "Unemployment Rate",
            "CPIAUCSL": "CPI",
            "T10Y2Y": "10Y-2Y Yield Spread",
            "T10Y3M": "10Y-3M Yield Spread",
            "VIXCLS": "VIX",
            "DTWEXBGS": "US Dollar Index",
            "INDPRO": "Industrial Production",
        }

        # Initialize FRED client if possible
        try:
            from fxml4.data_engineering.data_feeds.fred_feed import FREDDataFeed

            # Check if we can import without error but don't instantiate yet
            logger.info("FRED client module imported successfully")
            self.fred_client = None
        except (ImportError, ModuleNotFoundError):
            logger.warning("Failed to import FRED client, will use direct API calls")
            self.fred_client = None

    def fetch_fred_indicator(
        self,
        indicator: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
    ) -> pd.DataFrame:
        """
        Fetch a specific indicator from FRED.

        Args:
            indicator: FRED series ID (e.g., "UNRATE" for unemployment rate)
            start_date: Start date for the data
            end_date: End date for the data

        Returns:
            DataFrame with the indicator data
        """
        # Use existing FRED client if available
        if self.fred_client:
            df = self.fred_client.get_series(
                series_id=indicator, start_date=start_date, end_date=end_date
            )
            return df

        # Fallback to direct API calls
        try:
            from urllib.parse import urlencode

            import requests

            # Cache key
            cache_key = f"{indicator}_{start_date}_{end_date}"
            cache_file = os.path.join(self.cache_dir, f"{hash(cache_key)}.csv")

            # Check cache if enabled
            if self.use_cache and os.path.exists(cache_file):
                file_age = time.time() - os.path.getmtime(cache_file)
                if file_age < self.cache_expiry * 3600:  # Convert hours to seconds
                    df = pd.read_csv(cache_file, parse_dates=["date"], index_col="date")
                    return df

            # Process dates
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365 * 5)).strftime(
                    "%Y-%m-%d"
                )  # 5 years ago
            elif isinstance(start_date, datetime):
                start_date = start_date.strftime("%Y-%m-%d")

            if end_date is None:
                end_date = datetime.now().strftime("%Y-%m-%d")
            elif isinstance(end_date, datetime):
                end_date = end_date.strftime("%Y-%m-%d")

            # Prepare API request
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": indicator,
                "api_key": self.fred_api_key,
                "file_type": "json",
                "observation_start": start_date,
                "observation_end": end_date,
            }

            # Make API request
            response = requests.get(url, params=params)
            response.raise_for_status()

            # Parse response
            data = response.json()
            observations = data.get("observations", [])

            # Create DataFrame
            df = pd.DataFrame(observations)
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)

            # Convert values to numeric
            df["value"] = pd.to_numeric(df["value"], errors="coerce")

            # Cache result if enabled
            if self.use_cache:
                df.to_csv(cache_file)

            return df

        except Exception as e:
            logger.error(f"Error fetching FRED indicator {indicator}: {e}")
            return pd.DataFrame()

    def fetch_economic_indicators(
        self,
        indicators: Optional[List[str]] = None,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
    ) -> pd.DataFrame:
        """
        Fetch multiple economic indicators and combine them.

        Args:
            indicators: List of FRED series IDs (if None, uses default set)
            start_date: Start date for the data
            end_date: End date for the data

        Returns:
            DataFrame with combined economic indicators
        """
        # Use default indicators if none specified
        if indicators is None:
            indicators = list(self.default_indicators.keys())

        # Fetch data for each indicator
        all_data = {}
        for indicator in indicators:
            try:
                df = self.fetch_fred_indicator(indicator, start_date, end_date)
                if not df.empty:
                    all_data[indicator] = df["value"]
                    logger.info(
                        f"Successfully fetched {indicator} with {len(df)} data points"
                    )
                else:
                    logger.warning(f"No data returned for indicator {indicator}")
            except Exception as e:
                logger.error(f"Error fetching indicator {indicator}: {e}")

        # Combine all indicators into a single DataFrame
        if not all_data:
            logger.warning("No economic indicators were successfully fetched")
            return pd.DataFrame()

        # Create combined DataFrame
        combined_df = pd.DataFrame(all_data)

        # Fill missing values
        # Forward fill for most recent value, then backward fill for start of series
        combined_df = combined_df.ffill().bfill()

        return combined_df

    def create_economic_features(
        self,
        market_data: pd.DataFrame,
        economic_data: pd.DataFrame,
        resample: bool = True,
    ) -> pd.DataFrame:
        """
        Create economic features and integrate with market data.

        Args:
            market_data: DataFrame with market OHLCV data
            economic_data: DataFrame with economic indicators
            resample: Whether to resample economic data to match market data frequency

        Returns:
            DataFrame with market data and economic features
        """
        if economic_data.empty:
            logger.warning("No economic data provided, returning original market data")
            return market_data.copy()

        # Create a copy to avoid modifying original
        df = market_data.copy()

        # Determine market data frequency
        if isinstance(df.index, pd.DatetimeIndex):
            # Calculate average time delta
            time_diffs = df.index.to_series().diff().dropna()
            if len(time_diffs) > 0:
                avg_diff = time_diffs.mean().total_seconds()

                # Map to pandas frequency strings
                if avg_diff < 60:  # Less than a minute
                    freq = "S"  # Seconds
                elif avg_diff < 3600:  # Less than an hour
                    freq = "T"  # Minutes
                elif avg_diff < 86400:  # Less than a day
                    freq = "H"  # Hours
                else:
                    freq = "D"  # Days
            else:
                freq = "D"  # Default to daily
        else:
            logger.warning(
                "Market data index is not a DatetimeIndex, assuming daily frequency"
            )
            freq = "D"

        # Resample economic data if needed
        if resample:
            # Most economic data is daily or lower frequency, so we need to upsample
            # Use forward fill to propagate values
            if freq == "T":
                # Use minutes for higher frequency data
                economic_data_resampled = economic_data.resample("min").ffill()
            elif freq == "S":
                # Use seconds for very high frequency data
                economic_data_resampled = economic_data.resample("S").ffill()
            else:
                economic_data_resampled = economic_data.resample(freq).ffill()

            # Align with market data index
            eco_features = pd.DataFrame(index=df.index)
            for column in economic_data.columns:
                # Map each economic data point to closest market data point
                # First ensure compatible timezone handling
                try:
                    # Convert economic data index to naive datetime if it has timezone info
                    if economic_data_resampled.index.tz is not None:
                        eco_index = economic_data_resampled.index.tz_localize(None)
                        eco_temp = economic_data_resampled.copy()
                        eco_temp.index = eco_index

                        # If market data has timezone info, match it
                        if df.index.tz is not None:
                            eco_temp.index = eco_temp.index.tz_localize(df.index.tz)

                        eco_features[column] = eco_temp.reindex(
                            df.index, method="nearest"
                        )[column]
                    else:
                        # If market data has timezone but economic doesn't, localize economic data
                        if df.index.tz is not None:
                            eco_temp = economic_data_resampled.copy()
                            eco_temp.index = eco_temp.index.tz_localize(df.index.tz)
                            eco_features[column] = eco_temp.reindex(
                                df.index, method="nearest"
                            )[column]
                        else:
                            # Both are naive datetimes
                            eco_features[column] = economic_data_resampled.reindex(
                                df.index, method="nearest"
                            )[column]
                except Exception as e:
                    logger.warning(f"Error mapping economic data for {column}: {e}")
                    # Fallback: convert both to Unix timestamps and interpolate
                    try:
                        # Convert economic data to Series with Unix timestamp index
                        eco_series = pd.Series(
                            economic_data_resampled[column].values,
                            index=economic_data_resampled.index.astype(int) // 10**9,
                        )
                        # Convert market data index to Unix timestamps
                        market_ts = df.index.astype(int) // 10**9
                        # Interpolate economic data to market data timestamps
                        eco_features[column] = np.interp(
                            market_ts, eco_series.index, eco_series.values
                        )
                    except Exception as e2:
                        logger.error(
                            f"Fallback interpolation failed for {column}: {e2}"
                        )
                        eco_features[column] = np.nan

                # Calculate relative changes (daily, weekly, monthly)
                if column in eco_features.columns:
                    # Daily change rate
                    eco_features[f"{column}_change_1d"] = eco_features[
                        column
                    ].pct_change(1)

                    # Weekly change rate (5 business days)
                    eco_features[f"{column}_change_5d"] = eco_features[
                        column
                    ].pct_change(5)

                    # Monthly change rate (21 business days)
                    eco_features[f"{column}_change_21d"] = eco_features[
                        column
                    ].pct_change(21)
        else:
            # Just merge as is (suitable for same frequency data)
            eco_features = economic_data.copy()

        # Z-score normalization for all indicators
        for column in economic_data.columns:
            if column in eco_features.columns:
                mean = eco_features[column].mean()
                std = eco_features[column].std()
                if std > 0:
                    eco_features[f"{column}_zscore"] = (
                        eco_features[column] - mean
                    ) / std

        # Join with market data
        result = df.join(eco_features, how="left")

        # Fill any missing values from join
        result = result.ffill().bfill()

        logger.info(
            f"Added {len(eco_features.columns)} economic features to market data"
        )
        return result

    def feature_importance_analysis(
        self,
        market_data: pd.DataFrame,
        economic_data: pd.DataFrame,
        target_column: str,
        top_n: int = 10,
        plot: bool = False,
    ) -> Tuple[pd.DataFrame, Optional[plt.Figure]]:
        """
        Analyze feature importance between economic indicators and a target.

        Args:
            market_data: DataFrame with market data
            economic_data: DataFrame with economic indicators
            target_column: Name of target column in market data
            top_n: Number of top features to return
            plot: Whether to generate correlation heatmap

        Returns:
            Tuple of (feature importance DataFrame, optional matplotlib figure)
        """
        # Merge market data (containing target) with economic data
        merged_data = self.create_economic_features(market_data, economic_data)

        # Check if target column exists
        if target_column not in merged_data.columns:
            logger.error(f"Target column '{target_column}' not found in data")
            return pd.DataFrame(), None

        # Calculate correlation with target
        correlations = merged_data.corr()[target_column].drop(target_column)

        # Calculate absolute correlation for ranking
        abs_correlations = correlations.abs()

        # Get top N features by correlation
        top_features = abs_correlations.sort_values(ascending=False).head(top_n)

        # Create feature importance DataFrame
        importance_df = pd.DataFrame(
            {
                "feature": top_features.index,
                "correlation": correlations.loc[top_features.index],
                "abs_correlation": top_features.values,
            }
        )

        # Create heatmap if requested
        fig = None
        if plot:
            try:
                import seaborn as sns

                # Get features to include in heatmap (top N plus target)
                heatmap_cols = list(top_features.index) + [target_column]

                # Create correlation matrix
                corr_matrix = merged_data[heatmap_cols].corr()

                # Create the heatmap
                fig, ax = plt.subplots(figsize=(12, 10))
                sns.heatmap(
                    corr_matrix,
                    annot=True,
                    fmt=".2f",
                    cmap="coolwarm",
                    square=True,
                    cbar_kws={"shrink": 0.8},
                    vmin=-1,
                    vmax=1,
                    ax=ax,
                )
                ax.set_title("Correlation between Economic Indicators and Target")

                # Rotate y labels for better readability
                plt.yticks(rotation=0)
                plt.tight_layout()

            except ImportError:
                logger.warning("Seaborn not installed, skipping plot generation")

            except Exception as e:
                logger.error(f"Error generating correlation heatmap: {e}")

        return importance_df, fig


class SentimentFeatureIntegrator:
    """Integrates market sentiment data from Alpha Vantage with trading data."""

    def __init__(
        self,
        alpha_vantage_key: Optional[str] = None,
        use_cache: bool = True,
        cache_expiry: int = 6,  # hours
    ):
        """
        Initialize the sentiment feature integrator.

        Args:
            alpha_vantage_key: Alpha Vantage API key (if None, loads from env var)
            use_cache: Whether to cache API responses
            cache_expiry: Cache expiry time in hours
        """
        self.alpha_vantage_key = alpha_vantage_key or os.environ.get(
            "ALPHA_VANTAGE_API_KEY"
        )
        self.use_cache = use_cache
        self.cache_expiry = cache_expiry

        # Cache directory setup
        self.cache_dir = os.path.join(
            os.path.expanduser("~"), ".fxml4", "cache", "sentiment"
        )
        if use_cache and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)

        # Initialize Alpha Vantage client if available
        try:
            from fxml4.data_engineering.data_feeds.alpha_vantage_feed import (
                AlphaVantageDataFeed,
            )

            self.av_client = AlphaVantageDataFeed(
                {
                    "api_key": self.alpha_vantage_key,
                    "cache_data": self.use_cache,
                    "cache_expiry": self.cache_expiry * 3600,
                }
            )
            logger.info("Initialized Alpha Vantage client successfully")
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(f"Failed to import Alpha Vantage client: {e}")
            self.av_client = None

        # Initialize sentiment analyzer if available
        try:
            from fxml4.llm_integration.sentiment_analysis import SentimentAnalyzer

            self.sentiment_analyzer = SentimentAnalyzer(cache_dir=self.cache_dir)
            logger.info("Initialized sentiment analyzer successfully")
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(f"Failed to import sentiment analyzer: {e}")
            self.sentiment_analyzer = None

    def fetch_news_data(
        self, symbol: str, days_back: int = 30, limit: int = 50
    ) -> List[Dict]:
        """
        Fetch news data for a symbol.

        Args:
            symbol: Symbol or currency pair
            days_back: Number of days to look back
            limit: Maximum number of news items to return

        Returns:
            List of news items with metadata
        """
        # Check cache first if enabled
        if self.use_cache:
            cache_file = os.path.join(
                self.cache_dir, f"news_{symbol}_{days_back}d_{limit}.json"
            )

            # If cache exists and is recent, use it
            if os.path.exists(cache_file):
                file_age = time.time() - os.path.getmtime(cache_file)
                if file_age < self.cache_expiry * 3600:  # Convert hours to seconds
                    try:
                        import json

                        with open(cache_file, "r") as f:
                            return json.load(f)
                    except Exception as e:
                        logger.warning(f"Error reading cache: {e}")

        # Try to use Alpha Vantage client
        if self.av_client:
            try:
                # Format symbol for forex if needed
                if len(symbol) == 6 and symbol.isalpha():
                    # Convert EURUSD to EUR/USD
                    formatted_symbol = f"{symbol[:3]}/{symbol[3:]}"
                else:
                    formatted_symbol = symbol

                # Use Alpha Vantage news API
                # Note: This functionality might require a premium API key
                # Placeholder for future implementation
                # For now, try to use yfinance as fallback
                raise NotImplementedError("Alpha Vantage news API not yet implemented")

            except Exception as e:
                logger.warning(f"Error fetching news via Alpha Vantage: {e}")

        # Fallback to Yahoo Finance via yfinance
        try:
            import yfinance as yf

            # Format symbol for forex if needed
            if len(symbol) == 6 and symbol.isalpha():
                # EURUSD to EURUSD=X for forex symbols in Yahoo Finance
                formatted_symbol = f"{symbol}=X"
            elif "/" in symbol:
                # Convert EUR/USD to EURUSD=X
                formatted_symbol = f"{symbol.replace('/', '')}=X"
            else:
                formatted_symbol = symbol

            # Get ticker and news
            ticker = yf.Ticker(formatted_symbol)
            news_items = ticker.news

            # Process and format news
            processed_news = []
            for item in news_items[:limit]:
                # Convert timestamp to datetime
                timestamp = item.get("providerPublishTime", 0)
                pub_date = datetime.fromtimestamp(timestamp)

                # Skip news older than days_back
                if pub_date < datetime.now() - timedelta(days=days_back):
                    continue

                # Format news item
                processed_item = {
                    "title": item.get("title", ""),
                    "summary": item.get("summary", ""),
                    "publisher": item.get("publisher", ""),
                    "publish_date": pub_date.isoformat(),
                    "url": item.get("link", ""),
                    "source": "Yahoo Finance",
                }

                processed_news.append(processed_item)

            # Cache results if enabled
            if self.use_cache:
                import json

                try:
                    with open(cache_file, "w") as f:
                        json.dump(processed_news, f)
                except Exception as e:
                    logger.warning(f"Error writing cache: {e}")

            return processed_news

        except ImportError:
            logger.warning("yfinance not installed, cannot fetch news")
            return []
        except Exception as e:
            logger.error(f"Error fetching news data: {e}")
            return []

    def analyze_sentiment(self, news_items: List[Dict], symbol: str) -> Dict:
        """
        Analyze sentiment from news items.

        Args:
            news_items: List of news items with title and summary
            symbol: Symbol or currency pair

        Returns:
            Dictionary with sentiment analysis results
        """
        if not news_items:
            return {
                "overall_sentiment": 0.0,
                "bullish_articles": 0,
                "bearish_articles": 0,
                "neutral_articles": 0,
                "total_articles": 0,
            }

        # Check if we have the sentiment analyzer from fxml3
        if self.sentiment_analyzer:
            try:
                # Format symbol for forex if needed
                if len(symbol) == 6 and symbol.isalpha():
                    currency_pair = f"{symbol[:3]}/{symbol[3:]}"
                else:
                    currency_pair = symbol

                # Analyze sentiment for each news item
                analyzed_items = []
                for item in news_items:
                    # Combine title and summary
                    text = f"{item.get('title', '')} {item.get('summary', '')}"

                    # Skip empty items
                    if not text or len(text) < 20:
                        continue

                    # Analyze sentiment
                    sentiment = self.sentiment_analyzer.analyze_sentiment(
                        text, currency_pair
                    )

                    # Add to analyzed items
                    item_with_sentiment = {**item, "sentiment": sentiment}
                    analyzed_items.append(item_with_sentiment)

                # Calculate overall metrics
                bullish = 0
                bearish = 0
                neutral = 0

                # Sentiment scores for weighted average
                weighted_scores = []
                weights = []

                for item in analyzed_items:
                    sentiment = item.get("sentiment", {})
                    sentiment_type = sentiment.get("sentiment", "neutral").lower()

                    # Count by sentiment type
                    if sentiment_type == "bullish":
                        bullish += 1
                    elif sentiment_type == "bearish":
                        bearish += 1
                    else:
                        neutral += 1

                    # Calculate weighted sentiment score
                    # Map sentiment intensity (1-10) to -1 to 1 scale
                    intensity = sentiment.get("intensity", 5)
                    if sentiment_type == "neutral":
                        score = 0
                    elif sentiment_type == "bullish":
                        score = (intensity - 5) / 5  # Map 5-10 to 0-1
                    else:  # bearish
                        score = (5 - intensity) / 5  # Map 5-1 to 0-(-1)

                    # Use relevance and confidence as weights
                    relevance = sentiment.get("relevance", 5)
                    confidence = sentiment.get("confidence", 5)
                    weight = (relevance * confidence) / 100

                    weighted_scores.append(score * weight)
                    weights.append(weight)

                # Calculate overall sentiment score (-1 to 1 scale)
                if sum(weights) > 0:
                    overall_sentiment = sum(weighted_scores) / sum(weights)
                else:
                    overall_sentiment = 0.0

                return {
                    "overall_sentiment": overall_sentiment,
                    "bullish_articles": bullish,
                    "bearish_articles": bearish,
                    "neutral_articles": neutral,
                    "total_articles": len(analyzed_items),
                    "news_items": analyzed_items[
                        :10
                    ],  # Include top 10 items with sentiment
                }

            except Exception as e:
                logger.error(f"Error analyzing sentiment: {e}")

        # Simple sentiment analysis using text keywords if analyzer not available
        try:
            # Define sentiment keywords
            bullish_keywords = [
                "up",
                "rise",
                "gain",
                "bull",
                "beat",
                "positive",
                "growth",
                "recovery",
                "strong",
                "surge",
            ]
            bearish_keywords = [
                "down",
                "fall",
                "drop",
                "bear",
                "miss",
                "negative",
                "decline",
                "weak",
                "crash",
                "tumble",
            ]

            # Count articles by sentiment
            bullish = 0
            bearish = 0
            neutral = 0

            for item in news_items:
                # Combine title and summary
                text = f"{item.get('title', '')} {item.get('summary', '')}".lower()

                # Skip empty items
                if not text:
                    continue

                # Count keyword matches
                bullish_matches = sum(keyword in text for keyword in bullish_keywords)
                bearish_matches = sum(keyword in text for keyword in bearish_keywords)

                # Determine sentiment based on keyword counts
                if bullish_matches > bearish_matches:
                    bullish += 1
                elif bearish_matches > bullish_matches:
                    bearish += 1
                else:
                    neutral += 1

            # Calculate overall sentiment score (-1 to 1 scale)
            total_articles = bullish + bearish + neutral
            if total_articles > 0:
                overall_sentiment = (bullish - bearish) / total_articles
            else:
                overall_sentiment = 0.0

            return {
                "overall_sentiment": overall_sentiment,
                "bullish_articles": bullish,
                "bearish_articles": bearish,
                "neutral_articles": neutral,
                "total_articles": total_articles,
            }

        except Exception as e:
            logger.error(f"Error in simple sentiment analysis: {e}")
            return {
                "overall_sentiment": 0.0,
                "bullish_articles": 0,
                "bearish_articles": 0,
                "neutral_articles": 0,
                "total_articles": len(news_items),
            }

    def get_market_sentiment(
        self, symbol: str, days_back: int = 7, limit: int = 50, **kwargs
    ) -> Dict:
        """
        Get market sentiment for a symbol.

        Args:
            symbol: Symbol or currency pair
            days_back: Number of days to look back
            limit: Maximum number of news items to fetch
            **kwargs: Additional arguments

        Returns:
            Dictionary with sentiment analysis results
        """
        # Fetch news data
        news_items = self.fetch_news_data(symbol, days_back, limit)

        # If no news found, return default values
        if not news_items:
            logger.warning(f"No news found for {symbol}")
            return {
                "overall_sentiment": 0.0,
                "bullish_articles": 0,
                "bearish_articles": 0,
                "neutral_articles": 0,
                "total_articles": 0,
            }

        # Analyze sentiment
        sentiment = self.analyze_sentiment(news_items, symbol)

        return sentiment

    def create_sentiment_features(
        self,
        market_data: pd.DataFrame,
        symbol: str,
        days_back: Optional[int] = None,
        limit: int = 50,
    ) -> pd.DataFrame:
        """
        Create sentiment features and integrate with market data.

        Args:
            market_data: DataFrame with market OHLCV data
            symbol: Symbol or currency pair
            days_back: Number of days to look back (if None, infers from data)
            limit: Maximum number of news items to fetch

        Returns:
            DataFrame with market data and sentiment features
        """
        # Create a copy to avoid modifying original
        df = market_data.copy()

        # Determine days_back if not provided
        if days_back is None and isinstance(df.index, pd.DatetimeIndex):
            start_date = df.index[0]
            end_date = df.index[-1]
            days_back = (end_date - start_date).days + 1
        elif days_back is None:
            days_back = 30  # Default to 30 days

        # Get market sentiment
        sentiment_data = self.get_market_sentiment(symbol, days_back, limit)

        # If no sentiment data, return original data
        if not sentiment_data or sentiment_data.get("total_articles", 0) == 0:
            logger.warning(
                f"No sentiment data available for {symbol}, returning original data"
            )
            return df

        # Add overall sentiment score as a feature
        overall_sentiment = sentiment_data.get("overall_sentiment", 0.0)
        df["sentiment_score"] = overall_sentiment

        # Add sentiment article counts
        df["bullish_news_count"] = sentiment_data.get("bullish_articles", 0)
        df["bearish_news_count"] = sentiment_data.get("bearish_articles", 0)
        df["neutral_news_count"] = sentiment_data.get("neutral_articles", 0)

        # Calculate bullish ratio
        total_articles = sentiment_data.get("total_articles", 0)
        if total_articles > 0:
            df["bullish_ratio"] = (
                sentiment_data.get("bullish_articles", 0) / total_articles
            )
            df["bearish_ratio"] = (
                sentiment_data.get("bearish_articles", 0) / total_articles
            )
        else:
            df["bullish_ratio"] = 0.5
            df["bearish_ratio"] = 0.5

        # Calculate sentiment momentum by creating a windowed version
        df["sentiment_ma5"] = (
            df["sentiment_score"].rolling(5).mean().fillna(df["sentiment_score"])
        )
        df["sentiment_ma10"] = (
            df["sentiment_score"].rolling(10).mean().fillna(df["sentiment_score"])
        )

        # Calculate sentiment momentum (difference between short and long MA)
        df["sentiment_momentum"] = df["sentiment_ma5"] - df["sentiment_ma10"]

        logger.info(
            f"Added sentiment features to market data with overall score: {overall_sentiment:.2f}"
        )
        return df


class IntegratedFeatureEngineer:
    """Integrates technical, economic, and sentiment features for ML model training."""

    def __init__(
        self,
        fred_api_key: Optional[str] = None,
        alpha_vantage_key: Optional[str] = None,
        use_cache: bool = True,
    ):
        """
        Initialize the integrated feature engineer.

        Args:
            fred_api_key: FRED API key (if None, loads from env var)
            alpha_vantage_key: Alpha Vantage API key (if None, loads from env var)
            use_cache: Whether to cache API responses
        """
        self.use_cache = use_cache

        # Initialize feature integrators
        self.economic_integrator = EconomicFeatureIntegrator(
            fred_api_key=fred_api_key, use_cache=use_cache
        )

        self.sentiment_integrator = SentimentFeatureIntegrator(
            alpha_vantage_key=alpha_vantage_key, use_cache=use_cache
        )

        logger.info("Initialized integrated feature engineer")

    def create_integrated_features(
        self,
        market_data: pd.DataFrame,
        symbol: str,
        include_economic: bool = True,
        include_sentiment: bool = True,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        economic_indicators: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Create integrated features combining market, economic, and sentiment data.

        Args:
            market_data: DataFrame with market OHLCV data
            symbol: Symbol or currency pair
            include_economic: Whether to include economic features
            include_sentiment: Whether to include sentiment features
            start_date: Start date for economic data
            end_date: End date for economic data
            economic_indicators: List of FRED series IDs to include

        Returns:
            DataFrame with integrated features
        """
        # Create a copy to avoid modifying original
        df = market_data.copy()

        # Add economic features if requested
        if include_economic:
            try:
                # Fetch economic indicators
                economic_data = self.economic_integrator.fetch_economic_indicators(
                    indicators=economic_indicators,
                    start_date=start_date,
                    end_date=end_date,
                )

                # Add economic features to market data
                if not economic_data.empty:
                    df = self.economic_integrator.create_economic_features(
                        df, economic_data
                    )
                    logger.info(f"Added {len(economic_data.columns)} economic features")
                else:
                    logger.warning(
                        "No economic data available, skipping economic features"
                    )
            except Exception as e:
                logger.error(f"Error adding economic features: {e}")

        # Add sentiment features if requested
        if include_sentiment:
            try:
                # Determine days back from market data
                days_back = None
                if isinstance(df.index, pd.DatetimeIndex):
                    start_date = df.index[0]
                    end_date = df.index[-1]
                    days_back = (end_date - start_date).days + 1

                # Add sentiment features to market data
                df = self.sentiment_integrator.create_sentiment_features(
                    df, symbol, days_back=days_back
                )
                logger.info("Added sentiment features")
            except Exception as e:
                logger.error(f"Error adding sentiment features: {e}")

        return df


def main():
    """Main function for demonstration."""
    # Parse command-line arguments
    import argparse

    parser = argparse.ArgumentParser(
        description="Integrate economic and sentiment features with market data"
    )
    parser.add_argument(
        "--symbol", type=str, default="GBPUSD", help="Symbol or currency pair"
    )
    parser.add_argument("--days", type=int, default=30, help="Number of days to fetch")
    parser.add_argument(
        "--economic", action="store_true", help="Include economic features"
    )
    parser.add_argument(
        "--sentiment", action="store_true", help="Include sentiment features"
    )
    parser.add_argument("--plot", action="store_true", help="Generate correlation plot")
    args = parser.parse_args()

    # Load market data (example: use yfinance for demo)
    try:
        import yfinance as yf

        print(f"Fetching market data for {args.symbol} (last {args.days} days)...")

        # Format symbol for forex if needed
        if len(args.symbol) == 6 and args.symbol.isalpha():
            yf_symbol = f"{args.symbol}=X"  # EURUSD to EURUSD=X
        else:
            yf_symbol = args.symbol

        # Get historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
        market_data = yf.download(
            yf_symbol, start=start_date, end=end_date, interval="1d"
        )

        if market_data.empty:
            print(f"No data available for {args.symbol}")
            return

        print(f"Loaded {len(market_data)} data points")

        # Create target variable (next day return)
        market_data["next_day_return"] = market_data["Close"].pct_change(1).shift(-1)
        market_data["target"] = np.where(market_data["next_day_return"] > 0, 1, -1)

        # Initialize integrated feature engineer
        engineer = IntegratedFeatureEngineer()

        # Create integrated features
        result = engineer.create_integrated_features(
            market_data,
            args.symbol,
            include_economic=args.economic,
            include_sentiment=args.sentiment,
        )

        # Print feature summary
        print(f"Original features: {len(market_data.columns)}")
        print(f"Enhanced features: {len(result.columns)}")
        print("\nNew feature columns:")
        new_cols = set(result.columns) - set(market_data.columns)
        for col in sorted(new_cols):
            print(f"- {col}")

        # Generate correlation plot if requested
        if args.plot and args.economic:
            print("\nAnalyzing feature importance...")
            # Extract just the economic columns
            eco_cols = [col for col in new_cols if not col.startswith("sentiment")]
            eco_data = result[eco_cols]

            importance_df, _ = engineer.economic_integrator.feature_importance_analysis(
                result, eco_data, "target", plot=True
            )

            print("\nTop economic features by correlation with target:")
            print(importance_df)

            # Display the plot
            plt.show()

        print("\nDone!")

    except ImportError:
        print("yfinance package not installed. Install with: pip install yfinance")
    except Exception as e:
        print(f"Error in demonstration: {e}")


if __name__ == "__main__":
    main()
