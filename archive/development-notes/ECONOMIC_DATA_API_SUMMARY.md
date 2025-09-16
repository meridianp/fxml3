# Economic Data APIs for Forex Correlation Analysis

## Overview
This document summarizes the available economic indicators and market data from Alpha Vantage and FRED APIs that are relevant for forex correlation analysis.

## Alpha Vantage API (API Key: V10FRLTU9WKTQMD9)

### Installation
```bash
pip install alpha-vantage
```

### Available Data Categories

#### 1. Forex Data
- Real-time and historical exchange rates
- Support for all major currency pairs
- Daily, weekly, and monthly intervals
- Intraday data (1min, 5min, 15min, 30min, 60min)

```python
from alpha_vantage.foreignexchange import ForeignExchange
cc = ForeignExchange(key='V10FRLTU9WKTQMD9')
data, _ = cc.get_currency_exchange_rate(from_currency='EUR', to_currency='USD')
```

#### 2. Economic Indicators
- **GDP** - Gross Domestic Product
- **INFLATION** - US inflation rates
- **CONSUMER_SENTIMENT** - University of Michigan Consumer Surveys
- **TREASURY_YIELD** - US treasury yields
- **FEDERAL_FUNDS_RATE** - Federal funds rate
- **CPI** - Consumer Price Index
- **UNEMPLOYMENT** - Unemployment rate
- **NONFARM_PAYROLL** - Nonfarm payroll data

Note: Economic indicators require direct API calls using requests library:
```python
import requests
url = f'https://www.alphavantage.co/query?function=INFLATION&apikey=V10FRLTU9WKTQMD9'
response = requests.get(url)
data = response.json()
```

#### 3. Commodities
- **WTI** - Crude Oil Prices (West Texas Intermediate)
- **BRENT** - Crude Oil Prices (Brent)
- **NATURAL_GAS** - Natural Gas Prices
- **COPPER** - Global Copper Prices
- **ALUMINUM** - Global Aluminum Prices
- **WHEAT** - Global Wheat Prices
- **CORN** - Global Corn Prices
- **COTTON** - Global Cotton Prices
- **SUGAR** - Global Sugar Prices
- **COFFEE** - Global Coffee Prices

#### 4. Market Indices & Sentiment
- Real-time and historical stock market data
- Over 50 technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Market news & sentiment data
- Global market status (open/closed)

#### 5. Cryptocurrencies
- Bitcoin, Ethereum, and other major cryptocurrencies
- Exchange rates vs major fiat currencies
- Daily, weekly, monthly data

### API Limits
- Free tier: 25 requests per day
- Rate limit: 5 requests per minute

## FRED API (API Key: 5dfb1a7abe234caa5831f1a180a1bf1d)

### Installation
```bash
pip install fredapi pandas
```

### Key Economic Indicators for Forex Analysis

#### 1. Interest Rates
- **DFF** - Federal Funds Rate
- **DTB3** - 3-Month Treasury Bill
- **DGS2** - 2-Year Treasury Rate
- **DGS5** - 5-Year Treasury Rate
- **DGS10** - 10-Year Treasury Rate
- **DGS30** - 30-Year Treasury Rate
- **SOFR** - Secured Overnight Financing Rate

#### 2. Inflation Indicators
- **CPIAUCSL** - Consumer Price Index (All Urban Consumers)
- **CPILFESL** - Core CPI (Less Food and Energy)
- **PCEPI** - Personal Consumption Expenditures Price Index
- **GDPDEF** - GDP Deflator
- **T5YIE** - 5-Year Breakeven Inflation Rate
- **T10YIE** - 10-Year Breakeven Inflation Rate
- **MICH** - University of Michigan Inflation Expectation

#### 3. Economic Growth
- **GDP** - Gross Domestic Product
- **GDPC1** - Real GDP
- **GDPPOT** - Real Potential GDP
- **NYGDPMKTPCDWLD** - World GDP Per Capita
- **INDPRO** - Industrial Production Index
- **HOUST** - Housing Starts
- **PAYEMS** - All Employees: Total Nonfarm Payrolls

