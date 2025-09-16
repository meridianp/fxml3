
| Endpoint                               | Description                                                                                                                                                                                                                                                         | Tags                                      |
| :------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------- |
| `/TIME_SERIES_INTRADAY`                 | Returns intraday time series data for a given equity.                                                                                                                                                                                                                   | Core Time Series Stock Data APIs          |
| `/TIME_SERIES_DAILY`                    | Returns raw (as-traded) daily time series.                                                                                                                                                                                                                      | Core Time Series Stock Data APIs          |
| `/TIME_SERIES_DAILY_ADJUSTED`           | Returns daily open/high/low/close/volume values, adjusted close values, and historical split/dividend events.                                                                                                                                                | Core Time Series Stock Data APIs          |
| `/TIME_SERIES_WEEKLY`                   | Returns weekly time series (last trading day of each week, weekly open, weekly high, weekly low, weekly close, weekly volume) of the global equity specified.                       | Core Time Series Stock Data APIs      |
| `/TIME_SERIES_WEEKLY_ADJUSTED`          | Returns weekly adjusted time series (last trading day of each week, weekly open, weekly high, weekly low, weekly close, weekly adjusted close, weekly volume, weekly dividend) of the global equity specified.| Core Time Series Stock Data APIs      |
|`/TIME_SERIES_MONTHLY`                  | Returns monthly time series (last trading day of each month, monthly open, monthly high, monthly low, monthly close, monthly volume) of the global equity specified.    | Core Time Series Stock Data APIs          |
|`/TIME_SERIES_MONTHLY_ADJUSTED`         | Returns monthly adjusted time series (last trading day of each month, monthly open, monthly high, monthly low, monthly close, monthly adjusted close, monthly volume, monthly dividend) of the equity specified.| Core Time Series Stock Data APIs          |
| `/GLOBAL_QUOTE`                         | Returns the latest price and volume information for a ticker of your choice.                                                                                                                                                                                 | Core Time Series Stock Data APIs          |
| `/REALTIME_BULK_QUOTES`                 | Returns realtime quotes for US-traded symbols in bulk, accepting up to 100 symbols per API request.                                                                                                                                                      | Core Time Series Stock Data APIs          |
| `/SYMBOL_SEARCH`                        | Returns the best-matching symbols and market information based on keywords.                                                                                                                                                                                  | Core Time Series Stock Data APIs          |
| `/MARKET_STATUS`                        | Returns the current market status (open vs. closed) of major trading venues for equities, forex, and cryptocurrencies around the world.                                                                                                                | Core Time Series Stock Data APIs          |
| `/REALTIME_OPTIONS`                   | Returns realtime US options data with full market coverage.                                                                                                      | US Options Data APIs               |
| `/HISTORICAL_OPTIONS`                 | Returns the full historical options chain for a specific symbol on a specific date.                                                                                                                                                                        | US Options Data APIs               |
| `/NEWS_SENTIMENT`                       | Returns live and historical market news & sentiment data.                                                                                                                                                                                                       | Alpha Intelligence™                    |
| `/TOP_GAINERS_LOSERS`                   | Returns the top 20 gainers, losers, and the most active traded tickers in the US market.                                                                                                                                                              | Alpha Intelligence™                    |
| `/INSIDER_TRANSACTIONS`                 | Returns the latest and historical insider transactions made be key stakeholders of a specific company.                                                                                                                                                   | Alpha Intelligence™                    |
| `/ANALYTICS_FIXED_WINDOW`              | Returns a rich set of advanced analytics metrics for a given time series over a fixed temporal window.                                                                                                                                                 | Alpha Intelligence™                    |
| `/ANALYTICS_SLIDING_WINDOW`            | Returns a rich set of advanced analytics metrics for a given time series over sliding time windows.                                                                                                                                                 | Alpha Intelligence™                    |
| `/OVERVIEW`                             | Returns the company information, financial ratios, and other key metrics for the equity specified.                                                                                                                                                     | Fundamental Data                      |
| `/ETF_PROFILE`                           | Returns key ETF metrics, along with the corresponding ETF holdings / constituents with allocation by asset types and sectors.              | Fundamental Data                      |
| `/DIVIDENDS`                         | Returns historical and future (declared) dividend distributions.      | Fundamental Data                      |
| `/SPLITS`                              | Returns historical split events.                               | Fundamental Data             |
| `/INCOME_STATEMENT`                     | Returns the annual and quarterly income statements for the company of interest.                                                                                                                                                                  | Fundamental Data                      |
| `/BALANCE_SHEET`                        | Returns the annual and quarterly balance sheets for the company of interest.                                                                                                                                                                             | Fundamental Data                      |
| `/CASH_FLOW`                            | Returns the annual and quarterly cash flow for the company of interest.                                                                                                                                                                             | Fundamental Data                      |
| `/EARNINGS`                             | Returns the annual and quarterly earnings (EPS) for the company of interest.                                                                                                                                                                    | Fundamental Data                      |
| `/LISTING_STATUS`                       | Returns a list of active or delisted US stocks and ETFs.                                                                                                        | Fundamental Data                      |
| `/EARNINGS_CALENDAR`                    | Returns a list of company earnings expected in the next 3, 6, or 12 months.                                                                                                                                                                           | Fundamental Data                      |
| `/IPO_CALENDAR`                         | Returns a list of IPOs expected in the next 3 months.       | Fundamental Data                      |
| `/CURRENCY_EXCHANGE_RATE`              | Returns the realtime exchange rate for a pair of digital currency (e.g., Bitcoin) and physical currency (e.g., USD).                                           | Forex (FX), Digital/Crypto Currencies |
| `/FX_INTRADAY`                          | Returns intraday time series of the FX currency pair specified, updated realtime.                                                                                 | Forex (FX)                            |
| `/FX_DAILY`                             | Returns the daily time series of the FX currency pair specified, updated realtime.                                                                                        | Forex (FX)                            |
| `/FX_WEEKLY`                            | Returns the weekly time series of the FX currency pair specified, updated realtime.                                                                                       | Forex (FX)                            |
| `/FX_MONTHLY`                           | Returns the monthly time series of the FX currency pair specified, updated realtime.                                                                                      | Forex (FX)                            |
| `/CRYPTO_INTRADAY`                     | Returns intraday time series of the cryptocurrency specified, updated realtime.                                                                                      | Digital/Crypto Currencies              |
| `/DIGITAL_CURRENCY_DAILY`              | Returns the daily historical time series for a digital currency traded on a specific market, refreshed daily at midnight (UTC).                               | Digital/Crypto Currencies              |
| `/DIGITAL_CURRENCY_WEEKLY`             | Returns the weekly historical time series for a digital currency traded on a specific market, refreshed daily at midnight (UTC).                              | Digital/Crypto Currencies              |
| `/DIGITAL_CURRENCY_MONTHLY`            | Returns the monthly historical time series for a digital currency traded on a specific market, refreshed daily at midnight (UTC).                             | Digital/Crypto Currencies              |
| `/WTI`                                 | Returns the West Texas Intermediate (WTI) crude oil prices in daily, weekly, and monthly horizons.                                                                   | Commodities                           |
| `/BRENT`                               | Returns the Brent (Europe) crude oil prices in daily, weekly, and monthly horizons.                                                                                    | Commodities                           |
| `/NATURAL_GAS`                          | Returns the Henry Hub natural gas spot prices in daily, weekly, and monthly horizons.                                                                                  | Commodities                           |
| `/COPPER`                               | Returns the global price of copper in monthly, quarterly, and annual horizons.                                                                                         | Commodities                           |
| `/ALUMINUM`                            | Returns the global price of aluminum in monthly, quarterly, and annual horizons.                                                                       | Commodities                           |
|`/WHEAT`                                | Returns the global price of wheat in monthly, quarterly, and annual horizons.                                             | Commodities                           |
|`/CORN`                                 | Returns the global price of corn in monthly, quarterly, and annual horizons.                                             | Commodities                           |
|`/COTTON`                               | Returns the global price of cotton in monthly, quarterly, and annual horizons.                                             | Commodities                           |
|`/SUGAR`                                | Returns the global price of sugar in monthly, quarterly, and annual horizons.                                             | Commodities                           |
|`/COFFEE`                               | Returns the global price of coffee in monthly, quarterly, and annual horizons.                                             | Commodities                           |
|`/ALL_COMMODITIES`                      | Returns the global price index of all commodities in monthly, quarterly, and annual temporal dimensions.                                            | Commodities                           |
|`/REAL_GDP`                            | Returns the annual and quarterly Real GDP of the United States.                                        | Economic Indicators                    |
|`/REAL_GDP_PER_CAPITA`                 | Returns the quarterly Real GDP per Capita data of the United States.                                   | Economic Indicators                    |
|`/TREASURY_YIELD`                      | Returns the daily, weekly, and monthly US treasury yield of a given maturity timeline.                | Economic Indicators                    |
|`/FEDERAL_FUNDS_RATE`                 | Returns the daily, weekly, and monthly federal funds rate (interest rate) of the United States.       | Economic Indicators                    |
|`/CPI`                                  | Returns the monthly and semiannual consumer price index (CPI) of the United States.                  | Economic Indicators                    |
|`/INFLATION`                            | Returns the annual inflation rates (consumer prices) of the United States.                           | Economic Indicators                    |
|`/RETAIL_SALES`                        | Returns the monthly Advance Retail Sales: Retail Trade data of the United States.                   | Economic Indicators                    |
|`/DURABLES`                             | Returns the monthly manufacturers' new orders of durable goods in the United States.               | Economic Indicators                    |
|`/UNEMPLOYMENT`                          | Returns the monthly unemployment data of the United States.                                        | Economic Indicators                    |
|`/NONFARM_PAYROLL`                      | Returns the monthly US All Employees: Total Nonfarm (commonly known as Total Nonfarm Payroll).       | Economic Indicators                    |
|`/SMA`                |  Returns the simple moving average (SMA) values.        | Technical Indicators |
|`/EMA`                | Returns the exponential moving average (EMA) values.        | Technical Indicators |
|`/WMA`                | Returns the weighted moving average (WMA) values.       | Technical Indicators |
|`/DEMA`                | Returns the double exponential moving average (DEMA) values.          | Technical Indicators |
|`/TEMA`                | Returns the triple exponential moving average (TEMA) values.            | Technical Indicators |
|`/TRIMA`                | Returns the triangular moving average (TRIMA) values.    | Technical Indicators |
|`/KAMA`                | Returns the Kaufman adaptive moving average (KAMA) values.           | Technical Indicators |
|`/MAMA`               | Returns the MESA adaptive moving average (MAMA) values.                 | Technical Indicators |
|`/VWAP`               | Returns the volume weighted average price (VWAP) for intraday time series.        | Technical Indicators |
|`/T3`                | Returns the triple exponential moving average (T3) values.        | Technical Indicators |
|`/MACD`               | Returns the moving average convergence / divergence (MACD) values.           | Technical Indicators |
|`/MACDEXT`               | Returns the moving average convergence / divergence values with controllable moving average type. | Technical Indicators |
|`/STOCH`               | Returns the stochastic oscillator (STOCH) values.         | Technical Indicators |
|`/STOCHF`              | Returns the stochastic fast (STOCHF) values.   | Technical Indicators |
|`/RSI`                 | Returns the relative strength index (RSI) values.       | Technical Indicators |
|`/STOCHRSI`             | Returns the stochastic relative strength index (STOCHRSI) values.      | Technical Indicators |
|`/WILLR`             | Returns the Williams' %R (WILLR) values.        | Technical Indicators |
|`/ADX`                 | Returns the average directional movement index (ADX) values.          | Technical Indicators |
|`/ADXR`                | Returns the average directional movement index rating (ADXR) values.           | Technical Indicators |
|`/APO`                 | Returns the absolute price oscillator (APO) values.    | Technical Indicators |
|`/PPO`                 | Returns the percentage price oscillator (PPO) values. | Technical Indicators |
|`/MOM`                 | Returns the momentum (MOM) values.   | Technical Indicators |
|`/BOP`                 | Returns the balance of power (BOP) values.               | Technical Indicators |
|`/CCI`                 | Returns the commodity channel index (CCI) values.       | Technical Indicators |
|`/CMO`                | Returns the Chande momentum oscillator (CMO) values.       | Technical Indicators |
|`/ROC`                | Returns the rate of change (ROC) values.         | Technical Indicators |
|`/ROCR`               | Returns the rate of change ratio (ROCR) values.           | Technical Indicators |
|`/AROON`              | Returns the Aroon (AROON) values.   | Technical Indicators |
|`/AROONOSC`           | Returns the Aroon oscillator (AROONOSC) values.          | Technical Indicators |
|`/MFI`                | Returns the money flow index (MFI) values.    | Technical Indicators |
|`/TRIX`               | Returns the 1-day rate of change of a triple smooth exponential moving average (TRIX) values.        | Technical Indicators |
|`/ULTOSC`            | Returns the ultimate oscillator (ULTOSC) values.            | Technical Indicators |
|`/DX`                 | Returns the directional movement index (DX) values.     | Technical Indicators |
|`/MINUS_DI`         | Returns the minus directional indicator (MINUS_DI) values.      | Technical Indicators |
|`/PLUS_DI`          | Returns the plus directional indicator (PLUS_DI) values.       | Technical Indicators |
|`/MINUS_DM`          | Returns the minus directional movement (MINUS_DM) values.   | Technical Indicators |
|`/PLUS_DM`          | Returns the plus directional movement (PLUS_DM) values.       | Technical Indicators |
|`/BBANDS`             | Returns the Bollinger bands (BBANDS) values.              | Technical Indicators |
|`/MIDPOINT`         | Returns the midpoint (MIDPOINT) values. MIDPOINT = (highest value + lowest value)/2.     | Technical Indicators |
|`/MIDPRICE`          | Returns the midpoint price (MIDPRICE) values. MIDPRICE = (highest high + lowest low)/2.    | Technical Indicators |
|`/SAR`               | Returns the parabolic SAR (SAR) values.      | Technical Indicators |
|`/TRANGE`            | Returns the true range (TRANGE) values.                     | Technical Indicators |
|`/ATR`                | Returns the average true range (ATR) values.               | Technical Indicators |
|`/NATR`               | Returns the normalized average true range (NATR) values.  | Technical Indicators |
|`/AD`                 | Returns the Chaikin A/D line (AD) values.                 | Technical Indicators |
|`/ADOSC`              | Returns the Chaikin A/D oscillator (ADOSC) values.       | Technical Indicators |
|`/OBV`                | Returns the on balance volume (OBV) values.              | Technical Indicators |
|`/HT_TRENDLINE`       | Returns the Hilbert transform, instantaneous trendline (HT_TRENDLINE) values.   | Technical Indicators |
|`/HT_SINE`            | Returns the Hilbert transform, sine wave (HT_SINE) values. | Technical Indicators |
|`/HT_TRENDMODE`       | Returns the Hilbert transform, trend vs cycle mode (HT_TRENDMODE) values.    | Technical Indicators |
|`/HT_DCPERIOD`       | Returns the Hilbert transform, dominant cycle period (HT_DCPERIOD) values.  | Technical Indicators |
|`/HT_DCPHASE`        | Returns the Hilbert transform, dominant cycle phase (HT_DCPHASE) values.   | Technical Indicators |
|`/HT_PHASOR`         |  Returns the Hilbert transform, phasor components (HT_PHASOR) values.| Technical Indicators |
