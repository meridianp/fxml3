"""
Enterprise Trade Execution Engine for FXML4 Trading Platform

This module implements a comprehensive trade execution system that converts ML signals
and Elliott Wave patterns into executed trades with intelligent routing, risk management,
and performance monitoring.

Key Features:
- Signal-to-trade conversion with risk-managed position sizing
- Multiple execution strategies (Market, TWAP, VWAP)
- Cross-broker position tracking and correlation analysis
- Real-time execution performance monitoring and cost analysis
- Integration with Order Management System and all broker adapters
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from fxml4.messaging.messages import OrderSide, OrderStatus, OrderType
from fxml4.order_management import OrderManager, OrderRequest, OrderResponse

logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTIONS
# ============================================================================


class TradeExecutionError(Exception):
    """Raised when trade execution encounters an error."""

    pass


class InsufficientCapitalError(TradeExecutionError):
    """Raised when insufficient capital for trade execution."""

    pass


# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class ValidationResult:
    """Signal or trade validation result."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class TradingSignal(BaseModel):
    """Trading signal from ML ensemble or Elliott Wave analysis."""

    signal_id: str = Field(default_factory=lambda: f"SIG_{str(uuid4())[:8].upper()}")
    symbol: str
    signal_type: str  # ML_ENSEMBLE, ELLIOTT_WAVE, HYBRID
    direction: str  # BUY, SELL
    strength: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    entry_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    timeframe: Optional[str] = None
    source_models: List[str] = field(default_factory=list)
    pattern_type: Optional[str] = None  # For Elliott Wave
    wave_count: Optional[str] = None  # For Elliott Wave
    generated_at: datetime = field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_encoders={Decimal: lambda v: str(v), datetime: lambda v: v.isoformat()}
    )

    def validate(self) -> ValidationResult:
        """Validate trading signal parameters."""
        errors = []
        warnings = []

        if not self.signal_id:
            errors.append("Signal ID is required")

        if not self.symbol:
            errors.append("Symbol is required")

        if self.signal_type not in ["ML_ENSEMBLE", "ELLIOTT_WAVE", "HYBRID"]:
            errors.append("Invalid signal type")

        if self.direction not in ["BUY", "SELL"]:
            errors.append("Direction must be BUY or SELL")

        if not (0.0 <= self.strength <= 1.0):
            errors.append("Strength must be between 0.0 and 1.0")

        if not (0.0 <= self.confidence <= 1.0):
            errors.append("Confidence must be between 0.0 and 1.0")

        # Warnings for weak signals
        if self.strength < 0.6:
            warnings.append("Low signal strength")

        if self.confidence < 0.7:
            warnings.append("Low signal confidence")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )


class TradeRequest(BaseModel):
    """Processed trade request ready for execution."""

    request_id: str = Field(default_factory=lambda: f"REQ_{str(uuid4())[:8].upper()}")
    signal_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    expected_entry: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    signal_strength: float = 0.0
    signal_confidence: float = 0.0
    execution_strategy: str = "MARKET"
    pattern_info: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


