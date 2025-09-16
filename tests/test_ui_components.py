"""Tests for the FXML4 UI components."""

import json
from datetime import datetime
from unittest import mock

import pandas as pd
import pytest
import requests
import streamlit as st

from fxml4.ui.dashboard import ApiClient, Dashboard


@pytest.fixture
def mock_api_client():
    """Return a mocked API client."""
    with mock.patch("fxml4.ui.dashboard.ApiClient") as mock_client:
        client_instance = mock.MagicMock()
        mock_client.return_value = client_instance
        yield client_instance


@pytest.fixture
def mock_streamlit():
    """Mock streamlit components."""
    with mock.patch("fxml4.ui.dashboard.st") as mock_st:
        # Set up common streamlit mocks
        mock_st.session_state = {}
        mock_st.session_state.backtest_history = []
        mock_st.session_state.performance_metrics = {}
        mock_st.session_state.comparison_results = None

        # Mock form components
        mock_form = mock.MagicMock()
        mock_st.form.return_value.__enter__.return_value = mock_form

        # Mock columns
        mock_col = mock.MagicMock()
        mock_st.columns.return_value = [mock_col, mock_col, mock_col, mock_col]

        # Mock tabs
        mock_tab = mock.MagicMock()
        mock_st.tabs.return_value = [mock_tab, mock_tab, mock_tab, mock_tab, mock_tab]

        yield mock_st


def test_api_client_initialization():
    """Test ApiClient initialization."""
    # Test with default values
    client = ApiClient()
    assert client.base_url.startswith("http://")

    # Test with custom base URL
    custom_url = "http://custom-api:8000"
    client = ApiClient(custom_url)
    assert client.base_url == custom_url


@mock.patch("requests.get")
def test_api_client_get_request(mock_get):
    """Test API client GET request."""
    # Set up the mock response
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {"status": "ok"}
    mock_get.return_value = mock_response

    # Create client and make request
    client = ApiClient("http://test-api:8000")
    result = client._make_request("GET", "/api/health")

    # Verify the request was made correctly
    mock_get.assert_called_once_with("http://test-api:8000/api/health", params=None)
    assert result == {"status": "ok"}


@mock.patch("requests.post")
def test_api_client_post_request(mock_post):
    """Test API client POST request."""
    # Set up the mock response
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {"backtest_id": "BT-123"}
    mock_post.return_value = mock_response

    # Create client and make request
    client = ApiClient("http://test-api:8000")
    data = {"symbol": "EURUSD", "strategy": "test"}
    result = client._make_request("POST", "/api/backtest", data=data)

    # Verify the request was made correctly
    mock_post.assert_called_once_with(
        "http://test-api:8000/api/backtest", params=None, json=data
    )
    assert result == {"backtest_id": "BT-123"}


@mock.patch("requests.get")
def test_api_client_error_handling(mock_get):
    """Test API client error handling."""
    # Set up the mock to raise an exception
    mock_get.side_effect = requests.exceptions.RequestException("API error")

    # Create client and make request (should raise exception)
    client = ApiClient("http://test-api:8000")
    with pytest.raises(requests.exceptions.RequestException):
        client._make_request("GET", "/api/health")


def test_api_client_health_check(mock_api_client):
    """Test the health check method."""
    # Set up mock return value
    mock_api_client._make_request.return_value = {"status": "ok"}

    # Create real client with mocked internals
    client = ApiClient()
    client._make_request = mock_api_client._make_request

    # Call the method
    result = client.get_health()

    # Verify the request was made correctly
    mock_api_client._make_request.assert_called_once_with("GET", "/api/health")
    assert result == {"status": "ok"}


def test_api_client_run_backtest(mock_api_client):
    """Test the run_backtest method."""
    # Set up mock return value
    mock_api_client._make_request.return_value = {"backtest_id": "BT-123"}

    # Create real client with mocked internals
    client = ApiClient()
    client._make_request = mock_api_client._make_request

    # Prepare test data
    params = {
        "symbol": "EURUSD",
        "timeframe": "1h",
        "strategy": "test_strategy",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 10000.0,
        "parameters": {"param1": "value1"},
        "auto_report": True,
    }

    # Call the method
    result = client.run_backtest(**params)

    # Verify the request was made correctly
    mock_api_client._make_request.assert_called_once_with(
        "POST", "/api/backtest", data=params
    )
    assert result == {"backtest_id": "BT-123"}


def test_api_client_get_performance_metrics(mock_api_client):
    """Test the get_performance_metrics method."""
    # Set up mock return value
    mock_api_client._make_request.return_value = {"metrics": {"total_return": 25.0}}

    # Create real client with mocked internals
    client = ApiClient()
    client._make_request = mock_api_client._make_request

    # Call the method
    result = client.get_performance_metrics(
        backtest_id="BT-123",
        include_trades=True,
        include_equity_curve=False,
    )

    # Verify the request was made correctly
    mock_api_client._make_request.assert_called_once_with(
        "GET",
        "/api/performance/metrics/BT-123",
        params={"include_trades": True, "include_equity_curve": False},
    )
    assert result == {"metrics": {"total_return": 25.0}}


def test_api_client_get_performance_report_url():
    """Test the get_performance_report_url method."""
    client = ApiClient("http://test-api:8000")
    url = client.get_performance_report_url("BT-123", format="pdf")
    assert url == "http://test-api:8000/api/performance/report/BT-123?format=pdf"


