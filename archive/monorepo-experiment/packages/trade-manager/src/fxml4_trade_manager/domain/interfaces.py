"""Abstract interfaces for Trade Manager components."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal

from .models import (
    OrderRequest, OrderResponse, OrderModifyRequest,
    TradeData, AccountData, MarketData,
    OrderSide, OrderStatus
)


class ITimeProvider(ABC):
    """Interface for time operations."""
    
    @abstractmethod
    def now(self) -> datetime:
        """Get current UTC time."""
        pass
    
    @abstractmethod
    def today(self) -> datetime:
        """Get current UTC date at midnight."""
        pass


class IBrokerAdapter(ABC):
    """Interface for broker operations."""
    
    @abstractmethod
    async def place_order(self, order_request: OrderRequest) -> OrderResponse:
        """Place an order with the broker."""
        pass
    
    @abstractmethod
    async def modify_order(self, modify_request: OrderModifyRequest) -> OrderResponse:
        """Modify an existing order."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> OrderResponse:
        """Cancel an existing order."""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get the status of an order."""
        pass


class IPositionRepository(ABC):
    """Interface for position data storage."""
    
    @abstractmethod
    async def create(self, position_data: Dict[str, Any]) -> str:
        """Create a new position and return its ID."""
        pass
    
    @abstractmethod
    async def get(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get position by ID."""
        pass
    
    @abstractmethod
    async def update(self, position_id: str, updates: Dict[str, Any]) -> bool:
        """Update position data."""
        pass
    
    @abstractmethod
    async def delete(self, position_id: str) -> bool:
        """Delete a position."""
        pass
    
    @abstractmethod
    async def find_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Find all positions for a symbol."""
        pass
    
    @abstractmethod
    async def find_open_positions(self) -> List[Dict[str, Any]]:
        """Find all open positions."""
        pass


class IRiskCalculator(ABC):
    """Interface for risk calculations."""
    
    @abstractmethod
    def calculate_position_size(
        self,
        account_balance: Decimal,
        risk_percentage: Decimal,
        stop_loss_pips: Decimal,
        pip_value: Decimal
    ) -> Decimal:
        """Calculate appropriate position size."""
        pass
    
    @abstractmethod
    def calculate_risk_amount(
        self,
        position_size: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        side: OrderSide
    ) -> Decimal:
        """Calculate risk amount for a position."""
        pass
    
    @abstractmethod
    def calculate_risk_reward_ratio(
        self,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        take_profit_price: Decimal,
        side: OrderSide
    ) -> Decimal:
        """Calculate risk/reward ratio."""
        pass


class IMarketDataProvider(ABC):
    """Interface for market data operations."""
    
    @abstractmethod
    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current price for a symbol."""
        pass
    
    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get comprehensive market data for a symbol."""
        pass
    
    @abstractmethod
    async def get_volatility(self, symbol: str) -> Decimal:
        """Get current volatility for a symbol."""
        pass
    
    @abstractmethod
    async def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Get correlation between two symbols."""
        pass


class IEventPublisher(ABC):
    """Interface for publishing events."""
    
    @abstractmethod
    async def publish(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Publish an event."""
        pass
    
    @abstractmethod
    async def publish_batch(self, events: List[Tuple[str, Dict[str, Any]]]) -> None:
        """Publish multiple events."""
        pass


class IMetricsCollector(ABC):
    """Interface for collecting metrics."""
    
    @abstractmethod
    def record_trade_outcome(
        self,
        symbol: str,
        pnl: Decimal,
        duration_seconds: int,
        outcome: str
    ) -> None:
        """Record trade outcome metrics."""
        pass
    
    @abstractmethod
    def record_risk_violation(
        self,
        risk_type: str,
        severity: str,
        details: Dict[str, Any]
    ) -> None:
        """Record risk violation."""
        pass
    
    @abstractmethod
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        pass


class IPositionManager(ABC):
    """Interface for position management operations."""
    
    @abstractmethod
    async def create_position(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new position."""
        pass
    
    @abstractmethod
    async def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get position by ID."""
        pass
    
    @abstractmethod
    async def update_position_fill(
        self,
        position_id: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal('0')
    ) -> bool:
        """Update position with a fill."""
        pass
    
    @abstractmethod
    async def update_position_exit(
        self,
        position_id: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal('0')
    ) -> bool:
        """Update position with an exit."""
        pass
    
    @abstractmethod
    async def update_position_price(self, position_id: str, price: Decimal) -> bool:
        """Update position current price."""
        pass
    
    @abstractmethod
    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        pass


class IRiskMonitor(ABC):
    """Interface for risk monitoring operations."""
    
    @abstractmethod
    async def check_pre_trade_risk(
        self,
        trade_request: TradeData,
        account_data: AccountData,
        positions: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """Check if a trade passes risk checks."""
        pass
    
    @abstractmethod
    async def update_position_risk(
        self,
        position: Dict[str, Any],
        market_data: MarketData
    ) -> None:
        """Update risk metrics for a position."""
        pass
    
    @abstractmethod
    async def check_portfolio_risk(
        self,
        positions: List[Dict[str, Any]],
        account_data: AccountData
    ) -> Dict[str, Any]:
        """Check overall portfolio risk."""
        pass
    
    @abstractmethod
    async def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk summary."""
        pass


class IPnLTracker(ABC):
    """Interface for P&L tracking operations."""
    
    @abstractmethod
    async def record_trade_open(self, trade_data: Dict[str, Any]) -> None:
        """Record a new trade opening."""
        pass
    
    @abstractmethod
    async def update_position_pnl(
        self,
        position_id: str,
        current_price: Decimal,
        partial_exit: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update P&L for a position."""
        pass
    
    @abstractmethod
    async def record_trade_close(
        self,
        position_id: str,
        exit_price: Decimal,
        exit_time: Optional[datetime] = None,
        commission: Decimal = Decimal('0')
    ) -> None:
        """Record a trade closing."""
        pass
    
    @abstractmethod
    async def get_performance_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get performance summary."""
        pass


class IExitStrategyManager(ABC):
    """Interface for exit strategy management."""
    
    @abstractmethod
    async def assign_strategy(
        self,
        position_id: str,
        strategy_id: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Assign exit strategy to position."""
        pass
    
    @abstractmethod
    async def calculate_exit_levels(
        self,
        position_data: Dict[str, Any],
        market_data: Optional[MarketData] = None
    ) -> Dict[str, Decimal]:
        """Calculate exit levels for a position."""
        pass
    
    @abstractmethod
    async def create_exit_orders(
        self,
        position_data: Dict[str, Any],
        exit_levels: Dict[str, Decimal],
        broker_adapter: IBrokerAdapter
    ) -> Dict[str, str]:
        """Create exit orders for a position."""
        pass
    
    @abstractmethod
    async def update_trailing_stop(
        self,
        position_data: Dict[str, Any],
        current_price: Decimal,
        broker_adapter: IBrokerAdapter
    ) -> Optional[str]:
        """Update trailing stop for position."""
        pass
    
    @abstractmethod
    async def check_time_exits(
        self,
        position_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check if position should be exited based on time."""
        pass