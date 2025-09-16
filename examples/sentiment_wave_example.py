"""Example script demonstrating sentiment-enhanced Elliott Wave analysis.

This script shows how to use the SentimentWaveValidator to combine
sentiment analysis with Elliott Wave pattern detection for enhanced validation.
"""

import logging
import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path to import fxml4 modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Elliott Wave modules
from fxml4.wave_analysis.elliott_wave import (
    ElliottWaveAnalyzer,
    ElliottWaveCount,
    ElliottWavePattern,
    WavePosition,
    WaveType,
)
from fxml4.wave_analysis.fibonacci import FibonacciCalculator


# Create our own simplified SentimentWaveValidator for the example
# This avoids dependency issues with external libraries like openai
class SentimentWaveValidator:
    """Simplified sentiment-enhanced Elliott Wave validator for examples.

    This class implements a basic version of the SentimentWaveValidator without
    external dependencies. In a real-world scenario, use the full implementation.
    """

    def __init__(self, wave_analyzer, sentiment_analyzer=None, rag=None, config=None):
        """Initialize the simplified validator.

        Args:
            wave_analyzer: Elliott Wave analyzer
            sentiment_analyzer: Market sentiment analyzer (optional)
            rag: RAG system (optional)
            config: Configuration dictionary (optional)
        """
        self.wave_analyzer = wave_analyzer
        self.sentiment_analyzer = sentiment_analyzer
        self.rag = rag
        self.config = config or {}

        # Configuration parameters
        self.sentiment_weight = self.config.get("sentiment_weight", 0.3)
        self.rag_weight = self.config.get("rag_weight", 0.3)
        self.wave_weight = self.config.get("wave_weight", 0.4)
        self.min_confidence = self.config.get("min_confidence", 0.6)

    def validate_wave_pattern(
        self, pattern, price_data, news_data=None, pattern_position="END"
    ):
        """Validate a wave pattern using sentiment analysis.

        Args:
            pattern: Elliott Wave pattern
            price_data: Price data
            news_data: News data (optional)
            pattern_position: Position in pattern (START, MIDDLE, END)

        Returns:
            Tuple of (is_valid, confidence, details)
        """
        validation_details = {}

        # Get base confidence from wave pattern
        base_confidence = pattern.confidence
        validation_details["wave_confidence"] = base_confidence

        # Get sentiment from price or news
        if news_data is None:
            sentiment_score = self._get_sentiment_from_price(price_data)
        elif self.sentiment_analyzer:
            sentiment_score = self.sentiment_analyzer.analyze_sentiment(news_data)
        else:
            sentiment_score = 0.5  # Neutral

        validation_details["sentiment_score"] = sentiment_score

        # Use RAG for pattern validation if available
        rag_confidence = 0.7  # Default
        if self.rag:
            # Simulate RAG call
            pattern_type = pattern.wave_type.value
            if "IMPULSE" in pattern_type:
                rag_confidence = 0.85
            elif "CORRECTION" in pattern_type:
                rag_confidence = 0.72
            else:
                rag_confidence = 0.65

        validation_details["rag_confidence"] = rag_confidence

        # Calculate sentiment confidence
        # Higher if sentiment aligns with pattern type
        if pattern.wave_type == WaveType.IMPULSE and sentiment_score > 0:
            sentiment_confidence = 0.8
        elif pattern.wave_type == WaveType.CORRECTION and sentiment_score < 0:
            sentiment_confidence = 0.8
        else:
            sentiment_confidence = 0.5

        validation_details["sentiment_confidence"] = sentiment_confidence

        # Combine confidence scores
        combined_confidence = (
            base_confidence * self.wave_weight
            + sentiment_confidence * self.sentiment_weight
            + rag_confidence * self.rag_weight
        )

        # Determine if pattern is valid
        is_valid = combined_confidence >= self.min_confidence

        return is_valid, combined_confidence, validation_details

    def _get_sentiment_from_price(self, price_data):
        """Extract sentiment score from price action.

        Args:
            price_data: Price data

        Returns:
            Sentiment score (-1 to 1)
        """
        # Use the most recent N periods
        recent_data = price_data.tail(20)

        # Calculate return
        returns = (recent_data["close"].pct_change() * 100).dropna()

        # Calculate RSI if not in data
        if "rsi" not in recent_data.columns:
            # Simple RSI calculation (14-period)
            delta = recent_data["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            recent_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
        else:
            recent_rsi = recent_data["rsi"].iloc[-1]

        # Get price trend
        price_trend = returns.mean()

        # Convert RSI to -1 to 1 scale (50 is neutral)
        rsi_score = (recent_rsi - 50) / 50

        # Combine with price trend
        sentiment_score = (rsi_score * 0.7) + (np.sign(price_trend) * 0.3)

        # Ensure result is between -1 and 1
        sentiment_score = min(max(sentiment_score, -1.0), 1.0)

        return sentiment_score

    def analyze_with_sentiment(self, price_data, news_data=None):
        """Analyze price data with sentiment-enhanced validation.

        Args:
            price_data: Price data
            news_data: News data (optional)

        Returns:
            Dictionary with analysis results
        """
        results = {
            "patterns": [],
            "validation": [],
            "combined_score": 0.0,
        }

        # Step 1: Perform Elliott Wave analysis
        wave_count = self.wave_analyzer.analyze(price_data)

        if not wave_count or not wave_count.waves:
            return results

        # Step 2: Get sentiment score
        if news_data is None:
            sentiment_score = self._get_sentiment_from_price(price_data)
        elif self.sentiment_analyzer:
            sentiment_score = self.sentiment_analyzer.analyze_sentiment(news_data)
        else:
            sentiment_score = 0.5  # Neutral

        results["sentiment_score"] = sentiment_score

        # Step 3: Validate each wave pattern
        validated_patterns = []
        for wave in wave_count.waves:
            # Skip low confidence patterns
            if wave.confidence < 0.4:
                continue

            # Determine pattern position
            if wave.position:
                pattern_position = wave.position.value
            else:
                pattern_position = "END"

            # Validate pattern
            is_valid, confidence, details = self.validate_wave_pattern(
                wave, price_data, news_data, pattern_position
            )

            # Add to results
            validated_patterns.append(
                {
                    "pattern": wave.to_dict(),
                    "is_valid": is_valid,
                    "confidence": confidence,
                    "details": details,
                }
            )

        # Add patterns to results
        results["patterns"] = [wave.to_dict() for wave in wave_count.waves]
        results["validation"] = validated_patterns

        # Calculate combined confidence score
        valid_patterns = [p for p in validated_patterns if p["is_valid"]]
        if valid_patterns:
            results["combined_score"] = sum(
                p["confidence"] for p in valid_patterns
            ) / len(valid_patterns)

        return results


# Mock sentiment analyzer for the example (to avoid API calls)
class MockSentimentAnalyzer:
    def analyze_sentiment(self, news_data):
        """Return a mock sentiment score."""
        # If we have real news data, generate sentiment based on date
        if isinstance(news_data, pd.DataFrame) and len(news_data) > 0:
            # Use date to create a cyclical sentiment pattern
            if "date" in news_data.columns:
                latest_date = pd.to_datetime(news_data["date"]).max()
                # Create a simple oscillation based on day of month
                day_of_month = latest_date.day
                sentiment = np.sin(2 * np.pi * day_of_month / 30) * 0.5 + 0.2
                return sentiment

        # Default sentiment for price-only analysis
        return 0.4  # Slightly bullish


# Mock RAG for the example (to avoid API calls)
class MockRAG:
    def query(self, query_text):
        """Return a mock response based on the query content."""
        if "IMPULSE" in query_text:
            return """
            This appears to be a valid impulse wave pattern. The wave structure shows good
            adherence to Elliott Wave rules with proper proportions between waves 1, 3, and 5.
            The sentiment is aligned with what we would expect at this position.

            Confidence: 0.85
            """
        elif "CORRECTION" in query_text:
            return """
            This correction pattern generally follows Elliott Wave principles.
            The retracement levels are within typical ranges and the pattern structure
            is consistent with a correction wave.

            Confidence: 0.72
            """
        elif "DIAGONAL" in query_text:
            return """
            This diagonal pattern has some characteristics of a proper diagonal,
            but there are some inconsistencies in the wave structure.

            Confidence: 0.65
            """
        else:
            return """
            The pattern appears to follow Elliott Wave principles with reasonable confidence.

            Confidence: 0.70
            """


def generate_sample_data(pattern_type="impulse", with_noise=True):
    """Generate sample price data with the specified Elliott Wave pattern.

    Args:
        pattern_type: Type of pattern to generate (impulse, correction, diagonal).
        with_noise: Whether to add random noise to the data.

    Returns:
        DataFrame with OHLCV data.
    """
    # Base parameters
    n_samples = 100
    dates = pd.date_range(start="2025-01-01", periods=n_samples, freq="H")
    noise_level = 0.8 if with_noise else 0.0

    # Generate base data
    data = pd.DataFrame(
        {
            "open": np.zeros(n_samples),
            "high": np.zeros(n_samples),
            "low": np.zeros(n_samples),
            "close": np.zeros(n_samples),
            "volume": np.random.randint(100, 1000, n_samples),
        },
        index=dates,
    )

    # Add noise to volume
    data["volume"] = data["volume"] * (1 + np.random.normal(0, 0.2, n_samples))

    # Pattern-specific price generation
    if pattern_type == "impulse":
        # Wave 1: Bullish move
        data.loc[dates[0:20], "close"] = np.linspace(100, 110, 20)
        # Wave 2: Correction (not exceeding start of wave 1)
        data.loc[dates[20:30], "close"] = np.linspace(110, 103, 10)
        # Wave 3: Strong bullish move (longest)
        data.loc[dates[30:60], "close"] = np.linspace(103, 125, 30)
        # Wave 4: Correction (not overlapping with wave 1)
        data.loc[dates[60:70], "close"] = np.linspace(125, 118, 10)
        # Wave 5: Final bullish move
        data.loc[dates[70:100], "close"] = np.linspace(118, 130, 30)

    elif pattern_type == "correction":
        # Wave A: Initial bearish move
        data.loc[dates[0:30], "close"] = np.linspace(100, 85, 30)
        # Wave B: Partial recovery
        data.loc[dates[30:50], "close"] = np.linspace(85, 95, 20)
        # Wave C: Final bearish move
        data.loc[dates[50:100], "close"] = np.linspace(95, 78, 50)

    elif pattern_type == "diagonal":
        # Ending diagonal pattern (contracting)
        # Wave 1: Initial bullish move
        data.loc[dates[0:20], "close"] = np.linspace(100, 110, 20)
        # Wave 2: Correction
        data.loc[dates[20:35], "close"] = np.linspace(110, 104, 15)
        # Wave 3: Bullish move (shorter than wave 1)
        data.loc[dates[35:50], "close"] = np.linspace(104, 112, 15)
        # Wave 4: Correction
        data.loc[dates[50:65], "close"] = np.linspace(112, 108, 15)
        # Wave 5: Final bullish move (shorter than wave 3)
        data.loc[dates[65:100], "close"] = np.linspace(108, 114, 35)

    else:
        # Default to a simple uptrend
        data.loc[dates, "close"] = np.linspace(100, 130, n_samples)

    # Add random noise if requested
    if with_noise:
        noise = np.random.normal(0, noise_level, n_samples)
        data["close"] = data["close"] + noise

    # Fill in the open, high, low based on close
    data["open"] = data["close"].shift(1)
    data["open"].iloc[0] = data["close"].iloc[0] - 0.5

    for i in range(len(data)):
        # High is max of current close and previous close plus some randomness
        if i == 0:
            data.loc[dates[i], "high"] = data.loc[dates[i], "close"] + 0.5
        else:
            data.loc[dates[i], "high"] = max(
                data.loc[dates[i], "close"], data.loc[dates[i], "open"]
            ) + np.random.uniform(0.3, 1.0)

        # Low is min of current close and previous close minus some randomness
        data.loc[dates[i], "low"] = min(
            data.loc[dates[i], "close"], data.loc[dates[i], "open"]
        ) - np.random.uniform(0.3, 1.0)

    # Calculate some technical indicators
    # RSI (simplified calculation)
    delta = data["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    data["rsi"] = 100 - (100 / (1 + rs))
    data["rsi"].fillna(50, inplace=True)

    return data


def generate_sample_news(dates, sentiment_bias=0.0):
    """Generate sample news data with sentiment bias.

    Args:
        dates: DatetimeIndex for the news data.
        sentiment_bias: Bias to add to sentiment (-1 to +1).

    Returns:
        DataFrame with news data.
    """
    # Sample positive and negative headlines
    positive_headlines = [
        "Market shows strong signs of recovery",
        "Investors optimistic about economic outlook",
        "Central bank signals supportive stance",
        "Economic data exceeds expectations",
        "Strong earnings boost market sentiment",
    ]

    negative_headlines = [
        "Market concerns grow over economic slowdown",
        "Investors cautious amid uncertainty",
        "Central bank warns of risks ahead",
        "Economic data disappoints analysts",
        "Weak earnings weigh on market sentiment",
    ]

    # Select a subset of dates for news (not every day has news)
    news_dates = pd.DatetimeIndex([d for d in dates if np.random.random() > 0.7])

    # Generate news with sentiment aligned to the price trend
    n_news = len(news_dates)
    news_data = pd.DataFrame(
        {
            "date": news_dates,
            "headline": [""] * n_news,
            "content": [""] * n_news,
            "sentiment": np.zeros(n_news),
        }
    )

    # Fill in news data
    for i, date in enumerate(news_dates):
        # Determine sentiment based on position in the date range
        position = np.where(dates == date)[0][0] / len(dates)

        # Base sentiment follows a pattern plus bias
        base_sentiment = np.sin(position * 4 * np.pi) * 0.5 + sentiment_bias

        # Add some randomness
        sentiment = min(1.0, max(-1.0, base_sentiment + np.random.normal(0, 0.3)))

        # Select headline based on sentiment
        if sentiment > 0:
            headline = np.random.choice(positive_headlines)
            content = f"Positive market news: {headline.lower()}. Analysts suggest this could lead to continued strength."
        else:
            headline = np.random.choice(negative_headlines)
            content = f"Negative market news: {headline.lower()}. Analysts express concerns about market direction."

        news_data.loc[i, "headline"] = headline
        news_data.loc[i, "content"] = content
        news_data.loc[i, "sentiment"] = sentiment

    return news_data


def plot_results(price_data, analysis_results, news_data=None, save_path=None):
    """Plot price data with wave patterns and sentiment.

    Args:
        price_data: DataFrame with price data.
        analysis_results: Results from sentiment-enhanced wave analysis.
        news_data: Optional news data.
        save_path: Path to save the plot (if None, display interactively).
    """
    plt.figure(figsize=(14, 10))

    # Plot 1: Price chart with wave patterns
    ax1 = plt.subplot(2, 1, 1)
    ax1.plot(price_data.index, price_data["close"], label="Price")
    ax1.set_title("Price with Wave Patterns")
    ax1.set_ylabel("Price")

    # Highlight wave patterns
    if "patterns" in analysis_results and analysis_results["patterns"]:
        for pattern in analysis_results["patterns"]:
            if "start_idx" in pattern and "end_idx" in pattern:
                start_idx = pattern["start_idx"]
                end_idx = pattern["end_idx"]

                # Check if indices are valid
                if 0 <= start_idx < len(price_data) and 0 <= end_idx < len(price_data):
                    start_date = price_data.index[start_idx]
                    end_date = price_data.index[end_idx]

                    # Get pattern information
                    pattern_type = pattern.get("wave_type", "UNKNOWN")
                    confidence = pattern.get("confidence", 0)

                    # Highlight the pattern zone
                    ax1.axvspan(
                        start_date,
                        end_date,
                        alpha=0.2,
                        color=(
                            "green"
                            if pattern_type == "IMPULSE"
                            else "red" if pattern_type == "CORRECTION" else "orange"
                        ),
                    )

                    # Add label
                    mid_x = start_date + (end_date - start_date) / 2
                    y_pos = price_data.loc[start_date:end_date, "close"].max()
                    ax1.text(
                        mid_x,
                        y_pos,
                        f"{pattern_type}\n({confidence:.2f})",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                        bbox=dict(facecolor="white", alpha=0.6),
                    )

    # Plot 2: Sentiment and RSI
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)

    # Plot RSI if available
    if "rsi" in price_data.columns:
        ax2.plot(price_data.index, price_data["rsi"], "b-", label="RSI")
        ax2.axhline(y=70, color="r", linestyle="--", alpha=0.3)
        ax2.axhline(y=30, color="g", linestyle="--", alpha=0.3)
        ax2.axhline(y=50, color="k", linestyle="--", alpha=0.3)
        ax2.set_ylabel("RSI")

    # Create secondary y-axis for sentiment
    ax3 = ax2.twinx()

    # Plot overall sentiment score
    if "sentiment_score" in analysis_results:
        sentiment_score = analysis_results["sentiment_score"]
        ax3.axhline(
            y=sentiment_score,
            color="purple",
            linestyle="-",
            label=f"Overall Sentiment: {sentiment_score:.2f}",
        )

    # Plot news sentiment if available
    if news_data is not None and len(news_data) > 0:
        ax3.scatter(
            news_data["date"],
            news_data["sentiment"],
            color="purple",
            alpha=0.7,
            label="News Sentiment",
        )

    ax3.set_ylabel("Sentiment Score")
    ax3.set_ylim(-1.1, 1.1)

    # Format dates on x-axis
    plt.gcf().autofmt_xdate()

    # Add combined legend
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines3, labels3 = ax3.get_legend_handles_labels()
    ax3.legend(lines1 + lines3, labels1 + labels3, loc="upper left")

    # Add validation results as text
    if "validation" in analysis_results and analysis_results["validation"]:
        validation_text = "Validation Results:\n"
        for i, val in enumerate(analysis_results["validation"]):
            if "is_valid" in val and "confidence" in val:
                status = "✅" if val["is_valid"] else "❌"
                validation_text += f"{status} Pattern {i+1}: {val['confidence']:.2f}\n"

        if "combined_score" in analysis_results:
            validation_text += (
                f"\nCombined Score: {analysis_results['combined_score']:.2f}"
            )

        # Add text box with validation results
        props = dict(boxstyle="round", facecolor="wheat", alpha=0.5)
        ax1.text(
            0.02,
            0.02,
            validation_text,
            transform=ax1.transAxes,
            fontsize=9,
            verticalalignment="bottom",
            bbox=props,
        )

    plt.tight_layout()

    # Save or show the plot
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path)
        plt.close()
        logger.info(f"Plot saved to {save_path}")
    else:
        plt.show()