def test_api_client_compare_backtests(mock_api_client):
    """Test the compare_backtests method."""
    # Set up mock return value
    mock_api_client._make_request.return_value = {
        "metrics": {"total_return": {"BT-1": 25.0, "BT-2": 18.0}}
    }

    # Create real client with mocked internals
    client = ApiClient()
    client._make_request = mock_api_client._make_request

    # Call the method
    result = client.compare_backtests(
        backtest_ids=["BT-1", "BT-2"],
        metrics=["total_return", "sharpe_ratio"],
    )

    # Verify the request was made correctly
    mock_api_client._make_request.assert_called_once_with(
        "POST",
        "/api/performance/compare",
        data={
            "backtest_ids": ["BT-1", "BT-2"],
            "metrics": ["total_return", "sharpe_ratio"],
        },
    )
    assert result == {"metrics": {"total_return": {"BT-1": 25.0, "BT-2": 18.0}}}


def test_dashboard_initialization(mock_api_client):
    """Test Dashboard initialization."""
    # Set up session state in a context that mimics streamlit
    with mock.patch("fxml4.ui.dashboard.st") as mock_st:
        mock_st.session_state = {}

        # Initialize dashboard
        dashboard = Dashboard()

        # Verify session state is initialized
        assert "backtest_history" in mock_st.session_state
        assert "performance_metrics" in mock_st.session_state
        assert "comparison_results" in mock_st.session_state


def test_dashboard_run(mock_streamlit, mock_api_client):
    """Test the dashboard run method."""
    # Set up the mock API client to return health status
    mock_api_client.get_health.return_value = {"status": "ok"}

    # Initialize dashboard with mocked components
    dashboard = Dashboard()
    dashboard.api_client = mock_api_client

    # Run the dashboard
    dashboard.run()

    # Verify API health was checked
    mock_api_client.get_health.assert_called_once()

    # Verify streamlit page configuration was set
    mock_streamlit.set_page_config.assert_called_once()

    # Verify navigation was set up
    mock_streamlit.sidebar.radio.assert_called_once()


def test_show_backtest_runner(mock_streamlit, mock_api_client):
    """Test the backtest runner page."""
    # Set up dashboard with mocked components
    dashboard = Dashboard()
    dashboard.api_client = mock_api_client

    # Show the backtest runner page
    dashboard.show_backtest_runner()

    # Verify the header was set
    mock_streamlit.header.assert_called_with("Backtest Runner")

    # Verify the form was created
    mock_streamlit.form.assert_called_with("backtest_form")


def test_backtest_submission(mock_streamlit, mock_api_client):
    """Test backtest form submission."""
    # Set up mock form values
    form = mock_streamlit.form.return_value.__enter__.return_value
    form.form_submit_button.return_value = True  # Form is submitted

    # Set up mock selectbox values
    form.selectbox.side_effect = ["EURUSD", "1h", "ml_strategy"]

    # Set up mock date inputs
    form.date_input.side_effect = [
        datetime(2023, 1, 1).date(),  # Start date
        datetime(2023, 12, 31).date(),  # End date
    ]

    # Set up mock number input
    form.number_input.return_value = 10000.0  # Initial capital

    # Set up mock checkbox
    form.checkbox.return_value = True  # Auto generate report

    # Set up mock expander
    mock_expander = mock.MagicMock()
    form.expander.return_value.__enter__.return_value = mock_expander
    mock_expander.selectbox.return_value = "random_forest"
    mock_expander.multiselect.return_value = ["technical", "volatility"]

    # Set up mock backtest result
    backtest_result = {
        "backtest_id": "BT-123",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "strategy": "ml_strategy",
        "total_return_pct": 25.0,
        "final_capital": 12500.0,
        "total_return": 2500.0,
        "max_drawdown_pct": 8.0,
        "trade_count": 42,
        "report_url": "/api/performance/report/BT-123",
    }
    mock_api_client.run_backtest.return_value = backtest_result

    # Set up mock performance metrics
    metrics = {
        "metrics": {"total_return_pct": 25.0},
        "equity_curve": [{"timestamp": "2023-01-01", "equity": 10000.0}],
        "monthly_returns": {"2023-01": 2.1},
    }
    mock_api_client.get_performance_metrics.return_value = metrics

    # Show the backtest runner page
    dashboard = Dashboard()
    dashboard.api_client = mock_api_client
    mock_streamlit.session_state.backtest_history = []
    mock_streamlit.session_state.performance_metrics = {}

    dashboard.show_backtest_runner()

    # Verify the API was called with the right parameters
    mock_api_client.run_backtest.assert_called_once()
    call_args = mock_api_client.run_backtest.call_args[1]
    assert call_args["symbol"] == "EURUSD"
    assert call_args["timeframe"] == "1h"
    assert call_args["strategy"] == "ml_strategy"
    assert call_args["start_date"] == "2023-01-01"
    assert call_args["end_date"] == "2023-12-31"
    assert call_args["initial_capital"] == 10000.0
    assert call_args["parameters"]["model"] == "random_forest"
    assert call_args["parameters"]["features"] == ["technical", "volatility"]
    assert call_args["auto_report"] is True

    # Verify the backtest result was added to the history
    assert len(mock_streamlit.session_state.backtest_history) == 1
    assert mock_streamlit.session_state.backtest_history[0]["backtest_id"] == "BT-123"

    # Verify performance metrics were fetched
    mock_api_client.get_performance_metrics.assert_called_once_with(
        backtest_id="BT-123",
        include_equity_curve=True,
    )

    # Verify the success message was shown
    mock_streamlit.success.assert_called_once()

    # Verify charts were created
    assert mock_streamlit.plotly_chart.called
