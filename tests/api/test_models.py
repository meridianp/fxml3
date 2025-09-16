"""Test Pydantic models for FXML4 API.

This module tests the Pydantic models used for request and response validation
in the FXML4 API.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from fxml4.api.schemas.api_models import (
    BacktestRequest,
    BacktestResponse,
    DataRequest,
    OrderSideEnum,
    Signal,
    SignalRequest,
    SignalResponse,
    SignalTypeEnum,
    StrategyEnum,
    TimeframeEnum,
    TradeInfo,
)


def test_timeframe_enum():
    """Test TimeframeEnum values."""
    assert TimeframeEnum.ONE_MINUTE == "1m"
    assert TimeframeEnum.FIVE_MINUTES == "5m"
    assert TimeframeEnum.FIFTEEN_MINUTES == "15m"
    assert TimeframeEnum.THIRTY_MINUTES == "30m"
    assert TimeframeEnum.ONE_HOUR == "1h"
    assert TimeframeEnum.FOUR_HOURS == "4h"
    assert TimeframeEnum.ONE_DAY == "1d"
    assert TimeframeEnum.ONE_WEEK == "1w"
    assert TimeframeEnum.ONE_MONTH == "1M"


def test_strategy_enum():
    """Test StrategyEnum values."""
    assert StrategyEnum.INTEGRATED == "integrated_strategy"
    assert StrategyEnum.ML == "ml_strategy"
    assert StrategyEnum.WAVE == "wave_strategy"
    assert StrategyEnum.SENTIMENT == "sentiment_strategy"


def test_signal_type_enum():
    """Test SignalTypeEnum values."""
    assert SignalTypeEnum.ENTRY_LONG == "entry_long"
    assert SignalTypeEnum.ENTRY_SHORT == "entry_short"
    assert SignalTypeEnum.EXIT_LONG == "exit_long"
    assert SignalTypeEnum.EXIT_SHORT == "exit_short"


def test_order_side_enum():
    """Test OrderSideEnum values."""
    assert OrderSideEnum.BUY == "buy"
    assert OrderSideEnum.SELL == "sell"


def test_data_request_valid():
    """Test valid DataRequest model."""
    # Test with minimal required fields
    request = DataRequest(symbol="GBPUSD", timeframe="1h")
    assert request.symbol == "GBPUSD"
    assert request.timeframe == "1h"
    assert request.start_date is None
    assert request.end_date is None
    assert request.limit is None

    # Test with all fields
    request = DataRequest(
        symbol="EURUSD",
        timeframe="4h",
        start_date="2023-01-01",
        end_date="2023-12-31",
        limit=100,
    )
    assert request.symbol == "EURUSD"
    assert request.timeframe == "4h"
    assert request.start_date == "2023-01-01"
    assert request.end_date == "2023-12-31"
    assert request.limit == 100

    # Test with datetime objects
    now = datetime.now()
    request = DataRequest(symbol="GBPUSD", timeframe="1h", start_date=now)
    assert isinstance(request.start_date, str)
    assert now.isoformat() in request.start_date


def test_data_request_invalid():
    """Test invalid DataRequest model."""
    # Test missing required fields
    with pytest.raises(ValidationError):
        DataRequest(timeframe="1h")  # Missing symbol

    with pytest.raises(ValidationError):
        DataRequest(symbol="GBPUSD")  # Missing timeframe

    # Test invalid timeframe
    with pytest.raises(ValidationError):
        DataRequest(symbol="GBPUSD", timeframe="invalid")


def test_signal_request_valid():
    """Test valid SignalRequest model."""
    # Test with minimal required fields
    request = SignalRequest(
        symbol="GBPUSD", timeframe="1h", strategy="integrated_strategy"
    )
    assert request.symbol == "GBPUSD"
    assert request.timeframe == "1h"
    assert request.strategy == "integrated_strategy"
    assert request.parameters is None

    # Test with parameters
    request = SignalRequest(
        symbol="EURUSD",
        timeframe="4h",
        strategy="ml_strategy",
        parameters={"threshold": 0.7},
    )
    assert request.symbol == "EURUSD"
    assert request.timeframe == "4h"
    assert request.strategy == "ml_strategy"
    assert request.parameters == {"threshold": 0.7}


def test_signal_request_invalid():
    """Test invalid SignalRequest model."""
    # Test missing required fields
    with pytest.raises(ValidationError):
        SignalRequest(timeframe="1h", strategy="integrated_strategy")  # Missing symbol

    with pytest.raises(ValidationError):
        SignalRequest(
            symbol="GBPUSD", strategy="integrated_strategy"
        )  # Missing timeframe

    with pytest.raises(ValidationError):
        SignalRequest(symbol="GBPUSD", timeframe="1h")  # Missing strategy

    # Test invalid strategy
    with pytest.raises(ValidationError):
        SignalRequest(symbol="GBPUSD", timeframe="1h", strategy="invalid")


def test_backtest_request_valid():
    """Test valid BacktestRequest model."""
    # Test with minimal required fields
    request = BacktestRequest(
        symbol="GBPUSD",
        timeframe="1h",
        strategy="integrated_strategy",
        start_date="2023-01-01",
        end_date="2023-12-31",
    )
    assert request.symbol == "GBPUSD"
    assert request.timeframe == "1h"
    assert request.strategy == "integrated_strategy"
    assert request.start_date == "2023-01-01"
    assert request.end_date == "2023-12-31"
    assert request.initial_capital == 10000.0  # Default value
    assert request.parameters is None
    assert request.auto_report is True  # Default value

    # Test with all fields
    request = BacktestRequest(
        symbol="EURUSD",
        timeframe="4h",
        strategy="ml_strategy",
        start_date="2023-01-01",
        end_date="2023-12-31",
        initial_capital=20000.0,
        parameters={"threshold": 0.7},
        auto_report=False,
    )
    assert request.symbol == "EURUSD"
    assert request.timeframe == "4h"
    assert request.strategy == "ml_strategy"
    assert request.start_date == "2023-01-01"
    assert request.end_date == "2023-12-31"
    assert request.initial_capital == 20000.0
    assert request.parameters == {"threshold": 0.7}
    assert request.auto_report is False


def test_backtest_request_invalid():
    """Test invalid BacktestRequest model."""
    # Test missing required fields
    with pytest.raises(ValidationError):
        BacktestRequest(
            timeframe="1h",  # Missing symbol
            strategy="integrated_strategy",
            start_date="2023-01-01",
            end_date="2023-12-31",
        )

    with pytest.raises(ValidationError):
        BacktestRequest(
            symbol="GBPUSD",
            # Missing timeframe
            strategy="integrated_strategy",
            start_date="2023-01-01",
            end_date="2023-12-31",
        )

    # Test invalid date format
    with pytest.raises(ValidationError):
        BacktestRequest(
            symbol="GBPUSD",
            timeframe="1h",
            strategy="integrated_strategy",
            start_date="invalid_date",  # Invalid format
            end_date="2023-12-31",
        )


def test_signal_model_valid():
    """Test valid Signal model."""
    signal = Signal(
        symbol="GBPUSD",
        timestamp=datetime.now(),
        signal_type=SignalTypeEnum.ENTRY_LONG,
        confidence=0.85,
        price=1.2345,
        description="Strong buying opportunity",
    )
    assert signal.symbol == "GBPUSD"
    assert isinstance(signal.timestamp, datetime)
    assert signal.signal_type == SignalTypeEnum.ENTRY_LONG
    assert signal.confidence == 0.85
    assert signal.price == 1.2345
    assert signal.description == "Strong buying opportunity"
    assert signal.metadata is None

    # Test with metadata
    signal = Signal(
        symbol="EURUSD",
        timestamp=datetime.now(),
        signal_type=SignalTypeEnum.ENTRY_SHORT,
        confidence=0.75,
        price=1.0987,
        description="Potential trend reversal",
        metadata={"indicators": {"rsi": 70}},
    )
    assert signal.symbol == "EURUSD"
    assert signal.signal_type == SignalTypeEnum.ENTRY_SHORT
    assert signal.metadata == {"indicators": {"rsi": 70}}


def test_signal_model_invalid():
    """Test invalid Signal model."""
    now = datetime.now()

    # Test missing required fields
    with pytest.raises(ValidationError):
        Signal(
            timestamp=now,  # Missing symbol
            signal_type=SignalTypeEnum.ENTRY_LONG,
            confidence=0.85,
            price=1.2345,
        )

    # Test invalid confidence value
    with pytest.raises(ValidationError):
        Signal(
            symbol="GBPUSD",
            timestamp=now,
            signal_type=SignalTypeEnum.ENTRY_LONG,
            confidence=1.5,  # Should be between 0.0 and 1.0
            price=1.2345,
        )


def test_signal_response_valid():
    """Test valid SignalResponse model."""
    now = datetime.now()

    signal1 = Signal(
        symbol="GBPUSD",
        timestamp=now,
        signal_type=SignalTypeEnum.ENTRY_LONG,
        confidence=0.85,
        price=1.2345,
    )

    signal2 = Signal(
        symbol="GBPUSD",
        timestamp=now,
        signal_type=SignalTypeEnum.EXIT_LONG,
        confidence=0.75,
        price=1.2465,
    )

    response = SignalResponse(
        symbol="GBPUSD",
        timeframe="1h",
        strategy="integrated_strategy",
        signals=[signal1, signal2],
    )

    assert response.symbol == "GBPUSD"
    assert response.timeframe == "1h"
    assert response.strategy == "integrated_strategy"
    assert len(response.signals) == 2
    assert response.signals[0].symbol == "GBPUSD"
    assert response.signals[1].signal_type == SignalTypeEnum.EXIT_LONG


def test_backtest_response_valid():
    """Test valid BacktestResponse model."""
    response = BacktestResponse(
        backtest_id="BT-20230101-123456",
        symbol="GBPUSD",
        timeframe="1h",
        strategy="integrated_strategy",
        start_date="2023-01-01",
        end_date="2023-12-31",
        initial_capital=10000.0,
        final_capital=12000.0,
        total_return=2000.0,
        total_return_pct=20.0,
        max_drawdown=500.0,
        max_drawdown_pct=5.0,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        win_rate=0.6,
        profit_factor=1.8,
        trade_count=50,
    )

    assert response.backtest_id == "BT-20230101-123456"
    assert response.symbol == "GBPUSD"
    assert response.timeframe == "1h"
    assert response.strategy == "integrated_strategy"
    assert response.initial_capital == 10000.0
    assert response.final_capital == 12000.0
    assert response.total_return == 2000.0
    assert response.total_return_pct == 20.0
    assert response.max_drawdown == 500.0
    assert response.max_drawdown_pct == 5.0
    assert response.sharpe_ratio == 1.5
    assert response.sortino_ratio == 2.0
    assert response.win_rate == 0.6
    assert response.profit_factor == 1.8
    assert response.trade_count == 50
    assert response.report_url is None

    # Test with report_url
    response = BacktestResponse(
        backtest_id="BT-20230101-123456",
        symbol="GBPUSD",
        timeframe="1h",
        strategy="integrated_strategy",
        start_date="2023-01-01",
        end_date="2023-12-31",
        initial_capital=10000.0,
        final_capital=12000.0,
        total_return=2000.0,
        total_return_pct=20.0,
        max_drawdown=500.0,
        max_drawdown_pct=5.0,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        win_rate=0.6,
        profit_factor=1.8,
        trade_count=50,
        report_url="/performance/report/BT-20230101-123456",
    )

    assert response.report_url == "/performance/report/BT-20230101-123456"