def main():
    """Run the sentiment-enhanced Elliott Wave analysis example."""
    logger.info("Starting sentiment-enhanced Elliott Wave analysis example")

    # Generate sample data
    pattern_types = ["impulse", "correction", "diagonal"]

    for i, pattern_type in enumerate(pattern_types):
        logger.info(f"Analyzing {pattern_type} pattern")

        # Generate sample data with the specified pattern type
        price_data = generate_sample_data(pattern_type=pattern_type, with_noise=True)

        # Generate sample news data
        news_data = generate_sample_news(
            price_data.index,
            sentiment_bias=(
                0.3
                if pattern_type == "impulse"
                else -0.3 if pattern_type == "correction" else 0.0
            ),
        )

        # Initialize components
        wave_analyzer = ElliottWaveAnalyzer()
        fib_calculator = FibonacciCalculator()
        sentiment_analyzer = MockSentimentAnalyzer()
        rag = MockRAG()

        # Initialize sentiment-enhanced wave validator
        validator = SentimentWaveValidator(
            wave_analyzer=wave_analyzer,
            sentiment_analyzer=sentiment_analyzer,
            rag=rag,
            config={
                "sentiment_weight": 0.3,
                "rag_weight": 0.3,
                "wave_weight": 0.4,
                "min_confidence": 0.6,
            },
        )

        # Perform analysis
        analysis_results = validator.analyze_with_sentiment(
            price_data=price_data, news_data=news_data
        )

        # Create output directory if it doesn't exist
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "output",
            "sentiment_wave",
        )
        os.makedirs(output_dir, exist_ok=True)

        # Plot and save results
        save_path = os.path.join(output_dir, f"{pattern_type}_pattern_analysis.png")
        plot_results(price_data, analysis_results, news_data, save_path)

        # Log results summary
        if "validation" in analysis_results and analysis_results["validation"]:
            valid_count = sum(
                1 for v in analysis_results["validation"] if v.get("is_valid", False)
            )
            logger.info(
                f"{valid_count} out of {len(analysis_results['validation'])} patterns validated"
            )
            logger.info(
                f"Combined confidence score: {analysis_results.get('combined_score', 0):.2f}"
            )


if __name__ == "__main__":
    main()
