"""
Example of using Alpha Vantage for economic and commodity data in FXML4.

This script demonstrates how to use the AlphaVantageDataFeed class to fetch,
process, and analyze economic indicators and commodity price data.
"""

import os
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv

from fxml4.data_engineering.data_feeds.alpha_vantage_feed import AlphaVantageDataFeed

# Load environment variables
load_dotenv()

# Get API key from environment
api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
if not api_key:
    raise ValueError("ALPHA_VANTAGE_API_KEY not found in environment variables")

# Initialize the Alpha Vantage data feed
av_feed = AlphaVantageDataFeed(
    config={
        "api_key": api_key,
        "cache_data": True,
        "api_calls_per_minute": 5,  # Free tier limit
    }
)

# Example 1: Fetch GDP data (quarterly)
print("Fetching Real GDP data...")
gdp_data = av_feed.get_economic_indicator(
    indicator="REAL_GDP", interval="quarterly", outputsize="full"
)
print(f"Retrieved {len(gdp_data)} GDP data points")
print(gdp_data.head())

# Example 2: Fetch inflation data (annual)
print("\nFetching Inflation data...")
inflation_data = av_feed.get_economic_indicator(
    indicator="INFLATION", outputsize="full"
)
print(f"Retrieved {len(inflation_data)} inflation data points")
print(inflation_data.head())

# Example 3: Fetch unemployment data (monthly)
print("\nFetching Unemployment data...")
unemployment_data = av_feed.get_economic_indicator(
    indicator="UNEMPLOYMENT", outputsize="full"
)
print(f"Retrieved {len(unemployment_data)} unemployment data points")
print(unemployment_data.head())

# Example 4: Fetch treasury yield data (daily)
print("\nFetching Treasury Yield data...")
treasury_data = av_feed.get_economic_indicator(
    indicator="TREASURY_YIELD",
    interval="daily",
    maturity="10year",  # 10-year treasury yield
    outputsize="compact",
)
print(f"Retrieved {len(treasury_data)} treasury yield data points")
print(treasury_data.head())

# Example 5: Fetch WTI crude oil prices (daily)
print("\nFetching WTI crude oil price data...")
wti_data = av_feed.get_commodity_data(
    commodity="WTI", interval="daily", outputsize="compact"
)
print(f"Retrieved {len(wti_data)} WTI price data points")
print(wti_data.head())

# Example 6: Fetch natural gas prices (monthly)
print("\nFetching natural gas price data...")
gas_data = av_feed.get_commodity_data(
    commodity="NATURAL_GAS", interval="monthly", outputsize="full"
)
print(f"Retrieved {len(gas_data)} natural gas price data points")
print(gas_data.head())

# Data Analysis and Visualization

# Filter recent data (last 5 years)
five_years_ago = datetime.now() - timedelta(days=365 * 5)

# Calculate year-over-year changes
if not inflation_data.empty and len(inflation_data) > 12:
    print("\nCalculating economic trends...")

    # GDP growth rate
    if not gdp_data.empty and len(gdp_data) > 4:
        gdp_data = gdp_data[gdp_data.index >= five_years_ago]
        gdp_data["yoy_change"] = (
            gdp_data["value"].pct_change(4) * 100
        )  # 4 quarters = 1 year
        print(f"Latest GDP growth rate: {gdp_data['yoy_change'].iloc[-1]:.2f}%")

    # Latest inflation
    inflation_recent = inflation_data[inflation_data.index >= five_years_ago]
    print(f"Latest inflation rate: {inflation_recent['value'].iloc[-1]:.2f}%")

    # Latest unemployment
    unemployment_recent = unemployment_data[unemployment_data.index >= five_years_ago]
    print(f"Latest unemployment rate: {unemployment_recent['value'].iloc[-1]:.2f}%")

    # Plot economic indicators
    plt.figure(figsize=(12, 8))

    # Plot 1: GDP Growth
    if not gdp_data.empty and "yoy_change" in gdp_data.columns:
        plt.subplot(2, 2, 1)
        gdp_data["yoy_change"].plot(title="GDP Growth Rate (YoY %)")
        plt.grid(True)

    # Plot 2: Inflation
    plt.subplot(2, 2, 2)
    inflation_recent["value"].plot(title="Inflation Rate (%)")
    plt.grid(True)

    # Plot 3: Unemployment
    plt.subplot(2, 2, 3)
    unemployment_recent["value"].plot(title="Unemployment Rate (%)")
    plt.grid(True)

    # Plot 4: Treasury Yield
    if not treasury_data.empty:
        plt.subplot(2, 2, 4)
        treasury_data["value"].plot(title="10-Year Treasury Yield (%)")
        plt.grid(True)

    plt.tight_layout()
    plt.savefig("economic_indicators.png")
    print("Saved economic indicators plot to economic_indicators.png")

    # Commodity price analysis
    if not wti_data.empty and not gas_data.empty:
        print("\nAnalyzing commodity prices...")

        # Calculate 30-day moving average for WTI
        wti_recent = wti_data[wti_data.index >= five_years_ago]
        if len(wti_recent) > 30:
            wti_recent["30d_ma"] = wti_recent["value"].rolling(window=30).mean()

            # Calculate if price is above or below moving average
            wti_recent["above_ma"] = wti_recent["value"] > wti_recent["30d_ma"]
            above_pct = wti_recent["above_ma"].mean() * 100
            print(f"WTI price is above 30-day MA {above_pct:.1f}% of the time")

            # Current trend
            current_trend = (
                "UPTREND" if wti_recent["above_ma"].iloc[-1] else "DOWNTREND"
            )
            print(f"WTI current trend: {current_trend}")

            # Plot commodities
            plt.figure(figsize=(12, 6))

            # Plot 1: WTI with moving average
            plt.subplot(1, 2, 1)
            wti_recent["value"].plot(label="WTI Price")
            wti_recent["30d_ma"].plot(label="30-day MA", linestyle="--")
            plt.title("WTI Crude Oil Price")
            plt.legend()
            plt.grid(True)

            # Plot 2: Natural Gas
            plt.subplot(1, 2, 2)
            gas_recent = gas_data[gas_data.index >= five_years_ago]
            gas_recent["value"].plot()
            plt.title("Natural Gas Price")
            plt.grid(True)

            plt.tight_layout()
            plt.savefig("commodity_prices.png")
            print("Saved commodity prices plot to commodity_prices.png")

print("\nExamples completed successfully!")
