"""
Shared interfaces and protocols for FXML4 packages.

This module defines the contracts between different packages to avoid circular dependencies.
All packages should depend on these interfaces rather than concrete implementations.
"""

from abc import ABC, abstractmethod
from typing import Protocol, Dict, List, Optional, Any, Union
from datetime import datetime
import pandas as pd
from enum import Enum


# Enums for standardization
class OrderType(Enum):
    """Standard order types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(Enum):
    """Order side."""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Order execution status."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class SignalType(Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    EXIT = "EXIT"


# Data Types
class MarketData(Protocol):
    """Protocol for market data."""
    
    @property
    def symbol(self) -> str:
        """Trading symbol."""
        ...
    
    @property
    def timestamp(self) -> datetime:
        """Data timestamp."""
        ...
    
    @property
    def open(self) -> float:
        """Open price."""
        ...
    
    @property
    def high(self) -> float:
        """High price."""
        ...
    
    @property
    def low(self) -> float:
        """Low price."""
        ...
    
    @property
    def close(self) -> float:
        """Close price."""
        ...
    
    @property
    def volume(self) -> float:
        """Trading volume."""
        ...


class Order(Protocol):
    """Protocol for orders."""
    
    @property
    def order_id(self) -> str:
        """Unique order identifier."""
        ...
    
    @property
    def symbol(self) -> str:
        """Trading symbol."""
        ...
    
    @property
    def order_type(self) -> OrderType:
        """Order type."""
        ...
    
    @property
    def side(self) -> OrderSide:
        """Order side."""
        ...
    
    @property
    def quantity(self) -> float:
        """Order quantity."""
        ...
    
    @property
    def price(self) -> Optional[float]:
        """Limit price (for limit orders)."""
        ...
    
    @property
    def status(self) -> OrderStatus:
        """Order status."""
        ...


class Position(Protocol):
    """Protocol for positions."""
    
    @property
    def symbol(self) -> str:
        """Trading symbol."""
        ...
    
    @property
    def quantity(self) -> float:
        """Position quantity (positive for long, negative for short)."""
        ...
    
    @property
    def entry_price(self) -> float:
        """Average entry price."""
        ...
    
    @property
    def current_price(self) -> float:
        """Current market price."""
        ...
    
    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L."""
        ...
    
    @property
    def realized_pnl(self) -> float:
        """Realized P&L."""
        ...


class Signal(Protocol):
    """Protocol for trading signals."""
    
    @property
    def symbol(self) -> str:
        """Trading symbol."""
        ...
    
    @property
    def timestamp(self) -> datetime:
        """Signal timestamp."""
        ...
    
    @property
    def signal_type(self) -> SignalType:
        """Type of signal."""
        ...
    
    @property
    def strength(self) -> float:
        """Signal strength (0-1)."""
        ...
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Additional signal metadata."""
        ...


class Portfolio(Protocol):
    """Protocol for portfolio management."""
    
    @property
    def cash(self) -> float:
        """Available cash."""
        ...
    
    @property
    def total_value(self) -> float:
        """Total portfolio value."""
        ...
    
    @property
    def positions(self) -> Dict[str, Position]:
        """Current positions."""
        ...
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        ...


# Service Interfaces
class DataProvider(Protocol):
    """Interface for data providers."""
    
    async def get_market_data(
        self, 
        symbol: str, 
        start: datetime, 
        end: datetime,
        timeframe: str = "1h"
    ) -> pd.DataFrame:
        """Get historical market data."""
        ...
    
    async def get_realtime_data(self, symbol: str) -> MarketData:
        """Get real-time market data."""
        ...
    
    async def subscribe_market_data(
        self, 
        symbols: List[str], 
        callback: callable
    ) -> None:
        """Subscribe to real-time market data updates."""
        ...


class SignalGenerator(Protocol):
    """Interface for signal generators."""
    
    async def generate_signal(
        self, 
        data: pd.DataFrame,
        portfolio: Portfolio,
        context: Optional[Dict[str, Any]] = None
    ) -> Signal:
        """Generate trading signal from market data."""
        ...
    
    def get_required_history(self) -> int:
        """Get required history length in bars."""
        ...
    
    def get_supported_timeframes(self) -> List[str]:
        """Get supported timeframes."""
        ...


class RiskManager(Protocol):
    """Interface for risk management."""
    
    def calculate_position_size(
        self,
        signal: Signal,
        portfolio: Portfolio,
        market_data: MarketData
    ) -> float:
        """Calculate appropriate position size."""
        ...
    
    def check_risk_limits(
        self,
        order: Order,
        portfolio: Portfolio
    ) -> Tuple[bool, Optional[str]]:
        """Check if order passes risk limits."""
        ...
    
    def calculate_stop_loss(
        self,
        position: Position,
        market_data: MarketData
    ) -> float:
        """Calculate stop loss price."""
        ...
    
    def calculate_take_profit(
        self,
        position: Position,
        market_data: MarketData
    ) -> float:
        """Calculate take profit price."""
        ...


class TradeExecutor(Protocol):
    """Interface for trade execution."""
    
    async def execute_order(self, order: Order) -> Order:
        """Execute an order."""
        ...
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        ...
    
    async def get_order_status(self, order_id: str) -> Order:
        """Get order status."""
        ...
    
    async def get_open_orders(self) -> List[Order]:
        """Get all open orders."""
        ...


class FeatureEngineer(Protocol):
    """Interface for feature engineering."""
    
    def compute_features(
        self,
        data: pd.DataFrame,
        feature_config: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Compute features from raw data."""
        ...
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names."""
        ...
    
    def get_required_columns(self) -> List[str]:
        """Get required input columns."""
        ...


class ModelPredictor(Protocol):
    """Interface for ML model predictions."""
    
    def predict(
        self,
        features: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None
    ) -> Union[float, pd.Series]:
        """Make predictions from features."""
        ...
    
    def get_required_features(self) -> List[str]:
        """Get required feature names."""
        ...
    
    def get_model_metadata(self) -> Dict[str, Any]:
        """Get model metadata."""
        ...


class BacktestEngine(Protocol):
    """Interface for backtesting engines."""
    
    async def run_backtest(
        self,
        strategy: SignalGenerator,
        data: pd.DataFrame,
        initial_capital: float = 10000.0,
        commission: float = 0.001
    ) -> Dict[str, Any]:
        """Run a backtest."""
        ...
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics from last backtest."""
        ...
    
    def get_trades(self) -> pd.DataFrame:
        """Get trade history from last backtest."""
        ...


