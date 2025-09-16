"""
Trading Engine Service for FXML4 API.

The core orchestration service that coordinates the complete trading workflow:
signals → orders → execution → position management.

This service manages the trading loop, decision making, error recovery, and system states.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import asyncpg
from pydantic import BaseModel, Field

from fxml4.api.services.market_data import market_data_service
from fxml4.api.services.order_management import (
    OrderData,
    OrderExecution,
    OrderSide,
    OrderType,
    order_management_service,
)
from fxml4.api.services.signal_processing import SignalData, signal_processing_service

logger = logging.getLogger(__name__)


class TradingEngineState(str, Enum):
    """Trading engine operational states."""

    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class TradingMode(str, Enum):
    """Trading execution modes."""

    MANUAL = "manual"  # Manual approval required for all trades
    SEMI_AUTO = "semi_auto"  # Auto-execute high confidence signals
    FULLY_AUTO = "fully_auto"  # Auto-execute all valid signals


class PositionData(BaseModel):
    """Position tracking data."""

    symbol: str
    quantity: float = 0.0
    avg_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: float = 0.0
    open_orders: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class TradingEngineConfig(BaseModel):
    """Trading engine configuration."""

    trading_mode: TradingMode = TradingMode.MANUAL
    enabled_symbols: Set[str] = Field(default_factory=set)

    # Signal processing
    min_signal_confidence: float = 0.5
    signal_timeout_minutes: int = 5

    # Risk management
    max_position_size: float = 100000.0
    max_daily_volume: float = 1000000.0
    max_orders_per_hour: int = 50

    # Auto-execution thresholds
    auto_execute_confidence: float = 0.8
    position_size_multiplier: float = 1.0

    # System limits
    max_concurrent_orders: int = 20
    order_timeout_minutes: int = 15

    # Circuit breaker settings
    max_errors_per_minute: int = 10
    circuit_breaker_pause_minutes: int = 5


class TradingEngineMetrics(BaseModel):
    """Trading engine performance metrics."""

    signals_processed: int = 0
    orders_created: int = 0
    orders_executed: int = 0
    orders_cancelled: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_pnl: float = 0.0
    active_positions: int = 0
    uptime_seconds: float = 0.0
    last_signal_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None

    # Circuit breaker metrics
    errors: int = 0
    recent_errors: List[datetime] = Field(default_factory=list)
    circuit_breaker_triggered: bool = False
    circuit_breaker_until: Optional[datetime] = None


class TradingEngine:
    """Core trading engine for orchestrating the complete trading workflow."""

    def __init__(self):
        self.state = TradingEngineState.INACTIVE
        self.config = TradingEngineConfig()
        self.metrics = TradingEngineMetrics()

        # Position tracking
        self.positions: Dict[str, PositionData] = {}

        # System state
        self.start_time: Optional[datetime] = None
        self.error_message: Optional[str] = None

        # Background tasks
        self.engine_task: Optional[asyncio.Task] = None
        self.monitoring_task: Optional[asyncio.Task] = None
        self.position_update_task: Optional[asyncio.Task] = None

        # Event handlers
        self.signal_callbacks: List[Callable[[SignalData], None]] = []
        self.order_callbacks: List[Callable[[OrderData], None]] = []
        self.execution_callbacks: List[Callable[[OrderExecution], None]] = []
        self.state_callbacks: List[Callable[[TradingEngineState], None]] = []

        # Database connection
        self._pool = None

    async def initialize(self):
        """Initialize the trading engine."""
        try:
            logger.info("Initializing Trading Engine...")

            self._update_state(TradingEngineState.STARTING)

            # Get database connection pool
            self._pool = await market_data_service.get_connection_pool()

            # Initialize dependent services if not already done
            await signal_processing_service.initialize()
            await order_management_service.initialize()

            # Load configuration from database
            await self._load_configuration()

            # Load current positions
            await self._load_positions()

            # Set up service callbacks
            self._setup_service_callbacks()

            # Initialize metrics
            self.start_time = datetime.utcnow()

            logger.info("Trading Engine initialized successfully")
            self._update_state(TradingEngineState.INACTIVE)

        except Exception as e:
            logger.error(f"Failed to initialize Trading Engine: {e}")
            self._update_state(TradingEngineState.ERROR, str(e))
            raise

    async def start(self, symbols: Optional[List[str]] = None):
        """Start the trading engine."""
        try:
            if self.state not in [
                TradingEngineState.INACTIVE,
                TradingEngineState.PAUSED,
            ]:
                raise ValueError(f"Cannot start engine in state: {self.state}")

            logger.info("Starting Trading Engine...")
            self._update_state(TradingEngineState.STARTING)

            # Set enabled symbols
            if symbols:
                self.config.enabled_symbols = set(symbols)
            elif not self.config.enabled_symbols:
                # Default to all available symbols
                available_symbols = await market_data_service.get_available_symbols()
                # Limit to first 5
                self.config.enabled_symbols = set(available_symbols[:5])

            logger.info(
                f"Trading engine will monitor symbols: "
                f"{list(self.config.enabled_symbols)}"
            )

            # Start signal processing for enabled symbols
            await signal_processing_service.start_signal_processing(
                list(self.config.enabled_symbols)
            )

            # Start background tasks
            self.engine_task = asyncio.create_task(self._trading_engine_loop())
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            self.position_update_task = asyncio.create_task(
                self._position_update_loop()
            )

            self._update_state(TradingEngineState.ACTIVE)
            logger.info("Trading Engine started successfully")

        except Exception as e:
            logger.error(f"Failed to start Trading Engine: {e}")
            self._update_state(TradingEngineState.ERROR, str(e))
            raise

    async def stop(self):
        """Stop the trading engine."""
        try:
            logger.info("Stopping Trading Engine...")
            self._update_state(TradingEngineState.STOPPING)

            # Cancel background tasks
            tasks = [self.engine_task, self.monitoring_task, self.position_update_task]
            for task in tasks:
                if task and not task.done():
                    task.cancel()

            # Wait for tasks to complete
            for task in tasks:
                if task:
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            # Stop signal processing
            try:
                await signal_processing_service.stop_signal_processing(
                    list(self.config.enabled_symbols)
                )
            except Exception as e:
                logger.warning(f"Error stopping signal processing: {e}")

            self._update_state(TradingEngineState.INACTIVE)
            logger.info("Trading Engine stopped")

        except Exception as e:
            logger.error(f"Error stopping Trading Engine: {e}")
            self._update_state(TradingEngineState.ERROR, str(e))

    async def pause(self):
        """Pause the trading engine (stop creating new orders)."""
        if self.state == TradingEngineState.ACTIVE:
            self._update_state(TradingEngineState.PAUSED)
            logger.info("Trading Engine paused")

    async def resume(self):
        """Resume the trading engine."""
        if self.state == TradingEngineState.PAUSED:
            self._update_state(TradingEngineState.ACTIVE)
            logger.info("Trading Engine resumed")

    async def _trading_engine_loop(self):
        """Main trading engine loop."""
        logger.info("Trading engine loop started")

        try:
            while self.state in [TradingEngineState.ACTIVE, TradingEngineState.PAUSED]:
                try:
                    if self.state == TradingEngineState.ACTIVE:
                        # Check circuit breaker before processing
                        if self._check_circuit_breaker():
                            logger.info(
                                "Circuit breaker triggered - pausing trading engine"
                            )
                            await self.pause()
                            continue

                        # Process signals for all enabled symbols
                        await self._process_signals()

                        # Monitor and manage existing orders
                        await self._manage_orders()

                        # Update position tracking
                        await self._update_positions()

                    # Update metrics
                    self._update_metrics()

                    # Wait before next iteration
                    await asyncio.sleep(1.0)

                except Exception as e:
                    logger.error(f"Error in trading engine loop: {e}")
                    await asyncio.sleep(5.0)  # Wait longer on error

        except asyncio.CancelledError:
            logger.info("Trading engine loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in trading engine loop: {e}")
            self._update_state(TradingEngineState.ERROR, str(e))

    async def _process_signals(self):
        """Process signals from the signal processing service."""
        try:
            # Get recent signals for enabled symbols
            cutoff_time = datetime.utcnow() - timedelta(
                minutes=self.config.signal_timeout_minutes
            )

            for symbol in self.config.enabled_symbols:
                try:
                    # Add timeout for signal retrieval to prevent hanging
                    recent_signals = await asyncio.wait_for(
                        signal_processing_service.get_recent_signals(
                            symbol=symbol, limit=5, hours_back=1
                        ),
                        timeout=5.0,  # 5 second timeout
                    )

                    for signal in recent_signals:
                        if signal.timestamp > cutoff_time:
                            await self._handle_signal(signal)

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timeout processing signals for {symbol} - "
                        f"skipping this cycle"
                    )
                    self._record_error()
                except Exception as e:
                    logger.error(f"Error processing signals for {symbol}: {e}")
                    self._record_error()

        except Exception as e:
            logger.error(f"Error in signal processing: {e}")

    async def _handle_signal(self, signal: SignalData):
        """Handle a trading signal."""
        try:
            # Check if signal meets minimum confidence threshold
            if signal.confidence < self.config.min_signal_confidence:
                logger.debug(
                    f"Signal confidence {signal.confidence:.2f} below threshold "
                    f"{self.config.min_signal_confidence}"
                )
                return

            # Check if we already have recent orders for this symbol
            symbol_orders = await order_management_service.get_orders(
                symbol=signal.symbol, limit=5
            )

            # Check for recent orders (last 30 minutes)
            recent_cutoff = datetime.utcnow() - timedelta(minutes=30)
            recent_orders = [
                order
                for order in symbol_orders
                if order.created_at > recent_cutoff and order.signal_id
            ]

            if recent_orders:
                logger.debug(
                    f"Skipping signal for {signal.symbol} - recent orders exist"
                )
                return

            # Calculate position size
            position_size = self._calculate_position_size(signal)
            if position_size <= 0:
                logger.debug(
                    f"Position size calculation returned {position_size} "
                    f"for {signal.symbol}"
                )
                return

            # Check risk limits
            if not await self._check_risk_limits(signal.symbol, position_size):
                logger.warning(f"Risk limits exceeded for {signal.symbol}")
                return

            # Determine execution mode
            should_auto_execute = (
                self.config.trading_mode == TradingMode.FULLY_AUTO
                or (
                    self.config.trading_mode == TradingMode.SEMI_AUTO
                    and signal.confidence >= self.config.auto_execute_confidence
                )
            )

            # Create order from signal
            order = await order_management_service.create_order_from_signal(
                signal=signal,
                quantity=position_size,
                order_type=OrderType.MARKET,
                auto_execute=should_auto_execute,
            )

            self.metrics.signals_processed += 1
            self.metrics.orders_created += 1
            self.metrics.last_signal_time = signal.timestamp

            logger.info(
                f"Created order {order.id} from signal: {signal.direction:+d} "
                f"{position_size} {signal.symbol}"
            )

            # Notify callbacks
            for callback in self.signal_callbacks:
                try:
                    callback(signal)
                except Exception as e:
                    logger.error(f"Error in signal callback: {e}")

        except Exception as e:
            logger.error(f"Error handling signal for {signal.symbol}: {e}")

    async def _manage_orders(self):
        """Monitor and manage existing orders."""
        try:
            # Get all active orders with timeout
            try:
                active_orders = await asyncio.wait_for(
                    order_management_service.get_orders(limit=100),
                    timeout=10.0,  # 10 second timeout
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timeout getting active orders - " "skipping order management cycle"
                )
                return
            except Exception as e:
                logger.error(f"Error getting active orders: {e}")
                return

            for order in active_orders:
                try:
                    # Check for timeout orders
                    order_age = datetime.utcnow() - order.created_at
                    timeout_minutes = self.config.order_timeout_minutes
                    if order_age > timedelta(minutes=timeout_minutes):
                        if order.status in ["pending", "submitted"]:
                            logger.info(
                                f"Cancelling timeout order {order.id} "
                                f"(age: {order_age})"
                            )
                            try:
                                cancel_task = order_management_service.cancel_order(
                                    order.id
                                )
                                await asyncio.wait_for(
                                    cancel_task,
                                    timeout=5.0,  # 5 second timeout for cancellation
                                )
                                self.metrics.orders_cancelled += 1
                            except asyncio.TimeoutError:
                                logger.error(f"Timeout cancelling order {order.id}")
                            except Exception as e:
                                logger.error(f"Error cancelling order {order.id}: {e}")

                    # Update position tracking based on filled orders
                    if (
                        order.status == "filled"
                        and order.symbol in self.config.enabled_symbols
                    ):
                        await self._update_position_from_order(order)

                except Exception as e:
                    logger.error(f"Error managing order {order.id}: {e}")

        except Exception as e:
            logger.error(f"Error in order management: {e}")

    async def _update_positions(self):
        """Update position tracking."""
        try:
            for symbol in self.config.enabled_symbols:
                if symbol not in self.positions:
                    self.positions[symbol] = PositionData(symbol=symbol)

                position = self.positions[symbol]

                # Get current market price for P&L calculation with timeout
                try:
                    tick_data = await asyncio.wait_for(
                        market_data_service.get_latest_tick(symbol),
                        timeout=3.0,  # 3 second timeout
                    )
                    if tick_data and position.quantity != 0:
                        current_price = tick_data["price"]
                        position.market_value = position.quantity * current_price

                        if position.avg_price:
                            position.unrealized_pnl = (
                                current_price - position.avg_price
                            ) * position.quantity

                        position.last_updated = datetime.utcnow()

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timeout getting market data for {symbol} - "
                        f"skipping position update"
                    )
                except Exception as e:
                    logger.debug(f"Error updating position for {symbol}: {e}")

            # Update metrics
            self.metrics.active_positions = sum(
                1 for pos in self.positions.values() if pos.quantity != 0
            )

        except Exception as e:
            logger.error(f"Error updating positions: {e}")

    async def _update_position_from_order(self, order: OrderData):
        """Update position based on filled order."""
        try:
            if order.symbol not in self.positions:
                self.positions[order.symbol] = PositionData(symbol=order.symbol)

            position = self.positions[order.symbol]

            # Calculate new position
            if order.side == OrderSide.BUY:
                new_quantity = position.quantity + order.filled_quantity
            else:
                new_quantity = position.quantity - order.filled_quantity

            # Update average price
            if new_quantity != 0 and order.avg_fill_price:
                if position.quantity == 0:
                    # New position
                    position.avg_price = order.avg_fill_price
                else:
                    # Update average price
                    position_cost = position.quantity * (position.avg_price or 0)
                    side_multiplier = 1 if order.side == OrderSide.BUY else -1
                    order_cost = (
                        order.filled_quantity * order.avg_fill_price * side_multiplier
                    )
                    total_cost = position_cost + order_cost
                    position.avg_price = total_cost / new_quantity

            position.quantity = new_quantity
            position.last_updated = datetime.utcnow()

            # Update metrics
            if order.status == "filled":
                self.metrics.orders_executed += 1
                self.metrics.successful_trades += 1
                self.metrics.last_trade_time = order.filled_at

            logger.info(
                f"Updated position for {order.symbol}: {position.quantity} @ "
                f"{position.avg_price}"
            )

        except Exception as e:
            logger.error(f"Error updating position from order {order.id}: {e}")

    def _calculate_position_size(self, signal: SignalData) -> float:
        """Calculate position size for a signal."""
        try:
            # Base position size (could be based on account size, risk per trade, etc.)
            base_size = 10000.0  # Default base position size

            # Apply confidence multiplier
            confidence_multiplier = signal.confidence

            # Apply configured multiplier
            position_multiplier = self.config.position_size_multiplier

            # Calculate final size
            position_size = base_size * confidence_multiplier * position_multiplier

            # Apply maximum position limit
            position_size = min(position_size, self.config.max_position_size)

            return round(position_size, 2)

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0

    async def _check_risk_limits(self, symbol: str, position_size: float) -> bool:
        """Check if trade meets risk management limits."""
        try:
            # Check maximum position size
            if position_size > self.config.max_position_size:
                return False

            # Check current position exposure
            current_position = self.positions.get(symbol, PositionData(symbol=symbol))
            total_exposure = abs(current_position.quantity + position_size)
            if total_exposure > self.config.max_position_size:
                return False

            # Check daily volume limit (simplified)
            # In production, this would track actual daily volume

            # Check maximum concurrent orders
            active_orders = await order_management_service.get_orders(limit=100)
            if len(active_orders) >= self.config.max_concurrent_orders:
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return False

    async def _monitoring_loop(self):
        """Background monitoring and maintenance loop."""
        logger.info("Trading engine monitoring loop started")

        try:
            states_to_run = [TradingEngineState.ACTIVE, TradingEngineState.PAUSED]
            while self.state in states_to_run:
                try:
                    # Log status periodically
                    signals_processed = self.metrics.signals_processed
                    if signals_processed % 10 == 0 and signals_processed > 0:
                        logger.info(
                            f"Trading Engine Status: {signals_processed} signals, "
                            f"{self.metrics.orders_created} orders, "
                            f"{self.metrics.active_positions} positions"
                        )

                    # Perform health checks
                    await self._health_check()

                    await asyncio.sleep(30.0)  # Monitor every 30 seconds

                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(60.0)

        except asyncio.CancelledError:
            logger.info("Trading engine monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}")

    async def _position_update_loop(self):
        """Background position update loop."""
        logger.info("Trading engine position update loop started")

        try:
            states_to_run = [TradingEngineState.ACTIVE, TradingEngineState.PAUSED]
            while self.state in states_to_run:
                try:
                    await self._update_positions()
                    await asyncio.sleep(5.0)  # Update positions every 5 seconds

                except Exception as e:
                    logger.error(f"Error in position update loop: {e}")
                    await asyncio.sleep(10.0)

        except asyncio.CancelledError:
            logger.info("Trading engine position update loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in position update loop: {e}")

    async def _health_check(self):
        """Perform system health checks."""
        try:
            # Check database connectivity
            if self._pool:
                async with self._pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")

            # Check service health
            symbols = await market_data_service.get_available_symbols()
            if not symbols:
                logger.warning("No symbols available from market data service")

        except Exception as e:
            logger.error(f"Health check failed: {e}")

    def _update_metrics(self):
        """Update engine metrics."""
        if self.start_time:
            self.metrics.uptime_seconds = (
                datetime.utcnow() - self.start_time
            ).total_seconds()

        # Calculate total P&L
        total_pnl = sum(
            (pos.unrealized_pnl or 0.0) + pos.realized_pnl
            for pos in self.positions.values()
        )
        self.metrics.total_pnl = total_pnl

    def _record_error(self):
        """Record an error for circuit breaker tracking."""
        now = datetime.utcnow()
        self.metrics.errors += 1
        self.metrics.recent_errors.append(now)

        # Keep only errors from the last minute
        cutoff = now - timedelta(minutes=1)
        self.metrics.recent_errors = [
            error_time
            for error_time in self.metrics.recent_errors
            if error_time > cutoff
        ]

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker should be triggered."""
        now = datetime.utcnow()

        # Check if we're already in circuit breaker mode
        if self.metrics.circuit_breaker_triggered:
            if (
                self.metrics.circuit_breaker_until
                and now < self.metrics.circuit_breaker_until
            ):
                return True  # Still in circuit breaker mode
            else:
                # Reset circuit breaker
                self.metrics.circuit_breaker_triggered = False
                self.metrics.circuit_breaker_until = None
                logger.info("Circuit breaker reset - resuming normal operation")
                return False

        # Check if we should trigger circuit breaker
        if len(self.metrics.recent_errors) >= self.config.max_errors_per_minute:
            self.metrics.circuit_breaker_triggered = True
            pause_minutes = self.config.circuit_breaker_pause_minutes
            self.metrics.circuit_breaker_until = now + timedelta(minutes=pause_minutes)
            error_count = len(self.metrics.recent_errors)
            logger.error(
                f"Circuit breaker triggered: {error_count} errors in last minute. "
                f"Pausing for {pause_minutes} minutes."
            )
            return True

        return False

    async def _load_configuration(self):
        """Load configuration from database or file."""
        try:
            # For now, use defaults
            # In production, load from database or config file
            logger.info("Using default trading engine configuration")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")

    async def _load_positions(self):
        """Load current positions from database."""
        try:
            # Initialize empty positions for configured symbols
            available_symbols = await market_data_service.get_available_symbols()
            for symbol in available_symbols[:5]:  # Limit to first 5
                self.positions[symbol] = PositionData(symbol=symbol)

            position_count = len(self.positions)
            logger.info(f"Initialized position tracking for {position_count} symbols")

        except Exception as e:
            logger.error(f"Error loading positions: {e}")

    def _setup_service_callbacks(self):
        """Set up callbacks from dependent services."""
        try:
            # Set up order update callback
            order_service = order_management_service
            order_service.add_order_update_callback(self._on_order_update)
            order_service.add_execution_callback(self._on_execution)

            logger.info("Service callbacks configured")

        except Exception as e:
            logger.error(f"Error setting up service callbacks: {e}")

    def _on_order_update(self, order: OrderData):
        """Handle order updates from order management service."""
        try:
            # Update metrics based on order status
            if order.status == "filled":
                self.metrics.successful_trades += 1
            elif order.status == "cancelled":
                self.metrics.orders_cancelled += 1
            elif order.status == "rejected":
                self.metrics.failed_trades += 1

            # Notify callbacks
            for callback in self.order_callbacks:
                try:
                    callback(order)
                except Exception as e:
                    logger.error(f"Error in order callback: {e}")

        except Exception as e:
            logger.error(f"Error handling order update: {e}")

    def _on_execution(self, execution: OrderExecution):
        """Handle execution reports from order management service."""
        try:
            self.metrics.orders_executed += 1

            # Notify callbacks
            for callback in self.execution_callbacks:
                try:
                    callback(execution)
                except Exception as e:
                    logger.error(f"Error in execution callback: {e}")

        except Exception as e:
            logger.error(f"Error handling execution: {e}")

    def _update_state(
        self, new_state: TradingEngineState, error_message: Optional[str] = None
    ):
        """Update engine state and notify callbacks."""
        old_state = self.state
        self.state = new_state
        self.error_message = error_message

        logger.info(f"Trading Engine state: {old_state.value} → {new_state.value}")

        # Notify callbacks
        for callback in self.state_callbacks:
            try:
                callback(new_state)
            except Exception as e:
                logger.error(f"Error in state callback: {e}")

    # Configuration methods

    def set_trading_mode(self, mode: TradingMode):
        """Set trading mode."""
        self.config.trading_mode = mode
        logger.info(f"Trading mode set to: {mode.value}")

    def set_enabled_symbols(self, symbols: List[str]):
        """Set enabled trading symbols."""
        self.config.enabled_symbols = set(symbols)
        logger.info(f"Enabled symbols: {symbols}")

    def set_confidence_threshold(self, threshold: float):
        """Set minimum signal confidence threshold."""
        self.config.min_signal_confidence = max(0.0, min(1.0, threshold))
        threshold_value = self.config.min_signal_confidence
        logger.info(f"Signal confidence threshold: {threshold_value}")

    # Query methods

    def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        return {
            "state": self.state.value,
            "trading_mode": self.config.trading_mode.value,
            "enabled_symbols": list(self.config.enabled_symbols),
            "metrics": {
                "signals_processed": self.metrics.signals_processed,
                "orders_created": self.metrics.orders_created,
                "orders_executed": self.metrics.orders_executed,
                "successful_trades": self.metrics.successful_trades,
                "active_positions": self.metrics.active_positions,
                "total_pnl": self.metrics.total_pnl,
                "uptime_seconds": self.metrics.uptime_seconds,
            },
            "error_message": self.error_message,
            "start_time": (self.start_time.isoformat() if self.start_time else None),
        }

    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current positions."""
        return {
            symbol: {
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "market_value": pos.market_value,
                "unrealized_pnl": pos.unrealized_pnl,
                "realized_pnl": pos.realized_pnl,
                "last_updated": pos.last_updated.isoformat(),
            }
            for symbol, pos in self.positions.items()
        }

    def get_account_info(self) -> Dict[str, Any]:
        """Get current account information for API responses."""
        # Calculate total P&L from positions
        total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        total_realized = sum(pos.realized_pnl for pos in self.positions.values())

        # Get current configuration for account settings
        base_balance = getattr(self.config, "initial_capital", 100000.0)

        # Calculate margin usage (simplified - 2% margin requirement)
        position_values = [abs(pos.market_value) for pos in self.positions.values()]
        total_position_value = sum(position_values)
        margin_used = total_position_value * 0.02

        # Generate a consistent account number based on engine state
        if self.start_time:
            account_hash = hash(str(self.start_time)) % 100000000
            account_number = f"TE_{account_hash:08d}"
        else:
            account_number = "TE_00000000"

        return {
            "id": "trading_engine_account",
            "account_number": account_number,
            "currency": "USD",
            "balance": base_balance,
            "equity": base_balance + total_unrealized + total_realized,
            "margin_used": margin_used,
            "margin_available": max(0, base_balance + total_realized - margin_used),
            "unrealized_pnl": total_unrealized,
            "realized_pnl": total_realized,
            "total_orders": (
                len(getattr(self, "active_orders", {}))
                if hasattr(self, "active_orders")
                else 0
            ),
            "last_updated": datetime.utcnow().isoformat(),
        }

    # Event subscription methods

    def add_signal_callback(self, callback: Callable[[SignalData], None]):
        """Add callback for signal events."""
        self.signal_callbacks.append(callback)

    def add_order_callback(self, callback: Callable[[OrderData], None]):
        """Add callback for order events."""
        self.order_callbacks.append(callback)

    def add_execution_callback(self, callback: Callable[[OrderExecution], None]):
        """Add callback for execution events."""
        self.execution_callbacks.append(callback)

    def add_state_callback(self, callback: Callable[[TradingEngineState], None]):
        """Add callback for state changes."""
        self.state_callbacks.append(callback)

    async def close(self):
        """Close the trading engine."""
        try:
            logger.info("Closing Trading Engine...")

            # Stop if running
            if self.state != TradingEngineState.INACTIVE:
                await self.stop()

            logger.info("Trading Engine closed")

        except Exception as e:
            logger.error(f"Error closing Trading Engine: {e}")


# Global service instance
trading_engine_service = TradingEngine()
