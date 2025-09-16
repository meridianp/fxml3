"""Trade Manager package for fxml4."""

__version__ = "0.1.0"

from .position_manager import Position, PositionManager, PositionState
from .risk_monitor import RiskMonitor, RiskLevel, RiskType, RiskAlert, RiskLimits
from .pnl_tracker import PnLTracker, PnLMetrics, PnLPeriod, TradeOutcome
from .exit_strategy_manager import ExitStrategyManager, ExitStrategy, ExitReason, ExitLevel

# Import domain components
from .domain import (
    # Models
    OrderSide, OrderType, OrderStatus, TimeInForce,
    OrderRequest, OrderResponse, OrderModifyRequest,
    BrokerMessageFactory, TradeData, AccountData, MarketData,
    
    # Interfaces
    ITimeProvider, IBrokerAdapter, IPositionRepository,
    IRiskCalculator, IMarketDataProvider, IEventPublisher,
    IMetricsCollector, IPositionManager, IRiskMonitor,
    IPnLTracker, IExitStrategyManager,
    
    # Core Implementations
    UTCTimeProvider, MockTimeProvider,
    
    # Test Implementations
    MockEventPublisher, InMemoryMetricsCollector,
    SimpleRiskCalculator, MockMarketDataProvider,
    MockBrokerAdapter, InMemoryPositionRepository
)

__all__ = [
    # Core Components
    "Position",
    "PositionManager", 
    "PositionState",
    "RiskMonitor",
    "RiskLevel",
    "RiskType",
    "RiskAlert",
    "RiskLimits",
    "PnLTracker",
    "PnLMetrics",
    "PnLPeriod",
    "TradeOutcome",
    "ExitStrategyManager",
    "ExitStrategy",
    "ExitReason",
    "ExitLevel",
    
    # Domain Models
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "TimeInForce",
    "OrderRequest",
    "OrderResponse",
    "OrderModifyRequest",
    "BrokerMessageFactory",
    "TradeData",
    "AccountData",
    "MarketData",
    
    # Domain Interfaces
    "ITimeProvider",
    "IBrokerAdapter",
    "IPositionRepository",
    "IRiskCalculator",
    "IMarketDataProvider",
    "IEventPublisher",
    "IMetricsCollector",
    "IPositionManager",
    "IRiskMonitor",
    "IPnLTracker",
    "IExitStrategyManager",
    
    # Time Providers
    "UTCTimeProvider",
    "MockTimeProvider",
    
    # Test Implementations
    "MockEventPublisher",
    "InMemoryMetricsCollector",
    "SimpleRiskCalculator",
    "MockMarketDataProvider",
    "MockBrokerAdapter",
    "InMemoryPositionRepository"
]