class LLMAnalyzer(Protocol):
    """Interface for LLM-based analysis."""
    
    async def analyze_market(
        self,
        market_data: pd.DataFrame,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze market conditions using LLM."""
        ...
    
    async def analyze_sentiment(
        self,
        text: str,
        source: Optional[str] = None
    ) -> Dict[str, float]:
        """Analyze sentiment from text."""
        ...
    
    async def validate_signal(
        self,
        signal: Signal,
        market_context: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Validate a trading signal."""
        ...


class WaveAnalyzer(Protocol):
    """Interface for Elliott Wave analysis."""
    
    def identify_waves(
        self,
        data: pd.DataFrame,
        min_wave_size: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Identify Elliott Wave patterns."""
        ...
    
    def get_wave_count(
        self,
        data: pd.DataFrame,
        wave_degree: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get current wave count."""
        ...
    
    def predict_next_move(
        self,
        current_wave: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Predict next wave movement."""
        ...


# Event System
class Event(Protocol):
    """Base event protocol."""
    
    @property
    def event_type(self) -> str:
        """Event type identifier."""
        ...
    
    @property
    def timestamp(self) -> datetime:
        """Event timestamp."""
        ...
    
    @property
    def data(self) -> Dict[str, Any]:
        """Event data."""
        ...


class EventHandler(Protocol):
    """Interface for event handlers."""
    
    async def handle_event(self, event: Event) -> None:
        """Handle an event."""
        ...
    
    def get_supported_events(self) -> List[str]:
        """Get list of supported event types."""
        ...


class EventBus(Protocol):
    """Interface for event bus."""
    
    async def publish(self, event: Event) -> None:
        """Publish an event."""
        ...
    
    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler
    ) -> None:
        """Subscribe to events."""
        ...
    
    async def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler
    ) -> None:
        """Unsubscribe from events."""
        ...


# Storage Interfaces
class DataStorage(Protocol):
    """Interface for data storage."""
    
    async def save_market_data(
        self,
        data: pd.DataFrame,
        symbol: str,
        timeframe: str
    ) -> None:
        """Save market data."""
        ...
    
    async def load_market_data(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str
    ) -> pd.DataFrame:
        """Load market data."""
        ...
    
    async def save_trades(
        self,
        trades: pd.DataFrame,
        strategy_id: str
    ) -> None:
        """Save trade history."""
        ...
    
    async def load_trades(
        self,
        strategy_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Load trade history."""
        ...


# Configuration Interface
class ConfigProvider(Protocol):
    """Interface for configuration management."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        ...
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        ...
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get configuration section."""
        ...
    
    def reload(self) -> None:
        """Reload configuration."""
        ...