class Position(BaseModel):
    """Cross-broker position tracking."""

    position_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    entry_price: Decimal
    current_price: Optional[Decimal] = None
    broker: str
    strategy_id: Optional[str] = None
    opened_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P&L."""
        if not self.current_price:
            return Decimal("0")

        if self.side == OrderSide.BUY:
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def market_value(self) -> Decimal:
        """Calculate current market value."""
        price = self.current_price or self.entry_price
        return price * self.quantity


class TradeExecution(BaseModel):
    """Trade execution result with performance metrics."""

    execution_id: str
    trade_id: str
    symbol: str
    side: OrderSide
    requested_quantity: Decimal
    filled_quantity: Decimal
    average_fill_price: Decimal
    expected_price: Optional[Decimal] = None
    execution_time_ms: float
    commission: Decimal = Decimal("0")
    slippage_bps: float = 0.0
    orders_used: List[str] = field(default_factory=list)
    executed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExecutionResult:
    """Overall execution result summary."""

    success: bool
    signal_id: str
    trade_id: str = ""
    orders_placed: int = 0
    total_quantity: Decimal = Decimal("0")
    average_price: Optional[Decimal] = None
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """Execution strategy plan."""

    strategy_type: str
    orders: List[Dict[str, Any]] = field(default_factory=list)
    estimated_time_ms: float = 0.0
    expected_slippage_bps: float = 0.0


# ============================================================================
# SIGNAL PROCESSING
# ============================================================================


class SignalProcessor:
    """ML signal processing and trade decision logic."""

    def __init__(
        self,
        min_confidence: float = 0.7,
        min_strength: float = 0.6,
        supported_symbols: List[str] = None,
        max_position_size: float = 500000,
        base_risk_percent: float = 0.02,
    ):
        self.min_confidence = min_confidence
        self.min_strength = min_strength
        self.supported_symbols = supported_symbols or [
            "EUR/USD",
            "GBP/USD",
            "USD/JPY",
            "USD/CHF",
        ]
        self.max_position_size = max_position_size
        self.base_risk_percent = base_risk_percent

    async def process_signal(self, signal: TradingSignal) -> Optional[TradeRequest]:
        """Process trading signal and convert to trade request."""

        # 1. Validate signal
        validation = signal.validate()
        if not validation.is_valid:
            logger.warning(f"Invalid signal {signal.signal_id}: {validation.errors}")
            return None

        # 2. Check signal strength/confidence thresholds
        if (
            signal.strength < self.min_strength
            or signal.confidence < self.min_confidence
        ):
            logger.info(
                f"Signal {signal.signal_id} rejected: strength={signal.strength:.2f}, confidence={signal.confidence:.2f}"
            )
            return None

        # 3. Check symbol support
        if self.supported_symbols and signal.symbol not in self.supported_symbols:
            logger.warning(f"Symbol {signal.symbol} not supported")
            return None

        # 4. Convert direction to OrderSide
        side = OrderSide.BUY if signal.direction == "BUY" else OrderSide.SELL

        # 5. Calculate position size (will be refined by risk management)
        base_quantity = self.max_position_size * signal.strength * signal.confidence

        # 6. Determine execution strategy based on signal type and size
        execution_strategy = self._determine_execution_strategy(signal, base_quantity)

        # 7. Create trade request
        trade_request = TradeRequest(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            side=side,
            quantity=Decimal(str(base_quantity)),
            expected_entry=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            signal_strength=signal.strength,
            signal_confidence=signal.confidence,
            execution_strategy=execution_strategy,
        )

        # 8. Add pattern info for Elliott Wave signals
        if signal.signal_type == "ELLIOTT_WAVE":
            trade_request.pattern_info = {
                "type": signal.pattern_type,
                "wave_count": signal.wave_count,
            }

        return trade_request

    def calculate_position_size(
        self,
        account_balance: float,
        signal_strength: float,
        signal_confidence: float,
        risk_percent: float = None,
    ) -> float:
        """Calculate intelligent position size based on signal quality."""

        risk_pct = risk_percent or self.base_risk_percent

        # Base risk amount
        base_risk_amount = account_balance * risk_pct

        # Adjust based on signal quality (strength * confidence)
        quality_multiplier = signal_strength * signal_confidence

        # Scale position size (0.5x to 2.0x based on quality)
        size_multiplier = 0.5 + (1.5 * quality_multiplier)

        # Calculate position size (assuming 1% price movement for sizing)
        position_size = base_risk_amount * size_multiplier * 100  # 100x for 1% move

        # Apply limits
        return min(position_size, self.max_position_size)

    def _determine_execution_strategy(
        self, signal: TradingSignal, quantity: float
    ) -> str:
        """Determine optimal execution strategy."""

        # Large orders use TWAP to minimize market impact
        if quantity > 300000:
            return "TWAP"

        # High-confidence Elliott Wave patterns can use VWAP
        elif signal.signal_type == "ELLIOTT_WAVE" and signal.confidence > 0.85:
            return "VWAP"

        # Default to immediate market execution
        else:
            return "MARKET"


# ============================================================================
# EXECUTION STRATEGIES
# ============================================================================


class ExecutionStrategy:
    """Different execution algorithms for trade execution."""

    def __init__(
        self,
        strategy_type: str = "MARKET",
        max_order_size: float = 100000,
        time_limit_minutes: int = 30,
        execution_window_minutes: int = 60,
        slice_count: int = 10,
        volume_participation_rate: float = 0.1,
    ):
        self.strategy_type = strategy_type
        self.max_order_size = max_order_size
        self.time_limit_minutes = time_limit_minutes
        self.execution_window_minutes = execution_window_minutes
        self.slice_count = slice_count
        self.volume_participation_rate = volume_participation_rate

    async def plan_execution(
        self, trade_request: TradeRequest, order_manager
    ) -> ExecutionPlan:
        """Plan execution strategy for trade request."""

        if self.strategy_type == "MARKET":
            return await self._plan_market_execution(trade_request)
        elif self.strategy_type == "TWAP":
            return await self._plan_twap_execution(trade_request)
        elif self.strategy_type == "VWAP":
            return await self._plan_vwap_execution(trade_request)
        else:
            raise TradeExecutionError(
                f"Unknown execution strategy: {self.strategy_type}"
            )

    async def _plan_market_execution(
        self, trade_request: TradeRequest
    ) -> ExecutionPlan:
        """Plan immediate market execution."""

        orders = [
            {
                "order_type": OrderType.MARKET,
                "quantity": float(trade_request.quantity),
                "side": trade_request.side,
            }
        ]

        return ExecutionPlan(
            strategy_type="MARKET",
            orders=orders,
            estimated_time_ms=500,  # Very fast execution
            expected_slippage_bps=1.0,  # Minimal slippage for market orders
        )

    async def _plan_twap_execution(self, trade_request: TradeRequest) -> ExecutionPlan:
        """Plan Time Weighted Average Price execution."""

        total_quantity = float(trade_request.quantity)
        slice_size = total_quantity / self.slice_count

        orders = []
        for i in range(self.slice_count):
            # Adjust last slice for rounding
            quantity = (
                slice_size
                if i < self.slice_count - 1
                else total_quantity - (slice_size * i)
            )

            orders.append(
                {
                    "order_type": OrderType.LIMIT,  # Use limits for better price control
                    "quantity": quantity,
                    "side": trade_request.side,
                    "delay_minutes": i
                    * (self.execution_window_minutes / self.slice_count),
                }
            )

        return ExecutionPlan(
            strategy_type="TWAP",
            orders=orders,
            estimated_time_ms=self.execution_window_minutes * 60 * 1000,
            expected_slippage_bps=0.5,  # Lower slippage due to smaller orders
        )

    async def _plan_vwap_execution(self, trade_request: TradeRequest) -> ExecutionPlan:
        """Plan Volume Weighted Average Price execution."""

        # Get volume profile (mocked for now)
        volume_profile = await self._get_volume_profile(trade_request.symbol)

        total_quantity = float(trade_request.quantity)
        volume_slices = []

        # Distribute quantity based on volume profile
        for i, relative_volume in enumerate(
            volume_profile.get("volume_distribution", [1.0])
        ):
            slice_quantity = (
                total_quantity / len(volume_profile["volume_distribution"])
            ) * relative_volume
            volume_slices.append(slice_quantity)

        orders = []
        for i, quantity in enumerate(volume_slices):
            orders.append(
                {
                    "order_type": OrderType.LIMIT,
                    "quantity": quantity,
                    "side": trade_request.side,
                    "delay_minutes": i * 5,  # 5-minute intervals
                }
            )

        return ExecutionPlan(
            strategy_type="VWAP",
            orders=orders,
            estimated_time_ms=len(volume_slices) * 5 * 60 * 1000,
            expected_slippage_bps=0.3,  # Best execution with volume matching
        )

    async def _get_volume_profile(self, symbol: str) -> Dict[str, Any]:
        """Get volume profile for symbol (mocked implementation)."""
        return {
            "avg_volume_per_5min": 50000,
            "volume_distribution": [0.8, 1.2, 1.0, 0.9, 1.1, 0.7],  # Relative volumes
        }


# ============================================================================
# POSITION MANAGEMENT
# ============================================================================


class PositionManager:
    """Cross-broker position tracking and risk monitoring."""

    def __init__(
        self,
        max_portfolio_risk: float = 0.06,  # 6% portfolio risk
        max_correlation: float = 0.8,
        position_timeout_hours: int = 24,
    ):
        self.max_portfolio_risk = max_portfolio_risk
        self.max_correlation = max_correlation
        self.position_timeout_hours = position_timeout_hours

        # Position tracking
        self.active_positions: Dict[str, Position] = {}
        self.position_history: Dict[str, Position] = {}

        # Symbol correlation matrix (simplified)
        self.correlation_matrix = {
            ("EUR/USD", "GBP/USD"): 0.85,
            ("EUR/USD", "USD/CHF"): -0.75,
            ("GBP/USD", "USD/JPY"): 0.15,
            ("USD/JPY", "USD/CHF"): 0.45,
        }

    async def add_position(self, position: Position) -> None:
        """Add new position to tracking."""
        self.active_positions[position.position_id] = position
        logger.info(
            f"Added position {position.position_id}: {position.symbol} {position.side.value} {position.quantity}"
        )

    async def update_position(self, position_id: str, current_price: Decimal) -> None:
        """Update position with current market price."""
        if position_id in self.active_positions:
            self.active_positions[position_id].current_price = current_price
            self.active_positions[position_id].updated_at = datetime.utcnow()

    async def close_position(self, position_id: str) -> None:
        """Close position and move to history."""
        if position_id in self.active_positions:
            position = self.active_positions[position_id]
            self.position_history[position_id] = position
            del self.active_positions[position_id]
            logger.info(f"Closed position {position_id}")

    def get_symbol_exposure(self, symbol: str) -> float:
        """Get total exposure for a symbol across all positions."""
        total_exposure = 0
        for position in self.active_positions.values():
            if position.symbol == symbol:
                exposure = float(position.quantity)
                if position.side == OrderSide.SELL:
                    exposure = -exposure
                total_exposure += exposure
        return total_exposure

    def calculate_portfolio_risk(self, account_balance: float) -> Dict[str, Any]:
        """Calculate comprehensive portfolio risk metrics."""

        total_exposure = 0
        total_unrealized_pnl = Decimal("0")
        risk_by_symbol = defaultdict(float)
        positions_data = []

        for position in self.active_positions.values():
            # Market value exposure
            market_value = float(position.market_value)
            total_exposure += market_value

            # Unrealized P&L
            total_unrealized_pnl += position.unrealized_pnl

            # Risk by symbol
            risk_by_symbol[position.symbol] += market_value

            # Position data
            positions_data.append(
                {
                    "position_id": position.position_id,
                    "symbol": position.symbol,
                    "side": position.side.value,
                    "quantity": float(position.quantity),
                    "market_value": market_value,
                    "unrealized_pnl": float(position.unrealized_pnl),
                }
            )

        # Calculate risk percentages
        portfolio_risk_pct = (
            (total_exposure / account_balance) if account_balance > 0 else 0
        )

        return {
            "total_exposure": total_exposure,
            "portfolio_risk_percent": portfolio_risk_pct,
            "unrealized_pnl": float(total_unrealized_pnl),
            "risk_by_symbol": dict(risk_by_symbol),
            "positions": positions_data,
            "position_count": len(self.active_positions),
        }

    def check_correlation_risk(
        self, new_symbol: str, new_side: OrderSide
    ) -> Dict[str, Any]:
        """Check correlation risk for new position."""

        high_correlation_positions = []
        max_correlation = 0

        for position in self.active_positions.values():
            # Check correlation between symbols
            correlation = self._get_correlation(position.symbol, new_symbol)

            if correlation and abs(correlation) > self.max_correlation:
                # Same direction increases correlation risk
                if position.side == new_side:
                    risk_multiplier = abs(correlation)
                else:
                    risk_multiplier = (
                        abs(correlation) * 0.5
                    )  # Opposite directions reduce risk

                high_correlation_positions.append(
                    {
                        "position_id": position.position_id,
                        "symbol": position.symbol,
                        "correlation": correlation,
                        "risk_multiplier": risk_multiplier,
                    }
                )

                max_correlation = max(max_correlation, abs(correlation))

        return {
            "high_correlation": max_correlation > self.max_correlation,
            "correlation_score": max_correlation,
            "correlated_positions": high_correlation_positions,
        }

    def _get_correlation(self, symbol1: str, symbol2: str) -> Optional[float]:
        """Get correlation between two symbols."""
        key1 = (symbol1, symbol2)
        key2 = (symbol2, symbol1)

        if key1 in self.correlation_matrix:
            return self.correlation_matrix[key1]
        elif key2 in self.correlation_matrix:
            return self.correlation_matrix[key2]

        return None


# ============================================================================
# EXECUTION MONITORING
# ============================================================================


class ExecutionMonitor:
    """Execution performance monitoring and cost analysis."""

    def __init__(
        self, performance_targets: Dict[str, float] = None, history_size: int = 1000
    ):
        self.performance_targets = performance_targets or {
            "fill_rate": 0.98,
            "slippage_bps": 2.0,
            "execution_time_seconds": 30,
        }
        self.history_size = history_size

        # Execution tracking
        self.execution_history = deque(maxlen=history_size)
        self.daily_stats = defaultdict(list)

    async def record_execution(self, execution: TradeExecution) -> None:
        """Record trade execution for performance monitoring."""

        execution_data = {
            "execution_id": execution.execution_id,
            "symbol": execution.symbol,
            "side": execution.side.value,
            "quantity": float(execution.filled_quantity),
            "fill_rate": float(execution.filled_quantity)
            / float(execution.requested_quantity),
            "slippage_bps": execution.slippage_bps,
            "execution_time_ms": execution.execution_time_ms,
            "commission": float(execution.commission),
            "timestamp": execution.executed_at,
        }

        self.execution_history.append(execution_data)

        # Update daily stats
        date_key = execution.executed_at.date()
        self.daily_stats[date_key].append(execution_data)

        logger.info(
            f"Recorded execution {execution.execution_id}: {execution.symbol} {execution.side.value}"
        )

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""

        if not self.execution_history:
            return {
                "total_executions": 0,
                "average_slippage_bps": 0.0,
                "average_execution_time_ms": 0.0,
                "fill_rate": 0.0,
                "total_commission": 0.0,
            }

        total_executions = len(self.execution_history)
        total_slippage = sum(e["slippage_bps"] for e in self.execution_history)
        total_exec_time = sum(e["execution_time_ms"] for e in self.execution_history)
        total_fill_rate = sum(e["fill_rate"] for e in self.execution_history)
        total_commission = sum(e["commission"] for e in self.execution_history)

        return {
            "total_executions": total_executions,
            "average_slippage_bps": total_slippage / total_executions,
            "average_execution_time_ms": total_exec_time / total_executions,
            "fill_rate": total_fill_rate / total_executions,
            "total_commission": total_commission,
            "performance_vs_targets": self._check_performance_targets(),
        }

    def calculate_execution_costs(self) -> Dict[str, float]:
        """Calculate detailed execution cost analysis."""

        if not self.execution_history:
            return {
                "total_commission": 0.0,
                "average_slippage_bps": 0.0,
                "cost_per_million": 0.0,
            }

        total_commission = sum(e["commission"] for e in self.execution_history)
        total_quantity = sum(e["quantity"] for e in self.execution_history)
        total_slippage = sum(e["slippage_bps"] for e in self.execution_history)

        return {
            "total_commission": total_commission,
            "average_slippage_bps": total_slippage / len(self.execution_history),
            "cost_per_million": (
                (total_commission / (total_quantity / 1000000))
                if total_quantity > 0
                else 0.0
            ),
            "total_volume": total_quantity,
        }

    def _check_performance_targets(self) -> Dict[str, bool]:
        """Check if performance meets targets."""

        if not self.execution_history:
            return {"fill_rate_met": True, "slippage_met": True, "time_met": True}

        # Calculate metrics directly to avoid recursion
        total_executions = len(self.execution_history)
        avg_fill_rate = (
            sum(e["fill_rate"] for e in self.execution_history) / total_executions
        )
        avg_slippage = (
            sum(e["slippage_bps"] for e in self.execution_history) / total_executions
        )
        avg_exec_time = (
            sum(e["execution_time_ms"] for e in self.execution_history)
            / total_executions
        )

        return {
            "fill_rate_met": avg_fill_rate >= self.performance_targets["fill_rate"],
            "slippage_met": avg_slippage <= self.performance_targets["slippage_bps"],
            "time_met": avg_exec_time
            <= (self.performance_targets["execution_time_seconds"] * 1000),
        }


# ============================================================================
# MAIN TRADE EXECUTION ENGINE
# ============================================================================


class TradeExecutionEngine:
    """Main trade execution engine orchestrating signal-to-trade conversion."""

    def __init__(
        self,
        account_balance: float = 1000000,
        max_positions: int = 20,
        risk_config: Dict[str, Any] = None,
        audit_config: Dict[str, Any] = None,
        order_manager: Optional[OrderManager] = None,
    ):
        self.account_balance = account_balance
        self.max_positions = max_positions
        self.risk_config = risk_config or {
            "max_risk_per_trade": 0.02,
            "max_portfolio_risk": 0.06,
        }
        self.audit_config = audit_config or {}

        # Core components
        self.signal_processor = SignalProcessor(
            base_risk_percent=self.risk_config.get("max_risk_per_trade", 0.02)
        )
        self.position_manager = PositionManager(
            max_portfolio_risk=self.risk_config.get("max_portfolio_risk", 0.06)
        )
        self.execution_monitor = ExecutionMonitor()

        # Order management integration
        self.order_manager = order_manager

        # Execution tracking
        self.execution_count = 0
        self.successful_executions = 0

    async def execute_trade(self, signal: TradingSignal) -> ExecutionResult:
        """Execute complete trade from signal to order placement."""

        start_time = time.time()

        try:
            # 1. Process signal into trade request
            trade_request = await self.signal_processor.process_signal(signal)
            if not trade_request:
                return ExecutionResult(
                    success=False,
                    signal_id=signal.signal_id,
                    error_message="Signal rejected by processor",
                )

            # 2. Risk management checks
            await self._validate_risk_limits(trade_request)

            # 3. Refine position sizing based on portfolio
            refined_quantity = await self._calculate_portfolio_adjusted_size(
                trade_request
            )
            trade_request.quantity = Decimal(str(refined_quantity))

            # 4. Plan execution strategy
            execution_strategy = ExecutionStrategy(
                strategy_type=trade_request.execution_strategy
            )
            execution_plan = await execution_strategy.plan_execution(
                trade_request, self.order_manager
            )

            # 5. Execute orders through Order Management System
            orders_placed = []
            if self.order_manager:
                for order_plan in execution_plan.orders:
                    order_request = OrderRequest(
                        symbol=trade_request.symbol,
                        side=trade_request.side,
                        order_type=order_plan["order_type"],
                        quantity=Decimal(str(order_plan["quantity"])),
                    )

                    order_response = await self.order_manager.create_order(
                        order_request
                    )
                    if order_response.success:
                        orders_placed.append(order_response.order_id)

            # 6. Create position tracking
            if orders_placed:
                position = Position(
                    position_id=f"POS_{str(uuid4())[:8].upper()}",
                    symbol=trade_request.symbol,
                    side=trade_request.side,
                    quantity=trade_request.quantity,
                    entry_price=trade_request.expected_entry or Decimal("0"),
                    broker="AUTO_ROUTED",
                    strategy_id=signal.signal_type,
                )
                await self.position_manager.add_position(position)

            # 7. Record execution performance
            execution_time_ms = (time.time() - start_time) * 1000

            self.execution_count += 1
            if orders_placed:
                self.successful_executions += 1

            return ExecutionResult(
                success=len(orders_placed) > 0,
                signal_id=signal.signal_id,
                trade_id=trade_request.request_id,
                orders_placed=len(orders_placed),
                total_quantity=trade_request.quantity,
                execution_time_ms=execution_time_ms,
                performance_metrics={
                    "execution_strategy": execution_plan.strategy_type,
                    "orders_count": len(orders_placed),
                },
            )

        except (TradeExecutionError, InsufficientCapitalError) as e:
            # Re-raise specific trading errors
            raise

        except Exception as e:
            logger.error(f"Trade execution failed for signal {signal.signal_id}: {e}")
            return ExecutionResult(
                success=False,
                signal_id=signal.signal_id,
                error_message=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _validate_risk_limits(self, trade_request: TradeRequest) -> None:
        """Validate trade against risk limits."""

        # 1. Check account balance
        position_value = float(
            trade_request.quantity * (trade_request.expected_entry or Decimal("1"))
        )
        if position_value > self.account_balance * 0.2:  # Max 20% of account per trade
            raise InsufficientCapitalError(
                f"Trade size {position_value:,.2f} exceeds capital limits"
            )

        # 2. Check portfolio risk
        portfolio_risk = self.position_manager.calculate_portfolio_risk(
            self.account_balance
        )
        max_portfolio_risk = self.risk_config.get("max_portfolio_risk", 0.06)

        if portfolio_risk["portfolio_risk_percent"] > max_portfolio_risk:
            raise TradeExecutionError(
                f"Portfolio risk limit exceeded: {portfolio_risk['portfolio_risk_percent']:.2%}"
            )

        # 3. Check position limits
        if len(self.position_manager.active_positions) >= self.max_positions:
            raise TradeExecutionError(
                f"Maximum positions limit exceeded: {self.max_positions}"
            )

        # 4. Check correlation risk
        correlation_check = self.position_manager.check_correlation_risk(
            trade_request.symbol, trade_request.side
        )

        if correlation_check["high_correlation"]:
            logger.warning(
                f"High correlation risk detected: {correlation_check['correlation_score']:.2f}"
            )

    async def _calculate_portfolio_adjusted_size(
        self, trade_request: TradeRequest
    ) -> float:
        """Calculate position size adjusted for portfolio composition."""

        # Start with signal processor size
        base_size = float(trade_request.quantity)

        # Get current portfolio risk
        portfolio_risk = self.position_manager.calculate_portfolio_risk(
            self.account_balance
        )

        # Reduce size if portfolio risk is high
        if portfolio_risk["portfolio_risk_percent"] > 0.03:  # Above 3%
            risk_reduction_factor = 0.5 + (
                0.5 * (0.06 - portfolio_risk["portfolio_risk_percent"]) / 0.03
            )
            base_size *= max(risk_reduction_factor, 0.1)  # Minimum 10% of original size

        # Check symbol concentration
        symbol_exposure = abs(
            self.position_manager.get_symbol_exposure(trade_request.symbol)
        )
        max_symbol_exposure = self.account_balance * 0.1  # Max 10% per symbol

        if symbol_exposure > max_symbol_exposure:
            concentration_factor = max(
                (max_symbol_exposure - symbol_exposure) / max_symbol_exposure, 0.1
            )
            base_size *= concentration_factor

        return max(base_size, 10000)  # Minimum position size
