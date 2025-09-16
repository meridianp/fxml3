"""Broker adapters for FXML4.

This module provides unified interfaces to various broker APIs including:
- Interactive Brokers (IB)
- FXCM
- Oanda
- Manual Trading

All adapters inherit from BaseBrokerAdapter and implement the same interface
for order management, position tracking, and market data.
"""

from .base_broker_adapter import (
    BaseBrokerAdapter,
    BrokerAdapterFactory,
    BrokerAuthenticationError,
    BrokerConnectionError,
    BrokerOrderError,
)
from .fxcm_adapter import FXCMAdapter

# Import all adapters to ensure they register themselves
from .interactive_brokers_adapter import InteractiveBrokersAdapter
from .manual_trading_adapter import ManualTradingAdapter
from .oanda_adapter import OandaAdapter

__all__ = [
    # Base classes and factory
    "BaseBrokerAdapter",
    "BrokerAdapterFactory",
    # Exceptions
    "BrokerConnectionError",
    "BrokerOrderError",
    "BrokerAuthenticationError",
    # Adapters
    "InteractiveBrokersAdapter",
    "FXCMAdapter",
    "OandaAdapter",
    "ManualTradingAdapter",
]
