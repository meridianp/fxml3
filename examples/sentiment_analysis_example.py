#!/usr/bin/env python3
"""
Sentiment Analysis Example for Forex Trading

This example demonstrates how to use the sentiment analysis module
to analyze market sentiment for forex trading.
"""

import argparse
import json
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import sentiment analysis components
try:
    from fxml4.llm_integration.sentiment_analysis import SentimentAgent
except ImportError:
    print("Error importing SentimentAgent. Check that the fxml4 module is installed.")
    exit(1)


def plot_sentiment_timeseries(timeseries, symbol):
    """Plot sentiment timeseries data."""
    if not timeseries:
        print("No timeseries data available to plot.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(timeseries)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)

    # Plot sentiment
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    # Sentiment score
    axes[0].plot(df.index, df["weighted_sentiment"], "b-", label="Weighted Sentiment")
    axes[0].plot(df.index, df["sentiment_ma5"], "r-", label="5-day MA")
    axes[0].plot(df.index, df["sentiment_ma10"], "g-", label="10-day MA")
    axes[0].axhline(y=0, color="k", linestyle="-", alpha=0.3)
    axes[0].set_title(f"Market Sentiment for {symbol}")
    axes[0].set_ylabel("Sentiment Score")
    axes[0].legend()
    axes[0].grid(True)

    # Momentum and divergence
    axes[1].plot(df.index, df["sentiment_momentum"], "c-", label="Momentum")
    axes[1].plot(df.index, df["sentiment_divergence"], "m-", label="Divergence")
    axes[1].axhline(y=0, color="k", linestyle="-", alpha=0.3)
    axes[1].set_ylabel("Momentum/Divergence")
    axes[1].legend()
    axes[1].grid(True)

    # News count
    axes[2].bar(df.index, df["news_count"], color="orange", label="News Count")
    axes[2].set_ylabel("News Count")
    axes[2].set_xlabel("Date")
    axes[2].legend()
    axes[2].grid(True)

    plt.tight_layout()
    plt.savefig(f"sentiment_analysis_{symbol}.png")
    plt.show()

    print(f"Plot saved as sentiment_analysis_{symbol}.png")


def display_sentiment_summary(sentiment_data, symbol):
    """Display sentiment summary information."""
    if (
        "data" not in sentiment_data
        or "sentiment_summary" not in sentiment_data["data"]
    ):
        print("No sentiment summary available.")
        return

    summary = sentiment_data["data"]["sentiment_summary"]

    print("\n" + "=" * 50)
    print(f"MARKET SENTIMENT SUMMARY FOR {symbol}")
    print("=" * 50)

    # Overall sentiment
    print(f"Overall Sentiment: {summary.get('overall', 'neutral').upper()}")
    print(f"Weighted Score: {summary.get('weighted_score', 0):.2f} (-1.0 to 1.0 scale)")
    print(f"Confidence: {summary.get('confidence', 0):.2f}/10")

    # Momentum/trend
    if "momentum" in summary:
        momentum = summary["momentum"]
        print(
            f"Sentiment Momentum: {momentum:.2f} ({'Increasing' if momentum > 0 else 'Decreasing' if momentum < 0 else 'Stable'})"
        )

    if "divergence" in summary:
        divergence = summary["divergence"]
        print(
            f"Sentiment Divergence: {divergence:.2f} ({'Bullish' if divergence > 0.2 else 'Bearish' if divergence < -0.2 else 'Neutral'})"
        )

    # News count
    news_count = sentiment_data["data"].get("news_count", 0)
    print(f"News Articles Analyzed: {news_count}")

    # Top news items
    top_news = sentiment_data["data"].get("top_news", [])
    if top_news:
        print("\nTOP NEWS ARTICLES:")
        print("-" * 50)
        for i, item in enumerate(top_news[:3]):  # Show top 3 articles
            sentiment = item.get("sentiment_analysis", {})
            sentiment_type = sentiment.get("sentiment", "neutral")
            intensity = sentiment.get("intensity", 5)
            relevance = sentiment.get("relevance", 5)

            print(
                f"{i+1}. {item.get('title', 'No Title')} ({item.get('publisher', 'Unknown')})"
            )
            print(
                f"   Sentiment: {sentiment_type.upper()} (Intensity: {intensity}/10, Relevance: {relevance}/10)"
            )
            print(
                f"   Key factors: {', '.join(sentiment.get('key_factors', ['None']))}"
            )
            print(f"   Published: {item.get('publish_date', 'Unknown')}")
            print(f"   URL: {item.get('url', 'N/A')}")
            print()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Analyze market sentiment for forex trading."
    )
    parser.add_argument(
        "--symbol", "-s", type=str, default="GBPUSD", help="Symbol or currency pair"
    )
    parser.add_argument(
        "--days", "-d", type=int, default=30, help="Number of days to look back"
    )
    parser.add_argument(
        "--plot", "-p", action="store_true", help="Plot sentiment timeseries"
    )
    parser.add_argument(
        "--output", "-o", type=str, help="Output JSON file for sentiment data"
    )
    args = parser.parse_args()

    # Create sentiment agent
    print(f"Initializing sentiment analysis for {args.symbol}...")
    agent = SentimentAgent()

    # Get market sentiment
    print(f"Analyzing market sentiment for the past {args.days} days...")
    sentiment_data = agent.get_market_sentiment(
        symbol=args.symbol, days_back=args.days, timeframe="daily"
    )

    # Display summary
    display_sentiment_summary(sentiment_data, args.symbol)

    # Plot timeseries if requested
    if (
        args.plot
        and "data" in sentiment_data
        and "timeseries" in sentiment_data["data"]
    ):
        plot_sentiment_timeseries(sentiment_data["data"]["timeseries"], args.symbol)

    # Save to JSON if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(sentiment_data, f, indent=2)
        print(f"Sentiment data saved to {args.output}")

    print("\nDone!")


if __name__ == "__main__":
    main()
