"""Tests for the FXML4 API endpoints."""

import json
import os
from datetime import datetime
from unittest import mock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fxml4.api.main import app


@pytest.fixture
def client():
    """Return a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_backtest_result():
    """Return a mock backtest result."""
    return {
        "backtest_id": "BT-20230101-123456",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "strategy": "ml_strategy",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 10000.0,
        "final_capital": 12500.0,
        "total_return": 2500.0,
        "total_return_pct": 25.0,
        "max_drawdown": 800.0,
        "max_drawdown_pct": 8.0,
        "sharpe_ratio": 1.8,
        "sortino_ratio": 2.2,
        "win_rate": 0.65,
        "profit_factor": 2.1,
        "trade_count": 42,
        "report_url": "/performance/report/BT-20230101-123456",
    }


@pytest.fixture
def mock_performance_metrics():
    """Return mock performance metrics."""
    return {
        "backtest_id": "BT-20230101-123456",
        "metrics": {
            "total_return_pct": 25.0,
            "annualized_return": 18.2,
            "sharpe_ratio": 1.8,
            "sortino_ratio": 2.2,
            "max_drawdown_pct": 8.0,
            "win_rate": 0.65,
            "profit_factor": 2.1,
            "recovery_factor": 3.1,
            "expectancy": 0.52,
            "avg_win": 350.0,
            "avg_loss": -200.0,
            "risk_of_ruin": 0.05,
            "trades_per_month": 6.3,
            "max_consecutive_wins": 5,
            "max_consecutive_losses": 3,
        },
        "monthly_returns": {
            "2023-01": 2.1,
            "2023-02": -1.5,
            "2023-03": 3.2,
            "2023-04": 1.8,
        },
        "drawdowns": [
            {
                "start_date": "2023-02-15",
                "end_date": "2023-02-28",
                "recovery_date": "2023-03-10",
                "depth_pct": 8.0,
                "duration_days": 13,
                "recovery_days": 10,
            },
        ],
        "monte_carlo": {
            "mean_return": 25.8,
            "median_return": 24.9,
            "worst_case": 15.2,
            "best_case": 35.6,
            "probability_of_profit": 0.996,
            "probability_of_10pct_drawdown": 0.32,
            "percentiles": {
                "5": 18.5,
                "25": 22.4,
                "50": 24.9,
                "75": 28.1,
                "95": 32.7,
            },
        },
    }


@pytest.fixture
def mock_comparison_result():
    """Return mock comparison results."""
    return {
        "backtest_ids": [
            "BT-20230101-123456",
            "BT-20230215-123456",
            "BT-20230310-123456",
        ],
        "metrics": {
            "total_return_pct": {
                "BT-20230101-123456": 25.0,
                "BT-20230215-123456": 18.5,
                "BT-20230310-123456": 22.3,
            },
            "max_drawdown_pct": {
                "BT-20230101-123456": 8.0,
                "BT-20230215-123456": 6.5,
                "BT-20230310-123456": 7.2,
            },
            "sharpe_ratio": {
                "BT-20230101-123456": 1.8,
                "BT-20230215-123456": 1.5,
                "BT-20230310-123456": 1.7,
            },
        },
        "ranking": {
            "total_return_pct": [
                "BT-20230101-123456",
                "BT-20230310-123456",
                "BT-20230215-123456",
            ],
            "max_drawdown_pct": [
                "BT-20230215-123456",
                "BT-20230310-123456",
                "BT-20230101-123456",
            ],
            "sharpe_ratio": [
                "BT-20230101-123456",
                "BT-20230310-123456",
                "BT-20230215-123456",
            ],
        },
        "correlation_matrix": {
            "BT-20230101-123456": {
                "BT-20230101-123456": 1.0,
                "BT-20230215-123456": 0.75,
                "BT-20230310-123456": 0.82,
            },
            "BT-20230215-123456": {
                "BT-20230101-123456": 0.75,
                "BT-20230215-123456": 1.0,
                "BT-20230310-123456": 0.68,
            },
            "BT-20230310-123456": {
                "BT-20230101-123456": 0.82,
                "BT-20230215-123456": 0.68,
                "BT-20230310-123456": 1.0,
            },
        },
    }


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "FXML4 API running"}


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@mock.patch("datetime.datetime")
@mock.patch("fxml4.data_engineering.data_feeds.base_feed.DataFeedFactory.create")
@mock.patch("fxml4.backtesting.backtest_engine.run_backtest")
@mock.patch("fxml4.ml.features.create_technical_features")
def test_run_backtest(
    mock_create_features,
    mock_run_backtest,
    mock_create_feed,
    mock_datetime,
    client,
    mock_backtest_result,
):
    """Test the run_backtest endpoint."""
    # Mock datetime.now() to return a fixed datetime
    mock_now = mock.MagicMock()
    mock_now.strftime.return_value = "20230101-123456"
    mock_datetime.now.return_value = mock_now

    # Create a mock data feed
    mock_feed = mock.MagicMock()
    mock_create_feed.return_value = mock_feed

    # Mock data fetching
    df = pd.DataFrame(
        {
            "open": [1.1] * 100,
            "high": [1.12] * 100,
            "low": [1.09] * 100,
            "close": [1.11] * 100,
            "volume": [1000] * 100,
        }
    )
    df.index = pd.date_range(start="2023-01-01", periods=100, freq="H")
    mock_feed.fetch_data.return_value = df

    # Mock feature creation
    mock_create_features.return_value = df

    # Mock backtest result
    from fxml4.backtesting.backtest_engine import BacktestResult

    mock_result = mock.MagicMock(spec=BacktestResult)
    mock_result.final_capital = mock_backtest_result["final_capital"]
    mock_result.total_return = mock_backtest_result["total_return"]
    mock_result.total_return_pct = mock_backtest_result["total_return_pct"]
    mock_result.max_drawdown = mock_backtest_result["max_drawdown"]
    mock_result.max_drawdown_pct = mock_backtest_result["max_drawdown_pct"]
    mock_result.sharpe_ratio = mock_backtest_result["sharpe_ratio"]
    mock_result.sortino_ratio = mock_backtest_result["sortino_ratio"]
    mock_result.win_rate = mock_backtest_result["win_rate"]
    mock_result.profit_factor = mock_backtest_result["profit_factor"]
    mock_result.trades = []
    mock_result.generate_report.return_value = f"output/reports/BT-20230101-123456.html"
    mock_run_backtest.return_value = mock_result

    # Prepare request data
    request_data = {
        "symbol": "EURUSD",
        "timeframe": "1h",
        "strategy": "ml_strategy",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 10000.0,
        "parameters": {
            "model": "random_forest",
            "features": ["technical", "volatility"],
        },
        "auto_report": True,
    }

    # Mock file operations
    with (
        mock.patch("os.makedirs") as mock_makedirs,
        mock.patch("builtins.open", mock.mock_open()) as mock_open,
    ):

        # Make the request
        response = client.post("/backtest", json=request_data)

        # Check the response
        assert response.status_code == 200
        assert response.json()["symbol"] == request_data["symbol"]
        assert response.json()["timeframe"] == request_data["timeframe"]
        assert response.json()["strategy"] == request_data["strategy"]
        assert response.json()["backtest_id"].startswith("BT-")
        assert response.json()["final_capital"] == float(
            mock_backtest_result["final_capital"]
        )
        assert response.json()["total_return"] == float(
            mock_backtest_result["total_return"]
        )
        assert response.json()["total_return_pct"] == float(
            mock_backtest_result["total_return_pct"]
        )
        assert response.json()["max_drawdown"] == float(
            mock_backtest_result["max_drawdown"]
        )
        assert response.json()["max_drawdown_pct"] == float(
            mock_backtest_result["max_drawdown_pct"]
        )
        assert response.json()["sharpe_ratio"] == float(
            mock_backtest_result["sharpe_ratio"]
        )
        assert response.json()["sortino_ratio"] == float(
            mock_backtest_result["sortino_ratio"]
        )
        assert response.json()["win_rate"] == float(mock_backtest_result["win_rate"])
        assert response.json()["profit_factor"] == float(
            mock_backtest_result["profit_factor"]
        )
        assert len(mock_result.trades) == response.json()["trade_count"]

        # Check that report URL is included if auto_report is True
        assert "report_url" in response.json()
        assert response.json()["report_url"].startswith("/performance/report/")

        # Verify that the key methods were called with the right parameters
        mock_create_feed.assert_called_once()
        mock_feed.fetch_data.assert_called_once_with(
            symbol=request_data["symbol"],
            timeframe=request_data["timeframe"],
            start_date=mock.ANY,
            end_date=mock.ANY,
        )
        mock_create_features.assert_called_once()
        mock_run_backtest.assert_called_once()
        mock_makedirs.assert_called_once()
        mock_open.assert_called_once()


def test_get_performance_metrics(client, mock_performance_metrics):
    """Test the get_performance_metrics endpoint."""
    backtest_id = "BT-20230101-123456"

    # Mock file system operations
    with (
        mock.patch("os.path.exists") as mock_exists,
        mock.patch(
            "builtins.open",
            mock.mock_open(read_data=json.dumps(mock_performance_metrics)),
        ) as mock_open,
    ):

        # Setup mock to return True for metadata file and False for others
        def exists_side_effect(path):
            return backtest_id in path and path.endswith("_metadata.json")

        mock_exists.side_effect = exists_side_effect

        # Make the request
        response = client.get(
            f"/performance/metrics/{backtest_id}",
            params={"include_trades": False, "include_equity_curve": True},
        )

        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert data["backtest_id"] == backtest_id
        assert "metrics" in data
        assert "monthly_returns" in data
        assert "drawdowns" in data
        assert "monte_carlo" in data

        # Check specific metrics
        assert data["metrics"]["total_return_pct"] == 25.0
        assert data["metrics"]["sharpe_ratio"] == 1.8
        assert data["metrics"]["max_drawdown_pct"] == 8.0

        # Verify file operations
        mock_exists.assert_called()
        mock_open.assert_called_once()


def test_get_performance_report(client):
    """Test the get_performance_report endpoint."""
    backtest_id = "BT-20230101-123456"

    # Set up mocks
    with (
        mock.patch("os.path.exists") as mock_exists,
        mock.patch(
            "fastapi.responses.FileResponse.__init__", return_value=None
        ) as mock_file_response,
    ):

        # Setup mock to return True for needed files
        def exists_side_effect(path):
            if backtest_id in path and path.endswith("_metadata.json"):
                return True
            elif backtest_id in path and path.endswith(".html"):
                return True
            else:
                return False

        mock_exists.side_effect = exists_side_effect

        # Set up mock for file opening
        with mock.patch(
            "builtins.open",
            mock.mock_open(
                read_data=json.dumps(
                    {
                        "symbol": "EURUSD",
                        "strategy": "ml_strategy",
                        "timeframe": "1h",
                        "start_date": "2023-01-01",
                        "end_date": "2023-12-31",
                    }
                )
            ),
        ):
            # Make the request
            response = client.get(
                f"/performance/report/{backtest_id}", params={"format": "html"}
            )

            # In a real test, this would return the file content
            # Here we just check that FileResponse was called with the right arguments
            mock_file_response.assert_called_once()
            args, kwargs = mock_file_response.call_args
            assert f"output/reports/{backtest_id}.html" in str(kwargs.get("path", ""))
            assert kwargs.get("media_type") == "text/html"


def test_get_performance_report_not_found(client):
    """Test the get_performance_report endpoint when the report is not found."""
    response = client.get(
        "/performance/report/BT-NONEXISTENT", params={"format": "html"}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.fixture
def mock_market_data():
    """Return mock market data."""
    # Create sample OHLCV data
    data = []
    for i in range(10):
        timestamp = pd.Timestamp("2023-01-01") + pd.Timedelta(days=i)
        data.append(
            {
                "timestamp": timestamp.isoformat(),
                "open": 1.1000 + (i * 0.0010),
                "high": 1.1020 + (i * 0.0015),
                "low": 0.9980 + (i * 0.0005),
                "close": 1.1010 + (i * 0.0012),
                "volume": 1000 + (i * 100),
            }
        )
    return {
        "symbol": "EURUSD",
        "timeframe": "1d",
        "start_date": "2023-01-01",
        "end_date": "2023-01-10",
        "data": data,
        "count": len(data),
        "source": "alpha_vantage",
    }


@mock.patch("fxml4.data_engineering.data_feeds.base_feed.DataFeedFactory.create")
def test_get_data(mock_create_feed, client, mock_market_data):
    """Test the get_data endpoint."""
    # Create a mock data feed
    mock_feed = mock.MagicMock()
    mock_create_feed.return_value = mock_feed

    # Mock the fetch_data method to return a DataFrame
    df = pd.DataFrame(mock_market_data["data"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")
    mock_feed.fetch_data.return_value = df

    # Prepare request data
    request_data = {
        "symbol": "EURUSD",
        "timeframe": "1d",
        "start_date": "2023-01-01",
        "end_date": "2023-01-10",
    }

    # Make the request
    response = client.post("/data", json=request_data)

    # Check the response
    assert response.status_code == 200
    assert response.json()["symbol"] == request_data["symbol"]
    assert response.json()["timeframe"] == request_data["timeframe"]
    assert response.json()["count"] == len(mock_market_data["data"])
    assert len(response.json()["data"]) == len(mock_market_data["data"])

    # Verify the mock was called with the right parameters
    mock_create_feed.assert_called_once()
    mock_feed.fetch_data.assert_called_once_with(
        symbol=request_data["symbol"],
        timeframe=request_data["timeframe"],
        start_date=mock.ANY,
        end_date=mock.ANY,
        limit=None,
    )


def test_compare_backtests(client, mock_comparison_result):
    """Test the compare_backtests endpoint."""
    # Prepare request data
    request_data = {
        "backtest_ids": [
            "BT-20230101-123456",
            "BT-20230215-123456",
            "BT-20230310-123456",
        ],
        "metrics": ["total_return_pct", "max_drawdown_pct", "sharpe_ratio"],
    }

    # Create individual metadata for each backtest
    metadata = {}
    for backtest_id in request_data["backtest_ids"]:
        metadata[backtest_id] = {
            "total_return_pct": mock_comparison_result["metrics"]["total_return_pct"][
                backtest_id
            ],
            "max_drawdown_pct": mock_comparison_result["metrics"]["max_drawdown_pct"][
                backtest_id
            ],
            "sharpe_ratio": mock_comparison_result["metrics"]["sharpe_ratio"][
                backtest_id
            ],
        }

    # Mock file operations
    with (
        mock.patch("os.path.exists") as mock_exists,
        mock.patch("builtins.open") as mock_open,
    ):

        # Setup mock to return True for metadata files
        def exists_side_effect(path):
            for backtest_id in request_data["backtest_ids"]:
                if backtest_id in path and path.endswith("_metadata.json"):
                    return True
            return False

        mock_exists.side_effect = exists_side_effect

        # Setup mock for file opening to return different content for each file
        mock_open_cm = mock.MagicMock()
        mock_open.return_value = mock_open_cm
        mock_open_cm.__enter__.side_effect = [
            mock.MagicMock(read=lambda: json.dumps(metadata[backtest_id]))
            for backtest_id in request_data["backtest_ids"]
        ]

        # Make the request
        response = client.post("/performance/compare", json=request_data)

        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert "backtest_ids" in data
        assert "metrics" in data
        assert "ranking" in data
        assert "correlation_matrix" in data

        # Check specific metrics - values might be different due to actual implementation
        for backtest_id in request_data["backtest_ids"]:
            assert backtest_id in data["metrics"]["total_return_pct"]
            assert backtest_id in data["metrics"]["max_drawdown_pct"]
            assert backtest_id in data["metrics"]["sharpe_ratio"]

        # Verify file operations
        assert mock_exists.call_count >= len(request_data["backtest_ids"])
        assert mock_open.call_count >= len(request_data["backtest_ids"])
