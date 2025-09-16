"""Tests for types module."""

import os
from decimal import Decimal
from datetime import datetime
import pytest
from fxml4_core.types import (
    TimeFrame,
    OrderSide,
    OrderType,
    OrderStatus,
    JSONType,
    PathLike,
)


def test_timeframe_enum():
    """Test TimeFrame enum."""
    assert TimeFrame.M1.value == "1m"
    assert TimeFrame.H4.value == "4h"
    assert TimeFrame.D1.value == "1d"
    
    # Test string comparison
    assert TimeFrame.H4 == "4h"


def test_order_side_enum():
    """Test OrderSide enum."""
    assert OrderSide.BUY.value == "BUY"
    assert OrderSide.SELL.value == "SELL"
    
    # Test all values are present
    assert len(OrderSide) == 2


def test_order_type_enum():
    """Test OrderType enum."""
    assert OrderType.MARKET.value == "MARKET"
    assert OrderType.LIMIT.value == "LIMIT"
    assert OrderType.STOP.value == "STOP"
    assert OrderType.STOP_LIMIT.value == "STOP_LIMIT"


def test_order_status_enum():
    """Test OrderStatus enum."""
    expected_statuses = [
        "PENDING", "SUBMITTED", "FILLED", "PARTIALLY_FILLED",
        "CANCELLED", "REJECTED", "EXPIRED"
    ]
    
    for status in expected_statuses:
        assert hasattr(OrderStatus, status)
        assert getattr(OrderStatus, status).value == status


def test_type_aliases():
    """Test that type aliases work correctly."""
    # JSONType
    json_data: JSONType = {"key": "value", "number": 42, "list": [1, 2, 3]}
    assert isinstance(json_data, dict)
    
    # PathLike
    path1: PathLike = "/path/to/file"
    path2: PathLike = os.path.expanduser("~")
    assert isinstance(path1, str)
    assert isinstance(path2, str)