#### 4. Currency & Dollar Strength
- **DTWEXAFEGS** - Trade Weighted U.S. Dollar Index (Advanced Foreign Economies)
- **DTWEXBGS** - Trade Weighted U.S. Dollar Index (Broad)
- **DTWEXEMEGS** - Trade Weighted U.S. Dollar Index (Emerging Markets)
- **DEXJPUS** - Japan/U.S. Exchange Rate
- **DEXUSEU** - U.S./Euro Exchange Rate
- **DEXUSUK** - U.S./UK Exchange Rate
- **DEXCAUS** - Canada/U.S. Exchange Rate
- **DEXCHUS** - China/U.S. Exchange Rate
- **DEXSZUS** - Switzerland/U.S. Exchange Rate
- **DEXAUUS** - Australia/U.S. Exchange Rate

#### 5. Market Volatility & Risk
- **VIXCLS** - CBOE Volatility Index (VIX)
- **GVZCLS** - CBOE Gold ETF Volatility Index
- **STLFSI2** - St. Louis Fed Financial Stress Index
- **TEDRATE** - TED Spread
- **BAMLH0A0HYM2** - High Yield Option-Adjusted Spread

#### 6. Monetary Policy
- **M1SL** - M1 Money Supply
- **M2SL** - M2 Money Supply
- **M1V** - Velocity of M1 Money Stock
- **M2V** - Velocity of M2 Money Stock
- **BASE** - Monetary Base
- **BOGMBASE** - Board of Governors Monetary Base

#### 7. Employment
- **UNRATE** - Unemployment Rate
- **CIVPART** - Labor Force Participation Rate
- **EMRATIO** - Employment-Population Ratio
- **ICSA** - Initial Claims
- **UMCSENT** - University of Michigan Consumer Sentiment

#### 8. Trade & Current Account
- **BOPGSTB** - Trade Balance
- **NETEXP** - Net Exports
- **IMPGS** - Imports of Goods and Services
- **EXPGS** - Exports of Goods and Services

### Python Example
```python
from fredapi import Fred
import pandas as pd

fred = Fred(api_key='5dfb1a7abe234caa5831f1a180a1bf1d')

# Get multiple series for correlation analysis
indicators = {
    'DXY': 'DTWEXAFEGS',
    'VIX': 'VIXCLS',
    'Fed_Rate': 'DFF',
    'US_10Y': 'DGS10',
    'CPI': 'CPIAUCSL',
    'GDP': 'GDPC1',
    'EUR_USD': 'DEXUSEU',
    'GBP_USD': 'DEXUSUK'
}

data = {}
for name, series_id in indicators.items():
    data[name] = fred.get_series(series_id, observation_start='2020-01-01')

# Create DataFrame for correlation analysis
df = pd.DataFrame(data)
correlation_matrix = df.corr()
```

## Forex Correlation Analysis Recommendations

### Most Relevant Data for Forex Trading:

1. **Interest Rate Differentials**
   - Compare central bank rates between currency pairs
   - Monitor yield curves (2Y, 10Y spreads)
   - Track real interest rates (nominal - inflation)

2. **Dollar Strength Indices**
   - DXY (Dollar Index) - DTWEXAFEGS from FRED
   - Trade-weighted indices for specific regions

3. **Risk Sentiment Indicators**
   - VIX (Market volatility)
   - Gold/USD correlation
   - High-yield credit spreads
   - Financial stress indices

4. **Economic Growth Differentials**
   - GDP growth rates between countries
   - Industrial production
   - PMI data (not available in these APIs)

5. **Inflation Differentials**
   - CPI comparisons
   - Inflation expectations
   - Central bank inflation targets

6. **Commodity Correlations**
   - Oil prices (for commodity currencies: CAD, AUD, NZD)
   - Gold prices (safe haven flows)
   - Agricultural commodities (for EM currencies)

7. **Market Structure**
   - COT data (not available in these APIs)
   - Options positioning (limited availability)

### Implementation Strategy:

1. **Data Collection**: Use both APIs to gather comprehensive data
2. **Synchronization**: Align data by dates, handle missing values
3. **Normalization**: Standardize data for correlation analysis
4. **Time Periods**: Test correlations across different time windows
5. **Leading Indicators**: Identify which indicators lead forex moves
6. **Regime Detection**: Correlations change in different market regimes

### Additional Data Sources to Consider:
- Central bank communications (not in APIs)
- Political events and elections
- Trade balance data
- Capital flow data
- Positioning data (COT reports)