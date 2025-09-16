#!/usr/bin/env python3
"""
Unit tests for the Alpha Vantage data feed.
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from fxml4.data_engineering.data_feeds.alpha_vantage_feed import AlphaVantageDataFeed


@pytest.fixture
def config():
    """Test configuration fixture."""
    return {"api_key": "demo", "cache_data": True, "api_calls_per_minute": 5}


@pytest.fixture
def alpha_vantage_feed(config):
    """AlphaVantageDataFeed instance fixture."""
    return AlphaVantageDataFeed(config)


@pytest.fixture
def sample_forex_response():
    """Sample forex data response fixture."""
    return {
        "Meta Data": {
            "1. Information": "Forex Daily Prices (open, high, low, close)",
            "2. From Symbol": "EUR",
            "3. To Symbol": "USD",
            "4. Output Size": "Compact",
            "5. Last Refreshed": "2024-03-12 16:00:00",
        },
        "Time Series FX (Daily)": {
            "2024-03-12": {
                "1. open": "1.0900",
                "2. high": "1.0950",
                "3. low": "1.0850",
                "4. close": "1.0925",
            },
            "2024-03-11": {
                "1. open": "1.0880",
                "2. high": "1.0930",
                "3. low": "1.0860",
                "4. close": "1.0900",
            },
        },
    }


@pytest.fixture
def sample_stock_response():
    """Sample stock data response fixture."""
    return {
        "Meta Data": {
            "1. Information": "Daily Prices (open, high, low, close) and Volumes",
            "2. Symbol": "MSFT",
            "3. Last Refreshed": "2024-03-12",
            "4. Output Size": "Compact",
            "5. Time Zone": "US/Eastern",
        },
        "Time Series (Daily)": {
            "2024-03-12": {
                "1. open": "400.0000",
                "2. high": "405.0000",
                "3. low": "398.0000",
                "4. close": "403.5000",
                "5. volume": "25000000",
            },
            "2024-03-11": {
                "1. open": "402.0000",
                "2. high": "407.0000",
                "3. low": "401.0000",
                "4. close": "404.0000",
                "5. volume": "22000000",
            },
        },
    }


@pytest.fixture
def sample_exchange_rate_response():
    """Sample exchange rate response fixture."""
    return {
        "Realtime Currency Exchange Rate": {
            "1. From_Currency Code": "EUR",
            "2. From_Currency Name": "Euro",
            "3. To_Currency Code": "USD",
            "4. To_Currency Name": "United States Dollar",
            "5. Exchange Rate": "1.09243",
            "6. Last Refreshed": "2024-03-12 17:00:00",
            "7. Time Zone": "UTC",
        }
    }


@pytest.fixture
def sample_symbol_search_response():
    """Sample symbol search response fixture."""
    return {
        "bestMatches": [
            {
                "1. symbol": "MSFT",
                "2. name": "Microsoft Corporation",
                "3. type": "Equity",
                "4. region": "United States",
                "5. marketOpen": "09:30",
                "6. marketClose": "16:00",
                "7. timezone": "UTC-04",
                "8. currency": "USD",
                "9. matchScore": "1.0000",
            },
            {
                "1. symbol": "MSFT.LON",
                "2. name": "Microsoft Corporation",
                "3. type": "Equity",
                "4. region": "United Kingdom",
                "5. marketOpen": "08:00",
                "6. marketClose": "16:30",
                "7. timezone": "UTC+00",
                "8. currency": "GBP",
                "9. matchScore": "0.8000",
            },
        ]
    }


def test_init(alpha_vantage_feed):
    """Test initialization of the data feed."""
    assert alpha_vantage_feed.api_key == "demo"
    assert alpha_vantage_feed.cache_data is True
    assert alpha_vantage_feed.api_calls_per_minute == 5
    assert alpha_vantage_feed.call_interval == 60.0 / 5


def test_init_without_api_key(config):
    """Test initialization without API key."""
    config_without_key = dict(config)
    config_without_key.pop("api_key")

    with pytest.raises(ValueError):
        AlphaVantageDataFeed(config_without_key)


def test_format_symbol(alpha_vantage_feed):
    """Test symbol formatting."""
    assert alpha_vantage_feed._format_symbol_for_av("EURUSD") == "EURUSD"
    assert alpha_vantage_feed._format_symbol_for_av("EUR.USD") == "EURUSD"
    assert alpha_vantage_feed._format_symbol_for_av("MSFT") == "MSFT"


def test_cache_key(alpha_vantage_feed):
    """Test cache key generation."""
    key = alpha_vantage_feed._get_cache_key("FX_DAILY", "EURUSD", "1d")
    assert key == "FX_DAILY_EURUSD_1d"


@pytest.mark.network
@patch("requests.get")
def test_request_data(mock_get, alpha_vantage_feed):
    """Test API request with mocked response."""
    # Mock response
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"data": "test_data"}
    mock_get.return_value = mock_response

    # Test request
    params = {"function": "FX_DAILY", "from_symbol": "EUR", "to_symbol": "USD"}
    result = alpha_vantage_feed._request_data(params)

    # Verify result
    assert result == {"data": "test_data"}

    # Verify API key was added to params
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["apikey"] == "demo"


@pytest.mark.network
@patch("requests.get")
def test_forex_data_fetch(mock_get, alpha_vantage_feed, sample_forex_response):
    """Test fetching forex data."""
    # Mock response
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = sample_forex_response
    mock_get.return_value = mock_response

    # Test fetch_data
    result = alpha_vantage_feed.fetch_data("EURUSD", "1d", data_type="forex")

    # Verify result format
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]


@pytest.mark.network
@patch("requests.get")
def test_stock_data_fetch(mock_get, alpha_vantage_feed, sample_stock_response):
    """Test fetching stock data."""
    # Mock response
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = sample_stock_response
    mock_get.return_value = mock_response

    # Test fetch_data
    result = alpha_vantage_feed.fetch_data("MSFT", "1d", data_type="stock")

    # Verify result format
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]


@pytest.mark.network
@patch("requests.get")
def test_exchange_rate(mock_get, alpha_vantage_feed, sample_exchange_rate_response):
    """Test getting exchange rate."""
    # Mock response
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = sample_exchange_rate_response
    mock_get.return_value = mock_response

    # Test get_exchange_rate
    result = alpha_vantage_feed.get_exchange_rate("EUR", "USD")

    # Verify result format
    assert isinstance(result, dict)
    assert result["from_currency"] == "EUR"
    assert result["to_currency"] == "USD"
    assert abs(result["exchange_rate"] - 1.09243) < 1e-5


@pytest.mark.network
@patch("requests.get")
def test_symbol_search(mock_get, alpha_vantage_feed, sample_symbol_search_response):
    """Test symbol search."""
    # Mock response
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = sample_symbol_search_response
    mock_get.return_value = mock_response

    # Test symbol_search
    result = alpha_vantage_feed.search_symbol("Microsoft")

    # Verify result format
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert result.iloc[0]["symbol"] == "MSFT"
    assert result.iloc[0]["name"] == "Microsoft Corporation"


def test_available_timeframes(alpha_vantage_feed):
    """Test getting available timeframes."""
    timeframes = alpha_vantage_feed.get_available_timeframes()

    expected = ["1m", "5m", "15m", "30m", "60m", "1h", "1d", "1w", "1M"]
    assert set(timeframes) == set(expected)


def test_available_symbols(alpha_vantage_feed):
    """Test getting available symbols."""
    symbols = alpha_vantage_feed.get_available_symbols()

    expected = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
    assert set(symbols) == set(expected)
