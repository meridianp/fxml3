# Alpha Vantage Integration for FXML4

This document provides an overview of the Alpha Vantage integration in FXML4 and examples of how to use it to access financial market data, economic indicators, and commodity prices.

## Overview

Alpha Vantage is a comprehensive financial data provider offering APIs for stock, forex, cryptocurrency, technical indicators, economic data, and commodities. The FXML4 system integrates with Alpha Vantage to offer an alternative data source to Interactive Brokers for both historical and current market data, as well as exogenous economic data.

## Features

- **Market Data**: Access to forex, stocks, ETFs, and other financial instruments
- **Multiple Timeframes**: Support for timeframes from 1-minute to monthly (1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M)
- **Economic Indicators**: Access to major economic indicators like GDP, inflation, unemployment
- **Commodity Prices**: Data for energy, metals, and agricultural commodities
- **Symbol Search**: Ability to search for symbols by keywords
- **Exchange Rates**: Access to real-time currency exchange rates
- **Caching**: Efficient caching to minimize API calls
- **Rate Limiting**: Built-in rate limiting to respect API usage limits

## Configuration

To use Alpha Vantage, you need an API key. You can get a free API key from the [Alpha Vantage website](https://www.alphavantage.co/support/#api-key).

Add your API key to the configuration in `config/default.yaml`:

```yaml
data_feeds:
  alpha_vantage:
    enabled: true
    api_key: "YOUR_API_KEY"  # Add your API key here
    cache_data: true
    cache_expiry: 3600  # Cache for 1 hour
    api_calls_per_minute: 5  # Free tier limit
    symbols: ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "MSFT", "AAPL", "GOOGL", "AMZN"]
```

## Basic Usage Examples

### 1. Fetching Forex Data

```python
from fxml4.data_engineering.data_feeds.alpha_vantage_feed import AlphaVantageDataFeed
from fxml4.config import get_data_feed_config

# Get configuration from config file
config = get_data_feed_config("alpha_vantage")

# Create the data feed
feed = AlphaVantageDataFeed(config)

# Fetch daily data for EUR/USD for the last 30 days
data = feed.fetch_data(
    symbol="EURUSD",
    timeframe="1d",
    data_type="forex"
)

# Display the data
print(data.head())
```

### 2. Fetching Stock Data

```python
# Fetch daily data for Microsoft (MSFT)
data = feed.fetch_data(
    symbol="MSFT",
    timeframe="1d",
    data_type="stock",
    adjusted=True  # Get adjusted prices
)

# Display the data
print(data.head())
```

### 3. Fetching Intraday Data

```python
# Fetch 5-minute data for IBM
data = feed.fetch_data(
    symbol="IBM",
    timeframe="5m",
    data_type="stock"
)

# Display the data
print(data.head())
```

### 4. Searching for Symbols

```python
# Search for Apple
results = feed.search_symbol("Apple")

# Display the results
print(results)
```

### 5. Getting Exchange Rates

```python
# Get the EUR/USD exchange rate
exchange_rate = feed.get_exchange_rate("EUR", "USD")

# Display the exchange rate
print(f"EUR/USD: {exchange_rate['exchange_rate']}")
```

## Advanced Usage

### 1. Time-Based Filtering

```python
from datetime import datetime, timedelta

# Calculate start and end dates
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

# Fetch data for the last 30 days
data = feed.fetch_data(
    symbol="GBPUSD",
    timeframe="1h",
    start_date=start_date,
    end_date=end_date,
    data_type="forex"
)
```

### 2. Clearing the Cache

```python
# Clear the data cache
feed.clear_cache()
```

### 3. Handling Rate Limits

The AlphaVantageDataFeed automatically handles rate limiting to ensure you don't exceed the API call limits. However, if you need to monitor usage:

```python
# Get the current call interval
call_interval = feed.call_interval
print(f"API calls are limited to 1 call every {call_interval:.2f} seconds")
```

## Economic Indicators

Alpha Vantage provides access to major economic indicators:

```python
# Get Real GDP (quarterly)
gdp_data = feed.get_economic_indicator(
    indicator="REAL_GDP",
    interval="quarterly",
    outputsize="full"
)

# Get inflation data (annual)
inflation_data = feed.get_economic_indicator(
    indicator="INFLATION",
    outputsize="full"
)

# Get unemployment data (monthly)
unemployment_data = feed.get_economic_indicator(
    indicator="UNEMPLOYMENT",
    outputsize="full"
)

# Get treasury yield (10-year, daily)
treasury_data = feed.get_economic_indicator(
    indicator="TREASURY_YIELD",
    interval="daily",
    maturity="10year",
    outputsize="compact"
)
```

### Available Economic Indicators

| Indicator | Description | Frequency |
|-----------|-------------|-----------|
| `REAL_GDP` | US Real Gross Domestic Product | Annual, Quarterly |
| `REAL_GDP_PER_CAPITA` | US Real GDP per Capita | Quarterly |
| `TREASURY_YIELD` | US Treasury Yields | Daily, Weekly, Monthly |
| `FEDERAL_FUNDS_RATE` | US Federal Funds Rate | Daily, Weekly, Monthly |
| `CPI` | US Consumer Price Index | Monthly, Semiannual |
| `INFLATION` | US Inflation Rate | Annual |
| `RETAIL_SALES` | US Retail Sales | Monthly |
| `DURABLES` | US Durable Goods Orders | Monthly |
| `UNEMPLOYMENT` | US Unemployment Rate | Monthly |
| `NONFARM_PAYROLL` | US Nonfarm Payroll | Monthly |

## Commodity Data

Commodity price data is available through the `get_commodity_data` method:

```python
# Get WTI crude oil prices (daily)
wti_data = feed.get_commodity_data(
    commodity="WTI",
    interval="daily",
    outputsize="compact"
)

# Get natural gas prices (monthly)
gas_data = feed.get_commodity_data(
    commodity="NATURAL_GAS",
    interval="monthly",
    outputsize="full"
)

# Get copper prices (monthly)
copper_data = feed.get_commodity_data(
    commodity="COPPER",
    interval="monthly"
)
```

### Available Commodities

| Commodity | Description | Frequency |
|-----------|-------------|-----------|
| `WTI` | West Texas Intermediate (WTI) Crude Oil | Daily, Weekly, Monthly |
| `BRENT` | Brent (Europe) Crude Oil | Daily, Weekly, Monthly |
| `NATURAL_GAS` | Henry Hub Natural Gas | Daily, Weekly, Monthly |
| `COPPER` | Global Copper | Monthly, Quarterly, Annual |
| `ALUMINUM` | Global Aluminum | Monthly, Quarterly, Annual |
| `WHEAT` | Global Wheat | Monthly, Quarterly, Annual |
| `CORN` | Global Corn | Monthly, Quarterly, Annual |
| `COTTON` | Global Cotton | Monthly, Quarterly, Annual |
| `SUGAR` | Global Sugar | Monthly, Quarterly, Annual |
| `COFFEE` | Global Coffee | Monthly, Quarterly, Annual |
| `ALL_COMMODITIES` | Global Commodity Price Index | Monthly, Quarterly, Annual |

## Testing Connectivity

To test your connection to Alpha Vantage, run:

```bash
# Test with demo API key (limited functionality)
python scripts/test_alpha_vantage_access.py

# Test with your own API key
python scripts/test_alphavantage_feed.py --api-key YOUR_API_KEY
```

## API Rate Limits

- **Free API Key**: Limited to 5 API requests per minute and 500 requests per day
- **Premium API Key**: Up to 75 API requests per minute and 2500+ requests per day

The FXML4 codebase now fully supports premium tier API keys with automatic rate limit adjustment and improved data retrieval capabilities. Premium tier access is configured in the YAML configuration file:

```yaml
data_feeds:
  alpha_vantage:
    enabled: true
    api_key: "YOUR_PREMIUM_API_KEY"
    cache_data: true
    cache_expiry: 3600  # Cache for 1 hour
    api_calls_per_minute: 75  # Premium tier limit
    premium_tier: true  # Enable premium tier features
    symbols: ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "MSFT", "AAPL", "GOOGL", "AMZN"]
```

With premium tier enabled, the system automatically:
1. Adjusts rate limiting to allow up to 75 calls per minute
2. Sets all output sizes to "full" to retrieve complete historical datasets
3. Enhances logging with tier information

## Troubleshooting

1. **API Key Issues**: Ensure your API key is correct in the configuration
2. **Rate Limiting**: If you get rate limit errors, reduce the frequency of your requests
3. **Symbol Format**: For forex pairs, both "EURUSD" and "EUR.USD" formats are accepted
4. **Timeframe Format**: Use standard timeframe strings like "1m", "5m", "1h", "1d"

## Example Code

A complete example showing how to fetch, analyze, and visualize economic indicators and commodity data is available in:

```
docs/examples/alpha_vantage_economic_example.py
```

Run the example with:

```bash
python docs/examples/alpha_vantage_economic_example.py
```

## See Also

- [Alpha Vantage API Reference](alpha-vantage-api.md) - Complete list of all Alpha Vantage endpoints
- [Exogenous Data Integration Guide](exogenous_data_integration.md) - Guide to using economic data in trading strategies
